"""Las claves JSON que el front del inicio lee a mano están congeladas (RED-42).

Tres endpoints del backoffice devuelven un diccionario cuyas claves **no las
elige nadie**: salen de los kwargs de un `aggregate()` o de un literal perdido en
la vista, y el JavaScript las lee con `data.count || 0`, `data.has_more` o
`data.labels || []`. Renombrar `count=Count("id")` a `total=Count("id")` en
`legajos/views/alertas.py` deja el badge de alertas del navbar en **0 para todo
el backoffice** sin que falle ningún test ni aparezca un error en consola.

Consumidores de cada clave:

- `results` / `has_more` — `templates/inicio.html:909` (buscador del inicio).
- `labels` / `datos` — `templates/inicio.html:938` (gráfico de tendencias).
- `count` / `criticas` — `static/custom/js/alertas_conversaciones_simple.js:47` y
  `static/custom/js/alertas_websocket.js:239`.

El contrato se congela con el conjunto **exacto** de claves: una clave que se va
rompe el front, y una que se agrega sin avisar es una clave que la app móvil o
el WebSocket pueden empezar a leer sin que nadie lo decida.
"""

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
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


def _usuario(nombre, codigos):
    user = User.objects.create_user(nombre, password="Clave-Seg-2026x")
    user.groups.add(_rol_con(f"Rol de {nombre}", codigos))
    return user


class ContratoDashboardTests(TestCase):
    """RED-42: las claves que el front lee a mano no cambian sin romper un test."""

    def setUp(self):
        # `alertas_count_ajax` cachea 30 s por usuario y las métricas 60 s global:
        # entre tests la LocMem sobrevive y el contrato se mediría contra la foto vieja.
        cache.clear()

    def test_buscar_ciudadanos_tiene_results_y_has_more(self):
        Ciudadano.objects.create(dni="30111222", nombre="Ana", apellido="Perez")
        self.client.force_login(_usuario("buscador", ["ciudadano.ver"]))

        cuerpo = self.client.get(reverse("dashboard:api_buscar_ciudadanos"), {"q": "301"}).json()

        self.assertEqual(set(cuerpo), {"results", "has_more"})
        self.assertIs(cuerpo["has_more"], False)
        self.assertEqual(set(cuerpo["results"][0]), {"id", "nombre", "dni"})
        self.assertEqual(cuerpo["results"][0]["nombre"], "Perez, Ana")
        self.assertEqual(cuerpo["results"][0]["dni"], "30111222")

    def test_buscar_ciudadanos_avisa_cuando_hay_mas_de_veinte(self):
        """`has_more` es lo único que distingue «20 resultados» de «hay más»."""
        Ciudadano.objects.bulk_create(
            [Ciudadano(dni=f"3010{i:04d}", nombre=f"N{i}", apellido=f"A{i}") for i in range(21)]
        )
        self.client.force_login(_usuario("buscador-largo", ["ciudadano.ver"]))

        cuerpo = self.client.get(reverse("dashboard:api_buscar_ciudadanos"), {"q": "3010"}).json()

        self.assertIs(cuerpo["has_more"], True)
        self.assertEqual(len(cuerpo["results"]), 20)

    def test_buscar_ciudadanos_con_menos_de_tres_letras_tambien_trae_results(self):
        """El corto sale por otra rama de la vista y el front lee la misma clave."""
        self.client.force_login(_usuario("buscador-corto", ["ciudadano.ver"]))

        cuerpo = self.client.get(reverse("dashboard:api_buscar_ciudadanos"), {"q": "30"}).json()

        self.assertEqual(cuerpo, {"results": []})

    def test_tendencias_tiene_labels_y_datos(self):
        self.client.force_login(_usuario("tablero", ["dashboard.ver"]))

        for periodo, dias in (("7d", 7), ("30d", 30), ("90d", 90), ("inventado", 30)):
            with self.subTest(periodo=periodo):
                cuerpo = self.client.get(reverse("dashboard:api_tendencias"), {"periodo": periodo}).json()

                self.assertEqual(set(cuerpo), {"labels", "datos"})
                self.assertEqual(len(cuerpo["labels"]), dias)
                self.assertEqual(len(cuerpo["datos"]), dias)
                # Chart.js emparea por posición: una lista más larga que la otra
                # corre todo el gráfico un día.
                self.assertTrue(all(isinstance(d, int) for d in cuerpo["datos"]))

    def test_alertas_count_tiene_count_y_criticas(self):
        """Las claves son los kwargs del `aggregate()`: renombrarlos apaga el badge."""
        responsable = _usuario("navbar", ["ciudadano.ver", "ciudadano.sensible"])
        legajo = LegajoAtencion.objects.create(responsable=responsable)
        ciudadano = Ciudadano.objects.create(dni="30999888", nombre="Beto", apellido="Gomez")
        for prioridad in (AlertaCiudadano.Prioridad.CRITICA, AlertaCiudadano.Prioridad.ALTA):
            AlertaCiudadano.objects.create(
                ciudadano=ciudadano,
                legajo=legajo,
                tipo=AlertaCiudadano.TipoAlerta.RIESGO_ALTO,
                prioridad=prioridad,
                mensaje=f"Alerta {prioridad}",
                activa=True,
            )
        self.client.force_login(responsable)

        cuerpo = self.client.get(reverse("legajos:alertas_count_ajax")).json()

        self.assertEqual(set(cuerpo), {"count", "criticas"})
        self.assertEqual(cuerpo["count"], 2)
        self.assertEqual(cuerpo["criticas"], 1)

    def test_alertas_count_sin_alcance_devuelve_los_ceros_con_las_mismas_claves(self):
        """`data.count || 0` tapa un 404 y un cuerpo vacío: el cero tiene que ser real."""
        self.client.force_login(_usuario("navbar-sin-legajos", ["ciudadano.ver", "ciudadano.sensible"]))

        cuerpo = self.client.get(reverse("legajos:alertas_count_ajax")).json()

        self.assertEqual(cuerpo, {"count": 0, "criticas": 0})
