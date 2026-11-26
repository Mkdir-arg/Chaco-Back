"""API de campo, «Stock» (análisis 010, PR 7a): lectura del stock por edificio, libro, destinos de traspaso y consulta
de persona.

Permiso «stock» (``EmergenciaStockPermission``): abre el módulo **y** ``stock.ver`` en algún edificio de una institución
que lleva stock; sin eso, 403 ``SIN_MODULO``. Qué institución y qué edificio son suyos se resuelve por alcance:
lo ajeno, lo que no existe, lo no vinculado y la institución que no lleva stock contestan el mismo **404**. Ver el
edificio pero no tener la capacidad de la acción (destinos: ``stock.ingresar``; persona: ``stock.entregar`` y
``ciudadano.ver``) es 403 ``SIN_PERMISO``.

Las vistas solo orquestan: las reglas están en ``services.stock`` y el armado en ``services.stock_app``. Toda respuesta
va con ``Cache-Control: no-store``. La consulta de persona expone identidad: descuenta de la cubeta ``personas_campo``
(la misma de la consulta de identidad) y **no escribe** nada.
"""

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response

from core.dni import normalizar_dni
from programas.api.serializers_emergencia_stock import (
    ConsultaDePersonaStockSerializer,
    DestinoDeTraspasoSerializer,
    MovimientosConsultaSerializer,
    PaginaDeMovimientosSerializer,
    StockDelEdificioSerializer,
    StockDelParSerializer,
)
from programas.api.throttles import ConsultaPersonasThrottle
from programas.api.views_emergencia import (
    _SIN_TOKEN,
    CODIGO_SIN_MODULO,
    EmergenciaModuloConStockPermission,
    _respuesta_de_validacion,
    _VistaDeCampo,
)
from programas.services import stock as servicio
from programas.services import stock_app
from programas.services.dispositivos import CAP_STOCK_VER, dispositivos_en_alcance

MENSAJE_SIN_STOCK = (
    "El usuario no lleva stock en ningún dispositivo. "
    "Pedile a quien arma el equipo del dispositivo que te sume con un rol que vea el stock."
)
CODIGO_SIN_PERMISO = "SIN_PERMISO"

_SIN_STOCK = OpenApiResponse(
    description="El usuario no abre el módulo o no tiene `stock.ver` en ningún edificio: `code: SIN_MODULO`."
)
_SIN_PERMISO = OpenApiResponse(
    description="Ve el edificio pero no tiene la capacidad de esta consulta: `code: SIN_PERMISO`."
)
_FUERA_DE_ALCANCE = OpenApiResponse(
    description=(
        "La institución o el edificio no existen, no están vinculados entre sí, no están en el alcance de `stock.ver` "
        "o la institución no lleva stock: todo contesta lo mismo."
    )
)


class EmergenciaStockPermission(BasePermission):
    """Ve el stock de **algún** edificio: ``stock.ver`` con alcance en una institución que lleva stock.

    Va después de ``EmergenciaModuloConStockPermission``. Qué institución y qué edificio son suyos lo decide cada vista, con 404.
    """

    message = {"detail": MENSAJE_SIN_STOCK, "code": CODIGO_SIN_MODULO}

    def has_permission(self, request, view):
        return stock_app.ve_stock(request.user)


def _sin_permiso():
    return Response(
        {"detail": servicio.SIN_PERMISO_DE_STOCK, "code": CODIGO_SIN_PERMISO}, status=status.HTTP_403_FORBIDDEN
    )


class _VistaDeStock(_VistaDeCampo):
    permission_classes = [IsAuthenticated, EmergenciaModuloConStockPermission, EmergenciaStockPermission]

    def finalize_response(self, request, response, *args, **kwargs):
        # Saldos y personas: nada de esto se guarda en una caché intermedia.
        respuesta = super().finalize_response(request, response, *args, **kwargs)
        respuesta["Cache-Control"] = "no-store"
        return respuesta

    def _par(self, request, dispositivo_id, edificio_id):
        """``(dispositivo, edificio)`` en el alcance de ``stock.ver``, de una institución que lleva stock; si no, 404."""

        dispositivo = self._o_404(
            dispositivos_en_alcance(request.user, CAP_STOCK_VER).filter(tipo__maneja_stock=True).select_related("tipo"),
            dispositivo_id,
        )
        edificio = stock_app.edificio_de_stock(request.user, dispositivo, edificio_id)
        if edificio is None:
            raise NotFound
        return dispositivo, edificio


class StockDeLaAppView(_VistaDeStock):
    @extend_schema(
        responses={200: StockDelParSerializer(many=True), 401: _SIN_TOKEN, 403: _SIN_STOCK},
        description=(
            "Los pares institución-edificio con stock que el usuario ve (`stock.ver`), por nombre y sin paginar: solo "
            "instituciones que llevan stock y edificios activos. Cada uno trae cuántos insumos tienen saldo y lo que "
            "el usuario puede hacer ahí (`puede`)."
        ),
    )
    def get(self, request):
        return Response(StockDelParSerializer(stock_app.stock_de_la_app(request.user), many=True).data)


