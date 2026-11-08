"""Infraestructura del dispositivo como tarjetas por edificio y ficha (Cambio 439).

Lo que se fija acá: el orden del más grave al mejor, el filtro por estado, los avisos de vencimiento, el
aviso de sectores sin edificio según la capacidad, las acciones de la ficha según la capacidad y que, sin
alcance de inspección (Cambio 428), ni la tarjeta ni la ficha cuentan lo que el relevamiento dice.
"""

from datetime import timedelta

from django.utils import timezone

from programas.models import Edificio, InspeccionEdificio, Plaza, Sector
from programas.services.inspecciones import crear_inspeccion
from programas.tests.test_dispositivos_infraestructura import BaseInfraestructura, _panel
from programas.tests.test_dispositivos_inspecciones import Criticidad

Estado = InspeccionEdificio.Estado

ACCIONES = ("Vincular un edificio", "Cargar edificio", "Crear relevamiento", "Editar edificio", "Desvincular")


class BaseTarjetas(BaseInfraestructura):
    def setUp(self):
        super().setUp()
        self.edificio_cis.dispositivos.add(self.parador)
        self.sin_relevar = Edificio.objects.create(codigo="ED-NUEVO", nombre="Anexo sin relevar")
        self.sin_relevar.dispositivos.add(self.parador)
        self._relevar(self.predio, Criticidad.MEDIA, observaciones="Faltan dos duchas")
        self._relevar(self.edificio_cis, Criticidad.ALTA, observaciones="Pérdida de gas")
        self.solo_ver = self._usuario("solo_ver", ("dispositivo.ver",), [self.parador])
        # Ve la institución (ver_todos) pero no la opera ni la coordina: sin alcance de inspección.
        self.sin_alcance = self._usuario("sin_alcance", ("dispositivo.ver", "dispositivo.ver_todos"))

    def _infra(self, usuario=None, **params):
        respuesta = self._detalle(usuario or self.admin, self.parador, tab="infraestructura", **params)
        return respuesta, respuesta.context["infraestructura"], _panel(respuesta.content.decode())


