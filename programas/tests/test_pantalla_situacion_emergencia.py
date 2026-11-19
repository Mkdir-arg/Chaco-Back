"""E8 · lo que escribe ``services/pantalla_situacion_emergencia.py`` (Cambio 509 · E-5 #1184).

Puros, sin base: los números y las filas llegan armados a mano (fotos de juguete) y se mira solo cómo se
escriben, se agrupan y se ordenan. Las reglas (presión, horas hasta saturar, alertas) tienen sus propios tests
en ``test_situacion_emergencia_reglas.py`` y ``test_emergencia_situacion.py``.
"""

from datetime import datetime
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from programas.selectors.emergencia_situacion import VENTANA_7D, VENTANA_72H, LocalidadDelChaco
from programas.services import pantalla_situacion_emergencia as pantalla
from programas.services.ocupacion import NIVEL_CRITICA, NIVEL_EXIGIDA, NIVEL_NORMAL, Tension
from programas.services.situacion_emergencia import (
    NIVEL_SIN_DEMANDA,
    NO_SE_SATURA,
    PROYECCION,
    SATURADA,
    SIN_DATOS,
    CamasCercanas,
    Presion,
    Saturacion,
)


def _tension(ocupadas, operativas, porcentaje, nivel):
    return Tension(ocupadas=ocupadas, operativas=operativas, porcentaje=porcentaje, nivel=nivel)


def _numeros(*, filtrado=False, tension=None):
    return {
        "filtrado": filtrado,
        "personas_alojadas": {
            "valor": 1284,
            "dispositivos": 38,
            "variacion_del_dia": 146,
            "desde": datetime(2026, 11, 18, 9),
        },
        "personas_esperando": {"valor": 412, "familias": 118, "fuera_de_sla": 37},
        "camas_libres": {
            "valor": 163,
            "reservadas": 54,
            "tension": tension or _tension(1633, 1850, 88, NIVEL_CRITICA),
        },
        "saturacion": Saturacion(PROYECCION, 10.9, 15.2, 132, 41, 163),
    }


class NumerosTests(SimpleTestCase):
    def test_numero_con_punto_de_miles_y_raya_sin_dato(self):
        self.assertEqual(pantalla.numero(1284), "1.284")
        self.assertEqual(pantalla.numero(0), "0")
        self.assertEqual(pantalla.numero(None), "—")

    def test_con_signo(self):
        self.assertEqual(pantalla.con_signo(146), "+146")
        self.assertEqual(pantalla.con_signo(-3), "−3")
        self.assertEqual(pantalla.con_signo(0), "0")
        self.assertEqual(pantalla.con_signo(1500), "+1.500")

    def test_cociente_con_coma(self):
        self.assertEqual(pantalla.cociente(3.24), "3,2")


class BajadaTests(SimpleTestCase):
    def test_la_frase_del_hero_del_analisis(self):
        self.assertEqual(
            pantalla.bajada(_numeros()),
            "1.284 personas alojadas en 38 dispositivos · 412 esperando lugar · 163 camas libres (88 % de ocupación).",
        )

    def test_con_filtro_las_camas_dicen_red_provincial(self):
        self.assertIn("163 camas libres en la red provincial", pantalla.bajada(_numeros(filtrado=True)))

    def test_sin_camas_operativas_no_hay_porcentaje(self):
        sin_plazas = _tension(0, 0, None, "sin_plazas")
        self.assertIn("(sin camas operativas)", pantalla.bajada(_numeros(tension=sin_plazas)))


