"""Detalle de la estadía: la persona alojada, su línea de tiempo y el cambio de plaza (MVP v2, etapa 3 · #698 · P7).

Lo que se verifica, y por qué:

1. **Quién entra.** `dispositivo.ver` con alcance de programa y asignación al
   dispositivo, y además `ciudadano.ver`: la pantalla muestra nombre, DNI e historia de
   una persona. Sin `ciudadano.ver` el 403 sale **antes** de buscar la estadía, así que
   probar ids no dice cuáles existen. Una estadía de otro dispositivo da 404.
2. **La línea de tiempo refleja todos los movimientos en orden** (criterio de la task):
   del más nuevo al más viejo, recortada a los últimos diez, con la lista completa en la
   solapa Movimientos y el contador con el total real.
3. **El cambio de plaza** pasa por `cambiar_plaza`: plaza libre según el servicio de
   ocupación, motivo obligatorio, `dispositivo.admitir` con alcance, y la fecha del
   `datetime-local` comparada al minuto contra el último movimiento.
4. **Las acciones no se ofrecen** a quien el servicio va a rechazar.
5. **El costo no crece** con los movimientos ni con las otras estadías de la persona.

Los usuarios de cada prueba tienen **todo menos la condición que se prueba**.
"""

import json
import re
from collections import Counter
from datetime import timedelta
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.db import connection
from django.test import Client, tag
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from programas.models import Estadia, MotivoEgreso, MovimientoEstadia, Plaza, Sector
from programas.selectors import estadia_detalle
from programas.selectors.estadia_detalle import TOPE_EVENTOS, detalle_de_estadia
from programas.services.estadias import cambiar_plaza, egresar_persona, ingresar_persona
from programas.services.movimientos import registrar_movimiento
from programas.tests.test_dispositivos_estadias import BaseEstadias
from programas.views.dispositivos_legajo import url_solapa_estadias

FORMATO = "%Y-%m-%dT%H:%M"
TOKEN_CSRF = "a" * 32
TODO = ("dispositivo.ver", "dispositivo.admitir", "dispositivo.egresar", "dispositivo.editar", "ciudadano.ver")
PRESUPUESTOS = Path(settings.BASE_DIR) / "scripts" / "perf_budgets.json"
CLAVE_PRESUPUESTO = "dispositivos_estadia_detalle"

Tipo = MovimientoEstadia.Tipo


def _menos(*quitar):
    return tuple(c for c in TODO if c not in quitar)


class BaseDetalle(BaseEstadias):
    """Una persona alojada hace tres días en la plaza P1 del CIS, con un operador que tiene todo."""

    def setUp(self):
        super().setUp()
        self.alta = MotivoEgreso.objects.create(codigo="alta", nombre="Alta", orden=1)
        self.otro_sector = Sector.objects.create(dispositivo=self.cis, nombre="Mujeres", capacidad=2)
        self.plaza_otro_sector = Plaza.objects.create(sector=self.otro_sector, codigo="M1")
        self.operador = self._operador("Operador P7", self.cis, TODO)
        self.ingreso = timezone.now() - timedelta(days=3)
        self.estadia = ingresar_persona(
            ciudadano=self.persona,
            dispositivo=self.cis,
            plaza=self.plaza,
            usuario=self.operador,
            fecha_ingreso=self.ingreso,
        )
        self.url = reverse("dispositivos:estadia_detalle", args=[self.cis.pk, self.estadia.pk])

    def _cliente(self, usuario=None):
        cliente = Client()
        cliente.force_login(usuario or self.operador)
        return cliente

    def _get(self, usuario=None, url=None):
        return self._cliente(usuario).get(url or self.url)

    def _cambiar(self, momento, plaza=None, motivo="Convivencia"):
        return cambiar_plaza(
            estadia=self.estadia, plaza=plaza or self.otra_plaza, usuario=self.operador, motivo=motivo, momento=momento
        )


