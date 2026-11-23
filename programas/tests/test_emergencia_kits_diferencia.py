"""Entregas de kits de Emergencia: cerrar la diferencia, edificio inactivo y entregas demoradas (Cambio 586).

Salió de ``test_emergencia_kits`` (que pasaba de 1700 líneas): la base ``BaseKits`` es la de allá. Cada regla de
servicio tiene su test y su mutación (ver ``docs/internal/requerimientos/586.md``):

* **Reponer una sola vez** y **aceptar con motivo**, serializadas sobre la original con ``select_for_update``.
* **Cancelar la única reposición** reabre la diferencia.
* **Edificio inactivo** no recibe entregas nuevas.
* **Demorada** (más de ``EntregaKit.HORAS_PARA_DEMORADA`` horas en camino) en un solo lugar: ``selectors.kits``.
"""

import uuid
from contextlib import contextmanager
from datetime import timedelta
from unittest import mock

from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models.query import QuerySet

from programas.models import EntregaKit, LineaEntrega, TrazaEntrega
from programas.selectors import kits as selectores
from programas.services import kits as servicio
from programas.services.kits import EstadoCambioEntrega
from programas.tests.test_emergencia_casos import T0
from programas.tests.test_emergencia_kits import BaseKits

Estado = EntregaKit.Estado
Accion = TrazaEntrega.Accion

# ---------------------------------------------------------------------------
# Cerrar la diferencia (Cambio 586): reponer una sola vez o aceptar con motivo
# ---------------------------------------------------------------------------


