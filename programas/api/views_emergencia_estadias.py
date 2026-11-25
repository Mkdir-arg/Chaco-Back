"""API de campo: egreso por persona y cambio de plaza de una estadía (Cambio 597).

Vale para cualquier dispositivo y edificio, con el alcance de siempre (Cambio 523): una estadía de un
edificio que el usuario no ve, o inexistente, es un **404**; verla pero no tener la capacidad de la acción
(``dispositivo.egresar`` / ``dispositivo.admitir``) es un **403**. Las vistas solo orquestan:
``estadias.egresar_persona`` y ``estadias.cambiar_plaza`` son las de la web, con sus mismas reglas.

Si el tipo del dispositivo pide un formulario de egreso, el egreso se registra desde el backoffice
(409 ``EGRESO_CON_FORMULARIO``): la app no dibuja formularios de tipo.
"""

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.response import Response

from programas.api.serializers_emergencia_estadias import (
    AccionDeEstadiaSerializer,
    CambiarPlazaEnvioSerializer,
    EgresarEnvioSerializer,
    MotivoEgresoSerializer,
    PlazasParaCambioSerializer,
)
from programas.api.serializers_emergencia_plazas import MapaDelEdificioSerializer
from programas.api.views_emergencia import _SIN_MODULO, _SIN_TOKEN, _respuesta_de_validacion, _VistaDeCampo
from programas.models import Estadia, MomentoFormulario, MotivoEgreso, Plaza
from programas.services.dispositivos import puede_operar_plaza, q_edificios_en_alcance
from programas.services.edificio_operativo import edificio_de_la_institucion
from programas.services.estadias import CAP_ADMITIR, CAP_EGRESAR, asignar_plaza, cambiar_plaza, egresar_persona
from programas.services.ingreso import plazas_para_ingresar
from programas.services.plazas_app import mapa_del_edificio
from programas.services.respuestas_dispositivo import formulario_vigente

CAP_VER = "dispositivo.ver"
CODIGO_EGRESO_CON_FORMULARIO = "EGRESO_CON_FORMULARIO"
MENSAJE_EGRESO_CON_FORMULARIO = "Este egreso se registra desde el backoffice."
MENSAJE_SIN_EGRESAR = "No tenés permiso para registrar egresos en este dispositivo."
MENSAJE_SIN_CAMBIAR = "No tenés permiso para cambiar de plaza a personas de este dispositivo."

_AJENA = OpenApiResponse(description="La estadía no existe o es de un edificio que el usuario no ve.")
_SIN_CAPACIDAD = OpenApiResponse(description="Ve la estadía pero no tiene la capacidad de la acción.")


def _mapa_actualizado(request, dispositivo, edificio_id):
    """El mapa del edificio indicado, para que la app repinte sin otro pedido (``None`` si no hay edificio)."""
    if edificio_id is None:
        return None
    edificio = edificio_de_la_institucion(request.user, dispositivo, edificio_id)
    if edificio is None:
        return None
    return MapaDelEdificioSerializer(mapa_del_edificio(request.user, dispositivo, edificio)).data


class _VistaDeEstadia(_VistaDeCampo):
    def _estadia(self, request, pk):
        """La estadía de un edificio que el usuario ve, o 404 (el mismo cuerpo exista o no)."""
        consulta = Estadia.objects.select_related("ciudadano", "dispositivo__tipo", "plaza__sector").filter(
            q_edificios_en_alcance(request.user, CAP_VER, "dispositivo_id", "plaza__sector__edificio_id")
        )
        return self._o_404(consulta, pk)

    @staticmethod
    def _sin_capacidad(mensaje):
        return Response({"detail": mensaje, "code": "SIN_PERMISO"}, status=status.HTTP_403_FORBIDDEN)


class MotivosEgresoView(_VistaDeCampo):
    @extend_schema(
        responses={200: MotivoEgresoSerializer(many=True), 401: _SIN_TOKEN, 403: _SIN_MODULO},
        description="El catálogo de motivos de egreso vigentes (`activo`), en el orden del backoffice.",
    )
    def get(self, request):
        motivos = MotivoEgreso.objects.filter(activo=True).values("id", "nombre")
        return Response(MotivoEgresoSerializer(motivos, many=True).data)


