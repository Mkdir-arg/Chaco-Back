"""Aviso en la ficha de la institución: derivaciones de Emergencia por recibir (#1302).

Qué fija este archivo:

* **Quién lo ve** — `dispositivo.admitir` con Equipo, el admin del programa y el superusuario. Nadie más:
  ni `dispositivo.ver` solo ni `ver_todos`.
* **Qué cuenta** — solo las `PENDIENTE` de casos `DERIVADO`; con alcance Edificios, solo las de sus edificios
  (la misma regla que Llegadas, por `q_edificios_en_alcance`).
* **Tono y texto** — «N familia(s) derivada(s)…», el vencimiento más próximo y `danger` si vence en menos de
  `POR_VENCER_MIN` minutos.
* **Presupuesto** — el aviso suma una consulta a la ficha.

El admin del programa y el superusuario tienen alcance total (`Q()` vacío): por eso el filtro es un `filter` y
nunca un `exclude` (#1298).
"""

from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import User
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from programas.models import Derivacion, Edificio, MiembroEquipoDispositivo
from programas.selectors import emergencia_alojar as selectores
from programas.services import emergencia as mesa
from programas.services import emergencia_alojar as servicio
from programas.services.avisos_emergencia import POR_VENCER_MIN
from programas.tests.test_emergencia_alojar_base import BaseAlojar

Alcance = MiembroEquipoDispositivo.Alcance
TEXTO = "familia derivada por Emergencia esperando respuesta"


class BaseAviso(BaseAlojar):
    def setUp(self):
        super().setUp()
        self.url = reverse("dispositivos:detalle", args=[self.club.pk])
        self.url_llegadas = reverse("dispositivos:emergencia_llegadas", args=[self.club.pk])

    def _ver(self, usuario):
        self.client.force_login(usuario)
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 200)
        return respuesta

    def _admin(self):
        return self._usuario(
            "admin_programa",
            ("programa.configurar", "dispositivo.ver", "dispositivo.admitir"),
            programa=self.dispositivos,
        )

    def _edificio(self, codigo):
        edificio = Edificio.objects.create(codigo=codigo, nombre=f"Edificio {codigo}")
        edificio.dispositivos.add(self.club)
        return edificio

    def _guardia_de(self, nombre, *edificios):
        usuario = self._guardia(nombre, self.club)
        MiembroEquipoDispositivo.objects.filter(usuario=usuario).update(alcance=Alcance.EDIFICIOS)
        MiembroEquipoDispositivo.objects.get(usuario=usuario).edificios.set(edificios)
        return User.objects.get(pk=usuario.pk)

    def _derivado_a(self, edificio=None, **datos):
        caso, derivacion = self._derivado(**datos)
        if edificio is not None:
            Derivacion.objects.filter(pk=derivacion.pk).update(edificio=edificio)
        return caso, derivacion


class QuienLoVeTests(BaseAviso):
    def setUp(self):
        super().setUp()
        self._derivado()

    def test_la_guardia_con_admitir_en_el_equipo_lo_ve_con_su_texto_y_el_enlace(self):
        respuesta = self._ver(self.guardia)
        self.assertContains(respuesta, f"1 {TEXTO}")
        self.assertContains(respuesta, "Ir a Llegadas")
        self.assertContains(respuesta, f'href="{self.url_llegadas}"')
        self.assertContains(respuesta, "La primera vence el 12/11 22:00.")

    def test_el_admin_del_programa_lo_ve(self):
        self.assertContains(self._ver(self._admin()), f"1 {TEXTO}")

    def test_el_superusuario_lo_ve(self):
        root = User.objects.create_superuser("root", "root@example.com", "x")
        self.assertContains(self._ver(root), f"1 {TEXTO}")

    def test_quien_solo_tiene_ver_en_el_equipo_no_lo_ve(self):
        solo_ver = self._guardia("solo_ver", self.club, capacidades=("dispositivo.ver",))
        with mock.patch("programas.views.dispositivos_legajo.pendientes_por_recibir") as selector:
            respuesta = self._ver(solo_ver)
        self.assertNotContains(respuesta, TEXTO)
        self.assertNotContains(respuesta, "Ir a Llegadas")
        selector.assert_not_called()  # sin `admitir` ni siquiera se paga la consulta

    def test_quien_tiene_ver_todos_no_lo_ve(self):
        ve_todos = self._usuario("ve_todos", ("dispositivo.ver", "dispositivo.ver_todos"), programa=self.dispositivos)
        respuesta = self._ver(ve_todos)
        self.assertNotContains(respuesta, TEXTO)

    def test_la_guardia_de_otra_institucion_ni_abre_la_ficha(self):
        self.client.force_login(self.guardia_escuela)
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 404)
        self.assertNotContains(respuesta, TEXTO, status_code=404)


