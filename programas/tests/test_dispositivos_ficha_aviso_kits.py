"""Ficha de la institución: aviso de entregas de kits por recibir (#1347).

Es el hermano del aviso de derivaciones (#1302, ``test_emergencia_aviso_llegadas``) y reusa
``aviso_de_kits_por_recibir`` de ``programas.services.kits`` (rama ``para esta institución``).

1. Quién lo ve: ``emergencia.recibir_kit`` con alcance sobre TODA la institución (Equipo), el admin del programa y el
   superusuario. No lo ve quien tiene ``dispositivo.ver``, ``ver_todos`` o ``admitir`` sin ``recibir_kit``, ni quien
   recibe kits solo con alcance Edificios (Cambio 523: el aviso es de la institución; el suyo vive en la página de
   cada edificio).
2. Qué cuenta: ``EntregaKit.ESTADOS_ABIERTOS`` con destino a esa institución, tengan o no edificio.
3. Texto: nombra la entrega más vieja y el botón «Recibir kits» lleva a la recepción de la institución.
4. Costo: UNA consulta más en la ficha, y ninguna para quien no puede verlo.
"""

from unittest import mock

from django.contrib.auth.models import User
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from programas.models import EntregaKit, MiembroEquipoDispositivo
from programas.selectors.kits import entregas_por_recibir_de
from programas.services.kits import aviso_de_kits_por_recibir
from programas.tests.test_emergencia_aviso_llegadas import BaseAviso

Estado = EntregaKit.Estado
CAPS = ("dispositivo.ver", "emergencia.recibir_kit")
TITULO = "de kits por recibir para esta institución"
SELECTOR = "programas.views.dispositivos_legajo.entregas_por_recibir_de"


class BaseFichaKits(BaseAviso):
    def setUp(self):
        super().setUp()
        self.url_kits = reverse("emergencia:dispositivo_kits", args=[self.club.pk])
        self.recibe = self._guardia("recibe_kits", self.club, capacidades=CAPS)
        self._numero = 0

    def _entrega(self, estado=Estado.EN_CAMINO, edificio=None, dispositivo=None):
        self._numero += 1
        return EntregaKit.objects.create(
            numero=f"2026-K-{self._numero:06d}",
            dispositivo=dispositivo or self.club,
            edificio=edificio,
            estado=estado,
            armada_por=self.operador,
            despachada_en=timezone.now(),
        )

    def _admin_con_kits(self):
        return self._usuario(
            "admin_kits",
            ("programa.configurar", "dispositivo.ver", "emergencia.recibir_kit"),
            programa=self.dispositivos,
        )


class QuienLoVeTests(BaseFichaKits):
    def setUp(self):
        super().setUp()
        self._entrega()

    def test_la_guardia_con_recibir_kit_en_el_equipo_lo_ve_con_su_texto_y_el_boton(self):
        respuesta = self._ver(self.recibe)

        self.assertContains(respuesta, f"1 entrega {TITULO}")
        self.assertContains(respuesta, "Recibir kits")
        self.assertContains(respuesta, f'href="{self.url_kits}"')
        self.assertContains(respuesta, "bg-warning-soft")

    def test_el_admin_del_programa_lo_ve(self):
        self.assertContains(self._ver(self._admin_con_kits()), f"1 entrega {TITULO}")

    def test_el_superusuario_lo_ve(self):
        root = User.objects.create_superuser("root", "root@example.com", "x")
        self.assertContains(self._ver(root), f"1 entrega {TITULO}")

    def test_con_dispositivo_ver_solo_no_lo_ve_ni_paga_la_consulta(self):
        solo_ver = self._guardia("solo_ver", self.club, capacidades=("dispositivo.ver",))
        with mock.patch(SELECTOR) as selector:
            respuesta = self._ver(solo_ver)

        self.assertNotContains(respuesta, TITULO)
        self.assertIsNone(respuesta.context["aviso_kits"])
        selector.assert_not_called()

    def test_con_ver_todos_no_lo_ve(self):
        ve_todos = self._usuario("ve_todos", ("dispositivo.ver", "dispositivo.ver_todos"), programa=self.dispositivos)
        with mock.patch(SELECTOR) as selector:
            respuesta = self._ver(ve_todos)

        self.assertNotContains(respuesta, TITULO)
        selector.assert_not_called()

    def test_con_admitir_sin_recibir_kit_no_lo_ve(self):
        admite = self._guardia("admite", self.club, capacidades=("dispositivo.ver", "dispositivo.admitir"))
        with mock.patch(SELECTOR) as selector:
            respuesta = self._ver(admite)

        self.assertNotContains(respuesta, TITULO)
        selector.assert_not_called()

    def test_con_recibir_kit_pero_solo_con_alcance_edificios_no_lo_ve(self):
        edificio = self._edificio("ED-A")
        self._entrega(edificio=edificio)
        acotado = self._guardia_con_kits_en(edificio)
        with mock.patch(SELECTOR) as selector:
            respuesta = self._ver(acotado)

        self.assertNotContains(respuesta, TITULO)
        selector.assert_not_called()

    def _guardia_con_kits_en(self, edificio):
        usuario = self._guardia("acotado_kits", self.club, capacidades=CAPS)
        MiembroEquipoDispositivo.objects.filter(usuario=usuario).update(
            alcance=MiembroEquipoDispositivo.Alcance.EDIFICIOS
        )
        MiembroEquipoDispositivo.objects.get(usuario=usuario).edificios.set([edificio])
        return User.objects.get(pk=usuario.pk)

    def test_la_guardia_de_otra_institucion_ni_abre_la_ficha(self):
        self.client.force_login(self.guardia_escuela)
        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.status_code, 404)
        self.assertNotContains(respuesta, TITULO, status_code=404)


