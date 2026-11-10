"""Reproducible scenarios; operational measurements are distinct from simulated risk."""
import random
from statistics import mean
import simpy
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

class Params(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    solicitudes: int = Field(50, ge=1, le=1000)
    montacargas: int = Field(2, ge=1, le=30)
    operadores: int = Field(3, ge=1, le=30)
    turno_minutos: int = Field(480, ge=60, le=1440)
    localizacion_min: float = Field(0, ge=0, le=120)
    localizacion_max: float = Field(0, ge=0, le=120)
    preparacion_min: float = Field(5, ge=0, le=120)
    preparacion_max: float = Field(12, ge=0, le=120)
    traslado_min: float = Field(8, ge=0, le=120)
    traslado_max: float = Field(20, ge=0, le=120)
    incidencia_min: float = Field(0, ge=0, le=120)
    incidencia_max: float = Field(0, ge=0, le=120)
    probabilidad_incidencia: float = Field(0, ge=0, le=100)
    tiempo_requerido_min: float = Field(60, gt=0, le=1440)
    tolerancia_paro_min: float = Field(30, ge=0, le=1440)
    distribucion: Literal['uniforme','triangular'] = 'uniforme'
    porcentaje_urgentes: int = Field(25, ge=0, le=100)
    prioridad: Literal['urgentes','llegada'] = 'urgentes'
    semilla: int = Field(42, ge=0, le=100000000)
    replicas: int = Field(10, ge=1, le=100)

    @model_validator(mode='after')
    def ranges(self):
        for stage in ['localizacion','preparacion','traslado','incidencia']:
            if getattr(self,stage+'_min')>getattr(self,stage+'_max'):
                raise ValueError(f'{stage}: el mínimo debe ser menor o igual al máximo')
        return self

def una_corrida(p: Params, semilla: int):
    rng=random.Random(semilla)
    env=simpy.Environment()
    operators=simpy.PriorityResource(env,capacity=p.operadores)
    forklifts=simpy.PriorityResource(env,capacity=p.montacargas)
    records=[]
    operator_busy=0.0
    forklift_busy=0.0
    # Generate exogenous inputs before scheduling; comparisons share arrivals and tasks.
    arrivals=sorted(rng.uniform(0,p.turno_minutos) for _ in range(p.solicitudes))
    def duration(stage):
        lo,hi=getattr(p,stage+'_min'),getattr(p,stage+'_max')
        return rng.triangular(lo,hi,(lo+hi)/2) if p.distribucion=='triangular' else rng.uniform(lo,hi)
    tasks=[]
    for arrival in arrivals:
        urgent=rng.random()<p.porcentaje_urgentes/100
        locate,prepare,travel=duration('localizacion'),duration('preparacion'),duration('traslado')
        incident=rng.random()<p.probabilidad_incidencia/100
        incident_duration=duration('incidencia') if incident else 0
        tasks.append((arrival,urgent,locate,prepare,travel,incident,incident_duration))
    def overlap(start,end): return max(0,min(end,p.turno_minutos)-min(start,p.turno_minutos))
    def attend(index,task):
        nonlocal operator_busy,forklift_busy
        arrival,urgent,locate,prepare,travel,incident,incident_duration=task
        priority=0 if p.prioridad=='urgentes' and urgent else 1
        yield env.timeout(arrival)
        with operators.request(priority=priority) as op:
            yield op
            start=env.now
            yield env.timeout(locate+prepare)
            ready=env.now
            with forklifts.request(priority=priority) as lift:
                yield lift
                travel_start=env.now
                # An obstructed route occupies both operator and forklift until cleared.
                yield env.timeout(incident_duration+travel)
                end=env.now
                forklift_busy+=overlap(travel_start,end)
            operator_busy+=overlap(start,end)
        deadline=arrival+p.tiempo_requerido_min
        late=max(0,end-deadline)
        records.append({'id':index+1,'llegada':round(arrival,2),'inicio':round(start,2),'fin':round(end,2),'espera':round((start-arrival)+(travel_start-ready),2),'espera_operador':round(start-arrival,2),'espera_equipo':round(travel_start-ready,2),'duracion':round(end-arrival,2),'localizacion':round(locate,2),'preparacion':round(prepare,2),'traslado':round(travel,2),'incidencia':incident,'tiempo_incidencia':round(incident_duration,2),'urgente':urgent,'a_tiempo':end<=p.turno_minutos,'hora_requerida':round(deadline,2),'retraso':round(late,2),'a_tiempo_requerido':end<=deadline,'riesgo_paro':late>p.tolerancia_paro_min})
    for index,task in enumerate(tasks): env.process(attend(index,task))
    env.run()
    records.sort(key=lambda r:r['id'])
    percent=lambda predicate:100*sum(predicate(r) for r in records)/p.solicitudes
    return {'espera_promedio':mean(r['espera'] for r in records),'tiempo_total_promedio':mean(r['duracion'] for r in records),'entregas_en_turno':sum(r['a_tiempo'] for r in records),'porcentaje_en_turno':percent(lambda r:r['a_tiempo']),'espera_maxima':max(r['espera'] for r in records),'ultima_entrega':max(r['fin'] for r in records),'porcentaje_retraso':percent(lambda r:not r['a_tiempo_requerido']),'porcentaje_riesgo_paro':percent(lambda r:r['riesgo_paro']),'porcentaje_esperaron_equipo':percent(lambda r:r['espera_equipo']>0),'utilizacion_operadores':100*operator_busy/(p.operadores*p.turno_minutos),'utilizacion_montacargas':100*forklift_busy/(p.montacargas*p.turno_minutos),'incidencias_promedio':sum(r['incidencia'] for r in records),'registros':records}

def simulate(p):
    runs=[una_corrida(p,p.semilla+i) for i in range(p.replicas)]
    fields=[key for key in runs[0] if key!='registros']
    return {'parametros':p.model_dump(),'resumen':{field:round(mean(run[field] for run in runs),2) for field in fields},'corridas':[{'replica':i+1,**{key:round(run[key],2) for key in fields}} for i,run in enumerate(runs)],'muestra':runs[0]['registros'][:100],'nota':'Escenario hipotético: llegadas uniformes; servicios uniformes o triangulares; prioridad no expropiativa en ambas colas. El riesgo de paro representa retraso mayor a la tolerancia configurada, no una probabilidad industrial validada. Ocupación medida dentro del turno; las tareas pendientes se completan después.'}
