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

import tempfile
from datetime import date, timedelta
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, connection, transaction
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from programas.models import (
    AltaIntermediaSIIS,
    CorridaSiis,
    EnvioSIIS,
    Formulario,
    ProgramaSiis,
    TracaFormulario,
    ValidacionSIS,
)
from programas.services import proceso_masivo, siis_envio
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
            call_command("procesar_casos_siis", "--si", "--aplicar", "--total", "1", stdout=StringIO())
        cargar.assert_not_called()

    def test_la_relectura_bajo_el_lock_evita_llegar_al_indice(self, _armar):
        """La capa 2 de la reserva, fijada aparte.

        Las tres capas se tapan entre sí: si se saca la relectura de ``vigente``,
        el índice único igual impide el alta doble y todos los demás tests siguen
        verdes. Pero el camino cambia —se intenta el INSERT y se captura un
        ``IntegrityError``— y eso es ruido en la base y en los logs de PRD por
        cada doble clic. Acá se afirma que **ni se intenta**.
        """
        caso = self._caso(Formulario.Estado.APROBADO)
        EnvioSIIS.objects.create(formulario=caso, estado=EnvioSIIS.Estado.ENVIADO, documento="20301234")

        with CaptureQueriesContext(connection) as consultas:
            # Se entra por ``_mandar_a_siis`` para saltear el atajo barato de
            # ``enviar_beneficiario_a_siis``, que contesta antes de la reserva.
            envio = siis_envio._mandar_a_siis(caso, PAYLOAD[0], {}, siis_envio._base_envio(caso, self.user))

        self.assertEqual(envio.estado, EnvioSIIS.Estado.ENVIADO)
        inserts = [q["sql"] for q in consultas.captured_queries if "INSERT INTO" in q["sql"].upper()]
        self.assertEqual(inserts, [], "la reserva llegó al INSERT: la relectura bajo el lock no está haciendo nada")

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

    def test_sin_aplicar_dice_que_haria_y_no_toca_nada(self):
        salida, _ = self._correr("--liberar", str(self.envio.pk), "--motivo", "no llegó")
        self.envio.refresh_from_db()
        self.assertEqual(self.envio.estado, EnvioSIIS.Estado.INCIERTO)
        self.assertIn("[ensayo]", salida)
        self.assertIn("Agregá --aplicar", salida)

    def test_confirmar_deja_el_caso_informado_y_con_traza(self):
        salida, _ = self._correr(
            "--confirmar", str(self.envio.pk), "--siis-id", "55678", "--aplicar", "--usuario", self.user.username
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
            "--liberar",
            str(self.envio.pk),
            "--motivo",
            "ECOM confirmó que no llegó",
            "--aplicar",
            "--usuario",
            self.user.username,
        )
        self.envio.refresh_from_db()
        self.assertEqual(self.envio.estado, EnvioSIIS.Estado.ERROR)
        self.assertIsNone(self.envio.vigente)
        self.assertEqual(self.envio.codigo_error, "INCIERTO_LIBERADO")
        self.assertIn(self.caso.pk, proceso_masivo.ids_de(proceso_masivo.candidatos(programa=self.programa)))
        traza = TracaFormulario.objects.get(formulario=self.caso)
        self.assertIn("ECOM confirmó que no llegó", traza.valor_nuevo)

    def test_liberar_sin_motivo_no_hace_nada(self):
        with self.assertRaisesMessage(CommandError, "motivo"):
            self._correr("--liberar", str(self.envio.pk), "--aplicar")
        self.envio.refresh_from_db()
        self.assertEqual(self.envio.estado, EnvioSIIS.Estado.INCIERTO)

    def test_liberar_no_consume_un_intento(self):
        """Un caso con 4 errores previos no puede quedar fuera por haberse liberado.

        ``casos_con_errores_agotados`` cuenta los ``ERROR``, y liberar deja uno:
        sin excluirlo, el comando decía «vuelve a ser candidato» y el caso
        quedaba afuera para siempre (el quinto intento que nunca hizo).
        """
        for _ in range(proceso_masivo.MAX_REINTENTOS - 1):
            EnvioSIIS.objects.create(formulario=self.caso, estado=EnvioSIIS.Estado.ERROR, documento="20301234")
        self._correr("--liberar", str(self.envio.pk), "--motivo", "ECOM: no llegó", "--aplicar")

        self.assertEqual(self.caso.envios_sis.filter(estado=EnvioSIIS.Estado.ERROR).count(), 5)
        self.assertEqual(proceso_masivo.casos_con_errores_agotados(), [])
        self.assertIn(self.caso.pk, proceso_masivo.ids_de(proceso_masivo.candidatos(programa=self.programa)))

    def test_liberar_varios_de_una(self):
        otro_caso = self._caso(Formulario.Estado.APROBADO)
        otro = EnvioSIIS.objects.create(
            formulario=otro_caso, estado=EnvioSIIS.Estado.INCIERTO, documento="30999888", id_programa=79
        )
        self._correr("--liberar", f"{self.envio.pk}, {otro.pk}", "--motivo", "ECOM: ninguna llegó", "--aplicar")
        for envio in (self.envio, otro):
            envio.refresh_from_db()
            self.assertEqual(envio.estado, EnvioSIIS.Estado.ERROR)
            self.assertIsNone(envio.clave_persona_plan)

    def test_un_pk_malo_no_deja_el_lote_a_medias(self):
        """Se valida todo antes de escribir nada: 39 conciliados y 1 roto no sirve."""
        with self.assertRaisesMessage(CommandError, "No existe el EnvioSIIS #999999"):
            self._correr("--liberar", f"{self.envio.pk},999999", "--motivo", "x", "--aplicar")
        self.envio.refresh_from_db()
        self.assertEqual(self.envio.estado, EnvioSIIS.Estado.INCIERTO)

    def test_el_csv_de_ecom_se_aplica_de_una(self):
        """La vuelta del CSV: ECOM completa «decision» y el comando lo ejecuta."""
        otro_caso = self._caso(Formulario.Estado.APROBADO)
        otro = EnvioSIIS.objects.create(
            formulario=otro_caso, estado=EnvioSIIS.Estado.INCIERTO, documento="30999888", id_programa=79
        )
        ruta = Path(self.enterContext(tempfile.TemporaryDirectory())) / "respuesta.csv"
        ruta.write_text(
            "\n".join(
                [
                    "envio_id,caso,documento,id_programa,estado,creado,siis_id,codigo_error,decision,motivo",
                    f"{self.envio.pk},{self.caso.pk},20301234,79,INCIERTO,,55678,,confirmar,",
                    f"{otro.pk},{otro_caso.pk},30999888,79,INCIERTO,,,,liberar,ECOM dice que no llegó",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        salida, _ = self._correr("--desde-csv", str(ruta), "--aplicar", "--usuario", self.user.username)

        self.envio.refresh_from_db()
        otro.refresh_from_db()
        self.assertEqual(self.envio.estado, EnvioSIIS.Estado.ENVIADO)
        self.assertEqual(self.envio.siis_id, 55678)
        self.assertEqual(otro.estado, EnvioSIIS.Estado.ERROR)
        self.assertEqual(otro.codigo_error, EnvioSIIS.LIBERADO)
        self.assertIn("1 confirmado(s) y 1 liberado(s)", salida)

    def test_una_fila_del_csv_sin_decision_no_se_toca(self):
        ruta = Path(self.enterContext(tempfile.TemporaryDirectory())) / "respuesta.csv"
        ruta.write_text("\n".join(["envio_id,decision,motivo", f"{self.envio.pk},,", ""]), encoding="utf-8")
        with self.assertRaisesMessage(CommandError, "no hay nada que aplicar"):
            self._correr("--desde-csv", str(ruta), "--aplicar")
        self.envio.refresh_from_db()
        self.assertEqual(self.envio.estado, EnvioSIIS.Estado.INCIERTO)

    def test_el_csv_trae_las_columnas_que_ecom_tiene_que_completar(self):
        salida, _ = self._correr("--listar")
        self.assertIn("decision,motivo", salida.splitlines()[0])

    def test_no_se_concilia_lo_que_no_es_incierto(self):
        otro = self._caso(Formulario.Estado.APROBADO)
        enviado = EnvioSIIS.objects.create(formulario=otro, estado=EnvioSIIS.Estado.ENVIADO, documento="1")
        with self.assertRaisesMessage(CommandError, "no es un resultado incierto"):
            self._correr("--liberar", str(enviado.pk), "--motivo", "x", "--aplicar")

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

    def test_con_dos_procesos_a_la_vez_igual_sale_una_sola_alta(self, _armar):
        """La carrera de SIIS-05: el chequeo en Python la dejaba pasar.

        ``_duplicado_local`` es un check-then-act: entre mirar y escribir hay una
        ventana, y con dos procesos sobre el mismo DNI y plan los dos miraban
        «no hay nadie» y los dos mandaban (19 de 25 veces en MariaDB real). Acá
        se simula esa ventana: el rival aparece **después** de la consulta.
        Quien lo cierra es el índice único de ``clave_persona_plan``, y el
        ``IntegrityError`` se traduce a ``DUPLICADO_LOCAL``.
        """
        rival_caso = self._caso(Formulario.Estado.APROBADO)
        mio = self._caso(Formulario.Estado.APROBADO)
        real = siis_envio._duplicado_local
        entradas = []

        def ciego(formulario, base):
            entradas.append(formulario.pk)
            if len(entradas) == 1:
                # El rival commitea su reserva justo después de que miramos.
                EnvioSIIS.objects.create(
                    formulario=rival_caso, estado=EnvioSIIS.Estado.ENVIADO, documento="20301234", id_programa=79
                )
                return None
            return real(formulario, base)

        with (
            patch("programas.services.siis_envio._duplicado_local", side_effect=ciego),
            patch("programas.services.siis_envio.cargar_beneficiario", return_value=OK) as cargar,
        ):
            envio = enviar_beneficiario_a_siis(mio, self.user)

        cargar.assert_not_called()
        self.assertEqual(envio.estado, EnvioSIIS.Estado.RECHAZADO)
        self.assertEqual(envio.codigo_error, "DUPLICADO_LOCAL")
        self.assertIn(f"#{rival_caso.pk}", envio.detalles["_"][0])
        self.assertEqual(EnvioSIIS.objects.filter(clave_persona_plan="20301234:79").count(), 1)

    def test_el_indice_unico_rechaza_dos_vigentes_de_la_misma_persona_y_plan(self, _armar):
        """Lo mismo sin simular nada: es el motor el que lo impide."""
        uno = self._caso(Formulario.Estado.APROBADO)
        otro = self._caso(Formulario.Estado.APROBADO)
        EnvioSIIS.objects.create(formulario=uno, estado=EnvioSIIS.Estado.ENVIADO, documento="20301234", id_programa=79)
        with self.assertRaises(IntegrityError), transaction.atomic():
            EnvioSIIS.objects.create(
                formulario=otro, estado=EnvioSIIS.Estado.EN_PROCESO, documento="20301234", id_programa=79
            )

    def test_dos_planes_distintos_de_la_misma_persona_conviven(self, _armar):
        """La regla es «una por persona **y plan**», no «una por persona»."""
        uno = self._caso(Formulario.Estado.APROBADO)
        otro = self._caso(Formulario.Estado.APROBADO)
        EnvioSIIS.objects.create(formulario=uno, estado=EnvioSIIS.Estado.ENVIADO, documento="20301234", id_programa=79)
        EnvioSIIS.objects.create(formulario=otro, estado=EnvioSIIS.Estado.ENVIADO, documento="20301234", id_programa=80)
        self.assertEqual(EnvioSIIS.objects.filter(vigente=True).count(), 2)

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


@override_settings(SIIS_API_CLIENT_ID="id-de-prueba", SIIS_API_CLIENT_SECRET="secreto-de-prueba")
@patch("programas.services.siis_envio.armar_payload", return_value=PAYLOAD)
class FrenoConSiisCaidoTests(_BaseProcesoTest):
    """El freno corta con SIIS caído, también cuando lo que devuelve es ambiguo.

    Desde que 500, 502, 504 y ``ReadTimeout`` son ``INCIERTO``, un INCIERTO que
    no contara para el freno —y que además reseteara la racha de errores— dejaba
    la corrida golpeando un servicio caído **para siempre**, y cada vuelta dejaba
    un caso más tomado. Son cuatro caminos: el hilo del masivo y los tres
    comandos que heredan de ``ComandoSiisBase``.

    Los tres comandos se ejercitan **de verdad**, con SIIS contestando mal, y no
    solo mirando que acepten el flag: `reenviar_siis_pendientes` heredaba
    `--max-errores` y `--max-inciertos` de la base y los ignoraba, así que la
    paridad de flags estaba verde y el comando se comía los 200 casos de su
    `--limite` igual (RED-53).
    """

    def _casos(self, cuantos):
        """``cuantos`` casos aprobados, cada uno con su DNI en aprobados_materias.

        DNI distintos a propósito: con el mismo, el segundo sería
        ``DUPLICADO_LOCAL`` (SIIS-05) y nunca llegaría a llamar a SIIS.
        """
        from legajos.models import Ciudadano

        casos = []
        for i in range(cuantos):
            dni = f"3011000{i}"
            ciudadano = Ciudadano.objects.create(
                dni=dni, nombre=f"N{i}", apellido=f"A{i}", fecha_nacimiento=date(1995, 1, 1), genero="F"
            )
            casos.append(
                Formulario.objects.create(
                    relevamiento=self.relevamiento, ciudadano=ciudadano, estado=Formulario.Estado.APROBADO
                )
            )
            with connection.cursor() as cur:
                cur.execute(f"INSERT INTO {proceso_masivo.TABLA_APROBADOS_MATERIAS} (dni) VALUES (%s)", [dni])
        return casos

    #: Los tres comandos que heredan de ``ComandoSiisBase``, con los argumentos
    #: que hacen falta para que cada uno llegue a llamar a SIIS.
    COMANDOS_CON_ALTA = (
        ("enviar_casos_siis", ()),
        ("procesar_casos_siis", ("--solo-enviar", "--si")),
        ("reenviar_siis_pendientes", ()),
    )

    def test_los_comandos_honran_el_freno_con_siis_ambiguo(self, _armar):
        """RED-53: no alcanza con aceptar `--max-inciertos`; hay que cortar.

        El que no lo honraba era `reenviar_siis_pendientes`, y el test de paridad
        de flags no lo veía porque el flag estaba: lo que faltaba era usarlo.
        """
        casos = self._casos(10)
        for nombre, extra in self.COMANDOS_CON_ALTA:
            with self.subTest(comando=nombre):
                # Cada vuelta arranca limpia: los inciertos de la anterior
                # dejarían los casos tomados y no habría a quién llamar.
                EnvioSIIS.objects.all().delete()
                for caso in casos:
                    # `reenviar_siis_pendientes` solo toma los que vienen de un
                    # ERROR técnico; a los otros dos no les molesta.
                    EnvioSIIS.objects.create(
                        formulario=caso, estado=EnvioSIIS.Estado.ERROR, documento=caso.ciudadano.dni
                    )
                salida = StringIO()
                with patch("programas.services.siis_envio.cargar_beneficiario", return_value=INCIERTO) as cargar:
                    with self.assertRaises(SystemExit):
                        call_command(nombre, "--aplicar", "--max-inciertos", "3", *extra, stdout=salida)

                self.assertEqual(cargar.call_count, 3, f"{nombre} no cortó: siguió llamando a SIIS")
                self.assertIn("DETENIDO", salida.getvalue())
                self.assertIn("sin saber si el alta llegó", salida.getvalue())

    def test_el_masivo_corta_a_los_tres_inciertos(self, _armar):
        self._casos(10)
        corrida = CorridaSiis.objects.create(programa=self.programa, total_pedido=10, solicitada_por=self.user)
        validacion = ValidacionSIS(estado=ValidacionSIS.Estado.OK)

        with (
            # ``proceso_masivo`` importa ``armar_payload`` por nombre: el parche
            # de la clase es sobre el módulo del servicio y no lo alcanza.
            patch("programas.services.proceso_masivo.armar_payload", return_value=PAYLOAD),
            patch("programas.services.proceso_masivo.validar_formulario_en_siis", return_value=validacion),
            patch("programas.services.siis_envio.cargar_beneficiario", return_value=INCIERTO) as cargar,
        ):
            proceso_masivo.correr(corrida, catalogos=MagicMock(), lote=10)

        corrida.refresh_from_db()
        self.assertEqual(cargar.call_count, proceso_masivo.MAX_INCIERTOS)
        self.assertEqual(corrida.estado, CorridaSiis.Estado.DETENIDA)
        self.assertIn("sin saber si el alta llegó", corrida.mensaje)
        self.assertIn("conciliar_envios_siis", corrida.mensaje)

    def test_enviar_casos_corta_a_los_tres_inciertos(self, _armar):
        self._casos(10)
        salida = StringIO()
        with patch("programas.services.siis_envio.cargar_beneficiario", return_value=INCIERTO) as cargar:
            with self.assertRaises(SystemExit):
                call_command("enviar_casos_siis", "--aplicar", stdout=salida)

        self.assertEqual(cargar.call_count, proceso_masivo.MAX_INCIERTOS)
        self.assertIn("DETENIDO", salida.getvalue())
        self.assertIn("sin saber si el alta llegó", salida.getvalue())

    def test_procesar_casos_corta_a_los_tres_inciertos(self, _armar):
        self._casos(10)
        salida = StringIO()
        with patch("programas.services.siis_envio.cargar_beneficiario", return_value=INCIERTO) as cargar:
            with self.assertRaises(SystemExit):
                call_command("procesar_casos_siis", "--si", "--aplicar", "--solo-enviar", stdout=salida)

        self.assertEqual(cargar.call_count, proceso_masivo.MAX_INCIERTOS)
        self.assertIn("DETENIDO", salida.getvalue())

    def test_un_incierto_no_borra_la_racha_de_errores(self, _armar):
        """Alternar 500 y timeout no puede dejar las dos rachas en cero para siempre."""
        freno = proceso_masivo.Freno(max_errores=4, max_inciertos=99)
        for _ in range(3):
            self.assertFalse(freno.registrar(proceso_masivo.FALLA_TECNICA))
            self.assertFalse(freno.registrar(proceso_masivo.FALLA_INCIERTA))
        self.assertTrue(freno.registrar(proceso_masivo.FALLA_TECNICA))
        self.assertEqual(freno.tecnicos, 4)

    def test_un_alta_que_sale_bien_vuelve_las_dos_rachas_a_cero(self, _armar):
        freno = proceso_masivo.Freno()
        freno.registrar(proceso_masivo.FALLA_TECNICA)
        freno.registrar(proceso_masivo.FALLA_INCIERTA)
        freno.registrar(None)
        self.assertEqual((freno.tecnicos, freno.inciertos), (0, 0))

    def test_un_caso_ya_tomado_no_cuenta_como_falla_de_siis(self, _armar):
        """Lo que devuelve el servicio sin llamar a SIIS no dice nada del servicio."""
        caso = self._caso(Formulario.Estado.APROBADO)
        EnvioSIIS.objects.create(formulario=caso, estado=EnvioSIIS.Estado.INCIERTO, documento="20301234")
        cuenta = proceso_masivo.Cuenta()

        with patch("programas.services.siis_envio.cargar_beneficiario") as cargar:
            desenlace = proceso_masivo.procesar_caso(caso, self.user, None, cuenta, solo_enviar=True)

        cargar.assert_not_called()
        self.assertIsNone(desenlace)
        self.assertEqual(cuenta.ocupados, 1)
        self.assertEqual(cuenta.inciertos, 0)


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
        modelos = {"EnvioSIIS": EnvioSIIS, "TracaFormulario": TracaFormulario}

        class Apps:
            @staticmethod
            def get_model(app, modelo):
                return modelos[modelo]

        return Apps()

    def _migrar(self):
        """Corre la migración de datos y devuelve lo que imprimió."""
        salida = StringIO()
        with patch("builtins.print", lambda *args, **kw: salida.write(" ".join(str(a) for a in args) + "\n")):
            self.modulo.poblar_vigente(self._apps(), None)
        return salida.getvalue()

    @staticmethod
    def _como_antes_de_la_0075(envio, **extra):
        """Deja la fila como la habría escrito el código viejo: sin ``vigente``.

        Un segundo ``ENVIADO`` del mismo caso —o de la misma persona y plan— solo
        puede existir si viene de antes de esta migración, así que se arma
        salteando el ``save()`` que deriva las columnas nuevas.
        """
        EnvioSIIS.objects.filter(pk=envio.pk).update(
            estado=EnvioSIIS.Estado.ENVIADO, vigente=None, clave_persona_plan=None, **extra
        )

    def test_queda_vigente_el_enviado_mas_viejo_y_los_duplicados_se_listan(self):
        formulario = _crear_formulario_minimo()
        viejo = EnvioSIIS.objects.create(formulario=formulario, estado=EnvioSIIS.Estado.ENVIADO, documento="1")
        nuevo = EnvioSIIS.objects.create(formulario=formulario, estado=EnvioSIIS.Estado.ERROR, documento="1")
        self._como_antes_de_la_0075(nuevo)
        self._como_antes_de_la_0075(viejo, creado=timezone.now() - timedelta(days=2))

        salida = self._migrar()

        viejo.refresh_from_db()
        nuevo.refresh_from_db()
        self.assertTrue(viejo.vigente)
        self.assertIsNone(nuevo.vigente)
        self.assertIn("mas de un alta ENVIADO", salida)
        self.assertIn(f"caso #{formulario.pk}", salida)
        # Y queda consultable en el caso, no solo en el log del deploy.
        traza = TracaFormulario.objects.get(formulario=formulario)
        self.assertIn("alta duplicada en el mismo caso", traza.valor_nuevo)

    def test_dos_casos_del_mismo_dni_y_plan_quedan_los_dos_tomados(self):
        """El duplicado cruzado de PRD: dos altas reales de la misma persona.

        Sacarle ``vigente`` al perdedor lo devolvería a la lista de candidatos y
        la próxima corrida mandaría una **tercera** alta. Los dos siguen tomados;
        lo único que se reparte es la clave, que es la que el índice único exige.
        """
        uno = _crear_formulario_minimo()
        otro = _crear_formulario_minimo(dni="20301234", sufijo="b")
        # Nacen como ERROR —que no ocupa nada— y se los pasa a ENVIADO con un
        # UPDATE: es el único estado en que el código viejo pudo dejarlos, porque
        # hoy el índice único no deja crear dos.
        primero = EnvioSIIS.objects.create(
            formulario=uno, estado=EnvioSIIS.Estado.ERROR, documento="20301234", id_programa=79
        )
        segundo = EnvioSIIS.objects.create(
            formulario=otro, estado=EnvioSIIS.Estado.ERROR, documento="20301234", id_programa=79
        )
        self._como_antes_de_la_0075(primero, creado=timezone.now() - timedelta(days=2))
        self._como_antes_de_la_0075(segundo)

        salida = self._migrar()

        primero.refresh_from_db()
        segundo.refresh_from_db()
        self.assertTrue(primero.vigente)
        self.assertTrue(segundo.vigente, "el perdedor tiene que seguir tomado: liberarlo mandaría una tercera alta")
        self.assertEqual(primero.clave_persona_plan, "20301234:79")
        self.assertIsNone(segundo.clave_persona_plan)
        self.assertIn("mas de un alta vigente en el mismo plan", salida)
        self.assertIn("DNI 20301234", salida)
        # Una traza por cada uno de los dos casos involucrados.
        self.assertEqual(TracaFormulario.objects.filter(campo="envio_siis").count(), 2)

    def test_sin_dni_o_sin_plan_no_entran_al_indice_unico(self):
        """Dos incompletas no son «la misma persona»: quedan con la clave en NULL."""
        uno = _crear_formulario_minimo()
        otro = _crear_formulario_minimo(dni="40111222", sufijo="c")
        for formulario in (uno, otro):
            envio = EnvioSIIS.objects.create(
                formulario=formulario, estado=EnvioSIIS.Estado.ENVIADO, documento="", id_programa=None
            )
            self._como_antes_de_la_0075(envio)

        salida = self._migrar()

        self.assertEqual(EnvioSIIS.objects.filter(vigente=True).count(), 2)
        self.assertEqual(EnvioSIIS.objects.filter(clave_persona_plan__isnull=True).count(), 2)
        self.assertNotIn("ATENCION", salida)

    def test_la_reversa_deja_lo_incierto_como_enviado_para_que_nadie_lo_reenvie(self):
        formulario = _crear_formulario_minimo()
        envio = EnvioSIIS.objects.create(formulario=formulario, estado=EnvioSIIS.Estado.INCIERTO, documento="1")

        with patch("builtins.print", lambda *args, **kw: None):
            self.modulo.revertir_vigente(self._apps(), None)

        envio.refresh_from_db()
        self.assertEqual(envio.estado, EnvioSIIS.Estado.ENVIADO)
        self.assertEqual(envio.codigo_error, "INCIERTO_AL_REVERTIR")


def _crear_formulario_minimo(dni="20301234", sufijo=""):
    """Un caso con lo mínimo para colgarle envíos."""
    from datetime import date

    from django.contrib.auth.models import User

    from legajos.models import Ciudadano
    from programas.models import Convocatoria, ProgramaSiis, Relevamiento, Segmento

    # El programa y su cadena se reusan entre llamadas: ``siis_programa_id`` es
    # único, y lo que estos tests necesitan es más de un **formulario**.
    relevamiento = Relevamiento.objects.order_by("pk").first()
    if relevamiento is None:
        programa = ProgramaSiis.objects.create(nombre="Ñachec", siis_programa_id=79)
        segmento = Segmento.objects.create(nombre="Seg", cupo_maximo=10, programa=programa)
        convocatoria = Convocatoria.objects.create(
            nombre="Conv", segmento=segmento, fecha_inicio=date(2026, 1, 1), fecha_fin=date(2026, 12, 31)
        )
        relevamiento = Relevamiento.objects.create(
            convocatoria=convocatoria,
            territorial=User.objects.create_user("coord_migracion", password="x"),
            fecha_asignada=date(2026, 6, 1),
            zona="A",
        )
    # El DNI es único en ``Ciudadano``: «dos casos del mismo DNI» es una persona
    # con dos formularios, que es justo el escenario de SIIS-05.
    ciudadano, _ = Ciudadano.objects.get_or_create(
        dni=dni,
        defaults={
            "nombre": f"Juan{sufijo}",
            "apellido": "Perez",
            "fecha_nacimiento": date(1995, 6, 15),
            "genero": "M",
        },
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
    FLAGS_COMUNES = {"--aplicar", "--lote", "--pausa", "--max-errores", "--usuario", "--ignorar-corrida", "--motivo"}

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

    def test_los_cuatro_abortan_con_una_corrida_viva(self):
        """SIIS-03: un comando a mano mientras la pantalla está corriendo.

        Es el de la PoC invertido (``test_comando_reenviar_ignora_corrida_viva``).
        Los dos caminos procesan los mismos casos y comparten el freno por
        errores seguidos: con SIIS lento, ninguno de los dos corta a tiempo.
        """
        programa = ProgramaSiis.objects.create(nombre="Ñachec corrida viva", siis_programa_id=781)
        CorridaSiis.objects.create(programa=programa, total_pedido=10, latido=timezone.now())

        for nombre in self.COMANDOS:
            with self.subTest(comando=nombre):
                with patch("programas.services.siis.requests.post") as post:
                    with self.assertRaises(CommandError) as ctx:
                        call_command(nombre, "--aplicar", stdout=StringIO(), stderr=StringIO())
                self.assertIn("corrida", str(ctx.exception).lower())
                self.assertIn("--ignorar-corrida", str(ctx.exception))
                post.assert_not_called()

    def test_el_ensayo_corre_igual_con_una_corrida_viva(self):
        """Mirar qué haría no toca nada: la guarda es sobre ``--aplicar``."""
        programa = ProgramaSiis.objects.create(nombre="Ñachec ensayo", siis_programa_id=782)
        CorridaSiis.objects.create(programa=programa, total_pedido=10, latido=timezone.now())

        for nombre in self.COMANDOS:
            with self.subTest(comando=nombre):
                call_command(nombre, stdout=StringIO(), stderr=StringIO())

    def test_ignorar_corrida_es_la_salida_de_emergencia_y_deja_rastro(self):
        """Saltear la guarda se puede; saltearla en silencio, no."""
        programa = ProgramaSiis.objects.create(nombre="Ñachec emergencia", siis_programa_id=783)
        corrida = CorridaSiis.objects.create(programa=programa, total_pedido=10, latido=timezone.now())
        salida = StringIO()

        call_command(
            "reenviar_siis_pendientes",
            "--aplicar",
            "--ignorar-corrida",
            "--motivo",
            "ECOM pidió reintentar 3 casos hoy",
            stdout=salida,
            stderr=salida,
        )

        self.assertIn("corrida en curso", salida.getvalue())
        corrida.refresh_from_db()
        self.assertIn("--ignorar-corrida", corrida.mensaje)
        self.assertIn("ECOM pidió reintentar 3 casos hoy", corrida.mensaje)

    def test_ignorar_corrida_sin_motivo_no_corre(self):
        programa = ProgramaSiis.objects.create(nombre="Ñachec sin motivo", siis_programa_id=785)
        CorridaSiis.objects.create(programa=programa, total_pedido=10, latido=timezone.now())

        for nombre in self.COMANDOS:
            with self.subTest(comando=nombre):
                with self.assertRaises(CommandError) as ctx:
                    call_command(nombre, "--aplicar", "--ignorar-corrida", stdout=StringIO(), stderr=StringIO())
                self.assertIn("--motivo", str(ctx.exception))

    def test_una_corrida_interrumpida_no_frena_a_los_comandos(self):
        """Un pod muerto hace una hora no puede dejar la operación trabada."""
        programa = ProgramaSiis.objects.create(nombre="Ñachec muerta", siis_programa_id=784)
        CorridaSiis.objects.create(
            programa=programa, total_pedido=10, latido=timezone.now() - CorridaSiis.LATIDO_VENCIDO * 2
        )

        call_command("reenviar_siis_pendientes", "--aplicar", stdout=StringIO(), stderr=StringIO())

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