class StockDelEdificioView(_VistaDeStock):
    @extend_schema(
        responses={
            200: StockDelEdificioSerializer,
            401: _SIN_TOKEN,
            403: _SIN_STOCK,
            404: _FUERA_DE_ALCANCE,
        },
        description=(
            "El saldo de un edificio en una institución, por insumo, más los insumos activos que se pueden cargar "
            "y lo que el usuario puede hacer (`puede`). Un insumo desactivado con saldo 0 no se lista."
        ),
    )
    def get(self, request, dispositivo_id, edificio_id):
        dispositivo, edificio = self._par(request, dispositivo_id, edificio_id)
        return Response(
            StockDelEdificioSerializer(stock_app.stock_del_edificio(request.user, dispositivo, edificio)).data
        )


class MovimientosDelEdificioView(_VistaDeStock):
    @extend_schema(
        parameters=[
            OpenApiParameter("tipo", str, description="Un tipo de movimiento (`INGRESO_KIT`, `ENTREGA_PERSONA`…)."),
            OpenApiParameter("item", int, description="Solo los de ese insumo."),
            OpenApiParameter("cursor", int, description="El `siguiente` de la página anterior."),
        ],
        responses={
            200: PaginaDeMovimientosSerializer,
            400: OpenApiResponse(description="`code: VALIDACION`: `tipo`, `item` o `cursor` inválidos."),
            401: _SIN_TOKEN,
            403: _SIN_STOCK,
            404: _FUERA_DE_ALCANCE,
        },
        description=(
            "El libro del edificio, de a 50, del más nuevo al más viejo. No nombra a la persona de una entrega ni a "
            "otra institución en un traspaso."
        ),
    )
    def get(self, request, dispositivo_id, edificio_id):
        dispositivo, edificio = self._par(request, dispositivo_id, edificio_id)
        consulta = MovimientosConsultaSerializer(data=request.query_params)
        if not consulta.is_valid():
            return _respuesta_de_validacion(consulta.errors)
        filtros = consulta.validated_data
        filas, siguiente = stock_app.movimientos_del_edificio(
            dispositivo, edificio, filtros["tipo"], filtros["item"], filtros["cursor"]
        )
        return Response(PaginaDeMovimientosSerializer({"resultados": filas, "siguiente": siguiente}).data)


class DestinosDeTraspasoView(_VistaDeStock):
    @extend_schema(
        responses={
            200: DestinoDeTraspasoSerializer(many=True),
            401: _SIN_TOKEN,
            403: _SIN_PERMISO,
            404: _FUERA_DE_ALCANCE,
        },
        description=(
            "Los pares institución-edificio a los que el usuario puede traspasar desde este edificio: dentro del "
            "alcance de su `stock.ingresar`, activos y que llevan stock. Exige `stock.ingresar` sobre el origen."
        ),
    )
    def get(self, request, dispositivo_id, edificio_id):
        dispositivo, edificio = self._par(request, dispositivo_id, edificio_id)
        destinos, respuesta = self._ejecutar(
            lambda: stock_app.destinos_del_traspaso(request.user, dispositivo, edificio), sin_permiso=_sin_permiso()
        )
        if respuesta is not None:
            return respuesta
        return Response(DestinoDeTraspasoSerializer(destinos, many=True).data)


class PersonaDelStockView(_VistaDeStock):
    """A quién se le va a entregar y qué recibió antes. Expone identidad: cubeta ``personas_campo`` y sin escribir."""

    throttle_classes = [ConsultaPersonasThrottle]

    def check_throttles(self, request):
        # La cubeta se descuenta en ``get``, **después** del alcance, del DNI y del permiso: ni un 404, ni un 400 ni un
        # 403 consultan el padrón, así que no la gastan (y un 429 no tapa el 403 de quien no puede entregar).
        return None

    @extend_schema(
        parameters=[
            OpenApiParameter("dni", str, description="El DNI de la persona."),
            OpenApiParameter("sexo", str, description="`F` o `M`: con él se consulta al Registro si no hay legajo."),
        ],
        responses={
            200: ConsultaDePersonaStockSerializer,
            400: OpenApiResponse(
                description="`code: VALIDACION`: falta el DNI, no es válido, sexo inválido o fallecida."
            ),
            401: _SIN_TOKEN,
            403: _SIN_PERMISO,
            404: _FUERA_DE_ALCANCE,
            429: OpenApiResponse(
                description="Se superó el tope de consultas de identidad del usuario (`personas_campo`, compartido)."
            ),
        },
        description=(
            "La persona (del legajo o, con `sexo`, del Registro) y sus últimas entregas de insumos en toda la red; "
            "otra institución figura como «Otra institución». **No escribe**: no da de alta a nadie. `persona: null` "
            "si no alcanza para identificarla. Exige `stock.entregar` y `ciudadano.ver` sobre el edificio y descuenta "
            "de la cubeta de consultas de identidad."
        ),
    )
    def get(self, request, dispositivo_id, edificio_id):
        dispositivo, edificio = self._par(request, dispositivo_id, edificio_id)
        parametros = request.query_params
        if not normalizar_dni(parametros.get("dni", "")):
            return _respuesta_de_validacion({"dni": ["Indicá el DNI de la persona."]})
        if not servicio.puede_entregar(request.user, dispositivo, edificio.pk):
            return _sin_permiso()
        super().check_throttles(request)
        cuerpo, respuesta = self._ejecutar(
            lambda: stock_app.persona_del_stock(
                request.user, dispositivo, edificio, parametros.get("dni", ""), parametros.get("sexo", "")
            ),
            sin_permiso=_sin_permiso(),
        )
        if respuesta is not None:
            return respuesta
        return Response(ConsultaDePersonaStockSerializer(cuerpo).data)
