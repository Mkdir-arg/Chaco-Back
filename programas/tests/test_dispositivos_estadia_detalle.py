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
from programas.tests.test_dispositivos_estadias import BaseEstadias

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
