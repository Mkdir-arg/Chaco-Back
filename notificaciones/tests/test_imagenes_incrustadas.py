"""Imágenes del .zip incrustadas en cada correo: árbol MIME, vista previa y ciclo de vida (Cambio 292).

El Cambio 285 las servía en una ruta pública que el WAF de ECOM bloquea desde internet; desde el
Cambio 292 viajan como partes ``multipart/related`` con su Content-ID y la ruta pública no existe.
"""

import base64
import os
import re
from importlib import import_module

from django.apps import apps as apps_globales
from django.core import mail
from django.test import Client, override_settings
from django.urls import reverse

from notificaciones.models import Campana, ImagenCampana
from notificaciones.services import campanas as servicio
from notificaciones.services import envio, incrustadas
from notificaciones.services import html as servicio_html
from notificaciones.services.lectura_excel import parsear_destinatarios
from notificaciones.tests.test_paquete import mailing, zip_de
from notificaciones.tests.utils import TODAS, ConMediaTemporal, html, usuario_con, xlsx
from notificaciones.views.campanas import CSP_VISTA_PREVIA

CUERPO = (
    '<p>Hola</p><img src="img/foto-header.jpg" alt="cabecera"><img src="img/logo.png" alt="logo">'
    '<p>Pie</p><img src="img/logo.png" alt="logo otra vez">'
)
CIDS = ["01-foto-header.jpg@datanach", "02-logo.png@datanach"]


def crear_con_zip(archivo=None, *, usuario=None, emails=("a@x.com", "b@x.com"), nombre="Con imágenes"):
    archivo = archivo or mailing(CUERPO)
    excel = xlsx(["email", *emails])
    return servicio.crear_campana(
        nombre=nombre,
        asunto="Asunto",
        archivo_excel=excel,
        archivo_html=archivo,
        lectura=parsear_destinatarios(excel),
        datos_html=servicio_html.procesar(archivo),
        usuario=usuario,
    )


def cids_del_html(texto):
    return re.findall(r'src="cid:([^"]+)"', texto)


def arbol(mensaje_mime):
    """``(tipo, [hijos])`` del mensaje: la forma exacta de las partes."""
    if mensaje_mime.is_multipart():
        return (mensaje_mime.get_content_type(), [arbol(parte) for parte in mensaje_mime.get_payload()])
    return mensaje_mime.get_content_type()


def imagenes_de(mensaje_mime):
    return [parte for parte in mensaje_mime.walk() if parte.get_content_maintype() == "image"]


