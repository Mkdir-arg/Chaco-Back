"""Caracterización de los tres comandos contra SIIS y RENAPER (RED-32).

De los seis comandos SIIS que la Ola 1 va a reescribir, cuatro ya tienen red
(``corregir_datos_siis``, ``procesar_casos_siis``, ``enviar_casos_siis`` y
``correr_alta_siis`` se ejercen con ``call_command``). Estos tres estaban en
**0 % de cobertura**:

- ``validar_casos_siis`` escribe una ``ValidacionSIS`` por consulta, y lo que
  registra es lo que el revisor ve como vigente al abrir el caso.
- ``completar_casos_renaper`` reescribe identidad y ya tuvo un bug de memoria y
  timeout (``a427bffe``, 23/09: «trae los casos lote a lote») cuyo arreglo no
  tocó ningún test.
- ``sincronizar_programas_siis`` corre como CronJob diario a las 04:00.

Acá no se juzga nada: se **fija lo que hace hoy**, para que la Ola 1 vea en rojo
cualquier cambio de conducta. La red nunca se toca: el cliente HTTP va mockeado
en todos los casos, y donde no se moquea es porque el comando no debería salir a
la red (y eso también se afirma).
"""

from datetime import date
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext

from programas.models import Formulario, ProgramaSiis, RequisitoNativo, ValidacionSIS
from programas.services.siis import SiisCatalogError
from programas.tests.test_siis_envio import _BaseEnvioTest

TABLA_RENAPER = "ciudadanos_renaper"

PROVINCIAS = ["Chaco", "Corrientes", "Ciudad Autónoma de Buenos Aires"]


def preparar_information_schema():
    """Monta ``information_schema.tables`` y ``DATABASE()`` sobre SQLite.

    El comando pregunta por el volcado de RENAPER con el catálogo de MySQL, y
    esa guarda —cortar con un mensaje útil en vez de reventar a mitad— es
    justamente una de las cosas a fijar. Saltear la clase entera en SQLite
    dejaría al CI sin la red, así que en vez de eso se montan las dos piezas que
    faltan: una base adjunta que se llama ``information_schema`` con su tabla
    ``tables``, y la función ``DATABASE()``. El SQL del comando corre tal cual.

    SQLite no deja hacer ``ATTACH`` con una transacción abierta, así que esto va
    en ``setUpClass`` **antes** del ``atomic`` de ``TestCase``. La base adjunta
    vive en la conexión; el contenido de su tabla sí lo revierte el rollback de
    cada test, igual que el resto.
    """
    if connection.vendor != "sqlite":
        return
    with connection.cursor() as cur:
        connection.connection.create_function("DATABASE", 0, lambda: "main")
        cur.execute("PRAGMA database_list")
        if "information_schema" not in {fila[1] for fila in cur.fetchall()}:
            cur.execute("ATTACH DATABASE ':memory:' AS information_schema")
        cur.execute("CREATE TABLE IF NOT EXISTS information_schema.tables (table_schema TEXT, table_name TEXT)")


def crear_tabla_renaper(*filas):
    """El volcado que carga ``DatosPersonas.sql`` —el del directorio que apunta
    ``DATOS_SIIS_DIR``, desde RED-01— con las columnas que lee
    ``completar_casos_renaper``."""
    with connection.cursor() as cur:
        cur.execute(
            f"CREATE TABLE {TABLA_RENAPER} ("
            "dni_consultado VARCHAR(20), cuil VARCHAR(20), "
            "provincia_api VARCHAR(100), localidad_api VARCHAR(200), _ok INT)"
        )
        if connection.vendor == "sqlite":
            cur.execute("INSERT INTO information_schema.tables VALUES ('main', %s)", [TABLA_RENAPER])
        for dni, cuil, provincia, localidad, ok in filas:
            cur.execute(
                f"INSERT INTO {TABLA_RENAPER} "
                "(dni_consultado, cuil, provincia_api, localidad_api, _ok) VALUES (%s, %s, %s, %s, %s)",
                [dni, cuil, provincia, localidad, ok],
            )


