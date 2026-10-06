"""Catálogo de SIIS, respuestas raras y prevalidación del apoderado (Ola 1, PR 4).

Tres fichas independientes de la auditoría de octubre de 2026 que comparten una
misma forma: el sistema le cree a SIIS sin mirar qué le llegó.

* **SIIS-06** — ``sincronizar_programas_siis`` corre a las 04:00 y marca
  ``DESCONOCIDO`` todo programa que no aparezca en el catálogo, porque una baja
  en SIIS se ve exactamente así: como una ausencia. El costo era que un catálogo
  vacío por un error del servicio dejaba **todos** los programas bloqueados, y
  Becas entera con ellos, sin que nadie se enterara hasta la mañana siguiente.
* **SIIS-11** — un cuerpo JSON que no es un objeto (``[]``, ``"OK"``) reventaba
  con ``AttributeError`` sin capturar: en el masivo cortaba la corrida y al
  rechazar un caso daba 500.
* **SIIS-12** — el payload no miraba al apoderado: el Cambio 98 midió 265
  rechazos de SIIS por apoderado menor o con fecha futura y 448 casos con el
  propio alumno cargado como apoderado. Se corrigieron los datos, no el payload,
  así que el próximo caso igual sale a SIIS para que SIIS lo rechace.
"""

import uuid
from datetime import date, timedelta
from io import StringIO
from unittest.mock import Mock, patch

from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from programas.models import ProgramaSiis, ValidacionSIS
from programas.services import siis as siis_mod
from programas.services.siis import ESTADO_DESCONOCIDO, PROGRAMAS_TODOS_CACHE_KEY, TOKEN_CACHE_KEY, SiisCatalogError
from programas.services.siis_envio import armar_payload
from programas.services.siis_sync import sincronizar_estado_programas
from programas.services.validacion_siis import validar_formulario_en_siis
from programas.tests.test_siis_envio import _ConPayloadCompleto


def _programa_siis(id_remoto, estado=ProgramaSiis.EstadoSiis.ACTIVO):
    return ProgramaSiis.objects.create(
        nombre=f"Programa {id_remoto}",
        siis_programa_id=id_remoto,
        siis_programa_datos={"id": id_remoto},
        siis_programa_estado=estado,
    )


def _del_catalogo(*ids):
    return [{"id": pk, "nombre": f"Programa {pk}", "estado": "ACTIVO"} for pk in ids]


