# Performance en CI efímera

Cada pull request ejecuta dos guardas sin depender de entornos externos ni credenciales:

1. **Presupuestos deterministas SQLite:** cada ruta sintética tiene máximos versionados de queries y queries duplicadas. Excederlos bloquea el PR.
2. **Contrato MySQL+Redis:** GitHub Actions crea MySQL y Redis descartables, siembra datos `PERF`, ejecuta las rutas desde dos procesos Python y exige que Redis agregue ambas mediciones bajo un namespace único de la corrida. Reaplica los mismos presupuestos por ruta sobre el máximo de queries de cada request real capturada con `execute_wrapper`, además de bloquear N+1. Cada proceso usa identidades `PERF` propias para respetar la política de sesión única de Backoffice. Las dependencias externas se reemplazan por una sonda local `ci_stub`.

Los artefactos `performance-sqlite-report` y `performance-ephemeral-stack-report` contienen rutas normalizadas, conteos, histograma de latencia y dependencias agregadas. No incluyen SQL, parámetros, payloads, credenciales ni usuarios.

`scripts/perf_audit.py` es una herramienta diagnóstica local; su salida JSON no se versiona porque las mediciones dependen de la máquina. La única fuente de verdad para los umbrales es `scripts/perf_budgets.json`.

La latencia del runner compartido se publica como advertencia gruesa. El gate bloqueante es intencionalmente determinista: status, presupuesto de queries, queries duplicadas/N+1, privacidad y agregación Redis entre procesos.

Fuera de CI, la instrumentación está activada por defecto y puede apagarse por entorno con `PERFORMANCE_QUERY_MONITORING_ENABLED=False`. Usa un alias Redis dedicado, agrega en ventanas fijas con expiración y degrada a “no disponible” si Redis falla, sin interrumpir la request de negocio.

Dentro de CI, el job de presupuestos deterministas fija `PERFORMANCE_QUERY_MONITORING_ENABLED=False`: mide el costo del código de negocio, y su `reference_total_ms` se estableció sin instrumentación. El contrato efímero MySQL+Redis la habilita explícitamente porque su objeto de prueba es justamente la agregación entre procesos.

El muestreo se decide antes de instalar el collector de queries: `PERFORMANCE_QUERY_SAMPLE_RATE` vale `1.0` por defecto en desarrollo y QA, y `0.2` en producción. Una request no muestreada no fingerprinta queries ni escribe métricas. El reporte expone la tasa efectiva junto al origen, alcance y ventana para que los agregados no se interpreten como tráfico total.

El alias Redis `performance` usa `PERFORMANCE_REDIS_TIMEOUT_SECONDS=0.25` tanto para conexión como para operaciones, sin cambiar los timeouts de `default` ni `sessions`. Tras una falla de escritura, el circuito omite nuevos intentos durante `PERFORMANCE_REDIS_RECOVERY_SECONDS=60`; al vencer permite una sola sonda concurrente y vuelve a cerrar el circuito únicamente después de una escritura exitosa. `PERFORMANCE_N1_WARNING_INTERVAL_SECONDS=60` limita el warning a uno por ruta e intervalo, pero cada request muestreada afectada sigue incrementando el contador agregado de N+1.

Para aumentar un presupuesto se modifica `scripts/perf_budgets.json` en el mismo PR, con justificación revisable. No se deben introducir optimizaciones funcionales sin que una guarda haya señalado la regresión.
