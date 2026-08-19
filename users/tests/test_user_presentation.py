from django.contrib.auth.models import User
from django.test import TestCase

from users.models import Profile
from users.presentation import etiqueta_usuario


class EtiquetaUsuarioTests(TestCase):
    def test_nombre_apellido_y_dni(self):
        user = User.objects.create_user("jperez", first_name="Juan", last_name="Pérez")
        Profile.objects.update_or_create(user=user, defaults={"dni": "30123456"})
        user.refresh_from_db()

        self.assertEqual(etiqueta_usuario(user), "Juan Pérez (30123456)")

    def test_sin_dni_usa_nombre_y_sin_nombre_usa_username(self):
        con_nombre = User.objects.create_user("ana", first_name="Ana", last_name="López")
        sin_nombre = User.objects.create_user("territorial")

        self.assertEqual(etiqueta_usuario(con_nombre), "Ana López")
        self.assertEqual(etiqueta_usuario(sin_nombre), "territorial")

    def test_usuario_sin_perfil_no_rompe(self):
        user = User.objects.create_user("sin-perfil")

        self.assertEqual(etiqueta_usuario(user), "sin-perfil")

    def test_queryset_con_profile_no_genera_n_mas_uno(self):
        for numero in range(3):
            user = User.objects.create_user(f"user-{numero}")
            Profile.objects.update_or_create(user=user, defaults={"dni": f"3000000{numero}"})

        with self.assertNumQueries(1):
            etiquetas = [etiqueta_usuario(user) for user in User.objects.select_related("profile").order_by("pk")]

        self.assertEqual(len(etiquetas), 3)
