from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(r"ws/conversaciones/(?P<conversacion_id>\w+)/$", consumers.ConversacionConsumer.as_asgi()),
    re_path(r"ws/conversaciones/$", consumers.ConversacionesListConsumer.as_asgi()),
    re_path(r"ws/alertas/$", consumers.AlertasConsumer.as_asgi()),
    re_path(r"ws/alertas-conversaciones/$", consumers.AlertasConversacionesConsumer.as_asgi()),
]
