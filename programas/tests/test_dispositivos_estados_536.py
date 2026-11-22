"""Cambio 536 · estados de la institución y de las plazas con gente adentro (relevamiento de lógica del 22/11).

1. Cerrar rechaza con estadías abiertas, reservas (comunes o de derivación) o derivaciones de Emergencia en curso;
   inactivar rechaza con estadías o derivaciones y libera las reservas comunes diciendo cuántas.
2. Reservar y prestar exigen institución activa; cambiar de plaza se permite inactiva y no cerrada.
3. Un sector con estadías o reservas no se muda de edificio (de «sin edificio» a uno, sí).
"""

from datetime import timedelta

from django.contrib.messages import get_messages
from django.core.exceptions import ValidationError
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from programas.models import (
    Derivacion,
    Dispositivo,
    Edificio,
    Estadia,
    ReservaPlaza,
    Sector,
    TrazaDispositivo,
)
from programas.selectors.compromisos_institucion import compromisos_de_la_institucion
from programas.services.estadias import cambiar_plaza, ingresar_persona, reservar_plaza
from programas.services.estado_institucion import cerrar_dispositivo, inactivar_dispositivo
from programas.services.plazas import editar_sector
from programas.tests.test_dispositivos_reservas_derivacion import RELOJ, BaseDerivacion

CAPS = ("dispositivo.ver", "dispositivo.admitir", "dispositivo.editar", "dispositivo.egresar", "ciudadano.ver")


class BaseEstados(BaseDerivacion):
    def setUp(self):
        super().setUp()
        self.editor = self._operador("Editor 536", self.cis, CAPS)
        self.client.force_login(self.editor)
        # `BaseDerivacion` crea una derivación aceptada: cada test decide si la quiere vigente.
        Derivacion.objects.all().update(estado=Derivacion.Estado.CANCELADA, clave_vigente=None)

    def _estado(self, estado):
        Dispositivo.objects.filter(pk=self.cis.pk).update(estado=estado)
        self.cis.refresh_from_db()

    def _alojar(self, persona=None, plaza=None):
        return ingresar_persona(
            ciudadano=persona or self.persona, dispositivo=self.cis, usuario=self.editor, plaza=plaza or self.plaza
        )

    def _reservar(self, persona=None, plaza=None):
        return reservar_plaza(
            plaza=plaza or self.otra_plaza, ciudadano=persona or self.otra_persona, usuario=self.editor
        )

    def _derivacion_vigente(self, estado=Derivacion.Estado.PENDIENTE):
        return self._derivacion(estado=estado)

    def _refrescado(self):
        return Dispositivo.objects.get(pk=self.cis.pk).estado


