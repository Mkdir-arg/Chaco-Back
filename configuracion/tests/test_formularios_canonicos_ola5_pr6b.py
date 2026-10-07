"""Ola 5 · PR 6b — FE-20: Configuración y las páginas de error salen del shell legacy.

`templates/includes/main.html` es el wrapper heredado de AdminLTE: envuelve el contenido
en `app-main > app-content-header > container-fluid > row > col-sm-9`, cuatro clases que
**el build de Tailwind no genera** (anexo `anexo-front-clases-inexistentes.md`), así que el
contenido quedaba corrido —el `<h1>` de `/configuracion/localidades/crear/` medido en
x=644, contra x=320 en la lista— y las tres páginas de error salían como texto plano.

Sus 17 consumidores eran los 14 templates de Configuración (`*_form`, `*_confirm_delete`
y los cuatro pasos del wizard) y `templates/{403,404,500}.html`. Con los 17 migrados, el
shell se borra y las tres entradas de la allowlist de `compile_templates --bloques`
—`menu-adicional` de las páginas de error, que ningún ancestro declaraba— desaparecen.

El wizard **no tiene golden** (D4 del agente): se migra el shell y el formulario de cada
paso, sin inventar un stepper. La barra de progreso que ya existía se conserva.
"""

import importlib.util
import re
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from core import rbac
from core.models import Localidad, Municipio, Provincia, Secretaria, Subsecretaria
from users.models import Capacidad, RolMeta

REPO = Path(settings.BASE_DIR)

_SPEC = importlib.util.spec_from_file_location("design_audit_fe20", REPO / "scripts" / "design_audit.py")
design_audit = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(design_audit)

BASE_CONFIG = "configuracion/templates/configuracion/"
FORMULARIOS = tuple(
    f"{BASE_CONFIG}{entidad}_form.html"
    for entidad in ("provincia", "municipio", "localidad", "secretaria", "subsecretaria")
)
BORRADOS = tuple(
    f"{BASE_CONFIG}{entidad}_confirm_delete.html"
    for entidad in ("provincia", "municipio", "localidad", "secretaria", "subsecretaria")
)
WIZARD = tuple(f"{BASE_CONFIG}programa_wizard_paso{n}.html" for n in (1, 2, 3, 4))
ERRORES = ("templates/403.html", "templates/404.html", "templates/500.html")
#: Los 17 consumidores que tenía `templates/includes/main.html`.
CONSUMIDORES_DEL_SHELL_LEGACY = FORMULARIOS + BORRADOS + WIZARD + ERRORES

STYLE_EXENTO = re.compile(r'style="\s*(?:--|[^"]*\{\{|display\s*:\s*none\s*;?\s*")')


def texto(ruta):
    return (REPO / ruta).read_text(encoding="utf-8")


def usuario_con(*codigos, username=None):
    usuario = User.objects.create_user(username or f"f20-{'-'.join(codigos) or 'sin-rol'}", password="Clave-Seg-2026x")
    if not codigos:
        return usuario
    grupo, _ = Group.objects.get_or_create(name="Rol FE-20 " + "-".join(codigos))
    RolMeta.objects.get_or_create(grupo=grupo, defaults={"categoria": rbac.CATEGORIA_BACKOFFICE, "activo": True})
    ct = ContentType.objects.get_for_model(Capacidad)
    for codigo in codigos:
        grupo.permissions.add(Permission.objects.get(codename=rbac.codename_de(codigo), content_type=ct))
    usuario.groups.add(grupo)
    return usuario


