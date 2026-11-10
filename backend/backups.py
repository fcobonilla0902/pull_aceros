"""Consistent SQLite/PostgreSQL backups and guarded offline restoration."""
from contextlib import contextmanager,closing
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import sqlite3
import subprocess
import threading
from fastapi import APIRouter,Depends
from fastapi.responses import FileResponse
from sqlalchemy import create_engine,text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool
from sqlalchemy.exc import DBAPIError
from alembic.config import Config
from alembic.script import ScriptDirectory
from database import engine
from settings import ROOT,POSTGRES_BIN
from security import require,db_session
from api import audit,fail

router=APIRouter(prefix='/api/backups')
_server_mutex=threading.Lock()
_server_users=0
_server_context=None
LOCK_KEY=int.from_bytes(b'METARIDE','big')

def database_path():
    if engine.dialect.name!='sqlite' or not engine.url.database or engine.url.database==':memory:':raise ValueError('Esta función corresponde a una base SQLite en archivo')
    return Path(engine.url.database).resolve()

def backup_dir():
    default=database_path().parent/'backups' if engine.dialect.name=='sqlite' else ROOT/'backups'
    directory=Path(os.getenv('BACKUP_DIR',str(default))).resolve()
    directory.mkdir(parents=True,exist_ok=True);return directory

@contextmanager
def database_guard(database_url=None,shared=False):
    """API lifetimes share a PostgreSQL advisory lock; restoration requires exclusivity."""
    url=make_url(database_url) if database_url else engine.url
    if url.get_backend_name()=='postgresql':
        own_engine=create_engine(url,poolclass=NullPool) if database_url else None
        resource=own_engine or engine
        function='pg_try_advisory_lock_shared' if shared else 'pg_try_advisory_lock'
        unlock='pg_advisory_unlock_shared' if shared else 'pg_advisory_unlock'
        try:
            with resource.connect().execution_options(isolation_level='AUTOCOMMIT') as connection:
                locked=connection.scalar(text(f'SELECT {function}(:key)'),{'key':LOCK_KEY})
                if not locked:raise RuntimeError('La base está en uso. Detén el backend antes de restaurar.')
                try:yield
                finally:
                    try:connection.execute(text(f'SELECT {unlock}(:key)'),{'key':LOCK_KEY})
                    except DBAPIError as error:
                        # Stopping PostgreSQL closes this session and releases its advisory locks.
                        if not error.connection_invalidated and getattr(error.orig,'sqlstate',None) not in ['57P01','08006']:raise
        finally:
            if own_engine:own_engine.dispose()
        return
    if url.get_backend_name()!='sqlite':raise ValueError('Motor de base de datos no admitido')
    path=Path(url.database).resolve().with_suffix('.maintenance.lock')
    handle=path.open('a+b')
    if path.stat().st_size==0:handle.write(b'0');handle.flush()
    handle.seek(0)
    try:
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError as error:raise RuntimeError('La base está en uso. Detén el backend antes de restaurar o iniciar otra instancia.') from error
        yield
    finally:handle.close()

@contextmanager
def server_guard():
    global _server_users,_server_context
    with _server_mutex:
        if _server_users==0:
            context=database_guard(shared=True);context.__enter__();_server_context=context
        _server_users+=1
    try:yield
    finally:
        with _server_mutex:
            _server_users-=1
            if _server_users==0:_server_context.__exit__(None,None,None);_server_context=None

def pg_tool(name):
    candidate=POSTGRES_BIN/(name+('.exe' if os.name=='nt' else ''))
    found=str(candidate) if candidate.is_file() else shutil.which(name)
    if not found:raise ValueError(f'Configura PG_BIN para localizar {name}')
    return found

