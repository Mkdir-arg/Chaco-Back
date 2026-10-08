"""Lo que solo se ve ejecutando contra el motor de producción (TST-01, PR R-11).

La suite entera corre sobre **SQLite en memoria** (`PYTEST_RUNNING=1`), y hay una
familia de bugs que ahí da verde y en ECOM rompe: el UUID con guiones de MariaDB
10.7+ (incidente del 29/09/2026), `CONVERT_TZ` contra una base sin tablas de zona
horaria (Cambios 64 y 66, y DIS-01, vivo), `JSON_EXTRACT` con clave numérica, los
`select_for_update` —que en SQLite son un no-op— y las `UniqueConstraint` con
condición, que MySQL y MariaDB **no crean**.

Estos tests llevan `@tag("mysql")` y no corren en la suite normal: los corre el job
«Motor real» de `pr-performance.yml` con `manage.py test --tag mysql` contra
`mariadb:10.11`, `mariadb:11` y `mysql:8.0`, declarando cuál con `DJANGO_TEST_MOTOR`.
Sin motor real se saltean; con `DJANGO_TEST_MOTOR` puesto y una conexión que igual
es SQLite, fallan: un servicio que no levantó deja el paso en rojo en vez de volver
a medir SQLite sin que nadie se entere.

**División del trabajo con `core/tests/test_sql_motor_real.py`** (RED-07/08/09, PR
R-10): aquel **compila** el queryset contra el backend de MySQL sin abrir conexión y
afirma sobre la forma del SQL —corre en todos los PRs, en SQLite—; este **ejecuta**
el mismo código contra el servidor y mira el resultado. Son complementarios: la
forma del SQL se puede fijar en cada PR, barato; lo que el motor hace con esa forma
necesita el motor.

`MARIADB_INITDB_SKIP_TZINFO` no es un detalle: la imagen oficial de MariaDB **carga**
las tablas de zona horaria en el arranque, y con ellas `CONVERT_TZ` funciona y la
familia de bugs de DIS-01 no se manifiesta. La base de ECOM no las tiene, así que
sin esa variable la pata de MariaDB daría un verde que no significa nada. `mysql:8.0`
sí las trae, igual que icore: la matriz queda asimétrica porque así son los dos
destinos. Lo fija `MotorDeclaradoTests.test_mariadb_corre_sin_las_tablas_de_zona_horaria_como_ecom`.

Para correrlo a mano (contenedor efímero, puerto libre)::

    docker run -d --name r11 -e MARIADB_ROOT_PASSWORD=root -e MARIADB_DATABASE=datanach \
      -e MARIADB_INITDB_SKIP_TZINFO=1 -p 3320:3306 mariadb:10.11
    $env:DJANGO_SECRET_KEY="test-key"; $env:DJANGO_TEST_MOTOR="mariadb:10.11"
    $env:DATABASE_NAME="datanach"; $env:DATABASE_USER="root"; $env:DATABASE_PASSWORD="root"
    $env:DATABASE_HOST="127.0.0.1"; $env:DATABASE_PORT="3320"
    python manage.py test --tag mysql
"""

import threading
import time
import uuid
from datetime import date, timedelta
from io import StringIO
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import connection, connections
from django.test import TestCase, TransactionTestCase, tag
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from legajos.models import Ciudadano
from programas.models import (
    Admision,
    Cama,
    Convocatoria,
    DisenoFormulario,
    Dispositivo,
    Formulario,
    ItemDiseno,
    ListaEspera,
    PadronHabilitado,
    PreguntaGlobal,
    ProgramaSiis,
    Relevamiento,
    Segmento,
    TipoCampo,
    TipoDispositivo,
    TracaFormulario,
    ValidacionSIS,
)
from programas.services import dashboard_becas as dashboard
from programas.services.becas import (
    formulario_por_client_uuid,
    relevamiento_publico_por_token,
    resolver_ciudadano_offline,
)
from programas.services.cupo import agregar_a_lista_espera, aprobar_o_poner_en_espera, dar_baja_beneficiario
from programas.services.registro_diario import calcular_cantidades
from programas.services.respuestas import foto_definicion

#: El servidor que contestó, no el que se pidió.
MOTOR_REAL = connection.vendor == "mysql"


def convert_tz_devuelve_null():
    """¿El servidor está sin tablas de zona horaria, como el de ECOM?

    Se consulta en vez de deducirse de la imagen: lo que importa es el servidor que
    contestó. Va en una función y no en una constante de módulo porque al importar
    el módulo la base de test todavía no existe.
    """
    with connection.cursor() as cursor:
        cursor.execute("SELECT CONVERT_TZ('2026-09-05 12:00:00', 'UTC', %s)", [settings.TIME_ZONE])
        return cursor.fetchone()[0] is None


class MotorRealMixin:
    """Sin motor real se saltea; con motor declarado y SQLite del otro lado, falla."""

    def setUp(self):
        if settings.TEST_MOTOR and not MOTOR_REAL:
            self.fail(
                f"DJANGO_TEST_MOTOR={settings.TEST_MOTOR} pide motor real y la conexión es "
                f"«{connection.vendor}»: revisá DATABASE_* y que no haya quedado PYTEST_RUNNING mandando."
            )
        if not MOTOR_REAL:
            self.skipTest("Necesita MySQL o MariaDB de verdad (DJANGO_TEST_MOTOR + DATABASE_*).")
        super().setUp()


def _convocatoria(nombre="Conv motor real", cupo=10, programa=None):
    segmento = Segmento.objects.create(nombre=f"Seg {nombre}", cupo_maximo=cupo, programa=programa)
    return Convocatoria.objects.create(
        nombre=nombre,
        segmento=segmento,
        fecha_inicio=date(2026, 1, 1),
        fecha_fin=date(2026, 12, 31),
    )


