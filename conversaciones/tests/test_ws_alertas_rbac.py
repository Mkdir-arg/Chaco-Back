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
front no se disparaba nunca. La ronda 2 del PR #629 cerró la otra mitad: el
emisor manda **un solo** mensaje por alerta y la forma del aviso la decide el
cliente por prioridad, así que la crítica dejó de llegar duplicada.

Y la revalidación dejó de ser por entrega: el alcance se resuelve una vez por
ventana y se cachea en el socket (`VentanaDeRevalidacionTests`).

Los tests corren el `application` de `config/asgi.py` con el
`WebsocketCommunicator` de Channels: no hace falta daphne ni `runserver`.
"""

from unittest import mock

from asgiref.sync import async_to_sync, sync_to_async
from channels.testing import WebsocketCommunicator
from django.conf import settings
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext

from conversaciones.consumers import AlertasConsumer
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
        # El alcance se resuelve al conectar y vale una ventana: los legajos propios
        # del usuario existen **antes** del handshake, como en producción.
        self.legajo = LegajoAtencion.objects.create(responsable=self.usuario)
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
            alerta = AlertaCiudadano.objects.create(
                ciudadano=self.ciudadano, legajo=self.legajo, tipo="SIN_CONTACTO", prioridad="MEDIA", mensaje="m"
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
    @override_settings(ALERTAS_WS_VENTANA_REVALIDACION=0)
    def test_quitarle_el_rol_corta_el_socket_abierto(self):
        """Con la ventana en 0 cada entrega revalida: es el peor caso de latencia.

        Con la ventana real (60 s) el corte llega al vencer, no en el acto; eso
        es lo que declara ``AlertasConsumer.VENTANA_REVALIDACION``.
        """

        def crear_y_emitir(tipo):
            alerta = AlertaCiudadano.objects.create(
                ciudadano=self.ciudadano, legajo=self.legajo, tipo=tipo, prioridad="BAJA", mensaje="m"
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
            await sync_to_async(crear_y_emitir)("SIN_CONTACTO")
            primero = await com.receive_json_from(timeout=3)
            sigue = await sync_to_async(quitar_rol)()
            await sync_to_async(crear_y_emitir)("SIN_EVALUACION")
            salida = await com.receive_output(timeout=3)
            await com.disconnect()
            return primero, sigue, salida

        primero, sigue, salida = async_to_sync(flujo)()
        self.assertEqual(primero["type"], "nueva_alerta")
        self.assertFalse(sigue)
        # Revalidación al vencer la ventana: el socket se cierra con 4403 en vez
        # de seguir recibiendo con un rol que ya no existe.
        self.assertEqual(salida["type"], "websocket.close")
        self.assertEqual(salida["code"], 4403)

    @override_settings(ALERTAS_WS_VENTANA_REVALIDACION=0)
    def test_reemplazarle_la_sesion_corta_el_socket_abierto(self):
        """Cerrar sesión (o loguearse en otro lado) también corta dentro de la ventana."""

        def emitir():
            alerta = AlertaCiudadano.objects.create(
                ciudadano=self.ciudadano, legajo=self.legajo, tipo="SIN_CONTACTO", prioridad="BAJA", mensaje="m"
            )
            AlertasService._enviar_notificacion_alerta(alerta)

        def reemplazar_sesion():
            Profile.objects.filter(user=self.usuario).update(backoffice_session_key="otra-sesion")

        async def flujo():
            com = self._comunicador(cookie=self.cookie)
            await com.connect()
            await sync_to_async(reemplazar_sesion)()
            await sync_to_async(emitir)()
            salida = await com.receive_output(timeout=3)
            await com.disconnect()
            return salida

        salida = async_to_sync(flujo)()
        self.assertEqual(salida["type"], "websocket.close")
        self.assertEqual(salida["code"], 4403)

    # ------------------------------------------------------------------ G1c-17
    def test_la_alerta_critica_del_alcance_llega_una_sola_vez(self):
        """Un alta = **un** mensaje, también si es CRÍTICA.

        G1c-17 arregló el grupo y el tipo de la rama crítica, pero la dejó como
        un segundo `group_send` sobre el mismo grupo: el cliente mostraba toast
        *y* modal, con el sonido y el refresco del contador duplicados.
        """

        def crear_y_emitir():
            alerta = AlertaCiudadano.objects.create(
                ciudadano=self.ciudadano,
                legajo=self.legajo,
                tipo="RIESGO_SUICIDA",
                prioridad="CRITICA",
                mensaje="riesgo",
            )
            AlertasService._enviar_notificacion_alerta(alerta)
            return alerta.pk

        async def flujo():
            com = self._comunicador(cookie=self.cookie)
            await com.connect()
            pk = await sync_to_async(crear_y_emitir)()
            uno = await com.receive_json_from(timeout=3)
            nada_mas = await com.receive_nothing(timeout=1)
            await com.disconnect()
            return pk, uno, nada_mas

        pk, mensaje, nada_mas = async_to_sync(flujo)()
        self.assertEqual(mensaje["type"], "nueva_alerta")
        self.assertEqual(mensaje["alerta"]["id"], pk)
        self.assertEqual(mensaje["alerta"]["prioridad"], "CRITICA")
        self.assertTrue(nada_mas)

    def test_el_emisor_manda_un_solo_group_send_por_alerta_critica(self):
        """El mismo contrato visto desde el emisor, sin socket de por medio."""
        enviados = []

        class CapaFalsa:
            async def group_send(self, grupo, evento):
                enviados.append((grupo, evento["type"]))

        alerta = AlertaCiudadano.objects.create(
            ciudadano=self.ciudadano, legajo=self.legajo, tipo="RIESGO_SUICIDA", prioridad="CRITICA", mensaje="riesgo"
        )
        with mock.patch("legajos.services.alertas.get_channel_layer", return_value=CapaFalsa()):
            AlertasService._enviar_notificacion_alerta(alerta)

        self.assertEqual(enviados, [("alertas_sistema", "nueva_alerta")])

    def test_el_ruteo_no_viaja_al_cliente(self):
        """Los datos de alcance son de servidor: el navegador no los ve."""

        def crear_y_emitir():
            alerta = AlertaCiudadano.objects.create(
                ciudadano=self.ciudadano, legajo=self.legajo, tipo="SIN_CONTACTO", prioridad="MEDIA", mensaje="m"
            )
            AlertasService._enviar_notificacion_alerta(alerta)

        async def flujo():
            com = self._comunicador(cookie=self.cookie)
            await com.connect()
            await sync_to_async(crear_y_emitir)()
            mensaje = await com.receive_json_from(timeout=3)
            await com.disconnect()
            return mensaje

        mensaje = async_to_sync(flujo)()
        self.assertNotIn("ruteo", mensaje)
        self.assertNotIn("responsable_id", mensaje["alerta"])

    def test_el_cierre_de_una_alerta_del_alcance_llega(self):
        """`alerta_cerrada` tiene productor y ya no lo tapa el filtro `activa=True`."""

        def crear():
            return AlertaCiudadano.objects.create(
                ciudadano=self.ciudadano, legajo=self.legajo, tipo="SIN_CONTACTO", prioridad="MEDIA", mensaje="m"
            )

        def cerrar(alerta_id):
            return AlertasService.cerrar_alerta(alerta_id, self.usuario)

        async def flujo():
            alerta = await sync_to_async(crear)()
            com = self._comunicador(cookie=self.cookie)
            await com.connect()
            cerrada = await sync_to_async(cerrar)(alerta.pk)
            mensaje = await com.receive_json_from(timeout=3)
            await com.disconnect()
            return alerta.pk, cerrada, mensaje

        pk, cerrada, mensaje = async_to_sync(flujo)()
        self.assertTrue(cerrada)
        self.assertEqual(mensaje, {"type": "alerta_cerrada", "alerta_id": pk})

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


@override_settings(ALLOWED_HOSTS=["testserver"])
class VentanaDeRevalidacionTests(TestCase):
    """Entregar no cuesta consultas dentro de la ventana (G1c-04 + PERF).

    Antes, cada entrega llamaba a
    ``FiltrosUsuarioService.obtener_alertas_usuario(user).filter(pk=…).exists()``
    más la relectura del usuario y del ``Profile``: **5 consultas por alerta y
    por socket**, con tres ``IN`` anidados sobre las 40k inscripciones. La
    pasada horaria de ``generar_alertas`` redifunde todo de golpe, así que con
    N alertas × M sockets eso era 5·N·M contra un ``read_timeout`` de 10 s.

    Acá se mide lo que importa: el alcance se resuelve **una vez** y las
    entregas siguientes no vuelven a la base.
    """

    ENTREGAS = 10

    def setUp(self):
        cache.clear()
        self.usuario = User.objects.create_user("ws-ventana", password=CLAVE)
        self.usuario.groups.add(_rol("Rol ws ventana", ["ciudadano.sensible"]))
        self.legajo = LegajoAtencion.objects.create(responsable=self.usuario)
        self.client.force_login(self.usuario)
        Profile.objects.update_or_create(
            user=self.usuario, defaults={"backoffice_session_key": self.client.session.session_key}
        )

    def _consumer(self):
        """Un consumer con el scope del handshake y ``send`` capturado."""
        consumer = AlertasConsumer()
        consumer.scope = {"user": User.objects.get(pk=self.usuario.pk), "session": self.client.session}
        consumer._alcance = None
        consumer._alcance_vence = 0.0
        consumer.enviados = []

        async def enviar(text_data=None, **kwargs):
            consumer.enviados.append(text_data)

        consumer.send = enviar
        return consumer

    def _evento(self, n, responsable_id):
        return {
            "type": "nueva_alerta",
            "alerta": {"id": n, "prioridad": "MEDIA", "mensaje": "m", "ciudadano": "X"},
            "ruteo": {"responsable_id": responsable_id, "programa_ids": []},
        }

    def test_n_entregas_en_la_ventana_no_vuelven_a_la_base(self):
        consumer = self._consumer()
        self.assertTrue(async_to_sync(consumer.refrescar_alcance)())  # el alcance del handshake

        with CaptureQueriesContext(connection) as consultas:
            for n in range(self.ENTREGAS):
                async_to_sync(consumer._entregar)(
                    {"type": "nueva_alerta", "alerta": {"id": n}},
                    self._evento(n, self.usuario.pk),
                )

        self.assertEqual(len(consumer.enviados), self.ENTREGAS)
        self.assertLessEqual(len(consultas), 2, f"{len(consultas)} consultas para {self.ENTREGAS} entregas")

    def test_fuera_del_alcance_tampoco_consulta(self):
        otro = User.objects.create_user("ws-ventana-otro", password=CLAVE)
        consumer = self._consumer()
        self.assertTrue(async_to_sync(consumer.refrescar_alcance)())

        with CaptureQueriesContext(connection) as consultas:
            for n in range(self.ENTREGAS):
                async_to_sync(consumer._entregar)(
                    {"type": "nueva_alerta", "alerta": {"id": n}},
                    self._evento(n, otro.pk),
                )

        self.assertEqual(consumer.enviados, [])
        self.assertLessEqual(len(consultas), 2)

    @override_settings(ALERTAS_WS_VENTANA_REVALIDACION=0)
    def test_con_la_ventana_vencida_cada_entrega_revalida(self):
        """El contraste: sin ventana, el costo vuelve a ser por entrega."""
        consumer = self._consumer()
        self.assertTrue(async_to_sync(consumer.refrescar_alcance)())

        with CaptureQueriesContext(connection) as consultas:
            async_to_sync(consumer._entregar)(
                {"type": "nueva_alerta", "alerta": {"id": 1}},
                self._evento(1, self.usuario.pk),
            )

        self.assertEqual(len(consumer.enviados), 1)
        self.assertGreater(len(consultas), 0)
