"""Cambio 335 — «El CSV de convocatoria también lo baja el Coordinador» (PM, 17/10/2026).

Los tres CSV de convocatoria (beneficiarios aprobados, relevamientos y lista de espera)
y el flag ``puede_reportes`` que dibuja sus botones pasan por una sola regla,
``puede_exportar_convocatoria``:

- administrar el programa Becas, **o**
- ``becas.beneficiario.ver`` **y** ``becas.reportes.exportar``,

todo con el alcance del Programa Becas. El alcance por fila no cambia: la convocatoria
sale de ``convocatorias_visibles`` y los casos del link público siguen filtrados por
RN-P13. Se prueba con los roles **sembrados**, que es lo que el PM decidió.
"""

import csv
from datetime import date
from io import StringIO

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from core import rbac
from legajos.models import Ciudadano
from programas.management.commands.seed_becas import (
    ROL_ADMIN,
    ROL_COORDINADOR,
    ROL_COORDINADOR_REGIONAL,
    ROL_REFERENTE,
)
from programas.models import (
    AsignacionCoordinador,
    AsignacionReferente,
    Convocatoria,
    Formulario,
    ListaEspera,
    Programa,
    ProgramaSiis,
    Relevamiento,
    Segmento,
    Subsegmento,
)
from programas.services.autorizacion import programa_becas, puede_exportar_convocatoria
from users.models import Capacidad, RolMeta

EXPORTS = (
    "becas:convocatoria_export_beneficiarios",
    "becas:convocatoria_export_relevamientos",
    "becas:convocatoria_export_lista_espera",
)


def _usuario(username, rol):
    user = User.objects.create_user(username, password="x")
    user.groups.add(Group.objects.get(name=rol))
    return user


def _csv(respuesta):
    return list(csv.reader(StringIO(respuesta.content.decode("utf-8-sig"))))


