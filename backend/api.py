import csv
import io
import json
import hashlib
import secrets
import os
import re
from datetime import timedelta, date
from fastapi import APIRouter, Depends, HTTPException, Response, Request as HTTPRequest
from fastapi.responses import StreamingResponse
from sqlalchemy import select, update, func, or_
from sqlalchemy.exc import IntegrityError
from database import *
from security import db_session, current_user, require, identity, hash_password, verify
from schemas import Login, UserInput, RequestInput, ActionInput, RollInput, CatalogInput, HandoverInput, HandoverAcceptance
from operations import shift_at, utc_period, PLANT_TIMEZONE, CLOSED, SOON_MINUTES
router = APIRouter(prefix='/api')
def fail(detail, code=409): raise HTTPException(code, detail)
def audit(db, user, action, detail='', request_id=None):
    db.add(Audit(user_id=user.id, action=action, detail=detail, request_id=request_id))
def get_or_404(db, model, id):
    obj = db.get(model, id)
    if not obj: fail('Registro inexistente', 404)
    return obj
def serialize(row):
    return {c.name: getattr(row,c.name) for c in row.__table__.columns if c.name != 'password_hash'}

def delivery_detail(notes, receiver, codes):
    return ' | '.join(filter(None, [notes.strip(), 'Recibe: '+receiver,
        'Cantidad: '+str(len(codes)), 'Rollos: '+', '.join(codes)]))

def audit_detail(db, event):
    # Presenta las entregas antiguas con códigos sin modificar la bitácora guardada.
    if event.action != 'deliver': return event.detail
    match = re.fullmatch(r'(.*?) \| Recibe: (.*?) \| Rollos: (\d+(?:,\d+)*)', event.detail, re.DOTALL)
    if not match: return event.detail
    ids = [int(value) for value in match[3].split(',')]
    codes = dict(db.execute(select(Roll.id, Roll.code).where(Roll.id.in_(ids), Roll.request_id==event.request_id)).all())
    return delivery_detail(match[1], match[2], [codes.get(id, f'ID {id} (código no disponible)') for id in ids])
@router.post('/auth/login')
def login(data: Login, response: Response, request: HTTPRequest, db=Depends(db_session, scope='function')):
    # Los intentos fallidos se guardan; limita tanto la cuenta como el origen dentro de una ventana móvil.
    source = request.client.host if request.client else 'unknown'
    failures = db.scalar(select(func.count(Audit.id)).where(Audit.action == 'login_failed', Audit.created_at > now()-timedelta(minutes=15), or_(Audit.detail == source, Audit.detail == data.username)))
    if failures and failures >= 10: fail('Demasiados intentos. Espera 15 minutos.',429)
    user = db.scalar(select(User).where(User.username == data.username))
    valid = verify(data.password, user.password_hash) if user else verify(data.password, '0'*32 + ':' + '0'*128)
    if not user or not user.active or not valid:
        # Los fallos de autenticación deben conservarse al revertir la transacción por una excepción.
        admin = db.scalar(select(User.id))
        db.add(Audit(user_id=admin, action='login_failed', detail=source)); db.add(Audit(user_id=admin, action='login_failed', detail=data.username)); db.commit()
        fail('Credenciales incorrectas',401)
    token = secrets.token_urlsafe(48)
    db.add(SessionToken(digest=hashlib.sha256(token.encode()).hexdigest(), user_id=user.id, expires=now()+timedelta(hours=8)))
    response.set_cookie('metaride_session', token, httponly=True, samesite='strict', secure=os.getenv('COOKIE_SECURE','false').lower() == 'true', max_age=28800, path='/')
    audit(db,user,'login')
    return identity(user)
@router.get('/auth/me')
def me(user=Depends(current_user)): return identity(user)
@router.post('/auth/logout')
def logout(request: HTTPRequest, response: Response, db=Depends(db_session, scope='function')):
    digest = hashlib.sha256(request.cookies.get('metaride_session','').encode()).hexdigest()
    session = db.scalar(select(SessionToken).where(SessionToken.digest == digest))
    if session: db.delete(session)
    response.delete_cookie('metaride_session',path='/')
    return {'ok':True}
