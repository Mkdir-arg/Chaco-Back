"""La home no muestra piezas que el usuario no puede consumir (SEC-14, auditoría oct-2026).

`/inicio/` la ve cualquier usuario autenticado del backoffice, pero sus paneles se
alimentan de APIs que ahora piden capacidad. Una pieza que se dibuja sin la
capacidad es un control muerto: el buscador pegaba a `/api/buscar-ciudadanos/`,
recibía 403 y vaciaba la lista en silencio, sin aviso ni error en consola.
"""

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from core import rbac
from users.models import Capacidad, RolMeta


def _rol_con(nombre, codigos):
    grupo = Group.objects.create(name=nombre)
    RolMeta.objects.create(grupo=grupo, categoria=rbac.CATEGORIA_BACKOFFICE, activo=True)
    ct = ContentType.objects.get_for_model(Capacidad)
    for codigo in codigos:
        grupo.permissions.add(Permission.objects.get(codename=rbac.codename_de(codigo), content_type=ct))
    return grupo


class InicioSinCapacidadesTests(TestCase):
    """Un rol de menú acotado (p. ej. «Configuración») no tiene nada de ciudadanos."""

    def setUp(self):
        agente = User.objects.create_user("inicio-sin-caps", password="Clave-Seg-2026x")
        agente.groups.add(_rol_con("Solo configuración", ["config.ver", "config.administrar"]))
        self.client.force_login(agente)
        self.html = self.client.get("/inicio/").content.decode()

    def test_no_se_dibuja_el_buscador_de_ciudadanos(self):
        self.assertNotIn('class="search-input"', self.html)
        self.assertNotIn("Buscá por nombre, apellido o DNI", self.html)

    def test_no_afirma_que_no_hay_trabajo_pendiente(self):
        self.assertNotIn("Todo al día", self.html)
        self.assertIn("Este es el resumen de tu jornada.", self.html)

    def test_no_se_dibujan_los_paneles_ni_el_grafico_de_tendencias(self):
        self.assertNotIn("<h2>Mi trabajo de hoy</h2>", self.html)
        self.assertNotIn('id="chartTendencias"', self.html)


class InicioConCapacidadesTests(TestCase):
    def test_con_ciudadano_ver_vuelve_el_buscador(self):
        agente = User.objects.create_user("inicio-con-caps", password="Clave-Seg-2026x")
        agente.groups.add(_rol_con("Consulta de ciudadanos (inicio)", ["ciudadano.ver"]))
        self.client.force_login(agente)

        html = self.client.get("/inicio/").content.decode()

        self.assertIn('class="search-input"', html)
        self.assertIn("<h2>Mi trabajo de hoy</h2>", html)
        # Sin derivaciones pendientes y con la capacidad para verlas, el mensaje
        # optimista sí corresponde.
        self.assertIn("Todo al día", html)

    def test_con_dashboard_ver_vuelve_el_grafico_de_tendencias(self):
        agente = User.objects.create_user("inicio-tendencias", password="Clave-Seg-2026x")
        agente.groups.add(_rol_con("Tablero (inicio)", ["dashboard.ver"]))
        self.client.force_login(agente)

        html = self.client.get("/inicio/").content.decode()

        self.assertIn('id="chartTendencias"', html)
