"""El drenaje de la tabla intermedia respeta ``--total``, ``--lote`` y ``--pausa`` (Cambio 403).

``procesar_casos_siis --destino siis`` empieza vaciando la tabla local. Antes lo
hacía de una vez, sin tope ni pausa: en PRD, con 1.800 filas, SIIS cortó por
exceso de pedidos (429) y cada corte dejó un envío ``INCIERTO``, que no se
reintenta. Acá se fija que ahora va de a lotes, con pausa, que frena ante lo que
una persona tiene que mirar y que, si gastó todo el ``--total``, no sigue con
casos nuevos.
"""

from datetime import date
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import override_settings

from legajos.models import Ciudadano
from programas.models import AltaIntermediaSIIS, EnvioSIIS, Formulario
from programas.services.siis_envio import sincronizar_tabla_intermedia
from programas.tests.test_siis_enviar_exclusion import _alta_ok, _BaseExclusionTest, _catalogos_falsos

SIIS = "programas.services.siis_envio.cargar_beneficiario"
SLEEP = "programas.management.commands.procesar_casos_siis.time.sleep"


def _incierto(payload):
    """Lo que deja un timeout o un 429 en el alta: no se sabe si llegó."""
    return {"success": False, "codigo": "RESULTADO_INCIERTO", "resultado": "INCIERTO", "reintentable": False}


def _error_tecnico(payload):
    return {"success": False, "codigo": "ERROR_TECNICO", "resultado": "NO_ENVIADO", "reintentable": True}


@override_settings(SIIS_API_CLIENT_ID="id-de-prueba", SIIS_API_CLIENT_SECRET="secreto-de-prueba")
class DrenajePorLotesTests(_BaseExclusionTest):
    def _altas(self, cuantas):
        for i in range(cuantas):
            ciudadano = Ciudadano.objects.create(
                dni=f"4100000{i}", nombre=f"N{i}", apellido=f"A{i}", fecha_nacimiento=date(2000, 1, 1), genero="M"
            )
            formulario = Formulario.objects.create(
                relevamiento=self.relevamiento, ciudadano=ciudadano, estado=Formulario.Estado.APROBADO
            )
            AltaIntermediaSIIS.objects.create(formulario=formulario, tdoc=1, dni=int(ciudadano.dni))

    def pendientes(self):
        return AltaIntermediaSIIS.objects.filter(sincronizado=False).count()

    def correr(self, *args, api=_alta_ok):
        salida = StringIO()
        with (
            patch("programas.management.commands.procesar_casos_siis.Catalogos", _catalogos_falsos),
            patch(SIIS, side_effect=api) as llamadas,
            patch(SLEEP) as dormir,
        ):
            call_command(
                "procesar_casos_siis",
                "--sin-filtro-materias",
                "--si",
                "--destino",
                "siis",
                *args,
                stdout=salida,
                stderr=salida,
            )
        self.llamadas, self.dormir = llamadas, dormir
        return salida.getvalue()

    def test_respeta_el_total(self):
        self._altas(5)

        self.correr("--aplicar", "--total", "3", "--lote", "2")

        self.assertEqual(self.llamadas.call_count, 3)
        self.assertEqual(self.pendientes(), 2)

    def test_respeta_el_lote_y_duerme_la_pausa_entre_lotes(self):
        self._altas(5)

        self.correr("--aplicar", "--total", "5", "--lote", "2", "--pausa", "60")

        self.assertEqual(self.pendientes(), 0)
        self.assertEqual(self.llamadas.call_count, 5)
        # 3 lotes (2, 2, 1): la pausa va entre lotes, no después del último.
        self.assertEqual([c.args[0] for c in self.dormir.call_args_list], [60.0, 60.0])

    def test_cada_llamada_al_servicio_lleva_el_limite_del_lote(self):
        self._altas(5)

        with patch(
            "programas.management.commands.procesar_casos_siis.sincronizar_tabla_intermedia",
            wraps=sincronizar_tabla_intermedia,
        ) as servicio:
            self.correr("--aplicar", "--total", "5", "--lote", "2")

        self.assertEqual([c.kwargs["limite"] for c in servicio.call_args_list], [2, 2, 1])

    def test_si_el_drenaje_gasta_el_total_no_sigue_con_casos_nuevos(self):
        self._altas(2)
        with patch("programas.management.commands.procesar_casos_siis.proceso_masivo.candidatos") as candidatos:
            salida = self.correr("--aplicar", "--total", "2", "--lote", "2")

        candidatos.assert_not_called()
        self.assertIn("no se sigue con casos nuevos", salida)

    def test_frena_ante_un_error_y_no_manda_los_lotes_siguientes(self):
        self._altas(4)
        respuestas = iter([_alta_ok, _error_tecnico])

        def api(payload):
            return next(respuestas)(payload)

        salida = self.correr("--aplicar", "--total", "4", "--lote", "2", "--pausa", "5", api=api)

        self.assertIn("FRENO en el lote 1", salida)
        self.assertEqual(self.llamadas.call_count, 2)
        self.dormir.assert_not_called()
        self.assertEqual(self.pendientes(), 3)

    def test_frena_ante_un_envio_incierto_y_remite_a_conciliar(self):
        self._altas(4)

        salida = self.correr("--aplicar", "--total", "4", "--lote", "2", api=_incierto)

        self.assertIn("FRENO en el lote 1", salida)
        self.assertIn("conciliar_envios_siis", salida)
        self.assertEqual(self.llamadas.call_count, 2)
        self.assertTrue(EnvioSIIS.objects.filter(estado=EnvioSIIS.Estado.INCIERTO).exists())

    def test_frena_si_la_fila_se_cerro_por_un_envio_vigente(self):
        """No puede decir «0 pendientes» sobre un alta que está por conciliar."""
        self._altas(3)
        alta = AltaIntermediaSIIS.objects.order_by("pk").first()
        EnvioSIIS.objects.create(
            formulario=alta.formulario, estado=EnvioSIIS.Estado.INCIERTO, documento=str(alta.dni), vigente=True
        )

        salida = self.correr("--aplicar", "--total", "3", "--lote", "2")

        self.assertIn("FRENO en el lote 1", salida)
        self.assertIn("ya tenía un envío vigente", salida)
        self.assertIn("conciliar_envios_siis", salida)

    def test_el_ensayo_no_manda_y_dice_cuantos_lotes_haria(self):
        self._altas(5)

        salida = self.correr("--total", "5", "--lote", "2", "--pausa", "60")

        self.llamadas.assert_not_called()
        self.dormir.assert_not_called()
        self.assertEqual(self.pendientes(), 5)
        self.assertIn("en 3 lote(s) de 2", salida)

    def test_el_servicio_cuenta_los_inciertos_y_los_vigentes(self):
        self._altas(2)
        alta = AltaIntermediaSIIS.objects.order_by("pk").first()
        EnvioSIIS.objects.create(
            formulario=alta.formulario, estado=EnvioSIIS.Estado.EN_PROCESO, documento=str(alta.dni), vigente=True
        )

        with patch(SIIS, _incierto):
            cuenta = sincronizar_tabla_intermedia(self.user)

        self.assertEqual(cuenta["vigentes"], 1)
        self.assertEqual(cuenta["inciertos"], 1)
        self.assertEqual(cuenta["errores"], 0)
