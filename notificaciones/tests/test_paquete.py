"""El cuerpo como .zip con la carpeta del mailing: lectura segura y resolución de imágenes (Cambio 285).

Los paquetes se arman en el test con ``zipfile`` y Pillow: ningún mailing real entra al repo.
"""

import os
import re
import stat
import zipfile
from io import BytesIO
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from PIL import Image

from notificaciones.services import html as servicio_html
from notificaciones.services import paquete


def imagen(formato="PNG", color=(200, 30, 30), tam=(4, 4)):
    salida = BytesIO()
    Image.new("RGB", tam, color).save(salida, formato)
    return salida.getvalue()


def zip_de(archivos, nombre="mailing.zip"):
    """Un .zip subido con ``{ruta o ZipInfo: bytes|str}``."""
    salida = BytesIO()
    with zipfile.ZipFile(salida, "w", zipfile.ZIP_DEFLATED) as zf:
        for ruta, contenido in archivos.items():
            zf.writestr(ruta, contenido)
    return SimpleUploadedFile(nombre, salida.getvalue(), content_type="application/zip")


def mailing(cuerpo, *, carpeta="mailing/", extra=None):
    """La carpeta típica: ``mailing.html`` + ``img/`` (dentro de una carpeta, como la comprime Windows)."""
    archivos = {
        f"{carpeta}mailing.html": f"<html><body>{cuerpo}</body></html>",
        f"{carpeta}img/foto-header.jpg": imagen("JPEG"),
        f"{carpeta}img/logo.png": imagen("PNG"),
    }
    archivos.update(extra or {})
    return zip_de(archivos)


def cids(html):
    """Los ``src`` de imágenes incrustadas: ``cid:<nombre>@datanach``, sin ``<>`` (Cambio 292)."""
    return re.findall(r'src="(cid:[^"]+@datanach)"', html)


