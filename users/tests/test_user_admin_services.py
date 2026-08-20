from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from core import rbac
from users.forms import CustomUserChangeForm, UserCreationForm
from users.models import Capacidad, Profile, RolMeta
from users.services import UsuariosAdminService


def _perm(codigo):
    ct = ContentType.objects.get_for_model(Capacidad)
    return Permission.objects.get(codename=rbac.codename_de(codigo), content_type=ct)


class UsuariosAdminServiceTests(TestCase):
    def setUp(self):
        self.group_admin = Group.objects.create(name="Administrador")
        RolMeta.objects.create(grupo=self.group_admin, categoria="Sistema", activo=True, protegido=True)
        # El rol Administrador otorga las capacidades de administración (como el seed),
        # para que la auto-protección reconozca a sus usuarios como administradores.
        self.group_admin.permissions.add(_perm("usuario.administrar"), _perm("rol.administrar"))
        self.group_op = Group.objects.create(name="Operador")
        RolMeta.objects.create(grupo=self.group_op, categoria="Backoffice", activo=True)

    def test_create_user_from_form_persists_roles_and_password(self):
        form = UserCreationForm(
            data={
                "username": "operador1",
                "email": "operador1@example.com",
                "password": "clave-segura-123",
                "groups[]": [str(self.group_admin.pk), str(self.group_op.pk)],
                "last_name": "Perez",
                "first_name": "Ana",
                "dni": "30111222",
                "telefono": "3624000000",
                "institucion": "ECOM",
                "observacion": "Usuario territorial",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)

        user = UsuariosAdminService.create_user_from_form(form)

        self.assertEqual(user.username, "operador1")
        self.assertTrue(user.check_password("clave-segura-123"))
        self.assertEqual(user.profile.dni, "30111222")
        self.assertEqual(user.profile.telefono, "3624000000")
        self.assertEqual(user.profile.institucion, "ECOM")
        self.assertEqual(user.profile.observacion, "Usuario territorial")
        self.assertCountEqual(
            list(user.groups.values_list("name", flat=True)),
            ["Administrador", "Operador"],
        )

    def test_update_user_from_form_keeps_existing_password_when_blank(self):
        user = User.objects.create_user(
            username="operador2",
            email="old@example.com",
            password="clave-original",
            first_name="Luis",
            last_name="Gomez",
        )
        user.groups.add(self.group_op)
        original_password_hash = user.password

        form = CustomUserChangeForm(
            data={
                "username": "operador2",
                "email": "new@example.com",
                "password": "",
                "groups": [str(self.group_admin.pk)],
                "last_name": "Gomez",
                "first_name": "Luis",
                "dni": "28999888",
                "telefono": "3624111111",
                "institucion": "Desarrollo Social",
                "observacion": "Dato actualizado",
            },
            instance=user,
        )
        self.assertTrue(form.is_valid(), form.errors)

        updated_user = UsuariosAdminService.update_user_from_form(form)
        updated_user.refresh_from_db()

        self.assertEqual(updated_user.email, "new@example.com")
        self.assertEqual(updated_user.password, original_password_hash)
        self.assertTrue(updated_user.check_password("clave-original"))
        self.assertEqual(updated_user.profile.dni, "28999888")
        self.assertEqual(updated_user.profile.telefono, "3624111111")
        self.assertEqual(updated_user.profile.institucion, "Desarrollo Social")
        self.assertEqual(updated_user.profile.observacion, "Dato actualizado")
        self.assertCountEqual(
            list(updated_user.groups.values_list("name", flat=True)),
            ["Administrador"],
        )

    def test_rol_inactivo_no_es_asignable(self):
        inactivo = Group.objects.create(name="RolViejo")
        RolMeta.objects.create(grupo=inactivo, categoria="Backoffice", activo=False)

        form = UserCreationForm(
            data={
                "username": "x",
                "email": "x@example.com",
                "password": "clave-segura-123",
                "groups[]": [str(inactivo.pk)],
                "last_name": "X",
                "first_name": "X",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("groups", form.errors)

    def test_dni_no_puede_repetirse(self):
        existente = User.objects.create_user("existente", password="x")
        Profile.objects.update_or_create(user=existente, defaults={"dni": "30111222"})

        form = UserCreationForm(
            data={
                "username": "duplicado",
                "email": "duplicado@example.com",
                "password": "clave-segura-123",
                "last_name": "Duplicado",
                "first_name": "DNI",
                "dni": "30111222",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("dni", form.errors)

    def _form_edicion(self, user, dni):
        return CustomUserChangeForm(
            data={
                "username": user.username,
                "email": user.email or "x@example.com",
                "password": "",
                "last_name": "X",
                "first_name": "X",
                "dni": dni,
            },
            instance=user,
        )

    def test_dni_no_puede_repetirse_al_editar(self):
        """La edición corre la misma validación que el alta (antes sin cobertura)."""
        ajeno = User.objects.create_user("ajeno", password="x")
        Profile.objects.update_or_create(user=ajeno, defaults={"dni": "30111222"})
        editado = User.objects.create_user("editado", email="editado@example.com", password="x")
        Profile.objects.update_or_create(user=editado, defaults={"dni": "28999888"})

        form = self._form_edicion(editado, "30111222")

        self.assertFalse(form.is_valid())
        self.assertIn("dni", form.errors)

    def test_editar_conservando_el_propio_dni_no_es_duplicado(self):
        """El chequeo se excluye a sí mismo: guardar sin tocar el DNI no debe fallar."""
        editado = User.objects.create_user("editado", email="editado@example.com", password="x")
        Profile.objects.update_or_create(user=editado, defaults={"dni": "28999888"})

        form = self._form_edicion(editado, "28999888")

        self.assertTrue(form.is_valid(), form.errors)

    def test_varios_usuarios_sin_dni_conviven(self):
        """El vacío se guarda como NULL, no como cadena: el unique no los choca."""
        for n in range(3):
            form = UserCreationForm(
                data={
                    "username": f"sin-dni-{n}",
                    "email": f"sin-dni-{n}@example.com",
                    "password": "clave-segura-123",
                    "last_name": "Sin",
                    "first_name": "DNI",
                    "dni": "",
                }
            )
            self.assertTrue(form.is_valid(), form.errors)
            usuario = UsuariosAdminService.create_user_from_form(form)
            self.assertIsNone(usuario.profile.dni)
