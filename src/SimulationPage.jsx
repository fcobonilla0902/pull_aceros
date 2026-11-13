import { useEffect, useState } from "react";
import { Play, BarChart3, AlertTriangle, LoaderCircle, Truck, Clock3, CheckCircle2, Timer } from "lucide-react";

import { api } from "./api";

const API = import.meta.env.VITE_API_URL || import.meta.env.VITE_SIM_API || "";

// Valores iniciales del escenario. La preparación y el traslado se mantienen
// fijos; la pantalla solo permite cambiar demanda, recursos, turno y atención.
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

// Tarjeta reutilizable para cada uno de los tres resultados básicos.
function MetricCard({ icon: Icon, label, value, description }) {
  return (
    <div className="rounded-2xl bg-white p-5 shadow-sm">
      <div className="mb-3 flex items-center gap-2 text-blue-700"><Icon size={19} /><span className="text-xs font-bold uppercase text-slate-500">{label}</span></div>
      <p className="text-2xl font-bold text-slate-900">{value}</p>
      <p className="mt-1 text-xs text-slate-500">{description}</p>
    </div>
  );
}

// La longitud de cada barra representa la espera media del escenario.
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
      <p className="text-xs text-slate-500">Entrega promedio: {fmt(row.tiempo_total_promedio)} min · {fmt(row.entregas_en_turno)} solicitudes entregadas dentro del turno</p>
    </div>
  );
}

