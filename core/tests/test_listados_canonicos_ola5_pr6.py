"""Ola 5 · PR 6 — FE-11, FE-12 y FE-17 en los listados de Usuarios, Roles y Configuración.

Las tres fichas son la misma deuda vista desde tres lados:

- **FE-11**: `page_header`, `_estado_vacio`, `_paginacion` y `_stat_card` existían y solo las
  usaba Becas. Cada listado de afuera dibujaba su propio encabezado (`<h1 style="font-size:28px">`)
  y su propio estado vacío (`py-14 px-6 text-center` a mano).
- **FE-12**: la tabla venía con las utilidades pegadas por celda (`style="padding:13px 16px; …"`),
  el hover de fila en dos handlers inline (`onmouseenter`/`onmouseleave`) y los íconos como SVG
  Heroicons pegados en el contenido, contra la decisión D3 (Font Awesome en el contenido).
- **FE-17**: el pie de paginación estaba copiado a mano en `user_list` y, en `rol_list`, era un
  «1 de 1» **estático** con los dos botones `disabled` sobre una tabla sin paginar.

Los marcadores de arquetipo (`design_audit.py --arquetipo listado`) cubren el esqueleto; acá va
lo que ese modo no mira: que no quede markup copiado de las hermanas en ninguna de las nueve
pantallas migradas.
"""

import importlib.util
import re
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import resolve, reverse

REPO = Path(settings.BASE_DIR)

_SPEC = importlib.util.spec_from_file_location("design_audit_pr6", REPO / "scripts" / "design_audit.py")
design_audit = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(design_audit)

USUARIOS = (
    "users/templates/user/user_list.html",
    "users/templates/rol/rol_list.html",
)
CONFIGURACION = (
    "configuracion/templates/configuracion/provincia_list.html",
    "configuracion/templates/configuracion/municipio_list.html",
    "configuracion/templates/configuracion/localidad_list.html",
    "configuracion/templates/configuracion/secretaria_list.html",
    "configuracion/templates/configuracion/subsecretaria_list.html",
    "configuracion/templates/configuracion/programa_list.html",
)
LISTADOS = USUARIOS + CONFIGURACION
#: `rol_detail` no es un listado: entra como ajuste de encabezado (FE-11), no como arquetipo.
CON_PAGE_HEADER = LISTADOS + ("users/templates/rol/rol_detail.html",)

# `style=` que el inventario deja pasar: custom property, valor interpolado y `display:none`
# (el formulario oculto que postea el toggle).
STYLE_EXENTO = re.compile(r'style="\s*(?:--|[^"]*\{\{|display\s*:\s*none\s*;?\s*")')


def texto(ruta):
    return (REPO / ruta).read_text(encoding="utf-8")


class EncabezadoCanonicoTests(SimpleTestCase):
    """FE-11: el título de página es `{% page_header %}` y nada más."""

    def test_todas_usan_el_tag_canonico(self):
        for ruta in CON_PAGE_HEADER:
            with self.subTest(ruta=ruta):
                contenido = texto(ruta)
                self.assertIn("{% page_header ", contenido, f"{ruta}: falta {{% page_header %}}")
                self.assertIn("{% endpage_header %}", contenido, ruta)

    def test_ninguna_escribe_su_propio_h1(self):
        for ruta in CON_PAGE_HEADER:
            with self.subTest(ruta=ruta):
                self.assertNotIn("<h1", texto(ruta), f"{ruta}: el encabezado lo pone page_header")

    def test_ninguna_dibuja_su_estado_vacio_a_mano(self):
        for ruta in LISTADOS:
            with self.subTest(ruta=ruta):
                contenido = texto(ruta)
                self.assertIn("components/_estado_vacio.html", contenido, ruta)
                self.assertNotIn("py-14 px-6 text-center", contenido, f"{ruta}: estado vacío a mano")
                self.assertNotIn("padding:56px 24px", contenido, f"{ruta}: estado vacío a mano")


