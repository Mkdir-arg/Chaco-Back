"""API de campo de Emergencia, M2: llegada de familias (M2-1 a M2-5) y el mapa de camas.

Paridad con la pantalla E6 del backoffice (RU-1): cada vista llama a la **misma** función de
``services.emergencia_alojar`` que la vista web y solo traduce lo que contesta (RU-2), con
``_VistaDeCampo._ejecutar``:

* ``ValidationError`` → 400 por campo (``code: VALIDACION``), con el mensaje del servicio.
* :class:`EstadoCambio` → 409 ``{detail, estado_actual}``: otra guardia —desde su teléfono o
  desde el backoffice—, la mesa o el cron se adelantaron. ``detail`` es el del servicio
  (``_por_que_ya_no``), el mismo en el GET que en el POST. La app recarga.
* ``PermissionDenied`` → 404. No debería llegar: el alcance ya se resolvió acá. Si llega (lo
  sacaron del Equipo entre una línea y la otra), lo mismo que un id ajeno.

Quién entra (plan C2): sin ``dispositivo.admitir`` con alcance en **ningún** dispositivo, 403
``SIN_MODULO`` (`EmergenciaAdmitirPermission`); con ella, un dispositivo, una derivación o un
caso de **otro** dispositivo dan **404**, el mismo cuerpo que un id que no existe, sin nombrar
a nadie (RU-9). Lo que va por ``casos/{id}/`` se resuelve con
``emergencia_ingreso_comun.ingreso_sin_candado``: la misma guarda que usa el servicio.

El ingreso directo y el aviso a la mesa (M2-6) están en ``views_emergencia_sin_derivacion``,
que importa de acá; este módulo no los conoce.
"""

from django.core.exceptions import PermissionDenied
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from core import rbac
from programas.api.serializers_emergencia import (
    AceptacionSerializer,
    AceptarDerivacionEnvioSerializer,
    AgregarIntegranteEnvioSerializer,
    AlojarFamiliaEnvioSerializer,
    BusquedaPorDniSerializer,
    CancelarIngresoEnvioSerializer,
    CerrarConDiferenciaEnvioSerializer,
    CierreDeIngresoSerializer,
    CompletarFichaEnvioSerializer,
    ConfirmacionSerializer,
    ConfirmarIntegranteEnvioSerializer,
    EstadoCambioSerializer,
    FichaCompletadaSerializer,
    IntegranteAgregadoSerializer,
    IntegranteDetalleSerializer,
    IntegrantesDelCasoSerializer,
    MapaDePlazasSerializer,
    RechazarDerivacionEnvioSerializer,
    RechazoSerializer,
)
from programas.api.views_emergencia import (
    _SIN_TOKEN,
    EmergenciaAdmitirPermission,
    EmergenciaModuloPermission,
    _400,
    _creado_o_reenvio,
    _VistaDeCampo,
)
from programas.models import CasoEmergencia, Derivacion
from programas.selectors import emergencia_alojar as selectores_alojar
from programas.selectors.emergencia_mesa import ESTADOS_CON_INTEGRANTES
from programas.services import emergencia_alojar as servicio_alojar
from programas.services.dispositivos import dispositivos_en_alcance
from programas.services.emergencia_programa import CAP_ADMITIR

CAP_VER_CIUDADANO = "ciudadano.ver"

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


class BuscarFamiliaThrottle(UserRateThrottle):
    """Tope de la búsqueda por DNI (``emergencia_buscar``): dice si un DNI está derivado o alojado en la red.

    Sin tope, un token perdido enumera DNIs. Por **usuario**, como ``ConsultaPersonasThrottle``
    (SEC-25), y con cubeta propia: la guardia busca mucho más que lo que consulta identidades.
    """

    scope = "emergencia_buscar"


class _VistaDeLlegadas(_VistaDeCampo):
    """Base de M2: token (o sesión), el módulo abierto y admitir familias en algún dispositivo."""

    permission_classes = [IsAuthenticated, EmergenciaModuloPermission, EmergenciaAdmitirPermission]

    def _admitidos(self, request):
        return dispositivos_en_alcance(request.user, CAP_ADMITIR)

    def _dispositivo(self, request, pk):
        """El dispositivo, **si admite ahí**. El de otro es un 404."""
        return self._o_404(self._admitidos(request).select_related("tipo"), pk)

    def _derivacion(self, request, pk):
        """La derivación, **si es hacia un dispositivo donde admite**. La de otro es un 404 (C2)."""
        return self._o_404(Derivacion.objects.filter(dispositivo__in=self._admitidos(request)), pk)

    def _ingreso(self, request, pk):
        """``(caso, derivacion)`` si la **última** derivación del caso es hacia un dispositivo donde admite. Si no, 404.

        Es la guarda de RU-9 para todo lo que va por ``casos/{id}/``, y la misma del servicio
        (``ingreso_sin_candado``). Sin estados: quien escribe deja que el servicio pregunte el
        estado con el candado puesto.
        """
        try:
            return servicio_alojar.ingreso_sin_candado(pk, request.user)
        except PermissionDenied:
            raise NotFound from None

    def _caso_para_leer(self, request, pk):
        """El caso de :meth:`_ingreso` si su ingreso se aceptó: ``(caso, None)``; si no, ``(None, 409)``.

        Se lee en ``ESTADOS_CON_INTEGRANTES``, los mismos que la ficha de la mesa: el ingreso en
        curso, la familia alojada y el caso cerrado (la app vuelve a M2-3 después de cerrar).
        """
        ingreso, respuesta = self._ejecutar(
            lambda: servicio_alojar.ingreso_sin_candado(pk, request.user, *ESTADOS_CON_INTEGRANTES)
        )
        return (ingreso[0] if ingreso else None), respuesta


