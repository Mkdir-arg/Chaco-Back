"""Módulo Emergencia, PR 9: entregas de kits — el modelo, los servicios y los selectores.

Qué fija este archivo, regla por regla (``docs/internal/emergencia/04-kits.md``):

* **RN-4.1 y 4.2** — ``crear_entrega``: al menos una línea, ítems activos, sin repetir,
  cantidades enteras > 0, destino ``ACTIVO``; la unidad se copia (04 §10) y el número sale
  del contador de la serie ``K`` («2026-K-000031»).
* **RN-4.3 a 4.5** — ``recibir_entrega``: una cantidad ≥ 0 por cada línea, remito JPEG de
  hasta 5 MB, estado final según diferencias (la positiva también cuenta), idempotencia
  por ``uuid_cliente``, :class:`EstadoCambioEntrega` si ya fue recibida o cancelada, y la
  recepción no se edita: lo único posible después es ``observar_recepcion``.
* **RN-4.6 a 4.9** — nada toca existencias, un ítem desactivado sigue en las entregas
  viejas, el alcance de la guardia es su dispositivo y cada transición deja traza.
* **Mutación de RN-4.8** — ``recibir_kit`` en el dispositivo A no recibe una entrega de B.
  Se vio en rojo contra la guarda rota antes de quedar verde; el detalle está en el
  docstring del test.
* **Media** — el remito lo bajan la mesa y el Equipo del dispositivo destino, nadie más.
* **Presupuestos** — el listado de E4 con 200 entregas, el resumen de 50 destinos y
  ``mis_dispositivos``, por ``assertNumQueries`` (``@tag("performance")``).

Las carreras de verdad (dos conexiones) van al final con ``@tag("mysql")``: en SQLite
``select_for_update`` es un no-op, así que acá además se fija la **lógica** de cada carrera
con dos objetos viejos de la misma entrega.
"""

import shutil
import tempfile
import uuid
from datetime import datetime, time, timedelta
from unittest import mock

from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, connection, transaction
from django.db.models import UniqueConstraint
from django.test import TransactionTestCase, override_settings, tag
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from core import rbac
from core.tests.test_motor_real import MotorRealMixin
from core.validators import ADJUNTO_MAX_BYTES
from core.views.media import _autorizar
from programas.management.commands.seed_emergencia import asegurar_programa_emergencia
from programas.models import (
    Dispositivo,
    EntradaBitacora,
    EntregaKit,
    LineaEntrega,
    MiembroEquipoDispositivo,
    NumeradorEmergencia,
    TipoDispositivo,
    TipoKit,
    TrazaEntrega,
)
from programas.selectors import kits as selectores
from programas.services import kits as servicio
from programas.services.bitacora import crear_turno
from programas.services.emergencia import EstadoCambio
from programas.services.kits import EstadoCambioEntrega
from programas.tests.test_dispositivos_concurrencia import _permiso, en_paralelo, punto_critico
from programas.tests.test_emergencia_base import _programa
from programas.tests.test_emergencia_casos import JPEG, T0, BaseCasos
from users.models import RolMeta

Estado = EntregaKit.Estado
Accion = TrazaEntrega.Accion

RECIBIR_KIT = "emergencia.recibir_kit"
ADMITIR = "dispositivo.admitir"

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


class BaseKits(BaseCasos):
    """La mesa de ``BaseCasos`` más lo de kits: catálogo, dos dispositivos con guardia y media temporal."""

    def setUp(self):
        super().setUp()
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)
        ajuste = override_settings(MEDIA_ROOT=self.media)
        ajuste.enable()
        self.addCleanup(ajuste.disable)

        self.colchon = TipoKit.objects.create(nombre="Colchón", unidad="unidad", orden=1)
        self.alimentos = TipoKit.objects.create(nombre="Kit alimentario", unidad="kit", orden=2)
        self.agua = TipoKit.objects.create(nombre="Agua 6 l", unidad="bidón", orden=3)
        self.club = self._dispositivo("Club Sarmiento", camas=4, localidad="Resistencia")
        self.escuela = self._dispositivo("Escuela 12", camas=4, localidad="Barranqueras")
        self.guardia = self._guardia("guardia_club", [RECIBIR_KIT], [self.club])
        self.guardia_escuela = self._guardia("guardia_escuela", [RECIBIR_KIT], [self.escuela])

    def _sumar_rol(self, usuario, capacidades, programa, dispositivos=()):
        rol = Group.objects.create(name=f"Rol {usuario.username} {Group.objects.count()}")
        RolMeta.objects.create(grupo=rol, categoria=rbac.CATEGORIA_PROGRAMA, programa=programa, activo=True)
        rol.permissions.add(*[_permiso(codigo) for codigo in capacidades])
        usuario.groups.add(rol)
        for dispositivo in dispositivos:
            MiembroEquipoDispositivo.objects.create(dispositivo=dispositivo, usuario=usuario, rol=rol)
        return User.objects.get(pk=usuario.pk)

    def _guardia(self, nombre, capacidades, dispositivos=()):
        """Un usuario con un rol del programa DISPOSITIVOS, en el Equipo de ``dispositivos``."""
        usuario = User.objects.create_user(username=nombre, password="x", first_name="Gabi", last_name=nombre.title())
        return self._sumar_rol(usuario, capacidades, self.dispositivos, dispositivos)

    def _remito(self, nombre="remito.jpg", contenido=JPEG, tipo="image/jpeg"):
        return SimpleUploadedFile(nombre, contenido, content_type=tipo)

    def _entrega(self, dispositivo=None, lineas=None, usuario=None, **extra):
        if lineas is None:
            lineas = [(self.colchon, 10), (self.alimentos, 3)]
        return servicio.crear_entrega(usuario or self.operador, dispositivo or self.club, lineas, **extra)

    def _en_camino(self, **kwargs):
        return servicio.marcar_en_camino(self._entrega(**kwargs), self.operador)

    def _recibir(self, entrega, cantidades=None, usuario=None, **extra):
        if cantidades is None:
            cantidades = {linea.item_id: linea.cantidad_enviada for linea in entrega.lineas.all()}
        extra.setdefault("remito", self._remito())
        return servicio.recibir_entrega(entrega, usuario or self.guardia, cantidades, **extra)

    def _recibida_con_faltante(self):
        """10 colchones y 3 kits enviados; llegaron 8 colchones."""
        entrega = self._en_camino()
        return self._recibir(entrega, {self.colchon.pk: 8, self.alimentos.pk: 3})

    def _acciones(self, entrega):
        return list(TrazaEntrega.objects.filter(entrega=entrega).order_by("id").values_list("accion", flat=True))

    def _foto_de(self, entrega):
        """Lo que no puede cambiar si una acción se rechaza: la fila y sus líneas."""
        fila = EntregaKit.objects.filter(pk=entrega.pk).values().get()
        lineas = list(LineaEntrega.objects.filter(entrega=entrega).order_by("id").values())
        return fila, lineas, TrazaEntrega.objects.filter(entrega=entrega).count()


# ---------------------------------------------------------------------------
# Modelo
# ---------------------------------------------------------------------------


class ModeloDeEntregaTests(BaseKits):
    def test_str_y_propiedades(self):
        entrega = self._entrega()
        linea = entrega.lineas.select_related("item", "entrega").get(item=self.colchon)

        self.assertEqual(str(entrega), f"Entrega {entrega.numero}")
        self.assertEqual(str(linea), f"Colchón × 10 · entrega {entrega.numero}")
        self.assertEqual(str(TrazaEntrega.objects.get(entrega=entrega)), f"Entrega {entrega.numero} · Entrega armada")
        self.assertTrue(entrega.abierta)
        self.assertFalse(entrega.recibida)
        self.assertIsNone(linea.diferencia)
        self.assertRegex(entrega.carpeta_media, r"^[0-9a-f]{32}$")

    def test_la_traza_es_inmutable(self):
        traza = TrazaEntrega.objects.get(entrega=self._entrega())

        traza.detalle = "otra cosa"
        with self.assertRaises(ValidationError):
            traza.save()
        with self.assertRaises(ValidationError):
            traza.delete()
        with self.assertRaises(ValidationError):
            TrazaEntrega.objects.filter(pk=traza.pk).update(detalle="x")
        with self.assertRaises(ValidationError):
            TrazaEntrega.objects.filter(pk=traza.pk).delete()
        with self.assertRaises(ValidationError):
            TrazaEntrega.objects.bulk_update([traza], ["detalle"])

    def test_un_item_va_una_sola_vez_por_entrega_tambien_en_la_base(self):
        entrega = self._entrega()

        with self.assertRaises(IntegrityError), transaction.atomic():
            LineaEntrega.objects.create(entrega=entrega, item=self.colchon, unidad="unidad", cantidad_enviada=1)

    def test_la_base_no_acepta_una_cantidad_enviada_en_cero(self):
        entrega = self._entrega()

        with self.assertRaises(IntegrityError), transaction.atomic():
            LineaEntrega.objects.create(entrega=entrega, item=self.agua, unidad="bidón", cantidad_enviada=0)

    def test_ningun_unico_del_modelo_es_condicional(self):
        """MySQL y MariaDB ignoran un ``UniqueConstraint(condition=…)``: no se usa ninguno."""
        for modelo in (EntregaKit, LineaEntrega, TrazaEntrega):
            for restriccion in modelo._meta.constraints:
                if isinstance(restriccion, UniqueConstraint):
                    self.assertIsNone(restriccion.condition, restriccion.name)

    def test_el_indice_de_las_pendientes_de_un_dispositivo(self):
        self.assertIn(["dispositivo", "estado"], [indice.fields for indice in EntregaKit._meta.indexes])


