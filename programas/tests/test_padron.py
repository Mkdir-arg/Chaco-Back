"""Tests del padrón de habilitados por Excel (#299, análisis #289; Cambio 57).

Desde el Cambio 57 el padrón es de la **convocatoria** (lo usan el link y la
app), tiene seis columnas y valida la identidad cuando trae nombre y apellido.
La cascada de identidad y el cruce automático se prueban en
``test_padron_identidad``; acá queda el parser, la carga y la pantalla.
"""

import ast
from datetime import date
from decimal import Decimal
from io import BytesIO, StringIO
from tempfile import TemporaryDirectory

from django.conf import settings
from django.contrib.auth.models import Group, Permission, User
from django.contrib.messages import constants as message_levels
from django.contrib.messages import get_messages
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import transaction
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from core.dni import dni_valido
from core.models import Localidad, Municipio, Provincia
from core.rbac import APP_LABEL, codename_de
from legajos.models import Ciudadano
from programas.forms import RelevamientoForm
from programas.management.commands import completar_casos_renaper, corregir_datos_siis
from programas.management.commands.seed_becas import ROL_ADMIN
from programas.models import (
    CARACTERES_SIN_TEXTO,
    Convocatoria,
    Formulario,
    PadronHabilitado,
    Relevamiento,
    Segmento,
)
from programas.services.padron import (
    cargar_padron,
    clave_localidad,
    esta_habilitado,
    fila_padron,
    normalizar_dni,
    normalizar_fecha,
    objetivo_con_identidad,
    parsear_padron,
    plantilla_padron,
    quitar_padron_propio,
    validar_casos_pendientes,
)
from programas.services.padron import dni_valido as padron_dni_valido
from programas.services.siis_envio import _digitos as siis_envio_digitos

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _xlsx(filas, nombre="padron.xlsx"):
    from openpyxl import Workbook

    libro = Workbook()
    hoja = libro.active
    for fila in filas:
        hoja.append(fila)
    buffer = BytesIO()
    libro.save(buffer)
    return SimpleUploadedFile(nombre, buffer.getvalue(), content_type=XLSX_MIME)


def _pares(entradas):
    return [(e["dni"], e["sexo"]) for e in entradas]


