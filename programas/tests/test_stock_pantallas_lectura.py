"""Web de lectura del stock (análisis 010, PR 4): solapa «Stock» del edificio, fila de la tarjeta, aviso de la ficha y
checkbox «Lleva stock» del tipo.

1. La solapa existe solo con un tipo que lleva stock **y** ``stock.ver`` sobre el edificio; fuera de alcance, 404.
2. El panel: saldo por insumo, últimos movimientos, signo escrito y detalle sin datos personales sin ``ciudadano.ver``.
3. Las acciones se ofrecen con su capacidad y solo si su ruta existe (llegan con los PR 5 y 6).
4. La fila «Stock» de la tarjeta es ``None`` sin permiso o con el módulo apagado.
5. El aviso de la ficha: lleva stock y no tiene edificio activo.
6. El checkbox del tipo: dejar de llevar stock con saldo se rechaza (RN-010-16).
7. El costo no crece con los insumos ni con los movimientos.
"""

import json
from unittest import mock

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import tag
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from legajos.models import Ciudadano
from programas.forms import TipoDispositivoForm
from programas.models import Edificio, EntregaKit, MovimientoStock, OperacionStock, SaldoStock, TipoKit
from programas.tests.test_dispositivos_edificio_operativo import BaseOperativo
from programas.tests.test_equipo_alcance_edificio import Alcance

PRESUPUESTOS = settings.BASE_DIR / "scripts" / "perf_budgets.json"
CLAVE_PRESUPUESTO = "dispositivos_edificio_operativo_stock"
CLAVE_FICHA = "dispositivos_detalle_con_edificios"
LECTURA = ("dispositivo.ver", "stock.ver")


class BaseLecturaStock(BaseOperativo):
    def setUp(self):
        super().setUp()
        self.tipo.maneja_stock = True
        self.tipo.save(update_fields=["maneja_stock"])
        self.colchon = TipoKit.objects.create(nombre="Colchón", unidad="unidad", orden=1)
        self.agua = TipoKit.objects.create(nombre="Agua 6 l", unidad="bidón", orden=2)
        self.ve_inst = self._con("Ve stock inst", *LECTURA)
        self.ve_a = self._con("Ve stock A", *LECTURA, alcance=Alcance.EDIFICIOS, edificios=[self.edif_a])
        self.sin_stock = self._con("Sin stock", "dispositivo.ver")

    def _sembrar(self, item, cantidad, edificio=None, dispositivo=None, tipo=None, **operacion):
        """Deja un saldo con su libro coherente, sin pasar por el servicio (que ya prueba el PR 2a)."""

        edificio = edificio or self.edif_a
        dispositivo = dispositivo or self.cis
        campos = {"origen": OperacionStock.Origen.DONACION, **operacion}
        tipo_operacion = tipo or OperacionStock.Tipo.INGRESO_MANUAL
        op = OperacionStock.objects.create(
            tipo=tipo_operacion, dispositivo=dispositivo, edificio=edificio, usuario=self.operador, **campos
        )
        MovimientoStock.objects.create(
            operacion=op,
            tipo=MovimientoStock.Tipo(tipo_operacion if tipo_operacion != OperacionStock.Tipo.AJUSTE else "AJUSTE"),
            dispositivo=dispositivo,
            edificio=edificio,
            item=item,
            cantidad=cantidad or 1,
            saldo_posterior=cantidad,
        )
        SaldoStock.objects.update_or_create(
            dispositivo=dispositivo, edificio=edificio, item=item, defaults={"cantidad": cantidad}
        )
        return op

    def _ficha(self, usuario):
        self.client.force_login(User.objects.get(pk=usuario.pk))
        return self.client.get(reverse("dispositivos:detalle", args=[self.cis.pk]))


