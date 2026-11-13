"""API de campo del módulo Emergencia: base, perfil, M1 (el Formulario 1 del agente) y M3 (recepción de kits).

Lo que usa la app (`Chaco-mobile`) para saber qué accesos mostrar y para mandar una familia
relevada en el barrio, con o sin señal. Mismo molde que las otras dos superficies de la app
(`programas/api/views.py`, `views_inspecciones.py`): token de DRF —el mismo login,
``/api/becas/auth/token/``—, un permiso por recurso y la regla en el servicio.

* **Dos permisos.** `EmergenciaModuloPermission` es «abre el módulo»
  (``emergencia_programa.modulo_habilitado``, la misma función que consulta el login):
  agente territorial o guardia de un dispositivo. `EmergenciaRelevarPermission` es
  ``emergencia.relevar`` en el programa EMERGENCIA: solo el agente crea casos. Ninguna
  capacidad de otro módulo de la app (``becas.campo``, ``inspeccion.relevar``) abre esto, y
  ninguna de estas abre ``/api/becas/`` ni ``/api/dispositivos/`` (RU §6 n.° 3).
* **La vista no decide reglas.** `crear_caso` es la única función que crea casos y es la
  que usa la mesa: valida el Formulario 1, calcula el total y la prioridad, resuelve al
  responsable y es idempotente por ``uuid_cliente`` (RU-2, RU-16). Acá solo se traduce:
  ``ValidationError`` → 400 por campo, identificador de otro usuario → 409, sin permiso →
  403 ``SIN_MODULO``.
* **M3 · Recepción de kits.** `EmergenciaRecibirKitPermission` es «recibe kits en algún
  dispositivo» (``kits.recibe_kits``): sin eso, 403 ``SIN_MODULO``. Con la capacidad pero sin
  alcance sobre **ese** dispositivo o **esa** entrega, **404**, igual que un id inexistente
  (plan §2, C2). `recibir_entrega` es la misma función que usa la recepción web: acá se
  traduce ``ValidationError`` → 400 por campo y :class:`EstadoCambio` → 409
  ``{detail, estado_actual}``.
* **M2 · Llegada de familias (PR 8).** `EmergenciaAdmitirPermission` es «admite familias en
  algún dispositivo» (``dispositivo.admitir`` con alcance): sin eso, 403 ``SIN_MODULO``. Cada
  vista llama a la misma función de ``services.emergencia_alojar`` que la pantalla E6 del
  backoffice (RU-1, RU-2) y traduce: ``ValidationError`` → 400 por campo, :class:`EstadoCambio`
  → 409 ``{detail, estado_actual}``, y un dispositivo, una derivación o un caso de otro
  dispositivo → 404 (C2, RU-9).
* **La consulta de identidad** es la de Becas (``views.responder_consulta_de_persona``) con
  permiso propio y **la misma cubeta** de throttle: un usuario con los dos módulos no
  duplica su cuota cambiando de ruta (hallazgo H2 del plan).
"""

from django.core.exceptions import PermissionDenied, ValidationError
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.exceptions import NotFound
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.routers import APIRootView
from rest_framework.views import APIView

from core import rbac
from programas.api.serializers import ConsultaPersonaRespuestaSerializer, ConsultaPersonaSerializer
from programas.api.serializers_emergencia import (
    AceptacionSerializer,
    AceptarDerivacionEnvioSerializer,
    AgregarIntegranteEnvioSerializer,
    AlojarFamiliaEnvioSerializer,
    AvisoALaMesaSerializer,
    BusquedaPorDniSerializer,
    CancelarIngresoEnvioSerializer,
    CasoEmergenciaCreadoSerializer,
    CasoEmergenciaEnvioSerializer,
    CerrarConDiferenciaEnvioSerializer,
    CierreDeIngresoSerializer,
    CompletarFichaEnvioSerializer,
    ConfirmacionSerializer,
    ConfirmarIntegranteEnvioSerializer,
    EntregaKitSerializer,
    EstadoCambioSerializer,
    FichaCompletadaSerializer,
    IngresoDirectoEnvioSerializer,
    IngresoDirectoSerializer,
    IntegranteAgregadoSerializer,
    IntegranteDetalleSerializer,
    IntegrantesDelCasoSerializer,
    LocalidadEmergenciaSerializer,
    MapaDePlazasSerializer,
    MiCasoEmergenciaSerializer,
    MiDispositivoEmergenciaSerializer,
    PerfilEmergenciaSerializer,
    RecepcionKitEnvioSerializer,
    RecepcionKitRespuestaSerializer,
    RechazarDerivacionEnvioSerializer,
    RechazoSerializer,
)
from programas.api.views import ConsultaPersonasThrottle, responder_consulta_de_persona
from programas.api.views_inspecciones import _respuesta_400
from programas.models import CasoEmergencia, Derivacion, IntegranteGrupo
from programas.selectors import emergencia_alojar as selectores_alojar
from programas.selectors import kits as selectores_kits
from programas.selectors.emergencia_campo import casos_relevados_por, localidades_para_relevar
from programas.services import emergencia_alojar as servicio_alojar
from programas.services import kits as servicio_kits
from programas.services.dispositivos import dispositivos_en_alcance
from programas.services.emergencia import EstadoCambio, UuidEnUso, crear_caso
from programas.services.emergencia_programa import (
    CAP_ADMITIR,
    CAP_EMERGENCIA_RELEVAR,
    CAP_RECIBIR_KIT,
    modulo_habilitado,
    puede_en_programa_emergencia,
    roles_en_app,
)