# ---------------------------------------------------------------------------
# Crear (RN-4.1, RN-4.2, RN-4.7) y numerar
# ---------------------------------------------------------------------------


class CrearEntregaTests(BaseKits):
    def test_crea_la_entrega_preparada_con_sus_lineas(self):
        entrega = self._entrega(observacion="  Entregar a la directora.  ")

        self.assertEqual(entrega.estado, Estado.PREPARADA)
        self.assertEqual(entrega.dispositivo, self.club)
        self.assertEqual(entrega.armada_por, self.operador)
        self.assertEqual(entrega.observacion_mesa, "Entregar a la directora.")
        self.assertIsNone(entrega.despachada_en)
        self.assertEqual(
            list(entrega.lineas.order_by("id").values_list("item__nombre", "unidad", "cantidad_enviada")),
            [("Colchón", "unidad", 10), ("Kit alimentario", "kit", 3)],
        )
        self.assertEqual(list(entrega.lineas.values_list("cantidad_recibida", flat=True)), [None, None])
        traza = TrazaEntrega.objects.get(entrega=entrega)
        self.assertEqual((traza.accion, traza.estado_anterior, traza.estado_nuevo), ("CREADA", "", "PREPARADA"))
        self.assertEqual(traza.usuario, self.operador)
        self.assertIn("2 ítems para Club Sarmiento", traza.detalle)
        self.assertIn("Entregar a la directora.", traza.detalle)

    def test_el_supervisor_tambien_arma_entregas(self):
        self.assertEqual(self._entrega(usuario=self.supervisor).armada_por, self.supervisor)

    def test_las_lineas_tambien_llegan_como_dict_o_como_dicts(self):
        por_dict = self._entrega(lineas={self.colchon.pk: 2})
        por_dicts = self._entrega(lineas=[{"item": self.agua.pk, "cantidad": "4"}])

        self.assertEqual(list(por_dict.lineas.values_list("item_id", "cantidad_enviada")), [(self.colchon.pk, 2)])
        self.assertEqual(list(por_dicts.lineas.values_list("item_id", "cantidad_enviada")), [(self.agua.pk, 4)])

    def test_quien_no_trabaja_en_la_mesa_no_arma_entregas(self):
        for usuario in (self.agente, self.guardia):
            with self.subTest(usuario=usuario.username), self.assertRaises(PermissionDenied):
                self._entrega(usuario=usuario)
        self.assertFalse(EntregaKit.objects.exists())
        self.assertFalse(NumeradorEmergencia.objects.filter(serie="K").exists())

    def test_rn_4_1_sin_lineas_no_hay_entrega(self):
        for lineas in ([], {}, ()):
            with self.subTest(lineas=lineas), self.assertRaises(ValidationError) as error:
                self._entrega(lineas=lineas)
            self.assertEqual(error.exception.message_dict["lineas"], [servicio.SIN_LINEAS])

    def test_rn_4_1_un_item_repetido_se_rechaza(self):
        with self.assertRaises(ValidationError) as error:
            self._entrega(lineas=[(self.colchon, 2), (self.colchon.pk, 3)])
        self.assertEqual(error.exception.message_dict["lineas"], [servicio.ITEM_REPETIDO])

    def test_rn_4_1_la_cantidad_tiene_que_ser_un_entero_mayor_que_cero(self):
        for cantidad in (0, -1, None, "", "dos", 1.5, True, servicio.CANTIDAD_MAXIMA + 1):
            with self.subTest(cantidad=cantidad), self.assertRaises(ValidationError) as error:
                self._entrega(lineas=[(self.colchon, 2), (self.agua, cantidad)])
            self.assertEqual(error.exception.message_dict["lineas"], [servicio.CANTIDAD_INVALIDA])
        self.assertFalse(EntregaKit.objects.exists())

    def test_rn_4_1_un_item_inactivo_o_que_no_existe_se_rechaza(self):
        TipoKit.objects.filter(pk=self.agua.pk).update(activo=False)

        for item in (self.agua, 999_999, "x"):
            with self.subTest(item=item), self.assertRaises(ValidationError) as error:
                self._entrega(lineas=[(self.colchon, 2), (item, 1)])
            self.assertEqual(error.exception.message_dict["lineas"], [servicio.ITEM_NO_DISPONIBLE])

    def test_rn_4_2_el_destino_tiene_que_estar_activo(self):
        for estado in (Dispositivo.Estado.INACTIVO, Dispositivo.Estado.CERRADO, Dispositivo.Estado.BORRADOR):
            inactivo = self._dispositivo(f"Parroquia {estado}", estado=estado)
            with self.subTest(estado=estado), self.assertRaises(ValidationError) as error:
                self._entrega(dispositivo=inactivo)
            self.assertEqual(error.exception.message_dict["dispositivo"], [servicio.DISPOSITIVO_NO_ACTIVO])

    def test_rn_4_2_el_estado_del_destino_es_el_de_la_base_no_el_de_la_pantalla(self):
        en_pantalla = Dispositivo.objects.get(pk=self.club.pk)
        Dispositivo.objects.filter(pk=self.club.pk).update(estado=Dispositivo.Estado.INACTIVO)

        with self.assertRaises(ValidationError):
            self._entrega(dispositivo=en_pantalla)

    def test_rn_4_2_cualquier_tipo_de_dispositivo_recibe_kits(self):
        """Un merendero no maneja camas y también recibe (RN-4.2)."""
        sin_camas = TipoDispositivo.objects.create(codigo="MERENDERO", nombre="Merendero", tipos_plaza_admitidos=[])
        merendero = self._dispositivo("Merendero Los Pibes", tipo=sin_camas)

        self.assertEqual(self._entrega(dispositivo=merendero).dispositivo, merendero)

    def test_el_numero_es_de_la_serie_k_y_correlativo_por_anio(self):
        primera, segunda = self._entrega(), self._entrega(dispositivo=self.escuela)
        self.assertEqual((primera.numero, segunda.numero), ("2026-K-000001", "2026-K-000002"))

        self.reloj.ahora = timezone.make_aware(datetime(2027, 1, 1, 0, 30))
        self.assertEqual(self._entrega().numero, "2027-K-000001")
        self.assertEqual(
            list(NumeradorEmergencia.objects.filter(serie="K").values_list("anio", "ultimo")), [(2026, 2), (2027, 1)]
        )

    def test_la_serie_k_no_gasta_numeros_de_los_casos_ni_al_reves(self):
        self._caso()
        entrega = self._entrega()
        caso = self._caso()

        self.assertEqual(entrega.numero, "2026-K-000001")
        self.assertEqual(caso.numero, "2026-000002")

    def test_una_entrega_rechazada_no_gasta_numero(self):
        with self.assertRaises(ValidationError):
            self._entrega(lineas=[(self.colchon, 0)])
        self.assertEqual(self._entrega().numero, "2026-K-000001")

    def test_rn_4_7_la_unidad_se_copia_y_el_item_desactivado_sigue_en_la_entrega_vieja(self):
        entrega = self._entrega(lineas=[(self.agua, 6)])

        TipoKit.objects.filter(pk=self.agua.pk).update(unidad="pack", activo=False)

        linea = entrega.lineas.select_related("item").get()
        self.assertEqual((linea.item.nombre, linea.unidad, linea.item.unidad), ("Agua 6 l", "bidón", "pack"))
        self.assertEqual(selectores.resumen_de_items([linea]), "6 Agua 6 l")
        # …y deja de entrar en las nuevas.
        with self.assertRaises(ValidationError):
            self._entrega(lineas=[(self.agua, 1)])

    def test_rn_4_6_nada_toca_existencias(self):
        """No hay stock: armar y recibir no escriben en ninguna tabla que no sea de la entrega."""
        catalogo_antes = list(TipoKit.objects.order_by("pk").values())

        self._recibir(self._en_camino(), {self.colchon.pk: 8, self.alimentos.pk: 5})

        self.assertEqual(list(TipoKit.objects.order_by("pk").values()), catalogo_antes)
        campos = {campo.name for modelo in (TipoKit, EntregaKit, LineaEntrega) for campo in modelo._meta.get_fields()}
        self.assertEqual({campo for campo in campos if "stock" in campo or "existencia" in campo}, set())


