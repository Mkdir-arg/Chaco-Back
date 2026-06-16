import uuid
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from legajos.models import Ciudadano
from programas.models import InscripcionPrograma, Programa
from users.models import SolicitudCambioEmail


class CiudadanoPerfilViewsTests(TestCase):
    def setUp(self):
        grupo = Group.objects.create(name='Ciudadanos')
        self.user = User.objects.create_user(
            username='30111222',
            email='ana@old.test',
            password='secret123',
        )
        self.user.groups.add(grupo)
        self.ciudadano = Ciudadano.objects.create(
            dni='30111222',
            nombre='Ana',
            apellido='Perez',
            genero='F',
            email='ana@old.test',
            usuario=self.user,
        )
        self.programa = Programa.objects.create(
            codigo='PROG-1',
            nombre='Programa Uno',
            tipo=Programa.TipoPrograma.ACOMPANAMIENTO_SOCIAL,
        )

    def test_programa_detalle_no_permite_ver_otra_inscripcion(self):
        otro_user = User.objects.create_user(username='30999888', password='secret123')
        otro_user.groups.add(Group.objects.get(name='Ciudadanos'))
        otro_ciudadano = Ciudadano.objects.create(
            dni='30999888',
            nombre='Luis',
            apellido='Gomez',
            genero='M',
            usuario=otro_user,
        )
        inscripcion = InscripcionPrograma.objects.create(
            ciudadano=otro_ciudadano,
            programa=self.programa,
            estado=InscripcionPrograma.Estado.ACTIVO,
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse('portal:ciudadano_programa_detalle', args=[inscripcion.pk]))

        self.assertEqual(response.status_code, 404)

    @patch('portal.services.ciudadano_perfil.send_mail')
    def test_cambio_email_invalida_solicitudes_previas_y_crea_otra(self, send_mail_mock):
        anterior = SolicitudCambioEmail.objects.create(
            user=self.user,
            nuevo_email='ana-previa@example.com',
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('portal:ciudadano_cambio_email'),
            data={'nuevo_email': 'ana-nueva@example.com'},
        )

        self.assertRedirects(response, reverse('portal:ciudadano_mis_datos'))
        anterior.refresh_from_db()
        self.assertTrue(anterior.expirado)
        nueva = SolicitudCambioEmail.objects.get(user=self.user, nuevo_email='ana-nueva@example.com')
        self.assertFalse(nueva.confirmado)
        send_mail_mock.assert_called_once()

    def test_confirmar_email_actualiza_user_y_ciudadano(self):
        solicitud = SolicitudCambioEmail.objects.create(
            user=self.user,
            nuevo_email='ana-confirmada@example.com',
            token=uuid.uuid4(),
        )

        response = self.client.get(
            reverse('portal:ciudadano_confirmar_email', kwargs={'token': solicitud.token}),
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('portal:ciudadano_mis_datos'))
        self.user.refresh_from_db()
        self.ciudadano.refresh_from_db()
        solicitud.refresh_from_db()
        self.assertEqual(self.user.email, 'ana-confirmada@example.com')
        self.assertEqual(self.ciudadano.email, 'ana-confirmada@example.com')
        self.assertTrue(solicitud.confirmado)