class TarjetaSaturacionTests(SimpleTestCase):
    def test_proyeccion_redondeada_con_ritmo_y_rotulo(self):
        tarjeta = pantalla._tarjeta_saturacion(Saturacion(PROYECCION, 10.9, 15.2, 132, 41, 163), False)
        self.assertEqual((tarjeta["valor"], tarjeta["sufijo"], tarjeta["tono"]), ("≈ 11", " h", "danger"))
        self.assertEqual(
            tarjeta["nota"],
            "+15 camas/h netas en las últimas 6 h · proyección al ritmo actual, no es un pronóstico",
        )

    def test_proyeccion_lejana_es_warning(self):
        tarjeta = pantalla._tarjeta_saturacion(Saturacion(PROYECCION, 30.0, 2.0, 14, 2, 60), False)
        self.assertEqual(tarjeta["tono"], "warning")

    def test_red_saturada(self):
        tarjeta = pantalla._tarjeta_saturacion(Saturacion(SATURADA, None, 1.0, 6, 0, 0), False)
        self.assertEqual((tarjeta["valor"], tarjeta["tono"]), ("0", "danger"))
        self.assertEqual(tarjeta["nota"], "Red saturada: no quedan camas libres")

    def test_no_se_satura(self):
        tarjeta = pantalla._tarjeta_saturacion(Saturacion(NO_SE_SATURA, None, -0.5, 1, 4, 40), False)
        self.assertEqual((tarjeta["valor"], tarjeta["tono"]), ("—", "success"))
        self.assertTrue(tarjeta["nota"].startswith("No se satura al ritmo actual · "))

    def test_sin_datos(self):
        tarjeta = pantalla._tarjeta_saturacion(Saturacion(SIN_DATOS, None, 0.0, 0, 0, 40), False)
        self.assertEqual((tarjeta["valor"], tarjeta["nota"], tarjeta["tono"]), ("—", "Todavía no hay casos", "brand"))

    def test_con_filtro_dice_red_provincial(self):
        tarjeta = pantalla._tarjeta_saturacion(Saturacion(SIN_DATOS, None, 0.0, 0, 0, 40), True)
        self.assertEqual(tarjeta["nota"], "Red provincial · Todavía no hay casos")


def _fila(localidad_id, nombre, personas, presion, *, alojadas=0, cercanas=0, con_ubicacion=True):
    return {
        "localidad_id": localidad_id,
        "localidad": nombre,
        "departamento": "San Fernando" if localidad_id else "",
        "con_ubicacion": con_ubicacion,
        "familias": 1 if personas else 0,
        "personas": personas,
        "fuera_de_sla": 0,
        "alojadas": alojadas,
        "cercanas": None if localidad_id is None else CamasCercanas(cercanas, 0, 0, ()),
        "presion": presion,
    }


class TablaDePresionTests(SimpleTestCase):
    """Agrupa las sin demanda en «Otras localidades (N)», deja «Sin localidad» al final y respeta el orden."""

    FILAS = [
        _fila(1, "Barranqueras", 133, Presion(NIVEL_CRITICA, 3.24), cercanas=41),
        _fila(2, "Las Breñas", 3, Presion(NIVEL_CRITICA, None)),
        _fila(3, "Fontana", 33, Presion(NIVEL_EXIGIDA, 0.8), cercanas=41, con_ubicacion=False),
        _fila(4, "Quitilipi", 9, Presion(NIVEL_NORMAL, 0.2), cercanas=46),
        _fila(5, "Charata", 0, Presion(NIVEL_SIN_DEMANDA, None), alojadas=12),
        _fila(6, "Villa Ángela", 0, Presion(NIVEL_SIN_DEMANDA, None), alojadas=1200),
        _fila(None, "Sin localidad", 2, None, alojadas=1),
    ]

    def _tabla(self, supervisa=False):
        with mock.patch.object(pantalla, "presion_por_localidad", return_value=self.FILAS):
            return pantalla.tabla_de_presion(SimpleNamespace(), supervisa=supervisa)

    def test_orden_agrupado_y_sin_localidad_al_final(self):
        tabla = self._tabla()
        self.assertEqual(
            [fila["localidad"] for fila in tabla["filas"]],
            ["Barranqueras", "Las Breñas", "Fontana", "Quitilipi", "Otras localidades (2)", "Sin localidad"],
        )
        otras = tabla["filas"][4]
        self.assertEqual(
            (otras["personas"], otras["alojadas"], otras["presion"]["texto"]), ("0", "1.212", "Sin demanda")
        )

    def test_presion_escrita_con_icono(self):
        filas = self._tabla()["filas"]
        self.assertEqual(
            filas[0]["presion"], {"texto": "Crítica · 3,2×", "tono": "danger", "icono": "fa-circle-exclamation"}
        )
        self.assertEqual(filas[1]["presion"]["texto"], "Crítica · sin camas a 25 km")
        self.assertEqual(filas[2]["presion"]["tono"], "warning")
        self.assertTrue(filas[2]["sin_ubicacion"])
        self.assertEqual(filas[-1]["presion"]["texto"], "—")

    def test_el_total_suma_todas_las_filas(self):
        self.assertEqual(
            self._tabla()["total"], {"familias": "5", "personas": "180", "fuera_de_sla": "0", "alojadas": "1.213"}
        )

    def test_la_bandeja_solo_con_supervisar(self):
        self.assertEqual({fila["url"] for fila in self._tabla()["filas"]}, {""})
        self.assertEqual(self._tabla(supervisa=True)["filas"][0]["url"], "/emergencia/casos/?localidad=1")