def pg_command(name,args,url=None):
    url=make_url(url) if isinstance(url,str) else (url or engine.url)
    environment=os.environ.copy()
    environment.update(PGPASSWORD=url.password or '',PGCONNECT_TIMEOUT='10',PGAPPNAME='Meta-Ride maintenance')
    command=[pg_tool(name),'--host',url.host or '127.0.0.1','--port',str(url.port or 5432),'--username',url.username or '', '--no-password',*map(str,args)]
    result=subprocess.run(command,env=environment,capture_output=True,text=True,encoding='utf-8',errors='replace',creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    if result.returncode:raise ValueError(f'{name} no pudo completar la operación: '+result.stderr.strip()[-1500:])
    return result.stdout

def create_snapshot(prefix='metaride'):
    postgres=engine.dialect.name=='postgresql'
    suffix='.dump' if postgres else '.db'
    name=f'{prefix}-{datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")}-{secrets.token_hex(4)}{suffix}'
    target=backup_dir()/name;temporary=target.with_suffix(suffix+'.partial')
    try:
        if postgres:
            pg_command('pg_dump',['--format=custom','--no-owner','--no-privileges','--file',temporary,engine.url.database])
        else:
            source=database_path()
            if not source.exists():raise ValueError('No existe la base de datos')
            with closing(sqlite3.connect(source)) as origin,closing(sqlite3.connect(temporary)) as destination,destination:
                origin.backup(destination)
                if destination.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('El respaldo no superó la comprobación de integridad')
        temporary.replace(target)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return target

def saved_snapshot(name):
    if not re.fullmatch(r'[A-Za-z0-9_-]+\.(db|dump)',name):raise ValueError('Nombre de respaldo inválido')
    root=backup_dir();candidate=(root/name).resolve()
    if candidate.parent!=root or not candidate.is_file():raise ValueError('Respaldo no encontrado')
    return candidate

def current_revision():
    return ScriptDirectory.from_config(Config(str(ROOT/'alembic.ini'))).get_current_head()

def validate_snapshot(path):
    if path.suffix=='.dump':
        pg_command('pg_restore',['--list',path]);return
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as connection:
        if connection.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Respaldo SQLite dañado')
        if connection.execute('PRAGMA foreign_key_check').fetchone():raise ValueError('El respaldo tiene referencias inconsistentes')
        version=connection.execute('SELECT version_num FROM alembic_version').fetchone()
        if not version or version[0]!=current_revision():raise ValueError('El respaldo debe corresponder a la versión actual del esquema')
        admin=connection.execute("SELECT u.id FROM users u JOIN role_permissions rp ON rp.role_id=u.role_id JOIN permissions p ON p.id=rp.permission_id WHERE u.active=1 AND p.name='admin' LIMIT 1").fetchone()
        if not admin:raise ValueError('El respaldo no contiene un administrador activo')

@contextmanager
def staging_database(prefix='metaride_restore_'):
    from local_postgres import maintenance_url
    import psycopg
    from psycopg import sql
    administrator=maintenance_url()
    name=prefix+secrets.token_hex(8)
    with psycopg.connect(host=administrator.host,port=administrator.port,dbname=administrator.database,user=administrator.username,password=administrator.password,connect_timeout=10,autocommit=True) as connection:
        connection.execute(sql.SQL('CREATE DATABASE {} OWNER {} TEMPLATE template0 ENCODING {}').format(sql.Identifier(name),sql.Identifier(engine.url.username),sql.Literal('UTF8')))
        try:yield engine.url.set(database=name)
        finally:connection.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))

def validate_postgres_contents(url):
    resource=create_engine(url,poolclass=NullPool)
    try:
        with resource.connect() as connection:
            version=connection.scalar(text('SELECT version_num FROM alembic_version'))
            if version!=current_revision():raise ValueError('El respaldo debe corresponder a la versión actual del esquema')
            admin=connection.scalar(text("SELECT u.id FROM users u JOIN role_permissions rp ON rp.role_id=u.role_id JOIN permissions p ON p.id=rp.permission_id WHERE u.active=TRUE AND p.name='admin' LIMIT 1"))
            if admin is None:raise ValueError('El respaldo no contiene un administrador activo')
    finally:resource.dispose()

