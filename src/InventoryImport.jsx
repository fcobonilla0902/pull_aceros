import {useState} from 'react';
import {api,post,API} from './api';
const fields=[['codigo_rollo','Código del rollo'],['numero_parte','Número de parte'],['ubicacion','Ubicación'],['kg','Peso en kg'],['estado','Estado (opcional)']];
export default function InventoryImport({reload}) {
  const [file,setFile]=useState(null);const [mapping,setMapping]=useState({});const [update,setUpdate]=useState(false);
  const [preview,setPreview]=useState(null);const [busy,setBusy]=useState(false);const [error,setError]=useState('');const [message,setMessage]=useState('');
  async function review(e) {
    e.preventDefault();setError('');setMessage('');setBusy(true);setPreview(null);
    try {
      const body=new FormData();body.append('file',file);body.append('mapping',JSON.stringify(mapping));body.append('update_existing',String(update));
      const result=await api('/api/inventory/import/preview',{method:'POST',body});setPreview(result);setMapping(result.mapping);
    }catch(err){setError(err.message);}finally{setBusy(false);}
  }
  async function commit() {
    setError('');setBusy(true);
    try {const result=await post('/api/inventory/import/commit',{token:preview.token});setPreview(null);await reload();setMessage(`Importación completada: ${result.creates} rollos nuevos, ${result.updates} actualizados y ${result.unchanged} sin cambios.`);}
    catch(err){setError(err.message);setPreview(p=>p?{...p,valid:false}:p);}finally{setBusy(false);}
  }
  return <section className="space-y-4 rounded-2xl bg-white p-5 shadow-sm">
    <h2 className="font-bold">Importar inventario Excel / CSV</h2><p className="text-sm text-slate-500">Usa la primera hoja de Excel, con encabezados y hasta 5,000 filas / 5 MB. Registra antes las partes y ubicaciones. Para QAD, exporta a Excel o CSV y relaciona las columnas. Usa kg sin separador de miles y códigos como texto para conservar ceros iniciales.</p>
    <div className="flex flex-wrap gap-3 text-sm"><a className="text-blue-700 underline" href={`${API}/api/inventory/import/template?format=xlsx`}>Descargar plantilla Excel</a><a className="text-blue-700 underline" href={`${API}/api/inventory/import/template?format=csv`}>Descargar plantilla CSV</a></div>
    {error&&<p role="alert" className="rounded-xl bg-red-50 p-3 text-red-700">{error}</p>}{message&&<p role="status" className="rounded-xl bg-green-50 p-3 text-green-700">{message}</p>}
    <form onSubmit={review} className="space-y-4">
      <label className="block text-sm font-semibold">Archivo de inventario<input type="file" name="inventory_file" accept=".csv,.xlsx" required onChange={e=>{setFile(e.target.files[0]||null);setPreview(null);setMapping({});setMessage('');}} className="mt-2 block w-full rounded-xl border p-3 text-sm"/></label>
      <label className="flex gap-2 text-sm"><input type="checkbox" checked={update} onChange={e=>{setUpdate(e.target.checked);setPreview(null);}}/>Actualizar rollos existentes sin reserva (DISP o BLOQUEADO)</label>
      {preview?.headers&&<div className="grid gap-3 md:grid-cols-3">{fields.map(([key,label])=><label key={key} className="text-sm">{label}<select value={mapping[key]||''} onChange={e=>{setMapping({...mapping,[key]:e.target.value||null});setPreview({...preview,valid:false});}} className="mt-1 w-full rounded-xl border p-3"><option value="">{key==='estado'?'Sin columna: DISP':'Selecciona columna'}</option>{preview.headers.map(h=><option key={h}>{h}</option>)}</select></label>)}</div>}
      <button disabled={busy||!file} className="rounded-xl bg-blue-600 px-4 py-3 text-sm font-semibold text-white disabled:opacity-50">{busy?'Procesando…':'Revisar archivo sin guardar'}</button>
    </form>
    {preview&&<div className="space-y-3 border-t pt-4"><p className="font-semibold">{preview.total} filas · {preview.valid?'Archivo válido para confirmar':'Corrige los errores o asigna las columnas y vuelve a revisar'}</p>
      {preview.errors.map((e,i)=><p key={i} className="text-sm text-red-700">Fila {e.row}: {e.error}</p>)}{preview.error_count>200&&<p>Se muestran los primeros 200 errores de {preview.error_count}.</p>}
      {preview.valid&&<><p className="text-sm">Nuevos: {preview.creates} · Actualizados: {preview.updates} · Sin cambios: {preview.unchanged}. Esta revisión vence en 30 minutos.</p>
        <div className="overflow-x-auto"><table className="w-full text-left text-xs"><thead><tr>{fields.map(([key,label])=><th key={key} className="p-2">{label}</th>)}</tr></thead><tbody>{preview.sample.map(r=><tr key={r.codigo_rollo} className="border-t">{fields.map(([key])=><td key={key} className="p-2">{r[key]}</td>)}</tr>)}</tbody></table></div><p className="text-xs text-slate-500">Vista de hasta 50 filas. La confirmación vuelve a comprobar disponibilidad y aplica el archivo completo en una sola operación.</p>
        <button onClick={commit} disabled={busy} className="rounded-xl bg-emerald-600 px-4 py-3 text-sm font-semibold text-white disabled:opacity-50">Confirmar importación de {preview.total} filas</button>
      </>}
    </div>}
  </section>;
}
