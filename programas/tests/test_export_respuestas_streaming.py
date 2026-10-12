"""El export «respuestas por persona» se arma por lotes y se transmite (PERF-03, punto 3).

El punto 3 de la ficha pedía sacar el armado del archivo fuera del request con una cola
y un worker. No hay cola en el repo ni en ECOM, así que entra la alternativa sin
infraestructura nueva: **las filas se arman de a lotes mientras se escribe el archivo** y
el CSV se transmite con ``StreamingHttpResponse``. Lo que esto tiene que garantizar —y es
lo que miden estos tests— es:

1. **Lo que se descarga no cambia.** Contra una copia congelada del algoritmo anterior,
   celda por celda, sobre un dataset con adjuntos, condiciones, campos propios, preguntas
   que ya no están en el formulario y fórmulas de Excel; y el cuerpo del CSV transmitido,
   **byte por byte** contra el que armaba ``respuesta_reporte``.
2. **Ninguna consulta mira la convocatoria entera.** El ``read_timeout`` de ECOM es de
   10 s **por consulta**: la pasada principal traía las 20.000 filas anchas (con el JSON
   de ``data``) de un saque. Ahora cada consulta está acotada a un lote de ids.
3. **Las filas no están todas en memoria ni se arman antes de empezar a mandar.**
4. **El alcance por rol vale igual**, con la respuesta transmitida (SEC-22, RN-P13).
"""

import codecs
import csv
import re
from datetime import timedelta
from io import BytesIO, StringIO
from unittest import mock

from asgiref.sync import async_to_sync
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.test import AsyncRequestFactory, RequestFactory
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from openpyxl import load_workbook

from core import rbac
from programas.models import (
    AdjuntoFormulario,
    AsignacionCoordinador,
    Formulario,
    ItemDiseno,
    PreguntaGlobal,
    RequisitoNativo,
    TipoCampo,
)
from programas.services import dashboard_becas as svc
from programas.services.autorizacion import programa_becas
from programas.services.becas import get_campos_formulario
from programas.services.exportacion_reportes import respuesta_csv_en_streaming, respuesta_reporte
from programas.services.reportes import Reporte, ReportePerezoso
from programas.tests.test_dashboard_becas import HOY, DashboardBecasBase
from programas.views import dashboard_becas as vistas
from users.models import Capacidad, RolMeta

# ──────────────────────────────────────────────────────────────────────────────
# Copia congelada del algoritmo anterior (development @ 2d632cd9), para comparar
# ──────────────────────────────────────────────────────────────────────────────


def _respuestas_de_los_casos_referencia(pks, campos, planos):
    """La segunda pasada de entonces: ``(pk, respuestas)`` por lotes, en su propia
    consulta sobre las filas que la pasada principal ya había leído."""
    celdas, ocultas_por_caso = {}, {}
    for inicio in range(0, len(pks), svc.LOTE_RESPUESTAS):
        lote = pks[inicio : inicio + svc.LOTE_RESPUESTAS]
        for pk, respuestas in Formulario.objects.filter(pk__in=lote).order_by().values_list("pk", "respuestas"):
            respuestas = svc._como_dict(respuestas)
            if not respuestas:
                continue
            _, ocultos, _ = svc.condiciones.aplicar(planos, respuestas)
            ocultas_por_caso[pk] = ocultos
            valores = {}
            for clave, valor in respuestas.items():
                if clave in ocultos:
                    continue
                texto = svc._texto_legible(campos.get(clave) or {}, valor)
                if texto:
                    valores[clave] = texto
            celdas[pk] = valores
    return celdas, ocultas_por_caso