# ───────────────────────────────────────────────────────────────────────────
# validar_casos_siis
# ───────────────────────────────────────────────────────────────────────────
class ValidarCasosSiisTests(_BaseEnvioTest):
    """``validar_casos_siis``: lo que selecciona y lo que escribe."""

    def setUp(self):
        super().setUp()
        # El caso que trae la base: ENVIADO. Se suman uno aprobado y uno rechazado.
        self.formulario.estado = Formulario.Estado.ENVIADO
        self.formulario.save(update_fields=["estado"])
        self.aprobado = Formulario.objects.create(
            relevamiento=self.relevamiento, ciudadano=self.ciudadano, estado=Formulario.Estado.APROBADO
        )
        self.rechazado = Formulario.objects.create(
            relevamiento=self.relevamiento, ciudadano=self.ciudadano, estado=Formulario.Estado.RECHAZADO
        )

    def correr(self, *args):
        salida = StringIO()
        # El cliente va mockeado aunque no se use: si alguna rama saliera a la
        # red, el test lo delata en vez de colgarse contra SIIS.
        with patch("programas.services.validacion_siis.validar_formulario_en_siis") as validar:
            call_command("validar_casos_siis", *args, stdout=salida, stderr=salida)
        return salida.getvalue(), validar

    def test_ensayo_sin_aplicar_no_escribe_y_cuenta_bien(self):
        salida, validar = self.correr()

        validar.assert_not_called()
        self.assertEqual(ValidacionSIS.objects.count(), 0)
        self.assertIn("ENSAYO", salida)
        self.assertIn("Casos en total: 3 · con alguna validación: 0", salida)
        # El rechazado por el revisor no entra: quedan dos.
        self.assertIn("A validar (sin validación): 2 casos", salida)
        self.assertIn("Ensayo terminado, no se consultó a SIIS.", salida)

    def test_el_ensayo_informa_el_host_de_siis(self):
        """El operador tiene que ver contra qué ambiente va a validar."""
        with override_settings(SIIS_API_URL="https://siisapi.ejemplo.test"):
            salida, _ = self.correr()
        self.assertIn("SIIS: https://siisapi.ejemplo.test", salida)

    def test_incluir_rechazados_suma_el_caso_que_el_revisor_rechazo(self):
        salida, _ = self.correr("--incluir-rechazados")
        self.assertIn("A validar (sin validación): 3 casos", salida)

    def test_un_caso_ya_validado_no_vuelve_a_entrar(self):
        ValidacionSIS.objects.create(formulario=self.formulario, estado=ValidacionSIS.Estado.OK)
        salida, _ = self.correr()
        self.assertIn("Casos en total: 3 · con alguna validación: 1", salida)
        self.assertIn("A validar (sin validación): 1 casos", salida)

    def test_reintentar_errores_vuelve_a_tomar_el_que_quedo_en_error(self):
        ValidacionSIS.objects.create(formulario=self.formulario, estado=ValidacionSIS.Estado.ERROR)
        salida, _ = self.correr()
        self.assertIn("A validar (sin validación): 1 casos", salida)
        salida, _ = self.correr("--reintentar-errores")
        self.assertIn("A validar (sin validación o con ERROR técnico): 2 casos", salida)

    def test_todos_revalida_hasta_los_que_ya_tienen_veredicto(self):
        ValidacionSIS.objects.create(formulario=self.formulario, estado=ValidacionSIS.Estado.OK)
        salida, _ = self.correr("--todos")
        self.assertIn("A validar (todos): 2 casos", salida)

    @override_settings(SIIS_API_CLIENT_ID="", SIIS_API_CLIENT_SECRET="")
    def test_sin_credenciales_con_aplicar_corta_antes_de_tocar_nada(self):
        with self.assertRaisesMessage(CommandError, "SIIS_API_CLIENT_ID"):
            self.correr("--aplicar")
        self.assertEqual(ValidacionSIS.objects.count(), 0)

    def test_un_usuario_inexistente_corta_la_corrida(self):
        with self.assertRaisesMessage(CommandError, "No existe el usuario «fulano»"):
            self.correr("--usuario", "fulano")


