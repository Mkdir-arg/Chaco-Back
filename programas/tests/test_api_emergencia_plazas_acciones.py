"""Cambio 598: acciones de cama en la API de campo (reservar, prestar, liberar, sacar de servicio, volver a servicio).

Cada vista llama al mismo servicio que la web; acá se fija el contrato HTTP: 200 ``{ok, mapa}`` (el mapa
es el de ``GET .../mapa/`` del edificio de la cama, ya actualizado), 404 fuera de alcance, 403 sin capacidad, 400 con el motivo.

**Mutación vista en rojo** (alcance): sin el ``q_edificios_en_alcance`` de ``_AccionDeCamaView._plaza``, la plaza
de otra institución deja de dar 404 y contesta 403, y ``test_la_plaza_de_otra_institucion_es_404`` falla.
"""

from datetime import timedelta

from django.utils import timezone

from legajos.models import Ciudadano
from programas.models import Edificio, Plaza, ReservaPlaza, Sector
from programas.services import estadias
from programas.tests.base_emergencia_api import NO_ENCONTRADO, SIN_MODULO, BaseApiEmergencia, _url

VER, ADMITIR, EDITAR, CIUDADANO = "dispositivo.ver", "dispositivo.admitir", "dispositivo.editar", "ciudadano.ver"


