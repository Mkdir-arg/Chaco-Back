"""RED-73 (auditoría oct-2026): confirmar el alta autoriza antes de precondicionar.

`CiudadanoConfirmarView.dispatch` miraba la sesión de RENAPER y redirigía a
`legajos:ciudadano_nuevo` **antes** de llamar a `super().dispatch()`, que es donde
corren `CapacidadRequeridaMixin` y `LoginRequiredMixin`. No había fuga —lee la
sesión del propio solicitante— pero era la única ruta de todo el barrido del
URLconf que no rebotaba al anónimo (`core/tests/test_superficie_publica.py`), le
armaba una sesión anónima para colgar el `messages.error`, y sobre todo era el
molde equivocado: cualquier precondición puesta arriba de `super().dispatch()`
corre antes de la autorización.
"""

from urllib.parse import parse_qs, urlparse

from django.conf import settings
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse

from core import rbac
from users.models import Capacidad, RolMeta

URL_CONFIRMAR = "/legajos/ciudadanos/confirmar/"


class ConfirmarTests(TestCase):
    def test_un_anonimo_va_al_login_no_al_alta(self):
        respuesta = self.client.get(URL_CONFIRMAR)

        self.assertEqual(respuesta.status_code, 302)
        destino = urlparse(respuesta["Location"])
        # El login vive en la raíz, así que la comparación es por path exacto.
        self.assertEqual(destino.path, reverse(settings.LOGIN_URL))
        self.assertEqual(parse_qs(destino.query).get("next"), [URL_CONFIRMAR])

    def test_sin_capacidad_no_llega_al_alta_aunque_no_haya_datos_de_renaper(self):
        """La capacidad se evalúa primero; recién después la precondición."""
        mirón = User.objects.create_user("miron_confirmar", password="x")
        self.client.force_login(mirón)

        respuesta = self.client.get(URL_CONFIRMAR)

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta["Location"], reverse("core:inicio"))

    def test_sin_capacidad_por_ajax_da_403(self):
        """El contrato real de `_respuesta_sin_permiso` para fetch (no el redirect)."""
        mirón = User.objects.create_user("miron_ajax_confirmar", password="x")
        self.client.force_login(mirón)

        respuesta = self.client.get(URL_CONFIRMAR, headers={"x-requested-with": "XMLHttpRequest"})

        self.assertEqual(respuesta.status_code, 403)

    def test_con_capacidad_y_sin_datos_de_renaper_vuelve_al_alta(self):
        """La precondición sigue viva para quien sí puede crear ciudadanos."""
        operador = User.objects.create_user("operador_confirmar", password="x")
        rol = Group.objects.create(name="Alta de ciudadanos (test)")
        RolMeta.objects.create(grupo=rol, categoria="Backoffice", activo=True)
        rol.permissions.add(
            Permission.objects.get(
                content_type=ContentType.objects.get_for_model(Capacidad),
                codename=rbac.codename_de("ciudadano.crear"),
            )
        )
        operador.groups.add(rol)
        self.client.force_login(operador)

        respuesta = self.client.get(URL_CONFIRMAR)

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta["Location"], reverse("legajos:ciudadano_nuevo"))
