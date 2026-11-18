"""E7 · Regla de consumo por ítem y fecha de inicio del evento (análisis 009, E-7a, RN-009-15).

Lo que E8 «Abastecimiento» va a leer para estimar faltantes: la mesa lo carga en E7 antes de
que exista la solapa. Acá se prueba la carga, la validación cruzada y la traza.
"""

from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.utils import timezone

from programas.forms_emergencia import PREFIJO_KITS
from programas.models import SLAEmergencia, TipoKit, TrazaConfiguracion
from programas.services import configuracion_emergencia as servicio
from programas.tests.test_emergencia_base import SUPERVISAR, BaseE7, BaseEmergencia

K = PREFIJO_KITS


class ReglaDeConsumoE7Tests(BaseE7):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.supervisor)

    def _trazas(self):
        return {t.campo: (t.valor_anterior, t.valor_nuevo) for t in TrazaConfiguracion.objects.all()}

    def test_un_item_nuevo_con_regla_de_reposicion_traza_el_alta_y_la_regla(self):
        datos = self._datos(
            **self._fila_nueva(
                nombre="Agua 6 l",
                unidad="bidón",
                regla_modo="REPOSICION",
                regla_cantidad="0.5",
                regla_por="PERSONA",
                regla_cada_dias="1",
            )
        )
        self.assertRedirects(self.client.post(self.url, datos), self.url)

        tipo = TipoKit.objects.get()
        self.assertEqual(
            (tipo.regla_modo, tipo.regla_cantidad, tipo.regla_por, tipo.regla_cada_dias),
            (TipoKit.ModoRegla.REPOSICION, Decimal("0.5"), TipoKit.PorRegla.PERSONA, 1),
        )
        self.assertEqual(
            self._trazas(),
            {
                servicio.CAMPO_ALTA: ("", "Agua 6 l (bidón)"),
                "regla_modo": ("Sin regla", "Reposición (cada N días)"),
                "regla_cantidad": ("", "0,5"),
                "regla_por": ("", "Persona"),
                "regla_cada_dias": ("", "1"),
            },
        )

    def test_un_item_nuevo_sin_regla_solo_traza_el_alta(self):
        datos = self._datos(**self._fila_nueva(nombre="Linterna", unidad="unidad"))
        self.assertRedirects(self.client.post(self.url, datos), self.url)
        self.assertEqual(TipoKit.objects.get().regla_modo, TipoKit.ModoRegla.SIN_REGLA)
        self.assertEqual(list(self._trazas()), [servicio.CAMPO_ALTA])

    def test_a_un_item_existente_sin_regla_se_le_carga_una_dotacion(self):
        tipo = TipoKit.objects.create(nombre="Colchón", unidad="unidad")
        datos = self._datos(
            **{f"{K}-0-regla_modo": "DOTACION", f"{K}-0-regla_cantidad": "1", f"{K}-0-regla_por": "PERSONA"}
        )
        self.assertRedirects(self.client.post(self.url, datos), self.url)
        tipo.refresh_from_db()
        self.assertEqual((tipo.regla_modo, tipo.regla_cantidad, tipo.regla_cada_dias), ("DOTACION", Decimal("1"), None))
        self.assertEqual(
            self._trazas(),
            {
                "regla_modo": ("Sin regla", "Dotación (una vez)"),
                "regla_cantidad": ("", "1"),
                "regla_por": ("", "Persona"),
            },
        )

    def test_editar_otro_dato_de_un_item_sin_regla_sigue_andando(self):
        """Los ítems que ya existían nacen sin regla: E7 los tiene que poder seguir editando."""
        tipo = TipoKit.objects.create(nombre="Frazada", unidad="unidad")
        datos = self._datos(**{f"{K}-0-unidad": "pieza"})
        self.assertRedirects(self.client.post(self.url, datos), self.url)
        tipo.refresh_from_db()
        self.assertEqual((tipo.unidad, tipo.regla_modo), ("pieza", ""))
        self.assertEqual(self._trazas(), {"unidad": ("unidad", "pieza")})

    def test_reposicion_sin_dias_se_rechaza_y_no_se_guarda_nada(self):
        datos = self._datos(
            objetivo_tomar_min=20,
            **self._fila_nueva(
                nombre="Pañales", unidad="paquete", regla_modo="REPOSICION", regla_cantidad="1", regla_por="LACTANTE"
            ),
        )
        respuesta = self.client.post(self.url, datos)
        self.assertEqual(respuesta.status_code, 400)
        self.assertTrue(respuesta.context["kits"].filas_nuevas()[0].errors.get("regla_cada_dias"))
        self.assertFalse(TipoKit.objects.exists())
        self.assertEqual(SLAEmergencia.objects.get().objetivo_tomar_min, 15)
        self.assertFalse(TrazaConfiguracion.objects.exists())

    def test_una_regla_sin_cantidad_o_sin_por_se_rechaza(self):
        for faltante in ("regla_cantidad", "regla_por"):
            with self.subTest(faltante=faltante):
                fila = {"nombre": "Colchón", "unidad": "unidad", "regla_modo": "DOTACION"}
                fila |= {"regla_cantidad": "1", "regla_por": "PERSONA"}
                fila[faltante] = ""
                respuesta = self.client.post(self.url, self._datos(**self._fila_nueva(**fila)))
                self.assertEqual(respuesta.status_code, 400)
                self.assertTrue(respuesta.context["kits"].filas_nuevas()[0].errors.get(faltante))
                self.assertFalse(TipoKit.objects.exists())

    def test_una_cantidad_cero_se_rechaza(self):
        fila = {"nombre": "Agua", "unidad": "bidón", "regla_modo": "REPOSICION"}
        fila |= {"regla_cantidad": "0", "regla_por": "PERSONA", "regla_cada_dias": "1"}
        respuesta = self.client.post(self.url, self._datos(**self._fila_nueva(**fila)))
        self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(TipoKit.objects.exists())

    def test_pasar_a_sin_regla_vacia_los_datos_de_la_regla(self):
        tipo = TipoKit.objects.create(
            nombre="Kit de higiene",
            unidad="kit",
            regla_modo="REPOSICION",
            regla_cantidad=Decimal("1"),
            regla_por="FAMILIA",
            regla_cada_dias=3,
        )
        self.assertRedirects(self.client.post(self.url, self._datos(**{f"{K}-0-regla_modo": ""})), self.url)
        tipo.refresh_from_db()
        self.assertEqual(
            (tipo.regla_modo, tipo.regla_cantidad, tipo.regla_por, tipo.regla_cada_dias), ("", None, "", None)
        )
        self.assertEqual(
            self._trazas(),
            {
                "regla_modo": ("Reposición (cada N días)", "Sin regla"),
                "regla_cantidad": ("1", ""),
                "regla_por": ("Familia", ""),
                "regla_cada_dias": ("3", ""),
            },
        )

    def test_pasar_a_dotacion_vacia_los_dias(self):
        tipo = TipoKit.objects.create(
            nombre="Frazada",
            unidad="unidad",
            regla_modo="REPOSICION",
            regla_cantidad=2,
            regla_por="PERSONA",
            regla_cada_dias=7,
        )
        self.assertRedirects(self.client.post(self.url, self._datos(**{f"{K}-0-regla_modo": "DOTACION"})), self.url)
        tipo.refresh_from_db()
        self.assertEqual((tipo.regla_modo, tipo.regla_cada_dias), ("DOTACION", None))


