"""E8 · la solapa «Mapa» de la Situación de Emergencia (Cambio 512 · E-6 #1185, cierra C1 #1173).

La solapa usa la pieza ``components/_mapa_capas.html`` (Google Maps, Cambio 493) con ``detalle=False``; el
panel, las capas, la leyenda y la lista los arma la pantalla (``pantalla_situacion_emergencia.bloque_del_mapa``).

* **No nominal** (RNF-009-01, TC-1185-09/17): en el HTML y en el ``json_script`` solo viajan centroides de
  localidad y dispositivos publicables; ni coordenadas de casos ni datos de personas.
* **Ubicación reservada** (RN-009-13): test de mutación sobre la respuesta.
* **Enlaces** a la bandeja solo con ``supervisar``; «Ver dispositivo» solo si Dispositivos lo deja abrir.
* **La lista** coincide con la tabla del Resumen (TC-1185-08) y trae las de más presión (TC-1185-07).
* **Estados**: sin ubicaciones cargadas, «N sin ubicación», sin key y sin nada que dibujar.
* **Nada a terceros** antes de abrir el mapa (C1 #1173): la página no referencia hosts externos.

Todas las personas usan DNIs de prueba (90000001–90000099).
"""

import json
import re
from unittest import mock

from django.contrib.auth.models import User
from django.test import SimpleTestCase, override_settings
from django.urls import reverse

from core.models import UbicacionLocalidad
from programas.models import CasoEmergencia, Dispositivo
from programas.services import pantalla_situacion_emergencia as pantalla
from programas.services.situacion_emergencia import tamano_de_circulo
from programas.tests.test_emergencia_situacion import EscenarioSituacion
from programas.tests.test_emergencia_situacion_vista import URL, VER_SITUACION

ID_PUNTOS = "mapa-capas-situacion-puntos"

#: Lo que la pieza serializa por punto: ni un campo más (ni URL, ni cifras de personas).
CAMPOS_DEL_PUNTO = {"id", "capa", "lat", "lng", "etiqueta", "icono", "tono", "titulo", "subtitulo", "forma", "tamano"}


def _puntos(html):
    inicio = html.index(f'id="{ID_PUNTOS}"')
    return json.loads(html[html.index(">", inicio) + 1 : html.index("</script>", inicio)])


class BaseMapa(EscenarioSituacion):
    def setUp(self):
        super().setUp()
        self.autoridad = self._usuario("autoridad", [VER_SITUACION])

    def _respuesta(self, usuario, url=f"{URL}?tab=mapa"):
        self.client.force_login(usuario)
        respuesta = self.client.get(url)
        self.assertEqual(respuesta.status_code, 200)
        return respuesta

    def _html(self, usuario, url=f"{URL}?tab=mapa"):
        return self._respuesta(usuario, url).content.decode()


