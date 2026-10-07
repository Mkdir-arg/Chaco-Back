"""Comportamiento de ``validar_casos_siis`` con ``--aplicar`` (RED-32, Ola 1).

El PR R-06 dejó la **caracterización**: el ensayo, los flags de selección y los
dos frenos de arranque, todo sin llamar nunca al servicio. Lo que faltaba es lo
que pasa cuando el comando de verdad corre, que es lo que la ficha nombra como
frágil: si alguien toca el ``order_by`` del ``Subquery`` o el
``exclude(estado=RECHAZADO)`` de ``_casos``, el comando revalida miles de casos
ya validados o saltea los que faltan; y si se rompe el freno por errores
seguidos, una caída de SIIS deja miles de filas ``ERROR`` que el revisor abre y
lee como «SIIS dijo que es incompatible», porque la pantalla toma como vigente
la **última** validación del caso.

Nada sale a la red: se mockea ``validar_formulario_en_siis`` y las aserciones
son sobre a quién se llamó y en qué orden.

**Desvío de la ficha, a favor del código:** el patch va sobre
``programas.management.commands.validar_casos_siis.validar_formulario_en_siis``
y no sobre ``programas.services.validacion_siis...``. El comando importa el
nombre en su encabezado, así que parchear el módulo del servicio no cambia la
referencia que el comando ya tiene: con ese target los tests pasarían saliendo a
la red de verdad, que es exactamente lo que no se quiere.
"""

from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from programas.models import Formulario, ValidacionSIS
from programas.tests.test_siis_envio import _BaseEnvioTest

OBJETIVO = "programas.management.commands.validar_casos_siis.validar_formulario_en_siis"

CREDENCIALES = dict(SIIS_API_CLIENT_ID="client", SIIS_API_CLIENT_SECRET="secret")


