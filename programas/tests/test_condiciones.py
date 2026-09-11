"""Motor de condiciones (Cambio 58, RN-6/RN-7; task #341)."""

from datetime import date

from django.test import SimpleTestCase

from programas.models import TipoCampo
from programas.services.condiciones import (
    OPERADORES_POR_TIPO,
    aplicar,
    edad_en_anios,
    evaluar,
    evaluar_regla,
    fuentes_disponibles,
    validar_coherencia,
    validar_condicion,
)

HOY = date(2026, 8, 28)


def regla(op, fuente="f", valor=None):
    return {"fuente": fuente, "op": op, "valor": valor}


class OperadoresTests(SimpleTestCase):
    def test_selector(self):
        self.assertTrue(evaluar_regla(regla("es", valor="Terciario"), "Terciario"))
        self.assertFalse(evaluar_regla(regla("es", valor="Terciario"), "Primario"))
        self.assertTrue(evaluar_regla(regla("no_es", valor="Terciario"), "Primario"))
        self.assertTrue(evaluar_regla(regla("es_alguno", valor=["Terciario", "Universitario"]), "Universitario"))
        self.assertFalse(evaluar_regla(regla("es_alguno", valor=["Terciario"]), "Primario"))

    def test_selector_multiple(self):
        self.assertTrue(evaluar_regla(regla("incluye", valor="AUH"), ["AUH", "Pensión"]))
        self.assertFalse(evaluar_regla(regla("incluye", valor="AUH"), ["Pensión"]))
        self.assertTrue(evaluar_regla(regla("no_incluye", valor="AUH"), ["Pensión"]))
        self.assertTrue(evaluar_regla(regla("incluye_alguno", valor=["AUH", "Tarjeta"]), ["Tarjeta"]))
        self.assertFalse(evaluar_regla(regla("incluye_alguno", valor=["AUH"]), []))

    def test_numero(self):
        self.assertTrue(evaluar_regla(regla("lt", valor=3), "2"))
        self.assertTrue(evaluar_regla(regla("ge", valor=3), 3))
        self.assertFalse(evaluar_regla(regla("gt", valor=3), 3))
        self.assertTrue(evaluar_regla(regla("ne", valor=3), 4))
        self.assertFalse(evaluar_regla(regla("eq", valor=3), "tres"))

    def test_fecha_y_edad(self):
        nacimiento = "2010-03-14"  # 16 años el 28/08/2026
        self.assertEqual(edad_en_anios(nacimiento, HOY), 16)
        self.assertTrue(evaluar_regla(regla("edad_menor", valor=18), nacimiento, HOY))
        self.assertFalse(evaluar_regla(regla("edad_mayor", valor=18), nacimiento, HOY))
        self.assertTrue(evaluar_regla(regla("edad_igual", valor=16), nacimiento, HOY))
        self.assertTrue(evaluar_regla(regla("edad_entre", valor=[12, 17]), nacimiento, HOY))
        self.assertFalse(evaluar_regla(regla("edad_entre", valor=[18, 25]), nacimiento, HOY))
        self.assertTrue(evaluar_regla(regla("anterior", valor="2011-01-01"), nacimiento))
        self.assertTrue(evaluar_regla(regla("posterior", valor="2009-01-01"), "14/03/2010"))

    def test_cumple_18_hoy_no_es_menor(self):
        self.assertFalse(evaluar_regla(regla("edad_menor", valor=18), "2008-08-28", HOY))
        self.assertTrue(evaluar_regla(regla("edad_menor", valor=18), "2008-08-29", HOY))

    def test_texto_y_archivo(self):
        self.assertTrue(evaluar_regla(regla("completo"), "algo"))
        self.assertFalse(evaluar_regla(regla("completo"), "   "))
        self.assertTrue(evaluar_regla(regla("vacio"), ""))
        self.assertTrue(evaluar_regla(regla("adjuntado"), "cert.pdf"))
        self.assertTrue(evaluar_regla(regla("no_adjuntado"), None))

    def test_fuente_vacia_no_cumple_salvo_vacio(self):
        for op, valor in (
            ("es", "X"),
            ("lt", 3),
            ("edad_menor", 18),
            ("incluye", "A"),
            ("completo", None),
            ("adjuntado", None),
        ):
            self.assertFalse(evaluar_regla(regla(op, valor=valor), None), op)
            self.assertFalse(evaluar_regla(regla(op, valor=valor), ""), op)
        self.assertTrue(evaluar_regla(regla("vacio"), None))
        self.assertTrue(evaluar_regla(regla("no_adjuntado"), ""))

    def test_fecha_ilegible_no_cumple(self):
        self.assertFalse(evaluar_regla(regla("edad_menor", valor=18), "ayer", HOY))
        self.assertIsNone(edad_en_anios("ayer", HOY))

    def test_operador_desconocido_no_cumple(self):
        self.assertFalse(evaluar_regla(regla("magia", valor=1), "1"))

    def test_todos_los_tipos_tienen_operadores(self):
        for tipo in TipoCampo:
            self.assertIn(tipo, OPERADORES_POR_TIPO)


