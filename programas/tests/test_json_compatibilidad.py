"""Los JSON guardados con la forma vieja se siguen leyendo (RED-40).

Ocho `JSONField` del dominio de Becas tienen contrato implícito: `validators` = 0
y la forma la sostiene el código que escribe. Un renombre adentro del JSON
—`presentacion` → `modo_presentacion` en `ItemDiseno.propio`— no rompe nada:
`propio.get("presentacion", "LISTA")` devuelve el default y **todos los
selectores propios ya guardados vuelven a «LISTA»** sin un error.

Dos mitades:

1. `DatosViejosTests` — los casos y los ítems con la forma anterior se siguen
   leyendo por los tres caminos que los miran (revisión, definición de la app,
   traducción del contrato legacy).
2. `VerificarJsonGuardadoTests` — el comando de diagnóstico
   `verificar_json_guardado` detecta cada forma rota. Es la foto que hay que
   sacar contra un dump de producción **antes** de cambiar una forma.

**Desvío de la ficha, code-first.** La ficha pedía un caso con la `definicion`
«de la forma anterior al Cambio 58 (listas planas `globales`/`requisitos`, sin
`items`)». Esa fila **no puede existir**: el campo `Formulario.definicion` nació
en `programas.0062`, que es del propio Cambio 58, junto con `foto_definicion`,
que siempre escribe `{version, canal, items}`. Lo viejo de verdad es
`definicion = NULL` con `data` en el contrato plano de la app, y eso es lo que se
prueba acá. Lo mismo con `propio` sin `presentacion`: hoy el form siempre la
escribe, así que el test fija que la **clave** es el contrato (un renombre lo
pone rojo) y, aparte, que un `propio` sin ella se sigue leyendo.
"""

from datetime import date
from io import StringIO

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase

from programas.management.commands.verificar_json_guardado import (
    CLAVES_APODERADO,
    CLAVES_SIIS_CONSUMIDAS,
    _problemas_de_condicion,
    _problemas_de_datos_siis,
    _problemas_de_definicion,
    _problemas_de_propio,
    resumen,
    revisar,
)
from programas.models import (
    Convocatoria,
    DisenoFormulario,
    Formulario,
    GrupoRequisito,
    ItemDiseno,
    PreguntaGlobal,
    Relevamiento,
    Segmento,
    TipoCampo,
)
from programas.services.becas import definicion_formulario
from programas.services.diseno import campo_dict, clave_pregunta, obtener_o_crear_diseno
from programas.services.respuestas import respuestas_legibles, sincronizar_desde_legacy
from programas.validadores import validar_condicion_json


