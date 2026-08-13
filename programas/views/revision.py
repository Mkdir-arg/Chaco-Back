"""Backoffice — Revisión de formularios de Becas (#77).

Acceso granular: ``becas.revision.ver`` para listar/consultar, ``becas.revision.editar``
para iniciar revisión, editar contacto, aprobar/rechazar y terminar. Con alcance
por segmento. La validación SIIS conserva y presenta el detalle auditable de ECOM.
"""

from pathlib import Path
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Exists, OuterRef
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.dateparse import parse_date, parse_datetime
from django.views.generic import ListView

from core.rbac import CapacidadRequeridaMixin, puede, puede_alguna, requiere
from programas.forms import CiudadanoGeneroRevisionForm, FormularioRevisionForm
from programas.models import (
    Formulario,
    PreguntaGlobal,
    Relevamiento,
    RequisitoNativo,
    Segmento,
    TipoCampo,
    ValidacionSIS,
)
from programas.services.autorizacion import convocatorias_visibles, puede_gestionar_segmento
from programas.services.becas import es_menor, registrar_traza, resolver_ciudadano_offline
from programas.services.cupo import aprobar_o_poner_en_espera, motivo_bloqueo_aprobacion
from programas.services.personas import consultar_persona
from programas.services.siis import motivos_de_rechazo, validar_compatibilidad

CAP_REVISION_VER = "becas.revision.ver"
CAP_REVISION_EDITAR = "becas.revision.editar"
CAP_REVALIDAR_RENAPER = "becas.programa.administrar"
EXTENSIONES_IMAGEN = {".avif", ".gif", ".jpeg", ".jpg", ".png", ".webp"}

SIIS_CONTROLES = (
    ("vigencia_programa", "Vigencia del programa"),
    ("edad_minima", "Edad mínima"),
    ("empleo_publico", "Empleo público"),
    ("horas_docentes", "Horas docentes"),
    ("duplicidad_becas", "Otros beneficios o becas"),
)
SIIS_VALORES_FAVORABLES = {"VIGENTE", "CUMPLE_EDAD_MINIMA", "SIN_INCOMPATIBILIDAD"}
SIIS_VALORES_INFORMATIVOS = {"NO_EVALUADO_SIN_FECHA"}
SIIS_ETIQUETAS_VALOR = {
    "VIGENTE": "Programa vigente",
    "PROGRAMA_INACTIVO": "Programa inactivo",
    "CUMPLE_EDAD_MINIMA": "Cumple la edad mínima",
    "EDAD_INSUFICIENTE": "No cumple la edad mínima",
    "NO_EVALUADO_SIN_FECHA": "No evaluado: falta la fecha de nacimiento",
    "SIN_INCOMPATIBILIDAD": "Sin incompatibilidad",
    "INCOMPATIBLE_PLANTA": "Incompatible por empleo público",
    "INCOMPATIBLE_EXCEDE_HORAS": "Incompatible por exceso de horas docentes",
    "BENEFICIO_ACTIVO_EXISTENTE": "Tiene un beneficio activo incompatible",
    "SUSPENDIDO_TEMPORAL": "Tiene una suspensión temporal vigente",
}


def _detalle_validacion_siis(validacion):
    if validacion is None:
        return None
    respuesta = validacion.respuesta if isinstance(validacion.respuesta, dict) else {}
    valores = respuesta.get("validaciones") if isinstance(respuesta.get("validaciones"), dict) else {}
    controles = []
    for clave, etiqueta in SIIS_CONTROLES:
        valor = str(valores.get(clave) or "").strip().upper()
        if not valor:
            continue
        if valor in SIIS_VALORES_FAVORABLES:
            tono = "success"
        elif valor in SIIS_VALORES_INFORMATIVOS:
            tono = "warning"
        else:
            tono = "danger"
        controles.append(
            {
                "etiqueta": etiqueta,
                "detalle": SIIS_ETIQUETAS_VALOR.get(valor, valor.replace("_", " ").capitalize()),
                "tono": tono,
            }
        )
    registrado = respuesta.get("persona_registrada_siis")
    if registrado is True:
        situacion = "Registrado en SIIS"
    elif registrado is False:
        situacion = "Nuevo solicitante"
    else:
        situacion = "No informado"
    return {
        "programa_nombre": respuesta.get("nombre_programa") or "",
        "programa_id": respuesta.get("id_programa") or validacion.id_programa,
        "situacion": situacion,
        "controles": controles,
    }