class SolapaTests(BaseLecturaStock):
    def test_la_solapa_existe_con_stock_ver_y_un_tipo_que_lleva_stock(self):
        for usuario in (self.ve_inst, self.ve_a):
            with self.subTest(usuario=usuario.username):
                respuesta = self._get(usuario, self.edif_a)

                self.assertIn("stock", respuesta.context["solapas"])
                self.assertContains(respuesta, 'id="tab-stock"')

    def test_sin_stock_ver_no_hay_solapa_y_el_pedido_cae_en_la_de_siempre(self):
        respuesta = self._get(self.sin_stock, self.edif_a, tab="stock")

        self.assertNotIn("stock", respuesta.context["solapas"])
        self.assertNotContains(respuesta, 'id="tab-stock"')
        self.assertNotEqual(respuesta.context["tab"], "stock")
        self.assertFalse(respuesta.context["stock_cargado"])

    def test_un_tipo_que_no_lleva_stock_no_tiene_solapa_aunque_tenga_la_capacidad(self):
        self.tipo.maneja_stock = False
        self.tipo.save(update_fields=["maneja_stock"])

        respuesta = self._get(self.ve_inst, self.edif_a, tab="stock")

        self.assertNotIn("stock", respuesta.context["solapas"])
        self.assertNotContains(respuesta, 'id="tab-stock"')

    def test_un_edificio_fuera_del_alcance_da_404(self):
        self.assertEqual(self._get(self.ve_a, self.edif_b, tab="stock").status_code, 404)

    def test_con_otra_solapa_el_panel_no_se_arma_y_el_boton_navega(self):
        self._sembrar(self.colchon, 5)

        respuesta = self._get(self.ve_inst, self.edif_a, tab="estadias")

        self.assertNotIn("stock", respuesta.context)
        self.assertContains(respuesta, 'id="tab-stock" aria-controls="panel-stock" data-solapa-navega')
        # `escapejs` escribe el `=` de la URL como = dentro del atributo de Alpine.
        self.assertContains(respuesta, f"{self._url(self.edif_a)}?tab\\u003Dstock")
        self.assertEqual(respuesta.context["contadores"]["stock"], 1)

    def test_el_saldo_de_otro_edificio_y_de_otra_institucion_no_aparece(self):
        self._sembrar(self.colchon, 5)
        self._sembrar(self.agua, 9, edificio=self.edif_b)

        respuesta = self._get(self.ve_inst, self.edif_a, tab="stock")

        self.assertEqual([f["nombre"] for f in respuesta.context["stock"]["filas"]], ["Colchón"])
        self.assertNotContains(respuesta, "Agua 6 l")


