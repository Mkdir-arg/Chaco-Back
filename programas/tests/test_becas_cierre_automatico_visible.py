"""El cierre por vencimiento deja traza en el relevamiento y se avisa al operador.

El cron de las 03:10 manda los relevamientos a EN_REVISION sin que nadie lo vea:
la marca ``cerrado_automaticamente_en`` es lo que permite explicarlo en el detalle
y avisar, al extender la convocatoria, que no vuelven solos a campo.
"""

from datetime import timedelta

from django.contrib.messages import get_messages
from django.urls import reverse
from django.utils import timezone

from django.contrib.auth.models import Group, User

from programas.management.commands.seed_becas import ROL_COORDINADOR, ROL_REFERENTE
from programas.models import AsignacionCoordinador, AsignacionReferente, Relevamiento
from programas.tests.test_becas_vencimientos import _Base, _correr

EN_REVISION = Relevamiento.Estado.EN_REVISION


class MarcaDelCronTests(_Base):
    def test_el_cron_marca_solo_a_los_que_transiciona(self):
        conv = self._conv(self.ayer)
        en_curso = self._rel(conv, Relevamiento.Estado.EN_CURSO)
        finalizado = self._rel(conv, Relevamiento.Estado.FINALIZADO, fecha_finalizado=timezone.now())
        ya_en_revision = self._rel(conv, EN_REVISION)
        terminado = self._rel(conv, Relevamiento.Estado.TERMINADO)

        _correr()

        for rel in (en_curso, finalizado, ya_en_revision, terminado):
            rel.refresh_from_db()
        self.assertIsNotNone(en_curso.cerrado_automaticamente_en)
        self.assertIsNotNone(finalizado.cerrado_automaticamente_en)
        self.assertIsNone(ya_en_revision.cerrado_automaticamente_en)
        self.assertIsNone(terminado.cerrado_automaticamente_en)

    def test_es_idempotente(self):
        conv = self._conv(self.ayer)
        rel = self._rel(conv, Relevamiento.Estado.EN_CURSO)
        _correr()
        rel.refresh_from_db()
        primera = rel.cerrado_automaticamente_en

        _correr()

        rel.refresh_from_db()
        self.assertEqual(rel.cerrado_automaticamente_en, primera)

    def test_por_fecha_hasta_con_convocatoria_vigente(self):
        conv = self._conv(self.manana)
        rel = self._rel(conv, Relevamiento.Estado.EN_CURSO)
        Relevamiento.objects.filter(pk=rel.pk).update(fecha_hasta=timezone.now() - timedelta(hours=1))

        _correr()

        rel.refresh_from_db()
        self.assertEqual(rel.estado, EN_REVISION)
        self.assertIsNotNone(rel.cerrado_automaticamente_en)