class AutorizacionTests(BaseDetalle):
    def test_con_todo_ve_la_pantalla_de_la_persona(self):
        respuesta = self._get()

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, self.persona.nombre_completo)
        self.assertContains(respuesta, "DNI 30111222")

    def test_sin_dispositivo_ver_no_entra_aunque_tenga_todo_lo_demas(self):
        usuario = self._operador("Sin ver", self.cis, _menos("dispositivo.ver"))

        self.assertEqual(self._get(usuario).status_code, 403)

    def test_sin_ciudadano_ver_no_entra_aunque_tenga_todo_lo_demas(self):
        usuario = self._operador("Sin ciudadano", self.cis, _menos("ciudadano.ver"))

        respuesta = self._get(usuario)

        self.assertEqual(respuesta.status_code, 403)
        self.assertNotContains(respuesta, self.persona.apellido, status_code=403)

    def test_sin_ciudadano_ver_un_id_inexistente_tambien_da_403(self):
        """El 403 sale antes de buscar la estadía: probar ids no dice cuáles existen."""

        usuario = self._operador("Sin ciudadano", self.cis, _menos("ciudadano.ver"))
        url = reverse("dispositivos:estadia_detalle", args=[self.cis.pk, 999999])

        self.assertEqual(self._get(usuario, url).status_code, 403)

    def test_con_todo_en_otra_institucion_no_entra(self):
        usuario = self._operador("Todo en el parador", self.parador, TODO)

        self.assertEqual(self._get(usuario).status_code, 403)

    def test_una_estadia_de_otro_dispositivo_da_404(self):
        usuario = self._operador("Todo en el parador", self.parador, TODO)
        url = reverse("dispositivos:estadia_detalle", args=[self.parador.pk, self.estadia.pk])

        self.assertEqual(self._get(usuario, url).status_code, 404)


class LineaDeTiempoTests(BaseDetalle):
    def _recorrido_completo(self):
        """Ingreso, cambio de plaza, cambio de sector y egreso, en ese orden."""

        self._cambiar(timezone.now() - timedelta(days=2), plaza=self.otra_plaza, motivo="Convivencia")
        self._cambiar(timezone.now() - timedelta(days=1), plaza=self.plaza_otro_sector, motivo="Salud")
        egresar_persona(
            estadia=self.estadia,
            usuario=self.operador,
            fecha_egreso=timezone.now() - timedelta(hours=1),
            motivo_egreso=self.alta,
            destino="Domicilio",
        )
        self.estadia.refresh_from_db()

    def test_refleja_todos_los_movimientos_del_mas_nuevo_al_mas_viejo(self):
        self._recorrido_completo()

        respuesta = self._get()

        self.assertEqual(respuesta.status_code, 200)
        titulos = [evento["titulo"] for evento in respuesta.context["eventos"]]
        self.assertEqual(titulos, ["Egreso", "Cambio de sector", "Cambio de plaza", "Ingreso"])
        tabla = [fila["tipo"] for fila in respuesta.context["movimientos_page"]]
        self.assertEqual(tabla, titulos)
        plazas = [fila["plaza"] for fila in respuesta.context["movimientos_page"]]
        self.assertEqual(
            plazas,
            ["Mujeres · M1", "Varones · P2 → Mujeres · M1", "P1 → P2", "Varones · P1"],
            "un cambio dentro del mismo sector no repite el sector, como la línea de tiempo",
        )
        self.assertEqual(respuesta.context["n_movimientos"], 4)
        detalles = [evento["detalle"] for evento in respuesta.context["eventos"]]
        self.assertEqual(
            detalles,
            [
                "motivo: Alta",
                "Varones · P2 → Mujeres · M1 · motivo: Salud",
                "P1 → P2 · motivo: Convivencia",
                "plaza Varones · P1",
            ],
        )
        # Y en el HTML, en ese mismo orden.
        html = respuesta.content.decode()
        posiciones = [
            html.index(texto)
            for texto in ("motivo: Alta", "motivo: Salud", "motivo: Convivencia", "plaza Varones · P1")
        ]
        self.assertEqual(posiciones, sorted(posiciones))

    def test_la_linea_de_tiempo_es_la_del_servicio_de_movimientos(self):
        """Una sola fuente: si los movimientos no salen de `linea_de_tiempo`, la pantalla queda vacía."""

        with mock.patch.object(
            estadia_detalle, "linea_de_tiempo", return_value=MovimientoEstadia.objects.none()
        ) as fuente:
            datos = detalle_de_estadia(self.estadia)

        fuente.assert_called_once()
        self.assertEqual(datos["eventos"], [])

    def test_recorta_a_los_ultimos_diez_y_el_contador_es_el_total(self):
        inicio = self.ingreso + timedelta(hours=1)
        destinos = (self.otra_plaza, self.plaza)
        for numero in range(TOPE_EVENTOS + 1):
            self._cambiar(inicio + timedelta(hours=numero), plaza=destinos[numero % 2], motivo=f"Movida {numero}")

        respuesta = self._get()

        eventos = respuesta.context["eventos"]
        self.assertEqual(len(eventos), TOPE_EVENTOS)
        self.assertIn(f"Movida {TOPE_EVENTOS}", eventos[0]["detalle"], "el primero es el más nuevo")
        self.assertEqual(respuesta.context["n_movimientos"], TOPE_EVENTOS + 2)
        self.assertEqual(len(list(respuesta.context["movimientos_page"])), TOPE_EVENTOS + 2)
        self.assertContains(respuesta, f"Ver los {TOPE_EVENTOS + 2} movimientos")

    def test_la_plaza_actual_dice_desde_cuando_segun_los_movimientos(self):
        cambio = (timezone.now() - timedelta(days=1)).replace(second=0, microsecond=0)
        self._cambiar(cambio)

        respuesta = self._get()

        plaza = next(s for s in respuesta.context["secciones"] if s["codigo"] == "plaza")
        campos = {c["etiqueta"]: c["valor"] for c in plaza["campos"]}
        self.assertEqual(campos["Plaza"], "P2")
        self.assertEqual(campos["Desde"], timezone.localtime(cambio).strftime("%d/%m/%Y %H:%M"))
        self.assertEqual(respuesta.context["estadia"]["dias"], self.estadia.dias_de_permanencia())