class PanelTests(BaseLecturaStock):
    def test_muestra_el_saldo_con_el_insumo_sin_existencia_marcado(self):
        self._sembrar(self.colchon, 5)
        self._sembrar(self.agua, 0)

        respuesta = self._get(self.ve_inst, self.edif_a, tab="stock")

        stock = respuesta.context["stock"]
        self.assertEqual(stock["resumen"], "2 insumos · 1 sin existencia")
        self.assertEqual({f["nombre"]: f["cantidad"] for f in stock["filas"]}, {"Colchón": 5, "Agua 6 l": 0})
        self.assertContains(respuesta, "Sin existencia")
        self.assertEqual(respuesta.context["contadores"]["stock"], 2)

    def test_sin_saldo_dice_que_no_hay_stock_cargado(self):
        respuesta = self._get(self.ve_inst, self.edif_a, tab="stock")

        self.assertEqual(respuesta.context["stock"]["resumen"], "Sin stock cargado")
        self.assertContains(respuesta, "Todavía no hay stock cargado en este edificio")

    def test_los_movimientos_llevan_el_signo_escrito_y_el_saldo_que_quedo(self):
        self._sembrar(self.colchon, 5)
        self._sembrar(self.colchon, 3, tipo=OperacionStock.Tipo.AJUSTE, motivo="PERDIDA_ROBO", origen="")

        movimientos = self._get(self.ve_inst, self.edif_a, tab="stock").context["stock"]["movimientos"]

        self.assertEqual([m["cantidad_texto"] for m in movimientos], ["+3", "+5"])
        self.assertEqual([m["queda"] for m in movimientos], [3, 5])
        self.assertIn("Pérdida o robo", movimientos[0]["detalle"])

    def test_el_signo_menos_va_escrito_en_una_salida(self):
        op = self._sembrar(self.colchon, 5)
        MovimientoStock.objects.create(
            operacion=op,
            tipo=MovimientoStock.Tipo.ENTREGA_PERSONA,
            dispositivo=self.cis,
            edificio=self.edif_a,
            item=self.colchon,
            cantidad=-2,
            saldo_posterior=3,
        )

        movimientos = self._get(self.ve_inst, self.edif_a, tab="stock").context["stock"]["movimientos"]

        self.assertEqual(movimientos[0]["cantidad_texto"], "\N{MINUS SIGN}2")
        self.assertFalse(movimientos[0]["suma"])

    def test_la_persona_y_su_observacion_solo_se_nombran_con_ciudadano_ver(self):
        persona = Ciudadano.objects.create(dni="39111222", nombre="Ana", apellido="Pérez")
        op = self._sembrar(
            self.colchon,
            5,
            tipo=OperacionStock.Tipo.ENTREGA_PERSONA,
            ciudadano=persona,
            observacion="Vive sola con dos niños",
            origen="",
        )
        self.assertEqual(op.ciudadano, persona)
        con_persona = self._con("Ve personas", *LECTURA, "ciudadano.ver")

        sin = self._get(self.ve_inst, self.edif_a, tab="stock")
        con = self._get(con_persona, self.edif_a, tab="stock")

        for dato in ("Pérez", "39111222", "Vive sola"):
            self.assertNotContains(sin, dato)
        self.assertContains(sin, "Entrega a una persona")
        self.assertContains(con, "Pérez, Ana")
        self.assertContains(con, "39111222")

    def test_un_traspaso_a_otra_institucion_no_nombra_ni_el_edificio(self):
        otra = self._otra_institucion()
        op = self._sembrar(self.colchon, 5)
        MovimientoStock.objects.create(
            operacion=OperacionStock.objects.create(
                tipo=OperacionStock.Tipo.TRASPASO,
                dispositivo=self.cis,
                edificio=self.edif_a,
                destino_dispositivo=otra,
                destino_edificio=self.edif_b,
                usuario=self.operador,
            ),
            tipo=MovimientoStock.Tipo.TRASPASO_SALIDA,
            dispositivo=self.cis,
            edificio=self.edif_a,
            item=self.colchon,
            cantidad=-1,
            saldo_posterior=4,
        )
        self.assertIsNotNone(op)

        movimientos = self._get(self.ve_inst, self.edif_a, tab="stock").context["stock"]["movimientos"]

        self.assertEqual(movimientos[0]["detalle"], "A otra institución")

    def _otra_institucion(self):
        from programas.models import Dispositivo

        otra = Dispositivo.objects.create(tipo=self.tipo, codigo="GER-9", nombre="Otra", estado="ACTIVO")
        self.edif_b.dispositivos.add(otra)
        return otra


class RutasDeStockTests(BaseLecturaStock):
    """``_url_de_accion`` esconde en silencio una ruta que no existe: un nombre mal escrito no se vería sin este test."""

    def test_los_nombres_de_ruta_que_el_panel_conoce_resuelven(self):
        self.assertEqual(
            reverse("dispositivos:stock_entregar", args=[self.cis.pk, self.edif_a.pk]),
            f"/dispositivos/{self.cis.pk}/edificios/{self.edif_a.pk}/stock/entregar/",
        )

    def test_una_ruta_que_todavia_no_existe_no_dibuja_el_boton_y_una_que_existe_si(self):
        from programas.services.edificio_stock import _url_de_accion

        self.assertEqual(_url_de_accion("dispositivos:stock_ingresar", self.cis, self.edif_a), "")
        self.assertTrue(_url_de_accion("dispositivos:stock_entregar", self.cis, self.edif_a))


