"""#1114: nadie se cambia sus propios roles y el Administrador no lo reparte cualquiera.

Cubre el ABM de Usuarios (alta y edición) con el POST forzado: el combo recortado o
deshabilitado no es la defensa, lo es el servidor.
"""

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from core import rbac
from programas.models import Programa
from users.models import Capacidad, RolMeta

CLAVE = "Clave-Segura-2026"
MSG_PROPIOS = "No podés cambiar tus propios roles."
MSG_ADMIN = "Solo un Administrador puede asignar o quitar el rol Administrador."


def _rol(nombre, caps=(), programa=None, clave=None, protegido=False):
    grupo = Group.objects.create(name=nombre)
    RolMeta.objects.create(
        grupo=grupo,
        categoria=rbac.CATEGORIA_PROGRAMA if programa else "Backoffice",
        programa=programa,
        activo=True,
        clave=clave,
        protegido=protegido,
    )
    ct = ContentType.objects.get_for_model(Capacidad)
    for codigo in caps:
        grupo.permissions.add(Permission.objects.get(codename=rbac.codename_de(codigo), content_type=ct))
    return grupo


def _user(username, *grupos, **extra):
    usuario = User.objects.create_user(username, password=CLAVE, email=f"{username}@x.test", **extra)
    usuario.groups.add(*grupos)
    return usuario


def _post(client, target, grupos):
    return client.post(
        reverse("users:usuario_editar", args=[target.pk]),
        {
            "username": target.username,
            "email": target.email,
            "first_name": "Nombre",
            "last_name": target.last_name,
            "password": "",
            "groups": [str(g.pk) for g in grupos],
        },
    )


def _mensajes(response):
    return [str(m) for m in response.context["messages"]] if response.context else []


def _ids(form):
    return set(form.fields["groups"].queryset.values_list("pk", flat=True))


class Base(TestCase):
    def setUp(self):
        cache.clear()
        Programa.objects.create(codigo="BECAS", nombre="Becas")  # lo exige el guardado de usuarios
        # El Administrador lleva todas las capacidades de administración, como el sembrado.
        self.administrador = _rol(
            rbac.ROL_ADMINISTRADOR,
            ["usuario.administrar", "rol.administrar"],
            clave=rbac.CLAVE_ROL_ADMINISTRADOR,
            protegido=True,
        )
        self.rol_usuarios = _rol("Administración", ["usuario.administrar"])
        self.rol_a = _rol("Rol A")
        self.rol_b = _rol("Rol B")
        self.admin_usuarios = _user("adminusuarios", self.rol_usuarios, self.rol_a)
        self.otro = _user("otro", self.rol_a)

    def entrar(self, usuario):
        self.client.force_login(usuario)


