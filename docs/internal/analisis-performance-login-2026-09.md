# Análisis de performance — login y carga de pantallas (2026-09-03)

> **Clasificación:** análisis de código + mediciones locales. No incluye mediciones de
> producción: el acceso a `icore-srv` desde la sesión fue bloqueado por el clasificador
> de permisos. Los tiempos de esta nota son de la máquina de desarrollo y sirven para
> ordenar causas, no para describir producción. Antecedentes: `auditoria-performance-2026-07.md`
> y `relevamiento-performance-2026-08.md`.

**Síntoma reportado:** algunas pantallas tardan más de lo común; el login es el caso más notorio.

## 1. Qué recorre el usuario al ingresar

1. `POST /` → `UsuariosLoginView.form_valid`: `authenticate` (hash de contraseña), señal
   `user_logged_in` (`update_last_login` + `registrar_login` en Redis), `Profile`
   `get_or_create` + `select_for_update` + `save` en transacción, `set_expiry`.
2. `302 → /inicio/` (`LOGIN_REDIRECT_URL = core:inicio`): cadena completa de middlewares
   (sesión en Redis, usuario, grupos, `Profile`) + vista con contadores cacheados.
   Medido en agosto: 19 consultas, ~45 ms en `localhost`.
3. El navegador baja los estáticos de `includes/base.html`: **21 hojas de estilo y 17 scripts**
   más fuentes e imágenes.

## 2. Hallazgos, ordenados por impacto en el síntoma

### H-1 · El hash de la contraseña cuesta ~1 s de CPU por login — severidad ALTA (hecho medido)

`PASSWORD_HASHERS` no está definido: rige el default de Django, PBKDF2-SHA256. Producción corre
**Django 5.2.17** (`requirements.txt`), cuyo default es **1.000.000 de iteraciones**; el venv
local (4.2) usa 600.000, por eso localmente se percibe menos.

Medición en la máquina de desarrollo (`check_password`, mediana de 5 corridas):

| Hasher | Mediana |
|---|---:|
| PBKDF2 600k iteraciones (Django 4.2, venv local) | 332 ms |
| **PBKDF2 1.000k iteraciones (Django 5.2, producción)** | **952 ms** |
| Argon2id (parámetros por defecto de Django) | 89 ms |

En la VM de `icore-srv` (4 vCPU con flags x86-64-v2 enmascarados, ver memoria del deploy) el
costo es igual o mayor. Ese segundo se paga **con el GIL tomado**, así que mientras alguien se
loguea el proceso rinde menos para todos los demás (ver H-2). Un login fallido con usuario
inactivo lo paga dos veces (`_credenciales_de_usuario_inactivo`); el fallido común, una.

**Recomendación:** agregar `argon2-cffi` y definir
`PASSWORD_HASHERS = [Argon2PasswordHasher, PBKDF2PasswordHasher, ...]`. Django verifica los
hashes PBKDF2 existentes con el segundo hasher y **re-hashea solo al siguiente login exitoso**,
sin migración ni reseteo de claves. Ganancia esperada: ~10× en el POST de login.

### H-2 · Todo el HTTP corre en un solo proceso Python — severidad ALTA (hecho verificado en código)

`docker-compose.prod.yml` levanta `web` con `daphne` (un proceso) y `websocket` con otro Daphne.
Django bajo ASGI abre un `ThreadSensitiveContext` por request (`django/core/handlers/asgi.py`),
así que hay un hilo por request en vuelo, pero **el GIL serializa el código Python** de todos
ellos: el render de plantillas, los middlewares y el hash de H-1 comparten **un núcleo** de los
cuatro del servidor. El relevamiento de agosto lo mostró sin nombrarlo: con 8 clientes la
mediana de `/inicio/` pasó de 45,6 a 163,9 ms (×3,6) sin errores ni contención de base.

Esto explica el síntoma "a veces tarda más de lo común": la latencia de una pantalla depende de
qué estén haciendo los otros usuarios en ese momento (un login, un export, una consulta a RENAPER).

