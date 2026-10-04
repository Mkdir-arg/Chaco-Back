"""Forma del SQL que las consultas críticas le mandan al motor de producción (R-10).

Los tests corren sobre SQLite como el resto de la suite, pero **no** miran lo que
SQLite ejecuta: compilan el queryset contra el backend de MySQL/MariaDB sin abrir
ninguna conexión y afirman sobre el texto resultante. Es la única forma de que el
CI vea las dos clases de bug que en SQLite dan verde y en ECOM rompen:

* ``CONVERT_TZ`` (RED-07): ``Trunc*``/``__date`` sobre un ``DateTimeField`` con
  ``USE_TZ``. La base de ECOM no tiene cargadas las tablas de zona horaria, así que
  ``CONVERT_TZ`` devuelve NULL: gráfico vacío o 500, solo en producción. Ya costó
  tres incidentes (Cambios 64 y 66, y DIS-01, todavía vivo) y hasta ahora la única
  defensa eran dos comentarios.
* Funciones sobre la columna en el ``WHERE`` (RED-08): ``REPLACE(CAST(...))`` anula
  el índice. El Cambio 91 (165 respuestas 500 el 24/09/2026 en el link público) no
  fue un problema de **cantidad** de consultas —era una sola, como ahora— sino de
  su forma, y por eso los dos tests que lo cuidaban siguieron verdes con el bug.

Cada afirmación va acompañada de su pin invertido (``..._si_compila_...``): si Django
cambiara de estrategia de compilación, el test avisa en vez de quedar verde por una
comparación que ya no mira nada.

La ejecución real de estos casos contra MariaDB es otra ficha (TST-01, ``--tag mysql``).
"""

import unittest
import uuid
from contextlib import contextmanager
from datetime import date
from unittest import mock

from django.contrib.auth.models import User
from django.db import connections
from django.db.models import Count, QuerySet
from django.db.models.functions import TruncWeek
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from programas.models import (
    Admision,
    Cama,
    Convocatoria,
    Dispositivo,
    Formulario,
    InscripcionPrograma,
    Relevamiento,
)
from programas.services import reportes
from programas.services.becas import formulario_por_client_uuid, relevamiento_publico_por_token
from programas.services.dashboard_becas import Filtros, _serie_semanal
from programas.services.inscripcion_publica import dni_en_convocatoria
from programas.services.registro_diario import calcular_cantidades

UUID_CUALQUIERA = uuid.UUID("5d0f3f0a-9b1a-4a7e-8f1a-2b3c4d5e6f70")


def sql_mysql(consulta, mariadb=False):
    """SQL que ``consulta`` le mandaría a MySQL (o a MariaDB), sin tocar la red.

    Acepta un ``QuerySet`` o una ``Query``. Arma un ``DatabaseWrapper`` de MySQL a
    mano y le siembra lo que el compilador le preguntaría al servidor (versión,
    sabor, ``sql_mode``), de modo que ``get_compiler`` nunca intente conectarse.
    ``allows_group_by_selected_pks`` se fija a mano porque es la propiedad que
    abre conexión al compilar un queryset agrupado.

    Helper compartido: lo usan los tests de RED-07, RED-08, RED-09 y TST-01. Vive
    una sola vez acá a propósito.
    """
    ajustes = dict(connections["default"].settings_dict)
    ajustes.update({"ENGINE": "django.db.backends.mysql", "HOST": "127.0.0.1", "PORT": "1", "NAME": "x"})
    from django.db.backends.mysql.base import DatabaseWrapper

    wrapper = DatabaseWrapper(ajustes, "probe_mysql")
    wrapper.__dict__["mysql_is_mariadb"] = mariadb
    wrapper.__dict__["mysql_version"] = (11, 8, 0) if mariadb else (8, 0, 32)
    wrapper.__dict__["mysql_server_data"] = {
        "version": "11.8.0-MariaDB" if mariadb else "8.0.32",
        "sql_mode": (),
        "default_storage_engine": "InnoDB",
        "lower_case_table_names": False,
        "has_zoneinfo_database": False,
    }
    wrapper.features.__dict__["allows_group_by_selected_pks"] = False
    return str(getattr(consulta, "query", consulta).get_compiler(connection=wrapper).as_sql()[0])


