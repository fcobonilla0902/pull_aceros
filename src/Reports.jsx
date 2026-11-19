import { formatDuration } from './lib/time';
import { lazy, Suspense, useState } from 'react';
import { AlertTriangle, ArrowRight, CheckCheck, ClipboardList, Clock3, Download, Filter, RefreshCw, Siren, Users } from 'lucide-react';
import { api, API } from './api';
const DashboardCharts = lazy(() => import('./DashboardCharts'));
const panel = 'rounded-2xl border border-slate-200/70 bg-white p-5 shadow-sm';
const control = 'inline-flex h-11 items-center justify-center gap-2 rounded-xl px-4 text-sm font-semibold transition disabled:opacity-50';
const groups = [
  { id: 'pendientes', label: 'Por validar', states: ['Solicitado'], color: 'var(--status-pending)' },
  { id: 'validadas', label: 'Validadas', states: ['Validado'], color: 'var(--status-validated)' },
  { id: 'preparacion', label: 'En preparación', states: ['Tomado', 'En preparación'], color: 'var(--status-preparing)' },
  { id: 'listas', label: 'Listas para traslado', states: ['Listo para traslado'], color: 'var(--status-ready)' },
  { id: 'traslado', label: 'En traslado / parcial', states: ['En traslado', 'Entrega parcial'], color: 'var(--status-in-transit)' },
  { id: 'incidencias', label: 'Con incidencia', states: ['Con incidencia'], color: 'var(--status-incident)' },
  { id: 'entregadas', label: 'Entregadas', states: ['Entregado'], color: 'var(--status-delivered)' },
  { id: 'canceladas', label: 'Canceladas', states: ['Cancelado'], color: 'var(--status-cancelled)' },
];
const closed = r => ['Entregado', 'Cancelado'].includes(r.state);
const number = value => Number(value || 0).toLocaleString('es-MX', { maximumFractionDigits: 1 });
function dateInPlant(value, timezone) {
  const parts = new Intl.DateTimeFormat('en-CA', { timeZone: timezone, year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date(value + 'Z'));
  return ['year', 'month', 'day'].map(name => parts.find(p => p.type === name).value).join('-');
}
function Metric({ icon: Icon, label, value, detail, tone }) {
  const tones = { blue: 'bg-blue-50 text-blue-700', red: 'bg-red-50 text-red-600', green: 'bg-emerald-50 text-emerald-700', cyan: 'bg-cyan-50 text-cyan-700' };
  return <article className={panel}>
    <div className="flex items-center justify-between gap-3"><p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p><span className={`rounded-xl p-2.5 ${tones[tone]}`}><Icon size={19}/></span></div>
    <p className="mt-3 text-3xl font-bold tracking-tight text-slate-900">{value}</p><p className="mt-2 text-xs text-slate-500">{detail}</p>
  </article>;
}

export default function Reports({ data, onOpenRequest, onNavigate }) {
  const [report, setReport] = useState(null);
  const [period, setPeriod] = useState('');
  const [reportAt, setReportAt] = useState(null);
  const [reportRequests, setReportRequests] = useState([]);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [focus, setFocus] = useState(null);
  const m = report || data.metrics;
  const query = new URLSearchParams(period);
  const start = query.get('start');
  const end = query.get('end');
  const requests = (report ? reportRequests : data.requests).filter(r => {
    const day = dateInPlant(r.created_at, m.timezone);
    return (!start || day >= start) && (!end || day <= end);
  });
  const distribution = groups.map(g => ({ ...g, total: requests.filter(r => g.states.includes(r.state)).length }));
  const max = Math.max(1, ...distribution.map(g => g.total));
  const selected = groups.find(g => g.id === focus);
  const urgent = requests.filter(r => selected ? selected.states.includes(r.state) : !closed(r) && (r.priority === 'Urgente' || r.remaining_minutes <= m.soon_threshold_minutes))
    .sort((a, b) => Number(closed(a)) - Number(closed(b)) || Number(b.priority === 'Urgente') - Number(a.priority === 'Urgente') || new Date(a.required_at + 'Z') - new Date(b.required_at + 'Z'));
  async function filter(e) {
    e.preventDefault(); setBusy(true); setError('');
    const values = Object.fromEntries(new FormData(e.currentTarget));
    const nextQuery = new URLSearchParams(Object.entries(values).filter(([, v]) => v)).toString();
    try { setReport(await api(`/api/metrics?${nextQuery}`)); setReportRequests(data.requests); setPeriod(nextQuery); setReportAt(Date.now()); setFocus(null); }
    catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  return <div className="space-y-5" data-testid="operational-dashboard">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <p className="text-sm text-slate-500">Dashboard de surtimiento · {m.current_shift.date} · {m.current_shift.shift}</p>
      <span className="inline-flex items-center gap-2 text-xs text-slate-500"><span className="h-2 w-2 rounded-full bg-emerald-500"/>{report ? 'Consulta por periodo' : 'Actualización cada 30 s'} · {new Date(reportAt || data.updatedAt).toLocaleTimeString('es-MX', { timeZone: m.timezone, hour: '2-digit', minute: '2-digit' })}</span>
    </div>
    <form className={`${panel} grid items-end gap-3 xl:grid-cols-[minmax(0,1fr)_auto]`} onSubmit={filter} aria-label="Filtros del dashboard">
      <div className="grid items-end gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto_auto]">
        <label className="min-w-0 text-xs font-semibold text-slate-500">Desde<input aria-label="Desde" name="start" type="date" className="mt-1.5 block h-11 w-full min-w-0 rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-800"/></label>
        <label className="min-w-0 text-xs font-semibold text-slate-500">Hasta<input aria-label="Hasta" name="end" type="date" className="mt-1.5 block h-11 w-full min-w-0 rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-800"/></label>
        <button data-testid="dashboard-filter" disabled={busy} className={`${control} bg-[var(--dashboard-filter-button)] text-white hover:bg-[var(--dashboard-filter-button-hover)]`}><Filter size={16}/>{busy ? 'Consultando…' : 'Consultar periodo'}</button>
        <button type="reset" disabled={busy} onClick={() => { setReport(null); setPeriod(''); setReportAt(null); setFocus(null); setError(''); }} className={`${control} border border-slate-200 bg-white text-slate-600 hover:bg-slate-50`}><RefreshCw size={16}/>Ver todo</button>
      </div>
      <a data-testid="dashboard-export" className={`${control} border border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100`} href={`${API}/api/metrics/export${period ? '?' + period : ''}`}><Download size={16}/>Exportar indicadores CSV</a>
    </form>
    {error && <p role="alert" className="rounded-xl bg-red-50 p-3 text-sm text-red-700">{error}</p>}
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <Metric icon={ClipboardList} label="Solicitudes activas" value={number(m.active)} detail={`${number(m.pending_rolls)} rollos pendientes de entrega`} tone="blue"/>
      <Metric icon={AlertTriangle} label="Vencidas" value={number(m.overdue)} detail={`${number(m.due_soon)} próximas a vencer en ${m.soon_threshold_minutes} min`} tone="red"/>
      <Metric icon={CheckCheck} label="Entregas a tiempo" value={m.on_time_percent == null ? '—' : `${number(m.on_time_percent)}%`} detail={`${number(m.delivered)} ${m.delivered === 1 ? 'solicitud entregada' : 'solicitudes entregadas'} · ${report ? 'cohorte seleccionada' : 'acumulado'}`} tone="green"/>
      <Metric icon={Clock3} label="Promedio de surtimiento" value={m.average_minutes == null ? '—' : `${number(m.average_minutes)} min`} detail="Desde la solicitud hasta la entrega completa" tone="cyan"/>
    </div>
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {[[Siren, 'Urgentes activas', m.urgent, 'text-orange-600', 'kanban'], [AlertTriangle, 'Incidencias abiertas', m.incidents, 'text-red-600', 'kanban'], [Clock3, 'Paros abiertos', m.open_stops, 'text-rose-600', 'kanban'], [Users, 'Recepciones de turno pendientes', m.awaiting_handover_acceptance, 'text-violet-600', 'turno']].map(([Icon, label, value, color, page]) => <button key={label} onClick={() => onNavigate(page)} className="flex min-w-0 items-center gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 text-left transition hover:border-blue-300 hover:bg-blue-50/40"><Icon size={18} className={`shrink-0 ${color}`}/><span className="min-w-0 flex-1 text-xs text-slate-600">{label}</span><b className="text-lg text-slate-900">{number(value)}</b><ArrowRight size={14} className="shrink-0 text-slate-400"/></button>)}
    </div>
    <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
      <section className={panel} aria-label="Distribución de solicitudes">
        <div className="flex items-center justify-between gap-3"><h2 className="font-bold text-slate-900">Estado de solicitudes</h2><span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-600">{number(requests.length)} {requests.length === 1 ? 'folio' : 'folios'}</span></div>
        <p className="mt-1 text-xs text-slate-500">Selecciona una etapa para consultar sus solicitudes.</p>
        <div className="mt-4 space-y-1">{distribution.map(g => <button key={g.id} aria-pressed={focus === g.id} onClick={() => setFocus(focus === g.id ? null : g.id)} className={`grid w-full grid-cols-[120px_minmax(0,1fr)_28px] items-center gap-3 rounded-lg px-2 py-2 text-left text-xs transition sm:grid-cols-[140px_minmax(0,1fr)_28px] ${focus === g.id ? 'bg-blue-50 ring-1 ring-blue-200' : 'hover:bg-slate-50'}`}><span className="text-slate-600">{g.label}</span><span className="h-2.5 overflow-hidden rounded-full bg-slate-100"><span className="block h-full rounded-full transition-all" style={{ width: `${g.total / max * 100}%`, backgroundColor: g.color }}/></span><b className="text-right text-slate-800">{g.total}</b></button>)}</div>
        {!requests.length && <p className="mt-3 text-xs text-slate-500">Sin solicitudes para este periodo.</p>}
      </section>
      <section className={panel}>
        <div className="flex flex-wrap items-center justify-between gap-2"><h2 className="font-bold text-slate-900">{selected ? `Solicitudes · ${selected.label}` : 'Atención prioritaria'}</h2>{selected ? <button onClick={() => setFocus(null)} className="text-xs font-semibold text-blue-700">Ver prioridades</button> : <span className="rounded-full bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-700">{urgent.length} por atender</span>}</div>
        <div className="mt-4 space-y-2">{urgent.slice(0, 5).map(r => <button key={r.id} onClick={() => onOpenRequest(r)} className="flex w-full items-center gap-3 rounded-xl border border-slate-100 p-3 text-left transition hover:border-blue-200 hover:bg-blue-50/40"><span className={`h-9 w-1 shrink-0 rounded-full ${r.remaining_minutes < 0 && !closed(r) ? 'bg-red-400' : r.priority === 'Urgente' ? 'bg-orange-400' : 'bg-blue-400'}`}/><span className="min-w-0 flex-1"><span className="block truncate text-sm font-semibold text-slate-800">{r.folio} · {r.enn}</span><span className="mt-1 block truncate text-xs text-slate-500">{r.state} · {r.owner}</span></span><span className={`text-right text-xs font-semibold ${r.remaining_minutes < 0 && !closed(r) ? 'text-red-600' : 'text-slate-600'}`}>{closed(r) ? r.state : r.remaining_minutes < 0 ? `${formatDuration(r.remaining_minutes)} de retraso` : `Vence en ${formatDuration(r.remaining_minutes)}`}</span><ArrowRight size={14} className="shrink-0 text-slate-400"/></button>)}</div>
        {!urgent.length && <div className="flex min-h-44 flex-col items-center justify-center gap-3 text-center"><span className="rounded-full bg-emerald-50 p-3 text-emerald-600"><CheckCheck size={24}/></span><p className="text-sm font-semibold text-slate-600">{selected ? 'Sin solicitudes en esta etapa' : 'Sin solicitudes críticas por atender'}</p><p className="max-w-xs text-xs text-slate-400">{selected ? 'Selecciona otra etapa para ver su seguimiento.' : 'Las urgencias y los próximos vencimientos aparecerán aquí.'}</p></div>}
        <button onClick={() => onNavigate('kanban')} className="mt-4 inline-flex items-center gap-2 text-xs font-semibold text-blue-700 hover:underline">Abrir Panel Kanban<ArrowRight size={14}/></button>
      </section>
    </div>
    <Suspense fallback={<div className={`${panel} text-sm text-slate-500`}>Cargando gráficos del proceso…</div>}><DashboardCharts metrics={m}/></Suspense>
    <p className="text-xs leading-relaxed text-slate-400">Zona de planta: {m.timezone}. {m.cohort_note} {report ? 'El reporte corresponde a las fechas aplicadas; vuelve a consultar para actualizarlo.' : 'Indicadores acumulados de la operación.'}</p>
  </div>;
}
