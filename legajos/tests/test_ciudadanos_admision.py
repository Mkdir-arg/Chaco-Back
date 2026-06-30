from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse

from core import rbac
from legajos.forms import CiudadanoConfirmarForm, CiudadanoManualForm
from legajos.models import Ciudadano
from legajos.services import CiudadanosService
from users.models import Capacidad, RolMeta


class LegajosCiudadanosAdmisionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="operador-legajos",
            password="clave-segura-123",
            is_staff=True,
        )
        # El alta de ciudadanos exige la capacidad ciudadano.crear (RBAC).
        rol = Group.objects.create(name="Operador legajos")
        RolMeta.objects.create(grupo=rol, categoria="Backoffice", activo=True)
        _ct = ContentType.objects.get_for_model(Capacidad)
        rol.permissions.add(Permission.objects.get(content_type=_ct, codename=rbac.codename_de("ciudadano.crear")))
        self.user.groups.add(rol)
        self.ciudadano = Ciudadano.objects.create(
            dni="12345678",
            nombre="Ana",
            apellido="Perez",
            genero=Ciudadano.Genero.FEMENINO,
        )

    def test_ciudadano_forms_define_dni_widget_per_context(self):
        manual_form = CiudadanoManualForm()
        confirm_form = CiudadanoConfirmarForm()

        self.assertNotIn("readonly", manual_form.fields["dni"].widget.attrs)
        self.assertEqual(
            confirm_form.fields["dni"].widget.attrs.get("readonly"),
            True,
        )

    def test_store_and_clear_renaper_data(self):
        session = {}
        resultado = {
            "data": {"dni": "12345678", "nombre": "Ana"},
            "datos_api": {"apellido": "Perez"},
        }

        CiudadanosService.store_renaper_data(session, resultado)

        self.assertEqual(
            CiudadanosService.get_renaper_data(session)["dni"],
            "12345678",
        )
        self.assertEqual(
            CiudadanosService.get_renaper_raw_data(session)["apellido"],
            "Perez",
        )

        CiudadanosService.clear_renaper_data(session)

        self.assertEqual(CiudadanosService.get_renaper_data(session), {})
        self.assertEqual(CiudadanosService.get_renaper_raw_data(session), {})

    def test_ciudadano_confirmar_requires_renaper_session(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("legajos:ciudadano_confirmar"))

        self.assertRedirects(response, reverse("legajos:ciudadano_nuevo"))