class TablaCanonicaTests(SimpleTestCase):
    """FE-12: la tabla sale de `nodo-tables.css`, no de utilidades por celda."""

    def test_las_celdas_usan_las_clases_del_sistema(self):
        for ruta in LISTADOS:
            with self.subTest(ruta=ruta):
                contenido = texto(ruta)
                self.assertIn('<tr class="nodo-thead-row">', contenido, ruta)
                self.assertIn('<th class="nodo-th', contenido, ruta)
                self.assertIn('<td class="nodo-td', contenido, ruta)

    def test_ninguna_celda_lleva_sus_utilidades_en_linea(self):
        """El `style=` por celda es lo que FE-12 mide: 94 en subsecretaria_list, 46 en user_list."""
        for ruta in LISTADOS:
            with self.subTest(ruta=ruta):
                sobrantes = [
                    linea for linea in texto(ruta).splitlines() if 'style="' in linea and not STYLE_EXENTO.search(linea)
                ]
                self.assertEqual(sobrantes, [], f"{ruta}: {len(sobrantes)} `style=` fuera del contrato")

    def test_el_hover_de_fila_no_es_un_handler_inline(self):
        for ruta in LISTADOS:
            with self.subTest(ruta=ruta):
                contenido = texto(ruta)
                for atributo in ("onmouseenter", "onmouseleave", "onmouseover", "onmouseout"):
                    self.assertNotIn(atributo, contenido, f"{ruta}: {atributo} — el hover va en la clase")

    def test_los_iconos_del_contenido_son_font_awesome(self):
        """D3: Heroicons solo en el shell. En el contenido, Font Awesome con aria-hidden."""
        for ruta in LISTADOS:
            with self.subTest(ruta=ruta):
                contenido = texto(ruta)
                self.assertNotIn("<svg", contenido, f"{ruta}: SVG inline en el contenido")
                for icono in re.finditer(r"<i\s+class=\"fa[sr] [^\"]*\"[^>]*>", contenido):
                    self.assertIn('aria-hidden="true"', icono.group(0), f"{ruta}: {icono.group(0)}")

    def test_la_accion_de_fila_nombra_el_registro(self):
        for ruta in LISTADOS:
            with self.subTest(ruta=ruta):
                contenido = texto(ruta)
                botones = re.findall(r"<(?:a|button)\b[^>]*\bnodo-icon-btn\b[^>]*>", contenido)
                self.assertTrue(botones, f"{ruta}: ninguna acción de fila usa .nodo-icon-btn")
                for boton in botones:
                    self.assertRegex(boton, r'aria-label="[^"]*\{\{', f"{ruta}: aria-label genérico en {boton}")

    def test_la_columna_de_acciones_tiene_nombre(self):
        for ruta in LISTADOS:
            with self.subTest(ruta=ruta):
                self.assertIn('<span class="sr-only">Acciones</span>', texto(ruta), ruta)


class PaginacionCanonicaTests(SimpleTestCase):
    """FE-17: ninguna pantalla escribe su propio pie, y ninguna miente con un «1 de 1»."""

    def test_ningun_pie_esta_escrito_a_mano(self):
        for ruta in LISTADOS:
            with self.subTest(ruta=ruta):
                contenido = texto(ruta)
                self.assertNotIn("page_obj.has_next", contenido, f"{ruta}: paginación a mano")
                self.assertNotIn("page_obj.has_previous", contenido, f"{ruta}: paginación a mano")

    def test_rol_list_ya_no_afirma_una_sola_pagina(self):
        contenido = texto("users/templates/rol/rol_list.html")
        self.assertNotIn("1 de 1", contenido, "el pie estático de rol_list tiene que irse")
        self.assertIn("components/_paginacion.html", contenido)

    def test_las_ocho_incluyen_la_pieza(self):
        """Las ocho, no siete: `secretaria`, `subsecretaria` y `programa` todavía no paginan
        (sus `form_invalid` arman el listado a mano, FE-04), pero el include no dibuja nada sin
        `page_obj` y así el PR 6b solo toca la vista."""
        for ruta in LISTADOS:
            with self.subTest(ruta=ruta):
                self.assertIn("components/_paginacion.html", texto(ruta), ruta)


class SinEstilosDePantallaTests(SimpleTestCase):
    """El `<style>` de 140 líneas de rol_list (buscador, kebab, menú flotante) se fue entero."""

    def test_ninguna_pantalla_trae_su_propio_bloque_de_estilos(self):
        for ruta in CON_PAGE_HEADER:
            with self.subTest(ruta=ruta):
                self.assertNotIn("<style", texto(ruta), f"{ruta}: <style> local")

    def test_rol_list_no_declara_x_cloak_propio(self):
        """`override.css` ya define `[x-cloak]` global (inventario, fila de estilos heredados)."""
        self.assertNotIn("[x-cloak]", texto("users/templates/rol/rol_list.html"))


class MarcadoresDelArquetipoTests(SimpleTestCase):
    """Las nueve pantallas tienen que pasar `design_audit.py --arquetipo listado`."""

    def test_las_nueve_clonan_el_esqueleto_de_la_golden(self):
        for ruta in LISTADOS:
            with self.subTest(ruta=ruta):
                contenido = texto(ruta)
                posicion = 0
                for patron, opcional, descripcion in design_audit.ARQUETIPOS["listado"]["marcadores"]:
                    encontrado = re.compile(patron).search(contenido, posicion)
                    if encontrado is None:
                        self.assertTrue(
                            opcional and not re.compile(patron).search(contenido),
                            f"{ruta}: falta o está fuera de orden — {descripcion}",
                        )
                        continue
                    posicion = encontrado.end()
                for patron, motivo in design_audit.ARQUETIPOS["listado"]["prohibidos"]:
                    self.assertIsNone(re.compile(patron).search(contenido), f"{ruta}: {motivo}")


