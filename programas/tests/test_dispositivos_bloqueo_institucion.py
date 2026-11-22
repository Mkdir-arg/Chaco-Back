"""La institución se bloquea primero, en compartido (pendiente del Cambio 536).

Cada camino que toca plazas, reservas o estadías de una institución pide la fila de la institución
con un bloqueo **compartido** (`dispositivos.bloquear_institucion`, SQL crudo con
`LOCK IN SHARE MODE`) **antes** de bloquear la plaza. Así ninguno se cuela en una institución que
otro operador está cerrando o inactivando, y el orden de los candados es uno solo en todos los
caminos: institución → plaza → reserva / estadía → persona.

Se prueba por la secuencia de llamadas, como `OrdenDeLosCandadosTests`: en SQLite no hay candados.
La carrera real se midió contra MariaDB 10.11 con dos conexiones (ver el Cambio en
`docs/internal/requerimientos.md`).

Mutaciones verificadas (cada una pone en rojo su test): sacar la llamada de `ingresar_persona`,
`liberar_reserva`, `egresar_persona`, `asignar_plaza`, `sacar_plaza_de_servicio`,
`volver_plaza_a_servicio`, `exigir_institucion_en_estado` (reservar y cambiar de plaza),
`confirmar_ingreso`, `reservar_plazas_de_derivacion`, `consumir_reserva_de_derivacion`,
`liberar_reservas_de_derivacion`, `_liberar_la_sobrante` y `_ingresar_en_cama_libre`; volver a
poner la estadía antes que el dispositivo en `registrar_entrada`; y sacar el control de
transacción del helper.
"""

from contextlib import contextmanager
from datetime import datetime, time
from unittest import mock

from django.db import connection, transaction
from django.db.transaction import TransactionManagementError
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from core import db
from core.tests.candados import orden_de_candados
from legajos.models import Ciudadano
from programas.models import Dispositivo, EntradaBitacora, Estadia, Plaza, ReservaPlaza, TipoDispositivo, Turno
from programas.services import emergencia_alojar as servicio
from programas.services.bitacora import registrar_entrada
from programas.services.dispositivos import bloquear_institucion, bloquear_instituciones
from programas.services.estadias import (
    asignar_plaza,
    cambiar_plaza,
    egresar_persona,
    ingresar_persona,
    liberar_reserva,
    reservar_plaza,
    sacar_plaza_de_servicio,
    volver_plaza_a_servicio,
)
from programas.services.estado_institucion import inactivar_dispositivo
from programas.services.ingreso import confirmar_ingreso
from programas.tests.test_dispositivos_estadias import CAPACIDADES_OPERATIVAS, BaseEstadias
from programas.tests.test_emergencia_alojar_base import BaseAlojar
from programas.tests.test_emergencia_quitar_persona import BaseQuitar


def _orden():
    return orden_de_candados(
        compartido="institucion",
        dispositivo=Dispositivo.objects,
        plaza=Plaza.objects,
        reserva=ReservaPlaza.objects,
        estadia=Estadia.objects,
        persona=Ciudadano.objects,
    )


def _sin_repetir(orden):
    """El orden en que cada tipo de fila se pide **por primera vez**."""

    return list(dict.fromkeys(orden))


@contextmanager
def _espiar_bloqueos_compartidos():
    """Las instituciones que cada llamada a `leer_con_bloqueo_compartido` tomó, en orden de llamada."""

    llamadas = []
    original = db.leer_con_bloqueo_compartido

    def espiar(modelo, pks, campo):
        llamadas.append(set(pks))
        return original(modelo, pks, campo)

    with mock.patch.object(db, "leer_con_bloqueo_compartido", espiar):
        yield llamadas


class _InstitucionPrimero:
    def assertInstitucionAntesDeLaPlaza(self, orden):
        self.assertIn("institucion", orden, f"no bloqueó la institución: {orden}")
        if "plaza" in orden:
            self.assertLess(orden.index("institucion"), orden.index("plaza"), f"bloqueó la plaza antes: {orden}")