class CambioDePlazaPantallaTests(BaseDetalle):
    def setUp(self):
        super().setUp()
        self.url_cambio = reverse("dispositivos:cambiar_plaza", args=[self.cis.pk, self.estadia.pk])

    def _post(self, usuario=None, **cambios):
        datos = {
            "plaza": self.otra_plaza.pk,
            "momento": timezone.localtime().strftime(FORMATO),
            "motivo": "Convivencia",
        }
        datos.update(cambios)
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(usuario or self.operador)
        cliente.cookies[settings.CSRF_COOKIE_NAME] = TOKEN_CSRF
        return cliente.post(
            self.url_cambio, datos, headers={"x-requested-with": "XMLHttpRequest", "x-csrftoken": TOKEN_CSRF}
        )

    def _sin_cambios(self):
        self.estadia.refresh_from_db()
        self.assertEqual(self.estadia.plaza_id, self.plaza.pk)
        self.assertEqual(list(self.estadia.movimientos.values_list("tipo", flat=True)), [Tipo.INGRESO])

    def test_cambia_de_plaza_y_vuelve_al_detalle(self):
        respuesta = self._post(motivo="  Convivencia  ")

        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        self.assertEqual(respuesta.json()["redirect"], self.url)
        self.estadia.refresh_from_db()
        self.assertEqual(self.estadia.plaza, self.otra_plaza)
        movimiento = self.estadia.movimientos.get(tipo=Tipo.CAMBIO_PLAZA)
        self.assertEqual((movimiento.motivo, movimiento.responsable), ("Convivencia", self.operador))

    def test_sin_csrf_no_cambia(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.operador)

        respuesta = cliente.post(self.url_cambio, {"plaza": self.otra_plaza.pk, "motivo": "x"})

        self.assertEqual(respuesta.status_code, 403)
        self._sin_cambios()

    def test_una_plaza_ocupada_no_se_ofrece_ni_se_acepta(self):
        ingresar_persona(
            ciudadano=self.otra_persona, dispositivo=self.cis, plaza=self.otra_plaza, usuario=self.operador
        )

        respuesta = self._post()

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("plaza", respuesta.json()["errors"])
        self._sin_cambios()

    def test_la_plaza_tomada_despues_de_abrir_el_modal_la_rechaza_el_servicio(self):
        """El modal ofreció la plaza libre y otro operador la tomó: decide `cambiar_plaza`, con la fila bloqueada."""

        libre = [{"sector": self.sector, "plazas": [{"pk": self.otra_plaza.pk, "codigo": "P2", "disponible": True}]}]
        ingresar_persona(
            ciudadano=self.otra_persona, dispositivo=self.cis, plaza=self.otra_plaza, usuario=self.operador
        )

        with mock.patch("programas.views.dispositivos_legajo._sectores_para_cambio", return_value=libre):
            respuesta = self._post()

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("estadía activa", respuesta.json()["errors"]["plaza"][0])
        self._sin_cambios()

    def test_sin_admitir_no_cambia_aunque_tenga_todo_lo_demas(self):
        usuario = self._operador("Sin admitir", self.cis, _menos("dispositivo.admitir"))

        respuesta = self._post(usuario)

        self.assertEqual(respuesta.status_code, 403)
        self._sin_cambios()

    def test_con_admitir_en_otra_institucion_no_cambia(self):
        usuario = self._operador("Todo en el parador", self.parador, TODO)

        respuesta = self._post(usuario)

        self.assertEqual(respuesta.status_code, 403)
        self._sin_cambios()

    def test_el_motivo_es_obligatorio(self):
        respuesta = self._post(motivo="   ")

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("motivo", respuesta.json()["errors"])
        self._sin_cambios()

    def test_en_el_mismo_minuto_que_el_ultimo_movimiento_se_acepta(self):
        """El `datetime-local` no trae segundos: se compara al minuto y el cambio va en el instante del último."""

        ultimo = (timezone.now() - timedelta(hours=1)).replace(second=40, microsecond=0)
        self._cambiar(ultimo, plaza=self.otra_plaza)

        respuesta = self._post(plaza=self.plaza_otro_sector.pk, momento=timezone.localtime(ultimo).strftime(FORMATO))

        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        movimiento = self.estadia.movimientos.get(tipo=Tipo.CAMBIO_SECTOR)
        self.assertEqual(movimiento.momento, ultimo)

    def test_un_minuto_antes_del_ultimo_movimiento_se_rechaza(self):
        ultimo = (timezone.now() - timedelta(hours=1)).replace(second=40, microsecond=0)
        self._cambiar(ultimo, plaza=self.otra_plaza)

        antes = timezone.localtime(ultimo - timedelta(minutes=1)).strftime(FORMATO)
        respuesta = self._post(plaza=self.plaza_otro_sector.pk, momento=antes)

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("último movimiento", respuesta.json()["errors"]["momento"][0])
        self.assertFalse(self.estadia.movimientos.filter(tipo=Tipo.CAMBIO_SECTOR).exists())

    def test_el_modal_ofrece_solo_las_plazas_libres(self):
        fuera = Plaza.objects.create(
            sector=self.sector, codigo="P9", estado=Plaza.Estado.FUERA_SERVICIO, motivo_fuera_servicio="Rota"
        )

        respuesta = self._get()

        ofrecidas = {
            valor
            for _grupo, opciones in respuesta.context["form_cambio"].fields["plaza"].choices[1:]
            for valor, _ in opciones
        }
        self.assertEqual(ofrecidas, {self.otra_plaza.pk, self.plaza_otro_sector.pk})
        self.assertNotIn(fuera.pk, ofrecidas)
        self.assertNotIn(self.plaza.pk, ofrecidas, "la plaza en la que ya está no es libre")


