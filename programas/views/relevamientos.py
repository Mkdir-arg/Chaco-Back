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
from programas.models import Convocatoria, Formulario, ListaEspera, Relevamiento
from programas.services.autorizacion import (
    convocatorias_visibles,
    programa_becas,
    puede_gestionar_segmento,
    segmentos_visibles,
    subsegmentos_visibles,
    usuarios_territoriales_becas,
)
from programas.views.ajax_utils import ajax_errors, ajax_ok, ajax_redirect, is_ajax

CAP_CONVOCATORIA_VER = "becas.convocatoria.ver"
CAP_CONVOCATORIA_CREAR = "becas.convocatoria.crear"
CAP_CONVOCATORIA_EDITAR = "becas.convocatoria.editar"
logger = logging.getLogger(__name__)

CAP_RELEVAMIENTO_VER = "becas.relevamiento.ver"
CAP_RELEVAMIENTO_CREAR = "becas.relevamiento.crear"
CAP_RELEVAMIENTO_EDITAR = "becas.relevamiento.editar"
# Gateo del formulario público (RN-P13, análisis #289): sin esta capacidad los
# relevamientos públicos no existen para el usuario (ni selector, ni listados).
CAP_RELEVAMIENTO_PUBLICO = "becas.relevamiento.publico"
CAP_REPORTES = "becas.programa.administrar"
DETALLE_PAGE_SIZE = 50


def _paginate(request, queryset, page_param="page", per_page=DETALLE_PAGE_SIZE):
    paginator = Paginator(queryset, per_page)
    return paginator.get_page(request.GET.get(page_param))


def _querystring_without(request, *keys):
    params = request.GET.copy()
    for key in keys:
        params.pop(key, None)
    return params.urlencode()


def _puede_publico(user):
    return puede(user, CAP_RELEVAMIENTO_PUBLICO)


def _sin_publicos_si_no_puede(qs, user):
    """Excluye los relevamientos públicos para quien no tiene la capacidad."""
    if _puede_publico(user):
        return qs
    return qs.exclude(tipo=Relevamiento.Tipo.PUBLICO)


def _sin_formularios_publicos_si_no_puede(qs, user):
    if _puede_publico(user):
        return qs
    return qs.exclude(relevamiento__tipo=Relevamiento.Tipo.PUBLICO)


def _convocatorias_qs(request):
    return (
        Convocatoria.objects.select_related("segmento", "subsegmento")
        .defer("descripcion", "segmento__descripcion", "subsegmento__descripcion")
        .annotate(n_relevamientos=Count("relevamientos", distinct=True))
        .filter(pk__in=convocatorias_visibles(request.user))
        .order_by("-fecha_inicio", "nombre")
    )


def _convocatorias_ajax(request, message="Convocatoria guardada."):
    return ajax_ok(
        request,
        target="#convocatorias-table",
        partial="programas/becas/relevamientos/_convocatorias_table.html",
        context={"convocatorias": _convocatorias_qs(request)},
        message=message,
    )


def _relevamientos_ajax(request, convocatoria, message="Relevamiento creado y asignado."):
    """Re-renderiza la tabla de relevamientos de una convocatoria (pestaña
    "Relevamientos" de su detalle) tras crear uno desde el modal embebido."""
    relevamientos = list(
        _sin_publicos_si_no_puede(convocatoria.relevamientos.select_related("territorial"), request.user).order_by(
            "-fecha_asignada"
        )
    )
    return ajax_ok(
        request,
        target="#relevamientos-table",
        partial="programas/becas/relevamientos/_relevamientos_tab_table.html",
        context={"relevamientos": relevamientos},
        message=message,
    )


