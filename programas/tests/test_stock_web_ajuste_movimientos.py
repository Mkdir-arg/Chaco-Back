"""«Ajustar» (modal) y «Movimientos» (listado) en la web (análisis 010, PR 6b).

Ajuste: ``SaldoCambio`` se ve en el modal con el saldo de ahora, motivo obligatorio del catálogo, nada se mueve con
un rechazo, idempotencia, y las dos capas de autorización. Movimientos: filtros, paginación, la persona solo con
``ciudadano.ver``, otra institución sin nombre y presupuesto de consultas.

Mutaciones verificadas a mano (se rompe la regla, se mira el test rojo, se restaura):

* sacar el ``puede_ajustar`` de ``ajustar`` (servicio) pone rojo ``test_el_servicio_rechaza_aunque_la_vista_deje_pasar``;
* cambiar ``CAPACIDAD = CAP_STOCK_AJUSTAR`` de ``AjustarStockView`` por ``CAP_STOCK_INGRESAR`` pone rojo
  ``test_sin_stock_ajustar_en_ningun_lado_es_403``, y por ``CAP_STOCK_VER`` pone rojo
  ``test_la_vista_filtra_por_stock_ajustar_en_la_institucion_antes_que_el_servicio`` (el servicio solo daría 403);
* sacar el ``except SaldoCambio`` de ``AjustarStockView.post`` pone rojo ``test_un_saldo_que_cambio_reabre_el_modal_con_el_saldo_de_ahora``;
* sacar el ``con_persona`` / ``puede_ver_persona`` de ``MovimientosStockView.get`` pone rojo
  ``test_la_persona_de_una_entrega_solo_se_nombra_con_ciudadano_ver``;
* sacar el ``filter(tipo=…)`` de ``movimientos_de`` pone rojo ``test_filtra_por_tipo``;
* sacar el ``select_related`` de ``movimientos_de`` pone rojo ``test_el_listado_cuesta_lo_mismo_con_pocos_que_con_muchos_movimientos``;
* sacar el memo de ``puede_ver_stock`` pone rojo ``test_puede_ver_stock_se_lee_una_sola_vez_por_pagina``.
"""

import json
import uuid
from pathlib import Path

from django.db import connection
from django.test import tag
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from programas.models import MovimientoStock, OperacionStock, TipoKit
from programas.services import stock as servicio
from programas.services.edificio_stock import contexto_de_la_solapa
from programas.tests.test_stock_web_ingreso_traspaso import Alcance, BaseWeb

AJAX = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}
PRESUPUESTOS = Path(__file__).resolve().parents[2] / "scripts" / "perf_budgets.json"


class BaseAjuste(BaseWeb):
    RUTA = "dispositivos:stock_ajustar"

    def _datos(self, item=None, contada=7, visto=10, motivo="CONTEO_PERIODICO", **extra):
        datos = {
            "item": (item or self.colchon).pk,
            "saldo_visto": visto,
            "cantidad_contada": contada,
            "motivo": motivo,
            "detalle": "",
            "uuid_cliente": str(uuid.uuid4()),
        }
        datos.update(extra)
        return datos

    def _pagina(self, **parametros):
        return reverse("dispositivos:edificio_operativo", args=[self.disp.pk, self.edificio.pk]), {
            "tab": "stock",
            **parametros,
        }