class AccionesOcultasTests(BaseDetalle):
    def test_sin_admitir_no_se_ofrece_cambiar_plaza(self):
        usuario = self._operador("Sin admitir", self.cis, _menos("dispositivo.admitir"))

        respuesta = self._get(usuario)

        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, "Cambiar plaza")
        self.assertNotContains(respuesta, reverse("dispositivos:cambiar_plaza", args=[self.cis.pk, self.estadia.pk]))
        self.assertContains(respuesta, "Egresar")

    def test_sin_egresar_no_se_ofrece_el_egreso(self):
        usuario = self._operador("Sin egresar", self.cis, _menos("dispositivo.egresar"))

        respuesta = self._get(usuario)

        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, ">Egresar<")
        self.assertNotContains(respuesta, reverse("dispositivos:egresar", args=[self.cis.pk, self.estadia.pk]))
        self.assertContains(respuesta, "Cambiar plaza")

    def test_con_todo_se_ofrecen_las_dos(self):
        respuesta = self._get()

        self.assertContains(respuesta, "Cambiar plaza")
        self.assertContains(respuesta, ">Egresar<")
        self.assertContains(respuesta, reverse("dispositivos:egresar", args=[self.cis.pk, self.estadia.pk]))

    def test_una_estadia_cerrada_no_ofrece_ninguna_y_dice_que_egreso(self):
        egresar_persona(estadia=self.estadia, usuario=self.operador, motivo_egreso=self.alta, destino="Domicilio")

        respuesta = self._get()

        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, "Cambiar plaza")
        self.assertNotContains(respuesta, ">Egresar<")
        self.assertContains(respuesta, "Estadía cerrada")

    def test_las_observaciones_del_egreso_no_se_muestran(self):
        """Texto libre sin nivel de sensibilidad: no va a la pantalla, como en la trayectoria del legajo."""

        egresar_persona(
            estadia=self.estadia,
            usuario=self.operador,
            motivo_egreso=self.alta,
            destino="Domicilio",
            motivo="Dato privado de la persona",
        )

        self.assertNotContains(self._get(), "Dato privado de la persona")

    def test_sin_motivo_del_catalogo_las_observaciones_tampoco_se_muestran(self):
        """El caso que el de arriba no cubre: egreso sin motivo del catálogo.

        Así lo guardaba `egresar_persona` antes y así reconstruyó la migración 0089 los
        egresos viejos: el texto libre en `MovimientoEstadia.motivo`. Se arma ese movimiento
        tal cual, sin pasar por el servicio, para probar la guarda de la pantalla.
        """

        privado = "Dato privado de la persona"
        ahora = timezone.now()
        Estadia.objects.filter(pk=self.estadia.pk).update(
            estado=Estadia.Estado.EGRESADA, fecha_egreso=ahora, clave_alojamiento=None, motivo_egreso=privado
        )
        self.estadia.refresh_from_db()
        registrar_movimiento(
            estadia=self.estadia,
            tipo=Tipo.EGRESO,
            momento=ahora,
            responsable=self.operador,
            motivo=privado,
            plaza_origen=self.plaza,
        )

        respuesta = self._get()

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Egreso")
        self.assertNotContains(respuesta, privado)

    def test_el_egreso_sin_motivo_del_catalogo_no_copia_las_observaciones_al_movimiento(self):
        egresar_persona(
            estadia=self.estadia, usuario=self.operador, destino="Domicilio", motivo="Dato privado de la persona"
        )

        movimiento = self.estadia.movimientos.get(tipo=Tipo.EGRESO)
        self.assertEqual(movimiento.motivo, "")
        self.estadia.refresh_from_db()
        self.assertEqual(
            self.estadia.motivo_egreso, "Dato privado de la persona", "las observaciones siguen en la estadía"
        )