@contextmanager
def consultas_de(*modelos):
    """Intercepta los querysets de ``modelos`` justo antes de que toquen la base.

    Permite compilar el SQL **que arma la función de producción** en vez de
    reescribir su queryset dentro del test: un test que reescribe el queryset
    sigue verde cuando el código real cambia, que es justo lo que hay que evitar.
    Los querysets de los demás modelos (sesión, usuario, permisos) se ejecutan
    normalmente, así que adentro del bloque se puede llamar a una vista.
    """
    capturadas = []
    originales = {nombre: getattr(QuerySet, nombre) for nombre in ("_fetch_all", "exists", "count", "iterator")}

    def _es_nuestro(queryset):
        return queryset.model in modelos

    def _fetch_all(self):
        if not _es_nuestro(self):
            return originales["_fetch_all"](self)
        capturadas.append(self)
        self._result_cache = []
        self._prefetch_done = True
        return None

    def _exists(self, *args, **kwargs):
        if not _es_nuestro(self):
            return originales["exists"](self, *args, **kwargs)
        capturadas.append(self)
        return False

    def _count(self, *args, **kwargs):
        if not _es_nuestro(self):
            return originales["count"](self, *args, **kwargs)
        capturadas.append(self)
        return 0

    def _iterator(self, *args, **kwargs):
        if not _es_nuestro(self):
            return originales["iterator"](self, *args, **kwargs)
        capturadas.append(self)
        return iter(())

    with mock.patch.multiple(QuerySet, _fetch_all=_fetch_all, exists=_exists, count=_count, iterator=_iterator):
        yield capturadas


class SinConvertTZTests(TestCase):
    """RED-07: ninguna consulta viva puede traducirse a ``CONVERT_TZ``."""

    def test_la_serie_semanal_del_dashboard_no_compila_convert_tz(self):
        """El gráfico semanal agrupa en Python; con ``TruncWeek`` sale vacío en PRD."""
        formularios = Formulario.objects.filter(relevamiento_id__in=[1, 2]).order_by()
        with consultas_de(Formulario) as capturadas:
            _serie_semanal(formularios, Filtros())
        self.assertTrue(capturadas, "El servicio no llegó a consultar formularios")
        for queryset in capturadas:
            for mariadb in (False, True):
                with self.subTest(mariadb=mariadb):
                    self.assertNotIn("CONVERT_TZ", sql_mysql(queryset, mariadb=mariadb))

    def test_tendencias_agrupa_por_la_columna_sin_convert_tz(self):
        """``fecha_inscripcion`` ya es ``DateField``: agrupar por la columna usa el índice."""
        usuario = User.objects.create_superuser("tendencias", "tendencias@example.com", "x")
        from dashboard.api_views import tendencias_datos

        peticion = APIRequestFactory().get("/api/dashboard/tendencias/", {"periodo": "30d"})
        force_authenticate(peticion, user=usuario)
        with consultas_de(InscripcionPrograma) as capturadas:
            respuesta = tendencias_datos(peticion)
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(capturadas, "La vista no llegó a consultar inscripciones")
        for queryset in capturadas:
            sql = sql_mysql(queryset)
            self.assertNotIn("CONVERT_TZ", sql)
            self.assertIn("`programas_inscripcionprograma`.`fecha_inscripcion`", sql)

    def test_truncweek_si_compila_convert_tz(self):
        """Pin invertido: lo que pasaría si alguien «simplifica» la serie semanal.

        Si Django cambiara de estrategia y dejara de emitir ``CONVERT_TZ``, este
        test se pone rojo y avisa que los de arriba quedaron sin contenido.
        """
        agrupado = (
            Formulario.objects.filter(relevamiento_id__in=[1, 2])
            .annotate(semana=TruncWeek("creado"))
            .values("semana")
            .annotate(total=Count("id"))
        )
        self.assertIn("CONVERT_TZ", sql_mysql(agrupado))

    def test_hoy_los_reportes_de_dispositivos_si_compilan_convert_tz(self):
        """Caracterización de DIS-01: así está hoy el código que arregla la Ola 5.

        Acompaña al ``expectedFailure`` de abajo: mientras este test pase, el que
        falla lo hace por el bug y no porque la captura dejó de funcionar.
        """
        periodo = reportes._movimientos_en_periodo(date(2026, 1, 1), date(2026, 1, 31))
        self.assertIn("CONVERT_TZ", sql_mysql(Admision.objects.filter(periodo)))

    @unittest.expectedFailure
    def test_ninguna_consulta_de_reporte_usa_convert_tz(self):
        """DIS-01 (Ola 5): el parte F-01 y los reportes de Dispositivos filtran con ``__date``.

        ``fecha_ingreso``/``fecha_egreso`` son ``DateTimeField``, así que
        ``__date`` se traduce a ``DATE(CONVERT_TZ(...))``: en ECOM los conteos
        del parte diario salen en cero y el reporte por período no trae nada.
        Cuando la Ola 5 lo arregle, se saca el decorador.
        """
        sentencias = []
        dispositivo = Dispositivo(pk=1)
        with consultas_de(Admision, Cama) as capturadas:
            calcular_cantidades(dispositivo=dispositivo, fecha=date(2026, 1, 15))
        self.assertTrue(capturadas, "El parte diario no llegó a consultar movimientos")
        sentencias.extend(sql_mysql(queryset) for queryset in capturadas)
        periodo = reportes._movimientos_en_periodo(date(2026, 1, 1), date(2026, 1, 31))
        sentencias.append(sql_mysql(Admision.objects.filter(periodo)))
        for sql in sentencias:
            with self.subTest(sql=sql[:80]):
                self.assertNotIn("CONVERT_TZ", sql)


