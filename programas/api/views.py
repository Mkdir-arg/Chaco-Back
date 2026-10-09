"""API REST de la app de campo de Becas (#82).

Auth por token (DRF authtoken). El territorial solo ve/gestiona SUS relevamientos
y formularios. Capacidad requerida: ``becas.campo``.
"""

import logging

from django.db import transaction
from django.db.models import Count
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.decorators import (
    action,
    api_view,
    authentication_classes,
    permission_classes,
    throttle_classes,
)
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.routers import APIRootView
from rest_framework.throttling import UserRateThrottle

from core.rbac import puede
from core.services.throttle import (
    auth_ip_bloqueada,
    rate_limit_bloqueado,
    rate_limit_excedido,
    registrar_auth_fallida_por_ip,
)
from programas.api.serializers import (
    AdjuntoFormularioSerializer,
    ConsultaPersonaRespuestaSerializer,
    ConsultaPersonaSerializer,
    FormularioListSerializer,
    FormularioSerializer,
    RelevamientoDetailSerializer,
    RelevamientoListSerializer,
)
from programas.models import Formulario, Relevamiento
from programas.services import campo
from programas.services.becas import formulario_por_client_uuid, resolver_ciudadano_offline
from programas.services.identidad import ORIGEN_PADRON, ORIGEN_PERSONAS, identificar
from programas.services.padron import datos_de_fila, fila_padron, normalizar_dni, objetivo_con_identidad
from programas.services.respuestas import sincronizar_desde_legacy

logger = logging.getLogger(__name__)

CAP = "becas.campo"
DNI_DUPLICADO_MENSAJE = "Este DNI ya fue relevado en este relevamiento."
CASO_RESUELTO_MENSAJE = "El caso ya fue resuelto: el archivo que ya tiene ese campo no se puede reemplazar."

#: Lo que ``identificar`` devuelve como origen → la marca que guarda el caso.
ORIGEN_VALIDACION_POR_FUENTE = {
    ORIGEN_PADRON: Formulario.OrigenValidacion.PADRON,
    ORIGEN_PERSONAS: Formulario.OrigenValidacion.PERSONAS,
}


def _formulario_por_dni(relevamiento, dni):
    dni = normalizar_dni(dni)
    if not dni:
        return None
    # Dos consultas por índice en vez de un OR sobre la clave del JSON, que
    # recorría todos los formularios del relevamiento (Cambio 91).
    formularios = relevamiento.formularios.order_by("creado", "pk")
    return formularios.filter(dni_titular=dni).first() or formularios.filter(ciudadano__dni=dni).first()


def _formulario_dni_existe(relevamiento, dni):
    return _formulario_por_dni(relevamiento, dni) is not None


_formulario_por_client_uuid = formulario_por_client_uuid


def _captura_habilitada(relevamiento, capturado_en=None):
    """Permite operar hoy o sincronizar después una captura hecha en fecha."""
    if capturado_en is None:
        return relevamiento.habilitado_en(timezone.now())
    if capturado_en > timezone.now() + campo.ADELANTO_TOLERADO:
        return False
    return relevamiento.habilitado_en(capturado_en)


def _mensaje_pausa(relevamiento):
    pausa = relevamiento.pausa_efectiva
    if not pausa:
        return None
    return f"El relevamiento está pausado: {pausa.pausa_motivo}"


def _respuesta_pausa(relevamiento):
    mensaje = _mensaje_pausa(relevamiento)
    if mensaje:
        return Response({"detail": mensaje, "pausado": True}, status=status.HTTP_409_CONFLICT)
    return None


class CampoBecasPermission(BasePermission):
    """Exige la capacidad ``becas.campo`` (territorial / app de campo)."""

    message = "El usuario no tiene acceso a la app de campo de Becas."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and puede(user, CAP))


