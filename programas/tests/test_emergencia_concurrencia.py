"""Las carreras de la mesa de Emergencia, corridas de verdad con dos conexiones.

Lo que sostiene las reglas de esta etapa no es un ``UniqueConstraint(condition=...)``
—MySQL y MariaDB lo ignoran— sino ``select_for_update()`` sobre **la fila del caso**, más
un UNIQUE común sobre una columna anulable donde la fila no alcanza
(``Derivacion.clave_vigente``, ``CasoEmergencia.uuid_cliente``) y la fila del numerador
para repartir los números.

En SQLite —el motor de la suite rápida— eso **no se puede probar**: ``select_for_update()``
es un no-op y los dos hilos entran juntos. Por eso este módulo lleva ``@tag("mysql")`` y
corre en el job «Motor real» contra ``mariadb:10.11``, ``mariadb:11`` y ``mysql:8.0``; sin
motor real se saltea (``MotorRealMixin``), igual que
``programas.tests.test_dispositivos_concurrencia``, de donde sale el andamio
(``en_paralelo`` y ``punto_critico``): A se detiene **con su candado tomado**, y se exige
que B esté en ``LOCK WAIT`` en InnoDB antes de soltarlo.

Qué afirma cada caso:

1. **Exactamente uno gana** (o, en los reenvíos idempotentes y en el numerador, los dos
   terminan bien y el estado es el de una sola escritura por cada uno).
2. **El otro recibe el error de dominio** —``CasoTomadoPorOtro`` o ``EstadoCambio``—,
   nunca un ``IntegrityError`` crudo ni un ``OperationalError`` de deadlock.
3. **El estado final es consistente**: un dueño, una derivación vigente, números sin
   repetir ni saltear.

La capa de al lado, que corre en todos los PRs sobre SQLite, es
``test_emergencia_casos``: el test de mutación de RN-2.1 con dos objetos viejos del mismo
caso y ``OrdenDeLosCandadosEmergenciaTests``, que fija el orden caso → derivación.
"""

import uuid
from datetime import datetime
from unittest import mock

from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.test import TransactionTestCase, tag
from django.utils import timezone

from core import rbac
from core.tests.test_motor_real import MotorRealMixin
from legajos.models import Ciudadano
from programas.management.commands.seed_emergencia import asegurar_programa_emergencia
from programas.models import (
    CasoEmergencia,
    Derivacion,
    Dispositivo,
    GrupoFamiliar,
    NumeradorEmergencia,
    Plaza,
    Sector,
    TipoDispositivo,
    TrazaCaso,
)
from programas.services import emergencia as servicio
from programas.services.emergencia import CasoTomadoPorOtro, EstadoCambio
from programas.tests.test_dispositivos_concurrencia import _permiso, en_paralelo, punto_critico
from users.models import RolMeta

#: Un jueves a las 10 de la mañana de Resistencia.
_RELOJ = timezone.make_aware(datetime(2026, 11, 12, 10, 0, 0))

#: El primer candado de toda acción sobre un caso.
CASO_BLOQUEADO = punto_critico(CasoEmergencia, "_bloquear_caso")
#: El candado del contador de la serie.
NUMERADOR_BLOQUEADO = punto_critico(NumeradorEmergencia, "_bloquear_numerador")