**Recomendación:** servir HTTP con **gunicorn (WSGI), varios workers**, y dejar Daphne solo en
`websocket` (nginx ya enruta `/ws/` a ese servicio). `gunicorn==23.0.0` ya está en
`requirements.txt` y `config/wsgi.py` existe. Ejemplo para `web`:

```
command: gunicorn config.wsgi:application --bind 0.0.0.0:8001 --workers 3 --threads 2 --timeout 60
```

Hay que subir `mem_limit` de `web` (hoy 350m, con 150m de swap permitido): cada worker ronda
150–200 MB. El servidor tiene 7,8 GiB y mysql/redis/websocket suman 2,2 GiB de límites, así que
~900m para `web` entra sin problema. En Kubernetes (despliegue de ECOM) el equivalente es el
mismo comando o más réplicas del pod. El bootstrap (migraciones, estáticos, seeds) sigue en el
entrypoint: solo cambia el `exec` final.

### H-3 · Los seis middlewares propios no son async-capable — severidad MEDIA (hecho verificado)

`ApiCorsMiddleware`, `PortalCiudadanoMiddleware`, `BackofficeSingleSessionMiddleware`,
`CambioContrasenaObligatorioMiddleware`, `SecurityHeadersMiddleware` y `RequestLoggingMiddleware`
no declaran `async_capable`, y están intercalados con los de Django (que sí lo son). Bajo ASGI
eso produce **7 cambios de modo sync↔async por request**, cada uno un salto de hilo. No es la
causa principal, pero es costo puro. **Se resuelve solo al pasar el HTTP a WSGI (H-2)**; si se
mantiene Daphne, la alternativa es declararlos `sync_capable = True` / `async_capable = True`
con implementación dual.

### H-4 · nginx sirve `/static/` sin compresión ni HTTP/2 — severidad MEDIA (hecho verificado)

`nginx.conf` no tiene `gzip`, `gzip_static` ni `http2`. Cada pantalla del backoffice baja
~40 archivos por HTTP/1.1 (6 conexiones en paralelo → ~7 tandas de ida y vuelta) y sin comprimir:
`fontawesome/all.min.css` 102 KB, `tailwind.css` 55 KB, `chaco-tokens.css` 15 KB,
`fa-solid-900.woff2` 150 KB. WhiteNoise **ya deja los `.gz`/`.br` precomprimidos en
`staticfiles/`** por `CompressedManifestStaticFilesStorage`; nginx los ignora.

Con `Cache-Control: public, immutable` a 30 días el costo se paga en el **primer ingreso y
después de cada deploy** (cambian los hashes del manifest), que es exactamente cuando el usuario
"nota que el login tarda". Sobre VPN el efecto se multiplica por la latencia.

**Recomendación (solo configuración, reinicio de nginx):**

```
listen 443 ssl;
http2 on;
location /static/ {
    alias /staticfiles/;
    gzip_static on;          # usa los .gz que ya genera whitenoise
    expires 30d;
    add_header Cache-Control "public, immutable";
}
gzip on; gzip_types text/css application/javascript application/json image/svg+xml;
```

### H-5 · Demasiados archivos en `includes/base.html` — severidad MEDIA (hecho verificado)

21 `<link rel="stylesheet">` y 17 `<script>` por página. Con HTTP/2 (H-4) el costo baja mucho,
pero sigue conviniendo concatenar las hojas `nodo-*.css`, `main/custom/override/responsive/mobile-*`
en una sola dentro del build de Tailwind (`npm run build:tailwind`), que ya es el paso de build
del CSS. Esfuerzo mediano; coordinar con el sistema de diseño (`design_audit.py`).

### H-6 · Llamadas a servicios externos dentro del request — severidad MEDIA (hecho verificado)

| Pantalla / flujo | Servicio | Timeouts (conexión + lectura) |
|---|---|---|
| Alta de ciudadano por DNI (`legajos/views/ciudadanos.py`) | RENAPER | 10 s + 20 s |
| Admisiones de Dispositivos (`programas/views/admisiones.py`) | RENAPER | 10 s + 20 s |
| «Revalidar RENAPER» en revisión (`programas/views/revision.py`) | Personas | 10 s + 20 s |
| Chat público y API móvil (`conversaciones/views/public.py`, `programas/api/views.py`) | RENAPER | 10 s + 20 s |
| Alta de programa SIIS (`programas/forms.py`, catálogo) | SIIS | 10 s + 30 s, **cacheado** |

