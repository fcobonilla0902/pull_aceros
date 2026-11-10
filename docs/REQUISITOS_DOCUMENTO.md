# Propuesta de Sistema Digital de Surtimiento Interno (Meta-Ride)

Fuente principal: texto del documento proporcionado por el usuario en la conversación, después de la primera implementación. No se recibió un archivo PDF. Este archivo registra sus requisitos y su correspondencia con el código; no sustituye el documento original.

## Problemática y propósito

Producción necesita rollos con la especificación correcta para estampadoras de blancos y formados. Las solicitudes dispersas entre WhatsApp, radio, notas y comunicación verbal provocan pérdida de pendientes, duplicados, desconocimiento del avance, falta de comunicación entre turnos y riesgo de paro. El crecimiento de clientes, prensas y movimientos requiere centralizar la comunicación entre Producción, Logística, almacenes y manejo de materiales.

Meta-Ride debe conservar folio, responsables, etapas y marcas de tiempo desde la necesidad hasta la recepción del rollo en la estampadora. Debe permitir detectar retrasos, priorizar según impacto en Producción y generar históricos útiles para analizar capacidad.

## Correspondencia funcional

| Sección del documento | Requisito | Implementación y comprobación |
|---|---|---|
| 2–3 | Solicitud con estampadora, proceso, parte, rollo, prioridad y hora requerida | `Operations.jsx`: formulario; `RequestInput`; `requests`, `request_items`, `rolls`. Rollo específico opcional o reserva por parte. Folio único e idempotencia. |
| 2 | Verificar existencia, especificación y disponibilidad | Acción `validate`: reserva atómica, parte correspondiente, rollo DISP y peso elegible. La especificación es la del catálogo de parte; no existe matriz industrial de compatibilidad. |
| 2 | Asignación de operador/equipo y hora | Acción `assign`, control de ocupación, bitácora con usuario y hora. Montacargas opcional. |
| 2 | Preparación, identificación, localización y acondicionamiento | Etapas de preparación y material listo, observaciones y ubicación consultable en el detalle. La inspección física corresponde al operador. |
| 2 | Traslado al punto de entrega | Campo `destination`, etapa En traslado e historial. |
| 2 | Recepción o incidencia | Entrega completa/parcial con responsable, rollos entregados y marcas de tiempo; incidencia tipificada y resolución. |
| 3–4 | Pendientes, en proceso, completadas, urgencias y retrasos | Kanban con estados, filtros por estampadora y búsqueda; folio, partes, prioridad, responsable, hora requerida, tiempo abierto y tiempo restante/retraso. Alerta próxima a vencer: 30 minutos. |
| 4 | Tablero en tiempo real | Actualización por consulta cada 30 segundos. No utiliza conexión de streaming; la cifra puede demorar hasta ese intervalo. |
| 5 | Pendientes visibles entre turnos | `ShiftPage.jsx`: solicitudes activas con avance, notas, ubicación, incidentes y última actualización. |
| 5 | Aceptación digital de pendientes por personal entrante | Destinatario explícito, recepción autenticada, fecha/hora y comentario; impide autoaceptación, aceptación ajena y doble aceptación. Copia inmutable en `handover_items`. |
| 6 | Tiempo medio y porcentaje a tiempo | Indicadores de solicitudes completamente entregadas: creación a entrega y comparación con hora requerida. |
| 6 | Pendientes, vencidas, urgentes | Contadores de solicitudes activas, urgentes, próximas y vencidas. |
| 6 | Movimientos por turno | Cada confirmación de entrega completa/parcial cuenta como movimiento; desglose por fecha operativa y turno. T1 06:00, T2 14:00, T3 21:30, zona America/Monterrey configurable. |
| 6 | Causas de retraso y afectaciones/paros | Catálogo de causas de incidencia y marca explícita de paro. Tiempo de incidencias desde apertura hasta resolución; no se infiere un paro por simple vencimiento. |
| 6 | Reportes | Fechas de consulta y CSV de indicadores, movimientos por turno y causas; exportación de bitácora completa. |
| 7 | Entidades, estaciones y recursos limitados | `simulation.py`: solicitudes, localización/preparación, traslado; operadores y montacargas con capacidad limitada. |
| 7 | Variabilidad pseudoaleatoria | Semilla reproducible, llegadas uniformes; duraciones uniformes o triangulares; incidentes Bernoulli y tiempos de atención configurables. La ocupación de equipo surge de las colas. |
| 8 | Equipos, carga de turno, demanda y prioridades | Recursos, volumen, duración de turno y urgencias configurables. Comparación 1–4 montacargas y FIFO/urgentes con las mismas entradas pseudoaleatorias. |
| 8 | Surtimiento, cuellos de botella y retraso/paro | Tiempo medio, espera, ocupación de operadores/equipo, porcentaje de retraso contra plazo y riesgo simulado de paro por tolerancia configurable. |
| 7–9 | Histórico para simulación y decisiones | Ejecuciones guardadas y rangos observados de preparación/traslado desde cinco muestras válidas. No se declara ajuste estadístico ni validación industrial. |

