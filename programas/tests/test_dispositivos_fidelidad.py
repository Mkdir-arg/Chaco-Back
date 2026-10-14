"""Fidelidad P5/P6: identidad autorizada, vencimientos y consultas constantes."""

import json
import re
from datetime import datetime, timedelta
from datetime import timezone as tz
from pathlib import Path
from unittest.mock import patch

from django.db import connection
from django.test import tag
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from legajos.models import Ciudadano
from programas.models import Estadia, Plaza, ReservaPlaza, Sector
from programas.services.ingreso import plazas_para_ingresar
from programas.services.ocupacion import estado_de_plazas
from programas.services.sectores_plazas import sectores_con_plazas
from programas.tests.test_dispositivos_estadias import CAPACIDADES_OPERATIVAS, BaseEstadias
from programas.tests.test_dispositivos_ingreso import BaseIngreso

AHORA = datetime(2026, 10, 14, 12, tzinfo=tz.utc)
PRESUPUESTOS = Path(__file__).resolve().parents[2] / "scripts" / "perf_budgets.json"


class BaseMapaFidelidad(BaseEstadias):
    def setUp(self):
        super().setUp()
        self.addCleanup(patch.stopall)
        patch("django.utils.timezone.now", return_value=AHORA).start()
        self.autorizado = self._operador("Ve personas", self.cis, (*CAPACIDADES_OPERATIVAS, "ciudadano.ver"))
        self.ocupacion = Estadia.objects.create(
            ciudadano=self.persona,
            dispositivo=self.cis,
            plaza=self.plaza,
            fecha_ingreso=AHORA - timedelta(days=1),
            clave_alojamiento=Estadia.clave_para(self.persona),
        )
        self.reserva = ReservaPlaza.objects.create(
            plaza=self.otra_plaza,
            ciudadano=self.otra_persona,
            desde=AHORA - timedelta(hours=1),
            hasta=AHORA + timedelta(hours=6),
        )
        self.prestada = Plaza.objects.create(sector=self.sector, codigo="P3")
        ReservaPlaza.objects.create(
            plaza=self.prestada,
            ciudadano=self.otra_persona,
            tipo=ReservaPlaza.Tipo.PRESTAMO,
            desde=AHORA - timedelta(hours=1),
            hasta=AHORA + timedelta(hours=3),
        )
        self.fuera = Plaza.objects.create(
            sector=self.sector, codigo="P4", estado=Plaza.Estado.FUERA_SERVICIO, motivo_fuera_servicio="colchón"
        )
        self.libre = Plaza.objects.create(sector=self.sector, codigo="P5")

    def _estados(self, **kwargs):
        return estado_de_plazas(Plaza.objects.filter(sector=self.sector), AHORA, **kwargs)


class DetalleDePlazaTests(BaseMapaFidelidad):
    def test_vencimiento_de_otro_ano_conserva_detalle_corto_y_title_completo_sin_identidad(self):
        self.reserva.hasta = datetime(2027, 11, 18, 11, 46, tzinfo=tz.utc)
        self.reserva.save()
        for autorizado in (False, True):
            with self.subTest(autorizado=autorizado):
                estado = self._estados(puede_ver_personas=autorizado)[self.otra_plaza.pk]
                prefijo = "Pérez, J. · " if autorizado else ""
                local = timezone.localtime(self.reserva.hasta)
                self.assertEqual(estado.detalle, prefijo + f"hasta {local:%d/%m %H:%M}")
                self.assertEqual(estado.detalle_completo, prefijo + f"hasta {local:%d/%m/%Y %H:%M}")
                if not autorizado:
                    for privado in ("Pérez", "Juan", self.otra_persona.dni):
                        self.assertNotIn(privado, estado.detalle_completo)

    def test_detalle_de_los_cinco_estados_con_identidad_autorizada(self):
        estados = self._estados(puede_ver_personas=True)
        self.assertEqual(estados[self.plaza.pk].detalle, "Gómez, A.")
        self.assertEqual(
            estados[self.otra_plaza.pk].detalle,
            f"Pérez, J. · hasta {timezone.localtime(self.reserva.hasta):%d/%m %H:%M}",
        )
        self.assertEqual(
            estados[self.prestada.pk].detalle,
            f"Pérez, J. · hasta {timezone.localtime(AHORA + timedelta(hours=3)):%d/%m %H:%M}",
        )
        self.assertEqual(estados[self.fuera.pk].detalle, "colchón")
        self.assertEqual(estados[self.libre.pk].detalle, "")

    def test_por_defecto_no_expone_personas_y_conserva_vencimientos_y_motivo(self):
        estados = self._estados()
        self.assertEqual(estados[self.plaza.pk].detalle, "")
        self.assertEqual(
            estados[self.otra_plaza.pk].detalle, f"hasta {timezone.localtime(self.reserva.hasta):%d/%m %H:%M}"
        )
        self.assertEqual(
            estados[self.prestada.pk].detalle,
            f"hasta {timezone.localtime(AHORA + timedelta(hours=3)):%d/%m %H:%M}",
        )
        for estado in estados.values():
            for privado in ("Gómez", "Pérez", self.persona.dni, self.otra_persona.dni):
                self.assertNotIn(privado, estado.detalle)
        self.assertEqual(estados[self.fuera.pk].detalle, "colchón")

    def test_reserva_sin_vencimiento_no_inventa_fecha(self):
        self.reserva.hasta = None
        self.reserva.save()
        self.assertEqual(
            self._estados(puede_ver_personas=True)[self.otra_plaza.pk].detalle, "Pérez, J. · sin vencimiento"
        )
        self.assertEqual(self._estados()[self.otra_plaza.pk].detalle, "sin vencimiento")

    def test_vencida_no_muestra_persona_y_la_estadia_gana_a_la_reserva(self):
        ReservaPlaza.objects.filter(pk=self.reserva.pk).update(hasta=AHORA - timedelta(seconds=1))
        ReservaPlaza.objects.create(
            plaza=self.plaza,
            ciudadano=self.otra_persona,
            desde=AHORA - timedelta(hours=1),
            hasta=AHORA + timedelta(hours=1),
        )
        estados = self._estados(puede_ver_personas=True)
        self.assertTrue(estados[self.otra_plaza.pk].disponible)
        self.assertEqual(estados[self.otra_plaza.pk].detalle, "")
        self.assertEqual(estados[self.plaza.pk].detalle, "Gómez, A.")
        Plaza.objects.filter(pk=self.plaza.pk).update(
            estado=Plaza.Estado.FUERA_SERVICIO, motivo_fuera_servicio="arreglo"
        )
        self.assertEqual(self._estados(puede_ver_personas=True)[self.plaza.pk].detalle, "arreglo")


