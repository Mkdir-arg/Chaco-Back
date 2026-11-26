"""Stock, PR 2b (análisis 010, RN-010-11): el traspaso entre dos pares (institución, edificio) y sus destinos.

Mutaciones verificadas a mano (se rompe la regla, se mira el test rojo, se restaura):

* sacar el ``puede_ingresar`` del destino en ``_destino_de_traspaso`` pone rojo
  ``test_un_destino_fuera_del_alcance_de_quien_traspasa_se_rechaza`` y la propiedad de los destinos;
* sacar ``_exigir_saldo`` de ``_asentar`` pone rojo ``test_la_salida_no_alcanza_y_no_se_mueve_nada``
  (llega el ``IntegrityError`` del ``CHECK``, no ``SaldoInsuficiente``);
* sacar el ``sorted`` de ``_preparar`` pone rojo ``test_los_dos_pares_se_bloquean_por_pk_ascendente_vayan_como_vayan``.
"""

import re
from unittest import mock

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.test.utils import CaptureQueriesContext

from core.tests.candados import orden_de_candados
from programas.models import (
    Dispositivo,
    Edificio,
    MiembroEquipoDispositivo,
    MovimientoStock,
    OperacionStock,
    SaldoStock,
    TipoDispositivo,
)
from programas.services import stock as servicio
from programas.services.dispositivos import CAP_CONFIGURAR
from programas.tests.base_stock import BaseEntrega

Alcance = MiembroEquipoDispositivo.Alcance
CAPS_COORDINADOR = ("stock.ver", "stock.ingresar", "stock.ajustar")


class BaseTraspaso(BaseEntrega):
    def setUp(self):
        super().setUp()
        self._sembrar(self.colchon, 10)
        self.envio = "0b9a3f4e-2c1d-4e5f-8a7b-6c5d4e3f2a1b"
        # Coordina las dos instituciones, y por lo tanto traspasa de una a la otra.
        rol = self._rol("Coordina las dos", ("dispositivo.ver", *CAPS_COORDINADOR))
        self.coordinador = self._usuario("coordina_ab", rol)
        self._miembro(self.disp, self.coordinador, rol)
        self._miembro(self.disp_b, self.coordinador, rol)
        self.coordinador = self._fresco(self.coordinador)
        self.admin = self._usuario_con("admin_programa", ("stock.ver", "stock.ingresar", CAP_CONFIGURAR))

    def _traspasar(self, usuario=None, lineas=None, destino=None, **kwargs):
        destino_dispositivo, destino_edificio = destino or (self.disp, self.otro_edificio)
        return servicio.traspasar(
            usuario or self.carga,
            kwargs.pop("dispositivo", self.disp),
            kwargs.pop("edificio", self.edificio),
            destino_dispositivo,
            destino_edificio,
            lineas if lineas is not None else {self.colchon.pk: 3},
            **kwargs,
        )

    def _sumas(self, operacion):
        return sorted((m.tipo, m.dispositivo_id, m.edificio_id, m.cantidad) for m in operacion.movimientos.all())


