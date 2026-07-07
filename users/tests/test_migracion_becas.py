"""Tests de la migración de datos que remapea los permisos viejos de Becas
(granularización, #79) a las capacidades finas nuevas — ver
``users/migrations/0007_remapear_permisos_becas.py``.

Simula el escenario real: un ``Group`` (rol, semillado o custom) con alguna de
las 3 capacidades viejas (``becas_configurar``/``becas_relevamientos``/
``becas_revisar``) tildada ANTES de que el catálogo nuevo exista. La migración
debe agregarle las capacidades finas equivalentes antes de borrar la vieja,
para que ningún rol pierda acceso a Becas en silencio.
"""

import importlib

from django.apps import apps
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from users.models import Capacidad

remapeo = importlib.import_module("users.migrations.0007_remapear_permisos_becas")


class RemapeoPermisosBecasTests(TestCase):
    def setUp(self):
        self.ct = ContentType.objects.get_for_model(Capacidad)

    def _crear_permiso_viejo(self, codename):
        # get_or_create: "becas_campo" sigue vigente en el catálogo y ya lo
        # crea el post_migrate de la app de test; los codenames viejos
        # (becas_configurar/relevamientos/revisar) en cambio no existen.
        perm, _ = Permission.objects.get_or_create(content_type=self.ct, codename=codename, defaults={"name": codename})
        return perm

    def test_remapea_becas_configurar_a_capacidades_finas(self):
        perm_viejo = self._crear_permiso_viejo("becas_configurar")
        grupo = Group.objects.create(name="Rol custom con becas_configurar")
        grupo.permissions.add(perm_viejo)

        remapeo.remapear_permisos_becas(apps, None)

        codenames = set(grupo.permissions.values_list("codename", flat=True))
        self.assertIn("becas_programa_administrar", codenames)
        self.assertIn("becas_segmento_ver", codenames)
        self.assertIn("becas_segmento_crear", codenames)
        self.assertIn("becas_segmento_editar", codenames)
        self.assertIn("becas_coordinador_editar", codenames)
        self.assertNotIn("becas_configurar", codenames)
        self.assertFalse(Permission.objects.filter(content_type=self.ct, codename="becas_configurar").exists())

    def test_remapea_becas_relevamientos_y_becas_revisar(self):
        perm_relev = self._crear_permiso_viejo("becas_relevamientos")
        perm_revisar = self._crear_permiso_viejo("becas_revisar")
        grupo = Group.objects.create(name="Rol custom coordinador")
        grupo.permissions.add(perm_relev, perm_revisar)

        remapeo.remapear_permisos_becas(apps, None)

        codenames = set(grupo.permissions.values_list("codename", flat=True))
        self.assertIn("becas_convocatoria_ver", codenames)
        self.assertIn("becas_relevamiento_editar", codenames)
        self.assertIn("becas_revision_ver", codenames)
        self.assertIn("becas_cupo_ver", codenames)
        self.assertIn("becas_beneficiario_editar", codenames)
        self.assertNotIn("becas_relevamientos", codenames)
        self.assertNotIn("becas_revisar", codenames)

    def test_permiso_viejo_sin_grupos_se_borra_sin_error(self):
        self._crear_permiso_viejo("becas_configurar")
        remapeo.remapear_permisos_becas(apps, None)
        self.assertFalse(Permission.objects.filter(content_type=self.ct, codename="becas_configurar").exists())

    def test_es_idempotente(self):
        perm_viejo = self._crear_permiso_viejo("becas_configurar")
        grupo = Group.objects.create(name="Rol custom")
        grupo.permissions.add(perm_viejo)

        remapeo.remapear_permisos_becas(apps, None)
        remapeo.remapear_permisos_becas(apps, None)  # segunda pasada: no debe fallar ni duplicar

        codenames = list(grupo.permissions.values_list("codename", flat=True))
        self.assertEqual(len(codenames), len(set(codenames)))

    def test_becas_campo_no_se_toca(self):
        perm_campo = self._crear_permiso_viejo("becas_campo")
        grupo = Group.objects.create(name="Territorial custom")
        grupo.permissions.add(perm_campo)

        remapeo.remapear_permisos_becas(apps, None)

        self.assertTrue(Permission.objects.filter(content_type=self.ct, codename="becas_campo").exists())
        self.assertIn("becas_campo", grupo.permissions.values_list("codename", flat=True))