class MapaP5FidelidadTests(BaseMapaFidelidad):
    def _pagina(self, usuario):
        self.client.force_login(usuario)
        return self.client.get(reverse("dispositivos:sectores", args=[self.cis.pk]))

    def test_celdas_sin_capacidad_no_repiten_estado_y_solo_detallan_vencimiento(self):
        respuesta = self._pagina(self.operador_cis)
        self.assertEqual(respuesta.status_code, 200)
        celdas = re.findall(r"<li\b[^>]*>(.*?)</li>", respuesta.content.decode(), re.DOTALL)
        for plaza, estado, detalle in (
            (self.plaza, "Ocupada", ""),
            (self.otra_plaza, "Reservada", f"hasta {timezone.localtime(self.reserva.hasta):%d/%m %H:%M}"),
            (self.prestada, "Prestada", f"hasta {timezone.localtime(AHORA + timedelta(hours=3)):%d/%m %H:%M}"),
        ):
            with self.subTest(estado=estado):
                celda = next(celda for celda in celdas if f"</span>{plaza.codigo}</b>" in celda)
                self.assertEqual(celda.count(estado), 1)
                if detalle:
                    completo = self._estados()[plaza.pk].detalle_completo
                    self.assertIn(f'title="{completo}">{detalle}</span>', celda)
                else:
                    self.assertNotIn("truncate", celda)

    def test_capacidad_ciudadano_ver_decide_identidad_en_html_y_contexto(self):
        for usuario, permitido in ((self.operador_cis, False), (self.autorizado, True)):
            with self.subTest(permitido=permitido):
                respuesta = self._pagina(usuario)
                self.assertEqual(respuesta.status_code, 200)
                detalles = [plaza["detalle"] for sector in respuesta.context["sectores"] for plaza in sector["plazas"]]
                if permitido:
                    self.assertContains(respuesta, 'title="Gómez, A."')
                    self.assertContains(respuesta, "Pérez, J. · hasta")
                    self.assertIn("Gómez, A.", detalles)
                else:
                    for nombre in ("Gómez", "Pérez", "Ana", "Juan"):
                        self.assertNotContains(respuesta, nombre)
                        self.assertNotIn(nombre, " ".join(detalles))
                self.assertNotContains(respuesta, self.persona.dni)
                self.assertContains(respuesta, "colchón")

    def test_p5_y_p6_llevan_el_ano_al_title_y_mantienen_el_texto_corto(self):
        self.reserva.hasta = datetime(2027, 11, 18, 11, 46, tzinfo=tz.utc)
        self.reserva.save()
        for usuario, nombrar in ((self.operador_cis, False), (self.autorizado, True)):
            with self.subTest(nombrar=nombrar):
                estado = self._estados(puede_ver_personas=nombrar)[self.otra_plaza.pk]
                respuesta = self._pagina(usuario)
                self.assertContains(respuesta, f'title="{estado.detalle_completo}">{estado.detalle}</span>')
                sectores, _ = plazas_para_ingresar(self.cis, puede_ver_personas=nombrar)
                plaza = next(p for sector in sectores for p in sector["plazas"] if p["pk"] == self.otra_plaza.pk)
                self.assertEqual(plaza["detalle_completo"], estado.detalle_completo)

    def test_porcentaje_ocupadas_sobre_operativas_no_total_ni_reservadas(self):
        respuesta = self._pagina(self.autorizado)
        # Una ocupada / cuatro operativas (una fuera de servicio y dos reservadas).
        self.assertEqual(respuesta.context["sectores"][0]["resumen"]["porcentaje"], 25)
        self.assertContains(respuesta, "· 25 %")

    def test_cero_ocupadas_muestra_cero_y_sin_operativas_no_inventa_porcentaje(self):
        self.ocupacion.delete()
        respuesta = self._pagina(self.autorizado)
        self.assertContains(respuesta, "· 0 %")
        Plaza.objects.filter(sector=self.sector).update(
            estado=Plaza.Estado.FUERA_SERVICIO, motivo_fuera_servicio="arreglo"
        )
        respuesta = self._pagina(self.autorizado)
        self.assertIsNone(respuesta.context["sectores"][0]["resumen"]["porcentaje"])
        self.assertNotContains(respuesta, " %")