class EvaluarTests(SimpleTestCase):
    def test_sin_condicion_se_muestra(self):
        self.assertTrue(evaluar(None, {}))
        self.assertTrue(evaluar({}, {}))
        self.assertTrue(evaluar({"modo": "todas", "reglas": []}, {}))

    def test_todas_y_alguna(self):
        condicion = {"modo": "todas", "reglas": [regla("es", "nivel", "Terciario"), regla("completo", "escuela")]}
        self.assertTrue(evaluar(condicion, {"nivel": "Terciario", "escuela": "X"}))
        self.assertFalse(evaluar(condicion, {"nivel": "Terciario", "escuela": ""}))
        condicion["modo"] = "alguna"
        self.assertTrue(evaluar(condicion, {"nivel": "Terciario", "escuela": ""}))
        self.assertFalse(evaluar(condicion, {"nivel": "Primario", "escuela": ""}))

    def test_apoderado_por_edad(self):
        apoderado = {"modo": "todas", "reglas": [regla("edad_menor", "pg-fecha", 18)]}
        self.assertTrue(evaluar(apoderado, {"pg-fecha": "2010-03-14"}, HOY))
        self.assertFalse(evaluar(apoderado, {"pg-fecha": "1991-03-14"}, HOY))
        self.assertFalse(evaluar(apoderado, {}, HOY))  # sin fecha no se determina → oculto


ITEMS = [
    {"clave": "g-datos", "tipo": "grupo", "padre": None, "condicion": None},
    {"clave": "pg-fecha", "tipo": "campo", "tipo_campo": TipoCampo.DATE, "padre": "g-datos", "condicion": None},
    {
        "clave": "g-apoderado",
        "tipo": "grupo",
        "padre": None,
        "condicion": {"modo": "todas", "reglas": [regla("edad_menor", "pg-fecha", 18)]},
    },
    {
        "clave": "pg-apo-nombre",
        "tipo": "campo",
        "tipo_campo": TipoCampo.STRING,
        "padre": "g-apoderado",
        "condicion": None,
    },
    {"clave": "g-edu", "tipo": "grupo", "padre": None, "condicion": None},
    {"clave": "rn-nivel", "tipo": "campo", "tipo_campo": TipoCampo.SELECTOR, "padre": "g-edu", "condicion": None},
    {"clave": "t-1", "tipo": "texto", "padre": "g-edu", "condicion": None},
    {
        "clave": "rn-cert",
        "tipo": "campo",
        "tipo_campo": TipoCampo.ARCHIVO,
        "padre": "g-edu",
        "condicion": {"modo": "todas", "reglas": [regla("es_alguno", "rn-nivel", ["Terciario", "Universitario"])]},
    },
    {
        "clave": "rn-univ",
        "tipo": "campo",
        "tipo_campo": TipoCampo.STRING,
        "padre": "g-edu",
        "condicion": {"modo": "todas", "reglas": [regla("adjuntado", "rn-cert")]},
    },
]


class AplicarTests(SimpleTestCase):
    def test_menor_con_terciario(self):
        respuestas = {
            "pg-fecha": "2010-03-14",
            "pg-apo-nombre": "Graciela",
            "rn-nivel": "Terciario",
            "rn-cert": "c.pdf",
            "rn-univ": "UNNE",
        }
        visibles, ocultos, efectivas = aplicar(ITEMS, respuestas, HOY)
        self.assertIn("g-apoderado", visibles)
        self.assertIn("pg-apo-nombre", visibles)
        self.assertIn("rn-cert", visibles)
        self.assertIn("rn-univ", visibles)
        self.assertEqual(ocultos, set())
        self.assertEqual(efectivas["rn-univ"], "UNNE")

    def test_mayor_con_secundario_descarta_lo_oculto(self):
        respuestas = {
            "pg-fecha": "1991-03-14",
            "pg-apo-nombre": "basura",
            "rn-nivel": "Secundario",
            "rn-cert": "c.pdf",
            "rn-univ": "basura",
        }
        visibles, ocultos, efectivas = aplicar(ITEMS, respuestas, HOY)
        self.assertIn("g-apoderado", ocultos)
        self.assertIn("pg-apo-nombre", ocultos)  # hijo de grupo oculto
        self.assertIn("rn-cert", ocultos)
        # Encadenamiento: rn-univ depende de rn-cert, que quedó oculto → vacío → oculto.
        self.assertIn("rn-univ", ocultos)
        self.assertNotIn("pg-apo-nombre", efectivas)
        self.assertNotIn("rn-cert", efectivas)
        self.assertNotIn("rn-univ", efectivas)
        self.assertEqual(efectivas["rn-nivel"], "Secundario")

    def test_los_grupos_no_llevan_respuesta(self):
        _, _, efectivas = aplicar(ITEMS, {"g-datos": "x", "pg-fecha": "2010-03-14"}, HOY)
        self.assertNotIn("g-datos", efectivas)


