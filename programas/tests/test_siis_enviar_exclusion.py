"""La lista de exclusión ``siis_enviar``: quién NO se manda a SIIS.

El nombre dice «enviar» y la semántica es la contraria —lo eligió el PM—, así
que acá se fija lo único que importa: quien figura en esa tabla no llega a SIIS
por ningún camino. Ni como candidato nuevo, ni drenando la tabla intermedia,
ni aunque lo hayan agregado a la lista después de quedar guardado.

Y la confirmación: un alta en SIIS no se deshace desde acá, así que el total a
mandar tiene que pasar por los ojos de alguien antes de salir.
"""

from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import override_settings

from programas.models import AltaIntermediaSIIS, EnvioSIIS, Formulario
from programas.services import proceso_masivo
from programas.services.siis_envio import (
    Catalogos,
    guardar_en_tabla_intermedia,
    sincronizar_tabla_intermedia,
)
from programas.tests.test_siis_envio import _catalogo_falso, _ConPayloadCompleto

TABLA = proceso_masivo.TABLA_SIIS_ENVIAR


def crear_tabla_siis_enviar(*dnis):
    """La tabla que carga el PM: una sola columna ``dni``."""
    with connection.cursor() as cur:
        cur.execute(f"CREATE TABLE {TABLA} (dni VARCHAR(20))")
        for dni in dnis:
            cur.execute(f"INSERT INTO {TABLA} (dni) VALUES (%s)", [str(dni)])


def _catalogos_falsos():
    return Catalogos(cargar=_catalogo_falso)


def _alta_ok(payload):
    return {"success": True, "siis_id": 999, "data": {"ok": True}}


class _BaseExclusionTest(_ConPayloadCompleto):
    def setUp(self):
        super().setUp()
        self.formulario.estado = Formulario.Estado.APROBADO
        self.formulario.save(update_fields=["estado"])

    def candidatos(self):
        return set(proceso_masivo.candidatos(filtrar_materias=False).values_list("pk", flat=True))


class LecturaDeLaTablaTests(_BaseExclusionTest):
    def test_sin_la_tabla_no_excluye_a_nadie(self):
        """Es una lista opcional: faltar deja todo como antes de que existiera."""
        self.assertEqual(proceso_masivo.dnis_a_no_enviar(), set())
        self.assertIn(self.formulario.pk, self.candidatos())

    def test_la_tabla_vacia_tampoco(self):
        crear_tabla_siis_enviar()

        self.assertEqual(proceso_masivo.dnis_a_no_enviar(), set())
        self.assertIn(self.formulario.pk, self.candidatos())

    def test_cruza_aunque_el_dni_venga_con_ceros_adelante(self):
        """La planilla sale de Excel, que se los come; la base puede tenerlos."""
        crear_tabla_siis_enviar(f"0{self.ciudadano.dni}")

        self.assertNotIn(self.formulario.pk, self.candidatos())

    def test_el_conteo_de_personas_no_cuenta_las_variantes(self):
        """``dnis_a_no_enviar`` devuelve hasta tres formas del mismo documento."""
        crear_tabla_siis_enviar("20301234", "7654321")

        self.assertEqual(len(proceso_masivo.dnis_crudos_a_no_enviar()), 2)
        self.assertGreater(len(proceso_masivo.dnis_a_no_enviar()), 2)


class NoLlegaPorNingunCaminoTests(_BaseExclusionTest):
    def setUp(self):
        super().setUp()
        crear_tabla_siis_enviar(self.ciudadano.dni)

    def test_deja_de_ser_candidato(self):
        self.assertNotIn(self.formulario.pk, self.candidatos())

    def test_tampoco_entra_a_la_tabla_intermedia(self):
        """La tabla local es la antesala de SIIS: dejarlo ahí sería dejarlo en camino."""
        pendientes = proceso_masivo.candidatos(
            filtrar_materias=False, destino=proceso_masivo.DESTINO_TABLA
        ).values_list("pk", flat=True)

        self.assertNotIn(self.formulario.pk, set(pendientes))

    def test_el_que_ya_estaba_guardado_no_se_sincroniza(self):
        """Lo agregaron a la lista después de quedar guardado: igual no sale."""
        with connection.cursor() as cur:
            cur.execute(f"DELETE FROM {TABLA}")
        guardar_en_tabla_intermedia(self.formulario, self.user, catalogos=self.cat)
        with connection.cursor() as cur:
            cur.execute(f"INSERT INTO {TABLA} (dni) VALUES (%s)", [str(self.ciudadano.dni)])

        with patch("programas.services.siis_envio.cargar_beneficiario") as api:
            cuenta = sincronizar_tabla_intermedia(self.user)

        api.assert_not_called()
        self.assertEqual(cuenta["excluidas"], 1)
        self.assertFalse(AltaIntermediaSIIS.objects.get().sincronizado)
        self.assertFalse(EnvioSIIS.objects.exists())

    def test_el_que_no_esta_en_la_lista_sigue_saliendo(self):
        """La exclusión tiene que ser quirúrgica, no frenar la corrida entera."""
        with connection.cursor() as cur:
            cur.execute(f"DELETE FROM {TABLA}")
            cur.execute(f"INSERT INTO {TABLA} (dni) VALUES ('99999999')")
        guardar_en_tabla_intermedia(self.formulario, self.user, catalogos=self.cat)

        with patch("programas.services.siis_envio.cargar_beneficiario", _alta_ok):
            cuenta = sincronizar_tabla_intermedia(self.user)

        self.assertEqual(cuenta["altas"], 1)
        self.assertEqual(cuenta["excluidas"], 0)


