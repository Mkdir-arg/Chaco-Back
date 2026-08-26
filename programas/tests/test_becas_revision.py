"""Tests de la revisión de formularios de Becas (#77)."""

import csv
from datetime import date
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core import mail
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.template import TemplateDoesNotExist
from django.test import RequestFactory, TestCase
from django.urls import reverse

from legajos.models import Ciudadano
from programas.forms import FormularioRevisionForm
from programas.management.commands.seed_becas import ROL_ADMIN, ROL_COORDINADOR, ROL_TERRITORIAL
from programas.models import (
    AdjuntoFormulario,
    AsignacionCoordinador,
    Convocatoria,
    Formulario,
    ListaEspera,
    PreguntaGlobal,
    ProgramaSiis,
    Relevamiento,
    Segmento,
    TipoCampo,
    TracaFormulario,
    ValidacionSIS,
)
from programas.views.cupo import promover_lista_espera_view
from programas.views.revision import formulario_aprobar, formulario_rechazar


class _BaseRevisionTest(TestCase):
    def setUp(self):
        # programa_becas() cachea una instancia de Programa. Cada TestCase
        # revierte la base, por lo que no debe reutilizarse la PK del caso anterior.
        cache.clear()
        call_command("seed_becas", stdout=StringIO())
        self.seg_a = Segmento.objects.create(nombre="Seg A", cupo_maximo=100)
        self.seg_b = Segmento.objects.create(nombre="Seg B", cupo_maximo=100)
        self.conv_a = Convocatoria.objects.create(
            nombre="Conv A", segmento=self.seg_a, fecha_inicio=date(2026, 1, 1), fecha_fin=date(2026, 12, 31)
        )
        self.conv_b = Convocatoria.objects.create(
            nombre="Conv B", segmento=self.seg_b, fecha_inicio=date(2026, 1, 1), fecha_fin=date(2026, 12, 31)
        )
        self.territorial = User.objects.create_user("terri", password="x")
        self.territorial.groups.add(Group.objects.get(name=ROL_TERRITORIAL))

        self.rel_a = Relevamiento.objects.create(
            convocatoria=self.conv_a,
            territorial=self.territorial,
            fecha_asignada=date(2026, 6, 1),
            zona="A",
            estado=Relevamiento.Estado.FINALIZADO,
        )
        self.rel_b = Relevamiento.objects.create(
            convocatoria=self.conv_b,
            territorial=self.territorial,
            fecha_asignada=date(2026, 6, 1),
            zona="B",
            estado=Relevamiento.Estado.FINALIZADO,
        )
        self.form_a = Formulario.objects.create(
            relevamiento=self.rel_a,
            celular="3624100100",
            email_contacto="a@b.com",
            data={"globales": {}, "requisitos": {}},
        )
        self.form_b = Formulario.objects.create(
            relevamiento=self.rel_b,
            celular="3624200200",
            email_contacto="b@b.com",
        )

        self.admin = User.objects.create_user("admin_becas", password="x")
        self.admin.groups.add(Group.objects.get(name=ROL_ADMIN))
        self.coord_a = User.objects.create_user("coord_a", password="x")
        self.coord_a.groups.add(Group.objects.get(name=ROL_COORDINADOR))
        AsignacionCoordinador.objects.create(segmento=self.seg_a, coordinador=self.coord_a)


class AccesoRevisionTests(_BaseRevisionTest):
    def test_coordinador_accede_revision(self):
        self.client.force_login(self.coord_a)
        self.assertEqual(self.client.get(reverse("becas:revision")).status_code, 200)

    def test_territorial_no_accede(self):
        self.client.force_login(self.territorial)
        self.assertEqual(self.client.get(reverse("becas:revision")).status_code, 302)

    def test_coordinador_formularios_fuera_de_alcance_403(self):
        self.client.force_login(self.coord_a)
        resp = self.client.get(reverse("becas:revision_formularios", args=[self.rel_b.pk]))
        self.assertEqual(resp.status_code, 403)

    def test_coordinador_formulario_ajeno_403(self):
        self.client.force_login(self.coord_a)
        resp = self.client.get(reverse("becas:formulario_detalle", args=[self.form_b.pk]))
        self.assertEqual(resp.status_code, 403)