class _BasePadronTest(TestCase):
    def setUp(self):
        self.segmento = Segmento.objects.create(nombre="Seg", cupo_maximo=100)
        self.convocatoria = Convocatoria.objects.create(
            nombre="Conv",
            segmento=self.segmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        self.relevamiento = Relevamiento.objects.create(
            convocatoria=self.convocatoria,
            tipo=Relevamiento.Tipo.PUBLICO,
            fecha_asignada=date(2026, 6, 1),
            fecha_hasta=date(2026, 6, 30),
        )


class ParserPadronTests(TestCase):
    def test_parsea_filas_validas_y_reporta_rechazadas(self):
        archivo = _xlsx(
            [
                ("documento", "sexo"),  # encabezado: se saltea
                ("30.123.456", "f"),
                (28111222, "MASCULINO"),
                ("", "F"),  # sin dni: rechazada
                ("27000111", "Z"),  # sexo inválido: rechazada
                ("30123456", "M"),  # dni duplicado: rechazada
            ]
        )
        entradas, resumen = parsear_padron(archivo)
        self.assertEqual(_pares(entradas), [("30123456", "F"), ("28111222", "M")])
        self.assertEqual(resumen.rechazadas, 3)
        self.assertEqual(resumen.validas, 2)
        self.assertEqual(resumen.con_identidad, 0)

    def test_sin_encabezado_tambien_funciona(self):
        entradas, resumen = parsear_padron(_xlsx([("30123456", "F")]))
        self.assertEqual(_pares(entradas), [("30123456", "F")])
        self.assertEqual(resumen.rechazadas, 0)

    def test_seis_columnas_con_identidad(self):
        """Cambio 57: nombre, apellido, fecha y localidad viajan por fila; la
        identidad completa se cuenta aparte."""
        entradas, resumen = parsear_padron(
            _xlsx(
                [
                    ("documento", "sexo", "nombre", "apellido", "fecha de nacimiento", "localidad"),
                    ("36210951", "F", " Pamela  Janet ", "Romero", "14/03/2010", "Resistencia"),
                    ("28111222", "M", "", "", "", ""),
                    ("20111333", "F", "Ana", "", "2001-05-09", "Sáenz Peña"),
                ]
            )
        )
        self.assertEqual(resumen.validas, 3)
        self.assertEqual(resumen.con_identidad, 1)  # Ana no tiene apellido
        pamela = entradas[0]
        self.assertEqual(pamela["nombre"], "Pamela Janet")
        self.assertEqual(pamela["apellido"], "Romero")
        self.assertEqual(pamela["fecha_nacimiento"], date(2010, 3, 14))
        self.assertEqual(pamela["localidad_texto"], "Resistencia")
        self.assertEqual(entradas[2]["fecha_nacimiento"], date(2001, 5, 9))

    def test_fecha_invalida_no_rechaza_la_fila(self):
        entradas, resumen = parsear_padron(_xlsx([("30123456", "F", "Ana", "Paz", "ayer", "")]))
        self.assertEqual(len(entradas), 1)
        self.assertIsNone(entradas[0]["fecha_nacimiento"])
        self.assertEqual(resumen.fechas_invalidas, 1)
        self.assertEqual(resumen.con_identidad, 1)

    def test_fecha_como_celda_de_excel(self):
        entradas, _ = parsear_padron(_xlsx([("30123456", "F", "Ana", "Paz", date(1991, 3, 14), "")]))
        self.assertEqual(entradas[0]["fecha_nacimiento"], date(1991, 3, 14))

    def test_extension_invalida(self):
        archivo = SimpleUploadedFile("padron.csv", b"30123456,F", content_type="text/csv")
        with self.assertRaises(ValidationError):
            parsear_padron(archivo)

    def test_contenido_no_excel(self):
        archivo = SimpleUploadedFile("padron.xlsx", b"esto no es un excel", content_type=XLSX_MIME)
        with self.assertRaises(ValidationError):
            parsear_padron(archivo)

    def test_sin_filas_validas(self):
        with self.assertRaises(ValidationError):
            parsear_padron(_xlsx([("documento", "sexo"), ("", "")]))


class NormalizacionTests(TestCase):
    def test_fechas(self):
        self.assertEqual(normalizar_fecha("14/03/2010"), (date(2010, 3, 14), False))
        self.assertEqual(normalizar_fecha("2010-03-14"), (date(2010, 3, 14), False))
        self.assertEqual(normalizar_fecha(None), (None, False))
        self.assertEqual(normalizar_fecha("   "), (None, False))
        self.assertEqual(normalizar_fecha("14/13/2010"), (None, True))
        # Serial de Excel: 40251 = 14/03/2010.
        self.assertEqual(normalizar_fecha(40251), (date(2010, 3, 14), False))

    def test_clave_localidad(self):
        self.assertEqual(clave_localidad("Sáenz Peña"), clave_localidad("SAENZ PENA"))
        self.assertEqual(clave_localidad("  Resistencia "), "resistencia")
        self.assertNotEqual(clave_localidad("Rcia."), clave_localidad("Resistencia"))


class NormalizarDniTests(SimpleTestCase):
    """RED-47: las cuatro puertas que normalizan un DNI tienen que dar lo mismo.

    La canónica es ``padron.normalizar_dni``; las otras tres son copias que
    viven en los comandos y en el armado del payload de SIIS. Cada una recibe
    el DNI de una fuente distinta —openpyxl entrega ``float``, el driver de
    MySQL entrega ``Decimal`` cuando la columna de ``ciudadanos_renaper`` es
    ``DECIMAL``— y cualquiera de las dos, sin cast, agrega un ``0`` al final:
    ``30123456.0`` → ``"301234560"``, que no cruza con nada y se informa como
    «0 corregidos».
    """

    PUERTAS = {
        "padron.normalizar_dni": normalizar_dni,
        "completar_casos_renaper._solo_digitos": completar_casos_renaper._solo_digitos,
        "corregir_datos_siis._digitos": corregir_datos_siis._digitos,
        "siis_envio._digitos": siis_envio_digitos,
    }

    CASOS = [
        (30123456.0, "30123456"),
        (Decimal("30123456.0"), "30123456"),
        ("30.123.456", "30123456"),
        (" 30123456 ", "30123456"),
        ("M30123456", "30123456"),
        (None, ""),
    ]

    def test_las_cuatro_puertas_normalizan_igual(self):
        for nombre, funcion in self.PUERTAS.items():
            for crudo, esperado in self.CASOS:
                with self.subTest(puerta=nombre, crudo=repr(crudo)):
                    self.assertEqual(funcion(crudo), esperado)

    def test_float_y_decimal_no_agregan_un_cero(self):
        """El borde exacto de la ficha: el cast tiene que ser al entero, no a texto."""
        for nombre, funcion in self.PUERTAS.items():
            with self.subTest(puerta=nombre):
                self.assertEqual(funcion(30123456.0), "30123456")
                self.assertEqual(funcion(Decimal("30123456.0")), "30123456")

    def test_lo_que_no_es_un_entero_disfrazado_sigue_yendo_por_texto(self):
        """Un decimal con parte fraccionaria o un ``NaN`` no pueden romper la función."""
        self.assertEqual(normalizar_dni(Decimal("30123456.5")), "301234565")
        self.assertEqual(normalizar_dni(float("nan")), "")
        self.assertEqual(normalizar_dni(Decimal("NaN")), "")


class EstaHabilitadoTests(_BasePadronTest):
    def test_sin_padron_el_link_es_abierto(self):
        self.assertTrue(esta_habilitado(self.relevamiento, "99999999", "F"))
        self.assertTrue(esta_habilitado(self.convocatoria, "99999999", "F"))

    def test_matchea_con_normalizacion_en_ambos_sentidos(self):
        cargar_padron(self.relevamiento, None, [("30123456", "F")])
        self.assertTrue(esta_habilitado(self.relevamiento, "30.123.456", "femenino"))
        self.assertFalse(esta_habilitado(self.relevamiento, "30123456", "M"))
        self.assertFalse(esta_habilitado(self.relevamiento, "11111111", "F"))

    def test_reemplazo_total_con_efecto_inmediato(self):
        cargar_padron(self.convocatoria, None, [("30123456", "F")])
        cargar_padron(self.convocatoria, None, [("28111222", "M")])
        self.assertFalse(esta_habilitado(self.relevamiento, "30123456", "F"))
        self.assertTrue(esta_habilitado(self.relevamiento, "28111222", "M"))
        self.assertEqual(self.convocatoria.padron.count(), 1)

    def test_el_padron_es_de_la_convocatoria_y_lo_comparten_sus_relevamientos(self):
        """Cambio 57: un solo Excel para el link y para el territorial."""
        territorial = User.objects.create_user("terri_pad")
        rel_campo = Relevamiento.objects.create(
            convocatoria=self.convocatoria,
            territorial=territorial,
            fecha_asignada=date(2026, 6, 1),
            zona="Zona",
        )
        cargar_padron(self.convocatoria, None, [("30123456", "F")])
        self.assertTrue(esta_habilitado(rel_campo, "30123456", "F"))
        self.assertTrue(esta_habilitado(self.relevamiento, "30123456", "F"))
        self.assertFalse(esta_habilitado(rel_campo, "99999999", "F"))


class CargaConIdentidadTests(_BasePadronTest):
    def setUp(self):
        super().setUp()
        provincia = Provincia.objects.create(nombre="Chaco")
        municipio = Municipio.objects.create(nombre="San Fernando", provincia=provincia)
        self.resistencia = Localidad.objects.create(nombre="Resistencia", municipio=municipio)

    def test_guarda_identidad_y_cruza_localidad_por_nombre(self):
        resumen = cargar_padron(
            self.convocatoria,
            None,
            [
                {
                    "dni": "36210951",
                    "sexo": "F",
                    "nombre": "Pamela Janet",
                    "apellido": "Romero",
                    "fecha_nacimiento": date(2010, 3, 14),
                    "localidad_texto": "RESISTENCIA",
                },
                {"dni": "28111222", "sexo": "M", "localidad_texto": "Rcia."},
            ],
        )
        fila = fila_padron(self.convocatoria, "36.210.951", "femenino")
        self.assertTrue(fila.tiene_identidad)
        self.assertEqual(fila.localidad, self.resistencia)
        self.assertEqual(fila.localidad_texto, "RESISTENCIA")
        otra = fila_padron(self.convocatoria, "28111222", "M")
        self.assertFalse(otra.tiene_identidad)
        self.assertIsNone(otra.localidad)
        self.assertEqual(otra.localidad_texto, "Rcia.")
        self.assertEqual(resumen.validas, 2)
        self.assertEqual(resumen.con_identidad, 1)
        self.assertEqual(resumen.localidades_no_reconocidas, ["Rcia."])

    def test_las_tuplas_historicas_siguen_valiendo(self):
        """RN-7: un padrón de dos columnas habilita y no valida."""
        cargar_padron(self.convocatoria, None, [("30123456", "F")])
        fila = fila_padron(self.convocatoria, "30123456", "F")
        self.assertFalse(fila.tiene_identidad)

    def test_fila_padron_sin_dni_o_sexo_es_none(self):
        cargar_padron(self.convocatoria, None, [("30123456", "F")])
        self.assertIsNone(fila_padron(self.convocatoria, "", "F"))
        self.assertIsNone(fila_padron(self.convocatoria, "30123456", "X"))


class FormSinPadronTests(_BasePadronTest):
    def test_el_alta_de_relevamiento_ya_no_tiene_padron(self):
        form = RelevamientoForm(
            data={
                "tipo": Relevamiento.Tipo.PUBLICO,
                "convocatoria": self.convocatoria.pk,
                "fecha_asignada": "2026-07-01T08:00",
                "fecha_hasta": "2026-07-31T18:00",
            },
            puede_publico=True,
        )
        self.assertNotIn("padron", form.fields)
        self.assertTrue(form.is_valid(), form.errors)
        rel = form.save()
        self.assertTrue(esta_habilitado(rel, "1234567", "F"))


class PadronConvocatoriaViewTests(_BasePadronTest):
    """Alta y reemplazo desde la convocatoria (Cambio 57)."""

    def setUp(self):
        super().setUp()
        call_command("seed_becas", stdout=StringIO())
        grupo_admin = Group.objects.get(name=ROL_ADMIN)
        self.admin = User.objects.create_user("admin_pad", password="x")
        self.admin.groups.add(grupo_admin)
        self.sin_permiso = User.objects.create_user("sin_pad", password="x")

    def _url(self):
        return reverse("becas:convocatoria_padron", args=[self.convocatoria.pk])

    def test_carga_ok_y_redirige_a_la_convocatoria(self):
        self.client.force_login(self.admin)
        resp = self.client.post(
            self._url(),
            {"padron": _xlsx([("documento", "sexo", "nombre", "apellido"), ("30123456", "F", "Ana", "Paz")])},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse("becas:convocatoria_detalle", args=[self.convocatoria.pk]), resp.url)
        self.assertTrue(esta_habilitado(self.relevamiento, "30123456", "F"))
        self.convocatoria.refresh_from_db()
        self.assertTrue(self.convocatoria.padron_archivo)

    def test_sin_archivo_avisa(self):
        self.client.force_login(self.admin)
        resp = self.client.post(self._url(), {})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(self.convocatoria.padron.count(), 0)

    def test_archivo_invalido_no_borra_el_padron_anterior(self):
        cargar_padron(self.convocatoria, None, [("11111111", "M")])
        self.client.force_login(self.admin)
        self.client.post(self._url(), {"padron": SimpleUploadedFile("p.xlsx", b"no excel", content_type=XLSX_MIME)})
        self.assertEqual(list(self.convocatoria.padron.values_list("dni", flat=True)), ["11111111"])

    def test_sin_capacidad_no_puede(self):
        self.client.force_login(self.sin_permiso)
        resp = self.client.post(self._url(), {"padron": _xlsx([("30123456", "F")])})
        self.assertNotEqual(resp.status_code, 200)
        self.assertEqual(self.convocatoria.padron.count(), 0)

    def test_solo_post(self):
        self.client.force_login(self.admin)
        resp = self.client.get(self._url())
        self.assertEqual(resp.status_code, 405)

    def test_la_url_por_relevamiento_es_el_padron_propio(self):
        """Cambio 74: la ruta por relevamiento volvió, pero como padrón PROPIO
        (pisa al de la convocatoria), y solo por POST."""
        url = reverse("becas:relevamiento_padron", args=[self.relevamiento.pk])
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(url).status_code, 405)

    def test_plantilla_descargable(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse("becas:convocatoria_padron_plantilla", args=[self.convocatoria.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], XLSX_MIME)
        self.assertIn("plantilla-padron-habilitados.xlsx", resp["Content-Disposition"])
        from openpyxl import load_workbook

        hoja = load_workbook(BytesIO(resp.content)).active
        encabezados = [c.value for c in next(hoja.iter_rows(min_row=1, max_row=1))]
        self.assertEqual(encabezados, ["documento", "sexo", "nombre", "apellido", "fecha de nacimiento", "localidad"])

    def test_la_plantilla_se_puede_volver_a_cargar(self):
        """El ejemplo que descargamos tiene que pasar por nuestro propio parser."""
        entradas, resumen = parsear_padron(
            SimpleUploadedFile("plantilla.xlsx", plantilla_padron(), content_type=XLSX_MIME)
        )
        self.assertEqual(resumen.validas, 2)
        self.assertEqual(resumen.con_identidad, 1)
        self.assertEqual(entradas[0]["fecha_nacimiento"], date(1991, 3, 14))

    def test_el_detalle_de_la_convocatoria_muestra_el_padron(self):
        cargar_padron(
            self.convocatoria,
            None,
            [{"dni": "30123456", "sexo": "F", "nombre": "Ana", "apellido": "Paz"}, ("28111222", "M")],
        )
        self.client.force_login(self.admin)
        try:
            resp = self.client.get(reverse("becas:convocatoria_detalle", args=[self.convocatoria.pk]))
        except AttributeError as exc:  # bug conocido del test client local (Py3.14 + Dj4.2)
            if "dicts" not in str(exc):
                raise
            return
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Padrón de habilitados")
        self.assertContains(resp, "2 habilitados")
        self.assertContains(resp, reverse("becas:convocatoria_padron_plantilla", args=[self.convocatoria.pk]))


class PadronPorRelevamientoTests(_BasePadronTest):
    """Cambio 74: el padrón de la convocatoria se hereda; el propio de un
    relevamiento lo pisa solo para ese relevamiento."""

    def setUp(self):
        super().setUp()
        territorial = User.objects.create_user("terri_c59")
        self.rel_campo = Relevamiento.objects.create(
            convocatoria=self.convocatoria,
            territorial=territorial,
            fecha_asignada=date(2026, 6, 1),
            zona="Zona",
        )

    def test_hereda_hasta_tener_propio_y_el_propio_pisa(self):
        cargar_padron(self.convocatoria, None, [("30123456", "F")])
        # Los dos relevamientos heredan.
        self.assertTrue(esta_habilitado(self.relevamiento, "30123456", "F"))
        self.assertTrue(esta_habilitado(self.rel_campo, "30123456", "F"))
        # El público carga padrón propio: pisa al heredado SOLO para él.
        cargar_padron(self.relevamiento, None, [("28111222", "M")])
        self.assertFalse(esta_habilitado(self.relevamiento, "30123456", "F"))
        self.assertTrue(esta_habilitado(self.relevamiento, "28111222", "M"))
        self.assertTrue(esta_habilitado(self.rel_campo, "30123456", "F"))  # sigue heredando
        self.assertFalse(esta_habilitado(self.rel_campo, "28111222", "M"))

    def test_quitar_el_propio_vuelve_a_heredar(self):
        from programas.services.padron import origen_padron, quitar_padron_propio

        cargar_padron(self.convocatoria, None, [("30123456", "F")])
        cargar_padron(self.relevamiento, None, [("28111222", "M")])
        self.assertEqual(origen_padron(self.relevamiento), "propio")
        filas = quitar_padron_propio(self.relevamiento)
        self.assertEqual(filas, 1)
        self.assertEqual(origen_padron(self.relevamiento), "convocatoria")
        self.assertTrue(esta_habilitado(self.relevamiento, "30123456", "F"))
        self.assertFalse(esta_habilitado(self.relevamiento, "28111222", "M"))

    def test_identificar_usa_el_padron_efectivo(self):
        from programas.services.identidad import identificar

        cargar_padron(
            self.convocatoria,
            None,
            [{"dni": "30123456", "sexo": "F", "nombre": "Ana", "apellido": "Paz"}],
        )
        cargar_padron(
            self.relevamiento,
            None,
            [{"dni": "30123456", "sexo": "F", "nombre": "Maria", "apellido": "Gomez"}],
        )
        con_propio = identificar(self.relevamiento, "30123456", "F")
        heredado = identificar(self.rel_campo, "30123456", "F")
        self.assertEqual(con_propio["datos"]["nombre"], "Maria")
        self.assertEqual(heredado["datos"]["nombre"], "Ana")

    def test_el_cruce_no_pisa_las_respuestas_del_caso(self):
        """Los pendientes se leen sin sus columnas JSON pesadas; al validarlos,
        esas columnas quedan exactamente como estaban."""
        from programas.models import Formulario

        caso = Formulario.objects.create(
            relevamiento=self.rel_campo,
            datos_identificacion={"dni": "30123456", "sexo": "F"},
            data={"globales": {"g1": "hola"}},
            respuestas={"g-1": "hola"},
            definicion={"version": 1},
            datos_siis={"barrio": "Centro"},
        )
        resumen = cargar_padron(
            self.convocatoria, None, [{"dni": "30123456", "sexo": "F", "nombre": "Ana", "apellido": "Paz"}]
        )
        caso.refresh_from_db()
        self.assertEqual(resumen.casos_validados, 1)
        self.assertTrue(caso.validado_renaper)
        self.assertEqual(caso.datos_identificacion["nombre"], "Ana")
        self.assertEqual(caso.data, {"globales": {"g1": "hola"}})
        self.assertEqual(caso.respuestas, {"g-1": "hola"})
        self.assertEqual(caso.definicion, {"version": 1})
        self.assertEqual(caso.datos_siis, {"barrio": "Centro"})

    def test_la_carga_valida_los_casos_de_su_alcance(self):
        from programas.models import Formulario

        pendiente_publico = Formulario.objects.create(
            relevamiento=self.relevamiento, datos_identificacion={"dni": "30123456", "sexo": "F"}
        )
        pendiente_campo = Formulario.objects.create(
            relevamiento=self.rel_campo, datos_identificacion={"dni": "30123456", "sexo": "F"}
        )
        # El público tiene padrón propio SIN identidad: su caso no valida acá.
        cargar_padron(self.relevamiento, None, [("30123456", "F")])
        resumen = cargar_padron(
            self.convocatoria,
            None,
            [{"dni": "30123456", "sexo": "F", "nombre": "Ana", "apellido": "Paz"}],
        )
        pendiente_publico.refresh_from_db()
        pendiente_campo.refresh_from_db()
        self.assertEqual(resumen.casos_validados, 1)
        self.assertTrue(pendiente_campo.validado_renaper)  # hereda: lo valida la convocatoria
        self.assertFalse(pendiente_publico.validado_renaper)  # su padrón propio manda
        # Reemplazo el propio por uno con identidad: ahora valida su caso.
        resumen = cargar_padron(
            self.relevamiento,
            None,
            [{"dni": "30123456", "sexo": "F", "nombre": "Maria", "apellido": "Gomez"}],
        )
        pendiente_publico.refresh_from_db()
        self.assertEqual(resumen.casos_validados, 1)
        self.assertTrue(pendiente_publico.validado_renaper)

    def test_objetivo_con_identidad_prefiere_el_efectivo(self):
        from programas.services.padron import objetivo_con_identidad

        cargar_padron(
            self.convocatoria,
            None,
            [{"dni": "30123456", "sexo": "F", "nombre": "Ana", "apellido": "Paz"}],
        )
        # Sin propios: cualquiera de los dos sirve (el primero de la lista).
        elegido = objetivo_con_identidad([self.rel_campo, self.relevamiento], "30123456", "F")
        self.assertEqual(elegido, self.rel_campo)
        # El de campo carga un propio SIN esa persona: deja de servir.
        cargar_padron(self.rel_campo, None, [("28111222", "M")])
        elegido = objetivo_con_identidad([self.rel_campo, self.relevamiento], "30123456", "F")
        self.assertEqual(elegido, self.relevamiento)


class PadronRelevamientoViewTests(_BasePadronTest):
    """Carga y quita del padrón propio desde el detalle del relevamiento."""

    def setUp(self):
        super().setUp()
        call_command("seed_becas", stdout=StringIO())
        self.admin = User.objects.create_user("admin_pad59", password="x")
        grupo = Group.objects.get(name=ROL_ADMIN)
        # El relevamiento del fixture es público: el alcance exige la capacidad
        # de públicos (en la base real la asigna users.0025; acá, syncdb).
        from django.contrib.auth.models import Permission

        from core.rbac import APP_LABEL, codename_de

        grupo.permissions.add(
            Permission.objects.get(
                content_type__app_label=APP_LABEL, codename=codename_de("becas.relevamiento.publico")
            )
        )
        self.admin.groups.add(grupo)

    def test_carga_quita_y_permisos(self):
        self.client.force_login(self.admin)
        url = reverse("becas:relevamiento_padron", args=[self.relevamiento.pk])
        resp = self.client.post(
            url, {"padron": _xlsx([("documento", "sexo", "nombre", "apellido"), ("30123456", "F", "Ana", "Paz")])}
        )
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse("becas:relevamiento_detalle", args=[self.relevamiento.pk]), resp.url)
        self.relevamiento.refresh_from_db()
        self.assertEqual(self.relevamiento.padron_propio.count(), 1)
        self.assertTrue(self.relevamiento.padron_archivo)

        resp = self.client.post(reverse("becas:relevamiento_padron_quitar", args=[self.relevamiento.pk]))
        self.assertEqual(resp.status_code, 302)
        self.relevamiento.refresh_from_db()
        self.assertEqual(self.relevamiento.padron_propio.count(), 0)
        self.assertFalse(self.relevamiento.padron_archivo)

        sin_permiso = User.objects.create_user("sin_pad59", password="x")
        self.client.force_login(sin_permiso)
        resp = self.client.post(url, {"padron": _xlsx([("30123456", "F")])})
        self.assertNotEqual(resp.status_code, 200)
        self.assertEqual(self.relevamiento.padron_propio.count(), 0)