MENSAJE_SIN_MODULO = "El usuario no tiene acceso al módulo Emergencia."
MENSAJE_SIN_RELEVAR = (
    "El usuario no tiene permiso para relevar familias en Emergencia. "
    "Pedile a quien administra los usuarios que te sume el rol de agente territorial."
)
MENSAJE_SIN_RECIBIR_KIT = (
    "El usuario no recibe kits en ningún dispositivo. "
    "Pedile a quien arma el equipo del dispositivo que te sume con un rol que reciba kits."
)
CAP_VER_CIUDADANO = "ciudadano.ver"
CODIGO_SIN_MODULO = "SIN_MODULO"
CODIGO_VALIDACION = "VALIDACION"
CODIGO_UUID_EN_USO = "UUID_EN_USO"

_AUTENTICACION = [TokenAuthentication, SessionAuthentication]

_SIN_TOKEN = OpenApiResponse(description="Sin token o token inválido.")
_SIN_MODULO = OpenApiResponse(description="El usuario no abre el módulo Emergencia: `code: SIN_MODULO`.")
_SIN_RELEVAR = OpenApiResponse(
    description="El usuario no tiene `emergencia.relevar` en el programa Emergencia: `code: SIN_MODULO`."
)
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


class EmergenciaModuloPermission(BasePermission):
    """Abre el módulo: agente territorial o guardia de un dispositivo (H10 del plan)."""

    # `code` además de `detail`: la app distingue «este usuario no tiene el módulo» de
    # cualquier otro 403, igual que en Becas y en el relevamiento edilicio.
    message = {"detail": MENSAJE_SIN_MODULO, "code": CODIGO_SIN_MODULO}

    def has_permission(self, request, view):
        return modulo_habilitado(request.user)


class EmergenciaRelevarPermission(BasePermission):
    """Exige ``emergencia.relevar`` con alcance al programa EMERGENCIA (el agente territorial)."""

    message = {"detail": MENSAJE_SIN_RELEVAR, "code": CODIGO_SIN_MODULO}

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and puede_en_programa_emergencia(user, CAP_EMERGENCIA_RELEVAR))


class EmergenciaRecibirKitPermission(BasePermission):
    """Recibe kits en **algún** dispositivo: ``emergencia.recibir_kit`` con el Equipo (RU-8, H3).

    Va después de ``EmergenciaModuloPermission``. Qué dispositivo y qué entrega son suyos lo
    decide cada vista por alcance, con 404.
    """

    message = {"detail": MENSAJE_SIN_RECIBIR_KIT, "code": CODIGO_SIN_MODULO}

    def has_permission(self, request, view):
        return servicio_kits.recibe_kits(request.user)


class RaizApiEmergencia(APIRootView):
    """La raíz ``/api/emergencia/``: autentica igual que el resto del namespace (R0-04)."""

    authentication_classes = _AUTENTICACION
    permission_classes = [IsAuthenticated, EmergenciaModuloPermission]


class _VistaDelModulo(APIView):
    """Base de las vistas del namespace: token (o sesión) y el módulo abierto."""

    authentication_classes = _AUTENTICACION
    permission_classes = [IsAuthenticated, EmergenciaModuloPermission]


class PerfilEmergenciaView(_VistaDelModulo):
    @extend_schema(
        responses={200: PerfilEmergenciaSerializer, 401: _SIN_TOKEN, 403: _SIN_MODULO},
        description=(
            "Qué accesos del módulo abre el usuario, para armar la pantalla inicial (RU-5). `dispositivo` dice si "
            "puede **operar** en algún dispositivo (admitir familias o recibir kits). Vienen los dos en `false` "
            "solo para el administrador del programa Dispositivos sin esas capacidades: abre el módulo pero no "
            "tiene nada que hacer en la app."
        ),
    )
    def get(self, request):
        return Response(roles_en_app(request.user))


class ConsultarPersonaEmergenciaView(_VistaDelModulo):
    throttle_classes = [ConsultaPersonasThrottle]

    @extend_schema(
        request=ConsultaPersonaSerializer,
        responses={
            200: ConsultaPersonaRespuestaSerializer,
            400: OpenApiResponse(description="Falta el DNI o el sexo no es F ni M."),
            401: _SIN_TOKEN,
            403: _SIN_MODULO,
            404: OpenApiResponse(description="No se la pudo identificar, o Base de Personas la informa fallecida."),
            429: OpenApiResponse(
                description="Se superó el tope de consultas de identidad del usuario (compartido con Becas)."
            ),
            502: OpenApiResponse(description="Base de Personas falló."),
        },
        description=(
            "La misma consulta de identidad que `POST /api/becas/personas/consultar/`, con el mismo cuerpo y la "
            "misma respuesta, para quien abre Emergencia y no Becas. Consulta solo Base de Personas: `relevamiento` "
            "se ignora."
        ),
    )
    def post(self, request):
        return responder_consulta_de_persona(request.data)


class LocalidadesEmergenciaView(_VistaDelModulo):
    @extend_schema(
        responses={200: LocalidadEmergenciaSerializer(many=True), 401: _SIN_TOKEN, 403: _SIN_MODULO},
        description=(
            "Las localidades que ofrece el Formulario 1, por nombre y sin paginar: la app guarda la lista entera "
            "y la refresca una vez por día. Sin coordenadas."
        ),
    )
    def get(self, request):
        return Response(localidades_para_relevar())


def _respuesta_de_validacion(errores):
    """El 400 de la app de campo (``detail`` legible + detalle por campo) con su ``code``."""

    respuesta = _respuesta_400(errores)
    respuesta.data["code"] = CODIGO_VALIDACION
    return respuesta


