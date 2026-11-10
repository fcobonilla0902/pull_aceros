"""Reviewable CSV/XLSX imports; reservations and historical deliveries cannot be overwritten."""
import csv
import hashlib
import io
import json
import secrets
import unicodedata
import zipfile
from datetime import timedelta
from decimal import Decimal,InvalidOperation
from pathlib import Path
from fastapi import APIRouter,Depends,File,Form,UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select,update
from sqlalchemy.exc import IntegrityError
from openpyxl import Workbook,load_workbook
from openpyxl.utils.exceptions import InvalidFileException
from xml.etree.ElementTree import ParseError
from database import Part,Location,Roll,RequestItem,InventoryImport,now
from security import require,db_session
from schemas import ImportCommit
from api import fail,audit,serialize

router=APIRouter(prefix='/api/inventory/import')
MAX_BYTES=5*1024*1024
MAX_ROWS=5000
FIELDS=['codigo_rollo','numero_parte','ubicacion','kg','estado']
ALIASES={
    'codigo_rollo':['codigo_rollo','rollo','codigo','lote','lot','ld_lot'],
    'numero_parte':['numero_parte','parte','np','part','item','ld_part'],
    'ubicacion':['ubicacion','location','almacen','ld_loc'],
    'kg':['kg','peso_kg','peso','kilogramos','cantidad_kg'],
    'estado':['estado','estatus','status']}

def normalize(value):
    value=unicodedata.normalize('NFKD',str(value or '')).encode('ascii','ignore').decode().lower()
    return ''.join(c for c in value if c.isalnum())

def read_table(raw,filename):
    suffix=Path(filename).suffix.lower()
    if suffix=='.csv':
        try:text=raw.decode('utf-8-sig')
        except UnicodeDecodeError:text=raw.decode('cp1252')
        try:delimiter=csv.Sniffer().sniff(text[:8192],delimiters=',;\t').delimiter
        except csv.Error:delimiter=','
        reader=csv.reader(io.StringIO(text),delimiter=delimiter)
        table=[]
        for row in reader:
            if len(row)>50:raise ValueError('El archivo admite hasta 50 columnas')
            if any(str(c).strip() for c in row):table.append(row)
            if len(table)>MAX_ROWS+1:raise ValueError(f'El límite es {MAX_ROWS} filas de inventario')
    elif suffix=='.xlsx':
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            if sum(e.file_size for e in archive.infolist())>50*1024*1024:raise ValueError('El Excel descomprimido supera 50 MB')
        workbook=load_workbook(io.BytesIO(raw),read_only=True,data_only=False,keep_links=False)
        try:
            sheet=workbook.worksheets[0]
            if sheet.max_column>50 or sheet.max_row>MAX_ROWS+1:raise ValueError('Usa la primera hoja con hasta 5000 filas y 50 columnas, sin filas formateadas adicionales')
            table=[]
            for cells in sheet.iter_rows():
                if any(c.data_type=='f' for c in cells):raise ValueError('No se admiten fórmulas; pega los valores antes de importar')
                row=[c.value if c.value is not None else '' for c in cells]
                if any(str(c).strip() for c in row):table.append(row)
        finally:workbook.close()
    else:raise ValueError('Selecciona un archivo .csv o .xlsx; para QAD exporta primero a uno de estos formatos')
    if len(table)<2:raise ValueError('El archivo debe contener encabezados y al menos una fila')
    headers=[str(v).strip() for v in table[0]]
    if len(set(headers))!=len(headers) or any(not h for h in headers):raise ValueError('Los encabezados deben ser únicos y no estar vacíos')
    return headers,table[1:]

