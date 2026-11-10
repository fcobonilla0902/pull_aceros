import { useEffect, useState } from "react";
import { Play, BarChart3, AlertTriangle, LoaderCircle, Truck, Clock3, CheckCircle2, Timer } from "lucide-react";

import { api } from "./api";

const API = import.meta.env.VITE_API_URL || import.meta.env.VITE_SIM_API || "";

// Estos parámetros permanecen fijos para simplificar la interfaz.
const DEFAULTS = {
  solicitudes: 50,
  montacargas: 2,
  operadores: 3,
  turno_minutos: 480,
  preparacion_min: 5,
  preparacion_max: 12,
  traslado_min: 8,
  traslado_max: 20,
  porcentaje_urgentes: 0,
  prioridad: "llegada",
  semilla: 42,
  replicas: 10,
};

const fmt = (value) => Number(value ?? 0).toLocaleString("es-MX", { maximumFractionDigits: 2 });

function MetricCard({ icon: Icon, label, value, description }) {
  return (
    <div className="rounded-2xl bg-white p-5 shadow-sm">
      <div className="mb-3 flex items-center gap-2 text-blue-700"><Icon size={19} /><span className="text-xs font-bold uppercase text-slate-500">{label}</span></div>
      <p className="text-2xl font-bold text-slate-900">{value}</p>
      <p className="mt-1 text-xs text-slate-500">{description}</p>
    </div>
  );
}

function ComparisonBar({ row, max }) {
  const width = max > 0 ? Math.min(100, Math.max(0, (row.espera_promedio / max) * 100)) : 0;
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-3 text-sm">
        <span className="font-semibold text-slate-700">{row.label || `${row.montacargas} montacargas`}</span>
        <span className="text-slate-600">{fmt(row.espera_promedio)} min de espera</span>
      </div>
      <div className="h-3 overflow-hidden rounded-full bg-slate-100">
        <div className="h-full rounded-full bg-blue-600" style={{ width: `${width}%` }} />
      </div>
      <p className="text-xs text-slate-500">{fmt(row.porcentaje_en_turno)}% entregadas dentro del turno</p>
    </div>
  );
}

