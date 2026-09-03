# :material-package-variant-closed: Versión 001

<div class="grid cards" markdown>

-   :material-check-circle:{ style="color: #10b981" } **Estado**

    Cerrada

-   :material-calendar-range: **Período**

    3 jun 2026 → 31 ago 2026

-   :material-counter: **Avance**

    100% del alcance comprometido

-   :material-clock-outline: **Horas del período**

    1.699 h 12 min

</div>

!!! abstract "Objetivo"
    Definir el funcionamiento de los programas **Becas** y **Dispositivos**, y desarrollar el **motor RBAC base** para dejar el sistema de permisos operativo.

!!! success "Versión cerrada el 02/09/2026"
    Los diez ítems del alcance comprometido quedaron **completados**, con el Programa Becas operativo en el entorno del organismo. La versión absorbió además alcance nuevo pedido durante su ejecución —entre otras cosas, la inscripción por link público— que se detalla en el [informe de cierre](#informe-de-cierre-de-la-version).

---

## :material-clipboard-list-outline: Alcance de la versión

| # | Funcionalidad | Prioridad | Estado final |
|:-:|---|:-:|:-:|
| 1 | [Programa Becas — análisis funcional y estimación](../funcionalidades/programa-becas.md) | Alta | :material-check-circle:{ style="color: #10b981" } Completado |
| 2 | Motor RBAC base | Alta | :material-check-circle:{ style="color: #10b981" } Completado |
| 3 | [Programa Dispositivos y Merenderos — análisis y estimación](../funcionalidades/programa-dispositivos.md) | Alta | :material-check-circle:{ style="color: #10b981" } Completado — definición aprobada |
| 4 | Programa Becas — backend del backoffice | Alta | :material-check-circle:{ style="color: #10b981" } Completado — en operación |
| 5 | Programa Becas — pruebas funcionales del backend | Alta | :material-check-circle:{ style="color: #10b981" } Completado |
| 6 | App de campo (React Native) | Alta | :material-check-circle:{ style="color: #10b981" } Completado — en uso en territorio |
| 7 | Mockups y diseño UX (Becas) | Alta | :material-check-circle:{ style="color: #10b981" } Completado |
| 8 | Análisis Legajo Ciudadano | Media | :material-check-circle:{ style="color: #10b981" } Completado |
| 9 | Design System del proyecto | Media | :material-check-circle:{ style="color: #10b981" } Completado |
| 10 | Reuniones y coordinación | — | :material-check-circle:{ style="color: #10b981" } Completado |

!!! note "Criterio de las horas"
    Las **1.699 h 12 min** son el consumo imputado de los tres meses que abarcó la versión: junio 499 h 12 min, julio 500 h y agosto 700 h. El desglose día por día y por entregable está en el [detalle de consumo](../financiero/detalle-tareas.md). El corte por funcionalidad que esta página mostraba durante la ejecución (556 h 20 min al 10/07/2026) se conserva en ese detalle, en las filas de junio y julio.

---

## :material-flag-checkered: Informe de cierre de la versión

### :material-check-decagram: Qué quedó operativo

El **Programa Becas** funciona de punta a punta en el entorno del organismo: configuración del programa (segmentos, subsegmentos, cupos, coordinadores, requisitos y cuestionario social), convocatorias y relevamientos, carga en territorio con la app de campo, **inscripción de la persona por link público**, revisión de casos con trazabilidad, asignación de cupo con lista de espera y resolución con aviso al ciudadano. Sobre esa misma base quedaron el **motor de roles y permisos** que gobierna qué ve y qué opera cada perfil, el **legajo ciudadano unificado** por documento y el **sistema de diseño** que le da al producto una interfaz consistente.

El **Programa Dispositivos y Merenderos** cerró su definición funcional aprobada por el Ministerio y, durante la misma versión, avanzó bastante más allá de lo comprometido: legajo institucional, admisiones, camas, registro diario y su módulo de reportes.

### :material-plus-box-multiple-outline: Alcance incorporado durante la versión

Estos frentes no estaban en el alcance original y se absorbieron a pedido del Ministerio o por necesidad de la puesta en operación:

| Frente incorporado | Resultado |
|---|---|
| Inscripción por link público | Épica completa: link por relevamiento, padrón de habilitados por Excel, identificación por documento, formulario dinámico, comprobante en pantalla y por correo, y aviso de resolución |
| Seguridad de la superficie pública | Auditoría específica del circuito sin login y su endurecimiento (verificación anti-bot, límites de intentos, mensaje único de rechazo, adjuntos protegidos, cabeceras y librerías propias) |
| Integraciones externas | SIIS (catálogo de programas y compatibilidad), Base de Personas y RENAPER configuradas y verificadas contra el entorno del organismo |
| Nivel «Programa» | Un nivel por encima de los segmentos, vinculado al catálogo de SIIS |
| Módulo de reportes de Becas | Avance de convocatorias, cupos por segmento, producción territorial, embudo de revisión y padrón de beneficiarios, con exportación y permisos propios |
| Credenciales y acceso | Envío de credenciales por correo, cambio de contraseña obligatorio en el primer acceso y recuperación autogestionada |
| Portal ciudadano DATAÑACH | Home y navegación del portal con contenido real y datos de contacto |
| Programa Dispositivos | Desarrollo del programa (frontend, reportes y pruebas), más allá del análisis comprometido |
| Cambios solicitados sobre Becas | Sesión, datos de usuario, período y cupo de relevamientos, pausas operativas, domicilio del ciudadano y buscador de legajos |
| Calidad y rendimiento | Línea de base de observabilidad en el pipeline, corrección de consultas repetidas y pruebas de estrés |

### :material-arrow-right-bold-box-outline: Qué continúa después del cierre

| Frente | Estado al cierre |
|---|---|
| **Constructor de formularios por convocatoria** | En desarrollo. Alcance aprobado de 270 h, de las cuales 94 h 30 min se ejecutaron dentro de agosto |
| **App de campo con el formulario por convocatoria** | Pendiente del equipo móvil. La app actual sigue funcionando sin cambios: el sistema traduce entre ambos esquemas |
| **Remediación de diseño del Programa Dispositivos** | Catorce tareas derivadas de la auditoría de interfaz, en curso |
| **Aprobación de los textos de credenciales** | Los correos están operativos; sus textos siguen publicados para revisión del Ministerio |

### :material-file-document-multiple-outline: Documentación de la versión

- [Programa Becas — el sistema construido](../funcionalidades/programa-becas-sistema.md): cómo funciona hoy, en detalle.
- [Programa Becas — propuesta original](../funcionalidades/programa-becas.md): lo que se planteó al inicio, como registro histórico.
- [Programa Dispositivos](../funcionalidades/programa-dispositivos.md): definición aprobada.
- [Módulo financiero](../financiero/index.md): consumo mes por mes y detalle por entregable.

---

## :material-server-network: Despliegue de la versión

Stack: **Docker Compose**, cinco contenedores — MySQL, Redis, app web, websockets y nginx. El código de release vive en la rama **`main`** del repositorio (sin herramientas internas ni documentación).

Los ambientes de **testing y QA de ECOM no usan esta guía**: se despliegan solos con un push a `test`/`main` vía su CI/CD. Sus diferencias están en [Si el despliegue es en Kubernetes](#si-el-despliegue-es-en-kubernetes); la configuración de variables (paso 3) es la misma.

!!! warning "Reglas fijas"
    - Esta página es pública: donde aparece `<...>` va un valor real. **Cada ambiente usa valores propios** — nunca los de otro ambiente.
    - Se opera con un usuario del grupo `docker`. **Nunca `sudo su`**: la deploy key y Docker son del usuario de despliegue.
    - `.env.production` no se versiona ni se sube al repositorio.

### :material-numeric-1-circle: Requisitos del servidor

| Requisito | Detalle |
|---|---|
| Docker Engine + Compose | Verificar: `docker --version` y `docker compose version` |
| Usuario de despliegue | En el grupo `docker`, con **deploy key de solo lectura** del repositorio |
| MySQL `8.0.32` | Pin obligatorio: builds más nuevas no arrancan en CPUs sin `x86-64-v2` (caso de la VM actual) |
| Disco | Holgura para `mysql_data` y las capas de imagen |

### :material-numeric-2-circle: Traer la versión

```bash
git clone -b main git@github.com:Mkdir-arg/Chaco-Back.git ~/chaco
cd ~/chaco
```

Si el servidor ya tiene una versión, no se re-clona: ver [Actualizar a una versión nueva](#actualizar-a-una-version-nueva).

### :material-numeric-3-circle: Configurar el ambiente

Crear `~/chaco/.env.production` con permisos restringidos:

```bash
nano .env.production
chmod 600 .env.production
```

La referencia completa de variables es **`.env.qa.example`** (raíz del repositorio, viaja en el release): cada variable indica si es obligatoria y quién provee el valor. Mínimo para levantar:

```ini
# ─── Django ───────────────────────────────────────────────
DJANGO_SECRET_KEY=<cadena-larga-y-aleatoria-nueva-para-este-ambiente>
DJANGO_DEBUG=False
ENVIRONMENT=prd

# ─── URL del ambiente ─────────────────────────────────────
# Varias direcciones van separadas por coma.
DJANGO_ALLOWED_HOSTS=<dominio-o-ip-del-servidor>
DJANGO_CSRF_TRUSTED_ORIGINS=https://<dominio-o-ip-del-servidor>
DOMINIO=<dominio-o-ip-del-servidor>

# ─── Base de datos: las lee la APLICACIÓN ─────────────────
DATABASE_NAME=chaco
DATABASE_USER=chaco
DATABASE_PASSWORD=<password-db>
DATABASE_HOST=mysql
DATABASE_PORT=3306

# ─── Base de datos: las lee el CONTENEDOR MySQL ───────────
# Deben coincidir con las de arriba.
MYSQL_DATABASE=chaco
MYSQL_USER=chaco
MYSQL_PASSWORD=<password-db>
MYSQL_ROOT_PASSWORD=<password-root-db>

# ─── Redis ────────────────────────────────────────────────
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=1

# ─── Arranque del contenedor ──────────────────────────────
# Este bloque lo lee el proceso de arranque, no Django: en Kubernetes va como
# variables de entorno del pod, no en un archivo montado.
DJANGO_SETTINGS_MODULE=config.settings_production
APP_RUNTIME=daphne
RUN_MIGRATIONS=true
# Con ENVIRONMENT=prd|qa ya es el default; se deja explícito.
RUN_COLLECTSTATIC=true
# True solo sin nginx adelante (Kubernetes). Requiere volumen persistente en /app/media.
SERVE_MEDIA=False
# No recortar: siembra RBAC, roles de Becas, roles de menú y catálogos base.
LOCAL_BOOTSTRAP_COMMANDS=seed_datos_base crear_programas
LOCAL_OPTIONAL_BOOTSTRAP_COMMANDS=procesar_vencimientos

# ─── SIIS: catálogo de programas (Becas) ──────────────────
SIIS_API_URL=https://siisapi.ecomdev.ar
SIIS_API_CLIENT_ID=<lo-provee-ECOM>
SIIS_API_CLIENT_SECRET=<lo-provee-ECOM>

# ─── Personas / Gran Base: prevalidación de ciudadanos ────
PERSONAS_API_URL=https://personas.ecomdev.ar/api/v1
PERSONAS_API_CLIENT_ID=<lo-provee-ECOM>
PERSONAS_API_CLIENT_SECRET=<lo-provee-ECOM>
PERSONAS_API_ENTIDAD_UUID=<lo-provee-ECOM>
PERSONAS_API_FUENTE_ID=13

# ─── RENAPER ──────────────────────────────────────────────
# TEST_MODE=True devuelve datos ficticios y levanta sin credenciales.
RENAPER_TEST_MODE=False
RENAPER_API_URL=<url>
RENAPER_API_USERNAME=<usuario>
RENAPER_API_PASSWORD=<password>
RENAPER_AUTH_MODE=credentials
RENAPER_HTTP_METHOD=get

# ─── Correo saliente ──────────────────────────────────────
# El envío real ocurre solo con ENVIRONMENT=prd; con qa el correo va a la
# consola del contenedor aunque el SMTP esté configurado.
EMAIL_HOST=<servidor-smtp>
EMAIL_PORT=587
EMAIL_HOST_USER=<usuario>
EMAIL_HOST_PASSWORD=<password>
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=DATAÑACH <no-responder@chaco.gob.ar>

# ─── Sesión ───────────────────────────────────────────────
SESSION_IDLE_TIMEOUT_MINUTES=15
SESSION_IDLE_WARNING_SECONDS=60
```

Quién provee cada valor:

| Grupo | Lo define |
|---|---|
| Clave secreta, base de datos, Redis, dominio | Quien monta el ambiente, con **valores nuevos** |
| `SIIS_API_*` y `PERSONAS_API_*` | **ECOM** (son sus servicios) |
| `RENAPER_*` | El organismo, vía ECOM |
| `EMAIL_*` | Infraestructura del correo institucional |

!!! danger "Errores de configuración que impiden operar"
    1. **Dominio ausente** de `DJANGO_ALLOWED_HOSTS` o `DJANGO_CSRF_TRUSTED_ORIGINS` → 400 en toda petición y errores CSRF en los formularios.
    2. **`DATABASE_*` y `MYSQL_*` sin coincidir** → los contenedores quedan *healthy* pero la app no conecta a la base.
    3. **`LOCAL_BOOTSTRAP_COMMANDS` recortado** → roles congelados (un rol nuevo del sistema no aparece nunca) y catálogos sin cargar, incluidas las localidades del selector de zona.

**Certificado TLS** — con dominio real, usar el emitido. Por IP o red privada, autofirmado:

```bash
openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
  -keyout nginx-selfsigned.key -out nginx-selfsigned.crt \
  -subj "/CN=<dominio-o-ip-del-servidor>"
```

### :material-numeric-4-circle: Levantar todo

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

El entrypoint, en cada arranque y sin intervención: espera la base → aplica migraciones → recolecta estáticos → siembra roles, programas y catálogos → cierra lo vencido en Becas.

nginx cachea la IP interna de la app al arrancar. Tras cada `up --build`, reiniciarlo (síntoma si se omite: error 500 de archivos estáticos):

```bash
docker compose -f docker-compose.prod.yml ps   # esperar chaco-web-1 healthy
docker restart chaco-nginx-1
```

### :material-numeric-5-circle: Crear el primer superusuario

El sembrado **no crea usuarios**. El primer superusuario se crea una vez, con credenciales que define quien monta el ambiente:

```bash
docker exec -it chaco-web-1 python manage.py createsuperuser
```

Variante sin interacción (deja la contraseña en el historial del shell — evitarla en servidores):

```bash
docker exec \
  -e DJANGO_SUPERUSER_USERNAME=<usuario> \
  -e DJANGO_SUPERUSER_EMAIL=<correo> \
  -e DJANGO_SUPERUSER_PASSWORD=<contraseña> \
  chaco-web-1 python manage.py createsuperuser --noinput
```

Este usuario es solo la puerta de entrada: los usuarios de trabajo se dan de alta desde **Administración → Usuarios**, con su rol.

### :material-numeric-6-circle: Verificar que quedó sano

```bash
curl -f http://localhost/health/               # 200
curl -sI http://localhost/ | head -1           # 200 — el ingreso es la raíz /, no existe /login/
docker compose -f docker-compose.prod.yml ps   # cinco contenedores healthy
docker exec chaco-web-1 python manage.py showmigrations | tail -20
```

### :material-numeric-7-circle: Tareas programadas

Se instalan **una sola vez por servidor** (no viajan con el deploy). Snippets en `docker/cron/`:

| Tarea | Horario | Si no corre |
|---|:-:|---|
| `generar_alertas` | cada hora | No se generan las alertas de legajos |
| `procesar_vencimientos` | 03:10 | Convocatorias vencidas quedan abiertas; sus relevamientos no pasan a revisión |
| `limpiar_alertas_conversaciones` | 03:30 | Se acumulan alertas ya resueltas |
| `sincronizar_programas_siis` | 04:00 | **Una baja de programa en SIIS no se detecta** |

```bash
crontab -e
# patrón: <horario> docker exec chaco-web-1 python manage.py <comando> >> ~/cron-chaco.log 2>&1
crontab -l
```

`sincronizar_programas_siis` va **solo por cron**, nunca en el arranque: depende de un servicio externo y una caída dejaría el contenedor sin levantar.

### :material-kubernetes: Si el despliegue es en Kubernetes

Misma imagen; el compose de la VM resuelve cosas que en Kubernetes se replican explícitamente. Todo lo demás de la guía aplica igual.

**1. El pod arranca con el entrypoint de la imagen.** Con `command`/`args` en el manifiesto, el entrypoint ejecuta eso y **saltea migraciones, estáticos y sembrado** — síntoma silencioso: esquema atrasado y roles faltantes. Logs esperados al arrancar:

```
Aplicando migraciones...
Ejecutando python manage.py seed_datos_base
```

Si aparece `Comando personalizado detectado`, el bootstrap no corrió. Salidas: quitar `command`/`args`, o un initContainer/Job con la misma imagen y `args: ["bootstrap"]` (one-shot: migra, recolecta, siembra y termina). Ejemplo: `docker/k8s/bootstrap-initcontainer.yaml`.

**2. Las variables van como env del pod.** Las del bloque *Arranque del contenedor* y `DJANGO_SETTINGS_MODULE` las lee el script de inicio, no Django: un archivo montado no alcanza. Síntoma típico de que no llegaron: líneas de `django.utils.autoreload` en el log del pod — significa que el contenedor está corriendo el servidor de desarrollo porque le falta `APP_RUNTIME=daphne`.

**3. HTTPS.** Con `settings_production` la app exige `DJANGO_ALLOWED_HOSTS` (falla al arrancar si falta) y redirige a HTTPS: el ingress **debe enviar `X-Forwarded-Proto: https`**, o toda petición entra en bucle de redirección.

**4. Estáticos y media.** `/static/` lo sirve la app (whitenoise; `collectstatic` es default en `prd|qa`) — sin nginx ni sidecar. `/media/`: `SERVE_MEDIA=True` para que la app lo sirva, y **PVC en `/app/media`** — sin volumen, los adjuntos se pierden al reiniciar el pod.

**5. Websockets.** Un solo proceso daphne atiende HTTP y `/ws/`; el ingress debe pasar los encabezados `Upgrade` y `Connection`.

**6. Probes.** `/health/` sirve como liveness y readiness — y hace falta además un **startupProbe** holgado (`periodSeconds: 10`, `failureThreshold: 60`): el primer arranque tarda minutos y sin él el liveness mata el bootstrap a mitad de camino, dejando el pod en loop de reinicios (exit 137, sin error en el log). Los puertos tienen que ser consistentes: `APP_PORT` = `containerPort` = `targetPort` del Service = puerto de las probes.

**7. Tareas programadas = CronJob**, uno por comando de la tabla anterior. Plantillas: `docker/k8s/cronjobs.yaml`. `sincronizar_programas_siis` jamás en el arranque del pod.

**8. Base de datos y Redis propios.** El pin `mysql:8.0.32` es una limitación de la VM, no del sistema: en Kubernetes se usa su MySQL 8 vía `DATABASE_*` (MariaDB funciona; el warning `W036` de las constraints condicionales aparece igual con ambos motores y esas reglas las valida la aplicación). Y hace falta un **Redis** provisto por la plataforma —la app lo usa para caché y websockets, un `redis:7-alpine` alcanza—, apuntado con `REDIS_*`.

### :material-update: Actualizar a una versión nueva

```bash
cd ~/chaco
git pull --ff-only origin main
docker compose -f docker-compose.prod.yml up -d --build web websocket
docker compose -f docker-compose.prod.yml ps    # esperar chaco-web-1 healthy
docker restart chaco-nginx-1
curl -f http://localhost/health/
```

Las migraciones se aplican solas en el arranque. `.env.production` no se toca (no está versionado), pero conviene **compararlo contra `.env.qa.example`** después de actualizar: una variable nueva faltante no rompe el arranque — deja la funcionalidad que depende de ella apagada, en silencio.

!!! danger "Al actualizar a esta versión: el arranque ya no crea usuarios"
    Antes el arranque creaba un superusuario con credenciales fijas; se retiró. Un ambiente en funcionamiento no se ve afectado. Si la base se recrea, el superusuario se crea a mano (paso 5). Y **si la base se sembró con una versión anterior, existe el usuario `admin` con la contraseña conocida** — cambiarla o eliminarlo:

    ```bash
    docker exec -it chaco-web-1 python manage.py changepassword admin
    ```

!!! danger "No hacer"
    - `sudo su` — como root fallan `git pull` y el deploy.
    - Editar la base a mano — el esquema lo manejan las migraciones.
    - Subir `.env.production` al repositorio.
    - Reutilizar valores de otro ambiente (clave secreta y base, sobre todo).
    - Cambiar el pin de MySQL `8.0.32` sin verificar que la VM lo soporte.
