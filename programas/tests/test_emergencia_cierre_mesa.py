"""Cerrar desde la mesa y reabrir (Cambio 588, decisiones 6 y 7 del replanteo de Emergencia).

``emergencia.cerrar_reabrir`` es de la supervisión; cerrar una familia alojada egresa sus estadías y reabrir vuelve al
estado anterior al cierre, salvo que la familia ya tenga otro caso abierto (Cambio 579).
"""

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import SimpleTestCase
from django.urls import reverse

from core import rbac
from core.tests.candados import orden_de_candados
from programas.models import CasoEmergencia, Estadia, IntegranteGrupo, MotivoEgreso, TrazaCaso
from programas.services import emergencia as mesa
from programas.services import emergencia_alojar as alojar
from programas.services.emergencia import CasoTomadoPorOtro, EstadoCambio
from programas.services.emergencia_cierre_mesa import (
    ReaperturaConOtroCasoAbierto,
    cerrar_alojado_por_la_mesa,
    puede_cerrar_alojado_por_la_mesa,
    puede_reabrir_el_caso,
    reabrir_caso,
)
from programas.tests.test_emergencia_alojar_base import GUARDIA, BaseAlojar
from programas.tests.test_emergencia_base import OPERAR, SUPERVISAR

Estado = CasoEmergencia.Estado
Accion = TrazaCaso.Accion
CAP = "emergencia.cerrar_reabrir"


class _Base(BaseAlojar):
    def setUp(self):
        super().setUp()
        self.jefe = self._usuario("jefe_mesa", [OPERAR, SUPERVISAR, CAP])
        MotivoEgreso.objects.get_or_create(codigo="otro", defaults={"nombre": "Otro", "orden": 9})

    def _alojada(self, personas=2, **kwargs):
        caso, derivacion = self._aceptado(menores_f=0, menores_m=0, adultos_f=1, adultos_m=personas - 1, **kwargs)
        for orden, reserva in enumerate(self._reservas(derivacion), start=1):
            self._confirmar(caso, orden, str(45_000_100 + orden), plaza=reserva.plaza)
        return alojar.alojar_familia(caso=caso, usuario=self.guardia)

    def _trazas_de(self, caso, accion):
        return TrazaCaso.objects.filter(caso=caso, accion=accion)


class CapacidadTests(SimpleTestCase):
    def test_esta_en_el_catalogo_y_es_de_programa(self):
        self.assertIn(CAP, rbac.codigos_de_capacidad())


class PermisoTests(_Base):
    def _intentos(self, usuario):
        caso = self._alojada()
        with self.assertRaises(PermissionDenied):
            cerrar_alojado_por_la_mesa(caso, usuario, "Se fueron")
        self.assertEqual(self._estado(caso), Estado.ALOJADO)
        cerrada = mesa.cerrar_sin_alojamiento(self._caso_tomado(dni="30222333"), self.operador, "NO_REQUIERE")
        with self.assertRaises(PermissionDenied):
            reabrir_caso(cerrada, usuario)
        self.assertEqual(self._estado(cerrada), Estado.CERRADO)

    def test_quien_solo_supervisa_no_puede(self):
        self._intentos(self.supervisor)

    def test_quien_solo_opera_no_puede(self):
        self._intentos(self.operador)

    def test_la_guardia_sin_la_capacidad_no_puede(self):
        self._intentos(self.guardia)

    def test_la_guardia_no_puede_aunque_tenga_la_capacidad_en_dispositivos(self):
        guardia = self._usuario("g_con_cap", [*GUARDIA, CAP], programa=self.dispositivos)
        self._intentos(guardia)

    def test_la_capacidad_en_otro_programa_no_alcanza(self):
        self._intentos(self._usuario("de_becas", [CAP], programa=self.becas))

    def test_quien_la_tiene_en_emergencia_si_puede(self):
        caso = self._alojada()
        cerrar_alojado_por_la_mesa(caso, self.jefe, "Se fueron")
        self.assertEqual(self._estado(caso), Estado.CERRADO)


