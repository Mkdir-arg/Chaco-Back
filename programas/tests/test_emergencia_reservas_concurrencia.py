"""Las carreras de las reservas de derivación, con dos conexiones de verdad (Emergencia, PR 6).

Mismo patrón, mismos helpers y mismo `@tag("mysql")` que
`programas.tests.test_dispositivos_concurrencia`, del que salen `en_paralelo`,
`punto_critico` y `_BaseCarrera`: en SQLite `select_for_update()` es un no-op y la carrera no
existe, así que sin motor real estos casos **se saltean** (`MotorRealMixin`). Los corre el
job «Motor real» contra MariaDB y MySQL.

Cada caso afirma lo mismo que allá: exactamente uno gana, el otro recibe el error de
dominio (nunca un deadlock ni un `IntegrityError` crudo) y el estado final es consistente.

La otra capa —que los candados se pidan, y en qué orden— es
`OrdenDeLosCandadosDeDerivacionTests`, que corre en cada PR sobre SQLite.
"""

from datetime import timedelta

from django.test import tag

from legajos.models import Ciudadano
from programas.models import (
    CasoEmergencia,
    Derivacion,
    Dispositivo,
    Estadia,
    GrupoFamiliar,
    Plaza,
    ReservaPlaza,
)
from programas.services.estadias import ingresar_persona, liberar_reserva
from programas.services.reservas_derivacion import (
    consumir_reserva_de_derivacion,
    reservar_plazas_de_derivacion,
)
from programas.tests.test_dispositivos_concurrencia import (
    _RELOJ,
    PLAZA_BLOQUEADA,
    _BaseCarrera,
    en_paralelo,
    punto_critico,
)

#: El `FOR UPDATE` que toma todas las plazas de una aceptación: el punto por el que compiten
#: dos aceptaciones con camas en común. Sin JOIN, así que no se confunde con el conteo previo.
PLAZAS_DE_LA_DERIVACION = punto_critico(Plaza, "reservar_plazas_de_derivacion")


class _BaseCarreraDeDerivacion(_BaseCarrera):
    """El terreno de `_BaseCarrera` más una familia derivada al CIS, con Ana de responsable."""

    def setUp(self):
        super().setUp()
        self.derivacion = self._derivacion(self.ana)

    def _derivacion(self, responsable):
        correlativo = CasoEmergencia.objects.count() + 1
        grupo = GrupoFamiliar.objects.create(
            responsable=responsable,
            traslado=GrupoFamiliar.Traslado.BOMBEROS,
            adultos_f=1,
            total_declarado=3,
        )
        caso = CasoEmergencia.objects.create(
            numero=CasoEmergencia.formatear_numero(2026, correlativo),
            grupo=grupo,
            origen=CasoEmergencia.Origen.MESA,
            estado=CasoEmergencia.Estado.INGRESO_EN_CURSO,
            prioridad=CasoEmergencia.Prioridad.MEDIA,
            direccion="Av. Sarmiento 100",
            relevado_por=self.operador,
            relevado_en=_RELOJ,
        )
        return Derivacion.objects.create(
            caso=caso,
            dispositivo=self.cis,
            estado=Derivacion.Estado.ACEPTADA,
            plazas_pedidas=3,
            vence_en=_RELOJ + timedelta(hours=2),
            derivada_por=self.operador,
        )

    def _reservar(self, derivacion_pk, plazas_pk):
        def operacion():
            return reservar_plazas_de_derivacion(
                derivacion=Derivacion.objects.get(pk=derivacion_pk),
                plazas=list(plazas_pk),
                usuario=self._fresco(self.operador),
            )

        return operacion

    def _consumir(self, reserva_pk, ciudadano_pk):
        def operacion():
            return consumir_reserva_de_derivacion(
                reserva=ReservaPlaza.objects.get(pk=reserva_pk),
                ciudadano=Ciudadano.objects.get(pk=ciudadano_pk),
                usuario=self._fresco(self.operador),
            )

        return operacion


