"""«Ingresar stock» y «Traspasar stock» en la web (análisis 010, PR 6a): permisos en las dos capas, origen «Otro» con su
detalle, insumo inactivo fuera de la lista, destino fuera del alcance, todo o nada e idempotencia por ``uuid_cliente``.

Mutaciones verificadas a mano (se rompe la regla, se mira el test rojo, se restaura):

* sacar el ``puede_operar_edificio`` de ``_OperarStockView._lugar`` pone rojo ``test_un_edificio_fuera_del_alcance_es_404``;
* hacer que ``DestinoForm`` ofrezca todos los pares (sin el filtro de ``destinos_de_traspaso``) pone rojo
  ``test_un_destino_fuera_del_alcance_no_se_ofrece_ni_se_acepta_en_el_get``;
* sacar la guarda de ``claves_sin_campo`` de ``FormConTablaDeCantidades.clean`` pone rojo
  ``test_un_insumo_desactivado_mientras_se_armaba_no_se_descarta_en_silencio``;
* sacar ``activo=True`` de ``insumos_para_ingresar`` pone rojo ``test_el_get_ofrece_solo_insumos_activos``;
* sacar el ``puede_ingresar`` de ``ingresar_manual`` o de ``traspasar`` pone rojo los tests «el servicio rechaza aunque la
  vista deje pasar».
"""

import uuid
from unittest.mock import patch

from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from programas.models import MiembroEquipoDispositivo, OperacionStock, TipoKit
from programas.tests.base_stock import BaseEntrega
from programas.views.stock import IngresarStockView, TraspasarStockView

Alcance = MiembroEquipoDispositivo.Alcance


class BaseWeb(BaseEntrega):
    RUTA = ""
    VISTA = None

    def setUp(self):
        super().setUp()
        self._sembrar(self.colchon, 10)
        self._sembrar(self.frazada, 4)
        self.otro_edificio.dispositivos.add(self.disp)
        # Coordina las dos instituciones, y por lo tanto traspasa de una a la otra.
        rol = self._rol("Coordina las dos", ("dispositivo.ver", "stock.ver", "stock.ingresar"))
        coordinador = self._usuario("coordina_ab", rol)
        self._miembro(self.disp, coordinador, rol)
        self._miembro(self.disp_b, coordinador, rol)
        self.coordinador = self._fresco(coordinador)

    def _url(self, dispositivo=None, edificio=None):
        return reverse(self.RUTA, args=[(dispositivo or self.disp).pk, (edificio or self.edificio).pk])

    def _entrar(self, usuario=None):
        self.client.force_login(User.objects.get(pk=(usuario or self.carga).pk))

    def _mensajes(self, respuesta):
        return [str(m) for m in get_messages(respuesta.wsgi_request)]

    def _con_alcance_de_edificios(self, nombre, capacidades, edificios):
        rol = self._rol(f"Rol {nombre}", ("dispositivo.ver", *capacidades))
        usuario = self._usuario(nombre, rol)
        miembro = MiembroEquipoDispositivo.objects.create(
            dispositivo=self.disp, usuario=usuario, rol=rol, alcance=Alcance.EDIFICIOS
        )
        miembro.edificios.set(edificios)
        return self._fresco(usuario)

    def _ops(self, tipo):
        return OperacionStock.objects.filter(tipo=tipo)


