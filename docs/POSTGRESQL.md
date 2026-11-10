# PostgreSQL local de Meta-Ride

La base activa es **PostgreSQL 17.11**, en `127.0.0.1:5432`, base `metaride`, cuenta de servicio `metaride_app`. La cuenta no es superusuario y no puede crear bases ni roles. Los usuarios y contraseñas de la web son independientes de esta cuenta técnica y se conservaron durante la migración.

## Arranque habitual

Desde la raíz:

```powershell
npm run dev
```

En otra terminal:

```powershell
cd backend
.\run.ps1
```

El script inicia PostgreSQL local si está detenido, aplica migraciones, crea un respaldo y arranca FastAPI. No requiere Docker, un servicio de pago, un servicio global de Windows ni abrir el puerto de la base a la red. PostgreSQL escucha exclusivamente en IPv4 local.

Comprobaciones:

```powershell
.\.venv\Scripts\python.exe manage.py info
.\.venv\Scripts\python.exe local_postgres.py status
```

`http://127.0.0.1:8000/salud` y `http://localhost:5173/salud` informan `database: postgresql`. `manage.py info` no muestra contraseñas.

## Dónde se guarda

| Archivo/carpeta | Función |
|---|---|
| `backend/.env` | Conexión privada de la aplicación y ruta de utilidades |
| `backend/.postgres/data/` | Archivos del clúster PostgreSQL; no editarlos a mano |
| `backend/.postgres/pgsql/` | Binarios PostgreSQL locales |
| `backend/.postgres/credentials.json` | Credenciales privadas del clúster y la cuenta de servicio |
| `backend/backups/*.dump` | Respaldos lógicos de PostgreSQL |
| `backend/backups/antes-postgresql-*.db` | Copia SQLite tomada al migrar |
| `backend/metaride.db` | Base SQLite anterior, conservada como archivo previo al cambio |
| `backend/migration-reports/*.json` | Conteos y huellas SHA-256 por tabla de la copia verificada |

Estos datos y credenciales están excluidos de Git. Vite no sirve los archivos de `backend/` ni los archivos `.env`. Si falta la configuración después de activar PostgreSQL, la aplicación falla con un mensaje explícito y no cambia silenciosamente a la SQLite antigua.

PostgreSQL puede mantenerse en segundo plano cuando se cierra FastAPI. Para detenerlo, primero detén el backend y después ejecuta:

```powershell
.\.venv\Scripts\python.exe local_postgres.py stop
```

## Qué se migró y cómo

La copia conserva IDs, contraseñas hasheadas, permisos, usuarios, catálogos, ubicaciones, rollos, reservas, solicitudes, partidas, entregas, incidencias, eventos, transferencias de turno, simulaciones, sesiones e importaciones.

La herramienta `migrate_postgres.py`:

1. Exige detener la API SQLite antes de activar el cambio.
2. Obtiene una copia consistente con la API de backup de SQLite y verifica integridad y claves foráneas.
3. Actualiza el esquema de la copia, sin cambiar el archivo SQLite original.
4. Rechaza un destino PostgreSQL que ya contenga datos.
5. Copia en una transacción y compara todas las filas, tabla por tabla, mediante huellas normalizadas.
6. Ajusta las secuencias para que las próximas inserciones no reutilicen IDs existentes.
7. Solo después de verificarlo guarda `.env` y marca PostgreSQL como motor activo.

La activación final verificó **19 tablas y 84 registros**. Se conservaron los **6 usuarios, 1 parte, 1 ubicación, 2 rollos y 1 solicitud** que había en ese momento, además de sus registros relacionados. La verificación no agregó registros de demostración a la base activa.

## Reservas simultáneas

Se utilizan transacciones, versiones, bloqueos de filas y `FOR UPDATE SKIP LOCKED` para reservar rollos disponibles sin duplicarlos y permitir que otros movimientos avancen en paralelo. Índices únicos parciales impiden asignar un operador o montacargas a dos solicitudes abiertas, incluso si se intenta omitir la validación de aplicación.

