"""Las carreras de la etapa 3 de Emergencia (alojar), corridas de verdad con dos conexiones.

Mismo andamio, mismo ``@tag("mysql")`` y mismo criterio que
``programas.tests.test_emergencia_concurrencia`` y
``programas.tests.test_emergencia_reservas_concurrencia``: en SQLite ``select_for_update()``
es un no-op y la carrera no existe, así que sin motor real estos casos **se saltean**
(``MotorRealMixin``). Los corre el job «Motor real» contra MariaDB y MySQL.

Lo que sostiene la etapa es el candado sobre **la fila del caso**, tomado antes que nada
(plan §8, R1: caso → derivación → plazas → reservas → persona). Cada caso afirma:

1. **Exactamente uno gana.**
2. **El otro recibe el error de dominio** —``EstadoCambio`` (el 409 de la API) o un
   ``ValidationError``—, nunca un ``IntegrityError`` crudo ni un deadlock (``ERROR 1213``).
3. **El estado final es consistente**: una aceptación, una estadía, una reserva resuelta
   una sola vez, y ningún legajo huérfano del que perdió.

La otra capa —que los candados se pidan, y en qué orden— es
``OrdenDeLosCandadosDeAlojarTests``, que corre en cada PR sobre SQLite.
"""

from datetime import timedelta

from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.test import tag

from core import rbac
from legajos.models import Ciudadano
from programas.models import (
    CasoEmergencia,
    Derivacion,
    Estadia,
    IntegranteGrupo,
    MiembroEquipoDispositivo,
    Plaza,
    Programa,
    ReservaPlaza,
    TrazaCaso,
)
from programas.services import emergencia as mesa
from programas.services import emergencia_alojar as servicio
from programas.services.emergencia import EstadoCambio
from programas.services.estadias import liberar_reserva
from programas.tests.test_dispositivos_concurrencia import _permiso, en_paralelo, punto_critico
from programas.tests.test_emergencia_alojar import ficha_minima
from programas.tests.test_emergencia_concurrencia import _RELOJ, CASO_BLOQUEADO, _BaseCarreraEmergencia
from users.models import RolMeta

Estado = CasoEmergencia.Estado


class _BaseCarreraDeAlojar(_BaseCarreraEmergencia):
    """La mesa de ``_BaseCarreraEmergencia`` más la guardia del Club y el caso ya derivado ahí."""

    def setUp(self):
        super().setUp()
        self.dispositivos, _ = Programa.objects.get_or_create(
            codigo="DISPOSITIVOS", defaults={"nombre": "Dispositivos", "tipo": Programa.TipoPrograma.DISPOSITIVOS}
        )
        self.guardia = self._guardia("guardia_conc")
        self.otra_guardia = self._guardia("otra_guardia_conc")
        mesa.tomar_caso(self.caso, self._fresco(self.ana))
        self.derivacion = mesa.derivar_caso(self.caso, self._fresco(self.ana), self.club, 2)

    def _guardia(self, nombre):
        rol = Group.objects.create(name=f"Rol {nombre}")
        RolMeta.objects.create(grupo=rol, categoria=rbac.CATEGORIA_PROGRAMA, programa=self.dispositivos, activo=True)
        rol.permissions.add(*[_permiso(codigo) for codigo in ("dispositivo.ver", "dispositivo.admitir")])
        usuario = User.objects.create_user(username=nombre)
        usuario.groups.add(rol)
        MiembroEquipoDispositivo.objects.create(dispositivo=self.club, usuario=usuario, rol=rol)
        return User.objects.get(pk=usuario.pk)

    def _aceptar(self, usuario):
        def operacion():
            return servicio.aceptar_derivacion(
                derivacion=Derivacion.objects.get(pk=self.derivacion.pk), usuario=self._fresco(usuario)
            )

        return operacion

    def _confirmar(self, usuario, orden, dni, plaza_pk):
        def operacion():
            return servicio.confirmar_integrante(
                caso=self._caso_en_pantalla(),
                orden=orden,
                usuario=self._fresco(usuario),
                ficha=ficha_minima(dni),
                plaza=plaza_pk,
            )

        return operacion

    def _reservas(self):
        return list(ReservaPlaza.objects.filter(derivacion=self.derivacion).order_by("plaza_id"))