@override_settings(GOOGLE_MAPS_API_KEY="AIza-prueba")
class SolapaMapaTests(BaseMapa):
    def test_usa_la_pieza_sin_detalle_y_la_solapa_se_dibuja_sin_x_cloak(self):
        html = self._html(self.autoridad)
        self.assertIn('data-mapa-capas="situacion"', html)
        self.assertIn("data-sin-detalle", html)
        self.assertNotIn("data-a-pedido", html)
        self.assertIn('data-mapa="situacion"', html)
        self.assertIn("custom/css/nodo-mapa-capas.css", html)
        self.assertIn("custom/js/nodo-mapa-capas.js", html)
        self.assertIn("custom/js/nodo-mapa.js", html)
        self.assertRegex(html, r'<div x-show="tab===\'mapa\'" role="tabpanel" id="panel-mapa"')
        self.assertNotIn("El mapa todavía no está disponible", html)

    def test_tc_1185_02_y_03_un_circulo_por_localidad_y_los_dispositivos_publicables(self):
        puntos = {p["id"]: p for p in _puntos(self._html(self.autoridad))}
        self.assertEqual(
            set(puntos),
            {
                f"loc-{self.res.pk}",
                f"loc-{self.bar.pk}",
                f"loc-{self.bre.pk}",
                f"disp-{self.club.pk}",
                f"disp-{self.escuela.pk}",
            },
        )
        for punto in puntos.values():
            with self.subTest(punto=punto["id"]):
                self.assertLessEqual(set(punto), CAMPOS_DEL_PUNTO)
        resistencia = puntos[f"loc-{self.res.pk}"]
        self.assertEqual((resistencia["capa"], resistencia["forma"]), ("localidades", "circulo"))
        self.assertEqual((resistencia["lat"], resistencia["lng"]), (-27.4606, -58.9839))
        self.assertEqual(resistencia["tamano"], 3)  # la de más personas esperando (9)
        self.assertEqual(puntos[f"loc-{self.bre.pk}"]["tamano"], 2)  # 3 de 9
        club = puntos[f"disp-{self.club.pk}"]
        self.assertEqual((club["capa"], club["tono"]), ("dispositivos", "danger"))  # 9/10 con 50/80
        self.assertNotIn("forma", club)

    def test_tc_1185_04_capas_con_leyenda(self):
        html = self._html(self.autoridad)
        self.assertIn('data-mapa-capa="localidades" aria-pressed="true"', html)
        self.assertIn('data-mapa-capa="dispositivos" aria-pressed="true"', html)
        for texto in ("Sin demanda", "Sin plazas", "Más grande, más personas esperando."):
            with self.subTest(texto=texto):
                self.assertIn(texto, html)

    def test_tc_1185_05_panel_de_la_localidad(self):
        respuesta = self._respuesta(self.supervisor)
        (panel,) = [p for p in respuesta.context["mapa"]["localidades"] if p["id"] == f"loc-{self.res.pk}"]
        self.assertEqual(panel["titulo"], "Resistencia")
        self.assertEqual(panel["meta"], "Dpto. San Fernando")
        datos = dict(panel["datos"])
        self.assertEqual(
            (datos["Familias esperando"], datos["Personas esperando"], datos["Fuera de SLA"]), ("3", "9", "2")
        )
        self.assertEqual([c["nombre"] for c in panel["cercanos"]], ["Club Sarmiento", "Escuela 12"])
        self.assertRegex(panel["cercanos"][0]["detalle"], r"^\d+,\d km · \d+ libres de 10$")
        self.assertEqual(panel["reservadas"], "Incluye 6 camas en dispositivos de ubicación reservada.")
        self.assertEqual(panel["url"], f"/emergencia/casos/?solapa=abiertos&localidad={self.res.pk}")
        self.assertEqual(panel["url_texto"], "Ver los 3 casos en la bandeja")
        html = respuesta.content.decode()
        self.assertIn(f"x-show=\"elegido === 'loc-{self.res.pk}'\"", html)
        self.assertIn("@nodo-mapa-capas:seleccion=", html)

    def test_tc_1185_07_y_08_la_lista_coincide_con_la_tabla_del_resumen(self):
        contexto = self._respuesta(self.autoridad).context
        lista = contexto["mapa"]["lista"]
        self.assertEqual([item["nombre"] for item in lista], ["Resistencia", "Las Breñas", "Barranqueras"])
        tabla = {fila["localidad"]: fila["presion"]["texto"] for fila in contexto["presion"]["filas"]}
        for item in lista:
            with self.subTest(localidad=item["nombre"]):
                self.assertEqual(tabla[item["nombre"]], f"{item['etiqueta']} · {item['dato']}")
        self.assertTrue(all(item["dato"].endswith("×") for item in lista))
        self.assertEqual(contexto["mapa"]["lista_resumen"], "")

    def test_la_lista_se_recorta_con_su_total(self):
        with mock.patch.object(pantalla, "TOPE_MAS_PRESION", 2):
            contexto = self._respuesta(self.autoridad).context
        self.assertEqual(len(contexto["mapa"]["lista"]), 2)
        self.assertEqual(contexto["mapa"]["lista_resumen"], "Mostrando 2 de 3.")

    def test_tc_1185_06_la_lista_selecciona_el_punto_del_mapa(self):
        html = self._html(self.autoridad)
        lista = html.split('aria-labelledby="situacion-mas-presion-titulo"', 1)[1]
        self.assertIn(f'data-item="loc-{self.bre.pk}"', lista)
        self.assertIn('aria-pressed="false"', lista)

    def test_tc_1185_13_y_14_el_pie_cuenta_lo_que_no_se_dibuja(self):
        self.assertIn(
            "2 dispositivos sin ubicación · 1 con ubicación reservada · 2 casos de localidades sin ubicación",
            self._html(self.autoridad),
        )

    def test_tc_1185_16_ver_dispositivo_solo_si_dispositivos_lo_deja(self):
        enlace = reverse("dispositivos:detalle", args=[self.club.pk])
        self.assertNotIn(f'href="{enlace}"', self._html(self.autoridad))
        root = User.objects.create_superuser("root", "root@example.com", "x")
        html = self._html(root)
        self.assertIn(f'href="{enlace}"', html)
        self.assertIn("Ver dispositivo", html)

    def test_tc_1185_17_la_bandeja_solo_con_supervisar(self):
        bandeja = reverse("emergencia:bandeja")
        self.assertNotIn(bandeja, self._html(self.autoridad))
        self.assertIn(f'href="{bandeja}?solapa=abiertos&amp;localidad={self.bar.pk}"', self._html(self.supervisor))

    def test_c1_nada_de_terceros_en_la_pagina(self):
        html = self._html(self.supervisor)
        self.assertEqual(re.findall(r'(?:src|href)="(?:https?:)?//[^"]+"', html), [])
        self.assertNotIn("googleapis", html)
        self.assertNotIn("openstreetmap", html.lower())
        self.assertNotIn("leaflet", html.lower())

    def test_como_se_calcula_nombra_google_maps(self):
        self.assertIn("el fondo del mapa, de Google Maps", self._html(self.autoridad))


