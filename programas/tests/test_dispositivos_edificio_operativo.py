"""Página operativa del edificio dentro de una institución (Cambio 563, PR 0 del lote «el edificio como unidad operativa»).

1. Alcance: quien opera un edificio entra solo a ese; otro de la misma institución, uno no vinculado y un id
   inexistente dan 404.
2. Predio compartido: el aviso aparece y no nombra a la otra institución.
3. Capacidades: cada acción de «Más acciones» y de la cabecera existe solo con la capacidad que la gobierna.
4. Indicadores: salen del censo de plazas de **este** edificio y de **esta** institución.
5. Solapas: ``?tab=`` abre la pedida; una que el usuario no tiene cae en la de siempre.
6. El costo de la página no crece con los datos (``dispositivos_edificio_operativo``).
7. Solapa «Sectores y plazas» (Cambio 565): solo los sectores de este edificio y de esta institución, sin filtro
   «Edificio»; las acciones y los modales siguen en las rutas de la institución y vuelven a esta solapa.
"""

import json

from django.conf import settings
from django.contrib.auth.models import User
from django.db import connection
from django.test import tag
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from legajos.models import Ciudadano
from programas.models import Dispositivo, Edificio, Plaza, Sector
from programas.services.sectores_plazas import url_solapa_sectores
from programas.tests.test_dispositivos_bitacora_pantalla import MARTES, _local
from programas.tests.test_equipo_alcance_edificio import Alcance, BaseAlcance

AJAX = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}
PRESUPUESTOS = settings.BASE_DIR / "scripts" / "perf_budgets.json"
CLAVE_PRESUPUESTO = "dispositivos_edificio_operativo"
CLAVE_PRESUPUESTO_SECTORES = "dispositivos_edificio_operativo_solapa_sectores"


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