class ColumnaSargableTests(TestCase):
    """RED-08: las búsquedas por clave externa comparan la columna pelada."""

    #: Funciones que, envolviendo la columna, anulan el índice en MySQL/MariaDB.
    ENVOLTORIOS = r"(REPLACE|CAST|LOWER|UPPER|CONCAT|TRIM)\s*\(\s*`?\w+`?\.`?%s`?"

    def _assert_columna_pelada(self, sql, columna):
        self.assertNotRegex(sql, self.ENVOLTORIOS % columna)
        self.assertIn(f"`{columna}` = ", sql)

    def test_las_busquedas_por_uuid_y_dni_no_envuelven_la_columna(self):
        """Las tres consultas del link público comparan por igualdad, sin funciones."""
        for mariadb in (False, True):
            with self.subTest(motor="mariadb" if mariadb else "mysql"):
                por_token = relevamiento_publico_por_token(UUID_CUALQUIERA)
                self._assert_columna_pelada(sql_mysql(por_token, mariadb=mariadb), "token_publico")

                with consultas_de(Formulario) as capturadas:
                    formulario_por_client_uuid(Relevamiento(pk=1), UUID_CUALQUIERA)
                self.assertTrue(capturadas, "La búsqueda por client_uuid no llegó a la base")
                for queryset in capturadas:
                    self._assert_columna_pelada(sql_mysql(queryset, mariadb=mariadb), "client_uuid")

                with consultas_de(Formulario) as capturadas:
                    dni_en_convocatoria(Convocatoria(pk=1), "30111222")
                self.assertEqual(len(capturadas), 2, "RN-P5 son dos consultas, cada una por su índice")
                self._assert_columna_pelada(sql_mysql(capturadas[0], mariadb=mariadb), "dni_titular")
                self._assert_columna_pelada(sql_mysql(capturadas[1], mariadb=mariadb), "dni")

    def test_la_forma_vieja_del_cambio_91_si_envuelve_la_columna(self):
        """Pin invertido: el código que estuvo vivo entre el 21/08 y el 25/09 de 2026.

        Sin esto, el ``assertNotRegex`` de arriba podría quedar verde para siempre
        por un patrón que ya no matchea nada.
        """
        from django.db.models import CharField, Value
        from django.db.models.functions import Cast, Replace

        vieja = Formulario.objects.annotate(
            normalizado=Replace(Cast("client_uuid", CharField()), Value("-"), Value(""))
        ).filter(normalizado="5d0f3f0a9b1a4a7e8f1a2b3c4d5e6f70")
        self.assertRegex(sql_mysql(vieja), self.ENVOLTORIOS % "client_uuid")
