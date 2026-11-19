"""Baja lógica en cascada de Programas, Segmentos, Convocatorias y Relevamientos de Becas."""

from datetime import date, timedelta
from io import StringIO

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from core import rbac
from programas.forms import SegmentoForm
from programas.management.commands.seed_becas import ROL_ADMIN, ROL_COORDINADOR_REGIONAL
from programas.models import (
    AsignacionTerritorial,
    Convocatoria,
    Formulario,
    ProgramaSiis,
    Relevamiento,
    Segmento,
    Subsegmento,
)
from programas.services.autorizacion import segmento_dueno_id
from programas.services.campo import GRACIA_SINCRONIZACION
from programas.services.eliminacion import (
    CAP_CONVOCATORIA_ELIMINAR,
    CAP_PROGRAMA_ELIMINAR,
    CAP_RELEVAMIENTO_ELIMINAR,
    CAP_SEGMENTO_ELIMINAR,
    EliminacionBloqueada,
    eliminar,
    resumen_cascada,
)
from users.models import Capacidad, RolMeta

CAPS_ELIMINAR = (CAP_PROGRAMA_ELIMINAR, CAP_SEGMENTO_ELIMINAR, CAP_CONVOCATORIA_ELIMINAR, CAP_RELEVAMIENTO_ELIMINAR)


class _Base(TestCase):
    def setUp(self):
        cache.clear()
        call_command("seed_becas", stdout=StringIO())
        self.admin = User.objects.create_user("admin_becas", password="x")
        self.admin.groups.add(Group.objects.get(name=ROL_ADMIN))
        self.eliminador = User.objects.create_user("eliminador", password="x")
        self.eliminador.groups.add(Group.objects.get(name=ROL_ADMIN))
        rol = Group.objects.create(name="Eliminador de Becas")
        RolMeta.objects.create(grupo=rol)  # solo cuentan los roles activos
        ct = ContentType.objects.get_for_model(Capacidad)
        rol.permissions.add(
            *(
                Permission.objects.get_or_create(content_type=ct, codename=rbac.codename_de(c), defaults={"name": c})[0]
                for c in CAPS_ELIMINAR
            )
        )
        self.rol_eliminador = rol
        self.eliminador.groups.add(rol)

        self.programa = ProgramaSiis.objects.create(nombre="Programa Uno")
        self.segmento = Segmento.objects.create(programa=self.programa, nombre="Seg A", cupo_maximo=10)
        self.subsegmento = Subsegmento.objects.create(segmento=self.segmento, nombre="Sub A", cupo_maximo=5)
        self.convocatoria = Convocatoria.objects.create(
            nombre="Conv A", segmento=self.segmento, fecha_inicio=date(2026, 1, 1), fecha_fin=date(2026, 12, 31)
        )
        self.relevamiento = Relevamiento.objects.create(
            convocatoria=self.convocatoria, territorial=self.admin, fecha_asignada=date(2026, 6, 1), zona="A"
        )


