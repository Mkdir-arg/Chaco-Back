"""LEG-02 · Reinscribir en un programa con una inscripción previa no activa.

``InscripcionPrograma`` tiene ``unique_together = [ciudadano, programa]``: una
inscripción CERRADA, DADA DE BAJA o SUSPENDIDA ocupa la fila para siempre. Las tres
vías de alta hacían ``create`` igual —el form de derivación, ``DerivacionPrograma.aceptar``
y ``SolapasService.crear_inscripcion_directa``— y la base contestaba ``IntegrityError``
(500 en la vista). ``activar_inscripcion`` es la única puerta: reactiva la fila que ya
existe en vez de pelearse con el índice.
"""

import threading
from contextlib import contextmanager
from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import connection, connections
from django.db.models.query import QuerySet
from django.test import TestCase, TransactionTestCase, tag
from django.urls import reverse
from django.utils import timezone

from core.tests.candados import candados_tomados
from core.tests.test_motor_real import MotorRealMixin
from legajos.models import Ciudadano
from programas.models import DerivacionPrograma, InscripcionPrograma, Programa
from programas.services.inscripciones import activar_inscripcion, tomar_inscripcion
from programas.services.solapas import SolapasService


class ReactivarInscripcionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = User.objects.create_superuser("leg02", "leg02@x.com", "x")
        cls.programa = Programa.objects.create(
            codigo="LEG02",
            nombre="Programa LEG-02",
            tipo=Programa.TipoPrograma.DISPOSITIVOS,
            estado=Programa.Estado.ACTIVO,
        )

    def _ciudadano(self, dni):
        return Ciudadano.objects.create(dni=dni, nombre="N", apellido="A", fecha_nacimiento=date(1990, 1, 1))

    def test_aceptar_derivacion_con_inscripcion_cerrada_la_reactiva(self):
        ciudadano = self._ciudadano("31000001")
        previa = InscripcionPrograma.objects.create(
            ciudadano=ciudadano,
            programa=self.programa,
            estado=InscripcionPrograma.Estado.CERRADO,
            fecha_cierre=date(2026, 1, 1),
        )
        derivacion = DerivacionPrograma.objects.create(
            ciudadano=ciudadano, programa_destino=self.programa, motivo="reingreso"
        )

        inscripcion = derivacion.aceptar(usuario=self.usuario)

        self.assertEqual(inscripcion.pk, previa.pk)
        self.assertEqual(InscripcionPrograma.objects.filter(ciudadano=ciudadano, programa=self.programa).count(), 1)
        self.assertEqual(inscripcion.estado, InscripcionPrograma.Estado.ACTIVO)
        self.assertIsNone(inscripcion.fecha_cierre)
        self.assertEqual(inscripcion.fecha_inicio, timezone.localdate())
        self.assertEqual(inscripcion.via_ingreso, InscripcionPrograma.ViaIngreso.DERIVACION_EXTERNA)
        self.assertIn("reingreso", inscripcion.notas)
        derivacion.refresh_from_db()
        self.assertEqual(derivacion.estado, "ACEPTADA")
        self.assertEqual(derivacion.inscripcion_creada_id, previa.pk)

    def test_inscripcion_directa_con_baja_reactiva(self):
        ciudadano = self._ciudadano("31000002")
        previa = InscripcionPrograma.objects.create(
            ciudadano=ciudadano,
            programa=self.programa,
            estado=InscripcionPrograma.Estado.DADO_DE_BAJA,
        )
        self.client.force_login(self.usuario)

        respuesta = self.client.post(
            reverse("legajos:derivar_programa", args=[ciudadano.pk]),
            {
                "institucion_programa": self.programa.pk,
                "tipo_inicio": "inscripcion_directa",
                "motivo": "vuelve al programa",
                "urgencia": DerivacionPrograma.Urgencia.MEDIA,
            },
        )

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(InscripcionPrograma.objects.filter(ciudadano=ciudadano, programa=self.programa).count(), 1)
        previa.refresh_from_db()
        self.assertEqual(previa.estado, InscripcionPrograma.Estado.ACTIVO)
        self.assertEqual(previa.via_ingreso, InscripcionPrograma.ViaIngreso.DIRECTO)
        self.assertIn("vuelve al programa", previa.notas)

    def test_crear_inscripcion_directa_de_solapas_reactiva_la_suspendida(self):
        ciudadano = self._ciudadano("31000003")
        previa = InscripcionPrograma.objects.create(
            ciudadano=ciudadano,
            programa=self.programa,
            estado=InscripcionPrograma.Estado.SUSPENDIDO,
        )

        inscripcion = SolapasService.crear_inscripcion_directa(
            ciudadano, self.programa, self.usuario, notas="por ventanilla"
        )

        self.assertEqual(inscripcion.pk, previa.pk)
        self.assertEqual(inscripcion.estado, InscripcionPrograma.Estado.ACTIVO)
        self.assertEqual(inscripcion.notas, "por ventanilla")

    def test_activar_inscripcion_con_una_activa_no_duplica_ni_pisa_la_via(self):
        """Ya activa: la deja como está y no reescribe la vía de ingreso."""
        ciudadano = self._ciudadano("31000004")
        previa = InscripcionPrograma.objects.create(
            ciudadano=ciudadano,
            programa=self.programa,
            estado=InscripcionPrograma.Estado.ACTIVO,
            via_ingreso=InscripcionPrograma.ViaIngreso.ESPONTANEO,
            notas="original",
        )

        inscripcion = activar_inscripcion(
            ciudadano,
            self.programa,
            via=InscripcionPrograma.ViaIngreso.DIRECTO,
            usuario=self.usuario,
            notas="nueva",
        )

        self.assertEqual(inscripcion.pk, previa.pk)
        self.assertEqual(inscripcion.via_ingreso, InscripcionPrograma.ViaIngreso.ESPONTANEO)
        self.assertEqual(inscripcion.notas, "original")

    def test_activar_inscripcion_pendiente_pasa_a_activo(self):
        ciudadano = self._ciudadano("31000005")
        previa = InscripcionPrograma.objects.create(
            ciudadano=ciudadano,
            programa=self.programa,
            estado=InscripcionPrograma.Estado.PENDIENTE,
        )

        inscripcion = activar_inscripcion(
            ciudadano, self.programa, via=InscripcionPrograma.ViaIngreso.DIRECTO, usuario=self.usuario
        )

        self.assertEqual(inscripcion.pk, previa.pk)
        self.assertEqual(inscripcion.estado, InscripcionPrograma.Estado.ACTIVO)
        self.assertEqual(inscripcion.fecha_inicio, timezone.localdate())

    def test_activar_inscripcion_sin_fila_previa_la_crea(self):
        ciudadano = self._ciudadano("31000006")

        inscripcion = activar_inscripcion(
            ciudadano,
            self.programa,
            via=InscripcionPrograma.ViaIngreso.DERIVACION_INTERNA,
            usuario=self.usuario,
            notas="alta nueva",
        )

        self.assertEqual(inscripcion.estado, InscripcionPrograma.Estado.ACTIVO)
        self.assertEqual(inscripcion.via_ingreso, InscripcionPrograma.ViaIngreso.DERIVACION_INTERNA)
        self.assertEqual(inscripcion.responsable, self.usuario)
        self.assertEqual(inscripcion.notas, "alta nueva")


