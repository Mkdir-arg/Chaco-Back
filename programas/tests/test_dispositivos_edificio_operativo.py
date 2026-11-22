"""Página operativa del edificio dentro de una institución (Cambio 563, PR 0 del lote «el edificio como unidad operativa»).

1. Alcance: quien opera un edificio entra solo a ese; otro de la misma institución, uno no vinculado y un id
   inexistente dan 404.
2. Predio compartido: el aviso aparece y no nombra a la otra institución.
3. Capacidades: cada acción de «Más acciones» y de la cabecera existe solo con la capacidad que la gobierna.
4. Indicadores: salen del censo de plazas de **este** edificio y de **esta** institución.
5. Solapas: ``?tab=`` abre la pedida; una que el usuario no tiene cae en la de siempre.
6. El costo de la página no crece con los datos (``dispositivos_edificio_operativo``).
"""

import json

from django.conf import settings
from django.contrib.auth.models import User
from django.db import connection
from django.test import tag
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from programas.models import Dispositivo, Edificio, Plaza, Sector
from programas.tests.test_equipo_alcance_edificio import Alcance, BaseAlcance

PRESUPUESTOS = settings.BASE_DIR / "scripts" / "perf_budgets.json"
CLAVE_PRESUPUESTO = "dispositivos_edificio_operativo"


class BaseOperativo(BaseAlcance):
    def setUp(self):
        super().setUp()
        # Un tipo que maneja plazas: es el que muestra Sectores e Indicadores.
        self.tipo.plaza_obligatoria_al_ingresar = True
        self.tipo.save(update_fields=["plaza_obligatoria_al_ingresar"])
        self.de_a = User.objects.get(pk=self.de_a.pk)

    def _url(self, edificio, dispositivo=None):
        return reverse("dispositivos:edificio_operativo", args=[(dispositivo or self.cis).pk, edificio.pk])

    def _get(self, usuario, edificio, dispositivo=None, **params):
        self.client.force_login(User.objects.get(pk=usuario.pk))
        return self.client.get(self._url(edificio, dispositivo), params)

    def _con(self, nombre, *capacidades, alcance=Alcance.INSTITUCION, edificios=()):
        return self._miembro(nombre, alcance, edificios, capacidades=capacidades)


class AlcanceTests(BaseOperativo):
    def test_quien_opera_el_edificio_entra(self):
        respuesta = self._get(self.de_a, self.edif_a)

        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "programas/dispositivos/edificios/operativo.html")
        self.assertEqual(respuesta.context["edificio"], self.edif_a)

    def test_otro_edificio_de_la_misma_institucion_da_404(self):
        self.assertEqual(self._get(self.de_a, self.edif_b).status_code, 404)

    def test_quien_tiene_la_institucion_entra_a_cualquiera_de_sus_edificios(self):
        for edificio in (self.edif_a, self.edif_b):
            with self.subTest(edificio=edificio.codigo):
                self.assertEqual(self._get(self.de_inst, edificio).status_code, 200)

    def test_un_edificio_no_vinculado_a_la_institucion_da_404(self):
        ajeno = Edificio.objects.create(codigo="ED-AJENO", nombre="Ajeno")
        ajeno.dispositivos.add(self.parador)
        huerfano = Edificio.objects.create(codigo="ED-HUERF", nombre="Huérfano")

        self.assertEqual(self._get(self.de_inst, ajeno).status_code, 404)
        self.assertEqual(self._get(self.de_inst, huerfano).status_code, 404)

    def test_un_id_inexistente_da_404(self):
        self.client.force_login(self.de_inst)
        url = reverse("dispositivos:edificio_operativo", args=[self.cis.pk, 99999])

        self.assertEqual(self.client.get(url).status_code, 404)

    def test_un_edificio_desvinculado_deja_de_abrir(self):
        self.edif_a.dispositivos.remove(self.cis)

        self.assertEqual(self._get(self.de_a, self.edif_a).status_code, 404)

    def test_sin_dispositivo_ver_no_entra(self):
        sin_ver = self._con("Sin ver", "dispositivo.bitacora")

        self.assertIn(self._get(sin_ver, self.edif_a).status_code, (403, 404))