class CascadaServicioTests(_Base):
    def test_programa_elimina_toda_la_cascada(self):
        marcados = eliminar(self.programa, self.eliminador)

        self.assertEqual(
            marcados,
            {"relevamientos": 1, "convocatorias": 1, "subsegmentos": 1, "segmentos": 1, "programas": 1},
        )
        for modelo in (ProgramaSiis, Segmento, Subsegmento, Convocatoria, Relevamiento):
            self.assertFalse(modelo.objects.exists(), modelo.__name__)
            fila = modelo.todos.get()
            self.assertIsNotNone(fila.eliminado_en)
            self.assertEqual(fila.eliminado_por, self.eliminador)

    def test_segmento_no_toca_al_programa(self):
        eliminar(self.segmento, self.eliminador)
        self.assertTrue(ProgramaSiis.objects.filter(pk=self.programa.pk).exists())
        self.assertFalse(Segmento.objects.exists())
        self.assertFalse(Subsegmento.objects.exists())
        self.assertFalse(Convocatoria.objects.exists())
        self.assertFalse(Relevamiento.objects.exists())

    def test_convocatoria_baja_a_relevamientos_y_no_sube(self):
        eliminar(self.convocatoria, self.eliminador)
        self.assertTrue(Segmento.objects.filter(pk=self.segmento.pk).exists())
        self.assertFalse(Convocatoria.objects.exists())
        self.assertFalse(Relevamiento.objects.exists())

    def test_relevamiento_solo(self):
        eliminar(self.relevamiento, self.eliminador)
        self.assertTrue(Convocatoria.objects.filter(pk=self.convocatoria.pk).exists())
        self.assertFalse(self.convocatoria.relevamientos.exists())

    def test_casos_cargados_bloquean_y_no_marcan_nada(self):
        Formulario.objects.create(relevamiento=self.relevamiento, celular="3624000000")
        for objeto in (self.programa, self.segmento, self.convocatoria, self.relevamiento):
            with self.subTest(objeto=type(objeto).__name__), self.assertRaises(EliminacionBloqueada) as ctx:
                eliminar(objeto, self.eliminador)
            self.assertEqual(ctx.exception.casos, 1)
        self.assertFalse(Relevamiento.todos.filter(eliminado_en__isnull=False).exists())
        self.assertFalse(ProgramaSiis.todos.filter(eliminado_en__isnull=False).exists())

    def test_numero_de_relevamiento_no_se_reusa(self):
        eliminar(self.relevamiento, self.eliminador)
        nuevo = Relevamiento.objects.create(
            convocatoria=self.convocatoria, territorial=self.admin, fecha_asignada=date(2026, 7, 1), zona="B"
        )
        self.assertEqual(nuevo.numero, self.relevamiento.numero + 1)

    def test_nombre_de_segmento_eliminado_no_revienta_el_alta(self):
        eliminar(self.segmento, self.eliminador)
        repetido = Segmento(programa=self.programa, nombre="Seg A", cupo_maximo=3)
        with self.assertRaisesMessage(Exception, "segmento eliminado"):
            repetido.full_clean()

    def test_conteo_de_segmentos_del_programa_excluye_eliminados(self):
        Segmento.objects.create(programa=self.programa, nombre="Seg B", cupo_maximo=10)
        eliminar(self.segmento, self.eliminador)
        self.client.force_login(self.admin)
        resp = self.client.get(reverse("becas:programas"))
        self.assertEqual(resp.context["programas"].get(pk=self.programa.pk).n_segmentos, 1)


class VistasTests(_Base):
    URLS = (
        ("becas:programa_eliminar", "programa", "becas:programas"),
        ("becas:segmento_eliminar", "segmento", "becas:segmentos"),
        ("becas:convocatoria_eliminar", "convocatoria", "becas:convocatorias"),
        ("becas:relevamiento_eliminar", "relevamiento", "becas:relevamientos"),
    )

    def test_sin_login_redirige_al_login(self):
        for nombre, attr, _destino in self.URLS:
            with self.subTest(nombre):
                resp = self.client.post(reverse(nombre, args=[getattr(self, attr).pk]))
                self.assertEqual(resp.status_code, 302)
                self.assertIn("?next=", resp.url)

    def test_sin_capacidad_403_y_no_elimina(self):
        self.client.force_login(self.admin)
        for nombre, attr, _destino in self.URLS:
            with self.subTest(nombre):
                resp = self.client.post(reverse(nombre, args=[getattr(self, attr).pk]))
                self.assertEqual(resp.status_code, 403)
        self.assertTrue(Relevamiento.objects.filter(pk=self.relevamiento.pk).exists())

    def test_get_no_permitido(self):
        self.client.force_login(self.eliminador)
        resp = self.client.get(reverse("becas:relevamiento_eliminar", args=[self.relevamiento.pk]))
        self.assertEqual(resp.status_code, 405)

    def test_con_capacidad_elimina_y_vuelve_al_listado(self):
        self.client.force_login(self.eliminador)
        for nombre, attr, destino in reversed(self.URLS):
            with self.subTest(nombre):
                objeto = getattr(self, attr)
                resp = self.client.post(reverse(nombre, args=[objeto.pk]))
                self.assertRedirects(resp, reverse(destino), fetch_redirect_response=False)
                self.assertFalse(type(objeto).objects.filter(pk=objeto.pk).exists())

    def test_eliminado_da_404(self):
        eliminar(self.convocatoria, self.eliminador)
        self.client.force_login(self.eliminador)
        self.assertEqual(
            self.client.get(reverse("becas:convocatoria_detalle", args=[self.convocatoria.pk])).status_code, 404
        )
        self.assertEqual(
            self.client.get(reverse("becas:relevamiento_detalle", args=[self.relevamiento.pk])).status_code, 404
        )

    def test_con_casos_avisa_y_no_elimina(self):
        Formulario.objects.create(relevamiento=self.relevamiento, celular="3624000000")
        self.client.force_login(self.eliminador)
        resp = self.client.post(reverse("becas:segmento_eliminar", args=[self.segmento.pk]), follow=True)
        self.assertContains(resp, "No se puede eliminar el segmento: tiene 1 caso cargado")
        self.assertNotContains(resp, "Un relevamiento está en campo")
        self.assertTrue(Segmento.objects.filter(pk=self.segmento.pk).exists())


