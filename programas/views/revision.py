"""Backoffice — Revisión de casos de Becas (#77).

Un «caso» es la persona que completó un relevamiento, por link público o por
territorial; en el modelo es ``Formulario`` (vocabulario del PM, 27/08/2026).

Acceso granular: ``becas.revision.ver`` para listar/consultar, ``becas.revision.editar``
para iniciar revisión, editar contacto, aprobar/rechazar y terminar. Con alcance
por segmento. La validación SIIS conserva y presenta el detalle auditable de ECOM.
"""

from datetime import datetime, time, timedelta
from pathlib import Path
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.generic import ListView

from core.rbac import CapacidadRequeridaMixin, puede, puede_alguna, requiere
from programas.forms import CiudadanoGeneroRevisionForm, FormularioRevisionForm, ForzarIdentidadForm
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
from programas.services.avisos_resolucion import enviar_aviso_resolucion
from programas.services.becas import registrar_traza, resolver_ciudadano_offline
from programas.services.cupo import aprobar_o_poner_en_espera, motivo_bloqueo_aprobacion
from programas.services.identidad import gran_base_activa
from programas.services.padron import fila_padron, padron_de
from programas.services.personas import consultar_persona
from programas.services.respuestas import respuestas_legibles, sincronizar_desde_legacy
from programas.services.validacion_siis import validar_formulario_en_siis
from programas.views.relevamientos import CAP_RELEVAMIENTO_PUBLICO

CAP_REVISION_VER = "becas.revision.ver"
CAP_REVISION_EDITAR = "becas.revision.editar"
CAP_REVALIDAR_RENAPER = "becas.programa.administrar"
#: Casos por página en la revisión de un relevamiento.
CASOS_POR_PAGINA = 50
EXTENSIONES_IMAGEN = {".avif", ".gif", ".jpeg", ".jpg", ".png", ".webp"}


def _aware_start(fecha):
    return timezone.make_aware(datetime.combine(fecha, time.min), timezone.get_current_timezone())


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


def _marcar_carga_duplicada_pendiente(formularios):
    """Deja ``tiene_carga_duplicada_pendiente`` en cada caso de la página.

    Antes se anotaba con ``Exists(duplicado_de_id=OuterRef("pk"))``. ``duplicado_de_id``
    es casi siempre NULL, así que MySQL le asigna cardinalidad 1, descarta el índice y
    resuelve la subconsulta dependiente con un scan completo de la tabla **por cada
    fila**. Medido contra 40.000 casos: 3,3 s para una página de 50 y 182 s para un
    relevamiento entero, muy por encima del ``read_timeout`` de 10 s de producción.
    Resuelto por lote sobre los ids de la página, es una consulta indexada de pocos ms.
    """
    formularios = list(formularios)
    ids = [f.pk for f in formularios]
    con_conflicto = (
        set(
            Formulario.objects.filter(duplicado_de_id__in=ids, conflicto_resuelto=False).values_list(
                "duplicado_de_id", flat=True
            )
        )
        if ids
        else set()
    )
    for formulario in formularios:
        formulario.tiene_carga_duplicada_pendiente = formulario.pk in con_conflicto
    return formularios


def _pagina_hidratada(pks, orden, duplicados=True):
    """Trae los datos de presentación **solo** de los casos de la página.

    La página se elige con una consulta liviana (ver ``RevisionPersonasListView``) y
    recién acá se pagan los ``select_related``. La columna ``data`` no la usa ninguna
    de las tres plantillas de revisión, así que se difiere.
    """
    filas = (
        Formulario.objects.filter(pk__in=pks)
        .select_related("ciudadano", "relevamiento__convocatoria__segmento", "relevamiento__territorial")
        .defer("data")
        .order_by(*orden)
    )
    return _marcar_carga_duplicada_pendiente(filas) if duplicados else list(filas)


def _assert_scope_relevamiento(request, relevamiento):
    # RN-P13: sin la capacidad, un relevamiento público no existe para el usuario
    # (tampoco para mutarlo por URL).
    if relevamiento.es_publico and not puede(request.user, CAP_RELEVAMIENTO_PUBLICO):
        raise PermissionDenied("No tiene acceso a este relevamiento.")
    if (
        not puede_gestionar_segmento(request.user, relevamiento.segmento)
        or not convocatorias_visibles(request.user).filter(pk=relevamiento.convocatoria_id).exists()
    ):
        raise PermissionDenied("No tiene acceso a este relevamiento.")


