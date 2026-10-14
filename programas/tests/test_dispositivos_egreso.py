"""Egreso con catálogo de motivos y liberación de la plaza (MVP v2, etapa 2 · #691).

Lo que se verifica, y por qué:

1. **El servicio** cierra la estadía con un motivo *del catálogo*, un destino y las
   pertenencias, y rechaza un motivo dado de baja.
2. **La plaza queda libre en el acto** y lo dice el servicio de ocupación, no una cuenta de
   la vista.
3. **La pantalla** muta solo por POST con CSRF, respeta el alcance por dispositivo y
   devuelve los errores en la forma que espera el modal (`{campo: [mensajes]}`). La lista
   de personas y el modal viven en la solapa Estadías del detalle del dispositivo (P4): es
   la única lista de personas, y después de egresar se vuelve a esa solapa.
4. **El catálogo se amplía sin tocar código**: está en el admin, y la migración solo
   siembra los seis que nombra el mockup.
"""

import importlib
from datetime import timedelta
from unittest import mock

from django.apps import apps
from django.conf import settings
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from programas.models import Estadia, MotivoEgreso, TrazaDispositivo
from programas.services.estadias import cambiar_plaza, egresar_persona, ingresar_persona
from programas.services.ocupacion import ocupacion_de_plazas
from programas.tests.test_dispositivos_estadias import BaseEstadias

FORMATO = "%Y-%m-%dT%H:%M"
TOKEN_CSRF = "a" * 32


class BaseEgreso(BaseEstadias):
    def setUp(self):
        super().setUp()
        self.alta = self.motivo_alta
        self.baja = MotivoEgreso.objects.create(codigo="viejo", nombre="Motivo viejo", activo=False)
        self.ingreso = timezone.now() - timedelta(days=2)
        self.estadia = ingresar_persona(
            ciudadano=self.persona,
            dispositivo=self.cis,
            plaza=self.plaza,
            usuario=self.operador_cis,
            fecha_ingreso=self.ingreso,
        )


class EgresoServicioTests(BaseEgreso):
    def test_guarda_motivo_destino_y_pertenencias(self):
        egresar_persona(
            estadia=self.estadia,
            usuario=self.operador_cis,
            motivo="Se fue con la familia",
            motivo_egreso=self.alta,
            destino="Domicilio de familiar",
            pertenencias_devueltas=True,
        )

        self.estadia.refresh_from_db()
        self.assertEqual(self.estadia.estado, Estadia.Estado.EGRESADA)
        self.assertEqual(self.estadia.motivo, self.alta)
        self.assertEqual(self.estadia.destino_egreso, "Domicilio de familiar")
        self.assertEqual(self.estadia.motivo_egreso, "Se fue con la familia")
        self.assertTrue(self.estadia.pertenencias_devueltas)
        traza = TrazaDispositivo.objects.filter(dispositivo=self.cis, accion="ESTADIA_EGRESO").get()
        self.assertIn("motivo: Alta", traza.detalle)

    def test_sin_motivo_del_catalogo_el_servicio_rechaza_el_egreso(self):
        """La obligatoriedad vive en el servicio, no solo en `EgresoForm` (carril C3).

        Era el pendiente del Cambio 269 y el mismo patrón que la revisión del Cambio 262
        marcó como trampa: una regla que depende de que la vista se acuerde no es una
        regla. El historial no puede perder la razón de un egreso.
        """

        with self.assertRaises(ValidationError) as error:
            egresar_persona(estadia=self.estadia, usuario=self.operador_cis, destino="X")

        self.assertIn("motivo", error.exception.message_dict)
        self.estadia.refresh_from_db()
        self.assertTrue(self.estadia.activa, "la estadía no se cierra")
        self.assertFalse(self.estadia.movimientos.filter(tipo="EGRESO").exists())

    def test_las_observaciones_libres_no_sustituyen_al_motivo(self):
        """`motivo` es texto libre de observaciones y no es una opción del catálogo."""

        with self.assertRaises(ValidationError):
            egresar_persona(estadia=self.estadia, usuario=self.operador_cis, motivo="Se fue por su cuenta")

        self.estadia.refresh_from_db()
        self.assertTrue(self.estadia.activa)

    def test_un_motivo_dado_de_baja_se_rechaza_y_no_cierra_nada(self):
        with self.assertRaises(ValidationError) as error:
            egresar_persona(estadia=self.estadia, usuario=self.operador_cis, motivo_egreso=self.baja, destino="X")

        self.assertIn("motivo", error.exception.message_dict)
        self.estadia.refresh_from_db()
        self.assertTrue(self.estadia.activa)

    def test_la_plaza_queda_disponible_inmediatamente(self):
        antes = ocupacion_de_plazas(self.cis).de(self.cis).conteo
        self.assertEqual(antes.ocupadas, 1)

        egresar_persona(estadia=self.estadia, usuario=self.operador_cis, motivo_egreso=self.alta, destino="X")

        despues = ocupacion_de_plazas(self.cis).de(self.cis).conteo
        self.assertEqual(despues.ocupadas, 0)
        self.assertEqual(despues.disponibles, antes.disponibles + 1)

    def test_el_egreso_no_puede_ser_anterior_al_ingreso(self):
        with self.assertRaises(ValidationError) as error:
            egresar_persona(
                estadia=self.estadia,
                usuario=self.operador_cis,
                fecha_egreso=self.ingreso - timedelta(hours=1),
                motivo_egreso=self.alta,
            )
        self.assertIn("fecha_egreso", error.exception.message_dict)