# ---------------------------------------------------------------------------
# Marcar en camino y cancelar
# ---------------------------------------------------------------------------


class MarcarEnCaminoTests(BaseKits):
    def test_preparada_pasa_a_en_camino_con_la_hora_de_ahora(self):
        entrega = servicio.marcar_en_camino(self._entrega(), self.otro_operador, transporte="  Camioneta AB123CD ")

        self.assertEqual(entrega.estado, Estado.EN_CAMINO)
        self.assertEqual(entrega.despachada_en, T0)
        self.assertEqual(entrega.transporte, "Camioneta AB123CD")
        traza = TrazaEntrega.objects.filter(entrega=entrega).last()
        self.assertEqual(
            (traza.accion, traza.estado_anterior, traza.estado_nuevo, traza.usuario),
            ("EN_CAMINO", "PREPARADA", "EN_CAMINO", self.otro_operador),
        )
        self.assertEqual(traza.detalle, "Salió a las 10:00 · Camioneta AB123CD")

    def test_la_hora_de_salida_la_puede_cargar_la_mesa(self):
        salida = T0 - timedelta(minutes=40)

        self.assertEqual(servicio.marcar_en_camino(self._entrega(), self.operador, hora=salida).despachada_en, salida)

    def test_una_hora_de_salida_futura_se_rechaza(self):
        entrega = self._entrega()

        with self.assertRaises(ValidationError) as error:
            servicio.marcar_en_camino(entrega, self.operador, hora=T0 + timedelta(minutes=1))
        self.assertEqual(error.exception.message_dict["hora"], [servicio.HORA_FUTURA])
        self.assertEqual(EntregaKit.objects.get(pk=entrega.pk).estado, Estado.PREPARADA)

    def test_un_transporte_demasiado_largo_se_rechaza(self):
        with self.assertRaises(ValidationError) as error:
            servicio.marcar_en_camino(self._entrega(), self.operador, transporte="x" * 121)
        self.assertIn("transporte", error.exception.message_dict)

    def test_solo_la_mesa_la_marca_en_camino(self):
        entrega = self._entrega()

        with self.assertRaises(PermissionDenied):
            servicio.marcar_en_camino(entrega, self.guardia)
        self.assertEqual(EntregaKit.objects.get(pk=entrega.pk).estado, Estado.PREPARADA)

    def test_marcarla_dos_veces_es_un_estado_que_cambio(self):
        """La segunda pestaña tiene la entrega vieja: decide la fila bloqueada, no el objeto."""
        entrega = self._entrega()
        vieja = EntregaKit.objects.get(pk=entrega.pk)
        servicio.marcar_en_camino(entrega, self.operador)

        with self.assertRaises(EstadoCambioEntrega) as error:
            servicio.marcar_en_camino(vieja, self.otro_operador)
        self.assertEqual(error.exception.estado_actual, Estado.EN_CAMINO)
        self.assertIsInstance(error.exception, EstadoCambio)
        self.assertEqual(self._acciones(entrega), ["CREADA", "EN_CAMINO"])


class CancelarEntregaTests(BaseKits):
    def test_se_cancela_preparada_o_en_camino_con_motivo(self):
        for entrega, anterior in ((self._entrega(), "PREPARADA"), (self._en_camino(), "EN_CAMINO")):
            with self.subTest(anterior=anterior):
                cancelada = servicio.cancelar_entrega(entrega, self.operador, "  Se suspendió el envío. ")

                self.assertEqual(cancelada.estado, Estado.CANCELADA)
                self.assertEqual(cancelada.motivo_cancelacion, "Se suspendió el envío.")
                traza = TrazaEntrega.objects.filter(entrega=entrega).last()
                self.assertEqual(
                    (traza.accion, traza.estado_anterior, traza.estado_nuevo, traza.detalle),
                    ("CANCELADA", anterior, "CANCELADA", "Se suspendió el envío."),
                )

    def test_sin_motivo_no_se_cancela(self):
        entrega = self._entrega()

        for motivo in ("", "   ", None, "x" * 201):
            with self.subTest(motivo=motivo), self.assertRaises(ValidationError) as error:
                servicio.cancelar_entrega(entrega, self.operador, motivo)
            self.assertIn("motivo", error.exception.message_dict)
        self.assertEqual(EntregaKit.objects.get(pk=entrega.pk).estado, Estado.PREPARADA)

    def test_solo_la_mesa_cancela(self):
        entrega = self._en_camino()

        with self.assertRaises(PermissionDenied):
            servicio.cancelar_entrega(entrega, self.guardia, "No la quiero")
        self.assertEqual(EntregaKit.objects.get(pk=entrega.pk).estado, Estado.EN_CAMINO)

    def test_una_recibida_o_una_ya_cancelada_no_se_cancela(self):
        recibida = self._recibir(self._en_camino())
        cancelada = servicio.cancelar_entrega(self._entrega(), self.operador, "Error de carga")

        for entrega, estado in ((recibida, Estado.RECIBIDA), (cancelada, Estado.CANCELADA)):
            with self.subTest(estado=estado), self.assertRaises(EstadoCambioEntrega) as error:
                servicio.cancelar_entrega(entrega, self.operador, "Otra vez")
            self.assertEqual(error.exception.estado_actual, estado)
            self.assertEqual(EntregaKit.objects.get(pk=entrega.pk).estado, estado)


# ---------------------------------------------------------------------------
# Recibir (RN-4.3, RN-4.4, RN-4.8)
# ---------------------------------------------------------------------------


