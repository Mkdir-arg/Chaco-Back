"""SIIS-15 y SIIS-16 · El comprobante no puede voltear la inscripción, y un
adjunto anónimo se valida por lo que es y no por cómo se llama.

* **SIIS-15:** el `render_to_string` de las dos plantillas del correo y el armado
  del `EmailMultiAlternatives` estaban **fuera** del `try` que protege el envío.
  Un error de plantilla —una variable renombrada, un `{% url %}` que dejó de
  existir— daba 500 **después** de commiteada la inscripción: la persona
  reintentaba, la idempotencia por `client_uuid` devolvía `creado=False` y el
  comprobante no llegaba nunca. `avisos_resolucion.py` ya lo tenía adentro.
* **SIIS-16:** `_validar_archivo` miraba solo la extensión. Un `.pdf` con HTML
  adentro se guardaba en `media/` y se servía después desde el backoffice.
"""

from unittest.mock import patch

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.forms import ValidationError
from django.test import SimpleTestCase

from portal.forms.inscripcion import _validar_archivo
from portal.tests.test_inscripcion_envio import _BasePaso2Test
from programas.models import Formulario
from programas.services.inscripcion_publica import enviar_confirmacion_inscripcion

PDF = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\n"
PNG = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
JPG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00"


class ComprobanteQueNoTumbaLaInscripcionTests(_BasePaso2Test):
    """SIIS-15: el comprobante nunca rompe la inscripción, ni al renderizar."""

    def _formulario(self):
        self.relevamiento.confirmar_por_email = True
        self.relevamiento.save(update_fields=["confirmar_por_email"])
        return Formulario.objects.create(
            relevamiento=self.relevamiento,
            celular="3624123456",
            email_contacto="maria.gomez@correo.com",
            datos_identificacion={"dni": "30123456"},
        )

    def test_un_error_de_plantilla_no_tumba_el_envio(self):
        formulario = self._formulario()

        with patch(
            "programas.services.inscripcion_publica.render_to_string",
            side_effect=Exception("la plantilla no existe"),
        ):
            enviado = enviar_confirmacion_inscripcion(formulario)

        self.assertFalse(enviado)
        self.assertEqual(len(mail.outbox), 0)

    def test_un_error_de_plantilla_queda_logueado(self):
        formulario = self._formulario()

        with patch(
            "programas.services.inscripcion_publica.render_to_string",
            side_effect=Exception("la plantilla no existe"),
        ):
            with self.assertLogs("programas.services.inscripcion_publica", level="ERROR") as registro:
                enviar_confirmacion_inscripcion(formulario)

        self.assertIn(str(formulario.pk), "\n".join(registro.output))

    def test_con_las_plantillas_sanas_sigue_mandando(self):
        """Pin del camino feliz: el `try` no se tragó el envío."""
        self.assertTrue(enviar_confirmacion_inscripcion(self._formulario()))
        self.assertEqual(len(mail.outbox), 1)


class AdjuntoAnonimoPorFirmaTests(SimpleTestCase):
    """SIIS-16: la extensión la elige quien sube el archivo; la firma, no."""

    def _archivo(self, nombre, contenido):
        return SimpleUploadedFile(nombre, contenido)

    def test_un_pdf_que_adentro_es_html_se_rechaza(self):
        with self.assertRaises(ValidationError) as error:
            _validar_archivo(self._archivo("certificado.pdf", b"<html><body>hola</body></html>"))

        self.assertIn("no es un", str(error.exception))

    def test_un_png_que_adentro_es_un_script_se_rechaza(self):
        with self.assertRaises(ValidationError):
            _validar_archivo(self._archivo("foto.png", b"<?php system($_GET['c']); ?>"))

    def test_una_extension_que_no_coincide_con_el_contenido_se_rechaza(self):
        """Un JPG real subido como `.pdf`: la firma y la extensión tienen que hablar
        de lo mismo, o el backoffice lo abre esperando otra cosa."""
        with self.assertRaises(ValidationError):
            _validar_archivo(self._archivo("documento.pdf", JPG))

    def test_los_tres_formatos_de_verdad_pasan(self):
        for nombre, contenido in (("c.pdf", PDF), ("f.png", PNG), ("f.jpg", JPG), ("f.jpeg", JPG)):
            with self.subTest(nombre=nombre):
                _validar_archivo(self._archivo(nombre, contenido))

    def test_la_extension_sigue_filtrando_antes_que_la_firma(self):
        with self.assertRaises(ValidationError) as error:
            _validar_archivo(self._archivo("script.exe", PDF))

        self.assertIn("JPG, PNG o PDF", str(error.exception))

    def test_el_tope_de_tamano_sigue_vigente(self):
        grande = self._archivo("c.pdf", PDF + b"0" * (5 * 1024 * 1024))

        with self.assertRaises(ValidationError) as error:
            _validar_archivo(grande)

        self.assertIn("5 MB", str(error.exception))

    def test_un_archivo_mas_corto_que_la_firma_no_revienta(self):
        with self.assertRaises(ValidationError):
            _validar_archivo(self._archivo("c.pdf", b"%P"))
