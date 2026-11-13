"""API de campo de Emergencia, M3: recepción de kits, y «mis dispositivos» de la guardia.

`EmergenciaRecibirKitPermission` es «recibe kits en algún dispositivo» (``kits.recibe_kits``):
sin eso, 403 ``SIN_MODULO``. Con la capacidad pero sin alcance sobre **ese** dispositivo o
**esa** entrega, **404**, igual que un id inexistente (plan §2, C2). `recibir_entrega` es la
misma función que usa la recepción web: la vista solo traduce lo que rechaza
(``_VistaDeCampo._ejecutar``).

La base, los permisos y los traductores están en ``views_emergencia``.
"""

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from programas.api.serializers_emergencia import (
    EntregaKitSerializer,
    EstadoCambioSerializer,
    MiDispositivoEmergenciaSerializer,
    RecepcionKitEnvioSerializer,
    RecepcionKitRespuestaSerializer,
)
from programas.api.views_emergencia import (
    _SIN_MODULO,
    _SIN_TOKEN,
    EmergenciaModuloPermission,
    EmergenciaRecibirKitPermission,
    _respuesta_de_validacion,
    _VistaDeCampo,
)
from programas.selectors import emergencia_alojar as selectores_alojar
from programas.selectors import kits as selectores_kits
from programas.services import kits as servicio_kits
from programas.services.dispositivos import dispositivos_en_alcance
from programas.services.emergencia_programa import CAP_ADMITIR, CAP_RECIBIR_KIT

#: Tope de lo que devuelve la lista de un dispositivo cuando no se piden solo las pendientes.
TOPE_ENTREGAS = 50

_SIN_RECIBIR_KIT = OpenApiResponse(
    description=(
        "El usuario no abre el módulo o no tiene `emergencia.recibir_kit` en el Equipo de ningún dispositivo: "
        "`code: SIN_MODULO`."
    )
)
_FUERA_DE_ALCANCE = OpenApiResponse(
    description=(
        "No existe, o es de un dispositivo donde el usuario no recibe kits: las dos cosas contestan lo mismo, "
        "sin nombrar al dispositivo."
    )
)


class MisDispositivosEmergenciaView(_VistaDeCampo):
    @extend_schema(
        responses={200: MiDispositivoEmergenciaSerializer(many=True), 401: _SIN_TOKEN, 403: _SIN_MODULO},
        description=(
            "Los dispositivos donde el usuario es de la guardia de Emergencia (`dispositivo.admitir` o "
            "`emergencia.recibir_kit` con alcance), por nombre y sin paginar: con más de uno, la app pide elegir "
            "primero. `entregas_pendientes` cuenta lo que ese usuario puede recibir ahí; `plazas_libres` y "
            "`derivaciones_pendientes`, lo de «Llegada de familias» donde admite (0 donde solo recibe kits)."
        ),
    )
    def get(self, request):
        filas = selectores_kits.mis_dispositivos(request.user)
        if filas:
            resumen = selectores_alojar.resumen_de_llegadas(dispositivos_en_alcance(request.user, CAP_ADMITIR))
            for fila in filas:
                fila.update(resumen.get(fila["id"], {"plazas_libres": 0, "derivaciones_pendientes": 0}))
        return Response(MiDispositivoEmergenciaSerializer(filas, many=True).data)


class _VistaDeKits(_VistaDeCampo):
    """Base de M3: token (o sesión), el módulo abierto y recibir kits en algún dispositivo."""

    permission_classes = [IsAuthenticated, EmergenciaModuloPermission, EmergenciaRecibirKitPermission]

    def _entrega(self, request, pk):
        """La entrega, **si es de un dispositivo donde recibe kits**. La de otro es un 404 (RN-4.8)."""
        return self._o_404(selectores_kits.entregas_al_alcance(request.user), pk)


