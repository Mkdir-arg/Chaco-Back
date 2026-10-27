"""Acciones del mapa de plazas (MVP v2 · P5) y las alertas de P4 que resuelven.

Lo que se fija acá, y por qué:

1. **Cada plaza ofrece las acciones que su situación admite** (la disponible, tres), y las decide el
   estado que dibuja `ocupacion.estado_de_plazas` —la fuente única— más un segundo hecho:
   si queda una reserva **sin liberar**. Sin ese segundo hecho, la plaza de la alerta
   «Préstamo vencido sin liberar» sale Disponible y la única acción que ofrecería sería
   sacarla de servicio, que no resuelve nada.
2. **La capacidad decide si la celda es enlace**, con alcance al dispositivo: liberar pide
   `dispositivo.admitir`, sacar y reponer piden `dispositivo.editar`.
3. **Ajena, inexistente, de un sector dado de baja y sin capacidad dan lo mismo**: ni el
   modal ni el POST distinguen los cuatro casos, que juntos serían un oráculo de ids.
4. **La alerta de P4 desaparece sola** al ejecutar la acción desde la pantalla: de punta a
   punta, alerta presente → acción → alerta ausente.
5. **Consultas fijas**: el mapa cuesta lo mismo con un sector que con ocho (Cambio 272).
"""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from django.conf import settings
from django.db import connection
from django.test import tag
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from programas.models import MovimientoEstadia, Plaza, ReservaPlaza, Sector
from programas.services.detalle_dispositivo import alertas_del_dispositivo
from programas.services.estadias import ingresar_persona, reservar_plaza, sacar_plaza_de_servicio
from programas.services.ocupacion import ESTADO_DISPONIBLE, ESTADO_FUERA_SERVICIO, ESTADO_OCUPADA
from programas.services.sectores_plazas import (
    ACCION_FUERA_SERVICIO,
    ACCION_LIBERAR,
    ACCION_PRESTAR,
    ACCION_RESERVAR,
    ACCION_REUBICAR,
    ACCION_VOLVER,
    MOTIVO_PLAZA_OCUPADA,
    MOTIVO_SIN_PLAZAS_LIBRES,
    sectores_con_plazas,
)
from programas.tests.test_dispositivos_estadias import CAPACIDADES_OPERATIVAS, BaseEstadias

PRESUPUESTOS = settings.BASE_DIR / "scripts" / "perf_budgets.json"
CLAVE_PRESUPUESTO = "dispositivos_sectores_con_plazas"

AVISO_NO_GESTIONABLE = "Esa plaza ya no se puede gestionar desde acá."


class BaseMapa(BaseEstadias):
    """El terreno de las estadías más los tres recortes de capacidad que decide P5."""

    def setUp(self):
        super().setUp()
        self.url = reverse("dispositivos:sectores", args=[self.cis.pk])
        # Usuarios con todo menos la condición que cada test prueba.
        self.solo_lectura = self._operador("Solo lectura CIS", self.cis, ("dispositivo.ver",))
        self.sin_editar = self._operador(
            "Sin editar CIS", self.cis, ("dispositivo.ver", "dispositivo.admitir", "dispositivo.egresar")
        )
        self.sin_admitir = self._operador(
            "Sin admitir CIS", self.cis, ("dispositivo.ver", "dispositivo.editar", "dispositivo.egresar")
        )
        # Reservar y prestar buscan a la persona en el padrón: piden `ciudadano.ver` además de `admitir`.
        # `operador_cis` y `sin_editar` admiten pero no ven personas; estos dos sí.
        self.con_personas = self._operador("Con personas CIS", self.cis, (*CAPACIDADES_OPERATIVAS, "ciudadano.ver"))
        self.sin_editar_con_personas = self._operador(
            "Sin editar con personas CIS",
            self.cis,
            ("dispositivo.ver", "dispositivo.admitir", "dispositivo.egresar", "ciudadano.ver"),
        )

    def _celdas(self, respuesta):
        """`{codigo: celda}` de todas las plazas dibujadas."""

        return {celda["codigo"]: celda for item in respuesta.context["sectores"] for celda in item["plazas"]}

    def _pantalla(self, usuario=None, **params):
        self.client.force_login(usuario or self.operador_cis)
        return self.client.get(self.url, params)

    def _reserva_vencida(self, plaza=None, tipo=ReservaPlaza.Tipo.PRESTAMO):
        """Una reserva que venció y nadie liberó: la plaza vuelve a contar como disponible."""

        ahora = timezone.now()
        return ReservaPlaza.objects.create(
            plaza=plaza or self.plaza,
            ciudadano=self.otra_persona,
            tipo=tipo,
            desde=ahora - timedelta(days=1),
            hasta=ahora - timedelta(hours=2),
            creada_por=self.operador_cis,
        )

    def _alertas(self, regla):
        return [
            alerta
            for alerta in alertas_del_dispositivo(self.cis, usuario=self._usuario(self.operador_cis.pk))
            if alerta["regla"] == regla
        ]