def respuestas_por_persona_referencia(convocatoria, *, incluir_publicos):
    """El export tal como lo armaba el Cambio 189: una sola pasada, todo en memoria.

    No se toca. Es el testigo contra el que se compara la versión por lotes: si lo que
    el usuario descarga cambia aunque sea en una celda, el test de equivalencia falla.
    Reusa los auxiliares del servicio que **no** cambiaron (``_relevamientos_de``,
    ``_identificacion``, ``_apoderado``…) y trae copiada la segunda pasada de entonces,
    la que volvía a leer las mismas filas para traerse ``respuestas``.
    """
    campos_vigentes, planos_vigentes = svc.formulario_vigente(convocatoria)
    globales, requisitos = get_campos_formulario(convocatoria)
    definicion = [(f"pg-{p.pk}", p, "Pregunta general") for p in globales] + [
        (f"rn-{r.pk}", r, "Requisito") for r in requisitos
    ]
    en_definicion = {clave for clave, _, _ in definicion}

    adjuntos = {}
    for form_id, pg_id, rn_id, archivo in (
        AdjuntoFormulario.objects.filter(formulario__relevamiento__convocatoria=convocatoria)
        .order_by()
        .values_list("formulario_id", "pregunta_global_id", "requisito_nativo_id", "archivo")
    ):
        clave = f"pg-{pg_id}" if pg_id else f"rn-{rn_id}"
        adjuntos.setdefault(form_id, {}).setdefault(clave, []).append(svc._nombre_archivo(archivo))

    relevamientos = svc._relevamientos_de(convocatoria, incluir_publicos=incluir_publicos)
    etiquetas_estado = {valor: str(etiqueta) for valor, etiqueta in Formulario.Estado.choices}
    formularios = (
        Formulario.objects.filter(relevamiento_id__in=list(relevamientos))
        .order_by("relevamiento_id", "numero")
        .values(*svc._COLUMNAS_CASO)
    )
    casos, extra_claves = [], set()
    for f in formularios.iterator(chunk_size=2000):
        rel_id, rel_nombre, canal, territorial = relevamientos[f["relevamiento_id"]]
        dni, nombre = svc._identificacion(f)
        creado = f["creado"]
        base = [
            rel_id,
            rel_nombre,
            canal,
            territorial,
            f["pk"],
            f["numero"],
            etiquetas_estado.get(f["estado"], f["estado"]),
            svc.timezone.localtime(creado).strftime("%d/%m/%Y %H:%M") if creado else "",
            f["ciudadano_id"] or "",
            dni,
            nombre,
            "Sí" if (f["validado_renaper"] or f["identidad_forzada"]) else "No",
            f["celular"] or "",
            f["email_contacto"] or "",
            svc._apoderado(f),
            f"{f['gps_lat']}, {f['gps_lng']}" if f["gps_lat"] is not None and f["gps_lng"] is not None else "",
        ]
        data = svc._como_dict(f["data"])
        contestadas = {}
        for bolsa, prefijo in (("globales", "pg"), ("requisitos", "rn")):
            for pk, valor in svc._como_dict(data.get(bolsa)).items():
                valores = svc._valores_de(valor)
                if valores:
                    contestadas[f"{prefijo}-{pk}"] = " | ".join(valores)
        casos.append((f["pk"], base, contestadas))

    celdas, ocultas = _respuestas_de_los_casos_referencia([pk for pk, _, _ in casos], campos_vigentes, planos_vigentes)
    for pk, _base, contestadas in casos:
        for clave in ocultas.get(pk, ()):
            contestadas.pop(clave, None)
        contestadas.update(celdas.get(pk, {}))
        extra_claves.update(
            clave for clave in contestadas if clave not in en_definicion and clave not in campos_vigentes
        )

    extras = []
    if extra_claves:

        def pks_de(prefijo):
            return [int(c[3:]) for c in extra_claves if c.startswith(f"{prefijo}-") and c[3:].isdigit()]

        textos = {f"pg-{p.pk}": p.texto for p in PreguntaGlobal.objects.filter(pk__in=pks_de("pg"))}
        textos.update({f"rn-{r.pk}": r.texto for r in RequisitoNativo.objects.filter(pk__in=pks_de("rn"))})
        for clave in sorted(extra_claves):
            extras.append((clave, f"{textos.get(clave, 'Pregunta ' + clave)} (ya no está en el formulario)"))

    del_catalogo = {clave: svc._texto_columna(campo, prefijo) for clave, campo, prefijo in definicion}
    columnas = [
        (clave, del_catalogo.get(clave) or campo.get("texto", "") or clave)
        for clave, campo in campos_vigentes.items()
        if (campo.get("origen") or svc.OrigenRequisito.PREGUNTA) == svc.OrigenRequisito.PREGUNTA
    ]
    columnas += [(clave, texto) for clave, texto in del_catalogo.items() if clave not in campos_vigentes]
    columnas += extras
    repetidos = svc.Counter(texto for _, texto in columnas)
    encabezados_preguntas = [f"{texto} [{clave}]" if repetidos[texto] > 1 else texto for clave, texto in columnas]

    claves = [clave for clave, _ in columnas]
    posicion = {clave: i for i, clave in enumerate(claves)}
    filas = []
    for form_id, base, contestadas in casos:
        celdas_fila = [contestadas.get(clave, "") for clave in claves]
        for clave, nombres in adjuntos.get(form_id, {}).items():
            if clave in posicion:
                celdas_fila[posicion[clave]] = " | ".join(nombres)
        filas.append(tuple(base + celdas_fila))

    encabezados = svc.COLUMNAS_FIJAS + tuple(encabezados_preguntas)
    alcance = (
        f"Convocatoria {convocatoria.nombre} · {convocatoria.segmento.nombre} · {len(filas)} casos, "
        f"todos los estados, sin filtro de período · generado el {svc.timezone.localtime():%d/%m/%Y %H:%M}"
    )
    return Reporte(encabezados, tuple(filas)), alcance


