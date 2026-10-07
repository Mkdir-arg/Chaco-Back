"""`/becas/` tiene índice y no da 404 (#521, QA de testing 06/10/2026).

`programas/urls.py` no tenía ruta `""`: la raíz del módulo más grande del
sistema era un 404 para cualquiera, incluido un superusuario. Ahora redirige al
primer listado que el usuario puede ver, con el mismo orden que el link
«Programas» del sidebar colapsado.
"""

from io import StringIO

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from core import rbac
from users.models import Capacidad, RolMeta


def _rol_con(nombre, codigos):
    grupo = Group.objects.create(name=nombre)
    RolMeta.objects.create(grupo=grupo, categoria=rbac.CATEGORIA_BACKOFFICE, activo=True)
    ct = ContentType.objects.get_for_model(Capacidad)
    for codigo in codigos:
        grupo.permissions.add(Permission.objects.get(codename=rbac.codename_de(codigo), content_type=ct))
    return grupo


class InicioBecasTests(TestCase):
    URL = "/becas/"

    def test_la_ruta_existe(self):
        self.assertEqual(reverse("becas:inicio"), self.URL)

    def test_anonimo_va_al_login(self):
        respuesta = self.client.get(self.URL)

        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse("users:login"), respuesta["Location"])

    def test_usuario_sin_rol_vuelve_al_inicio_con_mensaje(self):
        """El mismo comportamiento que el resto de Becas: ni 404 ni 500."""
        self.client.force_login(User.objects.create_user("sin-rol-becas", password="Clave-Seg-2026x"))

        respuesta = self.client.get(self.URL)

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta["Location"], reverse("core:inicio"))
        self.assertEqual(
            [str(m) for m in respuesta.wsgi_request._messages],
            ["No tiene permisos para acceder a esta sección."],
        )

    def test_las_capacidades_son_las_que_exigen_los_listados(self):
        """`inicio_becas` repite los códigos en literal para no importar otras vistas
        (ratchet de `CapasTests`): acá se verifica que no se despeguen."""
        from programas.views.configuracion import CAP_SEGMENTO_VER
        from programas.views.inicio_becas import DESTINOS
        from programas.views.relevamientos import CAP_CONVOCATORIA_VER, CAP_RELEVAMIENTO_VER
        from programas.views.revision import CAP_REVISION_VER

        self.assertEqual(
            [capacidad for capacidad, _ in DESTINOS],
            [CAP_SEGMENTO_VER, CAP_CONVOCATORIA_VER, CAP_RELEVAMIENTO_VER, CAP_REVISION_VER],
        )

    def test_cada_capacidad_lleva_a_su_listado(self):
        casos = (
            ("becas.segmento.ver", "becas:segmentos"),
            ("becas.convocatoria.ver", "becas:convocatorias"),
            ("becas.relevamiento.ver", "becas:relevamientos"),
            ("becas.revision.ver", "becas:revision"),
        )
        for capacidad, destino in casos:
            with self.subTest(capacidad=capacidad):
                usuario = User.objects.create_user(f"solo-{capacidad}", password="Clave-Seg-2026x")
                usuario.groups.add(_rol_con(f"Rol {capacidad}", [capacidad]))
                self.client.force_login(usuario)

                respuesta = self.client.get(self.URL)

                self.assertEqual(respuesta.status_code, 302)
                self.assertEqual(respuesta["Location"], reverse(destino))

    def test_superusuario_entra(self):
        self.client.force_login(User.objects.create_superuser("root-becas", "root@example.com", "Clave-Seg-2026x"))

        respuesta = self.client.get(self.URL)

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta["Location"], reverse("becas:segmentos"))

    def test_sigue_el_redirect_sin_404(self):
        """Un rol de Becas aterriza en una pantalla real, no en otro error."""
        # `convocatorias_visibles` exige el programa BECAS configurado (si no, 403
        # de `autorizacion.programa_becas`): este test sigue el redirect de punta a
        # punta, así que necesita el seed.
        call_command("seed_becas", stdout=StringIO())
        usuario = User.objects.create_user("coord-becas-inicio", password="Clave-Seg-2026x")
        usuario.groups.add(_rol_con("Rol listado convocatorias", ["becas.convocatoria.ver"]))
        self.client.force_login(usuario)

        respuesta = self.client.get(self.URL, follow=True)

        self.assertEqual(respuesta.status_code, 200)