class CasosEmergenciaView(APIView):
    """El envío del Formulario 1: una familia relevada en territorio."""

    authentication_classes = _AUTENTICACION
    permission_classes = [IsAuthenticated, EmergenciaRelevarPermission]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @extend_schema(
        request={"multipart/form-data": CasoEmergenciaEnvioSerializer},
        responses={
            201: CasoEmergenciaCreadoSerializer,
            200: OpenApiResponse(
                response=CasoEmergenciaCreadoSerializer,
                description="Reenvío: ese `uuid_cliente` ya había creado un caso y se devuelve el mismo.",
            ),
            400: OpenApiResponse(
                description=(
                    "El envío no es válido. Trae `code: VALIDACION`, `detail` legible y el detalle por campo: "
                    "falta `uuid_cliente`, total en cero (`total`), RN-1.3, sin dirección, foto que no es JPEG "
                    "o que pasa de 5 MB, `relevado_en` adelantada más de un día."
                )
            ),
            401: _SIN_TOKEN,
            403: _SIN_RELEVAR,
            409: OpenApiResponse(
                description=(
                    "`code: UUID_EN_USO`: ese `uuid_cliente` ya creó un caso de otro usuario. No se reintenta "
                    "con el mismo identificador."
                )
            ),
        },
        description=(
            "Crea un caso de origen territorio con su grupo familiar y hasta dos fotos. Idempotente por "
            "`uuid_cliente`: el reenvío del mismo devuelve 200 con el caso que ya existía, sin validar ni "
            "escribir nada. El total de personas y la prioridad los calcula el servidor."
        ),
    )
    def post(self, request):
        entrada = CasoEmergenciaEnvioSerializer(data=request.data)
        if not entrada.is_valid():
            return _respuesta_de_validacion(entrada.errors)
        try:
            caso = crear_caso(
                usuario=request.user,
                origen=CasoEmergencia.Origen.TERRITORIO,
                datos_formulario1=entrada.datos_formulario1(),
                uuid_cliente=entrada.validated_data["uuid_cliente"],
                relevado_en=entrada.validated_data["relevado_en"],
            )
        except PermissionDenied:
            # No debería llegar: el permiso de la vista pregunta lo mismo. Si llega, el
            # mismo cuerpo que da el permiso.
            return Response(EmergenciaRelevarPermission.message, status=status.HTTP_403_FORBIDDEN)
        except UuidEnUso as error:
            detalle = error.message_dict["uuid_cliente"][0]
            return Response({"detail": detalle, "code": CODIGO_UUID_EN_USO}, status=status.HTTP_409_CONFLICT)
        except ValidationError as error:
            errores = error.message_dict if hasattr(error, "error_dict") else error.messages
            return _respuesta_de_validacion(errores)
        codigo = status.HTTP_200_OK if caso.ya_existia else status.HTTP_201_CREATED
        return Response(CasoEmergenciaCreadoSerializer(caso).data, status=codigo)


class MisCasosEmergenciaView(APIView):
    authentication_classes = _AUTENTICACION
    permission_classes = [IsAuthenticated, EmergenciaRelevarPermission]

    @extend_schema(
        responses={200: MiCasoEmergenciaSerializer(many=True), 401: _SIN_TOKEN, 403: _SIN_RELEVAR},
        description=(
            "«Mis envíos»: los últimos 50 casos que el agente relevó en territorio, del más nuevo al más viejo, "
            "con el estado en que está cada uno. Sin paginar."
        ),
    )
    def get(self, request):
        return Response(MiCasoEmergenciaSerializer(casos_relevados_por(request.user), many=True).data)


# ---------------------------------------------------------------------------
# M3 · Recepción de kits
# ---------------------------------------------------------------------------

#: Tope de lo que devuelve la lista de un dispositivo cuando no se piden solo las pendientes.
TOPE_ENTREGAS = 50
CODIGO_UUID_DE_OTRA_RECEPCION = CODIGO_UUID_EN_USO


class MisDispositivosEmergenciaView(_VistaDelModulo):
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


class _VistaDeKits(APIView):
    """Base de M3: token (o sesión), el módulo abierto y recibir kits en algún dispositivo."""

    authentication_classes = _AUTENTICACION
    permission_classes = [IsAuthenticated, EmergenciaModuloPermission, EmergenciaRecibirKitPermission]

    def _o_404(self, queryset, pk):
        """El objeto de ``queryset``, o el 404 de siempre: el mismo cuerpo exista o no en otro alcance."""
        objeto = queryset.filter(pk=pk).first()
        if objeto is None:
            raise NotFound
        return objeto

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
        try:
            recibida = servicio_kits.recibir_entrega(
                entrega,
                request.user,
                entrada.cantidades_por_item(),
                entrada.validated_data["remito"],
                observacion=entrada.validated_data["observacion"],
                uuid_cliente=entrada.validated_data["uuid_cliente"],
            )
        except PermissionDenied:
            # No debería llegar: la entrega salió del alcance del usuario. Si llega —lo sacaron
            # del Equipo entre una línea y la otra—, lo mismo que una entrega que no es suya.
            raise NotFound from None
        except EstadoCambio as cambio:
            return Response(
                {"detail": cambio.mensaje, "estado_actual": cambio.estado_actual}, status=status.HTTP_409_CONFLICT
            )
        except UuidEnUso as error:
            return Response(
                {"detail": error.message_dict["uuid_cliente"][0], "code": CODIGO_UUID_DE_OTRA_RECEPCION},
                status=status.HTTP_409_CONFLICT,
            )
        except ValidationError as error:
            errores = error.message_dict if hasattr(error, "error_dict") else error.messages
            return _respuesta_de_validacion(errores)
        diferencias = selectores_kits.diferencias_de(selectores_kits.lineas_de(recibida))
        cuerpo = {
            "estado": recibida.estado,
            "diferencias": [
                {"item": d["item"], "enviada": d["enviada"], "recibida": d["recibida"]} for d in diferencias
            ],
        }
        return Response(cuerpo)


