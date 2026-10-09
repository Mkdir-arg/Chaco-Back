"""Rutas de WebSocket de `legajos` (montadas en `config/asgi.py`).

Único canal del proyecto desde el apagado de `conversaciones` (G1-01 fase 2):
`ws/conversaciones/…` y `ws/alertas-conversaciones/` se desmontaron con el resto
de la app, y `ws/alertas/` se mudó acá junto con su consumer (RED-13).
"""

from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(r"ws/alertas/$", consumers.AlertasConsumer.as_asgi()),
]
