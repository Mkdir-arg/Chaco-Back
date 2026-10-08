"""Backoffice — Gestión de cupo y lista de espera por segmento (issue #78, RN-04/05).

Acceso de lectura: ``becas.cupo.ver`` o ``becas.beneficiario.ver`` (Admin del
programa, o Coordinador con asignación activa en el segmento). Acciones de
mutación (baja, promoción, agregar a lista de espera): ``becas.beneficiario.editar``.

El alcance **no es el segmento**: es el conjunto de convocatorias visibles (SEC-21,
auditoría oct-2026). El Coordinador Regional entra al segmento que contiene su
subsegmento, así que el segmento solo le mostraba —y le dejaba mutar— los casos de
sus pares. Los casos del link público quedan afuera sin RN-P13 (SEC-22).
"""

import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic.detail import DetailView

from core.rbac import CapacidadRequeridaMixin, puede_alguna
from programas.models import Formulario, ListaEspera, Segmento
from programas.services.autorizacion import (
    SegmentoScopedMixin,
    assert_alcance_formulario,
    convocatorias_visibles,
    es_admin_becas,
    programa_becas,
    sin_formularios_publicos_si_no_puede,
)
from programas.services.avisos_resolucion import enviar_aviso_resolucion
from programas.services.cupo import (
    agregar_a_lista_espera,
    dar_baja_beneficiario,
    get_cupo_stats,
    promover_lista_espera,
)
from programas.services.siis_envio import Catalogos, enviar_beneficiario_a_siis, mensaje_envio

logger = logging.getLogger(__name__)

CAP_CUPO_VER = "becas.cupo.ver"
CAP_BENEFICIARIO_VER = "becas.beneficiario.ver"
CAP_BENEFICIARIO_EDITAR = "becas.beneficiario.editar"
CUPO_PAGE_SIZE = 50


def _informar_a_siis(request, formulario):
    """Alta del beneficiario en SIIS tras la promoción (mismo helper que en
    ``views/revision.py``: son diez líneas y evita un import cruzado entre vistas).
    Nunca deshace la promoción: un fallo se registra y se reintenta desde el caso."""
    try:
        # SIIS-09: dentro de un request los catálogos salen de la copia local,
        # nunca de la red. Ver ``Catalogos.sin_red``.
        envio = enviar_beneficiario_a_siis(formulario, request.user, catalogos=Catalogos.sin_red())
    except ValueError as error:
        # SIIS-04: el estado releído bajo lock ya no habilita el envío.
        messages.warning(request, str(error))
        return None
    except Exception:  # noqa: BLE001 — la promoción ya está confirmada
        logger.exception("Fallo inesperado al informar el beneficiario %s a SIIS", formulario.pk)
        messages.error(request, "No se pudo informar el beneficiario a SIIS; reintentá desde el caso.")
        return None
    nivel, texto = mensaje_envio(envio)
    getattr(messages, nivel)(request, texto)
    return envio


def _paginate(request, queryset, page_param):
    paginator = Paginator(queryset, CUPO_PAGE_SIZE)
    return paginator.get_page(request.GET.get(page_param))


def _querystring_without(request, *keys):
    params = request.GET.copy()
    for key in keys:
        params.pop(key, None)
    return params.urlencode()


