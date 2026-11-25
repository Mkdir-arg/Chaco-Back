"""API de campo, acciones de cama (Cambio 598): reservar, prestar, liberar, sacar de servicio y volver a servicio.

Paridad con las vistas del mapa del backoffice (``PlazaReservarView`` y hermanas): cada vista
llama a la **misma** función de ``services.estadias`` y solo traduce lo que contesta. Quién ve qué
es el alcance de siempre: no hay reglas nuevas.

* Plaza inexistente, de un sector dado de baja o de un edificio fuera del alcance del usuario: **404**,
  el mismo cuerpo para las tres (no se distingue «no existe» de «no es tuya»).
* Sin la capacidad de la acción (``dispositivo.admitir`` para reservar, prestar y liberar;
  ``dispositivo.editar`` para sacar y volver a servicio; ``ciudadano.ver`` además para reservar y
  prestar, que buscan a la persona por DNI): **403** ``SIN_PERMISO``.
* La plaza no está en un estado que admita la acción (``acciones_de_plaza`` no la ofrece): **400** con el
  motivo de ``bloqueo_de_plaza`` si lo hay.
* Persona inexistente al reservar o prestar: **400** ``PERSONA_NO_ENCONTRADA``.
* ``ValidationError`` del servicio: **400** ``VALIDACION`` por campo.

Sacar de servicio y volver a servicio son idempotentes, como en la web: si la plaza ya estaba como se
la pide, contestan 200 sin cambiar nada.
"""

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.response import Response

from core import rbac
from programas.api.serializers_emergencia_plazas_acciones import (
    FueraDeServicioEnvioSerializer,
    LiberarPlazaEnvioSerializer,
    PrestarPlazaEnvioSerializer,
    ReservarPlazaEnvioSerializer,
)
from programas.api.views_emergencia import _SIN_TOKEN, _400, _respuesta_de_validacion, _VistaDeCampo
from programas.models import Plaza, ReservaPlaza
from programas.services.dispositivos import CAP_EDITAR, CAP_VER, puede_operar_plaza, q_edificios_en_alcance
from programas.services.estadias import (
    CAP_ADMITIR,
    liberar_reserva,
    reserva_abierta_de,
    reservar_plaza,
    sacar_plaza_de_servicio,
    volver_plaza_a_servicio,
)
from programas.services.ingreso import buscar_ciudadano_por_dni
from programas.services.ocupacion import estado_de_plazas
from programas.services.sectores_plazas import (
    ACCION_FUERA_SERVICIO,
    ACCION_LIBERAR,
    ACCION_PRESTAR,
    ACCION_RESERVAR,
    ACCION_VOLVER,
    acciones_de_plaza,
    bloqueo_de_plaza,
)

CAP_VER_CIUDADANO = "ciudadano.ver"

CODIGO_SIN_PERMISO = "SIN_PERMISO"
CODIGO_PERSONA_NO_ENCONTRADA = "PERSONA_NO_ENCONTRADA"
MENSAJE_SIN_PERMISO = "No tenés permiso para hacer esto con esta plaza."
MENSAJE_PERSONA_NO_ENCONTRADA = "No encontramos a nadie con ese DNI: dala de alta desde Ingresar persona."

_FRASES = {
    ACCION_RESERVAR: "reservarse",
    ACCION_PRESTAR: "prestarse",
    ACCION_LIBERAR: "liberarse",
    ACCION_FUERA_SERVICIO: "sacarse de servicio",
    ACCION_VOLVER: "volver a servicio",
}

_SIN_PERMISO = OpenApiResponse(
    description=(
        "`code: SIN_PERMISO`: el usuario ve la plaza pero no tiene la capacidad de la acción "
        "(`dispositivo.admitir`, `dispositivo.editar` o, para reservar y prestar, `ciudadano.ver`)."
    )
)
_AJENA = OpenApiResponse(description="La plaza no existe o es de un edificio fuera del alcance del usuario.")
_MAPA = OpenApiResponse(description="`{ok: true, mapa}`: el mapa del edificio de la plaza, ya actualizado.")


def _sin_capacidad():
    return Response({"detail": MENSAJE_SIN_PERMISO, "code": CODIGO_SIN_PERMISO}, status=status.HTTP_403_FORBIDDEN)


def _persona_no_encontrada():
    return Response(
        {
            "detail": MENSAJE_PERSONA_NO_ENCONTRADA,
            "code": CODIGO_PERSONA_NO_ENCONTRADA,
            "dni": [MENSAJE_PERSONA_NO_ENCONTRADA],
        },
        status=status.HTTP_400_BAD_REQUEST,
    )