class HelperFueraDeTransaccionTests(TransactionTestCase):
    def test_exige_estar_dentro_de_una_transaccion(self):
        """Fuera de `atomic()` el candado se soltaría al terminar la consulta: se rechaza, como `select_for_update`."""

        with self.assertRaises(TransactionManagementError):
            db.leer_con_bloqueo_compartido(Dispositivo, [1], "estado")
        with transaction.atomic():
            self.assertEqual(db.leer_con_bloqueo_compartido(Dispositivo, [1], "estado"), {})


class HelperTests(TestCase):
    def test_devuelve_el_estado_fresco_de_cada_institucion(self):
        tipo = TipoDispositivo.objects.create(codigo="T-BQ", nombre="Tipo")
        a = Dispositivo.objects.create(tipo=tipo, codigo="A-BQ", nombre="A", estado=Dispositivo.Estado.ACTIVO)
        b = Dispositivo.objects.create(tipo=tipo, codigo="B-BQ", nombre="B", estado=Dispositivo.Estado.CERRADO)
        Dispositivo.objects.filter(pk=a.pk).update(estado=Dispositivo.Estado.INACTIVO)
        with transaction.atomic():
            self.assertEqual(
                bloquear_instituciones([b.pk, a.pk, None]),
                {a.pk: Dispositivo.Estado.INACTIVO, b.pk: Dispositivo.Estado.CERRADO},
            )
            self.assertEqual(bloquear_institucion(a), Dispositivo.Estado.INACTIVO)
            self.assertIsNone(bloquear_institucion(999999))
            self.assertEqual(bloquear_instituciones([]), {})

    def test_en_mysql_y_mariadb_pide_lock_in_share_mode_ordenado_por_pk(self):
        """El SQL que llega al motor: la sintaxis que entienden los dos y las filas por pk."""

        cursor = mock.MagicMock()
        abierto = cursor.return_value.__enter__.return_value
        abierto.fetchall.return_value = [(3, "ACTIVO"), (7, "INACTIVO")]
        with transaction.atomic():
            with mock.patch.object(connection, "vendor", "mysql"), mock.patch.object(connection, "cursor", cursor):
                filas = db.leer_con_bloqueo_compartido(Dispositivo, [7, 3, 7], "estado")
        sql, parametros = abierto.execute.call_args.args
        self.assertEqual(filas, {3: "ACTIVO", 7: "INACTIVO"})
        self.assertEqual(parametros, [3, 7])
        q = connection.ops.quote_name
        self.assertTrue(sql.endswith(f" ORDER BY {q('id')} LOCK IN SHARE MODE"), sql)
        self.assertIn(f"FROM {q('programas_dispositivo')} WHERE {q('id')} IN (%s, %s)", sql)


