"""El comando que encadena el circuito completo de alta en SIIS.

Lo que se fija acá es sobre todo lo que el comando **no** deja hacer: arrancar
sin la configuración de pantalla, seguir con el catálogo vacío, o mandar la
corrida grande sin que alguien haya verificado el caso de prueba. Cada una de
esas tres cosas pasó de verdad el 01/10/2026 y costó 4.139 altas con la
localidad equivocada.
"""

from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings

from programas.management.commands.correr_alta_siis import _sentencias
from programas.models import LocalidadSiis, ProvinciaSiis, RequisitoNativo
from programas.tests.test_corregir_datos_siis import (
    _BaseCorreccionTest,
    crear_tabla_localidades,
    crear_tabla_renaper,
)
from programas.tests.test_proceso_masivo import crear_tabla_aprobados_materias

DESTINOS = ("prov_actual", "loc_actual", "barrio_actual", "calle_altura", "est_civil", "prov_nacim", "loc_nacim")


@override_settings(SIIS_API_CLIENT_ID="id-de-prueba", SIIS_API_CLIENT_SECRET="secreto-de-prueba")
class _BaseAltaTest(_BaseCorreccionTest):
    def setUp(self):
        super().setUp()
        # Las tres tablas que carga el organismo con sus .sql.
        crear_tabla_localidades()
        crear_tabla_renaper()
        crear_tabla_aprobados_materias(self.ciudadano.dni)
        # La configuración que en producción se hace desde la pantalla.
        for destino in DESTINOS:
            RequisitoNativo.objects.create(texto=destino, tipo="STRING", destino_siis=destino, segmento=self.segmento)
        self.programa.siis_id_plan_soc = 79
        self.programa.siis_jurid = 28
        self.programa.siis_funcion_id = 4
        self.programa.save()

    def correr(self, *args, con_hijos=False):
        """Corre el orquestador. Por defecto los comandos hijos van mockeados.

        Lo que se prueba acá es el orden y los frenos, no lo que hace cada
        comando —eso tiene sus propios tests—. Además dos de ellos leen
        ``information_schema``, que en SQLite no existe.
        """
        salida = StringIO()
        if con_hijos:
            call_command("correr_alta_siis", "--sin-insumos", *args, stdout=salida, stderr=salida)
            return salida.getvalue()
        with patch("programas.management.commands.correr_alta_siis.call_command") as hijo:
            try:
                call_command("correr_alta_siis", "--sin-insumos", *args, stdout=salida, stderr=salida)
            finally:
                # También cuando corta: hace falta para comprobar hasta dónde llegó.
                self.argumentos = hijo.call_args_list
                self.llamadas = [llamada.args[0] for llamada in hijo.call_args_list]
        return salida.getvalue()


class PrecondicionesTests(_BaseAltaTest):
    def test_sin_destinos_marcados_no_arranca(self):
        """Sin esto el sistema no ve ninguna respuesta y corrige lo que ya estaba bien."""
        RequisitoNativo.objects.filter(destino_siis="loc_actual").update(destino_siis="")

        with self.assertRaises(CommandError) as ctx:
            self.correr("--solo-precondiciones")

        self.assertIn("loc_actual", str(ctx.exception))
        self.assertIn("pantalla", str(ctx.exception))

    def test_sin_ningun_programa_con_identificadores_no_arranca(self):
        from programas.models import ProgramaSiis

        ProgramaSiis.objects.all().update(siis_id_plan_soc=None, siis_funcion_id=None, siis_programa_datos={})

        with self.assertRaises(CommandError) as ctx:
            self.correr("--solo-precondiciones")

        self.assertIn("identificadores", str(ctx.exception))

    def test_un_programa_ajeno_sin_configurar_no_frena_al_que_si_esta(self):
        """Un programa viejo sin identificadores no puede bloquear el alta de otro."""
        from programas.models import ProgramaSiis

        ProgramaSiis.objects.create(nombre="Programa viejo sin configurar", siis_programa_id=999)

        salida = self.correr("--solo-precondiciones")

        self.assertIn("Programa viejo sin configurar", salida)
        self.assertIn("los 7", salida)

    def test_informa_todo_lo_que_falta_de_una_vez(self):
        """Que no haya que correrlo cinco veces para enterarse de cinco cosas."""
        from programas.models import ProgramaSiis

        RequisitoNativo.objects.filter(destino_siis="est_civil").update(destino_siis="")
        ProgramaSiis.objects.all().update(siis_id_plan_soc=None, siis_funcion_id=None, siis_programa_datos={})

        with self.assertRaises(CommandError) as ctx:
            self.correr("--solo-precondiciones")

        self.assertIn("est_civil", str(ctx.exception))
        self.assertIn("identificadores", str(ctx.exception))

    def test_con_todo_puesto_dice_que_se_puede_arrancar(self):
        salida = self.correr("--solo-precondiciones")

        self.assertIn("los 7", salida)

    @override_settings(SIIS_API_CLIENT_ID="", SIIS_API_CLIENT_SECRET="")
    def test_sin_credenciales_no_deja_aplicar(self):
        with self.assertRaises(CommandError) as ctx:
            self.correr("--solo-precondiciones", "--aplicar")

        self.assertIn("SIIS_API_CLIENT_ID", str(ctx.exception))