def restore_snapshot(name,confirmation):
    if confirmation!='RESTAURAR':raise ValueError('Escribe RESTAURAR para confirmar el reemplazo de la base actual')
    with database_guard():
        snapshot=saved_snapshot(name)
        postgres=engine.dialect.name=='postgresql'
        if (snapshot.suffix=='.dump')!=postgres:raise ValueError('El respaldo pertenece a otro motor; usa la herramienta de migración para trasladar SQLite a PostgreSQL')
        validate_snapshot(snapshot)
        if postgres:
            # Validate schema and administrator in a disposable database before touching production.
            with staging_database() as staging:
                pg_command('pg_restore',['--clean','--if-exists','--no-owner','--no-privileges','--exit-on-error','--single-transaction','--dbname',staging.database,snapshot],staging)
                validate_postgres_contents(staging)
            recovery=create_snapshot('antes-restauracion')
            pg_command('pg_restore',['--clean','--if-exists','--no-owner','--no-privileges','--exit-on-error','--single-transaction','--dbname',engine.url.database,snapshot])
            with engine.begin() as connection:
                connection.execute(text('DELETE FROM sessions'))
                connection.execute(text('DELETE FROM inventory_imports WHERE committed_at IS NULL'))
                admin=connection.scalar(text("SELECT u.id FROM users u JOIN role_permissions rp ON rp.role_id=u.role_id JOIN permissions p ON p.id=rp.permission_id WHERE u.active=TRUE AND p.name='admin' LIMIT 1"))
                connection.execute(text('INSERT INTO audit(user_id,action,detail,created_at) VALUES(:user,:action,:detail,:created)'),{'user':admin,'action':'Base restaurada','detail':json.dumps({'respaldo':name,'recuperacion':recovery.name}),'created':datetime.now(timezone.utc).replace(tzinfo=None)})
        else:
            recovery=create_snapshot('antes-restauracion');engine.dispose()
            with closing(sqlite3.connect(snapshot.as_uri()+'?mode=ro',uri=True)) as source,closing(sqlite3.connect(database_path())) as destination,destination:
                source.backup(destination);destination.execute('PRAGMA foreign_keys=ON')
                destination.execute('DELETE FROM sessions');destination.execute('DELETE FROM inventory_imports WHERE committed_at IS NULL')
                admin=destination.execute("SELECT u.id FROM users u JOIN role_permissions rp ON rp.role_id=u.role_id JOIN permissions p ON p.id=rp.permission_id WHERE u.active=1 AND p.name='admin' LIMIT 1").fetchone()[0]
                destination.execute('INSERT INTO audit(user_id,action,detail,created_at) VALUES(?,?,?,?)',(admin,'Base restaurada',json.dumps({'respaldo':name,'recuperacion':recovery.name}),datetime.now(timezone.utc).replace(tzinfo=None).isoformat(' ')))
        return {'restored':name,'recovery':recovery.name}

@router.get('')
def list_backups(user=Depends(require('admin'))):
    expected='.dump' if engine.dialect.name=='postgresql' else '.db'
    return [{'name':p.name,'bytes':p.stat().st_size,'created_at':datetime.fromtimestamp(p.stat().st_mtime,timezone.utc).isoformat(),'engine':'postgresql' if p.suffix=='.dump' else 'sqlite','restorable':p.suffix==expected} for p in sorted(backup_dir().iterdir(),key=lambda p:p.stat().st_mtime,reverse=True) if p.suffix in ['.db','.dump'] and p.is_file() and not p.is_symlink()]

@router.post('',status_code=201)
def backup(user=Depends(require('admin')),db=Depends(db_session,scope='function')):
    try:path=create_snapshot()
    except (ValueError,sqlite3.Error) as error:fail(str(error),422)
    audit(db,user,'Respaldo creado',path.name)
    return {'name':path.name,'bytes':path.stat().st_size}

@router.get('/{name}')
def download(name:str,user=Depends(require('admin'))):
    try:path=saved_snapshot(name)
    except ValueError as error:fail(str(error),404)
    return FileResponse(path,filename=path.name,media_type='application/octet-stream' if path.suffix=='.dump' else 'application/vnd.sqlite3')