@router.get('/catalogs')
def catalogs(user=Depends(current_user), db=Depends(db_session, scope='function')):
    return {name:[serialize(r) for r in db.scalars(select(model))] for name,model in [('presses',Press),('processes',Process),('parts',Part),('locations',Location),('forklifts',Forklift),('roles',Role)]} | {'operators':[{'id':u.id,'username':u.username} for u in db.scalars(select(User).where(User.active == True)) if 'operate' in [p.name for p in u.role.permissions]], 'handover_users':[{'id':u.id,'username':u.username} for u in db.scalars(select(User).where(User.active == True)) if 'handover' in [p.name for p in u.role.permissions]]}
@router.post('/catalogs/{kind}',status_code=201)
def add_catalog(kind:str, data:CatalogInput, user=Depends(require('admin')),db=Depends(db_session, scope='function')):
    models={'presses':Press,'processes':Process,'parts':Part,'locations':Location,'forklifts':Forklift}
    if kind not in models: fail('Catálogo desconocido',404)
    model=models[kind]
    if kind!='parts' and len(data.name)>40:fail('El nombre admite hasta 40 caracteres',422)
    values={'code':data.name} if kind in ['parts','locations','forklifts'] else {'name':data.name}
    if kind=='parts':
        if not data.specification: fail('Indica la especificacion tecnica',422)
        values['specification']=data.specification
    if kind=='forklifts':values.update(available=True,active=data.available)
    row=model(**values); db.add(row)
    try: db.flush()
    except IntegrityError: fail('El registro ya existe')
    audit(db,user,'catalog_created',kind+': '+data.name)
    return serialize(row)
@router.get('/users')
def users(user=Depends(require('admin')),db=Depends(db_session, scope='function')):
    return [identity(u)|{'active':u.active,'version':u.version,'role_id':u.role_id} for u in db.scalars(select(User))]
@router.post('/users',status_code=201)
def add_user(data:UserInput,user=Depends(require('admin')),db=Depends(db_session, scope='function')):
    get_or_404(db,Role,data.role_id)
    row=User(username=data.username,password_hash=hash_password(data.password),role_id=data.role_id); db.add(row)
    try: db.flush()
    except IntegrityError: fail('Usuario duplicado')
    audit(db,user,'user_created',data.username)
    return identity(row)
@router.get('/inventory')
def inventory(user=Depends(current_user),db=Depends(db_session, scope='function')):
    parts={p.id:p for p in db.scalars(select(Part))}
    locations={l.id:l for l in db.scalars(select(Location))}
    return [serialize(r)|{'part':parts[r.part_id].code,'location':locations[r.location_id].code,'eligible':r.status=='DISP' and r.kg>500 and parts[r.part_id].active and locations[r.location_id].active} for r in db.scalars(select(Roll).order_by(Roll.id.desc()))]
@router.post('/inventory',status_code=201)
def add_roll(data:RollInput,user=Depends(require('inventory')),db=Depends(db_session, scope='function')):
    part=get_or_404(db,Part,data.part_id);location=get_or_404(db,Location,data.location_id)
    if not part.active or not location.active:fail('Selecciona parte y ubicación activas',422)
    r=Roll(**data.model_dump()); db.add(r)
    try: db.flush()
    except IntegrityError: fail('Código de rollo duplicado')
    audit(db,user,'roll_created',r.code)
    return serialize(r)
def request_data(db,r):
    items=[]
    for i in r.items:
        delivered=db.scalar(select(func.count(Roll.id)).where(Roll.request_id==r.id,Roll.part_id==i.part_id,Roll.status=='ENTREGADO'))
        stock=db.scalar(select(func.count(Roll.id)).join(Location).join(Part).where(Roll.part_id==i.part_id,Roll.status=='DISP',Roll.kg>500,Location.active==True,Part.active==True))
        items.append({'part':db.get(Part,i.part_id).code,'part_id':i.part_id,'preferred_roll_id':i.preferred_roll_id,'requested':i.quantity,'delivered':delivered,'stock':stock})
    events=list(db.scalars(select(Audit).where(Audit.request_id==r.id).order_by(Audit.id)))
    return serialize(r)|{'folio':f'REQ-{r.id:06d}','enn':db.get(Press,r.press_id).name,'process':db.get(Process,r.process_id).name,'owner':db.get(User,r.operator_id).username if r.operator_id else 'Sin asignar','requester':db.get(User,r.requester_id).username,'items':items,'rolls':[serialize(x)|{'location':db.get(Location,x.location_id).code} for x in db.scalars(select(Roll).where(Roll.request_id==r.id))],'incidents':[serialize(x) for x in db.scalars(select(Incident).where(Incident.request_id==r.id))], 'updated_at':events[-1].created_at if events else r.created_at, 'events':[serialize(e)|{'username':db.get(User,e.user_id).username, 'detail':audit_detail(db,e)} for e in events], 'remaining_minutes':round((r.required_at-now()).total_seconds()/60,1), 'shift':shift_at(r.created_at)['shift']}