@tag("mysql")
class CarreraDeAceptarTests(_BaseCarreraDeAlojar):
    def test_dos_guardias_aceptan_la_misma_derivacion_y_gana_una(self):
        """La app y el backoffice aceptan a la vez: una sola reserva de camas (03 §7, 409)."""

        resultados, errores = en_paralelo(
            self._aceptar(self.guardia), self._aceptar(self.otra_guardia), punto_a=CASO_BLOQUEADO
        )

        self.assertEqual(len(resultados), 1, "la derivación se aceptó dos veces")
        error = self._un_error(errores, EstadoCambio)
        self.assertEqual(error.estado_actual, Estado.INGRESO_EN_CURSO)
        self.assertEqual(CasoEmergencia.objects.get(pk=self.caso.pk).estado, Estado.INGRESO_EN_CURSO)
        self.assertEqual(Derivacion.objects.get(pk=self.derivacion.pk).estado, Derivacion.Estado.ACEPTADA)
        self.assertEqual(len(self._reservas()), 2, "las camas se reservaron dos veces")
        self.assertEqual(IntegranteGrupo.objects.filter(grupo=self.caso.grupo).count(), 2)
        self.assertEqual(
            TrazaCaso.objects.filter(caso=self.caso, accion=TrazaCaso.Accion.DERIVACION_ACEPTADA).count(), 1
        )

    def _vencer(self):
        def operacion():
            return mesa.vencer_derivacion(Derivacion.objects.get(pk=self.derivacion.pk))

        return operacion

    def _cumplir_el_plazo(self):
        Derivacion.objects.filter(pk=self.derivacion.pk).update(vence_en=_RELOJ - timedelta(minutes=10))

    def test_aceptar_le_gana_al_vencimiento_y_el_cron_no_toca_nada(self):
        """RN-3.3: con el plazo cumplido, si la guardia toma primero el caso, la derivación se acepta."""

        self._cumplir_el_plazo()

        resultados, errores = en_paralelo(self._aceptar(self.guardia), self._vencer(), punto_a=CASO_BLOQUEADO)

        self.assertEqual(errores, [])
        # El cron no levanta nada: devuelve ``None`` cuando la fila bloqueada ya no está para vencer.
        self.assertEqual(sum(1 for resultado in resultados if resultado is None), 1)
        self.assertEqual(Derivacion.objects.get(pk=self.derivacion.pk).estado, Derivacion.Estado.ACEPTADA)
        self.assertEqual(CasoEmergencia.objects.get(pk=self.caso.pk).estado, Estado.INGRESO_EN_CURSO)
        self.assertEqual(len(self._reservas()), 2)
        self.assertFalse(TrazaCaso.objects.filter(caso=self.caso, accion=TrazaCaso.Accion.DERIVACION_VENCIDA).exists())

    def test_el_vencimiento_le_gana_a_aceptar_y_no_queda_ninguna_cama_reservada(self):
        """El revés: el cron toma primero el caso; la guardia recibe «venció» y no reserva nada."""

        self._cumplir_el_plazo()

        resultados, errores = en_paralelo(self._vencer(), self._aceptar(self.guardia), punto_a=CASO_BLOQUEADO)

        self.assertEqual(len(resultados), 1)
        error = self._un_error(errores, EstadoCambio)
        self.assertIn("venció", error.mensaje)
        self.assertEqual(Derivacion.objects.get(pk=self.derivacion.pk).estado, Derivacion.Estado.VENCIDA)
        self.assertEqual(CasoEmergencia.objects.get(pk=self.caso.pk).estado, Estado.EN_GESTION)
        self.assertEqual(self._reservas(), [])
        self.assertFalse(IntegranteGrupo.objects.filter(grupo=self.caso.grupo).exists())