class InicioDelEventoE7Tests(BaseE7):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.supervisor)

    def test_se_carga_y_deja_traza(self):
        cuando = timezone.localtime(timezone.now() - timedelta(days=2)).replace(second=0, microsecond=0)
        datos = self._datos(inicio_evento=cuando.strftime("%Y-%m-%dT%H:%M"))
        self.assertRedirects(self.client.post(self.url, datos), self.url)
        self.assertEqual(SLAEmergencia.objects.get().inicio_evento, cuando)
        traza = TrazaConfiguracion.objects.get()
        self.assertEqual(
            (traza.campo, traza.valor_anterior, traza.valor_nuevo),
            ("inicio_evento", "", cuando.strftime("%d/%m/%Y %H:%M")),
        )

    def test_una_fecha_futura_se_rechaza(self):
        futuro = timezone.localtime(timezone.now() + timedelta(days=1))
        respuesta = self.client.post(self.url, self._datos(inicio_evento=futuro.strftime("%Y-%m-%dT%H:%M")))
        self.assertEqual(respuesta.status_code, 400)
        self.assertTrue(respuesta.context["form"].errors.get("inicio_evento"))
        self.assertIsNone(SLAEmergencia.objects.get().inicio_evento)
        self.assertFalse(TrazaConfiguracion.objects.exists())

    def test_es_opcional_y_la_pantalla_lo_muestra(self):
        respuesta = self.client.get(self.url)
        self.assertContains(respuesta, 'type="datetime-local"')
        self.assertContains(respuesta, "Inicio del evento")
        self.assertRedirects(self.client.post(self.url, self._datos()), self.url)
        self.assertIsNone(SLAEmergencia.objects.get().inicio_evento)