class RecibirEntregaTests(BaseKits):
    def test_hu_4_3_sin_tocar_nada_queda_recibida(self):
        entrega = self._en_camino()
        self.reloj.avanzar(hours=2)

        recibida = self._recibir(entrega, observacion="  Todo en orden. ")

        self.assertEqual(recibida.estado, Estado.RECIBIDA)
        self.assertEqual(recibida.recibida_por, self.guardia)
        self.assertEqual(recibida.recibida_en, T0 + timedelta(hours=2))
        self.assertEqual(recibida.observacion_dispositivo, "Todo en orden.")
        self.assertFalse(recibida.ya_existia)
        self.assertEqual(
            list(recibida.lineas.order_by("id").values_list("cantidad_enviada", "cantidad_recibida")),
            [(10, 10), (3, 3)],
        )
        traza = TrazaEntrega.objects.filter(entrega=entrega).last()
        self.assertEqual(
            (traza.accion, traza.estado_anterior, traza.estado_nuevo, traza.detalle, traza.usuario),
            ("RECIBIDA", "EN_CAMINO", "RECIBIDA", "Recibida completa", self.guardia),
        )

    def test_hu_4_3_si_llego_menos_queda_con_diferencias(self):
        recibida = self._recibida_con_faltante()

        self.assertEqual(recibida.estado, Estado.RECIBIDA_CON_DIFERENCIAS)
        self.assertEqual(recibida.lineas.get(item=self.colchon).diferencia, -2)
        self.assertEqual(recibida.lineas.get(item=self.alimentos).diferencia, 0)
        self.assertEqual(TrazaEntrega.objects.filter(entrega=recibida).last().detalle, "1 ítem con diferencia")
        self.assertIn(recibida, selectores.listado_de_entregas({"solapa": selectores.SOLAPA_CON_DIFERENCIAS}))

    def test_rn_4_3_llegar_de_mas_tambien_es_una_diferencia(self):
        recibida = self._recibir(self._en_camino(), {self.colchon.pk: 10, self.alimentos.pk: 4})

        self.assertEqual(recibida.estado, Estado.RECIBIDA_CON_DIFERENCIAS)
        self.assertEqual(recibida.lineas.get(item=self.alimentos).diferencia, 1)

    def test_rn_4_3_cero_es_una_cantidad_valida(self):
        recibida = self._recibir(self._en_camino(), {self.colchon.pk: 0, self.alimentos.pk: "3"})

        self.assertEqual(recibida.estado, Estado.RECIBIDA_CON_DIFERENCIAS)
        self.assertEqual(recibida.lineas.get(item=self.colchon).cantidad_recibida, 0)

    def test_rn_4_3_hace_falta_la_cantidad_de_todas_las_lineas(self):
        entrega = self._en_camino()
        antes = self._foto_de(entrega)

        incompletas = (
            {},
            {self.colchon.pk: 10},
            {self.colchon.pk: 10, self.alimentos.pk: ""},
            {self.colchon.pk: 10, self.alimentos.pk: None},
        )
        for cantidades in incompletas:
            with self.subTest(cantidades=cantidades), self.assertRaises(ValidationError) as error:
                self._recibir(entrega, cantidades)
            self.assertIn("cantidades", error.exception.message_dict)
        self.assertEqual(self._foto_de(entrega), antes)

    def test_rn_4_3_dice_que_item_falta(self):
        with self.assertRaises(ValidationError) as error:
            self._recibir(self._en_camino(), {self.colchon.pk: 10})
        self.assertIn("Kit alimentario", error.exception.message_dict["cantidades"][0])

    def test_rn_4_3_la_cantidad_recibida_es_un_entero_cero_o_mas(self):
        entrega = self._en_camino()

        for cantidad in (-1, "ocho", 2.5, True, servicio.CANTIDAD_MAXIMA + 1):
            with self.subTest(cantidad=cantidad), self.assertRaises(ValidationError) as error:
                self._recibir(entrega, {self.colchon.pk: cantidad, self.alimentos.pk: 3})
            self.assertIn("Colchón", error.exception.message_dict["cantidades"][0])
        self.assertEqual(EntregaKit.objects.get(pk=entrega.pk).estado, Estado.EN_CAMINO)

    def test_rn_4_3_una_cantidad_de_un_item_que_no_es_de_la_entrega_se_rechaza(self):
        with self.assertRaises(ValidationError) as error:
            self._recibir(self._en_camino(), {self.colchon.pk: 10, self.alimentos.pk: 3, self.agua.pk: 1})
        self.assertEqual(error.exception.message_dict["cantidades"], [servicio.ITEM_AJENO])

    def test_rn_4_3_sin_remito_no_se_recibe(self):
        entrega = self._en_camino()
        antes = self._foto_de(entrega)

        with self.assertRaises(ValidationError) as error:
            self._recibir(entrega, remito=None)
        self.assertEqual(error.exception.message_dict["remito"], ["Falta la foto del remito."])
        self.assertEqual(self._foto_de(entrega), antes)

    def test_rn_4_3_el_remito_tiene_que_ser_un_jpeg_de_verdad(self):
        entrega = self._en_camino()
        candidatos = {
            "png": self._remito("remito.png", PNG, "image/png"),
            "png disfrazado": self._remito("remito.jpg", PNG, "image/jpeg"),
            "pdf": self._remito("remito.pdf", b"%PDF-1.4", "application/pdf"),
            "jpeg con otra extensión": self._remito("remito.png", JPEG, "image/png"),
        }

        for nombre, archivo in candidatos.items():
            with self.subTest(remito=nombre), self.assertRaises(ValidationError) as error:
                self._recibir(entrega, remito=archivo)
            self.assertEqual(error.exception.message_dict["remito"], [servicio.REMITO_NO_ES_JPEG])
        self.assertEqual(EntregaKit.objects.get(pk=entrega.pk).estado, Estado.EN_CAMINO)

    def test_rn_4_3_el_remito_no_pasa_de_5_mb(self):
        entrega = self._en_camino()
        justo = self._remito(contenido=JPEG + b"0" * (ADJUNTO_MAX_BYTES - len(JPEG)))
        pasado = self._remito(contenido=JPEG + b"0" * (ADJUNTO_MAX_BYTES - len(JPEG) + 1))

        with self.assertRaises(ValidationError) as error:
            self._recibir(entrega, remito=pasado)
        self.assertEqual(error.exception.message_dict["remito"], ["El archivo no puede superar los 5 MB."])
        self.assertEqual(self._recibir(entrega, remito=justo).estado, Estado.RECIBIDA)

    def test_el_remito_queda_bajo_la_carpeta_opaca_de_la_entrega(self):
        recibida = self._recibir(self._en_camino())

        self.assertTrue(recibida.remito.name.startswith(f"emergencia/entregas/{recibida.carpeta_media}/"))
        self.assertTrue(recibida.remito.name.endswith(".jpg"))
        self.assertNotIn("remito", recibida.remito.name)
        self.assertTrue(recibida.remito.storage.exists(recibida.remito.name))

    def test_si_la_recepcion_falla_el_remito_no_queda_huerfano(self):
        """El archivo y la fila son una sola unidad (``archivos_atomicos``)."""
        entrega = self._en_camino()

        with (
            mock.patch("programas.services.kits._trazar", side_effect=RuntimeError("se cayó")),
            self.assertRaises(RuntimeError),
        ):
            self._recibir(entrega)

        self.assertEqual(EntregaKit.objects.get(pk=entrega.pk).estado, Estado.EN_CAMINO)
        self.assertFalse(EntregaKit.objects.get(pk=entrega.pk).remito)
        carpeta = f"emergencia/entregas/{entrega.carpeta_media}"
        almacen = entrega.remito.storage
        self.assertEqual(almacen.listdir(carpeta)[1] if almacen.exists(carpeta) else [], [])

    def test_recibir_una_preparada_vale_y_lo_dice_la_traza(self):
        recibida = self._recibir(self._entrega())

        self.assertEqual(recibida.estado, Estado.RECIBIDA)
        self.assertIsNone(recibida.despachada_en)
        traza = TrazaEntrega.objects.filter(entrega=recibida).last()
        self.assertEqual((traza.estado_anterior, traza.estado_nuevo), ("PREPARADA", "RECIBIDA"))
        self.assertEqual(traza.detalle, "Recibida completa · Recibida sin marca de salida")

    def test_rn_4_4_el_mismo_uuid_devuelve_la_misma_entrega_sin_reescribir(self):
        envio = uuid.uuid4()
        primera = self._recibir(self._en_camino(), {self.colchon.pk: 8, self.alimentos.pk: 3}, uuid_cliente=envio)
        antes = self._foto_de(primera)
        self.reloj.avanzar(minutes=5)

        # El reenvío trae otras cantidades y hasta le falta el remito: no se mira nada.
        segunda = servicio.recibir_entrega(primera, self.guardia, {self.colchon.pk: 10}, None, uuid_cliente=str(envio))

        self.assertEqual(segunda.pk, primera.pk)
        self.assertTrue(segunda.ya_existia)
        self.assertEqual(segunda.estado, Estado.RECIBIDA_CON_DIFERENCIAS)
        self.assertEqual(self._foto_de(primera), antes)
        self.assertEqual(self._acciones(primera), ["CREADA", "EN_CAMINO", "RECIBIDA"])

    def test_rn_4_4_ya_recibida_con_otro_uuid_o_sin_el_es_un_estado_que_cambio(self):
        recibida = self._recibir(self._en_camino(), uuid_cliente=uuid.uuid4())
        antes = self._foto_de(recibida)

        for otro in (uuid.uuid4(), None):
            with self.subTest(uuid=otro), self.assertRaises(EstadoCambioEntrega) as error:
                self._recibir(recibida, {self.colchon.pk: 1, self.alimentos.pk: 1}, uuid_cliente=otro)
            self.assertEqual(error.exception.estado_actual, Estado.RECIBIDA)
            self.assertIn("ya la recibió Gabi Guardia_Club a las 10:00", error.exception.mensaje)
        self.assertEqual(self._foto_de(recibida), antes)

    def test_la_recibida_desde_el_backoffice_sin_uuid_tambien_frena_a_la_app(self):
        """04 §8: «otra guardia la confirmó desde el backoffice» → 409 para la app."""
        recibida = self._recibir(self._en_camino())

        with self.assertRaises(EstadoCambioEntrega):
            self._recibir(recibida, uuid_cliente=uuid.uuid4())
        self.assertIsNone(EntregaKit.objects.get(pk=recibida.pk).uuid_cliente_recepcion)

    def test_cancelar_gana_y_recibir_se_entera(self):
        """04 §10: la mesa cancela mientras la guardia carga la recepción."""
        entrega = self._en_camino()
        en_la_app = EntregaKit.objects.get(pk=entrega.pk)
        self.reloj.avanzar(hours=5, minutes=2)
        servicio.cancelar_entrega(entrega, self.operador, "El camión volvió")
        antes = self._foto_de(entrega)

        with self.assertRaises(EstadoCambioEntrega) as error:
            self._recibir(en_la_app, {self.colchon.pk: 10, self.alimentos.pk: 3})

        self.assertEqual(error.exception.estado_actual, Estado.CANCELADA)
        self.assertEqual(
            error.exception.mensaje,
            f"Entrega {entrega.numero} cancelada por la mesa a las 15:02. Ya no se puede recibir.",
        )
        self.assertEqual(self._foto_de(entrega), antes)
        self.assertFalse(EntregaKit.objects.get(pk=entrega.pk).remito)

    def test_recibir_gana_y_cancelar_se_entera(self):
        entrega = self._en_camino()
        en_la_mesa = EntregaKit.objects.get(pk=entrega.pk)
        self._recibir(entrega)

        with self.assertRaises(EstadoCambioEntrega) as error:
            servicio.cancelar_entrega(en_la_mesa, self.operador, "Ya no hace falta")

        self.assertEqual(error.exception.estado_actual, Estado.RECIBIDA)
        self.assertEqual(EntregaKit.objects.get(pk=entrega.pk).estado, Estado.RECIBIDA)
        self.assertEqual(EntregaKit.objects.get(pk=entrega.pk).motivo_cancelacion, "")

    def test_un_uuid_que_no_es_un_uuid_se_rechaza(self):
        with self.assertRaises(ValidationError) as error:
            self._recibir(self._en_camino(), uuid_cliente="no-es-un-uuid")
        self.assertEqual(error.exception.message_dict["uuid_cliente"], [servicio.UUID_INVALIDO])

    def test_el_uuid_de_una_recepcion_no_sirve_para_otra_entrega(self):
        envio = uuid.uuid4()
        self._recibir(self._en_camino(), uuid_cliente=envio)
        otra = self._en_camino()

        with self.assertRaises(ValidationError) as error:
            self._recibir(otra, uuid_cliente=envio)
        self.assertEqual(error.exception.message_dict["uuid_cliente"], [servicio.UUID_EN_USO])
        self.assertEqual(EntregaKit.objects.get(pk=otra.pk).estado, Estado.EN_CAMINO)

    def test_un_dispositivo_inactivo_con_una_entrega_abierta_todavia_la_recibe(self):
        """04 §10: la guardia que sigue en el Equipo puede recibir."""
        entrega = self._en_camino()
        Dispositivo.objects.filter(pk=self.club.pk).update(estado=Dispositivo.Estado.INACTIVO)

        self.assertEqual(self._recibir(EntregaKit.objects.get(pk=entrega.pk)).estado, Estado.RECIBIDA)

    def test_el_admin_del_programa_dispositivos_con_la_capacidad_recibe_sin_equipo(self):
        """El alcance total es del admin del programa; la capacidad la tiene que tener igual."""
        admin = self._guardia("admin_disp", ["programa.configurar", RECIBIR_KIT])
        solo_admin = self._guardia("solo_admin", ["programa.configurar"])

        with self.assertRaises(PermissionDenied):
            self._recibir(self._en_camino(), usuario=solo_admin)

        self.assertEqual(self._recibir(self._en_camino(), usuario=admin).recibida_por, admin)


