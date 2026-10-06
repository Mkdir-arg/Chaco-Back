r"""Reproducciones de SIIS y núcleo de Becas (verificación V2, pasada 2).

Auditoría integral DATAÑACH, oct-2026 (ver el README.md de la carpeta de la auditoría).

CÓMO LEERLO (importante para TDD)
  Cada test AFIRMA EL COMPORTAMIENTO DEFECTUOSO ACTUAL: hoy PASA (verde = el bug existe en
  origin/development @ 917e583). Después del fix, el test correspondiente tiene que FALLAR.
  Para el ciclo TDD del ítem: copiá el test, INVERTÍ la aserción (o escribí el test de la
  sección «Tests a agregar» de la ficha), confirmá que el test invertido FALLA antes del fix
  y PASA después. Este archivo NO se commitea tal cual: se commitea el test invertido, con
  el nombre que pide la ficha.

CÓMO CORRERLO (PowerShell, raíz del repo, en el worktree de la ola)
  $env:PY = "C:\Users\mkdir\Proyectos\Chaco\.venv312\Scripts\python.exe"   # el venv vive en el checkout principal
  $env:DJANGO_SECRET_KEY = "test-key"; $env:PYTEST_RUNNING = "1"; $env:DJANGO_SYNCDB_PROJECT_APPS = "True"
  Copy-Item <este archivo> programas/tests/test_repro_siis_becas.py
  & $env:PY manage.py test programas.tests.test_repro_siis_becas -v 2
  (.venv312 = Python 3.12 + Django 5.2.17, igual al CI. No usar el Python global.)

  Depende de programas.tests.test_proceso_masivo._BaseProcesoTest: por eso va en programas/tests/.
  En SQLite select_for_update es un no-op: la concurrencia se simula con un mock que ejecuta la
  operación rival dentro de la ventana (mismo patrón que test_candados_concurrencia.py).

QUÉ ID CANÓNICO REPRODUCE CADA CLASE
  SiisAltaSinExclusionTests.test_reentrada_*     -> SIIS-01
  SiisAltaSinExclusionTests.test_comando_*       -> SIIS-03 (los comandos ignoran la corrida viva)
  SiisAltaSinExclusionTests.test_mismo_dni_*     -> SIIS-05
  ResultadoAmbiguoTests                          -> SIIS-02
  EstadoViejoEnMasivoTests                       -> SIIS-04
  LatidoTests                                    -> SIIS-03
  AprobarPisaRechazoTests                        -> BEC-01
  EsperaDobleTests                               -> BEC-02
  SyncCatalogoVacioTests                         -> SIIS-06
  CompatibilidadBodyListaTests                   -> SIIS-11
  PersonasAplanadoTests                          -> SIIS-10
  ApoderadoTests                                 -> SIIS-12
"""

from datetime import date, timedelta
from io import StringIO
from unittest.mock import MagicMock, patch

import requests
from django.core.management import call_command
from django.utils import timezone

from programas.models import CorridaSiis, EnvioSIIS, Formulario, ListaEspera, ProgramaSiis, ValidacionSIS
from programas.services import proceso_masivo
from programas.services import siis as siis_mod
from programas.services.cupo import agregar_a_lista_espera, aprobar_o_poner_en_espera
from programas.services.siis_envio import enviar_beneficiario_a_siis
from programas.tests.test_proceso_masivo import _BaseProcesoTest

OK = {"success": True, "siis_id": 1, "data": {"ids_generados": [1]}}
PAYLOAD = ({"dni": 20301234, "id_plan_soc": 79, "id_fun_x_plan": 4}, {})


