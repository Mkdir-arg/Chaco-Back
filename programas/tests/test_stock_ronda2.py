"""Stock, PR 2b, ronda 2 (auditorías del #1396 y del #1395): lo que las dos rondas pidieron y todavía no tenía test.

Mutaciones verificadas a mano (se rompe la regla, se mira el test rojo, se restaura):

* devolver ``@transaction.atomic`` a ``entregar_a_persona`` (la consulta al Registro vuelve a quedar adentro) pone rojo
  ``test_la_consulta_al_registro_corre_fuera_de_la_transaccion_de_la_entrega``;
* mover ``dar_de_alta`` antes de ``_exigir_saldo`` pone rojo ``test_sin_saldo_ni_se_intenta_dar_de_alta_a_la_persona``;
* sacar ``_exigir_tope`` de ``_asentar`` pone rojo los dos tests de tope (ingreso, traspaso y recepción de kit; en el
  ajuste no se alcanza: lo para el chequeo de lo contado);
* sacar el ``atomic`` (el ``with transaction.atomic()``) de ``entregar_a_persona`` pone rojo
  ``test_si_falla_al_asentar_tampoco_queda_el_legajo``, que vive en ``test_stock_entrega_persona.py`` (no acá);
* sacar el ``lleva_stock`` de ``consultar_persona`` pone rojo ``test_consultar_persona_rechaza_una_institucion_...``.
"""

from unittest import mock

from django.core.exceptions import ValidationError
from django.db import connection

from legajos.models import Ciudadano
from programas.models import OperacionStock
from programas.services import stock as servicio
from programas.tests.base_stock import BaseEntrega


class EntregaRondaDosTests(BaseEntrega):
    def setUp(self):
        super().setUp()
        self._sembrar(self.colchon, 5)

    def test_la_consulta_al_registro_corre_fuera_de_la_transaccion_de_la_entrega(self):
        """Dentro del ``atomic`` de la entrega hay un savepoint más que en el nivel del test: afuera, ninguno."""

        nivel_del_test = len(connection.savepoint_ids)
        savepoints = []

        def consulta(*_args, **_kwargs):
            savepoints.append(len(connection.savepoint_ids))
            return self.RENAPER_ENCUENTRA

        with mock.patch(self.CONSULTA_RENAPER, side_effect=consulta):
            self._entregar(dni="27555666", sexo="F")

        self.assertEqual(savepoints, [nivel_del_test])
        self.assertTrue(Ciudadano.objects.filter(dni="27555666").exists())

    def test_sin_saldo_ni_se_intenta_dar_de_alta_a_la_persona(self):
        """El alta va después de verificar el saldo: no depende de que el ``atomic`` la deshaga."""

        with (
            mock.patch(self.CONSULTA_RENAPER, return_value=self.RENAPER_ENCUENTRA),
            mock.patch.object(servicio, "dar_de_alta") as alta,
            self.assertRaises(servicio.SaldoInsuficiente),
        ):
            self._entregar(dni="27555666", sexo="F", lineas={self.colchon.pk: 11})

        alta.assert_not_called()

    def test_consultar_persona_rechaza_una_institucion_que_no_lleva_stock(self):
        self.disp.tipo.maneja_stock = False
        self.disp.tipo.save()

        with mock.patch(self.CONSULTA_RENAPER) as consulta, self.assertRaises(servicio.StockNoHabilitado):
            servicio.consultar_persona(self.guardia, self.disp, self.edificio, "27555666", "F")

        consulta.assert_not_called()

    def test_un_legajo_fallecido_no_recibe_nada(self):
        """DECISIÓN TOMADA POR DEFECTO: se rechaza igual que si el Registro lo da por fallecido."""

        self.persona.estado_renaper = Ciudadano.EstadoRenaper.FALLECIDO
        self.persona.save()

        with self.assertRaises(ValidationError) as contexto:
            self._entregar()
        with self.assertRaises(ValidationError):
            servicio.consultar_persona(self.guardia, self.disp, self.edificio, "30111222")

        self.assertIn("fallecida", contexto.exception.message_dict["dni"][0])
        self.assertEqual(self._cantidad(self.colchon), 5)
        self.assertFalse(OperacionStock.objects.exclude(tipo=OperacionStock.Tipo.INGRESO_MANUAL).exists())

    def test_el_edificio_y_la_institucion_como_texto_se_resuelven_o_se_rechazan_sin_romper(self):
        operacion = self._entregar(dispositivo=str(self.disp.pk), edificio=str(self.edificio.pk))
        self.assertEqual((operacion.dispositivo, operacion.edificio), (self.disp, self.edificio))

        for dispositivo in ("abc", None, 999999):
            with self.subTest(dispositivo), self.assertRaises(ValidationError):
                self._entregar(dispositivo=dispositivo)
        with self.assertRaises(ValidationError) as contexto:
            self._entregar(edificio="abc")
        self.assertIn("edificio", contexto.exception.message_dict)


