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

Guía **punta a punta** para poner esta versión en el servidor: preparar la máquina, traer el código y levantar todo. El sistema corre con **Docker Compose** (contenedores: base de datos MySQL, Redis, la app web, el canal de websockets y nginx como puerta de entrada).

!!! info "Contexto del entorno"
    El servidor de producción es una VM **Ubuntu 24.04** de acceso **solo por VPN**. El código de release vive en la rama **`main`** del repositorio (es una imagen depurada del proyecto: no incluye herramientas internas ni documentación). Se opera siempre con el usuario **`icore`** (que pertenece al grupo `docker`).

!!! warning "Credenciales"
    Esta página es pública: **no contiene contraseñas ni claves**. Donde aparece `<...>` va un valor real que provee el equipo de desarrollo (clave secreta de Django, contraseñas de la base, usuario RENAPER, etc.). Esos valores se cargan en el archivo `.env.production`, que **nunca** se versiona.

### :material-numeric-1-circle: Requisitos del servidor

<div class="grid cards" markdown>

-   :material-docker: **Docker + Compose**

    Docker Engine y el plugin `docker compose`. Verificar:
    ```bash
    docker --version
    docker compose version
    ```

-   :material-account-key: **Usuario `icore`**

    En el grupo `docker` (corre `docker` y `git` sin `sudo`). Con una **deploy key de solo lectura** de GitHub para clonar el repo.

</div>

### :material-numeric-2-circle: Traer la versión

Clonar la rama `main` (release) en `~/chaco`, usando la deploy key del servidor:

```bash
git clone -b main git@github.com:Mkdir-arg/Chaco.git ~/chaco
cd ~/chaco
```

!!! tip "Si el servidor ya tenía una versión anterior"
    No se vuelve a clonar: se actualiza con `git pull` (ver **Actualizar a una versión nueva**, al final de esta sección).

### :material-numeric-3-circle: Configurar el entorno

**a. Variables de entorno** — crear `~/chaco/.env.production` (archivo privado, permisos restringidos):

```bash
nano .env.production      # cargar las variables (ver plantilla)
chmod 600 .env.production
```

Plantilla de las variables clave (los valores reales los provee el equipo):

```ini
DJANGO_SECRET_KEY=<clave-secreta-nueva>
DJANGO_DEBUG=False
ENVIRONMENT=prd
DJANGO_ALLOWED_HOSTS=<ip-o-dominio-del-servidor>
DJANGO_CSRF_TRUSTED_ORIGINS=https://<ip-o-dominio-del-servidor>
# Base de datos (contenedor MySQL del propio compose)
MYSQL_DATABASE=chaco
MYSQL_USER=chaco
MYSQL_PASSWORD=<password-db>
MYSQL_ROOT_PASSWORD=<password-root-db>
# Integración RENAPER (la provee el equipo)
RENAPER_API_URL=<url>
RENAPER_API_USERNAME=<usuario>
RENAPER_API_PASSWORD=<password>
```

**b. Certificado** — como el acceso es por IP sobre VPN, se usa un certificado autofirmado:

```bash
openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
  -keyout nginx-selfsigned.key -out nginx-selfsigned.crt \
  -subj "/CN=<ip-del-servidor>"
```

### :material-numeric-4-circle: Levantar todo

```bash
cd ~/chaco
docker compose -f docker-compose.prod.yml up -d --build
```

Al arrancar, el contenedor de la app hace **solo, sin intervención**:

- [x] Espera a que la base esté lista y **aplica las migraciones** (crea/actualiza las tablas).
- [x] Recolecta los archivos estáticos.
- [x] **Siembra los datos base**: superadmin, roles y permisos (RBAC), programas.
- [x] **Cierra lo que esté vencido** en Becas (el proceso de vencimientos corre en cada arranque).

!!! warning "Reiniciar nginx después de levantar/reconstruir"
    nginx memoriza la dirección interna de la app cuando arranca. Tras un `up --build` hay que reiniciarlo o puede quedar apuntando al contenedor viejo (síntoma: error 500):
    ```bash
    docker restart chaco-nginx-1
    ```

**Verificar que quedó sano:**

```bash
curl -f http://localhost/health/      # debe responder 200
docker compose -f docker-compose.prod.yml ps   # todos "healthy"
```

### :material-numeric-5-circle: Cierre automático de vencidos (cron diario)

El cierre de convocatorias vencidas **ya corre en cada arranque** del servidor (paso anterior). Para que además se ejecute **todos los días a la madrugada** sin depender de un reinicio, se agrega **una línea** al cron del usuario `icore` (una sola vez):

```bash
( crontab -l 2>/dev/null | grep -vF procesar_vencimientos; \
  echo '10 3 * * * docker exec chaco-web-1 python manage.py procesar_vencimientos >> ~/cron-chaco.log 2>&1' ) | crontab -

crontab -l      # verificar que la línea quedó
```

!!! abstract "Qué hace"
    Todos los días a las **03:00** cierra las convocatorias de Becas cuya fecha de fin ya pasó y manda sus relevamientos abiertos a **En revisión**. Es idempotente: si corre de más o se saltea un día, no genera problemas.

### :material-update: Actualizar a una versión nueva

Para desplegar una versión posterior sobre un servidor ya configurado:

```bash
cd ~/chaco
git pull --ff-only
docker compose -f docker-compose.prod.yml up -d --build web websocket
docker restart chaco-nginx-1
curl -f http://localhost/health/
```

Las migraciones y el cierre de vencidos vuelven a correr solos en el arranque. El archivo `.env.production` no se toca (no está versionado).

!!! danger "Cosas a NO hacer"
    - **No operar con `sudo su`**: la clave de acceso a GitHub y a Docker es del usuario `icore`; como root fallan `git pull` y el deploy.
    - **No editar la base a mano**: el esquema lo manejan las migraciones.
    - **No subir `.env.production` al repositorio**: contiene secretos.
