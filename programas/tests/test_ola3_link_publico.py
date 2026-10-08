"""PR 7b de la Ola 3: link público, padrón, Base de Personas, aviso y CUIL.

Un módulo por PR y no uno por ficha, porque las seis son chicas y comparten
fixtures. Cada clase nombra su ficha:

* **G1-11** — el alta a SIIS calculaba el CUIL por módulo 11 **siempre**, aunque
  el caso trajera el CUIL emitido (campo «Cuit Alumno» del catálogo, que
  ``completar_casos_renaper`` completa desde ``ciudadanos_renaper``). Un ``23-…``
  real viajaba como ``20-…``, y el alta en SIIS no tiene baja. El real se usa
  solo si es de ese DNI **y es un CUIL válido** (prefijo de la AFIP y
  verificador por módulo 11): uno mal tipeado no puede pisar al calculado.
* **G1-12** — el padrón aceptaba fechas de nacimiento futuras o absurdas
  (``05/06/30`` → 2030 por el pivote de ``%y``; el serial 0 de Excel →
  1899-12-30) y el cruce las **escribía en el legajo**.
* **G1-13** — un 404 de Base de Personas se informaba como «falló el servicio»
  (502) por la app de campo, mientras el mismo «no está» por el código 12 del
  cuerpo daba 404.
* **G1-14** — el correo de resolución no dejaba registro: el retorno se
  descartaba en los cuatro llamadores y en el masivo.
* **R0-06** — dos filas con el mismo ``token_publico`` (hex y con guiones, lo que
  deja un restore de un motor al otro) hacían 500 en el link público.
* **R0-07 / RED-09** — ``q_uuid_en_texto`` reventaba con ``None`` o un texto, y
  vivía en ``programas.services.becas`` cuando lo necesitan también ``legajos`` y
  ``users``.
"""

import uuid
from datetime import date, timedelta
from io import StringIO
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import connection
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from core.db import q_uuid_en_texto
from legajos.models import Ciudadano
from programas.models import (
    Convocatoria,
    Formulario,
    Relevamiento,
    RequisitoNativo,
    Segmento,
    TracaFormulario,
)
from programas.services import padron as padron_mod
from programas.services import personas as personas_mod
from programas.services import siis_envio
from programas.services.avisos_resolucion import CAMPO_TRAZA_AVISO, enviar_aviso_resolucion, resultado_vigente
from programas.services.becas import relevamiento_publico_por_token
from programas.services.siis_envio import (
    CUIL_DE_OTRO_DOCUMENTO,
    CUIL_INVALIDO,
    CUIL_SIN_DATO,
    CUIL_USABLE,
    PREFIJOS_CUIL,
    TEXTO_CUIL_APODERADO,
    TEXTO_CUIL_TITULAR,
    armar_payload,
    calcular_cuil,
    clave_nombre,
    cuil_del_caso,
    cuil_valido,
    evaluar_cuil_respondido,
)
from programas.tests.test_becas_revision import _BaseAvisoResolucionTest
from programas.tests.test_siis_que_viaja import _ConFoto