class PredioCompartidoTests(BaseOperativo):
    def setUp(self):
        super().setUp()
        self.otra = Dispositivo.objects.create(
            tipo=self.tipo, codigo="GER-9", nombre="Geriátrico Reservado", estado=Dispositivo.Estado.ACTIVO
        )
        self.edif_a.dispositivos.add(self.otra)
        secreto = Sector.objects.create(
            dispositivo=self.otra, edificio=self.edif_a, nombre="Sector Secreto", capacidad=3
        )
        Plaza.objects.create(sector=secreto, codigo="SEC-01")

    def test_avisa_que_es_compartido_sin_nombrar_a_la_otra_institucion(self):
        respuesta = self._get(self.de_a, self.edif_a)

        self.assertTrue(respuesta.context["predio_compartido"])
        self.assertContains(respuesta, "Predio compartido.")
        for dato in ("Geriátrico Reservado", "GER-9", "Sector Secreto"):
            self.assertNotContains(respuesta, dato)

    def test_las_plazas_no_suman_las_de_la_otra_institucion(self):
        respuesta = self._get(self.de_a, self.edif_a)

        # El CIS tiene dos plazas en este edificio; la otra institución tiene una más que no se cuenta.
        self.assertEqual(respuesta.context["contadores"]["sectores"], 2)

    def test_sin_otra_institucion_no_hay_aviso(self):
        self.edif_a.dispositivos.remove(self.otra)

        respuesta = self._get(self.de_a, self.edif_a)

        self.assertFalse(respuesta.context["predio_compartido"])
        self.assertNotContains(respuesta, "Predio compartido.")


class CapacidadesTests(BaseOperativo):
    def _contexto(self, usuario):
        return self._get(usuario, self.edif_a).context

    def test_cada_accion_exige_su_capacidad(self):
        casos = (
            ("url_ingreso", "dispositivo.admitir"),
            ("url_llegadas", "dispositivo.admitir"),
            ("url_editar", "dispositivo.editar"),
            ("url_desvincular", "dispositivo.editar"),
            ("url_kits", "emergencia.recibir_kit"),
            ("url_recibir_kit", "emergencia.recibir_kit"),
        )
        for numero, (clave, capacidad) in enumerate(casos):
            with self.subTest(accion=clave):
                con = self._con(f"Con {numero}", "dispositivo.ver", "ciudadano.ver", capacidad)
                sin = self._con(f"Sin {numero}", "dispositivo.ver")
                self.assertTrue(self._contexto(con)[clave], f"{clave} debería estar con {capacidad}")
                self.assertEqual(self._contexto(sin)[clave], "")

    def test_la_bitacora_lleva_el_edificio(self):
        contexto = self._contexto(self._con("Mira", "dispositivo.ver"))

        esperado = reverse("dispositivos:bitacora", args=[self.cis.pk]) + f"?edificio={self.edif_a.pk}"
        self.assertEqual(contexto["url_bitacora"], esperado)

    def test_los_destinos_llevan_el_edificio(self):
        todas = ("dispositivo.ver", "ciudadano.ver", "dispositivo.admitir", "emergencia.recibir_kit")
        contexto = self._contexto(self._con("Emer", *todas))

        for clave in ("url_ingreso", "url_llegadas", "url_kits"):
            with self.subTest(destino=clave):
                self.assertTrue(contexto[clave].endswith(f"?edificio={self.edif_a.pk}"))

    def test_editar_y_desvincular_son_de_quien_tiene_la_institucion(self):
        acotado = self._con(
            "Acotado", "dispositivo.ver", "dispositivo.editar", alcance=Alcance.EDIFICIOS, edificios=[self.edif_a]
        )
        contexto = self._contexto(acotado)

        self.assertEqual(contexto["url_editar"], "")
        self.assertEqual(contexto["url_desvincular"], "")

    def test_sin_ninguna_accion_el_menu_no_se_dibuja(self):
        respuesta = self._get(self._con("Mira", "dispositivo.ver"), self.edif_a)

        self.assertFalse(respuesta.context["hay_mas_acciones"])
        self.assertNotContains(respuesta, "Más acciones")

    def test_el_menu_trae_los_items_en_orden_y_con_el_texto_del_diseno(self):
        completo = self._con(
            "Completo",
            "dispositivo.ver",
            "dispositivo.editar",
            "dispositivo.admitir",
            "emergencia.recibir_kit",
        )
        respuesta = self._get(completo, self.edif_a)

        html = respuesta.content.decode()
        orden = ("Editar edificio", "Emergencia · Llegadas", "Emergencia · Kits", "Recibir kit")
        posiciones = [html.index(texto) for texto in orden]
        self.assertEqual(posiciones, sorted(posiciones))
        self.assertContains(respuesta, f"Desvincular de {self.cis.nombre}")

    def test_sin_capacidad_de_kits_no_hay_solapa_kits(self):
        sin = self._get(self._con("Sin kits", "dispositivo.ver"), self.edif_a)
        con = self._get(self._con("Con kits", "dispositivo.ver", "emergencia.recibir_kit"), self.edif_a)

        self.assertNotContains(sin, 'id="tab-kits"')
        self.assertContains(con, 'id="tab-kits"')


