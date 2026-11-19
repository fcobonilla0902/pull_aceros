import { formatDuration } from './lib/time';
import { useMemo, useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { api, post } from "./api";
import { OperationPage, OperationalDetail } from "./Operations";
import SimulationPage from "./SimulationPage";
import { AlertTriangle, Bell, ChartNoAxesCombined, ChevronDown, CircleUserRound, ClipboardList, FileClock, Truck as Forklift, History, LayoutDashboard, LockKeyhole, LogOut, Menu, Plus, Search, Settings, Warehouse } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";


const navItems = [
  { id: "resumen", label: "Resumen", icon: LayoutDashboard },
  { id: "kanban", label: "Panel Kanban", icon: ClipboardList },
  { id: "nueva", label: "Nueva solicitud", icon: Plus },
  { id: "inventario", label: "Inventario", icon: Warehouse },
  { id: "turno", label: "Cambio de turno", icon: FileClock },
  { id: "historial", label: "Historial", icon: History },
  { id: "admin", label: "Administración", icon: Settings },
  { id: "simulacion", label: "Simulación", icon: ChartNoAxesCombined },
  { id: "cuenta", label: "Mi cuenta", icon: CircleUserRound },
];

const states = ["Solicitado", "Validado", "Tomado", "En preparación", "Listo para traslado", "En traslado", "Entrega parcial", "Con incidencia", "Entregado", "Cancelado"];

function Pill({ children, className = "" }) {
  return <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold ${className}`}>{children}</span>;
}

function RequestCard({ request, onOpen }) {
  const requested = request.items.reduce((a, b) => a + b.requested, 0);
  const delivered = request.items.reduce((a, b) => a + b.delivered, 0);
  return (
    <motion.button layout onClick={() => onOpen(request)} className="w-full rounded-2xl border border-slate-200 bg-white p-4 text-left shadow-sm transition hover:-translate-y-0.5 hover:border-blue-300 hover:shadow-md">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-xs font-bold text-blue-700">{request.displayId || request.folio || request.id}</p>
          <h3 className="mt-1 text-lg font-bold text-slate-900">{request.enn}</h3>
        </div>
        {request.risk !== "Sin riesgo" && <AlertTriangle className={request.risk === "Línea detenida" ? "text-red-600" : "text-orange-500"} size={20} />}
      </div>
      <div className="mt-3 flex flex-wrap gap-1.5">
        <Pill className={request.priority === "Urgente" ? "border-orange-200 bg-orange-50 text-orange-700" : request.priority === "Alta" ? "border-amber-200 bg-amber-50 text-amber-700" : "border-slate-200 bg-slate-50 text-slate-600"}>{request.priority}</Pill>
        <Pill className="border-slate-200 bg-slate-50 text-slate-600">{request.items.length} NP</Pill>
        {request.priority === "Urgente" && <Pill className="border-red-200 bg-red-50 text-red-700">Atención urgente</Pill>}
        {request.inherited && <Pill className="border-violet-200 bg-violet-50 text-violet-700">Turno anterior</Pill>}
      </div>
      <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
        <div><p className="text-xs text-slate-500">Rollos</p><p className="font-bold text-slate-800">{delivered}/{requested} entregados</p></div>
        <div><p className="text-xs text-slate-500">Tiempo abierto</p><p className="font-bold text-slate-800">{request.elapsed}</p></div>
      </div>
      <div className="mt-3 border-t border-slate-100 pt-3">
        <p className="truncate text-xs text-slate-500">{request.owner}</p>
        <p className="mt-1 text-xs text-slate-500">{request.items.map(i=>i.part).join(', ')}</p>
        <p className="mt-2 text-xs">Requerido: {new Date(request.required_at+'Z').toLocaleString('es-MX')}</p>
        <p className={`mt-1 text-xs font-semibold ${request.remaining_minutes<0?'text-red-700':request.remaining_minutes<=30?'text-amber-700':'text-slate-600'}`}>{['Entregado','Cancelado'].includes(request.state)?request.state:request.remaining_minutes<0?`${formatDuration(request.remaining_minutes)} de retraso`:`Vence en ${formatDuration(request.remaining_minutes)}`}</p>
      </div>
    </motion.button>
  );
}

function Modal({ open, onClose, children, size = "max-w-2xl" }) {
  return (
    <AnimatePresence>
      {open && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/45 p-4 backdrop-blur-sm" onMouseDown={onClose}>
          <motion.div initial={{ y: 20, opacity: 0, scale: .98 }} animate={{ y: 0, opacity: 1, scale: 1 }} exit={{ y: 20, opacity: 0, scale: .98 }} className={`max-h-[92vh] w-full overflow-auto rounded-3xl bg-white shadow-2xl ${size}`} onMouseDown={(e) => e.stopPropagation()}>
            {children}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export default function PullSteelPrototype() {
  const [user, setUser] = useState(null);
  const [checking, setChecking] = useState(true);
  const [loginError, setLoginError] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loginBusy, setLoginBusy] = useState(false);
  const [page, setPage] = useState('resumen');
  const [sidebar, setSidebar] = useState(false);
  const [ennFilter, setEnnFilter] = useState('Todos');
  const [search, setSearch] = useState('');
  const [selectedId, setSelectedId] = useState(null);
  const [notify, setNotify] = useState(false);

  const [dataError, setDataError] = useState('');
  const [data, setData] = useState(null);
  const role = user?.role || '';
  const reload = useCallback(async () => {
    const paths = ['/api/auth/me','/api/catalogs','/api/requests','/api/inventory','/api/metrics','/api/history','/api/handovers'];
    if (user?.permissions.includes('admin')) paths.push('/api/users');
    const values = await Promise.all(paths.map(path => api(path)));
    const identity=values.shift();
    if(JSON.stringify(identity)!==JSON.stringify(user))setUser(identity);
    setData({updatedAt: Date.now(), ...Object.fromEntries(['catalogs','requests','inventory','metrics','history','handovers','users'].map((k,i)=>[k,values[i] || []]))});
    setDataError('');
  }, [user]);
  useEffect(()=>{
    const expired=()=>{if(user){setUser(null);setData(null);setSelectedId(null);setPage('resumen');setPassword('');setLoginError('Tu sesión terminó o cambió tu acceso. Inicia sesión nuevamente.');}};
    window.addEventListener('metaride:unauthorized',expired);
    return()=>window.removeEventListener('metaride:unauthorized',expired);
  },[user]);
  useEffect(() => { api('/api/auth/me').then(setUser).catch(e => { if(e.message !== 'Inicia sesión') setLoginError(e.message); }).finally(()=>setChecking(false)); }, []);
  useEffect(() => {
    if(!user) return;
    const initial = setTimeout(()=>reload().catch(e=>setDataError(e.message)),0);
    const timer = setInterval(()=>reload().catch(e=>setDataError(e.message)),30000);
    return ()=>{clearTimeout(initial);clearInterval(timer);};
  }, [user,reload]);
  async function login() {
    setLoginBusy(true); setLoginError('');
    try { setUser(await post('/api/auth/login',{username,password})); setPassword(''); }
    catch(e) { setLoginError(e.message); } finally { setLoginBusy(false); }
  }
  async function logout() {
    try { await post('/api/auth/logout',{}); setUser(null);setData(null);setSelectedId(null);setPage('resumen');setUsername('');setPassword(''); }
    catch(e) { setDataError(e.message); }
  }
  const selected = data?.requests.find(r=>r.id===selectedId);
  const setSelected = r => setSelectedId(r?.id || null);
  const filteredRequests = useMemo(() => (data?.requests || []).filter(r => (ennFilter === 'Todos' || r.enn === ennFilter) && `${r.folio} ${r.enn} ${r.items.map(i=>i.part).join(' ')}`.toLowerCase().includes(search.toLowerCase())).sort((a,b)=>Number(['Entregado','Cancelado'].includes(a.state))-Number(['Entregado','Cancelado'].includes(b.state)) || Number(b.priority==='Urgente')-Number(a.priority==='Urgente') || new Date(a.required_at+'Z')-new Date(b.required_at+'Z')).map(r=>({...r, displayId:r.folio, elapsed:`${Math.max(0,Math.round((data.updatedAt-new Date(r.created_at+'Z').getTime())/60000))} min`})),[data,ennFilter,search]);

  if (checking) return <div className="p-10">Comprobando acceso...</div>;
  if (!user) {
    return (
      <div data-theme-section="acceso" className="min-h-screen bg-slate-950 p-5 font-sans text-slate-900" style={{ backgroundImage: "radial-gradient(circle at 18% 20%, var(--login-glow-primary) 0, transparent 28%), radial-gradient(circle at 82% 78%, var(--login-glow-secondary) 0, transparent 25%)" }}>
        <div className="mx-auto grid min-h-[calc(100vh-40px)] max-w-6xl overflow-hidden rounded-[32px] bg-white shadow-2xl lg:grid-cols-2">
          <div className="hidden bg-[var(--login-panel)] p-12 text-white lg:flex lg:flex-col lg:justify-between">
            <div className="flex items-center gap-3"><div className="rounded-2xl bg-blue-600 p-3"><Forklift /></div><div><p className="text-xl font-bold">Pull Aceros</p><p className="text-xs text-slate-300">Control de requerimientos ENN</p></div></div>
            <div>
              <Badge className="mb-5 border-0 bg-cyan-400/15 text-cyan-200">Operación en tiempo real</Badge>
              <h1 className="max-w-lg text-5xl font-bold leading-tight">Los pendientes permanecen visibles entre cada turno.</h1>
              <p className="mt-5 max-w-md text-slate-300">Solicita, prepara, traslada y controla rollos de acero desde un solo sitio.</p>
            </div>
            <div className="grid grid-cols-3 gap-3 text-center text-xs text-slate-300">
              <div className="rounded-2xl bg-white/5 p-4"><p className="text-xl font-bold text-white">6</p>ENNs</div>
              <div className="rounded-2xl bg-white/5 p-4"><p className="text-xl font-bold text-white">3</p>Turnos</div>
              <div className="rounded-2xl bg-white/5 p-4"><p className="text-xl font-bold text-white">24/7</p>Visible</div>
            </div>
          </div>
          <div className="flex items-center justify-center p-7 sm:p-12">
            <div className="w-full max-w-md">
              <div className="mb-10 flex items-center gap-3 lg:hidden"><div className="rounded-2xl bg-blue-600 p-3 text-white"><Forklift /></div><div><p className="text-xl font-bold">Pull Aceros</p><p className="text-xs text-slate-500">Control de requerimientos ENN</p></div></div>
              <p className="text-sm font-bold text-blue-700">BIENVENIDO</p>
              <h2 className="mt-2 text-3xl font-bold">Iniciar sesión</h2>
              <p className="mt-2 text-sm text-slate-500">Ingresa con el usuario creado para el sistema.</p>
              <label className="mt-8 block text-sm font-semibold">Usuario</label>
              <Input value={username} onChange={e=>setUsername(e.target.value)} autoComplete="username" placeholder="Ingresa tu usuario" className="mt-2 h-12 rounded-xl" />
              <label className="mt-5 block text-sm font-semibold">Contraseña</label>
              <div className="relative mt-2"><LockKeyhole className="absolute left-3 top-3.5 text-slate-400" size={18}/><Input type="password" value={password} onChange={e=>setPassword(e.target.value)} onKeyDown={e=>{if(e.key==='Enter')login();}} autoComplete="current-password" placeholder="Ingresa tu contraseña" className="h-12 rounded-xl pl-10" /></div>
              {loginError && <p role="alert" className="mt-4 text-sm text-red-600">{loginError}</p>}
              <Button disabled={loginBusy} onClick={login} className="mt-7 h-12 w-full rounded-xl bg-blue-600 font-bold hover:bg-blue-700">{loginBusy?'Ingresando...':'Entrar al sistema'}</Button>
              <p className="mt-5 text-center text-xs text-slate-400">Acceso con cuenta autorizada.</p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  const visibleNav = navItems.filter(n => n.id !== 'admin' || user.permissions.includes('admin')).filter(n => n.id !== 'nueva' || user.permissions.includes('request')).filter(n => n.id !== 'simulacion' || user.permissions.includes('simulate'));
  if (!data) return <div className="p-10 space-y-4"><p>{dataError || 'Cargando datos...'}</p><button onClick={()=>reload().catch(e=>setDataError(e.message))}>Reintentar</button><button onClick={logout}>Cerrar sesión</button></div>;


  return (
    <div className="min-h-screen bg-[var(--app-background)] font-sans text-slate-900">
      <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-slate-200 bg-[var(--app-header)] px-4 lg:px-7">
        <div className="flex items-center gap-3">
          <button onClick={() => setSidebar(!sidebar)} className="rounded-xl p-2 hover:bg-slate-100 lg:hidden"><Menu size={22}/></button>
          <div className="flex items-center gap-2.5"><div className="rounded-xl bg-blue-600 p-2 text-white"><Forklift size={20}/></div><div><p className="font-bold leading-4">Pull Aceros</p><p className="text-[10px] text-slate-500">Planta 100215</p></div></div>
        </div>
        <div className="flex items-center gap-2">
          <div className="hidden rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs font-semibold text-emerald-700 sm:block">Actualizado cada 30 s</div>
          <button onClick={() => setNotify(!notify)} className="relative rounded-xl p-2 hover:bg-slate-100"><Bell size={20}/><span className="absolute right-1 top-1 h-2 w-2 rounded-full bg-red-500"/></button>
          <button onClick={()=>setPage('cuenta')} className="flex items-center gap-2 rounded-xl p-2 hover:bg-slate-100"><CircleUserRound size={22}/><span className="hidden text-left sm:block"><span className="block text-xs font-bold">{role}</span><span className="block text-[10px] text-slate-500">{user.username}</span></span><ChevronDown size={15}/></button>
        </div>
      </header>

      {notify && <div className="fixed right-4 top-16 z-40 max-w-sm rounded-2xl border bg-white p-4 shadow-xl"><h3 className="font-bold">Alertas operativas</h3><p>{data.metrics.urgent} solicitudes urgentes</p><p>{data.metrics.due_soon} próximas a vencer (30 min)</p><p>{data.metrics.overdue} solicitudes retrasadas</p><p>{data.metrics.incidents} incidencias abiertas</p><p>{data.metrics.awaiting_handover_acceptance} turnos por aceptar</p><button onClick={()=>{setPage('kanban');setNotify(false);}}>Ver solicitudes</button></div>}


      <aside className={`fixed bottom-0 left-0 top-16 z-40 w-64 border-r border-slate-200 bg-[var(--navigation-background)] p-4 text-white transition-transform lg:translate-x-0 ${sidebar ? "translate-x-0" : "-translate-x-full"}`}>
        <nav className="space-y-1">
          {visibleNav.map(item => <button key={item.id} onClick={() => { setPage(item.id); setSidebar(false); }} className={`flex w-full items-center gap-3 rounded-xl px-3 py-3 text-sm font-semibold transition ${page === item.id ? "bg-[var(--navigation-active)] text-white" : "text-slate-300 hover:bg-white/10 hover:text-white"}`}><item.icon size={18}/>{item.label}</button>)}
        </nav>
        <div className="absolute bottom-4 left-4 right-4 border-t border-white/10 pt-4"><button onClick={logout} className="flex w-full items-center gap-3 rounded-xl px-3 py-2 text-sm text-slate-300 hover:bg-white/10"><LogOut size={18}/>Cerrar sesión</button></div>
      </aside>

      <main data-theme-section={page} className="p-4 pb-12 lg:ml-64 lg:p-7">
        {dataError && <p role="alert" className="mb-4 rounded-xl bg-red-50 p-3 text-red-700">{dataError}</p>}
        {page === 'kanban' ? <Kanban requests={filteredRequests} ennFilter={ennFilter} setEnnFilter={setEnnFilter} search={search} setSearch={setSearch} onOpen={setSelected} presses={data.catalogs.presses}/> : page === 'simulacion' ? <SimulationPage/> : <OperationPage key={page} page={page} data={data} reload={reload} user={user} onCreated={()=>setPage('kanban')} onNavigate={setPage} onOpenRequest={setSelected}/>}
      </main>

      <Modal open={!!selected} onClose={() => { setSelected(null); }} size="max-w-3xl">
        {selected && <OperationalDetail key={selected.id} request={selected} catalogs={data.catalogs} user={user} reload={reload} onClose={()=>setSelected(null)}/>}

      </Modal>
    </div>
  );
}

function PageHead({ eyebrow, title, description, action }) {
  return <div className="mb-6 flex flex-col justify-between gap-4 md:flex-row md:items-end"><div><p className="text-xs font-bold uppercase tracking-[.18em] text-blue-700">{eyebrow}</p><h1 className="mt-1 text-2xl font-bold sm:text-3xl">{title}</h1><p className="mt-1 max-w-2xl text-sm text-slate-500">{description}</p></div>{action}</div>;
}

function Kanban({ presses, requests, ennFilter, setEnnFilter, search, setSearch, onOpen }) {
  return <>
    <PageHead eyebrow="Seguimiento en vivo" title="Panel Kanban" description="Selecciona una tarjeta para consultar partidas, registrar avances, entregas o incidencias." />
    <Card className="mb-5 rounded-2xl border-0 shadow-sm"><CardContent className="flex flex-col gap-3 p-4 md:flex-row"><div className="relative flex-1"><Search className="absolute left-3 top-3 text-slate-400" size={18}/><Input value={search} onChange={e => setSearch(e.target.value)} placeholder="Buscar folio, ENN o número de parte" className="h-11 rounded-xl pl-10"/></div><select value={ennFilter} onChange={e => setEnnFilter(e.target.value)} className="h-11 rounded-xl border border-slate-200 bg-white px-4 text-sm"><option>Todos</option>{presses.map(p => <option key={p.id}>{p.name}</option>)}</select></CardContent></Card>
    <div className="flex snap-x gap-4 overflow-x-auto pb-4">
      {states.map(state => <section key={state} className="min-w-[286px] flex-1 snap-start rounded-2xl bg-[var(--kanban-column-background)]/55 p-3 xl:min-w-[300px]"><div className="mb-3 flex items-center justify-between px-1"><div className="flex items-center gap-2"><span className={`h-2.5 w-2.5 rounded-full ${state === "Con incidencia" ? "bg-red-500" : state === "Entrega parcial" ? "bg-orange-500" : "bg-[var(--kanban-status-dot)]"}`}/><h2 className="text-sm font-bold">{state}</h2></div><Badge variant="secondary" className="rounded-full">{requests.filter(r => r.state === state).length}</Badge></div><div className="space-y-3">{requests.filter(r => r.state === state).map(r => <RequestCard key={r.id} request={r} onOpen={onOpen}/>)}{requests.filter(r => r.state === state).length === 0 && <div className="rounded-2xl border border-dashed border-slate-300 p-8 text-center text-xs text-slate-400">Sin solicitudes</div>}</div></section>)}
    </div>
  </>;
}