class PermisosComunes:
    """Los mismos 403 y 404 para las dos pantallas (``CAPS`` son las que abren la pantalla)."""

    CAPS = ("stock.ver", "stock.ingresar")

    def _datos_validos(self):
        raise NotImplementedError

    def test_sin_sesion_va_al_login(self):
        respuesta = self.client.get(self._url())
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("next=", respuesta.url)

    def test_sin_stock_ingresar_en_ningun_lado_es_403(self):
        solo_ve = self._usuario_con("solo_ve", ("stock.ver", "stock.entregar", "ciudadano.ver"))
        self._entrar(solo_ve)
        self.assertEqual(self.client.get(self._url()).status_code, 403)
        self.assertEqual(self.client.post(self._url(), self._datos_validos()).status_code, 403)

    def test_sin_stock_ver_es_403(self):
        sin_ver = self._usuario_con("sin_ver", ("stock.ingresar",))
        self._entrar(sin_ver)
        self.assertEqual(self.client.get(self._url()).status_code, 403)

    def test_otra_institucion_y_su_edificio_son_404(self):
        self._entrar()
        self.assertEqual(self.client.get(self._url(self.disp_b, self.edificio_b)).status_code, 404)
        # Un edificio que no es de esta institución, aunque exista.
        self.assertEqual(self.client.get(self._url(self.disp, self.edificio_b)).status_code, 404)

    def test_un_edificio_fuera_del_alcance_es_404(self):
        """Con alcance por edificios, operar un edificio que no es de los suyos es 404 aunque la institución sea suya."""

        usuario = self._con_alcance_de_edificios("un_edificio", self.CAPS, [self.otro_edificio])
        self._entrar(usuario)
        self.assertEqual(self.client.get(self._url(self.disp, self.edificio)).status_code, 404)
        self.assertEqual(self.client.post(self._url(), self._datos_validos()).status_code, 404)
        self.assertEqual(self.client.get(self._url(self.disp, self.otro_edificio)).status_code, 200)

    def test_leer_toda_la_red_pero_operar_en_otro_edificio_es_404(self):
        rol = self._rol("Lee todo, opera uno", ("dispositivo.ver", "dispositivo.ver_todos", *self.CAPS))
        usuario = self._usuario("lee_todo_opera_uno", rol)
        miembro = MiembroEquipoDispositivo.objects.create(
            dispositivo=self.disp, usuario=usuario, rol=rol, alcance=Alcance.EDIFICIOS
        )
        miembro.edificios.set([self.otro_edificio])
        self._entrar(self._fresco(usuario))
        self.assertEqual(self.client.get(self._url(self.disp, self.edificio)).status_code, 404)

    def test_una_institucion_que_no_lleva_stock_es_404(self):
        self.tipo.maneja_stock = False
        self.tipo.save()
        self._entrar()
        self.assertEqual(self.client.get(self._url()).status_code, 404)


class IngresarGetTests(BaseWeb):
    RUTA = "dispositivos:stock_ingresar"

    def test_el_get_ofrece_solo_insumos_activos(self):
        self._entrar()
        respuesta = self.client.get(self._url())
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Colchón stock")
        self.assertContains(respuesta, "Frazada stock")
        self.assertNotContains(respuesta, "Insumo viejo")
        self.assertContains(respuesta, ">En stock</th>")
        self.assertContains(respuesta, "Registrar ingreso")

    def test_un_insumo_activo_sin_saldo_se_ofrece_con_cero(self):
        nuevo = TipoKit.objects.create(nombre="Pañal stock", unidad="paquete")
        self._entrar()
        respuesta = self.client.get(self._url())
        fila = next(f for f in respuesta.context["filas"] if f["nombre"] == nuevo.nombre)
        self.assertEqual(fila["info"][0]["texto"], "0")
        colchon = next(f for f in respuesta.context["filas"] if f["nombre"] == "Colchón stock")
        self.assertEqual(colchon["info"][0]["texto"], "10")

    def test_el_origen_ofrece_el_catalogo_cerrado(self):
        self._entrar()
        respuesta = self.client.get(self._url())
        for texto in ("Donación", "Municipio", "Compra", "Otro programa", "Otro"):
            self.assertContains(respuesta, f">{texto}</option>")

    def test_sin_insumos_activos_avisa_y_no_dibuja_el_formulario(self):
        TipoKit.objects.update(activo=False)
        self._entrar()
        respuesta = self.client.get(self._url())
        self.assertContains(respuesta, "No hay insumos activos")
        self.assertNotContains(respuesta, "Registrar ingreso")

    def test_el_get_no_escribe(self):
        self._entrar()
        self.client.get(self._url())
        self.assertEqual(self._ops(OperacionStock.Tipo.INGRESO_MANUAL).count(), 2)  # los dos sembrados