class CerrarLaDiferenciaTests(BaseKits):
    """Las dos salidas de «Qué hacer ahora». Cada regla tiene su test y su mutación (ver el requerimiento 586).

    * **Reponer una sola vez** — mutación: quitar el ``if original.cierre_diferencia is not None`` de
      ``_validar_reposicion`` deja en rojo ``test_reponer_se_hace_una_sola_vez`` y
      ``test_una_segunda_reposicion_con_la_entrega_vieja_tambien_se_rechaza``.
    * **Aceptar con motivo** — mutación: quitar el ``if not motivo`` de ``aceptar_diferencia`` deja en rojo
      ``test_aceptar_exige_un_motivo``; quitar el chequeo de ``cierre_diferencia is not None`` deja en rojo
      ``test_aceptar_dos_veces_o_despues_de_reponer_se_rechaza``.
    """

    def _reponer(self, original):
        return self._entrega(lineas=selectores.faltantes_de(selectores.lineas_de(original)), repone_a=original)

    def test_reponer_cierra_la_diferencia_como_repuesta_con_su_traza(self):
        original = self._recibida_con_faltante()
        self.assertIsNone(original.cierre_diferencia)
        self.assertTrue(original.diferencia_sin_cerrar)

        reposicion = self._reponer(original)

        cerrada = EntregaKit.objects.get(pk=original.pk)
        self.assertEqual(
            (cerrada.cierre_diferencia, cerrada.cierre_diferencia_por),
            (EntregaKit.CierreDiferencia.REPUESTA, self.operador),
        )
        self.assertIsNotNone(cerrada.cierre_diferencia_en)
        self.assertFalse(cerrada.diferencia_sin_cerrar)
        self.assertEqual(
            self._acciones(original), ["CREADA", "EN_CAMINO", "RECIBIDA", Accion.DIFERENCIA_REPUESTA.value]
        )
        self.assertIn(reposicion.numero, TrazaEntrega.objects.filter(entrega=original).last().detalle)

    def test_reponer_se_hace_una_sola_vez(self):
        original = self._recibida_con_faltante()
        self._reponer(original)
        antes = EntregaKit.objects.count()

        with self.assertRaises(ValidationError) as error:
            self._entrega(lineas=[(self.colchon, 2)], repone_a=original)

        self.assertIn("Reponer se hace una sola vez", error.exception.message_dict["repone_a"][0])
        self.assertEqual(EntregaKit.objects.count(), antes)

    def test_una_segunda_reposicion_con_la_entrega_vieja_tambien_se_rechaza(self):
        """Dos pestañas con la misma pantalla: la segunda pasa un objeto viejo, sin cierre, y el servicio lo relee."""
        vieja = self._recibida_con_faltante()
        self._reponer(vieja)
        self.assertIsNone(vieja.cierre_diferencia)  # el objeto que tiene la segunda pestaña no sabe del cierre

        with self.assertRaises(ValidationError):
            self._entrega(lineas=[(self.colchon, 2)], repone_a=vieja)
        self.assertEqual(EntregaKit.objects.filter(repone_a=vieja).count(), 1)

    def test_el_doble_envio_de_una_reposicion_devuelve_la_entrega_del_primero_y_no_un_error(self):
        """Dos envíos a la vez con el mismo ``uuid_cliente``: el segundo pasa la lectura de arriba antes de que el primero
        escriba, espera el candado de la original y la ve cerrada. Antes de rechazar vuelve a buscar su armado bajo el
        candado y devuelve la entrega del primero. Mutación: quitar el ``except _ReposicionYaHecha`` de
        ``crear_entrega`` deja este test en rojo (``ValidationError``)."""
        original = self._recibida_con_faltante()
        lineas = selectores.faltantes_de(selectores.lineas_de(original))
        armado = uuid.uuid4()
        primera = self._entrega(lineas=lineas, repone_a=original, uuid_cliente=armado)
        real = servicio._entrega_de_ese_armado
        lecturas = []

        def sin_verla_la_primera_vez(uuid_cliente, usuario):
            lecturas.append(uuid_cliente)
            return None if len(lecturas) == 1 else real(uuid_cliente, usuario)

        with mock.patch.object(servicio, "_entrega_de_ese_armado", side_effect=sin_verla_la_primera_vez):
            segunda = self._entrega(lineas=lineas, repone_a=original, uuid_cliente=armado)

        self.assertEqual((segunda.pk, segunda.ya_existia), (primera.pk, True))
        self.assertEqual(EntregaKit.objects.filter(repone_a=original).count(), 1)

    def test_otro_armado_sobre_una_diferencia_ya_repuesta_sigue_rechazandose(self):
        original = self._recibida_con_faltante()
        self._entrega(lineas=[(self.colchon, 2)], repone_a=original, uuid_cliente=uuid.uuid4())

        with self.assertRaises(ValidationError):
            self._entrega(lineas=[(self.colchon, 2)], repone_a=original, uuid_cliente=uuid.uuid4())

    def test_no_se_repone_una_diferencia_aceptada(self):
        original = self._recibida_con_faltante()
        servicio.aceptar_diferencia(original, self.operador, "Lo cubre otro envío")

        with self.assertRaises(ValidationError) as error:
            self._entrega(lineas=[(self.colchon, 2)], repone_a=original)

        self.assertIn("aceptada", error.exception.message_dict["repone_a"][0])

    def test_cancelar_la_unica_reposicion_viva_reabre_la_diferencia_con_traza(self):
        """Mutación: quitar la llamada a ``_reabrir_si_no_queda_reposicion`` deja este test en rojo."""
        original = self._recibida_con_faltante()
        reposicion = self._reponer(original)
        self.assertFalse(EntregaKit.objects.get(pk=original.pk).diferencia_sin_cerrar)

        servicio.cancelar_entrega(reposicion, self.operador, "El camión no salió")

        reabierta = EntregaKit.objects.get(pk=original.pk)
        self.assertTrue(reabierta.diferencia_sin_cerrar)
        self.assertEqual(
            (reabierta.cierre_diferencia, reabierta.cierre_diferencia_en, reabierta.cierre_diferencia_por),
            (None, None, None),
        )
        ultima = TrazaEntrega.objects.filter(entrega=original).last()
        self.assertEqual(ultima.accion, Accion.DIFERENCIA_REABIERTA)
        self.assertIn(reposicion.numero, ultima.detalle)
        # Y otra vez se puede reponer, o aceptar.
        otra = self._reponer(original)
        self.assertEqual(otra.repone_a_id, original.pk)
        servicio.cancelar_entrega(otra, self.operador, "Otra vez")
        servicio.aceptar_diferencia(original, self.operador, "Se cubrió por otro lado")

    def test_cancelar_una_reposicion_con_otra_viva_no_reabre(self):
        original = self._recibida_con_faltante()
        cancelada = self._reponer(original)
        EntregaKit.objects.create(
            numero="2026-K-990002",
            dispositivo=self.club,
            estado=Estado.EN_CAMINO,
            armada_por=self.operador,
            repone_a=original,
        )

        servicio.cancelar_entrega(cancelada, self.operador, "Duplicada")

        self.assertEqual(EntregaKit.objects.get(pk=original.pk).cierre_diferencia, EntregaKit.CierreDiferencia.REPUESTA)
        self.assertNotIn(Accion.DIFERENCIA_REABIERTA, self._acciones(original))

    def test_cancelar_una_entrega_comun_no_toca_ninguna_diferencia(self):
        original = self._recibida_con_faltante()
        aceptada = self._recibida_con_faltante()
        servicio.aceptar_diferencia(aceptada, self.operador, "Motivo")

        servicio.cancelar_entrega(self._entrega(), self.operador, "Error de carga")

        self.assertTrue(EntregaKit.objects.get(pk=original.pk).diferencia_sin_cerrar)
        self.assertEqual(EntregaKit.objects.get(pk=aceptada.pk).cierre_diferencia, EntregaKit.CierreDiferencia.ACEPTADA)

    def test_aceptar_cierra_con_motivo_sin_tocar_las_cantidades_y_deja_traza(self):
        original = self._recibida_con_faltante()
        lineas = list(LineaEntrega.objects.filter(entrega=original).order_by("id").values())

        servicio.aceptar_diferencia(original, self.operador, "  Lo cubre otro envío  ")

        cerrada = EntregaKit.objects.get(pk=original.pk)
        self.assertEqual(
            (cerrada.cierre_diferencia, cerrada.cierre_diferencia_motivo, cerrada.cierre_diferencia_por),
            (EntregaKit.CierreDiferencia.ACEPTADA, "Lo cubre otro envío", self.operador),
        )
        self.assertEqual(cerrada.cierre_diferencia_en, T0)
        self.assertEqual(cerrada.estado, Estado.RECIBIDA_CON_DIFERENCIAS)
        self.assertEqual(list(LineaEntrega.objects.filter(entrega=original).order_by("id").values()), lineas)
        ultima = TrazaEntrega.objects.filter(entrega=original).last()
        self.assertEqual((ultima.accion, ultima.detalle), (Accion.DIFERENCIA_ACEPTADA, "Lo cubre otro envío"))

    def test_aceptar_exige_un_motivo(self):
        original = self._recibida_con_faltante()
        antes = self._foto_de(original)

        for motivo in ("", "   ", None):
            with self.subTest(motivo=motivo), self.assertRaises(ValidationError) as error:
                servicio.aceptar_diferencia(original, self.operador, motivo)
            self.assertEqual(error.exception.message_dict["motivo"], [servicio.FALTA_EL_MOTIVO_DE_LA_DIFERENCIA])
        with self.assertRaises(ValidationError) as error:
            servicio.aceptar_diferencia(original, self.operador, "x" * 201)
        self.assertIn("200", error.exception.message_dict["motivo"][0])
        self.assertEqual(self._foto_de(original), antes)

    def test_aceptar_dos_veces_o_despues_de_reponer_se_rechaza(self):
        aceptada = self._recibida_con_faltante()
        servicio.aceptar_diferencia(aceptada, self.operador, "Primero")
        with self.assertRaises(EstadoCambioEntrega):
            servicio.aceptar_diferencia(aceptada, self.operador, "Segundo")
        self.assertEqual(EntregaKit.objects.get(pk=aceptada.pk).cierre_diferencia_motivo, "Primero")

        repuesta = self._recibida_con_faltante()
        self._reponer(repuesta)
        with self.assertRaises(EstadoCambioEntrega):
            servicio.aceptar_diferencia(repuesta, self.operador, "Tarde")
        self.assertEqual(EntregaKit.objects.get(pk=repuesta.pk).cierre_diferencia, EntregaKit.CierreDiferencia.REPUESTA)

    def test_aceptar_con_el_objeto_viejo_relee_el_cierre(self):
        original = self._recibida_con_faltante()
        otra_pestana = EntregaKit.objects.get(pk=original.pk)
        servicio.aceptar_diferencia(original, self.operador, "Primero")

        with self.assertRaises(EstadoCambioEntrega):
            servicio.aceptar_diferencia(otra_pestana, self.operador, "Segundo")

    def test_solo_se_acepta_una_recibida_con_diferencias(self):
        for nombre, entrega in {
            "preparada": self._entrega(),
            "en camino": self._en_camino(),
            "completa": self._recibir(self._en_camino()),
        }.items():
            with self.subTest(estado=nombre), self.assertRaises(EstadoCambioEntrega):
                servicio.aceptar_diferencia(entrega, self.operador, "Motivo")
            self.assertIsNone(EntregaKit.objects.get(pk=entrega.pk).cierre_diferencia)

    def test_la_guardia_no_cierra_diferencias(self):
        original = self._recibida_con_faltante()

        with self.assertRaises(PermissionDenied):
            servicio.aceptar_diferencia(original, self.guardia, "Motivo")

        self.assertIsNone(EntregaKit.objects.get(pk=original.pk).cierre_diferencia)

    def test_una_diferencia_cerrada_sale_de_la_solapa_y_del_aviso_de_sin_revisar(self):
        sin_cerrar = self._recibida_con_faltante()
        aceptada = self._recibida_con_faltante()
        servicio.aceptar_diferencia(aceptada, self.operador, "Motivo")

        conteos = selectores.conteos_de_solapas(T0)
        con_diferencias = selectores.listado_de_entregas({"solapa": selectores.SOLAPA_CON_DIFERENCIAS}, T0)
        recibidas = selectores.listado_de_entregas({"solapa": selectores.SOLAPA_RECIBIDAS}, T0)

        self.assertEqual(list(con_diferencias), [sin_cerrar])
        self.assertEqual(list(recibidas), [aceptada])
        self.assertEqual((conteos["con_diferencias"], conteos["recibidas"]), (1, 1))
        self.assertEqual(list(EntregaKit.objects.filter(selectores.q_entrega_sin_revisar())), [sin_cerrar])