class AccionesTests(BaseLecturaStock):
    """Las acciones se ofrecen con su capacidad y solo si su ruta existe (los PR 5 y 6 las crean)."""

    def test_hoy_solo_existe_la_ruta_de_entregar(self):
        """Ingresar, Traspasar y Ajustar llegan con el PR 6: sin su ruta el panel no dibuja un botón que da 404."""

        completa = self._con("Completa", *LECTURA, "stock.entregar", "stock.ingresar", "stock.ajustar", "ciudadano.ver")

        stock = self._get(completa, self.edif_a, tab="stock").context["stock"]

        self.assertEqual([a["texto"] for a in stock["acciones"]], ["Entregar a persona"])
        self.assertTrue(stock["acciones"][0]["url"].endswith("/stock/entregar/"))
        self.assertFalse(stock["puede_ajustar"])

    def test_con_las_rutas_cada_boton_exige_su_capacidad(self):
        entrega = self._con("Entrega", *LECTURA, "stock.entregar", "ciudadano.ver")
        ingresa = self._con("Ingresa", *LECTURA, "stock.ingresar")
        with mock.patch("programas.services.edificio_stock._url_de_accion", return_value="/ruta/"):
            textos = {
                usuario.username: [
                    a["texto"] for a in self._get(usuario, self.edif_a, tab="stock").context["stock"]["acciones"]
                ]
                for usuario in (entrega, ingresa, self.ve_inst)
            }

        self.assertEqual(textos[entrega.username], ["Entregar a persona"])
        self.assertEqual(textos[ingresa.username], ["Ingresar", "Traspasar"])
        self.assertEqual(textos[self.ve_inst.username], [])

    def test_entregar_exige_ciudadano_ver(self):
        sin_ciudadano = self._con("Entrega sin ciudadano", *LECTURA, "stock.entregar")
        with mock.patch("programas.services.edificio_stock._url_de_accion", return_value="/ruta/"):
            stock = self._get(sin_ciudadano, self.edif_a, tab="stock").context["stock"]

        self.assertEqual(stock["acciones"], [])

    def test_un_edificio_inactivo_no_ofrece_acciones(self):
        ingresa = self._con("Ingresa 2", *LECTURA, "stock.ingresar")
        self.edif_a.activo = False
        self.edif_a.save(update_fields=["activo"])
        with mock.patch("programas.services.edificio_stock._url_de_accion", return_value="/ruta/"):
            stock = self._get(ingresa, self.edif_a, tab="stock").context["stock"]

        self.assertEqual(stock["acciones"], [])


