"""Detalle del dispositivo (MVP v2, etapa 2 · #692 · P4).

Lo que se verifica, y por qué:

1. **Un solo origen.** Las cifras de la franja y del desglose por sector tienen que ser
   *exactamente* las del censo de `ocupacion_de_plazas`: el mapa de plazas y el ingreso
   leen de ahí, y una pantalla que contara por su cuenta mostraría otra ocupación.
2. **La solapa viaja en la URL**: filtrar y paginar vuelven a la misma solapa, y la
   página de una solapa no mueve a la otra.
3. **Sin N+1** en el listado de alojados: las consultas no crecen con las estadías.
4. **El alcance**: el detalle de un dispositivo ajeno es 403 y las acciones respetan la
   capacidad.
"""

import json
import re
from datetime import datetime, timedelta
from unittest import mock

from django.conf import settings
from django.db import connection
from django.test import tag
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from legajos.models import Ciudadano
from programas.models import Dispositivo, Estadia, Plaza, ReservaPlaza, Sector, TrazaDispositivo
from programas.selectors.trayectoria import _fila
from programas.services.detalle_dispositivo import (
    POR_PAGINA_ESTADIAS,
    estadias_del_dispositivo,
)
from programas.services.estadias import ingresar_persona
from programas.services.ocupacion import Censo, Conteo, OcupacionDispositivo, OcupacionSector, ocupacion_de_plazas
from programas.tests.test_dispositivos_estadias import CAPACIDADES_OPERATIVAS, BaseEstadias

PRESUPUESTOS = settings.BASE_DIR / "scripts" / "perf_budgets.json"
CLAVE_PRESUPUESTO = "dispositivos_detalle_estadias"


def _alojar(dispositivo, plaza, persona, ingreso=None):
    ingreso = ingreso or timezone.now()
    return Estadia.objects.create(
        ciudadano=persona,
        dispositivo=dispositivo,
        plaza=plaza,
        fecha_ingreso=ingreso,
        clave_alojamiento=Estadia.clave_para(persona),
    )


def _egresar(estadia):
    Estadia.objects.filter(pk=estadia.pk).update(
        estado=Estadia.Estado.EGRESADA, fecha_egreso=timezone.now(), clave_alojamiento=None
    )


class BaseDetalle(BaseEstadias):
    def setUp(self):
        super().setUp()
        self.tipo.plaza_obligatoria_al_ingresar = True
        self.tipo.save()
        self.operador = self._operador("Operador detalle", self.cis, (*CAPACIDADES_OPERATIVAS, "ciudadano.ver"))
        self.client.force_login(self.operador)
        self.url = reverse("dispositivos:detalle", args=[self.cis.pk])

    def _personas(self, cantidad, desde=0):
        return [
            Ciudadano.objects.create(
                dni=f"4{desde + n:07d}", nombre=f"Nombre{desde + n}", apellido=f"Apellido{desde + n}"
            )
            for n in range(cantidad)
        ]