@tag("mysql")
class MotorDeclaradoTests(MotorRealMixin, TestCase):
    """El paso corre contra el motor que dice correr, con las opciones de ECOM."""

    def test_el_servidor_es_el_que_declara_django_test_motor(self):
        """`mariadb:11` tiene que ser MariaDB 11, no «lo que haya levantado el runner».

        Las tres patas de la matriz comparten workflow: un `image:` mal
        interpolado las dejaría a las tres contra el mismo motor y el paso seguiría
        en verde, probando una sola cosa tres veces.
        """
        self.assertTrue(
            settings.TEST_MOTOR,
            "Correr contra el motor real sin declararlo en DJANGO_TEST_MOTOR deja sin verificar cuál contestó.",
        )
        sabor, _, version = settings.TEST_MOTOR.partition(":")

        self.assertEqual(
            connection.mysql_is_mariadb, sabor == "mariadb", f"el servidor dice {connection.mysql_version}"
        )
        esperada = tuple(int(parte) for parte in version.split("."))
        self.assertEqual(connection.mysql_version[: len(esperada)], esperada)

    def test_la_conexion_usa_las_opciones_de_produccion(self):
        """El `read_timeout` de 10 s es el límite acordado con ECOM (Cambio 91, OPS-05).

        Si el job lo relajara para que «no corte», dejaría de medir lo que pasa en
        producción justo en el escenario que importa.
        """
        opciones = connection.settings_dict["OPTIONS"]

        self.assertEqual(opciones["read_timeout"], 10)
        self.assertEqual(opciones["write_timeout"], 10)
        self.assertEqual(opciones["charset"], "utf8mb4")
        self.assertEqual(opciones["isolation_level"], "read committed")

    def test_mariadb_corre_sin_las_tablas_de_zona_horaria_como_ecom(self):
        """La pata de MariaDB reproduce la base de ECOM: `CONVERT_TZ` devuelve NULL.

        Medido al escribir este PR, y al revés de lo que se suponía: las **dos**
        imágenes oficiales traen las tablas de zona horaria cargadas —MariaDB las
        carga en el init salvo `MARIADB_INITDB_SKIP_TZINFO`, y `mysql:8.0` las trae
        de fábrica—. Con ellas, `CONVERT_TZ` anda y la familia de bugs que motiva
        esta matriz (Cambios 64 y 66; DIS-01, viva) **no se manifiesta**: la pata
        daría verde sin probar nada.

        Así que la matriz queda asimétrica a propósito, porque así son los dos
        destinos: **MariaDB = ECOM**, sin tablas de zona horaria (`CLAUDE.md`
        §Gotchas), y **MySQL = icore**, que corre la imagen oficial y sí las tiene.
        Lo que no puede pasar es que MariaDB las tenga, y eso es lo que fija el test.
        """
        if not connection.mysql_is_mariadb:
            self.skipTest("MySQL corre como icore, con las tablas cargadas: el contrato de ECOM es el de MariaDB.")

        self.assertTrue(
            convert_tz_devuelve_null(),
            "El servidor tiene cargadas las tablas de zona horaria y la base de ECOM no: "
            "levantá MariaDB con MARIADB_INITDB_SKIP_TZINFO=1 o el paso no prueba nada.",
        )


@tag("mysql")
class UuidEnElMotorRealTests(MotorRealMixin, TestCase):
    """Las dos formas del UUID conviven en la misma columna y las dos se encuentran.

    En MariaDB 10.7+ Django 5 manda el `UUIDField` **con guiones** (36 caracteres) y
    en MySQL 8 en hex (32); una base restaurada de un motor al otro trae la forma
    ajena. `q_uuid_en_texto` (RED-08/09) compara contra las dos sin envolver la
    columna. Eso, en SQLite, no se puede probar: ahí hay una sola forma.
    """

    def setUp(self):
        super().setUp()
        self.conv = _convocatoria()
        self.rel = Relevamiento.objects.create(
            convocatoria=self.conv,
            tipo=Relevamiento.Tipo.PUBLICO,
            fecha_asignada=timezone.now(),
        )

    def _token_guardado(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT token_publico FROM programas_relevamiento WHERE id = %s", [self.rel.pk])
            return cursor.fetchone()[0]

    def test_la_columna_guarda_la_forma_que_manda_el_motor(self):
        """Caracterización del incidente del 29/09: en MariaDB entra con guiones."""
        guardado = self._token_guardado()

        if connection.features.has_native_uuid_field:  # MariaDB 10.7+
            self.assertEqual(guardado, str(self.rel.token_publico))
            self.assertEqual(len(guardado), 36)
        else:
            self.assertEqual(guardado, self.rel.token_publico.hex)

    def test_el_link_publico_encuentra_su_relevamiento(self):
        encontrado = relevamiento_publico_por_token(self.rel.token_publico).first()

        self.assertEqual(encontrado, self.rel)

    def test_el_link_publico_encuentra_una_fila_restaurada_con_la_otra_forma(self):
        """La fila que dejó un restore del otro motor también tiene que abrir el link."""
        otra_forma = (
            self.rel.token_publico.hex if connection.features.has_native_uuid_field else str(self.rel.token_publico)
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE programas_relevamiento SET token_publico = %s WHERE id = %s", [otra_forma, self.rel.pk]
            )

        self.assertEqual(relevamiento_publico_por_token(self.rel.token_publico).first(), self.rel)

    def test_la_clave_idempotente_de_la_app_encuentra_las_dos_formas(self):
        """`client_uuid` lo manda la app de campo: con él se decide si el caso ya entró."""
        client_uuid = uuid.uuid4()
        formulario = Formulario.objects.create(relevamiento=self.rel, celular="3624100100", client_uuid=client_uuid)

        self.assertEqual(formulario_por_client_uuid(self.rel, client_uuid), formulario)

        otra_forma = client_uuid.hex if connection.features.has_native_uuid_field else str(client_uuid)
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE programas_formulario SET client_uuid = %s WHERE id = %s", [otra_forma, formulario.pk]
            )

        self.assertEqual(formulario_por_client_uuid(self.rel, client_uuid), formulario)

    def test_la_columna_admite_los_36_caracteres(self):
        """Sin la ampliación a `char(36)` el alta muere con «Data too long» (programas.0073)."""
        self.rel.token_publico = uuid.uuid4()
        self.rel.save(update_fields=["token_publico", "modificado"])

        self.assertEqual(Relevamiento.objects.filter(pk=self.rel.pk).count(), 1)


