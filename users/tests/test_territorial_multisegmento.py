"""Territorial con varios segmentos: «alguno» para ver, «dueño» para la cuenta.

El segmento dueño es el de la asignación más antigua. Cualquier gestor con alguno de
los segmentos del territorial lo ve y agrega o quita los suyos; solo el gestor del
dueño toca credenciales, datos personales y roles, y eso lo hace valer el servicio.
"""

from io import StringIO

from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from programas.management.commands.seed_becas import ROL_COORDINADOR, ROL_TERRITORIAL
from programas.models import AsignacionCoordinador, AsignacionTerritorial, Segmento
from users.forms import CustomUserChangeForm
from users.selectors.usuarios import (
    anotar_acciones_del_listado,
    puede_gestionar_credenciales,
    puede_gestionar_usuario,
    usuarios_visibles_para,
)
from users.services.admin import UsuariosAdminService


class _Base(TestCase):
    def setUp(self):
        cache.clear()
        call_command("seed_becas", stdout=StringIO())
        self.seg_a = Segmento.objects.create(nombre="Seg A", cupo_maximo=10)
        self.seg_b = Segmento.objects.create(nombre="Seg B", cupo_maximo=10)
        self.seg_c = Segmento.objects.create(nombre="Seg C", cupo_maximo=10)
        self.rol_territorial = Group.objects.get(name=ROL_TERRITORIAL)
        self.coord_a = self._coordinador("coord_a", self.seg_a)
        self.coord_b = self._coordinador("coord_b", self.seg_b)
        self.admin = User.objects.create_superuser("admin_ms", "admin@example.com", "x")
        self.territorial = User.objects.create_user(
            "terri_ms", email="terri@example.com", password="Clave-Original-2026", first_name="Terri", last_name="Ms"
        )
        self.territorial.groups.add(self.rol_territorial)
        # A es el dueño (la primera, de menor pk); B se suma después.
        self.fila_a = AsignacionTerritorial.objects.create(segmento=self.seg_a, territorial=self.territorial)
        self.fila_b = AsignacionTerritorial.objects.create(segmento=self.seg_b, territorial=self.territorial)

    def _coordinador(self, username, segmento):
        usuario = User.objects.create_user(username, password="x")
        usuario.groups.add(Group.objects.get(name=ROL_COORDINADOR))
        AsignacionCoordinador.objects.create(segmento=segmento, coordinador=usuario)
        return usuario

    def _data(self, **extra):
        data = {
            "username": "otro_usuario",
            "email": "otro@example.com",
            "password": "Clave-Nueva-2026",
            "first_name": "Cambiado",
            "last_name": "Cambiado",
            "dni": "30111222",
            "telefono": "555",
            "groups": [str(self.rol_territorial.pk)],
        }
        data.update(extra)
        return data

    def _snapshot(self):
        from users.models import Profile

        self.territorial.refresh_from_db()
        perfil = Profile.objects.filter(user=self.territorial).first()
        return (
            self.territorial.username,
            self.territorial.email,
            self.territorial.password,
            self.territorial.is_active,
            self.territorial.first_name,
            self.territorial.last_name,
            perfil.dni if perfil else None,
            perfil.telefono if perfil else None,
            tuple(self.territorial.groups.values_list("pk", flat=True)),
        )

    def _segmentos_del_territorial(self):
        return set(
            AsignacionTerritorial.objects.filter(territorial=self.territorial).values_list("segmento_id", flat=True)
        )


