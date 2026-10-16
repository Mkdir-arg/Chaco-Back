"""Carril FH: estado junto al título, acciones intactas y vocabulario institucional."""

import re
from datetime import datetime, timedelta, timezone
from unittest import mock

from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.html import strip_tags

from programas.models import Dispositivo
from programas.services.estadias import egresar_persona, ingresar_persona
from programas.tests.test_dispositivos_estadias import CAPACIDADES_OPERATIVAS, BaseEstadias

ESTADO_JUNTO_H1 = re.compile(r'<h1[^>]*>[^<]+</h1>\s*<span class="badge badge-dot badge-(\w+)">([^<]+)</span>')


class HeaderDispositivosTests(BaseEstadias):
    def setUp(self):
        self.ahora = datetime(2026, 10, 14, 10, tzinfo=timezone.utc)
        self.enterContext(mock.patch("django.utils.timezone.now", return_value=self.ahora))
        super().setUp()
        self.operador = self._operador("Operador FH", self.cis, (*CAPACIDADES_OPERATIVAS, "ciudadano.ver"))
        self.client.force_login(self.operador)

    def assert_estado_header(self, respuesta, texto, tono):
        self.assertEqual(respuesta.status_code, 200)
        html = respuesta.content.decode()
        self.assertEqual(ESTADO_JUNTO_H1.findall(html), [(tono, texto)])
        # El contenedor exclusivo de acciones termina antes del cierre del header.
        acciones = html.split('<div class="flex items-center gap-2 flex-wrap">', 1)[1].split("</div>", 1)[0]
        self.assertNotIn(f">{texto}</span>", acciones)

    def test_p4_y_p19_todos_los_estados_coinciden_con_las_filas(self):
        tonos = ("white", "info", "success", "warning", "danger", "gray", "gray")
        self.assertEqual(len(Dispositivo.Estado.choices), len(tonos))
        for (estado, texto), tono in zip(Dispositivo.Estado.choices, tonos, strict=True):
            self.cis.estado = estado
            self.cis.save(update_fields=["estado"])
            with self.subTest(estado=estado):
                for tab in ("estadias", "infraestructura"):
                    respuesta = self.client.get(reverse("dispositivos:detalle", args=[self.cis.pk]), {"tab": tab})
                    self.assert_estado_header(respuesta, texto, tono)
                    self.assertContains(respuesta, 'aria-label="Volver a Instituciones"')
                fila = render_to_string("programas/dispositivos/_estado_badge.html", {"dispositivo": self.cis})
                self.assertIn(f'class="badge badge-dot badge-{tono}">{texto}</span>', fila)

    def test_p7_estado_de_estadia_activa_y_egresada(self):
        estadia = ingresar_persona(
            ciudadano=self.persona,
            dispositivo=self.cis,
            plaza=self.plaza,
            usuario=self.operador,
            fecha_ingreso=self.ahora - timedelta(days=3),
        )
        url = reverse("dispositivos:estadia_detalle", args=[self.cis.pk, estadia.pk])
        self.assert_estado_header(self.client.get(url), "Alojada", "info")
        egresar_persona(
            destino="Domicilio",
            estadia=estadia,
            usuario=self.operador,
            motivo_egreso=self.motivo_alta,
            fecha_egreso=self.ahora,
        )
        self.assert_estado_header(self.client.get(url), "Egresada", "gray")

    def test_sidebar_y_migas_del_listado_se_llaman_instituciones(self):
        respuesta = self.client.get(reverse("dispositivos:detalle", args=[self.cis.pk]))
        html = respuesta.content.decode()
        enlace = re.search(
            r'<a\b[^>]*href="' + re.escape(reverse("dispositivos:lista")) + r'"[^>]*>(.*?)</a>', html, re.S
        )
        self.assertIsNotNone(enlace)
        self.assertEqual(strip_tags(enlace[1]).strip(), "Instituciones")
        self.assertContains(respuesta, reverse("legajos:ciudadanos"))
        for nombre in ("sectores", "bitacora"):
            detalle = self.client.get(reverse(f"dispositivos:{nombre}", args=[self.cis.pk]))
            self.assertEqual(detalle.context["migas"][0]["label"], "Instituciones")
