"""El alta que se guarda de este lado en vez de mandarse a SIIS.

Dos destinos excluyentes, y una regla que los ata: una corrida con destino SIIS
**vacía primero la tabla local**. Sin eso un alta guardada se quedaría ahí para
siempre, que es exactamente lo que el pedido quería evitar.
"""

from datetime import date
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import override_settings

from programas.models import AltaIntermediaSIIS, EnvioSIIS, Formulario
from programas.services import proceso_masivo
from programas.services.siis_envio import (
    DESTINO_TABLA,
    Catalogos,
    guardar_en_tabla_intermedia,
    payload_de,
    sincronizar_tabla_intermedia,
)
from programas.tests.test_siis_envio import _catalogo_falso, _ConPayloadCompleto


def _catalogos_falsos():
    """``Catalogos`` con el catálogo de mentira.

    No alcanza con parchear ``siis_envio.catalogo``: ``Catalogos.__init__`` lo
    toma como valor por defecto de un argumento, que se evalúa al importar el
    módulo. Hay que inyectar la clase donde el comando la construye.
    """
    return Catalogos(cargar=_catalogo_falso)


def _alta_ok(payload):
    return {"success": True, "siis_id": 999, "data": {"ok": True}}


def _rechazo(payload):
    return {"success": False, "codigo": "DATOS_INVALIDOS", "reintentable": False, "detalles": {"dni": ["mal"]}}


class _BaseTablaTest(_ConPayloadCompleto):
    """Hereda el caso con el payload completo: sin respuestas no hay alta que guardar."""

    def setUp(self):
        super().setUp()
        self.formulario.estado = Formulario.Estado.APROBADO
        self.formulario.save(update_fields=["estado"])

    def guardar(self):
        return guardar_en_tabla_intermedia(self.formulario, self.user, catalogos=self.cat)


class GuardarEnLaTablaTests(_BaseTablaTest):
    def test_guarda_el_alta_sin_llamar_a_siis(self):
        with patch("programas.services.siis_envio.cargar_beneficiario") as api:
            alta, envio = self.guardar()

        api.assert_not_called()
        self.assertIsNotNone(alta)
        self.assertIsNone(envio)
        self.assertEqual(AltaIntermediaSIIS.objects.count(), 1)

    def test_no_deja_envio_registrado(self):
        """El caso todavía no está en SIIS: no puede figurar como informado."""
        self.guardar()

        self.assertFalse(EnvioSIIS.objects.exists())

    def test_arranca_sin_sincronizar(self):
        alta, _ = self.guardar()

        self.assertFalse(alta.sincronizado)
        self.assertIsNone(alta.sincronizado_en)

    def test_los_campos_son_columnas_no_un_json(self):
        """El organismo la consulta por SQL: un JSON no le sirve."""
        alta, _ = self.guardar()

        self.assertEqual(alta.dni, int(self.ciudadano.dni))
        self.assertEqual(alta.apellido, self.ciudadano.apellido.upper())
        self.assertIsInstance(alta.fecha_nacim, date)

    def test_volver_a_guardarlo_pisa_la_fila(self):
        self.guardar()
        self.guardar()

        self.assertEqual(AltaIntermediaSIIS.objects.count(), 1)

    def test_el_caso_ya_informado_no_se_guarda(self):
        EnvioSIIS.objects.create(
            formulario=self.formulario, estado=EnvioSIIS.Estado.ENVIADO, documento=str(self.ciudadano.dni)
        )

        alta, envio = self.guardar()

        self.assertIsNone(alta)
        self.assertFalse(AltaIntermediaSIIS.objects.exists())


class SincronizarTests(_BaseTablaTest):
    def test_manda_lo_guardado_y_marca_el_flag(self):
        alta, _ = self.guardar()

        with patch("programas.services.siis_envio.cargar_beneficiario", _alta_ok):
            cuenta = sincronizar_tabla_intermedia(self.user)

        alta.refresh_from_db()
        self.assertEqual(cuenta["altas"], 1)
        self.assertTrue(alta.sincronizado)
        self.assertIsNotNone(alta.sincronizado_en)
        self.assertEqual(alta.envio.estado, EnvioSIIS.Estado.ENVIADO)

    def test_manda_el_payload_guardado_no_uno_recalculado(self):
        """Es lo que alguien revisó: cambiar el caso después no lo cambia."""
        self.guardar()
        self.ciudadano.apellido = "OTRO APELLIDO"
        self.ciudadano.save(update_fields=["apellido"])
        mandados = []

        def espiar(payload):
            mandados.append(payload)
            return _alta_ok(payload)

        with patch("programas.services.siis_envio.cargar_beneficiario", espiar):
            sincronizar_tabla_intermedia(self.user)

        self.assertNotEqual(mandados[0]["apellido"], "OTRO APELLIDO")

    def test_lo_ya_sincronizado_no_se_vuelve_a_mandar(self):
        self.guardar()
        with patch("programas.services.siis_envio.cargar_beneficiario", _alta_ok):
            sincronizar_tabla_intermedia(self.user)

        with patch("programas.services.siis_envio.cargar_beneficiario") as api:
            cuenta = sincronizar_tabla_intermedia(self.user)

        api.assert_not_called()
        self.assertEqual(cuenta["altas"], 0)

    def test_un_rechazo_deja_la_fila_pendiente(self):
        """Se corrige y se reintenta; no se pierde."""
        alta, _ = self.guardar()

        with patch("programas.services.siis_envio.cargar_beneficiario", _rechazo):
            cuenta = sincronizar_tabla_intermedia(self.user)

        alta.refresh_from_db()
        self.assertEqual(cuenta["rechazadas"], 1)
        self.assertFalse(alta.sincronizado)

    def test_si_entro_por_otro_camino_la_fila_se_cierra(self):
        alta, _ = self.guardar()
        EnvioSIIS.objects.create(
            formulario=self.formulario, estado=EnvioSIIS.Estado.ENVIADO, documento=str(self.ciudadano.dni)
        )

        with patch("programas.services.siis_envio.cargar_beneficiario") as api:
            sincronizar_tabla_intermedia(self.user)

        alta.refresh_from_db()
        api.assert_not_called()
        self.assertTrue(alta.sincronizado)

    def test_el_payload_no_lleva_los_campos_vacios(self):
        alta, _ = self.guardar()

        payload = payload_de(alta)

        self.assertNotIn("dni_apoderado", payload)  # titular adulto: el apoderado no viaja
        self.assertEqual(payload["fecha_nacim"], alta.fecha_nacim.isoformat())


