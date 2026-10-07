"""Ola 5 · PR 6b — FE-11, FE-12 y FE-17 en `legajos/ciudadano_list.html`.

Es el punto (4) de FE-11, el único archivo de FE-12 que quedó fuera del PR 6a: 492 líneas
con un `<style>` de 290 que redefinía a mano el encabezado (`.cl-h1`, 28 px), las seis
tarjetas de número (cajas de 52 px y avatares con `var(--gradient-brand)`), la barra de
búsqueda, la tabla, el pie de paginación y el estado vacío —todo lo que ya existe como
pieza canónica—, más ocho SVG de Heroicons pegados en el contenido.

De FE-17, acá vive la otra paginación mal armada: el enlace llevaba
`&search={{ search_value }}` **sin codificar**, así que buscar «Pérez Gómez» y pasar de
página perdía el filtro (y un `&` en la búsqueda cortaba el querystring).
"""

import importlib.util
import re
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import SimpleTestCase, TestCase
from django.urls import resolve, reverse

from core import rbac
from legajos.models import Ciudadano
from users.models import Capacidad, RolMeta

REPO = Path(settings.BASE_DIR)
PANTALLA = "legajos/templates/legajos/ciudadano_list.html"

_SPEC = importlib.util.spec_from_file_location("design_audit_pr6b", REPO / "scripts" / "design_audit.py")
design_audit = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(design_audit)

# `style=` que el inventario deja pasar: custom property, valor interpolado y `display:none`.
STYLE_EXENTO = re.compile(r'style="\s*(?:--|[^"]*\{\{|display\s*:\s*none\s*;?\s*")')


def texto(ruta=PANTALLA):
    return (REPO / ruta).read_text(encoding="utf-8")


def usuario_con(*codigos, username=None):
    """Usuario de backoffice con exactamente esas capacidades."""
    nombre_rol = "Rol 6b " + ("-".join(codigos) or "sin-capacidades")
    grupo, _ = Group.objects.get_or_create(name=nombre_rol)
    RolMeta.objects.get_or_create(grupo=grupo, defaults={"categoria": rbac.CATEGORIA_BACKOFFICE, "activo": True})
    ct = ContentType.objects.get_for_model(Capacidad)
    for codigo in codigos:
        grupo.permissions.add(Permission.objects.get(codename=rbac.codename_de(codigo), content_type=ct))
    usuario = User.objects.create_user(username or f"u-{nombre_rol}", password="Clave-Seg-2026x")
    usuario.groups.add(grupo)
    return usuario


class PantallaCanonicaTests(SimpleTestCase):
    """FE-11 y FE-12: nada de lo que la pantalla dibujaba a mano sobrevive."""

    def test_usa_el_encabezado_canonico_y_no_escribe_su_propio_h1(self):
        contenido = texto()

        self.assertIn("{% page_header ", contenido)
        self.assertIn("{% endpage_header %}", contenido)
        self.assertNotIn("<h1", contenido)

    def test_no_queda_bloque_de_estilos_ni_utilidades_en_linea(self):
        contenido = texto()

        self.assertNotIn("<style", contenido)
        self.assertEqual([m for m in re.findall(r'style="[^"]*"', contenido) if not STYLE_EXENTO.match(m)], [])

    def test_no_queda_ninguna_clase_de_pantalla(self):
        """Las 25 clases `cl-*` del `<style>` eran el diseño paralelo de esta pantalla."""
        self.assertEqual(re.findall(r"\bcl-[a-z-]+", texto()), [])

    def test_los_iconos_del_contenido_son_font_awesome(self):
        contenido = texto()

        self.assertNotIn("<svg", contenido)
        for icono in re.findall(r'<i class="fas [^"]*"[^>]*>', contenido):
            self.assertIn('aria-hidden="true"', icono)

    def test_la_tabla_usa_las_clases_del_sistema(self):
        contenido = texto()

        self.assertIn('<table class="w-full border-collapse">', contenido)
        self.assertIn('<tr class="nodo-thead-row">', contenido)
        self.assertIn('<th class="nodo-th', contenido)
        self.assertIn('<td class="nodo-td', contenido)
        self.assertIn('<span class="sr-only">Acciones</span>', contenido)
        self.assertIn("hover:bg-secondary", contenido)

    def test_las_piezas_canonicas_reemplazan_a_las_copias(self):
        contenido = texto()

        self.assertIn('{% include "components/_stat_card.html"', contenido)
        self.assertIn('{% include "components/_paginacion.html"', contenido)
        self.assertIn('{% include "components/_estado_vacio.html"', contenido)
        self.assertNotIn("page_obj.has_next", contenido)
        self.assertNotIn("py-14 px-6 text-center", contenido)

    def test_el_avatar_no_usa_el_gradiente_de_marca(self):
        """D5 del agente: las iniciales van `bg-brand-soft text-fg-brand`."""
        contenido = texto()

        self.assertNotIn("--gradient-brand", contenido)
        self.assertIn("rounded-full bg-brand-soft text-fg-brand", contenido)

    def test_pasa_los_marcadores_del_arquetipo_listado(self):
        self.assertEqual(design_audit.arquetipo_mode("listado", [PANTALLA]), 0)

    def test_el_form_de_filtros_cumple_el_contrato(self):
        contenido = texto()
        form = re.search(r"<form[^>]*data-dynamic-list-filters[^>]*>", contenido)

        self.assertIsNotNone(form)
        self.assertNotIn("class=", form.group(0))
        self.assertIn('name="search"', contenido)
        self.assertIn('aria-label="Buscar ciudadanos"', contenido)


