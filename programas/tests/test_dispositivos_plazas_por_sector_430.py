"""Cambio 430: con la numeración por sector el código se repite, así que los textos guardados
nombran la plaza con su sector y los mapas ordenan los números de forma natural."""

from programas.models import Plaza, TrazaDispositivo
from programas.services.bitacora import _texto_automatico
from programas.services.estadias import sacar_plaza_de_servicio
from programas.services.ingreso import plazas_para_ingresar
from programas.services.nombre_plaza import clave_natural, nombre_de_plaza, plaza_con_sector
from programas.services.sectores_plazas import _plazas_por_sector
from programas.tests.test_dispositivos_movimientos import BaseMovimientos


class NombreConSectorTests(BaseMovimientos):
    def setUp(self):
        super().setUp()
        # El mismo código en dos sectores: lo que ahora pasa de verdad.
        self.repetida = Plaza.objects.create(sector=self.otro_sector, codigo="P2")

    def test_el_helper_une_codigo_y_sector(self):
        self.assertEqual(nombre_de_plaza(self.otra_plaza), "plaza P2 (Varones)")
        self.assertEqual(plaza_con_sector(self.repetida), "P2 (Mujeres)")
        self.assertEqual(plaza_con_sector(self.repetida, "Otro"), "P2 (Otro)")

    def test_el_cambio_de_sector_distingue_las_dos_plazas_con_el_mismo_codigo(self):
        mismo_sector = self._cambiar(self.otra_plaza)
        otro_sector = self._cambiar(self.repetida)

        self.assertEqual(
            _texto_automatico(mismo_sector),
            "Cambio de plaza · plaza P1 (Varones) → plaza P2 (Varones) · motivo: Convivencia",
        )
        self.assertEqual(
            _texto_automatico(otro_sector),
            "Cambio de sector · plaza P2 (Varones) → plaza P2 (Mujeres) · motivo: Convivencia",
        )
        detalles = TrazaDispositivo.objects.filter(accion="ESTADIA_CAMBIO_PLAZA").values_list("detalle", flat=True)
        self.assertTrue(any("plaza P2 (Varones) → plaza P2 (Mujeres)" in d for d in detalles))

    def test_la_traza_de_sacar_de_servicio_nombra_el_sector(self):
        sacar_plaza_de_servicio(plaza=self.repetida, usuario=self.operador_cis, motivo="Rota")

        traza = TrazaDispositivo.objects.get(accion="PLAZA_FUERA_SERVICIO")
        self.assertIn("Plaza P2 (Mujeres)", traza.detalle)


class OrdenNaturalTests(BaseMovimientos):
    def test_la_clave_natural_pone_98_y_99_antes_que_100(self):
        self.assertEqual(sorted(["100", "99", "98"], key=clave_natural), ["98", "99", "100"])
        codigos = ["B-10", "B-9", "b-100", "B-01"]
        self.assertEqual(sorted(codigos, key=clave_natural), ["B-01", "B-9", "B-10", "b-100"])

    def test_el_mapa_de_sectores_ordena_los_numeros(self):
        for codigo in ("98", "99", "100"):
            Plaza.objects.create(sector=self.otro_sector, codigo=codigo)

        codigos = [p.codigo for p in _plazas_por_sector([self.otro_sector.pk])[self.otro_sector.pk]]

        self.assertEqual(codigos, ["M1", "98", "99", "100"])

    def test_el_mapa_de_ingreso_ordena_los_numeros(self):
        for codigo in ("98", "99", "100"):
            Plaza.objects.create(sector=self.otro_sector, codigo=codigo)

        sectores, _elegibles = plazas_para_ingresar(self.cis)

        fila = next(s for s in sectores if s["sector"].pk == self.otro_sector.pk)
        self.assertEqual([p["codigo"] for p in fila["plazas"]], ["M1", "98", "99", "100"])