class EdicionTrazaTests(_BaseRevisionTest):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.coord_a)

    def test_editar_genera_traza(self):
        resp = self.client.post(
            reverse("becas:formulario_detalle", args=[self.form_a.pk]),
            {
                "celular": "3624999999",  # cambia
                "email_contacto": "a@b.com",  # igual
                "apoderado_nombre": "",
                "apoderado_apellido": "",
                "apoderado_dni": "",
                "apoderado_genero": "",
                "apoderado_fecha_nacimiento": "",
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.form_a.refresh_from_db()
        self.assertEqual(self.form_a.celular, "3624999999")
        traza = TracaFormulario.objects.filter(formulario=self.form_a, campo="Celular")
        self.assertEqual(traza.count(), 1)
        self.assertEqual(traza.first().valor_anterior, "3624100100")
        self.assertEqual(traza.first().valor_nuevo, "3624999999")

    def test_adjunto_imagen_muestra_thumbnail_y_preview(self):
        pregunta = PreguntaGlobal.objects.create(
            texto="Foto DNI",
            tipo=TipoCampo.ARCHIVO,
            activo=True,
        )
        self.form_a.data = {
            "globales": {str(pregunta.pk): {"archivo_adjunto": True}},
            "requisitos": {},
        }
        self.form_a.save(update_fields=["data"])
        AdjuntoFormulario.objects.create(
            formulario=self.form_a,
            pregunta_global=pregunta,
            archivo=SimpleUploadedFile("dni.jpg", b"imagen", content_type="image/jpeg"),
        )

        resp = self.client.get(reverse("becas:formulario_detalle", args=[self.form_a.pk]))

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "data-image-preview")
        self.assertContains(resp, "<img", html=False)
        self.assertContains(resp, "Ampliar imagen")

    def test_detalle_muestra_fechas_y_mapa_de_la_toma(self):
        self.form_a.gps_lat = "-34.577067"
        self.form_a.gps_lng = "-58.486240"
        self.form_a.save(update_fields=["gps_lat", "gps_lng"])

        resp = self.client.get(reverse("becas:formulario_detalle", args=[self.form_a.pk]))

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Trazabilidad de la toma")
        self.assertContains(resp, "Fecha asignada")
        self.assertContains(resp, "Capturado en el dispositivo")
        self.assertContains(resp, "Recibido en el servidor")
        self.assertContains(resp, "Última actualización")
        self.assertContains(resp, "Mapa del lugar donde se realizó la toma")
        self.assertContains(resp, "-34.577067")
        self.assertContains(resp, "-58.486240")
        self.assertContains(resp, "openstreetmap.org")

    def test_detalle_sin_gps_informa_que_no_hay_coordenadas(self):
        resp = self.client.get(reverse("becas:formulario_detalle", args=[self.form_a.pk]))

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Este formulario no tiene coordenadas GPS registradas.")
        self.assertNotContains(resp, "Mapa del lugar donde se realizó la toma")

    def test_detalle_muestra_respuesta_completa_de_siis(self):
        ValidacionSIS.objects.create(
            formulario=self.form_a,
            estado=ValidacionSIS.Estado.OK,
            id_programa=41,
            documento="24459123",
            id_consulta="8ef13bfb-529a-4438-a8b4-dca8b238039a",
            respuesta={
                "nombre_programa": "Chaco Subsidia",
                "id_programa": 41,
                "persona_registrada_siis": False,
                "validaciones": {
                    "padron_siis": "NUEVO_SOLICITANTE",
                    "vigencia_programa": "VIGENTE",
                    "edad_minima": "CUMPLE_EDAD_MINIMA",
                    "empleo_publico": "SIN_INCOMPATIBILIDAD",
                    "horas_docentes": "SIN_INCOMPATIBILIDAD",
                    "duplicidad_becas": "SIN_INCOMPATIBILIDAD",
                },
            },
            solicitado_por=self.admin,
        )

        resp = self.client.get(reverse("becas:formulario_detalle", args=[self.form_a.pk]))

        self.assertContains(resp, "Compatible")
        self.assertContains(resp, "Nuevo solicitante")
        self.assertContains(resp, "Chaco Subsidia (#41)")
        self.assertContains(resp, "Empleo público")
        self.assertContains(resp, "Sin incompatibilidad")
        self.assertContains(resp, "8ef13bfb-529a-4438-a8b4-dca8b238039a")
        self.assertContains(resp, "no implica la aprobación automática")
        self.assertContains(resp, "Historial de validaciones (1)")

    def test_historial_siis_muestra_todos_los_intentos(self):
        for estado, consulta in (
            (ValidacionSIS.Estado.RECHAZADO, "11111111-1111-4111-8111-111111111111"),
            (ValidacionSIS.Estado.OK, "22222222-2222-4222-8222-222222222222"),
        ):
            ValidacionSIS.objects.create(
                formulario=self.form_a,
                estado=estado,
                id_programa=41,
                documento="24459123",
                id_consulta=consulta,
                respuesta={"nombre_programa": "Chaco Subsidia", "persona_registrada_siis": False},
                solicitado_por=self.admin,
            )

        resp = self.client.get(reverse("becas:formulario_detalle", args=[self.form_a.pk]))

        self.assertContains(resp, "Historial de validaciones (2)")
        self.assertContains(resp, "11111111-1111-4111-8111-111111111111")
        self.assertContains(resp, "22222222-2222-4222-8222-222222222222")
        self.assertContains(resp, 'id="btn-historial-siis"', html=False)
        self.assertContains(resp, 'aria-expanded="false"', html=False)
        self.assertContains(resp, 'id="historial-validaciones-siis" class="hidden', html=False)

    def test_editar_sin_cambios_no_traza(self):
        self.client.post(
            reverse("becas:formulario_detalle", args=[self.form_a.pk]),
            {
                "celular": "3624100100",
                "email_contacto": "a@b.com",
                "apoderado_nombre": "",
                "apoderado_apellido": "",
                "apoderado_dni": "",
                "apoderado_genero": "",
                "apoderado_fecha_nacimiento": "",
            },
        )
        self.assertEqual(TracaFormulario.objects.filter(formulario=self.form_a).count(), 0)

    def test_editar_menor_sin_apoderado_muestra_errores(self):
        self.form_a.ciudadano = Ciudadano.objects.create(
            dni="60600600",
            nombre="Persona",
            apellido="Menor",
            fecha_nacimiento=date(date.today().year - 10, 1, 1),
        )
        self.form_a.save(update_fields=["ciudadano"])

        form = FormularioRevisionForm(
            data={
                "celular": "3624100100",
                "email_contacto": "a@b.com",
                "apoderado_nombre": "",
                "apoderado_apellido": "",
                "apoderado_dni": "",
                "apoderado_genero": "",
                "apoderado_fecha_nacimiento": "",
            },
            instance=self.form_a,
        )

        self.assertFalse(form.is_valid())
        self.assertEqual(
            set(form.errors),
            {
                "apoderado_nombre",
                "apoderado_apellido",
                "apoderado_dni",
                "apoderado_genero",
                "apoderado_fecha_nacimiento",
            },
        )

    def test_detalle_adulto_sin_apoderado_oculta_sus_campos(self):
        self.form_a.ciudadano = Ciudadano.objects.create(
            dni="60600601",
            nombre="Persona",
            apellido="Adulta",
            fecha_nacimiento=date(1990, 1, 1),
        )
        self.form_a.save(update_fields=["ciudadano"])

        resp = self.client.get(reverse("becas:formulario_detalle", args=[self.form_a.pk]))

        self.assertContains(resp, "Datos de contacto")
        self.assertNotContains(resp, "Datos del apoderado")
        self.assertNotContains(resp, 'name="apoderado_fecha_nacimiento"')

    def test_detalle_menor_muestra_fecha_apoderado_en_formato_html(self):
        self.form_a.ciudadano = Ciudadano.objects.create(
            dni="60600602",
            nombre="Persona",
            apellido="Menor",
            fecha_nacimiento=date(2020, 1, 1),
        )
        self.form_a.apoderado_nombre = "Ana"
        self.form_a.apoderado_apellido = "Pérez"
        self.form_a.apoderado_dni = "27111444"
        self.form_a.apoderado_genero = "F"
        self.form_a.apoderado_fecha_nacimiento = date(1993, 7, 13)
        self.form_a.save(
            update_fields=[
                "ciudadano",
                "apoderado_nombre",
                "apoderado_apellido",
                "apoderado_dni",
                "apoderado_genero",
                "apoderado_fecha_nacimiento",
            ]
        )

        resp = self.client.get(reverse("becas:formulario_detalle", args=[self.form_a.pk]))

        self.assertContains(resp, "Datos del apoderado")
        self.assertContains(resp, 'value="1993-07-13"')


class RevalidacionRenaperTests(_BaseRevisionTest):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.ciudadano = Ciudadano.objects.create(
            dni="60600600",
            nombre="Nomvre",
            apellido="Anterior",
            fecha_nacimiento=date(1990, 1, 1),
            genero="F",
        )
        self.form_a.ciudadano = self.ciudadano
        self.form_a.validado_renaper = False
        self.form_a.save(update_fields=["ciudadano", "validado_renaper"])

    def test_admin_puede_completar_genero_desde_el_detalle(self):
        self.ciudadano.genero = ""
        self.ciudadano.save(update_fields=["genero"])
        self.client.force_login(self.admin)

        resp = self.client.post(
            reverse("becas:formulario_actualizar_genero", args=[self.form_a.pk]),
            {"genero": "F"},
        )

        self.assertRedirects(resp, reverse("becas:formulario_detalle", args=[self.form_a.pk]))
        self.ciudadano.refresh_from_db()
        self.assertEqual(self.ciudadano.genero, "F")
        self.assertTrue(
            TracaFormulario.objects.filter(
                formulario=self.form_a,
                campo="Ciudadano · sexo",
                valor_nuevo="Femenino",
            ).exists()
        )

    @patch("programas.views.revision.consultar_persona")
    def test_admin_revalida_corrige_ciudadano_y_registra_traza(self, consultar):
        consultar.return_value = {
            "success": True,
            "data": {
                "nombre": "Nombre",
                "apellido": "Correcto",
                "fecha_nacimiento": "1990-02-03",
                "sexo": "F",
            },
        }
        self.client.force_login(self.admin)

        resp = self.client.post(reverse("becas:formulario_revalidar_renaper", args=[self.form_a.pk]))

        self.assertEqual(resp.status_code, 302)
        self.form_a.refresh_from_db()
        self.ciudadano.refresh_from_db()
        self.assertTrue(self.form_a.validado_renaper)
        self.assertEqual(self.ciudadano.nombre, "Nombre")
        self.assertEqual(self.ciudadano.apellido, "Correcto")
        self.assertTrue(TracaFormulario.objects.filter(formulario=self.form_a, campo="Base de Personas").exists())

    @patch("programas.views.revision.consultar_persona")
    def test_error_renaper_no_modifica_formulario(self, consultar):
        consultar.return_value = {"success": False, "error": "Servicio no disponible"}
        self.client.force_login(self.admin)

        self.client.post(reverse("becas:formulario_revalidar_renaper", args=[self.form_a.pk]))

        self.form_a.refresh_from_db()
        self.ciudadano.refresh_from_db()
        self.assertFalse(self.form_a.validado_renaper)
        self.assertEqual(self.ciudadano.nombre, "Nomvre")
        self.assertFalse(TracaFormulario.objects.filter(formulario=self.form_a).exists())

    @patch("programas.views.revision.consultar_persona")
    def test_coordinador_no_puede_revalidar(self, consultar):
        self.client.force_login(self.coord_a)

        resp = self.client.post(reverse("becas:formulario_revalidar_renaper", args=[self.form_a.pk]))

        self.assertEqual(resp.status_code, 302)
        consultar.assert_not_called()
        self.form_a.refresh_from_db()
        self.assertFalse(self.form_a.validado_renaper)


class ReportesBecasTests(_BaseRevisionTest):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.ciudadano = Ciudadano.objects.create(
            dni="70700700", nombre="Ana", apellido="Pérez", fecha_nacimiento=date(1990, 1, 1), genero="F"
        )
        self.form_a.ciudadano = self.ciudadano
        self.form_a.estado = Formulario.Estado.APROBADO
        self.form_a.save(update_fields=["ciudadano", "estado"])

    def _csv(self, response):
        return list(csv.reader(StringIO(response.content.decode("utf-8-sig"))))

    def test_beneficiarios_exporta_columnas_y_solo_aprobados(self):
        Formulario.objects.create(
            relevamiento=self.rel_a,
            celular="1",
            email_contacto="pendiente@example.com",
            estado=Formulario.Estado.ENVIADO,
        )
        self.client.force_login(self.admin)

        response = self.client.get(reverse("becas:convocatoria_export_beneficiarios", args=[self.conv_a.pk]))
        rows = self._csv(response)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(rows[0], ["Nombre", "DNI", "Segmento", "Convocatoria", "Fecha de aprobación"])
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][1], "70700700")

    def test_avance_exporta_conteos_por_estado(self):
        Formulario.objects.create(
            relevamiento=self.rel_a,
            celular="1",
            email_contacto="rechazado@example.com",
            estado=Formulario.Estado.RECHAZADO,
        )
        self.client.force_login(self.admin)

        rows = self._csv(self.client.get(reverse("becas:convocatoria_export_relevamientos", args=[self.conv_a.pk])))

        self.assertEqual(rows[0][-3:], ["Enviados", "Aprobados", "Rechazados"])
        self.assertEqual(rows[1][-3:], ["0", "1", "1"])

    def test_lista_espera_exporta_solo_no_promovidos(self):
        ListaEspera.objects.create(formulario=self.form_a, segmento=self.seg_a, posicion=1)
        self.client.force_login(self.admin)

        rows = self._csv(self.client.get(reverse("becas:convocatoria_export_lista_espera", args=[self.conv_a.pk])))

        self.assertEqual(rows[0], ["Posición", "Nombre", "DNI", "Segmento", "Fecha de ingreso"])
        self.assertEqual(rows[1][0:3], ["1", "Ana Pérez", "70700700"])

    def test_coordinador_no_puede_exportar(self):
        self.client.force_login(self.coord_a)

        response = self.client.get(reverse("becas:convocatoria_export_beneficiarios", args=[self.conv_a.pk]))

        self.assertEqual(response.status_code, 302)
        self.assertNotIn("attachment", response.headers.get("Content-Disposition", ""))


