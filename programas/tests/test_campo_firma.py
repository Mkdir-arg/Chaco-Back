"""Campo «Firma» de los formularios del constructor (Cambio 480).

La firma es la imagen PNG del trazo —que viaja y se guarda como un archivo— más quién firmó
(``{nombre, dni, firmado}``) en la respuesta del campo. Acá se prueba la regla del firmante, el
PNG del recuadro web, el field, los formularios que lo usan (backoffice y portal), la carga de
la app (Becas y relevamiento edilicio), las condiciones y lo que muestra la revisión.
"""

import base64
import struct
import zlib
from datetime import UTC, datetime
from types import SimpleNamespace

from django.core.exceptions import ValidationError
from django.template.loader import render_to_string
from django.test import SimpleTestCase, TestCase

from programas.forms import ItemCampoPropioForm
from programas.forms_dinamicos import FirmaField, RespuestasDisenoForm, imagen_desde_trazo, sin_archivos
from programas.models import Formulario, TipoCampo
from programas.services import campo as servicio_campo
from programas.services.condiciones import OPERADORES_POR_TIPO, evaluar_regla
from programas.services.firma import (
    MENSAJE_DNI,
    MENSAJE_SIN_NOMBRE,
    MENSAJE_SIN_TRAZO,
    errores_del_firmante,
    normalizar_firmante,
    texto_del_firmante,
)
from programas.services.respuestas_dispositivo import _secciones
from programas.services.validacion_relevamiento import validar_respuestas_de_campo


def png(ancho=4, alto=2):
    """Un PNG válido mínimo (blanco), sin depender de Pillow."""

    def bloque(tipo, datos):
        return struct.pack(">I", len(datos)) + tipo + datos + struct.pack(">I", zlib.crc32(tipo + datos))

    filas = b"".join(b"\x00" + b"\xff" * ancho for _ in range(alto))
    return (
        b"\x89PNG\r\n\x1a\n"
        + bloque(b"IHDR", struct.pack(">IIBBBBB", ancho, alto, 8, 0, 0, 0, 0))
        + bloque(b"IDAT", zlib.compress(filas))
        + bloque(b"IEND", b"")
    )


def trazo(contenido=None):
    return "data:image/png;base64," + base64.b64encode(contenido or png()).decode()


FIRMANTE = {"nombre": "  Ana   Gómez ", "dni": "30.111.222"}


def foto_con_firma(obligatorio=True, condicionado=False):
    """La foto de un diseño con un campo FIRMA y, si se pide, un texto que solo aparece si se firmó."""
    items = [
        {
            "tipo_item": "campo",
            "clave": "cp-firma",
            "texto": "Firma del titular",
            "tipo": "FIRMA",
            "obligatorio": obligatorio,
            "opciones": [],
        }
    ]
    if condicionado:
        items.append(
            {
                "tipo_item": "campo",
                "clave": "cp-obs",
                "texto": "Observaciones de la firma",
                "tipo": "STRING",
                "obligatorio": False,
                "opciones": [],
                "condicion": {"modo": "todas", "reglas": [{"fuente": "cp-firma", "op": "adjuntado"}]},
            }
        )
    return {"items": [{"clave": "g1", "titulo": "Conformidad", "tipo_item": "grupo", "items": items}]}


class FirmanteTests(SimpleTestCase):
    def test_normaliza_nombre_y_dni_y_pone_la_fecha_del_servidor(self):
        momento = datetime(2026, 11, 17, 18, 30, tzinfo=UTC)

        limpio = normalizar_firmante(FIRMANTE, momento=momento)

        self.assertEqual(limpio, {"nombre": "Ana Gómez", "dni": "30111222", "firmado": momento.isoformat()})

    def test_rechaza_sin_nombre_o_con_dni_invalido(self):
        self.assertEqual(errores_del_firmante({"nombre": "", "dni": "123"}), [MENSAJE_SIN_NOMBRE, MENSAJE_DNI])
        self.assertEqual(errores_del_firmante("Ana"), [MENSAJE_SIN_NOMBRE, MENSAJE_DNI])
        with self.assertRaises(ValidationError):
            normalizar_firmante({"nombre": "Ana", "dni": "abc"})

    def test_la_fecha_del_cliente_no_vale(self):
        primera = normalizar_firmante({**FIRMANTE, "firmado": "2000-01-01T00:00:00+00:00"})

        self.assertNotEqual(primera["firmado"], "2000-01-01T00:00:00+00:00")

    def test_texto_para_mostrar(self):
        texto = texto_del_firmante({"nombre": "Ana Gómez", "dni": "30111222", "firmado": "2026-11-17T18:30:00+00:00"})

        self.assertTrue(texto.startswith("Ana Gómez · DNI 30111222 · 17/11/2026"))
        self.assertEqual(texto_del_firmante("cualquier cosa"), "")


