from django.contrib.auth.models import Group, User
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

    def _request(self):
        request = RequestFactory().get("/portal/mi-perfil/")
        # Instancia fresca: la que creó el legajo ya lo tiene en su caché de relaciones.
        request.user = User.objects.get(pk=self.user.pk)
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

    def test_sin_legajo_vinculado_cierra_sesion_y_redirige_al_login(self):
        huerfano = User.objects.create_user(username="sin-legajo", password="secret")
        huerfano.groups.add(self.grupo)
        self.client.force_login(huerfano)

        respuesta = self.client.get(reverse("portal:ciudadano_mis_consultas"))

        self.assertRedirects(respuesta, reverse("portal:ciudadano_login"), fetch_redirect_response=False)
        self.assertNotIn("_auth_user_id", self.client.session)