def _con_conflicto_duplicado_pendiente(queryset):
    conflictos = Formulario.objects.filter(duplicado_de_id=OuterRef("pk"), conflicto_resuelto=False)
    return queryset.annotate(tiene_carga_duplicada_pendiente=Exists(conflictos))


def _assert_scope_relevamiento(request, relevamiento):
    if (
        not puede_gestionar_segmento(request.user, relevamiento.segmento)
        or not convocatorias_visibles(request.user).filter(pk=relevamiento.convocatoria_id).exists()
    ):
        raise PermissionDenied("No tiene acceso a este relevamiento.")


def _assert_scope_formulario(request, formulario):
    if (
        not puede_gestionar_segmento(request.user, formulario.relevamiento.segmento)
        or not convocatorias_visibles(request.user).filter(pk=formulario.relevamiento.convocatoria_id).exists()
    ):
        raise PermissionDenied("No tiene acceso a este formulario.")


def _tiene_conflicto_duplicado_pendiente(formulario):
    return (
        formulario.conflicto_duplicado and not formulario.conflicto_resuelto
    ) or formulario.cargas_en_conflicto.filter(conflicto_resuelto=False).exists()


class RevisionPersonasListView(CapacidadRequeridaMixin, LoginRequiredMixin, ListView):
    """Personas relevadas (formularios sincronizados), con su convocatoria y
    relevamiento. Puerta de entrada a la revisión caso a caso."""

    capacidades_requeridas = CAP_REVISION_VER
    template_name = "programas/becas/revision/personas_list.html"
    context_object_name = "formularios"
    paginate_by = 25

    def get_queryset(self):
        qs = _con_conflicto_duplicado_pendiente(
            Formulario.objects.select_related(
                "ciudadano", "relevamiento__convocatoria__segmento", "relevamiento__territorial"
            )
            .filter(relevamiento__convocatoria__in=convocatorias_visibles(self.request.user))
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

    formularios = _con_conflicto_duplicado_pendiente(
        relevamiento.formularios.select_related("ciudadano").order_by("numero")
    )
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
        es_imagen = bool(adjunto and Path(adjunto.archivo.name or "").suffix.lower() in EXTENSIONES_IMAGEN)
        return {
            "label": label,
            "valor": v,
            "es_multiple": isinstance(v, list),
            "es_archivo": es_archivo,
            "adjunto": adjunto,
            "es_imagen": es_imagen,
            "es_subsegmento": bool(getattr(campo, "subsegmento_id", None)),
        }

    globales_list = [_fila(preguntas, adjuntos_pregunta, k, v) for k, v in globales.items()]
    requisitos_list = [_fila(requisitos_map, adjuntos_requisito, k, v) for k, v in requisitos.items()]
    requisitos_segmento = [item for item in requisitos_list if not item["es_subsegmento"]]
    requisitos_subsegmento = [item for item in requisitos_list if item["es_subsegmento"]]
    return globales_list, requisitos_segmento, requisitos_subsegmento


@login_required
@requiere(CAP_REVISION_VER, CAP_REVISION_EDITAR)
def formulario_detalle(request, pk):
    formulario = get_object_or_404(
        Formulario.objects.select_related("relevamiento__convocatoria__segmento", "ciudadano"), pk=pk
    )
    _assert_scope_formulario(request, formulario)

    conflicto_pendiente = None
    if formulario.conflicto_duplicado and not formulario.conflicto_resuelto:
        conflicto_pendiente = formulario
    else:
        conflicto_pendiente = formulario.cargas_en_conflicto.filter(conflicto_resuelto=False).first()
    formulario_comparacion = None
    if conflicto_pendiente:
        formulario_comparacion = (
            conflicto_pendiente.duplicado_de if formulario.pk == conflicto_pendiente.pk else conflicto_pendiente
        )

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
            resolver_ciudadano_offline(formulario)
            n = registrar_traza(formulario, request.user, cambios)
            if n:
                messages.success(request, f"Formulario actualizado ({n} cambio(s) registrado(s)).")
            else:
                messages.info(request, "No hubo cambios para guardar.")
            return redirect("becas:formulario_detalle", pk=formulario.pk)
    else:
        form = FormularioRevisionForm(instance=formulario)

    globales_list, requisitos_segmento, requisitos_subsegmento = _respuestas_resueltas(formulario)
    fecha_nacimiento = None
    if formulario.ciudadano_id:
        fecha_nacimiento = formulario.ciudadano.fecha_nacimiento
    elif isinstance(formulario.datos_identificacion, dict):
        fecha_nacimiento = formulario.datos_identificacion.get("fecha_nacimiento")
        if isinstance(fecha_nacimiento, str):
            fecha_nacimiento = parse_date(fecha_nacimiento)
    tiene_datos_apoderado = bool(
        formulario.apoderado_nombre
        or formulario.apoderado_apellido
        or formulario.apoderado_dni
        or formulario.apoderado_genero
        or formulario.apoderado_fecha_nacimiento
    )
    mostrar_apoderado = bool(es_menor(fecha_nacimiento) or tiene_datos_apoderado)
    mapa = None
    if formulario.gps_lat is not None and formulario.gps_lng is not None:
        lat = float(formulario.gps_lat)
        lng = float(formulario.gps_lng)
        margen = 0.005
        mapa = {
            "latitud": formulario.gps_lat,
            "longitud": formulario.gps_lng,
            "embed_url": "https://www.openstreetmap.org/export/embed.html?"
            + urlencode(
                {
                    "bbox": (f"{lng - margen:.6f},{lat - margen:.6f},{lng + margen:.6f},{lat + margen:.6f}"),
                    "layer": "mapnik",
                    "marker": f"{lat:.6f},{lng:.6f}",
                }
            ),
            "open_url": "https://www.openstreetmap.org/?"
            + urlencode({"mlat": f"{lat:.6f}", "mlon": f"{lng:.6f}", "zoom": 16}),
        }
    validaciones_sis = list(formulario.validaciones_sis.select_related("solicitado_por"))
    validacion_sis = validaciones_sis[0] if validaciones_sis else None
    historial_validaciones_sis = [
        {"validacion": validacion, "detalle": _detalle_validacion_siis(validacion)}
        for validacion in validaciones_sis
    ]
    return render(
        request,
        "programas/becas/revision/formulario_detalle.html",
        {
            "formulario": formulario,
            "relevamiento": formulario.relevamiento,
            "form": form,
            "genero_form": CiudadanoGeneroRevisionForm(
                initial={"genero": formulario.ciudadano.genero if formulario.ciudadano else ""}
            ),
            "mostrar_apoderado": mostrar_apoderado,
            "globales_list": globales_list,
            "requisitos_segmento": requisitos_segmento,
            "requisitos_subsegmento": requisitos_subsegmento,
            "mapa": mapa,
            "trazas": formulario.trazas.select_related("editado_por")[:50],
            "puede_revalidar_renaper": puede(request.user, CAP_REVALIDAR_RENAPER),
            "validacion_sis": validacion_sis,
            "detalle_siis": _detalle_validacion_siis(validacion_sis),
            "historial_validaciones_sis": historial_validaciones_sis,
            "motivo_bloqueo_aprobacion": motivo_bloqueo_aprobacion(formulario),
            "tiene_conflicto_duplicado_pendiente": _tiene_conflicto_duplicado_pendiente(formulario),
            "conflicto_pendiente": conflicto_pendiente,
            "formulario_comparacion": formulario_comparacion,
        },
    )


@login_required
@requiere(CAP_REVALIDAR_RENAPER)
def formulario_validar_sis(request, pk):
    formulario = get_object_or_404(
        Formulario.objects.select_related("ciudadano", "relevamiento__convocatoria__segmento"), pk=pk
    )
    _assert_scope_formulario(request, formulario)
    if request.method != "POST":
        return redirect("becas:formulario_detalle", pk=formulario.pk)

    convocatoria = formulario.relevamiento.convocatoria
    segmento = convocatoria.segmento
    ciudadano = formulario.ciudadano
    if not segmento.siis_programa_id:
        messages.error(request, "El segmento no tiene configurado el programa correspondiente de SIIS.")
        return redirect("becas:formulario_detalle", pk=formulario.pk)
    if ciudadano is None or not ciudadano.dni:
        messages.error(request, "El formulario no tiene un ciudadano con DNI vinculado.")
        return redirect("becas:formulario_detalle", pk=formulario.pk)

    # SIIS valida contra el programa (nuestro Segmento). El subsegmento es local
    # y ya no participa; la fecha de nacimiento es opcional y solo se usa para
    # evaluar edad mínima cuando la persona no figura en su padrón.
    resultado = validar_compatibilidad(
        ciudadano.dni,
        segmento.siis_programa_id,
        ciudadano.fecha_nacimiento.isoformat() if ciudadano.fecha_nacimiento else None,
    )
    data = resultado.get("data") or {}
    estado = ValidacionSIS.Estado.ERROR
    if resultado.get("success"):
        estado = ValidacionSIS.Estado.OK if resultado.get("compatible") else ValidacionSIS.Estado.RECHAZADO
    motivos = motivos_de_rechazo(data.get("validaciones"))
    ValidacionSIS.objects.create(
        formulario=formulario,
        estado=estado,
        id_programa=segmento.siis_programa_id,
        documento=ciudadano.dni,
        id_consulta=data.get("id_consulta") or None,
        fecha_validacion=parse_datetime(str(data.get("fecha_hora") or "")),
        codigo_motivo=", ".join(bandera for bandera, _ in motivos)[:100],
        motivo=" ".join(texto for _, texto in motivos) or str(resultado.get("error") or ""),
        respuesta=data,
        solicitado_por=request.user,
    )
    if estado == ValidacionSIS.Estado.OK:
        messages.success(request, "SIIS informo que la persona es compatible.")
    elif estado == ValidacionSIS.Estado.RECHAZADO:
        detalle = " ".join(texto for _, texto in motivos) or "sin motivo informado"
        messages.warning(request, f"SIIS rechazo la compatibilidad: {detalle}")
    else:
        messages.error(request, resultado.get("error") or "No se pudo validar contra SIIS.")
    return redirect("becas:formulario_detalle", pk=formulario.pk)


@login_required
@requiere(CAP_REVALIDAR_RENAPER)
def formulario_actualizar_genero(request, pk):
    formulario = get_object_or_404(Formulario.objects.select_related("ciudadano"), pk=pk)
    _assert_scope_formulario(request, formulario)
    if request.method != "POST":
        return redirect("becas:formulario_detalle", pk=formulario.pk)
    if formulario.ciudadano is None:
        messages.error(request, "El formulario no tiene un ciudadano vinculado.")
        return redirect("becas:formulario_detalle", pk=formulario.pk)
    if formulario.validado_renaper and formulario.ciudadano.genero:
        messages.info(request, "La identidad ya fue validada; el sexo es de solo lectura.")
        return redirect("becas:formulario_detalle", pk=formulario.pk)

    form = CiudadanoGeneroRevisionForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Seleccioná un sexo válido.")
        return redirect("becas:formulario_detalle", pk=formulario.pk)

    ciudadano = formulario.ciudadano
    genero_anterior = ciudadano.genero
    genero_nuevo = form.cleaned_data["genero"]
    if genero_anterior == genero_nuevo:
        messages.info(request, "El sexo no cambió.")
        return redirect("becas:formulario_detalle", pk=formulario.pk)

    etiquetas = dict(ciudadano.Genero.choices)
    ciudadano.genero = genero_nuevo
    ciudadano.save(update_fields=["genero", "modificado"])
    registrar_traza(
        formulario,
        request.user,
        [("Ciudadano · sexo", etiquetas.get(genero_anterior, "Sin informar"), etiquetas[genero_nuevo])],
    )
    if formulario.validado_renaper:
        messages.success(request, "Sexo guardado.")
    else:
        messages.success(request, "Sexo guardado. Ya podés revalidar con Base de Personas.")
    return redirect("becas:formulario_detalle", pk=formulario.pk)


@login_required
@requiere(CAP_REVISION_EDITAR)
def formulario_aprobar(request, pk):
    formulario = get_object_or_404(Formulario.objects.select_related("relevamiento__convocatoria__segmento"), pk=pk)
    _assert_scope_formulario(request, formulario)
    if request.method == "POST":
        if _tiene_conflicto_duplicado_pendiente(formulario):
            messages.error(request, "Primero debés resolver el conflicto de cargas duplicadas.")
            return redirect("becas:formulario_detalle", pk=formulario.pk)
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
def formulario_resolver_duplicado(request, pk):
    formulario = get_object_or_404(Formulario, pk=pk, conflicto_duplicado=True)
    _assert_scope_formulario(request, formulario)
    if request.method != "POST" or formulario.conflicto_resuelto:
        return redirect("becas:formulario_detalle", pk=formulario.pk)

    decision = request.POST.get("decision")
    with transaction.atomic():
        formulario = Formulario.objects.select_for_update().get(pk=formulario.pk)
        previo = Formulario.objects.select_for_update().filter(pk=formulario.duplicado_de_id).first()
        if previo is None:
            messages.error(request, "No se encontró la carga anterior vinculada.")
            return redirect("becas:formulario_detalle", pk=formulario.pk)

        if decision == "conservar_previo":
            estado_anterior = formulario.estado
            formulario.estado = Formulario.Estado.RECHAZADO
            formulario.motivo_rechazo = f"Carga duplicada del Formulario {previo.numero}."
            formulario.conflicto_resuelto = True
            formulario.save(update_fields=["estado", "motivo_rechazo", "conflicto_resuelto", "modificado"])
            registrar_traza(
                formulario,
                request.user,
                [("Conflicto DNI", estado_anterior, f"Se conservó el Formulario {previo.numero}")],
            )
            messages.success(request, f"Se conservó el Formulario {previo.numero} y se descartó esta carga duplicada.")
        elif decision == "conservar_actual":
            if previo.estado != Formulario.Estado.ENVIADO:
                messages.error(request, "La carga anterior ya fue procesada y no puede reemplazarse desde aquí.")
                return redirect("becas:formulario_detalle", pk=formulario.pk)
            previo.estado = Formulario.Estado.RECHAZADO
            previo.motivo_rechazo = f"Reemplazado por la carga duplicada del Formulario {formulario.numero}."
            previo.save(update_fields=["estado", "motivo_rechazo", "modificado"])
            formulario.conflicto_resuelto = True
            formulario.save(update_fields=["conflicto_resuelto", "modificado"])
            registrar_traza(
                previo,
                request.user,
                [("Conflicto DNI", "ENVIADO", f"Reemplazado por el Formulario {formulario.numero}")],
            )
            registrar_traza(formulario, request.user, [("Conflicto DNI", "PENDIENTE", "Carga conservada")])
            messages.success(request, f"Se conservó esta carga y se descartó el Formulario {previo.numero}.")
        else:
            messages.error(request, "Seleccioná qué carga querés conservar.")
    return redirect("becas:formulario_detalle", pk=formulario.pk)


@login_required
@requiere(CAP_REVISION_EDITAR)
def formulario_rechazar(request, pk):
    formulario = get_object_or_404(Formulario.objects.select_related("relevamiento__convocatoria__segmento"), pk=pk)
    _assert_scope_formulario(request, formulario)
    if request.method == "POST":
        if _tiene_conflicto_duplicado_pendiente(formulario):
            messages.error(request, "Primero debés resolver el conflicto de cargas duplicadas.")
            return redirect("becas:formulario_detalle", pk=formulario.pk)
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
    if ciudadano.genero not in ("F", "M"):
        messages.error(request, "Completá el sexo F o M antes de consultar Base de Personas.")
        return redirect("becas:formulario_detalle", pk=formulario.pk)
    resultado = consultar_persona(ciudadano.dni, ciudadano.genero)
    if not resultado.get("success"):
        mensaje = resultado.get("error") or "Base de Personas no pudo validar a la persona."
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
            cambios.append(("Base de Personas", "Pendiente", "Validado"))
        registrar_traza(formulario, request.user, cambios)

    messages.success(request, "Identidad revalidada correctamente con Base de Personas.")
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