class _BaseAprobacionTest(_BaseRevisionTest):
    """Formulario listo para aprobar: identidad validada, programa SIIS y una
    validación OK que corresponde al DNI y al programa actuales."""

    def setUp(self):
        super().setUp()
        self.siis = patch("programas.services.validacion_siis.validar_compatibilidad")
        self.validar_compatibilidad = self.siis.start()
        self.addCleanup(self.siis.stop)
        self.validar_compatibilidad.return_value = {
            "success": True,
            "compatible": True,
            "data": {
                "id_programa": 41,
                "id_consulta": "8ef13bfb-529a-4438-a8b4-dca8b238039a",
                "validaciones": {},
            },
        }
        self.ciudadano = Ciudadano.objects.create(
            dni="24459123", nombre="Persona", apellido="Compatible", fecha_nacimiento=date(1975, 2, 20), genero="F"
        )
        self.programa = ProgramaSiis.objects.create(nombre="Programa SIIS", siis_programa_id=41)
        self.seg_a.programa = self.programa
        self.seg_a.save(update_fields=["programa"])
        self.form_a.ciudadano = self.ciudadano
        self.form_a.validado_renaper = True
        self.form_a.save(update_fields=["ciudadano", "validado_renaper"])
        self.validacion = ValidacionSIS.objects.create(
            formulario=self.form_a,
            estado=ValidacionSIS.Estado.OK,
            id_programa=41,
            documento=self.ciudadano.dni,
            respuesta={"resultado": "OK", "apto": True},
            solicitado_por=self.admin,
        )
        self.client.force_login(self.coord_a)