@router.get('/requests')
def requests(user=Depends(current_user),db=Depends(db_session, scope='function')):
    return [request_data(db,r) for r in db.scalars(select(Request).order_by(Request.id.desc()))]
@router.post('/requests',status_code=201)
def create_request(data:RequestInput,user=Depends(require('request')),db=Depends(db_session, scope='function')):
    existing=db.scalar(select(Request).where(Request.key==data.key))
    if existing:
        if existing.requester_id!=user.id: fail('Clave ya utilizada')
        return request_data(db,existing)
    from reservations import validate_items,active_catalog
    active_catalog(db,Press,data.press_id);active_catalog(db,Process,data.process_id)
    validate_items(db,data.items)
    if data.required_at<now(): fail('La hora requerida debe estar en el futuro',422)
    # Un requerimiento abierto coincidente probablemente sea un duplicado accidental.
    for old in db.scalars(select(Request).where(Request.press_id==data.press_id,Request.process_id==data.process_id,Request.required_at==data.required_at,Request.state.notin_(['Entregado','Cancelado']))):
        if sorted((i.part_id,i.quantity) for i in old.items)==sorted((i.part_id,i.quantity) for i in data.items): fail('Ya existe una solicitud activa idéntica')
    r=Request(**data.model_dump(exclude={'items'}),requester_id=user.id,items=[RequestItem(**i.model_dump()) for i in data.items]); db.add(r)
    try: db.flush()
    except IntegrityError: fail('Solicitud duplicada')
    audit(db,user,'Solicitud creada',data.notes,r.id)
    return request_data(db,r)
