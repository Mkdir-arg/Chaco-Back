from django.urls import path

from .views import health_check, ready

app_name = "healthcheck"

urlpatterns = [
    # Liveness: sin I/O, para que una base lenta no mate los pods (OPS-04).
    path("health/", health_check, name="health_check"),
    # Readiness: toca la base y, en prd, el cache de sesiones. 503 si algo falla.
    # No se publica en nginx: cae en el `location /` general.
    path("health/ready/", ready, name="ready"),
]
