from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from conversaciones.forms.chat import MensajeConversacionForm
from conversaciones.models import Conversacion, HistorialAlertaConversacion, Mensaje
from conversaciones.selectors.conversaciones import (
    get_alertas_conversaciones_count,
    get_conversaciones_queryset_para_lista,
)
from conversaciones.services.chat import (
    crear_mensaje_operador,
    marcar_mensajes_ciudadano_leidos,
)
from core import rbac
from users.models import Capacidad, RolMeta


def _conceder_conversacion_operar(group):
    """Convierte el grupo en un rol ACTIVO con la capacidad conversacion.operar."""
    RolMeta.objects.get_or_create(grupo=group, defaults={"categoria": "Backoffice", "activo": True})
    ct = ContentType.objects.get_for_model(Capacidad)
    perm = Permission.objects.get(content_type=ct, codename=rbac.codename_de("conversacion.operar"))
    group.permissions.add(perm)


class MensajeConversacionFormTests(TestCase):
    def test_mensaje_form_normaliza_espacios(self):
        form = MensajeConversacionForm({"mensaje": "  hola  "})

        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["mensaje"], "hola")


class ChatServicesTests(TestCase):
    def setUp(self):
        self.operador = User.objects.create_user(
            username="operador-chat",
            password="secret",
            first_name="Operador",
            last_name="Chat",
        )

    def test_crear_mensaje_operador_autoasigna_si_no_tiene_operador(self):
        conversacion = Conversacion.objects.create(tipo="anonima", prioridad="normal", estado="activa")

        mensaje = crear_mensaje_operador(conversacion, self.operador, "respuesta")

        conversacion.refresh_from_db()
        self.assertEqual(mensaje.remitente, "operador")
        self.assertEqual(conversacion.operador_asignado, self.operador)
        self.assertEqual(Mensaje.objects.filter(conversacion=conversacion).count(), 1)

    def test_crear_mensaje_operador_falla_si_esta_asignada_a_otro(self):
        otro_operador = User.objects.create_user(username="otro-operador", password="secret")
        conversacion = Conversacion.objects.create(
            tipo="anonima",
            prioridad="normal",
            estado="activa",
            operador_asignado=otro_operador,
        )

        with self.assertRaises(PermissionError):
            crear_mensaje_operador(conversacion, self.operador, "respuesta")

    def test_marcar_mensajes_ciudadano_leidos_actualiza_solo_no_leidos(self):
        conversacion = Conversacion.objects.create(
            tipo="anonima",
            prioridad="normal",
            estado="activa",
            operador_asignado=self.operador,
        )
        Mensaje.objects.create(conversacion=conversacion, remitente="ciudadano", contenido="uno", leido=False)
        Mensaje.objects.create(conversacion=conversacion, remitente="ciudadano", contenido="dos", leido=True)
        Mensaje.objects.create(conversacion=conversacion, remitente="operador", contenido="tres", leido=False)

        actualizados = marcar_mensajes_ciudadano_leidos(conversacion)

        self.assertEqual(actualizados, 1)
        self.assertEqual(
            Mensaje.objects.filter(conversacion=conversacion, remitente="ciudadano", leido=False).count(),
            0,
        )

    def test_selector_alertas_count_devuelve_solo_no_vistas_del_operador(self):
        conversacion = Conversacion.objects.create(
            tipo="anonima",
            prioridad="normal",
            estado="activa",
            operador_asignado=self.operador,
        )
        HistorialAlertaConversacion.objects.create(
            conversacion=conversacion,
            operador=self.operador,
            tipo="NUEVO_MENSAJE",
            mensaje="alerta 1",
            vista=False,
        )
        HistorialAlertaConversacion.objects.create(
            conversacion=conversacion,
            operador=self.operador,
            tipo="NUEVA_CONVERSACION",
            mensaje="alerta 2",
            vista=True,
        )

        self.assertEqual(get_alertas_conversaciones_count(self.operador), 1)

    def test_selector_lista_usa_un_orden_estable_para_paginar(self):
        Conversacion.objects.create(tipo="anonima", prioridad="normal", estado="activa")

        queryset = get_conversaciones_queryset_para_lista(self.operador, {})

        self.assertTrue(queryset.ordered)


# G1-01 fase 2: acá vivían `ConversacionesViewsContractTests` (contrato de
# `enviar_mensaje_operador`, URLs de la lista y el detalle, el 426 de
# `/ws/conversaciones/`) y `NotificadorGlobalConversacionesPerformanceTests` (el
# polling de `conversaciones_tiempo_real_global.js`). Las rutas, los WS y el JS se
# apagaron; lo que queda medido es que ya no existen, en
# `conversaciones/tests/test_apagado.py`. Los servicios y los selectores de abajo
# siguen probados: son lo que habría que reactivar si el chat vuelve.


class ListaConversacionesConsultasTests(TestCase):
    def setUp(self):
        self.operador = User.objects.create_user(username="supervisor-lista", password="secret", is_superuser=True)

    def test_la_pagina_cuenta_mensajes_sin_agrupar_toda_la_tabla_de_mensajes(self):
        con_mensajes = Conversacion.objects.create(tipo="anonima", prioridad="normal", estado="activa")
        sin_mensajes = Conversacion.objects.create(tipo="anonima", prioridad="normal", estado="pendiente")
        Mensaje.objects.create(conversacion=con_mensajes, remitente="ciudadano", contenido="hola")
        Mensaje.objects.create(conversacion=con_mensajes, remitente="ciudadano", contenido="sigo acá")
        Mensaje.objects.create(conversacion=con_mensajes, remitente="operador", contenido="respuesta")
        Mensaje.objects.create(conversacion=con_mensajes, remitente="ciudadano", contenido="leído", leido=True)

        queryset = get_conversaciones_queryset_para_lista(self.operador, {})

        # La página es UNA consulta y los contadores salen de ella (sin N+1 ni JOIN con mensajes).
        with self.assertNumQueries(1):
            filas = {conversacion.pk: conversacion for conversacion in queryset[:25]}
        sql = str(queryset.query)
        self.assertNotIn(f"JOIN {connection.ops.quote_name('conversaciones_mensaje')}", sql)
        self.assertEqual(filas[con_mensajes.pk].total_mensajes, 4)
        self.assertEqual(filas[con_mensajes.pk].mensajes_no_leidos, 2)
        # Sin mensajes cuenta 0 (no None): la plantilla imprime el número tal cual.
        self.assertEqual(filas[sin_mensajes.pk].total_mensajes, 0)
        self.assertEqual(filas[sin_mensajes.pk].mensajes_no_leidos, 0)
        with self.assertNumQueries(1):
            self.assertEqual(queryset.count(), 2)

    def test_responder_no_relee_al_operador_si_la_conversacion_lo_trae_precargado(self):
        conversacion = Conversacion.objects.create(
            tipo="anonima", prioridad="normal", estado="activa", operador_asignado=self.operador
        )
        conversacion = Conversacion.objects.select_related("operador_asignado").get(pk=conversacion.pk)

        # INSERT del mensaje + UPDATE de la primera respuesta: ninguna lectura de auth_user.
        with CaptureQueriesContext(connection) as capturadas:
            mensaje = crear_mensaje_operador(conversacion, self.operador, "respuesta")

        self.assertEqual(mensaje.remitente, "operador")
        self.assertEqual(len(capturadas.captured_queries), 2)
        self.assertFalse([q["sql"] for q in capturadas.captured_queries if "auth_user" in q["sql"]])
