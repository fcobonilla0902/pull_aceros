import { useState } from 'react';
import { Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
const panel = 'min-w-0 rounded-2xl border border-slate-200/70 bg-white p-5 shadow-sm';
const colors = ['#2558d9', '#0891b2', '#8b5cf6', '#f59e0b', '#ef4444', '#64748b', '#10b981'];
const fmt = value => Number(value || 0).toLocaleString('es-MX', { maximumFractionDigits: 1 });
export default function DashboardCharts({ metrics: m }) {
  const [shift, setShift] = useState('Todos');
  const movements = m.movements_by_shift.filter(r => shift === 'Todos' || r.shift === shift);
  const byDate = movements.reduce((result, r) => {
    const row = result[r.date] ||= { date: r.date, label: `${r.date.slice(8, 10)}/${r.date.slice(5, 7)}`, T1: 0, T2: 0, T3: 0 };
    row[r.shift] += r.movements;
    return result;
  }, {});
  const chartRows = Object.values(byDate).sort((a, b) => a.date.localeCompare(b.date)).slice(-7);
  const causes = m.delay_causes;
  const total = causes.reduce((sum, r) => sum + r.count, 0);
  return <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
    <section className={panel}>
      <div className="flex flex-wrap items-center justify-between gap-3"><h2 className="font-bold text-slate-900">Movimientos por turno</h2><label className="text-xs text-slate-500"><span className="sr-only">Filtrar gráfico por turno</span><select aria-label="Filtrar gráfico por turno" value={shift} onChange={e => setShift(e.target.value)} className="h-9 rounded-lg border border-slate-200 bg-white px-2 text-xs text-slate-600"><option value="Todos">Todos los turnos</option><option>T1</option><option>T2</option><option>T3</option></select></label></div>
      <p className="mt-1 text-xs text-slate-500">Últimas siete fechas con movimientos del periodo.</p>
      {chartRows.length ? <div className="mt-5 h-60 min-w-0" role="img" aria-label="Comparación de movimientos por fecha y turno"><ResponsiveContainer width="100%" height="100%" minWidth={0}><BarChart data={chartRows} margin={{ top: 8, right: 0, left: -24, bottom: 0 }} barGap={3}><CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" vertical={false}/><XAxis dataKey="label" axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: '#94a3b8' }} dy={8}/><YAxis allowDecimals={false} axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: '#94a3b8' }}/><Tooltip labelFormatter={(_, payload) => payload?.[0]?.payload.date || ''} formatter={(value, name) => [`${value} movimientos`, name]} contentStyle={{ borderRadius: 12, borderColor: '#e2e8f0', fontSize: 12 }}/><Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 11, paddingTop: 16 }}/>{['T1', 'T2', 'T3'].filter(s => shift === 'Todos' || s === shift).map(s => <Bar key={s} isAnimationActive={false} name={s} dataKey={s} fill={colors[['T1', 'T2', 'T3'].indexOf(s)]} radius={[4, 4, 0, 0]} maxBarSize={28}/>)}</BarChart></ResponsiveContainer></div> : <div className="flex h-60 items-center justify-center rounded-xl bg-slate-50 text-sm text-slate-400">Sin entregas en este periodo o turno.</div>}
      <details className="mt-4 border-t border-slate-100 pt-3"><summary className="cursor-pointer text-xs font-semibold text-blue-700">Ver detalle de movimientos</summary><div className="mt-3 overflow-x-auto"><table className="w-full text-left text-xs"><thead className="text-slate-400"><tr><th className="pb-2 pr-3">Fecha</th><th className="pb-2 pr-3">Turno</th><th className="pb-2 pr-3">Movimientos</th><th className="pb-2">Solicitudes</th></tr></thead><tbody>{movements.map(r => <tr key={`${r.date}-${r.shift}`} className="border-t border-slate-100"><td className="py-2 pr-3">{r.date}</td><td>{r.shift}</td><td>{r.movements}</td><td>{r.requests}</td></tr>)}</tbody></table></div></details>
      <p className="mt-3 text-xs text-slate-400">Cada entrega, incluida una parcial, cuenta como movimiento. T1 06:00 · T2 14:00 · T3 21:30.</p>
    </section>
    <section className={panel}>
      <h2 className="font-bold text-slate-900">Causas de retraso reportadas</h2><p className="mt-1 text-xs text-slate-500">Distribución de las incidencias registradas.</p>
      {total ? <><div className="mt-2 h-48 min-w-0" role="img" aria-label={`Distribución de ${total} incidencias por causa`}><ResponsiveContainer width="100%" height="100%" minWidth={0}><PieChart><Pie isAnimationActive={false} data={causes} nameKey="cause" dataKey="count" innerRadius={54} outerRadius={76} paddingAngle={total > 1 ? 3 : 0} strokeWidth={0}>{causes.map((c, i) => <Cell key={c.cause} fill={colors[i % colors.length]}/>)}</Pie><Tooltip formatter={value => [`${value} incidencias`, 'Cantidad']} contentStyle={{ borderRadius: 12, borderColor: '#e2e8f0', fontSize: 12 }}/><text x="50%" y="47%" textAnchor="middle" dominantBaseline="central" fill="#17243a" fontSize={26} fontWeight={700}>{total}</text><text x="50%" y="61%" textAnchor="middle" fill="#94a3b8" fontSize={11}>{total === 1 ? 'incidencia' : 'incidencias'}</text></PieChart></ResponsiveContainer></div><div className="space-y-2">{causes.map((c, i) => <div key={c.cause} className="flex items-center gap-2 text-xs"><span className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: colors[i % colors.length] }}/><span className="min-w-0 flex-1 text-slate-500">{c.cause}</span><b className="text-slate-800">{c.count}</b><span className="w-10 text-right text-slate-400">{fmt(c.count / total * 100)}%</span></div>)}</div></> : <div className="flex h-48 items-center justify-center rounded-xl bg-slate-50 text-sm text-slate-400">Sin incidencias en este periodo.</div>}
      <div className="mt-4 grid grid-cols-2 gap-3 border-t border-slate-100 pt-4"><div><p className="text-xs text-slate-400">Paros reportados</p><p className="mt-1 text-xl font-bold text-slate-800">{m.production_stops}</p></div><div><p className="text-xs text-slate-400">Tiempo en incidencias con paro</p><p className="mt-1 text-xl font-bold text-slate-800">{fmt(m.downtime_minutes)} <span className="text-xs font-normal text-slate-400">min</span></p></div></div>
    </section>
  </div>;
}