@override_settings(NOTIF_PAUSA_SEG=0)
class CorreoConImagenesTests(ConMediaTemporal):
    def setUp(self):
        super().setUp()
        self.usuario = usuario_con(*TODAS, username="todo")
        self.client.force_login(self.usuario)
        self.campana = crear_con_zip(usuario=self.usuario)

    def _verificar_correo(self, mensaje):
        mime = mensaje.message()
        self.assertEqual(
            arbol(mime),
            ("multipart/related", [("multipart/alternative", ["text/plain", "text/html"]), "image/jpeg", "image/png"]),
        )
        cuerpo = mensaje.alternatives[0][0]
        # Gmail: el html nombra el cid sin <>; el Content-ID de la parte va con <>.
        self.assertEqual(cids_del_html(cuerpo), [CIDS[0], CIDS[1], CIDS[1]])
        partes = imagenes_de(mime)
        self.assertEqual([p["Content-ID"] for p in partes], [f"<{cid}>" for cid in CIDS])
        self.assertEqual(
            [p["Content-Disposition"] for p in partes],
            ['inline; filename="01-foto-header.jpg"', 'inline; filename="02-logo.png"'],
        )
        guardadas = {i.nombre: i for i in self.campana.imagenes.all()}
        for parte, nombre in zip(partes, ["01-foto-header.jpg", "02-logo.png"], strict=True):
            guardadas[nombre].archivo.open("rb")
            try:
                self.assertEqual(parte.get_payload(decode=True), guardadas[nombre].archivo.read())
            finally:
                guardadas[nombre].archivo.close()

    def test_la_prueba_lleva_las_imagenes_incrustadas(self):
        ok, _error, _aviso = envio.enviar_prueba(self.campana, "yo@x.com", usuario=self.usuario)
        self.assertTrue(ok)
        self._verificar_correo(mail.outbox[0])

    def test_el_envio_masivo_lleva_las_imagenes_y_las_lee_una_vez(self):
        campana = envio.iniciar_envio(self.campana, usuario=self.usuario)
        original = incrustadas.partes_mime
        llamadas = []

        def contando(c):
            llamadas.append(c.pk)
            return original(c)

        incrustadas.partes_mime = contando
        try:
            envio.correr(campana)
        finally:
            incrustadas.partes_mime = original

        self.assertEqual(len(mail.outbox), 2)
        for mensaje in mail.outbox:
            self._verificar_correo(mensaje)
        self.assertEqual(llamadas, [self.campana.pk])  # una vez por corrida, no por destinatario

    def test_el_html_ya_no_nombra_ninguna_ruta(self):
        self.assertEqual(cids_del_html(self.campana.html_sanitizado), [CIDS[0], CIDS[1], CIDS[1]])
        self.assertNotIn("/notificaciones/img/", self.campana.html_sanitizado)
        self.assertNotIn("http", self.campana.html_sanitizado)

    def test_solo_van_las_imagenes_que_el_html_usa(self):
        # Una fila de imagen que el HTML no nombra (p. ej. quedó de otra cosa) no viaja.
        ImagenCampana.objects.create(
            campana=self.campana,
            token="x" * 32,
            nombre="99-suelta.png",
            ruta_original="img/suelta.png",
            archivo="notificaciones/imagenes/no-existe.png",
            content_type="image/png",
            tamano=10,
        )
        partes = incrustadas.partes_mime(self.campana)
        self.assertEqual([p["Content-ID"] for p in partes], [f"<{cid}>" for cid in CIDS])

    def test_una_imagen_que_falta_en_el_disco_no_frena_el_correo(self):
        fila = self.campana.imagenes.get(nombre="02-logo.png")
        os.remove(fila.archivo.path)
        with self.assertLogs("notificaciones.services.incrustadas", "ERROR"):
            ok, _, aviso = envio.enviar_prueba(self.campana, "yo@x.com", usuario=self.usuario)
        self.assertTrue(ok)
        self.assertEqual(aviso, "Falta en el servidor 1 imagen: 02-logo.png; los correos salen sin ellas.")
        self.assertEqual([p["Content-ID"] for p in imagenes_de(mail.outbox[0].message())], [f"<{CIDS[0]}>"])

    def test_la_prueba_avisa_en_el_toast_las_imagenes_que_faltan(self):
        os.remove(self.campana.imagenes.get(nombre="02-logo.png").archivo.path)
        with self.assertLogs("notificaciones.services.incrustadas", "ERROR"):
            respuesta = self.client.post(
                reverse("notificaciones:campana_prueba", args=[self.campana.pk]), {"email": "yo@x.com"}
            )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(
            respuesta.json()["message"],
            "Se envió la prueba a yo@x.com. Falta en el servidor 1 imagen: 02-logo.png; los correos salen sin ellas.",
        )

    def test_el_envio_masivo_deja_el_aviso_en_la_campana(self):
        for nombre in ("01-foto-header.jpg", "02-logo.png"):
            os.remove(self.campana.imagenes.get(nombre=nombre).archivo.path)
        campana = envio.iniciar_envio(self.campana, usuario=self.usuario)
        with self.assertLogs("notificaciones.services.incrustadas", "ERROR"):
            envio.correr(campana)

        campana.refresh_from_db()
        self.assertEqual(campana.estado, Campana.Estado.ENVIADA)
        aviso = "Faltan en el servidor 2 imágenes: 01-foto-header.jpg, 02-logo.png; los correos salen sin ellas."
        self.assertEqual(campana.mensaje, aviso)
        self.assertEqual(len(mail.outbox), 2)
        detalle = self.client.get(reverse("notificaciones:campana_detalle", args=[campana.pk])).content.decode()
        self.assertIn("Aviso del envío", detalle)
        self.assertIn(aviso, detalle)

    def test_sin_faltantes_el_envio_no_deja_aviso(self):
        envio.correr(envio.iniciar_envio(self.campana, usuario=self.usuario))
        self.campana.refresh_from_db()
        self.assertEqual(self.campana.mensaje, "")

    def test_un_cid_guardado_con_otras_mayusculas_igual_viaja(self):
        Campana.objects.filter(pk=self.campana.pk).update(
            html_sanitizado='<img src="CID:01-FOTO-HEADER.JPG@DataNach"><img src="cid:02-logo.png@datanach">'
        )
        self.campana.refresh_from_db()
        self.assertEqual([p["Content-ID"] for p in incrustadas.partes_mime(self.campana)], [f"<{cid}>" for cid in CIDS])
        self.assertEqual(incrustadas.html_para_vista_previa(self.campana).count('src="data:image/'), 2)

    def test_html_suelto_sigue_siendo_un_alternative_sin_imagenes(self):
        suelta = crear_con_zip(html('<p>Hola</p><img src="https://cdn.x/a.png">'), nombre="Suelta")
        envio.enviar_prueba(suelta, "yo@x.com", usuario=self.usuario)
        self.assertEqual(arbol(mail.outbox[0].message()), ("multipart/alternative", ["text/plain", "text/html"]))
        self.assertIn('src="https://cdn.x/a.png"', mail.outbox[0].alternatives[0][0])