class UnSoloOrigenTests(BaseDetalle):
    def setUp(self):
        super().setUp()
        _alojar(self.cis, self.plaza, self.persona)
        ReservaPlaza.objects.create(
            plaza=self.otra_plaza,
            ciudadano=self.otra_persona,
            tipo=ReservaPlaza.Tipo.RESERVA,
            desde=timezone.now() - timedelta(hours=1),
            hasta=timezone.now() + timedelta(hours=5),
        )
        Plaza.objects.create(
            sector=self.sector, codigo="P3", estado=Plaza.Estado.FUERA_SERVICIO, motivo_fuera_servicio="Colchón"
        )

    def test_la_franja_muestra_las_cifras_del_censo_y_ninguna_otra(self):
        self.tipo.umbral_ocupacion_amarillo = 50
        self.tipo.umbral_ocupacion_rojo = 90
        self.tipo.save()

        respuesta = self.client.get(self.url)

        ocupacion = respuesta.context["indicadores"][0]
        self.assertEqual((ocupacion["valor"], ocupacion["tono"]), ("50 %", "warning"))
        self.assertContains(respuesta, "nodo-stat-tablero-valor", count=4)
        self.assertContains(
            respuesta,
            "nodo-stat-tablero-ico flex items-center justify-center flex-shrink-0 bg-warning-soft text-fg-warning",
            count=1,
        )
        self.assertContains(
            respuesta,
            "nodo-stat-tablero-ico flex items-center justify-center flex-shrink-0 bg-brand-soft text-fg-brand",
            count=3,
        )
        valores = {fila["etiqueta"]: fila["valor"] for fila in respuesta.context["indicadores"]}
        self.assertEqual(
            valores,
            {
                "Ocupación": "50 %",
                "Plazas operativas": 2,
                "Reservadas o prestadas": 1,
                "Disponibles": 0,
            },
        )
        # El escenario del test: 3 plazas, 1 fuera de servicio, 1 ocupada, 1 reservada, ninguna libre.
        self.assertEqual(list(valores.values()), ["50 %", 2, 1, 0])

    def test_el_desglose_por_sector_es_el_del_censo(self):
        ocupacion = ocupacion_de_plazas(self.cis).de(self.cis)

        respuesta = self.client.get(self.url)

        self.assertEqual(len(respuesta.context["sectores"]), len(ocupacion.sectores))
        for fila, sector in zip(respuesta.context["sectores"], ocupacion.sectores):
            self.assertEqual(fila["totales"], sector.conteo.totales)
            self.assertEqual(fila["ocupadas"], sector.conteo.ocupadas)
            self.assertEqual(fila["reservadas"], sector.conteo.reservadas)
            self.assertEqual(fila["disponibles"], sector.conteo.disponibles)
            self.assertEqual(fila["fuera_de_servicio"], sector.conteo.fuera_de_servicio)
        self.assertEqual(respuesta.context["n_plazas"], ocupacion.conteo.totales)

    def test_todas_las_cifras_de_plazas_salen_del_censo_y_de_ningun_otro_lado(self):
        """Con un censo inventado, la pantalla dibuja el censo inventado.

        Comparar contra el censo real no alcanza: una vista que contara por su cuenta, y bien,
        daría los mismos números. Acá las cifras no coinciden con ninguna base posible (97
        plazas en un dispositivo que tiene 3), así que solo pueden haber salido del servicio.
        """

        sector = OcupacionSector(
            sector_id=self.sector.pk,
            dispositivo_id=self.cis.pk,
            nombre="Sector del censo",
            tipo=self.sector.tipo,
            capacidad_declarada=4,
            conteo=Conteo(totales=97, fuera_de_servicio=3, ocupadas=41, reservadas=7),
        )
        inventado = OcupacionDispositivo(dispositivo_id=self.cis.pk, conteo=sector.conteo, sectores=(sector,))
        censo = Censo(por_dispositivo={self.cis.pk: inventado}, total=sector.conteo)

        with mock.patch("programas.views.dispositivos_legajo.ocupacion_de_plazas", return_value=censo) as llamado:
            respuesta = self.client.get(self.url)

        llamado.assert_called_once()
        valores = {fila["etiqueta"]: fila["valor"] for fila in respuesta.context["indicadores"]}
        self.assertEqual(
            valores,
            {
                "Ocupación": "44 %",
                "Plazas operativas": 94,
                "Reservadas o prestadas": 7,
                "Disponibles": 46,
            },
        )
        self.assertEqual(respuesta.context["n_plazas"], 97)
        [fila] = respuesta.context["sectores"]
        self.assertEqual(
            (fila["nombre"], fila["totales"], fila["ocupadas"], fila["reservadas"], fila["disponibles"]),
            ("Sector del censo", 97, 41, 7, 46),
        )

    def test_la_vista_no_cuenta_por_su_cuenta(self):
        """Si el censo cambia, la pantalla cambia con él: no hay una segunda cuenta."""

        _egresar(Estadia.objects.get(ciudadano=self.persona))

        respuesta = self.client.get(self.url)

        valores = {fila["etiqueta"]: fila["valor"] for fila in respuesta.context["indicadores"]}
        self.assertEqual(valores["Ocupación"], "0 %")
        self.assertEqual(valores["Disponibles"], 1)


