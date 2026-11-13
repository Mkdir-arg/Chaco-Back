"""Emergencia, etapa 3 sin derivación (``services.emergencia_sin_derivacion``).

**RN-3.10** — el ingreso directo («Ingresar igual») y **M2-6** — el aviso a la mesa.
"""

import uuid
from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError

from core.models import Localidad
from legajos.models import Ciudadano
from programas.models import (
    CasoEmergencia,
    Derivacion,
    EntradaBitacora,
    Estadia,
    IntegranteGrupo,
    ReservaPlaza,
    TrazaCaso,
)
from programas.selectors import emergencia_alojar as selectores
from programas.services import emergencia as mesa
from programas.services import emergencia_alojar as servicio
from programas.tests.test_emergencia_alojar_base import BaseAlojar
from programas.tests.test_emergencia_casos import T0

Estado = CasoEmergencia.Estado
Accion = TrazaCaso.Accion


class IngresoDirectoTests(BaseAlojar):
    def _formulario(self, **cambios):
        datos = self._datos(dni="33444555", nombre="Marta", apellido="Ríos", adultos_f=1, adultos_m=1, menores_f=1)
        del datos["direccion"]
        datos.update(cambios)
        return datos

    def test_el_ingreso_directo_nace_con_el_ingreso_en_curso_sin_pasar_por_la_mesa(self):
        """HU-3.6, RN-3.10."""

        self._turno(self.club)
        resistencia = Localidad.objects.create(nombre="Resistencia")

        caso = servicio.ingreso_directo(
            dispositivo=self.club, usuario=self.guardia, datos_formulario1=self._formulario()
        )

        fila = self._fila(caso)
        self.assertEqual(fila["origen"], CasoEmergencia.Origen.DISPOSITIVO)
        self.assertEqual(fila["estado"], Estado.INGRESO_EN_CURSO)
        self.assertIsNone(fila["tomado_por_id"])
        self.assertEqual(fila["relevado_por_id"], self.guardia.pk)
        self.assertEqual(fila["tomado_en"], fila["creado"])
        self.assertEqual(fila["derivado_en"], fila["creado"])
        self.assertEqual(fila["aceptado_en"], fila["creado"])
        self.assertEqual(fila["localidad_id"], resistencia.pk, "no tomó la localidad del dispositivo")
        self.assertEqual(fila["direccion"], "Se presentó en Club Sarmiento")
        derivacion = Derivacion.objects.get(caso=caso)
        self.assertEqual((derivacion.estado, derivacion.dispositivo), (Derivacion.Estado.ACEPTADA, self.club))
        self.assertEqual(derivacion.plazas_pedidas, 3)
        self.assertEqual(len(self._reservas(derivacion)), 3)
        self.assertEqual(IntegranteGrupo.objects.filter(grupo=caso.grupo).count(), 3)
        self.assertEqual((caso.reservadas, caso.faltantes), (3, 0))
        self.assertTrue(servicio.es_ingreso_directo(caso))
        self.assertEqual([t.accion for t in self._trazas(caso)], [Accion.CREADO, Accion.INGRESO_DIRECTO])
        self.assertTrue(EntradaBitacora.objects.filter(tipo="GENERAL", texto__contains="ingreso directo").exists())

    def test_despues_sigue_el_mismo_camino_hasta_alojado(self):
        caso = servicio.ingreso_directo(
            dispositivo=self.club, usuario=self.guardia, datos_formulario1=self._formulario(menores_f=0)
        )
        derivacion = Derivacion.objects.get(caso=caso)
        for orden, reserva in enumerate(self._reservas(derivacion), start=1):
            self._confirmar(caso, orden, str(45_000_100 + orden), plaza=reserva.plaza)

        servicio.alojar_familia(caso=caso, usuario=self.guardia)

        self.assertEqual(self._estado(caso), Estado.ALOJADO)

    def test_reserva_hasta_donde_alcance(self):
        self._ocupar(self.club, 7)
        caso = servicio.ingreso_directo(
            dispositivo=self.club, usuario=self.guardia, datos_formulario1=self._formulario()
        )
        self.assertEqual((caso.reservadas, caso.faltantes), (2, 1))

    def test_sin_camas_libres_no_hay_ingreso_directo_y_no_queda_el_caso(self):
        self._ocupar(self.club, 9)
        with self.assertRaises(ValidationError) as error:
            servicio.ingreso_directo(dispositivo=self.club, usuario=self.guardia, datos_formulario1=self._formulario())
        self.assertEqual(error.exception.message_dict["plazas"], [servicio.SIN_CAMAS_PARA_INGRESO_DIRECTO])
        self.assertFalse(CasoEmergencia.objects.exists())
        self.assertFalse(Ciudadano.objects.filter(dni="33444555").exists())

    def test_exige_alcance_sobre_ese_dispositivo(self):
        for usuario in (self.guardia_escuela, self.operador):
            with self.subTest(usuario=usuario.username), self.assertRaises(PermissionDenied):
                servicio.ingreso_directo(dispositivo=self.club, usuario=usuario, datos_formulario1=self._formulario())
        self.assertFalse(CasoEmergencia.objects.exists())

    def test_el_formulario_1_se_valida_igual_que_en_la_mesa(self):
        with self.assertRaises(ValidationError) as error:
            servicio.ingreso_directo(
                dispositivo=self.club,
                usuario=self.guardia,
                datos_formulario1=self._formulario(adultos_f=0, adultos_m=0, menores_f=0),
            )
        self.assertIn("total", error.exception.error_dict)
        self.assertFalse(ReservaPlaza.objects.exists())

    def test_reenviar_el_mismo_envio_devuelve_el_mismo_caso_aunque_ya_no_haya_camas(self):
        """RU-16: es lo único de la etapa que la app encola sin conexión."""

        envio = uuid.uuid4()
        primero = servicio.ingreso_directo(
            dispositivo=self.club, usuario=self.guardia, datos_formulario1=self._formulario(), uuid_cliente=envio
        )
        self._ocupar_todo()

        segundo = servicio.ingreso_directo(
            dispositivo=self.club, usuario=self.guardia, datos_formulario1=self._formulario(), uuid_cliente=str(envio)
        )

        self.assertEqual(primero.pk, segundo.pk)
        self.assertTrue(segundo.ya_existia)
        self.assertEqual((segundo.reservadas, segundo.faltantes), (primero.reservadas, primero.faltantes))
        self.assertEqual(CasoEmergencia.objects.count(), 1)
        self.assertEqual(ReservaPlaza.objects.filter(derivacion__caso=primero).count(), 3)

    def _ocupar_todo(self):
        for plaza in selectores.camas_libres(self.club):
            persona = Ciudadano.objects.create(dni=str(next(self._dnis)), nombre="Persona", apellido="Alojada")
            Estadia.objects.create(
                ciudadano=persona,
                dispositivo=self.club,
                plaza=plaza,
                fecha_ingreso=T0 - timedelta(days=1),
                clave_alojamiento=Estadia.clave_para(persona),
            )

    def test_cancelar_un_ingreso_directo_lo_deja_en_la_bandeja(self):
        """No tiene dueño en la mesa: «en gestión» sin operador no lo vería nadie."""

        caso = servicio.ingreso_directo(
            dispositivo=self.club, usuario=self.guardia, datos_formulario1=self._formulario()
        )
        servicio.cancelar_ingreso(caso=caso, usuario=self.guardia, motivo="Se fueron")
        self.assertEqual(self._estado(caso), Estado.NUEVO)