class AlcanceDelTerritorialCompartidoTests(_Base):
    def test_los_dos_coordinadores_lo_ven_en_el_listado(self):
        self.assertIn(self.territorial, usuarios_visibles_para(self.coord_a))
        self.assertIn(self.territorial, usuarios_visibles_para(self.coord_b))
        self.assertEqual(usuarios_visibles_para(self.coord_b).filter(pk=self.territorial.pk).count(), 1)

    def test_un_coordinador_ajeno_a_ambos_no_lo_ve(self):
        coord_c = self._coordinador("coord_c", self.seg_c)
        self.assertNotIn(self.territorial, usuarios_visibles_para(coord_c))
        self.assertFalse(puede_gestionar_usuario(coord_c, self.territorial))

    def test_ambos_pueden_gestionarlo_pero_la_cuenta_es_solo_del_dueno(self):
        self.assertTrue(puede_gestionar_usuario(self.coord_a, self.territorial))
        self.assertTrue(puede_gestionar_usuario(self.coord_b, self.territorial))
        self.assertTrue(puede_gestionar_credenciales(self.coord_a, self.territorial))
        self.assertFalse(puede_gestionar_credenciales(self.coord_b, self.territorial))

    def test_el_listado_marca_credenciales_solo_para_el_dueno(self):
        def marcas(operador):
            usuarios = list(User.objects.filter(pk=self.territorial.pk).prefetch_related("groups"))
            fila = anotar_acciones_del_listado(operador, usuarios)[0]
            return fila.gestionable, fila.credenciales_editables

        self.assertEqual(marcas(self.coord_a), (True, True))
        self.assertEqual(marcas(self.coord_b), (True, False))

    def test_al_quitar_la_fila_del_dueno_el_siguiente_pasa_a_ser_dueno(self):
        self.fila_a.delete()
        self.assertTrue(puede_gestionar_credenciales(self.coord_b, self.territorial))
        self.assertFalse(puede_gestionar_usuario(self.coord_a, self.territorial))

    def test_vistas_de_cuenta_cerradas_para_el_no_dueno(self):
        self.client.force_login(self.coord_b)
        antes = self._snapshot()
        self.client.post(reverse("users:usuario_toggle", args=[self.territorial.pk]))
        resp = self.client.post(reverse("users:usuario_cerrar_sesion_app", args=[self.territorial.pk]))
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(self._snapshot(), antes)
        # El dueño sí.
        self.client.force_login(self.coord_a)
        self.client.post(reverse("users:usuario_toggle", args=[self.territorial.pk]))
        self.territorial.refresh_from_db()
        self.assertFalse(self.territorial.is_active)