def _assert_scope(request, relevamiento):
    """403 si el usuario no puede gestionar el segmento del relevamiento, o si
    es público y no tiene la capacidad (RN-P13: ocultar no es bloquear)."""
    if relevamiento.es_publico and not _puede_publico(request.user):
        raise PermissionDenied("No tiene acceso a este relevamiento.")
    programa = programa_becas()
    if (
        not puede_gestionar_segmento(request.user, relevamiento.segmento, programa=programa)
        or not convocatorias_visibles(request.user, programa=programa).filter(pk=relevamiento.convocatoria_id).exists()
    ):
        raise PermissionDenied("No tiene acceso a este relevamiento.")


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
        return convocatorias_visibles(self.request.user).select_related("segmento", "subsegmento")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        conv = self.object
        relevamientos_qs = _sin_publicos_si_no_puede(
            conv.relevamientos.select_related("territorial"), self.request.user
        ).order_by("-fecha_asignada")
        relevamientos = list(relevamientos_qs)
        formularios_base = _sin_formularios_publicos_si_no_puede(
            Formulario.objects.filter(relevamiento__convocatoria=conv),
            self.request.user,
        )
        ctx["relevamientos"] = relevamientos
        ctx["beneficiarios"] = _paginate(
            self.request,
            formularios_base.select_related("ciudadano", "relevamiento").order_by("-creado"),
            page_param="beneficiarios_page",
        )
        ctx["n_relevamientos"] = len(relevamientos)
        conteos = formularios_base.aggregate(
            total=Count("pk"),
            aprobados=Count("pk", filter=Q(estado=Formulario.Estado.APROBADO)),
        )
        ctx["n_beneficiarios"] = conteos["total"] or 0
        ctx["n_aprobados"] = conteos["aprobados"] or 0
        ctx["beneficiarios_querystring"] = _querystring_without(self.request, "beneficiarios_page", "tab")
        ctx["puede_reportes"] = puede(self.request.user, CAP_REPORTES)
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
        ctx["siguiente_nombre"] = Relevamiento.proximo_nombre()
        # Padrón de habilitados (Cambio 57; herencia por relevamiento, Cambio 59):
        # acá se administra el de la convocatoria, que heredan los relevamientos
        # sin padrón propio. Un solo aggregate trae los dos niveles.
        nivel_convocatoria = Q(relevamiento__isnull=True)
        conteo_padron = conv.padron.aggregate(
            total=Count("pk", filter=nivel_convocatoria),
            con_identidad=Count("pk", filter=nivel_convocatoria & ~Q(nombre="") & ~Q(apellido="")),
            rels_propios=Count("relevamiento", distinct=True),
        )
        ctx["n_padron"] = conteo_padron["total"] or 0
        ctx["n_padron_identidad"] = conteo_padron["con_identidad"] or 0
        ctx["n_rels_padron_propio"] = conteo_padron["rels_propios"] or 0
        ctx["puede_padron"] = puede(self.request.user, CAP_CONVOCATORIA_EDITAR)
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
    destino = request.POST.get("next") or "becas:convocatorias"
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
    destino = request.POST.get("next") or "becas:convocatorias"

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
@requiere(CAP_REPORTES)
def convocatoria_export_beneficiarios(request, pk):
    conv = get_object_or_404(Convocatoria.objects.select_related("segmento"), pk=pk)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="beneficiarios_convocatoria_{conv.pk}.csv"'
    response.write("﻿")  # BOM para Excel
    writer = csv.writer(response)
    writer.writerow(["Nombre", "DNI", "Segmento", "Convocatoria", "Fecha de aprobación"])
    formularios = (
        _sin_formularios_publicos_si_no_puede(
            Formulario.objects.filter(relevamiento__convocatoria=conv, estado=Formulario.Estado.APROBADO),
            request.user,
        )
        .select_related("ciudadano", "relevamiento")
        .order_by("-creado")
    )
    for f in formularios:
        if f.ciudadano_id:
            dni = f.ciudadano.dni
            nombre = f.ciudadano.nombre_completo
        else:
            ident = f.datos_identificacion or {}
            dni = ident.get("dni", "")
            nombre = f"{ident.get('nombre', '')} {ident.get('apellido', '')}".strip()
        writer.writerow([nombre, dni, conv.segmento.nombre, conv.nombre, f.modificado.strftime("%d/%m/%Y")])
    return response


@login_required
@requiere(CAP_REPORTES)
def convocatoria_export_relevamientos(request, pk):
    conv = get_object_or_404(Convocatoria, pk=pk)
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
        _sin_publicos_si_no_puede(conv.relevamientos.select_related("territorial"), request.user)
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
                r.nombre,
                terr,
                timezone.localtime(r.fecha_asignada).strftime("%d/%m/%Y %H:%M"),
                timezone.localtime(r.fecha_hasta).strftime("%d/%m/%Y %H:%M"),
                r.zona,
                r.get_estado_display(),
                r.n_enviados,
                r.n_aprobados,
                r.n_rechazados,
            ]
        )
    return response


