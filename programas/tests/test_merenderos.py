from datetime import date
from unittest.mock import patch
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from core import rbac
from programas.forms import SolicitudMerenderoForm
from programas.models import EntregaMercaderia, Merendero, PrestacionDiaria, Programa, SolicitudMerendero
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

    def test_aprobar_solicitud_convierte_colision_de_codigo_en_error_de_validacion(self):
        solicitud = self.solicitud()
        crear_merendero = Merendero.objects.create

        def crear_con_colision(**kwargs):
            crear_merendero(**kwargs)
            return crear_merendero(**kwargs)

        with patch(
            "programas.services.merenderos.Merendero.objects.create",
            side_effect=crear_con_colision,
        ):
            with self.assertRaisesMessage(ValidationError, "Ya existe un merendero"):
                aprobar_solicitud(solicitud, self.usuario)

        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, SolicitudMerendero.Estado.EN_REVISION)
        self.assertIsNone(solicitud.merendero)
        self.assertEqual(Merendero.objects.count(), 0)
        Merendero.objects.create(
            codigo="MER-POST-COLISION",
            nombre="Merendero posterior a la colisión",
            domicilio="Calle 12",
            responsable_nombre="Operador",
        )
        self.assertTrue(Merendero.objects.filter(codigo="MER-POST-COLISION").exists())

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
        for campo in SolicitudMerendero.CAMPOS_INSTITUCIONALES_REQUERIDOS:
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
                datos[f"raciones-{dia}-{servicio}"] = ""
        datos["raciones-1-DESAYUNO"] = "20"
        datos["raciones-1-ALMUERZO"] = "30"

        response = self.client.post(reverse("merenderos:prestacion", args=[merendero.pk]), datos)

        self.assertEqual(response.status_code, 302)
        prestacion = merendero.prestaciones_mensuales.get(anio=2025, mes=2)
        self.assertEqual(prestacion.lineas_diarias.count(), 28 * 4)
        self.assertEqual(prestacion.total_del_dia(1), 50)
        self.assertEqual(prestacion.total_del_dia(2), 0)

    def test_prestacion_mensual_acepta_periodo_del_selector_nativo(self):
        merendero = Merendero.objects.create(
            codigo="MER-F02-SELECTOR", nombre="F02 selector", domicilio="Calle 4", responsable_nombre="Responsable"
        )

        respuesta = self.client.get(
            reverse("merenderos:prestacion", args=[merendero.pk]),
            {"periodo": "2026-07"},
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'value="2026-07"')

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


class EntregaCreateAutorizaAntesDeBuscarTests(TestCase):
    """El alta de entrega autoriza antes de buscar el merendero de la URL.

    Mismo molde que RED-73: el `dispatch` hacía `get_object_or_404` antes de
    `super().dispatch()`, así que la ruta le contestaba distinto a un anónimo
    según existiera o no el merendero —404 contra 302 al login— y eso alcanza
    para enumerar qué ids hay. Lo encontró el barrido de
    `core/tests/test_superficie_publica.py`.
    """

    def setUp(self):
        self.merendero = Merendero.objects.create(
            codigo="MER-RED73",
            nombre="Merendero con entregas",
            domicilio="Calle 9",
            responsable_nombre="Responsable",
        )
        self.url_existente = reverse("merenderos:entrega_crear", args=[self.merendero.pk])
        self.url_inexistente = reverse("merenderos:entrega_crear", args=[self.merendero.pk + 1000])

    def test_un_anonimo_va_al_login_exista_o_no_el_merendero(self):
        for descripcion, url in (("existe", self.url_existente), ("no existe", self.url_inexistente)):
            with self.subTest(merendero=descripcion):
                respuesta = self.client.get(url)

                self.assertEqual(respuesta.status_code, 302)
                self.assertEqual(urlparse(respuesta["Location"]).path, reverse(settings.LOGIN_URL))

    def test_sin_capacidad_da_403_exista_o_no_el_merendero(self):
        usuario = get_user_model().objects.create_user(username="miron-merenderos", password="test")
        self.client.force_login(usuario)

        for descripcion, url in (("existe", self.url_existente), ("no existe", self.url_inexistente)):
            with self.subTest(merendero=descripcion):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_con_capacidad_un_merendero_inexistente_sigue_dando_404(self):
        """La precondición no se perdió: solo se corrió de lugar."""
        admin = get_user_model().objects.create_superuser(username="admin-entregas", password="test")
        Programa.objects.create(
            codigo="MERENDEROS",
            nombre="Merenderos",
            tipo=Programa.TipoPrograma.MERENDEROS,
        )
        self.client.force_login(admin)

        self.assertEqual(self.client.get(self.url_inexistente).status_code, 404)
        self.assertEqual(self.client.get(self.url_existente).status_code, 200)