export default function SimulationPage() {
  // Opciones avanzadas: duración del turno, demanda y regla de atención.
  const [turnoMinutos, setTurnoMinutos] = useState(480);
  const [rule,setRule]=useState('auto');
  const [history, setHistory] = useState([]);
  const [solicitudes, setSolicitudes] = useState(50);
  const [montacargas, setMontacargas] = useState(2);
  const [operadores, setOperadores] = useState(3);
  const [demanda, setDemanda] = useState("normal");
  const [result, setResult] = useState(null);
  const [comparison, setComparison] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  useEffect(()=>{api('/api/simulations').then(setHistory).catch(e=>setError(e.message));},[]);

  // Construye los datos que recibe FastAPI. La semilla fija permite comparar
  // escenarios con las mismas llegadas y tiempos; se promedian 10 ejecuciones.
  const params = {
    ...DEFAULTS,
    turno_minutos: turnoMinutos,
    solicitudes,
    montacargas,
    operadores,
    porcentaje_urgentes: demanda === "urgente" ? 25 : 0,
    prioridad: rule === 'auto' ? (demanda === "urgente" ? "urgentes" : "llegada") : rule,
  };

  // Envía el escenario a SimPy a través de la API y actualiza el historial.
  // Las cookies identifican al usuario que guarda la simulación.
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

  // Ejecuta un escenario o compara varios, conservando el resto de parámetros.
  // Primero valida las cantidades y después bloquea los botones durante el cálculo.
  async function run(compare = false) {
    if (!Number.isInteger(turnoMinutos) || turnoMinutos < 60 || turnoMinutos > 1440) {
      setError("El turno debe durar entre 60 y 1440 minutos, sin decimales.");
      return;
    }
    if (![[solicitudes, 1000], [montacargas, 30], [operadores, 30]].every(([n, max]) => Number.isInteger(n) && n >= 1 && n <= max)) {
      setError("Ingresa entre 1 y 1000 solicitudes, y entre 1 y 30 montacargas y operadores, sin decimales.");
      return;
    }
    setLoading(true);
    setError("");
    setResult(null);
    setComparison([]);
    try {
      if (compare === 'rules') {
        // Compara las dos reglas con la misma demanda y los mismos recursos.
        const responses=await Promise.all(['llegada','urgentes'].map(prioridad=>post({...params,prioridad})));
        setComparison(responses.map((response,index)=>({label:index===0?'Orden de llegada':'Urgentes primero',...response.resumen})));
      } else if (compare) {
        // Solo varía el número de montacargas; los operadores no cambian.
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
        <p className="mt-2 text-sm text-slate-500">¿Cómo cambia la entrega de acero si aumentamos los montacargas o los operadores?</p>
      </div>

      <div className="grid gap-5 xl:grid-cols-[380px_1fr]">
        <section className="space-y-4 rounded-2xl bg-white p-5 shadow-sm">
          <h2 className="font-bold text-slate-900">1. Elige la carga de trabajo y los recursos</h2>

          <div className="grid gap-3">
            {[
              ["Solicitudes durante el turno", solicitudes, setSolicitudes, 1000],
              ["Montacargas disponibles", montacargas, setMontacargas, 30],
              ["Operadores disponibles", operadores, setOperadores, 30],
            ].map(([label, value, setter, max]) => (
              <label key={label} className="space-y-1 text-xs font-semibold text-slate-600">
                <span>{label}</span>
                <input
                  type="number"
                  min="1"
                  max={max}
                  disabled={loading}
                  step="1"
                  value={value}
                  onChange={(event) => setter(Number(event.target.value))}
                  className="w-full rounded-lg border border-slate-200 p-2.5 text-sm text-slate-900"
                />
              </label>
            ))}

          </div>


          <p className="rounded-xl bg-slate-50 p-3 text-xs text-slate-500">
            Turno de {params.turno_minutos} min. Preparación: {params.preparacion_min}–{params.preparacion_max} min; traslado: {params.traslado_min}–{params.traslado_max} min.
            {params.porcentaje_urgentes > 0 ? " El 25% de las solicitudes será urgente." : " Sin solicitudes urgentes."}
            {params.prioridad === "urgentes" ? " Se atienden primero las urgentes." : " Se atiende por orden de llegada."}
            {" Se repite 10 veces y se muestra el promedio. Son escenarios simulados."}
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
          <details className="space-y-3 rounded-xl border border-slate-200 p-3"><summary className="cursor-pointer text-sm font-semibold">Opciones avanzadas (opcional)</summary>
            <label className="space-y-1 text-xs font-semibold text-slate-600">
              <span>Tipo de demanda</span>
              <select
                disabled={loading}
                value={demanda}
                onChange={(event) => setDemanda(event.target.value)}
                className="w-full rounded-lg border border-slate-200 bg-white p-2.5 text-sm text-slate-900"
              >
                <option value="normal">Normal</option>
                <option value="urgente">Con urgencias</option>
              </select>
            </label>
            <label className="block text-xs font-semibold text-slate-600">Duración del turno (min)
              <input type="number" min="60" max="1440" step="1" disabled={loading} value={turnoMinutos} onChange={e=>setTurnoMinutos(Number(e.target.value))} className="mt-1 w-full rounded-lg border p-2"/>
            </label>
            <label className="block text-xs">Regla de atención<select disabled={loading} value={rule} onChange={e=>setRule(e.target.value)} className="mt-1 w-full rounded-lg border p-2"><option value="auto">Según tipo de demanda</option><option value="llegada">Orden de llegada</option><option value="urgentes">Urgentes primero</option></select></label>
            <button type="button" disabled={loading || params.porcentaje_urgentes === 0} onClick={()=>run('rules')} className="w-full rounded-xl border border-blue-200 p-3 font-semibold text-blue-700 disabled:opacity-50">Comparar orden de llegada y urgentes primero</button>
            <p className="text-xs text-slate-500">Selecciona demanda con urgencias para comparar las reglas de atención.</p>
          </details>
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
              <h2 className="font-bold text-slate-900">2. Ejecuta y observa qué cambia</h2>
              <p className="mt-2 text-sm">Empieza con 50 solicitudes, 2 montacargas y 3 operadores. Después compara de 1 a 4 montacargas para ver cómo cambia la espera.</p>
              <p className="mt-3 text-xs">Cada solicitud pasa por preparación y traslado antes de entregarse.</p>
            </div>
          )}

          {summary && (
            <>
              <h2 className="font-bold text-slate-900">2. Revisa los resultados</h2>
              <div className="grid gap-3 sm:grid-cols-2">
                <MetricCard icon={Clock3} label="Tiempo promedio de entrega" value={`${fmt(summary.tiempo_total_promedio)} min`} description="Desde la solicitud hasta la entrega" />
                <MetricCard icon={Timer} label="Tiempo promedio de espera" value={`${fmt(summary.espera_promedio)} min`} description="Tiempo esperando recursos disponibles" />
                <MetricCard icon={CheckCircle2} label="Entregas dentro del turno" value={fmt(summary.entregas_en_turno)} description={`De ${result.parametros.solicitudes} solicitudes en un turno de ${fmt(result.parametros.turno_minutos / 60)} horas; promedio de 10 ejecuciones`} />
              </div>
              <p className="text-xs text-slate-500">Los resultados corresponden al escenario simulado.</p>
            </>
          )}

          {comparison.length > 0 && (
            <div className="space-y-4 rounded-2xl bg-white p-5 shadow-sm">
              <h2 className="font-bold text-slate-900">2. Compara el tiempo de espera</h2>
              <p className="text-sm text-slate-600">Una barra más corta significa menos tiempo esperando recursos.</p>
              <p className="text-xs text-slate-500">Se usan las mismas llegadas y duraciones pseudoaleatorias; cambia únicamente el recurso o la regla elegida.</p>
              {comparison.map((row) => <ComparisonBar key={row.label || row.montacargas} row={row} max={maxWait} />)}
            </div>
          )}

          {history.length>0 && <details className="rounded-2xl bg-white p-5 shadow-sm"><summary className="cursor-pointer text-sm font-semibold">Ver simulaciones anteriores</summary>{history.slice(0,10).map(h=><p key={h.id} className="border-t py-2 text-xs text-slate-600">{new Date(h.created_at+'Z').toLocaleString('es-MX')} · {h.parameters.solicitudes} solicitudes · {h.parameters.montacargas} montacargas · {fmt(h.summary.espera_promedio)} min de espera</p>)}</details>}
        </section>
      </div>
    </div>
  );
}