class TraspasoTests(BaseTraspaso):
    def test_entre_dos_edificios_de_la_misma_institucion_sale_de_uno_y_entra_en_el_otro(self):
        operacion = self._traspasar(observacion=" por la helada ")

        self.assertFalse(operacion.ya_existia)
        self.assertEqual(operacion.tipo, OperacionStock.Tipo.TRASPASO)
        self.assertEqual((operacion.destino_dispositivo, operacion.destino_edificio), (self.disp, self.otro_edificio))
        self.assertEqual(operacion.observacion, "por la helada")
        self.assertEqual(self._cantidad(self.colchon), 7)
        self.assertEqual(self._cantidad(self.colchon, edificio=self.otro_edificio), 3)
        self.assertLibroCoherente()

    def test_la_salida_y_la_entrada_suman_cero(self):
        self._sembrar(self.frazada, 4)

        operacion = self._traspasar(lineas={self.colchon.pk: 3, self.frazada.pk: 2})

        movimientos = list(operacion.movimientos.all())
        self.assertEqual(len(movimientos), 4)
        self.assertEqual(sum(m.cantidad for m in movimientos), 0)
        for item in (self.colchon, self.frazada):
            del_item = [m for m in movimientos if m.item_id == item.pk]
            self.assertEqual(sorted(m.tipo for m in del_item), ["TRASPASO_ENTRADA", "TRASPASO_SALIDA"])
            self.assertEqual(sum(m.cantidad for m in del_item), 0)
        salida = next(m for m in movimientos if m.item_id == self.colchon.pk and m.tipo == "TRASPASO_SALIDA")
        entrada = next(m for m in movimientos if m.item_id == self.colchon.pk and m.tipo == "TRASPASO_ENTRADA")
        self.assertEqual((salida.cantidad, salida.saldo_posterior, salida.edificio), (-3, 7, self.edificio))
        self.assertEqual((entrada.cantidad, entrada.saldo_posterior, entrada.edificio), (3, 3, self.otro_edificio))
        self.assertLibroCoherente()

    def test_entre_dos_instituciones_y_de_ida_y_vuelta(self):
        ida = self._traspasar(self.coordinador, destino=(self.disp_b, self.edificio_b), lineas={self.colchon.pk: 4})
        self.assertEqual(self._cantidad(self.colchon), 6)
        self.assertEqual(self._cantidad(self.colchon, edificio=self.edificio_b, dispositivo=self.disp_b), 4)
        self.assertEqual((ida.dispositivo, ida.destino_dispositivo), (self.disp, self.disp_b))

        self._traspasar(
            self.coordinador,
            dispositivo=self.disp_b,
            edificio=self.edificio_b,
            destino=(self.disp, self.edificio),
            lineas={self.colchon.pk: 4},
        )

        self.assertEqual(self._cantidad(self.colchon), 10)
        self.assertEqual(self._cantidad(self.colchon, edificio=self.edificio_b, dispositivo=self.disp_b), 0)
        self.assertLibroCoherente()

    def test_un_insumo_desactivado_con_saldo_se_traspasa(self):
        self._sembrar(self.viejo, 2)

        self._traspasar(lineas={self.viejo.pk: 2})

        self.assertEqual(self._cantidad(self.viejo, edificio=self.otro_edificio), 2)

    def test_la_institucion_de_origen_inactiva_puede_vaciarse(self):
        """RN-010-14: la salida de un traspaso se permite con la institución no activa."""

        self.disp.estado = Dispositivo.Estado.INACTIVO
        self.disp.save()

        self._traspasar(self.coordinador, destino=(self.disp_b, self.edificio_b))

        self.assertEqual(self._cantidad(self.colchon), 7)
        self.assertEqual(self._cantidad(self.colchon, edificio=self.edificio_b, dispositivo=self.disp_b), 3)

    def test_la_salida_no_alcanza_y_no_se_mueve_nada(self):
        antes = (OperacionStock.objects.count(), MovimientoStock.objects.count())

        with self.assertRaises(servicio.SaldoInsuficiente) as contexto:
            self._traspasar(lineas={self.colchon.pk: 11})

        self.assertEqual(contexto.exception.faltantes, {self.colchon.pk: (11, 10)})
        # Solo el saldo del origen: el del destino no pisa la clave.
        self.assertEqual(contexto.exception.saldos_actuales, {self.colchon.pk: 10})
        self.assertEqual(self._cantidad(self.colchon), 10)
        self.assertEqual(self._cantidad(self.colchon, edificio=self.otro_edificio), 0)
        self.assertEqual((OperacionStock.objects.count(), MovimientoStock.objects.count()), antes)
        self.assertLibroCoherente()

    def test_una_linea_que_no_alcanza_frena_las_demas(self):
        self._sembrar(self.frazada, 1)

        with self.assertRaises(servicio.SaldoInsuficiente) as contexto:
            self._traspasar(lineas={self.colchon.pk: 3, self.frazada.pk: 2})

        self.assertEqual(set(contexto.exception.faltantes), {self.frazada.pk})
        self.assertEqual(self._cantidad(self.colchon), 10)
        self.assertEqual(self._cantidad(self.colchon, edificio=self.otro_edificio), 0)

    def test_las_lineas_y_la_observacion_se_validan(self):
        for lineas in ({}, {self.colchon.pk: 0}, {999999: 1}):
            with self.subTest(lineas), self.assertRaises(ValidationError) as contexto:
                self._traspasar(lineas=lineas)
            self.assertIn("lineas", contexto.exception.message_dict)
        with self.assertRaises(ValidationError) as contexto:
            self._traspasar(observacion="x" * 201)
        self.assertIn("observacion", contexto.exception.message_dict)


