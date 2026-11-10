# Auditoría del prototipo y decisiones

Fecha: 6 de noviembre de 2026.

## Estado encontrado

Git tenía `src/SimulationPage.jsx` modificado y `Microsoft/` sin seguimiento. No se restauraron estos cambios ni se escribió en Microsoft. La integración en SimulationPage conserva sus controles, valores iniciales y comparación de 1 a 4 montacargas.

En la primera auditoría no se encontró PDF y el mensaje técnico terminaba en «montacargas y disponi». Posteriormente el usuario proporcionó el texto completo de la propuesta funcional, que es ahora la fuente principal. Su correspondencia con el código y las definiciones operativas se registran en [REQUISITOS_DOCUMENTO.md](REQUISITOS_DOCUMENTO.md).

## Archivos y conexiones originales

- `index.html` carga `src/main.jsx`, que monta App bajo StrictMode e importa index.css.
- `App.jsx` contenía navegación por estado local, login demostrativo, resumen, Kanban, creación, inventario, turno, historial, administración y modal. No había router de URLs ni cliente API operativo. Solicitudes e inventario eran arreglos constantes. Login no verificaba contraseña y el selector permitía asumir roles. Crear, modificar, entregar, incidencia, exportar, cargar y turno únicamente disparaban mensajes. Métricas, fechas y alertas eran fijas.
- `SimulationPage.jsx` era la única pantalla conectada al servidor: POST /simular, comparación de cuatro escenarios, manejo de errores y resultados. Existían cambios locales previos para simplificar parámetros. Se conservaron.
- `backend/main.py` exponía GET /salud y POST /simular; parámetros Pydantic y motor SimPy sin base de datos, usuarios ni persistencia. Se identificó que el montacargas quedaba ocupado durante preparación pese al comentario del modelo. Se adquiere ahora después de preparar.
- `components/ui/{button,card,input,badge,progress}.jsx`, `lib/utils.js` y estilos suministran componentes Tailwind/Base UI y utilidades. Se conservaron; se limpiaron imports y exports auxiliares no consumidos que impedían ESLint.
- `App.css` conserva estilos del arranque Vite y no se importa por App; no interviene en el tablero. Assets hero/react/vite permanecen.
- `vite.config.js` usa React, Tailwind y alias @; se agregó proxy local a FastAPI. `eslint.config.js`, `components.json`, `jsconfig.json`, manifiesto y lock de npm se conservaron salvo el import explícito de process en Vite.
- Dependencias existentes: React, ReactDOM, Vite, Tailwind, Base UI, framer-motion, Lucide, Recharts, shadcn, cn y class-variance-authority. No se añadió framework frontend. Backend agrega SQLAlchemy y Alembic; httpx permite pruebas de API.

## Resultado y arquitectura

React conserva login, navegación, colores, tarjetas Kanban y modal; Operations.jsx contiene formularios reales, ShiftPage.jsx gestiona entrega/aceptación y Reports.jsx muestra indicadores por periodo. api.js usa cookies HttpOnly y errores Pydantic. FastAPI separa schemas, autenticación, acceso a datos y API. SQLAlchemy utiliza ahora PostgreSQL persistente; SQLite se conserva para compatibilidad y pruebas aisladas. Alembic conserva una instantánea independiente de la migración inicial. La migración verificada a PostgreSQL está completada, con psycopg, restauración validada y pruebas de concurrencia. Detalles en [POSTGRESQL.md](POSTGRESQL.md).

Tablas: roles, permissions, role_permissions, users, sessions, processes, presses, parts, locations, forklifts, requests, request_items, rolls, incidents, audit, handovers, handover_items, simulation_runs, inventory_imports. Solicitudes relacionan estampadora, proceso, solicitante, operador y montacargas; partidas relacionan número de parte y cantidad; rollos identifican unidad física, peso, ubicación y reserva. Restricciones únicas impiden códigos repetidos y partidas duplicadas. Reservas y cambios se confirman en una transacción. La versión de solicitud evita aplicar avances sobre información obsoleta.

Flujo: Solicitado → Validado → Tomado → En preparación → Listo para traslado → En traslado → Entregado / Entrega parcial. Las incidencias recuerdan el estado anterior y exigen resolución; cancelación exige motivo y libera solo los rollos no entregados. Entregas parciales identifican rollos físicos y responsable en bitácora. Solicitudes cerradas no admiten avances. Cambios de prioridad exigen justificación.

## Supuestos y límites explícitos