def cuerpo(respuesta):
    """El cuerpo, venga de un ``HttpResponse`` o de un ``StreamingHttpResponse``."""
    return respuesta.getvalue() if respuesta.streaming else respuesta.content


class ExportRespuestasBase(DashboardBecasBase):
    """Una convocatoria con todo lo que el export tiene que saber resolver."""

    def setUp(self):
        super().setUp()
        from programas.services.diseno import obtener_o_crear_diseno

        self.diseno, _ = obtener_o_crear_diseno(self.conv_propia)
        self.grupo = self.diseno.items.filter(tipo=ItemDiseno.Tipo.GRUPO).order_by("orden", "id").first()
        self.q_archivo = PreguntaGlobal.objects.create(
            texto="Constancia de alumno regular", tipo=TipoCampo.ARCHIVO, orden=4
        )
        self.q_retirada = PreguntaGlobal.objects.create(
            texto="Pregunta que se dio de baja", tipo=TipoCampo.SELECTOR, opciones=["A", "B"], orden=5, activo=False
        )
        self._propio("cp-madre", "¿Sos madre?", ["Sí", "No"], orden=90)
        self._propio(
            "cp-hijos",
            "¿Cuántos hijos?",
            ["Uno", "Dos"],
            orden=91,
            condicion={"modo": "todas", "reglas": [{"fuente": "cp-madre", "op": "es", "valor": "Sí"}]},
        )

    def _propio(self, clave, texto, opciones, orden=90, condicion=None, tipo=TipoCampo.SELECTOR):
        return ItemDiseno.objects.create(
            diseno=self.diseno,
            tipo=ItemDiseno.Tipo.CAMPO,
            clave=clave,
            padre=self.grupo,
            orden=orden,
            condicion=condicion,
            propio={"texto": texto, "tipo": tipo, "opciones": opciones, "obligatorio": False},
        )

    def _poblar(self):
        """Siete casos: del territorial y del link público, con y sin legajo, con
        adjunto, con una condición que oculta, con una pregunta dada de baja y con una
        clave que ya no existe en ningún lado."""
        ciudadana = self._ciudadano("30111222")
        completo = self._formulario(
            self.rel_propio,
            Formulario.Estado.APROBADO,
            creado=HOY - timedelta(days=5),
            ciudadano=ciudadana,
            validado_renaper=True,
            gps_lat="-27.45",
            gps_lng="-58.98",
            data={
                "globales": {
                    str(self.q_laboral.pk): "Trabaja",
                    str(self.q_transporte.pk): ["Colectivo", "Moto"],
                },
                "requisitos": {str(self.r_cursa.pk): "Sí"},
            },
            respuestas={"cp-madre": "Sí", "cp-hijos": "Dos"},
        )
        AdjuntoFormulario.objects.create(
            formulario=completo, pregunta_global=self.q_archivo, archivo="adjuntos/constancia.pdf"
        )
        self._formulario(
            self.rel_propio,
            creado=HOY - timedelta(days=4),
            data={"globales": {}, "requisitos": {}},
            respuestas={"cp-madre": "No", "cp-hijos": "Uno"},  # lo oculta la condición
        )
        self._formulario(
            self.rel_propio,
            creado=HOY - timedelta(days=3),
            # Una pregunta que ya no está en el formulario: su columna se conserva.
            data={"globales": {str(self.q_retirada.pk): "A"}, "requisitos": {}},
        )
        self._formulario(
            self.rel_publico,
            creado=HOY - timedelta(days=2),
            data={"globales": {}, "requisitos": {}},
            respuestas={"cp-que-ya-no-existe": "quedó respondida"},
        )
        self._formulario(
            self.rel_publico,
            creado=HOY - timedelta(days=2),
            data={"globales": {str(self.q_laboral.pk): "=1+1"}, "requisitos": {}},
            apoderado_dni="20111222",
            apoderado_nombre="Luis",
            apoderado_apellido="Sosa",
        )
        self._formulario(self.rel_publico, creado=HOY - timedelta(days=1), data={}, respuestas={})
        self._formulario(self.rel_publico, creado=HOY - timedelta(days=1))

    def _url(self, convocatoria, formato="csv"):
        return reverse("becas:programa_dashboard_respuestas", args=[self.programa.pk, convocatoria.pk, formato])


