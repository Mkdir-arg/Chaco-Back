"""Orden de los requisitos de programa, segmento y subsegmento por arrastre
(Cambio 264, reemplaza el orden manual del Cambio 23).

El endpoint recibe la lista completa de los requisitos **propios** de una lista
y los renumera 1..N; los heredados no se mueven desde otra pantalla.
"""

import json
from io import StringIO

from django.contrib.auth.models import Group, Permission, User
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from core.rbac import APP_LABEL, codename_de
from programas.management.commands.seed_becas import ROL_ADMIN, ROL_COORDINADOR, ROL_COORDINADOR_REGIONAL
from programas.models import AsignacionCoordinador, ProgramaSiis, RequisitoNativo, Segmento, Subsegmento, TipoCampo


def _capacidad(codigo):
    return Permission.objects.get(content_type__app_label=APP_LABEL, codename=codename_de(codigo))


def _req(texto, orden, **ancla):
    return RequisitoNativo.objects.create(texto=texto, tipo=TipoCampo.STRING, orden=orden, **ancla)


class _Base(TestCase):
    def setUp(self):
        cache.clear()
        call_command("seed_becas", stdout=StringIO())
        self.admin = User.objects.create_user("admin-req-orden", password="x")
        self.admin.groups.add(Group.objects.get(name=ROL_ADMIN))
        self.programa = ProgramaSiis.objects.create(nombre="Producción", siis_programa_id=38)
        self.seg = Segmento.objects.create(programa=self.programa, nombre="Seg A", cupo_maximo=100)
        self.otro_seg = Segmento.objects.create(programa=self.programa, nombre="Seg B", cupo_maximo=100)
        self.sub = Subsegmento.objects.create(segmento=self.seg, nombre="Sub A", cupo_maximo=40)
        # Órdenes repetidos y con huecos, como quedaron datos viejos (Cambio 23).
        self.p1 = _req("Del programa 1", 3, programa=self.programa)
        self.p2 = _req("Del programa 2", 3, programa=self.programa)
        self.s1 = _req("Del segmento 1", 1, segmento=self.seg)
        self.s2 = _req("Del segmento 2", 5, segmento=self.seg)
        self.s3 = _req("Del segmento 3", 9, segmento=self.seg)
        self.u1 = _req("Del subsegmento 1", 1, segmento=self.seg, subsegmento=self.sub)
        self.u2 = _req("Del subsegmento 2", 2, segmento=self.seg, subsegmento=self.sub)
        self.ajeno = _req("De otro segmento", 1, segmento=self.otro_seg)

    def _reordenar(self, nivel, pk, ids, **kwargs):
        return self.client.post(
            reverse("becas:requisitos_reordenar", args=[nivel, pk]),
            data=json.dumps({"ids": ids}),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            **kwargs,
        )

    @staticmethod
    def _ordenes(*reqs):
        return [RequisitoNativo.objects.get(pk=r.pk).orden for r in reqs]