@override_settings(GOOGLE_MAPS_API_KEY="AIza-prueba")
class NoNominalDelMapaTests(BaseMapa):
    """RNF-009-01 sobre la respuesta: el HTML y el ``json_script`` de la solapa."""

    def test_rnf_009_01_ni_personas_ni_casos_ni_sus_coordenadas(self):
        html = self._html(self.supervisor)
        payload = json.dumps(_puntos(html))
        prohibidos = ["Benítez", "Av. Sarmiento 1200", "-27.4111", "-27,4111", "-58.9222"]
        prohibidos += list(CasoEmergencia.objects.values_list("numero", flat=True))
        prohibidos += [str(dni) for dni in range(90_000_001, 90_000_100)]
        for dato in prohibidos:
            with self.subTest(dato=dato):
                self.assertNotIn(dato, html)
                self.assertNotIn(dato, payload)

    def test_rnf_009_01_cada_coordenada_es_un_centroide_o_un_dispositivo_publicable(self):
        permitidas = {(float(u.latitud), float(u.longitud)) for u in UbicacionLocalidad.objects.all()} | {
            (float(d.latitud), float(d.longitud))
            for d in Dispositivo.objects.filter(latitud__isnull=False, tipo__ubicacion_reservada=False)
        }
        for punto in _puntos(self._html(self.supervisor)):
            with self.subTest(punto=punto["id"]):
                self.assertIn((punto["lat"], punto["lng"]), permitidas)

    def test_rn_009_13_mutacion_ubicacion_reservada_saca_al_dispositivo(self):
        antes = self._html(self.supervisor)
        self.assertIn(f"disp-{self.club.pk}", json.dumps(_puntos(antes)))
        self.assertIn("Club Sarmiento", antes)

        self.club.tipo.ubicacion_reservada = True
        self.club.tipo.save(update_fields=["ubicacion_reservada"])

        despues = self._html(self.supervisor)
        puntos = _puntos(despues)
        self.assertNotIn(f"disp-{self.club.pk}", [p["id"] for p in puntos])
        self.assertNotIn("Club Sarmiento", despues)
        self.assertNotIn("-58.98,", json.dumps(puntos))
        # Sus camas siguen sumando en las cercanas, como una línea sin nombre.
        self.assertIn("camas en dispositivos de ubicación reservada.", despues)


@override_settings(GOOGLE_MAPS_API_KEY="AIza-prueba")
class EstadosDelMapaTests(BaseMapa):
    def test_tc_1185_18_sin_ubicaciones_cargadas_dibuja_los_dispositivos(self):
        UbicacionLocalidad.objects.all().delete()
        html = self._html(self.autoridad)
        ids = [p["id"] for p in _puntos(html)]
        self.assertTrue(ids)
        self.assertTrue(all(i.startswith("disp-") for i in ids))
        self.assertIn("7 casos de localidades sin ubicación", html)
        self.assertIn("Ninguna localidad del mapa tiene gente esperando lugar.", html)

    def test_sin_nada_que_dibujar_estado_vacio(self):
        UbicacionLocalidad.objects.all().delete()
        Dispositivo.objects.update(latitud=None, longitud=None)
        html = self._html(self.autoridad)
        self.assertIn("Todavía no hay nada para ubicar en el mapa", html)
        self.assertNotIn("data-mapa-capas=", html)

    @override_settings(GOOGLE_MAPS_API_KEY="")
    def test_sin_key_la_pieza_avisa_y_la_lista_sigue(self):
        html = self._html(self.autoridad)
        self.assertIn("El mapa no está disponible en este ambiente", html)
        self.assertIn("Localidades con más presión", html)
        self.assertIn(f'data-item="loc-{self.res.pk}"', html)

    def test_tc_1185_20_desde_otra_solapa_el_mapa_va_oculto(self):
        html = self._html(self.autoridad, URL)
        self.assertRegex(html, r'<div x-show="tab===\'mapa\'" x-cloak role="tabpanel" id="panel-mapa"')
        self.assertIn('data-mapa-capas="situacion"', html)


class TamanoDeCirculoTests(SimpleTestCase):
    def test_crece_con_la_raiz_de_las_personas_esperando(self):
        self.assertEqual(tamano_de_circulo(133, 133), 3)
        self.assertEqual(tamano_de_circulo(15, 133), 2)
        self.assertEqual(tamano_de_circulo(10, 133), 1)
        self.assertEqual(tamano_de_circulo(0, 133), 1)
        self.assertEqual(tamano_de_circulo(0, 0), 1)

    def test_bordes_enteros(self):
        # √(1/9) = 1/3 y √(4/9) = 2/3: los bordes quedan en el escalón de abajo.
        self.assertEqual(tamano_de_circulo(1, 9), 1)
        self.assertEqual(tamano_de_circulo(4, 9), 2)
        self.assertEqual(tamano_de_circulo(5, 9), 3)


class DatoDePresionTests(SimpleTestCase):
    def test_cifra_sin_camas_o_nada(self):
        from programas.services.situacion_emergencia import Presion

        self.assertEqual(pantalla._dato_de_presion(Presion("critica", 3.2)), "3,2×")
        self.assertEqual(pantalla._dato_de_presion(Presion("critica", None)), "sin camas a 25 km")
        self.assertEqual(pantalla._dato_de_presion(Presion("sin_demanda", None)), "")