class TopeYEntradasNoNumericasTests(BaseEntrega):
    """#1395 MINOR 1 y 4: la suma acumulada no pasa del máximo y un id no numérico no da 500."""

    def _ingresar(self, cantidad):
        return servicio.ingresar_manual(
            self.carga, self.disp, self.edificio, {self.colchon.pk: cantidad}, origen=OperacionStock.Origen.DONACION
        )

    def test_la_suma_acumulada_que_no_entra_en_el_saldo_es_un_error_de_validacion(self):
        self._ingresar(servicio.CANTIDAD_MAXIMA - 1)

        with self.assertRaises(ValidationError) as contexto:
            self._ingresar(2)

        self.assertEqual(contexto.exception.message_dict, {"lineas": [servicio.SALDO_EXCEDIDO]})
        self.assertEqual(self._cantidad(self.colchon), servicio.CANTIDAD_MAXIMA - 1)
        self.assertEqual(OperacionStock.objects.count(), 1)
        self._ingresar(1)  # justo el tope sí entra
        self.assertEqual(self._cantidad(self.colchon), servicio.CANTIDAD_MAXIMA)
        self.assertLibroCoherente()

    def test_el_traspaso_tampoco_hace_pasar_al_destino_del_maximo(self):
        self._sembrar(self.colchon, 10)
        self._sembrar(self.colchon, servicio.CANTIDAD_MAXIMA - 1, edificio=self.otro_edificio)

        with self.assertRaises(ValidationError) as contexto:
            servicio.traspasar(
                self.carga, self.disp, self.edificio, self.disp, self.otro_edificio, {self.colchon.pk: 2}
            )

        self.assertEqual(contexto.exception.message_dict, {"lineas": [servicio.SALDO_EXCEDIDO]})
        self.assertEqual(self._cantidad(self.colchon), 10)

    def test_un_ajuste_nunca_pasa_del_maximo(self):
        self._sembrar(self.colchon, 1)

        # En un ajuste el saldo queda en lo contado, así que el tope lo para el chequeo de lo contado y no ``_exigir_tope``.
        with self.assertRaises(ValidationError) as contexto:
            servicio.ajustar(
                self.carga, self.disp, self.edificio, self.colchon, servicio.CANTIDAD_MAXIMA + 1, 1, "OTRO", "x"
            )

        self.assertEqual(contexto.exception.message_dict, {"cantidad_contada": [servicio.CONTADO_INVALIDO]})
        self.assertEqual(self._cantidad(self.colchon), 1)

    def test_un_insumo_o_una_institucion_no_numericos_son_un_error_de_validacion(self):
        with self.assertRaises(ValidationError) as contexto:
            servicio.ajustar(self.carga, self.disp, self.edificio, "abc", 3, 0, "OTRO", "x")
        self.assertIn("item", contexto.exception.message_dict)
        for institucion in ("abc", None):
            with self.subTest(institucion), self.assertRaises(ValidationError) as contexto:
                servicio.ingresar_manual(
                    self.carga, institucion, self.edificio, {self.colchon.pk: 1}, origen=OperacionStock.Origen.DONACION
                )
            self.assertIn("dispositivo", contexto.exception.message_dict)


class TraspasoRondaDosTests(BaseEntrega):
    def setUp(self):
        super().setUp()
        self._sembrar(self.colchon, 10)

    def test_el_edificio_de_origen_como_texto_no_rompe_el_orden_de_los_candados(self):
        """Antes ``"5"`` daba ``TypeError`` en el ``sorted`` de ``_preparar``."""

        operacion = servicio.traspasar(
            self.carga, self.disp, str(self.edificio.pk), self.disp, str(self.otro_edificio.pk), {self.colchon.pk: 3}
        )

        self.assertEqual((operacion.edificio, operacion.destino_edificio), (self.edificio, self.otro_edificio))
        self.assertEqual(self._cantidad(self.colchon, edificio=self.otro_edificio), 3)

    def test_el_origen_sin_edificio_valido_se_rechaza(self):
        with self.assertRaises(ValidationError):
            servicio.traspasar(self.carga, self.disp, "abc", self.disp, self.otro_edificio, {self.colchon.pk: 1})

    def test_el_destino_inactivo_tiene_su_propio_mensaje(self):
        """DECISIÓN TOMADA POR DEFECTO: un texto que habla del destino, no del origen."""

        self.otro_edificio.activo = False
        self.otro_edificio.save()

        with self.assertRaises(servicio.StockNoHabilitado) as contexto:
            servicio.traspasar(
                self.carga, self.disp, self.edificio, self.disp, self.otro_edificio, {self.colchon.pk: 1}
            )

        self.assertEqual(contexto.exception.messages, ["La institución o el edificio de destino está inactivo."])