@override_settings(**CREDENCIALES)
class ValidarCasosSiisTests(_BaseEnvioTest):
    """Lo que el comando consulta, lo que saltea y cuándo se detiene."""

    def setUp(self):
        super().setUp()
        self.formulario.estado = Formulario.Estado.ENVIADO
        self.formulario.save(update_fields=["estado"])

    def otro_caso(self, estado=Formulario.Estado.ENVIADO):
        return Formulario.objects.create(relevamiento=self.relevamiento, ciudadano=self.ciudadano, estado=estado)

    def correr(self, *args, veredictos=None):
        """Corre con ``--aplicar`` y el servicio mockeado.

        ``veredictos`` es la lista de estados que va devolviendo el servicio, uno
        por llamada; el último se repite si se acaban. Una excepción en la lista
        se levanta en vez de devolverse. Devuelve
        ``(salida, mock, codigo_de_salida)``.
        """
        veredictos = list(veredictos or [ValidacionSIS.Estado.OK])
        salida = StringIO()
        codigo = 0

        def responder(caso, solicitante=None):
            estado = veredictos[min(responder.llamadas, len(veredictos) - 1)]
            responder.llamadas += 1
            if isinstance(estado, Exception):
                raise estado
            return ValidacionSIS.objects.create(formulario=caso, estado=estado, solicitado_por=solicitante)

        responder.llamadas = 0
        with patch(OBJETIVO, side_effect=responder) as validar:
            try:
                call_command("validar_casos_siis", "--aplicar", *args, stdout=salida, stderr=salida)
            except SystemExit as exc:
                codigo = exc.code
        return salida.getvalue(), validar, codigo

    def casos_consultados(self, validar):
        return [llamada.args[0].pk for llamada in validar.call_args_list]

    # ── Selección ───────────────────────────────────────────────────────────

    def test_toma_solo_los_casos_sin_validacion(self):
        sin_validar = self.otro_caso()
        ValidacionSIS.objects.create(formulario=self.formulario, estado=ValidacionSIS.Estado.OK)

        _, validar, _ = self.correr()

        self.assertEqual(self.casos_consultados(validar), [sin_validar.pk])

    def test_reintentar_errores_suma_los_que_quedaron_en_error(self):
        """«En ERROR» es el **último** intento, no «tuvo alguno»: un caso que
        erró y después salió bien está resuelto y no se vuelve a consultar."""
        con_error = self.otro_caso()
        ValidacionSIS.objects.create(formulario=con_error, estado=ValidacionSIS.Estado.ERROR)
        resuelto = self.otro_caso()
        ValidacionSIS.objects.create(formulario=resuelto, estado=ValidacionSIS.Estado.ERROR)
        ValidacionSIS.objects.create(formulario=resuelto, estado=ValidacionSIS.Estado.OK)

        _, validar, _ = self.correr("--reintentar-errores")

        self.assertEqual(sorted(self.casos_consultados(validar)), sorted([self.formulario.pk, con_error.pk]))

    def test_un_rechazado_por_el_revisor_se_saltea_salvo_incluir_rechazados(self):
        rechazado = self.otro_caso(Formulario.Estado.RECHAZADO)

        _, validar, _ = self.correr()
        self.assertNotIn(rechazado.pk, self.casos_consultados(validar))

        _, validar, _ = self.correr("--incluir-rechazados", "--todos")
        self.assertIn(rechazado.pk, self.casos_consultados(validar))

    def test_el_limite_corta_la_lista_por_el_orden_de_pk(self):
        segundo = self.otro_caso()
        self.otro_caso()

        _, validar, _ = self.correr("--limite", "2")

        self.assertEqual(self.casos_consultados(validar), [self.formulario.pk, segundo.pk])

    def test_un_caso_sin_dni_se_saltea_y_no_cuenta_como_error(self):
        """El servicio levanta ``ValueError`` cuando no hay consulta posible. Un
        salteo no es una falla de SIIS: no puede sumar al freno ni, peor, ponerle
        el contador en cero a una racha de errores de verdad."""
        salida, _, codigo = self.correr(veredictos=[ValueError("sin DNI")])

        self.assertEqual(codigo, 0)
        self.assertIn("salteados sin programa o sin DNI", salida)
        self.assertEqual(ValidacionSIS.objects.count(), 0)

    def test_el_usuario_queda_como_solicitante_de_la_validacion(self):
        User.objects.create_user("operador_siis", password="x")

        self.correr("--usuario", "operador_siis")

        self.assertEqual(ValidacionSIS.objects.get().solicitado_por.username, "operador_siis")

    # ── Freno ───────────────────────────────────────────────────────────────

    def test_diez_errores_tecnicos_seguidos_detienen_la_corrida(self):
        for _ in range(20):
            self.otro_caso()

        salida, validar, codigo = self.correr("--lote", "50", veredictos=[ValidacionSIS.Estado.ERROR])

        self.assertEqual(codigo, 1)
        self.assertEqual(validar.call_count, 10)
        self.assertIn("DETENIDO", salida)
        self.assertIn("--reintentar-errores", salida)

    def test_un_ok_entre_errores_reinicia_el_contador(self):
        for _ in range(19):
            self.otro_caso()
        veredictos = (
            [ValidacionSIS.Estado.ERROR] * 9
            + [ValidacionSIS.Estado.OK]
            + [ValidacionSIS.Estado.ERROR] * 9
            + [ValidacionSIS.Estado.OK]
        )

        salida, validar, codigo = self.correr("--lote", "50", veredictos=veredictos)

        self.assertEqual(codigo, 0)
        self.assertEqual(validar.call_count, 20)
        self.assertNotIn("DETENIDO", salida)

    def test_un_rechazo_de_siis_no_es_una_falla_tecnica(self):
        """Un RECHAZADO es una respuesta: el servicio está sano y el caso tiene
        un problema. Contarlo en el freno apagaría la corrida justo cuando
        funciona."""
        for _ in range(20):
            self.otro_caso()

        salida, validar, codigo = self.correr("--lote", "50", veredictos=[ValidacionSIS.Estado.RECHAZADO])

        self.assertEqual(codigo, 0)
        self.assertEqual(validar.call_count, 21)
        self.assertIn("incompatibles (RECHAZADO)", salida)

    def test_el_tope_de_errores_se_puede_bajar(self):
        for _ in range(5):
            self.otro_caso()

        _, validar, codigo = self.correr("--max-errores", "2", veredictos=[ValidacionSIS.Estado.ERROR])

        self.assertEqual(codigo, 1)
        self.assertEqual(validar.call_count, 2)

    # ── Frenos de arranque ──────────────────────────────────────────────────

    @override_settings(SIIS_API_CLIENT_ID="", SIIS_API_CLIENT_SECRET="")
    def test_sin_credenciales_con_aplicar_corta_con_commanderror(self):
        with patch(OBJETIVO) as validar:
            with self.assertRaisesMessage(CommandError, "SIIS_API_CLIENT_ID"):
                call_command("validar_casos_siis", "--aplicar", stdout=StringIO())

        validar.assert_not_called()
        self.assertEqual(ValidacionSIS.objects.count(), 0)
