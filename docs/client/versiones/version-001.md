# :material-package-variant-closed: Versión 001

<div class="grid cards" markdown>

-   :material-circle:{ style="color: #f59e0b" } **Estado**

    En progreso

-   :material-calendar-range: **Período**

    3 jun 2026 → en curso

-   :material-counter: **Avance**

    —

-   :material-clock-outline: **Horas consumidas**

    556h 20min (al 10/07/2026)

</div>

!!! abstract "Objetivo"
    Definir el funcionamiento de los programas **Becas** y **Dispositivos**, y desarrollar el **motor RBAC base** para dejar el sistema de permisos operativo.

---

## :material-clipboard-list-outline: Alcance de la versión

| # | Funcionalidad | Prioridad | Estado | Hs est. | Hs reales |
|:-:|---|:-:|:-:|:-:|:-:|
| 1 | [Programa Becas — análisis funcional y estimación](../funcionalidades/programa-becas.md) | Alta | Completado | — | 46h |
| 2 | Motor RBAC base | Alta | Completado | — | 22h |
| 3 | [Programa Dispositivos y Merenderos — análisis y estimación](../funcionalidades/programa-dispositivos.md) | Alta | Estimación presentada | — | 154h |
| 4 | Programa Becas — backend del backoffice | Alta | En pruebas | — | 83h |
| 5 | Programa Becas — pruebas funcionales del backend | Alta | En progreso | — | 32h |
| 6 | App de campo (React Native) | Alta | En desarrollo | — | 101h |
| 7 | Mockups y diseño UX (Becas) | Alta | En progreso | — | 65h |
| 8 | Análisis Legajo Ciudadano | Media | Completado | — | 30h |
| 9 | Design System del proyecto | Media | Completado | — | 8h |
| 10 | Reuniones y coordinación | — | — | — | 15h |
| | **Total** | | | | **556h** |

!!! note "Criterio de las horas reales"
    Las horas por funcionalidad suman el consumo registrado por frente de trabajo según el campo *Motivo* del [detalle de consumo](../financiero/detalle-tareas.md) (556 h 20 min al 10/07/2026). La estimación comprometida del desarrollo de Becas (654 h) se ejecuta en los meses siguientes — ver [estimación](../funcionalidades/estimacion-programa-becas.md).

---

## :material-server-network: Despliegue de la versión

Guía **punta a punta** para poner esta versión en un servidor propio: preparar la máquina, traer el código, configurar el ambiente y levantar todo. El sistema corre con **Docker Compose**, con cinco contenedores: base de datos MySQL, Redis, la app web, el canal de websockets y nginx como puerta de entrada.

!!! info "Contexto del entorno"
    El servidor es una VM **Ubuntu 24.04**. El código de release vive en la rama **`main`** del repositorio: es una imagen depurada del proyecto, sin herramientas internas ni documentación. Se opera siempre con un usuario del grupo `docker` (en nuestro servidor, `icore`), que corre `docker` y `git` sin `sudo`.

!!! warning "Credenciales"
    Esta página es pública: **no contiene contraseñas ni claves**. Donde aparece `<...>` va un valor real. **Cada ambiente usa sus propios valores**: no se copian los de otro y menos los de producción — una clave secreta compartida hace que una sesión firmada en un ambiente valga en el otro, y unas credenciales de base compartidas ponen los datos reales al alcance de una prueba.

!!! note "Ambientes con despliegue automático"
    Los ambientes de **testing y QA de ECOM** no se despliegan con esta guía: corren en Kubernetes y se actualizan solos a partir de un push a las ramas `test` y `main`, con la imagen que construye su propio pipeline. Esta guía aplica a un servidor administrado a mano. La configuración de variables (paso 3) es la misma en los dos casos; las diferencias específicas de Kubernetes están en la sección **Si el despliegue es en Kubernetes**, más abajo.

### :material-numeric-1-circle: Requisitos del servidor

<div class="grid cards" markdown>

-   :material-docker: **Docker + Compose**

    Docker Engine y el plugin `docker compose`. Verificar:
    ```bash
    docker --version
    docker compose version
    ```

-   :material-account-key: **Usuario de despliegue**

    En el grupo `docker` (corre `docker` y `git` sin `sudo`). Con una **deploy key de solo lectura** del repositorio para poder traer el código.