class ResumenFijoPadronTests(_BasePadronTest):
    """P-DA5: un solo aviso por carga (nivel del peor resultado) y resumen fijo en el detalle."""

    def setUp(self):
        super().setUp()
        call_command("seed_becas", stdout=StringIO())
        self.admin = User.objects.create_user("admin_resumen", password="x")
        self.admin.groups.add(Group.objects.get(name=ROL_ADMIN))
        self.client.force_login(self.admin)
        self.url = reverse("becas:convocatoria_padron", args=[self.convocatoria.pk])
        self.detalle = reverse("becas:convocatoria_detalle", args=[self.convocatoria.pk])

    def _cargar(self, filas):
        return self.client.post(self.url, {"padron": _xlsx([("documento", "sexo", "nombre", "apellido")] + filas)})

    def test_con_filas_ignoradas_el_mensaje_es_uno_y_warning(self):
        resp = self._cargar([("30123456", "F", "Ana", "Paz"), ("xx", "F", "Bad", "Row")])
        msgs = list(get_messages(resp.wsgi_request))
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0].level, message_levels.WARNING)
        self.assertIn("ignorada", msgs[0].message)

    def test_sin_problemas_el_mensaje_es_success(self):
        resp = self._cargar([("30123456", "F", "Ana", "Paz")])
        msgs = list(get_messages(resp.wsgi_request))
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0].level, message_levels.SUCCESS)

    def test_el_detalle_muestra_el_resumen_fijo_y_la_segunda_carga_lo_reemplaza(self):
        self._cargar([("30123456", "F", "Ana", "Paz"), ("xx", "F", "Bad", "Row")])
        for _ in range(2):  # persiste entre visitas
            resp = self.client.get(self.detalle)
            self.assertContains(resp, "Última carga del padrón")
            self.assertContains(resp, "1 habilitados")
            self.assertContains(resp, "1 filas ignoradas")
        self._cargar([("30123456", "F", "Ana", "Paz"), ("30123457", "M", "Luis", "Paz")])
        resp = self.client.get(self.detalle)
        self.assertContains(resp, "2 habilitados")
        self.assertNotContains(resp, "filas ignoradas")

    def test_el_detalle_del_relevamiento_muestra_su_resumen(self):
        from django.contrib.auth.models import Permission

        from core.rbac import APP_LABEL, codename_de

        Group.objects.get(name=ROL_ADMIN).permissions.add(
            Permission.objects.get(
                content_type__app_label=APP_LABEL, codename=codename_de("becas.relevamiento.publico")
            )
        )
        url = reverse("becas:relevamiento_padron", args=[self.relevamiento.pk])
        self.client.post(url, {"padron": _xlsx([("documento", "sexo"), ("30123456", "F")])})
        resp = self.client.get(reverse("becas:relevamiento_detalle", args=[self.relevamiento.pk]))
        self.assertContains(resp, "Última carga del padrón")
        # el resumen de la convocatoria no se filtra al relevamiento de otra carga
        resp = self.client.get(self.detalle)
        self.assertNotContains(resp, "Última carga del padrón")

    def test_tolera_un_request_sin_sesion(self):
        """RED-74: el arreglo `7feb9d83` se mergeó sin ningún test.

        `_resumen_fijo_padron` leía `request.session` directo. Un request que no pasó
        por `SessionMiddleware` —un `RequestFactory` crudo, un render fuera del ciclo
        normal— no tiene el atributo y la pantalla moría con `AttributeError`, o sea
        **500** en el detalle de la convocatoria. Ahora devuelve `None`, que es lo
        mismo que una sesión sin resumen cargado.
        """
        from django.test import RequestFactory

        from programas.views.relevamientos import _resumen_fijo_padron

        request = RequestFactory().get(self.detalle)

        self.assertFalse(hasattr(request, "session"))
        self.assertIsNone(_resumen_fijo_padron(request, f"conv-{self.convocatoria.pk}"))

    def test_con_sesion_y_resumen_cargado_si_devuelve_el_texto(self):
        """Control del andamio: el `None` de arriba es por la sesión ausente y no
        porque la función devuelva `None` siempre."""
        from programas.views.relevamientos import _clave_resumen_padron, _resumen_fijo_padron

        self._cargar([("30123456", "F", "Ana", "Paz")])
        clave = f"conv-{self.convocatoria.pk}"
        request = self.client.get(self.detalle).wsgi_request

        self.assertIn(_clave_resumen_padron(clave), request.session)
        self.assertIn("1 habilitados", _resumen_fijo_padron(request, clave)["texto"])