class BotonTests(_Base):
    PANTALLAS = (
        ("becas:programas", "becas:programa_eliminar", "programa"),
        ("becas:segmentos", "becas:segmento_eliminar", "segmento"),
        ("becas:convocatorias", "becas:convocatoria_eliminar", "convocatoria"),
        ("becas:relevamientos", "becas:relevamiento_eliminar", "relevamiento"),
    )

    def test_boton_solo_con_capacidad(self):
        for usuario, se_ve in ((self.admin, False), (self.eliminador, True)):
            self.client.force_login(usuario)
            for listado, accion, attr in self.PANTALLAS:
                with self.subTest(usuario=usuario.username, listado=listado):
                    resp = self.client.get(reverse(listado))
                    self.assertEqual(resp.status_code, 200)
                    url = reverse(accion, args=[getattr(self, attr).pk])
                    self.assertEqual(url in resp.content.decode(), se_ve)

    def test_lo_eliminado_no_se_lista(self):
        eliminar(self.programa, self.eliminador)
        self.client.force_login(self.eliminador)
        for listado, _accion, attr in self.PANTALLAS:
            with self.subTest(listado=listado):
                resp = self.client.get(reverse(listado))
                detalle = reverse(f"becas:{attr}_detalle", args=[getattr(self, attr).pk])
                self.assertNotContains(resp, detalle)


