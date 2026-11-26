"""Serializers del stock en la app de campo (análisis 010, PR 7a): solo lectura.

Las respuestas las arma ``programas.services.stock_app``; acá se fijan las claves que lee la app (`Chaco-mobile`).
Agregar una clave es seguro; renombrarla o sacarla es un release coordinado de la app y de
``programas/tests/base_emergencia_api.py`` (``CLAVES_STOCK_*``). Documentado en
``docs/internal/contrato-app-emergencia.md`` §17.
"""

from rest_framework import serializers

from programas.api.serializers_emergencia_plazas import DispositivoBreveSerializer, EdificioBreveSerializer
from programas.models import MovimientoStock


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
