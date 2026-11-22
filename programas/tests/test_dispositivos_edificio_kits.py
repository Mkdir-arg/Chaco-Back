"""Solapa Kits de la página operativa del edificio: tabla de entregas y detalle con recepción (Cambio 568, PR 3).

1. Alcance: solo las entregas de **este** edificio y de **esta** institución. La de otro edificio, la de otra
   institución del mismo predio y la sin edificio no aparecen, y su detalle da 404.
2. Capacidad: sin ``emergencia.recibir_kit`` no hay solapa ni detalle.
3. La tabla: orden, botón de cada fila, diferencias.
4. El detalle: recepción con ``next`` que vuelve a la solapa; la ya recibida, sin formulario.
5. El costo de la solapa no crece con las entregas.
"""

import json
from datetime import timedelta

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import tag
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from programas.models import Dispositivo, EntregaKit, LineaEntrega, TipoKit
from programas.tests.test_dispositivos_edificio_operativo import BaseOperativo
from programas.tests.test_equipo_alcance_edificio import Alcance

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 64
Estado = EntregaKit.Estado


class BaseKitsEdificio(BaseOperativo):
    def setUp(self):
        super().setUp()
        self.colchon = TipoKit.objects.create(nombre="Colchón", unidad="unidad", orden=1)
        self.agua = TipoKit.objects.create(nombre="Agua 6 l", unidad="bidón", orden=2)
        capacidades = ("dispositivo.ver", "emergencia.recibir_kit")
        self.recibe_a = self._con("Recibe A", *capacidades, alcance=Alcance.EDIFICIOS, edificios=[self.edif_a])
        self.recibe_inst = self._con("Recibe inst", *capacidades)

    def _entrega(self, numero, edificio, dispositivo=None, estado=Estado.EN_CAMINO, **extra):
        entrega = EntregaKit.objects.create(
            numero=numero,
            dispositivo=dispositivo or self.cis,
            edificio=edificio,
            estado=estado,
            armada_por=self.operador,
            despachada_en=timezone.now(),
            **extra,
        )
        LineaEntrega.objects.create(entrega=entrega, item=self.colchon, unidad="unidad", cantidad_enviada=10)
        LineaEntrega.objects.create(entrega=entrega, item=self.agua, unidad="bidón", cantidad_enviada=12)
        return entrega

    def _detalle(self, usuario, entrega, edificio=None):
        return self._get(usuario, edificio or self.edif_a, tab="kits", entrega=entrega.pk)

    def _otra_institucion(self):
        otra = Dispositivo.objects.create(
            tipo=self.tipo, codigo="GER-9", nombre="Otra institución", estado=Dispositivo.Estado.ACTIVO
        )
        self.edif_a.dispositivos.add(otra)
        return otra


class AlcanceDeLasEntregasTests(BaseKitsEdificio):
    def setUp(self):
        super().setUp()
        self.propia = self._entrega("2026-K-000101", self.edif_a)
        self.de_b = self._entrega("2026-K-000102", self.edif_b)
        self.sin_edificio = self._entrega("2026-K-000103", None)
        self.otra_inst = self._entrega("2026-K-000104", self.edif_a, dispositivo=self._otra_institucion())

    def test_la_tabla_trae_solo_las_de_este_edificio_y_esta_institucion(self):
        for usuario in (self.recibe_a, self.recibe_inst):
            respuesta = self._get(usuario, self.edif_a, tab="kits")

            self.assertEqual([f["entrega"].numero for f in respuesta.context["kits"]["filas"]], ["2026-K-000101"])
            for ajena in (self.de_b, self.sin_edificio, self.otra_inst):
                self.assertNotContains(respuesta, ajena.numero)

    def test_el_detalle_de_una_ajena_da_404(self):
        for usuario in (self.recibe_a, self.recibe_inst):
            for ajena in (self.de_b, self.sin_edificio, self.otra_inst):
                self.assertEqual(self._detalle(usuario, ajena).status_code, 404, ajena.numero)

    def test_el_detalle_de_la_propia_abre(self):
        respuesta = self._detalle(self.recibe_a, self.propia)

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context["tab"], "kits")
        self.assertContains(respuesta, "Volver a las entregas")

    def test_un_id_que_no_es_numero_da_404(self):
        self.client.force_login(self.recibe_inst)
        for pedida in ("abc", "²", "-1", ""):
            with self.subTest(pedida=pedida):
                respuesta = self.client.get(self._url(self.edif_a), {"tab": "kits", "entrega": pedida})

                # Un vacío no pide ninguna entrega: abre la tabla.
                self.assertEqual(respuesta.status_code, 200 if pedida == "" else 404)

    def test_la_sin_edificio_sigue_visible_en_emergencia_kits_con_alcance_institucion(self):
        self.client.force_login(self.recibe_inst)

        respuesta = self.client.get(reverse("emergencia:dispositivo_kits", args=[self.cis.pk]))

        self.assertContains(respuesta, self.sin_edificio.numero)