class AccionPorPlazaTests(BaseMapa):
    """Qué acción ofrece cada plaza, según su situación."""

    def test_una_plaza_disponible_ofrece_reservar_prestar_y_sacar_de_servicio(self):
        respuesta = self._pantalla()

        celda = self._celdas(respuesta)["P1"]

        self.assertEqual(celda["estado"], ESTADO_DISPONIBLE)
        self.assertEqual(celda["url"], f"?plaza={self.plaza.pk}")
        self.assertEqual(
            self._pantalla(self.con_personas, plaza=self.plaza.pk).context["plaza_accion"]["acciones"],
            [ACCION_RESERVAR, ACCION_PRESTAR, ACCION_FUERA_SERVICIO],
        )

    def test_una_plaza_fuera_de_servicio_se_puede_volver_a_servicio(self):
        sacar_plaza_de_servicio(plaza=self.plaza, usuario=self.operador_cis, motivo="Colchón roto")

        respuesta = self._pantalla(plaza=self.plaza.pk)

        self.assertEqual(self._celdas(respuesta)["P1"]["estado"], ESTADO_FUERA_SERVICIO)
        self.assertEqual(respuesta.context["plaza_accion"]["accion"], ACCION_VOLVER)
        # El motivo viaja al modal desde el estado derivado, no desde una lectura propia.
        self.assertEqual(respuesta.context["plaza_accion"]["estado"].detalle, "Colchón roto")

    def test_una_plaza_reservada_se_puede_liberar(self):
        reservar_plaza(plaza=self.plaza, ciudadano=self.otra_persona, usuario=self.operador_cis)

        respuesta = self._pantalla(plaza=self.plaza.pk)

        self.assertEqual(respuesta.context["plaza_accion"]["accion"], ACCION_LIBERAR)

    def test_la_plaza_de_una_reserva_vencida_ofrece_liberarla_aunque_el_mapa_la_muestre_disponible(self):
        """El caso de la alerta de P4: la plaza ya cuenta como disponible y la reserva sigue abierta.

        Si la acción se decidiera por el estado del mapa —que acá dice Disponible—, lo único
        que P5 ofrecería sería sacarla de servicio, y la alerta no se podría resolver.
        """

        self._reserva_vencida()

        respuesta = self._pantalla(plaza=self.plaza.pk)

        self.assertEqual(self._celdas(respuesta)["P1"]["estado"], ESTADO_DISPONIBLE)
        self.assertEqual(respuesta.context["plaza_accion"]["accion"], ACCION_LIBERAR)

    def test_una_plaza_ocupada_explica_por_que_no_se_puede_sacar_de_servicio(self):
        """Quien solo configura plazas (sin admitir) sigue viendo el aviso: no puede reubicar."""

        ingresar_persona(ciudadano=self.persona, dispositivo=self.cis, usuario=self.operador_cis, plaza=self.plaza)

        respuesta = self._pantalla(self.sin_admitir, plaza=self.plaza.pk)

        self.assertEqual(self._celdas(respuesta)["P1"]["estado"], ESTADO_OCUPADA)
        self.assertEqual(respuesta.context["plaza_accion"]["bloqueo"], MOTIVO_PLAZA_OCUPADA)
        self.assertNotIn("form_plaza", respuesta.context)
        self.assertNotIn("form_cambio", respuesta.context)
        self.assertContains(respuesta, "No se puede sacar de servicio")

    def test_un_sector_dado_de_baja_no_aporta_plazas_ni_acciones(self):
        Sector.objects.filter(pk=self.sector.pk).update(activo=False)

        respuesta = self._pantalla(plaza=self.plaza.pk)

        self.assertEqual(self._celdas(respuesta), {})
        self.assertNotIn("plaza_accion", respuesta.context)