class CerrarAlojadoTests(_Base):
    def test_el_motivo_es_obligatorio(self):
        caso = self._alojada()
        for motivo in ("", "   ", None, "x" * 201):
            with self.assertRaises(ValidationError):
                cerrar_alojado_por_la_mesa(caso, self.jefe, motivo)
        self.assertEqual(self._estado(caso), Estado.ALOJADO)
        self.assertFalse(self._trazas_de(caso, Accion.CERRADO_POR_LA_MESA).exists())
        self.assertEqual(Estadia.objects.filter(estado=Estadia.Estado.ACTIVA).count(), 2)

    def test_cierra_la_familia_alojada_y_egresa_las_estadias(self):
        caso = self._alojada(3)

        cerrado = cerrar_alojado_por_la_mesa(caso, self.jefe, "Volvieron a su casa")

        caso.refresh_from_db()
        self.assertEqual(caso.estado, Estado.CERRADO)
        self.assertEqual(caso.motivo_cierre, CasoEmergencia.MotivoCierre.OTRO)
        self.assertEqual(caso.observacion_cierre, "Volvieron a su casa")
        self.assertIsNotNone(caso.cerrado_en)
        self.assertEqual(cerrado.estadias_egresadas, 3)
        self.assertFalse(Estadia.objects.filter(estado=Estadia.Estado.ACTIVA).exists())
        self.assertFalse(IntegranteGrupo.objects.filter(grupo=caso.grupo, egresado_en__isnull=True).exists())
        traza = self._trazas_de(caso, Accion.CERRADO_POR_LA_MESA).get()
        self.assertTrue(traza.por_supervisor)
        self.assertEqual((traza.estado_anterior, traza.estado_nuevo), (Estado.ALOJADO, Estado.CERRADO))
        self.assertIn("Volvieron a su casa", traza.detalle)
        # El receptor del egreso no cierra por segunda vez.
        self.assertFalse(self._trazas_de(caso, Accion.CERRADO_POR_EGRESO).exists())

    def test_un_ingreso_parcial_se_puede_cerrar(self):
        caso, derivacion = self._aceptado(menores_f=0, menores_m=0, adultos_f=1, adultos_m=2)
        self._confirmar(caso, 1, "45000101")
        caso = alojar.cerrar_con_diferencia(caso=caso, usuario=self.guardia, motivo="NO_LLEGO")
        self.assertEqual(caso.estado, Estado.ALOJADO)
        self.assertTrue(caso.ingreso_parcial)

        cerrar_alojado_por_la_mesa(caso, self.jefe, "Solo vino uno y se fue")

        self.assertEqual(self._estado(caso), Estado.CERRADO)
        self.assertIn("ingreso parcial", self._trazas_de(caso, Accion.CERRADO_POR_LA_MESA).get().detalle)

    def test_un_caso_que_no_esta_alojado_es_un_cambio_de_estado(self):
        caso = self._caso_tomado()
        with self.assertRaises(EstadoCambio):
            cerrar_alojado_por_la_mesa(caso, self.jefe, "Se fueron")
        self.assertEqual(self._estado(caso), Estado.EN_GESTION)

    def test_sin_motivo_de_egreso_activo_no_cierra_nada(self):
        caso = self._alojada()
        MotivoEgreso.objects.filter(codigo__in=("otro", "abandono")).update(activo=False)
        with self.assertRaises(ValidationError):
            cerrar_alojado_por_la_mesa(caso, self.jefe, "Se fueron")
        self.assertEqual(self._estado(caso), Estado.ALOJADO)
        self.assertEqual(Estadia.objects.filter(estado=Estadia.Estado.ACTIVA).count(), 2)

    def test_toma_los_candados_en_el_orden_de_un_egreso(self):
        """Estadía antes que caso: el receptor del egreso de la guardia hace lo mismo."""
        caso = self._alojada()
        with orden_de_candados(estadia=Estadia.objects, caso=CasoEmergencia.objects) as orden:
            cerrar_alojado_por_la_mesa(caso, self.jefe, "Se fueron")
        self.assertEqual(orden[0], "estadia")
        self.assertLess(orden.index("estadia"), orden.index("caso"))