class _BaseCarreraEmergencia(MotorRealMixin, TransactionTestCase):
    """La mesa mínima: un agente, dos operadores, dos dispositivos con camas y un caso nuevo.

    ``TransactionTestCase`` y no ``TestCase``: lo que se prueba son transacciones que
    commitean; con el ``atomic`` envolvente de ``TestCase`` los hilos no verían nada del otro.
    """

    def setUp(self):
        super().setUp()
        reloj = mock.patch("django.utils.timezone.now", return_value=_RELOJ)
        reloj.start()
        self.addCleanup(reloj.stop)
        cache.clear()
        self.addCleanup(cache.clear)
        self.programa, _creado, _sla = asegurar_programa_emergencia()
        self.agente = self._usuario("agente_conc", ["emergencia.relevar"])
        self.ana = self._usuario("ana_conc", ["emergencia.operar"])
        self.juan = self._usuario("juan_conc", ["emergencia.operar"])
        self.tipo = TipoDispositivo.objects.create(
            codigo="EVACUADOS-C", nombre="Centro de evacuados", tipos_plaza_admitidos=["CAMA"]
        )
        self.club = self._dispositivo("EVA-C1", "Club concurrencia")
        self.escuela = self._dispositivo("EVA-C2", "Escuela concurrencia")
        self._dnis = iter(range(36_000_001, 36_000_999))
        # El primer caso deja además creada y commiteada la fila del numerador del año.
        self.caso = self._crear_caso()

    def _usuario(self, nombre, capacidades):
        rol = Group.objects.create(name=f"Rol {nombre}")
        RolMeta.objects.create(grupo=rol, categoria=rbac.CATEGORIA_PROGRAMA, programa=self.programa, activo=True)
        rol.permissions.add(*[_permiso(codigo) for codigo in capacidades])
        usuario = User.objects.create_user(username=nombre)
        usuario.groups.add(rol)
        return User.objects.get(pk=usuario.pk)

    def _dispositivo(self, codigo, nombre, camas=6):
        dispositivo = Dispositivo.objects.create(
            tipo=self.tipo, codigo=codigo, nombre=nombre, estado=Dispositivo.Estado.ACTIVO
        )
        sector = Sector.objects.create(dispositivo=dispositivo, nombre="General", capacidad=camas)
        Plaza.objects.bulk_create([Plaza(sector=sector, codigo=f"{codigo}-{n}") for n in range(1, camas + 1)])
        return dispositivo

    def _datos(self):
        return {
            "traslado": GrupoFamiliar.Traslado.BOMBEROS,
            "dni": str(next(self._dnis)),
            "nombre": "Rosa",
            "apellido": "Benítez",
            "adultos_f": 1,
            "adultos_m": 1,
            "direccion": "Av. Sarmiento 1200",
        }

    def _crear_caso(self, datos=None, uuid_cliente=None):
        return servicio.crear_caso(
            usuario=self._fresco(self.agente),
            origen=CasoEmergencia.Origen.TERRITORIO,
            datos_formulario1=datos or self._datos(),
            uuid_cliente=uuid_cliente,
        )

    def _fresco(self, usuario):
        """``rbac`` memoiza las capacidades en el objeto, y cada hilo necesita el suyo."""

        return User.objects.get(pk=usuario.pk)

    def _caso_en_pantalla(self):
        """El caso como lo tiene cada pestaña: leído antes de que el otro haga nada."""

        return CasoEmergencia.objects.get(pk=self.caso.pk)

    def _un_error(self, errores, tipo):
        """Exactamente un perdedor, y con el error de dominio: ni 500 ni deadlock."""

        self.assertEqual(
            len(errores),
            1,
            f"se esperaba un solo perdedor y hubo {len(errores)}: {[repr(e) for e in errores]}",
        )
        self.assertIsInstance(errores[0], tipo, f"el perdedor no recibió el error de dominio: {errores[0]!r}")
        return errores[0]


@tag("mysql")
class CarreraDeTomarTests(_BaseCarreraEmergencia):
    """RN-2.1 / RU §6 n.° 4: dos operadores, un caso."""

    def _tomar(self, usuario):
        def operacion():
            return servicio.tomar_caso(self._caso_en_pantalla(), self._fresco(usuario))

        return operacion

    def test_dos_operadores_toman_el_mismo_caso_y_gana_uno(self):
        resultados, errores = en_paralelo(self._tomar(self.ana), self._tomar(self.juan), punto_a=CASO_BLOQUEADO)

        self.assertEqual(len(resultados), 1)
        error = self._un_error(errores, CasoTomadoPorOtro)
        caso = CasoEmergencia.objects.get(pk=self.caso.pk)
        self.assertEqual(caso.estado, CasoEmergencia.Estado.EN_GESTION)
        self.assertEqual(caso.tomado_por_id, resultados[0].tomado_por_id)
        self.assertEqual(error.tomado_por.pk, caso.tomado_por_id)
        self.assertEqual(TrazaCaso.objects.filter(caso=caso, accion=TrazaCaso.Accion.TOMADO).count(), 1)


