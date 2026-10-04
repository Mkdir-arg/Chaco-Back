"""Alertas de ciudadanos: capacidad y alcance (SEC-18 + R0b-06, auditoría oct-2026).

Lo que el barrido de RED-89 midió el 04-oct-2026 con un usuario **sin ningún
rol**: `/legajos/alertas/` le devolvía 59 KB de HTML con el nombre del ciudadano
y el texto de la alerta, `/legajos/alertas/preview/` y `/api/legajos/alertas/`
lo mismo en JSON, y las tres entradas de cierre —`cerrar-ajax/`, `cerrar/` y
`POST /api/legajos/alertas/<id>/cerrar/`— contestaban 200 y dejaban la alerta
ajena en `activa=False`. Con `n = 1..N` eso silencia las alertas de todo el
sistema. Además, un `pk` no numérico en la ruta de DRF daba **500**.

Dos cosas lo cierran: la capacidad (`ciudadano.ver`) y el alcance
(`FiltrosUsuarioService`), que ya no cae en el fallback «todas las CRÍTICAS».
"""

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import Client, TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from core import rbac
from legajos.models import AlertaCiudadano, Ciudadano, LegajoAtencion
from legajos.services import FiltrosUsuarioService
from users.models import Capacidad, RolMeta


def usuario_con(*codigos, username=None):
    """Usuario de backoffice con exactamente esas capacidades (ninguna = sin rol)."""
    usuario = User.objects.create_user(username or f"a-{'-'.join(codigos) or 'sin-rol'}", password="Clave-Seg-2026x")
    if not codigos:
        return usuario
    grupo, _ = Group.objects.get_or_create(name="Rol alertas " + "-".join(codigos))
    RolMeta.objects.get_or_create(grupo=grupo, defaults={"categoria": rbac.CATEGORIA_BACKOFFICE, "activo": True})
    ct = ContentType.objects.get_for_model(Capacidad)
    for codigo in codigos:
        grupo.permissions.add(Permission.objects.get(codename=rbac.codename_de(codigo), content_type=ct))
    usuario.groups.add(grupo)
    return usuario


class AlertasRbacTests(TestCase):
    """Quién puede abrir el dashboard, contar, previsualizar y cerrar."""

    @classmethod
    def setUpTestData(cls):
        cls.mirta = Ciudadano.objects.create(dni="21444555", nombre="Mirta", apellido="Quiroga")
        cls.alerta = AlertaCiudadano.objects.create(
            ciudadano=cls.mirta,
            tipo=AlertaCiudadano.TipoAlerta.RIESGO_SUICIDA,
            prioridad=AlertaCiudadano.Prioridad.CRITICA,
            mensaje="Riesgo suicida detectado en la última entrevista",
        )

    def _cliente(self, usuario):
        cliente = Client()
        cliente.force_login(usuario)
        return cliente

    def test_sin_rol_no_ve_el_dashboard_ni_los_endpoints(self):
        cliente = self._cliente(usuario_con())

        for nombre, args in (
            ("legajos:alertas_dashboard", []),
            ("legajos:alertas_count_ajax", []),
            ("legajos:alertas_preview_ajax", []),
        ):
            with self.subTest(ruta=nombre):
                respuesta = cliente.get(reverse(nombre, args=args), headers={"x-requested-with": "XMLHttpRequest"})
                self.assertEqual(respuesta.status_code, 403)

    def test_sin_rol_no_cierra_una_alerta_ajena(self):
        """El agujero medido: 200 y la alerta de otro quedaba en `activa=False`."""
        cliente = self._cliente(usuario_con())

        for nombre in ("legajos:cerrar_alerta_ajax", "legajos:cerrar_alerta_ciudadano"):
            with self.subTest(ruta=nombre):
                respuesta = cliente.post(
                    reverse(nombre, args=[self.alerta.id]), headers={"x-requested-with": "XMLHttpRequest"}
                )
                self.assertEqual(respuesta.status_code, 403)
                self.alerta.refresh_from_db()
                self.assertTrue(self.alerta.activa)

    def test_con_ciudadano_ver_abre_el_dashboard(self):
        """El rol «Gestión de Ciudadanos» del seed tiene `ciudadano.ver`: sigue entrando."""
        cliente = self._cliente(usuario_con("ciudadano.ver"))

        self.assertEqual(cliente.get(reverse("legajos:alertas_dashboard")).status_code, 200)
        self.assertEqual(cliente.get(reverse("legajos:alertas_count_ajax")).status_code, 200)
        self.assertEqual(cliente.get(reverse("legajos:alertas_preview_ajax")).status_code, 200)

    def test_el_superusuario_abre_el_dashboard(self):
        cliente = self._cliente(User.objects.create_superuser("root-alertas", "root-a@example.test", "x"))

        self.assertEqual(cliente.get(reverse("legajos:alertas_dashboard")).status_code, 200)

    def test_el_anonimo_va_al_login(self):
        respuesta = Client().get(reverse("legajos:alertas_dashboard"))

        self.assertEqual(respuesta.status_code, 302)


