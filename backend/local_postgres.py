"""Gestión de PostgreSQL local del proyecto, sin Docker, servicio global ni contraseñas predeterminadas."""
import argparse
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import tempfile
from sqlalchemy.engine import URL,make_url
from settings import ROOT,POSTGRES_BIN

DIRECTORY=ROOT/'.postgres'
DATA=DIRECTORY/'data'
CREDS=DIRECTORY/'credentials.json'

def run_tool(name,*args,check=True):
    executable=POSTGRES_BIN/(name+('.exe' if os.name=='nt' else ''))
    if not executable.is_file():raise RuntimeError(f'No se encuentra {name} en PG_BIN. Instala PostgreSQL o configura su carpeta bin.')
    # El proceso principal de PostgreSQL en Windows puede heredar identificadores de tuberías; utiliza un archivo para que pg_ctl pueda desvincularse correctamente.
    with tempfile.TemporaryFile() as output:
        process=subprocess.run([str(executable),*map(str,args)],stdout=output,stderr=output,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        output.seek(0);message=output.read().decode('utf-8',errors='replace')
    result=subprocess.CompletedProcess(process.args,process.returncode,message,'')
    if check and result.returncode:raise RuntimeError(f'{name}: '+(result.stderr or result.stdout).strip())
    return result

def credentials():
    if not CREDS.exists():raise RuntimeError('Inicializa PostgreSQL con local_postgres.py setup')
    return json.loads(CREDS.read_text(encoding='utf-8'))

def database_url(database=None,admin=False):
    config=credentials()
    return URL.create('postgresql+psycopg',username=config['admin_user'] if admin else config['app_user'],password=config['admin_password'] if admin else config['app_password'],host='127.0.0.1',port=config['port'],database=database or config['database'])

def maintenance_url(database='postgres'):
    if os.getenv('PG_ADMIN_URL'):return make_url(os.environ['PG_ADMIN_URL']).set(database=database)
    return database_url(database=database,admin=True)

def choose_port():
    for port in [5432,55432]:
        with socket.socket() as connection:
            try:connection.bind(('127.0.0.1',port));return port
            except OSError:continue
    raise RuntimeError('Los puertos locales 5432 y 55432 están ocupados')

def start():
    config=credentials()
    import psycopg
    connect=dict(host='127.0.0.1',port=config['port'],dbname='postgres',user=config['admin_user'],password=config['admin_password'],connect_timeout=3)
    try:
        with psycopg.connect(**connect) as connection:connection.execute('SELECT 1').fetchone()
        return config
    except psycopg.OperationalError:pass
    if not (DATA/'PG_VERSION').exists():raise RuntimeError('No existe el clúster PostgreSQL local; ejecuta setup')
    if run_tool('pg_ctl','status','-D',DATA,check=False).returncode:
        run_tool('pg_ctl','start','-D',DATA,'-l',DIRECTORY/'postgres.log','-w','-t','60')
    with psycopg.connect(host='127.0.0.1',port=config['port'],dbname='postgres',user=config['admin_user'],password=config['admin_password'],connect_timeout=10) as connection:
        connection.execute('SELECT 1').fetchone()
    return config

def setup():
    DIRECTORY.mkdir(exist_ok=True)
    if not CREDS.exists():
        if (DATA/'PG_VERSION').exists():raise RuntimeError('Ya existe un clúster sin su configuración privada; no se sobrescribirá')
        config={'port':choose_port(),'admin_user':'metaride_owner','admin_password':secrets.token_urlsafe(36),'app_user':'metaride_app','app_password':secrets.token_urlsafe(36),'database':'metaride'}
        CREDS.write_text(json.dumps(config,indent=2),encoding='utf-8')
    config=credentials()
    if not (DATA/'PG_VERSION').exists():
        password_file=DIRECTORY/'initdb-password.txt'
        password_file.write_text(config['admin_password'],encoding='utf-8')
        try:run_tool('initdb','-D',DATA,'-U',config['admin_user'],'--pwfile',password_file,'--auth-host=scram-sha-256','--auth-local=scram-sha-256','--encoding=UTF8','--locale=C')
        finally:password_file.unlink(missing_ok=True)
        with (DATA/'postgresql.conf').open('a',encoding='utf-8') as file:
            file.write(f"\n# Meta-Ride: local only\nlisten_addresses = '127.0.0.1'\nport = {config['port']}\ntimezone = 'UTC'\npassword_encryption = 'scram-sha-256'\n")
    start()
    import psycopg
    from psycopg import sql
    with psycopg.connect(host='127.0.0.1',port=config['port'],dbname='postgres',user=config['admin_user'],password=config['admin_password'],connect_timeout=10,autocommit=True) as connection:
        if not connection.execute('SELECT 1 FROM pg_roles WHERE rolname=%s',(config['app_user'],)).fetchone():
            connection.execute(sql.SQL('CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD {}').format(sql.Identifier(config['app_user']),sql.Literal(config['app_password'])))
        owner=connection.execute('SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname=%s',(config['database'],)).fetchone()
        if owner and owner[0]!=config['app_user']:raise RuntimeError('La base existente pertenece a otro usuario; no se modificará')
        if not owner:connection.execute(sql.SQL('CREATE DATABASE {} OWNER {} ENCODING {} TEMPLATE template0').format(sql.Identifier(config['database']),sql.Identifier(config['app_user']),sql.Literal('UTF8')))
        connection.execute(sql.SQL('REVOKE ALL ON DATABASE {} FROM PUBLIC').format(sql.Identifier(config['database'])))
    return {'engine':'postgresql','host':'127.0.0.1','port':config['port'],'database':config['database'],'user':config['app_user']}

def write_active_config():
    """Se llama solo después de que la migración haya verificado las filas copiadas."""
    from dotenv import dotenv_values
    values=dict(dotenv_values(ROOT/'.env')) if (ROOT/'.env').exists() else {}
    values.update(DATABASE_URL=database_url().render_as_string(hide_password=False),PG_BIN=POSTGRES_BIN.as_posix(),PG_LOCAL_AUTOSTART='true')
    lines=['# Configuración local privada. Excluida de Git.']
    for key,value in values.items():
        if value is not None:lines.append(key+'='+json.dumps(str(value),ensure_ascii=False))
    temporary=ROOT/'.env.pending'
    temporary.write_text('\n'.join(lines)+'\n',encoding='utf-8');temporary.replace(ROOT/'.env')
    (DIRECTORY/'ACTIVE_DATABASE').write_text('postgresql\n',encoding='ascii')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['setup','start','status','stop','autostart'])
    args=parser.parse_args()
    if args.command=='autostart':
        if os.getenv('PG_LOCAL_AUTOSTART','').lower()=='true':
            config=start();result={'engine':'postgresql','port':config['port'],'status':'running'}
        else:result={'autostart':False}
    elif args.command=='setup':result=setup()
    elif args.command=='start':
        config=start();result={'engine':'postgresql','port':config['port'],'status':'running'}
    elif args.command=='status':
        import psycopg
        config=credentials()
        try:
            with psycopg.connect(host='127.0.0.1',port=config['port'],dbname='postgres',user=config['admin_user'],password=config['admin_password'],connect_timeout=3) as connection:connection.execute('SELECT 1').fetchone()
            result={'running':True,'port':config['port']}
        except psycopg.OperationalError:result={'running':False,'port':config['port']}
    else:
        from backups import database_guard
        with database_guard():run_tool('pg_ctl','stop','-D',DATA,'-m','fast','-w','-t','60')
        result={'status':'stopped'}
    print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