class EquivalenciaConElExportAnteriorTests(ExportRespuestasBase):
    """Lo que se descarga no cambia: contra la copia congelada y contra el escritor viejo."""

    def test_las_filas_son_las_mismas_que_las_del_algoritmo_anterior(self):
        self._poblar()

        esperado, alcance_esperado = respuestas_por_persona_referencia(self.conv_propia, incluir_publicos=True)
        reporte, alcance = svc.respuestas_por_persona_en_lotes(self.conv_propia, incluir_publicos=True)
        filas = list(reporte.filas)

        self.assertEqual(reporte.encabezados, esperado.encabezados)
        self.assertEqual(len(filas), len(esperado.filas))
        self.assertEqual(len(filas), 7)
        for numero, (nueva, vieja) in enumerate(zip(filas, esperado.filas)):
            with self.subTest(fila=numero):
                self.assertEqual(nueva, vieja)
        self.assertEqual(alcance, alcance_esperado)
        # Y lo que se comparó no es un reporte pelado: están las cuatro piezas difíciles.
        cabeceras = list(reporte.encabezados)
        self.assertIn("¿Cuántos hijos?", cabeceras)
        self.assertIn("Pregunta que se dio de baja (ya no está en el formulario)", cabeceras)
        self.assertIn("Pregunta cp-que-ya-no-existe (ya no está en el formulario)", cabeceras)
        celdas = [celda for fila in filas for celda in fila]
        self.assertIn("constancia.pdf", celdas)
        self.assertIn("Colectivo | Moto", celdas)
        # El saneo de SEC-20 es del escritor, no del servicio: acá la celda viaja cruda.
        self.assertIn("=1+1", celdas)
        # La condición sigue tapando la respuesta del segundo caso.
        columna = cabeceras.index("¿Cuántos hijos?")
        self.assertEqual([fila[columna] for fila in filas], ["Dos", "", "", "", "", "", ""])

    def test_el_csv_transmitido_es_byte_por_byte_el_que_armaba_respuesta_reporte(self):
        self._poblar()
        reporte, alcance = svc.respuestas_por_persona_en_lotes(self.conv_propia, incluir_publicos=True)
        materializado = reporte.materializado()

        viejo = respuesta_reporte(materializado, "csv", "becas_respuestas", alcance=alcance)
        nuevo = respuesta_csv_en_streaming(
            RequestFactory().get("/x/"),
            ReportePerezoso(materializado.encabezados, iter(materializado.filas)),
            "becas_respuestas",
            alcance=alcance,
        )

        self.assertEqual(cuerpo(nuevo), cuerpo(viejo))
        self.assertEqual(nuevo["Content-Type"], viejo["Content-Type"])
        self.assertEqual(nuevo["Content-Disposition"], viejo["Content-Disposition"])

    def test_la_descarga_del_csv_trae_las_mismas_filas_que_el_xlsx(self):
        """El puente con el Cambio 189: los dos formatos siguen saliendo del mismo
        reporte, ahora que uno se transmite y el otro no."""
        self._poblar()
        self.client.force_login(self.admin)

        del_csv = list(csv.reader(StringIO(cuerpo(self.client.get(self._url(self.conv_propia))).decode("utf-8-sig"))))
        xlsx = self.client.get(self._url(self.conv_propia, "xlsx"))

        libro = load_workbook(BytesIO(cuerpo(xlsx)), read_only=True)
        del_xlsx = [
            ["" if celda is None else str(celda) for celda in fila]
            for fila in libro["Respuestas"].iter_rows(values_only=True)
        ]
        self.assertEqual(len(del_csv), len(del_xlsx))
        for numero, (una, otra) in enumerate(zip(del_csv, del_xlsx)):
            with self.subTest(fila=numero):
                self.assertEqual(una, otra)
        self.assertEqual(len(del_csv) - 3, 7)
        # SEC-20 no se negocia porque la respuesta se transmita: la fórmula va escapada
        # en los dos archivos.
        self.assertIn("'=1+1", [celda for fila in del_csv for celda in fila])
        self.assertIn("'=1+1", [celda for fila in del_xlsx for celda in fila])


