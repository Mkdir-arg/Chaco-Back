"""Contratos de `Edificio`, `Sector` y `Plaza` (MVP v2, etapa 1 · #685 y #686).

Las tres entidades que la etapa 1 deja en pie, con las tres distinciones que la hacen
funcionar y que un refactor apurado borra sin que nada se queje:

* el **edificio** es el inmueble y se comparte: varios a varios con `Dispositivo`, en
  los dos sentidos (predio de Resistencia con el parador, el geriátrico y Sotai);
* el **sector** cuelga del dispositivo, **no** del edificio: es la organización
  operativa de la institución, no una parte del inmueble;
* la **plaza** guarda su estado *operativo* y nada más. Ocupada, reservada y prestada
  son derivadas de las estadías y las calcula el servicio único de cálculo: acá se
  verifica que el modelo **no tenga** dónde tipearlas.
"""

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase

from programas.models import Dispositivo, Edificio, Plaza, Sector, TipoDispositivo


def _tipo(codigo="ALBERGUE", **extra):
    return TipoDispositivo.objects.create(codigo=codigo, nombre=f"Tipo {codigo}", **extra)


def _dispositivo(tipo, codigo="CIS-3", nombre="CIS N.º 3"):
    return Dispositivo.objects.create(tipo=tipo, codigo=codigo, nombre=nombre)


class EdificioTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.tipo = _tipo()
        cls.parador = _dispositivo(cls.tipo, codigo="PAR-1", nombre="Parador")
        cls.geriatrico = _dispositivo(cls.tipo, codigo="GER-1", nombre="Geriátrico")

    def test_un_predio_aloja_varias_instituciones_y_se_ve_desde_cualquiera(self):
        predio = Edificio.objects.create(codigo="RES-01", nombre="Predio Resistencia")

        predio.dispositivos.set([self.parador, self.geriatrico])

        self.assertEqual(
            sorted(predio.dispositivos.values_list("codigo", flat=True)),
            ["GER-1", "PAR-1"],
        )
        self.assertEqual(list(self.parador.edificios.all()), [predio])
        self.assertEqual(list(self.geriatrico.edificios.all()), [predio])

    def test_una_institucion_puede_ocupar_mas_de_un_inmueble(self):
        uno = Edificio.objects.create(codigo="RES-01", nombre="Casa central")
        otro = Edificio.objects.create(codigo="RES-02", nombre="Anexo")

        self.parador.edificios.set([uno, otro])

        self.assertEqual(
            sorted(self.parador.edificios.values_list("codigo", flat=True)),
            ["RES-01", "RES-02"],
        )

    def test_desvincular_no_borra_el_edificio_ni_la_institucion(self):
        predio = Edificio.objects.create(codigo="RES-01", nombre="Predio Resistencia")
        predio.dispositivos.add(self.parador, self.geriatrico)

        predio.dispositivos.remove(self.parador)

        self.assertEqual(list(predio.dispositivos.all()), [self.geriatrico])
        self.assertTrue(Dispositivo.objects.filter(pk=self.parador.pk).exists())
        self.assertTrue(Edificio.objects.filter(pk=predio.pk).exists())

    def test_el_codigo_del_edificio_es_unico(self):
        Edificio.objects.create(codigo="RES-01", nombre="Predio Resistencia")

        with self.assertRaises(IntegrityError), transaction.atomic():
            Edificio.objects.create(codigo="RES-01", nombre="Otro predio")

    def test_el_domicilio_normalizado_se_arma_sin_las_partes_vacias(self):
        predio = Edificio.objects.create(
            codigo="RES-01",
            nombre="Predio Resistencia",
            calle="Av. 25 de Mayo",
            numero="1240",
            localidad="Resistencia",
        )

        self.assertEqual(predio.domicilio_completo, "Av. 25 de Mayo 1240 · Resistencia · Chaco")

    def test_el_edificio_guarda_su_geolocalizacion(self):
        predio = Edificio.objects.create(
            codigo="RES-01",
            nombre="Predio Resistencia",
            latitud="-27.451000",
            longitud="-58.986600",
        )

        predio.refresh_from_db()

        self.assertEqual(str(predio.latitud), "-27.451000")
        self.assertEqual(str(predio.longitud), "-58.986600")

    def test_el_mvp_no_trae_tenencia_servicios_estado_fisico_ni_plano(self):
        """Eso es de la Versión 2 completa; si aparece acá, alguien se adelantó."""

        campos = {campo.name for campo in Edificio._meta.get_fields()}

        self.assertEqual(campos & {"tenencia", "servicios", "estado_fisico", "plano"}, set())


class SectorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.tipo = _tipo()
        cls.dispositivo = _dispositivo(cls.tipo)
        cls.otro = _dispositivo(cls.tipo, codigo="CIS-4", nombre="CIS N.º 4")

    def test_el_sector_cuelga_del_dispositivo_y_no_del_edificio(self):
        sector = Sector.objects.create(
            dispositivo=self.dispositivo,
            nombre="Pabellón A",
            tipo=Sector.Tipo.PABELLON,
            perfil="varones",
            capacidad=16,
        )

        self.assertEqual(list(self.dispositivo.sectores.all()), [sector])
        self.assertNotIn("edificio", {campo.name for campo in Sector._meta.get_fields()})

    def test_el_nombre_del_sector_es_unico_dentro_del_dispositivo(self):
        Sector.objects.create(dispositivo=self.dispositivo, nombre="Pabellón A")

        with self.assertRaises(IntegrityError), transaction.atomic():
            Sector.objects.create(dispositivo=self.dispositivo, nombre="Pabellón A")

    def test_dos_instituciones_pueden_tener_un_sector_con_el_mismo_nombre(self):
        Sector.objects.create(dispositivo=self.dispositivo, nombre="Pabellón A")
        Sector.objects.create(dispositivo=self.otro, nombre="Pabellón A")

        self.assertEqual(Sector.objects.filter(nombre="Pabellón A").count(), 2)

    def test_la_capacidad_es_la_declarada_y_no_la_cuenta_de_plazas(self):
        """El número del legajo y el mapa real se comparan; no se pisan."""

        sector = Sector.objects.create(dispositivo=self.dispositivo, nombre="Pabellón A", capacidad=16)
        Plaza.objects.create(sector=sector, codigo="A-01")

        self.assertEqual(sector.capacidad, 16)
        self.assertEqual(sector.plazas.count(), 1)

    def test_no_se_puede_borrar_un_dispositivo_con_sectores(self):
        Sector.objects.create(dispositivo=self.dispositivo, nombre="Pabellón A")

        with self.assertRaises(ProtectedError), transaction.atomic():
            self.dispositivo.delete()

    def test_un_dispositivo_sin_sectores_ni_plazas_no_rompe(self):
        self.assertEqual(list(self.dispositivo.sectores.all()), [])
        self.assertEqual(Plaza.objects.filter(sector__dispositivo=self.dispositivo).count(), 0)


class PlazaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.tipo = _tipo()
        cls.dispositivo = _dispositivo(cls.tipo)
        cls.sector = Sector.objects.create(
            dispositivo=cls.dispositivo,
            nombre="Pabellón A",
            tipo=Sector.Tipo.PABELLON,
            capacidad=16,
        )

    def test_los_tipos_de_plaza_son_cama_cupo_y_turno(self):
        self.assertEqual(
            [(valor, etiqueta) for valor, etiqueta in Plaza.Tipo.choices],
            [("CAMA", "Cama"), ("CUPO", "Cupo"), ("TURNO", "Turno")],
        )

    def test_el_estado_guardado_es_solo_el_operativo(self):
        """La plaza guarda lo único que alguien decide; la ocupación se deriva."""

        self.assertEqual(set(Plaza.Estado.values), {"OPERATIVA", "FUERA_SERVICIO"})
        self.assertEqual(
            {"OCUPADA", "RESERVADA", "PRESTADA"} & set(Plaza.Estado.values),
            set(),
            "Estos tres NO se guardan: los deriva de las estadías el servicio de cálculo "
            "(task 22). Guardarlos crearía una segunda fuente de verdad que se desincroniza "
            "con el primer egreso que falle a mitad de camino; y además reserva y préstamo "
            "vencen por reloj, así que un estado guardado necesitaría un cron que lo revierta "
            "—el mismo problema que ya tiene el cron de las 03:10 de relevamientos—. Si "
            "llegaste acá porque hace falta cachear alguno, eso es una decisión que se revisa "
            "a propósito, no un test que se ajuste.",
        )

    def test_la_plaza_nace_operativa(self):
        plaza = Plaza.objects.create(sector=self.sector, codigo="A-01")

        self.assertEqual(plaza.estado, Plaza.Estado.OPERATIVA)
        self.assertEqual(plaza.tipo, Plaza.Tipo.CAMA)
        self.assertTrue(plaza.operativa)

    def test_el_codigo_de_la_plaza_es_unico_dentro_del_sector(self):
        Plaza.objects.create(sector=self.sector, codigo="A-01")

        with self.assertRaises(IntegrityError), transaction.atomic():
            Plaza.objects.create(sector=self.sector, codigo="A-01")

    def test_dos_sectores_pueden_repetir_el_codigo_de_plaza(self):
        otro_sector = Sector.objects.create(dispositivo=self.dispositivo, nombre="Pabellón B")
        Plaza.objects.create(sector=self.sector, codigo="A-01")
        Plaza.objects.create(sector=otro_sector, codigo="A-01")

        self.assertEqual(Plaza.objects.filter(codigo="A-01").count(), 2)

    def test_sacar_de_servicio_exige_motivo_en_la_validacion(self):
        plaza = Plaza(sector=self.sector, codigo="A-01", estado=Plaza.Estado.FUERA_SERVICIO)

        with self.assertRaises(ValidationError) as error:
            plaza.full_clean()

        self.assertIn("motivo_fuera_servicio", error.exception.message_dict)

    def test_sacar_de_servicio_sin_motivo_tampoco_entra_en_la_base(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Plaza.objects.create(
                sector=self.sector,
                codigo="A-01",
                estado=Plaza.Estado.FUERA_SERVICIO,
            )

    def test_transicion_operativa_a_fuera_de_servicio_y_vuelta(self):
        plaza = Plaza.objects.create(sector=self.sector, codigo="A-01")

        plaza.estado = Plaza.Estado.FUERA_SERVICIO
        plaza.motivo_fuera_servicio = "colchón"
        plaza.full_clean()
        plaza.save()
        plaza.refresh_from_db()

        self.assertFalse(plaza.operativa)
        self.assertEqual(plaza.motivo_fuera_servicio, "colchón")

        plaza.estado = Plaza.Estado.OPERATIVA
        plaza.motivo_fuera_servicio = ""
        plaza.full_clean()
        plaza.save()
        plaza.refresh_from_db()

        self.assertTrue(plaza.operativa)

    def test_no_se_puede_borrar_un_sector_con_plazas(self):
        Plaza.objects.create(sector=self.sector, codigo="A-01")

        with self.assertRaises(ProtectedError), transaction.atomic():
            self.sector.delete()


class ConfiguracionDeTipoDeDispositivoTests(TestCase):
    """El tipo manda qué plazas admite y si asignar una es obligatorio al ingresar."""

    def test_sin_restriccion_declarada_admite_cualquier_tipo(self):
        tipo = _tipo()

        self.assertEqual(tipo.tipos_de_plaza, [])
        for valor in Plaza.Tipo.values:
            self.assertTrue(tipo.admite_tipo_de_plaza(valor))

    def test_un_nulo_heredado_se_lee_como_sin_restriccion(self):
        """Lo que ve el código nuevo sobre una fila escrita antes de la columna."""

        tipo = _tipo()
        TipoDispositivo.objects.filter(pk=tipo.pk).update(tipos_plaza_admitidos=None)
        tipo.refresh_from_db()

        self.assertEqual(tipo.tipos_de_plaza, [])
        self.assertTrue(tipo.admite_tipo_de_plaza(Plaza.Tipo.CAMA))

    def test_el_tipo_restringido_rechaza_una_plaza_de_otro_tipo(self):
        tipo = _tipo(tipos_plaza_admitidos=[Plaza.Tipo.CUPO])
        dispositivo = _dispositivo(tipo, codigo="COM-1", nombre="Comedor")
        sector = Sector.objects.create(dispositivo=dispositivo, nombre="Turno noche", tipo=Sector.Tipo.TURNO)

        plaza = Plaza(sector=sector, codigo="N-01", tipo=Plaza.Tipo.CAMA)
        with self.assertRaises(ValidationError) as error:
            plaza.full_clean()
        self.assertIn("tipo", error.exception.message_dict)

        admitida = Plaza(sector=sector, codigo="N-02", tipo=Plaza.Tipo.CUPO)
        admitida.full_clean()  # no levanta

    def test_un_tipo_de_plaza_desconocido_no_pasa_la_validacion_del_tipo(self):
        tipo = TipoDispositivo(codigo="X", nombre="X", tipos_plaza_admitidos=["SILLA"])

        with self.assertRaises(ValidationError) as error:
            tipo.full_clean()

        self.assertIn("tipos_plaza_admitidos", error.exception.message_dict)

    def test_la_plaza_obligatoria_al_ingresar_nace_apagada(self):
        tipo = _tipo()

        self.assertFalse(tipo.plaza_obligatoria_al_ingresar)