class IngresarPermisosTests(PermisosComunes, BaseWeb):
    RUTA = "dispositivos:stock_ingresar"

    def _datos_validos(self):
        return {
            "origen": "DONACION",
            "uuid_cliente": str(uuid.uuid4()),
            f"cantidad_{self.colchon.pk}": "1",
        }

    def test_el_servicio_rechaza_aunque_la_vista_deje_pasar(self):
        """Segunda capa: sin el chequeo de la vista, el POST igual muere en el servicio y no escribe nada."""

        lector = self._usuario_con("lector_i", ("stock.ver",))
        self._entrar(lector)

        def dejar_pasar(_vista, _usuario, _dispositivo_pk, _edificio_pk):
            return self.disp, self.edificio

        with patch.object(IngresarStockView, "_lugar", dejar_pasar):
            respuesta = self.client.post(self._url(), self._datos_validos())
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(self._cantidad(self.colchon), 10)


class IngresarPostTests(BaseWeb):
    RUTA = "dispositivos:stock_ingresar"

    def setUp(self):
        super().setUp()
        self._entrar()

    def _datos(self, cantidades, origen="DONACION", uuid_cliente=None, **extra):
        datos = {
            "origen": origen,
            "origen_detalle": "",
            "comprobante": "",
            "uuid_cliente": str(uuid_cliente or uuid.uuid4()),
        }
        for item, cantidad in cantidades.items():
            datos[f"cantidad_{item.pk}"] = cantidad
        datos.update(extra)
        return datos

    def test_ingreso_suma_asienta_y_vuelve_a_la_solapa(self):
        respuesta = self.client.post(
            self._url(), self._datos({self.colchon: 5, self.frazada: 1}, comprobante=" Remito 0001-123 ")
        )
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(respuesta.url.endswith("?tab=stock"))
        self.assertEqual(self._cantidad(self.colchon), 15)
        self.assertEqual(self._cantidad(self.frazada), 5)
        operacion = self._ops(OperacionStock.Tipo.INGRESO_MANUAL).latest("pk")
        self.assertEqual(operacion.origen, OperacionStock.Origen.DONACION)
        self.assertEqual(operacion.comprobante, "Remito 0001-123")
        self.assertEqual(operacion.usuario, self.carga)
        self.assertLibroCoherente()
        self.assertIn("Ingreso registrado", self._mensajes(respuesta)[0])

    def test_un_insumo_sin_fila_de_saldo_recibe_su_primera_carga(self):
        nuevo = TipoKit.objects.create(nombre="Pañal stock", unidad="paquete")
        respuesta = self.client.post(self._url(), self._datos({nuevo: 7}))
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(self._cantidad(nuevo), 7)
        self.assertLibroCoherente()

    def test_cantidades_vacias_o_en_cero_no_se_suman(self):
        respuesta = self.client.post(self._url(), self._datos({self.colchon: 2, self.frazada: 0}))
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(self._cantidad(self.frazada), 4)

    def test_origen_otro_sin_detalle_vuelve_en_su_campo_y_no_suma(self):
        respuesta = self.client.post(self._url(), self._datos({self.colchon: 2}, origen="OTRO"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.context["form"].errors["origen_detalle"])
        self.assertContains(respuesta, "con «Otro» el detalle es obligatorio")
        self.assertEqual(self._cantidad(self.colchon), 10)

    def test_origen_otro_con_detalle_suma_y_lo_guarda(self):
        respuesta = self.client.post(
            self._url(), self._datos({self.colchon: 2}, origen="OTRO", origen_detalle="Vecinos del barrio")
        )
        self.assertEqual(respuesta.status_code, 302)
        operacion = self._ops(OperacionStock.Tipo.INGRESO_MANUAL).latest("pk")
        self.assertEqual((operacion.origen, operacion.origen_detalle), ("OTRO", "Vecinos del barrio"))

    def test_un_origen_fuera_del_catalogo_o_vacio_se_rechaza(self):
        for origen in ("REGALO", ""):
            with self.subTest(origen=origen):
                respuesta = self.client.post(self._url(), self._datos({self.colchon: 1}, origen=origen))
                self.assertEqual(respuesta.status_code, 200)
                self.assertTrue(respuesta.context["form"].errors["origen"])
                self.assertEqual(self._cantidad(self.colchon), 10)

    def test_sin_ninguna_cantidad_vuelve_con_el_error(self):
        respuesta = self.client.post(self._url(), self._datos({}))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Cargá la cantidad de al menos un insumo.")

    def test_la_cantidad_invalida_vuelve_en_su_fila(self):
        respuesta = self.client.post(self._url(), self._datos({self.colchon: "-2"}))
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.context["form"].errors[f"cantidad_{self.colchon.pk}"])
        self.assertEqual(self._cantidad(self.colchon), 10)

    def test_un_insumo_inactivo_no_se_ofrece_y_si_llega_por_post_se_rechaza(self):
        respuesta = self.client.post(self._url(), self._datos({self.colchon: 1, self.viejo: 3}))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Algún insumo se desactivó")
        self.assertEqual(self._cantidad(self.colchon), 10)
        self.assertEqual(self._cantidad(self.viejo), 0)

    def test_un_insumo_desactivado_mientras_se_armaba_no_se_descarta_en_silencio(self):
        """Todo o nada: el colchón se desactivó entre el GET y el POST; la frazada no entra sola con «Ingreso registrado»."""

        self.colchon.activo = False
        self.colchon.save()
        respuesta = self.client.post(self._url(), self._datos({self.colchon: 3, self.frazada: 1}))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Algún insumo se desactivó")
        self.assertEqual(self._cantidad(self.frazada), 4)
        self.assertFalse(self._mensajes(respuesta))

    def test_una_clave_de_cantidad_rara_no_da_500(self):
        respuesta = self.client.post(self._url(), self._datos({self.colchon: 1}, **{"cantidad_²": "2"}))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(self._cantidad(self.colchon), 10)

    def test_doble_post_con_el_mismo_uuid_es_una_sola_operacion(self):
        datos = self._datos({self.colchon: 2})
        primera = self.client.post(self._url(), datos)
        segunda = self.client.post(self._url(), datos)
        self.assertEqual((primera.status_code, segunda.status_code), (302, 302))
        self.assertEqual(self._cantidad(self.colchon), 12)
        self.assertEqual(self._ops(OperacionStock.Tipo.INGRESO_MANUAL).count(), 3)  # los dos sembrados y este
        self.assertIn("ya estaba registrado", self._mensajes(segunda)[-1])
        self.assertLibroCoherente()

    def test_el_uuid_de_otro_usuario_no_suma_y_se_regenera(self):
        usado = uuid.uuid4()
        from programas.services import stock as servicio

        servicio.ingresar_manual(
            self._usuario_con("otra_carga", ("stock.ver", "stock.ingresar")),
            self.disp,
            self.edificio,
            {self.frazada.pk: 1},
            "COMPRA",
            uuid_cliente=usado,
        )
        respuesta = self.client.post(self._url(), self._datos({self.colchon: 1}, uuid_cliente=usado))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(self._cantidad(self.colchon), 10)
        self.assertNotEqual(str(respuesta.context["form"]["uuid_cliente"].value()), str(usado))

    def test_un_post_sin_identificador_del_envio_muestra_el_error_arriba(self):
        datos = self._datos({self.colchon: 1})
        datos.pop("uuid_cliente")
        respuesta = self.client.post(self._url(), datos)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Falta el identificador del envío")
        self.assertEqual(self._cantidad(self.colchon), 10)

    def test_una_institucion_inactiva_vuelve_con_el_motivo(self):
        self.disp.estado = self.disp.Estado.INACTIVO
        self.disp.save()
        respuesta = self.client.post(self._url(), self._datos({self.colchon: 1}))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "no está activa")
        self.assertEqual(self._cantidad(self.colchon), 10)

    def test_los_ids_de_la_pantalla_no_se_repiten_y_la_cantidad_anuncia_su_unidad(self):
        import re

        respuesta = self.client.get(self._url())
        ids = re.findall(r'\sid="([^"]+)"', respuesta.content.decode())
        self.assertFalse({i for i in ids if ids.count(i) > 1})
        self.assertContains(respuesta, f'aria-describedby="ingreso_cantidad_{self.colchon.pk}-ayuda"')


