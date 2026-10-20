"""El costo del login es el hash de la contraseña: Argon2 primero, PBKDF2 solo para leer lo ya guardado."""

from django.contrib.auth.hashers import Argon2PasswordHasher, identify_hasher, make_password
from django.contrib.auth.models import User
from django.test import TestCase


def _usuario_con_hash_pbkdf2(username, password):
    """Simula una cuenta creada antes del cambio: su hash quedó en PBKDF2."""
    user = User.objects.create_user(username, password="provisoria")
    user.password = make_password(password, hasher="pbkdf2_sha256")
    user.save(update_fields=["password"])
    return user


class PasswordHashersTests(TestCase):
    def test_las_contrasenas_nuevas_se_guardan_con_argon2(self):
        user = User.objects.create_user("nuevo", password="clave-correcta-123")

        self.assertEqual(identify_hasher(user.password).algorithm, "argon2")

    def test_un_hash_pbkdf2_existente_sigue_autenticando(self):
        user = _usuario_con_hash_pbkdf2("viejo", "clave-correcta-123")

        self.assertTrue(user.check_password("clave-correcta-123"))
        self.assertFalse(user.check_password("otra-clave"))

    def test_el_login_migra_el_hash_pbkdf2_a_argon2(self):
        user = _usuario_con_hash_pbkdf2("migra", "clave-correcta-123")
        self.assertEqual(identify_hasher(user.password).algorithm, "pbkdf2_sha256")

        response = self.client.post("/login/", {"username": "migra", "password": "clave-correcta-123"})

        self.assertEqual(response.status_code, 302)
        user.refresh_from_db()
        self.assertEqual(identify_hasher(user.password).algorithm, "argon2")
        self.assertTrue(user.check_password("clave-correcta-123"))


class Argon2AjustadoTests(TestCase):
    """Parámetros OWASP (m=19456, t=2, p=1) en lugar de los defaults de Django."""

    def test_una_clave_nueva_sale_con_los_parametros_ajustados(self):
        user = User.objects.create_user("owasp", password="clave-correcta-123")

        self.assertIn("m=19456,t=2,p=1", user.password)

    def test_un_hash_con_los_defaults_de_django_sigue_autenticando_y_se_rehashea(self):
        user = User.objects.create_user("stock", password="provisoria")
        user.password = Argon2PasswordHasher().encode("clave-correcta-123", Argon2PasswordHasher().salt())
        user.save(update_fields=["password"])
        self.assertIn("m=102400,t=2,p=8", user.password)

        self.assertTrue(user.check_password("clave-correcta-123"))
        response = self.client.post("/login/", {"username": "stock", "password": "clave-correcta-123"})

        self.assertEqual(response.status_code, 302)
        user.refresh_from_db()
        self.assertIn("m=19456,t=2,p=1", user.password)
        self.assertTrue(user.check_password("clave-correcta-123"))
