from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from core import rbac
from programas.forms import SolicitudMerenderoForm
from programas.models import Merendero, PrestacionDiaria, Programa, SolicitudMerendero
from programas.services.merenderos import (
    aprobar_solicitud,
    cambiar_estado_merendero,
    guardar_prestacion,
    registrar_entrega,
)
from users.models import Capacidad, RolMeta


def permiso(codigo):
    content_type = ContentType.objects.get_for_model(Capacidad)
    return Permission.objects.get(codename=rbac.codename_de(codigo), content_type=content_type)


class MerenderosServiceTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(username="operador-merenderos")

    def solicitud(self, *, documentacion="respaldo.pdf"):
        return SolicitudMerendero.objects.create(
            codigo="MER-ACEPT-01",
            nombre="Merendero Horizonte",
            domicilio="Calle 10 123",
            zona="Norte",
            barrio="San Martín",
            dias_horarios="Lunes a viernes, 16 a 19",
            responsable_nombre="María Pérez",
            documentacion=documentacion,
            estado=SolicitudMerendero.Estado.EN_REVISION,
        )

    def test_aprobar_solicitud_documentada_crea_un_unico_merendero_activo(self):
        solicitud = self.solicitud()

        merendero = aprobar_solicitud(solicitud, self.usuario)

        solicitud.refresh_from_db()
        self.assertEqual(merendero.estado, Merendero.Estado.ACTIVO)
        self.assertEqual(merendero.codigo, "MER-ACEPT-01")
        self.assertEqual(solicitud.estado, SolicitudMerendero.Estado.APROBADA)
        self.assertEqual(solicitud.merendero, merendero)
        self.assertEqual(solicitud.validada_por, self.usuario)
        self.assertIsNotNone(solicitud.validada_en)
        self.assertEqual(Merendero.objects.count(), 1)

    def test_no_aprueba_solicitud_sin_documentacion(self):
        solicitud = self.solicitud(documentacion="")

        with self.assertRaisesMessage(ValidationError, "documentación respaldatoria"):
            aprobar_solicitud(solicitud, self.usuario)

        self.assertEqual(Merendero.objects.count(), 0)
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, SolicitudMerendero.Estado.EN_REVISION)

    def test_f02_febrero_bisiesto_genera_dias_reales_y_firma(self):
        merendero = Merendero.objects.create(
            codigo="MER-ACEPT-02",
            nombre="Rayito de Sol",
            domicilio="Av. Siempre Viva 742",
            responsable_nombre="Juan Gómez",
        )

        prestacion = guardar_prestacion(
            merendero,
            anio=2024,
            mes=2,
            raciones={29: {"DESAYUNO": 20, "ALMUERZO": 30}},
            observaciones={29: "Jornada especial"},
            usuario=self.usuario,
        )

        self.assertEqual(prestacion.lineas_diarias.count(), 29 * 4)
        self.assertEqual(prestacion.total_del_dia(29), 50)
        self.assertEqual(prestacion.lineas_diarias.filter(dia=29, firmado_por=self.usuario).count(), 4)
        self.assertEqual(prestacion.observacion_del_dia(29), "Jornada especial")

    def test_f02_reabre_el_mismo_mes_sin_duplicar_lineas(self):
        merendero = Merendero.objects.create(
            codigo="MER-ACEPT-03",
            nombre="Manos Unidas",
            domicilio="Mitre 321",
            responsable_nombre="Ana Díaz",
        )

        primera = guardar_prestacion(merendero, anio=2026, mes=4, raciones={1: {"CENA": 4}}, usuario=self.usuario)
        segunda = guardar_prestacion(merendero, anio=2026, mes=4, raciones={1: {"CENA": 7}}, usuario=self.usuario)

        self.assertEqual(primera.pk, segunda.pk)
        self.assertEqual(segunda.lineas_diarias.count(), 30 * 4)
        self.assertEqual(segunda.total_del_dia(1), 7)

    def test_prestacion_rechaza_anio_fuera_del_rango_operativo(self):
        merendero = Merendero.objects.create(
            codigo="MER-ACEPT-04",
            nombre="Esperanza",
            domicilio="Belgrano 10",
            responsable_nombre="Ana Díaz",
        )

        with self.assertRaisesMessage(ValidationError, "Año inválido"):
            guardar_prestacion(merendero, anio=1999, mes=1, raciones={}, usuario=self.usuario)

    def test_entrega_exige_kits_positivos_y_servicio(self):
        merendero = Merendero.objects.create(
            codigo="MER-ACEPT-05",
            nombre="Nueva Vida",
            domicilio="Rivadavia 20",
            responsable_nombre="Ana Díaz",
        )

        with self.assertRaisesMessage(ValidationError, "kits"):
            registrar_entrega(
                merendero,
                fecha=date(2026, 7, 27),
                cantidad_kits=0,
                servicio="Merienda",
                responsable_receptor="",
                observaciones="",
            )

    def test_servicios_rechazan_un_merendero_inactivo(self):
        merendero = Merendero.objects.create(
            codigo="MER-ACEPT-07",
            nombre="Puertas Abiertas",
            domicilio="Sarmiento 40",
            responsable_nombre="Ana Díaz",
            estado=Merendero.Estado.SUSPENDIDO,
        )

        with self.assertRaisesMessage(ValidationError, "entregas"):
            registrar_entrega(
                merendero,
                fecha=date(2026, 7, 27),
                cantidad_kits=1,
                servicio="Merienda",
                responsable_receptor="",
                observaciones="",
            )
        with self.assertRaisesMessage(ValidationError, "prestación"):
            guardar_prestacion(merendero, anio=2026, mes=7, raciones={}, usuario=self.usuario)
        with self.assertRaisesMessage(ValidationError, "servicio"):
            registrar_entrega(
                merendero,
                fecha=date(2026, 7, 27),
                cantidad_kits=1,
                servicio=" ",
                responsable_receptor="",
                observaciones="",
            )

    def test_suspension_guarda_quien_y_cuando_actualizo_el_estado(self):
        merendero = Merendero.objects.create(
            codigo="MER-ACEPT-06",
            nombre="Sol Naciente",
            domicilio="Moreno 30",
            responsable_nombre="Ana Díaz",
        )

        cambiar_estado_merendero(merendero, nuevo_estado=Merendero.Estado.SUSPENDIDO, usuario=self.usuario)

        merendero.refresh_from_db()
        self.assertEqual(merendero.estado, Merendero.Estado.SUSPENDIDO)
        self.assertEqual(merendero.estado_actualizado_por, self.usuario)
        self.assertIsNotNone(merendero.estado_actualizado_en)


