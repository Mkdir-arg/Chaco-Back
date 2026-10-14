"""P3 con asistencia lateral y vencimiento edilicio compartido por P2/P4."""

import json
import re
import shutil
import subprocess
from datetime import timedelta
from unittest import skipUnless
from unittest.mock import patch

from django.conf import settings
from django.db import connection
from django.db.utils import IntegrityError
from django.test import tag
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from programas.forms import DispositivoForm
from programas.models import Dispositivo, Edificio, InspeccionEdificio, TrazaDispositivo
from programas.services.alertas_dispositivos import relevamientos_vencidos
from programas.services.detalle_dispositivo import infraestructura_del_dispositivo
from programas.services.dispositivos import campos_para_validacion
from programas.services.inspecciones import SEMAFOROS, SIN_RELEVAR, VENCIDO, semaforos_de_dispositivos
from programas.tests.test_dispositivos_fidelidad_fd import AHORA
from programas.tests.test_dispositivos_infraestructura import BaseInfraestructura


class FidelidadFITests(BaseInfraestructura):
    def setUp(self):
        reloj = patch("django.utils.timezone.now", return_value=AHORA)
        reloj.start()
        self.addCleanup(reloj.stop)
        super().setUp()
        self.client.force_login(self.admin)
        self.crear = reverse("dispositivos:crear")
        self.cis.estado = Dispositivo.Estado.BORRADOR
        self.cis.save()
        self.editar = reverse("dispositivos:editar", args=[self.cis.pk])
        self.datos = {
            "tipo": self.tipo.pk,
            "codigo": "FI-NUEVO",
            "nombre": "Institución FI",
            "localidad": "Resistencia",
            "domicilio": "Calle 123",
            "responsable_nombre": "Responsable FI",
            "contacto_telefono": "123456",
        }

    def test_alta_y_edicion_tienen_dos_columnas_y_paneles(self):
        for url in (self.crear, self.editar):
            with self.subTest(url=url):
                respuesta = self.client.get(url)
                self.assertContains(respuesta, 'class="grid grid-cols-1 lg:grid-cols-3 gap-5"')
                self.assertContains(respuesta, 'class="lg:col-span-2 min-w-0"')
                self.assertContains(respuesta, "Posibles duplicados")
                self.assertContains(respuesta, "Qué falta para validar")
                self.assertContains(respuesta, "Borrador</span>")
                self.assertContains(respuesta, 'name="accion" value="enviar_validacion"')
        self.assertContains(self.client.get(self.crear), 'id="duplicate-search"')
        self.assertNotContains(self.client.get(self.editar), 'id="duplicate-search"')

    def test_faltantes_salen_de_la_regla_y_del_valor_actual_del_form(self):
        form = DispositivoForm(data={**self.datos, "responsable_nombre": "", "contacto_telefono": ""})
        self.assertEqual([f.name for f in form.requisitos_validacion], list(campos_para_validacion()))
        self.assertEqual([f.name for f in form.faltantes_validacion], ["responsable_nombre", "contacto_telefono"])
        self.assertEqual(DispositivoForm(data=self.datos).faltantes_validacion, [])
        respuesta = self.client.post(self.crear, {**self.datos, "accion": "enviar_validacion", "localidad": ""})
        self.assertContains(respuesta, "Completá los campos obligatorios")
        self.assertContains(respuesta, 'data-requisito-campo="id_localidad">Localidad</li>')
        self.assertFalse(Dispositivo.objects.filter(codigo=self.datos["codigo"]).exists())
        self.assertNotContains(respuesta, "Editar institución")
        self.assertContains(respuesta, 'id="duplicate-search"')

    def test_guardar_borrador_sigue_admitiendo_datos_operativos_faltantes(self):
        respuesta = self.client.post(self.crear, {**self.datos, "responsable_nombre": "", "localidad": ""})
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(Dispositivo.objects.get(codigo=self.datos["codigo"]).estado, Dispositivo.Estado.BORRADOR)

    def test_enviar_desde_alta_y_edicion_guarda_y_transiciona_con_traza(self):
        for url, codigo in ((self.crear, "FI-NUEVO"), (self.editar, self.cis.codigo)):
            with self.subTest(url=url):
                respuesta = self.client.post(url, {**self.datos, "codigo": codigo, "accion": "enviar_validacion"})
                self.assertEqual(respuesta.status_code, 302)
                dispositivo = Dispositivo.objects.get(codigo=codigo)
                self.assertEqual(dispositivo.estado, Dispositivo.Estado.PENDIENTE_VALIDACION)
                self.assertEqual(dispositivo.responsable_nombre, self.datos["responsable_nombre"])
                self.assertTrue(
                    TrazaDispositivo.objects.filter(dispositivo=dispositivo, accion="ENVIADO_VALIDACION").exists()
                )

    def test_envio_invalido_no_guarda_la_edicion_ni_su_traza(self):
        respuesta = self.client.post(self.editar, {**self.datos, "accion": "enviar_validacion", "domicilio": ""})
        self.assertContains(respuesta, "Completá los campos obligatorios")
        self.cis.refresh_from_db()
        self.assertEqual(self.cis.codigo, "CIS-3")
        self.assertFalse(TrazaDispositivo.objects.filter(dispositivo=self.cis).exists())

    def test_colision_al_guardar_conserva_el_render_de_alta_y_restaura_la_base(self):
        guardar = DispositivoForm.save

        def colision(form):
            guardar(form)
            raise IntegrityError("Colisión concurrente del código")

        with patch.object(DispositivoForm, "save", autospec=True, side_effect=colision):
            respuesta = self.client.post(self.crear, self.datos)
        self.assertContains(respuesta, "Ya existe un dispositivo con este código")
        self.assertContains(respuesta, 'id="duplicate-search"')
        self.assertNotContains(respuesta, "Editar institución")
        self.assertFalse(Dispositivo.objects.filter(codigo=self.datos["codigo"]).exists())

    def test_solo_borrador_y_observado_ofrecen_envio_y_servidor_rechaza_activo(self):
        for estado in Dispositivo.Estado.values:
            self.cis.estado = estado
            self.cis.save()
            if estado == Dispositivo.Estado.CERRADO:
                self.assertEqual(self.client.get(self.editar).status_code, 403)
                continue
            respuesta = self.client.get(self.editar)
            esperado = estado in (Dispositivo.Estado.BORRADOR, Dispositivo.Estado.OBSERVADO)
            self.assertEqual(respuesta.context["puede_enviar_validacion"], esperado)
        self.cis.estado = Dispositivo.Estado.ACTIVO
        self.cis.save()
        respuesta = self.client.post(self.editar, {**self.datos, "accion": "enviar_validacion"})
        self.assertContains(respuesta, "La transición de estado solicitada no está permitida")
        self.cis.refresh_from_db()
        self.assertEqual(self.cis.codigo, "CIS-3")

    def test_crear_sin_editar_no_ofrece_envio_y_post_forjado_no_crea(self):
        from core.rbac import codename_de

        rol = self.admin.groups.get()
        rol.permissions.remove(*rol.permissions.filter(codename=codename_de("dispositivo.editar")))
        self.client.force_login(self._fresco(self.admin))
        self.assertNotContains(self.client.get(self.crear), 'name="accion"')
        self.assertEqual(self.client.post(self.crear, {**self.datos, "accion": "enviar_validacion"}).status_code, 403)
        self.assertFalse(Dispositivo.objects.filter(codigo="FI-NUEVO").exists())

    def test_creador_con_editar_sin_asignacion_no_puede_enviar_institucion_nueva(self):
        usuario = self._usuario(
            "creador_fi", ("dispositivo.crear", "dispositivo.editar", "dispositivo.ver"), [self.cis]
        )
        self.client.force_login(usuario)
        self.assertNotContains(self.client.get(self.crear), 'name="accion"')
        self.assertEqual(self.client.post(self.crear, {**self.datos, "accion": "enviar_validacion"}).status_code, 403)
        self.assertFalse(Dispositivo.objects.filter(codigo="FI-NUEVO").exists())
        self.assertContains(self.client.get(self.editar), 'name="accion"')

    def test_codigo_repetido_bloquea_aunque_la_coincidencia_este_fuera_del_alcance(self):
        usuario = self._usuario("creador_fuera_fi", ("dispositivo.crear", "dispositivo.ver"), [self.cis])
        self.client.force_login(usuario)
        respuesta = self.client.get(reverse("dispositivos:buscar_duplicados"), {"codigo": self.parador.codigo})
        self.assertEqual(respuesta.json()["coincidencias"], [])
        self.assertTrue(respuesta.json()["codigo_duplicado"])
        self.assertContains(
            self.client.post(self.crear, {**self.datos, "codigo": self.parador.codigo}), "Ya existe un dispositivo"
        )

    @skipUnless(shutil.which("node"), "Requiere Node para ejecutar el JS renderizado")
    def test_el_resumen_de_faltantes_sigue_la_edicion_en_el_navegador(self):
        html = self.client.get(self.editar).content.decode()
        script = next(s for s in re.findall(r"<script>(.*?)</script>", html, re.S) if "actualizarFaltantes" in s)
        resultado = subprocess.run(
            [shutil.which("node"), str(settings.BASE_DIR / "programas/tests/js/faltantes_fi.cjs")],
            input=json.dumps(script),
            text=True,
            capture_output=True,
            timeout=15,
        )
        self.assertEqual(resultado.returncode, 0, resultado.stderr)

    @skipUnless(shutil.which("node"), "Requiere Node para ejecutar el JS renderizado")
    def test_los_dos_catch_ignoran_abortos_y_reenvio_conserva_submitter(self):
        html = self.client.get(self.crear).content.decode()
        script = next(s for s in re.findall(r"<script>(.*?)</script>", html, re.S) if "const codigo =" in s)
        resultado = subprocess.run(
            [shutil.which("node"), str(settings.BASE_DIR / "programas/tests/js/duplicados_fi.cjs")],
            input=json.dumps(script),
            text=True,
            capture_output=True,
            timeout=15,
        )
        self.assertEqual(resultado.returncode, 0, resultado.stderr)

    def test_vencido_comparte_regla_con_alerta_y_cambia_p2_p4_y_predio(self):
        inspeccion = self._crear()
        InspeccionEdificio.objects.filter(pk=inspeccion.pk).update(fecha_vencimiento=AHORA.date() - timedelta(days=1))
        self.assertEqual(len(list(relevamientos_vencidos(self.parador))), 1)
        semaforos = semaforos_de_dispositivos([self.parador.pk, self.geriatrico.pk, self.cis.pk])
        for dispositivo in (self.parador, self.geriatrico):
            self.assertEqual(semaforos[dispositivo.pk], SEMAFOROS[VENCIDO])
            datos = infraestructura_del_dispositivo(dispositivo)
            self.assertEqual(datos["semaforo"], SEMAFOROS[VENCIDO])
            self.assertEqual(datos["edificios"][0]["semaforo"], SEMAFOROS[VENCIDO])
            self.assertContains(
                self.client.get(reverse("dispositivos:detalle", args=[dispositivo.pk])), "Vencido</span>"
            )
        self.assertEqual(semaforos[self.cis.pk], SEMAFOROS[SIN_RELEVAR])
        self.assertContains(self.client.get(reverse("dispositivos:lista")), "Vencido</span>")

    def test_dia_del_vencimiento_no_vencido_y_vigente_conserva_criticidad(self):
        self._relevar(self.predio, InspeccionEdificio.Criticidad.MEDIA)
        inspeccion = self._crear()
        for fecha in (AHORA.date(), AHORA.date() + timedelta(days=1)):
            InspeccionEdificio.objects.filter(pk=inspeccion.pk).update(fecha_vencimiento=fecha)
            self.assertEqual(list(relevamientos_vencidos(self.parador)), [])
            self.assertEqual(semaforos_de_dispositivos([self.parador.pk])[self.parador.pk].texto, "Regular")
            self.assertEqual(infraestructura_del_dispositivo(self.parador)["semaforo"].texto, "Regular")

    def test_cancelada_y_realizada_no_encienden_vencido(self):
        inspeccion = self._crear()
        for estado in (InspeccionEdificio.Estado.CANCELADA, InspeccionEdificio.Estado.REALIZADA):
            InspeccionEdificio.objects.filter(pk=inspeccion.pk).update(
                estado=estado,
                fecha_vencimiento=AHORA.date() - timedelta(days=1),
                criticidad=InspeccionEdificio.Criticidad.BAJA if estado == InspeccionEdificio.Estado.REALIZADA else "",
                realizada_en=AHORA if estado == InspeccionEdificio.Estado.REALIZADA else None,
                realizada_por=self.agente if estado == InspeccionEdificio.Estado.REALIZADA else None,
                motivo_cancelacion="Cancelado en prueba" if estado == InspeccionEdificio.Estado.CANCELADA else "",
            )
            self.assertEqual(list(relevamientos_vencidos(self.parador)), [])
            esperado = "Bueno" if estado == InspeccionEdificio.Estado.REALIZADA else "Sin relevar"
            self.assertEqual(semaforos_de_dispositivos([self.parador.pk])[self.parador.pk].texto, esperado)

    def test_vencido_prevalece_sobre_criticidad_y_sin_relevar_en_otro_edificio(self):
        self._relevar(self.predio, InspeccionEdificio.Criticidad.ALTA)
        self.edificio_cis.dispositivos.add(self.parador)
        inspeccion = self._crear()
        InspeccionEdificio.objects.filter(pk=inspeccion.pk).update(fecha_vencimiento=AHORA.date() - timedelta(days=1))
        self.assertEqual(semaforos_de_dispositivos([self.parador.pk])[self.parador.pk].texto, "Vencido")
        self.assertEqual(infraestructura_del_dispositivo(self.parador)["semaforo"].texto, "Vencido")

    @tag("performance")
    def test_vencidos_se_leen_en_lote_sin_aumentar_presupuestos(self):
        self._relevar(self.predio, InspeccionEdificio.Criticidad.BAJA)
        inspeccion = self._crear()
        InspeccionEdificio.objects.filter(pk=inspeccion.pk).update(fecha_vencimiento=AHORA.date() - timedelta(days=1))
        presupuestos = json.loads((settings.BASE_DIR / "scripts/perf_budgets.json").read_text(encoding="utf-8"))[
            "servicios"
        ]
        ids = [self.parador.pk]
        medidas = []
        for cantidad in (1, 9):
            if cantidad > 1:
                for indice in range(8):
                    dispositivo = Dispositivo.objects.create(
                        tipo=self.tipo, codigo=f"FI-PERF-{indice}", nombre=f"FI {indice}"
                    )
                    ids.append(dispositivo.pk)
                    edificio = Edificio.objects.create(codigo=f"FI-ED-{indice}", nombre=f"FI edificio {indice}")
                    edificio.dispositivos.add(dispositivo, self.parador)
                    InspeccionEdificio.objects.create(
                        edificio=edificio,
                        asignado_a=self.agente,
                        creado_por=self.admin,
                        fecha_vencimiento=AHORA.date() - timedelta(days=1),
                    )
            with CaptureQueriesContext(connection) as consultas:
                semaforos = semaforos_de_dispositivos(ids)
            self.assertLessEqual(len(consultas), presupuestos["dispositivos_semaforo_edilicio"]["consultas_fijas"])
            self.assertTrue(all(s.nivel == VENCIDO for s in semaforos.values()))
            total_semaforo = len(consultas)
            with CaptureQueriesContext(connection) as consultas:
                datos = infraestructura_del_dispositivo(self.parador)
            self.assertLessEqual(len(consultas), presupuestos["dispositivos_infraestructura"]["consultas_fijas"])
            self.assertEqual(datos["semaforo"].nivel, VENCIDO)
            medidas.append((total_semaforo, len(consultas)))
        self.assertEqual(medidas[0], medidas[1])