class AtencionTests(SimpleTestCase):
    def _alerta(self, n):
        return {"regla": "AE-1", "tono": "danger", "icono": "circle-exclamation", "titulo": f"Alerta {n}", "texto": ""}

    def _atencion(self, mostradas, total, supervisa=False):
        resultado = {"alertas": [self._alerta(n) for n in range(mostradas)], "total": total}
        with mock.patch.object(pantalla, "alertas_de_situacion", return_value=resultado):
            return pantalla.atencion(SimpleNamespace(), supervisa=supervisa)

    def test_mostrando_n_de_m_con_el_tope(self):
        self.assertEqual(self._atencion(6, 8)["resumen"], "Mostrando 6 de 8. Primero las de prioridad alta.")

    def test_sin_recorte_y_sin_alertas(self):
        self.assertEqual(self._atencion(1, 1)["resumen"], "1 alerta, primero las de prioridad alta.")
        self.assertEqual(self._atencion(0, 0)["resumen"], "Ninguna alerta estratégica con estos filtros.")

    def test_solo_ae_6_enlaza_y_los_avisos_operativos_solo_con_supervisar(self):
        """Ninguna enlaza a un caso; AE-6 lleva a la solapa Abastecimiento (RN-009-22, TC-1187-35)."""
        atencion = self._atencion(2, 2)
        self.assertEqual(set(atencion["avisos"][0]), {"tono", "icono", "titulo", "texto", "url", "accion"})
        self.assertEqual({(a["url"], a["accion"]) for a in atencion["avisos"]}, {("", "")})
        resultado = {"alertas": [{**self._alerta(0), "regla": "AE-6"}], "total": 1}
        with mock.patch.object(pantalla, "alertas_de_situacion", return_value=resultado):
            ae_6 = pantalla.atencion(SimpleNamespace(), supervisa=False)["avisos"][0]
        self.assertEqual(
            (ae_6["url"], ae_6["accion"]), ("/emergencia/situacion/?tab=abastecimiento", "Ver el abastecimiento")
        )
        self.assertEqual(atencion["url_avisos_operativos"], "")
        self.assertEqual(self._atencion(2, 2, supervisa=True)["url_avisos_operativos"], "/emergencia/tablero/")


