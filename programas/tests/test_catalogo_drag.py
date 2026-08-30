"""Catálogo de requisitos generales agrupado: vista agrupada, drag & drop y
grupos (Cambio 58, Fase 3: task #337, análisis #326)."""

import json
from io import StringIO

from django.contrib.auth.models import Group, Permission, User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from core.rbac import APP_LABEL, codename_de
from programas.management.commands.seed_becas import ROL_ADMIN
from programas.models import CanalFormulario, GrupoRequisito, PreguntaGlobal, TipoCampo
from users.models import RolMeta


def _seed():
    call_command("seed_becas", stdout=StringIO())


class _Base(TestCase):
    def setUp(self):
        _seed()
        self.admin = User.objects.create_user("admin-drag", password="x")
        self.admin.groups.add(Group.objects.get(name=ROL_ADMIN))
        self.client.force_login(self.admin)
        self.cuestionario = GrupoRequisito.objects.get(clave="cuestionario")
        self.contacto = GrupoRequisito.objects.get(clave="contacto")
        self.p1 = PreguntaGlobal.objects.create(
            texto="Pregunta uno", tipo=TipoCampo.STRING, grupo=self.cuestionario, orden=100
        )
        self.p2 = PreguntaGlobal.objects.create(
            texto="Pregunta dos", tipo=TipoCampo.INT, grupo=self.cuestionario, orden=101
        )

    def _reordenar(self, grupos, **kwargs):
        return self.client.post(
            reverse("becas:preguntas_reordenar"),
            data=json.dumps({"grupos": grupos}),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            **kwargs,
        )

    def _payload_actual(self):
        grupos = []
        for g in GrupoRequisito.objects.order_by("orden", "id"):
            grupos.append(
                {"id": g.pk, "preguntas": list(g.preguntas.order_by("orden", "id").values_list("pk", flat=True))}
            )
        return grupos


class VistaAgrupadaTests(_Base):
    def test_sin_filtros_muestra_los_grupos_con_manijas(self):
        resp = self.client.get(reverse("becas:preguntas"))
        self.assertEqual(resp.status_code, 200)
        self.assertIsNotNone(resp.context["grupos_con_preguntas"])
        nombres = [g.clave for g, _ in resp.context["grupos_con_preguntas"]]
        self.assertEqual(nombres, ["datos_personales", "contacto", "apoderado", "cuestionario"])
        html = resp.content.decode()
        self.assertIn("data-sortable-grupos", html)
        self.assertIn('data-puede-ordenar="1"', html)
        self.assertIn("pregunta-grip", html)
        self.assertIn("Nuevo grupo", html)

    def test_con_filtros_vuelve_la_tabla_plana(self):
        resp = self.client.get(reverse("becas:preguntas"), {"q": "uno"})
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.context["grupos_con_preguntas"])
        html = resp.content.decode()
        self.assertNotIn("data-sortable-grupos", html)
        self.assertIn("Pregunta uno", html)
        self.assertNotIn("Pregunta dos", html)

    def test_sin_permiso_de_edicion_no_hay_manijas(self):
        lector = User.objects.create_user("lector-drag", password="x")
        grupo = Group.objects.create(name="solo-lectura-preguntas")
        RolMeta.objects.create(grupo=grupo)  # solo cuentan los roles activos
        grupo.permissions.add(
            Permission.objects.get(content_type__app_label=APP_LABEL, codename=codename_de("becas.pregunta.ver"))
        )
        lector.groups.add(grupo)
        self.client.force_login(lector)
        resp = self.client.get(reverse("becas:preguntas"))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn('data-puede-ordenar="0"', html)
        self.assertNotIn("pregunta-grip", html)
        self.assertNotIn(reverse("becas:grupo_crear"), html)  # sin botón «Nuevo grupo»