class CerrarTests(BaseEstados):
    def test_con_alojados_y_reservas_dice_las_cifras_y_no_cierra(self):
        self._alojar()
        self._reservar()

        with self.assertRaises(ValidationError) as fallo:
            cerrar_dispositivo(self.cis, self.editor)

        self.assertEqual(
            fallo.exception.messages[0],
            "No se puede cerrar: hay 1 persona alojada y 1 reserva vigente. Resolvelo antes de cerrar la institución.",
        )
        self.assertEqual(self._refrescado(), Dispositivo.Estado.ACTIVO)
        self.assertFalse(TrazaDispositivo.objects.filter(accion="CERRADO").exists())

    def test_una_reserva_de_derivacion_tambien_impide_cerrar(self):
        derivacion = self._derivacion_vigente(Derivacion.Estado.ACEPTADA)
        from programas.services.reservas_derivacion import reservar_plazas_de_derivacion

        reservar_plazas_de_derivacion(derivacion=derivacion, plazas=self.plazas[:2], usuario=self.editor)

        with self.assertRaises(ValidationError) as fallo:
            cerrar_dispositivo(self.cis, self.editor)

        mensaje = fallo.exception.messages[0]
        self.assertIn("2 reservas vigentes", mensaje)
        self.assertIn("1 derivación de Emergencia en curso", mensaje)

    def test_una_derivacion_pendiente_sola_impide_cerrar(self):
        self._derivacion_vigente(Derivacion.Estado.PENDIENTE)

        with self.assertRaises(ValidationError) as fallo:
            cerrar_dispositivo(self.cis, self.editor)

        self.assertIn("1 derivación de Emergencia en curso", fallo.exception.messages[0])

    def test_una_reserva_vencida_sin_liberar_sigue_contando(self):
        reserva = self._reservar()
        ReservaPlaza.objects.filter(pk=reserva.pk).update(
            desde=RELOJ - timedelta(hours=3), hasta=RELOJ - timedelta(hours=1)
        )

        with self.assertRaises(ValidationError):
            cerrar_dispositivo(self.cis, self.editor)

    def test_sin_compromisos_cierra(self):
        self._derivacion_vigente(Derivacion.Estado.PENDIENTE)
        Derivacion.objects.all().update(estado=Derivacion.Estado.RECHAZADA, clave_vigente=None)
        egresada = self._alojar()
        Estadia.objects.filter(pk=egresada.pk).update(
            estado=Estadia.Estado.EGRESADA, fecha_egreso=RELOJ, clave_alojamiento=None
        )

        cerrar_dispositivo(self.cis, self.editor)

        self.assertEqual(self._refrescado(), Dispositivo.Estado.CERRADO)

    def test_la_vista_muestra_el_error_y_no_cierra(self):
        self._alojar()

        respuesta = self.client.post(reverse("dispositivos:cerrar", args=[self.cis.pk]))

        self.assertEqual(respuesta.status_code, 302)
        textos = [str(m) for m in get_messages(respuesta.wsgi_request)]
        self.assertTrue(any("No se puede cerrar: hay 1 persona alojada" in t for t in textos), textos)
        self.assertEqual(self._refrescado(), Dispositivo.Estado.ACTIVO)

    def test_el_conteo_cuesta_tres_consultas_sin_importar_la_cantidad(self):
        self._alojar()
        self._reservar()
        with CaptureQueriesContext(connection) as pocas:
            compromisos_de_la_institucion(self.cis)
        for numero in range(3, 6):
            ReservaPlaza.objects.create(
                plaza=self.plazas[numero], ciudadano=self.persona, desde=RELOJ, creada_por=self.editor
            )
        with CaptureQueriesContext(connection) as muchas:
            c = compromisos_de_la_institucion(self.cis)
        self.assertEqual(len(pocas), 3)
        self.assertEqual(len(muchas), 3)
        self.assertEqual(c.reservas, 4)


class InactivarTests(BaseEstados):
    def test_con_alojados_no_inactiva(self):
        self._alojar()

        with self.assertRaises(ValidationError) as fallo:
            inactivar_dispositivo(self.cis, self.editor)

        self.assertIn("No se puede inactivar: hay 1 persona alojada", fallo.exception.messages[0])
        self.assertEqual(self._refrescado(), Dispositivo.Estado.ACTIVO)

    def test_con_una_derivacion_vigente_no_inactiva(self):
        self._derivacion_vigente(Derivacion.Estado.ACEPTADA)

        with self.assertRaises(ValidationError) as fallo:
            inactivar_dispositivo(self.cis, self.editor)

        self.assertIn("1 derivación de Emergencia en curso", fallo.exception.messages[0])
        self.assertEqual(self._refrescado(), Dispositivo.Estado.ACTIVO)

    def test_las_reservas_comunes_se_liberan_con_motivo_y_se_cuentan(self):
        self._reservar()
        self._reservar(persona=self.persona, plaza=self.plaza)

        inactivado = inactivar_dispositivo(self.cis, self.editor)

        self.assertEqual(inactivado.reservas_liberadas, 2)
        self.assertEqual(self._refrescado(), Dispositivo.Estado.INACTIVO)
        liberadas = ReservaPlaza.objects.filter(estado=ReservaPlaza.Estado.LIBERADA)
        self.assertEqual(liberadas.count(), 2)
        self.assertEqual({r.motivo for r in liberadas}, {"Se inactivó la institución"})
        traza = TrazaDispositivo.objects.get(accion="INACTIVADO")
        self.assertIn("2 reservas liberadas", traza.detalle)

    def test_la_vista_avisa_cuantas_reservas_se_liberaron(self):
        self._reservar()

        respuesta = self.client.post(reverse("dispositivos:inactivar", args=[self.cis.pk]))

        textos = [str(m) for m in get_messages(respuesta.wsgi_request)]
        self.assertEqual(textos, ["Dispositivo inactivado. Se liberó 1 reserva."])

    def test_la_vista_rechaza_con_alojados(self):
        self._alojar()

        respuesta = self.client.post(reverse("dispositivos:inactivar", args=[self.cis.pk]))

        textos = [str(m) for m in get_messages(respuesta.wsgi_request)]
        self.assertTrue(any("No se puede inactivar" in t for t in textos), textos)
        self.assertEqual(self._refrescado(), Dispositivo.Estado.ACTIVO)

    def test_sin_nada_inactiva_sin_aviso_de_reservas(self):
        respuesta = self.client.post(reverse("dispositivos:inactivar", args=[self.cis.pk]))

        textos = [str(m) for m in get_messages(respuesta.wsgi_request)]
        self.assertEqual(textos, ["Dispositivo inactivado."])