class AjustePermisosTests(BaseAjuste):
    def test_sin_sesion_va_al_login(self):
        respuesta = self.client.post(self._url(), self._datos())
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("next=", respuesta.url)

    def test_sin_stock_ajustar_en_ningun_lado_es_403(self):
        solo_ingresa = self._usuario_con("solo_ingresa", ("stock.ver", "stock.ingresar", "stock.entregar"))
        self._entrar(solo_ingresa)
        self.assertEqual(self.client.post(self._url(), self._datos()).status_code, 403)
        self.assertEqual(self._cantidad(self.colchon), 10)

    def test_sin_stock_ver_es_403(self):
        self._entrar(self._usuario_con("sin_ver", ("stock.ajustar",)))
        self.assertEqual(self.client.post(self._url(), self._datos()).status_code, 403)

    def test_otra_institucion_y_su_edificio_son_404(self):
        self._entrar()
        self.assertEqual(self.client.post(self._url(self.disp_b, self.edificio_b), self._datos()).status_code, 404)
        self.assertEqual(self.client.post(self._url(self.disp, self.edificio_b), self._datos()).status_code, 404)

    def test_un_edificio_fuera_del_alcance_es_404(self):
        usuario = self._con_alcance_de_edificios("un_edificio", ("stock.ver", "stock.ajustar"), [self.otro_edificio])
        self._entrar(usuario)
        self.assertEqual(self.client.post(self._url(), self._datos()).status_code, 404)
        self.assertEqual(self._cantidad(self.colchon), 10)

    def test_una_institucion_que_no_lleva_stock_es_404(self):
        self.tipo.maneja_stock = False
        self.tipo.save()
        self._entrar()
        self.assertEqual(self.client.post(self._url(), self._datos()).status_code, 404)

    def test_la_vista_filtra_por_stock_ajustar_en_la_institucion_antes_que_el_servicio(self):
        """Primera capa: con ``stock.ver`` en ``disp`` y ``stock.ajustar`` solo en ``disp_b``, la **vista** da 404 en
        ``disp``. Si la vista pidiera ``stock.ver`` pasaría y el 403 lo daría recién el servicio."""

        usuario = self._usuario_con("ajusta_en_otra", ("stock.ver",))
        rol = self._rol("Ajusta solo en B", ("dispositivo.ver", "stock.ver", "stock.ajustar"))
        usuario.groups.add(rol)  # la capacidad del programa la da el grupo; el equipo la acota a ``disp_b``
        self._miembro(self.disp_b, usuario, rol)
        self._entrar(self._fresco(usuario))
        self.assertEqual(self.client.post(self._url(), self._datos()).status_code, 404)
        self.assertEqual(self._cantidad(self.colchon), 10)

    def test_el_ajuste_es_solo_post(self):
        self._entrar()
        self.assertEqual(self.client.get(self._url()).status_code, 405)

    def test_el_servicio_rechaza_aunque_la_vista_deje_pasar(self):
        """Segunda capa: sin ``stock.ajustar`` el servicio levanta ``PermissionDenied`` aunque se lo llame directo."""

        from django.core.exceptions import PermissionDenied

        sin_ajustar = self._usuario_con("sin_ajustar", ("stock.ver", "stock.ingresar"))
        with self.assertRaises(PermissionDenied):
            servicio.ajustar(sin_ajustar, self.disp, self.edificio, self.colchon, 3, 10, "CONTEO_PERIODICO")
        self.assertEqual(self._cantidad(self.colchon), 10)