class CaminosDeDispositivosTests(_InstitucionPrimero, BaseEstadias):
    def setUp(self):
        super().setUp()
        reloj = mock.patch("django.utils.timezone.now", return_value=timezone.make_aware(datetime(2026, 9, 7, 10)))
        reloj.start()
        self.addCleanup(reloj.stop)

    def test_reservar(self):
        with _orden() as orden:
            reservar_plaza(plaza=self.plaza, ciudadano=self.persona, usuario=self.operador_cis)
        self.assertEqual(_sin_repetir(orden), ["institucion", "plaza", "persona"])

    def test_liberar(self):
        reserva = reservar_plaza(plaza=self.plaza, ciudadano=self.persona, usuario=self.operador_cis)
        with _orden() as orden:
            liberar_reserva(reserva=reserva, usuario=self.operador_cis, motivo="No vino")
        self.assertEqual(orden, ["institucion", "plaza", "reserva"])

    def test_ingresar_con_reserva(self):
        reserva = reservar_plaza(plaza=self.plaza, ciudadano=self.persona, usuario=self.operador_cis)
        with _orden() as orden:
            ingresar_persona(
                ciudadano=self.persona,
                dispositivo=self.cis,
                plaza=self.plaza,
                usuario=self.operador_cis,
                reserva=reserva,
            )
        self.assertEqual(_sin_repetir(orden), ["institucion", "plaza", "reserva", "persona"])

    def test_ingresar_sin_plaza_tambien_toma_la_institucion(self):
        with _orden() as orden:
            ingresar_persona(ciudadano=self.persona, dispositivo=self.cis, usuario=self.operador_cis)
        self.assertEqual(_sin_repetir(orden), ["institucion", "persona"])

    def test_ingresar_lee_el_estado_fresco_y_no_el_del_objeto(self):
        """El estado sale de la fila bloqueada: el objeto que llega puede ser de antes de inactivarla."""

        viejo = Dispositivo.objects.get(pk=self.cis.pk)
        Dispositivo.objects.filter(pk=self.cis.pk).update(estado=Dispositivo.Estado.INACTIVO)
        with self.assertRaisesMessage(Exception, "Solo se puede alojar en un dispositivo activo."):
            ingresar_persona(ciudadano=self.persona, dispositivo=viejo, plaza=self.plaza, usuario=self.operador_cis)
        self.assertFalse(Estadia.objects.exists())

    def test_cambiar_de_plaza(self):
        estadia = ingresar_persona(
            ciudadano=self.persona, dispositivo=self.cis, plaza=self.plaza, usuario=self.operador_cis
        )
        with _orden() as orden:
            cambiar_plaza(estadia=estadia, plaza=self.otra_plaza, usuario=self.operador_cis, motivo="Pidió cambio")
        self.assertEqual(_sin_repetir(orden), ["institucion", "plaza", "estadia"])

    def test_asignar_plaza(self):
        estadia = ingresar_persona(ciudadano=self.persona, dispositivo=self.cis, usuario=self.operador_cis)
        self.tipo.plaza_obligatoria_al_ingresar = True  # sin plaza al ingresar, pero el tipo maneja plazas
        self.tipo.save()
        with _orden() as orden:
            asignar_plaza(estadia=estadia, plaza=self.plaza, usuario=self.operador_cis)
        self.assertEqual(_sin_repetir(orden), ["institucion", "plaza", "estadia"])

    def test_egresar(self):
        estadia = ingresar_persona(
            ciudadano=self.persona, dispositivo=self.cis, plaza=self.plaza, usuario=self.operador_cis
        )
        with _orden() as orden:
            egresar_persona(estadia=estadia, usuario=self.operador_cis, motivo_egreso=self.motivo_alta, destino="Casa")
        self.assertEqual(orden[:2], ["institucion", "estadia"])

    def test_sacar_y_volver_a_servicio(self):
        with _orden() as orden:
            sacar_plaza_de_servicio(plaza=self.plaza, usuario=self.operador_cis, motivo="Rota")
        self.assertEqual(orden, ["institucion", "plaza"])
        with _orden() as orden:
            volver_plaza_a_servicio(plaza=Plaza.objects.get(pk=self.plaza.pk), usuario=self.operador_cis)
        self.assertEqual(orden, ["institucion", "plaza"])

    def test_inactivar_toma_la_institucion_en_exclusivo_y_despues_las_plazas(self):
        """El otro lado de la carrera: el mismo orden, con la institución en exclusivo."""

        reservar_plaza(plaza=self.plaza, ciudadano=self.persona, usuario=self.operador_cis)
        with _orden() as orden:
            inactivar_dispositivo(self.cis, self.operador_cis)
        self.assertEqual(_sin_repetir(orden), ["dispositivo", "institucion", "plaza", "reserva"])

    def test_el_ingreso_toma_de_una_vez_las_instituciones_de_las_reservas_que_cierra(self):
        """`confirmar_ingreso` cierra reservas de otros dispositivos: todas las instituciones primero, por pk."""

        reservar_plaza(plaza=self.plaza_parador, ciudadano=self.persona, usuario=self.operador_parador)
        with _espiar_bloqueos_compartidos() as llamadas:
            with _orden() as orden:
                confirmar_ingreso(
                    dispositivo=self.cis,
                    usuario=self.operador_cis,
                    ciudadano_id=self.persona.pk,
                    datos_renaper=None,
                    plaza_id=self.plaza.pk,
                )
        self.assertInstitucionAntesDeLaPlaza(orden)
        self.assertEqual(llamadas[0], {self.cis.pk, self.parador.pk})
        self.assertEqual(ReservaPlaza.objects.get(plaza=self.plaza_parador).estado, ReservaPlaza.Estado.LIBERADA)

    def test_la_novedad_con_personas_toma_el_dispositivo_antes_que_la_estadia(self):
        """Institución → estadía, como el cambio de plaza: con el orden inverso se esperaban en cruz."""

        operador = self._operador("Operador bitácora", self.cis, (*CAPACIDADES_OPERATIVAS, "dispositivo.bitacora"))
        Turno.objects.create(dispositivo=self.cis, nombre="Guardia", hora_desde=time(0), hora_hasta=time(0))
        estadia = ingresar_persona(ciudadano=self.persona, dispositivo=self.cis, usuario=self.operador_cis)
        with _orden() as orden:
            registrar_entrada(
                dispositivo=self.cis,
                usuario=operador,
                tipo=EntradaBitacora.Tipo.GENERAL,
                texto="Durmió bien.",
                personas=[estadia.pk],
            )
        self.assertEqual(orden, ["dispositivo", "estadia"])