class SolapaEnLaUrlTests(BaseDetalle):
    def setUp(self):
        super().setUp()
        self.sector.capacidad = 80
        self.sector.save()
        plazas = Plaza.objects.bulk_create(
            Plaza(sector=self.sector, codigo=f"X{n}") for n in range(POR_PAGINA_ESTADIAS + 5)
        )
        for plaza, persona in zip(plazas, self._personas(len(plazas))):
            _alojar(self.cis, plaza, persona)

    def test_la_paginacion_de_estadias_conserva_su_solapa(self):
        respuesta = self.client.get(self.url, {"tab": "estadias"})

        self.assertContains(respuesta, "?estadias_page=2&amp;tab=estadias")
        self.assertEqual(len(respuesta.context["estadias"]), POR_PAGINA_ESTADIAS)

    def test_la_segunda_pagina_trae_el_resto(self):
        respuesta = self.client.get(self.url, {"tab": "estadias", "estadias_page": 2})

        self.assertEqual(len(respuesta.context["estadias"]), 5)

    def test_las_pildoras_conservan_la_solapa_y_el_filtro_elegido(self):
        respuesta = self.client.get(self.url, {"tab": "estadias", "estado": "TODAS"})

        self.assertContains(respuesta, '<input type="hidden" name="tab" value="estadias">', html=True)
        self.assertContains(respuesta, '<option value="TODAS" selected>Todas</option>', html=True)

    def test_la_solapa_sale_de_la_url_y_sin_ella_es_estadias(self):
        """Como en la golden: `?tab=` manda, y sin él se abre la solapa que P4 muestra activa."""

        self.assertContains(self.client.get(self.url, {"tab": "historial"}), "tab: 'historial'")
        self.assertContains(self.client.get(self.url), "tab: 'estadias'")


class SolapaNormalizadaTests(BaseDetalle):
    """Una solapa pedida que este dispositivo no tiene cae en la de siempre (carril C3).

    Sin esto, Alpine se quedaba con el valor de la URL, ningún panel coincidía con él y la
    tarjeta entera quedaba en blanco: ni solapas, ni estadías, ni historial.
    """

    def test_una_solapa_inventada_cae_en_la_de_siempre(self):
        respuesta = self.client.get(self.url, {"tab": "inventada"})

        self.assertEqual(respuesta.context["tab"], "estadias")
        self.assertContains(respuesta, "tab: 'estadias'")

    def test_sectores_en_un_tipo_que_no_maneja_plazas_cae_en_la_de_siempre(self):
        """El caso del pedido: `?tab=sectores` donde esa solapa ni siquiera se dibuja."""

        con_plazas = self.client.get(self.url, {"tab": "sectores"})
        self.assertContains(con_plazas, 'id="tab-sectores"')
        self.assertEqual(con_plazas.context["tab"], "sectores")

        self.tipo.plaza_obligatoria_al_ingresar = False
        self.tipo.save()

        respuesta = self.client.get(self.url, {"tab": "sectores"})

        self.assertNotContains(respuesta, 'id="tab-sectores"')
        self.assertEqual(respuesta.context["tab"], "estadias")
        self.assertContains(respuesta, "tab: 'estadias'")

    def test_la_estadia_normaliza_su_propia_solapa(self):
        """P7 tiene el mismo `?tab=` y el mismo agujero: ficha, movimientos o novedades."""

        estadia = _alojar(self.cis, self.plaza, self.persona)
        url = reverse("dispositivos:estadia_detalle", args=[self.cis.pk, estadia.pk])

        self.assertEqual(self.client.get(url, {"tab": "movimientos"}).context["tab"], "movimientos")
        self.assertEqual(self.client.get(url, {"tab": "sectores"}).context["tab"], "ficha")


