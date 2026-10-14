"""Relevamientos edilicios: listado y asignación del coordinador (P21 · #701).

En pantalla, «Relevamientos»; en el código, `InspeccionEdificio`. Esta pantalla es del
**coordinador** (``inspeccion.asignar``): el agente territorial no la ve, recibe la tarea en
la app. Todo pasa por `programas.services.inspecciones`, que decide quién ve qué, sobre
qué edificios se asigna y a qué agentes; la vista solo arma la página.

Los modales de asignar, reasignar y cancelar se abren con un parámetro GET
(``?asignar=<edificio>``, ``?reasignar=<id>``, ``?cancelar=<id>``) porque el selector de
agentes depende del edificio —el personal de sus instituciones no se ofrece— y el menú de
fila solo sabe navegar. Así cada modal llega armado por el servidor, sin JS propio.

Cuatro solapas, y la última **no es de relevamientos**: «Sin relevar nunca» lista
*edificios* del alcance que no tienen ninguno realizado, que es justo lo que no puede salir
de una tabla de `InspeccionEdificio`. Las píldoras de filtro van **dentro de cada panel**
(`ocultos=("tab", <clave>)`, el patrón de P4): el formulario de filtros es del servidor y
la solapa la cambia Alpine en el navegador, así que un solo oculto arriba mandaba siempre
la solapa que resolvió el servidor y filtrar desde otra volvía a «En curso».

:class:`RelevamientoInformeView` es la pantalla de solo lectura de un relevamiento y **no
es solo del coordinador**: también entra quien opera una institución del edificio, desde la
solapa Infraestructura. Por eso no lleva el mixin de capacidad: la única regla es
`inspecciones_visibles`, y lo ajeno da el mismo 404 que lo inexistente.
"""

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse, QueryDict
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.http import urlencode
from django.views import View
from django.views.generic import TemplateView

from programas.forms_dispositivos import (
    AsignarRelevamientoForm,
    CancelarRelevamientoForm,
    ElegirEdificioForm,
    ReasignarRelevamientoForm,
)
from programas.mixins_dispositivos import DispositivoProgramaPermissionMixin
from programas.models import Dispositivo, InspeccionEdificio
from programas.services.dispositivos import CAP_VER, puede_en_programa_dispositivos, puede_operar_dispositivo
from programas.services.inspecciones import (
    AGENTE_DEBE_SER_EXTERNO,
    CAP_ASIGNAR,
    Situacion,
    agentes_asignables,
    cancelar_inspeccion,
    crear_inspeccion,
    edificios_en_alcance,
    edificios_para_asignar,
    edificios_sin_relevar,
    filtrar_por_situacion,
    informe_de_relevamiento,
    inspecciones_en_curso_por_edificio,
    inspecciones_visibles,
    reasignar_inspeccion,
    resumen_listado,
    situacion_de,
)
from programas.views.ajax_utils import ajax_redirect, is_ajax

#: Parámetros que abren un modal: no son filtros ni se conservan al paginar.
PARAMETROS_DE_MODAL = ("nuevo", "asignar", "reasignar", "cancelar")
PARAMETRO_VOLVER = "volver"
#: Lo que se conserva al elegir el edificio de «Nuevo relevamiento»: la solapa y los filtros.
PARAMETROS_DE_VISTA = ("tab", "estado", "asignado_a")

Estado = InspeccionEdificio.Estado
#: Las solapas de relevamientos de P21: (clave, rótulo, ícono, estado del modelo, orden).
SOLAPAS = (
    ("en_curso", "En curso", "fa-clipboard-list", Estado.ASIGNADA, ("fecha_vencimiento", "pk")),
    ("completados", "Completados", "fa-circle-check", Estado.REALIZADA, ("-realizada_en", "-pk")),
    ("cancelados", "Cancelados", "fa-ban", Estado.CANCELADA, ("-modificado", "-pk")),
)
#: La cuarta solapa no lista relevamientos sino **edificios**: lo que nunca se relevó no
#: tiene fila en `InspeccionEdificio`, así que no puede salir de las otras tres.
SOLAPA_SIN_RELEVAR = "sin_relevar"
SOLAPA_POR_DEFECTO = "en_curso"


