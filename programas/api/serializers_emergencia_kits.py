"""Serializers de la API de campo, M3 · Recepción de kits (y «mis dispositivos»).

Salieron de ``serializers_emergencia`` para que ese archivo no pase el tope de 1000 líneas, igual que ya se parten
por superficie los de plazas, estadías y stock. Mismas clases, mismo esquema: el contrato que lee Chaco-mobile está
en ``docs/internal/contrato-app-emergencia.md`` y las claves en ``programas/tests/base_emergencia_api.py``.
``EstadoCambioSerializer`` (el 409 que comparten llegadas y kits) se queda en ``serializers_emergencia``.
"""

import re

from rest_framework import serializers
from rest_framework.fields import empty
from rest_framework.utils import html

from programas.api.serializers_emergencia import texto
from programas.models import EntregaKit, LineaEntrega
from programas.services.kits import edificios_para_recibir, requiere_edificio_al_recibir

#: Cómo viaja la cantidad de cada ítem en el multipart de la recepción: `cantidades[<id del ítem>]`.
CLAVE_DE_CANTIDAD = re.compile(r"^cantidades\[(\d+)\]$")
MENSAJE_SIN_CANTIDADES = "Indicá cuánto llegó de cada ítem: un campo `cantidades[<id del ítem>]` por línea."
MENSAJE_CANTIDADES_INVALIDAS = "La cantidad de cada ítem tiene que ser un número entero, cero o más."


class MiDispositivoEmergenciaSerializer(serializers.Serializer):
    """Un dispositivo donde el usuario es de la guardia de Emergencia (RU-5)."""

    id = serializers.IntegerField()
    nombre = serializers.CharField()
    entregas_pendientes = serializers.IntegerField(
        help_text="Entregas de kits que el usuario puede recibir ahí (en camino o preparadas). 0 si solo admite."
    )
    plazas_libres = serializers.IntegerField(
        help_text="Camas libres ahora (PR 8). 0 donde el usuario solo recibe kits y no admite familias."
    )
    derivaciones_pendientes = serializers.IntegerField(
        help_text="Derivaciones por aceptar o rechazar (PR 8). 0 donde el usuario solo recibe kits."
    )
    admite = serializers.BooleanField(
        help_text="El usuario admite familias (`dispositivo.admitir`) en este dispositivo: ofrecer M2 acá."
    )
    recibe_kits = serializers.BooleanField(
        help_text="El usuario recibe kits (`emergencia.recibir_kit`) en este dispositivo: ofrecer M3 acá."
    )


class LineaEntregaKitSerializer(serializers.ModelSerializer):
    """Un ítem de la entrega: lo enviado y, cuando ya se recibió, lo recibido."""

    item = serializers.IntegerField(source="item_id", read_only=True, help_text="`id` del ítem del catálogo.")
    nombre = serializers.CharField(source="nombre_visible", read_only=True)
    enviada = serializers.IntegerField(source="cantidad_enviada", read_only=True)
    recibida = serializers.IntegerField(
        source="cantidad_recibida", read_only=True, allow_null=True, help_text="`null` hasta que se recibe."
    )

    class Meta:
        model = LineaEntrega
        fields = ["item", "nombre", "unidad", "enviada", "recibida"]
        read_only_fields = fields


class EntregaKitSerializer(serializers.ModelSerializer):
    """Una entrega de kits como la ve la guardia: la misma forma en la lista y en el detalle."""

    lineas = LineaEntregaKitSerializer(many=True, read_only=True)
    requiere_edificio = serializers.SerializerMethodField(
        help_text="Hay que elegir `edificio_id` al recibirla: no tiene edificio y la institución lleva stock."
    )
    edificios = serializers.SerializerMethodField(
        help_text="Entre cuáles elige quien recibe (`{id, nombre}`). Vacía si no hay nada que elegir."
    )

    class Meta:
        model = EntregaKit
        fields = [
            "id",
            "numero",
            "estado",
            "despachada_en",
            "recibida_en",
            "observacion_mesa",
            "observacion_dispositivo",
            "lineas",
            "requiere_edificio",
            "edificios",
        ]
        read_only_fields = fields

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Con ``many=True`` el hijo es uno solo para toda la lista: el memo vive lo que la respuesta.
        self._memo_por_dispositivo = {}

    def _de_su_dispositivo(self, entrega) -> dict:
        """``{"requiere_edificio", "edificios"}`` de una entrega **sin edificio**, calculado una vez por dispositivo.

        La lista trae muchas entregas del mismo dispositivo y la respuesta solo depende de él y del usuario: se
        resuelve una vez y no por fila. Por eso la lista **no crece en consultas** con las entregas legadas (sin
        edificio): las consultas son las del primer dispositivo, no las de cada entrega.
        """

        if entrega.dispositivo_id not in self._memo_por_dispositivo:
            usuario = getattr(self.context.get("request"), "user", None)
            requiere = requiere_edificio_al_recibir(entrega)
            edificios = edificios_para_recibir(usuario, entrega) if requiere and usuario is not None else []
            self._memo_por_dispositivo[entrega.dispositivo_id] = {
                "requiere_edificio": requiere,
                "edificios": [{"id": e.pk, "nombre": e.nombre} for e in edificios],
            }
        return self._memo_por_dispositivo[entrega.dispositivo_id]

    def get_requiere_edificio(self, entrega) -> bool:
        # Solo una entrega sin edificio (anteriores al Cambio 523) puede pedirlo: el resto no consulta nada.
        return entrega.edificio_id is None and self._de_su_dispositivo(entrega)["requiere_edificio"]

    def get_edificios(self, entrega) -> list:
        if entrega.edificio_id is not None:
            return []
        return self._de_su_dispositivo(entrega)["edificios"]


