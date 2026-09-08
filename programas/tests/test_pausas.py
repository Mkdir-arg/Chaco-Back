from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from programas.models import Convocatoria, RegistroPausa, Relevamiento, Segmento, Subsegmento
from programas.services.pausas import cambiar_pausa


class PausasOperativasTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user("admin-pausas", password="x")
        self.territorial = User.objects.create_user("territorial-pausas", password="x")
        self.segmento = Segmento.objects.create(nombre="Segmento", cupo_maximo=10)
        self.subsegmento = Subsegmento.objects.create(segmento=self.segmento, nombre="Subsegmento", cupo_maximo=10)
        self.convocatoria = Convocatoria.objects.create(
            nombre="Convocatoria",
            segmento=self.segmento,
            subsegmento=self.subsegmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        self.relevamiento = Relevamiento.objects.create(
            convocatoria=self.convocatoria,
            territorial=self.territorial,
            fecha_asignada=date(2026, 8, 7),
            fecha_hasta=date(2026, 8, 8),
            zona="Centro",
        )

    def test_pausa_superior_bloquea_relevamiento_y_deja_historial(self):
        cambiar_pausa(self.subsegmento, self.usuario, True, "Tormenta")
        self.relevamiento.refresh_from_db()

        pausa = self.relevamiento.pausa_efectiva
        self.assertEqual(pausa.pk, self.subsegmento.pk)
        self.assertFalse(self.relevamiento.habilitado_en(date(2026, 8, 7)))
        registro = RegistroPausa.objects.get()
        self.assertEqual(registro.accion, RegistroPausa.Accion.PAUSAR)
        self.assertEqual(registro.usuario, self.usuario)
        self.assertEqual(registro.motivo, "Tormenta")

    def test_reanudar_conserva_ambos_movimientos(self):
        cambiar_pausa(self.convocatoria, self.usuario, True, "Operativo suspendido")
        convocatoria = cambiar_pausa(self.convocatoria, self.usuario, False, "Operativo autorizado")

        self.assertFalse(convocatoria.pausado)
        self.assertEqual(
            list(RegistroPausa.objects.values_list("accion", flat=True)),
            [RegistroPausa.Accion.REANUDAR, RegistroPausa.Accion.PAUSAR],
        )

    def test_motivo_es_obligatorio(self):
        with self.assertRaisesMessage(ValueError, "El motivo es obligatorio"):
            cambiar_pausa(self.segmento, self.usuario, True, "")

    def test_administrador_pausa_desde_backoffice(self):
        self.usuario.is_superuser = True
        self.usuario.save(update_fields=["is_superuser"])
        self.client.force_login(self.usuario)
        url = reverse("becas:gestionar_pausa", args=["relevamiento", self.relevamiento.pk])

        formulario = self.client.get(url)
        respuesta = self.client.post(url, {"accion": "pausar", "motivo": "Corte preventivo"})

        self.assertEqual(formulario.status_code, 200)
        self.assertRedirects(
            respuesta,
            reverse("becas:relevamiento_detalle", args=[self.relevamiento.pk]),
            fetch_redirect_response=False,
        )
        self.relevamiento.refresh_from_db()
        self.assertTrue(self.relevamiento.pausado)