def _respuesta_con_mapa(request, plaza):
    """Lo que contesta toda acción: ``{"ok": true, "mapa": {...}}``.

    TODO(596): ``mapa`` es el cuerpo de ``GET dispositivos/<d>/edificios/<e>/mapa/``, que arma
    ``mapa_del_edificio(user, dispositivo, edificio)`` en el PR 596. Mientras no esté integrado va ``None``;
    este es el único lugar que lo conecta.
    """
    return Response({"ok": True, "mapa": None})


class _AccionDeCamaView(_VistaDeCampo):
    """Base de las cinco acciones: resuelve la plaza por alcance, exige la capacidad y la oferta del estado."""

    accion = None
    capacidad = None
    envio = None
    #: Reservar y prestar buscan a la persona por DNI en el padrón: piden también `ciudadano.ver`.
    requiere_ver_ciudadanos = False

    def _plaza(self, request, pk):
        """La plaza **si el usuario la ve**; si no, el 404 de siempre. Con el sector y el dispositivo ya traídos."""
        return self._o_404(
            Plaza.objects.select_related("sector__dispositivo").filter(
                q_edificios_en_alcance(request.user, CAP_VER, "sector__dispositivo_id", "sector__edificio_id"),
                sector__activo=True,
            ),
            pk,
        )

    def _puede(self, request, plaza):
        if not puede_operar_plaza(request.user, plaza.sector.dispositivo, plaza, self.capacidad):
            return False
        return not self.requiere_ver_ciudadanos or rbac.puede(request.user, CAP_VER_CIUDADANO)

    def _ya_estaba(self, plaza):
        """Para las acciones idempotentes: ¿la plaza ya está como se la pide?"""
        return False

    def _rechazo_de_estado(self, plaza):
        """El 400 con el motivo si el estado de la plaza no admite la acción, o ``None``.

        La capacidad ya se exigió: acá se pregunta solo qué admite la plaza (estado, reserva abierta y
        estado de la institución), con las capacidades en alto.
        """
        estado = estado_de_plazas([plaza], puede_ver_personas=False)[plaza.pk]
        ofrecidas = acciones_de_plaza(
            estado,
            reserva_abierta_de(plaza) is not None,
            puede_admitir=True,
            puede_editar=True,
            puede_buscar_personas=True,
            puede_egresar=False,
            estado_dispositivo=plaza.sector.dispositivo.estado,
        )
        # «Sacar de servicio» una plaza ocupada sí se ofrece (deshabilitada, con su motivo): acá se rechaza.
        motivo = bloqueo_de_plaza(estado, self.accion)
        if not motivo and self.accion in ofrecidas:
            return None
        motivo = motivo or f"Esta plaza no puede {_FRASES[self.accion]} ahora."
        return _respuesta_de_validacion({"estado": [motivo]})

    def post(self, request, pk):
        plaza = self._plaza(request, pk)
        if not self._puede(request, plaza):
            return _sin_capacidad()
        datos = {}
        if self.envio is not None:
            datos, error = self._entrada(self.envio, request)
            if error is not None:
                return error
        if not self._ya_estaba(plaza):
            rechazo = self._rechazo_de_estado(plaza)
            if rechazo is not None:
                return rechazo
        rechazo = self._ejecutar_accion(request, plaza, datos)
        if rechazo is not None:
            return rechazo
        return _respuesta_con_mapa(request, plaza)

    def _ejecutar_accion(self, request, plaza, datos):
        """Corre el servicio. ``None`` si salió bien; si no, la respuesta de error."""
        raise NotImplementedError


class _ReservaDeCamaView(_AccionDeCamaView):
    capacidad = CAP_ADMITIR
    requiere_ver_ciudadanos = True
    tipo = ReservaPlaza.Tipo.RESERVA

    def _ejecutar_accion(self, request, plaza, datos):
        ciudadano = buscar_ciudadano_por_dni(datos["dni"])
        if ciudadano is None:
            return _persona_no_encontrada()
        _, respuesta = self._ejecutar(
            lambda: reservar_plaza(
                plaza=plaza,
                ciudadano=ciudadano,
                usuario=request.user,
                tipo=self.tipo,
                desde=datos.get("desde"),
                hasta=datos.get("hasta"),
                motivo=datos.get("motivo", ""),
            ),
            sin_permiso=_sin_capacidad(),
        )
        return respuesta


