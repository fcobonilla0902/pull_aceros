# Meta-Ride / Pull Aceros

Aplicación local React + Vite + Tailwind y FastAPI + SimPy, con PostgreSQL persistente, SQLAlchemy y Alembic. Se conserva el proyecto original y sus datos. SQLite queda como compatibilidad para pruebas y archivo previo a la migración.

## Ejecutar

Requisitos: Node.js/npm y Python 3.12. Sin Docker.

En la raíz:

```powershell
npm install
npm run dev
```

En otra terminal:

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\run.ps1
```

El script verifica dependencias, aplica migraciones, respalda la base existente y solicita una contraseña inicial de al menos 12 caracteres si no hay usuarios. Inicia sesión con usuario **admin** y esa contraseña. No hay contraseña predeterminada. En arranques posteriores la contraseña permanece hasheada en la base de datos y no se solicita nuevamente en terminal.

Frontend: http://localhost:5173. API y documentación: http://127.0.0.1:8000/docs. Vite redirige /api y /simular a FastAPI; conserva el origen de las cookies.

Alternativa manual al script:

```powershell
cd backend
.\.venv\Scripts\python.exe -m alembic upgrade head
$env:METARIDE_ADMIN_PASSWORD = 'elige-una-clave-larga-y-unica'
.\.venv\Scripts\python.exe -m uvicorn main:app --reload
```

La variable solo se usa al crear la primera cuenta. No compartas contraseñas ni archivos de base de datos en Git.

## Primer recorrido

1. En Administración crea números de parte y especificaciones, ubicaciones y montacargas. Crea cuentas de Producción, Logística y Operador.
2. En Inventario registra rollos con código único, número de parte, ubicación y kg. La regla heredada exige DISP y >500 kg para reservar.
3. Producción crea una solicitud con estampadora, proceso, prioridad, riesgo, punto de entrega, fecha/hora y partidas; puede seleccionar un rollo específico.
4. Logística abre la tarjeta Kanban, valida y reserva stock; asigna operador y montacargas opcional; registra preparación, localización y traslado.
5. Confirma entrega completa o selecciona rollos para una entrega parcial, indicando responsable. Incidencias registran causa y si existe paro de Producción; requieren descripción y resolución.
6. Consulta indicadores por periodo, movimientos por turno y causas de retraso; exporta CSV. En Cambio de turno selecciona destinatario y registra notas. La persona entrante inicia sesión y acepta digitalmente los pendientes; queda evidencia con usuario, hora y copia del estado al entregar.
7. Ejecuta SimPy y compara recursos o FIFO/urgentes; las simulaciones quedan guardadas. Las opciones avanzadas permiten variar duración del turno, localización, incidencias, distribuciones y plazo de entrega. Los rangos históricos de preparación/traslado requieren cinco muestras válidas por etapa. El riesgo simulado de paro es hipotético y depende de una tolerancia configurable.

Las pantallas inician sin datos operativos ficticios. Los roles y permisos se comprueban también en el servidor.

Producción registra solicitudes; Logística coordina validación, asignación y modificaciones; el operador avanza sus movimientos asignados. La recepción de turno está disponible para personal autorizado y debe confirmarla una persona distinta de quien entrega.

## Persistencia y configuración

Motor activo: PostgreSQL local, base `metaride` en `127.0.0.1:5432`. La conexión privada se carga desde `backend/.env`. Los archivos del clúster están en `backend/.postgres/data/`; no se editan a mano. Alembic administra el esquema. Respaldos: Administración o `manage.py backup`, formato `.dump`. La SQLite previa se conservó y ya no recibe operaciones. Ver [docs/POSTGRESQL.md](docs/POSTGRESQL.md).

Variables opcionales:

- `DATABASE_URL`: URL SQLAlchemy PostgreSQL con psycopg, guardada privadamente en backend/.env tras la copia verificada. Una variable explícita permite usar una base aislada de pruebas.
- `PG_BIN`: carpeta con pg_ctl, pg_dump y pg_restore.
- `PG_LOCAL_AUTOSTART=true`: run.ps1 inicia el clúster local si es necesario.
- `BACKUP_DIR`: carpeta local de respaldos; predeterminada `backend/backups`.
- `METARIDE_ADMIN_PASSWORD`: contraseña de arranque inicial, mínimo 12 caracteres.
- `COOKIE_SECURE=true`: obligatorio al servir remotamente por HTTPS; mantener false en desarrollo HTTP local.
- `PLANT_TIMEZONE`: zona IANA para indicadores de turno; predeterminada `America/Monterrey`. T1 06:00–14:00, T2 14:00–21:30, T3 21:30–06:00. El turno nocturno se atribuye al día de su inicio.
- `CORS_ORIGINS`: orígenes permitidos separados por comas, sin espacios. Por defecto localhost/127.0.0.1 en puertos 5173 y 5174.
- `VITE_API_URL`: origen API si no se usa proxy. `VITE_SIM_API` se conserva como alternativa compatible. En un despliegue debe configurarse proxy al backend para API y simulación y permitir el origen correspondiente en CORS si se separan.

Las sesiones opacas duran ocho horas; las cookies son HttpOnly y SameSite=Strict. Contraseñas scrypt con sal aleatoria. No se almacenan tokens en localStorage. El backend limita intentos fallidos de login y registra operaciones en bitácora.

## Verificación

```powershell
npm run lint
npm run build
cd backend
.\.venv\Scripts\python.exe -m unittest test_integration
```

Las pruebas usan una base temporal independiente. No modifican la SQLite operativa.

Prueba opcional con Chrome instalado, sin ventana y con base/perfil temporales:

```powershell
backend\.venv\Scripts\python.exe backend\check_browser.py
```

Utiliza puertos locales 8107, 5179 y 9337, que deben estar libres. Guarda una captura en `artifacts/resumen-browser.png` (datos de prueba). Comprueba crear/editar usuarios, importar CSV, editar cantidades y reservas, flujo completo, respaldo, cambio de contraseña, entrega/aceptación de turno, SimPy y ancho móvil.

Correspondencia con la propuesta suministrada: [docs/REQUISITOS_DOCUMENTO.md](docs/REQUISITOS_DOCUMENTO.md).

Guía de usuarios, contraseñas, edición de solicitudes, importación Excel/CSV de QAD, catálogos y recuperación: [docs/MANTENIMIENTO_LOCAL.md](docs/MANTENIMIENTO_LOCAL.md). Las funciones de mantenimiento local están implementadas. PostgreSQL es el motor activo y está probado con transacciones simultáneas; la simulación todavía requiere datos reales para validación industrial. Migración, credenciales técnicas, archivos y respaldo: [docs/POSTGRESQL.md](docs/POSTGRESQL.md).