class ShellLegacyRetiradoTests(SimpleTestCase):
    """El wrapper heredado se queda sin consumidores y se borra."""

    def test_el_archivo_del_shell_legacy_ya_no_existe(self):
        self.assertFalse((REPO / "templates/includes/main.html").exists())

    def test_ningun_template_del_repo_lo_extiende(self):
        candidatos = [p for p in REPO.rglob("*.html") if ".claude" not in p.parts and "node_modules" not in p.parts]
        culpables = [
            p.relative_to(REPO).as_posix()
            for p in candidatos
            if 'extends "includes/main.html"' in p.read_text(encoding="utf-8", errors="replace")
        ]

        self.assertEqual(culpables, [])

    def test_los_diecisiete_extienden_el_shell_del_backoffice(self):
        for ruta in CONSUMIDORES_DEL_SHELL_LEGACY:
            with self.subTest(ruta=ruta):
                contenido = texto(ruta)
                self.assertIn('{% extends "includes/base.html" %}', contenido)
                self.assertIn("{% block main-content %}", contenido)

    def test_la_allowlist_de_bloques_sin_destino_pierde_las_tres_paginas_de_error(self):
        """Los `{% block menu-adicional %}` existían solo porque el wrapper no lo declaraba."""
        from scripts.compile_templates import BLOQUES_SIN_DESTINO_CONOCIDOS

        for pagina in ("403.html", "404.html", "500.html"):
            self.assertNotIn((pagina, "menu-adicional"), BLOQUES_SIN_DESTINO_CONOCIDOS)

    def test_ninguna_usa_las_clases_que_el_build_no_genera(self):
        muertas = ("app-content", "container-fluid", "col-sm-9", "col-sm-3", "float-sm-end", "error-page", "headline")
        for ruta in CONSUMIDORES_DEL_SHELL_LEGACY:
            with self.subTest(ruta=ruta):
                contenido = texto(ruta)
                for clase in muertas:
                    self.assertNotIn(clase, contenido)


class FormulariosCanonicosTests(SimpleTestCase):
    """Los cinco `*_form` clonan la golden del arquetipo Formulario."""

    def test_pasan_los_marcadores_del_arquetipo(self):
        self.assertEqual(design_audit.arquetipo_mode("formulario", list(FORMULARIOS)), 0)

    def test_los_campos_salen_del_include_y_no_de_labels_a_mano(self):
        for ruta in FORMULARIOS:
            with self.subTest(ruta=ruta):
                contenido = texto(ruta)
                self.assertIn('{% include "programas/becas/_field.html" %}', contenido)
                self.assertNotIn("id_for_label", contenido)
                self.assertNotIn("field.errors", contenido)

    def test_los_errores_no_de_campo_salen_de_la_pieza(self):
        for ruta in FORMULARIOS + WIZARD:
            with self.subTest(ruta=ruta):
                self.assertIn('{% include "components/_form_errores.html" %}', texto(ruta))

    def test_ninguno_escribe_su_propio_h1_ni_su_paleta(self):
        for ruta in FORMULARIOS + BORRADOS + WIZARD + ERRORES:
            with self.subTest(ruta=ruta):
                contenido = texto(ruta)
                self.assertNotIn("<h1", contenido)
                self.assertNotIn("<style", contenido)
                self.assertEqual(design_audit._p1_rawpalette(ruta, contenido), [])
                self.assertEqual([m for m in re.findall(r'style="[^"]*"', contenido) if not STYLE_EXENTO.match(m)], [])


class BorradosConAvisoTests(SimpleTestCase):
    """Variante «confirmación de borrado» de la ficha del arquetipo Formulario."""

    def test_el_riesgo_se_explica_con_la_pieza_de_alerta(self):
        for ruta in BORRADOS:
            with self.subTest(ruta=ruta):
                contenido = texto(ruta)
                self.assertIn('{% include "components/_alerta.html" with tono="danger"', contenido)
                self.assertIn("btn-nodo btn-danger btn-base", contenido)
                self.assertNotIn("btn-nodo btn-brand", contenido)


class PaginasDeErrorTests(SimpleTestCase):
    """V5A-NEW-03: las tres salían como texto plano de 16 px."""

    def test_usan_el_encabezado_y_el_estado_vacio_canonicos(self):
        for ruta in ERRORES:
            with self.subTest(ruta=ruta):
                contenido = texto(ruta)
                self.assertIn("{% page_header ", contenido)
                self.assertIn('{% include "components/_estado_vacio.html"', contenido)
                self.assertIn("fa-triangle-exclamation", contenido)

    def test_ninguna_declara_un_bloque_que_nadie_dibuja(self):
        for ruta in ERRORES:
            with self.subTest(ruta=ruta):
                contenido = texto(ruta)
                for bloque in ("menu-adicional", "titulo-pagina", "breadcrumb", "content"):
                    self.assertNotIn("{% block " + bloque + " %}", contenido)