class ArmadoPorLotesTests(ExportRespuestasBase):
    """Ninguna consulta mira la convocatoria entera, y las filas no se arman de golpe."""

    IDS = re.compile(r'"id" IN \(([^)]*)\)')

    def _casos_mirados(self, sql):
        """Cuántos ids de caso mira una consulta sobre ``programas_formulario``."""
        if "programas_formulario" not in sql:
            return 0
        encontrados = self.IDS.search(sql)
        return len(encontrados.group(1).split(",")) if encontrados else None

    def test_ninguna_consulta_ancha_mira_mas_de_un_lote_de_casos(self):
        """El riesgo real contra el ``read_timeout`` de 10 s: la pasada principal traía
        las filas anchas —con el JSON de ``data``— de **todos** los casos en una sola
        consulta. Con 40.000 casos eso es un solo SELECT de cientos de MB."""
        self._poblar()

        with mock.patch.object(svc, "LOTE_RESPUESTAS", 2), CaptureQueriesContext(connection) as capturadas:
            reporte, _alcance = svc.respuestas_por_persona_en_lotes(self.conv_propia, incluir_publicos=True)
            self.assertEqual(len(list(reporte.filas)), 7)

        anchas = [q["sql"] for q in capturadas if '"programas_formulario"."data"' in q["sql"]]
        self.assertTrue(anchas, "ninguna consulta trae el JSON del caso: el test ya no mide lo que decía medir")
        for sql in anchas:
            with self.subTest(sql=sql[:120]):
                self.assertLessEqual(
                    self._casos_mirados(sql),
                    2,
                    "una consulta del export mira más casos que un lote: con 40.000 casos "
                    "ese SELECT se pasa de los 10 s de `read_timeout` de ECOM",
                )
        # Dos pasadas (columnas y filas) sobre cuatro lotes de 2 casos: 7 casos.
        self.assertEqual([self._casos_mirados(sql) for sql in anchas], [2, 2, 2, 1] * 2)

    def test_las_filas_se_leen_recien_cuando_se_las_recorre(self):
        self._poblar()

        with CaptureQueriesContext(connection) as al_resolver_columnas:
            reporte, _alcance = svc.respuestas_por_persona_en_lotes(self.conv_propia, incluir_publicos=True)
        with CaptureQueriesContext(connection) as al_recorrer:
            filas = list(reporte.filas)

        self.assertEqual(len(filas), 7)
        self.assertTrue(al_resolver_columnas.captured_queries)
        # Dos consultas por lote: el caso con sus respuestas, y sus adjuntos.
        self.assertEqual(
            len(al_recorrer.captured_queries),
            2,
            "si no hay consultas acá, las filas ya estaban armadas: el reporte no es "
            "perezoso y la convocatoria entera vuelve a estar en memoria antes de "
            "escribir la primera celda",
        )

    def test_el_primer_trozo_del_csv_sale_sin_haber_leido_todos_los_casos(self):
        self._poblar()
        self.client.force_login(self.admin)

        with (
            mock.patch.object(svc, "LOTE_RESPUESTAS", 2),
            mock.patch("programas.services.exportacion_reportes.TROZO_CSV", 1),
        ):
            respuesta = self.client.get(self._url(self.conv_propia))
            self.assertTrue(respuesta.streaming, "el CSV grande se arma entero antes de mandar un byte")
            trozos = iter(respuesta.streaming_content)
            with CaptureQueriesContext(connection) as hasta_el_primer_trozo:
                primero = next(trozos)
            resto = b"".join(trozos)

        self.assertTrue(primero.startswith(codecs.BOM_UTF8))
        self.assertIn(b"Alcance: Convocatoria ", primero)
        lotes = len([q for q in hasta_el_primer_trozo.captured_queries if '"programas_formulario"."data"' in q["sql"]])
        self.assertEqual(lotes, 1, "para mandar la primera fila se leyeron todos los lotes de casos")
        self.assertEqual(len((primero + resto).decode("utf-8-sig").strip().splitlines()), 3 + 7)

    def test_el_cuerpo_sale_en_varios_trozos_y_no_en_uno_solo(self):
        self._poblar()
        self.client.force_login(self.admin)

        with mock.patch("programas.services.exportacion_reportes.TROZO_CSV", 1):
            trozos = list(self.client.get(self._url(self.conv_propia)).streaming_content)

        self.assertGreater(len(trozos), 1)

    def test_el_xlsx_consume_las_filas_del_mismo_iterador_por_lotes(self):
        """El punto 3 vale para los dos formatos: el libro se escribe en
        ``write_only`` con las filas que van llegando, no con las 40.000 en memoria."""
        self._poblar()
        self.client.force_login(self.admin)

        with mock.patch.object(svc, "LOTE_RESPUESTAS", 2), CaptureQueriesContext(connection) as capturadas:
            respuesta = self.client.get(self._url(self.conv_propia, "xlsx"))

        self.assertEqual(respuesta.status_code, 200)
        anchas = [q["sql"] for q in capturadas if '"programas_formulario"."data"' in q["sql"]]
        self.assertEqual([self._casos_mirados(sql) for sql in anchas], [2, 2, 2, 1] * 2)