class DestinoDelTraspasoTests(BaseTraspaso):
    def test_un_destino_fuera_del_alcance_de_quien_traspasa_se_rechaza(self):
        antes = OperacionStock.objects.count()

        with self.assertRaises(ValidationError) as contexto:
            self._traspasar(self.carga, destino=(self.disp_b, self.edificio_b))

        self.assertEqual(contexto.exception.message_dict, {"destino": [servicio.DESTINO_INVALIDO]})
        self.assertEqual(self._cantidad(self.colchon), 10)
        self.assertEqual(OperacionStock.objects.count(), antes)

    def test_el_destino_no_dice_si_existe_ni_si_esta_vinculado(self):
        """Fuera de alcance, inexistente y no vinculado dan el mismo texto: no se enumeran instituciones ajenas."""

        sin_vinculo = Edificio.objects.create(codigo="ED-SV", nombre="Sin vínculo")
        casos = {
            "fuera de alcance": (self.disp_b, self.edificio_b),
            "institución inexistente": (999999, self.edificio_b),
            "edificio inexistente": (self.disp, 999999),
            "edificio no vinculado": (self.disp, sin_vinculo),
            "sin edificio": (self.disp, None),
        }
        for nombre, destino in casos.items():
            with self.subTest(nombre), self.assertRaises(ValidationError) as contexto:
                self._traspasar(self.carga, destino=destino)
            self.assertEqual(contexto.exception.message_dict, {"destino": [servicio.DESTINO_INVALIDO]})

    def test_el_administrador_del_programa_traspasa_a_cualquiera(self):
        self._sembrar(self.colchon, 10, edificio=self.edificio, dispositivo=self.disp)

        self._traspasar(self.admin, destino=(self.disp_b, self.edificio_b))

        self.assertEqual(self._cantidad(self.colchon, edificio=self.edificio_b, dispositivo=self.disp_b), 3)

    def test_ver_todos_no_da_destino_porque_no_da_stock_ingresar(self):
        rol = self._rol("Supervisión", ("dispositivo.ver", "dispositivo.ver_todos", "stock.ver", "stock.ingresar"))
        supervisor = self._fresco(self._usuario("supervisor", rol))

        with self.assertRaises(PermissionDenied):
            self._traspasar(supervisor)
        with self.assertRaises(PermissionDenied):
            servicio.destinos_de_traspaso(supervisor, self.disp, self.edificio)

    def test_ver_todos_no_da_destino_aunque_pase_el_origen(self):
        """Pasa el permiso del ORIGEN (miembro de ``disp`` con ``stock.ingresar``) y falla solo en el destino.

        ``dispositivo.ver_todos`` amplía ``stock.ver`` a toda la red, pero no ``stock.ingresar``: sin el segundo
        filtro del destino, un coordinador con ``ver_todos`` traspasaría a cualquier institución.
        """

        rol = self._rol("Opera en A y ve todo", ("dispositivo.ver", "dispositivo.ver_todos", *CAPS_COORDINADOR))
        usuario = self._usuario("ve_todo_opera_en_a", rol)
        self._miembro(self.disp, usuario, rol)
        usuario = self._fresco(usuario)

        with self.assertRaises(ValidationError) as contexto:
            self._traspasar(usuario, destino=(self.disp_b, self.edificio_b))
        self.assertEqual(contexto.exception.message_dict, {"destino": [servicio.DESTINO_INVALIDO]})
        self.assertEqual(self._cantidad(self.colchon), 10)
        destinos = servicio.destinos_de_traspaso(usuario, self.disp, self.edificio)
        self.assertNotIn(self.disp_b, [d for d, _e in destinos])
        self.assertIn((self.disp, self.otro_edificio), destinos)

    def test_el_destino_tambien_necesita_stock_ver(self):
        rol_sin_ver = self._rol("Ingresa sin ver en B", ("dispositivo.ver", "stock.ingresar"))
        rol_con_ver = self._rol("Ve y opera en A", ("dispositivo.ver", "stock.ver", "stock.ingresar"))
        usuario = self._usuario("mixto", rol_con_ver)
        self._miembro(self.disp, usuario, rol_con_ver)
        self._miembro(self.disp_b, usuario, rol_sin_ver)
        usuario = self._fresco(usuario)

        with self.assertRaises(ValidationError):
            self._traspasar(usuario, destino=(self.disp_b, self.edificio_b))

    def test_con_alcance_de_edificios_solo_alcanza_los_suyos(self):
        rol = self._rol("De un edificio", ("dispositivo.ver", "stock.ver", "stock.ingresar"))
        usuario = self._usuario("de_un_edificio", rol)
        miembro = MiembroEquipoDispositivo.objects.create(
            dispositivo=self.disp, usuario=usuario, rol=rol, alcance=Alcance.EDIFICIOS
        )
        miembro.edificios.set([self.edificio])
        usuario = self._fresco(usuario)

        with self.assertRaises(ValidationError):
            self._traspasar(usuario, destino=(self.disp, self.otro_edificio))
        self.assertEqual(self._cantidad(self.colchon, edificio=self.otro_edificio), 0)

    def test_el_origen_tambien_necesita_stock_ingresar_y_alcance(self):
        sin_ingresar = self._usuario_con("sin_ingresar", ("stock.ver", "stock.entregar", "stock.ajustar"))

        with self.assertRaises(PermissionDenied):
            self._traspasar(sin_ingresar)
        with self.assertRaises(PermissionDenied):
            self._traspasar(self.carga, dispositivo=self.disp_b, edificio=self.edificio_b)
        self.assertEqual(self._cantidad(self.colchon), 10)

    def test_el_destino_tiene_que_ser_otro_par(self):
        with self.assertRaises(ValidationError) as contexto:
            self._traspasar(destino=(self.disp, self.edificio))

        self.assertEqual(contexto.exception.message_dict, {"destino": [servicio.TRASPASO_AL_MISMO_LUGAR]})

    def test_un_edificio_compartido_por_dos_instituciones_son_dos_saldos(self):
        self.edificio.dispositivos.add(self.disp_b)

        self._traspasar(self.coordinador, destino=(self.disp_b, self.edificio))

        self.assertEqual(self._cantidad(self.colchon), 7)
        self.assertEqual(self._cantidad(self.colchon, dispositivo=self.disp_b), 3)
        self.assertLibroCoherente()

    def test_un_edificio_destino_inactivo_se_rechaza(self):
        self.otro_edificio.activo = False
        self.otro_edificio.save()

        with self.assertRaises(servicio.StockNoHabilitado) as contexto:
            self._traspasar()

        self.assertEqual(contexto.exception.messages, [servicio.DESTINO_INACTIVO])
        self.assertEqual(self._cantidad(self.colchon), 10)

    def test_una_institucion_destino_que_no_esta_activa_se_rechaza(self):
        self.disp_b.estado = Dispositivo.Estado.INACTIVO
        self.disp_b.save()

        with self.assertRaises(servicio.StockNoHabilitado) as contexto:
            self._traspasar(self.coordinador, destino=(self.disp_b, self.edificio_b))

        self.assertEqual(contexto.exception.messages, [servicio.DESTINO_INACTIVO])
        self.assertEqual(self._cantidad(self.colchon), 10)

    def test_una_institucion_destino_que_no_lleva_stock_se_rechaza(self):
        sin_stock = TipoDispositivo.objects.create(codigo="SIN-STOCK", nombre="Sin stock", maneja_stock=False)
        otra = Dispositivo.objects.create(
            tipo=sin_stock, codigo="SS-1", nombre="No lleva stock", estado=Dispositivo.Estado.ACTIVO
        )
        self.edificio_b.dispositivos.add(otra)

        with self.assertRaises(servicio.StockNoHabilitado):
            self._traspasar(self.admin, destino=(otra, self.edificio_b))

        self.assertEqual(self._cantidad(self.colchon), 10)

    def test_el_origen_que_no_lleva_stock_no_traspasa(self):
        self.tipo.maneja_stock = False
        self.tipo.save()

        with self.assertRaises(servicio.StockNoHabilitado):
            self._traspasar()