class PrestacionMensualEnCelularTests(TestCase):
    """FE-10: a 390 px la grilla del mes quedaba ilegible.

    El contenedor era `overflow-x-hidden`, así que la tabla se comprimía adentro del
    ancho del teléfono: con `table-fixed` y los anchos del `<colgroup>` en porcentaje,
    los `<th>` caían a 25-50 px y los encabezados se partían letra por letra, sin
    ninguna forma de llegar al resto de las columnas. Ahora el contenedor scrollea en
    los dos ejes y la tabla tiene un ancho mínimo propio.

    `min-w-[720px]` es una utilidad de valor arbitrario: si no está en el CSS
    committeado la tabla se vuelve a comprimir sin que falle nada, así que el test
    también exige que el build la tenga (la novedad la autoriza la ficha FE-10).
    """

    RUTA = "programas/templates/programas/merenderos/prestacion_mensual.html"

    def setUp(self):
        self.template = (settings.BASE_DIR / self.RUTA).read_text(encoding="utf-8")

    def test_el_contenedor_de_la_grilla_scrollea_en_horizontal(self):
        self.assertNotIn("overflow-x-hidden", self.template)
        self.assertIn("overflow-auto", self.template)

    def test_la_tabla_tiene_ancho_minimo(self):
        self.assertRegex(self.template, r"<table[^>]*\bmin-w-\[720px\]")

    def test_el_ancho_minimo_existe_en_el_build(self):
        import importlib.util
        from pathlib import Path

        spec = importlib.util.spec_from_file_location(
            "design_audit", Path(settings.BASE_DIR) / "scripts" / "design_audit.py"
        )
        design_audit = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(design_audit)

        self.assertIn("min-w-[720px]", design_audit._clases_del_build())