class IngresarPresupuestoTests(BaseWeb):
    RUTA = "dispositivos:stock_ingresar"

    def _consultas(self):
        self._entrar()
        self.client.get(self._url())
        with CaptureQueriesContext(connection) as consultas:
            respuesta = self.client.get(self._url())
        self.assertEqual(respuesta.status_code, 200)
        return len(consultas)

    def test_la_pantalla_cuesta_lo_mismo_con_pocos_que_con_muchos_insumos(self):
        con_pocos = self._consultas()
        for numero in range(30):
            TipoKit.objects.create(nombre=f"Insumo extra {numero:02d}", unidad="unidad")
        self.assertEqual(self._consultas(), con_pocos)


class TraspasarGetTests(BaseWeb):
    RUTA = "dispositivos:stock_traspasar"

    def _opciones(self, respuesta):
        return list(respuesta.context["destino_form"].destinos)

    def test_el_destino_se_elige_entre_los_pares_del_alcance_de_quien_traspasa(self):
        self._entrar(self.coordinador)
        respuesta = self.client.get(self._url())
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(
            sorted(self._opciones(respuesta)),
            sorted([f"{self.disp.pk}:{self.otro_edificio.pk}", f"{self.disp_b.pk}:{self.edificio_b.pk}"]),
        )
        self.assertNotContains(respuesta, "Traspasar</button>")

    def test_un_destino_fuera_del_alcance_no_se_ofrece_ni_se_acepta_en_el_get(self):
        # ``carga`` solo integra el Equipo de ``disp``: la otra institución está fuera de su alcance de carga.
        self._entrar()
        respuesta = self.client.get(self._url())
        self.assertEqual(self._opciones(respuesta), [f"{self.disp.pk}:{self.otro_edificio.pk}"])
        fuera = f"{self.disp_b.pk}:{self.edificio_b.pk}"
        respuesta = self.client.get(self._url(), {"destino": fuera})
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.context["destino_form"].errors["destino"])
        self.assertNotContains(respuesta, "Cantidad a traspasar")
        self.assertNotContains(respuesta, f'value="{fuera}"')

    def test_el_propio_origen_no_se_ofrece(self):
        self._entrar()
        respuesta = self.client.get(self._url(), {"destino": f"{self.disp.pk}:{self.edificio.pk}"})
        self.assertTrue(respuesta.context["destino_form"].errors["destino"])

    def test_con_destino_muestra_la_tabla_con_lo_que_hay_y_no_escribe(self):
        self._sembrar(self.frazada, 0)
        self._entrar()
        antes = OperacionStock.objects.count()
        respuesta = self.client.get(self._url(), {"destino": f"{self.disp.pk}:{self.otro_edificio.pk}"})
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Cantidad a traspasar")
        self.assertContains(respuesta, ">En stock</th>")
        self.assertContains(respuesta, "Colchón stock")
        self.assertNotContains(respuesta, "Frazada stock")
        self.assertContains(respuesta, f'name="destino" value="{self.disp.pk}:{self.otro_edificio.pk}"')
        self.assertEqual(OperacionStock.objects.count(), antes)

    def test_sin_insumos_con_stock_avisa(self):
        self._sembrar(self.colchon, 0)
        self._sembrar(self.frazada, 0)
        self._entrar()
        respuesta = self.client.get(self._url(), {"destino": f"{self.disp.pk}:{self.otro_edificio.pk}"})
        self.assertContains(respuesta, "no tiene insumos con stock")
        self.assertNotContains(respuesta, "Cantidad a traspasar")

    def test_sin_a_donde_traspasar_avisa_y_no_dibuja_el_selector(self):
        self.otro_edificio.dispositivos.remove(self.disp)
        self._entrar()
        respuesta = self.client.get(self._url())
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "No hay a dónde traspasar")
        self.assertNotContains(respuesta, "Elegir el destino")