class CaminosDeEmergenciaTests(_InstitucionPrimero, BaseAlojar):
    def test_aceptar_reserva_las_camas_con_la_institucion_tomada(self):
        _caso, derivacion = self._derivado(plazas=2)
        with _orden() as orden:
            servicio.aceptar_derivacion(derivacion=derivacion, usuario=self.guardia)
        self.assertEqual(_sin_repetir(orden), ["institucion", "plaza"])

    def test_ingreso_directo(self):
        datos = self._datos(dni="33444555", nombre="Marta", apellido="Ríos")
        with _orden() as orden:
            servicio.ingreso_directo(dispositivo=self.club, usuario=self.guardia, datos_formulario1=datos)
        self.assertInstitucionAntesDeLaPlaza(orden)

    def test_confirmar_consumiendo_la_reserva_de_la_familia(self):
        caso, _derivacion = self._aceptado(plazas=2)
        with _orden() as orden:
            self._confirmar(caso, 2, "45000111")
        self.assertEqual(_sin_repetir(orden), ["institucion", "plaza", "reserva", "persona"])

    def test_confirmar_en_una_cama_libre_cerrando_una_reserva_de_otro_dispositivo(self):
        caso, _derivacion = self._aceptado()
        persona = Ciudadano.objects.create(dni="45000111", nombre="Juan", apellido="Pérez")
        escuela = Plaza.objects.filter(sector__dispositivo=self.escuela).order_by("pk").first()
        reservar_plaza(plaza=escuela, ciudadano=persona, usuario=self.guardia_escuela)
        with _espiar_bloqueos_compartidos() as llamadas:
            with _orden() as orden:
                self._confirmar(caso, 2, "45000111", plaza=self._cama_libre())
        self.assertEqual(_sin_repetir(orden), ["institucion", "plaza", "reserva", "persona"])
        self.assertEqual(llamadas[0], {self.club.pk, self.escuela.pk})

    def test_cerrar_con_diferencia_libera_con_la_institucion_tomada(self):
        caso, _derivacion = self._aceptado(menores_f=0, menores_m=0, plazas=2)
        self._confirmar(caso, 1, "45000101")
        with _orden() as orden:
            servicio.cerrar_con_diferencia(caso=caso, usuario=self.guardia, motivo="NO_LLEGO")
        self.assertEqual(_sin_repetir(orden), ["institucion", "plaza", "reserva"])


class QuitarIntegranteTests(_InstitucionPrimero, BaseQuitar):
    def test_quitar_libera_la_sobrante_con_la_institucion_tomada(self):
        self._agregar()
        self._confirmar_agregada(2)
        with _orden() as orden:
            servicio.quitar_integrante(caso=self.caso, orden=4, usuario=self.guardia_b)
        self.assertEqual(_sin_repetir(orden), ["institucion", "plaza", "reserva"])
