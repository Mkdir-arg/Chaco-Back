"""Correcciones de formularios de Emergencia y Dispositivos (auditoría del 21-nov-2026).

* **Encargado que recibe**: siempre el usuario que aloja; el campo ya no está en el formulario y la
  API sigue aceptándolo (la app vieja) pero lo ignora.
* **Adulto responsable** de un menor: un adulto confirmado del mismo grupo, validado en el servidor.
* **Fecha de nacimiento aproximada**: no entra al legajo.
* **Teléfono** de Emergencia: la regla del legajo del dispositivo.
* **Localidad del edificio**: del catálogo, como la del dispositivo.
"""

from django.core.exceptions import ValidationError

from core.models import Localidad, Municipio, Provincia
from legajos.models import Ciudadano
from programas.forms_dispositivos import EdificioForm
from programas.forms_emergencia_dispositivo import FamiliaAlojadaForm, FichaIntegranteForm
from programas.models import CasoEmergencia, IntegranteGrupo, Sector
from programas.services import emergencia_alojar as servicio
from programas.tests.base_emergencia_api import BaseApiLlegadas, _url
from programas.tests.test_emergencia_alojar_base import BaseAlojar
from programas.tests.test_emergencia_casos import T0, BaseCasos
from programas.validacion_contacto import MENSAJE_TELEFONO_INVALIDO

MENOR = {"fecha_nacimiento": "2015-05-05"}


class EncargadoQueRecibeTests(BaseAlojar):
    def _familia_confirmada(self):
        self._turno(self.club)
        caso, derivacion = self._aceptado(menores_f=0, menores_m=0, adultos_f=1, adultos_m=1)
        for orden, reserva in enumerate(self._reservas(derivacion), start=1):
            self._confirmar(caso, orden, str(45_000_100 + orden), plaza=reserva.plaza)
        return caso

    def test_el_servidor_registra_al_usuario_que_aloja_aunque_manden_otro_nombre(self):
        caso = self._familia_confirmada()

        servicio.alojar_familia(caso=caso, usuario=self.guardia, encargado="Cualquier Otra Persona")

        alojamiento = CasoEmergencia.objects.get(pk=caso.pk).situacion["alojamiento"]
        self.assertEqual(alojamiento["encargado_id"], self.guardia.pk)
        self.assertEqual(alojamiento["encargado"], "guardia_club")

    def test_el_formulario_no_tiene_el_campo_encargado(self):
        self.assertNotIn("encargado", FamiliaAlojadaForm(sectores=Sector.objects.none()).fields)