class PaqueteValidoTests(SimpleTestCase):
    def test_publica_las_imagenes_referenciadas_y_reescribe_los_src(self):
        leido = paquete.leer_paquete(mailing('<img src="img/foto-header.jpg" alt="x"><img src="./img/logo.png">'))

        self.assertEqual(len(leido.token), 32)
        self.assertEqual([i.nombre for i in leido.imagenes], ["01-foto-header.jpg", "02-logo.png"])
        self.assertEqual([i.content_type for i in leido.imagenes], ["image/jpeg", "image/png"])
        self.assertEqual(
            [i.ruta_original for i in leido.imagenes], ["mailing/img/foto-header.jpg", "mailing/img/logo.png"]
        )
        self.assertEqual(cids(leido.html), ["cid:01-foto-header.jpg@datanach", "cid:02-logo.png@datanach"])
        self.assertNotIn('src="img/', leido.html)
        self.assertEqual(leido.faltantes, [])
        self.assertEqual(leido.rechazadas, [])

    def test_los_cid_propios_sobreviven_al_saneo_y_los_ajenos_no(self):
        datos = servicio_html.procesar(
            mailing('<img src="img/logo.png"><img src="cid:ajeno@x"><img src="data:image/png;base64,AA">')
        )
        self.assertEqual(cids(datos["html_sanitizado"]), ["cid:01-logo.png@datanach"])
        self.assertNotIn("cid:ajeno", datos["html_sanitizado"])
        self.assertNotIn("data:", datos["html_sanitizado"])
        self.assertEqual(datos["imagenes_alojadas"], 1)
        # El cid: ajeno y el data: no le llegan a nadie; el propio sí.
        self.assertEqual(datos["imagenes_no_visibles"], 2)

    def test_barra_invertida_mayusculas_y_espacios_codificados(self):
        archivo = zip_de(
            {
                "mailing.html": '<img src="IMG\\Foto-Header.JPG"><img src="img/mi%20foto.png"><img src=img/LOGO.png>',
                "img/foto-header.jpg": imagen("JPEG"),
                "img/mi foto.png": imagen("PNG"),
                "img/logo.png": imagen("PNG"),
            }
        )
        leido = paquete.leer_paquete(archivo)
        self.assertEqual(leido.faltantes, [])
        self.assertEqual(
            [i.ruta_original for i in leido.imagenes], ["img/foto-header.jpg", "img/mi foto.png", "img/logo.png"]
        )
        self.assertEqual(len(cids(leido.html)), 3)

    def test_una_imagen_nombrada_dos_veces_se_publica_una_vez(self):
        leido = paquete.leer_paquete(mailing('<img src="img/logo.png"><img src="img/logo.png?v=2">'))
        self.assertEqual(len(leido.imagenes), 1)
        self.assertEqual(len(cids(leido.html)), 2)

    def test_imagen_que_falta_va_a_la_lista_y_no_cuenta_como_no_visible(self):
        datos = servicio_html.procesar(mailing('<img src="img/logo.png"><img src="img/nada.png"><img src="cid:x">'))
        self.assertEqual(datos["imagenes_faltantes"], "img/nada.png")
        self.assertEqual(datos["imagenes_alojadas"], 1)
        # Solo el cid: queda como «no visible por otra causa»: la faltante ya se nombra.
        self.assertEqual(datos["imagenes_no_visibles"], 1)

    def test_las_no_referenciadas_no_se_publican(self):
        leido = paquete.leer_paquete(mailing('<img src="img/logo.png">', extra={"mailing/img/sobra.png": imagen()}))
        self.assertEqual([i.ruta_original for i in leido.imagenes], ["mailing/img/logo.png"])

    def test_svg_no_se_publica(self):
        svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
        datos = servicio_html.procesar(mailing('<img src="img/logo.svg">', extra={"mailing/img/logo.svg": svg}))
        self.assertEqual(datos["imagenes"], [])
        self.assertIn("mailing/img/logo.svg (SVG no se admite)", datos["imagenes_rechazadas"])
        self.assertEqual(cids(datos["html_sanitizado"]), [])

    def test_svg_con_extension_png_tampoco(self):
        svg = b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg"></svg>'
        leido = paquete.leer_paquete(mailing('<img src="img/x.png">', extra={"mailing/img/x.png": svg}))
        self.assertEqual(leido.imagenes, [])
        self.assertEqual(len(leido.rechazadas), 1)

    def test_imagen_falsa_con_extension_png_no_se_publica(self):
        falsa = b"<html><script>alert(document.cookie)</script></html>"
        leido = paquete.leer_paquete(mailing('<img src="img/falsa.png">', extra={"mailing/img/falsa.png": falsa}))
        self.assertEqual(leido.imagenes, [])
        self.assertEqual(leido.rechazadas, [f"mailing/img/falsa.png ({paquete.MOTIVO_NO_IMAGEN})"])
        self.assertEqual(cids(leido.html), [])

    def test_un_formato_real_no_admitido_no_se_publica(self):
        leido = paquete.leer_paquete(mailing('<img src="img/x.png">', extra={"mailing/img/x.png": imagen("BMP")}))
        self.assertEqual(leido.imagenes, [])

    def test_la_extension_publicada_es_la_del_formato_real(self):
        leido = paquete.leer_paquete(mailing('<img src="img/x.png">', extra={"mailing/img/x.png": imagen("JPEG")}))
        self.assertEqual(leido.imagenes[0].nombre, "01-x.jpg")
        self.assertEqual(leido.imagenes[0].content_type, "image/jpeg")

    def test_macosx_y_basura_del_sistema_se_ignoran(self):
        leido = paquete.leer_paquete(
            mailing(
                '<img src="img/logo.png">',
                extra={
                    "__MACOSX/mailing/._mailing.html": b"\x00\x05\x16\x07basura",
                    "mailing/.DS_Store": b"\x00\x00",
                    "mailing/img/Thumbs.db": b"\x00",
                    "mailing/._otro.html": b"\x00",
                },
            )
        )
        self.assertEqual(leido.nombre_html, "mailing/mailing.html")
        self.assertEqual(len(leido.imagenes), 1)

    def test_con_varios_html_gana_el_index_de_la_raiz(self):
        archivo = zip_de(
            {
                "carpeta/index.html": '<img src="img/logo.png">',
                "carpeta/version-texto.html": "<p>x</p>",
                "carpeta/img/logo.png": imagen(),
            }
        )
        self.assertEqual(paquete.leer_paquete(archivo).nombre_html, "carpeta/index.html")

    def test_ruta_que_sale_del_paquete_es_faltante(self):
        leido = paquete.leer_paquete(mailing('<img src="../../etc/passwd">'))
        self.assertEqual(leido.imagenes, [])
        self.assertEqual(leido.faltantes, ["../../etc/passwd"])

    def test_html_suelto_sigue_igual(self):
        datos = servicio_html.procesar(
            SimpleUploadedFile("c.html", b'<p>Hola</p><img src="img/rel.png"><img src="https://cdn.x/a.png">')
        )
        self.assertEqual(datos["imagenes"], [])
        self.assertEqual(datos["imagenes_alojadas"], 0)
        self.assertIsNone(datos["imagenes_faltantes"])
        self.assertEqual(datos["imagenes_no_visibles"], 1)
        self.assertIn('src="https://cdn.x/a.png"', datos["html_sanitizado"])