class AjustePostTests(BaseAjuste):
    def setUp(self):
        super().setUp()
        self._entrar()

    def test_el_ajuste_lleva_el_saldo_a_lo_contado_asienta_y_vuelve_a_la_solapa(self):
        respuesta = self.client.post(self._url(), self._datos(contada=7))
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta.url, self._url_stock())
        self.assertEqual(self._cantidad(self.colchon), 7)
        movimiento = MovimientoStock.objects.filter(tipo=MovimientoStock.Tipo.AJUSTE).get()
        self.assertEqual((movimiento.cantidad, movimiento.saldo_posterior), (-3, 7))
        self.assertEqual(movimiento.operacion.motivo, OperacionStock.MotivoAjuste.CONTEO_PERIODICO)
        self.assertIn("Ajuste registrado", " ".join(self._mensajes(respuesta)))
        self.assertLibroCoherente()

    def _url_stock(self):
        return reverse("dispositivos:edificio_operativo", args=[self.disp.pk, self.edificio.pk]) + "?tab=stock"

    def test_desde_el_modal_responde_la_orden_de_navegar_y_deja_el_aviso(self):
        respuesta = self.client.post(self._url(), self._datos(contada=12), **AJAX)
        self.assertEqual(respuesta.status_code, 200)
        cuerpo = respuesta.json()
        self.assertTrue(cuerpo["ok"])
        self.assertEqual(cuerpo["redirect"], self._url_stock())
        self.assertEqual(self._cantidad(self.colchon), 12)
        self.assertIn("Ajuste registrado", " ".join(self._mensajes(respuesta)))

    def test_el_motivo_es_obligatorio_y_del_catalogo(self):
        for motivo in ("", "INVENTADO"):
            respuesta = self.client.post(self._url(), self._datos(motivo=motivo), **AJAX)
            self.assertEqual(respuesta.status_code, 400, motivo)
            self.assertIn("motivo", respuesta.json()["errors"])
        self.assertEqual(self._cantidad(self.colchon), 10)

    def test_el_catalogo_de_motivos_es_el_cerrado_del_analisis(self):
        textos = [texto for _valor, texto in OperacionStock.MotivoAjuste.choices]
        self.assertEqual(
            textos,
            [
                "Inventario inicial",
                "Conteo periódico",
                "Rotura o vencimiento",
                "Pérdida o robo",
                "Corrección de carga",
                "Otro",
            ],
        )

    def test_otro_y_correccion_de_carga_piden_el_detalle_y_lo_dice_el_modal(self):
        for motivo in ("OTRO", "CORRECCION_CARGA"):
            respuesta = self.client.post(self._url(), self._datos(motivo=motivo), **AJAX)
            self.assertEqual(respuesta.status_code, 400, motivo)
            self.assertIn("detalle", respuesta.json()["errors"])
        self.assertEqual(self._cantidad(self.colchon), 10)

    def test_otro_con_detalle_ajusta_y_lo_guarda(self):
        respuesta = self.client.post(self._url(), self._datos(motivo="OTRO", detalle="Se mojó el depósito"))
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(self._cantidad(self.colchon), 7)
        self.assertEqual(OperacionStock.objects.get(tipo=OperacionStock.Tipo.AJUSTE).observacion, "Se mojó el depósito")

    def test_la_cantidad_contada_invalida_vuelve_en_su_campo(self):
        for contada in ("", "-1", "abc", "2.5"):
            respuesta = self.client.post(self._url(), self._datos(contada=contada), **AJAX)
            self.assertEqual(respuesta.status_code, 400, contada)
            self.assertIn("cantidad_contada", respuesta.json()["errors"])
        self.assertEqual(self._cantidad(self.colchon), 10)

    def test_contar_lo_mismo_que_hay_no_ajusta_nada(self):
        respuesta = self.client.post(self._url(), self._datos(contada=10), **AJAX)
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("cantidad_contada", respuesta.json()["errors"])
        self.assertFalse(MovimientoStock.objects.filter(tipo=MovimientoStock.Tipo.AJUSTE).exists())

    def test_un_oculto_roto_sube_al_error_general(self):
        respuesta = self.client.post(self._url(), self._datos(uuid_cliente="no-es-un-uuid"), **AJAX)
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("__all__", respuesta.json()["errors"])
        self.assertEqual(self._cantidad(self.colchon), 10)

    def test_un_saldo_que_cambio_reabre_el_modal_con_el_saldo_de_ahora(self):
        """RN-010-12: otro movimiento cambió el saldo mientras se contaba. No se mueve nada; el rechazo vuelve como aviso
        y la página reabre el modal con lo que hay **ahora**."""

        self._sembrar(self.colchon, 15)  # el saldo que vio el modal (10) ya no es el de ahora
        respuesta = self.client.post(self._url(), self._datos(contada=7, visto=10), **AJAX)
        self.assertEqual(respuesta.status_code, 200)
        cuerpo = respuesta.json()
        self.assertTrue(cuerpo["ok"])
        self.assertEqual(cuerpo["redirect"], f"{self._url_stock()}&ajustar={self.colchon.pk}")
        self.assertIn(
            "El saldo cambió mientras contabas: ahora hay 15 y habías visto 10", " ".join(self._mensajes(respuesta))
        )
        self.assertEqual(self._cantidad(self.colchon), 15)
        self.assertFalse(MovimientoStock.objects.filter(tipo=MovimientoStock.Tipo.AJUSTE).exists())
        pagina = self.client.get(cuerpo["redirect"])
        self.assertEqual(pagina.status_code, 200)
        self.assertEqual(pagina.context["ajuste"]["hay"], "Hay 15 ahora (unidad)")
        self.assertEqual(pagina.context["ajuste"]["form"].initial["saldo_visto"], 15)
        self.assertContains(pagina, 'id="modal-ajustar-titulo"')

    def test_un_saldo_que_cambio_sin_javascript_tambien_reabre(self):
        self._sembrar(self.colchon, 15)
        respuesta = self.client.post(self._url(), self._datos(contada=7, visto=10))
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta.url, f"{self._url_stock()}&ajustar={self.colchon.pk}")
        self.assertEqual(self._cantidad(self.colchon), 15)

    def test_doble_post_con_el_mismo_uuid_es_un_solo_ajuste(self):
        datos = self._datos(contada=4)
        self.client.post(self._url(), datos)
        segunda = self.client.post(self._url(), datos)
        self.assertEqual(segunda.status_code, 302)
        self.assertEqual(self._cantidad(self.colchon), 4)
        self.assertEqual(self._ops(OperacionStock.Tipo.AJUSTE).count(), 1)
        self.assertIn("ya estaba registrado", " ".join(self._mensajes(segunda)))

    def test_el_uuid_de_otro_usuario_no_ajusta_y_reabre_con_uno_nuevo(self):
        usado = uuid.uuid4()
        servicio.ajustar(
            self.carga, self.disp, self.edificio, self.frazada, 1, 4, "CONTEO_PERIODICO", uuid_cliente=usado
        )
        otra = self._usuario_con("otra_que_ajusta", ("stock.ver", "stock.ajustar"))
        self._entrar(otra)
        respuesta = self.client.post(self._url(), self._datos(contada=2, uuid_cliente=str(usado)), **AJAX)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["redirect"], f"{self._url_stock()}&ajustar={self.colchon.pk}")
        self.assertEqual(self._cantidad(self.colchon), 10)

    def test_un_insumo_desactivado_se_ajusta_hacia_abajo_y_no_hacia_arriba(self):
        self._sembrar(self.viejo, 5)
        arriba = self.client.post(self._url(), self._datos(self.viejo, contada=9, visto=5), **AJAX)
        self.assertEqual(arriba.status_code, 400)
        self.assertIn("__all__", arriba.json()["errors"])  # `item` no es un campo del modal: va al error general
        abajo = self.client.post(self._url(), self._datos(self.viejo, contada=2, visto=5))
        self.assertEqual(abajo.status_code, 302)
        self.assertEqual(self._cantidad(self.viejo), 2)

    def test_una_institucion_inactiva_puede_vaciar_su_stock(self):
        self.disp.estado = "INACTIVO"
        self.disp.save()
        respuesta = self.client.post(self._url(), self._datos(contada=0, motivo="PERDIDA_ROBO"))
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(self._cantidad(self.colchon), 0)


