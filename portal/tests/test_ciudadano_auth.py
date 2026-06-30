from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from legajos.models import Ciudadano


class CiudadanoAuthViewsTests(TestCase):
    def setUp(self):
        Group.objects.create(name="Ciudadanos")

    def test_registro_step1_con_legajo_existente_guarda_sesion(self):
        ciudadano = Ciudadano.objects.create(
            dni="30111222",
            nombre="Ana",
            apellido="Perez",
            genero="F",
        )

        response = self.client.post(
            reverse("portal:ciudadano_registro_step1"),
            data={"dni": ciudadano.dni, "genero": ciudadano.genero},
        )

        self.assertRedirects(response, reverse("portal:ciudadano_registro_step2"))
        session = self.client.session["registro_ciudadano"]
        self.assertEqual(session["flujo"], "legajo_existente")
        self.assertEqual(session["ciudadano_id"], ciudadano.pk)
        self.assertEqual(session["dni"], ciudadano.dni)

    def test_registro_step1_con_usuario_existente_redirige_login(self):
        user = User.objects.create_user(username="30111222", password="secret")
        user.groups.add(Group.objects.get(name="Ciudadanos"))
        Ciudadano.objects.create(
            dni="30111222",
            nombre="Ana",
            apellido="Perez",
            genero="F",
            usuario=user,
        )

        response = self.client.post(
            reverse("portal:ciudadano_registro_step1"),
            data={"dni": "30111222", "genero": "F"},
        )

        self.assertRedirects(response, reverse("portal:ciudadano_login"))

    @patch("portal.services.ciudadano_auth.consultar_datos_renaper")
    def test_registro_step1_nuevo_consulta_renaper_y_guarda_sesion(self, consultar_mock):
        consultar_mock.return_value = {
            "success": True,
            "data": {"nombre": "Ana", "apellido": "Perez"},
        }

        response = self.client.post(
            reverse("portal:ciudadano_registro_step1"),
            data={"dni": "30111222", "genero": "F"},
        )

        self.assertRedirects(response, reverse("portal:ciudadano_registro_step2"))
        session = self.client.session["registro_ciudadano"]
        self.assertEqual(session["flujo"], "nuevo")
        self.assertEqual(session["nombre"], "Ana")
        self.assertEqual(session["apellido"], "Perez")

    def test_registro_step2_vincula_legajo_existente_y_loguea(self):
        ciudadano = Ciudadano.objects.create(
            dni="30111222",
            nombre="Ana",
            apellido="Perez",
            genero="F",
        )
        session = self.client.session
        session["registro_ciudadano"] = {
            "flujo": "legajo_existente",
            "ciudadano_id": ciudadano.pk,
            "dni": ciudadano.dni,
        }
        session.save()

        response = self.client.post(
            reverse("portal:ciudadano_registro_step2"),
            data={
                "email": "ana@example.com",
                "telefono": "2664123456",
                "password1": "supersecret123",
                "password2": "supersecret123",
            },
        )

        ciudadano.refresh_from_db()
        self.assertIsNotNone(ciudadano.usuario_id)
        self.assertEqual(ciudadano.usuario.email, "ana@example.com")
        self.assertEqual(self.client.session.get("_auth_user_id"), str(ciudadano.usuario_id))
        self.assertRedirects(response, reverse("portal:ciudadano_mi_perfil"))
