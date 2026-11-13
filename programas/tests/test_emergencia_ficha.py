"""Emergencia, etapa 3: el Formulario 2 (``services.emergencia_ficha``), sin base de datos.

El esquema de ocho secciones, la normalización, el mínimo para confirmar (RN-3.6) y el
aplanado para el formulario. Las demás piezas de la etapa: ver ``test_emergencia_alojar``.
"""

from datetime import date

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from programas.models import (
    CasoEmergencia,
    TrazaCaso,
)
from programas.services import emergencia_alojar as servicio
from programas.tests.test_emergencia_alojar_base import ficha_minima

Estado = CasoEmergencia.Estado
Accion = TrazaCaso.Accion


class FichaTests(SimpleTestCase):
    HOY = date(2026, 11, 12)

    def test_el_esquema_tiene_las_ocho_secciones_en_orden(self):
        self.assertEqual(
            list(servicio.ESQUEMA_FICHA),
            [
                "parentesco",
                "datos_personales",
                "avisos_salud",
                "educacion",
                "vacunacion",
                "salud",
                "trabajo",
                "observaciones",
            ],
        )
        self.assertEqual(servicio.SECCIONES_MINIMAS + servicio.SECCIONES_OPCIONALES, tuple(servicio.ESQUEMA_FICHA))

    def test_los_campos_no_se_repiten_entre_secciones(self):
        """Es lo que deja aplanar la ficha a un formulario y volver a armarla."""

        campos = [campo for seccion in servicio.ESQUEMA_FICHA.values() for campo in seccion]
        self.assertEqual(len(campos), len(set(campos)))

    def test_normalizar_guarda_solo_lo_respondido_y_lleva_la_version(self):
        ficha = servicio.normalizar_ficha(
            {
                "datos_personales": {"dni": "30.111.222", "nombre": "  Juan ", "telefono": "", "cualquiera": 1},
                "avisos_salud": {"embarazo": "no", "discapacidad": True, "electrodependiente": None},
                "educacion": {"sin_datos": "si"},
                "otra_seccion": {"x": 1},
            }
        )

        self.assertEqual(ficha["version"], servicio.FICHA_VERSION)
        self.assertEqual(ficha["datos_personales"], {"dni": "30111222", "nombre": "Juan"})
        self.assertEqual(ficha["avisos_salud"], {"embarazo": False, "discapacidad": True})
        self.assertEqual(ficha["educacion"], {"sin_datos": True})
        self.assertNotIn("otra_seccion", ficha)
        self.assertEqual(servicio.normalizar_ficha(ficha), ficha, "normalizar no es idempotente")

    def test_normalizar_rechaza_lo_que_no_es_del_tipo(self):
        with self.assertRaises(ValidationError) as error:
            servicio.normalizar_ficha(
                {
                    "parentesco": {"parentesco": "PRIMO"},
                    "datos_personales": {"fecha_nacimiento": "ayer", "telefono": "1" * 41},
                }
            )
        self.assertEqual(set(error.exception.error_dict), {"parentesco", "fecha_nacimiento", "telefono"})

    def test_el_minimo_completo_pasa(self):
        ficha = servicio.ficha_minima_valida(ficha_minima("30111222"), hoy=self.HOY)
        self.assertEqual(ficha["datos_personales"]["fecha_nacimiento"], "2006-03-10")

    def test_sin_avisos_de_salud_falta_cada_pregunta(self):
        """HU-3.3: «Falta: avisos de salud». Las cinco tienen que estar **respondidas**."""

        ficha = ficha_minima("30111222")
        ficha["avisos_salud"] = {"embarazo": False}

        with self.assertRaises(ValidationError) as error:
            servicio.ficha_minima_valida(ficha, hoy=self.HOY)

        errores = error.exception.message_dict
        self.assertEqual(set(errores), {"discapacidad", "electrodependiente", "medicacion_critica", "alergias_graves"})
        self.assertTrue(all("Falta: avisos de salud" in mensajes[0] for mensajes in errores.values()))

    def test_la_medicacion_critica_pide_nombre_y_dosis(self):
        ficha = ficha_minima("30111222", avisos_salud={"medicacion_critica": True})
        with self.assertRaises(ValidationError) as error:
            servicio.ficha_minima_valida(ficha, hoy=self.HOY)
        self.assertEqual(
            set(error.exception.error_dict), {"medicacion_critica_nombre", "medicacion_critica_tiene_dosis"}
        )

        ficha["avisos_salud"].update(medicacion_critica_nombre="Insulina", medicacion_critica_tiene_dosis=False)
        servicio.ficha_minima_valida(ficha, hoy=self.HOY)

    def test_falta_todo_lo_demas_del_minimo(self):
        with self.assertRaises(ValidationError) as error:
            servicio.ficha_minima_valida({"parentesco": {"parentesco": "OTRO"}}, hoy=self.HOY)
        self.assertTrue(
            {"parentesco_otro", "dni", "nombre", "apellido", "sexo", "fecha_nacimiento", "embarazo"}
            <= set(error.exception.error_dict)
        )

    def test_sin_numero_de_dni_no_se_confirma(self):
        """Decisión del PM (D-10): no se inventan DNI; se cierra con diferencia."""

        for dni in ("", "no sabe", "123"):
            with self.subTest(dni=dni), self.assertRaises(ValidationError) as error:
                servicio.ficha_minima_valida(ficha_minima(dni), hoy=self.HOY)
            self.assertEqual(error.exception.message_dict["dni"], [servicio.SIN_NUMERO_DE_DOCUMENTO])

    def test_un_menor_de_16_necesita_adulto_responsable(self):
        """03 §10. 15 años y 364 días es menor; el día que cumple 16, no."""

        menor = ficha_minima("50111222", datos_personales={"fecha_nacimiento": "2010-11-13"})
        with self.assertRaises(ValidationError) as error:
            servicio.ficha_minima_valida(menor, hoy=self.HOY)
        self.assertEqual(set(error.exception.error_dict), {"adulto_responsable"})

        menor["observaciones"] = {"adulto_responsable": "Rosa Benítez, la madre"}
        servicio.ficha_minima_valida(menor, hoy=self.HOY)
        cumple_16 = ficha_minima("50111222", datos_personales={"fecha_nacimiento": "2010-11-12"})
        servicio.ficha_minima_valida(cumple_16, hoy=self.HOY)

    def test_una_fecha_de_nacimiento_futura_no_vale(self):
        with self.assertRaises(ValidationError) as error:
            servicio.ficha_minima_valida(
                ficha_minima("30111222", datos_personales={"fecha_nacimiento": "2027-01-01"}), hoy=self.HOY
            )
        self.assertEqual(set(error.exception.error_dict), {"fecha_nacimiento"})

    def test_la_ficha_esta_completa_con_un_dato_o_sin_datos_en_cada_seccion(self):
        ficha = servicio.normalizar_ficha(ficha_minima("30111222"))
        self.assertFalse(servicio.ficha_esta_completa(ficha))
        self.assertEqual(len(servicio.secciones_incompletas(ficha)), 5)

        ficha = servicio.normalizar_ficha(
            ficha_minima(
                "30111222",
                educacion={"nivel_educativo": "PRIMARIO"},
                vacunacion={"sin_datos": True},
                salud={"obra_social": "No tiene"},
                trabajo={"sin_datos": True},
                observaciones={"mascotas": False},
            )
        )
        self.assertTrue(servicio.ficha_esta_completa(ficha))

    def test_la_ficha_se_aplana_y_se_vuelve_a_armar(self):
        ficha = servicio.normalizar_ficha(
            ficha_minima("30111222", salud={"sin_datos": True}, trabajo={"ocupacion": "Albañil"})
        )
        plano = servicio.ficha_a_plano(ficha)

        self.assertEqual(plano["dni"], "30111222")
        self.assertIs(plano["salud_sin_datos"], True)
        self.assertEqual(plano["ocupacion"], "Albañil")
        self.assertEqual(servicio.normalizar_ficha(servicio.ficha_desde_plano(plano)), ficha)