class PildorasTests(SimpleTestCase):
    LOCALIDADES = {
        1: LocalidadDelChaco(1, "La Esperanza", None, None, "Libertador General San Martín"),
        2: LocalidadDelChaco(2, "La Esperanza", None, None, "San Fernando"),
        3: LocalidadDelChaco(3, "Resistencia", None, None, "San Fernando"),
        4: LocalidadDelChaco(4, "Sin centro", None, None, ""),
    }

    def _pildoras(self, departamento="", ventana=VENTANA_72H):
        foto = SimpleNamespace(
            filtros=SimpleNamespace(departamento=departamento, localidad_id=None, ventana=ventana),
            localidades=self.LOCALIDADES,
        )
        return {pildora["nombre"]: pildora for pildora in pantalla.pildoras(foto)}

    def test_homonimas_con_su_departamento(self):
        opciones = self._pildoras()["localidad"]["opciones"]
        self.assertEqual(
            opciones,
            [
                (1, "La Esperanza (Libertador General San Martín)"),
                (2, "La Esperanza (San Fernando)"),
                (3, "Resistencia"),
                (4, "Sin centro"),
            ],
        )

    def test_la_localidad_sigue_al_departamento(self):
        pildoras = self._pildoras(departamento="San Fernando")
        self.assertEqual(pildoras["localidad"]["opciones"], [(2, "La Esperanza"), (3, "Resistencia")])
        self.assertEqual(
            pildoras["departamento"]["opciones"],
            [("Libertador General San Martín", "Libertador General San Martín"), ("San Fernando", "San Fernando")],
        )

    def test_ventana_72_h_es_la_opcion_vacia(self):
        self.assertEqual(self._pildoras()["ventana"]["valor"], "")
        self.assertEqual(self._pildoras()["ventana"]["todos"], "72 h")
        self.assertEqual(self._pildoras(ventana=VENTANA_7D)["ventana"]["valor"], VENTANA_7D)


class EmbudoTests(SimpleTestCase):
    def test_el_p90_que_supera_el_objetivo_lo_dice_en_texto(self):
        datos = {
            "hay_casos": True,
            "pasos": [
                {"paso": "relevados", "casos": 10, "conversion": None},
                {"paso": "tomados", "casos": 9, "conversion": 90},
            ],
            "tramos": [{"tramo": "tomar", "casos": 9, "mediana_min": 9, "p90_min": 22, "objetivo_min": 15}],
            "cerrados_sin_alojar": {"total": 0, "por_motivo": {}},
            "rechazadas": {"total": 0, "por_motivo": {}},
            "vencidas": 0,
            "ingresos_directos": 0,
        }
        with mock.patch.object(pantalla, "embudo", return_value=datos):
            filas = pantalla.bloque_de_embudo(SimpleNamespace())["filas"]
        self.assertEqual((filas[0]["p90_supera"], filas[0]["p90_nota"]), (False, ""))
        self.assertEqual((filas[1]["p90_supera"], filas[1]["p90_nota"]), (True, " (supera el objetivo)"))


class SinEntregaTests(SimpleTestCase):
    def test_tope_con_mostrando_n_de_m(self):
        filas = [
            {
                "id": n,
                "nombre": f"D{n}",
                "localidad": "",
                "reservado": False,
                "personas": 3,
                "ultima_recepcion": None,
                "horas": None,
            }
            for n in range(pantalla.TOPE_SIN_ENTREGA + 2)
        ]
        datos = {
            "despachadas": 0,
            "recibidas": 0,
            "con_diferencias": 0,
            "en_camino": 0,
            "transito_mediano_min": None,
            "por_item": [],
            "sin_entrega_48h": filas,
        }
        with mock.patch.object(pantalla, "logistica", return_value=datos):
            bloque = pantalla.bloque_de_logistica(SimpleNamespace(), dispositivos_visibles=frozenset())
        self.assertEqual(len(bloque["sin_entrega"]), pantalla.TOPE_SIN_ENTREGA)
        self.assertEqual(bloque["sin_entrega_resumen"], f"Mostrando {pantalla.TOPE_SIN_ENTREGA} de {len(filas)}.")
        self.assertEqual(bloque["sin_entrega"][0]["detalle"], "3 personas, nunca recibió")
