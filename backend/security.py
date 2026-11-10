import hashlib
import hmac
import secrets
import os
from datetime import timedelta
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select,text
from sqlalchemy.exc import DBAPIError
from database import Session, SessionToken, User, Role, Permission, Process, Press, now

def hash_password(password):
    salt = secrets.token_hex(16)
    return salt + ':' + hashlib.scrypt(password.encode(), salt=salt.encode(), n=16384, r=8, p=1).hex()
def verify(password, stored):
    salt, expected = stored.split(':')
    return hmac.compare_digest(hashlib.scrypt(password.encode(), salt=salt.encode(), n=16384, r=8, p=1).hex(), expected)
def db_session():
    with Session() as db:
        try:
            yield db
            db.commit()
        except DBAPIError as error:
            db.rollback()
            state=getattr(error.orig,'sqlstate',None)
            if state in ['23505','40001','40P01','55P03']:
                raise HTTPException(409,'Otro movimiento cambió el material o recurso. Actualiza y vuelve a intentar.') from error
            raise
        except Exception:
            db.rollback()
            raise
def current_user(request: Request, db=Depends(db_session, scope='function')):
    token = request.cookies.get('metaride_session', '')
    session = db.scalar(select(SessionToken).where(SessionToken.digest == hashlib.sha256(token.encode()).hexdigest(), SessionToken.expires > now()))
    user = db.get(User, session.user_id) if session else None
    if not user or not user.active: raise HTTPException(401, 'Inicia sesión')
    return user
def require(permission):
    def check(user=Depends(current_user)):
        if permission not in [p.name for p in user.role.permissions]: raise HTTPException(403, 'Permiso insuficiente')
        return user
    return check
def identity(user):
    return dict(id=user.id, username=user.username, role=user.role.name, permissions=[p.name for p in user.role.permissions])
def bootstrap():
    password = os.getenv('METARIDE_ADMIN_PASSWORD')
    with Session.begin() as db:
        if db.bind.dialect.name=='postgresql':db.execute(text('SELECT pg_advisory_xact_lock(5567948267349312580)'))
        permissions = {}
        for name in ['request', 'operate', 'inventory', 'handover', 'admin', 'simulate', 'coordinate']:
            p = db.scalar(select(Permission).where(Permission.name == name))
            if not p:
                p = Permission(name=name); db.add(p); db.flush()
            permissions[name] = p
        for name, grants in {'Administrador': list(permissions), 'Producción': ['request'], 'Logística': ['request','operate','inventory','handover','simulate','coordinate'], 'Operador': ['operate','handover']}.items():
            role=db.scalar(select(Role).where(Role.name == name))
            if not role:
                role=Role(name=name);db.add(role)
            role.permissions=[permissions[g] for g in grants]
        db.flush()
        if not db.scalar(select(User.id)):
            if not password or len(password) < 12: raise RuntimeError('Define METARIDE_ADMIN_PASSWORD con al menos 12 caracteres para crear admin.')
            db.add(User(username='admin', password_hash=hash_password(password), role_id=db.scalar(select(Role.id).where(Role.name == 'Administrador'))))
        for model, names in [(Press, ['ENN1','ENN2','ENN3','ENN4','ENN5','ENN6']), (Process, ['Blancos','Formados'])]:
            for name in names:
                if not db.scalar(select(model).where(model.name == name)): db.add(model(name=name))
