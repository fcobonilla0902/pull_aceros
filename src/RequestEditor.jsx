import {useState} from 'react';
import {api} from './api';
const input='mt-1 w-full rounded-xl border border-slate-200 bg-white p-3 text-sm';
export default function RequestEditor({request:r,catalogs:c,reload}) {
  const [items,setItems]=useState(()=>r.items.map(i=>({part_id:i.part_id,quantity:i.requested,preferred_roll_id:i.preferred_roll_id||''})));
  const [busy,setBusy]=useState(false);const [error,setError]=useState('');const [message,setMessage]=useState('');
  const update=(index,fields)=>setItems(items.map((item,i)=>i===index?{...item,...fields}:item));
  async function save(e) {
    e.preventDefault();const f=Object.fromEntries(new FormData(e.currentTarget));setError('');setMessage('');setBusy(true);
    try {
      await api(`/api/requests/${r.id}`,{method:'PATCH',body:JSON.stringify({...f,version:r.version,press_id:Number(f.press_id),process_id:Number(f.process_id),required_at:f.required_at===localValue?r.required_at+'Z':new Date(f.required_at).toISOString(),items:items.map(i=>({part_id:Number(i.part_id),quantity:Number(i.quantity),preferred_roll_id:i.preferred_roll_id?Number(i.preferred_roll_id):null}))})});
      await reload();setMessage('Solicitud actualizada; reservas y justificación registradas.');
    }catch(err){setError(err.message);}finally{setBusy(false);}
  }
  const localDate=new Date(r.required_at+'Z');
  const localValue=new Date(localDate.getTime()-localDate.getTimezoneOffset()*60000).toISOString().slice(0,19);
  return <details data-testid="request-editor" className="space-y-4 rounded-2xl border border-blue-200 bg-blue-50/40 p-5">
    <summary className="cursor-pointer font-bold">Editar solicitud y cantidades</summary>
    <p className="text-xs text-slate-600">Si cambia el material, se ajustan las reservas y se repite la preparación. Las entregas registradas se conservan. Durante el traslado no se permite cambiar material o destino. Si falta inventario no se guarda ningún cambio.</p>
    {error&&<p role="alert" className="text-red-700">{error}</p>}{message&&<p role="status" className="text-green-700">{message}</p>}
    <form onSubmit={save} className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="text-sm">Estampadora<select name="press_id" defaultValue={r.press_id} className={input}>{c.presses.filter(p=>p.active||p.id===r.press_id).map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
        <label className="text-sm">Proceso<select name="process_id" defaultValue={r.process_id} className={input}>{c.processes.filter(p=>p.active||p.id===r.process_id).map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
        <label className="text-sm">Prioridad<select name="priority" defaultValue={r.priority} className={input}><option>Normal</option><option>Alta</option><option>Urgente</option></select></label>
        <label className="text-sm">Riesgo<select name="risk" defaultValue={r.risk} className={input}><option>Sin riesgo</option><option>Riesgo de paro</option><option>Línea detenida</option></select></label>
        <label className="text-sm">Hora requerida<input type="datetime-local" step="1" name="required_at" defaultValue={localValue} required className={input}/></label>
        <label className="text-sm">Punto de entrega<input name="destination" maxLength={200} defaultValue={r.destination} required placeholder="Ej. DANLY 800 · alimentación de prensa" className={input}/></label>
      </div>
      <label className="block text-sm">Comentario<textarea name="notes" maxLength={2000} defaultValue={r.notes} placeholder="Indica especificaciones y observaciones para la entrega" className={input}/></label>
      {items.map((item,index)=><div key={index} className="grid items-end gap-2 sm:grid-cols-[1fr_100px_80px]">
        <label className="text-xs">Número de parte<select value={item.part_id} onChange={e=>update(index,{part_id:e.target.value,preferred_roll_id:''})} required className={input}><option value="">Selecciona un número de parte</option>{c.parts.filter(p=>p.active||p.id===Number(item.part_id)).map(p=><option key={p.id} value={p.id}>{p.code} · {p.specification}</option>)}</select></label>
        <label className="text-xs">Cantidad<input type="number" required min="1" max={item.preferred_roll_id?1:100} value={item.quantity} placeholder="Ej. 2" onChange={e=>update(index,{quantity:e.target.value})} className={input}/></label>
        <button type="button" disabled={items.length===1} onClick={()=>setItems(items.filter((_,i)=>i!==index))} className="p-3 text-sm text-red-700 disabled:opacity-40">Quitar</button>
        {item.preferred_roll_id&&<p className="sm:col-span-3 text-xs text-blue-700">Rollo específico #{item.preferred_roll_id} conservado. <button type="button" className="underline" onClick={()=>update(index,{preferred_roll_id:''})}>Permitir asignación automática</button></p>}
      </div>)}
      <button type="button" className="rounded-xl border bg-white px-4 py-2 text-sm" onClick={()=>setItems([...items,{part_id:'',quantity:1,preferred_roll_id:''}])}>Agregar partida</button>
      <label className="block text-sm font-semibold">Justificación obligatoria<textarea name="justification" required minLength={3} maxLength={2000} placeholder="Ej. Se ajusta la cantidad por un cambio en el programa de Producción" className={input}/></label>
      <button disabled={busy} className="rounded-xl bg-blue-600 px-4 py-3 text-sm font-semibold text-white disabled:opacity-50">Guardar solicitud y ajustar reservas</button>
    </form>
  </details>;
}
