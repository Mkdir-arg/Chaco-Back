from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from conversaciones.forms_chat import IniciarConversacionForm, MensajeConversacionForm
from conversaciones.models import Conversacion, HistorialAlertaConversacion, Mensaje
from conversaciones.selectors_conversaciones import get_alertas_conversaciones_count
from conversaciones.services_chat import (
    crear_mensaje_operador,
    iniciar_conversacion_publica,
    marcar_mensajes_ciudadano_leidos,
)

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType

from core import rbac
from users.models import Capacidad


def _conceder_conversacion_operar(group):
    """Asigna la capacidad ``conversacion.operar`` a un rol (modelo RBAC)."""
    ct = ContentType.objects.get_for_model(Capacidad)
    perm = Permission.objects.get(
        content_type=ct, codename=rbac.codename_de("conversacion.operar")
    )
    group.permissions.add(perm)


class IniciarConversacionFormTests(TestCase):
    def test_acepta_conversacion_personal_sin_endurecer_contrato_legacy(self):
        form = IniciarConversacionForm({
            'tipo': 'personal',
            'prioridad': 'normal',
        })

        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['tipo'], 'personal')

    def test_mensaje_form_normaliza_espacios(self):
        form = MensajeConversacionForm({'mensaje': '  hola  '})

        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['mensaje'], 'hola')


class ChatServicesTests(TestCase):
    def setUp(self):
        self.operador = User.objects.create_user(
            username='operador-chat',
            password='secret',
            first_name='Operador',
            last_name='Chat',
        )

    @patch('conversaciones.services.chat.NotificacionService.notificar_nueva_conversacion')
    @patch('conversaciones.services.chat.AsignadorAutomatico.asignar_conversacion_automatica', return_value=False)
    def test_iniciar_conversacion_publica_crea_conversacion_activa(self, mock_asignar, mock_notificar):
        conversacion = iniciar_conversacion_publica({
            'tipo': 'anonima',
            'dni': '',
            'sexo': '',
            'datos_renaper': {},
            'prioridad': 'alta',
        })

        self.assertEqual(conversacion.estado, 'activa')
        self.assertEqual(conversacion.prioridad, 'alta')
        mock_asignar.assert_called_once_with(conversacion)
        mock_notificar.assert_called_once_with(conversacion)

    def test_crear_mensaje_operador_autoasigna_si_no_tiene_operador(self):
        conversacion = Conversacion.objects.create(tipo='anonima', prioridad='normal', estado='activa')

        mensaje = crear_mensaje_operador(conversacion, self.operador, 'respuesta')

        conversacion.refresh_from_db()
        self.assertEqual(mensaje.remitente, 'operador')
        self.assertEqual(conversacion.operador_asignado, self.operador)
        self.assertEqual(Mensaje.objects.filter(conversacion=conversacion).count(), 1)

    def test_crear_mensaje_operador_falla_si_esta_asignada_a_otro(self):
        otro_operador = User.objects.create_user(username='otro-operador', password='secret')
        conversacion = Conversacion.objects.create(
            tipo='anonima',
            prioridad='normal',
            estado='activa',
            operador_asignado=otro_operador,
        )

        with self.assertRaises(PermissionError):
            crear_mensaje_operador(conversacion, self.operador, 'respuesta')

    def test_marcar_mensajes_ciudadano_leidos_actualiza_solo_no_leidos(self):
        conversacion = Conversacion.objects.create(
            tipo='anonima',
            prioridad='normal',
            estado='activa',
            operador_asignado=self.operador,
        )
        Mensaje.objects.create(conversacion=conversacion, remitente='ciudadano', contenido='uno', leido=False)
        Mensaje.objects.create(conversacion=conversacion, remitente='ciudadano', contenido='dos', leido=True)
        Mensaje.objects.create(conversacion=conversacion, remitente='operador', contenido='tres', leido=False)

        actualizados = marcar_mensajes_ciudadano_leidos(conversacion)

        self.assertEqual(actualizados, 1)
        self.assertEqual(
            Mensaje.objects.filter(conversacion=conversacion, remitente='ciudadano', leido=False).count(),
            0,
        )

    def test_selector_alertas_count_devuelve_solo_no_vistas_del_operador(self):
        conversacion = Conversacion.objects.create(
            tipo='anonima',
            prioridad='normal',
            estado='activa',
            operador_asignado=self.operador,
        )
        HistorialAlertaConversacion.objects.create(
            conversacion=conversacion,
            operador=self.operador,
            tipo='NUEVO_MENSAJE',
            mensaje='alerta 1',
            vista=False,
        )
        HistorialAlertaConversacion.objects.create(
            conversacion=conversacion,
            operador=self.operador,
            tipo='NUEVA_CONVERSACION',
            mensaje='alerta 2',
            vista=True,
        )

        self.assertEqual(get_alertas_conversaciones_count(self.operador), 1)


class ConversacionesViewsContractTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.operador = User.objects.create_user(
            username='super-chat',
            password='secret',
            is_superuser=True,
            is_staff=True,
        )

    def _csrf_headers(self):
        return {'HTTP_X_CSRFTOKEN': self.client.cookies['csrftoken'].value}

    def test_chat_ciudadano_emite_cookie_csrf(self):
        response = self.client.get(reverse('conversaciones:chat_ciudadano'))

        self.assertEqual(response.status_code, 200)
        self.assertIn('csrftoken', self.client.cookies)

    @patch('conversaciones.views.public.iniciar_conversacion_publica')
    def test_iniciar_conversacion_publica_requiere_csrf_y_devuelve_contrato(self, mock_iniciar):
        mock_iniciar.return_value = Conversacion(id=44)
        url = reverse('conversaciones:iniciar_conversacion')

        self.client.get(reverse('conversaciones:chat_ciudadano'))
        forbidden = self.client.post(
            url,
            data='{"tipo":"anonima","prioridad":"normal"}',
            content_type='application/json',
        )
        allowed = self.client.post(
            url,
            data='{"tipo":"anonima","prioridad":"normal"}',
            content_type='application/json',
            **self._csrf_headers(),
        )

        self.assertEqual(forbidden.status_code, 403)
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(allowed.json(), {'success': True, 'conversacion_id': 44})

    def test_evaluar_conversacion_publica_requiere_csrf_y_actualiza_satisfaccion(self):
        conversacion = Conversacion.objects.create(tipo='anonima', prioridad='normal', estado='cerrada')
        url = reverse('conversaciones:evaluar', args=[conversacion.id])

        self.client.get(reverse('conversaciones:chat_ciudadano'))
        forbidden = self.client.post(
            url,
            data='{"satisfaccion":5}',
            content_type='application/json',
        )
        allowed = self.client.post(
            url,
            data='{"satisfaccion":4}',
            content_type='application/json',
            **self._csrf_headers(),
        )

        conversacion.refresh_from_db()
        self.assertEqual(forbidden.status_code, 403)
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(allowed.json(), {'success': True})
        self.assertEqual(conversacion.satisfaccion, 4)

    def test_enviar_mensaje_operador_requiere_csrf_y_devuelve_contrato(self):
        conversacion = Conversacion.objects.create(tipo='anonima', prioridad='normal', estado='activa')
        url = reverse('conversaciones:enviar_mensaje_operador', args=[conversacion.id])

        self.client.force_login(self.operador)
        self.client.get(reverse('conversaciones:detalle', args=[conversacion.id]))
        forbidden = self.client.post(
            url,
            data='{"mensaje":"hola"}',
            content_type='application/json',
        )
        allowed = self.client.post(
            url,
            data='{"mensaje":"hola"}',
            content_type='application/json',
            **self._csrf_headers(),
        )

        payload = allowed.json()
        conversacion.refresh_from_db()
        self.assertEqual(forbidden.status_code, 403)
        self.assertEqual(allowed.status_code, 200)
        self.assertTrue(payload['success'])
        self.assertEqual(payload['mensaje']['contenido'], 'hola')
        self.assertEqual(conversacion.operador_asignado, self.operador)

    @override_settings(WEBSOCKETS_ENABLED=True)
    def test_lista_renderiza_urls_para_websocket_runtime(self):
        group = Group.objects.create(name='Conversaciones')
        _conceder_conversacion_operar(group)
        operador = User.objects.create_user(username='operador-lista', password='secret')
        operador.groups.add(group)

        self.client.force_login(operador)
        response = self.client.get(reverse('conversaciones:lista'))

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('data-detail-api-url-template="/conversaciones/api/conversacion/0/"', html)
        self.assertIn('data-detail-url-template="/conversaciones/0/"', html)
        self.assertIn('data-close-url-template="/conversaciones/0/cerrar/"', html)
        self.assertIn('data-list-ws-path="/ws/conversaciones/"', html)

    @override_settings(WEBSOCKETS_ENABLED=True)
    def test_detalle_renderiza_path_websocket_desde_template(self):
        group = Group.objects.create(name='Conversaciones')
        _conceder_conversacion_operar(group)
        operador = User.objects.create_user(username='operador-detalle', password='secret')
        operador.groups.add(group)
        conversacion = Conversacion.objects.create(
            tipo='anonima',
            prioridad='normal',
            estado='activa',
            operador_asignado=operador,
        )

        self.client.force_login(operador)
        response = self.client.get(reverse('conversaciones:detalle', args=[conversacion.id]))

        self.assertEqual(response.status_code, 200)
        self.assertIn('data-ws-path-template="/ws/conversaciones/0/"', response.content.decode())

    def test_lista_no_expone_path_websocket_si_runtime_no_lo_soporta(self):
        group = Group.objects.create(name='Conversaciones')
        _conceder_conversacion_operar(group)
        operador = User.objects.create_user(username='operador-lista-local', password='secret')
        operador.groups.add(group)

        self.client.force_login(operador)
        response = self.client.get(reverse('conversaciones:lista'))

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('websocket_disable.js', html)
        self.assertIn('data-list-ws-path=""', html)

    def test_http_a_endpoint_websocket_devuelve_upgrade_required(self):
        response = self.client.get('/ws/conversaciones/')

        self.assertEqual(response.status_code, 426)
        self.assertIn('requires an ASGI server', response.content.decode())
