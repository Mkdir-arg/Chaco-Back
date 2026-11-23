"""Página del edificio: «Recibir kit» y los avisos de derivaciones y kits por recibir (Cambio 574; #1361, #1362, #1365).

1. «Recibir kit» (#1361): sin entregas por recibir en **este** edificio no se ofrece; con una lleva a su recepción; con
   varias, a la solapa Kits con el número. La entrega de otro edificio, la sin edificio y las ya cerradas no cuentan.
2. Avisos (#1362): las derivaciones y los kits por recibir de ESTE edificio, con la misma regla de quién los ve que la
   ficha de la institución y con alcance sobre el edificio. Sin pendientes no hay nada.
3. Contadores (#1365): ningún número de kits va suelto, siempre dice «por recibir».
4. Costo: los avisos suman una consulta por aviso y no crecen con la cantidad.
"""

from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import User
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from programas.models import EntregaKit
from programas.tests.test_emergencia_aviso_llegadas import Alcance, BaseAviso, MiembroEquipoDispositivo

Estado = EntregaKit.Estado
CAPS = ("dispositivo.ver", "dispositivo.admitir", "emergencia.recibir_kit")
AVISO_DERIVACION = "por Emergencia a este edificio esperando respuesta"
AVISO_KITS = "de kits por recibir en este edificio"


class BaseEdificioAvisos(BaseAviso):
    def setUp(self):
        super().setUp()
        self.edif_a = self._edificio("ED-A")
        self.edif_b = self._edificio("ED-B")
        self.todo = self._guardia("todo_club", self.club, capacidades=CAPS)
        self._numero = 0

    def _entrega(self, edificio, estado=Estado.EN_CAMINO, dispositivo=None):
        self._numero += 1
        return EntregaKit.objects.create(
            numero=f"2026-K-{self._numero:06d}",
            dispositivo=dispositivo or self.club,
            edificio=edificio,
            estado=estado,
            armada_por=self.operador,
            despachada_en=timezone.now(),
        )

    def _pagina(self, usuario, edificio, **params):
        self.client.force_login(User.objects.get(pk=usuario.pk))
        url = reverse("dispositivos:edificio_operativo", args=[self.club.pk, edificio.pk])
        respuesta = self.client.get(url, params)
        self.assertEqual(respuesta.status_code, 200)
        return respuesta

    def _url(self, edificio):
        return reverse("dispositivos:edificio_operativo", args=[self.club.pk, edificio.pk])

    def _acotado(self, nombre, *edificios, capacidades=CAPS):
        usuario = self._guardia(nombre, self.club, capacidades=capacidades)
        MiembroEquipoDispositivo.objects.filter(usuario=usuario).update(alcance=Alcance.EDIFICIOS)
        MiembroEquipoDispositivo.objects.get(usuario=usuario).edificios.set(edificios)
        return User.objects.get(pk=usuario.pk)


