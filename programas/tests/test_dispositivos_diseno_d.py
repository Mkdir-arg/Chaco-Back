"""PR-D del relevamiento de diseño de Dispositivos: configuración y formularios.

Lo que se fija acá, y por qué:

1. **«Cancelar» del legajo vuelve al origen**: editando, a la ficha de la institución; creando, a la
   lista. Antes iba siempre a la lista y tiraba al usuario fuera del registro que estaba mirando.
2. **El filtro «Localidad» es un select** con las localidades que existen *en el alcance de quien mira*,
   y filtra igual que antes (`icontains`). Un valor viejo de la URL no se esconde.
3. **Las exportaciones van al menú** del encabezado: una acción primaria y un menú, no tres botones.
4. **Los booleanos del tipo son interruptores** (`SwitchInput`) y guardan lo mismo: mismos nombres de
   campo, mismo valor.
5. **El JS del legajo vive en `static/custom/js/`** y la página no trae su lógica en `<script>` inline.
"""

import re
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from core.widgets import SwitchInput
from programas.forms import TipoDispositivoForm
from programas.models import Programa, TipoDispositivo
from programas.tests.test_dispositivos_config import rol_configuracion
from programas.tests.test_dispositivos_detalle import BaseDetalle
from programas.tests.test_dispositivos_listado import URL_LISTA, BaseListado

CANCELAR = re.compile(r'<a href="([^"]*)" class="btn-nodo btn-tertiary btn-base">Cancelar</a>')


class CancelarDelLegajoTests(BaseDetalle):
    def setUp(self):
        super().setUp()
        self.operador.is_superuser = True
        self.operador.save()
        self.client.force_login(self.operador)

    def _cancelar(self, url):
        html = self.client.get(url).content.decode()
        return CANCELAR.search(html).group(1)

    def test_editando_cancelar_vuelve_a_la_ficha_de_la_institucion(self):
        """Mutación: con `{% url 'dispositivos:lista' %}` fijo en el enlace, editar vuelve a la lista."""
        self.assertEqual(self._cancelar(reverse("dispositivos:editar", args=[self.cis.pk])), self.url)

    def test_creando_cancelar_vuelve_a_la_lista(self):
        self.assertEqual(self._cancelar(reverse("dispositivos:crear")), reverse("dispositivos:lista"))