class GuardadoDelNoDuenoTests(_Base):
    def _editar(self, operador, **extra):
        self.client.force_login(operador)
        return self.client.post(reverse("users:usuario_editar", args=[self.territorial.pk]), self._data(**extra))

    def test_el_no_dueno_no_toca_la_cuenta_con_un_post_armado(self):
        antes = self._snapshot()
        resp = self._editar(self.coord_b, segmentos_territoriales=[str(self.seg_b.pk)])
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(self._snapshot(), antes)
        self.assertEqual(self._segmentos_del_territorial(), {self.seg_a.pk, self.seg_b.pk})

    def test_el_no_dueno_no_saca_el_rol_territorial(self):
        antes = self._snapshot()
        resp = self._editar(self.coord_b, groups=[], segmentos_territoriales=[str(self.seg_b.pk)])
        self.assertIn(resp.status_code, (200, 302))
        self.assertEqual(self._snapshot(), antes)
        self.assertTrue(self.territorial.groups.filter(pk=self.rol_territorial.pk).exists())
        self.assertEqual(self._segmentos_del_territorial(), {self.seg_a.pk, self.seg_b.pk})

    def test_el_servicio_lo_hace_valer_aunque_el_form_no_lo_bloquee(self):
        """El form del admin deja todo editable; el que guarda es el no dueño y el servicio decide solo."""
        antes = self._snapshot()
        form = CustomUserChangeForm(
            self._data(segmentos_territoriales=[str(self.seg_b.pk)]),
            instance=self.territorial,
            operador=self.admin,  # el form del admin: todos los campos editables y válidos
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.operador = self.coord_b
        UsuariosAdminService.update_user_from_form(form)
        self.assertEqual(self._snapshot(), antes)
        # Eligió B, que es de su alcance y ya estaba: los segmentos no cambian.
        self.assertEqual(self._segmentos_del_territorial(), {self.seg_a.pk, self.seg_b.pk})

    def test_el_no_dueno_quita_su_segmento_sin_borrar_el_del_dueno(self):
        resp = self._editar(self.coord_b, segmentos_territoriales=[])
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(self._segmentos_del_territorial(), {self.seg_a.pk})

    def test_el_dueno_edita_la_cuenta_y_conserva_la_fila_ajena(self):
        resp = self._editar(self.coord_a, username="renombrado", segmentos_territoriales=[str(self.seg_a.pk)])
        self.assertEqual(resp.status_code, 302, resp.context["form"].errors if resp.context else None)
        self.territorial.refresh_from_db()
        self.assertEqual(self.territorial.username, "renombrado")
        self.assertEqual(self.territorial.first_name, "Cambiado")
        self.assertEqual(self._segmentos_del_territorial(), {self.seg_a.pk, self.seg_b.pk})

    def test_el_dueno_que_quita_su_segmento_deja_al_siguiente_como_dueno(self):
        # El set final no queda vacío: la fila de B queda fuera de su alcance y se conserva.
        resp = self._editar(self.coord_a, segmentos_territoriales=[])
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(self._segmentos_del_territorial(), {self.seg_b.pk})
        self.assertTrue(puede_gestionar_credenciales(self.coord_b, self.territorial))

    def test_agregar_un_segmento_no_borra_los_ajenos_y_registra_quien_asigno(self):
        coord_ac = self._coordinador("coord_ac", self.seg_a)
        AsignacionCoordinador.objects.create(segmento=self.seg_c, coordinador=coord_ac)
        resp = self._editar(coord_ac, segmentos_territoriales=[str(self.seg_c.pk)])
        self.assertEqual(resp.status_code, 302, resp.context["form"].errors if resp.context else None)
        # A salió (era de su alcance y no lo eligió), B (ajeno) se conserva, C entró.
        self.assertEqual(self._segmentos_del_territorial(), {self.seg_b.pk, self.seg_c.pk})
        self.assertEqual(AsignacionTerritorial.objects.get(segmento=self.seg_c).asignado_por, coord_ac)


class EscritorYFormTests(_Base):
    def test_el_admin_reemplaza_en_alcance_y_no_borra_segmentos_inactivos(self):
        self.seg_b.activo = False
        self.seg_b.save(update_fields=["activo"])
        self.client.force_login(self.admin)
        resp = self.client.post(
            reverse("users:usuario_editar", args=[self.territorial.pk]),
            self._data(
                username="terri_ms",
                email="terri@example.com",
                password="",
                segmentos_territoriales=[str(self.seg_c.pk)],
            ),
        )
        self.assertEqual(resp.status_code, 302, resp.context["form"].errors if resp.context else None)
        self.assertEqual(self._segmentos_del_territorial(), {self.seg_b.pk, self.seg_c.pk})  # A reemplazado
        self.assertEqual(AsignacionTerritorial.objects.get(segmento=self.seg_c).asignado_por, self.admin)

    def test_el_form_precarga_los_segmentos_del_alcance_del_operador(self):
        form = CustomUserChangeForm(instance=self.territorial, operador=self.coord_b)
        self.assertEqual(form.fields["segmentos_territoriales"].initial, [self.seg_b.pk])
        form = CustomUserChangeForm(instance=self.territorial, operador=self.admin)
        self.assertEqual(form.fields["segmentos_territoriales"].initial, [self.seg_a.pk, self.seg_b.pk])

    def test_el_form_del_no_dueno_deshabilita_cuenta_perfil_y_roles(self):
        form = CustomUserChangeForm(instance=self.territorial, operador=self.coord_b)
        for nombre in ("username", "email", "password", "first_name", "last_name", "groups", "dni", "telefono"):
            self.assertTrue(form.fields[nombre].disabled, nombre)
        self.assertFalse(form.fields["segmentos_territoriales"].disabled)
        form = CustomUserChangeForm(instance=self.territorial, operador=self.coord_a)
        self.assertFalse(form.fields["username"].disabled)

    def test_alta_rapida_asigna_y_registra_al_operador(self):
        self.client.force_login(self.coord_a)
        resp = self.client.post(
            reverse("users:usuario_alta_rapida"),
            {
                "tipo": "territorial",
                "segmento_id": self.seg_a.pk,
                "username": "terri_modal",
                "email": "modal@example.com",
                "password": "Clave-Modal-2026",
                "first_name": "Terri",
                "last_name": "Modal",
            },
        )
        self.assertEqual(resp.status_code, 200)
        fila = AsignacionTerritorial.objects.get(territorial__username="terri_modal")
        self.assertEqual((fila.segmento, fila.asignado_por), (self.seg_a, self.coord_a))

    def test_alta_rapida_rechaza_un_segmento_fuera_del_alcance(self):
        self.client.force_login(self.coord_a)
        resp = self.client.post(
            reverse("users:usuario_alta_rapida"),
            {"tipo": "territorial", "segmento_id": self.seg_b.pk, "username": "x_terri", "password": "Clave-X-2026"},
        )
        self.assertEqual(resp.status_code, 403)
