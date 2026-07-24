"""Contratos del legajo institucional y su alcance RBAC (#180, #175)."""

from unittest.mock import patch

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import RequestFactory, TestCase
from django.urls import reverse

from core import rbac
from programas.forms import DispositivoForm
from programas.models import AsignacionDispositivo, Dispositivo, Programa, TipoDispositivo, TrazaDispositivo
from programas.services.dispositivos import (
    buscar_posibles_duplicados,
    enviar_a_validacion,
    puede_operar_dispositivo,
    validar_dispositivo,
)
from programas.views.dispositivos_legajo import DispositivoUpdateView
from users.models import Capacidad, RolMeta


def permiso(codigo):
    content_type = ContentType.objects.get_for_model(Capacidad)
    return Permission.objects.get(codename=rbac.codename_de(codigo), content_type=content_type)


class AlcanceDispositivosTests(TestCase):
    def setUp(self):
        self.programa, _ = Programa.objects.get_or_create(
            codigo="DISPOSITIVOS",
            defaults={
                "nombre": "Dispositivos",
                "tipo": Programa.TipoPrograma.DISPOSITIVOS,
            },
        )
        self.tipo = TipoDispositivo.objects.create(codigo="AM", nombre="Adulto Mayor")
        self.dispositivo_a = Dispositivo.objects.create(codigo="HOGAR-A", nombre="Hogar A", tipo=self.tipo)
        self.dispositivo_b = Dispositivo.objects.create(codigo="HOGAR-B", nombre="Hogar B", tipo=self.tipo)

        self.rol = Group.objects.create(name="Operador Dispositivos")
        RolMeta.objects.create(
            grupo=self.rol,
            categoria=rbac.CATEGORIA_PROGRAMA,
            programa=self.programa,
            activo=True,
        )
        self.rol.permissions.add(permiso("dispositivo.editar"))

        self.operador = User.objects.create_user("operador-dispositivo", password="x")
        self.operador.groups.add(self.rol)
        AsignacionDispositivo.objects.create(dispositivo=self.dispositivo_a, rol=self.rol)
        cache.clear()

    def test_operador_solo_puede_operar_el_dispositivo_asignado(self):
        self.assertTrue(puede_operar_dispositivo(self.operador, self.dispositivo_a, "dispositivo.editar"))
        self.assertFalse(puede_operar_dispositivo(self.operador, self.dispositivo_b, "dispositivo.editar"))

    def test_alcances_de_roles_activos_se_unen_y_un_rol_inactivo_no_aporta(self):
        rol_b = Group.objects.create(name="Operador Dispositivos B")
        meta_b = RolMeta.objects.create(
            grupo=rol_b,
            categoria=rbac.CATEGORIA_PROGRAMA,
            programa=self.programa,
            activo=True,
        )
        rol_b.permissions.add(permiso("dispositivo.editar"))
        self.operador.groups.add(rol_b)
        AsignacionDispositivo.objects.create(dispositivo=self.dispositivo_b, rol=rol_b)

        self.assertTrue(puede_operar_dispositivo(self.operador, self.dispositivo_a, "dispositivo.editar"))
        self.assertTrue(puede_operar_dispositivo(self.operador, self.dispositivo_b, "dispositivo.editar"))

        meta_b.activo = False
        meta_b.save(update_fields=["activo"])
        usuario_refrescado = User.objects.get(pk=self.operador.pk)
        self.assertFalse(puede_operar_dispositivo(usuario_refrescado, self.dispositivo_b, "dispositivo.editar"))

    def test_alcance_fino_de_otro_programa_no_se_combina_con_capacidad_de_dispositivos(self):
        rol_dispositivos = Group.objects.create(name="Sin alcance Dispositivos")
        RolMeta.objects.create(
            grupo=rol_dispositivos,
            categoria=rbac.CATEGORIA_PROGRAMA,
            programa=self.programa,
            activo=True,
        )
        rol_dispositivos.permissions.add(permiso("dispositivo.editar"))
        programa_becas, _ = Programa.objects.get_or_create(codigo="BECAS", defaults={"nombre": "Becas"})
        rol_becas = Group.objects.create(name="Alcance ajeno Becas")
        RolMeta.objects.create(
            grupo=rol_becas,
            categoria=rbac.CATEGORIA_PROGRAMA,
            programa=programa_becas,
            activo=True,
        )
        rol_becas.permissions.add(permiso("dispositivo.editar"))
        AsignacionDispositivo.objects.create(dispositivo=self.dispositivo_b, rol=rol_becas)
        usuario = User.objects.create_user("roles-cruzados", password="x")
        usuario.groups.add(rol_dispositivos, rol_becas)

        self.assertFalse(puede_operar_dispositivo(usuario, self.dispositivo_b, "dispositivo.editar"))