-   :material-database: **MySQL 8.0.32**

    El compose fija esa versión a propósito: las builds más nuevas no arrancan en CPUs sin `x86-64-v2`, que es el caso de nuestra VM. No cambiar el pin sin probarlo.

-   :material-memory: **Recursos**

    Los cinco contenedores conviven en una VM chica, pero la base y el build de la imagen son los que piden disco: prever holgura para `mysql_data` y para las capas de Docker.

</div>

### :material-numeric-2-circle: Traer la versión

Clonar la rama `main` (release) en `~/chaco`, con la deploy key del servidor:

```bash
git clone -b main git@github.com:Mkdir-arg/Chaco-Back.git ~/chaco
cd ~/chaco
```

!!! tip "Si el servidor ya tenía una versión anterior"
    No se vuelve a clonar: se actualiza con `git pull` (ver **Actualizar a una versión nueva**, al final de esta sección).

### :material-numeric-3-circle: Configurar el ambiente

Es el paso donde se cae la mayoría de los despliegues nuevos. Todo se resuelve con un archivo de variables.

**a. Variables de entorno** — crear `~/chaco/.env.production` (archivo privado, permisos restringidos):

```bash
nano .env.production
chmod 600 .env.production
```

!!! abstract "La plantilla completa está en el repositorio"
    El archivo **`.env.qa.example`**, en la raíz del código, es la referencia viva: lista **todas** las variables que lee la aplicación, con una nota por variable indicando si es obligatoria y **quién provee el valor**. Viaja en el release, así que ya está en el servidor después del paso anterior. Lo que sigue es el mínimo para levantar.

```ini
# ─── Django ───────────────────────────────────────────────
DJANGO_SECRET_KEY=<cadena-larga-y-aleatoria-nueva-para-este-ambiente>
DJANGO_DEBUG=False
ENVIRONMENT=prd

# ─── URL del ambiente ─────────────────────────────────────
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
# Tienen que coincidir con las de arriba, o la app no entra a su propia base.
MYSQL_DATABASE=chaco
MYSQL_USER=chaco
MYSQL_PASSWORD=<password-db>
MYSQL_ROOT_PASSWORD=<password-root-db>

# ─── Redis (caché, sesiones y websockets) ─────────────────
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=1

# ─── Arranque del contenedor ──────────────────────────────
# Este bloque lo lee el proceso de arranque, no la aplicación: en Kubernetes tiene
# que ir como variables de entorno del pod (no alcanza un archivo montado).
#
# Ajustes endurecidos para un ambiente servido: exige DJANGO_ALLOWED_HOSTS (falla al
# arrancar si falta), fuerza DEBUG=False y redirige a HTTPS. El proxy o ingress debe
# enviar el encabezado X-Forwarded-Proto: https, o las peticiones entran en bucle.
DJANGO_SETTINGS_MODULE=config.settings_production
APP_RUNTIME=daphne
RUN_MIGRATIONS=true
# Recolecta los estáticos al arrancar. Con ENVIRONMENT=prd|qa ya es el default; se
# deja explícito. La app sirve /static/ por sí sola: no hace falta nginx para eso.
RUN_COLLECTSTATIC=true
# Solo sin nginx adelante (Kubernetes): la app sirve también /media/, los archivos
# que suben los territoriales. Ese directorio necesita almacenamiento persistente.
# En la VM queda en False, porque /media/ lo sirve nginx.
SERVE_MEDIA=False
# Siembra roles, capacidades, programas y catálogos base. Conviene dejarlo tal cual:
# recortar esta lista deja los roles congelados. No crea usuarios: el superusuario se
# crea a mano en el paso 5, con las credenciales que definan ustedes.
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
# En True devuelve datos ficticios y el ambiente levanta sin credenciales.
RENAPER_TEST_MODE=False
RENAPER_API_URL=<url>
RENAPER_API_USERNAME=<usuario>
RENAPER_API_PASSWORD=<password>
RENAPER_AUTH_MODE=credentials
RENAPER_HTTP_METHOD=get

# ─── Correo saliente ──────────────────────────────────────
# Sin esto el alta de usuario funciona, pero la invitación no sale. El envío real
# ocurre solo con ENVIRONMENT=prd: con qa el correo va a la consola del pod (a
# propósito, para que un ambiente de prueba no mande mails de verdad).
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
| `SIIS_API_*` y `PERSONAS_API_*` | **ECOM**: son sus servicios y ellos emiten las credenciales |
| `RENAPER_*` | El organismo, gestionado a través de ECOM |
| `EMAIL_*` | El área de infraestructura que administra el correo institucional |

!!! danger "Las dos causas de «desplegué y no anda»"
    **1. El dominio ausente.** Si el dominio o la IP del ambiente no figuran en `DJANGO_ALLOWED_HOSTS` **y** en `DJANGO_CSRF_TRUSTED_ORIGINS`, la aplicación responde **400 a toda petición** y los formularios fallan por CSRF. Si se entra por más de una dirección, van todas separadas por coma.

    **2. La base vacía sin sembrar.** Una base nueva no tiene roles, permisos, programas ni catálogos. Eso lo resuelve `LOCAL_BOOTSTRAP_COMMANDS` en el arranque, y por eso conviene no recortar esa lista: `seed_datos_base` es un paraguas que siembra el RBAC, los roles del programa Becas, los roles de menú y los catálogos base —incluidas las localidades que usa el selector de zona de los relevamientos—. **Si se recorta, los roles quedan congelados en el estado en que se sembró la base** y un rol nuevo del sistema no aparece nunca. Y como no se crea ningún usuario por su cuenta, hay que crear el primer superusuario a mano: es el paso 5.

!!! warning "Los dos bloques de base de datos no son redundantes"
    `DATABASE_*` las lee **Django**; `MYSQL_*` las lee el **contenedor de MySQL** cuando crea la base por primera vez. Si no coinciden, MySQL levanta bien y la aplicación no puede entrar a su propia base. Es un error difícil de diagnosticar porque los contenedores quedan *healthy*.

**b. Certificado** — si el acceso es por un dominio con certificado emitido, se usa ese. Para un acceso por IP o dentro de una red privada alcanza un autofirmado:

```bash
openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
  -keyout nginx-selfsigned.key -out nginx-selfsigned.crt \
  -subj "/CN=<dominio-o-ip-del-servidor>"