export default function SimulationPage() {
  const [advanced,setAdvanced]=useState({turno_minutos:480,localizacion_min:0,localizacion_max:0,incidencia_min:0,incidencia_max:0,probabilidad_incidencia:0,tiempo_requerido_min:60,tolerancia_paro_min:30,distribucion:'uniforme'});
  const [rule,setRule]=useState('auto');
  const [history, setHistory] = useState([]);
  const [calibration, setCalibration] = useState(null);
  const [useHistorical, setUseHistorical] = useState(false);
  const [solicitudes, setSolicitudes] = useState(50);
  const [montacargas, setMontacargas] = useState(2);
  const [operadores, setOperadores] = useState(3);
  const [demanda, setDemanda] = useState("normal");
  const [result, setResult] = useState(null);
  const [comparison, setComparison] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  useEffect(()=>{Promise.all([api('/api/simulations'),api('/api/simulations/calibration')]).then(([h,c])=>{setHistory(h);setCalibration(c);}).catch(e=>setError(e.message));},[]);

  const params = {
    ...DEFAULTS,
    ...advanced,
    ...(useHistorical ? calibration?.parameters : {}),
    solicitudes,
    montacargas,
    operadores,
    porcentaje_urgentes: demanda === "urgente" ? 25 : 0,
    prioridad: rule === 'auto' ? (demanda === "urgente" ? "urgentes" : "llegada") : rule,
  };

  async function post(payload) {
    const response = await fetch(`${API}/simular`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(typeof body.detail === "string" ? body.detail : `Error HTTP ${response.status}`);
    }
    const result = await response.json();
    api('/api/simulations').then(setHistory).catch(()=>{});
    return result;
  }

  async function run(compare = false) {
    if (![solicitudes, montacargas, operadores].every((n) => Number.isInteger(n) && n >= 1)) {
      setError("Las solicitudes, montacargas y operadores deben ser números enteros mayores que cero.");
      return;
    }
    setLoading(true);
    setError("");
    setResult(null);
    setComparison([]);
    try {
      if (compare === 'rules') {
        const responses=await Promise.all(['llegada','urgentes'].map(prioridad=>post({...params,prioridad})));
        setComparison(responses.map((response,index)=>({label:index===0?'Orden de llegada':'Urgentes primero',...response.resumen})));
      } else if (compare) {
        const responses = await Promise.all(
          [1, 2, 3, 4].map((count) => post({ ...params, montacargas: count }))
        );
        setComparison(responses.map((response, index) => ({
          montacargas: index + 1,
          ...response.resumen,
        })));
      } else {
        setResult(await post(params));
      }
    } catch (err) {
      setError(`${err.message}. Verifica que el servidor Python esté activo en ${API}.`);
    } finally {
      setLoading(false);
    }
  }

  const summary = result?.resumen;
  const maxWait = Math.max(1, ...comparison.map((row) => Number(row.espera_promedio) || 0));

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs font-bold uppercase tracking-widest text-blue-700">Modelado y simulación</p>
        <h1 className="mt-1 text-3xl font-bold text-slate-900">Simulador de surtimiento de acero</h1>
        <p className="mt-2 text-sm text-slate-500">Descubre cómo cambia el tiempo de entrega al modificar los recursos disponibles.</p>
      </div>

      <div className="grid gap-5 xl:grid-cols-[380px_1fr]">
        <section className="space-y-4 rounded-2xl bg-white p-5 shadow-sm">
          <h2 className="font-bold text-slate-900">Configura tu escenario</h2>
          {calibration && <label className="block rounded-xl bg-blue-50 p-3 text-xs text-blue-800"><input type="checkbox" checked={useHistorical} onChange={e=>setUseHistorical(e.target.checked)} disabled={Object.keys(calibration.parameters).length===0}/> Usar rangos históricos disponibles. Muestras: preparación {calibration.samples.preparacion}, traslado {calibration.samples.traslado}. Se necesitan 5 por etapa; las etapas sin muestras suficientes conservan los supuestos originales.</label>}
          <div className="grid grid-cols-2 gap-3">
            {[
              ["Solicitudes de acero", solicitudes, setSolicitudes],
              ["Montacargas", montacargas, setMontacargas],
              ["Operadores", operadores, setOperadores],
            ].map(([label, value, setter]) => (
              <label key={label} className="space-y-1 text-xs font-semibold text-slate-600">
                <span>{label}</span>
                <input
                  type="number"
                  min="1"
                  step="1"
                  value={value}
                  onChange={(event) => setter(Number(event.target.value))}
                  className="w-full rounded-lg border border-slate-200 p-2.5 text-sm text-slate-900"
                />
              </label>
            ))}
            <label className="space-y-1 text-xs font-semibold text-slate-600">
              <span>Tipo de demanda</span>
              <select
                value={demanda}
                onChange={(event) => setDemanda(event.target.value)}
                className="w-full rounded-lg border border-slate-200 bg-white p-2.5 text-sm text-slate-900"
              >
                <option value="normal">Normal</option>
                <option value="urgente">Con urgencias</option>
              </select>
            </label>
          </div>

          <details className="space-y-3 rounded-xl border border-slate-200 p-3"><summary className="cursor-pointer text-sm font-semibold">Escenario avanzado: turnos, localización, incidencias y prioridades</summary>
            <div className="grid grid-cols-2 gap-3">{[
              ['turno_minutos','Duración del turno (min)',60,1440],['localizacion_min','Localización mínima (min)',0,120],['localizacion_max','Localización máxima (min)',0,120],['probabilidad_incidencia','Incidencias (%)',0,100],['incidencia_min','Incidencia mínima (min)',0,120],['incidencia_max','Incidencia máxima (min)',0,120],['tiempo_requerido_min','Plazo desde solicitud (min)',0.01,1440],['tolerancia_paro_min','Retraso tolerado antes de riesgo de paro (min)',0,1440]
            ].map(([key,label,min,max])=><label key={key} className="text-xs font-semibold text-slate-600">{label}<input type="number" min={min} max={max} step={key==='turno_minutos'?1:0.01} value={advanced[key]} onChange={e=>setAdvanced({...advanced,[key]:Number(e.target.value)})} className="mt-1 w-full rounded-lg border p-2"/></label>)}</div>
            <label className="block text-xs">Distribución de duraciones<select value={advanced.distribucion} onChange={e=>setAdvanced({...advanced,distribucion:e.target.value})} className="mt-1 w-full rounded-lg border p-2"><option value="uniforme">Uniforme</option><option value="triangular">Triangular (moda en punto medio)</option></select></label>
            <label className="block text-xs">Regla de atención<select value={rule} onChange={e=>setRule(e.target.value)} className="mt-1 w-full rounded-lg border p-2"><option value="auto">Según tipo de demanda</option><option value="llegada">Orden de llegada</option><option value="urgentes">Urgentes primero</option></select></label>
          </details>
          <p className="rounded-xl bg-slate-50 p-3 text-xs text-slate-500">
            Turno de {params.turno_minutos} min. Preparación: {params.preparacion_min}–{params.preparacion_max} min; traslado: {params.traslado_min}–{params.traslado_max} min.
            {demanda === "urgente" ? " El 25% de las solicitudes será urgente." : " Las solicitudes se atienden por orden de llegada."}
          </p>

          <button
            type="button"
            disabled={loading}
            onClick={() => run(false)}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-blue-600 p-3 font-bold text-white hover:bg-blue-700 disabled:opacity-60"
          >
            {loading ? <LoaderCircle className="animate-spin" size={18} /> : <Play size={18} />}
            Ejecutar simulación
          </button>
          <button
            type="button"
            disabled={loading}
            onClick={() => run(true)}
            className="flex w-full items-center justify-center gap-2 rounded-xl border border-blue-200 p-3 font-semibold text-blue-700 hover:bg-blue-50 disabled:opacity-60"
          >
            <BarChart3 size={18} /> Comparar 1 a 4 montacargas
          </button>
          <button type="button" disabled={loading} onClick={()=>run('rules')} className="w-full rounded-xl border border-blue-200 p-3 font-semibold text-blue-700 disabled:opacity-50">Comparar FIFO y urgentes primero</button>
        </section>

        <section className="space-y-4">
          {error && (
            <div className="flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
              <AlertTriangle size={18} className="shrink-0" /> {error}
            </div>
          )}

          {!summary && comparison.length === 0 && !error && (
            <div className="rounded-2xl bg-white p-10 text-center text-slate-500 shadow-sm">
              <Truck size={34} className="mx-auto mb-3 text-blue-600" />
              Configura tu escenario y presiona «Ejecutar simulación».
            </div>
          )}

          {summary && (
            <>
              <h2 className="font-bold text-slate-900">Resultados de la simulación</h2>
              <div className="grid gap-3 sm:grid-cols-2">
                <MetricCard icon={Clock3} label="Tiempo promedio de entrega" value={`${fmt(summary.tiempo_total_promedio)} min`} description="Desde la solicitud hasta la entrega" />
                <MetricCard icon={Timer} label="Tiempo promedio de espera" value={`${fmt(summary.espera_promedio)} min`} description="Tiempo esperando recursos disponibles" />
                <MetricCard icon={CheckCircle2} label="Entregas dentro del turno" value={fmt(summary.entregas_en_turno)} description={`Solicitudes completadas en ${result.parametros.turno_minutos} min (promedio de réplicas)`} />
                <MetricCard icon={BarChart3} label="Cumplimiento del turno" value={`${fmt(summary.porcentaje_en_turno)}%`} description="Porcentaje completado antes de finalizar el turno" />
                <MetricCard icon={AlertTriangle} label="Solicitudes con retraso" value={`${fmt(summary.porcentaje_retraso)}%`} description="Entrega posterior al plazo desde la solicitud"/>
                <MetricCard icon={AlertTriangle} label="Riesgo simulado de paro" value={`${fmt(summary.porcentaje_riesgo_paro)}%`} description={`Retraso superior a ${result.parametros.tolerancia_paro_min} min; supuesto de escenario`}/>
                <MetricCard icon={Truck} label="Ocupación de montacargas" value={`${fmt(summary.utilizacion_montacargas)}%`} description="Dentro del turno, incluye obstrucción de ruta"/>
                <MetricCard icon={Timer} label="Ocupación de operadores" value={`${fmt(summary.utilizacion_operadores)}%`} description="Incluye espera por equipo; permite detectar saturación"/>
              </div>
              <p className="rounded-xl bg-amber-50 p-3 text-xs text-amber-800">{result.nota}</p>
            </>
          )}

          {comparison.length > 0 && (
            <div className="space-y-4 rounded-2xl bg-white p-5 shadow-sm">
              <h2 className="font-bold text-slate-900">Comparación de escenarios</h2>
              <p className="text-xs text-slate-500">Se usan las mismas llegadas y duraciones pseudoaleatorias; cambia únicamente el recurso o la regla elegida.</p>
              {comparison.map((row) => <ComparisonBar key={row.label || row.montacargas} row={row} max={maxWait} />)}
            </div>
          )}

          {history.length>0 && <div className="rounded-2xl bg-white p-5 shadow-sm"><h2 className="mb-3 font-bold">Simulaciones guardadas</h2>{history.slice(0,10).map(h=><p key={h.id} className="border-t py-2 text-xs text-slate-600">{new Date(h.created_at+'Z').toLocaleString('es-MX')} · {h.parameters.solicitudes} solicitudes · {h.parameters.montacargas} montacargas · {fmt(h.summary.espera_promedio)} min de espera</p>)}</div>}
        </section>
      </div>
    </div>
  );
}