class EgresarEstadiaView(_VistaDeEstadia):
    @extend_schema(
        request=EgresarEnvioSerializer,
        responses={
            200: AccionDeEstadiaSerializer,
            400: OpenApiResponse(description="Motivo, destino, fecha o estado inválidos (`code: VALIDACION`)."),
            401: _SIN_TOKEN,
            403: _SIN_CAPACIDAD,
            404: _AJENA,
            409: OpenApiResponse(description="El tipo pide formulario de egreso: `code: EGRESO_CON_FORMULARIO`."),
        },
        description="Registra el egreso de **una** persona (`egresar_persona`). `fecha_egreso` vacía = ahora.",
    )
    def post(self, request, pk):
        estadia = self._estadia(request, pk)
        if not puede_operar_plaza(request.user, estadia.dispositivo, estadia.plaza_id, CAP_EGRESAR):
            return self._sin_capacidad(MENSAJE_SIN_EGRESAR)
        if formulario_vigente(estadia.dispositivo.tipo_id, MomentoFormulario.EGRESO) is not None:
            return Response(
                {"detail": MENSAJE_EGRESO_CON_FORMULARIO, "code": CODIGO_EGRESO_CON_FORMULARIO},
                status=status.HTTP_409_CONFLICT,
            )
        datos, error = self._entrada(EgresarEnvioSerializer, request)
        if error is not None:
            return error
        edificio_id = estadia.plaza.sector.edificio_id if estadia.plaza_id else None
        motivo = (
            MotivoEgreso.objects.filter(pk=datos["motivo_egreso_id"]).first() if datos["motivo_egreso_id"] else None
        )

        _, respuesta = self._ejecutar(
            lambda: egresar_persona(
                estadia=estadia,
                usuario=request.user,
                fecha_egreso=datos["fecha_egreso"],
                motivo=datos["observaciones"],
                motivo_egreso=motivo,
                destino=datos["destino"],
                pertenencias_devueltas=datos["pertenencias_devueltas"],
            ),
            sin_permiso=self._sin_capacidad(MENSAJE_SIN_EGRESAR),
        )
        if respuesta is not None:
            return respuesta
        return Response({"ok": True, "mapa": _mapa_actualizado(request, estadia.dispositivo, edificio_id)})


class PlazasParaCambioView(_VistaDeEstadia):
    @extend_schema(
        responses={200: PlazasParaCambioSerializer, 401: _SIN_TOKEN, 403: _SIN_CAPACIDAD, 404: _AJENA},
        description="Las plazas libres del dispositivo a las que se puede mover la persona, por sector.",
    )
    def get(self, request, pk):
        estadia = self._estadia(request, pk)
        if not puede_operar_plaza(request.user, estadia.dispositivo, estadia.plaza_id, CAP_ADMITIR):
            return self._sin_capacidad(MENSAJE_SIN_CAMBIAR)
        sectores, _ = plazas_para_ingresar(estadia.dispositivo, usuario=request.user)
        libres_por_sector = [
            (item, [p for p in item["plazas"] if p["disponible"] and p["pk"] != estadia.plaza_id]) for item in sectores
        ]
        tipos = dict(
            Plaza.objects.filter(pk__in=[p["pk"] for _item, libres in libres_por_sector for p in libres]).values_list(
                "pk", "tipo"
            )
        )
        cuerpo = []
        for item, plazas in libres_por_sector:
            libres = [{"id": p["pk"], "codigo": p["codigo"], "tipo": tipos[p["pk"]]} for p in plazas]
            if libres:
                cuerpo.append({"id": item["sector"].pk, "nombre": item["sector"].nombre, "plazas": libres})
        return Response({"sectores": cuerpo})


class CambiarPlazaEstadiaView(_VistaDeEstadia):
    @extend_schema(
        request=CambiarPlazaEnvioSerializer,
        responses={
            200: AccionDeEstadiaSerializer,
            400: OpenApiResponse(description="Plaza ocupada o inexistente, motivo vacío (`code: VALIDACION`)."),
            401: _SIN_TOKEN,
            403: _SIN_CAPACIDAD,
            404: _AJENA,
        },
        description=(
            "Mueve a la persona a otra plaza **del mismo dispositivo** (`cambiar_plaza`). Si la estadía no "
            "tenía plaza, se la asigna (`asignar_plaza`, motivo opcional), como la web."
        ),
    )
    def post(self, request, pk):
        estadia = self._estadia(request, pk)
        datos, error = self._entrada(CambiarPlazaEnvioSerializer, request)
        if error is not None:
            return error
        plaza = None
        if datos["plaza_id"]:
            sectores, _ = plazas_para_ingresar(estadia.dispositivo, usuario=request.user)
            elegibles = {p["pk"] for item in sectores for p in item["plazas"]}
            if datos["plaza_id"] in elegibles:
                plaza = (
                    Plaza.objects.select_related("sector")
                    .filter(pk=datos["plaza_id"], sector__dispositivo=estadia.dispositivo)
                    .first()
                )
        if plaza is None:
            return _respuesta_de_validacion({"plaza_id": ["Elegí la plaza a la que se mueve la persona."]})
        mover = asignar_plaza if estadia.plaza_id is None else cambiar_plaza
        _, respuesta = self._ejecutar(
            lambda: mover(estadia=estadia, plaza=plaza, usuario=request.user, motivo=datos["motivo"]),
            sin_permiso=self._sin_capacidad(MENSAJE_SIN_CAMBIAR),
        )
        if respuesta is not None:
            return respuesta
        return Response({"ok": True, "mapa": _mapa_actualizado(request, estadia.dispositivo, plaza.sector.edificio_id)})
