"""Ayudas compartidas por los tests de Notificaciones."""

import shutil
import tempfile
from io import BytesIO

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from openpyxl import Workbook

from core import rbac
from notificaciones.models import Campana
from notificaciones.services import campanas as servicio
from notificaciones.services import html as servicio_html
from notificaciones.services.lectura_excel import parsear_destinatarios
from users.models import Capacidad

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
HTML_BASICO = "<html><head><style>p{color:#333}</style></head><body><p>Hola</p></body></html>"
TODAS = ("notificacion.ver", "notificacion.gestionar", "notificacion.enviar")


def xlsx(filas, nombre="lista.xlsx"):
    """Un .xlsx subido con ``filas`` (cada una, lista de celdas o un valor suelto)."""
    libro = Workbook()
    hoja = libro.active
    for fila in filas:
        hoja.append(list(fila) if isinstance(fila, (list, tuple)) else [fila])
    salida = BytesIO()
    libro.save(salida)
    return SimpleUploadedFile(nombre, salida.getvalue(), content_type=XLSX)


def html(texto=HTML_BASICO, nombre="correo.html"):
    return SimpleUploadedFile(nombre, texto.encode("utf-8"), content_type="text/html")


def correos(n, dominio="ejemplo.com"):
    return [f"persona{i}@{dominio}" for i in range(n)]


def usuario_con(*codigos, username=None, email=""):
    """Un usuario con un rol que tiene exactamente ``codigos``."""
    username = username or f"u_{'_'.join(c.split('.')[-1] for c in codigos) or 'sin'}"
    user = User.objects.create_user(username, email=email or f"{username}@ejemplo.com", password="x")
    if codigos:
        grupo = Group.objects.create(name=f"rol {username}")
        ct = ContentType.objects.get_for_model(Capacidad)
        for codigo in codigos:
            permiso, _ = Permission.objects.get_or_create(
                content_type=ct, codename=rbac.codename_de(codigo), defaults={"name": codigo}
            )
            grupo.permissions.add(permiso)
        user.groups.add(grupo)
    return user


def crear_campana(*, emails=None, html_texto=HTML_BASICO, nombre="Campaña de prueba", asunto="Asunto", usuario=None):
    """Una campaña «A enviar» armada por el mismo servicio que usa la pantalla."""
    filas = ["email", *(emails if emails is not None else correos(3))]
    excel = xlsx(filas)
    cuerpo = html(html_texto)
    return servicio.crear_campana(
        nombre=nombre,
        asunto=asunto,
        archivo_excel=excel,
        archivo_html=cuerpo,
        lectura=parsear_destinatarios(excel),
        datos_html=servicio_html.procesar(cuerpo),
        usuario=usuario,
    )


class ConMediaTemporal(TestCase):
    """Los archivos de las campañas van a un ``MEDIA_ROOT`` descartable."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._media = tempfile.mkdtemp(prefix="notif-media-")
        cls._ajustes = override_settings(MEDIA_ROOT=cls._media)
        cls._ajustes.enable()

    @classmethod
    def tearDownClass(cls):
        cls._ajustes.disable()
        shutil.rmtree(cls._media, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        cache.clear()


__all__ = ["Campana", "ConMediaTemporal", "crear_campana", "correos", "html", "usuario_con", "xlsx", "TODAS"]