class CapacidadTests(BaseKitsEdificio):
    def test_sin_recibir_kit_no_hay_solapa_ni_detalle(self):
        sin = self._con("Sin kits", "dispositivo.ver")
        propia = self._entrega("2026-K-000201", self.edif_a)

        lista = self._get(sin, self.edif_a, tab="kits")
        detalle = self._detalle(sin, propia)

        for respuesta in (lista, detalle):
            self.assertEqual(respuesta.status_code, 200)
            self.assertNotIn("kits", respuesta.context)
            self.assertNotContains(respuesta, 'id="panel-kits"')
            self.assertNotContains(respuesta, propia.numero)
        self.assertEqual(detalle.context["tab"], "sectores")

    def test_alcance_a_otro_edificio_no_ve_este(self):
        propia = self._entrega("2026-K-000202", self.edif_b)
        respuesta = self._detalle(self.recibe_a, propia, edificio=self.edif_b)

        self.assertEqual(respuesta.status_code, 404)


class TablaTests(BaseKitsEdificio):
    def test_de_la_mas_nueva_a_la_mas_vieja_con_su_boton(self):
        vieja = self._entrega("2026-K-000301", self.edif_a, estado=Estado.RECIBIDA, recibida_en=timezone.now())
        nueva = self._entrega("2026-K-000302", self.edif_a)

        respuesta = self._get(self.recibe_inst, self.edif_a, tab="kits")

        filas = respuesta.context["kits"]["filas"]
        self.assertEqual([f["entrega"].pk for f in filas], [nueva.pk, vieja.pk])
        self.assertEqual([f["recibe"] for f in filas], [True, False])
        self.assertContains(respuesta, "Entregas a este edificio")
        self.assertContains(respuesta, f'aria-label="Recibir {nueva.numero}"')
        self.assertContains(respuesta, f'aria-label="Ver detalle {vieja.numero}"')
        self.assertContains(respuesta, "2 entregas · 1 en camino")

    def test_la_diferencia_dice_cuanto_y_de_que_item(self):
        entrega = self._entrega("2026-K-000303", self.edif_a, estado=Estado.RECIBIDA_CON_DIFERENCIAS)
        LineaEntrega.objects.filter(entrega=entrega, item=self.agua).update(cantidad_recibida=10)
        LineaEntrega.objects.filter(entrega=entrega, item=self.colchon).update(cantidad_recibida=11)

        respuesta = self._get(self.recibe_inst, self.edif_a, tab="kits")

        self.assertContains(respuesta, "−2 · faltan (Agua 6 l)")
        self.assertContains(respuesta, "+1 · de más (Colchón)")

    def test_en_camino_no_cuenta_las_preparadas_y_el_badge_si(self):
        self._entrega("2026-K-000304", self.edif_a)
        self._entrega("2026-K-000305", self.edif_a, estado=Estado.PREPARADA)

        respuesta = self._get(self.recibe_inst, self.edif_a, tab="kits")

        self.assertContains(respuesta, "2 entregas · 1 en camino")
        self.assertEqual(respuesta.context["contadores"]["kits"], 2)

    def test_las_fechas_van_en_dias_desde_un_dia(self):
        entrega = self._entrega("2026-K-000306", self.edif_a)
        for atras, esperado in (
            (timedelta(hours=3), "hace 3 horas"),
            (timedelta(days=1, hours=2), "hace 1 día"),
            (timedelta(days=7), "hace 7 días"),
            (timedelta(days=28), "hace 28 días"),
        ):
            EntregaKit.objects.filter(pk=entrega.pk).update(despachada_en=timezone.now() - atras)

            respuesta = self._get(self.recibe_inst, self.edif_a, tab="kits")

            self.assertEqual(respuesta.context["kits"]["filas"][0]["enviada"], esperado)

    def test_la_paginacion_usa_su_propio_parametro(self):
        for numero in range(26):
            self._entrega(f"2026-K-0007{numero:02d}", self.edif_a)

        respuesta = self._get(self.recibe_inst, self.edif_a, tab="kits", kits_page=2)

        self.assertEqual(len(respuesta.context["kits"]["filas"]), 1)
        self.assertContains(respuesta, "kits_page=1")

    def test_la_cancelada_no_dice_recibida_ni_tiene_remito(self):
        cancelada = self._entrega("2026-K-000307", self.edif_a, estado=Estado.CANCELADA)

        respuesta = self._detalle(self.recibe_inst, cancelada)

        self.assertContains(respuesta, "Cancelada")
        self.assertNotContains(respuesta, "Recibida hace")
        self.assertNotContains(respuesta, "Lo recibido")
        self.assertNotContains(respuesta, 'id="form-recibir-entrega"')
        self.assertNotContains(respuesta, "Sin remito")

    def test_sin_entregas_dice_que_no_hay(self):
        respuesta = self._get(self.recibe_inst, self.edif_a, tab="kits")

        self.assertContains(respuesta, "Todavía no hay entregas a este edificio")