class _Base(TestCase):
    def setUp(self):
        self.segmento = Segmento.objects.create(nombre="Educación", cupo_maximo=10)
        self.convocatoria = Convocatoria.objects.create(
            nombre="Becas 2026",
            segmento=self.segmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        self.pregunta = PreguntaGlobal.objects.create(
            texto="Tenencia de la vivienda",
            tipo=TipoCampo.SELECTOR,
            opciones=["Propia", "Alquilada"],
            orden=600,
        )
        # Público: sin territorial, que es lo que exige el CheckConstraint.
        self.relevamiento = Relevamiento.objects.create(
            convocatoria=self.convocatoria,
            tipo=Relevamiento.Tipo.PUBLICO,
            fecha_asignada=date(2026, 6, 1),
            zona="Zona de prueba",
        )

    def _diseno(self):
        diseno, _ = obtener_o_crear_diseno(self.convocatoria)
        return diseno

    def _item_propio(self, propio):
        diseno = self._diseno()
        grupo = diseno.items.filter(tipo=ItemDiseno.Tipo.GRUPO).first()
        return ItemDiseno.objects.create(
            diseno=diseno,
            tipo=ItemDiseno.Tipo.CAMPO,
            clave="cp-viejo",
            padre=grupo,
            orden=99,
            propio=propio,
        )


class DatosViejosTests(_Base):
    """RED-40: lo guardado antes se sigue leyendo igual."""

    def test_un_propio_sin_presentacion_se_lee_como_lista(self):
        """La forma anterior al Cambio 56: sin `presentacion` ni `opciones`."""
        item = self._item_propio({"texto": "Pregunta vieja", "tipo": TipoCampo.SELECTOR, "obligatorio": True})

        datos = campo_dict(item)

        self.assertEqual(datos["presentacion"], "LISTA")
        self.assertEqual(datos["opciones"], [])
        self.assertEqual(datos["tipo"], TipoCampo.SELECTOR)
        self.assertTrue(datos["obligatorio"])

    def test_la_clave_presentacion_es_el_contrato(self):
        """Renombrarla adentro del JSON no rompe nada: todo vuelve a «LISTA».

        Este test es el que se pone rojo ante ese renombre, que es justo el
        cambio que la ficha señala como invisible.
        """
        item = self._item_propio(
            {"texto": "Localidad", "tipo": TipoCampo.SELECTOR, "opciones": ["A", "B"], "presentacion": "BUSCADOR"}
        )

        self.assertEqual(campo_dict(item)["presentacion"], "BUSCADOR")

    def test_un_caso_sin_foto_de_definicion_no_rompe_la_revision(self):
        """`definicion = NULL` es el caso anterior al Cambio 58 (no una foto plana).

        `respuestas_legibles` devuelve `None` y el lector cae al camino viejo por
        pk. Si alguna vez devolviera `[]`, la revisión mostraría el caso **vacío**
        en vez de caer al fallback.
        """
        caso = Formulario.objects.create(relevamiento=self.relevamiento, definicion=None)

        self.assertIsNone(respuestas_legibles(caso))

    def test_un_caso_legacy_se_traduce_a_respuestas_por_clave(self):
        """`data` con listas planas `globales`/`requisitos` por pk: el contrato
        de la app de campo anterior al Cambio 58."""
        caso = Formulario.objects.create(
            relevamiento=self.relevamiento,
            definicion=None,
            data={"globales": {str(self.pregunta.pk): "Alquilada"}, "requisitos": {}},
        )

        respuestas = sincronizar_desde_legacy(caso)

        caso.refresh_from_db()
        self.assertEqual(respuestas[clave_pregunta(self.pregunta)], "Alquilada")
        # Y al traducirlo se le guarda la foto de hoy, con la forma nueva.
        # `destinos_siis` entró con el Cambio 158 (G1-08): su **presencia** es lo
        # que distingue una foto nueva de una vieja, así que va en el contrato.
        self.assertEqual(set(caso.definicion), {"version", "canal", "items", "destinos_siis"})

    def test_la_definicion_para_la_app_conserva_las_listas_planas(self):
        """`globales` y `requisitos` siguen saliendo planos para la app vieja,
        al lado de `items`. Sacarlos deja a la app de campo sin formulario."""
        definicion = definicion_formulario(self.relevamiento)

        self.assertEqual(
            set(definicion),
            {"requiere_gps", "canal", "version", "items", "globales", "requisitos"},
        )
        self.assertIsInstance(definicion["globales"], list)
        self.assertIsInstance(definicion["requisitos"], list)


class VerificarJsonGuardadoTests(_Base):
    """El comando de diagnóstico ve cada forma rota. Solo lectura."""

    def test_una_condicion_con_un_operador_inexistente_se_detecta(self):
        """El que más duele: `evaluar_regla` cae al `return False` y el ítem
        condicionado no se muestra **nunca**."""
        problemas = _problemas_de_condicion(
            {"modo": "todas", "reglas": [{"fuente": "pg-1", "op": "mayor_que", "valor": 3}]}, "x"
        )

        self.assertEqual([p["problema"] for p in problemas], ["operador_desconocido"])

    def test_una_condicion_sana_no_reporta_nada(self):
        sana = {"modo": "alguna", "reglas": [{"fuente": "pg-1", "op": "es", "valor": "Propia"}]}

        self.assertEqual(_problemas_de_condicion(sana, "x"), [])
        self.assertEqual(_problemas_de_condicion(None, "x"), [])

    def test_una_condicion_deforme_se_detecta(self):
        for condicion, esperado in (
            ("todas", "condicion_no_es_objeto"),
            ({"modo": "ambas", "reglas": []}, "modo_desconocido"),
            ({"modo": "todas", "reglas": "pg-1"}, "reglas_no_es_lista"),
            ({"modo": "todas", "reglas": ["pg-1"]}, "regla_no_es_objeto"),
            ({"modo": "todas", "reglas": [{"op": "es", "valor": "x"}]}, "regla_sin_fuente"),
        ):
            with self.subTest(condicion=condicion):
                self.assertIn(esperado, [p["problema"] for p in _problemas_de_condicion(condicion, "x")])

    def test_un_propio_sin_tipo_o_sin_presentacion_se_detecta(self):
        problemas = [p["problema"] for p in _problemas_de_propio({"texto": "x"}, "y")]

        self.assertEqual(sorted(problemas), ["propio_sin_presentacion", "propio_sin_tipo"])

    def test_una_definicion_plana_se_detecta(self):
        problemas = [p["problema"] for p in _problemas_de_definicion({"globales": [], "requisitos": []}, "y")]

        self.assertEqual(sorted(problemas), ["definicion_sin_items", "definicion_sin_version"])

    def test_un_datos_siis_con_claves_que_nadie_consume_se_detecta(self):
        problemas = _problemas_de_datos_siis({"barrio_actual": "Centro", "inventado": 1}, "y")

        self.assertEqual([p["problema"] for p in problemas], ["datos_siis_con_claves_no_consumidas"])
        self.assertEqual(problemas[0]["detalle"], "inventado")

    def test_las_claves_del_apoderado_siguen_siendo_las_que_lee_el_payload(self):
        """`CLAVES_APODERADO` está escrita a mano: si `siis_envio` empieza a leer
        otra corrección del apoderado, el comando la reportaría como «no
        consumida» y mandaría a borrar un dato que sí se usa."""
        from pathlib import Path

        from django.conf import settings

        fuente = (Path(settings.BASE_DIR) / "programas" / "services" / "siis_envio.py").read_text(encoding="utf-8")

        leidas = {
            clave
            for clave in CLAVES_SIIS_CONSUMIDAS
            if f'correcciones.get("{clave}")' in fuente or f'correcciones.get("{clave}",' in fuente
        }

        self.assertTrue(set(CLAVES_APODERADO) <= leidas, f"el payload ya no lee: {set(CLAVES_APODERADO) - leidas}")

    def test_el_comando_corre_sobre_la_base_y_no_escribe(self):
        self._item_propio({"texto": "Pregunta vieja", "tipo": TipoCampo.SELECTOR})
        Formulario.objects.create(relevamiento=self.relevamiento, datos_siis={"inventado": 1})
        antes = DisenoFormulario.objects.values_list("version", flat=True).first()

        salida = StringIO()
        call_command("verificar_json_guardado", "--json", stdout=salida)

        conteo = resumen(revisar())
        self.assertEqual(conteo["propio_sin_presentacion"], 1)
        self.assertEqual(conteo["datos_siis_con_claves_no_consumidas"], 1)
        self.assertIn("datos_siis_con_claves_no_consumidas", salida.getvalue())
        self.assertEqual(DisenoFormulario.objects.values_list("version", flat=True).first(), antes)

    def test_sin_problemas_el_comando_lo_dice(self):
        salida = StringIO()

        call_command("verificar_json_guardado", stdout=salida)

        self.assertIn("Sin problemas", salida.getvalue())


class ValidadorDeCondicionTests(_Base):
    """La parte Ola 3 de RED-40: `validators` en los dos `JSONField` que guardan
    una condición.

    El diagnóstico (`verificar_json_guardado`, parte R) dice qué hay roto en lo
    ya guardado; esto impide que entre lo siguiente. El hallazgo que ordena la
    lista: un operador fuera de `OPERADORES_POR_TIPO` cae al `return False`
    final de `evaluar_regla`, así que el ítem condicionado **no se muestra
    nunca** — sin error, sin log y sin forma de notarlo desde la pantalla.

    El validador mira la **forma**, no la coherencia: que la fuente exista, esté
    antes y el operador aplique al tipo de **ese** campo lo decide
    `condiciones.validar_condicion`, que necesita el diseño alrededor.
    """

    def _item(self, condicion):
        diseno = self._diseno()
        grupo = diseno.items.filter(tipo=ItemDiseno.Tipo.GRUPO).first()
        return ItemDiseno(
            diseno=diseno,
            tipo=ItemDiseno.Tipo.CAMPO,
            clave="cp-condicionado",
            padre=grupo,
            orden=98,
            condicion=condicion,
        )

    def test_un_operador_inventado_no_se_guarda(self):
        item = self._item({"modo": "todas", "reglas": [{"fuente": "pg-1", "op": "mayor_que", "valor": 3}]})

        with self.assertRaises(ValidationError) as caso:
            item.full_clean(exclude=["diseno", "padre", "pregunta", "requisito"])

        self.assertIn("mayor_que", str(caso.exception))

    def test_un_modo_inventado_no_se_guarda(self):
        item = self._item({"modo": "cualquiera", "reglas": []})

        with self.assertRaises(ValidationError):
            item.full_clean(exclude=["diseno", "padre", "pregunta", "requisito"])

    def test_un_operador_que_necesita_valor_sin_valor_no_se_guarda(self):
        item = self._item({"modo": "todas", "reglas": [{"fuente": "pg-1", "op": "es"}]})

        with self.assertRaises(ValidationError) as caso:
            item.full_clean(exclude=["diseno", "padre", "pregunta", "requisito"])

        self.assertIn("necesita un valor", str(caso.exception))

    def test_un_operador_de_lista_con_un_escalar_no_se_guarda(self):
        item = self._item({"modo": "todas", "reglas": [{"fuente": "pg-1", "op": "es_alguno", "valor": "Sí"}]})

        with self.assertRaises(ValidationError) as caso:
            item.full_clean(exclude=["diseno", "padre", "pregunta", "requisito"])

        self.assertIn("lista de valores", str(caso.exception))

    def test_una_regla_sin_fuente_no_se_guarda(self):
        item = self._item({"modo": "todas", "reglas": [{"op": "completo"}]})

        with self.assertRaises(ValidationError):
            item.full_clean(exclude=["diseno", "padre", "pregunta", "requisito"])

    def test_un_operador_sin_valor_no_necesita_valor(self):
        """`vacio`, `completo`, `adjuntado` y `no_adjuntado` se guardan solos:
        el validador no puede pedirles lo que no llevan."""
        item = self._item({"modo": "alguna", "reglas": [{"fuente": "pg-1", "op": "completo"}]})

        item.full_clean(exclude=["diseno", "padre", "pregunta", "requisito"])

    def test_sin_condicion_no_hay_nada_que_validar(self):
        for vacio in (None, {}, ""):
            with self.subTest(valor=vacio):
                validar_condicion_json(vacio)

    def test_el_grupo_del_catalogo_valida_la_misma_forma(self):
        grupo = GrupoRequisito(
            clave="g-condicionado",
            nombre="Grupo",
            condicion_defecto={"modo": "todas", "reglas": [{"fuente": "pg-1", "op": "no_existe"}]},
        )

        with self.assertRaises(ValidationError):
            grupo.full_clean(exclude=["clave"])
