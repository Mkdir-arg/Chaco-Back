"""API de campo, «Stock» (análisis 010, PR 7b): las cuatro escrituras. Entregar a una persona, ingresar, traspasar y ajustar.

Cada vista llama a **la misma función** de ``services.stock`` que la web y solo traduce lo que contesta: ninguna regla de
saldo, de estado ni de permiso vive acá (la vista mira el permiso antes de validar el cuerpo para dar 403 y no 400, y el
servicio lo vuelve a exigir). Quién ve qué es el alcance de ``stock.ver`` (lo ajeno, lo inexistente, lo no vinculado y la
institución que no lleva stock son el mismo **404**); la capacidad de la acción —``stock.entregar`` con ``ciudadano.ver``,
``stock.ingresar``, ``stock.ajustar``— sobre el **par** (institución, edificio) es 403 ``SIN_PERMISO``.

Idempotentes por ``uuid_cliente``: **201** la primera vez, **200** con ``ya_existia: true`` el reenvío del mismo usuario
para el mismo lugar (con el resultado de la primera vez, sin mover el saldo). Un reenvío con el cuerpo malformado es 400
antes de llegar al servicio. Sin escrituras offline (decisión 7): la app necesita conexión y no las encola.

Los rechazos del servicio, con su ``code``: 409 ``SALDO_INSUFICIENTE`` (con los saldos), ``SALDO_CAMBIO``,
``UUID_EN_USO`` y ``STOCK_NO_HABILITADO``; 400 ``VALIDACION`` y ``PERSONA_SIN_DATOS``. Una entrega rechazada por la
persona, por el saldo o por una institución o un edificio no activos gasta una consulta de ``personas_campo`` (429 si
se agotó); la asentada no.
"""

from django.core.exceptions import PermissionDenied, ValidationError
from drf_spectacular.utils import OpenApiResponse, PolymorphicProxySerializer, extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import Throttled
from rest_framework.parsers import JSONParser
from rest_framework.response import Response

from programas.api.serializers_emergencia_stock import (
    AjusteEnvioSerializer,
    EntregaAPersonaEnvioSerializer,
    IngresoManualEnvioSerializer,
    OperacionDeStockSerializer,
    SaldoCambioSerializer,
    SaldoInsuficienteSerializer,
    TraspasoEnvioSerializer,
)
from programas.api.throttles import StockEscrituraThrottle, descontar_consulta_de_identidad
from programas.api.views_emergencia import (
    _SIN_TOKEN,
    _creado_o_reenvio,
    _errores,
    _respuesta_de_validacion,
)
from programas.api.views_emergencia_stock import (
    _FUERA_DE_ALCANCE,
    _SIN_PERMISO,
    _sin_permiso,
    _VistaDeStock,
)
from programas.services import stock as servicio
from programas.services import stock_app
from programas.services.stock_personas import PersonaSinDatos

CODIGO_PERSONA_SIN_DATOS = "PERSONA_SIN_DATOS"

#: Lo que el servicio llama de una forma y la app manda de otra.
_CLAVE_DE_LA_APP = {"item": "item_id"}


class UuidEnUsoSerializer(serializers.Serializer):
    """409 de ``UUID_EN_USO``: solo el mensaje y el código."""

    detail = serializers.CharField()
    code = serializers.CharField()


class StockNoHabilitadoSerializer(serializers.Serializer):
    """409 de ``STOCK_NO_HABILITADO``: solo el mensaje y el código."""

    detail = serializers.CharField()
    code = serializers.CharField()


_CONFLICTOS = OpenApiResponse(
    response=PolymorphicProxySerializer(
        component_name="RechazoDeStock409",
        # El discriminador es `code`: un cuerpo `SALDO_INSUFICIENTE` también tiene `detail` y `code`, así que sin él
        # los tres esquemas se superponen y `oneOf` no dice cuál es.
        serializers={
            "SALDO_INSUFICIENTE": SaldoInsuficienteSerializer,
            "SALDO_CAMBIO": SaldoCambioSerializer,
            "UUID_EN_USO": UuidEnUsoSerializer,
            "STOCK_NO_HABILITADO": StockNoHabilitadoSerializer,
        },
        resource_type_field_name="code",
    ),
    description=(
        "`code: SALDO_INSUFICIENTE` (con `saldos` de todas las líneas que salen), `SALDO_CAMBIO` (ajuste: con "
        "`saldo_actual` y `saldo_visto`), `UUID_EN_USO` (ese `uuid_cliente` es de otra operación, de otro usuario o de "
        "otro lugar) o `STOCK_NO_HABILITADO` (la institución —o la de destino de un traspaso— no lleva stock o no está "
        "activa, o el edificio está inactivo)."
    ),
)
_VALIDACION = OpenApiResponse(
    description=(
        "`code: VALIDACION` con el detalle por campo (cuerpo mal armado, líneas, origen, motivo, destino…), o "
        "`PERSONA_SIN_DATOS` con `pide_sexo` y `motivo`: no alcanza para identificar a la persona."
    )
)
_OPERACION = OpenApiResponse(
    response=OperacionDeStockSerializer, description="Asentada: **201**. Reenvío del mismo `uuid_cliente`: **200**."
)