class AlertasAlcanceTests(TestCase):
    """Tener `ciudadano.ver` no es ver las alertas de todo el sistema."""

    @classmethod
    def setUpTestData(cls):
        cls.mirta = Ciudadano.objects.create(dni="21444666", nombre="Mirta", apellido="Quiroga")
        cls.responsable = User.objects.create_user("resp-alertas", password="Clave-Seg-2026x")
        cls.legajo = LegajoAtencion.objects.create(responsable=cls.responsable)
        cls.critica = AlertaCiudadano.objects.create(
            ciudadano=cls.mirta,
            legajo=cls.legajo,
            tipo=AlertaCiudadano.TipoAlerta.RIESGO_SUICIDA,
            prioridad=AlertaCiudadano.Prioridad.CRITICA,
            mensaje="Riesgo suicida detectado",
        )

    def test_un_usuario_sin_legajos_no_ve_las_criticas_del_sistema(self):
        """El fallback era `Q(prioridad="CRITICA")`: mostraba todas las críticas
        justo a quien no tiene un solo legajo asignado (SEC-18)."""
        sin_legajos = usuario_con("ciudadano.ver", username="ve-pero-sin-legajos")

        alertas = FiltrosUsuarioService.obtener_alertas_usuario(sin_legajos)

        self.assertEqual(list(alertas), [])
        self.assertEqual(FiltrosUsuarioService.obtener_estadisticas_usuario(sin_legajos)["criticas"], 0)

    def test_el_dashboard_de_un_usuario_sin_legajos_no_nombra_al_ciudadano(self):
        cliente = Client()
        cliente.force_login(usuario_con("ciudadano.ver", username="dash-sin-legajos"))

        html = cliente.get(reverse("legajos:alertas_dashboard")).content.decode()

        self.assertNotIn("Quiroga", html)
        self.assertNotIn("Riesgo suicida detectado", html)

    def test_cerrar_una_alerta_fuera_de_alcance_no_la_cierra(self):
        """Con capacidad pero sin la alerta en su alcance: no la silencia."""
        cliente = Client()
        cliente.force_login(usuario_con("ciudadano.ver", username="cierra-ajena"))

        respuesta = cliente.post(reverse("legajos:cerrar_alerta_ajax", args=[self.critica.id]))

        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(respuesta.json()["success"])
        self.critica.refresh_from_db()
        self.assertTrue(self.critica.activa)

    def test_el_responsable_del_legajo_si_la_cierra(self):
        cliente = Client()
        grupo, _ = Group.objects.get_or_create(name="Rol responsable alertas")
        RolMeta.objects.get_or_create(grupo=grupo, defaults={"categoria": rbac.CATEGORIA_BACKOFFICE, "activo": True})
        ct = ContentType.objects.get_for_model(Capacidad)
        grupo.permissions.add(Permission.objects.get(codename=rbac.codename_de("ciudadano.ver"), content_type=ct))
        self.responsable.groups.add(grupo)
        cliente.force_login(self.responsable)

        respuesta = cliente.post(reverse("legajos:cerrar_alerta_ajax", args=[self.critica.id]))

        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.json()["success"])
        self.critica.refresh_from_db()
        self.assertFalse(self.critica.activa)
        self.assertEqual(self.critica.cerrada_por, self.responsable)

    def test_quien_administra_la_configuracion_sigue_viendo_todo(self):
        """`config.administrar` es el alcance global, previsto en `filtros_usuario`."""
        admin = usuario_con("config.administrar", username="admin-global-alertas")

        self.assertEqual(list(FiltrosUsuarioService.obtener_alertas_usuario(admin)), [self.critica])


