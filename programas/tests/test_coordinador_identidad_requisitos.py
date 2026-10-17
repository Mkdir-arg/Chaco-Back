"""Cambio 334 — decisiones del PM del 17/10/2026 sobre el diagnóstico del Cambio 332.

1. El rol «Becas — Coordinador» suma ``becas.requisito.editar``: corrige, reordena y
   borra los requisitos de **sus** segmentos. Los de otros segmentos y los del
   programa siguen fuera de su alcance, y la pantalla del programa no le ofrece
   botones que le darían 403.
2. Validar la identidad de un caso (corregir el sexo, revalidar contra la Base de
   Personas, validar contra el padrón y forzar a mano) pasa a ser
   ``becas.programa.administrar`` **o** ``becas.revision.identidad``, con el alcance
   del Programa Becas. La capacidad nueva se siembra al Administrador y al
   Coordinador; no al Coordinador Regional ni al Referente.

Una negativa por **capacidad** redirige al inicio (``requiere``); una por
**alcance** es 403 (``assert_alcance_formulario``). Los tests distinguen las dos.
"""

import json
from datetime import date
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from legajos.models import Ciudadano
from programas.management.commands.seed_becas import (
    ROL_ADMIN,
    ROL_COORDINADOR,
    ROL_COORDINADOR_REGIONAL,
    ROL_REFERENTE,
    ROL_TERRITORIAL,
)
from programas.models import (
    AsignacionCoordinador,
    AsignacionReferente,
    Convocatoria,
    Formulario,
    ProgramaSiis,
    Relevamiento,
    RequisitoNativo,
    Segmento,
    Subsegmento,
    TipoCampo,
)
from programas.services.autorizacion import puede_validar_identidad

AJAX = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}
MOTIVO = "El DNI no figura en la Base de Personas"


def _usuario(username, rol):
    user = User.objects.create_user(username, password="x")
    user.groups.add(Group.objects.get(name=rol))
    return user


class _Base(TestCase):
    def setUp(self):
        cache.clear()
        call_command("seed_becas", stdout=StringIO())
        self.programa = ProgramaSiis.objects.create(nombre="Producción", siis_programa_id=38)
        self.seg_a = Segmento.objects.create(programa=self.programa, nombre="Seg A", cupo_maximo=100)
        self.seg_b = Segmento.objects.create(programa=self.programa, nombre="Seg B", cupo_maximo=100)
        self.sub_a = Subsegmento.objects.create(segmento=self.seg_a, nombre="Sub A", cupo_maximo=40)

        self.admin = _usuario("admin-334", ROL_ADMIN)
        self.coord = _usuario("coord-334", ROL_COORDINADOR)
        AsignacionCoordinador.objects.create(segmento=self.seg_a, coordinador=self.coord)
        self.referente = _usuario("referente-334", ROL_REFERENTE)
        AsignacionReferente.objects.create(referente=self.referente, coordinador=self.coord)
        self.regional = _usuario("regional-334", ROL_COORDINADOR_REGIONAL)
        self.sub_a.referente = self.regional
        self.sub_a.save(update_fields=["referente"])


