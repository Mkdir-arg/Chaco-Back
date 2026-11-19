"""Cambio 498 (E-2) · `core.UbicacionLocalidad` y `cargar_ubicaciones_localidades`."""

import io
import shutil
import tempfile
from decimal import Decimal
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, connection, transaction
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from core.models import Localidad, Municipio, Provincia, UbicacionLocalidad
from core.services.ubicaciones_localidades import clave

ENCABEZADO = "# comentario de atribución\nid_fuente,nombre,municipio,departamento,latitud,longitud\n"
FILAS = [
    "22140010,Barranqueras,Barranqueras,San Fernando,-27.483333,-58.933333",
    "22001001,La Esperanza,Villa Ángela,Mayor Luis J. Fontana,-27.500000,-60.700000",
    "22001002,La Esperanza,Villa Ángela,Mayor Luis J. Fontana,-27.510000,-60.710000",
    "22002001,La Esperanza,Charata,Chacabuco,-27.200000,-61.200000",
    "22003001,El Paraisal,Juan José Castelli,General Güemes,-25.900000,-60.600000",
]


class UbicacionLocalidadTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        chaco = Provincia.objects.create(nombre="Chaco")
        otra = Provincia.objects.create(nombre="Corrientes")
        cls.barranqueras_mun = Municipio.objects.create(nombre="Barranqueras", provincia=chaco)
        villa_angela = Municipio.objects.create(nombre="Villa Angela", provincia=chaco)
        charata = Municipio.objects.create(nombre="Charata", provincia=chaco)
        quitilipi = Municipio.objects.create(nombre="Quitilipi", provincia=chaco)
        cls.barranqueras = Localidad.objects.create(nombre="BARRANQUERAS", municipio=cls.barranqueras_mun)
        cls.esperanza_va = Localidad.objects.create(nombre="La Esperanza", municipio=villa_angela)
        cls.esperanza_ch = Localidad.objects.create(nombre="La Esperanza", municipio=charata)
        cls.paraisal = Localidad.objects.create(nombre="El Paraisal", municipio=quitilipi)
        cls.inexistente = Localidad.objects.create(nombre="Paraje Inventado", municipio=quitilipi)
        cls.fuera = Localidad.objects.create(
            nombre="Barranqueras", municipio=Municipio.objects.create(nombre="Barranqueras", provincia=otra)
        )

    def setUp(self):
        carpeta = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, carpeta, True)
        self.csv = carpeta / "georef.csv"
        self._escribir(FILAS)

    def _escribir(self, filas):
        self.csv.write_text(ENCABEZADO + "\n".join(filas) + "\n", encoding="utf-8")

    def _correr(self, *args):
        salida = io.StringIO()
        call_command("cargar_ubicaciones_localidades", "--archivo", str(self.csv), *args, stdout=salida)
        return salida.getvalue()

    def test_str(self):
        ubicacion = UbicacionLocalidad(
            localidad=self.barranqueras, latitud=Decimal("-27.483333"), longitud=Decimal("-58.933333")
        )

        self.assertEqual(str(ubicacion), "BARRANQUERAS (-27.483333, -58.933333)")

    def test_clave_ignora_acentos_mayusculas_y_signos(self):
        self.assertEqual(clave("  Villa  Ángela "), "villa angela")
        self.assertEqual(clave("El Ñandubay"), "el nandubay")
        self.assertEqual(clave("Pcia. Roque Sáenz Peña"), "pcia roque saenz pena")

    def test_crea_una_ubicacion_por_localidad_conciliada(self):
        salida = self._correr()

        ubicacion = UbicacionLocalidad.objects.get(localidad=self.barranqueras)
        self.assertEqual(ubicacion.latitud, Decimal("-27.483333"))
        self.assertEqual(ubicacion.longitud, Decimal("-58.933333"))
        self.assertEqual(ubicacion.departamento, "San Fernando")
        self.assertEqual(ubicacion.fuente, "BAHRA/Georef")
        self.assertEqual(ubicacion.id_fuente, "22140010")
        self.assertIn("Conciliadas: 2 (creadas 2, actualizadas 0, sin cambios 0)", salida)

    def test_no_toca_localidades_de_otra_provincia(self):
        self._correr()

        self.assertFalse(UbicacionLocalidad.objects.filter(localidad=self.fuera).exists())

    def test_correr_dos_veces_deja_el_mismo_resultado(self):
        self._correr()
        antes = list(UbicacionLocalidad.objects.values_list("localidad_id", "latitud", "longitud", "id_fuente"))

        salida = self._correr()

        despues = list(UbicacionLocalidad.objects.values_list("localidad_id", "latitud", "longitud", "id_fuente"))
        self.assertEqual(antes, despues)
        self.assertIn("creadas 0, actualizadas 0, sin cambios 2", salida)

    def test_un_dato_cambiado_actualiza_sin_duplicar(self):
        self._correr()
        self._escribir([FILAS[0].replace("-27.483333", "-27.490000"), *FILAS[1:]])

        salida = self._correr()

        self.assertEqual(UbicacionLocalidad.objects.count(), 2)
        self.assertEqual(UbicacionLocalidad.objects.get(localidad=self.barranqueras).latitud, Decimal("-27.490000"))
        self.assertIn("creadas 0, actualizadas 1, sin cambios 1", salida)

    def test_una_localidad_ambigua_no_se_asigna_a_ciegas(self):
        """Dos filas con el mismo nombre y municipio: no hay cómo saber cuál es."""
        salida = self._correr()

        self.assertFalse(UbicacionLocalidad.objects.filter(localidad=self.esperanza_va).exists())
        self.assertIn(f"La Esperanza — municipio Villa Angela (id {self.esperanza_va.pk})", salida)
        self.assertIn("22001001 La Esperanza / Villa Ángela", salida)

    def test_nombre_repetido_que_concilia_por_municipio_se_asigna(self):
        """«La Esperanza» se repite, pero en Charata hay una sola fila con su municipio."""
        self._correr()

        self.assertEqual(UbicacionLocalidad.objects.get(localidad=self.esperanza_ch).id_fuente, "22002001")

    def test_nombre_que_solo_aparece_en_otro_municipio_es_ambiguo(self):
        salida = self._correr()

        self.assertFalse(UbicacionLocalidad.objects.filter(localidad=self.paraisal).exists())
        self.assertIn(f"El Paraisal — municipio Quitilipi (id {self.paraisal.pk}) · candidatos", salida)

    def test_una_localidad_no_conciliada_queda_sin_punto_y_reportada(self):
        salida = self._correr()

        self.assertFalse(UbicacionLocalidad.objects.filter(localidad=self.inexistente).exists())
        reporte = salida.split("No conciliadas (sin punto en el mapa")[1]
        self.assertIn(f"Paraje Inventado — municipio Quitilipi (id {self.inexistente.pk})", reporte)

    def test_simular_no_escribe(self):
        salida = self._correr("--simular")

        self.assertFalse(UbicacionLocalidad.objects.exists())
        self.assertIn("[simulación]", salida)

    def test_una_sola_ubicacion_por_localidad(self):
        self._correr()

        with self.assertRaises(IntegrityError), transaction.atomic():
            UbicacionLocalidad.objects.create(
                localidad=self.barranqueras, latitud=0, longitud=0, fuente="x", id_fuente="y"
            )

    def test_csv_mal_formado_corta_sin_escribir(self):
        self._escribir([FILAS[0].replace("-27.483333", "norte")])

        with self.assertRaisesMessage(CommandError, "no es un número"):
            self._correr()
        self.assertFalse(UbicacionLocalidad.objects.exists())

    def test_el_error_informa_la_linea_real_del_archivo(self):
        """El encabezado tiene un comentario: la tercera fila de datos está en la línea 5."""
        self._escribir([FILAS[0], FILAS[1], FILAS[2].replace("-27.510000", "norte")])

        with self.assertRaisesMessage(CommandError, "Línea 5: latitud «norte» no es un número."):
            self._correr()

    def test_nan_se_rechaza_con_su_linea(self):
        self._escribir([FILAS[0].replace("-58.933333", "NaN")])

        with self.assertRaisesMessage(CommandError, "Línea 3: longitud «NaN» no es un número."):
            self._correr()
        self.assertFalse(UbicacionLocalidad.objects.exists())

    def test_latitud_y_longitud_invertidas_se_rechazan(self):
        self._escribir(["22140010,Barranqueras,Barranqueras,San Fernando,-58.933333,-27.483333"])

        with self.assertRaisesMessage(CommandError, "Línea 3: latitud -58.933333 fuera de la provincia"):
            self._correr()
        self.assertFalse(UbicacionLocalidad.objects.exists())

    def test_coordenada_de_otra_provincia_se_rechaza(self):
        self._escribir(["22140010,Barranqueras,Barranqueras,San Fernando,-34.600000,-58.933333"])

        with self.assertRaisesMessage(CommandError, "latitud -34.600000 fuera de la provincia"):
            self._correr()

    def test_el_reporte_marca_las_que_conservan_una_ubicacion_anterior(self):
        """El comando no borra: si una localidad deja de conciliar, el reporte no puede decir «sin punto» a secas."""
        self._correr()
        self._escribir(FILAS[1:])

        salida = self._correr()

        self.assertEqual(UbicacionLocalidad.objects.get(localidad=self.barranqueras).id_fuente, "22140010")
        reporte = salida.split("No conciliadas (sin punto en el mapa")[1]
        self.assertIn(
            f"BARRANQUERAS — municipio Barranqueras (id {self.barranqueras.pk}) · conserva ubicación anterior "
            "(id_fuente 22140010)",
            reporte,
        )
        self.assertNotIn(f"Paraje Inventado — municipio Quitilipi (id {self.inexistente.pk}) · conserva", reporte)

    def test_la_marca_de_conservadas_cuesta_una_sola_consulta(self):
        from core.selectors.geografia import localidades_operativas
        from core.services.ubicaciones_localidades import cargar_ubicaciones, leer_csv

        localidades = list(localidades_operativas())
        filas = leer_csv(self.csv)
        cargar_ubicaciones(localidades, filas)

        with CaptureQueriesContext(connection) as consultas:
            resultado = cargar_ubicaciones(localidades, filas[1:3])

        selects = [q["sql"] for q in consultas.captured_queries if q["sql"].startswith("SELECT")]
        self.assertEqual(len(selects), 1, selects)

        self.assertEqual(resultado.conservadas, {self.barranqueras.pk: "22140010", self.esperanza_ch.pk: "22002001"})

    def test_csv_ausente(self):
        self.csv.unlink()

        with self.assertRaisesMessage(CommandError, "Falta el archivo"):
            self._correr()


