import os

from core.logging_config import construir_logging

from .settings import *
from .settings import LOG_DIR, LOG_TO_FILES

# OPS-12: acá había `ENVIRONMENT = "prd"`. Reasignarlo no cambiaba nada de lo que
# `settings.py` ya había derivado de la variable real —cache, channel layer, motor de
# sesiones, prefijo del asunto de los correos—, pero sí lo que el código lee en runtime:
# en QA (testing de ECOM, `ENVIRONMENT=qa` + este módulo) `settings.ENVIRONMENT` decía
# «prd» mientras el cache era LocMem, y `diagnosticar_siis` / `diagnosticar_correo`
# informaban sobre un ambiente que no era el que estaba corriendo. Este módulo es el
# endurecido —HSTS, cookies seguras, redirección a HTTPS—; cuál es el ambiente lo dice
# la variable `ENVIRONMENT`, y el system check `core.W002` avisa si no la declararon.
DEBUG = False

# Cambio 446: el `LOGGING` se armó en `settings.py` con el `DEBUG` de la variable, antes de
# la línea de arriba. Con `DJANGO_DEBUG=True` mal puesto (testing de ECOM, 09-nov-2026) el
# root y `django.template` quedaban en DEBUG y cada `VariableDoesNotExist` se registraba con
# su traceback: el detalle de un dispositivo pasaba de 0,27 s a 3,7 s. Se rearma acá.
LOGGING = construir_logging(log_dir=LOG_DIR, debug=False, log_to_files=LOG_TO_FILES)

# Silk (profiling) nunca en producción, sin depender del orden de carga de .env.
INSTALLED_APPS = [app for app in INSTALLED_APPS if app != "silk"]
# Y la bandera que deriva de esa lista se recalcula: `config/settings.py` la fijó antes
# de este filtro, así que con `DJANGO_DEBUG=True` mal puesto en un ambiente servido
# quedaba en `True` con la app ya afuera, y `config/urls.py` montaba `/silk/` apuntando a
# `silk.urls` sin la app instalada.
SILK_HABILITADO = False

# Refuerza hosts solo desde variable de entorno en producción.
hosts_env = os.getenv("DJANGO_ALLOWED_HOSTS", "")
ALLOWED_HOSTS = [h.strip() for h in hosts_env.split(",") if h.strip()]
if not ALLOWED_HOSTS:
    raise ValueError("DJANGO_ALLOWED_HOSTS debe configurarse en producción")

# Refuerzos de seguridad en producción: seguros por defecto, override por env var.
SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "True") == "True"
SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "True") == "True"
CSRF_COOKIE_SECURE = os.environ.get("CSRF_COOKIE_SECURE", "True") == "True"
SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = os.environ.get("SECURE_HSTS_INCLUDE_SUBDOMAINS", "True") == "True"
SECURE_HSTS_PRELOAD = os.environ.get("SECURE_HSTS_PRELOAD", "True") == "True"