class MigracionDeLasYaRepuestasTests(BaseKits):
    """``0143``: las entregas que ya tenían una reposición quedan ``REPUESTA`` y no ofrecen reponer otra vez."""

    def _correr(self):
        import importlib

        from django.apps import apps

        modulo = importlib.import_module("programas.migrations.0143_entrega_cierre_diferencia_datos")
        modulo.cerrar_las_ya_repuestas(apps, None)

    def test_marca_repuesta_con_la_primera_reposicion_y_es_idempotente(self):
        con_reposicion = self._recibida_con_faltante()
        primera = self._entrega(
            lineas=selectores.faltantes_de(selectores.lineas_de(con_reposicion)), repone_a=con_reposicion
        )
        EntregaKit.objects.create(
            numero="2026-K-990001",
            dispositivo=self.club,
            estado=Estado.PREPARADA,
            armada_por=self.supervisor,
            repone_a=con_reposicion,
        )
        sin_reposicion = self._recibida_con_faltante()
        solo_cancelada = self._recibida_con_faltante()
        cancelada = self._entrega(
            lineas=selectores.faltantes_de(selectores.lineas_de(solo_cancelada)), repone_a=solo_cancelada
        )
        EntregaKit.objects.filter(pk=cancelada.pk).update(estado=Estado.CANCELADA)
        EntregaKit.objects.filter(pk=solo_cancelada.pk).update(
            cierre_diferencia=None, cierre_diferencia_en=None, cierre_diferencia_por=None
        )
        EntregaKit.objects.filter(pk=con_reposicion.pk).update(
            cierre_diferencia=None, cierre_diferencia_en=None, cierre_diferencia_por=None
        )

        self._correr()
        self._correr()

        cerrada = EntregaKit.objects.get(pk=con_reposicion.pk)
        self.assertEqual(cerrada.cierre_diferencia, EntregaKit.CierreDiferencia.REPUESTA)
        self.assertEqual(cerrada.cierre_diferencia_por, primera.armada_por)
        self.assertEqual(cerrada.cierre_diferencia_en, primera.creado)
        self.assertIsNone(EntregaKit.objects.get(pk=sin_reposicion.pk).cierre_diferencia)
        self.assertIsNone(EntregaKit.objects.get(pk=solo_cancelada.pk).cierre_diferencia)


