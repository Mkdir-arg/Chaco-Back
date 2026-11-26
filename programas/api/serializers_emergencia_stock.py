"""Serializers del stock en la app de campo (análisis 010, PR 7a y 7b): lectura y escritura.

Las respuestas las arma ``programas.services.stock_app``; acá se fijan las claves que lee la app (`Chaco-mobile`).
Agregar una clave es seguro; renombrarla o sacarla es un release coordinado de la app y de
``programas/tests/base_emergencia_api.py`` (``CLAVES_STOCK_*``). Documentado en
``docs/internal/contrato-app-emergencia.md`` §17.
"""

from rest_framework import serializers

from programas.api.serializers_emergencia import texto
from programas.api.serializers_emergencia_plazas import DispositivoBreveSerializer, EdificioBreveSerializer
from programas.models import MovimientoStock, OperacionStock


class PuedeEnElStockSerializer(serializers.Serializer):
    entregar = serializers.BooleanField(help_text="`stock.entregar` y `ciudadano.ver` sobre este edificio.")
    ingresar = serializers.BooleanField(help_text="`stock.ingresar` sobre este edificio: ingresos y traspasos.")
    ajustar = serializers.BooleanField(help_text="`stock.ajustar` sobre este edificio.")


class StockDelParSerializer(serializers.Serializer):
    dispositivo = DispositivoBreveSerializer()
    edificio = EdificioBreveSerializer()
    insumos_con_saldo = serializers.IntegerField(help_text="Cuántos insumos tienen saldo mayor que 0.")
    puede = PuedeEnElStockSerializer()


class SaldoDelInsumoSerializer(serializers.Serializer):
    item_id = serializers.IntegerField()
    nombre = serializers.CharField()
    unidad = serializers.CharField()
    cantidad = serializers.IntegerField()
    activo = serializers.BooleanField(help_text="`false`: el insumo está desactivado y solo se puede bajar.")


class InsumoActivoSerializer(serializers.Serializer):
    item_id = serializers.IntegerField()
    nombre = serializers.CharField()
    unidad = serializers.CharField()


class StockDelEdificioSerializer(serializers.Serializer):
    dispositivo = DispositivoBreveSerializer()
    edificio = EdificioBreveSerializer()
    puede = PuedeEnElStockSerializer()
    saldos = SaldoDelInsumoSerializer(many=True)
    insumos_activos = InsumoActivoSerializer(many=True, help_text="Los que se pueden cargar, tengan o no saldo.")


class MovimientoDelStockSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    tipo = serializers.ChoiceField(choices=MovimientoStock.Tipo.choices)
    item_id = serializers.IntegerField()
    nombre = serializers.CharField()
    unidad = serializers.CharField()
    cantidad = serializers.IntegerField(help_text="Con signo: negativa si salió.")
    saldo_posterior = serializers.IntegerField()
    creado_en = serializers.DateTimeField()
    usuario = serializers.CharField(help_text="Quién lo hizo (en una recepción de kit, quien recibió).")
    detalle = serializers.CharField(
        help_text="Origen, motivo o sentido del traspaso. Nunca nombra a la persona ni a otra institución."
    )


class PaginaDeMovimientosSerializer(serializers.Serializer):
    resultados = MovimientoDelStockSerializer(many=True)
    siguiente = serializers.IntegerField(
        allow_null=True, help_text="`cursor` de la página que sigue; `null` si no hay más."
    )


class MovimientosConsultaSerializer(serializers.Serializer):
    """Los parámetros del libro. Un valor inválido es 400, no un filtro que devuelve vacío en silencio."""

    tipo = serializers.ChoiceField(choices=MovimientoStock.Tipo.choices, required=False, default="")
    item = serializers.IntegerField(min_value=1, required=False, default=None)
    cursor = serializers.IntegerField(min_value=1, required=False, default=None)


class DestinoDeTraspasoSerializer(serializers.Serializer):
    dispositivo = DispositivoBreveSerializer()
    edificio = EdificioBreveSerializer()


class PersonaDelStockSerializer(serializers.Serializer):
    dni = serializers.CharField()
    nombre = serializers.CharField(allow_blank=True)
    apellido = serializers.CharField(allow_blank=True)


class LineaDelHistorialSerializer(serializers.Serializer):
    nombre = serializers.CharField()
    unidad = serializers.CharField()
    cantidad = serializers.IntegerField()


class EntregaDelHistorialSerializer(serializers.Serializer):
    creado_en = serializers.DateTimeField()
    institucion = serializers.CharField(help_text="El nombre solo si es esta institución; si no, «Otra institución».")
    lineas = LineaDelHistorialSerializer(many=True)


class ConsultaDePersonaStockSerializer(serializers.Serializer):
    persona = PersonaDelStockSerializer(
        allow_null=True,
        help_text="`null` si no alcanza para identificarla: se cargan nombre y apellido al entregar.",
    )
    historial = EntregaDelHistorialSerializer(many=True)


# ---------------------------------------------------------------------------
# Escritura (PR 7b): acá solo se mira la forma; las reglas son de ``services.stock``, la misma que usa la web.
# ---------------------------------------------------------------------------

MENSAJE_LINEAS = "Mandá `lineas`: una lista con al menos una línea con `item_id` y `cantidad`."


