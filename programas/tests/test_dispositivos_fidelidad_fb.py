"""P2/P4/P19: semáforo configurable, acciones acotadas y predio sin datos ajenos."""

import json
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from decimal import Decimal
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import Group
from django.db import connection
from django.test import tag
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from programas.models import AsignacionDispositivo, Estadia, Plaza, ReservaPlaza
from programas.selectors.capacidad_dispositivo import instituciones_del_predio
from programas.services.dispositivos import dispositivos_visibles
from programas.services.ocupacion import Conteo, tension_de_ocupacion
from programas.tests.test_dispositivos_detalle import BaseDetalle, _alojar, _egresar
from programas.tests.test_dispositivos_estadias import CAPACIDADES_OPERATIVAS, _permiso
from programas.tests.test_dispositivos_infraestructura import BaseInfraestructura, Criticidad, _panel
from users.models import RolMeta

AHORA = datetime(2026, 10, 14, 12, 0, tzinfo=dt_timezone.utc)


class FidelidadDetalleTests(BaseDetalle):
    def setUp(self):
        reloj = patch("django.utils.timezone.now", return_value=AHORA)
        reloj.start()
        self.addCleanup(reloj.stop)
        super().setUp()
        self.estadia = _alojar(self.cis, self.plaza, self.persona, AHORA - timedelta(days=2))

    def test_p2_y_p4_usan_los_umbrales_del_tipo_y_el_mismo_conteo(self):
        for amarillo, rojo, tono, etiqueta in (
            (51, 90, "success", "Normal"),
            (50, 90, "warning", "Exigida"),
            (0, 50, "danger", "Crítica"),
        ):
            with self.subTest(amarillo=amarillo, rojo=rojo):
                self.tipo.umbral_ocupacion_amarillo = amarillo
                self.tipo.umbral_ocupacion_rojo = rojo
                self.tipo.save()
                detalle = self.client.get(self.url)
                tarjeta = detalle.context["indicadores"][0]
                listado = self.client.get(reverse("dispositivos:lista"))
                fila = next(d for d in listado.context["dispositivos"] if d.pk == self.cis.pk)
                self.assertEqual((tarjeta["valor"], tarjeta["tono"]), ("50 %", tono))
                self.assertEqual((fila.plazas.porcentaje, fila.plazas.tono), (50, tono))
                self.assertContains(detalle, f"{etiqueta} · 1 de 2 operativas")
                self.assertContains(detalle, f"bg-{tono}-soft text-fg-{tono}")

    def test_el_porcentaje_no_cuenta_reservas_ni_plazas_fuera_de_servicio(self):
        Plaza.objects.create(
            sector=self.sector, codigo="F", estado=Plaza.Estado.FUERA_SERVICIO, motivo_fuera_servicio="Colchón"
        )
        ReservaPlaza.objects.create(
            plaza=self.otra_plaza,
            ciudadano=self.otra_persona,
            desde=AHORA - timedelta(hours=1),
            hasta=AHORA + timedelta(hours=1),
        )
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.context["indicadores"][0]["valor"], "50 %")
        self.assertEqual(respuesta.context["n_plazas"], sum(s["totales"] for s in respuesta.context["sectores"]))

    def test_sin_operativas_o_sin_conteo_no_inventa_cero_por_ciento(self):
        for conteo in (Conteo(totales=2, fuera_de_servicio=2, ocupadas=0), Conteo(totales=2)):
            self.assertIsNone(tension_de_ocupacion(conteo, tipo=self.tipo).porcentaje)

    def test_datos_incluye_email_horarios_y_ubicacion_del_legajo(self):
        self.cis.contacto_email = "institucion@example.test"
        self.cis.horarios = "Lunes a viernes\n08:00 a 20:00"
        self.cis.latitud = Decimal("-27.451120")
        self.cis.longitud = Decimal("-58.986340")
        self.cis.save()
        respuesta = self.client.get(self.url)
        self.assertContains(respuesta, self.cis.contacto_email)
        self.assertContains(respuesta, self.cis.horarios)
        self.assertContains(respuesta, "https://www.openstreetmap.org/?mlat=-27.451120&amp;mlon=-58.986340")

    def test_menu_y_modal_cambio_reusan_formulario_de_p7_sin_plazas_tomadas(self):
        respuesta = self.client.get(self.url)
        self.assertContains(respuesta, f'id="menu-fila-{self.estadia.pk}"')
        for accion in ("Ver estadía", "Cambiar plaza", "Registrar egreso"):
            self.assertContains(respuesta, accion)
        modal = self.client.get(self.url, {"cambio": self.estadia.pk})
        self.assertContains(modal, "modalCambio: true")
        self.assertContains(modal, 'x-becas-modal="modalCambio"')
        self.assertContains(
            modal, f'action="{reverse("dispositivos:cambiar_plaza", args=[self.cis.pk, self.estadia.pk])}"'
        )
        self.assertEqual(
            modal.context["form_cambio"].fields["plaza"].choices[1:], [("Varones", [(self.otra_plaza.pk, "P2")])]
        )

    def test_sin_plazas_libres_cambio_deshabilitado_con_motivo_y_sin_modal(self):
        _alojar(self.cis, self.otra_plaza, self.otra_persona, AHORA - timedelta(days=1))
        respuesta = self.client.get(self.url)
        self.assertContains(respuesta, 'aria-disabled="true"')
        self.assertContains(respuesta, "No hay plazas libres en el dispositivo.")
        self.assertNotIn("form_cambio", self.client.get(self.url, {"cambio": self.estadia.pk}).context)

    def test_egresada_y_sin_plaza_no_ofrecen_cambiar_plaza(self):
        Estadia.objects.filter(pk=self.estadia.pk).update(plaza=None)
        self.assertNotContains(self.client.get(self.url), ">Cambiar plaza<")
        self.assertNotIn("form_cambio", self.client.get(self.url, {"cambio": self.estadia.pk}).context)
        _egresar(self.estadia)
        respuesta = self.client.get(self.url, {"estado": "TODAS"})
        self.assertNotContains(respuesta, ">Cambiar plaza<")
        self.assertNotContains(respuesta, ">Registrar egreso<")
        self.assertNotIn("form_cambio", self.client.get(self.url, {"cambio": self.estadia.pk}).context)
        self.assertNotIn("estadia_egreso", self.client.get(self.url, {"egreso": self.estadia.pk}).context)

    def test_cambiar_plaza_no_ofrece_el_cupo_libre_si_el_tipo_solo_admite_camas(self):
        self.tipo.tipos_plaza_admitidos = [Plaza.Tipo.CAMA]
        self.tipo.save()
        self.otra_plaza.tipo = Plaza.Tipo.CUPO
        self.otra_plaza.save()
        respuesta = self.client.get(self.url)
        [fila] = respuesta.context["estadias"]
        self.assertEqual(fila.motivo_cambiar, "No hay plazas libres en el dispositivo.")
        self.assertContains(respuesta, 'aria-disabled="true"')
        self.assertNotIn("form_cambio", self.client.get(self.url, {"cambio": self.estadia.pk}).context)

    def test_menu_y_modal_consultan_las_plazas_elegibles_una_sola_vez(self):
        from programas.services.ingreso import plazas_para_ingresar

        with patch("programas.views.dispositivos_legajo.plazas_para_ingresar", wraps=plazas_para_ingresar) as mapa:
            self.assertIn("form_cambio", self.client.get(self.url, {"cambio": self.estadia.pk}).context)
        mapa.assert_called_once()

    def test_cada_accion_y_modal_exigen_su_capacidad(self):
        for capacidad, accion, parametro in (
            ("dispositivo.admitir", "Cambiar plaza", "cambio"),
            ("dispositivo.egresar", "Registrar egreso", "egreso"),
            ("ciudadano.ver", "Ver estadía", None),
        ):
            with self.subTest(capacidad=capacidad):
                usuario = self._operador(
                    capacidad,
                    self.cis,
                    (
                        *[c for c in CAPACIDADES_OPERATIVAS if c != capacidad],
                        *([] if capacidad == "ciudadano.ver" else ["ciudadano.ver"]),
                    ),
                )
                self.client.force_login(usuario)
                self.assertNotContains(self.client.get(self.url), f">{accion}<")
                if parametro:
                    self.assertEqual(self.client.get(self.url, {parametro: self.estadia.pk}).status_code, 403)

    def test_modal_ajeno_inexistente_y_id_no_ascii_son_el_mismo_404(self):
        ajena = _alojar(self.parador, self.plaza_parador, self.otra_persona, AHORA - timedelta(days=1))
        for parametro in ("cambio", "egreso"):
            for pk in (ajena.pk, 999999, "²", "١", "-1", " 1"):
                with self.subTest(parametro=parametro, pk=pk):
                    self.assertEqual(self.client.get(self.url, {parametro: pk}).status_code, 404)

    def test_cambio_json_desde_p4_vuelve_a_p4_sin_exigir_ciudadano_ver(self):
        usuario = self._operador("Admisor sin legajo", self.cis, CAPACIDADES_OPERATIVAS)
        self.client.force_login(usuario)
        respuesta = self.client.post(
            reverse("dispositivos:cambiar_plaza", args=[self.cis.pk, self.estadia.pk]),
            {
                "plaza": self.otra_plaza.pk,
                "momento": timezone.localtime(AHORA).strftime("%Y-%m-%dT%H:%M"),
                "motivo": "Convivencia",
                "volver": "dispositivo",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.json()["ok"])
        self.assertEqual(respuesta.json()["redirect"], f"{self.url}?tab=estadias")
        self.estadia.refresh_from_db()
        self.assertEqual(self.estadia.plaza_id, self.otra_plaza.pk)

    def test_egreso_se_abre_con_el_formulario_de_la_persona_elegida(self):
        respuesta = self.client.get(self.url, {"egreso": self.estadia.pk})
        self.assertContains(respuesta, "modalEgreso: true")
        self.assertEqual(respuesta.context["form_egreso"].estadia.pk, self.estadia.pk)
        self.assertContains(respuesta, reverse("dispositivos:egresar", args=[self.cis.pk, self.estadia.pk]))


class FidelidadInfraestructuraTests(BaseInfraestructura):
    def setUp(self):
        reloj = patch("django.utils.timezone.now", return_value=AHORA)
        reloj.start()
        self.addCleanup(reloj.stop)
        super().setUp()

    def test_ubicacion_usa_coordenadas_del_edificio_y_acepta_cero(self):
        self.predio.latitud = Decimal("0")
        self.predio.longitud = Decimal("-58.986340")
        self.predio.save()
        respuesta = self._detalle(self.operador_geriatrico, self.geriatrico)
        panel = _panel(respuesta.content.decode())
        self.assertIn("https://www.openstreetmap.org/?mlat=0.000000&amp;mlon=-58.986340", panel)
        self.assertIn('rel="noopener noreferrer"', panel)
        self.assertNotIn("Plano", panel)

    def test_coordenadas_incompletas_sin_enlace_ni_coordenadas_inventadas(self):
        self.predio.latitud = Decimal("-27.451120")
        self.predio.save()
        panel = _panel(self._detalle(self.operador_geriatrico, self.geriatrico).content.decode())
        self.assertIn("Sin ubicación cargada", panel)
        self.assertNotIn("Ver en el mapa", panel)

    def test_predio_muestra_solo_instituciones_en_alcance_y_no_inventa_sector(self):
        respuesta = self._detalle(self.operador_geriatrico, self.geriatrico)
        panel = _panel(respuesta.content.decode())
        self.assertIn("Institución en este predio", panel)
        self.assertIn(self.geriatrico.nombre, panel)
        self.assertIn(reverse("dispositivos:detalle", args=[self.geriatrico.pk]), panel)
        self.assertNotIn(self.parador.nombre, panel)
        self.assertNotIn(reverse("dispositivos:detalle", args=[self.parador.pk]), panel)
        self.assertNotIn("Sector que ocupa", panel)
        admin = _panel(self._detalle(self.admin, self.geriatrico).content.decode())
        self.assertIn(self.parador.nombre, admin)
        self.assertIn(reverse("dispositivos:detalle", args=[self.parador.pk]), admin)
        self.assertIn("Activo", admin)

    def test_asignacion_en_rol_sin_ver_no_suma_alcance_para_identidad_del_predio(self):
        rol = Group.objects.create(name="Asignado sin ver")
        RolMeta.objects.create(grupo=rol, categoria="Programa", programa=self.programa, activo=True)
        rol.permissions.add(_permiso("dispositivo.admitir"))
        self.operador_geriatrico.groups.add(rol)
        AsignacionDispositivo.objects.create(rol=rol, dispositivo=self.parador)
        panel = _panel(self._detalle(self.operador_geriatrico, self.geriatrico).content.decode())
        self.assertNotIn(self.parador.nombre, panel)

    def test_selector_sin_usuario_no_devuelve_identidades_ni_consulta(self):
        with self.assertNumQueries(0):
            self.assertEqual(instituciones_del_predio(None, [self.predio.pk]), {})

    def test_estado_fuera_del_catalogo_conserva_el_valor_y_no_rompe_p4(self):
        type(self.parador).objects.filter(pk=self.parador.pk).update(estado="DESCONOCIDO")
        respuesta = self._detalle(self.admin, self.geriatrico)
        self.assertEqual(respuesta.status_code, 200)
        instituciones = respuesta.context["infraestructura"]["edificios"][0]["instituciones"]
        fila = next(fila for fila in instituciones if fila["pk"] == self.parador.pk)
        self.assertEqual(fila["get_estado_display"], "DESCONOCIDO")

    def test_relevamiento_en_curso_conserva_fecha_de_carga_en_las_fotos(self):
        """Decisión PM G3: mientras no hay realización, se muestra la fecha de la foto."""
        from programas.services.inspecciones import agregar_foto
        from programas.tests.test_dispositivos_inspecciones import _foto

        inspeccion = self._crear()
        foto = agregar_foto(self._fresco(self.agente), inspeccion, archivo=_foto(), descripcion="fachada")
        respuesta = self._detalle(self.operador_geriatrico, self.geriatrico)
        [evento] = respuesta.context["infraestructura"]["eventos"]
        self.assertEqual(evento["fotos"][0]["fecha"], foto.creado)
        self.assertIn('datetime="2026-10-14"', _panel(respuesta.content.decode()))

    def test_fotos_rotulan_fecha_del_relevamiento_y_no_fecha_de_subida(self):
        inspeccion = self._relevar(self.predio, Criticidad.MEDIA, fotos=("fachada",), dias_atras=30)
        respuesta = self._detalle(self.operador_geriatrico, self.geriatrico)
        [evento] = respuesta.context["infraestructura"]["eventos"]
        self.assertEqual(evento["fotos"][0]["fecha"], inspeccion.realizada_en)
        panel = _panel(respuesta.content.decode())
        self.assertNotIn('datetime="2026-10-14"', panel)


@tag("performance")
class FidelidadPresupuestoTests(BaseInfraestructura):
    def setUp(self):
        reloj = patch("django.utils.timezone.now", return_value=AHORA)
        reloj.start()
        self.addCleanup(reloj.stop)
        super().setUp()

    def test_instituciones_del_predio_cuesta_una_consulta_independiente_del_volumen(self):
        usuario = self._fresco(self.admin)
        list(dispositivos_visibles(usuario))  # calienta solo la autorización, no las filas del selector
        with CaptureQueriesContext(connection) as pocas:
            instituciones_del_predio(usuario, [self.predio.pk])
        for n in range(20):
            self.predio.dispositivos.add(self._dispositivo(f"PERF-{n}", f"Institución {n}"))
        with CaptureQueriesContext(connection) as muchas:
            filas = instituciones_del_predio(usuario, [self.predio.pk])
        self.assertEqual(len(filas[self.predio.pk]), 22)
        self.assertEqual(len(muchas), len(pocas))
        techo = json.loads((settings.BASE_DIR / "scripts/perf_budgets.json").read_text(encoding="utf-8"))["servicios"][
            "dispositivos_predio_instituciones"
        ]["consultas_fijas"]
        self.assertLessEqual(len(muchas), techo)