class EdificioInactivoNoRecibeEntregasTests(BaseKits):
    """Un edificio inactivo no recibe entregas nuevas (Cambio 586, decisión del juez).

    Mutación: quitar el filtro ``activo=True`` de ``edificios_a_elegir`` o el chequeo de
    ``_exigir_edificio_activo`` deja en rojo el test de cada camino que ese filtro cubre.
    """

    def _edificio(self, codigo, activo=True):
        from programas.models import Edificio

        edificio = Edificio.objects.create(codigo=codigo, nombre=f"Edificio {codigo}", activo=activo)
        edificio.dispositivos.add(self.club)
        return edificio

    def test_el_edificio_pedido_inactivo_se_rechaza_y_no_se_crea_nada(self):
        activo, inactivo = self._edificio("A"), self._edificio("B", activo=False)

        with self.assertRaises(ValidationError) as error:
            self._entrega(edificio=inactivo)

        self.assertIn("está inactivo", error.exception.message_dict["edificio"][0])
        self.assertFalse(EntregaKit.objects.exists())
        self.assertEqual(self._entrega(edificio=activo).edificio_id, activo.pk)

    def test_el_unico_edificio_inactivo_no_deja_crear_la_entrega_sin_edificio(self):
        self._edificio("A", activo=False)

        with self.assertRaises(ValidationError) as error:
            self._entrega()

        self.assertIn("Reactivalo", error.exception.message_dict["edificio"][0])
        self.assertFalse(EntregaKit.objects.exists())

    def test_con_uno_activo_y_otro_inactivo_queda_fijo_el_activo(self):
        activo = self._edificio("A")
        self._edificio("B", activo=False)

        self.assertEqual(self._entrega().edificio_id, activo.pk)

    def test_la_reposicion_que_hereda_un_edificio_inactivo_se_rechaza_y_no_cierra_la_original(self):
        edificio = self._edificio("A")
        original = self._recibida_con_faltante()
        EntregaKit.objects.filter(pk=original.pk).update(edificio=edificio)
        original = EntregaKit.objects.get(pk=original.pk)
        edificio.activo = False
        edificio.save(update_fields=["activo"])
        antes = EntregaKit.objects.count()

        with self.assertRaises(ValidationError) as error:
            self._entrega(lineas=[(self.colchon, 2)], repone_a=original)

        self.assertIn("está inactivo", error.exception.message_dict["edificio"][0])
        self.assertEqual(EntregaKit.objects.count(), antes)
        self.assertIsNone(EntregaKit.objects.get(pk=original.pk).cierre_diferencia)

    def test_el_selector_no_ofrece_los_inactivos(self):
        self._edificio("A")
        self._edificio("B", activo=False)
        self.assertEqual(selectores.edificios_a_elegir(self.club), [])  # uno activo: queda fijo

        self._edificio("C")
        self.assertEqual([e.codigo for e in selectores.edificios_a_elegir(self.club)], ["A", "C"])

    def test_sin_edificios_la_entrega_sigue_saliendo_sin_edificio(self):
        self.assertIsNone(self._entrega().edificio_id)


