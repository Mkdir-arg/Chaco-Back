import csv
import tempfile
from datetime import date
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase
from openpyxl import Workbook

from programas.models import Dispositivo, Merendero, TipoDispositivo


class ImportPadronCommandTests(TestCase):
    def test_admite_planilla_xlsx_normalizada(self):
        TipoDispositivo.objects.create(codigo="XLSX", nombre="Tipo XLSX")

        with tempfile.TemporaryDirectory() as directory:
            archivo = Path(directory) / "padron.xlsx"
            libro = Workbook()
            hoja = libro.active
            hoja.append(["entidad", "codigo", "nombre", "tipo", "domicilio", "responsable_nombre"])
            hoja.append(["DISPOSITIVO", "DIS-XLSX", "Hogar XLSX", "XLSX", "Calle 3", "Cora"])
            libro.save(archivo)

            call_command(
                "import_padron_dispositivos",
                "--file",
                str(archivo),
                "--fuente",
                "Ministerio",
                "--fecha",
                "2026-07-29",
                "--responsable",
                "Operador de carga",
            )

        self.assertTrue(Dispositivo.objects.filter(codigo="DIS-XLSX").exists())

    def test_normaliza_celdas_xlsx_no_textuales(self):
        with tempfile.TemporaryDirectory() as directory:
            archivo = Path(directory) / "padron.xlsx"
            libro = Workbook()
            hoja = libro.active
            hoja.append(["entidad", "codigo", "nombre", "domicilio", "responsable_nombre"])
            hoja.append(["MERENDERO", 184, "Merendero numérico", "Calle 184", "Cora"])
            libro.save(archivo)

            call_command(
                "import_padron_dispositivos",
                "--file",
                str(archivo),
                "--fuente",
                "Ministerio",
                "--fecha",
                "2026-07-29",
                "--responsable",
                "Operador de carga",
            )

        self.assertTrue(Merendero.objects.filter(codigo="184").exists())

    def test_informa_fila_invalida_sin_crear_registro(self):
        with tempfile.TemporaryDirectory() as directory:
            archivo = Path(directory) / "padron.csv"
            archivo.write_text(
                "entidad,codigo,nombre,domicilio,responsable_nombre,contacto_email\n"
                "MERENDERO,MER-INVALIDO,Inválido,Calle 1,Ana,no-es-email\n",
                encoding="utf-8",
            )

            call_command(
                "import_padron_dispositivos",
                "--file",
                str(archivo),
                "--fuente",
                "Ministerio",
                "--fecha",
                "2026-07-29",
                "--responsable",
                "Operador de carga",
            )

        self.assertFalse(Merendero.objects.filter(codigo="MER-INVALIDO").exists())

    def test_importa_dispositivo_y_merendero_con_procedencia(self):
        TipoDispositivo.objects.create(codigo="AM", nombre="Adulto Mayor")

        with tempfile.TemporaryDirectory() as directory:
            archivo = Path(directory) / "padron.csv"
            with archivo.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(
                    stream,
                    fieldnames=[
                        "entidad",
                        "codigo",
                        "nombre",
                        "tipo",
                        "domicilio",
                        "localidad",
                        "zona",
                        "barrio",
                        "dias_horarios",
                        "responsable_nombre",
                        "contacto_telefono",
                    ],
                )
                writer.writeheader()
                writer.writerows(
                    [
                        {
                            "entidad": "DISPOSITIVO",
                            "codigo": "DIS-001",
                            "nombre": "Hogar Norte",
                            "tipo": "AM",
                            "domicilio": "Calle 1",
                            "localidad": "Resistencia",
                            "zona": "",
                            "barrio": "",
                            "dias_horarios": "",
                            "responsable_nombre": "Ana",
                            "contacto_telefono": "3624-000000",
                        },
                        {
                            "entidad": "MERENDERO",
                            "codigo": "MER-001",
                            "nombre": "Rayito de Sol",
                            "tipo": "",
                            "domicilio": "Calle 2",
                            "localidad": "",
                            "zona": "Norte",
                            "barrio": "San Martín",
                            "dias_horarios": "Lunes 16 h",
                            "responsable_nombre": "Beto",
                            "contacto_telefono": "3624-111111",
                        },
                    ]
                )

            call_command(
                "import_padron_dispositivos",
                "--file",
                str(archivo),
                "--fuente",
                "Ministerio",
                "--fecha",
                "2026-07-29",
                "--responsable",
                "Operador de carga",
            )

        dispositivo = Dispositivo.objects.get(codigo="DIS-001")
        merendero = Merendero.objects.get(codigo="MER-001")
        self.assertEqual(dispositivo.fuente_padron, "Ministerio")
        self.assertEqual(merendero.fuente_padron, "Ministerio")
        self.assertEqual(dispositivo.fecha_padron, date(2026, 7, 29))
        self.assertEqual(merendero.responsable_padron, "Operador de carga")

    def test_omite_codigos_legacy_ignorando_mayusculas_y_espacios(self):
        tipo = TipoDispositivo.objects.create(codigo="LEG", nombre="Tipo legacy")
        Dispositivo.objects.create(
            codigo="dis   legacy",
            nombre="Dispositivo legacy",
            tipo=tipo,
        )
        Merendero.objects.create(
            codigo="mer   legacy",
            nombre="Merendero legacy",
            domicilio="Calle 1",
            responsable_nombre="Ana",
        )

        with tempfile.TemporaryDirectory() as directory:
            archivo = Path(directory) / "padron.csv"
            archivo.write_text(
                "entidad,codigo,nombre,tipo,domicilio,responsable_nombre\n"
                "DISPOSITIVO,  DIS LEGACY  ,Otro dispositivo,LEG,Calle 2,Beto\n"
                "MERENDERO,  MER LEGACY  ,Otro merendero,,Calle 3,Cora\n",
                encoding="utf-8",
            )

            call_command(
                "import_padron_dispositivos",
                "--file",
                str(archivo),
                "--fuente",
                "Ministerio",
                "--fecha",
                "2026-07-29",
                "--responsable",
                "Operador de carga",
            )

        self.assertEqual(Dispositivo.objects.count(), 1)
        self.assertEqual(Merendero.objects.count(), 1)
