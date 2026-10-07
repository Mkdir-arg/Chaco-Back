"""Ola 5 · PR 6b — FE-17: las paginaciones copiadas a mano de Becas pasan a la pieza.

`templates/components/_paginacion.html` leía y escribía siempre ``?page=``, así que una
pantalla con más de una lista paginada no podía usarla: la golden del arquetipo Detalle
(`becas/cupo/segmento_detail.html`) tenía **tres** pies copiados a mano, y
`relevamientos/convocatoria_detail.html` y `relevamientos/relevamiento_detail.html` uno
cada uno —los dos además sin la caja del pie canónico y sin `aria-label` en las flechas—.

Con ``param`` y ``extra_qs`` (Cambio 167) la pieza cubre el caso, y `ConvocatoriaListView`
—que renderizaba la tabla entera— pasa a paginar, también en el re-render AJAX del modal.
"""

from datetime import date
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from legajos.models import Ciudadano
from programas.models import Convocatoria, Formulario, ListaEspera, Programa, Relevamiento, Segmento

REPO = Path(settings.BASE_DIR)


def sembrar_programa_becas():
    """La autorización de Becas falla cerrado sin la fila ``BECAS`` (RED-56), y
    ``programa_becas()`` la cachea cinco minutos: sin limpiar la caché, el programa que
    sembró otro módulo de la suite se cuela con un pk que acá no existe."""
    cache.clear()
    Programa.objects.get_or_create(codigo="BECAS", defaults={"nombre": "Becas"})


#: Las tres pantallas de Becas que FE-17 nombra como «paginaciones copiadas».
CON_PIE_COPIADO = (
    "programas/templates/programas/becas/cupo/segmento_detail.html",
    "programas/templates/programas/becas/relevamientos/convocatoria_detail.html",
    "programas/templates/programas/becas/relevamientos/relevamiento_detail.html",
)
TABLA_CONVOCATORIAS = "programas/templates/programas/becas/relevamientos/_convocatorias_table.html"


def texto(ruta):
    return (REPO / ruta).read_text(encoding="utf-8")


class SinPieEscritoAManoTests(SimpleTestCase):
    """FE-17: ninguna de las cuatro vuelve a armar el pie con `has_next`/`has_previous`."""

    def test_ninguna_pantalla_arma_el_pie_a_mano(self):
        for ruta in CON_PIE_COPIADO + (TABLA_CONVOCATORIAS,):
            with self.subTest(ruta=ruta):
                contenido = texto(ruta)
                self.assertNotIn(".has_next", contenido)
                self.assertNotIn(".has_previous", contenido)
                self.assertNotIn("previous_page_number", contenido)
                self.assertNotIn("next_page_number", contenido)

    def test_las_cuatro_incluyen_la_pieza(self):
        for ruta in CON_PIE_COPIADO + (TABLA_CONVOCATORIAS,):
            with self.subTest(ruta=ruta):
                self.assertIn('{% include "components/_paginacion.html"', texto(ruta))

    def test_la_golden_pagina_sus_tres_solapas_con_su_propio_parametro(self):
        contenido = texto(CON_PIE_COPIADO[0])

        for param, tab in (
            ("beneficiarios_page", "beneficiarios"),
            ("lista_espera_page", "lista_espera"),
            ("pendientes_page", "pendientes"),
        ):
            with self.subTest(param=param):
                self.assertIn(f'param="{param}"', contenido)
                self.assertIn(f'extra_qs="tab={tab}"', contenido)