class AjusteModalTests(BaseAjuste):
    """El modal se arma en la página del edificio con ``?tab=stock&ajustar=<insumo>``."""

    def _get(self, usuario=None, **parametros):
        self._entrar(usuario)
        url, base = self._pagina(**parametros)
        return self.client.get(url, base)

    def test_sin_el_parametro_no_hay_modal(self):
        respuesta = self._get()
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, 'id="modal-ajustar-titulo"')

    def test_el_boton_de_la_fila_abre_el_modal_de_ese_insumo(self):
        respuesta = self._get()
        self.assertContains(respuesta, f"?tab=stock&amp;ajustar={self.colchon.pk}")
        abierto = self._get(ajustar=self.colchon.pk)
        self.assertContains(abierto, 'id="modal-ajustar-titulo"')
        self.assertContains(abierto, "Ajustar · Colchón stock")
        self.assertContains(abierto, "Hay 10 ahora (unidad)")
        self.assertContains(abierto, "data-ajax")
        self.assertContains(abierto, reverse(self.RUTA, args=[self.disp.pk, self.edificio.pk]))

    def test_el_modal_ofrece_el_catalogo_de_motivos_y_nace_con_su_identificador(self):
        form = self._get(ajustar=self.colchon.pk).context["ajuste"]["form"]
        self.assertEqual(
            [valor for valor, _t in form.fields["motivo"].choices],
            ["", *OperacionStock.MotivoAjuste.values],
        )
        self.assertEqual(form.initial["saldo_visto"], 10)
        self.assertIsNotNone(form.initial["uuid_cliente"])

    def test_sin_stock_ajustar_no_hay_boton_ni_modal(self):
        solo_ve = self._usuario_con("solo_ve_modal", ("stock.ver",))
        respuesta = self._get(solo_ve, ajustar=self.colchon.pk)
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, 'id="modal-ajustar-titulo"')
        self.assertNotContains(respuesta, "ajustar=")
        self.assertIn("no se puede ajustar", " ".join(self._mensajes(respuesta)))

    def test_un_insumo_sin_fila_o_inexistente_no_abre_nada(self):
        extra = TipoKit.objects.create(nombre="Sin saldo", unidad="unidad")
        for pedido in (extra.pk, 999999, "abc"):
            respuesta = self._get(ajustar=pedido)
            self.assertEqual(respuesta.status_code, 200)
            self.assertNotContains(respuesta, 'id="modal-ajustar-titulo"')

    def test_un_edificio_inactivo_no_ofrece_el_ajuste(self):
        self.edificio.activo = False
        self.edificio.save()
        respuesta = self._get(ajustar=self.colchon.pk)
        self.assertNotContains(respuesta, 'id="modal-ajustar-titulo"')

    def test_la_pagina_con_el_modal_cuesta_lo_mismo_con_pocos_que_con_muchos_insumos(self):
        peor = self._con_alcance_de_edificios(
            "peor_ajuste",
            ("stock.ver", "stock.entregar", "stock.ingresar", "stock.ajustar", "ciudadano.ver"),
            [self.edificio],
        )

        def consultas():
            self._entrar(peor)
            url, base = self._pagina(ajustar=self.colchon.pk)
            self.client.get(url, base)
            with CaptureQueriesContext(connection) as medidas:
                respuesta = self.client.get(url, base)
            self.assertContains(respuesta, 'id="modal-ajustar-titulo"')
            return len(medidas)

        con_pocos = consultas()
        for numero in range(25):
            self._sembrar(TipoKit.objects.create(nombre=f"Insumo extra {numero:02d}", unidad="unidad"), numero + 1)
        con_muchos = consultas()
        self.assertEqual(con_muchos, con_pocos)
        techo = json.loads(PRESUPUESTOS.read_text(encoding="utf-8"))["servicios"][
            "dispositivos_edificio_operativo_stock"
        ]
        self.assertLessEqual(con_muchos, techo["consultas_fijas"], f"medido con el modal abierto: {con_muchos}")