@tag("mysql")
class DashboardEnElMotorRealTests(MotorRealMixin, TestCase):
    """El dashboard calcula contra el motor real: sin `CONVERT_TZ` y con `JSON_EXTRACT`.

    Los dos bloques que ya costaron incidentes (Cambios 64 y 66, y la medición del
    25/09 sobre el banco MySQL) se ejecutan acá de punta a punta. Un `TruncWeek`
    «simplificador» o un `KeyTransform` con clave numérica dan NULL contra una base
    sin tablas de zona horaria o contra un objeto JSON, y acá se ve.
    """

    def setUp(self):
        super().setUp()
        cache.clear()
        call_command("crear_programas", stdout=StringIO())
        self.admin = User.objects.create_superuser("admin-motor-real", "a@b.com", "x")
        self.programa = ProgramaSiis.objects.create(nombre="Programa motor real", siis_programa_id=941)
        self.conv = _convocatoria(programa=self.programa)
        self.rel = Relevamiento.objects.create(
            convocatoria=self.conv,
            territorial=self.admin,
            fecha_asignada=timezone.now(),
            zona="Z",
        )
        self.pregunta = PreguntaGlobal.objects.create(
            texto="Situación laboral", tipo=TipoCampo.SELECTOR, opciones=["Trabaja", "Estudia"], orden=1
        )
        for indice, respuesta in enumerate(("Trabaja", "Trabaja", "Estudia")):
            Formulario.objects.create(
                relevamiento=self.rel,
                celular=f"362410010{indice}",
                data={"globales": {str(self.pregunta.pk): respuesta}, "requisitos": {}},
            )
        hoy = timezone.localdate()
        self.filtros = dashboard.Filtros(desde=hoy - timedelta(days=30), hasta=hoy)

    def test_la_serie_semanal_cuenta_los_casos_de_la_semana(self):
        """Con `TruncWeek` el motor devolvería NULL y la serie saldría vacía (RED-07)."""
        datos = dashboard.metricas(self.admin, self.programa, self.filtros)

        self.assertEqual(datos.indicadores.formularios_recibidos, 3)
        self.assertEqual(sum(semana["total"] for semana in datos.serie_semanal), 3)

    def test_la_distribucion_de_respuestas_agrupa_por_la_clave_numerica_del_json(self):
        """`JSON_EXTRACT(data, '$."globales"."13"')`: con `KeyTransform` sería un índice."""
        distribucion = dashboard.distribucion_respuestas(
            self.admin, self.programa, self.filtros, f"global:{self.pregunta.pk}"
        )

        self.assertEqual(distribucion.base, 3)
        self.assertEqual(
            {fila["opcion"]: fila["total"] for fila in distribucion.opciones},
            {"Trabaja": 2, "Estudia": 1},
        )


@tag("mysql")
class CamposPropiosEnElMotorRealTests(MotorRealMixin, TestCase):
    """G2-01 contra el motor real: los campos propios del constructor.

    Lo que SQLite no prueba y acá sí: `JSON_EXTRACT(respuestas, '$."cp-xxx"')` sobre la
    columna **nueva** y con la ruta en la raíz (no bajo `globales`/`requisitos`), y el
    `GROUP BY` sobre **varias** extracciones JSON a la vez —la pregunta y las claves de
    las que depende su condición—, que es la forma en que una respuesta oculta deja de
    contar sin leer la foto de cada caso. Una ruta sin comillas o un `KeyTransform`
    devolverían NULL y las tres distribuciones saldrían vacías.
    """

    def setUp(self):
        super().setUp()
        cache.clear()
        call_command("crear_programas", stdout=StringIO())
        self.admin = User.objects.create_superuser("admin-propios-motor", "a@b.com", "x")
        self.programa = ProgramaSiis.objects.create(nombre="Programa propios", siis_programa_id=942)
        self.conv = _convocatoria(programa=self.programa)
        self.rel = Relevamiento.objects.create(
            convocatoria=self.conv,
            territorial=self.admin,
            fecha_asignada=timezone.now(),
            zona="Z",
        )
        diseno = DisenoFormulario.objects.create(convocatoria=self.conv, version=1)
        grupo = ItemDiseno.objects.create(diseno=diseno, tipo=ItemDiseno.Tipo.GRUPO, clave="g-1", orden=0)
        ItemDiseno.objects.create(
            diseno=diseno,
            tipo=ItemDiseno.Tipo.CAMPO,
            clave="cp-madre001",
            padre=grupo,
            orden=1,
            propio={"texto": "¿Sos madre?", "tipo": TipoCampo.SELECTOR, "opciones": ["Sí", "No"]},
        )
        ItemDiseno.objects.create(
            diseno=diseno,
            tipo=ItemDiseno.Tipo.CAMPO,
            clave="cp-hijos001",
            padre=grupo,
            orden=2,
            condicion={"modo": "todas", "reglas": [{"fuente": "cp-madre001", "op": "es", "valor": "Sí"}]},
            propio={"texto": "¿Cuántos hijos?", "tipo": TipoCampo.SELECTOR, "opciones": ["Uno", "Dos"]},
        )
        for indice, respuestas in enumerate(
            (
                {"cp-madre001": "Sí", "cp-hijos001": "Dos"},
                {"cp-madre001": "Sí", "cp-hijos001": "Dos"},
                {"cp-madre001": "No", "cp-hijos001": "Uno"},  # oculta por la condición
            )
        ):
            Formulario.objects.create(
                relevamiento=self.rel,
                celular=f"362420010{indice}",
                data={"globales": {}, "requisitos": {}},
                respuestas=respuestas,
                definicion=foto_definicion(self.rel),
            )
        hoy = timezone.localdate()
        self.filtros = dashboard.Filtros(desde=hoy - timedelta(days=30), hasta=hoy)

    def test_la_distribucion_de_un_campo_propio_sale_de_la_columna_respuestas(self):
        distribucion = dashboard.distribucion_respuestas(self.admin, self.programa, self.filtros, "cp-madre001")

        self.assertEqual(distribucion.base, 3)
        self.assertEqual({fila["opcion"]: fila["total"] for fila in distribucion.opciones}, {"Sí": 2, "No": 1})

    def test_el_group_by_sobre_dos_extracciones_descarta_lo_que_la_condicion_oculto(self):
        distribucion = dashboard.distribucion_respuestas(self.admin, self.programa, self.filtros, "cp-hijos001")

        self.assertEqual(distribucion.base, 2)
        self.assertEqual({fila["opcion"]: fila["total"] for fila in distribucion.opciones}, {"Dos": 2, "Uno": 0})

    def test_el_excel_por_persona_trae_la_columna_propia_sin_leer_la_foto_por_fila(self):
        with CaptureQueriesContext(connection) as capturadas:
            reporte, _alcance = dashboard.respuestas_por_persona(self.conv)

        cabeceras = list(reporte.encabezados)
        self.assertIn("¿Sos madre?", cabeceras)
        filas = [dict(zip(cabeceras, fila)) for fila in reporte.filas]
        self.assertEqual(sorted(f["¿Sos madre?"] for f in filas), ["No", "Sí", "Sí"])
        # La condición oculta la respuesta del tercer caso, también en la planilla.
        self.assertEqual(sorted(f["¿Cuántos hijos?"] for f in filas), ["", "Dos", "Dos"])
        self.assertEqual(
            [sql for sql in (q["sql"] for q in capturadas) if "programas_formulario" in sql and "definicion" in sql],
            [],
            "la foto no puede volver a leerse por fila: con 20.000 casos son 12 s de export",
        )