@router.post('/requests/{id}/actions')
def action(id:int,data:ActionInput,user=Depends(require('operate')),db=Depends(db_session, scope='function')):
    r=get_or_404(db,Request,id)
    coordinator='coordinate' in [p.name for p in user.role.permissions]
    if data.action in ['validate','assign','edit','cancel'] and not coordinator: fail('Esta acción requiere coordinación de Logística',403)
    if data.action in ['prepare','ready','transport','deliver','resolve'] and not coordinator and r.operator_id!=user.id: fail('Solo el operador asignado puede registrar este avance',403)
    if db.execute(update(Request).where(Request.id==id,Request.version==data.version).values(version=Request.version+1)).rowcount!=1: fail('La solicitud cambió; actualiza y vuelve a intentar')
    db.refresh(r)
    a=data.action
    if r.state in ['Entregado','Cancelado']: fail('Solicitud cerrada')
    if a=='validate':
        if r.state!='Solicitado': fail('Solo se validan solicitudes nuevas')
        from reservations import reserve
        reserve(db,r)
        r.state='Validado'
    elif a=='assign':
        if r.state!='Validado': fail('Primero valida existencia y especificación')
        if data.operator_id is None: fail("Selecciona un operador",422)
        # Bloquea la fila del operador antes de comprobar las asignaciones activas en PostgreSQL.
        operator=db.scalar(select(User).where(User.id==data.operator_id).with_for_update())
        if not operator:fail('Operador inexistente',404)
        db.refresh(operator)
        if not operator.active or 'operate' not in [p.name for p in operator.role.permissions]: fail('Operador inválido',422)
        if db.scalar(select(Request.id).where(Request.operator_id==operator.id,Request.state.notin_(['Entregado','Cancelado']),Request.id!=id)): fail('Operador ocupado')
        if data.forklift_id:
            forklift=get_or_404(db,Forklift,data.forklift_id)
            if db.execute(update(Forklift).where(Forklift.id==forklift.id,Forklift.available==True,Forklift.active==True).values(available=False,version=Forklift.version+1)).rowcount!=1: fail('Montacargas no disponible')
            r.forklift_id=forklift.id
        r.operator_id=operator.id; r.state='Tomado'
    elif a in ['prepare','ready','transport','deliver']:
        expected={'prepare':'Tomado','ready':'En preparación','transport':'Listo para traslado','deliver':'En traslado'}
        target={'prepare':'En preparación','ready':'Listo para traslado','transport':'En traslado','deliver':'Entregado'}
        if r.state!=expected[a] and not (a=='deliver' and r.state=='Entrega parcial'): fail('Transición inválida desde '+r.state)
        if a=='deliver':
            if not data.receiver: fail('Indica el responsable que recibe',422)
            reserved=list(db.scalars(select(Roll).where(Roll.request_id==id,Roll.status=='RESERVADO')))
            selected=set(data.roll_ids) if data.roll_ids else {roll.id for roll in reserved}
            if not selected or not selected.issubset({roll.id for roll in reserved}): fail('Selecciona rollos reservados de esta solicitud',422)
            for roll in reserved:
                if roll.id in selected: roll.status='ENTREGADO';roll.version+=1
            r.receiver=data.receiver
            if len(selected)==len(reserved):
                r.delivered_at=now()
                if r.forklift_id:
                    lift=db.get(Forklift,r.forklift_id);lift.available=True;lift.version+=1
            else: target[a]='Entrega parcial'
            codes = [roll.code for roll in sorted(reserved, key=lambda roll: roll.id) if roll.id in selected]
            data.notes = delivery_detail(data.notes, data.receiver, codes)
        r.state=target[a]
    elif a=='incident':
        if r.state=='Con incidencia': fail('Resuelve primero la incidencia abierta')
        if len(data.notes)<3: fail('Describe la incidencia',422)
        db.add(Incident(request_id=id,description=data.notes,previous_state=r.state,cause=data.cause,production_stopped=data.production_stopped)); r.state='Con incidencia'
    elif a=='resolve':
        incident=db.scalar(select(Incident).where(Incident.request_id==id,Incident.resolved_at.is_(None)))
        if not incident or len(data.notes)<3: fail('Indica la resolución de la incidencia abierta',422)
        incident.resolved_at=now(); incident.resolution=data.notes; r.state=incident.previous_state
    elif a=='edit':
        if len(data.notes)<3 or not data.priority: fail('Indica prioridad y justificación',422)
        r.priority=data.priority; r.notes=data.notes
    elif a=='cancel':
        if len(data.notes)<3: fail('Justifica la cancelación',422)
        for roll in db.scalars(select(Roll).where(Roll.request_id==id,Roll.status=='RESERVADO')):
            roll.request_id=None; roll.status='DISP';roll.version+=1
        if r.forklift_id:
            lift=db.get(Forklift,r.forklift_id);lift.available=True;lift.version+=1
        for incident in db.scalars(select(Incident).where(Incident.request_id==id,Incident.resolved_at.is_(None))):
            incident.resolved_at=now(); incident.resolution='Cancelada: '+data.notes
        r.state='Cancelado'
    audit(db,user,a,data.notes or r.state,id); db.flush()
    return request_data(db,r)
@router.get('/history')
def history(user=Depends(current_user),db=Depends(db_session, scope='function')):
    return [serialize(a)|{'username':db.get(User,a.user_id).username, 'detail':audit_detail(db,a)} for a in db.scalars(select(Audit).order_by(Audit.id.desc()).limit(2000))]