class OrdenTests(_BaseAltaTest):
    def test_los_pasos_corren_en_el_orden_correcto(self):
        """El catálogo antes de corregir, y corregir antes de mandar."""
        self.correr("--continuar", "--aplicar", "--usuario", self.user.username)

        self.assertEqual(
            self.llamadas,
            [
                "seed_catalogo_siis",
                "completar_casos_renaper",
                "corregir_datos_siis",
                "procesar_casos_siis",  # el caso de prueba
                "procesar_casos_siis",  # la corrida completa
            ],
        )

    def test_en_ensayo_no_hay_caso_de_prueba(self):
        """Sin --aplicar no se manda nada, ni siquiera el caso de verificación."""
        self.correr("--continuar")

        self.assertEqual(self.llamadas.count("procesar_casos_siis"), 1)


class CatalogoVacioTests(_BaseAltaTest):
    def test_corta_si_el_catalogo_quedo_vacio(self):
        """El error del 01/10: sin catálogo, la API devuelve posiciones de lista."""
        LocalidadSiis.objects.all().delete()
        ProvinciaSiis.objects.all().delete()

        with self.assertRaises(CommandError) as ctx:
            self.correr()

        self.assertIn("catálogo", str(ctx.exception).lower())
        self.assertIn("domicilio equivocado", str(ctx.exception))

    def test_no_llega_a_corregir_ni_a_mandar_con_el_catalogo_vacio(self):
        LocalidadSiis.objects.all().delete()
        ProvinciaSiis.objects.all().delete()

        with self.assertRaises(CommandError):
            self.correr("--continuar")

        self.assertNotIn("corregir_datos_siis", self.llamadas)
        self.assertNotIn("procesar_casos_siis", self.llamadas)


class FrenoDelCasoDePruebaTests(_BaseAltaTest):
    def test_sin_continuar_no_llega_a_la_corrida_completa(self):
        salida = self.correr()

        self.assertIn("FRENO", salida)
        self.assertNotIn("PASO 7", salida)

    def test_avisa_que_el_caso_tiene_que_ser_del_interior(self):
        """Resistencia coincide de casualidad: verificar con ella no prueba nada."""
        salida = self.correr()

        self.assertIn("interior", salida)
        self.assertIn("Resistencia", salida)

    def test_con_continuar_llega_al_paso_7(self):
        salida = self.correr("--continuar")

        self.assertIn("PASO 7", salida)


class ParserDeSqlTests(SimpleTestCase):
    """Los ``.sql`` del organismo se ejecutan desde Django: el pod no trae cliente."""

    def test_saltea_el_punto_y_coma_de_un_comentario(self):
        """``DatosPersonas.sql`` tiene uno en su cabecera y partía el archivo mal."""
        sql = "-- Generado el 2026-09-18; 10321 filas\nSELECT 1;\nSELECT 2;"

        self.assertEqual(list(_sentencias(sql)), ["SELECT 1", "SELECT 2"])

    def test_el_punto_y_coma_dentro_de_una_cadena_no_corta(self):
        sql = "INSERT INTO t (x) VALUES ('hola; chau');"

        self.assertEqual(list(_sentencias(sql)), ["INSERT INTO t (x) VALUES ('hola; chau')"])

    def test_dos_guiones_dentro_de_una_cadena_no_son_comentario(self):
        sql = "INSERT INTO t (x) VALUES ('Villa -- Angela');"

        self.assertEqual(list(_sentencias(sql)), ["INSERT INTO t (x) VALUES ('Villa -- Angela')"])

    def test_los_sql_del_repo_se_parten_sin_sentencias_vacias(self):
        """Contra los archivos de verdad, no contra un ejemplo inventado."""
        for archivo in ("Aprobados.sql", "Localidades.sql", "DatosPersonas.sql"):
            ruta = Path(settings.BASE_DIR) / "scripts" / archivo
            if not ruta.exists():
                continue
            with self.subTest(archivo=archivo):
                sentencias = list(_sentencias(ruta.read_text(encoding="utf-8")))
                self.assertTrue(sentencias, f"{archivo} no produjo ninguna sentencia")
                for sentencia in sentencias:
                    self.assertTrue(sentencia.strip(), f"{archivo} produjo una sentencia vacía")
                # La primera tiene que ser SQL de verdad, no un resto de comentarios.
                self.assertRegex(sentencias[0].upper(), r"^(DROP|CREATE|SET|INSERT|SELECT)")