class EstadoDeLaInstitucionTests(BaseEstados):
    def _post_reservar(self, nombre="plaza_reservar", plaza=None):
        plaza = plaza or self.otra_plaza
        return self.client.post(
            reverse(f"dispositivos:{nombre}", args=[self.cis.pk, plaza.pk]),
            {
                "dni": self.otra_persona.dni,
                "hasta": (timezone.localtime() + timedelta(hours=12)).strftime("%Y-%m-%dT%H:%M"),
            },
            headers={"x-requested-with": "XMLHttpRequest"},
        )

    def test_reservar_y_prestar_exigen_institucion_activa(self):
        for estado in (Dispositivo.Estado.INACTIVO, Dispositivo.Estado.CERRADO):
            self._estado(estado)
            for tipo in (ReservaPlaza.Tipo.RESERVA, ReservaPlaza.Tipo.PRESTAMO):
                with self.subTest(estado=estado, tipo=tipo):
                    hasta = RELOJ + timedelta(hours=12) if tipo == ReservaPlaza.Tipo.PRESTAMO else None
                    with self.assertRaises(ValidationError) as fallo:
                        reservar_plaza(
                            plaza=self.otra_plaza,
                            ciudadano=self.otra_persona,
                            usuario=self.editor,
                            tipo=tipo,
                            hasta=hasta,
                        )
                    self.assertIn("la institución está", fallo.exception.message_dict["dispositivo"][0])
        self.assertFalse(ReservaPlaza.objects.exists())

    def test_reservar_en_una_activa_sigue_andando(self):
        self.assertEqual(self._reservar().estado, ReservaPlaza.Estado.VIGENTE)

    def test_la_vista_de_reservar_rechaza_en_inactiva(self):
        self._estado(Dispositivo.Estado.INACTIVO)

        respuesta = self._post_reservar()

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("la institución está inactivo", str(respuesta.json()))
        self.assertFalse(ReservaPlaza.objects.exists())

    def test_cambiar_de_plaza_se_permite_en_inactiva_y_se_rechaza_en_cerrada(self):
        estadia = self._alojar()
        self._estado(Dispositivo.Estado.INACTIVO)

        cambiar_plaza(estadia=estadia, plaza=self.otra_plaza, usuario=self.editor, motivo="Convivencia")

        estadia.refresh_from_db()
        self.assertEqual(estadia.plaza_id, self.otra_plaza.pk)

        self._estado(Dispositivo.Estado.CERRADO)
        with self.assertRaises(ValidationError) as fallo:
            cambiar_plaza(estadia=estadia, plaza=self.plaza, usuario=self.editor, motivo="Otra vez")
        self.assertIn("la institución está cerrado", fallo.exception.message_dict["dispositivo"][0])
        estadia.refresh_from_db()
        self.assertEqual(estadia.plaza_id, self.otra_plaza.pk)

    def test_la_vista_de_cambiar_plaza_rechaza_en_cerrada(self):
        estadia = self._alojar()
        self._estado(Dispositivo.Estado.CERRADO)

        respuesta = self.client.post(
            reverse("dispositivos:cambiar_plaza", args=[self.cis.pk, estadia.pk]),
            {"plaza": self.otra_plaza.pk, "motivo": "x", "momento": timezone.localtime().strftime("%Y-%m-%dT%H:%M")},
            headers={"x-requested-with": "XMLHttpRequest"},
        )

        self.assertEqual(respuesta.status_code, 400)
        estadia.refresh_from_db()
        self.assertEqual(estadia.plaza_id, self.plaza.pk)

    def test_el_ingreso_por_derivacion_a_una_activa_sigue_andando(self):
        from programas.services.reservas_derivacion import reservar_plazas_de_derivacion

        derivacion = self._derivacion_vigente(Derivacion.Estado.ACEPTADA)

        reservas = reservar_plazas_de_derivacion(derivacion=derivacion, plazas=self.plazas[:2], usuario=self.editor)

        self.assertEqual(len(reservas), 2)


