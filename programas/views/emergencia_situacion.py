"""E8 · «Situación» de Emergencia: el tablero estratégico, no nominal (análisis 009; task #1184).

Solo orquesta: lee una vez la foto (``selectors.emergencia_situacion``), valida los filtros contra
lo que la foto trae, y le pide a ``services.pantalla_situacion_emergencia`` lo que se dibuja. No
calcula nada. La ven ``emergencia.ver_situacion`` o ``emergencia.supervisar`` en el programa; sin
ninguna, 403.

Sin auto-refresh: «Actualizar» vuelve a pedir la pantalla. La solapa **Mapa** (E-6) sale de la misma
foto, sin consultas (``pantalla_situacion_emergencia.bloque_del_mapa``), y no le pide nada a Google
mientras está oculta. La solapa **Abastecimiento** (E-7b) se calcula **solo** con ``?tab=abastecimiento``
(``componentes/tabs.md``): desde otra solapa su panel trae «Calcular el abastecimiento», un enlace
GET a la misma URL con esa solapa, y no suma ninguna consulta.

**Presupuesto de la vista completa: 21 consultas** (RNF-009-03; ``scripts/perf_budgets.json``,
``servicios.emergencia_situacion_vista``) y **26 con la solapa Abastecimiento** (RNF-009-11:
21 + A1-A5; ``servicios.emergencia_situacion_abastecimiento``), medidos en
``programas.tests.test_emergencia_situacion_vista`` y ``programas.tests.test_emergencia_abastecimiento``.
"""

from django.core.paginator import Paginator
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views import View

from programas.forms_emergencia_situacion import SOLAPA_ABASTECIMIENTO, FiltrosSituacionForm
from programas.mixins_emergencia import SituacionPermissionMixin
from programas.selectors import emergencia_situacion as situacion
from programas.selectors.emergencia_abastecimiento import lecturas_de_abastecimiento
from programas.selectors.emergencia_situacion import FiltrosSituacion
from programas.services.abastecimiento_emergencia import armar_abastecimiento
from programas.services.configuracion_emergencia import sla_vigente
from programas.services.dispositivos import dispositivos_visibles
from programas.services.emergencia_programa import puede_operar_la_mesa, puede_supervisar_la_mesa
from programas.services.pantalla_abastecimiento_emergencia import contexto_de_abastecimiento, panel_sin_calcular
from programas.services.pantalla_situacion_emergencia import contexto_del_resumen, pildoras

TEMPLATE = "programas/emergencia/situacion/situacion.html"

#: Desde cuántas filas con demanda se pagina «Presión por localidad», y de a cuántas (§7).
PAGINAR_DESDE = 60
FILAS_POR_PAGINA = 25
PARAMETRO_DE_PAGINA = "localidades_page"


class SituacionView(SituacionPermissionMixin, View):
    def get(self, request):
        form = FiltrosSituacionForm(request.GET)
        sla, ahora = sla_vigente(), timezone.now()
        foto = situacion.foto_de_situacion(sla, ahora, FiltrosSituacion(ventana=form.ventana_elegida))
        filtros = form.filtros(foto.localidades)
        if filtros.activos:
            foto = situacion.con_filtros(foto, filtros)

        supervisa = puede_supervisar_la_mesa(request.user)
        visibles = frozenset(dispositivos_visibles(request.user).values_list("pk", flat=True))
        url_abastecimiento = _url_de_la_solapa(request, SOLAPA_ABASTECIMIENTO)
        contexto = contexto_del_resumen(
            foto, supervisa=supervisa, dispositivos_visibles=visibles, url_abastecimiento=url_abastecimiento
        )

        filas = contexto["presion"]["filas"]
        pagina = None
        if len(filas) > PAGINAR_DESDE:
            pagina = Paginator(filas, FILAS_POR_PAGINA).get_page(request.GET.get(PARAMETRO_DE_PAGINA))

        solapa = form.solapa
        url_limpiar = reverse("emergencia:situacion")
        contexto.update(
            {
                "solapa": solapa,
                "pildoras": pildoras(foto),
                "ocultos": (("tab", solapa),),
                "url_limpiar": url_limpiar,
                "url_accion": request.get_full_path(),
                "accion_texto": "Actualizar",
                "accion_icono": "fa-rotate",
                "actualizado": f"{timezone.localtime(ahora):%H:%M}",
                "impreso": f"{timezone.localtime(ahora):%d/%m/%Y %H:%M}",
                "url_mesa": reverse("emergencia:tablero") if supervisa else "",
                "pagina_localidades": pagina,
                "filas_presion": pagina.object_list if pagina else filas,
                "parametro_de_pagina": PARAMETRO_DE_PAGINA,
                "abastecimiento": _abastecimiento(
                    request, foto, sla, ahora, solapa=solapa, supervisa=supervisa, url_calcular=url_abastecimiento
                ),
            }
        )
        return render(request, TEMPLATE, contexto)


def _url_de_la_solapa(request, solapa):
    """La misma pantalla con sus filtros (que viajan aunque no la acoten) y ``tab=solapa``, sin página."""

    consulta = request.GET.copy()
    consulta["tab"] = solapa
    consulta.pop(PARAMETRO_DE_PAGINA, None)
    return f"{reverse('emergencia:situacion')}?{consulta.urlencode()}"


def _abastecimiento(request, foto, sla, ahora, *, solapa, supervisa, url_calcular):
    """La solapa Abastecimiento: lecturas → reglas → lo que se dibuja, **solo** si se pidió.

    Desde otra solapa o sin ``inicio_evento``, 0 consultas: el panel lo arma
    ``pantalla_abastecimiento_emergencia.panel_sin_calcular``.
    """

    panel = panel_sin_calcular(
        pedido=solapa == SOLAPA_ABASTECIMIENTO,
        inicio_evento=sla.inicio_evento,
        url_calcular=url_calcular,
        supervisa=supervisa,
    )
    if panel is not None:
        return panel
    armado = armar_abastecimiento(lecturas_de_abastecimiento(foto, sla.inicio_evento), foto, ahora)
    return contexto_de_abastecimiento(armado, ahora, opera=puede_operar_la_mesa(request.user), supervisa=supervisa)