class AccionesDeCamaTests(BaseApiEmergencia):
    def setUp(self):
        super().setUp()
        self.jefa = self._guardia("jefa", [VER, ADMITIR, EDITAR, CIUDADANO], [self.club])
        self.plaza = Plaza.objects.filter(sector__dispositivo=self.club).order_by("codigo").first()
        self.persona = Ciudadano.objects.create(dni="30111222", nombre="Rosa", apellido="Benítez")
        self.edificio = Edificio.objects.create(codigo="EDI-C", nombre="Edificio del club")
        self.edificio.dispositivos.add(self.club)
        Sector.objects.filter(dispositivo=self.club).update(edificio=self.edificio)

    def _celda(self, respuesta, plaza=None):
        """La plaza dentro del ``mapa`` de la respuesta; el mapa trae los sectores del edificio."""
        mapa = respuesta.json()["mapa"]
        self.assertTrue(mapa["sectores"])
        plaza = plaza or self.plaza
        return next(p for s in mapa["sectores"] for p in s["plazas"] if p["id"] == plaza.pk)

    def _post(self, usuario, nombre, plaza=None, cuerpo=None):
        return self._como(usuario).post(_url(nombre, (plaza or self.plaza).pk), cuerpo or {}, format="json")

    def _reservar(self, plaza=None, **cuerpo):
        return self._post(self.jefa, "plaza-reservar", plaza, {"dni": "30111222", **cuerpo})

    def _ocupar_la_plaza(self):
        self._ocupar(self.club, 1)
        return Plaza.objects.get(pk=self.plaza.pk)

    def _hasta(self, horas=12):
        return (timezone.now() + timedelta(hours=horas)).isoformat()

    # --- Felices ---------------------------------------------------------------------------

    def test_reservar(self):
        respuesta = self._reservar(motivo="Lista de espera")
        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        self.assertTrue(respuesta.json()["ok"])
        celda = self._celda(respuesta)
        self.assertEqual(celda["estado"], "reservada")
        self.assertEqual(celda["persona"]["dni"], "30111222")
        reserva = estadias.reserva_abierta_de(self.plaza)
        self.assertEqual(reserva.ciudadano_id, self.persona.pk)
        self.assertEqual(reserva.tipo, ReservaPlaza.Tipo.RESERVA)

    def test_prestar_con_vencimiento(self):
        respuesta = self._post(self.jefa, "plaza-prestar", cuerpo={"dni": "30111222", "hasta": self._hasta()})
        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        self.assertEqual(self._celda(respuesta)["estado"], "prestada")
        reserva = estadias.reserva_abierta_de(self.plaza)
        self.assertEqual(reserva.tipo, ReservaPlaza.Tipo.PRESTAMO)
        self.assertIsNotNone(reserva.hasta)

    def test_prestar_sin_vencimiento_es_400(self):
        respuesta = self._post(self.jefa, "plaza-prestar", cuerpo={"dni": "30111222"})
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("hasta", respuesta.json())
        self.assertIsNone(estadias.reserva_abierta_de(self.plaza))

    def test_liberar(self):
        self._reservar()
        respuesta = self._post(self.jefa, "plaza-liberar", cuerpo={"motivo": "No vino"})
        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        self.assertEqual(self._celda(respuesta)["estado"], "disponible")
        self.assertIsNone(estadias.reserva_abierta_de(self.plaza))

    def test_liberar_sin_reserva_es_400(self):
        respuesta = self._post(self.jefa, "plaza-liberar")
        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(respuesta.json()["code"], "VALIDACION")

    def test_sacar_de_servicio_y_volver(self):
        respuesta = self._post(self.jefa, "plaza-fuera-servicio", cuerpo={"motivo": "Colchón roto"})
        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        self.assertEqual(self._celda(respuesta)["estado"], "fuera_servicio")
        self.plaza.refresh_from_db()
        self.assertEqual(self.plaza.estado, Plaza.Estado.FUERA_SERVICIO)
        self.assertEqual(self.plaza.motivo_fuera_servicio, "Colchón roto")

        respuesta = self._post(self.jefa, "plaza-volver-servicio")
        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        self.assertEqual(self._celda(respuesta)["estado"], "disponible")
        self.plaza.refresh_from_db()
        self.assertEqual(self.plaza.estado, Plaza.Estado.OPERATIVA)

    def test_sacar_de_servicio_es_idempotente_y_no_pisa_el_motivo(self):
        self._post(self.jefa, "plaza-fuera-servicio", cuerpo={"motivo": "Colchón roto"})
        otra_vez = self._post(self.jefa, "plaza-fuera-servicio", cuerpo={"motivo": "Otro"})
        self.assertEqual(otra_vez.status_code, 200)
        self.plaza.refresh_from_db()
        self.assertEqual(self.plaza.motivo_fuera_servicio, "Colchón roto")

    def test_volver_a_servicio_una_plaza_en_servicio_es_200(self):
        self.assertEqual(self._post(self.jefa, "plaza-volver-servicio").status_code, 200)

    def test_sacar_de_servicio_exige_motivo(self):
        respuesta = self._post(self.jefa, "plaza-fuera-servicio")
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("motivo", respuesta.json())

    # --- Estado que no admite la acción ----------------------------------------------------

    def test_la_plaza_ocupada_no_se_saca_de_servicio(self):
        plaza = self._ocupar_la_plaza()
        respuesta = self._post(self.jefa, "plaza-fuera-servicio", plaza, {"motivo": "Rota"})
        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(
            respuesta.json()["detail"], "La plaza está ocupada: primero registrá el egreso o cambiala de plaza."
        )
        plaza.refresh_from_db()
        self.assertEqual(plaza.estado, Plaza.Estado.OPERATIVA)

    def test_la_plaza_ocupada_no_se_reserva(self):
        plaza = self._ocupar_la_plaza()
        respuesta = self._reservar(plaza)
        self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(ReservaPlaza.objects.exists())

    def test_doble_reserva_es_400(self):
        self.assertEqual(self._reservar().status_code, 200)
        otra = Ciudadano.objects.create(dni="30222333", nombre="Ana", apellido="Gómez")
        respuesta = self._post(self.jefa, "plaza-reservar", cuerpo={"dni": otra.dni})
        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(ReservaPlaza.objects.abiertas().count(), 1)

    def test_la_misma_persona_no_reserva_dos_plazas(self):
        self.assertEqual(self._reservar().status_code, 200)
        segunda = Plaza.objects.filter(sector__dispositivo=self.club).order_by("codigo")[1]
        self.assertEqual(self._reservar(segunda).status_code, 400)

    # --- Persona -----------------------------------------------------------------------------

    def test_persona_inexistente_es_400(self):
        for nombre, cuerpo in (("plaza-reservar", {}), ("plaza-prestar", {"hasta": self._hasta()})):
            with self.subTest(nombre=nombre):
                respuesta = self._post(self.jefa, nombre, cuerpo={"dni": "99999999", **cuerpo})
                self.assertEqual(respuesta.status_code, 400)
                self.assertEqual(respuesta.json()["code"], "PERSONA_NO_ENCONTRADA")
        self.assertFalse(ReservaPlaza.objects.exists())

    def test_dni_invalido_es_400(self):
        respuesta = self._reservar(dni="12")
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("dni", respuesta.json())

    def test_el_dni_con_puntos_encuentra_a_la_persona(self):
        self.assertEqual(self._reservar(dni="30.111.222").status_code, 200)

    # --- Capacidades y alcance ----------------------------------------------------------------

    def test_sin_editar_no_saca_ni_vuelve_a_servicio(self):
        sin_editar = self._guardia("sin_editar", [VER, ADMITIR, CIUDADANO], [self.club])
        for nombre, cuerpo in (("plaza-fuera-servicio", {"motivo": "x"}), ("plaza-volver-servicio", {})):
            with self.subTest(nombre=nombre):
                respuesta = self._post(sin_editar, nombre, cuerpo=cuerpo)
                self.assertEqual(respuesta.status_code, 403)
                self.assertEqual(respuesta.json()["code"], "SIN_PERMISO")
        self.plaza.refresh_from_db()
        self.assertEqual(self.plaza.estado, Plaza.Estado.OPERATIVA)

    def test_sin_admitir_no_reserva_ni_presta_ni_libera(self):
        sin_admitir = self._guardia("sin_admitir", [VER, EDITAR, CIUDADANO], [self.club])
        for nombre in ("plaza-reservar", "plaza-prestar", "plaza-liberar"):
            with self.subTest(nombre=nombre):
                respuesta = self._post(sin_admitir, nombre, cuerpo={"dni": "30111222", "hasta": self._hasta()})
                self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(ReservaPlaza.objects.exists())

    def test_sin_ver_ciudadanos_no_reserva_y_no_distingue_si_el_dni_existe(self):
        sin_ciudadanos = self._guardia("sin_ciudadanos", [VER, ADMITIR, EDITAR], [self.club])
        for dni in ("30111222", "99999999"):
            with self.subTest(dni=dni):
                respuesta = self._post(sin_ciudadanos, "plaza-reservar", cuerpo={"dni": dni})
                self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(ReservaPlaza.objects.exists())

    def test_la_plaza_de_otra_institucion_es_404(self):
        otro = self._dispositivo("Otro Club", camas=2)
        ajena = Plaza.objects.filter(sector__dispositivo=otro).first()
        for nombre, cuerpo in (
            ("plaza-reservar", {"dni": "30111222"}),
            ("plaza-prestar", {"dni": "30111222", "hasta": self._hasta()}),
            ("plaza-liberar", {}),
            ("plaza-fuera-servicio", {"motivo": "x"}),
            ("plaza-volver-servicio", {}),
        ):
            with self.subTest(nombre=nombre):
                respuesta = self._post(self.jefa, nombre, ajena, cuerpo)
                self.assertEqual(respuesta.status_code, 404)
                self.assertEqual(respuesta.json(), NO_ENCONTRADO)
        self.assertFalse(ReservaPlaza.objects.exists())
        ajena.refresh_from_db()
        self.assertEqual(ajena.estado, Plaza.Estado.OPERATIVA)

    def test_una_plaza_inexistente_es_404(self):
        respuesta = self._como(self.jefa).post(_url("plaza-liberar", 999999), {}, format="json")
        self.assertEqual(respuesta.status_code, 404)

    def test_un_rol_de_becas_no_abre_las_acciones(self):
        respuesta = self._post(self.territorial_becas, "plaza-reservar", cuerpo={"dni": "30111222"})
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(respuesta.json(), SIN_MODULO)
