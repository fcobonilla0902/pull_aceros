import {useState} from 'react';
import {post} from './api';
export default function AccountPage({user}) {
  const [error,setError]=useState('');const [message,setMessage]=useState('');const [busy,setBusy]=useState(false);
  async function submit(e) {
    e.preventDefault();const form=e.currentTarget;const fields=Object.fromEntries(new FormData(form));
    setError('');setMessage('');
    if(fields.new_password!==fields.confirm_password){setError('La confirmación no coincide.');return;}
    setBusy(true);
    try {await post('/api/auth/password',{current_password:fields.current_password,new_password:fields.new_password});form.reset();setMessage('Contraseña actualizada. Se cerraron las sesiones de otros dispositivos.');}
    catch(err){setError(err.message);}finally{setBusy(false);}
  }
  return <div className="max-w-xl space-y-5 rounded-2xl bg-white p-6 shadow-sm"><h2 className="font-bold">{user.username} · {user.role}</h2><p className="text-sm text-slate-500">Cambia tu contraseña sin cerrar esta sesión.</p>{error&&<p role="alert" className="text-red-700">{error}</p>}{message&&<p role="status" className="text-green-700">{message}</p>}
    <form onSubmit={submit} className="space-y-4">{[['current_password','Contraseña actual','current-password'],['new_password','Nueva contraseña','new-password'],['confirm_password','Confirmar nueva contraseña','new-password']].map(([name,label,autocomplete])=><label key={name} className="block text-sm font-semibold">{label}<input type="password" name={name} required minLength={name==='current_password'?1:12} maxLength={200} autoComplete={autocomplete} placeholder={name==='current_password'?'Ingresa tu contraseña actual':name==='new_password'?'Mínimo 12 caracteres':'Repite la nueva contraseña'} className="mt-1 w-full rounded-xl border p-3"/></label>)}<p className="text-xs text-slate-500">Usa una contraseña diferente de al menos 12 caracteres.</p><button disabled={busy} className="rounded-xl bg-blue-600 px-4 py-3 font-semibold text-white disabled:opacity-50">Cambiar contraseña</button></form>
  </div>;
}
