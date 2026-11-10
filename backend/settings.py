"""Load local configuration only when the caller has not selected another database."""
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT=Path(__file__).resolve().parent
if not os.getenv('DATABASE_URL'):
    load_dotenv(ROOT/'.env',override=False)
if not os.getenv('DATABASE_URL') and (ROOT/'.postgres'/'ACTIVE_DATABASE').exists():
    raise RuntimeError('Falta backend/.env del entorno PostgreSQL. No se utilizará automáticamente la antigua base SQLite.')

DATABASE_URL=os.getenv('DATABASE_URL','sqlite:///'+str(ROOT/'metaride.db'))
POSTGRES_BIN=Path(os.getenv('PG_BIN',str(ROOT/'.postgres'/'pgsql'/'bin')))