```

### :material-numeric-4-circle: Levantar todo

```bash
cd ~/chaco
docker compose -f docker-compose.prod.yml up -d --build
```

Al arrancar, el contenedor de la app hace **solo, sin intervención**:

- [x] Espera a que la base esté lista y **aplica las migraciones** (crea o actualiza las tablas).
- [x] Recolecta los archivos estáticos.
- [x] **Siembra los datos base**: superadmin, roles y permisos (RBAC), programas.
- [x] **Cierra lo que esté vencido** en Becas.

!!! warning "Reiniciar nginx después de levantar o reconstruir"
    nginx memoriza la dirección interna de la app cuando arranca. Tras un `up --build` hay que reiniciarlo o puede quedar apuntando al contenedor viejo (síntoma: error 500 con mensajes de archivos estáticos). Conviene esperar a que la app esté *healthy* antes:
    ```bash
    docker compose -f docker-compose.prod.yml ps   # esperar chaco-web-1 healthy
    docker restart chaco-nginx-1
    ```

### :material-numeric-5-circle: Crear el primer superusuario

El sistema **no crea ningún usuario por su cuenta**: el sembrado del paso anterior deja los roles y los programas, pero ninguna cuenta. El primer superusuario se crea una sola vez, y **las credenciales las define quien monta el ambiente**:

```bash
docker exec -it chaco-web-1 python manage.py createsuperuser
```

Pide usuario, correo y contraseña de forma interactiva. Si hace falta hacerlo sin interacción —por ejemplo desde un script—, se pasan por variables de entorno:

```bash
docker exec \
  -e DJANGO_SUPERUSER_USERNAME=<usuario> \
  -e DJANGO_SUPERUSER_EMAIL=<correo> \
  -e DJANGO_SUPERUSER_PASSWORD=<contraseña> \
  chaco-web-1 python manage.py createsuperuser --noinput