class QueCuentaTests(BaseFichaKits):
    def test_sin_entregas_no_hay_aviso(self):
        respuesta = self._ver(self.recibe)

        self.assertNotContains(respuesta, TITULO)
        self.assertIsNone(respuesta.context["aviso_kits"])

    def test_en_camino_y_preparadas_cuentan(self):
        self._entrega(Estado.EN_CAMINO)
        self._entrega(Estado.PREPARADA)

        self.assertContains(self._ver(self.recibe), f"2 entregas {TITULO}")

    def test_una_entrega_recibida_con_o_sin_diferencias_o_cancelada_no_cuenta(self):
        self._entrega(Estado.RECIBIDA)
        self._entrega(Estado.RECIBIDA_CON_DIFERENCIAS)
        self._entrega(Estado.CANCELADA)

        self.assertNotContains(self._ver(self.recibe), TITULO)

    def test_el_aviso_se_va_al_recibir_la_entrega(self):
        entrega = self._entrega()
        self.assertContains(self._ver(self.recibe), TITULO)

        EntregaKit.objects.filter(pk=entrega.pk).update(estado=Estado.RECIBIDA)

        self.assertNotContains(self._ver(self.recibe), TITULO)

    def test_las_de_otra_institucion_no_cuentan(self):
        self._entrega(dispositivo=self.escuela)

        self.assertNotContains(self._ver(self.recibe), TITULO)

    def test_cuentan_las_de_cualquier_edificio_y_las_que_no_tienen(self):
        edif_a, edif_b = self._edificio("ED-A"), self._edificio("ED-B")
        self._entrega(edificio=edif_a)
        self._entrega(edificio=edif_b)
        self._entrega(edificio=None)

        self.assertContains(self._ver(self.recibe), f"3 entregas {TITULO}")

    def test_nombra_la_mas_vieja_y_lleva_a_la_recepcion_de_la_institucion(self):
        self._entrega()  # 2026-K-000001
        self._entrega()  # 2026-K-000002

        aviso = self._ver(self.recibe).context["aviso_kits"]

        self.assertIn("La más vieja es la entrega 2026-K-000001.", aviso["texto"])
        self.assertEqual(aviso["accion_url"], self.url_kits)
        self.assertEqual(aviso["accion_texto"], "Recibir kits")
        self.assertEqual(aviso["tono"], "warning")

    def test_si_la_mas_vieja_se_recibe_pasa_a_nombrar_la_siguiente(self):
        primera = self._entrega()
        self._entrega()
        EntregaKit.objects.filter(pk=primera.pk).update(estado=Estado.RECIBIDA)

        self.assertContains(self._ver(self.recibe), "La más vieja es la entrega 2026-K-000002.")