class ObservarYRechazarTests(BaseDetalle):
    """Los dos modales de P4 que piden motivo, con el contrato JSON del arquetipo Modal.

    Antes posteaban clásico: el error del servicio llegaba como toast **después** de
    recargar la pantalla, con el modal ya cerrado y el texto escrito perdido.
    """

    def setUp(self):
        super().setUp()
        self.cis.estado = Dispositivo.Estado.PENDIENTE_VALIDACION
        self.cis.save(update_fields=["estado"])
        self.validador = self._operador("Validador", self.cis, (*CAPACIDADES_OPERATIVAS, "dispositivo.validar"))
        self.client.force_login(self.validador)

    def _post(self, accion, datos, ajax=True):
        cabeceras = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"} if ajax else {}
        return self.client.post(reverse(f"dispositivos:{accion}", args=[self.cis.pk]), datos, **cabeceras)

    def test_los_dos_modales_mandan_por_ajax_y_tienen_donde_pintar_el_error(self):
        html = self.client.get(self.url).content.decode()

        for accion in ("observar", "rechazar"):
            with self.subTest(accion=accion):
                desde = html.index(reverse(f"dispositivos:{accion}", args=[self.cis.pk]))
                formulario = html[desde : html.index("</form>", desde)]
                self.assertIn("data-ajax", formulario)
                self.assertIn('data-error="motivo"', formulario)
                self.assertIn('data-error="__all__"', formulario)

    def test_sin_motivo_el_error_vuelve_en_su_campo_y_no_cambia_nada(self):
        for accion in ("observar", "rechazar"):
            with self.subTest(accion=accion):
                respuesta = self._post(accion, {"motivo": "   "})

                self.assertEqual(respuesta.status_code, 400)
                self.assertIn("motivo", respuesta.json()["errors"])
                self.cis.refresh_from_db()
                self.assertEqual(self.cis.estado, Dispositivo.Estado.PENDIENTE_VALIDACION)

    def test_lo_que_el_servicio_rechaza_sin_campo_va_al_error_general(self):
        """El dispositivo ya no está en validación: no es un problema del campo «Motivo»."""

        self.cis.estado = Dispositivo.Estado.ACTIVO
        self.cis.save(update_fields=["estado"])

        respuesta = self._post("observar", {"motivo": "Faltan datos"})

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("__all__", respuesta.json()["errors"])

    def test_al_observar_el_front_navega_al_detalle(self):
        respuesta = self._post("observar", {"motivo": "Falta el responsable"})

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["redirect"], self.url)
        self.cis.refresh_from_db()
        self.assertEqual(self.cis.estado, Dispositivo.Estado.OBSERVADO)

    def test_sin_js_sigue_posteando_y_redirigiendo_como_antes(self):
        respuesta = self._post("rechazar", {"motivo": "No corresponde"}, ajax=False)

        self.assertRedirects(respuesta, self.url)
        self.cis.refresh_from_db()
        self.assertEqual(self.cis.estado, Dispositivo.Estado.RECHAZADO)

    def test_sin_js_y_sin_motivo_el_error_vuelve_como_mensaje(self):
        respuesta = self._post("observar", {"motivo": ""}, ajax=False)

        self.assertRedirects(respuesta, self.url)
        self.cis.refresh_from_db()
        self.assertEqual(self.cis.estado, Dispositivo.Estado.PENDIENTE_VALIDACION)