class ContratoDeCandadoTests(TestCase):
    """RED-67 · capa 1: el candado se afirma por su presencia, no por su efecto.

    En SQLite —donde corre la suite— ``select_for_update()`` es un no-op: nadie se
    pone rojo si alguien lo borra al optimizar, y en MariaDB se pierde la
    serialización que evita la segunda fila. La carrera de verdad está abajo, con
    ``@tag("mysql")``.
    """

    @classmethod
    def setUpTestData(cls):
        cls.usuario = User.objects.create_superuser("leg02-candado", "c@x.com", "x")
        cls.programa = Programa.objects.create(
            codigo="LEG02CAND",
            nombre="Programa candado",
            tipo=Programa.TipoPrograma.DISPOSITIVOS,
            estado=Programa.Estado.ACTIVO,
        )
        cls.ciudadano = Ciudadano.objects.create(
            dni="31900001", nombre="N", apellido="A", fecha_nacimiento=date(1990, 1, 1)
        )

    def test_activar_inscripcion_toma_el_candado_de_la_fila(self):
        InscripcionPrograma.objects.create(
            ciudadano=self.ciudadano, programa=self.programa, estado=InscripcionPrograma.Estado.CERRADO
        )

        with candados_tomados(InscripcionPrograma.objects) as candados:
            activar_inscripcion(
                self.ciudadano,
                self.programa,
                via=InscripcionPrograma.ViaIngreso.DIRECTO,
                usuario=self.usuario,
            )

        self.assertIn("inscripciones.py:tomar_inscripcion", candados)