class AlcanceDeLaRecepcionTests(BaseKits):
    """RN-4.8 y el test de mutación de 04 §11."""

    def test_recibir_kit_en_a_no_recibe_una_entrega_de_b(self):
        """**Mutación.** La guardia de la Escuela tiene ``recibir_kit``… en la Escuela.

        Visto en rojo: con la guarda de ``recibir_entrega`` reemplazada por la capacidad
        suelta (``puede_en_programa_dispositivos(usuario, CAP_RECIBIR_KIT)``, sin el Equipo
        de **ese** dispositivo) este test falla con «PermissionDenied not raised» y la
        entrega del Club queda ``RECIBIDA`` por alguien de otra institución. Restaurada la
        guarda, pasa.
        """
        entrega = self._en_camino(dispositivo=self.club)
        antes = self._foto_de(entrega)

        with self.assertRaises(PermissionDenied):
            self._recibir(entrega, usuario=self.guardia_escuela)

        self.assertEqual(self._foto_de(entrega), antes)
        self.assertFalse(EntregaKit.objects.get(pk=entrega.pk).remito)
        self.assertEqual(EntradaBitacora.objects.count(), 0)

    def test_la_capacidad_sin_equipo_no_recibe_nada(self):
        sin_equipo = self._guardia("sin_equipo", [RECIBIR_KIT])

        with self.assertRaises(PermissionDenied):
            self._recibir(self._en_camino(), usuario=sin_equipo)

    def test_estar_en_el_equipo_con_otra_capacidad_no_alcanza(self):
        admisor = self._guardia("admisor", [ADMITIR], [self.club])

        with self.assertRaises(PermissionDenied):
            self._recibir(self._en_camino(), usuario=admisor)

    def test_la_mesa_no_recibe(self):
        """Tabla de RU §4: recibir es del dispositivo."""
        entrega = self._en_camino()

        for usuario in (self.operador, self.supervisor, self.agente):
            with self.subTest(usuario=usuario.username), self.assertRaises(PermissionDenied):
                self._recibir(entrega, usuario=usuario)

    def test_una_fila_del_equipo_dada_de_baja_deja_de_recibir(self):
        entrega = self._en_camino()
        MiembroEquipoDispositivo.objects.filter(usuario=self.guardia).update(activo=False)

        with self.assertRaises(PermissionDenied):
            self._recibir(entrega, usuario=User.objects.get(pk=self.guardia.pk))

    def test_las_pendientes_son_solo_las_de_su_dispositivo(self):
        del_club = self._en_camino(dispositivo=self.club)
        preparada = self._entrega(dispositivo=self.club)
        self._en_camino(dispositivo=self.escuela)
        self._recibir(self._en_camino(dispositivo=self.club))
        servicio.cancelar_entrega(self._entrega(dispositivo=self.club), self.operador, "Error")

        self.assertEqual(list(selectores.entregas_pendientes_de(self.club, self.guardia)), [del_club, preparada])
        self.assertEqual(list(selectores.entregas_pendientes_de(self.escuela, self.guardia)), [])
        self.assertEqual(list(selectores.entregas_pendientes_de(self.club, self.operador)), [])

    def test_las_entregas_al_alcance_no_incluyen_las_de_otro_dispositivo(self):
        del_club = self._en_camino(dispositivo=self.club)
        de_la_escuela = self._en_camino(dispositivo=self.escuela)

        self.assertEqual(list(selectores.entregas_al_alcance(self.guardia)), [del_club])
        self.assertEqual(list(selectores.entregas_al_alcance(self.guardia_escuela)), [de_la_escuela])
        self.assertEqual(list(selectores.entregas_al_alcance(self.operador)), [])

    def test_la_mesa_ve_todas(self):
        self._en_camino(dispositivo=self.club)
        self._en_camino(dispositivo=self.escuela)

        self.assertEqual(selectores.listado_de_entregas().count(), 2)


class BitacoraDeLaRecepcionTests(BaseKits):
    """RU-15: recibir deja una novedad ``GENERAL`` automática en el dispositivo."""

    def _con_turno(self):
        editor = self._guardia("editor_club", ["dispositivo.editar"], [self.club])
        return crear_turno(
            dispositivo=self.club, usuario=editor, nombre="Guardia", hora_desde=time(8), hora_hasta=time(8)
        )

    def test_recibir_deja_la_novedad_automatica_en_el_turno_vigente(self):
        turno = self._con_turno()
        recibida = self._recibida_con_faltante()

        entrada = EntradaBitacora.objects.get()
        self.assertEqual(entrada.dispositivo, self.club)
        self.assertEqual(entrada.turno, turno)
        self.assertEqual(entrada.tipo, EntradaBitacora.Tipo.GENERAL)
        self.assertEqual(entrada.origen, EntradaBitacora.Origen.AUTOMATICA)
        self.assertEqual(entrada.texto, f"Kit recibido N.° {recibida.numero}")
        self.assertEqual(entrada.responsable, self.guardia)
        self.assertEqual(entrada.momento, recibida.recibida_en)

    def test_sin_turno_vigente_se_recibe_igual_y_no_se_inventa_una_novedad(self):
        self.assertEqual(self._recibir(self._en_camino()).estado, Estado.RECIBIDA)
        self.assertFalse(EntradaBitacora.objects.exists())

    def test_el_reenvio_idempotente_no_duplica_la_novedad(self):
        self._con_turno()
        envio = uuid.uuid4()
        recibida = self._recibir(self._en_camino(), uuid_cliente=envio)

        self._recibir(recibida, uuid_cliente=envio)

        self.assertEqual(EntradaBitacora.objects.count(), 1)

    def test_una_recepcion_rechazada_no_deja_novedad(self):
        self._con_turno()

        with self.assertRaises(ValidationError):
            self._recibir(self._en_camino(), remito=None)
        self.assertFalse(EntradaBitacora.objects.exists())


# ---------------------------------------------------------------------------
# RN-4.5: después de recibida, solo una observación de la mesa
# ---------------------------------------------------------------------------


