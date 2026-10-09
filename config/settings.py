import importlib.util
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from django.contrib.messages import constants as messages
from dotenv import load_dotenv

from core.logging_config import construir_logging, purgar_logs_viejos

BASE_DIR = Path(__file__).resolve().parent.parent

# Carga base para desarrollo local
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR / ".env.local")

# En despliegues se puede forzar archivo de entorno (ej: .env.production)
ENV_FILE = os.environ.get("DJANGO_ENV_FILE")
if ENV_FILE:
    load_dotenv(BASE_DIR / ENV_FILE, override=False)
elif (BASE_DIR / ".env.production").exists() and os.environ.get("ENVIRONMENT") == "prd":
    load_dotenv(BASE_DIR / ".env.production", override=False)

DEBUG = os.environ.get("DJANGO_DEBUG", "False") == "True"
ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")  # dev|qa|prd
PYTEST_RUNNING = "pytest" in sys.argv or os.environ.get("PYTEST_RUNNING") == "1"

# Motor real en los tests (TST-01). La suite corre sobre SQLite en memoria
# (``PYTEST_RUNNING=1``), donde no se ven ni el UUID con guiones de MariaDB, ni
# ``CONVERT_TZ`` sobre una base sin tablas de zona horaria, ni los
# ``select_for_update``, que ahí son un no-op. Los tests marcados ``@tag("mysql")``
# necesitan el motor de producción, y pedirlo es explícito: esta variable lleva
# **qué** motor se espera (``mariadb:10.11``, ``mariadb:11``, ``mysql:8.0``), con
# las ``DATABASE_*`` apuntando a ese servidor. Vacía, no cambia nada.
# ``core/tests/test_motor_real.py`` enfrenta el valor contra el servidor que
# contestó: un servicio que no levantó la imagen pedida deja el paso en rojo en
# vez de volver a medir SQLite sin que nadie se entere.
TEST_MOTOR = os.environ.get("DJANGO_TEST_MOTOR", "")

# Con qué servidor arranca la imagen (`docker-entrypoint.sh`): `runserver`, `gunicorn`
# o `daphne`. No es lo mismo para los websockets ni para las conexiones de base, así
# que se lee una sola vez y se usa en los dos lugares.
APP_RUNTIME = os.environ.get("APP_RUNTIME", "runserver")

websockets_enabled_env = os.environ.get("WEBSOCKETS_ENABLED")
if websockets_enabled_env is None:
    WEBSOCKETS_ENABLED = APP_RUNTIME == "daphne"
else:
    WEBSOCKETS_ENABLED = websockets_enabled_env == "True"

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("DJANGO_SECRET_KEY debe estar configurada en variables de entorno")

LANGUAGE_CODE = "es-ar"
TIME_ZONE = "America/Argentina/Buenos_Aires"
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Hosts permitidos
hosts_env = os.getenv("DJANGO_ALLOWED_HOSTS", "")
hosts = [h.strip() for h in hosts_env.split(",") if h.strip()]
if DEBUG:
    for h in ("localhost", "127.0.0.1", "0.0.0.0"):
        if h not in hosts:
            hosts.append(h)
    if "*" not in hosts:
        hosts.append("*")

# Nombres de servicios Docker internos
for h in ("app", "web", "websocket"):
    if h not in hosts:
        hosts.append(h)

ALLOWED_HOSTS = list(dict.fromkeys(hosts))

# CSRF trusted origins via env para evitar hardcode de IPs/dominios
csrf_env = os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "")
CSRF_TRUSTED_ORIGINS = [u.strip() for u in csrf_env.split(",") if u.strip()]
if DEBUG:
    CSRF_TRUSTED_ORIGINS += [
        "http://localhost",
        "http://127.0.0.1",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:9000",
        "http://127.0.0.1:9000",
    ]
CSRF_TRUSTED_ORIGINS = list(dict.fromkeys(CSRF_TRUSTED_ORIGINS))

# El 403 de CSRF del portal público tiene que ser recuperable, no la pantalla
# cruda de Django: ver `config.views.csrf_failure`.
CSRF_FAILURE_VIEW = "config.views.csrf_failure"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.admindocs",
    "rest_framework",
    "rest_framework.authtoken",
    # Sin la app, `DEFAULT_SCHEMA_CLASS` y `SPECTACULAR_SETTINGS` quedaban
    # colgados: `/api/docs/` y `/api/redoc/` daban 500 (`TemplateDoesNotExist`)
    # y no existía `manage.py spectacular`, así que el esquema no se podía
    # validar en CI (RED-36, auditoría oct-2026).
    "drf_spectacular",
    # Los bundles de Swagger-UI y Redoc, vendorizados. Va después de
    # `drf_spectacular` y existe solo para que `collectstatic` los encuentre.
    "drf_spectacular_sidecar",
    # `django-filter` ya estaba en `requirements.txt` y seis ViewSets declaran
    # `DjangoFilterBackend`, pero sin la app el cargador por directorios no
    # encontraba `django_filters/rest_framework/form.html`: la página navegable
    # de DRF —lo que recibe cualquiera que abra `/api/legajos/ciudadanos/` en el
    # navegador— daba 500 al dibujar el formulario de filtros (#521, QA de
    # testing 06/10/2026). No trae modelos ni migraciones: solo templates y los
    # `FilterSet` que ya se estaban usando.
    "django_filters",
    "channels",
    "django_redis",
    # OPS-13 (Cambio 196): acá estaban las tres apps de `django-health-check`. OPS-04 ya
    # les había sacado las URLs (Cambio 153) y las sondas del sistema son la app
    # `healthcheck` de este repo (`/health/` y `/health/ready/`). Lo que faltaba para
    # poder retirarlas era la limpieza que `core.0003` hace: su tabla
    # (`health_check_db_testmodel`) y sus dos filas de `django_migrations`
    # (`db.0001_initial` y `health_check_db.0001_initial`; el `app_label` cambió entre
    # versiones del paquete, por eso son dos). Sin eso quedaban una tabla sin modelo y
    # dos filas sin archivo en icore, testing y PRD.
    "users",
    "core",
    "dashboard",
    "legajos",
    "configuracion",
    "conversaciones",
    "portal",
    "programas",
    "healthcheck",
]

