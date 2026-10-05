"""Un alta por caso, resultado incierto no reintentable y conciliación.

Auditoría oct-2026, Ola 1 PR 2 (Cambio 127): SIIS-01, SIIS-02, SIIS-04 y SIIS-05.
Son las PoC de ``docs/internal/auditoria-2026-10/poc/test_repro_siis_becas.py``
**invertidas**: cada clase afirmaba el bug y acá afirma el arreglo.

Lo que se protege, en una línea: **el alta en SIIS no tiene baja**. Dos altas de
la misma persona son irreversibles desde este lado, así que cada camino que
puede llamar a la API tiene que pasar por la misma reserva, y un resultado que
pudo haber llegado no se reintenta nunca solo.

En SQLite ``select_for_update`` es un no-op: la concurrencia se simula con un
mock que ejecuta la operación rival dentro de la ventana (mismo patrón que
``test_candados_concurrencia.py``). Lo que el lock no cubre lo cubre el índice
único, y ese sí se ejerce de verdad.
"""

from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from programas.models import AltaIntermediaSIIS, EnvioSIIS, Formulario, TracaFormulario, ValidacionSIS
from programas.services import proceso_masivo
from programas.services.siis_envio import enviar_beneficiario_a_siis, guardar_en_tabla_intermedia, mensaje_envio
from programas.tests.test_proceso_masivo import _BaseProcesoTest, crear_tabla_aprobados_materias

OK = {"success": True, "resultado": "OK", "siis_id": 1, "data": {"ids_generados": [1]}}
INCIERTO = {
    "success": False,
    "resultado": "INCIERTO",
    "codigo": "RESULTADO_INCIERTO",
    "reintentable": False,
    "error": "SIIS no contestó.",
    "detalles": {},
    "data": {},
}
ERROR_DE_RED = {
    "success": False,
    "resultado": "NO_ENVIADO",
    "codigo": "ERROR_TECNICO",
    "reintentable": True,
    "error": "No se pudo conectar con SIIS.",
    "detalles": {},
    "data": {},
}
# Lo mínimo que la tabla intermedia exige con columnas de verdad (tdoc y dni).
PAYLOAD = ({"tdoc": 1, "dni": 20301234, "id_plan_soc": 79, "id_fun_x_plan": 4}, {})