def _entero(valor):
    """El id de un parámetro GET, o ``None``. Solo dígitos ASCII: un superíndice o un dígito
    arábigo pasan `isdigit()` y rompen `int()`."""

    valor = (valor or "").strip()
    return int(valor) if valor.isascii() and valor.isdecimal() else None


def _sin(parametros, claves):
    copia = parametros.copy()
    for clave in claves:
        copia.pop(clave, None)
    return copia


def _url_lista(querystring=""):
    """La URL del listado con un querystring saneado: se vuelve a armar, nunca se copia crudo."""

    base = reverse("dispositivos:relevamientos")
    parametros = _sin(QueryDict(querystring or ""), PARAMETROS_DE_MODAL)
    codificado = parametros.urlencode()
    return f"{base}?{codificado}" if codificado else base


def _vence_relativo(fecha, hoy):
    dias = (fecha - hoy).days
    if dias == 0:
        return "vence hoy"
    if dias == 1:
        return "en 1 día"
    if dias > 1:
        return f"en {dias} días"
    if dias == -1:
        return "hace 1 día"
    return f"hace {-dias} días"


def _nombre(usuario):
    return usuario.get_full_name() or usuario.username


class RelevamientoListView(DispositivoProgramaPermissionMixin, TemplateView):
    """P21: los relevamientos que el coordinador puede ver, en cuatro solapas, y sus modales."""

    capacidad_requerida = CAP_ASIGNAR
    template_name = "programas/dispositivos/relevamientos/list.html"
    paginate_by = 25

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        params = self.request.GET
        hoy = timezone.localdate()

        visibles = inspecciones_visibles(user)
        claves = [solapa[0] for solapa in SOLAPAS] + [SOLAPA_SIN_RELEVAR]
        solapa_actual = params.get("tab") if params.get("tab") in claves else SOLAPA_POR_DEFECTO
        situacion = params.get("estado", "")
        situacion = situacion if situacion in dict(Situacion.EN_CURSO) else ""
        asignado_id = _entero(params.get("asignado_a"))

        resumen = resumen_listado(visibles, situacion=situacion, asignado_a_id=asignado_id, hoy=hoy)
        base = visibles.select_related("edificio", "asignado_a")
        if asignado_id:
            base = base.filter(asignado_a_id=asignado_id)
        vista = _sin(params, PARAMETROS_DE_MODAL)
        # Lo que la paginación de cada solapa conserva: los filtros, sin modales, sin la solapa
        # (la pone cada una) y sin las páginas. Nunca vacío: `_paginacion.html` con `filtros_qs`
        # vacío vuelve a copiar todo `request.GET`, modal incluido.
        filtros = _sin(params, PARAMETROS_DE_MODAL + ("tab",) + tuple(f"{c}_page" for c in claves))

        def querystring_de(clave):
            """Lo que la paginación de la solapa conserva: sus filtros, más su propia `tab`."""

            filtros_qs = QueryDict(mutable=True)
            filtros_qs["tab"] = clave
            for nombre in filtros:
                filtros_qs.setlist(nombre, filtros.getlist(nombre))
            return filtros_qs.urlencode()

        # `dispositivo.ver` permite leer el relevamiento, pero no quién lo tiene asignado.
        # La misma regla por lote que `ve_la_asignacion`: coordinar ESE edificio o ser el agente.
        asignaciones_visibles = visibles.filter(
            Q(edificio__in=edificios_en_alcance(user, CAP_ASIGNAR)) | Q(asignado_a_id=user.pk)
        )
        agentes = get_user_model().objects.filter(pk__in=asignaciones_visibles.values("asignado_a"))
        pildora_agente = {
            "nombre": "asignado_a",
            "etiqueta": "Asignado a",
            "opciones": [(str(u.pk), _nombre(u)) for u in agentes.order_by("first_name", "last_name", "username")],
            "valor": str(asignado_id or ""),
        }
        pildora_estado = {"nombre": "estado", "etiqueta": "Estado", "opciones": Situacion.EN_CURSO, "valor": situacion}

        solapas = []
        for clave, etiqueta, icono, estado, orden in SOLAPAS:
            queryset = base.filter(estado=estado).order_by(*orden)
            if clave == "en_curso":
                queryset = filtrar_por_situacion(queryset, situacion, hoy)
            paginator = Paginator(queryset, self.paginate_by)
            # El total ya salió del aggregate de `resumen_listado`, con los mismos filtros:
            # así las tres solapas no suman un COUNT cada una.
            paginator.count = resumen[f"solapa_{clave}"]
            pagina = paginator.get_page(params.get(f"{clave}_page"))
            solapas.append(
                {
                    "clave": clave,
                    "etiqueta": etiqueta,
                    "icono": icono,
                    "total": paginator.count,
                    "pagina": pagina,
                    "filas": list(pagina.object_list),
                    "param": f"{clave}_page",
                    "filtros_qs": querystring_de(clave),
                    # El oculto de las píldoras es la solapa del panel que las dibuja, no la
                    # que resolvió el servidor: filtrar desde Completados tiene que quedarse ahí.
                    "ocultos": [("tab", clave)],
                    # «Estado» solo filtra lo que está en curso: en las otras no se ofrece.
                    "pildoras": [pildora_estado, pildora_agente] if clave == "en_curso" else [pildora_agente],
                    "hay_filtros": bool(asignado_id or (clave == "en_curso" and situacion)),
                    "vacio_titulo": f"Todavía no hay relevamientos {etiqueta.lower()}",
                    "url_sin_filtros": f"{reverse('dispositivos:relevamientos')}?tab={clave}",
                }
            )

        en_alcance = set(
            edificios_en_alcance(user, CAP_ASIGNAR)
            .filter(pk__in={r.edificio_id for s in solapas for r in s["filas"]})
            .values_list("pk", flat=True)
        )
        for solapa in solapas:
            for relevamiento in solapa["filas"]:
                ve_asignacion = relevamiento.edificio_id in en_alcance or relevamiento.asignado_a_id == user.pk
                relevamiento.agente_visible = _nombre(relevamiento.asignado_a) if ve_asignacion else ""
                self._preparar_fila(relevamiento, hoy, en_alcance, vista, solapa["clave"])

        edificios_libres = edificios_para_asignar(user)
        sin_relevar = self._solapa_sin_relevar(user, params, vista, querystring_de)
        context.update(
            {
                "solapas": solapas,
                "sin_relevar": sin_relevar,
                # La barra de solapas es una sola; los paneles, no: el cuarto lista edificios.
                "solapas_nav": [*solapas, sin_relevar],
                "solapa_actual": solapa_actual,
                "resumen": resumen,
                "ocultos_nuevo": [(k, params[k]) for k in PARAMETROS_DE_VISTA if params.get(k)],
                "agente_externo": AGENTE_DEBE_SER_EXTERNO,
                "volver_qs": vista.urlencode(),
                "url_nuevo": reverse("dispositivos:relevamientos") + "?nuevo=1",
            }
        )
        self._preparar_modales(context, user, params, edificios_libres)
        return context

    def _solapa_sin_relevar(self, user, params, vista, querystring_de):
        """La cuarta solapa: edificios del alcance **sin ningún relevamiento realizado**.

        El `Paginator` hace su propio `COUNT` —no sale del aggregate de `resumen_listado`,
        que cuenta relevamientos y acá se cuentan edificios—, y el agente de lo que ya está
        en curso se trae de una sola vez para toda la página: por fila sería un N+1.
        """

        paginator = Paginator(edificios_sin_relevar(user), self.paginate_by)
        pagina = paginator.get_page(params.get(f"{SOLAPA_SIN_RELEVAR}_page"))
        filas = list(pagina.object_list)
        en_curso = inspecciones_en_curso_por_edificio([edificio.pk for edificio in filas])
        for edificio in filas:
            relevamiento = en_curso.get(edificio.pk)
            edificio.relevamiento_en_curso = relevamiento
            edificio.asignado_a = _nombre(relevamiento.asignado_a) if relevamiento else ""
            consulta = vista.copy()
            consulta["tab"] = SOLAPA_SIN_RELEVAR
            consulta["asignar"] = edificio.pk
            # Sin el botón cuando ya tiene uno en curso: es la regla de `crear_inspeccion`,
            # que acepta un solo relevamiento en curso por edificio.
            edificio.url_asignar = "" if relevamiento else f"?{consulta.urlencode()}"
        return {
            "clave": SOLAPA_SIN_RELEVAR,
            "etiqueta": "Sin relevar nunca",
            "icono": "fa-building",
            "total": paginator.count,
            "pagina": pagina,
            "filas": filas,
            "param": f"{SOLAPA_SIN_RELEVAR}_page",
            "filtros_qs": querystring_de(SOLAPA_SIN_RELEVAR),
        }

    @staticmethod
    def _preparar_fila(relevamiento, hoy, en_alcance, vista, solapa):
        """Lo que la fila muestra.

        Completado es terminal pero tiene una acción: **ver el informe**, que es lo único que
        queda por hacer con él. Cancelado no dejó resultado, así que sigue sin menú.
        """

        relevamiento.situacion = situacion_de(relevamiento, hoy)
        relevamiento.situacion_texto = Situacion.ETIQUETAS.get(relevamiento.situacion, relevamiento.situacion)
        realizado = relevamiento.estado == Estado.REALIZADA
        relevamiento.con_acciones = relevamiento.en_curso or realizado
        relevamiento.vence_relativo = (
            _vence_relativo(relevamiento.fecha_vencimiento, hoy) if relevamiento.en_curso else ""
        )
        relevamiento.menu_id = f"relevamiento-{relevamiento.pk}"
        relevamiento.menu_etiqueta = f"Más acciones del relevamiento de {relevamiento.edificio.nombre}"
        if realizado:
            consulta = vista.copy()
            consulta["tab"] = solapa
            relevamiento.url_informe = (
                reverse("dispositivos:relevamiento_informe", args=[relevamiento.pk])
                + f"?{urlencode({PARAMETRO_VOLVER: consulta.urlencode()})}"
            )
        if not relevamiento.en_curso:
            return
        relevamiento.gestionable = relevamiento.edificio_id in en_alcance
        motivo = "" if relevamiento.gestionable else "Fuera de tu alcance: lo gestiona la coordinación del edificio."
        relevamiento.motivo_reasignar = relevamiento.motivo_cancelar = motivo
        for accion in ("reasignar", "cancelar"):
            consulta = vista.copy()
            consulta["tab"] = solapa
            consulta[accion] = relevamiento.pk
            setattr(relevamiento, f"url_{accion}", f"?{consulta.urlencode()}")

    def _preparar_modales(self, context, user, params, edificios_libres):
        """Cada modal se abre solo si el registro pedido sigue siendo gestionable."""

        context["form_elegir"] = ElegirEdificioForm(edificios=edificios_libres)
        context["puede_crear"] = edificios_libres.exists()
        context["abrir_nuevo"] = params.get("nuevo") == "1" and context["puede_crear"]

        edificio = self._pedido(params, "asignar", edificios_libres)
        if edificio is not None:
            context["edificio_asignar"] = edificio
            context["form_asignar"] = AsignarRelevamientoForm(edificio=edificio, agentes=agentes_asignables(edificio))

        gestionables = InspeccionEdificio.objects.filter(
            estado=Estado.ASIGNADA,
            edificio__in=edificios_en_alcance(user, CAP_ASIGNAR),
        ).select_related("edificio", "asignado_a")
        relevamiento = self._pedido(params, "reasignar", gestionables)
        if relevamiento is not None:
            context["relevamiento_reasignar"] = relevamiento
            context["form_reasignar"] = ReasignarRelevamientoForm(agentes=agentes_asignables(relevamiento.edificio))
        relevamiento = self._pedido(params, "cancelar", gestionables)
        if relevamiento is not None:
            context["relevamiento_cancelar"] = relevamiento
            context["form_cancelar"] = CancelarRelevamientoForm()

    def _pedido(self, params, clave, queryset):
        if not params.get(clave):
            return None
        pk = _entero(params.get(clave))
        objeto = queryset.filter(pk=pk).first() if pk is not None else None
        if objeto is None:
            messages.warning(self.request, "Ese relevamiento ya no se puede gestionar desde acá.")
        return objeto