@contextmanager
def _atomic_al_pedir_el_candado(manager):
    """Registra si había transacción abierta en cada ``select_for_update()``.

    Es la misma pregunta que se hace Django al ejecutar la consulta
    (``SQLCompiler.as_sql`` levanta ``TransactionManagementError`` si el
    ``select_for_update`` corre en autocommit), hecha en el único momento en que
    SQLite la deja ver: ahí ``has_select_for_update`` es ``False`` y la consulta
    se ejecuta sin chistar.
    """
    original = manager.select_for_update
    estados = []

    def registrar(*args, **kwargs):
        estados.append(connection.in_atomic_block)
        return original(*args, **kwargs)

    with patch.object(manager, "select_for_update", registrar):
        yield estados


@contextmanager
def _la_fila_recien_commiteada_no_se_ve(veces=2):
    """Simula la carrera que obliga a la rama de rescate de ``tomar_inscripcion``.

    El otro proceso ya insertó la fila —el índice único lo va a demostrar— pero la
    vista de esta transacción todavía no la ve. Hacen falta **dos** ``get`` ciegos:
    el del principio de ``get_or_create`` y el del rescate que el propio Django
    intenta antes de re-lanzar el ``IntegrityError``.
    """
    real_get = QuerySet.get
    restantes = [veces]

    def get_ciego(self, *args, **kwargs):
        if restantes[0] and self.model is InscripcionPrograma:
            restantes[0] -= 1
            raise InscripcionPrograma.DoesNotExist
        return real_get(self, *args, **kwargs)

    with patch.object(QuerySet, "get", get_ciego):
        yield


class TomarInscripcionFueraDeAtomicTests(TransactionTestCase):
    """La rama de rescate pedía el candado en autocommit → 500 en MySQL/MariaDB.

    ``TransactionTestCase`` y no ``TestCase``: este último envuelve cada test en su
    propia transacción, así que ``in_atomic_block`` daría ``True`` de arriba y el
    test pasaría con el bug adentro.
    """

    def setUp(self):
        self.usuario = User.objects.create_superuser("leg02-atomic", "a@x.com", "x")
        self.programa = Programa.objects.create(
            codigo="LEG02ATOM",
            nombre="Programa atomic",
            tipo=Programa.TipoPrograma.DISPOSITIVOS,
            estado=Programa.Estado.ACTIVO,
        )
        self.ciudadano = Ciudadano.objects.create(
            dni="31900002", nombre="N", apellido="A", fecha_nacimiento=date(1990, 1, 1)
        )
        self.previa = InscripcionPrograma.objects.create(
            ciudadano=self.ciudadano, programa=self.programa, estado=InscripcionPrograma.Estado.CERRADO
        )

    def test_la_rama_de_rescate_pide_el_candado_dentro_de_una_transaccion(self):
        self.assertFalse(connection.in_atomic_block, "el test tiene que arrancar en autocommit")

        with _la_fila_recien_commiteada_no_se_ve():
            with _atomic_al_pedir_el_candado(InscripcionPrograma.objects) as con_transaccion:
                fila, creada = tomar_inscripcion(self.ciudadano, self.programa, defaults={"responsable": self.usuario})

        self.assertFalse(creada)
        self.assertEqual(fila.pk, self.previa.pk)
        self.assertEqual(len(con_transaccion), 2, "se esperan dos candados: el de la rama feliz y el del rescate")
        self.assertTrue(
            all(con_transaccion),
            "un `select_for_update` en autocommit es `TransactionManagementError` en MySQL y MariaDB",
        )


