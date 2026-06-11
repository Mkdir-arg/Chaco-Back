from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from conversaciones.models import Conversacion, Mensaje
from legajos.models import Ciudadano


class CiudadanoConsultasViewsTests(TestCase):
    def setUp(self):
        self.group = Group.objects.create(name='Ciudadanos')
        self.user = User.objects.create_user(username='30111222', password='secret')
        self.user.groups.add(self.group)
        self.ciudadano = Ciudadano.objects.create(
            dni='30111222',
            nombre='Ana',
            apellido='Perez',
            genero='F',
            usuario=self.user,
        )

        self.other_user = User.objects.create_user(username='30999888', password='secret')
        self.other_user.groups.add(self.group)
        self.other_ciudadano = Ciudadano.objects.create(
            dni='30999888',
            nombre='Luis',
            apellido='Gomez',
            genero='M',
            usuario=self.other_user,
        )

    def test_mis_consultas_muestra_solo_conversaciones_del_ciudadano(self):
        propia = Conversacion.objects.create(
            tipo='personal',
            dni_ciudadano=self.ciudadano.dni,
            ciudadano_usuario=self.user,
            estado='activa',
            prioridad='normal',
        )
        Conversacion.objects.create(
            tipo='personal',
            dni_ciudadano=self.other_ciudadano.dni,
            ciudadano_usuario=self.other_user,
            estado='activa',
            prioridad='normal',
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse('portal:ciudadano_mis_consultas'))

        self.assertEqual(response.status_code, 200)
        conversaciones = list(response.context['conversaciones'])
        self.assertEqual(conversaciones, [propia])

    def test_consulta_detalle_rechaza_acceso_a_otra_conversacion(self):
        ajena = Conversacion.objects.create(
            tipo='personal',
            dni_ciudadano=self.other_ciudadano.dni,
            ciudadano_usuario=self.other_user,
            estado='activa',
            prioridad='normal',
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse('portal:ciudadano_consulta_detalle', args=[ajena.pk]))

        self.assertEqual(response.status_code, 404)

    def test_nueva_consulta_invalida_no_crea_conversacion(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('portal:ciudadano_nueva_consulta'),
            data={'motivo': 'corta'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Conversacion.objects.count(), 0)
        # No se acopla al wording exacto del validador: basta con que el form
        # re-renderizado reporte el error de longitud mínima en 'motivo'.
        form = response.context.get('form')
        self.assertIsNotNone(form)
        self.assertIn('motivo', form.errors)

    @patch('portal.services.consultas._notificar_grupo')
    @patch('portal.services.consultas.NotificacionService.notificar_nueva_conversacion')
    @patch('portal.services.consultas.AsignadorAutomatico.asignar_conversacion_automatica', return_value=False)
    def test_nueva_consulta_valida_crea_conversacion_y_mensaje(
        self,
        mock_asignar,
        mock_notificar,
        mock_group_notify,
    ):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('portal:ciudadano_nueva_consulta'),
            data={'motivo': 'Necesito ayuda con mi consulta urgente'},
        )

        conversacion = Conversacion.objects.get(ciudadano_usuario=self.user)
        mensaje = Mensaje.objects.get(conversacion=conversacion)
        self.assertRedirects(
            response,
            reverse('portal:ciudadano_consulta_detalle', args=[conversacion.pk]),
        )
        self.assertEqual(conversacion.dni_ciudadano, self.ciudadano.dni)
        self.assertEqual(mensaje.contenido, 'Necesito ayuda con mi consulta urgente')
        mock_asignar.assert_called_once_with(conversacion)
        mock_notificar.assert_called_once_with(conversacion)
        self.assertGreaterEqual(mock_group_notify.call_count, 1)