# Silk (profiling) y django-extensions (`shell_plus`, `show_urls`): solo en desarrollo,
# nunca en producción. OPS-13: `django_extensions` estaba arriba, incondicional, así que
# viajaba en la imagen de PRD con sus comandos cargados; los dos paquetes pasaron a
# `requirements-dev.txt` y la imagen (`requirements.txt`) ya no los trae.
#
# Se agregan solo **si están instalados**, y no a secas, porque el `docker-compose.yml` de
# desarrollo levanta esa misma imagen con `DJANGO_DEBUG=True`: con un `INSTALLED_APPS`
# incondicional el contenedor moriría al importar. Faltando, lo único que se pierde es el
# profiling y `shell_plus`; la app arranca igual.
_APPS_DE_DESARROLLO = ("django_extensions", "silk")
if DEBUG:
    INSTALLED_APPS += [app for app in _APPS_DE_DESARROLLO if importlib.util.find_spec(app) is not None]

#: Lo lee `config/urls.py` para montar `/silk/` solo cuando la app entró de verdad.
SILK_HABILITADO = "silk" in INSTALLED_APPS

if PYTEST_RUNNING:
    INSTALLED_APPS += ["zeal"]

if os.environ.get("DJANGO_SYNCDB_PROJECT_APPS", "False") == "True":
    MIGRATION_MODULES = {
        "users": None,
        "core": None,
        "dashboard": None,
        "legajos": None,
        "configuracion": None,
        "conversaciones": None,
        "portal": None,
        "programas": None,
    }

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Sirve /static/ desde la propia app. En la VM nginx responde esas rutas antes
    # de llegar acá; en Kubernetes es lo que evita depender de un sidecar.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.gzip.GZipMiddleware",
    "core.middleware.ApiCorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # SEC-35 · Va primero de los propios: una sesión vencida por inactividad no
    # tiene por qué pagar el Profile de la sesión única ni terminar en la pantalla
    # de cambio de clave obligatorio; termina en el login.
    "core.middleware.ExpiracionPorInactividadMiddleware",
    "core.middleware.PortalCiudadanoMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "users.middleware.BackofficeSingleSessionMiddleware",
    "users.middleware.CambioContrasenaObligatorioMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # CSP y Permissions-Policy: el ingress reescribe X-Frame-Options con una
    # directiva obsoleta, así que el anti-clickjacking real es frame-ancestors.
    "config.middlewares.security_headers.SecurityHeadersMiddleware",
    "core.middleware.RequestLoggingMiddleware",
]


def _performance_query_monitoring_enabled():
    return os.environ.get("PERFORMANCE_QUERY_MONITORING_ENABLED", "False") == "True"


# Apagado por defecto; los relevamientos efímeros lo habilitan explícitamente.
PERFORMANCE_QUERY_MONITORING_ENABLED = _performance_query_monitoring_enabled()
PERFORMANCE_METRICS_WINDOW_SECONDS = int(os.environ.get("PERFORMANCE_METRICS_WINDOW_SECONDS", "3600"))
PERFORMANCE_METRICS_RETENTION_SECONDS = int(os.environ.get("PERFORMANCE_METRICS_RETENTION_SECONDS", "86400"))
PERFORMANCE_METRICS_NAMESPACE = os.environ.get("PERFORMANCE_METRICS_NAMESPACE", "")
PERFORMANCE_QUERY_SAMPLE_RATE = float(
    os.environ.get("PERFORMANCE_QUERY_SAMPLE_RATE", "0.2" if ENVIRONMENT == "prd" else "1.0")
)
PERFORMANCE_REDIS_TIMEOUT_SECONDS = float(os.environ.get("PERFORMANCE_REDIS_TIMEOUT_SECONDS", "0.25"))
PERFORMANCE_REDIS_RECOVERY_SECONDS = float(os.environ.get("PERFORMANCE_REDIS_RECOVERY_SECONDS", "60"))
PERFORMANCE_N1_WARNING_INTERVAL_SECONDS = float(os.environ.get("PERFORMANCE_N1_WARNING_INTERVAL_SECONDS", "60"))
if not 0 <= PERFORMANCE_QUERY_SAMPLE_RATE <= 1:
    raise ValueError("PERFORMANCE_QUERY_SAMPLE_RATE debe estar entre 0 y 1")
if PERFORMANCE_REDIS_TIMEOUT_SECONDS <= 0:
    raise ValueError("PERFORMANCE_REDIS_TIMEOUT_SECONDS debe ser mayor que 0")
if PERFORMANCE_REDIS_RECOVERY_SECONDS < 0:
    raise ValueError("PERFORMANCE_REDIS_RECOVERY_SECONDS no puede ser negativo")
if PERFORMANCE_N1_WARNING_INTERVAL_SECONDS < 0:
    raise ValueError("PERFORMANCE_N1_WARNING_INTERVAL_SECONDS no puede ser negativo")
PERFORMANCE_CI = os.environ.get("PERFORMANCE_CI") == "1"
if PERFORMANCE_QUERY_MONITORING_ENABLED:
    # Debe envolver sesión y autenticación: agregado al final subcontaba el costo real.
    MIDDLEWARE.insert(0, "config.middlewares.query_counter.QueryCountMiddleware")