class ReubicarDesdeElMapaTests(BaseMapa):
    """La plaza ocupada ofrece reubicar a quien puede admitir (Cambio 377, revierte en parte el 287)."""

    def setUp(self):
        super().setUp()
        self.estadia = ingresar_persona(
            ciudadano=self.persona, dispositivo=self.cis, usuario=self.operador_cis, plaza=self.plaza
        )
        self.con_ciudadano = self._operador(
            "Con ciudadano CIS", self.cis, ("dispositivo.ver", "dispositivo.admitir", "ciudadano.ver")
        )

    def _post_cambio(self, usuario=None, **datos):
        self.client.force_login(usuario or self.operador_cis)
        cuerpo = {
            "plaza": self.otra_plaza.pk,
            "momento": timezone.localtime().strftime("%Y-%m-%dT%H:%M"),
            "motivo": "Convivencia",
            "volver": "sectores",
        }
        cuerpo.update(datos)
        return self.client.post(reverse("dispositivos:cambiar_plaza", args=[self.cis.pk, self.estadia.pk]), cuerpo)

    def test_con_admitir_la_plaza_ocupada_ofrece_reubicar_con_solo_las_libres(self):
        respuesta = self._pantalla(plaza=self.plaza.pk)

        celda = self._celdas(respuesta)["P1"]
        self.assertEqual(celda["estado"], ESTADO_OCUPADA)
        self.assertEqual(celda["url"], f"?plaza={self.plaza.pk}")
        self.assertEqual(respuesta.context["plaza_accion"]["accion"], ACCION_REUBICAR)
        self.assertEqual(respuesta.context["plaza_accion"]["bloqueo"], "")
        form = respuesta.context["form_cambio"]
        grupos = form.fields["plaza"].choices[1:]
        self.assertEqual([pk for _sector, libres in grupos for pk, _codigo in libres], [self.otra_plaza.pk])
        url = reverse("dispositivos:cambiar_plaza", args=[self.cis.pk, self.estadia.pk])
        self.assertEqual(respuesta.context["url_cambiar_plaza"], url)
        self.assertContains(respuesta, f'action="{url}"')
        self.assertContains(respuesta, '<input type="hidden" name="volver" value="sectores">')
        self.assertContains(respuesta, "Confirmar cambio")

    def test_reubicar_arma_los_sectores_con_el_dispositivo_de_la_vista(self):
        """El mapa de ingreso sale del `dispositivo` ya cargado: con `estadia.dispositivo` (sin su tipo)
        se volvía a leer el tipo de dispositivo, una consulta más que el modal de las otras acciones."""

        self.client.force_login(self.operador_cis)
        consultas = {}
        for nombre, plaza in (("reubicar", self.plaza), ("otra", self.otra_plaza)):
            with CaptureQueriesContext(connection) as capturadas:
                self.client.get(self.url, {"plaza": plaza.pk})
            consultas[nombre] = sum("programas_tipodispositivo" in q["sql"] for q in capturadas)

        self.assertEqual(consultas["reubicar"], consultas["otra"])

    def test_admitir_sin_editar_tambien_reubica(self):
        respuesta = self._pantalla(self.sin_editar, plaza=self.plaza.pk)

        self.assertEqual(respuesta.context["plaza_accion"]["accion"], ACCION_REUBICAR)
        self.assertIn("form_cambio", respuesta.context)

    def test_sin_plazas_libres_avisa_y_no_trae_formulario(self):
        ingresar_persona(
            ciudadano=self.otra_persona, dispositivo=self.cis, usuario=self.operador_cis, plaza=self.otra_plaza
        )

        respuesta = self._pantalla(plaza=self.plaza.pk)

        self.assertEqual(respuesta.context["plaza_accion"]["bloqueo"], MOTIVO_SIN_PLAZAS_LIBRES)
        self.assertNotIn("form_cambio", respuesta.context)
        self.assertContains(respuesta, MOTIVO_SIN_PLAZAS_LIBRES)
        self.assertNotContains(respuesta, "Confirmar cambio")

    def test_con_editar_sin_admitir_sigue_el_aviso_de_hoy(self):
        respuesta = self._pantalla(self.sin_admitir, plaza=self.plaza.pk)

        self.assertEqual(respuesta.context["plaza_accion"]["accion"], ACCION_FUERA_SERVICIO)
        self.assertEqual(respuesta.context["plaza_accion"]["bloqueo"], MOTIVO_PLAZA_OCUPADA)
        self.assertNotIn("form_cambio", respuesta.context)

    def test_sin_admitir_ni_editar_la_plaza_ocupada_no_es_enlace(self):
        respuesta = self._pantalla(self.solo_lectura, plaza=self.plaza.pk)

        self.assertEqual(self._celdas(respuesta)["P1"]["url"], "")
        self.assertNotIn("plaza_accion", respuesta.context)
        self.assertNotIn("form_cambio", respuesta.context)

    def test_el_nombre_de_la_persona_solo_lo_ve_quien_puede_ver_ciudadanos(self):
        sin_nombre = self._pantalla(plaza=self.plaza.pk)
        self.assertEqual(sin_nombre.context["estadia_cambio"].persona_visible, "Persona alojada")
        self.assertNotContains(sin_nombre, "Gómez")

        con_nombre = self._pantalla(self.con_ciudadano, plaza=self.plaza.pk)
        self.assertContains(con_nombre, "Gómez")

    def test_confirmar_vuelve_al_mapa_libera_la_plaza_y_registra_el_movimiento(self):
        respuesta = self._post_cambio()

        self.assertRedirects(respuesta, self.url)
        self.estadia.refresh_from_db()
        self.assertEqual(self.estadia.plaza, self.otra_plaza)
        celdas = self._celdas(self._pantalla())
        self.assertEqual(celdas["P1"]["estado"], ESTADO_DISPONIBLE)
        self.assertEqual(celdas["P2"]["estado"], ESTADO_OCUPADA)
        movimiento = MovimientoEstadia.objects.filter(estadia=self.estadia).order_by("-id").first()
        self.assertEqual(movimiento.plaza_destino, self.otra_plaza)
        self.assertEqual(movimiento.motivo, "Convivencia")

    def test_sin_volver_el_post_sigue_yendo_a_la_estadia(self):
        respuesta = self._post_cambio(volver="")

        self.assertRedirects(
            respuesta,
            reverse("dispositivos:estadia_detalle", args=[self.cis.pk, self.estadia.pk]),
            fetch_redirect_response=False,
        )

    def test_el_mapa_cerrado_no_arma_el_formulario(self):
        respuesta = self._pantalla()

        self.assertNotIn("form_cambio", respuesta.context)
        self.assertNotIn("estadia_cambio", respuesta.context)