@tag("mysql")
class CarreraDeReservaDeDerivacionTests(_BaseCarreraDeDerivacion):
    def test_dos_consumos_de_la_misma_reserva_alojan_a_uno_solo(self):
        """Dos guardias confirman a dos personas en la misma cama (PWA y backoffice a la vez).

        Sin el `FOR UPDATE` de la plaza y la relectura de la reserva, los dos la leen vigente,
        los dos le ponen su nombre y la cama termina con dos personas.
        """

        (reserva,) = self._reservar(self.derivacion.pk, [self.plaza.pk])()

        resultados, errores = en_paralelo(
            self._consumir(reserva.pk, self.ana.pk),
            self._consumir(reserva.pk, self.beto.pk),
            punto_a=PLAZA_BLOQUEADA,
        )

        self.assertEqual(len(resultados), 1, "la misma reserva alojó a dos personas")
        error = self._un_error(errores)
        self.assertIn("no está vigente", str(error))
        self.assertEqual(Estadia.objects.activas().filter(plaza=self.plaza).count(), 1)
        self.assertEqual(Estadia.objects.count(), 1)
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, ReservaPlaza.Estado.CONSUMIDA)
        # La reserva quedó a nombre de quien entró, no del que perdió.
        self.assertEqual(reserva.ciudadano_id, resultados[0].ciudadano_id)

    def test_consumir_y_liberar_la_misma_reserva_a_la_vez_la_resuelve_una_sola_vez(self):
        """La guardia confirma a una persona mientras otro operador libera la cama desde el mapa.

        Los dos caminos piden plaza y después reserva: `liberar_reserva` tiene que esperar la
        **plaza**, no un candado posterior, o el `UPDATE` de la reserva arma el `ERROR 1213`.
        """

        (reserva,) = self._reservar(self.derivacion.pk, [self.plaza.pk])()

        def liberar():
            return liberar_reserva(
                reserva=ReservaPlaza.objects.get(pk=reserva.pk),
                usuario=self._fresco(self.operador),
                motivo="La familia no llegó",
            )

        resultados, errores = en_paralelo(
            self._consumir(reserva.pk, self.beto.pk),
            liberar,
            punto_a=PLAZA_BLOQUEADA,
            punto_b=punto_critico(Plaza, "liberar_reserva", limite=1),
        )

        self.assertEqual(len(resultados), 1, "la reserva se consumió y se liberó")
        error = self._un_error(errores)
        self.assertIn("no está vigente", str(error))
        reserva.refresh_from_db()
        alojada = Estadia.objects.activas().filter(plaza=self.plaza).exists()
        if reserva.estado == ReservaPlaza.Estado.CONSUMIDA:
            self.assertTrue(alojada, "la reserva se consumió y nadie quedó alojado")
            self.assertEqual(reserva.ciudadano_id, self.beto.pk)
        else:
            self.assertEqual(reserva.estado, ReservaPlaza.Estado.LIBERADA)
            self.assertFalse(alojada, "la reserva se liberó y quedó alguien alojado igual")
            # El que perdió no dejó su nombre en una reserva que no consumió.
            self.assertEqual(reserva.ciudadano_id, self.ana.pk)

    def test_un_consumo_y_un_ingreso_normal_en_la_misma_plaza_dejan_un_solo_ocupante(self):
        """El asistente normal de Dispositivos apunta a la cama que la guardia está confirmando."""

        (reserva,) = self._reservar(self.derivacion.pk, [self.plaza.pk])()

        def ingreso_normal():
            return ingresar_persona(
                ciudadano=Ciudadano.objects.get(pk=self.beto.pk),
                dispositivo=Dispositivo.objects.get(pk=self.cis.pk),
                usuario=self._fresco(self.operador),
                plaza=Plaza.objects.get(pk=self.plaza.pk),
            )

        resultados, errores = en_paralelo(
            self._consumir(reserva.pk, self.ana.pk), ingreso_normal, punto_a=PLAZA_BLOQUEADA
        )

        self.assertEqual(len(resultados), 1, "la plaza quedó con dos personas")
        error = self._un_error(errores)
        self.assertIn("La plaza ya tiene", str(error))
        self.assertEqual(Estadia.objects.activas().filter(plaza=self.plaza).count(), 1)
        self.assertEqual(Estadia.objects.get().ciudadano_id, self.ana.pk)
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, ReservaPlaza.Estado.CONSUMIDA)

    def test_dos_aceptaciones_con_plazas_en_comun_reservan_para_una_sola_familia(self):
        """Dos derivaciones al mismo dispositivo aceptadas a la vez, con una cama en común.

        Las dos piden sus plazas ordenadas por pk: se forman en la que comparten y no se
        esperan en cruz. La que pierde no deja **ninguna** reserva (todo o nada).
        """

        otra = self._derivacion(self.beto)

        resultados, errores = en_paralelo(
            self._reservar(self.derivacion.pk, [self.plaza.pk, self.otra_plaza.pk]),
            self._reservar(otra.pk, [self.tercera_plaza.pk, self.otra_plaza.pk]),
            punto_a=PLAZAS_DE_LA_DERIVACION,
        )

        self.assertEqual(len(resultados), 1, "la cama en común quedó reservada para las dos familias")
        error = self._un_error(errores)
        self.assertIn("La plaza ya tiene una reserva vigente", str(error))
        vigentes = ReservaPlaza.objects.filter(estado=ReservaPlaza.Estado.VIGENTE)
        self.assertEqual(vigentes.count(), 2)
        self.assertEqual(vigentes.filter(plaza=self.otra_plaza).count(), 1)
        # Todo o nada: las dos reservas son de la misma derivación, la que ganó.
        self.assertEqual(vigentes.values("derivacion_id").distinct().count(), 1)
        self.assertEqual(set(vigentes.values_list("derivacion_id", flat=True)), {resultados[0][0].derivacion_id})
