"""Contratos del modelo base de Dispositivos y Merenderos (#173)."""

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.utils import timezone

from legajos.models import Ciudadano
from programas.models import Programa


class TipoProgramaDispositivosTests(TestCase):
    def test_incluye_dispositivos_y_merenderos_sin_quitar_choices_existentes(self):
        valores_originales = {
            "ACOMPANAMIENTO_SOCIAL",
            "ECONOMICO",
            "FAMILIAR",
            "REDUCCION_DANOS",
            "REINSERCION_SOCIAL",
            "CAPACITACION_COMUNITARIA",
            "BECAS",
        }

        valores = {valor for valor, _etiqueta in Programa.TipoPrograma.choices}

        self.assertTrue(valores_originales.issubset(valores))
        self.assertIn("DISPOSITIVOS", valores)
        self.assertIn("MERENDEROS", valores)


class ModelosDispositivosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.programa_dispositivos, _ = Programa.objects.get_or_create(
            codigo="DISPOSITIVOS",
            defaults={"nombre": "Dispositivos", "tipo": Programa.TipoPrograma.DISPOSITIVOS},
        )
        cls.programa_merenderos, _ = Programa.objects.get_or_create(
            codigo="MERENDEROS",
            defaults={"nombre": "Merenderos", "tipo": Programa.TipoPrograma.MERENDEROS},
        )

    def test_relaciones_base_son_persistibles_y_cama_es_opcional(self):
        from programas.models import Admision, Cama, Dispositivo, InscripcionPrograma, TipoDispositivo

        tipo = TipoDispositivo.objects.create(codigo="AM", nombre="Adulto Mayor", maneja_camas=True)
        dispositivo = Dispositivo.objects.create(
            codigo="DISP-001",
            nombre="Residencia Norte",
            tipo=tipo,
            domicilio="Calle Falsa 123",
            latitud=-27.4514,
            longitud=-58.9867,
            responsable_nombre="Responsable Demo",
            contacto_telefono="3624000000",
            horarios="Lunes a viernes de 8 a 18",
        )
        cama = Cama.objects.create(dispositivo=dispositivo, codigo="C-01")
        ciudadano = Ciudadano.objects.create(dni="30111222", nombre="Ana", apellido="Demo")
        membresia = InscripcionPrograma.objects.create(ciudadano=ciudadano, programa=self.programa_dispositivos)

        admision = Admision.objects.create(
            ciudadano=ciudadano,
            dispositivo=dispositivo,
            inscripcion_programa=membresia,
            fecha_ingreso=timezone.now(),
        )

        self.assertEqual(dispositivo.tipo, tipo)
        self.assertEqual(cama.dispositivo, dispositivo)
        self.assertIsNone(admision.cama)
        self.assertEqual(admision.inscripcion_programa, membresia)

    def test_permite_multiples_admisiones_para_el_mismo_ciudadano_y_dispositivo(self):
        from programas.models import Admision, Dispositivo, TipoDispositivo

        tipo = TipoDispositivo.objects.create(codigo="AM", nombre="Adulto Mayor", maneja_camas=True)
        dispositivo = Dispositivo.objects.create(codigo="DISP-001", nombre="Residencia", tipo=tipo)
        ciudadano = Ciudadano.objects.create(dni="30111222", nombre="Ana", apellido="Demo")

        primera = Admision.objects.create(
            ciudadano=ciudadano,
            dispositivo=dispositivo,
            fecha_ingreso=timezone.now(),
        )
        segunda = Admision.objects.create(
            ciudadano=ciudadano,
            dispositivo=dispositivo,
            fecha_ingreso=timezone.now(),
            es_reingreso=True,
        )

        self.assertNotEqual(primera.pk, segunda.pk)
        self.assertEqual(Admision.objects.filter(ciudadano=ciudadano, dispositivo=dispositivo).count(), 2)

    def test_admision_rechaza_cama_de_otro_dispositivo(self):
        from programas.models import Admision, Cama, Dispositivo, TipoDispositivo

        tipo = TipoDispositivo.objects.create(codigo="AM", nombre="Adulto Mayor", maneja_camas=True)
        dispositivo = Dispositivo.objects.create(codigo="DISP-001", nombre="Residencia", tipo=tipo)
        otro_dispositivo = Dispositivo.objects.create(codigo="DISP-002", nombre="Otra residencia", tipo=tipo)
        cama_ajena = Cama.objects.create(dispositivo=otro_dispositivo, codigo="C-01")
        ciudadano = Ciudadano.objects.create(dni="30111222", nombre="Ana", apellido="Demo")

        admision = Admision(
            ciudadano=ciudadano,
            dispositivo=dispositivo,
            cama=cama_ajena,
            fecha_ingreso=timezone.now(),
        )

        with self.assertRaisesMessage(ValidationError, "La cama debe pertenecer al dispositivo"):
            admision.full_clean()

    def test_admision_rechaza_membresia_de_otro_ciudadano_o_programa(self):
        from programas.models import Admision, Dispositivo, InscripcionPrograma, TipoDispositivo

        tipo = TipoDispositivo.objects.create(codigo="AM", nombre="Adulto Mayor", maneja_camas=True)
        dispositivo = Dispositivo.objects.create(codigo="DISP-001", nombre="Residencia", tipo=tipo)
        ciudadano = Ciudadano.objects.create(dni="30111222", nombre="Ana", apellido="Demo")
        otro_ciudadano = Ciudadano.objects.create(dni="30111223", nombre="Beto", apellido="Demo")
        membresia_ajena = InscripcionPrograma.objects.create(
            ciudadano=otro_ciudadano,
            programa=self.programa_dispositivos,
        )
        membresia_otro_programa = InscripcionPrograma.objects.create(
            ciudadano=ciudadano,
            programa=self.programa_merenderos,
        )

        admision = Admision(
            ciudadano=ciudadano,
            dispositivo=dispositivo,
            inscripcion_programa=membresia_ajena,
            fecha_ingreso=timezone.now(),
        )
        with self.assertRaisesMessage(ValidationError, "La membresía debe pertenecer al ciudadano"):
            admision.full_clean()

        admision.inscripcion_programa = membresia_otro_programa
        with self.assertRaisesMessage(ValidationError, "La membresía debe ser del programa Dispositivos"):
            admision.full_clean()

    def test_cama_con_admision_historica_no_se_puede_eliminar(self):
        from programas.models import Admision, Cama, Dispositivo, TipoDispositivo

        tipo = TipoDispositivo.objects.create(codigo="AM", nombre="Adulto Mayor", maneja_camas=True)
        dispositivo = Dispositivo.objects.create(codigo="DISP-001", nombre="Residencia", tipo=tipo)
        cama = Cama.objects.create(dispositivo=dispositivo, codigo="C-01")
        ciudadano = Ciudadano.objects.create(dni="30111222", nombre="Ana", apellido="Demo")
        Admision.objects.create(
            ciudadano=ciudadano,
            dispositivo=dispositivo,
            cama=cama,
            fecha_ingreso=timezone.now(),
            fecha_egreso=timezone.now(),
            estado=Admision.Estado.EGRESADO,
        )

        with self.assertRaises(ProtectedError):
            cama.delete()

    def test_choices_de_estado_coinciden_con_el_analisis(self):
        from programas.models import Admision, Cama, Dispositivo

        self.assertEqual(
            {etiqueta for _valor, etiqueta in Dispositivo.Estado.choices},
            {"Borrador", "Pendiente de validación", "Activo", "Observado", "Rechazado", "Inactivo", "Cerrado"},
        )
        self.assertEqual(
            {etiqueta for _valor, etiqueta in Cama.Estado.choices},
            {"Disponible", "Reservada", "Ocupada", "Fuera de servicio"},
        )
        self.assertEqual(
            {etiqueta for _valor, etiqueta in Admision.Estado.choices},
            {
                "Solicitado",
                "En revisión",
                "Lista de espera",
                "Aprobado",
                "Rechazado",
                "Alojado",
                "Egresado",
                "Trasladado",
            },
        )

    def test_membresia_conserva_unicidad_por_ciudadano_y_programa(self):
        from programas.models import InscripcionPrograma

        ciudadano = Ciudadano.objects.create(dni="30111222", nombre="Ana", apellido="Demo")
        InscripcionPrograma.objects.create(ciudadano=ciudadano, programa=self.programa_dispositivos)

        with self.assertRaises(IntegrityError), transaction.atomic():
            InscripcionPrograma.objects.create(ciudadano=ciudadano, programa=self.programa_dispositivos)