class LoQueNoEntraEnElArchivoTests(ExportRespuestasBase):
    """Las dos pasadas abren una ventana, y lo que cae ahí no se pierde callado.

    El encabezado se cierra en la primera pasada y las filas se leen en la segunda: una
    respuesta con una clave **sin columna** escrita en el medio no tiene dónde salir. La
    ventana es inherente a armar el archivo en dos pasadas (cerrarla pide bloquear la
    convocatoria o volver a leerla entera); lo que no puede pasar es que se vaya en
    silencio.
    """

    LOGGER = "programas.services.dashboard_becas"
    CLAVE_NUEVA = "cp-llegada-tarde"

    def test_una_respuesta_sin_columna_escrita_entre_las_dos_pasadas_queda_en_el_log(self):
        self._poblar()
        reporte, _alcance = svc.respuestas_por_persona_en_lotes(self.conv_propia, incluir_publicos=True)

        # El encabezado ya está cerrado: alguien contesta mientras el archivo se escribe,
        # y su pregunta no está ni en el formulario vigente ni en el catálogo.
        caso = Formulario.objects.filter(relevamiento=self.rel_propio).order_by("pk").first()
        caso.respuestas = {**svc._como_dict(caso.respuestas), self.CLAVE_NUEVA: "Sí"}
        caso.save(update_fields=["respuestas"])

        with self.assertLogs(self.LOGGER, level="WARNING") as registro:
            filas = list(reporte.filas)

        self.assertEqual(len(filas), 7)
        self.assertNotIn(self.CLAVE_NUEVA, "".join(reporte.encabezados))
        aviso = registro.output[0]
        self.assertIn("1 clave(s)", aviso)
        self.assertIn(f"convocatoria={self.conv_propia.pk}", aviso)
        # El aviso dice cuántas y de qué convocatoria, nunca qué contestó quién.
        self.assertNotIn(self.CLAVE_NUEVA, aviso)
        self.assertNotIn("Sí", aviso)

    def test_un_export_normal_no_avisa_nada(self):
        """Las claves que a propósito no tienen columna —las del legajo y el apoderado—
        no son una pérdida: si contaran, el aviso saldría en cada export y nadie lo leería."""
        self._poblar()

        with self.assertNoLogs(self.LOGGER, level="WARNING"):
            reporte, _alcance = svc.respuestas_por_persona_en_lotes(self.conv_propia, incluir_publicos=True)
            self.assertEqual(len(list(reporte.filas)), 7)