class MovimientosBase(BaseWeb):
    RUTA = "dispositivos:stock_movimientos"

    def _filas(self, respuesta):
        return respuesta.context["filas"]

    def _get(self, usuario=None, **parametros):
        self._entrar(usuario)
        return self.client.get(self._url(), parametros)

    def _ingresos(self, cuantos):
        for _ in range(cuantos):
            servicio.ingresar_manual(self.carga, self.disp, self.edificio, {self.colchon.pk: 1}, "DONACION")


class MovimientosPermisosTests(MovimientosBase):
    def test_sin_sesion_va_al_login(self):
        respuesta = self.client.get(self._url())
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("next=", respuesta.url)

    def test_sin_stock_ver_es_403(self):
        self._entrar(self._usuario_con("sin_ver_mov", ("stock.ingresar", "stock.ajustar")))
        self.assertEqual(self.client.get(self._url()).status_code, 403)

    def test_otra_institucion_y_su_edificio_son_404(self):
        self._entrar()
        self.assertEqual(self.client.get(self._url(self.disp_b, self.edificio_b)).status_code, 404)
        self.assertEqual(self.client.get(self._url(self.disp, self.edificio_b)).status_code, 404)

    def test_un_edificio_fuera_del_alcance_es_404(self):
        usuario = self._con_alcance_de_edificios("solo_otro_mov", ("stock.ver",), [self.otro_edificio])
        self._entrar(usuario)
        self.assertEqual(self.client.get(self._url()).status_code, 404)
        self.assertEqual(self.client.get(self._url(self.disp, self.otro_edificio)).status_code, 200)

    def test_una_institucion_que_no_lleva_stock_es_404(self):
        self.tipo.maneja_stock = False
        self.tipo.save()
        self._entrar()
        self.assertEqual(self.client.get(self._url()).status_code, 404)

    def test_quien_solo_ve_el_stock_abre_el_listado(self):
        self.assertEqual(self._get(self._usuario_con("solo_ve_mov", ("stock.ver",))).status_code, 200)

    def test_es_solo_lectura(self):
        self._entrar()
        self.assertEqual(self.client.post(self._url(), {}).status_code, 405)