@override_settings(SIIS_API_CLIENT_ID="id-de-prueba", SIIS_API_CLIENT_SECRET="secreto-de-prueba")
@patch("programas.services.siis_envio.armar_payload", return_value=PAYLOAD)
class UnSoloEnvioVigenteTests(_BaseProcesoTest):
    """SIIS-01: un solo envío vigente por caso, en todas las vías."""

    def test_segundo_envio_con_primero_en_vuelo_no_llama_a_siis(self, _armar):
        """La PoC invertida: con el primer POST en vuelo, el segundo se retira.

        Antes: dos POST y dos ``ENVIADO``. El check-then-act leía los envíos sin
        lock, armaba el payload y recién registraba después del HTTP.
        """
        caso = self._caso(Formulario.Estado.APROBADO)
        reentrante = {}

        def post(payload):
            if "envio" not in reentrante:
                # Mientras el primer POST espera a SIIS entra otro camino sobre
                # el mismo caso: doble clic, masivo, comando a mano.
                reentrante["envio"] = enviar_beneficiario_a_siis(Formulario.objects.get(pk=caso.pk), self.user)
            return OK

        with patch("programas.services.siis_envio.cargar_beneficiario", side_effect=post) as cargar:
            envio = enviar_beneficiario_a_siis(caso, self.user)

        self.assertEqual(cargar.call_count, 1)
        self.assertEqual(caso.envios_sis.filter(vigente=True).count(), 1)
        self.assertEqual(caso.envios_sis.filter(estado=EnvioSIIS.Estado.ENVIADO).count(), 1)
        self.assertEqual(envio.estado, EnvioSIIS.Estado.ENVIADO)
        # El segundo recibe el envío en vuelo, no uno nuevo.
        self.assertEqual(reentrante["envio"].pk, envio.pk)
        self.assertEqual(reentrante["envio"].estado, EnvioSIIS.Estado.EN_PROCESO)

    def test_indice_unico_rechaza_un_segundo_vigente(self, _armar):
        """Lo que el lock no cubre (dos pods, un restore) lo cubre el motor."""
        caso = self._caso(Formulario.Estado.APROBADO)
        EnvioSIIS.objects.create(formulario=caso, estado=EnvioSIIS.Estado.ENVIADO, documento="20301234")
        with self.assertRaises(IntegrityError), transaction.atomic():
            EnvioSIIS.objects.create(formulario=caso, estado=EnvioSIIS.Estado.EN_PROCESO, documento="20301234")

    def test_varios_no_vigentes_del_mismo_caso_conviven(self, _armar):
        """Varios NULL en el índice único: es la unicidad condicional que MariaDB no da."""
        caso = self._caso(Formulario.Estado.APROBADO)
        for _ in range(3):
            EnvioSIIS.objects.create(formulario=caso, estado=EnvioSIIS.Estado.ERROR, documento="20301234")
        self.assertEqual(caso.envios_sis.count(), 3)
        self.assertEqual(caso.envios_sis.filter(vigente=True).count(), 0)

    def test_el_estado_decide_vigente_aunque_el_que_llama_no_lo_sepa(self, _armar):
        caso = self._caso(Formulario.Estado.APROBADO)
        enviado = EnvioSIIS.objects.create(formulario=caso, estado=EnvioSIIS.Estado.ENVIADO, documento="1")
        rechazado = EnvioSIIS.objects.create(formulario=caso, estado=EnvioSIIS.Estado.RECHAZADO, documento="1")
        self.assertTrue(enviado.vigente)
        self.assertIsNone(rechazado.vigente)
        self.assertEqual(caso.envio_siis_activo, enviado)

    def test_un_envio_en_proceso_saca_al_caso_de_todas_las_listas(self, _armar):
        """Candidatos del masivo, ``reenviar_siis_pendientes`` y ``enviar_casos_siis``."""
        caso = self._caso(Formulario.Estado.APROBADO)
        EnvioSIIS.objects.create(formulario=caso, estado=EnvioSIIS.Estado.ERROR, documento="20301234")
        self.assertIn(caso.pk, proceso_masivo.ids_de(proceso_masivo.candidatos(programa=self.programa)))

        EnvioSIIS.objects.create(formulario=caso, estado=EnvioSIIS.Estado.EN_PROCESO, documento="20301234")

        self.assertNotIn(caso.pk, proceso_masivo.ids_de(proceso_masivo.candidatos(programa=self.programa)))
        with patch("programas.management.commands.reenviar_siis_pendientes.enviar_beneficiario_a_siis") as reenviar:
            call_command("reenviar_siis_pendientes", "--aplicar", stdout=StringIO())
        reenviar.assert_not_called()
        with patch("programas.management.commands.enviar_casos_siis.enviar_beneficiario_a_siis") as masivo:
            call_command("enviar_casos_siis", "--aplicar", stdout=StringIO())
        masivo.assert_not_called()

    def test_la_tabla_intermedia_no_manda_un_caso_ya_tomado(self, _armar):
        """La séptima vía (#517): ``sincronizar_tabla_intermedia`` pasa por la misma reserva."""
        caso = self._caso(Formulario.Estado.APROBADO)
        with patch("programas.services.siis_envio.cargar_beneficiario", return_value=OK):
            alta, _ = guardar_en_tabla_intermedia(caso, self.user)
        self.assertIsNotNone(alta)
        EnvioSIIS.objects.create(formulario=caso, estado=EnvioSIIS.Estado.EN_PROCESO, documento="20301234")

        with patch("programas.services.siis_envio.cargar_beneficiario") as cargar:
            call_command("procesar_casos_siis", "--aplicar", "--total", "1", stdout=StringIO())
        cargar.assert_not_called()

    def test_guardar_en_la_tabla_no_duplica_un_caso_en_vuelo(self, _armar):
        caso = self._caso(Formulario.Estado.APROBADO)
        EnvioSIIS.objects.create(formulario=caso, estado=EnvioSIIS.Estado.INCIERTO, documento="20301234")
        alta, envio = guardar_en_tabla_intermedia(caso, self.user)
        self.assertIsNone(alta)
        self.assertIsNone(envio)
        self.assertFalse(AltaIntermediaSIIS.objects.exists())


