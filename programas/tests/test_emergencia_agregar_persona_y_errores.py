"""Emergencia · «Agregar persona» a la vista y aviso con la lista de errores (Cambio 587; issues #1346 y #1259).

* **#1346** — en el paso 2 de Llegadas, «Agregar persona» es un botón secundario visible junto al contador
  «N de N confirmadas» y solo con ``puede_agregar`` (el ingreso en curso). «Más acciones» queda con los cierres
  y, si ninguno corresponde, no se dibuja.
* **#1259** — cuando «Nuevo caso» de la mesa o el Formulario 1 de la puerta vuelven con errores, la página
  deja la lista en el ``json_script`` ``aviso-errores`` (título con N y un ítem por error, con la etiqueta de su
  campo y el enlace a su control); sin errores, no hay aviso. Los errores de cada campo y el bloque de arriba
  siguen donde estaban.

Mutaciones verificadas (cada una pone en rojo al menos un test de acá): dejar «Agregar persona» dentro de
``menu_fila``; dibujar el botón sin ``{% if puede_agregar %}``; sacar el include del aviso de ``casos/form.html``
o de ``dispositivo/formulario1.html``; contar campos en vez de mensajes en el título; sacar la etiqueta del texto
del ítem; dibujar el aviso sin errores.
"""

import json
import re

from programas.models import CasoEmergencia
from programas.tests import test_emergencia_alojar_vistas as vistas
from programas.tests.test_emergencia_mesa import URL_NUEVO, BaseMesa

Estado = CasoEmergencia.Estado
BOTON = re.compile(r'<button[^>]*data-confirm-url="[^"]*agregar[^"]*"[^>]*>', re.S)
MENU = re.compile(r'<div class="nodo-menu-fila__menu".*?</div>', re.S)


def _aviso(respuesta):
    """La lista del aviso (``{"titulo", "items"}``) o ``None`` si la página no la trae."""

    html = respuesta.content.decode()
    hallado = re.search(r'<script id="aviso-errores" type="application/json">(.*?)</script>', html, re.S)
    return json.loads(hallado.group(1)) if hallado else None


def _titulo(total):
    return f"No se guardó: hay {total} {'cosa' if total == 1 else 'cosas'} para corregir"


class AgregarPersonaVisibleTests(vistas.BaseLlegadas):
    def setUp(self):
        super().setUp()
        self.caso, _derivacion = self._aceptado()
        self.url = self._url("integrantes", self.caso.pk)

    def _html(self):
        return self.client.get(self.url).content.decode()

    def test_con_el_ingreso_en_curso_el_boton_esta_a_la_vista_junto_al_contador(self):
        html = self._html()

        boton = BOTON.search(html)
        self.assertIsNotNone(boton, "falta el botón «Agregar persona»")
        self.assertIn(f'data-confirm-url="{self._url("agregar", self.caso.pk)}"', boton.group(0))
        self.assertIn("btn-secondary", boton.group(0))
        self.assertIn('data-confirm-title="¿Agregar una persona a la familia?"', boton.group(0))
        # En el encabezado de la sección Integrantes, antes del contador.
        self.assertLess(html.index("Agregar persona"), html.index("data-contador-avance"))
        self.assertGreater(html.index("Agregar persona"), html.index('id="ingreso-integrantes-titulo"'))

    def test_el_menu_mas_acciones_ya_no_trae_agregar_persona(self):
        html = self._html()

        menu = MENU.search(html)
        self.assertIsNotNone(menu, "sin nadie confirmado todavía, el menú trae «Cancelar ingreso»")
        self.assertIn("Cancelar ingreso", menu.group(0))
        self.assertNotIn("Agregar persona", menu.group(0))
        self.assertEqual(html.count("</i> Agregar persona"), 1)

    def test_con_diferencia_el_menu_trae_solo_los_cierres(self):
        self._confirmar(self.caso, 2, "45000111")
        html = self._html()

        menu = MENU.search(html).group(0)
        self.assertIn("Cerrar ingreso con diferencia", menu)
        self.assertNotIn("Agregar persona", menu)
        self.assertIsNotNone(BOTON.search(html), "con alguien confirmado y faltantes sigue en curso: se puede agregar")

    def test_sin_acciones_de_cierre_el_menu_no_se_dibuja_pero_el_boton_sigue(self):
        caso, _derivacion = self._aceptado(dni="30222333", menores_f=0, menores_m=0)
        total = caso.grupo.total_declarado
        for orden in range(1, total + 1):
            self._confirmar(caso, orden, f"4500{orden:04d}")
        html = self.client.get(self._url("integrantes", caso.pk)).content.decode()

        self.assertNotIn("data-menu-fila-trigger", html)
        self.assertIsNotNone(BOTON.search(html))

    def test_con_el_ingreso_cerrado_no_hay_boton_ni_menu(self):
        CasoEmergencia.objects.filter(pk=self.caso.pk).update(estado=Estado.ALOJADO)
        html = self._html()

        self.assertIsNone(BOTON.search(html))
        self.assertNotIn("Agregar persona", html)
        self.assertNotIn("data-menu-fila-trigger", html)


