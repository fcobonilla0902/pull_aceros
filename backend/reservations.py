"""Transactional material selection shared by validation and request revision."""
from sqlalchemy import select,update
from database import Roll,Part,Location
from api import fail

def active_catalog(db,model,id):
    row=db.scalar(select(model).where(model.id==id).with_for_update(read=True).execution_options(populate_existing=True))
    if not row or not row.active:fail('El catálogo está inactivo o no existe',422)
    return row

def reserve(db,request):
    for item in sorted(request.items,key=lambda item:item.part_id):
        part=active_catalog(db,Part,item.part_id)
        delivered=list(db.scalars(select(Roll).where(Roll.request_id==request.id,Roll.part_id==item.part_id,Roll.status=='ENTREGADO')))
        remaining=item.quantity-len(delivered)
        if remaining<0:fail('La cantidad no puede ser menor a lo ya entregado',422)
        if not remaining:continue
        query=select(Roll).join(Location).where(Roll.part_id==item.part_id,Roll.status=='DISP',Roll.kg>500,Roll.request_id.is_(None),Location.active==True)
        if item.preferred_roll_id:query=query.where(Roll.id==item.preferred_roll_id)
        query=query.order_by(Roll.id).limit(remaining)
        if db.bind.dialect.name=='postgresql':query=query.with_for_update(skip_locked=True,of=Roll)
        candidates=list(db.scalars(query))
        if len(candidates)!=remaining:fail('Inventario insuficiente o rollo no disponible para '+part.code)
        for roll in candidates:
            active_catalog(db,Location,roll.location_id)
            if db.execute(update(Roll).where(Roll.id==roll.id,Roll.status=='DISP',Roll.request_id.is_(None),Roll.version==roll.version).values(status='RESERVADO',request_id=request.id,version=Roll.version+1)).rowcount!=1:fail('Otro movimiento modificó el rollo; actualiza e intenta nuevamente')

def validate_items(db,items):
    ids=[item.part_id for item in items]
    if len(ids)!=len(set(ids)):fail('Combina las cantidades de cada número de parte',422)
    for item in sorted(items,key=lambda item:item.part_id):
        active_catalog(db,Part,item.part_id)
        if item.preferred_roll_id:
            roll=db.get(Roll,item.preferred_roll_id)
            if not roll or roll.part_id!=item.part_id or item.quantity!=1:fail('El rollo específico debe corresponder a la parte y cantidad 1',422)