class PantallaTests(BaseDetalle):
    def test_la_pantalla_no_repite_ids(self):
        """Los dos modales tienen un campo `motivo`: sin `auto_id` propio saldrían dos `id_motivo`."""

        html = self._get().content.decode()
        repetidos = [i for i, n in Counter(re.findall(r'\sid="([^"]+)"', html)).items() if n > 1]

        self.assertEqual(repetidos, [])
        self.assertIn('id="cambio_motivo"', html)
        self.assertIn('id="id_motivo"', html)

    def test_eyebrow_con_la_ubicacion_y_modal_de_egreso_con_la_persona(self):
        respuesta = self._get()

        self.assertContains(respuesta, "Centro integrador · Varones · plaza P1")
        self.assertContains(respuesta, f"Registrar egreso de {self.persona.nombre_completo}")
        self.assertContains(respuesta, "Ingreso ")
        self.assertContains(respuesta, " · plaza P1 · 3 días de permanencia")

    def test_sin_plazas_libres_no_se_ofrece_cambiar_plaza(self):
        ingresar_persona(
            ciudadano=self.otra_persona, dispositivo=self.cis, plaza=self.otra_plaza, usuario=self.operador
        )
        tercera = self.persona.__class__.objects.create(dni="30555666", nombre="Rosa", apellido="Díaz")
        ingresar_persona(ciudadano=tercera, dispositivo=self.cis, plaza=self.plaza_otro_sector, usuario=self.operador)

        respuesta = self._get()

        self.assertNotContains(respuesta, "Cambiar plaza")
        self.assertContains(respuesta, ">Egresar<")

    def test_el_total_de_otras_estadias_se_dice_en_total(self):
        for numero in range(7):
            Estadia.objects.create(
                ciudadano=self.persona,
                dispositivo=self.parador,
                fecha_ingreso=self.ingreso - timedelta(days=60 - numero * 5),
                fecha_egreso=self.ingreso - timedelta(days=58 - numero * 5),
                estado=Estadia.Estado.EGRESADA,
            )

        self.assertContains(self._get(), "Ver la trayectoria completa (7 en total)")


