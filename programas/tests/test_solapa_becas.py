from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase

from legajos.models import Ciudadano
from programas.models import Convocatoria, Formulario, ListaEspera, ProgramaSiis, Relevamiento, Segmento
from programas.services.solapas import SolapasService


class SolapaBecasTests(TestCase):
    def test_resumen_sin_formularios_ejecuta_una_sola_query(self):
        ciudadano = Ciudadano.objects.create(dni="39000202", nombre="Cora", apellido="Sin becas")

        with self.assertNumQueries(1):
            resumen = SolapasService.obtener_resumen_becas_ciudadano(ciudadano)

        self.assertEqual(resumen["formularios"], [])

    def test_resumen_opcional_conserva_solapa_y_badge(self):
        territorial = User.objects.create_user(username="territorial-solapa-becas")
        ciudadano = Ciudadano.objects.create(dni="39000201", nombre="Beto", apellido="Becas")
        programa = ProgramaSiis.objects.create(nombre="Programa becas", siis_programa_id=902)
        segmento = Segmento.objects.create(programa=programa, nombre="Segmento becas", cupo_maximo=10)
        convocatoria = Convocatoria.objects.create(
            nombre="Convocatoria becas",
            segmento=segmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        relevamiento = Relevamiento.objects.create(
            convocatoria=convocatoria,
            territorial=territorial,
            fecha_asignada=date(2026, 6, 1),
            fecha_hasta=date(2026, 6, 30),
            zona="Zona becas",
        )
        formulario = Formulario.objects.create(
            relevamiento=relevamiento,
            ciudadano=ciudadano,
            celular="3624000000",
            email_contacto="solapa@example.com",
        )
        ListaEspera.objects.create(formulario=formulario, segmento=segmento, posicion=1)

        solapas_sin_resumen = SolapasService.obtener_solapas_ciudadano(ciudadano)
        resumen = SolapasService.obtener_resumen_becas_ciudadano(ciudadano)
        solapas_con_resumen = SolapasService.obtener_solapas_ciudadano(ciudadano, resumen_becas=resumen)

        self.assertEqual(solapas_sin_resumen, solapas_con_resumen)
        solapa_becas = next(solapa for solapa in solapas_con_resumen if solapa["id"] == "becas")
        self.assertEqual(
            solapa_becas["badge"],
            {
                "tipo": "punto",
                "color_hex": "var(--text-fg-warning)",
                "title": "Lista de espera",
            },
        )
