"""Validación de DNI/CUIT, teléfono y nombre del responsable (#628).

QA cargó `3e1312321` como DNI/CUIT de una solicitud de merendero y se guardó. Cubre el
helper puro y el form del legajo de dispositivo; el de la solicitud de merendero está
en `test_merenderos.py`.
"""

from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase
from django.urls import reverse

from programas.forms import DispositivoForm
from programas.models import Dispositivo
from programas.tests.test_dispositivos_fidelidad_fd import AHORA
from programas.tests.test_dispositivos_horarios_localidad import catalogo_chaco
from programas.tests.test_dispositivos_infraestructura import BaseInfraestructura
from programas.validacion_contacto import (
    MENSAJE_CUIT_INVALIDO,
    MENSAJE_DOCUMENTO_INVALIDO,
    MENSAJE_NOMBRE_INVALIDO,
    MENSAJE_TELEFONO_INVALIDO,
    normalizar_documento_responsable,
    normalizar_telefono,
    validar_nombre_responsable,
)

# 20-12345678-6: prefijo 20 y verificador que cierra por módulo 11.
CUIT_VALIDO = "20123456786"


class DocumentoResponsableTests(SimpleTestCase):
    def test_acepta_dni_y_cuit_y_guarda_solo_digitos(self):
        casos = {
            "30123456": "30123456",
            "30.123.456": "30123456",
            "30-123-456": "30123456",
            "  30 123 456 ": "30123456",
            "1234567": "1234567",
            CUIT_VALIDO: CUIT_VALIDO,
            "20-12345678-6": CUIT_VALIDO,
            "20 12345678 6": CUIT_VALIDO,
        }
        for crudo, esperado in casos.items():
            with self.subTest(crudo=crudo):
                self.assertEqual(normalizar_documento_responsable(crudo), esperado)

    def test_rechaza_lo_que_no_son_digitos_o_tiene_otro_largo(self):
        # `3e1312321` es el caso de QA: nueve caracteres, uno de ellos una «e».
        for crudo in ("3e1312321", "abc", "30123456x", "12345", "123456789", "1234567890", "123456789012", "", "---"):
            with self.subTest(crudo=crudo), self.assertRaises(ValidationError) as ctx:
                normalizar_documento_responsable(crudo)
            self.assertEqual(ctx.exception.messages, [MENSAJE_DOCUMENTO_INVALIDO])

    def test_cuit_con_verificador_incorrecto(self):
        for crudo in ("20123456780", "20-12345678-0", "99123456786"):
            with self.subTest(crudo=crudo), self.assertRaises(ValidationError) as ctx:
                normalizar_documento_responsable(crudo)
            self.assertEqual(ctx.exception.messages, [MENSAJE_CUIT_INVALIDO])


class TelefonoResponsableTests(SimpleTestCase):
    def test_normaliza_a_digitos_conservando_el_mas_inicial(self):
        casos = {
            "3624123456": "3624123456",
            "+54 362 412-3456": "+543624123456",
            "(0362) 4123456": "03624123456",
            "12345678": "12345678",
            "123456789012345": "123456789012345",
        }
        for crudo, esperado in casos.items():
            with self.subTest(crudo=crudo):
                self.assertEqual(normalizar_telefono(crudo), esperado)

    def test_rechaza_caracteres_ajenos_y_largos_fuera_de_rango(self):
        for crudo in ("1234567", "1234567890123456", "abc12345678", "3624.123456", "362412345x", ""):
            with self.subTest(crudo=crudo), self.assertRaises(ValidationError) as ctx:
                normalizar_telefono(crudo)
            self.assertEqual(ctx.exception.messages, [MENSAJE_TELEFONO_INVALIDO])


class NombreResponsableTests(SimpleTestCase):
    def test_exige_al_menos_una_letra(self):
        self.assertEqual(validar_nombre_responsable("  María Pérez "), "María Pérez")
        self.assertEqual(validar_nombre_responsable("Juan 2"), "Juan 2")
        for crudo in ("1234", "---", "   ", ""):
            with self.subTest(crudo=crudo), self.assertRaises(ValidationError) as ctx:
                validar_nombre_responsable(crudo)
            self.assertEqual(ctx.exception.messages, [MENSAJE_NOMBRE_INVALIDO])