class FiltrosDeEstadiasTests(BaseDetalle):
    def setUp(self):
        super().setUp()
        self.otro_sector = Sector.objects.create(dispositivo=self.cis, nombre="Mujeres", capacidad=1)
        self.plaza_mujeres = Plaza.objects.create(sector=self.otro_sector, codigo="M1")
        self.alojada = _alojar(self.cis, self.plaza, self.persona)
        self.egresada = _alojar(self.cis, self.plaza_mujeres, self.otra_persona)
        _egresar(self.egresada)

    def _personas_en(self, respuesta):
        return {e.ciudadano.apellido for e in respuesta.context["estadias"]}

    def test_por_defecto_son_las_alojadas(self):
        self.assertEqual(self._personas_en(self.client.get(self.url)), {"Gómez"})

    def test_egresadas_y_todas(self):
        self.assertEqual(self._personas_en(self.client.get(self.url, {"estado": "EGRESADA"})), {"Pérez"})
        self.assertEqual(self._personas_en(self.client.get(self.url, {"estado": "TODAS"})), {"Gómez", "Pérez"})

    def test_por_sector(self):
        respuesta = self.client.get(self.url, {"estado": "TODAS", "sector": self.otro_sector.pk})
        self.assertEqual(self._personas_en(respuesta), {"Pérez"})

    def test_un_filtro_ajeno_o_roto_se_descarta(self):
        sector_ajeno = self.sector_parador.pk
        respuesta = self.client.get(self.url, {"estado": "ROTO", "sector": sector_ajeno})
        self.assertEqual(self._personas_en(respuesta), {"Gómez"})
        self.assertFalse(respuesta.context["hay_filtros_estadias"])
        self.assertEqual(self.client.get(self.url, {"sector": "abc"}).status_code, 200)
        # «²» es un dígito para `isdigit()` pero `int()` lo rechaza: tiene que descartarse, no dar 500.
        for raro in ("²", "١", "-1", " 1"):
            with self.subTest(sector=raro):
                respuesta = self.client.get(self.url, {"sector": raro})
                self.assertEqual(respuesta.status_code, 200)
                self.assertFalse(respuesta.context["hay_filtros_estadias"])

    def test_la_pildora_sector_solo_aparece_si_hay_sectores(self):
        con_sectores = self.client.get(self.url)
        self.assertEqual([p["nombre"] for p in con_sectores.context["pildoras"]], ["estado", "sector"])
        self.assertContains(con_sectores, '<select name="sector"')

        Sector.objects.filter(dispositivo=self.cis).update(activo=False)
        sin_sectores = self.client.get(self.url)

        self.assertEqual([p["nombre"] for p in sin_sectores.context["pildoras"]], ["estado"])
        self.assertNotContains(sin_sectores, '<select name="sector"')

    def test_el_contador_de_la_solapa_cuenta_estadias_alojadas_aunque_el_filtro_sea_otro(self):
        respuesta = self.client.get(self.url, {"estado": "EGRESADA"})
        self.assertEqual(respuesta.context["n_alojadas"], 1)

    def test_el_estado_de_cada_estadia_lo_decide_el_servicio(self):
        respuesta = self.client.get(self.url, {"estado": "TODAS"})

        por_persona = {e.ciudadano.apellido: (e.estado_texto, e.tono) for e in respuesta.context["estadias"]}
        self.assertEqual(por_persona, {"Gómez": ("Alojada", "info"), "Pérez": ("Egresada", "gray")})
        self.assertContains(respuesta, '<span class="badge badge-dot badge-info">Alojada</span>', html=True)
        self.assertContains(respuesta, '<span class="badge badge-dot badge-gray">Egresada</span>', html=True)

    def test_la_misma_estadia_se_ve_igual_en_la_solapa_del_legajo(self):
        """Una sola tabla de estados: P4 y la trayectoria del legajo (P16) no pueden discrepar."""

        respuesta = self.client.get(self.url, {"estado": "TODAS"})

        for estadia in respuesta.context["estadias"]:
            with self.subTest(estado=estadia.estado):
                fila = _fila(Estadia.objects.select_related("dispositivo__tipo", "plaza__sector").get(pk=estadia.pk))
                self.assertEqual((fila["estado"], fila["tono"]), (estadia.estado_texto, estadia.tono))

    def test_sin_resultados_ofrece_limpiar_los_filtros(self):
        Estadia.objects.filter(estado=Estadia.Estado.EGRESADA).delete()
        respuesta = self.client.get(self.url, {"estado": "EGRESADA"})
        self.assertContains(respuesta, "Ninguna estadía coincide con los filtros")


