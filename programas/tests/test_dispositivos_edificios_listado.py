"""Listado de la sección «Edificios» de Dispositivos (#1167, análisis #1164).

Lo que se fija acá:

1. Permiso: ``edificio.ver``; sin ella 403 aunque tenga ``dispositivo.ver``; sin sesión, al login.
2. Alcance: el listado muestra solo los edificios del alcance; huérfanos e inactivos, solo al admin
   y detrás del filtro «Situación», que no se muestra ni se aplica para el resto.
3. Las instituciones fuera de alcance no se nombran.
4. «Crear relevamiento» solo cuando corresponde, al modal de asignar de Relevamientos.
5. Filtros y paginación conservan lo pedido; ninguna acción de escritura del edificio.
6. El costo de la página no crece con los edificios (presupuesto ``dispositivos_edificios_listado``).
"""

import json
from pathlib import Path

from django.conf import settings
from django.db import connection
from django.test import tag
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from programas.models import Edificio
from programas.tests.test_dispositivos_edificios_selector import BaseEdificios
from programas.tests.test_dispositivos_inspecciones import Criticidad

URL = reverse("dispositivos:edificios")
PRESUPUESTOS = Path(settings.BASE_DIR) / "scripts" / "perf_budgets.json"


class BaseListado(BaseEdificios):
    def _get(self, usuario, **params):
        return self._cliente(usuario).get(URL, params)

    def _codigos(self, respuesta):
        return {fila["codigo"] for fila in respuesta.context["filas"]}


class PermisoTests(BaseListado):
    def test_con_edificio_ver_entra(self):
        respuesta = self._get(self.del_parador)

        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "programas/dispositivos/edificios/list.html")

    def test_sin_edificio_ver_es_403_aunque_vea_dispositivos(self):
        solo_dispositivos = self._usuario("solo_disp", ("dispositivo.ver",), [self.parador])

        self.assertEqual(self._get(solo_dispositivos).status_code, 403)

    def test_sin_sesion_va_al_login(self):
        respuesta = self.client.get(URL)

        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(f"?next={URL}", respuesta["Location"])


class AlcanceTests(BaseListado):
    def test_muestra_solo_los_edificios_del_alcance(self):
        self.assertEqual(self._codigos(self._get(self.del_parador)), {"ED-PREDIO"})

    def test_la_situacion_no_se_muestra_ni_se_aplica_para_quien_no_es_admin(self):
        respuesta = self._get(self.del_parador, situacion="todos")

        self.assertEqual(self._codigos(respuesta), {"ED-PREDIO"})
        self.assertNotContains(respuesta, 'name="situacion"')

    def test_el_admin_ve_huerfanos_e_inactivos_solo_con_la_situacion(self):
        self.assertEqual(self._codigos(self._get(self.admin)), {"ED-PREDIO", "ED-CIS"})
        respuesta = self._get(self.admin, situacion="todos")

        self.assertEqual(self._codigos(respuesta), {"ED-PREDIO", "ED-CIS", "ED-HUERF", "ED-INACT"})
        self.assertContains(respuesta, 'name="situacion"')
        self.assertContains(respuesta, "Inactivo")

    def test_las_instituciones_fuera_de_alcance_no_se_nombran(self):
        respuesta = self._get(self.del_parador)

        self.assertContains(respuesta, "Parador")
        self.assertNotContains(respuesta, "Geriátrico")
        self.assertContains(respuesta, "y 1 más")

    def test_sin_edificios_en_el_alcance_el_vacio_lo_dice(self):
        sin_nada = self._usuario("sin_nada", ("edificio.ver",), [self.sin_edificio])
        respuesta = self._get(sin_nada)

        self.assertTrue(respuesta.context["vacio_por_alcance"])
        self.assertContains(respuesta, "No tenés edificios en tu alcance")


class AccionesTests(BaseListado):
    def test_crear_relevamiento_lleva_al_modal_de_asignar(self):
        coordinador = self._usuario("coord_edif", ("edificio.ver", "inspeccion.asignar"), [self.parador])
        respuesta = self._get(coordinador)

        destino = f"{reverse('dispositivos:relevamientos')}?asignar={self.predio.pk}"
        self.assertContains(respuesta, destino)

    def test_sin_inspeccion_asignar_no_hay_crear_relevamiento(self):
        respuesta = self._get(self.del_parador)

        self.assertNotContains(respuesta, "?asignar=")

    def test_ninguna_accion_de_escritura_del_edificio(self):
        respuesta = self._get(self.admin, situacion="todos")
        html = respuesta.content.decode()

        for ruta in ("edificio_crear", "edificio_vincular"):
            self.assertNotIn(reverse(f"dispositivos:{ruta}", args=[self.parador.pk]), html)
        for texto in ("Editar edificio", "Desvincular", "Cargar edificio", "Vincular un edificio"):
            self.assertNotIn(texto, html)


class FiltrosTests(BaseListado):
    def test_filtros_por_estado_y_compartido(self):
        self._relevar(self.edificio_cis, Criticidad.ALTA)

        self.assertEqual(self._codigos(self._get(self.admin, estado="CRITICO")), {"ED-CIS"})
        self.assertEqual(self._codigos(self._get(self.admin, compartido="si")), {"ED-PREDIO"})
        self.assertEqual(self._codigos(self._get(self.admin, q="predio")), {"ED-PREDIO"})

    def test_con_filtros_y_sin_resultados_ofrece_limpiar(self):
        respuesta = self._get(self.admin, q="no-existe")

        self.assertTrue(respuesta.context["hay_filtros"])
        self.assertContains(respuesta, f'href="{URL}"')

    def test_la_paginacion_conserva_los_filtros(self):
        for numero in range(30):
            Edificio.objects.create(codigo=f"ED-P{numero:02}", nombre=f"Pabellón {numero:02}").dispositivos.add(
                self.cis
            )
        respuesta = self._get(self.admin, q="pabellón", page=2)

        self.assertEqual(respuesta.context["page_obj"].number, 2)
        self.assertEqual(len(respuesta.context["filas"]), 5)
        self.assertContains(respuesta, "q=pabell")


@tag("performance")
class PresupuestoTests(BaseListado):
    def _medir(self):
        cliente = self._cliente(self.admin)
        cliente.get(URL)  # calienta sesión y caché del programa, igual en las dos mediciones
        with CaptureQueriesContext(connection) as consultas:
            respuesta = cliente.get(URL)
        return len(respuesta.context["filas"]), len(consultas)

    def test_la_pagina_cuesta_lo_mismo_con_2_que_con_20_edificios(self):
        self._relevar(self.predio, Criticidad.MEDIA)
        filas_antes, antes = self._medir()
        for numero in range(18):
            edificio = Edificio.objects.create(codigo=f"ED-N{numero}", nombre=f"Nuevo {numero}")
            edificio.dispositivos.add(self.cis, self.geriatrico)
            if numero % 2:
                self._relevar(edificio, Criticidad.BAJA)
        filas_despues, despues = self._medir()

        techo = json.loads(PRESUPUESTOS.read_text(encoding="utf-8"))["servicios"]["dispositivos_edificios_listado"]
        self.assertEqual((filas_antes, filas_despues), (2, 20))
        self.assertEqual(antes, despues)
        self.assertLessEqual(despues, techo["consultas_fijas"])