class _CantidadesField(serializers.DictField):
    """``{"<id del ítem>": cantidad}``. En multipart, un campo ``cantidades[<id>]`` por ítem."""

    def get_value(self, dictionary):
        if html.is_html_input(dictionary):
            cantidades = {}
            for clave in dictionary:
                coincide = CLAVE_DE_CANTIDAD.match(clave)
                if coincide:
                    cantidades[coincide.group(1)] = dictionary.get(clave)
            return cantidades or empty
        return super().get_value(dictionary)

    def run_child_validation(self, data):
        # Un solo mensaje para el campo, no un dict de errores por ítem: el 400 de la app es
        # una lista de mensajes por clave.
        try:
            return super().run_child_validation(data)
        except serializers.ValidationError:
            raise serializers.ValidationError(MENSAJE_CANTIDADES_INVALIDAS) from None


class RecepcionKitEnvioSerializer(serializers.Serializer):
    """Cuerpo multipart de ``POST /api/emergencia/entregas/{id}/recibir/``.

    Acá solo se mira **la forma** (que el identificador sea un UUID, que las cantidades sean
    enteros). Las reglas —una cantidad por cada línea, el remito obligatorio en JPEG de hasta
    5 MB, el estado de la entrega, el alcance— son de ``recibir_entrega``, la misma función
    que usa la recepción web (RU-2): por eso el remito no es obligatorio en este nivel.
    """

    uuid_cliente = serializers.UUIDField(
        help_text="Identificador de la recepción, generado en el celular. Reenviarlo no la repite."
    )
    cantidades = _CantidadesField(
        child=serializers.IntegerField(min_value=0),
        error_messages={"required": MENSAJE_SIN_CANTIDADES},
        help_text=(
            "Cuánto llegó de **cada** ítem de la entrega, aunque sea 0. En multipart, un campo "
            "`cantidades[<id del ítem>]` por línea (p. ej. `cantidades[12]=8`)."
        ),
    )
    remito = serializers.FileField(
        required=False,
        allow_null=True,
        default=None,
        help_text="Obligatorio. Foto del remito en JPEG, hasta 5 MB. HEIC/HEIF se convierten en la app.",
    )
    observacion = texto(help_text="Lo que la mesa tiene que saber de esta entrega. Opcional.")
    edificio_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        default=None,
        help_text="Edificio en que se recibe. Obligatorio si la entrega trae `requiere_edificio: true`; si no, se ignora.",
    )

    def cantidades_por_item(self):
        """``{item_id: cantidad}`` con las claves como enteros: lo que recibe ``recibir_entrega``."""
        return {int(item_id): cantidad for item_id, cantidad in self.validated_data["cantidades"].items()}


class DiferenciaDeRecepcionSerializer(serializers.Serializer):
    item = serializers.IntegerField(help_text="`id` del ítem del catálogo.")
    enviada = serializers.IntegerField()
    recibida = serializers.IntegerField()


class RecepcionKitRespuestaSerializer(serializers.Serializer):
    """«Recibida · 2 ítems con diferencia» (M3-2): el estado final y lo que difirió."""

    estado = serializers.ChoiceField(
        choices=EntregaKit.Estado.choices, help_text="`RECIBIDA` o `RECIBIDA_CON_DIFERENCIAS`."
    )
    diferencias = DiferenciaDeRecepcionSerializer(
        many=True, help_text="Las líneas con `recibida` distinta de `enviada`. Vacía si llegó completa."
    )
