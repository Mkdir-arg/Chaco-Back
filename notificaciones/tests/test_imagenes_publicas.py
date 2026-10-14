"""Imágenes del .zip publicadas: vista pública, ciclo de vida y URLs del correo (Cambio 285)."""

import os
import re

from django.contrib.auth.models import Group
from django.core import mail
from django.test import Client, override_settings
from django.urls import reverse

from core.middleware import CLAVE_ULTIMA_ACTIVIDAD
from notificaciones.models import Campana, ImagenCampana
from notificaciones.services import campanas as servicio
from notificaciones.services import envio
from notificaciones.services import html as servicio_html
from notificaciones.services.lectura_excel import parsear_destinatarios
from notificaciones.tests.test_paquete import mailing, zip_de
from notificaciones.tests.utils import TODAS, ConMediaTemporal, html, usuario_con, xlsx
from notificaciones.views.campanas import CACHE_IMAGEN, CSP_IMAGEN, CSP_VISTA_PREVIA

BASE = "https://datanach.test"
CUERPO = '<p>Hola</p><img src="img/foto-header.jpg" alt="cabecera"><img src="img/logo.png" alt="logo">'


def crear_con_zip(archivo=None, *, usuario=None, emails=("a@x.com", "b@x.com")):
    archivo = archivo or mailing(CUERPO)
    excel = xlsx(["email", *emails])
    return servicio.crear_campana(
        nombre="Con imágenes",
        asunto="Asunto",
        archivo_excel=excel,
        archivo_html=archivo,
        lectura=parsear_destinatarios(excel),
        datos_html=servicio_html.procesar(archivo),
        usuario=usuario,
    )


def url_imagen(fila):
    return reverse("notificaciones:imagen_publica", args=[fila.token, fila.nombre])


def tokens_en(texto):
    return set(re.findall(r"/notificaciones/img/([\w-]{32})/", texto))


@override_settings(NOTIF_URL_PUBLICA=BASE)
class VistaPublicaTests(ConMediaTemporal):
    def setUp(self):
        super().setUp()
        self.campana = crear_con_zip()
        self.imagenes = list(self.campana.imagenes.order_by("nombre"))
        self.anonimo = Client()

    def test_quedan_alojadas_con_un_token_por_paquete(self):
        self.assertEqual(self.campana.imagenes_alojadas, 2)
        self.assertEqual([i.nombre for i in self.imagenes], ["01-foto-header.jpg", "02-logo.png"])
        self.assertEqual({i.token for i in self.imagenes}, tokens_en(self.campana.html_sanitizado))
        for fila in self.imagenes:
            self.assertTrue(fila.archivo.name.startswith(f"notificaciones/imagenes/{fila.token}/"))
            self.assertIn(f'src="{BASE}{url_imagen(fila)}"', self.campana.html_sanitizado)

    def test_sin_sesion_sirve_la_imagen_con_sus_cabeceras(self):
        fila = self.imagenes[1]
        respuesta = self.anonimo.get(url_imagen(fila))

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta["Content-Type"], "image/png")
        self.assertEqual(respuesta["X-Content-Type-Options"], "nosniff")
        self.assertEqual(respuesta["Content-Disposition"], 'inline; filename="02-logo.png"')
        self.assertEqual(respuesta["Content-Security-Policy"], CSP_IMAGEN)
        self.assertEqual(respuesta["Cache-Control"], CACHE_IMAGEN)
        self.assertNotIn("Set-Cookie", respuesta.headers)
        fila.archivo.open("rb")
        try:
            self.assertEqual(b"".join(respuesta.streaming_content), fila.archivo.read())
        finally:
            fila.archivo.close()

    def test_jpeg_sale_como_jpeg(self):
        self.assertEqual(self.anonimo.get(url_imagen(self.imagenes[0]))["Content-Type"], "image/jpeg")

    def test_token_o_nombre_que_no_existen_dan_404(self):
        fila = self.imagenes[0]
        otro_token = "A" * 32
        for destino in (
            reverse("notificaciones:imagen_publica", args=[otro_token, fila.nombre]),
            reverse("notificaciones:imagen_publica", args=[fila.token, "03-nada.png"]),
            reverse("notificaciones:imagen_publica", args=["corto", fila.nombre]),
        ):
            with self.subTest(destino=destino):
                self.assertEqual(self.anonimo.get(destino).status_code, 404)

    def test_no_expone_otros_archivos_de_media(self):
        fila = self.imagenes[0]
        excel = self.campana.archivo_excel.name  # notificaciones/excel/<uuid>.xlsx
        html_original = self.campana.archivo_html.name
        for nombre in (
            os.path.basename(excel),
            os.path.basename(html_original),
            os.path.basename(fila.archivo.name),  # el nombre en disco no es el de la URL
            "..%2Fexcel%2F" + os.path.basename(excel),
        ):
            with self.subTest(nombre=nombre):
                respuesta = self.anonimo.get(f"/notificaciones/img/{fila.token}/{nombre}")
                self.assertEqual(respuesta.status_code, 404)
        for ruta in (excel, html_original, f"../{excel}"):
            with self.subTest(ruta=ruta):
                self.assertEqual(self.anonimo.get(f"/notificaciones/img/{fila.token}/{ruta}").status_code, 404)

    def test_el_token_de_una_campana_no_abre_las_imagenes_de_otra(self):
        ajena = crear_con_zip(mailing('<img src="img/logo.png">')).imagenes.get()  # «01-logo.png»
        propio = self.imagenes[0].token
        self.assertNotEqual(propio, ajena.token)
        self.assertEqual(self.anonimo.get(url_imagen(ajena)).status_code, 200)
        for token, nombre in ((propio, ajena.nombre), (ajena.token, self.imagenes[1].nombre)):
            with self.subTest(token=token, nombre=nombre):
                destino = reverse("notificaciones:imagen_publica", args=[token, nombre])
                self.assertEqual(self.anonimo.get(destino).status_code, 404)

    def test_post_no_se_admite(self):
        self.assertEqual(self.anonimo.post(url_imagen(self.imagenes[0])).status_code, 405)

    def test_campana_eliminada_da_404_y_borra_los_archivos(self):
        destinos = [url_imagen(f) for f in self.imagenes]
        rutas = [f.archivo.path for f in self.imagenes]
        with self.captureOnCommitCallbacks(execute=True):
            servicio.eliminar_campana(self.campana)

        self.assertFalse(ImagenCampana.objects.exists())
        for destino, ruta in zip(destinos, rutas, strict=True):
            self.assertEqual(self.anonimo.get(destino).status_code, 404)
            self.assertFalse(os.path.exists(ruta))

    def test_archivo_borrado_del_disco_da_404(self):
        fila = self.imagenes[0]
        os.remove(fila.archivo.path)
        self.assertEqual(self.anonimo.get(url_imagen(fila)).status_code, 404)


