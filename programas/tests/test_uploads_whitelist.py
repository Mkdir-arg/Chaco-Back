"""Lista blanca y techo de tamaño en los uploads del backoffice (SEC-15, SEC-31).

Hasta este PR, el campo ARCHIVO del **F-00** y la **documentación respaldatoria**
de una solicitud de merendero eran `FileField` pelados: cualquier extensión, de
cualquier peso. Un `.html` con `<script>` quedaba en `media/` y se servía
*same-origin* —en DEV por nginx, y en ECOM `django.views.static.serve` infiere
`text/html` y no manda `attachment`—, así que el XSS corría en el origen del
sitio. Requiere un usuario interno (`dispositivo.admitir` o `merendero.crear`),
por eso es MEDIA y no ALTA, pero el archivo lo mira después cualquiera.

La lista blanca es la que el repo ya usa para los adjuntos de la app de campo
(Cambio 46), movida a `core/validators.py` para que haya una sola:
``.jpg .jpeg .png .pdf .heic .heif .webp`` y 5 MB. **D-15 = no hacen falta
`.doc`/`.docx`**: PDF e imagen. Para PDF, PNG y JPG se mira además la firma de
los primeros bytes, que sí es del contenido y no del nombre.

El padrón (SEC-31) tenía un tope de 2 MB **sobre el .xlsx comprimido**: un zip
de 1 MB que descomprime a 2 GB lo armaba openpyxl en memoria. Ahora se suman los
tamaños declarados en el índice del zip antes de abrirlo y se corta la lectura
por cantidad de filas.
"""

import io
import zipfile

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from core.validators import ADJUNTO_EXTENSIONES, ADJUNTO_MAX_BYTES
from programas.forms import F00DinamicoForm, SolicitudMerenderoForm
from programas.models import CampoTipoDispositivo, TipoCampo, TipoDispositivo

PDF = b"%PDF-1.4 contenido real"


def subido(nombre, contenido=PDF, tipo="application/pdf"):
    return SimpleUploadedFile(nombre, contenido, content_type=tipo)


class ListaBlancaCompartidaTests(TestCase):
    """Una sola lista: la que ya acepta la app de campo (Cambio 46)."""

    def test_no_entra_contenido_interpretable(self):
        for extension in (".html", ".htm", ".svg", ".js", ".xml", ".doc", ".docx"):
            self.assertNotIn(extension, ADJUNTO_EXTENSIONES, extension)

    def test_entran_los_formatos_del_tramite(self):
        for extension in (".pdf", ".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp"):
            self.assertIn(extension, ADJUNTO_EXTENSIONES, extension)

    def test_la_api_de_campo_usa_exactamente_la_misma_lista(self):
        """Angostarla acá le rompe el trabajo al territorial: ante un 4xx la app
        marca la operación `FAILED_PERMANENT` y no la reintenta nunca."""
        from programas.api import serializers

        self.assertEqual(serializers.ADJUNTO_EXTENSIONES, ADJUNTO_EXTENSIONES)
        self.assertEqual(serializers.ADJUNTO_MAX_BYTES, ADJUNTO_MAX_BYTES)


class SolicitudMerenderoUploadTests(TestCase):
    """PoC invertida: `SolicitudMerenderoForm` aceptaba `x.html`."""

    def _form(self, archivo):
        return SolicitudMerenderoForm(
            data={"codigo": "", "nombre": "M"},
            files={"documentacion": archivo},
            validar_completitud=False,
        )

    def test_merendero_rechaza_html(self):
        form = self._form(subido("x.html", b"<script>alert(1)</script>", "text/html"))

        self.assertFalse(form.is_valid())
        self.assertIn("documentacion", form.errors)

    def test_merendero_rechaza_svg(self):
        form = self._form(subido("x.svg", b"<svg onload=alert(1)>", "image/svg+xml"))

        self.assertIn("documentacion", self._errores(form))

    def test_merendero_rechaza_un_pdf_que_no_es_pdf(self):
        """La extensión la elige quien sube; la firma es del contenido."""
        form = self._form(subido("trampa.pdf", b"<html><script>alert(1)</script>"))

        self.assertIn("documentacion", self._errores(form))

    def test_merendero_rechaza_el_archivo_mayor_al_tope(self):
        form = self._form(subido("grande.pdf", PDF + b"\x00" * ADJUNTO_MAX_BYTES))

        self.assertIn("documentacion", self._errores(form))

    def test_merendero_acepta_el_pdf_de_siempre(self):
        form = self._form(subido("acta.pdf"))

        self.assertNotIn("documentacion", self._errores(form))

    @staticmethod
    def _errores(form):
        form.is_valid()
        return form.errors


