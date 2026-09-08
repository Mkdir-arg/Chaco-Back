"""Presentación de los campos selector: lista o buscador con píldoras (Cambio 56).

Cubre las dos puntas que quedan en este repo: el configurador de Becas —los dos
lugares donde se define un requisito— y la definición que consumen el portal y
la app de campo. El control del portal se prueba en
``portal/tests/test_inscripcion_envio.py``.
"""

from datetime import date, timedelta

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from programas.forms import PreguntaGlobalForm, RequisitoNativoForm
from programas.models import (
    Convocatoria,
    PreguntaGlobal,
    PresentacionCampo,
    Relevamiento,
    RequisitoNativo,
    Segmento,
    TipoCampo,
)
from programas.services.becas import definicion_formulario


class PresentacionModeloTests(TestCase):
    def test_default_es_lista(self):
        """Nada de lo ya configurado cambia de aspecto por el alta del campo."""
        pregunta = PreguntaGlobal.objects.create(texto="Nivel educativo", tipo=TipoCampo.SELECTOR)
        requisito = RequisitoNativo.objects.create(texto="Localidad", tipo=TipoCampo.SELECTOR)
        self.assertEqual(pregunta.presentacion, PresentacionCampo.LISTA)
        self.assertEqual(requisito.presentacion, PresentacionCampo.LISTA)

    def test_selectores_son_los_dos_tipos_con_opciones(self):
        self.assertEqual(TipoCampo.selectores(), (TipoCampo.SELECTOR, TipoCampo.SELECTOR_MULTIPLE))


