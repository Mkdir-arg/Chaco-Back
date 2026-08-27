import logging
import os
import sys
from pathlib import Path

from django.contrib.messages import constants as messages
from dotenv import load_dotenv

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

websockets_enabled_env = os.environ.get("WEBSOCKETS_ENABLED")
if websockets_enabled_env is None:
    WEBSOCKETS_ENABLED = os.environ.get("APP_RUNTIME", "runserver") == "daphne"
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
    "django_extensions",
    "rest_framework",
    "rest_framework.authtoken",
    "channels",
    "django_redis",
    "health_check",
    "health_check.db",
    "health_check.cache",
    "users",
    "core",
    "dashboard",
    "legajos",
    "configuracion",
    "conversaciones",
    "portal",
    "tramites",
    "programas",
    "healthcheck",
]

# Silk (profiling): solo en desarrollo, nunca en producción.
if DEBUG:
    INSTALLED_APPS += ["silk"]

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
                "conversaciones.context_processors.user_groups",
                "core.context_processors.sidebar_badges",
                "core.context_processors.session_idle_config",
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

# Servir /media/ desde la app (django.views.static.serve). Pensado para ambientes
# servidos sin nginx adelante (Kubernetes): alcanza para la escala de QA. Los
# archivos viven en MEDIA_ROOT, que ahí debe ser un volumen persistente.
SERVE_MEDIA = os.environ.get("SERVE_MEDIA", "False") == "True"

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
# request del alta de usuario hasta que corte el gateway.
EMAIL_TIMEOUT = int(os.getenv("EMAIL_TIMEOUT", "10"))
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

MESSAGE_TAGS = {
    messages.DEBUG: "bg-gray-800 text-white",
    messages.INFO: "bg-blue-500 text-white",
    messages.SUCCESS: "bg-green-500 text-white",
    messages.WARNING: "bg-yellow-500 text-white",
    messages.ERROR: "bg-red-500 text-white",
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
            "read_timeout": 10,
            "write_timeout": 10,
        },
        "CONN_MAX_AGE": 60,
        "CONN_HEALTH_CHECKS": True,
    }
}

if PYTEST_RUNNING:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}

REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
REDIS_PORT = os.environ.get("REDIS_PORT", "6379")
REDIS_SSL = os.environ.get("REDIS_SSL", "False") == "True"
REDIS_DB = os.environ.get("REDIS_DB", "1")
REDIS_URL = os.environ.get(
    "REDIS_URL",
    f"{'rediss' if REDIS_SSL else 'redis'}://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}",
)

if ENVIRONMENT == "prd" or PERFORMANCE_CI:
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
            "LOCATION": REDIS_URL,
            "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
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

# Cierre de sesión automático por inactividad (idle logout, lado cliente).
# Minutos sin actividad del usuario (mouse/teclado/scroll/touch) tras los cuales
# se cierra la sesión. Configurable por entorno para ajustar a 10, 15, 20, etc.
# 0 desactiva la funcionalidad.
SESSION_IDLE_TIMEOUT_MINUTES = int(os.environ.get("SESSION_IDLE_TIMEOUT_MINUTES", "15"))
# Segundos de aviso previo (modal con cuenta regresiva) antes de cerrar la
# sesión. 0 = cerrar sin aviso.
SESSION_IDLE_WARNING_SECONDS = int(os.environ.get("SESSION_IDLE_WARNING_SECONDS", "60"))

if ENVIRONMENT == "prd":
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

HEALTH_CHECK = {
    "DISK_USAGE_MAX": 90,
    "MEMORY_MIN": 100,
}

DEFAULT_CACHE_TIMEOUT = 600
DASHBOARD_CACHE_TIMEOUT = 600
CIUDADANO_CACHE_TIMEOUT = 600
SLOW_REQUEST_MS = int(os.environ.get("SLOW_REQUEST_MS", "3000"))

REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 10,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_RATES": {
        # Endpoints que llaman a RENAPER (servicio externo lento): límite por
        # cliente para no agotar el pool de workers ni abusar del upstream.
        "renaper": "30/min",
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
RENAPER_CONNECT_TIMEOUT = int(os.getenv("RENAPER_CONNECT_TIMEOUT", "10"))
RENAPER_TIMEOUT = int(os.getenv("RENAPER_TIMEOUT", "20"))
RENAPER_RETRIES = int(os.getenv("RENAPER_RETRIES", "0"))
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

# Techos de carga. Django no limita por sí mismo el tamaño de los archivos, y el
# formulario público acepta adjuntos sin autenticación: sin estos valores un solo
# request podía escribir cientos de MB a disco antes de que el form los validara.
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
RECAPTCHA_TIMEOUT = int(os.environ.get("RECAPTCHA_TIMEOUT", "10"))