class EgresoDesdeLaEstadiaTests(BaseDetalle):
    """El modal de P7 postea al egreso de siempre y pide volver a la estadía con una clave, no con una URL."""

    def _egresar(self, **extra):
        datos = {
            "fecha_egreso": timezone.localtime().strftime(FORMATO),
            "motivo": self.alta.pk,
            "destino": "Domicilio",
            "observaciones": "",
        }
        datos.update(extra)
        url = reverse("dispositivos:egresar", args=[self.cis.pk, self.estadia.pk])
        return self._cliente().post(url, datos, headers={"x-requested-with": "XMLHttpRequest"})

    def test_con_volver_estadia_vuelve_a_la_pantalla_de_la_estadia(self):
        respuesta = self._egresar(volver="estadia")

        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        self.assertEqual(respuesta.json()["redirect"], self.url)

    def test_sin_volver_va_a_personas_alojadas_como_siempre(self):
        respuesta = self._egresar()

        self.assertEqual(respuesta.json()["redirect"], url_solapa_estadias(self.cis.pk))

    def test_un_valor_que_no_es_la_clave_no_redirige_afuera(self):
        """Sin AJAX y con un dato inválido, el egreso se rechaza y redirige a `volver`: ahí se ve el destino.

        Así se prueban varios valores sin cerrar la estadía en cada uno.
        """

        lista = url_solapa_estadias(self.cis.pk)
        url = reverse("dispositivos:egresar", args=[self.cis.pk, self.estadia.pk])
        cliente = self._cliente()
        for malicioso in ("https://evil.example/robar", "//evil.example", "/admin/", "estadia/../../x", ""):
            with self.subTest(malicioso=malicioso):
                respuesta = cliente.post(url, {"motivo": "", "volver": malicioso})
                self.assertEqual(respuesta.status_code, 302)
                self.assertEqual(respuesta["Location"], lista)
        respuesta = cliente.post(url, {"motivo": "", "volver": "estadia"})
        self.assertEqual(respuesta["Location"], self.url)
        self.estadia.refresh_from_db()
        self.assertTrue(self.estadia.activa)

    def test_la_pantalla_de_la_estadia_manda_la_clave(self):
        self.assertContains(self._get(), '<input type="hidden" name="volver" value="estadia">')


