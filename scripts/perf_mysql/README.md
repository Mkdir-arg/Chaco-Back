# Banco de performance contra MySQL 8 / MariaDB 10.11

Los tests y SQLite no reproducen los 500 por `read_timeout` de producción: solo un motor
real con volumen real y las `OPTIONS` de producción (`read_timeout` 10 s,
`STRICT_TRANS_TABLES`, read committed) los muestra antes de que pasen. Esta carpeta arma
ese banco en minutos y lo mide con las mismas rutas que `scripts/perf_audit.py` más las
pesadas del dashboard, los reportes y la revisión. Se excluye del release
(`export-ignore`).

**ECOM corre MariaDB** (testing y PRD): los criterios de cierre de la auditoría de octubre
de 2026 piden medir ahí, no en MySQL 8. La receta de abajo vale para los dos motores; solo
cambia el contenedor del paso 1.

## Receta (PowerShell, raíz del repo)

```powershell
# 1a. MariaDB 10.11 (lo que corre ECOM), sin tablas de zona horaria como allá. Descartable.
docker run -d --name chaco-mariadb-bench -e MARIADB_ROOT_PASSWORD=root `
  -e MARIADB_DATABASE=chaco_perf_ci -e MARIADB_INITDB_SKIP_TZINFO=1 -p 3310:3306 mariadb:10.11
docker run -d --name chaco-redis-bench -p 6380:6379 redis:7-alpine
$ROOT = "root"   # y DATABASE_PORT = 3310 en el paso 2

# 1b. O MySQL 8 (icore), en el contenedor `chaco-mysql-dash` del puerto 3308.
docker start chaco-mysql-dash
$ROOT = (docker inspect chaco-mysql-dash --format '{{range .Config.Env}}{{println .}}{{end}}' | Select-String '^MYSQL_ROOT_PASSWORD=').ToString().Split('=',2)[1]
docker exec chaco-mysql-dash mysql -uroot -p"$ROOT" -e "CREATE DATABASE IF NOT EXISTS chaco_perf_ci CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;"

# 2. Variables: seed_perf SOLO acepta la base `chaco_perf_ci` con el perfil de CI de performance.
$env:DJANGO_SECRET_KEY = "test-key"; $env:DATABASE_NAME = "chaco_perf_ci"; $env:DATABASE_USER = "root"
$env:DATABASE_PASSWORD = $ROOT; $env:DATABASE_HOST = "127.0.0.1"; $env:DATABASE_PORT = "3308"
$env:DJANGO_DEBUG = "False"; $env:DJANGO_ALLOWED_HOSTS = "testserver,localhost"
Remove-Item Env:PYTEST_RUNNING, Env:DJANGO_SYNCDB_PROJECT_APPS -ErrorAction SilentlyContinue

# 3. Esquema y datos base (≈ 2 + 4 min). DB_*_TIMEOUT sube el read/write_timeout de 10 s
#    SOLO para sembrar: los bulk del seed se pasan de largo y mueren con «2013 Lost
#    connection». Medir siempre sin estas dos variables, con los 10 s de producción.
$env:DB_READ_TIMEOUT = "600"; $env:DB_WRITE_TIMEOUT = "600"
$env:ENVIRONMENT = "dev";  & $env:PY_VENV manage.py migrate --noinput
$env:ENVIRONMENT = "ci"; $env:PERFORMANCE_CI = "1"; $env:REDIS_URL = "redis://127.0.0.1:6380/1"
& $env:PY_VENV manage.py seed_perf --scale 2000
Remove-Item Env:PERFORMANCE_CI; $env:ENVIRONMENT = "dev"

# 4. La forma de producción: UN relevamiento público con 20.000 casos completos (≈ 6 min).
#    `--preguntas` asegura N preguntas generales de opciones cerradas antes de armar los
#    casos: el catálogo de `seed_datos_base` no tiene ninguna (sus cinco generales son
#    ARCHIVO), así que sin esto `preguntas_graficables` devuelve 0 y las rutas del
#    dashboard se miden sobre un catálogo vacío.
& $env:PY_VENV scripts\perf_mysql\escalar_bench.py --casos 20000 --preguntas 12
Remove-Item Env:DB_READ_TIMEOUT, Env:DB_WRITE_TIMEOUT
& $env:PY_VENV manage.py shell -c "from programas.models import *; rel=Relevamiento.objects.filter(tipo='PUBLICO').order_by('-pk').first(); p,_=ProgramaSiis.objects.get_or_create(siis_programa_id=90, defaults={'nombre':'BENCH Programa SIIS'}); Segmento.objects.filter(pk=rel.convocatoria.segmento_id).update(programa=p)"

# 5. Medir (≈ 1 min) y perfilar una ruta.
& $env:PY_VENV scripts\perf_mysql\bench_mysql.py --salida scripts\perf_mysql\resultado.json
& $env:PY_VENV scripts\perf_mysql\perfil_ruta.py /becas/reportes/beneficiarios/export/xlsx/ 1
```

`bench_mysql.py` imprime por ruta: status, ms en frío, ms en caliente (mediana de 3),
consultas, duplicadas y ms de SQL; el JSON guarda además las tres consultas más lentas.
`perfil_ruta.py` corre `cProfile` sobre la ruta y separa SQL de plantillas/Python.

## Gotchas

- `settings_bench.py` saca `BackofficeSingleSessionMiddleware` (el segundo request del
  mismo usuario daba 302) y fuerza caché en memoria: lo que se mide es la consulta.
- En Git Bash exportar `MSYS_NO_PATHCONV=1` antes de pasar una URL como argumento, o
  `/becas/...` se convierte en `C:/Program Files/Git/becas/...`.
- El laptop tiene ruido de ±2x entre corridas: comparar siempre antes/después en la misma
  sesión, y mirar primero los ms de SQL y `EXPLAIN ANALYZE` (`docker exec ... mysql -e`).
  Para lo que es CPU y no SQL (armar un xlsx), medir `time.process_time()` y quedarse con
  el mejor de 3: el reloj de pared de este equipo no distingue un 10 %.
- Las rutas del dashboard reciben el pk de `ProgramaSiis`, no el del `Programa` del RBAC;
  el paso 4 ata el segmento del relevamiento del banco a un `ProgramaSiis` sintético para
  que `bench_mysql.py` las encuentre (antes devolvían 404 y se medían vacías).
- `OPENPYXL_LXML=False` desactiva lxml sin desinstalarlo: sirve para comparar el costo de
  armar un xlsx con y sin él (PERF-03).
- Después de medir: `docker stop chaco-mysql-dash chaco-redis-bench` (o
  `docker rm -f chaco-mariadb-bench chaco-redis-bench` si el banco era descartable).
