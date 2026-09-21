"""Proceso masivo a SIIS: registro de la corrida, servicio y pantalla."""

from datetime import date, timedelta
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.rbac import CATALOGO
from legajos.models import Ciudadano
from programas.models import (
    Convocatoria,
    CorridaSiis,
    EnvioSIIS,
    Formulario,
    ProgramaSiis,
    Relevamiento,
    Segmento,
    ValidacionSIS,
)
from programas.services import proceso_masivo
from programas.services.siis_envio import CatalogoNoDisponible


class CorridaSiisTests(TestCase):
    def setUp(self):
        self.programa = ProgramaSiis.objects.create(nombre="Ñachec", siis_programa_id=79)

    def _corrida(self, **kwargs):
        kwargs.setdefault("total_pedido", 1000)
        return CorridaSiis.objects.create(programa=self.programa, **kwargs)

    def test_una_corrida_recien_creada_no_esta_interrumpida(self):
        corrida = self._corrida(latido=timezone.now())
        self.assertFalse(corrida.interrumpida)

    def test_el_latido_viejo_la_marca_interrumpida(self):
        """Nadie escribe «me morí»: la interrupción se deduce del latido."""
        corrida = self._corrida(latido=timezone.now() - timedelta(minutes=5))
        self.assertTrue(corrida.interrumpida)

    def test_una_corrida_terminada_nunca_esta_interrumpida(self):
        corrida = self._corrida(estado=CorridaSiis.Estado.TERMINADA, latido=timezone.now() - timedelta(hours=3))
        self.assertFalse(corrida.interrumpida)

    def test_sin_latido_se_mide_desde_que_se_creo(self):
        corrida = self._corrida()
        self.assertFalse(corrida.interrumpida)

    def test_en_curso_devuelve_la_corrida_viva(self):
        corrida = self._corrida(latido=timezone.now())
        self.assertEqual(CorridaSiis.en_curso(), corrida)

    def test_en_curso_ignora_una_interrumpida(self):
        """Un pod muerto hace diez minutos no puede dejar el sistema trabado."""
        self._corrida(latido=timezone.now() - timedelta(minutes=30))
        self.assertIsNone(CorridaSiis.en_curso())

    def test_salteados_es_la_diferencia_entre_mirados_y_elegidos(self):
        corrida = self._corrida(mirados=1600, elegidos=1000)
        self.assertEqual(corrida.salteados, 600)

    def test_el_progreso_no_se_pasa_de_cien(self):
        corrida = self._corrida(total_pedido=10, elegidos=12)
        self.assertEqual(corrida.progreso, 100)
        self.assertEqual(self._corrida(total_pedido=10, elegidos=3).progreso, 30)