class ReservarPlazaView(_ReservaDeCamaView):
    accion = ACCION_RESERVAR
    envio = ReservarPlazaEnvioSerializer

    @extend_schema(
        request=ReservarPlazaEnvioSerializer,
        responses={
            200: _MAPA,
            400: _400("`PERSONA_NO_ENCONTRADA` si el DNI no está en el Legajo."),
            401: _SIN_TOKEN,
            403: _SIN_PERMISO,
            404: _AJENA,
        },
        description=(
            "Guarda la plaza disponible para una persona del Legajo, buscada por DNI (la de «Reservar» del "
            "backoffice). Pide `dispositivo.admitir` y `ciudadano.ver`."
        ),
    )
    def post(self, request, pk):
        return super().post(request, pk)


class PrestarPlazaView(_ReservaDeCamaView):
    accion = ACCION_PRESTAR
    envio = PrestarPlazaEnvioSerializer
    tipo = ReservaPlaza.Tipo.PRESTAMO

    @extend_schema(
        request=PrestarPlazaEnvioSerializer,
        responses={
            200: _MAPA,
            400: _400("`hasta` es obligatorio; `PERSONA_NO_ENCONTRADA` si el DNI no está."),
            401: _SIN_TOKEN,
            403: _SIN_PERMISO,
            404: _AJENA,
        },
        description="Presta la plaza hasta `hasta` (obligatorio). Pide `dispositivo.admitir` y `ciudadano.ver`.",
    )
    def post(self, request, pk):
        return super().post(request, pk)


class LiberarPlazaView(_AccionDeCamaView):
    accion = ACCION_LIBERAR
    capacidad = CAP_ADMITIR
    envio = LiberarPlazaEnvioSerializer

    def _ejecutar_accion(self, request, plaza, datos):
        # La reserva se busca de nuevo y no viaja en el pedido: entre que el mapa se dibujó y el envío,
        # un ingreso pudo consumirla. `liberar_reserva` la relee con la fila bloqueada.
        reserva = reserva_abierta_de(plaza)
        if reserva is None:
            return _respuesta_de_validacion(
                {"estado": ["La plaza ya no tiene una reserva ni un préstamo sin liberar."]}
            )
        _, respuesta = self._ejecutar(
            lambda: liberar_reserva(reserva=reserva, usuario=request.user, motivo=datos.get("motivo", "")),
            sin_permiso=_sin_capacidad(),
        )
        return respuesta

    @extend_schema(
        request=LiberarPlazaEnvioSerializer,
        responses={
            200: _MAPA,
            400: _400("La plaza no tiene reserva ni préstamo."),
            401: _SIN_TOKEN,
            403: _SIN_PERMISO,
            404: _AJENA,
        },
        description="Suelta la reserva o el préstamo de la plaza. Pide `dispositivo.admitir`.",
    )
    def post(self, request, pk):
        return super().post(request, pk)


class FueraDeServicioView(_AccionDeCamaView):
    accion = ACCION_FUERA_SERVICIO
    capacidad = CAP_EDITAR
    envio = FueraDeServicioEnvioSerializer

    def _ya_estaba(self, plaza):
        return plaza.estado == Plaza.Estado.FUERA_SERVICIO

    def _ejecutar_accion(self, request, plaza, datos):
        _, respuesta = self._ejecutar(
            lambda: sacar_plaza_de_servicio(plaza=plaza, usuario=request.user, motivo=datos["motivo"]),
            sin_permiso=_sin_capacidad(),
        )
        return respuesta

    @extend_schema(
        request=FueraDeServicioEnvioSerializer,
        responses={
            200: _MAPA,
            400: _400("Sin motivo, o la plaza está tomada: primero se reubica."),
            401: _SIN_TOKEN,
            403: _SIN_PERMISO,
            404: _AJENA,
        },
        description="Saca la plaza de servicio, con su motivo (obligatorio). Pide `dispositivo.editar`. Idempotente.",
    )
    def post(self, request, pk):
        return super().post(request, pk)


class VolverAServicioView(_AccionDeCamaView):
    accion = ACCION_VOLVER
    capacidad = CAP_EDITAR

    def _ya_estaba(self, plaza):
        return plaza.estado == Plaza.Estado.OPERATIVA

    def _ejecutar_accion(self, request, plaza, datos):
        _, respuesta = self._ejecutar(
            lambda: volver_plaza_a_servicio(plaza=plaza, usuario=request.user), sin_permiso=_sin_capacidad()
        )
        return respuesta

    @extend_schema(
        request=None,
        responses={200: _MAPA, 401: _SIN_TOKEN, 403: _SIN_PERMISO, 404: _AJENA},
        description="Repone la plaza fuera de servicio. Pide `dispositivo.editar`. Idempotente.",
    )
    def post(self, request, pk):
        return super().post(request, pk)
