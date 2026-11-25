"""Serializers del egreso y el cambio de plaza de la app (Cambio 597).

Solo traducen la forma del cuerpo (ids, booleanos, fechas ISO): las reglas —motivo vigente, destino
obligatorio, fechas, plaza libre— son de ``programas.services.estadias``, las mismas que la web.
"""

from rest_framework import serializers


class MotivoEgresoSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nombre = serializers.CharField()


class EgresarEnvioSerializer(serializers.Serializer):
    """Cuerpo de ``POST /api/emergencia/estadias/{id}/egresar/``."""

    motivo_egreso_id = serializers.IntegerField(required=False, allow_null=True, default=None)
    destino = serializers.CharField(required=False, allow_blank=True, default="", max_length=200)
    pertenencias_devueltas = serializers.BooleanField(required=False, default=False)
    observaciones = serializers.CharField(required=False, allow_blank=True, default="")
    fecha_egreso = serializers.DateTimeField(required=False, allow_null=True, default=None)


class CambiarPlazaEnvioSerializer(serializers.Serializer):
    """Cuerpo de ``POST /api/emergencia/estadias/{id}/cambiar-plaza/``."""

    plaza_id = serializers.IntegerField(required=False, allow_null=True, default=None)
    motivo = serializers.CharField(required=False, allow_blank=True, default="")


class PlazaParaCambioSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    codigo = serializers.CharField()
    tipo = serializers.CharField()


class SectorParaCambioSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nombre = serializers.CharField()
    plazas = PlazaParaCambioSerializer(many=True)


class PlazasParaCambioSerializer(serializers.Serializer):
    sectores = SectorParaCambioSerializer(many=True)


class AccionDeEstadiaSerializer(serializers.Serializer):
    """Respuesta de egresar y cambiar plaza: ``mapa`` es el del edificio, o ``null`` si todavía no se arma."""

    ok = serializers.BooleanField()
    mapa = serializers.JSONField(allow_null=True)