class SincronizacionDefensivaTests(TestCase):
    """SIIS-06: una ausencia masiva se parece más a un error que a una baja.

    La regla no cambia —un programa ausente del catálogo completo está dado de
    baja y queda bloqueado—; lo que cambia es que deja de aplicarse a ciegas. Un
    catálogo vacío no se escribe nunca, y una ausencia que alcanza a todos los
    programas vinculados (o a más de la mitad) necesita que alguien la confirme
    con ``--forzar``. El umbral es el default de **D-S06**.
    """

    def setUp(self):
        cache.clear()

    def test_un_catalogo_vacio_no_escribe_nada(self):
        programa = _programa_siis(79)

        with patch("programas.services.siis_sync.listar_programas_todos", return_value=[]):
            with self.assertRaisesMessage(SiisCatalogError, "catálogo vacío"):
                sincronizar_estado_programas()

        programa.refresh_from_db()
        self.assertEqual(programa.siis_programa_estado, ProgramaSiis.EstadoSiis.ACTIVO)
        self.assertIsNone(programa.siis_verificado_en)

    def test_una_ausencia_de_una_entre_tres_se_escribe_sola(self):
        """Lo normal: un programa dado de baja en SIIS. Sigue funcionando igual."""
        ausente, presente, otro = _programa_siis(79), _programa_siis(80), _programa_siis(81)

        with patch("programas.services.siis_sync.listar_programas_todos", return_value=_del_catalogo(80, 81)):
            cambios = sincronizar_estado_programas()

        self.assertEqual([programa.pk for programa, _, _ in cambios], [ausente.pk])
        ausente.refresh_from_db()
        presente.refresh_from_db()
        otro.refresh_from_db()
        self.assertEqual(ausente.siis_programa_estado, ESTADO_DESCONOCIDO)
        self.assertEqual(presente.siis_programa_estado, ProgramaSiis.EstadoSiis.ACTIVO)
        self.assertEqual(otro.siis_programa_estado, ProgramaSiis.EstadoSiis.ACTIVO)

    def test_la_mitad_justa_todavia_pasa(self):
        """El umbral es *más* del 50 %: uno de dos se escribe, no se frena."""
        ausente, presente = _programa_siis(79), _programa_siis(80)

        with patch("programas.services.siis_sync.listar_programas_todos", return_value=_del_catalogo(80)):
            sincronizar_estado_programas()

        ausente.refresh_from_db()
        presente.refresh_from_db()
        self.assertEqual(ausente.siis_programa_estado, ESTADO_DESCONOCIDO)
        self.assertEqual(presente.siis_programa_estado, ProgramaSiis.EstadoSiis.ACTIVO)

    def test_mas_de_la_mitad_ausentes_no_se_escribe_sin_forzar(self):
        programas = [_programa_siis(79), _programa_siis(80), _programa_siis(81)]

        with patch("programas.services.siis_sync.listar_programas_todos", return_value=_del_catalogo(81)):
            with self.assertRaisesMessage(SiisCatalogError, "2 de 3"):
                sincronizar_estado_programas()

        for programa in programas:
            programa.refresh_from_db()
            self.assertEqual(programa.siis_programa_estado, ProgramaSiis.EstadoSiis.ACTIVO)
            self.assertIsNone(programa.siis_verificado_en)

    def test_todos_ausentes_no_se_escribe_sin_forzar(self):
        programas = [_programa_siis(79), _programa_siis(80)]

        with patch("programas.services.siis_sync.listar_programas_todos", return_value=_del_catalogo(99)):
            with self.assertRaises(SiisCatalogError):
                sincronizar_estado_programas()

        for programa in programas:
            programa.refresh_from_db()
            self.assertEqual(programa.siis_programa_estado, ProgramaSiis.EstadoSiis.ACTIVO)

    def test_con_forzar_la_ausencia_masiva_se_escribe(self):
        """La baja masiva existe: se informa a mano, con alguien mirando."""
        programas = [_programa_siis(79), _programa_siis(80)]

        with patch("programas.services.siis_sync.listar_programas_todos", return_value=_del_catalogo(99)):
            cambios = sincronizar_estado_programas(forzar=True, motivo="baja confirmada con ECOM")

        self.assertEqual(len(cambios), 2)
        for programa in programas:
            programa.refresh_from_db()
            self.assertEqual(programa.siis_programa_estado, ESTADO_DESCONOCIDO)

    def test_el_goteo_no_saltea_la_guarda(self):
        """MINOR del PR 4: lo que se confirma es el estado **resultante**.

        Contando solo los ``DESCONOCIDO`` nuevos de cada corrida, tres catálogos
        parciales seguidos —4 ausentes de 10, después 5, después 1— dejaban los
        diez programas bloqueados sin que la guarda saltara nunca: ninguna de las
        tres corridas pasaba el umbral por sí sola. La ficha SIIS-06 pide
        confirmar «si pasarían a DESCONOCIDO todos los vinculados o más del
        50 %», y eso solo se sabe mirando cómo queda el conjunto.
        """
        programas = [_programa_siis(70 + indice) for indice in range(10)]

        def correr(presentes):
            with patch("programas.services.siis_sync.listar_programas_todos", return_value=_del_catalogo(*presentes)):
                sincronizar_estado_programas()

        def bloqueados():
            return ProgramaSiis.objects.filter(siis_programa_estado=ESTADO_DESCONOCIDO).count()

        correr(range(74, 80))  # 4 ausentes de 10: 40 %, pasa
        self.assertEqual(bloqueados(), 4)

        with self.assertRaisesMessage(SiisCatalogError, "9 de 10"):
            correr([79])  # 5 nuevos, pero quedarían 9 de 10 bloqueados

        self.assertEqual(bloqueados(), 4, "la segunda corrida escribió igual")
        for programa in programas[4:]:
            programa.refresh_from_db()
            self.assertEqual(programa.siis_programa_estado, ProgramaSiis.EstadoSiis.ACTIVO)

    def test_un_programa_que_ya_estaba_bloqueado_sigue_contando(self):
        """El mismo bug visto de cerca: sin novedades, la guarda no se aplicaba."""
        _programa_siis(79, estado=ProgramaSiis.EstadoSiis.DESCONOCIDO)
        _programa_siis(80, estado=ProgramaSiis.EstadoSiis.DESCONOCIDO)
        presente = _programa_siis(81)

        with patch("programas.services.siis_sync.listar_programas_todos", return_value=_del_catalogo(81)):
            with self.assertRaisesMessage(SiisCatalogError, "2 de 3"):
                sincronizar_estado_programas()

        presente.refresh_from_db()
        self.assertIsNone(presente.siis_verificado_en)

    def test_el_forzado_queda_en_el_log(self):
        """Saltear la guarda no puede ser silencioso: quién, cuándo y por qué."""
        _programa_siis(79)
        _programa_siis(80)

        with patch("programas.services.siis_sync.listar_programas_todos", return_value=_del_catalogo(99)):
            with self.assertLogs("programas.services.siis_sync", level="WARNING") as registrado:
                sincronizar_estado_programas(forzar=True, motivo="ECOM dio de baja el plan", usuario="jperez")

        linea = registrado.output[0]
        self.assertIn("2 de 2", linea)
        self.assertIn("jperez", linea)
        self.assertIn("ECOM dio de baja el plan", linea)

    def test_un_forzar_que_no_hacia_falta_no_ensucia_el_log(self):
        """``--forzar`` por costumbre sobre una baja normal no es una emergencia."""
        _programa_siis(79)
        _programa_siis(80)
        _programa_siis(81)

        with patch("programas.services.siis_sync.listar_programas_todos", return_value=_del_catalogo(80, 81)):
            with patch("programas.services.siis_sync.logger") as log:
                sincronizar_estado_programas(forzar=True, motivo="por las dudas")

        log.warning.assert_not_called()

    def test_con_un_solo_programa_vinculado_la_guarda_no_se_aplica(self):
        """Con uno solo, «todos» y «más del 50 %» son siempre ciertos: la guarda
        dejaría de poder detectar nunca una baja real."""
        programa = _programa_siis(79)

        with patch("programas.services.siis_sync.listar_programas_todos", return_value=_del_catalogo(99)):
            sincronizar_estado_programas()

        programa.refresh_from_db()
        self.assertEqual(programa.siis_programa_estado, ESTADO_DESCONOCIDO)

    def test_el_dry_run_tampoco_decide_por_su_cuenta(self):
        _programa_siis(79)
        _programa_siis(80)

        with patch("programas.services.siis_sync.listar_programas_todos", return_value=[]):
            with self.assertRaises(SiisCatalogError):
                sincronizar_estado_programas(dry_run=True)

    @override_settings(SIIS_API_URL="https://siis.example", SIIS_API_CLIENT_ID="c", SIIS_API_CLIENT_SECRET="s")
    def test_un_catalogo_vacio_no_queda_cacheado(self):
        """Cachear el vacío cinco minutos multiplica por cinco minutos el error."""
        respuesta = Mock(status_code=200)
        respuesta.json.return_value = {"data": []}
        respuesta.raise_for_status.return_value = None
        cache.set(TOKEN_CACHE_KEY, "abc", 60)

        with patch("programas.services.siis.sesion.get", return_value=respuesta):
            self.assertEqual(siis_mod.listar_programas_todos(), [])

        self.assertIsNone(cache.get(PROGRAMAS_TODOS_CACHE_KEY))

    def _correr(self, catalogo, *args):
        salida = StringIO()
        with patch("programas.services.siis_sync.listar_programas_todos", return_value=catalogo):
            call_command("sincronizar_programas_siis", *args, stdout=salida, stderr=salida)
        return salida.getvalue()

    def test_el_comando_informa_el_catalogo_vacio_como_error(self):
        programa = _programa_siis(79)

        with self.assertRaisesMessage(CommandError, "catálogo vacío"):
            self._correr([])

        programa.refresh_from_db()
        self.assertEqual(programa.siis_programa_estado, ProgramaSiis.EstadoSiis.ACTIVO)

    def test_el_forzar_del_comando_llega_al_servicio(self):
        _programa_siis(79)
        _programa_siis(80)

        salida = self._correr(_del_catalogo(99), "--forzar", "--motivo", "baja confirmada con ECOM")

        self.assertIn("2 programa(s) actualizado(s)", salida)
        self.assertEqual(
            ProgramaSiis.objects.filter(siis_programa_estado=ESTADO_DESCONOCIDO).count(),
            2,
        )

    def test_el_forzar_del_comando_exige_motivo(self):
        """MINOR del PR 4: era un flag pelado, como ``--ignorar-corrida`` antes
        del PR 3. Deja bloqueada media Becas o más: tiene que quedar escrito."""
        _programa_siis(79)
        _programa_siis(80)

        with self.assertRaisesMessage(CommandError, "--forzar necesita --motivo"):
            self._correr(_del_catalogo(99), "--forzar")

        self.assertEqual(ProgramaSiis.objects.filter(siis_programa_estado=ESTADO_DESCONOCIDO).count(), 0)

    def test_el_motivo_en_blanco_no_cuenta(self):
        _programa_siis(79)
        _programa_siis(80)

        with self.assertRaises(CommandError):
            self._correr(_del_catalogo(99), "--forzar", "--motivo", "   ")

    def test_el_usuario_del_comando_llega_al_log(self):
        _programa_siis(79)
        _programa_siis(80)

        with self.assertLogs("programas.services.siis_sync", level="WARNING") as registrado:
            self._correr(_del_catalogo(99), "--forzar", "--motivo", "baja real", "--usuario", "jperez")

        self.assertIn("jperez", registrado.output[0])

    def test_el_cronjob_corre_sin_motivo_porque_no_fuerza(self):
        """``docker/k8s/cronjobs.yaml`` lo invoca pelado: no tiene que cambiar."""
        _programa_siis(79)
        _programa_siis(80)
        _programa_siis(81)

        salida = self._correr(_del_catalogo(80, 81))

        self.assertIn("1 programa(s) actualizado(s)", salida)


