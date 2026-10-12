"""Configuración de tipos de dispositivo: formulario, ABM y alcance.

El ABM de **campos** del tipo se fue con `CampoTipoDispositivo` (MVP v2, release A):
el F-00 configurable muere con la admisión vieja, y lo que lo reemplace va sobre el
motor de formularios. Lo que queda acá es el tipo en sí.
"""

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase
from django.urls import reverse

from core import rbac
from programas.forms import DispositivoForm, TipoDispositivoForm
from programas.models import Programa, TipoDispositivo
from users.models import Capacidad, RolMeta


def permiso(codigo):
    content_type = ContentType.objects.get_for_model(Capacidad)
    return Permission.objects.get(codename=rbac.codename_de(codigo), content_type=content_type)


def rol_configuracion(nombre, programa, *, activo=True):
    rol = Group.objects.create(name=nombre)
    RolMeta.objects.create(
        grupo=rol,
        categoria=rbac.CATEGORIA_PROGRAMA,
        programa=programa,
        activo=activo,
    )
    # `programa.configurar` habilita las vistas de configuración; las dos transversales
    # son las que le dan el alcance sobre los ABM de Usuarios y Roles de su programa
    # (y con eso la sección Administración del sidebar).
    rol.permissions.add(
        permiso("programa.configurar"),
        permiso("programa.usuario.administrar"),
        permiso("programa.rol.administrar"),
    )
    return rol