class MudarSectorTests(BaseEstados):
    def setUp(self):
        super().setUp()
        self.edificio_a = Edificio.objects.create(codigo="EDI-A", nombre="Predio A")
        self.edificio_b = Edificio.objects.create(codigo="EDI-B", nombre="Predio B")
        self.edificio_a.dispositivos.add(self.cis)
        self.edificio_b.dispositivos.add(self.cis)

    def _editar(self, sector, edificio):
        return editar_sector(
            sector=sector,
            usuario=self.editor,
            nombre=sector.nombre,
            tipo=sector.tipo,
            capacidad=sector.capacidad,
            edificio=edificio,
        )

    def _en_edificio(self, edificio):
        Sector.objects.filter(pk=self.sector.pk).update(edificio=edificio)
        self.sector.refresh_from_db()

    def test_con_alojados_y_reservas_no_se_muda_y_dice_las_cifras(self):
        self._en_edificio(self.edificio_a)
        self._alojar()
        self._reservar()

        with self.assertRaises(ValidationError) as fallo:
            self._editar(self.sector, self.edificio_b)

        mensaje = fallo.exception.message_dict["edificio"][0]
        self.assertIn("1 persona alojada y 1 reserva vigente", mensaje)
        self.sector.refresh_from_db()
        self.assertEqual(self.sector.edificio_id, self.edificio_a.pk)

    def test_solo_con_reservas_tampoco(self):
        self._en_edificio(self.edificio_a)
        self._reservar()

        with self.assertRaises(ValidationError):
            self._editar(self.sector, self.edificio_b)

    def test_sin_gente_se_muda(self):
        self._en_edificio(self.edificio_a)

        self._editar(self.sector, self.edificio_b)

        self.sector.refresh_from_db()
        self.assertEqual(self.sector.edificio_id, self.edificio_b.pk)

    def test_de_sin_edificio_a_un_edificio_se_permite_con_gente_adentro(self):
        self._en_edificio(None)
        self._alojar()
        self._reservar()

        self._editar(self.sector, self.edificio_a)

        self.sector.refresh_from_db()
        self.assertEqual(self.sector.edificio_id, self.edificio_a.pk)

    def test_con_gente_se_puede_editar_el_resto_sin_cambiar_de_edificio(self):
        self._en_edificio(self.edificio_a)
        self._alojar()

        editar_sector(
            sector=self.sector,
            usuario=self.editor,
            nombre="Varones 2",
            tipo=self.sector.tipo,
            capacidad=self.sector.capacidad,
            edificio=self.edificio_a,
        )

        self.sector.refresh_from_db()
        self.assertEqual(self.sector.nombre, "Varones 2")

    def test_la_vista_rechaza_la_mudanza_con_el_error_en_el_edificio(self):
        self._en_edificio(self.edificio_a)
        self._alojar()

        respuesta = self.client.post(
            reverse("dispositivos:sector_editar", args=[self.cis.pk, self.sector.pk]),
            {
                "nombre": self.sector.nombre,
                "tipo": self.sector.tipo,
                "capacidad": self.sector.capacidad,
                "activo": "on",
                "edificio": self.edificio_b.pk,
            },
            headers={"x-requested-with": "XMLHttpRequest"},
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("edificio", respuesta.json()["errors"])
        self.sector.refresh_from_db()
        self.assertEqual(self.sector.edificio_id, self.edificio_a.pk)
