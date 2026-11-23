"""Cambio 577: ``GET /api/emergencia/derivaciones/{id}/``, la tarjeta de una derivación pendiente.

La app abre una fila de la lista (Cambio 576) sin conocer el DNI. La forma es la de ``derivacion`` de
``buscar?dni=`` (mismo serializer base), con el alcance de ``aceptar``/``rechazar``. Lo único que difiere es
``responsable.identidad_a_revisar``: la tarjeta de la web no lo muestra, así que viene ``null``.
"""

from datetime import UTC, datetime

from django.db import connection
from django.test import tag
from django.test.utils import CaptureQueriesContext

from programas.models import CasoEmergencia, Derivacion
from programas.services import emergencia as mesa
from programas.services import emergencia_alojar as servicio
from programas.tests.base_emergencia_api import (
    CLAVES_DERIVACION_LLEGADA,
    CLAVES_ESTADO_CAMBIO,
    CLAVES_SIN_MODULO,
    NO_ENCONTRADO,
    SIN_ADMITIR,
    BaseApiLlegadas,
    _url,
)
from programas.tests.test_emergencia_alojar_alcance_edificio import _con_alcance_edificios, _partir_en_edificios
from programas.tests.test_emergencia_base import RECIBIR_KIT


class DerivacionDetalleApiTests(BaseApiLlegadas):
    def _detalle(self, derivacion, usuario=None):
        return self._como(usuario or self.guardia_centro).get(_url("derivacion-detalle", derivacion.pk))

    def test_misma_forma_y_valores_que_la_derivacion_de_buscar(self):
        _, derivacion = self._derivado(embarazo=True, telefono="3624000000", observaciones="Vienen con un perro.")

        detalle = self._detalle(derivacion)
        buscada = (
            self._como(self.guardia_centro)
            .get(_url("dispositivo-buscar", self.centro.pk), {"dni": "30111222"})
            .json()["derivacion"]
        )

        self.assertEqual(detalle.status_code, 200)
        cuerpo = detalle.json()
        self.assertEqual(sorted(cuerpo), CLAVES_DERIVACION_LLEGADA)
        self.assertEqual(cuerpo["responsable"]["identidad_a_revisar"], None)
        buscada["responsable"]["identidad_a_revisar"] = None
        self.assertEqual(cuerpo, buscada)
        self.assertEqual(cuerpo["necesidades"], ["embarazo"])
        self.assertEqual(cuerpo["telefono"], "3624000000")

    def test_el_aviso_de_identidad_no_se_expone(self):
        caso, derivacion = self._derivado()
        caso.situacion = {
            **caso.situacion,
            caso.SITUACION_IDENTIDAD_A_REVISAR: {"nombre": "Pedro", "apellido": "Gómez"},
        }
        caso.save(update_fields=["situacion"])

        buscada = (
            self._como(self.guardia_centro)
            .get(_url("dispositivo-buscar", self.centro.pk), {"dni": "30111222"})
            .json()["derivacion"]
        )
        self.assertIsNotNone(buscada["responsable"]["identidad_a_revisar"])
        cuerpo = self._detalle(derivacion).json()

        self.assertIsNone(cuerpo["responsable"]["identidad_a_revisar"])
        self.assertNotIn("Gómez", str(cuerpo))

    def test_la_derivacion_ajena_da_404_como_aceptar(self):
        _, derivacion = self._derivado()

        respuesta = self._detalle(derivacion, self.guardia_escuela)

        self.assertEqual((respuesta.status_code, respuesta.json()), (404, NO_ENCONTRADO))
        self.assertEqual(self._detalle_inexistente().status_code, 404)

    def _detalle_inexistente(self):
        return self._como(self.guardia_centro).get(_url("derivacion-detalle", 999999))

    def test_sin_dispositivo_admitir_da_403(self):
        _, derivacion = self._derivado()
        deposito = self._guardia("deposito", [RECIBIR_KIT], [self.centro])

        for usuario in (self.agente, deposito):
            with self.subTest(usuario=usuario.username):
                respuesta = self._detalle(derivacion, usuario)
                self.assertEqual((respuesta.status_code, respuesta.json()), (403, SIN_ADMITIR))
        respuesta = self._detalle(derivacion, self.territorial_becas)
        self.assertEqual((respuesta.status_code, sorted(respuesta.json())), (403, CLAVES_SIN_MODULO))

    def test_sin_token_da_401(self):
        _, derivacion = self._derivado()

        self.assertEqual(self._anonimo().get(_url("derivacion-detalle", derivacion.pk)).status_code, 401)

    def _por_estado(self):
        """Una derivación en cada estado en que ``aceptar`` contesta 409: ``{nombre: derivacion}``."""
        _, en_curso = self._aceptado(dni="30222333", apellido="EnCurso", plazas=1)
        caso_alojado, alojado = self._aceptado(dni="30333444", apellido="Alojada", plazas=1)
        CasoEmergencia.objects.filter(pk=caso_alojado.pk).update(estado=CasoEmergencia.Estado.ALOJADO)
        _, rechazada = self._derivado(dni="30444555", apellido="Rechazada", plazas=1)
        servicio.rechazar_derivacion(derivacion=rechazada, usuario=self.guardia_centro, motivo="SIN_PLAZAS")
        _, vencida = self._derivado(dni="30555666", apellido="Vencida", plazas=1)
        Derivacion.objects.filter(pk=vencida.pk).update(vence_en=datetime(2026, 11, 1, tzinfo=UTC))
        mesa.vencer_derivacion(vencida)
        _, cancelada = self._derivado(dni="30666777", apellido="Cancelada", plazas=1)
        mesa.cancelar_derivacion(cancelada, self.operador, "La familia se fue con parientes.")
        return {
            "aceptada con ingreso en curso": en_curso,
            "aceptada y ya alojada": alojado,
            "rechazada": rechazada,
            "vencida": vencida,
            "cancelada": cancelada,
        }

    def test_una_derivacion_que_ya_no_esta_pendiente_da_el_mismo_409_que_aceptar(self):
        """El JSON entero (``detail`` incluido) es el del ``POST aceptar`` sobre la misma derivación."""
        for nombre, derivacion in self._por_estado().items():
            with self.subTest(estado=nombre):
                respuesta = self._detalle(derivacion)
                esperado = self._como(self.guardia_centro).post(
                    _url("derivacion-aceptar", derivacion.pk), {}, format="json"
                )
                self.assertEqual(esperado.status_code, 409, nombre)
                self.assertEqual((respuesta.status_code, respuesta.json()), (409, esperado.json()))
                self.assertEqual(sorted(respuesta.json()), CLAVES_ESTADO_CAMBIO)

    def test_la_vencida_por_el_cron_da_409(self):
        _, derivacion = self._derivado()
        Derivacion.objects.filter(pk=derivacion.pk).update(vence_en=Derivacion.objects.get(pk=derivacion.pk).creado)
        mesa.vencer_derivacion(derivacion)

        respuesta = self._detalle(derivacion)

        self.assertEqual(respuesta.status_code, 409)
        self.assertEqual(respuesta.json()["estado_actual"], "EN_GESTION")

    @tag("performance")
    def test_el_numero_de_consultas_es_fijo(self):
        _, una = self._derivado(dni="30111222")
        _, otra = self._derivado(dni="30222333", apellido="Otra", menores_f=5)
        cliente = self._como(self.guardia_centro)
        cliente.get(_url("derivacion-detalle", una.pk))  # calienta las caches de permisos

        with CaptureQueriesContext(connection) as primera:
            cliente.get(_url("derivacion-detalle", una.pk))
        with CaptureQueriesContext(connection) as segunda:
            cliente.get(_url("derivacion-detalle", otra.pk))

        self.assertEqual(len(primera), len(segunda))
        self.assertEqual(len(primera), 5, [q["sql"][:80] for q in primera.captured_queries])


