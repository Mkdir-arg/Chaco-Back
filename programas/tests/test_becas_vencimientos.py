"""Tests del cierre por vencimiento de convocatorias y su cascada a relevamientos.

Cubre: corte de fecha (con `localdate()`), idempotencia, cascada a EN_REVISION,
flags `--dry-run` / `--solo`, y la reactivación con "fecha manda".
"""

from datetime import timedelta
from io import StringIO

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from programas.forms import ConvocatoriaForm
from programas.management.commands.seed_becas import ROL_ADMIN
from programas.models import Convocatoria, Relevamiento, Segmento
from programas.services.vencimientos import (
    ESTADOS_RELEVAMIENTO_ABIERTOS,
    ESTADOS_RELEVAMIENTO_CERRADOS,
)

# La partición escrita a mano, a propósito: los tests de abajo recorren estas
# tuplas y no las constantes del servicio, así que sacarle o agregarle un estado
# a `ESTADOS_RELEVAMIENTO_ABIERTOS` deja un test en rojo (RED-28, mutación M27).
# `test_la_particion_de_estados_cubre_el_enum` las enfrenta con el enum real.
ESTADOS_ABIERTOS_ESPERADOS = (
    Relevamiento.Estado.ASIGNADO,
    Relevamiento.Estado.EN_CURSO,
    Relevamiento.Estado.FINALIZANDO,
    Relevamiento.Estado.FINALIZADO,
)
ESTADOS_CERRADOS_ESPERADOS = (
    Relevamiento.Estado.EN_REVISION,
    Relevamiento.Estado.TERMINADO,
)


def _correr(*args):
    out = StringIO()
    call_command("procesar_vencimientos", *args, stdout=out, stderr=StringIO())
    return out.getvalue()


class _Base(TestCase):
    def setUp(self):
        call_command("seed_becas", stdout=StringIO())
        self.hoy = timezone.localdate()
        self.ayer = self.hoy - timedelta(days=1)
        self.manana = self.hoy + timedelta(days=1)
        self.seg = Segmento.objects.create(nombre="Segmento", cupo_maximo=100)
        self.admin = User.objects.create_user("admin_becas", password="x")
        self.admin.groups.add(Group.objects.get(name=ROL_ADMIN))

    def _conv(self, fecha_fin, activo=True, nombre="Conv"):
        return Convocatoria.objects.create(
            nombre=nombre,
            segmento=self.seg,
            fecha_inicio=self.hoy - timedelta(days=30),
            fecha_fin=fecha_fin,
            activo=activo,
        )

    def _rel(self, conv, estado, fecha_finalizado=None):
        rel = Relevamiento.objects.create(
            convocatoria=conv,
            territorial=self.admin,
            fecha_asignada=self.hoy - timedelta(days=10),
            zona="Zona",
            estado=estado,
        )
        if fecha_finalizado is not None:
            Relevamiento.objects.filter(pk=rel.pk).update(fecha_finalizado=fecha_finalizado)
            rel.refresh_from_db()
        return rel


class CierreConvocatoriaTests(_Base):
    def test_cierra_vencida(self):
        conv = self._conv(self.ayer)
        _correr()
        conv.refresh_from_db()
        self.assertFalse(conv.activo)
        self.assertTrue(conv.cerrada_automaticamente)
        self.assertIsNotNone(conv.cerrada_el)

    def test_no_cierra_el_dia_de_fin(self):
        # fecha_fin = hoy → sigue vigente todo el día (corte es fecha_fin < hoy).
        conv = self._conv(self.hoy)
        _correr()
        conv.refresh_from_db()
        self.assertTrue(conv.activo)

    def test_no_cierra_futura(self):
        conv = self._conv(self.manana)
        _correr()
        conv.refresh_from_db()
        self.assertTrue(conv.activo)

    def test_idempotente(self):
        conv = self._conv(self.ayer)
        _correr()
        conv.refresh_from_db()
        cerrada_el = conv.cerrada_el
        # Segunda corrida: no hay pendientes, no vuelve a tocar.
        salida = _correr()
        conv.refresh_from_db()
        self.assertEqual(conv.cerrada_el, cerrada_el)
        self.assertIn("sin pendientes", salida)

    def test_no_toca_ya_inactiva(self):
        # Una baja manual previa (activo=False) no queda marcada como cierre automático.
        conv = self._conv(self.ayer, activo=False)
        _correr()
        conv.refresh_from_db()
        self.assertFalse(conv.cerrada_automaticamente)