class VistaPreviaTests(ConMediaTemporal):
    def setUp(self):
        super().setUp()
        self.client.force_login(usuario_con(*TODAS, username="todo"))
        self.campana = crear_con_zip()

    def test_las_imagenes_van_como_data_y_la_csp_las_admite(self):
        respuesta = self.client.get(reverse("notificaciones:campana_vista_previa", args=[self.campana.pk]))
        contenido = respuesta.content.decode()

        self.assertEqual(respuesta["Content-Security-Policy"], CSP_VISTA_PREVIA)
        self.assertIn("img-src https: data:", CSP_VISTA_PREVIA)
        self.assertNotIn("'self'", CSP_VISTA_PREVIA.split("img-src", 1)[1].split(";", 1)[0])
        self.assertNotIn("cid:", contenido)
        datos = re.findall(r'src="data:(image/[a-z]+);base64,([^"]+)"', contenido)
        self.assertEqual([tipo for tipo, _ in datos], ["image/jpeg", "image/png", "image/png"])
        logo = self.campana.imagenes.get(nombre="02-logo.png")
        logo.archivo.open("rb")
        try:
            self.assertEqual(base64.b64decode(datos[1][1]), logo.archivo.read())
        finally:
            logo.archivo.close()
        # Solo en la respuesta: lo guardado sigue con cid:.
        self.campana.refresh_from_db()
        self.assertNotIn("data:", self.campana.html_sanitizado)


class RutaPublicaRetiradaTests(ConMediaTemporal):
    def test_la_ruta_publica_ya_no_responde_sin_sesion(self):
        fila = crear_con_zip().imagenes.first()
        for ruta in (f"/notificaciones/img/{fila.token}/{fila.nombre}", "/notificaciones/img/x/x"):
            with self.subTest(ruta=ruta):
                self.assertNotEqual(Client().get(ruta).status_code, 200)

    def test_por_media_protegida_piden_ver_campanas(self):
        fila = crear_con_zip().imagenes.first()
        ruta = f"/media/{fila.archivo.name}"
        con_ver = Client()
        con_ver.force_login(usuario_con("notificacion.ver", username="ve"))
        self.assertEqual(con_ver.get(ruta).status_code, 200)
        sin_ver = Client()
        sin_ver.force_login(usuario_con(username="sin_ver"))
        self.assertEqual(sin_ver.get(ruta).status_code, 403)
        self.assertEqual(Client().get(ruta).status_code, 302)


class MigracionACidTests(ConMediaTemporal):
    """``notificaciones.0004`` pasa los src de la ruta pública del Cambio 285 a ``cid:``."""

    def test_reescribe_solo_las_imagenes_propias(self):
        campana = crear_con_zip()
        token = campana.imagenes.first().token
        viejo = (
            f'<p>a</p><img src="https://datanach.ecomdev.ar/notificaciones/img/{token}/01-foto-header.jpg">'
            f'<img src="https://datanach.ecomdev.ar/notificaciones/img/{token}/02-logo.png">'
            f'<img src="https://datanach.ecomdev.ar/notificaciones/img/{"Z" * 32}/02-logo.png">'
            '<img src="https://cdn.x/a.png">'
        )
        Campana.objects.filter(pk=campana.pk).update(html_sanitizado=viejo)

        import_module("notificaciones.migrations.0004_imagenes_incrustadas").a_cid(apps_globales, None)

        campana.refresh_from_db()
        self.assertEqual(
            cids_del_html(campana.html_sanitizado), ["01-foto-header.jpg@datanach", "02-logo.png@datanach"]
        )
        # Un token que no es de la campaña y una URL externa quedan como estaban.
        self.assertIn(f'/notificaciones/img/{"Z" * 32}/02-logo.png"', campana.html_sanitizado)
        self.assertIn('src="https://cdn.x/a.png"', campana.html_sanitizado)


