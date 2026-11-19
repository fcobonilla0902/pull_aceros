import { useEffect, useState } from "react";
import { Play, BarChart3, AlertTriangle, LoaderCircle, Truck, Clock3, CheckCircle2, Timer } from "lucide-react";

import { api } from "./api";
import { Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

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

const PRIORITIES = [
  { key: 'urgente', name: 'Urgente', color: 'var(--simulation-priority-urgent)' },
  { key: 'alta', name: 'Alta', color: 'var(--simulation-priority-high)' },
  { key: 'normal', name: 'Normal', color: 'var(--simulation-priority-normal)' },
];

function PriorityDonut({ row }) {
  const data = PRIORITIES.map(priority => ({ ...priority, ...row.por_prioridad?.[priority.key] }));
  const measured = data.filter(item => item.solicitudes > 0);
  return <article className="min-w-0 rounded-xl border border-slate-200 p-4">
    <h3 className="text-sm font-bold text-slate-900">{row.montacargas} montacargas</h3>
    <div className="h-48 min-w-0" role="img" aria-label={`Tiempo promedio de entrega por prioridad con ${row.montacargas} montacargas. ${data.map(item => `${item.name}: ${item.solicitudes ? `${fmt(item.tiempo_total_promedio)} minutos` : 'sin solicitudes'}`).join('. ')}`}>
      {measured.length ? <ResponsiveContainer width="100%" height="100%" minWidth={0}><PieChart>
        <Pie data={measured} dataKey="tiempo_total_promedio" nameKey="name" innerRadius={50} outerRadius={72} paddingAngle={3} strokeWidth={0} isAnimationActive={false}>
          {measured.map(item => <Cell key={item.key} fill={item.color} />)}
        </Pie>
        <Tooltip formatter={value => [`${fmt(value)} min`, 'Entrega promedio']} />
        <text x="50%" y="48%" textAnchor="middle" dominantBaseline="central" fontSize={20} fontWeight={700} fill="var(--simulation-chart-text)">{fmt(row.tiempo_total_promedio)}</text>
        <text x="50%" y="60%" textAnchor="middle" fontSize={10} fill="var(--simulation-chart-caption)">min · promedio global</text>
      </PieChart></ResponsiveContainer> : <p className="pt-16 text-center text-xs text-slate-500">Sin solicitudes para calcular tiempos.</p>}
    </div>
    <ul className="space-y-2">{data.map(item => <li key={item.key} className="flex items-center gap-2 text-xs">
      <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: item.color }} />
      <span className="flex-1 text-slate-600">{item.name}</span>
      <strong className="text-slate-900">{item.solicitudes ? `${fmt(item.tiempo_total_promedio)} min` : 'Sin solicitudes'}</strong>
    </li>)}</ul>
  </article>;
}

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

const chartCard = "min-w-0 rounded-2xl bg-white p-5 shadow-sm";
const axisTick = { fontSize: 11, fill: "var(--simulation-chart-ticks)" };
const replicaLabel = (value) => `Ejecución ${value}`;

function TimeChart({ runs, metric, title, average, color }) {
  return <figure className={chartCard}>
    <figcaption className="font-bold text-slate-900">{title}</figcaption>
    <p className="mt-1 text-xs text-slate-600">Línea punteada · promedio general de {fmt(average)} min</p>
    <div className="mt-3 h-56 min-w-0">
      <ResponsiveContainer width="100%" height="100%" minWidth={0}>
        <LineChart data={runs} margin={{ top: 8, right: 12, bottom: 6, left: 0 }}>
          <CartesianGrid stroke="var(--chart-grid)" vertical={false} />
          <XAxis dataKey="replica" tick={axisTick} tickLine={false} />
          <YAxis width={56} unit=" min" tick={axisTick} tickLine={false} />
          <Tooltip labelFormatter={replicaLabel} formatter={value => [`${fmt(value)} min`, 'Promedio de la ejecución']} />
          <ReferenceLine y={average} stroke={color} strokeDasharray="5 4" />
          <Line name={title} dataKey={metric} stroke={color} strokeWidth={2} dot={{ r: 3 }} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  </figure>;
}