class CapacidadDelMapaTests(BaseMapa):
    """La celda es enlace solo si quien mira puede ejercer la acción de esa plaza."""

    def setUp(self):
        reloj = patch("django.utils.timezone.now", return_value=datetime(2026, 10, 14, 10, tzinfo=UTC))
        reloj.start()
        self.addCleanup(reloj.stop)
        super().setUp()

    def test_sin_dispositivo_editar_la_plaza_disponible_solo_ofrece_reservar_y_prestar(self):
        respuesta = self._pantalla(self.sin_editar_con_personas)
        self.assertEqual(self._celdas(respuesta)["P1"]["url"], f"?plaza={self.plaza.pk}")
        self.assertEqual(
            respuesta.context["plazas_modal"][self.plaza.pk]["acciones"], [ACCION_RESERVAR, ACCION_PRESTAR]
        )

    def test_sin_dispositivo_editar_el_modal_no_ofrece_sacar_de_servicio(self):
        respuesta = self._pantalla(self.sin_editar_con_personas, plaza=self.plaza.pk)
        self.assertEqual(respuesta.context["plaza_accion"]["acciones"], [ACCION_RESERVAR, ACCION_PRESTAR])
        self.assertNotIn(ACCION_FUERA_SERVICIO, respuesta.context["plazas_modal"][self.plaza.pk]["acciones"])

    def test_sin_dispositivo_admitir_la_plaza_reservada_no_se_puede_liberar(self):
        reservar_plaza(plaza=self.plaza, ciudadano=self.otra_persona, usuario=self.operador_cis)

        respuesta = self._pantalla(self.sin_admitir, plaza=self.plaza.pk)

        self.assertEqual(self._celdas(respuesta)["P1"]["url"], f"?editar_plaza={self.plaza.pk}")
        self.assertNotIn("plaza_accion", respuesta.context)

    def test_con_dispositivo_editar_la_plaza_reservada_tampoco_se_saca_de_servicio(self):
        """Liberar gana sobre sacar de servicio: una plaza tomada no se saca, se libera."""

        reservar_plaza(plaza=self.plaza, ciudadano=self.otra_persona, usuario=self.operador_cis)
        datos = sectores_con_plazas(self.cis, puede_liberar=False, puede_configurar_plazas=True)
        celdas = {celda["codigo"]: celda for item in datos["sectores"] for celda in item["plazas"]}
        self.assertEqual(celdas["P1"]["url"], f"?editar_plaza={self.plaza.pk}")

    def test_solo_lectura_no_ve_ninguna_plaza_accionable(self):
        respuesta = self._pantalla(self.solo_lectura)
        self.assertEqual({celda["url"] for celda in self._celdas(respuesta).values()}, {""})


class PlazaPedidaTests(BaseMapa):
    """La plaza ajena, la inexistente y la de otro dispositivo dan todas lo mismo."""

    def test_una_plaza_de_otra_institucion_no_abre_el_modal(self):
        respuesta = self._pantalla(plaza=self.plaza_parador.pk)
        self.assertNotIn("plaza_accion", respuesta.context)
        self.assertContains(respuesta, AVISO_NO_GESTIONABLE)

    def test_una_plaza_inexistente_da_el_mismo_aviso_que_la_ajena(self):
        respuesta = self._pantalla(plaza=99999)
        self.assertNotIn("plaza_accion", respuesta.context)
        self.assertContains(respuesta, AVISO_NO_GESTIONABLE)

    def test_un_id_que_no_es_un_numero_no_rompe(self):
        respuesta = self._pantalla(plaza="٣")  # dígito arábigo: pasa isdigit() y rompe int()
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotIn("plaza_accion", respuesta.context)


