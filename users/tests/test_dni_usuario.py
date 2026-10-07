"""RED-48 (ronda 3) · El DNI del usuario de backoffice, la novena puerta.

Dos cosas que la unificación de la ronda 2 dejó mal y que **solo se ven contra el motor
real**, porque SQLite no aplica el `max_length`:

1. El form aceptaba `12.345.678` —`dni_valido()` normaliza antes de medir— y el servicio
   lo guardaba **crudo** en `Profile.dni`, que es un `CharField(max_length=8)`. En
   MariaDB y en MySQL eso es `DataError (1406, "Data too long for column 'dni'")`: un
   **500** en el ABM de usuarios.
2. Exigir la regla de largo siempre dejaba **inmodificable** a cualquier usuario con un
   DNI legacy de 6 dígitos: no se le podía cambiar ni el rol ni el correo, porque el
   error quedaba colgado del campo `dni` y el form no validaba.

`UsuarioDniMotorRealTests` es la parte que necesita motor (`@tag("mysql")`, la corre el
job «Motor real»); el resto corre en la suite normal.
"""

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.test import TestCase, TransactionTestCase, tag

from core import rbac
from programas.tests.base_becas import ProgramaBecasSembrado
from users.forms import CustomUserChangeForm, UserCreationForm
from users.models import Capacidad, Profile, RolMeta
from users.services import UsuariosAdminService

MOTOR_REAL = connection.vendor == "mysql"


def _rol_administrador():
    grupo = Group.objects.create(name="Administrador")
    RolMeta.objects.create(grupo=grupo, categoria="Sistema", activo=True, protegido=True)
    tipo = ContentType.objects.get_for_model(Capacidad)
    for codigo in ("usuario.administrar", "rol.administrar"):
        grupo.permissions.add(Permission.objects.get(codename=rbac.codename_de(codigo), content_type=tipo))
    return grupo


def _datos_de_alta(**extra):
    return {
        "username": "operador_dni",
        "email": "operador_dni@example.com",
        "password": "clave-segura-123",
        "last_name": "Perez",
        "first_name": "Ana",
        **extra,
    }


def _datos_de_edicion(usuario, dni, **extra):
    return {
        "username": usuario.username,
        "email": usuario.email or "x@example.com",
        "password": "",
        "last_name": usuario.last_name or "X",
        "first_name": usuario.first_name or "X",
        "dni": dni,
        **extra,
    }


class DniDelUsuarioTests(ProgramaBecasSembrado, TestCase):
    """Lo que se puede medir sin motor real: qué queda en `cleaned_data`."""

    def setUp(self):
        super().setUp()
        self.rol = _rol_administrador()

    def test_el_dni_con_separadores_llega_normalizado_al_servicio(self):
        """El bug de fondo: lo que el form deja en `cleaned_data` es lo que se guarda."""
        form = UserCreationForm(data=_datos_de_alta(dni="12.345.678"))

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["dni"], "12345678")

    def test_un_dni_fuera_de_la_regla_sigue_rechazado_en_el_alta(self):
        form = UserCreationForm(data=_datos_de_alta(dni="123456"))

        self.assertFalse(form.is_valid())
        self.assertIn("dni", form.errors)

    def test_sin_dni_se_guarda_nulo(self):
        """El Cambio 5: puede haber varios usuarios sin DNI."""
        form = UserCreationForm(data=_datos_de_alta(dni=""))

        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.cleaned_data["dni"])

    def test_el_duplicado_se_detecta_contra_el_dni_normalizado(self):
        ajeno = User.objects.create_user("ajeno_dni", password="x")
        Profile.objects.update_or_create(user=ajeno, defaults={"dni": "12345678"})

        form = UserCreationForm(data=_datos_de_alta(dni="12.345.678"))

        self.assertFalse(form.is_valid())
        self.assertIn("dni", form.errors)


