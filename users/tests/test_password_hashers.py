"""El costo del login es el hash de la contraseña: Argon2 primero, PBKDF2 solo para leer lo ya guardado."""

from django.contrib.auth.hashers import identify_hasher, make_password
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