# ---------------------------------------------------------------------------
# M2 · Llegada de familias (PR 8)
# ---------------------------------------------------------------------------
#
# Paridad con la pantalla E6 del backoffice (RU-1): cada vista llama a la **misma** función de
# ``services.emergencia_alojar`` que la vista web y solo traduce lo que contesta (RU-2):
#
# * ``ValidationError`` → 400 por campo (``code: VALIDACION``), con el mensaje del servicio.
# * :class:`EstadoCambio` → 409 ``{detail, estado_actual}``: otra guardia —desde su teléfono o
#   desde el backoffice—, la mesa o el cron se adelantaron. La app recarga.
# * ``PermissionDenied`` → 404. No debería llegar: el alcance ya se resolvió acá, por
#   ``dispositivos_en_alcance``. Si llega (lo sacaron del Equipo entre una línea y la otra), lo
#   mismo que un id ajeno.
#
# Quién entra (plan C2): sin ``dispositivo.admitir`` con alcance en **ningún** dispositivo, 403
# ``SIN_MODULO``; con ella, un dispositivo, una derivación o un caso de **otro** dispositivo dan
# **404**, el mismo cuerpo que un id que no existe, sin nombrar a nadie (RU-9).

MENSAJE_SIN_ADMITIR = (
    "El usuario no admite familias en ningún dispositivo. "
    "Pedile a quien arma el equipo del dispositivo que te sume con un rol que admita familias."
)
INGRESO_NO_DISPONIBLE = (
    "El ingreso del caso {numero} todavía no se aceptó o ya no sigue en este dispositivo. Buscá a la familia de nuevo."
)

#: Los estados del caso en que la guardia todavía lo ve: el ingreso en curso y lo que vino después.
ESTADOS_CON_INGRESO = (
    CasoEmergencia.Estado.INGRESO_EN_CURSO,
    CasoEmergencia.Estado.ALOJADO,
    CasoEmergencia.Estado.CERRADO,
)

_SIN_ADMITIR = OpenApiResponse(
    description=(
        "El usuario no abre el módulo o no tiene `dispositivo.admitir` en el Equipo de ningún dispositivo: "
        "`code: SIN_MODULO`."
    )
)
_AJENO = OpenApiResponse(
    description=(
        "No existe, o es de un dispositivo donde el usuario no admite familias: las dos cosas contestan lo mismo, "
        "sin nombrar al dispositivo."
    )
)
_CAMBIO = OpenApiResponse(
    response=EstadoCambioSerializer,
    description=(
        "El caso ya no está como la acción necesita: otra guardia actuó (desde su teléfono o desde el backoffice), "
        "la mesa canceló o el cron venció la derivación. `detail` dice qué pasó y `estado_actual` en qué estado "
        "quedó el caso. La app recarga."
    ),
)


def _400(descripcion):
    return OpenApiResponse(
        description=f"`code: VALIDACION`, `detail` legible y el detalle por campo. {descripcion}".strip()
    )


class EmergenciaAdmitirPermission(BasePermission):
    """Admite familias en **algún** dispositivo: ``dispositivo.admitir`` con alcance (RU-8).

    Va después de ``EmergenciaModuloPermission``. Qué dispositivo, derivación o caso son suyos
    lo decide cada vista por alcance, con 404.
    """

    message = {"detail": MENSAJE_SIN_ADMITIR, "code": CODIGO_SIN_MODULO}

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and dispositivos_en_alcance(user, CAP_ADMITIR).exists())


def _errores(error):
    return error.message_dict if hasattr(error, "error_dict") else error.messages


def _respuesta_409(cambio):
    return Response({"detail": cambio.mensaje, "estado_actual": cambio.estado_actual}, status=status.HTTP_409_CONFLICT)


def _ficha_publica(ficha):
    """La ficha guardada sin los identificadores de envío, que no son del Formulario 2."""
    return {clave: valor for clave, valor in (ficha or {}).items() if clave not in servicio_alojar.CLAVES_DE_ENVIO}


