"""Ola 5 · PR 7, ronda 2 — G2-04: «Legajos activos» tampoco medía legajos.

La cuarta stat card del inicio dice «Legajos activos · de N legajos en total»,
pero `legajos_activos` y `total_legajos` salían de `dashboard.utils.contar_legajos()`,
que agrega **`InscripcionPrograma`**: inscripciones a un programa, no legajos de
atención. Dos pantallas de la misma sesión se contradecían —el inicio y
`/legajos/reportes/`, que sí cuenta `LegajoAtencion`— y ninguna de las dos estaba
rota: medían cosas distintas con el mismo rótulo.

El rótulo manda (es el defecto que ataca G2-04), así que la tarjeta pasa a contar
`LegajoAtencion` con la **misma** definición de «activo» que usa reportes, y esa
definición vive ahora en un solo lugar: `legajos.selectors.legajos`.

`contar_legajos()` **no se tocó**: `dashboard.views.home.DashboardView` la usa y
RED-51 (Ola 4) tiene dos tests escritos alrededor de que esa clave agrega
inscripciones. El contador nuevo es otro, con su propia clave.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from core import rbac
from legajos.models import LegajoAtencion
from programas.models import InscripcionPrograma, Programa
from users.models import Capacidad, RolMeta


def _crear_legajos(activos, cerrados):
    """`estado` por defecto es ABIERTO; «activo» es todo lo que no esté CERRADO."""
    for _ in range(activos):
        LegajoAtencion.objects.create(estado=LegajoAtencion.Estado.ABIERTO)
    for _ in range(cerrados):
        LegajoAtencion.objects.create(estado=LegajoAtencion.Estado.CERRADO)


def _rol_con(nombre, codigos):
    grupo = Group.objects.create(name=nombre)
    RolMeta.objects.create(grupo=grupo, categoria=rbac.CATEGORIA_BACKOFFICE, activo=True)
    ct = ContentType.objects.get_for_model(Capacidad)
    for codigo in codigos:
        grupo.permissions.add(Permission.objects.get(codename=rbac.codename_de(codigo), content_type=ct))
    return grupo


class ReproDelRevisorTests(TestCase):
    """4 legajos de atención (3 activos) y 5 inscripciones: las dos pantallas coinciden.

    Antes, el inicio decía «Legajos activos 0 · de 5 legajos en total» —las cinco
    inscripciones, ninguna en ACTIVO/EN_SEGUIMIENTO— y `/legajos/reportes/` decía
    «Total 4 · activos 3» en la misma sesión.
    """

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

        _crear_legajos(activos=3, cerrados=1)
        programa = Programa.objects.create(nombre="Inscripciones", codigo="INS")
        from legajos.models import Ciudadano

        for i in range(5):
            ciudadano = Ciudadano.objects.create(dni=f"3011122{i}", nombre=f"N{i}", apellido="Repro")
            InscripcionPrograma.objects.create(ciudadano=ciudadano, programa=programa, estado="PENDIENTE")

        # Un operador real: la capacidad justa de reportes, sin superusuario.
        self.usuario = get_user_model().objects.create_user(username="repro-legajos", password="x")
        self.usuario.groups.add(_rol_con("Reportes (repro)", ["reporte.ver"]))
        self.client.force_login(self.usuario)

    def test_el_inicio_cuenta_legajos_de_atencion_no_inscripciones(self):
        contexto = self.client.get(reverse("core:inicio")).context

        self.assertEqual(contexto["total_legajos"], 4)
        self.assertEqual(contexto["legajos_activos"], 3)

    def test_el_inicio_y_reportes_dan_el_mismo_numero(self):
        inicio = self.client.get(reverse("core:inicio")).context
        reportes = self.client.get(reverse("legajos:reportes")).context["stats"]

        self.assertEqual(inicio["total_legajos"], reportes["total_legajos"])
        self.assertEqual(inicio["legajos_activos"], reportes["legajos_activos"])


class UnaSolaDefinicionDeActivoTests(TestCase):
    """La regla vive en el selector; las dos pantallas la consumen, no la copian."""

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def test_derivado_y_en_seguimiento_cuentan_como_activos(self):
        """«Activo» es *no cerrado*: ABIERTO, EN_SEGUIMIENTO y DERIVADO."""
        from legajos.selectors import resumen_legajos_atencion

        for estado in (
            LegajoAtencion.Estado.ABIERTO,
            LegajoAtencion.Estado.EN_SEGUIMIENTO,
            LegajoAtencion.Estado.DERIVADO,
            LegajoAtencion.Estado.CERRADO,
        ):
            LegajoAtencion.objects.create(estado=estado)

        self.assertEqual(resumen_legajos_atencion(), {"total": 4, "activos": 3})

    def test_reportes_no_vuelve_a_escribir_la_regla(self):
        vista = (
            __import__("pathlib").Path(__file__).resolve().parents[2] / "legajos/views/dashboard_simple.py"
        ).read_text(encoding="utf-8")

        self.assertNotIn('exclude(estado="CERRADO")', vista)
        self.assertIn("legajos_abiertos", vista)

    def test_el_resumen_se_resuelve_en_una_sola_consulta(self):
        from legajos.selectors import resumen_legajos_atencion

        _crear_legajos(activos=2, cerrados=1)

        with self.assertNumQueries(1):
            resumen_legajos_atencion()


class ContadorDeInscripcionesIntactoTests(TestCase):
    """`contar_legajos()` sigue agregando inscripciones, con su clave de siempre.

    Lo exige `dashboard.views.home.DashboardView` (vista tapada, RED-78) y lo dan por
    sentado los dos tests de RED-51 en `dashboard/tests/test_cache_invalidacion.py`.
    """

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def test_contar_legajos_sigue_mirando_inscripciones(self):
        from dashboard.utils import contar_legajos
        from legajos.models import Ciudadano

        programa = Programa.objects.create(nombre="Intacto", codigo="INT")
        ciudadano = Ciudadano.objects.create(dni="30999888", nombre="Sin", apellido="Legajo")
        InscripcionPrograma.objects.create(ciudadano=ciudadano, programa=programa, estado="ACTIVO")
        _crear_legajos(activos=2, cerrados=0)

        self.assertEqual(contar_legajos(), {"total": 1, "activos": 1})

    def test_los_dos_contadores_usan_claves_distintas(self):
        from dashboard.utils import contar_legajos, contar_legajos_atencion

        contar_legajos()
        contar_legajos_atencion()

        self.assertIsNotNone(cache.get("stats_legajos"))
        self.assertIsNotNone(cache.get("stats_legajos_atencion"))

    def test_guardar_un_legajo_invalida_la_clave_nueva(self):
        """Sin esto el inicio queda con el número viejo hasta que expire el TTL."""
        from dashboard.utils import contar_legajos_atencion

        contar_legajos_atencion()

        LegajoAtencion.objects.create()

        self.assertIsNone(cache.get("stats_legajos_atencion"))
