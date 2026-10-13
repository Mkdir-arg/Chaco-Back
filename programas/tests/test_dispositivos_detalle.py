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
from datetime import timedelta
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
    indicadores_de_plazas,
)
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
        conteo = ocupacion_de_plazas(self.cis).de(self.cis).conteo

        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.context["indicadores"], indicadores_de_plazas(conteo))
        valores = {fila["etiqueta"]: fila["valor"] for fila in respuesta.context["indicadores"]}
        self.assertEqual(
            valores,
            {
                "Plazas operativas": conteo.operativas,
                "Ocupadas": conteo.ocupadas,
                "Reservadas o prestadas": conteo.reservadas,
                "Disponibles": conteo.disponibles,
            },
        )
        # El escenario del test: 3 plazas, 1 fuera de servicio, 1 ocupada, 1 reservada, ninguna libre.
        self.assertEqual(list(valores.values()), [2, 1, 1, 0])

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
        self.assertEqual(respuesta.context["n_plazas"], ocupacion.conteo.operativas)

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
            {"Plazas operativas": 94, "Ocupadas": 41, "Reservadas o prestadas": 7, "Disponibles": 46},
        )
        self.assertEqual(respuesta.context["n_plazas"], 94)
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
        self.assertEqual(valores["Ocupadas"], 0)
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

        self.assertContains(self.client.get(self.url), "get('tab') || 'estadias'")


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

    def test_la_fila_ofrece_el_legajo_solo_con_ciudadano_ver(self):
        _alojar(self.cis, self.plaza, self.persona)
        legajo = reverse("legajos:ciudadano_detalle", args=[self.persona.pk])

        self.assertContains(self.client.get(self.url), legajo)

        sin_legajo = self._operador("Sin legajo", self.cis, CAPACIDADES_OPERATIVAS)
        self.client.force_login(sin_legajo)
        self.assertNotContains(self.client.get(self.url), legajo)

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
