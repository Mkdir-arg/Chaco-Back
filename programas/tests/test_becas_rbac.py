"""Tests de los roles RBAC de Becas y el scoping por segmento (#79)."""

from io import StringIO

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase

from core import rbac
from programas.management.commands.seed_becas import (
    ROL_ADMIN,
    ROL_COORDINADOR,
    ROL_TERRITORIAL,
)
from programas.models import AsignacionCoordinador, Programa, Segmento
from programas.services.autorizacion import (
    es_admin_becas,
    es_coordinador_becas,
    puede_gestionar_segmento,
    segmentos_visibles,
)


class RbacBecasTests(TestCase):
    def setUp(self):
        call_command("seed_becas", stdout=StringIO())
        self.becas = Programa.objects.get(codigo="BECAS")
        self.seg_a = Segmento.objects.create(nombre="Segmento A", cupo_maximo=100)
        self.seg_b = Segmento.objects.create(nombre="Segmento B", cupo_maximo=100)

        self.g_admin = Group.objects.get(name=ROL_ADMIN)
        self.g_coord = Group.objects.get(name=ROL_COORDINADOR)
        self.g_terri = Group.objects.get(name=ROL_TERRITORIAL)

        self.admin = User.objects.create_user("admin_becas")
        self.admin.groups.add(self.g_admin)

        self.coord = User.objects.create_user("coord_becas")
        self.coord.groups.add(self.g_coord)
        AsignacionCoordinador.objects.create(segmento=self.seg_a, coordinador=self.coord)

        self.coord_sin = User.objects.create_user("coord_sin_asignacion")
        self.coord_sin.groups.add(self.g_coord)

        self.territorial = User.objects.create_user("terri")
        self.territorial.groups.add(self.g_terri)

    # --- existencia y configuración de roles ---
    def test_tres_roles_existen_categoria_programa(self):
        for nombre in (ROL_ADMIN, ROL_COORDINADOR, ROL_TERRITORIAL):
            meta = Group.objects.get(name=nombre).meta
            self.assertEqual(meta.categoria, rbac.CATEGORIA_PROGRAMA)
            self.assertEqual(meta.programa_id, self.becas.id)
            self.assertTrue(meta.activo)

    def test_capacidades_de_cada_rol(self):
        self.assertTrue(rbac.puede(self.admin, "becas.programa.administrar", programa=self.becas))
        self.assertTrue(rbac.puede(self.admin, "becas.revision.editar", programa=self.becas))
        self.assertFalse(rbac.puede(self.coord, "becas.programa.administrar", programa=self.becas))
        self.assertTrue(rbac.puede(self.coord, "becas.revision.editar", programa=self.becas))
        self.assertTrue(rbac.puede(self.territorial, "becas.campo", programa=self.becas))
        self.assertFalse(rbac.puede(self.territorial, "becas.revision.editar", programa=self.becas))

    # --- admin: acceso total ---
    def test_admin_gestiona_cualquier_segmento(self):
        self.assertTrue(es_admin_becas(self.admin, programa=self.becas))
        self.assertTrue(puede_gestionar_segmento(self.admin, self.seg_a, programa=self.becas))
        self.assertTrue(puede_gestionar_segmento(self.admin, self.seg_b, programa=self.becas))
        self.assertEqual(set(segmentos_visibles(self.admin, programa=self.becas)), {self.seg_a, self.seg_b})

    # --- coordinador: scoping por segmento ---
    def test_coordinador_asignado_accede_solo_a_su_segmento(self):
        self.assertTrue(es_coordinador_becas(self.coord, programa=self.becas))
        self.assertTrue(puede_gestionar_segmento(self.coord, self.seg_a, programa=self.becas))
        self.assertFalse(puede_gestionar_segmento(self.coord, self.seg_b, programa=self.becas))
        self.assertEqual(set(segmentos_visibles(self.coord, programa=self.becas)), {self.seg_a})

    def test_coordinador_sin_asignacion_no_accede(self):
        self.assertFalse(puede_gestionar_segmento(self.coord_sin, self.seg_a, programa=self.becas))
        self.assertFalse(puede_gestionar_segmento(self.coord_sin, self.seg_b, programa=self.becas))
        self.assertEqual(list(segmentos_visibles(self.coord_sin, programa=self.becas)), [])

    # --- territorial: sin acceso de gestión/revisión ---
    def test_territorial_no_gestiona_segmentos(self):
        self.assertFalse(es_admin_becas(self.territorial, programa=self.becas))
        self.assertFalse(es_coordinador_becas(self.territorial, programa=self.becas))
        self.assertFalse(puede_gestionar_segmento(self.territorial, self.seg_a, programa=self.becas))
        self.assertEqual(list(segmentos_visibles(self.territorial, programa=self.becas)), [])

    # --- RN-27: múltiples roles a la vez ---
    def test_usuario_con_multiples_roles(self):
        otro_grupo = Group.objects.create(name="Operador genérico")
        rbac_ct_user = User.objects.create_user("multi")
        rbac_ct_user.groups.add(self.g_admin, otro_grupo)
        # Sigue siendo admin de Becas con varios roles asignados.
        self.assertTrue(es_admin_becas(rbac_ct_user, programa=self.becas))
        self.assertTrue(puede_gestionar_segmento(rbac_ct_user, self.seg_b, programa=self.becas))

    def test_anonimo_no_accede(self):
        from django.contrib.auth.models import AnonymousUser

        self.assertFalse(puede_gestionar_segmento(AnonymousUser(), self.seg_a, programa=self.becas))
        self.assertEqual(list(segmentos_visibles(AnonymousUser(), programa=self.becas)), [])