@patch("programas.services.siis_envio.armar_payload", return_value=PAYLOAD)
class ResultadoInciertoTests(_BaseProcesoTest):
    """SIIS-02: lo ambiguo no se reintenta solo, se concilia."""

    def test_un_resultado_incierto_no_se_reintenta_por_ninguna_via(self, _armar):
        """La PoC invertida: antes el ``ReadTimeout`` quedaba ERROR y el masivo lo retomaba."""
        caso = self._caso(Formulario.Estado.APROBADO)
        with patch("programas.services.siis_envio.cargar_beneficiario", return_value=INCIERTO):
            envio = enviar_beneficiario_a_siis(caso, self.user)

        self.assertEqual(envio.estado, EnvioSIIS.Estado.INCIERTO)
        self.assertTrue(envio.vigente)
        self.assertFalse(envio.reintentable)
        self.assertTrue(envio.incierto)
        self.assertNotIn(caso.pk, proceso_masivo.ids_de(proceso_masivo.candidatos(programa=self.programa)))
        self.assertEqual(mensaje_envio(envio)[0], "warning")

        with patch("programas.services.siis_envio.cargar_beneficiario") as cargar:
            self.assertEqual(enviar_beneficiario_a_siis(Formulario.objects.get(pk=caso.pk), self.user).pk, envio.pk)
        cargar.assert_not_called()

    def test_un_error_de_red_si_vuelve_a_ser_candidato(self, _armar):
        """El contraste: cuando consta que el POST no salió, el caso se libera solo."""
        caso = self._caso(Formulario.Estado.APROBADO)
        with patch("programas.services.siis_envio.cargar_beneficiario", return_value=ERROR_DE_RED):
            envio = enviar_beneficiario_a_siis(caso, self.user)

        self.assertEqual(envio.estado, EnvioSIIS.Estado.ERROR)
        self.assertIsNone(envio.vigente)
        self.assertTrue(envio.reintentable)
        self.assertIn(caso.pk, proceso_masivo.ids_de(proceso_masivo.candidatos(programa=self.programa)))

    def test_un_proceso_muerto_despues_del_post_deja_el_caso_tomado(self, _armar):
        """A1-03: gunicorn recicla el worker entre el POST y el registro."""
        caso = self._caso(Formulario.Estado.APROBADO)

        def muere(payload):
            raise SystemExit(1)

        with patch("programas.services.siis_envio.cargar_beneficiario", side_effect=muere):
            with self.assertRaises(SystemExit):
                enviar_beneficiario_a_siis(caso, self.user)

        envio = caso.envios_sis.get()
        self.assertEqual(envio.estado, EnvioSIIS.Estado.EN_PROCESO)
        self.assertTrue(envio.vigente)
        self.assertNotIn(caso.pk, proceso_masivo.ids_de(proceso_masivo.candidatos(programa=self.programa)))

    def test_un_en_proceso_viejo_se_ve_incierto(self, _armar):
        caso = self._caso(Formulario.Estado.APROBADO)
        envio = EnvioSIIS.objects.create(formulario=caso, estado=EnvioSIIS.Estado.EN_PROCESO, documento="1")
        self.assertFalse(envio.incierto)
        self.assertEqual(mensaje_envio(envio)[0], "info")

        viejo = timezone.now() - EnvioSIIS.EN_PROCESO_VENCE - timedelta(minutes=1)
        EnvioSIIS.objects.filter(pk=envio.pk).update(creado=viejo)
        envio.refresh_from_db()
        self.assertTrue(envio.incierto)
        self.assertEqual(mensaje_envio(envio)[0], "warning")

    def test_el_cierre_no_pisa_lo_que_decidio_una_conciliacion(self, _armar):
        """El UPDATE filtra por EN_PROCESO: si alguien ya lo resolvió, no se vuelve atrás."""
        caso = self._caso(Formulario.Estado.APROBADO)

        def post(payload):
            # Mientras el POST estaba en vuelo, una conciliación lo dio por bueno.
            EnvioSIIS.objects.filter(formulario=caso).update(
                estado=EnvioSIIS.Estado.ENVIADO, siis_id=999, codigo_error="INCIERTO_CONFIRMADO"
            )
            return ERROR_DE_RED

        with patch("programas.services.siis_envio.cargar_beneficiario", side_effect=post):
            envio = enviar_beneficiario_a_siis(caso, self.user)

        self.assertEqual(envio.estado, EnvioSIIS.Estado.ENVIADO)
        self.assertEqual(envio.siis_id, 999)
        self.assertEqual(envio.codigo_error, "INCIERTO_CONFIRMADO")