@tag("performance")
class EstadiaDetallePresupuestoTests(BaseDetalle):
    """El detalle no puede crecer con los movimientos ni con las otras estadías de la persona.

    El presupuesto del selector vive en `scripts/perf_budgets.json` (sección `servicios`);
    la pantalla entera se mide además contra sí misma, con poca y con mucha historia.
    """

    def _presupuesto(self):
        return json.loads(PRESUPUESTOS.read_text(encoding="utf-8"))["servicios"][CLAVE_PRESUPUESTO]["consultas_fijas"]

    def _estadia_anterior(self, numero):
        Estadia.objects.create(
            ciudadano=self.persona,
            dispositivo=self.parador if numero % 2 else self.cis,
            plaza=self.plaza_parador if numero % 2 else self.plaza,
            fecha_ingreso=self.ingreso - timedelta(days=60 - numero * 5),
            fecha_egreso=self.ingreso - timedelta(days=58 - numero * 5),
            estado=Estadia.Estado.EGRESADA,
        )

    def _sumar_historia(self):
        inicio = self.ingreso + timedelta(hours=1)
        destinos = (self.otra_plaza, self.plaza_otro_sector, self.plaza)
        for numero in range(14):
            self._cambiar(inicio + timedelta(hours=numero), plaza=destinos[numero % 3], motivo=f"Movida {numero}")
        for numero in range(1, 8):
            self._estadia_anterior(numero)

    def _medir(self, cliente):
        estadia = Estadia.objects.select_related(
            "ciudadano", "dispositivo", "plaza__sector", "motivo", "ingresada_por", "egresada_por"
        ).get(pk=self.estadia.pk)
        with CaptureQueriesContext(connection) as selector:
            detalle_de_estadia(estadia)
        # Se cuenta acá y no al final: `len()` relee `connection.queries`, y el próximo
        # request lo vacía (`reset_queries`), así que contado después daría cero.
        consultas_selector = len(selector)
        cliente.get(self.url)  # calienta la sesión y las cachés del shell
        with CaptureQueriesContext(connection) as pantalla:
            self.assertEqual(cliente.get(self.url).status_code, 200)
        return consultas_selector, len(pantalla)

    def test_el_costo_no_crece_con_la_historia(self):
        techo = self._presupuesto()
        self._estadia_anterior(0)  # con una sola otra estadía ya se paga la consulta de la lista
        cliente = self._cliente()
        selector_corto, pantalla_corta = self._medir(cliente)
        self._sumar_historia()
        selector_largo, pantalla_larga = self._medir(cliente)

        self.assertGreater(selector_corto, 0, "la medición tiene que ver las consultas del selector")
        for medida in (selector_corto, selector_largo):
            self.assertLessEqual(
                medida,
                techo,
                f"{medida} consultas; el presupuesto de «{CLAVE_PRESUPUESTO}» en scripts/perf_budgets.json es "
                f"{techo}. Subirlo exige justificarlo en el mismo PR.",
            )
        self.assertEqual(
            pantalla_larga, pantalla_corta, "la pantalla no puede pagar una consulta por movimiento o estadía"
        )


class IntegracionConElDetalleDelDispositivoTests(BaseDetalle):
    """P4 abre P7 desde la fila de la estadía, y P7 vuelve a la solapa Estadías de P4."""

    def _p4(self, usuario=None):
        return self._get(usuario, reverse("dispositivos:detalle", args=[self.cis.pk]) + "?tab=estadias")

    def test_la_fila_de_p4_abre_la_estadia(self):
        respuesta = self._p4()

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, f'href="{self.url}"')
        self.assertContains(respuesta, f"Ver estadía de {self.persona.nombre_completo}")

    def test_sin_ciudadano_ver_la_fila_no_ofrece_la_estadia(self):
        usuario = self._operador("Sin ciudadano", self.cis, _menos("ciudadano.ver"))

        respuesta = self._p4(usuario)

        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, f'href="{self.url}"')

    def test_p7_vuelve_a_la_solapa_estadias(self):
        respuesta = self._get()

        destino = url_solapa_estadias(self.cis.pk)
        self.assertEqual(respuesta.context["url_volver"], destino)
        self.assertEqual(respuesta.context["migas"][2], {"label": "Estadías", "url": destino})