class EnsayoTests(_BaseAltaTest):
    def test_el_ensayo_no_manda_ningun_caso(self):
        salida = self.correr("--continuar")

        self.assertIn("ENSAYO", salida)
        self.assertIn("no se manda ningún caso", salida)

    def test_el_ensayo_no_le_pasa_aplicar_a_ningun_hijo(self):
        """Un --aplicar que se cuele acá manda altas de verdad."""
        self.correr("--continuar")

        for llamada in self.argumentos:
            self.assertNotIn("--aplicar", llamada.args, f"{llamada.args[0]} recibió --aplicar en un ensayo")

    def test_con_aplicar_los_hijos_lo_reciben(self):
        self.correr("--continuar", "--aplicar", "--usuario", self.user.username)

        con_aplicar = [llamada.args[0] for llamada in self.argumentos if "--aplicar" in llamada.args]
        self.assertIn("completar_casos_renaper", con_aplicar)
        self.assertIn("corregir_datos_siis", con_aplicar)
        self.assertIn("procesar_casos_siis", con_aplicar)


class DestinoTests(_BaseAltaTest):
    """``--destino tabla`` no llama a SIIS, así que no hay nada que frenar."""

    def test_con_destino_tabla_no_hay_caso_de_prueba_ni_freno(self):
        salida = self.correr("--destino", "tabla", "--aplicar", "--usuario", self.user.username)

        self.assertIn("tabla intermedia", salida)
        self.assertNotIn("FRENO", salida)
        self.assertEqual(self.llamadas.count("procesar_casos_siis"), 1)

    def test_el_destino_le_llega_al_comando_que_manda(self):
        self.correr("--destino", "tabla", "--aplicar", "--usuario", self.user.username)

        envio = [llamada for llamada in self.argumentos if llamada.args[0] == "procesar_casos_siis"][-1]
        self.assertIn("tabla", envio.args)

    def test_por_defecto_sigue_yendo_a_siis_y_frena(self):
        salida = self.correr("--aplicar", "--usuario", self.user.username)

        self.assertIn("FRENO", salida)


class TandasTests(_BaseAltaTest):
    """El paso 7 manda de a tandas: con el total de una, el pod se queda sin memoria."""

    def _totales(self):
        """El ``--total`` de cada llamada a ``procesar_casos_siis`` del paso 7."""
        totales = []
        for llamada in self.argumentos:
            # El caso de prueba del paso 6 tambien llama al comando, pero sin
            # --destino: asi se distingue de las tandas del paso 7.
            if llamada.args[0] != "procesar_casos_siis" or "--destino" not in llamada.args:
                continue
            totales.append(int(llamada.args[llamada.args.index("--total") + 1]))
        return totales

    @patch("programas.management.commands.correr_alta_siis.TANDA", 2)
    @patch("programas.management.commands.correr_alta_siis.Command._cuantos_quedan")
    def test_nunca_le_pide_mas_de_una_tanda(self, quedan):
        quedan.side_effect = [5, 3, 1, 0]

        self.correr("--continuar", "--aplicar", "--usuario", self.user.username)

        self.assertTrue(self._totales())
        self.assertTrue(all(t <= 2 for t in self._totales()), self._totales())

    @patch("programas.management.commands.correr_alta_siis.TANDA", 2)
    @patch("programas.management.commands.correr_alta_siis.Command._cuantos_quedan")
    def test_corta_si_la_cuenta_deja_de_bajar(self, quedan):
        """Lo que queda no se puede mandar: insistir sería un lazo infinito."""
        quedan.side_effect = [4, 4, 4, 4, 4, 4]

        salida = self.correr("--continuar", "--aplicar", "--usuario", self.user.username)

        self.assertIn("no bajan", salida)
        self.assertEqual(len(self._totales()), 1)

    @patch("programas.management.commands.correr_alta_siis.Command._cuantos_quedan", return_value=9000)
    def test_en_ensayo_una_vuelta_alcanza(self, _quedan):
        self.correr("--continuar")

        self.assertEqual(len(self._totales()), 1)