class IdentidadDelPadronTests(_BasePadronTest):
    """RED-77: RN-2 escrita una sola vez para la fila y para el queryset.

    La property `PadronHabilitado.tiene_identidad` usa `strip()`; los cruces
    masivos de `services/padron.py` filtraban con
    `.exclude(nombre="").exclude(apellido="")`, **sin** `strip()`. Una fila con
    `nombre="  "` —que puede entrar por el admin, un fixture o una migración; el
    parser del Excel no la deja pasar— la validaba el cruce automático y la
    rechazaba el botón manual de la revisión. Las dos mitades ahora salen del
    mismo lugar: `PadronHabilitadoQuerySet.con_identidad()`.
    """

    #: Las combinaciones de identidad que puede tener una fila. Las últimas son
    #: los espacios que **no** son ASCII: `\xa0` es el que deja un copy&paste de
    #: una página web o de un PDF, y es el que `\s` de MariaDB no reconoce.
    CASOS = [
        ("40000001", "Ana", "Paz", True),
        ("40000002", "", "Paz", False),
        ("40000003", "Ana", "", False),
        ("40000004", "", "", False),
        ("40000005", "   ", "Paz", False),
        ("40000006", "Ana", "   ", False),
        ("40000007", "\t", "Paz", False),
        ("40000008", "\xa0", "Paz", False),
        ("40000009", "　", "Paz", False),
        ("40000010", "Ana\xa0Paz", "Paz", True),
        ("40000011", "Añá", "Óé", True),
    ]

    def setUp(self):
        super().setUp()
        cache.clear()
        call_command("seed_becas", stdout=StringIO())
        for dni, nombre, apellido, _ in self.CASOS:
            PadronHabilitado.objects.create(
                convocatoria=self.convocatoria,
                dni=dni,
                sexo="F",
                nombre=nombre,
                apellido=apellido,
            )

    def test_property_y_queryset_coinciden(self):
        con_identidad = set(
            PadronHabilitado.objects.con_identidad().values_list("dni", flat=True),
        )
        for dni, nombre, apellido, esperado in self.CASOS:
            with self.subTest(dni=dni, nombre=repr(nombre), apellido=repr(apellido)):
                fila = PadronHabilitado.objects.get(dni=dni)
                self.assertEqual(fila.tiene_identidad, esperado)
                self.assertEqual(
                    dni in con_identidad,
                    esperado,
                    "La property y `con_identidad()` dicen cosas distintas de la misma fila.",
                )

    def test_la_clase_cubre_exactamente_lo_que_saca_strip(self):
        """La lista literal de `CARACTERES_SIN_TEXTO` no se puede desfasar de
        `str.strip()`: si Unicode suma un espacio y Python lo adopta, acá se ve.

        Es lo que sostiene la equivalencia con la property: el motor recibe la
        misma lista de caracteres que `strip()` saca, ni uno más ni uno menos.
        """
        self.assertEqual(
            set(CARACTERES_SIN_TEXTO),
            {caracter for caracter in map(chr, range(0x110000)) if caracter.isspace()},
        )
        # Ninguno es especial dentro de una clase de regex: la clase se arma por
        # interpolación, sin escapar nada.
        self.assertFalse(set(CARACTERES_SIN_TEXTO) & set("]^-\\"))

    def _caso_pendiente(self, dni, genero="F"):
        """Un caso sin validar, con el género que el cruce necesita para ubicar
        su fila del padrón (`_identidad_del_caso` devuelve `(dni, genero)`)."""
        ciudadano = Ciudadano.objects.create(dni=dni, genero=genero, nombre="", apellido="")
        return Formulario.objects.create(
            relevamiento=self.relevamiento,
            ciudadano=ciudadano,
            celular="3624000000",
        )

    def test_el_cruce_automatico_no_valida_un_caso_con_identidad_en_blanco(self):
        """El efecto que se veía: el cruce masivo validaba a quien el botón
        manual rechazaba. `validar_casos_pendientes` recorre el mismo criterio.

        El caso lleva `genero` a propósito: sin él, `_identidad_del_caso` devuelve
        `(dni, "")`, el cruce no encuentra ninguna fila y el test pasaría por el
        motivo equivocado —pasaba hasta con la regla vieja—.
        """
        formulario = self._caso_pendiente("40000005")

        validados = validar_casos_pendientes(self.convocatoria)

        formulario.refresh_from_db()
        self.assertEqual(validados, 0)
        self.assertFalse(formulario.validado_renaper)

    def test_el_cruce_automatico_si_valida_un_caso_con_identidad_completa(self):
        """Control del anterior: con la misma receta y una fila que sí tiene
        identidad, el cruce valida. Sin este par, `validados == 0` no significa
        nada."""
        formulario = self._caso_pendiente("40000001")

        validados = validar_casos_pendientes(self.convocatoria)

        formulario.refresh_from_db()
        self.assertEqual(validados, 1)
        self.assertTrue(formulario.validado_renaper)

    def test_objetivo_con_identidad_ignora_la_fila_en_blanco(self):
        """La otra mitad de `services/padron.py`: el relevamiento que la app de
        campo elige para precargar la identidad."""
        self.assertIsNone(objetivo_con_identidad([self.relevamiento], "40000005", "F"))
        self.assertEqual(
            objetivo_con_identidad([self.relevamiento], "40000001", "F"),
            self.relevamiento,
        )

    def test_el_contador_de_la_convocatoria_usa_la_misma_regla(self):
        """RED-77, cuarta copia: el «N con identidad» del detalle de la
        convocatoria tenía su propio `Count(filter=~Q(nombre="") & …)`, así que
        contaba las filas de solo espacios que el cruce ya no valida."""
        admin = User.objects.create_user("admin_padron_contador", password="x")
        admin.groups.add(Group.objects.get(name=ROL_ADMIN))
        self.client.force_login(admin)

        resp = self.client.get(reverse("becas:convocatoria_detalle", args=[self.convocatoria.pk]))

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["n_padron"], len(self.CASOS))
        esperados = sum(1 for *_, con_identidad in self.CASOS if con_identidad)
        self.assertEqual(
            resp.context["n_padron_identidad"],
            esperados,
            "El contador de la pantalla y `con_identidad()` cuentan distinto.",
        )
        self.assertEqual(
            resp.context["n_padron_identidad"],
            PadronHabilitado.objects.con_identidad().count(),
        )