class TarjetaYAvisoTests(BaseLecturaStock):
    def _fila(self, usuario, edificio):
        tarjetas = self._ficha(usuario).context["tarjetas_edificios"]
        return next(t for t in tarjetas if t["pk"] == edificio.pk)

    def test_la_fila_resume_los_insumos_y_los_que_no_tienen_existencia(self):
        self._sembrar(self.colchon, 5)
        self._sembrar(self.agua, 0)

        fila = self._fila(self.ve_inst, self.edif_a)

        self.assertEqual(fila["stock"]["texto"], "2 insumos · 1 sin existencia")
        self.assertEqual(fila["stock"]["clase"], "text-fg-warning")
        self.assertEqual(self._fila(self.ve_inst, self.edif_b)["stock"]["texto"], "Sin stock cargado")

    def test_la_fila_es_none_sin_stock_ver_o_con_el_modulo_apagado(self):
        self._sembrar(self.colchon, 5)
        self.assertIsNone(self._fila(self.sin_stock, self.edif_a)["stock"])
        self.tipo.maneja_stock = False
        self.tipo.save(update_fields=["maneja_stock"])

        self.assertIsNone(self._fila(self.ve_inst, self.edif_a)["stock"])

    def test_con_alcance_edificios_la_fila_solo_esta_en_los_suyos(self):
        self._sembrar(self.colchon, 5)
        self._sembrar(self.agua, 2, edificio=self.edif_b)

        acotado = {t["pk"]: t for t in self._ficha(self.ve_a).context["tarjetas_edificios"]}
        completo = {t["pk"]: t for t in self._ficha(self.ve_inst).context["tarjetas_edificios"]}

        self.assertEqual(acotado[self.edif_a.pk]["stock"]["texto"], "1 insumo · 0 sin existencia")
        self.assertNotIn(self.edif_b.pk, acotado)
        self.assertIsNotNone(completo[self.edif_b.pk]["stock"])

    def test_el_aviso_aparece_sin_edificio_activo_y_solo_para_quien_ve_todo(self):
        for edificio in (self.edif_a, self.edif_b):
            edificio.activo = False
            edificio.save(update_fields=["activo"])

        con = self._ficha(self.ve_inst)
        sin = self._ficha(self.sin_stock)
        acotado = self._ficha(self.ve_a)

        self.assertIn("no tiene un edificio activo", con.context["aviso_stock"]["titulo"])
        self.assertIsNone(sin.context["aviso_stock"])
        self.assertIsNone(acotado.context["aviso_stock"])

    def test_el_aviso_no_aparece_con_un_edificio_activo_ni_con_el_modulo_apagado(self):
        self.assertIsNone(self._ficha(self.ve_inst).context["aviso_stock"])
        self.edif_a.activo = False
        self.edif_a.save(update_fields=["activo"])
        self.edif_b.activo = False
        self.edif_b.save(update_fields=["activo"])
        self.tipo.maneja_stock = False
        self.tipo.save(update_fields=["maneja_stock"])

        self.assertIsNone(self._ficha(self.ve_inst).context["aviso_stock"])


class CheckboxDelTipoTests(BaseLecturaStock):
    def _datos(self, **extra):
        return {
            "codigo": self.tipo.codigo,
            "nombre": self.tipo.nombre,
            "umbral_ocupacion_amarillo": 50,
            "umbral_ocupacion_rojo": 80,
            "maneja_sectores_plazas": "on",
            "tipos_plaza_admitidos": ["CAMA"],
            "activo": "on",
            **extra,
        }

    def test_tildar_lleva_stock_se_guarda(self):
        self.tipo.maneja_stock = False
        self.tipo.save(update_fields=["maneja_stock"])

        form = TipoDispositivoForm(self._datos(maneja_stock="on"), instance=self.tipo)

        self.assertTrue(form.is_valid(), form.errors)
        self.assertTrue(form.save().maneja_stock)

    def test_destildar_con_saldo_mayor_que_cero_se_rechaza(self):
        self._sembrar(self.colchon, 5)

        form = TipoDispositivoForm(self._datos(), instance=self.tipo)

        self.assertFalse(form.is_valid())
        self.assertIn("Hay 1 institución", form.errors["maneja_stock"][0])

    def test_si_entra_stock_despues_de_validar_el_guardado_lo_rechaza_bajo_candado(self):
        """La carrera de RN-010-16: la validación vio saldo 0, un ingreso entró, y el guardado no puede destildar."""

        form = TipoDispositivoForm(self._datos(), instance=self.tipo)
        self.assertTrue(form.is_valid(), form.errors)
        self._sembrar(self.colchon, 5)

        with self.assertRaises(ValidationError) as contexto:
            form.save()

        self.assertIn("Hay 1 institución", contexto.exception.message_dict["maneja_stock"][0])
        self.tipo.refresh_from_db()
        self.assertTrue(self.tipo.maneja_stock)

    def test_la_vista_devuelve_el_rechazo_del_guardado_en_el_campo(self):
        admin = User.objects.create_superuser("admin_tipo", "a@x.com", "x")
        self.client.force_login(admin)
        self._sembrar(self.colchon, 5)

        # Sin el aviso temprano del formulario: es el guardado, bajo candado, el que tiene que frenarlo.
        with mock.patch.object(TipoDispositivoForm, "_validar_dejar_de_llevar_stock"):
            respuesta = self.client.post(reverse("dispositivos:tipo_editar", args=[self.tipo.pk]), self._datos())

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("Hay 1 institución", respuesta.context["form"].errors["maneja_stock"][0])
        self.tipo.refresh_from_db()
        self.assertTrue(self.tipo.maneja_stock)

    def test_destildar_con_saldo_cero_se_permite(self):
        self._sembrar(self.colchon, 0)

        form = TipoDispositivoForm(self._datos(), instance=self.tipo)

        self.assertTrue(form.is_valid(), form.errors)
        self.assertFalse(form.save().maneja_stock)

    def test_el_saldo_de_otro_tipo_no_frena_a_este(self):
        from programas.models import Dispositivo, TipoDispositivo

        otro_tipo = TipoDispositivo.objects.create(codigo="OTRO-T", nombre="Otro tipo", maneja_stock=True)
        ajeno = Dispositivo.objects.create(tipo=otro_tipo, codigo="OT-1", nombre="Ajeno", estado="ACTIVO")
        self.edif_b.dispositivos.add(ajeno)
        self._sembrar(self.colchon, 7, edificio=self.edif_b, dispositivo=ajeno)

        form = TipoDispositivoForm(self._datos(), instance=self.tipo)

        self.assertTrue(form.is_valid(), form.errors)


