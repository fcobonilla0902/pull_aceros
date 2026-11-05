import React, { useState } from "react";
import { Play, BarChart3, AlertTriangle, LoaderCircle, Truck, Clock3, CheckCircle2, Timer } from "lucide-react";

const API = import.meta.env.VITE_SIM_API || "http://127.0.0.1:8000";

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
        <span className="font-semibold text-slate-700">{row.montacargas} montacargas</span>
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
  const [solicitudes, setSolicitudes] = useState(50);
  const [montacargas, setMontacargas] = useState(2);
  const [operadores, setOperadores] = useState(3);
  const [demanda, setDemanda] = useState("normal");
  const [result, setResult] = useState(null);
  const [comparison, setComparison] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const params = {
    ...DEFAULTS,
    solicitudes,
    montacargas,
    operadores,
    porcentaje_urgentes: demanda === "urgente" ? 25 : 0,
    prioridad: demanda === "urgente" ? "urgentes" : "llegada",
  };

  async function post(payload) {
    const response = await fetch(`${API}/simular`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(typeof body.detail === "string" ? body.detail : `Error HTTP ${response.status}`);
    }
    return response.json();
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
      if (compare) {
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

          <p className="rounded-xl bg-slate-50 p-3 text-xs text-slate-500">
            Simulación de un turno de 8 horas. Preparación: 5–12 min; traslado: 8–20 min.
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
                <MetricCard icon={CheckCircle2} label="Entregas dentro del turno" value={fmt(summary.entregas_en_turno)} description="Solicitudes completadas en 8 horas (promedio de réplicas)" />
                <MetricCard icon={BarChart3} label="Cumplimiento del turno" value={`${fmt(summary.porcentaje_en_turno)}%`} description="Porcentaje completado antes de finalizar el turno" />
              </div>
            </>
          )}

          {comparison.length > 0 && (
            <div className="space-y-4 rounded-2xl bg-white p-5 shadow-sm">
              <h2 className="font-bold text-slate-900">Comparación de montacargas</h2>
              <p className="text-xs text-slate-500">Se mantienen las mismas solicitudes y operadores; solo cambia la cantidad de montacargas.</p>
              {comparison.map((row) => <ComparisonBar key={row.montacargas} row={row} max={maxWait} />)}
            </div>
          )}

          <p className="text-xs text-slate-500">
            Modelo académico con datos hipotéticos. Los resultados se calculan con SimPy y pueden variar entre escenarios.
            Se usan 10 réplicas con semilla base 42; las solicitudes pueden terminar después del turno.
          </p>
        </section>
      </div>
    </div>
  );
}
