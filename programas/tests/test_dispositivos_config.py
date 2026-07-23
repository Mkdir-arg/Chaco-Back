from io import StringIO

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.management import call_command
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase
from django.urls import reverse

from core import rbac
from legajos.models import Ciudadano
from programas.forms import CampoTipoDispositivoForm
from programas.models import CampoTipoDispositivo, Programa, TipoCampo, TipoDispositivo
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
    rol.permissions.add(permiso("programa.configurar"))
    return rol


class CampoTipoDispositivoFormTests(TestCase):
    def setUp(self):
        self.tipo = TipoDispositivo.objects.create(codigo="PRUEBA", nombre="Prueba")

    def datos(self, **cambios):
        base = {
            "seccion": "A",
            "nombre": "Campo",
            "tipo_campo": TipoCampo.STRING,
            "opciones_texto": "",
            "orden": 1,
        }
        base.update(cambios)
        return base

    def test_guarda_selector_con_opciones_json(self):
        form = CampoTipoDispositivoForm(
            self.datos(tipo_campo=TipoCampo.SELECTOR, opciones_texto="Una\nDos"),
            tipo_dispositivo=self.tipo,
        )

        self.assertTrue(form.is_valid(), form.errors)
        campo = form.save()
        self.assertEqual(campo.opciones, ["Una", "Dos"])
        self.assertEqual(campo.tipo_dispositivo, self.tipo)

    def test_rechaza_selectores_sin_opciones(self):
        for tipo_campo in (TipoCampo.SELECTOR, TipoCampo.SELECTOR_MULTIPLE):
            with self.subTest(tipo_campo=tipo_campo):
                form = CampoTipoDispositivoForm(
                    self.datos(tipo_campo=tipo_campo),
                    tipo_dispositivo=self.tipo,
                )
                self.assertFalse(form.is_valid())
                self.assertIn(
                    "Indicá al menos una opción para este tipo de campo.",
                    form.errors["opciones_texto"],
                )

    def test_descarta_opciones_en_tipos_no_selectores(self):
        for tipo_campo in (TipoCampo.STRING, TipoCampo.INT, TipoCampo.DATE, TipoCampo.ARCHIVO):
            with self.subTest(tipo_campo=tipo_campo):
                form = CampoTipoDispositivoForm(
                    self.datos(nombre=f"Campo {tipo_campo}", tipo_campo=tipo_campo, opciones_texto="No persiste"),
                    tipo_dispositivo=self.tipo,
                )
                self.assertTrue(form.is_valid(), form.errors)
                self.assertIsNone(form.save().opciones)

    def test_nombre_es_obligatorio(self):
        form = CampoTipoDispositivoForm(self.datos(nombre=""), tipo_dispositivo=self.tipo)
        self.assertFalse(form.is_valid())
        self.assertIn("nombre", form.errors)


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
        cls.campo = CampoTipoDispositivo.objects.create(
            tipo_dispositivo=cls.tipo,
            seccion="B",
            nombre="Segundo",
            tipo_campo=TipoCampo.STRING,
            orden=2,
        )

    def setUp(self):
        cache.clear()

    def test_abm_tipo_y_toggle_conserva_campos(self):
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
        self.assertTrue(self.tipo.campos_configurados.filter(pk=self.campo.pk).exists())
        self.client.post(reverse("dispositivos:tipo_toggle", args=[self.tipo.pk]))
        self.tipo.refresh_from_db()
        self.assertTrue(self.tipo.activo)

    def test_abm_campos_y_detalle_agrupado(self):
        CampoTipoDispositivo.objects.create(
            tipo_dispositivo=self.tipo,
            seccion="A",
            nombre="Primero",
            tipo_campo=TipoCampo.INT,
            orden=1,
        )
        self.client.force_login(self.admin)
        detalle = self.client.get(reverse("dispositivos:tipo_detalle", args=[self.tipo.pk]))
        self.assertEqual(detalle.status_code, 200)
        self.assertContains(detalle, "A")
        self.assertContains(detalle, "B")
        contenido = detalle.content.decode()
        self.assertLess(contenido.index("Primero"), contenido.index("Segundo"))

        alta = self.client.post(
            reverse("dispositivos:campo_crear", args=[self.tipo.pk]),
            {
                "seccion": "C",
                "nombre": "Selector",
                "tipo_campo": TipoCampo.SELECTOR,
                "opciones_texto": "Sí\nNo",
                "obligatorio": "on",
                "orden": 3,
            },
        )
        self.assertEqual(alta.status_code, 302)
        campo = CampoTipoDispositivo.objects.get(nombre="Selector")
        self.assertEqual(campo.opciones, ["Sí", "No"])

        edicion = self.client.post(
            reverse("dispositivos:campo_editar", args=[campo.pk]),
            {
                "seccion": "D",
                "nombre": "Selector editado",
                "tipo_campo": TipoCampo.STRING,
                "opciones_texto": "Se descarta",
                "orden": 4,
            },
        )
        self.assertEqual(edicion.status_code, 302)
        campo.refresh_from_db()
        self.assertEqual(campo.seccion, "D")
        self.assertIsNone(campo.opciones)

        borrado = self.client.post(reverse("dispositivos:campo_eliminar", args=[campo.pk]))
        self.assertEqual(borrado.status_code, 302)
        self.assertFalse(CampoTipoDispositivo.objects.filter(pk=campo.pk).exists())

    def test_tipo_sin_campos_muestra_estado_vacio(self):
        vacio = TipoDispositivo.objects.create(codigo="VACIO", nombre="Vacío")
        self.client.force_login(self.admin)
        respuesta = self.client.get(reverse("dispositivos:tipo_detalle", args=[vacio.pk]))
        self.assertContains(respuesta, "todavía no tiene campos")
        self.assertContains(respuesta, "Agregar primer campo")

    def test_ediciones_renderizan_modal_sobre_detalle_y_altas_siguen_como_pagina(self):
        self.client.force_login(self.admin)

        editar_tipo = self.client.get(reverse("dispositivos:tipo_editar", args=[self.tipo.pk]))
        self.assertContains(editar_tipo, "data-edit-modal")
        self.assertContains(editar_tipo, "Editar tipo de dispositivo")
        self.assertContains(editar_tipo, "Segundo")

        editar_campo = self.client.get(reverse("dispositivos:campo_editar", args=[self.campo.pk]))
        self.assertContains(editar_campo, "data-edit-modal")
        self.assertContains(editar_campo, "Editar campo")
        self.assertContains(editar_campo, 'value="Segundo"')

        nuevo_tipo = self.client.get(reverse("dispositivos:tipo_crear"))
        nuevo_campo = self.client.get(reverse("dispositivos:campo_crear", args=[self.tipo.pk]))
        self.assertNotContains(nuevo_tipo, "data-edit-modal")
        self.assertNotContains(nuevo_campo, "data-edit-modal")

    def test_error_de_edicion_de_campo_permanece_en_modal(self):
        self.client.force_login(self.admin)
        respuesta = self.client.post(
            reverse("dispositivos:campo_editar", args=[self.campo.pk]),
            {
                "seccion": "B",
                "nombre": "Segundo",
                "tipo_campo": TipoCampo.SELECTOR,
                "opciones_texto": "",
                "orden": 2,
            },
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "data-edit-modal")
        self.assertContains(respuesta, "Indicá al menos una opción para este tipo de campo.")

    def test_usuario_sin_permiso_y_admin_otro_programa_reciben_403(self):
        rutas = [
            ("get", reverse("dispositivos:tipos"), None),
            ("get", reverse("dispositivos:tipo_crear"), None),
            ("post", reverse("dispositivos:tipo_crear"), {}),
            ("get", reverse("dispositivos:tipo_editar", args=[self.tipo.pk]), None),
            ("get", reverse("dispositivos:tipo_toggle", args=[self.tipo.pk]), None),
            ("post", reverse("dispositivos:tipo_toggle", args=[self.tipo.pk]), {}),
            ("get", reverse("dispositivos:campo_crear", args=[self.tipo.pk]), None),
            ("post", reverse("dispositivos:campo_crear", args=[self.tipo.pk]), {}),
            ("get", reverse("dispositivos:campo_editar", args=[self.campo.pk]), None),
            ("post", reverse("dispositivos:campo_editar", args=[self.campo.pk]), {}),
            ("get", reverse("dispositivos:campo_eliminar", args=[self.campo.pk]), None),
            ("post", reverse("dispositivos:campo_eliminar", args=[self.campo.pk]), {}),
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


class CargarConfigDispositivosCommandTests(TestCase):
    def setUp(self):
        CampoTipoDispositivo.objects.all().delete()
        TipoDispositivo.objects.all().delete()

    def ejecutar(self):
        salida = StringIO()
        call_command("cargar_config_dispositivos", stdout=salida)
        return salida.getvalue()

    def test_carga_conteos_secciones_y_grupo_sanguineo(self):
        self.ejecutar()
        adulto = TipoDispositivo.objects.get(codigo="ADULTO_MAYOR")
        abordaje = TipoDispositivo.objects.get(codigo="ABORDAJE_PSICOSOCIAL")

        self.assertEqual(adulto.campos_configurados.count(), 33)
        self.assertEqual(abordaje.campos_configurados.count(), 45)
        self.assertTrue(
            adulto.campos_configurados.filter(
                seccion__startswith="F.",
                nombre="Grupo sanguíneo",
            ).exists()
        )
        self.assertFalse(any(field.name == "grupo_sanguineo" for field in Ciudadano._meta.fields))
        self.assertFalse(adulto.campos_configurados.filter(seccion__startswith="H.").exists())
        self.assertFalse(abordaje.campos_configurados.filter(nombre__iexact="Egreso").exists())

    def test_es_idempotente_y_no_pisa_configuracion_existente(self):
        self.ejecutar()
        adulto = TipoDispositivo.objects.get(codigo="ADULTO_MAYOR")
        campo = adulto.campos_configurados.get(nombre="Oficio")
        campo.obligatorio = True
        campo.save(update_fields=["obligatorio"])

        salida = self.ejecutar()
        campo.refresh_from_db()
        self.assertTrue(campo.obligatorio)
        self.assertEqual(adulto.campos_configurados.count(), 33)
        self.assertEqual(
            TipoDispositivo.objects.get(codigo="ABORDAJE_PSICOSOCIAL").campos_configurados.count(),
            45,
        )
        self.assertIn("78 ya existentes", salida)