class MovimientosListadoTests(MovimientosBase):
    def test_lista_del_mas_nuevo_al_mas_viejo_y_solo_los_de_este_edificio(self):
        servicio.ingresar_manual(self.carga, self.disp, self.otro_edificio, {self.colchon.pk: 3}, "DONACION")
        respuesta = self._get()
        self.assertEqual(respuesta.status_code, 200)
        filas = self._filas(respuesta)
        self.assertEqual([f["insumo"] for f in filas], ["Frazada stock", "Colchón stock"])
        self.assertContains(respuesta, "Movimientos de stock")

    def test_pagina_de_a_25_y_conserva_los_filtros_en_los_enlaces(self):
        self._ingresos(30)  # + los 2 de la siembra = 32
        primera = self._get(insumo=self.colchon.pk)
        self.assertEqual(len(self._filas(primera)), 25)
        self.assertEqual(primera.context["page_obj"].paginator.count, 31)
        self.assertContains(primera, f"page=2&amp;insumo={self.colchon.pk}")
        segunda = self._get(insumo=self.colchon.pk, page=2)
        self.assertEqual(len(self._filas(segunda)), 6)

    def test_una_pagina_que_no_existe_cae_en_la_ultima(self):
        self._ingresos(30)
        self.assertEqual(len(self._filas(self._get(page=99))), 7)

    def test_filtra_por_insumo(self):
        filas = self._filas(self._get(insumo=self.frazada.pk))
        self.assertEqual([f["insumo"] for f in filas], ["Frazada stock"])

    def test_filtra_por_tipo(self):
        servicio.ajustar(self.carga, self.disp, self.edificio, self.colchon, 7, 10, "CONTEO_PERIODICO")
        filas = self._filas(self._get(tipo="AJUSTE"))
        self.assertEqual([f["tipo_texto"] for f in filas], ["Ajuste por conteo"])

    def test_filtra_por_fechas_inclusivas_y_en_hora_local(self):
        hoy = timezone.localdate()
        manana = hoy + timezone.timedelta(days=1)
        self.assertEqual(len(self._filas(self._get(desde=hoy.isoformat(), hasta=hoy.isoformat()))), 2)
        self.assertEqual(len(self._filas(self._get(desde=manana.isoformat()))), 0)
        self.assertEqual(len(self._filas(self._get(hasta=(hoy - timezone.timedelta(days=1)).isoformat()))), 0)

    def test_un_filtro_invalido_se_ignora_y_no_da_500(self):
        respuesta = self._get(insumo="x", tipo="NO_EXISTE", desde="2026-13-45", hasta="ayer", page="z")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(self._filas(respuesta)), 2)
        self.assertFalse(respuesta.context["hay_filtros"])

    def test_un_hasta_en_la_fecha_maxima_es_sin_tope_y_no_da_500(self):
        """``9999-12-31`` es válida pero el rango del día le suma uno y desborda: se trata como «sin tope»."""

        respuesta = self._get(hasta="9999-12-31")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(self._filas(respuesta)), 2)
        self.assertFalse(respuesta.context["hay_filtros"])

    def test_sin_resultados_distingue_el_filtro_del_edificio_sin_movimientos(self):
        con_filtro = self._get(tipo="AJUSTE")
        self.assertContains(con_filtro, "Ningún movimiento coincide con los filtros")
        self.assertNotContains(con_filtro, "Sin movimientos todavía")
        self._entrar()
        vacio = self.client.get(self._url(self.disp, self.otro_edificio))  # un edificio que nunca se movió
        self.assertContains(vacio, "Sin movimientos todavía")

    def test_el_filtro_de_insumo_ofrece_solo_los_que_se_movieron_aca(self):
        respuesta = self._get()
        self.assertEqual({i.pk for i in respuesta.context["insumos"]}, {self.colchon.pk, self.frazada.pk})
        self.assertContains(respuesta, 'aria-label="Insumo"')
        self.assertContains(respuesta, 'aria-label="Tipo de movimiento"')