class IdentidadDeEstadiasTests(BaseDetalle):
    def setUp(self):
        reloj = mock.patch("django.utils.timezone.now", return_value=timezone.make_aware(datetime(2026, 9, 8, 10)))
        reloj.start()
        self.addCleanup(reloj.stop)
        super().setUp()
        self.estadia = ingresar_persona(
            dispositivo=self.cis, plaza=self.plaza, ciudadano=self.persona, usuario=self.operador_cis
        )

    def test_sin_ciudadano_ver_no_hay_identidad_en_la_fila_ni_en_los_modales(self):
        # Tiene todas las capacidades operativas y asignación; solo falta ciudadano.ver.
        self.client.force_login(self.operador_cis)
        for parametro in (None, "egreso", "cambio"):
            with self.subTest(modal=parametro):
                datos = {"tab": "estadias"}
                if parametro:
                    datos[parametro] = self.estadia.pk
                respuesta = self.client.get(self.url, datos)
                self.assertContains(respuesta, "Persona alojada")
                self.assertContains(respuesta, "Ingreso de Persona alojada")
                for identidad in (self.persona.nombre, self.persona.apellido, self.persona.dni, "30.111.222"):
                    self.assertNotContains(respuesta, identidad)
                self.assertContains(respuesta, "Cambiar plaza")
                self.assertContains(respuesta, "Registrar egreso")
                self.assertNotContains(respuesta, "Ver estadía")
                if parametro:
                    self.assertContains(respuesta, f'aria-labelledby="modal-{parametro}-titulo"')

    def test_con_ciudadano_ver_se_muestran_nombre_y_dni_sin_avatar(self):
        for parametro in (None, "egreso", "cambio"):
            with self.subTest(modal=parametro):
                datos = {"tab": "estadias"}
                if parametro:
                    datos[parametro] = self.estadia.pk
                respuesta = self.client.get(self.url, datos)
                self.assertContains(respuesta, "Gómez, Ana")
                self.assertContains(respuesta, "DNI 30.111.222")
                self.assertContains(respuesta, "Acciones de estadía de Ana Gómez")
                self.assertContains(respuesta, "Ingreso de Gómez, Ana")
                if parametro == "egreso":
                    self.assertContains(respuesta, "persona: 'Ana Gómez'")
                if parametro == "cambio":
                    self.assertContains(respuesta, self.persona.nombre_completo)
                tabla = respuesta.content.decode().split('id="panel-estadias"', 1)[1].split("</table>", 1)[0]
                self.assertNotIn("rounded-full", tabla)

    def test_el_listado_conserva_el_metodo_de_permanencia_del_modelo(self):
        [estadia] = estadias_del_dispositivo(self.cis)
        self.assertTrue(callable(estadia.dias_de_permanencia))
        self.assertEqual(estadia.dias_de_permanencia(), 0)


