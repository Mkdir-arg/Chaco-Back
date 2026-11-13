"""API de campo de Emergencia, M2-6: la familia llegó sin derivación.

«Ingresar igual» (`IngresoDirectoView`) y «Avisar a la mesa» (`AvisarALaMesaView`) van en su
propio módulo a propósito (decisión 4 del PM): se tienen que poder sacar sin tocar el resto.
Para eso alcanza con borrar este archivo y sus dos rutas de ``api_emergencia_urls``: ni la
base (``views_emergencia``) ni las llegadas (``views_emergencia_llegadas``) importan de acá.

Las dos son **idempotentes** por ``uuid_cliente``: es lo único de M2 que la app encola sin señal.
"""

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from programas.api.serializers_emergencia import (
    AvisoALaMesaSerializer,
    IngresoDirectoEnvioSerializer,
    IngresoDirectoSerializer,
)
from programas.api.views_emergencia import _SIN_TOKEN, _400, _creado_o_reenvio, _respuesta_de_validacion
from programas.api.views_emergencia_llegadas import _AJENO, _SIN_ADMITIR, _filas, _VistaDeLlegadas
from programas.models import CasoEmergencia
from programas.services import emergencia_alojar as servicio_alojar


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