class ConciliarEnviosSiisTests(_BaseProcesoTest):
    """El comando que es la única salida de un INCIERTO."""

    def setUp(self):
        super().setUp()
        self.caso = self._caso(Formulario.Estado.APROBADO)
        self.envio = EnvioSIIS.objects.create(
            formulario=self.caso,
            estado=EnvioSIIS.Estado.INCIERTO,
            documento="20301234",
            id_programa=79,
            codigo_error="RESULTADO_INCIERTO",
        )

    def _correr(self, *args):
        salida, errores = StringIO(), StringIO()
        call_command("conciliar_envios_siis", *args, stdout=salida, stderr=errores)
        return salida.getvalue(), errores.getvalue()

    def test_listar_arma_el_csv_para_ecom(self):
        salida, errores = self._correr("--listar")
        self.assertIn("envio_id,caso,documento,id_programa", salida)
        self.assertIn(f"{self.envio.pk},{self.caso.pk},20301234,79,INCIERTO", salida)
        self.assertIn("1 envío(s) de resultado desconocido", errores)

    def test_listar_no_trae_los_en_proceso_que_todavia_pueden_estar_en_vuelo(self):
        otro = self._caso(Formulario.Estado.APROBADO)
        EnvioSIIS.objects.create(formulario=otro, estado=EnvioSIIS.Estado.EN_PROCESO, documento="1")
        salida, _ = self._correr("--listar")
        self.assertNotIn("EN_PROCESO", salida)

    def test_confirmar_deja_el_caso_informado_y_con_traza(self):
        salida, _ = self._correr(
            "--confirmar", str(self.envio.pk), "--siis-id", "55678", "--usuario", self.user.username
        )
        self.envio.refresh_from_db()
        self.assertEqual(self.envio.estado, EnvioSIIS.Estado.ENVIADO)
        self.assertTrue(self.envio.vigente)
        self.assertEqual(self.envio.siis_id, 55678)
        self.assertIsNotNone(self.envio.resuelto_en)
        traza = TracaFormulario.objects.get(formulario=self.caso)
        self.assertEqual(traza.editado_por, self.user)
        self.assertIn("55678", traza.valor_nuevo)
        self.assertIn("confirmado", salida)

    def test_liberar_permite_reenvio_y_deja_traza(self):
        self._correr(
            "--liberar", str(self.envio.pk), "--motivo", "ECOM confirmó que no llegó", "--usuario", self.user.username
        )
        self.envio.refresh_from_db()
        self.assertEqual(self.envio.estado, EnvioSIIS.Estado.ERROR)
        self.assertIsNone(self.envio.vigente)
        self.assertEqual(self.envio.codigo_error, "INCIERTO_LIBERADO")
        self.assertIn(self.caso.pk, proceso_masivo.ids_de(proceso_masivo.candidatos(programa=self.programa)))
        traza = TracaFormulario.objects.get(formulario=self.caso)
        self.assertIn("ECOM confirmó que no llegó", traza.valor_nuevo)

    def test_liberar_sin_motivo_no_hace_nada(self):
        with self.assertRaisesMessage(CommandError, "--motivo"):
            self._correr("--liberar", str(self.envio.pk))
        self.envio.refresh_from_db()
        self.assertEqual(self.envio.estado, EnvioSIIS.Estado.INCIERTO)

    def test_no_se_concilia_lo_que_no_es_incierto(self):
        otro = self._caso(Formulario.Estado.APROBADO)
        enviado = EnvioSIIS.objects.create(formulario=otro, estado=EnvioSIIS.Estado.ENVIADO, documento="1")
        with self.assertRaisesMessage(CommandError, "no es un resultado incierto"):
            self._correr("--liberar", str(enviado.pk), "--motivo", "x")

    def test_una_sola_accion_por_corrida(self):
        with self.assertRaisesMessage(CommandError, "una sola acción"):
            self._correr("--listar", "--confirmar", str(self.envio.pk))