class RelevamientoInformeView(LoginRequiredMixin, TemplateView):
    """«Ver informe»: el relevamiento en solo lectura, con su resultado y su galería.

    **Sin mixin de capacidad a propósito.** La entran tres personas distintas —el
    coordinador desde P21, el agente que lo cargó y quien opera una institución del edificio
    desde la solapa Infraestructura— y cada una tiene una capacidad distinta. Poner una sola
    acá sería una segunda regla de alcance que se desincroniza de `inspecciones_visibles`:
    la única es esa, y lo que no está en ella da **404**, el mismo que un id inexistente (sin
    oráculo de existencia). Quien no tiene ninguna capacidad de Dispositivos cae ahí también,
    porque `inspecciones_visibles` le devuelve el conjunto vacío.

    El servicio decide **qué** se ve: el nombre del agente y las indicaciones no se le pasan
    al template cuando quien mira es la institución relevada.
    """

    template_name = "programas/dispositivos/relevamientos/informe.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        relevamiento = get_object_or_404(
            inspecciones_visibles(user).select_related("edificio", "asignado_a", "realizada_por"),
            pk=kwargs["pk"],
        )
        volver_url, volver_label = self._volver(user, self.request.GET)
        context.update(informe_de_relevamiento(user, relevamiento))
        context.update({"volver_url": volver_url, "volver_label": volver_label})
        return context

    @staticmethod
    def _volver(user, params):
        """A dónde vuelve el botón: de donde se entró, y nunca a una pantalla que daría 403.

        Las dos URL se arman con `reverse` y el querystring del listado se **rearma** con
        `_url_lista`: lo que llega por la URL no se copia crudo a un `Location`.
        """

        pk = _entero(params.get("dispositivo"))
        if pk is not None:
            dispositivo = Dispositivo.objects.filter(pk=pk).only("id", "nombre").first()
            if dispositivo is not None and puede_operar_dispositivo(user, dispositivo, CAP_VER):
                url = reverse("dispositivos:detalle", args=[dispositivo.pk])
                return f"{url}?tab=infraestructura", dispositivo.nombre
        if puede_en_programa_dispositivos(user, CAP_ASIGNAR):
            return _url_lista(params.get(PARAMETRO_VOLVER, "")), "Relevamientos"
        return reverse("dispositivos:lista"), "Dispositivos"


