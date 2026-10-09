"""`conversaciones` está apagada: no tiene superficie HTTP, WS ni de UI (G1-01 fase 2).

La app no está en uso (decisión del PM, 29-sep-2026) y su chat público creaba el legajo
de cualquier DNI con el nombre que mandara el cliente. La Ola 0 (#510, Cambio 101)
desmontó las rutas públicas; esto apaga lo que quedaba: las rutas del backoffice, la API,
los dos WebSockets del chat, el menú, la card del inicio y la solapa del legajo.

**Apagar no es borrar:** los modelos, las migraciones, las vistas y los templates siguen
en el repo y las tablas no se tocan. Lo que no existe es la puerta. Los tests de abajo
miden exactamente eso, y el límite: `ws/alertas/` —las alertas sensibles del legajo— se
mudó a `legajos` (RED-13) y **sigue andando** (`legajos/tests/test_ws_alertas_rbac.py`).
"""

from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import NoReverseMatch, reverse

from legajos.models import Ciudadano
from programas.services.solapas import SolapasService

CLAVE = "Clave-Seg-2026x"

#: Las rutas HTTP que publicaba `conversaciones/urls.py` bajo `/conversaciones/`.
RUTAS_DEL_BACKOFFICE = (
    "/conversaciones/",
    "/conversaciones/1/",
    "/conversaciones/1/asignar/",
    "/conversaciones/1/reasignar/",
    "/conversaciones/1/responder/",
    "/conversaciones/1/cerrar/",
    "/conversaciones/metricas/",
    "/conversaciones/configurar-cola/",
    "/conversaciones/asignacion-automatica/",
    "/conversaciones/api/metricas/",
    "/conversaciones/api/estadisticas/",
    "/conversaciones/api/conversacion/1/",
)

#: Los cuatro endpoints de `conversaciones/api_urls.py`, que estaban montados bajo
#: **dos** prefijos (`/api/conversaciones/` y `/conversaciones/api/`).
RUTAS_DE_LA_API = (
    "/api/conversaciones/alertas/count/",
    "/api/conversaciones/alertas/preview/",
    "/api/conversaciones/alertas/marcar-leidos/1/",
    "/api/conversaciones/conversacion/1/",
    "/conversaciones/api/alertas/count/",
    "/conversaciones/api/alertas/preview/",
)


class RutasApagadasTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Superusuario: si algo contestara distinto de 404, no sería por permisos.
        cls.admin = get_user_model().objects.create_superuser(
            username="apagado-admin", password=CLAVE, email="apagado@example.test"
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def test_las_rutas_del_backoffice_no_existen(self):
        for ruta in RUTAS_DEL_BACKOFFICE:
            with self.subTest(ruta=ruta):
                self.assertEqual(self.client.get(ruta).status_code, 404)

    def test_los_endpoints_de_la_api_no_existen(self):
        for ruta in RUTAS_DE_LA_API:
            with self.subTest(ruta=ruta):
                self.assertEqual(self.client.get(ruta).status_code, 404)

    def test_los_dos_namespaces_dejaron_de_resolver(self):
        for nombre in ("conversaciones:lista", "conversaciones:metricas", "conversaciones:configurar_cola"):
            with self.subTest(nombre=nombre):
                with self.assertRaises(NoReverseMatch):
                    reverse(nombre)
        with self.assertRaises(NoReverseMatch):
            reverse("conversaciones_api:alertas_count")


class WebsocketsApagadosTests(TestCase):
    """Los dos WS del chat se fueron del routing; el de alertas quedó.

    `URLRouter` levanta `ValueError` cuando ninguna ruta matchea el path: el handshake
    no llega a ningún consumer. Es «no conecta» en su forma más fuerte.
    """

    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_superuser(
            username="apagado-ws", password=CLAVE, email="apagado-ws@example.test"
        )

    @staticmethod
    def _aplicacion():
        from config.asgi import application

        return application

    def _comunicador(self, path):
        encabezados = [(b"host", b"testserver"), (b"origin", b"http://testserver")]
        return WebsocketCommunicator(self._aplicacion(), path, headers=encabezados)

    @override_settings(ALLOWED_HOSTS=["testserver"])
    def test_los_ws_del_chat_no_tienen_ruta(self):
        for path in ("/ws/conversaciones/", "/ws/conversaciones/7/", "/ws/alertas-conversaciones/"):
            with self.subTest(path=path):

                async def flujo(path=path):
                    comunicador = self._comunicador(path)
                    try:
                        await comunicador.connect()
                    finally:
                        await comunicador.disconnect()

                with self.assertRaises(ValueError):
                    async_to_sync(flujo)()

    @override_settings(ALLOWED_HOSTS=["testserver"])
    def test_el_ws_de_alertas_sigue_ruteado(self):
        """Control: el mismo montaje, con la ruta que **no** se apagó.

        Acá el handshake llega al consumer y este decide (cierra con 4403 porque el
        comunicador no manda cookie de sesión). Lo que importa es que no hay
        `ValueError`: la ruta existe. El RBAC del socket lo mide
        `legajos/tests/test_ws_alertas_rbac.py`.
        """

        async def flujo():
            comunicador = self._comunicador("/ws/alertas/")
            conectado, _ = await comunicador.connect()
            await comunicador.disconnect()
            return conectado

        self.assertFalse(async_to_sync(flujo)())

    def test_el_426_quedo_solo_para_alertas(self):
        """`config/urls.py` contesta 426 en las rutas `ws/` cuando el runtime no es ASGI.

        Tenía cuatro entradas; queda una. Las del chat ahora son 404, como cualquier
        ruta que no existe.
        """
        self.client.force_login(self.usuario)

        self.assertEqual(self.client.get("/ws/alertas/").status_code, 426)
        for path in ("/ws/conversaciones/", "/ws/conversaciones/7/", "/ws/alertas-conversaciones/"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)


class SuperficieDeUiApagadaTests(TestCase):
    """El menú, la card del inicio y la solapa del legajo.

    Se miden con un **superusuario**: tiene `conversacion.operar` y
    `conversacion.configurar` por bypass, así que si algo siguiera condicionado a la
    capacidad, lo vería. No ve nada porque no queda nada.
    """

    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser(
            username="apagado-ui", password=CLAVE, email="apagado-ui@example.test"
        )
        cls.ciudadano = Ciudadano.objects.create(dni="27333444", nombre="Alba", apellido="Ferreyra")

    def setUp(self):
        self.client.force_login(self.admin)

    def test_el_sidebar_no_tiene_ningun_item_de_conversaciones(self):
        html = self.client.get(reverse("core:inicio")).content.decode("utf-8")

        self.assertNotIn("/conversaciones/", html)
        self.assertNotIn("Cola Conversaciones", html)
        self.assertNotIn("Dashboard Conversaciones", html)

    def test_el_inicio_no_arma_la_card_ni_su_contexto(self):
        respuesta = self.client.get(reverse("core:inicio"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertNotIn("conversaciones_sin_asignar", respuesta.context)
        self.assertNotIn("conversaciones_sin_asignar_count", respuesta.context)
        self.assertNotIn("Conversaciones sin asignar", respuesta.content.decode("utf-8"))

    def test_el_shell_no_publica_los_flags_de_conversaciones(self):
        respuesta = self.client.get(reverse("core:inicio"))

        self.assertNotIn("puede_conversaciones", respuesta.context)
        self.assertNotIn("badge_conversaciones", respuesta.context)
        # Lo que el shell sí necesita sigue llegando (RED-13).
        self.assertIn("websockets_enabled", respuesta.context)
        self.assertIn("puede_alertas_sensibles", respuesta.context)

    def test_el_detalle_del_ciudadano_no_tiene_la_solapa(self):
        respuesta = self.client.get(reverse("legajos:ciudadano_detalle", args=[self.ciudadano.pk]))

        self.assertEqual(respuesta.status_code, 200)
        self.assertNotIn("conversaciones_ciudadano", respuesta.context)
        self.assertNotIn('id="tab-conversaciones"', respuesta.content.decode("utf-8"))

    def test_el_servicio_de_solapas_ya_no_declara_conversaciones(self):
        ids = {solapa["id"] for solapa in SolapasService.SOLAPAS_ESTATICAS}

        self.assertNotIn("conversaciones", ids)
        # Control: las vecinas de la lista estática siguen ahí.
        self.assertIn("derivaciones", ids)
        self.assertIn("alertas", ids)

    def test_los_badges_de_solapas_no_consultan_conversaciones(self):
        badges = SolapasService.obtener_badges_ciudadano(self.ciudadano)

        self.assertNotIn("conversaciones", badges)