class IdentidadTests(_Base):
    def setUp(self):
        super().setUp()
        territorial = _usuario("territorial-334", ROL_TERRITORIAL)
        self.caso_a = self._caso(self.seg_a, territorial, "30300300", subsegmento=self.sub_a)
        self.caso_b = self._caso(self.seg_b, territorial, "30300301")

    @staticmethod
    def _caso(segmento, territorial, dni, subsegmento=None):
        convocatoria = Convocatoria.objects.create(
            nombre=f"Conv {segmento.nombre}",
            segmento=segmento,
            subsegmento=subsegmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        relevamiento = Relevamiento.objects.create(
            convocatoria=convocatoria,
            territorial=territorial,
            fecha_asignada=date(2026, 6, 1),
            zona="Z",
            estado=Relevamiento.Estado.FINALIZADO,
        )
        ciudadano = Ciudadano.objects.create(
            dni=dni, nombre="Persona", apellido="Sin Fuente", genero="", fecha_nacimiento=date(1990, 5, 5)
        )
        return Formulario.objects.create(
            relevamiento=relevamiento,
            ciudadano=ciudadano,
            celular="3624100100",
            validado_renaper=False,
            data={"globales": {}, "requisitos": {}},
        )

    def _forzar(self, caso):
        return self.client.post(reverse("becas:formulario_forzar_identidad", args=[caso.pk]), {"motivo": MOTIVO})

    def _validado(self, caso):
        caso.refresh_from_db()
        return caso.validado_renaper

    # --- la regla ---------------------------------------------------------------
    def test_la_regla_por_rol_sembrado(self):
        self.assertTrue(puede_validar_identidad(self.admin))
        self.assertTrue(puede_validar_identidad(self.coord))
        self.assertFalse(puede_validar_identidad(self.regional))
        self.assertFalse(puede_validar_identidad(self.referente))

    # --- forzar -------------------------------------------------------------------
    def test_el_coordinador_fuerza_un_caso_de_su_segmento(self):
        self.client.force_login(self.coord)

        respuesta = self._forzar(self.caso_a)

        self.assertRedirects(respuesta, reverse("becas:formulario_detalle", args=[self.caso_a.pk]))
        self.assertTrue(self._validado(self.caso_a))
        self.assertTrue(self.caso_a.identidad_forzada)

    def test_el_coordinador_no_fuerza_un_caso_de_otro_segmento(self):
        self.client.force_login(self.coord)

        respuesta = self._forzar(self.caso_b)

        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(self._validado(self.caso_b))

    def test_regional_y_referente_no_fuerzan_ni_en_su_alcance(self):
        for usuario in (self.regional, self.referente):
            with self.subTest(usuario=usuario.username):
                self.client.force_login(usuario)

                respuesta = self._forzar(self.caso_a)

                self.assertRedirects(respuesta, reverse("core:inicio"), fetch_redirect_response=False)
                self.assertFalse(self._validado(self.caso_a))

    def test_el_admin_sigue_forzando(self):
        self.client.force_login(self.admin)

        self._forzar(self.caso_b)

        self.assertTrue(self._validado(self.caso_b))

    # --- revalidar, sexo y padrón -------------------------------------------------
    @patch("programas.views.revision.consultar_persona")
    def test_el_coordinador_revalida_un_caso_de_su_segmento(self, consultar):
        consultar.return_value = {
            "success": True,
            "data": {"nombre": "Persona", "apellido": "Con Fuente", "fecha_nacimiento": "1990-05-05", "sexo": "F"},
        }
        self.caso_a.ciudadano.genero = "F"
        self.caso_a.ciudadano.save(update_fields=["genero"])
        self.client.force_login(self.coord)

        self.client.post(reverse("becas:formulario_revalidar_renaper", args=[self.caso_a.pk]))

        consultar.assert_called_once()
        self.assertTrue(self._validado(self.caso_a))

    @patch("programas.views.revision.consultar_persona")
    def test_el_referente_no_revalida(self, consultar):
        self.client.force_login(self.referente)

        respuesta = self.client.post(reverse("becas:formulario_revalidar_renaper", args=[self.caso_a.pk]))

        self.assertRedirects(respuesta, reverse("core:inicio"), fetch_redirect_response=False)
        consultar.assert_not_called()

    def test_el_coordinador_corrige_el_sexo_de_un_caso_de_su_segmento(self):
        self.client.force_login(self.coord)

        self.client.post(reverse("becas:formulario_actualizar_genero", args=[self.caso_a.pk]), {"genero": "M"})

        self.caso_a.ciudadano.refresh_from_db()
        self.assertEqual(self.caso_a.ciudadano.genero, "M")

    def test_el_coordinador_no_corrige_el_sexo_de_otro_segmento(self):
        self.client.force_login(self.coord)

        respuesta = self.client.post(
            reverse("becas:formulario_actualizar_genero", args=[self.caso_b.pk]), {"genero": "M"}
        )

        self.assertEqual(respuesta.status_code, 403)
        self.caso_b.ciudadano.refresh_from_db()
        self.assertEqual(self.caso_b.ciudadano.genero, "")

    def test_validar_padron_pasa_la_puerta_solo_en_su_segmento(self):
        self.client.force_login(self.coord)
        propio = self.client.post(reverse("becas:formulario_validar_padron", args=[self.caso_a.pk]))
        # Sin padrón cargado la vista avisa y vuelve al caso: lo que se mide es que la
        # puerta lo dejó pasar (sin la capacidad redirigiría al inicio).
        self.assertRedirects(propio, reverse("becas:formulario_detalle", args=[self.caso_a.pk]))

        ajeno = self.client.post(reverse("becas:formulario_validar_padron", args=[self.caso_b.pk]))
        self.assertEqual(ajeno.status_code, 403)

    # --- bandeja y botones --------------------------------------------------------
    def test_la_bandeja_del_coordinador_muestra_solo_su_alcance(self):
        self.client.force_login(self.coord)

        respuesta = self.client.get(reverse("becas:renaper_pendientes"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual([f.pk for f in respuesta.context["formularios"]], [self.caso_a.pk])

    def test_la_bandeja_del_admin_muestra_todos(self):
        self.client.force_login(self.admin)

        respuesta = self.client.get(reverse("becas:renaper_pendientes"))

        self.assertEqual({f.pk for f in respuesta.context["formularios"]}, {self.caso_a.pk, self.caso_b.pk})

    def test_regional_y_referente_no_entran_a_la_bandeja(self):
        for usuario in (self.regional, self.referente):
            with self.subTest(usuario=usuario.username):
                self.client.force_login(usuario)
                respuesta = self.client.get(reverse("becas:renaper_pendientes"))
                self.assertRedirects(respuesta, reverse("core:inicio"), fetch_redirect_response=False)

    def test_el_link_y_el_contador_de_la_bandeja_siguen_la_misma_regla(self):
        url_bandeja = reverse("becas:renaper_pendientes")
        self.client.force_login(self.coord)
        respuesta = self.client.get(reverse("becas:revision"))
        self.assertContains(respuesta, url_bandeja)
        self.assertEqual(respuesta.context["pendientes_renaper"], 1)

        # El Referente revisa (``revision.ver``) pero no valida identidades.
        self.client.force_login(self.referente)
        respuesta = self.client.get(reverse("becas:revision"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, url_bandeja)
        self.assertNotIn("pendientes_renaper", respuesta.context)

    def test_los_botones_del_caso_siguen_la_misma_regla(self):
        url_forzar = reverse("becas:formulario_forzar_identidad", args=[self.caso_a.pk])
        url_genero = reverse("becas:formulario_actualizar_genero", args=[self.caso_a.pk])
        detalle = reverse("becas:formulario_detalle", args=[self.caso_a.pk])

        self.client.force_login(self.coord)
        respuesta = self.client.get(detalle)
        self.assertContains(respuesta, url_forzar)
        self.assertContains(respuesta, url_genero)

        self.client.force_login(self.referente)
        respuesta = self.client.get(detalle)
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, url_forzar)
        self.assertNotContains(respuesta, url_genero)


class RequisitosTests(_Base):
    def setUp(self):
        super().setUp()
        self.del_programa = self._req("Del programa", programa=self.programa)
        self.propio_1 = self._req("Propio 1", segmento=self.seg_a, orden=1)
        self.propio_2 = self._req("Propio 2", segmento=self.seg_a, orden=2)
        self.del_sub = self._req("Del subsegmento", segmento=self.seg_a, subsegmento=self.sub_a)
        self.ajeno = self._req("Ajeno", segmento=self.seg_b)
        self.client.force_login(self.coord)

    @staticmethod
    def _req(texto, orden=1, **ancla):
        return RequisitoNativo.objects.create(texto=texto, tipo=TipoCampo.STRING, orden=orden, **ancla)

    def _editar(self, req):
        return self.client.post(
            reverse("becas:requisito_editar", args=[req.pk]),
            {"texto": "Texto corregido", "tipo": TipoCampo.STRING, "obligatorio": "True"},
            **AJAX,
        )

    def _reordenar(self, nivel, pk, ids):
        return self.client.post(
            reverse("becas:requisitos_reordenar", args=[nivel, pk]),
            data=json.dumps({"ids": ids}),
            content_type="application/json",
            **AJAX,
        )

    def test_el_coordinador_edita_reordena_y_borra_los_de_su_segmento(self):
        self.assertEqual(self._editar(self.propio_1).status_code, 200)
        self.propio_1.refresh_from_db()
        self.assertEqual(self.propio_1.texto, "Texto corregido")

        self.assertEqual(self._editar(self.del_sub).status_code, 200)

        respuesta = self._reordenar("segmento", self.seg_a.pk, [self.propio_2.pk, self.propio_1.pk])
        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        self.propio_2.refresh_from_db()
        self.assertEqual(self.propio_2.orden, 1)

        self.client.post(reverse("becas:requisito_eliminar", args=[self.propio_2.pk]))
        self.assertFalse(RequisitoNativo.objects.filter(pk=self.propio_2.pk).exists())

    def test_el_coordinador_no_toca_los_de_otro_segmento(self):
        self.assertEqual(self._editar(self.ajeno).status_code, 403)
        self.assertEqual(self._reordenar("segmento", self.seg_b.pk, [self.ajeno.pk]).status_code, 403)
        self.assertEqual(self.client.post(reverse("becas:requisito_eliminar", args=[self.ajeno.pk])).status_code, 403)
        self.ajeno.refresh_from_db()
        self.assertEqual(self.ajeno.texto, "Ajeno")

    def test_el_coordinador_no_toca_los_del_programa(self):
        self.assertEqual(self._editar(self.del_programa).status_code, 403)
        self.assertEqual(self._reordenar("programa", self.programa.pk, [self.del_programa.pk]).status_code, 403)
        eliminar = self.client.post(reverse("becas:requisito_eliminar", args=[self.del_programa.pk]))
        self.assertEqual(eliminar.status_code, 403)
        crear = self.client.post(
            reverse("becas:requisito_programa_crear", args=[self.programa.pk]),
            {"texto": "Nuevo", "tipo": TipoCampo.STRING, "obligatorio": "True"},
            **AJAX,
        )
        self.assertEqual(crear.status_code, 403)
        self.del_programa.refresh_from_db()
        self.assertEqual(self.del_programa.texto, "Del programa")
        self.assertFalse(RequisitoNativo.objects.filter(texto="Nuevo").exists())

    def test_el_coordinador_no_ve_las_acciones_del_programa(self):
        respuesta = self.client.get(reverse("becas:programa_detalle", args=[self.programa.pk]))

        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, '@click="modalReq=true"')
        self.assertNotContains(respuesta, reverse("becas:requisito_editar", args=[self.del_programa.pk]))
        self.assertNotContains(respuesta, reverse("becas:requisito_eliminar", args=[self.del_programa.pk]))

    def test_el_admin_ve_las_acciones_del_programa(self):
        self.client.force_login(self.admin)

        respuesta = self.client.get(reverse("becas:programa_detalle", args=[self.programa.pk]))

        self.assertContains(respuesta, '@click="modalReq=true"')
        self.assertContains(respuesta, reverse("becas:requisito_editar", args=[self.del_programa.pk]))

    def test_la_lista_transversal_solo_ofrece_editar_lo_que_puede(self):
        respuesta = self.client.get(reverse("becas:requisitos_segmento"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, reverse("becas:requisito_editar", args=[self.propio_1.pk]))
        self.assertNotContains(respuesta, reverse("becas:requisito_editar", args=[self.del_programa.pk]))