class AccionesYAlcanceTests(BaseDetalle):
    def test_el_detalle_de_un_dispositivo_ajeno_es_403(self):
        """Mismo usuario, misma capacidad: lo que cambia es el alcance (no tiene el Parador)."""

        self.assertEqual(self.client.get(self.url).status_code, 200)
        respuesta = self.client.get(reverse("dispositivos:detalle", args=[self.parador.pk]))
        self.assertEqual(respuesta.status_code, 403)

    def test_sin_dispositivo_ver_es_403_aunque_tenga_otras_capacidades_sobre_el_dispositivo(self):
        """Asignado al CIS y con todas las operativas menos `dispositivo.ver`: no entra."""

        sin_ver = self._operador("Sin ver", self.cis, ("dispositivo.admitir", "dispositivo.editar", "ciudadano.ver"))
        self.client.force_login(sin_ver)

        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_quien_solo_ve_no_recibe_acciones_que_el_servidor_va_a_rechazar(self):
        acciones = [
            reverse(f"dispositivos:{nombre}", args=[self.cis.pk])
            for nombre in ("cerrar", "inactivar", "ingreso_persona", "editar")
        ]
        # Primero el caso positivo, en el mismo estado del dispositivo: si no, el negativo
        # pasaría también con una pantalla que no dibujara ninguna acción.
        con_permisos = self.client.get(self.url)
        for url in acciones:
            self.assertContains(con_permisos, url)

        consulta = self._operador("Consulta", self.cis, ("dispositivo.ver",))
        self.client.force_login(consulta)
        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.status_code, 200)
        for url in acciones:
            self.assertNotContains(respuesta, url)

    def test_la_fila_ofrece_la_estadia_solo_con_ciudadano_ver(self):
        """El ojo abre el detalle de la estadía (P7, #698), que a su vez enlaza al legajo."""

        estadia = _alojar(self.cis, self.plaza, self.persona)
        # Con `href=` y las comillas: la URL de la estadía es prefijo de la del egreso.
        detalle = f'href="{reverse("dispositivos:estadia_detalle", args=[self.cis.pk, estadia.pk])}"'

        self.assertContains(self.client.get(self.url), detalle)

        sin_legajo = self._operador("Sin legajo", self.cis, CAPACIDADES_OPERATIVAS)
        self.client.force_login(sin_legajo)
        self.assertNotContains(self.client.get(self.url), detalle)

    def test_las_acciones_de_estado_confirman_con_el_modal_estandar_y_van_por_post(self):
        respuesta = self.client.get(self.url)

        self.assertContains(respuesta, f'data-confirm-url="{reverse("dispositivos:cerrar", args=[self.cis.pk])}"')
        self.assertContains(respuesta, f'data-confirm-url="{reverse("dispositivos:inactivar", args=[self.cis.pk])}"')
        # Ningún `data-confirm` a secas (el handler legacy de SweetAlert2): solo sus variantes
        # con guion. Con regex, para no depender de qué carácter sigue al atributo.
        self.assertIsNone(re.search(r"data-confirm(?![-\w])", respuesta.content.decode()))
        self.assertNotContains(respuesta, "_swal_confirm")
        self.assertContains(respuesta, reverse("dispositivos:ingreso_persona", args=[self.cis.pk]))

    def test_pendiente_de_validacion_ofrece_observar_y_rechazar_con_motivo(self):
        validador = self._operador("Validador", self.cis, ("dispositivo.ver", "dispositivo.validar"))
        Dispositivo.objects.filter(pk=self.cis.pk).update(estado=Dispositivo.Estado.PENDIENTE_VALIDACION)
        self.client.force_login(validador)

        respuesta = self.client.get(self.url)

        self.assertContains(respuesta, f'action="{reverse("dispositivos:observar", args=[self.cis.pk])}"')
        self.assertContains(respuesta, f'action="{reverse("dispositivos:rechazar", args=[self.cis.pk])}"')
        self.assertContains(respuesta, 'name="motivo"', count=2)
        self.assertContains(respuesta, f'data-confirm-url="{reverse("dispositivos:validar", args=[self.cis.pk])}"')

    def test_un_dispositivo_inactivo_explica_por_que_no_se_puede_ingresar(self):
        Dispositivo.objects.filter(pk=self.cis.pk).update(estado=Dispositivo.Estado.INACTIVO)

        respuesta = self.client.get(self.url)

        self.assertContains(respuesta, "No se pueden registrar ingresos")
        self.assertContains(respuesta, "Está inactivo: no admite ingresos mientras siga así.")
        self.assertNotContains(respuesta, reverse("dispositivos:ingreso_persona", args=[self.cis.pk]))

    def test_el_aviso_dice_por_que_segun_el_estado_y_no_aparece_si_esta_activo(self):
        self.assertNotContains(self.client.get(self.url), "No se pueden registrar ingresos")
        esperados = {
            Dispositivo.Estado.BORRADOR: "Está en borrador",
            Dispositivo.Estado.PENDIENTE_VALIDACION: "Está pendiente de validación",
            Dispositivo.Estado.OBSERVADO: "Está observado",
            Dispositivo.Estado.RECHAZADO: "Fue rechazado en la validación",
            Dispositivo.Estado.CERRADO: "Está cerrado",
        }
        for estado, texto in esperados.items():
            with self.subTest(estado=estado):
                Dispositivo.objects.filter(pk=self.cis.pk).update(estado=estado)
                self.assertContains(self.client.get(self.url), texto)


