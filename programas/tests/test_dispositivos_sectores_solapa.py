"""«Sectores y plazas» dentro de la ficha de la institución: el mismo cuerpo que la pantalla, con filtro por edificio.

La solapa se arma solo cuando se la abre (`?tab=sectores` o un parámetro que abre uno de sus modales). El
filtro «Edificio» acota el mapa y se valida contra los edificios que quien mira alcanza; sus acciones siguen
exigiendo su capacidad y vuelven a la solapa.
"""

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils.html import escapejs

from programas.models import Edificio, Plaza, Sector
from programas.services.sectores_plazas import PARAM_EDIFICIO_SECTORES, url_solapa_sectores
from programas.tests.test_equipo_alcance_edificio import Alcance, BaseAlcance

AJAX = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}


class SolapaSectoresTests(BaseAlcance):
    def setUp(self):
        super().setUp()
        # La solapa solo existe en los tipos que manejan plazas.
        self.tipo.plaza_obligatoria_al_ingresar = True
        self.tipo.save()
        self.ficha = reverse("dispositivos:detalle", args=[self.cis.pk])

    def _solapa(self, usuario=None, **params):
        self.client.force_login(usuario or self.de_inst)
        return self.client.get(self.ficha, {"tab": "sectores", **params})

    def _ajeno(self):
        """Un edificio de **otra** institución: no es de este dispositivo."""

        edificio = Edificio.objects.create(codigo="ED-X", nombre="Edificio ajeno")
        edificio.dispositivos.add(self.parador)
        return edificio

    def test_la_solapa_muestra_los_sectores_de_la_pantalla(self):
        respuesta = self._solapa()

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context["tab"], "sectores")
        self.assertTrue(respuesta.context["sectores_cargados"])
        self.assertTemplateUsed(respuesta, "programas/dispositivos/sectores/_cuerpo.html")
        self.assertContains(respuesta, "Varones · Edificio ED-A · 2 plazas")
        self.assertContains(respuesta, "Mujeres · Edificio ED-B · 1 plaza")
        self.assertContains(respuesta, "Agregar plazas")

    def test_el_filtro_por_edificio_acota_el_mapa_y_los_totales(self):
        respuesta = self._solapa(**{PARAM_EDIFICIO_SECTORES: self.edif_a.pk})

        self.assertContains(respuesta, "Varones · Edificio ED-A")
        self.assertNotContains(respuesta, "Mujeres · Edificio ED-B")
        self.assertEqual(respuesta.context["totales"]["total"], 2)
        self.assertEqual(respuesta.context["pildoras_sectores"][0]["valor"], str(self.edif_a.pk))

    def test_el_filtro_es_enlazable_y_conserva_la_solapa(self):
        respuesta = self._solapa(**{PARAM_EDIFICIO_SECTORES: self.edif_b.pk, "inactivos": "1"})

        self.assertContains(respuesta, '<input type="hidden" name="tab" value="sectores">', html=True)
        self.assertContains(respuesta, '<input type="hidden" name="inactivos" value="1">', html=True)
        self.assertEqual(respuesta.context["qs_sectores"], f"tab=sectores&{PARAM_EDIFICIO_SECTORES}={self.edif_b.pk}&")
        # Las plazas del mapa siguen en la solapa y en el filtro elegido.
        celda = next(c for item in respuesta.context["sectores_mapa"] for c in item["plazas"])
        self.assertEqual(
            celda["url"], f"?tab=sectores&{PARAM_EDIFICIO_SECTORES}={self.edif_b.pk}&plaza={self.plaza_b.pk}"
        )

    def test_el_filtro_ofrece_todos_y_los_edificios_de_la_institucion(self):
        pildora = self._solapa().context["pildoras_sectores"][0]

        self.assertEqual(pildora["etiqueta"], "Edificio")
        self.assertEqual(pildora["valor"], "")
        self.assertEqual(
            pildora["opciones"], [(str(self.edif_a.pk), "Edificio ED-A"), (str(self.edif_b.pk), "Edificio ED-B")]
        )

    def test_un_edificio_ajeno_inexistente_o_invalido_no_filtra_ni_filtra_datos(self):
        ajeno = self._ajeno()
        for pedido in (ajeno.pk, 999999, "abc", "1 OR 1=1"):
            with self.subTest(pedido=pedido):
                respuesta = self._solapa(**{PARAM_EDIFICIO_SECTORES: pedido})

                self.assertContains(respuesta, "Varones · Edificio ED-A")
                self.assertContains(respuesta, "Mujeres · Edificio ED-B")
                self.assertEqual(respuesta.context["pildoras_sectores"][0]["valor"], "")
                self.assertNotContains(respuesta, "Edificio ajeno")

    def test_con_alcance_edificios_ve_solo_los_suyos_y_no_hay_filtro(self):
        respuesta = self._solapa(self.de_a)

        self.assertContains(respuesta, "Varones · Edificio ED-A")
        self.assertNotContains(respuesta, "Mujeres · Edificio ED-B")
        self.assertEqual(respuesta.context["pildoras_sectores"], [])

    def test_con_alcance_edificios_el_filtro_no_destapa_un_edificio_fuera_de_su_alcance(self):
        respuesta = self._solapa(self.de_a, **{PARAM_EDIFICIO_SECTORES: self.edif_b.pk})

        # Se ignora el pedido: sigue viendo lo suyo, no un mapa vacío ni el del edificio ajeno.
        self.assertContains(respuesta, "Varones · Edificio ED-A")
        self.assertNotContains(respuesta, "Mujeres · Edificio ED-B")

    def test_con_alcance_en_dos_edificios_el_filtro_ofrece_solo_esos_dos(self):
        edif_c = self._edificio("ED-C")
        usuario = self._miembro("De A y C", Alcance.EDIFICIOS, [self.edif_a, edif_c])

        opciones = self._solapa(usuario).context["pildoras_sectores"][0]["opciones"]

        self.assertEqual([pk for pk, _nombre in opciones], [str(self.edif_a.pk), str(edif_c.pk)])

    def test_con_un_solo_edificio_no_se_muestra_el_filtro(self):
        self.edif_b.dispositivos.remove(self.cis)

        respuesta = self._solapa()

        self.assertEqual(respuesta.context["pildoras_sectores"], [])
        self.assertNotContains(respuesta, f'name="{PARAM_EDIFICIO_SECTORES}"')

    def test_sin_abrir_la_solapa_no_se_arma_el_mapa(self):
        self.client.force_login(self.de_inst)

        for params in ({}, {"tab": "estadias"}, {"tab": "equipo"}):
            with self.subTest(params=params):
                respuesta = self.client.get(self.ficha, params)

                self.assertEqual(respuesta.status_code, 200)
                self.assertFalse(respuesta.context["sectores_cargados"])
                self.assertNotIn("sectores_mapa", respuesta.context)
                self.assertNotContains(respuesta, "Agregar plazas")
        # Y el botón de la solapa navega a ella en vez de mostrar un panel vacío.
        self.assertContains(respuesta, f"window.location.href='{escapejs(url_solapa_sectores(self.cis.pk))}'")

    def test_las_consultas_de_la_solapa_no_crecen_con_sectores_ni_plazas(self):
        def consultas():
            with CaptureQueriesContext(connection) as capturadas:
                self._solapa()
            return len(capturadas)

        consultas()  # calienta cachés (permisos, content types)
        antes = consultas()
        for i in range(4):
            sector = Sector.objects.create(
                dispositivo=self.cis, nombre=f"Extra {i}", capacidad=3, edificio=self.edif_a if i % 2 else self.edif_b
            )
            for j in range(3):
                Plaza.objects.create(sector=sector, codigo=f"X{i}-{j}")

        self.assertEqual(consultas(), antes)

    def test_las_acciones_de_la_solapa_siguen_exigiendo_su_capacidad(self):
        solo_ver = self._miembro("Solo ver", Alcance.INSTITUCION, capacidades=("dispositivo.ver",))

        sin = self._solapa(solo_ver)
        con = self._solapa()

        self.assertNotContains(sin, "Nuevo sector")
        self.assertNotContains(sin, "Editar sector")
        self.assertNotIn("form_sector_nuevo", sin.context)
        self.assertContains(con, "Nuevo sector")
        self.assertContains(con, "Editar sector")
        self.assertIn("form_sector_nuevo", con.context)
        # El POST lo decide el servidor, no el botón que se dibujó o no.
        self.client.force_login(solo_ver)
        enviado = self.client.post(
            reverse("dispositivos:plaza_fuera_servicio", args=[self.cis.pk, self.plaza_b.pk]), {"motivo": "colchón"}
        )
        self.assertNotEqual(enviado.status_code, 200)
        self.assertEqual(Plaza.objects.get(pk=self.plaza_b.pk).estado, Plaza.Estado.OPERATIVA)

    def test_los_parametros_de_los_modales_abren_la_solapa(self):
        self.client.force_login(self.de_inst)

        editar = self.client.get(self.ficha, {"editar_sector": self.sector_b.pk})
        plaza = self.client.get(self.ficha, {"plaza": self.plaza_b.pk})
        editar_plaza = self.client.get(self.ficha, {"editar_plaza": self.plaza_b.pk})

        self.assertEqual(editar.context["tab"], "sectores")
        self.assertEqual(editar.context["sector_en_edicion"], self.sector_b)
        self.assertEqual(plaza.context["tab"], "sectores")
        self.assertEqual(plaza.context["plaza_inicial"], self.plaza_b.pk)
        self.assertEqual(editar_plaza.context["tab"], "sectores")
        self.assertEqual(editar_plaza.context["plaza_en_edicion"], self.plaza_b)

    def test_un_sector_o_plaza_de_un_edificio_fuera_del_alcance_no_abre_el_modal(self):
        self.client.force_login(self.de_a)

        editar = self.client.get(self.ficha, {"editar_sector": self.sector_b.pk})
        plaza = self.client.get(self.ficha, {"plaza": self.plaza_b.pk})

        self.assertNotIn("sector_en_edicion", editar.context)
        self.assertNotIn("plaza_inicial", plaza.context)
        self.assertNotIn("plaza_accion", plaza.context)

    def test_el_fragmento_de_reubicar_responde_desde_la_ficha_y_respeta_el_alcance(self):
        self.client.force_login(self.de_inst)
        pedido = {"plaza": self.plaza_a.pk, "fragmento": "reubicar"}

        propio = self.client.get(self.ficha, pedido, **AJAX)
        self.assertEqual(propio.status_code, 200)
        self.assertTemplateUsed(propio, "programas/dispositivos/sectores/_modal_reubicar.html")

        self.client.force_login(self.de_a)
        ajeno = self.client.get(self.ficha, {**pedido, "plaza": self.plaza_b.pk}, **AJAX)
        self.assertEqual(ajeno.status_code, 404)

    def test_las_acciones_vuelven_a_la_solapa(self):
        self.client.force_login(self.de_inst)

        respuesta = self.client.post(
            reverse("dispositivos:plaza_fuera_servicio", args=[self.cis.pk, self.plaza_b.pk]), {"motivo": "colchón"}
        )

        self.assertRedirects(respuesta, url_solapa_sectores(self.cis.pk))

    def test_la_ruta_vieja_sigue_respondiendo_con_el_mismo_cuerpo_y_el_filtro(self):
        self.client.force_login(self.de_inst)
        vieja = reverse("dispositivos:sectores", args=[self.cis.pk])

        respuesta = self.client.get(vieja, {PARAM_EDIFICIO_SECTORES: self.edif_a.pk})

        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "programas/dispositivos/sectores/_cuerpo.html")
        self.assertContains(respuesta, "Varones · Edificio ED-A")
        self.assertNotContains(respuesta, "Mujeres · Edificio ED-B")
