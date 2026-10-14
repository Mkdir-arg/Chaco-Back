"""Revisión del resultado: permiso, candado, auditoría y presentación de P21."""

import json
import re
from datetime import datetime
from datetime import timezone as tz
from pathlib import Path
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.db.models.deletion import ProtectedError
from django.test import Client, tag
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from core.tests.candados import candados_tomados
from programas.models import InspeccionEdificio, TrazaInspeccion
from programas.selectors.inspecciones import relevamiento_para_revision
from programas.services import inspecciones as servicio
from programas.tests.test_dispositivos_inspecciones import TODAS_DE_DISPOSITIVOS, BaseInspecciones
from programas.tests.test_dispositivos_relevamientos_listado import _sin_token

AHORA = datetime(2026, 10, 14, 12, 0, tzinfo=tz.utc)


class BaseRevision(BaseInspecciones):
    def setUp(self):
        reloj = patch("django.utils.timezone.now", return_value=AHORA)
        reloj.start()
        self.addCleanup(reloj.stop)
        super().setUp()

    def _completada(self):
        return servicio.registrar_resultado(
            self._fresco(self.agente), self._crear(), criticidad=InspeccionEdificio.Criticidad.ALTA
        )

    def _cliente(self, usuario, csrf=False):
        cliente = Client(enforce_csrf_checks=csrf)
        cliente.force_login(usuario)
        return cliente

    def _url(self, inspeccion):
        return reverse("dispositivos:relevamiento_revisar", args=[inspeccion.pk])