class SiisAltaSinExclusionTests(_BaseProcesoTest):
    """SIIS-01: el alta es check-then-act; una segunda llamada con la primera en vuelo vuelve a POSTear."""

    @patch("programas.services.siis_envio.armar_payload", return_value=PAYLOAD)
    def test_reentrada_con_primero_en_vuelo_duplica_alta(self, _armar):
        caso = self._caso(Formulario.Estado.APROBADO)
        llamadas = []

        def post(payload):
            llamadas.append(payload)
            if len(llamadas) == 1:
                # Mientras el primer POST espera a SIIS, entra otro request (doble clic,
                # masivo, reenviar_siis_pendientes) sobre el mismo caso.
                enviar_beneficiario_a_siis(Formulario.objects.get(pk=caso.pk), self.user)
            return OK

        with patch("programas.services.siis_envio.cargar_beneficiario", side_effect=post):
            enviar_beneficiario_a_siis(caso, self.user)
        self.assertEqual(len(llamadas), 2)
        self.assertEqual(caso.envios_sis.filter(estado=EnvioSIIS.Estado.ENVIADO).count(), 2)

    @patch("programas.services.siis_envio.armar_payload", return_value=PAYLOAD)
    def test_comando_reenviar_ignora_corrida_viva(self, _armar):
        caso = self._caso(Formulario.Estado.APROBADO)
        EnvioSIIS.objects.create(formulario=caso, estado=EnvioSIIS.Estado.ERROR, documento="20301234")
        CorridaSiis.objects.create(programa=self.programa, total_pedido=10, latido=timezone.now())
        self.assertIsNotNone(CorridaSiis.en_curso())
        with patch("programas.services.siis_envio.cargar_beneficiario", return_value=OK) as cargar:
            call_command("reenviar_siis_pendientes", stdout=StringIO())
        self.assertEqual(cargar.call_count, 1)

    @patch("programas.services.siis_envio.armar_payload", return_value=PAYLOAD)
    def test_mismo_dni_en_otro_caso_se_informa_otra_vez(self, _armar):
        a = self._caso(Formulario.Estado.APROBADO)
        b = self._caso(Formulario.Estado.APROBADO)
        with patch("programas.services.siis_envio.cargar_beneficiario", return_value=OK) as cargar:
            enviar_beneficiario_a_siis(a, self.user)
            enviar_beneficiario_a_siis(b, self.user)
        self.assertEqual(cargar.call_count, 2)


class ResultadoAmbiguoTests(_BaseProcesoTest):
    """SIIS-02: un ReadTimeout (POST ya entregado) queda ERROR reintentable y el masivo lo retoma."""

    def test_read_timeout_es_error_reintentable_y_vuelve_a_candidatos(self):
        with (
            patch.object(siis_mod.SiisAPIClient, "_token", return_value="t"),
            patch.object(siis_mod.sesion, "post", side_effect=requests.ReadTimeout("read")),
        ):
            r = siis_mod.cargar_beneficiario({"x": 1})
        self.assertTrue(r["reintentable"])
        self.assertEqual(r["codigo"], "ERROR_TECNICO")
        caso = self._caso(Formulario.Estado.APROBADO)
        EnvioSIIS.objects.create(formulario=caso, estado=EnvioSIIS.Estado.ERROR, documento="20301234")
        self.assertIn(caso.pk, proceso_masivo.ids_de(proceso_masivo.candidatos(programa=self.programa)))


class EstadoViejoEnMasivoTests(_BaseProcesoTest):
    """SIIS-04 (A1-04): el masivo decide con el estado hidratado."""

    @patch("programas.services.siis_envio.armar_payload", return_value=PAYLOAD)
    def test_caso_dado_de_baja_despues_de_hidratar_se_informa(self, _armar):
        caso = self._caso(Formulario.Estado.APROBADO)
        hidratado = proceso_masivo.hidratar([caso.pk])[0]
        Formulario.objects.filter(pk=caso.pk).update(estado=Formulario.Estado.BAJA)
        val = ValidacionSIS(estado=ValidacionSIS.Estado.OK)
        with (
            patch("programas.services.proceso_masivo.validar_formulario_en_siis", return_value=val),
            patch("programas.services.siis_envio.cargar_beneficiario", return_value=OK) as cargar,
        ):
            proceso_masivo.procesar_caso(hidratado, self.user, None, proceso_masivo.Cuenta())
        self.assertEqual(cargar.call_count, 1)


class LatidoTests(_BaseProcesoTest):
    """SIIS-03: el latido no se escribe durante la selección y la corrida viva se da por muerta."""

    def test_sin_latido_durante_elegir_completos(self):
        corrida = CorridaSiis.objects.create(programa=self.programa, total_pedido=5)
        visto = {}

        def elegir(casos, catalogos, total, cuenta):
            visto["latido"] = CorridaSiis.objects.get(pk=corrida.pk).latido
            return [], {}

        with patch("programas.services.proceso_masivo.elegir_completos", side_effect=elegir):
            proceso_masivo.correr(corrida, catalogos=MagicMock())
        self.assertIsNone(visto["latido"])

    def test_corrida_viva_sin_latido_2min_permite_otra(self):
        viva = CorridaSiis.objects.create(programa=self.programa, total_pedido=5)
        CorridaSiis.objects.filter(pk=viva.pk).update(creado=timezone.now() - timedelta(minutes=3))
        self.assertIsNone(CorridaSiis.en_curso())
        otra = proceso_masivo.crear_corrida(programa=self.programa, solicitada_por=self.user, total_pedido=5)
        self.assertIsNotNone(otra)
        self.assertEqual(CorridaSiis.objects.filter(estado=CorridaSiis.Estado.EN_CURSO).count(), 2)


