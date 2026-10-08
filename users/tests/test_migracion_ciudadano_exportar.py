"""Tests de la siembra de ``ciudadano.exportar`` — ``users/migrations/0028``.

**D-20, decidida por el PM el 08-oct-2026:** la capacidad se tilda sobre **todo rol
que tenga `ciudadano.ver`**, no solo sobre los que editan. Así el «Operador de
backoffice» —que ve el padrón y no da altas— conserva la exportación el día del
deploy, y la capacidad queda separada para poder quitársela rol por rol desde el ABM.
El criterio anterior (sembrar a quien tenía `ciudadano.editar`) le sacaba la
exportación a ese rol sin que nadie lo pidiera.
"""

import importlib

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from core import rbac
from core.tests.historico import estado_historico
from users.models import Capacidad

migracion = importlib.import_module("users.migrations.0028_sembrar_ciudadano_exportar")
# RED-17: los modelos **de entonces**, no los de hoy.
APPS_DE_ENTONCES = estado_historico("users", "0028_sembrar_ciudadano_exportar")

CODIGO = "ciudadano.exportar"


def _capacidades(grupo):
    return set(grupo.permissions.values_list("codename", flat=True))


def _rol(nombre, *codigos):
    grupo = Group.objects.create(name=nombre)
    ct = ContentType.objects.get_for_model(Capacidad)
    for codigo in codigos:
        permiso, _ = Permission.objects.get_or_create(
            content_type=ct, codename=rbac.codename_de(codigo), defaults={"name": codigo}
        )
        grupo.permissions.add(permiso)
    return grupo


class SembrarCiudadanoExportarTests(TestCase):
    def test_el_codename_esperado_sigue_en_el_catalogo(self):
        """Si alguien renombra la capacidad, la siembra queda sin efecto en silencio."""
        self.assertIn(CODIGO, rbac.codigos_de_capacidad())
        self.assertEqual(rbac.codename_de(CODIGO), migracion.CODENAME_NUEVA)
        self.assertEqual(rbac.codename_de("ciudadano.ver"), migracion.CODENAME_LECTURA)

    def test_la_recibe_todo_rol_que_ve_ciudadanos(self):
        edita = _rol("Gestión de Ciudadanos", "ciudadano.ver", "ciudadano.editar")
        solo_ve = _rol("Operador de backoffice", "ciudadano.ver")

        migracion.sembrar(APPS_DE_ENTONCES, None)

        self.assertIn(migracion.CODENAME_NUEVA, _capacidades(edita))
        self.assertIn(migracion.CODENAME_NUEVA, _capacidades(solo_ve))

    def test_un_rol_que_no_ve_ciudadanos_no_la_recibe(self):
        ajeno = _rol("Reportes", "reporte.ver")

        migracion.sembrar(APPS_DE_ENTONCES, None)

        self.assertNotIn(migracion.CODENAME_NUEVA, _capacidades(ajeno))

    def test_es_idempotente(self):
        grupo = _rol("Operador de backoffice", "ciudadano.ver")

        migracion.sembrar(APPS_DE_ENTONCES, None)
        migracion.sembrar(APPS_DE_ENTONCES, None)

        self.assertEqual(grupo.permissions.filter(codename=migracion.CODENAME_NUEVA).count(), 1)
        self.assertEqual(Permission.objects.filter(codename=migracion.CODENAME_NUEVA).count(), 1)

    def test_sin_roles_no_falla(self):
        """Base nueva: los roles los crea `seed_rbac` después de migrar."""
        migracion.sembrar(APPS_DE_ENTONCES, None)  # no debe levantar

    def test_la_reversa_la_quita_de_todos(self):
        grupo = _rol("Operador de backoffice", "ciudadano.ver")
        migracion.sembrar(APPS_DE_ENTONCES, None)

        migracion.quitar(APPS_DE_ENTONCES, None)

        self.assertNotIn(migracion.CODENAME_NUEVA, _capacidades(grupo))
