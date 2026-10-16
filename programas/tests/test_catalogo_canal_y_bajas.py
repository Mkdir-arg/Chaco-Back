"""Hallazgos de QA del constructor y del catálogo de Becas (#338, #339 y #341).

- E2 (#338): las listas de requisitos muestran en qué canal se pide cada uno, sin
  abrir el modal, igual que el catálogo de preguntas (`_pregunta_row.html`).
- E3 (#339): borrar un requisito o una pregunta del catálogo que estaba en un diseño
  sube la versión en el acto, anula las condiciones que lo usaban como fuente (el
  constructor ya no queda trabado con 400) y el próximo que abre el constructor ve
  qué se borró y qué condiciones cayeron por eso.
"""

import json
from datetime import date
from io import StringIO

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from programas.management.commands.seed_becas import ROL_ADMIN
from programas.models import (
    CanalFormulario,
    Convocatoria,
    DisenoFormulario,
    PreguntaGlobal,
    ProgramaSiis,
    RequisitoNativo,
    Segmento,
    Subsegmento,
    TipoCampo,
)
from programas.services.diseno import clave_pregunta, clave_requisito, obtener_o_crear_diseno, reconciliar

BADGE_APP = '<span class="badge badge-white">Solo app de campo</span>'
BADGE_LINK = '<span class="badge badge-white">Solo link público</span>'
BADGE_AMBOS = '<span class="badge badge-white">Ambos canales</span>'


