"""FD: DNI solo en presentación y medición del ancho real en las pantallas MVP.

El pase de navegador se activa con CHACO_PLAYWRIGHT=1; Playwright/Chromium puede
vivir en un venv temporal, expuesto mediante PYTHONPATH, sin dependencia productiva.
"""

import os
from datetime import datetime, time, timedelta, timezone
from io import BytesIO
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.template.loader import render_to_string
from django.test import RequestFactory
from django.urls import reverse
from PIL import Image, ImageChops

from core.models import Localidad, Municipio, Provincia, Secretaria, Subsecretaria
from programas.models import (
    Convocatoria,
    Dispositivo,
    Edificio,
    Formulario,
    InspeccionEdificio,
    Plaza,
    Programa,
    Relevamiento,
    ReservaPlaza,
    Segmento,
    Turno,
)
from programas.tests.test_dispositivos_detalle import BaseDetalle, _alojar
from programas.tests.test_dispositivos_ingreso import BaseIngreso

AHORA = datetime(2026, 10, 14, 12, tzinfo=timezone.utc)


class DniEnDispositivosTests(BaseDetalle):
    def setUp(self):
        reloj = patch("django.utils.timezone.now", return_value=AHORA)
        reloj.start()
        self.addCleanup(reloj.stop)
        super().setUp()
        self.persona.dni = "12345678"
        self.persona.save()
        self.estadia = _alojar(self.cis, self.plaza, self.persona, AHORA - timedelta(days=2))

    def test_p4_y_p7_presentan_el_dni_sin_modificar_la_identidad(self):
        for url in (self.url, reverse("dispositivos:estadia_detalle", args=[self.cis.pk, self.estadia.pk])):
            with self.subTest(url=url):
                self.assertContains(self.client.get(url), "DNI 12.345.678")
        p7 = self.client.get(reverse("dispositivos:estadia_detalle", args=[self.cis.pk, self.estadia.pk]))
        self.assertContains(p7, '<dd class="mt-1 text-sm text-body">12.345.678</dd>', html=True)
        self.persona.refresh_from_db()
        self.assertEqual(self.persona.dni, "12345678")

    def test_p16_y_la_golden_de_revision_presentan_el_mismo_dni(self):
        request = RequestFactory().get("/")
        request.user = self.operador
        for nombre in ("legajos/solapas/dispositivos.html", "programas/dispositivos/estadia/revision_referencia.html"):
            with self.subTest(template=nombre):
                html = render_to_string(nombre, {"ciudadano": self.persona, "persona": self.persona}, request=request)
                self.assertIn("DNI 12.345.678", html)


class DniEnIngresoTests(BaseIngreso):
    def setUp(self):
        reloj = patch("django.utils.timezone.now", return_value=AHORA)
        reloj.start()
        self.addCleanup(reloj.stop)
        super().setUp()
        self.persona.dni = "12345678"
        self.persona.save()

    def test_p6_busca_sin_puntos_muestra_con_puntos_y_guarda_sin_puntos(self):
        self.assertRedirects(self.client.post(self.url_persona, {"dni": "12345678"}), self.url_plaza)
        self.assertContains(self.client.get(self.url_plaza), "12.345.678")
        self._elegir_plaza(self.plaza)
        self.assertContains(self.client.get(self.url_confirmar), "12.345.678")
        self.assertRedirects(self._confirmar(), reverse("dispositivos:detalle", args=[self.cis.pk]))
        self.persona.refresh_from_db()
        self.assertEqual(self.persona.dni, "12345678")