@override_settings(SIIS_API_CLIENT_ID="id-de-prueba", SIIS_API_CLIENT_SECRET="secreto-de-prueba")
@patch("programas.services.siis_envio.armar_payload", return_value=PAYLOAD)
class EstadoRelidoBajoLockTests(_BaseProcesoTest):
    """SIIS-04: el estado se relee bajo lock, no se decide con el hidratado."""

    def test_un_caso_dado_de_baja_despues_de_hidratar_no_se_informa(self, _armar):
        """La PoC invertida: antes ``procesar_caso`` lo mandaba igual."""
        caso = self._caso(Formulario.Estado.APROBADO)
        hidratado = proceso_masivo.hidratar([caso.pk])[0]
        Formulario.objects.filter(pk=caso.pk).update(estado=Formulario.Estado.BAJA)
        cuenta = proceso_masivo.Cuenta()
        validacion = ValidacionSIS(estado=ValidacionSIS.Estado.OK)

        with (
            patch("programas.services.proceso_masivo.validar_formulario_en_siis", return_value=validacion),
            patch("programas.services.siis_envio.cargar_beneficiario", return_value=OK) as cargar,
        ):
            proceso_masivo.procesar_caso(hidratado, self.user, None, cuenta)

        cargar.assert_not_called()
        self.assertEqual(cuenta.no_aprobable, 1)
        self.assertFalse(EnvioSIIS.objects.filter(formulario=caso).exists())

    def test_enviar_casos_con_estado_cambiado_no_informa(self, _armar):
        caso = self._caso(Formulario.Estado.APROBADO)
        original = proceso_masivo.hidratar

        def hidratar_y_dar_de_baja(ids):
            casos = original(ids)
            Formulario.objects.filter(pk=caso.pk).update(estado=Formulario.Estado.BAJA)
            return casos

        with (
            patch("programas.services.proceso_masivo.hidratar", side_effect=hidratar_y_dar_de_baja),
            patch("programas.services.siis_envio.cargar_beneficiario", return_value=OK) as cargar,
        ):
            salida = StringIO()
            call_command("enviar_casos_siis", "--aplicar", stdout=salida)

        cargar.assert_not_called()
        self.assertRegex(salida.getvalue(), r"cambiaron de estado y no se informaron\s+1")

    def test_la_tabla_intermedia_no_informa_un_caso_que_paso_a_baja(self, _armar):
        """#517: el payload guardado no sabe que el caso cambió después."""
        caso = self._caso(Formulario.Estado.APROBADO)
        alta, _ = guardar_en_tabla_intermedia(caso, self.user)
        self.assertIsNotNone(alta)
        Formulario.objects.filter(pk=caso.pk).update(estado=Formulario.Estado.BAJA)

        from programas.services.siis_envio import sincronizar_tabla_intermedia

        with patch("programas.services.siis_envio.cargar_beneficiario", return_value=OK) as cargar:
            cuenta = sincronizar_tabla_intermedia(self.user)

        cargar.assert_not_called()
        self.assertEqual(cuenta["no_aprobables"], 1)
        alta.refresh_from_db()
        self.assertFalse(alta.sincronizado)


