"""Ola 5 · PR 6 — FE-17: el listado de Roles pagina de verdad.

El pie de `rol_list.html` era HTML fijo: «1 de 1» con los dos botones `disabled`, debajo de
una tabla que renderizaba **todos** los roles visibles. Con 30 roles el pie seguía diciendo
«1 de 1» y no había forma de llegar a ninguna página: la afirmación era falsa y la lista,
ilimitada. `RolListView` ahora pagina de a 25 y la pantalla usa `components/_paginacion.html`.

Los cuatro perfiles de acceso de la pantalla ya los cubre `test_roles_abm.py`; acá va solo lo
que cambia este PR.
"""

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse

from core import rbac
from users.models import Capacidad, RolMeta
from users.views.roles import RolListView


def _perm(codigo):
    ct = ContentType.objects.get_for_model(Capacidad)
    return Permission.objects.get(codename=rbac.codename_de(codigo), content_type=ct)


class RolesPaginaDeVerdadTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin_group = Group.objects.create(name="Admins roles")
        RolMeta.objects.create(grupo=cls.admin_group, categoria="Sistema", activo=True)
        cls.admin_group.permissions.add(_perm("rol.administrar"))
        cls.admin = User.objects.create_user("admin-paginacion", password="x")
        cls.admin.groups.add(cls.admin_group)
        # 30 roles visibles (los 29 de abajo + el del propio operador) contra un tope de 25.
        for i in range(29):
            grupo = Group.objects.create(name=f"Rol {i:02d}")
            RolMeta.objects.create(grupo=grupo, categoria="Backoffice", activo=True)

    def setUp(self):
        self.client.force_login(self.admin)

    def test_la_primera_pagina_corta_en_el_tope(self):
        respuesta = self.client.get(reverse("users:roles"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(respuesta.context["items"]), RolListView.por_pagina)
        self.assertEqual(respuesta.context["page_obj"].paginator.count, 30)
        self.assertEqual(respuesta.context["page_obj"].paginator.num_pages, 2)

    def test_la_segunda_pagina_trae_el_resto_y_es_alcanzable(self):
        primera = self.client.get(reverse("users:roles"))
        self.assertContains(primera, "?page=2")
        segunda = self.client.get(reverse("users:roles"), {"page": 2})
        self.assertEqual(len(segunda.context["items"]), 30 - RolListView.por_pagina)
        en_primera = {it["group"].pk for it in primera.context["items"]}
        en_segunda = {it["group"].pk for it in segunda.context["items"]}
        self.assertFalse(en_primera & en_segunda)
        self.assertEqual(len(en_primera | en_segunda), 30)

    def test_el_pie_ya_no_afirma_una_sola_pagina(self):
        respuesta = self.client.get(reverse("users:roles"))
        self.assertNotContains(respuesta, "1 de 1")
        self.assertContains(respuesta, "Página 1 de 2")

    def test_el_filtro_viaja_a_la_pagina_siguiente(self):
        """`_paginacion.html` conserva el querystring salvo `page` (si no, filtrar y pasar de
        página devolvía la lista entera)."""
        respuesta = self.client.get(reverse("users:roles"), {"categoria": "Backoffice"})
        self.assertEqual(respuesta.context["page_obj"].paginator.count, 29)
        self.assertContains(respuesta, "categoria=Backoffice")

    def test_el_contador_lo_pone_la_pieza_y_cuenta_lo_filtrado(self):
        """El pie viejo decía «Mostrando N de total_roles»; la pieza cuenta lo que se está viendo.

        `total_roles` —el total del alcance del operador— se fue del contexto con el pie que
        lo imprimía: ningún consumidor quedó.
        """
        respuesta = self.client.get(reverse("users:roles"), {"categoria": "Backoffice"})
        self.assertNotIn("total_roles", respuesta.context)
        self.assertNotContains(respuesta, "Mostrando")
        self.assertContains(respuesta, "29 roles")


class UsuariosUsaLaPiezaDePaginacionTests(TestCase):
    """FE-17: el pie copiado de `user_list` pasa a `components/_paginacion.html`."""

    @classmethod
    def setUpTestData(cls):
        grupo = Group.objects.create(name="Admins usuarios")
        RolMeta.objects.create(grupo=grupo, categoria="Sistema", activo=True)
        grupo.permissions.add(_perm("usuario.administrar"))
        cls.admin = User.objects.create_user("admin-usuarios-pag", password="x")
        cls.admin.groups.add(grupo)
        for i in range(30):
            User.objects.create_user(f"usuario-{i:02d}", password="x")

    def setUp(self):
        self.client.force_login(self.admin)

    def test_la_pagina_1_ofrece_la_2_con_el_texto_de_la_pieza(self):
        respuesta = self.client.get(reverse("users:usuarios"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "?page=2")
        self.assertContains(respuesta, "Página 1 de")
        self.assertNotContains(respuesta, "Mostrando")

    def test_la_ultima_fila_es_alcanzable(self):
        ultima = self.client.get(reverse("users:usuarios"), {"page": 2})
        self.assertEqual(ultima.status_code, 200)
        self.assertTrue(ultima.context["page_obj"].object_list)
