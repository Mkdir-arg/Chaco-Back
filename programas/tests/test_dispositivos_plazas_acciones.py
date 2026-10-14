"""Acciones del mapa de plazas (MVP v2 · P5) y las alertas de P4 que resuelven.

Lo que se fija acá, y por qué:

1. **Cada plaza ofrece una sola acción, la que su situación admite**, y la decide el
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

from programas.models import Plaza, ReservaPlaza, Sector
from programas.services.detalle_dispositivo import alertas_del_dispositivo
from programas.services.estadias import ingresar_persona, reservar_plaza, sacar_plaza_de_servicio
from programas.services.ocupacion import ESTADO_DISPONIBLE, ESTADO_FUERA_SERVICIO, ESTADO_OCUPADA
from programas.services.sectores_plazas import (
    ACCION_FUERA_SERVICIO,
    ACCION_LIBERAR,
    ACCION_VOLVER,
    MOTIVO_PLAZA_OCUPADA,
    sectores_con_plazas,
)
from programas.tests.test_dispositivos_estadias import BaseEstadias

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

    def test_una_plaza_disponible_se_puede_sacar_de_servicio(self):
        respuesta = self._pantalla()

        celda = self._celdas(respuesta)["P1"]

        self.assertEqual(celda["estado"], ESTADO_DISPONIBLE)
        self.assertEqual(celda["url"], f"?plaza={self.plaza.pk}")
        self.assertEqual(self._pantalla(plaza=self.plaza.pk).context["plaza_accion"]["accion"], ACCION_FUERA_SERVICIO)

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
        ingresar_persona(ciudadano=self.persona, dispositivo=self.cis, usuario=self.operador_cis, plaza=self.plaza)

        respuesta = self._pantalla(plaza=self.plaza.pk)

        self.assertEqual(self._celdas(respuesta)["P1"]["estado"], ESTADO_OCUPADA)
        self.assertEqual(respuesta.context["plaza_accion"]["bloqueo"], MOTIVO_PLAZA_OCUPADA)
        self.assertNotIn("form_plaza", respuesta.context)
        self.assertContains(respuesta, "No se puede sacar de servicio")

    def test_un_sector_dado_de_baja_no_aporta_plazas_ni_acciones(self):
        Sector.objects.filter(pk=self.sector.pk).update(activo=False)

        respuesta = self._pantalla(plaza=self.plaza.pk)

        self.assertEqual(self._celdas(respuesta), {})
        self.assertNotIn("plaza_accion", respuesta.context)


class CapacidadDelMapaTests(BaseMapa):
    """La celda es enlace solo si quien mira puede ejercer la acción de esa plaza."""

    def setUp(self):
        reloj = patch("django.utils.timezone.now", return_value=datetime(2026, 10, 14, 10, tzinfo=UTC))
        reloj.start()
        self.addCleanup(reloj.stop)
        super().setUp()

    def test_sin_dispositivo_editar_la_plaza_disponible_no_es_enlace(self):
        respuesta = self._pantalla(self.sin_editar)
        self.assertEqual(self._celdas(respuesta)["P1"]["url"], "")

    def test_sin_dispositivo_editar_tampoco_se_abre_el_modal(self):
        respuesta = self._pantalla(self.sin_editar, plaza=self.plaza.pk)
        self.assertNotIn("plaza_accion", respuesta.context)
        self.assertContains(respuesta, AVISO_NO_GESTIONABLE)

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


@tag("performance")
class MapaPresupuestoTests(BaseMapa):
    """El mapa cuesta lo mismo con un sector que con ocho (el N+1 del Cambio 272)."""

    def _medir(self):
        with CaptureQueriesContext(connection) as medida:
            datos = sectores_con_plazas(self.cis, puede_liberar=True, puede_configurar_plazas=True)
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
