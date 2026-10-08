"""El circuito SIIS deja de pagar por caso lo que es igual para todos (Ola 4, PR 3).

Cuatro fichas de la auditoría oct-2026 sobre el mismo camino —elegir candidatos, armar
el payload, validarlos y mirarlos desde la pantalla—:

* **PERF-01 (+V4-NEW-02)** — ``armar_payload`` consultaba 6 veces por caso lo mismo:
  los campos con destino SIIS del catálogo, la provincia y la localidad. Medido:
  ``elegir_completos`` sobre 200 casos = 1.200 consultas; proyectado a los 7.496
  candidatos reales, 45-60 mil **antes** del primer latido de la corrida.
* **PERF-19** — «el último envío por caso» viajaba como una subconsulta correlacionada
  escrita **dos veces** en el WHERE, y MariaDB no comparte la caché entre las dos.
* **PERF-07** — la pantalla del masivo contaba candidatos con los 15.531 DNI
  habilitados como literales (188 KB de SQL) y, con una corrida en curso, se relee sola
  cada 5 s en el mismo proceso que la corrida.
* **PERF-06** — ``validar_casos_siis`` traía todos los casos con sus cuatro JSON en una
  sola consulta.

Lo que se fija acá, en el orden de las fichas:

1. Las consultas de la selección **no crecen** con la cantidad de casos.
2. El payload que viaja a SIIS es **idéntico** con y sin el memo.
3. ``hidratar`` no difiere los JSON del payload: ``armar_payload`` los lee (es la
   corrección code-first a la propuesta 5 de la ficha).
4. La subconsulta del último envío aparece **una** vez, y los candidatos son los mismos.
5. Con una corrida en curso la pantalla no cuenta nada, y sin corrida cuenta una vez
   por minuto.
6. ``validar_casos_siis`` hidrata por lotes y sin los JSON.
"""

from datetime import date, timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.core.management import call_command
from django.db import connection
from django.db.models import OuterRef, Q, Subquery
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from legajos.models import Ciudadano
from programas.management.commands.seed_becas import ROL_ADMIN
from programas.models import (
    Convocatoria,
    CorridaSiis,
    EnvioSIIS,
    Formulario,
    ProgramaSiis,
    Relevamiento,
    Segmento,
    ValidacionSIS,
)
from programas.services import proceso_masivo
from programas.services.siis_envio import Catalogos, armar_payload
from programas.tests.test_proceso_masivo import crear_tabla_aprobados_materias
from programas.tests.test_siis_envio import _catalogo_falso, _ConPayloadCompleto

#: Las cuatro columnas JSON del caso, como las nombra el SQL.
JSON_DEL_CASO = ("data", "respuestas", "definicion", "datos_siis")


def _candidatos_a_la_vieja(**filtros):
    """El filtro de «último envío» anterior a PERF-19, como referencia de **resultado**.

    Dos ``Q`` sobre la misma anotación: el conjunto que devolvía es el que
    :func:`proceso_masivo.candidatos` tiene que seguir devolviendo.
    """
    ultimo = EnvioSIIS.objects.filter(formulario=OuterRef("pk")).order_by("-creado", "-id").values("estado")[:1]
    base = proceso_masivo.candidatos(**filtros)
    # Se rearma desde cero el pedazo que cambió, sobre el mismo resto de condiciones.
    return list(
        Formulario.objects.filter(pk__in=base.values_list("pk", flat=True))
        .annotate(ultimo_viejo=Subquery(ultimo))
        .filter(Q(ultimo_viejo__isnull=True) | ~Q(ultimo_viejo=EnvioSIIS.Estado.ENVIADO))
        .order_by("pk")
        .values_list("pk", flat=True)
    )


