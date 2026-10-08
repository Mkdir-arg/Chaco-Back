"""`/ws/alertas/`: origen, sesión, capacidad y alcance (G1c-04 y G1c-17).

La PoC `poc/test_repro_admin_cron_renaper.py::G1c04WsAlertasTests` medía cuatro
agujeros sobre el mismo socket, y este módulo los invierte uno por uno:

a. difundía a todo el grupo `alertas_sistema` la alerta de **cualquier**
   ciudadano, incluso a quien por HTTP no la ve (`FiltrosUsuarioService`);
b. un socket ya abierto seguía recibiendo después de quitarle el rol;
c. conectaba con una sesión que el backoffice ya había reemplazado
   (`BackofficeSingleSessionMiddleware`) o con la clave provisoria sin cambiar;
d. aceptaba el handshake con cualquier `Origin` (CSWSH).

Más G1c-17: el emisor mandaba la rama crítica al grupo `alertas_criticas` con
el tipo `nueva_alerta_critica`, que no existe en ningún consumer; el modal del
front no se disparaba nunca.

Los tests corren el `application` de `config/asgi.py` con el
`WebsocketCommunicator` de Channels: no hace falta daphne ni `runserver`.
"""

from asgiref.sync import async_to_sync, sync_to_async
from channels.testing import WebsocketCommunicator
from django.conf import settings
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.test import TestCase, override_settings

from core import rbac
from legajos.models import AlertaCiudadano, Ciudadano, LegajoAtencion
from legajos.services.alertas import AlertasService
from users.models import Capacidad, Profile, RolMeta

CLAVE = "Clave-Seg-2026x"


def _rol(nombre, codigos):
    grupo, _ = Group.objects.get_or_create(name=nombre)
    RolMeta.objects.get_or_create(grupo=grupo, defaults={"categoria": rbac.CATEGORIA_BACKOFFICE, "activo": True})
    ct = ContentType.objects.get_for_model(Capacidad)
    for codigo in codigos:
        grupo.permissions.add(Permission.objects.get(codename=rbac.codename_de(codigo), content_type=ct))
    return grupo


def _aplicacion():
    from config.asgi import application

    return application