class LasTresListasQueFaltabanPaginanTests(TestCase):
    """FE-17: `secretaria`, `subsecretaria` y `programa` incluían la pieza y no paginaban.

    El PR 6a les puso el `{% include %}`, pero sus `form_invalid` armaban el listado a
    mano (sin `page_obj`) y ponerles `paginate_by` ahí reestrenaba el bug de la fila 21.
    Acá entra la vista: `paginate_by` + el `_contexto_lista` que devuelve **la página que
    contiene la fila** cuya edición falló.
    """

    @classmethod
    def setUpTestData(cls):
        cls.secretarias = [Secretaria.objects.create(nombre=f"Secretaría {i:02d}") for i in range(21)]
        for i, secretaria in enumerate(cls.secretarias):
            Subsecretaria.objects.create(nombre=f"Subsecretaría {i:02d}", secretaria=secretaria)

    def setUp(self):
        self.client.force_login(usuario_con("config.administrar", "programa.configurar", username="f20-listas"))

    def test_las_dos_listas_de_secretarias_ofrecen_la_pagina_2(self):
        for ruta, contador in (
            ("configuracion:secretarias", "21 secretarías"),
            ("configuracion:subsecretarias", "21 subsecretarías"),
        ):
            with self.subTest(ruta=ruta):
                respuesta = self.client.get(reverse(ruta))

                self.assertContains(respuesta, 'href="?page=2"')
                self.assertContains(respuesta, contador)

    def test_la_fila_21_es_alcanzable(self):
        respuesta = self.client.get(reverse("configuracion:secretarias") + "?page=2")

        self.assertContains(respuesta, "Secretaría 20")

    def test_el_error_de_edicion_de_la_fila_21_vuelve_a_su_propia_pagina(self):
        ultima = self.secretarias[-1]
        url = reverse("configuracion:secretaria_editar", args=[ultima.pk])
        # Nombre duplicado: el form vuelve inválido y re-renderiza el listado.
        respuesta = self.client.post(url, {"nombre": "", "descripcion": "", "activo": "on"})

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context["page_obj"].number, 2)
        self.assertIn(ultima, list(respuesta.context["secretarias"]))

    def test_el_listado_de_programas_pagina(self):
        from programas.models import Programa

        subsecretaria = Subsecretaria.objects.first()
        for i in range(21):
            Programa.objects.create(nombre=f"Programa {i:02d}", codigo=f"P{i:02d}", subsecretaria=subsecretaria)
        respuesta = self.client.get(reverse("configuracion:programas"))

        self.assertContains(respuesta, 'href="?page=2"')
        self.assertContains(respuesta, "21 programas")
        self.assertEqual(len(respuesta.context["programas"]), 20)


