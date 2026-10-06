"""Tests de la migración de datos que le otorga ``becas.relevamiento.publico``
al rol protegido ``Administrador`` — ver
``users/migrations/0025_administrador_relevamiento_publico.py``.

El rol protegido no se puede editar desde la pantalla de Roles, así que la
migración es el único camino. Se verifica que otorgue, que sea idempotente, que
no toque otros roles y que no explote en una base sin roles creados.
"""

import importlib

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from core import rbac
from core.tests.historico import estado_historico
from users.models import Capacidad

migracion = importlib.import_module("users.migrations.0025_administrador_relevamiento_publico")
# RED-17: los modelos **de entonces**, no los de hoy. Con `django.apps.apps` la prueba
# no habría notado que la función usa un campo agregado después de esta migración.
APPS_DE_ENTONCES = estado_historico("users", "0025_administrador_relevamiento_publico")

CODIGO = "becas.relevamiento.publico"


class OtorgarPublicoAlAdministradorTests(TestCase):
    def setUp(self):
        self.ct = ContentType.objects.get_for_model(Capacidad)

    def _capacidades(self, grupo):
        return set(grupo.permissions.values_list("codename", flat=True))

    def test_el_codename_esperado_sigue_en_el_catalogo(self):
        # Si alguien renombra la capacidad, la migración quedaría sin efecto en
        # silencio: este assert lo hace ruidoso.
        self.assertIn(CODIGO, rbac.codigos_de_capacidad())
        self.assertEqual(rbac.codename_de(CODIGO), migracion.CODENAME)

    def test_otorga_la_capacidad_al_rol_protegido(self):
        grupo = Group.objects.create(name=migracion.ROL)

        migracion.otorgar_al_administrador(APPS_DE_ENTONCES, None)

        self.assertIn(migracion.CODENAME, self._capacidades(grupo))

    def test_es_idempotente(self):
        grupo = Group.objects.create(name=migracion.ROL)

        migracion.otorgar_al_administrador(APPS_DE_ENTONCES, None)
        migracion.otorgar_al_administrador(APPS_DE_ENTONCES, None)

        self.assertEqual(
            list(grupo.permissions.filter(codename=migracion.CODENAME).values_list("codename", flat=True)),
            [migracion.CODENAME],
        )
        self.assertEqual(Permission.objects.filter(codename=migracion.CODENAME).count(), 1)

    def test_no_toca_otros_roles(self):
        Group.objects.create(name=migracion.ROL)
        otro = Group.objects.create(name="Becas — Administrador")

        migracion.otorgar_al_administrador(APPS_DE_ENTONCES, None)

        self.assertNotIn(migracion.CODENAME, self._capacidades(otro))

    def test_sin_rol_administrador_no_falla(self):
        # Base nueva: los roles los crea `seed_rbac` después de migrar.
        self.assertFalse(Group.objects.filter(name=migracion.ROL).exists())

        migracion.otorgar_al_administrador(APPS_DE_ENTONCES, None)  # no debe levantar

    def test_revertir_no_quita_la_capacidad(self):
        grupo = Group.objects.create(name=migracion.ROL)
        migracion.otorgar_al_administrador(APPS_DE_ENTONCES, None)

        migracion.revertir(APPS_DE_ENTONCES, None)

        self.assertIn(migracion.CODENAME, self._capacidades(grupo))
