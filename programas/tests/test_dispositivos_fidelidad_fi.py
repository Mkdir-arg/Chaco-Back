"""P3 con asistencia lateral y vencimiento edilicio compartido por P2/P4."""

import json
import re
import shutil
import subprocess
from datetime import timedelta
from unittest import skipUnless
from unittest.mock import patch

from django.conf import settings
from django.contrib.messages import get_messages
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
from programas.tests.test_dispositivos_horarios_localidad import catalogo_chaco
from programas.tests.test_dispositivos_infraestructura import BaseInfraestructura
from programas.tests.test_dispositivos_legajo import area_de_prueba


class FidelidadFITests(BaseInfraestructura):
    def setUp(self):
        reloj = patch("django.utils.timezone.now", return_value=AHORA)
        reloj.start()
        self.addCleanup(reloj.stop)
        super().setUp()
        catalogo_chaco()
        self.client.force_login(self.admin)
        self.crear = reverse("dispositivos:crear")
        self.cis.estado = Dispositivo.Estado.BORRADOR
        self.cis.save()
        self.editar = reverse("dispositivos:editar", args=[self.cis.pk])
        self.datos = {
            "tipo": self.tipo.pk,
            "codigo": "FI-NUEVO",
            "nombre": "Institución FI",
            "categoria": Dispositivo.Categoria.PRIVADO,
            "area_ministerio": area_de_prueba().pk,
            "localidad": "Resistencia",
            "domicilio": "Calle 123",
            "responsable_nombre": "Responsable FI",
            "contacto_telefono": "3624123456",
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

    def test_el_asterisco_marca_lo_que_hace_falta_para_validar_y_lo_dice_la_bajada(self):
        """Mockup #p3: el `*` marca los requisitos de **enviar a validación**, no los de guardar.

        Domicilio, Responsable institucional y Teléfono no son obligatorios para guardar
        —el borrador se guarda incompleto— y el mockup los marca igual, porque sin ellos
        no se puede enviar. Se aplica con el mecanismo de `components/_field.html`
        (`marca_requerido`), sin tocar `required`: la validación no cambia.
        """

        form = DispositivoForm()
        requeridos = {nombre for nombre, campo in form.fields.items() if getattr(campo, "marca_requerido", False)}

        self.assertEqual(requeridos, set(campos_para_validacion()))
        # Y ninguno de los tres que el mockup agrega pasó a ser obligatorio para guardar.
        for nombre in ("domicilio", "responsable_nombre", "contacto_telefono"):
            self.assertFalse(form.fields[nombre].required, nombre)

        html = self.client.get(self.crear).content.decode()
        for nombre in campos_para_validacion():
            etiqueta = form[nombre].label
            self.assertIn(
                f'{etiqueta} <span class="text-fg-danger">*</span>',
                html,
                f"{nombre} tendría que llevar el asterisco",
            )
        # Latitud no es requisito de validación: no lo lleva.
        self.assertNotIn('Latitud <span class="text-fg-danger">*</span>', html)
        self.assertIn(
            'Para enviar a validación hacen falta los campos marcados con <span class="text-fg-danger">*</span>.',
            html,
        )

    def test_p3_dibuja_categoria_area_titularidad_y_dependencia_despues_de_nombre(self):
        """Mockup #p3: los cuatro selectores van en «Identidad y encuadre», después de Nombre."""
        for url in (self.crear, self.editar):
            with self.subTest(url=url):
                html = self.client.get(url).content.decode()
                orden = [
                    html.index(f'name="{nombre}"')
                    for nombre in (
                        "nombre",
                        "categoria",
                        "area_ministerio",
                        "titularidad_inmueble",
                        "dependencia_gestion",
                    )
                ]
                self.assertEqual(orden, sorted(orden))
                # Todo el encuadre queda antes de la tarjeta de Ubicación.
                self.assertLess(orden[-1], html.index('name="localidad"'))
                for nombre in ("categoria", "area_ministerio", "titularidad_inmueble", "dependencia_gestion"):
                    self.assertRegex(html, rf'<select[^>]*name="{nombre}"')
                self.assertContains(self.client.get(url), "Público / Estatal")
                self.assertContains(self.client.get(url), "Particular (alquiler o préstamo)")

    def test_categoria_y_area_llevan_asterisco_y_titularidad_y_dependencia_no(self):
        html = self.client.get(self.crear).content.decode()
        self.assertIn('Categoría <span class="text-fg-danger">*</span>', html)
        self.assertIn('Área del Ministerio <span class="text-fg-danger">*</span>', html)
        self.assertNotIn('Titularidad del inmueble <span class="text-fg-danger">*</span>', html)
        self.assertNotIn('Dependencia de la gestión <span class="text-fg-danger">*</span>', html)

    def test_guardar_conserva_los_cuatro_valores_de_encuadre(self):
        area = area_de_prueba()
        datos = {
            **self.datos,
            "categoria": Dispositivo.Categoria.RELIGIOSO,
            "area_ministerio": area.pk,
            "titularidad_inmueble": Dispositivo.TitularidadInmueble.PARTICULAR,
            "dependencia_gestion": Dispositivo.DependenciaGestion.ONG,
        }
        self.assertEqual(self.client.post(self.crear, datos).status_code, 302)
        dispositivo = Dispositivo.objects.get(codigo=self.datos["codigo"])
        self.assertEqual(dispositivo.categoria, "RELIGIOSO")
        self.assertEqual(dispositivo.area_ministerio, area)
        self.assertEqual(dispositivo.titularidad_inmueble, "PARTICULAR")
        self.assertEqual(dispositivo.dependencia_gestion, "ONG")

        respuesta = self.client.post(self.editar, {**datos, "categoria": "PRIVADO", "dependencia_gestion": ""})
        self.assertEqual(respuesta.status_code, 302)
        self.cis.refresh_from_db()
        self.assertEqual(self.cis.categoria, "PRIVADO")
        self.assertIsNone(self.cis.dependencia_gestion)

    def test_valores_fuera_de_catalogo_se_rechazan(self):
        respuesta = self.client.post(self.crear, {**self.datos, "categoria": "INVENTADA", "area_ministerio": 999999})
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Dispositivo.objects.filter(codigo=self.datos["codigo"]).exists())

    def test_borrador_sin_encuadre_se_guarda_pero_no_se_envia(self):
        sin_encuadre = {**self.datos, "categoria": "", "area_ministerio": ""}
        respuesta = self.client.post(self.crear, sin_encuadre)
        self.assertEqual(respuesta.status_code, 302)
        dispositivo = Dispositivo.objects.get(codigo=self.datos["codigo"])
        self.assertEqual(dispositivo.estado, Dispositivo.Estado.BORRADOR)
        self.assertFalse(dispositivo.categoria)
        self.assertIsNone(dispositivo.area_ministerio)

        for faltante in ("categoria", "area_ministerio"):
            with self.subTest(faltante=faltante):
                datos = {**self.datos, faltante: "", "accion": "enviar_validacion", "codigo": f"FI-{faltante}"}
                respuesta = self.client.post(self.crear, datos)
                self.assertContains(respuesta, "Completá los campos obligatorios")
                self.assertContains(respuesta, f'data-requisito-campo="id_{faltante}"')
                self.assertFalse(Dispositivo.objects.filter(codigo=f"FI-{faltante}").exists())

    def test_el_area_ofrece_las_activas_y_conserva_la_guardada_aunque_este_inactiva(self):
        activa = area_de_prueba()
        inactiva = area_de_prueba("Subsecretaría dada de baja", activo=False)
        self.assertEqual(list(DispositivoForm().fields["area_ministerio"].queryset), [activa])

        self.cis.area_ministerio = inactiva
        self.cis.save()
        opciones = DispositivoForm(instance=self.cis).fields["area_ministerio"].queryset
        self.assertCountEqual(opciones, [activa, inactiva])

    def test_p4_muestra_el_encuadre_y_un_guion_si_falta(self):
        detalle = reverse("dispositivos:detalle", args=[self.cis.pk])
        vacio = self.client.get(detalle).content.decode()
        for rotulo in ("Categoría", "Área del Ministerio", "Titularidad del inmueble", "Dependencia de la gestión"):
            self.assertRegex(vacio, rf"{rotulo}</dt><dd[^>]*>—</dd>")

        area = area_de_prueba()
        Dispositivo.objects.filter(pk=self.cis.pk).update(
            categoria="ONG",
            area_ministerio=area,
            titularidad_inmueble="MUNICIPIO",
            dependencia_gestion="RELIGIOSA",
        )
        respuesta = self.client.get(detalle)
        self.assertContains(respuesta, "ONG</dd>")
        self.assertContains(respuesta, str(area))
        self.assertContains(respuesta, "Municipio</dd>")
        self.assertContains(respuesta, "Iglesia o congregación religiosa</dd>")

    def test_guardar_borrador_sigue_admitiendo_datos_operativos_faltantes(self):
        respuesta = self.client.post(self.crear, {**self.datos, "responsable_nombre": "", "localidad": ""})
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(Dispositivo.objects.get(codigo=self.datos["codigo"]).estado, Dispositivo.Estado.BORRADOR)

    def test_editar_sin_enviar_conserva_el_mensaje_de_actualizacion(self):
        respuesta = self.client.post(self.editar, self.datos)
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual([str(m) for m in get_messages(respuesta.wsgi_request)], ["Dispositivo actualizado."])

    def test_contador_solo_en_alta_y_envio_habilitado_sin_javascript(self):
        alta = self.client.get(self.crear)
        self.assertContains(
            alta, 'id="duplicate-count" class="badge badge-warning" aria-label="Coincidencias">0</span>'
        )
        self.assertNotContains(self.client.get(self.editar), 'id="duplicate-count"')
        for url in (self.crear, self.editar):
            html = self.client.get(url).content.decode()
            boton = re.search(r'<button[^>]*name="accion"[^>]*>', html).group()
            self.assertNotIn("disabled", boton)
        self.assertContains(alta, 'id="duplicate-search" class="hidden" tabindex="-1"')

    def test_enviar_desde_alta_y_edicion_guarda_y_transiciona_con_traza(self):
        for url, codigo in ((self.crear, "FI-NUEVO"), (self.editar, self.cis.codigo)):
            with self.subTest(url=url):
                self.client.get(url)  # Consume los mensajes del POST anterior, como el navegador.
                respuesta = self.client.post(url, {**self.datos, "codigo": codigo, "accion": "enviar_validacion"})
                self.assertEqual(respuesta.status_code, 302)
                self.assertEqual(
                    [str(m) for m in get_messages(respuesta.wsgi_request)], ["Dispositivo enviado a validación."]
                )
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

    def test_creador_sin_alcance_de_admin_no_entra_al_alta_y_sigue_editando_lo_suyo(self):
        """El alta queda para quien administra el programa (decisión del PM).

        Este usuario tiene `dispositivo.crear`, `editar` y `ver` y está asignado al CIS,
        pero no tiene alcance total: la institución que diera de alta no tendría ninguna
        asignación, así que guardaba el borrador y el redirect a su propio legajo le
        respondía 403, con la institución ya escrita. Ahora las dos puertas del alta
        responden 403 sin crear nada, y lo que sí puede —editar el CIS que tiene
        asignado, y enviarlo a validación— no cambia.
        """

        usuario = self._usuario(
            "creador_fi", ("dispositivo.crear", "dispositivo.editar", "dispositivo.ver"), [self.cis]
        )
        self.client.force_login(usuario)

        self.assertEqual(self.client.get(self.crear).status_code, 403)
        self.assertEqual(self.client.post(self.crear, {**self.datos, "accion": "enviar_validacion"}).status_code, 403)
        self.assertEqual(self.client.post(self.crear, self.datos).status_code, 403)
        self.assertFalse(Dispositivo.objects.filter(codigo="FI-NUEVO").exists())
        self.assertEqual(
            self.client.get(reverse("dispositivos:buscar_duplicados"), {"codigo": "FI-NUEVO"}).status_code, 403
        )
        self.assertContains(self.client.get(self.editar), 'name="accion"')

    def test_con_alcance_de_admin_el_alta_sigue_abierta(self):
        """El otro perfil: mismas capacidades más el alcance de admin del programa."""

        usuario = self._usuario(
            "creador_admin_fi",
            ("dispositivo.crear", "dispositivo.editar", "dispositivo.ver", "programa.configurar"),
        )
        self.client.force_login(usuario)

        self.assertEqual(self.client.get(self.crear).status_code, 200)
        self.assertEqual(self.client.post(self.crear, self.datos).status_code, 302)
        creada = Dispositivo.objects.get(codigo="FI-NUEVO")
        # Y entra a su propio legajo, que es lo que el perfil de arriba no podía.
        self.assertEqual(self.client.get(reverse("dispositivos:detalle", args=[creada.pk])).status_code, 200)

    def test_codigo_repetido_bloquea_aunque_la_coincidencia_este_fuera_del_alcance(self):
        # Alta sí, lectura no: sin `dispositivo.ver` la respuesta no nombra ninguna
        # institución, pero el código sigue estando tomado y el alta igual se rechaza.
        usuario = self._usuario("creador_fuera_fi", ("dispositivo.crear", "programa.configurar"), [self.cis])
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
            encoding="utf-8",
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
            encoding="utf-8",
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

    def test_critico_prevalece_sobre_vencido_y_sin_relevar_en_otro_edificio(self):
        """Decisión PM (G3): la última realizada Alta conserva Crítico aun con vencidos."""
        self._relevar(self.predio, InspeccionEdificio.Criticidad.ALTA)
        self.edificio_cis.dispositivos.add(self.parador)
        inspeccion = self._crear()
        InspeccionEdificio.objects.filter(pk=inspeccion.pk).update(fecha_vencimiento=AHORA.date() - timedelta(days=1))
        self.assertEqual(semaforos_de_dispositivos([self.parador.pk])[self.parador.pk].texto, "Crítico")
        self.assertEqual(infraestructura_del_dispositivo(self.parador)["semaforo"].texto, "Crítico")

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
