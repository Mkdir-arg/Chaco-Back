"""Regresiones de la auditoría independiente del MVP, carril G1 (personas y red)."""

import json
from datetime import datetime, timedelta
from unittest import mock

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import connection
from django.db.models.signals import post_init
from django.test import tag
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from core.tests.candados import orden_de_candados
from legajos.models import Ciudadano
from programas.models import Estadia, MovimientoEstadia, TrazaDispositivo
from programas.services.estadias import (
    ALOJAMIENTO_SOLAPADO,
    EGRESO_SIN_DESTINO,
    egresar_persona,
    ingresar_persona,
    reservar_plaza,
    verificar_alojamiento_en_red,
)
from programas.services.ingreso import buscar_ciudadano_por_dni
from programas.services.ocupacion import alojada_en
from programas.tests.test_dispositivos_estadias import BaseEstadias

AHORA = timezone.make_aware(datetime(2026, 10, 16, 12))


class PersonasRedTests(BaseEstadias):
    def setUp(self):
        super().setUp()
        reloj = mock.patch("django.utils.timezone.now", return_value=AHORA)
        reloj.start()
        self.addCleanup(reloj.stop)

    def _cerrada(self, desde=-6, hasta=-2, dispositivo=None):
        return Estadia.objects.create(
            ciudadano=self.persona,
            dispositivo=dispositivo or self.parador,
            fecha_ingreso=AHORA + timedelta(days=desde),
            fecha_egreso=AHORA + timedelta(days=hasta),
            estado=Estadia.Estado.EGRESADA,
        )

    def _ingresar(self, desde, plaza=None):
        return ingresar_persona(
            ciudadano=self.persona,
            dispositivo=self.cis,
            usuario=self.operador_cis,
            fecha_ingreso=AHORA + timedelta(days=desde),
            plaza=plaza,
        )

    def test_ingreso_retroactivo_rechaza_el_doble_alojamiento_del_censo(self):
        anterior = ingresar_persona(
            ciudadano=self.persona,
            dispositivo=self.parador,
            usuario=self.operador_parador,
            plaza=self.plaza_parador,
            fecha_ingreso=AHORA - timedelta(days=6),
        )
        anterior = egresar_persona(
            estadia=anterior,
            usuario=self.operador_parador,
            motivo_egreso=self.motivo_alta,
            destino="Domicilio",
            fecha_egreso=AHORA - timedelta(days=2),
        )
        self.assertTrue(alojada_en(anterior.fecha_ingreso, anterior.fecha_egreso, AHORA - timedelta(days=3)))
        with self.assertRaisesMessage(ValidationError, ALOJAMIENTO_SOLAPADO) as error:
            self._ingresar(-4, self.plaza)
        self.assertIn("fecha_ingreso", error.exception.message_dict)
        self.assertNotIn(self.parador.nombre, str(error.exception))
        self.assertNotIn(self.parador.codigo, str(error.exception))
        self.assertEqual(Estadia.objects.count(), 1)
        self.assertEqual(MovimientoEstadia.objects.count(), 2)
        self.assertEqual(TrazaDispositivo.objects.count(), 2)

    def test_historial_posterior_al_ingreso_tambien_solapa_sin_plaza_y_en_el_mismo_dispositivo(self):
        self._cerrada(desde=-3, hasta=-1, dispositivo=self.cis)
        with self.assertRaisesMessage(ValidationError, ALOJAMIENTO_SOLAPADO):
            self._ingresar(-4)

    def test_ingreso_en_el_instante_del_egreso_anterior_se_permite(self):
        self._cerrada()
        self.assertTrue(self._ingresar(-2).activa)

    def test_ingreso_despues_del_egreso_anterior_se_permite(self):
        self._cerrada()
        self.assertTrue(self._ingresar(-1).activa)

    def test_una_estadia_historica_sin_duracion_no_ocupa_un_intervalo(self):
        self._cerrada(desde=-3, hasta=-3)
        self.assertTrue(self._ingresar(-4).activa)

    def test_egreso_en_el_instante_del_ingreso_no_ocupa_un_intervalo(self):
        estadia = self._ingresar(-4)
        self._cerrada(desde=-6, hasta=-2)
        egresar_persona(
            estadia=estadia,
            usuario=self.operador_cis,
            motivo_egreso=self.motivo_alta,
            destino="Domicilio",
            fecha_egreso=estadia.fecha_ingreso,
        )
        estadia.refresh_from_db()
        self.assertFalse(estadia.activa)

    def test_egreso_retroactivo_no_confirma_un_intervalo_que_solapa_con_otro(self):
        estadia = self._ingresar(-6)
        self._cerrada(desde=-4, hasta=-2)
        with self.assertRaisesMessage(ValidationError, ALOJAMIENTO_SOLAPADO) as error:
            egresar_persona(
                estadia=estadia,
                usuario=self.operador_cis,
                motivo_egreso=self.motivo_alta,
                destino="Domicilio",
                fecha_egreso=AHORA - timedelta(days=3),
            )
        self.assertIn("fecha_egreso", error.exception.message_dict)
        estadia.refresh_from_db()
        self.assertTrue(estadia.activa)
        self.assertFalse(estadia.movimientos.filter(tipo="EGRESO").exists())

    def test_egreso_ignora_la_propia_estadia_y_el_historial_que_empieza_al_terminar(self):
        estadia = self._ingresar(-6)
        self._cerrada(desde=-2, hasta=-1)
        egresar_persona(
            estadia=estadia,
            usuario=self.operador_cis,
            motivo_egreso=self.motivo_alta,
            destino="  Domicilio  ",
            fecha_egreso=AHORA - timedelta(days=2),
        )
        estadia.refresh_from_db()
        self.assertEqual(estadia.destino_egreso, "Domicilio")
        self.assertFalse(estadia.activa)

    def test_destino_omitido_nulo_vacio_o_con_espacios_rechaza_sin_liberar_ni_trazar(self):
        estadia = self._ingresar(-1)
        for datos in ({}, {"destino": None}, {"destino": ""}, {"destino": " \t\n "}):
            with self.subTest(datos=datos), self.assertRaisesMessage(ValidationError, EGRESO_SIN_DESTINO) as error:
                egresar_persona(estadia=estadia, usuario=self.operador_cis, motivo_egreso=self.motivo_alta, **datos)
            self.assertIn("destino", error.exception.message_dict)
            estadia.refresh_from_db()
            self.assertTrue(estadia.activa)
            self.assertEqual(estadia.clave_alojamiento, Estadia.clave_para(self.persona))
            self.assertFalse(estadia.movimientos.filter(tipo="EGRESO").exists())
            self.assertFalse(TrazaDispositivo.objects.filter(accion="ESTADIA_EGRESO").exists())

    def test_sondeo_con_admitir_sin_ver_reconoce_la_institucion_propia(self):
        estadia = self._ingresar(-1)
        capacidades = ("dispositivo.admitir", "dispositivo.egresar", "dispositivo.editar")
        usuario = self._operador("Admite sin ver", self.cis, capacidades)
        resultado = verificar_alojamiento_en_red(self.persona, usuario)
        self.assertTrue(resultado.dentro_del_alcance)
        self.assertEqual(resultado.estadia_id, estadia.pk)
        self.assertEqual(resultado.dispositivo, self.cis.nombre)
        ajena = verificar_alojamiento_en_red(self.persona, self.operador_parador)
        self.assertTrue(ajena.alojada)
        self.assertFalse(ajena.dentro_del_alcance)
        self.assertEqual(ajena.dispositivo, "")
        self.assertIsNone(ajena.estadia_id)

    def test_candados_del_ingreso_van_plaza_reserva_persona(self):
        reserva = reservar_plaza(plaza=self.plaza, ciudadano=self.persona, usuario=self.operador_cis)
        with orden_de_candados(
            plaza=type(self.plaza).objects, reserva=type(reserva).objects, persona=Ciudadano.objects
        ) as orden:
            ingresar_persona(
                ciudadano=self.persona,
                dispositivo=self.cis,
                usuario=self.operador_cis,
                plaza=self.plaza,
                reserva=reserva,
            )
        self.assertEqual(orden, ["plaza", "reserva", "persona"])