class IdempotenciaDelTraspasoTests(BaseTraspaso):
    def test_el_mismo_envio_no_traspasa_dos_veces(self):
        primera = self._traspasar(uuid_cliente=self.envio)
        segunda = self._traspasar(uuid_cliente=self.envio)

        self.assertFalse(primera.ya_existia)
        self.assertTrue(segunda.ya_existia)
        self.assertEqual(segunda.pk, primera.pk)
        self.assertEqual(self._cantidad(self.colchon), 7)
        self.assertEqual(OperacionStock.objects.filter(tipo=OperacionStock.Tipo.TRASPASO).count(), 1)
        self.assertLibroCoherente()

    def test_el_mismo_envio_a_otro_destino_o_de_otro_usuario_es_uuid_en_uso(self):
        self._traspasar(self.coordinador, uuid_cliente=self.envio)

        with self.assertRaises(servicio.UuidEnUso):
            self._traspasar(self.coordinador, destino=(self.disp_b, self.edificio_b), uuid_cliente=self.envio)
        with self.assertRaises(servicio.UuidEnUso):
            self._traspasar(self.carga, uuid_cliente=self.envio)
        with self.assertRaises(servicio.UuidEnUso):
            servicio.ajustar(
                self.coordinador, self.disp, self.edificio, self.colchon, 0, 7, "PERDIDA_ROBO", uuid_cliente=self.envio
            )
        self.assertEqual(self._cantidad(self.colchon), 7)


