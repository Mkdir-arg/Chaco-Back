"""Backoffice — Revisión de formularios de Becas (#77).

Acceso granular: ``becas.revision.ver`` para listar/consultar, ``becas.revision.editar``
para iniciar revisión, editar contacto, aprobar/rechazar y terminar. Con alcance
por segmento. La validación SIS es un placeholder.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.dateparse import parse_date
from django.views.generic import ListView

from core.rbac import CapacidadRequeridaMixin, puede, puede_alguna, requiere
from legajos.services.consulta_renaper import consultar_datos_renaper
from programas.forms import FormularioRevisionForm
from programas.models import (
    Formulario,
    PreguntaGlobal,
    Relevamiento,
    RequisitoNativo,
    Segmento,
    TipoCampo,
)
from programas.services.autorizacion import puede_gestionar_segmento, segmentos_visibles
from programas.services.becas import registrar_traza
from programas.services.cupo import aprobar_o_poner_en_espera

CAP_REVISION_VER = "becas.revision.ver"
CAP_REVISION_EDITAR = "becas.revision.editar"
CAP_REVALIDAR_RENAPER = "becas.programa.administrar"


def _assert_scope_relevamiento(request, relevamiento):
    if not puede_gestionar_segmento(request.user, relevamiento.segmento):
        raise PermissionDenied("No tiene acceso a este relevamiento.")


def _assert_scope_formulario(request, formulario):
    if not puede_gestionar_segmento(request.user, formulario.relevamiento.segmento):
        raise PermissionDenied("No tiene acceso a este formulario.")


class RevisionPersonasListView(CapacidadRequeridaMixin, LoginRequiredMixin, ListView):
    """Personas relevadas (formularios sincronizados), con su convocatoria y
    relevamiento. Puerta de entrada a la revisión caso a caso."""

    capacidades_requeridas = CAP_REVISION_VER
    template_name = "programas/becas/revision/personas_list.html"
    context_object_name = "formularios"
    paginate_by = 25

    def get_queryset(self):
        qs = (
            Formulario.objects.select_related(
                "ciudadano", "relevamiento__convocatoria__segmento", "relevamiento__territorial"
            )
            .filter(relevamiento__convocatoria__segmento__in=segmentos_visibles(self.request.user))
            .order_by("-creado")
        )
        estado = self.request.GET.get("estado")
        if estado:
            qs = qs.filter(estado=estado)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["estados"] = Formulario.Estado.choices
        ctx["estado_actual"] = self.request.GET.get("estado", "")
        ctx["puede_revalidar_renaper"] = puede(self.request.user, CAP_REVALIDAR_RENAPER)
        ctx["pendientes_renaper"] = Formulario.objects.filter(validado_renaper=False).count()
        return ctx


class RenaperPendientesListView(CapacidadRequeridaMixin, LoginRequiredMixin, ListView):
    capacidades_requeridas = CAP_REVALIDAR_RENAPER
    template_name = "programas/becas/revision/renaper_pendientes.html"
    context_object_name = "formularios"
    paginate_by = 50

    def get_queryset(self):
        queryset = Formulario.objects.filter(validado_renaper=False).select_related(
            "ciudadano", "relevamiento__territorial", "relevamiento__convocatoria__segmento"
        )
        if self.request.GET.get("fecha"):
            queryset = queryset.filter(creado__date=self.request.GET["fecha"])
        if self.request.GET.get("territorial"):
            queryset = queryset.filter(relevamiento__territorial_id=self.request.GET["territorial"])
        if self.request.GET.get("segmento"):
            queryset = queryset.filter(relevamiento__convocatoria__segmento_id=self.request.GET["segmento"])
        return queryset.order_by("-creado")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        base = Formulario.objects.filter(validado_renaper=False)
        context["territoriales"] = (
            base.values("relevamiento__territorial_id", "relevamiento__territorial__username")
            .distinct()
            .order_by("relevamiento__territorial__username")
        )
        context["segmentos"] = (
            Segmento.objects.filter(convocatorias__relevamientos__formularios__validado_renaper=False)
            .distinct()
            .order_by("nombre")
        )
        context["filtros"] = self.request.GET
        return context


@login_required
@requiere(CAP_REVISION_VER)
def revision_formularios(request, relevamiento_pk):
    relevamiento = get_object_or_404(Relevamiento.objects.select_related("convocatoria__segmento"), pk=relevamiento_pk)
    _assert_scope_relevamiento(request, relevamiento)

    formularios = relevamiento.formularios.select_related("ciudadano").order_by("-creado")
    estado = request.GET.get("estado")
    if estado:
        formularios = formularios.filter(estado=estado)

    return render(
        request,
        "programas/becas/revision/formulario_list.html",
        {
            "relevamiento": relevamiento,
            "formularios": formularios,
            "estados": Formulario.Estado.choices,
            "estado_actual": estado or "",
            "pendientes": relevamiento.formularios.filter(estado=Formulario.Estado.ENVIADO).count(),
        },
    )


def _respuestas_resueltas(formulario):
    """Arma listas legibles de respuestas (pregunta/requisito → valor).

    Los campos tipo ARCHIVO no traen el archivo en ``data`` (ahí la app de
    campo solo deja un placeholder tipo ``{"pendiente_upload": true}``): el
    archivo real se resuelve contra ``AdjuntoFormulario`` (#82).
    """
    data = formulario.data or {}
    globales = data.get("globales", {}) or {}
    requisitos = data.get("requisitos", {}) or {}

    preguntas = {str(p.pk): p for p in PreguntaGlobal.objects.all()}
    req_ids = [int(k) for k in requisitos.keys() if str(k).isdigit()]
    requisitos_map = {str(r.pk): r for r in RequisitoNativo.objects.filter(pk__in=req_ids)}

    adjuntos_pregunta = {a.pregunta_global_id: a for a in formulario.adjuntos.filter(pregunta_global__isnull=False)}
    adjuntos_requisito = {a.requisito_nativo_id: a for a in formulario.adjuntos.filter(requisito_nativo__isnull=False)}

    def _fila(campo_map, adjuntos_map, k, v):
        campo = campo_map.get(str(k))
        label = campo.texto if campo else f"Campo #{k}"
        es_archivo = campo is not None and campo.tipo == TipoCampo.ARCHIVO
        adjunto = adjuntos_map.get(int(k)) if es_archivo and str(k).isdigit() else None
        return {"label": label, "valor": v, "es_archivo": es_archivo, "adjunto": adjunto}

    globales_list = [_fila(preguntas, adjuntos_pregunta, k, v) for k, v in globales.items()]
    requisitos_list = [_fila(requisitos_map, adjuntos_requisito, k, v) for k, v in requisitos.items()]
    return globales_list, requisitos_list


@login_required
@requiere(CAP_REVISION_VER, CAP_REVISION_EDITAR)
def formulario_detalle(request, pk):
    formulario = get_object_or_404(
        Formulario.objects.select_related("relevamiento__convocatoria__segmento", "ciudadano"), pk=pk
    )
    _assert_scope_formulario(request, formulario)

    if request.method == "POST":
        if not puede_alguna(request.user, [CAP_REVISION_EDITAR]):
            raise PermissionDenied("No tiene permisos para editar este formulario.")
        # Edición de campos de contacto/apoderado con traza por cambio.
        anteriores = {f: getattr(formulario, f) for f in FormularioRevisionForm.Meta.fields}
        form = FormularioRevisionForm(request.POST, instance=formulario)
        if form.is_valid():
            cambios = []
            for campo in FormularioRevisionForm.Meta.fields:
                nuevo = form.cleaned_data[campo]
                if anteriores[campo] != nuevo:
                    cambios.append((FormularioRevisionForm.LABELS[campo], anteriores[campo], nuevo))
            form.save()
            n = registrar_traza(formulario, request.user, cambios)
            if n:
                messages.success(request, f"Formulario actualizado ({n} cambio(s) registrado(s)).")
            else:
                messages.info(request, "No hubo cambios para guardar.")
            return redirect("becas:formulario_detalle", pk=formulario.pk)
    else:
        form = FormularioRevisionForm(instance=formulario)

    globales_list, requisitos_list = _respuestas_resueltas(formulario)
    return render(
        request,
        "programas/becas/revision/formulario_detalle.html",
        {
            "formulario": formulario,
            "relevamiento": formulario.relevamiento,
            "form": form,
            "globales_list": globales_list,
            "requisitos_list": requisitos_list,
            "trazas": formulario.trazas.select_related("editado_por")[:50],
            "puede_revalidar_renaper": puede(request.user, CAP_REVALIDAR_RENAPER),
        },
    )


@login_required
@requiere(CAP_REVISION_EDITAR)
def formulario_aprobar(request, pk):
    formulario = get_object_or_404(Formulario.objects.select_related("relevamiento__convocatoria__segmento"), pk=pk)
    _assert_scope_formulario(request, formulario)
    if request.method == "POST":
        try:
            resultado = aprobar_o_poner_en_espera(formulario, request.user)
        except ValidationError as e:
            messages.error(request, e.message)
        else:
            if resultado == "aprobado":
                messages.success(request, "Formulario aprobado.")
            else:
                segmento = formulario.relevamiento.convocatoria.segmento
                messages.warning(
                    request,
                    f"No hay cupo disponible en {segmento.nombre}: se agregó a la lista de espera.",
                )
    return redirect("becas:formulario_detalle", pk=formulario.pk)


@login_required
@requiere(CAP_REVISION_EDITAR)
def formulario_rechazar(request, pk):
    formulario = get_object_or_404(Formulario.objects.select_related("relevamiento__convocatoria__segmento"), pk=pk)
    _assert_scope_formulario(request, formulario)
    if request.method == "POST":
        motivo = (request.POST.get("motivo") or "").strip()
        if not motivo:
            messages.error(request, "Debés indicar el motivo del rechazo.")
            return redirect("becas:formulario_detalle", pk=formulario.pk)
        estado_anterior = formulario.estado
        formulario.estado = Formulario.Estado.RECHAZADO
        formulario.motivo_rechazo = motivo
        formulario.save(update_fields=["estado", "motivo_rechazo", "modificado"])
        registrar_traza(formulario, request.user, [("estado", estado_anterior, f"RECHAZADO: {motivo}")])
        messages.success(request, "Formulario rechazado.")
    return redirect("becas:formulario_detalle", pk=formulario.pk)


@login_required
@requiere(CAP_REVALIDAR_RENAPER)
def formulario_revalidar_renaper(request, pk):
    formulario = get_object_or_404(Formulario.objects.select_related("ciudadano"), pk=pk)
    if request.method != "POST":
        return redirect("becas:formulario_detalle", pk=formulario.pk)
    ciudadano = formulario.ciudadano
    if ciudadano is None:
        messages.error(request, "El formulario no tiene un ciudadano vinculado para revalidar.")
        return redirect("becas:formulario_detalle", pk=formulario.pk)
    if not ciudadano.genero:
        messages.error(request, "El ciudadano no tiene sexo registrado; completalo antes de consultar RENAPER.")
        return redirect("becas:formulario_detalle", pk=formulario.pk)

    resultado = consultar_datos_renaper(ciudadano.dni, ciudadano.genero)
    if not resultado.get("success"):
        mensaje = resultado.get("error") or "RENAPER no pudo validar a la persona."
        if resultado.get("fallecido"):
            mensaje = "RENAPER informa que la persona está fallecida."
        messages.error(request, mensaje)
        return redirect("becas:formulario_detalle", pk=formulario.pk)

    datos = resultado.get("data") or {}
    cambios = []
    nuevos = {
        "nombre": datos.get("nombre") or ciudadano.nombre,
        "apellido": datos.get("apellido") or ciudadano.apellido,
        "genero": datos.get("sexo") or datos.get("genero") or ciudadano.genero,
    }
    fecha = datos.get("fecha_nacimiento")
    if isinstance(fecha, str):
        try:
            fecha = parse_date(fecha)
        except ValueError:
            fecha = None
    if fecha:
        nuevos["fecha_nacimiento"] = fecha

    with transaction.atomic():
        campos_actualizados = []
        for campo, nuevo in nuevos.items():
            anterior = getattr(ciudadano, campo)
            if anterior != nuevo:
                setattr(ciudadano, campo, nuevo)
                campos_actualizados.append(campo)
                cambios.append((f"Ciudadano · {campo}", anterior, nuevo))
        if campos_actualizados:
            ciudadano.save(update_fields=[*campos_actualizados, "modificado"])
        if not formulario.validado_renaper:
            formulario.validado_renaper = True
            formulario.save(update_fields=["validado_renaper", "modificado"])
            cambios.append(("RENAPER", "Pendiente", "Validado"))
        registrar_traza(formulario, request.user, cambios)

    messages.success(request, "Identidad revalidada correctamente con RENAPER.")
    return redirect("becas:formulario_detalle", pk=formulario.pk)


@login_required
@requiere(CAP_REVISION_EDITAR)
def relevamiento_iniciar_revision(request, pk):
    rel = get_object_or_404(Relevamiento.objects.select_related("convocatoria__segmento"), pk=pk)
    _assert_scope_relevamiento(request, rel)
    if request.method == "POST" and rel.estado == Relevamiento.Estado.FINALIZADO:
        rel.estado = Relevamiento.Estado.EN_REVISION
        rel.save(update_fields=["estado", "modificado"])
        messages.success(request, "Relevamiento marcado en revisión.")
    return redirect("becas:revision_formularios", relevamiento_pk=rel.pk)


@login_required
@requiere(CAP_REVISION_EDITAR)
def relevamiento_terminar(request, pk):
    rel = get_object_or_404(Relevamiento.objects.select_related("convocatoria__segmento"), pk=pk)
    _assert_scope_relevamiento(request, rel)
    if request.method == "POST" and rel.estado == Relevamiento.Estado.EN_REVISION:
        pendientes = rel.formularios.filter(estado=Formulario.Estado.ENVIADO).count()
        if pendientes:
            messages.error(request, f"Quedan {pendientes} formulario(s) sin revisar.")
        else:
            rel.estado = Relevamiento.Estado.TERMINADO
            rel.save(update_fields=["estado", "modificado"])
            messages.success(request, "Relevamiento terminado.")
    return redirect("becas:revision_formularios", relevamiento_pk=rel.pk)
