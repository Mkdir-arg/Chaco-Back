"""Pantalla «Sectores y plazas» (MVP v2, etapa 1 · P5): alcance, tope y honestidad de los estados."""

from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from core import rbac
from programas.models import Dispositivo, Plaza, Programa, Sector, TipoDispositivo
from programas.services.sectores_plazas import TOPE_PLAZAS_POR_SECTOR
from programas.tests.test_dispositivos_config import permiso
from users.models import RolMeta


class SectoresYPlazasPantallaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.programa, _ = Programa.objects.get_or_create(
            codigo="DISPOSITIVOS",
            defaults={"nombre": "Dispositivos", "tipo": Programa.TipoPrograma.DISPOSITIVOS},
        )
        rol = Group.objects.create(name="Lector Dispositivos test")
        RolMeta.objects.create(grupo=rol, categoria=rbac.CATEGORIA_PROGRAMA, programa=cls.programa, activo=True)
        rol.permissions.add(permiso("dispositivo.ver"), permiso("programa.configurar"))
        cls.lector = User.objects.create_user("lector-sectores", password="x")
        cls.lector.groups.add(rol)
        cls.sin_permiso = User.objects.create_user("sin-permiso-sectores", password="x")
        tipo = TipoDispositivo.objects.create(codigo="ALB-S", nombre="Albergue")
        cls.dispositivo = Dispositivo.objects.create(tipo=tipo, codigo="CIS-3", nombre="CIS N.º 3")
        cls.sector = Sector.objects.create(
            dispositivo=cls.dispositivo, nombre="Pabellón A", perfil="varones", capacidad=3
        )
        Plaza.objects.create(sector=cls.sector, codigo="A-01")
        Plaza.objects.create(sector=cls.sector, codigo="A-02")
        Plaza.objects.create(
            sector=cls.sector,
            codigo="A-03",
            estado=Plaza.Estado.FUERA_SERVICIO,
            motivo_fuera_servicio="colchón",
        )
        Sector.objects.create(dispositivo=cls.dispositivo, nombre="Pabellón viejo", activo=False)
        cls.url = reverse("dispositivos:sectores", args=[cls.dispositivo.pk])

    def setUp(self):
        cache.clear()

    def test_sin_capacidad_no_entra(self):
        self.client.force_login(self.sin_permiso)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_muestra_el_mapa_con_los_dos_estados_que_existen(self):
        self.client.force_login(self.lector)
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Pabellón A · varones · 3 plazas")
        self.assertContains(respuesta, "2 operativas de 3")
        self.assertContains(respuesta, "1 fuera de servicio")
        self.assertContains(respuesta, "colchón")
        self.assertNotContains(respuesta, "Pabellón viejo")

    def test_no_miente_sobre_la_ocupacion(self):
        """Sin estadías, una plaza operativa no es «disponible» ni «ocupada»."""

        self.client.force_login(self.lector)
        respuesta = self.client.get(self.url)
        self.assertContains(respuesta, "Operativa")
        self.assertContains(respuesta, "Todavía no se ve la ocupación")
        for estado in ("Disponible", "Ocupada", "Reservada", "Prestada"):
            self.assertNotContains(respuesta, estado)

    def test_cada_sector_se_acota_al_tope_y_avisa(self):
        grande = Sector.objects.create(dispositivo=self.dispositivo, nombre="Galpón")
        Plaza.objects.bulk_create(
            [Plaza(sector=grande, codigo=f"G-{n:03d}") for n in range(TOPE_PLAZAS_POR_SECTOR + 5)]
        )
        self.client.force_login(self.lector)
        respuesta = self.client.get(self.url)
        sector = next(item for item in respuesta.context["sectores"] if item["sector"] == grande)
        self.assertEqual(len(sector["plazas"]), TOPE_PLAZAS_POR_SECTOR)
        self.assertContains(respuesta, f"Mostrando {TOPE_PLAZAS_POR_SECTOR} de {TOPE_PLAZAS_POR_SECTOR + 5} plazas.")

    def test_dispositivo_sin_sectores_muestra_el_vacio(self):
        otro = Dispositivo.objects.create(tipo=self.dispositivo.tipo, codigo="CIS-4", nombre="CIS 4")
        self.client.force_login(self.lector)
        respuesta = self.client.get(reverse("dispositivos:sectores", args=[otro.pk]))
        self.assertContains(respuesta, "Este dispositivo no tiene sectores")
