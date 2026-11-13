"""Inventario técnico generado desde el código, sin conectar la base operativa."""
import ast
import importlib.metadata
import json
import os
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
BUILD=ROOT/'backend'/'manuales_build'
BUILD.mkdir(exist_ok=True)
os.environ['DATABASE_URL']='sqlite:///:memory:'
from main import app
from database import Base

tables=[]
for table in Base.metadata.sorted_tables:
    tables.append(dict(name=table.name,columns=[dict(name=c.name,type=str(c.type),nullable=c.nullable,pk=c.primary_key,fk=[str(f.column) for f in c.foreign_keys],unique=bool(c.unique)) for c in table.columns]))
routes=[]
spec=app.openapi()
for path, operations in spec['paths'].items():
    for method, detail in operations.items():
        if method not in {'get','post','patch','put','delete'}:continue
        routes.append(dict(path=path,methods=[method.upper()],name=detail.get('summary',''),status=next((int(code) for code in detail['responses'] if code.startswith('2')),200)))
versions={name:importlib.metadata.version(name) for name in ['fastapi','uvicorn','simpy','pydantic','SQLAlchemy','alembic','psycopg','openpyxl','python-docx','playwright']}
front={name:json.loads((ROOT/'node_modules'/name/'package.json').read_text(encoding='utf-8'))['version'] for name in ['react','react-dom','vite','tailwindcss','recharts','framer-motion','lucide-react']}
sources=[]
for base in [ROOT/'src',ROOT/'backend',ROOT/'docs']:
    for p in base.rglob('*'):
        if any(part in {'.venv','.postgres','__pycache__','manuales_build','backups','migration-reports','capturas'} for part in p.parts):continue
        if p.is_file() and p.suffix in {'.py','.jsx','.js','.md','.ps1','.ini','.css'} and not p.name.startswith('manuales_'):
            content=p.read_text(encoding='utf-8-sig')
            sources.append(dict(path=p.relative_to(ROOT).as_posix(),lines=len(content.splitlines())))
(BUILD/'metadata.json').write_text(json.dumps(dict(tables=tables,routes=routes,backend_versions=versions,frontend_versions=front,sources=sources),ensure_ascii=False,indent=2),encoding='utf-8')
(BUILD/'openapi.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2),encoding='utf-8')
print('Inventario:',len(tables),'tablas;',len(routes),'rutas;',len(sources),'archivos fuente leídos.')