class ScriptsDelLegajoTests(BaseDetalle):
    SCRIPTS = (
        "dispositivos-legajo-faltantes.js",
        "dispositivos-legajo-tipo.js",
        "dispositivos-legajo-franjas.js",
    )

    MARCAS_DEL_LEGAJO = (
        "actualizarFaltantes",
        "prepararQuitar",
        "const codigo =",
        "data-contacto-responsable",
        "NodoFormularioTipo",
    )

    def setUp(self):
        super().setUp()
        self.operador.is_superuser = True
        self.operador.save()
        self.client.force_login(self.operador)

    def _scripts_inline(self, url):
        html = self.client.get(url).content.decode()
        return [s for s in re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", html, re.S) if s.strip()]

    def test_el_alta_carga_sus_archivos_y_no_trae_script_inline(self):
        """Mutación: con un `<script>` inline en el template, la lista de inline deja de estar vacía."""
        url = reverse("dispositivos:crear")
        html = self.client.get(url).content.decode()
        for nombre in (*self.SCRIPTS, "dispositivos-legajo-responsables.js", "dispositivos-legajo-duplicados.js"):
            self.assertIn(f"custom/js/{nombre}", html)
        # El shell trae sus propios inline; lo que no puede traer es la lógica del legajo.
        propios = [s for s in self._scripts_inline(url) if any(m in s for m in self.MARCAS_DEL_LEGAJO)]
        self.assertEqual(propios, [])
        # La URL de la búsqueda de duplicados viaja en el propio <script>, no escrita en el JS.
        self.assertIn(f'data-url="{reverse("dispositivos:buscar_duplicados")}"', html)

    def test_la_edicion_no_carga_lo_que_es_solo_del_alta(self):
        html = self.client.get(reverse("dispositivos:editar", args=[self.cis.pk])).content.decode()
        for nombre in self.SCRIPTS:
            self.assertIn(f"custom/js/{nombre}", html)
        self.assertNotIn("dispositivos-legajo-duplicados.js", html)
        self.assertNotIn("dispositivos-legajo-responsables.js", html)

    def test_ningun_archivo_del_legajo_quedo_con_sintaxis_de_template(self):
        base = Path(settings.BASE_DIR) / "static" / "custom" / "js"
        archivos = list(base.glob("dispositivos-legajo-*.js"))
        self.assertEqual(len(archivos), 5)
        for ruta in archivos:
            texto = ruta.read_text(encoding="utf-8")
            self.assertNotIn("{%", texto, ruta.name)
            self.assertNotIn("{{", texto, ruta.name)


class FiltroLocalidadTests(BaseListado):
    def setUp(self):
        super().setUp()
        self.hogar = self._dispositivo("HOG-1", "Hogar San José", localidad="Barranqueras")
        self.otro_hogar = self._dispositivo("HOG-2", "Hogar Santa Rita", localidad="Barranqueras")
        self.parador = self._dispositivo("PAR-1", "Parador Nocturno", localidad="Resistencia")
        self.lejano = self._dispositivo("LEJ-1", "Hogar Lejano", localidad="Fontana")
        self.sin_localidad = self._dispositivo("SIN-1", "Hogar sin localidad")
        self.admin = self._admin("admin-localidad")
        self.cliente = self._cliente(self.admin)

    def test_el_select_ofrece_cada_localidad_una_vez_y_ordenadas(self):
        respuesta = self.cliente.get(URL_LISTA)

        self.assertEqual(respuesta.context["localidades"], ["Barranqueras", "Fontana", "Resistencia"])
        self.assertContains(respuesta, '<select name="localidad" aria-label="Localidad"')
        self.assertContains(respuesta, '<option value="Fontana" >Fontana</option>')
        self.assertNotContains(respuesta, '<input type="search" name="localidad"')

    def test_solo_ofrece_localidades_del_alcance_de_quien_mira(self):
        """Mutación: con `Dispositivo.objects` en vez de `dispositivos_visibles`, aparece «Fontana»."""
        usuario = self._usuario("operador-acotado", ("dispositivo.ver",), alcance=[self.hogar])

        respuesta = self._cliente(usuario).get(URL_LISTA)

        self.assertEqual(respuesta.context["localidades"], ["Barranqueras"])
        self.assertNotContains(respuesta, "Fontana")

    def test_elegir_una_localidad_filtra_como_antes(self):
        respuesta = self.cliente.get(URL_LISTA, {"localidad": "Barranqueras"})

        self.assertEqual(sorted(self._filas(respuesta)), ["HOG-1", "HOG-2"])
        self.assertContains(respuesta, '<option value="Barranqueras" selected>Barranqueras</option>')
        self.assertEqual(respuesta.context["exportar_qs"], "localidad=Barranqueras")

    def test_un_valor_de_la_url_que_no_es_una_localidad_se_ofrece_igual(self):
        """El select no esconde un filtro aplicado (un enlace viejo con texto libre)."""
        respuesta = self.cliente.get(URL_LISTA, {"localidad": "barran"})

        self.assertEqual(sorted(self._filas(respuesta)), ["HOG-1", "HOG-2"])
        self.assertEqual(respuesta.context["localidades"][0], "barran")
        self.assertContains(respuesta, '<option value="barran" selected>barran</option>')


class EncabezadoDeInstitucionesTests(BaseListado):
    def setUp(self):
        super().setUp()
        self._dispositivo("HOG-1", "Hogar San José", localidad="Barranqueras")
        self.admin = self._admin("admin-encabezado", "dispositivo.crear")
        self.cliente = self._cliente(self.admin)

    def test_las_exportaciones_van_al_menu_y_llevan_los_filtros(self):
        """Mutación: con los dos `<a class="btn-tertiary">` sueltos, el menú desaparece."""
        respuesta = self.cliente.get(URL_LISTA, {"localidad": "Barranqueras"})
        html = respuesta.content.decode()

        self.assertIn('id="menu-fila-exportar-padron"', html)
        self.assertNotRegex(html, r'btn-tertiary btn-base[^>]*>\s*<i class="fas fa-file-(csv|excel)')
        for formato in ("csv", "xlsx"):
            url = reverse("dispositivos:exportar", args=["padron", formato]) + "?localidad=Barranqueras"
            self.assertIn(f'href="{url}" role="menuitem"', html)

    def test_la_accion_primaria_sigue_siendo_el_alta_con_su_capacidad(self):
        self.assertContains(self.cliente.get(URL_LISTA), "Nueva institución")


class InterruptoresDelTipoTests(TestCase):
    CAMPOS = ("maneja_sectores_plazas", "plaza_obligatoria_al_ingresar", "ubicacion_reservada", "activo")

    @classmethod
    def setUpTestData(cls):
        cls.programa, _ = Programa.objects.get_or_create(
            codigo="DISPOSITIVOS",
            defaults={"nombre": "Dispositivos", "tipo": Programa.TipoPrograma.DISPOSITIVOS},
        )
        cls.admin = User.objects.create_user("admin-interruptores", password="x")
        cls.admin.groups.add(rol_configuracion("Admin interruptores", cls.programa))
        cls.tipo = TipoDispositivo.objects.create(codigo="INT", nombre="Tipo interruptores")

    def setUp(self):
        cache.clear()
        self.client.force_login(self.admin)

    def test_los_cuatro_booleanos_son_interruptores(self):
        """Mutación: con `CheckboxInput` de nuevo en un campo, el isinstance falla."""
        form = TipoDispositivoForm()
        for nombre in self.CAMPOS:
            with self.subTest(campo=nombre):
                self.assertIsInstance(form.fields[nombre].widget, SwitchInput)
        # El que muestra los tipos de plaza sigue atado al x-data de la pantalla.
        self.assertEqual(form.fields["maneja_sectores_plazas"].widget.attrs["x-model"], "plazas")

    def test_la_pagina_los_dibuja_como_switch_con_el_mismo_name(self):
        respuesta = self.client.get(reverse("dispositivos:tipo_editar", args=[self.tipo.pk]))
        html = respuesta.content.decode()
        for nombre in self.CAMPOS:
            with self.subTest(campo=nombre):
                entrada = re.search(rf'<input[^>]*name="{nombre}"[^>]*>', html).group()
                self.assertIn('role="switch"', entrada)
                self.assertIn("nodo-switch", entrada)

    def test_guardar_conserva_el_valor_que_viaja(self):
        url = reverse("dispositivos:tipo_editar", args=[self.tipo.pk])
        datos = {
            "codigo": "INT",
            "nombre": "Tipo interruptores",
            "umbral_ocupacion_amarillo": 50,
            "umbral_ocupacion_rojo": 80,
        }

        self.client.post(url, {**datos, "ubicacion_reservada": "on", "activo": "on"})
        self.tipo.refresh_from_db()
        self.assertTrue(self.tipo.ubicacion_reservada)
        self.assertTrue(self.tipo.activo)

        self.client.post(url, datos)
        self.tipo.refresh_from_db()
        self.assertFalse(self.tipo.ubicacion_reservada)
        self.assertFalse(self.tipo.activo)

    def test_editar_tipo_lleva_su_icono(self):
        """Mutación: sin el `<i class="fas fa-pen">`, el botón vuelve a ser solo texto."""
        respuesta = self.client.get(reverse("dispositivos:tipo_detalle", args=[self.tipo.pk]))

        self.assertContains(respuesta, '<i class="fas fa-pen" aria-hidden="true"></i> Editar tipo</a>')
