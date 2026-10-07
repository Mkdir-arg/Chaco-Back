"""G2-01 · Los campos propios del constructor en el Excel por persona y en el dashboard.

Un campo propio (`cp-…`) vive en el diseño de **una** convocatoria y su respuesta no
tiene lugar en `Formulario.data`: solo en `respuestas`, con la foto de la definición al
lado. Mientras los dos reportes leyeran `data` —el contrato anterior al Cambio 58—, una
convocatoria que usara el constructor exportaba planillas sin las preguntas que el
ministerio pidió agregar, y su dashboard no tenía ninguna de ellas para graficar.

Acá está también la otra mitad de la ficha: una respuesta que el motor de condiciones
ocultó **no es una respuesta** (RN-6, D11) y no entra ni en la planilla ni en la
distribución.

La reproducción original es `docs/internal/auditoria-2026-10/poc/test_repro_dashboard_campos_propios.py`.
"""

from datetime import timedelta

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from programas.models import CanalFormulario, ItemDiseno, TipoCampo
from programas.services import dashboard_becas as svc
from programas.tests.test_dashboard_becas import HOY, VENTANA, DashboardBecasBase


class CamposPropiosEnReportesTests(DashboardBecasBase):
    def setUp(self):
        super().setUp()
        from programas.services.diseno import obtener_o_crear_diseno

        self.diseno, _ = obtener_o_crear_diseno(self.conv_propia)
        self.grupo = self.diseno.items.filter(tipo=ItemDiseno.Tipo.GRUPO).order_by("orden", "id").first()

    # --- helpers -----------------------------------------------------------
    def _propio(self, clave, texto, opciones, orden=90, condicion=None, tipo=TipoCampo.SELECTOR, padre=None):
        return ItemDiseno.objects.create(
            diseno=self.diseno,
            tipo=ItemDiseno.Tipo.CAMPO,
            clave=clave,
            padre=padre or self.grupo,
            orden=orden,
            condicion=condicion,
            propio={"texto": texto, "tipo": tipo, "opciones": opciones, "obligatorio": False},
        )

    def _caso_con_foto(self, relevamiento, respuestas, **extra):
        """Un caso como lo deja el link público: respuestas por clave más la foto."""
        from programas.services.respuestas import foto_definicion

        return self._formulario(
            relevamiento,
            creado=HOY - timedelta(days=1),
            definicion=foto_definicion(relevamiento),
            respuestas=respuestas,
            data={"globales": {}, "requisitos": {}},
            **extra,
        )

    # --- Excel por persona --------------------------------------------------
    def test_el_campo_propio_es_una_columna_del_excel_con_su_respuesta(self):
        """La PoC invertida: la columna aparece y trae «Sí»."""
        self._propio("cp-hijos", "¿Tenés hijos a cargo?", ["Sí", "No"])
        caso = self._caso_con_foto(self.rel_publico, {"cp-hijos": "Sí"})

        reporte, _ = svc.respuestas_por_persona(self.conv_propia)

        cab = list(reporte.encabezados)
        self.assertIn("¿Tenés hijos a cargo?", cab)
        fila = dict(zip(cab, reporte.filas[0]))
        self.assertEqual(fila["ID caso"], caso.pk)
        self.assertEqual(fila["¿Tenés hijos a cargo?"], "Sí")

    def test_el_excel_no_muestra_lo_que_la_condicion_oculto(self):
        self._propio("cp-madre", "¿Sos madre?", ["Sí", "No"], orden=90)
        self._propio(
            "cp-hijos",
            "¿Cuántos hijos?",
            ["Uno", "Dos"],
            orden=91,
            condicion={"modo": "todas", "reglas": [{"fuente": "cp-madre", "op": "es", "valor": "Sí"}]},
        )
        visible = self._caso_con_foto(self.rel_publico, {"cp-madre": "Sí", "cp-hijos": "Dos"})
        oculto = self._caso_con_foto(self.rel_publico, {"cp-madre": "No", "cp-hijos": "Uno"})

        reporte, _ = svc.respuestas_por_persona(self.conv_propia)

        cab = list(reporte.encabezados)
        filas = {fila[cab.index("ID caso")]: dict(zip(cab, fila)) for fila in reporte.filas}
        self.assertEqual(filas[visible.pk]["¿Cuántos hijos?"], "Dos")
        self.assertEqual(filas[oculto.pk]["¿Cuántos hijos?"], "")

    def test_las_fechas_salen_legibles_y_la_multiple_se_une_con_barras(self):
        self._propio("cp-mudanza", "Fecha de mudanza", [], orden=92, tipo=TipoCampo.DATE)
        self._propio("cp-ayudas", "Ayudas que recibís", ["AUH", "Tarjeta"], orden=93, tipo=TipoCampo.SELECTOR_MULTIPLE)
        self._caso_con_foto(self.rel_publico, {"cp-mudanza": "2024-03-07", "cp-ayudas": ["AUH", "Tarjeta"]})

        reporte, _ = svc.respuestas_por_persona(self.conv_propia)

        fila = dict(zip(list(reporte.encabezados), reporte.filas[0]))
        self.assertEqual(fila["Fecha de mudanza"], "07/03/2024")
        self.assertEqual(fila["Ayudas que recibís"], "AUH | Tarjeta")

    def test_un_caso_sin_foto_sigue_exportando_desde_data(self):
        """Los casos anteriores al Cambio 58 no tienen `respuestas` ni foto: sus
        columnas se siguen leyendo del contrato anterior."""
        self._propio("cp-hijos", "¿Tenés hijos a cargo?", ["Sí", "No"])
        viejo = self._formulario(
            self.rel_propio,
            creado=HOY - timedelta(days=2),
            data={"globales": {str(self.q_laboral.pk): "Trabaja"}, "requisitos": {str(self.r_cursa.pk): "Sí"}},
        )
        nuevo = self._caso_con_foto(self.rel_publico, {"cp-hijos": "No"})

        reporte, _ = svc.respuestas_por_persona(self.conv_propia)

        cab = list(reporte.encabezados)
        filas = {fila[cab.index("ID caso")]: dict(zip(cab, fila)) for fila in reporte.filas}
        self.assertEqual(filas[viejo.pk]["Situación laboral"], "Trabaja")
        self.assertEqual(filas[viejo.pk]["¿Cursás actualmente?"], "Sí")
        self.assertEqual(filas[viejo.pk]["¿Tenés hijos a cargo?"], "")
        self.assertEqual(filas[nuevo.pk]["¿Tenés hijos a cargo?"], "No")

    def test_la_segunda_pasada_va_por_lotes_y_no_crece_con_cada_caso(self):
        """Un lote de pks cada `LOTE_RESPUESTAS` casos, no una consulta por caso."""
        self._propio("cp-hijos", "¿Tenés hijos a cargo?", ["Sí", "No"])
        self._caso_con_foto(self.rel_publico, {"cp-hijos": "Sí"})
        svc.respuestas_por_persona(self.conv_propia)
        with CaptureQueriesContext(connection) as pocas:
            svc.respuestas_por_persona(self.conv_propia)
        for _ in range(12):
            self._caso_con_foto(self.rel_publico, {"cp-hijos": "No"})
        with CaptureQueriesContext(connection) as muchas:
            reporte, _ = svc.respuestas_por_persona(self.conv_propia)
        self.assertEqual(len(reporte.filas), 13)
        self.assertEqual(len(muchas), len(pocas))
        self.assertLessEqual(len(muchas), 8)

    # --- Dashboard ----------------------------------------------------------
    def test_el_campo_propio_entra_al_catalogo_graficable(self):
        self._propio("cp-hijos", "¿Tenés hijos a cargo?", ["Sí", "No"])
        self._propio("cp-nota", "Comentario", [], orden=95, tipo=TipoCampo.STRING)

        catalogo = {p.clave: p for p in svc.preguntas_graficables(self.admin, self.programa)}

        self.assertIn("cp-hijos", catalogo)
        self.assertNotIn("cp-nota", catalogo)  # no es de opciones cerradas
        propia = catalogo["cp-hijos"]
        self.assertEqual(propia.texto, "¿Tenés hijos a cargo?")
        self.assertEqual(propia.opciones, ["Sí", "No"])
        self.assertFalse(propia.multiple)
        self.assertIn(self.conv_propia.nombre, propia.origen)

    def test_el_campo_propio_de_una_convocatoria_fuera_del_alcance_no_entra(self):
        from programas.services.diseno import obtener_o_crear_diseno

        ajeno, _ = obtener_o_crear_diseno(self.conv_ajena)
        ItemDiseno.objects.create(
            diseno=ajeno,
            tipo=ItemDiseno.Tipo.CAMPO,
            clave="cp-ajena01",
            padre=ajeno.items.filter(tipo=ItemDiseno.Tipo.GRUPO).order_by("orden", "id").first(),
            orden=90,
            propio={"texto": "Del interior", "tipo": TipoCampo.SELECTOR, "opciones": ["A"], "obligatorio": False},
        )
        self._propio("cp-hijos", "¿Tenés hijos a cargo?", ["Sí", "No"])

        claves = {p.clave for p in svc.preguntas_graficables(self.regional, self.programa)}

        self.assertIn("cp-hijos", claves)
        self.assertNotIn("cp-ajena01", claves)

    def test_la_distribucion_de_un_campo_propio_sale_de_respuestas(self):
        self._propio("cp-hijos", "¿Tenés hijos a cargo?", ["Sí", "No"])
        for valor in ("Sí", "Sí", "No"):
            self._caso_con_foto(self.rel_publico, {"cp-hijos": valor})
        self._caso_con_foto(self.rel_publico, {})  # no la contestó: no entra en la base

        distribucion = svc.distribucion_respuestas(self.admin, self.programa, VENTANA, "cp-hijos")

        self.assertEqual(distribucion.base, 3)
        self.assertEqual({o["opcion"]: o["total"] for o in distribucion.opciones}, {"Sí": 2, "No": 1})

    def test_una_respuesta_que_la_condicion_oculto_no_cuenta_en_la_distribucion(self):
        self._propio("cp-madre", "¿Sos madre?", ["Sí", "No"], orden=90)
        self._propio(
            "cp-hijos",
            "¿Cuántos hijos?",
            ["Uno", "Dos"],
            orden=91,
            condicion={"modo": "todas", "reglas": [{"fuente": "cp-madre", "op": "es", "valor": "Sí"}]},
        )
        self._caso_con_foto(self.rel_publico, {"cp-madre": "Sí", "cp-hijos": "Dos"})
        self._caso_con_foto(self.rel_publico, {"cp-madre": "No", "cp-hijos": "Uno"})

        distribucion = svc.distribucion_respuestas(self.admin, self.programa, VENTANA, "cp-hijos")

        self.assertEqual(distribucion.base, 1)
        self.assertEqual({o["opcion"]: o["total"] for o in distribucion.opciones}, {"Dos": 1, "Uno": 0})

    def test_un_grupo_oculto_esconde_a_sus_hijos_en_la_distribucion(self):
        self._propio("cp-trabaja", "¿Trabajás?", ["Sí", "No"], orden=90)
        aparte = ItemDiseno.objects.create(
            diseno=self.diseno,
            tipo=ItemDiseno.Tipo.GRUPO,
            clave="g-laboral",
            orden=95,
            etiqueta="Situación laboral",
            canal=CanalFormulario.AMBOS,
            condicion={"modo": "todas", "reglas": [{"fuente": "cp-trabaja", "op": "es", "valor": "Sí"}]},
        )
        self._propio("cp-rubro", "Rubro", ["Comercio", "Campo"], orden=96, padre=aparte)
        self._caso_con_foto(self.rel_publico, {"cp-trabaja": "Sí", "cp-rubro": "Comercio"})
        self._caso_con_foto(self.rel_publico, {"cp-trabaja": "No", "cp-rubro": "Campo"})

        distribucion = svc.distribucion_respuestas(self.admin, self.programa, VENTANA, "cp-rubro")

        self.assertEqual(distribucion.base, 1)
        self.assertEqual({o["opcion"]: o["total"] for o in distribucion.opciones}, {"Comercio": 1, "Campo": 0})

    def test_una_consulta_por_pregunta_aunque_tenga_condicion(self):
        """La condición se agrupa en SQL junto con la pregunta: sigue habiendo una
        consulta por pregunta y no una por caso."""
        self._propio("cp-madre", "¿Sos madre?", ["Sí", "No"], orden=90)
        self._propio(
            "cp-hijos",
            "¿Cuántos hijos?",
            ["Uno", "Dos"],
            orden=91,
            condicion={"modo": "todas", "reglas": [{"fuente": "cp-madre", "op": "es", "valor": "Sí"}]},
        )
        for _ in range(6):
            self._caso_con_foto(self.rel_publico, {"cp-madre": "Sí", "cp-hijos": "Dos"})
        alcance = svc.resolver_alcance(self.admin, self.programa, VENTANA)
        catalogo = svc.preguntas_graficables(self.admin, self.programa)
        with self.assertNumQueries(len(catalogo)):
            svc.distribuciones_respuestas(self.admin, self.programa, VENTANA, alcance=alcance, catalogo=catalogo)

    def test_el_endpoint_del_dashboard_grafica_un_campo_propio(self):
        self._propio("cp-hijos", "¿Tenés hijos a cargo?", ["Sí", "No"])
        self._caso_con_foto(self.rel_publico, {"cp-hijos": "Sí"})
        self.client.force_login(self.admin)

        url = reverse("becas:programa_dashboard_datos", args=[self.programa.pk])
        datos = self.client.get(url, {"pregunta": "cp-hijos", "periodo": "todo"}).json()

        self.assertEqual(datos["filtros_aplicados"]["pregunta"], "cp-hijos")
        self.assertEqual(datos["respuestas"]["texto"], "¿Tenés hijos a cargo?")
        self.assertEqual(datos["respuestas"]["base"], 1)

    def test_sin_capacidad_de_reportes_el_campo_propio_tampoco_se_ve(self):
        self._propio("cp-hijos", "¿Tenés hijos a cargo?", ["Sí", "No"])
        self._caso_con_foto(self.rel_publico, {"cp-hijos": "Sí"})
        url = reverse("becas:programa_dashboard_datos", args=[self.programa.pk])

        self.assertEqual(self.client.get(url).status_code, 302)  # anónimo: al login
        self.client.force_login(self._usuario_sin_reportes())
        self.assertEqual(self.client.get(url, {"pregunta": "cp-hijos"}).status_code, 403)