class ObtainCampoToken(ObtainAuthToken):
    """Login de la app de campo: valida credenciales y exige ``becas.campo``.

    SEC-26 · dos cubetas, y cada una frena en un momento distinto:

    * **Por usuario, sin mirar la IP** (acá). Es lo contrario de lo que haría un
      ``ScopedRateThrottle``, a propósito: los territoriales entran desde datos
      móviles, detrás del NAT del operador, así que una cubeta por IP estrecha le
      cerraría la app a una región entera por los errores de tipeo de una persona.
      Como la llena cualquiera con solo tipear el usuario de otro, se consulta
      **después** de validar las credenciales y solo si estaban mal: el dueño con
      su clave entra siempre.
    * **Por IP, holgada y compartida con el login web**
      (``AUTH_FALLIDOS_MAX_POR_IP``, 300/10 min por defecto). Es la única que
      rechaza antes de verificar la clave —la paga quien ataca— y es lo que corta
      el password-spray, que la cubeta por usuario no ve porque cambia de usuario
      en cada intento.

    En las dos, solo cuentan los intentos fallidos.
    """

    TOKEN_VENTANA_SEGUNDOS = 600
    TOKEN_MAX_POR_USUARIO = 10

    def _demasiados_intentos(self):
        return Response(
            {"detail": "Demasiados intentos fallidos. Esperá unos minutos antes de volver a probar."},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    def post(self, request, *args, **kwargs):
        if auth_ip_bloqueada(request):
            return self._demasiados_intentos()
        # El recorte a 150 es el de `auth_user.username`: sin él, el usuario tipeado
        # entraba entero en la clave de la caché y un POST con 10 KB de "username"
        # escribía una clave de 10 KB en Redis por intento.
        usuario_pedido = str(request.data.get("username") or "").strip().lower()[:150]
        serializer = self.serializer_class(data=request.data, context={"request": request})
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError:
            registrar_auth_fallida_por_ip(request)
            if usuario_pedido:
                rate_limit_excedido(
                    request,
                    "token_campo",
                    self.TOKEN_MAX_POR_USUARIO,
                    self.TOKEN_VENTANA_SEGUNDOS,
                    sufijo=usuario_pedido,
                    incluir_ip=False,
                )
                if rate_limit_bloqueado(
                    request, "token_campo", self.TOKEN_MAX_POR_USUARIO, sufijo=usuario_pedido, incluir_ip=False
                ):
                    return self._demasiados_intentos()
            raise
        user = serializer.validated_data["user"]
        if not puede(user, CAP):
            return Response(
                {"detail": "El usuario no tiene acceso a la app de campo de Becas."},
                status=status.HTTP_403_FORBIDDEN,
            )
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key, "user_id": user.pk, "username": user.username})


def _pisar_identidad_acreditada(formulario, acreditada):
    """Deja en ``datos_identificacion`` lo que dijo la **fuente** cuando la hay
    (Cambio 57, RN-4).

    ``acreditada`` es el dict de ``datos_de_fila``/``identificar``: su nombre y
    apellido pisan lo que tipeó el territorial, y la fecha de nacimiento y la
    localidad solo si la fuente las trajo.

    Con ``acreditada=None`` —la fuente no respaldó nada— lo único que cambia es
    ``origen: "manual"``, el camino previsto para una carga sin respaldo: el caso
    queda **sin validar** y el nombre tipeado sigue viaje al legajo que arma
    ``resolver_ciudadano_offline``. Ese es el comportamiento heredado del
    Cambio 57 y no lo toca SEC-24; lo que la marca aporta es que el caso no se
    presente como acreditado por una fuente que no lo acreditó.

    Devuelve ``True`` si hay que guardar la columna.
    """
    if not isinstance(formulario.datos_identificacion, dict):
        return False
    actualizado = dict(formulario.datos_identificacion)
    if acreditada:
        actualizado.update(nombre=acreditada["nombre"], apellido=acreditada["apellido"])
        if acreditada.get("fecha_nacimiento"):
            actualizado["fecha_nacimiento"] = acreditada["fecha_nacimiento"]
        if acreditada.get("localidad_id"):
            actualizado["localidad_id"] = acreditada["localidad_id"]
    else:
        actualizado["origen"] = "manual"
    formulario.datos_identificacion = actualizado
    return True