class PostDeLasAccionesTests(BaseMapa):
    """Las tres acciones mutan: solo POST, con CSRF, con alcance y con la capacidad de cada una."""

    def _url(self, nombre, plaza=None):
        return reverse(nombre, args=[self.cis.pk, (plaza or self.plaza).pk])

    def test_sacar_de_servicio_con_motivo(self):
        respuesta = self._post("dispositivos:plaza_fuera_servicio", {"motivo": "Colchón roto"})

        self.assertRedirects(respuesta, self.url)
        self.plaza.refresh_from_db()
        self.assertEqual(self.plaza.estado, Plaza.Estado.FUERA_SERVICIO)
        self.assertEqual(self.plaza.motivo_fuera_servicio, "Colchón roto")

    def test_sacar_de_servicio_sin_motivo_no_cambia_nada(self):
        self._post("dispositivos:plaza_fuera_servicio", {"motivo": "  "})

        self.plaza.refresh_from_db()
        self.assertEqual(self.plaza.estado, Plaza.Estado.OPERATIVA)

    def test_no_se_saca_de_servicio_una_plaza_ocupada(self):
        ingresar_persona(ciudadano=self.persona, dispositivo=self.cis, usuario=self.operador_cis, plaza=self.plaza)

        self._post("dispositivos:plaza_fuera_servicio", {"motivo": "Colchón roto"})

        self.plaza.refresh_from_db()
        self.assertEqual(self.plaza.estado, Plaza.Estado.OPERATIVA)

    def test_volver_a_servicio(self):
        sacar_plaza_de_servicio(plaza=self.plaza, usuario=self.operador_cis, motivo="Colchón roto")

        self._post("dispositivos:plaza_volver_servicio", {})

        self.plaza.refresh_from_db()
        self.assertEqual(self.plaza.estado, Plaza.Estado.OPERATIVA)
        self.assertEqual(self.plaza.motivo_fuera_servicio, "")

    def test_liberar_la_reserva_de_la_plaza(self):
        reserva = reservar_plaza(plaza=self.plaza, ciudadano=self.otra_persona, usuario=self.operador_cis)

        self._post("dispositivos:plaza_liberar", {"motivo": "No se presentó"})

        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, ReservaPlaza.Estado.LIBERADA)
        self.assertEqual(reserva.motivo, "No se presentó")

    def test_liberar_una_plaza_sin_reserva_abierta_no_rompe(self):
        respuesta = self._post("dispositivos:plaza_liberar", {})
        self.assertRedirects(respuesta, self.url)

    def test_sin_alcance_sobre_el_dispositivo_no_se_puede(self):
        self.client.force_login(self.operador_parador)

        respuesta = self.client.post(self._url("dispositivos:plaza_fuera_servicio"), {"motivo": "x"})

        self.assertEqual(respuesta.status_code, 403)
        self.plaza.refresh_from_db()
        self.assertEqual(self.plaza.estado, Plaza.Estado.OPERATIVA)

    def test_sin_la_capacidad_de_la_accion_no_se_puede(self):
        """`dispositivo.admitir` no habilita sacar plazas de servicio, que es `dispositivo.editar`."""

        self.client.force_login(self.sin_editar)

        respuesta = self.client.post(self._url("dispositivos:plaza_fuera_servicio"), {"motivo": "x"})

        self.assertEqual(respuesta.status_code, 403)
        self.plaza.refresh_from_db()
        self.assertEqual(self.plaza.estado, Plaza.Estado.OPERATIVA)

    def test_quien_no_opera_el_dispositivo_no_puede_distinguir_una_plaza_que_existe(self):
        """La compuerta de alcance va **antes** de buscar la plaza, y por eso existe.

        El operador del parador tiene `dispositivo.editar` en el programa, así que el mixin
        lo deja pasar: lo que lo frena es el alcance al CIS. Si esa compuerta estuviera
        después de la búsqueda, la plaza del CIS daría 403 —el servicio la rechaza— y una
        inexistente daría 404, y la diferencia enumera las plazas de otra institución.
        """

        self.client.force_login(self.operador_parador)

        existe = self.client.post(self._url("dispositivos:plaza_fuera_servicio"), {"motivo": "x"})
        inexistente = self.client.post(
            reverse("dispositivos:plaza_fuera_servicio", args=[self.cis.pk, 99999]), {"motivo": "x"}
        )

        self.assertEqual(existe.status_code, inexistente.status_code)
        self.assertEqual(existe.status_code, 403)

    def test_la_plaza_de_otra_institucion_da_404_y_no_se_toca(self):
        self.client.force_login(self.operador_cis)

        respuesta = self.client.post(
            reverse("dispositivos:plaza_fuera_servicio", args=[self.cis.pk, self.plaza_parador.pk]),
            {"motivo": "x"},
        )

        self.assertEqual(respuesta.status_code, 404)
        self.plaza_parador.refresh_from_db()
        self.assertEqual(self.plaza_parador.estado, Plaza.Estado.OPERATIVA)

    def test_una_plaza_inexistente_da_el_mismo_404_que_la_ajena(self):
        self.client.force_login(self.operador_cis)
        respuesta = self.client.post(
            reverse("dispositivos:plaza_fuera_servicio", args=[self.cis.pk, 99999]), {"motivo": "x"}
        )
        self.assertEqual(respuesta.status_code, 404)

    def test_un_get_no_muta_nada(self):
        self.client.force_login(self.operador_cis)
        respuesta = self.client.get(self._url("dispositivos:plaza_fuera_servicio"))
        self.assertEqual(respuesta.status_code, 405)

    def _post(self, nombre, datos, plaza=None):
        self.client.force_login(self.operador_cis)
        return self.client.post(self._url(nombre, plaza), datos)


class LaAlertaSeResuelveDesdeLaPantallaTests(BaseMapa):
    """De punta a punta: la alerta de P4 está, se actúa en P5 y la alerta ya no está."""

    def test_la_alerta_de_prestamo_vencido_desaparece_al_liberarlo_desde_el_mapa(self):
        self._reserva_vencida()
        regla = "dispositivos.reserva_vencida"
        [alerta] = self._alertas(regla)
        self.assertEqual(alerta["enlace"], self.url)

        self.client.force_login(self.operador_cis)
        self.client.post(reverse("dispositivos:plaza_liberar", args=[self.cis.pk, self.plaza.pk]), {})

        self.assertEqual(self._alertas(regla), [])

    def test_la_alerta_de_plazas_fuera_de_servicio_desaparece_al_reponerlas_desde_el_mapa(self):
        sacar_plaza_de_servicio(plaza=self.plaza, usuario=self.operador_cis, motivo="Colchón roto")
        regla = "dispositivos.plazas_fuera_de_servicio"
        [alerta] = self._alertas(regla)
        self.assertEqual(alerta["enlace"], self.url)

        self.client.force_login(self.operador_cis)
        self.client.post(reverse("dispositivos:plaza_volver_servicio", args=[self.cis.pk, self.plaza.pk]), {})

        self.assertEqual(self._alertas(regla), [])


