"""«Crear relevamiento» desde la solapa Infraestructura de P4 (MVP v2, P21 · #701).

Lo que se fija acá, y por qué:

1. **El botón es de quien puede asignar y solo aparece si hay algo que asignar**: sin
   `inspeccion.asignar`, o con todos los edificios ya en curso, o sin edificios, no hay botón.
2. **El edificio se elige en el modal**: con uno solo elegible va fijo; con varios, el
   selector lista únicamente los que no tienen un relevamiento en curso.
3. **El agente se valida contra el edificio elegido.** El selector ofrece la unión de los
   agentes asignables; el servicio rechaza al que es personal del edificio que se eligió.
4. **El POST lo decide el servidor**: capacidad, edificio del dispositivo, edificio libre.
5. **El costo de P4 no crece con los edificios.**
"""

import re
from datetime import timedelta

from django.db import connection
from django.test import Client, tag
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from programas.models import Edificio, InspeccionEdificio
from programas.tests.test_dispositivos_inspecciones import BaseInspecciones

AJAX = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}
BOTON = '@click="modalRelevamiento=true"'


class BaseCrearRelevamiento(BaseInspecciones):
    def setUp(self):
        super().setUp()
        self._clientes = {}
        self.url_parador = reverse("dispositivos:detalle", args=[self.parador.pk])
        self.url_post = reverse("dispositivos:relevamiento_asignar_dispositivo", args=[self.parador.pk])
        self.personal_geriatrico = self._usuario("personal_geriatrico", ("inspeccion.relevar",), [self.geriatrico])
        # Quien además puede vincular (el edificio del CIS es vinculable): la página trae los dos modales.
        self.admin_p4 = self._usuario(
            "admin_p4", ("inspeccion.asignar", "dispositivo.ver", "dispositivo.editar"), [self.parador, self.cis]
        )

    def _cliente(self, usuario):
        # Uno por usuario: el backoffice admite una sola sesión, y un segundo login invalida el primero.
        if usuario.pk not in self._clientes:
            self._clientes[usuario.pk] = Client()
            self._clientes[usuario.pk].force_login(usuario)
        return self._clientes[usuario.pk]

    def _detalle(self, usuario, dispositivo=None, **parametros):
        url = reverse("dispositivos:detalle", args=[(dispositivo or self.parador).pk])
        return self._cliente(usuario).get(url, {"tab": "infraestructura", **parametros})

    def _edificio_extra(self, codigo="ED-EXTRA"):
        edificio = Edificio.objects.create(codigo=codigo, nombre=f"Edificio {codigo}")
        edificio.dispositivos.add(self.parador)
        return edificio

    def _datos(self, edificio=None, agente=None, **extra):
        datos = {
            "asignado_a": (agente or self.agente).pk,
            "fecha_vencimiento": (timezone.localdate() + timedelta(days=15)).isoformat(),
            "indicaciones": "Revisar el techo",
        }
        if edificio is not None:
            datos["edificio"] = edificio.pk
        datos.update(extra)
        return datos

    def _post(self, datos, usuario=None):
        return self._cliente(usuario or self.coordinador).post(self.url_post, datos, **AJAX)

    def _en_curso(self, edificio):
        return InspeccionEdificio.objects.create(
            edificio=edificio,
            asignado_a=self.otro_agente,
            creado_por=self.coordinador,
            fecha_vencimiento=self.vence,
        )

    def _agentes_del_selector(self, **parametros):
        form = self._detalle(self.coordinador, **parametros).context["form_relevamiento"]
        return set(form.fields["asignado_a"].queryset)


