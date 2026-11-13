"""API de campo del módulo Emergencia: base, perfil y M1 (el Formulario 1 del agente).

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
* **La consulta de identidad** es la de Becas (``views.responder_consulta_de_persona``) con
  permiso propio y **la misma cubeta** de throttle: un usuario con los dos módulos no
  duplica su cuota cambiando de ruta (hallazgo H2 del plan).
"""

from django.core.exceptions import PermissionDenied, ValidationError
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.routers import APIRootView
from rest_framework.views import APIView

from programas.api.serializers import ConsultaPersonaRespuestaSerializer, ConsultaPersonaSerializer
from programas.api.serializers_emergencia import (
    CasoEmergenciaCreadoSerializer,
    CasoEmergenciaEnvioSerializer,
    LocalidadEmergenciaSerializer,
    MiCasoEmergenciaSerializer,
    PerfilEmergenciaSerializer,
)
from programas.api.views import ConsultaPersonasThrottle, responder_consulta_de_persona
from programas.api.views_inspecciones import _respuesta_400
from programas.models import CasoEmergencia
from programas.selectors.emergencia_campo import casos_relevados_por, localidades_para_relevar
from programas.services.emergencia import UuidEnUso, crear_caso
from programas.services.emergencia_programa import (
    CAP_EMERGENCIA_RELEVAR,
    modulo_habilitado,
    puede_en_programa_emergencia,
    roles_en_app,
)

MENSAJE_SIN_MODULO = "El usuario no tiene acceso al módulo Emergencia."
MENSAJE_SIN_RELEVAR = (
    "El usuario no tiene permiso para relevar familias en Emergencia. "
    "Pedile a quien administra los usuarios que te sume el rol de agente territorial."
)
CODIGO_SIN_MODULO = "SIN_MODULO"
CODIGO_VALIDACION = "VALIDACION"
CODIGO_UUID_EN_USO = "UUID_EN_USO"

_AUTENTICACION = [TokenAuthentication, SessionAuthentication]

_SIN_TOKEN = OpenApiResponse(description="Sin token o token inválido.")
_SIN_MODULO = OpenApiResponse(description="El usuario no abre el módulo Emergencia: `code: SIN_MODULO`.")
_SIN_RELEVAR = OpenApiResponse(
    description="El usuario no tiene `emergencia.relevar` en el programa Emergencia: `code: SIN_MODULO`."
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
            "Qué accesos del módulo abre el usuario, para armar la pantalla inicial (RU-5). Al menos uno de los "
            "dos es verdadero: si no abriera ninguno, la respuesta sería el 403."
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