class _VistaDeLlegadas(APIView):
    """Base de M2: token (o sesión), el módulo abierto y admitir familias en algún dispositivo."""

    authentication_classes = _AUTENTICACION
    permission_classes = [IsAuthenticated, EmergenciaModuloPermission, EmergenciaAdmitirPermission]

    def _admitidos(self, request):
        return dispositivos_en_alcance(request.user, CAP_ADMITIR)

    def _dispositivo(self, request, pk):
        """El dispositivo, **si admite ahí**. El de otro es un 404."""
        dispositivo = self._admitidos(request).select_related("tipo").filter(pk=pk).first()
        if dispositivo is None:
            raise NotFound
        return dispositivo

    def _derivacion(self, request, pk):
        """La derivación, **si es hacia un dispositivo donde admite**. La de otro es un 404 (C2)."""
        derivacion = Derivacion.objects.filter(pk=pk, dispositivo__in=self._admitidos(request)).first()
        if derivacion is None:
            raise NotFound
        return derivacion

    def _ingreso(self, request, pk):
        """La **última** derivación del caso, si es hacia un dispositivo donde admite. Si no, 404.

        Es la guarda de RU-9 para todo lo que va por ``casos/{id}/``: la misma derivación que
        mira el servicio (``_abrir_ingreso``). Un caso que la guardia rechazó y la mesa derivó
        a otro lado deja de ser suyo.
        """
        derivacion = (
            Derivacion.objects.filter(caso_id=pk).select_related("caso__grupo__responsable").order_by("-id").first()
        )
        if derivacion is None or not self._admitidos(request).filter(pk=derivacion.dispositivo_id).exists():
            raise NotFound
        return derivacion

    def _ingreso_para_leer(self, request, pk):
        """El caso de :meth:`_ingreso` si su ingreso se aceptó; si no, el 409 que lo dice."""
        derivacion = self._ingreso(request, pk)
        caso = derivacion.caso
        if derivacion.estado != Derivacion.Estado.ACEPTADA or caso.estado not in ESTADOS_CON_INGRESO:
            cambio = EstadoCambio(INGRESO_NO_DISPONIBLE.format(numero=caso.numero), estado_actual=caso.estado)
            return caso, _respuesta_409(cambio)
        return caso, None

    def _ejecutar(self, accion):
        """Corre la función del servicio y traduce lo que rechace. Devuelve ``(resultado, respuesta)``."""
        try:
            return accion(), None
        except PermissionDenied:
            raise NotFound from None
        except EstadoCambio as cambio:
            return None, _respuesta_409(cambio)
        except ValidationError as error:
            errores = _errores(error)
            if isinstance(errores, dict) and errores.get("uuid_cliente") == [UUID_EN_USO]:
                return None, Response(
                    {"detail": UUID_EN_USO, "code": CODIGO_UUID_EN_USO}, status=status.HTTP_409_CONFLICT
                )
            return None, _respuesta_de_validacion(errores)

    def _entrada(self, serializer_class, request):
        """El cuerpo validado en su forma, o ``(None, 400)``."""
        entrada = serializer_class(data=request.data)
        if not entrada.is_valid():
            return None, _respuesta_de_validacion(entrada.errors)
        return entrada.validated_data, None


def _filas(caso_pk):
    """``(caso, integrantes_de(caso))`` recién leídos: después de una escritura, lo que quedó. **2 consultas.**"""
    caso = CasoEmergencia.objects.select_related("grupo").get(pk=caso_pk)
    return caso, selectores_alojar.integrantes_de(caso)


def _fila(caso_pk, orden):
    _caso, datos = _filas(caso_pk)
    return next(fila for fila in datos["integrantes"] if fila["n"] == orden)


def _creado_o_reenvio(repetido):
    return status.HTTP_200_OK if repetido else status.HTTP_201_CREATED


class BuscarFamiliaView(_VistaDeLlegadas):
    @extend_schema(
        parameters=[OpenApiParameter("dni", str, required=True, description="DNI de cualquiera de la familia.")],
        responses={
            200: BusquedaPorDniSerializer,
            400: _400("`dni` vacío o que no es un DNI."),
            401: _SIN_TOKEN,
            403: _SIN_ADMITIR,
            404: _AJENO,
        },
        description=(
            "M2-1: busca a la familia por el DNI del responsable o de una persona ya confirmada. `DERIVACION`: hay "
            "una derivación pendiente o aceptada **hacia este dispositivo**. `ALOJADA`: la persona tiene una "
            "estadía abierta (dónde, solo si el usuario lo puede ver). `SIN_DERIVACION`: todo lo demás, incluida "
            "una derivación a otro dispositivo, que no se nombra."
        ),
    )
    def get(self, request, dispositivo_id):
        dispositivo = self._dispositivo(request, dispositivo_id)
        resultado, respuesta = self._ejecutar(
            lambda: servicio_alojar.buscar_por_dni(
                dispositivo=dispositivo, dni=request.query_params.get("dni", ""), usuario=request.user
            )
        )
        if respuesta is not None:
            return respuesta
        return Response(BusquedaPorDniSerializer(resultado).data)


class AceptarDerivacionView(_VistaDeLlegadas):
    @extend_schema(
        request=AceptarDerivacionEnvioSerializer,
        responses={
            200: AceptacionSerializer,
            400: _400("`plazas`: el dispositivo no tiene camas libres, o una se ocupó mientras se aceptaba."),
            401: _SIN_TOKEN,
            403: _SIN_ADMITIR,
            404: _AJENO,
            409: _CAMBIO,
        },
        description=(
            "M2-2: acepta una derivación pendiente —vale aunque ya haya pasado `vence_en`, mientras la mesa no la "
            "marque vencida—, reserva hasta las camas pedidas y abre el ingreso (`INGRESO_EN_CURSO`). Con menos "
            "camas que las pedidas acepta igual y lo dice en `faltantes`. Requiere conexión."
        ),
    )
    def post(self, request, pk):
        derivacion = self._derivacion(request, pk)
        _datos, respuesta = self._entrada(AceptarDerivacionEnvioSerializer, request)
        if respuesta is not None:
            return respuesta
        resultado, respuesta = self._ejecutar(
            lambda: servicio_alojar.aceptar_derivacion(derivacion=derivacion, usuario=request.user)
        )
        if respuesta is not None:
            return respuesta
        caso, datos = _filas(resultado.caso.pk)
        cuerpo = {
            "caso": caso,
            "reservadas": resultado.reservadas,
            "faltantes": resultado.faltantes,
            "mensaje": resultado.mensaje,
            "integrantes": datos["integrantes"],
        }
        return Response(AceptacionSerializer(cuerpo).data)


