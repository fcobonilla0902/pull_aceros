"""Copia SQLite a una base de datos VACÍA de PostgreSQL y verifica cada fila antes de activarla."""
import argparse
from contextlib import closing,nullcontext
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import sqlite3
import subprocess
import sys
from sqlalchemy import create_engine,select,text,inspect
from database import Base
from settings import ROOT
from backups import database_guard
from local_postgres import database_url,write_active_config

def upgrade(url):
    environment=os.environ.copy();environment['DATABASE_URL']=str(url)
    result=subprocess.run([sys.executable,'-m','alembic','-c',str(ROOT/'alembic.ini'),'upgrade','head'],cwd=ROOT,env=environment,capture_output=True,text=True,encoding='utf-8',errors='replace')
    if result.returncode:raise ValueError('No se pudieron aplicar las migraciones. '+result.stderr[-1800:])

def normalized(row):
    return {key:value.isoformat() if isinstance(value,datetime) else value for key,value in row.items()}

def fingerprint(rows):
    return hashlib.sha256(json.dumps([normalized(r) for r in rows],ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def migrate(source,target,activate=False):
    source=Path(source).resolve()
    if not source.is_file():raise ValueError('No se encuentra la base SQLite de origen')
    source_url='sqlite:///'+str(source)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+secrets.token_hex(4)
    snapshot=ROOT/'backups'/f'antes-postgresql-{stamp}.db'
    snapshot.parent.mkdir(exist_ok=True)
    # La API activa de SQLite debe detenerse antes de la copia final. La copia de prueba permite mantenerla en ejecución.
    with database_guard(source_url) if activate else nullcontext():
        with closing(sqlite3.connect(source)) as origin,closing(sqlite3.connect(snapshot)) as copy,copy:
            origin.backup(copy)
            if copy.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or copy.execute('PRAGMA foreign_key_check').fetchone():raise ValueError('La SQLite de origen no supera la verificación de integridad')
        upgrade('sqlite:///'+str(snapshot))
        source_engine=create_engine('sqlite:///'+str(snapshot))
        target_engine=create_engine(target,pool_pre_ping=True)
        try:
            if target_engine.dialect.name!='postgresql':raise ValueError('El destino debe ser PostgreSQL')
            inspector=inspect(target_engine)
            with target_engine.connect() as connection:
                for table in Base.metadata.sorted_tables:
                    if inspector.has_table(table.name) and connection.scalar(select(table).limit(1)) is not None:raise ValueError('El destino ya contiene datos; no se sobrescribirá')
            upgrade(target.render_as_string(hide_password=False))
            checks={}
            with source_engine.connect() as origin,target_engine.begin() as destination:
                for table in Base.metadata.sorted_tables:
                    rows=[dict(row) for row in origin.execute(select(table).order_by(*table.primary_key.columns)).mappings()]
                    for row in rows:
                        for column in table.columns:
                            value=row[column.name]
                            if isinstance(value,str) and getattr(column.type,'length',None) and len(value)>column.type.length:raise ValueError(f'{table.name}.{column.name}: existe un valor que supera el tamaño permitido')
                    for start in range(0,len(rows),500):destination.execute(table.insert(),rows[start:start+500])
                    copied=[dict(row) for row in destination.execute(select(table).order_by(*table.primary_key.columns)).mappings()]
                    if fingerprint(rows)!=fingerprint(copied):raise ValueError(f'No coincide el contenido de {table.name}; se revierte la copia completa')
                    checks[table.name]={'rows':len(rows),'sha256':fingerprint(rows),'verified':True}
                    if 'id' in table.c:
                        sequence=destination.scalar(text("SELECT pg_get_serial_sequence(:table,'id')"),{'table':'public.'+table.name})
                        if sequence:
                            maximum=max((row['id'] for row in rows),default=0)
                            destination.execute(text('SELECT setval(CAST(:sequence AS regclass),:maximum,:called)'),{'sequence':sequence,'maximum':max(1,maximum),'called':maximum>0})
            if activate:write_active_config()
            result={'activated':activate,'source_backup':snapshot.name,'database':target.database,'engine':'postgresql','verified_tables':checks,'verified_rows':sum(row['rows'] for row in checks.values()),'created_at':datetime.now(timezone.utc).isoformat()}
            reports=ROOT/'migration-reports';reports.mkdir(exist_ok=True)
            (reports/f'postgresql-{stamp}.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
            return result
        finally:source_engine.dispose();target_engine.dispose()

def main():
    parser=argparse.ArgumentParser(description='Migración conservadora Meta-Ride SQLite → PostgreSQL')
    parser.add_argument('--source',default=str(ROOT/'metaride.db'))
    parser.add_argument('--activate',action='store_true')
    args=parser.parse_args()
    try:
        result=migrate(args.source,database_url(),activate=args.activate)
        print(json.dumps({'activated':result['activated'],'engine':result['engine'],'database':result['database'],'tables':len(result['verified_tables']),'rows':result['verified_rows'],'source_backup':result['source_backup']},ensure_ascii=False))
    except Exception as error:
        from sqlalchemy.exc import DBAPIError
        reason=f'PostgreSQL rechazó la copia ({getattr(error.orig,"sqlstate","sin código")})' if isinstance(error,DBAPIError) else str(error)
        parser.exit(1,'No se activó PostgreSQL. '+reason+'\n')
if __name__=='__main__':main()
