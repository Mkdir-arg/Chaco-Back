"""El administrador del programa y el superusuario reservan camas de Emergencia (#1298).

`reservar_plazas_de_derivacion` exigía cada plaza en el alcance con
`exclude(q_edificios_en_alcance(...))`. Con alcance total ese `Q` es vacío, y `exclude(Q())` no
excluye nada: quien alcanza toda la institución recibía 403 al aceptar una derivación y al
«Ingresar igual», por la web y por la API M2. El alcance Edificios del Equipo sigue protegiendo.

Mutación: volver al `exclude` pone en rojo los de admin y superusuario; sacar el control de las
plazas pone en rojo `test_la_guardia_de_un_edificio_no_reserva_camas_de_otro`.
"""

import uuid

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.urls import reverse

from programas.models import CasoEmergencia, Derivacion, Edificio, MiembroEquipoDispositivo, Plaza, ReservaPlaza, Sector
from programas.services import emergencia_alojar as servicio
from programas.services.dispositivos import CAP_CONFIGURAR
from programas.services.reservas_derivacion import reservar_plazas_de_derivacion
from programas.tests.base_emergencia_api import BaseApiLlegadas, _url
from programas.tests.test_emergencia_alojar_base import GUARDIA, BaseAlojar

Estado = CasoEmergencia.Estado


def _superusuario(nombre="super"):
    return User.objects.create_superuser(username=nombre, password="x")


class ServicioConAlcanceTotalTests(BaseAlojar):
    """Por el servicio: admin del programa (sin Equipo) y superusuario."""

    def setUp(self):
        super().setUp()
        self.admin = self._usuario("admin_disp", [CAP_CONFIGURAR, *GUARDIA], programa=self.dispositivos)

    def _acepta(self, usuario):
        caso, derivacion = self._derivado()
        resultado = servicio.aceptar_derivacion(derivacion=derivacion, usuario=usuario)
        self.assertEqual((resultado.reservadas, resultado.faltantes), (7, 0))
        self.assertEqual(len(self._reservas(derivacion)), 7)
        self.assertEqual(self._estado(caso), Estado.INGRESO_EN_CURSO)

    def test_el_admin_del_programa_acepta_y_reserva(self):
        self._acepta(self.admin)

    def test_el_superusuario_acepta_y_reserva(self):
        self._acepta(_superusuario())

    def test_el_admin_reserva_plazas_elegidas(self):
        _caso, derivacion = self._derivado(plazas=2)
        plazas = list(Plaza.objects.filter(sector__dispositivo=self.club).order_by("pk")[:2])

        reservas = reservar_plazas_de_derivacion(derivacion=derivacion, plazas=plazas, usuario=self.admin)

        self.assertEqual([reserva.plaza_id for reserva in reservas], [plaza.pk for plaza in plazas])


class AlcanceEdificiosSigueProtegiendoTests(BaseAlojar):
    """La guardia del Equipo con alcance Edificios solo reserva camas de sus edificios (RN4)."""

    def setUp(self):
        super().setUp()
        self.edif_a = Edificio.objects.create(codigo="ED-A", nombre="Edificio A")
        self.edif_b = Edificio.objects.create(codigo="ED-B", nombre="Edificio B")
        self.edif_a.dispositivos.add(self.club)
        self.edif_b.dispositivos.add(self.club)
        Sector.objects.filter(dispositivo=self.club).update(edificio=self.edif_a)
        sector_b = Sector.objects.create(dispositivo=self.club, nombre="Anexo", capacidad=2, edificio=self.edif_b)
        self.plaza_a = Plaza.objects.filter(sector__edificio=self.edif_a).order_by("pk").first()
        self.plaza_b = Plaza.objects.create(sector=sector_b, codigo="B-01")
        fila = MiembroEquipoDispositivo.objects.get(usuario=self.guardia, dispositivo=self.club)
        fila.alcance = MiembroEquipoDispositivo.Alcance.EDIFICIOS
        fila.save(update_fields=["alcance"])
        fila.edificios.set([self.edif_a])
        self.guardia = User.objects.get(pk=self.guardia.pk)
        _caso, self.derivacion = self._derivado(plazas=2)
        Derivacion.objects.filter(pk=self.derivacion.pk).update(edificio=self.edif_a)
        self.derivacion.refresh_from_db()

    def test_la_guardia_de_un_edificio_no_reserva_camas_de_otro(self):
        for plazas in ([self.plaza_b], [self.plaza_a, self.plaza_b]):
            with self.subTest(plazas=[plaza.pk for plaza in plazas]), self.assertRaises(PermissionDenied):
                reservar_plazas_de_derivacion(derivacion=self.derivacion, plazas=plazas, usuario=self.guardia)
        self.assertFalse(ReservaPlaza.objects.filter(derivacion=self.derivacion).exists())

    def test_la_guardia_de_un_edificio_reserva_camas_del_suyo(self):
        reservas = reservar_plazas_de_derivacion(
            derivacion=self.derivacion, plazas=[self.plaza_a], usuario=self.guardia
        )
        self.assertEqual([reserva.plaza_id for reserva in reservas], [self.plaza_a.pk])

    def test_el_admin_reserva_camas_de_cualquier_edificio(self):
        admin = self._usuario("admin_disp", [CAP_CONFIGURAR, *GUARDIA], programa=self.dispositivos)
        reservas = reservar_plazas_de_derivacion(
            derivacion=self.derivacion, plazas=[self.plaza_a, self.plaza_b], usuario=admin
        )
        self.assertEqual(len(reservas), 2)