```

!!! warning "Elegir una contraseña propia, y no dejarla en el historial"
    Ninguna versión del sistema trae usuarios ni contraseñas por defecto: **la contraseña la eligen ustedes**. La forma interactiva es preferible en un ambiente servido, porque la variante con variables deja la contraseña en el historial del shell.

!!! tip "Este usuario es solo la puerta de entrada"
    El superusuario tiene acceso total y sirve para entrar la primera vez. Los usuarios de trabajo —administradores de programa, coordinadores, referentes y territoriales— se dan de alta **desde el propio sistema**, en Administración → Usuarios, con el rol que corresponda.

### :material-numeric-6-circle: Verificar que quedó sano

```bash
curl -f http://localhost/health/               # debe responder 200
curl -sI http://localhost/ | head -1           # el ingreso, debe responder 200
docker compose -f docker-compose.prod.yml ps   # los cinco contenedores en healthy
docker exec chaco-web-1 python manage.py showmigrations | tail -20
```

!!! tip "El acceso al sistema es la raíz"
    El ingreso está en `/`. No existe `/login/`.

### :material-numeric-7-circle: Tareas programadas

Hay trabajo periódico que **no** corre dentro de la aplicación: lo dispara el cron del usuario de despliegue. Los snippets están versionados en `docker/cron/` dentro del código. **Se instalan una sola vez por servidor y no viajan con el despliegue**: un servidor nuevo los necesita de nuevo.

| Tarea | Horario | Qué pasa si no corre |
|---|:-:|---|
| `generar_alertas` | cada hora | No se generan las alertas de legajos |
| `procesar_vencimientos` | 03:10 | Las convocatorias vencidas quedan abiertas y sus relevamientos no pasan a revisión |
| `limpiar_alertas_conversaciones` | 03:30 | Se acumulan alertas de conversaciones ya resueltas |
| `sincronizar_programas_siis` | 04:00 | **Una baja de programa en SIIS no se detecta** y el segmento sigue operando como si el programa estuviera vigente |

```bash
crontab -e
# pegar las líneas de los archivos de docker/cron/, con el patrón:
#   <horario> docker exec chaco-web-1 python manage.py <comando> >> ~/cron-chaco.log 2>&1
crontab -l      # verificar que quedaron
```

!!! abstract "Por qué algunas van al cron y no al arranque"
    `procesar_vencimientos` trabaja solo sobre la base propia, así que puede correr también en cada arranque sin riesgo. `sincronizar_programas_siis` depende de un servicio externo: si se pusiera en el arranque, una caída de ese servicio **dejaría el contenedor sin levantar**. Por eso va únicamente por cron.

### :material-kubernetes: Si el despliegue es en Kubernetes

La imagen es la misma, pero el `docker-compose.prod.yml` de la VM resuelve varias cosas que en Kubernetes hay que replicar explícitamente. Esta es la lista de diferencias; todo lo demás de la guía (variables, sembrado, superusuario, verificación) aplica igual.

**1. El pod tiene que arrancar con el entrypoint de la imagen.** Es el punto más importante. Si el manifiesto define `command` o `args`, el entrypoint ejecuta eso directamente y **se saltea las migraciones, los estáticos y el sembrado**. El síntoma es silencioso: la aplicación levanta y funciona, pero con el esquema de base atrasado y con roles que faltan. En los logs del arranque del pod tienen que verse estas líneas:

```
Aplicando migraciones...
Ejecutando python manage.py seed_datos_base
```

Si en cambio aparece `Comando personalizado detectado: ...`, el bootstrap no corrió. Dos salidas: quitar el `command`/`args` del manifiesto, o correrlo aparte con un **initContainer o Job usando la misma imagen con `args: ["bootstrap"]`** — es un modo one-shot que ejecuta migraciones, estáticos y sembrado y termina. Hay un ejemplo completo en `docker/k8s/bootstrap-initcontainer.yaml`, dentro del repositorio.

**2. Las variables van como variables de entorno del pod, no solo en un archivo.** Las del bloque *Arranque del contenedor* (`RUN_MIGRATIONS`, `RUN_COLLECTSTATIC`, `LOCAL_BOOTSTRAP_COMMANDS`, `APP_RUNTIME`) y `DJANGO_SETTINGS_MODULE` las lee el script de arranque, no la aplicación: un archivo `.env.production` montado no alcanza para ellas.

**3. HTTPS detrás del ingress.** Con `DJANGO_SETTINGS_MODULE=config.settings_production` la aplicación exige `DJANGO_ALLOWED_HOSTS` (falla al arrancar si falta, a propósito) y redirige todo a HTTPS. El ingress **debe enviar el encabezado `X-Forwarded-Proto: https`** al pod; sin él, cada petición entra en un bucle de redirección infinito.

**4. Estáticos y archivos subidos.** La app sirve `/static/` **por sí sola** (whitenoise), y con `ENVIRONMENT=prd|qa` los recolecta al arrancar por defecto: no hace falta nginx ni un sidecar. Para `/media/` —los archivos que suben los territoriales— hay dos cosas: con `SERVE_MEDIA=True` la app también los sirve, y el directorio `/app/media` necesita **almacenamiento persistente** (un PVC); sin volumen, los adjuntos se pierden en cada reinicio del pod.

**5. Websockets.** Con `APP_RUNTIME=daphne`, el mismo proceso atiende HTTP y websockets (ruta `/ws/`). El ingress tiene que dejar pasar los encabezados `Upgrade` y `Connection` hacia el pod.

**6. Probes.** `/health/` responde 200 y sirve tal cual como liveness y readiness probe.

**7. Tareas programadas = CronJob.** Cada comando de la tabla anterior es un `CronJob` de Kubernetes (`python manage.py <comando>` sobre la misma imagen). Hay plantillas de los cuatro en `docker/k8s/cronjobs.yaml`, dentro del repositorio. `sincronizar_programas_siis` **nunca va en el arranque del pod**: depende de un servicio externo, y una caída de ese servicio dejaría el pod sin levantar.

**8. Base de datos propia.** El pin de `mysql:8.0.32` es una limitación de nuestra VM, no del sistema: en Kubernetes usan su MySQL 8 con los valores de conexión en `DATABASE_*`.

### :material-update: Actualizar a una versión nueva

Sobre un servidor ya configurado:

```bash
cd ~/chaco
git pull --ff-only origin main
docker compose -f docker-compose.prod.yml up -d --build web websocket
docker compose -f docker-compose.prod.yml ps    # esperar chaco-web-1 healthy
docker restart chaco-nginx-1
curl -f http://localhost/health/
```

Las migraciones vuelven a aplicarse solas en el arranque, antes de que la aplicación atienda pedidos. El archivo `.env.production` no se toca: no está versionado y el `git pull` no lo alcanza.

!!! tip "Si la versión trae variables nuevas"
    Al agregarse una integración pueden aparecer variables que el ambiente no tenía. Conviene comparar `.env.production` contra `.env.qa.example` después de cada actualización: una variable faltante no rompe el arranque, pero deja la funcionalidad que depende de ella silenciosamente apagada.

!!! danger "Cambio importante de esta versión: el arranque ya no crea usuarios"
    Hasta la versión anterior, el arranque creaba un superusuario con **usuario y contraseña fijos**, los mismos en cualquier ambiente. Se retiró, porque dejaba una credencial conocida en todo servidor donde se levantara el sistema. Qué implica al actualizar:

    - **Un ambiente en funcionamiento no se ve afectado**: los usuarios que ya existen siguen igual y se sigue entrando como siempre.
    - **Si en algún momento se recrea la base**, hay que crear el superusuario a mano: es el paso 5 de esta guía.
    - **Si el ambiente se sembró con una versión anterior, tiene un usuario `admin` con la contraseña conocida.** Hay que cambiarla —o eliminar ese usuario si no se usa— desde Administración → Usuarios, o con:

    ```bash
    docker exec -it chaco-web-1 python manage.py changepassword admin
    ```

!!! danger "Cosas a NO hacer"
    - **No operar con `sudo su`**: la clave de acceso al repositorio y a Docker es del usuario de despliegue; como root fallan `git pull` y el deploy.
    - **No editar la base a mano**: el esquema lo manejan las migraciones.
    - **No subir `.env.production` al repositorio**: contiene secretos.
    - **No reutilizar los valores de otro ambiente**, en especial la clave secreta y las credenciales de base.
    - **No cambiar el pin de MySQL 8.0.32** sin verificar que la VM lo soporte.