class TraspasarPermisosTests(PermisosComunes, BaseWeb):
    RUTA = "dispositivos:stock_traspasar"

    def _datos_validos(self):
        return {
            "destino": f"{self.disp.pk}:{self.otro_edificio.pk}",
            "uuid_cliente": str(uuid.uuid4()),
            f"cantidad_{self.colchon.pk}": "1",
        }

    def test_el_servicio_rechaza_aunque_la_vista_deje_pasar(self):
        lector = self._usuario_con("lector_t", ("stock.ver",))
        self._entrar(lector)

        def dejar_pasar(_vista, _usuario, _dispositivo_pk, _edificio_pk):
            return self.disp, self.edificio

        def ofrecer_el_destino(_vista):
            # ``destinos_de_traspaso`` también exige el permiso: sin esto el POST moriría ahí y no probaría ``traspasar``.
            return [(self.disp, self.otro_edificio)]

        with (
            patch.object(TraspasarStockView, "_lugar", dejar_pasar),
            patch.object(TraspasarStockView, "_destinos", ofrecer_el_destino),
        ):
            respuesta = self.client.post(self._url(), self._datos_validos())
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(self._cantidad(self.colchon), 10)
        self.assertEqual(self._cantidad(self.colchon, edificio=self.otro_edificio), 0)