class _BaseDispositivoTest(MotorRealMixin, TestCase):
    """Un hogar con una cama y una persona alojada hoy."""

    def setUp(self):
        super().setUp()
        tipo = TipoDispositivo.objects.create(codigo="MR", nombre="Hogar", maneja_camas=True)
        self.dispositivo = Dispositivo.objects.create(
            codigo="HOGAR-MR", nombre="Hogar motor real", tipo=tipo, camas_totales=2
        )
        self.cama = Cama.objects.create(dispositivo=self.dispositivo, codigo="C-01")
        ciudadano = Ciudadano.objects.create(dni="30111222", nombre="Persona", apellido="Parte")
        self.hoy = timezone.localdate()
        self.admision = Admision.objects.create(
            ciudadano=ciudadano,
            dispositivo=self.dispositivo,
            cama=self.cama,
            fecha_ingreso=timezone.now(),
            estado=Admision.Estado.ALOJADO,
        )


@tag("mysql")
class ParteDiarioEnElMotorRealTests(_BaseDispositivoTest):
    """DIS-01 contra el motor real: `__date` sobre un `DateTimeField` no cuenta nada.

    Solo tiene sentido contra un servidor **sin** tablas de zona horaria, que es el
    de ECOM y el que arma el CI; contra uno que las tenga, `CONVERT_TZ` resuelve y el
    bug no se manifiesta, así que la clase se saltea en vez de reportar un éxito
    inesperado que diría lo contrario de lo que pasa en producción.
    """

    def setUp(self):
        super().setUp()
        if not convert_tz_devuelve_null():
            self.skipTest("El servidor tiene tablas de zona horaria: DIS-01 no se manifiesta acá.")

    def test_el_parte_diario_cuenta_el_ingreso_de_hoy(self):
        """**DIS-01** (Ola 5, Cambio 140), contra el motor real.

        `calcular_cantidades` filtraba con `fecha_ingreso__date=fecha`, que en MySQL
        y MariaDB se traduce a `DATE(CONVERT_TZ(...))`; sin tablas de zona horaria
        devuelve NULL y el parte F-01 informaba **cero ingresos** en producción. En
        SQLite daba bien, y por eso el bug vivió hasta la Ola 5. Ahora el día se
        acota con un rango `[inicio, fin)` calculado en Python
        (`core.utils_fechas.rango_dia_local`), que no depende del servidor: este
        test queda como la regresión que lo cuida en el motor donde rompía.
        """
        cantidades = calcular_cantidades(dispositivo=self.dispositivo, fecha=self.hoy)

        self.assertEqual(cantidades["ingresos"], 1)

    def test_la_ocupacion_nocturna_del_parte_si_cuenta(self):
        """Caracterización que acompaña al `expectedFailure` de arriba.

        La ocupación compara `fecha_ingreso` contra un `datetime` completo, sin
        truncar: esa parte del parte diario sí funciona. Sin este test, el
        `expectedFailure` podría quedar «verde» porque el fixture esté roto.
        """
        cantidades = calcular_cantidades(dispositivo=self.dispositivo, fecha=self.hoy)

        self.assertEqual(cantidades["ocupacion_nocturna"], 1)
        self.assertEqual(cantidades["camas_totales"], 1)


@tag("mysql")
class ConstraintCondicionalTests(_BaseDispositivoTest):
    """Lo que la base **no** hace cumplir en producción, aunque el modelo lo declare."""

    def test_una_uniqueconstraint_con_condicion_no_existe_en_el_motor(self):
        """**DIS-02** (v2), caracterizado: `supports_partial_indexes = False`.

        `Admision` declara `UniqueConstraint(fields=["cama"], condition=Q(estado="ALOJADO"))`
        y en SQLite la base la hace cumplir, así que la suite «prueba» una unicidad
        que en ECOM no existe: dos personas pueden quedar en la misma cama. La
        defensa real es el chequeo explícito en el servicio (DIS-02); lo que fija
        este test es que la ilusión se vea en el CI.
        """
        otro = Ciudadano.objects.create(dni="30111333", nombre="Otra", apellido="Persona")

        Admision.objects.create(
            ciudadano=otro,
            dispositivo=self.dispositivo,
            cama=self.cama,
            fecha_ingreso=timezone.now(),
            estado=Admision.Estado.ALOJADO,
        )

        self.assertEqual(Admision.objects.filter(cama=self.cama, estado=Admision.Estado.ALOJADO).count(), 2)