class RecepcionDesdeLaSolapaTests(BaseKitsEdificio):
    def setUp(self):
        super().setUp()
        self.entrega = self._entrega("2026-K-000401", self.edif_a, observacion_mesa="Los colchones vienen con funda.")
        self.url_pagina = self._url(self.edif_a)
        self.url_recibir = reverse("emergencia:dispositivo_kit_recibir", args=[self.cis.pk, self.entrega.pk])

    def _cuerpo(self, **extra):
        return {
            f"cantidad_{self.colchon.pk}": 10,
            f"cantidad_{self.agua.pk}": 12,
            "remito": SimpleUploadedFile("remito.jpg", JPEG, content_type="image/jpeg"),
            **extra,
        }

    def test_el_detalle_en_camino_trae_el_formulario_y_la_nota_de_la_mesa(self):
        respuesta = self._detalle(self.recibe_a, self.entrega)

        self.assertContains(respuesta, 'id="form-recibir-entrega"')
        self.assertContains(respuesta, f'action="{self.url_recibir}"')
        self.assertContains(respuesta, f'name="next" value="{self.url_pagina}?tab=kits"')
        self.assertContains(respuesta, "Confirmar recepción")
        self.assertContains(respuesta, "reportValidity")
        self.assertContains(respuesta, "La recepción no se corrige")
        self.assertContains(respuesta, 'form="form-recibir-entrega"')
        self.assertContains(respuesta, "Los colchones vienen con funda.")
        self.assertContains(respuesta, "Entrega 1 de 1 de este edificio")

    def test_recibir_vuelve_a_la_solapa(self):
        self.client.force_login(self.recibe_a)

        respuesta = self.client.post(self.url_recibir, self._cuerpo(next=f"{self.url_pagina}?tab=kits"))

        self.assertRedirects(respuesta, f"{self.url_pagina}?tab=kits", fetch_redirect_response=False)
        self.assertEqual(EntregaKit.objects.get(pk=self.entrega.pk).estado, Estado.RECIBIDA)

    def test_un_error_de_recepcion_conserva_el_regreso_a_la_solapa(self):
        self.client.force_login(self.recibe_a)
        cuerpo = self._cuerpo(next=f"{self.url_pagina}?tab=kits")
        del cuerpo["remito"]

        respuesta = self.client.post(self.url_recibir, cuerpo)

        self.assertEqual(respuesta.status_code, 400)
        self.assertContains(respuesta, f'name="next" value="{self.url_pagina}?tab=kits"', status_code=400)
        self.assertContains(
            respuesta,
            f'href="{self.url_pagina}?tab=kits" class="btn-nodo btn-tertiary btn-base">Cancelar',
            status_code=400,
        )

    def test_un_error_con_next_ajeno_no_lo_devuelve_al_formulario(self):
        self.client.force_login(self.recibe_a)
        cuerpo = self._cuerpo(next="https://ejemplo.com/robo")
        del cuerpo["remito"]

        respuesta = self.client.post(self.url_recibir, cuerpo)

        self.assertEqual(respuesta.status_code, 400)
        self.assertNotContains(respuesta, "ejemplo.com", status_code=400)

    def test_un_next_de_otro_sitio_se_ignora(self):
        self.client.force_login(self.recibe_a)

        respuesta = self.client.post(self.url_recibir, self._cuerpo(next="https://ejemplo.com/robo"))

        self.assertRedirects(
            respuesta,
            reverse("emergencia:dispositivo_kits", args=[self.cis.pk]),
            fetch_redirect_response=False,
        )

    def test_sin_next_la_recepcion_sigue_volviendo_a_las_pendientes(self):
        self.client.force_login(self.recibe_a)

        respuesta = self.client.post(self.url_recibir, self._cuerpo())

        self.assertRedirects(
            respuesta,
            reverse("emergencia:dispositivo_kits", args=[self.cis.pk]),
            fetch_redirect_response=False,
        )

    def test_la_ya_recibida_muestra_lo_recibido_y_el_remito_sin_formulario(self):
        self.client.force_login(self.recibe_a)
        self.client.post(self.url_recibir, self._cuerpo(next=f"{self.url_pagina}?tab=kits", observacion="Todo bien."))

        respuesta = self._detalle(self.recibe_a, self.entrega)

        self.assertNotContains(respuesta, 'id="form-recibir-entrega"')
        self.assertContains(respuesta, "Lo recibido")
        self.assertContains(respuesta, "Todo bien.")
        self.assertContains(respuesta, "sin diferencia")
        self.assertContains(respuesta, "Remito")
        self.assertContains(respuesta, f"Remito de la entrega {self.entrega.numero}")

    def test_recibir_una_entrega_de_otro_edificio_sigue_dando_404(self):
        # La regla no cambió: el alcance por edificio lo decide RecibirKitView, no esta solapa.
        ajena = self._entrega("2026-K-000402", self.edif_b)
        self.client.force_login(self.recibe_a)

        respuesta = self.client.post(
            reverse("emergencia:dispositivo_kit_recibir", args=[self.cis.pk, ajena.pk]), self._cuerpo()
        )

        self.assertEqual(respuesta.status_code, 404)