class CupoSegmentoDetailView(SegmentoScopedMixin, CapacidadRequeridaMixin, LoginRequiredMixin, DetailView):
    """Vista principal de cupo: stat cards + Beneficiarios / Lista de espera / Pendientes."""

    model = Segmento
    capacidades_requeridas = [CAP_CUPO_VER, CAP_BENEFICIARIO_VER]
    template_name = "programas/becas/cupo/segmento_detail.html"

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        self.assert_puede_gestionar_segmento(obj)
        return obj

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        segmento = self.object

        stats = get_cupo_stats(segmento)

        # La pantalla lista nombre, DNI, convocatoria y fechas: los dos JSON del
        # formulario no los toca ninguna de las tres tablas (medido: 226 ms -> 92 ms).
        sin_json = ("data", "datos_identificacion")

        # SEC-21: el segmento solo no alcanza como alcance. El Coordinador Regional
        # entra al segmento que contiene su subsegmento, así que filtrando solo por
        # ``relevamiento__convocatoria__segmento`` veía —con nombre y DNI— a los
        # beneficiarios, la espera y los pendientes de los subsegmentos de sus pares.
        # SEC-22: y los casos del link público, sin tener RN-P13.
        usuario = self.request.user
        programa = programa_becas(usuario)
        # Para el admin del programa (y el superusuario, que pasa por el mismo bypass)
        # `convocatorias_visibles` es *todas* las convocatorias: filtrar por ellas no
        # recorta nada y mete un `IN` con la tabla entera en las tres consultas de una
        # pantalla que ya costó un 500 por `read_timeout` en ECOM. Así que ve todo sin
        # filtro. Para el resto el recorte sí acota, y va como ids planos y no como
        # subconsulta, que es el mismo `IN` anidado tres veces.
        convocatorias = (
            None
            if es_admin_becas(usuario, programa=programa)
            else list(convocatorias_visibles(usuario, programa=programa).values_list("pk", flat=True))
        )

        def _de_mi_alcance(qs, prefijo=""):
            if convocatorias is not None:
                qs = qs.filter(**{f"{prefijo}relevamiento__convocatoria_id__in": convocatorias})
            return sin_formularios_publicos_si_no_puede(qs, usuario, programa=programa, prefijo=prefijo)

        beneficiarios_qs = (
            _de_mi_alcance(
                Formulario.objects.filter(
                    estado=Formulario.Estado.APROBADO,
                    ciudadano__isnull=False,
                    relevamiento__convocatoria__segmento=segmento,
                )
            )
            .select_related("ciudadano", "relevamiento__convocatoria")
            .defer(*sin_json)
            .order_by("modificado")
        )

        lista_espera_qs = (
            _de_mi_alcance(ListaEspera.objects.filter(segmento=segmento, promovido=False), prefijo="formulario__")
            .select_related("formulario__ciudadano", "formulario__relevamiento__convocatoria")
            .defer(*[f"formulario__{campo}" for campo in sin_json])
            .order_by("posicion")
        )

        # Formularios ENVIADOS del segmento que aún no están en lista de espera. El
        # "ya está en espera" se mira sobre todo el segmento a propósito: un caso que
        # otro coordinador puso en la lista no tiene que reaparecer acá como pendiente.
        formularios_en_espera_ids = ListaEspera.objects.filter(segmento=segmento, promovido=False).values_list(
            "formulario_id", flat=True
        )
        pendientes_qs = (
            _de_mi_alcance(
                Formulario.objects.filter(
                    estado=Formulario.Estado.ENVIADO,
                    ciudadano__isnull=False,
                    relevamiento__convocatoria__segmento=segmento,
                )
            )
            .exclude(pk__in=formularios_en_espera_ids)
            .select_related("ciudadano", "relevamiento__convocatoria")
            .defer(*sin_json)
            .order_by("creado")
        )

        beneficiarios = _paginate(self.request, beneficiarios_qs, "beneficiarios_page")
        lista_espera = _paginate(self.request, lista_espera_qs, "lista_espera_page")
        pendientes = _paginate(self.request, pendientes_qs, "pendientes_page")

        ctx.update(
            {
                "stats": stats,
                "beneficiarios": beneficiarios,
                "lista_espera": lista_espera,
                "pendientes": pendientes,
                # El total lo trae el paginador: contarlo aparte repetía el mismo COUNT.
                "n_beneficiarios": beneficiarios.paginator.count,
                "n_lista_espera": lista_espera.paginator.count,
                "n_pendientes": pendientes.paginator.count,
                "beneficiarios_querystring": _querystring_without(self.request, "beneficiarios_page", "tab"),
                "lista_espera_querystring": _querystring_without(self.request, "lista_espera_page", "tab"),
                "pendientes_querystring": _querystring_without(self.request, "pendientes_page", "tab"),
                "puede_editar_beneficiarios": puede_alguna(usuario, [CAP_BENEFICIARIO_EDITAR], programa=programa),
            }
        )
        return ctx