@override_settings(NOTIF_URL_PUBLICA=BASE, SESSION_IDLE_TIMEOUT_MINUTES=15)
class MiddlewaresNoLaTocanTests(ConMediaTemporal):
    """Una cookie que viaja por casualidad no redirige la imagen ni le pone ``Set-Cookie``."""

    def setUp(self):
        super().setUp()
        self.destino = url_imagen(crear_con_zip().imagenes.first())

    def _sin_sesion_tocada(self, respuesta):
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotIn("Set-Cookie", respuesta.headers)

    def test_ciudadano_del_portal(self):
        from core import rbac

        ciudadano = usuario_con(username="ciudadano")
        ciudadano.groups.add(Group.objects.get_or_create(name=rbac.GRUPO_CIUDADANO_PORTAL)[0])
        self.client.force_login(ciudadano)
        self._sin_sesion_tocada(self.client.get(self.destino))

    def test_clave_provisoria(self):
        usuario = usuario_con(username="provisoria")
        usuario.profile.debe_cambiar_contrasena = True
        usuario.profile.save()
        self.client.force_login(usuario)
        self._sin_sesion_tocada(self.client.get(self.destino))

    def test_sesion_vencida_por_inactividad(self):
        self.client.force_login(usuario_con(username="dormido"))
        sesion = self.client.session
        sesion[CLAVE_ULTIMA_ACTIVIDAD] = 0
        sesion.save()
        self._sin_sesion_tocada(self.client.get(self.destino))

    def test_sesion_reemplazada(self):
        usuario = usuario_con(username="reemplazado")
        self.client.force_login(usuario)
        usuario.profile.backoffice_session_key = "otra-sesion"
        usuario.profile.save()
        self._sin_sesion_tocada(self.client.get(self.destino))