@override_settings(ALLOWED_HOSTS=["testserver"])
class WsAlertasRbacTests(TestCase):
    def setUp(self):
        cache.clear()
        self.ciudadano = Ciudadano.objects.create(dni="20111222", nombre="Persona", apellido="Ajena")
        self.usuario = User.objects.create_user("ws-operador", password=CLAVE)
        self.usuario.groups.add(_rol("Rol ws sensible", ["ciudadano.ver", "ciudadano.sensible"]))
        self.client.force_login(self.usuario)
        self.cookie = f"{settings.SESSION_COOKIE_NAME}={self.client.session.session_key}".encode()
        Profile.objects.update_or_create(
            user=self.usuario,
            defaults={"backoffice_session_key": self.client.session.session_key},
        )

    def _comunicador(self, cookie=None, origin=b"http://testserver"):
        encabezados = [(b"host", b"testserver"), (b"origin", origin)]
        if cookie is not None:
            encabezados.append((b"cookie", cookie))
        return WebsocketCommunicator(_aplicacion(), "/ws/alertas/", headers=encabezados)

    def _conecta(self, **kwargs):
        async def flujo():
            com = self._comunicador(**kwargs)
            ok, _ = await com.connect()
            await com.disconnect()
            return ok

        return async_to_sync(flujo)()

    # ----------------------------------------------------------------- (d) origen
    def test_origin_ajeno_no_conecta(self):
        self.assertFalse(self._conecta(cookie=self.cookie, origin=b"https://evil.example"))

    def test_origin_propio_conecta(self):
        self.assertTrue(self._conecta(cookie=self.cookie))

    # ------------------------------------------------------------ capacidades
    def test_el_anonimo_no_conecta(self):
        self.assertFalse(self._conecta(cookie=None))

    def test_sin_rol_no_conecta(self):
        otro = User.objects.create_user("ws-sin-rol", password=CLAVE)
        self.client.force_login(otro)
        cookie = f"{settings.SESSION_COOKIE_NAME}={self.client.session.session_key}".encode()
        Profile.objects.update_or_create(
            user=otro, defaults={"backoffice_session_key": self.client.session.session_key}
        )

        self.assertFalse(self._conecta(cookie=cookie))

    def test_con_ciudadano_ver_solo_no_conecta(self):
        """D-11: el contenido de la alerta es sensible; `ciudadano.ver` no alcanza."""
        otro = User.objects.create_user("ws-solo-ver", password=CLAVE)
        otro.groups.add(_rol("Rol ws solo ver", ["ciudadano.ver"]))
        self.client.force_login(otro)
        cookie = f"{settings.SESSION_COOKIE_NAME}={self.client.session.session_key}".encode()
        Profile.objects.update_or_create(
            user=otro, defaults={"backoffice_session_key": self.client.session.session_key}
        )

        self.assertFalse(self._conecta(cookie=cookie))

    def test_el_ciudadano_del_portal_no_conecta(self):
        ciudadano = User.objects.create_user("ws-portal", password=CLAVE)
        grupo, _ = Group.objects.get_or_create(name=rbac.GRUPO_CIUDADANO_PORTAL)
        ciudadano.groups.add(grupo)
        self.client.force_login(ciudadano)
        cookie = f"{settings.SESSION_COOKIE_NAME}={self.client.session.session_key}".encode()
        Profile.objects.update_or_create(
            user=ciudadano, defaults={"backoffice_session_key": self.client.session.session_key}
        )

        self.assertFalse(self._conecta(cookie=cookie))

    def test_el_superusuario_conecta(self):
        root = User.objects.create_superuser("ws-root", "ws-root@example.test", CLAVE)
        self.client.force_login(root)
        cookie = f"{settings.SESSION_COOKIE_NAME}={self.client.session.session_key}".encode()
        Profile.objects.update_or_create(
            user=root, defaults={"backoffice_session_key": self.client.session.session_key}
        )

        self.assertTrue(self._conecta(cookie=cookie))

    # --------------------------------------------------------------- (c) sesión
    def test_sesion_reemplazada_no_conecta(self):
        Profile.objects.filter(user=self.usuario).update(backoffice_session_key="otra-sesion")

        self.assertFalse(self._conecta(cookie=self.cookie))

    def test_clave_provisoria_sin_cambiar_no_conecta(self):
        Profile.objects.filter(user=self.usuario).update(debe_cambiar_contrasena=True)

        self.assertFalse(self._conecta(cookie=self.cookie))

    # --------------------------------------------------------------- (a) alcance
    def test_no_entrega_una_alerta_fuera_del_alcance(self):
        def crear_y_emitir():
            alerta = AlertaCiudadano.objects.create(
                ciudadano=self.ciudadano, tipo="RIESGO_SUICIDA", prioridad="CRITICA", mensaje="riesgo"
            )
            AlertasService._enviar_notificacion_alerta(alerta)
            return alerta.pk

        async def flujo():
            com = self._comunicador(cookie=self.cookie)
            ok, _ = await com.connect()
            await sync_to_async(crear_y_emitir)()
            nada = await com.receive_nothing(timeout=1)
            await com.disconnect()
            return ok, nada

        conectado, no_recibio_nada = async_to_sync(flujo)()
        self.assertTrue(conectado)
        self.assertTrue(no_recibio_nada)

    def test_entrega_una_alerta_del_alcance(self):
        def crear_y_emitir():
            legajo = LegajoAtencion.objects.create(responsable=self.usuario)
            alerta = AlertaCiudadano.objects.create(
                ciudadano=self.ciudadano, legajo=legajo, tipo="SIN_CONTACTO", prioridad="MEDIA", mensaje="m"
            )
            AlertasService._enviar_notificacion_alerta(alerta)
            return alerta.pk

        async def flujo():
            com = self._comunicador(cookie=self.cookie)
            await com.connect()
            pk = await sync_to_async(crear_y_emitir)()
            mensaje = await com.receive_json_from(timeout=3)
            await com.disconnect()
            return pk, mensaje

        pk, mensaje = async_to_sync(flujo)()
        self.assertEqual(mensaje["type"], "nueva_alerta")
        self.assertEqual(mensaje["alerta"]["id"], pk)

    # ------------------------------------------------------- (b) revalidación
    def test_quitarle_el_rol_corta_el_socket_abierto(self):
        def preparar():
            return LegajoAtencion.objects.create(responsable=self.usuario)

        def crear_y_emitir(legajo, tipo):
            alerta = AlertaCiudadano.objects.create(
                ciudadano=self.ciudadano, legajo=legajo, tipo=tipo, prioridad="BAJA", mensaje="m"
            )
            AlertasService._enviar_notificacion_alerta(alerta)
            return alerta.pk

        def quitar_rol():
            self.usuario.groups.clear()
            cache.clear()
            return rbac.puede(User.objects.get(pk=self.usuario.pk), "ciudadano.sensible")

        async def flujo():
            com = self._comunicador(cookie=self.cookie)
            await com.connect()
            legajo = await sync_to_async(preparar)()
            await sync_to_async(crear_y_emitir)(legajo, "SIN_CONTACTO")
            primero = await com.receive_json_from(timeout=3)
            sigue = await sync_to_async(quitar_rol)()
            await sync_to_async(crear_y_emitir)(legajo, "SIN_EVALUACION")
            salida = await com.receive_output(timeout=3)
            await com.disconnect()
            return primero, sigue, salida

        primero, sigue, salida = async_to_sync(flujo)()
        self.assertEqual(primero["type"], "nueva_alerta")
        self.assertFalse(sigue)
        # Revalidación en la entrega: el socket se cierra con 4403 en vez de
        # seguir recibiendo con un rol que ya no existe.
        self.assertEqual(salida["type"], "websocket.close")
        self.assertEqual(salida["code"], 4403)

    # ------------------------------------------------------------------ G1c-17
    def test_la_alerta_critica_del_alcance_dispara_el_modal(self):
        """El emisor y el consumer hablan el mismo idioma (G1c-17)."""

        def crear_y_emitir():
            legajo = LegajoAtencion.objects.create(responsable=self.usuario)
            alerta = AlertaCiudadano.objects.create(
                ciudadano=self.ciudadano, legajo=legajo, tipo="RIESGO_SUICIDA", prioridad="CRITICA", mensaje="riesgo"
            )
            AlertasService._enviar_notificacion_alerta(alerta)
            return alerta.pk

        async def flujo():
            com = self._comunicador(cookie=self.cookie)
            await com.connect()
            pk = await sync_to_async(crear_y_emitir)()
            uno = await com.receive_json_from(timeout=3)
            dos = await com.receive_json_from(timeout=3)
            await com.disconnect()
            return pk, [uno, dos]

        pk, mensajes = async_to_sync(flujo)()
        tipos = {mensaje["type"] for mensaje in mensajes}
        self.assertEqual(tipos, {"nueva_alerta", "alerta_critica"})
        for mensaje in mensajes:
            self.assertEqual(mensaje["alerta"]["id"], pk)

    def test_la_alerta_critica_fuera_del_alcance_tampoco_llega(self):
        def crear_y_emitir():
            alerta = AlertaCiudadano.objects.create(
                ciudadano=self.ciudadano, tipo="RIESGO_SUICIDA", prioridad="CRITICA", mensaje="riesgo"
            )
            AlertasService._enviar_notificacion_alerta(alerta)
            return alerta.pk

        async def flujo():
            com = self._comunicador(cookie=self.cookie)
            await com.connect()
            await sync_to_async(crear_y_emitir)()
            nada = await com.receive_nothing(timeout=1)
            await com.disconnect()
            return nada

        self.assertTrue(async_to_sync(flujo)())
