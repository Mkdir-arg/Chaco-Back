# Pruebas de reproducción (PoC) de la auditoría

Todo lo de esta carpeta se escribió contra `origin/development @ 917e583` y se corrió con `.venv312`
(Python 3.12 + Django 5.2.17, el mismo stack del CI), SQLite en memoria (`PYTEST_RUNNING=1`) y
`DJANGO_SYNCDB_PROJECT_APPS=True`.

**Regla de lectura:** cada test de reproducción **afirma el defecto actual**. Hoy pasa (verde = el bug
existe). Después del arreglo tiene que fallar. Para el TDD de cada ítem: copiar el test, invertir la
aserción (o escribir el de «Tests a agregar» de la ficha), comprobar que el invertido **falla antes** del
fix y **pasa después**, y commitear solo el invertido con el nombre que pide la ficha. Estos archivos no
se commitean tal cual.

**Excepción — tests de control que NO se invierten:** algunos tests no demuestran el bug sino que fijan
un comportamiento correcto que el arreglo tiene que conservar. En `test_repro_dispositivos_legajos.py`
(DIS-01 y DIS-02) son `test_fix_por_rango_*`, `test_variante_truncmonth_*`, `test_parte_diario_en_sqlite_*`
y `test_admitir_usa_full_clean_*`: tienen que seguir en verde antes y después del fix.

Verificación independiente (R2, 01-oct-2026): 85 tests, 84 pasan y 1 skip intencional (SEC-09 sin
`SERVE_MEDIA`; con `SERVE_MEDIA=True` pasa). Sin falsos positivos.

Prólogo común (PowerShell, raíz del worktree):

```powershell
$env:PY = "C:\Users\mkdir\Proyectos\Chaco\.venv312\Scripts\python.exe"   # el venv vive en el checkout principal
$env:DJANGO_SECRET_KEY = "test-key"; $env:PYTEST_RUNNING = "1"; $env:DJANGO_SYNCDB_PROJECT_APPS = "True"
```
En la tabla, «`manage.py test …`» se corre como `& $env:PY manage.py test …`.

| Archivo | Copiar a | Correr | IDs que reproduce |
|---|---|---|---|
| `test_repro_seguridad.py` | `core/tests/` | `manage.py test core.tests.test_repro_seguridad` (SEC-09 además con `$env:SERVE_MEDIA="True"`) | SEC-01 a SEC-17, SEC-19 (clase `SEC18DebugXssTests`), SEC-18 (dentro de `SEC11LegajosJsonTests`) y SEC-29 (dentro de `SEC01BasicAuthTests`) |
| `patch_settings_sec01.py` | — (se ejecuta) | `& $env:PY <ruta>\patch_settings_sec01.py` desde la raíz de un worktree descartable | Aplica la propuesta de SEC-01 para comprobar 0 regresiones |
| `test_repro_siis_becas.py` | `programas/tests/` | `manage.py test programas.tests.test_repro_siis_becas` | SIIS-01..06, SIIS-10..12, BEC-01, BEC-02 |
| `test_repro_dispositivos_legajos.py` | `programas/tests/` | `manage.py test programas.tests.test_repro_dispositivos_legajos` | DIS-01..09, MER-01, LEG-01..05, SEC-18, SEC-19 |
| `test_repro_datos_operacion.py` | `programas/tests/` | `manage.py test programas.tests.test_repro_datos_operacion` | DAT-01, OPS-03, OPS-04 |
| `test_repro_usuarios.py` | `users/tests/` | `manage.py test users.tests.test_repro_usuarios` | SEC-03 (ampliación), SEC-26, G1b-02, G1b-05, G1b-06, G1b-07, OPS-06 (origen G2-02), G2-03 |
| `test_repro_dashboard_campos_propios.py` | `programas/tests/` | `manage.py test programas.tests.test_repro_dashboard_campos_propios` | G2-01 |
| `test_repro_admin_cron_renaper.py` | `core/tests/` | `manage.py test core.tests.test_repro_admin_cron_renaper` | OPS-06 (seeds), G1c-04, G1c-08, G1c-09, G1c-15, SIIS-14 |
| `perf_harness/tests.py` | `v4perf/tests.py` (+ `v4perf/__init__.py`) | `manage.py test v4perf` con `$env:V4_CASOS` y `$env:V4_OUT` (ver cabecera) | Mediciones de PERF-01..04, 07, 12, 19, 20 |
| `perf_harness/v4_mediciones.json` | — | — | Resultados de referencia de la verificación V4 (ver `../anexo-mediciones-performance.md`) |
| `perf_harness/asgi_conn_probe.py` | — | `python asgi_conn_probe.py 60 200` y `python asgi_conn_probe.py 0 200` | PERF-08 |
| `herramientas/cssclasses.py` + `missing_classes.py` | — | `python missing_classes.py <raiz_repo>` | FE-06, FE-13 (base de la regla CLASSDEF) |
| `herramientas/design_baseline.py` | — | `python design_baseline.py` desde la raíz del repo | Línea base de las reglas P1 del agente de diseño (Ola 6) |
| `herramientas/bloques_sin_destino.py` | — | `python bloques_sin_destino.py` desde la raíz del repo | FE-05 (base del flag `--bloques` de `compile_templates.py`) |

Resultados de las corridas originales:
- Seguridad: 21 tests, OK (1 skip = SEC-09, que da OK aparte con `SERVE_MEDIA=True`).
- SIIS/Becas: 13 reproducciones, todas en verde.
- Dispositivos/Legajos: 24 tests, OK (MER-01 crea su propio merendero; hasta la verificación R2 se salteaba por falta de fixture).
- Usuarios y dashboard (pasada 3): 13 tests, todos en verde.
- Admin, ws/alertas, RENAPER del backoffice y bootstrap (pasada 3): 9 tests, OK.
- Datos y operación: `test_repro_datos_operacion.py` en verde (DAT-01, OPS-03, OPS-04).
- Con los defaults de SEC-01 aplicados: 114 tests de `test_becas_api`, `users.tests.test_api_rbac`,
  `legajos`, `dashboard` y el PoC, 0 regresiones (solo los dos PoC de SEC-01 pasan a 403).

Lo que **no** está acá: las capturas de Playwright de la verificación de front (V5a) y del agente de
diseño; se reemplazan por los criterios de verificación escritos en cada ficha FE y en el anexo del
agente de diseño (recetas de Playwright + SQLite descriptas en la memoria del proyecto).