class WebConAlcanceTotalTests(BaseAlojar):
    """Por la vista de Llegadas (E6): «Aceptar y reservar camas» e «Ingresar igual»."""

    def _url(self, nombre, *args):
        return reverse(f"dispositivos:emergencia_{nombre}", args=[self.club.pk, *args])

    def _acepta_por_la_web(self, usuario):
        self.client.force_login(usuario)
        _caso, derivacion = self._derivado()

        respuesta = self.client.post(self._url("aceptar", derivacion.pk))

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(Derivacion.objects.get(pk=derivacion.pk).estado, Derivacion.Estado.ACEPTADA)
        self.assertEqual(len(self._reservas(derivacion)), 7)

    def _ingresa_igual(self, usuario):
        self.client.force_login(usuario)
        datos = {
            "traslado": "BOMBEROS",
            "dni": "33444555",
            "nombre": "Marta",
            "apellido": "Ríos",
            "adultos_f": "1",
            "adultos_m": "1",
            "menores_f": "1",
        }

        respuesta = self.client.post(self._url("ingreso_directo"), datos)

        caso = CasoEmergencia.objects.get()
        self.assertRedirects(respuesta, self._url("integrantes", caso.pk), fetch_redirect_response=False)
        self.assertEqual(ReservaPlaza.objects.filter(derivacion__caso=caso).count(), caso.grupo.total_declarado)

    def test_el_admin_del_programa_acepta_por_la_web(self):
        self._acepta_por_la_web(self._usuario("admin_disp", [CAP_CONFIGURAR, *GUARDIA], programa=self.dispositivos))

    def test_el_superusuario_acepta_por_la_web(self):
        self._acepta_por_la_web(_superusuario())

    def test_el_admin_del_programa_ingresa_igual(self):
        self._ingresa_igual(self._usuario("admin_disp", [CAP_CONFIGURAR, *GUARDIA], programa=self.dispositivos))

    def test_el_superusuario_ingresa_igual(self):
        self._ingresa_igual(_superusuario())


class ApiM2ConAlcanceTotalTests(BaseApiLlegadas):
    """Por la API M2 de la app: aceptar e ingreso directo."""

    def _acepta(self, usuario):
        _caso, derivacion = self._derivado()

        respuesta = self._como(usuario).post(
            _url("derivacion-aceptar", derivacion.pk), {"uuid_cliente": str(uuid.uuid4())}, format="json"
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        self.assertEqual(len(self._reservas(derivacion)), 7)

    def _ingresa(self, usuario):
        cuerpo = self._cuerpo(adultos_m=2)
        cuerpo.pop("direccion", None)

        respuesta = self._como(usuario).post(
            _url("dispositivo-ingreso-directo", self.centro.pk), cuerpo, format="multipart"
        )

        self.assertEqual(respuesta.status_code, 201, respuesta.content)
        self.assertEqual(respuesta.json()["faltantes"], 0)
        self.assertGreater(respuesta.json()["reservadas"], 0)

    def test_el_admin_del_programa_acepta_por_la_api(self):
        self._acepta(self._guardia("admin_disp", [CAP_CONFIGURAR, *GUARDIA]))

    def test_el_superusuario_acepta_por_la_api(self):
        self._acepta(_superusuario())

    def test_el_admin_del_programa_ingresa_directo_por_la_api(self):
        self._ingresa(self._guardia("admin_disp", [CAP_CONFIGURAR, *GUARDIA]))

    def test_el_superusuario_ingresa_directo_por_la_api(self):
        self._ingresa(_superusuario())