class CandadosDelTraspasoTests(BaseTraspaso):
    def test_el_orden_es_dispositivo_edificio_saldo(self):
        with orden_de_candados(compartido="institucion", edificio=Edificio.objects, saldo=SaldoStock.objects) as orden:
            self._traspasar(self.coordinador, destino=(self.disp_b, self.edificio_b))

        self.assertEqual(list(dict.fromkeys(orden)), ["institucion", "edificio", "saldo"])
        # Los dos pares se piden de una vez: una sola vez cada tipo, no uno por par.
        self.assertEqual(orden.count("institucion"), 1)

    def test_los_dos_pares_se_bloquean_por_pk_ascendente_vayan_como_vayan(self):
        """A→B y B→A piden las mismas filas en el mismo orden: es lo que evita el interbloqueo (RN-010-19).

        Los pks 7017 y 7010 están elegidos para que un ``set`` de Python los itere de **mayor a menor** (caen en los
        casilleros 1 y 2 de su tabla): sin el ``sorted`` de ``_preparar`` el pedido saldría al revés.
        """

        alto, bajo = 7017, 7010
        instituciones = {
            pk: Dispositivo.objects.create(
                pk=pk, tipo=self.tipo, codigo=f"CRUZ-{pk}", nombre=f"Cruzada {pk}", estado=Dispositivo.Estado.ACTIVO
            )
            for pk in (alto, bajo)
        }
        edificios = {
            pk: Edificio.objects.create(pk=pk, codigo=f"ED-{pk}", nombre=f"Edificio {pk}") for pk in (alto, bajo)
        }
        rol = self._rol("Coordina las cruzadas", ("dispositivo.ver", *CAPS_COORDINADOR))
        usuario = self._usuario("coordina_cruzadas", rol)
        for pk in (alto, bajo):
            edificios[pk].dispositivos.add(instituciones[pk])
            self._miembro(instituciones[pk], usuario, rol)
            self._sembrar(self.colchon, 10, edificio=edificios[pk], dispositivo=instituciones[pk])
        usuario = self._fresco(usuario)
        pedidos = []
        bloquear = servicio.bloquear_instituciones

        def espiar(ids):
            pedidos.append(list(ids))
            return bloquear(ids)

        with mock.patch.object(servicio, "bloquear_instituciones", espiar):
            for origen, destino in ((alto, bajo), (bajo, alto)):
                with CaptureQueriesContext(connection) as consultas:
                    self._traspasar(
                        usuario,
                        dispositivo=instituciones[origen],
                        edificio=edificios[origen],
                        destino=(instituciones[destino], edificios[destino]),
                        lineas={self.colchon.pk: 1},
                    )
                bloqueo_de_edificios = next(
                    q["sql"] for q in consultas if re.search(r'FROM [`"]programas_edificio[`"] WHERE', q["sql"])
                )
                self.assertRegex(bloqueo_de_edificios, r"ORDER BY (1|\S*\bid\S*) ASC$")

        self.assertEqual(pedidos, [[bajo, alto], [bajo, alto]])
        self.assertLibroCoherente()