class PresentacionFormularioTests(TestCase):
    """El ajuste se ofrece en los dos configuradores y se normaliza solo."""

    def setUp(self):
        self.segmento = Segmento.objects.create(nombre="Seg", cupo_maximo=100)

    def test_los_dos_formularios_ofrecen_el_campo(self):
        for form in (RequisitoNativoForm(), PreguntaGlobalForm()):
            with self.subTest(form=type(form).__name__):
                campo = form.fields["presentacion"]
                etiquetas = [str(etiqueta) for _, etiqueta in campo.choices]
                self.assertIn("Lista de opciones", etiquetas)
                self.assertIn("Buscador con píldoras", etiquetas)

    def test_requisito_selector_guarda_buscador(self):
        form = RequisitoNativoForm(
            {
                "texto": "Localidad",
                "tipo": TipoCampo.SELECTOR,
                "presentacion": PresentacionCampo.BUSCADOR,
                "obligatorio": "True",
                "opciones_texto": "Resistencia\nBarranqueras\nFontana",
            },
            segmento=self.segmento,
        )
        self.assertTrue(form.is_valid(), form.errors)
        requisito = form.save(commit=False)
        self.assertEqual(requisito.presentacion, PresentacionCampo.BUSCADOR)

    def test_pregunta_selector_multiple_guarda_buscador(self):
        form = PreguntaGlobalForm(
            {
                "texto": "Prestaciones que recibís",
                "tipo": TipoCampo.SELECTOR_MULTIPLE,
                "presentacion": PresentacionCampo.BUSCADOR,
                "obligatorio": "on",
                "activo": "on",
                "opciones_texto": "AUH\nTarjeta Alimentar\nPensión",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save(commit=False).presentacion, PresentacionCampo.BUSCADOR)

    def test_tipo_sin_opciones_normaliza_a_lista(self):
        """Un texto o una fecha no tienen opciones: guardar BUSCADOR ahí sería
        un dato que nadie lee. Se corrige en silencio, no se rechaza el alta."""
        form = RequisitoNativoForm(
            {
                "texto": "Observaciones",
                "tipo": TipoCampo.STRING,
                "presentacion": PresentacionCampo.BUSCADOR,
                "obligatorio": "True",
            },
            segmento=self.segmento,
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save(commit=False).presentacion, PresentacionCampo.LISTA)

    def test_archivo_tambien_normaliza(self):
        form = PreguntaGlobalForm(
            {
                "texto": "Certificado",
                "tipo": TipoCampo.ARCHIVO,
                "presentacion": PresentacionCampo.BUSCADOR,
                "obligatorio": "on",
                "activo": "on",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save(commit=False).presentacion, PresentacionCampo.LISTA)


class PresentacionAltaBackofficeTests(TestCase):
    """El alta real por pantalla, con el permiso puesto."""

    def setUp(self):
        self.admin = User.objects.create_user("admin_pres", password="x", is_staff=True, is_superuser=True)
        Group.objects.get_or_create(name="Administrador")
        self.client.force_login(self.admin)
        self.segmento = Segmento.objects.create(nombre="Seg", cupo_maximo=100)

    def test_alta_de_requisito_con_buscador(self):
        respuesta = self.client.post(
            reverse("becas:requisito_crear", args=[self.segmento.pk]),
            {
                "texto": "Localidad",
                "tipo": TipoCampo.SELECTOR,
                "presentacion": PresentacionCampo.BUSCADOR,
                "orden": 1,
                "obligatorio": "True",
                "opciones_texto": "Resistencia\nBarranqueras",
            },
        )
        self.assertEqual(respuesta.status_code, 302)
        requisito = RequisitoNativo.objects.get(texto="Localidad")
        self.assertEqual(requisito.presentacion, PresentacionCampo.BUSCADOR)
        self.assertEqual(requisito.opciones, ["Resistencia", "Barranqueras"])

    def test_alta_de_pregunta_con_buscador(self):
        respuesta = self.client.post(
            reverse("becas:pregunta_crear"),
            {
                "texto": "Nivel educativo",
                "tipo": TipoCampo.SELECTOR,
                "presentacion": PresentacionCampo.BUSCADOR,
                "orden": 1,
                "obligatorio": "on",
                "activo": "on",
                "opciones_texto": "Primario\nSecundario\nTerciario",
            },
        )
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(
            PreguntaGlobal.objects.get(texto="Nivel educativo").presentacion,
            PresentacionCampo.BUSCADOR,
        )

    def test_el_select_del_configurador_se_renderiza_con_las_dos_opciones(self):
        """El template pinta todos los fields con ``_field.html``: alcanza con
        que el widget del campo salga bien."""
        html = str(RequisitoNativoForm(segmento=self.segmento)["presentacion"])
        self.assertIn('value="LISTA"', html)
        self.assertIn('value="BUSCADOR"', html)
        self.assertIn("nodo-field", html)


class PresentacionDefinicionTests(TestCase):
    """La definición es una sola para el portal y la app (RN-P12): el ajuste
    viaja ahí, no en una estructura paralela."""

    def setUp(self):
        self.segmento = Segmento.objects.create(nombre="Seg", cupo_maximo=100)
        self.convocatoria = Convocatoria.objects.create(
            nombre="Becas 2026",
            segmento=self.segmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        self.relevamiento = Relevamiento.objects.create(
            convocatoria=self.convocatoria,
            tipo=Relevamiento.Tipo.PUBLICO,
            fecha_asignada=timezone.now() - timedelta(days=1),
            fecha_hasta=timezone.now() + timedelta(days=10),
        )

    def test_definicion_expone_la_presentacion_de_globales_y_requisitos(self):
        PreguntaGlobal.objects.create(
            texto="Nivel educativo",
            tipo=TipoCampo.SELECTOR,
            opciones=["Primario", "Secundario"],
            presentacion=PresentacionCampo.BUSCADOR,
            orden=1,
        )
        RequisitoNativo.objects.create(
            texto="Localidad",
            tipo=TipoCampo.SELECTOR,
            opciones=["Resistencia"],
            segmento=self.segmento,
            presentacion=PresentacionCampo.BUSCADOR,
            orden=1,
        )
        PreguntaGlobal.objects.create(texto="Observaciones", tipo=TipoCampo.STRING, orden=2)

        definicion = definicion_formulario(self.relevamiento)

        globales = {campo["texto"]: campo["presentacion"] for campo in definicion["globales"]}
        requisitos = {campo["texto"]: campo["presentacion"] for campo in definicion["requisitos"]}
        self.assertEqual(globales["Nivel educativo"], PresentacionCampo.BUSCADOR)
        self.assertEqual(globales["Observaciones"], PresentacionCampo.LISTA)
        self.assertEqual(requisitos["Localidad"], PresentacionCampo.BUSCADOR)
