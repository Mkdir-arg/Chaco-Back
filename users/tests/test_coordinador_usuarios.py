from io import StringIO

from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from programas.management.commands.seed_becas import ROL_COORDINADOR, ROL_TERRITORIAL
from programas.models import AsignacionCoordinador, AsignacionTerritorial, Segmento
from users.forms import UserCreationForm


class CoordinadorGestionTerritorialesTests(TestCase):
    def setUp(self):
        cache.clear()
        call_command("seed_becas", stdout=StringIO())
        self.segmento = Segmento.objects.create(nombre="Coordinado", cupo_maximo=20)
        self.otro_segmento = Segmento.objects.create(nombre="Ajeno", cupo_maximo=20)
        self.coordinador = User.objects.create_user("coord-usuarios", password="x")
        self.coordinador.groups.add(Group.objects.get(name=ROL_COORDINADOR))
        AsignacionCoordinador.objects.create(segmento=self.segmento, coordinador=self.coordinador)
        self.rol_territorial = Group.objects.get(name=ROL_TERRITORIAL)
        self.client.force_login(self.coordinador)

    def test_form_solo_ofrece_rol_territorial_y_segmentos_coordinados(self):
        form = UserCreationForm(operador=self.coordinador)

        self.assertEqual(list(form.fields["groups"].queryset), [self.rol_territorial])
        self.assertEqual(list(form.fields["segmento_territorial"].queryset), [self.segmento])

    def test_crea_territorial_en_su_segmento(self):
        response = self.client.post(
            reverse("users:usuario_crear"),
            {
                "username": "territorial-nuevo",
                "email": "territorial@example.com",
                "password": "clave-segura-123",
                "first_name": "Territorial",
                "last_name": "Nuevo",
                "groups": [self.rol_territorial.pk],
                "segmento_territorial": self.segmento.pk,
            },
        )

        self.assertEqual(response.status_code, 302)
        creado = User.objects.get(username="territorial-nuevo")
        self.assertEqual(creado.asignacion_territorial.segmento, self.segmento)
        self.assertEqual(list(creado.groups.all()), [self.rol_territorial])

    def test_no_puede_asignar_segmento_ajeno(self):
        response = self.client.post(
            reverse("users:usuario_crear"),
            {
                "username": "territorial-ajeno",
                "email": "ajeno@example.com",
                "password": "clave-segura-123",
                "first_name": "Territorial",
                "last_name": "Ajeno",
                "groups": [self.rol_territorial.pk],
                "segmento_territorial": self.otro_segmento.pk,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="territorial-ajeno").exists())
        self.assertIn("segmento_territorial", response.context["form"].errors)

    def test_alta_rapida_crea_y_asigna_territorial(self):
        response = self.client.post(
            reverse("users:usuario_alta_rapida"),
            {
                "tipo": "territorial",
                "segmento_id": self.segmento.pk,
                "username": "territorial-modal",
                "email": "modal@example.com",
                "password": "clave-segura-123",
                "first_name": "Territorial",
                "last_name": "Modal",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        creado = User.objects.get(username="territorial-modal")
        self.assertEqual(creado.asignacion_territorial.segmento, self.segmento)
        self.assertEqual(response.json()["user"]["id"], creado.pk)

    def test_coordinador_no_puede_crear_otro_coordinador(self):
        response = self.client.post(
            reverse("users:usuario_alta_rapida"),
            {
                "tipo": "coordinador",
                "username": "coord-prohibido",
                "password": "clave-segura-123",
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(User.objects.filter(username="coord-prohibido").exists())

    def test_administrador_puede_crear_coordinador_desde_modal(self):
        admin = User.objects.create_superuser("admin-modal", "admin@example.com", "x")
        self.client.force_login(admin)
        response = self.client.post(
            reverse("users:usuario_alta_rapida"),
            {
                "tipo": "coordinador",
                "username": "coordinador-modal",
                "email": "coord-modal@example.com",
                "password": "clave-segura-123",
                "first_name": "Coordinador",
                "last_name": "Modal",
            },
        )

        self.assertEqual(response.status_code, 200)
        creado = User.objects.get(username="coordinador-modal")
        self.assertTrue(creado.groups.filter(name=ROL_COORDINADOR).exists())

    def test_ve_solo_territoriales_de_su_segmento_y_no_administra_roles(self):
        propio = User.objects.create_user("territorial-propio")
        propio.groups.add(self.rol_territorial)
        AsignacionTerritorial.objects.create(territorial=propio, segmento=self.segmento)
        ajeno = User.objects.create_user("territorial-otro")
        ajeno.groups.add(self.rol_territorial)
        AsignacionTerritorial.objects.create(territorial=ajeno, segmento=self.otro_segmento)

        usuarios = self.client.get(reverse("users:usuarios"))
        roles = self.client.get(reverse("users:roles"))

        visibles = list(usuarios.context["users"])
        self.assertIn(propio, visibles)
        self.assertNotIn(ajeno, visibles)
        self.assertEqual(roles.status_code, 302)
        self.assertContains(usuarios, reverse("users:usuarios"))
        self.assertNotContains(usuarios, reverse("users:roles"))
