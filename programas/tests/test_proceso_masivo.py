"""Proceso masivo a SIIS: registro de la corrida, servicio y pantalla."""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from programas.models import CorridaSiis, ProgramaSiis


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