if PYTEST_RUNNING:
    MIDDLEWARE += ["zeal.middleware.zeal_middleware"]
    ZEAL_RAISE = True
    ZEAL_ALLOWLIST = []

# El runner de Django, con la salida a la red cortada (SIIS-09): un test que
# parchea el lugar equivocado tiene que fallar, no salir a internet y afirmar
# algo que nunca se ejercitó. Ver ``core/tests/runner.py``.
TEST_RUNNER = "core.tests.runner.RunnerSinRed"

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                # RED-13: esto era `conversaciones.context_processors.user_groups`.
                # Cuatro de sus variables (`user_groups_list`, `user_primary_group`,
                # `user_is_superuser`, `websockets_enabled`) no son de esa app y las
                # lee `includes/base.html`, que extiende todo el backoffice.
                "core.context_processors.identidad_usuario",
                "core.context_processors.sidebar_badges",
                "core.context_processors.session_idle_config",
                "portal.context_processors.gtm",
            ],
        },
    },
]

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
]

# En ambientes servidos: manifest (URLs con hash, cacheables) + precompresión de
# whitenoise. Antes solo "prd" usaba manifest, con lo cual un QA quedaba con
# estáticos sin hash y distinto de producción.
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": (
            "whitenoise.storage.CompressedManifestStaticFilesStorage"
            if ENVIRONMENT in ("prd", "qa")
            else "django.contrib.staticfiles.storage.StaticFilesStorage"
        ),
    },
}

# `/media/` lo sirve SIEMPRE `core.views.media.media_protegida`, que exige sesión
# y pertenencia por archivo (SEC-09 etapa 2). No hay perilla para apagarlo: ahí
# viven los documentos del ciudadano y los padrones.
#
# `SERVE_MEDIA` existió hasta el Cambio 188 para decidir si la ruta se registraba;
# con ella apagada `/media/` caía en 404 y, con DEBUG, lo servía `static()` **sin
# sesión** (R0b-07). Quien todavía la tenga en su entorno puede dejarla: se ignora.
#
# Lo único configurable es **quién entrega los bytes** una vez autorizado:
# con MEDIA_X_ACCEL=True la respuesta sale vacía con
# `X-Accel-Redirect: /protected-media/<ruta>` y el archivo lo manda el servidor de
# adelante sin pasar por Python (menos memoria y sendfile). Requiere ese
# `location internal`: nginx.conf ya lo tiene; en ECOM depende del ingress
# (D-09/H-05), así que el default es apagado y los entrega Django.
MEDIA_X_ACCEL = os.environ.get("MEDIA_X_ACCEL", "False") == "True"

LOGIN_URL = "users:login"
LOGIN_REDIRECT_URL = "core:inicio"
LOGOUT_REDIRECT_URL = "users:login"
ACCOUNT_FORMS = {"login": "users.forms.UserLoginForm"}

EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
# STARTTLS en el 587 es exactamente EMAIL_USE_TLS (EMAIL_USE_SSL es el 465 implícito).
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True").lower() == "true"
# El envío es sincrónico (no hay cola): sin timeout un SMTP lento cuelga el
# request del alta de usuario hasta que corte el gateway. En 5 s desde SIIS-09:
# el correo es el último eslabón de «Aprobar», después de dos llamadas a SIIS,
# y es el que menos puede costar — si no sale, el caso igual quedó resuelto.
EMAIL_TIMEOUT = int(os.getenv("EMAIL_TIMEOUT", "5"))
# El backend lo decide la presencia de EMAIL_HOST, no el ENVIRONMENT: qa usa el
# mismo SMTP que prd, y el dev local sigue en consola sin configurar nada.
EMAIL_BACKEND = (
    "django.core.mail.backends.smtp.EmailBackend" if EMAIL_HOST else "django.core.mail.backends.console.EmailBackend"
)
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "DATAÑACH <no-responder@datanach.local>")
# QA y producción comparten casilla y plantilla: el prefijo en el asunto es lo
# único que distingue un correo de prueba de uno real en la bandeja del usuario.
EMAIL_ASUNTO_PREFIJO = "" if ENVIRONMENT == "prd" else f"[{ENVIRONMENT.upper()}] "
# Pie de los correos. Vacío = la línea no se renderiza (a definir con el cliente).
EMAIL_SOPORTE = os.getenv("EMAIL_SOPORTE", "")
EMAIL_PIE_DIRECCION = os.getenv("EMAIL_PIE_DIRECCION", "")

# Vencimiento del enlace de recupero. Los correos (backoffice y portal) prometen
# 24 h; el default de Django son 3 días.
PASSWORD_RESET_TIMEOUT = int(os.getenv("PASSWORD_RESET_TIMEOUT", "86400"))

