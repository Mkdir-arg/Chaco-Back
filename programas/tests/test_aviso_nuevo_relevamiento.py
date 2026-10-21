"""«Nuevo relevamiento» avisa por qué no se puede (o no hay a quién asignar).

Sin esto el modal salía con el select de convocatoria vacío y los territoriales ocultos,
y al guardar daba el genérico «Seleccione una opción válida». Los avisos no relajan
ninguna regla: la convocatoria pausada o cerrada sigue fuera del queryset del form.
"""

from datetime import timedelta
from io import StringIO

from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from programas.forms import RelevamientoForm
from programas.management.commands.seed_becas import ROL_TERRITORIAL
from programas.models import AsignacionTerritorial, Convocatoria, Segmento
from programas.tests.test_siis_vigencia_programa import crear_programa

HOY = timezone.localdate()
# El mismo texto vive en el script del filtro: el aviso del servidor se distingue por su etiqueta.
SIN_TERRITORIALES = 'role="status" data-aviso-territorial>Este segmento no tiene territoriales asignados.'
SIN_CONVOCATORIAS = "No hay convocatorias abiertas para crear relevamientos"


class AvisosNuevoRelevamientoTests(TestCase):
    def setUp(self):
        cache.clear()
        call_command("seed_becas", stdout=StringIO())
        self.programa = crear_programa()
        self.segmento = Segmento.objects.create(programa=self.programa, nombre="Seg avisos", cupo_maximo=100)
        self.convocatoria = Convocatoria.objects.create(
            nombre="Conv avisos",
            segmento=self.segmento,
            fecha_inicio=HOY - timedelta(days=30),
            fecha_fin=HOY + timedelta(days=30),
        )
        self.client.force_login(User.objects.create_superuser("super-avisos", password="x"))

    def _detalle(self):
        return self.client.get(reverse("becas:convocatoria_detalle", args=[self.convocatoria.pk]))

    def _asignar_territorial(self):
        territorial = User.objects.create_user("terri-avisos", password="x")
        territorial.groups.add(Group.objects.get(name=ROL_TERRITORIAL))
        AsignacionTerritorial.objects.create(segmento=self.segmento, territorial=territorial)
        return territorial

    def test_convocatoria_pausada_muestra_el_motivo_y_no_ofrece_el_alta(self):
        self.convocatoria.pausado = True
        self.convocatoria.pausa_motivo = "Revisión de cupos"
        self.convocatoria.save(update_fields=["pausado", "pausa_motivo", "modificado"])

        response = self._detalle()

        self.assertContains(response, "La convocatoria está pausada: Revisión de cupos")
        self.assertIsNone(response.context["form_crear"])
        self.assertNotContains(response, "modal-relevamiento-crear-titulo")
        self.assertNotContains(response, "Nuevo relevamiento</button>")

    def test_pausa_heredada_del_segmento_nombra_al_segmento(self):
        self.segmento.pausado = True
        self.segmento.pausa_motivo = "Auditoría"
        self.segmento.save(update_fields=["pausado", "pausa_motivo", "modificado"])

        response = self._detalle()

        self.assertContains(response, "El segmento de la convocatoria está pausado: Auditoría")
        self.assertIsNone(response.context["form_crear"])

    def test_convocatoria_cerrada_por_vencimiento_dice_cuando_vencio(self):
        fin = HOY - timedelta(days=2)
        Convocatoria.objects.filter(pk=self.convocatoria.pk).update(fecha_fin=fin, activo=False)

        response = self._detalle()

        self.assertContains(response, f"La convocatoria está cerrada (venció el {fin:%d/%m/%Y}).")
        self.assertContains(response, "extendé la fecha de fin y reactivala")
        self.assertIsNone(response.context["form_crear"])
        self.assertContains(response, reverse("becas:convocatoria_editar", args=[self.convocatoria.pk]))

    def test_convocatoria_cerrada_a_mano_dice_que_hay_que_reactivarla(self):
        Convocatoria.objects.filter(pk=self.convocatoria.pk).update(activo=False)

        response = self._detalle()

        self.assertContains(response, "La convocatoria está cerrada. Para crear relevamientos, reactivala.")

    def test_segmento_sin_territoriales_avisa_desde_el_servidor(self):
        response = self._detalle()

        self.assertIsNotNone(response.context["form_crear"])
        self.assertTrue(response.context["segmento_sin_territoriales"])
        self.assertContains(response, SIN_TERRITORIALES)
        self.assertContains(response, reverse("users:usuarios"))
        self.assertNotContains(response, "La convocatoria está pausada")
        self.assertNotContains(response, "La convocatoria está cerrada")

    def test_con_territorial_asignado_no_hay_avisos(self):
        self._asignar_territorial()

        response = self._detalle()

        self.assertFalse(response.context["segmento_sin_territoriales"])
        self.assertNotContains(response, SIN_TERRITORIALES)
        self.assertNotContains(response, "No se pueden crear relevamientos")
        self.assertIn(self.convocatoria, response.context["form_crear"].fields["convocatoria"].queryset)

    def test_el_script_trae_los_textos_de_ayuda_del_filtro_territorial(self):
        response = self._detalle()

        self.assertContains(response, "Elegí primero una convocatoria")
        self.assertContains(response, "data-aviso-territorial")

    def test_form_sin_convocatorias_abiertas_lo_expone(self):
        self.assertFalse(RelevamientoForm().sin_convocatorias)
        Convocatoria.objects.filter(pk=self.convocatoria.pk).update(activo=False)
        self.assertTrue(RelevamientoForm().sin_convocatorias)

    def test_pagina_de_alta_avisa_si_no_hay_convocatorias(self):
        url = reverse("becas:relevamiento_crear")
        self.assertNotContains(self.client.get(url), SIN_CONVOCATORIAS)

        Convocatoria.objects.filter(pk=self.convocatoria.pk).update(activo=False)
        response = self.client.get(url)

        self.assertContains(response, SIN_CONVOCATORIAS)
        self.assertContains(response, reverse("becas:convocatorias"))

    def test_modal_del_listado_avisa_si_no_hay_convocatorias(self):
        url = reverse("becas:relevamientos")
        self.assertNotContains(self.client.get(url), SIN_CONVOCATORIAS)

        Convocatoria.objects.filter(pk=self.convocatoria.pk).update(activo=False)

        self.assertContains(self.client.get(url), SIN_CONVOCATORIAS)