class ReabrirTests(_Base):
    def _cerrada_sin_alojar(self, **kwargs):
        caso = self._caso_tomado(**{"dni": "30111222", **kwargs})
        return mesa.cerrar_sin_alojamiento(caso, self.operador, "NO_REQUIERE")

    def test_vuelve_a_en_gestion_con_su_dueno_y_queda_en_el_historial(self):
        caso = self._cerrada_sin_alojar()

        reabrir_caso(caso, self.jefe)

        caso.refresh_from_db()
        self.assertEqual(caso.estado, Estado.EN_GESTION)
        self.assertEqual(caso.tomado_por, self.operador)
        self.assertIsNone(caso.cerrado_en)
        self.assertEqual(caso.motivo_cierre, "")
        traza = self._trazas_de(caso, Accion.REABIERTO).get()
        self.assertTrue(traza.por_supervisor)
        self.assertEqual((traza.estado_anterior, traza.estado_nuevo), (Estado.CERRADO, Estado.EN_GESTION))

    def test_un_caso_cerrado_estando_alojado_vuelve_a_alojado(self):
        caso = self._alojada()
        cerrar_alojado_por_la_mesa(caso, self.jefe, "Se fueron")

        reabrir_caso(caso, self.jefe)

        self.assertEqual(self._estado(caso), Estado.ALOJADO)

    def test_se_puede_cerrar_de_nuevo_con_su_propia_fecha(self):
        caso = self._cerrada_sin_alojar()
        primera = CasoEmergencia.objects.get(pk=caso.pk).cerrado_en
        reabrir_caso(caso, self.jefe)
        self.reloj.avanzar(hours=2)

        mesa.cerrar_sin_alojamiento(CasoEmergencia.objects.get(pk=caso.pk), self.operador, "NO_REQUIERE")

        self.assertGreater(CasoEmergencia.objects.get(pk=caso.pk).cerrado_en, primera)

    def test_se_rechaza_si_la_familia_ya_tiene_otro_caso_abierto(self):
        caso = self._cerrada_sin_alojar()
        otro = self._caso(dni="30111222")
        self.assertNotEqual(otro.pk, caso.pk)

        with self.assertRaises(ReaperturaConOtroCasoAbierto) as error:
            reabrir_caso(caso, self.jefe)

        self.assertEqual(error.exception.caso.pk, otro.pk)
        self.assertEqual(self._estado(caso), Estado.CERRADO)
        self.assertFalse(self._trazas_de(caso, Accion.REABIERTO).exists())

    def test_con_el_otro_caso_ya_cerrado_se_puede(self):
        caso = self._cerrada_sin_alojar()
        otro = self._caso(dni="30111222")
        mesa.cerrar_sin_alojamiento(mesa.tomar_caso(otro, self.operador), self.operador, "NO_REQUIERE")

        reabrir_caso(caso, self.jefe)

        self.assertEqual(self._estado(caso), Estado.EN_GESTION)

    def test_un_caso_abierto_no_se_reabre(self):
        caso = self._caso_tomado()
        with self.assertRaises(EstadoCambio):
            reabrir_caso(caso, self.jefe)

    def test_toma_el_numerador_antes_que_el_caso(self):
        from programas.models import NumeradorEmergencia

        caso = self._cerrada_sin_alojar()
        with orden_de_candados(numerador=NumeradorEmergencia.objects, caso=CasoEmergencia.objects) as orden:
            reabrir_caso(caso, self.jefe)
        self.assertEqual(orden[:2], ["numerador", "caso"])


class TomarSinDuenoTests(_Base):
    def test_un_caso_derivado_sin_dueno_se_toma_y_conserva_su_estado(self):
        caso, _ = self._derivado()
        CasoEmergencia.objects.filter(pk=caso.pk).update(tomado_por=None)
        caso = CasoEmergencia.objects.get(pk=caso.pk)
        self.assertTrue(caso.abierto)

        tomado = mesa.tomar_caso(caso, self.otro_operador)

        self.assertEqual(tomado.estado, Estado.DERIVADO)
        self.assertEqual(tomado.tomado_por, self.otro_operador)

    def test_un_alojado_sin_dueno_se_toma(self):
        caso = self._alojada()
        CasoEmergencia.objects.filter(pk=caso.pk).update(tomado_por=None)

        tomado = mesa.tomar_caso(CasoEmergencia.objects.get(pk=caso.pk), self.operador)

        self.assertEqual(tomado.estado, Estado.ALOJADO)
        self.assertEqual(tomado.tomado_por, self.operador)

    def test_la_ficha_ofrece_tomar_un_caso_abierto_sin_dueno_en_cualquier_estado(self):
        for estado, ofrece in (
            (Estado.NUEVO, True),
            (Estado.DERIVADO, True),
            (Estado.ALOJADO, True),
            (Estado.CERRADO, False),
        ):
            sin_dueno = CasoEmergencia(estado=estado, tomado_por=None)
            acciones = mesa.acciones_posibles(sin_dueno, self.operador, es_supervisor=False, derivacion_pendiente=False)
            self.assertEqual(acciones["puede_tomar"], ofrece, estado)
        con_dueno = CasoEmergencia(estado=Estado.DERIVADO, tomado_por=self.otro_operador)
        acciones = mesa.acciones_posibles(con_dueno, self.operador, es_supervisor=False, derivacion_pendiente=False)
        self.assertFalse(acciones["puede_tomar"])

    def test_con_dueno_no_se_pisa(self):
        caso, _ = self._derivado()
        self.assertIsNotNone(caso.tomado_por_id)
        with self.assertRaises(CasoTomadoPorOtro):
            mesa.tomar_caso(caso, self.otro_operador)
        self.assertEqual(CasoEmergencia.objects.get(pk=caso.pk).tomado_por, self.operador)

    def test_un_caso_cerrado_no_se_toma(self):
        caso = mesa.cerrar_sin_alojamiento(self._caso_tomado(), self.operador, "NO_REQUIERE")
        with self.assertRaises(EstadoCambio):
            mesa.tomar_caso(caso, self.otro_operador)