# Los tags viajan en ``data-tags`` (base.html, portal/base.html) y ``nodo-toast.js``
# (``resolveType``) elige la variante por estas palabras: no poner clases CSS acá.
MESSAGE_TAGS = {
    messages.DEBUG: "info",
    messages.INFO: "info",
    messages.SUCCESS: "success",
    messages.WARNING: "warning",
    messages.ERROR: "error",
}

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.environ.get("DATABASE_NAME"),
        "USER": os.environ.get("DATABASE_USER"),
        "PASSWORD": os.environ.get("DATABASE_PASSWORD"),
        "HOST": os.environ.get("DATABASE_HOST"),
        "PORT": os.environ.get("DATABASE_PORT"),
        "OPTIONS": {
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
            "charset": "utf8mb4",
            "isolation_level": "read committed",
            "autocommit": True,
            "connect_timeout": 10,
            # OPS-05 / D-O05. Los 10 s son el límite acordado con ECOM para el tráfico
            # (Cambio 91) y ahí se quedan: subirlos corre el corte hacia adelante sin
            # arreglar la consulta lenta. Lo que no puede valer 10 s es el `migrate`: en
            # MySQL/MariaDB no hay DDL transaccional, así que un ALTER que espera el
            # metadata lock más de 10 s devuelve un 2013 al cliente y **se aplica igual**
            # en el servidor — esquema adelantado, migración sin fila en
            # `django_migrations` y un deploy que no se arregla reintentando. El
            # `docker-entrypoint.sh` levanta estas dos variables solo para el bloque de
            # migraciones y sembrado, sin exportarlas al proceso del server.
            "read_timeout": int(os.environ.get("DB_READ_TIMEOUT", "10")),
            "write_timeout": int(os.environ.get("DB_WRITE_TIMEOUT", "10")),
        },
        # PERF-08. Django guarda la conexión persistente en un `local()` **por hilo**
        # y la devuelve al cerrar el request. Bajo daphne cada request HTTP lo atiende
        # un hilo nuevo del pool de `asgiref` (`sync_to_async` con `thread_sensitive`
        # no reusa el mismo hilo entre requests), así que ninguna conexión se reutiliza
        # jamás: 200 requests abren 200 conexiones y las que no alcanza a cerrar el
        # request quedan vivas hasta que pasa el GC cíclico. Medido con la sonda
        # `poc/perf_harness/asgi_conn_probe.py`: con 60 quedaban 9 abiertas (50 de 50
        # con el GC apagado); con 0, ninguna. Reutilizar de verdad exige WSGI, que es
        # lo que corre icore (`APP_RUNTIME=gunicorn`) y ahí el 60 sí sirve.
        "CONN_MAX_AGE": 0 if APP_RUNTIME == "daphne" else 60,
        "CONN_HEALTH_CHECKS": True,
        # La base que crea el runner de tests (TST-01) nace con el mismo juego de
        # caracteres que las conexiones de producción. Las tres imágenes de la
        # matriz hoy arrancan en utf8mb4, pero eso es configuración del servidor,
        # no contrato: declararlo evita que un servidor distinto (o un `my.cnf` de
        # ECOM) haga que un test de acentos mida el servidor y no el código.
        "TEST": {"CHARSET": "utf8mb4"},
    }
}

# El motor real gana sobre el SQLite de los tests, nunca al revés: con
# ``DJANGO_TEST_MOTOR`` puesto, ``PYTEST_RUNNING=1`` deja de mandar.
if PYTEST_RUNNING and not TEST_MOTOR:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}

REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
REDIS_PORT = os.environ.get("REDIS_PORT", "6379")
REDIS_SSL = os.environ.get("REDIS_SSL", "False") == "True"
REDIS_DB = os.environ.get("REDIS_DB", "1")
REDIS_URL = os.environ.get(
    "REDIS_URL",
    f"{'rediss' if REDIS_SSL else 'redis'}://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}",
)

# PERF-10 / G1c-12. Las sesiones y la caché comparten hoy la misma base de Redis, así
# que un `cache.clear()` —que en django_redis es un FLUSHDB— desloguea a todo el mundo,
# y las dos poblaciones compiten por los mismos 350 MB con `allkeys-lru`.
#
# `REDIS_SESSIONS_DB` separa **solo la base**: con la variable sin definir el alias
# `sessions` apunta exactamente a `REDIS_URL`, que es lo que hace hoy. Queda preparado
# y apagado porque el Redis de ECOM no es nuestro (H-06): el cambio de verdad lo tiene
# que acompañar su configuración, y mover la base con sesiones vivas las deja atrás
# (quien esté logueado vuelve al login una vez).
#
# Lo que esto **no** arregla: `maxmemory` es del servidor, no de la base, así que una
# caché que llena los 350 MB sigue pudiendo desalojar sesiones. Para eso hace falta la
# política o la instancia aparte que se le pide a ECOM.
REDIS_SESSIONS_DB = os.environ.get("REDIS_SESSIONS_DB", "")


def _url_en_otra_base(url, db):
    """La misma URL de Redis apuntando a otra base. Conserva esquema, credenciales,
    host, puerto y querystring: lo único que se reemplaza es el path."""
    if not db:
        return url
    partes = urlsplit(url)
    return urlunsplit((partes.scheme, partes.netloc, f"/{db}", partes.query, partes.fragment))


REDIS_SESSIONS_URL = _url_en_otra_base(REDIS_URL, REDIS_SESSIONS_DB)

# OPS-12: QA (el testing de ECOM) también usa Redis. Antes el único ambiente servido
# con Redis era `prd`, así que QA corría con un cache y un channel layer **locales al
# proceso**: el throttle contaba por worker, una invalidación limpiaba uno de varios y
# los websockets no cruzaban entre pods. Y como `settings_production` reasignaba
# `ENVIRONMENT = "prd"` después de este bloque, `settings.ENVIRONMENT` decía «prd»
# mientras el cache era LocMem: QA no reproducía lo que iba a pasar en producción.
# `USE_REDIS_CACHE=True` es la escotilla para reproducirlo en un dev.
USE_REDIS = ENVIRONMENT in ("prd", "qa") or PERFORMANCE_CI or os.environ.get("USE_REDIS_CACHE") == "True"

if USE_REDIS:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
                "SOCKET_CONNECT_TIMEOUT": 5,
                "SOCKET_TIMEOUT": 5,
            },
            "TIMEOUT": 600,
        },
        "sessions": {
            "BACKEND": "django_redis.cache.RedisCache",
            # Igual a `REDIS_URL` salvo que se defina `REDIS_SESSIONS_DB` (PERF-10).
            "LOCATION": REDIS_SESSIONS_URL,
            # Mismos límites que `default` (Cambio 91): sin ellos, un Redis que
            # no responde deja colgado cada request que lee su sesión —el portal
            # público la lee y la escribe en cada paso— y cada hilo colgado
            # retiene su conexión MySQL. Con límite falla rápido y se ve.
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
                "SOCKET_CONNECT_TIMEOUT": 5,
                "SOCKET_TIMEOUT": 5,
            },
            "TIMEOUT": 86400,
        },
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "sistemso-dev-cache",
        },
        "sessions": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "sistemso-dev-sessions",
        },
    }