class AprobarRechazarTests(_BaseAprobacionTest):
    def test_aprobar(self):
        resp = self.client.post(reverse("becas:formulario_aprobar", args=[self.form_a.pk]))
        self.assertEqual(resp.status_code, 302)
        self.form_a.refresh_from_db()
        self.assertEqual(self.form_a.estado, Formulario.Estado.APROBADO)
        self.validar_compatibilidad.assert_called_once()

    def test_no_aprueba_identidad_sin_validar(self):
        self.form_a.validado_renaper = False
        self.form_a.save(update_fields=["validado_renaper"])

        self.client.post(reverse("becas:formulario_aprobar", args=[self.form_a.pk]))

        self.form_a.refresh_from_db()
        self.assertEqual(self.form_a.estado, Formulario.Estado.ENVIADO)

    def test_aprobar_dispara_validacion_siis_aunque_no_haya_previa(self):
        self.validacion.delete()

        self.client.post(reverse("becas:formulario_aprobar", args=[self.form_a.pk]))

        self.form_a.refresh_from_db()
        self.assertEqual(self.form_a.estado, Formulario.Estado.APROBADO)
        self.assertTrue(self.form_a.validaciones_sis.filter(estado=ValidacionSIS.Estado.OK).exists())

    def test_no_aprueba_si_siis_rechazo(self):
        self.validar_compatibilidad.return_value = {
            "success": True,
            "compatible": False,
            "data": {"id_programa": 41, "validaciones": {"empleo_publico": "INCOMPATIBLE_PLANTA"}},
        }

        self.client.post(reverse("becas:formulario_aprobar", args=[self.form_a.pk]))

        self.form_a.refresh_from_db()
        self.assertEqual(self.form_a.estado, Formulario.Estado.ENVIADO)

    def test_no_aprueba_si_el_segmento_no_tiene_programa(self):
        self.seg_a.programa = None
        self.seg_a.save(update_fields=["programa"])

        self.client.post(reverse("becas:formulario_aprobar", args=[self.form_a.pk]))

        self.form_a.refresh_from_db()
        self.assertEqual(self.form_a.estado, Formulario.Estado.ENVIADO)

    def test_no_promueve_desde_lista_de_espera_si_siis_rechazo(self):
        entrada = ListaEspera.objects.create(formulario=self.form_a, segmento=self.seg_a, posicion=1)
        self.validacion.estado = ValidacionSIS.Estado.RECHAZADO
        self.validacion.save(update_fields=["estado"])

        self.client.post(reverse("becas:lista_espera_promover", args=[entrada.pk]))

        entrada.refresh_from_db()
        self.form_a.refresh_from_db()
        self.assertFalse(entrada.promovido)
        self.assertEqual(self.form_a.estado, Formulario.Estado.ENVIADO)

    def test_detalle_explica_por_que_la_aprobacion_esta_bloqueada(self):
        self.form_a.validado_renaper = False
        self.form_a.save(update_fields=["validado_renaper"])

        resp = self.client.get(reverse("becas:formulario_detalle", args=[self.form_a.pk]))

        self.assertContains(resp, "Aprobación bloqueada")
        self.assertContains(resp, "La identidad debe estar validada antes de aprobar")
        self.assertContains(resp, 'disabled aria-disabled="true"', html=False)

    def test_rechazar_sin_motivo_falla(self):
        self.client.post(reverse("becas:formulario_rechazar", args=[self.form_a.pk]), {"motivo": ""})
        self.form_a.refresh_from_db()
        self.assertEqual(self.form_a.estado, Formulario.Estado.ENVIADO)

    def test_rechazar_con_motivo(self):
        self.client.post(
            reverse("becas:formulario_rechazar", args=[self.form_a.pk]),
            {"motivo": "Documentación incompleta"},
        )
        self.form_a.refresh_from_db()
        self.assertEqual(self.form_a.estado, Formulario.Estado.RECHAZADO)
        self.assertEqual(self.form_a.motivo_rechazo, "Documentación incompleta")
        self.validar_compatibilidad.assert_called_once()

    def test_rechazar_registra_error_si_siis_no_responde(self):
        self.validar_compatibilidad.return_value = {"success": False, "error": "Timeout", "data": {}}

        self.client.post(
            reverse("becas:formulario_rechazar", args=[self.form_a.pk]),
            {"motivo": "Documentación incompleta"},
        )

        self.form_a.refresh_from_db()
        self.assertEqual(self.form_a.estado, Formulario.Estado.RECHAZADO)
        self.assertEqual(self.form_a.validaciones_sis.first().estado, ValidacionSIS.Estado.ERROR)

    def test_coordinador_puede_validar_siis_manualmente(self):
        response = self.client.post(reverse("becas:formulario_validar_sis", args=[self.form_a.pk]))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.form_a.validaciones_sis.count(), 2)
        self.assertEqual(
            str(self.form_a.validaciones_sis.first().id_consulta),
            "8ef13bfb-529a-4438-a8b4-dca8b238039a",
        )

    def test_coordinador_ve_boton_validar_siis(self):
        response = self.client.get(reverse("becas:formulario_detalle", args=[self.form_a.pk]))

        self.assertContains(response, "Reintentar validación SIIS")


