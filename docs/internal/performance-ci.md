# Performance en CI efímera

Cada pull request ejecuta dos guardas sin depender de entornos externos ni credenciales:

1. **Presupuestos deterministas SQLite:** cada ruta sintética tiene máximos versionados de queries y queries duplicadas. Excederlos bloquea el PR.
2. **Contrato MySQL+Redis:** GitHub Actions crea MySQL y Redis descartables, siembra datos `PERF`, ejecuta las rutas desde dos procesos Python y exige que Redis agregue ambas mediciones bajo un namespace único de la corrida. Reaplica los mismos presupuestos por ruta sobre el máximo de queries de cada request real capturada con `execute_wrapper`, además de bloquear N+1. Cada proceso usa identidades `PERF` propias para respetar la política de sesión única de Backoffice. Las dependencias externas se reemplazan por una sonda local `ci_stub`.

Los artefactos `performance-sqlite-report` y `performance-ephemeral-stack-report` contienen rutas normalizadas, conteos, histograma de latencia y dependencias agregadas. No incluyen SQL, parámetros, payloads, credenciales ni usuarios.

`scripts/perf_audit.py` es una herramienta diagnóstica local; su salida JSON no se versiona porque las mediciones dependen de la máquina. La única fuente de verdad para los umbrales es `scripts/perf_budgets.json`.

La latencia del runner compartido se publica como advertencia gruesa. El gate bloqueante es intencionalmente determinista: status, presupuesto de queries, queries duplicadas/N+1, privacidad y agregación Redis entre procesos.

Fuera de CI, la instrumentación permanece desactivada por defecto. Cuando se habilita en QA/HML usa un alias Redis dedicado, agrega en ventanas fijas con expiración y degrada a “no disponible” si Redis falla, sin interrumpir la request de negocio.

Para aumentar un presupuesto se modifica `scripts/perf_budgets.json` en el mismo PR, con justificación revisable. No se deben introducir optimizaciones funcionales sin que una guarda haya señalado la regresión.