class _ConVariosCasos(_ConPayloadCompleto):
    """El caso completo de ``test_siis_envio``, clonado ``n`` veces en el mismo segmento.

    Sin foto de la definición a propósito: son los casos que resuelven sus destinos
    contra el catálogo de hoy, que es el camino que consultaba dos tablas por caso.
    """

    def _clonar(self, cuantos):
        """Deja ``cuantos`` casos en total (el original más sus clones) y devuelve sus ids."""
        ids = list(Formulario.objects.order_by("pk").values_list("pk", flat=True))
        for indice in range(len(ids), cuantos):
            ciudadano = Ciudadano.objects.create(
                dni=f"3030{indice:04d}",
                nombre="Clon",
                apellido=f"Perez {indice}",
                fecha_nacimiento=date(1995, 6, 15),
                genero="M",
            )
            clon = Formulario.objects.create(
                relevamiento=self.relevamiento,
                ciudadano=ciudadano,
                celular="3624123456",
                email_contacto=f"clon{indice}@email.com",
                estado=Formulario.Estado.APROBADO,
                validado_renaper=True,
                data=self.formulario.data,
            )
            ids.append(clon.pk)
        return sorted(ids)


class PayloadSinConsultasPorCasoTests(_ConVariosCasos):
    """PERF-01: la selección cuesta lo mismo con 5 casos que con 15."""

    def _consultas_de_elegir(self, cuantos):
        ids = self._clonar(cuantos)
        catalogos = Catalogos(cargar=_catalogo_falso)
        with CaptureQueriesContext(connection) as capturadas:
            elegidos, _ = proceso_masivo.elegir_completos(
                proceso_masivo.hidratar(ids), catalogos, 999, proceso_masivo.Cuenta()
            )
        self.assertEqual(len(elegidos), cuantos, "el dataset tiene que salir completo o el test no mide nada")
        return len(capturadas.captured_queries)

    def test_las_consultas_no_crecen_con_la_cantidad_de_casos(self):
        """Antes eran 6 por caso: 2 de destinos, 2 de ``ProvinciaSiis``, 2 de
        ``LocalidadSiis``. Con 7.496 candidatos, 45 mil consultas."""
        con_cinco = self._consultas_de_elegir(5)
        con_quince = self._consultas_de_elegir(15)

        self.assertEqual(
            con_cinco,
            con_quince,
            f"la selección volvió a consultar por caso: {con_cinco} con 5 casos y {con_quince} con 15",
        )

    def test_el_memo_no_cambia_el_payload(self):
        """Lo que viaja a SIIS es lo mismo: el alta no tiene baja."""
        ids = self._clonar(4)
        casos = proceso_masivo.hidratar(ids)

        compartido = Catalogos(cargar=_catalogo_falso)
        con_memo = [armar_payload(caso, catalogos=compartido, hoy=date(2026, 9, 14)) for caso in casos]
        sin_memo = [
            armar_payload(caso, catalogos=Catalogos(cargar=_catalogo_falso), hoy=date(2026, 9, 14)) for caso in casos
        ]

        self.assertEqual(con_memo, sin_memo)
        self.assertTrue(all(faltantes == {} for _, faltantes in con_memo))

    def test_hidratar_trae_los_json_que_el_payload_lee(self):
        """V4-NEW-02, corregido contra el código.

        La ficha proponía que ``hidratar`` difiriera ``respuestas`` y ``definicion``.
        No puede: ``respuestas_por_destino`` abre ``definicion`` y ``data``, el CUIL
        respondido abre ``respuestas`` y las correcciones ``datos_siis``. Diferirlos los
        vuelve a pedir **de a uno**, que es lo contrario de lo que la ficha busca. El
        ``defer`` existe, pero es del llamador que no los lee (PERF-06).
        """
        ids = self._clonar(3)

        casos = proceso_masivo.hidratar(ids)
        with CaptureQueriesContext(connection) as sin_diferir:
            for caso in casos:
                armar_payload(caso, catalogos=Catalogos(cargar=_catalogo_falso), hoy=date(2026, 9, 14))

        diferidos = proceso_masivo.hidratar(ids, diferir=proceso_masivo.JSON_DEL_CASO)
        with CaptureQueriesContext(connection) as con_defer:
            for caso in diferidos:
                armar_payload(caso, catalogos=Catalogos(cargar=_catalogo_falso), hoy=date(2026, 9, 14))

        self.assertGreater(
            len(con_defer.captured_queries),
            len(sin_diferir.captured_queries),
            "si diferir los JSON no costara nada, la propuesta 5 de PERF-01 se aplicaría tal cual",
        )