def _actualizar_validacion_identidad(formulario, datos_identificacion=None):
    if formulario.identidad_forzada:
        # La validación manual del revisor (Cambio 55) no la deshace un sync.
        return
    datos = datos_identificacion if isinstance(datos_identificacion, dict) else formulario.datos_identificacion
    datos = datos if isinstance(datos, dict) else {}
    origen = str(datos.get("origen") or "").strip().lower()
    origen_validacion = ""
    campos = []  # un solo UPDATE al final

    if origen in ("scan", "escaneo", "dni_scan"):
        # D-24: el escaneo del código de barras del DNI **sí** cuenta como
        # validación. Es el documento físico leído por la cámara delante de la
        # persona, no un dato que el cliente se autoasignó, y el servidor no
        # tiene forma de re-verificarlo.
        validado = True
        origen_validacion = Formulario.OrigenValidacion.SCAN
    elif origen in ("personas", "gran_base"):
        # SEC-24 · el cliente tampoco puede autovalidarse por acá. Antes
        # alcanzaba con que el request dijera `origen: personas` y trajera
        # cualquier nombre y apellido para que el caso quedara
        # `validado_renaper=True`: un token de campo acreditaba una identidad
        # inventada. Ahora el servidor vuelve a resolverla con la misma cascada
        # del Cambio 57 —padrón de la convocatoria y después Base de Personas— y
        # lo que queda guardado es lo que dijo la fuente, igual que en `padron`.
        resultado = identificar(
            formulario.relevamiento,
            datos.get("dni"),
            datos.get("sexo") or datos.get("genero"),
        )
        validado = bool(resultado["validado"])
        if not validado:
            # Con la fuente caída —o con una identidad que no existe— el caso
            # queda **pendiente**, no validado: lo desbloquea el revisor a mano
            # (Cambio 55). Confiar en el cliente cuando no se lo puede verificar
            # es justamente el agujero de la ficha.
            logger.warning(
                "SEC-24: no se pudo acreditar la identidad que el caso %s declaró como «%s» (error: %s)",
                formulario.pk,
                origen,
                resultado["error"] or "sin respaldo",
            )
        # El log lo ve el operador del servidor; el revisor, no. Sin una línea en
        # la carga, el caso llega a la pantalla de revisión sin validar y sin
        # decir por qué, y la validación manual se hace a ciegas. Las dos
        # situaciones no se resuelven igual: que la fuente **respondiera** y el
        # documento no figure es un dato sobre la persona; que no respondiera no
        # dice nada de ella.
        if validado:
            cambio_observaciones = campo.quitar_observaciones(formulario, campo.PREFIJO_IDENTIDAD_SIN_ACREDITAR)
        else:
            cambio_observaciones = campo.sumar_observacion(
                formulario,
                campo.IDENTIDAD_NO_ENCONTRADA if resultado["no_encontrado"] else campo.IDENTIDAD_FUENTE_SIN_RESPUESTA,
            )
        if cambio_observaciones:
            campos.append("observaciones_carga")
        if _pisar_identidad_acreditada(formulario, resultado["datos"] if validado else None):
            campos.append("datos_identificacion")
        origen_validacion = ORIGEN_VALIDACION_POR_FUENTE.get(resultado["origen"], "") if validado else ""
    elif origen == "padron":
        # Cambio 57, RN-4: el cliente no puede autovalidarse. La fila se busca
        # en el padrón de la convocatoria y, si valida, la identidad es la del
        # padrón —no la que tipeó el territorial—. Acá **no** se sale a la red:
        # el origen declarado es el padrón y es el padrón el que tiene que
        # respaldarlo.
        fila = fila_padron(
            formulario.relevamiento,
            datos.get("dni"),
            datos.get("sexo") or datos.get("genero"),
        )
        validado = bool(fila is not None and fila.tiene_identidad)
        if _pisar_identidad_acreditada(formulario, datos_de_fila(fila) if validado else None):
            campos.append("datos_identificacion")
        origen_validacion = Formulario.OrigenValidacion.PADRON if validado else ""
    elif origen == "manual":
        validado = False
    else:
        # El cliente nunca puede autovalidarse sin un origen de confianza.
        validado = False

    if formulario.validado_renaper != validado or formulario.origen_validacion != origen_validacion:
        formulario.validado_renaper = validado
        formulario.origen_validacion = origen_validacion
        campos.extend(["validado_renaper", "origen_validacion"])
    if campos:
        formulario.save(update_fields=[*campos, "modificado"])


def _completar_alta(formulario, relevamiento, datos_identificacion):
    """Lo que no necesita el lock del relevamiento y por eso corre después del
    commit del alta (Cambio 91): la validación de identidad, las respuestas por
    clave con la foto de la definición y el legajo.

    Idempotente a propósito: si un envío anterior se cortó a mitad de camino,
    el reintento de la app —que la idempotencia por ``client_uuid`` devuelve
    como existente— completa lo que faltó.
    """
    _actualizar_validacion_identidad(formulario, datos_identificacion)
    # Cambio 58: la app manda el contrato anterior (data por pk + columnas
    # fijas); acá se traduce a respuestas por clave y se guarda la foto de la
    # definición que respondió (D3).
    sincronizar_desde_legacy(formulario, relevamiento)
    # G1-05: recién acá hay foto y respuestas por clave, que es lo que el motor
    # de condiciones necesita. Va **antes** de `resolver_ciudadano_offline`
    # porque esa función borra `datos_identificacion` al vincular el legajo.
    campo.aplicar_revision(
        formulario,
        campo.revisar_carga(formulario, relevamiento, identidad=datos_identificacion),
    )
    resolver_ciudadano_offline(formulario)


