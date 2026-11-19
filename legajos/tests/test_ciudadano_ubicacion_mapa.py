"""Domicilio con mapa en el legajo del ciudadano (Cambio 493, fase 2).

Latitud y longitud nuevas en `Ciudadano`; las completa el mapa del backoffice en las tres
pantallas de carga (alta manual, confirmación con RENAPER y edición), siempre **a pedido**
(SEC-33): abrir el legajo no le manda la ubicación de la persona a Google. El portal no las toca.
"""

from decimal import Decimal

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase, override_settings
from django.urls import reverse

from core import rbac
from legajos.forms import CiudadanoConfirmarForm, CiudadanoManualForm, CiudadanoUpdateForm
from legajos.models import Ciudadano
from portal.forms.ciudadano import CiudadanoEditarDatosForm
from users.models import Capacidad, RolMeta


class CoordenadasDelCiudadanoTests(TestCase):
    def test_son_opcionales_y_guardan_seis_decimales(self):
        sin_punto = Ciudadano.objects.create(dni="20111222", nombre="Ana", apellido="Paz")
        self.assertIsNone(sin_punto.latitud)
        self.assertIsNone(sin_punto.longitud)

        con_punto = Ciudadano.objects.create(
            dni="20111223", nombre="Luis", apellido="Gil", latitud=Decimal("-27.451198"), longitud=Decimal("-58.986695")
        )
        con_punto.refresh_from_db()
        self.assertEqual((con_punto.latitud, con_punto.longitud), (Decimal("-27.451198"), Decimal("-58.986695")))

    def test_los_formularios_del_backoffice_las_piden_y_el_portal_no(self):
        for form_class in (CiudadanoManualForm, CiudadanoConfirmarForm, CiudadanoUpdateForm):
            campos = form_class().fields
            self.assertIn("latitud", campos, form_class.__name__)
            self.assertIn("longitud", campos, form_class.__name__)
            self.assertFalse(campos["latitud"].required)
        self.assertNotIn("latitud", CiudadanoEditarDatosForm.Meta.fields)

    def _form(self, **coordenadas):
        return CiudadanoManualForm(data={"dni": "30555666", "nombre": "Ana", "apellido": "Paz", **coordenadas})

    def test_fuera_de_rango_vuelve_al_campo(self):
        form = self._form(latitud="500", longitud="-58.9")
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors["latitud"], ["La latitud va de -90 a 90."])

        form = self._form(latitud="-27.4", longitud="-181")
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors["longitud"], ["La longitud va de -180 a 180."])

    def test_una_sola_coordenada_no_se_guarda(self):
        for coordenadas in ({"latitud": "-27.4"}, {"longitud": "-58.9"}):
            form = self._form(**coordenadas)
            self.assertFalse(form.is_valid(), coordenadas)
            self.assertEqual(form.errors["latitud"], ["Cargá latitud y longitud, o ninguna de las dos."])

    def test_las_dos_o_ninguna_pasan(self):
        self.assertTrue(self._form(latitud="-27.451198", longitud="-58.986695").is_valid())
        self.assertTrue(self._form().is_valid())


@override_settings(GOOGLE_MAPS_API_KEY="AIza-prueba", GOOGLE_MAPS_MAP_ID="mapa-chaco")
class PantallasConMapaTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="operador-mapa", password="clave-segura-123", is_staff=True)
        rol = Group.objects.create(name="Operador mapa")
        RolMeta.objects.create(grupo=rol, categoria="Backoffice", activo=True)
        ct = ContentType.objects.get_for_model(Capacidad)
        for codigo in ("ciudadano.ver", "ciudadano.crear", "ciudadano.editar"):
            rol.permissions.add(Permission.objects.get(content_type=ct, codename=rbac.codename_de(codigo)))
        self.user.groups.add(rol)
        self.client.force_login(self.user)
        self.ciudadano = Ciudadano.objects.create(
            dni="30111222", nombre="Ana", apellido="Paz", latitud=Decimal("-27.451198"), longitud=Decimal("-58.986695")
        )

    def _assert_pieza_a_pedido(self, respuesta):
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "data-nodo-ubicacion")
        self.assertContains(respuesta, "data-a-pedido")
        self.assertContains(respuesta, "custom/js/nodo-ubicacion.js")
        self.assertContains(respuesta, "custom/css/nodo-ubicacion.css")
        self.assertContains(respuesta, 'id="nodo-mapa-config"')
        html = respuesta.content.decode()
        for nombre in ("domicilio", "latitud", "longitud"):
            self.assertEqual(html.count(f'name="{nombre}"'), 1, nombre)

    def test_la_edicion_trae_la_pieza_a_pedido_con_provincia_y_localidad(self):
        respuesta = self.client.get(reverse("legajos:ciudadano_editar", args=[self.ciudadano.pk]))

        self._assert_pieza_a_pedido(respuesta)
        self.assertContains(respuesta, 'data-localidad="id_localidad"')
        self.assertContains(respuesta, 'data-provincia-id="id_provincia"')
        self.assertContains(respuesta, 'value="-27.451198"')

    def test_el_alta_manual_trae_la_pieza_a_pedido(self):
        self._assert_pieza_a_pedido(self.client.get(reverse("legajos:ciudadano_manual")))

    def test_la_edicion_guarda_las_coordenadas_del_mapa(self):
        url = reverse("legajos:ciudadano_editar", args=[self.ciudadano.pk])
        form = self.client.get(url).context["form"]
        datos = {
            nombre: (valor if valor is not None else "")
            for nombre, valor in ((n, form[n].value()) for n in form.fields)
            if not form.fields[nombre].disabled and nombre != "foto"
        }
        datos.update({"domicilio": "Av. Sarmiento 1250", "latitud": "-27.458427", "longitud": "-58.995889"})

        respuesta = self.client.post(url, datos)

        self.assertEqual(respuesta.status_code, 302)
        self.ciudadano.refresh_from_db()
        self.assertEqual(
            (self.ciudadano.domicilio, self.ciudadano.latitud, self.ciudadano.longitud),
            ("Av. Sarmiento 1250", Decimal("-27.458427"), Decimal("-58.995889")),
        )

    def test_el_alta_manual_guarda_las_coordenadas(self):
        respuesta = self.client.post(
            reverse("legajos:ciudadano_manual"),
            {
                "dni": "30999888",
                "nombre": "Luis",
                "apellido": "Gil",
                "genero": "M",
                "domicilio": "Mitre 10",
                "latitud": "-27.440000",
                "longitud": "-58.970000",
            },
        )

        self.assertEqual(respuesta.status_code, 302)
        nuevo = Ciudadano.objects.get(dni="30999888")
        self.assertEqual((nuevo.latitud, nuevo.longitud), (Decimal("-27.440000"), Decimal("-58.970000")))