class UnaSolaSubconsultaDelUltimoEnvioTests(TestCase):
    """PERF-19: el WHERE nombra la subconsulta del último envío una sola vez."""

    def setUp(self):
        # Con la planilla vacía el ``IN`` queda imposible y Django ni compila el WHERE.
        crear_tabla_aprobados_materias("30000000")

    def _where(self):
        consulta = proceso_masivo.candidatos()
        compilador = consulta.query.get_compiler("default")
        compilador.pre_sql_setup()
        return compilador.compile(consulta.query.where)[0]

    def test_la_subconsulta_del_ultimo_envio_no_se_escribe_dos_veces(self):
        where = self._where()

        # Dos referencias a la tabla: la subconsulta del último estado y el
        # ``NOT EXISTS`` del envío vigente —una búsqueda exacta contra su índice único,
        # que no se toca—. Solo la primera lleva el ``ORDER BY … LIMIT 1``.
        referencias = where.split('"programas_enviosiis"')[1:]
        con_orden = [pedazo for pedazo in referencias if "ORDER BY" in pedazo[:200]]

        self.assertEqual(len(referencias), 2, where)
        self.assertEqual(
            len(con_orden),
            1,
            "volvió a haber dos subconsultas correlacionadas del último envío en el WHERE:\n" + where,
        )


class LosMismosCandidatosTests(TestCase):
    """PERF-19: cambia el SQL, no el conjunto."""

    def setUp(self):
        call_command("seed_becas", stdout=StringIO())
        crear_tabla_aprobados_materias("40000000", "40000001", "40000002", "40000003")
        self.programa = ProgramaSiis.objects.create(nombre="P", siis_programa_id=71, siis_funcion_id=4)
        segmento = Segmento.objects.create(nombre="S", cupo_maximo=100, programa=self.programa)
        convocatoria = Convocatoria.objects.create(
            nombre="C", segmento=segmento, fecha_inicio=date(2026, 1, 1), fecha_fin=date(2026, 12, 31)
        )
        territorial = User.objects.create_user("terri_perf19", password="x")
        self.relevamiento = Relevamiento.objects.create(
            convocatoria=convocatoria, territorial=territorial, fecha_asignada=date(2026, 6, 1), zona="Z"
        )
        self.casos = []
        for indice in range(4):
            ciudadano = Ciudadano.objects.create(
                dni=f"4000000{indice}",
                nombre="N",
                apellido=f"A{indice}",
                fecha_nacimiento=date(1990, 1, 1),
                genero="F",
            )
            self.casos.append(
                Formulario.objects.create(
                    relevamiento=self.relevamiento,
                    ciudadano=ciudadano,
                    estado=Formulario.Estado.APROBADO,
                    validado_renaper=True,
                    data={"globales": {}, "requisitos": {}},
                )
            )

    def _envio(self, caso, estado, minutos, como_el_codigo_viejo=False):
        """Un intento de ``minutos`` atrás.

        ``como_el_codigo_viejo`` deja la fila ``ENVIADO`` **sin** ``vigente``, que es
        como nacen las que escribe la release anterior durante un rolling
        (expand/contract). Es el único escenario donde el filtro de PERF-19 decide
        solo: con ``vigente`` puesto, el ``NOT EXISTS`` ya lo saca.
        """
        envio = EnvioSIIS.objects.create(formulario=caso, estado=estado, documento=caso.ciudadano.dni)
        actualizar = {"creado": timezone.now() - timedelta(minutes=minutos)}
        if como_el_codigo_viejo:
            actualizar.update(vigente=None, clave_persona_plan=None)
        EnvioSIIS.objects.filter(pk=envio.pk).update(**actualizar)
        return envio

    def test_el_conjunto_es_el_mismo_que_con_los_dos_q(self):
        # Sin envíos; con un ERROR; con un ENVIADO viejo y un ERROR nuevo; con un
        # ENVIADO como último intento (ese no es candidato).
        self._envio(self.casos[1], EnvioSIIS.Estado.ERROR, 10)
        self._envio(self.casos[2], EnvioSIIS.Estado.ENVIADO, 20, como_el_codigo_viejo=True)
        self._envio(self.casos[2], EnvioSIIS.Estado.ERROR, 5)
        self._envio(self.casos[3], EnvioSIIS.Estado.ENVIADO, 5, como_el_codigo_viejo=True)

        nuevos = list(proceso_masivo.candidatos(programa=self.programa).values_list("pk", flat=True))

        self.assertEqual(nuevos, _candidatos_a_la_vieja(programa=self.programa))
        self.assertEqual(nuevos, [self.casos[0].pk, self.casos[1].pk, self.casos[2].pk])

    def test_un_envio_sin_estado_no_entra_como_candidato_nuevo(self):
        """El borde del ``Coalesce``: el valor de relleno (``""``) no puede coincidir
        con ningún estado real, o un caso informado volvería a salir."""
        self._envio(self.casos[0], EnvioSIIS.Estado.ENVIADO, 1, como_el_codigo_viejo=True)

        self.assertNotIn(
            self.casos[0].pk,
            list(proceso_masivo.candidatos(programa=self.programa).values_list("pk", flat=True)),
        )


