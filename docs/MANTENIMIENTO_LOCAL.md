# Administración y mantenimiento local

## Dashboard de Resumen

Resumen presenta indicadores de solicitudes activas, vencimientos, cumplimiento y tiempo de surtimiento; accesos al seguimiento y cambio de turno; distribución por etapas, movimientos por turno y causas de incidencia. Seleccionar una etapa muestra sus folios; seleccionar un folio abre su detalle.

Las fechas se aplican con **Consultar periodo**. La exportación CSV utiliza ese mismo periodo aplicado. **Ver todo** restablece la consulta acumulada, que se actualiza cada 30 segundos. Una consulta por periodo es una captura de indicadores: vuelve a consultar para actualizarla. Los movimientos pueden filtrarse por turno y tienen una tabla de detalle. Cuando no hay datos, se muestra el estado vacío, sin cifras de demostración.

Para completar las reglas físicas del rollo y la validación de simulación, utiliza [Plantilla_validacion_MetaRide.xlsx](Plantilla_validacion_MetaRide.xlsx). Contiene instrucciones, reglas por confirmar, tiempos de solicitudes e incidencias. No modifica la base ni sustituye los procedimientos de planta.

## Usuarios y contraseñas

En **Administración → Usuarios** se crean cuentas y se despliega cada usuario para editar su nombre, rol y estado activo. Los registros no se borran, para conservar la trazabilidad.

- Cambiar rol o desactivar revoca las sesiones del usuario.
- Siempre debe quedar al menos un administrador activo.
- Una cuenta con movimientos abiertos o entregas de turno pendientes no se desactiva hasta cerrar esos pendientes. Un cambio de rol compatible con su actividad sí es posible.
- **Restablecer contraseña** permite que un administrador asigne otra contraseña a una cuenta diferente; revoca todas las sesiones de esa cuenta.
- En **Mi cuenta** cada persona cambia su contraseña indicando la actual y confirmando la nueva. Se mantiene esa sesión y se cierran las de otros dispositivos.
- Las contraseñas requieren al menos 12 caracteres. Las contraseñas no se incluyen en el historial.

## Editar solicitudes y reservas

Logística o admin abre una tarjeta Kanban y despliega **Editar solicitud y cantidades**. Puede cambiar partidas, cantidades, prioridad, riesgo, estampadora, proceso, punto de entrega, hora requerida y comentarios. Debe indicar una justificación.

Si la solicitud ya estaba validada, el sistema libera/reasigna reservas en una sola transacción. Si no alcanza el inventario o un rollo cambió, no guarda ninguna parte del cambio. Cuando cambian partidas con operador asignado, el folio vuelve a **Tomado**, para repetir preparación y localización. Si existe una incidencia, conserva la incidencia y vuelve a esa etapa al resolverla.

Los rollos entregados se conservan. No se pueden quitar sus partes, reducir las cantidades por debajo de lo entregado ni cerrar una entrega parcial mediante edición. Durante el traslado no se permite cambiar material o destino: primero se confirma la entrega o se cancela el pendiente. Una solicitud cerrada no se edita. El historial registra datos anteriores, nuevos y justificación.

## Importar inventario Excel o CSV de QAD

En **Inventario → Importar inventario Excel / CSV**:

1. Descarga una plantilla Excel o CSV.
2. Registra previamente las partes y ubicaciones, con sus especificaciones.
3. Reemplaza los ejemplos de la plantilla por tus datos. No importes la fila de ejemplo sin reemplazarla.
4. Selecciona el archivo y pulsa **Revisar archivo sin guardar**.
5. Si los encabezados son diferentes, relaciona las columnas y vuelve a revisar.
6. Revisa las filas nuevas, actualizaciones, filas sin cambios y errores.
7. Pulsa **Confirmar importación**. Solo entonces cambia el inventario.

| Campo | Contenido |
|---|---|
| `codigo_rollo` | Código físico único del rollo |
| `numero_parte` | Código de parte existente y activa |
| `ubicacion` | Código de ubicación existente y activa |
| `kg` | Peso positivo, hasta 1,000,000; sin separadores de miles |
| `estado` | `DISP` o `BLOQUEADO`; si no hay columna se utiliza `DISP` |

Se admite `.xlsx` (primera hoja) o CSV en UTF-8/Windows-1252, con coma, punto y coma o tabulador. Para datos de QAD exporta a uno de estos formatos y asigna las columnas. No se conecta directamente al ERP.