def _alta_incompleta(formulario):
    """¿Un envío anterior se cortó después de insertar el caso? Se nota en que
    no tiene la foto de la definición o en que la identificación offline sigue
    sin resolverse a un legajo."""
    datos = formulario.datos_identificacion if isinstance(formulario.datos_identificacion, dict) else {}
    return not formulario.definicion or (not formulario.ciudadano_id and bool(datos.get("dni")))


def _formulario_fresco(pk):
    """El caso como quedó después de completarlo, con su legajo en la misma
    consulta: es lo que se le devuelve a la app."""
    return Formulario.objects.select_related("ciudadano").get(pk=pk)


def _relevamientos_para_identificar(user, relevamiento_id):
    """Con qué padrones se identifica a una persona desde la app (Cambio 57;
    con herencia por relevamiento desde el Cambio 74).

    Si la app manda el relevamiento, ese; si no, todos los vigentes del
    territorial (la app vieja no manda nada).
    """
    if relevamiento_id:
        rel = Relevamiento.objects.filter(pk=relevamiento_id, territorial=user).select_related("convocatoria").first()
        return [rel] if rel else []
    return list(
        Relevamiento.objects.filter(
            territorial=user,
            estado__in=[Relevamiento.Estado.ASIGNADO, Relevamiento.Estado.EN_CURSO],
        )
        .select_related("convocatoria")
        .order_by("-convocatoria__fecha_inicio", "pk")
    )


class ConsultaPersonasThrottle(UserRateThrottle):
    """SEC-25 · tope de la consulta de identidad de la app (``personas_campo``).

    **Por usuario, no por IP** (``UserRateThrottle`` toma ``request.user.pk``
    cuando hay sesión o token, que es siempre acá: el permiso corre antes que el
    throttle y un anónimo ya se fue en 403). Una cubeta por IP le cerraría la
    consulta a toda una región: los territoriales salen por el NAT de la
    operadora móvil. Es además la razón por la que esto **no** toca
    ``NUM_PROXIES``, que vale distinto en DEV (nginx) y en ECOM (ingress).

    El 429 no rompe nada en el teléfono instalado: ``RelevamientoDetailScreen``
    atrapa el error de la consulta, cae a carga manual y el caso entra sin
    validar (``Chaco-mobile@a66c2d3``). No pasa por la cola de sincronización,
    así que no hay ``FAILED_PERMANENT`` posible.
    """

    scope = "personas_campo"