class RechazarDerivacionView(_VistaDeLlegadas):
    @extend_schema(
        request=RechazarDerivacionEnvioSerializer,
        responses={
            200: RechazoSerializer,
            400: _400("`motivo` fuera de la lista; `observacion` vacía con `OTRO`."),
            401: _SIN_TOKEN,
            403: _SIN_ADMITIR,
            404: _AJENO,
            409: _CAMBIO,
        },
        description="M2-2: rechaza una derivación pendiente con motivo. El caso vuelve a la mesa (`EN_GESTION`).",
    )
    def post(self, request, pk):
        derivacion = self._derivacion(request, pk)
        datos, respuesta = self._entrada(RechazarDerivacionEnvioSerializer, request)
        if respuesta is not None:
            return respuesta
        rechazada, respuesta = self._ejecutar(
            lambda: servicio_alojar.rechazar_derivacion(derivacion=derivacion, usuario=request.user, **datos)
        )
        if respuesta is not None:
            return respuesta
        return Response(RechazoSerializer({"caso_estado": rechazada.caso.estado}).data)


class IntegrantesView(_VistaDeLlegadas):
    @extend_schema(
        operation_id="emergencia_casos_integrantes_list",
        responses={200: IntegrantesDelCasoSerializer, 401: _SIN_TOKEN, 403: _SIN_ADMITIR, 404: _AJENO, 409: _CAMBIO},
        description=(
            "M2-3: las filas de la familia («3 de 7 confirmadas»). Abre con el ingreso aceptado, en curso o ya "
            "alojado; antes de aceptar o después de un rechazo o una cancelación, 409."
        ),
    )
    def get(self, request, pk):
        caso, respuesta = self._ingreso_para_leer(request, pk)
        if respuesta is not None:
            return respuesta
        datos = selectores_alojar.integrantes_de(caso)
        return Response(IntegrantesDelCasoSerializer({"caso": caso, **datos}).data)

    @extend_schema(
        request=AgregarIntegranteEnvioSerializer,
        responses={
            201: IntegranteAgregadoSerializer,
            200: OpenApiResponse(
                response=IntegranteAgregadoSerializer,
                description="Reenvío: ese `uuid_cliente` ya había agregado una fila y se devuelve la misma.",
            ),
            400: _400("Falta `uuid_cliente` o no es un UUID."),
            401: _SIN_TOKEN,
            403: _SIN_ADMITIR,
            404: _AJENO,
            409: _CAMBIO,
        },
        description=(
            "«Agregar persona» (RN-3.8): suma una fila sin confirmar y `total_declarado` crece en uno. No reserva "
            "cama: al confirmarla se elige entre las libres. Idempotente por `uuid_cliente`."
        ),
    )
    def post(self, request, pk):
        derivacion = self._ingreso(request, pk)
        datos, respuesta = self._entrada(AgregarIntegranteEnvioSerializer, request)
        if respuesta is not None:
            return respuesta
        integrante, respuesta = self._ejecutar(
            lambda: servicio_alojar.agregar_integrante(
                caso=derivacion.caso_id, usuario=request.user, uuid_cliente=datos["uuid_cliente"]
            )
        )
        if respuesta is not None:
            return respuesta
        cuerpo = {
            "integrante": _fila(derivacion.caso_id, integrante.orden),
            "total_declarado": integrante.total_declarado,
        }
        return Response(IntegranteAgregadoSerializer(cuerpo).data, status=_creado_o_reenvio(integrante.ya_estaba))


class IntegranteView(_VistaDeLlegadas):
    @extend_schema(
        responses={200: IntegranteDetalleSerializer, 401: _SIN_TOKEN, 403: _SIN_ADMITIR, 404: _AJENO, 409: _CAMBIO},
        description="Una persona de la familia con su ficha guardada, para completar las secciones 4 a 8 (M2-4).",
    )
    def get(self, request, pk, n):
        caso, respuesta = self._ingreso_para_leer(request, pk)
        if respuesta is not None:
            return respuesta
        integrante = IntegranteGrupo.objects.filter(grupo_id=caso.grupo_id, orden=n).only("ficha").first()
        if integrante is None:
            raise NotFound
        fila = next(fila for fila in selectores_alojar.integrantes_de(caso)["integrantes"] if fila["n"] == n)
        ficha = _ficha_publica(integrante.ficha)
        cuerpo = {**fila, "ficha": ficha, "secciones_incompletas": servicio_alojar.secciones_incompletas(ficha)}
        return Response(IntegranteDetalleSerializer(cuerpo).data)

    @extend_schema(
        request=CompletarFichaEnvioSerializer,
        responses={
            200: FichaCompletadaSerializer,
            400: _400(
                "`ficha` no es un objeto; un campo que no es del tipo (clave: el nombre del campo); `orden`: la "
                "persona no es de la familia o todavía no se confirmó."
            ),
            401: _SIN_TOKEN,
            403: _SIN_ADMITIR,
            404: _AJENO,
            409: _CAMBIO,
        },
        description=(
            "Completa las secciones 4 a 8 de una persona ya confirmada, con el ingreso en curso o la familia ya "
            "alojada. Cada sección que viene reemplaza a la guardada; las del mínimo no se tocan."
        ),
    )
    def patch(self, request, pk, n):
        derivacion = self._ingreso(request, pk)
        datos, respuesta = self._entrada(CompletarFichaEnvioSerializer, request)
        if respuesta is not None:
            return respuesta
        integrante, respuesta = self._ejecutar(
            lambda: servicio_alojar.completar_ficha(
                caso=derivacion.caso_id, orden=n, usuario=request.user, ficha=datos["ficha"]
            )
        )
        if respuesta is not None:
            return respuesta
        cuerpo = {
            "ficha_completa": integrante.ficha_completa,
            "secciones_incompletas": servicio_alojar.secciones_incompletas(integrante.ficha),
        }
        return Response(FichaCompletadaSerializer(cuerpo).data)


