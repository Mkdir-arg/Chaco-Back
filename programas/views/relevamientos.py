"""Backoffice — ABM de Relevamientos y Convocatorias de Becas (#76).

Acceso granular por entidad (ver/crear/editar de Convocatoria y Relevamiento).
El alcance por segmento se aplica en la query (un coordinador solo ve/gestiona
relevamientos de sus segmentos asignados); el Admin ve todos.
"""

import csv
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, F, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from core.rbac import CapacidadRequeridaMixin, puede, requiere
from programas.forms import (
    ConvocatoriaForm,
    CupoRelevamientoForm,
    ReasignarTerritorialForm,
    RelevamientoForm,
    ReprogramarForm,
    VolverACampoForm,
)
from programas.models import Convocatoria, Formulario, ListaEspera, Relevamiento, q_con_identidad
from programas.services.autorizacion import (
    assert_alcance_relevamiento,
    convocatorias_visibles,
    es_admin_becas,
    programa_becas,
    puede_gestionar_segmento,
    puede_relevamiento_publico,
    segmentos_visibles,
    sin_formularios_publicos_si_no_puede,
    sin_relevamientos_publicos_si_no_puede,
    subsegmentos_visibles,
    usuarios_territoriales_becas,
)
from programas.services.exportacion_reportes import celda_segura
from programas.services.listados import PaginadorConConteo, hidratar_pagina
from programas.views.ajax_utils import ajax_errors, ajax_ok, ajax_redirect, is_ajax

CAP_CONVOCATORIA_VER = "becas.convocatoria.ver"
CAP_CONVOCATORIA_CREAR = "becas.convocatoria.crear"
CAP_CONVOCATORIA_EDITAR = "becas.convocatoria.editar"
logger = logging.getLogger(__name__)

CAP_RELEVAMIENTO_VER = "becas.relevamiento.ver"
CAP_RELEVAMIENTO_CREAR = "becas.relevamiento.crear"
CAP_RELEVAMIENTO_EDITAR = "becas.relevamiento.editar"
# ``CAP_RELEVAMIENTO_PUBLICO`` (RN-P13) se mudó a ``programas.services.autorizacion``
# junto con los filtros y los guards de alcance (RED-79): la importaban dos vistas más.
# SEC-06: los tres exports pedían esta capacidad con ``@requiere``, que evalúa **sin
# alcance**, y bajaban la convocatoria por ``pk`` suelto. Un rol de **otro** programa con
# ``becas.programa.administrar`` tildada se llevaba el CSV con DNI de cualquier
# convocatoria. Desde este cambio la capacidad va por ``es_admin_becas`` —que la evalúa
# contra el Programa Becas— y el objeto sale de ``convocatorias_visibles``; el flag
# ``puede_reportes`` que decide qué muestra la pantalla usa **la misma regla**, para que
# la UI no ofrezca un botón que va a contestar 403.


def _puede_exportar(user):
    """El flag de UI de los CSV de convocatoria: **la misma regla que el gate**.

    Era ``puede(user, "becas.programa.administrar")`` sin alcance, o sea lo que SEC-06
    acaba de dejar de aceptar en ``_convocatoria_para_export``: la pantalla seguía
    ofreciendo los botones a quien el export contesta 403. Falla en ``False`` —y no en
    403— si el Programa Becas no está configurado: esto decide qué se dibuja, no quién
    entra.
    """
    try:
        return es_admin_becas(user)
    except PermissionDenied:
        return False


def _convocatoria_para_export(request, pk, queryset=None):
    """La convocatoria del export, o 403 (SEC-06).

    Dos candados, no uno: ``es_admin_becas`` exige la capacidad **en el Programa
    Becas** (un rol de Dispositivos con la paraguas tildada deja de pasar) y
    ``convocatorias_visibles`` acota el objeto al alcance fino del usuario, que para un
    Coordinador Regional son sus subsegmentos. El primero solo no alcanza: ``puede``
    sin alcance era justo el agujero.
    """
    if not es_admin_becas(request.user):
        raise PermissionDenied("No administra el programa Becas.")
    base = convocatorias_visibles(request.user) if queryset is None else queryset
    return get_object_or_404(base, pk=pk)


DETALLE_PAGE_SIZE = 50
#: FE-17: el listado de convocatorias no paginaba. 25 es el valor del resto del backoffice.
CONVOCATORIAS_PAGE_SIZE = 25


def _paginate(request, queryset, page_param="page", per_page=DETALLE_PAGE_SIZE):
    paginator = Paginator(queryset, per_page)
    return paginator.get_page(request.GET.get(page_param))


def _querystring_without(request, *keys):
    params = request.GET.copy()
    for key in keys:
        params.pop(key, None)
    return params.urlencode()


def _puede_publico(user):
    """RN-P13 con el alcance del Programa Becas. La regla vive en ``services.autorizacion``:
    acá solo se le pasa el programa, que el resto del alcance de esta pantalla ya resolvió."""
    return puede_relevamiento_publico(user, programa=programa_becas(user))


def _convocatorias_qs(request):
    # El badge de estado de cada fila mira ``pausa_efectiva``, que sube por
    # segmento → programa y por subsegmento → segmento → programa: sin estas
    # relaciones precargadas el listado hace tres consultas por convocatoria.
    return (
        Convocatoria.objects.select_related(
            "segmento__programa",
            "subsegmento__segmento__programa",
        )
        .defer("descripcion", "segmento__descripcion", "subsegmento__descripcion")
        .annotate(n_relevamientos=Count("relevamientos", distinct=True))
        .filter(pk__in=convocatorias_visibles(request.user))
        .order_by("-fecha_inicio", "nombre")
    )


def _pagina_de_convocatorias(request):
    """Qué página estaba mirando quien disparó el pedido.

    El modal «Nueva convocatoria» postea a ``convocatoria_crear`` **sin** querystring,
    así que en el re-render AJAX ``request.GET`` viene vacío y mirar solo ahí devolvía
    siempre la página 1 aunque la URL del navegador dijera 2. El formulario manda la
    página en un campo oculto; el GET sigue mandando cuando el contexto lo arma la vista.
    """
    return request.POST.get("page") or request.GET.get("page")


