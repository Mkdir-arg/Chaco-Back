"""Proceso masivo a SIIS: registro de la corrida, servicio y pantalla."""

from datetime import date, timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from legajos.models import Ciudadano
from programas.models import (
    Convocatoria,
    CorridaSiis,
    EnvioSIIS,
    Formulario,
    ProgramaSiis,
    Relevamiento,
    Segmento,
)
from programas.services import proceso_masivo


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