class TransicionesRelevamientoTests(_BaseRevisionTest):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.coord_a)

    def test_iniciar_revision(self):
        self.client.post(reverse("becas:revision_iniciar", args=[self.rel_a.pk]))
        self.rel_a.refresh_from_db()
        self.assertEqual(self.rel_a.estado, Relevamiento.Estado.EN_REVISION)

    def test_terminar_bloqueado_con_pendientes(self):
        self.rel_a.estado = Relevamiento.Estado.EN_REVISION
        self.rel_a.save()
        self.client.post(reverse("becas:revision_terminar", args=[self.rel_a.pk]))
        self.rel_a.refresh_from_db()
        self.assertEqual(self.rel_a.estado, Relevamiento.Estado.EN_REVISION)  # sigue, hay pendiente

    def test_terminar_ok_sin_pendientes(self):
        self.rel_a.estado = Relevamiento.Estado.EN_REVISION
        self.rel_a.save()
        self.form_a.estado = Formulario.Estado.APROBADO
        self.form_a.save()
        self.client.post(reverse("becas:revision_terminar", args=[self.rel_a.pk]))
        self.rel_a.refresh_from_db()
        self.assertEqual(self.rel_a.estado, Relevamiento.Estado.TERMINADO)


class BeneficiarioScopingTests(_BaseRevisionTest):
    """El Coordinador tiene becas.beneficiario.editar, pero solo puede
    gestionar beneficiarios de los segmentos que tiene asignados (#78)."""

    def setUp(self):
        super().setUp()
        self.form_a.estado = Formulario.Estado.APROBADO
        self.form_a.save()
        self.form_b.estado = Formulario.Estado.APROBADO
        self.form_b.save()

    def test_coordinador_da_de_baja_beneficiario_de_su_segmento(self):
        self.client.force_login(self.coord_a)
        resp = self.client.post(reverse("becas:beneficiario_dar_baja", args=[self.form_a.pk]))
        self.assertEqual(resp.status_code, 302)
        self.form_a.refresh_from_db()
        self.assertEqual(self.form_a.estado, Formulario.Estado.BAJA)

    def test_coordinador_no_da_de_baja_beneficiario_de_otro_segmento(self):
        self.client.force_login(self.coord_a)
        resp = self.client.post(reverse("becas:beneficiario_dar_baja", args=[self.form_b.pk]))
        self.assertEqual(resp.status_code, 403)
        self.form_b.refresh_from_db()
        self.assertEqual(self.form_b.estado, Formulario.Estado.APROBADO)

    def test_admin_da_de_baja_beneficiario_de_cualquier_segmento(self):
        self.client.force_login(self.admin)
        resp = self.client.post(reverse("becas:beneficiario_dar_baja", args=[self.form_b.pk]))
        self.assertEqual(resp.status_code, 302)
        self.form_b.refresh_from_db()
        self.assertEqual(self.form_b.estado, Formulario.Estado.BAJA)