class UnaSolaPuertaDePadronTests(_BasePadronTest):
    """Las dos pantallas que suben padrón comparten el cuerpo (RED-53, Ola 5).

    `convocatoria_padron` y `relevamiento_padron` eran clones literales salvo el
    objeto, la URL de vuelta y el prefijo del aviso: uno de los quince grupos que
    midió el detector AST de la auditoría. El riesgo que la ficha nombra no es
    estético —una corrección entra en una copia y no en la otra, como el candado
    de corrida viva que SIIS-03 le puso a dos de los tres comandos—, así que acá
    van las dos mitades: que la puerta sea una sola (AST) y que las dos vistas se
    comporten igual en los bordes compartidos (HTTP).
    """

    FUENTE = "programas/views/relevamientos.py"
    #: Las dos vistas y lo único que `_subir_padron` **no** puede absorber.
    VISTAS = ("convocatoria_padron", "relevamiento_padron")

    def setUp(self):
        super().setUp()
        call_command("seed_becas", stdout=StringIO())
        self.admin = User.objects.create_user("admin_red53", password="x")
        self.admin.groups.add(Group.objects.get(name=ROL_ADMIN))
        Group.objects.get(name=ROL_ADMIN).permissions.add(
            Permission.objects.get(
                content_type__app_label=APP_LABEL, codename=codename_de("becas.relevamiento.publico")
            )
        )
        cache.clear()
        self.client.force_login(self.admin)
        self.urls = {
            "convocatoria": reverse("becas:convocatoria_padron", args=[self.convocatoria.pk]),
            "relevamiento": reverse("becas:relevamiento_padron", args=[self.relevamiento.pk]),
        }
        self.duenios = {"convocatoria": self.convocatoria, "relevamiento": self.relevamiento}
        #: El padrón propio del relevamiento cuelga de otro `related_name`.
        self.padrones = {"convocatoria": "padron", "relevamiento": "padron_propio"}

    def _post(self, url, datos):
        """Un cliente por POST: los avisos no se consumen y se acumularían en sesión."""
        from django.test import Client

        cliente = Client()
        cliente.force_login(self.admin)
        resp = cliente.post(url, datos)
        return resp, [m.message for m in get_messages(resp.wsgi_request)]

    def _cuerpos(self):
        arbol = ast.parse((settings.BASE_DIR / self.FUENTE).read_text(encoding="utf-8"))
        return {
            nodo.name: nodo
            for nodo in ast.walk(arbol)
            if isinstance(nodo, ast.FunctionDef) and nodo.name in self.VISTAS
        }

    def test_las_dos_vistas_suben_por_la_misma_puerta(self):
        cuerpos = self._cuerpos()

        self.assertEqual(sorted(cuerpos), sorted(self.VISTAS))
        for nombre, nodo in cuerpos.items():
            llamadas = {
                hijo.func.id
                for hijo in ast.walk(nodo)
                if isinstance(hijo, ast.Call) and isinstance(hijo.func, ast.Name)
            }
            with self.subTest(vista=nombre):
                self.assertIn("_subir_padron", llamadas)
                # Lo que la vista deja de hacer por su cuenta: si vuelve a hacerlo,
                # volvió el clon.
                self.assertEqual(llamadas & {"cargar_padron", "parsear_padron"}, set())

    def test_el_cuerpo_de_cada_vista_es_corto_porque_delega(self):
        """Un clon que vuelva no va a entrar en cinco sentencias."""
        for nombre, nodo in self._cuerpos().items():
            with self.subTest(vista=nombre):
                sentencias = [
                    s for s in nodo.body if not isinstance(s, ast.Expr) or not isinstance(s.value, ast.Constant)
                ]

                self.assertLessEqual(len(sentencias), 5, f"{nombre} volvió a tener cuerpo propio")

    def test_las_dos_avisan_igual_cuando_falta_el_archivo(self):
        for pantalla, url in self.urls.items():
            with self.subTest(pantalla=pantalla):
                resp, mensajes = self._post(url, {})

                self.assertEqual(resp.status_code, 302)
                self.assertEqual(len(mensajes), 1)
                self.assertIn("Adjuntá el Excel del padrón", mensajes[0])
                self.assertEqual(getattr(self.duenios[pantalla], self.padrones[pantalla]).count(), 0)

    def test_las_dos_conservan_el_padron_anterior_si_el_excel_no_se_entiende(self):
        for pantalla, url in self.urls.items():
            with self.subTest(pantalla=pantalla):
                duenio = self.duenios[pantalla]
                cargado = getattr(duenio, self.padrones[pantalla])
                cargar_padron(duenio, None, [("11111111", "M")])

                self._post(url, {"padron": SimpleUploadedFile("p.xlsx", b"no excel", content_type=XLSX_MIME)})

                self.assertEqual(list(cargado.values_list("dni", flat=True)), ["11111111"])

    def test_solo_el_padron_propio_del_relevamiento_se_anuncia_con_su_prefijo(self):
        """Lo único que `_subir_padron` recibe distinto de cada vista."""
        excel = [("documento", "sexo"), ("30123456", "F")]

        _, de_convocatoria = self._post(self.urls["convocatoria"], {"padron": _xlsx(excel)})
        _, de_relevamiento = self._post(self.urls["relevamiento"], {"padron": _xlsx(excel)})

        self.assertEqual(len(de_convocatoria), 1)
        self.assertEqual(len(de_relevamiento), 1)
        self.assertNotIn("Padrón propio", de_convocatoria[0])
        self.assertTrue(de_relevamiento[0].startswith("Padrón propio de este relevamiento. "))

    def test_la_autorizacion_sigue_siendo_de_cada_vista(self):
        """`_subir_padron` no autoriza: el guard de cada pantalla es distinto."""
        cuerpos = self._cuerpos()
        fuentes = {
            nombre: ast.get_source_segment((settings.BASE_DIR / self.FUENTE).read_text(encoding="utf-8"), nodo)
            for nombre, nodo in cuerpos.items()
        }

        self.assertIn("convocatorias_visibles", fuentes["convocatoria_padron"])
        self.assertIn("_assert_scope", fuentes["relevamiento_padron"])