@tag("mysql")
class CarreraDeCupoTests(MotorRealMixin, TransactionTestCase):
    """RED-67 · capa 2: dos hilos sobre el último lugar, con el candado de verdad.

    La capa 1 (`programas/tests/test_candados_concurrencia.py::ContratoDeCandadosTests`)
    afirma que el `select_for_update()` se pide y desde dónde; no puede afirmar que
    sirva, porque en SQLite es un no-op. Acá se corre la carrera: dos requests
    simultáneos sobre un segmento con **un** lugar libre. Sin el candado los dos
    leen el mismo `cupo_disponible`, los dos aprueban, el cupo se excede y SIIS
    recibe dos altas —que no tiene baja—.
    """

    def setUp(self):
        super().setUp()
        self.programa = ProgramaSiis.objects.create(nombre="Programa carrera", siis_programa_id=942)
        self.conv = _convocatoria(nombre="Conv carrera", cupo=1, programa=self.programa)
        self.segmento = self.conv.segmento
        self.rel = Relevamiento.objects.create(
            convocatoria=self.conv,
            fecha_asignada=timezone.now(),
            tipo=Relevamiento.Tipo.PUBLICO,
        )
        self.admin = User.objects.create_superuser("admin-carrera", "c@c.com", "x")
        self.formularios = [self._caso_aprobable(f"3011100{numero}") for numero in (1, 2)]

    def _caso_aprobable(self, dni):
        ciudadano = Ciudadano.objects.create(dni=dni, nombre="Persona", apellido=dni, fecha_nacimiento=date(1990, 5, 3))
        formulario = Formulario.objects.create(
            relevamiento=self.rel,
            celular=f"3624{dni[:6]}",
            ciudadano=ciudadano,
            validado_renaper=True,
        )
        ValidacionSIS.objects.create(
            formulario=formulario,
            estado=ValidacionSIS.Estado.OK,
            id_programa=self.programa.siis_id_plan_soc_efectivo,
            documento=dni,
            respuesta={"resultado": "OK", "apto": True},
            solicitado_por=self.admin,
        )
        return formulario

    def _en_paralelo(self, operacion):
        """Corre `operacion(formulario)` en dos hilos que arrancan juntos."""
        barrera = threading.Barrier(2, timeout=30)
        resultados, errores = [], []

        def correr(pk):
            try:
                formulario = Formulario.objects.get(pk=pk)
                barrera.wait()
                resultados.append(operacion(formulario))
            except Exception as exc:  # el hilo no propaga: se reporta al final
                errores.append(exc)
            finally:
                connections.close_all()

        hilos = [threading.Thread(target=correr, args=(formulario.pk,)) for formulario in self.formularios]
        for hilo in hilos:
            hilo.start()
        for hilo in hilos:
            hilo.join(timeout=60)

        self.assertEqual([repr(e) for e in errores], [])
        return resultados

    def test_dos_aprobaciones_simultaneas_consumen_un_solo_lugar(self):
        resultados = self._en_paralelo(lambda formulario: aprobar_o_poner_en_espera(formulario, self.admin))

        self.assertEqual(sorted(resultados), ["aprobado", "lista_espera"])
        self.assertEqual(Formulario.objects.filter(estado=Formulario.Estado.APROBADO).count(), 1)
        self.assertEqual(ListaEspera.objects.filter(promovido=False).count(), 1)

    def test_dos_altas_simultaneas_a_la_lista_no_comparten_posicion(self):
        self._en_paralelo(lambda formulario: agregar_a_lista_espera(formulario, self.segmento, self.admin))

        posiciones = sorted(ListaEspera.objects.values_list("posicion", flat=True))

        self.assertEqual(posiciones, [1, 2])


@tag("mysql")
class CarreraDelMismoCasoTests(MotorRealMixin, TransactionTestCase):
    """BEC-01 y BEC-02 · capa 2: dos requests sobre **el mismo** caso.

    ``CarreraDeCupoTests`` corre dos casos distintos contra el último lugar: lo
    que protege ahí es el candado del *segmento*. Acá los dos hilos pelean por la
    misma fila de ``programas_formulario`` —doble clic, dos pestañas, la pantalla
    y el masivo—, que es lo que el candado del segmento no cubre y lo que hasta
    ahora no tomaba nadie del lado de aprobar.

    Sin el candado de la fila, con READ COMMITTED los dos leen el mismo estado,
    los dos escriben y el caso se resuelve dos veces: dos trazas, dos correos y
    dos altas en SIIS —que no tiene baja—.

    Medido contra este mismo MariaDB 10.11, con `cupo.py` en `development`: los
    dos de abajo fallan (dos filas activas en la lista; las dos bajas pasan) y el
    de las dos aprobaciones **pasa**, porque esas dos ya las serializaba el
    candado del segmento. Ese queda igual como guarda de regresión: lo que hoy lo
    sostiene es un candado que no es el suyo, y la baja y el alta a la lista
    muestran que con eso no alcanza.
    """

    def setUp(self):
        super().setUp()
        self.programa = ProgramaSiis.objects.create(nombre="Programa mismo caso", siis_programa_id=944)
        self.conv = _convocatoria(nombre="Conv mismo caso", cupo=10, programa=self.programa)
        self.segmento = self.conv.segmento
        self.rel = Relevamiento.objects.create(
            convocatoria=self.conv,
            fecha_asignada=timezone.now(),
            tipo=Relevamiento.Tipo.PUBLICO,
        )
        self.admin = User.objects.create_superuser("admin-mismo-caso", "m@c.com", "x")
        ciudadano = Ciudadano.objects.create(
            dni="30222111", nombre="Persona", apellido="Unica", fecha_nacimiento=date(1990, 5, 3)
        )
        self.formulario = Formulario.objects.create(
            relevamiento=self.rel, celular="3624302221", ciudadano=ciudadano, validado_renaper=True
        )
        ValidacionSIS.objects.create(
            formulario=self.formulario,
            estado=ValidacionSIS.Estado.OK,
            id_programa=self.programa.siis_id_plan_soc_efectivo,
            documento=ciudadano.dni,
            respuesta={"resultado": "OK", "apto": True},
            solicitado_por=self.admin,
        )

    def _dos_veces(self, operacion):
        """La misma operación sobre el mismo caso, en dos hilos que arrancan juntos."""
        barrera = threading.Barrier(2, timeout=30)
        resultados, errores = [], []

        def correr():
            try:
                formulario = Formulario.objects.get(pk=self.formulario.pk)
                barrera.wait()
                resultados.append(operacion(formulario))
            except Exception as exc:  # el perdedor de la carrera avisa: se cuenta
                errores.append(exc)
            finally:
                connections.close_all()

        hilos = [threading.Thread(target=correr) for _ in range(2)]
        for hilo in hilos:
            hilo.start()
        for hilo in hilos:
            hilo.join(timeout=60)
        return resultados, errores

    def test_dos_aprobaciones_del_mismo_caso_dejan_una_sola(self):
        resultados, errores = self._dos_veces(lambda f: aprobar_o_poner_en_espera(f, self.admin))

        self.assertEqual(resultados, ["aprobado"], "los dos hilos aprobaron el mismo caso")
        self.assertEqual(len(errores), 1)
        self.assertIsInstance(errores[0], ValidationError)
        self.formulario.refresh_from_db()
        self.assertEqual(self.formulario.estado, Formulario.Estado.APROBADO)
        self.assertEqual(
            TracaFormulario.objects.filter(formulario=self.formulario, campo="estado").count(),
            1,
            "la aprobación se registró dos veces: la fila del caso no se serializó",
        )

    def test_dos_altas_del_mismo_caso_a_la_lista_dejan_una_sola_fila(self):
        _, errores = self._dos_veces(lambda f: agregar_a_lista_espera(f, self.segmento, self.admin))

        self.assertEqual(ListaEspera.objects.filter(formulario=self.formulario, promovido=False).count(), 1)
        self.assertEqual(len(errores), 1)
        self.assertIsInstance(errores[0], ValidationError)

    def test_una_baja_y_una_aprobacion_a_la_vez_no_se_pisan(self):
        """La aprobación y la baja se serializan: el caso queda en una sola de las dos."""
        self.formulario.estado = Formulario.Estado.APROBADO
        self.formulario.save(update_fields=["estado"])
        barrera = threading.Barrier(2, timeout=30)
        errores = []

        def bajar():
            try:
                formulario = Formulario.objects.get(pk=self.formulario.pk)
                barrera.wait()
                dar_baja_beneficiario(formulario, self.admin)
            except Exception as exc:
                errores.append(exc)
            finally:
                connections.close_all()

        hilos = [threading.Thread(target=bajar) for _ in range(2)]
        for hilo in hilos:
            hilo.start()
        for hilo in hilos:
            hilo.join(timeout=60)

        self.assertEqual(len(errores), 1, "las dos bajas pasaron: la fila no se serializó")
        self.formulario.refresh_from_db()
        self.assertEqual(self.formulario.estado, Formulario.Estado.BAJA)
        self.assertEqual(TracaFormulario.objects.filter(formulario=self.formulario, campo="estado").count(), 1)