class _Base(TestCase):
    def setUp(self):
        cache.clear()
        call_command("seed_becas", stdout=StringIO())
        self.programa_siis = ProgramaSiis.objects.create(nombre="Producción", siis_programa_id=38)
        self.seg_a = Segmento.objects.create(programa=self.programa_siis, nombre="Seg A", cupo_maximo=100)
        self.seg_b = Segmento.objects.create(programa=self.programa_siis, nombre="Seg B", cupo_maximo=100)
        self.sub_a = Subsegmento.objects.create(segmento=self.seg_a, nombre="Sub A", cupo_maximo=40)

        self.admin = _usuario("admin-335", ROL_ADMIN)
        self.coord = _usuario("coord-335", ROL_COORDINADOR)
        AsignacionCoordinador.objects.create(segmento=self.seg_a, coordinador=self.coord)
        self.referente = _usuario("referente-335", ROL_REFERENTE)
        AsignacionReferente.objects.create(referente=self.referente, coordinador=self.coord)
        self.regional = _usuario("regional-335", ROL_COORDINADOR_REGIONAL)
        self.sub_a.referente = self.regional
        self.sub_a.save(update_fields=["referente"])

        self.territorial = User.objects.create_user("territorial-335", password="x")
        # La convocatoria propia cuelga del subsegmento del Regional: así el Regional y el
        # Referente la **ven** y la negativa del export es por capacidad, no por alcance.
        self.conv_a = self._convocatoria(self.seg_a, "30300300", subsegmento=self.sub_a)
        self.conv_b = self._convocatoria(self.seg_b, "30300301")

    def _convocatoria(self, segmento, dni, subsegmento=None):
        conv = Convocatoria.objects.create(
            nombre=f"Conv {segmento.nombre}",
            segmento=segmento,
            subsegmento=subsegmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        relevamiento = Relevamiento.objects.create(
            convocatoria=conv,
            territorial=self.territorial,
            fecha_asignada=date(2026, 6, 1),
            fecha_hasta=date(2026, 6, 30),
            zona="Z",
        )
        ciudadano = Ciudadano.objects.create(dni=dni, nombre="Persona", apellido="Exportada")
        Formulario.objects.create(relevamiento=relevamiento, ciudadano=ciudadano, estado=Formulario.Estado.APROBADO)
        en_espera = Formulario.objects.create(
            relevamiento=relevamiento, ciudadano=ciudadano, estado=Formulario.Estado.ENVIADO
        )
        ListaEspera.objects.create(formulario=en_espera, segmento=segmento, posicion=1)
        return conv

    def _get(self, nombre, conv):
        return self.client.get(reverse(nombre, args=[conv.pk]))


class ReglaPorRolSembradoTests(_Base):
    def test_la_matriz_de_los_roles_sembrados(self):
        self.assertTrue(puede_exportar_convocatoria(self.admin))
        self.assertTrue(puede_exportar_convocatoria(self.coord))
        self.assertFalse(puede_exportar_convocatoria(self.regional))
        self.assertFalse(puede_exportar_convocatoria(self.referente))


class CoordinadorExportaTests(_Base):
    def test_el_coordinador_baja_los_tres_csv_de_su_segmento(self):
        self.client.force_login(self.coord)

        beneficiarios = self._get(EXPORTS[0], self.conv_a)
        relevamientos = self._get(EXPORTS[1], self.conv_a)
        espera = self._get(EXPORTS[2], self.conv_a)

        for respuesta in (beneficiarios, relevamientos, espera):
            self.assertEqual(respuesta.status_code, 200)
            self.assertEqual(respuesta["Content-Type"], "text/csv; charset=utf-8")
        self.assertEqual([fila[1] for fila in _csv(beneficiarios)[1:]], ["30300300"])
        self.assertEqual(len(_csv(relevamientos)), 2)
        self.assertEqual([fila[2] for fila in _csv(espera)[1:]], ["30300300"])

    def test_el_coordinador_no_baja_una_convocatoria_de_otro_segmento(self):
        """Fuera de su alcance la convocatoria no existe para él: 404, como el detalle."""
        self.client.force_login(self.coord)

        for nombre in EXPORTS:
            with self.subTest(export=nombre):
                self.assertEqual(self._get(nombre, self.conv_b).status_code, 404)

    def test_el_coordinador_no_baja_los_casos_del_link_publico(self):
        """RN-P13 sigue igual: el Coordinador sembrado no tiene ``relevamiento.publico``."""
        publico = Relevamiento.objects.create(
            convocatoria=self.conv_a,
            tipo=Relevamiento.Tipo.PUBLICO,
            fecha_asignada=date(2026, 6, 1),
            fecha_hasta=date(2026, 6, 30),
            zona="Link",
        )
        ciudadano = Ciudadano.objects.create(dni="30300399", nombre="Del", apellido="Link")
        Formulario.objects.create(relevamiento=publico, ciudadano=ciudadano, estado=Formulario.Estado.APROBADO)
        self.client.force_login(self.coord)

        dnis_coord = [fila[1] for fila in _csv(self._get(EXPORTS[0], self.conv_a))[1:]]
        # Contraste: quien sí ve los públicos (``relevamiento.publico`` es opt-in, ni el
        # Administrador sembrado la trae) baja los dos casos.
        self.client.force_login(User.objects.create_superuser("root-335", "root@x.test", "x"))
        dnis_root = [fila[1] for fila in _csv(self._get(EXPORTS[0], self.conv_a))[1:]]

        self.assertEqual(dnis_coord, ["30300300"])
        self.assertEqual(sorted(dnis_root), ["30300300", "30300399"])

    def test_el_coordinador_ve_los_botones(self):
        self.client.force_login(self.coord)

        respuesta = self.client.get(reverse("becas:convocatoria_detalle", args=[self.conv_a.pk]))

        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.context["puede_reportes"])
        self.assertContains(respuesta, "Exportar beneficiarios (CSV)")
        for nombre in EXPORTS:
            self.assertContains(respuesta, reverse(nombre, args=[self.conv_a.pk]))


class RegionalYReferenteNoExportanTests(_Base):
    def test_reciben_403_en_los_tres_csv(self):
        for usuario in (self.regional, self.referente):
            self.client.force_login(usuario)
            for nombre in EXPORTS:
                with self.subTest(usuario=usuario.username, export=nombre):
                    self.assertEqual(self._get(nombre, self.conv_a).status_code, 403)

    def test_no_ven_los_botones(self):
        for usuario in (self.regional, self.referente):
            with self.subTest(usuario=usuario.username):
                self.client.force_login(usuario)

                respuesta = self.client.get(reverse("becas:convocatoria_detalle", args=[self.conv_a.pk]))

                # La convocatoria la ven: el botón falta por la regla, no por el alcance.
                self.assertEqual(respuesta.status_code, 200)
                self.assertFalse(respuesta.context["puede_reportes"])
                self.assertNotContains(respuesta, "Exportar beneficiarios (CSV)")
                for nombre in EXPORTS:
                    self.assertNotContains(respuesta, reverse(nombre, args=[self.conv_a.pk]))