if PERFORMANCE_QUERY_MONITORING_ENABLED:
    # La agregación debe ser compartida entre workers también en QA, donde el
    # cache default sigue siendo local por compatibilidad con el entorno.
    CACHES["performance"] = {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SOCKET_CONNECT_TIMEOUT": PERFORMANCE_REDIS_TIMEOUT_SECONDS,
            "SOCKET_TIMEOUT": PERFORMANCE_REDIS_TIMEOUT_SECONDS,
        },
        "TIMEOUT": PERFORMANCE_METRICS_RETENTION_SECONDS,
    }

SESSION_ENGINE = (
    "django.contrib.sessions.backends.cache" if ENVIRONMENT == "prd" else "django.contrib.sessions.backends.db"
)
SESSION_CACHE_ALIAS = "sessions"
SESSION_COOKIE_AGE = 86400

# Cierre de sesión automático por inactividad.
# Minutos sin actividad del usuario (mouse/teclado/scroll/touch) tras los cuales
# se cierra la sesión. Configurable por entorno para ajustar a 10, 15, 20, etc.
# 0 desactiva la funcionalidad.
# SEC-35: el mismo número lo aplica el servidor en
# `core.middleware.ExpiracionPorInactividadMiddleware`, contando pedidos HTTP. El
# JS sigue estando para el aviso con cuenta regresiva y para el latido que avisa
# que alguien está tipeando un formulario largo sin pedir pantallas.
SESSION_IDLE_TIMEOUT_MINUTES = int(os.environ.get("SESSION_IDLE_TIMEOUT_MINUTES", "15"))
# Segundos de aviso previo (modal con cuenta regresiva) antes de cerrar la
# sesión. 0 = cerrar sin aviso.
SESSION_IDLE_WARNING_SECONDS = int(os.environ.get("SESSION_IDLE_WARNING_SECONDS", "60"))

# El channel layer compartido hace falta donde hay más de un proceso atendiendo
# websockets, que son los ambientes servidos. El CI de performance y la escotilla
# `USE_REDIS_CACHE` encienden el cache, no los websockets: ahí no hay WS que cruzar.
if ENVIRONMENT in ("prd", "qa"):
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [REDIS_URL]},
        },
    }
else:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        },
    }

# OPS-13: acá estaba `HEALTH_CHECK = {"DISK_USAGE_MAX": 90, "MEMORY_MIN": 100}`, la
# configuración de `django-health-check`. El paquete se fue del repo en este mismo
# Cambio (196) y nadie más lee esa clave: las sondas son la app `healthcheck`.

DEFAULT_CACHE_TIMEOUT = 600
DASHBOARD_CACHE_TIMEOUT = 600
CIUDADANO_CACHE_TIMEOUT = 600
SLOW_REQUEST_MS = int(os.environ.get("SLOW_REQUEST_MS", "3000"))

REST_FRAMEWORK = {
    # Solo sesión: HTTP Basic (default de DRF) salteaba las tres barreras que el
    # login web sí respeta —la separación portal/backoffice, la sesión única de
    # backoffice y el cambio de clave provisoria—, porque los middlewares eximen
    # `/api/` a propósito (SEC-01, auditoría oct-2026). La app de campo de Becas
    # no se ve afectada: declara `TokenAuthentication` en sus propias vistas
    # (`programas/api/views.py`) y su login hereda `permission_classes = ()`.
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    # Default de DRF era `AllowAny`: una vista nueva nacía pública salvo que se
    # acordara de declarar permisos. Se invierte el default.
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 10,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_RATES": {
        # SEC-25 · `POST /api/becas/personas/consultar/` (y su alias
        # `renaper/consultar/`) devuelve nombre, apellido y nacimiento de
        # cualquier DNI + sexo: sin tope, un token de campo enumera la Gran Base.
        # Por **usuario**, no por IP: los territoriales salen por el NAT de la
        # operadora móvil y una cubeta por IP le cierra la consulta a una región
        # entera. 120/h es el default de D-25 —una jornada de campo son decenas
        # de personas, no cientos— y se mide con el uso real antes de apretarlo.
        #
        # Reemplaza a `"renaper": "30/min"`, que quedó sin consumidor al borrar
        # `RenaperRateThrottle` con SEC-04 (#509) y estaba reservada para este
        # throttle (R0-05).
        "personas_campo": "120/hour",
    },
}