class ConfirmarIntegranteView(_VistaDeLlegadas):
    @extend_schema(
        request=ConfirmarIntegranteEnvioSerializer,
        responses={
            201: ConfirmacionSerializer,
            200: OpenApiResponse(
                response=ConfirmacionSerializer,
                description="Reenvío: ese `uuid_cliente` ya había confirmado a esta persona y se devuelve lo mismo.",
            ),
            400: _400(
                "Falta lo mínimo de la ficha (clave: el nombre plano del campo, p. ej. `embarazo`, `dni`, "
                "`adulto_responsable`); `plaza`: la cama no se puede elegir (ocupada, fuera de servicio, reservada "
                "para otra persona, de otro dispositivo) o no queda ninguna; `dni`: la persona ya está confirmada en "
                "esta familia o alojada en la red; `orden`: la persona no es de la familia."
            ),
            401: _SIN_TOKEN,
            403: _SIN_ADMITIR,
            404: _AJENO,
            409: _CAMBIO,
        },
        description=(
            "M2-4 «Confirmar persona»: la ficha mínima y la cama, en una transacción (crea la estadía). Idempotente "
            "por `uuid_cliente`; la misma persona confirmada por otro envío es 409. Requiere conexión."
        ),
    )
    def post(self, request, pk, n):
        derivacion = self._ingreso(request, pk)
        datos, respuesta = self._entrada(ConfirmarIntegranteEnvioSerializer, request)
        if respuesta is not None:
            return respuesta
        integrante, respuesta = self._ejecutar(
            lambda: servicio_alojar.confirmar_integrante(
                caso=derivacion.caso_id,
                orden=n,
                usuario=request.user,
                ficha=datos["ficha"],
                plaza=datos["plaza_id"],
                uuid_cliente=datos["uuid_cliente"],
            )
        )
        if respuesta is not None:
            return respuesta
        cuerpo = {
            "integrante": _fila(derivacion.caso_id, n),
            "confirmadas": integrante.confirmadas,
            "total_declarado": integrante.total_declarado,
            "reserva_liberada": integrante.reserva_liberada,
        }
        return Response(ConfirmacionSerializer(cuerpo).data, status=_creado_o_reenvio(integrante.ya_estaba))


def _cierre(caso):
    return CierreDeIngresoSerializer(
        {"estado": caso.estado, "total_alojado": caso.total_alojado, "liberadas": caso.reservas_liberadas}
    ).data


class AlojarFamiliaView(_VistaDeLlegadas):
    @extend_schema(
        request=AlojarFamiliaEnvioSerializer,
        responses={
            200: CierreDeIngresoSerializer,
            400: _400(
                "Falta confirmar a alguien (`non_field_errors`); `sector` que no es del dispositivo; "
                "`tarjeta_numero` vacío con la tarjeta entregada; textos largos."
            ),
            401: _SIN_TOKEN,
            403: _SIN_ADMITIR,
            404: _AJENO,
            409: _CAMBIO,
        },
        description="M2-5 «Familia alojada»: con N de N confirmadas, guarda la sección 4 y el caso pasa a `ALOJADO`.",
    )
    def post(self, request, pk):
        derivacion = self._ingreso(request, pk)
        datos, respuesta = self._entrada(AlojarFamiliaEnvioSerializer, request)
        if respuesta is not None:
            return respuesta
        caso, respuesta = self._ejecutar(
            lambda: servicio_alojar.alojar_familia(caso=derivacion.caso_id, usuario=request.user, **datos)
        )
        return respuesta if respuesta is not None else Response(_cierre(caso))


class CerrarConDiferenciaView(_VistaDeLlegadas):
    @extend_schema(
        request=CerrarConDiferenciaEnvioSerializer,
        responses={
            200: CierreDeIngresoSerializer,
            400: _400(
                "`motivo` fuera de la lista; `observacion` vacía con `OTRO`; nadie confirmado o todos confirmados "
                "(`non_field_errors`)."
            ),
            401: _SIN_TOKEN,
            403: _SIN_ADMITIR,
            404: _AJENO,
            409: _CAMBIO,
        },
        description=(
            "RN-3.9: llegaron menos de las declaradas. Con al menos una confirmada, el caso pasa a `ALOJADO` con "
            "`total_alojado` = confirmadas y las reservas sobrantes se liberan."
        ),
    )
    def post(self, request, pk):
        derivacion = self._ingreso(request, pk)
        datos, respuesta = self._entrada(CerrarConDiferenciaEnvioSerializer, request)
        if respuesta is not None:
            return respuesta
        caso, respuesta = self._ejecutar(
            lambda: servicio_alojar.cerrar_con_diferencia(caso=derivacion.caso_id, usuario=request.user, **datos)
        )
        return respuesta if respuesta is not None else Response(_cierre(caso))


class CancelarIngresoView(_VistaDeLlegadas):
    @extend_schema(
        request=CancelarIngresoEnvioSerializer,
        responses={
            200: CierreDeIngresoSerializer,
            400: _400("`motivo` vacío o de más de 200 caracteres; ya hay personas confirmadas (`non_field_errors`)."),
            401: _SIN_TOKEN,
            403: _SIN_ADMITIR,
            404: _AJENO,
            409: _CAMBIO,
        },
        description=(
            "Cancela un ingreso aceptado sin nadie confirmado: libera las camas y el caso vuelve a la mesa "
            "(`EN_GESTION`, o `NUEVO` si era un ingreso directo)."
        ),
    )
    def post(self, request, pk):
        derivacion = self._ingreso(request, pk)
        datos, respuesta = self._entrada(CancelarIngresoEnvioSerializer, request)
        if respuesta is not None:
            return respuesta
        caso, respuesta = self._ejecutar(
            lambda: servicio_alojar.cancelar_ingreso(caso=derivacion.caso_id, usuario=request.user, **datos)
        )
        return respuesta if respuesta is not None else Response(_cierre(caso))


