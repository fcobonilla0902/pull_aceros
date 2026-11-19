import { useEffect, useState } from 'react';
import { api, post, API } from './api';
const panel='space-y-4 rounded-2xl bg-white p-5 shadow-sm';
const input='w-full rounded-xl border border-slate-200 bg-white p-3 text-sm';
const button='rounded-xl bg-[var(--admin-action)] px-4 py-3 text-sm font-semibold text-white disabled:opacity-50';
const catalogExamples={parts:'Ej. 180553AA',locations:'Ej. ALM-A01',forklifts:'Ej. MC-01',presses:'Ej. DANLY 800',processes:'Ej. Blancos'};
const kinds=[['parts','Números de parte'],['locations','Ubicaciones'],['forklifts','Montacargas'],['presses','Estampadoras'],['processes','Tipos de proceso']];

export default function AdminPage({data,user,reload}) {
  const [tab,setTab]=useState('usuarios');
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const [message,setMessage]=useState('');
  const [backups,setBackups]=useState([]);
  const [selectedBackup,setSelectedBackup]=useState('');
  useEffect(()=>{
    if(tab==='respaldos')api('/api/backups').then(setBackups).catch(e=>setError(e.message));
  },[tab]);
  async function submit(event,path,build,method='POST') {
    event.preventDefault();const form=event.currentTarget;
    setError('');setMessage('');setBusy(true);
    try {
      await api(path,{method,body:JSON.stringify(build(Object.fromEntries(new FormData(form))))});
      await reload();setMessage('Cambios guardados y registrados en el historial.');
      if(method==='POST')form.reset();
    }catch(e){setError(e.message);}finally{setBusy(false);}
  }
  async function backup() {
    setError('');setBusy(true);
    try {const result=await post('/api/backups',{});setBackups(await api('/api/backups'));await reload();setMessage(`Respaldo creado: ${result.name}`);}
    catch(e){setError(e.message);}finally{setBusy(false);}
  }
  return <div className="space-y-5">
    <div className="flex flex-wrap gap-2">{[['usuarios','Usuarios'],['catalogos','Catálogos'],['respaldos','Respaldos']].map(([id,label])=><button key={id} onClick={()=>{setTab(id);setError('');setMessage('');}} className={tab===id?button:'rounded-xl border bg-white px-4 py-3 text-sm'}>{label}</button>)}</div>
    {error&&<p role="alert" className="rounded-xl bg-red-50 p-3 text-red-700">{error}</p>}
    {message&&<p role="status" className="rounded-xl bg-green-50 p-3 text-green-700">{message}</p>}
    {tab==='usuarios'&&<>
      <form className={panel} onSubmit={e=>submit(e,'/api/users',f=>({...f,role_id:Number(f.role_id)}))}>
        <h2 className="font-bold">Crear usuario</h2>
        <div className="grid gap-3 md:grid-cols-3">
          <label className="text-sm">Usuario<input name="username" required minLength={3} maxLength={80} pattern="[a-zA-Z0-9_.-]+" autoComplete="off" placeholder="Ej. logistica.turno1" className={input}/></label>
          <label className="text-sm">Contraseña inicial<input name="password" type="password" required minLength={12} maxLength={200} autoComplete="new-password" placeholder="Mínimo 12 caracteres" className={input}/></label>
          <label className="text-sm">Rol<select name="role_id" required className={input}><option value="">Selecciona un rol</option>{data.catalogs.roles.map(r=><option key={r.id} value={r.id}>{r.name}</option>)}</select></label>
        </div><p className="text-xs text-slate-500">Las contraseñas requieren al menos 12 caracteres.</p><button disabled={busy} className={button}>Crear cuenta</button>
      </form>
      <section className={panel}><h2 className="font-bold">Usuarios y permisos</h2><p className="text-xs text-slate-500">Cambiar el rol o desactivar una cuenta cierra sus sesiones. Los usuarios se conservan en el historial. Siempre debe quedar un administrador activo.</p>
        {data.users.map(u=><details key={`${u.id}-${u.version}`} className="rounded-xl border border-slate-200 p-4">
          <summary className="cursor-pointer text-sm font-semibold">{u.username} · {u.role} · {u.active?'Activo':'Inactivo'}{u.id===user.id?' · Tu cuenta':''}</summary>
          <p className="my-3 text-xs text-slate-500">Permisos: {u.permissions.join(', ')}</p>
          <form className="grid gap-3 md:grid-cols-3" onSubmit={e=>submit(e,`/api/users/${u.id}`,f=>({username:f.username,role_id:Number(f.role_id),active:f.active==='on',version:u.version}),'PATCH')}>
            <label className="text-sm">Usuario<input name="username" required minLength={3} maxLength={80} pattern="[a-zA-Z0-9_.-]+" defaultValue={u.username} placeholder="Ej. logistica.turno1" className={input}/></label>
            <label className="text-sm">Rol<select name="role_id" defaultValue={u.role_id} className={input}>{data.catalogs.roles.map(r=><option key={r.id} value={r.id}>{r.name}</option>)}</select></label>
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" name="active" defaultChecked={u.active}/>Cuenta activa</label>
            <button disabled={busy} className={button}>Guardar usuario</button>
          </form>
          {u.id!==user.id?<form className="mt-4 flex flex-wrap items-end gap-3 border-t pt-4" onSubmit={e=>submit(e,`/api/users/${u.id}/password`,f=>f)}>
            <label className="min-w-0 flex-1 text-sm">Nueva contraseña<input type="password" name="new_password" required minLength={12} maxLength={200} autoComplete="new-password" placeholder="Mínimo 12 caracteres" className={input}/></label><button disabled={busy} className={button}>Restablecer contraseña</button>
          </form>:<p className="mt-4 text-xs text-blue-700">Para cambiar tu contraseña abre Mi cuenta en el menú.</p>}
        </details>)}
      </section>
    </>}
    {tab==='catalogos'&&<div className="grid items-start gap-5 xl:grid-cols-2">{kinds.map(([kind,label])=><section key={kind} className={panel}>
      <h2 className="font-bold">{label}</h2>
      <form className="space-y-3" onSubmit={e=>submit(e,`/api/catalogs/${kind}`,f=>f)}>
        <input name="name" aria-label={`Nuevo registro de ${label}`} required maxLength={kind==='parts'?80:40} placeholder={catalogExamples[kind]} className={input}/>
        {kind==='parts'&&<input name="specification" required maxLength={200} placeholder="Ej. Acero, espesor 2 mm, ancho 1200 mm" className={input}/>}
        <button disabled={busy} className={button}>Agregar</button>
      </form>
      {data.catalogs[kind].map(r=><details key={`${r.id}-${r.version}`} className="rounded-xl border border-slate-200 p-3">
        <summary className="cursor-pointer text-sm font-semibold">{r.name||r.code} · {!r.active?'Inactivo':kind==='forklifts'?(r.available?'Disponible':'Asignado'):'Activo'}</summary>
        <form className="mt-3 space-y-3" onSubmit={e=>submit(e,`/api/catalogs/${kind}/${r.id}`,f=>({...f,active:f.active==='on',version:r.version}),'PATCH')}>
          <label className="block text-sm">Nombre o código<input name="name" required maxLength={kind==='parts'?80:40} defaultValue={r.name||r.code} placeholder={catalogExamples[kind]} className={input}/></label>
          {kind==='parts'&&<label className="block text-sm">Especificación<input name="specification" required maxLength={200} defaultValue={r.specification} placeholder="Ej. Acero, espesor 2 mm, ancho 1200 mm" className={input}/></label>}
          <label className="flex items-center gap-2 text-sm"><input name="active" type="checkbox" defaultChecked={r.active}/>{kind==='forklifts'?'En servicio':'Activo para nuevas operaciones'}</label>
          <button disabled={busy} className={button}>Guardar catálogo</button>
        </form>
      </details>)}
      <p className="text-xs text-slate-500">Los registros utilizados se conservan. La desactivación se rechaza si afecta movimientos abiertos.{kind==='parts'?' Una especificación distinta para rollos existentes requiere otra parte.':''}</p>
    </section>)}</div>}
    {tab==='respaldos'&&<section className={panel}>
      <h2 className="font-bold">Respaldos locales</h2><p className="text-sm text-slate-600">Guarda una copia consistente de usuarios, inventario, solicitudes e historial. Los archivos contienen información de acceso; guárdalos en un lugar privado.</p>
      <button disabled={busy} onClick={backup} className={button}>Crear respaldo ahora</button>
      <div className="space-y-3">{backups.map(b=><div key={b.name} className="flex flex-wrap justify-between gap-3 rounded-xl border p-3 text-sm"><div className="min-w-0 break-all"><p className="font-semibold">{b.name}</p><p className="text-xs text-slate-500">{new Date(b.created_at).toLocaleString('es-MX')} · {(b.bytes/1024).toFixed(1)} KB · {b.engine==='postgresql'?'PostgreSQL':'SQLite'}{b.restorable===false?' · Copia del motor anterior':''}</p></div><a className="text-blue-700 underline" href={`${API}/api/backups/${encodeURIComponent(b.name)}`}>Descargar</a></div>)}{!backups.length&&<p className="text-sm text-slate-500">No hay respaldos guardados.</p>}</div>
      <details className="rounded-xl border border-amber-200 bg-amber-50 p-4"><summary className="cursor-pointer font-semibold">Recuperar un respaldo</summary>
        <p className="my-3 text-sm">La recuperación reemplaza los datos actuales. Primero detén el backend con Ctrl+C. Se guardará una copia del estado anterior y se cerrarán todas las sesiones.</p>
        <label className="block text-sm">Respaldo del motor actual a recuperar<select value={selectedBackup} onChange={e=>setSelectedBackup(e.target.value)} className={input}><option value="">Selecciona un respaldo</option>{backups.filter(b=>b.restorable!==false).map(b=><option key={b.name}>{b.name}</option>)}</select></label>
        {selectedBackup&&<><p className="mt-3 text-sm">Desde la carpeta backend ejecuta:</p><pre className="mt-2 overflow-x-auto rounded-xl bg-white p-3 text-xs">{`.\\.venv\\Scripts\\python.exe manage.py restore "${selectedBackup}" --confirm RESTAURAR`}</pre><p className="mt-3 text-sm">Después inicia nuevamente con .\run.ps1 e ingresa con las credenciales que tenía ese respaldo. El proceso verifica integridad y compatibilidad antes de reemplazar datos.</p></>}
      </details>
    </section>}
  </div>;
}