@tag("mysql")
class EscriturasAtomicasMotorRealTests(MotorRealMixin, TransactionTestCase):
    """RED-35 contra el motor de verdad: el rollback es un `ROLLBACK`, no un savepoint.

    El gemelo de `core/tests/test_contrato_escrituras.py` corre dentro del
    `atomic` de `TestCase`, así que lo que deshace el error es un `ROLLBACK TO
    SAVEPOINT` de SQLite. Acá no hay transacción envolvente: la de
    `resolver_ciudadano_offline` es la única, y la que tiene que volver atrás es
    InnoDB. Es también donde se vería un motor que confirmara la escritura antes
    de tiempo (DDL implícito, `autocommit` perdido).
    """

    def setUp(self):
        super().setUp()
        self.convocatoria = _convocatoria("Conv atomic motor real")
        self.relevamiento = Relevamiento.objects.create(
            convocatoria=self.convocatoria,
            territorial=User.objects.create_user("terri_atomic_mr", password="x"),
            fecha_asignada=date(2026, 6, 1),
            zona="A",
        )
        self.formulario = Formulario.objects.create(
            relevamiento=self.relevamiento,
            celular="3624555666",
            email_contacto="lucia@correo.com",
            datos_identificacion={"dni": "41222333", "nombre": "Lucía", "apellido": "Paz", "sexo": "F"},
        )

    def test_resolver_ciudadano_offline_no_commitea_a_medias(self):
        with patch(
            "programas.services.becas._completar_contacto",
            side_effect=RuntimeError("se cayó el paso siguiente"),
        ):
            with self.assertRaises(RuntimeError):
                resolver_ciudadano_offline(self.formulario)

        self.assertFalse(
            Ciudadano.objects.filter(dni="41222333").exists(),
            "El legajo quedó commiteado por una escritura que falló.",
        )
        self.formulario.refresh_from_db()
        self.assertIsNone(self.formulario.ciudadano_id)
        self.assertIsNotNone(self.formulario.datos_identificacion)


@tag("mysql")
class IdentidadDelPadronMotorRealTests(MotorRealMixin, TestCase):
    """RED-77: la regla RN-2 del queryset se evalúa en el servidor, no en Python.

    `con_identidad()` filtra con `__regex`, y los dos motores de producción ni
    siquiera usan el mismo mecanismo: Django compila el lookup como
    `%s REGEXP BINARY %s` en **MariaDB** (PCRE) y como `REGEXP_LIKE(%s, %s, 'c')`
    en **MySQL 8** (ICU). En SQLite lo resuelve `re` de Python, así que la suite
    normal **no** prueba lo que corre en ECOM.

    Medido en la ronda 2 del PR: con `\\s` —o con `[[:space:]]`— la pata de
    MariaDB discrepa de `strip()` en los espacios que no son ASCII (NBSP, EM
    SPACE, IDEOGRAPHIC SPACE, NEL), porque ahí las dos clases son ASCII. Por eso
    la regla usa la **clase literal** de `CARACTERES_SIN_TEXTO`, que los tres
    motores resuelven igual. Los casos de abajo son exactamente esa diferencia,
    más los dos controles de falso positivo (acentos y espacio interno).
    """

    CASOS = [
        ("40000001", "Ana", "Paz", True),
        ("40000002", "", "Paz", False),
        ("40000003", "Ana", "", False),
        ("40000004", "", "", False),
        ("40000005", "   ", "Paz", False),
        ("40000006", "Ana", "   ", False),
        ("40000007", "\tAna", "Paz", True),
        ("40000008", "\t", "Paz", False),
        # Lo que `\s` de MariaDB no reconoce (el NBSP es el que deja un
        # copy&paste de una web o un PDF).
        ("40000009", "\xa0", "Paz", False),
        ("40000010", " ", "Paz", False),
        ("40000011", "　", "Paz", False),
        ("40000012", "\x85", "Paz", False),
        ("40000013", "\xa0  \t", "Paz", False),
        # Controles de falso positivo: `REGEXP BINARY` podría mirar bytes, y la
        # «à» se codifica con el mismo `A0` que el NBSP.
        ("40000014", "Añá", "Óé", True),
        ("40000015", "à", "Paz", True),
        ("40000016", "Ana\xa0Paz", "Paz", True),
        ("40000017", "​", "Paz", True),  # ZWSP no es whitespace para Python
    ]

    def test_con_identidad_dice_lo_mismo_que_la_property_en_el_motor_real(self):
        convocatoria = _convocatoria("Conv padron motor real")
        for dni, nombre, apellido, _ in self.CASOS:
            PadronHabilitado.objects.create(
                convocatoria=convocatoria, dni=dni, sexo="F", nombre=nombre, apellido=apellido
            )

        con_identidad = set(PadronHabilitado.objects.con_identidad().values_list("dni", flat=True))

        for dni, nombre, apellido, esperado in self.CASOS:
            with self.subTest(dni=dni, nombre=repr(nombre), apellido=repr(apellido)):
                fila = PadronHabilitado.objects.get(dni=dni)
                self.assertEqual(fila.tiene_identidad, esperado)
                self.assertEqual(
                    dni in con_identidad,
                    esperado,
                    f"{connection.vendor} {connection.mysql_version}: el REGEXP del motor no coincide "
                    "con `tiene_identidad` para esta fila.",
                )