@login_required
@requiere(CAP_REPORTES)
def convocatoria_export_lista_espera(request, pk):
    conv = get_object_or_404(Convocatoria.objects.select_related("segmento"), pk=pk)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="lista_espera_convocatoria_{conv.pk}.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(["Posición", "Nombre", "DNI", "Segmento", "Fecha de ingreso"])
    entradas = (
        ListaEspera.objects.filter(formulario__relevamiento__convocatoria=conv, promovido=False)
        .select_related("formulario__ciudadano", "segmento")
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
            [entrada.posicion, nombre, dni, entrada.segmento.nombre, entrada.fecha_ingreso.strftime("%d/%m/%Y")]
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
        qs = _sin_publicos_si_no_puede(qs, self.request.user)

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
        query_params = self.request.GET.copy()
        query_params.pop("page", None)
        ctx["querystring"] = query_params.urlencode()
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
        ctx["siguiente_nombre"] = Relevamiento.proximo_nombre()
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
            if not self.object.convocatoria.padron.exists():
                mensaje += " La convocatoria no tiene padrón: el link queda abierto."
            if is_ajax(self.request):
                return ajax_redirect(detalle, mensaje)
            messages.success(self.request, mensaje)
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
    # El template y _assert_scope recorren convocatoria/segmento/territorial.
    # El padrón es de la convocatoria (Cambio 57): su tamaño viaja anotado en
    # la misma consulta para no sumar una lectura al presupuesto de la ruta.
    # Los dos niveles del padrón en la misma consulta (Cambio 59): el propio
    # del relevamiento y el de la convocatoria que heredaría si no tiene.
    queryset = Relevamiento.objects.select_related(
        "convocatoria__segmento", "convocatoria__subsegmento", "territorial"
    ).annotate(
        n_padron_propio=Count("convocatoria__padron", filter=Q(convocatoria__padron__relevamiento_id=F("pk"))),
        n_padron_convocatoria=Count("convocatoria__padron", filter=Q(convocatoria__padron__relevamiento__isnull=True)),
    )
    capacidades_requeridas = CAP_RELEVAMIENTO_VER
    template_name = "programas/becas/relevamientos/relevamiento_detail.html"
    context_object_name = "relevamiento"

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        _assert_scope(self.request, obj)
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
        ctx["form_reasignar"] = ReasignarTerritorialForm(
            initial={"territorial": rel.territorial}, segmento=rel.convocatoria.segmento
        )
        ctx["form_reprogramar"] = ReprogramarForm(
            initial={"fecha_asignada": rel.fecha_asignada, "fecha_hasta": rel.fecha_hasta},
            convocatoria=rel.convocatoria,
        )
        ctx["form_cupo"] = CupoRelevamientoForm(instance=rel)
        ctx["form_volver_a_campo"] = VolverACampoForm(convocatoria=rel.convocatoria)
        formularios_qs = rel.formularios.select_related("ciudadano").order_by("numero")
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
    _assert_scope(request, rel)
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
    _assert_scope(request, rel)
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
    _assert_scope(request, rel)
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
    destino = reverse("becas:convocatoria_detalle", kwargs={"pk": conv.pk})
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
    resumen = cargar_padron(conv, archivo, entradas, usuario=request.user)
    resumen.rechazadas = resumen_parseo.rechazadas
    resumen.fechas_invalidas = resumen_parseo.fechas_invalidas
    messages.success(request, resumen.mensaje())
    if resumen.localidades_no_reconocidas:
        muestra = ", ".join(resumen.localidades_no_reconocidas[:8])
        if len(resumen.localidades_no_reconocidas) > 8:
            muestra += ", …"
        messages.warning(
            request,
            f"Localidades que no coinciden con el catálogo (quedan como texto): {muestra}. "
            "Corregí el Excel si querés que se vinculen al legajo.",
        )
    return redirect(destino)


@login_required
@requiere(CAP_CONVOCATORIA_EDITAR)
@require_POST
def relevamiento_padron(request, pk):
    """Carga o reemplaza el padrón **propio** de un relevamiento (Cambio 59).

    Con padrón propio, el relevamiento deja de heredar el de la convocatoria:
    habilita e identifica solo con el suyo. Al cargar, se cruzan y validan los
    casos pendientes de este relevamiento (RN-5).
    """
    rel = get_object_or_404(Relevamiento.objects.select_related("convocatoria__segmento"), pk=pk)
    _assert_scope(request, rel)
    destino = reverse("becas:relevamiento_detalle", kwargs={"pk": rel.pk})
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
    resumen = cargar_padron(rel, archivo, entradas, usuario=request.user)
    resumen.rechazadas = resumen_parseo.rechazadas
    resumen.fechas_invalidas = resumen_parseo.fechas_invalidas
    messages.success(request, "Padrón propio de este relevamiento. " + resumen.mensaje())
    if resumen.localidades_no_reconocidas:
        muestra = ", ".join(resumen.localidades_no_reconocidas[:8])
        if len(resumen.localidades_no_reconocidas) > 8:
            muestra += ", …"
        messages.warning(
            request,
            f"Localidades que no coinciden con el catálogo (quedan como texto): {muestra}. "
            "Corregí el Excel si querés que se vinculen al legajo.",
        )
    return redirect(destino)


@login_required
@requiere(CAP_CONVOCATORIA_EDITAR)
@require_POST
def relevamiento_padron_quitar(request, pk):
    """Quita el padrón propio: el relevamiento vuelve a heredar el de la
    convocatoria (o queda abierto si la convocatoria no tiene)."""
    rel = get_object_or_404(Relevamiento.objects.select_related("convocatoria__segmento"), pk=pk)
    _assert_scope(request, rel)
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
    _assert_scope(request, rel)
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
    _assert_scope(request, rel)
    form = CupoRelevamientoForm(request.POST, instance=rel)
    if form.is_valid():
        form.save()
        messages.success(request, "Cupo del relevamiento actualizado.")
    else:
        messages.error(request, next(iter(form.errors.values()))[0])
    return redirect("becas:relevamiento_detalle", pk=rel.pk)