class PlazaDisponibleSinRecargaTests(BaseMapa):
    """La plaza libre ofrece reservar, prestar y sacar de servicio, y la celda abre el modal sin recargar."""

    def _opciones(self, usuario):
        return self._pantalla(usuario).context["plazas_modal"][self.plaza.pk]["acciones"]

    def test_la_disponible_ofrece_cada_opcion_segun_la_capacidad(self):
        self.assertEqual(self._opciones(self.con_personas), [ACCION_RESERVAR, ACCION_PRESTAR, ACCION_FUERA_SERVICIO])
        self.assertEqual(self._opciones(self.sin_editar_con_personas), [ACCION_RESERVAR, ACCION_PRESTAR])
        self.assertEqual(self._opciones(self.sin_admitir), [ACCION_FUERA_SERVICIO])

    def test_sin_ciudadano_ver_no_se_ofrece_reservar_ni_prestar(self):
        """Buscar a la persona por DNI es mirar el padrón: `admitir` solo no alcanza, como en el ingreso."""

        # Admite y edita, pero no ve personas: le queda sacar de servicio.
        self.assertEqual(self._opciones(self.operador_cis), [ACCION_FUERA_SERVICIO])
        # Admite y no ve personas ni edita: la plaza disponible no tiene nada que ofrecerle.
        respuesta = self._pantalla(self.sin_editar)
        self.assertEqual(respuesta.context["plazas_modal"], {})
        celda = self._celdas(respuesta)["P1"]
        self.assertEqual((celda["url"], celda["click"]), ("", ""))

    def test_sin_ninguna_capacidad_la_plaza_no_es_clickeable(self):
        respuesta = self._pantalla(self.solo_lectura)

        celda = self._celdas(respuesta)["P1"]
        self.assertEqual((celda["url"], celda["click"]), ("", ""))
        self.assertEqual(respuesta.context["plazas_modal"], {})
        self.assertNotContains(respuesta, '@click="abrirPlaza(')

    def test_la_celda_es_un_boton_y_no_un_enlace(self):
        respuesta = self._pantalla(self.con_personas)

        self.assertContains(respuesta, f'<button type="button" @click="abrirPlaza({self.plaza.pk})"')
        self.assertNotContains(respuesta, f'<a href="?plaza={self.plaza.pk}"')
        # El enlace directo sigue existiendo como dato: `?plaza=` abre el mismo modal.
        self.assertEqual(self._celdas(respuesta)["P1"]["url"], f"?plaza={self.plaza.pk}")

    def test_los_datos_del_modal_viajan_en_la_pagina(self):
        respuesta = self._pantalla(self.con_personas)

        self.assertContains(respuesta, 'id="plazas-modal-datos"')
        self.assertEqual(
            set(respuesta.context["urls_plaza"]), {"reservar", "prestar", "liberar", "fuera_servicio", "volver"}
        )
        self.assertIn("/plazas/__pk__/reservar/", respuesta.context["urls_plaza"]["reservar"])

    def test_la_plaza_ocupada_tambien_es_un_boton_que_pide_su_modal_al_tocar(self):
        ingresar_persona(ciudadano=self.persona, dispositivo=self.cis, usuario=self.operador_cis, plaza=self.plaza)

        respuesta = self._pantalla()

        celda = self._celdas(respuesta)["P1"]
        self.assertEqual(celda["url"], f"?plaza={self.plaza.pk}")
        self.assertEqual(celda["click"], f"abrirReubicar({self.plaza.pk})")
        self.assertContains(respuesta, f'<button type="button" @click="abrirReubicar({self.plaza.pk})"')
        # Lo que depende de la estadía no viaja en la página: ni form ni estadía.
        self.assertNotIn(self.plaza.pk, respuesta.context["plazas_modal"])
        self.assertNotIn("form_cambio", respuesta.context)

    def test_con_plaza_en_la_url_el_modal_llega_abierto_en_esa_plaza(self):
        respuesta = self._pantalla(self.con_personas, plaza=self.plaza.pk)

        self.assertEqual(respuesta.context["plaza_inicial"], self.plaza.pk)
        self.assertContains(respuesta, f"plazaSel: {self.plaza.pk}")


