"""LEG-02 · Reinscribir en un programa con una inscripción previa no activa.

``InscripcionPrograma`` tiene ``unique_together = [ciudadano, programa]``: una
inscripción CERRADA, DADA DE BAJA o SUSPENDIDA ocupa la fila para siempre. Las tres
vías de alta hacían ``create`` igual —el form de derivación, ``DerivacionPrograma.aceptar``
y ``SolapasService.crear_inscripcion_directa``— y la base contestaba ``IntegrityError``
(500 en la vista). ``activar_inscripcion`` es la única puerta: reactiva la fila que ya
existe en vez de pelearse con el índice.
"""

from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from legajos.models import Ciudadano
from programas.models import DerivacionPrograma, InscripcionPrograma, Programa
from programas.services.inscripciones import activar_inscripcion
from programas.services.solapas import SolapasService


class ReactivarInscripcionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = User.objects.create_superuser("leg02", "leg02@x.com", "x")
        cls.programa = Programa.objects.create(
            codigo="LEG02",
            nombre="Programa LEG-02",
            tipo=Programa.TipoPrograma.DISPOSITIVOS,
            estado=Programa.Estado.ACTIVO,
        )

    def _ciudadano(self, dni):
        return Ciudadano.objects.create(dni=dni, nombre="N", apellido="A", fecha_nacimiento=date(1990, 1, 1))

    def test_aceptar_derivacion_con_inscripcion_cerrada_la_reactiva(self):
        ciudadano = self._ciudadano("31000001")
        previa = InscripcionPrograma.objects.create(
            ciudadano=ciudadano,
            programa=self.programa,
            estado=InscripcionPrograma.Estado.CERRADO,
            fecha_cierre=date(2026, 1, 1),
        )
        derivacion = DerivacionPrograma.objects.create(
            ciudadano=ciudadano, programa_destino=self.programa, motivo="reingreso"
        )

        inscripcion = derivacion.aceptar(usuario=self.usuario)

        self.assertEqual(inscripcion.pk, previa.pk)
        self.assertEqual(InscripcionPrograma.objects.filter(ciudadano=ciudadano, programa=self.programa).count(), 1)
        self.assertEqual(inscripcion.estado, InscripcionPrograma.Estado.ACTIVO)
        self.assertIsNone(inscripcion.fecha_cierre)
        self.assertEqual(inscripcion.fecha_inicio, timezone.localdate())
        self.assertEqual(inscripcion.via_ingreso, InscripcionPrograma.ViaIngreso.DERIVACION_EXTERNA)
        self.assertIn("reingreso", inscripcion.notas)
        derivacion.refresh_from_db()
        self.assertEqual(derivacion.estado, "ACEPTADA")
        self.assertEqual(derivacion.inscripcion_creada_id, previa.pk)

    def test_inscripcion_directa_con_baja_reactiva(self):
        ciudadano = self._ciudadano("31000002")
        previa = InscripcionPrograma.objects.create(
            ciudadano=ciudadano,
            programa=self.programa,
            estado=InscripcionPrograma.Estado.DADO_DE_BAJA,
        )
        self.client.force_login(self.usuario)

        respuesta = self.client.post(
            reverse("legajos:derivar_programa", args=[ciudadano.pk]),
            {
                "institucion_programa": self.programa.pk,
                "tipo_inicio": "inscripcion_directa",
                "motivo": "vuelve al programa",
                "urgencia": DerivacionPrograma.Urgencia.MEDIA,
            },
        )

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(InscripcionPrograma.objects.filter(ciudadano=ciudadano, programa=self.programa).count(), 1)
        previa.refresh_from_db()
        self.assertEqual(previa.estado, InscripcionPrograma.Estado.ACTIVO)
        self.assertEqual(previa.via_ingreso, InscripcionPrograma.ViaIngreso.DIRECTO)
        self.assertIn("vuelve al programa", previa.notas)

    def test_crear_inscripcion_directa_de_solapas_reactiva_la_suspendida(self):
        ciudadano = self._ciudadano("31000003")
        previa = InscripcionPrograma.objects.create(
            ciudadano=ciudadano,
            programa=self.programa,
            estado=InscripcionPrograma.Estado.SUSPENDIDO,
        )

        inscripcion = SolapasService.crear_inscripcion_directa(
            ciudadano, self.programa, self.usuario, notas="por ventanilla"
        )

        self.assertEqual(inscripcion.pk, previa.pk)
        self.assertEqual(inscripcion.estado, InscripcionPrograma.Estado.ACTIVO)
        self.assertEqual(inscripcion.notas, "por ventanilla")

    def test_activar_inscripcion_con_una_activa_no_duplica_ni_pisa_la_via(self):
        """Ya activa: la deja como está y no reescribe la vía de ingreso."""
        ciudadano = self._ciudadano("31000004")
        previa = InscripcionPrograma.objects.create(
            ciudadano=ciudadano,
            programa=self.programa,
            estado=InscripcionPrograma.Estado.ACTIVO,
            via_ingreso=InscripcionPrograma.ViaIngreso.ESPONTANEO,
            notas="original",
        )

        inscripcion = activar_inscripcion(
            ciudadano,
            self.programa,
            via=InscripcionPrograma.ViaIngreso.DIRECTO,
            usuario=self.usuario,
            notas="nueva",
        )

        self.assertEqual(inscripcion.pk, previa.pk)
        self.assertEqual(inscripcion.via_ingreso, InscripcionPrograma.ViaIngreso.ESPONTANEO)
        self.assertEqual(inscripcion.notas, "original")

    def test_activar_inscripcion_pendiente_pasa_a_activo(self):
        ciudadano = self._ciudadano("31000005")
        previa = InscripcionPrograma.objects.create(
            ciudadano=ciudadano,
            programa=self.programa,
            estado=InscripcionPrograma.Estado.PENDIENTE,
        )

        inscripcion = activar_inscripcion(
            ciudadano, self.programa, via=InscripcionPrograma.ViaIngreso.DIRECTO, usuario=self.usuario
        )

        self.assertEqual(inscripcion.pk, previa.pk)
        self.assertEqual(inscripcion.estado, InscripcionPrograma.Estado.ACTIVO)
        self.assertEqual(inscripcion.fecha_inicio, timezone.localdate())

    def test_activar_inscripcion_sin_fila_previa_la_crea(self):
        ciudadano = self._ciudadano("31000006")

        inscripcion = activar_inscripcion(
            ciudadano,
            self.programa,
            via=InscripcionPrograma.ViaIngreso.DERIVACION_INTERNA,
            usuario=self.usuario,
            notas="alta nueva",
        )

        self.assertEqual(inscripcion.estado, InscripcionPrograma.Estado.ACTIVO)
        self.assertEqual(inscripcion.via_ingreso, InscripcionPrograma.ViaIngreso.DERIVACION_INTERNA)
        self.assertEqual(inscripcion.responsable, self.usuario)
        self.assertEqual(inscripcion.notas, "alta nueva")