@tag("mysql")
class CandadoDeBootstrapTests(MotorRealMixin, TransactionTestCase):
    """OPS-07 · `bootstrap_lock` serializa de verdad, con dos conexiones.

    `GET_LOCK` es de la **conexión**, así que para probarlo hace falta una segunda: con
    una sola, el mismo cliente puede volver a tomar un candado que ya tiene. La capa de
    protocolo —qué SQL manda, qué pasa si no lo consigue— está en
    `core/tests/test_bootstrap_lock.py`, que corre en todos los PRs sobre SQLite; acá se
    verifica lo único que SQLite no puede decir: que el segundo proceso **espera**.
    """

    NOMBRE = "datanach_test_bootstrap"

    def _otra_conexion(self):
        otra = connections.create_connection("default")
        self.addCleanup(otra.close)
        return otra

    def _get_lock(self, conexion, espera=0):
        with conexion.cursor() as cursor:
            cursor.execute("SELECT GET_LOCK(%s, %s)", [self.NOMBRE, espera])
            return cursor.fetchone()[0]

    def _release(self, conexion):
        with conexion.cursor() as cursor:
            cursor.execute("SELECT RELEASE_LOCK(%s)", [self.NOMBRE])

    def test_una_segunda_conexion_no_consigue_el_candado_tomado(self):
        primera, segunda = self._otra_conexion(), self._otra_conexion()
        self.assertEqual(self._get_lock(primera), 1)
        try:
            self.assertEqual(self._get_lock(segunda), 0, "el motor dejó entrar a dos migradores")
        finally:
            self._release(primera)

    def test_al_soltarlo_el_siguiente_entra(self):
        primera, segunda = self._otra_conexion(), self._otra_conexion()
        self.assertEqual(self._get_lock(primera), 1)
        self._release(primera)

        self.assertEqual(self._get_lock(segunda), 1)
        self._release(segunda)

    def test_el_candado_muere_con_la_conexion(self):
        """Es la razón de usar `GET_LOCK` y no una fila de control: un pod matado a mitad
        del bootstrap no puede dejar bloqueado el deploy siguiente."""
        efimera = connections.create_connection("default")
        self.assertEqual(self._get_lock(efimera), 1)
        efimera.close()

        otra = self._otra_conexion()
        self.assertEqual(self._get_lock(otra, espera=5), 1)
        self._release(otra)

    def test_el_comando_corre_sus_comandos_con_el_candado_puesto(self):
        salida = StringIO()

        call_command("bootstrap_lock", "--nombre", self.NOMBRE, "--espera", "5", "--comando", "check", stdout=salida)

        self.assertIn("Candado", salida.getvalue())
        # Al terminar, el candado quedó libre para el deploy siguiente.
        otra = self._otra_conexion()
        self.assertEqual(self._get_lock(otra), 1)
        self._release(otra)


@tag("mysql")
class MigracionReentranteTests(MotorRealMixin, TransactionTestCase):
    """RED-58 · `legajos.0007` corrida dos veces seguidas contra el motor.

    La base de test ya tiene la migración aplicada (el job «Motor real» corre migraciones
    de verdad). Lo que se verifica es que volver a correr el camino de ida —que es lo que
    hace el reintento de una migración cortada, porque no hay fila en `django_migrations`—
    no explote con el `ERROR 1091` del `DROP FOREIGN KEY` sobre una FK que ya no está, y
    deje el esquema igual.
    """

    COLUMNAS = (
        ("legajos_legajoatencion", "id"),
        ("legajos_alertaciudadano", "legajo_id"),
        ("legajos_historialcontacto", "legajo_id"),
        ("legajos_adjunto", "object_id"),
    )

    def _esquema(self):
        from core.migraciones import nombre_de_fk, tipo_de_columna

        with connection.schema_editor(atomic=False) as editor:
            tipos = {clave: tipo_de_columna(editor, *clave) for clave in self.COLUMNAS}
            fks = {
                tabla: nombre_de_fk(editor, tabla, "legajo_id")
                for tabla in ("legajos_alertaciudadano", "legajos_historialcontacto")
            }
        return tipos, fks

    def _ampliar(self):
        import importlib

        migracion = importlib.import_module("legajos.migrations.0007_ampliar_uuid_legajos")
        with connection.schema_editor(atomic=False) as editor:
            migracion.ampliar_uuid_legajos_mysql(None, editor)

    def test_ampliar_uuid_es_idempotente(self):
        antes = self._esquema()

        self._ampliar()
        self._ampliar()

        self.assertEqual(self._esquema(), antes)
        self.assertEqual({tipo for tipo in antes[0].values()}, {"char(36)"})
        self.assertNotIn(None, antes[1].values())