class AvisarALaMesaTests(BaseAlojar):
    def _formulario(self):
        return self._datos(dni="33444555", nombre="Marta", apellido="Ríos")

    def test_avisar_crea_un_caso_nuevo_en_la_puerta_del_dispositivo(self):
        """M2-6: no reserva nada; la mesa lo ve en la bandeja."""

        self._ocupar(self.club, 9)  # se usa justo cuando no hay lugar

        caso = servicio.avisar_a_la_mesa(
            dispositivo=self.club, usuario=self.guardia, datos_formulario1=self._formulario()
        )

        fila = self._fila(caso)
        self.assertEqual((fila["estado"], fila["origen"]), (Estado.NUEVO, CasoEmergencia.Origen.DISPOSITIVO))
        self.assertEqual(
            fila["situacion"]["en_la_puerta_de"], {"dispositivo_id": self.club.pk, "dispositivo": "Club Sarmiento"}
        )
        self.assertFalse(Derivacion.objects.exists())
        self.assertFalse(ReservaPlaza.objects.exists())
        self.assertFalse(servicio.es_ingreso_directo(caso))
        self.assertEqual(self._trazas(caso)[-1].detalle, "En la puerta de Club Sarmiento · esperando derivación")

    def test_la_mesa_deriva_y_la_guardia_busca_de_nuevo(self):
        """03 §10: llega una persona antes de que la mesa derive."""

        caso = servicio.avisar_a_la_mesa(
            dispositivo=self.club, usuario=self.guardia, datos_formulario1=self._formulario()
        )
        sin_derivar = servicio.buscar_por_dni(dispositivo=self.club, dni="33444555", usuario=self.guardia)
        self.assertEqual(sin_derivar.resultado, servicio.BUSQUEDA_SIN_DERIVACION)

        mesa.derivar_caso(mesa.tomar_caso(caso, self.operador), self.operador, self.club, 2)
        derivada = servicio.buscar_por_dni(dispositivo=self.club, dni="33444555", usuario=self.guardia)

        self.assertEqual(derivada.resultado, servicio.BUSQUEDA_DERIVACION)
        self.assertEqual(derivada.caso.pk, caso.pk)

    def test_es_idempotente_y_exige_alcance(self):
        envio = uuid.uuid4()
        argumentos = {"dispositivo": self.club, "usuario": self.guardia, "datos_formulario1": self._formulario()}
        primero = servicio.avisar_a_la_mesa(**argumentos, uuid_cliente=envio)
        segundo = servicio.avisar_a_la_mesa(**argumentos, uuid_cliente=envio)
        self.assertEqual(primero.pk, segundo.pk)
        self.assertEqual(TrazaCaso.objects.filter(accion=Accion.AVISO_A_LA_MESA).count(), 1)

        with self.assertRaises(PermissionDenied):
            servicio.avisar_a_la_mesa(
                dispositivo=self.club, usuario=self.guardia_escuela, datos_formulario1=self._formulario()
            )