class CoherenciaTests(SimpleTestCase):
    def test_diseno_coherente(self):
        self.assertEqual(validar_coherencia(ITEMS), {})

    def test_una_regla_malformada_es_un_error_no_una_excepcion(self):
        anteriores = {"f": {"tipo": "campo", "tipo_campo": TipoCampo.INT}}
        condicion = {
            "modo": "todas",
            "reglas": [
                "f",
                {"fuente": ["f"], "op": "eq", "valor": 1},
                {"fuente": "f", "op": ["eq"], "valor": 1},
                {"fuente": "f", "op": "eq", "valor": 1},
            ],
        }
        errores = validar_condicion(condicion, {"clave": "x"}, anteriores)
        self.assertEqual(len(errores), 3)

    def test_fuente_posterior_o_inexistente(self):
        items = [
            {
                "clave": "a",
                "tipo": "campo",
                "tipo_campo": TipoCampo.STRING,
                "condicion": {"modo": "todas", "reglas": [regla("completo", "b")]},
            },
            {
                "clave": "b",
                "tipo": "campo",
                "tipo_campo": TipoCampo.STRING,
                "condicion": {"modo": "todas", "reglas": [regla("completo", "zzz")]},
            },
        ]
        errores = validar_coherencia(items)
        self.assertIn("a", errores)
        self.assertIn("b", errores)
        self.assertIn("está después", errores["a"][0])

    def test_no_depende_de_si_mismo(self):
        items = [
            {
                "clave": "a",
                "tipo": "campo",
                "tipo_campo": TipoCampo.STRING,
                "condicion": {"modo": "todas", "reglas": [regla("completo", "a")]},
            }
        ]
        self.assertIn("sí mismo", validar_coherencia(items)["a"][0])

    def test_operador_incompatible_con_el_tipo(self):
        items = [
            {"clave": "txt", "tipo": "campo", "tipo_campo": TipoCampo.STRING, "condicion": None},
            {
                "clave": "b",
                "tipo": "campo",
                "tipo_campo": TipoCampo.STRING,
                "condicion": {"modo": "todas", "reglas": [regla("edad_menor", "txt", 18)]},
            },
        ]
        self.assertIn("no aplica", validar_coherencia(items)["b"][0])

    def test_un_texto_o_un_grupo_no_son_fuente(self):
        items = [
            {"clave": "g", "tipo": "grupo", "condicion": None},
            {"clave": "t", "tipo": "texto", "condicion": None},
            {
                "clave": "b",
                "tipo": "campo",
                "tipo_campo": TipoCampo.STRING,
                "condicion": {"modo": "alguna", "reglas": [regla("completo", "g"), regla("completo", "t")]},
            },
        ]
        self.assertEqual(len(validar_coherencia(items)["b"]), 2)

    def test_valor_requerido_y_listas(self):
        items = [
            {"clave": "sel", "tipo": "campo", "tipo_campo": TipoCampo.SELECTOR, "condicion": None},
            {
                "clave": "b",
                "tipo": "campo",
                "tipo_campo": TipoCampo.STRING,
                "condicion": {"modo": "todas", "reglas": [regla("es", "sel", ""), regla("es_alguno", "sel", "A")]},
            },
        ]
        errores = validar_coherencia(items)["b"]
        self.assertTrue(any("necesita un valor" in e for e in errores))
        self.assertTrue(any("lista" in e for e in errores))

    def test_modo_desconocido(self):
        items = [
            {"clave": "a", "tipo": "campo", "tipo_campo": TipoCampo.STRING, "condicion": None},
            {
                "clave": "b",
                "tipo": "campo",
                "tipo_campo": TipoCampo.STRING,
                "condicion": {"modo": "quizas", "reglas": [regla("completo", "a")]},
            },
        ]
        self.assertIn("Modo desconocido", validar_coherencia(items)["b"][0])

    def test_fuentes_disponibles_son_los_campos_anteriores(self):
        claves = [f["clave"] for f in fuentes_disponibles(ITEMS, "rn-cert")]
        self.assertEqual(claves, ["pg-fecha", "pg-apo-nombre", "rn-nivel"])
        self.assertEqual(fuentes_disponibles(ITEMS, "g-datos"), [])
