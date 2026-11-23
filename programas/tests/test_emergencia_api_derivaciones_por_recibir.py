"""Cambio 576: ``GET /api/emergencia/dispositivos/{id}/derivaciones/``, las familias por aceptar de una sede.

La app de campo lista, al elegir la sede, lo mismo que la web en «Derivaciones por recibir»
(``llegadas_del_dispositivo``, con el mismo alcance por edificio del Cambio 523), sin datos personales
de más: apellido del responsable, cantidad de personas, caso, prioridad, vencimiento y edificio.

Los vencimientos son momentos fijos: ``vence_en`` se escribe a mano y el «ahora» de la vista se fija.
"""

import json
from datetime import UTC, datetime, timedelta
from unittest import mock

from django.db import connection
from django.test import tag
from django.test.utils import CaptureQueriesContext

from programas.models import Derivacion
from programas.selectors import emergencia_alojar as selectores
from programas.services import emergencia as mesa
from programas.services import emergencia_alojar as servicio
from programas.tests.base_emergencia_api import (
    CLAVES_DERIVACION_POR_RECIBIR,
    CLAVES_SIN_MODULO,
    NO_ENCONTRADO,
    SIN_ADMITIR,
    BaseApiLlegadas,
    _url,
)
from programas.tests.test_emergencia_alojar_alcance_edificio import _con_alcance_edificios, _partir_en_edificios
from programas.tests.test_emergencia_base import RECIBIR_KIT

AHORA = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)


class DerivacionesPorRecibirApiTests(BaseApiLlegadas):
    def _lista(self, usuario=None, dispositivo=None):
        with mock.patch("programas.api.views_emergencia_llegadas.timezone.now", return_value=AHORA):
            return self._como(usuario or self.guardia_centro).get(
                _url("dispositivo-derivaciones", (dispositivo or self.centro).pk)
            )

    def _vence(self, derivacion, momento):
        Derivacion.objects.filter(pk=derivacion.pk).update(vence_en=momento)

    def test_lista_la_derivacion_pendiente_con_claves_exactas(self):
        caso, derivacion = self._derivado()
        self._vence(derivacion, AHORA + timedelta(hours=5))

        respuesta = self._lista()

        self.assertEqual(respuesta.status_code, 200)
        filas = respuesta.json()
        self.assertEqual(len(filas), 1)
        fila = filas[0]
        self.assertEqual(sorted(fila), CLAVES_DERIVACION_POR_RECIBIR)
        self.assertEqual(fila["id"], derivacion.pk)
        self.assertEqual((fila["apellido"], fila["personas"], fila["caso_numero"]), ("Benítez", 7, caso.numero))
        self.assertEqual(fila["prioridad"], caso.prioridad)
        self.assertEqual(datetime.fromisoformat(fila["vence_en"]), AHORA + timedelta(hours=5))
        self.assertIs(fila["por_vencer"], False)
        self.assertIsNone(fila["edificio"])

    def test_sede_sin_derivaciones_da_lista_vacia(self):
        respuesta = self._lista(self.guardia_escuela, self.escuela)

        self.assertEqual((respuesta.status_code, respuesta.json()), (200, []))

    def test_por_vencer_es_el_umbral_de_la_web_y_el_orden_es_por_vencimiento(self):
        _, tarde = self._derivado(dni="30111222", apellido="Tarde")
        _, justo = self._derivado(dni="30222333", apellido="Justo")
        _, vencida = self._derivado(dni="30333444", apellido="Vencida")
        self._vence(tarde, AHORA + timedelta(hours=3))
        self._vence(justo, AHORA + timedelta(minutes=59))
        self._vence(vencida, AHORA - timedelta(minutes=10))

        filas = self._lista().json()

        self.assertEqual([f["apellido"] for f in filas], ["Vencida", "Justo", "Tarde"])
        self.assertEqual([f["por_vencer"] for f in filas], [True, True, False])

    def test_exactamente_sesenta_minutos_no_es_por_vencer(self):
        _, derivacion = self._derivado()
        self._vence(derivacion, AHORA + timedelta(minutes=60))

        self.assertIs(self._lista().json()[0]["por_vencer"], False)

    def test_solo_las_pendientes_de_casos_derivados(self):
        self._aceptado(dni="30222333", apellido="Aceptada")
        _, rechazada = self._derivado(dni="30333444", apellido="Rechazada")
        servicio.rechazar_derivacion(derivacion=rechazada, usuario=self.guardia_centro, motivo="SIN_PLAZAS")
        _, vencida = self._derivado(dni="30444555", apellido="Vencida")
        self._vence(vencida, datetime(2026, 11, 1, tzinfo=UTC))  # antes del reloj de BaseCasos
        mesa.vencer_derivacion(vencida)
        _, pendiente = self._derivado(dni="30555666", apellido="Pendiente")

        filas = self._lista().json()

        self.assertEqual([f["id"] for f in filas], [pendiente.pk])

    def test_misma_lista_que_la_web(self):
        self._derivado(dni="30111222", apellido="Uno")
        self._derivado(dni="30222333", apellido="Dos")
        self._aceptado(dni="30333444", apellido="Tres")

        web = selectores.llegadas_del_dispositivo(self.centro, self.guardia_centro)["pendientes"]

        self.assertEqual([f["id"] for f in self._lista().json()], [d.pk for d in web])
        self.assertEqual(len(web), 2)

    def test_no_trae_datos_personales_de_mas(self):
        caso, _ = self._derivado(dni="30111222", telefono="3624000000", observaciones="Vienen con un perro.")

        crudo = json.dumps(self._lista().json(), ensure_ascii=False)

        for dato in ("30111222", "3624000000", "perro", "Rosa", "dni", "telefono", "domicilio", "integrantes"):
            self.assertNotIn(dato, crudo)
        self.assertIn(caso.numero, crudo)

    def test_la_sede_ajena_da_404_como_el_resto_de_m2(self):
        self._derivado()

        respuesta = self._lista(self.guardia_escuela, self.centro)

        self.assertEqual((respuesta.status_code, respuesta.json()), (404, NO_ENCONTRADO))

    def test_sin_dispositivo_admitir_da_403(self):
        deposito = self._guardia("deposito", [RECIBIR_KIT], [self.centro])

        for usuario in (self.agente, deposito):
            with self.subTest(usuario=usuario.username):
                respuesta = self._lista(usuario)
                self.assertEqual((respuesta.status_code, respuesta.json()), (403, SIN_ADMITIR))

    def test_un_rol_de_becas_no_entra(self):
        respuesta = self._lista(self.territorial_becas)

        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(sorted(respuesta.json()), CLAVES_SIN_MODULO)

    def test_sin_token_da_401(self):
        respuesta = self._anonimo().get(_url("dispositivo-derivaciones", self.centro.pk))

        self.assertEqual(respuesta.status_code, 401)

    @tag("performance")
    def test_el_numero_de_consultas_no_crece_con_las_derivaciones(self):
        self._derivado(dni="30111222")
        cliente = self._como(self.guardia_centro)
        url = _url("dispositivo-derivaciones", self.centro.pk)
        cliente.get(url)  # calienta las caches de permisos

        with CaptureQueriesContext(connection) as con_una:
            self.assertEqual(len(cliente.get(url).json()), 1)
        for dni in ("30222333", "30333444", "30444555"):
            self._derivado(dni=dni)
        with CaptureQueriesContext(connection) as con_cuatro:
            self.assertEqual(len(cliente.get(url).json()), 4)

        self.assertEqual(len(con_cuatro), len(con_una))


