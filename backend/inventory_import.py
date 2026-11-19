"""Importaciones revisables de CSV/XLSX; las reservas y las entregas históricas no se pueden sobrescribir."""
import csv
import hashlib
import io
import json
import re
import secrets
import unicodedata
import zipfile
from datetime import date, timedelta
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
SOURCE_FIELDS = [
    'Número Artículo', 'Descripción', 'Línea de productos', 'Descripción Línea Producto',
    'Grupo', 'Descripción Grupo', 'Planta', 'Ubicación', 'Descripción Ubicación',
    'Lote/Serie', 'Referencia', 'Cantidad Existencias', 'Unidad de medida',
    'Fcha Recepcn', 'Orden Compra', 'Expira', 'Fecha Transferencia',
]
SOURCE_EXAMPLE = [
    '03003AA', 'CINTA', '1206', 'Dom Steel Chrysler DS', '1021', 'DS', '100215',
    '1601OB', 'OBSOLETOS VL', 'AX0196040005', '10120', '3,731.0', 'KG',
    '25/06/2024', 'DCXT4095', '30/10/2026', '18/08/2026',
]
SOURCE_MAPPING = {
    'codigo_rollo': 'Lote/Serie', 'numero_parte': 'Número Artículo',
    'ubicacion': 'Ubicación', 'kg': 'Cantidad Existencias',
}
SOURCE_ALIASES = {
    'Número Artículo': ['Número de artículo', 'Núm. artículo', 'Nro. artículo', 'Nº artículo', 'N° artículo', 'No. artículo', 'Artículo'],
    'Lote/Serie': ['Lote de serie', 'Lote / N.º de serie', 'Lote o serie', 'Lote', 'Serie'],
    'Cantidad Existencias': ['Cantidad de existencias', 'Cantidad en existencias', 'Cantidad en existencia', 'Existencias'],
    'Unidad de medida': ['Unidad medida', 'U. Medida', 'U.M.', 'Unidad'],
    'Descripción': ['Descripción artículo', 'Descripción del artículo'],
    'Planta': ['Planta de almacén', 'Código de planta'],
    'Fcha Recepcn': ['Fecha Recepción', 'Fecha de recepción'],
}
ALIASES={
    'codigo_rollo':['codigo_rollo','rollo','codigo','lote','lot','ld_lot',SOURCE_MAPPING['codigo_rollo'],*SOURCE_ALIASES['Lote/Serie']],
    'numero_parte':['numero_parte','parte','np','part','item','ld_part',SOURCE_MAPPING['numero_parte'],*SOURCE_ALIASES['Número Artículo']],
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
            if any(str(c).strip() for c in row):table.append((reader.line_num,row))
            if len(table)>MAX_ROWS+1:raise ValueError(f'El límite es {MAX_ROWS} filas de inventario')
    elif suffix=='.xlsx':
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            if sum(e.file_size for e in archive.infolist())>50*1024*1024:raise ValueError('El Excel descomprimido supera 50 MB')
        workbook=load_workbook(io.BytesIO(raw),read_only=True,data_only=False,keep_links=False)
        try:
            sheet=workbook.worksheets[0]
            if sheet.max_column>50 or sheet.max_row>MAX_ROWS+1:raise ValueError('Usa la primera hoja con hasta 5000 filas y 50 columnas, sin filas formateadas adicionales')
            table=[]
            for number,cells in enumerate(sheet.iter_rows(),1):
                if any(c.data_type=='f' for c in cells):raise ValueError('No se admiten fórmulas; pega los valores antes de importar')
                row=[c.value if c.value is not None else '' for c in cells]
                if any(str(c).strip() for c in row):table.append((number,row))
        finally:workbook.close()
    else:raise ValueError('Selecciona un archivo .csv o .xlsx; para QAD exporta primero a uno de estos formatos')
    if len(table)<2:raise ValueError('El archivo debe contener encabezados y al menos una fila')
    headers=[str(v).strip() for v in table[0][1]]
    if len(set(headers))!=len(headers) or any(not h for h in headers):raise ValueError('Los encabezados deben ser únicos y no estar vacíos')
    return headers,table[1:]

def source_text(value):
    return value.strftime('%d/%m/%Y') if isinstance(value,date) else str(value).strip()


def stock_weight(value):
    if re.fullmatch(r'[0-9]{1,3}(,[0-9]{3})+(\.[0-9]+)?', value):
        return value.replace(',', '')
    if re.fullmatch(r'[0-9]{1,3}(\.[0-9]{3})+,[0-9]+', value):
        return value.replace('.', '').replace(',', '.')
    return value.replace(',', '.')


def stock_identity(source):
    return tuple(source.get(field,'') for field in ('Lote/Serie','Número Artículo','Planta','Ubicación','Referencia','Orden Compra'))


def stock_roll_code(source, known_codes, occupied):
    identity = stock_identity(source)
    if identity in known_codes:
        return known_codes[identity]
    lot = source['Lote/Serie']
    if lot not in occupied:
        return lot
    digest = hashlib.sha256(json.dumps(identity,ensure_ascii=False).encode()).hexdigest()[:20]
    return f'{lot[:59]}-{digest}'


def review(db,rows,update_existing,*,persist_catalogs=False):
    parts={p.code:p for p in db.scalars(select(Part))}
    locations={l.code:l for l in db.scalars(select(Location))}
    existing={r.code:r for r in db.scalars(select(Roll))}
    known_codes = {stock_identity(roll.source_data):code for code,roll in existing.items() if roll.source_data}
    occupied = set(existing)
    errors=[];actions=[];seen=set();counts={'creates':0,'updates':0,'unchanged':0}
    for index,row in enumerate(rows,2):
        index = row.get('source_line',index)
        try:
            part=parts.get(row['numero_parte']);location=locations.get(row['ubicacion'])
            source = row.get('source_data')
            code = row['codigo_rollo']
            if source:
                identity = stock_identity(source)
                legacy = existing.get(code)
                if legacy and not legacy.source_data and part and location and (legacy.part_id,legacy.location_id) == (part.id,location.id) and code not in seen:
                    known_codes.setdefault(identity,code)
                code = stock_roll_code(source,known_codes,occupied)
                if code in existing and known_codes.get(identity) != code:
                    raise ValueError(f'El código {code} ya pertenece a otro rollo')
                known_codes[identity] = code
                occupied.add(code)
                if part is None:
                    description = source.get('Descripción','')
                    if not description or len(description)>200:
                        raise ValueError('Descripción: usa de 1 a 200 caracteres para registrar el artículo')
                    part = Part(code=row['numero_parte'], specification=description, active=True)
                    parts[part.code] = part
                    if persist_catalogs: db.add(part)
                if location is None:
                    location = Location(code=row['ubicacion'], active=True)
                    locations[location.code] = location
                    if persist_catalogs: db.add(location)
            if not part or not part.active:raise ValueError('Número de parte inexistente o inactivo')
            if not location or not location.active:raise ValueError('Ubicación inexistente o inactiva')
            if code in seen:raise ValueError('Código de rollo repetido dentro del archivo')
            seen.add(code)
            current=existing.get(code)
            if source and persist_catalogs and (part.id is None or location.id is None):
                db.flush()
            values={'code':code,'part_id':part.id,'location_id':location.id,'kg':row['kg'],'status':row['estado']}
            if source:
                values['source_data'] = source
                if current:
                    values['status'] = current.status
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
def template(format:str='xlsx',layout:str='standard',user=Depends(require('inventory'))):
    if format not in ['xlsx','csv']:fail('Formato inválido',422)
    if layout not in ['standard','stock']:fail('Plantilla inválida',422)
    fields = SOURCE_FIELDS if layout == 'stock' else FIELDS
    example = SOURCE_EXAMPLE if layout == 'stock' else ['ROLLO-EJEMPLO-001','PARTE-EJEMPLO','ALM-EJEMPLO',1000,'DISP']
    if format=='csv':
        buffer=io.StringIO();writer=csv.writer(buffer);writer.writerow(fields);writer.writerow(example)
        content=('\ufeff'+buffer.getvalue()).encode('utf-8');media='text/csv; charset=utf-8'
    else:
        book=Workbook();sheet=book.active;sheet.title='Inventario';sheet.append(fields);sheet.append(example)
        for cell in sheet[2]:
            if isinstance(cell.value,str):cell.number_format='@'
            sheet.column_dimensions[cell.column_letter].width=max(24,len(fields[cell.column-1])+2)
        buffer=io.BytesIO();book.save(buffer);book.close();content=buffer.getvalue();media='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    name = 'plantilla-existencias' if layout == 'stock' else 'plantilla-inventario'
    return StreamingResponse(iter([content]),media_type=media,headers={'Content-Disposition':f'attachment; filename={name}.{format}'})

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
        source_columns = {}
        for field in SOURCE_FIELDS:
            for label in (field, *SOURCE_ALIASES.get(field, ())):
                if normalize(label) in normalized:
                    source_columns[field] = normalized[normalize(label)]
                    break
        source_layout = all(field in source_columns for field in (*SOURCE_MAPPING.values(), 'Unidad de medida'))
        if source_layout:
            selected = {field: source_columns[header] for field,header in SOURCE_MAPPING.items()}
            selected['estado'] = None
            recognized = set(source_columns.values())
            source_columns.update({header: header for header in headers if header not in recognized})
        elif 'Cantidad Existencias' in source_columns and 'Unidad de medida' not in source_columns:
            return {'valid':False,'headers':headers,'mapping':selected,'source_layout':True,'total':len(table),'errors':[{'row':1,'error':'Incluye la columna «Unidad de medida» para verificar que las existencias estén en KG'}],'sample':[]}
        for field in FIELDS:
            if field not in selected:selected[field]=next((normalized[normalize(a)] for a in ALIASES[field] if normalize(a) in normalized),None)
        missing=[field for field in FIELDS[:-1] if selected.get(field) not in headers]
        if selected.get('estado') and selected['estado'] not in headers:missing.append('estado')
        if missing:return {'valid':False,'headers':headers,'mapping':selected,'total':len(table),'errors':[{'row':1,'error':'Asigna las columnas: '+', '.join(missing)}],'sample':[]}
        parsed=[];parse_errors=[];stock_rows={};duplicates=0
        for number,row in table:
            try:
                cells = dict(zip(headers,row))
                values={field:cells.get(selected[field],'') if selected.get(field) else 'DISP' for field in FIELDS}
                values={key:str(value).strip() for key,value in values.items()}
                if source_layout:
                    source = {field:source_text(cells.get(header,'')) for field,header in source_columns.items()}
                    if source['Unidad de medida'].upper() != 'KG':
                        raise ValueError('Unidad de medida debe ser KG')
                    if any(value.startswith('=') for value in source.values()):
                        raise ValueError('No se admiten fórmulas')
                if any(value.startswith('=') for value in values.values()):raise ValueError('No se admiten fórmulas')
                for field in ['codigo_rollo','numero_parte','ubicacion']:
                    limit = 40 if field == 'ubicacion' else 80
                    if not values[field] or len(values[field])>limit:raise ValueError(f'{selected[field]}: usa de 1 a {limit} caracteres')
                weight=Decimal(stock_weight(values['kg']) if source_layout else values['kg'].replace(',','.'))
                if not weight.is_finite() or not 0<weight<=1000000:raise ValueError('kg debe ser mayor a cero y no superar 1000000')
                values['kg']=float(weight);values['estado']=values['estado'].upper() or 'DISP'
                if values['estado'] not in ['DISP','BLOQUEADO']:raise ValueError('Estado permitido: DISP o BLOQUEADO')
                if source_layout:
                    identity = stock_identity(source)
                    if identity in stock_rows:
                        previous, first_line = stock_rows[identity]
                        if previous != source:
                            raise ValueError(f'El lote {source["Lote/Serie"]} coincide con la fila {first_line} en artículo, planta, ubicación, referencia y orden de compra, pero tiene datos distintos')
                        duplicates += 1
                        continue
                    stock_rows[identity] = (source,number)
                    values.update(source_data=source,source_line=number)
                parsed.append(values)
            except (ValueError,InvalidOperation) as error:
                parse_errors.append({'row':number,'error':str(error) if isinstance(error,ValueError) else 'La cantidad de existencias debe ser numérica'})
        if parse_errors:return {'valid':False,'headers':headers,'mapping':selected,'source_layout':source_layout,'total':len(table),'errors':parse_errors[:200],'error_count':len(parse_errors),'sample':[]}
        actions,errors,counts=review(db,parsed,update_existing)
        result={'valid':not errors,'headers':headers,'mapping':selected,'source_layout':source_layout,'total':len(table),'duplicates':duplicates,'errors':errors[:200],'error_count':len(errors),'sample':parsed[:50],**counts,'source_sha256':hashlib.sha256(raw).hexdigest()}
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
    try:
        actions,errors,counts=review(db,payload['rows'],batch.update_existing,persist_catalogs=True)
    except IntegrityError:
        fail('El catálogo cambió durante la confirmación; vuelve a revisar el archivo')
    if errors:fail({'message':'El inventario cambió; vuelve a generar la vista previa','errors':errors[:200]})
    for action in actions:
        expected=payload['expected'].get(action['values']['code'])
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