class DispositivoFormTests(TestCase):
    def setUp(self):
        self.tipo = TipoDispositivo.objects.create(codigo="AM", nombre="Adulto Mayor")
        Dispositivo.objects.create(
            codigo="HOGAR-01",
            nombre="Hogar Norte",
            localidad="Resistencia",
            tipo=self.tipo,
        )

    def test_codigo_normalizado_duplicado_se_bloquea(self):
        form = DispositivoForm(
            {
                "tipo": self.tipo.pk,
                "codigo": " hogar-01 ",
                "nombre": "Otro hogar",
                "localidad": "Resistencia",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("Ya existe un dispositivo con este código institucional.", form.errors["codigo"])

    def test_busqueda_avisa_coincidencia_blanda_sin_bloquear_codigo_distinto(self):
        resultado = buscar_posibles_duplicados(
            codigo="HOGAR-02",
            nombre="Hogar Norte",
            localidad="Resistencia",
        )

        self.assertFalse(resultado["codigo_duplicado"])
        self.assertEqual(list(resultado["dispositivos"]), [Dispositivo.objects.get(codigo="HOGAR-01")])


class ValidacionDispositivoTests(TestCase):
    def setUp(self):
        self.tipo = TipoDispositivo.objects.create(codigo="AM", nombre="Adulto Mayor")
        self.dispositivo = Dispositivo.objects.create(codigo="HOGAR-01", nombre="Hogar Norte", tipo=self.tipo)
        self.supervisor = User.objects.create_user("supervisor-dispositivo", password="x")

    def test_borrador_incompleto_no_pasa_a_validacion(self):
        with self.assertRaisesMessage(ValidationError, "Completá los campos obligatorios antes de validar"):
            enviar_a_validacion(self.dispositivo, self.supervisor)

        self.dispositivo.refresh_from_db()
        self.assertEqual(self.dispositivo.estado, Dispositivo.Estado.BORRADOR)

    def test_supervisor_valida_y_queda_traza_de_la_transicion(self):
        self.dispositivo.localidad = "Resistencia"
        self.dispositivo.domicilio = "Av. Sarmiento 100"
        self.dispositivo.responsable_nombre = "Laura Pérez"
        self.dispositivo.contacto_telefono = "3624000000"
        self.dispositivo.save()

        enviar_a_validacion(self.dispositivo, self.supervisor)
        validar_dispositivo(self.dispositivo, self.supervisor)

        self.dispositivo.refresh_from_db()
        traza = TrazaDispositivo.objects.get(dispositivo=self.dispositivo, accion="VALIDADO")
        self.assertEqual(self.dispositivo.estado, Dispositivo.Estado.ACTIVO)
        self.assertEqual(traza.usuario, self.supervisor)
        self.assertEqual(traza.estado_anterior, Dispositivo.Estado.PENDIENTE_VALIDACION)
        self.assertEqual(traza.estado_nuevo, Dispositivo.Estado.ACTIVO)

    def test_transicion_y_traza_se_revierten_juntas_si_falla_auditoria(self):
        self.dispositivo.localidad = "Resistencia"
        self.dispositivo.domicilio = "Av. Sarmiento 100"
        self.dispositivo.responsable_nombre = "Laura Pérez"
        self.dispositivo.contacto_telefono = "3624000000"
        self.dispositivo.save()

        with patch("programas.services.dispositivos._registrar_traza", side_effect=RuntimeError("falló auditoría")):
            with self.assertRaisesMessage(RuntimeError, "falló auditoría"):
                enviar_a_validacion(self.dispositivo, self.supervisor)

        self.dispositivo.refresh_from_db()
        self.assertEqual(self.dispositivo.estado, Dispositivo.Estado.BORRADOR)

    def test_traza_no_admite_edicion_ni_borrado(self):
        traza = TrazaDispositivo.objects.create(
            dispositivo=self.dispositivo,
            usuario=self.supervisor,
            accion="CREADO",
            estado_nuevo=Dispositivo.Estado.BORRADOR,
        )

        with self.assertRaisesMessage(ValidationError, "inmutables"):
            traza.save()
        with self.assertRaisesMessage(ValidationError, "no se eliminan"):
            traza.delete()
        with self.assertRaisesMessage(ValidationError, "inmutables"):
            TrazaDispositivo.objects.filter(pk=traza.pk).update(accion="EDITADO")
        with self.assertRaisesMessage(ValidationError, "inmutables"):
            TrazaDispositivo.objects.bulk_update([traza], ["accion"])
        with self.assertRaisesMessage(ValidationError, "no se eliminan"):
            TrazaDispositivo.objects.filter(pk=traza.pk).delete()
        with self.assertRaisesMessage(ValidationError, "inmutables"):
            TrazaDispositivo._base_manager.filter(pk=traza.pk).update(accion="EDITADO")


class LegajoDispositivoViewsTests(TestCase):
    def setUp(self):
        self.programa, _ = Programa.objects.get_or_create(
            codigo="DISPOSITIVOS",
            defaults={
                "nombre": "Dispositivos",
                "tipo": Programa.TipoPrograma.DISPOSITIVOS,
            },
        )
        self.tipo = TipoDispositivo.objects.create(codigo="AM", nombre="Adulto Mayor")
        self.dispositivo_a = Dispositivo.objects.create(codigo="HOGAR-A", nombre="Hogar A", tipo=self.tipo)
        self.dispositivo_b = Dispositivo.objects.create(codigo="HOGAR-B", nombre="Hogar B", tipo=self.tipo)
        self.rol = Group.objects.create(name="Consulta Dispositivos")
        RolMeta.objects.create(
            grupo=self.rol,
            categoria=rbac.CATEGORIA_PROGRAMA,
            programa=self.programa,
            activo=True,
        )
        self.rol.permissions.add(permiso("dispositivo.ver"))
        self.consulta = User.objects.create_user("consulta-dispositivos", password="x")
        self.consulta.groups.add(self.rol)
        AsignacionDispositivo.objects.create(dispositivo=self.dispositivo_a, rol=self.rol)

        self.operador_rol = Group.objects.create(name="Operador legajo")
        RolMeta.objects.create(
            grupo=self.operador_rol,
            categoria=rbac.CATEGORIA_PROGRAMA,
            programa=self.programa,
            activo=True,
        )
        self.operador_rol.permissions.add(
            permiso("dispositivo.ver"),
            permiso("dispositivo.crear"),
            permiso("dispositivo.editar"),
        )
        self.operador = User.objects.create_user("operador-legajo", password="x")
        self.operador.groups.add(self.operador_rol)
        AsignacionDispositivo.objects.create(dispositivo=self.dispositivo_a, rol=self.operador_rol)

        self.supervisor_rol = Group.objects.create(name="Supervisor legajo")
        RolMeta.objects.create(
            grupo=self.supervisor_rol,
            categoria=rbac.CATEGORIA_PROGRAMA,
            programa=self.programa,
            activo=True,
        )
        self.supervisor_rol.permissions.add(permiso("dispositivo.ver"), permiso("dispositivo.validar"))
        self.supervisor = User.objects.create_user("supervisor-legajo", password="x")
        self.supervisor.groups.add(self.supervisor_rol)
        AsignacionDispositivo.objects.create(dispositivo=self.dispositivo_a, rol=self.supervisor_rol)
        cache.clear()

    def test_listado_y_detalle_aplican_alcance_incluso_por_url_directa(self):
        self.client.force_login(self.consulta)

        listado = self.client.get(reverse("dispositivos:lista"))
        detalle_en_alcance = self.client.get(reverse("dispositivos:detalle", args=[self.dispositivo_a.pk]))
        fuera_de_alcance = self.client.get(reverse("dispositivos:detalle", args=[self.dispositivo_b.pk]))

        self.assertContains(listado, "Hogar A")
        self.assertNotContains(listado, "Hogar B")
        self.assertContains(detalle_en_alcance, "Hogar A")
        self.assertNotContains(detalle_en_alcance, "Editar")
        self.assertEqual(fuera_de_alcance.status_code, 403)

    def test_busqueda_previa_muestra_coincidencias_antes_del_alta(self):
        self.client.force_login(self.operador)

        response = self.client.get(
            reverse("dispositivos:buscar_duplicados"),
            {"codigo": " hogar-a ", "nombre": "Hogar A", "localidad": "Resistencia"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["codigo_duplicado"])
        self.assertEqual(response.json()["coincidencias"][0]["codigo"], "HOGAR-A")

    def test_edicion_conserva_valor_anterior_en_auditoria(self):
        self.client.force_login(self.operador)

        response = self.client.post(
            reverse("dispositivos:editar", args=[self.dispositivo_a.pk]),
            {
                "tipo": self.tipo.pk,
                "codigo": "HOGAR-A",
                "nombre": "Hogar A",
                "localidad": "Resistencia",
                "domicilio": "",
                "responsable_nombre": "",
                "responsable_documento": "",
                "contacto_telefono": "",
                "contacto_email": "",
                "horarios": "",
                "camas_totales": "0",
            },
        )

        self.assertEqual(response.status_code, 302)
        traza = TrazaDispositivo.objects.get(dispositivo=self.dispositivo_a, accion="EDITADO")
        self.assertIn('"anterior": ""', traza.detalle)
        self.assertIn('"nuevo": "Resistencia"', traza.detalle)

    def test_validacion_exige_capacidad_y_alcance_tambien_por_post_directo(self):
        self.dispositivo_a.localidad = "Resistencia"
        self.dispositivo_a.domicilio = "Av. Sarmiento 100"
        self.dispositivo_a.responsable_nombre = "Laura Pérez"
        self.dispositivo_a.contacto_telefono = "3624000000"
        self.dispositivo_a.save()
        enviar_a_validacion(self.dispositivo_a, self.operador)

        self.client.force_login(self.operador)
        sin_capacidad = self.client.post(reverse("dispositivos:validar", args=[self.dispositivo_a.pk]))
        self.assertEqual(sin_capacidad.status_code, 403)
        self.dispositivo_a.refresh_from_db()
        self.assertEqual(self.dispositivo_a.estado, Dispositivo.Estado.PENDIENTE_VALIDACION)

    def test_post_directo_ajax_sin_capacidad_devuelve_json_403(self):
        self.dispositivo_a.localidad = "Resistencia"
        self.dispositivo_a.domicilio = "Av. Sarmiento 100"
        self.dispositivo_a.responsable_nombre = "Laura Pérez"
        self.dispositivo_a.contacto_telefono = "3624000000"
        self.dispositivo_a.save()
        enviar_a_validacion(self.dispositivo_a, self.operador)
        self.client.force_login(self.operador)

        response = self.client.post(
            reverse("dispositivos:validar", args=[self.dispositivo_a.pk]),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {"ok": False, "message": "No tenés permiso para realizar esta acción."})

        self.client.force_login(self.supervisor)
        validado = self.client.post(reverse("dispositivos:validar", args=[self.dispositivo_a.pk]))
        self.assertEqual(validado.status_code, 302)
        self.dispositivo_a.refresh_from_db()
        self.assertEqual(self.dispositivo_a.estado, Dispositivo.Estado.ACTIVO)
        self.assertTrue(TrazaDispositivo.objects.filter(dispositivo=self.dispositivo_a, accion="VALIDADO").exists())

    def test_observar_por_post_directo_requiere_motivo(self):
        self.dispositivo_a.localidad = "Resistencia"
        self.dispositivo_a.domicilio = "Av. Sarmiento 100"
        self.dispositivo_a.responsable_nombre = "Laura Pérez"
        self.dispositivo_a.contacto_telefono = "3624000000"
        self.dispositivo_a.save()
        enviar_a_validacion(self.dispositivo_a, self.operador)
        self.client.force_login(self.supervisor)

        response = self.client.post(reverse("dispositivos:observar", args=[self.dispositivo_a.pk]), {"motivo": ""})

        self.assertEqual(response.status_code, 302)
        self.dispositivo_a.refresh_from_db()
        self.assertEqual(self.dispositivo_a.estado, Dispositivo.Estado.PENDIENTE_VALIDACION)

    def test_dispositivo_cerrado_no_se_puede_editar_por_post_directo(self):
        self.dispositivo_a.estado = Dispositivo.Estado.CERRADO
        self.dispositivo_a.save(update_fields=["estado", "modificado"])
        self.client.force_login(self.operador)

        response = self.client.post(
            reverse("dispositivos:editar", args=[self.dispositivo_a.pk]),
            {"tipo": self.tipo.pk, "codigo": "HOGAR-A", "nombre": "Hogar A", "camas_totales": "0"},
        )

        self.assertEqual(response.status_code, 403)

    def test_edicion_con_objeto_cargado_no_reabre_un_cierre_intercalado(self):
        view = DispositivoUpdateView()
        view.request = RequestFactory().post(reverse("dispositivos:editar", args=[self.dispositivo_a.pk]))
        view.request.user = self.operador
        view.object = Dispositivo.objects.get(pk=self.dispositivo_a.pk)
        form = DispositivoForm(
            {
                "tipo": self.tipo.pk,
                "codigo": "HOGAR-A",
                "nombre": "Hogar A",
                "localidad": "Resistencia",
                "camas_totales": "0",
            },
            instance=view.object,
        )
        self.assertTrue(form.is_valid(), form.errors)
        Dispositivo.objects.filter(pk=self.dispositivo_a.pk).update(estado=Dispositivo.Estado.CERRADO)

        with self.assertRaises(PermissionDenied):
            view.form_valid(form)

        self.dispositivo_a.refresh_from_db()
        self.assertEqual(self.dispositivo_a.estado, Dispositivo.Estado.CERRADO)
