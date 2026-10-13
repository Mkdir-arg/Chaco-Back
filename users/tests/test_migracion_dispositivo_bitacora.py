"""Siembra de ``dispositivo.bitacora`` — ``users/migrations/0036`` (MVP v2, etapa 3 · #695).

La capacidad nueva se tilda sobre **todo rol que ya tenga `dispositivo.admitir`**: quien
opera el día a día de la institución sigue pudiendo cargar la bitácora del turno el día
del deploy, y de ahí en adelante se da o se quita rol por rol desde el ABM.
"""

import importlib

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from core import rbac
from core.tests.historico import estado_historico
from users.models import Capacidad

migracion = importlib.import_module("users.migrations.0036_capacidad_dispositivo_bitacora")
# RED-17: los modelos **de entonces**, no los de hoy.
APPS_DE_ENTONCES = estado_historico("users", "0036_capacidad_dispositivo_bitacora")

CODIGO = "dispositivo.bitacora"


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


class SembrarDispositivoBitacoraTests(TestCase):
    def test_los_codenames_siguen_en_el_catalogo(self):
        """Si alguien renombra cualquiera de las dos, la siembra queda sin efecto en silencio."""

        self.assertIn(CODIGO, rbac.codigos_de_capacidad())
        self.assertEqual(rbac.codename_de(CODIGO), migracion.CODENAME_NUEVA)
        self.assertEqual(rbac.codename_de("dispositivo.admitir"), migracion.CODENAME_OPERATIVA)

    def test_la_recibe_todo_rol_que_admite(self):
        operador = _rol("Operador de turno", "dispositivo.ver", "dispositivo.admitir")

        migracion.sembrar(APPS_DE_ENTONCES, None)

        self.assertIn(migracion.CODENAME_NUEVA, _capacidades(operador))

    def test_un_rol_que_solo_ve_dispositivos_no_la_recibe(self):
        consulta = _rol("Consulta de dispositivos", "dispositivo.ver", "dispositivo.editar")

        migracion.sembrar(APPS_DE_ENTONCES, None)

        self.assertNotIn(migracion.CODENAME_NUEVA, _capacidades(consulta))

    def test_es_idempotente(self):
        grupo = _rol("Operador de turno", "dispositivo.admitir")

        migracion.sembrar(APPS_DE_ENTONCES, None)
        migracion.sembrar(APPS_DE_ENTONCES, None)

        self.assertEqual(grupo.permissions.filter(codename=migracion.CODENAME_NUEVA).count(), 1)
        self.assertEqual(Permission.objects.filter(codename=migracion.CODENAME_NUEVA).count(), 1)

    def test_la_reversa_la_quita_de_todos(self):
        grupo = _rol("Operador de turno", "dispositivo.admitir")
        migracion.sembrar(APPS_DE_ENTONCES, None)

        migracion.quitar(APPS_DE_ENTONCES, None)

        self.assertNotIn(migracion.CODENAME_NUEVA, _capacidades(grupo))
        self.assertIn(migracion.CODENAME_OPERATIVA, _capacidades(grupo))