class BotonTests(BaseCrearRelevamiento):
    def test_el_coordinador_con_un_edificio_libre_ve_el_boton(self):
        respuesta = self._detalle(self.coordinador)

        self.assertTrue(respuesta.context["puede_crear_relevamiento"])
        self.assertContains(respuesta, BOTON)
        self.assertContains(respuesta, "Crear relevamiento")

    def test_quien_no_tiene_inspeccion_asignar_no_ve_el_boton(self):
        operador = self._usuario("operador_p4", ("dispositivo.ver", "dispositivo.editar"), [self.parador])

        respuesta = self._detalle(operador)

        self.assertFalse(respuesta.context["puede_crear_relevamiento"])
        self.assertNotContains(respuesta, BOTON)

    def test_sin_edificios_no_hay_boton(self):
        coord = self._usuario("coord_sin_edificio", ("inspeccion.asignar", "dispositivo.ver"), [self.sin_edificio])

        respuesta = self._detalle(coord, self.sin_edificio)

        self.assertFalse(respuesta.context["puede_crear_relevamiento"])
        self.assertNotContains(respuesta, BOTON)

    def test_si_todos_los_edificios_tienen_uno_en_curso_no_hay_boton(self):
        self._en_curso(self.predio)

        respuesta = self._detalle(self.coordinador)

        self.assertFalse(respuesta.context["puede_crear_relevamiento"])
        self.assertNotContains(respuesta, BOTON)

    def test_el_formulario_llega_con_la_pagina_solo_a_quien_puede_y_hay_elegibles(self):
        con = self._detalle(self.coordinador)
        self.assertIn("form_relevamiento", con.context)
        self.assertContains(con, 'x-show="modalRelevamiento"')
        self.assertContains(con, "modalRelevamiento: false")

        operador = self._usuario("operador_sin_asignar", ("dispositivo.ver", "dispositivo.editar"), [self.parador])
        sin_capacidad = self._detalle(operador)
        self.assertNotIn("form_relevamiento", sin_capacidad.context)
        self.assertNotContains(sin_capacidad, 'x-show="modalRelevamiento"')

        self._en_curso(self.predio)
        sin_elegibles = self._detalle(self.coordinador)
        self.assertNotIn("form_relevamiento", sin_elegibles.context)
        self.assertNotContains(sin_elegibles, 'x-show="modalRelevamiento"')

    def test_un_enlace_viejo_con_el_parametro_se_ignora_en_silencio(self):
        respuesta = self._detalle(self.coordinador, relevamiento="nuevo")

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "modalRelevamiento: false")

    def test_la_pantalla_no_repite_ids_con_el_modal_y_el_de_vincular_abiertos(self):
        self._edificio_extra()
        html = self._detalle(self.admin_p4, edificio="vincular").content.decode()

        ids = re.findall(r'id="([^"]+)"', html)
        repetidos = sorted({i for i in ids if ids.count(i) > 1})
        self.assertIn('id="relev_edificio"', html)
        self.assertIn('id="id_edificio"', html)
        self.assertEqual(repetidos, [])


class ModalTests(BaseCrearRelevamiento):
    def test_con_un_solo_edificio_elegible_va_fijo_y_de_solo_lectura(self):
        respuesta = self._detalle(self.coordinador)

        form = respuesta.context["form_relevamiento"]
        self.assertTrue(form.edificio_fijo)
        self.assertEqual([valor for valor, _ in form.fields["edificio"].choices], [str(self.predio.pk)])
        self.assertContains(respuesta, 'id="relev_edificio"')
        self.assertContains(respuesta, "disabled")
        self.assertContains(respuesta, self.url_post)

    def test_con_varios_el_selector_lista_solo_los_que_no_tienen_uno_en_curso(self):
        libre = self._edificio_extra("ED-LIBRE")
        ocupado = self._edificio_extra("ED-OCUPADO")
        self._en_curso(ocupado)

        form = self._detalle(self.coordinador).context["form_relevamiento"]

        self.assertFalse(form.edificio_fijo)
        valores = [valor for valor, _ in form.fields["edificio"].choices]
        self.assertEqual(valores[0], "")
        self.assertCountEqual(valores[1:], [str(libre.pk), str(self.predio.pk)])
        self.assertNotIn(str(ocupado.pk), valores)

    def test_el_selector_de_agentes_es_por_capacidad_y_sin_el_personal(self):
        agentes = self._agentes_del_selector()

        self.assertIn(self.agente, agentes)
        self.assertIn(self.otro_agente, agentes)
        # Personal de la institución relevada: nunca.
        self.assertNotIn(self.personal_parador, agentes)
        # Sin `inspeccion.relevar` no es candidato, aunque coordine.
        self.assertNotIn(self.coordinador, agentes)

    def test_con_varios_el_personal_de_un_solo_edificio_sigue_en_el_selector(self):
        self._edificio_extra()

        agentes = self._agentes_del_selector()

        # Personal del geriátrico = del predio, pero no del edificio extra: se valida al elegir.
        self.assertIn(self.personal_geriatrico, agentes)
        self.assertNotIn(self.personal_parador, agentes)


