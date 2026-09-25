# Banco de performance contra MySQL 8

Los tests y SQLite no reproducen los 500 por `read_timeout` de producción: solo un MySQL
con volumen real y las `OPTIONS` de producción (`read_timeout` 10 s, `STRICT_TRANS_TABLES`,
read committed) los muestra antes de que pasen. Esta carpeta arma ese banco en minutos y
lo mide con las mismas rutas que `scripts/perf_audit.py` más las pesadas del dashboard, los
reportes y la revisión. Se excluye del release (`export-ignore`).

## Receta (PowerShell, raíz del repo)

```powershell
# 1. MySQL 8 en docker (sirve el contenedor `chaco-mysql-dash`, puerto 3308) y un Redis descartable.
docker start chaco-mysql-dash
docker run -d --name chaco-redis-bench -p 6380:6379 redis:7-alpine
$ROOT = (docker inspect chaco-mysql-dash --format '{{range .Config.Env}}{{println .}}{{end}}' | Select-String '^MYSQL_ROOT_PASSWORD=').ToString().Split('=',2)[1]
docker exec chaco-mysql-dash mysql -uroot -p"$ROOT" -e "CREATE DATABASE IF NOT EXISTS chaco_perf_ci CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;"

# 2. Variables: seed_perf SOLO acepta la base `chaco_perf_ci` con el perfil de CI de performance.
$env:DJANGO_SECRET_KEY = "test-key"; $env:DATABASE_NAME = "chaco_perf_ci"; $env:DATABASE_USER = "root"
$env:DATABASE_PASSWORD = $ROOT; $env:DATABASE_HOST = "127.0.0.1"; $env:DATABASE_PORT = "3308"
$env:DJANGO_DEBUG = "False"; $env:DJANGO_ALLOWED_HOSTS = "testserver,localhost"
Remove-Item Env:PYTEST_RUNNING, Env:DJANGO_SYNCDB_PROJECT_APPS -ErrorAction SilentlyContinue

# 3. Esquema y datos base (≈ 2 + 4 min).
$env:ENVIRONMENT = "dev";  & $env:PY_VENV manage.py migrate --noinput
$env:ENVIRONMENT = "ci"; $env:PERFORMANCE_CI = "1"; $env:REDIS_URL = "redis://127.0.0.1:6380/1"
& $env:PY_VENV manage.py seed_perf --scale 2000
Remove-Item Env:PERFORMANCE_CI; $env:ENVIRONMENT = "dev"

# 4. La forma de producción: UN relevamiento público con 20.000 casos completos (≈ 40 s).
& $env:PY_VENV scripts\perf_mysql\escalar_bench.py --casos 20000
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
- Después de medir: `docker stop chaco-mysql-dash chaco-redis-bench`.
