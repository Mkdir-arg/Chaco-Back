"""Las APIs del dashboard exigen capacidad, no solo sesión (SEC-14, auditoría oct-2026).

`/api/buscar-ciudadanos/?q=301` devolvía nombre y DNI del padrón —hasta 20 por
consulta, con `has_more` para saber que hay más— a cualquier usuario autenticado,
sin `ciudadano.ver`. Con prefijos de DNI alcanzaba para enumerar el padrón entero.
Las alertas y la actividad reciente exponían además el alcance global, sin pasar por
`FiltrosUsuarioService`, que es la pieza que acota las alertas al usuario.
"""

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse

from core import rbac
from legajos.models import AlertaCiudadano, Ciudadano
from users.models import Capacidad, RolMeta


def _rol_con(nombre, codigos):
    grupo = Group.objects.create(name=nombre)
    RolMeta.objects.create(grupo=grupo, categoria=rbac.CATEGORIA_BACKOFFICE, activo=True)
    ct = ContentType.objects.get_for_model(Capacidad)
    for codigo in codigos:
        grupo.permissions.add(Permission.objects.get(codename=rbac.codename_de(codigo), content_type=ct))
    return grupo


class BuscarCiudadanosRbacTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.url = reverse("dashboard:api_buscar_ciudadanos")
        Ciudadano.objects.create(dni="30111222", nombre="Ana", apellido="Perez")

    def test_buscar_ciudadanos_sin_capacidad_403(self):
        self.client.force_login(User.objects.create_user("plano-dash", password="Clave-Seg-2026x"))

        respuesta = self.client.get(self.url, {"q": "301"})

        self.assertEqual(respuesta.status_code, 403)
        self.assertNotIn(b"30111222", respuesta.content)

    def test_con_ciudadano_ver_200(self):
        agente = User.objects.create_user("agente-dash", password="Clave-Seg-2026x")
        agente.groups.add(_rol_con("Consulta de ciudadanos", ["ciudadano.ver"]))
        self.client.force_login(agente)

        respuesta = self.client.get(self.url, {"q": "301"})

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["results"][0]["dni"], "30111222")


class AlertasYActividadRbacTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ciudadano = Ciudadano.objects.create(dni="30999888", nombre="Beto", apellido="Gomez")
        AlertaCiudadano.objects.create(
            ciudadano=ciudadano,
            tipo=AlertaCiudadano.TipoAlerta.RIESGO_ALTO,
            prioridad=AlertaCiudadano.Prioridad.CRITICA,
            mensaje="Alerta de prueba",
            activa=True,
        )

    def test_alertas_criticas_sin_capacidad_403(self):
        self.client.force_login(User.objects.create_user("plano-alertas", password="Clave-Seg-2026x"))

        respuesta = self.client.get(reverse("dashboard:api_alertas_criticas"))

        self.assertEqual(respuesta.status_code, 403)

    def test_actividad_reciente_sin_capacidad_403(self):
        self.client.force_login(User.objects.create_user("plano-actividad", password="Clave-Seg-2026x"))

        respuesta = self.client.get(reverse("dashboard:api_actividad_reciente"))

        self.assertEqual(respuesta.status_code, 403)

    def test_alertas_criticas_con_sensible_200(self):
        agente = User.objects.create_user("agente-alertas", password="Clave-Seg-2026x")
        agente.groups.add(_rol_con("Datos sensibles", ["ciudadano.sensible"]))
        self.client.force_login(agente)

        respuesta = self.client.get(reverse("dashboard:api_alertas_criticas"))

        self.assertEqual(respuesta.status_code, 200)

    def test_alertas_criticas_respetan_el_alcance_del_usuario(self):
        # Sin legajos propios, `FiltrosUsuarioService` deja solo las CRÍTICAS: la
        # consulta directa a `AlertaCiudadano` traía también las ALTAS de todos.
        ciudadano = Ciudadano.objects.create(dni="30777666", nombre="Cora", apellido="Diaz")
        AlertaCiudadano.objects.create(
            ciudadano=ciudadano,
            tipo=AlertaCiudadano.TipoAlerta.RIESGO_ALTO,
            prioridad=AlertaCiudadano.Prioridad.ALTA,
            mensaje="Alerta ajena de prioridad alta",
            activa=True,
        )
        agente = User.objects.create_user("agente-alcance", password="Clave-Seg-2026x")
        agente.groups.add(_rol_con("Sensible sin legajos", ["ciudadano.sensible"]))
        self.client.force_login(agente)

        respuesta = self.client.get(reverse("dashboard:api_alertas_criticas"))

        prioridades = {alerta["prioridad"] for alerta in respuesta.json()["results"]}
        self.assertEqual(prioridades, {"CRITICA"})


class MetricasYTendenciasRbacTests(TestCase):
    def test_sin_dashboard_ver_403(self):
        self.client.force_login(User.objects.create_user("plano-metricas", password="Clave-Seg-2026x"))

        for nombre in ("dashboard:api_metricas", "dashboard:api_tendencias"):
            with self.subTest(ruta=nombre):
                self.assertEqual(self.client.get(reverse(nombre)).status_code, 403)

    def test_con_dashboard_ver_200(self):
        agente = User.objects.create_user("agente-metricas", password="Clave-Seg-2026x")
        agente.groups.add(_rol_con("Tablero", ["dashboard.ver"]))
        self.client.force_login(agente)

        for nombre in ("dashboard:api_metricas", "dashboard:api_tendencias"):
            with self.subTest(ruta=nombre):
                self.assertEqual(self.client.get(reverse(nombre)).status_code, 200)


class ApiDashboardSoloBackofficeTests(TestCase):
    """SEC-01 punto 2: el ciudadano del portal no entra ni con sesión."""

    def test_ciudadano_del_portal_no_busca_ciudadanos(self):
        ciudadano = User.objects.create_superuser("30111222", "ciud@example.com", "Clave-Seg-2026x")
        ciudadano.groups.add(Group.objects.create(name=rbac.GRUPO_CIUDADANO_PORTAL))
        self.client.force_login(ciudadano)

        respuesta = self.client.get(reverse("dashboard:api_buscar_ciudadanos"), {"q": "301"})

        # `PortalCiudadanoMiddleware` lo saca antes de llegar a la vista; si alguna vez
        # no estuviera, `BackofficeAutenticado` responde 403.
        self.assertIn(respuesta.status_code, (302, 403))
