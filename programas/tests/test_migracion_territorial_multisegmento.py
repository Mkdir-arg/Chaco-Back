"""La reversa de la 0103 deja una asignación por territorial (la de menor pk).

El job de ida y vuelta siembra una sola fila por territorial y no ejercita este
paso: sin él, ``migrate programas 0102`` muere al recrear el UNIQUE del OneToOne con
una base que ya tiene territoriales de varios segmentos.

Se llama a la función con el registro **histórico** de la propia migración
(``core.tests.historico``) y las filas se arman con los modelos reales: la tabla es la
misma.
"""

from importlib import import_module

from django.contrib.auth.models import User
from django.test import TestCase

from core.tests.historico import estado_historico
from programas.models import AsignacionTerritorial, Segmento

NOMBRE = "0103_asignacion_territorial_multisegmento"
MIGRACION = import_module(f"programas.migrations.{NOMBRE}")


class DedupReversaTests(TestCase):
    def setUp(self):
        self.seg = [Segmento.objects.create(nombre=f"Seg {i}", cupo_maximo=5) for i in range(3)]
        self.t1 = User.objects.create_user("t1", password="x")
        self.t2 = User.objects.create_user("t2", password="x")

    def _reversa(self):
        MIGRACION.dedup_reversa(estado_historico("programas", NOMBRE, al_final=True), None)

    def test_deja_la_asignacion_de_menor_pk_de_cada_territorial(self):
        a1 = AsignacionTerritorial.objects.create(segmento=self.seg[0], territorial=self.t1)
        AsignacionTerritorial.objects.create(segmento=self.seg[1], territorial=self.t1)
        AsignacionTerritorial.objects.create(segmento=self.seg[2], territorial=self.t1)
        solo = AsignacionTerritorial.objects.create(segmento=self.seg[1], territorial=self.t2)

        self._reversa()

        self.assertEqual(
            sorted(AsignacionTerritorial.objects.values_list("pk", flat=True)),
            sorted([a1.pk, solo.pk]),
        )
        self.assertEqual(AsignacionTerritorial.objects.get(territorial=self.t1).segmento, self.seg[0])

    def test_es_idempotente(self):
        AsignacionTerritorial.objects.create(segmento=self.seg[0], territorial=self.t1)
        AsignacionTerritorial.objects.create(segmento=self.seg[1], territorial=self.t1)
        self._reversa()
        self._reversa()
        self.assertEqual(AsignacionTerritorial.objects.filter(territorial=self.t1).count(), 1)

    def test_sin_duplicados_no_toca_nada(self):
        AsignacionTerritorial.objects.create(segmento=self.seg[0], territorial=self.t1)
        AsignacionTerritorial.objects.create(segmento=self.seg[1], territorial=self.t2)
        self._reversa()
        self.assertEqual(AsignacionTerritorial.objects.count(), 2)