class _BaseAvisoResolucionTest(_BaseAprobacionTest):
    """``rel_a`` es territorial y con el toggle encendido: el escenario que
    habilita el Cambio 44 (antes el toggle solo existía en los públicos)."""

    def setUp(self):
        super().setUp()
        # El aviso es opt-in: sin el toggle el servicio corta antes de armar nada.
        self.rel_a.confirmar_por_email = True
        self.rel_a.save(update_fields=["confirmar_por_email"])


class AvisoResolucionCableadoTests(_BaseAvisoResolucionTest):
    """Cada vista avisa con el desenlace que realmente ocurrió (Cambio 44)."""

    def _ocupar_todo_el_cupo(self):
        """Deja el segmento sin cupo para que Aprobar caiga en lista de espera."""
        self.seg_a.cupo_maximo = 1
        self.seg_a.save(update_fields=["cupo_maximo"])
        Formulario.objects.create(
            relevamiento=self.rel_a,
            celular="3624300300",
            email_contacto="ocupa@b.com",
            estado=Formulario.Estado.APROBADO,
        )

    @patch("programas.views.revision.enviar_aviso_resolucion")
    def test_aprobar_con_cupo_avisa_aprobado(self, aviso):
        self.client.post(reverse("becas:formulario_aprobar", args=[self.form_a.pk]))

        self.form_a.refresh_from_db()
        self.assertEqual(self.form_a.estado, Formulario.Estado.APROBADO)
        aviso.assert_called_once()
        self.assertEqual(aviso.call_args.args[0].pk, self.form_a.pk)
        self.assertEqual(aviso.call_args.args[1], "aprobado")

    @patch("programas.views.revision.enviar_aviso_resolucion")
    def test_aprobar_sin_cupo_avisa_lista_de_espera(self, aviso):
        self._ocupar_todo_el_cupo()

        self.client.post(reverse("becas:formulario_aprobar", args=[self.form_a.pk]))

        self.form_a.refresh_from_db()
        # Sin cupo el formulario sigue ENVIADO: avisar «aprobado» sería mentirle.
        self.assertEqual(self.form_a.estado, Formulario.Estado.ENVIADO)
        self.assertTrue(ListaEspera.objects.filter(formulario=self.form_a, promovido=False).exists())
        aviso.assert_called_once()
        self.assertEqual(aviso.call_args.args[1], "lista_espera")

    @patch("programas.views.revision.enviar_aviso_resolucion")
    def test_aprobacion_bloqueada_no_avisa(self, aviso):
        self.form_a.validado_renaper = False
        self.form_a.save(update_fields=["validado_renaper"])

        self.client.post(reverse("becas:formulario_aprobar", args=[self.form_a.pk]))

        self.form_a.refresh_from_db()
        self.assertEqual(self.form_a.estado, Formulario.Estado.ENVIADO)
        aviso.assert_not_called()

    @patch("programas.views.revision.enviar_aviso_resolucion")
    def test_rechazar_avisa_con_el_motivo_textual(self, aviso):
        motivo = "Falta el certificado de alumno regular."

        self.client.post(reverse("becas:formulario_rechazar", args=[self.form_a.pk]), {"motivo": motivo})

        self.form_a.refresh_from_db()
        self.assertEqual(self.form_a.estado, Formulario.Estado.RECHAZADO)
        aviso.assert_called_once()
        self.assertEqual(aviso.call_args.args[0].pk, self.form_a.pk)
        self.assertEqual(aviso.call_args.args[1], "rechazado")
        self.assertEqual(aviso.call_args.kwargs["motivo"], motivo)

    @patch("programas.views.revision.enviar_aviso_resolucion")
    def test_rechazo_sin_motivo_no_avisa(self, aviso):
        self.client.post(reverse("becas:formulario_rechazar", args=[self.form_a.pk]), {"motivo": ""})

        self.form_a.refresh_from_db()
        self.assertEqual(self.form_a.estado, Formulario.Estado.ENVIADO)
        aviso.assert_not_called()

    @patch("programas.views.cupo.enviar_aviso_resolucion")
    def test_promover_desde_lista_de_espera_avisa_promovido(self, aviso):
        entrada = ListaEspera.objects.create(formulario=self.form_a, segmento=self.seg_a, posicion=1)

        self.client.post(reverse("becas:lista_espera_promover", args=[entrada.pk]))

        self.form_a.refresh_from_db()
        self.assertEqual(self.form_a.estado, Formulario.Estado.APROBADO)
        aviso.assert_called_once()
        self.assertEqual(aviso.call_args.args[0].pk, self.form_a.pk)
        self.assertEqual(aviso.call_args.args[1], "promovido")

    @patch("programas.views.cupo.enviar_aviso_resolucion")
    def test_promocion_que_no_prospera_no_avisa(self, aviso):
        entrada = ListaEspera.objects.create(formulario=self.form_a, segmento=self.seg_a, posicion=1, promovido=True)

        self.client.post(reverse("becas:lista_espera_promover", args=[entrada.pk]))

        aviso.assert_not_called()

    @patch("programas.views.revision.enviar_aviso_resolucion")
    def test_validar_siis_no_avisa(self, aviso):
        """La prevalidación (Cambio 34) no resuelve el caso: no es un desenlace."""
        self.client.post(reverse("becas:formulario_validar_sis", args=[self.form_a.pk]))

        aviso.assert_not_called()


