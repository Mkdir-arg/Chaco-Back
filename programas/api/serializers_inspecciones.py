"""Serializers de la API de campo del relevamiento edilicio (MVP v2, tasks 38 y 39).

Lo que lee y manda la app del agente territorial (`Chaco-mobile`). Agregar una clave es
seguro; renombrarla o sacarla es un release coordinado de la app (mismo criterio que
`programas/tests/test_becas_api_contrato.py`).
"""

from rest_framework import serializers

from programas.models import AdjuntoRespuestaRelevamiento, Edificio, FotoInspeccion, InspeccionEdificio
from programas.services.respuestas_dispositivo import foto_vigente


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


class AdjuntoFormularioCampoSerializer(serializers.ModelSerializer):
    """Un archivo de un campo del formulario ya recibido. Sin el archivo: la app ya lo tiene."""

    class Meta:
        model = AdjuntoRespuestaRelevamiento
        fields = ["id", "clave", "uuid_cliente", "creado"]
        read_only_fields = fields


def _diseno_vigente(inspeccion):
    """El formulario «Relevamiento» que hoy pide este relevamiento, o ``None`` (sin formulario
    o dado de baja). Hay que traer ``diseno`` con ``select_related``."""
    diseno = inspeccion.diseno if inspeccion.diseno_id is not None else None
    return diseno if diseno is not None and diseno.dado_de_baja_en is None else None


class InspeccionCampoListSerializer(serializers.ModelSerializer):
    edificio = EdificioCampoSerializer(read_only=True)
    vencida = serializers.BooleanField(read_only=True, help_text="En curso y con el vencimiento pasado.")
    formulario_version = serializers.SerializerMethodField(
        help_text="Versión vigente del formulario del relevamiento; `null` si no tiene formulario."
    )

    class Meta:
        model = InspeccionEdificio
        fields = ["id", "edificio", "estado", "fecha_vencimiento", "vencida", "indicaciones", "formulario_version"]
        read_only_fields = fields

    def get_formulario_version(self, inspeccion) -> int | None:
        diseno = _diseno_vigente(inspeccion)
        return diseno.version if diseno is not None else None


class InspeccionCampoDetailSerializer(InspeccionCampoListSerializer):
    fotos = FotoInspeccionCampoSerializer(many=True, read_only=True)
    formulario = serializers.SerializerMethodField(
        help_text=(
            "El formulario «Relevamiento» **vigente**: `{definicion, version}`, con la definición en el mismo "
            "formato que el de Becas y los formularios por tipo. `null` si el tipo no tiene formulario."
        )
    )

    class Meta(InspeccionCampoListSerializer.Meta):
        fields = [
            *InspeccionCampoListSerializer.Meta.fields,
            "formulario",
            "criticidad",
            "observaciones",
            "realizada_en",
            "uuid_resultado",
            "motivo_cancelacion",
            "fotos",
        ]
        read_only_fields = fields

    def get_formulario(self, inspeccion) -> dict | None:
        diseno = _diseno_vigente(inspeccion)
        if diseno is None:
            return None
        return {"definicion": foto_vigente(diseno), "version": diseno.version}


class ResultadoInspeccionSerializer(serializers.Serializer):
    """Cuerpo de ``POST /api/dispositivos/inspecciones/{id}/resultado/``."""

    uuid_cliente = serializers.UUIDField(
        help_text="Identificador del envío, generado en el celular. Reenviarlo no duplica."
    )
    criticidad = serializers.ChoiceField(choices=InspeccionEdificio.Criticidad.choices)
    observaciones = serializers.CharField(required=False, allow_blank=True, default="")
    respuestas = serializers.DictField(
        child=serializers.JSONField(),
        required=False,
        allow_null=True,
        default=None,
        help_text=(
            "`{clave: valor}` del formulario del relevamiento, si lo tiene. Texto: string; entero: número o "
            "string numérico; selector: una opción; selector múltiple: lista de opciones; fecha: `AAAA-MM-DD`. "
            "Los campos de archivo no van acá: se mandan a `adjuntos/`."
        ),
    )
    version_capturada = serializers.IntegerField(
        required=False,
        allow_null=True,
        default=None,
        min_value=0,
        help_text=(
            "Versión del formulario con la que la app capturó. Opcional: si difiere de la vigente al recibir "
            "el resultado, se acepta y el informe lo marca."
        ),
    )


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


class AdjuntoFormularioEnvioSerializer(serializers.Serializer):
    """Cuerpo multipart de ``POST /api/dispositivos/inspecciones/{id}/adjuntos/``.

    Extensión, tamaño y firma del archivo los valida el modelo (``validar_adjunto``): los mismos
    límites que los adjuntos de la app de Becas.
    """

    clave = serializers.CharField(max_length=60, help_text="La clave de un campo de archivo del formulario.")
    archivo = serializers.FileField(help_text="JPG, PNG, WEBP, HEIC o PDF, hasta 5 MB.")
    uuid_cliente = serializers.UUIDField(
        help_text="Identificador del archivo, generado en el celular. Reenviarlo no duplica."
    )