def _rechazo(error, serializador=None, **extra):
    cuerpo = {"detail": error.messages[0], "code": error.code, **extra}
    if serializador is not None:
        cuerpo = serializador(cuerpo).data
    return Response(cuerpo, status=status.HTTP_409_CONFLICT)


def _con_claves_de_la_app(error):
    """El ``ValidationError`` con las claves del servicio que la app llama distinto (``item`` → ``item_id``)."""

    if not hasattr(error, "error_dict"):
        return error
    return ValidationError({_CLAVE_DE_LA_APP.get(campo, campo): errores for campo, errores in error.error_dict.items()})


class _EscrituraDeStockView(_VistaDeStock):
    """El molde de las cuatro: par en alcance → capacidad → forma del cuerpo → servicio → 201 o 200."""

    parser_classes = [JSONParser]
    throttle_classes = [StockEscrituraThrottle]
    envio = None
    #: Una entrega rechazada por la persona, por el saldo o por una institución o un edificio no activos gasta la cuota
    #: de identidad (ver ``_descontar_identidad``).
    gasta_cuota_de_identidad = False

    def puede(self, usuario, dispositivo, edificio_id):
        raise NotImplementedError

    def asentar(self, usuario, dispositivo, edificio, datos):
        raise NotImplementedError

    def post(self, request, dispositivo_id, edificio_id):
        dispositivo, edificio = self._par(request, dispositivo_id, edificio_id)
        if not self.puede(request.user, dispositivo, edificio.pk):
            return _sin_permiso()
        datos, respuesta = self._entrada(self.envio, request)
        if respuesta is not None:
            return respuesta
        operacion, respuesta = self._correr(lambda: self.asentar(request.user, dispositivo, edificio, datos))
        if respuesta is not None:
            return respuesta
        cuerpo = OperacionDeStockSerializer(stock_app.operacion_para_la_app(operacion, dispositivo, edificio)).data
        return Response(cuerpo, status=_creado_o_reenvio(operacion.ya_existia))

    def _correr(self, accion):
        """Corre la función del servicio y traduce lo que rechace: ``(operación, None)`` o ``(None, respuesta)``."""

        try:
            return accion(), None
        except PersonaSinDatos as error:
            self._descontar_identidad()
            return None, self._sin_datos(error)
        except servicio.SaldoInsuficiente as error:
            self._descontar_identidad()
            return None, Response(
                SaldoInsuficienteSerializer(stock_app.rechazo_por_saldo(error)).data, status=status.HTTP_409_CONFLICT
            )
        except servicio.SaldoCambio as error:
            return None, _rechazo(
                error, SaldoCambioSerializer, saldo_actual=error.saldo_actual, saldo_visto=error.saldo_visto
            )
        except servicio.StockNoHabilitado as error:
            # La persona se resuelve antes que el estado de la institución y del edificio: este 409 ya dijo que el DNI
            # tiene legajo o figura en el Registro. Sin esto era un oráculo de identidad sin cuota.
            self._descontar_identidad()
            return None, _rechazo(error)
        except servicio.UuidEnUso as error:
            return None, _rechazo(error)
        except PermissionDenied:
            # La capacidad se perdió entre la vista y el servicio (lo sacaron del Equipo): 403, no 404, porque el par
            # ya se resolvió por alcance.
            return None, _sin_permiso()
        except ValidationError as error:
            if "dni" in getattr(error, "error_dict", {}):
                self._descontar_identidad()
            return None, _respuesta_de_validacion(_errores(_con_claves_de_la_app(error)))

    def _descontar_identidad(self):
        """La entrega rechazada por la persona, por el saldo o por una institución o un edificio no activos
        (``StockNoHabilitado``) ya consultó el legajo o el Registro y dice si el DNI existe o figura fallecido: gasta de ``personas_campo`` como el «DNI ya registrado» de ``crear_caso``. La
        asentada no gasta; agotada la cuota, contesta 429."""

        if not self.gasta_cuota_de_identidad:
            return
        espera = descontar_consulta_de_identidad(self.request)
        if espera is not None:
            raise Throttled(wait=espera)

    @staticmethod
    def _sin_datos(error):
        mensaje = error.messages[0]
        return Response(
            {
                "detail": mensaje,
                "code": CODIGO_PERSONA_SIN_DATOS,
                "non_field_errors": [mensaje],
                "pide_sexo": error.pide_sexo,
                "motivo": error.motivo,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )


_RESPUESTAS = {
    201: _OPERACION,
    200: _OPERACION,
    400: _VALIDACION,
    401: _SIN_TOKEN,
    403: _SIN_PERMISO,
    404: _FUERA_DE_ALCANCE,
    409: _CONFLICTOS,
    429: OpenApiResponse(
        description="Tope de escrituras de stock del usuario (`stock_escritura`). Trae `Retry-After`."
    ),
}


class EntregaAPersonaView(_EscrituraDeStockView):
    envio = EntregaAPersonaEnvioSerializer
    gasta_cuota_de_identidad = True

    def puede(self, usuario, dispositivo, edificio_id):
        return servicio.puede_entregar(usuario, dispositivo, edificio_id)

    def asentar(self, usuario, dispositivo, edificio, datos):
        return servicio.entregar_a_persona(
            usuario,
            dispositivo,
            edificio,
            datos["dni"],
            datos["lineas"],
            sexo=datos["sexo"],
            nombre=datos["nombre"],
            apellido=datos["apellido"],
            observacion=datos["observacion"],
            uuid_cliente=datos["uuid_cliente"],
        )

    @extend_schema(
        request=EntregaAPersonaEnvioSerializer,
        responses=_RESPUESTAS,
        description=(
            "Descuenta insumos del edificio y los asienta a nombre de una persona (`stock.entregar` y `ciudadano.ver`). "
            "La persona sale del legajo, del Registro (con `sexo`) o del alta mínima (con `nombre` y `apellido`); si no "
            "alcanza, 400 `PERSONA_SIN_DATOS`. Nunca deja un saldo negativo: 409 `SALDO_INSUFICIENTE`. **No devuelve "
            "datos de la persona.** Requiere conexión: no se encola."
        ),
    )
    def post(self, request, dispositivo_id, edificio_id):
        return super().post(request, dispositivo_id, edificio_id)


class IngresoManualView(_EscrituraDeStockView):
    envio = IngresoManualEnvioSerializer

    def puede(self, usuario, dispositivo, edificio_id):
        return servicio.puede_ingresar(usuario, dispositivo, edificio_id)

    def asentar(self, usuario, dispositivo, edificio, datos):
        return servicio.ingresar_manual(
            usuario,
            dispositivo,
            edificio,
            datos["lineas"],
            datos["origen"],
            origen_detalle=datos["origen_detalle"],
            comprobante=datos["comprobante"],
            uuid_cliente=datos["uuid_cliente"],
        )

    @extend_schema(
        request=IngresoManualEnvioSerializer,
        responses=_RESPUESTAS,
        description=(
            "Suma stock cargado a mano —donación, compra…— al edificio (`stock.ingresar`). Solo insumos activos, con "
            "la institución activa y el edificio activo. Requiere conexión: no se encola."
        ),
    )
    def post(self, request, dispositivo_id, edificio_id):
        return super().post(request, dispositivo_id, edificio_id)


class TraspasoView(_EscrituraDeStockView):
    envio = TraspasoEnvioSerializer

    def puede(self, usuario, dispositivo, edificio_id):
        return servicio.puede_ingresar(usuario, dispositivo, edificio_id)

    def asentar(self, usuario, dispositivo, edificio, datos):
        return servicio.traspasar(
            usuario,
            dispositivo,
            edificio,
            datos["destino_dispositivo_id"],
            datos["destino_edificio_id"],
            datos["lineas"],
            observacion=datos["observacion"],
            uuid_cliente=datos["uuid_cliente"],
        )

    @extend_schema(
        request=TraspasoEnvioSerializer,
        responses=_RESPUESTAS,
        description=(
            "Pasa insumos de este edificio a otro par de `destinos-traspaso/` (`stock.ingresar` en el origen y en el "
            "destino). Inmediato: el destino no confirma. Un destino inexistente, no vinculado o fuera de alcance "
            "contesta lo mismo: 400 con `destino`. El cuerpo trae solo la salida del origen."
        ),
    )
    def post(self, request, dispositivo_id, edificio_id):
        return super().post(request, dispositivo_id, edificio_id)


class AjusteView(_EscrituraDeStockView):
    envio = AjusteEnvioSerializer

    def puede(self, usuario, dispositivo, edificio_id):
        return servicio.puede_ajustar(usuario, dispositivo, edificio_id)

    def asentar(self, usuario, dispositivo, edificio, datos):
        return servicio.ajustar(
            usuario,
            dispositivo,
            edificio,
            datos["item_id"],
            datos["cantidad_contada"],
            datos["saldo_visto"],
            datos["motivo"],
            detalle=datos["detalle"],
            uuid_cliente=datos["uuid_cliente"],
        )

    @extend_schema(
        request=AjusteEnvioSerializer,
        responses=_RESPUESTAS,
        description=(
            "Lleva el saldo de un insumo a lo **contado** (`stock.ajustar`); el sistema calcula la diferencia. Si el "
            "saldo ya no es `saldo_visto`: 409 `SALDO_CAMBIO` con `saldo_actual`. Contar lo mismo que hay es 400. "
            "Se permite con la institución no activa, y entonces solo hacia abajo."
        ),
    )
    def post(self, request, dispositivo_id, edificio_id):
        return super().post(request, dispositivo_id, edificio_id)