class ObservarRecepcionTests(BaseKits):
    def test_la_mesa_anota_una_observacion_con_traza_y_no_cambia_nada_mas(self):
        recibida = self._recibida_con_faltante()
        lineas_antes = list(LineaEntrega.objects.filter(entrega=recibida).order_by("id").values())

        observada = servicio.observar_recepcion(recibida, self.supervisor, "  El remito decía 10: se reclamó. ")

        self.assertEqual(observada.observacion_mesa, "El remito decía 10: se reclamó.")
        self.assertEqual(observada.estado, Estado.RECIBIDA_CON_DIFERENCIAS)
        self.assertEqual(list(LineaEntrega.objects.filter(entrega=recibida).order_by("id").values()), lineas_antes)
        traza = TrazaEntrega.objects.filter(entrega=recibida).last()
        self.assertEqual(
            (traza.accion, traza.estado_anterior, traza.estado_nuevo, traza.usuario),
            ("OBSERVADA", "RECIBIDA_CON_DIFERENCIAS", "RECIBIDA_CON_DIFERENCIAS", self.supervisor),
        )
        self.assertEqual(traza.detalle, "El remito decía 10: se reclamó.")

    def test_la_nota_original_no_se_pierde_queda_en_la_traza(self):
        entrega = self._entrega(observacion="Entregar a la directora.")
        recibida = self._recibir(entrega)

        servicio.observar_recepcion(recibida, self.operador, "Corrección de la mesa.")

        detalles = list(TrazaEntrega.objects.filter(entrega=recibida).order_by("id").values_list("detalle", flat=True))
        self.assertIn("Entregar a la directora.", detalles[0])
        self.assertEqual(detalles[-1], "Corrección de la mesa.")

    def test_solo_sobre_una_entrega_recibida(self):
        cancelada = servicio.cancelar_entrega(self._entrega(), self.operador, "Error")

        for entrega in (self._entrega(), self._en_camino(), cancelada):
            with self.subTest(estado=entrega.estado), self.assertRaises(EstadoCambioEntrega):
                servicio.observar_recepcion(entrega, self.operador, "Nota")

    def test_sin_texto_no_hay_observacion(self):
        recibida = self._recibir(self._en_camino())

        with self.assertRaises(ValidationError) as error:
            servicio.observar_recepcion(recibida, self.operador, "   ")
        self.assertIn("texto", error.exception.message_dict)

    def test_la_guardia_no_observa(self):
        recibida = self._recibir(self._en_camino())

        with self.assertRaises(PermissionDenied):
            servicio.observar_recepcion(recibida, self.guardia, "Nota")

    def test_rn_4_5_no_hay_ninguna_funcion_que_cambie_las_cantidades_recibidas(self):
        """La recepción no se edita: el servicio público es exactamente este."""
        publicas = {
            nombre
            for nombre, valor in vars(servicio).items()
            if callable(valor) and not nombre.startswith("_") and getattr(valor, "__module__", "") == servicio.__name__
        }
        self.assertEqual(
            publicas,
            {
                "EstadoCambioEntrega",
                "crear_entrega",
                "marcar_en_camino",
                "cancelar_entrega",
                "recibir_entrega",
                "observar_recepcion",
                "validar_remito",
                "puede_recibir",
                "estado_visible_de_entrega",
                "siguiente_numero_de_entrega",
            },
        )


# ---------------------------------------------------------------------------
# Reponer (HU-4.5)
# ---------------------------------------------------------------------------


class ReponerTests(BaseKits):
    def test_los_faltantes_son_las_diferencias_negativas(self):
        entrega = self._en_camino(lineas=[(self.colchon, 10), (self.alimentos, 3), (self.agua, 6)])
        recibida = self._recibir(entrega, {self.colchon.pk: 8, self.alimentos.pk: 5, self.agua.pk: 6})

        faltantes = selectores.faltantes_de(selectores.lineas_de(recibida))

        self.assertEqual(faltantes, [(self.colchon, 2)])

    def test_un_item_desactivado_no_entra_en_la_precarga(self):
        recibida = self._recibida_con_faltante()
        TipoKit.objects.filter(pk=self.colchon.pk).update(activo=False)

        self.assertEqual(selectores.faltantes_de(selectores.lineas_de(recibida)), [])

    def test_la_reposicion_guarda_a_quien_repone_y_se_ve_en_los_dos_sentidos(self):
        original = self._recibida_con_faltante()
        faltantes = selectores.faltantes_de(selectores.lineas_de(original))

        reposicion = self._entrega(lineas=faltantes, repone_a=original)

        self.assertEqual(reposicion.repone_a, original)
        self.assertEqual(reposicion.dispositivo, original.dispositivo)
        self.assertEqual(list(reposicion.lineas.values_list("item_id", "cantidad_enviada")), [(self.colchon.pk, 2)])
        self.assertEqual(selectores.reposiciones_de(original), [reposicion])
        self.assertIn(f"repone a la entrega {original.numero}", TrazaEntrega.objects.get(entrega=reposicion).detalle)

    def test_solo_se_repone_una_recibida_con_diferencias_del_mismo_dispositivo(self):
        con_faltante = self._recibida_con_faltante()
        completa = self._recibir(self._en_camino())
        abierta = self._en_camino()

        casos = {
            "completa": (self.club, completa),
            "abierta": (self.club, abierta),
            "otro dispositivo": (self.escuela, con_faltante),
            "inexistente": (self.club, 999_999),
        }
        for nombre, (dispositivo, repone_a) in casos.items():
            with self.subTest(caso=nombre), self.assertRaises(ValidationError) as error:
                self._entrega(dispositivo=dispositivo, lineas=[(self.colchon, 2)], repone_a=repone_a)
            self.assertEqual(error.exception.message_dict["repone_a"], [servicio.REPOSICION_INVALIDA])


# ---------------------------------------------------------------------------
# RN-4.9: toda transición deja traza
# ---------------------------------------------------------------------------


class TrazaDeLaEntregaTests(BaseKits):
    def test_cada_transicion_deja_su_fila_en_orden(self):
        entrega = self._en_camino()
        recibida = self._recibir(entrega, {self.colchon.pk: 9, self.alimentos.pk: 3})
        servicio.observar_recepcion(recibida, self.operador, "Reclamado")

        filas = list(
            TrazaEntrega.objects.filter(entrega=entrega)
            .order_by("id")
            .values_list("accion", "estado_anterior", "estado_nuevo", "usuario__username")
        )
        self.assertEqual(
            filas,
            [
                ("CREADA", "", "PREPARADA", "ana"),
                ("EN_CAMINO", "PREPARADA", "EN_CAMINO", "ana"),
                ("RECIBIDA", "EN_CAMINO", "RECIBIDA_CON_DIFERENCIAS", "guardia_club"),
                ("OBSERVADA", "RECIBIDA_CON_DIFERENCIAS", "RECIBIDA_CON_DIFERENCIAS", "ana"),
            ],
        )

    def test_una_accion_rechazada_no_deja_traza(self):
        entrega = self._entrega()

        with self.assertRaises(ValidationError):
            servicio.cancelar_entrega(entrega, self.operador, "")
        with self.assertRaises(PermissionDenied):
            servicio.marcar_en_camino(entrega, self.guardia)
        with self.assertRaises(EstadoCambioEntrega):
            servicio.observar_recepcion(entrega, self.operador, "Nota")

        self.assertEqual(self._acciones(entrega), ["CREADA"])

    def test_la_traza_del_selector_va_de_la_mas_nueva_a_la_mas_vieja(self):
        entrega = self._en_camino()

        eventos = selectores.traza_de(entrega)

        self.assertEqual([evento["titulo"] for evento in eventos], ["Marcada en camino", "Entrega armada"])
        self.assertEqual(eventos[0]["cuando"], "12/11/2026 10:00 · Ana López")


# ---------------------------------------------------------------------------
# Media: el remito
# ---------------------------------------------------------------------------


class RemitoPorMediaTests(BaseKits):
    def test_el_remito_lo_bajan_la_mesa_y_el_equipo_del_destino_y_nadie_mas(self):
        """RU-17 y RN-4.8: detrás de login, y para la guardia solo el de **su** dispositivo."""
        ruta = self._recibir(self._en_camino(dispositivo=self.club)).remito.name
        admisor = self._guardia("admisor", [ADMITIR, "dispositivo.ver"], [self.club])
        de_becas = self._usuario("de_becas", ["becas.campo"], programa=self.becas)

        self.assertTrue(_autorizar(self.operador, ruta))
        self.assertTrue(_autorizar(self.supervisor, ruta))
        self.assertTrue(_autorizar(self.guardia, ruta))
        # Sin alcance, el mismo 404 que un archivo inexistente: ni confirma que existe.
        for ajeno in (self.guardia_escuela, admisor, self.agente, de_becas):
            with self.subTest(usuario=ajeno.username):
                self.assertIsNone(_autorizar(ajeno, ruta))
        self.assertIsNone(_autorizar(self.operador, "emergencia/entregas/no-existe/x.jpg"))

    def test_por_http_la_guardia_de_otro_dispositivo_recibe_404(self):
        ruta = self._recibir(self._en_camino(dispositivo=self.club)).remito.name

        self.client.force_login(self.guardia_escuela)
        self.assertEqual(self.client.get(f"/media/{ruta}").status_code, 404)
        self.client.force_login(self.guardia)
        self.assertEqual(self.client.get(f"/media/{ruta}").status_code, 200)
        self.client.logout()
        self.assertEqual(self.client.get(f"/media/{ruta}").status_code, 302)


# ---------------------------------------------------------------------------
# Selectores
# ---------------------------------------------------------------------------