class DniLegacyDelUsuarioTests(ProgramaBecasSembrado, TestCase):
    """Un usuario cargado con un DNI que la regla nueva rechaza sigue siendo editable."""

    def setUp(self):
        super().setUp()
        self.rol = _rol_administrador()
        self.usuario = User.objects.create_user("legacy_dni", email="legacy@example.com", password="x")
        self.usuario.first_name = "Vieja"
        self.usuario.last_name = "Ficha"
        self.usuario.save()
        Profile.objects.update_or_create(user=self.usuario, defaults={"dni": "123456"})

    def _editar(self, dni="123456", **extra):
        return CustomUserChangeForm(
            data=_datos_de_edicion(self.usuario, dni, **extra),
            instance=self.usuario,
        )

    def test_se_puede_cambiar_el_correo_sin_tocar_el_dni(self):
        form = self._editar(email="nuevo@example.com")

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["dni"], "123456")

    def test_se_puede_cambiar_el_rol_sin_tocar_el_dni(self):
        operador = User.objects.create_superuser("root_dni", "root@example.com", "x")
        form = CustomUserChangeForm(
            data={
                **_datos_de_edicion(self.usuario, "123456"),
                "groups[]": [str(self.rol.pk)],
            },
            instance=self.usuario,
            operador=operador,
        )

        self.assertTrue(form.is_valid(), form.errors)
        UsuariosAdminService.update_user_from_form(form)

        self.usuario.refresh_from_db()
        self.assertEqual(list(self.usuario.groups.values_list("name", flat=True)), ["Administrador"])
        self.assertEqual(self.usuario.profile.dni, "123456")

    def test_cambiarlo_por_otro_invalido_sigue_sin_poder(self):
        form = self._editar(dni="999")

        self.assertFalse(form.is_valid())
        self.assertIn("dni", form.errors)

    def test_corregirlo_por_uno_valido_se_puede(self):
        form = self._editar(dni="30.111.222")

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["dni"], "30111222")


@tag("mysql")
class UsuarioDniMotorRealTests(ProgramaBecasSembrado, TransactionTestCase):
    """El 1406 solo existe contra el motor de verdad: SQLite ignora el `max_length`.

    `Profile.dni` es `char(8)`; `12.345.678` son diez caracteres. Antes de este arreglo
    el ABM de usuarios respondía **500** al dar de alta con el DNI tipeado con puntos.
    """

    available_apps = None

    def setUp(self):
        if not MOTOR_REAL:
            self.skipTest("Necesita MySQL o MariaDB de verdad (DJANGO_TEST_MOTOR + DATABASE_*).")
        super().setUp()
        self.rol = _rol_administrador()

    def test_la_columna_es_mas_corta_que_un_dni_con_separadores(self):
        """El motivo por el que esto tiene que ser un test de motor real."""
        self.assertEqual(Profile._meta.get_field("dni").max_length, 8)
        self.assertGreater(len("12.345.678"), 8)

    def test_el_alta_con_el_dni_tipeado_con_puntos_guarda_los_digitos(self):
        form = UserCreationForm(data=_datos_de_alta(dni="12.345.678"))
        self.assertTrue(form.is_valid(), form.errors)

        usuario = UsuariosAdminService.create_user_from_form(form)

        usuario.refresh_from_db()
        self.assertEqual(usuario.profile.dni, "12345678")

    def test_la_edicion_con_el_dni_tipeado_con_puntos_guarda_los_digitos(self):
        usuario = User.objects.create_user("edita_dni", email="edita@example.com", password="x")
        Profile.objects.update_or_create(user=usuario, defaults={"dni": "30111222"})
        operador = User.objects.create_superuser("root_motor", "root@example.com", "x")
        form = CustomUserChangeForm(
            data=_datos_de_edicion(usuario, "12.345.678"),
            instance=usuario,
            operador=operador,
        )
        self.assertTrue(form.is_valid(), form.errors)

        UsuariosAdminService.update_user_from_form(form)

        usuario.refresh_from_db()
        self.assertEqual(usuario.profile.dni, "12345678")