class CiudadanosListadoPorHttpTests(TestCase):
    """Lo que el test estático no ve: que la pantalla siga sirviendo para lo mismo."""

    @classmethod
    def setUpTestData(cls):
        cls.url = reverse("legajos:ciudadanos")
        for indice in range(3):
            Ciudadano.objects.create(dni=f"3000000{indice}", nombre=f"Ana{indice}", apellido="Pérez & Gómez")

    def _html(self, usuario, query="", por_pagina=2):
        from legajos.views.ciudadanos import CiudadanoListView

        self.client.force_login(usuario)
        with mock.patch.object(CiudadanoListView, "paginate_by", por_pagina):
            respuesta = self.client.get(self.url + query)
        self.assertEqual(respuesta.status_code, 200)
        return respuesta

    def test_anonimo_va_al_login(self):
        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(resolve(respuesta.url.split("?")[0]).url_name, {"login"})

    def test_cuenta_sin_rol_no_entra(self):
        """`CapacidadRequeridaMixin` no devuelve 403 acá: redirige al inicio con aviso."""
        self.client.force_login(usuario_con())
        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta.url, reverse("core:inicio"))

    def test_con_la_capacidad_justa_entra_y_no_ofrece_el_alta(self):
        respuesta = self._html(usuario_con("ciudadano.ver"))

        self.assertFalse(respuesta.context["puede_crear"])
        self.assertNotIn(reverse("legajos:ciudadano_nuevo"), respuesta.content.decode())

    def test_con_la_capacidad_de_alta_aparece_el_boton(self):
        respuesta = self._html(usuario_con("ciudadano.ver", "ciudadano.crear"))

        self.assertTrue(respuesta.context["puede_crear"])
        self.assertIn(reverse("legajos:ciudadano_nuevo"), respuesta.content.decode())

    def test_el_superusuario_entra(self):
        admin = User.objects.create_superuser("admin-cl-6b", password="x")

        self.assertTrue(self._html(admin).context["puede_crear"])

    def test_la_busqueda_viaja_codificada_a_la_pagina_siguiente(self):
        """FE-17: antes salía `&search=Pérez & Gómez` crudo y la 2ª página perdía el filtro."""
        admin = User.objects.create_superuser("admin-cl-6b-qs", password="x")
        html = self._html(admin, "?search=" + "P%C3%A9rez+%26+G%C3%B3mez").content.decode()

        self.assertIn("search=P%C3%A9rez+%26+G%C3%B3mez", html)
        self.assertNotIn("search=Pérez & Gómez", html)

    def test_la_ultima_fila_es_alcanzable(self):
        admin = User.objects.create_superuser("admin-cl-6b-pag", password="x")

        self.assertIn("Página 1 de 2 · 3 ciudadanos", self._html(admin).content.decode())
        self.assertEqual(len(self._html(admin, "?page=2").context["ciudadanos"]), 1)

    def test_sin_resultados_por_la_busqueda_ofrece_limpiar_filtros(self):
        admin = User.objects.create_superuser("admin-cl-6b-vacio", password="x")
        html = self._html(admin, "?search=zzzzzz").content.decode()

        self.assertIn("Limpiar filtros", html)
        self.assertIn(f'href="{self.url}"', html)
        self.assertNotIn("Agregar ciudadano", html)

    def test_sin_ciudadanos_y_sin_capacidad_el_estado_vacio_no_ofrece_el_alta(self):
        """El estado vacío apunta al mismo destino que el botón del encabezado: se gatea igual."""
        Ciudadano.objects.all().delete()
        html = self._html(usuario_con("ciudadano.ver", username="u-solo-ver-vacio")).content.decode()

        self.assertIn("No hay ciudadanos registrados", html)
        self.assertNotIn(reverse("legajos:ciudadano_nuevo"), html)

    def test_sin_ciudadanos_ofrece_el_alta(self):
        Ciudadano.objects.all().delete()
        admin = User.objects.create_superuser("admin-cl-6b-cero", password="x")
        html = self._html(admin).content.decode()

        self.assertIn("No hay ciudadanos registrados", html)
        self.assertIn(f'href="{reverse("legajos:ciudadano_nuevo")}"', html)

    def test_el_exportar_csv_conserva_la_busqueda(self):
        admin = User.objects.create_superuser("admin-cl-6b-csv", password="x")
        html = self._html(admin, "?search=ana").content.decode()

        self.assertIn(f"{reverse('legajos:ciudadanos_exportar_csv')}?search=ana", html)
