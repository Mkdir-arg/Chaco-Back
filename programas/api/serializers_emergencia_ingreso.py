"""Cuerpos del ingreso de una persona a una cama desde la app (Cambio 614).

Solo la forma del envío y de las respuestas: las reglas de fondo (plaza libre, persona ya alojada, alta del
legajo) son de ``programas.services.ingreso`` y ``programas.services.estadias``.
"""

from django.utils import timezone
from rest_framework import serializers

from core.dni import MENSAJE_DNI_INVALIDO, dni_valido, normalizar_dni
from legajos.models import Ciudadano


class PersonaNuevaEnvioSerializer(serializers.Serializer):
    """El alta manual de la persona que no está en el padrón.

    Lo que el modelo exige de verdad es DNI, nombre y apellido; ``sexo`` y ``fecha_nacimiento`` son opcionales
    (la app los pide, pero una persona sin esos datos no queda sin cama). Sin ``estado_renaper``: no se validó.
    """

    dni = serializers.CharField(max_length=32)
    nombre = serializers.CharField(max_length=Ciudadano._meta.get_field("nombre").max_length)
    apellido = serializers.CharField(max_length=Ciudadano._meta.get_field("apellido").max_length)
    # CharField y no ChoiceField: un enum «sexo» más choca con los del esquema (drf-spectacular).
    sexo = serializers.CharField(max_length=1, required=False, allow_null=True, allow_blank=True, default="")
    fecha_nacimiento = serializers.DateField(required=False, allow_null=True, default=None)

    def validate_dni(self, valor):
        dni = normalizar_dni(valor)
        if not dni_valido(dni):
            raise serializers.ValidationError(MENSAJE_DNI_INVALIDO)
        return dni

    def validate_sexo(self, valor):
        if valor and valor not in Ciudadano.Genero.values:
            raise serializers.ValidationError("El sexo es F, M o X.")
        return valor or ""

    def validate_fecha_nacimiento(self, valor):
        if valor and valor > timezone.localdate():
            raise serializers.ValidationError("La fecha de nacimiento no puede ser futura.")
        return valor


class FormularioEnvioSerializer(serializers.Serializer):
    """Lo respondido del formulario de ingreso: la versión con la que la app lo dibujó y ``{clave: valor}``."""

    version = serializers.IntegerField(min_value=0)
    respuestas = serializers.DictField(child=serializers.JSONField(), required=False, default=dict)


class IngresarEnvioSerializer(serializers.Serializer):
    """``{plaza_id?, ciudadano_id? | persona_nueva?, formulario?}``: una de las dos formas de indicar a la persona."""

    plaza_id = serializers.IntegerField(required=False, allow_null=True, default=None)
    ciudadano_id = serializers.IntegerField(required=False, allow_null=True, default=None)
    persona_nueva = PersonaNuevaEnvioSerializer(required=False, allow_null=True, default=None)
    formulario = FormularioEnvioSerializer(required=False, allow_null=True, default=None)

    def validate(self, datos):
        if datos["ciudadano_id"] is None and datos["persona_nueva"] is None:
            raise serializers.ValidationError(
                {"ciudadano_id": ["Indicá a la persona: `ciudadano_id` o `persona_nueva`."]}
            )
        if datos["ciudadano_id"] is not None and datos["persona_nueva"] is not None:
            raise serializers.ValidationError(
                {"persona_nueva": ["Mandá `ciudadano_id` o `persona_nueva`, no las dos."]}
            )
        return datos


class PersonaDelIngresoSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    dni = serializers.CharField()
    nombre_completo = serializers.CharField()


class AlojamientoDelIngresoSerializer(serializers.Serializer):
    """Dónde está alojada hoy. ``dispositivo``, ``plaza`` y ``desde`` vienen vacíos si es de fuera del alcance."""

    mensaje = serializers.CharField()
    dentro_del_alcance = serializers.BooleanField()
    dispositivo = serializers.CharField(allow_blank=True)
    plaza = serializers.CharField(allow_blank=True)
    desde = serializers.DateTimeField(allow_null=True)


class PersonaDelIngresoRespuestaSerializer(serializers.Serializer):
    encontrada = serializers.BooleanField()
    puede_dar_de_alta = serializers.BooleanField(required=False)
    persona = PersonaDelIngresoSerializer(required=False)
    alojada = serializers.BooleanField(required=False)
    alojamiento = AlojamientoDelIngresoSerializer(required=False, allow_null=True)
    plaza_reservada_id = serializers.IntegerField(required=False, allow_null=True)


class FormularioDeIngresoSerializer(serializers.Serializer):
    definicion = serializers.DictField()
    version = serializers.IntegerField()
    requiere_archivo = serializers.BooleanField()


class FormularioDeIngresoRespuestaSerializer(serializers.Serializer):
    formulario = FormularioDeIngresoSerializer(allow_null=True)