class QueCuentaTests(BaseAviso):
    def test_sin_derivaciones_pendientes_no_hay_aviso(self):
        self.assertNotContains(self._ver(self.guardia), TEXTO)
        self.assertIsNone(selectores.pendientes_por_recibir(self.club, self.guardia))

    def test_una_derivacion_aceptada_ya_no_cuenta(self):
        _caso, derivacion = self._derivado()
        self.assertContains(self._ver(self.guardia), TEXTO)
        servicio.aceptar_derivacion(derivacion=derivacion, usuario=self.guardia)
        self.assertNotContains(self._ver(self.guardia), TEXTO)

    def test_una_derivacion_cancelada_ya_no_cuenta(self):
        _caso, derivacion = self._derivado()
        mesa.cancelar_derivacion(derivacion, self.operador, "Se equivocó de dispositivo")
        self.assertNotContains(self._ver(self.guardia), TEXTO)

    def test_las_de_otro_dispositivo_no_cuentan(self):
        self._derivado(dispositivo=self.escuela, plazas=2)
        self.assertNotContains(self._ver(self.guardia), TEXTO)

    def test_dos_familias_se_cuentan_y_el_texto_nombra_el_vencimiento_mas_proximo(self):
        _c1, primera = self._derivado()
        self.reloj.avanzar(hours=1)
        self._derivado(dni="30222333", plazas=2)
        respuesta = self._ver(self.guardia)
        self.assertContains(respuesta, "2 familias derivadas por Emergencia esperando respuesta")
        resumen = selectores.pendientes_por_recibir(self.club, self.guardia)
        self.assertEqual(resumen["cantidad"], 2)
        self.assertEqual(resumen["primera_vence"], Derivacion.objects.get(pk=primera.pk).vence_en)

    def test_con_alcance_edificios_cuenta_solo_las_de_sus_edificios(self):
        edif_a, edif_b = self._edificio("ED-A"), self._edificio("ED-B")
        self._derivado_a(edif_a)
        self._derivado_a(edif_b, dni="30222333", plazas=2)
        self.assertContains(self._ver(self._guardia_de("de_a", edif_a)), f"1 {TEXTO}")
        self.assertContains(self._ver(self._guardia_de("de_ab", edif_a, edif_b)), "2 familias derivadas")
        self.assertContains(self._ver(self._admin()), "2 familias derivadas")

    def test_con_alcance_edificios_sin_derivaciones_en_los_suyos_no_hay_aviso(self):
        edif_a, edif_b = self._edificio("ED-A"), self._edificio("ED-B")
        self._derivado_a(edif_b)
        self.assertNotContains(self._ver(self._guardia_de("de_a", edif_a)), TEXTO)

    def test_una_derivacion_sin_edificio_no_entra_con_alcance_edificios_pero_si_con_toda_la_institucion(self):
        edif_a = self._edificio("ED-A")
        self._derivado_a()
        self.assertNotContains(self._ver(self._guardia_de("de_a", edif_a)), TEXTO)
        self.assertContains(self._ver(self.guardia), f"1 {TEXTO}")


class TonoTests(BaseAviso):
    def _aviso(self, usuario):
        return self._ver(usuario).context["aviso_llegadas"]

    def test_con_margen_el_tono_es_de_advertencia(self):
        self._derivado()
        aviso = self._aviso(self.guardia)
        self.assertEqual(aviso["tono"], "warning")
        self.assertContains(self._ver(self.guardia), "bg-warning-soft")

    def test_por_vencer_se_destaca_como_peligro(self):
        _caso, derivacion = self._derivado()
        vence = Derivacion.objects.get(pk=derivacion.pk).vence_en
        self.reloj.ahora = vence - timedelta(minutes=POR_VENCER_MIN - 1)
        self.assertEqual(self._aviso(self.guardia)["tono"], "danger")
        self.assertContains(self._ver(self.guardia), "bg-danger-soft")

    def test_una_vencida_que_el_cron_todavia_no_marco_sigue_avisando_como_peligro(self):
        _caso, derivacion = self._derivado()
        self.reloj.ahora = Derivacion.objects.get(pk=derivacion.pk).vence_en + timedelta(minutes=5)
        aviso = self._aviso(self.guardia)
        self.assertEqual(aviso["tono"], "danger")
        self.assertIn("La primera venció el", aviso["texto"])

    def test_justo_en_el_umbral_todavia_es_advertencia(self):
        _caso, derivacion = self._derivado()
        vence = Derivacion.objects.get(pk=derivacion.pk).vence_en
        self.reloj.ahora = vence - timedelta(minutes=POR_VENCER_MIN)
        self.assertEqual(self._aviso(self.guardia)["tono"], "warning")


class PresupuestoTests(BaseAviso):
    def _consultas(self, usuario):
        self._ver(usuario)  # calienta lo que se memoiza por proceso
        with CaptureQueriesContext(connection) as captura:
            self._ver(usuario)
        return len(captura)

    def test_el_aviso_suma_una_consulta_a_la_ficha(self):
        self._derivado()
        for usuario in (self.guardia, self._admin()):
            con_aviso = self._consultas(usuario)
            with mock.patch("programas.views.dispositivos_legajo.pendientes_por_recibir", return_value=None):
                sin_aviso = self._consultas(usuario)
            self.assertEqual(con_aviso - sin_aviso, 1, usuario.username)

    def test_el_selector_cuesta_una_consulta_con_cualquier_cantidad_de_pendientes(self):
        self._derivado()
        selectores.pendientes_por_recibir(self.club, self.guardia)
        with CaptureQueriesContext(connection) as una:
            selectores.pendientes_por_recibir(self.club, self.guardia)
        self._derivado(dni="30222333", plazas=2)
        with CaptureQueriesContext(connection) as dos:
            selectores.pendientes_por_recibir(self.club, self.guardia)
        self.assertEqual(len(una), len(dos))