class TraspasarPostTests(BaseWeb):
    RUTA = "dispositivos:stock_traspasar"

    def setUp(self):
        super().setUp()
        self._entrar()
        self.destino = f"{self.disp.pk}:{self.otro_edificio.pk}"

    def _datos(self, cantidades, destino=None, uuid_cliente=None, **extra):
        datos = {
            "destino": self.destino if destino is None else destino,
            "observacion": "",
            "uuid_cliente": str(uuid_cliente or uuid.uuid4()),
        }
        for item, cantidad in cantidades.items():
            datos[f"cantidad_{item.pk}"] = cantidad
        datos.update(extra)
        return datos

    def test_traspaso_mueve_asienta_y_vuelve_a_la_solapa(self):
        respuesta = self.client.post(self._url(), self._datos({self.colchon: 3, self.frazada: 1}, observacion="Helada"))
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(respuesta.url.endswith("?tab=stock"))
        self.assertEqual(self._cantidad(self.colchon), 7)
        self.assertEqual(self._cantidad(self.colchon, edificio=self.otro_edificio), 3)
        self.assertEqual(self._cantidad(self.frazada, edificio=self.otro_edificio), 1)
        operacion = self._ops(OperacionStock.Tipo.TRASPASO).get()
        self.assertEqual((operacion.destino_dispositivo, operacion.destino_edificio), (self.disp, self.otro_edificio))
        self.assertEqual(operacion.observacion, "Helada")
        self.assertLibroCoherente()
        self.assertIn("Traspaso registrado", self._mensajes(respuesta)[0])

    def test_un_destino_fuera_del_alcance_se_rechaza_y_no_mueve_nada(self):
        destino = f"{self.disp_b.pk}:{self.edificio_b.pk}"
        respuesta = self.client.post(self._url(), self._datos({self.colchon: 3}, destino=destino))
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.context["destino_form"].errors["destino"])
        self.assertNotContains(respuesta, "Cantidad a traspasar")
        self.assertEqual(self._cantidad(self.colchon), 10)
        self.assertEqual(self._cantidad(self.colchon, edificio=self.edificio_b, dispositivo=self.disp_b), 0)
        self.assertFalse(self._ops(OperacionStock.Tipo.TRASPASO).exists())

    def test_un_destino_inexistente_o_roto_se_rechaza(self):
        for destino in ("", "abc", "999:999", f"{self.disp.pk}:", ":"):
            with self.subTest(destino=destino):
                respuesta = self.client.post(self._url(), self._datos({self.colchon: 1}, destino=destino))
                self.assertEqual(respuesta.status_code, 200)
                self.assertEqual(self._cantidad(self.colchon), 10)

    def test_saldo_insuficiente_vuelve_al_form_con_el_saldo_de_ahora_y_no_mueve_nada(self):
        respuesta = self.client.post(self._url(), self._datos({self.colchon: 11, self.frazada: 1}))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Hay 10 y pediste 11.")
        # Todo o nada: ni siquiera la frazada que sí alcanzaba.
        self.assertEqual(self._cantidad(self.colchon), 10)
        self.assertEqual(self._cantidad(self.frazada), 4)
        self.assertFalse(self._ops(OperacionStock.Tipo.TRASPASO).exists())
        self.assertEqual(respuesta.context["form"][f"cantidad_{self.colchon.pk}"].value(), "11")

    def test_un_insumo_que_llega_a_cero_entre_el_get_y_el_post_no_se_descarta_en_silencio(self):
        self._sembrar(self.colchon, 0)
        respuesta = self.client.post(self._url(), self._datos({self.colchon: 3, self.frazada: 1}))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Hay 0 y pediste 3.")
        self.assertEqual(self._cantidad(self.frazada), 4)
        self.assertFalse(self._ops(OperacionStock.Tipo.TRASPASO).exists())

    def test_una_cantidad_de_un_insumo_sin_fila_se_rechaza_y_no_se_descarta(self):
        respuesta = self.client.post(self._url(), self._datos({self.frazada: 1}, **{"cantidad_999999": "2"}))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Algún insumo ya no está en el stock de este edificio")
        self.assertEqual(self._cantidad(self.frazada), 4)

    def test_sin_ninguna_cantidad_vuelve_con_el_error(self):
        respuesta = self.client.post(self._url(), self._datos({}))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Cargá la cantidad de al menos un insumo.")

    def test_un_insumo_desactivado_con_saldo_si_se_puede_traspasar(self):
        self.colchon.activo = False
        self.colchon.save()
        respuesta = self.client.post(self._url(), self._datos({self.colchon: 2}))
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(self._cantidad(self.colchon, edificio=self.otro_edificio), 2)

    def test_doble_post_con_el_mismo_uuid_es_un_solo_traspaso(self):
        datos = self._datos({self.colchon: 2})
        primera = self.client.post(self._url(), datos)
        segunda = self.client.post(self._url(), datos)
        self.assertEqual((primera.status_code, segunda.status_code), (302, 302))
        self.assertEqual(self._ops(OperacionStock.Tipo.TRASPASO).count(), 1)
        self.assertEqual(self._cantidad(self.colchon), 8)
        self.assertIn("ya estaba registrado", self._mensajes(segunda)[-1])
        self.assertLibroCoherente()

    def test_el_uuid_de_otro_usuario_no_traspasa_y_se_regenera(self):
        usado = uuid.uuid4()
        from programas.services import stock as servicio

        servicio.traspasar(
            self._usuario_con("otra_t", ("stock.ver", "stock.ingresar")),
            self.disp,
            self.edificio,
            self.disp,
            self.otro_edificio,
            {self.frazada.pk: 1},
            uuid_cliente=usado,
        )
        respuesta = self.client.post(self._url(), self._datos({self.colchon: 1}, uuid_cliente=usado))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(self._cantidad(self.colchon), 10)
        self.assertNotEqual(str(respuesta.context["form"]["uuid_cliente"].value()), str(usado))

    def test_un_destino_inactivo_vuelve_con_el_motivo(self):
        self.otro_edificio.activo = False
        self.otro_edificio.save()
        respuesta = self.client.post(self._url(), self._datos({self.colchon: 1}))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(self._cantidad(self.colchon), 10)
        self.assertEqual(self._cantidad(self.colchon, edificio=self.otro_edificio), 0)

    def test_traspaso_a_otra_institucion_del_alcance(self):
        self._entrar(self.coordinador)
        destino = f"{self.disp_b.pk}:{self.edificio_b.pk}"
        respuesta = self.client.post(self._url(), self._datos({self.colchon: 4}, destino=destino))
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(self._cantidad(self.colchon, edificio=self.edificio_b, dispositivo=self.disp_b), 4)
        self.assertLibroCoherente()


class TraspasarPresupuestoTests(BaseWeb):
    RUTA = "dispositivos:stock_traspasar"

    def _consultas(self):
        self._entrar(self.coordinador)
        url = self._url()
        destino = {"destino": f"{self.disp_b.pk}:{self.edificio_b.pk}"}
        self.client.get(url, destino)
        with CaptureQueriesContext(connection) as consultas:
            respuesta = self.client.get(url, destino)
        self.assertEqual(respuesta.status_code, 200)
        return len(consultas)

    def test_la_pantalla_cuesta_lo_mismo_con_pocos_que_con_muchos_insumos(self):
        con_pocos = self._consultas()
        for numero in range(30):
            self._sembrar(TipoKit.objects.create(nombre=f"Insumo extra {numero:02d}", unidad="unidad"), numero + 1)
        self.assertEqual(self._consultas(), con_pocos)