class CascadaRelevamientoTests(_Base):
    def test_relevamientos_abiertos_pasan_a_revision(self):
        conv = self._conv(self.ayer)
        asignado = self._rel(conv, Relevamiento.Estado.ASIGNADO)
        en_curso = self._rel(conv, Relevamiento.Estado.EN_CURSO)
        _correr()
        asignado.refresh_from_db()
        en_curso.refresh_from_db()
        self.assertEqual(asignado.estado, Relevamiento.Estado.EN_REVISION)
        self.assertEqual(en_curso.estado, Relevamiento.Estado.EN_REVISION)
        # A los que no tenían fecha_finalizado se les sella al cortar el campo.
        self.assertIsNotNone(asignado.fecha_finalizado)

    def test_no_pisa_fecha_finalizado_existente(self):
        conv = self._conv(self.ayer)
        marca = timezone.now() - timedelta(days=2)
        fin = self._rel(conv, Relevamiento.Estado.FINALIZADO, fecha_finalizado=marca)
        _correr()
        fin.refresh_from_db()
        self.assertEqual(fin.estado, Relevamiento.Estado.EN_REVISION)
        self.assertEqual(fin.fecha_finalizado, marca)

    def test_no_toca_terminados_ni_en_revision(self):
        conv = self._conv(self.ayer)
        terminado = self._rel(conv, Relevamiento.Estado.TERMINADO)
        revision = self._rel(conv, Relevamiento.Estado.EN_REVISION)
        _correr()
        terminado.refresh_from_db()
        revision.refresh_from_db()
        self.assertEqual(terminado.estado, Relevamiento.Estado.TERMINADO)
        self.assertEqual(revision.estado, Relevamiento.Estado.EN_REVISION)

    def test_vence_por_fecha_hasta_aunque_la_convocatoria_siga_vigente(self):
        conv = self._conv(self.manana)
        asignado = self._rel(conv, Relevamiento.Estado.ASIGNADO)
        _correr()
        asignado.refresh_from_db()
        self.assertEqual(asignado.estado, Relevamiento.Estado.EN_REVISION)

    def test_todos_los_estados_abiertos_pasan_a_revision(self):
        """RED-28: la partición completa de los estados que el cron cierra.

        `FINALIZANDO` (el relevamiento que está sincronizando desde la app) no
        lo cubría ningún test: sacarlo de `ESTADOS_RELEVAMIENTO_ABIERTOS` dejaba
        esos relevamientos fuera del cierre automático para siempre y la suite
        seguía en verde.
        """
        conv = self._conv(self.ayer)
        rels = {estado: self._rel(conv, estado) for estado in ESTADOS_ABIERTOS_ESPERADOS}

        _correr()

        for estado, rel in rels.items():
            with self.subTest(estado=estado):
                rel.refresh_from_db()
                self.assertEqual(rel.estado, Relevamiento.Estado.EN_REVISION)

    def test_los_estados_cerrados_no_se_tocan(self):
        """RED-28: la otra mitad de la partición. Un estado de más en la tupla
        de abiertos cortaría trabajo que ya está cerrado."""
        conv = self._conv(self.ayer)
        rels = {estado: self._rel(conv, estado) for estado in ESTADOS_CERRADOS_ESPERADOS}

        _correr()

        for estado, rel in rels.items():
            with self.subTest(estado=estado):
                rel.refresh_from_db()
                self.assertEqual(rel.estado, estado)

    def test_la_particion_de_estados_cubre_el_enum(self):
        """RED-28: todo estado del enum cae en exactamente una de las dos
        tuplas, y las dos son las que recorren los tests de arriba. Un estado
        nuevo sin clasificar deja de ser una omisión silenciosa."""
        abiertos = set(ESTADOS_RELEVAMIENTO_ABIERTOS)
        cerrados = set(ESTADOS_RELEVAMIENTO_CERRADOS)

        self.assertEqual(abiertos | cerrados, set(Relevamiento.Estado))
        self.assertEqual(abiertos & cerrados, set())
        self.assertEqual(abiertos, set(ESTADOS_ABIERTOS_ESPERADOS))
        self.assertEqual(cerrados, set(ESTADOS_CERRADOS_ESPERADOS))

    def test_por_fecha_hasta_solo_vencen_asignado_y_en_curso(self):
        """Caracterización (RED-28): la segunda rama de la regla —vencimiento
        por `fecha_hasta` con la convocatoria todavía vigente— usa una lista de
        estados más corta que la primera.

        Conducta de hoy, recorriendo el enum entero: un `FINALIZANDO` o un
        `FINALIZADO` cuya ventana de campo ya pasó **no** se cierra solo
        mientras la convocatoria siga abierta; lo cierra el día que vence la
        convocatoria. Si G1-04 cambia esto, este test lo marca.
        """
        conv = self._conv(self.manana)
        rels = {estado: self._rel(conv, estado) for estado in Relevamiento.Estado}
        vencen_por_fecha = {Relevamiento.Estado.ASIGNADO, Relevamiento.Estado.EN_CURSO}

        _correr()

        for estado, rel in rels.items():
            with self.subTest(estado=estado):
                rel.refresh_from_db()
                esperado = Relevamiento.Estado.EN_REVISION if estado in vencen_por_fecha else estado
                self.assertEqual(rel.estado, esperado)


