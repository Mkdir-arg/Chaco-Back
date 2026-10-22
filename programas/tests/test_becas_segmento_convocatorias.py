"""Solapa «Convocatorias» del detalle del segmento (Becas), solo lectura.

Lista las convocatorias del segmento entero y las de sus subsegmentos. Se muestra
por la capacidad ``becas.convocatoria.ver`` y las filas se acotan con
``convocatorias_visibles``: el Coordinador Regional ve solo las de su subsegmento.
"""

from django.contrib.auth.models import Group, User
from django.urls import reverse

from programas.management.commands.seed_becas import ROL_ADMIN
from programas.models import Convocatoria
from programas.tests.test_coordinador_regional import _BaseRegional, _capacidad
from users.models import RolMeta

TAB_BOTON = "@click=\"tab='convs'\""
TAB_PANEL = "x-show=\"tab==='convs'\""
VACIO = "Este segmento todavía no tiene convocatorias."


class SolapaConvocatoriasSegmentoTests(_BaseRegional):
    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_user("admin_convs", password="x")
        self.admin.groups.add(Group.objects.get(name=ROL_ADMIN))
        self.entera = self._convocatoria("Del segmento entero", self.segmento)
        self.de_ana = self._convocatoria("De Ladrillo", self.segmento, self.sub_ana)
        self.de_beto = self._convocatoria("De Carbón", self.segmento, self.sub_beto)
        self.ajena = self._convocatoria("De otro segmento", self.otro_segmento, self.sub_ajeno)
        self.url = reverse("becas:segmento_detalle", args=[self.segmento.pk])

    def _convocatoria(self, nombre, segmento, subsegmento=None):
        return Convocatoria.objects.create(
            nombre=nombre,
            segmento=segmento,
            subsegmento=subsegmento,
            fecha_inicio=self.fecha_inicio,
            fecha_fin=self.fecha_fin,
        )

    def _get(self, user):
        self.client.force_login(user)
        return self.client.get(self.url)

    def test_aparece_con_su_contador_y_lista_segmento_y_subsegmentos(self):
        resp = self._get(self.admin)

        self.assertContains(resp, TAB_BOTON)
        self.assertContains(resp, TAB_PANEL)
        self.assertEqual(resp.context["puede_ver_convocatorias"], True)
        self.assertCountEqual(resp.context["convocatorias"], [self.entera, self.de_ana, self.de_beto])
        html = resp.content.decode()
        self.assertRegex(html, r"Convocatorias\s*<span class=\"badge badge-gray ml-0\.5\">3</span>")
        for nombre in ("Del segmento entero", "De Ladrillo", "De Carbón"):
            self.assertIn(nombre, html)
        # La convocatoria a nivel segmento lo dice; las de subsegmento, su nombre.
        self.assertEqual(html.count("Todo el segmento"), 1)

    def test_no_lista_convocatorias_de_otro_segmento(self):
        resp = self._get(self.admin)

        self.assertNotIn(self.ajena, resp.context["convocatorias"])
        self.assertNotContains(resp, "De otro segmento</a>")

    def test_cada_fila_enlaza_al_detalle_de_su_convocatoria(self):
        resp = self._get(self.admin)

        for c in (self.entera, self.de_ana, self.de_beto):
            url = reverse("becas:convocatoria_detalle", args=[c.pk])
            self.assertContains(
                resp, f'<a href="{url}" class="text-fg-brand hover:underline">{c.nombre}</a>', html=False
            )

    def test_no_trae_las_acciones_de_activar_ni_desactivar(self):
        resp = self._get(self.admin)

        for c in (self.entera, self.de_ana, self.de_beto):
            self.assertNotContains(resp, reverse("becas:convocatoria_toggle", args=[c.pk]))
            self.assertNotContains(resp, reverse("becas:convocatoria_reactivar", args=[c.pk]))

    def test_sin_convocatorias_muestra_el_estado_vacio(self):
        Convocatoria.objects.filter(segmento=self.segmento).delete()

        resp = self._get(self.admin)

        self.assertContains(resp, VACIO)
        self.assertContains(resp, TAB_BOTON)

    def test_sin_becas_convocatoria_ver_no_ve_la_solapa(self):
        rol = Group.objects.create(name="Solo segmentos")
        rol.permissions.set(self.rol.permissions.exclude(pk=_capacidad("becas.convocatoria.ver").pk))
        meta = self.rol.meta
        RolMeta.objects.create(grupo=rol, categoria=meta.categoria, programa=meta.programa, activo=True)
        usuario = User.objects.create_user("sin_convs", password="x")
        usuario.groups.add(rol)
        self.sub_ana.referente = usuario
        self.sub_ana.save(update_fields=["referente", "modificado"])

        resp = self._get(usuario)

        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.context["puede_ver_convocatorias"])
        self.assertNotContains(resp, TAB_BOTON)
        self.assertNotContains(resp, TAB_PANEL)
        self.assertNotContains(resp, "De Ladrillo</a>")

    def test_el_coordinador_regional_ve_solo_las_de_su_subsegmento(self):
        resp = self._get(self.ana)

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context["puede_ver_convocatorias"])
        self.assertEqual(list(resp.context["convocatorias"]), [self.de_ana])
        self.assertContains(resp, TAB_BOTON)
        self.assertContains(resp, "De Ladrillo</a>")
        self.assertNotContains(resp, "De Carbón</a>")
        self.assertNotContains(resp, "Del segmento entero</a>")

    def test_sin_n_mas_uno_en_la_tabla(self):
        """Más convocatorias no suman consultas: el badge de estado no pega por fila."""
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        self.client.force_login(self.admin)
        self.client.get(self.url)
        with CaptureQueriesContext(connection) as pocas:
            self.client.get(self.url)
        for i in range(6):
            self._convocatoria(f"Extra {i}", self.segmento, self.sub_ana if i % 2 else None)
        with CaptureQueriesContext(connection) as muchas:
            self.client.get(self.url)

        self.assertEqual(len(muchas), len(pocas))