class ResolucionCoherenteTests(_BaseAvisoResolucionTest):
    """Los tres huecos que destapó la revisión del Cambio 44."""

    def test_no_se_puede_rechazar_un_formulario_ya_resuelto(self):
        """Sin la guarda, un doble clic rechazaba dos veces y mandaba dos correos."""
        self.form_a.estado = Formulario.Estado.APROBADO
        self.form_a.save(update_fields=["estado"])

        with patch("programas.views.revision.enviar_aviso_resolucion") as aviso:
            self.client.post(
                reverse("becas:formulario_rechazar", args=[self.form_a.pk]),
                {"motivo": "no corresponde"},
            )

        self.form_a.refresh_from_db()
        self.assertEqual(self.form_a.estado, Formulario.Estado.APROBADO)
        aviso.assert_not_called()

    @patch("programas.views.revision.enviar_aviso_resolucion")
    def test_el_rechazo_de_una_carga_duplicada_no_avisa(self, aviso):
        """Las dos cargas son de la misma persona: rechazar el duplicado es
        limpieza, no la resolución de su inscripción. La que sobrevive avisa
        cuando se resuelva de verdad."""
        previo = Formulario.objects.create(
            relevamiento=self.rel_a,
            celular="3624300300",
            email_contacto="mismo@b.com",
            estado=Formulario.Estado.ENVIADO,
        )
        self.form_a.conflicto_duplicado = True
        self.form_a.duplicado_de = previo
        self.form_a.save(update_fields=["conflicto_duplicado", "duplicado_de"])

        self.client.post(
            reverse("becas:formulario_resolver_duplicado", args=[self.form_a.pk]),
            {"decision": "conservar_previo"},
        )

        self.form_a.refresh_from_db()
        self.assertEqual(self.form_a.estado, Formulario.Estado.RECHAZADO)
        aviso.assert_not_called()

    @patch("programas.views.cupo.enviar_aviso_resolucion")
    def test_el_alta_manual_a_lista_de_espera_avisa(self, aviso):
        """Mismo desenlace que aprobar sin cupo, mismo aviso."""
        self.client.post(reverse("becas:formulario_agregar_espera", args=[self.form_a.pk]))

        aviso.assert_called_once()
        self.assertEqual(aviso.call_args.args[1], "lista_espera")