class FalloAMitadDelStreamTests(ExportRespuestasBase):
    """Con la respuesta ya empezada no hay 500 que mandar: el 200 queda, pero cortado.

    El estado es `200` + cuerpo truncado + la excepción viajando al servidor. Es lo
    correcto —un archivo incompleto es mejor que uno silenciosamente corto— y por eso se
    fija acá: envolver `_vigilar` en un `except` que se trague el error convertiría la
    descarga cortada en un CSV que parece entero.
    """

    LOGGER = "programas.views.dashboard_becas"

    def test_el_vigilante_deja_el_fallo_en_el_log_y_lo_vuelve_a_lanzar(self):
        def filas():
            yield ("una fila",)
            raise RuntimeError("se cortó la lectura")

        vigilado = vistas._vigilar(filas(), 77)
        self.assertEqual(next(vigilado), ("una fila",))

        with self.assertLogs(self.LOGGER, level="ERROR") as registro, self.assertRaises(RuntimeError):
            next(vigilado)

        self.assertIn("convocatoria=77", registro.output[0])
        self.assertIn("RuntimeError", registro.output[0], "sin el traceback el log no sirve para nada")

    def test_un_fallo_a_mitad_del_csv_corta_la_descarga_en_vez_de_completarla(self):
        self._poblar()
        self.client.force_login(self.admin)

        def filas_que_se_cortan(*_args, **_kwargs):
            yield ("primera",)
            raise RuntimeError("se cortó la lectura")

        with (
            mock.patch.object(svc, "_filas_por_persona", filas_que_se_cortan),
            mock.patch("programas.services.exportacion_reportes.TROZO_CSV", 1),
        ):
            respuesta = self.client.get(self._url(self.conv_propia))
            # El estado ya se mandó: no hay forma de convertir esto en un 500.
            self.assertEqual(respuesta.status_code, 200)
            self.assertTrue(respuesta.streaming)
            trozos = iter(respuesta.streaming_content)
            primero = next(trozos)

            with self.assertLogs(self.LOGGER, level="ERROR") as registro, self.assertRaises(RuntimeError):
                b"".join(trozos)

        self.assertIn(b"Alcance: Convocatoria ", primero)
        self.assertIn(f"convocatoria={self.conv_propia.pk}", registro.output[0])


