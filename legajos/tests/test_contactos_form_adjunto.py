"""Seguimiento de #643 — el adjunto de contactos dice lo que el servidor acepta.

El PR 7 de la Ola 2 actualizó el `help_text` del **modelo** a «(PDF o imagen, hasta
5 MB)», pero el form lo pisaba con «Grabación, foto o documento» y era el único de los
tres campos de archivo del repo sin `accept`. El campo se llama a sí mismo «Grabación» y
desde SEC-15 `validar_adjunto` rechaza `.mp3`/`.m4a` con «Solo se aceptan archivos JPG,
PNG, WEBP, HEIC o PDF».

El alcance lo fijó D-15, así que el rechazo no es la desviación: lo que faltaba era que
el texto y el `accept` lo dijeran.
"""

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from core.validators import ACCEPT_ADJUNTO, ADJUNTO_EXTENSIONES, MENSAJE_ADJUNTO_FORMATO
from legajos.forms.contactos import HistorialContactoForm
from legajos.models.contactos import HistorialContacto


class AdjuntoDeContactoTests(TestCase):
    def setUp(self):
        self.form = HistorialContactoForm()

    def test_el_help_text_es_el_del_modelo(self):
        """El form ya no lo pisa: una sola frase, la que describe lo que se valida."""
        del_modelo = HistorialContacto._meta.get_field("archivo_adjunto").help_text

        self.assertEqual(self.form.fields["archivo_adjunto"].help_text, del_modelo)
        self.assertIn("PDF o imagen", del_modelo)
        self.assertNotIn("Grabación, foto o documento", self.form.fields["archivo_adjunto"].help_text)

    def test_el_widget_lleva_accept_y_sale_de_la_lista_blanca(self):
        accept = self.form.fields["archivo_adjunto"].widget.attrs["accept"]

        self.assertEqual(accept, ACCEPT_ADJUNTO)
        for extension in ADJUNTO_EXTENSIONES:
            self.assertIn(extension, accept)
        self.assertNotIn(".mp3", accept)

    def test_el_accept_es_la_misma_fuente_que_usa_el_servidor(self):
        """Dos copias de la lista se desincronizan: `ACCEPT_ADJUNTO` se deriva de
        `ADJUNTO_EXTENSIONES`, que es lo que mira `validar_adjunto`."""
        self.assertEqual(ACCEPT_ADJUNTO, ",".join(ADJUNTO_EXTENSIONES))

    def test_un_audio_sigue_rechazandose_con_el_mensaje_de_siempre(self):
        """El `accept` del navegador se saltea: lo que decide es el servidor.

        Se ejercita el campo del form (que arrastra los `validators` del modelo) y no el
        `form.is_valid()` entero, porque `clean_fecha_contacto` compara con
        `datetime.now()` **naive** contra un valor aware y rompe con `TypeError` antes de
        llegar acá. Ese bug es anterior a este PR y queda anotado, no arreglado: tocarlo
        es cambiar el comportamiento de una pantalla que no es de esta ficha.
        """
        contacto = HistorialContacto(
            tipo_contacto="LLAMADA",
            estado="REALIZADO",
            motivo="Seguimiento",
            archivo_adjunto=SimpleUploadedFile("grabacion.mp3", b"ID3-audio"),
        )

        with self.assertRaises(ValidationError) as capturado:
            contacto.full_clean(exclude=["ciudadano", "fecha_contacto", "creado_por"])

        self.assertIn(MENSAJE_ADJUNTO_FORMATO, capturado.exception.message_dict["archivo_adjunto"])