DOMINIO = os.environ.get("DOMINIO", "localhost:8000")
RENAPER_API_USERNAME = os.getenv("RENAPER_API_USERNAME")
RENAPER_API_PASSWORD = os.getenv("RENAPER_API_PASSWORD")
RENAPER_API_URL = os.getenv("RENAPER_API_URL", "").strip().strip('"').strip("'")
RENAPER_LOGIN_URL = os.getenv("RENAPER_LOGIN_URL", "").strip().strip('"').strip("'")
RENAPER_CONSULTA_URL = os.getenv("RENAPER_CONSULTA_URL", "").strip().strip('"').strip("'")
RENAPER_API_KEY = os.getenv("RENAPER_API_KEY", "").strip().strip('"').strip("'")
RENAPER_API_KEY_HEADER = os.getenv("RENAPER_API_KEY_HEADER", "X-API-Key")
RENAPER_API_KEY_PREFIX = os.getenv("RENAPER_API_KEY_PREFIX", "").strip()
RENAPER_AUTH_MODE = os.getenv("RENAPER_AUTH_MODE", "auto").strip().lower()  # auto|api_key|credentials
RENAPER_HTTP_METHOD = os.getenv("RENAPER_HTTP_METHOD", "auto").strip().lower()  # auto|get|post
RENAPER_TEST_MODE = os.getenv("RENAPER_TEST_MODE", "False") == "True"
RENAPER_TEST_LATENCY_SECONDS = max(0, float(os.getenv("RENAPER_TEST_LATENCY_SECONDS", "0")))
# SIIS-09: consulta, o sea (5, 10) (D-S09). Entra en el presupuesto de red por
# request que verifica ``core.checks.presupuesto_de_llamadas_externas``.
RENAPER_CONNECT_TIMEOUT = int(os.getenv("RENAPER_CONNECT_TIMEOUT", "5"))
RENAPER_TIMEOUT = int(os.getenv("RENAPER_TIMEOUT", "10"))
RENAPER_RETRIES = int(os.getenv("RENAPER_RETRIES", "0"))
# SEC-27 · Verificación del certificado de RENAPER. El cliente va con
# `verify=False` desde siempre: cualquiera en el camino de red puede presentar su
# propio certificado, leer el documento que se consulta y devolver la identidad
# que quiera —y lo que vuelve de ahí es lo que marca a un ciudadano como
# «validado»—.
#
# **D-27 (default aplicado): queda preparado y apagado.** Encenderlo depende de
# que ECOM confirme la cadena de certificados del organismo (H-08 / pasos para el
# PM): si RENAPER usa una CA privada y no está en el almacén del contenedor, con
# `verify` activo **se corta la consulta en el acto**, y con ella el alta de
# ciudadanos. Por eso el default es el comportamiento de hoy y el cambio es una
# variable de entorno, ambiente por ambiente, con `manage.py diagnosticar_integraciones`
# como prueba antes de tocar producción.
#
# `RENAPER_CA_BUNDLE` (ruta a un .pem) implica verificar: es la forma de hacerlo
# con una CA privada sin meterla en el almacén del sistema.
RENAPER_CA_BUNDLE = os.getenv("RENAPER_CA_BUNDLE", "").strip()
RENAPER_VERIFY_TLS = os.getenv("RENAPER_VERIFY_TLS", "False") == "True"
# ─── Seguridad de la superficie pública ───────────────────────────────────────
# Redes desde las que se aceptan las cabeceras de proxy (X-Real-IP / X-Forwarded-For)
# al resolver la IP del cliente para el rate limit. Fuera de estas redes manda
# REMOTE_ADDR: sin esto, cualquiera anulaba el límite mandando una cabecera falsa.
TRUSTED_PROXY_NETS = [
    red.strip()
    for red in os.environ.get(
        "TRUSTED_PROXY_NETS", "10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,127.0.0.0/8,::1/128,fc00::/7"
    ).split(",")
    if red.strip()
]

# SEC-26 · techo por IP de los intentos de autenticación FALLIDOS, compartido por
# el login web y `/api/becas/auth/token/`. Holgado a propósito: tiene que aguantar
# una repartición detrás de una IP y a los territoriales detrás del NAT del
# operador móvil, y a la vez cortar un barrido de miles de usuarios distintos. Es
# la única cubeta que frena antes de verificar la clave, y puede serlo porque la
# paga la IP que ataca y no la cuenta atacada.
AUTH_FALLIDOS_MAX_POR_IP = int(os.getenv("AUTH_FALLIDOS_MAX_POR_IP", "300"))
AUTH_FALLIDOS_VENTANA_SEGUNDOS = int(os.getenv("AUTH_FALLIDOS_VENTANA_SEGUNDOS", "600"))

# Techos de carga. **Ojo con lo que cada uno limita de verdad** (SIIS-16: el
# comentario anterior prometía un tope del request que estos valores no dan):
#
# * ``DATA_UPLOAD_MAX_MEMORY_SIZE`` es el tope del cuerpo **sin contar los
#   archivos**: Django lo evalúa sobre lo que no son uploads. No frena un POST
#   multipart de 100 MB de adjuntos.
# * ``FILE_UPLOAD_MAX_MEMORY_SIZE`` no es un tope: es el umbral a partir del cual
#   el archivo se vuelca a disco en vez de quedar en memoria.
# * ``DATA_UPLOAD_MAX_NUMBER_FILES`` sí acota el request anónimo, por cantidad.
#
# El tamaño de cada adjunto lo valida el formulario (``portal.forms.inscripcion``,
# 5 MB y firma por magic bytes). El techo del **request** solo lo puede poner el
# proxy: ``client_max_body_size`` en la location del link público (ver
# ``nginx.conf`` y el ingress de ECOM).
DATA_UPLOAD_MAX_MEMORY_SIZE = int(os.environ.get("DATA_UPLOAD_MAX_MEMORY_SIZE", 5 * 1024 * 1024))
FILE_UPLOAD_MAX_MEMORY_SIZE = int(os.environ.get("FILE_UPLOAD_MAX_MEMORY_SIZE", 2 * 1024 * 1024))
DATA_UPLOAD_MAX_NUMBER_FIELDS = int(os.environ.get("DATA_UPLOAD_MAX_NUMBER_FIELDS", 500))
DATA_UPLOAD_MAX_NUMBER_FILES = int(os.environ.get("DATA_UPLOAD_MAX_NUMBER_FILES", 20))

# reCAPTCHA v2 (casilla "No soy un robot") del formulario público. Sin claves
# configuradas el paso 1 cae al desafío aritmético propio, así que un entorno sin
# credenciales sigue funcionando.
# CSP en modo solo-reporte para una puesta en marcha gradual (no bloquea, avisa).
CSP_REPORT_ONLY = os.environ.get("CSP_REPORT_ONLY", "False") == "True"