class MovimientosPrivacidadTests(MovimientosBase):
    def _entrega(self):
        return servicio.entregar_a_persona(self.guardia, self.disp, self.edificio, "30111222", {self.colchon.pk: 1})

    def test_la_persona_de_una_entrega_solo_se_nombra_con_ciudadano_ver(self):
        self._entrega()
        con = self._get(self.guardia)
        sin = self._get(self.carga)  # stock completo, pero sin ciudadano.ver
        self.assertContains(con, "Paz, Ana")
        self.assertNotContains(sin, "Paz, Ana")
        self.assertNotContains(sin, "30111222")
        self.assertContains(sin, "Entrega a una persona")

    def test_una_entrega_no_nombra_a_la_persona_en_ningun_dato_del_contexto_sin_ciudadano_ver(self):
        self._entrega()
        respuesta = self._get(self.carga)
        self.assertNotIn("Paz", json.dumps(respuesta.context["filas"], default=str))

    def test_un_traspaso_a_otra_institucion_no_la_nombra(self):
        servicio.traspasar(
            self.coordinador, self.disp, self.edificio, self.disp_b, self.edificio_b, {self.colchon.pk: 2}
        )
        respuesta = self._get(self.coordinador)
        self.assertContains(respuesta, "A otra institución")
        self.assertNotContains(respuesta, self.disp_b.nombre)
        self.assertNotContains(respuesta, self.edificio_b.nombre)

    def test_un_traspaso_dentro_de_la_institucion_nombra_el_otro_edificio(self):
        servicio.traspasar(self.carga, self.disp, self.edificio, self.disp, self.otro_edificio, {self.colchon.pk: 2})
        self.assertContains(self._get(), f"A {self.otro_edificio.nombre}")