@override_settings(
    SIIS_API_URL="https://siis.example",
    SIIS_API_CLIENT_ID="client",
    SIIS_API_CLIENT_SECRET="secret",
    SIIS_API_CONNECT_TIMEOUT=1,
    SIIS_API_TIMEOUT=2,
)
class RespuestaQueNoEsObjetoTests(TestCase):
    """SIIS-11: un JSON que no es un diccionario no puede ser un 500.

    El alta ya se cubría sola (Cambio 127 normaliza el cuerpo antes de leerlo);
    faltaban la consulta de compatibilidad, el token y el registro de la
    validación, que son los tres caminos que atraviesa «Validar en SIIS».
    """

    def setUp(self):
        cache.clear()

    def _respuesta(self, body, status=200):
        respuesta = Mock(status_code=status)
        respuesta.json.return_value = body
        respuesta.raise_for_status.return_value = None
        return respuesta

    def test_una_compatibilidad_que_contesta_una_lista_no_revienta(self):
        cache.set(TOKEN_CACHE_KEY, "abc", 60)

        with patch("programas.services.siis.sesion.post", return_value=self._respuesta(["OK"])):
            resultado = siis_mod.validar_compatibilidad("20301234", 79)

        self.assertFalse(resultado["success"])
        # Lo que contestó no se tira: sin esto, «no contestó» y «contestó una
        # lista» quedaban iguales en la fila registrada (MINOR del PR 4).
        self.assertEqual(resultado["data"], {"_crudo": "['OK']"})

    def test_una_compatibilidad_que_contesta_un_texto_no_revienta(self):
        cache.set(TOKEN_CACHE_KEY, "abc", 60)

        with patch("programas.services.siis.sesion.post", return_value=self._respuesta("OK", status=503)):
            resultado = siis_mod.validar_compatibilidad("20301234", 79)

        self.assertFalse(resultado["success"])

    def test_un_token_que_contesta_una_lista_no_revienta(self):
        """Sin cuerpo de objeto no hay ``access_token``: es configuración rota."""
        with patch("programas.services.siis.sesion.post", return_value=self._respuesta([])):
            resultado = siis_mod.validar_compatibilidad("20301234", 79)

        self.assertFalse(resultado["success"])

    def test_un_catalogo_que_contesta_una_lista_de_strings_no_revienta(self):
        cache.set(TOKEN_CACHE_KEY, "abc", 60)

        with patch("programas.services.siis.sesion.get", return_value=self._respuesta(["uno", "dos"])):
            self.assertEqual(siis_mod.listar_programas_todos(), [])