class RecibirKitTests(BaseEdificioAvisos):
    def test_sin_entregas_por_recibir_el_item_no_se_ofrece(self):
        respuesta = self._pagina(self.todo, self.edif_a)

        self.assertEqual(respuesta.context["url_recibir_kit"], "")
        self.assertNotContains(respuesta, "Recibir kit")
        # «Emergencia · Kits» sigue: es el listado de la institución.
        self.assertContains(respuesta, "Emergencia · Kits")

    def test_con_una_va_directo_a_su_recepcion_en_la_solapa_kits(self):
        entrega = self._entrega(self.edif_a)

        respuesta = self._pagina(self.todo, self.edif_a)

        esperada = f"{self._url(self.edif_a)}?tab=kits&entrega={entrega.pk}"
        self.assertEqual(respuesta.context["url_recibir_kit"], esperada)
        self.assertEqual(respuesta.context["texto_recibir_kit"], "Recibir kit")
        # El destino es el detalle con el formulario, que al confirmar vuelve a la solapa Kits del edificio.
        detalle = self._pagina(self.todo, self.edif_a, tab="kits", entrega=entrega.pk)
        self.assertContains(detalle, "Confirmar recepción")
        self.assertContains(detalle, f'name="next" value="{self._url(self.edif_a)}?tab=kits"')

    def test_con_varias_va_a_la_solapa_kits_y_el_texto_dice_cuantas(self):
        self._entrega(self.edif_a)
        self._entrega(self.edif_a, estado=Estado.PREPARADA)

        respuesta = self._pagina(self.todo, self.edif_a)

        self.assertEqual(respuesta.context["url_recibir_kit"], f"{self._url(self.edif_a)}?tab=kits")
        self.assertEqual(respuesta.context["texto_recibir_kit"], "Recibir kit (2)")
        self.assertContains(respuesta, "Recibir kit (2)")

    def test_la_entrega_de_otro_edificio_o_sin_edificio_no_cuenta(self):
        self._entrega(self.edif_b)
        self._entrega(None)

        norte = self._pagina(self.todo, self.edif_a)
        sur = self._pagina(self.todo, self.edif_b)

        self.assertEqual(norte.context["url_recibir_kit"], "")
        self.assertNotContains(norte, "Recibir kit")
        self.assertNotEqual(sur.context["url_recibir_kit"], "")

    def test_las_recibidas_y_canceladas_no_cuentan(self):
        self._entrega(self.edif_a, estado=Estado.RECIBIDA)
        self._entrega(self.edif_a, estado=Estado.CANCELADA)

        respuesta = self._pagina(self.todo, self.edif_a)

        self.assertEqual(respuesta.context["url_recibir_kit"], "")

    def test_sin_la_capacidad_de_kits_no_se_ofrece_aunque_haya_entregas(self):
        self._entrega(self.edif_a)
        sin = self._guardia("sin_kits", self.club, capacidades=("dispositivo.ver", "dispositivo.admitir"))

        respuesta = self._pagina(sin, self.edif_a)

        self.assertEqual(respuesta.context["url_recibir_kit"], "")
        self.assertNotContains(respuesta, "Recibir kit")

    def test_la_solapa_kits_lista_primero_las_por_recibir(self):
        recibida = self._entrega(self.edif_a, estado=Estado.RECIBIDA)
        vieja_abierta = self._entrega(self.edif_a)
        # La recibida es la más nueva por fecha de creación: igual va después de la abierta.
        EntregaKit.objects.filter(pk=recibida.pk).update(creado=timezone.now() + timedelta(hours=1))

        respuesta = self._pagina(self.todo, self.edif_a, tab="kits")

        filas = respuesta.context["kits"]["filas"]
        self.assertEqual([f["entrega"].pk for f in filas], [vieja_abierta.pk, recibida.pk])


class AvisoDeDerivacionesTests(BaseEdificioAvisos):
    def test_aparece_en_el_edificio_de_la_derivacion_y_no_en_el_otro(self):
        self._derivado_a(self.edif_a)

        norte = self._pagina(self.todo, self.edif_a)
        sur = self._pagina(self.todo, self.edif_b)

        self.assertContains(norte, f"1 familia derivada {AVISO_DERIVACION}")
        self.assertContains(norte, "Ir a Llegadas")
        self.assertContains(norte, "La primera vence el")
        self.assertNotContains(sur, AVISO_DERIVACION)

    def test_el_enlace_lleva_a_llegadas_de_ese_edificio(self):
        self._derivado_a(self.edif_a)

        respuesta = self._pagina(self.todo, self.edif_a)

        destino = f"{self.url_llegadas}?edificio={self.edif_a.pk}"
        self.assertContains(respuesta, f'href="{destino}"')

    def test_con_alcance_edificios_solo_ve_el_aviso_de_los_suyos(self):
        self._derivado_a(self.edif_b)
        guardia_de_a = self._acotado("de_a", self.edif_a)

        propio = self._pagina(guardia_de_a, self.edif_a)

        self.assertNotContains(propio, AVISO_DERIVACION)
        # La página de un edificio fuera de su alcance ni se abre.
        self.client.force_login(guardia_de_a)
        self.assertEqual(self.client.get(self._url(self.edif_b)).status_code, 404)

    def test_sin_dispositivo_admitir_no_hay_aviso_ni_se_paga_la_consulta(self):
        self._derivado_a(self.edif_a)
        solo_kits = self._guardia("solo_kits", self.club, capacidades=("dispositivo.ver", "emergencia.recibir_kit"))

        with mock.patch("programas.services.edificio_operativo.pendientes_por_recibir") as selector:
            respuesta = self._pagina(solo_kits, self.edif_a)

        self.assertNotContains(respuesta, AVISO_DERIVACION)
        selector.assert_not_called()  # sin `admitir` ni siquiera se paga la consulta

    def test_una_derivacion_sin_edificio_no_aparece_en_ninguno(self):
        self._derivado_a()

        self.assertNotContains(self._pagina(self.todo, self.edif_a), AVISO_DERIVACION)

    def test_la_ficha_de_la_institucion_sigue_mostrando_el_aviso_general(self):
        self._derivado_a(self.edif_a)
        self.client.force_login(self.todo)

        ficha = self.client.get(self.url)

        self.assertContains(ficha, "familia derivada por Emergencia esperando respuesta")

    def test_sin_pendientes_no_hay_avisos(self):
        respuesta = self._pagina(self.todo, self.edif_a)

        self.assertEqual(respuesta.context["avisos"], [])