class DispositivoContactoTests(BaseInfraestructura):
    def setUp(self):
        reloj = patch("django.utils.timezone.now", return_value=AHORA)
        reloj.start()
        self.addCleanup(reloj.stop)
        super().setUp()
        catalogo_chaco()
        self.client.force_login(self.admin)
        # Un registro viejo: guardado antes de que se validara el formato.
        self.cis.estado = Dispositivo.Estado.BORRADOR
        self.cis.responsable_documento = "3e1312321"
        self.cis.contacto_telefono = "123"
        self.cis.save()
        self.editar = reverse("dispositivos:editar", args=[self.cis.pk])

    def _datos(self, **cambios):
        return {
            "tipo": self.tipo.pk,
            "codigo": self.cis.codigo,
            "nombre": self.cis.nombre,
            "localidad": "Resistencia",
            "domicilio": "Calle 123",
            "responsable_nombre": "Responsable FI",
            "responsable_documento": "30.123.456",
            "contacto_telefono": "+54 362 412-3456",
            **cambios,
        }

    def test_normaliza_documento_y_telefono(self):
        form = DispositivoForm(data=self._datos(), instance=self.cis)
        form.is_valid()
        self.assertEqual(form.cleaned_data["responsable_documento"], "30123456")
        self.assertEqual(form.cleaned_data["contacto_telefono"], "+543624123456")
        self.assertNotIn("responsable_documento", form.errors)
        self.assertNotIn("contacto_telefono", form.errors)

    def test_rechaza_documento_telefono_y_nombre_invalidos(self):
        form = DispositivoForm(
            data=self._datos(responsable_documento="3e1312321", contacto_telefono="12", responsable_nombre="123"),
            instance=self.cis,
        )
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors["responsable_documento"], [MENSAJE_DOCUMENTO_INVALIDO])
        self.assertEqual(form.errors["contacto_telefono"], [MENSAJE_TELEFONO_INVALIDO])
        self.assertEqual(form.errors["responsable_nombre"], [MENSAJE_NOMBRE_INVALIDO])

    def test_cuit_con_verificador_malo(self):
        form = DispositivoForm(data=self._datos(responsable_documento="20123456780"), instance=self.cis)
        form.is_valid()
        self.assertEqual(form.errors["responsable_documento"], [MENSAJE_CUIT_INVALIDO])

    def test_borrador_vacio_no_valida_formato(self):
        form = DispositivoForm(
            data=self._datos(responsable_documento="", contacto_telefono="", responsable_nombre=""),
            instance=self.cis,
        )
        form.is_valid()
        for campo in ("responsable_documento", "contacto_telefono", "responsable_nombre"):
            self.assertNotIn(campo, form.errors)

    def test_el_get_muestra_el_dato_viejo_sin_error_y_con_la_ayuda(self):
        respuesta = self.client.get(self.editar)
        self.assertContains(respuesta, "3e1312321")
        self.assertContains(respuesta, "DNI de 7 u 8 dígitos o CUIT de 11")
        self.assertNotContains(respuesta, MENSAJE_DOCUMENTO_INVALIDO)

    def test_al_editar_un_registro_viejo_se_pide_corregir(self):
        respuesta = self.client.post(self.editar, self._datos(responsable_documento="3e1312321"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, MENSAJE_DOCUMENTO_INVALIDO)
        self.cis.refresh_from_db()
        self.assertEqual(self.cis.responsable_documento, "3e1312321")

        respuesta = self.client.post(self.editar, self._datos())
        self.assertEqual(respuesta.status_code, 302)
        self.cis.refresh_from_db()
        self.assertEqual(self.cis.responsable_documento, "30123456")
        self.assertEqual(self.cis.contacto_telefono, "+543624123456")