@router.get('/history/export')
def export(user=Depends(current_user),db=Depends(db_session, scope='function')):
    buffer=io.StringIO(); writer=csv.writer(buffer); writer.writerow(['fecha_utc','usuario','solicitud','accion','detalle'])
    def safe(value):
        s=str(value or '')
        return "'"+s if s.lstrip().startswith(('=','+','-','@')) else s
    for a in db.scalars(select(Audit).order_by(Audit.id)):
        writer.writerow([safe(a.created_at),safe(db.get(User,a.user_id).username),a.request_id,safe(a.action),safe(audit_detail(db,a))])
    return StreamingResponse(iter(['\ufeff'+buffer.getvalue()]),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename=historial.csv'})
def handover_data(db, row):
    return serialize(row)|{'sender':db.get(User,row.user_id).username,'recipient':db.get(User,row.receiving_user_id).username if row.receiving_user_id else None,'accepted_by':db.get(User,row.accepted_by_id).username if row.accepted_by_id else None,'items':[{'request_id':i.request_id,'snapshot':json.loads(i.snapshot)} for i in db.scalars(select(HandoverItem).where(HandoverItem.handover_id==row.id))]}

@router.get('/handovers')
def handovers(user=Depends(current_user),db=Depends(db_session, scope='function')):
    return [handover_data(db,r) for r in db.scalars(select(Handover).order_by(Handover.id.desc()).limit(100))]
@router.post('/handovers',status_code=201)
def handover(data:HandoverInput,user=Depends(require('handover')),db=Depends(db_session, scope='function')):
    if data.receiving_user_id:
        recipient=get_or_404(db,User,data.receiving_user_id)
        if recipient.id==user.id or not recipient.active or 'handover' not in [p.name for p in recipient.role.permissions]: fail('Selecciona otro usuario autorizado para recibir el turno',422)
    pending=list(db.scalars(select(Request.id).where(Request.state.notin_(['Entregado','Cancelado']))))
    row=Handover(**data.model_dump(),user_id=user.id,pending=json.dumps(pending)); db.add(row)
    db.flush()
    for request_id in pending:
        snapshot=request_data(db,db.get(Request,request_id))
        db.add(HandoverItem(handover_id=row.id,request_id=request_id,snapshot=json.dumps(snapshot,default=lambda d:d.isoformat())))
    audit(db,user,'Cambio de turno',f'Entrega #{row.id} a {data.incoming_shift}: '+data.notes); db.flush()
    return handover_data(db,row)

@router.post('/handovers/{id}/accept')
def accept_handover(id:int,data:HandoverAcceptance,user=Depends(require('handover')),db=Depends(db_session, scope='function')):
    row=get_or_404(db,Handover,id)
    if row.user_id==user.id: fail('La recepción debe confirmarla una persona del turno entrante',403)
    if row.receiving_user_id and row.receiving_user_id!=user.id: fail('Entrega dirigida a otro responsable',403)
    accepted=now()
    if db.execute(update(Handover).where(Handover.id==id,Handover.accepted_at.is_(None)).values(accepted_at=accepted,accepted_by_id=user.id,acceptance_notes=data.notes)).rowcount!=1: fail('Esta entrega ya fue aceptada')
    audit(db,user,'Recepción de turno',f'Entrega #{id} a {row.incoming_shift}: '+data.notes)
    db.refresh(row)
    return handover_data(db,row)
@router.get('/metrics')
def metrics(start:date|None=None,end:date|None=None,user=Depends(current_user),db=Depends(db_session, scope='function')):
    if start and end and start>end: fail('El inicio debe ser anterior al fin',422)
    lower,upper=utc_period(start,end)
    def in_period(timestamp): return (lower is None or timestamp>=lower) and (upper is None or timestamp<upper)
    rows=[r for r in db.scalars(select(Request)) if in_period(r.created_at)]
    active=[r for r in rows if r.state not in ['Entregado','Cancelado']]
    done=[r for r in rows if r.delivered_at]
    current=now()
    all_incidents=list(db.scalars(select(Incident)))
    incidents=[i for i in all_incidents if in_period(i.created_at)]
    causes={}
    for incident in incidents: causes[incident.cause]=causes.get(incident.cause,0)+1
    movement_events=[e for e in db.scalars(select(Audit).where(Audit.action=='deliver')) if in_period(e.created_at)]
    shift_counts={}
    for e in movement_events:
        period=shift_at(e.created_at); key=(period['date'],period['shift'])
        entry=shift_counts.setdefault(key,{'date':key[0],'shift':key[1],'movements':0,'requests':set()})
        entry['movements']+=1;entry['requests'].add(e.request_id)
    stops=[i for i in incidents if i.production_stopped]
    return {'active':len(active),'overdue':sum(r.required_at<current for r in active),'incidents':sum(i.resolved_at is None for i in incidents),'delivered':len(done),'on_time_percent':round(100*sum(r.delivered_at<=r.required_at for r in done)/len(done),1) if done else None,'average_minutes':round(sum((r.delivered_at-r.created_at).total_seconds()/60 for r in done)/len(done),2) if done else None,'pending_rolls':sum(i.quantity for r in active for i in r.items)-db.scalar(select(func.count(Roll.id)).where(Roll.request_id.in_([r.id for r in active]),Roll.status=='ENTREGADO')),
        'urgent':sum(r.priority=='Urgente' for r in active),'due_soon':sum(0<=(r.required_at-current).total_seconds()<=SOON_MINUTES*60 for r in active),'soon_threshold_minutes':SOON_MINUTES,
        'production_stops':len(stops),'open_stops':sum(i.resolved_at is None for i in stops),'downtime_minutes':round(sum(((i.resolved_at or current)-i.created_at).total_seconds()/60 for i in stops),2),
        'delay_causes':[{'cause':k,'count':v} for k,v in sorted(causes.items(),key=lambda x:(-x[1],x[0]))],
        'movements_by_shift':[{**v,'requests':len(v['requests'])} for _,v in sorted(shift_counts.items(),reverse=True)],
        'current_shift':shift_at(current),'timezone':PLANT_TIMEZONE,
        'awaiting_handover_acceptance':db.scalar(select(func.count(Handover.id)).where(Handover.accepted_at.is_(None))),
        'period':{'start':start,'end':end},'cohort_note':'Solicitudes por fecha de creación; movimientos e incidencias por fecha del evento. Tiempo de paro suma incidencias reportadas y puede solaparse.'}

@router.get('/metrics/export')
def export_metrics(start:date|None=None,end:date|None=None,user=Depends(current_user),db=Depends(db_session, scope='function')):
    data=metrics(start,end,user,db)
    buffer=io.StringIO();writer=csv.writer(buffer);writer.writerow(['indicador','valor','unidad'])
    for key,unit in [('active','solicitudes'),('overdue','solicitudes'),('urgent','solicitudes'),('due_soon','solicitudes'),('on_time_percent','porcentaje'),('average_minutes','minutos'),('production_stops','incidencias'),('downtime_minutes','minutos de incidencias')]: writer.writerow([key,data[key],unit])
    writer.writerow([]);writer.writerow(['fecha_operativa','turno','movimientos','solicitudes_distintas'])
    for row in data['movements_by_shift']: writer.writerow([row['date'],row['shift'],row['movements'],row['requests']])
    writer.writerow([]);writer.writerow(['causa_retraso','incidencias'])
    for row in data['delay_causes']: writer.writerow([row['cause'],row['count']])
    return StreamingResponse(iter(['\ufeff'+buffer.getvalue()]),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename=indicadores.csv'})

@router.get('/simulations')
def simulation_history(user=Depends(require('simulate')),db=Depends(db_session, scope='function')):
    return [{'id':r.id,'created_at':r.created_at,'parameters':json.loads(r.parameters),'summary':json.loads(r.result)['resumen']} for r in db.scalars(select(SimulationRun).order_by(SimulationRun.id.desc()).limit(50))]
@router.get('/simulations/calibration')
def calibration(user=Depends(require('simulate')),db=Depends(db_session, scope='function')):
    samples={'preparacion':[],'traslado':[]}
    for r in db.scalars(select(Request).where(Request.state=='Entregado')):
        events=list(db.scalars(select(Audit).where(Audit.request_id==r.id).order_by(Audit.id)))
        # Los incidentes invalidan las estimaciones del tiempo de servicio hasta que se modelen explícitamente las pausas.
        if any(a.action=='incident' for a in events): continue
        timestamps={a.action:a.created_at for a in events}
        for name,start,end in [('preparacion','prepare','ready'),('traslado','transport','deliver')]:
            if start in timestamps and end in timestamps:
                minutes=(timestamps[end]-timestamps[start]).total_seconds()/60
                if 0 < minutes <= 120: samples[name].append(minutes)
    parameters={}
    for name,values in samples.items():
        if len(values)>=5: parameters[name+'_min']=round(min(values),4);parameters[name+'_max']=round(max(values),4)
    return {'parameters':parameters,'samples':{k:len(v) for k,v in samples.items()},'minimum_samples':5,'note':'Rangos observados en solicitudes entregadas sin incidencias; validar representatividad antes de planificar.'}