@skipUnless(os.environ.get("CHACO_PLAYWRIGHT") == "1", "Requiere Playwright y Chromium en el entorno de prueba")
class DispositivosResponsiveFDTests(StaticLiveServerTestCase):
    def setUp(self):
        from playwright.sync_api import sync_playwright

        super().setUp()
        reloj = patch("django.utils.timezone.now", return_value=AHORA)
        reloj.start()
        self.addCleanup(reloj.stop)
        self.terreno = BaseDetalle()
        self.terreno.client = self.client
        self.terreno.setUp()
        f = self.terreno
        # Administrador ficticio: todas las acciones y P21 visibles en la misma sesión.
        f.operador.is_superuser = True
        f.operador.save()
        self.client.force_login(f.operador)
        self.estadia = _alojar(f.cis, f.plaza, f.persona, AHORA - timedelta(days=2))
        Plaza.objects.create(
            sector=f.sector, codigo="P3", estado=Plaza.Estado.FUERA_SERVICIO, motivo_fuera_servicio="Colchón"
        )
        ReservaPlaza.objects.create(
            plaza=f.otra_plaza,
            ciudadano=f.otra_persona,
            desde=AHORA - timedelta(days=2),
            hasta=AHORA - timedelta(days=1),
        )
        f.cis.contacto_email = "contacto.del.centro.integrador.territorial@example.test"
        f.cis.latitud, f.cis.longitud = "-27.451120", "-58.986340"
        f.cis.save()
        nombre_largo = "Centro de Integración Social y Acompañamiento Comunitario de Resistencia"
        self.assertGreaterEqual(len(nombre_largo), 60)
        Dispositivo.objects.create(codigo="FF-LARGO", nombre=nombre_largo, tipo=f.tipo, localidad="Resistencia")
        f.tipo.nombre = "Centro de Atención Integral y Acompañamiento a Personas en Situación de Vulnerabilidad"
        f.tipo.save()
        f.persona.nombre = "María de los Ángeles"
        f.persona.apellido = "Fernández de la Comunidad"
        f.persona.save()
        provincia = Provincia.objects.create(nombre="Provincia del Chaco para la prueba de tablas con nombres largos")
        municipio = Municipio.objects.create(
            nombre="Municipalidad de Presidencia Roque Sáenz Peña", provincia=provincia
        )
        Localidad.objects.create(nombre="Localidad de Presidencia Roque Sáenz Peña", municipio=municipio)
        secretaria = Secretaria.objects.create(nombre="Secretaría de Desarrollo Social y Acompañamiento Comunitario")
        Subsecretaria.objects.create(
            nombre="Subsecretaría de Abordaje Psicosocial y Atención Comunitaria", secretaria=secretaria
        )
        Programa.objects.create(codigo="BECAS", nombre="Programa de Becas para Acompañamiento Comunitario")
        segmento = Segmento.objects.create(
            nombre="Estudiantes en situación de vulnerabilidad socioeconómica", cupo_maximo=100
        )
        convocatoria = Convocatoria.objects.create(
            nombre="Convocatoria de acompañamiento para estudiantes de la provincia del Chaco",
            segmento=segmento,
            fecha_inicio=AHORA.date(),
            fecha_fin=AHORA.date() + timedelta(days=30),
        )
        relevamiento = Relevamiento.objects.create(
            convocatoria=convocatoria, territorial=f.operador, fecha_asignada=AHORA, zona="Resistencia"
        )
        Formulario.objects.create(relevamiento=relevamiento, ciudadano=f.persona)
        edificio = Edificio.objects.create(
            codigo="ED-1", nombre="Predio central", latitud="-27.451120", longitud="-58.986340"
        )
        edificio.dispositivos.add(f.cis)
        InspeccionEdificio.objects.create(
            edificio=edificio,
            asignado_a=f.operador,
            creado_por=f.operador,
            fecha_vencimiento=AHORA.date() - timedelta(days=1),
        )
        Turno.objects.create(dispositivo=f.cis, nombre="Guardia", hora_desde=time(0), hora_hasta=time(0))
        self.motor = sync_playwright().start()
        self.addCleanup(self.motor.stop)
        self.navegador = self.motor.chromium.launch()
        self.addCleanup(self.navegador.close)
        self.pagina = self.navegador.new_page()
        self.pagina.context.add_cookies(
            [{"name": "sessionid", "value": self.client.cookies["sessionid"].value, "url": self.live_server_url}]
        )

    def test_p4_todas_las_solapas_y_listados_con_nombres_largos_sin_scroll_de_pagina(self):
        f = self.terreno
        urls = [
            (f"P4-{tab}", f"{f.url}?tab={tab}")
            for tab in ("datos", "sectores", "estadias", "infraestructura", "historial")
        ]
        urls += [
            ("P5", reverse("dispositivos:sectores", args=[f.cis.pk])),
            ("P7", reverse("dispositivos:estadia_detalle", args=[f.cis.pk, self.estadia.pk])),
            ("P10", reverse("dispositivos:bitacora", args=[f.cis.pk])),
            ("P21", reverse("dispositivos:relevamientos")),
            ("P2", reverse("dispositivos:lista")),
            ("Tipos", reverse("dispositivos:tipos")),
            ("Becas-revision", reverse("becas:revision")),
            ("Ciudadanos", reverse("legajos:ciudadanos")),
        ]
        urls += [
            (f"Configuracion-{nombre}", reverse(f"configuracion:{nombre}"))
            for nombre in ("provincias", "municipios", "localidades", "secretarias", "subsecretarias", "programas")
        ]
        for ancho in (390, 1440):
            self.pagina.set_viewport_size({"width": ancho, "height": 1000})
            for pantalla, url in urls:
                with self.subTest(pantalla=pantalla, ancho=ancho):
                    respuesta = self.pagina.goto(self.live_server_url + url)
                    self.assertEqual(respuesta.status, 200)
                    self.pagina.wait_for_function("window.Alpine !== undefined")
                    self.pagina.evaluate("document.fonts.ready")
                    if pantalla.startswith("P4-"):
                        self.pagina.locator("#panel-" + pantalla[3:]).wait_for(state="visible")
                        self.assertTrue(self.pagina.locator('[aria-label="Alertas del dispositivo"]').is_visible())
                    if pantalla == "P4-datos":
                        email = self.pagina.locator("#panel-datos dd").filter(has_text=f.cis.contacto_email)
                        self.assertTrue(
                            email.evaluate(
                                """e => {
                                    const rango = document.createRange();
                                    rango.selectNodeContents(e);
                                    const caja = e.getBoundingClientRect();
                                    return [...rango.getClientRects()].every(r => r.right <= caja.right + 1);
                                }"""
                            ),
                            "El email largo debe poder leerse completo dentro de Datos, sin recortarlo.",
                        )
                    self.assertEqual(self.pagina.evaluate("document.documentElement.scrollWidth"), ancho, pantalla)
                    if ancho == 1440:
                        self.pagina.add_style_tag(
                            content="*, *::before, *::after { animation: none !important; transition: none !important; }"
                        )
                        antes = self.pagina.screenshot(animations="disabled")
                        regla_anterior = self.pagina.add_style_tag(content=".overflow-x-auto { position: static; }")
                        diferencia = ImageChops.difference(
                            Image.open(BytesIO(antes)).convert("RGB"),
                            Image.open(BytesIO(self.pagina.screenshot(animations="disabled"))).convert("RGB"),
                        )
                        # Posicionar el wrapper puede cambiar el antialias del borde
                        # redondeado en hasta dos niveles RGB, sin modificar contenido ni geometría.
                        self.assertLessEqual(
                            max(maximo for _, maximo in diferencia.getextrema()),
                            2,
                            f"{pantalla}: la tabla conserva su aspecto a 1440px",
                        )
                        regla_anterior.evaluate("e => e.remove()")
                    for tabla in self.pagina.locator("table:visible").all():
                        if tabla.evaluate("e => e.scrollWidth > e.parentElement.clientWidth"):
                            self.assertTrue(
                                tabla.evaluate("e => e.closest('.overflow-x-auto') !== null"),
                                f"{pantalla} a {ancho}px: toda tabla ancha necesita su wrapper de scroll.",
                            )
                    for wrapper in self.pagina.locator(".overflow-x-auto:visible").all():
                        if wrapper.evaluate("e => e.scrollWidth > e.clientWidth"):
                            wrapper.evaluate("e => e.scrollLeft = e.scrollWidth")
                            self.assertGreater(wrapper.evaluate("e => e.scrollLeft"), 0)
                            self.assertEqual(self.pagina.evaluate("document.documentElement.scrollWidth"), ancho)

    def test_p3_aviso_de_duplicados_actualiza_la_alerta_dentro_del_flujo(self):
        self.pagina.goto(self.live_server_url + reverse("dispositivos:crear"))
        aviso = self.pagina.locator("#duplicate-search")
        self.assertFalse(aviso.is_visible())
        self.pagina.locator("#id_codigo").fill(self.terreno.cis.codigo)
        self.pagina.locator("#id_nombre").focus()
        aviso.wait_for(state="visible")
        self.assertEqual(aviso.locator('[role="alert"]').count(), 1)
        self.assertEqual(aviso.locator(".bg-warning-soft.border-warning-subtle").count(), 1)
        self.assertIn("El código ya está en uso", aviso.locator("strong").inner_text())
        self.assertIn(self.terreno.cis.nombre, aviso.locator("li").inner_text())
        self.pagina.locator("#id_codigo").fill("FF-SIN-COINCIDENCIAS")
        self.pagina.locator("#id_nombre").focus()
        aviso.wait_for(state="hidden")