class DetalleYVolverACampoTests(_Base):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)
        self.conv = self._conv(self.ayer)
        self.rel = self._rel(self.conv, Relevamiento.Estado.EN_CURSO)
        _correr()
        self.rel.refresh_from_db()

    def test_el_detalle_explica_el_cierre(self):
        resp = self.client.get(reverse("becas:relevamiento_detalle", args=[self.rel.pk]))

        cuando = timezone.localtime(self.rel.cerrado_automaticamente_en)
        self.assertContains(resp, f"Cerrado automáticamente el {cuando:%d/%m/%Y %H:%M} porque venció su período.")
        self.assertContains(resp, "Para seguir cargando, usá «Volver a campo».")

    def test_sin_marca_no_hay_aviso(self):
        Relevamiento.objects.filter(pk=self.rel.pk).update(cerrado_automaticamente_en=None)

        resp = self.client.get(reverse("becas:relevamiento_detalle", args=[self.rel.pk]))

        self.assertNotContains(resp, "Cerrado automáticamente")

    def test_volver_a_campo_limpia_la_marca(self):
        self.conv.fecha_fin = self.manana
        self.conv.activo = True
        self.conv.save()
        nueva = timezone.localtime(timezone.now() + timedelta(hours=5))

        self.client.post(
            reverse("becas:relevamiento_reabrir", args=[self.rel.pk]),
            {"fecha_hasta": nueva.strftime("%Y-%m-%dT%H:%M")},
        )

        self.rel.refresh_from_db()
        self.assertEqual(self.rel.estado, Relevamiento.Estado.EN_CURSO)
        self.assertIsNone(self.rel.cerrado_automaticamente_en)
        resp = self.client.get(reverse("becas:relevamiento_detalle", args=[self.rel.pk]))
        self.assertNotContains(resp, "Cerrado automáticamente")

    def test_sin_capacidad_de_editar_ve_el_motivo_pero_no_la_accion(self):
        coordinador = User.objects.create_user("coord_cierre", password="x")
        coordinador.groups.add(Group.objects.get(name=ROL_COORDINADOR))
        AsignacionCoordinador.objects.create(segmento=self.seg, coordinador=coordinador)
        referente = User.objects.create_user("ref_cierre", password="x")
        referente.groups.add(Group.objects.get(name=ROL_REFERENTE))
        AsignacionReferente.objects.create(referente=referente, coordinador=coordinador)
        self.client.force_login(referente)

        resp = self.client.get(reverse("becas:relevamiento_detalle", args=[self.rel.pk]))

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "porque venció su período.")
        self.assertNotContains(resp, "Para seguir cargando, usá «Volver a campo».")

    def test_terminar_limpia_la_marca(self):
        resp = self.client.post(reverse("becas:revision_terminar", args=[self.rel.pk]))

        self.assertEqual(resp.status_code, 302)
        self.rel.refresh_from_db()
        self.assertEqual(self.rel.estado, Relevamiento.Estado.TERMINADO)
        self.assertIsNone(self.rel.cerrado_automaticamente_en)


class AvisoAlExtenderConvocatoriaTests(_Base):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)
        self.conv = self._conv(self.ayer)
        self.cerrados = [self._rel(self.conv, Relevamiento.Estado.EN_CURSO) for _ in range(2)]
        self._rel(self.conv, EN_REVISION)  # en revisión por otra vía: no cuenta
        _correr()
        self.conv.refresh_from_db()

    def _mensajes(self, resp):
        return [m.message for m in get_messages(resp.wsgi_request)]

    def _editar(self, fecha_fin, activo):
        datos = {
            "nombre": self.conv.nombre,
            "segmento": self.seg.pk,
            "fecha_inicio": self.conv.fecha_inicio,
            "fecha_fin": fecha_fin,
            "descripcion": "",
        }
        if activo:
            datos["activo"] = "on"
        return self.client.post(reverse("becas:convocatoria_editar", args=[self.conv.pk]), datos)

    def test_extender_y_reactivar_avisa_con_el_conteo(self):
        resp = self._editar(self.manana, activo=True)

        self.assertEqual(resp.status_code, 302)
        self.assertIn(
            "La convocatoria tiene 2 relevamientos cerrados automáticamente por vencimiento. "
            "Si tienen que volver a campo, usá «Volver a campo» en cada uno.",
            self._mensajes(resp),
        )
        for rel in self.cerrados:  # no reabre nada
            rel.refresh_from_db()
            self.assertEqual(rel.estado, EN_REVISION)

    def test_editar_sin_tocar_fecha_ni_activo_no_avisa(self):
        self.conv.activo = True
        self.conv.fecha_fin = self.manana
        self.conv.save()

        resp = self._editar(self.manana, activo=True)

        self.assertFalse([m for m in self._mensajes(resp) if "cerrado" in m and "automáticamente" in m])

    def test_sin_relevamientos_cerrados_por_el_cron_no_avisa(self):
        Relevamiento.objects.update(cerrado_automaticamente_en=None)

        resp = self._editar(self.manana, activo=True)

        self.assertFalse([m for m in self._mensajes(resp) if "automáticamente" in m])

    def test_la_reactivacion_rapida_tambien_avisa(self):
        resp = self.client.post(
            reverse("becas:convocatoria_reactivar", args=[self.conv.pk]), {"fecha_fin": self.manana.isoformat()}
        )

        self.assertTrue([m for m in self._mensajes(resp) if "2 relevamientos cerrados automáticamente" in m])