class FlagsComandoTests(_Base):
    def test_dry_run_no_modifica(self):
        conv = self._conv(self.ayer)
        rel = self._rel(conv, Relevamiento.Estado.ASIGNADO)
        salida = _correr("--dry-run")
        conv.refresh_from_db()
        rel.refresh_from_db()
        self.assertTrue(conv.activo)
        self.assertEqual(rel.estado, Relevamiento.Estado.ASIGNADO)
        self.assertIn("dry-run", salida)

    def test_solo_una_regla(self):
        conv = self._conv(self.ayer)
        rel = self._rel(conv, Relevamiento.Estado.ASIGNADO)
        _correr("--solo", "becas.convocatoria")
        conv.refresh_from_db()
        rel.refresh_from_db()
        self.assertFalse(conv.activo)  # la regla de convocatoria corrió
        self.assertEqual(rel.estado, Relevamiento.Estado.ASIGNADO)  # la de relevamiento no

    def test_solo_slug_inexistente_falla(self):
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            _correr("--solo", "no.existe")


class ReactivacionTests(_Base):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)

    def test_reactivar_con_fecha_futura(self):
        conv = self._conv(self.ayer, activo=False)
        conv.cerrada_automaticamente = True
        conv.cerrada_el = timezone.now()
        conv.save()
        resp = self.client.post(
            reverse("becas:convocatoria_reactivar", args=[conv.pk]),
            {"fecha_fin": self.manana.isoformat()},
        )
        self.assertEqual(resp.status_code, 302)
        conv.refresh_from_db()
        self.assertTrue(conv.activo)
        self.assertEqual(conv.fecha_fin, self.manana)
        self.assertFalse(conv.cerrada_automaticamente)
        self.assertIsNone(conv.cerrada_el)

    def test_reactivar_con_fecha_pasada_rechaza(self):
        conv = self._conv(self.ayer, activo=False)
        resp = self.client.post(
            reverse("becas:convocatoria_reactivar", args=[conv.pk]),
            {"fecha_fin": self.ayer.isoformat()},
        )
        self.assertEqual(resp.status_code, 302)
        conv.refresh_from_db()
        self.assertFalse(conv.activo)
        self.assertEqual(conv.fecha_fin, self.ayer)

    def test_toggle_no_activa_vencida(self):
        # El toggle simple no puede reactivar una vencida (debe ir por reactivar).
        conv = self._conv(self.ayer, activo=False)
        resp = self.client.post(reverse("becas:convocatoria_toggle", args=[conv.pk]))
        self.assertEqual(resp.status_code, 302)
        conv.refresh_from_db()
        self.assertFalse(conv.activo)

    def test_toggle_desactiva_vigente(self):
        conv = self._conv(self.manana, activo=True)
        resp = self.client.post(reverse("becas:convocatoria_toggle", args=[conv.pk]))
        self.assertEqual(resp.status_code, 302)
        conv.refresh_from_db()
        self.assertFalse(conv.activo)


class FormFechaMandaTests(_Base):
    def _data(self, fecha_fin, activo):
        return {
            "nombre": "X",
            "segmento": self.seg.pk,
            "subsegmento": "",
            "fecha_inicio": (self.hoy - timedelta(days=30)).isoformat(),
            "fecha_fin": fecha_fin.isoformat(),
            "descripcion": "",
            "activo": activo,
        }

    def test_no_activa_con_fecha_pasada(self):
        form = ConvocatoriaForm(data=self._data(self.ayer, activo=True))
        self.assertFalse(form.is_valid())
        self.assertIn("fecha_fin", form.errors)

    def test_activa_con_fecha_futura_ok(self):
        form = ConvocatoriaForm(data=self._data(self.manana, activo=True))
        self.assertTrue(form.is_valid(), form.errors)

    def test_save_activa_limpia_flags(self):
        conv = self._conv(self.ayer, activo=False)
        conv.cerrada_automaticamente = True
        conv.cerrada_el = timezone.now()
        conv.save()
        form = ConvocatoriaForm(instance=conv, data=self._data(self.manana, activo=True))
        self.assertTrue(form.is_valid(), form.errors)
        obj = form.save()
        self.assertTrue(obj.activo)
        self.assertFalse(obj.cerrada_automaticamente)
        self.assertIsNone(obj.cerrada_el)
