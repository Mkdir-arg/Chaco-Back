from django.urls import path

from programas.views import emergencia_config as config

app_name = "emergencia"

# Módulo Emergencia. Hoy solo la configuración (E7): el tablero, la bandeja de casos y las
# entregas de kits se suman en los PRs siguientes. El segmento es `config/` y no
# `configuracion/` a propósito: el sidebar enciende el grupo «Configuración» con cualquier
# ruta que contenga esa palabra.
urlpatterns = [
    path("config/", config.ConfiguracionEmergenciaView.as_view(), name="configuracion"),
]