class DniValidoTests(TestCase):
    """RED-48: «DNI válido» es una sola regla, y todas las puertas la usan.

    Antes de este cambio convivían **cuatro** reglas de largo sobre ocho puertas:
    7 u 8 (padrón, los dos formularios públicos, el serializer de la app, el
    buscador de Dispositivos y la consulta a RENAPER de Legajos), exactamente 8
    (`extract_dni_from_cuit`), hasta 10 (`siis_envio`) y de 6 a 9 (el registro del
    portal). Las dos puntas callaban: el padrón descartaba la fila en silencio y
    `siis_envio` mandaba a SIIS —que no tiene baja— lo que los formularios
    rechazaban.

    Los cuatro valores de la ficha, uno por cada borde de la regla.
    """

    CASOS = [("123456", False), ("1234567", True), ("12345678", True), ("123456789", False)]

    def test_misma_regla_en_todas_las_puertas(self):
        from legajos.forms.ciudadanos import CiudadanoManualForm, ConsultaRenaperForm
        from legajos.services.ciudadanos import CiudadanosService
        from portal.forms.ciudadano import RegistroStep1Form
        from portal.forms.inscripcion import InscripcionPaso1Form
        from programas.forms import BusquedaCiudadanoDNIForm

        def _form(clase, dni, campo="dni", **extra):
            form = clase(data={campo: dni, **extra})
            form.is_valid()
            return campo not in form.errors

        puertas = {
            "core.dni.dni_valido": dni_valido,
            "padron (reexporta la canónica)": padron_dni_valido,
            "InscripcionPaso1Form.clean_dni": lambda dni: _form(InscripcionPaso1Form, dni),
            "RegistroStep1Form.clean_dni": lambda dni: _form(RegistroStep1Form, dni),
            "BusquedaCiudadanoDNIForm.clean_dni": lambda dni: _form(BusquedaCiudadanoDNIForm, dni),
            "ConsultaRenaperForm.clean_dni": lambda dni: _form(ConsultaRenaperForm, dni),
            "CiudadanoManualForm.clean_dni": lambda dni: _form(CiudadanoManualForm, dni),
            "CiudadanosService.extract_dni_from_cuit": lambda dni: bool(
                CiudadanosService.extract_dni_from_cuit(f"20{dni.zfill(8)}3")
            ),
        }
        for nombre, puerta in puertas.items():
            for dni, esperado in self.CASOS:
                with self.subTest(puerta=nombre, dni=dni):
                    self.assertEqual(bool(puerta(dni)), esperado)

    def test_el_padron_descarta_la_fila_con_la_misma_regla(self):
        """La puerta que **no** avisa: la fila entra a `rechazadas` y nadie la ve."""
        entradas, resumen = parsear_padron(
            _xlsx([("documento", "sexo"), ("1234567", "F"), ("123456", "F"), ("123456789", "M")])
        )

        self.assertEqual(_pares(entradas), [("1234567", "F")])
        self.assertEqual(resumen.rechazadas, 2)

    def test_siis_envio_ya_no_es_mas_laxo_que_los_formularios(self):
        """El alta a SIIS no tiene baja: lo que el formulario rechaza no viaja.

        El `len(dni) <= 10` que había dejaba pasar un DNI de un dígito o de nueve.
        """
        from programas.services.siis_envio import dni_valido as dni_valido_en_siis_envio

        for dni, esperado in [*self.CASOS, ("1", False)]:
            with self.subTest(dni=dni):
                self.assertEqual(dni_valido_en_siis_envio(dni), esperado)