class ReservarYPrestarTests(BaseMapa):
    """Reservar y prestar desde el mapa: DNI de una persona del Legajo, `dispositivo.admitir`."""

    AJAX = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}

    def _post(self, accion, datos, usuario=None, plaza=None, **extra):
        self.client.force_login(usuario or self.con_personas)
        url = reverse(f"dispositivos:plaza_{accion}", args=[self.cis.pk, (plaza or self.plaza).pk])
        return self.client.post(url, datos, **extra)

    def _hasta(self, horas=12):
        return (timezone.localtime() + timedelta(hours=horas)).strftime("%Y-%m-%dT%H:%M")

    def test_reservar_crea_la_reserva_y_la_plaza_queda_reservada(self):
        respuesta = self._post("reservar", {"dni": self.otra_persona.dni, "motivo": "Viene del hospital"})

        self.assertRedirects(respuesta, self.url)
        [reserva] = ReservaPlaza.objects.filter(plaza=self.plaza)
        self.assertEqual(reserva.tipo, ReservaPlaza.Tipo.RESERVA)
        self.assertEqual(reserva.ciudadano, self.otra_persona)
        self.assertEqual(reserva.motivo, "Viene del hospital")
        self.assertIsNone(reserva.hasta)
        self.assertEqual(self._celdas(self._pantalla())["P1"]["estado"], "Reservada")

    def test_el_dni_con_puntos_encuentra_a_la_persona(self):
        self._post("reservar", {"dni": "30.333.444"})

        self.assertEqual(ReservaPlaza.objects.get(plaza=self.plaza).ciudadano, self.otra_persona)

    def test_prestar_crea_el_prestamo_con_su_vencimiento(self):
        self._post("prestar", {"dni": self.otra_persona.dni, "hasta": self._hasta(12)})

        reserva = ReservaPlaza.objects.get(plaza=self.plaza)
        self.assertEqual(reserva.tipo, ReservaPlaza.Tipo.PRESTAMO)
        self.assertIsNotNone(reserva.hasta)
        self.assertEqual(self._celdas(self._pantalla())["P1"]["estado"], "Prestada")

    def test_prestar_sin_hasta_es_un_error_del_campo_y_no_crea_nada(self):
        respuesta = self._post("prestar", {"dni": self.otra_persona.dni}, **self.AJAX)

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("hasta", respuesta.json()["errors"])
        self.assertFalse(ReservaPlaza.objects.exists())

    def test_prestar_con_un_vencimiento_pasado_lo_rechaza_el_servicio_en_el_campo(self):
        respuesta = self._post("prestar", {"dni": self.otra_persona.dni, "hasta": self._hasta(-3)}, **self.AJAX)

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("hasta", respuesta.json()["errors"])
        self.assertFalse(ReservaPlaza.objects.exists())

    def test_un_dni_que_no_esta_en_el_legajo_es_un_error_del_campo_dni(self):
        respuesta = self._post("reservar", {"dni": "20999888"}, **self.AJAX)

        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(
            respuesta.json()["errors"]["dni"],
            ["No encontramos a nadie con ese DNI: dala de alta desde Ingresar persona."],
        )
        self.assertFalse(ReservaPlaza.objects.exists())

    def test_un_dni_mal_escrito_dice_que_no_es_valido(self):
        respuesta = self._post("reservar", {"dni": "abc"}, **self.AJAX)

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("dni", respuesta.json()["errors"])
        self.assertFalse(ReservaPlaza.objects.exists())

    def test_sin_admitir_no_se_puede_reservar_ni_prestar(self):
        for accion, datos in (
            ("reservar", {"dni": self.otra_persona.dni}),
            ("prestar", {"dni": self.otra_persona.dni, "hasta": self._hasta()}),
        ):
            with self.subTest(accion=accion):
                respuesta = self._post(accion, datos, usuario=self.sin_admitir)
                self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(ReservaPlaza.objects.exists())

    def test_sin_ciudadano_ver_reservar_y_prestar_dan_403_sin_crear_nada(self):
        """Buscar por DNI es mirar el padrón: sin `ciudadano.ver` ni el error de «no encontramos» se puede ver."""

        for usuario in (self.operador_cis, self.sin_editar):
            for accion in ("reservar", "prestar"):
                for datos in (
                    {"dni": self.otra_persona.dni, "hasta": self._hasta()},
                    {"dni": "20999888", "hasta": self._hasta()},  # con un DNI que no existe: tampoco se sondea
                    {"dni": "abc"},  # ni con un form inválido: el gate va antes de validar
                ):
                    with self.subTest(usuario=usuario.username, accion=accion, dni=datos["dni"]):
                        comun = self._post(accion, datos, usuario=usuario)
                        ajax = self._post(accion, datos, usuario=usuario, **self.AJAX)
                        self.assertEqual(comun.status_code, 403)
                        self.assertEqual(ajax.status_code, 403)
                        self.assertNotIn("errors", ajax.json())
        self.assertFalse(ReservaPlaza.objects.exists())

    def test_con_admitir_sin_editar_se_puede_reservar_y_prestar(self):
        """La capacidad de reservar es `admitir`: exigir `editar` dejaría afuera a quien admite."""

        self._post("reservar", {"dni": self.otra_persona.dni}, usuario=self.sin_editar_con_personas)
        self.assertEqual(ReservaPlaza.objects.get(plaza=self.plaza).tipo, ReservaPlaza.Tipo.RESERVA)

        ReservaPlaza.objects.all().delete()
        self._post(
            "prestar",
            {"dni": self.otra_persona.dni, "hasta": self._hasta()},
            usuario=self.sin_editar_con_personas,
        )
        self.assertEqual(ReservaPlaza.objects.get(plaza=self.plaza).tipo, ReservaPlaza.Tipo.PRESTAMO)

    def test_la_plaza_de_otra_institucion_da_404_y_no_se_reserva(self):
        respuesta = self._post("reservar", {"dni": self.otra_persona.dni}, plaza=self.plaza_parador)

        self.assertEqual(respuesta.status_code, 404)
        self.assertFalse(ReservaPlaza.objects.exists())

    def test_quien_no_opera_el_dispositivo_recibe_403_aunque_la_plaza_exista(self):
        respuesta = self._post("reservar", {"dni": self.otra_persona.dni}, usuario=self.operador_parador)

        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(ReservaPlaza.objects.exists())

    def test_una_plaza_tomada_no_se_reserva(self):
        ingresar_persona(ciudadano=self.persona, dispositivo=self.cis, usuario=self.operador_cis, plaza=self.plaza)

        respuesta = self._post("reservar", {"dni": self.otra_persona.dni}, **self.AJAX)

        self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(ReservaPlaza.objects.exists())

    def test_un_get_no_muta_nada(self):
        self.client.force_login(self.operador_cis)

        for accion in ("reservar", "prestar"):
            respuesta = self.client.get(reverse(f"dispositivos:plaza_{accion}", args=[self.cis.pk, self.plaza.pk]))
            self.assertEqual(respuesta.status_code, 405)