class RevisionTests(BaseRevision):
    def test_revision_registra_autor_fecha_traza_y_candado_sin_cambiar_el_resultado(self):
        inspeccion = self._completada()
        with candados_tomados(InspeccionEdificio.objects) as candados:
            revisada = servicio.marcar_revisado(self._fresco(self.coordinador), inspeccion)
        self.assertEqual(candados, ["inspecciones.py:_bloquear"])
        self.assertEqual(revisada.revisado_en, AHORA)
        self.assertEqual(revisada.revisado_por, self.coordinador)
        self.assertEqual(revisada.estado, InspeccionEdificio.Estado.REALIZADA)
        self.assertEqual(revisada.realizada_en, inspeccion.realizada_en)
        self.assertEqual(revisada.criticidad, inspeccion.criticidad)
        traza = revisada.trazas.get(accion=TrazaInspeccion.Accion.REVISADA)
        self.assertEqual(traza.usuario, self.coordinador)
        self.assertEqual(traza.creado_en, AHORA)
        self.assertIn("revisado por coordinador", traza.detalle)
        self.assertEqual(servicio.ultima_inspeccion(self.predio).pk, inspeccion.pk)
        self.assertEqual(servicio.ultimas_inspecciones_por_edificio([self.predio.pk])[self.predio.pk].pk, inspeccion.pk)
        self.assertEqual(servicio.semaforos_de_dispositivos([self.parador.pk])[self.parador.pk].tono, "danger")

    def test_no_se_revisa_una_asignada(self):
        inspeccion = self._crear()
        with self.assertRaisesMessage(ValidationError, "Solo se puede revisar un relevamiento completado"):
            servicio.marcar_revisado(self._fresco(self.coordinador), inspeccion)
        inspeccion.refresh_from_db()
        self.assertIsNone(inspeccion.revisado_en)
        self.assertIsNone(inspeccion.revisado_por)
        self.assertFalse(inspeccion.trazas.filter(accion=TrazaInspeccion.Accion.REVISADA).exists())

    def test_no_se_revisa_una_cancelada(self):
        inspeccion = servicio.cancelar_inspeccion(self._fresco(self.coordinador), self._crear(), "Reprogramado")
        with self.assertRaisesMessage(ValidationError, "Solo se puede revisar un relevamiento completado"):
            servicio.marcar_revisado(self._fresco(self.coordinador), inspeccion)
        inspeccion.refresh_from_db()
        self.assertIsNone(inspeccion.revisado_en)

    def test_dos_revisiones_incluso_con_objeto_desactualizado_no_pisan_la_primera(self):
        inspeccion = self._completada()
        servicio.marcar_revisado(self._fresco(self.coordinador), inspeccion)
        with self.assertRaisesMessage(ValidationError, "ya está revisado"):
            servicio.marcar_revisado(self._fresco(self.coordinador), inspeccion)
        inspeccion.refresh_from_db()
        self.assertEqual(inspeccion.revisado_en, AHORA)
        self.assertEqual(inspeccion.trazas.filter(accion=TrazaInspeccion.Accion.REVISADA).count(), 1)

    def test_sin_capacidad_aunque_tenga_todo_lo_demas_no_revisa(self):
        usuario = self._usuario(
            "sin_revisar", [c for c in TODAS_DE_DISPOSITIVOS if c != "inspeccion.asignar"], [self.parador]
        )
        inspeccion = self._completada()
        with self.assertRaises(PermissionDenied):
            servicio.marcar_revisado(self._fresco(usuario), inspeccion)
        respuesta = self._cliente(usuario).post(self._url(inspeccion))
        self.assertEqual(respuesta.status_code, 403)
        self.assertNotContains(respuesta, self.predio.nombre, status_code=403)
        inspeccion.refresh_from_db()
        self.assertIsNone(inspeccion.revisado_en)

    def test_fuera_de_alcance_403_igual_que_inexistente_sin_leer_estado(self):
        inspeccion = self._completada()
        usuario = self._usuario(
            "otra_institucion", [c for c in TODAS_DE_DISPOSITIVOS if c != "programa.configurar"], [self.cis]
        )
        with self.assertRaises(PermissionDenied):
            servicio.marcar_revisado(self._fresco(usuario), inspeccion)
        self.assertIsNone(relevamiento_para_revision(self._fresco(usuario), inspeccion.pk))
        self.assertIsNone(relevamiento_para_revision(self._fresco(usuario), 999999))
        cliente = self._cliente(usuario)
        ajeno = cliente.post(self._url(inspeccion))
        inexistente = cliente.post(reverse("dispositivos:relevamiento_revisar", args=[999999]))
        self.assertEqual((ajeno.status_code, inexistente.status_code), (403, 403))
        self.assertEqual(_sin_token(ajeno.content), _sin_token(inexistente.content))
        self.assertNotContains(ajeno, self.predio.nombre, status_code=403)
        ajeno_ajax = cliente.post(self._url(inspeccion), HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        inexistente_ajax = cliente.post(
            reverse("dispositivos:relevamiento_revisar", args=[999999]), HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertEqual((ajeno_ajax.status_code, inexistente_ajax.status_code), (403, 403))
        self.assertEqual(
            ajeno_ajax.json(), {"ok": False, "message": "No tenés permiso para revisar este relevamiento."}
        )
        self.assertEqual(ajeno_ajax.json(), inexistente_ajax.json())
        inspeccion.refresh_from_db()
        self.assertIsNone(inspeccion.revisado_en)

    def test_error_de_auditoria_revierte_la_revision(self):
        inspeccion = self._completada()
        with patch.object(servicio, "_trazar", side_effect=RuntimeError("Traza fallida")):
            with self.assertRaises(RuntimeError):
                servicio.marcar_revisado(self._fresco(self.coordinador), inspeccion)
        inspeccion.refresh_from_db()
        self.assertIsNone(inspeccion.revisado_en)
        self.assertIsNone(inspeccion.revisado_por)

    def test_revisor_protegido_aunque_no_tenga_otras_referencias(self):
        usuario = self._usuario("revisor_nuevo", ("inspeccion.asignar",), [self.parador])
        servicio.marcar_revisado(usuario, self._completada())
        # El campo, además de la traza, conserva su autor.
        self.assertEqual(InspeccionEdificio._meta.get_field("revisado_por").remote_field.on_delete.__name__, "PROTECT")
        with self.assertRaises(ProtectedError):
            usuario.delete()

    def test_post_csrf_y_solo_post_y_modal_canonico(self):
        inspeccion = self._completada()
        cliente = self._cliente(self.coordinador, csrf=True)
        url = self._url(inspeccion)
        self.assertEqual(cliente.get(url).status_code, 405)
        informe = reverse("dispositivos:relevamiento_informe", args=[inspeccion.pk])
        respuesta = cliente.get(informe)
        self.assertContains(respuesta, 'data-confirm-danger="false"')
        self.assertContains(respuesta, f'data-confirm-url="{url}"')
        self.assertContains(respuesta, "ModernModal.show(opciones)")
        self.assertEqual(cliente.post(url).status_code, 403)
        token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', respuesta.content.decode()).group(1)
        self.assertRedirects(cliente.post(url, {"csrfmiddlewaretoken": token}), informe)
        respuesta = cliente.get(informe)
        self.assertContains(respuesta, "Completado")
        self.assertContains(respuesta, ">Revisado</span>")
        self.assertContains(respuesta, "Revisado por")
        self.assertContains(respuesta, "coordinador")
        self.assertNotContains(respuesta, f'data-confirm-url="{url}"')
        duplicado = cliente.post(url, {"csrfmiddlewaretoken": token}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(duplicado.status_code, 400)
        self.assertIn("ya está revisado", str(duplicado.json()))

    def test_informe_no_ofrece_revision_a_lector_ni_fuera_de_alcance(self):
        inspeccion = self._completada()
        url = reverse("dispositivos:relevamiento_informe", args=[inspeccion.pk])
        fuera = self._usuario("coord_cis", ("inspeccion.asignar",), [self.cis])
        lector = self._usuario("lector_predio", ("dispositivo.ver",), [self.parador])
        fuera.groups.add(*lector.groups.all())
        for usuario in (lector, fuera, self.agente):
            with self.subTest(usuario=usuario.username):
                respuesta = self._cliente(usuario).get(url)
                self.assertEqual(respuesta.status_code, 200)
                self.assertNotContains(respuesta, "Marcar como revisado")

    def test_informe_no_ofrece_revision_de_asignada_o_cancelada_al_coordinador(self):
        inspeccion = self._crear()
        cliente = self._cliente(self.coordinador)
        url = reverse("dispositivos:relevamiento_informe", args=[inspeccion.pk])
        self.assertNotContains(cliente.get(url), "Marcar como revisado")
        servicio.cancelar_inspeccion(self._fresco(self.coordinador), inspeccion, "Reprogramado")
        self.assertNotContains(cliente.get(url), "Marcar como revisado")

    def test_revisados_es_subconjunto_de_completados_con_filtro_y_conteo(self):
        revisada = servicio.marcar_revisado(self._fresco(self.coordinador), self._completada())
        pendiente = self._completada()
        cliente = self._cliente(self.coordinador)
        lista = reverse("dispositivos:relevamientos")
        respuesta = cliente.get(lista, {"tab": "revisados", "asignado_a": self.agente.pk})
        solapas = {s["clave"]: s for s in respuesta.context["solapas"]}
        self.assertEqual(solapas["completados"]["total"], 2)
        self.assertEqual(solapas["revisados"]["total"], 1)
        self.assertEqual([r.pk for r in solapas["revisados"]["filas"]], [revisada.pk])
        self.assertContains(respuesta, ">Revisado</span>")
        self.assertNotContains(respuesta, f'data-confirm-url="{self._url(revisada)}')
        self.assertContains(respuesta, f'data-confirm-url="{self._url(pendiente)}')
        sin_filas = cliente.get(lista, {"tab": "revisados", "asignado_a": self.otro_agente.pk})
        self.assertEqual(next(s for s in sin_filas.context["solapas"] if s["clave"] == "revisados")["total"], 0)
        self.assertRedirects(
            cliente.post(self._url(pendiente) + "?volver=tab%3Dcompletados"), lista + "?tab=completados"
        )

    def test_revision_desde_informe_conserva_el_origen_del_boton_volver(self):
        inspeccion = self._completada()
        cliente = self._cliente(self.coordinador)
        informe = reverse("dispositivos:relevamiento_informe", args=[inspeccion.pk])
        respuesta = cliente.get(informe, {"dispositivo": self.parador.pk})
        url_revision = respuesta.context["url_revisar"]
        self.assertIn("origen=informe", url_revision)
        self.assertRedirects(cliente.post(url_revision), informe + f"?dispositivo={self.parador.pk}")
        respuesta = cliente.get(informe, {"dispositivo": self.parador.pk})
        self.assertEqual(
            respuesta.context["volver_url"],
            reverse("dispositivos:detalle", args=[self.parador.pk]) + "?tab=infraestructura",
        )


@tag("performance")
class RevisionPresupuestoTests(BaseRevision):
    def test_p21_con_revisores_no_consulta_por_fila(self):
        cliente = self._cliente(self.coordinador)
        lista = reverse("dispositivos:relevamientos")
        cliente.get(lista)
        servicio.cancelar_inspeccion(self._fresco(self.coordinador), self._crear(), "Reprogramado")
        presupuesto = json.loads((Path(__file__).resolve().parents[2] / "scripts/perf_budgets.json").read_text())
        techo = presupuesto["servicios"]["dispositivos_relevamientos_revisados"]["consultas_fijas"]
        medidas = []
        for total in (2, 20):
            for _ in range(total - (2 if medidas else 0)):
                servicio.marcar_revisado(self._fresco(self.coordinador), self._completada())
            en_curso = self._crear()
            with CaptureQueriesContext(connection) as consultas:
                respuesta = cliente.get(lista, {"tab": "revisados"})
            self.assertEqual(respuesta.status_code, 200)
            self.assertEqual(next(s for s in respuesta.context["solapas"] if s["clave"] == "revisados")["total"], total)
            medidas.append(len(consultas))
            self.assertLessEqual(len(consultas), techo, f"Revisados excede el presupuesto con {total} filas")
            servicio.cancelar_inspeccion(self._fresco(self.coordinador), en_curso, "Reprogramado")
        self.assertEqual(medidas[0], medidas[1], "P21 consulta por revisor o por fila")
