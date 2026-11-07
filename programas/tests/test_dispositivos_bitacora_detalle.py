"""Detalle de una novedad de la bitácora (Cambio 427, caso de QA 3).

Lo que se verifica:

1. **Autorización**: leer pide ``dispositivo.ver`` con alcance al dispositivo; una entrada
   de **otro** dispositivo es 404, y quien no opera el dispositivo recibe 403 igual con un
   id ajeno que con uno inexistente. Cada usuario de prueba tiene todo menos lo que el test
   aísla (la lección del Cambio 271).
2. **Contenido**: observaciones completas, personas con enlace a su legajo (solo con
   ``ciudadano.ver``), adjuntos (imagen con vista previa, el resto para descargar) y la
   cadena de versiones con su motivo.
3. **Archivos**: el enlace es el de ``/media/``, que valida el alcance del dispositivo.
4. **Desde el listado**: «Ver detalle» y el nombre del archivo como enlace.
"""

import re
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from programas.services.bitacora import corregir_entrada
from programas.tests.test_dispositivos_bitacora_pantalla import (
    AHORA,
    MIERCOLES,
    PDF,
    BasePantalla,
    _local,
    _reloj,
    _sin,
)

#: Un PNG mínimo válido (firma + IHDR + IDAT + IEND) para que pase la validación de firma.
PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xa7\x9a\xa0\xa0\x00\x00\x00\x00IEND\xaeB`\x82"
)

TEXTO_LARGO = "Primera línea del parte.\nSegunda línea con detalle. " + "Texto largo. " * 40 + "FIN-DEL-TEXTO"


class BaseDetalle(BasePantalla):
    def setUp(self):
        super().setUp()
        self.entrada = self._cargar(
            _local(MIERCOLES, 15, 30),
            texto=TEXTO_LARGO,
            personas=[self.estadia_ana],
            adjuntos=[
                SimpleUploadedFile("acta.pdf", PDF, content_type="application/pdf"),
                SimpleUploadedFile("daño.png", PNG, content_type="image/png"),
            ],
        )

    def _url(self, entrada=None, dispositivo=None):
        return reverse(
            "dispositivos:bitacora_entrada", args=[(dispositivo or self.cis).pk, (entrada or self.entrada).pk]
        )

    def _detalle(self, usuario=None, entrada=None, dispositivo=None):
        self.client.force_login(usuario or self.operador)
        with _reloj():
            return self.client.get(self._url(entrada, dispositivo))


class AutorizacionTests(BaseDetalle):
    def test_con_ver_y_alcance_se_ve(self):
        usuario = self._usuario("Solo lectura", self.cis, ("dispositivo.ver",))

        self.assertEqual(self._detalle(usuario).status_code, 200)

    def test_sin_dispositivo_ver_es_403(self):
        usuario = self._usuario("Sin ver", self.cis, _sin("dispositivo.ver"))

        self.assertEqual(self._detalle(usuario).status_code, 403)

    def test_otra_institucion_es_404_igual_con_id_ajeno_que_inexistente(self):
        intruso = self._usuario("Operador parador", self.parador)
        inexistente = mock.Mock(pk=999999)

        self.assertEqual(self._detalle(intruso).status_code, 404)
        self.assertEqual(self._detalle(intruso, entrada=inexistente).status_code, 404)

    def test_entrada_de_otro_dispositivo_es_404(self):
        operador_parador = self._usuario("Operador parador", self.parador)
        ajena = self._cargar_en_parador(operador_parador)
        # Con alcance a ambos, el id de la entrada ajena por la URL del CIS no existe.
        doble = self._usuario("Doble", self.cis)
        self._asignar(doble, self.parador)

        self.assertEqual(self._detalle(doble, entrada=ajena).status_code, 404)
        self.assertEqual(self._detalle(doble, entrada=ajena, dispositivo=self.parador).status_code, 200)

    def test_anonimo_va_al_login(self):
        with _reloj():
            self.assertEqual(self.client.get(self._url()).status_code, 302)

    def _cargar_en_parador(self, usuario):
        from programas.services.bitacora import registrar_entrada

        with _reloj():
            return registrar_entrada(dispositivo=self.parador, usuario=usuario, tipo="GENERAL", texto="Ajena.")

    def _asignar(self, usuario, dispositivo):
        from programas.models import AsignacionDispositivo

        rol = usuario.groups.get()
        AsignacionDispositivo.objects.create(dispositivo=dispositivo, rol=rol, activo=True)


class ContenidoTests(BaseDetalle):
    def test_muestra_las_observaciones_completas(self):
        html = self._html(self._detalle())

        self.assertIn("FIN-DEL-TEXTO", html)
        self.assertIn("Segunda línea con detalle.", html)

    def test_la_persona_enlaza_a_su_legajo(self):
        html = self._html(self._detalle())

        self.assertIn(f'href="{reverse("legajos:ciudadano_detalle", args=[self.ana.pk])}"', html)
        self.assertIn("Gómez, Ana", html)

    def test_sin_ciudadano_ver_no_hay_nombre_ni_enlace(self):
        usuario = self._usuario("Sin legajo", self.cis, _sin("ciudadano.ver"))

        html = self._html(self._detalle(usuario))

        self.assertNotIn(reverse("legajos:ciudadano_detalle", args=[self.ana.pk]), html)
        for dato in ("Gómez", "30111222"):
            self.assertNotIn(dato, html)
        self.assertIn("1 persona involucrada", html)

    def test_la_imagen_tiene_vista_previa_y_el_pdf_se_descarga(self):
        html = self._html(self._detalle())
        imagen, pdf = (self.entrada.adjuntos.get(nombre_original=n) for n in ("daño.png", "acta.pdf"))

        self.assertRegex(html, rf'<img[^>]+src="{re.escape(imagen.archivo.url)}"')
        self.assertIn(f'href="{pdf.archivo.url}"', html)
        self.assertNotRegex(html, rf'<img[^>]+src="{re.escape(pdf.archivo.url)}"')
        self.assertTrue(imagen.archivo.url.startswith("/media/"))

    def test_muestra_la_cadena_de_versiones_con_el_motivo(self):
        with _reloj():
            nueva = corregir_entrada(
                entrada=self.entrada,
                usuario=self.operador,
                texto="Texto corregido.",
                motivo="Faltaba un dato",
                adjuntos_nuevos=[SimpleUploadedFile("otro.pdf", PDF, content_type="application/pdf")],
            )

        vieja = self._html(self._detalle())
        vigente = self._html(self._detalle(entrada=nueva))

        self.assertIn("Esta versión fue reemplazada.", vieja)
        self.assertIn(self._url(nueva), vieja)
        self.assertIn("Faltaba un dato · +1 adjunto", vieja)
        self.assertNotIn("Esta versión fue reemplazada.", vigente)
        self.assertIn("Texto corregido.", vigente)
        self.assertIn("corregida el ", vigente)
        self.assertIn(self._url(self.entrada), vigente)
        self.assertIn("Vigente", vigente)

    def test_una_novedad_sin_personas_ni_adjuntos_lo_dice(self):
        simple = self._cargar(_local(MIERCOLES, 15, 45), texto="Nada más.")

        html = self._html(self._detalle(entrada=simple))

        self.assertIn("Sin personas asociadas", html)
        self.assertIn("Sin adjuntos", html)


class MediaTests(BaseDetalle):
    """Los archivos salen por `/media/`, que valida el alcance del dispositivo dueño."""

    def _bajar(self, usuario):
        adjunto = self.entrada.adjuntos.get(nombre_original="acta.pdf")
        self.client.force_login(usuario)
        return self.client.get(adjunto.archivo.url)

    def test_quien_ve_el_dispositivo_baja_el_archivo(self):
        respuesta = self._bajar(self.operador)

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("attachment", respuesta["Content-Disposition"])

    def test_otra_institucion_no_baja_el_archivo(self):
        self.assertEqual(self._bajar(self._usuario("Operador parador", self.parador)).status_code, 404)

    def test_sin_dispositivo_ver_no_baja_el_archivo(self):
        self.assertEqual(self._bajar(self._usuario("Sin ver", self.cis, _sin("dispositivo.ver"))).status_code, 404)


class DesdeElListadoTests(BaseDetalle):
    def test_cada_novedad_enlaza_a_su_detalle_y_el_archivo_es_un_enlace(self):
        with _reloj(AHORA):
            self.client.force_login(self.operador)
            html = self._html(self.client.get(self.url))
        acta = self.entrada.adjuntos.get(nombre_original="acta.pdf")

        self.assertIn(f'href="{self._url()}"', html)
        self.assertIn(">Ver detalle</a>", html)
        self.assertRegex(html, rf'<a href="{re.escape(acta.archivo.url)}"[^>]*>acta.pdf</a>')
        self.assertNotIn("Adjuntos: ", html)
