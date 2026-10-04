"""Humo de Legajos: ninguna de sus rutas revienta (RED-06, auditoría oct-2026).

23 de las 36 rutas de la app no tenían una sola cita en los tests. No es
teórico: el Cambio 66 metió un `select_related("conversacion__usuario")` sobre
un campo que no existe y `/legajos/alertas/` devolvió **500 a todo operador con
`conversacion.operar`** hasta que alguien lo leyó. Un `FieldError`, un template
renombrado o un selector que cambia de firma no se ven desde afuera.

El barrido va con un usuario que tiene **todas** las capacidades y con datos
reales en la base, así que no se detiene en el primer guard ni en el primer 404:
llega al cuerpo de la vista, que es donde están los `FieldError`.

`ARGS_POR_RUTA` es literal a propósito: una ruta nueva sin entrada pone el test
en rojo con el nombre, en vez de quedar sin cubrir en silencio.
"""

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from core import rbac
from legajos.models import Adjunto, AlertaCiudadano, Ciudadano, LegajoAtencion
from legajos.urls import urlpatterns
from programas.models import DerivacionPrograma, Programa
from users.models import Capacidad, RolMeta


def _usuario_con_todas_las_capacidades(username):
    grupo, _ = Group.objects.get_or_create(name="Rol humo legajos")
    RolMeta.objects.get_or_create(grupo=grupo, defaults={"categoria": rbac.CATEGORIA_BACKOFFICE, "activo": True})
    ct = ContentType.objects.get_for_model(Capacidad)
    grupo.permissions.set(Permission.objects.filter(content_type=ct))
    usuario = User.objects.create_user(username, password="Clave-Seg-2026x")
    usuario.groups.add(grupo)
    return usuario


class PantallasDeLegajosAbrenTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ciudadano = Ciudadano.objects.create(dni="21666777", nombre="Mirta", apellido="Quiroga")
        cls.responsable = User.objects.create_user("resp-humo", password="Clave-Seg-2026x")
        cls.legajo = LegajoAtencion.objects.create(responsable=cls.responsable)
        cls.programa = Programa.objects.create(codigo="HUMO", nombre="Programa de humo")
        cls.derivacion = DerivacionPrograma.objects.create(
            ciudadano=cls.ciudadano,
            programa_destino=cls.programa,
            motivo="Derivación de humo",
            estado=DerivacionPrograma.Estado.PENDIENTE,
        )
        cls.alerta = AlertaCiudadano.objects.create(
            ciudadano=cls.ciudadano,
            legajo=cls.legajo,
            tipo=AlertaCiudadano.TipoAlerta.SIN_CONTACTO,
            prioridad=AlertaCiudadano.Prioridad.MEDIA,
            mensaje="Sin contacto hace 30 días",
        )
        cls.adjunto = Adjunto.objects.create(
            content_type=ContentType.objects.get_for_model(Ciudadano),
            object_id=cls.ciudadano.id,
            archivo=SimpleUploadedFile("humo.pdf", b"%PDF-1.4"),
            etiqueta="humo.pdf",
        )
        cls.operador = _usuario_con_todas_las_capacidades("humo-legajos")

    def setUp(self):
        self.navegador = Client(raise_request_exception=False)
        self.navegador.force_login(self.operador)

    def _args_por_ruta(self):
        """Argumentos reales por nombre de URL. `()` = la ruta no lleva argumentos."""
        return {
            "lista": (),
            "nuevo": (),
            "ciudadanos": (),
            "ciudadanos_exportar_csv": (),
            "ciudadano_buscar_api": (),
            "ciudadano_nuevo": (),
            "ciudadano_confirmar": (),
            "ciudadano_manual": (),
            "ciudadano_detalle": (self.ciudadano.id,),
            "ciudadano_editar": (self.ciudadano.id,),
            "dispositivos_ciudadano": (self.ciudadano.id, 1),
            "programas": (),
            "programa_detalle": (self.programa.id,),
            "derivar_programa": (self.ciudadano.id,),
            "dashboard_contactos": (),
            "reportes": (),
            "exportar_csv": (),
            "derivacion_ciudadano_aceptar": (self.derivacion.id,),
            "derivacion_ciudadano_rechazar": (self.derivacion.id,),
            "historial_contactos": (self.legajo.id,),
            "red_contactos": (self.legajo.id,),
            "actividades_ciudadano": (self.ciudadano.id,),
            "subir_archivos": (self.legajo.id,),
            "archivos_legajo": (self.legajo.id,),
            "archivos_ciudadano": (self.ciudadano.id,),
            "subir_archivos_ciudadano": (self.ciudadano.id,),
            "eliminar_archivo_ciudadano": (self.ciudadano.id, self.adjunto.id),
            "eliminar_archivo_legajo": (self.legajo.id, self.adjunto.id),
            "alertas_ciudadano": (self.ciudadano.id,),
            "cerrar_alerta_ciudadano": (self.alerta.id,),
            "timeline_ciudadano": (self.ciudadano.id,),
            "prediccion_riesgo": (self.ciudadano.id,),
            "evolucion_legajo": (self.legajo.id,),
            "alertas_dashboard": (),
            "cerrar_alerta_ajax": (self.alerta.id,),
            "alertas_count_ajax": (),
            "alertas_preview_ajax": (),
        }

    def test_el_mapa_cubre_todas_las_rutas_de_legajos(self):
        """Una ruta nueva sin entrada en el mapa queda sin humo: eso avisa acá."""
        del_urlconf = {patron.name for patron in urlpatterns}

        self.assertEqual(sorted(del_urlconf - set(self._args_por_ruta())), [])
        self.assertEqual(sorted(set(self._args_por_ruta()) - del_urlconf), [])

    def test_ninguna_pantalla_de_legajos_revienta(self):
        rotas = []
        for nombre, args in self._args_por_ruta().items():
            url = reverse(f"legajos:{nombre}", args=args)
            respuesta = self.navegador.get(url)
            if respuesta.status_code == 405:
                respuesta = self.navegador.post(url, {})
            with self.subTest(ruta=nombre):
                if respuesta.status_code >= 500:
                    rotas.append(f"legajos:{nombre} → {url} ({respuesta.status_code})")

        self.assertEqual(rotas, [], "\n".join(["Rutas de Legajos que revientan:", *rotas]))