@extend_schema(
    request=ConsultaPersonaSerializer,
    responses={
        200: ConsultaPersonaRespuestaSerializer,
        400: OpenApiResponse(description="Falta el DNI o el sexo no es F ni M."),
        404: OpenApiResponse(description="No se la pudo identificar, o Base de Personas la informa fallecida."),
        429: OpenApiResponse(description="Se superó el tope de consultas de identidad del usuario."),
        502: OpenApiResponse(description="Base de Personas falló."),
    },
)
@api_view(["POST"])
@authentication_classes([TokenAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated, CampoBecasPermission])
@throttle_classes([ConsultaPersonasThrottle])
def consultar_persona_becas(request):
    entrada = ConsultaPersonaSerializer(data=request.data)
    if not entrada.is_valid():
        # El cuerpo del 400 es el de siempre: la app en producción lee `error`,
        # no el diccionario de campos que devolvería `raise_exception=True`.
        return Response(
            {"success": False, "error": "DNI y sexo (F o M) son requeridos."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    dni = entrada.validated_data["dni"]
    sexo = entrada.validated_data["sexo"]

    # Cascada del Cambio 57 en el servidor: padrón de la convocatoria → Base de
    # Personas (si está activa) → manual. Mismo contrato de respuesta que antes;
    # se suma ``origen`` para que la app lo repita en ``datos_identificacion``.
    relevamientos = _relevamientos_para_identificar(request.user, entrada.validated_data.get("relevamiento"))
    # El padrón efectivo se mira para todos los relevamientos vigentes de una
    # vez; la Gran Base se consulta una sola vez (no depende del relevamiento).
    elegido = objetivo_con_identidad(relevamientos, dni, sexo) or (relevamientos[0] if relevamientos else None)
    resultado = identificar(elegido, dni, sexo)

    if resultado["fallecido"]:
        return Response(
            {"success": False, "fallecido": True, "error": "Base de Personas informa que la persona falleció."},
            status=status.HTTP_404_NOT_FOUND,
        )
    if not resultado["validado"]:
        if resultado["error"] and not resultado["no_encontrado"]:
            # La Gran Base falló (no "no la encontró"): 502, como antes.
            return Response({"success": False, "error": resultado["error"]}, status=status.HTTP_502_BAD_GATEWAY)
        return Response(
            {
                "success": False,
                "error": resultado["error"]
                or "La persona no figura con datos en el padrón y Base de Personas no pudo validarla.",
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    datos = dict(resultado["datos"] or {})
    datos.update(dni=dni, sexo=sexo)
    return Response({"success": True, "origen": resultado["origen"], "data": datos, "datos_api": {}})


class RaizApiCampo(APIRootView):
    """La raíz ``/api/becas/`` (R0-04).

    Desde SEC-01 la API entera exige sesión y el router dejaba su vista raíz con
    la autenticación por defecto: un ``Authorization: Token`` —el único que usa
    la app— no autenticaba y la raíz devolvía 403 mientras todo lo que cuelga de
    ella devolvía 200. La app en producción **no la consulta** (verificado en
    ``Chaco-mobile@a66c2d3``, el release del 21/08: su ``initializeWafSession``
    pide ``/``, la raíz del sitio, no la de la API), así que esto no cambia nada
    para el teléfono; lo que arregla es que la raíz deje de contradecir a su
    propio namespace.
    """

    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated, CampoBecasPermission]


class RelevamientoViewSet(viewsets.ReadOnlyModelViewSet):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated, CampoBecasPermission]
    # G1-03: la agenda y los casos de un relevamiento se sirven **completos**.
    # La paginación global de DRF corta en 10 y la app no sigue `next`
    # (`relevamientoService.js`: `payload?.results` y nada más), así que con 40
    # casos cargados `dniYaRelevado` solo veía los 10 últimos y el territorial
    # volvía a cargar a alguien ya relevado; con más de 10 relevamientos
    # vigentes, la agenda y la caché offline mostraban 10. Las dos listas están
    # acotadas por naturaleza: la agenda, a lo vigente del territorial; los
    # casos, al cupo del relevamiento.
    pagination_class = None
    # RED-37: solo para el esquema. `get_queryset()` —que es el que corre— pisa
    # esto entero, pero necesita `self.request.user` y al generar el esquema no
    # hay request: sin el atributo, drf-spectacular no podía deducir el tipo de
    # `{id}` y lo publicaba como `string`. `basename` está declarado en
    # `api_urls.py`, así que el router no lo mira.
    queryset = Relevamiento.objects.none()

    def get_queryset(self):
        queryset = (
            Relevamiento.objects.filter(territorial=self.request.user)
            # La cadena de pausa (segmento → programa y subsegmento → segmento →
            # programa) y el diseño del formulario vienen en el mismo SELECT:
            # antes cada relevamiento del listado los leía aparte y el detalle
            # y el alta los volvían a pedir con el lock tomado (Cambio 91).
            .select_related(
                "convocatoria__segmento__programa",
                "convocatoria__subsegmento__segmento__programa",
                "convocatoria__diseno",
            )
            .annotate(formularios_count=Count("formularios"))
            .order_by("-fecha_asignada")
        )
        if self.action == "list":
            ahora = timezone.now()
            # La agenda del territorial incluye lo vigente y lo próximo. Las
            # acciones operativas siguen validando que ya haya comenzado.
            queryset = queryset.filter(fecha_hasta__gte=ahora).order_by("fecha_asignada", "nombre")
        return queryset

    def get_serializer_class(self):
        if self.action == "retrieve":
            return RelevamientoDetailSerializer
        return RelevamientoListSerializer

    @action(detail=True, methods=["post"])
    def iniciar(self, request, pk=None):
        rel = self.get_object()
        if respuesta := _respuesta_pausa(rel):
            return respuesta
        capturado_en = request.data.get("capturado_en")
        if capturado_en:
            try:
                capturado_en = serializers.DateTimeField().to_internal_value(capturado_en)
            except serializers.ValidationError:
                return Response(
                    {"capturado_en": "La fecha de captura no es válida."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        if not _captura_habilitada(rel, capturado_en):
            return Response(
                {"detail": "Solo se puede relevar dentro del período asignado."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if rel.estado == Relevamiento.Estado.EN_CURSO:
            return Response(RelevamientoListSerializer(rel).data)
        if rel.estado != Relevamiento.Estado.ASIGNADO:
            return Response({"detail": "Solo se puede iniciar un relevamiento asignado."}, status=400)
        rel.estado = Relevamiento.Estado.EN_CURSO
        rel.save(update_fields=["estado", "modificado"])
        return Response(RelevamientoListSerializer(rel).data)

    @action(detail=True, methods=["post"])
    def finalizar(self, request, pk=None):
        rel = self.get_object()
        if respuesta := _respuesta_pausa(rel):
            return respuesta
        capturado_en = request.data.get("capturado_en")
        if capturado_en:
            try:
                capturado_en = serializers.DateTimeField().to_internal_value(capturado_en)
            except serializers.ValidationError:
                return Response(
                    {"capturado_en": "La fecha de captura no es válida."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        if not _captura_habilitada(rel, capturado_en):
            return Response(
                {"detail": "Solo se puede relevar dentro del período asignado."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        ya_cerrado = (Relevamiento.Estado.FINALIZADO, Relevamiento.Estado.EN_REVISION)
        if rel.estado in ya_cerrado and campo.en_gracia(rel):
            # G1-04: la cola offline sube primero las personas y después el
            # «finalizar». Si el cron cerró el relevamiento en el medio, el
            # cierre ya ocurrió: devolverle un 400 a la app lo deja como
            # `FAILED_PERMANENT` y le muestra un error por algo que ya está
            # hecho. Idempotente, igual que `iniciar` con un EN_CURSO.
            # `FINALIZANDO` **no** entra acá: ese sí tiene que terminar de pasar
            # a `FINALIZADO`, que es el camino normal.
            return Response(RelevamientoListSerializer(rel).data)
        if rel.estado not in (Relevamiento.Estado.EN_CURSO, Relevamiento.Estado.FINALIZANDO):
            return Response({"detail": "El relevamiento no está en curso."}, status=400)
        rel.estado = Relevamiento.Estado.FINALIZADO
        rel.fecha_finalizado = timezone.now()
        rel.save(update_fields=["estado", "fecha_finalizado", "modificado"])
        return Response(RelevamientoListSerializer(rel).data)

    @action(detail=True, methods=["post"])
    def reabrir(self, request, pk=None):
        rel = self.get_object()
        if respuesta := _respuesta_pausa(rel):
            return respuesta
        if not rel.habilitado_en(timezone.now()):
            return Response(
                {"detail": "Solo se puede relevar dentro del período asignado."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if rel.estado != Relevamiento.Estado.FINALIZADO:
            return Response({"detail": "Solo se puede reabrir un relevamiento finalizado."}, status=400)
        rel.estado = Relevamiento.Estado.EN_CURSO
        rel.fecha_finalizado = None
        rel.save(update_fields=["estado", "fecha_finalizado", "modificado"])
        return Response(RelevamientoListSerializer(rel).data)

    @action(detail=True, methods=["get", "post"])
    def formularios(self, request, pk=None):
        rel = self.get_object()
        if request.method == "GET":
            # G1-03: lista plana y **sin** `data`. `FormularioSerializer`
            # arrastra el JSON de respuestas del contrato anterior (~7 KB por
            # caso) y de este listado la app solo lee el nombre, el DNI y el
            # estado para la lista de personas y para avisar «DNI ya relevado».
            qs = (
                rel.formularios.select_related("ciudadano")
                # Las cuatro columnas pesadas de la fila: ninguna se sirve acá y
                # traerlas es lo que pone el listado cerca del `read_timeout`.
                .defer("data", "respuestas", "definicion", "datos_siis")
                .order_by("-creado")
            )
            return Response(FormularioListSerializer(qs, many=True).data)

        if respuesta := _respuesta_pausa(rel):
            return respuesta

        serializer = FormularioSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        capturado_en = serializer.validated_data.get("capturado_en")
        client_uuid = serializer.validated_data.get("client_uuid")
        datos_identificacion = serializer.validated_data.get("datos_identificacion") or {}
        dni = normalizar_dni(datos_identificacion.get("dni"))
        datos_identificacion["dni"] = dni
        # Con el lock del relevamiento tomado queda solo lo que el lock protege:
        # estado y período de la fila fresca, idempotencia por client_uuid,
        # cupo, duplicado y el insert. La identidad, las respuestas y el legajo
        # salen después del commit (Cambio 91, el mismo patrón que el link
        # público): cada consulta de más acá adentro la pagan en cola los otros
        # dispositivos que sincronizan, y el que espera más de 10 s se lleva un
        # 500 por el read_timeout de MySQL.
        with transaction.atomic():
            # Evita que dos dispositivos inserten simultáneamente el mismo DNI.
            bloqueado = Relevamiento.objects.select_for_update().get(pk=rel.pk)
            # La convocatoria y su cadena de pausa ya vinieron cargadas con el
            # relevamiento: se reutilizan para no releerlas con el lock tomado.
            # Lo que el lock decide —estado, fechas, pausa propia, cupo— es de
            # la fila recién leída.
            bloqueado.convocatoria = rel.convocatoria
            # G1-04: una captura hecha en fecha entra aunque el cron ya haya
            # cerrado el relevamiento, mientras dure la gracia; se marca para
            # que la revisión lo sepa. Lo que se rechaza es lo que no se puede
            # aceptar: fuera del período, del futuro, o con la gracia vencida.
            decision = campo.evaluar_captura(bloqueado, capturado_en)
            if decision.rechaza:
                return Response({"detail": decision.detalle}, status=decision.status)
            existente = _formulario_por_client_uuid(bloqueado, client_uuid) if client_uuid else None
            if existente is None:
                if bloqueado.formularios.count() >= bloqueado.cupo_maximo:
                    return Response(
                        {
                            "detail": "Se alcanzó el cupo del relevamiento. No se pueden cargar nuevas personas.",
                            "code": "CUPO_RELEVAMIENTO_COMPLETO",
                            "cupo_maximo": bloqueado.cupo_maximo,
                        },
                        status=status.HTTP_409_CONFLICT,
                    )
                formulario_existente = _formulario_por_dni(bloqueado, dni)
                formulario = serializer.save(
                    relevamiento=bloqueado,
                    created_by=request.user,
                    conflicto_duplicado=formulario_existente is not None,
                    duplicado_de=formulario_existente,
                    sincronizado_tarde=decision.tardia,
                )
        if existente is not None:
            # Doble envío o reintento de la app. Si el envío anterior se cortó
            # después del commit (sin respuestas por clave, sin legajo), se
            # completa acá en vez de devolverlo a medias.
            if _alta_incompleta(existente):
                _completar_alta(existente, rel, datos_identificacion)
                existente = _formulario_fresco(existente.pk)
            return Response(FormularioSerializer(existente).data, status=status.HTTP_200_OK)
        _completar_alta(formulario, rel, datos_identificacion)
        return Response(FormularioSerializer(_formulario_fresco(formulario.pk)).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path="dni-existe")
    def dni_existe(self, request, pk=None):
        rel = self.get_object()
        dni = normalizar_dni(request.query_params.get("dni"))
        if not dni:
            return Response({"dni": "El DNI es requerido."}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"existe": _formulario_dni_existe(rel, dni)})


class FormularioViewSet(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """El caso ya cargado: se lee y se le suben los archivos. **No se edita.**

    SEC-23 · tenía ``UpdateModelMixin`` y ``perform_update`` no miraba el estado
    del caso: con el token, un ``PATCH`` semanas después sobre un caso APROBADO
    cambiaba el apoderado o ``datos_identificacion`` y volvía a disparar
    ``resolver_ciudadano_offline``. El sync offline legítimo **solo crea**
    casos —``POST relevamientos/<id>/formularios/``, idempotente por
    ``client_uuid``— y ni la build instalada (``Chaco-mobile@a66c2d3``) ni el
    ``main`` del repo de la app hacen un PATCH: no hay ni una sola llamada con
    método ``PATCH`` o ``PUT`` en todo ``src/``. Sin el mixin el router deja de
    mapear los dos verbos y la ruta contesta 405.
    """

    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated, CampoBecasPermission]
    parser_classes = [JSONParser, FormParser, MultiPartParser]
    serializer_class = FormularioSerializer
    # RED-37, igual que en `RelevamientoViewSet`: solo para el esquema.
    queryset = Formulario.objects.none()

    def get_queryset(self):
        return Formulario.objects.filter(relevamiento__territorial=self.request.user).select_related(
            "relevamiento", "ciudadano"
        )

    @action(detail=True, methods=["get", "post"])
    def adjuntos(self, request, pk=None):
        """Sube (multipart) o lista los archivos de los campos tipo ARCHIVO del
        formulario (fotos DNI, certificado de domicilio, etc. — #82).

        Reemplaza el placeholder ``{"pendiente_upload": true}`` que la app de
        campo guardaba en ``data`` sin subir nunca el archivo real.

        G1-07: **un archivo por campo**. El POST se puede repetir —la cola
        offline reintenta, y el territorial vuelve a sacar la foto cuando sale
        movida— y antes cada repetición dejaba una fila más, con la revisión
        quedándose con la **más vieja**. Ahora reemplaza. A qué caso se sube ya
        lo decide ``get_queryset`` (solo los del propio territorial); lo que se
        suma acá es que el campo exista en el formulario de ese relevamiento.

        SEC-23: sobre un caso que el backoffice ya resolvió, el reemplazo
        contesta **409 ``CASO_RESUELTO``** y el campo vacío entra con una
        observación para la revisión.
        """
        formulario = self.get_object()
        if request.method == "GET":
            return Response(AdjuntoFormularioSerializer(formulario.adjuntos.all(), many=True).data)

        if respuesta := _respuesta_pausa(formulario.relevamiento):
            return respuesta

        if not _captura_habilitada(formulario.relevamiento, formulario.capturado_en):
            return Response(
                {"detail": "El relevamiento está fuera de su período asignado."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = AdjuntoFormularioSerializer(data=request.data, context={"formulario": formulario})
        serializer.is_valid(raise_exception=True)
        pregunta_global = serializer.validated_data.get("pregunta_global")
        requisito_nativo = serializer.validated_data.get("requisito_nativo")

        # SEC-23: lo que no se puede hacer sobre un caso ya resuelto es
        # **reemplazar** su documentación. El POST pisa el archivo del campo
        # (G1-07), así que sin esto un token de campo cambiaba la foto del DNI de
        # un caso APROBADO semanas después y sin dejar rastro. El guard mira
        # entonces lo que importa: que ese campo ya tenga un adjunto.
        #
        # El campo **vacío** se acepta, y no es una concesión: rechazarlo le
        # costaba a la app todo el caso. Ante el 409 la cola marca la operación
        # `FAILED_PERMANENT` (`relevamientoService.js:1487`) y
        # `hasPendingFormularioOperations` (`:1030`) cuenta las fallidas, así que
        # el `finalizar_relevamiento` del teléfono queda bloqueado **para
        # siempre** y con él se pierden todos los adjuntos pendientes del caso,
        # no solo el que llegó tarde. El archivo entra y la revisión se entera
        # por `observaciones_carga`, que es el patrón del Cambio 178 (#627).
        #
        # 409 y no 400 porque es un conflicto de estado, y es el código que ya
        # usa el resto de la familia (cupo lleno, pausa).
        resuelto = formulario.estado != Formulario.Estado.ENVIADO
        if (
            resuelto
            and formulario.adjuntos.filter(pregunta_global=pregunta_global, requisito_nativo=requisito_nativo).exists()
        ):
            return Response(
                {"detail": CASO_RESUELTO_MENSAJE, "code": "CASO_RESUELTO", "estado": formulario.estado},
                status=status.HTTP_409_CONFLICT,
            )

        adjunto = campo.guardar_adjunto(
            formulario,
            archivo=serializer.validated_data["archivo"],
            pregunta_global=pregunta_global,
            requisito_nativo=requisito_nativo,
        )
        if resuelto:
            campo.observar_adjunto(
                formulario,
                pregunta_global or requisito_nativo,
                plantilla=campo.ADJUNTO_TARDIO,
                estado=formulario.get_estado_display(),
            )
        # Sigue siendo 201 también cuando reemplazó: la app instalada
        # (`Chaco-mobile@a66c2d3`) clasifica la subida por el código, y un 200
        # que hoy no espera sería un cambio de contrato que pide release. Lo que
        # cambia es que la respuesta trae el `id` del adjunto **que vale**, no el
        # de una fila nueva que duplicaba a la anterior.
        return Response(AdjuntoFormularioSerializer(adjunto).data, status=status.HTTP_201_CREATED)