class ReordenarTests(_Base):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)

    def test_reordena_el_segmento_y_renumera_compacto(self):
        resp = self._reordenar("segmento", self.seg.pk, [self.s3.pk, self.s1.pk, self.s2.pk])
        self.assertEqual(resp.status_code, 200, resp.content)
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["target"], "#reqs-panel")
        self.assertIn("data-sortable-lista", data["html"])
        self.assertEqual(self._ordenes(self.s3, self.s1, self.s2), [1, 2, 3])
        # Las otras listas no se tocan.
        self.assertEqual(self._ordenes(self.u1, self.u2, self.p1, self.ajeno), [1, 2, 3, 1])

    def test_reordena_el_programa_y_normaliza_repetidos(self):
        resp = self._reordenar("programa", self.programa.pk, [self.p2.pk, self.p1.pk])
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()["target"], "#reqs-programa-panel")
        self.assertEqual(self._ordenes(self.p2, self.p1), [1, 2])

    def test_reordena_el_subsegmento(self):
        resp = self._reordenar("subsegmento", self.sub.pk, [self.u2.pk, self.u1.pk])
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()["target"], "#reqs-propios-panel")
        self.assertEqual(self._ordenes(self.u2, self.u1), [1, 2])
        self.assertEqual(self._ordenes(self.s1, self.s2, self.s3), [1, 5, 9])

    def test_el_parcial_devuelto_sale_en_el_orden_nuevo(self):
        html = self._reordenar("segmento", self.seg.pk, [self.s3.pk, self.s1.pk, self.s2.pk]).json()["html"]
        self.assertLess(html.index("Del segmento 3"), html.index("Del segmento 1"))
        self.assertLess(html.index("Del segmento 1"), html.index("Del segmento 2"))

    def test_ids_repetidos_es_400(self):
        resp = self._reordenar("segmento", self.seg.pk, [self.s1.pk, self.s1.pk, self.s2.pk, self.s3.pk])
        self.assertEqual(resp.status_code, 400)

    def test_payload_invalido_es_400(self):
        url = reverse("becas:requisitos_reordenar", args=["segmento", self.seg.pk])
        self.assertEqual(self.client.post(url, data="no-json", content_type="application/json").status_code, 400)
        for cuerpo in ({}, {"ids": "1,2"}, {"ids": ["x"]}, {"ids": [True]}, ["no-objeto"]):
            resp = self.client.post(url, data=json.dumps(cuerpo), content_type="application/json")
            self.assertEqual(resp.status_code, 400, cuerpo)

    def test_un_id_ajeno_es_409_y_no_toca_nada(self):
        resp = self._reordenar("segmento", self.seg.pk, [self.s1.pk, self.s2.pk, self.s3.pk, self.ajeno.pk])
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(self._ordenes(self.s1, self.s2, self.s3), [1, 5, 9])

    def test_un_heredado_no_se_mueve_desde_el_subsegmento(self):
        # El del segmento se ve en el subsegmento como heredado, pero no es de su lista.
        resp = self._reordenar("subsegmento", self.sub.pk, [self.s1.pk, self.u1.pk, self.u2.pk])
        self.assertEqual(resp.status_code, 409)
        resp = self._reordenar("segmento", self.seg.pk, [self.p1.pk, self.s1.pk, self.s2.pk, self.s3.pk])
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(self._ordenes(self.s1, self.u1, self.p1), [1, 1, 3])

    def test_si_falta_uno_es_409(self):
        resp = self._reordenar("segmento", self.seg.pk, [self.s2.pk, self.s1.pk])
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(self._ordenes(self.s1, self.s2), [1, 5])

    def test_nivel_desconocido_o_ancla_inexistente_es_404(self):
        self.assertEqual(self._reordenar("convocatoria", self.seg.pk, []).status_code, 404)
        self.assertEqual(self._reordenar("segmento", 999999, []).status_code, 404)

    def test_solo_post(self):
        url = reverse("becas:requisitos_reordenar", args=["segmento", self.seg.pk])
        self.assertEqual(self.client.get(url).status_code, 405)

    def test_un_alta_despues_de_reordenar_va_al_final(self):
        self._reordenar("segmento", self.seg.pk, [self.s3.pk, self.s1.pk, self.s2.pk])
        resp = self.client.post(
            reverse("becas:requisito_crear", args=[self.seg.pk]),
            {"texto": "Nuevo", "tipo": TipoCampo.STRING, "obligatorio": "True"},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(RequisitoNativo.objects.get(texto="Nuevo").orden, 4)


class PermisosTests(_Base):
    def _coordinador(self, username, segmento, con_editar=True):
        user = User.objects.create_user(username, password="x")
        grupo = Group.objects.get(name=ROL_COORDINADOR)
        user.groups.add(grupo)
        if con_editar:
            grupo.permissions.add(_capacidad("becas.requisito.editar"))
        AsignacionCoordinador.objects.create(segmento=segmento, coordinador=user)
        cache.clear()
        return user

    def test_anonimo_no_reordena(self):
        resp = self._reordenar("segmento", self.seg.pk, [self.s3.pk, self.s1.pk, self.s2.pk])
        self.assertIn(resp.status_code, (302, 403))
        self.assertEqual(self._ordenes(self.s1, self.s2, self.s3), [1, 5, 9])

    def test_sin_la_capacidad_de_editar_es_403(self):
        # El Coordinador sembrado ve y crea requisitos, pero no los edita.
        self.client.force_login(self._coordinador("coord-sin-editar", self.seg, con_editar=False))
        resp = self._reordenar("segmento", self.seg.pk, [self.s3.pk, self.s1.pk, self.s2.pk])
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(self._ordenes(self.s1, self.s2, self.s3), [1, 5, 9])

    def test_coordinador_reordena_su_segmento_pero_no_uno_ajeno(self):
        self.client.force_login(self._coordinador("coord-con-editar", self.seg))
        resp = self._reordenar("segmento", self.seg.pk, [self.s3.pk, self.s1.pk, self.s2.pk])
        self.assertEqual(resp.status_code, 200, resp.content)
        resp = self._reordenar("segmento", self.otro_seg.pk, [self.ajeno.pk])
        self.assertEqual(resp.status_code, 403)

    def test_coordinador_no_reordena_el_programa(self):
        self.client.force_login(self._coordinador("coord-programa", self.seg))
        resp = self._reordenar("programa", self.programa.pk, [self.p2.pk, self.p1.pk])
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(self._ordenes(self.p1, self.p2), [3, 3])

    def test_regional_reordena_solo_su_subsegmento(self):
        rol = Group.objects.get(name=ROL_COORDINADOR_REGIONAL)
        rol.permissions.add(_capacidad("becas.requisito.editar"))
        ana = User.objects.create_user("ana-orden", password="x")
        ana.groups.add(rol)
        beto = User.objects.create_user("beto-orden", password="x")
        Subsegmento.objects.filter(pk=self.sub.pk).update(referente=ana)
        par = Subsegmento.objects.create(segmento=self.seg, nombre="Sub B", cupo_maximo=40, referente=beto)
        del_par = _req("Del par", 1, segmento=self.seg, subsegmento=par)
        cache.clear()
        self.client.force_login(ana)
        self.assertEqual(self._reordenar("subsegmento", self.sub.pk, [self.u2.pk, self.u1.pk]).status_code, 200)
        self.assertEqual(self._reordenar("subsegmento", par.pk, [del_par.pk]).status_code, 403)
        # Lo del segmento entero no lo configura el Regional (SEC-30).
        resp = self._reordenar("segmento", self.seg.pk, [self.s3.pk, self.s1.pk, self.s2.pk])
        self.assertEqual(resp.status_code, 403)


class RenderTests(_Base):
    def test_el_admin_ve_manijas_solo_en_las_filas_propias(self):
        self.client.force_login(self.admin)
        html = self.client.get(reverse("becas:segmento_detalle", args=[self.seg.pk])).content.decode()
        self.assertIn("data-sortable-lista", html)
        self.assertIn('data-puede-ordenar="1"', html)
        self.assertIn(reverse("becas:requisitos_reordenar", args=["segmento", self.seg.pk]), html)
        self.assertEqual(html.count('class="grip lista-grip" role="button" tabindex="0"'), 3)
        self.assertIn("flechas arriba y abajo", html)
        self.assertIn(f'data-item-id="{self.s1.pk}"', html)
        # Los heredados del programa se listan, pero sin manija ni fila ordenable.
        self.assertIn("Del programa 1", html)
        self.assertNotIn(f'data-item-id="{self.p1.pk}"', html)
        self.assertIn("vendor/sortablejs/Sortable.min.js", html)
        self.assertIn("custom/js/nodo-catalogo-grupos.js", html)
        self.assertNotIn('name="orden"', html)

    def test_subsegmento_arrastra_propios_y_heredados_quedan_fijos(self):
        self.client.force_login(self.admin)
        html = self.client.get(reverse("becas:subsegmento_detalle", args=[self.sub.pk])).content.decode()
        self.assertEqual(html.count("lista-grip"), 2)
        self.assertIn(reverse("becas:requisitos_reordenar", args=["subsegmento", self.sub.pk]), html)
        for heredado in (self.p1, self.s1):
            self.assertIn(heredado.texto, html)
            self.assertNotIn(f'data-item-id="{heredado.pk}"', html)
        self.assertNotIn('name="orden"', html)

    def test_programa_arrastra_sus_requisitos(self):
        self.client.force_login(self.admin)
        html = self.client.get(reverse("becas:programa_detalle", args=[self.programa.pk])).content.decode()
        self.assertEqual(html.count("lista-grip"), 2)
        self.assertIn(reverse("becas:requisitos_reordenar", args=["programa", self.programa.pk]), html)
        self.assertNotIn('name="orden"', html)

    def test_sin_capacidad_de_editar_no_hay_manijas(self):
        coord = User.objects.create_user("coord-lector", password="x")
        coord.groups.add(Group.objects.get(name=ROL_COORDINADOR))
        AsignacionCoordinador.objects.create(segmento=self.seg, coordinador=coord)
        self.client.force_login(coord)
        resp = self.client.get(reverse("becas:segmento_detalle", args=[self.seg.pk]))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn('data-puede-ordenar="0"', html)
        self.assertNotIn("lista-grip", html)
        self.assertNotIn("vendor/sortablejs/Sortable.min.js", html)

    def test_la_lista_transversal_no_pide_orden(self):
        self.client.force_login(self.admin)
        html = self.client.get(reverse("becas:requisitos_segmento")).content.decode()
        self.assertNotIn('name="orden"', html)


class JsListasTests(TestCase):
    def test_el_js_cablea_las_listas_planas(self):
        from pathlib import Path

        from django.conf import settings

        js = Path(settings.BASE_DIR, "static", "custom", "js", "nodo-catalogo-grupos.js").read_text(encoding="utf-8")
        self.assertIn("[data-sortable-lista]", js)
        self.assertIn("handle: '.lista-grip'", js)
        self.assertIn("lista.isConnected", js)
        self.assertIn("JSON.stringify({\n          ids:", js.replace("\r\n", "\n"))