class ConviveConDerivacionesTests(BaseFichaKits):
    def test_con_derivaciones_y_kits_pendientes_se_ven_los_dos_avisos_cada_uno_con_su_enlace(self):
        self._derivado()
        self._entrega()
        # Una guardia del Equipo con admitir y recibir kit: los dos avisos, uno debajo del otro.
        guardia = self._guardia(
            "guardia_ambas", self.club, capacidades=("dispositivo.ver", "dispositivo.admitir", "emergencia.recibir_kit")
        )

        respuesta = self._ver(guardia)

        self.assertContains(respuesta, "familia derivada por Emergencia esperando respuesta")
        self.assertContains(respuesta, TITULO)
        self.assertContains(respuesta, f'href="{self.url_llegadas}"')
        self.assertContains(respuesta, f'href="{self.url_kits}"')
        contenido = respuesta.content.decode()
        self.assertLess(contenido.index("esperando respuesta"), contenido.index(TITULO))


class AvisoDeKitsTests(BaseFichaKits):
    """El servicio puro: la rama de la institución y que la de la página del edificio no cambia."""

    def test_sin_cantidad_no_hay_aviso(self):
        self.assertIsNone(aviso_de_kits_por_recibir(0, "/x/"))
        self.assertIsNone(aviso_de_kits_por_recibir(0, "/x/", mas_vieja="2026-K-000001"))

    def test_la_rama_de_la_institucion_dice_para_esta_institucion_y_recibir_kits(self):
        uno = aviso_de_kits_por_recibir(1, "/x/", mas_vieja="2026-K-000007")
        varias = aviso_de_kits_por_recibir(3, "/x/", mas_vieja="2026-K-000007")

        self.assertEqual(uno["titulo"], "1 entrega de kits por recibir para esta institución")
        self.assertEqual(varias["titulo"], "3 entregas de kits por recibir para esta institución")
        self.assertEqual(uno["accion_texto"], "Recibir kits")
        self.assertEqual(varias["accion_texto"], "Recibir kits")
        self.assertTrue(uno["texto"].startswith("La más vieja es la entrega 2026-K-000007. "))

    def test_la_salida_de_la_pagina_del_edificio_no_cambia(self):
        uno = aviso_de_kits_por_recibir(1, "/x/", en_este_edificio=True)
        varias = aviso_de_kits_por_recibir(2, "/x/", en_este_edificio=True)

        self.assertEqual(uno["titulo"], "1 entrega de kits por recibir en este edificio")
        self.assertEqual(uno["accion_texto"], "Recibir kit")
        self.assertEqual(varias["accion_texto"], "Ver entregas")
        self.assertEqual(
            uno["texto"], "Hasta que se confirme la recepción, la mesa de Emergencia las sigue viendo abiertas."
        )

    def test_el_selector_cuenta_y_nombra_la_mas_vieja_en_una_consulta(self):
        self.assertEqual(entregas_por_recibir_de(self.club), (0, None))
        self._entrega()
        self._entrega(Estado.PREPARADA)
        self._entrega(Estado.RECIBIDA)
        with CaptureQueriesContext(connection) as captura:
            resultado = entregas_por_recibir_de(self.club)

        self.assertEqual(resultado, (2, "2026-K-000001"))
        self.assertEqual(len(captura), 1)


class PresupuestoTests(BaseFichaKits):
    def _consultas(self, usuario):
        self._ver(usuario)  # calienta lo que se memoiza por proceso
        with CaptureQueriesContext(connection) as captura:
            self._ver(usuario)
        return len(captura)

    def test_el_aviso_suma_exactamente_una_consulta_a_la_ficha(self):
        self._entrega()
        for usuario in (self.recibe, self._admin_con_kits()):
            con_aviso = self._consultas(usuario)
            with mock.patch(SELECTOR, return_value=(0, None)):
                sin_aviso = self._consultas(usuario)
            self.assertEqual(con_aviso - sin_aviso, 1, usuario.username)

    def test_cuesta_lo_mismo_con_una_que_con_muchas_entregas(self):
        self._entrega()
        una = self._consultas(self.recibe)
        for _ in range(8):
            self._entrega()
        self.assertEqual(self._consultas(self.recibe), una)

    def test_quien_no_puede_verlo_no_paga_nada(self):
        self._entrega()
        solo_ver = self._guardia("solo_ver", self.club, capacidades=("dispositivo.ver",))
        with mock.patch(SELECTOR, side_effect=AssertionError("no debe consultarse")):
            self._ver(solo_ver)
