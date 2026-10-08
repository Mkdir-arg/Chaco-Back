"""El shell solo carga el WebSocket de alertas para quien puede conectarlo (G3-03).

`templates/includes/base.html` incluía `alertas_websocket.js` para **todo** el
backoffice con solo mirar `websockets_enabled`. Quien no tiene la capacidad del
socket igual disparaba el handshake y, ante el 4403, cinco reintentos cada 3 s
contra el único daphne; el indicador quedaba en «Desconectado». Con G1c-04 la
capacidad del socket es `ciudadano.sensible`, así que ese es el guard.
"""

from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase, override_settings
from django.urls import reverse

from core import rbac
from users.models import Capacidad, RolMeta

CLAVE = "Clave-Seg-2026x"
JS = Path(settings.BASE_DIR) / "static" / "custom" / "js" / "alertas_websocket.js"


def _usuario_con(*codigos, username=None):
    usuario = User.objects.create_user(username or f"shell-{'-'.join(codigos) or 'sin-rol'}", password=CLAVE)
    if not codigos:
        return usuario
    grupo, _ = Group.objects.get_or_create(name="Rol shell " + "-".join(codigos))
    RolMeta.objects.get_or_create(grupo=grupo, defaults={"categoria": rbac.CATEGORIA_BACKOFFICE, "activo": True})
    ct = ContentType.objects.get_for_model(Capacidad)
    for codigo in codigos:
        grupo.permissions.add(Permission.objects.get(codename=rbac.codename_de(codigo), content_type=ct))
    usuario.groups.add(grupo)
    return usuario


@override_settings(WEBSOCKETS_ENABLED=True)
class AlertasWebsocketEnElShellTests(TestCase):
    def _html(self, usuario):
        self.client.force_login(usuario)
        return self.client.get(reverse("core:inicio")).content.decode()

    def test_sin_capacidad_no_se_incluye_el_script(self):
        """Un usuario de Becas sin `ciudadano.ver` no tiene campana ni socket."""
        html = self._html(_usuario_con())

        self.assertNotIn("alertas_websocket.js", html)
        self.assertNotIn("alertas-campana", html)

    def test_con_ciudadano_ver_viaja_el_script_pero_no_abre_el_socket(self):
        """La campana se refresca por HTTP; el handshake pide `ciudadano.sensible`."""
        html = self._html(_usuario_con("ciudadano.ver", username="shell-solo-ver"))

        self.assertIn("alertas_websocket.js", html)
        self.assertIn("alertas-campana", html)
        self.assertIn("puedeSocket: false", html)

    def test_con_ciudadano_sensible_abre_el_socket(self):
        html = self._html(_usuario_con("ciudadano.ver", "ciudadano.sensible", username="shell-sensible"))

        self.assertIn("alertas_websocket.js", html)
        self.assertIn("puedeSocket: true", html)

    def test_el_superusuario_lo_recibe(self):
        root = User.objects.create_superuser("shell-root", "shell-root@example.test", CLAVE)

        html = self._html(root)

        self.assertIn("alertas_websocket.js", html)
        self.assertIn("puedeSocket: true", html)

    def test_los_flags_viajan_por_el_context_processor(self):
        respuesta = self.client.get(reverse("core:inicio"))  # anónimo: redirige
        self.assertEqual(respuesta.status_code, 302)

        self.client.force_login(_usuario_con("ciudadano.sensible", username="shell-ctx"))
        contexto = self.client.get(reverse("core:inicio")).context

        self.assertTrue(contexto["puede_alertas_sensibles"])
        self.assertFalse(contexto["puede_ver_ciudadanos"])


class AlertasWebsocketReintentosTests(TestCase):
    """El 4403 del consumer es definitivo: reintentarlo es ruido puro (G3-03)."""

    def test_el_js_no_reintenta_tras_un_4403(self):
        fuente = JS.read_text(encoding="utf-8")

        self.assertIn("event.code === 4403", fuente)
        self.assertIn("this.rechazado = true", fuente)
        self.assertIn("if (this.rechazado) return;", fuente)

    def test_el_js_respeta_el_flag_del_shell_antes_de_abrir(self):
        fuente = JS.read_text(encoding="utf-8")

        self.assertIn("puedeAbrirSocket", fuente)
        self.assertIn("puedeSocket", fuente)