class PantallaDelMasivoTests(TestCase):
    """PERF-07: los dos números de la pantalla, cuándo se calculan y cuándo no."""

    def setUp(self):
        cache.clear()
        call_command("seed_becas", stdout=StringIO())
        crear_tabla_aprobados_materias("50000000")
        self.programa = ProgramaSiis.objects.create(nombre="P masivo", siis_programa_id=72, siis_funcion_id=4)
        self.admin = User.objects.create_user("admin_masivo_perf", password="x")
        self.admin.groups.add(Group.objects.get(name=ROL_ADMIN))
        self.client.force_login(self.admin)
        self.url = reverse("becas:proceso_masivo", kwargs={"pk": self.programa.pk})

    def tearDown(self):
        cache.clear()

    def _sql_de_la_pantalla(self):
        with CaptureQueriesContext(connection) as capturadas:
            respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 200)
        return respuesta, [q["sql"] for q in capturadas.captured_queries]

    def test_con_una_corrida_en_curso_no_se_cuentan_los_candidatos(self):
        """La pantalla se relee sola cada 5 s mientras corre, y en ese estado la
        plantilla **no** muestra ninguno de los dos números."""
        CorridaSiis.objects.create(
            programa=self.programa,
            solicitada_por=self.admin,
            total_pedido=10,
            estado=CorridaSiis.Estado.EN_CURSO,
            latido=timezone.now(),
        )

        respuesta, sql = self._sql_de_la_pantalla()

        self.assertIsNone(respuesta.context["pendientes"])
        self.assertFalse(
            [s for s in sql if "COUNT" in s.upper() and "programas_formulario" in s],
            "la pantalla volvió a contar candidatos con una corrida en curso",
        )
        self.assertFalse(
            [s for s in sql if "aprobados_materias" in s and "SELECT dni" in s],
            "la pantalla volvió a leer la planilla entera de DNI habilitados",
        )

    def test_sin_corrida_el_conteo_se_calcula_una_vez_y_se_cachea(self):
        _, primera = self._sql_de_la_pantalla()
        _, segunda = self._sql_de_la_pantalla()

        self.assertTrue([s for s in primera if "COUNT" in s.upper() and "programas_formulario" in s])
        self.assertFalse(
            [s for s in segunda if "COUNT" in s.upper() and "programas_formulario" in s],
            "el segundo request volvió a contar: el cacheo de PERF-07 dejó de funcionar",
        )

    def test_los_dos_conteos_leen_los_insumos_una_sola_vez(self):
        with CaptureQueriesContext(connection) as juntos:
            proceso_masivo.conteos_de_la_pantalla(self.programa)
        with CaptureQueriesContext(connection) as separados:
            proceso_masivo.candidatos(programa=self.programa).count()
            proceso_masivo.candidatos(programa=self.programa, solo_incompatibles=True).count()

        self.assertLess(len(juntos.captured_queries), len(separados.captured_queries))

    def test_sin_la_tabla_de_materias_la_pantalla_lo_dice_sin_leerla(self):
        with connection.cursor() as cur:
            cur.execute(f"DROP TABLE {proceso_masivo.TABLA_APROBADOS_MATERIAS}")

        respuesta, sql = self._sql_de_la_pantalla()

        self.assertTrue(respuesta.context["tabla_materias_faltante"])
        self.assertIn("aprobados_materias", respuesta.context["motivo_bloqueo"])
        self.assertFalse([s for s in sql if "COUNT" in s.upper() and "programas_formulario" in s])