class EntregaDeMercaderiaTests(TestCase):
    """La entrega se registra desde la pantalla del merendero (RED-33).

    `EntregaMercaderiaCreateView` estaba cubierta solo por el lado del guard
    (`EntregaCreateAutorizaAntesDeBuscarTests`, RED-73): nadie había registrado
    una entrega **por HTTP**. El riesgo que nombra la ficha es que la entrega
    deje de asociarse al merendero del `pk` de la URL —el `form_class` no tiene
    campo `merendero`, así que el único vínculo es `self.merendero`—, y eso no
    rompe ningún test de servicio porque `registrar_entrega` lo recibe armado.
    """

    def setUp(self):
        cache.clear()
        self.programa = Programa.objects.create(
            codigo="MERENDEROS",
            nombre="Merenderos",
            tipo=Programa.TipoPrograma.MERENDEROS,
        )
        self.merendero = self._merendero("MER-ENT-01", "Merendero Uno")
        self.otro = self._merendero("MER-ENT-02", "Merendero Dos")
        self.admin = get_user_model().objects.create_superuser(username="admin-entrega", password="test")
        self.sin_rol = get_user_model().objects.create_user(username="sin-rol-entrega", password="test")
        self.operador = self._usuario_con("operador-entrega", ["merendero.ver", "merendero.entregar"])
        self.miron = self._usuario_con("miron-entrega", ["merendero.ver"])
        cache.clear()

    def _merendero(self, codigo, nombre):
        return Merendero.objects.create(
            codigo=codigo,
            nombre=nombre,
            domicilio="Calle 7",
            responsable_nombre="Responsable",
            estado=Merendero.Estado.ACTIVO,
        )

    def _usuario_con(self, username, capacidades):
        rol = Group.objects.create(name=f"Rol {username}")
        RolMeta.objects.create(grupo=rol, categoria=rbac.CATEGORIA_PROGRAMA, programa=self.programa, activo=True)
        rol.permissions.add(*[permiso(codigo) for codigo in capacidades])
        usuario = get_user_model().objects.create_user(username=username, password="test")
        usuario.groups.add(rol)
        return usuario

    @staticmethod
    def _datos(**extra):
        datos = {
            "fecha": date(2026, 10, 6).isoformat(),
            "cantidad_kits": 12,
            "servicio": "Merienda",
            "responsable_receptor": "Quien recibe",
            "observaciones": "",
        }
        datos.update(extra)
        return datos

    def test_la_entrega_queda_asociada_al_merendero_de_la_url(self):
        self.client.force_login(self.operador)

        respuesta = self.client.post(reverse("merenderos:entrega_crear", args=[self.merendero.pk]), self._datos())

        self.assertRedirects(respuesta, reverse("merenderos:detalle", args=[self.merendero.pk]))
        entrega = self.merendero.entregas_mercaderia.get()
        self.assertEqual(entrega.cantidad_kits, 12)
        self.assertEqual(entrega.servicio, "Merienda")
        self.assertFalse(self.otro.entregas_mercaderia.exists())

    def test_una_entrega_de_un_merendero_ajeno_no_se_crea(self):
        """El `merendero` del cuerpo no manda: el formulario ni siquiera lo tiene."""
        self.client.force_login(self.operador)

        respuesta = self.client.post(
            reverse("merenderos:entrega_crear", args=[self.merendero.pk]),
            self._datos(merendero=self.otro.pk),
        )

        self.assertRedirects(respuesta, reverse("merenderos:detalle", args=[self.merendero.pk]))
        self.assertEqual(self.merendero.entregas_mercaderia.count(), 1)
        self.assertFalse(self.otro.entregas_mercaderia.exists())

    def test_sin_capacidad_403(self):
        url = reverse("merenderos:entrega_crear", args=[self.merendero.pk])

        for descripcion, usuario in (("sin rol", self.sin_rol), ("solo ver", self.miron)):
            with self.subTest(usuario=descripcion):
                self.client.force_login(usuario)

                self.assertEqual(self.client.get(url).status_code, 403)
                self.assertEqual(self.client.post(url, self._datos()).status_code, 403)

        self.assertFalse(self.merendero.entregas_mercaderia.exists())

    def test_una_entrega_en_un_merendero_suspendido_vuelve_al_formulario(self):
        cambiar_estado_merendero(self.merendero, nuevo_estado=Merendero.Estado.SUSPENDIDO, usuario=self.admin)
        self.client.force_login(self.operador)

        respuesta = self.client.post(reverse("merenderos:entrega_crear", args=[self.merendero.pk]), self._datos())

        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(self.merendero.entregas_mercaderia.exists())
        self.assertIn("activos", " ".join(respuesta.context["form"].errors["__all__"]))

    def test_cero_kits_no_crea_la_entrega(self):
        self.client.force_login(self.operador)

        respuesta = self.client.post(
            reverse("merenderos:entrega_crear", args=[self.merendero.pk]), self._datos(cantidad_kits=0)
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(self.merendero.entregas_mercaderia.exists())


class MerenderoDetalleYEstadoPorHttpTests(TestCase):
    """El detalle y el cambio de estado, por la URL (RED-33).

    `MerenderoDetailView` decide con `puede_entregar`/`puede_editar` qué botones
    dibuja, y `MerenderoEstadoView` es el único camino para suspender o cerrar:
    las dos estaban sin un test que entrara por HTTP (`merenderos.py` al 76 %).
    """

    def setUp(self):
        cache.clear()
        self.programa = Programa.objects.create(
            codigo="MERENDEROS",
            nombre="Merenderos",
            tipo=Programa.TipoPrograma.MERENDEROS,
        )
        self.merendero = Merendero.objects.create(
            codigo="MER-EST-01",
            nombre="Merendero Estado",
            domicilio="Calle 8",
            responsable_nombre="Responsable",
            estado=Merendero.Estado.ACTIVO,
        )
        self.editor = self._usuario_con("editor-merendero", ["merendero.ver", "merendero.editar"])
        self.miron = self._usuario_con("miron-estado", ["merendero.ver"])
        cache.clear()

    def _usuario_con(self, username, capacidades):
        rol = Group.objects.create(name=f"Rol {username}")
        RolMeta.objects.create(grupo=rol, categoria=rbac.CATEGORIA_PROGRAMA, programa=self.programa, activo=True)
        rol.permissions.add(*[permiso(codigo) for codigo in capacidades])
        usuario = get_user_model().objects.create_user(username=username, password="test")
        usuario.groups.add(rol)
        return usuario

    def test_el_detalle_dice_que_puede_hacer_quien_mira(self):
        self.client.force_login(self.miron)

        respuesta = self.client.get(reverse("merenderos:detalle", args=[self.merendero.pk]))

        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(respuesta.context["puede_entregar"])
        self.assertFalse(respuesta.context["puede_editar"])
        self.assertEqual(list(respuesta.context["entregas"]), [])

    def test_el_detalle_no_lista_las_entregas_anuladas(self):
        vigente = EntregaMercaderia.objects.create(
            merendero=self.merendero,
            fecha=date(2026, 10, 6),
            cantidad_kits=3,
            servicio="Merienda",
            responsable_receptor="Quien recibe",
        )
        EntregaMercaderia.objects.create(
            merendero=self.merendero,
            fecha=date(2026, 10, 6),
            cantidad_kits=4,
            servicio="Merienda",
            responsable_receptor="Quien recibe",
            anulada=True,
        )
        self.client.force_login(self.miron)

        respuesta = self.client.get(reverse("merenderos:detalle", args=[self.merendero.pk]))

        self.assertEqual(list(respuesta.context["entregas"]), [vigente])

    def test_suspender_guarda_quien_y_solo_por_post(self):
        self.client.force_login(self.editor)
        url = reverse("merenderos:estado", args=[self.merendero.pk, "suspender"])

        self.assertEqual(self.client.get(url).status_code, 405)
        self.merendero.refresh_from_db()
        self.assertEqual(self.merendero.estado, Merendero.Estado.ACTIVO)

        respuesta = self.client.post(url)

        self.assertRedirects(respuesta, reverse("merenderos:detalle", args=[self.merendero.pk]))
        self.merendero.refresh_from_db()
        self.assertEqual(self.merendero.estado, Merendero.Estado.SUSPENDIDO)
        self.assertEqual(self.merendero.estado_actualizado_por, self.editor)

    def test_una_accion_de_estado_inventada_da_400(self):
        self.client.force_login(self.editor)

        respuesta = self.client.post(reverse("merenderos:estado", args=[self.merendero.pk, "reactivar"]))

        self.assertEqual(respuesta.status_code, 400)
        self.merendero.refresh_from_db()
        self.assertEqual(self.merendero.estado, Merendero.Estado.ACTIVO)

    def test_una_transicion_prohibida_no_cambia_el_estado(self):
        cambiar_estado_merendero(self.merendero, nuevo_estado=Merendero.Estado.CERRADO, usuario=self.editor)
        self.client.force_login(self.editor)

        respuesta = self.client.post(reverse("merenderos:estado", args=[self.merendero.pk, "suspender"]))

        self.assertRedirects(respuesta, reverse("merenderos:detalle", args=[self.merendero.pk]))
        self.merendero.refresh_from_db()
        self.assertEqual(self.merendero.estado, Merendero.Estado.CERRADO)

    def test_sin_merendero_editar_no_se_cambia_el_estado(self):
        self.client.force_login(self.miron)

        respuesta = self.client.post(reverse("merenderos:estado", args=[self.merendero.pk, "suspender"]))

        self.assertEqual(respuesta.status_code, 403)
        self.merendero.refresh_from_db()
        self.assertEqual(self.merendero.estado, Merendero.Estado.ACTIVO)

    def test_un_anonimo_va_al_login(self):
        for nombre, url in (
            ("detalle", reverse("merenderos:detalle", args=[self.merendero.pk])),
            ("estado", reverse("merenderos:estado", args=[self.merendero.pk, "suspender"])),
        ):
            with self.subTest(pantalla=nombre):
                respuesta = self.client.get(url)

                self.assertEqual(respuesta.status_code, 302)
                self.assertEqual(urlparse(respuesta["Location"]).path, reverse(settings.LOGIN_URL))