class ListadoTests(BaseTarjetas):
    def test_las_tarjetas_van_del_mas_grave_al_mejor_y_sin_relevar_al_final(self):
        _, infra, panel = self._infra()

        self.assertEqual(
            [fila["pk"] for fila in infra["listado"]],
            [self.edificio_cis.pk, self.predio.pk, self.sin_relevar.pk],
        )
        self.assertEqual([fila["estado"]["clave"] for fila in infra["listado"]], ["CRITICO", "REGULAR", "SIN_RELEVAR"])
        self.assertLess(panel.index("Edificio CIS"), panel.index("Predio Resistencia"))
        self.assertLess(panel.index("Predio Resistencia"), panel.index("Anexo sin relevar"))
        self.assertIn("Funciona en 3 edificios", panel)

    def test_el_encabezado_nombra_al_mas_grave_con_enlace_a_su_ficha(self):
        _, infra, panel = self._infra()

        self.assertEqual(infra["resumen"]["mas_grave"]["pk"], self.edificio_cis.pk)
        self.assertIn(f"ver_edificio={self.edificio_cis.pk}", panel)
        self.assertIn("Crítico", panel)

    def test_el_filtro_por_estado_deja_solo_ese_estado_y_cuenta_todos(self):
        _, infra, panel = self._infra(estado_edificio="CRITICO")

        self.assertEqual([fila["pk"] for fila in infra["listado"]], [self.edificio_cis.pk])
        self.assertEqual(panel.count("data-tarjeta-edificio"), 1)
        activos = [chip for chip in infra["filtros"] if chip["activo"]]
        self.assertEqual([chip["texto"] for chip in activos], ["Crítico"])
        self.assertEqual(infra["filtros"][0]["n"], 3)

    def test_un_estado_inventado_no_filtra(self):
        _, infra, _ = self._infra(estado_edificio="INVENTADO")

        self.assertEqual(len(infra["listado"]), 3)

    def test_un_filtro_sin_resultados_ofrece_volver_a_ver_todos(self):
        _, infra, panel = self._infra(estado_edificio="BUENO")

        self.assertEqual(infra["listado"], [])
        self.assertIn("Ningún edificio está en ese estado", panel)

    def _abrir(self, edificio, vence):
        inspeccion = crear_inspeccion(
            self._fresco(self.admin),
            edificio=edificio,
            asignado_a=self._fresco(self.agente),
            fecha_vencimiento=timezone.localdate() + timedelta(days=30),
        )
        InspeccionEdificio.objects.filter(pk=inspeccion.pk).update(fecha_vencimiento=vence)

    def test_vencido_y_por_vencer_son_avisos_aparte_del_estado(self):
        hoy = timezone.localdate()
        self._abrir(self.predio, hoy - timedelta(days=2))
        self._abrir(self.edificio_cis, hoy + timedelta(days=10))

        _, infra, panel = self._infra()
        por_pk = {fila["pk"]: fila for fila in infra["listado"]}

        self.assertTrue(por_pk[self.predio.pk]["vencido"])
        self.assertEqual(por_pk[self.predio.pk]["aviso"]["texto"], "Vencido")
        self.assertEqual(por_pk[self.predio.pk]["estado"]["clave"], "REGULAR")
        self.assertEqual(por_pk[self.edificio_cis.pk]["aviso"]["texto"], "Vence en 10 días")
        self.assertFalse(por_pk[self.edificio_cis.pk]["vencido"])
        self.assertIn("Vence en 10 días", panel)

    def test_el_predio_compartido_se_dice_en_la_tarjeta(self):
        _, infra, panel = self._infra()
        por_pk = {fila["pk"]: fila for fila in infra["listado"]}

        self.assertEqual(por_pk[self.predio.pk]["otras_instituciones"], 1)
        self.assertEqual(por_pk[self.edificio_cis.pk]["otras_instituciones"], 1)
        self.assertEqual(por_pk[self.sin_relevar.pk]["otras_instituciones"], 0)
        self.assertIn("Compartido", panel)

    def test_los_sectores_de_cada_edificio_traen_sus_plazas(self):
        sector = Sector.objects.create(dispositivo=self.parador, edificio=self.predio, nombre="Pabellón Norte")
        Plaza.objects.create(sector=sector, codigo="N-01")
        Plaza.objects.create(sector=sector, codigo="N-02")

        _, infra, panel = self._infra()
        fila = next(f for f in infra["listado"] if f["pk"] == self.predio.pk)

        self.assertEqual(fila["n_plazas"], 2)
        self.assertEqual(fila["sectores_texto"], "Pabellón Norte (2)")
        self.assertIn("Pabellón Norte (2)", panel)


class SinEdificioTests(BaseTarjetas):
    def setUp(self):
        super().setUp()
        self.huerfano = Sector.objects.create(dispositivo=self.parador, edificio=None, nombre="Sin ubicar")

    def test_con_capacidad_de_edicion_se_ofrece_asignar_edificio(self):
        _, infra, panel = self._infra()

        self.assertEqual(infra["sin_edificio"]["primero_pk"], self.huerfano.pk)
        self.assertIn("1 sector todavía no tiene edificio", panel)
        self.assertIn("Asignar edificio", panel)
        self.assertIn(f"?sector={self.huerfano.pk}", panel)

    def test_sin_capacidad_de_edicion_queda_el_aviso_sin_la_accion(self):
        _, _, panel = self._infra(self.solo_ver)

        self.assertIn("1 sector todavía no tiene edificio", panel)
        self.assertNotIn("Asignar edificio", panel)

    def test_sin_sectores_huerfanos_no_hay_aviso(self):
        Sector.objects.filter(pk=self.huerfano.pk).update(activo=False)

        _, infra, panel = self._infra()

        self.assertIsNone(infra["sin_edificio"])
        self.assertNotIn("todavía no tiene edificio", panel)


