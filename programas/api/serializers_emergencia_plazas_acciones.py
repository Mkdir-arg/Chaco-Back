"""Cuerpos de las acciones de cama de la app (Cambio 598).

Solo la forma del envío: las reglas de fondo (plaza libre, alcance, vigencia) son de
``programas.services.estadias``, y la persona se resuelve en la vista, como lo hace la web.
"""

from rest_framework import serializers

from core.dni import MENSAJE_DNI_INVALIDO, dni_valido, normalizar_dni


class ReservarPlazaEnvioSerializer(serializers.Serializer):
    """Reservar: ``{dni, sexo?, desde?, hasta?, motivo?}``.

    ``desde`` y ``sexo`` se aceptan por contrato con la app pero no se usan: la reserva arranca ahora, y la web
    tampoco da de alta personas desde «Reservar» (``ReservarPlazaForm``), solo busca en el Legajo por DNI.
    """

    dni = serializers.CharField(max_length=32)
    # CharField y no ChoiceField: un enum «sexo» más choca con los del esquema (drf-spectacular).
    sexo = serializers.CharField(max_length=1, required=False, allow_null=True, allow_blank=True)
    desde = serializers.DateTimeField(required=False, allow_null=True)
    hasta = serializers.DateTimeField(required=False, allow_null=True)
    motivo = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")

    def validate_sexo(self, valor):
        if valor and valor not in ("F", "M", "X"):
            raise serializers.ValidationError("El sexo es F, M o X.")
        return valor

    def validate_dni(self, valor):
        dni = normalizar_dni(valor)
        if not dni_valido(dni):
            raise serializers.ValidationError(MENSAJE_DNI_INVALIDO)
        return dni


class PrestarPlazaEnvioSerializer(ReservarPlazaEnvioSerializer):
    """Prestar: lo mismo, con el vencimiento obligatorio (``PrestarPlazaForm``)."""

    hasta = serializers.DateTimeField(
        error_messages={
            "required": "Un préstamo exige indicar hasta cuándo.",
            "null": "Un préstamo exige indicar hasta cuándo.",
        }
    )


class LiberarPlazaEnvioSerializer(serializers.Serializer):
    motivo = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")


class FueraDeServicioEnvioSerializer(serializers.Serializer):
    motivo = serializers.CharField(
        max_length=200,
        error_messages={
            "required": "Sacar una plaza de servicio exige un motivo.",
            "blank": "Sacar una plaza de servicio exige un motivo.",
            "null": "Sacar una plaza de servicio exige un motivo.",
        },
    )