class EgresoPantallaTests(BaseEgreso):
    def setUp(self):
        super().setUp()
        self.url = reverse("dispositivos:egresar", args=[self.cis.pk, self.estadia.pk])
        self.cliente = Client(enforce_csrf_checks=True)
        self.cliente.force_login(self.operador_cis)

    def _post(self, cliente=None, **cambios):
        datos = {
            "fecha_egreso": timezone.localtime().strftime(FORMATO),
            "motivo": self.alta.pk,
            "destino": "Domicilio de familiar",
            "observaciones": "",
            "pertenencias_devueltas": "on",
        }
        datos.update(cambios)
        cliente = cliente or self.cliente
        token = self._csrf(cliente)
        return cliente.post(self.url, datos, headers={"x-requested-with": "XMLHttpRequest", "x-csrftoken": token})

    @staticmethod
    def _csrf(cliente):
        """Un token de 32 caracteres en la cookie, que Django acepta como secreto sin enmascarar."""

        cliente.cookies[settings.CSRF_COOKIE_NAME] = TOKEN_CSRF
        return TOKEN_CSRF

    def test_egresa_por_post_y_libera_la_plaza(self):
        respuesta = self._post()

        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        self.assertTrue(respuesta.json()["ok"])
        # Vuelve a la solapa desde la que se egresó, no a la de por defecto del detalle.
        self.assertEqual(
            respuesta.json()["redirect"], reverse("dispositivos:detalle", args=[self.cis.pk]) + "?tab=estadias"
        )
        self.estadia.refresh_from_db()
        self.assertEqual(self.estadia.estado, Estadia.Estado.EGRESADA)
        self.assertEqual(self.estadia.egresada_por, self.operador_cis)
        self.assertEqual(ocupacion_de_plazas(self.cis).de(self.cis).conteo.ocupadas, 0)

    def test_un_get_no_muta_nada(self):
        respuesta = self.cliente.get(self.url)

        self.assertEqual(respuesta.status_code, 405)
        self.estadia.refresh_from_db()
        self.assertTrue(self.estadia.activa)

    def test_egreso_en_el_mismo_minuto_del_cambio_de_plaza_desde_p4(self):
        """P4 envía solo el minuto: el egreso debe conservar el instante del último movimiento."""

        ultimo = (timezone.now() - timedelta(hours=1)).replace(second=45, microsecond=0)
        cambiar_plaza(
            estadia=self.estadia,
            plaza=self.otra_plaza,
            usuario=self.operador_cis,
            motivo="Convivencia",
            momento=ultimo,
        )

        respuesta = self._post(fecha_egreso=timezone.localtime(ultimo).strftime(FORMATO))

        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        self.assertTrue(respuesta.json()["ok"])
        self.assertEqual(
            respuesta.json()["redirect"], reverse("dispositivos:detalle", args=[self.cis.pk]) + "?tab=estadias"
        )
        self.estadia.refresh_from_db()
        self.assertEqual(self.estadia.estado, Estadia.Estado.EGRESADA)
        self.assertEqual(self.estadia.fecha_egreso, ultimo)
        self.assertEqual(self.estadia.movimientos.get(tipo="EGRESO").momento, ultimo)
        self.assertEqual(ocupacion_de_plazas(self.cis).de(self.cis).conteo.ocupadas, 0)

    def test_sin_csrf_no_egresa(self):
        self.cliente.cookies[settings.CSRF_COOKIE_NAME] = TOKEN_CSRF
        respuesta = self.cliente.post(self.url, {"motivo": self.alta.pk})

        self.assertEqual(respuesta.status_code, 403)
        self.estadia.refresh_from_db()
        self.assertTrue(self.estadia.activa)

    def test_el_motivo_es_obligatorio_y_sale_en_el_campo(self):
        respuesta = self._post(motivo="")

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("motivo", respuesta.json()["errors"])
        self.estadia.refresh_from_db()
        self.assertTrue(self.estadia.activa)

    def test_un_motivo_dado_de_baja_no_se_ofrece_ni_se_acepta(self):
        respuesta = self._post(motivo=self.baja.pk)

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("motivo", respuesta.json()["errors"])

    def test_fecha_futura_se_rechaza(self):
        futura = (timezone.localtime() + timedelta(days=1)).strftime(FORMATO)
        respuesta = self._post(fecha_egreso=futura)

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("fecha_egreso", respuesta.json()["errors"])

    def test_fecha_anterior_al_ingreso_se_rechaza(self):
        antes = (timezone.localtime(self.ingreso) - timedelta(hours=2)).strftime(FORMATO)
        respuesta = self._post(fecha_egreso=antes)

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("anterior al último movimiento", respuesta.json()["errors"]["fecha_egreso"][0])

    def test_una_estadia_ya_cerrada_va_al_error_general(self):
        self.assertEqual(self._post().status_code, 200)
        respuesta = self._post()

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("__all__", respuesta.json()["errors"])

    def test_sin_alcance_sobre_el_dispositivo_no_egresa(self):
        otro = Client(enforce_csrf_checks=True)
        otro.force_login(self.operador_parador)

        respuesta = self._post(cliente=otro)

        self.assertEqual(respuesta.status_code, 403)
        self.estadia.refresh_from_db()
        self.assertTrue(self.estadia.activa)

    def test_la_vista_corta_sin_alcance_antes_de_llamar_al_servicio(self):
        """La guarda de la vista, sola: el servicio repite el chequeo y escondería que falta."""

        otro = Client(enforce_csrf_checks=True)
        otro.force_login(self.operador_parador)

        with mock.patch("programas.views.dispositivos_legajo.egresar_persona") as servicio:
            respuesta = self._post(cliente=otro)

        self.assertEqual(respuesta.status_code, 403)
        servicio.assert_not_called()

    def test_la_estadia_tiene_que_ser_del_dispositivo_de_la_url(self):
        url = reverse("dispositivos:egresar", args=[self.parador.pk, self.estadia.pk])
        otro = Client(enforce_csrf_checks=True)
        otro.force_login(self.operador_parador)
        token = self._csrf(otro)

        respuesta = otro.post(url, {"motivo": self.alta.pk}, headers={"x-csrftoken": token})

        self.assertEqual(respuesta.status_code, 404)

    def test_egresar_en_el_mismo_minuto_del_ingreso_no_se_rechaza(self):
        """El `datetime-local` pierde los segundos; el ingreso los trae."""

        # Cinco minutos atras y con segundo 30: inequivocamente pasado, corra cuando corra el test.
        ingreso = (timezone.now() - timedelta(minutes=5)).replace(second=30, microsecond=0)
        Estadia.objects.filter(pk=self.estadia.pk).update(fecha_ingreso=ingreso)
        # El input datetime-local manda el minuto del ingreso, o sea segundo 00: 30 s antes.
        respuesta = self._post(fecha_egreso=timezone.localtime(ingreso).strftime(FORMATO))

        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        cerrada = Estadia.objects.get(pk=self.estadia.pk)
        self.assertEqual(cerrada.fecha_egreso, ingreso)
        self.assertEqual(cerrada.estado, Estadia.Estado.EGRESADA)
        self.assertGreaterEqual(cerrada.fecha_egreso, cerrada.fecha_ingreso)

    def _detalle(self, cliente=None, *, egreso=False):
        parametros = {"tab": "estadias"}
        if egreso:
            parametros["egreso"] = self.estadia.pk
        return (cliente or self.cliente).get(reverse("dispositivos:detalle", args=[self.cis.pk]), parametros)

    def test_el_modal_se_abre_con_un_formulario_nuevo_sin_datos_del_post_anterior(self):
        """La acción GET por fila abre un formulario fresco, como los modales de P21."""

        self._post(destino="Destino anterior", fecha_egreso="roto")
        html = self._detalle(egreso=True).content.decode()

        self.assertIn('x-ref="form"', html)
        self.assertNotIn("Destino anterior", html)
        self.assertIn("modalEgreso: true", html)
        self.assertIn("data-ajax", html)
        self.assertIn('x-becas-modal="modalEgreso"', html)

    def test_la_solapa_estadias_ofrece_el_egreso_con_la_capacidad(self):
        respuesta = self._detalle(egreso=True)

        self.assertContains(respuesta, "Acciones de estadía de Ana Gómez")
        self.assertContains(respuesta, 'aria-labelledby="modal-egreso-titulo"')
        self.assertContains(respuesta, self.url)
        self.assertContains(respuesta, "Alta")
        self.assertNotContains(respuesta, "Motivo viejo")

    def test_sin_la_capacidad_de_egresar_no_hay_boton_ni_modal(self):
        """Ve el dispositivo y opera el resto, pero sin `dispositivo.egresar`: ni botón ni modal."""

        self.assertContains(self._detalle(egreso=True), self.url)  # el caso positivo, en el mismo estado
        sin_egresar = self._operador("Sin egresar", self.cis, ("dispositivo.ver", "dispositivo.admitir"))
        cliente = Client()
        cliente.force_login(sin_egresar)

        respuesta = self._detalle(cliente)

        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, self.url)
        self.assertNotContains(respuesta, "Registrar egreso de Ana Gómez")
        self.assertNotContains(respuesta, 'aria-labelledby="modal-egreso-titulo"')

    def test_una_estadia_egresada_no_ofrece_egresar_otra_vez(self):
        self.assertEqual(self._post().status_code, 200)

        respuesta = self.cliente.get(
            reverse("dispositivos:detalle", args=[self.cis.pk]), {"tab": "estadias", "estado": "TODAS"}
        )

        self.assertContains(respuesta, "Egresada")
        self.assertNotContains(respuesta, self.url)

    def test_el_modal_muestra_la_permanencia_de_la_persona(self):
        """Ingresó hace dos días (`BaseEgreso`): el modal lo dice antes de confirmar."""

        self.assertContains(self._detalle(egreso=True), "2 días de permanencia")

    def test_la_ruta_vieja_de_personas_alojadas_lleva_a_la_solapa(self):
        respuesta = self.cliente.get(reverse("dispositivos:estadias", args=[self.cis.pk]))

        self.assertRedirects(
            respuesta,
            reverse("dispositivos:detalle", args=[self.cis.pk]) + "?tab=estadias",
            fetch_redirect_response=False,
        )


class CatalogoDeMotivosTests(BaseEgreso):
    def test_se_amplia_desde_el_admin_sin_tocar_codigo(self):
        self.assertIn(MotivoEgreso, admin.site._registry)

    def test_el_admin_no_permite_borrar_un_motivo_con_historia(self):
        modelo_admin = admin.site._registry[MotivoEgreso]
        self.assertFalse(modelo_admin.has_delete_permission(None, self.alta))

    def test_la_migracion_siembra_solo_los_seis_del_mockup(self):
        MotivoEgreso.objects.all().delete()
        migracion = importlib.import_module("programas.migrations.0088_motivo_egreso_catalogo")

        migracion.sembrar_motivos(apps, None)
        migracion.sembrar_motivos(apps, None)  # idempotente

        self.assertEqual(
            list(MotivoEgreso.objects.values_list("nombre", flat=True)),
            ["Alta", "Alta con derivación", "Abandono", "Traslado", "Fallecimiento", "Otro"],
        )