class ValidarCasosSiisTests(TestCase):
    """PERF-06: el comando hidrata por lotes y sin los JSON del caso."""

    def setUp(self):
        call_command("seed_becas", stdout=StringIO())
        programa = ProgramaSiis.objects.create(nombre="P val", siis_programa_id=73, siis_funcion_id=4)
        segmento = Segmento.objects.create(nombre="S val", cupo_maximo=100, programa=programa)
        convocatoria = Convocatoria.objects.create(
            nombre="C val", segmento=segmento, fecha_inicio=date(2026, 1, 1), fecha_fin=date(2026, 12, 31)
        )
        territorial = User.objects.create_user("terri_perf06", password="x")
        self.relevamiento = Relevamiento.objects.create(
            convocatoria=convocatoria, territorial=territorial, fecha_asignada=date(2026, 6, 1), zona="Z"
        )

    def _casos(self, cuantos, desde=0):
        for indice in range(desde, desde + cuantos):
            ciudadano = Ciudadano.objects.create(
                dni=f"6{indice:07d}",
                nombre="N",
                apellido=f"V{indice}",
                fecha_nacimiento=date(1990, 1, 1),
                genero="F",
            )
            Formulario.objects.create(
                relevamiento=self.relevamiento,
                ciudadano=ciudadano,
                estado=Formulario.Estado.ENVIADO,
                data={"globales": {}, "requisitos": {}},
                definicion={"campos": []},
            )

    def _correr(self, **extra):
        salida = StringIO()
        with CaptureQueriesContext(connection) as capturadas:
            call_command("validar_casos_siis", stdout=salida, **extra)
        return salida.getvalue(), [q["sql"] for q in capturadas.captured_queries]

    def test_el_ensayo_no_pide_los_json_del_caso(self):
        self._casos(5)

        _, sql = self._correr()

        del_caso = [s for s in sql if "programas_formulario" in s and "SELECT" in s]
        self.assertTrue(del_caso)
        for consulta in del_caso:
            for columna in JSON_DEL_CASO:
                self.assertNotIn(
                    f'"{columna}"',
                    consulta,
                    f"`{columna}` volvió a viajar en la selección de validar_casos_siis",
                )

    @override_settings(SIIS_API_CLIENT_ID="x", SIIS_API_CLIENT_SECRET="y")
    def test_el_aplicar_hidrata_por_lote_y_no_por_caso(self):
        """Ficha: con N=10 y N=30 las consultas crecen por lote, no por caso."""

        def hidrataciones(sql):
            return len([s for s in sql if "programas_formulario" in s and 'WHERE "programas_formulario"."id" IN' in s])

        self._casos(10)
        respuesta_de_siis = {"success": True, "compatible": True, "data": {}}
        with patch("programas.services.validacion_siis.validar_compatibilidad", return_value=respuesta_de_siis):
            _, con_diez = self._correr(aplicar=True, lote=50)
            self._casos(20, desde=10)
            _, con_treinta = self._correr(aplicar=True, lote=50)

        self.assertEqual(hidrataciones(con_diez), 1)
        self.assertEqual(hidrataciones(con_treinta), 1)

    def test_el_ensayo_cuenta_los_salteados_en_la_base(self):
        """Los dos números que antes salían de recorrer los casos en memoria."""
        self._casos(3)
        sin_ciudadano = Formulario.objects.create(
            relevamiento=self.relevamiento,
            estado=Formulario.Estado.ENVIADO,
            data={"globales": {}, "requisitos": {}},
        )

        texto, _ = self._correr()

        self.assertIn("se van a saltear", texto)
        self.assertIn("1 sin DNI", texto)
        self.assertEqual(ValidacionSIS.objects.count(), 0)
        self.assertTrue(sin_ciudadano.pk)
