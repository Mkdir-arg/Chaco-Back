"""SIIS-13 · Un DNI ajeno cargado en el link abierto deja de bloquear al titular.

RN-P5 cuenta **todos** los formularios de la convocatoria, incluidos los
RECHAZADO. En un link sin padrón cualquiera puede tipear el documento de un
tercero: queda un formulario `manual` que, aunque el backoffice lo rechace,
sigue ocupando el DNI en toda la convocatoria y el titular real no se puede
inscribir nunca.

**D-S13, default aplicado:** un RECHAZADO cuya identidad **nunca se validó**
libera el documento. Un RECHAZADO validado sigue bloqueando —esa persona sí se
presentó y ya tiene su resolución— y un BAJA también, porque llegó a estar
aprobado.
"""

from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone

from legajos.models import Ciudadano
from programas.models import Convocatoria, Formulario, Relevamiento, Segmento
from programas.services.inscripcion_publica import dni_en_convocatoria


class RechazadoSinValidarNoBloqueaTests(TestCase):
    def setUp(self):
        self.segmento = Segmento.objects.create(nombre="Seg", cupo_maximo=100)
        self.convocatoria = Convocatoria.objects.create(
            nombre="Becas 2026",
            segmento=self.segmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        self.relevamiento = Relevamiento.objects.create(
            convocatoria=self.convocatoria,
            tipo=Relevamiento.Tipo.PUBLICO,
            fecha_asignada=timezone.now() - timedelta(days=1),
            fecha_hasta=timezone.now() + timedelta(days=10),
        )

    def _caso(self, dni, estado, validado, con_legajo=False):
        datos = {"ciudadano": Ciudadano.objects.create(dni=dni, nombre="Ana", apellido="Paz")} if con_legajo else {}
        return Formulario.objects.create(
            relevamiento=self.relevamiento,
            estado=estado,
            validado_renaper=validado,
            datos_identificacion=None if con_legajo else {"dni": dni},
            **datos,
        )

    def test_un_rechazado_sin_validar_libera_el_documento(self):
        self._caso("30111222", Formulario.Estado.RECHAZADO, validado=False)

        self.assertFalse(dni_en_convocatoria(self.convocatoria, "30111222"))

    def test_un_rechazado_sin_validar_con_legajo_tambien_lo_libera(self):
        """La segunda consulta de RN-P5 (por `ciudadano__dni`) aplica la misma regla."""
        self._caso("30111222", Formulario.Estado.RECHAZADO, validado=False, con_legajo=True)

        self.assertFalse(dni_en_convocatoria(self.convocatoria, "30111222"))

    def test_un_rechazado_validado_sigue_bloqueando(self):
        self._caso("30111222", Formulario.Estado.RECHAZADO, validado=True)

        self.assertTrue(dni_en_convocatoria(self.convocatoria, "30111222"))

    def test_una_baja_sigue_bloqueando_aunque_no_este_validada(self):
        """Un BAJA llegó a estar aprobado: no es una carga de un tercero."""
        self._caso("30111222", Formulario.Estado.BAJA, validado=False)

        self.assertTrue(dni_en_convocatoria(self.convocatoria, "30111222"))

    def test_un_enviado_sin_validar_sigue_bloqueando(self):
        """Lo que todavía no se revisó ocupa el lugar: si no, dos cargas del
        mismo documento entrarían a la bandeja a la vez."""
        self._caso("30111222", Formulario.Estado.ENVIADO, validado=False)

        self.assertTrue(dni_en_convocatoria(self.convocatoria, "30111222"))

    def test_el_titular_entra_aunque_le_hayan_quemado_el_documento(self):
        """El escenario completo: la carga ajena rechazada y el titular después."""
        self._caso("30111222", Formulario.Estado.RECHAZADO, validado=False)

        self.assertFalse(dni_en_convocatoria(self.convocatoria, "30111222"))

        self._caso("30111222", Formulario.Estado.ENVIADO, validado=True)

        self.assertTrue(dni_en_convocatoria(self.convocatoria, "30111222"))

    def test_siguen_siendo_dos_consultas(self):
        """El Cambio 91: una por índice, sin funciones sobre la columna."""
        with self.assertNumQueries(2):
            dni_en_convocatoria(self.convocatoria, "99999999")
