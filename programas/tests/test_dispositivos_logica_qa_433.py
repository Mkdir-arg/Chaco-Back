"""Errores de lógica que QA encontró en testing (Cambio 433).

1. Asignar y reasignar un relevamiento edilicio usan la misma fuente de candidatos.
2. El doble envío de una novedad de bitácora no la duplica.
3. Corregir una novedad sin cambios se rechaza.
4. «Fuera de servicio» sobre una plaza que ya lo está dice que no hubo nada que cambiar.
5. Reasignar un relevamiento cancelado dice que no está en curso, no que el agente no sirve.
6. La capacidad declarada de un sector tiene tope.
"""

from datetime import timedelta

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from programas.forms_dispositivos import SectorForm
from programas.models import Edificio, EntradaBitacora, InspeccionEdificio, Plaza
from programas.services.bitacora import SIN_CAMBIOS_PARA_CORREGIR
from programas.services.inspecciones import (
    SOLO_EN_CURSO_SE_REASIGNA,
    agentes_asignables,
    agentes_para_reasignar,
    cancelar_inspeccion,
    crear_inspeccion,
)
from programas.services.plazas import CAPACIDAD_DECLARADA_MAXIMA, crear_sector, editar_sector
from programas.tests.test_dispositivos_bitacora import LUNES, PDF, BaseBitacora, _local
from programas.tests.test_dispositivos_crear_relevamiento_p4 import AJAX, BaseCrearRelevamiento
from programas.tests.test_dispositivos_plazas_acciones import BaseMapa


class ReasignarUsaLosMismosCandidatosTests(BaseCrearRelevamiento):
    def _asignar(self, agente):
        return crear_inspeccion(
            self._fresco(self.coordinador),
            edificio=self.predio,
            asignado_a=self._fresco(agente),
            fecha_vencimiento=self.vence,
        )

    def _reasignar(self, inspeccion, agente):
        url = reverse("dispositivos:relevamiento_reasignar", args=[inspeccion.pk])
        return self._cliente(self.coordinador).post(url, {"asignado_a": agente.pk}, **AJAX)

    def test_el_agente_de_la_asignacion_inicial_es_aceptado_al_reasignar_otro_relevamiento_del_edificio(self):
        primera = self._asignar(self.agente)
        cancelar_inspeccion(self._fresco(self.coordinador), primera, "Se reprograma")
        segunda = self._asignar(self.otro_agente)

        self.assertIn(self.agente, agentes_asignables(self.predio))
        self.assertIn(self.agente, agentes_para_reasignar(segunda))
        respuesta = self._reasignar(segunda, self.agente)

        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        segunda.refresh_from_db()
        self.assertEqual(segunda.asignado_a, self.agente)

    def test_reasignar_excluye_solo_al_asignado_actual(self):
        inspeccion = self._asignar(self.agente)

        # Con relevar: agente, otro_agente y el personal del parador y del geriatrico (ambos del predio).
        self.assertEqual(set(agentes_asignables(self.predio)), {self.agente, self.otro_agente})
        self.assertEqual(set(agentes_para_reasignar(inspeccion)), {self.otro_agente})

    def test_el_personal_de_otra_institucion_del_edificio_compartido_no_es_candidato(self):
        """Lo que vio QA: «personal» es todo usuario con rol asignado a una institución del edificio.

        P4 ofrece a `personal_geriatrico` (es personal del predio pero no de ED-EXTRA), el POST de P4
        lo rechaza para el predio y reasignar no lo ofrece ni lo acepta.
        """

        self._edificio_extra()
        self.assertIn(self.personal_geriatrico, self._agentes_del_selector())

        respuesta = self._post(self._datos(edificio=self.predio, agente=self.personal_geriatrico))
        self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(InspeccionEdificio.objects.exists())

        inspeccion = self._asignar(self.agente)
        self.assertNotIn(self.personal_geriatrico, agentes_para_reasignar(inspeccion))
        self.assertEqual(self._reasignar(inspeccion, self.personal_geriatrico).status_code, 400)
        inspeccion.refresh_from_db()
        self.assertEqual(inspeccion.asignado_a, self.agente)

    def test_el_selector_del_modal_trae_la_misma_lista(self):
        inspeccion = self._asignar(self.agente)
        respuesta = self._cliente(self.coordinador).get(
            reverse("dispositivos:relevamientos"), {"reasignar": inspeccion.pk}
        )

        form = respuesta.context["form_reasignar"]
        self.assertEqual(set(form.fields["asignado_a"].queryset), {self.otro_agente})