class DerivacionDetalleAlcanceEdificioTests(BaseApiLlegadas):
    """Cambio 523: con alcance Edificios, solo se abre la derivación de sus edificios."""

    def setUp(self):
        super().setUp()
        self.edif_a, self.edif_b = _partir_en_edificios(self.centro)
        self.guardia_norte = _con_alcance_edificios(
            self._guardia("guardia_norte", ["dispositivo.ver", "dispositivo.admitir"], [self.centro]),
            self.centro,
            self.edif_a,
        )
        self.a_norte = self._derivar_a(self.edif_a, "30111222", "Norte")
        self.a_sur = self._derivar_a(self.edif_b, "30222333", "Sur")

    def _derivar_a(self, edificio, dni, apellido):
        caso = self._caso_tomado(menores_f=0, menores_m=0, dni=dni, apellido=apellido, nombre="X")
        return mesa.derivar_caso(caso, self.operador, self.centro, 1, True, edificio=edificio)

    def test_norte_abre_la_suya_y_no_la_de_sur(self):
        cliente = self._como(self.guardia_norte)

        propia = cliente.get(_url("derivacion-detalle", self.a_norte.pk))
        ajena = cliente.get(_url("derivacion-detalle", self.a_sur.pk))

        self.assertEqual(propia.status_code, 200)
        self.assertEqual(propia.json()["edificio"], {"id": self.edif_a.pk, "nombre": "Edificio A"})
        self.assertEqual((ajena.status_code, ajena.json()), (404, NO_ENCONTRADO))

    def test_la_guardia_de_toda_la_institucion_abre_las_dos(self):
        cliente = self._como(self.guardia_centro)

        for derivacion in (self.a_norte, self.a_sur):
            self.assertEqual(cliente.get(_url("derivacion-detalle", derivacion.pk)).status_code, 200)