class OrdenDeCandadosTests(BaseKits):
    """``crear_entrega`` bloquea el dispositivo destino, después la entrega original y después el edificio.

    «Inactivar» y «desvincular» edificio van Dispositivo → Edificio, y el ``INSERT`` pide un candado compartido sobre el
    dispositivo: tomar el edificio primero cerraba un ciclo (1213 para una de las dos). En SQLite ``select_for_update``
    no hace nada, así que lo que se fija es **el orden en que se piden**. Mutación: pedir el edificio antes que el
    dispositivo deja este test en rojo.
    """

    @contextmanager
    def _orden_de_los_candados(self):
        pedidos = []
        real = QuerySet.select_for_update

        def registrar(consulta, *args, **kwargs):
            pedidos.append(consulta.model.__name__)
            return real(consulta, *args, **kwargs)

        with mock.patch.object(QuerySet, "select_for_update", registrar):
            yield pedidos

    def _edificio(self):
        from programas.models import Edificio

        edificio = Edificio.objects.create(codigo="OC", nombre="Edificio OC")
        edificio.dispositivos.add(self.club)
        return edificio

    def test_dispositivo_antes_que_edificio_y_el_numerador_al_final(self):
        edificio = self._edificio()

        with self._orden_de_los_candados() as pedidos:
            self._entrega(edificio=edificio)

        self.assertLess(pedidos.index("Dispositivo"), pedidos.index("Edificio"))
        self.assertLess(pedidos.index("Edificio"), pedidos.index("NumeradorEmergencia"))

    def test_con_una_reposicion_el_orden_es_dispositivo_original_edificio(self):
        edificio = self._edificio()
        original = self._recibida_con_faltante()
        EntregaKit.objects.filter(pk=original.pk).update(edificio=edificio)

        with self._orden_de_los_candados() as pedidos:
            self._entrega(lineas=[(self.colchon, 2)], repone_a=original)

        self.assertLess(pedidos.index("Dispositivo"), pedidos.index("EntregaKit"))
        self.assertLess(pedidos.index("EntregaKit"), pedidos.index("Edificio"))
        self.assertLess(pedidos.index("Edificio"), pedidos.index("NumeradorEmergencia"))