class ValidacionConDatosIlegiblesTests(_ConPayloadCompleto):
    """SIIS-11, segunda mitad: lo que se guarda de esa respuesta.

    ``id_consulta`` es un ``UUIDField`` y ``fecha_validacion`` un
    ``DateTimeField``: un ``"abc"`` o un ``"2026-13-45"`` del otro lado no tienen
    que convertirse en un 500 al guardar el intento auditable, que es justamente
    lo que deja constancia de que SIIS contestó cualquier cosa.
    """

    def _validar(self, data):
        with patch(
            "programas.services.validacion_siis.validar_compatibilidad",
            return_value={"success": True, "compatible": True, "data": data},
        ):
            return validar_formulario_en_siis(self.formulario, self.user)

    def test_un_id_de_consulta_ilegible_se_guarda_en_none(self):
        registro = self._validar({"id_consulta": "abc", "validaciones": {}})

        self.assertIsNone(registro.id_consulta)
        self.assertEqual(registro.estado, ValidacionSIS.Estado.OK)

    def test_una_fecha_imposible_se_guarda_en_none(self):
        registro = self._validar({"fecha_hora": "2026-13-45T00:00:00", "validaciones": {}})

        self.assertIsNone(registro.fecha_validacion)

    def test_un_id_de_consulta_valido_se_guarda_igual(self):
        valido = "8ef13bfb-529a-4438-a8b4-dca8b238039a"

        registro = self._validar({"id_consulta": valido, "validaciones": {}})

        self.assertEqual(registro.id_consulta, uuid.UUID(valido))

    def test_un_data_que_no_es_objeto_no_revienta(self):
        registro = self._validar(["OK"])

        self.assertIsNone(registro.id_consulta)
        self.assertEqual(registro.respuesta, {"_crudo": "['OK']"})

    def test_lo_que_contesto_siis_queda_guardado_aunque_no_sea_un_objeto(self):
        """MINOR del PR 4: ``respuesta = {}`` perdía la única pista que había.

        Quien después abre la validación para entender por qué el caso no avanzó
        no tiene otra cosa que esta fila: «SIIS no contestó» y «SIIS contestó el
        HTML de error de un proxy» son dos problemas distintos y se veían igual.
        """
        registro = self._validar("<html>502 Bad Gateway</html>")

        self.assertEqual(registro.respuesta, {"_crudo": "<html>502 Bad Gateway</html>"})
        self.assertEqual(registro.estado, ValidacionSIS.Estado.OK)

    def test_una_respuesta_enorme_se_recorta(self):
        """Un 502 de nginx son varios KB de HTML: no entran enteros en la fila."""
        registro = self._validar("x" * 5000)

        self.assertEqual(len(registro.respuesta["_crudo"]), siis_mod.LARGO_CRUDO)

    def test_el_detalle_de_la_pantalla_sobrevive_al_crudo(self):
        """El único lector estructurado de ``respuesta`` no se entera del cambio."""
        from programas.views.revision import _detalle_validacion_siis

        registro = self._validar(["OK"])

        detalle = _detalle_validacion_siis(registro)

        self.assertEqual(detalle["controles"], [])
        self.assertEqual(detalle["situacion"], "No informado")
        self.assertEqual(detalle["programa_nombre"], "")