@tag("performance")
class BusquedaDniTests(BaseEstadias):
    def _presupuesto(self, nombre):
        return json.loads((settings.BASE_DIR / "scripts/perf_budgets.json").read_text(encoding="utf-8"))["servicios"][
            nombre
        ]["consultas_fijas"]

    def test_dni_exacto_tiene_prioridad_y_no_escanea(self):
        duplicada = Ciudadano.objects.create(dni="99999999", nombre="Duplicada", apellido="Separadores")
        Ciudadano.objects.filter(pk=duplicada.pk).update(dni="30.111.222")
        with self.assertNumQueries(self._presupuesto("dispositivos_buscar_dni_exacto")):
            resultado = buscar_ciudadano_por_dni("30.111.222")
            self.assertEqual(resultado.pk, self.persona.pk)
            self.assertEqual(resultado.nombre, "Ana")

    def test_regexp_solo_lee_id_y_dni_e_instancia_el_ganador(self):
        Ciudadano.objects.filter(pk=self.persona.pk).update(dni="30.111.222")
        # bulk_create conserva la carga histórica sin pasar por save(), que normaliza DNI.
        Ciudadano.objects.bulk_create(
            [Ciudadano(dni=f"40.000.{n:03d}", nombre="Otra", apellido="Persona") for n in range(20)]
        )
        instanciados = []

        def registrar(sender, instance, **kwargs):
            instanciados.append(instance.pk)

        post_init.connect(registrar, sender=Ciudadano, weak=False)
        try:
            with CaptureQueriesContext(connection) as consultas:
                resultado = buscar_ciudadano_por_dni("30111222")
                self.assertEqual(resultado.nombre, "Ana")
                self.assertEqual(resultado.apellido, "Gómez")
        finally:
            post_init.disconnect(registrar, sender=Ciudadano)
        self.assertEqual(resultado.pk, self.persona.pk)
        self.assertEqual(instanciados, [self.persona.pk])
        escaneo = next(q["sql"] for q in consultas if "REGEXP" in q["sql"])
        self.assertNotIn('"nombre"', escaneo)
        self.assertNotIn('"apellido"', escaneo)
        self.assertEqual(len(consultas), self._presupuesto("dispositivos_buscar_dni_separadores"))

    def test_dni_sin_coincidencias_o_vacio_no_hidrata_modelos(self):
        with self.assertNumQueries(2):
            self.assertIsNone(buscar_ciudadano_por_dni("99999999"))
        with self.assertNumQueries(0):
            self.assertIsNone(buscar_ciudadano_por_dni(""))
