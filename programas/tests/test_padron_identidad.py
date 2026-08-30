"""El padrón como fuente de identidad (Cambio 57, análisis #325).

Cascada padrón → Base de Personas (si está activa) → manual; origen ``padron``
verificado en el servidor; cruce automático al subir el padrón; la revisión
con la Gran Base apagada. Tasks #329, #330, #331, #332, #333.
"""

from datetime import date, timedelta
from io import StringIO
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from legajos.models import Ciudadano
from programas.api.views import _actualizar_validacion_identidad
from programas.management.commands.seed_becas import ROL_ADMIN
from programas.models import Convocatoria, Formulario, Relevamiento, Segmento, TracaFormulario
from programas.services.identidad import gran_base_activa, identificar
from programas.services.padron import cargar_padron, validar_casos_pendientes

GRAN_BASE = {
    "success": True,
    "data": {"dni": "36210951", "nombre": "Pamela J.", "apellido": "Romero", "fecha_nacimiento": "2010-03-14", "sexo": "F"},
}
NO_ENCONTRADA = {"success": False, "not_found": True, "error": "El DNI no fue encontrado en Base de Personas."}
CAIDA = {"success": False, "error": "Servicio no disponible"}

FILA_PAMELA = {
    "dni": "36210951",
    "sexo": "F",
    "nombre": "Pamela Janet",
    "apellido": "Romero",
    "fecha_nacimiento": date(2010, 3, 14),
    "localidad_texto": "Resistencia",
}
FILA_SIN_DATOS = {"dni": "28111222", "sexo": "M"}