# ───────────────────────────────────────────────────────────────────────────
# completar_casos_renaper
# ───────────────────────────────────────────────────────────────────────────
class CompletarCasosRenaperTests(_BaseEnvioTest):
    """``completar_casos_renaper``: los frenos y el avance lote a lote."""

    @classmethod
    def setUpClass(cls):
        # Antes del atomic de TestCase: SQLite no adjunta bases en transacción.
        preparar_information_schema()
        super().setUpClass()

    def setUp(self):
        super().setUp()
        self.requisitos = {
            "cuit": RequisitoNativo.objects.create(
                texto="Cuit Alumno", tipo="INTEGER", segmento=self.segmento, orden=1
            ),
            "cuil": RequisitoNativo.objects.create(
                texto="Cuil Apoderado", tipo="INTEGER", segmento=self.segmento, orden=2
            ),
            "provincia": RequisitoNativo.objects.create(
                texto="Provincia Nacimiento",
                tipo="SELECTOR",
                opciones=PROVINCIAS,
                segmento=self.segmento,
                orden=3,
            ),
            "localidad": RequisitoNativo.objects.create(
                texto="Localidad de nacimiento", tipo="STRING", segmento=self.segmento, orden=4
            ),
        }

    def correr(self, *args):
        salida = StringIO()
        call_command("completar_casos_renaper", *args, stdout=salida, stderr=salida)
        return salida.getvalue()

    def _casos(self, cantidad):
        """``cantidad`` casos más (ya hay uno de la base), con DNI distinto."""
        creados = []
        for i in range(cantidad):
            from legajos.models import Ciudadano

            ciudadano = Ciudadano.objects.create(
                dni=f"3010000{i}", nombre=f"N{i}", apellido=f"A{i}", fecha_nacimiento=date(1995, 1, 1), genero="F"
            )
            creados.append(
                Formulario.objects.create(
                    relevamiento=self.relevamiento, ciudadano=ciudadano, data={"globales": {}, "requisitos": {}}
                )
            )
        return creados

    def test_sin_tabla_de_renaper_aborta_con_mensaje_util(self):
        """Primer freno: sin el volcado no hay nada que cruzar.

        Desde RED-01 (PR R-01) los volcados no están en el repo, así que el
        mensaje tiene que nombrar el archivo **y** la variable que dice dónde
        buscarlo: con solo «cargá DatosPersonas.sql» el operador no sabe de
        dónde sale. La ruta `scripts/` ya no corresponde.
        """
        with self.assertRaises(CommandError) as ctx:
            self.correr()
        mensaje = str(ctx.exception)
        self.assertIn("No existe la tabla", mensaje)
        self.assertIn(TABLA_RENAPER, mensaje)
        self.assertIn("DatosPersonas.sql", mensaje)
        self.assertIn("DATOS_SIIS_DIR", mensaje)
        self.assertNotIn("scripts/DatosPersonas.sql", mensaje)

    def test_sin_los_campos_del_catalogo_aborta_y_los_nombra(self):
        """Segundo freno: el comando escribe por texto del requisito, no por id."""
        crear_tabla_renaper()
        self.requisitos["provincia"].delete()
        with self.assertRaises(CommandError) as ctx:
            self.correr()
        self.assertIn("No están en el catálogo: Provincia Nacimiento", str(ctx.exception))

    def test_dry_run_no_escribe(self):
        crear_tabla_renaper((self.ciudadano.dni, "20203012349", "CHACO", "RESISTENCIA", 1))
        antes = Formulario.objects.get(pk=self.formulario.pk)

        salida = self.correr()

        self.assertIn("ENSAYO: no se escribe nada", salida)
        self.assertIn("la base quedó intacta", salida)
        despues = Formulario.objects.get(pk=self.formulario.pk)
        self.assertEqual(despues.respuestas, antes.respuestas)
        self.assertEqual(despues.data, antes.data)
        self.assertIsNone(despues.definicion)

    def test_aplicar_completa_el_cuit_desde_renaper(self):
        crear_tabla_renaper((self.ciudadano.dni, "20-30123456-9", "CHACO", "LAS_BREÑAS_", 1))

        salida = self.correr("--aplicar")

        self.formulario.refresh_from_db()
        clave = f"rn-{self.requisitos['cuit'].pk}"
        self.assertEqual(self.formulario.respuestas[clave], 20301234569)
        self.assertEqual(self.formulario.data["requisitos"][str(self.requisitos["cuit"].pk)], 20301234569)
        # La provincia sale por el selector y la localidad se vuelve legible.
        self.assertEqual(self.formulario.respuestas[f"rn-{self.requisitos['provincia'].pk}"], "Chaco")
        self.assertEqual(self.formulario.respuestas[f"rn-{self.requisitos['localidad'].pk}"], "Las Breñas")
        self.assertIn("Cuit Alumno completado", salida)

    def test_una_provincia_sin_opcion_en_el_selector_no_se_escribe_y_se_informa(self):
        crear_tabla_renaper((self.ciudadano.dni, "20301234569", "TIERRA DEL FUEGO", "USHUAIA", 1))

        salida = self.correr("--aplicar")

        self.formulario.refresh_from_db()
        self.assertNotIn(f"rn-{self.requisitos['provincia'].pk}", self.formulario.respuestas or {})
        self.assertIn("sin opción en el selector", salida)
        self.assertIn("TIERRA DEL FUEGO", salida)

    def test_lo_cargado_a_mano_no_se_pisa_salvo_que_se_pida(self):
        crear_tabla_renaper((self.ciudadano.dni, "20301234569", "CHACO", "RESISTENCIA", 1))
        clave = f"rn-{self.requisitos['cuit'].pk}"
        # Como lo tiene un caso cargado antes del Cambio 58: en ``data`` por pk.
        self.formulario.data = {"globales": {}, "requisitos": {str(self.requisitos["cuit"].pk): 99999999999}}
        self.formulario.save(update_fields=["data"])

        self.correr("--aplicar")
        self.formulario.refresh_from_db()
        self.assertEqual(self.formulario.respuestas[clave], 99999999999)

        self.correr("--aplicar", "--pisar-existentes")
        self.formulario.refresh_from_db()
        self.assertEqual(self.formulario.respuestas[clave], 20301234569)

    def test_sin_lugar_nacimiento_deja_provincia_y_localidad_afuera(self):
        crear_tabla_renaper((self.ciudadano.dni, "20301234569", "CHACO", "RESISTENCIA", 1))

        salida = self.correr("--aplicar", "--sin-lugar-nacimiento")

        self.formulario.refresh_from_db()
        self.assertIn(f"rn-{self.requisitos['cuit'].pk}", self.formulario.respuestas)
        self.assertNotIn(f"rn-{self.requisitos['provincia'].pk}", self.formulario.respuestas)
        self.assertIn("se omite por --sin-lugar-nacimiento", salida)

    def test_procesa_por_lotes(self):
        """El arreglo de ``a427bffe``: los casos se traen lote a lote.

        Volver a un ``for caso in qs:`` que trae todo de una vez no rompe ningún
        test de conducta, pero contra la base de ECOM —283 MB de fotos y un
        ``read_timeout`` de 10 s— muere con «Lost connection to server».
        """
        crear_tabla_renaper((self.ciudadano.dni, "20301234569", "CHACO", "RESISTENCIA", 1))
        self._casos(4)  # 5 casos en total
        self.assertEqual(Formulario.objects.count(), 5)

        with CaptureQueriesContext(connection) as consultas:
            salida = self.correr("--aplicar", "--lote", "2")

        self.assertIn("Casos a procesar: 5 en 3 lotes de 2", salida)
        self.assertEqual(salida.count("· casos "), 3)
        lecturas = [
            q["sql"]
            for q in consultas.captured_queries
            if "programas_formulario" in q["sql"] and q["sql"].lstrip().upper().startswith("SELECT")
        ]
        # Una lectura por lote como mínimo: con una sola consulta para los cinco
        # casos, este número baja.
        self.assertGreaterEqual(len(lecturas), 3)

    def test_el_limite_acota_los_casos(self):
        crear_tabla_renaper((self.ciudadano.dni, "20301234569", "CHACO", "RESISTENCIA", 1))
        self._casos(4)

        salida = self.correr("--limite", "2")

        self.assertIn("Casos a procesar: 2 en 1 lotes de 50", salida)

    def test_sin_casos_corta_temprano(self):
        crear_tabla_renaper()
        Formulario.objects.all().delete()

        salida = self.correr()

        self.assertIn("No hay casos que procesar.", salida)

    def test_solo_lee_las_filas_con_consulta_exitosa(self):
        """``_ok = 0`` es una consulta a RENAPER que falló: no es un dato."""
        crear_tabla_renaper((self.ciudadano.dni, "20301234569", "CHACO", "RESISTENCIA", 0))

        salida = self.correr("--aplicar")

        self.formulario.refresh_from_db()
        self.assertIn("RENAPER: 0 personas con respuesta", salida)
        self.assertNotIn(f"rn-{self.requisitos['cuit'].pk}", self.formulario.respuestas or {})


