from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404

from conversaciones.models import Conversacion


def get_ciudadano_perfil(user):
    return user.ciudadano_perfil


def get_ciudadano_conversaciones(user, ciudadano):
    return Conversacion.objects.filter(Q(dni_ciudadano=ciudadano.dni) | Q(ciudadano_usuario=user)).order_by(
        "-fecha_inicio"
    )


def get_ciudadano_conversacion_or_404(user, ciudadano, pk):
    conversacion = get_object_or_404(
        Conversacion.objects.prefetch_related("mensajes"),
        pk=pk,
    )
    if conversacion.dni_ciudadano != ciudadano.dni and conversacion.ciudadano_usuario != user:
        raise Http404
    return conversacion
