"""API de campo, «Plazas y estadías» (Cambio 596): lectura de los edificios, el mapa de camas y las estadías.

Vale para **cualquier** institución y edificio, de Emergencia o no: quién ve qué es el alcance de siempre
(``dispositivo.ver`` con ``q_edificios_en_alcance`` y ``edificio_de_la_institucion``), igual que la página operativa del
edificio de la web. Un edificio ajeno, desvinculado o fuera de alcance es **404**, igual que un id que no existe.
El permiso de módulo es el de todo el namespace (``modulo_habilitado``).

Las vistas solo orquestan; el armado y las reglas están en ``programas.services.plazas_app``.
"""

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.utils.urls import replace_query_param

from programas.api.serializers_emergencia_plazas import (
    EdificioDeLaAppSerializer,
    MapaDelEdificioSerializer,
    PaginaDeEstadiasSerializer,
)
from programas.api.views_emergencia import _SIN_MODULO, _SIN_TOKEN, _VistaDeCampo
from programas.services.dispositivos import CAP_VER, dispositivos_en_alcance
from programas.services.edificio_operativo import edificio_de_la_institucion
from programas.services.plazas_app import edificios_de_la_app, estadias_de_la_app, mapa_del_edificio

_FUERA_DE_ALCANCE = OpenApiResponse(
    description=(
        "La institución o el edificio no existen, o no están en el alcance del usuario (`dispositivo.ver`): "
        "las dos cosas contestan lo mismo."
    )
)


class _VistaDeUnEdificio(_VistaDeCampo):
    def _institucion_y_edificio(self, request, dispositivo_id, edificio_id):
        """``(dispositivo, edificio)`` en el alcance de lectura de quien mira; si no, 404."""

        dispositivo = self._o_404(dispositivos_en_alcance(request.user, CAP_VER).select_related("tipo"), dispositivo_id)
        edificio = edificio_de_la_institucion(request.user, dispositivo, edificio_id)
        if edificio is None:
            raise NotFound
        return dispositivo, edificio


class EdificiosDeLaAppView(_VistaDeCampo):
    @extend_schema(
        responses={200: EdificioDeLaAppSerializer(many=True), 401: _SIN_TOKEN, 403: _SIN_MODULO},
        description=(
            "Los edificios que el usuario ve con `dispositivo.ver`, un ítem por par institución-edificio y por "
            "nombre de edificio, con las cifras de sus camas. Sin paginar. Vacía si no ve ninguno."
        ),
    )
    def get(self, request):
        return Response(EdificioDeLaAppSerializer(edificios_de_la_app(request.user), many=True).data)


class MapaDelEdificioView(_VistaDeUnEdificio):
    @extend_schema(
        responses={
            200: MapaDelEdificioSerializer,
            401: _SIN_TOKEN,
            403: _SIN_MODULO,
            404: _FUERA_DE_ALCANCE,
        },
        description=(
            "El mapa de camas de un edificio en una institución: sectores y plazas con su estado, quién las ocupa "
            "(solo con `ciudadano.ver`) y las acciones que el usuario puede ejercer sobre cada una. `puede` resume "
            "las capacidades sobre este edificio."
        ),
    )
    def get(self, request, dispositivo_id, edificio_id):
        dispositivo, edificio = self._institucion_y_edificio(request, dispositivo_id, edificio_id)
        return Response(MapaDelEdificioSerializer(mapa_del_edificio(request.user, dispositivo, edificio)).data)


class EstadiasDelEdificioView(_VistaDeUnEdificio):
    @extend_schema(
        parameters=[
            OpenApiParameter("estado", str, description="`activa` (por defecto) o `egresada`."),
            OpenApiParameter("sector", int, description="Solo las de ese sector; uno ajeno se ignora."),
            OpenApiParameter("page", int, description="Página (25 por página)."),
        ],
        responses={
            200: PaginaDeEstadiasSerializer,
            401: _SIN_TOKEN,
            403: _SIN_MODULO,
            404: _FUERA_DE_ALCANCE,
        },
        description=(
            "Las estadías de las personas de esta institución en este edificio (las que tienen plaza en él), de "
            "la más nueva a la más vieja. Cada una trae `acciones` (`egresar`, `reubicar`) según lo que el usuario "
            "puede hacer, y `persona` solo con `ciudadano.ver`."
        ),
    )
    def get(self, request, dispositivo_id, edificio_id):
        dispositivo, edificio = self._institucion_y_edificio(request, dispositivo_id, edificio_id)
        consulta = request.query_params
        pagina, filas = estadias_de_la_app(
            request.user,
            dispositivo,
            edificio,
            consulta.get("estado", ""),
            consulta.get("sector", ""),
            consulta.get("page"),
        )
        url = request.build_absolute_uri()
        return Response(
            PaginaDeEstadiasSerializer(
                {
                    "count": pagina.paginator.count,
                    "next": replace_query_param(url, "page", pagina.next_page_number()) if pagina.has_next() else None,
                    "previous": (
                        replace_query_param(url, "page", pagina.previous_page_number())
                        if pagina.has_previous()
                        else None
                    ),
                    "results": filas,
                }
            ).data
        )