class AvisoResolucionEnvioRealTests(_BaseAvisoResolucionTest):
    """El correo se arma y sale de verdad, y nunca rompe la acción del técnico:
    cuando la vista llama al servicio, la aprobación o el rechazo ya están
    commiteados y no hay forma de retractarlos (criterio del Cambio 41).

    Estas pruebas llaman a la vista con ``RequestFactory`` en vez de
    ``self.client``: bajo Python 3.14 + Django 4.2 el test client instrumenta
    el render de plantillas y revienta en ``Context.__copy__``, lo que alcanza
    también al ``render_to_string`` del correo y dejaría el ``outbox`` vacío
    por un motivo ajeno al cambio. Es el mismo desvío que hace
    ``test_avisos_resolucion`` al ejercitar el servicio suelto.
    """

    def _llamar(self, vista, pk, **data):
        request = RequestFactory().post("/", data)
        request.user = self.coord_a
        request.session = self.client.session
        request._messages = FallbackStorage(request)
        return vista(request, pk)

    def test_territorial_con_el_toggle_encendido_manda_el_aviso(self):
        """La regresión que habilita el cambio: ``rel_a`` no es público."""
        self.assertFalse(self.rel_a.es_publico)

        resp = self._llamar(formulario_aprobar, self.form_a.pk)

        self.assertEqual(resp.status_code, 302)
        self.form_a.refresh_from_db()
        self.assertEqual(self.form_a.estado, Formulario.Estado.APROBADO)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["a@b.com"])
        self.assertEqual(mail.outbox[0].subject, "Tu inscripción fue aprobada — Conv A")

    def test_el_rechazo_manda_el_motivo_textual(self):
        motivo = "Falta el certificado de alumno regular."

        self._llamar(formulario_rechazar, self.form_a.pk, motivo=motivo)

        self.form_a.refresh_from_db()
        self.assertEqual(self.form_a.estado, Formulario.Estado.RECHAZADO)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "Novedades sobre tu inscripción — Conv A")
        self.assertIn(motivo, mail.outbox[0].body)

    def test_la_promocion_manda_el_aviso(self):
        entrada = ListaEspera.objects.create(formulario=self.form_a, segmento=self.seg_a, posicion=1)

        self._llamar(promover_lista_espera_view, entrada.pk)

        entrada.refresh_from_db()
        self.assertTrue(entrada.promovido)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "Tu inscripción fue aprobada — Conv A")
        self.assertIn("Se liberó un lugar", mail.outbox[0].body)

    def test_toggle_apagado_no_manda_nada(self):
        self.rel_a.confirmar_por_email = False
        self.rel_a.save(update_fields=["confirmar_por_email"])

        self._llamar(formulario_aprobar, self.form_a.pk)

        self.form_a.refresh_from_db()
        self.assertEqual(self.form_a.estado, Formulario.Estado.APROBADO)
        self.assertEqual(len(mail.outbox), 0)

    def test_smtp_caido_no_voltea_la_aprobacion(self):
        with patch(
            "programas.services.avisos_resolucion.EmailMultiAlternatives.send",
            side_effect=OSError("smtp caído"),
        ):
            with self.assertLogs("programas.services.avisos_resolucion", level="ERROR"):
                resp = self._llamar(formulario_aprobar, self.form_a.pk)

        self.assertEqual(resp.status_code, 302)
        self.form_a.refresh_from_db()
        self.assertEqual(self.form_a.estado, Formulario.Estado.APROBADO)
        self.assertEqual(len(mail.outbox), 0)

    def test_smtp_caido_no_voltea_el_rechazo(self):
        with patch(
            "programas.services.avisos_resolucion.EmailMultiAlternatives.send",
            side_effect=OSError("smtp caído"),
        ):
            with self.assertLogs("programas.services.avisos_resolucion", level="ERROR"):
                resp = self._llamar(formulario_rechazar, self.form_a.pk, motivo="Documentación incompleta")

        self.assertEqual(resp.status_code, 302)
        self.form_a.refresh_from_db()
        self.assertEqual(self.form_a.estado, Formulario.Estado.RECHAZADO)
        self.assertEqual(self.form_a.motivo_rechazo, "Documentación incompleta")

    def test_smtp_caido_no_voltea_la_promocion(self):
        entrada = ListaEspera.objects.create(formulario=self.form_a, segmento=self.seg_a, posicion=1)

        with patch(
            "programas.services.avisos_resolucion.EmailMultiAlternatives.send",
            side_effect=OSError("smtp caído"),
        ):
            with self.assertLogs("programas.services.avisos_resolucion", level="ERROR"):
                resp = self._llamar(promover_lista_espera_view, entrada.pk)

        self.assertEqual(resp.status_code, 302)
        entrada.refresh_from_db()
        self.form_a.refresh_from_db()
        self.assertTrue(entrada.promovido)
        self.assertEqual(self.form_a.estado, Formulario.Estado.APROBADO)

    def test_una_plantilla_rota_tampoco_voltea_la_aprobacion(self):
        """El armado del correo está dentro del mismo blindaje que el envío: si
        quedara afuera, un error de plantilla daría un 500 sobre una aprobación
        ya guardada, que es justo lo que el cambio se propone evitar."""
        with patch(
            "programas.services.avisos_resolucion.render_to_string",
            side_effect=TemplateDoesNotExist("resolucion_body.txt"),
        ):
            with self.assertLogs("programas.services.avisos_resolucion", level="ERROR"):
                resp = self._llamar(formulario_aprobar, self.form_a.pk)

        self.assertEqual(resp.status_code, 302)
        self.form_a.refresh_from_db()
        self.assertEqual(self.form_a.estado, Formulario.Estado.APROBADO)
        self.assertEqual(len(mail.outbox), 0)
