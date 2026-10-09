import os

import django
from django.core.asgi import get_asgi_application

# Configure Django FIRST
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

# Import after Django setup
from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator

from legajos.routing import websocket_urlpatterns

application = ProtocolTypeRouter(
    {
        "http": get_asgi_application(),
        # `AllowedHostsOriginValidator` chequea el `Origin` del handshake contra
        # `ALLOWED_HOSTS`. Sin él, el WebSocket no tiene nada parecido a la
        # protección CSRF del HTTP: cualquier página podía abrir `/ws/alertas/`
        # con la cookie de sesión del visitante (`SameSite=Lax` no frena un
        # handshake de WebSocket) y leer en vivo las alertas del backoffice.
        # Desde el apagado de `conversaciones` (G1-01 fase 2) el único canal es
        # `ws/alertas/`; el validador se queda igual, en la raíz del router.
        "websocket": AllowedHostsOriginValidator(AuthMiddlewareStack(URLRouter(websocket_urlpatterns))),
    }
)