@patch("programas.services.siis_envio.armar_payload", return_value=PAYLOAD)
class DuplicadoLocalTests(_BaseProcesoTest):
    """SIIS-05: la misma persona y el mismo plan, una sola vez (D-S05)."""

    def test_el_mismo_dni_y_plan_en_otro_caso_no_se_informa_otra_vez(self, _armar):
        """La PoC invertida: antes eran dos POST, porque la idempotencia era por caso."""
        primero = self._caso(Formulario.Estado.APROBADO)
        segundo = self._caso(Formulario.Estado.APROBADO)

        with patch("programas.services.siis_envio.cargar_beneficiario", return_value=OK) as cargar:
            enviar_beneficiario_a_siis(primero, self.user)
            envio = enviar_beneficiario_a_siis(segundo, self.user)

        self.assertEqual(cargar.call_count, 1)
        self.assertEqual(envio.estado, EnvioSIIS.Estado.RECHAZADO)
        self.assertEqual(envio.codigo_error, "DUPLICADO_LOCAL")
        self.assertIn(f"#{primero.pk}", envio.detalles["_"][0])
        # El rechazo local no ocupa el caso: si el otro se libera, este puede salir.
        self.assertIsNone(envio.vigente)
        self.assertEqual(mensaje_envio(envio)[0], "warning")

    def test_un_envio_no_vigente_del_mismo_dni_no_bloquea(self, _armar):
        primero = self._caso(Formulario.Estado.APROBADO)
        segundo = self._caso(Formulario.Estado.APROBADO)
        EnvioSIIS.objects.create(
            formulario=primero, estado=EnvioSIIS.Estado.ERROR, documento="20301234", id_programa=79
        )

        with patch("programas.services.siis_envio.cargar_beneficiario", return_value=OK) as cargar:
            envio = enviar_beneficiario_a_siis(segundo, self.user)

        self.assertEqual(cargar.call_count, 1)
        self.assertEqual(envio.estado, EnvioSIIS.Estado.ENVIADO)

    def test_el_masivo_cuenta_los_duplicados_aparte(self, _armar):
        primero = self._caso(Formulario.Estado.APROBADO)
        EnvioSIIS.objects.create(
            formulario=primero, estado=EnvioSIIS.Estado.ENVIADO, documento="20301234", id_programa=79
        )
        segundo = self._caso(Formulario.Estado.APROBADO)
        cuenta = proceso_masivo.Cuenta()

        with patch("programas.services.siis_envio.cargar_beneficiario", return_value=OK) as cargar:
            proceso_masivo.procesar_caso(segundo, self.user, None, cuenta, solo_enviar=True)

        cargar.assert_not_called()
        self.assertEqual(cuenta.duplicados, 1)
        self.assertEqual(cuenta.rechazados, 0)