class AvisoDeKitsTests(BaseEdificioAvisos):
    def test_aparece_en_el_edificio_de_la_entrega_con_acceso_a_la_recepcion(self):
        entrega = self._entrega(self.edif_a)

        norte = self._pagina(self.todo, self.edif_a)
        sur = self._pagina(self.todo, self.edif_b)

        self.assertContains(norte, f"1 entrega {AVISO_KITS}")
        self.assertContains(norte, f'href="{self._url(self.edif_a)}?tab=kits&amp;entrega={entrega.pk}"')
        self.assertNotContains(sur, AVISO_KITS)

    def test_con_varias_cuenta_y_enlaza_a_la_solapa(self):
        self._entrega(self.edif_a)
        self._entrega(self.edif_a, estado=Estado.PREPARADA)

        respuesta = self._pagina(self.todo, self.edif_a)

        self.assertContains(respuesta, f"2 entregas {AVISO_KITS}")
        self.assertContains(respuesta, "Ver entregas")

    def test_con_alcance_edificios_solo_en_los_suyos(self):
        self._entrega(self.edif_b)
        guardia_de_a = self._acotado("de_a", self.edif_a)

        self.assertNotContains(self._pagina(guardia_de_a, self.edif_a), AVISO_KITS)
        guardia_de_b = self._acotado("de_b", self.edif_b)
        self.assertContains(self._pagina(guardia_de_b, self.edif_b), AVISO_KITS)

    def test_sin_emergencia_recibir_kit_no_aparece(self):
        self._entrega(self.edif_a)
        sin = self._guardia("sin_kits", self.club, capacidades=("dispositivo.ver", "dispositivo.admitir"))

        self.assertNotContains(self._pagina(sin, self.edif_a), AVISO_KITS)

    def test_el_admin_del_programa_y_el_superusuario_lo_ven(self):
        self._entrega(self.edif_a)
        admin = self._usuario(
            "admin_kits",
            ("programa.configurar", "dispositivo.ver", "emergencia.recibir_kit"),
            programa=self.dispositivos,
        )
        root = User.objects.create_superuser("root_kits", "root@example.com", "x")

        for usuario in (admin, root):
            self.assertContains(self._pagina(usuario, self.edif_a), AVISO_KITS, msg_prefix=usuario.username)


class ContadoresTests(BaseEdificioAvisos):
    def test_el_cero_del_badge_dice_por_recibir(self):
        self._entrega(self.edif_a, estado=Estado.RECIBIDA)

        respuesta = self._pagina(self.todo, self.edif_a)

        self.assertContains(respuesta, "0 por recibir</span>")

    def test_con_una_por_recibir_dice_1_por_recibir(self):
        self._entrega(self.edif_a)

        respuesta = self._pagina(self.todo, self.edif_a)

        self.assertContains(respuesta, "1 por recibir</span>")

    def test_el_encabezado_de_la_lista_es_coherente(self):
        self._entrega(self.edif_a, estado=Estado.RECIBIDA)
        self._entrega(self.edif_a, estado=Estado.RECIBIDA)

        respuesta = self._pagina(self.todo, self.edif_a, tab="kits")

        self.assertContains(respuesta, "2 entregas · 0 por recibir")


class PresupuestoTests(BaseEdificioAvisos):
    def _consultas(self):
        self._pagina(self.todo, self.edif_a)  # calienta sesión y cachés
        with CaptureQueriesContext(connection) as captura:
            self._pagina(self.todo, self.edif_a)
        return len(captura)

    def test_los_avisos_no_crecen_con_las_derivaciones_ni_las_entregas(self):
        self._derivado_a(self.edif_a)
        self._entrega(self.edif_a)
        antes = self._consultas()
        self._derivado_a(self.edif_a, dni="30222333", plazas=2)
        for _ in range(4):
            self._entrega(self.edif_a)

        self.assertEqual(self._consultas(), antes)

    def test_el_aviso_de_derivaciones_suma_una_consulta(self):
        self._derivado_a(self.edif_a)
        con_aviso = self._consultas()
        with mock.patch("programas.services.edificio_operativo.pendientes_por_recibir", return_value=None):
            sin_aviso = self._consultas()

        # El de kits no suma: el contador de la solapa y «Recibir kit» salen de la misma consulta.
        self.assertEqual(con_aviso - sin_aviso, 1)