class FuncionesPurasTests(SimpleTestCase):
    def test_cada_una_mira_el_estado(self):
        self.assertTrue(puede_cerrar_alojado_por_la_mesa(CasoEmergencia(estado=Estado.ALOJADO)))
        self.assertFalse(puede_cerrar_alojado_por_la_mesa(CasoEmergencia(estado=Estado.CERRADO)))
        self.assertTrue(puede_reabrir_el_caso(CasoEmergencia(estado=Estado.CERRADO)))
        self.assertFalse(puede_reabrir_el_caso(CasoEmergencia(estado=Estado.ALOJADO)))


class VistasTests(_Base):
    def _post(self, nombre, caso, datos=None):
        return self.client.post(reverse(f"emergencia:{nombre}", args=[caso.pk]), datos or {})

    def test_sin_la_capacidad_responde_403_y_no_escribe(self):
        caso = self._alojada()
        for usuario in (self.operador, self.supervisor, self.guardia):
            self.client.force_login(usuario)
            self.assertEqual(self._post("caso_cerrar_alojado", caso, {"motivo": "x"}).status_code, 403)
            self.assertEqual(self._post("caso_reabrir", caso).status_code, 403)
        self.assertEqual(self._estado(caso), Estado.ALOJADO)

    def test_cerrar_con_motivo_redirige_a_la_ficha_y_cierra(self):
        caso = self._alojada()
        self.client.force_login(User.objects.get(pk=self.jefe.pk))

        respuesta = self._post("caso_cerrar_alojado", caso, {"motivo": "Se fueron"})

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(self._estado(caso), Estado.CERRADO)

    def test_cerrar_sin_motivo_vuelve_a_mostrar_el_modal_y_no_cierra(self):
        caso = self._alojada()
        self.client.force_login(User.objects.get(pk=self.jefe.pk))

        respuesta = self._post("caso_cerrar_alojado", caso, {"motivo": ""})

        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(self._estado(caso), Estado.ALOJADO)

    def test_reabrir_solo_por_post(self):
        caso = mesa.cerrar_sin_alojamiento(self._caso_tomado(), self.operador, "NO_REQUIERE")
        self.client.force_login(User.objects.get(pk=self.jefe.pk))
        self.assertEqual(self.client.get(reverse("emergencia:caso_reabrir", args=[caso.pk])).status_code, 405)

    def test_reabrir_con_otro_caso_abierto_avisa_y_no_reabre(self):
        caso = mesa.cerrar_sin_alojamiento(self._caso_tomado(dni="30111222"), self.operador, "NO_REQUIERE")
        self._caso(dni="30111222")
        self.client.force_login(User.objects.get(pk=self.jefe.pk))

        respuesta = self._post("caso_reabrir", caso)

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(self._estado(caso), Estado.CERRADO)

    def test_next_externo_se_ignora(self):
        caso = mesa.cerrar_sin_alojamiento(self._caso_tomado(), self.operador, "NO_REQUIERE")
        self.client.force_login(User.objects.get(pk=self.jefe.pk))

        respuesta = self.client.post(
            reverse("emergencia:caso_reabrir", args=[caso.pk]) + "?next=https://malo.example/", {}
        )

        self.assertEqual(respuesta.status_code, 302)
        self.assertNotIn("malo.example", respuesta["Location"])

    def test_los_items_del_menu_solo_los_ve_quien_tiene_la_capacidad(self):
        alojado = self._alojada()
        cerrado = mesa.cerrar_sin_alojamiento(self._caso_tomado(dni="30222333"), self.operador, "NO_REQUIERE")
        for usuario, ve in ((self.jefe, True), (self.operador, False)):
            self.client.force_login(User.objects.get(pk=usuario.pk))
            html_alojado = self.client.get(reverse("emergencia:caso_detalle", args=[alojado.pk])).content.decode()
            html_cerrado = self.client.get(reverse("emergencia:caso_detalle", args=[cerrado.pk])).content.decode()
            self.assertEqual("Cerrar: la familia ya no está" in html_alojado, ve)
            self.assertEqual("Reabrir caso" in html_cerrado, ve)