class IndicadoresTests(BaseOperativo):
    def test_cuatro_indicadores_con_las_etiquetas_del_diseno(self):
        respuesta = self._get(self.de_a, self.edif_a)

        etiquetas = [i["etiqueta"] for i in respuesta.context["indicadores"]]
        self.assertEqual(etiquetas, ["Ocupación", "Plazas operativas", "Reservadas o prestadas", "Disponibles"])

    def test_cuentan_solo_las_plazas_y_estadias_de_este_edificio(self):
        # La base aloja a Ana y a Juan en el edificio A; el B tiene una plaza libre.
        Plaza.objects.create(sector=self.sector_b, codigo="B-02")
        contexto_a = self._get(self.de_a, self.edif_a).context
        contexto_b = self._get(self.de_inst, self.edif_b).context
        a = {i["etiqueta"]: i["valor"] for i in contexto_a["indicadores"]}
        b = {i["etiqueta"]: i["valor"] for i in contexto_b["indicadores"]}

        self.assertEqual(a["Plazas operativas"], 2)
        self.assertEqual(b["Plazas operativas"], 2)
        self.assertNotEqual(a["Disponibles"], b["Disponibles"])
        self.assertEqual(contexto_a["contadores"]["estadias"], 2)
        self.assertEqual(contexto_b["contadores"]["estadias"], 0)


class SolapasTests(BaseOperativo):
    def test_tab_abre_la_pedida(self):
        self.assertEqual(self._get(self.de_a, self.edif_a, tab="estadias").context["tab"], "estadias")

    def test_una_solapa_desconocida_o_sin_permiso_cae_en_la_de_siempre(self):
        sin_kits = self._con("Sin kits", "dispositivo.ver")

        self.assertEqual(self._get(self.de_a, self.edif_a, tab="inventada").context["tab"], "sectores")
        self.assertEqual(self._get(sin_kits, self.edif_a, tab="kits").context["tab"], "sectores")

    def test_los_paneles_existen(self):
        respuesta = self._get(self.de_inst, self.edif_a)

        for panel in ("sectores", "estadias", "equipo", "edilicio", "historial"):
            self.assertContains(respuesta, f'id="panel-{panel}"')


@tag("performance")
class PresupuestoTests(BaseOperativo):
    def _medir(self):
        self.client.force_login(self.de_inst)
        url = self._url(self.edif_a)
        self.client.get(url)  # calienta sesión y caché, igual en las dos mediciones
        with CaptureQueriesContext(connection) as consultas:
            respuesta = self.client.get(url)
        self.assertEqual(respuesta.status_code, 200)
        return len(consultas)

    def test_la_pagina_cuesta_lo_mismo_con_uno_que_con_muchos(self):
        antes = self._medir()
        for numero in range(6):
            sector = Sector.objects.create(dispositivo=self.cis, edificio=self.edif_a, nombre=f"S{numero}", capacidad=2)
            Plaza.objects.create(sector=sector, codigo=f"X-{numero}")
        otra = Dispositivo.objects.create(
            tipo=self.tipo, codigo="GER-9", nombre="Otra", estado=Dispositivo.Estado.ACTIVO
        )
        self.edif_a.dispositivos.add(otra)
        despues = self._medir()

        techo = json.loads(PRESUPUESTOS.read_text(encoding="utf-8"))["servicios"][CLAVE_PRESUPUESTO]
        self.assertEqual(antes, despues)
        self.assertLessEqual(despues, techo["consultas_fijas"])