@login_required
def dar_baja_beneficiario_view(request, pk):
    formulario = get_object_or_404(
        Formulario.objects.select_related("relevamiento__convocatoria__segmento"),
        pk=pk,
    )
    segmento = formulario.relevamiento.convocatoria.segmento
    # SEC-21: el mismo alcance que el listado, también para mutar por URL directa
    # (Cambio 18). ``puede_gestionar_segmento`` solo miraba el segmento, que para el
    # Coordinador Regional incluye los subsegmentos de sus pares.
    if not puede_alguna(request.user, [CAP_BENEFICIARIO_EDITAR], programa=programa_becas(request.user)):
        raise PermissionDenied
    assert_alcance_formulario(request.user, formulario)
    if request.method == "POST":
        try:
            dar_baja_beneficiario(formulario, request.user)
            messages.warning(
                request,
                f"Se liberó 1 cupo en {segmento.nombre}. ¿Promover desde lista de espera?",
            )
        except ValidationError as e:
            messages.error(request, e.message)
    return redirect(reverse("becas:cupo_segmento", kwargs={"pk": segmento.pk}) + "?tab=beneficiarios")


@login_required
def promover_lista_espera_view(request, pk):
    lista = get_object_or_404(
        # La convocatoria y el segmento del relevamiento los necesita el aviso
        # de resolución (Cambio 44) para el asunto y el cuerpo del correo.
        ListaEspera.objects.select_related(
            "formulario__ciudadano", "formulario__relevamiento__convocatoria__segmento", "segmento"
        ),
        pk=pk,
    )
    if not puede_alguna(request.user, [CAP_BENEFICIARIO_EDITAR], programa=programa_becas(request.user)):
        raise PermissionDenied
    # SEC-21: el alcance es el del caso, no el del segmento de la entrada.
    assert_alcance_formulario(request.user, lista.formulario)
    if request.method == "POST":
        try:
            promover_lista_espera(lista, request.user)
        except ValidationError as e:
            messages.error(request, e.message)
        else:
            # Aviso al ciudadano (Cambio 44): pasar de la lista a beneficiario
            # también es una resolución que le cambia el desenlace. Va afuera de
            # ``promover_lista_espera``, que es ``@transaction.atomic``, y afuera
            # del ``try``, para no confundir una falla del correo con una
            # promoción rechazada.
            _informar_a_siis(request, lista.formulario)
            enviar_aviso_resolucion(
                lista.formulario,
                "promovido",
                usuario=request.user,
                protocol="https" if request.is_secure() else "http",
                domain=request.get_host(),
            )
            nombre = lista.formulario.ciudadano.nombre_completo if lista.formulario.ciudadano else "el ciudadano"
            messages.success(request, f"{nombre} fue promovido como beneficiario.")
    return redirect(reverse("becas:cupo_segmento", kwargs={"pk": lista.segmento.pk}) + "?tab=lista_espera")


@login_required
def agregar_lista_espera_view(request, pk):
    formulario = get_object_or_404(
        Formulario.objects.select_related("relevamiento__convocatoria__segmento"),
        pk=pk,
    )
    segmento = formulario.relevamiento.convocatoria.segmento
    if not puede_alguna(request.user, [CAP_BENEFICIARIO_EDITAR], programa=programa_becas(request.user)):
        raise PermissionDenied
    assert_alcance_formulario(request.user, formulario)
    if request.method == "POST":
        try:
            agregar_a_lista_espera(formulario, segmento, request.user)
        except ValidationError as e:
            messages.error(request, e.message)
        else:
            # Mismo desenlace que aprobar sin cupo, asi que mismo aviso (Cambio 44):
            # para la persona da igual si entro a la lista por el cupo lleno o
            # porque el operador la agrego a mano. Va afuera de
            # ``agregar_a_lista_espera``, que es ``@transaction.atomic``, y afuera
            # del ``try``, para no reportar una falla del correo como un alta
            # rechazada.
            enviar_aviso_resolucion(
                formulario,
                "lista_espera",
                usuario=request.user,
                protocol="https" if request.is_secure() else "http",
                domain=request.get_host(),
            )
            messages.success(request, "Caso agregado a la lista de espera.")
    return redirect(reverse("becas:cupo_segmento", kwargs={"pk": segmento.pk}) + "?tab=lista_espera")