class PadronArchivoViejoTests(_BasePadronTest):
    """DAT-05: el Excel reemplazado no se queda para siempre en `media/`.

    Cada archivo tiene DNI, nombre y fecha de nacimiento de miles de personas. Al
    recargar el padrón el `FileField` se reasignaba y el anterior quedaba en el
    storage sin dueño; al quitar el padrón propio pasaba lo contrario —el borrado
    corría **dentro** de la transacción, así que un error posterior dejaba la fila
    apuntando a un archivo que ya no existía—.

    El borrado va en `transaction.on_commit`, que en un `TestCase` no se dispara
    solo: por eso cada carga pasa por `captureOnCommitCallbacks`.
    """

    def setUp(self):
        super().setUp()
        temporal = TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        ajustes = override_settings(MEDIA_ROOT=temporal.name)
        ajustes.enable()
        self.addCleanup(ajustes.disable)

    def _cargar(self, objetivo, nombre):
        archivo = _xlsx([("documento", "sexo"), ("30123456", "F")], nombre=nombre)
        entradas, _ = parsear_padron(archivo)
        with self.captureOnCommitCallbacks(execute=True):
            cargar_padron(objetivo, archivo, entradas)
        objetivo.refresh_from_db()
        return objetivo.padron_archivo.name

    def test_recargar_el_padron_borra_el_excel_anterior(self):
        primero = self._cargar(self.convocatoria, "padron-1.xlsx")
        storage = self.convocatoria.padron_archivo.storage

        segundo = self._cargar(self.convocatoria, "padron-2.xlsx")

        self.assertNotEqual(primero, segundo)
        self.assertFalse(storage.exists(primero), "el Excel viejo sigue en media/ con los datos de todo el padrón")
        self.assertTrue(storage.exists(segundo))

    def test_quitar_el_padron_propio_borra_el_excel(self):
        nombre = self._cargar(self.relevamiento, "propio.xlsx")
        storage = self.relevamiento.padron_archivo.storage

        with self.captureOnCommitCallbacks(execute=True):
            quitar_padron_propio(self.relevamiento)
        self.relevamiento.refresh_from_db()

        self.assertFalse(self.relevamiento.padron_archivo)
        self.assertFalse(storage.exists(nombre))

    def test_si_la_transaccion_falla_el_excel_sigue_estando(self):
        """El borrado va en `on_commit`: un rollback deja fila y archivo intactos."""
        nombre = self._cargar(self.relevamiento, "propio-rollback.xlsx")
        storage = self.relevamiento.padron_archivo.storage

        with self.captureOnCommitCallbacks(execute=True):
            with self.assertRaises(RuntimeError):
                with transaction.atomic():
                    quitar_padron_propio(self.relevamiento)
                    raise RuntimeError("algo falla después de quitar el padrón")

        self.relevamiento.refresh_from_db()
        self.assertEqual(self.relevamiento.padron_archivo.name, nombre)
        self.assertTrue(storage.exists(nombre))
