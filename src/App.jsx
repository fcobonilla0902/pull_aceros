import React, { useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import SimulationPage from "./SimulationPage";
import {
  AlertTriangle,
  Archive,
  Bell,
  ChartNoAxesCombined,
  Boxes,
  Check,
  ChevronDown,
  ChevronRight,
  CircleUserRound,
  ClipboardList,
  Clock3,
  Download,
  FileClock,
  FileSpreadsheet,
  Filter,
  Truck as Forklift,
  History,
  LayoutDashboard,
  LockKeyhole,
  LogOut,
  Menu,
  PackageCheck,
  Pencil,
  Plus,
  RefreshCw,
  Search,
  Settings,
  ShieldCheck,
  Truck,
  Upload,
  UserCog,
  Users,
  Warehouse,
  X,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";

const palette = {
  navy: "#17243A",
  blue: "#2558D9",
  cyan: "#30B6D9",
  bg: "#F3F6FA",
};

const navItems = [
  { id: "resumen", label: "Resumen", icon: LayoutDashboard },
  { id: "kanban", label: "Panel Kanban", icon: ClipboardList },
  { id: "nueva", label: "Nueva solicitud", icon: Plus },
  { id: "inventario", label: "Inventario", icon: Warehouse },
  { id: "turno", label: "Cambio de turno", icon: FileClock },
  { id: "historial", label: "Historial", icon: History },
  { id: "admin", label: "Administración", icon: Settings },
  { id: "simulacion", label: "Simulación", icon: ChartNoAxesCombined },
];

const initialRequests = [
  {
    id: "REQ-20260901-0008",
    enn: "ENN3",
    state: "Solicitado",
    priority: "Urgente",
    risk: "Riesgo de paro",
    requestedAt: "09:42",
    elapsed: "38 min",
    owner: "Sin asignar",
    requester: "logistico.enn3",
    shift: "T1",
    notes: "Material requerido para continuidad de programa",
    items: [
      { part: "180324AB", requested: 2, delivered: 0, stock: 8 },
      { part: "190031AB", requested: 1, delivered: 0, stock: 12 },
    ],
  },
  {
    id: "REQ-20260901-0007",
    enn: "ENN1",
    state: "Tomado",
    priority: "Alta",
    risk: "Sin riesgo",
    requestedAt: "09:18",
    elapsed: "1 h 02 min",
    owner: "Titular Recibo",
    requester: "logistico.enn1",
    shift: "T1",
    notes: "Atender después de solicitud crítica",
    items: [{ part: "180296AA", requested: 3, delivered: 0, stock: 5 }],
  },
  {
    id: "REQ-20260901-0006",
    enn: "ENN5",
    state: "En preparación",
    priority: "Normal",
    risk: "Sin riesgo",
    requestedAt: "08:55",
    elapsed: "1 h 25 min",
    owner: "Montacarguista Recibo",
    requester: "logistico.enn5",
    shift: "T1",
    notes: "Dos rollos localizados en 05155",
    items: [
      { part: "180299AB", requested: 2, delivered: 0, stock: 7 },
      { part: "180546AA", requested: 1, delivered: 0, stock: 6 },
    ],
  },
  {
    id: "REQ-20260901-0005",
    enn: "ENN2",
    state: "Listo para traslado",
    priority: "Alta",
    risk: "Sin riesgo",
    requestedAt: "08:21",
    elapsed: "1 h 59 min",
    owner: "Titular Recibo",
    requester: "logistico.enn2",
    shift: "T1",
    notes: "Esperando plana interna",
    items: [{ part: "180057AA", requested: 4, delivered: 0, stock: 9 }],
  },
  {
    id: "REQ-20260901-0004",
    enn: "ENN6",
    state: "En traslado",
    priority: "Normal",
    risk: "Sin riesgo",
    requestedAt: "07:48",
    elapsed: "2 h 32 min",
    owner: "Montacarguista Recibo",
    requester: "logistico.enn6",
    shift: "T1",
    notes: "Traslado directo a ENN6",
    items: [{ part: "180543AA", requested: 2, delivered: 0, stock: 3 }],
  },
  {
    id: "REQ-20260901-0003",
    enn: "ENN4",
    state: "Entrega parcial",
    priority: "Urgente",
    risk: "Línea detenida",
    requestedAt: "06:35",
    elapsed: "3 h 45 min",
    owner: "Montacarguista Recibo",
    requester: "logistico.enn4",
    shift: "T1",
    notes: "Falta un rollo por localizar",
    items: [
      { part: "180582AA", requested: 3, delivered: 2, stock: 6 },
      { part: "190017AA", requested: 2, delivered: 2, stock: 8 },
    ],
  },
  {
    id: "REQ-20260831-0048",
    enn: "ENN3",
    state: "Con incidencia",
    priority: "Alta",
    risk: "Riesgo de paro",
    requestedAt: "22:14",
    elapsed: "12 h 06 min",
    owner: "Titular Recibo",
    requester: "logistico.enn3",
    shift: "T3",
    notes: "Inventario insuficiente para completar",
    inherited: true,
    items: [{ part: "180610AA", requested: 3, delivered: 1, stock: 0 }],
  },
];

const inventory = [
  { part: "180324AB", rolls: 8, kg: 42867, committed: 2, locations: "05110, 05130, RA-C08", status: "Disponible" },
  { part: "190031AB", rolls: 12, kg: 68724, committed: 1, locations: "05110, 05130", status: "Disponible" },
  { part: "180296AA", rolls: 5, kg: 56559, committed: 3, locations: "05145", status: "Bajo" },
  { part: "180299AB", rolls: 7, kg: 67150, committed: 2, locations: "05155", status: "Disponible" },
  { part: "180543AA", rolls: 3, kg: 51645, committed: 2, locations: "05165", status: "Bajo" },
  { part: "180610AA", rolls: 2, kg: 10000, committed: 3, locations: "05130", status: "Insuficiente" },
];

const stateStyle = {
  "Solicitado": "bg-blue-50 text-blue-700 border-blue-200",
  "Tomado": "bg-indigo-50 text-indigo-700 border-indigo-200",
  "En preparación": "bg-cyan-50 text-cyan-700 border-cyan-200",
  "Listo para traslado": "bg-violet-50 text-violet-700 border-violet-200",
  "En traslado": "bg-amber-50 text-amber-700 border-amber-200",
  "Entrega parcial": "bg-orange-50 text-orange-700 border-orange-200",
  "Con incidencia": "bg-red-50 text-red-700 border-red-200",
  "Entregado": "bg-emerald-50 text-emerald-700 border-emerald-200",
};

const states = ["Solicitado", "Tomado", "En preparación", "Listo para traslado", "En traslado", "Entrega parcial", "Con incidencia"];

function Pill({ children, className = "" }) {
  return <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold ${className}`}>{children}</span>;
}

function Metric({ icon: Icon, label, value, detail, tone = "blue" }) {
  const tones = {
    blue: "bg-blue-50 text-blue-700",
    cyan: "bg-cyan-50 text-cyan-700",
    amber: "bg-amber-50 text-amber-700",
    red: "bg-red-50 text-red-700",
    green: "bg-emerald-50 text-emerald-700",
  };
  return (
    <Card className="border-0 shadow-sm rounded-2xl">
      <CardContent className="p-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p>
            <p className="mt-2 text-3xl font-bold text-slate-900">{value}</p>
            <p className="mt-1 text-xs text-slate-500">{detail}</p>
          </div>
          <div className={`rounded-2xl p-3 ${tones[tone]}`}><Icon size={21} /></div>
        </div>
      </CardContent>
    </Card>
  );
}

function RequestCard({ request, onOpen }) {
  const requested = request.items.reduce((a, b) => a + b.requested, 0);
  const delivered = request.items.reduce((a, b) => a + b.delivered, 0);
  return (
    <motion.button layout onClick={() => onOpen(request)} className="w-full rounded-2xl border border-slate-200 bg-white p-4 text-left shadow-sm transition hover:-translate-y-0.5 hover:border-blue-300 hover:shadow-md">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-xs font-bold text-blue-700">{request.id}</p>
          <h3 className="mt-1 text-lg font-bold text-slate-900">{request.enn}</h3>
        </div>
        {request.risk !== "Sin riesgo" && <AlertTriangle className={request.risk === "Línea detenida" ? "text-red-600" : "text-orange-500"} size={20} />}
      </div>
      <div className="mt-3 flex flex-wrap gap-1.5">
        <Pill className={request.priority === "Urgente" ? "border-orange-200 bg-orange-50 text-orange-700" : request.priority === "Alta" ? "border-amber-200 bg-amber-50 text-amber-700" : "border-slate-200 bg-slate-50 text-slate-600"}>{request.priority}</Pill>
        <Pill className="border-slate-200 bg-slate-50 text-slate-600">{request.items.length} NP</Pill>
        {request.inherited && <Pill className="border-violet-200 bg-violet-50 text-violet-700">Turno anterior</Pill>}
      </div>
      <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
        <div><p className="text-xs text-slate-500">Rollos</p><p className="font-bold text-slate-800">{delivered}/{requested} entregados</p></div>
        <div><p className="text-xs text-slate-500">Tiempo abierto</p><p className="font-bold text-slate-800">{request.elapsed}</p></div>
      </div>
      <div className="mt-3 border-t border-slate-100 pt-3">
        <p className="truncate text-xs text-slate-500">{request.owner}</p>
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
  const [logged, setLogged] = useState(false);
  const [page, setPage] = useState("resumen");
  const [sidebar, setSidebar] = useState(false);
  const [role, setRole] = useState("Especialista");
  const [ennFilter, setEnnFilter] = useState("Todos");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState(null);
  const [notify, setNotify] = useState(false);
  const [edit, setEdit] = useState(false);
  const [toast, setToast] = useState("");
  const [newItems, setNewItems] = useState([{ part: "", qty: 1 }]);

  const filteredRequests = useMemo(() => initialRequests.filter(r => (ennFilter === "Todos" || r.enn === ennFilter) && `${r.id} ${r.enn} ${r.items.map(i => i.part).join(" ")}`.toLowerCase().includes(search.toLowerCase())), [ennFilter, search]);

  const flash = (message) => {
    setToast(message);
    setTimeout(() => setToast(""), 2800);
  };

  if (!logged) {
    return (
      <div className="min-h-screen bg-slate-950 p-5 font-sans text-slate-900" style={{ backgroundImage: "radial-gradient(circle at 18% 20%, #2558D9 0, transparent 28%), radial-gradient(circle at 82% 78%, #156E89 0, transparent 25%)" }}>
        <div className="mx-auto grid min-h-[calc(100vh-40px)] max-w-6xl overflow-hidden rounded-[32px] bg-white shadow-2xl lg:grid-cols-2">
          <div className="hidden bg-[#17243A] p-12 text-white lg:flex lg:flex-col lg:justify-between">
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
              <Input defaultValue="especialista.aceros" className="mt-2 h-12 rounded-xl" />
              <label className="mt-5 block text-sm font-semibold">Contraseña</label>
              <div className="relative mt-2"><LockKeyhole className="absolute left-3 top-3.5 text-slate-400" size={18}/><Input type="password" defaultValue="demopull" className="h-12 rounded-xl pl-10" /></div>
              <label className="mt-5 block text-sm font-semibold">Vista de demostración</label>
              <select value={role} onChange={e => setRole(e.target.value)} className="mt-2 h-12 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm">
                <option>Especialista</option><option>Logístico ENN3</option><option>Titular de Recibo</option><option>Montacarguista</option><option>Gruista ENN3</option>
              </select>
              <Button onClick={() => { setLogged(true); if(role.includes("Logístico")) setPage("kanban"); }} className="mt-7 h-12 w-full rounded-xl bg-blue-600 font-bold hover:bg-blue-700">Entrar al sistema</Button>
              <p className="mt-5 text-center text-xs text-slate-400">Prototipo visual, los datos mostrados son demostrativos.</p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  const visibleNav = role.includes("Logístico") ? navItems.filter(n => !["admin"].includes(n.id)) : role.includes("Montacarguista") ? navItems.filter(n => ["resumen", "kanban", "inventario", "turno"].includes(n.id)) : navItems;

  return (
    <div className="min-h-screen bg-[#F3F6FA] font-sans text-slate-900">
      <AnimatePresence>{toast && <motion.div initial={{ y: -20, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: -20, opacity: 0 }} className="fixed left-1/2 top-5 z-[70] -translate-x-1/2 rounded-2xl bg-slate-900 px-5 py-3 text-sm font-semibold text-white shadow-xl"><Check className="mr-2 inline" size={16}/>{toast}</motion.div>}</AnimatePresence>
      <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-slate-200 bg-white px-4 lg:px-7">
        <div className="flex items-center gap-3">
          <button onClick={() => setSidebar(!sidebar)} className="rounded-xl p-2 hover:bg-slate-100 lg:hidden"><Menu size={22}/></button>
          <div className="flex items-center gap-2.5"><div className="rounded-xl bg-blue-600 p-2 text-white"><Forklift size={20}/></div><div><p className="font-bold leading-4">Pull Aceros</p><p className="text-[10px] text-slate-500">Planta 100215</p></div></div>
        </div>
        <div className="flex items-center gap-2">
          <div className="hidden rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs font-semibold text-emerald-700 sm:block">Inventario actualizado hoy 07:05</div>
          <button onClick={() => setNotify(!notify)} className="relative rounded-xl p-2 hover:bg-slate-100"><Bell size={20}/><span className="absolute right-1 top-1 h-2 w-2 rounded-full bg-red-500"/></button>
          <button className="flex items-center gap-2 rounded-xl p-2 hover:bg-slate-100"><CircleUserRound size={22}/><span className="hidden text-left sm:block"><span className="block text-xs font-bold">{role}</span><span className="block text-[10px] text-slate-500">Turno 1</span></span><ChevronDown size={15}/></button>
        </div>
      </header>

      {notify && <div className="fixed right-4 top-16 z-40 w-[calc(100%-2rem)] max-w-sm rounded-2xl border border-slate-200 bg-white p-4 shadow-xl"><div className="flex items-center justify-between"><h3 className="font-bold">Alertas</h3><button onClick={() => setNotify(false)}><X size={18}/></button></div><div className="mt-3 space-y-2"><div className="rounded-xl bg-red-50 p-3 text-sm"><b>REQ-20260901-0003</b><p className="text-xs text-red-700">Línea detenida en ENN4</p></div><div className="rounded-xl bg-orange-50 p-3 text-sm"><b>REQ-20260901-0008</b><p className="text-xs text-orange-700">Nueva solicitud urgente de ENN3</p></div><div className="rounded-xl bg-amber-50 p-3 text-sm"><b>Inventario</b><p className="text-xs text-amber-700">180610AA con disponibilidad insuficiente</p></div></div></div>}

      <aside className={`fixed bottom-0 left-0 top-16 z-40 w-64 border-r border-slate-200 bg-[#17243A] p-4 text-white transition-transform lg:translate-x-0 ${sidebar ? "translate-x-0" : "-translate-x-full"}`}>
        <nav className="space-y-1">
          {visibleNav.map(item => <button key={item.id} onClick={() => { setPage(item.id); setSidebar(false); }} className={`flex w-full items-center gap-3 rounded-xl px-3 py-3 text-sm font-semibold transition ${page === item.id ? "bg-blue-600 text-white" : "text-slate-300 hover:bg-white/10 hover:text-white"}`}><item.icon size={18}/>{item.label}</button>)}
        </nav>
        <div className="absolute bottom-4 left-4 right-4 border-t border-white/10 pt-4"><button onClick={() => setLogged(false)} className="flex w-full items-center gap-3 rounded-xl px-3 py-2 text-sm text-slate-300 hover:bg-white/10"><LogOut size={18}/>Cerrar sesión</button></div>
      </aside>

      <main className="p-4 pb-12 lg:ml-64 lg:p-7">
        {page === "resumen" && <Dashboard setPage={setPage} onOpen={setSelected} />}
        {page === "kanban" && <Kanban requests={filteredRequests} ennFilter={ennFilter} setEnnFilter={setEnnFilter} search={search} setSearch={setSearch} onOpen={setSelected} />}
        {page === "nueva" && <NewRequest newItems={newItems} setNewItems={setNewItems} role={role} flash={flash} setPage={setPage} />}
        {page === "inventario" && <Inventory flash={flash} />}
        {page === "turno" && <Shift requests={initialRequests} flash={flash} />}
        {page === "historial" && <HistoryPage flash={flash} />}
        {page === "admin" && <Admin flash={flash} />}
        {page === "simulacion" && <SimulationPage />}
      </main>

      <Modal open={!!selected} onClose={() => { setSelected(null); setEdit(false); }} size="max-w-3xl">
        {selected && <RequestDetail request={selected} edit={edit} setEdit={setEdit} flash={flash} onClose={() => setSelected(null)} />}
      </Modal>
    </div>
  );
}

function PageHead({ eyebrow, title, description, action }) {
  return <div className="mb-6 flex flex-col justify-between gap-4 md:flex-row md:items-end"><div><p className="text-xs font-bold uppercase tracking-[.18em] text-blue-700">{eyebrow}</p><h1 className="mt-1 text-2xl font-bold sm:text-3xl">{title}</h1><p className="mt-1 max-w-2xl text-sm text-slate-500">{description}</p></div>{action}</div>;
}

function Dashboard({ setPage, onOpen }) {
  return <>
    <PageHead eyebrow="Turno 1 · 01 septiembre 2026" title="Resumen operativo" description="Vista consolidada de requerimientos activos, alertas y continuidad entre turnos." action={<Button onClick={() => setPage("nueva")} className="rounded-xl bg-blue-600"><Plus size={17} className="mr-2"/>Nueva solicitud</Button>}/>
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <Metric icon={ClipboardList} label="Solicitudes activas" value="7" detail="1 heredada del turno 3" />
      <Metric icon={Boxes} label="Rollos pendientes" value="13" detail="De 22 solicitados" tone="cyan" />
      <Metric icon={AlertTriangle} label="Atención crítica" value="3" detail="1 línea detenida" tone="red" />
      <Metric icon={PackageCheck} label="Entregados hoy" value="9" detail="6 solicitudes cerradas" tone="green" />
    </div>
    <div className="mt-5 grid gap-5 xl:grid-cols-[1.4fr_.8fr]">
      <Card className="rounded-2xl border-0 shadow-sm"><CardHeader className="flex-row items-center justify-between"><CardTitle className="text-base">Prioridades activas</CardTitle><Button variant="ghost" onClick={() => setPage("kanban")} className="text-blue-700">Ver Kanban<ChevronRight size={16}/></Button></CardHeader><CardContent className="space-y-3">
        {initialRequests.filter(r => r.priority === "Urgente" || r.inherited).slice(0,3).map(r => <button key={r.id} onClick={() => onOpen(r)} className="flex w-full items-center justify-between gap-4 rounded-2xl border border-slate-100 p-4 text-left hover:bg-slate-50"><div className="flex items-center gap-3"><div className={`rounded-xl p-2.5 ${r.risk === "Línea detenida" ? "bg-red-100 text-red-700" : "bg-orange-100 text-orange-700"}`}><AlertTriangle size={19}/></div><div><p className="font-bold">{r.enn} · {r.id}</p><p className="text-xs text-slate-500">{r.items.length} NP · {r.elapsed} abierto</p></div></div><Pill className={stateStyle[r.state]}>{r.state}</Pill></button>)}
      </CardContent></Card>
      <Card className="rounded-2xl border-0 shadow-sm"><CardHeader><CardTitle className="text-base">Avance del turno</CardTitle></CardHeader><CardContent>
        <div className="flex items-end justify-between"><div><p className="text-4xl font-bold">41%</p><p className="text-xs text-slate-500">9 de 22 rollos entregados</p></div><Truck className="text-blue-600" size={35}/></div><Progress value={41} className="mt-5 h-3"/>
        <div className="mt-6 space-y-3 text-sm"><div className="flex justify-between"><span className="text-slate-500">Solicitudes nuevas</span><b>4</b></div><div className="flex justify-between"><span className="text-slate-500">En proceso</span><b>5</b></div><div className="flex justify-between"><span className="text-slate-500">Incidencias abiertas</span><b className="text-red-600">1</b></div></div>
      </CardContent></Card>
    </div>
  </>;
}

function Kanban({ requests, ennFilter, setEnnFilter, search, setSearch, onOpen }) {
  return <>
    <PageHead eyebrow="Seguimiento en vivo" title="Panel Kanban" description="Selecciona una tarjeta para consultar partidas, registrar avances, entregas o incidencias." />
    <Card className="mb-5 rounded-2xl border-0 shadow-sm"><CardContent className="flex flex-col gap-3 p-4 md:flex-row"><div className="relative flex-1"><Search className="absolute left-3 top-3 text-slate-400" size={18}/><Input value={search} onChange={e => setSearch(e.target.value)} placeholder="Buscar folio, ENN o número de parte" className="h-11 rounded-xl pl-10"/></div><select value={ennFilter} onChange={e => setEnnFilter(e.target.value)} className="h-11 rounded-xl border border-slate-200 bg-white px-4 text-sm"><option>Todos</option>{[1,2,3,4,5,6].map(n => <option key={n}>ENN{n}</option>)}</select><Button variant="outline" className="h-11 rounded-xl"><Filter size={17} className="mr-2"/>Más filtros</Button></CardContent></Card>
    <div className="flex snap-x gap-4 overflow-x-auto pb-4">
      {states.map(state => <section key={state} className="min-w-[286px] flex-1 snap-start rounded-2xl bg-slate-200/55 p-3 xl:min-w-[300px]"><div className="mb-3 flex items-center justify-between px-1"><div className="flex items-center gap-2"><span className={`h-2.5 w-2.5 rounded-full ${state === "Con incidencia" ? "bg-red-500" : state === "Entrega parcial" ? "bg-orange-500" : "bg-blue-500"}`}/><h2 className="text-sm font-bold">{state}</h2></div><Badge variant="secondary" className="rounded-full">{requests.filter(r => r.state === state).length}</Badge></div><div className="space-y-3">{requests.filter(r => r.state === state).map(r => <RequestCard key={r.id} request={r} onOpen={onOpen}/>)}{requests.filter(r => r.state === state).length === 0 && <div className="rounded-2xl border border-dashed border-slate-300 p-8 text-center text-xs text-slate-400">Sin solicitudes</div>}</div></section>)}
    </div>
  </>;
}

function NewRequest({ newItems, setNewItems, role, flash, setPage }) {
  const update = (idx, key, value) => setNewItems(newItems.map((it, i) => i === idx ? {...it, [key]: value} : it));
  return <>
    <PageHead eyebrow="Crear requerimiento" title="Nueva solicitud" description="Un mismo folio puede incluir varios números de parte y cantidades de rollos diferentes." />
    <div className="grid gap-5 xl:grid-cols-[1fr_320px]">
      <div className="space-y-5">
        <Card className="rounded-2xl border-0 shadow-sm"><CardHeader><CardTitle className="text-base">Datos generales</CardTitle></CardHeader><CardContent className="grid gap-4 md:grid-cols-2">
          <Field label="ENN destino"><select className="h-11 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 text-sm" defaultValue={role.includes("ENN3") ? "ENN3" : "ENN1"} disabled={role.includes("Logístico")}><option>ENN1</option><option>ENN2</option><option>ENN3</option><option>ENN4</option><option>ENN5</option><option>ENN6</option></select></Field>
          <Field label="Turno detectado"><Input value="Turno 1 · 06:00 a 14:00" readOnly className="h-11 rounded-xl bg-slate-50"/></Field>
          <Field label="Prioridad"><select className="h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm"><option>Normal</option><option>Alta</option><option>Urgente</option></select></Field>
          <Field label="Riesgo operativo"><select className="h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm"><option>Sin riesgo</option><option>Riesgo de paro</option><option>Línea detenida</option></select></Field>
          <Field label="Fecha y hora requerida"><Input type="datetime-local" defaultValue="2026-09-01T12:00" className="h-11 rounded-xl"/></Field>
          <Field label="Comentario general"><Input placeholder="Describe brevemente la necesidad" className="h-11 rounded-xl"/></Field>
        </CardContent></Card>
        <Card className="rounded-2xl border-0 shadow-sm"><CardHeader className="flex-row items-center justify-between"><div><CardTitle className="text-base">Números de parte</CardTitle><p className="mt-1 text-xs text-slate-500">Solo cuentan como rollos disponibles los registros DISP con más de 500 kg.</p></div><Button variant="outline" onClick={() => setNewItems([...newItems, {part:"", qty:1}])} className="rounded-xl"><Plus size={16} className="mr-2"/>Agregar NP</Button></CardHeader><CardContent className="space-y-3">
          {newItems.map((item, idx) => <motion.div layout key={idx} className="grid items-end gap-3 rounded-2xl border border-slate-200 p-4 md:grid-cols-[1fr_130px_170px_40px]"><Field label={`Número de parte ${idx+1}`}><Input value={item.part} onChange={e => update(idx,"part",e.target.value.toUpperCase())} placeholder="Ej. 180324AB" className="h-11 rounded-xl"/></Field><Field label="Rollos"><Input type="number" min="1" value={item.qty} onChange={e => update(idx,"qty",e.target.value)} className="h-11 rounded-xl"/></Field><div className="rounded-xl bg-emerald-50 p-3 text-xs text-emerald-700"><b>Disponibilidad</b><p>{item.part ? "Consultar al capturar NP" : "Pendiente de consulta"}</p></div><button disabled={newItems.length === 1} onClick={() => setNewItems(newItems.filter((_,i) => i!==idx))} className="mb-1 rounded-xl p-2 text-slate-400 hover:bg-red-50 hover:text-red-600 disabled:opacity-30"><X size={18}/></button></motion.div>)}
        </CardContent></Card>
      </div>
      <div><Card className="sticky top-24 rounded-2xl border-0 shadow-sm"><CardHeader><CardTitle className="text-base">Resumen</CardTitle></CardHeader><CardContent className="space-y-4 text-sm"><div className="flex justify-between"><span className="text-slate-500">Partidas</span><b>{newItems.length}</b></div><div className="flex justify-between"><span className="text-slate-500">Rollos solicitados</span><b>{newItems.reduce((a,b)=>a+(Number(b.qty)||0),0)}</b></div><div className="rounded-xl bg-blue-50 p-3 text-xs text-blue-700">El folio, usuario, fecha operativa y turno se guardarán automáticamente.</div><Button onClick={() => { flash("Solicitud REQ-20260901-0009 creada"); setPage("kanban"); }} className="h-12 w-full rounded-xl bg-blue-600"><ClipboardList size={17} className="mr-2"/>Disparar requerimiento</Button><Button variant="outline" className="h-11 w-full rounded-xl">Guardar borrador</Button></CardContent></Card></div>
    </div>
  </>;
}

function Field({ label, children }) { return <label className="block"><span className="mb-1.5 block text-xs font-semibold text-slate-600">{label}</span>{children}</label>; }

function Inventory({ flash }) {
  const [q,setQ]=useState("");
  const rows=inventory.filter(i=>i.part.toLowerCase().includes(q.toLowerCase()));
  return <><PageHead eyebrow="Fuente QAD · actualización diaria" title="Inventario de rollos" description="La disponibilidad considera únicamente registros con estatus DISP y cantidad mayor a 500 kg." action={<Button onClick={() => flash("Selecciona el archivo QAD del día")} className="rounded-xl bg-blue-600"><Upload size={17} className="mr-2"/>Actualizar inventario</Button>}/>
    <div className="mb-5 grid gap-4 sm:grid-cols-3"><Metric icon={Boxes} label="Rollos disponibles" value="865" detail="Después de aplicar regla > 500 kg"/><Metric icon={Archive} label="Comprometidos" value="28" detail="En solicitudes activas" tone="amber"/><Metric icon={RefreshCw} label="Última actualización" value="07:05" detail="01 septiembre 2026" tone="green"/></div>
    <Card className="rounded-2xl border-0 shadow-sm"><CardContent className="p-0"><div className="flex flex-col gap-3 border-b border-slate-100 p-4 md:flex-row"><div className="relative flex-1"><Search className="absolute left-3 top-3 text-slate-400" size={18}/><Input value={q} onChange={e=>setQ(e.target.value)} placeholder="Buscar número de parte" className="h-11 rounded-xl pl-10"/></div><Button variant="outline" className="h-11 rounded-xl"><Filter size={17} className="mr-2"/>Ubicación</Button></div><div className="overflow-x-auto"><table className="w-full min-w-[850px] text-left text-sm"><thead className="bg-slate-50 text-xs uppercase text-slate-500"><tr>{["Número de parte","Rollos","Kg disponibles","Comprometidos","Disponibilidad neta","Ubicaciones","Estado"].map(h=><th className="px-5 py-3" key={h}>{h}</th>)}</tr></thead><tbody>{rows.map(r=><tr key={r.part} className="border-t border-slate-100 hover:bg-slate-50"><td className="px-5 py-4 font-bold text-blue-700">{r.part}</td><td className="px-5 py-4 font-semibold">{r.rolls}</td><td className="px-5 py-4">{r.kg.toLocaleString()} kg</td><td className="px-5 py-4">{r.committed}</td><td className="px-5 py-4 font-bold">{r.rolls-r.committed}</td><td className="px-5 py-4 text-xs text-slate-500">{r.locations}</td><td className="px-5 py-4"><Pill className={r.status==="Disponible"?"border-emerald-200 bg-emerald-50 text-emerald-700":r.status==="Bajo"?"border-amber-200 bg-amber-50 text-amber-700":"border-red-200 bg-red-50 text-red-700"}>{r.status}</Pill></td></tr>)}</tbody></table></div></CardContent></Card>
  </>;
}

function Shift({ requests, flash }) {
  const inherited=requests.filter(r=>r.inherited||["Entrega parcial","Con incidencia"].includes(r.state));
  return <><PageHead eyebrow="Continuidad operativa" title="Cambio de turno" description="Los pendientes permanecen activos automáticamente. Agrega notas únicamente cuando el siguiente turno necesite contexto adicional." action={<Button onClick={()=>flash("Entrega de turno registrada")} className="rounded-xl bg-blue-600"><Check size={17} className="mr-2"/>Registrar entrega de turno</Button>}/>
    <div className="grid gap-4 sm:grid-cols-3"><Metric icon={Clock3} label="Pendientes a entregar" value="7" detail="Todos continúan activos"/><Metric icon={AlertTriangle} label="Críticos" value="3" detail="Requieren seguimiento prioritario" tone="red"/><Metric icon={Users} label="Turno entrante" value="T2" detail="Inicia a las 14:00" tone="cyan"/></div>
    <div className="mt-5 grid gap-5 xl:grid-cols-[1fr_340px]"><Card className="rounded-2xl border-0 shadow-sm"><CardHeader><CardTitle className="text-base">Pendientes destacados</CardTitle></CardHeader><CardContent className="space-y-3">{inherited.map(r=><div key={r.id} className="rounded-2xl border border-slate-200 p-4"><div className="flex flex-wrap items-start justify-between gap-2"><div><p className="font-bold">{r.enn} · {r.id}</p><p className="text-xs text-slate-500">{r.items.map(i=>`${i.part}: ${i.requested-i.delivered} pendiente(s)`).join(" · ")}</p></div><Pill className={stateStyle[r.state]}>{r.state}</Pill></div><p className="mt-3 rounded-xl bg-slate-50 p-3 text-xs text-slate-600">{r.notes}</p></div>)}</CardContent></Card><Card className="rounded-2xl border-0 shadow-sm"><CardHeader><CardTitle className="text-base">Nota para el siguiente turno</CardTitle></CardHeader><CardContent><textarea className="min-h-44 w-full resize-none rounded-xl border border-slate-200 p-3 text-sm" placeholder="Ej. La plana interna queda asignada para completar ENN4..."/><div className="mt-4 rounded-xl bg-blue-50 p-3 text-xs text-blue-700">No es necesario copiar todos los folios. El sistema conserva y muestra automáticamente los pendientes.</div></CardContent></Card></div>
  </>;
}

function HistoryPage({ flash }) {
  return <><PageHead eyebrow="Consulta mensual" title="Historial y exportación" description="Consulta solicitudes, partidas, entregas, incidencias y modificaciones del periodo seleccionado." action={<Button onClick={()=>flash("Historial mensual preparado para Excel")} className="rounded-xl bg-emerald-600 hover:bg-emerald-700"><FileSpreadsheet size={17} className="mr-2"/>Descargar Excel</Button>}/><Card className="rounded-2xl border-0 shadow-sm"><CardContent className="p-5"><div className="grid gap-3 md:grid-cols-4"><Field label="Mes"><select className="h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm"><option>Septiembre</option><option>Agosto</option></select></Field><Field label="Año"><select className="h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm"><option>2026</option></select></Field><Field label="ENN"><select className="h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm"><option>Todos</option><option>ENN1</option><option>ENN2</option><option>ENN3</option></select></Field><Field label="Estado"><select className="h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm"><option>Todos</option><option>Entregado</option><option>Cancelado</option><option>Con incidencia</option></select></Field></div></CardContent></Card><div className="mt-5 grid gap-4 sm:grid-cols-3"><Metric icon={ClipboardList} label="Solicitudes del mes" value="48" detail="42 cerradas y 6 activas"/><Metric icon={Boxes} label="Rollos entregados" value="126" detail="De 139 solicitados" tone="green"/><Metric icon={Pencil} label="Modificaciones" value="9" detail="Todas con justificación" tone="amber"/></div><Card className="mt-5 rounded-2xl border-0 shadow-sm"><CardHeader><CardTitle className="text-base">Movimientos recientes</CardTitle></CardHeader><CardContent className="space-y-2">{["REQ-20260901-0003 · Entrega parcial registrada · 09:46","REQ-20260901-0008 · Solicitud creada · 09:42","REQ-20260901-0007 · Responsable asignado · 09:25","REQ-20260901-0005 · Estado cambiado a Listo para traslado · 09:12"].map((x,i)=><div key={i} className="flex items-center gap-3 rounded-xl bg-slate-50 p-3 text-sm"><History size={17} className="text-blue-600"/><span>{x}</span></div>)}</CardContent></Card></>;
}

function Admin({ flash }) {
  return <><PageHead eyebrow="Configuración" title="Administración" description="Gestiona usuarios, permisos, catálogos, carga diaria y reglas generales del sistema."/><div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{[
    {icon:UserCog,title:"Usuarios y accesos",desc:"15 cuentas activas, roles y ENN asignado",action:"Gestionar usuarios"},
    {icon:Warehouse,title:"Carga de inventario",desc:"Última actualización hoy a las 07:05",action:"Cargar Excel"},
    {icon:ShieldCheck,title:"Roles y permisos",desc:"Logístico, gruista, recibo y especialista",action:"Revisar permisos"},
    {icon:Boxes,title:"Regla de rollo",desc:"DISP y cantidad mayor a 500 kg",action:"Ver configuración"},
    {icon:Clock3,title:"Turnos",desc:"T1 06:00, T2 14:00, T3 21:30",action:"Configurar turnos"},
    {icon:Download,title:"Respaldos mensuales",desc:"Archivo mensual e historial exportable",action:"Consultar respaldos"},
  ].map(({icon:Icon,title,desc,action})=><Card key={title} className="rounded-2xl border-0 shadow-sm"><CardContent className="p-5"><div className="flex items-start justify-between"><div className="rounded-2xl bg-blue-50 p-3 text-blue-700"><Icon size={22}/></div><ChevronRight className="text-slate-300"/></div><h3 className="mt-5 font-bold">{title}</h3><p className="mt-1 min-h-10 text-sm text-slate-500">{desc}</p><Button onClick={()=>flash(`${action}: módulo de demostración`)} variant="outline" className="mt-4 w-full rounded-xl">{action}</Button></CardContent></Card>)}</div></>;
}

function RequestDetail({ request, edit, setEdit, flash, onClose }) {
  const requested=request.items.reduce((a,b)=>a+b.requested,0), delivered=request.items.reduce((a,b)=>a+b.delivered,0);
  return <div><div className="flex items-start justify-between border-b border-slate-100 p-6"><div><div className="flex flex-wrap items-center gap-2"><h2 className="text-xl font-bold">{request.id}</h2><Pill className={stateStyle[request.state]}>{request.state}</Pill></div><p className="mt-1 text-sm text-slate-500">{request.enn} · Solicitado {request.requestedAt} · {request.shift}</p></div><button onClick={onClose} className="rounded-xl p-2 hover:bg-slate-100"><X size={20}/></button></div><div className="p-6">
    <div className="grid gap-3 sm:grid-cols-4"><Info label="Prioridad" value={request.priority}/><Info label="Riesgo" value={request.risk}/><Info label="Responsable" value={request.owner}/><Info label="Tiempo abierto" value={request.elapsed}/></div>
    <div className="mt-6"><h3 className="font-bold">Partidas del requerimiento</h3><div className="mt-3 overflow-hidden rounded-2xl border border-slate-200"><table className="w-full text-left text-sm"><thead className="bg-slate-50 text-xs text-slate-500"><tr><th className="p-3">Número de parte</th><th className="p-3">Solicitados</th><th className="p-3">Entregados</th><th className="p-3">Pendientes</th><th className="p-3">Stock neto</th></tr></thead><tbody>{request.items.map(i=><tr key={i.part} className="border-t border-slate-100"><td className="p-3 font-bold text-blue-700">{i.part}</td><td className="p-3">{i.requested}</td><td className="p-3">{i.delivered}</td><td className="p-3 font-bold">{i.requested-i.delivered}</td><td className="p-3">{i.stock}</td></tr>)}</tbody></table></div></div>
    <div className="mt-5 rounded-2xl bg-slate-50 p-4"><p className="text-xs font-semibold text-slate-500">COMENTARIO MÁS RECIENTE</p><p className="mt-1 text-sm">{request.notes}</p></div>
    {edit && <motion.div initial={{opacity:0,y:-5}} animate={{opacity:1,y:0}} className="mt-5 rounded-2xl border border-amber-200 bg-amber-50 p-4"><div className="flex gap-2 text-amber-800"><AlertTriangle size={19}/><div><p className="font-bold">La modificación quedará en la bitácora</p><p className="text-xs">Es obligatorio indicar el motivo y la justificación antes de guardar.</p></div></div><div className="mt-4 grid gap-3 sm:grid-cols-2"><Field label="Motivo"><select className="h-11 w-full rounded-xl border border-amber-200 bg-white px-3 text-sm"><option>Error de captura</option><option>Cambio de programa</option><option>Cambio de cantidad</option><option>Cambio de número de parte</option></select></Field><Field label="Justificación"><Input placeholder="Explica por qué se realiza el cambio" className="h-11 rounded-xl bg-white"/></Field></div></motion.div>}
    <div className="mt-6 flex flex-wrap justify-end gap-2"><Button variant="outline" onClick={()=>setEdit(!edit)} className="rounded-xl"><Pencil size={16} className="mr-2"/>{edit?"Cancelar edición":"Modificar"}</Button><Button variant="outline" onClick={()=>flash("Incidencia registrada")} className="rounded-xl text-red-700"><AlertTriangle size={16} className="mr-2"/>Incidencia</Button><Button onClick={()=>flash(request.state==="Entrega parcial"?"Entrega adicional registrada":"Estado actualizado")} className="rounded-xl bg-blue-600"><Truck size={16} className="mr-2"/>{request.state==="Entrega parcial"?"Registrar entrega":"Avanzar estado"}</Button>{edit&&<Button onClick={()=>{flash("Modificación guardada en bitácora");setEdit(false)}} className="rounded-xl bg-amber-600 hover:bg-amber-700">Guardar modificación</Button>}</div>
    <div className="mt-5 border-t border-slate-100 pt-4 text-xs text-slate-500">Avance total: {delivered} de {requested} rollos · Solicitante: {request.requester}</div>
  </div></div>;
}

function Info({label,value}) { return <div className="rounded-xl bg-slate-50 p-3"><p className="text-[10px] font-bold uppercase text-slate-500">{label}</p><p className="mt-1 text-sm font-semibold">{value}</p></div>; }