@tag("mysql")
class CarreraDeDerivarTests(_BaseCarreraEmergencia):
    """RN-2.6: a lo sumo una derivación vigente, con dos pestañas derivando a la vez."""

    def setUp(self):
        super().setUp()
        servicio.tomar_caso(self.caso, self._fresco(self.ana))

    def _derivar(self, dispositivo):
        def operacion():
            return servicio.derivar_caso(
                self._caso_en_pantalla(), self._fresco(self.ana), Dispositivo.objects.get(pk=dispositivo.pk), 2
            )

        return operacion

    def _cancelar(self, derivacion):
        def operacion():
            return servicio.cancelar_derivacion(
                Derivacion.objects.get(pk=derivacion.pk), self._fresco(self.ana), "Error de carga"
            )

        return operacion

    def test_dos_derivaciones_a_la_vez_dejan_una_sola_vigente(self):
        resultados, errores = en_paralelo(self._derivar(self.club), self._derivar(self.escuela), punto_a=CASO_BLOQUEADO)

        self.assertEqual(len(resultados), 1)
        error = self._un_error(errores, EstadoCambio)
        self.assertEqual(error.estado_actual, CasoEmergencia.Estado.DERIVADO)
        self.assertEqual(Derivacion.objects.filter(caso=self.caso).count(), 1)
        self.assertEqual(Derivacion.objects.filter(clave_vigente=self.caso.pk).count(), 1)
        self.assertEqual(CasoEmergencia.objects.get(pk=self.caso.pk).estado, CasoEmergencia.Estado.DERIVADO)
        self.assertEqual(TrazaCaso.objects.filter(caso=self.caso, accion=TrazaCaso.Accion.DERIVADO).count(), 1)

    def test_dos_cancelaciones_de_la_misma_derivacion_la_cancelan_una_sola_vez(self):
        """Los dos caminos piden caso y después derivación: esperan, no se matan."""
        derivacion = servicio.derivar_caso(self.caso, self._fresco(self.ana), self.club, 2)

        resultados, errores = en_paralelo(
            self._cancelar(derivacion), self._cancelar(derivacion), punto_a=CASO_BLOQUEADO
        )

        self.assertEqual(len(resultados), 1)
        self._un_error(errores, EstadoCambio)
        derivacion.refresh_from_db()
        self.assertEqual(derivacion.estado, Derivacion.Estado.CANCELADA)
        self.assertIsNone(derivacion.clave_vigente)
        self.assertEqual(CasoEmergencia.objects.get(pk=self.caso.pk).estado, CasoEmergencia.Estado.EN_GESTION)
        self.assertEqual(
            TrazaCaso.objects.filter(caso=self.caso, accion=TrazaCaso.Accion.DERIVACION_CANCELADA).count(), 1
        )


@tag("mysql")
class CarreraDelNumeradorTests(_BaseCarreraEmergencia):
    """El numerador reparte un número a cada uno, sin repetir ni saltear."""

    def _crear(self, datos, uuid_cliente=None):
        def operacion():
            return servicio.crear_caso(
                usuario=self._fresco(self.agente),
                origen=CasoEmergencia.Origen.TERRITORIO,
                datos_formulario1=datos,
                uuid_cliente=uuid_cliente,
            )

        return operacion

    def test_dos_casos_a_la_vez_reciben_numeros_consecutivos(self):
        resultados, errores = en_paralelo(
            self._crear(self._datos()), self._crear(self._datos()), punto_a=NUMERADOR_BLOQUEADO
        )

        self.assertEqual(errores, [])
        self.assertEqual(sorted(caso.numero for caso in resultados), ["2026-000002", "2026-000003"])
        self.assertEqual(CasoEmergencia.objects.count(), 3)
        self.assertEqual(NumeradorEmergencia.objects.get(serie="C", anio=2026).ultimo, 3)

    def test_el_mismo_envio_dos_veces_a_la_vez_crea_un_caso(self):
        """RU-16 / RN-1.8 con las dos copias en vuelo: el UNIQUE de ``uuid_cliente`` decide.

        El segundo no ve al primero en la búsqueda inicial (todavía no commiteó), espera en
        el numerador y choca en el ``INSERT``: devuelve el caso que ganó, y su número y su
        grupo se deshacen con la transacción anidada.
        """
        envio = uuid.uuid4()
        datos = self._datos()
        # El responsable ya está en el legajo: si no, las dos copias competirían antes, en el
        # alta de la persona, y lo que se mediría sería el UNIQUE del DNI y no el del envío.
        Ciudadano.objects.create(dni=datos["dni"], nombre=datos["nombre"], apellido=datos["apellido"])

        resultados, errores = en_paralelo(
            self._crear(datos, envio), self._crear(datos, envio), punto_a=NUMERADOR_BLOQUEADO
        )

        self.assertEqual(errores, [])
        self.assertEqual(len({caso.pk for caso in resultados}), 1)
        self.assertEqual(sorted(caso.ya_existia for caso in resultados), [False, True])
        self.assertEqual(CasoEmergencia.objects.count(), 2)
        self.assertEqual(GrupoFamiliar.objects.count(), 2)
        self.assertEqual(NumeradorEmergencia.objects.get(serie="C", anio=2026).ultimo, 2)