class _BaseProcesoTest(TestCase):
    def setUp(self):
        call_command("seed_becas", stdout=StringIO())
        self.programa = ProgramaSiis.objects.create(nombre="Ñachec", siis_programa_id=79, siis_funcion_id=4)
        self.segmento = Segmento.objects.create(nombre="Seg", cupo_maximo=100, programa=self.programa)
        self.convocatoria = Convocatoria.objects.create(
            nombre="Conv",
            segmento=self.segmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        self.user = User.objects.create_user("coord_masivo", password="x")
        self.relevamiento = Relevamiento.objects.create(
            convocatoria=self.convocatoria,
            territorial=self.user,
            fecha_asignada=date(2026, 6, 1),
            zona="A",
        )
        self.ciudadano = Ciudadano.objects.create(
            dni="20301234", nombre="Juan", apellido="Perez", fecha_nacimiento=date(1995, 6, 15), genero="M"
        )

    def _caso(self, estado=Formulario.Estado.ENVIADO):
        return Formulario.objects.create(relevamiento=self.relevamiento, ciudadano=self.ciudadano, estado=estado)


class CandidatosTests(_BaseProcesoTest):
    def test_toma_los_enviados_y_los_aprobados(self):
        enviado = self._caso()
        aprobado = self._caso(Formulario.Estado.APROBADO)
        self._caso(Formulario.Estado.RECHAZADO)
        encontrados = set(proceso_masivo.candidatos(programa=self.programa).values_list("pk", flat=True))
        self.assertEqual(encontrados, {enviado.pk, aprobado.pk})

    def test_saltea_el_que_ya_tiene_alta(self):
        caso = self._caso(Formulario.Estado.APROBADO)
        EnvioSIIS.objects.create(formulario=caso, estado=EnvioSIIS.Estado.ENVIADO, documento="1")
        self.assertFalse(proceso_masivo.candidatos(programa=self.programa).exists())

    def test_incluye_al_que_nunca_se_mando(self):
        """Sin envio el ultimo estado es NULL, y un exclude lo descartaria."""
        caso = self._caso(Formulario.Estado.APROBADO)
        self.assertIn(caso.pk, proceso_masivo.candidatos(programa=self.programa).values_list("pk", flat=True))

    def test_saltea_el_duplicado_sin_resolver(self):
        caso = self._caso()
        caso.conflicto_duplicado = True
        caso.conflicto_resuelto = False
        caso.save(update_fields=["conflicto_duplicado", "conflicto_resuelto"])
        self.assertFalse(proceso_masivo.candidatos(programa=self.programa).exists())


class ElegirCompletosTests(_BaseProcesoTest):
    def test_junta_el_total_salteando_los_incompletos(self):
        """El total cuenta casos que se mandan, no casos que se miran."""
        casos = [self._caso() for _ in range(3)]
        cuenta = proceso_masivo.Cuenta()
        with patch("programas.services.proceso_masivo.armar_payload") as armar:
            armar.side_effect = [({}, {"nro_actual": "falta"}), ({}, {}), ({}, {})]
            elegidos, descartados = proceso_masivo.elegir_completos(casos, None, 2, cuenta)
        self.assertEqual([c.pk for c in elegidos], [casos[1].pk, casos[2].pk])
        self.assertEqual(descartados, {"nro_actual": 1})
        self.assertEqual(cuenta.mirados, 3)
        self.assertEqual(cuenta.elegidos, 2)

    def test_si_no_alcanzan_devuelve_los_que_hay(self):
        casos = [self._caso()]
        cuenta = proceso_masivo.Cuenta()
        with patch("programas.services.proceso_masivo.armar_payload") as armar:
            armar.return_value = ({}, {})
            elegidos, _ = proceso_masivo.elegir_completos(casos, None, 50, cuenta)
        self.assertEqual(len(elegidos), 1)


class CorrerTests(_BaseProcesoTest):
    def setUp(self):
        super().setUp()
        self.parches = {
            nombre: patch(f"programas.services.proceso_masivo.{nombre}").start()
            for nombre in (
                "armar_payload",
                "validar_formulario_en_siis",
                "aprobar_o_poner_en_espera",
                "enviar_beneficiario_a_siis",
                "enviar_aviso_resolucion",
            )
        }
        self.addCleanup(patch.stopall)
        self.parches["armar_payload"].return_value = ({}, {})
        self.parches["validar_formulario_en_siis"].side_effect = lambda f, u: ValidacionSIS.objects.create(
            formulario=f, estado=ValidacionSIS.Estado.OK, documento="1", id_programa=79
        )
        self.parches["aprobar_o_poner_en_espera"].side_effect = lambda f, u: "aprobado"
        self.parches["enviar_beneficiario_a_siis"].side_effect = lambda f, u, **kw: EnvioSIIS.objects.create(
            formulario=f, estado=EnvioSIIS.Estado.ENVIADO, documento="1", siis_id=1
        )

    def _corrida(self, total=10):
        return CorridaSiis.objects.create(programa=self.programa, total_pedido=total)

    def test_termina_y_cuenta_las_altas(self):
        for _ in range(3):
            self._caso()
        corrida = proceso_masivo.correr(self._corrida(), lote=2)
        self.assertEqual(corrida.estado, CorridaSiis.Estado.TERMINADA)
        self.assertEqual(corrida.altas, 3)
        self.assertEqual(corrida.aprobados, 3)
        self.assertIsNotNone(corrida.finalizada)

    def test_escribe_el_latido_en_cada_lote(self):
        for _ in range(3):
            self._caso()
        corrida = proceso_masivo.correr(self._corrida(), lote=2)
        self.assertIsNotNone(corrida.latido)
        self.assertFalse(corrida.interrumpida)

    def test_frenar_corta_al_cerrar_el_lote(self):
        for _ in range(4):
            self._caso()
        corrida = self._corrida()

        def marcar(f, u, **kw):
            # Alguien aprieta Frenar mientras corre el primer lote.
            CorridaSiis.objects.filter(pk=corrida.pk).update(cancelacion_pedida=True)
            return EnvioSIIS.objects.create(formulario=f, estado=EnvioSIIS.Estado.ENVIADO, documento="1")

        self.parches["enviar_beneficiario_a_siis"].side_effect = marcar
        resultado = proceso_masivo.correr(corrida, lote=2)
        self.assertEqual(resultado.estado, CorridaSiis.Estado.CANCELADA)
        # Corta al cerrar el lote, no a mitad: procesó los 2 del primero.
        self.assertEqual(resultado.altas, 2)

    def test_se_detiene_tras_errores_tecnicos_seguidos(self):
        for _ in range(4):
            self._caso()
        self.parches["enviar_beneficiario_a_siis"].side_effect = lambda f, u, **kw: EnvioSIIS.objects.create(
            formulario=f, estado=EnvioSIIS.Estado.ERROR, documento="1", codigo_error="ERROR_TECNICO"
        )
        corrida = proceso_masivo.correr(self._corrida(), lote=10, max_errores=2)
        self.assertEqual(corrida.estado, CorridaSiis.Estado.DETENIDA)
        self.assertIn("SIIS", corrida.mensaje)

    def test_el_catalogo_caido_la_detiene_con_el_motivo(self):
        self._caso()
        self.parches["armar_payload"].side_effect = CatalogoNoDisponible("el servicio no responde")
        corrida = proceso_masivo.correr(self._corrida())
        self.assertEqual(corrida.estado, CorridaSiis.Estado.DETENIDA)
        self.assertIn("no responde", corrida.mensaje)

    def test_una_excepcion_no_prevista_queda_escrita(self):
        """Corre en un hilo: si escapara, nadie la veria."""
        self._caso()
        self.parches["validar_formulario_en_siis"].side_effect = RuntimeError("algo raro")
        corrida = proceso_masivo.correr(self._corrida())
        self.assertEqual(corrida.estado, CorridaSiis.Estado.DETENIDA)
        self.assertIn("algo raro", corrida.mensaje)

    def test_sin_candidatos_termina_igual(self):
        corrida = proceso_masivo.correr(self._corrida())
        self.assertEqual(corrida.estado, CorridaSiis.Estado.TERMINADA)
        self.assertEqual(corrida.altas, 0)

    def test_no_manda_correos_al_ciudadano(self):
        """Mil correos irretractables no van detras de un boton oculto."""
        self._caso()
        proceso_masivo.correr(self._corrida())
        self.parches["enviar_aviso_resolucion"].assert_not_called()


class LanzarTests(_BaseProcesoTest):
    def test_el_ejecutor_se_inyecta(self):
        """En los tests corre sincronico; sin eso serian una carrera."""
        corrida = CorridaSiis.objects.create(programa=self.programa, total_pedido=1)
        llamadas = []
        proceso_masivo.lanzar(corrida, ejecutor=llamadas.append)
        self.assertEqual(len(llamadas), 1)


class PantallaProcesoMasivoTests(_BaseProcesoTest):
    CAP = "becas.programa.proceso_masivo"

    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_superuser("admin_masivo", password="x")
        self.client.force_login(self.admin)

    def _url(self, nombre="proceso_masivo"):
        return reverse(f"becas:{nombre}", args=[self.programa.pk])

    def test_la_capacidad_esta_en_el_catalogo(self):
        codigos = [c for modulo in CATALOGO for c, _ in modulo["capacidades"]]
        self.assertIn(self.CAP, codigos)

    def test_la_pantalla_abre_y_muestra_los_pendientes(self):
        self._caso()
        resp = self.client.get(self._url())
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Proceso masivo")
        self.assertEqual(resp.context["pendientes"], 1)

    def test_sin_la_capacidad_no_entra(self):
        """Un usuario sin la capacidad no llega, aunque sepa la URL."""
        otro = User.objects.create_user("sin_capacidad", password="x")
        self.client.force_login(otro)
        resp = self.client.get(self._url())
        self.assertIn(resp.status_code, (302, 403))

    def test_no_se_enlaza_desde_ninguna_otra_pantalla(self):
        """«Secreta» es no listada: ninguna plantilla ajena apunta acá."""
        raiz = Path(__file__).resolve().parents[1] / "templates"
        propia = "proceso_masivo.html"
        con_referencia = sorted(
            ruta.name for ruta in raiz.rglob("*.html") if "proceso_masivo" in ruta.read_text(encoding="utf-8")
        )
        self.assertEqual(con_referencia, [propia])

    def test_lanzar_crea_la_corrida_y_no_espera(self):
        self._caso()
        with patch("programas.views.proceso_masivo.servicio.lanzar") as lanzar:
            resp = self.client.post(self._url("proceso_masivo_lanzar"), {"total_pedido": "25"})
        self.assertEqual(resp.status_code, 302)
        corrida = CorridaSiis.objects.get()
        self.assertEqual(corrida.total_pedido, 25)
        self.assertEqual(corrida.solicitada_por, self.admin)
        lanzar.assert_called_once()

    def test_no_deja_lanzar_dos_a_la_vez(self):
        CorridaSiis.objects.create(programa=self.programa, total_pedido=10, latido=timezone.now())
        with patch("programas.views.proceso_masivo.servicio.lanzar") as lanzar:
            self.client.post(self._url("proceso_masivo_lanzar"), {"total_pedido": "10"})
        self.assertEqual(CorridaSiis.objects.count(), 1)
        lanzar.assert_not_called()

    def test_una_interrumpida_no_bloquea(self):
        CorridaSiis.objects.create(
            programa=self.programa, total_pedido=10, latido=timezone.now() - timedelta(minutes=30)
        )
        with patch("programas.views.proceso_masivo.servicio.lanzar"):
            self.client.post(self._url("proceso_masivo_lanzar"), {"total_pedido": "10"})
        self.assertEqual(CorridaSiis.objects.count(), 2)

    def test_un_total_invalido_no_crea_nada(self):
        with patch("programas.views.proceso_masivo.servicio.lanzar"):
            self.client.post(self._url("proceso_masivo_lanzar"), {"total_pedido": "0"})
            self.client.post(self._url("proceso_masivo_lanzar"), {"total_pedido": "99999"})
            self.client.post(self._url("proceso_masivo_lanzar"), {"total_pedido": "abc"})
        self.assertFalse(CorridaSiis.objects.exists())

    def test_frenar_marca_la_corrida(self):
        corrida = CorridaSiis.objects.create(programa=self.programa, total_pedido=10, latido=timezone.now())
        resp = self.client.post(self._url("proceso_masivo_frenar"))
        self.assertEqual(resp.status_code, 302)
        corrida.refresh_from_db()
        self.assertTrue(corrida.cancelacion_pedida)
        # El estado lo cambia el proceso al cerrar el lote, no este request.
        self.assertEqual(corrida.estado, CorridaSiis.Estado.EN_CURSO)

    def test_frenar_sin_corrida_no_rompe(self):
        resp = self.client.post(self._url("proceso_masivo_frenar"))
        self.assertEqual(resp.status_code, 302)