function SimulationCharts({ result }) {
  const { corridas, resumen, parametros } = result;
  const deliveries = corridas.map(run => ({
    ...run,
    entregas_despues: parametros.solicitudes - run.entregas_en_turno,
  }));

  return <section className="grid min-w-0 gap-4 sm:grid-cols-2" aria-label="Gráficas de la simulación por ejecución">
    <TimeChart runs={corridas} metric="tiempo_total_promedio" title="Tiempo promedio de entrega" average={resumen.tiempo_total_promedio} color="var(--simulation-delivery-time)" />
    <TimeChart runs={corridas} metric="espera_promedio" title="Tiempo promedio de espera" average={resumen.espera_promedio} color="var(--simulation-wait-time)" />
    <figure className={`${chartCard} sm:col-span-2`}>
      <figcaption className="font-bold text-slate-900">Entregas dentro del turno</figcaption>
      <p className="mt-1 text-xs text-slate-600">En promedio, el {fmt(resumen.porcentaje_en_turno)}% de las solicitudes se entregó dentro del turno.</p>
      <div className="mt-3 h-64 min-w-0">
        <ResponsiveContainer width="100%" height="100%" minWidth={0}>
          <BarChart data={deliveries} margin={{ top: 8, right: 12, bottom: 6, left: 0 }}>
            <CartesianGrid stroke="var(--chart-grid)" vertical={false} />
            <XAxis dataKey="replica" tick={axisTick} tickLine={false} />
            <YAxis width={48} allowDecimals={false} domain={[0, parametros.solicitudes]} tick={axisTick} tickLine={false} />
            <Tooltip labelFormatter={replicaLabel} formatter={(value, name) => [`${fmt(value)} solicitudes`, name]} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Bar name="Dentro del turno" dataKey="entregas_en_turno" stackId="deliveries" fill="var(--simulation-in-shift)" maxBarSize={40} isAnimationActive={false} />
            <Bar name="Después del turno" dataKey="entregas_despues" stackId="deliveries" fill="var(--simulation-after-shift)" maxBarSize={40} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </figure>
    <p className="text-xs text-slate-500 sm:col-span-2">El eje horizontal indica el número de ejecución. Selecciona un punto o una barra para consultar sus valores.</p>
  </section>;
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
  const [demanda, setDemanda] = useState("urgente");
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
    porcentaje_altas: demanda === "urgente" ? 25 : 0,
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
          por_prioridad: response.por_prioridad,
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
            {params.porcentaje_urgentes > 0 ? " Mezcla esperada: 25% urgente, 25% alta y 50% normal." : " Todas las solicitudes son normales."}
            {params.prioridad === "urgentes" ? " Se atienden primero urgentes, después altas y normales." : " Se atiende por orden de llegada."}
            {" Se repite 10 veces y se muestra el promedio. Son escenarios simulados."}
          </p>

          <button
            type="button"
            disabled={loading}
            onClick={() => run(false)}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-[var(--simulation-run-button)] p-3 font-bold text-white hover:bg-[var(--simulation-run-button-hover)] disabled:opacity-60"
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
                <option value="urgente">Urgentes, altas y normales</option>
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

          <section className="min-w-0 space-y-4">
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
                <MetricCard icon={CheckCircle2} label="Entregas dentro del turno" value={fmt(summary.entregas_en_turno)} description={`De ${result.parametros.solicitudes} solicitudes por turno de ${fmt(result.parametros.turno_minutos / 60)} horas, en promedio`} />
              </div>
              <SimulationCharts result={result} />
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

          {comparison.some(row => row.por_prioridad) && <section className="min-w-0 space-y-4 rounded-2xl bg-white p-5 shadow-sm">
            <h2 className="font-bold text-slate-900">Tiempo de entrega por prioridad</h2>
            <p className="text-sm text-slate-600">Tiempo promedio desde la solicitud hasta la entrega, incluyendo espera y servicio, para cada cantidad de montacargas. Los operadores se mantienen fijos.</p>
            <div className="grid min-w-0 gap-4 sm:grid-cols-2">{comparison.map(row => <PriorityDonut key={row.montacargas} row={row} />)}</div>
            <p className="text-xs text-slate-500">Cada segmento representa los minutos promedio de su prioridad; no representa el porcentaje de pedidos. El centro muestra el promedio global ponderado por solicitudes. Se incluyen todas las solicitudes de las 10 ejecuciones, incluso las entregadas después del turno. Una prioridad sin solicitudes se indica sin asignarle un tiempo.</p>
          </section>}

          {history.length>0 && <details className="rounded-2xl bg-white p-5 shadow-sm"><summary className="cursor-pointer text-sm font-semibold">Ver simulaciones anteriores</summary>{history.slice(0,10).map(h=><p key={h.id} className="border-t py-2 text-xs text-slate-600">{new Date(h.created_at+'Z').toLocaleString('es-MX')} · {h.parameters.solicitudes} solicitudes · {h.parameters.montacargas} montacargas · {fmt(h.summary.espera_promedio)} min de espera</p>)}</details>}
        </section>
      </div>
    </div>
  );
}
