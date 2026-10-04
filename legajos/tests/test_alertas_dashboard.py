"""`/legajos/alertas/` y sus tres endpoints AJAX (RED-06, auditoría oct-2026).

La pantalla ya dio 500 una vez (Cambio 66): un `select_related("conversacion__usuario")`
sobre un campo que `Conversacion` no tiene levantaba `FieldError` para **todo**
operador con `conversacion.operar`, y nadie se enteró porque ningún test la
abría. El arreglo quedó, el test no. Acá queda.

El contrato JSON de `count`, `preview` y `cerrar-ajax` es el que leen
`alertas_websocket.js` y el include `_alerta`: cambiarle una clave rompe el
badge del navbar sin que nada falle del lado del servidor.
"""

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse

from conversaciones.models import Conversacion, HistorialAlertaConversacion
from core import rbac
from legajos.models import AlertaCiudadano, Ciudadano, LegajoAtencion
from users.models import Capacidad, RolMeta


def _rol(nombre, *codigos):
    grupo, _ = Group.objects.get_or_create(name=nombre)
    RolMeta.objects.get_or_create(grupo=grupo, defaults={"categoria": rbac.CATEGORIA_BACKOFFICE, "activo": True})
    ct = ContentType.objects.get_for_model(Capacidad)
    for codigo in codigos:
        grupo.permissions.add(Permission.objects.get(codename=rbac.codename_de(codigo), content_type=ct))
    return grupo


class AlertasDashboardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ciudadano = Ciudadano.objects.create(dni="21777888", nombre="Mirta", apellido="Quiroga")
        cls.operador = User.objects.create_user("operador-alertas-dash", password="Clave-Seg-2026x")
        cls.legajo = LegajoAtencion.objects.create(responsable=cls.operador)
        cls.alerta = AlertaCiudadano.objects.create(
            ciudadano=cls.ciudadano,
            legajo=cls.legajo,
            tipo=AlertaCiudadano.TipoAlerta.SIN_CONTACTO,
            prioridad=AlertaCiudadano.Prioridad.CRITICA,
            mensaje="Sin contacto hace 30 días",
        )
        # El operador ve sus alertas (`ciudadano.ver`) y además opera conversaciones.
        cls.operador.groups.add(_rol("Rol alertas + conversaciones", "ciudadano.ver", "conversacion.operar"))
        conversacion = Conversacion.objects.create(tipo="anonima", estado="activa", operador_asignado=cls.operador)
        HistorialAlertaConversacion.objects.create(
            conversacion=conversacion,
            operador=cls.operador,
            tipo="NUEVO_MENSAJE",
            mensaje="Nuevo mensaje del ciudadano",
        )

    def setUp(self):
        # `alertas_count_ajax` cachea 30 s con la clave `alertas_count:<user.id>`.
        # La base se revierte entre tests pero la caché no, y los ids de usuario se
        # repiten de un `TestCase` a otro: sin esto el contador llega con el valor
        # que dejó otro test y la suite completa falla donde las apps sueltas pasan.
        cache.clear()
        self.cliente = Client()
        self.cliente.force_login(self.operador)

    def test_responde_200_para_un_operador_de_conversaciones(self):
        """Falla con `FieldError` si vuelve el `select_related` inválido."""
        respuesta = self.cliente.get(reverse("legajos:alertas_dashboard"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(respuesta.context["alertas_conversaciones"]), 1)

    def test_responde_200_sin_la_capacidad_de_conversaciones_y_no_las_lista(self):
        otro = User.objects.create_user("solo-ciudadanos", password="Clave-Seg-2026x")
        otro.groups.add(_rol("Rol solo ciudadanos", "ciudadano.ver"))
        cliente = Client()
        cliente.force_login(otro)

        respuesta = cliente.get(reverse("legajos:alertas_dashboard"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(list(respuesta.context["alertas_conversaciones"]), [])

    def test_los_tres_endpoints_ajax_responden_json(self):
        count = self.cliente.get(reverse("legajos:alertas_count_ajax"))
        self.assertEqual(count.status_code, 200)
        self.assertEqual(count.json(), {"count": 1, "criticas": 1})

        preview = self.cliente.get(reverse("legajos:alertas_preview_ajax"))
        self.assertEqual(preview.status_code, 200)
        fila = preview.json()["results"][0]
        for clave in ("id", "ciudadano_nombre", "mensaje", "prioridad", "tipo", "creado", "legajo_id"):
            self.assertIn(clave, fila)
        self.assertEqual(fila["ciudadano_nombre"], "Mirta Quiroga")

        cerrar = self.cliente.post(reverse("legajos:cerrar_alerta_ajax", args=[self.alerta.id]))
        self.assertEqual(cerrar.status_code, 200)
        self.assertEqual(cerrar.json(), {"success": True})
        self.alerta.refresh_from_db()
        self.assertFalse(self.alerta.activa)