class AdministradorTests(_Base):
    def test_el_admin_baja_los_tres_csv_de_cualquier_segmento(self):
        self.client.force_login(self.admin)

        for conv in (self.conv_a, self.conv_b):
            for nombre in EXPORTS:
                with self.subTest(conv=conv.nombre, export=nombre):
                    self.assertEqual(self._get(nombre, conv).status_code, 200)

    def test_el_admin_ve_los_botones(self):
        self.client.force_login(self.admin)

        respuesta = self.client.get(reverse("becas:convocatoria_detalle", args=[self.conv_b.pk]))

        self.assertTrue(respuesta.context["puede_reportes"])


class RolDeOtroProgramaTests(_Base):
    """SEC-06: las dos capacidades tildadas en un rol de **otro** programa no abren nada."""

    def setUp(self):
        super().setUp()
        dispositivos = Programa.objects.create(codigo="DISPOSITIVOS", nombre="Dispositivos")
        grupo = Group.objects.create(name="Dispositivos con exportar de Becas")
        RolMeta.objects.create(grupo=grupo, categoria=rbac.CATEGORIA_PROGRAMA, programa=dispositivos, activo=True)
        ct = ContentType.objects.get_for_model(Capacidad)
        # Inyectadas a mano: el ABM ya no las ofrece fuera de Becas (SEC-06); lo que se
        # mide es que la regla tampoco las acepte.
        for codigo in ("becas.convocatoria.ver", "becas.beneficiario.ver", "becas.reportes.exportar"):
            grupo.permissions.add(Permission.objects.get(codename=rbac.codename_de(codigo), content_type=ct))
        self.ajeno = User.objects.create_user("dispositivos-335", password="x")
        self.ajeno.groups.add(grupo)
        # Y además le da el alcance: si la regla evaluara sin programa, el export saldría.
        AsignacionCoordinador.objects.create(segmento=self.seg_a, coordinador=self.ajeno)

    def test_sin_alcance_las_tiene_pero_la_regla_no_lo_deja(self):
        self.assertTrue(rbac.puede(self.ajeno, "becas.beneficiario.ver"))
        self.assertTrue(rbac.puede(self.ajeno, "becas.reportes.exportar"))
        self.assertFalse(puede_exportar_convocatoria(self.ajeno))

    def test_recibe_403_en_los_tres_csv(self):
        self.client.force_login(self.ajeno)

        for nombre in EXPORTS:
            with self.subTest(export=nombre):
                self.assertEqual(self._get(nombre, self.conv_a).status_code, 403)


class RolAMedidaDeBecasTests(_Base):
    """La regla no depende del rol sembrado: un rol armado a mano **del Programa Becas**
    con ``beneficiario.ver`` y ``reportes.exportar``, más una asignación de coordinador,
    baja los CSV de su segmento y no los de otro (MINOR del PR #903)."""

    def setUp(self):
        super().setUp()
        grupo = Group.objects.create(name="Becas — Analista de exportaciones")
        RolMeta.objects.create(grupo=grupo, categoria=rbac.CATEGORIA_PROGRAMA, programa=programa_becas(), activo=True)
        ct = ContentType.objects.get_for_model(Capacidad)
        for codigo in ("becas.beneficiario.ver", "becas.reportes.exportar"):
            grupo.permissions.add(Permission.objects.get(codename=rbac.codename_de(codigo), content_type=ct))
        self.a_medida = User.objects.create_user("a-medida-335", password="x")
        self.a_medida.groups.add(grupo)
        AsignacionCoordinador.objects.create(segmento=self.seg_a, coordinador=self.a_medida)

    def test_la_regla_lo_deja_pasar(self):
        self.assertTrue(puede_exportar_convocatoria(self.a_medida))

    def test_baja_los_tres_csv_de_su_segmento(self):
        self.client.force_login(self.a_medida)

        for nombre in EXPORTS:
            with self.subTest(export=nombre):
                self.assertEqual(self._get(nombre, self.conv_a).status_code, 200)

    def test_no_baja_los_de_otro_segmento(self):
        self.client.force_login(self.a_medida)

        for nombre in EXPORTS:
            with self.subTest(export=nombre):
                self.assertEqual(self._get(nombre, self.conv_b).status_code, 404)