class F00UploadTests(TestCase):
    """El campo ARCHIVO del F-00 dinámico."""

    def setUp(self):
        self.tipo = TipoDispositivo.objects.create(codigo="F00", nombre="Formulario")
        self.campo = CampoTipoDispositivo.objects.create(
            tipo_dispositivo=self.tipo,
            seccion="Datos",
            nombre="Constancia",
            tipo_campo=TipoCampo.ARCHIVO,
            obligatorio=True,
            orden=1,
        )
        self.nombre = F00DinamicoForm.nombre_campo(self.campo)

    def _form(self, archivo):
        return F00DinamicoForm({}, {self.nombre: archivo}, tipo_dispositivo=self.tipo)

    def test_f00_rechaza_svg(self):
        form = self._form(subido("x.svg", b"<svg onload=alert(1)>", "image/svg+xml"))

        self.assertFalse(form.is_valid())
        self.assertIn(self.nombre, form.errors)

    def test_f00_rechaza_html(self):
        form = self._form(subido("x.html", b"<script>alert(1)</script>", "text/html"))

        form.is_valid()
        self.assertIn(self.nombre, form.errors)

    def test_f00_rechaza_el_archivo_mayor_al_tope(self):
        form = self._form(subido("grande.pdf", PDF + b"\x00" * ADJUNTO_MAX_BYTES))

        form.is_valid()
        self.assertIn(self.nombre, form.errors)

    def test_f00_acepta_una_foto_del_telefono(self):
        form = self._form(subido("constancia.jpg", b"\xff\xd8\xff\xe0contenido", "image/jpeg"))

        form.is_valid()
        self.assertNotIn(self.nombre, form.errors)


class HistorialContactoUploadTests(TestCase):
    """`HistorialContacto.archivo_adjunto`: mismo validador, por el modelo."""

    def test_el_campo_lleva_el_validador(self):
        from core.validators import validar_adjunto
        from legajos.models import HistorialContacto

        campo = HistorialContacto._meta.get_field("archivo_adjunto")

        self.assertIn(validar_adjunto, campo.validators)

    def test_un_archivo_ya_guardado_no_se_revalida(self):
        """Datos legacy: lo que está en `media/` se sigue viendo y descargando."""
        from core.validators import validar_adjunto
        from legajos.models import HistorialContacto

        contacto = HistorialContacto(archivo_adjunto="contactos/viejo.docx")
        contacto.archivo_adjunto._committed = True

        validar_adjunto(contacto.archivo_adjunto)  # no levanta


def xlsx_que_se_infla(bytes_descomprimidos):
    """Un .xlsx válido en el índice cuyo contenido descomprime a `n` bytes."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", b"<Types/>")
        zf.writestr("xl/worksheets/sheet1.xml", b"\x00" * bytes_descomprimidos)
    buffer.seek(0)
    return SimpleUploadedFile(
        "padron.xlsx", buffer.read(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


class PadronZipBombTests(TestCase):
    """SEC-31: el tope de 2 MB miraba solo el comprimido."""

    def test_un_xlsx_que_se_infla_se_rechaza_antes_de_abrirlo(self):
        from programas.services.padron import PADRON_MAX_DESCOMPRIMIDO, parsear_padron

        archivo = xlsx_que_se_infla(PADRON_MAX_DESCOMPRIMIDO + 1)
        # El comprimido pasa el tope viejo: ese era el agujero.
        from programas.services.padron import PADRON_MAX_BYTES

        self.assertLess(archivo.size, PADRON_MAX_BYTES)

        with self.assertRaises(ValidationError) as cm:
            parsear_padron(archivo)

        self.assertIn("descomprim", " ".join(cm.exception.messages).lower())

    def test_un_padron_de_verdad_sigue_entrando(self):
        from openpyxl import Workbook

        from programas.services.padron import parsear_padron

        libro = Workbook()
        hoja = libro.active
        hoja.append(["documento", "sexo", "nombre", "apellido", "fecha de nacimiento", "localidad"])
        hoja.append(["30111222", "F", "Mirta", "Quiroga", "1980-05-04", "Resistencia"])
        buffer = io.BytesIO()
        libro.save(buffer)
        buffer.seek(0)

        entradas, resumen = parsear_padron(SimpleUploadedFile("padron.xlsx", buffer.read()))

        self.assertEqual(resumen.validas, 1)
        self.assertEqual(entradas[0]["dni"], "30111222")

    def test_un_archivo_que_no_es_zip_sigue_dando_el_mensaje_de_siempre(self):
        from programas.services.padron import parsear_padron

        with self.assertRaises(ValidationError) as cm:
            parsear_padron(SimpleUploadedFile("padron.xlsx", b"esto no es un zip"))

        self.assertIn("no es un Excel", " ".join(cm.exception.messages))