class TrazoYFieldTests(SimpleTestCase):
    def test_el_trazo_del_recuadro_es_un_png(self):
        archivo = imagen_desde_trazo(trazo())

        self.assertEqual(archivo.read(8), b"\x89PNG\r\n\x1a\n")

    def test_lo_que_no_es_un_png_se_rechaza(self):
        for malo in ("data:image/jpeg;base64,AAAA", "data:image/png;base64,@@@", trazo(b"<html>no soy png</html>")):
            with self.subTest(malo=malo[:30]), self.assertRaises(ValidationError):
                imagen_desde_trazo(malo)

    def test_un_trazo_enorme_se_corta_antes_de_decodificar(self):
        with self.assertRaises(ValidationError):
            imagen_desde_trazo("data:image/png;base64," + "A" * (2 * 1024 * 1024))

    def test_firmar_a_medias_es_error(self):
        campo = FirmaField(required=False)

        self.assertIsNone(campo.clean(["", "", ""]))
        with self.assertRaisesMessage(ValidationError, MENSAJE_SIN_TRAZO):
            campo.clean(["", "Ana Gómez", "30111222"])
        with self.assertRaisesMessage(ValidationError, MENSAJE_DNI):
            campo.clean([trazo(), "Ana Gómez", ""])

    def test_firmado_completo(self):
        limpio = FirmaField(required=True).clean([trazo(), "Ana Gómez", "30111222"])

        self.assertEqual((limpio["nombre"], limpio["dni"]), ("Ana Gómez", "30111222"))
        self.assertTrue(limpio["archivo"].name.endswith(".png"))


