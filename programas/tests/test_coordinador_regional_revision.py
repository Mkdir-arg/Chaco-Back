"""Cambio 336 — el Coordinador Regional consulta la revisión de sus casos (PM, 17/10/2026).

Decisión 5 del Cambio 332. El rol sembrado «Becas — Coordinador Regional» suma
``becas.revision.ver`` y **no** ``becas.revision.editar``:

- ve la bandeja, el listado de un relevamiento y el detalle de los casos de **sus**
  subsegmentos; los de un par del mismo segmento, los de la convocatoria del segmento
  entero y los de otro segmento le dan 403 (``assert_alcance_*`` sobre
  ``convocatorias_visibles``, que para él es «las convocatorias de sus subsegmentos»);
- no aprueba, no rechaza ni edita: las acciones redirigen al inicio (negativa por
  **capacidad**, ``requiere``) y el caso no cambia;
- el detalle no le dibuja los formularios que exigen ``revision.editar`` —contacto y
  duplicado—, igual que al Referente, que tiene solo ``revision.ver`` desde siempre;
- los links «Formulario N» de Cupo, que le daban 403, ahora abren.

Sigue sin ``becas.beneficiario.ver`` (Cambio 335): ve los beneficiarios desde Cupo pero
no baja el CSV de convocatoria.
"""

import re
from datetime import date
from io import StringIO

from django.contrib.auth.models import Group, User
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
    Relevamiento,
    Segmento,
    Subsegmento,
)
from programas.services.autorizacion import programa_becas

URL_CASO = re.compile(r"/becas/revision/formulario/(\d+)/")


def _usuario(username, rol):
    user = User.objects.create_user(username, password="x")
    user.groups.add(Group.objects.get(name=rol))
    return user