Límites: 5 MB, 5,000 filas, 50 columnas; no se admiten fórmulas ni macros. Usa códigos como texto para conservar ceros iniciales. El peso puede tener punto o coma decimal, sin separador de miles. Un rollo de 500 kg o menos se registra pero no es elegible para surtimiento según la regla heredada.

La opción **Actualizar rollos existentes** solo modifica rollos libres con estado DISP/BLOQUEADO. Nunca sobrescribe rollos reservados o entregados. Los errores, duplicados, conflictos entre usuarios y cambios desde la vista previa rechazan el archivo completo. Una revisión vence en 30 minutos y solo puede confirmarse una vez por el usuario que la generó.

## Catálogos

En **Administración → Catálogos** se editan nombres/códigos y se activan o desactivan partes, ubicaciones, estampadoras, procesos y montacargas. No se borran registros con historial.

- Los inactivos dejan de ofrecerse para operaciones nuevas.
- La desactivación que afectaría movimientos abiertos se rechaza.
- En montacargas, **En servicio** controla mantenimiento/retiro. **Asignado** corresponde a una maniobra; no se libera un equipo ocupado activando una casilla.
- Una parte que ya identifica rollos físicos no cambia de especificación. Crea una nueva parte para otro material.
- La versión del registro evita sobrescribir cambios hechos por otra persona.

## Respaldar y recuperar

En **Administración → Respaldos**, pulsa **Crear respaldo ahora** y descarga el archivo. En PostgreSQL se usa pg_dump con formato personalizado .dump, consistente durante la operación. La compatibilidad SQLite utiliza su API de backup. Los archivos se guardan en `backend/backups/` y no se incluyen en Git.

`run.ps1` también crea un respaldo antes de iniciar cuando ya existen usuarios. No borra copias anteriores. `BACKUP_DIR` permite cambiar la carpeta.

Para recuperar:

1. Detén el backend con **Ctrl+C** en su terminal.
2. Desde `backend`, ejecuta el comando que muestra Administración para el respaldo elegido:

```powershell
.\.venv\Scripts\python.exe manage.py restore "metaride-FECHA-CODIGO.dump" --confirm RESTAURAR
```

3. Inicia otra vez con `.\run.ps1` e ingresa con las credenciales que existían en ese respaldo.

La restauración comprueba el respaldo en una base temporal, versión del esquema y existencia de un administrador activo antes de aplicar cambios. Rechaza el reemplazo con el backend abierto, archivos corruptos o nombres fuera de la carpeta de respaldos. Solo admite respaldos del esquema actual. Las copias de versiones anteriores se conservan para recuperación con migración asistida.

Antes de reemplazar crea automáticamente un archivo `antes-restauracion-...dump`, con el que puedes volver al estado anterior. Revoca las sesiones y las importaciones pendientes; queda una entrada en el historial. En PostgreSQL se verifica primero el archivo en una base temporal y la restauración se ejecuta en una transacción. En SQLite se utiliza su API de backup sin manipular WAL a mano. No se ejecutó restauración sobre tus datos durante el desarrollo: se comprobó sobre bases temporales.

También puedes crear una copia desde terminal, con el backend activo:

```powershell
.\.venv\Scripts\python.exe manage.py backup
```

Los respaldos contienen datos operativos y hashes de contraseñas; mantenlos privados. Descargarlos y guardarlos en otro disco protege frente a pérdida de esta carpeta.

## Verificación ejecutable

```powershell
npm run lint
npm run build
backend\.venv\Scripts\python.exe -m unittest discover -s backend -p test_integration.py
backend\.venv\Scripts\python.exe backend\check_browser.py
```

La suite comprueba flujo operativo, permisos, sesiones, último administrador, contraseñas, catálogos, reservas con rollback, entregas parciales, importación CSV/XLSX, duplicados, archivos inválidos, confirmación única, cambios posteriores a la revisión, respaldos y recuperación. Chrome utiliza usuarios, archivos, perfil y base temporales; no modifica la base de operación. Requiere Chrome y puertos 8107, 5179 y 9337 disponibles.

La calibración industrial sigue necesitando datos reales de tiempos y reglas de planta; no se sustituyeron por datos ficticios. Esto es validación operativa, no una función pendiente del código local.

## Motor de base de datos

PostgreSQL es la base activa. Los respaldos SQLite previos se conservan identificados como copias del motor anterior. Consulta [POSTGRESQL.md](POSTGRESQL.md) para arranque automático, ubicación, pruebas de concurrencia y recuperación.