class _RelevamientoAccionView(DispositivoProgramaPermissionMixin, View):
    """Base de los POST de P21: el servicio decide; la vista traduce su respuesta."""

    capacidad_requerida = CAP_ASIGNAR
    http_method_names = ["post"]

    def _volver(self):
        return _url_lista(self.request.POST.get(PARAMETRO_VOLVER, ""))

    def _ok(self, mensaje):
        if is_ajax(self.request):
            return ajax_redirect(self.request, self._volver(), mensaje)
        messages.success(self.request, mensaje)
        return redirect(self._volver())

    def _errores_del_servicio(self, error, form):
        if not hasattr(error, "error_dict"):
            return {"__all__": list(error.messages)}
        errores = {}
        for campo, mensajes in error.message_dict.items():
            destino = campo if campo in form.fields else "__all__"
            errores.setdefault(destino, []).extend(mensajes)
        return errores

    def _rechazar(self, errores):
        if is_ajax(self.request):
            return JsonResponse({"ok": False, "errors": {k: list(v) for k, v in errores.items()}}, status=400)
        for mensajes in errores.values():
            for mensaje in mensajes:
                messages.error(self.request, mensaje)
        return redirect(self._volver())

    def _prohibido(self, error):
        if is_ajax(self.request):
            mensaje = str(error) or "No tenés permiso para realizar esta acción."
            return JsonResponse({"ok": False, "message": mensaje}, status=403)
        raise error

    def _relevamiento(self, pk):
        return get_object_or_404(
            inspecciones_visibles(self.request.user).select_related("edificio", "asignado_a"), pk=pk
        )


