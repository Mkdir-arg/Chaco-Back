"""Contratos de la migración de datos de Dispositivos y Merenderos (#173).

Con los modelos de hoy y no con los de la 0012 (RED-17 (2)): la suite arma el esquema
desde los modelos actuales (`DJANGO_SYNCDB_PROJECT_APPS`), así que un `Programa` de la
época de esta migración escribiría un `INSERT` sin `umbral_disponibilidad_verde`, que
hoy es `NOT NULL`. Que la migración nombre modelos que existían en su momento se
verifica sin base en ``core/tests/test_migraciones_estado_historico.py``.
"""

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

    def test_falla_si_un_codigo_objetivo_tiene_datos_incompatibles(self):
        Programa.objects.filter(codigo="DISPOSITIVOS").delete()
        Programa.objects.create(
            codigo="DISPOSITIVOS",
            nombre="Dispositivos",
            tipo=Programa.TipoPrograma.BECAS,
            naturaleza=Programa.Naturaleza.PERSISTENTE,
            estado=Programa.Estado.ACTIVO,
        )
        migration = import_module(self.migration_module)

        with self.assertRaisesMessage(RuntimeError, 'Programa(codigo="DISPOSITIVOS")'):
            migration.crear_programas(apps, schema_editor=None)


class RetirarMerenderosDataMigrationTests(TestCase):
    """`0115`: la fila `Programa(MERENDEROS)` y los roles atados a ella se borran sin tocar el resto."""

    migration_module = "programas.migrations.0115_retirar_merenderos"

    def _rol(self, nombre, programa):
        from django.contrib.auth.models import Group

        from users.models import CATEGORIA_PROGRAMA, RolMeta

        grupo = Group.objects.create(name=nombre)
        RolMeta.objects.create(grupo=grupo, categoria=CATEGORIA_PROGRAMA, programa=programa)
        return grupo

    def test_borra_el_programa_sus_roles_y_su_inscripcion_sin_tocar_los_demas(self):
        from django.contrib.auth.models import Group

        merenderos = Programa.objects.create(codigo="MERENDEROS", nombre="Merenderos", tipo="MERENDEROS")
        becas = Programa.objects.create(codigo="BECAS-X", nombre="Becas X")
        rol_merenderos = self._rol("Rol Merenderos", merenderos)
        rol_becas = self._rol("Rol Becas X", becas)
        ciudadano = Ciudadano.objects.create(dni="30111222", nombre="Ana", apellido="Demo")
        InscripcionPrograma.objects.create(ciudadano=ciudadano, programa=merenderos)
        membresia = InscripcionPrograma.objects.create(ciudadano=ciudadano, programa=becas)

        migration = import_module(self.migration_module)
        migration.borrar_programa(apps, schema_editor=None)

        self.assertFalse(Programa.objects.filter(codigo="MERENDEROS").exists())
        self.assertFalse(Group.objects.filter(pk=rol_merenderos.pk).exists())
        self.assertTrue(Group.objects.filter(pk=rol_becas.pk).exists())
        self.assertTrue(Programa.objects.filter(pk=becas.pk).exists())
        self.assertTrue(InscripcionPrograma.objects.filter(pk=membresia.pk).exists())

    def test_es_idempotente_y_la_reversa_recrea_la_fila(self):
        migration = import_module(self.migration_module)

        migration.borrar_programa(apps, schema_editor=None)
        migration.borrar_programa(apps, schema_editor=None)
        migration.restituir_programa(apps, schema_editor=None)
        migration.restituir_programa(apps, schema_editor=None)

        self.assertEqual(Programa.objects.filter(codigo="MERENDEROS").count(), 1)