@override_settings(NOTIF_PAUSA_SEG=0)
class CicloDeVidaTests(ConMediaTemporal):
    def setUp(self):
        super().setUp()
        self.usuario = usuario_con(*TODAS, username="todo")
        self.client.force_login(self.usuario)
        self.campana = crear_con_zip(usuario=self.usuario)
        self.token = self.campana.imagenes.first().token

    def test_duplicar_copia_las_imagenes_con_token_nuevo(self):
        copia = servicio.duplicar_campana(self.campana, usuario=self.usuario)

        self.assertEqual(copia.imagenes.count(), 2)
        self.assertNotIn(self.token, {f.token for f in copia.imagenes.all()})
        self.assertEqual(cids_del_html(copia.html_sanitizado), cids_del_html(self.campana.html_sanitizado))
        rutas_original = {f.archivo.name for f in self.campana.imagenes.all()}
        self.assertFalse(rutas_original & {f.archivo.name for f in copia.imagenes.all()})
        # Borrar la original no le saca las imágenes a la copia.
        with self.captureOnCommitCallbacks(execute=True):
            servicio.eliminar_campana(self.campana)
        self.assertEqual(len(incrustadas.partes_mime(copia)), 2)

    def test_editar_con_un_zip_nuevo_reemplaza_las_imagenes(self):
        rutas_viejas = [f.archivo.path for f in self.campana.imagenes.all()]
        nuevo = mailing('<img src="img/logo.png">')
        with self.captureOnCommitCallbacks(execute=True):
            servicio.editar_campana(
                self.campana, nombre="Otra", asunto="Otro", archivo_html=nuevo, datos_html=servicio_html.procesar(nuevo)
            )

        self.campana.refresh_from_db()
        filas = list(self.campana.imagenes.all())
        self.assertEqual(len(filas), 1)
        self.assertNotEqual(filas[0].token, self.token)
        self.assertEqual(self.campana.imagenes_alojadas, 1)
        self.assertEqual(cids_del_html(self.campana.html_sanitizado), ["01-logo.png@datanach"])
        for ruta in rutas_viejas:
            self.assertFalse(os.path.exists(ruta))

    def test_editar_con_un_html_suelto_saca_las_imagenes(self):
        cuerpo = html("<p>Sin imágenes</p>")
        with self.captureOnCommitCallbacks(execute=True):
            servicio.editar_campana(
                self.campana, nombre="x", asunto="y", archivo_html=cuerpo, datos_html=servicio_html.procesar(cuerpo)
            )
        self.campana.refresh_from_db()
        self.assertFalse(self.campana.imagenes.exists())
        self.assertEqual(self.campana.imagenes_alojadas, 0)

    def test_editar_solo_el_nombre_conserva_las_imagenes(self):
        servicio.editar_campana(self.campana, nombre="Renombrada", asunto="Asunto")
        self.assertEqual(self.campana.imagenes.count(), 2)

    def test_eliminar_borra_filas_y_archivos(self):
        rutas = [f.archivo.path for f in self.campana.imagenes.all()]
        with self.captureOnCommitCallbacks(execute=True):
            servicio.eliminar_campana(self.campana)
        self.assertFalse(ImagenCampana.objects.exists())
        for ruta in rutas:
            self.assertFalse(os.path.exists(ruta))

    def test_un_rollback_no_deja_imagenes_huerfanas(self):
        archivo = mailing(CUERPO)
        datos = servicio_html.procesar(archivo)
        antes = set(_archivos_en_media())
        excel = xlsx(["email", "a@x.com"])
        with self.assertRaises(RuntimeError):
            _crear_y_fallar(archivo, excel, datos)
        self.assertEqual(set(_archivos_en_media()), antes)

    def test_alta_por_la_pantalla_con_zip(self):
        respuesta = self.client.post(
            reverse("notificaciones:campana_crear"),
            {
                "nombre": "Desde la pantalla",
                "asunto": "Hola",
                "archivo_excel": xlsx(["email", "a@x.com"]),
                "archivo_html": mailing(
                    CUERPO + '<img src="img/nada.png"><img src="img/logo.svg">',
                    extra={"mailing/img/logo.svg": b"<svg></svg>"},
                ),
            },
        )
        campana = Campana.objects.get(nombre="Desde la pantalla")
        self.assertRedirects(respuesta, reverse("notificaciones:campana_detalle", args=[campana.pk]))
        self.assertEqual(campana.nombre_html, "mailing.zip")
        detalle = self.client.get(reverse("notificaciones:campana_detalle", args=[campana.pk])).content.decode()
        self.assertIn("Imágenes que faltan en el .zip", detalle)
        self.assertIn("img/nada.png", detalle)
        self.assertIn("Imágenes del .zip que no se incluyen", detalle)
        self.assertIn("mailing/img/logo.svg (SVG no se admite)", detalle)
        self.assertRegex(detalle, r"Cada correo pesa ~\d+ KB \(2 imágenes incrustadas\)")
        self.assertNotIn("pública", detalle)

    def test_el_peso_aproximado_cuenta_el_html_y_las_imagenes_en_base64(self):
        tamanos = sum(f.tamano for f in self.campana.imagenes.all())
        peso = incrustadas.peso_aproximado(self.campana)
        self.assertGreaterEqual(peso, tamanos * 4 // 3)
        self.assertLess(peso, tamanos * 4 // 3 + 10_000)

    def test_eliminar_ya_no_habla_de_correos_enviados(self):
        detalle = self.client.get(reverse("notificaciones:campana_detalle", args=[self.campana.pk])).content.decode()
        self.assertIn("Se borran la campaña «Con imágenes», su lista de destinatarios y sus archivos.", detalle)
        self.assertNotIn("dejan de verse", detalle)

    def test_el_formulario_acepta_zip_y_explica_que_viajan_en_el_correo(self):
        contenido = self.client.get(reverse("notificaciones:campana_crear")).content.decode()
        self.assertIn('accept=".html,.htm,.zip"', contenido)
        self.assertIn("Cuerpo del correo (HTML o .zip con la carpeta)", contenido)
        self.assertIn("Las imágenes del .zip viajan dentro de cada correo (hasta 2 MB en total)", contenido)
        self.assertNotIn("sin iniciar sesión", contenido)

    def test_el_formulario_rechaza_un_zip_de_mas_de_2_mb_de_imagenes(self):
        archivos = {"mailing.html": "".join(f'<img src="img/r{n}.png">' for n in range(3))}
        for n in range(3):
            archivos[f"img/r{n}.png"] = _ruido_png()
        respuesta = self.client.post(
            reverse("notificaciones:campana_crear"),
            {
                "nombre": "Pesada",
                "asunto": "Hola",
                "archivo_excel": xlsx(["email", "a@x.com"]),
                "archivo_html": zip_de(archivos),
            },
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("el tope es 2 MB", respuesta.content.decode())
        self.assertFalse(Campana.objects.filter(nombre="Pesada").exists())

    def test_el_formulario_muestra_el_error_del_zip(self):
        respuesta = self.client.post(
            reverse("notificaciones:campana_crear"),
            {
                "nombre": "Mala",
                "asunto": "Hola",
                "archivo_excel": xlsx(["email", "a@x.com"]),
                "archivo_html": zip_de({"a.html": "<p>a</p>", "b.html": "<p>b</p>"}),
            },
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("2 archivos HTML", respuesta.content.decode())
        self.assertFalse(Campana.objects.filter(nombre="Mala").exists())


def _ruido_png():
    from io import BytesIO

    from PIL import Image

    salida = BytesIO()
    Image.frombytes("RGB", (600, 600), os.urandom(600 * 600 * 3)).save(salida, "PNG")
    return salida.getvalue()


def _archivos_en_media():
    from django.conf import settings

    for raiz, _dirs, archivos in os.walk(settings.MEDIA_ROOT):
        for nombre in archivos:
            yield os.path.join(raiz, nombre)


def _crear_y_fallar(archivo, excel, datos):
    """Crea la campaña dentro de una transacción que después revienta."""
    from django.db import transaction

    from core.archivos import archivos_atomicos

    @archivos_atomicos
    @transaction.atomic
    def operacion():
        servicio.crear_campana(
            nombre="Rollback",
            asunto="x",
            archivo_excel=excel,
            archivo_html=archivo,
            lectura=parsear_destinatarios(excel),
            datos_html=datos,
            usuario=None,
        )
        raise RuntimeError("falla después de escribir")

    operacion()