class FormularioDelDisenoTests(SimpleTestCase):
    def _form(self, datos, guardadas=None):
        return RespuestasDisenoForm(datos, foto=foto_con_firma(condicionado=True), guardadas=guardadas, prefix="f")

    def test_la_firma_va_a_respuestas_y_la_imagen_a_archivos(self):
        form = self._form({"f-cp-firma_0": trazo(), "f-cp-firma_1": "Ana Gómez", "f-cp-firma_2": "30111222"})

        self.assertTrue(form.is_valid(), form.errors)
        valor = form.respuestas()["cp-firma"]
        self.assertEqual(
            (valor["nombre"], valor["dni"], valor["archivo"]), ("Ana Gómez", "30111222", "firma-cp-firma.png")
        )
        self.assertIn("firmado", valor)
        [(clave, archivo)] = form.archivos()
        self.assertEqual((clave, archivo.name), ("cp-firma", "firma-cp-firma.png"))
        # La firma cuenta como «adjuntado» para las condiciones: el campo condicionado queda visible.
        self.assertNotIn("cp-obs", form._ocultos)

    def test_sin_firma_nueva_vale_la_guardada(self):
        guardada = {
            "nombre": "Ana Gómez",
            "dni": "30111222",
            "firmado": "2026-11-17T18:30:00+00:00",
            "archivo": "x.png",
        }
        form = self._form(
            {"f-cp-firma_0": "", "f-cp-firma_1": "", "f-cp-firma_2": ""}, guardadas={"cp-firma": guardada}
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.respuestas()["cp-firma"], guardada)
        self.assertEqual(form.archivos(), [])
        self.assertEqual(form._grupos[0]["items"][0]["archivo_guardado"], "x.png")

    def test_la_misma_persona_firma_de_nuevo_y_la_fecha_es_la_de_hoy(self):
        """Auditoría de #1159: la firma rehecha guardaba la fecha de la anterior."""
        guardada = {
            "nombre": "Ana Gómez",
            "dni": "30111222",
            "firmado": "2026-01-01T10:00:00+00:00",
            "archivo": "x.png",
        }
        form = self._form(
            {"f-cp-firma_0": trazo(), "f-cp-firma_1": "Ana Gómez", "f-cp-firma_2": "30111222"},
            guardadas={"cp-firma": guardada},
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertNotEqual(form.respuestas()["cp-firma"]["firmado"], guardada["firmado"])
        self.assertEqual(len(form.archivos()), 1)

    def test_una_firma_guardada_no_muestra_el_aviso_de_archivo(self):
        guardada = {
            "nombre": "Ana Gómez",
            "dni": "30111222",
            "firmado": "2026-01-01T10:00:00+00:00",
            "archivo": "x.png",
        }
        form = self._form(None, guardadas={"cp-firma": guardada})
        html = render_to_string(
            "programas/dispositivos/legajo/_formulario_tipo.html",
            {
                "formulario_tipo": SimpleNamespace(
                    grupos=form.grupos, planos=[], diseno=SimpleNamespace(pk=1, version=1)
                )
            },
        )

        self.assertIn("Ya firmó: Ana Gómez", html)
        self.assertNotIn("Ya cargado", html)

    def test_firmar_a_medias_marca_el_campo(self):
        form = self._form({"f-cp-firma_0": "", "f-cp-firma_1": "Ana Gómez", "f-cp-firma_2": "30111222"})

        self.assertFalse(form.is_valid())
        self.assertIn(MENSAJE_SIN_TRAZO, form.errors["cp-firma"])

    def test_la_firma_no_se_conserva_entre_intentos(self):
        self.assertEqual(sin_archivos(foto_con_firma(), {"cp-firma": {"nombre": "Ana"}, "otra": 1}), {"otra": 1})

    def test_el_recuadro_se_dibuja_con_nombre_y_dni(self):
        html = str(self._form(None)["cp-firma"])

        self.assertIn("data-firma-canvas", html)
        self.assertIn('name="f-cp-firma_0"', html)
        self.assertIn("Nombre y apellido de quien firma", html)
        self.assertIn("nodo-firma.js", html)


class CondicionesYConstructorTests(SimpleTestCase):
    def test_la_firma_se_condiciona_como_un_archivo(self):
        self.assertEqual(OPERADORES_POR_TIPO[TipoCampo.FIRMA], {"adjuntado", "no_adjuntado"})
        self.assertTrue(evaluar_regla({"op": "adjuntado"}, {"nombre": "Ana", "dni": "30111222"}))
        self.assertTrue(evaluar_regla({"op": "no_adjuntado"}, None))

    def test_con_adjunto_es_la_unica_regla(self):
        self.assertEqual(TipoCampo.con_adjunto(), (TipoCampo.ARCHIVO, TipoCampo.FIRMA))

    def test_un_campo_propio_de_becas_no_puede_ser_firma_y_en_dispositivos_si(self):
        datos = {"texto": "Firma del titular", "tipo": "FIRMA", "canal": "ambos"}

        becas = ItemCampoPropioForm(datos)
        dispositivos = ItemCampoPropioForm(datos, permite_archivo=True)

        self.assertFalse(becas.is_valid())
        self.assertIn("tipo", becas.errors)
        self.assertTrue(dispositivos.is_valid(), dispositivos.errors)


class CargaDeLaAppTests(TestCase):
    """Lo que manda la app: en el alta de Becas y en el resultado del relevamiento edilicio."""

    def _revisar(self, respuestas, obligatorio=True):
        formulario = Formulario(definicion=foto_con_firma(obligatorio), respuestas=respuestas, observaciones_carga="")
        return servicio_campo.revisar_carga(formulario, relevamiento=SimpleNamespace(convocatoria=None))

    def test_becas_normaliza_el_firmante_con_la_fecha_del_servidor(self):
        revision = self._revisar({"cp-firma": {**FIRMANTE, "firmado": "2000-01-01T00:00:00+00:00"}})

        valor = revision.respuestas["cp-firma"]
        self.assertEqual((valor["nombre"], valor["dni"]), ("Ana Gómez", "30111222"))
        self.assertNotEqual(valor["firmado"], "2000-01-01T00:00:00+00:00")
        self.assertEqual(revision.observaciones, [])

    def test_becas_observa_sin_rechazar(self):
        sin_dni = self._revisar({"cp-firma": {"nombre": "Ana", "dni": ""}})
        sin_firma = self._revisar({})

        self.assertIn(f"«Firma del titular»: {MENSAJE_DNI}", sin_dni.observaciones)
        con_fecha_del_telefono = self._revisar({"cp-firma": {"nombre": "Ana", "dni": "1", "firmado": "2020-01-01"}})
        self.assertEqual(con_fecha_del_telefono.respuestas["cp-firma"], {"nombre": "Ana", "dni": "1"})
        self.assertIn("Falta la respuesta obligatoria «Firma del titular».", sin_firma.observaciones)

    def test_relevamiento_valida_el_firmante_y_exige_la_obligatoria(self):
        efectivas, errores = validar_respuestas_de_campo(foto_con_firma(), {"cp-firma": FIRMANTE})
        _, sin_dni = validar_respuestas_de_campo(foto_con_firma(), {"cp-firma": {"nombre": "Ana"}})
        _, falta = validar_respuestas_de_campo(foto_con_firma(), {})

        self.assertEqual(errores, {})
        self.assertEqual(efectivas["cp-firma"]["dni"], "30111222")
        self.assertIn("firmado", efectivas["cp-firma"])
        self.assertIn(MENSAJE_DNI, sin_dni["cp-firma"])
        self.assertIn("cp-firma", falta)


class VisualizacionTests(SimpleTestCase):
    def test_la_seccion_trae_la_imagen_y_quien_firmo(self):
        adjunto = SimpleNamespace(archivo=SimpleNamespace(name="firma-cp-firma.png", url="/media/f.png"))
        valor = {"nombre": "Ana Gómez", "dni": "30111222", "firmado": "2026-11-17T18:30:00+00:00"}

        [seccion] = _secciones(foto_con_firma(), {"cp-firma": valor}, {"cp-firma": adjunto}, None)
        [campo] = seccion["campos"]

        self.assertTrue(campo["es_firma"])
        self.assertIs(campo["adjunto"], adjunto)
        self.assertTrue(campo["firmante"].startswith("Ana Gómez · DNI 30111222"))
        html = render_to_string(
            "programas/dispositivos/_formulario_respondido.html",
            {"respondido": {"secciones": [seccion], "titulo": "Ingreso", "version": 1}},
        )
        self.assertIn('src="/media/f.png"', html)
        self.assertIn("Firmó: Ana Gómez · DNI 30111222", html)

    def test_sin_imagen_avisa(self):
        html = render_to_string(
            "components/_firma_respondida.html", {"adjunto": None, "firmante": "Ana Gómez · DNI 30111222"}
        )

        self.assertIn("Falta la imagen de la firma", html)