def _filas(caso_pk):
    """``(caso, integrantes_de(caso))`` recién leídos: después de una escritura, lo que quedó. **2 consultas.**"""
    caso = CasoEmergencia.objects.select_related("grupo").get(pk=caso_pk)
    return caso, selectores_alojar.integrantes_de(caso)


class BuscarFamiliaView(_VistaDeLlegadas):
    throttle_classes = [BuscarFamiliaThrottle]

    @extend_schema(
        parameters=[OpenApiParameter("dni", str, required=True, description="DNI de cualquiera de la familia.")],
        responses={
            200: BusquedaPorDniSerializer,
            400: _400("`dni` vacío o que no es un DNI."),
            401: _SIN_TOKEN,
            403: _SIN_ADMITIR,
            404: _AJENO,
            429: OpenApiResponse(
                description="Se superó el tope de búsquedas por DNI del usuario (`emergencia_buscar`). Trae `Retry-After`."
            ),
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
        caso, respuesta = self._caso_para_leer(request, pk)
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
        caso, _derivacion = self._ingreso(request, pk)
        datos, respuesta = self._entrada(AgregarIntegranteEnvioSerializer, request)
        if respuesta is not None:
            return respuesta
        integrante, respuesta = self._ejecutar(
            lambda: servicio_alojar.agregar_integrante(
                caso=caso.pk, usuario=request.user, uuid_cliente=datos["uuid_cliente"]
            )
        )
        if respuesta is not None:
            return respuesta
        cuerpo = {
            "integrante": selectores_alojar.integrante_de(caso, integrante.orden),
            "total_declarado": integrante.total_declarado,
        }
        return Response(IntegranteAgregadoSerializer(cuerpo).data, status=_creado_o_reenvio(integrante.ya_estaba))


class IntegranteView(_VistaDeLlegadas):
    @extend_schema(
        responses={200: IntegranteDetalleSerializer, 401: _SIN_TOKEN, 403: _SIN_ADMITIR, 404: _AJENO, 409: _CAMBIO},
        description="Una persona de la familia con su ficha guardada, para completar las secciones 4 a 8 (M2-4).",
    )
    def get(self, request, pk, n):
        caso, respuesta = self._caso_para_leer(request, pk)
        if respuesta is not None:
            return respuesta
        integrante = selectores_alojar.integrante_de(caso, n)
        if integrante is None:
            raise NotFound
        return Response(IntegranteDetalleSerializer(integrante).data)

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
        caso, _derivacion = self._ingreso(request, pk)
        datos, respuesta = self._entrada(CompletarFichaEnvioSerializer, request)
        if respuesta is not None:
            return respuesta
        integrante, respuesta = self._ejecutar(
            lambda: servicio_alojar.completar_ficha(caso=caso.pk, orden=n, usuario=request.user, ficha=datos["ficha"])
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
        caso, _derivacion = self._ingreso(request, pk)
        datos, respuesta = self._entrada(ConfirmarIntegranteEnvioSerializer, request)
        if respuesta is not None:
            return respuesta
        integrante, respuesta = self._ejecutar(
            lambda: servicio_alojar.confirmar_integrante(
                caso=caso.pk,
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
            "integrante": selectores_alojar.integrante_de(caso, n),
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
        caso, _derivacion = self._ingreso(request, pk)
        datos, respuesta = self._entrada(AlojarFamiliaEnvioSerializer, request)
        if respuesta is not None:
            return respuesta
        cerrado, respuesta = self._ejecutar(
            lambda: servicio_alojar.alojar_familia(caso=caso.pk, usuario=request.user, **datos)
        )
        return respuesta if respuesta is not None else Response(_cierre(cerrado))


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
        caso, _derivacion = self._ingreso(request, pk)
        datos, respuesta = self._entrada(CerrarConDiferenciaEnvioSerializer, request)
        if respuesta is not None:
            return respuesta
        cerrado, respuesta = self._ejecutar(
            lambda: servicio_alojar.cerrar_con_diferencia(caso=caso.pk, usuario=request.user, **datos)
        )
        return respuesta if respuesta is not None else Response(_cierre(cerrado))


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
        caso, _derivacion = self._ingreso(request, pk)
        datos, respuesta = self._entrada(CancelarIngresoEnvioSerializer, request)
        if respuesta is not None:
            return respuesta
        cerrado, respuesta = self._ejecutar(
            lambda: servicio_alojar.cancelar_ingreso(caso=caso.pk, usuario=request.user, **datos)
        )
        return respuesta if respuesta is not None else Response(_cierre(cerrado))


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
            _caso, derivacion = self._ingreso(request, caso)
            if derivacion.dispositivo_id != dispositivo.pk:
                raise NotFound
        else:
            caso = None
        sectores = selectores_alojar.plazas_para_caso(
            dispositivo, caso, request.user, puede_ver_personas=rbac.puede(request.user, CAP_VER_CIUDADANO)
        )
        return Response(MapaDePlazasSerializer({"caso": caso, "sectores": sectores}).data)