class CasosConErroresAgotadosTests(_BaseProcesoTest):
    """A2-15 (punto 6 de SIIS-02): no se insiste para siempre con el mismo caso."""

    def test_cinco_errores_lo_sacan_de_los_candidatos(self):
        caso = self._caso(Formulario.Estado.APROBADO)
        for _ in range(proceso_masivo.MAX_REINTENTOS - 1):
            EnvioSIIS.objects.create(formulario=caso, estado=EnvioSIIS.Estado.ERROR, documento="20301234")
        self.assertIn(caso.pk, proceso_masivo.ids_de(proceso_masivo.candidatos(programa=self.programa)))

        EnvioSIIS.objects.create(formulario=caso, estado=EnvioSIIS.Estado.ERROR, documento="20301234")

        self.assertEqual(proceso_masivo.casos_con_errores_agotados(), [caso.pk])
        self.assertNotIn(caso.pk, proceso_masivo.ids_de(proceso_masivo.candidatos(programa=self.programa)))

    def test_reenviar_los_lista_y_no_los_toca(self):
        caso = self._caso(Formulario.Estado.APROBADO)
        for _ in range(proceso_masivo.MAX_REINTENTOS):
            EnvioSIIS.objects.create(formulario=caso, estado=EnvioSIIS.Estado.ERROR, documento="20301234")
        salida = StringIO()
        with patch("programas.management.commands.reenviar_siis_pendientes.enviar_beneficiario_a_siis") as enviar:
            call_command("reenviar_siis_pendientes", "--aplicar", stdout=salida)
        enviar.assert_not_called()
        self.assertIn("necesitan que alguien los mire", salida.getvalue())
        self.assertIn(str(caso.pk), salida.getvalue())


class MigracionVigenteTests(TestCase):
    """La migración de datos de la 0075, sobre el modelo real.

    Se ejerce la función, no el ``migrate``: el runner crea el esquema desde los
    modelos (``DJANGO_SYNCDB_PROJECT_APPS``) y no hay forma de volver al estado
    previo sin la columna. Lo que importa es la regla —el ENVIADO **más viejo**—
    y que un caso con dos altas no haga fallar la migración.
    """

    def setUp(self):
        from programas.migrations import __name__ as _  # noqa: F401  (el paquete existe)

        self.modulo = __import__("programas.migrations.0075_enviosiis_vigente", fromlist=["poblar_vigente"])

    def _apps(self):
        class Apps:
            @staticmethod
            def get_model(app, modelo):
                return EnvioSIIS

        return Apps()

    def test_queda_vigente_el_enviado_mas_viejo_y_los_duplicados_se_listan(self):
        from programas.tests.test_siis_envio import _BaseEnvioTest  # noqa: F401 (solo por el import circular)

        formulario = _crear_formulario_minimo()
        viejo = EnvioSIIS.objects.create(formulario=formulario, estado=EnvioSIIS.Estado.ENVIADO, documento="1")
        nuevo = EnvioSIIS.objects.create(formulario=formulario, estado=EnvioSIIS.Estado.ERROR, documento="1")
        # Un segundo ENVIADO solo puede existir si viene de antes de la 0075: se
        # crea salteando el ``save()`` y el índice, con un UPDATE directo.
        EnvioSIIS.objects.filter(pk=nuevo.pk).update(estado=EnvioSIIS.Estado.ENVIADO, vigente=None)
        EnvioSIIS.objects.filter(pk=viejo.pk).update(vigente=None, creado=timezone.now() - timedelta(days=2))

        salida = StringIO()
        with patch("builtins.print", lambda *args, **kw: salida.write(" ".join(str(a) for a in args))):
            self.modulo.poblar_vigente(self._apps(), None)

        viejo.refresh_from_db()
        nuevo.refresh_from_db()
        self.assertTrue(viejo.vigente)
        self.assertIsNone(nuevo.vigente)
        self.assertIn("más de un alta ENVIADO", salida.getvalue())
        self.assertIn(f"caso #{formulario.pk}", salida.getvalue())

    def test_la_reversa_deja_lo_incierto_como_enviado_para_que_nadie_lo_reenvie(self):
        formulario = _crear_formulario_minimo()
        envio = EnvioSIIS.objects.create(formulario=formulario, estado=EnvioSIIS.Estado.INCIERTO, documento="1")

        with patch("builtins.print", lambda *args, **kw: None):
            self.modulo.revertir_vigente(self._apps(), None)

        envio.refresh_from_db()
        self.assertEqual(envio.estado, EnvioSIIS.Estado.ENVIADO)
        self.assertEqual(envio.codigo_error, "INCIERTO_AL_REVERTIR")