class LecturaUnicaDeLaRespuestaTests(TestCase):
    """`respuesta_de` y `_expresion_respuesta` leen la misma clave del mismo documento."""

    def test_una_clave_del_catalogo_se_lee_de_data_y_una_propia_de_respuestas(self):
        data = {"globales": {"7": "Trabaja"}, "requisitos": {"3": 12}}
        self.assertEqual(svc.respuesta_de(data, "global:7"), ["Trabaja"])
        self.assertEqual(svc.respuesta_de(data, "requisito:3"), ["12"])
        self.assertEqual(svc.respuesta_de({"cp-hijos": "Sí"}, "cp-hijos"), ["Sí"])
        self.assertEqual(svc.respuesta_de({"cp-hijos": ["A", "B"]}, "cp-hijos"), ["A", "B"])
        self.assertEqual(svc.respuesta_de({}, "cp-hijos"), [])

    def test_la_ruta_json_de_una_clave_propia_apunta_a_respuestas(self):
        """La ruta va entre comillas y como parámetro: `KeyTransform` trataría una
        clave numérica como índice y en MariaDB devolvería NULL (§0.2)."""
        for clave, columna, ruta in (
            ("cp-ab12cd34", "respuestas", '$."cp-ab12cd34"'),
            ("pg-9", "respuestas", '$."pg-9"'),
            ("global:9", "data", '$."globales"."9"'),
            ("requisito:9", "data", '$."requisitos"."9"'),
        ):
            with self.subTest(clave=clave):
                expresion = svc._expresion_respuesta(clave)
                self.assertEqual(expresion.source_expressions[0].name, columna)
                self.assertEqual(expresion.source_expressions[1].value, ruta)