def _contexto_convocatorias(request):
    """Página del listado de convocatorias, igual para la vista y para el re-render AJAX.

    FE-17: la vista no paginaba y el modal devolvía la tabla entera. Con ``paginate_by``
    solo en la vista, guardar una convocatoria reemplazaba la página por las N filas
    visibles, que es el bug de la pantalla sin paginar con otro disfraz.
    """
    pagina = Paginator(_convocatorias_qs(request), CONVOCATORIAS_PAGE_SIZE).get_page(_pagina_de_convocatorias(request))
    return {
        "convocatorias": pagina.object_list,
        "page_obj": pagina,
        "paginator": pagina.paginator,
        "is_paginated": pagina.has_other_pages(),
    }


def _convocatorias_ajax(request, message="Convocatoria guardada."):
    return ajax_ok(
        request,
        target="#convocatorias-table",
        partial="programas/becas/relevamientos/_convocatorias_table.html",
        context=_contexto_convocatorias(request),
        message=message,
    )


def _relevamientos_ajax(request, convocatoria, message="Relevamiento creado y asignado."):
    """Re-renderiza la tabla de relevamientos de una convocatoria (pestaña
    "Relevamientos" de su detalle) tras crear uno desde el modal embebido."""
    relevamientos = list(
        sin_relevamientos_publicos_si_no_puede(
            convocatoria.relevamientos.select_related("territorial"),
            request.user,
            programa=programa_becas(request.user),
        ).order_by("-fecha_asignada")
    )
    return ajax_ok(
        request,
        target="#relevamientos-table",
        partial="programas/becas/relevamientos/_relevamientos_tab_table.html",
        context={"relevamientos": relevamientos},
        message=message,
    )


