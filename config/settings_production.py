from .settings import *
import os

ENVIRONMENT = "prd"
DEBUG = False

# Silk (profiling) nunca en producción, sin depender del orden de carga de .env.
INSTALLED_APPS = [app for app in INSTALLED_APPS if app != "silk"]

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
