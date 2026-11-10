import json
from collections import Counter
from fastapi import APIRouter,Depends
from sqlalchemy import select,update
from database import Request,RequestItem,Roll,Press,Process,Incident,now
from security import db_session,require
from schemas import RequestRevision
from api import fail,get_or_404,audit,request_data
from operations import CLOSED
from reservations import reserve,validate_items,active_catalog

router=APIRouter(prefix='/api')

@router.patch('/requests/{id}')
def revise(id:int,data:RequestRevision,user=Depends(require('coordinate')),db=Depends(db_session,scope='function')):
    row=get_or_404(db,Request,id)
    if row.state in CLOSED:fail('No se modifica una solicitud cerrada')
    if db.execute(update(Request).where(Request.id==id,Request.version==data.version).values(version=Request.version+1)).rowcount!=1:fail('La solicitud cambió; actualiza e intenta nuevamente')
    db.refresh(row)
    before=request_data(db,row)
    for model,selected in [(Press,data.press_id),(Process,data.process_id)]:
        active_catalog(db,model,selected)
    if data.required_at!=row.required_at and data.required_at<now():fail('La nueva hora requerida debe estar en el futuro',422)
    validate_items(db,data.items)
    signature=lambda items:sorted((i.part_id,i.quantity,i.preferred_roll_id or 0) for i in items)
    material_changed=signature(row.items)!=signature(data.items)
    incident=db.scalar(select(Incident).where(Incident.request_id==id,Incident.resolved_at.is_(None)))
    if (material_changed or data.press_id!=row.press_id or data.process_id!=row.process_id or data.destination!=row.destination) and (row.state=='En traslado' or (incident and incident.previous_state=='En traslado')):
        fail('El material está en traslado; confirma la entrega o cancela el pendiente antes de cambiar material o destino')
    if material_changed:
        delivered=list(db.scalars(select(Roll).where(Roll.request_id==id,Roll.status=='ENTREGADO')))
        counts=Counter(roll.part_id for roll in delivered)
        desired={i.part_id:i for i in data.items}
        for part_id,quantity in counts.items():
            if part_id not in desired or desired[part_id].quantity<quantity:fail('No se pueden quitar partes ni cantidades ya entregadas',422)
            preferred=desired[part_id].preferred_roll_id
            if preferred and preferred not in [roll.id for roll in delivered if roll.part_id==part_id]:fail('El rollo indicado no corresponde a la entrega ya registrada',422)
        if delivered and sum(i.quantity for i in data.items)<=len(delivered):fail('La edición no cierra una entrega parcial; conserva al menos un rollo pendiente o cancela el remanente',422)
        reserved=row.state!='Solicitado'
        for roll in db.scalars(select(Roll).where(Roll.request_id==id,Roll.status=='RESERVADO').order_by(Roll.id)):
            roll.status='DISP';roll.request_id=None;roll.version+=1
        for item in list(row.items):db.delete(item)
        db.flush();db.expire(row,['items'])
        row.items=[RequestItem(**item.model_dump()) for item in data.items]
        db.flush()
        if reserved:
            reserve(db,row)
            new_state='Tomado' if row.operator_id else 'Validado'
            if incident:incident.previous_state=new_state
            else:row.state=new_state
    for field in ['press_id','process_id','priority','risk','destination','required_at','notes']:setattr(row,field,getattr(data,field))
    db.flush()
    after=request_data(db,row)
    audit(db,user,'Solicitud modificada',json.dumps({'motivo':data.justification,'antes':{k:before[k] for k in ['press_id','process_id','priority','risk','destination','required_at','items']},'despues':{k:after[k] for k in ['press_id','process_id','priority','risk','destination','required_at','items']},'preparacion_requerida':material_changed and row.operator_id is not None},default=str,ensure_ascii=False),id)
    db.flush();return request_data(db,row)