@tag("mysql")
class TomarInscripcionMotorRealTests(MotorRealMixin, TransactionTestCase):
    """Lo mismo contra MariaDB/MySQL de verdad, donde el candado no es un no-op.

    Acá el ``select_for_update`` en autocommit **no** pasa desapercibido: el
    compilador levanta ``TransactionManagementError`` y la vista contesta 500.
    """

    def setUp(self):
        super().setUp()
        self.usuario = User.objects.create_superuser("leg02-motor", "m@x.com", "x")
        self.programa = Programa.objects.create(
            codigo="LEG02MOTOR",
            nombre="Programa motor real",
            tipo=Programa.TipoPrograma.DISPOSITIVOS,
            estado=Programa.Estado.ACTIVO,
        )
        self.ciudadano = Ciudadano.objects.create(
            dni="31900003", nombre="N", apellido="A", fecha_nacimiento=date(1990, 1, 1)
        )
        self.previa = InscripcionPrograma.objects.create(
            ciudadano=self.ciudadano, programa=self.programa, estado=InscripcionPrograma.Estado.CERRADO
        )

    def test_la_rama_de_rescate_no_explota_sin_atomic_externo(self):
        self.assertFalse(connection.in_atomic_block)

        with _la_fila_recien_commiteada_no_se_ve():
            fila, creada = tomar_inscripcion(self.ciudadano, self.programa, defaults={"responsable": self.usuario})

        self.assertFalse(creada)
        self.assertEqual(fila.pk, self.previa.pk)


@tag("mysql")
class CarreraDeReactivacionTests(MotorRealMixin, TransactionTestCase):
    """RED-67 · capa 2: dos reactivaciones simultáneas de la misma inscripción.

    El ``unique_together`` deja **una** fila por (ciudadano, programa). Dos requests
    que reactivan a la vez —una derivación aceptada y una inscripción directa, por
    ejemplo— tienen que terminar con esa fila ACTIVA y ninguna excepción: el que
    llega segundo espera el candado del primero y relee, en vez de intentar un
    ``INSERT`` que el índice rechaza.
    """

    def setUp(self):
        super().setUp()
        self.usuario = User.objects.create_superuser("leg02-carrera", "r@x.com", "x")
        self.programa = Programa.objects.create(
            codigo="LEG02RACE",
            nombre="Programa carrera",
            tipo=Programa.TipoPrograma.DISPOSITIVOS,
            estado=Programa.Estado.ACTIVO,
        )
        self.ciudadano = Ciudadano.objects.create(
            dni="31900004", nombre="N", apellido="A", fecha_nacimiento=date(1990, 1, 1)
        )

    def _en_paralelo(self, operacion, veces=2):
        barrera = threading.Barrier(veces, timeout=30)
        resultados, errores = [], []

        def correr(via):
            try:
                barrera.wait()
                resultados.append(operacion(via).pk)
            except Exception as exc:  # el hilo no propaga: se reporta al final
                errores.append(exc)
            finally:
                connections.close_all()

        vias = [InscripcionPrograma.ViaIngreso.DIRECTO, InscripcionPrograma.ViaIngreso.DERIVACION_INTERNA]
        hilos = [threading.Thread(target=correr, args=(via,)) for via in vias[:veces]]
        for hilo in hilos:
            hilo.start()
        for hilo in hilos:
            hilo.join(timeout=60)

        self.assertEqual([repr(e) for e in errores], [])
        return resultados

    def _activar(self, via):
        return activar_inscripcion(self.ciudadano, self.programa, via=via, usuario=self.usuario)

    def test_dos_reactivaciones_simultaneas_dejan_una_sola_fila_activa(self):
        previa = InscripcionPrograma.objects.create(
            ciudadano=self.ciudadano, programa=self.programa, estado=InscripcionPrograma.Estado.CERRADO
        )

        pks = self._en_paralelo(self._activar)

        self.assertEqual(set(pks), {previa.pk})
        inscripciones = InscripcionPrograma.objects.filter(ciudadano=self.ciudadano, programa=self.programa)
        self.assertEqual(inscripciones.count(), 1)
        self.assertEqual(inscripciones.get().estado, InscripcionPrograma.Estado.ACTIVO)
        self.assertIsNone(inscripciones.get().fecha_cierre)

    def test_dos_altas_simultaneas_sin_fila_previa_no_duplican(self):
        """Sin fila previa el ganador la crea y el perdedor la relee, no la duplica."""
        pks = self._en_paralelo(self._activar)

        self.assertEqual(len(set(pks)), 1)
        self.assertEqual(
            InscripcionPrograma.objects.filter(ciudadano=self.ciudadano, programa=self.programa).count(), 1
        )