class EncargadoQueRecibeApiTests(BaseApiLlegadas):
    def test_la_app_vieja_manda_encargado_y_el_servidor_lo_ignora(self):
        caso, _derivacion = self._aceptado(dni="30111222", menores_f=0, menores_m=0, plazas=3)
        self._confirmar(caso, 1, "30111222")
        self._confirmar(caso, 2, "45111222")

        respuesta = self._como(self.guardia_centro).post(
            _url("caso-alojar", caso.pk), {"encargado": "Otra Persona"}, format="json"
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        alojamiento = CasoEmergencia.objects.get(pk=caso.pk).situacion["alojamiento"]
        self.assertEqual(alojamiento["encargado_id"], self.guardia_centro.pk)
        self.assertNotEqual(alojamiento["encargado"], "Otra Persona")


class AdultoResponsableTests(BaseAlojar):
    def setUp(self):
        super().setUp()
        self.caso, self.derivacion = self._aceptado()
        self.reservas = self._reservas(self.derivacion)

    def _confirmar_n(self, orden, dni, **cambios):
        return self._confirmar(self.caso, orden, dni, plaza=self.reservas[orden - 1].plaza, **cambios)

    def _filas(self):
        return IntegranteGrupo.objects.filter(grupo=self.caso.grupo).select_related("ciudadano")

    def test_un_menor_con_un_adulto_del_grupo_se_confirma_y_guarda_su_nombre(self):
        adulto = self._confirmar_n(1, "30111222")

        menor = self._confirmar_n(
            3, "55000111", datos_personales=MENOR, observaciones={"adulto_responsable_orden": "1"}
        )

        observaciones = IntegranteGrupo.objects.get(pk=menor.pk).ficha["observaciones"]
        self.assertEqual(observaciones["adulto_responsable_orden"], "1")
        self.assertEqual(observaciones["adulto_responsable"], adulto.ciudadano.apellido_nombre)

    def test_otro_menor_no_vale_como_adulto_responsable(self):
        self._confirmar_n(1, "30111222")
        self._confirmar_n(2, "55000222", datos_personales=MENOR, observaciones={"adulto_responsable_orden": "1"})

        with self.assertRaises(ValidationError) as error:
            self._confirmar_n(3, "55000111", datos_personales=MENOR, observaciones={"adulto_responsable_orden": "2"})

        self.assertEqual(set(error.exception.error_dict), {"adulto_responsable_orden"})

    def test_una_persona_sin_confirmar_o_inexistente_no_vale(self):
        self._confirmar_n(1, "30111222")
        for elegido in ("4", "99", "x", "²"):
            with self.subTest(elegido=elegido), self.assertRaises(ValidationError) as error:
                self._confirmar_n(
                    3, "55000111", datos_personales=MENOR, observaciones={"adulto_responsable_orden": elegido}
                )
            self.assertEqual(set(error.exception.error_dict), {"adulto_responsable_orden"})
        self.assertFalse(IntegranteGrupo.objects.get(grupo=self.caso.grupo, orden=3).confirmada)

    def test_nadie_es_su_propio_adulto_responsable(self):
        self._confirmar_n(1, "30111222")

        self.assertEqual([a["orden"] for a in servicio.adultos_del_grupo(self._filas())], [1])
        self.assertEqual(servicio.adultos_del_grupo(self._filas(), excluir_orden=1), [])

    def test_el_texto_libre_de_antes_sigue_valiendo_para_la_app_vieja(self):
        menor = self._confirmar_n(
            3, "55000111", datos_personales=MENOR, observaciones={"adulto_responsable": "Rosa Benítez"}
        )

        self.assertTrue(menor.confirmada)

    def test_completar_la_ficha_tambien_valida_al_adulto(self):
        self._confirmar_n(1, "30111222")
        self._confirmar_n(3, "55000111", datos_personales=MENOR, observaciones={"adulto_responsable_orden": "1"})

        with self.assertRaises(ValidationError):
            servicio.completar_ficha(
                caso=self.caso,
                orden=3,
                usuario=self.guardia,
                ficha={"observaciones": {"adulto_responsable_orden": "5"}},
            )

    def test_el_selector_ofrece_solo_a_los_adultos_confirmados(self):
        self._confirmar_n(1, "30111222")
        self._confirmar_n(2, "55000222", datos_personales=MENOR, observaciones={"adulto_responsable_orden": "1"})

        form = FichaIntegranteForm(adultos=servicio.adultos_del_grupo(self._filas(), excluir_orden=3))

        self.assertEqual([valor for valor, _ in form.fields["adulto_responsable_orden"].choices], ["", "1"])
        self.assertNotIn("adulto_responsable", form.fields)

    def test_el_error_del_menor_sin_adulto_cae_en_el_selector(self):
        form = FichaIntegranteForm({}, adultos=[{"orden": 1, "nombre": "Benítez, Rosa"}])
        form.is_valid()
        form.agregar_errores_del_servicio(ValidationError({"adulto_responsable": "Falta."}))

        self.assertEqual(form.errors["adulto_responsable_orden"], ["Falta."])

    def test_sin_adultos_el_backoffice_ofrece_el_texto_libre(self):
        form = FichaIntegranteForm({"adulto_responsable": "Rosa Benítez"}, adultos=[])
        form.is_valid()

        self.assertIn("adulto_responsable", form.fields)
        self.assertNotIn("adulto_responsable_orden", form.fields)
        self.assertEqual(form.ficha()["observaciones"]["adulto_responsable"], "Rosa Benítez")
        form.agregar_errores_del_servicio(ValidationError({"adulto_responsable": "Falta."}))
        self.assertEqual(form.errors["adulto_responsable"], ["Falta."])

    def test_un_grupo_sin_adultos_confirma_al_menor_con_texto(self):
        self.assertEqual(servicio.adultos_de_la_familia(self.caso.grupo, excluir_orden=3), [])

        menor = self._confirmar_n(
            3, "55000111", datos_personales=MENOR, observaciones={"adulto_responsable": "Rosa Benítez"}
        )

        self.assertEqual(
            IntegranteGrupo.objects.get(pk=menor.pk).ficha["observaciones"]["adulto_responsable"], "Rosa Benítez"
        )

    def test_el_selector_muestra_como_solo_lectura_el_texto_guardado(self):
        ficha = {"observaciones": {"adulto_responsable": "Tía Marta"}}

        form = FichaIntegranteForm(solo_opcionales=True, ficha=ficha, adultos=[{"orden": 1, "nombre": "Benítez, Rosa"}])

        self.assertIn("Guardado: Tía Marta", form.fields["adulto_responsable_orden"].help_text)
        self.assertNotIn("adulto_responsable", form.fields)

    def test_con_el_adulto_egresado_otra_seccion_se_guarda_sin_error(self):
        """La app guarda «Trabajo» del menor: el adulto que eligió egresó y eso no es un 400."""

        self._confirmar_n(1, "30111222")
        self._confirmar_n(3, "55000111", datos_personales=MENOR, observaciones={"adulto_responsable_orden": "1"})
        IntegranteGrupo.objects.filter(grupo=self.caso.grupo, orden=1).update(egresado_en=T0)

        guardada = servicio.completar_ficha(
            caso=self.caso, orden=3, usuario=self.guardia, ficha={"trabajo": {"ocupacion": "Ninguna"}}
        )

        observaciones = guardada.ficha["observaciones"]
        self.assertEqual(observaciones["adulto_responsable_orden"], "1")
        self.assertTrue(observaciones["adulto_responsable"])

    def test_el_texto_se_conserva_al_guardar_otra_seccion_o_observaciones_sin_adulto(self):
        menor = self._confirmar_n(
            3, "55000111", datos_personales=MENOR, observaciones={"adulto_responsable": "Rosa Benítez"}
        )
        for enviada in ({"trabajo": {"ocupacion": "Ninguna"}}, {"observaciones": {"mascotas": True}}):
            with self.subTest(enviada=enviada):
                guardada = servicio.completar_ficha(caso=self.caso, orden=3, usuario=self.guardia, ficha=enviada)

                self.assertEqual(guardada.ficha["observaciones"]["adulto_responsable"], "Rosa Benítez")
        self.assertTrue(IntegranteGrupo.objects.get(pk=menor.pk).ficha["observaciones"]["mascotas"])

    def test_un_mayor_no_pierde_su_adulto_responsable_al_guardar_observaciones(self):
        persona = self._confirmar_n(2, "45000111", observaciones={"adulto_responsable": "Tía Marta", "mascotas": False})

        guardada = servicio.completar_ficha(
            caso=self.caso, orden=2, usuario=self.guardia, ficha={"observaciones": {"mascotas": True}}
        )

        self.assertEqual(guardada.pk, persona.pk)
        self.assertEqual(guardada.ficha["observaciones"], {"adulto_responsable": "Tía Marta", "mascotas": True})

    def test_un_adulto_egresado_no_se_ofrece_ni_vale_como_responsable(self):
        self._confirmar_n(1, "30111222")
        IntegranteGrupo.objects.filter(grupo=self.caso.grupo, orden=1).update(egresado_en=T0)

        self.assertEqual(servicio.adultos_del_grupo(self._filas(), excluir_orden=3), [])
        with self.assertRaises(ValidationError):
            self._confirmar_n(3, "55000111", datos_personales=MENOR, observaciones={"adulto_responsable_orden": "1"})

    def test_la_seccion_que_llega_con_un_adulto_invalido_si_se_rechaza(self):
        self._confirmar_n(3, "55000111", datos_personales=MENOR, observaciones={"adulto_responsable": "Rosa Benítez"})

        with self.assertRaises(ValidationError) as error:
            servicio.completar_ficha(
                caso=self.caso,
                orden=3,
                usuario=self.guardia,
                ficha={"observaciones": {"adulto_responsable_orden": "2"}},
            )

        self.assertEqual(set(error.exception.error_dict), {"adulto_responsable_orden"})


class FechaAproximadaTests(BaseAlojar):
    def setUp(self):
        super().setUp()
        self.caso, self.derivacion = self._aceptado()
        self.reservas = self._reservas(self.derivacion)

    def test_una_persona_nueva_con_fecha_aproximada_queda_sin_fecha_en_el_legajo(self):
        integrante = self._confirmar(
            self.caso,
            2,
            "45000111",
            plaza=self.reservas[0].plaza,
            datos_personales={"fecha_nacimiento_aproximada": True},
        )

        self.assertIsNone(Ciudadano.objects.get(dni="45000111").fecha_nacimiento)
        datos = IntegranteGrupo.objects.get(pk=integrante.pk).ficha["datos_personales"]
        self.assertEqual((datos["fecha_nacimiento"], datos["fecha_nacimiento_aproximada"]), ("2006-03-10", True))

    def test_con_fecha_firme_entra_al_legajo(self):
        self._confirmar(self.caso, 2, "45000111", plaza=self.reservas[0].plaza)

        self.assertEqual(str(Ciudadano.objects.get(dni="45000111").fecha_nacimiento), "2006-03-10")

    def test_el_responsable_sin_fecha_en_el_legajo_tampoco_la_recibe_si_es_aproximada(self):
        responsable = self.caso.grupo.responsable
        Ciudadano.objects.filter(pk=responsable.pk).update(fecha_nacimiento=None)

        self._confirmar(
            self.caso,
            1,
            "30111222",
            plaza=self.reservas[0].plaza,
            datos_personales={"fecha_nacimiento_aproximada": True},
        )

        self.assertIsNone(Ciudadano.objects.get(pk=responsable.pk).fecha_nacimiento)


class TelefonoDeEmergenciaTests(BaseAlojar):
    def setUp(self):
        super().setUp()
        self.caso, self.derivacion = self._aceptado()
        self.reservas = self._reservas(self.derivacion)

    def test_la_ficha_normaliza_el_telefono_y_va_al_legajo(self):
        self._confirmar(
            self.caso,
            2,
            "45000111",
            plaza=self.reservas[0].plaza,
            datos_personales={"telefono": "+54 (362) 4-111-222"},
        )

        self.assertEqual(Ciudadano.objects.get(dni="45000111").telefono, "+543624111222")

    def test_un_telefono_que_no_es_un_numero_se_rechaza_sin_crear_nada(self):
        for telefono in ("no tiene", "el de la vecina", "123"):
            with self.subTest(telefono=telefono), self.assertRaises(ValidationError) as error:
                self._confirmar(
                    self.caso,
                    2,
                    "45000111",
                    plaza=self.reservas[0].plaza,
                    datos_personales={"telefono": telefono},
                )
            self.assertEqual(error.exception.message_dict["telefono"], [MENSAJE_TELEFONO_INVALIDO])
        self.assertFalse(Ciudadano.objects.filter(dni="45000111").exists())

    def test_completar_no_revalida_un_telefono_guardado_antes(self):
        integrante = self._confirmar(self.caso, 2, "45000111", plaza=self.reservas[0].plaza)
        guardada = IntegranteGrupo.objects.get(pk=integrante.pk)
        guardada.ficha["datos_personales"]["telefono"] = "el de la vecina"
        guardada.save(update_fields=["ficha"])

        servicio.completar_ficha(
            caso=self.caso, orden=2, usuario=self.guardia, ficha={"trabajo": {"ocupacion": "Albañil"}}
        )

        self.assertEqual(
            IntegranteGrupo.objects.get(pk=integrante.pk).ficha["datos_personales"]["telefono"], "el de la vecina"
        )


class TelefonoDelFormulario1Tests(BaseCasos):
    def test_se_guarda_normalizado(self):
        caso = self._caso(telefono="3624 11-1111")

        self.assertEqual(caso.situacion["telefono"], "3624111111")

    def test_vacio_no_se_guarda(self):
        self.assertNotIn("telefono", self._caso(telefono="").situacion)

    def test_un_texto_que_no_es_un_numero_se_rechaza(self):
        with self.assertRaises(ValidationError) as error:
            self._caso(telefono="no tiene")

        self.assertEqual(error.exception.message_dict["telefono"], [MENSAJE_TELEFONO_INVALIDO])


class LocalidadDelEdificioTests(BaseAlojar):
    def _datos(self, **cambios):
        return {"codigo": "EDI-1", "nombre": "Predio", "provincia": "Chaco", **cambios}

    def test_la_localidad_es_un_selector_del_catalogo(self):
        self.assertEqual(EdificioForm().fields["localidad"].widget.__class__.__name__, "Select")

    def test_un_texto_que_no_esta_en_el_catalogo_se_rechaza(self):
        form = EdificioForm(self._datos(localidad="Rcia."))

        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors["localidad"], ["Elegí una localidad del listado."])

    def test_una_localidad_del_catalogo_guarda_el_nombre(self):
        provincia, _ = Provincia.objects.get_or_create(nombre="Chaco")
        municipio = Municipio.objects.create(nombre="Resistencia", provincia=provincia)
        Localidad.objects.create(nombre="Resistencia", municipio=municipio)
        form = EdificioForm(self._datos(localidad="Resistencia"))

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["localidad"], "Resistencia")