class ModelosMerenderosTests(TestCase):
    def test_solicitud_puede_existir_antes_de_crear_el_legajo(self):
        from programas.models import SolicitudMerendero

        solicitud = SolicitudMerendero.objects.create(
            documentacion="merenderos/solicitudes/respaldo.pdf",
        )

        self.assertIsNone(solicitud.merendero)

    def test_solicitud_entrega_y_prestacion_diaria_son_persistibles(self):
        from programas.models import (
            EntregaMercaderia,
            Merendero,
            PrestacionDiaria,
            PrestacionMensual,
            SolicitudMerendero,
        )

        merendero = Merendero.objects.create(
            codigo="MER-001",
            nombre="Rayito de Sol",
            domicilio="Barrio Demo Mz. 1",
            zona="Norte",
            barrio="Demo",
            telefono="3624111111",
            responsable_nombre="Vecina Demo",
            responsable_documento="30123456",
            responsable_email="demo@example.com",
        )
        solicitud = SolicitudMerendero.objects.create(
            merendero=merendero,
            documentacion="merenderos/solicitudes/respaldo.pdf",
        )
        entrega = EntregaMercaderia.objects.create(
            merendero=merendero,
            fecha=timezone.localdate(),
            cantidad_kits=10,
            servicio="Almuerzo",
        )
        prestacion = PrestacionMensual.objects.create(merendero=merendero, anio=2026, mes=7)
        linea = PrestacionDiaria.objects.create(
            prestacion=prestacion,
            dia=1,
            servicio="ALMUERZO",
            raciones=35,
        )

        self.assertTrue(solicitud.documentacion.name.endswith("respaldo.pdf"))
        self.assertEqual(entrega.merendero, merendero)
        self.assertEqual(linea.prestacion, prestacion)
        self.assertEqual(linea.raciones, 35)

    def test_choices_de_estado_coinciden_con_el_analisis(self):
        from programas.models import Merendero, SolicitudMerendero

        self.assertEqual(
            {etiqueta for _valor, etiqueta in Merendero.Estado.choices},
            {"Activo", "Suspendido", "Cerrado"},
        )
        self.assertEqual(
            {etiqueta for _valor, etiqueta in SolicitudMerendero.Estado.choices},
            {"Borrador", "En revisión", "Observada", "Aprobada", "Rechazada"},
        )