class AvisoDeErroresNuevoCasoTests(BaseMesa):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.operador)

    def test_el_aviso_cuenta_los_errores_y_nombra_cada_campo_con_su_etiqueta_y_enlace(self):
        respuesta = self.client.post(URL_NUEVO, self._formulario1(nombre="", apellido="", dni="40732199"))

        self.assertEqual(respuesta.status_code, 400)
        aviso = _aviso(respuesta)
        form = respuesta.context["form"]
        errores = {nombre: list(lista) for nombre, lista in form.errors.items()}
        total = sum(len(lista) for lista in errores.values())
        self.assertGreaterEqual(total, 1)
        self.assertEqual(aviso["titulo"], _titulo(total))
        self.assertEqual(len(aviso["items"]), total)
        nombre = next(i for i in aviso["items"] if i["href"] == "#id_nombre")
        self.assertEqual(nombre["texto"], f"{form['nombre'].label}: {errores['nombre'][0]}")

    def test_varios_errores_de_distintos_bloques_se_listan_todos(self):
        respuesta = self.client.post(
            URL_NUEVO, self._formulario1(menores_f="0", menores_m="0", lactantes="2", dependientes="9")
        )

        aviso = _aviso(respuesta)
        hrefs = {i["href"] for i in aviso["items"]}
        self.assertIn("#id_dependientes", hrefs)
        self.assertIn("#id_lactantes", hrefs)
        self.assertEqual(aviso["titulo"], _titulo(len(aviso["items"])))
        self.assertGreaterEqual(len(aviso["items"]), 2)
        self.assertTrue(any(i["texto"].startswith("Lactantes: ") for i in aviso["items"]), aviso)

    def test_los_errores_siguen_debajo_de_cada_campo(self):
        respuesta = self.client.post(URL_NUEVO, self._formulario1(traslado=""))

        self.assertContains(respuesta, 'data-error="traslado"', status_code=400)
        self.assertNotContains(
            respuesta, 'id="id_traslado-error" class="mt-1 text-xs text-fg-danger hidden"', status_code=400
        )

    def test_sin_errores_la_pagina_no_trae_aviso(self):
        self.assertIsNone(_aviso(self.client.get(URL_NUEVO)))

    def test_un_guardado_correcto_redirige_y_no_crea_aviso(self):
        respuesta = self.client.post(URL_NUEVO, self._formulario1())

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(CasoEmergencia.objects.count(), 1)


class AvisoDeErroresPuertaTests(vistas.BaseLlegadas):
    def test_el_formulario_1_de_la_puerta_trae_el_aviso_con_los_errores(self):
        respuesta = self.client.post(self._url("avisar"), self._formulario1(dni="", traslado=""))

        self.assertEqual(respuesta.status_code, 400)
        aviso = _aviso(respuesta)
        form = respuesta.context["form"]
        total = sum(len(lista) for lista in form.errors.values())
        self.assertEqual(aviso["titulo"], _titulo(total))
        self.assertIn("#id_traslado", {i["href"] for i in aviso["items"]})
        self.assertTrue(any(i["texto"].startswith(f"{form['traslado'].label}: ") for i in aviso["items"]), aviso)

    def test_un_error_del_conjunto_va_sin_etiqueta_ni_enlace(self):
        self._ocupar(self.club, 9)

        respuesta = self.client.post(self._url("ingreso_directo"), self._formulario1())

        aviso = _aviso(respuesta)
        self.assertEqual(aviso["titulo"], _titulo(1))
        self.assertEqual(aviso["items"], [{"texto": vistas.servicio.SIN_CAMAS_PARA_INGRESO_DIRECTO, "href": ""}])

    def test_sin_errores_no_hay_aviso(self):
        self.assertIsNone(_aviso(self.client.get(self._url("avisar"))))
