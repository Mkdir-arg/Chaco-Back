"""Saneo del HTML de la campaña y texto plano (RNF-007-03, RN-007-07/08/13)."""

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase

from notificaciones.services import html as servicio
from notificaciones.tests.utils import html


class SanitizarTests(SimpleTestCase):
    def test_saca_script_eventos_iframe_form_y_javascript(self):
        original = (
            '<p onclick="alert(1)">Hola</p><script>alert(2)</script>'
            '<iframe src="https://x"></iframe><object data="x"></object><embed src="x">'
            '<form action="https://x"><input name="dni"></form>'
            '<a href="javascript:alert(3)">mal</a><a href="https://ok.com">bien</a>'
        )
        limpio = servicio.sanitizar(original).lower()
        for prohibido in ("<script", "alert(", "onclick", "<iframe", "<object", "<embed", "<form", "<input", "javascript:"):
            self.assertNotIn(prohibido, limpio)
        self.assertIn('href="https://ok.com"', limpio)
        self.assertIn("hola", limpio)

    def test_conserva_estilos_tablas_e_imagenes_https(self):
        original = (
            "<html><head><style>p{color:red}</style><title>T</title></head><body>"
            '<table width="600" bgcolor="#fff"><tr><td style="padding:8px">x</td></tr></table>'
            '<img src="https://cdn.ejemplo.com/logo.png" alt="Logo" width="120"></body></html>'
        )
        limpio = servicio.sanitizar(original)
        self.assertIn("<style>p{color:red}</style>", limpio)
        self.assertIn('style="padding:8px"', limpio)
        self.assertIn('src="https://cdn.ejemplo.com/logo.png"', limpio)
        self.assertNotIn("<title", limpio)

    def test_quita_meta_refresh_y_base(self):
        limpio = servicio.sanitizar('<meta http-equiv="refresh" content="0;url=https://x"><base href="https://x"><p>a</p>')
        self.assertNotIn("<meta", limpio)
        self.assertNotIn("<base", limpio)

    def test_cuenta_lo_que_quito_y_las_imagenes_no_visibles(self):
        original = (
            '<script>1</script><p onmouseover="x()">a</p>'
            '<img src="cid:logo"><img src="img/rel.png"><img src="https://ok/a.png"><img src="data:image/png;base64,AA">'
        )
        self.assertEqual(servicio.contar_quitados(original), 2)
        self.assertEqual(servicio.contar_imagenes_no_visibles(original), 2)

    def test_texto_plano_derivado(self):
        texto = servicio.a_texto(
            servicio.sanitizar(
                "<style>p{x:y}</style><h1>Título</h1><p>Hola &amp; chau</p>"
                '<p><a href="https://ejemplo.com/inscribirme">Inscribirme</a></p>'
            )
        )
        self.assertIn("Título", texto)
        self.assertIn("Hola & chau", texto)
        self.assertIn("Inscribirme (https://ejemplo.com/inscribirme)", texto)
        self.assertNotIn("<", texto)
        self.assertNotIn("x:y", texto)


class LeerHtmlTests(SimpleTestCase):
    def test_extension(self):
        with self.assertRaisesMessage(ValidationError, ".html"):
            servicio.leer_html(SimpleUploadedFile("correo.txt", b"<p>x</p>"))

    def test_htm_vale(self):
        self.assertEqual(servicio.leer_html(html("<p>x</p>", nombre="c.htm")), "<p>x</p>")

    def test_tamano(self):
        archivo = SimpleUploadedFile("c.html", b"a" * (servicio.HTML_MAX_BYTES + 1))
        with self.assertRaisesMessage(ValidationError, "1 MB"):
            servicio.leer_html(archivo)

    def test_utf8(self):
        with self.assertRaisesMessage(ValidationError, "UTF-8"):
            servicio.leer_html(SimpleUploadedFile("c.html", "<p>Ñandú</p>".encode("latin-1")))

    def test_bom_utf8_aceptado(self):
        self.assertEqual(servicio.leer_html(SimpleUploadedFile("c.html", "﻿<p>ñ</p>".encode("utf-8"))), "<p>ñ</p>")

    def test_procesar_rechaza_lo_que_queda_vacio(self):
        with self.assertRaisesMessage(ValidationError, "quedó vacío"):
            servicio.procesar(html("<script>alert(1)</script>"))