class _Base(TestCase):
    def setUp(self):
        self.segmento = Segmento.objects.create(nombre="Seg", cupo_maximo=100)
        self.convocatoria = Convocatoria.objects.create(
            nombre="Conv",
            segmento=self.segmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        self.territorial = User.objects.create_user("terri_id", password="x")
        self.relevamiento = Relevamiento.objects.create(
            convocatoria=self.convocatoria,
            territorial=self.territorial,
            fecha_asignada=timezone.now() - timedelta(days=1),
            fecha_hasta=timezone.now() + timedelta(days=10),
            zona="Zona",
        )

    def _caso(self, dni="36210951", genero="F", nombre="", apellido="", **extra):
        ciudadano = Ciudadano.objects.create(dni=dni, nombre=nombre, apellido=apellido, genero=genero)
        return Formulario.objects.create(
            relevamiento=self.relevamiento,
            ciudadano=ciudadano,
            celular="3624000000",
            email_contacto="a@b.com",
            **extra,
        )


# ── Cascada ──────────────────────────────────────────────────────────────────


@override_settings(PERSONAS_API_ACTIVA=False)
class IdentificarSinGranBaseTests(_Base):
    def test_variable_apaga_la_gran_base(self):
        self.assertFalse(gran_base_activa())

    @patch("programas.services.identidad.consultar_persona")
    def test_fila_con_identidad_valida_por_padron_sin_consultar(self, consultar):
        cargar_padron(self.convocatoria, None, [FILA_PAMELA])
        resultado = identificar(self.convocatoria, "36.210.951", "femenino")
        self.assertTrue(resultado["validado"])
        self.assertEqual(resultado["origen"], "padron")
        self.assertEqual(resultado["datos"]["nombre"], "Pamela Janet")
        self.assertEqual(resultado["datos"]["apellido"], "Romero")
        self.assertEqual(resultado["datos"]["fecha_nacimiento"], "2010-03-14")
        self.assertEqual(resultado["datos"]["localidad_texto"], "Resistencia")
        consultar.assert_not_called()

    @patch("programas.services.identidad.consultar_persona")
    def test_fila_sin_datos_queda_manual(self, consultar):
        cargar_padron(self.convocatoria, None, [FILA_SIN_DATOS])
        resultado = identificar(self.convocatoria, "28111222", "M")
        self.assertFalse(resultado["validado"])
        self.assertEqual(resultado["origen"], "manual")
        self.assertIsNone(resultado["datos"])
        consultar.assert_not_called()

    @patch("programas.services.identidad.consultar_persona")
    def test_fuera_del_padron_queda_manual(self, consultar):
        cargar_padron(self.convocatoria, None, [FILA_PAMELA])
        resultado = identificar(self.convocatoria, "99999999", "F")
        self.assertEqual(resultado["origen"], "manual")
        consultar.assert_not_called()

    def test_sin_convocatoria_ni_gran_base_es_manual(self):
        self.assertEqual(identificar(None, "36210951", "F")["origen"], "manual")

    def test_dni_o_sexo_invalidos(self):
        cargar_padron(self.convocatoria, None, [FILA_PAMELA])
        self.assertEqual(identificar(self.convocatoria, "", "F")["origen"], "manual")
        self.assertEqual(identificar(self.convocatoria, "36210951", "Z")["origen"], "manual")


@override_settings(PERSONAS_API_ACTIVA=True)
class IdentificarConGranBaseTests(_Base):
    @patch("programas.services.identidad.consultar_persona", return_value=GRAN_BASE)
    def test_la_gran_base_manda_sobre_el_padron_y_deja_las_diferencias(self, consultar):
        cargar_padron(self.convocatoria, None, [FILA_PAMELA])
        resultado = identificar(self.convocatoria, "36210951", "F")
        self.assertEqual(resultado["origen"], "personas")
        self.assertEqual(resultado["datos"]["nombre"], "Pamela J.")  # la oficial
        self.assertEqual(resultado["datos"]["localidad_texto"], "Resistencia")  # la del padrón se conserva
        self.assertEqual(resultado["diferencias"], {"nombre": ("Pamela Janet", "Pamela J.")})
        consultar.assert_called_once_with("36210951", "F")

    @patch("programas.services.identidad.consultar_persona", return_value=CAIDA)
    def test_si_la_gran_base_falla_queda_lo_del_padron(self, consultar):
        cargar_padron(self.convocatoria, None, [FILA_PAMELA])
        resultado = identificar(self.convocatoria, "36210951", "F")
        self.assertTrue(resultado["validado"])
        self.assertEqual(resultado["origen"], "padron")
        self.assertEqual(resultado["error"], "Servicio no disponible")

    @patch("programas.services.identidad.consultar_persona", return_value=NO_ENCONTRADA)
    def test_sin_padron_y_sin_match_es_manual(self, consultar):
        resultado = identificar(self.convocatoria, "36210951", "F")
        self.assertEqual(resultado["origen"], "manual")
        self.assertFalse(resultado["validado"])

    @patch("programas.services.identidad.consultar_persona", return_value=GRAN_BASE)
    def test_sin_padron_valida_la_gran_base(self, consultar):
        resultado = identificar(self.convocatoria, "36210951", "F")
        self.assertEqual(resultado["origen"], "personas")
        self.assertTrue(resultado["validado"])

    @patch("programas.services.identidad.consultar_persona", return_value={"success": False, "fallecido": True})
    def test_fallecido_solo_lo_dice_la_gran_base(self, consultar):
        cargar_padron(self.convocatoria, None, [FILA_PAMELA])
        resultado = identificar(self.convocatoria, "36210951", "F")
        self.assertTrue(resultado["fallecido"])


# ── API de campo: el servidor verifica el origen «padron» ────────────────────


class OrigenPadronServidorTests(_Base):
    def test_padron_sin_respaldo_queda_manual(self):
        caso = Formulario.objects.create(
            relevamiento=self.relevamiento,
            celular="3624000000",
            email_contacto="a@b.com",
            datos_identificacion={"dni": "36210951", "sexo": "F", "nombre": "X", "apellido": "Y", "origen": "padron"},
        )
        _actualizar_validacion_identidad(caso, caso.datos_identificacion)
        caso.refresh_from_db()
        self.assertFalse(caso.validado_renaper)
        self.assertEqual(caso.origen_validacion, "")
        self.assertEqual(caso.datos_identificacion["origen"], "manual")

    def test_padron_con_respaldo_valida_y_toma_los_datos_del_padron(self):
        cargar_padron(self.convocatoria, None, [FILA_PAMELA])
        caso = Formulario.objects.create(
            relevamiento=self.relevamiento,
            celular="3624000000",
            email_contacto="a@b.com",
            datos_identificacion={"dni": "36210951", "sexo": "F", "nombre": "Pame", "apellido": "R", "origen": "padron"},
        )
        _actualizar_validacion_identidad(caso, caso.datos_identificacion)
        caso.refresh_from_db()
        self.assertTrue(caso.validado_renaper)
        self.assertEqual(caso.origen_validacion, Formulario.OrigenValidacion.PADRON)
        self.assertEqual(caso.datos_identificacion["nombre"], "Pamela Janet")
        self.assertEqual(caso.datos_identificacion["fecha_nacimiento"], "2010-03-14")

    def test_personas_y_scan_llevan_su_origen(self):
        caso = Formulario.objects.create(
            relevamiento=self.relevamiento,
            celular="3624000000",
            email_contacto="a@b.com",
            datos_identificacion={"dni": "36210951", "nombre": "A", "apellido": "B", "origen": "personas"},
        )
        _actualizar_validacion_identidad(caso, caso.datos_identificacion)
        caso.refresh_from_db()
        self.assertEqual(caso.origen_validacion, Formulario.OrigenValidacion.PERSONAS)
        _actualizar_validacion_identidad(caso, {"dni": "36210951", "origen": "scan"})
        caso.refresh_from_db()
        self.assertEqual(caso.origen_validacion, Formulario.OrigenValidacion.SCAN)

    def test_una_validacion_manual_no_la_deshace_un_sync(self):
        caso = self._caso(identidad_forzada=True, validado_renaper=True, origen_validacion="forzada")
        _actualizar_validacion_identidad(caso, {"dni": "36210951", "origen": "manual"})
        caso.refresh_from_db()
        self.assertTrue(caso.validado_renaper)
        self.assertEqual(caso.origen_validacion, "forzada")


# ── Cruce automático al subir el padrón ──────────────────────────────────────


class CruceAutomaticoTests(_Base):
    def test_valida_los_pendientes_y_completa_el_ciudadano(self):
        pendiente = self._caso(nombre="", apellido="")
        ya_validado = self._caso(dni="20111222", genero="M", nombre="Juan", apellido="Paz", validado_renaper=True, origen_validacion="personas")
        forzado = self._caso(dni="20111333", genero="F", identidad_forzada=True, validado_renaper=True, origen_validacion="forzada")
        fuera = self._caso(dni="99999999", genero="F")

        resumen = cargar_padron(
            self.convocatoria,
            None,
            [FILA_PAMELA, {"dni": "20111222", "sexo": "M", "nombre": "Otro", "apellido": "Nombre"}],
        )

        self.assertEqual(resumen.casos_validados, 1)
        pendiente.refresh_from_db()
        self.assertTrue(pendiente.validado_renaper)
        self.assertEqual(pendiente.origen_validacion, Formulario.OrigenValidacion.PADRON)
        self.assertEqual(pendiente.ciudadano.nombre, "Pamela Janet")
        self.assertEqual(pendiente.ciudadano.fecha_nacimiento, date(2010, 3, 14))
        self.assertEqual(TracaFormulario.objects.filter(formulario=pendiente).count(), 4)  # validación + 3 campos
        ya_validado.refresh_from_db()
        self.assertEqual(ya_validado.ciudadano.nombre, "Juan")  # no se pisa ni se toca
        self.assertEqual(ya_validado.origen_validacion, "personas")
        forzado.refresh_from_db()
        self.assertEqual(forzado.origen_validacion, "forzada")
        fuera.refresh_from_db()
        self.assertFalse(fuera.validado_renaper)

    def test_no_pisa_lo_ya_cargado_en_el_ciudadano(self):
        caso = self._caso(nombre="Pame", apellido="Romero")
        cargar_padron(self.convocatoria, None, [FILA_PAMELA])
        caso.refresh_from_db()
        self.assertTrue(caso.validado_renaper)
        self.assertEqual(caso.ciudadano.nombre, "Pame")

    def test_fila_sin_identidad_no_valida(self):
        caso = self._caso(dni="28111222", genero="M")
        cargar_padron(self.convocatoria, None, [FILA_SIN_DATOS])
        caso.refresh_from_db()
        self.assertFalse(caso.validado_renaper)

    def test_un_padron_nuevo_sin_datos_no_desvalida(self):
        caso = self._caso()
        cargar_padron(self.convocatoria, None, [FILA_PAMELA])
        cargar_padron(self.convocatoria, None, [("36210951", "F")])
        caso.refresh_from_db()
        self.assertTrue(caso.validado_renaper)

    def test_caso_offline_sin_ciudadano_completa_datos_identificacion(self):
        caso = Formulario.objects.create(
            relevamiento=self.relevamiento,
            celular="3624000000",
            email_contacto="a@b.com",
            datos_identificacion={"dni": "36210951", "sexo": "F", "origen": "manual"},
        )
        cargar_padron(self.convocatoria, None, [FILA_PAMELA])
        caso.refresh_from_db()
        self.assertTrue(caso.validado_renaper)
        self.assertEqual(caso.datos_identificacion["nombre"], "Pamela Janet")
        self.assertEqual(caso.datos_identificacion["origen"], "padron")

    def test_sin_padron_no_hace_nada(self):
        self._caso()
        self.assertEqual(validar_casos_pendientes(self.convocatoria), 0)


# ── Revisión ─────────────────────────────────────────────────────────────────


class RevisionConPadronTests(_Base):
    def setUp(self):
        super().setUp()
        call_command("seed_becas", stdout=StringIO())
        self.admin = User.objects.create_user("admin_rev", password="x", is_staff=True, is_superuser=True)
        self.admin.groups.add(Group.objects.get(name=ROL_ADMIN))
        self.client.force_login(self.admin)

    def test_validar_contra_el_padron(self):
        caso = self._caso()
        cargar_padron(self.convocatoria, None, [FILA_PAMELA])
        # El cruce automático ya lo validó; se vuelve a dejar pendiente para probar el botón.
        Formulario.objects.filter(pk=caso.pk).update(validado_renaper=False, origen_validacion="")
        resp = self.client.post(reverse("becas:formulario_validar_padron", args=[caso.pk]))
        self.assertEqual(resp.status_code, 302)
        caso.refresh_from_db()
        self.assertTrue(caso.validado_renaper)
        self.assertEqual(caso.origen_validacion, Formulario.OrigenValidacion.PADRON)
        self.assertEqual(caso.ciudadano.nombre, "Pamela Janet")

    def test_validar_contra_el_padron_sin_fila_avisa_y_no_valida(self):
        caso = self._caso(dni="99999999")
        cargar_padron(self.convocatoria, None, [FILA_PAMELA])
        self.client.post(reverse("becas:formulario_validar_padron", args=[caso.pk]))
        caso.refresh_from_db()
        self.assertFalse(caso.validado_renaper)

    def test_validar_contra_el_padron_con_fila_sin_datos_no_valida(self):
        caso = self._caso(dni="28111222", genero="M")
        cargar_padron(self.convocatoria, None, [FILA_SIN_DATOS])
        self.client.post(reverse("becas:formulario_validar_padron", args=[caso.pk]))
        caso.refresh_from_db()
        self.assertFalse(caso.validado_renaper)

    def test_validar_contra_el_padron_solo_post(self):
        caso = self._caso()
        resp = self.client.get(reverse("becas:formulario_validar_padron", args=[caso.pk]))
        self.assertEqual(resp.status_code, 302)
        caso.refresh_from_db()
        self.assertFalse(caso.validado_renaper)

    @override_settings(PERSONAS_API_ACTIVA=False)
    @patch("programas.views.revision.consultar_persona")
    def test_revalidar_apagado_no_consulta(self, consultar):
        caso = self._caso(nombre="Pame", apellido="Romero")
        resp = self.client.post(reverse("becas:formulario_revalidar_renaper", args=[caso.pk]))
        self.assertEqual(resp.status_code, 302)
        consultar.assert_not_called()
        caso.refresh_from_db()
        self.assertFalse(caso.validado_renaper)

    @override_settings(PERSONAS_API_ACTIVA=True)
    @patch("programas.views.revision.consultar_persona", return_value=GRAN_BASE)
    def test_revalidar_marca_el_origen_personas(self, consultar):
        caso = self._caso(nombre="Pame", apellido="Romero")
        self.client.post(reverse("becas:formulario_revalidar_renaper", args=[caso.pk]))
        caso.refresh_from_db()
        self.assertTrue(caso.validado_renaper)
        self.assertEqual(caso.origen_validacion, Formulario.OrigenValidacion.PERSONAS)

    def test_forzar_marca_el_origen_forzada(self):
        caso = self._caso(nombre="Pame", apellido="Romero")
        self.client.post(
            reverse("becas:formulario_forzar_identidad", args=[caso.pk]),
            {"motivo": "La persona presentó el DNI en la oficina."},
        )
        caso.refresh_from_db()
        self.assertTrue(caso.identidad_forzada)
        self.assertEqual(caso.origen_validacion, Formulario.OrigenValidacion.FORZADA)


# ── Diagnóstico ──────────────────────────────────────────────────────────────


class DiagnosticoTests(TestCase):
    @override_settings(PERSONAS_API_ACTIVA=False)
    def test_gran_base_apagada_es_estado_normal(self):
        salida = StringIO()
        try:
            call_command("diagnosticar_integraciones", stdout=salida, stderr=StringIO())
        except SystemExit:
            pass
        texto = salida.getvalue()
        self.assertIn("PERSONAS_API_ACTIVA", texto)
        self.assertIn("desactivada por configuración", texto)
        self.assertNotIn("configuración incompleta: el formulario público NUNCA", texto)
