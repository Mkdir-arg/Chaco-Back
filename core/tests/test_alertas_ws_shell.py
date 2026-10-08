"""El shell solo carga el WebSocket de alertas para quien puede conectarlo (G3-03).

`templates/includes/base.html` incluía `alertas_websocket.js` para **todo** el
backoffice con solo mirar `websockets_enabled`. Quien no tiene la capacidad del
socket igual disparaba el handshake y, ante el 4403, cinco reintentos cada 3 s
contra el único daphne; el indicador quedaba en «Desconectado». Con G1c-04 la
capacidad del socket es `ciudadano.sensible`, así que ese es el guard.

Desde la ronda 2 del PR #629 el guard es **uno solo**: D-11 subió también la
campana del navbar, el contador y el preview a `ciudadano.sensible`, así que la
única superficie del script y el socket piden lo mismo. Quien no la tiene no ve
campana, ni punto de estado, ni script.
"""

from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase, override_settings
from django.urls import reverse

from core import rbac
from core.tests.js_harness import correr_script, requiere_node, sin_comentarios
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
        """Un usuario de Becas sin `ciudadano.sensible` no tiene campana ni socket."""
        html = self._html(_usuario_con())

        self.assertNotIn("alertas_websocket.js", html)
        self.assertNotIn("alertas-campana", html)
        self.assertNotIn("websocket-status", html)

    def test_con_ciudadano_ver_solo_tampoco_hay_campana_ni_script(self):
        """D-11: el «Operador de backoffice» pierde la campana de alertas."""
        html = self._html(_usuario_con("ciudadano.ver", username="shell-solo-ver"))

        self.assertNotIn("alertas_websocket.js", html)
        self.assertNotIn("alertas-campana", html)
        self.assertNotIn("websocket-status", html)

    def test_con_ciudadano_sensible_hay_campana_y_script(self):
        html = self._html(_usuario_con("ciudadano.ver", "ciudadano.sensible", username="shell-sensible"))

        self.assertIn("alertas_websocket.js", html)
        self.assertIn("alertas-campana", html)
        self.assertIn("websocket-status", html)

    def test_el_superusuario_lo_recibe(self):
        root = User.objects.create_superuser("shell-root", "shell-root@example.test", CLAVE)

        html = self._html(root)

        self.assertIn("alertas_websocket.js", html)
        self.assertIn("alertas-campana", html)

    def test_el_flag_viaja_por_el_context_processor(self):
        respuesta = self.client.get(reverse("core:inicio"))  # anónimo: redirige
        self.assertEqual(respuesta.status_code, 302)

        self.client.force_login(_usuario_con("ciudadano.sensible", username="shell-ctx"))
        contexto = self.client.get(reverse("core:inicio")).context

        self.assertTrue(contexto["puede_alertas_sensibles"])


class AlertasWebsocketReintentosTests(TestCase):
    """El 4403 del consumer es definitivo: reintentarlo es ruido puro (G3-03)."""

    def test_el_js_no_reintenta_tras_un_4403(self):
        fuente = JS.read_text(encoding="utf-8")

        self.assertIn("event.code === 4403", fuente)
        self.assertIn("this.rechazado = true", fuente)
        self.assertIn("if (this.rechazado) return;", fuente)

    def test_el_js_no_tiene_su_propio_guard_de_capacidad(self):
        """Un solo guard, y vive en el shell: el JS ya no mira `puedeSocket`."""
        fuente = sin_comentarios(JS.read_text(encoding="utf-8"))

        self.assertNotIn("puedeSocket", fuente)
        self.assertNotIn("puedeAbrirSocket", fuente)


# Stubs de lo que el navegador le da a `alertas_websocket.js` y el DOM mínimo del
# harness no trae. Se suman al prelude, antes del archivo bajo prueba.
_STUBS = """
__log.toasts = [];
__log.sonidos = [];
__log.contadores = [];
__log.titulos = [];
var Notification = function () {};
Notification.permission = 'denied';
var Audio = function () { __log.sonidos.push('alert.mp3'); return {volume: 0, play: function () { return {catch: function () {}}; }}; };
var WebSocket = function () { return {}; };
window.toast = function (tipo, texto) { __log.toasts.push([tipo, texto]); };
window.ModernModal = ModernModal;
window.alertasConfig = {ciudadanoDetalleUrlTemplate: '/legajos/ciudadanos/0/'};
"""

_ALERTA = "{id: 7, prioridad: 'CRITICA', ciudadano: 'Mirta', mensaje: 'riesgo', fecha: 'hoy', ciudadano_id: 3}"


class AlertaCriticaSinDuplicarTests(TestCase):
    """Una alerta crítica = un modal, un sonido, un refresco del contador.

    El emisor mandaba `nueva_alerta` **y** `alerta_critica` sobre el mismo grupo:
    el cliente corría las dos ramas, así que la crítica salía como toast *y* como
    modal, el sonido sonaba dos veces y el contador se refrescaba dos veces. Ahora
    el servidor manda un solo mensaje y la forma del aviso la decide la prioridad.
    """

    def _correr(self, alerta_js):
        fuente = JS.read_text(encoding="utf-8")
        acciones = f"""
        var ws = Object.create(AlertasWebSocket.prototype);
        ws.updateAlertasCounter = function () {{ __log.contadores.push(1); }};
        ws.blinkTitle = function (t) {{ __log.titulos.push(t); }};
        ws.handleMessage({{type: 'nueva_alerta', alerta: {alerta_js}}});
        """
        return correr_script(_STUBS + "\n" + fuente, acciones)

    @requiere_node
    def test_la_critica_abre_el_modal_una_sola_vez_y_sin_toast(self):
        log = self._correr(_ALERTA)

        self.assertEqual(len(log["modal"]), 1)
        self.assertEqual(log["toasts"], [])
        self.assertEqual(len(log["sonidos"]), 1)
        self.assertEqual(len(log["contadores"]), 1)
        self.assertEqual(len(log["titulos"]), 1)

    @requiere_node
    def test_la_no_critica_sale_como_toast_sin_modal_ni_sonido(self):
        log = self._correr(_ALERTA.replace("CRITICA", "MEDIA"))

        self.assertEqual(log["modal"], [])
        self.assertEqual(len(log["toasts"]), 1)
        self.assertEqual(log["sonidos"], [])
        self.assertEqual(len(log["contadores"]), 1)

    def test_el_js_ya_no_tiene_handler_del_mensaje_critico(self):
        """El tipo `alerta_critica` no existe más: ni emisor, ni consumer, ni cliente."""
        fuente = sin_comentarios(JS.read_text(encoding="utf-8"))

        self.assertNotIn("alerta_critica", fuente)
