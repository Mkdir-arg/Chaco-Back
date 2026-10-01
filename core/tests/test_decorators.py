from django.contrib.auth.models import AnonymousUser, Group, User
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.urls import reverse

from core.decorators import ciudadano_required
from core.rbac import es_ciudadano_portal
from legajos.models import Ciudadano


class CiudadanoRequiredTests(TestCase):
    def setUp(self):
        self.grupo = Group.objects.create(name="Ciudadanos")
        self.user = User.objects.create_user(username="30111222", password="secret")
        self.user.groups.add(self.grupo)
        self.ciudadano = Ciudadano.objects.create(dni="30111222", nombre="Ana", apellido="Perez", usuario=self.user)

    def _request(self, user=None):
        # SEC-29: las vistas con este decorador ya no tienen ruta publicada, así que
        # el decorador se ejercita directo sobre un request armado a mano.
        request = RequestFactory().get("/portal/")
        SessionMiddleware(lambda r: HttpResponse()).process_request(request)
        MessageMiddleware(lambda r: HttpResponse()).process_request(request)
        # Instancia fresca: la que creó el legajo ya lo tiene en su caché de relaciones.
        request.user = user if user is not None else User.objects.get(pk=self.user.pk)
        # Grupos ya resueltos, como los deja el middleware del portal en un request real.
        es_ciudadano_portal(request.user)
        return request

    def test_lee_el_legajo_una_vez_y_lo_deja_cacheado_para_la_vista(self):
        visto = {}

        @ciudadano_required
        def vista(request):
            # El decorador ya leyó el legajo: la vista lo encuentra sin volver a la base.
            with self.assertNumQueries(0):
                visto["ciudadano"] = request.user.ciudadano_perfil
                visto["usuario"] = request.user.ciudadano_perfil.usuario
            return HttpResponse("ok")

        request = self._request()

        with self.assertNumQueries(1):
            respuesta = vista(request)

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(visto["ciudadano"], self.ciudadano)
        self.assertIs(visto["usuario"], request.user)

    def test_sin_legajo_vinculado_cierra_sesion_y_redirige_a_la_home_del_portal(self):
        huerfano = User.objects.create_user(username="sin-legajo", password="secret")  # nosec B106
        huerfano.groups.add(self.grupo)

        @ciudadano_required
        def vista(request):
            return HttpResponse("no debería llegar")

        request = self._request(user=huerfano)
        request.session["_auth_user_id"] = str(huerfano.pk)

        respuesta = vista(request)

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta["Location"], reverse("portal:home"))
        self.assertNotIn("_auth_user_id", request.session)

    def test_quien_no_es_ciudadano_del_portal_va_a_la_home_del_portal(self):
        """SEC-29: el login del portal ya no existe; el decorador manda a portal:home."""

        @ciudadano_required
        def vista(request):
            return HttpResponse("no debería llegar")

        request = self._request(user=AnonymousUser())

        respuesta = vista(request)

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta["Location"], reverse("portal:home"))
