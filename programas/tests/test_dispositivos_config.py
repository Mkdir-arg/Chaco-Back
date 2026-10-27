"""Configuración de tipos de dispositivo: formulario, ABM y alcance.

El ABM de **campos** del tipo se dio de baja con la versión 1 (MVP v2, release A):
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
from programas.models import Dispositivo, Plaza, Programa, Sector, TipoDispositivo
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
    """Los dos venían de `test_dispositivos_camas.py`, que se fue con el modelo de camas de la versión 1."""

    def test_forma_de_tipo_conserva_umbrales_por_defecto_en_post_existente(self):
        tipo = TipoDispositivo.objects.create(codigo="FORM", nombre="Formulario", maneja_camas=True)

        form = TipoDispositivoForm(
            {"codigo": "FORM", "nombre": "Formulario actualizado", "descripcion": "", "activo": "on"},
            instance=tipo,
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_formulario_de_dispositivo_no_permite_editar_capacidad_manual(self):
        self.assertNotIn("camas_totales", DispositivoForm.base_fields)


class TipoDispositivoSectoresYPlazasTests(TestCase):
    """«Sectores y plazas» reemplaza a «Maneja camas» en el modal del tipo."""

    def _form(self, datos=None, instance=None):
        base = {"codigo": "SP", "nombre": "Con plazas", "descripcion": "", "activo": "on"}
        return TipoDispositivoForm({**base, **(datos or {})}, instance=instance)

    def test_tildada_sin_tipos_de_plaza_es_error(self):
        form = self._form({"maneja_sectores_plazas": "on"})

        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors["tipos_plaza_admitidos"], ["Elegí al menos un tipo de plaza."])

    def test_tildada_con_cama_maneja_plazas_y_sincroniza_maneja_camas(self):
        form = self._form({"maneja_sectores_plazas": "on", "tipos_plaza_admitidos": ["CAMA"]})

        self.assertTrue(form.is_valid(), form.errors)
        tipo = form.save()
        tipo.refresh_from_db()
        self.assertEqual(tipo.tipos_plaza_admitidos, ["CAMA"])
        self.assertTrue(tipo.maneja_plazas)
        self.assertTrue(tipo.maneja_camas)

    def test_destildada_vacia_los_tipos_y_la_obligatoriedad(self):
        tipo = TipoDispositivo.objects.create(
            codigo="SP",
            nombre="Con plazas",
            maneja_camas=True,
            tipos_plaza_admitidos=["CAMA", "CUPO"],
            plaza_obligatoria_al_ingresar=True,
        )
        form = self._form(
            {"tipos_plaza_admitidos": ["CAMA"], "plaza_obligatoria_al_ingresar": "on"},
            instance=tipo,
        )

        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        tipo.refresh_from_db()
        self.assertEqual(tipo.tipos_plaza_admitidos, [])
        self.assertFalse(tipo.plaza_obligatoria_al_ingresar)
        self.assertFalse(tipo.maneja_plazas)
        self.assertFalse(tipo.maneja_camas)

    def test_destildar_con_plazas_cargadas_no_deja(self):
        tipo = TipoDispositivo.objects.create(
            codigo="SP", nombre="Con plazas", maneja_camas=True, tipos_plaza_admitidos=["CAMA"]
        )
        dispositivo = Dispositivo.objects.create(tipo=tipo, codigo="SP-1", nombre="Institución")
        sector = Sector.objects.create(dispositivo=dispositivo, nombre="Pabellón", capacidad=2)
        Plaza.objects.create(sector=sector, codigo="P-1")
        Plaza.objects.create(sector=sector, codigo="P-2")

        form = self._form(instance=tipo)

        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors["maneja_sectores_plazas"],
            [
                "Hay 2 plazas cargadas en instituciones de este tipo: "
                "no se puede dejar de manejar plazas mientras existan."
            ],
        )
        tipo.refresh_from_db()
        self.assertTrue(tipo.maneja_plazas)

    def test_destildar_con_una_sola_plaza_cargada_concuerda_en_singular(self):
        tipo = TipoDispositivo.objects.create(
            codigo="SP1", nombre="Con una plaza", maneja_camas=True, tipos_plaza_admitidos=["CAMA"]
        )
        dispositivo = Dispositivo.objects.create(tipo=tipo, codigo="SP1-1", nombre="Institución")
        sector = Sector.objects.create(dispositivo=dispositivo, nombre="Pabellón", capacidad=1)
        Plaza.objects.create(sector=sector, codigo="P-1")

        form = self._form(instance=tipo)

        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors["maneja_sectores_plazas"],
            [
                "Hay 1 plaza cargada en instituciones de este tipo: "
                "no se puede dejar de manejar plazas mientras existan."
            ],
        )

    def test_tipo_de_la_v1_con_maneja_camas_viene_tildado_con_cama(self):
        tipo = TipoDispositivo.objects.create(codigo="MUN", nombre="Municipal", maneja_camas=True)

        form = TipoDispositivoForm(instance=tipo)

        self.assertTrue(form["maneja_sectores_plazas"].value())
        self.assertEqual(form["tipos_plaza_admitidos"].value(), ["CAMA"])

    def test_exigir_plaza_viene_tildada_en_el_alta(self):
        form = TipoDispositivoForm()

        self.assertTrue(form["plaza_obligatoria_al_ingresar"].value())

    def test_exigir_plaza_viene_tildada_en_un_tipo_de_la_v1_sin_configurar(self):
        tipo = TipoDispositivo.objects.create(codigo="MUN", nombre="Municipal", maneja_camas=True)

        form = TipoDispositivoForm(instance=tipo)

        self.assertTrue(form["plaza_obligatoria_al_ingresar"].value())

    def test_exigir_plaza_respeta_lo_guardado_en_un_tipo_de_la_v2(self):
        tipo = TipoDispositivo.objects.create(
            codigo="CDD",
            nombre="Centro de día",
            tipos_plaza_admitidos=["CUPO"],
            plaza_obligatoria_al_ingresar=False,
        )

        form = TipoDispositivoForm(instance=tipo)

        self.assertFalse(form["plaza_obligatoria_al_ingresar"].value())

    def test_alta_sin_enviar_la_casilla_de_exigir_plaza_guarda_false(self):
        form = self._form({"maneja_sectores_plazas": "on", "tipos_plaza_admitidos": ["CAMA"]})

        self.assertTrue(form.is_valid(), form.errors)
        tipo = form.save()
        tipo.refresh_from_db()
        self.assertFalse(tipo.plaza_obligatoria_al_ingresar)

    def test_guardar_el_tipo_de_la_v1_le_da_la_solapa_al_detalle_de_la_institucion(self):
        programa, _ = Programa.objects.get_or_create(
            codigo="DISPOSITIVOS",
            defaults={"nombre": "Dispositivos", "tipo": Programa.TipoPrograma.DISPOSITIVOS},
        )
        rol = Group.objects.create(name="Lector plazas test")
        RolMeta.objects.create(grupo=rol, categoria=rbac.CATEGORIA_PROGRAMA, programa=programa, activo=True)
        rol.permissions.add(permiso("dispositivo.ver"), permiso("programa.configurar"))
        usuario = User.objects.create_user("lector-plazas", password="x")
        usuario.groups.add(rol)
        tipo = TipoDispositivo.objects.create(codigo="MUN", nombre="Municipal", maneja_camas=True)
        dispositivo = Dispositivo.objects.create(tipo=tipo, codigo="MUN-1", nombre="Municipal 1")
        url = reverse("dispositivos:detalle", args=[dispositivo.pk])
        self.client.force_login(usuario)
        self.assertNotContains(self.client.get(url), "Sectores y plazas")

        form = TipoDispositivoForm(
            {
                "codigo": "MUN",
                "nombre": "Municipal",
                "descripcion": "",
                "maneja_sectores_plazas": "on",
                "tipos_plaza_admitidos": ["CAMA"],
                "activo": "on",
            },
            instance=tipo,
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()

        self.assertContains(self.client.get(url), "Sectores y plazas")


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
                "maneja_sectores_plazas": "on",
                "tipos_plaza_admitidos": ["CAMA"],
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

    def test_el_detalle_del_tipo_ya_no_ofrece_el_abm_de_campos_del_f00(self):
        """Los campos del F-00 no vuelven: lo que hay ahora son los formularios por
        momento (P17), que se prueban en `test_dispositivos_formularios_tipo.py`."""
        vacio = TipoDispositivo.objects.create(codigo="VACIO", nombre="Vacío")
        self.client.force_login(self.admin)
        respuesta = self.client.get(reverse("dispositivos:tipo_detalle", args=[vacio.pk]))
        self.assertContains(respuesta, "Este tipo todavía no tiene formularios")
        self.assertNotContains(respuesta, "Agregar campo")

    def test_ediciones_renderizan_modal_sobre_detalle_y_altas_siguen_como_pagina(self):
        self.client.force_login(self.admin)

        detalle = self.client.get(reverse("dispositivos:tipo_detalle", args=[self.tipo.pk]))
        self.assertContains(detalle, "data-edit-url")

        editar_tipo = self.client.get(reverse("dispositivos:tipo_editar", args=[self.tipo.pk]))
        self.assertContains(editar_tipo, "data-edit-modal")
        self.assertContains(editar_tipo, "Editar tipo de dispositivo")
        self.assertContains(editar_tipo, 'value="Tipo test"')
        # Modal estándar: se cierra con la X y «Cancelar» (`data-becas-modal-cerrar`) y a dónde
        # vuelve lo dice `data-cancel-url`, que lee el JS de la pantalla.
        self.assertContains(editar_tipo, 'aria-labelledby="dispositivos-edit-title"')
        self.assertContains(
            editar_tipo,
            f'data-cancel-url="{reverse("dispositivos:tipo_detalle", args=[self.tipo.pk])}"',
        )

        nuevo_tipo = self.client.get(reverse("dispositivos:tipo_crear"))
        self.assertNotContains(nuevo_tipo, "data-edit-modal")

    def test_un_clic_dentro_del_modal_no_lo_vuelve_a_abrir(self):
        """El modal también lleva `data-edit-url`: si el clic lo busca sin `a`, cada clic adentro lo
        pone gris y lo vuelve a pedir, y la casilla no se tilda."""
        self.client.force_login(self.admin)

        editar_tipo = self.client.get(reverse("dispositivos:tipo_editar", args=[self.tipo.pk]))

        self.assertContains(editar_tipo, "closest('a[data-edit-url]')")
        self.assertNotContains(editar_tipo, "closest('[data-edit-url]')")

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

    def test_p14_estado_junto_al_titulo_conserva_textos_y_acciones(self):
        self.client.force_login(self.admin)
        # El semáforo se muestra si el tipo maneja plazas (Cambio 372), no por `maneja_camas`.
        self.tipo.tipos_plaza_admitidos = ["CAMA"]
        for activo, texto, tono in ((True, "Activo", "success"), (False, "Inactivo", "gray")):
            self.tipo.activo = activo
            self.tipo.save(update_fields=["activo", "tipos_plaza_admitidos"])
            with self.subTest(activo=activo):
                respuesta = self.client.get(reverse("dispositivos:tipo_detalle", args=[self.tipo.pk]))
                self.assertContains(
                    respuesta,
                    '<p class="text-xs font-semibold uppercase tracking-wide text-fg-brand mb-1">'
                    "Tipo de dispositivo</p>",
                    html=True,
                )
                self.assertInHTML(
                    '<div class="flex items-center gap-3 flex-wrap">'
                    '<h1 class="text-3xl font-extrabold text-heading tracking-tight">Tipo test</h1>'
                    f'<span class="badge badge-dot badge-{tono}">{texto}</span></div>',
                    respuesta.content.decode(),
                )
                self.assertContains(respuesta, "Editar tipo")
                self.assertContains(respuesta, "Desactivar" if activo else "Activar")
                self.assertContains(respuesta, "Semáforo de ocupación: amarillo desde")
