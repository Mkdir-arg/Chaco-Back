"""``proponer_alias_siis``: clasifica las localidades core contra el padrón de SIIS y no escribe nada."""

import csv
import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from core.models import Localidad, Municipio, Provincia
from programas.models import AliasLocalidadSiis, LocalidadSiis, ProvinciaSiis
from programas.services.siis_envio import clave_nombre


def _siis_loc(provincia, siis_id, nombre):
    return LocalidadSiis.objects.create(provincia=provincia, siis_id=siis_id, nombre=nombre, clave=clave_nombre(nombre))


class ProponerAliasSiisTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        chaco = Provincia.objects.create(nombre="Chaco")
        otra = Provincia.objects.create(nombre="Corrientes")
        cls.m_resis = Municipio.objects.create(nombre="Resistencia", provincia=chaco)
        cls.m_plaza = Municipio.objects.create(nombre="Presidencia De La Plaza", provincia=chaco)
        cls.m_lejano = Municipio.objects.create(nombre="Municipio Sin Padron", provincia=chaco)
        cls.m_otro = Municipio.objects.create(nombre="Resistencia", provincia=otra)

        siis_chaco = ProvinciaSiis.objects.create(siis_id=1, nombre="CHACO", clave="chaco")
        cls.resistencia = _siis_loc(siis_chaco, 1, "RESISTENCIA")
        cls.plaza = _siis_loc(siis_chaco, 19, "PCIA. DE LA PLAZA")
        cls.dup_a = _siis_loc(siis_chaco, 50, "LA LOMA")
        cls.dup_b = _siis_loc(siis_chaco, 51, "LA LOMA")

        Localidad.objects.create(nombre="Resistencia", municipio=cls.m_resis)  # CRUZA
        Localidad.objects.create(nombre="Barrio Nuevo", municipio=cls.m_resis)  # PROPUESTA (municipio)
        Localidad.objects.create(nombre="Presidencia De La Plaza", municipio=cls.m_plaza)  # PROPUESTA (abreviatura)
        Localidad.objects.create(nombre="Paraje Perdido", municipio=cls.m_lejano)  # SIN_CANDIDATO
        Localidad.objects.create(nombre="La Loma", municipio=cls.m_lejano)  # repetida en el padrón
        Localidad.objects.create(nombre="Resistencia", municipio=cls.m_otro)  # otra provincia: no entra

    def _correr(self, **opciones):
        salida, err = StringIO(), StringIO()
        call_command("proponer_alias_siis", stdout=salida, stderr=err, **opciones)
        return list(csv.DictReader(StringIO(salida.getvalue()))), err.getvalue()

    def _por_nombre(self, filas):
        return {f["localidad_core"]: f for f in filas}

    def test_clasifica_cruza_propuesta_y_sin_candidato(self):
        filas, resumen = self._correr()
        f = self._por_nombre(filas)

        self.assertEqual(f["Resistencia"]["estado"], "CRUZA")
        self.assertEqual(f["Resistencia"]["siis_id"], "")

        self.assertEqual(f["Barrio Nuevo"]["estado"], "PROPUESTA")
        self.assertEqual(f["Barrio Nuevo"]["localidad_siis_propuesta"], "RESISTENCIA")
        self.assertEqual(f["Barrio Nuevo"]["siis_id"], "1")
        self.assertIn("municipio", f["Barrio Nuevo"]["motivo"])

        self.assertEqual(f["Presidencia De La Plaza"]["estado"], "PROPUESTA")
        self.assertEqual(f["Presidencia De La Plaza"]["localidad_siis_propuesta"], "PCIA. DE LA PLAZA")
        self.assertEqual(f["Presidencia De La Plaza"]["siis_id"], "19")
        self.assertIn("abreviaturas", f["Presidencia De La Plaza"]["motivo"])

        self.assertEqual(f["Paraje Perdido"]["estado"], "SIN_CANDIDATO")
        self.assertEqual(f["Paraje Perdido"]["localidad_siis_propuesta"], "")
        self.assertEqual(f["La Loma"]["estado"], "SIN_CANDIDATO")
        self.assertIn("repetido", f["La Loma"]["motivo"])

        self.assertEqual(len(filas), 5, "solo la provincia operativa")
        self.assertIn("1 CRUZA, 2 PROPUESTA, 2 SIN_CANDIDATO", resumen)

    def test_una_equivalencia_cargada_cuenta_como_cruza_y_una_sin_destino_no(self):
        siis_chaco = ProvinciaSiis.objects.get(siis_id=1)
        AliasLocalidadSiis.objects.create(
            provincia=siis_chaco, clave=clave_nombre("Barrio Nuevo"), texto="Barrio Nuevo", localidad=self.plaza
        )
        AliasLocalidadSiis.objects.create(
            provincia=siis_chaco, clave=clave_nombre("Paraje Perdido"), texto="Paraje Perdido", localidad=None
        )
        f = self._por_nombre(self._correr()[0])
        self.assertEqual(f["Barrio Nuevo"]["estado"], "CRUZA")
        self.assertEqual(f["Paraje Perdido"]["estado"], "SIN_CANDIDATO")
        self.assertIn("ya revisada", f["Paraje Perdido"]["motivo"])

    def test_mismo_nombre_con_propuestas_distintas_no_se_propone(self):
        # «Barrio Nuevo» ya está en Resistencia (→ 1); en el municipio de La Plaza daría 19.
        Localidad.objects.create(nombre="Barrio Nuevo", municipio=self.m_plaza)
        filas = [f for f in self._correr()[0] if f["localidad_core"] == "Barrio Nuevo"]
        self.assertEqual({f["estado"] for f in filas}, {"SIN_CANDIDATO"})
        self.assertTrue(all(f["siis_id"] == "" for f in filas))

    def test_no_escribe_en_la_base(self):
        antes = (Localidad.objects.count(), LocalidadSiis.objects.count(), AliasLocalidadSiis.objects.count())
        # Provincia de SIIS, localidades de SIIS, equivalencias y localidades core: cuatro lecturas.
        with self.assertNumQueries(4):
            self._correr()
        despues = (Localidad.objects.count(), LocalidadSiis.objects.count(), AliasLocalidadSiis.objects.count())
        self.assertEqual(antes, despues)

    def test_celdas_protegidas_contra_formulas(self):
        Localidad.objects.create(nombre='=HYPERLINK("http://x")', municipio=self.m_lejano)
        filas = self._correr()[0]
        celda = next(f["localidad_core"] for f in filas if "HYPERLINK" in f["localidad_core"])
        self.assertTrue(celda.startswith("'"), celda)

    def test_escribe_a_archivo_con_salida(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "propuesta.csv"
            call_command("proponer_alias_siis", salida=str(ruta), stderr=StringIO())
            with ruta.open(encoding="utf-8", newline="") as archivo:
                filas = list(csv.DictReader(archivo))
        self.assertEqual(len(filas), 5)

    def test_sin_catalogo_siis_avisa(self):
        ProvinciaSiis.objects.all().delete()
        with self.assertRaisesMessage(CommandError, "seed_catalogo_siis"):
            call_command("proponer_alias_siis", stdout=StringIO(), stderr=StringIO())