RECAPTCHA_SITE_KEY = os.environ.get("RECAPTCHA_SITE_KEY", "").strip()
RECAPTCHA_SECRET_KEY = os.environ.get("RECAPTCHA_SECRET_KEY", "").strip()
RECAPTCHA_VERIFY_URL = os.environ.get("RECAPTCHA_VERIFY_URL", "https://www.google.com/recaptcha/api/siteverify")
# SIIS-09: el paso 1 del link público verifica el token contra Google **antes**
# de consultar identidad, así que entra en el presupuesto de red del request. Es
# un par (conectar, leer) y no un escalar: con un escalar ``requests`` lo aplica
# a las dos fases y el peor caso es el doble del número que dice la variable.
RECAPTCHA_CONNECT_TIMEOUT = int(os.environ.get("RECAPTCHA_CONNECT_TIMEOUT", "5"))
RECAPTCHA_TIMEOUT = int(os.environ.get("RECAPTCHA_TIMEOUT", "10"))

# Google Tag Manager en las pantallas públicas de inscripción (Cambio 68). Sin
# contenedor no se renderiza nada ni se abre la CSP a Google: así test, dev e
# icore-srv no ensucian las métricas de producción.
GTM_CONTAINER_ID = os.environ.get("GTM_CONTAINER_ID", "").strip()
# Hosts extra para la CSP, para las etiquetas que se sumen en GTM además de GA4
# (Meta, Google Ads…): "connect-src=https://a.com https://b.com;img-src=https://c.com".
from config.middlewares.security_headers import parsear_fuentes_extra  # noqa: E402

CSP_EXTRA_SOURCES = parsear_fuentes_extra(os.environ.get("CSP_EXTRA_SOURCES", ""))

PERSONAS_API_URL = os.getenv("PERSONAS_API_URL", "https://personas.ecomdev.ar/api/v1").strip().rstrip("/")
PERSONAS_API_CLIENT_ID = os.getenv("PERSONAS_API_CLIENT_ID", "")
PERSONAS_API_CLIENT_SECRET = os.getenv("PERSONAS_API_CLIENT_SECRET", "")
PERSONAS_API_ENTIDAD_UUID = os.getenv("PERSONAS_API_ENTIDAD_UUID", "")
PERSONAS_API_FUENTE_ID = int(os.getenv("PERSONAS_API_FUENTE_ID", "13"))
# SIIS-09: consulta, o sea (5, 10) (D-S09). Con la Gran Base caída, cada paso 1
# del link público retenía un hilo hasta 30 s; además del timeout más corto, el
# cortacircuito de ``core.integraciones`` deja de consultarla tras tres fallas.
PERSONAS_API_CONNECT_TIMEOUT = int(os.getenv("PERSONAS_API_CONNECT_TIMEOUT", "5"))
PERSONAS_API_TIMEOUT = int(os.getenv("PERSONAS_API_TIMEOUT", "10"))
# Cambio 57: en False no se consulta Base de Personas en ningún lugar (link,
# app de campo, «Revalidar», diagnóstico). La identidad se resuelve con el
# padrón de la convocatoria. No cambia el resultado de quien está en el padrón:
# le saca la espera del timeout a una API que no responde.
PERSONAS_API_ACTIVA = os.getenv("PERSONAS_API_ACTIVA", "True").strip().lower() in ("true", "1", "si", "sí", "yes")
# Sin default a propósito (RED-61): el que había apuntaba al SIIS de desarrollo,
# que responde 200. Si en producción la variable falta o cambia de nombre, el
# alta se da por informada y el organismo nunca la recibe, en una integración sin
# baja. Lo valida ``core.checks.entorno_de_integraciones`` (``check --deploy``).
SIIS_API_URL = os.getenv("SIIS_API_URL", "").strip().rstrip("/")
SIIS_API_CLIENT_ID = os.getenv("SIIS_API_CLIENT_ID", "")
SIIS_API_CLIENT_SECRET = os.getenv("SIIS_API_CLIENT_SECRET", "")
# SIIS-09 · Un timeout por tipo de llamada, no uno solo para todas. «Aprobar»
# encadena token → compatibilidad → alta → correo dentro del mismo clic: con
# (10, 30) para las tres llamadas a SIIS la cadena pasaba los 120 s y nginx la
# cortaba a los 60 (``nginx.conf:97``), dejando al operador con un 504 y el alta
# posiblemente hecha del otro lado. Los valores son el default de D-S09; que la
# suma entre en el presupuesto lo verifica
# ``core.checks.presupuesto_de_llamadas_externas`` (``check --deploy``).
SIIS_API_CONNECT_TIMEOUT = int(os.getenv("SIIS_API_CONNECT_TIMEOUT", "5"))
# El token es autenticación contra el mismo host: o contesta rápido o está roto.
SIIS_API_TIMEOUT_TOKEN = int(os.getenv("SIIS_API_TIMEOUT_TOKEN", "5"))
# Compatibilidad y catálogos: lecturas.
SIIS_API_TIMEOUT_CONSULTA = int(os.getenv("SIIS_API_TIMEOUT_CONSULTA", "10"))
# Solo el alta en la tabla intermedia, que del otro lado escribe. Más largo que
# una consulta y aun así corto: lo que no contesta queda INCIERTO y se concilia
# con ECOM (SIIS-02), que es mejor que un 504 sin registro.
SIIS_API_TIMEOUT = int(os.getenv("SIIS_API_TIMEOUT", "20"))
# Dónde están los .sql con los datos del organismo (RENAPER, aprobados, localidades)
# que carga `manage.py correr_alta_siis`. Antes se leían de `scripts/` dentro de la
# imagen, con los datos personales de 10.321 personas adentro (RED-01). Ahora es un
# directorio montado como volumen o secret, que no viaja con el código ni con la
# imagen. Si no está montado, los comandos cortan nombrando la variable.
DATOS_SIIS_DIR = os.getenv("DATOS_SIIS_DIR", "/datos-siis")
# OPS-13: y acá `OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")`, sin un solo consumidor en
# el código. `openai` salió de `requirements.txt` en este Cambio; leer el secreto para no
# usarlo solo servía para que apareciera en los `.env` de los ambientes.

