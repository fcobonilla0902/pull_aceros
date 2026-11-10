"""Validate against disposable PostgreSQL databases; never tests on the live database."""
from contextlib import contextmanager
import argparse
import json
import os
import secrets
import subprocess
import sys
from pathlib import Path
from local_postgres import start,credentials,database_url,maintenance_url
from settings import ROOT

@contextmanager
def temporary_database():
    import psycopg
    from psycopg import sql
    owner=maintenance_url();config=credentials();name='metaride_test_'+secrets.token_hex(8)
    with psycopg.connect(host=owner.host,port=owner.port,dbname=owner.database,user=owner.username,password=owner.password,connect_timeout=10,autocommit=True) as connection:
        connection.execute(sql.SQL('CREATE DATABASE {} OWNER {} TEMPLATE template0 ENCODING {}').format(sql.Identifier(name),sql.Identifier(config['app_user']),sql.Literal('UTF8')))
        try:yield database_url(database=name)
        finally:connection.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--migration-only',action='store_true');parser.add_argument('--skip-migration',action='store_true');parser.add_argument('--browser',action='store_true');args=parser.parse_args()
    start()
    if args.browser:
        with temporary_database() as target:
            environment=os.environ.copy();environment['METARIDE_BROWSER_DATABASE_URL']=target.render_as_string(hide_password=False)
            result=subprocess.run([sys.executable,str(ROOT/'check_browser.py')],cwd=ROOT.parent,env=environment)
            raise SystemExit(result.returncode)
    if not args.skip_migration:
        from migrate_postgres import migrate
        with temporary_database() as target:
            result=migrate(ROOT/'metaride.db',target)
            print(json.dumps({'trial_migration':'ok','tables':len(result['verified_tables']),'rows':result['verified_rows']},ensure_ascii=False),flush=True)
    if args.migration_only:return
    with temporary_database() as target:
        environment=os.environ.copy()
        environment['DATABASE_URL']=target.render_as_string(hide_password=False)
        environment['METARIDE_TEST_DATABASE_URL']=environment['DATABASE_URL']
        environment['PG_ADMIN_URL']=maintenance_url().render_as_string(hide_password=False)
        result=subprocess.run([sys.executable,'-m','unittest','-v','test_integration','test_postgres_concurrency'],cwd=ROOT,env=environment)
        if result.returncode:raise SystemExit(result.returncode)
if __name__=='__main__':main()