class EntregasDemoradasTests(BaseKits):
    """Más de 48 h en camino sin recibirse: se separa de lo «en camino» y no se cancela sola (Cambio 586)."""

    def _despachada_hace(self, horas, **kwargs):
        entrega = self._en_camino(**kwargs)
        EntregaKit.objects.filter(pk=entrega.pk).update(despachada_en=T0 - timedelta(hours=horas))
        return EntregaKit.objects.get(pk=entrega.pk)

    def test_la_regla_en_python_y_la_de_la_consulta_dicen_lo_mismo_incluido_el_borde(self):
        """``es_demorada`` (la fila del listado) y ``q_demorada`` (la solapa y el conteo) son una sola regla: si una
        cambia sin la otra, el chip de la fila deja de coincidir con la solapa. Mutación: cambiar el ``<`` de una de las
        dos por ``<=`` deja en rojo el borde de las 48 h."""
        entregas = [
            self._despachada_hace(47),
            self._despachada_hace(EntregaKit.HORAS_PARA_DEMORADA),
            self._despachada_hace(EntregaKit.HORAS_PARA_DEMORADA + 1),
            self._entrega(),
            self._recibir(self._despachada_hace(90)),
        ]

        en_consulta = set(EntregaKit.objects.filter(selectores.q_demorada(T0)).values_list("pk", flat=True))
        en_python = {entrega.pk for entrega in EntregaKit.objects.all() if selectores.es_demorada(entrega, T0)}

        self.assertEqual(en_python, en_consulta)
        self.assertEqual(en_consulta, {entregas[2].pk})

    def test_q_demorada_con_prefijo_sirve_desde_las_lineas(self):
        vieja = self._despachada_hace(60)
        self._despachada_hace(5)

        lineas = LineaEntrega.objects.filter(selectores.q_demorada(T0, "entrega__"))

        self.assertEqual({linea.entrega_id for linea in lineas}, {vieja.pk})

    def test_demorada_es_en_camino_y_pasada_de_48_horas(self):
        justa = self._despachada_hace(48)
        vieja = self._despachada_hace(49)
        reciente = self._despachada_hace(47)
        preparada = self._entrega()
        recibida = self._recibir(self._despachada_hace(60))

        demoradas = list(EntregaKit.objects.filter(selectores.q_demorada(T0)))

        self.assertEqual(demoradas, [vieja])
        self.assertNotIn(justa, demoradas)
        self.assertNotIn(reciente, demoradas)
        self.assertNotIn(preparada, demoradas)
        self.assertNotIn(recibida, demoradas)

    def test_la_solapa_y_el_conteo_las_separan_y_siguen_siendo_abiertas(self):
        vieja = self._despachada_hace(60)
        self._despachada_hace(5)

        conteos = selectores.conteos_de_solapas(T0)
        demoradas = selectores.listado_de_entregas({"solapa": selectores.SOLAPA_DEMORADAS}, T0)

        self.assertEqual((conteos["demoradas"], conteos["abiertas"]), (1, 2))
        self.assertEqual(list(demoradas), [vieja])