class CsvVersionadoContraElCatalogoTests(TestCase):
    """El CSV del repo contra el fixture real del catálogo (TC-1181-07)."""

    fixtures = ["localidad_municipio_provincia"]

    def test_carga_el_csv_versionado_y_las_posiciones_caen_en_el_chaco(self):
        salida = io.StringIO()
        call_command("cargar_ubicaciones_localidades", stdout=salida)

        self.assertIn("Localidades del catálogo: 778", salida.getvalue())
        self.assertGreater(UbicacionLocalidad.objects.count(), 700)
        fuera_de_la_caja = UbicacionLocalidad.objects.exclude(
            latitud__range=(-28.5, -23.5), longitud__range=(-63.9, -57.8)
        )
        self.assertFalse(fuera_de_la_caja.exists())
        esperado = {
            "Barranqueras": "San Fernando",
            "Resistencia": "San Fernando",
            "Juan José Castelli": "General Güemes",
            "Las Breñas": "9 de Julio",
        }
        for nombre, departamento in esperado.items():
            with self.subTest(nombre=nombre):
                ubicacion = UbicacionLocalidad.objects.get(
                    localidad__nombre=nombre, localidad__municipio__provincia__nombre="Chaco"
                )
                self.assertEqual(ubicacion.departamento, departamento)
