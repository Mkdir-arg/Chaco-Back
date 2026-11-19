"""`TipoDispositivo.ubicacion_reservada` (Cambio 499, C2 / T9b, RN-009-13)."""

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from programas.models import Dispositivo, Programa, Sector, TipoDispositivo
from programas.services.ubicacion_reservada import q_sin_ubicacion_reservada, separar_por_ubicacion_reservada
from programas.tests.test_dispositivos_config import rol_configuracion


class CampoTests(TestCase):
    def test_un_tipo_nuevo_nace_sin_reservar(self):
        tipo = TipoDispositivo.objects.create(codigo="HOG", nombre="Hogar")
        tipo.refresh_from_db()
        self.assertFalse(tipo.ubicacion_reservada)


class HelperTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.comun = TipoDispositivo.objects.create(codigo="HOG", nombre="Hogar")
        cls.reservado = TipoDispositivo.objects.create(codigo="PRO", nombre="Protección", ubicacion_reservada=True)
        cls.hogar = Dispositivo.objects.create(
            codigo="D1", nombre="Hogar Norte", tipo=cls.comun, localidad="Resistencia", latitud=-27.45, longitud=-58.98
        )
        cls.refugio = Dispositivo.objects.create(
            codigo="D2", nombre="Refugio", tipo=cls.reservado, localidad="Resistencia", latitud=-27.46, longitud=-58.99
        )

    def test_la_q_excluye_los_dispositivos_de_tipo_reservado(self):
        self.assertEqual(list(Dispositivo.objects.filter(q_sin_ubicacion_reservada())), [self.hogar])

    def test_la_q_con_prefijo_filtra_un_modelo_que_llega_al_dispositivo(self):
        del_hogar = Sector.objects.create(dispositivo=self.hogar, nombre="General", capacidad=4)
        Sector.objects.create(dispositivo=self.refugio, nombre="General", capacidad=4)
        self.assertEqual(list(Sector.objects.filter(q_sin_ubicacion_reservada("dispositivo__"))), [del_hogar])

    def test_separar_no_consulta_con_el_tipo_ya_traido_y_deja_sumar_los_reservados(self):
        red = list(Dispositivo.objects.select_related("tipo").order_by("codigo"))
        filas = [{"dispositivo": d, "libres": libres} for d, libres in zip(red, (3, 5))]

        with self.assertNumQueries(0):
            publicables, reservados = separar_por_ubicacion_reservada(filas, dispositivo=lambda f: f["dispositivo"])

        self.assertEqual([f["dispositivo"] for f in publicables], [self.hogar])
        self.assertEqual([f["dispositivo"] for f in reservados], [self.refugio])
        # Los puntos del mapa salen solo de los publicables; el total suma los dos.
        self.assertEqual(sum(f["libres"] for f in publicables + reservados), 8)
        self.assertEqual(sum(f["libres"] for f in reservados), 5)

    def test_separar_sin_extractor_toma_el_elemento_como_dispositivo(self):
        red = list(Dispositivo.objects.select_related("tipo").order_by("codigo"))
        self.assertEqual(separar_por_ubicacion_reservada(red), ([self.hogar], [self.refugio]))


class ConfiguracionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        programa, _ = Programa.objects.get_or_create(
            codigo="DISPOSITIVOS", defaults={"nombre": "Dispositivos", "tipo": Programa.TipoPrograma.DISPOSITIVOS}
        )
        cls.admin = User.objects.create_user("admin-reservada", password="x")
        cls.admin.groups.add(rol_configuracion("Admin reservada", programa))
        cls.sin_permiso = User.objects.create_user("operador-reservada", password="x")
        cls.tipo = TipoDispositivo.objects.create(codigo="PRO", nombre="Protección")

    def setUp(self):
        cache.clear()

    def _post(self, **extra):
        datos = {"codigo": "PRO", "nombre": "Protección", "descripcion": "", "activo": "on", **extra}
        return self.client.post(reverse("dispositivos:tipo_editar", args=[self.tipo.pk]), datos)

    def test_la_casilla_aparece_en_la_edicion(self):
        self.client.force_login(self.admin)
        respuesta = self.client.get(reverse("dispositivos:tipo_editar", args=[self.tipo.pk]))
        self.assertContains(respuesta, 'name="ubicacion_reservada"')
        self.assertContains(respuesta, "Ubicación reservada")

    def test_la_casilla_se_guarda_y_se_destilda(self):
        self.client.force_login(self.admin)
        self.assertEqual(self._post(ubicacion_reservada="on").status_code, 302)
        self.tipo.refresh_from_db()
        self.assertTrue(self.tipo.ubicacion_reservada)

        self.assertEqual(self._post().status_code, 302)
        self.tipo.refresh_from_db()
        self.assertFalse(self.tipo.ubicacion_reservada)

    def test_el_alta_sin_la_casilla_nace_sin_reservar(self):
        self.client.force_login(self.admin)
        self.client.post(
            reverse("dispositivos:tipo_crear"), {"codigo": "NUE", "nombre": "Nuevo", "descripcion": "", "activo": "on"}
        )
        self.assertFalse(TipoDispositivo.objects.get(codigo="NUE").ubicacion_reservada)

    def test_sin_capacidad_no_la_cambia(self):
        self.client.force_login(self.sin_permiso)
        self.assertEqual(self._post(ubicacion_reservada="on").status_code, 403)
        self.tipo.refresh_from_db()
        self.assertFalse(self.tipo.ubicacion_reservada)