class PlazasDelDispositivoView(_VistaDeLlegadas):
    @extend_schema(
        parameters=[
            OpenApiParameter(
                "caso",
                int,
                description=(
                    "`id` del caso cuya familia se aloja: sus camas salen `RESERVADA_FAMILIA`. Tiene que ser un caso "
                    "derivado a este dispositivo (si no, 404). Sin él, ninguna cama es de la familia."
                ),
            )
        ],
        responses={200: MapaDePlazasSerializer, 401: _SIN_TOKEN, 403: _SIN_ADMITIR, 404: _AJENO},
        description=(
            "El mapa de camas del dispositivo para elegir la de una persona (M2-4): sectores activos con camas, "
            "por nombre, y sus camas por código con su estado."
        ),
    )
    def get(self, request, dispositivo_id):
        dispositivo = self._dispositivo(request, dispositivo_id)
        caso = request.query_params.get("caso")
        if caso not in (None, ""):
            if not str(caso).isdecimal():
                raise NotFound
            caso = int(caso)
            if self._ingreso(request, caso).dispositivo_id != dispositivo.pk:
                raise NotFound
        else:
            caso = None
        sectores = selectores_alojar.plazas_para_caso(
            dispositivo, caso, request.user, puede_ver_personas=rbac.puede(request.user, CAP_VER_CIUDADANO)
        )
        return Response(MapaDePlazasSerializer({"caso": caso, "sectores": sectores}).data)


# El ingreso directo y el aviso a la mesa van al final y en sus propias vistas a propósito
# (decisión 4 del PM): se tienen que poder sacar sin tocar el resto.


class IngresoDirectoView(_VistaDeLlegadas):
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @extend_schema(
        request={"multipart/form-data": IngresoDirectoEnvioSerializer},
        responses={
            201: IngresoDirectoSerializer,
            200: OpenApiResponse(
                response=IngresoDirectoSerializer,
                description="Reenvío: ese `uuid_cliente` ya había creado el caso y se devuelve el mismo.",
            ),
            400: _400(
                "Lo mismo que el envío de M1 (§6) salvo la dirección, que es opcional; `plazas`: no hay camas "
                "libres; `dispositivo`: no recibe familias."
            ),
            401: _SIN_TOKEN,
            403: _SIN_ADMITIR,
            404: _AJENO,
            409: OpenApiResponse(
                description="`code: UUID_EN_USO`: ese `uuid_cliente` ya creó un caso de otro usuario."
            ),
        },
        description=(
            "M2-6 «Ingresar igual»: la familia llegó sin derivación. Crea el caso de origen dispositivo con el "
            "ingreso en curso, reserva las camas que alcancen y deja las N filas. **Idempotente** por "
            "`uuid_cliente`: es lo único de M2 que la app encola sin señal."
        ),
    )
    def post(self, request, dispositivo_id):
        dispositivo = self._dispositivo(request, dispositivo_id)
        entrada = IngresoDirectoEnvioSerializer(data=request.data)
        if not entrada.is_valid():
            return _respuesta_de_validacion(entrada.errors)
        caso, respuesta = self._ejecutar(
            lambda: servicio_alojar.ingreso_directo(
                dispositivo=dispositivo,
                usuario=request.user,
                datos_formulario1=entrada.datos_formulario1(),
                uuid_cliente=entrada.validated_data["uuid_cliente"],
            )
        )
        if respuesta is not None:
            return respuesta
        caso_leido, datos = _filas(caso.pk)
        cuerpo = {
            "caso": caso_leido,
            "reservadas": caso.reservadas,
            "faltantes": caso.faltantes,
            "integrantes": datos["integrantes"],
        }
        return Response(IngresoDirectoSerializer(cuerpo).data, status=_creado_o_reenvio(caso.ya_existia))


class AvisarALaMesaView(_VistaDeLlegadas):
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @extend_schema(
        request={"multipart/form-data": IngresoDirectoEnvioSerializer},
        responses={
            201: AvisoALaMesaSerializer,
            200: OpenApiResponse(
                response=AvisoALaMesaSerializer,
                description="Reenvío: ese `uuid_cliente` ya había creado el caso y se devuelve el mismo.",
            ),
            400: _400("Lo mismo que el envío de M1 (§6) salvo la dirección, que es opcional."),
            401: _SIN_TOKEN,
            403: _SIN_ADMITIR,
            404: _AJENO,
            409: OpenApiResponse(
                description="`code: UUID_EN_USO`: ese `uuid_cliente` ya creó un caso de otro usuario."
            ),
        },
        description=(
            "M2-6 «Avisar a la mesa»: la familia está en la puerta y no hay derivación. Crea el caso `NUEVO` con la "
            "marca «En la puerta de …»; la mesa lo deriva y la guardia busca de nuevo. No exige camas libres. "
            "Idempotente por `uuid_cliente`."
        ),
    )
    def post(self, request, dispositivo_id):
        dispositivo = self._dispositivo(request, dispositivo_id)
        entrada = IngresoDirectoEnvioSerializer(data=request.data)
        if not entrada.is_valid():
            return _respuesta_de_validacion(entrada.errors)
        caso, respuesta = self._ejecutar(
            lambda: servicio_alojar.avisar_a_la_mesa(
                dispositivo=dispositivo,
                usuario=request.user,
                datos_formulario1=entrada.datos_formulario1(),
                uuid_cliente=entrada.validated_data["uuid_cliente"],
            )
        )
        if respuesta is not None:
            return respuesta
        caso_leido = CasoEmergencia.objects.select_related("grupo").get(pk=caso.pk)
        return Response(AvisoALaMesaSerializer({"caso": caso_leido}).data, status=_creado_o_reenvio(caso.ya_existia))
