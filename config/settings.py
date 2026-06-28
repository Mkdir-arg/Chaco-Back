import os
import sys
import logging
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
    "django.middleware.gzip.GZipMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "core.middleware.PortalCiudadanoMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.RequestLoggingMiddleware",
]

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
                "legajos.context_processors.alertas_eventos_criticos",
                "conversaciones.context_processors.user_groups",
                "core.context_processors.sidebar_badges",
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

STATICFILES_STORAGE = (
    "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"
    if ENVIRONMENT == "prd"
    else "django.contrib.staticfiles.storage.StaticFilesStorage"
)

LOGIN_URL = "users:login"
LOGIN_REDIRECT_URL = "core:inicio"
LOGOUT_REDIRECT_URL = "users:login"
ACCOUNT_FORMS = {"login": "users.forms.UserLoginForm"}

EMAIL_BACKEND = (
    "django.core.mail.backends.smtp.EmailBackend"
    if ENVIRONMENT == "prd"
    else "django.core.mail.backends.console.EmailBackend"
)

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

if "pytest" in sys.argv or os.environ.get("PYTEST_RUNNING") == "1":
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}

REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
REDIS_PORT = os.environ.get("REDIS_PORT", "6379")
REDIS_SSL = os.environ.get("REDIS_SSL", "False") == "True"
REDIS_DB = os.environ.get("REDIS_DB", "1")
REDIS_URL = os.environ.get(
    "REDIS_URL",
    f"{'rediss' if REDIS_SSL else 'redis'}://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}",
)

if ENVIRONMENT == "prd":
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

SESSION_ENGINE = (
    "django.contrib.sessions.backends.cache"
    if ENVIRONMENT == "prd"
    else "django.contrib.sessions.backends.db"
)
SESSION_CACHE_ALIAS = "sessions"
SESSION_COOKIE_AGE = 86400

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

REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 10,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

DOMINIO = os.environ.get("DOMINIO", "localhost:8000")
RENAPER_API_USERNAME = os.getenv("RENAPER_API_USERNAME")
RENAPER_API_PASSWORD = os.getenv("RENAPER_API_PASSWORD")
RENAPER_API_URL = os.getenv("RENAPER_API_URL", "").strip().strip('"').strip("'")
RENAPER_API_KEY = os.getenv("RENAPER_API_KEY", "").strip().strip('"').strip("'")
RENAPER_API_KEY_HEADER = os.getenv("RENAPER_API_KEY_HEADER", "X-API-Key")
RENAPER_API_KEY_PREFIX = os.getenv("RENAPER_API_KEY_PREFIX", "").strip()
RENAPER_AUTH_MODE = os.getenv("RENAPER_AUTH_MODE", "auto").strip().lower()  # auto|api_key|credentials
RENAPER_HTTP_METHOD = os.getenv("RENAPER_HTTP_METHOD", "auto").strip().lower()  # auto|get|post
RENAPER_TEST_MODE = os.getenv("RENAPER_TEST_MODE", "False") == "True"
RENAPER_CONNECT_TIMEOUT = int(os.getenv("RENAPER_CONNECT_TIMEOUT", "10"))
RENAPER_TIMEOUT = int(os.getenv("RENAPER_TIMEOUT", "20"))
RENAPER_RETRIES = int(os.getenv("RENAPER_RETRIES", "0"))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", os.getenv("SUPABASE_KEY", ""))
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_TIMEOUT_SECONDS = int(os.getenv("SUPABASE_TIMEOUT_SECONDS", "12"))

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
        "info_file": {"level": "INFO", "filters": ["info_only"], "class": "core.utils.DailyFileHandler", "filename": str(LOG_DIR / "info.log"), "formatter": "verbose"},
        "error_file": {"level": "ERROR", "filters": ["error_only"], "class": "core.utils.DailyFileHandler", "filename": str(LOG_DIR / "error.log"), "formatter": "verbose"},
        "warning_file": {"level": "WARNING", "filters": ["warning_only"], "class": "core.utils.DailyFileHandler", "filename": str(LOG_DIR / "warning.log"), "formatter": "verbose"},
        "critical_file": {"level": "CRITICAL", "filters": ["critical_only"], "class": "core.utils.DailyFileHandler", "filename": str(LOG_DIR / "critical.log"), "formatter": "verbose"},
        "data_file": {"level": "INFO", "filters": ["data_only"], "class": "core.utils.DailyFileHandler", "filename": str(LOG_DIR / "data.log"), "formatter": "json_data"},
    },
    "root": {"handlers": ["console", "info_file", "error_file", "warning_file", "critical_file", "data_file"], "level": "DEBUG" if DEBUG else "INFO"},
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
