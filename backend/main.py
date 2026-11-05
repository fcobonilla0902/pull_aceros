"""Meta-Ride: simulación de surtimiento de acero con SimPy."""
from __future__ import annotations
import random
from statistics import mean
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import simpy

app = FastAPI(title="Meta-Ride Simulador", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://localhost:5174", "http://127.0.0.1:5173", "http://127.0.0.1:5174"], allow_credentials=False, allow_methods=["GET", "POST"], allow_headers=["*"])

class Params(BaseModel):
    solicitudes: int = Field(50, ge=1, le=1000)
    montacargas: int = Field(2, ge=1, le=30)
    operadores: int = Field(3, ge=1, le=30)
    turno_minutos: int = Field(480, ge=60, le=1440)
    preparacion_min: float = Field(5, ge=0, le=120)
    preparacion_max: float = Field(12, ge=0, le=120)
    traslado_min: float = Field(8, ge=0, le=120)
    traslado_max: float = Field(20, ge=0, le=120)
    porcentaje_urgentes: int = Field(25, ge=0, le=100)
    prioridad: str = Field("urgentes", pattern="^(urgentes|llegada)$")
    semilla: int = Field(42, ge=0, le=100000000)
    replicas: int = Field(10, ge=1, le=100)


def una_corrida(p: Params, semilla: int):
    if p.preparacion_min > p.preparacion_max or p.traslado_min > p.traslado_max:
        raise ValueError("Los mínimos no pueden superar los máximos")
    rng = random.Random(semilla)
    env = simpy.Environment()
    # El operador realiza preparación y traslado; el montacargas se ocupa en traslado.
    operadores = simpy.Resource(env, capacity=p.operadores)
    montacargas = simpy.PriorityResource(env, capacity=p.montacargas) if p.prioridad == "urgentes" else simpy.Resource(env, capacity=p.montacargas)
    registros = []
    interarribos = sorted(rng.uniform(0, p.turno_minutos) for _ in range(p.solicitudes))

    def atender(idx, llegada, urgente, preparacion, traslado):
        yield env.timeout(llegada)
        # Solicitudes que esperan operador: FIFO; urgencia prioriza cola del montacargas.
        with operadores.request() as req_op:
            yield req_op
            with montacargas.request(priority=0 if urgente else 1) if p.prioridad == "urgentes" else montacargas.request() as req_m:
                yield req_m
                inicio = env.now
                yield env.timeout(preparacion + traslado)
                fin = env.now
        registros.append({"id": idx + 1, "llegada": round(llegada, 2), "inicio": round(inicio, 2), "fin": round(fin, 2), "espera": round(inicio-llegada, 2), "duracion": round(fin-llegada, 2), "urgente": urgente, "a_tiempo": fin <= p.turno_minutos})

    for i, llegada in enumerate(interarribos):
        urgente = rng.random() < p.porcentaje_urgentes / 100
        prep = rng.uniform(p.preparacion_min, p.preparacion_max)
        tras = rng.uniform(p.traslado_min, p.traslado_max)
        env.process(atender(i, llegada, urgente, prep, tras))
    env.run()
    registros.sort(key=lambda x: x["id"])
    espera = mean(r["espera"] for r in registros)
    duracion = mean(r["duracion"] for r in registros)
    finalizados = sum(r["a_tiempo"] for r in registros)
    return {"espera_promedio": espera, "tiempo_total_promedio": duracion, "entregas_en_turno": finalizados, "porcentaje_en_turno": 100 * finalizados / p.solicitudes, "espera_maxima": max(r["espera"] for r in registros), "ultima_entrega": max(r["fin"] for r in registros), "registros": registros}

@app.get("/salud")
def salud():
    return {"estado": "ok"}

@app.post("/simular")
def simular(p: Params):
    if p.preparacion_min > p.preparacion_max or p.traslado_min > p.traslado_max:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail="Los tiempos mínimos deben ser menores o iguales a los máximos")
    corridas = [una_corrida(p, p.semilla + i) for i in range(p.replicas)]
    campos = ["espera_promedio", "tiempo_total_promedio", "entregas_en_turno", "porcentaje_en_turno", "espera_maxima", "ultima_entrega"]
    resumen = {campo: round(mean(c[campo] for c in corridas), 2) for campo in campos}
    return {"parametros": p.model_dump(), "resumen": resumen, "corridas": [{"replica": i+1, **{k: round(c[k], 2) for k in campos}} for i,c in enumerate(corridas)], "muestra": corridas[0]["registros"][:100], "nota": "Modelo académico: llegadas uniformes, tiempos uniformes y operadores compartidos; validar supuestos con datos reales."}
