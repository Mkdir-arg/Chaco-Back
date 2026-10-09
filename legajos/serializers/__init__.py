from django.contrib.auth.models import User
from rest_framework import serializers

from core import rbac

from ..models import (
    AlertaCiudadano,
    Ciudadano,
)

# Datos de contacto del ciudadano: solo para quien tenga ``ciudadano.sensible``
# (SEC-02, auditoría oct-2026).
CAMPOS_SENSIBLES = ("telefono", "email", "domicilio")


class CiudadanoSerializer(serializers.ModelSerializer):
    """Serializer para el modelo Ciudadano"""

    legajos_count = serializers.SerializerMethodField()

    class Meta:
        model = Ciudadano
        fields = [
            "id",
            "dni",
            "nombre",
            "apellido",
            "fecha_nacimiento",
            "genero",
            "telefono",
            "email",
            "domicilio",
            "activo",
            "legajos_count",
            "creado",
            "modificado",
        ]
        read_only_fields = ["id", "creado", "modificado"]

    # RED-37: es un conteo; el esquema lo publicaba como `string`.
    def get_legajos_count(self, obj) -> int:
        return getattr(obj, "legajos_count", obj.inscripciones_programas.count())

    def to_representation(self, instance):
        """Oculta los datos de contacto salvo que el usuario tenga ``ciudadano.sensible``.

        Sin request en el contexto (uso programático) se oculta igual: el default
        es el más restrictivo.
        """
        datos = super().to_representation(instance)
        request = self.context.get("request")
        usuario = getattr(request, "user", None)
        if not rbac.puede(usuario, "ciudadano.sensible"):
            for campo in CAMPOS_SENSIBLES:
                datos.pop(campo, None)
        return datos


class UserSerializer(serializers.ModelSerializer):
    """Serializer básico para User"""

    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name", "email"]


class AlertaCiudadanoSerializer(serializers.ModelSerializer):
    """Serializer para AlertaCiudadano"""

    ciudadano_nombre = serializers.CharField(source="ciudadano.nombre_completo", read_only=True)
    legajo_codigo = serializers.CharField(source="legajo.codigo", read_only=True)
    dispositivo_nombre = serializers.SerializerMethodField()
    cerrada_por_nombre = serializers.CharField(source="cerrada_por.get_full_name", read_only=True)

    # RED-37: sin la anotación el esquema publicaba este campo como `string`,
    # cuando puede venir nulo.
    def get_dispositivo_nombre(self, obj) -> str | None:
        if not obj.legajo or not obj.legajo.dispositivo:
            return None
        return obj.legajo.dispositivo.nombre

    class Meta:
        model = AlertaCiudadano
        fields = [
            "id",
            "ciudadano",
            "ciudadano_nombre",
            "legajo",
            "legajo_codigo",
            "dispositivo_nombre",
            "tipo",
            "prioridad",
            "mensaje",
            "activa",
            "fecha_cierre",
            "cerrada_por",
            "cerrada_por_nombre",
            "creado",
            "modificado",
        ]
        read_only_fields = ["id", "creado", "modificado"]


from .contactos import *  # noqa: F401,F403,E402