class SectoresSolapaTests(BaseOperativo):
    """El cuerpo de «Sectores y plazas» con el edificio fijo."""

    def setUp(self):
        super().setUp()
        # Otra institución en el mismo predio, con su sector y su plaza.
        self.otra = Dispositivo.objects.create(
            tipo=self.tipo, codigo="GER-9", nombre="Geriátrico Reservado", estado=Dispositivo.Estado.ACTIVO
        )
        self.edif_a.dispositivos.add(self.otra)
        self.sector_otra = Sector.objects.create(
            dispositivo=self.otra, edificio=self.edif_a, nombre="Sector Secreto", capacidad=3
        )
        self.plaza_otra = Plaza.objects.create(sector=self.sector_otra, codigo="SEC-01")
        self.libre_a = Plaza.objects.create(sector=self.sector_a, codigo="A-LIBRE")
        self.libre_b = Plaza.objects.create(sector=self.sector_b, codigo="B-LIBRE")

    def _sectores(self, respuesta):
        return [item["sector"] for item in respuesta.context["sectores_mapa"]]

    def test_dibuja_solo_los_sectores_de_este_edificio(self):
        respuesta = self._get(self.de_inst, self.edif_a)

        self.assertEqual(self._sectores(respuesta), [self.sector_a])
        self.assertTemplateUsed(respuesta, "programas/dispositivos/sectores/_cuerpo.html")
        self.assertContains(respuesta, self.sector_a.nombre)
        self.assertNotContains(respuesta, self.sector_b.nombre)

    def test_el_otro_edificio_muestra_el_suyo(self):
        respuesta = self._get(self.de_inst, self.edif_b)

        self.assertEqual(self._sectores(respuesta), [self.sector_b])

    def test_un_predio_compartido_no_muestra_nada_de_la_otra_institucion(self):
        respuesta = self._get(self.de_inst, self.edif_a)

        self.assertNotIn(self.sector_otra, self._sectores(respuesta))
        for dato in ("Sector Secreto", "SEC-01", "Geriátrico Reservado"):
            self.assertNotContains(respuesta, dato)

    def test_no_lleva_el_filtro_edificio_ni_repite_el_nombre_del_edificio(self):
        respuesta = self._get(self.de_inst, self.edif_a)

        self.assertFalse(respuesta.context["pildoras_sectores"])
        self.assertTrue(respuesta.context["edificio_fijo"])
        self.assertContains(respuesta, f"{self.sector_a.nombre} · ")
        self.assertNotContains(respuesta, f"{self.sector_a.nombre} · Edificio ED-A")

    def test_los_totales_son_los_del_edificio(self):
        respuesta = self._get(self.de_inst, self.edif_a)

        self.assertEqual(respuesta.context["totales"]["total"], 3)
        self.assertEqual(respuesta.context["contadores"]["sectores"], 3)

    def test_con_otra_solapa_no_se_arma_el_mapa_y_el_boton_navega(self):
        respuesta = self._get(self.de_inst, self.edif_a, tab="historial")

        self.assertFalse(respuesta.context["sectores_cargados"])
        self.assertNotIn("sectores_mapa", respuesta.context)
        self.assertContains(respuesta, 'id="tab-sectores" aria-controls="panel-sectores" data-solapa-navega')
        self.assertEqual(respuesta.context["url_solapa_sectores"], f"{self._url(self.edif_a)}?tab=sectores")
        self.assertContains(respuesta, "window.location.href=")

    def test_una_plaza_de_este_edificio_abre_su_modal(self):
        respuesta = self._get(self.de_inst, self.edif_a, plaza=self.libre_a.pk)

        self.assertEqual(respuesta.context["plaza_inicial"], self.libre_a.pk)

    def test_una_plaza_de_otro_edificio_o_de_otra_institucion_no_abre_el_modal(self):
        for plaza in (self.libre_b, self.plaza_otra):
            with self.subTest(plaza=plaza.codigo):
                respuesta = self._get(self.de_inst, self.edif_a, plaza=plaza.pk)

                self.assertNotIn("plaza_inicial", respuesta.context)
                self.assertNotIn("plaza_accion", respuesta.context)

    def _ocupar_b(self):
        """Una persona en la plaza de B: ocupada ofrece reubicar, así que el fragmento solo se frena por el edificio."""

        persona = Ciudadano.objects.create(dni="30555666", nombre="Eva", apellido="Soto")
        self._ingresar(persona, self.plaza_b, _local(MARTES, 11))

    def test_el_fragmento_de_reubicar_es_solo_de_este_edificio(self):
        self._ocupar_b()
        self.client.force_login(self.de_inst)
        pedido = {"fragmento": "reubicar"}

        # La plaza ocupada de B es accionable para `de_inst`: en su edificio abre, en el A es 404.
        en_b = self.client.get(self._url(self.edif_b), {**pedido, "plaza": self.plaza_b.pk}, **AJAX)
        self.assertEqual(en_b.status_code, 200)
        en_a = self.client.get(self._url(self.edif_a), {**pedido, "plaza": self.plaza_b.pk}, **AJAX)
        self.assertEqual(en_a.status_code, 404)

        propio = self.client.get(self._url(self.edif_a), {**pedido, "plaza": self.plaza_a.pk}, **AJAX)
        self.assertEqual(propio.status_code, 200)
        self.assertTemplateUsed(propio, "programas/dispositivos/sectores/_modal_reubicar.html")
        self.assertContains(propio, 'name="next"')

    def test_el_fragmento_de_una_plaza_de_otra_institucion_es_404(self):
        self.client.force_login(self.de_inst)

        respuesta = self.client.get(
            self._url(self.edif_a), {"plaza": self.plaza_otra.pk, "fragmento": "reubicar"}, **AJAX
        )

        self.assertEqual(respuesta.status_code, 404)

    def test_el_fragmento_no_salta_el_alcance_del_edificio(self):
        # `de_a` no alcanza el edificio B: la página es un 404 también para el fragmento, aunque la plaza esté ocupada.
        self._ocupar_b()
        self.client.force_login(self.de_a)

        respuesta = self.client.get(self._url(self.edif_b), {"plaza": self.plaza_b.pk, "fragmento": "reubicar"}, **AJAX)

        self.assertEqual(respuesta.status_code, 404)

    def test_el_fragmento_de_un_edificio_desvinculado_es_404_aunque_la_plaza_sea_accionable(self):
        # Solo el chequeo del edificio lo frena: `de_inst` sí opera la plaza ocupada de B (la sirve en su página).
        self._ocupar_b()
        self.client.force_login(self.de_inst)
        pedido = {"plaza": self.plaza_b.pk, "fragmento": "reubicar"}
        self.assertEqual(self.client.get(self._url(self.edif_b), pedido, **AJAX).status_code, 200)

        self.edif_b.dispositivos.remove(self.cis)

        self.assertEqual(self.client.get(self._url(self.edif_b), pedido, **AJAX).status_code, 404)

    def test_la_barra_de_cifras_es_la_breve_del_diseno(self):
        respuesta = self._get(self.de_inst, self.edif_a)

        # El edificio A tiene A-01, A-02, A-LIBRE (y Ana y Juan alojados en las dos primeras).
        self.assertContains(respuesta, "3 plazas cargadas · 3 operativas · 2 ocupadas · 1 disponible")
        self.assertNotContains(respuesta, "operativas de")

    def test_el_resumen_del_sector_es_el_breve_y_conserva_la_capacidad_declarada_si_difiere(self):
        Sector.objects.filter(pk=self.sector_a.pk).update(capacidad=2)
        respuesta = self._get(self.de_inst, self.edif_a)

        self.assertContains(respuesta, "3 operativas · 0 fuera de servicio · 2 ocupadas")
        self.assertNotContains(respuesta, "0 reservadas")
        # La capacidad declarada (2) difiere de las 3 plazas cargadas: el sufijo queda.
        self.assertContains(respuesta, "capacidad declarada: 2")
        Sector.objects.filter(pk=self.sector_a.pk).update(capacidad=3)
        igual = self._get(self.de_inst, self.edif_a)
        self.assertNotContains(igual, "capacidad declarada")

    def test_nuevo_sector_preselecciona_el_edificio_de_la_pagina(self):
        en_a = self._get(self.de_inst, self.edif_a)
        en_b = self._get(self.de_inst, self.edif_b)

        self.assertEqual(en_a.context["form_sector_nuevo"]["edificio"].value(), self.edif_a.pk)
        self.assertEqual(en_b.context["form_sector_nuevo"]["edificio"].value(), self.edif_b.pk)

    def test_sin_sectores_dice_este_edificio_y_los_inactivos_no_repiten_el_edificio(self):
        self.edif_c = self._edificio("ED-C")
        vacio = self._get(self.de_inst, self.edif_c)
        self.assertContains(vacio, "Este edificio no tiene sectores")
        self.assertContains(vacio, "Un sector es cómo este edificio ordena su capacidad")
        self.assertNotContains(vacio, "Este dispositivo no tiene sectores")

        Sector.objects.filter(pk=self.sector_b.pk).update(activo=False)
        inactivos = self._get(self.de_inst, self.edif_b, inactivos=1)
        self.assertNotContains(inactivos, f"· {self.edif_b.nombre} ·")

    def test_editar_un_sector_de_otro_edificio_no_abre_el_modal(self):
        propio = self._get(self.de_inst, self.edif_a, editar_sector=self.sector_a.pk)
        for sector in (self.sector_b, self.sector_otra):
            with self.subTest(sector=sector.nombre):
                ajeno = self._get(self.de_inst, self.edif_a, editar_sector=sector.pk)

                self.assertNotIn("sector_en_edicion", ajeno.context)

        self.assertEqual(propio.context["sector_en_edicion"], self.sector_a)

    def test_agregar_plazas_ofrece_solo_los_sectores_de_este_edificio(self):
        respuesta = self._get(self.de_inst, self.edif_a)

        ofrecidos = set(respuesta.context["form_plazas"].fields["sector"].queryset)
        self.assertEqual(ofrecidos, {self.sector_a})

    def test_los_formularios_vuelven_a_esta_solapa(self):
        respuesta = self._get(self.de_inst, self.edif_a)

        esperado = f"{self._url(self.edif_a)}?tab=sectores"
        self.assertEqual(respuesta.context["vuelta_a"], esperado)
        self.assertContains(respuesta, f'name="next" value="{esperado}"')

    def test_una_accion_con_next_vuelve_a_la_pagina_del_edificio(self):
        self.client.force_login(self.de_inst)
        destino = f"{self._url(self.edif_a)}?tab=sectores"

        respuesta = self.client.post(
            reverse("dispositivos:plaza_fuera_servicio", args=[self.cis.pk, self.libre_a.pk]),
            {"motivo": "colchón", "next": destino},
        )

        self.assertRedirects(respuesta, destino)

    def test_un_next_de_otro_sitio_se_ignora(self):
        self.client.force_login(self.de_inst)

        for ajeno in ("https://sitio-ajeno.example/robo", "//sitio-ajeno.example/robo"):
            with self.subTest(next=ajeno):
                respuesta = self.client.post(
                    reverse("dispositivos:plaza_fuera_servicio", args=[self.cis.pk, self.libre_a.pk]),
                    {"motivo": "colchón", "next": ajeno},
                )

                self.assertRedirects(respuesta, url_solapa_sectores(self.cis.pk))

    def test_las_acciones_siguen_exigiendo_su_capacidad(self):
        solo_ver = self._con("Solo ver", "dispositivo.ver")

        respuesta = self._get(solo_ver, self.edif_a)

        self.assertNotContains(respuesta, "Nuevo sector")
        self.assertNotContains(respuesta, "Editar sector")
        self.assertNotIn("form_sector_nuevo", respuesta.context)


