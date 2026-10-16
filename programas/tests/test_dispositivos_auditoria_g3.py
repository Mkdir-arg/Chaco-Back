"""G3: guardas y fidelidad del relevamiento, con reloj fijo y sin cambiar el contrato de campo."""

from datetime import timedelta
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import connection
from django.template.loader import render_to_string
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from programas.models import InspeccionEdificio, TrazaDispositivo
from programas.services.detalle_dispositivo import infraestructura_del_dispositivo
from programas.services.edificios import RELEVAMIENTO_EN_CURSO, desvincular_edificio
from programas.services.inspecciones import (
    agregar_foto,
    cancelar_inspeccion,
    marcar_revisado,
    semaforos_de_dispositivos,
)
from programas.tests.test_dispositivos_fidelidad_fd import AHORA
from programas.tests.test_dispositivos_infraestructura import BaseInfraestructura
from programas.tests.test_dispositivos_inspecciones import _foto
from programas.tests.test_dispositivos_relevamientos_listado import URL_LISTA, BaseListado

Criticidad = InspeccionEdificio.Criticidad


class RelojFijo:
    def setUp(self):
        reloj = patch("django.utils.timezone.now", return_value=AHORA)
        reloj.start()
        self.addCleanup(reloj.stop)
        super().setUp()


class InfraestructuraTests(RelojFijo, BaseInfraestructura):
    def test_revisado_lleva_badge_verde_autoria_y_fecha_sin_perder_criticidad(self):
        self.coordinador.first_name = "Ana Revisora"
        self.coordinador.save(update_fields=["first_name"])
        for _ in range(3):
            inspeccion = self._relevar(self.predio, Criticidad.ALTA)
            marcar_revisado(self._fresco(self.coordinador), inspeccion)

        datos = infraestructura_del_dispositivo(self.parador)
        with self.assertNumQueries(0):
            # El revisor viaja en la consulta de la página, nunca se lee por evento.
            for relevamiento in datos["relevamientos"]:
                self.assertEqual(relevamiento.revisado_por.first_name, "Ana Revisora")
        html = render_to_string("components/_linea_tiempo.html", {"eventos": datos["eventos"]})
        self.assertEqual(html.count('class="badge badge-success">Revisado</span>'), 3)
        for evento in datos["eventos"]:
            self.assertIn("revisado por Ana Revisora el 14/10/2026 09:00", evento["cuando"])
            self.assertIn("Crítico", evento["detalle"])
            self.assertEqual(evento["tono"], "danger")

    def test_revisor_se_carga_en_lote_en_la_consulta_de_la_pagina(self):
        inspeccion = self._relevar(self.predio, Criticidad.MEDIA)
        marcar_revisado(self._fresco(self.coordinador), inspeccion)
        with CaptureQueriesContext(connection) as consultas:
            infraestructura_del_dispositivo(self.parador)
        # Ninguna consulta aislada a auth_user: el revisor va con JOIN en la página.
        tabla_usuario = connection.ops.quote_name("auth_user")
        self.assertFalse(any(f"FROM {tabla_usuario}" in consulta["sql"] for consulta in consultas))

    def test_foto_en_curso_conserva_fecha_de_carga(self):
        inspeccion = self._crear()
        foto = agregar_foto(self._fresco(self.agente), inspeccion, _foto())
        datos = infraestructura_del_dispositivo(self.parador)
        self.assertEqual(datos["eventos"][0]["fotos"][0]["fecha"], foto.creado)
        self.assertEqual(foto.creado, AHORA)

    def test_critico_prevalece_en_p2_p4_y_p19_con_vencido_en_otro_edificio(self):
        """Decisión PM G3: Crítico no se atenúa a warning por otro edificio vencido."""
        self._relevar(self.predio, Criticidad.ALTA)
        self.edificio_cis.dispositivos.add(self.parador)
        pendiente = self._crear(edificio=self.edificio_cis)
        InspeccionEdificio.objects.filter(pk=pendiente.pk).update(fecha_vencimiento=AHORA.date() - timedelta(days=1))
        semaforo = semaforos_de_dispositivos([self.parador.pk])[self.parador.pk]
        self.assertEqual((semaforo.texto, semaforo.tono), ("Crítico", "danger"))
        self.assertEqual(infraestructura_del_dispositivo(self.parador)["semaforo"], semaforo)
        lista = self._cliente(self.admin).get(reverse("dispositivos:lista"))
        self.assertContains(lista, "Crítico")
        detalle = self._detalle(self.admin, self.parador, tab="infraestructura")
        self.assertEqual(detalle.context["infraestructura"]["semaforo"], semaforo)
        self.assertContains(detalle, "Crítico")

    def test_vencido_solo_cede_ante_la_ultima_realizada_alta(self):
        for criticidad in (None, Criticidad.BAJA, Criticidad.MEDIA, Criticidad.ALTA):
            with self.subTest(criticidad=criticidad):
                if criticidad:
                    self._relevar(self.predio, criticidad)
                inspeccion = self._crear()
                InspeccionEdificio.objects.filter(pk=inspeccion.pk).update(
                    fecha_vencimiento=AHORA.date() - timedelta(days=1)
                )
                semaforo = semaforos_de_dispositivos([self.parador.pk])[self.parador.pk]
                esperado = ("Crítico", "danger") if criticidad == Criticidad.ALTA else ("Vencido", "warning")
                self.assertEqual((semaforo.texto, semaforo.tono), esperado)
                self.assertEqual(infraestructura_del_dispositivo(self.parador)["semaforo"], semaforo)
                cancelar_inspeccion(self._fresco(self.admin), inspeccion, "Fin del escenario")

    def test_predio_compartido_no_pierde_el_ultimo_dispositivo_si_hay_relevamiento_en_curso(self):
        inspeccion = self._crear()
        desvincular_edificio(edificio=self.predio, dispositivo=self.parador, usuario=self._fresco(self.admin))
        self.assertEqual(list(self.predio.dispositivos.all()), [self.geriatrico])
        trazas = TrazaDispositivo.objects.count()

        with self.assertRaises(ValidationError) as error:
            desvincular_edificio(edificio=self.predio, dispositivo=self.geriatrico, usuario=self._fresco(self.admin))

        self.assertEqual(error.exception.message_dict, {"__all__": [RELEVAMIENTO_EN_CURSO]})
        self.assertEqual(list(self.predio.dispositivos.all()), [self.geriatrico])
        self.assertEqual(TrazaDispositivo.objects.count(), trazas)
        cancelar_inspeccion(self._fresco(self.admin), inspeccion, "Ya no se requiere")
        desvincular_edificio(edificio=self.predio, dispositivo=self.geriatrico, usuario=self._fresco(self.admin))
        self.assertFalse(self.predio.dispositivos.exists())