class SelectoresDeKitsTests(BaseKits):
    def test_las_solapas_reparten_las_entregas_y_el_conteo_coincide(self):
        preparada = self._entrega()
        en_camino = self._en_camino()
        completa = self._recibir(self._en_camino())
        con_faltante = self._recibida_con_faltante()
        cancelada = servicio.cancelar_entrega(self._entrega(), self.operador, "Error")

        esperado = {
            selectores.SOLAPA_ABIERTAS: {preparada, en_camino},
            selectores.SOLAPA_CON_DIFERENCIAS: {con_faltante},
            selectores.SOLAPA_RECIBIDAS: {completa},
            selectores.SOLAPA_CANCELADAS: {cancelada},
        }
        conteos = selectores.conteos_de_solapas()
        for solapa, entregas in esperado.items():
            with self.subTest(solapa=solapa):
                self.assertEqual(set(selectores.listado_de_entregas({"solapa": solapa})), entregas)
                self.assertEqual(conteos[solapa], len(entregas))
        self.assertEqual(conteos["total"], 5)
        self.assertEqual([clave for clave, _texto in selectores.SOLAPAS], list(esperado))

    def test_sin_entregas_los_conteos_son_cero(self):
        self.assertEqual(set(selectores.conteos_de_solapas().values()), {0})

    def test_los_filtros_del_listado(self):
        del_club = self._entrega(dispositivo=self.club)
        self.reloj.avanzar(days=1)
        de_la_escuela = self._en_camino(dispositivo=self.escuela)

        listado = selectores.listado_de_entregas
        self.assertEqual(list(listado({"dispositivo": self.club.pk})), [del_club])
        self.assertEqual(list(listado({"localidad": "Barranqueras"})), [de_la_escuela])
        self.assertEqual(list(listado({"estado": Estado.EN_CAMINO})), [de_la_escuela])
        self.assertEqual(list(listado({"fecha": T0.date()})), [del_club])
        self.assertEqual(list(listado({"fecha": (T0 + timedelta(days=1)).date()})), [de_la_escuela])
        self.assertEqual(list(listado({"solapa": "no-existe"})), [de_la_escuela, del_club])

    def test_el_filtro_por_fecha_es_del_dia_local(self):
        """23:30 de Resistencia es el día siguiente en UTC: el rango se arma con la hora local."""
        self.reloj.ahora = timezone.make_aware(datetime(2026, 11, 12, 23, 30))
        entrega = self._entrega()

        self.assertEqual(list(selectores.listado_de_entregas({"fecha": datetime(2026, 11, 12).date()})), [entrega])
        self.assertEqual(list(selectores.listado_de_entregas({"fecha": datetime(2026, 11, 13).date()})), [])

    def test_el_resumen_de_items_corta_despues_de_tres(self):
        cuarto = TipoKit.objects.create(nombre="Frazada", unidad="unidad", orden=4)
        entrega = self._entrega(lineas=[(self.colchon, 10), (self.alimentos, 3), (self.agua, 6), (cuarto, 2)])

        self.assertEqual(
            selectores.resumen_de_items(selectores.lineas_de(entrega)), "10 Colchón, 3 Kit alimentario, 6 Agua 6 l…"
        )

    def test_los_destinos_con_entregas_alimentan_los_filtros(self):
        self._entrega(dispositivo=self.club)
        self._entrega(dispositivo=self.club)
        self._entrega(dispositivo=self.escuela)

        dispositivos, localidades = selectores.destinos_con_entregas()

        self.assertEqual(dispositivos, [(self.club.pk, "Club Sarmiento"), (self.escuela.pk, "Escuela 12")])
        self.assertEqual(localidades, ["Barranqueras", "Resistencia"])

    def test_los_destinos_posibles_son_los_activos_y_se_buscan_por_nombre_o_localidad(self):
        self._dispositivo("Parroquia cerrada", estado=Dispositivo.Estado.CERRADO, localidad="Resistencia")

        self.assertEqual(list(selectores.destinos_posibles()), [self.club, self.escuela])
        self.assertEqual(list(selectores.destinos_posibles("sarmi")), [self.club])
        self.assertEqual(list(selectores.destinos_posibles("barranq")), [self.escuela])
        self.assertEqual(list(selectores.destinos_posibles("resistencia")), [self.club])

    def test_el_resumen_del_destino(self):
        self._ocupar(self.club, 3)
        self._recibida_con_faltante()
        self.reloj.avanzar(hours=1)
        ultima = self._entrega(dispositivo=self.club)

        resumen = selectores.resumen_destino(self.club)
        sin_nada = selectores.resumen_destino(self.escuela)

        self.assertEqual((resumen["alojadas"], resumen["plazas_ocupadas"], resumen["plazas_operativas"]), (3, 3, 4))
        self.assertEqual(
            resumen["ultima_entrega"], {"numero": ultima.numero, "fecha": ultima.creado, "con_diferencias": False}
        )
        self.assertEqual(
            sin_nada, {"alojadas": 0, "plazas_ocupadas": 0, "plazas_operativas": 4, "ultima_entrega": None}
        )

    def test_la_ultima_entrega_dice_si_tuvo_diferencias(self):
        con_faltante = self._recibida_con_faltante()

        ultima = selectores.resumen_destino(self.club)["ultima_entrega"]

        self.assertEqual((ultima["numero"], ultima["con_diferencias"]), (con_faltante.numero, True))

    def test_mis_dispositivos_cuenta_las_pendientes_solo_donde_recibe(self):
        doble = self._sumar_rol(self.guardia, [ADMITIR], self.dispositivos, [self.escuela])
        self._en_camino(dispositivo=self.club)
        self._entrega(dispositivo=self.club)
        self._recibir(self._en_camino(dispositivo=self.club))
        self._en_camino(dispositivo=self.escuela)

        self.assertEqual(
            selectores.mis_dispositivos(doble),
            [
                {"id": self.club.pk, "nombre": "Club Sarmiento", "entregas_pendientes": 2},
                # En la Escuela solo admite: sus entregas no son suyas para recibir.
                {"id": self.escuela.pk, "nombre": "Escuela 12", "entregas_pendientes": 0},
            ],
        )
        self.assertEqual(selectores.mis_dispositivos(self.operador), [])
        self.assertEqual(selectores.mis_dispositivos(self.agente), [])


@tag("performance")
class PresupuestosDeKitsTests(BaseKits):
    """El ``read_timeout`` de ECOM es de 10 s: lo que crece con los datos no puede sumar consultas."""

    def _doscientas(self):
        dispositivos = [self._dispositivo(f"Centro {n:02d}", camas=2, localidad="Resistencia") for n in range(20)]
        operadores = [self.operador, self.otro_operador, self.supervisor]
        for n in range(200):
            entrega = servicio.crear_entrega(
                operadores[n % 3], dispositivos[n % 20], [(self.colchon, 5), (self.alimentos, 2), (self.agua, 1)]
            )
            if n % 2:
                servicio.marcar_en_camino(entrega, self.operador)
        return dispositivos

    def test_la_pagina_del_listado_de_e4_cuesta_dos_consultas_con_200_entregas(self):
        self._doscientas()

        with self.assertNumQueries(2):
            pagina = list(selectores.listado_de_entregas({"solapa": selectores.SOLAPA_ABIERTAS})[:50])
            filas = [
                (
                    entrega.numero,
                    entrega.dispositivo.nombre,
                    selectores.nombre_de(entrega.armada_por),
                    selectores.nombre_de(entrega.recibida_por),
                    selectores.resumen_de_items(list(entrega.lineas.all())),
                )
                for entrega in pagina
            ]
        self.assertEqual(len(filas), 50)
        self.assertEqual(filas[0][4], "5 Colchón, 2 Kit alimentario, 1 Agua 6 l")

    def test_los_conteos_de_las_solapas_cuestan_una_consulta(self):
        self._doscientas()

        with self.assertNumQueries(1):
            conteos = selectores.conteos_de_solapas()
        self.assertEqual((conteos[selectores.SOLAPA_ABIERTAS], conteos["total"]), (200, 200))

    def test_el_resumen_de_los_destinos_cuesta_cinco_consultas_haya_5_o_50(self):
        pocos = [self._dispositivo(f"Poco {n}", camas=2) for n in range(5)]
        muchos = [self._dispositivo(f"Mucho {n:02d}", camas=2) for n in range(50)]
        for dispositivo in (*pocos, *muchos):
            self._ocupar(dispositivo, 1)
            self._entrega(dispositivo=dispositivo)

        for dispositivos in (pocos, muchos):
            with self.subTest(cuantos=len(dispositivos)), self.assertNumQueries(5):
                resumenes = selectores.resumenes_de_destino(dispositivos)
            self.assertEqual({resumen["alojadas"] for resumen in resumenes.values()}, {1})
            self.assertTrue(all(resumen["ultima_entrega"] for resumen in resumenes.values()))

    def test_mis_dispositivos_cuesta_lo_mismo_con_1_o_con_30_dispositivos(self):
        """Las dos del selector más las del alcance (programa, capacidades y Equipo), que no crecen."""
        cache.clear()
        base = self._medir(self.guardia)
        muchos = [self._dispositivo(f"Sede {n:02d}") for n in range(30)]
        para_todos = self._guardia("guardia_de_todos", [RECIBIR_KIT, ADMITIR], muchos)
        for dispositivo in muchos:
            self._en_camino(dispositivo=dispositivo)
            self._entrega(dispositivo=dispositivo)
        cache.clear()

        self.assertEqual(self._medir(para_todos), base)
        self.assertEqual({fila["entregas_pendientes"] for fila in selectores.mis_dispositivos(para_todos)}, {2})

    def _medir(self, usuario):
        fresco = User.objects.get(pk=usuario.pk)
        with CaptureQueriesContext(connection) as consultas:
            selectores.mis_dispositivos(fresco)
        return len(consultas)

    def test_las_pendientes_de_un_dispositivo_cuestan_dos_consultas_mas_el_alcance(self):
        for _ in range(15):
            self._en_camino(dispositivo=self.club)
        fresco = User.objects.get(pk=self.guardia.pk)
        selectores.entregas_pendientes_de(self.club, fresco)  # memoiza capacidades y programa

        with self.assertNumQueries(3):
            pendientes = list(selectores.entregas_pendientes_de(self.club, fresco))
            for entrega in pendientes:
                [linea.item.nombre for linea in entrega.lineas.all()]
        self.assertEqual(len(pendientes), 15)