LOG_DIR = BASE_DIR / "logs"
# OPS-03: stdout es el destino de verdad —es lo que recogen `docker compose logs` y
# `kubectl logs`—. Los archivos de `logs/` son un extra de icore, donde el directorio
# está montado desde el host: se encienden con LOG_TO_FILES=True (docker-compose.prod.yml)
# y se purgan solos pasados LOG_RETENTION_DAYS días. Apagados, no se crea ni el
# directorio, que en un filesystem de solo lectura era un arranque fallido.
LOG_TO_FILES = os.environ.get("LOG_TO_FILES", "False") == "True"
LOG_RETENTION_DAYS = int(os.environ.get("LOG_RETENTION_DAYS", "14"))
if LOG_TO_FILES:
    os.makedirs(LOG_DIR, exist_ok=True)
    purgar_logs_viejos(LOG_DIR, LOG_RETENTION_DAYS)

LOGGING = construir_logging(log_dir=LOG_DIR, debug=DEBUG, log_to_files=LOG_TO_FILES)

# Argon2 primero: verificar una contraseña con el PBKDF2 por defecto de Django 5.2
# (1.000.000 de iteraciones) cuesta ~1 s de CPU por login, con el GIL tomado;
# Argon2id ronda los 90 ms con seguridad equivalente. PBKDF2 se conserva para
# leer los hashes ya guardados: Django los re-hashea a Argon2 en el siguiente
# login exitoso, sin migración ni reseteo de claves.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

if DEBUG:
    INTERNAL_IPS = ["127.0.0.1", "::1"]

USE_GZIP = True
GZIP_CONTENT_TYPES = (
    "text/css",
    "text/javascript",
    "application/javascript",
    "application/x-javascript",
    "text/xml",
    "text/plain",
    "text/html",
    "application/json",
)

SILKY_PYTHON_PROFILER = True
SILKY_PYTHON_PROFILER_BINARY = True
SILKY_AUTHENTICATION = True
SILKY_AUTHORISATION = True
SILKY_MAX_REQUEST_BODY_SIZE = 1024
SILKY_MAX_RESPONSE_BODY_SIZE = 1024
SILKY_INTERCEPT_PERCENT = 100 if DEBUG else 10

USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# SEC-35 · Las cookies de sesión y de CSRF dejan de depender de `ENVIRONMENT`.
# Atarlas a `prd` las dejaba viajando en claro en cualquier ambiente servido que
# no declarara la variable —y `ENVIRONMENT` es una declaración, no un hecho: icore
# vale `prd` siendo DEV y QA lo pisa a `prd` (OPS-12)—. Lo que sí es un hecho es
# `DEBUG`: con `DEBUG=False` hay alguien sirviendo tráfico detrás de TLS, y ahí la
# cookie va con `Secure`. Un desarrollo local sobre `http://localhost` corre con
# `DJANGO_DEBUG=True` y no cambia.
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

if ENVIRONMENT == "prd":
    SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = os.environ.get("SECURE_HSTS_INCLUDE_SUBDOMAINS", "True") == "True"
    SECURE_HSTS_PRELOAD = os.environ.get("SECURE_HSTS_PRELOAD", "True") == "True"
    SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "True") == "True"
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
else:
    SECURE_HSTS_SECONDS = 0
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False
    SECURE_SSL_REDIRECT = False

SPECTACULAR_SETTINGS = {
    "TITLE": "Sistema API",
    "DESCRIPTION": "Documentación de APIs del Sistema",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": "/api/",
    # Sin esto, `/api/docs/` y `/api/redoc/` cargan Swagger-UI y Redoc desde
    # `cdn.jsdelivr.net/...@latest`: código de terceros, sin versión fija, que
    # se ejecuta con la sesión de un usuario de backoffice. `SIDECAR` los sirve
    # desde `/static/`, con la versión pineada en `requirements.txt`.
    "SWAGGER_UI_DIST": "SIDECAR",
    "SWAGGER_UI_FAVICON_HREF": "SIDECAR",
    "REDOC_DIST": "SIDECAR",
    # SEC-01 · Las tres pantallas de documentación van envueltas en
    # `login_required` (`config/urls.py`), pero por dentro declaran `AllowAny`, que
    # es el default de Spectacular: la sesión de un ciudadano del portal —si
    # alguna vez esquivara `PortalCiudadanoMiddleware`— tenía ahí el inventario
    # completo de endpoints, parámetros y modelos. **Qué NO cambia:** la decisión
    # del 26/08/2026 fue dejarlas detrás de login y no detrás de una capacidad, así
    # que un usuario de backoffice sin rol las sigue viendo.
    "SERVE_PERMISSIONS": ["core.api_permissions.BackofficeAutenticado"],
    # `drf_spectacular/checks.py` registra un check `deploy=True` que vuelca cada
    # warning y cada error del esquema como un issue más de `manage.py check
    # --deploy`: 25 líneas nuevas en el log del CI, sin umbral y sin forma de
    # bajarlas una por una. El mismo dato, con allowlist y ratchet, lo da
    # `core.tests.test_api_schema_contrato.EsquemaOpenApiTests`, que sí falla si
    # aparece uno nuevo. Acá solo sería ruido (RED-36, revisión del PR R-04).
    "ENABLE_DJANGO_DEPLOY_CHECK": False,
}
