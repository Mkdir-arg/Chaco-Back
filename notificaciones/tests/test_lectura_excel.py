"""Lectura del Excel de destinatarios (RN-007-02 a RN-007-06, RN-007-15, casos límite)."""

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase

from notificaciones.models import Descartado
from notificaciones.services.lectura_excel import EXCEL_MAX_BYTES, parsear_destinatarios
from notificaciones.tests.utils import XLSX, correos, xlsx


class LecturaExcelTests(SimpleTestCase):
    def test_criterio_de_aceptacion_7_validos_2_invalidos_1_duplicado(self):
        filas = [
            "email",
            "a@x.com",
            "b@x.com",
            "no-es-un-correo",
            "c@x.com",
            "A@X.com",  # duplicado de a@x.com sin distinguir mayúsculas
            "d@x.com",
            "e@x.com",
            "f@x.com",
            "mal@",
            "g@x.com",
        ]
        lectura = parsear_destinatarios(xlsx(filas))
        self.assertEqual(len(lectura.validos), 7)
        self.assertEqual(lectura.invalidos, 2)
        self.assertEqual(lectura.duplicados, 1)
        self.assertEqual(lectura.leidas, 10)

    def test_normaliza_a_minusculas_y_recorta(self):
        lectura = parsear_destinatarios(xlsx(["email", "  Persona@Ejemplo.COM  "]))
        self.assertEqual(lectura.validos, [(2, "persona@ejemplo.com")])

    def test_duplicados_case_insensitive_van_a_descartados(self):
        lectura = parsear_destinatarios(xlsx(["email", "a@x.com", "A@x.COM"]))
        self.assertEqual(lectura.validos, [(2, "a@x.com")])
        self.assertEqual(lectura.descartados, [(3, "A@x.COM", Descartado.Motivo.DUPLICADO)])

    def test_celda_con_varios_correos_se_descarta(self):
        lectura = parsear_destinatarios(xlsx(["email", "a@x.com; b@y.com", "c@x.com"]))
        self.assertEqual([email for _f, email in lectura.validos], ["c@x.com"])
        self.assertEqual(lectura.descartados[0][2], Descartado.Motivo.INVALIDO)

    def test_fila_con_otras_columnas_y_correo_vacio_es_vacio(self):
        lectura = parsear_destinatarios(xlsx([("email", "nombre"), ("a@x.com", "Ana"), ("", "Beto")]))
        self.assertEqual(lectura.descartados, [(3, "", Descartado.Motivo.VACIO)])
        self.assertEqual(lectura.invalidos, 1)

    def test_filas_vacias_del_todo_no_cuentan(self):
        lectura = parsear_destinatarios(xlsx(["email", "a@x.com", None, None, "b@x.com"]))
        self.assertEqual(lectura.leidas, 2)
        self.assertEqual(lectura.descartados, [])

    def test_encabezado_correo_o_mail_sin_acentos_ni_mayusculas(self):
        for encabezado in ("Correo", "MAIL", "Émail"):
            with self.subTest(encabezado=encabezado):
                lectura = parsear_destinatarios(xlsx([("Nombre", encabezado), ("Ana", "ana@x.com")]))
                self.assertEqual(lectura.validos, [(2, "ana@x.com")])

    def test_otras_columnas_se_ignoran(self):
        lectura = parsear_destinatarios(xlsx([("nombre", "email", "dni"), ("Ana", "ana@x.com", "123")]))
        self.assertEqual(lectura.validos, [(2, "ana@x.com")])

    def test_sin_encabezado_se_lee_la_columna_a_desde_la_fila_1(self):
        lectura = parsear_destinatarios(xlsx(["a@x.com", "b@x.com"]))
        self.assertEqual(lectura.validos, [(1, "a@x.com"), (2, "b@x.com")])

    def test_sin_ningun_valido_levanta_error(self):
        with self.assertRaisesMessage(ValidationError, "ningún correo válido"):
            parsear_destinatarios(xlsx(["email", "nada", "tampoco"]))

    def test_tope_de_5000(self):
        parsear_destinatarios(xlsx(["email", *correos(5000)]))
        with self.assertRaisesMessage(ValidationError, "el tope por campaña es 5.000"):
            parsear_destinatarios(xlsx(["email", *correos(5001)]))

    def test_no_xlsx_rechazado(self):
        for nombre in ("lista.xls", "lista.csv"):
            with self.subTest(nombre=nombre):
                archivo = SimpleUploadedFile(nombre, b"email\na@x.com\n", content_type="text/csv")
                with self.assertRaisesMessage(ValidationError, ".xlsx"):
                    parsear_destinatarios(archivo)

    def test_xlsx_que_no_es_excel(self):
        archivo = SimpleUploadedFile("lista.xlsx", b"esto no es un zip", content_type=XLSX)
        with self.assertRaisesMessage(ValidationError, "no es un Excel .xlsx válido"):
            parsear_destinatarios(archivo)

    def test_mas_de_2_mb_rechazado(self):
        archivo = SimpleUploadedFile("lista.xlsx", b"0" * (EXCEL_MAX_BYTES + 1), content_type=XLSX)
        with self.assertRaisesMessage(ValidationError, "2 MB"):
            parsear_destinatarios(archivo)

    def test_deja_el_archivo_al_principio(self):
        archivo = xlsx(["email", "a@x.com"])
        parsear_destinatarios(archivo)
        self.assertEqual(archivo.tell(), 0)