class PostTests(BaseCrearRelevamiento):
    def test_crea_el_relevamiento_y_vuelve_a_la_solapa_infraestructura(self):
        respuesta = self._post(self._datos(self.predio))

        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        cuerpo = respuesta.json()
        self.assertTrue(cuerpo["ok"])
        self.assertEqual(cuerpo["redirect"], f"{self.url_parador}?tab=infraestructura")
        creado = InspeccionEdificio.objects.get()
        self.assertEqual(creado.edificio, self.predio)
        self.assertEqual(creado.asignado_a, self.agente)
        self.assertEqual(creado.creado_por, self.coordinador)
        self.assertEqual(creado.indicaciones, "Revisar el techo")

    def test_con_el_edificio_fijo_no_se_puede_cambiar_por_el_post(self):
        # Un solo elegible: el campo está deshabilitado y usa el inicial, no lo que llegue.
        respuesta = self._post(self._datos(self.edificio_cis))

        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        self.assertEqual(InspeccionEdificio.objects.get().edificio, self.predio)

    def test_con_varios_el_edificio_elegido_manda(self):
        otro = self._edificio_extra()

        self.assertEqual(self._post(self._datos(otro)).status_code, 200)

        self.assertEqual(InspeccionEdificio.objects.get().edificio, otro)

    def test_rechaza_sin_la_capacidad(self):
        operador = self._usuario("operador_post", ("dispositivo.ver", "dispositivo.editar"), [self.parador])

        respuesta = self._post(self._datos(self.predio), usuario=operador)

        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(InspeccionEdificio.objects.exists())

    def test_rechaza_un_edificio_ajeno_al_dispositivo(self):
        self._edificio_extra()  # con dos elegibles el campo no es fijo y lo enviado cuenta

        respuesta = self._post(self._datos(self.edificio_cis))

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("edificio", respuesta.json()["errors"])
        self.assertFalse(InspeccionEdificio.objects.exists())

    def test_rechaza_un_edificio_ajeno_aunque_quien_asigna_tenga_alcance_sobre_el(self):
        self._edificio_extra()
        coord_ambos = self._usuario("coord_ambos", ("inspeccion.asignar", "dispositivo.ver"), [self.parador, self.cis])

        respuesta = self._post(self._datos(self.edificio_cis), usuario=coord_ambos)

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("edificio", respuesta.json()["errors"])
        self.assertFalse(InspeccionEdificio.objects.exists())

    def test_rechaza_un_edificio_con_uno_en_curso(self):
        libre = self._edificio_extra()
        self._edificio_extra("ED-OTRO")  # con dos libres el campo no es fijo y lo enviado cuenta
        self._en_curso(self.predio)

        respuesta = self._post(self._datos(self.predio))

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("edificio", respuesta.json()["errors"])
        self.assertEqual(InspeccionEdificio.objects.count(), 1)
        self.assertEqual(self._post(self._datos(libre)).status_code, 200)

    def test_rechaza_un_territorial_que_es_personal_del_edificio(self):
        respuesta = self._post(self._datos(self.predio, agente=self.personal_parador))

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("asignado_a", respuesta.json()["errors"])
        self.assertFalse(InspeccionEdificio.objects.exists())

    def test_rechaza_un_territorial_valido_para_otro_edificio_pero_no_para_el_elegido(self):
        otro = self._edificio_extra()

        # Personal del geriátrico: ocupa el predio, no el edificio extra.
        en_predio = self._post(self._datos(self.predio, agente=self.personal_geriatrico))
        en_otro = self._post(self._datos(otro, agente=self.personal_geriatrico))

        self.assertEqual(en_predio.status_code, 400)
        self.assertIn("asignado_a", en_predio.json()["errors"])
        self.assertEqual(en_otro.status_code, 200, en_otro.content)
        self.assertEqual(InspeccionEdificio.objects.get().edificio, otro)

    def test_rechaza_un_usuario_sin_inspeccion_relevar(self):
        respuesta = self._post(self._datos(self.predio, agente=self.coordinador))

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("asignado_a", respuesta.json()["errors"])

    def test_el_vencimiento_es_obligatorio(self):
        respuesta = self._post(self._datos(self.predio, fecha_vencimiento=""))

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("fecha_vencimiento", respuesta.json()["errors"])
        self.assertFalse(InspeccionEdificio.objects.exists())

    def test_el_vencimiento_no_puede_ser_anterior_a_hoy(self):
        ayer = (timezone.localdate() - timedelta(days=1)).isoformat()

        respuesta = self._post(self._datos(self.predio, fecha_vencimiento=ayer))

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("fecha_vencimiento", respuesta.json()["errors"])

    def test_un_dispositivo_inexistente_es_404(self):
        url = reverse("dispositivos:relevamiento_asignar_dispositivo", args=[999999])

        respuesta = self._cliente(self.coordinador).post(url, self._datos(self.predio), **AJAX)

        self.assertEqual(respuesta.status_code, 404)

    def test_sin_alcance_sobre_los_edificios_no_crea_nada(self):
        coord_cis = self._usuario("coord_cis_post", ("inspeccion.asignar", "dispositivo.ver"), [self.cis])

        respuesta = self._post(self._datos(self.predio), usuario=coord_cis)

        self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(InspeccionEdificio.objects.exists())


@tag("performance")
class CostoTests(BaseCrearRelevamiento):
    def _consultas(self, **parametros):
        self._detalle(self.coordinador, **parametros)  # calienta caches
        with CaptureQueriesContext(connection) as captura:
            self.assertEqual(self._detalle(self.coordinador, **parametros).status_code, 200)
        return len(captura)

    def test_el_costo_no_crece_con_los_edificios(self):
        self._edificio_extra("ED-A")
        pocos = self._consultas()
        for n in range(6):
            self._edificio_extra(f"ED-M{n}")

        self.assertEqual(self._consultas(), pocos)