- ENN1–ENN6 y procesos Blancos/Formados son catálogos iniciales. No se inventaron inventario ni solicitudes productivas. Admin crea partes con especificación, ubicaciones, montacargas y usuarios.
- La unidad de inventario es un rollo con código único. Se reserva por número de parte/especificación; FIFO por identificador y solo DISP con peso >500 kg, regla encontrada en el prototipo. Producción puede seleccionar un código de rollo específico por partida de cantidad 1; la validación respeta ese código y rechaza su reserva si ya no está disponible.
- No hay matriz de compatibilidad estampadora–parte–proceso porque no existe fuente que la defina. Logística debe verificar la especificación del catálogo al validar.
- Cada solicitud admite un operador y montacargas opcional; no se permite compartir operador entre solicitudes abiertas. La cancelación de un pendiente parcialmente entregado conserva la trazabilidad del material ya entregado.
- Fechas almacenadas en UTC; el navegador captura y muestra hora local. El turno y responsable entrantes se seleccionan explícitamente. Los pendientes continúan activos y se conserva una copia por folio al entregar; la recepción digital requiere otra cuenta autorizada y registra usuario/fecha/hora. Indicadores usan America/Monterrey (configurable), T1 06:00, T2 14:00 y T3 21:30; no hay calendarios editables.
- Roles: Administrador, Producción, Logística y Operador. Son roles efectivos del servidor; no hay selector para asumir identidades. Se editan cuentas, roles y estado activo y se restablecen/cambian contraseñas con revocación de sesiones. No existe restricción por ENN de cada usuario, recuperación por correo ni edición de los permisos internos de los cuatro roles.
- Inventario mediante captura individual o importación XLSX/CSV con mapeo de columnas de QAD, revisión previa y confirmación transaccional. Se ofrecen plantillas Excel/CSV. La edición de solicitudes ajusta reservas, conserva entregas y obliga a repetir preparación si cambia el material asignado; bloquea cambios físicos durante traslado. Reglas y uso en [MANTENIMIENTO_LOCAL.md](MANTENIMIENTO_LOCAL.md).
- Actualización cada 30 segundos, sin WebSockets. Historial visible: últimos 2000 eventos; exportación incluye todos. Entregas de turno: últimos 100. Simulaciones: últimas 50, interfaz muestra 10.
- El modelo SimPy usa llegadas uniformes y duraciones uniformes o triangulares. Incluye localización, preparación, traslado, incidentes configurables que ocupan ambos recursos en ruta y prioridad no expropiativa FIFO/urgentes en ambas colas. Expone retraso contra plazo y riesgo hipotético de paro por tolerancia; no modela rutas geométricas, compatibilidades ni fallos de equipo individuales. Rangos históricos se ofrecen desde cinco muestras por etapa en entregas sin incidencias, con duración >0 y ≤120 minutos; si faltan muestras se mantienen supuestos originales. Requiere validar representatividad y ajuste de distribuciones antes de usar para planeación industrial.
- Arranque local sin Docker. El despliegue remoto debe servir por HTTPS y activar COOKIE_SECURE=true. No se publicaron servicios. Existen respaldos desde Administración, copia automática al iniciar con run.ps1 y restauración local con backend detenido y copia previa de recuperación.

## API

- GET /salud; POST /simular (permiso simulate; guarda resultado).
- POST /api/auth/login, /api/auth/logout; GET /api/auth/me.
- GET /api/catalogs; POST /api/catalogs/{parts|locations|forklifts|presses|processes}.
- GET/POST /api/users (admin); GET/POST /api/inventory (escritura inventory).
- GET/POST /api/requests; POST /api/requests/{id}/actions (operate).
- GET /api/history, /api/history/export, /api/metrics, /api/metrics/export; métricas admiten start/end por fecha local.
- GET/POST /api/handovers; POST /api/handovers/{id}/accept. GET /api/simulations, /api/simulations/calibration.

## Validación

Pruebas de integración usan SQLite temporal y migraciones reales: sesiones, acceso anónimo, permisos de Producción, idempotencia, reserva elegible, falta de inventario con rollback, transición inválida, concurrencia optimista, asignación, incidencia/resolución, entrega con responsable, cancelación, notas de turno, indicadores, exportación y simulación reproducible/persistida. Se ejecutan además ESLint y compilación Vite. check_browser.py permite comprobar el flujo real con Chrome headless y servidores/base/perfil temporales. Se ejecutaron 25 pruebas funcionales y de concurrencia contra PostgreSQL y un recorrido real de navegador sobre otra PostgreSQL temporal.

## Mantenimiento completado

La migración 0005 incorpora estado activo y versiones de usuarios/catálogos/rollos, e importaciones revisadas. Rutas nuevas: PATCH /api/users/{id}; POST /api/users/{id}/password; POST /api/auth/password; PATCH /api/catalogs/{kind}/{id}; PATCH /api/requests/{id}; GET /api/inventory/import/template; POST /api/inventory/import/preview y /commit; GET/POST /api/backups y GET /api/backups/{nombre}. La restauración se realiza mediante manage.py y requiere backend detenido.

La suite se amplió a 17 pruebas de integración. El recorrido de Chrome comprobó creación/edición de usuario, importación, edición de partidas, entrega, respaldo y cambio de contraseña, además del flujo anterior. Se preservaron los datos capturados por el usuario y se creó respaldo antes de migrar.

## PostgreSQL activado

La migración 0006 agrega índices únicos parciales para recursos activos. La base metaride en PostgreSQL 17.11 está activa, con metaride_app sin privilegios de superusuario. La copia final verificó 19 tablas y 84 registros, mantuvo las seis cuentas y conservó SQLite antes del cambio. Los respaldos operativos se producen con pg_dump; restauración con pg_restore, validación previa temporal, bloqueo de mantenimiento y copia de recuperación. Ver POSTGRESQL.md.