def _assert_scope_formulario(request, formulario):
    if formulario.relevamiento.es_publico and not puede(request.user, CAP_RELEVAMIENTO_PUBLICO):
        raise PermissionDenied("No tiene acceso a este formulario.")
    if (
        not puede_gestionar_segmento(request.user, formulario.relevamiento.segmento)
        or not convocatorias_visibles(request.user).filter(pk=formulario.relevamiento.convocatoria_id).exists()
    ):
        raise PermissionDenied("No tiene acceso a este formulario.")


def _sin_formularios_publicos_si_no_puede(qs, user):
    if puede(user, CAP_RELEVAMIENTO_PUBLICO):
        return qs
    return qs.exclude(relevamiento__tipo=Relevamiento.Tipo.PUBLICO)


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

    #: Orden de la bandeja. El desempate por pk la vuelve estable entre páginas y
    #: permite rehidratar la página en el mismo orden.
    orden = ("-creado", "-pk")

    def get_queryset(self):
        # Consulta liviana: sin joins de presentación. Con los ``select_related`` acá,
        # MySQL arranca el plan por ``programas_relevamiento``, materializa las 40.000
        # filas y recién después recorta (3,7 s medidos). Sin ellos recorre el índice
        # de ``creado`` hacia atrás y corta en la página.
        convocatorias = list(convocatorias_visibles(self.request.user).values_list("pk", flat=True))
        # Solo el pk: la fila entera se lee una vez, en la hidratación. Proyectando todas
        # las columnas MySQL recorre la tabla y ordena (``type=ALL`` + filesort); pidiendo
        # solo el pk el índice cubre la consulta y la página profunda baja de 255 a 42 ms.
        # Sigue siendo O(offset): si el padrón llega a cientos de miles, lo que hace falta
        # es paginar por keyset (creado, pk) < el último visto, no un OFFSET más barato.
        qs = Formulario.objects.filter(relevamiento__convocatoria_id__in=convocatorias).only("pk").order_by(*self.orden)
        qs = _sin_formularios_publicos_si_no_puede(qs, self.request.user)
        estado = self.request.GET.get("estado")
        if estado:
            qs = qs.filter(estado=estado)
        return qs

    def paginate_queryset(self, queryset, page_size):
        paginator, page, object_list, is_paginated = super().paginate_queryset(queryset, page_size)
        return paginator, page, _pagina_hidratada([f.pk for f in object_list], self.orden), is_paginated

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["estados"] = Formulario.Estado.choices
        ctx["estado_actual"] = self.request.GET.get("estado", "")
        ctx["puede_revalidar_renaper"] = puede(self.request.user, CAP_REVALIDAR_RENAPER)
        # El contador vive dentro del mismo ``{% if %}`` de la plantilla: para quien no
        # administra el programa, contarlo es un COUNT de toda la tabla al pedo.
        if ctx["puede_revalidar_renaper"]:
            ctx["pendientes_renaper"] = _sin_formularios_publicos_si_no_puede(
                Formulario.objects.filter(validado_renaper=False),
                self.request.user,
            ).count()
        return ctx