class ReglaDeConsumoServicioTests(BaseEmergencia):
    """El servicio valida por su cuenta: una API futura no pasa por el formulario."""

    def setUp(self):
        super().setUp()
        self.supervisor = self._usuario("supervisor", [SUPERVISAR])

    def test_crear_tipo_kit_acepta_la_regla(self):
        tipo = servicio.crear_tipo_kit(
            self.supervisor,
            nombre="Módulo alimentario",
            unidad="módulo",
            regla_modo="REPOSICION",
            regla_cantidad=Decimal("1"),
            regla_por="FAMILIA",
            regla_cada_dias=1,
        )
        self.assertEqual((tipo.regla_modo, tipo.regla_por), ("REPOSICION", "FAMILIA"))
        self.assertEqual(TrazaConfiguracion.objects.filter(objeto_id=tipo.pk).count(), 5)

    def test_reglas_a_medias_se_rechazan_en_el_servicio(self):
        invalidas = {
            "regla_cada_dias": {"regla_modo": "REPOSICION", "regla_cantidad": Decimal("1"), "regla_por": "PERSONA"},
            "regla_cantidad": {"regla_modo": "DOTACION", "regla_por": "PERSONA"},
        }
        invalidas["regla_cada_dias_dotacion"] = {
            "regla_modo": "DOTACION",
            "regla_cantidad": Decimal("1"),
            "regla_por": "PERSONA",
            "regla_cada_dias": 2,
        }
        invalidas["regla_por_sin_regla"] = {"regla_modo": "", "regla_por": "PERSONA"}
        for nombre, regla in invalidas.items():
            with self.subTest(caso=nombre):
                with self.assertRaises(ValidationError):
                    servicio.crear_tipo_kit(self.supervisor, nombre=f"Ítem {nombre}", unidad="unidad", **regla)
        self.assertFalse(TipoKit.objects.exists())
        self.assertFalse(TrazaConfiguracion.objects.exists())

    def test_inicio_futuro_se_rechaza_en_el_servicio(self):
        with self.assertRaises(ValidationError):
            servicio.guardar_sla(self.supervisor, inicio_evento=timezone.now() + timedelta(hours=1))
        self.assertIsNone(servicio.sla_vigente().inicio_evento)


class ReglaDeConsumoModeloTests(BaseEmergencia):
    def test_un_item_nuevo_nace_sin_regla(self):
        tipo = TipoKit.objects.create(nombre="Agua", unidad="bidón")
        self.assertEqual(
            (tipo.regla_modo, tipo.regla_cantidad, tipo.regla_por, tipo.regla_cada_dias), ("", None, "", None)
        )
        tipo.full_clean()

    def test_el_sla_nace_sin_inicio_del_evento(self):
        self.assertIsNone(servicio.sla_vigente().inicio_evento)