class ReordenarTests(_Base):
    def test_mueve_una_pregunta_a_otro_grupo_y_renumera(self):
        grupos = self._payload_actual()
        por_id = {g["id"]: g for g in grupos}
        por_id[self.cuestionario.pk]["preguntas"].remove(self.p2.pk)
        por_id[self.contacto.pk]["preguntas"].insert(0, self.p2.pk)
        resp = self._reordenar(grupos)
        self.assertEqual(resp.status_code, 200, resp.content)
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["target"], "#preguntas-table")
        self.assertIn("data-sortable-grupos", data["html"])
        self.p2.refresh_from_db()
        self.assertEqual(self.p2.grupo, self.contacto)
        ordenes = list(PreguntaGlobal.objects.order_by("orden").values_list("orden", flat=True))
        self.assertEqual(ordenes, list(range(1, len(ordenes) + 1)))  # renumeración compacta y única
        # Dentro de Contacto quedó primera.
        primera = self.contacto.preguntas.order_by("orden").first()
        self.assertEqual(primera, self.p2)

    def test_reordena_los_grupos(self):
        grupos = self._payload_actual()
        grupos.reverse()
        resp = self._reordenar(grupos)
        self.assertEqual(resp.status_code, 200)
        claves = list(GrupoRequisito.objects.order_by("orden", "id").values_list("clave", flat=True))
        self.assertEqual(claves, ["cuestionario", "apoderado", "contacto", "datos_personales"])

    def test_payload_invalido_o_ids_inexistentes(self):
        resp = self.client.post(reverse("becas:preguntas_reordenar"), data="no-json", content_type="application/json")
        self.assertEqual(resp.status_code, 400)
        resp = self._reordenar([{"id": 999999, "preguntas": []}])
        self.assertEqual(resp.status_code, 409)
        resp = self._reordenar([{"id": self.cuestionario.pk, "preguntas": [self.p1.pk, self.p1.pk]}])
        self.assertEqual(resp.status_code, 400)

    def test_las_preguntas_que_no_vienen_quedan_detras(self):
        resp = self._reordenar([{"id": self.cuestionario.pk, "preguntas": [self.p2.pk]}])
        self.assertEqual(resp.status_code, 200)
        self.p2.refresh_from_db()
        self.assertEqual(self.p2.orden, 1)
        self.assertEqual(
            PreguntaGlobal.objects.count(), len(set(PreguntaGlobal.objects.values_list("orden", flat=True)))
        )

    def test_exige_permiso_de_edicion_y_post(self):
        self.assertEqual(self.client.get(reverse("becas:preguntas_reordenar")).status_code, 405)
        self.client.logout()
        resp = self._reordenar(self._payload_actual())
        self.assertIn(resp.status_code, (302, 403))


class GruposTests(_Base):
    def test_crear_grupo_por_ajax_devuelve_el_parcial(self):
        resp = self.client.post(
            reverse("becas:grupo_crear"),
            {"nombre": "Situación habitacional", "subtitulo": "Dónde vive", "canal": CanalFormulario.LINK},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        grupo = GrupoRequisito.objects.get(nombre="Situación habitacional")
        self.assertFalse(grupo.protegido)
        self.assertTrue(grupo.clave.startswith("grupo-"))
        self.assertEqual(grupo.orden, GrupoRequisito.objects.exclude(pk=grupo.pk).order_by("-orden").first().orden + 1)
        self.assertIn("Situación habitacional", resp.json()["html"])

    def test_nombre_duplicado_se_rechaza(self):
        resp = self.client.post(
            reverse("becas:grupo_crear"),
            {"nombre": "contacto", "canal": "ambos"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("nombre", resp.json()["errors"])

    def test_editar_un_protegido_renombra_pero_no_lo_desprotege(self):
        resp = self.client.post(
            reverse("becas:grupo_editar", args=[self.contacto.pk]),
            {"nombre": "Cómo te contactamos", "subtitulo": "", "canal": "app"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        self.contacto.refresh_from_db()
        self.assertEqual(self.contacto.nombre, "Cómo te contactamos")
        self.assertEqual(self.contacto.canal, "app")
        self.assertTrue(self.contacto.protegido)
        self.assertEqual(self.contacto.clave, "contacto")

    def test_eliminar_solo_grupos_libres_y_vacios(self):
        vacio = GrupoRequisito.objects.create(nombre="Vacío", orden=50)
        # Protegido: no.
        self.client.post(reverse("becas:grupo_eliminar", args=[self.contacto.pk]))
        self.assertTrue(GrupoRequisito.objects.filter(pk=self.contacto.pk).exists())
        # Con preguntas: no.
        con_preguntas = GrupoRequisito.objects.create(nombre="Con preguntas", orden=51)
        self.p1.grupo = con_preguntas
        self.p1.save()
        self.client.post(reverse("becas:grupo_eliminar", args=[con_preguntas.pk]))
        self.assertTrue(GrupoRequisito.objects.filter(pk=con_preguntas.pk).exists())
        # Libre y vacío: sí.
        resp = self.client.post(reverse("becas:grupo_eliminar", args=[vacio.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(GrupoRequisito.objects.filter(pk=vacio.pk).exists())

    def test_grupo_eliminar_no_acepta_get(self):
        self.assertEqual(self.client.get(reverse("becas:grupo_eliminar", args=[self.contacto.pk])).status_code, 405)


class JsCatalogoTests(TestCase):
    def test_el_patron_de_la_cookie_csrf_escapa_las_barras(self):
        r"""`'\s'` en un string JS es la letra s: el patrón solo encontraba la
        cookie si `csrftoken` iba primera y el drag & drop fallaba con 403."""
        from pathlib import Path

        from django.conf import settings

        js = Path(settings.BASE_DIR, "static", "custom", "js", "nodo-catalogo-grupos.js").read_text(encoding="utf-8")
        self.assertIn("'(^|;)\\\\s*' + name + '\\\\s*=\\\\s*([^;]+)'", js)