class AlertasApiTests(TestCase):
    """`AlertasViewSet`: capacidad (R0b-06) y `get_object()` (el 500 del `pk`)."""

    @classmethod
    def setUpTestData(cls):
        cls.mirta = Ciudadano.objects.create(dni="21444777", nombre="Mirta", apellido="Quiroga")
        cls.responsable = User.objects.create_user("resp-api-alertas", password="Clave-Seg-2026x")
        cls.legajo = LegajoAtencion.objects.create(responsable=cls.responsable)
        cls.alerta = AlertaCiudadano.objects.create(
            ciudadano=cls.mirta,
            legajo=cls.legajo,
            tipo=AlertaCiudadano.TipoAlerta.VIOLENCIA,
            prioridad=AlertaCiudadano.Prioridad.CRITICA,
            mensaje="Situación de violencia reportada",
        )

    def _api(self, usuario):
        cliente = APIClient()
        cliente.force_authenticate(usuario)
        return cliente

    def test_sin_capacidad_no_lista_ni_cuenta(self):
        cliente = self._api(usuario_con(username="api-sin-rol"))

        for url in ("/api/legajos/alertas/", "/api/legajos/alertas/count/"):
            with self.subTest(url=url):
                self.assertEqual(cliente.get(url).status_code, 403)

    def test_sin_capacidad_no_cierra(self):
        cliente = self._api(usuario_con(username="api-sin-rol-cierra"))

        respuesta = cliente.post(f"/api/legajos/alertas/{self.alerta.id}/cerrar/")

        self.assertEqual(respuesta.status_code, 403)
        self.alerta.refresh_from_db()
        self.assertTrue(self.alerta.activa)

    def test_con_pk_no_numerico_da_404_y_no_revienta(self):
        """Antes: `AlertasService.cerrar_alerta` recibía el `pk` crudo → 500."""
        cliente = self._api(usuario_con("ciudadano.ver", username="api-ve-alertas"))

        respuesta = cliente.post("/api/legajos/alertas/x/cerrar/")

        self.assertEqual(respuesta.status_code, 404)

    def test_cerrar_una_alerta_fuera_de_alcance_da_404(self):
        cliente = self._api(usuario_con("ciudadano.ver", username="api-fuera-alcance"))

        respuesta = cliente.post(f"/api/legajos/alertas/{self.alerta.id}/cerrar/")

        self.assertEqual(respuesta.status_code, 404)
        self.alerta.refresh_from_db()
        self.assertTrue(self.alerta.activa)

    def test_el_responsable_cierra_por_la_api(self):
        ct = ContentType.objects.get_for_model(Capacidad)
        grupo, _ = Group.objects.get_or_create(name="Rol api responsable")
        RolMeta.objects.get_or_create(grupo=grupo, defaults={"categoria": rbac.CATEGORIA_BACKOFFICE, "activo": True})
        grupo.permissions.add(Permission.objects.get(codename=rbac.codename_de("ciudadano.ver"), content_type=ct))
        self.responsable.groups.add(grupo)

        respuesta = self._api(self.responsable).post(f"/api/legajos/alertas/{self.alerta.id}/cerrar/")

        self.assertEqual(respuesta.status_code, 200)
        self.alerta.refresh_from_db()
        self.assertFalse(self.alerta.activa)
