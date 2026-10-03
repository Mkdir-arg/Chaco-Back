"""`/media/` exige sesión de backoffice (SEC-09 etapa 1, auditoría oct-2026).

Dos caminos servían los archivos subidos sin que Django mirara quién pedía:

- **nginx** (`nginx.conf`, icore-srv/DEV) los servía con `alias` y `expires 7d`,
  sin pasar por la app: cualquiera con la ruta los bajaba sin sesión.
- **Django** (`SERVE_MEDIA=True`) los sirve con `login_required`, pero
  `PortalCiudadanoMiddleware` eximía `/media/`, así que la sesión de un
  ciudadano del portal alcanzaba para bajar cualquier adjunto del backoffice.

Esta etapa cierra las dos puertas: nginx deja de servir `/media/` (solo queda
`/protected-media/` como `internal`, para la etapa 2) y la exención del
middleware se va. La pertenencia por archivo —quién puede ver *qué* adjunto— es
la etapa 2 (Ola 2) y acá todavía no se verifica.
"""

import importlib
import tempfile
from contextlib import contextmanager
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import clear_url_caches, reverse

import config.urls
from core import rbac

RAIZ = Path(settings.BASE_DIR)
RUTA_ADJUNTO = "/media/adjuntos/dni_secreto.pdf"
CONTENIDO = b"%PDF-contenido-del-ciudadano"


@contextmanager
def _media_servido_por_django(media_root):
    """Activa `SERVE_MEDIA` rearmando el urlconf (las rutas se arman al importar)."""
    contexto = override_settings(SERVE_MEDIA=True, MEDIA_ROOT=str(media_root))
    contexto.enable()
    importlib.reload(config.urls)
    clear_url_caches()
    try:
        yield
    finally:
        contexto.disable()
        importlib.reload(config.urls)
        clear_url_caches()


class MediaPorDjangoTests(TestCase):
    """Camino `SERVE_MEDIA=True` (ECOM y cualquier despliegue sin nginx)."""

    def setUp(self):
        self.media_root = Path(tempfile.mkdtemp())
        adjuntos = self.media_root / "adjuntos"
        adjuntos.mkdir()
        (adjuntos / "dni_secreto.pdf").write_bytes(CONTENIDO)

    def _get(self):
        with _media_servido_por_django(self.media_root):
            return self.client.get(RUTA_ADJUNTO)

    def test_ciudadano_portal_no_descarga_media(self):
        grupo, _ = Group.objects.get_or_create(name=rbac.GRUPO_CIUDADANO_PORTAL)
        ciudadano = User.objects.create_user("ciudadano_media", password="x")
        ciudadano.groups.add(grupo)
        self.client.force_login(ciudadano)

        respuesta = self._get()

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta["Location"], reverse("portal:home"))

    def test_anonimo_no_descarga_media(self):
        respuesta = self._get()

        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse(settings.LOGIN_URL), respuesta["Location"])

    def test_usuario_de_backoffice_con_sesion_descarga_adjunto(self):
        operador = User.objects.create_user("operador_media", password="x")
        self.client.force_login(operador)

        respuesta = self._get()

        self.assertEqual(respuesta.status_code, 200)
        cuerpo = b"".join(respuesta.streaming_content) if respuesta.streaming else respuesta.content
        self.assertEqual(cuerpo, CONTENIDO)


class NginxNoSirveMediaTests(SimpleTestCase):
    """Camino nginx (icore-srv/DEV): el contrato vive en los archivos de despliegue."""

    def setUp(self):
        self.nginx = (RAIZ / "nginx.conf").read_text(encoding="utf-8")

    def test_nginx_no_tiene_location_media(self):
        self.assertNotIn("location /media/", self.nginx)

    def test_nginx_expone_protected_media_como_internal(self):
        bloques = [b for b in self.nginx.split("location ") if b.startswith("/protected-media/")]
        # Un bloque por server (:80 y :443).
        self.assertEqual(len(bloques), 2)
        for bloque in bloques:
            cuerpo = bloque.split("}")[0]
            self.assertIn("internal;", cuerpo)
            self.assertIn("alias /media/;", cuerpo)

    def test_compose_prod_activa_serve_media_en_web(self):
        compose = (RAIZ / "docker-compose.prod.yml").read_text(encoding="utf-8")
        web = compose.split("  web:", 1)[1].split("\n  websocket:", 1)[0]
        self.assertIn("SERVE_MEDIA=True", web)