def _exif_con_gps():
    exif = Image.Exif()
    exif[0x0110] = "CamaraDelDisenador"  # Model
    exif[0x0112] = 6  # Orientation: girada 90°
    exif[0x8825] = {1: "S", 2: (27.0, 27.0, 1.0), 3: "W", 4: (58.0, 59.0, 1.0)}  # GPSInfo
    return exif


class ImagenRecodificadaTests(SimpleTestCase):
    """Lo que se publica es la imagen recodificada, sin metadatos (revisión del juez, ronda 2)."""

    def _publicada(self, ruta, datos):
        leido = paquete.leer_paquete(mailing(f'<img src="{ruta}">', extra={f"mailing/{ruta}": datos}))
        self.assertEqual(leido.rechazadas, [])
        return leido.imagenes[0].contenido

    def test_jpeg_con_exif_gps_sale_sin_exif_y_derecha(self):
        salida = BytesIO()
        Image.new("RGB", (8, 4), (10, 120, 200)).save(salida, "JPEG", exif=_exif_con_gps(), icc_profile=b"perfil")
        original = salida.getvalue()
        self.assertIn(b"CamaraDelDisenador", original)
        self.assertTrue(Image.open(BytesIO(original)).getexif().get_ifd(0x8825))

        publicada = self._publicada("img/foto.jpg", original)

        self.assertNotIn(b"CamaraDelDisenador", publicada)
        self.assertNotIn(b"Exif", publicada)
        limpia = Image.open(BytesIO(publicada))
        self.assertEqual(limpia.format, "JPEG")
        self.assertEqual(dict(limpia.getexif()), {})
        self.assertEqual(limpia.size, (4, 8))  # se aplicó la orientación antes de perderla
        self.assertEqual(limpia.info.get("icc_profile"), b"perfil")  # el perfil de color se conserva

    def test_png_sale_sin_textos_ni_exif(self):
        from PIL import PngImagePlugin

        textos = PngImagePlugin.PngInfo()
        textos.add_text("Author", "NombreDeLaDisenadora")
        salida = BytesIO()
        Image.new("RGBA", (4, 4), (0, 0, 0, 0)).save(salida, "PNG", pnginfo=textos, exif=_exif_con_gps())

        publicada = self._publicada("img/logo.png", salida.getvalue())

        self.assertNotIn(b"NombreDeLaDisenadora", publicada)
        self.assertNotIn(b"CamaraDelDisenador", publicada)
        limpia = Image.open(BytesIO(publicada))
        self.assertEqual((limpia.format, limpia.mode), ("PNG", "RGBA"))
        self.assertNotIn("Author", limpia.info)

    def test_gif_animado_conserva_la_animacion_y_pierde_el_comentario(self):
        cuadros = [Image.new("RGB", (4, 4), color) for color in ((255, 0, 0), (0, 255, 0), (0, 0, 255))]
        salida = BytesIO()
        cuadros[0].save(
            salida, "GIF", save_all=True, append_images=cuadros[1:], comment=b"ComentarioPrivado", duration=120, loop=0
        )

        publicada = self._publicada("img/anim.gif", salida.getvalue())

        self.assertNotIn(b"ComentarioPrivado", publicada)
        limpia = Image.open(BytesIO(publicada))
        self.assertTrue(limpia.is_animated)
        self.assertEqual(limpia.n_frames, 3)

    def test_lo_pegado_atras_de_la_imagen_no_se_publica(self):
        poliglota = imagen("PNG") + b"<script>alert(1)</script>"
        self.assertNotIn(b"<script>", self._publicada("img/x.png", poliglota))

    def test_mas_de_25_millones_de_pixeles_no_se_publica(self):
        salida = BytesIO()
        Image.new("1", (5001, 5000)).save(salida, "PNG")  # pocos KB, 25.005.000 px
        leido = paquete.leer_paquete(
            mailing('<img src="img/enorme.png">', extra={"mailing/img/enorme.png": salida.getvalue()})
        )
        self.assertEqual(leido.imagenes, [])
        self.assertEqual(leido.rechazadas, [f"mailing/img/enorme.png ({paquete.MOTIVO_PIXELES})"])

    def test_la_alarma_de_bomba_de_pillow_tambien_rechaza(self):
        # Con el umbral de Pillow bajado: 12×12 dispara el aviso y 20×20 el error.
        for lado in (12, 20):
            with self.subTest(lado=lado), patch.object(Image, "MAX_IMAGE_PIXELS", 100):
                leido = paquete.leer_paquete(
                    mailing('<img src="img/b.png">', extra={"mailing/img/b.png": imagen(tam=(lado, lado))})
                )
                self.assertEqual(leido.imagenes, [])
                self.assertEqual(leido.rechazadas, [f"mailing/img/b.png ({paquete.MOTIVO_PIXELES})"])


