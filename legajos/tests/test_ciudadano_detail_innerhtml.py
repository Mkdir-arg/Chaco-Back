"""El legajo arma sus tablas y la búsqueda de familiares sin marcado crudo de la API (Cambio 95).

El script del legajo concatena en ``innerHTML`` lo que devuelven la API de ciudadanos,
la de vínculos, la de archivos y la de actividades. El nombre y el apellido los carga
el ciudadano en la inscripción pública: sin escapar, un nombre con marcado se inyectaba
al mostrar los resultados, y la búsqueda además armaba un ``onclick`` con el nombre.
Se ejecuta el script real de la página con ``node`` sobre un DOM simulado.
"""

import json
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.tests.js_harness import atributos_de, correr_script_pagina, requiere_node, script_con
from legajos.models import Ciudadano

MARCADO = '<img src=x onerror="window.__inyectado=1">'
CIERRA_EL_LITERAL = "x',window.__inyectado=1,'"


@requiere_node
class CiudadanoDetailInnerHtmlTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("admin-legajo-innerhtml", password="x")
        self.ciudadano = Ciudadano.objects.create(
            dni="30300300", nombre="Ana", apellido="Paz", fecha_nacimiento=date(1990, 1, 1), genero="F"
        )
        self.client.force_login(self.admin)
        response = self.client.get(reverse("legajos:ciudadano_detalle", args=[self.ciudadano.pk]))
        self.assertEqual(response.status_code, 200)
        self.script = script_con(response.content.decode(), "resultadosBusqueda")

    def _correr(self, respuestas, acciones):
        return correr_script_pagina(
            self.script,
            "".join(
                f"__respuestas[{json.dumps(clave)}] = {json.dumps(valor)};\n" for clave, valor in respuestas.items()
            )
            + acciones,
        )

    def assertSinMarcadoInyectado(self, html, *valores):
        elementos = atributos_de(html)
        self.assertNotIn("img", [tag for tag, _ in elementos], html)
        for tag, attrs in elementos:
            for nombre_attr, valor_attr in attrs.items():
                if nombre_attr.startswith("on"):
                    for valor in valores:
                        self.assertNotIn(valor, valor_attr, f"<{tag} {nombre_attr}> interpola datos de la API")

    def test_busqueda_de_familiar_no_inyecta_el_nombre_y_lo_pasa_por_data(self):
        respuesta = {"results": [{"id": 77, "nombre": MARCADO, "apellido": CIERRA_EL_LITERAL, "dni": "40400400"}]}

        log = self._correr(
            {"/api/legajos/ciudadanos/": respuesta},
            # 3 caracteres: desde SEC-02 el buscador no consulta con menos.
            "__el('buscarCiudadano').value = 'ana';\n__disparar('#buscarCiudadano', 'input');\n",
        )

        html = log["html"]["#resultadosBusqueda"]
        self.assertSinMarcadoInyectado(html, MARCADO, CIERRA_EL_LITERAL)
        (item,) = [attrs for _, attrs in atributos_de(html) if "data-ciudadano-id" in attrs]
        self.assertEqual(item["data-ciudadano-id"], "77")
        self.assertEqual(item["data-ciudadano-nombre"], f"{MARCADO} {CIERRA_EL_LITERAL}")
        self.assertEqual(item["data-ciudadano-dni"], "40400400")
        self.assertIn("DNI: 40400400", html)

    def test_elegir_un_resultado_completa_el_formulario_desde_data(self):
        dataset = {"ciudadanoId": "77", "ciudadanoNombre": f"{MARCADO} {CIERRA_EL_LITERAL}", "ciudadanoDni": "40400400"}

        log = self._correr(
            {}, f"__disparar('#resultadosBusqueda', 'click', {{target: __item({json.dumps(dataset)})}});\n"
        )

        self.assertEqual(log["valores"]["#ciudadanoSeleccionado"], "77")
        self.assertEqual(log["valores"]["#buscarCiudadano"], f"{MARCADO} {CIERRA_EL_LITERAL} (DNI: 40400400)")

    def test_tabla_de_vinculos_muestra_los_datos_como_texto(self):
        respuesta = {
            "results": [
                {
                    "id": 5,
                    "ciudadano_vinculado_detail": {
                        "id": 9,
                        "nombre": MARCADO,
                        "apellido": "<b>Paz</b>",
                        "dni": MARCADO,
                        "telefono": MARCADO,
                    },
                    "tipo_vinculo_display": MARCADO,
                }
            ]
        }

        log = self._correr({"/api/legajos/contactos/vinculos-familiares/": respuesta}, "cargarVinculos();\n")

        html = log["html"]["#tabla-vinculos"]
        self.assertSinMarcadoInyectado(html, MARCADO)
        self.assertNotIn("<b>", html)
        self.assertIn("&lt;b&gt;Paz&lt;/b&gt;", html)
        self.assertIn('onclick="eliminarVinculo(5)"', html)

    def test_tablas_de_archivos_y_actividades_escapan_etiqueta_y_descripcion(self):
        archivos = {
            "results": [
                {
                    "id": 3,
                    "nombre": "informe.pdf",
                    "etiqueta": MARCADO,
                    "tamano": 10,
                    "fecha_subida": "2026-09-01",
                    "tipo_origen": "ciudadano",
                    "url": "/media/informe.pdf",
                }
            ]
        }
        actividades = {
            "results": [
                {
                    "tipo": "SEGUIMIENTO",
                    "fecha_hora": "2026-09-01T10:00:00",
                    "descripcion": MARCADO,
                    "usuario_nombre": "Operador",
                    "legajo_id": 4,
                    "legajo_codigo": "L-4",
                }
            ]
        }

        log = self._correr(
            {f"/legajos/ciudadanos/{self.ciudadano.pk}/archivos/": archivos, "actividades": actividades},
            "cargarArchivos();\ncargarActividades();\n",
        )

        self.assertSinMarcadoInyectado(log["html"]["#tabla-archivos"], MARCADO)
        self.assertIn('href="/media/informe.pdf"', log["html"]["#tabla-archivos"])
        self.assertSinMarcadoInyectado(log["html"]["#tabla-actividades"], MARCADO)
        self.assertIn("L-4", log["html"]["#tabla-actividades"])