class FiltrosCanonicosTests(SimpleTestCase):
    """Los controles de filtro llevan `aria-label`; el JS tira todo lo demás."""

    CON_FILTROS_SIMPLES = (
        "users/templates/rol/rol_list.html",
        "configuracion/templates/configuracion/secretaria_list.html",
        "configuracion/templates/configuracion/subsecretaria_list.html",
        "configuracion/templates/configuracion/programa_list.html",
    )

    def test_cada_control_tiene_nombre_accesible(self):
        for ruta in self.CON_FILTROS_SIMPLES:
            with self.subTest(ruta=ruta):
                contenido = texto(ruta)
                form = re.search(r"<form method=\"get\" data-dynamic-list-filters>(.*?)</form>", contenido, re.S)
                self.assertIsNotNone(form, f"{ruta}: el form de filtros no sigue el contrato")
                controles = re.findall(r"<(?:input|select)\b[^>]*>", form.group(1))
                self.assertTrue(controles, ruta)
                for control in controles:
                    self.assertIn("aria-label=", control, f"{ruta}: {control}")

    def test_el_form_de_filtros_no_lleva_clase_ni_boton_propio(self):
        for ruta in self.CON_FILTROS_SIMPLES:
            with self.subTest(ruta=ruta):
                form = re.search(
                    r"<form method=\"get\" data-dynamic-list-filters>(.*?)</form>", texto(ruta), re.S
                ).group(1)
                self.assertNotIn("<button", form, f"{ruta}: el JS tira los botones propios del form")


# --- Guarda: ningún {% url %} nombra una ruta que no existe -------------------
#
# `{% url 'x' as var %}` **no** levanta `NoReverseMatch`: deja la variable vacía y el
# enlace desaparece sin error, sin log y sin 404. Así se coló
# `configuracion:programa_list` (la ruta se llama `configuracion:programas`) y el botón
# «Limpiar filtros» del estado vacío de Programas no se dibujaba nunca. La forma sin
# `as` sí revienta, pero solo cuando alguien entra a esa pantalla.

URL_LITERAL = re.compile(r"\{%\s*url\s+(['\"])([a-zA-Z0-9_:.-]+)\1")

#: Las pantallas de `portal/templates/portal/ciudadano/` quedaron **sin ruta** y el
#: inventario del agente las declara «no son referencia»; las borra la Ola 7. Se
#: congela el conteo para que no crezcan.
PORTAL_CIUDADANO_DIR = "portal/templates/portal/ciudadano/"
PORTAL_CIUDADANO_ROTAS = 32

#: Lo roto fuera de esa carpeta, con su dueño.
URLS_ROTAS_CONOCIDAS = {
    # Parcial del shell legacy `includes/main.html`; lo retira LEG-06 (Ola 7).
    ("templates/components/widget_contactos.html", "legajos:metricas_contactos_api"),
}


def _nombres_de_url_rotos():
    from django.urls import NoReverseMatch, reverse

    raices = [REPO / "templates"] + sorted(REPO.glob("*/templates"))
    rotos = set()
    for raiz in raices:
        for archivo in sorted(raiz.rglob("*.html")):
            contenido = archivo.read_text(encoding="utf-8", errors="replace")
            for coincidencia in URL_LITERAL.finditer(contenido):
                nombre = coincidencia.group(2)
                try:
                    reverse(nombre)
                except NoReverseMatch as exc:
                    # «requires arguments» = la ruta existe; solo no se puede resolver sin ellos.
                    if "argument" in str(exc):
                        continue
                    rotos.add((archivo.relative_to(REPO).as_posix(), nombre))
    return rotos


class UrlsDeTemplatesResuelvenTests(SimpleTestCase):
    """Todo nombre literal de `{% url %}` existe en el URLconf (ratchet en dos direcciones)."""

    def test_ningun_template_nombra_una_ruta_inexistente(self):
        nuevos = sorted(
            par
            for par in _nombres_de_url_rotos()
            if par not in URLS_ROTAS_CONOCIDAS and not par[0].startswith(PORTAL_CIUDADANO_DIR)
        )
        self.assertEqual(nuevos, [], f"{len(nuevos)} nombre(s) de URL sin ruta: {nuevos}")

    def test_la_lista_de_rotas_conocidas_no_tiene_entradas_muertas(self):
        """Si alguien arregla una, el ratchet obliga a sacarla de la lista."""
        rotos = _nombres_de_url_rotos()
        resueltas = sorted(par for par in URLS_ROTAS_CONOCIDAS if par not in rotos)
        self.assertEqual(resueltas, [], f"ya resuelto(s), sacar de URLS_ROTAS_CONOCIDAS: {resueltas}")

    def test_el_portal_ciudadano_no_suma_rutas_rotas(self):
        del_portal = {par for par in _nombres_de_url_rotos() if par[0].startswith(PORTAL_CIUDADANO_DIR)}
        self.assertEqual(
            len(del_portal),
            PORTAL_CIUDADANO_ROTAS,
            f"el portal ciudadano pasó de {PORTAL_CIUDADANO_ROTAS} a {len(del_portal)} nombres sin ruta",
        )

    def test_el_barrido_ve_la_forma_con_as(self):
        """Control del andamio: `{% url 'x' as var %}` también tiene que entrar al barrido."""
        self.assertIsNotNone(URL_LITERAL.search("{% url 'configuracion:programas' as url_sin_filtros %}"))
        self.assertEqual(
            URL_LITERAL.search("{% url 'configuracion:programas' as url_sin_filtros %}").group(2),
            "configuracion:programas",
        )