@tag("performance")
class MovimientosPresupuestoTests(MovimientosBase):
    def _mover(self, vueltas):
        """Por vuelta: un ingreso, una entrega a una persona y un traspaso (cuatro movimientos de tres clases que
        nombran otra fila: el detalle toca la entrega de kit, la persona y el otro edificio)."""

        self._sembrar(self.colchon, 1000)
        for _ in range(vueltas):
            servicio.ingresar_manual(self.carga, self.disp, self.edificio, {self.colchon.pk: 1}, "DONACION")
            servicio.entregar_a_persona(self.guardia, self.disp, self.edificio, "30111222", {self.colchon.pk: 1})
            servicio.traspasar(
                self.carga, self.disp, self.edificio, self.disp, self.otro_edificio, {self.colchon.pk: 1}
            )

    def _consultas(self, usuario):
        self._entrar(usuario)
        self.client.get(self._url())
        with CaptureQueriesContext(connection) as medidas:
            respuesta = self.client.get(self._url())
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(respuesta.context["filas"]), 25)
        return len(medidas)

    def test_el_listado_cuesta_lo_mismo_con_pocos_que_con_muchos_movimientos(self):
        self._mover(8)  # 32 + 2: ya llena la primera página
        con_pocos = self._consultas(self.guardia)
        self._mover(20)
        self.assertEqual(self._consultas(self.guardia), con_pocos)

    def test_cuesta_lo_mismo_con_y_sin_ciudadano_ver_y_en_pocas_consultas(self):
        self._mover(8)
        con_persona = self._consultas(self.guardia)
        sin_persona = self._consultas(self.carga)
        self.assertLessEqual(sin_persona, con_persona)
        techo = json.loads(PRESUPUESTOS.read_text(encoding="utf-8"))["servicios"]["dispositivos_stock_movimientos"]
        self.assertLessEqual(con_persona, techo["consultas_fijas"], f"medido: {con_persona}")

    def test_un_listado_con_filtros_entra_en_el_mismo_techo(self):
        self._mover(8)
        self._entrar(self.guardia)
        parametros = {"insumo": self.colchon.pk, "tipo": "INGRESO", "desde": "2020-01-01", "hasta": "2999-12-31"}
        self.client.get(self._url(), parametros)
        with CaptureQueriesContext(connection) as medidas:
            respuesta = self.client.get(self._url(), parametros)
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.context["hay_filtros"])
        techo = json.loads(PRESUPUESTOS.read_text(encoding="utf-8"))["servicios"]["dispositivos_stock_movimientos"]
        self.assertLessEqual(len(medidas), techo["consultas_fijas"], f"medido con filtros: {len(medidas)}")


class PermisosMemoizadosTests(MovimientosBase):
    """``stock.ver`` se lee una vez por usuario y edificio, y ninguna acción se la salta (RN-010-13)."""

    def test_puede_ver_stock_se_lee_una_sola_vez_por_pagina(self):
        usuario = self._con_alcance_de_edificios("memo", ("stock.ver", "stock.ingresar"), [self.edificio])
        servicio.puede_ver_stock(usuario, self.disp, self.edificio.pk)
        with CaptureQueriesContext(connection) as repetida:
            for _ in range(3):
                self.assertTrue(servicio.puede_ver_stock(usuario, self.disp, self.edificio.pk))
                self.assertTrue(servicio.puede_ver_stock(usuario, self.disp.pk, self.edificio.pk))
        self.assertEqual(len(repetida), 0)

    def test_la_api_publica_ya_no_tiene_una_marca_para_saltarse_stock_ver(self):
        sin_ver = self._usuario_con("ingresa_sin_ver", ("stock.ingresar", "stock.entregar", "stock.ajustar"))
        for permiso in (servicio.puede_ingresar, servicio.puede_entregar, servicio.puede_ajustar):
            with self.assertRaises(TypeError):
                permiso(sin_ver, self.disp, self.edificio.pk, ya_ve=True)
            self.assertFalse(permiso(sin_ver, self.disp, self.edificio.pk))

    def test_el_panel_no_ofrece_botones_sin_stock_ver(self):
        sin_ver = self._usuario_con("panel_sin_ver", ("stock.ingresar", "stock.ajustar"))
        contexto = contexto_de_la_solapa(sin_ver, self.disp, self.edificio)
        self.assertEqual(contexto["acciones"], [])
        self.assertFalse(contexto["puede_ajustar"])
        self.assertEqual(contexto["url_movimientos"], "")

    def test_el_alcance_es_por_edificio_y_el_memo_no_lo_mezcla(self):
        usuario = self._con_alcance_de_edificios("memo_edificios", ("stock.ver",), [self.edificio])
        self.assertTrue(servicio.puede_ver_stock(usuario, self.disp, self.edificio.pk))
        self.assertFalse(servicio.puede_ver_stock(usuario, self.disp, self.otro_edificio.pk))
        self.assertTrue(Alcance.EDIFICIOS)