@override_settings(SIIS_API_CLIENT_ID="id-de-prueba", SIIS_API_CLIENT_SECRET="secreto-de-prueba")
class ConfirmacionTests(_BaseExclusionTest):
    def correr(self, *args, responde=None):
        salida = StringIO()
        with patch("programas.management.commands.procesar_casos_siis.Catalogos", _catalogos_falsos):
            with patch("programas.management.commands.procesar_casos_siis.sys.stdin") as entrada:
                entrada.isatty.return_value = responde is not None
                with patch("builtins.input", return_value=responde or ""):
                    call_command(
                        "procesar_casos_siis",
                        "--sin-filtro-materias",
                        "--solo-enviar",
                        *args,
                        stdout=salida,
                        stderr=salida,
                    )
        return salida.getvalue()

    def test_dice_cuantos_va_a_enviar_y_pregunta(self):
        with patch("programas.services.siis_envio.cargar_beneficiario", _alta_ok):
            salida = self.correr("--aplicar", "--usuario", self.user.username, responde="y")

        self.assertIn("Esta corrida puede mandar a SIIS", salida)
        self.assertIn("caso(s) nuevos como máximo", salida)
        self.assertTrue(EnvioSIIS.objects.filter(estado=EnvioSIIS.Estado.ENVIADO).exists())

    def test_si_contesta_que_no_no_manda_nada(self):
        with patch("programas.services.siis_envio.cargar_beneficiario") as api:
            salida = self.correr("--aplicar", "--usuario", self.user.username, responde="n")

        api.assert_not_called()
        self.assertIn("Cancelado", salida)
        self.assertFalse(EnvioSIIS.objects.exists())

    def test_enter_vacio_es_que_no(self):
        """El default tiene que ser no mandar: lo que entra a SIIS no se saca."""
        with patch("programas.services.siis_envio.cargar_beneficiario") as api:
            self.correr("--aplicar", "--usuario", self.user.username, responde="")

        api.assert_not_called()

    def test_con_si_no_pregunta(self):
        with patch("programas.services.siis_envio.cargar_beneficiario", _alta_ok):
            salida = self.correr("--si", "--aplicar", "--usuario", self.user.username, responde=None)

        self.assertIn("no se pregunta", salida)
        self.assertTrue(EnvioSIIS.objects.filter(estado=EnvioSIIS.Estado.ENVIADO).exists())

    def test_sin_terminal_y_sin_si_corta(self):
        """Un cron no puede contestar: que la pregunta no desaparezca ahí."""
        with self.assertRaises(CommandError) as ctx:
            self.correr("--aplicar", "--usuario", self.user.username, responde=None)

        self.assertIn("--si", str(ctx.exception))
        self.assertFalse(EnvioSIIS.objects.exists())

    def test_guardar_en_la_tabla_no_pregunta(self):
        """Es reversible: la pregunta es para lo que no se puede deshacer."""
        salida = self.correr("--destino", "tabla", "--aplicar", "--usuario", self.user.username, responde=None)

        self.assertNotIn("¿Querés enviar?", salida)
        self.assertEqual(AltaIntermediaSIIS.objects.count(), 1)

    def test_informa_la_lista_aunque_este_vacia(self):
        """«No se excluyó a nadie» tiene que ser una afirmación, no un silencio."""
        salida = self.correr("--destino", "tabla", "--aplicar", "--usuario", self.user.username, responde=None)

        self.assertIn("vacía o inexistente", salida)

    def test_informa_cuantos_excluye(self):
        crear_tabla_siis_enviar("11111111", "22222222")

        salida = self.correr("--destino", "tabla", "--aplicar", "--usuario", self.user.username, responde=None)

        self.assertIn("2 DNI que NO se mandan a SIIS", salida)