class DestinosDeTraspasoTests(BaseTraspaso):
    def setUp(self):
        super().setUp()
        sin_stock = TipoDispositivo.objects.create(codigo="SIN-STOCK", nombre="Sin stock", maneja_stock=False)
        self.sin_stock = Dispositivo.objects.create(
            tipo=sin_stock, codigo="SS-1", nombre="No lleva stock", estado=Dispositivo.Estado.ACTIVO
        )
        self.inactiva = Dispositivo.objects.create(
            tipo=self.tipo, codigo="IN-1", nombre="Inactiva", estado=Dispositivo.Estado.INACTIVO
        )
        self.edificio_inactivo = Edificio.objects.create(codigo="ED-IN", nombre="Edificio inactivo", activo=False)
        self.edificio_b.dispositivos.add(self.sin_stock, self.inactiva)
        self.edificio_inactivo.dispositivos.add(self.disp, self.disp_b)

    def _pares(self, usuario, dispositivo=None, edificio=None):
        return [
            (d.pk, e.pk)
            for d, e in servicio.destinos_de_traspaso(usuario, dispositivo or self.disp, edificio or self.edificio)
        ]

    def test_el_coordinador_de_una_institucion_ve_los_otros_edificios_de_ella(self):
        self.assertEqual(self._pares(self.carga), [(self.disp.pk, self.otro_edificio.pk)])

    def test_quien_coordina_dos_instituciones_ve_los_edificios_de_las_dos_sin_el_origen(self):
        self.assertEqual(
            self._pares(self.coordinador),
            sorted(
                [(self.disp.pk, self.otro_edificio.pk), (self.disp_b.pk, self.edificio_b.pk)],
                key=lambda par: (Dispositivo.objects.get(pk=par[0]).nombre, par[0]),
            ),
        )

    def test_el_administrador_ve_toda_la_red_que_lleva_stock_activa(self):
        pares = self._pares(self.admin)

        self.assertEqual(
            set(pares),
            {
                (self.disp.pk, self.otro_edificio.pk),
                (self.disp_b.pk, self.edificio_b.pk),
            },
        )
        # No están: el propio origen, el que no lleva stock, el inactivo y el edificio inactivo.
        self.assertNotIn((self.disp.pk, self.edificio.pk), pares)
        self.assertNotIn((self.sin_stock.pk, self.edificio_b.pk), pares)
        self.assertNotIn((self.inactiva.pk, self.edificio_b.pk), pares)
        self.assertNotIn((self.disp.pk, self.edificio_inactivo.pk), pares)

    def test_el_orden_es_por_nombre_de_institucion_y_de_edificio(self):
        nombres = [(d.nombre, e.nombre) for d, e in servicio.destinos_de_traspaso(self.admin, self.disp, self.edificio)]

        self.assertEqual(nombres, sorted(nombres))

    def test_cada_destino_que_ofrece_es_uno_que_traspasar_acepta_y_al_reves(self):
        """El mismo predicado en las dos puntas: la pantalla no ofrece lo que el servicio rechaza ni al revés."""

        rol = self._rol("De un edificio", ("dispositivo.ver", "stock.ver", "stock.ingresar"))
        de_un_edificio = self._usuario("de_un_edificio", rol)
        miembro = MiembroEquipoDispositivo.objects.create(
            dispositivo=self.disp, usuario=de_un_edificio, rol=rol, alcance=Alcance.EDIFICIOS
        )
        miembro.edificios.set([self.edificio, self.otro_edificio])
        de_un_edificio = self._fresco(de_un_edificio)
        todos = [
            (dispositivo, edificio)
            for dispositivo in Dispositivo.objects.all()
            for edificio in Edificio.objects.filter(dispositivos=dispositivo)
        ]

        for usuario in (self.carga, self.coordinador, self.admin, de_un_edificio):
            ofrecidos = set(self._pares(usuario))
            with self.subTest(usuario.username):
                for dispositivo, edificio in todos:
                    par = (dispositivo.pk, edificio.pk)
                    try:
                        servicio._destino_de_traspaso(usuario, (dispositivo.pk, edificio.pk))
                        alcanzable = True
                    except ValidationError:
                        alcanzable = False
                    activo = (
                        dispositivo.estado == Dispositivo.Estado.ACTIVO
                        and dispositivo.tipo.maneja_stock
                        and edificio.activo
                        and par != (self.disp.pk, self.edificio.pk)
                    )
                    self.assertEqual(par in ofrecidos, alcanzable and activo, par)

    def test_exige_poder_traspasar_desde_el_origen(self):
        sin_ingresar = self._usuario_con("sin_ingresar", ("stock.ver", "stock.entregar"))

        with self.assertRaises(PermissionDenied):
            servicio.destinos_de_traspaso(sin_ingresar, self.disp, self.edificio)
        with self.assertRaises(PermissionDenied):
            servicio.destinos_de_traspaso(self.carga, self.disp_b, self.edificio_b)

    def test_cuesta_una_consulta_de_datos_sin_importar_cuantos_destinos_haya(self):
        for numero in range(5):
            edificio = Edificio.objects.create(codigo=f"ED-X{numero}", nombre=f"Extra {numero}")
            edificio.dispositivos.add(self.disp, self.disp_b)
        servicio.destinos_de_traspaso(self.admin, self.disp, self.edificio)  # tibia la caché de permisos

        with CaptureQueriesContext(connection) as consultas:
            destinos = servicio.destinos_de_traspaso(self.admin, self.disp, self.edificio)

        self.assertGreaterEqual(len(destinos), 10)
        self.assertLessEqual(len(consultas), 3)