class _BaseBecas(TestCase):
    def setUp(self):
        self.segmento = Segmento.objects.create(nombre="Becas Secundario", cupo_maximo=100)
        self.convocatoria = Convocatoria.objects.create(
            nombre="Becas 2026",
            segmento=self.segmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        self.relevamiento = Relevamiento.objects.create(
            convocatoria=self.convocatoria,
            tipo=Relevamiento.Tipo.PUBLICO,
            fecha_asignada=date(2026, 6, 1),
            confirmar_por_email=True,
        )


# ── G1-11 ────────────────────────────────────────────────────────────────────


class _BaseCuil(_BaseBecas):
    DNI = "30123456"

    def setUp(self):
        super().setUp()
        self.requisito = RequisitoNativo.objects.create(
            texto="Cuit Alumno", tipo="INTEGER", segmento=self.segmento, orden=1
        )
        self.ciudadano = Ciudadano.objects.create(dni=self.DNI, nombre="MARIA", apellido="GOMEZ", genero="F")

    def _caso(self, respondido=None, texto="Cuit Alumno"):
        clave = f"rn-{self.requisito.pk}"
        return Formulario.objects.create(
            relevamiento=self.relevamiento,
            ciudadano=self.ciudadano,
            email_contacto="m@correo.com",
            definicion={
                "version": 1,
                "items": [
                    {"clave": "g-1", "tipo": "grupo", "items": [{"clave": clave, "texto": texto, "tipo": "INTEGER"}]}
                ],
            },
            respuestas={clave: respondido} if respondido is not None else {},
        )


class CuilRealDelCasoTests(_BaseCuil):
    """D-G11: el CUIL emitido le gana al calculado **cuando es de ese DNI**."""

    def test_los_textos_del_catalogo_normalizan_a_las_claves(self):
        """Las constantes son literales porque el normalizador se define después."""
        self.assertEqual(clave_nombre("Cuit Alumno"), TEXTO_CUIL_TITULAR)
        self.assertEqual(clave_nombre("Cuil  Apoderado"), TEXTO_CUIL_APODERADO)

    def test_el_cuil_real_de_ese_dni_le_gana_al_calculado(self):
        """El hallazgo: un 23-… emitido viajaba como 20-… / 27-…."""
        calculado = calcular_cuil(self.DNI, "F")
        real = f"23{self.DNI}2"
        self.assertTrue(cuil_valido(real))
        self.assertNotEqual((int(real[:2]), int(real[-1])), calculado)

        caso = self._caso(respondido=real)

        self.assertEqual(cuil_del_caso(caso, self.DNI, "F", TEXTO_CUIL_TITULAR), (23, 2))

    def test_un_cuil_de_otro_documento_no_se_usa(self):
        caso = self._caso(respondido="23999999994")

        self.assertEqual(cuil_del_caso(caso, self.DNI, "F", TEXTO_CUIL_TITULAR), calcular_cuil(self.DNI, "F"))

    def test_un_cuil_valido_de_otro_documento_tampoco(self):
        """Que el CUIL sea válido no alcanza: tiene que ser de esta persona."""
        otro = "31234567"
        prefijo, digito = calcular_cuil(otro, "F")
        de_otro = f"{prefijo:02d}{otro}{digito}"
        self.assertTrue(cuil_valido(de_otro))
        caso = self._caso(respondido=de_otro)

        self.assertEqual(cuil_del_caso(caso, self.DNI, "F", TEXTO_CUIL_TITULAR), calcular_cuil(self.DNI, "F"))

    def test_un_cuil_de_ese_dni_con_el_verificador_roto_no_se_usa(self):
        """El de la revisión: 27-<DNI>-9 salía como (27, 9); el verificador es 8."""
        self.assertEqual(calcular_cuil(self.DNI, "F"), (27, 8))
        for roto in (f"27{self.DNI}9", f"23{self.DNI}4"):
            with self.subTest(respondido=roto):
                caso = self._caso(respondido=roto)
                self.assertEqual(cuil_del_caso(caso, self.DNI, "F", TEXTO_CUIL_TITULAR), (27, 8))

    def test_un_cuil_de_ese_dni_con_un_prefijo_imposible_no_se_usa(self):
        """99-… no lo asigna la AFIP, aunque el módulo 11 cierre (con 9 cierra)."""
        for imposible in (f"99{self.DNI}9", f"99{self.DNI}1", f"21{self.DNI}0"):
            with self.subTest(respondido=imposible):
                caso = self._caso(respondido=imposible)
                self.assertEqual(cuil_del_caso(caso, self.DNI, "F", TEXTO_CUIL_TITULAR), (27, 8))

    def test_un_cuil_incompleto_o_vacio_no_se_usa(self):
        for respondido in ("", "2730123456", "no sé", None):
            with self.subTest(respondido=respondido):
                caso = self._caso(respondido=respondido)
                self.assertEqual(cuil_del_caso(caso, self.DNI, "F", TEXTO_CUIL_TITULAR), calcular_cuil(self.DNI, "F"))

    def test_el_cuil_entra_con_guiones_o_como_numero(self):
        """`completar_casos_renaper` lo guarda como int; a mano llega con guiones."""
        for respondido in (f"23-{self.DNI}-2", int(f"23{self.DNI}2")):
            with self.subTest(respondido=respondido):
                caso = self._caso(respondido=respondido)
                self.assertEqual(cuil_del_caso(caso, self.DNI, "F", TEXTO_CUIL_TITULAR), (23, 2))

    def test_un_caso_sin_foto_sigue_calculando(self):
        """Los casos anteriores a la foto no declaran sus campos: no hay de dónde leer."""
        caso = Formulario.objects.create(
            relevamiento=self.relevamiento, ciudadano=self.ciudadano, email_contacto="m@correo.com"
        )

        self.assertEqual(cuil_del_caso(caso, self.DNI, "F", TEXTO_CUIL_TITULAR), calcular_cuil(self.DNI, "F"))

    def test_el_campo_del_apoderado_no_se_confunde_con_el_del_titular(self):
        caso = self._caso(respondido=f"23{self.DNI}2")

        self.assertEqual(cuil_del_caso(caso, self.DNI, "F", TEXTO_CUIL_APODERADO), calcular_cuil(self.DNI, "F"))

    def test_un_dni_de_siete_digitos_cruza_con_el_cero_adelante(self):
        dni = "7123456"
        caso = self._caso(respondido=f"2007123456{calcular_cuil(dni, 'M')[1]}")

        prefijo, _ = cuil_del_caso(caso, dni, "M", TEXTO_CUIL_TITULAR)

        self.assertEqual(prefijo, 20)


class CuilEnElPayloadTests(_BaseCuil):
    """El payload que viaja a SIIS, no solo el helper."""

    def test_el_payload_lleva_el_cuil_real(self):
        caso = self._caso(respondido=f"23{self.DNI}2")
        caso.ciudadano.fecha_nacimiento = date(1990, 5, 4)
        caso.ciudadano.save(update_fields=["fecha_nacimiento"])

        # Un doble que no resuelve catálogos ni memoriza destinos: lo que se mide acá es
        # el CUIL, y con PERF-01 ``armar_payload`` le pregunta también por los destinos.
        catalogos = Mock(
            estado_civil_id=lambda *a, **k: None,
            destinos_del_catalogo=siis_envio._destinos_del_catalogo,
        )

        payload, _ = armar_payload(caso, catalogos)[:2]

        self.assertEqual(payload["cuil_pref"], 23)
        self.assertEqual(payload["cuil_dig"], 2)


class CuilValidoTests(SimpleTestCase):
    """La regla que decide si el CUIL respondido puede pisar al calculado."""

    def test_todo_cuil_que_calcula_el_alta_es_valido(self):
        """Mismo verificador: lo que calcula ``calcular_cuil`` siempre valida.

        Incluye el caso especial de la AFIP: 20301234 (M) da 10 con prefijo 20 y
        sale ``23-…-9``; 30123407 (F) da 10 con prefijo 27 y sale ``23-…-4``.
        """
        self.assertEqual(calcular_cuil("20301234", "M"), (23, 9))
        self.assertEqual(calcular_cuil("30123407", "F"), (23, 4))
        for dni in [str(n) for n in range(30123400, 30123500)] + ["20301234", "7123456"]:
            for sexo in ("M", "F"):
                prefijo, digito = calcular_cuil(dni, sexo)
                with self.subTest(dni=dni, sexo=sexo):
                    self.assertTrue(cuil_valido(f"{prefijo:02d}{dni.zfill(8)}{digito}"))

    def test_el_verificador_roto_no_es_valido(self):
        self.assertTrue(cuil_valido("27301234568"))
        for digito in "012345679":
            with self.subTest(digito=digito):
                self.assertFalse(cuil_valido(f"2730123456{digito}"))

    def test_un_prefijo_que_no_asigna_la_afip_no_es_valido(self):
        self.assertEqual(PREFIJOS_CUIL, {20, 23, 24, 27, 30, 33, 34})
        self.assertFalse(cuil_valido("99301234569"))  # el módulo 11 cierra, el prefijo no existe

    def test_un_verificador_que_da_diez_no_es_valido(self):
        """20301234 con prefijo 20 da 10: ese CUIL no se emite (sale 23-…-9)."""
        for digito in "0123456789":
            with self.subTest(digito=digito):
                self.assertFalse(cuil_valido(f"2020301234{digito}"))

    def test_largo_y_formato(self):
        self.assertTrue(cuil_valido("27-30123456-8"))
        self.assertTrue(cuil_valido(27301234568))
        for raro in ("", None, "2730123456", "273012345688"):
            with self.subTest(valor=raro):
                self.assertFalse(cuil_valido(raro))

    def test_la_evaluacion_separa_las_cuatro_situaciones(self):
        dni = "30123456"
        self.assertEqual(evaluar_cuil_respondido(f"23{dni}2", dni), CUIL_USABLE)
        self.assertEqual(evaluar_cuil_respondido(f"27{dni}9", dni), CUIL_INVALIDO)
        self.assertEqual(evaluar_cuil_respondido(f"99{dni}9", dni), CUIL_INVALIDO)
        self.assertEqual(evaluar_cuil_respondido("27312345671", dni), CUIL_DE_OTRO_DOCUMENTO)
        self.assertEqual(evaluar_cuil_respondido("2730123456", dni), CUIL_SIN_DATO)


class CuilEnElPayloadCompletoTests(_ConFoto):
    """El contrato completo de ``test_siis_que_viaja``, con un CUIL real en el caso.

    Compara el dict entero y no solo ``cuil_pref``/``cuil_dig``: preferir el real
    no puede mover ningún otro campo de lo que viaja.
    """

    ESPERADO = {
        "dni": 20301234,
        "tdoc": 1,
        "apellido": "PEREZ",
        "nombre": "JUAN CARLOS",
        "sexo": "M",
        "est_civil": 1,
        "prov_nacim": 22,
        "fecha_nacim": "1995-06-15",
        "loc_nacim": 1,
        "celular": 3624123456,
        "prov_actual": 22,
        "loc_actual": 1,
        "barrio_actual": "BARRIO CENTRO",
        "calle_actual": "AV. 9 DE JULIO",
        "nro_actual": 450,
        "piso_actual": 2,
        "dpto_actual": "B",
        "correo_electron": "juan.perez@email.com",
        "jurid": 28,
        "id_plan_soc": 79,
        "id_fun_x_plan": 4,
    }

    def setUp(self):
        super().setUp()
        self.cuit = RequisitoNativo.objects.create(texto="Cuit Alumno", tipo="INTEGER", segmento=self.segmento, orden=1)
        self._sacar_foto()

    def _responder_cuil(self, valor):
        self.formulario.data["requisitos"][str(self.cuit.pk)] = valor
        self.formulario.save(update_fields=["data"])
        return armar_payload(self.formulario, catalogos=self.cat, hoy=date(2026, 9, 14))

    def test_un_cuil_real_valido_distinto_del_calculado_viaja_entero(self):
        # 20301234 (M) calcula 23-…-9; 24-20301234-5 es un CUIL válido de ese DNI.
        self.assertEqual(calcular_cuil("20301234", "M"), (23, 9))
        self.assertTrue(cuil_valido("24203012345"))

        payload, faltantes = self._responder_cuil("24-20301234-5")

        self.assertEqual(faltantes, {})
        self.assertEqual(payload, {**self.ESPERADO, "cuil_pref": 24, "cuil_dig": 5})

    def test_un_cuil_real_roto_deja_el_payload_de_siempre(self):
        payload, faltantes = self._responder_cuil("24-20301234-6")

        self.assertEqual(faltantes, {})
        self.assertEqual(payload, {**self.ESPERADO, "cuil_pref": 23, "cuil_dig": 9})


class MedirCuilRespondidoTests(_BaseCuil):
    """La medición cuenta con la misma regla que el alta y no imprime datos personales."""

    def test_cuenta_el_respondido_invalido_aparte_y_sin_datos_personales(self):
        respondidos = (f"27{self.DNI}8", f"23{self.DNI}2", f"27{self.DNI}9", f"99{self.DNI}9", "27312345671", "")
        for respondido in respondidos:
            self._caso(respondido=respondido)
        salida = StringIO()

        call_command("medir_cuil_respondido", stdout=salida)

        texto = salida.getvalue()
        titular = texto.split("Titular:")[1].split("Apoderado:")[0]
        conteo = {}
        for linea in titular.splitlines():
            nombre, _, numero = linea.strip().rpartition(" ")
            if numero.isdigit():
                conteo[nombre.strip()] = int(numero)
        self.assertEqual(
            conteo,
            {"coincide": 1, "difiere": 1, "de otro documento": 1, "respondido inválido": 2, "sin CUIL": 1},
        )
        self.assertNotIn(self.DNI, texto)


# ── G1-12 ────────────────────────────────────────────────────────────────────


class FechasDelPadronTests(SimpleTestCase):
    """G1-12: lo que no se puede creer se cuenta como fecha sin interpretar."""

    def test_el_ano_de_dos_digitos_no_manda_a_alguien_al_futuro(self):
        """El caso de la ficha: `05/06/30` es 1930, no 2030."""
        fecha, invalida = padron_mod.normalizar_fecha("05/06/30")

        self.assertFalse(invalida)
        self.assertEqual(fecha, date(1930, 6, 5))

    def test_el_serial_cero_de_excel_no_entra_como_1899(self):
        fecha, invalida = padron_mod.normalizar_fecha(0)

        self.assertIsNone(fecha)
        self.assertTrue(invalida)

    def test_una_fecha_futura_no_entra(self):
        manana = timezone.localdate() + timedelta(days=1)

        fecha, invalida = padron_mod.normalizar_fecha(manana)

        self.assertIsNone(fecha)
        self.assertTrue(invalida)

    def test_hoy_si_entra(self):
        """El corte es «futura», no «de hoy»: un recién nacido es una fecha válida."""
        hoy = timezone.localdate()

        self.assertEqual(padron_mod.normalizar_fecha(hoy), (hoy, False))

    def test_una_fecha_anterior_a_1900_no_entra(self):
        fecha, invalida = padron_mod.normalizar_fecha("31/12/1899")

        self.assertIsNone(fecha)
        self.assertTrue(invalida)

    def test_una_celda_vacia_no_es_invalida(self):
        for valor in (None, "", "   "):
            with self.subTest(valor=valor):
                self.assertEqual(padron_mod.normalizar_fecha(valor), (None, False))

    def test_una_fecha_normal_sigue_entrando(self):
        self.assertEqual(padron_mod.normalizar_fecha("04/05/1990"), (date(1990, 5, 4), False))
        self.assertEqual(padron_mod.normalizar_fecha("1990-05-04"), (date(1990, 5, 4), False))


class ResumenDePadronTests(SimpleTestCase):
    """Las dos filas de la ficha se informan, no se cuelan en silencio."""

    def test_las_dos_filas_de_la_ficha_cuentan_como_fecha_sin_interpretar(self):
        resumen = padron_mod.ResumenPadron(validas=2, con_identidad=2)
        for crudo in ("05/06/30", 0):
            fecha, invalida = padron_mod.normalizar_fecha(crudo)
            if invalida:
                resumen.fechas_invalidas += 1

        # `05/06/30` se interpreta bien (1930); el serial 0, no.
        self.assertEqual(resumen.fechas_invalidas, 1)
        self.assertIn("1 fecha sin interpretar", resumen.mensaje())


# ── G1-13 ────────────────────────────────────────────────────────────────────


class PersonasNoEncontradaTests(SimpleTestCase):
    """G1-13: un 404 del proveedor es «no figura», no «el servicio falló»."""

    def _consultar(self, status, cuerpo=None):
        respuesta = Mock(status_code=status)
        respuesta.json.return_value = cuerpo or {}
        respuesta.raise_for_status.return_value = None
        cliente = personas_mod.PersonasAPIClient()
        with patch.object(cliente, "_configurada", return_value=True):
            with patch.object(cliente, "_token", return_value="tok"):
                with patch.object(personas_mod.sesion, "get", return_value=respuesta):
                    return cliente.consultar(dni="30123456", sexo="F")

    def test_un_404_se_informa_como_no_encontrada(self):
        resultado = self._consultar(404)

        self.assertFalse(resultado["success"])
        self.assertTrue(resultado["not_found"])

    def test_el_codigo_12_del_cuerpo_sigue_diciendo_lo_mismo(self):
        """Las dos formas en que el proveedor dice «no está» tienen que coincidir."""
        resultado = self._consultar(200, {"data": {"codigo": 12, "mensaje": "NO SE ENCONTRO"}})

        self.assertTrue(resultado["not_found"])

    def test_un_500_no_es_no_encontrada(self):
        respuesta = Mock(status_code=500)
        respuesta.json.return_value = {}
        respuesta.raise_for_status.side_effect = ValueError("500")
        cliente = personas_mod.PersonasAPIClient()
        with patch.object(cliente, "_configurada", return_value=True):
            with patch.object(cliente, "_token", return_value="tok"):
                with patch.object(personas_mod.sesion, "get", return_value=respuesta):
                    resultado = cliente.consultar(dni="30123456", sexo="F")

        self.assertFalse(resultado.get("not_found", False))


class IdentidadNoEncontradaTests(_BaseBecas):
    """La marca tiene que llegar hasta quien decide el código HTTP."""

    def test_identificar_propaga_no_encontrado(self):
        from programas.services.identidad import identificar

        with patch(
            "programas.services.identidad.consultar_persona",
            return_value={"success": False, "not_found": True, "error": "no está"},
        ):
            resultado = identificar(self.relevamiento, "30123456", "F")

        self.assertTrue(resultado["no_encontrado"])
        self.assertFalse(resultado["validado"])


# ── G1-14 ────────────────────────────────────────────────────────────────────


class TrazaDelAvisoTests(_BaseBecas):
    """G1-14: el correo de resolución deja registro, salga o no."""

    def setUp(self):
        super().setUp()
        self.usuario = User.objects.create_user("revisor", password="x")
        self.ciudadano = Ciudadano.objects.create(dni="30123456", nombre="MARIA", apellido="GOMEZ", genero="F")
        self.caso = Formulario.objects.create(
            relevamiento=self.relevamiento,
            ciudadano=self.ciudadano,
            email_contacto="maria@correo.com",
        )

    def _trazas(self):
        return list(TracaFormulario.objects.filter(formulario=self.caso, campo=CAMPO_TRAZA_AVISO))

    def test_un_envio_que_sale_queda_registrado(self):
        self.assertTrue(enviar_aviso_resolucion(self.caso, "aprobado", usuario=self.usuario))

        trazas = self._trazas()
        self.assertEqual(len(trazas), 1)
        self.assertIn("enviado", trazas[0].valor_nuevo)
        self.assertEqual(trazas[0].editado_por, self.usuario)

    def test_un_envio_que_falla_queda_registrado(self):
        """El de la ficha: `EmailMultiAlternatives.send` que lanza."""
        with patch(
            "programas.services.avisos_resolucion.EmailMultiAlternatives.send",
            side_effect=OSError("smtp caído"),
        ):
            self.assertFalse(enviar_aviso_resolucion(self.caso, "rechazado", usuario=self.usuario))

        trazas = self._trazas()
        self.assertEqual(len(trazas), 1)
        self.assertIn("falló", trazas[0].valor_nuevo)
        self.assertIn("rechazado", trazas[0].valor_nuevo)

    def test_lo_que_no_se_intenta_no_deja_traza(self):
        """Un relevamiento sin aviso o un caso sin correo no son un envío."""
        self.relevamiento.confirmar_por_email = False
        self.relevamiento.save(update_fields=["confirmar_por_email"])
        self.caso.refresh_from_db()

        self.assertFalse(enviar_aviso_resolucion(self.caso, "aprobado", usuario=self.usuario))

        self.assertEqual(self._trazas(), [])

    def test_una_traza_que_falla_no_voltea_el_correo(self):
        """La acción del técnico ya está firme: perder el registro no puede dar 500."""
        with patch("programas.services.becas.registrar_traza", side_effect=OSError("base caída")):
            self.assertTrue(enviar_aviso_resolucion(self.caso, "aprobado", usuario=self.usuario))

    def test_la_conexion_del_lote_es_la_que_se_usa(self):
        """G1-14: una conexión SMTP por lote, no una por correo."""
        conexion = Mock()
        with patch("programas.services.avisos_resolucion.EmailMultiAlternatives") as mensaje:
            mensaje.return_value.send.return_value = 1
            enviar_aviso_resolucion(self.caso, "aprobado", usuario=self.usuario, conexion=conexion)

        self.assertIs(mensaje.call_args.kwargs["connection"], conexion)


class ResultadoVigenteTests(_BaseBecas):
    """El desenlace del reenvío lo dice el caso, no el operador."""

    def setUp(self):
        super().setUp()
        self.caso = Formulario.objects.create(relevamiento=self.relevamiento, email_contacto="m@correo.com")

    def test_un_caso_sin_resolver_no_tiene_aviso_que_reenviar(self):
        self.assertEqual(resultado_vigente(self.caso), "")

    def test_aprobado_y_rechazado_salen_de_su_estado(self):
        for estado, esperado in (
            (Formulario.Estado.APROBADO, "aprobado"),
            (Formulario.Estado.RECHAZADO, "rechazado"),
        ):
            with self.subTest(estado=estado):
                self.caso.estado = estado
                self.assertEqual(resultado_vigente(self.caso), esperado)

    def test_la_lista_de_espera_la_trae_quien_llama(self):
        """`Formulario.Estado` no tiene «en espera»: sin cupo el caso sigue ENVIADO."""
        self.caso.estado = Formulario.Estado.ENVIADO

        self.assertEqual(resultado_vigente(self.caso, en_espera=True), "lista_espera")
        self.assertEqual(resultado_vigente(self.caso, en_espera=False), "")


class ReenviarAvisoViewTests(_BaseAvisoResolucionTest):
    """El botón «Reenviar aviso» del detalle (G1-14), con sus bordes de permiso."""

    def _url(self):
        return reverse("becas:formulario_reenviar_aviso", args=[self.form_a.pk])

    def _resolver(self, estado=Formulario.Estado.APROBADO):
        self.form_a.estado = estado
        self.form_a.email_contacto = "maria@correo.com"
        self.form_a.save(update_fields=["estado", "email_contacto"])

    @patch("programas.views.revision.enviar_aviso_resolucion", return_value=True)
    def test_reenvia_con_el_desenlace_que_dice_el_caso(self, aviso):
        self._resolver(Formulario.Estado.RECHAZADO)

        self.client.post(self._url())

        aviso.assert_called_once()
        self.assertEqual(aviso.call_args.args[1], "rechazado")
        self.assertEqual(aviso.call_args.kwargs["usuario"], self.coord_a)

    @patch("programas.views.revision.enviar_aviso_resolucion")
    def test_un_caso_sin_resolver_no_manda_nada(self, aviso):
        self.form_a.estado = Formulario.Estado.ENVIADO
        self.form_a.save(update_fields=["estado"])

        self.client.post(self._url())

        aviso.assert_not_called()

    @patch("programas.views.revision.enviar_aviso_resolucion")
    def test_sin_el_toggle_del_relevamiento_no_manda_nada(self, aviso):
        self._resolver()
        self.rel_a.confirmar_por_email = False
        self.rel_a.save(update_fields=["confirmar_por_email"])

        self.client.post(self._url())

        aviso.assert_not_called()

    @patch("programas.views.revision.enviar_aviso_resolucion")
    def test_sin_correo_de_contacto_no_manda_nada(self, aviso):
        self._resolver()
        self.form_a.email_contacto = ""
        self.form_a.save(update_fields=["email_contacto"])

        self.client.post(self._url())

        aviso.assert_not_called()

    def test_el_get_no_reenvia(self):
        """Mandar un correo con un GET lo dispara cualquier precarga del navegador."""
        self._resolver()

        self.assertEqual(self.client.get(self._url()).status_code, 405)

    @patch("programas.views.revision.enviar_aviso_resolucion")
    def test_anonimo_va_al_login(self, aviso):
        self._resolver()
        self.client.logout()

        respuesta = self.client.post(self._url())

        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("next=", respuesta["Location"])
        aviso.assert_not_called()

    @patch("programas.views.revision.enviar_aviso_resolucion")
    def test_sin_la_capacidad_no_manda_nada(self, aviso):
        """``@requiere`` saca al que no tiene la capacidad con un redirect, no un 403."""
        self._resolver()
        self.client.force_login(User.objects.create_user("mirón", password="x"))

        respuesta = self.client.post(self._url())

        self.assertEqual(respuesta.status_code, 302)
        self.assertNotIn("reenviar-aviso", respuesta["Location"])
        aviso.assert_not_called()

    @patch("programas.views.revision.enviar_aviso_resolucion", return_value=True)
    def test_un_superusuario_puede(self, aviso):
        self._resolver()
        self.client.force_login(User.objects.create_superuser("jefa", "j@x.com", "x"))

        self.client.post(self._url())

        aviso.assert_called_once()


# ── R0-07 / RED-09 ───────────────────────────────────────────────────────────


class QUuidEnTextoTests(SimpleTestCase):
    """R0-07: el helper no revienta con lo que no es un UUID."""

    def test_un_none_no_levanta_y_no_trae_nada(self):
        """Antes era `valor.hex` → AttributeError adentro de la vista."""
        filtro = q_uuid_en_texto("token_publico", None)

        self.assertEqual(str(filtro), str(type(filtro)(pk__in=[])))

    def test_un_texto_invalido_tampoco(self):
        for valor in ("", "no-es-un-uuid", 12, []):
            with self.subTest(valor=valor):
                filtro = q_uuid_en_texto("token_publico", valor)
                self.assertEqual(str(filtro), str(type(filtro)(pk__in=[])))

    def test_un_uuid_en_texto_vale_igual_que_el_objeto(self):
        valor = uuid.uuid4()

        self.assertEqual(
            str(q_uuid_en_texto("token_publico", str(valor))), str(q_uuid_en_texto("token_publico", valor))
        )
        self.assertEqual(str(q_uuid_en_texto("token_publico", valor.hex)), str(q_uuid_en_texto("token_publico", valor)))

    def test_vive_en_core_y_becas_lo_reexporta(self):
        """RED-09: `legajos` y `users` no pueden importar un servicio de `programas`."""
        from programas.services import becas

        self.assertIs(becas.q_uuid_en_texto, q_uuid_en_texto)


# ── R0-06 ────────────────────────────────────────────────────────────────────


class TokenPublicoDuplicadoTests(_BaseBecas):
    """R0-06: el link no puede dar 500 porque un restore dejó el token dos veces."""

    def setUp(self):
        super().setUp()
        self.token = uuid.uuid4()
        self.relevamiento.token_publico = self.token
        self.relevamiento.save(update_fields=["token_publico"])
        # La segunda fila, con el **mismo** UUID en la otra forma: es lo que deja
        # un restore de MySQL (hex) sobre MariaDB (con guiones) y viceversa. El
        # índice único no lo impide porque compara texto.
        self.gemelo = Relevamiento.objects.create(
            convocatoria=self.convocatoria,
            tipo=Relevamiento.Tipo.PUBLICO,
            fecha_asignada=date(2026, 6, 1),
        )
        # Por SQL crudo a propósito: el ``UUIDField`` normaliza el valor en el
        # ORM (en SQLite lo guarda siempre en hex), así que por el ORM las dos
        # formas colapsan en la misma y el índice único las rechaza. La fila
        # «de la otra forma» solo puede nacer de un restore, que tampoco pasa por
        # Django — y es exactamente el escenario de la ficha.
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE programas_relevamiento SET token_publico = %s WHERE id = %s",
                [str(self.token), self.gemelo.pk],
            )

    def test_el_queryset_trae_las_dos_filas(self):
        """Lo que hacía estallar a `get_object_or_404`."""
        self.assertEqual(relevamiento_publico_por_token(self.token).count(), 2)

    def test_el_link_atiende_la_mas_vieja_y_no_revienta(self):
        from portal.views.inscripcion import _get_relevamiento

        with self.assertLogs("portal.views.inscripcion", level="ERROR") as registro:
            elegido = _get_relevamiento(self.token)

        self.assertEqual(elegido.pk, min(self.relevamiento.pk, self.gemelo.pk))
        self.assertIn("comparten el token", registro.output[0])

    def test_sin_duplicado_no_se_loguea_nada(self):
        from portal.views.inscripcion import _get_relevamiento

        Relevamiento.objects.filter(pk=self.gemelo.pk).delete()

        with patch("portal.views.inscripcion.logger") as log:
            elegido = _get_relevamiento(self.token)

        self.assertEqual(elegido.pk, self.relevamiento.pk)
        log.error.assert_not_called()

    def test_un_token_que_no_existe_sigue_siendo_404(self):
        from django.http import Http404

        from portal.views.inscripcion import _get_relevamiento

        with self.assertRaises(Http404):
            _get_relevamiento(uuid.uuid4())