class SolicitudMerenderoFormTests(TestCase):
    def test_campos_institucionales_requeridos_no_pueden_enviarse_vacios(self):
        form = SolicitudMerenderoForm(
            data={
                "codigo": "",
                "nombre": "",
                "domicilio": "",
                "zona": "",
                "barrio": "",
                "dias_horarios": "",
                "responsable_nombre": "",
            }
        )

        self.assertFalse(form.is_valid())
        for campo in ("codigo", "nombre", "domicilio", "zona", "barrio", "dias_horarios", "responsable_nombre"):
            self.assertIn(campo, form.errors)


class MerenderosViewsTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_superuser(username="admin-merenderos", password="test")
        Programa.objects.create(
            codigo="MERENDEROS",
            nombre="Merenderos",
            tipo=Programa.TipoPrograma.MERENDEROS,
        )
        self.client.force_login(self.usuario)

    def test_rbac_exige_y_respeta_capacidad_acotada_a_merenderos(self):
        usuario = get_user_model().objects.create_user(username="consulta-merenderos", password="test")
        self.client.force_login(usuario)
        self.assertEqual(self.client.get(reverse("merenderos:lista")).status_code, 403)

        rol = Group.objects.create(name="Consulta Merenderos")
        RolMeta.objects.create(
            grupo=rol,
            categoria=rbac.CATEGORIA_PROGRAMA,
            programa=Programa.objects.get(codigo="MERENDEROS"),
            activo=True,
        )
        rol.permissions.add(permiso("merendero.ver"))
        usuario.groups.add(rol)
        cache.clear()

        self.assertEqual(self.client.get(reverse("merenderos:lista")).status_code, 200)

    def solicitud_sin_documentacion(self):
        return SolicitudMerendero.objects.create(
            codigo="MER-SIN-DOC",
            nombre="Sin respaldo",
            domicilio="Calle 1",
            zona="Centro",
            barrio="Centro",
            dias_horarios="Lunes",
            responsable_nombre="Responsable",
            estado=SolicitudMerendero.Estado.EN_REVISION,
        )

    def test_post_directo_no_aprueba_solicitud_sin_documentacion(self):
        solicitud = self.solicitud_sin_documentacion()

        response = self.client.post(reverse("merenderos:solicitud_resolver", args=[solicitud.pk, "aprobar"]))

        self.assertEqual(response.status_code, 302)
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, SolicitudMerendero.Estado.EN_REVISION)
        self.assertFalse(Merendero.objects.filter(codigo="MER-SIN-DOC").exists())

    def test_borrador_puede_guardarse_incompleto_y_una_observada_se_corrige_y_reenvia(self):
        response = self.client.post(reverse("merenderos:solicitud_crear"), {"accion": "borrador"})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(SolicitudMerendero.objects.get().estado, SolicitudMerendero.Estado.BORRADOR)

        solicitud = SolicitudMerendero.objects.create(
            codigo="MER-OBS-01",
            nombre="Amanecer",
            domicilio="Calle 5",
            zona="Sur",
            barrio="Barrio Sur",
            dias_horarios="Martes",
            responsable_nombre="Responsable",
            documentacion="respaldo.pdf",
            estado=SolicitudMerendero.Estado.OBSERVADA,
            observaciones="Corregir domicilio",
        )
        response = self.client.post(
            reverse("merenderos:solicitud_editar", args=[solicitud.pk]),
            {
                "codigo": "MER-OBS-01",
                "nombre": "Amanecer",
                "domicilio": "Calle 5 bis",
                "zona": "Sur",
                "barrio": "Barrio Sur",
                "dias_horarios": "Martes",
                "responsable_nombre": "Responsable",
            },
        )

        self.assertEqual(response.status_code, 302)
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, SolicitudMerendero.Estado.EN_REVISION)
        self.assertEqual(solicitud.observaciones, "Corregir domicilio")
        self.assertEqual(solicitud.domicilio, "Calle 5 bis")

    def test_post_prestacion_calcula_lineas_del_mes_y_no_acepta_total_manipulado(self):
        merendero = Merendero.objects.create(
            codigo="MER-F02-01", nombre="F02", domicilio="Calle 2", responsable_nombre="Responsable"
        )

        datos = {"anio": "2025", "mes": "2", "total-1": "9999"}
        for dia in range(1, 29):
            for servicio, _etiqueta in PrestacionDiaria.Servicio.choices:
                datos[f"raciones-{dia}-{servicio}"] = "0"
        datos["raciones-1-DESAYUNO"] = "20"
        datos["raciones-1-ALMUERZO"] = "30"

        response = self.client.post(reverse("merenderos:prestacion", args=[merendero.pk]), datos)

        self.assertEqual(response.status_code, 302)
        prestacion = merendero.prestaciones_mensuales.get(anio=2025, mes=2)
        self.assertEqual(prestacion.lineas_diarias.count(), 28 * 4)
        self.assertEqual(prestacion.total_del_dia(1), 50)

    def test_prestacion_bloquea_merendero_inactivo_y_post_parcial(self):
        merendero = Merendero.objects.create(
            codigo="MER-F02-02", nombre="F02 cerrado", domicilio="Calle 3", responsable_nombre="Responsable"
        )
        guardar_prestacion(merendero, anio=2025, mes=1, raciones={1: {"CENA": 8}}, usuario=self.usuario)

        respuesta_parcial = self.client.post(
            reverse("merenderos:prestacion", args=[merendero.pk]),
            {"anio": "2025", "mes": "1", "raciones-1-CENA": "0"},
        )
        self.assertEqual(respuesta_parcial.status_code, 302)
        self.assertEqual(merendero.prestaciones_mensuales.get(anio=2025, mes=1).total_del_dia(1), 8)

        merendero.estado = Merendero.Estado.SUSPENDIDO
        merendero.save(update_fields=["estado", "modificado"])
        respuesta_get = self.client.get(reverse("merenderos:prestacion", args=[merendero.pk]))
        respuesta_post = self.client.post(
            reverse("merenderos:prestacion", args=[merendero.pk]), {"anio": "2025", "mes": "1"}
        )

        self.assertEqual(respuesta_get.status_code, 403)
        self.assertEqual(respuesta_post.status_code, 403)