class CupoSegmentoPaginaPorSolapaTests(TestCase):
    """La golden: cada solapa pagina sola y el enlace vuelve a la solapa que se miraba."""

    def setUp(self):
        sembrar_programa_becas()
        self.admin = User.objects.create_superuser("admin-pag-6b", password="x")
        self.segmento = Segmento.objects.create(nombre="Seg Paginada", cupo_maximo=10)
        convocatoria = Convocatoria.objects.create(
            nombre="Conv P",
            segmento=self.segmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        self.relevamiento = Relevamiento.objects.create(
            convocatoria=convocatoria,
            territorial=self.admin,
            fecha_asignada=date(2026, 6, 1),
            zona="A",
            estado=Relevamiento.Estado.FINALIZADO,
        )
        for indice in range(2):
            ListaEspera.objects.create(
                segmento=self.segmento,
                formulario=self._formulario(f"7000000{indice}", Formulario.Estado.APROBADO),
                posicion=indice + 1,
            )
        for indice in range(2):
            self._formulario(f"7100000{indice}", Formulario.Estado.ENVIADO)
        self.url = reverse("becas:cupo_segmento", args=[self.segmento.pk])

    def _formulario(self, dni, estado):
        ciudadano = Ciudadano.objects.create(
            dni=dni, nombre=f"N{dni[-1]}", apellido="Paz", fecha_nacimiento=date(1990, 1, 1), genero="F"
        )
        return Formulario.objects.create(
            relevamiento=self.relevamiento,
            ciudadano=ciudadano,
            celular="1",
            email_contacto=f"{dni}@b.com",
            estado=estado,
        )

    def _html(self, query=""):
        self.client.force_login(self.admin)
        with mock.patch("programas.views.cupo.CUPO_PAGE_SIZE", 1):
            respuesta = self.client.get(self.url + query)
        self.assertEqual(respuesta.status_code, 200)
        return respuesta.content.decode()

    def test_el_enlace_de_una_solapa_no_mueve_a_la_otra(self):
        html = self._html()

        self.assertIn("?lista_espera_page=2&amp;tab=lista_espera", html)
        self.assertIn("?pendientes_page=2&amp;tab=pendientes", html)
        self.assertNotIn("?page=2", html)

    def test_estando_en_la_pagina_2_el_parametro_no_se_duplica(self):
        html = self._html("?tab=lista_espera&lista_espera_page=2")

        self.assertIn("?lista_espera_page=1&amp;tab=lista_espera", html)
        # El enlace a la 1 lleva el parámetro una sola vez: con el bug de duplicado
        # («…lista_espera_page=1&…&lista_espera_page=2») el pie no movía de página.
        enlaces = [trozo.split('"')[0] for trozo in html.split('href="?')[1:] if trozo.startswith("lista_espera_page=")]
        self.assertTrue(enlaces)
        for enlace in enlaces:
            self.assertEqual(enlace.count("lista_espera_page="), 1)

    def test_el_pie_es_el_canonico(self):
        html = self._html()

        self.assertIn("px-4 py-3 border-t border-light bg-secondary", html)
        self.assertIn('aria-label="Página siguiente"', html)
        self.assertIn("2 personas en espera", html)


class ConvocatoriasPaginanTests(TestCase):
    """FE-17: `ConvocatoriaListView` renderizaba **todas** las convocatorias visibles."""

    def setUp(self):
        sembrar_programa_becas()
        self.admin = User.objects.create_superuser("admin-conv-6b", password="x")
        segmento = Segmento.objects.create(nombre="Seg Conv", cupo_maximo=5)
        for indice in range(3):
            Convocatoria.objects.create(
                nombre=f"Conv {indice:02d}",
                segmento=segmento,
                fecha_inicio=date(2026, 1, 1 + indice),
                fecha_fin=date(2026, 12, 31),
            )
        self.url = reverse("becas:convocatorias")

    def _html(self, query="", por_pagina=2):
        from programas.views.relevamientos import ConvocatoriaListView

        self.client.force_login(self.admin)
        with mock.patch.object(ConvocatoriaListView, "paginate_by", por_pagina):
            respuesta = self.client.get(self.url + query)
        self.assertEqual(respuesta.status_code, 200)
        return respuesta

    def test_la_vista_pagina_y_el_pie_ofrece_la_siguiente(self):
        respuesta = self._html()
        html = respuesta.content.decode()

        self.assertEqual(len(respuesta.context["convocatorias"]), 2)
        self.assertIn("Página 1 de 2 · 3 convocatorias", html)
        self.assertIn('href="?page=2"', html)

    def test_la_ultima_convocatoria_es_alcanzable(self):
        respuesta = self._html("?page=2")

        self.assertEqual(len(respuesta.context["convocatorias"]), 1)

    def test_el_tamano_de_pagina_esta_declarado_en_la_vista(self):
        from programas.views.relevamientos import ConvocatoriaListView

        self.assertEqual(ConvocatoriaListView.paginate_by, 25)

    def test_el_re_render_del_modal_devuelve_la_misma_pagina_que_el_listado(self):
        """Sin esto, guardar una convocatoria reemplazaba la tabla por la lista entera."""
        from programas.views import relevamientos as vistas

        peticion = self.client.get(self.url).wsgi_request
        peticion.user = self.admin
        with mock.patch.object(vistas, "CONVOCATORIAS_PAGE_SIZE", 2):
            contexto = vistas._contexto_convocatorias(peticion)

        self.assertEqual(len(contexto["convocatorias"]), 2)
        self.assertEqual(contexto["page_obj"].paginator.count, 3)

    def test_el_formulario_del_modal_lleva_la_pagina_que_se_esta_mirando(self):
        html = self._html("?page=2").content.decode()

        self.assertIn('<input type="hidden" name="page" value="2">', html)

    def test_al_guardar_desde_la_pagina_2_el_re_render_vuelve_a_la_2(self):
        """El POST va a `convocatoria_crear` sin querystring: mirando solo `request.GET`
        el modal devolvía siempre la página 1 aunque la URL dijera 2."""
        from programas.views import relevamientos as vistas

        self.client.force_login(self.admin)
        with mock.patch.object(vistas, "CONVOCATORIAS_PAGE_SIZE", 2):
            respuesta = self.client.post(
                reverse("becas:convocatoria_crear"),
                {
                    "nombre": "Conv nueva",
                    "segmento": Segmento.objects.get(nombre="Seg Conv").pk,
                    "fecha_inicio": "2026-02-01",
                    "fecha_fin": "2026-11-30",
                    "activo": "on",
                    "page": "2",
                },
                headers={"x-requested-with": "XMLHttpRequest"},
            )

        self.assertEqual(respuesta.status_code, 200)
        cuerpo = respuesta.json()
        self.assertTrue(cuerpo["ok"], cuerpo)
        self.assertIn("Página 2 de 2", cuerpo["html"])

    def test_sin_el_campo_oculto_el_re_render_sigue_dando_la_primera(self):
        """La conducta de siempre para quien no manda la página (el GET de la vista)."""
        from programas.views import relevamientos as vistas

        self.client.force_login(self.admin)
        with mock.patch.object(vistas, "CONVOCATORIAS_PAGE_SIZE", 2):
            respuesta = self.client.post(
                reverse("becas:convocatoria_crear"),
                {
                    "nombre": "Conv sin página",
                    "segmento": Segmento.objects.get(nombre="Seg Conv").pk,
                    "fecha_inicio": "2026-02-01",
                    "fecha_fin": "2026-11-30",
                    "activo": "on",
                },
                headers={"x-requested-with": "XMLHttpRequest"},
            )

        self.assertIn("Página 1 de 2", respuesta.json()["html"])