class _LineasField(serializers.ListField):
    """``[{"item_id": 12, "cantidad": 2}]`` → ``[(12, 2)]``, los pares que recibe el servicio.

    Una lista de pares y no un dict: un insumo repetido tiene que llegar al servicio para que lo rechace, no
    colapsarse en silencio. El valor de cada ``item_id`` y de cada ``cantidad`` lo valida el servicio (RN-010-04).
    """

    default_error_messages = {"invalida": MENSAJE_LINEAS}

    def to_internal_value(self, data):
        if not isinstance(data, list) or not data:
            self.fail("invalida")
        pares = []
        for linea in data:
            if not isinstance(linea, dict) or "item_id" not in linea or "cantidad" not in linea:
                self.fail("invalida")
            pares.append((linea["item_id"], linea["cantidad"]))
        return pares

    def to_representation(self, value):
        return [{"item_id": item_id, "cantidad": cantidad} for item_id, cantidad in value]


def _lineas():
    return _LineasField(
        child=serializers.DictField(),
        help_text="`[{item_id, cantidad}]`: al menos una, sin repetir insumo, cantidades enteras > 0.",
    )


def _uuid_cliente():
    return serializers.UUIDField(
        help_text="Identificador de la operación, generado en el celular. Reenviarlo no la repite (200, `ya_existia`)."
    )


class EntregaAPersonaEnvioSerializer(serializers.Serializer):
    uuid_cliente = _uuid_cliente()
    dni = serializers.CharField(max_length=20, help_text="El DNI de la persona.")
    lineas = _lineas()
    sexo = texto(help_text="`F`, `M` o `X`: con él se consulta al Registro si la persona no tiene legajo.")
    nombre = texto(help_text="Solo si no hay legajo ni Registro (`PERSONA_SIN_DATOS`): con el apellido, da el alta.")
    apellido = texto(help_text="Ver `nombre`.")
    observacion = texto(help_text="Texto libre. No sale en el libro de la app.")


class IngresoManualEnvioSerializer(serializers.Serializer):
    uuid_cliente = _uuid_cliente()
    lineas = _lineas()
    origen = serializers.CharField(help_text="`" + "`, `".join(OperacionStock.Origen.values) + "`.")
    origen_detalle = texto(help_text="Obligatorio con origen `OTRO`.")
    comprobante = texto(help_text="Texto libre y opcional.")


class TraspasoEnvioSerializer(serializers.Serializer):
    uuid_cliente = _uuid_cliente()
    destino_dispositivo_id = serializers.IntegerField(help_text="Uno de `destinos-traspaso/`.")
    destino_edificio_id = serializers.IntegerField(help_text="Uno de `destinos-traspaso/`.")
    lineas = _lineas()
    observacion = texto(help_text="Texto libre.")


class AjusteEnvioSerializer(serializers.Serializer):
    uuid_cliente = _uuid_cliente()
    item_id = serializers.IntegerField(help_text="El insumo que se contó.")
    cantidad_contada = serializers.IntegerField(help_text="Lo que se contó: entero, cero o más.")
    saldo_visto = serializers.IntegerField(
        help_text="El saldo que se vio al abrir el ajuste: si cambió, 409 `SALDO_CAMBIO`."
    )
    motivo = serializers.CharField(help_text="`" + "`, `".join(OperacionStock.MotivoAjuste.values) + "`.")
    detalle = texto(help_text="Obligatorio con motivo `OTRO` y `CORRECCION_CARGA`.")


class MovimientoDeLaOperacionSerializer(serializers.Serializer):
    item_id = serializers.IntegerField()
    nombre = serializers.CharField()
    unidad = serializers.CharField()
    cantidad = serializers.IntegerField(help_text="Con signo: negativa si salió.")
    saldo_posterior = serializers.IntegerField(help_text="El saldo del edificio después de esta operación.")


class OperacionDeStockSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    tipo = serializers.ChoiceField(choices=OperacionStock.Tipo.choices)
    uuid_cliente = serializers.UUIDField(allow_null=True)
    ya_existia = serializers.BooleanField(help_text="`true`: era un reenvío; se devuelve la primera vez (200).")
    creado_en = serializers.DateTimeField()
    movimientos = MovimientoDeLaOperacionSerializer(
        many=True, help_text="Los del edificio de origen: en un traspaso, la salida; nunca el otro lado."
    )


class SaldoDelRechazoSerializer(serializers.Serializer):
    item_id = serializers.IntegerField()
    nombre = serializers.CharField()
    unidad = serializers.CharField()
    cantidad = serializers.IntegerField(help_text="Lo que hay ahora.")
    alcanza = serializers.BooleanField(help_text="`false`: lo pedido de este insumo supera lo que hay.")


class SaldoInsuficienteSerializer(serializers.Serializer):
    detail = serializers.CharField()
    code = serializers.CharField()
    saldos = SaldoDelRechazoSerializer(many=True, help_text="**Todas** las líneas que salen, no solo las faltantes.")


class SaldoCambioSerializer(serializers.Serializer):
    detail = serializers.CharField()
    code = serializers.CharField()
    saldo_actual = serializers.IntegerField()
    saldo_visto = serializers.IntegerField()