@tag("performance")
class PresupuestoDeStockTests(BaseLecturaStock):
    def _medir(self, usuario, url, **params):
        self.client.force_login(User.objects.get(pk=usuario.pk))
        self.client.get(url, params)
        with CaptureQueriesContext(connection) as consultas:
            respuesta = self.client.get(url, params)
        self.assertEqual(respuesta.status_code, 200)
        return len(consultas)

    def _cargar(self, cuantos, desde=0):
        for numero in range(desde, desde + cuantos):
            item = TipoKit.objects.create(nombre=f"Insumo {numero:02d}", unidad="unidad")
            self._sembrar(item, numero + 1)

    def test_la_solapa_cuesta_lo_mismo_con_1_que_con_30_insumos(self):
        self._cargar(1)
        con_uno = self._medir(self.ve_inst, self._url(self.edif_a), tab="stock")
        self._cargar(29, desde=1)

        con_treinta = self._medir(self.ve_inst, self._url(self.edif_a), tab="stock")

        self.assertEqual(con_treinta, con_uno)
        techo = json.loads(PRESUPUESTOS.read_text(encoding="utf-8"))["servicios"][CLAVE_PRESUPUESTO]
        self.assertLessEqual(con_treinta, techo["consultas_fijas"])

    def _mover_de_todo(self, cuantos, desde=0):
        """``cuantos`` movimientos de **cada** tipo que nombra otra fila (kit, traspaso y entrega a persona), en edif_a."""

        persona, _creada = Ciudadano.objects.get_or_create(
            dni="30777666", defaults={"nombre": "Eva", "apellido": "Sosa"}
        )
        item = TipoKit.objects.create(nombre=f"Movido {desde}", unidad="unidad")
        for numero in range(desde, desde + cuantos):
            entrega = EntregaKit.objects.create(
                numero=f"2026-K-9{numero:05d}",
                dispositivo=self.cis,
                edificio=self.edif_a,
                estado=EntregaKit.Estado.RECIBIDA,
                armada_por=self.ve_inst,
            )
            de_kit = OperacionStock.objects.create(
                tipo=OperacionStock.Tipo.INGRESO_KIT,
                dispositivo=self.cis,
                edificio=self.edif_a,
                usuario=self.ve_inst,
                entrega_kit=entrega,
            )
            traspaso = OperacionStock.objects.create(
                tipo=OperacionStock.Tipo.TRASPASO,
                dispositivo=self.cis,
                edificio=self.edif_b,
                usuario=self.ve_inst,
                destino_dispositivo=self.cis,
                destino_edificio=self.edif_a,
            )
            entrega_persona = OperacionStock.objects.create(
                tipo=OperacionStock.Tipo.ENTREGA_PERSONA,
                dispositivo=self.cis,
                edificio=self.edif_a,
                usuario=self.ve_inst,
                ciudadano=persona,
            )
            for operacion, tipo, cantidad in (
                (de_kit, MovimientoStock.Tipo.INGRESO_KIT, 4),
                (traspaso, MovimientoStock.Tipo.TRASPASO_ENTRADA, 2),
                (entrega_persona, MovimientoStock.Tipo.ENTREGA_PERSONA, -1),
            ):
                MovimientoStock.objects.create(
                    operacion=operacion,
                    tipo=tipo,
                    dispositivo=self.cis,
                    edificio=self.edif_a,
                    item=item,
                    cantidad=cantidad,
                    saldo_posterior=10,
                )

    def test_la_solapa_no_hace_una_consulta_por_cada_tipo_de_movimiento_ni_por_persona(self):
        """Cada fila nombra cosas distintas según su tipo (entrega de kit, edificio de la otra punta, persona): todas
        vienen en la consulta de los movimientos. Sacar uno de esos ``select_related`` hace crecer el costo con las filas."""

        lector = self._con("Lector con persona", *LECTURA, "ciudadano.ver")
        url = self._url(self.edif_a)
        self._mover_de_todo(1)
        con_uno = self._medir(lector, url, tab="stock")

        self._mover_de_todo(7, desde=1)
        con_ocho = self._medir(lector, url, tab="stock")

        self.assertEqual(con_ocho, con_uno)

    def test_la_ficha_con_edificios_no_crece_con_los_edificios_y_el_peor_usuario_entra_en_el_techo(self):
        url = reverse("dispositivos:detalle", args=[self.cis.pk])
        self._cargar(3)
        self.tipo.maneja_stock = False
        self.tipo.save(update_fields=["maneja_stock"])
        sin_modulo = self._medir(self.ve_inst, url)
        self.tipo.maneja_stock = True
        self.tipo.save(update_fields=["maneja_stock"])

        con_dos_edificios = self._medir(self.ve_inst, url)
        for numero in range(4):
            extra = Edificio.objects.create(codigo=f"ED-X{numero}", nombre=f"Edificio extra {numero}")
            extra.dispositivos.add(self.cis)
        con_seis_edificios = self._medir(self.ve_inst, url)

        # El stock suma consultas fijas (el alcance de stock.ver, el resumen agrupado de las tarjetas y el aviso:
        # RN-010-21) y ninguna por tarjeta.
        self.assertLessEqual(con_dos_edificios - sin_modulo, 3)
        techo = json.loads(PRESUPUESTOS.read_text(encoding="utf-8"))["servicios"][CLAVE_FICHA]
        self.assertLessEqual(con_dos_edificios, techo["consultas_fijas"])
        # Cada edificio nuevo suma lo mismo que ya sumaba sin el módulo: la diferencia no depende de cuántos haya.
        self.tipo.maneja_stock = False
        self.tipo.save(update_fields=["maneja_stock"])
        sin_modulo_seis = self._medir(self.ve_inst, url)
        self.assertEqual(con_seis_edificios - sin_modulo_seis, con_dos_edificios - sin_modulo)

    def test_el_superusuario_con_un_tipo_que_lleva_stock_entra_en_el_techo_de_la_ficha(self):
        admin = User.objects.create_superuser("super_ficha", "s@x.com", "x")
        self._cargar(3)

        consultas = self._medir(admin, reverse("dispositivos:detalle", args=[self.cis.pk]))

        techo = json.loads(PRESUPUESTOS.read_text(encoding="utf-8"))["servicios"][CLAVE_FICHA]
        self.assertLessEqual(consultas, techo["consultas_fijas"])
