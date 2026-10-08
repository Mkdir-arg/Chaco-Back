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
from legajos.models import AlertaCiudadano, Ciudadano, LegajoAtencion
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
        # El endpoint resuelve por `FiltrosUsuarioService`, no consultando
        # `AlertaCiudadano` directo: así no trae las alertas de todo el sistema.
        #
        # Actualizado por SEC-18 (R-19, Cambio 126): sin legajos propios el
        # alcance ahora es **vacío**. Antes caía en el fallback
        # `Q(prioridad="CRITICA")` y este test afirmaba que veía las CRÍTICAS de
        # todos —que es justo lo que la ficha vino a sacar— mientras filtraba la
        # ALTA ajena. El responsable de un legajo sigue viendo las suyas.
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

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["results"], [])

    def test_alertas_criticas_traen_las_del_legajo_propio_y_no_las_ajenas(self):
        """Contracara del anterior: con alcance, el endpoint sí contesta."""
        responsable = User.objects.create_user("agente-con-legajo", password="Clave-Seg-2026x")
        responsable.groups.add(_rol_con("Sensible con legajos", ["ciudadano.sensible"]))
        propio = Ciudadano.objects.create(dni="30777555", nombre="Dora", apellido="Luna")
        legajo = LegajoAtencion.objects.create(responsable=responsable)
        AlertaCiudadano.objects.create(
            ciudadano=propio,
            legajo=legajo,
            tipo=AlertaCiudadano.TipoAlerta.RIESGO_ALTO,
            prioridad=AlertaCiudadano.Prioridad.CRITICA,
            mensaje="Alerta del legajo propio",
            activa=True,
        )
        self.client.force_login(responsable)

        resultados = self.client.get(reverse("dashboard:api_alertas_criticas")).json()["results"]

        self.assertEqual([alerta["mensaje"] for alerta in resultados], ["Alerta del legajo propio"])


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


class ActividadRecienteAlcanceTests(TestCase):
    """R0b-09: la capacidad tiene que corresponder al contenido del feed.

    El endpoint pedía `ciudadano.sensible` y listaba las últimas inscripciones y
    derivaciones **de todos los programas**, sin pasar por ningún alcance; quien
    solo tenía `ciudadano.ver` —el rol de Legajos sin datos sensibles— no veía
    nada. Ahora el piso es `ciudadano.ver`, las inscripciones y derivaciones
    salen acotadas al alcance del usuario y la rama de alertas solo aparece con
    `ciudadano.sensible` (D-11).
    """

    @classmethod
    def setUpTestData(cls):
        from programas.models import DerivacionPrograma, InscripcionPrograma, Programa

        cls.url = reverse("dashboard:api_actividad_reciente")
        cls.programa_propio = Programa.objects.create(codigo="PROPIO", nombre="Programa propio")
        cls.programa_ajeno = Programa.objects.create(codigo="AJENO", nombre="Programa ajeno")
        cls.vecina = Ciudadano.objects.create(dni="31222333", nombre="Vera", apellido="Nuñez")
        cls.ajena = Ciudadano.objects.create(dni="31444555", nombre="Ajena", apellido="Lopez")

        cls.responsable = User.objects.create_user("agente-actividad", password="Clave-Seg-2026x")
        cls.legajo = LegajoAtencion.objects.create(responsable=cls.responsable)
        InscripcionPrograma.objects.create(ciudadano=cls.vecina, programa=cls.programa_propio, legajo_id=cls.legajo.id)
        InscripcionPrograma.objects.create(ciudadano=cls.ajena, programa=cls.programa_ajeno)
        DerivacionPrograma.objects.create(ciudadano=cls.ajena, programa_destino=cls.programa_ajeno, motivo="ajena")
        AlertaCiudadano.objects.create(
            ciudadano=cls.vecina,
            legajo=cls.legajo,
            tipo=AlertaCiudadano.TipoAlerta.RIESGO_ALTO,
            prioridad=AlertaCiudadano.Prioridad.CRITICA,
            mensaje="Alerta del legajo propio",
            activa=True,
        )

    def _descripciones(self, usuario):
        self.client.force_login(usuario)
        return [item["descripcion"] for item in self.client.get(self.url).json()["results"]]

    def test_sin_capacidad_403(self):
        self.client.force_login(User.objects.create_user("plano-feed", password="Clave-Seg-2026x"))

        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_con_ciudadano_ver_contesta_y_trae_lo_de_su_alcance_sin_alertas(self):
        self.responsable.groups.add(_rol_con("Feed solo ver", ["ciudadano.ver"]))

        descripciones = self._descripciones(self.responsable)

        self.assertTrue(any("Programa propio" in d for d in descripciones))
        self.assertFalse(any("Programa ajeno" in d for d in descripciones))
        self.assertFalse(any(d.startswith("Alerta:") for d in descripciones))

    def test_con_ciudadano_sensible_suma_las_alertas_de_su_alcance(self):
        self.responsable.groups.add(_rol_con("Feed sensible", ["ciudadano.ver", "ciudadano.sensible"]))

        descripciones = self._descripciones(self.responsable)

        self.assertTrue(any(d.startswith("Alerta:") for d in descripciones))
        self.assertFalse(any("Programa ajeno" in d for d in descripciones))

    def test_sin_alcance_el_feed_queda_vacio(self):
        mirona = User.objects.create_user("agente-sin-alcance", password="Clave-Seg-2026x")
        mirona.groups.add(_rol_con("Feed sin alcance", ["ciudadano.ver", "ciudadano.sensible"]))

        self.assertEqual(self._descripciones(mirona), [])

    def test_config_administrar_ve_todo(self):
        """Misma puerta global que usa `FiltrosUsuarioService` para las alertas."""
        admin = User.objects.create_user("agente-config", password="Clave-Seg-2026x")
        admin.groups.add(_rol_con("Feed config", ["ciudadano.ver", "config.administrar"]))

        descripciones = self._descripciones(admin)

        self.assertTrue(any("Programa ajeno" in d for d in descripciones))

    def test_el_ciudadano_del_portal_no_entra(self):
        """`PortalCiudadanoMiddleware` lo saca antes de la vista: 302 a /portal/."""
        portal = User.objects.create_user("32111000", password="Clave-Seg-2026x")
        portal.groups.add(Group.objects.create(name=rbac.GRUPO_CIUDADANO_PORTAL))
        self.client.force_login(portal)

        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(respuesta["Location"].startswith("/portal/"))

    def test_el_superusuario_ve_todo(self):
        root = User.objects.create_superuser("root-feed", "root-feed@example.test", "Clave-Seg-2026x")

        self.assertTrue(any("Programa ajeno" in d for d in self._descripciones(root)))

    def test_el_anonimo_no_entra(self):
        self.assertEqual(self.client.get(self.url).status_code, 403)