def review(db,rows,update_existing):
    parts={p.code:p for p in db.scalars(select(Part))}
    locations={l.code:l for l in db.scalars(select(Location))}
    existing={r.code:r for r in db.scalars(select(Roll))}
    errors=[];actions=[];seen=set();counts={'creates':0,'updates':0,'unchanged':0}
    for index,row in enumerate(rows,2):
        try:
            if row['codigo_rollo'] in seen:raise ValueError('Código de rollo repetido dentro del archivo')
            seen.add(row['codigo_rollo'])
            part=parts.get(row['numero_parte']);location=locations.get(row['ubicacion'])
            if not part or not part.active:raise ValueError('Número de parte inexistente o inactivo')
            if not location or not location.active:raise ValueError('Ubicación inexistente o inactiva')
            current=existing.get(row['codigo_rollo'])
            values={'code':row['codigo_rollo'],'part_id':part.id,'location_id':location.id,'kg':row['kg'],'status':row['estado']}
            action='create'
            if current:
                if not update_existing:raise ValueError('El rollo ya existe; activa actualizar existentes si corresponde')
                if current.status not in ['DISP','BLOQUEADO'] or current.request_id is not None:raise ValueError('Un rollo reservado o entregado no se puede sobrescribir')
                if current.part_id!=part.id and db.scalar(select(RequestItem.id).where(RequestItem.preferred_roll_id==current.id)):raise ValueError('El rollo tiene referencias históricas; no se cambia su parte')
                action='unchanged' if all(getattr(current,k)==v for k,v in values.items()) else 'update'
            counts[{'create':'creates','update':'updates','unchanged':'unchanged'}[action]]+=1
            actions.append({'row':index,'values':values,'action':action,'existing_id':current.id if current else None,'version':current.version if current else None})
        except ValueError as error:errors.append({'row':index,'error':str(error)})
    return actions,errors,counts

@router.get('/template')
def template(format:str='xlsx',user=Depends(require('inventory'))):
    if format not in ['xlsx','csv']:fail('Formato inválido',422)
    example=['ROLLO-EJEMPLO-001','PARTE-EJEMPLO','ALM-EJEMPLO',1000,'DISP']
    if format=='csv':
        buffer=io.StringIO();writer=csv.writer(buffer);writer.writerow(FIELDS);writer.writerow(example)
        content=('\ufeff'+buffer.getvalue()).encode('utf-8');media='text/csv; charset=utf-8'
    else:
        book=Workbook();sheet=book.active;sheet.title='Inventario';sheet.append(FIELDS);sheet.append(example)
        for col in ['A','B','C','E']:sheet[f'{col}2'].number_format='@';sheet.column_dimensions[col].width=24
        buffer=io.BytesIO();book.save(buffer);book.close();content=buffer.getvalue();media='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    return StreamingResponse(iter([content]),media_type=media,headers={'Content-Disposition':f'attachment; filename=plantilla-inventario.{format}'})