class _Base(TestCase):
    """Ana y Beto son Regionales **pares**: un subsegmento cada uno en el mismo segmento."""

    def setUp(self):
        cache.clear()
        call_command("seed_becas", stdout=StringIO())
        self.segmento = Segmento.objects.create(nombre="Fuego y Barro", cupo_maximo=300)
        self.otro_segmento = Segmento.objects.create(nombre="Producción", cupo_maximo=300)

        self.ana = _usuario("ana-336", ROL_COORDINADOR_REGIONAL)
        self.beto = _usuario("beto-336", ROL_COORDINADOR_REGIONAL)
        self.sub_ana = Subsegmento.objects.create(
            segmento=self.segmento, nombre="Ladrillo", cupo_maximo=100, referente=self.ana
        )
        self.sub_beto = Subsegmento.objects.create(
            segmento=self.segmento, nombre="Carbón", cupo_maximo=100, referente=self.beto
        )

        self.territorial = User.objects.create_user("terri-336", password="x")
        self.propio = self._caso("Propio", "30336001", self.segmento, self.sub_ana)
        self.del_par = self._caso("Del par", "30336002", self.segmento, self.sub_beto)
        self.del_segmento = self._caso("Del segmento", "30336003", self.segmento)
        self.de_otro_segmento = self._caso("Otro segmento", "30336004", self.otro_segmento)

    def _caso(self, etiqueta, dni, segmento, subsegmento=None, estado=Formulario.Estado.ENVIADO):
        convocatoria = Convocatoria.objects.create(
            nombre=f"Conv {etiqueta}",
            segmento=segmento,
            subsegmento=subsegmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        relevamiento = Relevamiento.objects.create(
            convocatoria=convocatoria,
            territorial=self.territorial,
            fecha_asignada=date(2026, 6, 1),
            fecha_hasta=date(2026, 6, 30),
            zona=f"Zona {etiqueta}",
        )
        ciudadano = Ciudadano.objects.create(dni=dni, nombre=etiqueta, apellido="Revisión")
        return Formulario.objects.create(
            relevamiento=relevamiento,
            ciudadano=ciudadano,
            estado=estado,
            celular="3624000000",
            email_contacto="persona@example.com",
        )

    def _detalle(self, caso):
        return self.client.get(reverse("becas:formulario_detalle", args=[caso.pk]))

    def _marcar_duplicado(self, caso):
        """Una segunda carga del mismo DNI en el mismo relevamiento, con el conflicto abierto."""
        return Formulario.objects.create(
            relevamiento=caso.relevamiento,
            ciudadano=caso.ciudadano,
            estado=Formulario.Estado.ENVIADO,
            celular="3624000001",
            conflicto_duplicado=True,
            duplicado_de=caso,
        )


class SemillaTests(_Base):
    def test_el_regional_tiene_revision_ver_y_no_editar(self):
        becas = programa_becas()
        self.assertTrue(rbac.puede(self.ana, "becas.revision.ver", programa=becas))
        self.assertFalse(rbac.puede(self.ana, "becas.revision.editar", programa=becas))
        # Decisión 5, segunda parte: ve beneficiarios desde Cupo, sin ``beneficiario.ver``.
        self.assertTrue(rbac.puede(self.ana, "becas.cupo.ver", programa=becas))
        self.assertFalse(rbac.puede(self.ana, "becas.beneficiario.ver", programa=becas))


class BandejaYListadoTests(_Base):
    def test_la_bandeja_muestra_solo_los_casos_de_sus_subsegmentos(self):
        self.client.force_login(self.ana)

        respuesta = self.client.get(reverse("becas:revision"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual([f.pk for f in respuesta.context["formularios"]], [self.propio.pk])
        self.assertContains(respuesta, self.propio.ciudadano.dni)
        for ajeno in (self.del_par, self.del_segmento, self.de_otro_segmento):
            self.assertNotContains(respuesta, ajeno.ciudadano.dni)

    def test_abre_el_listado_de_su_relevamiento(self):
        self.client.force_login(self.ana)

        respuesta = self.client.get(reverse("becas:revision_formularios", args=[self.propio.relevamiento_id]))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, reverse("becas:formulario_detalle", args=[self.propio.pk]))
        # «Terminar relevamiento» es ``revision.editar``: no se le ofrece.
        self.assertNotContains(respuesta, reverse("becas:revision_terminar", args=[self.propio.relevamiento_id]))

    def test_no_abre_el_listado_de_un_relevamiento_ajeno(self):
        self.client.force_login(self.ana)

        for ajeno in (self.del_par, self.del_segmento, self.de_otro_segmento):
            with self.subTest(caso=ajeno.ciudadano.nombre):
                respuesta = self.client.get(reverse("becas:revision_formularios", args=[ajeno.relevamiento_id]))
                self.assertEqual(respuesta.status_code, 403)

    def test_el_menu_lateral_le_muestra_revision(self):
        self.client.force_login(self.ana)

        respuesta = self.client.get(reverse("becas:cupo_segmento", args=[self.segmento.pk]))

        self.assertContains(respuesta, f'href="{reverse("becas:revision")}"')


class DetalleTests(_Base):
    def test_abre_el_detalle_de_un_caso_suyo(self):
        self.client.force_login(self.ana)

        respuesta = self._detalle(self.propio)

        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(respuesta.context["puede_editar_caso"])

    def test_no_abre_casos_fuera_de_sus_subsegmentos(self):
        self.client.force_login(self.ana)

        for ajeno in (self.del_par, self.del_segmento, self.de_otro_segmento):
            with self.subTest(caso=ajeno.ciudadano.nombre):
                self.assertEqual(self._detalle(ajeno).status_code, 403)

    def test_no_aprueba_ni_rechaza(self):
        self.client.force_login(self.ana)

        aprobar = self.client.post(reverse("becas:formulario_aprobar", args=[self.propio.pk]))
        rechazar = self.client.post(
            reverse("becas:formulario_rechazar", args=[self.propio.pk]), {"motivo": "No corresponde"}
        )

        # Negativa por capacidad: ``requiere`` redirige al inicio (403 en AJAX).
        for respuesta in (aprobar, rechazar):
            self.assertRedirects(respuesta, reverse("core:inicio"), fetch_redirect_response=False)
        ajax = self.client.post(
            reverse("becas:formulario_aprobar", args=[self.propio.pk]), HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertEqual(ajax.status_code, 403)
        self.propio.refresh_from_db()
        self.assertEqual(self.propio.estado, Formulario.Estado.ENVIADO)

    def test_no_edita_el_contacto_por_post(self):
        self.client.force_login(self.ana)

        respuesta = self.client.post(
            reverse("becas:formulario_detalle", args=[self.propio.pk]),
            {"celular": "3624999999", "email_contacto": "otro@example.com"},
        )

        self.assertEqual(respuesta.status_code, 403)
        self.propio.refresh_from_db()
        self.assertEqual(self.propio.celular, "3624000000")

    def test_no_ve_los_formularios_que_exigen_editar(self):
        self.client.force_login(self.ana)

        respuesta = self._detalle(self.propio)

        self.assertNotContains(respuesta, "Guardar cambios")
        self.assertNotContains(respuesta, 'id="btn-aprobar"')
        # Los datos de contacto se siguen viendo, en campos deshabilitados.
        self.assertContains(respuesta, "3624000000")
        self.assertTrue(all(campo.disabled for campo in respuesta.context["form"].fields.values()))

    def test_no_ve_los_botones_de_duplicado(self):
        otra_carga = self._marcar_duplicado(self.propio)
        self.client.force_login(self.ana)

        respuesta = self._detalle(otra_carga)

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "DNI cargado desde más de un dispositivo")
        self.assertContains(respuesta, f"Comparar con el caso {self.propio.numero}")
        self.assertNotContains(respuesta, reverse("becas:formulario_resolver_duplicado", args=[otra_carga.pk]))
        self.assertNotContains(respuesta, "Conservar este")

    def test_no_resuelve_el_duplicado_por_post(self):
        otra_carga = self._marcar_duplicado(self.propio)
        self.client.force_login(self.ana)

        respuesta = self.client.post(
            reverse("becas:formulario_resolver_duplicado", args=[otra_carga.pk]), {"decision": "conservar_actual"}
        )

        self.assertRedirects(respuesta, reverse("core:inicio"), fetch_redirect_response=False)
        otra_carga.refresh_from_db()
        self.assertFalse(otra_carga.conflicto_resuelto)


class CupoTests(_Base):
    def setUp(self):
        super().setUp()
        self.beneficiario = self._caso(
            "Beneficiario", "30336010", self.segmento, self.sub_ana, estado=Formulario.Estado.APROBADO
        )
        self._caso("Beneficiario del par", "30336011", self.segmento, self.sub_beto, estado=Formulario.Estado.APROBADO)

    def test_los_links_a_sus_casos_abren(self):
        self.client.force_login(self.ana)

        cupo = self.client.get(reverse("becas:cupo_segmento", args=[self.segmento.pk]))
        enlazados = {int(pk) for pk in URL_CASO.findall(cupo.content.decode())}

        self.assertEqual(cupo.status_code, 200)
        self.assertContains(cupo, f"Formulario {self.beneficiario.numero}")
        self.assertIn(self.beneficiario.pk, enlazados)
        for pk in enlazados:
            with self.subTest(formulario=pk):
                self.assertEqual(self.client.get(reverse("becas:formulario_detalle", args=[pk])).status_code, 200)


class QuienEditaTests(_Base):
    """La otra mitad: el Referente (solo ``revision.ver``) tampoco ve los dos formularios, y
    quien tiene ``revision.editar`` los sigue viendo."""

    def setUp(self):
        super().setUp()
        self.coord = _usuario("coord-336", ROL_COORDINADOR)
        AsignacionCoordinador.objects.create(segmento=self.segmento, coordinador=self.coord)
        self.referente = _usuario("referente-336", ROL_REFERENTE)
        AsignacionReferente.objects.create(referente=self.referente, coordinador=self.coord)
        self.otra_carga = self._marcar_duplicado(self.propio)

    def test_el_referente_no_ve_contacto_ni_duplicado(self):
        self.client.force_login(self.referente)

        respuesta = self._detalle(self.otra_carga)

        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, "Guardar cambios")
        self.assertNotContains(respuesta, reverse("becas:formulario_resolver_duplicado", args=[self.otra_carga.pk]))
        self.assertContains(respuesta, "DNI cargado desde más de un dispositivo")

    def test_quien_edita_los_sigue_viendo(self):
        admin = _usuario("admin-336", ROL_ADMIN)
        for usuario in (self.coord, admin):
            with self.subTest(usuario=usuario.username):
                self.client.force_login(usuario)

                respuesta = self._detalle(self.otra_carga)

                self.assertTrue(respuesta.context["puede_editar_caso"])
                self.assertContains(respuesta, "Guardar cambios")
                self.assertContains(
                    respuesta, reverse("becas:formulario_resolver_duplicado", args=[self.otra_carga.pk])
                )
                self.assertFalse(any(campo.disabled for campo in respuesta.context["form"].fields.values()))