class RelevamientoAsignarView(_RelevamientoAccionView):
    """Crea el relevamiento de un edificio y se lo asigna a un agente."""

    def post(self, request, edificio_pk):
        # Fuera del alcance es 404, igual que un id inexistente: si el form se validara antes
        # contra un edificio ajeno, el 400/403 diría qué edificios existen y quién es su personal.
        # `edificios_en_alcance` y no `edificios_para_asignar`: «ya tiene uno en curso» sigue
        # siendo un error del campo, que lo decide el servicio.
        edificio = get_object_or_404(edificios_en_alcance(request.user, CAP_ASIGNAR), pk=edificio_pk)
        form = AsignarRelevamientoForm(request.POST, edificio=edificio, agentes=agentes_asignables(edificio))
        if not form.is_valid():
            return self._rechazar(form.errors)
        datos = form.cleaned_data
        try:
            crear_inspeccion(
                request.user,
                edificio=edificio,
                asignado_a=datos["asignado_a"],
                fecha_vencimiento=datos["fecha_vencimiento"],
                indicaciones=datos["indicaciones"],
            )
        except PermissionDenied as error:
            return self._prohibido(error)
        except ValidationError as error:
            return self._rechazar(self._errores_del_servicio(error, form))
        return self._ok(f"Relevamiento de {edificio.nombre} asignado a {_nombre(datos['asignado_a'])}.")