class PaqueteRechazadoTests(SimpleTestCase):
    def _rechaza(self, archivo, fragmento):
        with self.assertRaises(ValidationError) as ctx:
            servicio_html.procesar(archivo)
        self.assertIn(fragmento, " ".join(ctx.exception.messages))

    def test_ruta_con_puntos_puntos(self):
        self._rechaza(zip_de({"mailing.html": "<p>x</p>", "../afuera.png": imagen()}), "ruta no permitida")

    def test_ruta_absoluta_y_unidad_de_windows(self):
        self._rechaza(zip_de({"mailing.html": "<p>x</p>", "/etc/x.png": imagen()}), "ruta no permitida")
        self._rechaza(zip_de({"mailing.html": "<p>x</p>", "C:/x.png": imagen()}), "ruta no permitida")
        self._rechaza(zip_de({"mailing.html": "<p>x</p>", "img\\..\\..\\x.png": imagen()}), "ruta no permitida")

    def test_enlace_simbolico(self):
        enlace = zipfile.ZipInfo("img/logo.png")
        enlace.external_attr = (stat.S_IFLNK | 0o777) << 16
        self._rechaza(zip_de({"mailing.html": "<p>x</p>", enlace: "/etc/passwd"}), "enlace simbólico")

    def test_bomba_de_compresion(self):
        # 21 MB de ceros comprimen a unos pocos KB: el tope es sobre lo descomprimido.
        bomba = zip_de({"mailing.html": "<p>x</p>", "img/bomba.png": b"\x00" * (21 * 1024 * 1024)})
        self.assertLess(bomba.size, 1024 * 1024)
        self._rechaza(bomba, "descomprimido supera 20 MB")

    def test_mas_de_50_imagenes(self):
        archivos = {"mailing.html": "<p>x</p>"}
        archivos.update({f"img/{n}.png": imagen() for n in range(51)})
        self._rechaza(zip_de(archivos), "más de 50 imágenes")

    def test_dos_html_sin_index(self):
        self._rechaza(zip_de({"a.html": "<p>a</p>", "b.htm": "<p>b</p>"}), "2 archivos HTML")

    def test_index_en_una_subcarpeta_no_desempata(self):
        self._rechaza(zip_de({"a.html": "<p>a</p>", "sub/index.html": "<p>b</p>"}), "2 archivos HTML")

    def test_sin_html(self):
        self._rechaza(zip_de({"img/logo.png": imagen()}), "ningún archivo .html")

    def test_zip_roto(self):
        self._rechaza(SimpleUploadedFile("m.zip", b"PK\x03\x04no-es-un-zip"), "dañado")

    def test_zip_de_mas_de_10_mb(self):
        archivo = SimpleUploadedFile("m.zip", b"x")
        archivo.size = paquete.ZIP_MAX_BYTES + 1
        self._rechaza(archivo, "10 MB")

    def test_html_que_no_es_utf8(self):
        self._rechaza(zip_de({"m.html": "<p>Ñandú</p>".encode("latin-1")}), "UTF-8")

    def test_las_imagenes_pasan_los_2_mb_en_total(self):
        """Cada correo lleva todas las imágenes: el total (ya recodificado) tiene tope (Cambio 292)."""
        archivos = {"mailing.html": "".join(f'<img src="img/ruido{n}.png">' for n in range(3))}
        for n in range(3):
            salida = BytesIO()
            Image.frombytes("RGB", (600, 600), os.urandom(600 * 600 * 3)).save(salida, "PNG")  # ~1 MB, no comprime
            archivos[f"img/ruido{n}.png"] = salida.getvalue()
        with self.assertRaises(ValidationError) as ctx:
            servicio_html.procesar(zip_de(archivos))
        mensaje = " ".join(ctx.exception.messages)
        self.assertRegex(mensaje, r"pesan 3\.\d MB en total")
        self.assertIn("el tope es 2 MB", mensaje)

    def test_justo_debajo_del_tope_entra(self):
        archivos = {"mailing.html": '<img src="img/ruido.png">'}
        salida = BytesIO()
        Image.frombytes("RGB", (600, 600), os.urandom(600 * 600 * 3)).save(salida, "PNG")
        archivos["img/ruido.png"] = salida.getvalue()
        self.assertEqual(len(paquete.leer_paquete(zip_de(archivos)).imagenes), 1)

    def test_otra_extension(self):
        self._rechaza(SimpleUploadedFile("m.rar", b"x"), ".zip con la carpeta")
