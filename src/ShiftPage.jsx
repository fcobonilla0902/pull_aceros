import { useState } from 'react';
import { post } from './api';

const panel = 'space-y-4 rounded-2xl bg-white p-5 shadow-sm';
const input = 'w-full rounded-xl border border-slate-200 p-3 text-sm';
const button = 'rounded-xl bg-blue-600 px-4 py-3 text-sm font-semibold text-white disabled:opacity-50';
const local = value => value ? new Date(value + 'Z').toLocaleString('es-MX') : '—';

function Pending({ request, current }) {
  return <div className="space-y-2 rounded-xl border border-slate-200 p-4 text-sm">
    <p className="font-bold">{request.folio} · {request.enn} · {request.state}</p>
    <p>{request.priority} · {request.risk} · Responsable: {request.owner}</p>
    <p>Requerido: {local(request.required_at)} · Última actualización: {local(request.updated_at)}</p>
    <p>Destino: {request.destination || request.enn}</p>
    <p>{request.items.map(i => `${i.part}: ${i.requested - i.delivered} pendientes`).join(' · ')}</p>
    <p>{request.rolls.length ? request.rolls.map(r => `${r.code}: ${r.location} (${r.status})`).join(' · ') : 'Rollos pendientes de localizar / reservar'}</p>
    {request.incidents.filter(i => !i.resolved_at).map(i => <p key={i.id} className="text-red-700">Incidencia: {i.cause} · {i.description}</p>)}
    <p className="text-slate-500">{request.notes || 'Sin observaciones adicionales'}</p>
    {current && <p className="font-semibold text-blue-700">Estado actual: {current.state} · Responsable actual: {current.owner}</p>}
  </div>;
}

export default function ShiftPage({ data, user, reload }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const pending = data.requests.filter(r => !['Entregado', 'Cancelado'].includes(r.state));
  const can = user.permissions.includes('handover');
  async function submit(event, path, build = f => f) {
    event.preventDefault();const form=event.currentTarget;
    setBusy(true);setError('');setMessage('');
    try {
      await post(path, build(Object.fromEntries(new FormData(form))));
      await reload();form.reset();setMessage('Registro de turno guardado con usuario y fecha/hora.');
    } catch(e) {setError(e.message);} finally {setBusy(false);}
  }
  return <div className="space-y-5">
    {error && <p role="alert" className="rounded-xl bg-red-50 p-3 text-red-700">{error}</p>}
    {message && <p role="status" className="rounded-xl bg-green-50 p-3 text-green-700">{message}</p>}
    <div className={panel}><h2 className="font-bold">{pending.length} pendientes que continúan activos</h2>
      <p className="text-sm text-slate-500">La recepción transfiere la coordinación de estos pendientes; conserva las asignaciones de operadores y las reservas.</p>
      {pending.map(r => <Pending key={r.id} request={r}/>)}
      {!pending.length && <p>No hay solicitudes abiertas.</p>}
    </div>
    {can && <form className={panel} onSubmit={e => submit(e, '/api/handovers', f => ({...f, receiving_user_id:Number(f.receiving_user_id)}))}>
      <h2 className="font-bold">Entregar al siguiente turno</h2>
      <label className="block text-sm">Turno entrante<select name="incoming_shift" className={input}><option>T1</option><option>T2</option><option>T3</option></select></label>
      <label className="block text-sm">Responsable entrante<select required name="receiving_user_id" className={input}><option value="">Selecciona otra persona</option>{data.catalogs.handover_users.filter(u=>u.id!==user.id).map(u=><option key={u.id} value={u.id}>{u.username}</option>)}</select></label>
      <textarea required minLength={3} maxLength={4000} name="notes" aria-label="Nota al turno entrante" placeholder="Pendientes críticos y contexto para el siguiente turno" className={input}/>
      <button disabled={busy} className={button}>Enviar pendientes para aceptación</button>
    </form>}
    <section className={panel}><h2 className="font-bold">Entregas y recepciones de turno</h2>
      {data.handovers.map(h => <article key={h.id} className="space-y-3 rounded-xl border border-slate-200 p-4">
        <h3 className="font-bold">Entrega #{h.id} · {h.incoming_shift} · {h.accepted_at?'Aceptada':'Pendiente de aceptación'}</h3>
        <p className="text-sm">{h.sender} → {h.recipient || 'Responsable entrante por confirmar'} · {local(h.created_at)}</p>
        <p className="text-sm">{h.notes}</p>
        <details><summary className="cursor-pointer text-sm font-semibold text-blue-700">Pendientes al entregar ({JSON.parse(h.pending).length})</summary>
          <div className="mt-3 space-y-3">{h.items.map(i=><Pending key={i.request_id} request={i.snapshot} current={data.requests.find(r=>r.id===i.request_id)}/>)}</div>
          {!h.items.length && <p className="text-sm text-slate-500">{JSON.parse(h.pending).length ? `Registro anterior sin copia detallada. Folios: ${JSON.parse(h.pending).join(', ')}` : 'No había pendientes al entregar.'}</p>}
        </details>
        {h.accepted_at ? <p className="rounded-xl bg-green-50 p-3 text-sm text-green-800">Aceptó {h.accepted_by} el {local(h.accepted_at)} · {h.acceptance_notes}</p> : can && h.user_id!==user.id && (!h.receiving_user_id || h.receiving_user_id===user.id) ? <form className="space-y-3" onSubmit={e=>submit(e,`/api/handovers/${h.id}/accept`)}>
          <textarea required minLength={3} maxLength={2000} name="notes" aria-label={`Recepción de entrega ${h.id}`} placeholder="Confirmo la recepción y revisión de estos pendientes" className={input}/>
          <button disabled={busy} className={button}>Aceptar recepción de pendientes</button>
        </form> : <p className="text-sm text-amber-700">En espera de aceptación por el responsable entrante.</p>}
      </article>)}
      {!data.handovers.length && <p>No hay entregas registradas.</p>}
    </section>
  </div>;
}