@tag("mysql")
class CarreraDeConfirmarTests(_BaseCarreraDeAlojar):
    def setUp(self):
        super().setUp()
        servicio.aceptar_derivacion(derivacion=self.derivacion, usuario=self._fresco(self.guardia))
        self.reservas = self._reservas()

    def test_dos_guardias_confirman_a_la_misma_persona_y_queda_una_sola_estadia(self):
        """03 §10: la app y el backoffice confirman la fila 2, cada uno en una cama distinta.

        El candado del caso los serializa: la segunda lee la fila ya confirmada y recibe
        ``EstadoCambio`` antes de dar de alta nada. Sin él, las dos darían de alta a la
        persona —o chocarían en su UNIQUE— y una quedaría con una cama consumida de más.
        """

        resultados, errores = en_paralelo(
            self._confirmar(self.guardia, 2, "45000111", self.reservas[0].plaza_id),
            self._confirmar(self.otra_guardia, 2, "45000111", self.reservas[1].plaza_id),
            punto_a=CASO_BLOQUEADO,
        )

        self.assertEqual(len(resultados), 1, "la misma persona se confirmó dos veces")
        self._un_error(errores, EstadoCambio)
        self.assertEqual(Ciudadano.objects.filter(dni="45000111").count(), 1)
        self.assertEqual(Estadia.objects.activas().count(), 1)
        self.assertEqual(
            ReservaPlaza.objects.filter(derivacion=self.derivacion, estado=ReservaPlaza.Estado.CONSUMIDA).count(), 1
        )
        self.assertEqual(
            ReservaPlaza.objects.filter(derivacion=self.derivacion, estado=ReservaPlaza.Estado.VIGENTE).count(), 1
        )
        self.assertEqual(IntegranteGrupo.objects.filter(grupo=self.caso.grupo, confirmada_en__isnull=False).count(), 1)

    def test_dos_personas_distintas_en_la_misma_cama_dejan_un_solo_ocupante(self):
        """Dos filas de la misma familia apuntan a la misma cama reservada: entra una."""

        cama = self.reservas[0].plaza_id

        resultados, errores = en_paralelo(
            self._confirmar(self.guardia, 1, "45000111", cama),
            self._confirmar(self.otra_guardia, 2, "45000222", cama),
            punto_a=CASO_BLOQUEADO,
        )

        self.assertEqual(len(resultados), 1, "la cama quedó con dos personas")
        error = self._un_error(errores, ValidationError)
        self.assertIn("plaza", error.message_dict)
        self.assertEqual(Estadia.objects.activas().filter(plaza_id=cama).count(), 1)
        # El que perdió no dejó su legajo: el alta y el ingreso son una sola transacción (RN-3.7).
        self.assertEqual(Ciudadano.objects.filter(dni__in=["45000111", "45000222"]).count(), 1)

    def test_confirmar_y_liberar_la_cama_desde_el_mapa_la_resuelven_una_sola_vez(self):
        """La guardia confirma mientras otro operador libera esa cama desde «Sectores y plazas».

        ``liberar_reserva`` no pasa por Emergencia —no bloquea el caso—: los dos caminos se
        encuentran en la **plaza**, que los dos piden antes que la reserva. Gane quien gane,
        la reserva queda resuelta una sola vez y no hay ``ERROR 1213``.
        """

        reserva = self.reservas[0]

        def liberar():
            return liberar_reserva(
                reserva=ReservaPlaza.objects.get(pk=reserva.pk),
                usuario=self._fresco(self.otra_guardia),
                motivo="La cama se necesita para otra persona",
            )

        resultados, errores = en_paralelo(
            self._confirmar(self.guardia, 2, "45000111", reserva.plaza_id),
            liberar,
            punto_a=punto_critico(Plaza, "_bloquear_plaza"),
            punto_b=punto_critico(Plaza, "liberar_reserva", limite=1),
        )

        self.assertEqual(len(resultados), 1, "la reserva se consumió y se liberó")
        self._un_error(errores, ValidationError)
        reserva.refresh_from_db()
        alojada = Estadia.objects.activas().filter(plaza_id=reserva.plaza_id).exists()
        if reserva.estado == ReservaPlaza.Estado.CONSUMIDA:
            self.assertTrue(alojada, "la reserva se consumió y nadie quedó alojado")
            self.assertTrue(IntegranteGrupo.objects.get(grupo=self.caso.grupo, orden=2).confirmada)
        else:
            self.assertEqual(reserva.estado, ReservaPlaza.Estado.LIBERADA)
            self.assertFalse(alojada, "la reserva se liberó y quedó alguien alojado igual")
            self.assertFalse(Ciudadano.objects.filter(dni="45000111").exists(), "quedó el legajo del que no entró")
            self.assertFalse(IntegranteGrupo.objects.get(grupo=self.caso.grupo, orden=2).confirmada)

    def test_confirmar_y_cerrar_con_diferencia_a_la_vez_no_dejan_una_reserva_a_medias(self):
        """Una guardia confirma a la segunda persona mientras la otra cierra el ingreso con diferencia.

        Los dos toman primero el caso. Si gana la confirmación, el cierre cuenta dos de dos y
        se rechaza («no hay diferencia»); si gana el cierre, la confirmación llega tarde
        (``EstadoCambio``) y su cama ya se liberó. En los dos casos no queda una reserva vigente
        de un caso alojado.
        """

        servicio.confirmar_integrante(
            caso=self.caso,
            orden=1,
            usuario=self._fresco(self.guardia),
            ficha=ficha_minima("45000111"),
            plaza=self.reservas[0].plaza_id,
        )

        def cerrar():
            return servicio.cerrar_con_diferencia(
                caso=self._caso_en_pantalla(), usuario=self._fresco(self.otra_guardia), motivo="NO_LLEGO"
            )

        resultados, errores = en_paralelo(
            self._confirmar(self.guardia, 2, "45000222", self.reservas[1].plaza_id), cerrar, punto_a=CASO_BLOQUEADO
        )

        self.assertEqual(len(resultados), 1)
        self.assertEqual(len(errores), 1, f"se esperaba un solo perdedor: {[repr(e) for e in errores]}")
        self.assertIsInstance(errores[0], (EstadoCambio, ValidationError))
        caso = CasoEmergencia.objects.get(pk=self.caso.pk)
        if caso.estado == Estado.ALOJADO:
            self.assertFalse(
                ReservaPlaza.objects.filter(derivacion=self.derivacion, estado=ReservaPlaza.Estado.VIGENTE).exists()
            )
            self.assertEqual(caso.total_alojado, Estadia.objects.activas().count())
        else:
            self.assertEqual(caso.estado, Estado.INGRESO_EN_CURSO)
            self.assertEqual(Estadia.objects.activas().count(), 2)