@override_settings(NOTIF_URL_PUBLICA=BASE, NOTIF_PAUSA_SEG=0)
class CicloDeVidaTests(ConMediaTemporal):
    def setUp(self):
        super().setUp()
        self.usuario = usuario_con(*TODAS, username="todo")
        self.client.force_login(self.usuario)
        self.campana = crear_con_zip(usuario=self.usuario)
        self.token = self.campana.imagenes.first().token

    def test_el_correo_enviado_lleva_las_urls_absolutas(self):
        campana = envio.iniciar_envio(self.campana, usuario=self.usuario)
        envio.correr(campana)

        self.assertEqual(len(mail.outbox), 2)
        cuerpo = mail.outbox[0].alternatives[0][0]
        for fila in self.campana.imagenes.all():
            self.assertIn(f'src="{BASE}{url_imagen(fila)}"', cuerpo)
        self.assertNotIn('src="img/', cuerpo)

    def test_la_prueba_lleva_las_mismas_urls(self):
        ok, _error = envio.enviar_prueba(self.campana, "yo@x.com", usuario=self.usuario)
        self.assertTrue(ok)
        cuerpo = mail.outbox[0].alternatives[0][0]
        self.assertEqual(tokens_en(cuerpo), {self.token})
        self.assertEqual(cuerpo.count(f"{BASE}/notificaciones/img/{self.token}/"), 2)

    def test_la_vista_previa_lleva_las_mismas_urls_y_las_deja_cargar(self):
        respuesta = self.client.get(reverse("notificaciones:campana_vista_previa", args=[self.campana.pk]))
        self.assertEqual(tokens_en(respuesta.content.decode()), {self.token})
        self.assertIn("img-src 'self' https:", respuesta["Content-Security-Policy"])
        self.assertEqual(respuesta["Content-Security-Policy"], CSP_VISTA_PREVIA)

    def test_duplicar_copia_las_imagenes_con_token_nuevo(self):
        copia = servicio.duplicar_campana(self.campana, usuario=self.usuario)

        nuevos = {f.token for f in copia.imagenes.all()}
        self.assertEqual(copia.imagenes.count(), 2)
        self.assertEqual(len(nuevos), 1)
        self.assertNotIn(self.token, nuevos)
        self.assertEqual(tokens_en(copia.html_sanitizado), nuevos)
        self.assertEqual(self.campana.imagenes.count(), 2)
        rutas_original = {f.archivo.name for f in self.campana.imagenes.all()}
        self.assertFalse(rutas_original & {f.archivo.name for f in copia.imagenes.all()})
        # Borrar la original no rompe el correo de la copia.
        with self.captureOnCommitCallbacks(execute=True):
            servicio.eliminar_campana(self.campana)
        for fila in copia.imagenes.all():
            self.assertEqual(Client().get(url_imagen(fila)).status_code, 200)

    def test_editar_con_un_zip_nuevo_reemplaza_las_imagenes(self):
        viejas = list(self.campana.imagenes.all())
        rutas_viejas = [f.archivo.path for f in viejas]
        nuevo = mailing('<img src="img/logo.png">')
        with self.captureOnCommitCallbacks(execute=True):
            servicio.editar_campana(
                self.campana,
                nombre="Otra",
                asunto="Otro",
                archivo_html=nuevo,
                datos_html=servicio_html.procesar(nuevo),
            )

        self.campana.refresh_from_db()
        filas = list(self.campana.imagenes.all())
        self.assertEqual(len(filas), 1)
        self.assertNotEqual(filas[0].token, self.token)
        self.assertEqual(self.campana.imagenes_alojadas, 1)
        self.assertEqual(tokens_en(self.campana.html_sanitizado), {filas[0].token})
        for fila, ruta in zip(viejas, rutas_viejas, strict=True):
            self.assertFalse(os.path.exists(ruta))
            self.assertEqual(Client().get(url_imagen(fila)).status_code, 404)

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
                    extra={
                        "mailing/img/logo.svg": b"<svg></svg>",
                    },
                ),
            },
        )
        campana = Campana.objects.get(nombre="Desde la pantalla")
        self.assertRedirects(respuesta, reverse("notificaciones:campana_detalle", args=[campana.pk]))
        self.assertEqual(campana.nombre_html, "mailing.zip")
        detalle = self.client.get(reverse("notificaciones:campana_detalle", args=[campana.pk])).content.decode()
        self.assertIn("Imágenes que faltan en el .zip", detalle)
        self.assertIn("img/nada.png", detalle)
        self.assertIn("Imágenes del .zip que no se publicaron", detalle)
        self.assertIn("mailing/img/logo.svg (SVG no se admite)", detalle)
        self.assertIn("Se alojaron 2 imágenes del .zip", detalle)

    def test_la_confirmacion_de_eliminar_avisa_que_las_imagenes_dejan_de_verse(self):
        aviso = "Las imágenes alojadas dejan de verse en los correos ya enviados"
        detalle = self.client.get(reverse("notificaciones:campana_detalle", args=[self.campana.pk])).content.decode()
        self.assertIn(aviso, detalle)
        sin_imagenes = servicio.crear_campana(
            nombre="Sin imágenes",
            asunto="x",
            archivo_excel=xlsx(["email", "a@x.com"]),
            archivo_html=html(),
            lectura=parsear_destinatarios(xlsx(["email", "a@x.com"])),
            datos_html=servicio_html.procesar(html()),
            usuario=self.usuario,
        )
        otro = self.client.get(reverse("notificaciones:campana_detalle", args=[sin_imagenes.pk])).content.decode()
        self.assertIn("Se borran la campaña «Sin imágenes»", otro)
        self.assertNotIn(aviso, otro)

    def test_el_formulario_acepta_zip(self):
        contenido = self.client.get(reverse("notificaciones:campana_crear")).content.decode()
        self.assertIn('accept=".html,.htm,.zip"', contenido)
        self.assertIn("Cuerpo del correo (HTML o .zip con la carpeta)", contenido)

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

    def test_imagenes_por_media_protegida_piden_ver_campanas(self):
        fila = self.campana.imagenes.first()
        ruta = f"/media/{fila.archivo.name}"
        self.assertEqual(self.client.get(ruta).status_code, 200)
        otro = Client()
        otro.force_login(usuario_con(username="sin_ver"))
        self.assertEqual(otro.get(ruta).status_code, 403)
        self.assertEqual(Client().get(ruta).status_code, 302)


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