class SinPlazasTests(BaseDetalle):
    def test_un_tipo_sin_plazas_no_muestra_franja_ni_solapa_de_sectores(self):
        con_plazas = self.client.get(self.url)
        self.assertContains(con_plazas, "Indicadores operativos")
        self.assertContains(con_plazas, 'id="tab-sectores"')

        self.tipo.plaza_obligatoria_al_ingresar = False
        self.tipo.save()

        respuesta = self.client.get(self.url)

        self.assertNotContains(respuesta, "Indicadores operativos")
        self.assertNotContains(respuesta, 'id="tab-sectores"')


class HistorialTests(BaseDetalle):
    def test_el_historial_es_una_linea_de_tiempo_paginada(self):
        for n in range(25):
            TrazaDispositivo.objects.create(dispositivo=self.cis, usuario=self.operador, accion=f"EDICION {n}")

        pagina_1 = self.client.get(self.url)
        pagina_2 = self.client.get(self.url, {"historial_page": 2, "tab": "historial"})

        self.assertEqual(pagina_1.context["historial"].paginator.count, 25)
        self.assertEqual(len(pagina_1.context["eventos"]), 20)
        self.assertEqual(len(pagina_2.context["eventos"]), 5)
        self.assertContains(pagina_1, "?historial_page=2&amp;tab=historial")


class SinNMasUnoTests(BaseDetalle):
    def _consultas(self):
        with CaptureQueriesContext(connection) as medida:
            self.assertEqual(self.client.get(self.url).status_code, 200)
        return len(medida)

    def test_las_consultas_no_crecen_con_las_estadias(self):
        for persona, plaza in zip(self._personas(2), (self.plaza, self.otra_plaza)):
            _alojar(self.cis, plaza, persona)
        self._consultas()  # calienta caches de permisos y de contenido
        pocas = self._consultas()

        plazas = Plaza.objects.bulk_create(Plaza(sector=self.sector, codigo=f"Y{n}") for n in range(20))
        for persona, plaza in zip(self._personas(20, desde=100), plazas):
            _alojar(self.cis, plaza, persona)
        muchas = self._consultas()

        self.assertEqual(muchas, pocas, "una consulta por estadía sería un N+1 en el listado de alojados")


@tag("performance")
class DetalleEstadiasPresupuestoTests(BaseDetalle):
    """El listado de alojados cuesta lo mismo con 3 que con 60 estadías."""

    def test_el_listado_respeta_el_presupuesto_y_no_crece_con_las_filas(self):
        techo = json.loads(PRESUPUESTOS.read_text(encoding="utf-8"))["servicios"][CLAVE_PRESUPUESTO]["consultas_fijas"]
        _alojar(self.cis, self.plaza, self.persona)

        with CaptureQueriesContext(connection) as una:
            list(estadias_del_dispositivo(self.cis))

        plazas = Plaza.objects.bulk_create(Plaza(sector=self.sector, codigo=f"Z{n}") for n in range(20))
        for plaza, persona in zip(plazas, self._personas(20, desde=300)):
            _alojar(self.cis, plaza, persona)
        with CaptureQueriesContext(connection) as muchas:
            filas = list(estadias_del_dispositivo(self.cis))
            # Tocar lo que la tabla muestra no puede disparar consultas.
            [(e.ciudadano.nombre, e.plaza.codigo, e.plaza.sector.nombre) for e in filas]

        self.assertEqual(len(muchas), len(una))
        self.assertLessEqual(len(muchas), techo)