class PropiosRolesTests(Base):
    def test_get_muestra_los_roles_de_solo_lectura_con_la_ayuda(self):
        self.entrar(self.admin_usuarios)
        r = self.client.get(reverse("users:usuario_editar", args=[self.admin_usuarios.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertIn("Tus roles los cambia otro administrador.", r.content.decode())
        self.assertTrue(r.context["form"].fields["groups"].disabled)
        self.assertTrue(r.context["form"].roles_solo_lectura)

    def test_get_en_la_ficha_de_otro_no_muestra_la_ayuda(self):
        self.entrar(self.admin_usuarios)
        r = self.client.get(reverse("users:usuario_editar", args=[self.otro.pk]))
        self.assertNotIn("Tus roles los cambia otro administrador.", r.content.decode())
        self.assertFalse(r.context["form"].fields["groups"].disabled)

    def test_post_forzado_agregandose_un_rol_se_rechaza_sin_guardar_nada(self):
        self.entrar(self.admin_usuarios)
        antes = set(self.admin_usuarios.groups.values_list("pk", flat=True))
        r = _post(self.client, self.admin_usuarios, [self.rol_usuarios, self.rol_a, self.rol_b])
        self.assertEqual(r.status_code, 200)
        self.assertIn(MSG_PROPIOS, _mensajes(r))
        self.admin_usuarios.refresh_from_db()
        self.assertEqual(set(self.admin_usuarios.groups.values_list("pk", flat=True)), antes)
        self.assertEqual(self.admin_usuarios.first_name, "")  # tampoco se guardó nada más

    def test_post_forzado_asignandose_el_administrador_se_rechaza(self):
        self.entrar(self.admin_usuarios)
        r = _post(self.client, self.admin_usuarios, [self.rol_usuarios, self.rol_a, self.administrador])
        self.assertIn(MSG_PROPIOS, _mensajes(r))
        self.assertFalse(self.admin_usuarios.groups.filter(pk=self.administrador.pk).exists())

    def test_puede_editar_sus_datos_personales_sin_tocar_los_roles(self):
        self.entrar(self.admin_usuarios)
        antes = set(self.admin_usuarios.groups.values_list("pk", flat=True))
        # Como un navegador: el select deshabilitado no viaja en el POST.
        r = self.client.post(
            reverse("users:usuario_editar", args=[self.admin_usuarios.pk]),
            {
                "username": "adminusuarios",
                "email": "adminusuarios@x.test",
                "first_name": "Nuevo",
                "last_name": "Apellido",
                "password": "",
            },
        )
        self.assertEqual(r.status_code, 302)
        self.admin_usuarios.refresh_from_db()
        self.assertEqual(self.admin_usuarios.first_name, "Nuevo")
        self.assertEqual(set(self.admin_usuarios.groups.values_list("pk", flat=True)), antes)

    def test_superusuario_si_se_cambia_sus_propios_roles(self):
        su = User.objects.create_superuser("super", "s@x.test", CLAVE)
        self.entrar(su)
        r = _post(self.client, su, [self.rol_b])
        self.assertEqual(r.status_code, 302)
        self.assertEqual(list(su.groups.values_list("pk", flat=True)), [self.rol_b.pk])

    def test_el_servicio_no_toca_los_roles_propios_aunque_el_formulario_los_deje_pasar(self):
        from users.services.admin import UsuariosAdminService

        class FormFalso:
            operador = self.admin_usuarios
            instance = self.admin_usuarios
            cleaned_data = {
                "username": "adminusuarios",
                "email": "adminusuarios@x.test",
                "first_name": "",
                "last_name": "",
                "password": "",
                "groups": [self.rol_b],
            }

        UsuariosAdminService.update_user_from_form(FormFalso())
        self.assertFalse(self.admin_usuarios.groups.filter(pk=self.rol_b.pk).exists())


class AdministradorTests(Base):
    def test_el_combo_no_ofrece_el_administrador_a_un_admin_comun(self):
        self.entrar(self.admin_usuarios)
        r = self.client.get(reverse("users:usuario_editar", args=[self.otro.pk]))
        ids = _ids(r.context["form"])
        self.assertNotIn(self.administrador.pk, ids)
        self.assertIn(self.rol_b.pk, ids)

    def test_post_forzado_que_agrega_el_administrador_se_rechaza(self):
        self.entrar(self.admin_usuarios)
        r = _post(self.client, self.otro, [self.rol_a, self.administrador])
        self.assertEqual(r.status_code, 200)
        self.assertIn(MSG_ADMIN, _mensajes(r))
        self.assertFalse(self.otro.groups.filter(pk=self.administrador.pk).exists())

    def test_alta_con_el_administrador_forzado_se_rechaza(self):
        self.entrar(self.admin_usuarios)
        r = self.client.post(
            reverse("users:usuario_crear"),
            {
                "username": "nuevo",
                "email": "nuevo@x.test",
                "first_name": "N",
                "last_name": "N",
                "password": CLAVE,
                "groups": [str(self.administrador.pk)],
            },
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn(MSG_ADMIN, _mensajes(r))
        self.assertFalse(User.objects.filter(username="nuevo").exists())

    def test_editar_a_un_administrador_no_le_quita_el_rol(self):
        admin_existente = _user("ya-admin", self.administrador, self.rol_a)
        self.entrar(self.admin_usuarios)
        # El combo no lo ofrece, así que el navegador no lo manda: solo cambia Rol A por Rol B.
        r = _post(self.client, admin_existente, [self.rol_b])
        self.assertEqual(r.status_code, 302)
        self.assertEqual(
            set(admin_existente.groups.values_list("pk", flat=True)), {self.administrador.pk, self.rol_b.pk}
        )

    def test_un_administrador_asigna_y_quita_el_administrador_a_otros(self):
        quien = _user("quien", self.administrador)
        self.entrar(quien)
        r = _post(self.client, self.otro, [self.rol_a, self.administrador])
        self.assertEqual(r.status_code, 302)
        self.assertTrue(self.otro.groups.filter(pk=self.administrador.pk).exists())
        r = _post(self.client, self.otro, [self.rol_a])
        self.assertEqual(r.status_code, 302)
        self.assertFalse(self.otro.groups.filter(pk=self.administrador.pk).exists())

    def test_el_superusuario_asigna_el_administrador(self):
        su = User.objects.create_superuser("super", "s@x.test", CLAVE)
        self.entrar(su)
        r = _post(self.client, self.otro, [self.administrador])
        self.assertEqual(r.status_code, 302)
        self.assertTrue(self.otro.groups.filter(pk=self.administrador.pk).exists())

    def test_se_identifica_por_la_clave_y_no_por_el_nombre(self):
        impostor = _rol("Administrador ")  # parecido, sin la clave: es un rol común
        self.entrar(self.admin_usuarios)
        r = self.client.get(reverse("users:usuario_editar", args=[self.otro.pk]))
        self.assertIn(impostor.pk, _ids(r.context["form"]))
        RolMeta.objects.filter(grupo=self.administrador).update(clave=None)
        Group.objects.filter(pk=self.administrador.pk).update(name="Otro nombre")
        r = self.client.get(reverse("users:usuario_editar", args=[self.otro.pk]))
        self.assertIn(self.administrador.pk, _ids(r.context["form"]))  # sin clave ya no es «el» Administrador


class AdminDeProgramaTests(Base):
    def test_el_admin_de_programa_sigue_asignando_roles_de_su_programa_a_otros(self):
        disp = Programa.objects.create(codigo="DISPOSITIVOS", nombre="Dispositivos")
        rol_admin_prog = _rol("Admin Disp", ["programa.usuario.administrar"], programa=disp)
        rol_prog = _rol("Operador Disp", programa=disp)
        admin_prog = _user("adminprog", rol_admin_prog)
        objetivo = _user("objetivo", rol_prog)
        self.entrar(admin_prog)
        r = self.client.get(reverse("users:usuario_editar", args=[objetivo.pk]))
        self.assertFalse(r.context["form"].fields["groups"].disabled)
        self.assertNotIn(self.administrador.pk, _ids(r.context["form"]))
        r = _post(self.client, objetivo, [rol_prog])
        self.assertEqual(r.status_code, 302)


class AvisosFormularioDeRolesTests(Base):
    def test_el_form_de_roles_muestra_los_dos_avisos(self):
        su = User.objects.create_superuser("super", "s@x.test", CLAVE)
        self.entrar(su)
        html = self.client.get(reverse("users:rol_crear")).content.decode()
        self.assertIn("Administración global de todo el sistema", html)
        self.assertIn("Estas casillas permiten administrar todos los usuarios y todos los roles", html)
        self.assertIn("Administración de un programa en particular", html)
        self.assertIn("se limita al programa elegido en este rol", html)
