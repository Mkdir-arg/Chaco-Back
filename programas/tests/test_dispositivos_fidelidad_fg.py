"""Desglose de P5 y contrato del contenido dinámico de la alerta de P3."""

import json
import re
from datetime import timedelta
from html.parser import HTMLParser
from unittest.mock import patch

from django.conf import settings
from django.db import connection
from django.test import tag
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from programas.models import Plaza, ReservaPlaza, Sector
from programas.services.ocupacion import Conteo, ocupacion_de_plazas
from programas.tests.test_dispositivos_detalle import BaseDetalle
from programas.tests.test_dispositivos_fidelidad_fd import AHORA


class _ContenidoAlerta(HTMLParser):
    """Lee el HTML crudo: un navegador corregiría un ul dentro de p y ocultaría el defecto."""

    def __init__(self, selector):
        super().__init__()
        self.selector = selector
        self.pila = []
        self.destinos = []

    def handle_starttag(self, tag, attrs):
        self.pila.append(tag)
        if self.selector in dict(attrs):
            self.destinos.append(tuple(self.pila))

    def handle_endtag(self, tag):
        if tag in self.pila:
            self.pila = self.pila[: len(self.pila) - 1 - self.pila[::-1].index(tag)]


class FidelidadFGTests(BaseDetalle):
    def setUp(self):
        reloj = patch("django.utils.timezone.now", return_value=AHORA)
        reloj.start()
        self.addCleanup(reloj.stop)
        super().setUp()
        self.operador.is_superuser = True
        self.operador.save()
        self.client.force_login(self.operador)

    def test_p5_separa_y_pluraliza_uno_y_dos_de_cada_tipo(self):
        for reservas, prestamos in ((1, 1), (2, 2), (0, 1), (1, 0), (0, 0)):
            with self.subTest(reservas=reservas, prestamos=prestamos):
                ReservaPlaza.objects.all().delete()
                for tipo, cantidad in ((ReservaPlaza.Tipo.RESERVA, reservas), (ReservaPlaza.Tipo.PRESTAMO, prestamos)):
                    for indice in range(cantidad):
                        plaza, _ = Plaza.objects.get_or_create(sector=self.sector, codigo=f"{tipo}-{indice}")
                        ReservaPlaza.objects.create(
                            plaza=plaza,
                            ciudadano=self.persona,
                            tipo=tipo,
                            desde=AHORA - timedelta(hours=1),
                            hasta=AHORA + timedelta(hours=1),
                        )
                respuesta = self.client.get(reverse("dispositivos:sectores", args=[self.cis.pk]))
                texto = (
                    f"{reservas} reservada{'s' if reservas != 1 else ''} · "
                    f"{prestamos} prestada{'s' if prestamos != 1 else ''}"
                )
                self.assertContains(respuesta, texto + " · ", count=2)
                self.assertNotContains(respuesta, "reservadas o prestadas")
                # P4 conserva la métrica agregada y la disponibilidad descuenta ambos.
                conteo = ocupacion_de_plazas(self.cis, momento=AHORA).de(self.cis).conteo
                self.assertEqual(conteo.reservadas, reservas + prestamos)
                self.assertEqual(conteo.disponibles, conteo.operativas - reservas - prestamos)

    @tag("performance")
    def test_desglose_se_suma_por_sector_dispositivo_y_red(self):
        for dispositivo, cantidad in ((self.cis, 1), (self.parador, 2)):
            sector = Sector.objects.create(dispositivo=dispositivo, nombre="Préstamos")
            for indice in range(cantidad):
                plaza = Plaza.objects.create(sector=sector, codigo=f"PRE-{indice}")
                ReservaPlaza.objects.create(
                    plaza=plaza,
                    ciudadano=self.persona,
                    tipo=ReservaPlaza.Tipo.PRESTAMO,
                    desde=AHORA,
                    hasta=AHORA + timedelta(hours=1),
                )
        with CaptureQueriesContext(connection) as consultas:
            censo = ocupacion_de_plazas([self.cis, self.parador], momento=AHORA)
        presupuestos = json.loads((settings.BASE_DIR / "scripts/perf_budgets.json").read_text(encoding="utf-8"))
        self.assertLessEqual(
            len(consultas), presupuestos["servicios"]["dispositivos_ocupacion_de_plazas"]["consultas_fijas"]
        )
        self.assertEqual(censo.total.prestadas, 3)
        self.assertEqual(censo.total.reservadas_sin_prestamo, 0)
        for dispositivo, cantidad in ((self.cis, 1), (self.parador, 2)):
            ocupacion = censo.de(dispositivo)
            self.assertEqual(ocupacion.conteo.prestadas, cantidad)
            self.assertEqual(sum(s.conteo.prestadas for s in ocupacion.sectores), cantidad)

    def test_desglose_desconocido_no_inventa_ceros(self):
        for conteo in (Conteo(reservadas=2), Conteo(prestadas=1), Conteo()):
            with self.subTest(conteo=conteo):
                self.assertIsNone(conteo.reservadas_sin_prestamo)
        conocido = Conteo(reservadas=3, prestadas=1)
        self.assertEqual(conocido.reservadas_sin_prestamo, 2)
        self.assertIsNone((conocido + Conteo(reservadas=1)).prestadas)
        self.assertEqual(ocupacion_de_plazas([], momento=AHORA).total.prestadas, 0)

    def test_lista_de_duplicados_se_inserta_fuera_de_un_parrafo(self):
        html = self.client.get(reverse("dispositivos:crear")).content.decode()
        selector = re.search(r"aviso.querySelector\('\[([^\]]+)\]'\).replaceChildren\(lista\)", html)
        self.assertIsNotNone(selector, "La inserción debe usar el selector propio del contenido")
        parser = _ContenidoAlerta(selector.group(1))
        parser.feed(html)
        self.assertEqual(len(parser.destinos), 1)
        self.assertNotIn("p", parser.destinos[0], "El ul dinámico no puede tener un párrafo como ancestro")
        self.assertEqual(parser.destinos[0][-1], "div")
        self.assertNotIn("querySelector('strong')", html)
        self.assertNotIn("querySelector('p')", html)
        self.assertIn("querySelector('[data-duplicados-mensaje]')", html)

    def test_ambos_fallos_de_busqueda_se_registran_en_consola(self):
        html = self.client.get(reverse("dispositivos:crear")).content.decode()
        capturas = re.findall(r"\.catch\(function \(error\) \{(.*?)\}\);", html, re.S)
        self.assertEqual(len(capturas), 2)
        for captura in capturas:
            self.assertIn("console.error('No se pudo verificar duplicados.', error);", captura)