Con un solo proceso (H-2), cada una retiene un hilo y, si el servicio externo está lento o caído,
los timeouts de 20–30 s se acumulan. No es la causa del login lento, pero sí de "algunas
pantallas" lentas de forma intermitente. **Recomendación:** timeouts de lectura de 5–8 s y un
corte breve tras fallas consecutivas (el alias `performance` ya implementa ese patrón), además de
H-2.

### H-7 · Límite de memoria de `web` — severidad A VERIFICAR (hipótesis)

`mem_limit: 350m` + `memswap_limit: 500m`: si el proceso supera 350 MB empieza a paginar y las
latencias se vuelven erráticas. Verificar en el servidor con `docker stats --no-stream` y
`docker inspect chaco-web-1` (reinicios por OOM). Si se aplica H-2 el límite debe subir de todos
modos.

### H-8 · Logging por request — severidad BAJA (hecho verificado)

`RequestLoggingMiddleware` emite un INFO por request al `root`, que tiene **6 handlers** (consola
+ 5 archivos con filtros). Costo chico por request pero sincrónico. Además `DailyFileHandler`
fija la carpeta de fecha **al arrancar** el proceso (no rota por día) y el contenedor no tiene
`logging.options.max-size`, así que `docker logs` crece sin límite. Ajuste operativo, no de latencia.

### H-9 · Polling del navbar sin caché — severidad BAJA (hecho verificado)

`alertas_conversaciones_fallback.js` pide `alertas/count/` cada 10 s por pestaña cuando el WS no
conecta (rol Conversaciones), y `conversaciones_tiempo_real_global.js` cada 5 s.
`get_alertas_conversaciones_count` hace un `COUNT` sin caché por pedido. Cachear 15–30 s por
usuario, como ya hace `get_conversaciones_pendientes_count`.

### H-10 · Tres consultas para fijar la sesión única — severidad BAJA (hecho verificado)

`form_valid` hace `get_or_create` + `select_for_update().get` + `save` dentro de una
transacción. Un `Profile.objects.filter(user=...).update(backoffice_session_key=...)` (el
`UPDATE` ya bloquea la fila) con `get_or_create` solo si no afectó filas baja a 1–2 consultas.
Marginal frente a H-1.

## 3. Lo que ya está bien (no tocar)

- Sesiones y caché en Redis en producción; contadores del inicio cacheados; badge del sidebar
  cacheado 30 s por usuario; `CONN_MAX_AGE=60` con health checks.
- Consultas por ruta dentro de los presupuestos de `scripts/perf_budgets.json`; sin N+1
  dependiente del volumen (relevamiento de agosto, §10).
- Plantillas con loader cacheado (`DEBUG=False`), estáticos con hash y `immutable` a 30 días.
- La página de login en sí es liviana (0 consultas en el GET, ~250 KB de estáticos propios).

## 4. Orden sugerido y evidencia a tomar antes

1. **Medir en el servidor** (5 minutos, sin cambios): `RequestLoggingMiddleware` ya escribe como
   WARNING toda request de más de 3 s (`SLOW_REQUEST_MS`). En `icore-srv`:
   `docker exec chaco-web-1 sh -c 'grep -h duration= /app/logs/*/warning.log | tail -50'` y
   `docker stats --no-stream`. Confirma H-1/H-2 y descarta o confirma H-7.
2. **H-1 Argon2** — 1 dependencia + 1 setting, sin migración. Riesgo bajo.
3. **H-4 nginx** — solo configuración, reinicio de nginx. Riesgo bajo.
4. **H-2 gunicorn en `web` + `mem_limit`** — probar primero en el compose de aceptación; actualizar
   `docker/k8s/README.md` para ECOM. Riesgo medio (cambia el runtime HTTP). Cubre H-3.
5. H-6, H-9, H-5, H-8, H-10 a medida que se toque cada módulo.

Cada punto que se implemente lleva su entrada en `docs/internal/requerimientos.md`.