# ---------------------------------------------------------------------------
# Carreras contra el motor real
# ---------------------------------------------------------------------------

#: El candado de toda transición de una entrega.
ENTREGA_BLOQUEADA = punto_critico(EntregaKit, "_bloquear_entrega")
#: El candado del contador de la serie (es el mismo que el de los casos).
NUMERADOR_BLOQUEADO = punto_critico(NumeradorEmergencia, "_bloquear_numerador")


class _BaseCarreraKits(MotorRealMixin, TransactionTestCase):
    """La mesa mínima con dos operadores, un dispositivo con su guardia y dos ítems.

    ``TransactionTestCase`` y no ``TestCase``: lo que se prueba son transacciones que
    commitean. Sin motor real se saltea (``MotorRealMixin``), igual que
    ``test_emergencia_concurrencia``.
    """

    def setUp(self):
        super().setUp()
        reloj = mock.patch("django.utils.timezone.now", return_value=T0)
        reloj.start()
        self.addCleanup(reloj.stop)
        cache.clear()
        self.addCleanup(cache.clear)
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)
        ajuste = override_settings(MEDIA_ROOT=self.media)
        ajuste.enable()
        self.addCleanup(ajuste.disable)

        self.programa, _creado, _sla = asegurar_programa_emergencia()
        self.dispositivos = _programa("DISPOSITIVOS", "Dispositivos")
        self.ana = self._usuario("ana_kits", ["emergencia.operar"], self.programa)
        self.juan = self._usuario("juan_kits", ["emergencia.operar"], self.programa)
        tipo = TipoDispositivo.objects.create(codigo="EVACUADOS-K", nombre="Centro de evacuados")
        self.club = Dispositivo.objects.create(
            tipo=tipo, codigo="EVA-K1", nombre="Club kits", estado=Dispositivo.Estado.ACTIVO
        )
        self.guardia = self._usuario("guardia_kits", [RECIBIR_KIT], self.dispositivos, equipo=self.club)
        self.otra_guardia = self._usuario("guardia_kits_2", [RECIBIR_KIT], self.dispositivos, equipo=self.club)
        self.colchon = TipoKit.objects.create(nombre="Colchón carrera", unidad="unidad")
        # La primera entrega deja además creada y commiteada la fila del numerador del año.
        self.entrega = servicio.marcar_en_camino(self._crear()(), self._fresco(self.ana))

    def _usuario(self, nombre, capacidades, programa, equipo=None):
        rol = Group.objects.create(name=f"Rol {nombre}")
        RolMeta.objects.create(grupo=rol, categoria=rbac.CATEGORIA_PROGRAMA, programa=programa, activo=True)
        rol.permissions.add(*[_permiso(codigo) for codigo in capacidades])
        usuario = User.objects.create_user(username=nombre)
        usuario.groups.add(rol)
        if equipo is not None:
            MiembroEquipoDispositivo.objects.create(dispositivo=equipo, usuario=usuario, rol=rol)
        return User.objects.get(pk=usuario.pk)

    def _fresco(self, usuario):
        """``rbac`` memoiza las capacidades en el objeto, y cada hilo necesita el suyo."""
        return User.objects.get(pk=usuario.pk)

    def _en_pantalla(self):
        return EntregaKit.objects.get(pk=self.entrega.pk)

    def _crear(self):
        def operacion():
            return servicio.crear_entrega(self._fresco(self.ana), self.club.pk, [(self.colchon.pk, 4)])

        return operacion

    def _recibir(self, usuario, cantidad=4, uuid_cliente=None):
        def operacion():
            return servicio.recibir_entrega(
                self._en_pantalla(),
                self._fresco(usuario),
                {self.colchon.pk: cantidad},
                SimpleUploadedFile("remito.jpg", JPEG, content_type="image/jpeg"),
                uuid_cliente=uuid_cliente,
            )

        return operacion

    def _cancelar(self):
        def operacion():
            return servicio.cancelar_entrega(self._en_pantalla(), self._fresco(self.juan), "Se suspendió")

        return operacion

    def _un_error(self, errores, tipo):
        self.assertEqual(len(errores), 1, f"se esperaba un solo perdedor: {[repr(e) for e in errores]}")
        self.assertIsInstance(errores[0], tipo, f"el perdedor no recibió el error de dominio: {errores[0]!r}")
        return errores[0]


@tag("mysql")
class CarreraDelNumeradorDeKitsTests(_BaseCarreraKits):
    def test_dos_entregas_a_la_vez_reciben_numeros_consecutivos(self):
        resultados, errores = en_paralelo(self._crear(), self._crear(), punto_a=NUMERADOR_BLOQUEADO)

        self.assertEqual(errores, [])
        self.assertEqual(sorted(entrega.numero for entrega in resultados), ["2026-K-000002", "2026-K-000003"])
        self.assertEqual(EntregaKit.objects.count(), 3)
        self.assertEqual(NumeradorEmergencia.objects.get(serie="K", anio=2026).ultimo, 3)


@tag("mysql")
class CarreraDeLaRecepcionTests(_BaseCarreraKits):
    def test_cancelar_contra_recibir_gana_uno_y_el_otro_recibe_el_error_de_dominio(self):
        resultados, errores = en_paralelo(self._cancelar(), self._recibir(self.guardia), punto_a=ENTREGA_BLOQUEADA)

        self.assertEqual(len(resultados), 1)
        error = self._un_error(errores, EstadoCambioEntrega)
        entrega = self._en_pantalla()
        self.assertEqual(error.estado_actual, entrega.estado)
        self.assertEqual(entrega.estado, Estado.CANCELADA)
        self.assertFalse(entrega.remito)
        self.assertIsNone(entrega.lineas.get().cantidad_recibida)
        self.assertEqual(TrazaEntrega.objects.filter(entrega=entrega).exclude(accion="CREADA").count(), 2)

    def test_recibir_contra_cancelar_deja_la_entrega_recibida(self):
        resultados, errores = en_paralelo(self._recibir(self.guardia), self._cancelar(), punto_a=ENTREGA_BLOQUEADA)

        self.assertEqual(len(resultados), 1)
        error = self._un_error(errores, EstadoCambioEntrega)
        entrega = self._en_pantalla()
        self.assertEqual((entrega.estado, error.estado_actual), (Estado.RECIBIDA, Estado.RECIBIDA))
        self.assertEqual(entrega.motivo_cancelacion, "")

    def test_dos_guardias_reciben_a_la_vez_y_la_recepcion_es_una(self):
        resultados, errores = en_paralelo(
            self._recibir(self.guardia, 4), self._recibir(self.otra_guardia, 3), punto_a=ENTREGA_BLOQUEADA
        )

        self.assertEqual(len(resultados), 1)
        self._un_error(errores, EstadoCambioEntrega)
        entrega = self._en_pantalla()
        self.assertEqual(entrega.recibida_por_id, resultados[0].recibida_por_id)
        self.assertEqual(entrega.lineas.get().cantidad_recibida, 4 if entrega.estado == Estado.RECIBIDA else 3)
        self.assertEqual(TrazaEntrega.objects.filter(entrega=entrega, accion="RECIBIDA").count(), 1)

    def test_el_mismo_envio_dos_veces_a_la_vez_recibe_una_sola_vez(self):
        """RU-16 con las dos copias en vuelo: la segunda espera el candado y lee el identificador ya escrito."""
        envio = uuid.uuid4()

        resultados, errores = en_paralelo(
            self._recibir(self.guardia, 3, envio), self._recibir(self.guardia, 3, envio), punto_a=ENTREGA_BLOQUEADA
        )

        self.assertEqual(errores, [])
        self.assertEqual(sorted(entrega.ya_existia for entrega in resultados), [False, True])
        self.assertEqual(self._en_pantalla().estado, Estado.RECIBIDA_CON_DIFERENCIAS)
        self.assertEqual(TrazaEntrega.objects.filter(entrega=self.entrega, accion="RECIBIDA").count(), 1)