def _crear_formulario_minimo():
    """Un caso con lo mínimo para colgarle envíos."""
    from datetime import date

    from django.contrib.auth.models import User

    from legajos.models import Ciudadano
    from programas.models import Convocatoria, ProgramaSiis, Relevamiento, Segmento

    programa = ProgramaSiis.objects.create(nombre="Ñachec", siis_programa_id=79)
    segmento = Segmento.objects.create(nombre="Seg", cupo_maximo=10, programa=programa)
    convocatoria = Convocatoria.objects.create(
        nombre="Conv", segmento=segmento, fecha_inicio=date(2026, 1, 1), fecha_fin=date(2026, 12, 31)
    )
    user = User.objects.create_user("coord_migracion", password="x")
    relevamiento = Relevamiento.objects.create(
        convocatoria=convocatoria, territorial=user, fecha_asignada=date(2026, 6, 1), zona="A"
    )
    ciudadano = Ciudadano.objects.create(
        dni="20301234", nombre="Juan", apellido="Perez", fecha_nacimiento=date(1995, 6, 15), genero="M"
    )
    return Formulario.objects.create(relevamiento=relevamiento, ciudadano=ciudadano, estado=Formulario.Estado.APROBADO)


@override_settings(SIIS_API_CLIENT_ID="id-de-prueba", SIIS_API_CLIENT_SECRET="secreto-de-prueba")
class ParidadComandosSiisTests(TestCase):
    """RED-53: lo que se agrega en un comando de SIIS se agrega en los cuatro.

    Los cuatro que hablan con SIIS caso por caso heredan de ``ComandoSiisBase``.
    El riesgo que mide este test es el de la «séptima vía»: una guarda nueva que
    entra en tres comandos y deja al cuarto abierto. ``correr_alta_siis`` no está
    porque no llama a SIIS: encadena a estos.
    """

    COMANDOS = ("validar_casos_siis", "enviar_casos_siis", "procesar_casos_siis", "reenviar_siis_pendientes")
    FLAGS_COMUNES = {"--aplicar", "--lote", "--pausa", "--max-errores", "--usuario"}

    def setUp(self):
        # Cambio 90: sin la tabla, dos de los cuatro cortan antes de empezar.
        crear_tabla_aprobados_materias()

    def _parser(self, nombre):
        from django.core.management import load_command_class

        comando = load_command_class("programas", nombre)
        return comando, comando.create_parser("manage.py", nombre)

    def test_los_cuatro_comandos_aceptan_los_mismos_flags(self):
        for nombre in self.COMANDOS:
            with self.subTest(comando=nombre):
                _, parser = self._parser(nombre)
                opciones = {cadena for accion in parser._actions for cadena in accion.option_strings}
                self.assertTrue(
                    self.FLAGS_COMUNES <= opciones,
                    f"a {nombre} le faltan {sorted(self.FLAGS_COMUNES - opciones)}",
                )

    def test_los_cuatro_heredan_de_la_base(self):
        from programas.management.commands._base_siis import ComandoSiisBase

        for nombre in self.COMANDOS:
            with self.subTest(comando=nombre):
                comando, _ = self._parser(nombre)
                self.assertIsInstance(comando, ComandoSiisBase)

    def test_ninguno_llama_a_siis_sin_aplicar(self):
        """El ensayo es el default en los cuatro: ninguno manda nada por omisión."""
        with (
            patch("programas.services.siis.requests.post") as post,
            patch("programas.services.siis.requests.get") as get,
        ):
            for nombre in self.COMANDOS:
                with self.subTest(comando=nombre):
                    call_command(nombre, stdout=StringIO(), stderr=StringIO())
            post.assert_not_called()
            get.assert_not_called()
