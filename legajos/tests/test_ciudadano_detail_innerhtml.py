"""El legajo arma sus tablas sin marcado crudo de la API (Cambio 95).

El script del legajo concatena en ``innerHTML`` lo que devuelven la API de archivos y la
de actividades. El nombre y el apellido los carga el ciudadano en la inscripción pública:
sin escapar, un nombre con marcado se inyectaba al mostrar los resultados.
Se ejecuta el script real de la página con ``node`` sobre un DOM simulado.

La búsqueda de familiares y la tabla de vínculos se fueron con la solapa «Red Familiar»
(LEG-03, default D-L03 = B): sus casos vivían acá y se retiraron junto con el marcado.
"""

import json
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.tests.js_harness import atributos_de, correr_script_pagina, requiere_node, script_con
from legajos.models import Ciudadano

MARCADO = '<img src=x onerror="window.__inyectado=1">'


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
        self.script = script_con(response.content.decode(), "tabla-archivos")

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

    def test_tablas_de_archivos_y_actividades_escapan_etiqueta_y_descripcion(self):
        archivos = {
            "results": [
                {
                    "id": 3,
                    "nombre": "informe.pdf",
                    "etiqueta": MARCADO,
                    "tamano": 10,
                    "faltante": False,
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