class ListadoTests(RelojFijo, BaseListado):
    def test_modal_asignar_orden_del_mockup_y_contrato_post(self):
        respuesta = self._cliente(self.coord).get(URL_LISTA, {"asignar": self.predio.pk})
        self.assertEqual(respuesta.status_code, 200)
        html = respuesta.content.decode()
        campos = ["edificio", "asignado_a", "fecha_vencimiento", "indicaciones"]
        posiciones = [html.index(f'for="id_{campo}"') for campo in campos]
        self.assertEqual(posiciones, sorted(posiciones))
        for campo in campos:
            self.assertIn(f'name="{campo}"', html)
        self.assertIn(f'action="{reverse("dispositivos:relevamiento_asignar", args=[self.predio.pk])}"', html)

    def test_cancelado_mantiene_el_alcance_y_abre_informe_con_motivo_y_galeria(self):
        inspeccion = self._crear()
        agregar_foto(self._fresco(self.agente), inspeccion, _foto(), "Fachada cancelada")
        cancelar_inspeccion(self._fresco(self.coord), inspeccion, "Obra suspendida")
        cliente = self._cliente(self.coord)
        respuesta = cliente.get(URL_LISTA, {"tab": "cancelados"})
        fila = next(s for s in respuesta.context["solapas"] if s["clave"] == "cancelados")["filas"][0]
        informe = cliente.get(fila.url_informe)
        self.assertContains(informe, "Obra suspendida")
        self.assertContains(informe, "Fachada cancelada")
        ajeno = self._usuario("coord_ajeno_g3", ("inspeccion.asignar",), [self.cis])
        ajeno_cliente = self._cliente(ajeno)
        listado_ajeno = ajeno_cliente.get(URL_LISTA, {"tab": "cancelados"})
        self.assertNotContains(listado_ajeno, fila.url_informe)
        self.assertEqual(ajeno_cliente.get(fila.url_informe).status_code, 404)
