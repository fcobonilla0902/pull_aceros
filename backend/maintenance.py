"""Administración con revocación de sesiones y conservación del historial operativo."""
import json
from fastapi import APIRouter, Depends, Request as HTTPRequest
from sqlalchemy import select, update, delete, func
from sqlalchemy.exc import IntegrityError
from database import User, Role, SessionToken, Request, RequestItem, Roll, Part, Location, Press, Process, Forklift, Handover
from security import db_session, current_user, require, identity, hash_password, verify
from schemas import UserUpdate, PasswordChange, PasswordReset, CatalogUpdate
from api import fail, audit, get_or_404, serialize
from operations import CLOSED

router=APIRouter(prefix='/api')

@router.patch('/users/{id}')
def edit_user(id:int,data:UserUpdate,user=Depends(require('admin')),db=Depends(db_session,scope='function')):
    # Serializa los cambios de administradores, incluidas las reducciones de permisos mutuas y simultáneas.
    db.execute(update(Role).where(Role.name=='Administrador').values(name=Role.name))
    db.refresh(user)
    if not user.active or 'admin' not in [p.name for p in user.role.permissions]:fail('Tu acceso administrativo cambió',403)
    target=db.scalar(select(User).where(User.id==id).with_for_update())
    if not target:fail('Usuario inexistente',404)
    db.refresh(target)
    role=get_or_404(db,Role,data.role_id)
    before={'username':target.username,'role_id':target.role_id,'active':target.active}
    permissions=[p.name for p in role.permissions]
    if 'admin' in [p.name for p in target.role.permissions] and (not data.active or 'admin' not in permissions):
        admins=[u for u in db.scalars(select(User).where(User.active==True)) if u.id!=id and 'admin' in [p.name for p in u.role.permissions]]
        if not admins:fail('Debe permanecer al menos un administrador activo')
    if (not data.active or 'operate' not in permissions) and db.scalar(select(Request.id).where(Request.operator_id==id,Request.state.notin_(CLOSED))):fail('El usuario tiene movimientos abiertos; reasígnalos o ciérralos antes de cambiar su acceso')
    if (not data.active or 'handover' not in permissions) and db.scalar(select(Handover.id).where(Handover.receiving_user_id==id,Handover.accepted_at.is_(None))):fail('El usuario tiene entregas de turno pendientes de aceptar')
    try:
        changed=db.execute(update(User).where(User.id==id,User.version==data.version).values(username=data.username,role_id=data.role_id,active=data.active,version=User.version+1)).rowcount
        if changed!=1:fail('La cuenta cambió; actualiza e intenta nuevamente')
        db.flush()
    except IntegrityError:fail('El nombre de usuario ya existe')
    if before['role_id']!=data.role_id or before['active']!=data.active:
        db.execute(delete(SessionToken).where(SessionToken.user_id==id))
    audit(db,user,'Usuario modificado',json.dumps({'id':id,'antes':before,'despues':data.model_dump(exclude={'version'})},ensure_ascii=False))
    db.refresh(target);return identity(target)|{'active':target.active,'version':target.version,'role_id':target.role_id}

@router.post('/users/{id}/password')
def reset_password(id:int,data:PasswordReset,user=Depends(require('admin')),db=Depends(db_session,scope='function')):
    if id==user.id:fail('Cambia tu propia contraseña desde Mi cuenta, indicando la contraseña actual',422)
    target=get_or_404(db,User,id)
    target.password_hash=hash_password(data.new_password);target.version+=1
    db.execute(delete(SessionToken).where(SessionToken.user_id==id))
    audit(db,user,'Contraseña restablecida',f'Usuario #{id}: {target.username}; sesiones revocadas')
    return {'ok':True}

@router.post('/auth/password')
def change_password(data:PasswordChange,request:HTTPRequest,user=Depends(current_user),db=Depends(db_session,scope='function')):
    import hashlib
    if not verify(data.current_password,user.password_hash):fail('La contraseña actual no coincide',403)
    if verify(data.new_password,user.password_hash):fail('La nueva contraseña debe ser diferente',422)
    user.password_hash=hash_password(data.new_password);user.version+=1
    digest=hashlib.sha256(request.cookies.get('metaride_session','').encode()).hexdigest()
    db.execute(delete(SessionToken).where(SessionToken.user_id==user.id,SessionToken.digest!=digest))
    audit(db,user,'Contraseña cambiada','Sesiones de otros dispositivos revocadas')
    return {'ok':True}

@router.patch('/catalogs/{kind}/{id}')
def edit_catalog(kind:str,id:int,data:CatalogUpdate,user=Depends(require('admin')),db=Depends(db_session,scope='function')):
    models={'parts':Part,'locations':Location,'presses':Press,'processes':Process,'forklifts':Forklift}
    if kind not in models:fail('Catálogo inexistente',404)
    if kind!='parts' and len(data.name)>40:fail('El nombre admite hasta 40 caracteres',422)
    model=models[kind]
    row=db.scalar(select(model).where(model.id==id).with_for_update().execution_options(populate_existing=True))
    if not row:fail('Registro inexistente',404)
    before=serialize(row)
    if kind=='parts':
        if not data.specification:fail('Indica la especificación técnica',422)
        if data.specification!=row.specification and db.scalar(select(Roll.id).where(Roll.part_id==id)):fail('La parte ya identifica rollos físicos; crea otra parte para una especificación distinta')
    if not data.active:
        if kind=='parts':busy=db.scalar(select(RequestItem.id).join(Request).where(RequestItem.part_id==id,Request.state.notin_(CLOSED)))
        elif kind=='locations':busy=db.scalar(select(Roll.id).where(Roll.location_id==id,Roll.status=='RESERVADO'))
        else:
            field={'presses':Request.press_id,'processes':Request.process_id,'forklifts':Request.forklift_id}[kind]
            busy=db.scalar(select(Request.id).where(field==id,Request.state.notin_(CLOSED)))
        if busy:fail('El registro participa en movimientos abiertos; termina o cancela esos movimientos antes de desactivarlo')
    values={'name' if kind in ['presses','processes'] else 'code':data.name,'active':data.active,'version':model.version+1}
    if kind=='parts':values['specification']=data.specification
    if kind=='forklifts':values['available']=not bool(db.scalar(select(Request.id).where(Request.forklift_id==id,Request.state.notin_(CLOSED))))
    try:
        if db.execute(update(model).where(model.id==id,model.version==data.version).values(**values)).rowcount!=1:fail('El catálogo cambió; actualiza e intenta nuevamente')
        db.flush()
    except IntegrityError:fail('Ese nombre o código ya existe')
    db.refresh(row)
    audit(db,user,'Catálogo modificado',json.dumps({'catalogo':kind,'id':id,'antes':before,'despues':serialize(row)},default=str,ensure_ascii=False))
    return serialize(row)