class DerivacionesPorRecibirAlcanceEdificioTests(BaseApiLlegadas):
    """Cambio 523: con alcance Edificios, solo las derivaciones de sus edificios."""

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
        self.sin_edificio = self._derivar_a(None, "30333444", "Suelta")

    def _derivar_a(self, edificio, dni, apellido):
        caso = self._caso_tomado(menores_f=0, menores_m=0, dni=dni, apellido=apellido, nombre="X")
        return mesa.derivar_caso(caso, self.operador, self.centro, 1, True, edificio=edificio)

    def _ids(self, usuario):
        respuesta = self._como(usuario).get(_url("dispositivo-derivaciones", self.centro.pk))
        self.assertEqual(respuesta.status_code, 200)
        return [fila["id"] for fila in respuesta.json()]

    def test_la_guardia_de_norte_no_ve_la_derivacion_a_sur(self):
        self.assertEqual(self._ids(self.guardia_norte), [self.a_norte.pk])

    def test_con_alcance_edificios_la_derivacion_sin_edificio_no_aparece(self):
        self.assertNotIn(self.sin_edificio.pk, self._ids(self.guardia_norte))

    def test_la_guardia_de_toda_la_institucion_ve_todas_con_su_edificio(self):
        filas = self._como(self.guardia_centro).get(_url("dispositivo-derivaciones", self.centro.pk)).json()

        self.assertEqual(
            {fila["id"]: fila["edificio"] for fila in filas},
            {
                self.a_norte.pk: {"id": self.edif_a.pk, "nombre": "Edificio A"},
                self.a_sur.pk: {"id": self.edif_b.pk, "nombre": "Edificio B"},
                self.sin_edificio.pk: None,
            },
        )

    def test_la_fila_se_abre_con_su_id_para_aceptar(self):
        """El `id` de la fila es el de ``derivaciones/{id}/aceptar/``; la de Sur, para Norte, es 404."""
        fila = self._como(self.guardia_norte).get(_url("dispositivo-derivaciones", self.centro.pk)).json()[0]

        ajena = self._como(self.guardia_norte).post(_url("derivacion-aceptar", self.a_sur.pk), {}, format="json")
        propia = self._como(self.guardia_norte).post(_url("derivacion-aceptar", fila["id"]), {}, format="json")

        self.assertEqual(ajena.status_code, 404)
        self.assertEqual(propia.status_code, 200, propia.content)