class RevisionAuditoriaTests(_Base):
    """Hallazgos de la auditoría del PR #1194."""

    def test_regional_no_elimina_el_programa_si_no_puede_eliminar_sus_segmentos(self):
        regional = User.objects.create_user("regional", password="x")
        regional.groups.add(Group.objects.get(name=ROL_COORDINADOR_REGIONAL), self.rol_eliminador)
        self.subsegmento.referente = regional
        self.subsegmento.save()
        self.client.force_login(regional)

        resp = self.client.post(reverse("becas:programa_eliminar", args=[self.programa.pk]))

        self.assertEqual(resp.status_code, 403)
        self.assertTrue(Segmento.objects.filter(pk=self.segmento.pk).exists())

    def test_renombrar_con_el_nombre_de_un_eliminado_es_error_de_formulario(self):
        otro = Segmento.objects.create(programa=self.programa, nombre="Seg B", cupo_maximo=10)
        eliminar(self.segmento, self.eliminador)
        form = SegmentoForm(
            data={"nombre": "Seg A", "descripcion": "", "cupo_maximo": 10, "requiere_gps": False, "activo": True},
            instance=otro,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("nombre", form.errors)

    def test_el_dueno_del_territorial_es_la_asignacion_viva_mas_antigua(self):
        territorial = User.objects.create_user("terri", password="x")
        vivo = Segmento.objects.create(programa=self.programa, nombre="Seg vivo", cupo_maximo=10)
        AsignacionTerritorial.objects.create(segmento=self.segmento, territorial=territorial)
        AsignacionTerritorial.objects.create(segmento=vivo, territorial=territorial)
        self.assertEqual(segmento_dueno_id(territorial), self.segmento.pk)

        eliminar(self.segmento, self.eliminador)

        self.assertEqual(segmento_dueno_id(territorial), vivo.pk)

    def test_subsegmento_protegido_por_convocatoria_eliminada_lo_dice(self):
        conv = Convocatoria.objects.create(
            nombre="Conv sub",
            segmento=self.segmento,
            subsegmento=self.subsegmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        eliminar(conv, self.eliminador)
        self.client.force_login(self.admin)
        resp = self.client.post(reverse("becas:subsegmento_eliminar", args=[self.subsegmento.pk]), follow=True)
        self.assertContains(resp, "lo usa una convocatoria eliminada")


class RelevamientoEnCampoTests(_Base):
    """La app puede tener capturas offline sin sincronizar (decisión del usuario, 18/11/2026)."""

    def test_en_curso_o_finalizando_bloquean_toda_la_cascada(self):
        for estado in (Relevamiento.Estado.EN_CURSO, Relevamiento.Estado.FINALIZANDO):
            Relevamiento.objects.filter(pk=self.relevamiento.pk).update(estado=estado)
            for objeto in (self.programa, self.segmento, self.convocatoria, self.relevamiento):
                with (
                    self.subTest(estado=estado, objeto=type(objeto).__name__),
                    self.assertRaises(EliminacionBloqueada) as ctx,
                ):
                    eliminar(objeto, self.eliminador)
                self.assertEqual((ctx.exception.casos, ctx.exception.en_campo), (0, 1))
        self.assertFalse(Relevamiento.todos.filter(eliminado_en__isnull=False).exists())

    def test_fuera_de_campo_se_elimina(self):
        for estado in (Relevamiento.Estado.FINALIZADO, Relevamiento.Estado.EN_REVISION, Relevamiento.Estado.TERMINADO):
            with self.subTest(estado=estado):
                rel = Relevamiento.objects.create(
                    convocatoria=self.convocatoria, territorial=self.admin, fecha_asignada=date(2026, 6, 1), zona="Z"
                )
                Relevamiento.objects.filter(pk=rel.pk).update(estado=estado)
                eliminar(rel, self.eliminador)
                self.assertFalse(Relevamiento.objects.filter(pk=rel.pk).exists())

    def test_la_vista_avisa_el_motivo(self):
        Relevamiento.objects.filter(pk=self.relevamiento.pk).update(estado=Relevamiento.Estado.EN_CURSO)
        self.client.force_login(self.eliminador)
        resp = self.client.post(reverse("becas:convocatoria_eliminar", args=[self.convocatoria.pk]), follow=True)
        self.assertContains(resp, "tiene 1 relevamiento en campo")
        self.assertTrue(Convocatoria.objects.filter(pk=self.convocatoria.pk).exists())

    def test_la_vista_del_relevamiento_dice_que_el_esta_en_campo(self):
        Relevamiento.objects.filter(pk=self.relevamiento.pk).update(estado=Relevamiento.Estado.EN_CURSO)
        self.client.force_login(self.eliminador)
        resp = self.client.post(reverse("becas:relevamiento_eliminar", args=[self.relevamiento.pk]), follow=True)
        self.assertContains(resp, "No se puede eliminar el relevamiento: está en campo.")
        self.assertContains(resp, "hasta 24 h después de la fecha de fin de su período")


class GraciaDeSincronizacionTests(_Base):
    """Un relevamiento cerrado todavía acepta capturas atrasadas durante la gracia (``campo.en_gracia``)."""

    def _cerrado(self, estado, cerro_hace):
        Relevamiento.objects.filter(pk=self.relevamiento.pk).update(
            estado=estado, fecha_hasta=timezone.now() - cerro_hace
        )

    def test_cerrado_dentro_de_la_gracia_bloquea(self):
        for estado in (Relevamiento.Estado.FINALIZADO, Relevamiento.Estado.EN_REVISION):
            with self.subTest(estado=estado):
                self._cerrado(estado, timedelta(hours=2))
                for objeto in (self.programa, self.convocatoria, self.relevamiento):
                    with self.assertRaises(EliminacionBloqueada) as ctx:
                        eliminar(objeto, self.eliminador)
                    self.assertEqual(ctx.exception.en_campo, 1)
        self.assertFalse(Relevamiento.todos.filter(eliminado_en__isnull=False).exists())

    def test_vencida_la_gracia_se_elimina(self):
        self._cerrado(Relevamiento.Estado.EN_REVISION, GRACIA_SINCRONIZACION + timedelta(minutes=1))
        eliminar(self.convocatoria, self.eliminador)
        self.assertFalse(Relevamiento.objects.filter(pk=self.relevamiento.pk).exists())

    def test_terminado_no_tiene_gracia(self):
        self._cerrado(Relevamiento.Estado.TERMINADO, timedelta(hours=2))
        eliminar(self.relevamiento, self.eliminador)
        self.assertFalse(Relevamiento.objects.filter(pk=self.relevamiento.pk).exists())


class ResumenCascadaTests(SimpleTestCase):
    """El aviso de éxito no anuncia al propio elemento como si fuera un hijo (QA en testing, 19-nov)."""

    def test_segmento_no_se_cuenta_a_si_mismo(self):
        marcados = {"segmentos": 1, "convocatorias": 1}
        self.assertEqual(resumen_cascada(marcados, "segmentos"), " También se eliminaron: 1 convocatoria.")

    def test_relevamiento_solo_no_anuncia_nada(self):
        self.assertEqual(resumen_cascada({"relevamientos": 1}, "relevamientos"), "")

    def test_programa_cuenta_todos_sus_hijos(self):
        self.assertEqual(resumen_cascada({"segmentos": 2}), " También se eliminaron: 2 segmentos.")

    def test_no_modifica_el_diccionario_recibido(self):
        marcados = {"convocatorias": 1}
        resumen_cascada(marcados, "convocatorias")
        self.assertEqual(marcados, {"convocatorias": 1})