class RenaperPendientesListView(CapacidadRequeridaMixin, LoginRequiredMixin, ListView):
    capacidades_requeridas = CAP_REVALIDAR_RENAPER
    template_name = "programas/becas/revision/renaper_pendientes.html"
    context_object_name = "formularios"
    paginate_by = 50
    orden = ("-creado", "-pk")

    def get_queryset(self):
        # Igual que la bandeja de personas: la página se elige sin joins de
        # presentación y se hidrata después (ver ``_pagina_hidratada``).
        queryset = Formulario.objects.filter(validado_renaper=False).only("pk")
        queryset = _sin_formularios_publicos_si_no_puede(queryset, self.request.user)
        if self.request.GET.get("fecha"):
            fecha = parse_date(self.request.GET["fecha"])
            if fecha:
                queryset = queryset.filter(
                    creado__gte=_aware_start(fecha),
                    creado__lt=_aware_start(fecha + timedelta(days=1)),
                )
        # Los filtros llegan por GET: solo se aplican si son ids válidos.
        territorial = self.request.GET.get("territorial", "")
        if territorial.isdigit():
            queryset = queryset.filter(relevamiento__territorial_id=int(territorial))
        segmento = self.request.GET.get("segmento", "")
        if segmento.isdigit():
            queryset = queryset.filter(relevamiento__convocatoria__segmento_id=int(segmento))
        return queryset.order_by(*self.orden)

    def paginate_queryset(self, queryset, page_size):
        paginator, page, object_list, is_paginated = super().paginate_queryset(queryset, page_size)
        return (
            paginator,
            page,
            _pagina_hidratada([f.pk for f in object_list], self.orden, duplicados=False),
            is_paginated,
        )

    @staticmethod
    def territoriales_pendientes(base):
        """Opciones del filtro. Los formularios públicos no tienen territorial:
        quedan fuera del selector (antes generaban una opción `None`)."""
        return (
            base.exclude(relevamiento__territorial__isnull=True)
            .values("relevamiento__territorial_id", "relevamiento__territorial__username")
            .distinct()
            .order_by("relevamiento__territorial__username")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        base = Formulario.objects.filter(validado_renaper=False)
        base = _sin_formularios_publicos_si_no_puede(base, self.request.user)
        context["territoriales"] = self.territoriales_pendientes(base)
        # Por relevamiento, no por formulario: filtrar por ``formularios__in=base`` compila
        # a un self-join de programas_formulario consigo misma para leer una columna que el
        # relevamiento ya determina (35 ms -> 6 ms). El conjunto es identico.
        context["segmentos"] = (
            Segmento.objects.filter(convocatorias__relevamientos__in=base.values("relevamiento_id"))
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

    # Por el manager del modelo, no por ``relevamiento.formularios``: el manager
    # relacionado empareja cada fila con el relevamiento leyendo ``relevamiento_id``, que
    # ``only("pk")`` difiere, y eso dispara una consulta por fila.
    formularios = Formulario.objects.filter(relevamiento=relevamiento).order_by("numero")
    estado = request.GET.get("estado")
    if estado:
        formularios = formularios.filter(estado=estado)

    # Sin paginar, un relevamiento de 3.300 casos rendía una sola página con todas las
    # filas y su JSON de respuestas. Se pagina como el resto de las bandejas.
    paginador = Paginator(formularios.only("pk"), CASOS_POR_PAGINA)
    pagina = paginador.get_page(request.GET.get("page"))

    return render(
        request,
        "programas/becas/revision/formulario_list.html",
        {
            "relevamiento": relevamiento,
            "formularios": _pagina_hidratada([f.pk for f in pagina], ("numero",)),
            "page_obj": pagina,
            "paginator": paginador,
            "is_paginated": pagina.has_other_pages(),
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

    pregunta_ids = [int(k) for k in globales.keys() if str(k).isdigit()]
    preguntas = {str(p.pk): p for p in PreguntaGlobal.objects.filter(pk__in=pregunta_ids)}
    req_ids = [int(k) for k in requisitos.keys() if str(k).isdigit()]
    requisitos_map = {str(r.pk): r for r in RequisitoNativo.objects.filter(pk__in=req_ids)}

    # Una sola lectura de adjuntos: eran dos consultas sobre la misma tabla y el mismo caso.
    adjuntos = list(formulario.adjuntos.all())
    adjuntos_pregunta = {a.pregunta_global_id: a for a in adjuntos if a.pregunta_global_id}
    adjuntos_requisito = {a.requisito_nativo_id: a for a in adjuntos if a.requisito_nativo_id}

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


def _sin_vinculados(bloques):
    """Los campos vinculados al legajo y al apoderado ya tienen su sección en
    el detalle (identidad, contacto, apoderado): en «Respuestas» quedan solo
    las preguntas y los textos. Un grupo que se queda sin nada no se muestra."""
    if bloques is None:
        return None
    filtrados = []
    for bloque in bloques:
        items = [
            i for i in bloque["items"] if i.get("tipo") != "campo" or not i.get("origen") or i["origen"] == "pregunta"
        ]
        if items:
            filtrados.append({**bloque, "items": items})
    return filtrados


@login_required
@requiere(CAP_REVISION_VER, CAP_REVISION_EDITAR)
def formulario_detalle(request, pk):
    formulario = get_object_or_404(
        # ``programa`` lo lee ``motivo_bloqueo_aprobacion``; sin el va una consulta suelta.
        Formulario.objects.select_related("relevamiento__convocatoria__segmento__programa", "ciudadano"),
        pk=pk,
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
            sincronizar_desde_legacy(formulario)  # las respuestas por clave siguen a las columnas
            resolver_ciudadano_offline(formulario)
            n = registrar_traza(formulario, request.user, cambios)
            if n:
                messages.success(request, f"Caso actualizado ({n} cambio(s) registrado(s)).")
            else:
                messages.info(request, "No hubo cambios para guardar.")
            return redirect("becas:formulario_detalle", pk=formulario.pk)
    else:
        form = FormularioRevisionForm(instance=formulario)

    # Cambio 58 (#347): un caso con foto se lee desde la foto; uno anterior, por pk.
    bloques = _sin_vinculados(respuestas_legibles(formulario))
    if bloques is None:
        globales_list, requisitos_segmento, requisitos_subsegmento = _respuestas_resueltas(formulario)
    else:
        globales_list, requisitos_segmento, requisitos_subsegmento = [], [], []
    # Cambio 67: el apoderado se pide a toda persona que se inscribe, así que la
    # sección editable se muestra siempre (también en los casos anteriores, que se
    # pueden completar desde acá). Reemplaza la regla por condición de la foto del
    # Cambio 58: ya no hay caso en que el apoderado no se pida.
    mostrar_apoderado = True
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
        {"validacion": validacion, "detalle": _detalle_validacion_siis(validacion)} for validacion in validaciones_sis
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
            # Cambio 58 (#347): con foto, un solo listado en el orden del formulario
            # que respondio; sin foto, las tres listas historicas por alcance.
            "bloques": bloques,
            "globales_list": globales_list,
            "requisitos_segmento": requisitos_segmento,
            "requisitos_subsegmento": requisitos_subsegmento,
            "mapa": mapa,
            "trazas": formulario.trazas.select_related("editado_por")[:50],
            "puede_revalidar_renaper": puede(request.user, CAP_REVALIDAR_RENAPER),
            # Cambio 57: con la Gran Base apagada, «Revalidar» se deshabilita y
            # se ofrece validar contra el padrón de la convocatoria.
            "gran_base_activa": gran_base_activa(),
            "convocatoria_tiene_padron": padron_de(formulario.relevamiento).exists(),
            "forzar_identidad_form": ForzarIdentidadForm(),
            "puede_validar_siis": puede(request.user, CAP_REVISION_EDITAR),
            "validacion_sis": validacion_sis,
            "detalle_siis": _detalle_validacion_siis(validacion_sis),
            "historial_validaciones_sis": historial_validaciones_sis,
            "motivo_bloqueo_aprobacion": motivo_bloqueo_aprobacion(formulario, validacion_sis),
            # ``conflicto_pendiente`` ya resolvio esta misma pregunta unas lineas arriba.
            "tiene_conflicto_duplicado_pendiente": conflicto_pendiente is not None,
            "conflicto_pendiente": conflicto_pendiente,
            "formulario_comparacion": formulario_comparacion,
        },
    )


@login_required
@requiere(CAP_REVISION_EDITAR)
def formulario_validar_sis(request, pk):
    formulario = get_object_or_404(
        Formulario.objects.select_related("ciudadano", "relevamiento__convocatoria__segmento__programa"), pk=pk
    )
    _assert_scope_formulario(request, formulario)
    if request.method != "POST":
        return redirect("becas:formulario_detalle", pk=formulario.pk)

    try:
        validacion = validar_formulario_en_siis(formulario, request.user)
    except ValueError as error:
        messages.error(request, str(error))
        return redirect("becas:formulario_detalle", pk=formulario.pk)
    if validacion.estado == ValidacionSIS.Estado.OK:
        messages.success(request, "SIIS informo que la persona es compatible.")
    elif validacion.estado == ValidacionSIS.Estado.RECHAZADO:
        messages.warning(request, f"SIIS rechazo la compatibilidad: {validacion.motivo or 'sin motivo informado'}")
    else:
        messages.error(request, validacion.motivo or "No se pudo validar contra SIIS.")
    return redirect("becas:formulario_detalle", pk=formulario.pk)


@login_required
@requiere(CAP_REVALIDAR_RENAPER)
def formulario_actualizar_genero(request, pk):
    formulario = get_object_or_404(Formulario.objects.select_related("ciudadano"), pk=pk)
    _assert_scope_formulario(request, formulario)
    if request.method != "POST":
        return redirect("becas:formulario_detalle", pk=formulario.pk)
    if formulario.ciudadano is None:
        messages.error(request, "El caso no tiene un ciudadano vinculado.")
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
            validar_formulario_en_siis(formulario, request.user)
            resultado = aprobar_o_poner_en_espera(formulario, request.user)
        except (ValidationError, ValueError) as error:
            messages.error(request, getattr(error, "message", str(error)))
        else:
            if resultado == "aprobado":
                messages.success(request, "Caso aprobado.")
            else:
                segmento = formulario.relevamiento.convocatoria.segmento
                messages.warning(
                    request,
                    f"No hay cupo disponible en {segmento.nombre}: se agregó a la lista de espera.",
                )
            # Aviso al ciudadano (Cambio 44). Va acá y no dentro de
            # ``aprobar_o_poner_en_espera``: el servicio es ``@transaction.atomic``
            # y un rollback dejaría el correo enviado sin forma de retractarlo.
            # ``resultado`` distingue los dos desenlaces de "Aprobar": mandar
            # «fuiste aprobado» le mentiría a quien cayó en lista de espera.
            enviar_aviso_resolucion(
                formulario,
                resultado,
                protocol="https" if request.is_secure() else "http",
                domain=request.get_host(),
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

        # Ninguna de las dos ramas manda el aviso del Cambio 44, y es deliberado:
        # las dos cargas son de la MISMA persona en el mismo relevamiento, asi que
        # el rechazo de una es limpieza de un duplicado, no la resolucion de su
        # inscripcion. La carga que sobrevive queda ENVIADO y cuando se resuelva
        # --aprobada, en espera o rechazada-- ahi si recibe el correo que
        # corresponde. Avisar aca le diria "no fue aprobada" a alguien cuyo tramite
        # sigue abierto.
        if decision == "conservar_previo":
            estado_anterior = formulario.estado
            formulario.estado = Formulario.Estado.RECHAZADO
            formulario.motivo_rechazo = f"Carga duplicada del Formulario {previo.numero}."
            formulario.conflicto_resuelto = True
            formulario.save(update_fields=["estado", "motivo_rechazo", "conflicto_resuelto", "modificado"])
            registrar_traza(
                formulario,
                request.user,
                [("Conflicto DNI", estado_anterior, f"Se conservó el caso {previo.numero}")],
            )
            messages.success(request, f"Se conservó el caso {previo.numero} y se descartó esta carga duplicada.")
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
                [("Conflicto DNI", "ENVIADO", f"Reemplazado por el caso {formulario.numero}")],
            )
            registrar_traza(formulario, request.user, [("Conflicto DNI", "PENDIENTE", "Carga conservada")])
            messages.success(request, f"Se conservó esta carga y se descartó el caso {previo.numero}.")
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
        # Simetria con la aprobacion, que corta en ``aprobar_o_poner_en_espera``.
        # Sin esta guarda un doble clic rechazaba dos veces --y desde el Cambio 44
        # mandaba dos correos-- y un POST armado a mano podia rechazar a un
        # beneficiario ya APROBADO, liberandole el cupo y avisandole que no fue
        # aprobado.
        if formulario.estado != Formulario.Estado.ENVIADO:
            messages.error(request, "Solo se pueden rechazar casos pendientes de resolución.")
            return redirect("becas:formulario_detalle", pk=formulario.pk)
        motivo = (request.POST.get("motivo") or "").strip()
        if not motivo:
            messages.error(request, "Debés indicar el motivo del rechazo.")
            return redirect("becas:formulario_detalle", pk=formulario.pk)
        try:
            validacion = validar_formulario_en_siis(formulario, request.user)
        except ValueError as error:
            messages.error(request, str(error))
            return redirect("becas:formulario_detalle", pk=formulario.pk)
        estado_anterior = formulario.estado
        formulario.estado = Formulario.Estado.RECHAZADO
        formulario.motivo_rechazo = motivo
        formulario.save(update_fields=["estado", "motivo_rechazo", "modificado"])
        registrar_traza(formulario, request.user, [("estado", estado_anterior, f"RECHAZADO: {motivo}")])
        # Aviso al ciudadano (Cambio 44), con el motivo textual tal como lo
        # escribió el técnico (decisión del cliente). Si el correo falla, el
        # rechazo ya quedó firme: el servicio loguea y devuelve False.
        enviar_aviso_resolucion(
            formulario,
            "rechazado",
            motivo=motivo,
            protocol="https" if request.is_secure() else "http",
            domain=request.get_host(),
        )
        if validacion.estado == ValidacionSIS.Estado.ERROR:
            messages.warning(request, "SIIS no respondió correctamente; quedó registrado para reintentar.")
        messages.success(request, "Caso rechazado.")
    return redirect("becas:formulario_detalle", pk=formulario.pk)


@login_required
@requiere(CAP_REVALIDAR_RENAPER)
def formulario_revalidar_renaper(request, pk):
    formulario = get_object_or_404(Formulario.objects.select_related("ciudadano"), pk=pk)
    _assert_scope_formulario(request, formulario)
    if request.method != "POST":
        return redirect("becas:formulario_detalle", pk=formulario.pk)
    if not gran_base_activa():
        # Cambio 57: apagada por configuración mientras el servicio no responde.
        messages.error(
            request,
            "Base de Personas está desactivada por configuración. Usá «Validar contra el padrón» "
            "o la validación manual.",
        )
        return redirect("becas:formulario_detalle", pk=formulario.pk)
    ciudadano = formulario.ciudadano
    if ciudadano is None:
        messages.error(request, "El caso no tiene un ciudadano vinculado para revalidar.")
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
        if not formulario.validado_renaper or formulario.origen_validacion != Formulario.OrigenValidacion.PERSONAS:
            anterior = formulario.get_origen_validacion_display() if formulario.validado_renaper else "Pendiente"
            formulario.validado_renaper = True
            # La Gran Base es la fuente oficial: manda sobre el padrón (RN-6).
            formulario.origen_validacion = Formulario.OrigenValidacion.PERSONAS
            formulario.save(update_fields=["validado_renaper", "origen_validacion", "modificado"])
            cambios.append(("Base de Personas", anterior, "Validado"))
        registrar_traza(formulario, request.user, cambios)

    messages.success(request, "Identidad revalidada correctamente con Base de Personas.")
    return redirect("becas:formulario_detalle", pk=formulario.pk)


@login_required
@requiere(CAP_REVALIDAR_RENAPER)
def formulario_validar_padron(request, pk):
    """Valida la identidad de un caso pendiente contra el padrón de su
    convocatoria (Cambio 57). Es lo mismo que hace el cruce automático al
    subir el padrón, para un caso puntual: sirve cuando el padrón se corrigió
    después, o cuando la Gran Base está apagada y el caso entró como manual."""
    formulario = get_object_or_404(Formulario.objects.select_related("ciudadano", "relevamiento__convocatoria"), pk=pk)
    _assert_scope_formulario(request, formulario)
    if request.method != "POST":
        return redirect("becas:formulario_detalle", pk=formulario.pk)
    if formulario.validado_renaper:
        messages.error(request, "La identidad de este caso ya está validada.")
        return redirect("becas:formulario_detalle", pk=formulario.pk)
    ciudadano = formulario.ciudadano
    if ciudadano is None or not ciudadano.dni:
        messages.error(request, "El caso necesita un ciudadano con DNI para buscarlo en el padrón.")
        return redirect("becas:formulario_detalle", pk=formulario.pk)
    fila = fila_padron(formulario.relevamiento, ciudadano.dni, ciudadano.genero)
    if fila is None:
        messages.error(request, f"El DNI {ciudadano.dni} no figura en el padrón de la convocatoria con ese sexo.")
        return redirect("becas:formulario_detalle", pk=formulario.pk)
    if not fila.tiene_identidad:
        messages.error(
            request,
            "La persona figura en el padrón pero sin nombre y apellido: subí un padrón con esos datos o validá a mano.",
        )
        return redirect("becas:formulario_detalle", pk=formulario.pk)

    with transaction.atomic():
        cambios = [("Validación de identidad", "Pendiente", "Validada por padrón")]
        actualizados = []
        for campo, valor in (
            ("nombre", fila.nombre),
            ("apellido", fila.apellido),
            ("fecha_nacimiento", fila.fecha_nacimiento),
            ("localidad", fila.localidad),
        ):
            if valor and not getattr(ciudadano, campo):
                setattr(ciudadano, campo, valor)
                actualizados.append(campo)
                cambios.append((f"Ciudadano · {campo}", "", str(valor)))
        if actualizados:
            ciudadano.save(update_fields=[*actualizados, "modificado"])
        formulario.validado_renaper = True
        formulario.origen_validacion = Formulario.OrigenValidacion.PADRON
        formulario.save(update_fields=["validado_renaper", "origen_validacion", "modificado"])
        registrar_traza(formulario, request.user, cambios)
    messages.success(request, "Identidad validada contra el padrón de la convocatoria.")
    return redirect("becas:formulario_detalle", pk=formulario.pk)


@login_required
@requiere(CAP_REVALIDAR_RENAPER)
def formulario_forzar_identidad(request, pk):
    """Marca la identidad como validada a mano, con motivo y traza.

    Base de Personas no siempre puede validar a alguien que existe: el DNI no
    figura en la fuente, la fuente no responde, o la persona quedó fuera del
    padrón que expone. Como ``motivo_bloqueo_aprobacion`` exige identidad
    validada, sin esta salida el caso no se puede resolver nunca.

    No inventa datos: no toca nombre, apellido, fecha de nacimiento ni sexo
    —eso sigue siendo lo que cargó el territorial o la persona— y deja marcado
    que la validación fue manual, para que el dato no se lea como si lo hubiera
    devuelto la fuente.
    """
    formulario = get_object_or_404(Formulario.objects.select_related("ciudadano"), pk=pk)
    _assert_scope_formulario(request, formulario)
    if request.method != "POST":
        return redirect("becas:formulario_detalle", pk=formulario.pk)
    if formulario.validado_renaper:
        messages.error(request, "La identidad de este caso ya está validada.")
        return redirect("becas:formulario_detalle", pk=formulario.pk)
    if formulario.ciudadano_id is None or not formulario.ciudadano.dni:
        messages.error(request, "El caso necesita un ciudadano con DNI antes de validar la identidad.")
        return redirect("becas:formulario_detalle", pk=formulario.pk)

    form = ForzarIdentidadForm(request.POST)
    if not form.is_valid():
        messages.error(request, next(iter(form.errors.values()))[0])
        return redirect("becas:formulario_detalle", pk=formulario.pk)

    motivo = form.cleaned_data["motivo"]
    with transaction.atomic():
        formulario.validado_renaper = True
        formulario.identidad_forzada = True
        formulario.identidad_forzada_motivo = motivo
        formulario.origen_validacion = Formulario.OrigenValidacion.FORZADA
        formulario.save(
            update_fields=[
                "validado_renaper",
                "identidad_forzada",
                "identidad_forzada_motivo",
                "origen_validacion",
                "modificado",
            ]
        )
        registrar_traza(
            formulario,
            request.user,
            [("Validación de identidad", "Pendiente", f"Validada manualmente — {motivo}")],
        )
    messages.warning(
        request,
        "Identidad validada manualmente. Queda registrado en la traza junto con el motivo.",
    )
    return redirect("becas:formulario_detalle", pk=formulario.pk)


# Estados desde los que se puede cerrar la revisión: el campo ya está cerrado,
# sea porque alguien finalizó el relevamiento o porque se venció la fecha. A
# EN_REVISION solo se llega por fecha (decisión del PM, 27/08/2026): no hay
# forma manual de marcar un relevamiento «en revisión», así que terminar
# también tiene que poder hacerse desde FINALIZADO o el cierre quedaría
# esperando el vencimiento.
ESTADOS_TERMINABLES = (Relevamiento.Estado.FINALIZADO, Relevamiento.Estado.EN_REVISION)


@login_required
@requiere(CAP_REVISION_EDITAR)
def relevamiento_terminar(request, pk):
    rel = get_object_or_404(Relevamiento.objects.select_related("convocatoria__segmento"), pk=pk)
    _assert_scope_relevamiento(request, rel)
    if request.method == "POST":
        if rel.estado not in ESTADOS_TERMINABLES:
            messages.error(request, "Solo se puede terminar un relevamiento finalizado o en revisión.")
        else:
            pendientes = rel.formularios.filter(estado=Formulario.Estado.ENVIADO).count()
            if pendientes:
                messages.error(request, f"Quedan {pendientes} caso(s) sin revisar.")
            else:
                rel.estado = Relevamiento.Estado.TERMINADO
                rel.save(update_fields=["estado", "modificado"])
                messages.success(request, "Relevamiento terminado.")
    return redirect("becas:revision_formularios", relevamiento_pk=rel.pk)
