"""Bandeja «Pendientes de validación» (RENAPER): paginación y textos.

La vista pagina de a 50 (``RenaperPendientesListView.paginate_by``) pero la plantilla
no tenía pie: desde el caso 51 los pendientes no se podían abrir. Además el rótulo de
los casos del link público llegaba doble-codificado («Formulario pÃºblico»).
"""

from datetime import date
from io import StringIO

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from legajos.models import Ciudadano
from programas.models import Convocatoria, Formulario, Relevamiento, Segmento

URL = reverse("becas:renaper_pendientes")
FILA = '<tr class="hover:bg-secondary">'


class _BaseRenaperPendientes(TestCase):
    def setUp(self):
        cache.clear()
        call_command("seed_becas", stdout=StringIO())
        self.segmento = Segmento.objects.create(nombre="Seg Renaper", cupo_maximo=500)
        self.convocatoria = Convocatoria.objects.create(
            nombre="Conv Renaper",
            segmento=self.segmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        self.territorial = User.objects.create_user("terri_renaper", password="x")
        self.relevamiento = Relevamiento.objects.create(
            convocatoria=self.convocatoria,
            territorial=self.territorial,
            fecha_asignada=date(2026, 6, 1),
            zona="Z",
            estado=Relevamiento.Estado.FINALIZADO,
        )
        self.usuario = User.objects.create_superuser("super_renaper", password="x")
        self.client.force_login(self.usuario)


class PaginacionRenaperPendientesTests(_BaseRenaperPendientes):
    def setUp(self):
        super().setUp()
        for i in range(51):
            Formulario.objects.create(
                relevamiento=self.relevamiento,
                celular=f"36240{i:05d}",
                validado_renaper=False,
            )

    def test_pagina_1_enlaza_a_la_pagina_2(self):
        resp = self.client.get(URL)

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context["is_paginated"])
        self.assertContains(resp, 'href="?page=2"')
        self.assertContains(resp, "Página 1 de 2 · 51 casos")
        self.assertContains(resp, 'aria-label="Página siguiente"')
        self.assertNotContains(resp, 'aria-label="Página anterior"')

    def test_el_enlace_a_la_pagina_2_conserva_los_filtros(self):
        hoy = timezone.localdate().isoformat()
        resp = self.client.get(
            URL,
            {"fecha": hoy, "territorial": self.territorial.pk, "segmento": self.segmento.pk},
        )

        self.assertEqual(resp.context["page_obj"].paginator.count, 51)
        self.assertContains(
            resp,
            f'href="?page=2&amp;fecha={hoy}&amp;territorial={self.territorial.pk}&amp;segmento={self.segmento.pk}"',
        )

    def test_la_pagina_2_muestra_la_fila_51(self):
        resp = self.client.get(URL, {"page": 2})

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.context["formularios"]), 1)
        self.assertContains(resp, FILA, count=1)
        self.assertContains(resp, "Página 2 de 2 · 51 casos")
        self.assertContains(resp, 'href="?page=1"')
        self.assertNotContains(resp, 'aria-label="Página siguiente"')

    def test_con_una_sola_pagina_no_hay_pie(self):
        Formulario.objects.filter(validado_renaper=False).order_by("pk").first().delete()

        resp = self.client.get(URL)

        self.assertFalse(resp.context["is_paginated"])
        self.assertNotContains(resp, "?page=")
        self.assertContains(resp, FILA, count=50)


class TextosRenaperPendientesTests(_BaseRenaperPendientes):
    def test_caso_publico_dice_formulario_publico_sin_texto_roto(self):
        rel_publico = Relevamiento.objects.create(
            convocatoria=self.convocatoria,
            tipo=Relevamiento.Tipo.PUBLICO,
            fecha_asignada=date(2026, 6, 1),
        )
        Formulario.objects.create(relevamiento=rel_publico, celular="3624777777", validado_renaper=False)

        resp = self.client.get(URL)

        self.assertContains(resp, "Formulario público")
        self.assertNotContains(resp, "Ã")

    def test_ver_caso_es_un_boton_de_icono_con_nombre_accesible(self):
        ciudadano = Ciudadano.objects.create(
            dni="60600610",
            nombre="Lucía",
            apellido="Benítez",
            fecha_nacimiento=date(2000, 1, 1),
        )
        caso = Formulario.objects.create(
            relevamiento=self.relevamiento,
            ciudadano=ciudadano,
            celular="3624222222",
            validado_renaper=False,
        )

        resp = self.client.get(URL)

        self.assertContains(
            resp,
            f'<a href="{reverse("becas:formulario_detalle", args=[caso.pk])}?next=/becas/revision/renaper/pendientes/" '
            'class="nodo-icon-btn" aria-label="Ver caso de Lucía Benítez">',
        )
        self.assertNotContains(resp, ">Abrir<")

    def test_volver_lleva_a_revision(self):
        resp = self.client.get(URL)

        self.assertContains(
            resp,
            f'<a href="{reverse("becas:revision")}" class="btn-tertiary btn-back-circle" '
            'aria-label="Volver a Revisión"><i class="fas fa-arrow-left" aria-hidden="true"></i></a>',
            html=True,
        )

    def test_vacio_sin_filtros_dice_que_no_hay_pendientes(self):
        resp = self.client.get(URL)

        self.assertContains(resp, "No hay casos pendientes de validación")
        self.assertContains(resp, "Todas las identidades cargadas ya están validadas.")
        self.assertNotContains(resp, "Los filtros seleccionados no tienen resultados.")

    def test_vacio_con_filtros_lo_atribuye_a_los_filtros(self):
        Formulario.objects.create(relevamiento=self.relevamiento, celular="3624111111", validado_renaper=False)

        resp = self.client.get(URL, {"segmento": self.segmento.pk + 999})

        self.assertContains(resp, "Los filtros seleccionados no tienen resultados.")
        self.assertNotContains(resp, "No hay casos pendientes de validación")