## Definiciones de medición

- Las solicitudes del reporte se agrupan por fecha de **creación**; movimientos e incidencias por fecha de su **evento**. Los límites de fechas son días locales de planta, inclusivos, convertidos a UTC. La pantalla informa esta definición.
- Una solicitud parcialmente entregada continúa pendiente y su cantidad pendiente descuenta los rollos ya entregados. No entra al promedio de solicitudes completadas hasta la entrega final.
- Un movimiento es una confirmación de entrega, incluso si incluye varios rollos. El reporte presenta también solicitudes distintas por turno, para evitar confundir ambas cantidades.
- La aceptación de turno transfiere la responsabilidad de coordinación de la lista de pendientes. No cambia automáticamente al operador de una maniobra en curso ni libera material reservado.
- La copia al entregar muestra el estado histórico; se consulta también el estado actual para que un cambio posterior no quede oculto. Entregas antiguas sin copia detallada se identifican como tales.
- El tiempo de paro reportado suma intervalos de incidencias marcadas como paro. Si varias solicitudes afectan la misma estampadora simultáneamente puede haber solapamiento; no equivale a tiempo único de inactividad de la máquina.
- En SimPy, el riesgo de paro es el porcentaje de entidades cuyo retraso excede la tolerancia configurada. Es un indicador del escenario hipotético, no la probabilidad industrial real de paro.

## Verificación y límites

Diecisiete pruebas de integración cubren flujo, autenticación/roles, atomicidad, entregas parciales, selección de rollo, recepción de turno, copia histórica, fechas/turnos, indicadores y simulación reproducible con incidencias. ESLint y compilación Vite completan la revisión estática.

La prueba con Chrome headless completó login, creación, reserva, asignación, preparación, traslado, entrega, entrega de turno, SimPy y recepción con otra cuenta, sin excepciones JavaScript. Comprobó además que la pantalla de recepción no excede el ancho de un dispositivo de 390 px. La base, cuentas y perfil del navegador de esta prueba fueron temporales. La captura de resumen usa datos de prueba, en `artifacts/resumen-browser.png`.

El recorrido de navegador detectó una carrera entre respuesta y confirmación de sesión. Las dependencias SQLAlchemy usan ahora alcance de función (`scope='function'`, FastAPI ≥0.121), de modo que commit/rollback termina antes de enviar la respuesta; esto evita que la siguiente consulta lea una sesión o un avance todavía no confirmado. La prueba de cambio de usuario verificó la corrección.

Faltan datos reales para validar duraciones, distribuciones, compatibilidades, rutas, probabilidades de incidentes y umbrales de afectación de cada estampadora. La regla DISP y >500 kg y los horarios de turnos se heredaron del prototipo; el documento no los fija y deben contrastarse con la planta. La importación XLSX/CSV de QAD con mapeo de columnas y los cambios de cantidades con ajuste de reservas están implementados y documentados en MANTENIMIENTO_LOCAL.md. PostgreSQL es ahora el motor activo: la copia verificó todas las tablas y se probaron flujo, restauración, navegador y operaciones simultáneas. Ver POSTGRESQL.md.