class ReasignarCanceladoTests(BaseCrearRelevamiento):
    def test_el_estado_se_valida_antes_que_el_agente(self):
        inspeccion = crear_inspeccion(
            self._fresco(self.coordinador),
            edificio=self.predio,
            asignado_a=self._fresco(self.agente),
            fecha_vencimiento=self.vence,
        )
        cancelar_inspeccion(self._fresco(self.coordinador), inspeccion, "Ya no hace falta")
        url = reverse("dispositivos:relevamiento_reasignar", args=[inspeccion.pk])

        # El agente actual no es una opción del selector: antes el error era el del agente.
        respuesta = self._cliente(self.coordinador).post(url, {"asignado_a": self.agente.pk}, **AJAX)

        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(respuesta.json()["errors"], {"__all__": [SOLO_EN_CURSO_SE_REASIGNA]})
        inspeccion.refresh_from_db()
        self.assertEqual(inspeccion.estado, InspeccionEdificio.Estado.CANCELADA)


class DobleEnvioDeNovedadTests(BaseBitacora):
    def test_dos_envios_identicos_dejan_una_sola_novedad(self):
        ahora = _local(LUNES, 15)

        primera = self._cargar(ahora)
        segunda = self._cargar(ahora + timedelta(seconds=2))

        self.assertEqual(segunda.pk, primera.pk)
        self.assertEqual(EntradaBitacora.objects.filter(origen=EntradaBitacora.Origen.MANUAL).count(), 1)

    def test_otro_texto_otro_tipo_u_otro_autor_son_novedades_distintas(self):
        ahora = _local(LUNES, 15)
        self._cargar(ahora)

        self._cargar(ahora, texto="Otra cosa distinta.")
        self._cargar(ahora, tipo=EntradaBitacora.Tipo.GENERAL)
        otro = self._operador("Otro operador CIS", self.cis)
        self._cargar(ahora, usuario=otro)

        self.assertEqual(EntradaBitacora.objects.filter(origen=EntradaBitacora.Origen.MANUAL).count(), 4)

    def test_el_mismo_texto_con_otra_persona_o_con_adjuntos_distintos_es_otra_novedad(self):
        ahora = _local(LUNES, 15)
        ana = self._estadia(self.persona, self.cis, ahora - timedelta(days=1))
        juan = self._estadia(self.otra_persona, self.cis, ahora - timedelta(days=1))

        a = self._cargar(ahora, personas=[ana])
        igual = self._cargar(ahora, personas=[ana])
        otra = self._cargar(ahora, personas=[juan])
        con_archivo = self._cargar(
            ahora, personas=[ana], adjuntos=[SimpleUploadedFile("acta.pdf", PDF, content_type="application/pdf")]
        )

        self.assertEqual(igual.pk, a.pk)
        self.assertEqual(len({a.pk, otra.pk, con_archivo.pk}), 3)

    def test_pasada_la_ventana_es_una_novedad_nueva(self):
        ahora = _local(LUNES, 15)
        self._cargar(ahora)

        self._cargar(ahora + timedelta(seconds=30))

        self.assertEqual(EntradaBitacora.objects.filter(origen=EntradaBitacora.Origen.MANUAL).count(), 2)


class CorregirSinCambiosTests(BaseBitacora):
    def test_corregir_con_todo_igual_se_rechaza(self):
        entrada = self._cargar(_local(LUNES, 15))

        with self.assertRaises(ValidationError) as contexto:
            self._corregir(_local(LUNES, 15, 5), entrada, texto=entrada.texto, motivo="Revisé")

        self.assertEqual(contexto.exception.message_dict, {"entrada": [SIN_CAMBIOS_PARA_CORREGIR]})
        self.assertEqual(EntradaBitacora.objects.filter(origen=EntradaBitacora.Origen.MANUAL).count(), 1)

    def test_cambiar_el_tipo_o_el_texto_si_corrige(self):
        entrada = self._cargar(_local(LUNES, 15))

        por_tipo = self._corregir(_local(LUNES, 15, 5), entrada, texto=entrada.texto, tipo=EntradaBitacora.Tipo.GENERAL)
        por_texto = self._corregir(_local(LUNES, 15, 6), por_tipo, texto="Texto distinto.")

        self.assertEqual((por_tipo.version, por_texto.version), (2, 3))