class NombreDeLaTablaTests(_BaseExclusionTest):
    """El PM la crea a mano y el nombre no coincide por accidente.

    La de testing se creó como ``SiisEnviar``; buscar ``siis_enviar`` no la
    encontraba --no es la capitalización, es el guion bajo-- y la lista salía
    vacía sin un solo error. Para algo cuyo trabajo es frenar envíos, ese
    silencio es la peor forma posible de fallar.
    """

    def _tabla(self, nombre, columna="DNI"):
        with connection.cursor() as cur:
            cur.execute(f"CREATE TABLE {nombre} ({columna} INT)")
            cur.execute(f"INSERT INTO {nombre} ({columna}) VALUES (%s)", [int(self.ciudadano.dni)])

    def test_la_encuentra_como_SiisEnviar(self):
        self._tabla("SiisEnviar")

        self.assertEqual(proceso_masivo.dnis_crudos_a_no_enviar(), {str(int(self.ciudadano.dni))})
        self.assertNotIn(self.formulario.pk, self.candidatos())

    def test_la_encuentra_como_siis_enviar(self):
        self._tabla("siis_enviar")

        self.assertNotIn(self.formulario.pk, self.candidatos())

    def test_una_tabla_con_otro_nombre_no_cuenta(self):
        """Mejor no excluir a nadie que excluir por una tabla que no es la lista."""
        self._tabla("otra_lista_cualquiera")

        self.assertEqual(proceso_masivo.dnis_crudos_a_no_enviar(), set())
        self.assertIn(self.formulario.pk, self.candidatos())


@override_settings(SIIS_API_CLIENT_ID="id-de-prueba", SIIS_API_CLIENT_SECRET="secreto-de-prueba")
class ConfirmarAntesDeDrenarTests(_BaseExclusionTest):
    """La pregunta tiene que ir ANTES de vaciar la tabla intermedia.

    El drenaje manda a SIIS y mandar no se deshace. Con la pregunta al final
    --como salió la primera versión-- contestar «no» cancelaba los casos nuevos
    pero las altas guardadas ya habían salido: en testing eran 1.295 contra la
    API de producción. Se detectó el 06/10/2026 antes de correrlo.
    """

    def correr(self, responde):
        salida = StringIO()
        guardar_en_tabla_intermedia(self.formulario, self.user, catalogos=self.cat)
        with patch("programas.management.commands.procesar_casos_siis.sys.stdin") as entrada:
            entrada.isatty.return_value = True
            with patch("builtins.input", return_value=responde):
                call_command(
                    "procesar_casos_siis",
                    "--sin-filtro-materias",
                    "--solo-enviar",
                    "--destino",
                    "siis",
                    "--aplicar",
                    "--usuario",
                    self.user.username,
                    stdout=salida,
                    stderr=salida,
                )
        return salida.getvalue()

    def test_contestar_que_no_tampoco_drena_la_tabla(self):
        with patch("programas.services.siis_envio.cargar_beneficiario") as api:
            salida = self.correr("n")

        api.assert_not_called()
        self.assertIn("Cancelado", salida)
        self.assertFalse(AltaIntermediaSIIS.objects.get().sincronizado)
        self.assertFalse(EnvioSIIS.objects.exists())

    def test_la_pregunta_dice_cuantas_guardadas_van_primero(self):
        """El número de la tabla intermedia es exacto y es el que más importa."""
        with patch("programas.services.siis_envio.cargar_beneficiario") as api:
            salida = self.correr("n")

        api.assert_not_called()
        self.assertIn("1 alta(s) guardada(s) en la tabla intermedia (salen primero)", salida)

    def test_contestar_que_si_drena(self):
        with patch("programas.services.siis_envio.cargar_beneficiario", _alta_ok):
            self.correr("y")

        self.assertTrue(AltaIntermediaSIIS.objects.get().sincronizado)

    def test_las_excluidas_no_se_cuentan_en_la_pregunta(self):
        """Si la lista las frena, no son altas que vayan a salir."""
        with connection.cursor() as cur:
            cur.execute(f"CREATE TABLE {TABLA} (dni VARCHAR(20))")
            cur.execute(f"INSERT INTO {TABLA} (dni) VALUES (%s)", [str(self.ciudadano.dni)])

        with patch("programas.services.siis_envio.cargar_beneficiario") as api:
            salida = self.correr("n")

        api.assert_not_called()
        self.assertIn("0 alta(s) guardada(s) en la tabla intermedia", salida)