@tag("mysql")
class CandadoSobreviveAlLoaddataTests(MotorRealMixin, TransactionTestCase):
    """OPS-07 · El candado no se suelta porque un comando cierre la conexión.

    `seed_datos_base` llama a `loaddata`, y `loaddata` termina con
    `connections[alias].close()` —a propósito: es un workaround de Django para un bug
    viejo de MySQL (#7572)—. Con el candado tomado sobre `connections["default"]`, ese
    `close()` lo liberaba a mitad del sembrado y un segundo bootstrap podía entrar: medido
    con dos arranques simultáneos sobre una base vacía, los dos sembraron en paralelo.

    Esto solo se puede probar contra el motor real: en SQLite `GET_LOCK` no existe y el
    comando ni siquiera toma candado.
    """

    NOMBRE = "datanach_test_loaddata"

    def _conexion_testigo(self):
        """Un tercero que intenta tomar el candado, como haría el otro pod."""
        testigo = connections.create_connection("default")
        self.addCleanup(testigo.close)
        return testigo

    def test_un_comando_que_cierra_la_conexion_no_suelta_el_candado(self):
        testigo = self._conexion_testigo()
        visto = {}
        salida = StringIO()

        def comando_que_cierra_la_conexion(*args, **kwargs):
            connections["default"].close()  # exactamente lo que hace `loaddata`
            with testigo.cursor() as cursor:
                cursor.execute("SELECT GET_LOCK(%s, 0)", [self.NOMBRE])
                visto["lo_tomo_el_testigo"] = cursor.fetchone()[0]

        with patch("core.management.commands.bootstrap_lock.call_command", comando_que_cierra_la_conexion):
            call_command(
                "bootstrap_lock",
                "--nombre",
                self.NOMBRE,
                "--espera",
                "3",
                "--comando",
                "seed_datos_base",
                stdout=salida,
            )

        self.assertEqual(
            visto["lo_tomo_el_testigo"],
            0,
            "otro bootstrap pudo tomar el candado mientras este sembraba",
        )
        self.assertNotIn("AVISO", salida.getvalue())
        self.assertIn("liberado", salida.getvalue())

    def test_al_terminar_el_candado_queda_libre_para_el_deploy_siguiente(self):
        salida = StringIO()
        with patch("core.management.commands.bootstrap_lock.call_command", lambda *a, **kw: None):
            call_command(
                "bootstrap_lock", "--nombre", self.NOMBRE, "--espera", "3", "--comando", "check", stdout=salida
            )

        testigo = self._conexion_testigo()
        with testigo.cursor() as cursor:
            cursor.execute("SELECT GET_LOCK(%s, 0)", [self.NOMBRE])
            self.assertEqual(cursor.fetchone()[0], 1)
            cursor.execute("SELECT RELEASE_LOCK(%s)", [self.NOMBRE])


@tag("mysql")
class CandadoConLaConexionMuertaTests(MotorRealMixin, TransactionTestCase):
    """OPS-07 · Que se caiga la conexión del candado no puede hacer fallar el bootstrap.

    La conexión dedicada es la que **no habla**: toma el candado y se queda ociosa hasta
    que terminan el `migrate` y los seeds (141-218 s medidos). Si el servidor la cierra en
    el medio —`wait_timeout` apretado, un `KILL`, un firewall que corta ociosos— el
    `SELECT IS_USED_LOCK` del `finally` levantaba un 2013 y el comando salía con **exit 1**
    sobre un esquema correcto: Job en `Failed`, initContainer en CrashLoop, y el AVISO
    escrito justo para ese caso no llegaba a imprimirse nunca.

    Acá se mata la conexión de verdad, con un `KILL` desde otra, en el momento exacto en
    que el comando está corriendo sus comandos con el candado tomado.
    """

    NOMBRE = "datanach_test_muerta"

    def _conexion_testigo(self):
        testigo = connections.create_connection("default")
        self.addCleanup(testigo.close)
        return testigo

    @staticmethod
    def _id_del_candado(salida):
        """El comando imprime «Candado «x» tomado (conexión N).» antes de correr nada."""
        for linea in salida.getvalue().splitlines():
            if "tomado (conexión" in linea:
                return int(linea.rsplit("conexión", 1)[1].strip(" ).\n"))
        raise AssertionError(f"el comando no informó qué conexión tomó el candado:\n{salida.getvalue()}")

    def test_un_kill_de_la_conexion_del_candado_no_cambia_el_exit_code(self):
        testigo = self._conexion_testigo()
        salida = StringIO()
        visto = {}

        def comando_que_corre_mientras_matan_la_conexion(*args, **kwargs):
            visto["id"] = self._id_del_candado(salida)
            with testigo.cursor() as cursor:
                cursor.execute(f"KILL {visto['id']}")

        with patch(
            "core.management.commands.bootstrap_lock.call_command",
            comando_que_corre_mientras_matan_la_conexion,
        ):
            # Lo que importa es que NO levante: antes salía con un 2013 desde el `finally`.
            call_command(
                "bootstrap_lock", "--nombre", self.NOMBRE, "--espera", "3", "--comando", "check", stdout=salida
            )

        self.assertIn("AVISO", salida.getvalue())
        self.assertIn("se cayó durante el bootstrap", salida.getvalue())
        self.assertNotIn("liberado", salida.getvalue())

        # Y el candado quedó libre: el servidor lo soltó al cerrar la conexión.
        with testigo.cursor() as cursor:
            cursor.execute("SELECT GET_LOCK(%s, 0)", [self.NOMBRE])
            self.assertEqual(cursor.fetchone()[0], 1)
            cursor.execute("SELECT RELEASE_LOCK(%s)", [self.NOMBRE])

    def test_la_conexion_del_candado_sobrevive_a_un_wait_timeout_global_apretado(self):
        """El `SET SESSION wait_timeout` es la otra mitad: que no se caiga, no solo que no
        falle cuando se cae."""
        testigo = self._conexion_testigo()
        with testigo.cursor() as cursor:
            cursor.execute("SELECT @@GLOBAL.wait_timeout")
            global_original = cursor.fetchone()[0]
            cursor.execute("SET GLOBAL wait_timeout = 2")
        self.addCleanup(self._restaurar_wait_timeout, testigo, global_original)

        salida = StringIO()

        def comando_que_tarda_mas_que_el_wait_timeout(*args, **kwargs):
            time.sleep(5)

        with patch(
            "core.management.commands.bootstrap_lock.call_command",
            comando_que_tarda_mas_que_el_wait_timeout,
        ):
            call_command(
                "bootstrap_lock", "--nombre", self.NOMBRE, "--espera", "3", "--comando", "check", stdout=salida
            )

        self.assertIn("liberado", salida.getvalue(), f"el candado no sobrevivió:\n{salida.getvalue()}")
        self.assertNotIn("AVISO", salida.getvalue())

    @staticmethod
    def _restaurar_wait_timeout(testigo, valor):
        with testigo.cursor() as cursor:
            cursor.execute("SET GLOBAL wait_timeout = %s", [valor])