class FragmentoReubicarTests(BaseMapa):
    """«Cambiar de plaza» se abre sin recargar: el servidor da solo el cuerpo del modal al tocar la celda."""

    AJAX = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}

    def setUp(self):
        super().setUp()
        self.estadia = ingresar_persona(
            ciudadano=self.persona, dispositivo=self.cis, usuario=self.operador_cis, plaza=self.plaza
        )

    def _fragmento(self, usuario=None, plaza=None, **extra):
        self.client.force_login(usuario or self.operador_cis)
        pk = self.plaza.pk if plaza is None else plaza
        return self.client.get(self.url, {"plaza": pk, "fragmento": "reubicar"}, **{**self.AJAX, **extra})

    def test_devuelve_solo_el_modal_con_el_form_que_se_envia_por_ajax(self):
        respuesta = self._fragmento()

        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "programas/dispositivos/sectores/_modal_reubicar.html")
        self.assertTemplateNotUsed(respuesta, "includes/base.html")
        self.assertNotContains(respuesta, "<html")
        self.assertContains(respuesta, "Cambiar de plaza")
        self.assertContains(respuesta, "data-ajax")
        self.assertContains(respuesta, reverse("dispositivos:cambiar_plaza", args=[self.cis.pk, self.estadia.pk]))
        self.assertContains(respuesta, "csrfmiddlewaretoken")

    def test_sin_plazas_libres_el_bloqueo_viaja_en_el_fragmento(self):
        ingresar_persona(
            ciudadano=self.otra_persona, dispositivo=self.cis, usuario=self.operador_cis, plaza=self.otra_plaza
        )

        respuesta = self._fragmento()

        self.assertContains(respuesta, MOTIVO_SIN_PLAZAS_LIBRES)
        self.assertNotContains(respuesta, "Confirmar cambio")

    def test_ajena_inexistente_y_no_reubicable_dan_404(self):
        # Libre (no hay quién mover), de otra institución y que no existe: lo mismo para las tres.
        for plaza in (self.otra_plaza.pk, self.plaza_parador.pk, 99999, "٣", "x"):
            with self.subTest(plaza=plaza):
                self.assertEqual(self._fragmento(plaza=plaza).status_code, 404)

    def test_sin_admitir_da_404_aunque_pueda_editar(self):
        self.assertEqual(self._fragmento(self.sin_admitir).status_code, 404)
        self.assertEqual(self._fragmento(self.solo_lectura).status_code, 404)

    def test_sin_el_encabezado_ajax_se_arma_la_pagina_entera(self):
        self.client.force_login(self.operador_cis)

        respuesta = self.client.get(self.url, {"plaza": self.plaza.pk, "fragmento": "reubicar"})

        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "programas/dispositivos/sectores/sectores.html")
        self.assertContains(respuesta, "Cambiar de plaza")

    def test_cuesta_pocas_consultas_y_no_arma_el_mapa(self):
        self.client.force_login(self.operador_cis)
        with CaptureQueriesContext(connection) as fragmento:
            self.client.get(self.url, {"plaza": self.plaza.pk, "fragmento": "reubicar"}, **self.AJAX)
        with CaptureQueriesContext(connection) as pagina:
            self.client.get(self.url, {"plaza": self.plaza.pk})

        self.assertLess(len(fragmento), len(pagina))
        self.assertLessEqual(len(fragmento), 20)


@tag("performance")
class MapaPresupuestoTests(BaseMapa):
    """El mapa cuesta lo mismo con un sector que con ocho (el N+1 del Cambio 272)."""

    def _medir(self):
        with CaptureQueriesContext(connection) as medida:
            datos = sectores_con_plazas(
                self.cis, puede_liberar=True, puede_configurar_plazas=True, puede_ver_personas=True
            )
        return len(medida), datos

    def test_el_mapa_respeta_el_presupuesto_y_no_crece_con_los_sectores(self):
        techo = json.loads(PRESUPUESTOS.read_text(encoding="utf-8"))["servicios"][CLAVE_PRESUPUESTO]["consultas_fijas"]
        self._reserva_vencida()
        sacar_plaza_de_servicio(plaza=self.otra_plaza, usuario=self.operador_cis, motivo="Pintura")
        pocas, datos = self._medir()
        self.assertEqual(len(datos["sectores"]), 1)

        for n in range(7):
            sector = Sector.objects.create(dispositivo=self.cis, nombre=f"Pabellón {n}", capacidad=5)
            Plaza.objects.bulk_create(Plaza(sector=sector, codigo=f"{n}-{i}") for i in range(5))
        muchas, datos = self._medir()

        self.assertEqual(len(datos["sectores"]), 8)
        self.assertEqual(muchas, pocas, "una consulta por sector sería el N+1 que esta pantalla arrastraba")
        self.assertLessEqual(muchas, techo)