class AlcanceDelCsvTransmitidoTests(ExportRespuestasBase):
    """Que la respuesta se transmita no relaja ni el permiso ni el recorte (SEC-22)."""

    def _usuario_con_la_capacidad_justa(self):
        """Ve el programa porque coordina el segmento, y tiene **solo** las dos
        capacidades de reportes: ninguna de alcance sobre el link público (RN-P13)."""
        grupo = Group.objects.create(name="Becas — Solo reportes")
        RolMeta.objects.create(grupo=grupo, programa=programa_becas(), activo=True)
        content_type = ContentType.objects.get_for_model(Capacidad)
        grupo.permissions.add(
            *Permission.objects.filter(
                content_type=content_type,
                codename__in=[
                    rbac.codename_de("becas.segmento.ver"),
                    rbac.codename_de("becas.reportes.ver"),
                    rbac.codename_de("becas.reportes.exportar"),
                ],
            )
        )
        usuario = User.objects.create_user("solo-reportes", password="x")
        usuario.groups.add(grupo)
        AsignacionCoordinador.objects.create(segmento=self.segmento, coordinador=usuario)
        return usuario

    def test_el_anonimo_va_al_login_y_no_baja_nada(self):
        self._poblar()

        respuesta = self.client.get(self._url(self.conv_propia))

        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(respuesta.streaming)

    def test_sin_la_capacidad_de_exportar_es_403_y_no_un_csv_a_medias(self):
        self._poblar()
        self.client.force_login(self._usuario_sin_reportes())

        respuesta = self.client.get(self._url(self.conv_propia))

        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(respuesta.streaming)

    def test_con_la_capacidad_justa_baja_pero_sin_rn_p13_no_trae_los_casos_publicos(self):
        self._poblar()
        self.client.force_login(self._usuario_con_la_capacidad_justa())

        respuesta = self.client.get(self._url(self.conv_propia))

        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.streaming)
        # Tres casos territoriales; los cuatro del link público quedan afuera (SEC-22).
        self.assertEqual(len(cuerpo(respuesta).decode("utf-8-sig").strip().splitlines()), 3 + 3)

    def test_el_superusuario_baja_la_convocatoria_entera(self):
        self._poblar()
        self.client.force_login(User.objects.create_superuser("root-export", "root@example.com", "x"))

        respuesta = self.client.get(self._url(self.conv_propia))

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(cuerpo(respuesta).decode("utf-8-sig").strip().splitlines()), 3 + 7)

    def test_una_convocatoria_de_otro_programa_sigue_siendo_404(self):
        self.client.force_login(self.admin)

        respuesta = self.client.get(self._url(self.conv_otro))

        self.assertEqual(respuesta.status_code, 404)


class CsvBajoAsgiTests(ExportRespuestasBase):
    """Bajo daphne, un iterador sincrónico no se transmite: Django lo junta entero con
    ``sync_to_async(list)`` y recién ahí manda el cuerpo. El CSV se adapta."""

    @staticmethod
    def _juntar(contenido):
        async def recorrer():
            partes = []
            async for parte in contenido:
                partes.append(parte)
            return b"".join(partes)

        return async_to_sync(recorrer)()

    def test_bajo_asgi_el_cuerpo_viaja_como_iterador_asincronico(self):
        reporte = ReportePerezoso(("Columna",), iter([("uno",), ("dos",)]))

        respuesta = respuesta_csv_en_streaming(AsyncRequestFactory().get("/x/"), reporte, "x", alcance="Un alcance")

        self.assertTrue(respuesta.is_async)
        self.assertEqual(
            self._juntar(respuesta.streaming_content).decode("utf-8-sig"),
            "Alcance: Un alcance\r\n\r\nColumna\r\nuno\r\ndos\r\n",
        )

    def test_bajo_wsgi_el_cuerpo_sigue_siendo_sincronico(self):
        reporte = ReportePerezoso(("Columna",), iter([("uno",)]))

        respuesta = respuesta_csv_en_streaming(RequestFactory().get("/x/"), reporte, "x")

        self.assertFalse(respuesta.is_async)

    def test_bajo_asgi_las_filas_tambien_salen_de_a_lotes(self):
        self._poblar()
        reporte, alcance = svc.respuestas_por_persona_en_lotes(self.conv_propia, incluir_publicos=True)

        respuesta = respuesta_csv_en_streaming(AsyncRequestFactory().get("/x/"), reporte, "x", alcance=alcance)
        filas = self._juntar(respuesta.streaming_content).decode("utf-8-sig").strip().splitlines()

        self.assertEqual(len(filas), 3 + 7)