class AccionesPorCapacidadTests(BaseTarjetas):
    def test_con_todas_las_capacidades_se_ven_las_acciones(self):
        _, _, listado = self._infra()
        _, _, ficha = self._infra(ver_edificio=self.predio.pk)

        for texto in ACCIONES:
            with self.subTest(listado=texto):
                self.assertIn(texto, listado)
        for texto in ("Editar edificio", "Desvincular", "Crear relevamiento"):
            with self.subTest(ficha=texto):
                self.assertIn(texto, ficha)

    def test_solo_con_ver_no_hay_ninguna_accion_de_escritura(self):
        _, _, listado = self._infra(self.solo_ver)
        _, _, ficha = self._infra(self.solo_ver, ver_edificio=self.predio.pk)

        for panel in (listado, ficha):
            for texto in ACCIONES:
                with self.subTest(texto=texto):
                    self.assertNotIn(texto, panel)

    def test_editar_ofrece_vincular_y_cargar_pero_no_crear_relevamiento(self):
        editor = self._usuario("editor", ("dispositivo.ver", "dispositivo.editar"), [self.parador])

        _, _, panel = self._infra(editor)

        self.assertIn("Vincular un edificio", panel)
        self.assertIn("Cargar edificio", panel)
        self.assertNotIn("Crear relevamiento", panel)


class AlcanceDelRelevamientoTests(BaseTarjetas):
    """Cambio 428: sin alcance de inspección solo se ve el semáforo y la fecha, nunca lo que dice el relevamiento."""

    def test_la_tarjeta_sin_alcance_no_cuenta_la_observacion_ni_las_fotos(self):
        _, infra, panel = self._infra(self.sin_alcance)
        fila = next(f for f in infra["listado"] if f["pk"] == self.predio.pk)

        self.assertFalse(fila["ve_detalle"])
        self.assertEqual(fila["observacion"], "")
        self.assertEqual(fila["estado"]["clave"], "REGULAR")
        self.assertNotIn("Faltan dos duchas", panel)
        self.assertNotIn("Pérdida de gas", panel)
        # Los dos edificios relevados no cuentan; el sin relevar no tiene nada que ocultar.
        con_relevamiento = [f for f in infra["listado"] if f["estado"]["clave"] != "SIN_RELEVAR"]
        self.assertEqual([f["con_conteo"] for f in con_relevamiento], [False, False])
        self.assertEqual(panel.count("Ver ficha y fotos"), 1)

    def test_con_alcance_la_tarjeta_trae_la_observacion(self):
        _, infra, panel = self._infra()
        fila = next(f for f in infra["listado"] if f["pk"] == self.predio.pk)

        self.assertTrue(fila["ve_detalle"])
        self.assertEqual(fila["observacion"], "Faltan dos duchas")
        self.assertIn("Faltan dos duchas", panel)
        self.assertIn("Ver ficha y fotos", panel)

    def test_la_ficha_sin_alcance_no_trae_observaciones_ni_registro(self):
        _, infra, panel = self._infra(self.sin_alcance, ver_edificio=self.predio.pk)

        self.assertEqual(infra["modo"], "ficha")
        self.assertNotIn("Faltan dos duchas", panel)
        self.assertNotIn("<details", panel)
        self.assertIn("Último relevamiento", panel)

    def test_la_ficha_con_alcance_trae_el_registro_en_desplegables(self):
        _, _, panel = self._infra(ver_edificio=self.predio.pk)

        self.assertIn("Faltan dos duchas", panel)
        self.assertIn("<details", panel)


class ChipsTests(BaseTarjetas):
    def test_la_ficha_ofrece_cambiar_de_edificio_y_marca_el_actual(self):
        _, infra, panel = self._infra(ver_edificio=self.predio.pk)

        self.assertEqual(len(infra["chips"]), 3)
        self.assertEqual([chip["texto"] for chip in infra["chips"] if chip["activo"]], ["Predio Resistencia"])
        self.assertIn('aria-current="page"', panel)
        for chip in infra["chips"]:
            self.assertIn("tab=infraestructura", chip["url"])
        self.assertIn("Los 3 edificios", panel)