class ApoderadoPrevalidadoTests(_ConPayloadCompleto):
    """SIIS-12: los tres rechazos que SIIS nos venía devolviendo por apoderado.

    Prevalidar no es duplicar la regla de SIIS: es dejar de gastar un alta —que
    no tiene baja— para enterarnos de algo que se ve con la fecha en la mano, y
    decírselo al coordinador en la pantalla de «Completar datos para SIIS», que
    es donde lo puede arreglar.
    """

    HOY = date(2026, 9, 14)

    def setUp(self):
        super().setUp()
        self.ciudadano.fecha_nacimiento = date(2015, 3, 10)  # menor: hay que informar apoderado
        self.ciudadano.save(update_fields=["fecha_nacimiento"])
        self.formulario.apoderado_dni = "25999888"
        self.formulario.apoderado_nombre = "Mario"
        self.formulario.apoderado_apellido = "Tutor"
        self.formulario.apoderado_genero = "M"
        self.formulario.apoderado_fecha_nacimiento = date(1978, 10, 20)
        self.formulario.save()

    def _payload(self):
        return armar_payload(self.formulario, catalogos=self.cat, hoy=self.HOY)

    def _apoderado(self, **campos):
        for campo, valor in campos.items():
            setattr(self.formulario, campo, valor)
        self.formulario.save()

    def test_un_apoderado_mayor_y_distinto_del_titular_no_deja_faltantes(self):
        payload, faltantes = self._payload()

        self.assertEqual(faltantes, {})
        self.assertEqual(payload["dni_apoderado"], 25999888)

    def test_un_apoderado_menor_de_18_es_un_faltante(self):
        self._apoderado(apoderado_fecha_nacimiento=self.HOY - timedelta(days=365 * 15))

        payload, faltantes = self._payload()

        self.assertEqual(faltantes["fecha_nacim_apoderado"], "El apoderado debe ser mayor de 18 años.")
        self.assertNotIn("fecha_nacim_apoderado", payload)

    def test_el_borde_de_los_18_cumplidos_hoy_pasa(self):
        self._apoderado(apoderado_fecha_nacimiento=date(2008, 9, 14))

        _, faltantes = self._payload()

        self.assertEqual(faltantes, {})

    def test_un_dia_antes_de_cumplir_18_no_pasa(self):
        self._apoderado(apoderado_fecha_nacimiento=date(2008, 9, 15))

        _, faltantes = self._payload()

        self.assertIn("fecha_nacim_apoderado", faltantes)

    def test_una_fecha_de_nacimiento_futura_es_un_faltante(self):
        self._apoderado(apoderado_fecha_nacimiento=self.HOY + timedelta(days=1))

        payload, faltantes = self._payload()

        self.assertEqual(faltantes["fecha_nacim_apoderado"], "La fecha de nacimiento del apoderado es futura.")
        self.assertNotIn("fecha_nacim_apoderado", payload)

    def test_el_titular_cargado_como_su_propio_apoderado_es_un_faltante(self):
        """448 casos en PRD (Cambio 98): el alumno se cargó a sí mismo."""
        self._apoderado(apoderado_dni=self.ciudadano.dni, apoderado_fecha_nacimiento=date(1978, 10, 20))

        _, faltantes = self._payload()

        self.assertEqual(faltantes["dni_apoderado"], "El apoderado no puede ser el propio titular.")

    def test_la_correccion_del_coordinador_destraba_el_apoderado(self):
        """Se valida lo corregido, no lo del legajo: si no, no habría salida."""
        self._apoderado(apoderado_dni=self.ciudadano.dni, apoderado_fecha_nacimiento=date(2009, 3, 10))
        self.formulario.datos_siis = {"dni_apoderado": "25999888", "fecha_nacim_apoderado": "1978-10-20"}
        self.formulario.save(update_fields=["datos_siis"])

        payload, faltantes = self._payload()

        self.assertEqual(faltantes, {})
        self.assertEqual(payload["dni_apoderado"], 25999888)

    def test_una_correccion_que_sigue_estando_mal_tampoco_pasa(self):
        self._apoderado(apoderado_fecha_nacimiento=date(1978, 10, 20))
        self.formulario.datos_siis = {"fecha_nacim_apoderado": "2015-03-10"}
        self.formulario.save(update_fields=["datos_siis"])

        _, faltantes = self._payload()

        self.assertIn("fecha_nacim_apoderado", faltantes)

    def test_un_apoderado_invalido_no_llega_a_siis(self):
        """El contrato de verdad: con faltantes no se llama a ``cargar_beneficiario``."""
        from programas.models import EnvioSIIS
        from programas.services.siis_envio import enviar_beneficiario_a_siis

        self._apoderado(apoderado_dni=self.ciudadano.dni)
        self.formulario.estado = self.formulario.Estado.APROBADO
        self.formulario.save(update_fields=["estado"])

        with patch("programas.services.siis_envio.cargar_beneficiario") as cargar:
            envio = enviar_beneficiario_a_siis(self.formulario, self.user, catalogos=self.cat)

        cargar.assert_not_called()
        self.assertEqual(envio.estado, EnvioSIIS.Estado.INCOMPLETO)
        self.assertIn("dni_apoderado", envio.detalles)

    def test_un_apoderado_mayor_tampoco_se_valida_si_el_titular_es_adulto(self):
        """La prevalidación vive adentro del bloque condicional: sin apoderado
        que informar, un apoderado viejo y mal cargado no bloquea nada."""
        self.ciudadano.fecha_nacimiento = date(1995, 6, 15)
        self.ciudadano.save(update_fields=["fecha_nacimiento"])
        self._apoderado(apoderado_dni=self.ciudadano.dni, apoderado_fecha_nacimiento=self.HOY + timedelta(days=1))

        payload, faltantes = self._payload()

        self.assertEqual(faltantes, {})
        self.assertNotIn("dni_apoderado", payload)