class BadgeDeCanalTests(TestCase):
    """E2: el canal se ve en la celda Tipo; «ambos» no lleva badge."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_becas", stdout=StringIO())
        cls.admin = User.objects.create_user("admin_canal", password="x")
        cls.admin.groups.add(Group.objects.get(name=ROL_ADMIN))
        cls.programa = ProgramaSiis.objects.create(siis_programa_id=77, nombre="Becas canal")
        cls.segmento = Segmento.objects.create(nombre="Seg canal", cupo_maximo=10, programa=cls.programa)
        cls.subsegmento = Subsegmento.objects.create(segmento=cls.segmento, nombre="Sub canal", cupo_maximo=5)

        def requisito(texto, canal, **ancla):
            return RequisitoNativo.objects.create(texto=texto, tipo=TipoCampo.STRING, canal=canal, **ancla)

        requisito("Prog solo app", CanalFormulario.APP, programa=cls.programa)
        requisito("Prog ambos", CanalFormulario.AMBOS, programa=cls.programa)
        requisito("Seg solo link", CanalFormulario.LINK, segmento=cls.segmento)
        requisito("Seg ambos", CanalFormulario.AMBOS, segmento=cls.segmento)
        requisito("Sub solo app", CanalFormulario.APP, segmento=cls.segmento, subsegmento=cls.subsegmento)
        requisito("Sub ambos", CanalFormulario.AMBOS, segmento=cls.segmento, subsegmento=cls.subsegmento)

    def setUp(self):
        self.client.force_login(self.admin)

    def _html(self, nombre, *args):
        resp = self.client.get(reverse(f"becas:{nombre}", args=args))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertNotIn(BADGE_AMBOS, html)
        return html

    def test_panel_del_programa(self):
        html = self._html("programa_detalle", self.programa.pk)
        self.assertEqual(html.count(BADGE_APP), 1)
        self.assertNotIn(BADGE_LINK, html)

    def test_panel_del_segmento_y_heredados_del_programa(self):
        html = self._html("segmento_detalle", self.segmento.pk)
        self.assertEqual(html.count(BADGE_LINK), 1)  # el propio del segmento
        self.assertEqual(html.count(BADGE_APP), 1)  # el heredado del programa (solo lectura)

    def test_panel_del_subsegmento_y_heredados(self):
        html = self._html("subsegmento_detalle", self.subsegmento.pk)
        # Propio del subsegmento + heredado del programa; el del segmento es «link».
        self.assertEqual(html.count(BADGE_APP), 2)
        self.assertEqual(html.count(BADGE_LINK), 1)

    def test_pagina_de_requisitos(self):
        html = self._html("requisitos_segmento")
        self.assertIn(BADGE_LINK, html)
        self.assertIn(BADGE_APP, html)


class _BaseBajas(TestCase):
    """Una convocatoria con su diseño ya abierto una vez (versión 1).

    El certificado (segmento, orden 2) puede depender del nivel (segmento, orden 1);
    el barrio es el único requisito del subsegmento, así que su grupo automático se
    queda vacío si se lo borra.
    """

    def setUp(self):
        call_command("seed_becas", stdout=StringIO())
        self.admin = User.objects.create_user("admin_bajas", password="x")
        self.admin.groups.add(Group.objects.get(name=ROL_ADMIN))
        self.segmento = Segmento.objects.create(nombre="Educación", cupo_maximo=100)
        self.subsegmento = Subsegmento.objects.create(segmento=self.segmento, nombre="Resistencia", cupo_maximo=40)
        self.convocatoria = Convocatoria.objects.create(
            nombre="Becas 2026",
            segmento=self.segmento,
            subsegmento=self.subsegmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        self.nivel = RequisitoNativo.objects.create(
            texto="Nivel educativo",
            tipo=TipoCampo.SELECTOR,
            opciones=["Primario", "Secundario"],
            segmento=self.segmento,
            orden=1,
        )
        self.certificado = RequisitoNativo.objects.create(
            texto="Certificado de alumno regular", tipo=TipoCampo.ARCHIVO, segmento=self.segmento, orden=2
        )
        self.barrio = RequisitoNativo.objects.create(
            texto="Barrio", tipo=TipoCampo.STRING, segmento=self.segmento, subsegmento=self.subsegmento, orden=1
        )
        self.tenencia = PreguntaGlobal.objects.create(
            texto="Tenencia de la vivienda", tipo=TipoCampo.SELECTOR, opciones=["Propia", "Alquilada"], orden=600
        )
        self.diseno, _ = obtener_o_crear_diseno(self.convocatoria)
        self.assertEqual(self.diseno.version, 1)

    def _condicionar(self, clave_destino, fuente, valor):
        item = self.diseno.items.get(clave=clave_destino)
        item.condicion = {"modo": "todas", "reglas": [{"fuente": fuente, "op": "es", "valor": valor}]}
        item.save(update_fields=["condicion"])
        return item

    def _version(self):
        return DisenoFormulario.objects.get(pk=self.diseno.pk).version


class BorrarDelCatalogoTests(_BaseBajas):
    def test_sin_dependientes_sube_la_version_y_el_aviso_lo_nombra(self):
        self.certificado.delete()
        self.assertEqual(self._version(), 2)  # en el acto, no al abrir el constructor

        avisos = reconciliar(self.diseno)

        self.assertIn("Certificado de alumno regular", avisos["quitados"])
        self.assertEqual(avisos["fuentes_quitadas"], ["Certificado de alumno regular"])
        self.assertEqual(avisos["condiciones_quitadas"], [])
        self.assertEqual(self._version(), 2)  # ya subió con el borrado

    def test_con_dependientes_anula_la_condicion_en_el_acto_y_avisa_quien_la_perdio(self):
        cert = self._condicionar(clave_requisito(self.certificado), clave_requisito(self.nivel), "Secundario")

        self.nivel.delete()

        cert.refresh_from_db()
        self.assertIsNone(cert.condicion)
        self.assertEqual(self._version(), 2)
        avisos = reconciliar(self.diseno)
        self.assertEqual(avisos["fuentes_quitadas"], ["Nivel educativo → Certificado de alumno regular"])
        self.assertIn("Nivel educativo", avisos["quitados"])

    def test_una_pregunta_general_tambien(self):
        cert = self._condicionar(clave_requisito(self.certificado), clave_pregunta(self.tenencia), "Propia")

        self.tenencia.delete()

        cert.refresh_from_db()
        self.assertIsNone(cert.condicion)
        avisos = reconciliar(self.diseno)
        self.assertEqual(avisos["fuentes_quitadas"], ["Tenencia de la vivienda → Certificado de alumno regular"])

    def test_reconciliar_dos_veces_no_vuelve_a_avisar_ni_a_subir_la_version(self):
        """TC-339-07."""
        self.certificado.delete()
        reconciliar(self.diseno)

        avisos = reconciliar(self.diseno)

        self.assertEqual(avisos["quitados"], [])
        self.assertEqual(avisos["fuentes_quitadas"], [])
        self.assertEqual(self._version(), 2)
        self.assertIsNone(DisenoFormulario.objects.get(pk=self.diseno.pk).bajas_pendientes)

    def test_el_grupo_automatico_que_queda_vacio_se_borra_al_reconciliar(self):
        """RN-3: el barrio era el único campo del grupo del subsegmento."""
        self.barrio.delete()
        self.assertTrue(self.diseno.items.filter(clave="g-subsegmento").exists())

        reconciliar(self.diseno)

        self.assertFalse(self.diseno.items.filter(clave="g-subsegmento").exists())
        self.assertEqual(self._version(), 2)

    def test_borrado_masivo_tiene_el_mismo_efecto(self):
        cert = self._condicionar(clave_requisito(self.certificado), clave_requisito(self.nivel), "Secundario")

        RequisitoNativo.objects.filter(pk=self.nivel.pk).delete()

        cert.refresh_from_db()
        self.assertIsNone(cert.condicion)
        avisos = reconciliar(self.diseno)
        self.assertEqual(avisos["fuentes_quitadas"], ["Nivel educativo → Certificado de alumno regular"])

    def test_borrar_todo_el_catalogo_no_rompe(self):
        PreguntaGlobal.objects.all().delete()
        RequisitoNativo.objects.all().delete()
        avisos = reconciliar(self.diseno)
        self.assertIn("Tenencia de la vivienda", avisos["quitados"])
        self.assertFalse(self.diseno.items.filter(pregunta__isnull=False).exists())

    def test_borrado_desde_el_admin(self):
        cert = self._condicionar(clave_requisito(self.certificado), clave_requisito(self.nivel), "Secundario")
        root = User.objects.create_superuser("root_bajas", "root@bajas.test", "x")
        self.client.force_login(root)

        resp = self.client.post(
            reverse("admin:programas_requisitonativo_delete", args=[self.nivel.pk]), {"post": "yes"}
        )

        self.assertEqual(resp.status_code, 302)
        self.assertFalse(RequisitoNativo.objects.filter(pk=self.nivel.pk).exists())
        cert.refresh_from_db()
        self.assertIsNone(cert.condicion)
        self.assertEqual(self._version(), 2)


class ConstructorTrasElBorradoTests(_BaseBajas):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)

    def test_una_mutacion_despues_del_borrado_no_da_400(self):
        """Antes la condición quedaba apuntando a una fuente inexistente y toda
        mutación moría en `validar_coherencia` hasta reabrir el constructor."""
        self._condicionar(clave_requisito(self.certificado), clave_requisito(self.nivel), "Secundario")
        self.nivel.delete()

        resp = self.client.post(
            reverse("becas:formulario_mover", args=[self.convocatoria.pk]),
            data=json.dumps({"clave": clave_requisito(self.certificado), "padre": "g-cuestionario", "posicion": 0}),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(resp.status_code, 200, resp.content)

    def test_la_pantalla_muestra_el_aviso_de_lo_borrado(self):
        self._condicionar(clave_requisito(self.certificado), clave_requisito(self.nivel), "Secundario")
        self.nivel.delete()

        resp = self.client.get(reverse("becas:convocatoria_formulario", args=[self.convocatoria.pk]))

        self.assertIn("Nivel educativo → Certificado de alumno regular", resp.content.decode())