PERSONAS_API_URL = os.getenv("PERSONAS_API_URL", "https://personas.ecomdev.ar/api/v1").strip().rstrip("/")
PERSONAS_API_CLIENT_ID = os.getenv("PERSONAS_API_CLIENT_ID", "")
PERSONAS_API_CLIENT_SECRET = os.getenv("PERSONAS_API_CLIENT_SECRET", "")
PERSONAS_API_ENTIDAD_UUID = os.getenv("PERSONAS_API_ENTIDAD_UUID", "")
PERSONAS_API_FUENTE_ID = int(os.getenv("PERSONAS_API_FUENTE_ID", "13"))
PERSONAS_API_CONNECT_TIMEOUT = int(os.getenv("PERSONAS_API_CONNECT_TIMEOUT", "10"))
PERSONAS_API_TIMEOUT = int(os.getenv("PERSONAS_API_TIMEOUT", "20"))
SIIS_API_URL = os.getenv("SIIS_API_URL", "https://siisapi.ecomdev.ar").strip().rstrip("/")
SIIS_API_CLIENT_ID = os.getenv("SIIS_API_CLIENT_ID", "")
SIIS_API_CLIENT_SECRET = os.getenv("SIIS_API_CLIENT_SECRET", "")
SIIS_API_CONNECT_TIMEOUT = int(os.getenv("SIIS_API_CONNECT_TIMEOUT", "10"))
SIIS_API_TIMEOUT = int(os.getenv("SIIS_API_TIMEOUT", "30"))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

LOG_DIR = BASE_DIR / "logs"
os.makedirs(LOG_DIR, exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "info_only": {"()": "django.utils.log.CallbackFilter", "callback": lambda r: r.levelno == logging.INFO},
        "error_only": {"()": "django.utils.log.CallbackFilter", "callback": lambda r: r.levelno == logging.ERROR},
        "warning_only": {"()": "django.utils.log.CallbackFilter", "callback": lambda r: r.levelno == logging.WARNING},
        "critical_only": {"()": "django.utils.log.CallbackFilter", "callback": lambda r: r.levelno == logging.CRITICAL},
        "data_only": {"()": "django.utils.log.CallbackFilter", "callback": lambda r: hasattr(r, "data")},
    },
    "formatters": {
        "verbose": {"format": "[{asctime}] {module} {levelname} {name}: {message}", "style": "{"},
        "simple": {"format": "[{asctime}] {levelname} {message}", "style": "{"},
        "json_data": {"()": "core.utils.JSONDataFormatter"},
    },
    "handlers": {
        "console": {
            "level": "DEBUG" if DEBUG else "INFO",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "info_file": {
            "level": "INFO",
            "filters": ["info_only"],
            "class": "core.utils.DailyFileHandler",
            "filename": str(LOG_DIR / "info.log"),
            "formatter": "verbose",
        },
        "error_file": {
            "level": "ERROR",
            "filters": ["error_only"],
            "class": "core.utils.DailyFileHandler",
            "filename": str(LOG_DIR / "error.log"),
            "formatter": "verbose",
        },
        "warning_file": {
            "level": "WARNING",
            "filters": ["warning_only"],
            "class": "core.utils.DailyFileHandler",
            "filename": str(LOG_DIR / "warning.log"),
            "formatter": "verbose",
        },
        "critical_file": {
            "level": "CRITICAL",
            "filters": ["critical_only"],
            "class": "core.utils.DailyFileHandler",
            "filename": str(LOG_DIR / "critical.log"),
            "formatter": "verbose",
        },
        "data_file": {
            "level": "INFO",
            "filters": ["data_only"],
            "class": "core.utils.DailyFileHandler",
            "filename": str(LOG_DIR / "data.log"),
            "formatter": "json_data",
        },
    },
    "root": {
        "handlers": ["console", "info_file", "error_file", "warning_file", "critical_file", "data_file"],
        "level": "DEBUG" if DEBUG else "INFO",
    },
    "loggers": {
        "django": {"handlers": [], "level": "DEBUG" if DEBUG else "INFO", "propagate": True},
        "django.request": {"handlers": ["error_file", "warning_file"], "level": "WARNING", "propagate": False},
        "core.requests": {"handlers": [], "level": "INFO", "propagate": True},
    },
}

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

if ENVIRONMENT == "prd":
    SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = os.environ.get("SECURE_HSTS_INCLUDE_SUBDOMAINS", "True") == "True"
    SECURE_HSTS_PRELOAD = os.environ.get("SECURE_HSTS_PRELOAD", "True") == "True"
    SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "True") == "True"
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
else:
    SECURE_HSTS_SECONDS = 0
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False

SPECTACULAR_SETTINGS = {
    "TITLE": "Sistema API",
    "DESCRIPTION": "Documentación de APIs del Sistema",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": "/api/",
}