def _destino_seguro(request, defecto="becas:convocatorias"):
    """BEC-19: el ``next`` del formulario solo puede volver a este sitio.

    Los dos POST de la tabla de convocatorias redirigían a ``POST["next"]`` tal cual,
    así que un link preparado con ``next=https://evil.example`` sacaba al operador del
    backoffice —con su sesión recién usada para una acción legítima— hacia afuera.
    Mismo criterio que ``RelevamientoCreateView``.
    """
    destino = request.POST.get("next") or ""
    if destino and url_has_allowed_host_and_scheme(
        destino, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return destino
    return defecto


def _rechazar_si_pausado(request, relevamiento):
    pausa = relevamiento.pausa_efectiva
    if not pausa:
        return False
    messages.error(request, f"La operación no está disponible porque el elemento está pausado: {pausa.pausa_motivo}")
    return True


def _mensaje_solapamiento(territorial, fecha_desde, fecha_hasta, solapamiento):
    nombre = territorial.get_full_name() or territorial.username
    fecha_legible = f"{fecha_desde:%d/%m/%Y %H:%M} al {fecha_hasta:%d/%m/%Y %H:%M}"
    return (
        f"El territorial {nombre} ya tiene una asignación que se superpone con {fecha_legible} "
        f"en {solapamiento.zona}. ¿Confirmás la asignación?"
    )


# ---------------------------------------------------------------------------
# Convocatorias (prerequisito para crear relevamientos)
# ---------------------------------------------------------------------------
class ConvocatoriaListView(CapacidadRequeridaMixin, LoginRequiredMixin, ListView):
    capacidades_requeridas = CAP_CONVOCATORIA_VER
    template_name = "programas/becas/relevamientos/convocatoria_list.html"
    context_object_name = "convocatorias"
    paginate_by = CONVOCATORIAS_PAGE_SIZE

    def get_queryset(self):
        return _convocatorias_qs(self.request)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        form = ConvocatoriaForm(
            subsegmentos_permitidos=subsegmentos_visibles(self.request.user),
            operador=self.request.user,
        )
        form.fields["segmento"].queryset = segmentos_visibles(self.request.user)
        ctx["form_convocatoria"] = form
        return ctx


class ConvocatoriaDetailView(CapacidadRequeridaMixin, LoginRequiredMixin, DetailView):
    model = Convocatoria
    capacidades_requeridas = CAP_CONVOCATORIA_VER
    template_name = "programas/becas/relevamientos/convocatoria_detail.html"
    context_object_name = "convocatoria"

    def get_queryset(self):
        return convocatorias_visibles(self.request.user).select_related("segmento__programa", "subsegmento")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        conv = self.object
        relevamientos_qs = sin_relevamientos_publicos_si_no_puede(
            conv.relevamientos.select_related("territorial"),
            self.request.user,
            programa=programa_becas(self.request.user),
        ).order_by("-fecha_asignada")
        relevamientos = list(relevamientos_qs)
        # Los relevamientos visibles de la convocatoria ya están en memoria: filtrar los
        # casos por sus ids da el mismo conjunto que el join más la exclusión por tipo,
        # y le deja a MySQL un rango indexado en vez de ordenar todo el join.
        formularios_base = Formulario.objects.filter(relevamiento_id__in=[r.pk for r in relevamientos])
        ctx["relevamientos"] = relevamientos
        ctx["n_relevamientos"] = len(relevamientos)
        conteos = formularios_base.aggregate(
            total=Count("pk"),
            aprobados=Count("pk", filter=Q(estado=Formulario.Estado.APROBADO)),
        )
        # La página se elige proyectando solo el pk y se hidrata después. Con los
        # ``select_related`` en la consulta paginada, en cuanto la convocatoria tiene más
        # de un relevamiento MySQL arranca por ``programas_relevamiento``, materializa
        # TODOS sus casos (con los JSON) en una tabla temporal y recién ahí ordena y
        # recorta: 720 ms medidos con 20.000 casos en dos relevamientos, contra 26 ms
        # por pk (recorre el índice de ``creado`` hacia atrás y corta en la página). El
        # total ya lo trae el aggregate: el paginador no lo vuelve a contar.
        pagina = PaginadorConConteo(
            formularios_base.order_by("-creado", "-pk").values_list("pk", flat=True),
            DETALLE_PAGE_SIZE,
            total=conteos["total"] or 0,
        ).get_page(self.request.GET.get("beneficiarios_page"))
        ctx["beneficiarios"] = hidratar_pagina(
            pagina,
            # La tabla de beneficiarios no abre las respuestas ni la foto del formulario
            # (``definicion``, ~7 KB por caso): se difieren los cuatro JSON.
            Formulario.objects.select_related("ciudadano", "relevamiento").defer(
                "data", "respuestas", "definicion", "datos_siis"
            ),
        )
        ctx["n_beneficiarios"] = conteos["total"] or 0
        ctx["n_aprobados"] = conteos["aprobados"] or 0
        ctx["beneficiarios_querystring"] = _querystring_without(self.request, "beneficiarios_page", "tab")
        ctx["puede_reportes"] = _puede_exportar(self.request.user)
        # Cambio 58: «Configurar formulario» (admin del programa y coordinador del segmento, D7).
        ctx["puede_formulario"] = puede(self.request.user, CAP_CONVOCATORIA_EDITAR) and puede_gestionar_segmento(
            self.request.user, conv.segmento
        )
        ctx["cupo_segmento"] = conv.segmento.cupo_maximo
        segmentos = segmentos_visibles(self.request.user)
        form = ConvocatoriaForm(
            instance=conv,
            subsegmentos_permitidos=subsegmentos_visibles(self.request.user),
            operador=self.request.user,
        )
        form.fields["segmento"].queryset = segmentos
        ctx["form_convocatoria"] = form
        # Modal "Nuevo relevamiento" con esta convocatoria preseleccionada.
        ctx["puede_publico"] = _puede_publico(self.request.user)
        ctx["form_crear"] = RelevamientoForm(
            initial={"convocatoria": conv},
            segmentos_permitidos=segmentos,
            convocatorias_permitidas=convocatorias_visibles(self.request.user),
            territoriales_permitidos=usuarios_territoriales_becas().filter(
                asignacion_territorial__segmento__in=segmentos
            ),
            operador=self.request.user,
            puede_publico=ctx["puede_publico"],
        )
        # Fija: un disabled no viaja en el POST; el valor lo aporta el hidden del template.
        ctx["form_crear"].fields["convocatoria"].widget.attrs["disabled"] = True
        # Padrón de habilitados (Cambio 57; herencia por relevamiento, Cambio 74):
        # acá se administra el de la convocatoria, que heredan los relevamientos
        # sin padrón propio. Un solo aggregate trae los dos niveles.
        nivel_convocatoria = Q(relevamiento__isnull=True)
        conteo_padron = conv.padron.aggregate(
            total=Count("pk", filter=nivel_convocatoria),
            # RED-77: la misma regla que el cruce automático y el botón manual.
            # Escrita a mano, este contador decía «N con identidad» incluyendo
            # filas con nombre o apellido de solo espacios, que no validan nada.
            con_identidad=Count("pk", filter=nivel_convocatoria & q_con_identidad()),
            rels_propios=Count("relevamiento", distinct=True),
        )
        ctx["n_padron"] = conteo_padron["total"] or 0
        ctx["n_padron_identidad"] = conteo_padron["con_identidad"] or 0
        ctx["n_rels_padron_propio"] = conteo_padron["rels_propios"] or 0
        ctx["puede_padron"] = puede(self.request.user, CAP_CONVOCATORIA_EDITAR)
        ctx["padron_resumen"] = _resumen_fijo_padron(self.request, f"conv-{conv.pk}")
        ctx["tiene_publicos"] = any(r.es_publico for r in relevamientos)
        return ctx


class ConvocatoriaCreateView(CapacidadRequeridaMixin, LoginRequiredMixin, CreateView):
    capacidades_requeridas = CAP_CONVOCATORIA_CREAR
    form_class = ConvocatoriaForm
    template_name = "programas/becas/relevamientos/convocatoria_form.html"
    success_url = reverse_lazy("becas:convocatorias")

    def get_form(self, form_class=None):
        form = ConvocatoriaForm(
            data=self.request.POST or None,
            files=self.request.FILES or None,
            subsegmentos_permitidos=subsegmentos_visibles(self.request.user),
            operador=self.request.user,
        )
        form.fields["segmento"].queryset = segmentos_visibles(self.request.user)
        return form

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.save()
        if is_ajax(self.request):
            return _convocatorias_ajax(self.request, "Convocatoria creada.")
        messages.success(self.request, "Convocatoria creada.")
        return redirect(self.success_url)

    def form_invalid(self, form):
        if is_ajax(self.request):
            return ajax_errors(form)
        return super().form_invalid(form)


class ConvocatoriaUpdateView(CapacidadRequeridaMixin, LoginRequiredMixin, UpdateView):
    capacidades_requeridas = CAP_CONVOCATORIA_EDITAR
    form_class = ConvocatoriaForm
    template_name = "programas/becas/relevamientos/convocatoria_form.html"
    context_object_name = "convocatoria"

    def get_queryset(self):
        return convocatorias_visibles(self.request.user)

    def get_form(self, form_class=None):
        form = ConvocatoriaForm(
            data=self.request.POST or None,
            files=self.request.FILES or None,
            instance=self.object,
            subsegmentos_permitidos=subsegmentos_visibles(self.request.user),
            operador=self.request.user,
        )
        form.fields["segmento"].queryset = segmentos_visibles(self.request.user)
        return form

    def get_success_url(self):
        return reverse("becas:convocatoria_detalle", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        messages.success(self.request, "Convocatoria actualizada.")
        return super().form_valid(form)


@login_required
@requiere(CAP_CONVOCATORIA_EDITAR)
def convocatoria_toggle_activo(request, pk):
    conv = get_object_or_404(convocatorias_visibles(request.user), pk=pk)
    destino = _destino_seguro(request)
    if request.method == "POST":
        # Reactivar una vencida exige extender la fecha (fecha manda): eso va por
        # convocatoria_reactivar, no por el toggle simple.
        if not conv.activo and conv.esta_vencida:
            messages.error(
                request,
                "La convocatoria está vencida: para reactivarla tenés que extender la fecha de fin.",
            )
            return redirect(destino)
        # El toggle es siempre una acción manual: limpia la marca de cierre automático.
        conv.activo = not conv.activo
        conv.cerrada_automaticamente = False
        conv.cerrada_el = None
        conv.save(update_fields=["activo", "cerrada_automaticamente", "cerrada_el", "modificado"])
        messages.success(request, f"Convocatoria {'activada' if conv.activo else 'desactivada'}.")
    return redirect(destino)


@login_required
@requiere(CAP_CONVOCATORIA_EDITAR)
@require_POST
def convocatoria_reactivar(request, pk):
    """Reactiva una convocatoria vencida extendiendo su fecha de fin (fecha manda).
    Se dispara desde el pop-up con selector de fecha de la tabla."""
    conv = get_object_or_404(convocatorias_visibles(request.user), pk=pk)
    destino = _destino_seguro(request)

    nueva_fecha = parse_date(request.POST.get("fecha_fin") or "")
    if nueva_fecha is None:
        messages.error(request, "Indicá una nueva fecha de fin válida.")
    elif nueva_fecha < timezone.localdate():
        messages.error(request, "La nueva fecha de fin debe ser hoy o una fecha posterior.")
    elif nueva_fecha < conv.fecha_inicio:
        messages.error(request, "La fecha de fin no puede ser anterior a la fecha de inicio.")
    else:
        conv.fecha_fin = nueva_fecha
        conv.activo = True
        conv.cerrada_automaticamente = False
        conv.cerrada_el = None
        conv.save(update_fields=["fecha_fin", "activo", "cerrada_automaticamente", "cerrada_el", "modificado"])
        messages.success(request, f"Convocatoria reactivada hasta el {nueva_fecha.strftime('%d/%m/%Y')}.")
    return redirect(destino)


@login_required
def convocatoria_export_beneficiarios(request, pk):
    conv = _convocatoria_para_export(request, pk, convocatorias_visibles(request.user).select_related("segmento"))
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="beneficiarios_convocatoria_{conv.pk}.csv"'
    response.write("﻿")  # BOM para Excel
    writer = csv.writer(response)
    writer.writerow(["Nombre", "DNI", "Segmento", "Convocatoria", "Fecha de aprobación"])
    # Por ``values_list`` y no por instancias: el CSV usa cinco columnas y traer el
    # modelo entero arrastra el JSON de respuestas de cada caso y lo deserializa
    # (medido: 907 ms de bucle contra 106 ms, sobre 4.827 aprobados).
    filas = (
        sin_formularios_publicos_si_no_puede(
            Formulario.objects.filter(relevamiento__convocatoria=conv, estado=Formulario.Estado.APROBADO),
            request.user,
            programa=programa_becas(request.user),
        )
        .order_by("-creado")
        .values_list(
            "ciudadano_id",
            "ciudadano__dni",
            "ciudadano__nombre",
            "ciudadano__apellido",
            "datos_identificacion",
            "modificado",
        )
    )
    for ciudadano_id, dni_ciudadano, nombre, apellido, identificacion, modificado in filas.iterator(chunk_size=2000):
        if ciudadano_id:
            dni = dni_ciudadano
            nombre_completo = f"{nombre} {apellido}"
        else:
            ident = identificacion or {}
            dni = ident.get("dni", "")
            nombre_completo = f"{ident.get('nombre', '')} {ident.get('apellido', '')}".strip()
        # SEC-20: un apellido `=HYPERLINK(...)` cargado por el link público se evalúa
        # al abrir el CSV en Excel. ``celda_segura`` lo prefija con una comilla.
        writer.writerow(
            [
                celda_segura(valor)
                for valor in (
                    nombre_completo,
                    dni,
                    conv.segmento.nombre,
                    conv.nombre,
                    modificado.strftime("%d/%m/%Y"),
                )
            ]
        )
    return response


@login_required
def convocatoria_export_relevamientos(request, pk):
    conv = _convocatoria_para_export(request, pk)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="relevamientos_convocatoria_{conv.pk}.csv"'
    response.write("﻿")
    writer = csv.writer(response)
    writer.writerow(
        [
            "Relevamiento",
            "Territorial",
            "Fecha desde",
            "Fecha hasta",
            "Zona",
            "Estado",
            "Enviados",
            "Aprobados",
            "Rechazados",
        ]
    )
    relevamientos = (
        sin_relevamientos_publicos_si_no_puede(
            conv.relevamientos.select_related("territorial"), request.user, programa=programa_becas(request.user)
        )
        .annotate(
            n_enviados=Count("formularios", filter=Q(formularios__estado=Formulario.Estado.ENVIADO)),
            n_aprobados=Count("formularios", filter=Q(formularios__estado=Formulario.Estado.APROBADO)),
            n_rechazados=Count("formularios", filter=Q(formularios__estado=Formulario.Estado.RECHAZADO)),
        )
        .order_by("-fecha_asignada")
    )
    for r in relevamientos:
        terr = (r.territorial.get_full_name() or r.territorial.username) if r.territorial else "Formulario público"
        writer.writerow(
            [
                celda_segura(valor)
                for valor in (
                    r.nombre,
                    terr,
                    timezone.localtime(r.fecha_asignada).strftime("%d/%m/%Y %H:%M"),
                    timezone.localtime(r.fecha_hasta).strftime("%d/%m/%Y %H:%M"),
                    r.zona,
                    r.get_estado_display(),
                    r.n_enviados,
                    r.n_aprobados,
                    r.n_rechazados,
                )
            ]
        )
    return response


@login_required
def convocatoria_export_lista_espera(request, pk):
    conv = _convocatoria_para_export(request, pk, convocatorias_visibles(request.user).select_related("segmento"))
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="lista_espera_convocatoria_{conv.pk}.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(["Posición", "Nombre", "DNI", "Segmento", "Fecha de ingreso"])
    entradas = (
        sin_formularios_publicos_si_no_puede(
            ListaEspera.objects.filter(formulario__relevamiento__convocatoria=conv, promovido=False),
            request.user,
            programa=programa_becas(request.user),
            prefijo="formulario__",
        )
        .select_related("formulario__ciudadano", "segmento")
        # El CSV no abre las respuestas del formulario; traerlas es ancho de fila
        # y un json.loads por entrada.
        .defer("formulario__data")
        .order_by("posicion")
    )
    for entrada in entradas:
        formulario = entrada.formulario
        if formulario.ciudadano_id:
            nombre = formulario.ciudadano.nombre_completo
            dni = formulario.ciudadano.dni
        else:
            datos = formulario.datos_identificacion or {}
            nombre = f"{datos.get('nombre', '')} {datos.get('apellido', '')}".strip()
            dni = datos.get("dni", "")
        writer.writerow(
            [
                celda_segura(valor)
                for valor in (
                    entrada.posicion,
                    nombre,
                    dni,
                    entrada.segmento.nombre,
                    entrada.fecha_ingreso.strftime("%d/%m/%Y"),
                )
            ]
        )
    return response


# ---------------------------------------------------------------------------
# Relevamientos
# ---------------------------------------------------------------------------
class RelevamientoListView(CapacidadRequeridaMixin, LoginRequiredMixin, ListView):
    capacidades_requeridas = CAP_RELEVAMIENTO_VER
    template_name = "programas/becas/relevamientos/relevamiento_list.html"
    context_object_name = "relevamientos"
    paginate_by = 25

    def get_queryset(self):
        qs = (
            Relevamiento.objects.select_related("convocatoria__segmento", "territorial")
            .defer("observaciones", "convocatoria__descripcion", "convocatoria__segmento__descripcion")
            .filter(convocatoria__in=convocatorias_visibles(self.request.user))
            .order_by("-fecha_asignada", "nombre")
        )
        qs = sin_relevamientos_publicos_si_no_puede(qs, self.request.user, programa=programa_becas(self.request.user))

        q = self.request.GET.get("q", "").strip()
        estado = self.request.GET.get("estado", "").strip()
        segmento = self.request.GET.get("segmento", "").strip()
        territorial = self.request.GET.get("territorial", "").strip()
        fecha_desde = parse_date(self.request.GET.get("fecha_desde", ""))
        fecha_hasta = parse_date(self.request.GET.get("fecha_hasta", ""))

        if q:
            qs = qs.filter(
                Q(nombre__icontains=q)
                | Q(zona__icontains=q)
                | Q(territorial__username__icontains=q)
                | Q(territorial__first_name__icontains=q)
                | Q(territorial__last_name__icontains=q)
            )
        if estado:
            qs = qs.filter(estado=estado)
        if segmento:
            qs = qs.filter(convocatoria__segmento_id=segmento)
        if territorial:
            qs = qs.filter(territorial_id=territorial)
        if fecha_desde:
            qs = qs.filter(fecha_hasta__gte=fecha_desde)
        if fecha_hasta:
            qs = qs.filter(fecha_asignada__lte=fecha_hasta)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        segmentos = segmentos_visibles(self.request.user).order_by("nombre")
        territoriales = usuarios_territoriales_becas().filter(asignacion_territorial__segmento__in=segmentos)
        ctx["estados"] = Relevamiento.Estado.choices
        ctx["segmentos"] = segmentos
        ctx["filtros"] = {
            "q": self.request.GET.get("q", ""),
            "estado": self.request.GET.get("estado", ""),
            "segmento": self.request.GET.get("segmento", ""),
            "territorial": self.request.GET.get("territorial", ""),
            "fecha_desde": self.request.GET.get("fecha_desde", ""),
            "fecha_hasta": self.request.GET.get("fecha_hasta", ""),
        }
        # Form + nombre autogenerado para el modal "Nuevo relevamiento".
        ctx["puede_publico"] = _puede_publico(self.request.user)
        form_crear = RelevamientoForm(
            segmentos_permitidos=segmentos,
            convocatorias_permitidas=convocatorias_visibles(self.request.user),
            territoriales_permitidos=territoriales,
            operador=self.request.user,
            puede_publico=ctx["puede_publico"],
        )
        # El filtro y el modal usan los mismos territoriales. Congelar las
        # opciones evita consultar dos veces el mismo queryset al renderizar.
        # La comprensión evita el ``COUNT`` que ``list(ModelChoiceIterator)``
        # solicita como length hint antes de traer las opciones.
        opciones_territoriales = [opcion for opcion in form_crear.fields["territorial"].choices]
        ctx["territoriales"] = [
            valor.instance for valor, _etiqueta in opciones_territoriales if getattr(valor, "instance", None)
        ]
        form_crear.fields["territorial"].choices = opciones_territoriales
        ctx["form_crear"] = form_crear
        return ctx


class RelevamientoCreateView(CapacidadRequeridaMixin, LoginRequiredMixin, CreateView):
    capacidades_requeridas = CAP_RELEVAMIENTO_CREAR
    form_class = RelevamientoForm
    template_name = "programas/becas/relevamientos/relevamiento_form.html"
    success_url = reverse_lazy("becas:relevamientos")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["segmentos_permitidos"] = segmentos_visibles(self.request.user)
        kwargs["convocatorias_permitidas"] = convocatorias_visibles(self.request.user)
        kwargs["territoriales_permitidos"] = usuarios_territoriales_becas().filter(
            asignacion_territorial__segmento__in=segmentos_visibles(self.request.user)
        )
        kwargs["operador"] = self.request.user
        kwargs["puede_publico"] = _puede_publico(self.request.user)
        return kwargs

    def form_valid(self, form):
        territorial = form.cleaned_data.get("territorial")
        fecha_desde = form.cleaned_data["fecha_asignada"]
        fecha_hasta = form.cleaned_data["fecha_hasta"]
        # El control de solapamiento es por territorial; a un público no aplica.
        solapamiento = (
            Relevamiento.asignaciones_solapadas(
                territorial=territorial, fecha_desde=fecha_desde, fecha_hasta=fecha_hasta
            )
            .only("zona")
            .first()
            if territorial
            else None
        )
        if solapamiento and self.request.POST.get("confirmar_solapamiento") != "1":
            mensaje = _mensaje_solapamiento(territorial, fecha_desde, fecha_hasta, solapamiento)
            if is_ajax(self.request):
                return JsonResponse(
                    {"ok": False, "confirm_required": True, "message": mensaje},
                    status=409,
                )
            return self.render_to_response(
                self.get_context_data(
                    form=form,
                    advertencia_solapamiento=mensaje,
                )
            )

        self.object = form.save()
        if self.object.es_publico:
            # El link se muestra en el detalle: se navega ahí directamente.
            detalle = reverse("becas:relevamiento_detalle", kwargs={"pk": self.object.pk})
            mensaje = "Relevamiento público creado. Compartí el link de inscripción."
            nivel = messages.SUCCESS
            if not self.object.convocatoria.padron.exists():
                # Sin padrón cualquiera puede inscribirse: es una advertencia.
                mensaje += " La convocatoria no tiene padrón: el link queda abierto."
                nivel = messages.WARNING
            if is_ajax(self.request):
                return ajax_redirect(self.request, detalle, mensaje, level=nivel)
            messages.add_message(self.request, nivel, mensaje)
            return redirect(detalle)
        if is_ajax(self.request):
            return _relevamientos_ajax(self.request, self.object.convocatoria)
        messages.success(self.request, "Relevamiento creado y asignado.")
        return redirect(self.get_success_url())

    def form_invalid(self, form):
        if is_ajax(self.request):
            return ajax_errors(form)
        return super().form_invalid(form)

    def get_success_url(self):
        # "next" permite volver a la pantalla de origen (p. ej. el detalle de la
        # convocatoria cuando se crea desde su modal).
        next_url = self.request.POST.get("next")
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={self.request.get_host()}):
            return next_url
        return str(self.success_url)


class RelevamientoDetailView(CapacidadRequeridaMixin, LoginRequiredMixin, DetailView):
    model = Relevamiento
    # El template y el guard de alcance recorren convocatoria/segmento/territorial.
    # El padrón es de la convocatoria (Cambio 57): su tamaño viaja anotado en
    # la misma consulta para no sumar una lectura al presupuesto de la ruta.
    # Los dos niveles del padrón en la misma consulta (Cambio 74): el propio
    # del relevamiento y el de la convocatoria que heredaría si no tiene.
    queryset = Relevamiento.objects.select_related(
        "convocatoria__segmento__programa", "convocatoria__subsegmento", "territorial"
    ).annotate(
        n_padron_propio=Count("convocatoria__padron", filter=Q(convocatoria__padron__relevamiento_id=F("pk"))),
        n_padron_convocatoria=Count("convocatoria__padron", filter=Q(convocatoria__padron__relevamiento__isnull=True)),
    )
    capacidades_requeridas = CAP_RELEVAMIENTO_VER
    template_name = "programas/becas/relevamientos/relevamiento_detail.html"
    context_object_name = "relevamiento"

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        # El guard ya cubre RN-P13; el segundo chequeo queda por su mensaje propio.
        assert_alcance_relevamiento(self.request.user, obj)
        if obj.es_publico and not _puede_publico(self.request.user):
            raise PermissionDenied("No tiene acceso a los relevamientos de formulario público.")
        return obj

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        rel = self.object
        ctx["link_publico"] = self.request.build_absolute_uri(rel.url_publica) if rel.es_publico else ""
        # Anotados en el queryset (Cambios 57 y 59): propio pisa a heredado.
        ctx["n_padron_propio"] = rel.n_padron_propio
        ctx["n_padron_convocatoria"] = rel.n_padron_convocatoria
        ctx["n_padron"] = rel.n_padron_propio or rel.n_padron_convocatoria
        ctx["padron_origen"] = (
            "propio" if rel.n_padron_propio else ("convocatoria" if rel.n_padron_convocatoria else "")
        )
        ctx["puede_padron"] = puede(self.request.user, CAP_CONVOCATORIA_EDITAR)
        ctx["padron_resumen"] = _resumen_fijo_padron(self.request, f"rel-{rel.pk}")
        ctx["form_reasignar"] = ReasignarTerritorialForm(
            initial={"territorial": rel.territorial}, segmento=rel.convocatoria.segmento
        )
        ctx["form_reprogramar"] = ReprogramarForm(
            initial={"fecha_asignada": rel.fecha_asignada, "fecha_hasta": rel.fecha_hasta},
            convocatoria=rel.convocatoria,
        )
        ctx["form_cupo"] = CupoRelevamientoForm(instance=rel)
        ctx["form_volver_a_campo"] = VolverACampoForm(convocatoria=rel.convocatoria)
        # La tabla de personas relevadas no muestra las respuestas: ``datos_identificacion``
        # sí se usa (casos sin legajo); ``data``, ``respuestas``, ``datos_siis`` y la foto
        # del formulario (``definicion``, ~7 KB por caso) no.
        formularios_qs = (
            rel.formularios.select_related("ciudadano")
            .defer("data", "respuestas", "definicion", "datos_siis")
            .order_by("numero")
        )
        formularios_page = _paginate(self.request, formularios_qs, page_param="formularios_page")
        ctx["formularios"] = formularios_page
        ctx["n_formularios"] = formularios_page.paginator.count
        ctx["formularios_querystring"] = _querystring_without(self.request, "formularios_page", "tab")
        ctx["puede_revisar"] = puede(self.request.user, "becas.revision.ver")
        ctx["estados_revisables"] = [
            Relevamiento.Estado.FINALIZADO,
            Relevamiento.Estado.EN_REVISION,
            Relevamiento.Estado.TERMINADO,
        ]
        return ctx


@login_required
@requiere(CAP_RELEVAMIENTO_EDITAR)
@require_POST
def relevamiento_finalizar(request, pk):
    rel = get_object_or_404(Relevamiento.objects.select_related("convocatoria__segmento"), pk=pk)
    assert_alcance_relevamiento(request.user, rel)
    if _rechazar_si_pausado(request, rel):
        return redirect("becas:relevamiento_detalle", pk=rel.pk)
    if rel.estado != Relevamiento.Estado.EN_CURSO:
        messages.error(request, "Solo se puede finalizar un relevamiento en curso.")
        return redirect("becas:relevamiento_detalle", pk=rel.pk)

    rel.estado = Relevamiento.Estado.FINALIZADO
    rel.fecha_finalizado = timezone.now()
    rel.save(update_fields=["estado", "fecha_finalizado", "modificado"])
    messages.success(request, "Relevamiento finalizado.")
    return redirect("becas:relevamiento_detalle", pk=rel.pk)


@login_required
@requiere(CAP_RELEVAMIENTO_EDITAR)
@require_POST
def relevamiento_reabrir(request, pk):
    """Vuelve el relevamiento a EN_CURSO: «volver a campo».

    Admite los dos estados cerrados: FINALIZADO —el campo se cerró a mano y el
    período sigue vigente— y EN_REVISION, al que solo se llega por fecha (la
    regla ``becas.relevamiento`` de ``procesar_vencimientos``).

    Las dos condiciones de abajo no son preferencia sino mecánica: si la
    convocatoria venció o está cerrada, o si el período del relevamiento ya
    pasó y no se manda una fecha nueva, el cron devolvería el relevamiento a
    EN_REVISION a las 03:10 y la reapertura sería mentira por unas horas.
    """
    rel = get_object_or_404(Relevamiento.objects.select_related("convocatoria__segmento"), pk=pk)
    assert_alcance_relevamiento(request.user, rel)
    if _rechazar_si_pausado(request, rel):
        return redirect("becas:relevamiento_detalle", pk=rel.pk)
    if rel.estado not in (Relevamiento.Estado.FINALIZADO, Relevamiento.Estado.EN_REVISION):
        messages.error(request, "Solo se puede volver a campo un relevamiento finalizado o en revisión.")
        return redirect("becas:relevamiento_detalle", pk=rel.pk)

    convocatoria = rel.convocatoria
    if not convocatoria.activo or convocatoria.esta_vencida:
        messages.error(
            request,
            "La convocatoria está cerrada o vencida: extendé su fecha de fin antes de volver el relevamiento a campo.",
        )
        return redirect("becas:relevamiento_detalle", pk=rel.pk)

    form = VolverACampoForm(request.POST, convocatoria=convocatoria)
    if not form.is_valid():
        messages.error(request, next(iter(form.errors.values()))[0])
        return redirect("becas:relevamiento_detalle", pk=rel.pk)

    fecha_hasta = form.cleaned_data.get("fecha_hasta") or rel.fecha_hasta
    if fecha_hasta is None or fecha_hasta <= timezone.now():
        messages.error(
            request,
            "El período del relevamiento ya venció: indicá una fecha hasta futura para volver a campo.",
        )
        return redirect("becas:relevamiento_detalle", pk=rel.pk)

    estado_anterior = rel.estado
    rel.estado = Relevamiento.Estado.EN_CURSO
    rel.fecha_finalizado = None
    rel.fecha_hasta = fecha_hasta
    rel.save(update_fields=["estado", "fecha_finalizado", "fecha_hasta", "modificado"])
    # El relevamiento no tiene traza propia (a diferencia de los casos y los
    # dispositivos): hasta que exista, la reapertura queda en el log.
    logger.info(
        "relevamiento_volver_a_campo pk=%s de=%s por=%s fecha_hasta=%s",
        rel.pk,
        estado_anterior,
        request.user.pk,
        rel.fecha_hasta.isoformat() if rel.fecha_hasta else None,
    )
    messages.success(
        request,
        f"Relevamiento en curso otra vez, con fecha hasta {timezone.localtime(rel.fecha_hasta):%d/%m/%Y %H:%M}.",
    )
    return redirect("becas:relevamiento_detalle", pk=rel.pk)


@login_required
@requiere(CAP_RELEVAMIENTO_EDITAR)
def relevamiento_reasignar(request, pk):
    rel = get_object_or_404(Relevamiento.objects.select_related("convocatoria__segmento"), pk=pk)
    assert_alcance_relevamiento(request.user, rel)
    if rel.es_publico:
        messages.error(request, "Un relevamiento de formulario público no lleva territorial.")
        return redirect("becas:relevamiento_detalle", pk=rel.pk)
    if _rechazar_si_pausado(request, rel):
        return redirect("becas:relevamiento_detalle", pk=rel.pk)
    if request.method == "POST":
        form = ReasignarTerritorialForm(request.POST, segmento=rel.convocatoria.segmento)
        if form.is_valid():
            rel.territorial = form.cleaned_data["territorial"]
            rel.save(update_fields=["territorial", "modificado"])
            messages.success(request, "Territorial reasignado.")
        else:
            messages.error(request, "No se pudo reasignar: revisá el territorial seleccionado.")
    return redirect("becas:relevamiento_detalle", pk=rel.pk)


PADRON_LOCALIDADES_MAX = 10


def _clave_resumen_padron(clave):
    return f"padron_ultima_carga:{clave}"


def _informar_carga_padron(request, clave, resumen, prefijo=""):
    """Un solo aviso por carga, con el nivel del peor resultado, y el resumen
    fijo en sesión (reemplaza al de la carga anterior del mismo objeto)."""
    hay_problemas = bool(resumen.rechazadas or resumen.fechas_invalidas or resumen.localidades_no_reconocidas)
    nivel = messages.WARNING if hay_problemas else messages.SUCCESS
    messages.add_message(request, nivel, prefijo + resumen.mensaje())
    request.session[_clave_resumen_padron(clave)] = {
        "validas": resumen.validas,
        "con_identidad": resumen.con_identidad,
        "rechazadas": resumen.rechazadas,
        "fechas_invalidas": resumen.fechas_invalidas,
        "casos_validados": resumen.casos_validados,
        "localidades_total": len(resumen.localidades_no_reconocidas),
        "localidades": list(resumen.localidades_no_reconocidas[:PADRON_LOCALIDADES_MAX]),
    }


def _resumen_fijo_padron(request, clave):
    """Datos de la alerta persistente (`components/_alerta.html`) de la última carga, o None."""
    sesion = getattr(request, "session", None)
    datos = sesion.get(_clave_resumen_padron(clave)) if sesion is not None else None
    if not datos:
        return None
    partes = [f"{datos['validas']} habilitados", f"{datos['con_identidad']} con identidad completa"]
    if datos["rechazadas"]:
        partes.append(f"{datos['rechazadas']} filas ignoradas")
    if datos["fechas_invalidas"]:
        partes.append(f"{datos['fechas_invalidas']} fechas sin interpretar")
    if datos["casos_validados"]:
        partes.append(f"{datos['casos_validados']} casos pendientes validados")
    texto = " · ".join(partes) + "."
    if datos["localidades_total"]:
        muestra = ", ".join(datos["localidades"])
        if datos["localidades_total"] > len(datos["localidades"]):
            muestra += ", …"
        texto += (
            f" Localidades que no coinciden con el catálogo ({datos['localidades_total']}, quedan como texto): "
            f"{muestra}. Corregí el Excel si querés que se vinculen al legajo."
        )
    hay_problemas = bool(datos["rechazadas"] or datos["fechas_invalidas"] or datos["localidades_total"])
    return {"tono": "warning" if hay_problemas else "success", "titulo": "Última carga del padrón", "texto": texto}


def _subir_padron(request, duenio, destino, clave, prefijo=""):
    """Sube el Excel del padrón a `duenio` y vuelve a `destino` (RED-53).

    Las dos pantallas que cargan padrón —la convocatoria (Cambio 57) y el
    relevamiento con padrón propio (Cambio 74)— tenían este cuerpo escrito dos
    veces, igual salvo el objeto, la URL de vuelta y el prefijo del aviso. Eran
    dos de los quince clones que midió la auditoría: el riesgo real es que una
    corrección —el mensaje, el orden de `parsear` y `cargar`, el no borrar el
    padrón anterior si el archivo no se entiende— entre en una copia y no en la
    otra. Lo que **no** se unifica es la autorización: la convocatoria filtra por
    `convocatorias_visibles` y el relevamiento llama a `assert_alcance_relevamiento`, que son
    guardas distintas y se quedan en cada vista.

    `clave` es la del resumen fijo en sesión (`conv-<pk>` / `rel-<pk>`): la lee el
    detalle de cada pantalla, así que no se puede derivar del objeto sin atar las
    dos cosas.
    """
    archivo = request.FILES.get("padron")
    if archivo is None:
        messages.error(
            request, "Adjuntá el Excel del padrón (.xlsx): documento, sexo y, si los tenés, los datos de identidad."
        )
        return redirect(destino)
    from django.core.exceptions import ValidationError as DjangoValidationError

    from programas.services.padron import cargar_padron, parsear_padron

    try:
        entradas, resumen_parseo = parsear_padron(archivo)
    except DjangoValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return redirect(destino)
    resumen = cargar_padron(duenio, archivo, entradas, usuario=request.user)
    resumen.rechazadas = resumen_parseo.rechazadas
    resumen.fechas_invalidas = resumen_parseo.fechas_invalidas
    _informar_carga_padron(request, clave, resumen, prefijo=prefijo)
    return redirect(destino)


@login_required
@requiere(CAP_CONVOCATORIA_EDITAR)
@require_POST
def convocatoria_padron(request, pk):
    """Carga o reemplaza el padrón de habilitados de la convocatoria (Cambio 57).

    Reemplazo total, con efecto inmediato en el paso 1 del link y en la app de
    campo. Al terminar, los casos pendientes que figuren con nombre y apellido
    quedan validados por padrón (cruce automático, RN-5). Quien edita la
    convocatoria administra su padrón: admin del programa y coordinador.
    """
    conv = get_object_or_404(convocatorias_visibles(request.user).select_related("segmento"), pk=pk)
    return _subir_padron(
        request,
        conv,
        reverse("becas:convocatoria_detalle", kwargs={"pk": conv.pk}),
        f"conv-{conv.pk}",
    )


@login_required
@requiere(CAP_CONVOCATORIA_EDITAR)
@require_POST
def relevamiento_padron(request, pk):
    """Carga o reemplaza el padrón **propio** de un relevamiento (Cambio 74).

    Con padrón propio, el relevamiento deja de heredar el de la convocatoria:
    habilita e identifica solo con el suyo. Al cargar, se cruzan y validan los
    casos pendientes de este relevamiento (RN-5).
    """
    rel = get_object_or_404(Relevamiento.objects.select_related("convocatoria__segmento"), pk=pk)
    assert_alcance_relevamiento(request.user, rel)
    return _subir_padron(
        request,
        rel,
        reverse("becas:relevamiento_detalle", kwargs={"pk": rel.pk}),
        f"rel-{rel.pk}",
        prefijo="Padrón propio de este relevamiento. ",
    )


@login_required
@requiere(CAP_CONVOCATORIA_EDITAR)
@require_POST
def relevamiento_padron_quitar(request, pk):
    """Quita el padrón propio: el relevamiento vuelve a heredar el de la
    convocatoria (o queda abierto si la convocatoria no tiene)."""
    rel = get_object_or_404(Relevamiento.objects.select_related("convocatoria__segmento"), pk=pk)
    assert_alcance_relevamiento(request.user, rel)
    from programas.services.padron import quitar_padron_propio

    filas = quitar_padron_propio(rel)
    if filas:
        messages.success(request, f"Padrón propio quitado ({filas} personas): vuelve a regir el de la convocatoria.")
    else:
        messages.info(request, "Este relevamiento no tenía padrón propio.")
    return redirect(reverse("becas:relevamiento_detalle", kwargs={"pk": rel.pk}))


@login_required
@requiere(CAP_CONVOCATORIA_VER)
def convocatoria_padron_plantilla(request, pk):
    """El .xlsx de ejemplo con las seis columnas, para que el organismo arme el
    padrón con el formato que el sistema espera."""
    get_object_or_404(convocatorias_visibles(request.user), pk=pk)
    from programas.services.padron import plantilla_padron

    respuesta = HttpResponse(
        plantilla_padron(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    respuesta["Content-Disposition"] = 'attachment; filename="plantilla-padron-habilitados.xlsx"'
    return respuesta


@login_required
@requiere(CAP_RELEVAMIENTO_EDITAR)
def relevamiento_reprogramar(request, pk):
    rel = get_object_or_404(Relevamiento.objects.select_related("convocatoria__segmento"), pk=pk)
    assert_alcance_relevamiento(request.user, rel)
    if _rechazar_si_pausado(request, rel):
        return redirect("becas:relevamiento_detalle", pk=rel.pk)
    if request.method == "POST":
        form = ReprogramarForm(request.POST, convocatoria=rel.convocatoria)
        if form.is_valid():
            rel.fecha_asignada = form.cleaned_data["fecha_asignada"]
            rel.fecha_hasta = form.cleaned_data["fecha_hasta"]
            rel.save(update_fields=["fecha_asignada", "fecha_hasta", "modificado"])
            messages.success(request, "Relevamiento reprogramado.")
        else:
            messages.error(request, next(iter(form.errors.values()))[0])
    return redirect("becas:relevamiento_detalle", pk=rel.pk)


@login_required
@requiere(CAP_RELEVAMIENTO_CREAR)
@require_POST
def relevamiento_modificar_cupo(request, pk):
    rel = get_object_or_404(Relevamiento.objects.select_related("convocatoria__segmento"), pk=pk)
    assert_alcance_relevamiento(request.user, rel)
    form = CupoRelevamientoForm(request.POST, instance=rel)
    if form.is_valid():
        form.save()
        messages.success(request, "Cupo del relevamiento actualizado.")
    else:
        messages.error(request, next(iter(form.errors.values()))[0])
    return redirect("becas:relevamiento_detalle", pk=rel.pk)