class RelevamientoReasignarView(_RelevamientoAccionView):
    def post(self, request, pk):
        relevamiento = self._relevamiento(pk)
        form = ReasignarRelevamientoForm(request.POST, agentes=agentes_asignables(relevamiento.edificio))
        if not form.is_valid():
            return self._rechazar(form.errors)
        agente = form.cleaned_data["asignado_a"]
        try:
            reasignar_inspeccion(request.user, relevamiento, agente)
        except PermissionDenied as error:
            return self._prohibido(error)
        except ValidationError as error:
            return self._rechazar(self._errores_del_servicio(error, form))
        return self._ok(f"Relevamiento de {relevamiento.edificio.nombre} reasignado a {_nombre(agente)}.")


class RelevamientoCancelarView(_RelevamientoAccionView):
    def post(self, request, pk):
        relevamiento = self._relevamiento(pk)
        form = CancelarRelevamientoForm(request.POST)
        if not form.is_valid():
            return self._rechazar(form.errors)
        try:
            cancelar_inspeccion(request.user, relevamiento, form.cleaned_data["motivo"])
        except PermissionDenied as error:
            return self._prohibido(error)
        except ValidationError as error:
            return self._rechazar(self._errores_del_servicio(error, form))
        return self._ok(f"Relevamiento de {relevamiento.edificio.nombre} cancelado.")