@router.post('/preview')
def preview(file:UploadFile=File(...),mapping:str=Form('{}'),update_existing:bool=Form(False),user=Depends(require('inventory')),db=Depends(db_session,scope='function')):
    raw=file.file.read(MAX_BYTES+1)
    if len(raw)>MAX_BYTES:fail('El archivo debe pesar como máximo 5 MB',413)
    try:
        headers,table=read_table(raw,file.filename or '')
        selected=json.loads(mapping)
        if not isinstance(selected,dict) or set(selected)-set(FIELDS):raise ValueError('Mapeo de columnas inválido')
        if any(not isinstance(v,(str,type(None))) for v in selected.values()):raise ValueError('Mapeo de columnas inválido')
        normalized={normalize(h):h for h in headers}
        for field in FIELDS:
            if field not in selected:selected[field]=next((normalized[normalize(a)] for a in ALIASES[field] if normalize(a) in normalized),None)
        missing=[field for field in FIELDS[:-1] if selected.get(field) not in headers]
        if selected.get('estado') and selected['estado'] not in headers:missing.append('estado')
        if missing:return {'valid':False,'headers':headers,'mapping':selected,'total':len(table),'errors':[{'row':1,'error':'Asigna las columnas: '+', '.join(missing)}],'sample':[]}
        parsed=[];parse_errors=[]
        for number,row in enumerate(table,2):
            try:
                values={field:(row[headers.index(selected[field])] if headers.index(selected[field])<len(row) else '') if selected.get(field) else 'DISP' for field in FIELDS}
                values={key:str(value).strip() for key,value in values.items()}
                if any(value.startswith('=') for value in values.values()):raise ValueError('No se admiten fórmulas')
                for field in ['codigo_rollo','numero_parte','ubicacion']:
                    if not values[field] or len(values[field])>80:raise ValueError(f'{field}: usa de 1 a 80 caracteres')
                weight=Decimal(values['kg'].replace(',','.'))
                if not weight.is_finite() or not 0<weight<=1000000:raise ValueError('kg debe ser mayor a cero y no superar 1000000')
                values['kg']=float(weight);values['estado']=values['estado'].upper() or 'DISP'
                if values['estado'] not in ['DISP','BLOQUEADO']:raise ValueError('Estado permitido: DISP o BLOQUEADO')
                parsed.append(values)
            except (ValueError,InvalidOperation):parse_errors.append({'row':number,'error':'Fila inválida: revisa códigos, kg positivos sin separador de miles y estado DISP/BLOQUEADO'})
        if parse_errors:return {'valid':False,'headers':headers,'mapping':selected,'total':len(table),'errors':parse_errors[:200],'error_count':len(parse_errors),'sample':[]}
        actions,errors,counts=review(db,parsed,update_existing)
        result={'valid':not errors,'headers':headers,'mapping':selected,'total':len(parsed),'errors':errors[:200],'error_count':len(errors),'sample':parsed[:50],**counts,'source_sha256':hashlib.sha256(raw).hexdigest()}
        if not errors:
            token=secrets.token_urlsafe(32);expires=now()+timedelta(minutes=30)
            expected={a['values']['code']:{'id':a['existing_id'],'version':a['version']} for a in actions}
            db.add(InventoryImport(token_digest=hashlib.sha256(token.encode()).hexdigest(),user_id=user.id,filename=Path(file.filename or 'inventario').name[:200],payload=json.dumps({'rows':parsed,'expected':expected}),update_existing=update_existing,expires_at=expires))
            result.update(token=token,expires_at=expires)
        return result
    except (ValueError,UnicodeError,zipfile.BadZipFile,KeyError,IndexError,TypeError,InvalidFileException,ParseError) as error:fail('Archivo inválido: '+str(error),422)

@router.post('/commit')
def commit(data:ImportCommit,user=Depends(require('inventory')),db=Depends(db_session,scope='function')):
    digest=hashlib.sha256(data.token.encode()).hexdigest()
    batch=db.scalar(select(InventoryImport).where(InventoryImport.token_digest==digest,InventoryImport.user_id==user.id))
    if not batch:fail('Vista previa inexistente',404)
    if batch.expires_at<now():fail('La vista previa venció; vuelve a revisar el archivo')
    if db.execute(update(InventoryImport).where(InventoryImport.id==batch.id,InventoryImport.committed_at.is_(None)).values(committed_at=now())).rowcount!=1:fail('Este archivo ya fue confirmado')
    payload=json.loads(batch.payload)
    actions,errors,counts=review(db,payload['rows'],batch.update_existing)
    if errors:fail({'message':'El inventario cambió; vuelve a generar la vista previa','errors':errors[:200]})
    for action in actions:
        expected=payload['expected'][action['values']['code']]
        if expected!={'id':action['existing_id'],'version':action['version']}:fail('Un rollo cambió desde la vista previa; revisa nuevamente el archivo')
    try:
        for action in actions:
            if action['action']=='unchanged':continue
            if action['action']=='create':db.add(Roll(**action['values']))
            else:
                old=db.get(Roll,action['existing_id']);before=serialize(old)
                if db.execute(update(Roll).where(Roll.id==old.id,Roll.version==action['version'],Roll.request_id.is_(None),Roll.status.in_(['DISP','BLOQUEADO'])).values(**action['values'],version=Roll.version+1)).rowcount!=1:fail('Otro movimiento cambió un rollo; vuelve a revisar el archivo')
                audit(db,user,'Rollo actualizado por archivo',json.dumps({'antes':before,'despues':action['values']},default=str,ensure_ascii=False))
        db.flush()
    except IntegrityError:fail('Otro usuario registró uno de los códigos; vuelve a generar la vista previa')
    audit(db,user,'Inventario importado',json.dumps({'archivo':batch.filename,'filas':len(actions),**counts},ensure_ascii=False))
    return {'ok':True,'total':len(actions),**counts}