class FueraDeServicioDosVecesTests(BaseMapa):
    def _sacar(self, motivo):
        self.client.force_login(self.operador_cis)
        url = reverse("dispositivos:plaza_fuera_servicio", args=[self.cis.pk, self.plaza.pk])
        return self.client.post(url, {"motivo": motivo}, **AJAX)

    def test_la_segunda_vez_dice_que_ya_estaba_y_no_pisa_el_motivo(self):
        primera = self._sacar("Colchón roto")
        self.assertIn("fuera de servicio.", primera.json()["message"])
        self.plaza.refresh_from_db()
        modificado = self.plaza.modificado

        segunda = self._sacar("Otro motivo")

        self.assertEqual(segunda.status_code, 200)
        self.assertIn("ya estaba fuera de servicio", segunda.json()["message"])
        self.plaza.refresh_from_db()
        self.assertEqual(self.plaza.motivo_fuera_servicio, "Colchón roto")
        self.assertEqual(self.plaza.modificado, modificado)
        self.assertEqual(self.plaza.estado, Plaza.Estado.FUERA_SERVICIO)


class CapacidadDeclaradaTests(BaseMapa):
    def test_un_sector_anterior_al_tope_se_renombra_y_se_da_de_baja_sin_tocar_la_capacidad(self):
        self.sector.capacidad = 50000
        self.sector.save()
        edificio = Edificio.objects.create(codigo="ED-VIEJO", nombre="Edificio viejo")
        edificio.dispositivos.add(self.cis)
        datos = {"nombre": "Renombrado", "tipo": self.sector.tipo, "edificio": edificio, "capacidad": 50000}

        form = SectorForm({**datos, "edificio": edificio.pk, "activo": "on"}, dispositivo=self.cis, sector=self.sector)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertNotIn("max", form.fields["capacidad"].widget.attrs)
        editar_sector(sector=self.sector, usuario=self.operador_cis, **datos)
        self.sector.refresh_from_db()
        self.assertEqual((self.sector.nombre, self.sector.capacidad), ("Renombrado", 50000))

        editar_sector(sector=self.sector, usuario=self.operador_cis, **datos, activo=False)
        self.sector.refresh_from_db()
        self.assertFalse(self.sector.activo)

    def test_en_un_sector_anterior_al_tope_cambiar_la_cifra_por_otra_que_lo_supera_se_rechaza(self):
        self.sector.capacidad = 50000
        self.sector.save()

        form = SectorForm(
            {"nombre": "Varones", "tipo": self.sector.tipo, "capacidad": 60000},
            dispositivo=self.cis,
            sector=self.sector,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("capacidad", form.errors)
        with self.assertRaises(ValidationError):
            editar_sector(
                sector=self.sector, usuario=self.operador_cis, nombre="Varones", tipo=self.sector.tipo, capacidad=60000
            )

    def test_el_formulario_rechaza_mas_del_tope(self):
        datos = {"nombre": "Pabellón", "tipo": "OTRO", "capacidad": 99999999}

        form = SectorForm(datos, dispositivo=self.cis)

        self.assertFalse(form.is_valid())
        self.assertIn("capacidad", form.errors)
        self.assertEqual(form.fields["capacidad"].max_value, CAPACIDAD_DECLARADA_MAXIMA)

    def test_el_servicio_rechaza_mas_del_tope(self):
        with self.assertRaises(ValidationError) as contexto:
            crear_sector(
                dispositivo=self.cis,
                usuario=self.operador_cis,
                nombre="Pabellón",
                tipo="OTRO",
                capacidad=CAPACIDAD_DECLARADA_MAXIMA + 1,
            )

        self.assertIn("capacidad", contexto.exception.message_dict)