class DestinoEnElProcesoMasivoTests(_BaseTablaTest):
    def test_con_destino_tabla_no_se_llama_a_la_api(self):
        cuenta = proceso_masivo.Cuenta()

        with patch("programas.services.siis_envio.cargar_beneficiario") as api:
            proceso_masivo.procesar_caso(
                self.formulario, self.user, self.cat, cuenta, solo_enviar=True, destino=DESTINO_TABLA
            )

        api.assert_not_called()
        self.assertEqual(cuenta.guardadas, 1)
        self.assertEqual(cuenta.altas, 0)

    def test_el_caso_guardado_sigue_siendo_candidato(self):
        """Todavía no está en SIIS: la corrida con destino siis lo tiene que agarrar."""
        cuenta = proceso_masivo.Cuenta()
        proceso_masivo.procesar_caso(
            self.formulario, self.user, self.cat, cuenta, solo_enviar=True, destino=DESTINO_TABLA
        )

        pendientes = proceso_masivo.candidatos(filtrar_materias=False).values_list("pk", flat=True)

        self.assertIn(self.formulario.pk, set(pendientes))


@override_settings(SIIS_API_CLIENT_ID="id-de-prueba", SIIS_API_CLIENT_SECRET="secreto-de-prueba")
class ComandoTests(_BaseTablaTest):
    def correr(self, *args):
        salida = StringIO()
        with patch("programas.management.commands.procesar_casos_siis.Catalogos", _catalogos_falsos):
            call_command("procesar_casos_siis", "--sin-filtro-materias", *args, stdout=salida, stderr=salida)
        return salida.getvalue()

    def test_avisa_que_no_llama_a_siis(self):
        salida = self.correr("--destino", "tabla")

        self.assertIn("NO se llama a SIIS", salida)

    def test_con_destino_siis_vacia_la_tabla_primero(self):
        self.guardar()

        with patch("programas.services.siis_envio.cargar_beneficiario", _alta_ok):
            salida = self.correr("--destino", "siis", "--aplicar", "--usuario", self.user.username)

        self.assertIn("Tabla intermedia: 1 alta", salida)
        self.assertIn("Van primero", salida)
        self.assertTrue(AltaIntermediaSIIS.objects.get().sincronizado)

    def test_en_ensayo_no_vacia_nada(self):
        alta, _ = self.guardar()

        salida = self.correr("--destino", "siis")

        alta.refresh_from_db()
        self.assertIn("ensayo", salida.lower())
        self.assertFalse(alta.sincronizado)


@override_settings(SIIS_API_CLIENT_ID="id-de-prueba", SIIS_API_CLIENT_SECRET="secreto-de-prueba")
class NoReprocesaLoGuardadoTests(_BaseTablaTest):
    """Una segunda vuelta no puede volver a agarrar lo que ya está en la tabla.

    Guardar no deja ``EnvioSIIS`` --el caso no está en SIIS-- así que el filtro
    por destino es lo único que lo saca de los candidatos. Sin él, correr el
    comando diez veces deja la tabla clavada en el tamaño de la primera tanda y
    cada vuelta prevalida de nuevo contra SIIS para nada. Pasó el 01/10/2026: la
    exclusión estaba escrita en ``candidatos()`` y el comando nunca le pasaba el
    destino.
    """

    def correr(self):
        salida = StringIO()
        with patch("programas.management.commands.procesar_casos_siis.Catalogos", _catalogos_falsos):
            call_command(
                "procesar_casos_siis",
                "--sin-filtro-materias",
                # Sin --solo-enviar el comando prevalida contra SIIS de verdad.
                "--solo-enviar",
                "--destino",
                "tabla",
                "--aplicar",
                "--usuario",
                self.user.username,
                stdout=salida,
                stderr=salida,
            )
        return salida.getvalue()

    def test_la_segunda_vuelta_no_lo_vuelve_a_procesar(self):
        self.correr()
        self.assertEqual(AltaIntermediaSIIS.objects.count(), 1)

        salida = self.correr()

        self.assertIn("No hay casos que procesar", salida)
        self.assertEqual(AltaIntermediaSIIS.objects.count(), 1)

    def test_el_filtro_por_destino_le_llega_a_candidatos(self):
        self.guardar()

        pendientes = proceso_masivo.candidatos(filtrar_materias=False, destino=DESTINO_TABLA)

        self.assertNotIn(self.formulario.pk, set(pendientes.values_list("pk", flat=True)))

    def test_con_destino_siis_el_guardado_sigue_siendo_candidato(self):
        """Tiene que poder sincronizarse: ahí sí vuelve a entrar."""
        self.guardar()

        pendientes = proceso_masivo.candidatos(filtrar_materias=False)

        self.assertIn(self.formulario.pk, set(pendientes.values_list("pk", flat=True)))