@tag("performance")
class PresupuestoTests(BaseOperativo):
    def _medir(self, **params):
        self.client.force_login(self.de_inst)
        url = self._url(self.edif_a)
        self.client.get(url, params)  # calienta sesión y caché, igual en las dos mediciones
        with CaptureQueriesContext(connection) as consultas:
            respuesta = self.client.get(url, params)
        self.assertEqual(respuesta.status_code, 200)
        return len(consultas)

    def _crecer(self):
        for numero in range(6):
            sector = Sector.objects.create(dispositivo=self.cis, edificio=self.edif_a, nombre=f"S{numero}", capacidad=2)
            Plaza.objects.create(sector=sector, codigo=f"X-{numero}")
        otra = Dispositivo.objects.create(
            tipo=self.tipo, codigo="GER-9", nombre="Otra", estado=Dispositivo.Estado.ACTIVO
        )
        self.edif_a.dispositivos.add(otra)

    def _techo(self, clave):
        return json.loads(PRESUPUESTOS.read_text(encoding="utf-8"))["servicios"][clave]["consultas_fijas"]

    def test_la_pagina_cuesta_lo_mismo_con_uno_que_con_muchos(self):
        # Con otra solapa abierta el mapa no se arma: el costo es el del encabezado.
        antes = self._medir(tab="historial")
        self._crecer()
        despues = self._medir(tab="historial")

        self.assertEqual(antes, despues)
        self.assertLessEqual(despues, self._techo(CLAVE_PRESUPUESTO))

    def test_la_solapa_sectores_no_crece_con_sectores_ni_plazas(self):
        antes = self._medir(tab="sectores")
        self._crecer()
        despues = self._medir(tab="sectores")

        self.assertEqual(antes, despues)
        self.assertLessEqual(despues, self._techo(CLAVE_PRESUPUESTO_SECTORES))
