"""Contratos de la migración de datos de Dispositivos y Merenderos (#173)."""

from importlib import import_module

from django.apps import apps
from django.test import TestCase

from legajos.models import Ciudadano
from programas.models import InscripcionPrograma, Programa


class ProgramasDispositivosDataMigrationTests(TestCase):
    migration_module = "programas.migrations.0012_crear_programas_dispositivos_merenderos"

    def test_crea_los_dos_programas_sin_tocar_becas_ni_membresias(self):
        Programa.objects.filter(codigo__in=["DISPOSITIVOS", "MERENDEROS"]).delete()
        becas = Programa.objects.create(codigo="BECAS-EXISTENTE", nombre="Becas existente")
        ciudadano = Ciudadano.objects.create(dni="30111222", nombre="Ana", apellido="Demo")
        membresia = InscripcionPrograma.objects.create(ciudadano=ciudadano, programa=becas)

        migration = import_module(self.migration_module)
        migration.crear_programas(apps, schema_editor=None)

        programas = Programa.objects.filter(codigo__in=["DISPOSITIVOS", "MERENDEROS"])
        self.assertEqual(programas.count(), 2)
        self.assertEqual(
            set(programas.values_list("codigo", "tipo")),
            {("DISPOSITIVOS", "DISPOSITIVOS"), ("MERENDEROS", "MERENDEROS")},
        )
        self.assertTrue(Programa.objects.filter(pk=becas.pk).exists())
        self.assertTrue(InscripcionPrograma.objects.filter(pk=membresia.pk).exists())

    def test_es_idempotente(self):
        migration = import_module(self.migration_module)

        migration.crear_programas(apps, schema_editor=None)
        migration.crear_programas(apps, schema_editor=None)

        self.assertEqual(Programa.objects.filter(codigo="DISPOSITIVOS").count(), 1)
        self.assertEqual(Programa.objects.filter(codigo="MERENDEROS").count(), 1)
