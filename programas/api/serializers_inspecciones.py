"""Serializers de la API de campo del relevamiento edilicio (MVP v2, tasks 38 y 39).

Lo que lee y manda la app del agente territorial (`Chaco-mobile`). Agregar una clave es
seguro; renombrarla o sacarla es un release coordinado de la app (mismo criterio que
`programas/tests/test_becas_api_contrato.py`).
"""

from rest_framework import serializers

from programas.models import Edificio, FotoInspeccion, InspeccionEdificio


class EdificioCampoSerializer(serializers.ModelSerializer):
    """Dónde ir: lo que el agente necesita para llegar al edificio."""

    class Meta:
        model = Edificio
        fields = [
            "id",
            "codigo",
            "nombre",
            "calle",
            "numero",
            "piso_departamento",
            "localidad",
            "provincia",
            "codigo_postal",
            "latitud",
            "longitud",
        ]
        read_only_fields = fields


class FotoInspeccionCampoSerializer(serializers.ModelSerializer):
    """Una foto ya recibida. Sin el archivo: la app ya lo tiene, y `/media/` va por sesión."""

    class Meta:
        model = FotoInspeccion
        fields = ["id", "uuid_cliente", "descripcion", "creado"]
        read_only_fields = fields


class InspeccionCampoListSerializer(serializers.ModelSerializer):
    edificio = EdificioCampoSerializer(read_only=True)
    vencida = serializers.BooleanField(read_only=True, help_text="En curso y con el vencimiento pasado.")

    class Meta:
        model = InspeccionEdificio
        fields = ["id", "edificio", "estado", "fecha_vencimiento", "vencida", "indicaciones"]
        read_only_fields = fields


class InspeccionCampoDetailSerializer(InspeccionCampoListSerializer):
    fotos = FotoInspeccionCampoSerializer(many=True, read_only=True)

    class Meta(InspeccionCampoListSerializer.Meta):
        fields = [
            *InspeccionCampoListSerializer.Meta.fields,
            "criticidad",
            "observaciones",
            "realizada_en",
            "uuid_resultado",
            "motivo_cancelacion",
            "fotos",
        ]
        read_only_fields = fields


class ResultadoInspeccionSerializer(serializers.Serializer):
    """Cuerpo de ``POST /api/dispositivos/inspecciones/{id}/resultado/``."""

    uuid_cliente = serializers.UUIDField(
        help_text="Identificador del envío, generado en el celular. Reenviarlo no duplica."
    )
    criticidad = serializers.ChoiceField(choices=InspeccionEdificio.Criticidad.choices)
    observaciones = serializers.CharField(required=False, allow_blank=True, default="")


class FotoInspeccionEnvioSerializer(serializers.Serializer):
    """Cuerpo multipart de ``POST /api/dispositivos/inspecciones/{id}/fotos/``.

    El tipo, la firma y el tamaño del archivo los valida el modelo (`validar_foto`), no
    este serializer: una sola regla para la app y el backoffice. **HEIC/HEIF no entran**:
    la conversión a JPEG es de la app, como la compresión.
    """

    uuid_cliente = serializers.UUIDField(
        help_text="Identificador de la foto, generado en el celular. Reenviarla no duplica."
    )
    archivo = serializers.FileField(help_text="JPEG, PNG o WEBP, hasta 5 MB. HEIC/HEIF se convierten en la app.")
    descripcion = serializers.CharField(required=False, allow_blank=True, default="", max_length=120)