class AprobarPisaRechazoTests(_BaseProcesoTest):
    """BEC-01 (A1-06): aprobar relee sin lock de fila y guarda el objeto en memoria."""

    def test_rechazo_confirmado_tras_relectura_se_pisa(self):
        caso = self._caso()
        ValidacionSIS.objects.create(
            formulario=caso, estado=ValidacionSIS.Estado.OK, id_programa=79, documento="20301234"
        )
        caso.validado_renaper = True
        caso.save(update_fields=["validado_renaper"])
        self.programa.siis_programa_id = 79
        self.programa.save()

        def stats(segmento):
            Formulario.objects.filter(pk=caso.pk).update(estado=Formulario.Estado.RECHAZADO)
            return {"cupo_maximo": 10, "cupo_ocupado": 0, "cupo_disponible": 10}

        with patch("programas.services.cupo.get_cupo_stats", side_effect=stats):
            resultado = aprobar_o_poner_en_espera(Formulario.objects.get(pk=caso.pk), self.user)
        self.assertEqual(resultado, "aprobado")
        self.assertEqual(Formulario.objects.get(pk=caso.pk).estado, Formulario.Estado.APROBADO)


class EsperaDobleTests(_BaseProcesoTest):
    """BEC-02 (A1-17): el chequeo de «ya en espera» va antes del lock."""

    def test_segundo_alta_espera_bajo_lock_duplica_fila(self):
        caso = self._caso()
        falso = MagicMock()

        def get(pk):
            # T1 commitea su fila mientras T2 esperaba el lock.
            ListaEspera.objects.create(formulario=caso, segmento=self.segmento, posicion=1)

        falso.objects.select_for_update.return_value.get.side_effect = get
        with patch("programas.services.cupo.Segmento", falso):
            agregar_a_lista_espera(caso, self.segmento, self.user)
        self.assertEqual(ListaEspera.objects.filter(formulario=caso, promovido=False).count(), 2)


class SyncCatalogoVacioTests(_BaseProcesoTest):
    """SIIS-06 (A2-04)."""

    def test_catalogo_vacio_bloquea_todos(self):
        from programas.services.siis_sync import sincronizar_estado_programas

        ProgramaSiis.objects.filter(pk=self.programa.pk).update(siis_programa_estado="ACTIVO")
        with patch("programas.services.siis_sync.listar_programas_todos", return_value=[]):
            sincronizar_estado_programas()
        self.programa.refresh_from_db()
        self.assertEqual(self.programa.siis_programa_estado, "DESCONOCIDO")
        self.assertIsNotNone(self.programa.pausa_efectiva)


class CompatibilidadBodyListaTests(_BaseProcesoTest):
    """A2-11."""

    def test_body_lista_revienta(self):
        resp = MagicMock(status_code=200)
        resp.json.return_value = ["OK"]
        with (
            patch.object(siis_mod.SiisAPIClient, "_token", return_value="t"),
            patch.object(siis_mod.sesion, "post", return_value=resp),
        ):
            with self.assertRaises(AttributeError):
                siis_mod.validar_compatibilidad("1", 79)


class PersonasAplanadoTests(_BaseProcesoTest):
    """A2-09."""

    def test_nombre_sale_de_objeto_anidado(self):
        from programas.services.personas import normalizar_persona

        r = normalizar_persona(
            {"data": {"domicilio": {"localidad": {"nombre": "Resistencia"}}, "nombres": "Ana", "apellido": "P"}}, "1"
        )
        self.assertEqual(r["nombre"], "Resistencia")


class ApoderadoTests(_BaseProcesoTest):
    """A2-13."""

    def test_apoderado_menor_y_mismo_dni_no_son_faltantes(self):
        from programas.services.siis_envio import _apoderado

        caso = self._caso()
        caso.apoderado_dni = "20301234"
        caso.apoderado_nombre = "X"
        caso.apoderado_apellido = "Y"
        caso.apoderado_genero = "F"
        caso.apoderado_fecha_nacimiento = date.today() - timedelta(days=365 * 10)
        faltantes = {}
        _apoderado(caso, faltantes)
        self.assertEqual(faltantes, {})