PRESUPUESTOS = settings.BASE_DIR / "scripts" / "perf_budgets.json"
CLAVE_PRESUPUESTO = "dispositivos_edificio_operativo_kits"


@tag("performance")
class PresupuestoDeKitsTests(BaseKitsEdificio):
    def _medir(self, **params):
        self.client.force_login(self.recibe_inst)
        url = self._url(self.edif_a)
        self.client.get(url, params)
        with CaptureQueriesContext(connection) as consultas:
            respuesta = self.client.get(url, params)
        self.assertEqual(respuesta.status_code, 200)
        return len(consultas)

    def test_la_lista_y_el_detalle_cuestan_lo_mismo_con_una_que_con_muchas(self):
        primera = self._entrega("2026-K-000501", self.edif_a)
        lista_antes = self._medir(tab="kits")
        detalle_antes = self._medir(tab="kits", entrega=primera.pk)
        for numero in range(8):
            self._entrega(f"2026-K-0006{numero:02d}", self.edif_a, estado=Estado.RECIBIDA, recibida_en=timezone.now())

        self.assertEqual(self._medir(tab="kits"), lista_antes)
        self.assertEqual(self._medir(tab="kits", entrega=primera.pk), detalle_antes)
        techo = json.loads(PRESUPUESTOS.read_text(encoding="utf-8"))["servicios"][CLAVE_PRESUPUESTO]
        self.assertLessEqual(max(lista_antes, detalle_antes), techo["consultas_fijas"])

    def test_con_otra_solapa_los_kits_no_se_arman_y_el_boton_navega(self):
        self._entrega("2026-K-000502", self.edif_a)
        self.client.force_login(self.recibe_inst)

        respuesta = self.client.get(self._url(self.edif_a), {"tab": "estadias"})

        self.assertNotIn("kits", respuesta.context)
        self.assertContains(respuesta, 'id="tab-kits" aria-controls="panel-kits" data-solapa-navega')
        self.assertContains(respuesta, f"{self._url(self.edif_a)}?tab=kits")
        self.assertNotContains(respuesta, "2026-K-000502")