# --- El botón del estado vacío existe y lleva a algún lado -------------------

#: Para cada listado: nombre de ruta y la querystring que lo deja sin filas. Las tres
#: pantallas de geografía no tienen filtros: su estado vacío es el de «no hay nada».
SIN_RESULTADOS = (
    (
        "users:usuarios",
        {"filters": '{"logic":"AND","items":[{"field":"username","op":"contains","value":"zzzz-no-existe"}]}'},
    ),
    ("users:roles", {"q": "zzzz-no-existe"}),
    ("configuracion:provincias", {}),
    ("configuracion:municipios", {}),
    ("configuracion:localidades", {}),
    ("configuracion:secretarias", {"search": "zzzz-no-existe"}),
    ("configuracion:subsecretarias", {"secretaria": "999999"}),
    ("configuracion:programas", {"q": "zzzz-no-existe"}),
)

#: El ancla que dibuja `components/_estado_vacio.html` (`mt-2` es suyo y de nadie más).
ACCION_DEL_ESTADO_VACIO = re.compile(r'<a href="([^"]*)" class="btn-nodo [^"]*mt-2">')


class EstadoVacioConBotonTests(TestCase):
    """El botón del estado vacío tiene `href` y ese `href` resuelve, en las ocho listas.

    `{% url 'x' as var %}` con un nombre inexistente deja `var` vacía: el componente
    recibe `accion_url=""`, no dibuja el ancla y nadie se entera. Es exactamente lo que
    pasaba en Programas con `configuracion:programa_list`.
    """

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser("estado-vacio-admin", "ev@chaco.gob.ar", "x")

    def setUp(self):
        self.client.force_login(self.admin)

    def _estado_vacio(self, nombre, params):
        respuesta = self.client.get(reverse(nombre), params)
        self.assertEqual(respuesta.status_code, 200, nombre)
        html = respuesta.content.decode()
        self.assertIn("py-14 px-6 text-center", html, f"{nombre}: no se renderizó el estado vacío")
        return html

    def test_las_ocho_listas_dibujan_el_boton_y_su_href_resuelve(self):
        for nombre, params in SIN_RESULTADOS:
            with self.subTest(pantalla=nombre):
                html = self._estado_vacio(nombre, params)
                enlaces = ACCION_DEL_ESTADO_VACIO.findall(html)
                self.assertTrue(enlaces, f"{nombre}: el estado vacío quedó sin botón")
                for href in enlaces:
                    self.assertTrue(href.strip(), f"{nombre}: el botón quedó con href vacío")
                    self.assertIsNotNone(resolve(href.split("?")[0]), f"{nombre}: {href} no resuelve")

    def test_la_variante_con_filtros_ofrece_limpiar_y_no_el_alta(self):
        """Con filtros la acción es terciaria («Limpiar filtros»), nunca la primaria de alta."""
        for nombre, params in SIN_RESULTADOS:
            if not params:
                continue
            with self.subTest(pantalla=nombre):
                html = self._estado_vacio(nombre, params)
                bloque = html[html.index("py-14 px-6 text-center") :][:1200]
                self.assertIn("btn-tertiary", bloque, f"{nombre}: la acción con filtros no es terciaria")
                self.assertIn("Limpiar filtros", bloque, nombre)

    def test_sin_filtros_la_accion_es_el_alta_y_apunta_a_la_pantalla_de_creacion(self):
        """Las tres de geografía: sin registros, el botón lleva al alta."""
        for nombre, destino in (
            ("configuracion:provincias", "configuracion:provincia_crear"),
            ("configuracion:municipios", "configuracion:municipio_crear"),
            ("configuracion:localidades", "configuracion:localidad_crear"),
        ):
            with self.subTest(pantalla=nombre):
                html = self._estado_vacio(nombre, {})
                self.assertIn(f'<a href="{reverse(destino)}" class="btn-nodo btn-brand btn-base mt-2">', html)