class MapaP6FidelidadTests(BaseIngreso):
    def setUp(self):
        super().setUp()
        reloj = patch("django.utils.timezone.now", return_value=AHORA)
        reloj.start()
        self.addCleanup(reloj.stop)

    def test_mapa_nombra_ocupante_y_solo_ofrece_libres_con_persona_al_costado(self):
        Estadia.objects.create(
            ciudadano=self.otra_persona,
            dispositivo=self.cis,
            plaza=self.plaza,
            fecha_ingreso=AHORA,
            clave_alojamiento=Estadia.clave_para(self.otra_persona),
        )
        self.client.post(self.url_persona, {"dni": self.persona.dni})
        respuesta = self.client.get(self.url_plaza)
        self.assertContains(respuesta, "Pérez, J.")
        self.assertNotContains(respuesta, f'?elegir={self.plaza.pk}"')
        self.assertContains(respuesta, f'?elegir={self.otra_plaza.pk}"')
        self.assertContains(respuesta, 'aria-disabled="true" class="cursor-not-allowed')
        self.assertContains(respuesta, 'class="cursor-pointer')
        self.assertContains(respuesta, "grid grid-cols-1 lg:grid-cols-3 gap-5")
        self.assertContains(respuesta, "lg:col-span-2 min-w-0")
        html = respuesta.content.decode()
        self.assertLess(html.index('aria-labelledby="sector-'), html.index(">Persona</h2>"))
        self.assertContains(respuesta, 'uppercase text-body-subtle">Nombre</dt>')
        self.assertNotContains(respuesta, "Nombre:</dt>")

    def test_resumen_final_usa_rotulos_de_p7(self):
        self._hasta_la_plaza(self.persona, self.plaza)
        respuesta = self.client.get(self.url_confirmar)
        self.assertContains(respuesta, 'uppercase text-body-subtle">Persona</dt>')
        self.assertNotContains(respuesta, "Persona:</dt>")


@tag("performance")
class MapaFidelidadPresupuestoTests(BaseMapaFidelidad):
    def _medir(self):
        # Los querysets se materializan fuera de estado_de_plazas: el presupuesto
        # protege sus dos consultas de movimientos, no la lectura de Plaza.
        plazas = list(Plaza.objects.filter(sector__dispositivo=self.cis))
        resultados = {}
        for clave, llamada in (
            ("dispositivos_estado_de_plazas", lambda: estado_de_plazas(plazas, AHORA, puede_ver_personas=True)),
            ("dispositivos_plazas_para_ingresar", lambda: plazas_para_ingresar(self.cis, puede_ver_personas=True)),
            ("dispositivos_sectores_con_plazas", lambda: sectores_con_plazas(self.cis, puede_ver_personas=True)),
        ):
            with CaptureQueriesContext(connection) as consultas:
                llamada()
            resultados[clave] = len(consultas)
        return resultados

    def test_detalles_no_crecen_con_personas_plazas_ni_sectores(self):
        presupuestos = json.loads(PRESUPUESTOS.read_text(encoding="utf-8"))["servicios"]
        pocas = self._medir()
        for n in range(12):
            sector = Sector.objects.create(dispositivo=self.cis, nombre=f"Sector {n}")
            persona = Ciudadano.objects.create(dni=str(40000000 + n), nombre="María", apellido=f"Apellido{n}")
            ocupada = Plaza.objects.create(sector=sector, codigo=f"S{n}-1")
            Estadia.objects.create(
                ciudadano=persona,
                dispositivo=self.cis,
                plaza=ocupada,
                fecha_ingreso=AHORA,
                clave_alojamiento=Estadia.clave_para(persona),
            )
            reservada = Plaza.objects.create(sector=sector, codigo=f"S{n}-2")
            ReservaPlaza.objects.create(
                plaza=reservada, ciudadano=persona, desde=AHORA, hasta=AHORA + timedelta(hours=1)
            )
        muchas = self._medir()
        self.assertEqual(muchas, pocas, "los detalles no deben introducir consultas por persona o plaza")
        for clave, cantidad in muchas.items():
            self.assertEqual(cantidad, presupuestos[clave]["consultas_fijas"], clave)