Los cambios de catálogos se coordinan con la reserva para evitar desactivar una ubicación mientras se compromete material. Los conflictos transaccionales se devuelven como errores 409 que permiten actualizar y reintentar. El arranque de usuarios/roles también se serializa para admitir varias instancias de API sobre la misma PostgreSQL.

## Respaldos y restauración

Administración conserva el mismo flujo de crear y descargar respaldos. Ahora se utiliza **pg_dump en formato personalizado `.dump`**, con una copia consistente mientras la aplicación funciona. Las copias SQLite antiguas se identifican y pueden descargarse, pero no se ofrecen para restaurar directamente sobre PostgreSQL.

Crear desde terminal:

```powershell
.\.venv\Scripts\python.exe manage.py backup
```

Restaurar con el backend detenido:

```powershell
.\.venv\Scripts\python.exe manage.py restore "metaride-FECHA-CODIGO.dump" --confirm RESTAURAR
.\run.ps1
```

La restauración adquiere un bloqueo exclusivo de mantenimiento. Rechaza la operación si una API está usando la base. Primero restaura el archivo en una base temporal para comprobar formato, esquema y administrador activo; después crea un respaldo del estado actual y restaura la base mediante una transacción. Revoca sesiones e importaciones pendientes y registra el evento.

La cuenta de aplicación no tiene permiso de crear bases. La validación temporal de una restauración usa las credenciales administrativas locales únicamente en la herramienta de mantenimiento. Para un servidor externo, esta herramienta admite `PG_ADMIN_URL` definido para ese proceso y `PG_BIN` con sus utilidades. La API normal usa únicamente la cuenta de servicio.

Las copias deben corresponder al esquema actual. No reemplaces una PostgreSQL con operaciones nuevas por la SQLite anterior: esa SQLite representa el momento previo a la migración. Para una transferencia inversa de información posterior se requiere otra copia verificada.

## Verificación reproducible sin tocar la base activa

```powershell
backend\.venv\Scripts\python.exe backend\check_postgres.py
backend\.venv\Scripts\python.exe backend\check_postgres.py --browser
npm run lint
npm run build
```

`check_postgres.py` crea bases desechables, comprueba una migración de ensayo y ejecuta pruebas funcionales, de respaldo/restauración y de concurrencia. Las bases de prueba se eliminan al terminar. La prueba de navegador también usa otra base temporal y un perfil independiente de Chrome.

Resultado: **25 pruebas aprobadas sobre PostgreSQL**, más una prueba de restauración específica de SQLite omitida en esa ejecución y comprobada en la suite SQLite. Se verificaron ocho reservas paralelas, competencia por el mismo rollo, operador y montacargas, versiones concurrentes, cambios de ubicación y permisos administrativos. El recorrido de Chrome pasó conectado a PostgreSQL.

## Instalación reproducible en otra copia local

```powershell
cd backend
.\setup-postgres.ps1
# Detener el backend SQLite antes de activar:
.\.venv\Scripts\python.exe migrate_postgres.py --activate
.\run.ps1
```

El instalador local utiliza los [binarios EDB enlazados por PostgreSQL](https://www.postgresql.org/download/windows/) y comprueba el SHA-256 publicado para `postgresql-17.11-5-windows-x64-binaries.zip`: `80379b2c04d51c30225532e0ae04509899141e9957ed096fe749d7fd9df8f82f`. Se extraen servidor, bibliotecas y utilidades; no se necesita pgAdmin. [Referencia del distribuidor para el archivo y su huella](https://github.com/EnterpriseDB/edb-installers/issues/731).

Si el puerto 5432 ya está ocupado al inicializar un clúster nuevo, se utiliza 55432. No se modifica una instalación PostgreSQL preexistente ni se reutilizan contraseñas por defecto.
