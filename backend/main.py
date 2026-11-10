"""Meta-Ride: simulación de surtimiento de acero con SimPy."""
from __future__ import annotations
from fastapi import FastAPI, Depends
from contextlib import asynccontextmanager
from security import bootstrap, require, db_session
from api import router
from maintenance import router as maintenance_router
from request_revisions import router as revision_router
from inventory_import import router as import_router
from backups import router as backup_router, server_guard
from database import SimulationRun,engine
import json
import os
from fastapi.middleware.cors import CORSMiddleware

@asynccontextmanager
async def lifespan(app):
    with server_guard():
        bootstrap()
        yield

app = FastAPI(title="Meta-Ride / Pull Aceros", version="2.0.0", lifespan=lifespan)
app.include_router(router)
app.include_router(maintenance_router)
app.include_router(revision_router)
app.include_router(import_router)
app.include_router(backup_router)
app.add_middleware(CORSMiddleware, allow_origins=os.getenv('CORS_ORIGINS','http://localhost:5173,http://localhost:5174,http://127.0.0.1:5173,http://127.0.0.1:5174').split(','), allow_credentials=True, allow_methods=["GET", "POST", "PATCH"], allow_headers=["*"])

from simulation import Params, una_corrida, simulate

@app.get('/salud')
def salud():
    return {'estado':'ok','database':engine.dialect.name}

@app.post('/simular')
def simular(p: Params,user=Depends(require('simulate')),db=Depends(db_session, scope='function')):
    result=simulate(p)
    db.add(SimulationRun(user_id=user.id,parameters=json.dumps(p.model_dump()),result=json.dumps(result)))
    return result
