"""Segunda pasada MVP: formulario canónico, rótulos y lecturas perezosas de P4."""

import json
import re
from datetime import timedelta
from unittest.mock import patch

from django.conf import settings
from django.db import connection
from django.template.loader import render_to_string
from django.test import tag
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from programas.models import Estadia, ReservaPlaza
from programas.services.ingreso import plazas_para_ingresar
from programas.tests.test_dispositivos_detalle import BaseDetalle, _alojar
from programas.tests.test_dispositivos_fidelidad_fd import AHORA


class FidelidadFFTests(BaseDetalle):
    def setUp(self):
        reloj = patch("django.utils.timezone.now", return_value=AHORA)
        reloj.start()
        self.addCleanup(reloj.stop)
        super().setUp()
        self.operador.is_superuser = True
        self.operador.save()
        self.client.force_login(self.operador)

    def test_formulario_alta_y_edicion_conserva_campos_post_y_acciones(self):
        # FI (Cambio 308): en edición el pie dice «Guardar cambios»; el margen de cada título
        # de sección depende de su bloque, así que se fija el título y no el margen.
        for url, titulo, volver, guardar in (
            (reverse("dispositivos:crear"), "Nueva institución", reverse("dispositivos:lista"), "Guardar borrador"),
            (reverse("dispositivos:editar", args=[self.cis.pk]), "Editar institución", self.url, "Guardar cambios"),
        ):
            with self.subTest(titulo=titulo):
                respuesta = self.client.get(url)
                self.assertContains(
                    respuesta,
                    f'<h1 class="text-3xl font-extrabold text-heading tracking-tight">{titulo}</h1>',
                    html=True,
                )
                self.assertContains(respuesta, "Legajo institucional")
                self.assertContains(respuesta, f'href="{volver}"')
                # El form es un contenedor y la tarjeta de datos es su primer hijo (P3).
                self.assertContains(
                    respuesta,
                    '<form method="post" enctype="multipart/form-data" class="space-y-5">',
                )
                self.assertRegex(
                    respuesta.content.decode(),
                    r'<form method="post"[^>]*>\s*<input[^>]*csrfmiddlewaretoken[^>]*>\s*'
                    r'<div class="bg-white rounded-xl border border-base shadow-sm p-6">',
                )
                self.assertContains(respuesta, 'name="csrfmiddlewaretoken"')
                for nombre in respuesta.context["form"].fields:
                    self.assertContains(respuesta, f'name="{nombre}"', count=1)
                self.assertContains(respuesta, "Cancelar")
                self.assertContains(respuesta, guardar)
                for seccion in ("Identidad y encuadre", "Ubicación", "Responsable y contacto"):
                    self.assertRegex(
                        respuesta.content.decode(), rf'<h2 class="text-heading font-bold[^"]*">{seccion}</h2>'
                    )

    def test_aviso_de_duplicados_usa_la_alerta_canonica_solo_en_alta(self):
        respuesta = self.client.get(reverse("dispositivos:crear"))
        alerta = render_to_string(
            "components/_alerta.html",
            {"tono": "warning", "contenido_template": "programas/dispositivos/legajo/_duplicados.html"},
        )
        self.assertInHTML(alerta, respuesta.content.decode())
        # FJ: el aviso recibe el foco cuando un código repetido bloquea el envío.
        self.assertContains(respuesta, '<div id="duplicate-search" class="hidden" tabindex="-1">')
        self.assertNotContains(
            self.client.get(reverse("dispositivos:editar", args=[self.cis.pk])), 'id="duplicate-search"'
        )

    def test_cerrar_es_terciario_y_conserva_confirmacion_destructiva(self):
        html = self.client.get(self.url).content.decode()
        boton = re.search(
            r'<button[^>]+data-confirm-url="'
            + re.escape(reverse("dispositivos:cerrar", args=[self.cis.pk]))
            + r'"[^>]*>Cerrar</button>',
            html,
        ).group()
        self.assertIn('class="btn-nodo btn-tertiary btn-sm btn-fit"', boton)
        self.assertIn('data-confirm-danger="true"', boton)
        self.assertIn('data-confirm-ok="Sí, cerrar"', boton)
        self.assertIn('data-confirm-url="' + reverse("dispositivos:inactivar", args=[self.cis.pk]) + '"', html)

    def test_p5_nombra_reservas_y_prestamos_en_ambos_resumenes(self):
        ReservaPlaza.objects.create(
            plaza=self.plaza,
            ciudadano=self.persona,
            tipo=ReservaPlaza.Tipo.PRESTAMO,
            desde=AHORA - timedelta(hours=1),
            hasta=AHORA + timedelta(hours=1),
        )
        respuesta = self.client.get(reverse("dispositivos:sectores", args=[self.cis.pk]))
        self.assertContains(respuesta, "0 reservadas · 1 prestada · ", count=2)
        self.assertContains(
            respuesta,
            '<p class="text-xs font-semibold uppercase tracking-wide text-fg-brand mb-1">' + self.cis.nombre + "</p>",
            html=True,
        )
        bajada = re.search(
            r'<p class="text-sm text-body-subtle mt-1">(.*?)</p>', respuesta.content.decode(), re.S
        ).group(1)
        self.assertNotIn(self.cis.nombre, bajada)

    def test_no_busca_plazas_sin_filas_activas_con_plaza(self):
        self.operador.is_superuser = False
        self.operador.save()
        self.client.force_login(self.operador)
        with patch("programas.views.dispositivos_legajo.plazas_para_ingresar", wraps=plazas_para_ingresar) as mapa:
            self.assertEqual(self.client.get(self.url).status_code, 200)
            cerrada = _alojar(self.cis, self.plaza, self.persona, AHORA - timedelta(days=2))
            Estadia.objects.filter(pk=cerrada.pk).update(
                estado=Estadia.Estado.EGRESADA, fecha_egreso=AHORA, clave_alojamiento=None
            )
            _alojar(self.cis, None, self.otra_persona, AHORA - timedelta(days=1))
            self.assertEqual(self.client.get(self.url, {"estado": "TODAS"}).status_code, 200)
        mapa.assert_not_called()

    def test_menu_y_modal_comparten_una_sola_lectura_de_plazas(self):
        activa = _alojar(self.cis, self.plaza, self.persona, AHORA - timedelta(days=2))
        with patch("programas.views.dispositivos_legajo.plazas_para_ingresar", wraps=plazas_para_ingresar) as mapa:
            respuesta = self.client.get(self.url, {"cambio": activa.pk})
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("form_cambio", respuesta.context)
        mapa.assert_called_once()

    def test_modal_busca_plazas_aunque_la_fila_no_este_en_la_pagina(self):
        activa = _alojar(self.cis, self.plaza, self.persona, AHORA - timedelta(days=2))
        with patch("programas.views.dispositivos_legajo.plazas_para_ingresar", wraps=plazas_para_ingresar) as mapa:
            respuesta = self.client.get(self.url, {"estado": "EGRESADA", "cambio": activa.pk})
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(respuesta.context["estadias"]), 0)
        self.assertIn("form_cambio", respuesta.context)
        mapa.assert_called_once()


@tag("performance")
class PresupuestoDetalleFFTests(BaseDetalle):
    def setUp(self):
        reloj = patch("django.utils.timezone.now", return_value=AHORA)
        reloj.start()
        self.addCleanup(reloj.stop)
        super().setUp()
        self.operador.is_superuser = True
        self.operador.save()
        self.client.force_login(self.operador)

    def test_detalle_sin_estadias_en_cada_solapa_no_paga_el_mapa_de_ingreso(self):
        presupuestos = json.loads((settings.BASE_DIR / "scripts/perf_budgets.json").read_text(encoding="utf-8"))
        techo = presupuestos["servicios"]["dispositivos_detalle_sin_estadias"]["consultas_fijas"]
        for tab in ("datos", "sectores", "estadias", "infraestructura", "historial"):
            with self.subTest(tab=tab):
                with CaptureQueriesContext(connection) as consultas:
                    respuesta = self.client.get(self.url, {"tab": tab})
                self.assertEqual(respuesta.status_code, 200)
                self.assertLessEqual(len(consultas), techo, f"{tab}: {len(consultas)} consultas")