class TipoDispositivoFormTests(TestCase):
    """Los dos venían de `test_dispositivos_camas.py`, que se fue con `Cama`."""

    def test_forma_de_tipo_conserva_umbrales_por_defecto_en_post_existente(self):
        tipo = TipoDispositivo.objects.create(codigo="FORM", nombre="Formulario", maneja_camas=True)

        form = TipoDispositivoForm(
            {"codigo": "FORM", "nombre": "Formulario actualizado", "descripcion": "", "activo": "on"},
            instance=tipo,
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_formulario_de_dispositivo_no_permite_editar_capacidad_manual(self):
        self.assertNotIn("camas_totales", DispositivoForm.base_fields)


class ConfiguracionDispositivosViewsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.programa, _ = Programa.objects.get_or_create(
            codigo="DISPOSITIVOS",
            defaults={
                "nombre": "Dispositivos",
                "tipo": Programa.TipoPrograma.DISPOSITIVOS,
            },
        )
        cls.otro_programa = Programa.objects.create(codigo="BECAS-TEST", nombre="Becas test")
        cls.rol = rol_configuracion("Admin Dispositivos test", cls.programa)
        cls.rol_otro = rol_configuracion("Admin Becas test", cls.otro_programa)
        cls.admin = User.objects.create_user("admin-dispositivos", password="x")
        cls.admin.groups.add(cls.rol)
        cls.ajeno = User.objects.create_user("admin-becas", password="x")
        cls.ajeno.groups.add(cls.rol_otro)
        cls.sin_permiso = User.objects.create_user("operador", password="x")
        cls.tipo = TipoDispositivo.objects.create(
            codigo="TEST",
            nombre="Tipo test",
            maneja_camas=True,
        )

    def setUp(self):
        cache.clear()

    def test_abm_tipo_y_toggle(self):
        self.client.force_login(self.admin)
        alta = self.client.post(
            reverse("dispositivos:tipo_crear"),
            {
                "codigo": "NUEVO",
                "nombre": "Nuevo tipo",
                "descripcion": "Demo",
                "maneja_camas": "on",
                "activo": "on",
            },
        )
        nuevo = TipoDispositivo.objects.get(codigo="NUEVO")
        self.assertRedirects(alta, reverse("dispositivos:tipo_detalle", args=[nuevo.pk]))
        self.assertTrue(nuevo.maneja_camas)

        edicion = self.client.post(
            reverse("dispositivos:tipo_editar", args=[self.tipo.pk]),
            {
                "codigo": "TEST",
                "nombre": "Tipo editado",
                "descripcion": "",
                "activo": "on",
            },
        )
        self.assertEqual(edicion.status_code, 302)
        self.tipo.refresh_from_db()
        self.assertEqual(self.tipo.nombre, "Tipo editado")
        self.assertFalse(self.tipo.maneja_camas)

        self.client.post(reverse("dispositivos:tipo_toggle", args=[self.tipo.pk]))
        self.tipo.refresh_from_db()
        self.assertFalse(self.tipo.activo)
        self.client.post(reverse("dispositivos:tipo_toggle", args=[self.tipo.pk]))
        self.tipo.refresh_from_db()
        self.assertTrue(self.tipo.activo)

    def test_el_detalle_del_tipo_ya_no_ofrece_formulario_propio(self):
        vacio = TipoDispositivo.objects.create(codigo="VACIO", nombre="Vacío")
        self.client.force_login(self.admin)
        respuesta = self.client.get(reverse("dispositivos:tipo_detalle", args=[vacio.pk]))
        self.assertContains(respuesta, "no tiene formulario propio")
        self.assertNotContains(respuesta, "Agregar campo")

    def test_ediciones_renderizan_modal_sobre_detalle_y_altas_siguen_como_pagina(self):
        self.client.force_login(self.admin)

        detalle = self.client.get(reverse("dispositivos:tipo_detalle", args=[self.tipo.pk]))
        self.assertContains(detalle, "data-edit-url")

        editar_tipo = self.client.get(reverse("dispositivos:tipo_editar", args=[self.tipo.pk]))
        self.assertContains(editar_tipo, "data-edit-modal")
        self.assertContains(editar_tipo, "Editar tipo de dispositivo")
        self.assertContains(editar_tipo, 'value="Tipo test"')
        self.assertContains(
            editar_tipo,
            f'href="{reverse("dispositivos:tipo_detalle", args=[self.tipo.pk])}"',
            count=2,
        )

        nuevo_tipo = self.client.get(reverse("dispositivos:tipo_crear"))
        self.assertNotContains(nuevo_tipo, "data-edit-modal")

    def test_get_ajax_de_ediciones_devuelve_solo_el_modal(self):
        self.client.force_login(self.admin)

        casos = [
            (
                reverse("dispositivos:tipo_editar", args=[self.tipo.pk]),
                "Editar tipo de dispositivo",
            ),
        ]
        for ruta, titulo in casos:
            with self.subTest(ruta=ruta):
                respuesta = self.client.get(
                    ruta,
                    HTTP_X_REQUESTED_WITH="XMLHttpRequest",
                )
                self.assertEqual(respuesta.status_code, 200)
                data = respuesta.json()
                self.assertTrue(data["ok"])
                self.assertIn("data-edit-modal", data["html"])
                self.assertIn("data-ajax", data["html"])
                self.assertIn(f'action="{ruta}"', data["html"])
                self.assertIn(titulo, data["html"])
                self.assertNotIn("<!DOCTYPE html>", data["html"])

    def test_post_ajax_actualiza_tipo_y_devuelve_parcial_del_detalle(self):
        self.client.force_login(self.admin)
        respuesta = self.client.post(
            reverse("dispositivos:tipo_editar", args=[self.tipo.pk]),
            {
                "codigo": "TEST",
                "nombre": "Tipo actualizado sin recarga",
                "descripcion": "Actualizado por AJAX",
                "activo": "on",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(respuesta.status_code, 200)
        data = respuesta.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["target"], "#dispositivos-detail-content")
        self.assertIn("Tipo actualizado sin recarga", data["html"])
        self.assertIn("Actualizado por AJAX", data["html"])
        self.assertIn("data-edit-url", data["html"])
        self.tipo.refresh_from_db()
        self.assertEqual(self.tipo.nombre, "Tipo actualizado sin recarga")

    def test_error_ajax_de_edicion_de_tipo_devuelve_errores_por_campo(self):
        self.client.force_login(self.admin)
        respuesta = self.client.post(
            reverse("dispositivos:tipo_editar", args=[self.tipo.pk]),
            {
                "codigo": "",
                "nombre": "",
                "descripcion": "",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(respuesta.status_code, 400)
        data = respuesta.json()
        self.assertFalse(data["ok"])
        self.assertIn("codigo", data["errors"])
        self.assertIn("nombre", data["errors"])

    def test_usuario_anonimo_recibe_401_json_en_ediciones_ajax(self):
        rutas = [reverse("dispositivos:tipo_editar", args=[self.tipo.pk])]
        for ruta in rutas:
            for metodo in ("get", "post"):
                with self.subTest(ruta=ruta, metodo=metodo):
                    respuesta = getattr(self.client, metodo)(
                        ruta,
                        data={},
                        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
                    )
                    self.assertEqual(respuesta.status_code, 401)
                    data = respuesta.json()
                    self.assertFalse(data["ok"])
                    self.assertEqual(data["message"], "Tu sesión venció. Volvé a iniciar sesión.")
                    self.assertIn("next=", data["redirect"])

    def test_error_de_edicion_permanece_en_modal(self):
        self.client.force_login(self.admin)
        respuesta = self.client.post(
            reverse("dispositivos:tipo_editar", args=[self.tipo.pk]),
            {"codigo": "", "nombre": "", "descripcion": ""},
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "data-edit-modal")
        self.assertContains(respuesta, "Este campo es requerido.")

    def test_usuario_sin_permiso_recibe_403_json_en_ediciones_ajax(self):
        self.client.force_login(self.ajeno)
        rutas = [reverse("dispositivos:tipo_editar", args=[self.tipo.pk])]
        for ruta in rutas:
            for metodo in ("get", "post"):
                with self.subTest(ruta=ruta, metodo=metodo):
                    respuesta = getattr(self.client, metodo)(
                        ruta,
                        data={},
                        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
                    )
                    self.assertEqual(respuesta.status_code, 403)
                    self.assertEqual(
                        respuesta.json(),
                        {
                            "ok": False,
                            "message": "No tiene permisos para realizar esta acción.",
                        },
                    )

    def test_usuario_sin_permiso_y_admin_otro_programa_reciben_403(self):
        rutas = [
            ("get", reverse("dispositivos:tipos"), None),
            ("get", reverse("dispositivos:tipo_crear"), None),
            ("post", reverse("dispositivos:tipo_crear"), {}),
            ("get", reverse("dispositivos:tipo_editar", args=[self.tipo.pk]), None),
            ("get", reverse("dispositivos:tipo_toggle", args=[self.tipo.pk]), None),
            ("post", reverse("dispositivos:tipo_toggle", args=[self.tipo.pk]), {}),
        ]
        for usuario in (self.sin_permiso, self.ajeno):
            self.client.force_login(usuario)
            for verbo, ruta, datos in rutas:
                with self.subTest(usuario=usuario.username, verbo=verbo, ruta=ruta):
                    respuesta = getattr(self.client, verbo)(ruta, data=datos)
                    self.assertEqual(respuesta.status_code, 403)

    def test_superusuario_activo_puede_operar_y_el_inactivo_no(self):
        superusuario = User.objects.create_superuser("root-dispositivos", "root@example.com", "x")
        self.client.force_login(superusuario)
        self.assertEqual(self.client.get(reverse("dispositivos:tipos")).status_code, 200)

        superusuario.is_active = False
        superusuario.save(update_fields=["is_active"])
        self.client.force_login(superusuario)
        self.assertIn(self.client.get(reverse("dispositivos:tipos")).status_code, (302, 403))

    def test_rol_desactivado_deja_de_habilitar(self):
        self.rol.meta.activo = False
        self.rol.meta.save(update_fields=["activo"])
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("dispositivos:tipos")).status_code, 403)

    def test_sidebar_muestra_entrada_solo_con_alcance_dispositivos(self):
        def render(usuario):
            request = RequestFactory().get("/")
            request.user = usuario
            request.resolver_match = None
            return render_to_string("includes/sidebar/opciones.html", {"request": request, "branding": {}})

        contenido = render(self.admin)
        grupo_dispositivos = contenido.index('<span class="flex-1">Dispositivos</span>')
        grupo_administracion = contenido.index('<span class="flex-1">Administración</span>')
        configuracion_dispositivos = contenido.index("Configuración", grupo_dispositivos)

        self.assertLess(grupo_dispositivos, configuracion_dispositivos)
        self.assertLess(configuracion_dispositivos, grupo_administracion)
        self.assertNotIn("Dispositivos", contenido[grupo_administracion:])
        self.assertNotIn('href="/dispositivos/config/"', render(self.ajeno))