class EntregasDelDispositivoView(_VistaDeKits):
    @extend_schema(
        parameters=[
            OpenApiParameter(
                "pendientes",
                bool,
                description="`1`: solo las que todavía se pueden recibir (en camino o preparadas), de la más vieja.",
            )
        ],
        responses={
            200: EntregaKitSerializer(many=True),
            401: _SIN_TOKEN,
            403: _SIN_RECIBIR_KIT,
            404: _FUERA_DE_ALCANCE,
        },
        description=(
            "Las entregas de kits de un dispositivo donde el usuario recibe kits. Con `?pendientes=1`, las que "
            "esperan recepción; sin él, las últimas 50 de cualquier estado, de la más nueva a la más vieja."
        ),
    )
    def get(self, request, dispositivo_id):
        dispositivo = self._o_404(dispositivos_en_alcance(request.user, CAP_RECIBIR_KIT), dispositivo_id)
        if request.query_params.get("pendientes") in ("1", "true", "True"):
            entregas = selectores_kits.entregas_pendientes_de(dispositivo, request.user)
        else:
            entregas = selectores_kits.entregas_de(dispositivo)[:TOPE_ENTREGAS]
        return Response(EntregaKitSerializer(entregas, many=True).data)


class EntregaKitDetalleView(_VistaDeKits):
    @extend_schema(
        responses={200: EntregaKitSerializer, 401: _SIN_TOKEN, 403: _SIN_RECIBIR_KIT, 404: _FUERA_DE_ALCANCE},
        description="Una entrega de un dispositivo donde el usuario recibe kits, con sus líneas.",
    )
    def get(self, request, pk):
        return Response(EntregaKitSerializer(self._entrega(request, pk)).data)


class RecibirEntregaKitView(_VistaDeKits):
    """La recepción: lo que llegó de cada ítem, el remito y una observación."""

    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @extend_schema(
        request={"multipart/form-data": RecepcionKitEnvioSerializer},
        responses={
            200: RecepcionKitRespuestaSerializer,
            400: OpenApiResponse(
                description=(
                    "La recepción no es válida. Trae `code: VALIDACION`, `detail` legible y el detalle por campo: "
                    "falta `uuid_cliente`, falta la cantidad de algún ítem o no es un entero ≥ 0 (`cantidades`), "
                    "falta el remito, no es JPEG o pasa de 5 MB (`remito`)."
                )
            ),
            401: _SIN_TOKEN,
            403: _SIN_RECIBIR_KIT,
            404: _FUERA_DE_ALCANCE,
            409: OpenApiResponse(
                response=EstadoCambioSerializer,
                description=(
                    "La entrega ya fue recibida —desde otro teléfono o desde el backoffice— o la mesa la canceló: "
                    "`detail` dice qué pasó y `estado_actual` en qué estado quedó. Con `code: UUID_EN_USO`, ese "
                    "`uuid_cliente` ya es el de la recepción de otra entrega."
                ),
            ),
        },
        description=(
            "Confirma la recepción de una entrega en camino (o preparada: vale aunque la mesa no la haya marcado). "
            "Idempotente por `uuid_cliente`: el reenvío del mismo devuelve 200 con el resultado de la primera vez, "
            "sin validar ni escribir nada. Requiere conexión: no se encola."
        ),
    )
    def post(self, request, pk):
        entrega = self._entrega(request, pk)
        entrada = RecepcionKitEnvioSerializer(data=request.data)
        if not entrada.is_valid():
            return _respuesta_de_validacion(entrada.errors)
        recibida, respuesta = self._ejecutar(
            lambda: servicio_kits.recibir_entrega(
                entrega,
                request.user,
                entrada.cantidades_por_item(),
                entrada.validated_data["remito"],
                observacion=entrada.validated_data["observacion"],
                uuid_cliente=entrada.validated_data["uuid_cliente"],
            )
        )
        if respuesta is not None:
            return respuesta
        diferencias = selectores_kits.diferencias_de(selectores_kits.lineas_de(recibida))
        cuerpo = {
            "estado": recibida.estado,
            "diferencias": [
                {"item": d["item"], "enviada": d["enviada"], "recibida": d["recibida"]} for d in diferencias
            ],
        }
        return Response(cuerpo)