class PantallasDeConfiguracionPorHttpTests(TestCase):
    """Lo que el test estático no ve: que las pantallas sigan sirviendo para lo mismo."""

    @classmethod
    def setUpTestData(cls):
        cls.provincia = Provincia.objects.create(nombre="Chaco")
        cls.municipio = Municipio.objects.create(nombre="Resistencia", provincia=cls.provincia)
        cls.localidad = Localidad.objects.create(nombre="Barranqueras", municipio=cls.municipio)
        cls.secretaria = Secretaria.objects.create(nombre="Secretaría A")
        cls.subsecretaria = Subsecretaria.objects.create(nombre="Subsecretaría A", secretaria=cls.secretaria)

    def setUp(self):
        self.client.force_login(usuario_con("config.administrar", username="f20-admin"))

    def test_las_altas_y_ediciones_dibujan_el_formulario_canonico(self):
        rutas = (
            reverse("configuracion:provincia_crear"),
            reverse("configuracion:provincia_editar", args=[self.provincia.pk]),
            reverse("configuracion:municipio_crear"),
            reverse("configuracion:localidad_crear"),
            reverse("configuracion:secretaria_crear"),
            reverse("configuracion:subsecretaria_crear"),
        )
        for ruta in rutas:
            with self.subTest(ruta=ruta):
                respuesta = self.client.get(ruta)

                self.assertEqual(respuesta.status_code, 200)
                html = respuesta.content.decode()
                self.assertIn('class="bg-white rounded-xl border border-base shadow-sm p-6"', html)
                self.assertIn("nodo-field", html)
                self.assertNotIn("app-content-header", html)

    def test_el_titulo_distingue_alta_de_edicion(self):
        alta = self.client.get(reverse("configuracion:provincia_crear")).content.decode()
        edicion = self.client.get(reverse("configuracion:provincia_editar", args=[self.provincia.pk])).content.decode()

        self.assertIn("Nueva provincia</h1>", alta)
        self.assertIn("Editar provincia</h1>", edicion)

    def test_el_alta_sigue_guardando(self):
        respuesta = self.client.post(reverse("configuracion:provincia_crear"), {"nombre": "Formosa"})

        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(Provincia.objects.filter(nombre="Formosa").exists())

    def test_el_borrado_avisa_del_riesgo_y_borra(self):
        objetivo = Provincia.objects.create(nombre="Para borrar")
        url = reverse("configuracion:provincia_eliminar", args=[objetivo.pk])
        html = self.client.get(url).content.decode()

        self.assertIn("Para borrar", html)
        self.assertIn("no se puede deshacer", html)
        self.assertEqual(self.client.post(url).status_code, 302)
        self.assertFalse(Provincia.objects.filter(pk=objetivo.pk).exists())

    def _entrar_al_wizard(self):
        """El wizard pide `programa.configurar`, no `config.administrar`."""
        self.client.force_login(usuario_con("programa.configurar", username="f20-wizard"))

    def test_el_paso_1_del_wizard_conserva_su_cascada(self):
        self._entrar_al_wizard()
        html = self.client.get(reverse("configuracion:programa_wizard_paso1")).content.decode()

        self.assertIn(reverse("core:ajax_load_subsecretarias"), html)
        self.assertIn('name="subsecretaria"', html)
        self.assertIn("Paso 1 de 4", html)
        self.assertIn("Seleccioná primero una secretaría.", html)

    def test_los_cuatro_pasos_del_wizard_abren(self):
        self._entrar_al_wizard()
        sesion = self.client.session
        sesion["wizard_programa_nuevo"] = {
            "paso1": {
                "nombre": "Programa X",
                "codigo": "PRX",
                "descripcion": "",
                "secretaria": self.secretaria.pk,
                "subsecretaria": self.subsecretaria.pk,
            },
            "paso2": {"naturaleza": "UN_SOLO_ACTO"},
            "paso3": {"cupo_maximo": None, "tiene_lista_espera": False},
        }
        sesion.save()
        for paso in (1, 2, 3, 4):
            with self.subTest(paso=paso):
                respuesta = self.client.get(reverse(f"configuracion:programa_wizard_paso{paso}"))

                self.assertEqual(respuesta.status_code, 200)
                html = respuesta.content.decode()
                self.assertIn(f"Paso {paso} de 4", html)
                self.assertNotIn("app-content-header", html)

    def test_el_paso_4_sigue_mostrando_el_resumen_de_lo_cargado(self):
        self._entrar_al_wizard()
        sesion = self.client.session
        sesion["wizard_programa_nuevo"] = {
            "paso1": {
                "nombre": "Programa X",
                "codigo": "PRX",
                "descripcion": "",
                "secretaria": self.secretaria.pk,
                "subsecretaria": self.subsecretaria.pk,
            },
            "paso2": {"naturaleza": "UN_SOLO_ACTO"},
            "paso3": {"cupo_maximo": 10, "tiene_lista_espera": True},
        }
        sesion.save()
        html = self.client.get(reverse("configuracion:programa_wizard_paso4")).content.decode()

        self.assertIn("Programa X", html)
        self.assertIn("10 inscripciones", html)
        self.assertIn("Menor número = aparece primero.", html)