# ───────────────────────────────────────────────────────────────────────────
# sincronizar_programas_siis
# ───────────────────────────────────────────────────────────────────────────
class SincronizarProgramasSiisTests(TestCase):
    """``sincronizar_programas_siis``: el CronJob diario de las 04:00."""

    def setUp(self):
        self.programa = ProgramaSiis.objects.create(
            nombre="Ñachec",
            siis_programa_id=79,
            siis_programa_datos={"id": 79, "nombre": "Ñachec"},
            siis_programa_estado=ProgramaSiis.EstadoSiis.ACTIVO,
        )

    def correr(self, catalogo, *args):
        salida = StringIO()
        with patch("programas.services.siis_sync.listar_programas_todos", return_value=catalogo):
            call_command("sincronizar_programas_siis", *args, stdout=salida, stderr=salida)
        return salida.getvalue()

    def test_sin_cambios_no_dice_nada_raro(self):
        salida = self.correr([{"id": 79, "nombre": "Ñachec", "estado": "ACTIVO"}])
        self.assertIn("Sin cambios", salida)
        self.programa.refresh_from_db()
        self.assertEqual(self.programa.siis_programa_estado, ProgramaSiis.EstadoSiis.ACTIVO)

    def test_catalogo_vacio_no_escribe_nada(self):
        """La Ola 1 decidió al revés que la caracterización (SIIS-06).

        Hasta el 06/10/2026 este test se llamaba
        ``test_catalogo_vacio_marca_todo_desconocido`` y dejaba fijado lo
        contrario: el catálogo vacío marcaba **todo** ``DESCONOCIDO`` y Becas
        quedaba bloqueada entera. Era caracterización explícita, no aprobación
        (RED-32), puesta ahí «para que la Ola 1 lo decida a la vista»: la regla de
        fondo sigue igual —``estado=TODOS`` se pide justamente porque una baja se
        ve como una ausencia—, pero una respuesta vacía ya no es una ausencia, es
        SIIS roto, y el cron de las 04:00 corre sin nadie mirando.

        La ausencia *parcial* se sigue escribiendo sola: eso lo fija
        ``programas.tests.test_siis_catalogo_y_payload.SincronizacionDefensivaTests``.
        """
        with self.assertRaisesMessage(CommandError, "catálogo vacío"):
            self.correr([])

        self.programa.refresh_from_db()
        self.assertEqual(self.programa.siis_programa_estado, ProgramaSiis.EstadoSiis.ACTIVO)
        self.assertIsNone(self.programa.siis_verificado_en)

    def test_dry_run_informa_el_cambio_sin_escribirlo(self):
        salida = self.correr([{"id": 79, "nombre": "Ñachec", "estado": "INACTIVO"}], "--dry-run")

        self.programa.refresh_from_db()
        self.assertEqual(self.programa.siis_programa_estado, ProgramaSiis.EstadoSiis.ACTIVO)
        self.assertIn("[dry-run]", salida)
        self.assertIn("1 programa(s) a actualizar", salida)

    def test_siis_caido_da_commanderror_y_no_toca_ids(self):
        salida = StringIO()
        with patch(
            "programas.services.siis_sync.listar_programas_todos",
            side_effect=SiisCatalogError("SIIS no respondió el catálogo."),
        ):
            with self.assertRaisesMessage(CommandError, "SIIS no respondió el catálogo."):
                call_command("sincronizar_programas_siis", stdout=salida, stderr=salida)

        self.programa.refresh_from_db()
        self.assertEqual(self.programa.siis_programa_estado, ProgramaSiis.EstadoSiis.ACTIVO)
        self.assertEqual(self.programa.siis_programa_id, 79)
        self.assertIsNone(self.programa.siis_verificado_en)
