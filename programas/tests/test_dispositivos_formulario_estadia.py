"""Formularios de «Ingreso» y «Egreso» del tipo de dispositivo (P17, PR 1 y 2 de los momentos de la estadía).

Cubre el paso Confirmar del asistente de ingreso (P6) con y sin formulario, la validación que
frena antes de escribir, la transacción única con la estadía, los archivos y su regla de
`/media/`, el servicio de egreso y el formulario en el modal de egreso (P7 y P4), la baja lógica del formulario con
respuestas y la lectura en el detalle de la estadía (P7). El presupuesto va con `@tag("performance")`.
"""

import json
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import tag
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from programas.models import (
    AdjuntoRespuestaEgreso,
    AdjuntoRespuestaIngreso,
    DisenoFormulario,
    Estadia,
    ItemDiseno,
    MomentoFormulario,
    MotivoEgreso,
    RespuestasEgresoEstadia,
    RespuestasIngresoEstadia,
)
from programas.services import constructor
from programas.services.estadias import ingresar_persona
from programas.services.formularios_tipo import crear_formulario, puede_eliminar_formulario
from programas.services.respuestas_dispositivo import (
    formularios_de_estadia,
    foto_vigente,
    guardar_respuestas_egreso,
    guardar_respuestas_ingreso,
    tiene_respuestas,
)
from programas.tests.test_dispositivos_ingreso import BaseIngreso

PDF = b"%PDF-1.4\n%prueba\n"
User = get_user_model()


def _presupuesto(nombre):
    presupuestos = json.loads(
        (Path(__file__).resolve().parents[2] / "scripts/perf_budgets.json").read_text(encoding="utf-8")
    )
    return presupuestos["servicios"][nombre]["consultas_fijas"]


def _pdf(nombre="constancia.pdf"):
    return SimpleUploadedFile(nombre, PDF, content_type="application/pdf")


class _Base(BaseIngreso):
    """El tipo con su formulario de INGRESO: camas (número, obligatorio), observaciones (texto) y una
    constancia (archivo, opcional)."""

    momento = MomentoFormulario.INGRESO

    def setUp(self):
        super().setUp()
        import tempfile

        from django.test import override_settings

        media = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(media.cleanup)
        contexto = override_settings(MEDIA_ROOT=media.name)
        contexto.enable()
        self.addCleanup(contexto.disable)
        self.admin = User.objects.create_superuser("admin_formulario_estadia", password="x")
        self.diseno = self._formulario(self.momento)

    # ── helpers ──
    def _mutar(self, diseno, operacion):
        constructor.mutar(diseno, self.admin, operacion)
        diseno.refresh_from_db()

    def _formulario(self, momento):
        diseno = crear_formulario(self.tipo, momento, self.admin)
        self._mutar(
            diseno,
            lambda: constructor.crear_grupo(
                diseno, {"etiqueta": "Datos del ingreso", "subtitulo": "", "canal": "ambos"}
            ),
        )
        grupo = diseno.items.get(tipo=ItemDiseno.Tipo.GRUPO)
        for texto, tipo, obligatorio in (
            ("Cantidad de pertenencias", "INT", True),
            ("Observaciones", "STRING", False),
            ("Constancia", "ARCHIVO", False),
        ):
            propio = {
                "texto": texto,
                "tipo": tipo,
                "opciones": [],
                "presentacion": "LISTA",
                "obligatorio": obligatorio,
            }
            self._mutar(diseno, lambda: constructor.crear_propio(diseno, grupo, {"propio": propio, "canal": "ambos"}))
        return diseno

    def _item(self, texto, diseno=None):
        return (diseno or self.diseno).items.get(tipo=ItemDiseno.Tipo.CAMPO, propio__texto=texto)

    def _nombre(self, texto, diseno=None):
        return f"formulario-{self._item(texto, diseno).clave}"

    def _completo(self, **extra):
        datos = {
            self._nombre("Cantidad de pertenencias"): "3",
            self._nombre("Observaciones"): "Llega con mochila",
            self._nombre("Constancia"): _pdf(),
        }
        datos.update(extra)
        return datos

    def _ir_a_confirmar(self):
        self._hasta_la_plaza(self.persona, self.plaza)

    def _carpeta_de_archivos(self):
        carpeta = Path(settings.MEDIA_ROOT) / "dispositivos" / "estadias"
        return [p for p in carpeta.rglob("*") if p.is_file()]


# ── P6: sin formulario el asistente queda como hoy ───────────────────────────


class SinFormularioTests(BaseIngreso):
    def test_sin_formulario_el_paso_final_no_cambia_y_cuesta_una_consulta_mas(self):
        self._hasta_la_plaza(self.persona, self.plaza)

        with CaptureQueriesContext(connection) as con_busqueda:
            pagina = self.client.get(self.url_confirmar)
        with patch("programas.views.dispositivos_ingreso.formulario_de_momento_para", return_value=None):
            with CaptureQueriesContext(connection) as sin_busqueda:
                self.client.get(self.url_confirmar)

        self.assertNotContains(pagina, "multipart/form-data")
        self.assertNotContains(pagina, "Formulario de ingreso")
        # La única consulta nueva es averiguar si el tipo pide un formulario vigente.
        self.assertEqual(len(con_busqueda), len(sin_busqueda) + 1)

        respuesta = self._confirmar()
        self.assertRedirects(respuesta, reverse("dispositivos:detalle", args=[self.cis.pk]))
        self.assertEqual(Estadia.objects.get(ciudadano=self.persona).plaza, self.plaza)
        self.assertFalse(RespuestasIngresoEstadia.objects.exists())


# ── P6: con formulario ───────────────────────────────────────────────────────


class IngresoConFormularioTests(_Base):
    def test_el_paso_final_pide_el_formulario_en_su_tarjeta_y_manda_archivos(self):
        self._ir_a_confirmar()

        pagina = self.client.get(self.url_confirmar)

        self.assertContains(pagina, 'enctype="multipart/form-data"')
        self.assertContains(pagina, "Formulario de ingreso")
        self.assertContains(pagina, "Cantidad de pertenencias")
        self.assertContains(pagina, "Los campos con * son obligatorios para confirmar el ingreso.")

    def test_se_guarda_con_la_foto_y_la_version_en_la_misma_transaccion_que_el_ingreso(self):
        self._ir_a_confirmar()

        respuesta = self._confirmar(self._completo())

        self.assertRedirects(
            respuesta, reverse("dispositivos:detalle", args=[self.cis.pk]), fetch_redirect_response=False
        )
        estadia = Estadia.objects.get(ciudadano=self.persona)
        fila = RespuestasIngresoEstadia.objects.get(estadia=estadia)
        self.assertEqual(fila.diseno, self.diseno)
        self.assertEqual(fila.version, self.diseno.version)
        self.assertEqual(fila.definicion["version"], self.diseno.version)
        self.assertEqual(fila.definicion, foto_vigente(self.diseno))
        self.assertEqual(fila.respuestas[self._item("Cantidad de pertenencias").clave], 3)
        self.assertEqual(fila.actualizado_por, self.operador_cis)
        adjunto = AdjuntoRespuestaIngreso.objects.get(respuestas=fila)
        self.assertEqual(adjunto.clave, self._item("Constancia").clave)
        self.assertTrue(adjunto.archivo.name.startswith("dispositivos/estadias/formularios/"))
        self.assertNotIn("constancia", adjunto.archivo.name)

    def test_un_obligatorio_vacio_bloquea_y_no_se_escribe_nada(self):
        """Mutación: sin `faltantes()` en `IngresoConfirmarView.post` este test se pone rojo."""
        self._ir_a_confirmar()

        respuesta = self._confirmar(self._completo(**{self._nombre("Cantidad de pertenencias"): ""}))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Este dato es obligatorio.")
        self.assertFalse(Estadia.objects.filter(ciudadano=self.persona).exists())
        self.assertFalse(RespuestasIngresoEstadia.objects.exists())
        self.assertFalse(AdjuntoRespuestaIngreso.objects.exists())
        self.assertEqual(self._carpeta_de_archivos(), [])
        # La plaza sigue libre: se puede alojar a otra persona en ella.
        ingresar_persona(ciudadano=self.otra_persona, dispositivo=self.cis, usuario=self.operador_cis, plaza=self.plaza)
        # Y lo no-archivo que se escribió vuelve en la pantalla del error.
        self.assertContains(respuesta, "Llega con mochila")

    def test_un_valor_mal_escrito_tambien_frena(self):
        self._ir_a_confirmar()

        respuesta = self._confirmar(self._completo(**{self._nombre("Cantidad de pertenencias"): "muchas"}))

        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Estadia.objects.filter(ciudadano=self.persona).exists())

    def test_si_guardar_las_respuestas_explota_no_queda_la_estadia_ni_el_archivo(self):
        self._ir_a_confirmar()
        real = guardar_respuestas_ingreso

        def explota_despues(*args, **kwargs):
            real(*args, **kwargs)  # escribe la fila y el archivo…
            raise RuntimeError("falla el guardado")

        with patch("programas.views.dispositivos_ingreso.guardar_respuestas_ingreso", side_effect=explota_despues):
            with self.assertRaises(RuntimeError):
                self._confirmar(self._completo())

        self.assertFalse(Estadia.objects.filter(ciudadano=self.persona).exists())
        self.assertFalse(RespuestasIngresoEstadia.objects.exists())
        self.assertEqual(self._carpeta_de_archivos(), [])
        self.assertFalse(Estadia.objects.filter(plaza=self.plaza).exists())

    def test_si_la_plaza_se_pierde_lo_no_archivo_vuelve_precargado_y_el_archivo_se_vuelve_a_elegir(self):
        self._ir_a_confirmar()
        ingresar_persona(ciudadano=self.otra_persona, dispositivo=self.cis, usuario=self.operador_cis, plaza=self.plaza)

        respuesta = self._confirmar(self._completo())

        self.assertRedirects(respuesta, self.url_plaza, fetch_redirect_response=False)
        self.assertFalse(RespuestasIngresoEstadia.objects.exists())
        self.assertEqual(self._carpeta_de_archivos(), [])
        self._elegir_plaza(self.otra_plaza)
        pagina = self.client.get(self.url_confirmar)
        self.assertContains(pagina, "Llega con mochila")
        self.assertNotContains(pagina, "constancia.pdf")

    def test_un_formulario_dado_de_baja_no_se_pide(self):
        DisenoFormulario.objects.filter(pk=self.diseno.pk).update(dado_de_baja_en=timezone.now())
        self._ir_a_confirmar()

        pagina = self.client.get(self.url_confirmar)
        self.assertNotContains(pagina, "multipart/form-data")

        self._confirmar()
        self.assertTrue(Estadia.objects.filter(ciudadano=self.persona).exists())
        self.assertFalse(RespuestasIngresoEstadia.objects.exists())


# ── /media/ ──────────────────────────────────────────────────────────────────


class MediaTests(_Base):
    def test_el_adjunto_lo_baja_quien_ve_el_dispositivo_con_ciudadano_ver_y_el_resto_es_404(self):
        """Mutación: sin la comprobación de `ciudadano.ver` o sin el alcance en `_archivo_de_formulario_estadia`
        alguno de los 404 de abajo pasa a 200."""
        self._ir_a_confirmar()
        self._confirmar(self._completo())
        url = AdjuntoRespuestaIngreso.objects.get().archivo.url

        self.assertEqual(self.client.get(url).status_code, 200)
        # Un archivo que no existe, el mismo 404.
        self.assertEqual(self.client.get(url.replace(".pdf", "x.pdf")).status_code, 404)
        # Con alcance sobre el dispositivo pero sin ciudadano.ver.
        sin_ciudadano = self._operador("Solo dispositivo", self.cis, ("dispositivo.ver",))
        self.client.force_login(sin_ciudadano)
        self.assertEqual(self.client.get(url).status_code, 404)
        # Con ciudadano.ver pero sin alcance sobre ese dispositivo.
        ajeno = self._operador("Ajeno", self.parador, ("dispositivo.ver", "ciudadano.ver"))
        self.client.force_login(ajeno)
        self.assertEqual(self.client.get(url).status_code, 404)


# ── Servicio de egreso (la UI es el PR 2) y baja lógica ──────────────────────


class EgresoYBajaTests(_Base):
    def setUp(self):
        super().setUp()
        self.estadia = ingresar_persona(
            ciudadano=self.persona, dispositivo=self.cis, usuario=self.operador_cis, plaza=self.plaza
        )
        self.egreso = self._formulario(MomentoFormulario.EGRESO)

    def test_guardar_respuestas_egreso_guarda_foto_version_y_adjunto(self):
        fila = guardar_respuestas_egreso(
            self.estadia,
            self.egreso,
            foto_vigente(self.egreso),
            {self._item("Observaciones", self.egreso).clave: "Se va con familiares"},
            [(self._item("Constancia", self.egreso).clave, _pdf())],
            self.operador_cis,
        )

        self.assertEqual(fila.version, self.egreso.version)
        self.assertEqual(fila.definicion, foto_vigente(self.egreso))
        self.assertEqual(RespuestasEgresoEstadia.objects.get().estadia, self.estadia)
        adjunto = AdjuntoRespuestaEgreso.objects.get()
        self.assertTrue(adjunto.archivo.name.startswith("dispositivos/estadias/formularios/"))
        self.assertFalse(RespuestasIngresoEstadia.objects.exists())

    def test_sin_nada_respondido_no_se_crea_fila(self):
        self.assertIsNone(
            guardar_respuestas_ingreso(self.estadia, self.diseno, foto_vigente(self.diseno), {}, (), None)
        )
        self.assertFalse(RespuestasIngresoEstadia.objects.exists())
        self.assertFalse(tiene_respuestas(self.diseno))
        self.assertTrue(puede_eliminar_formulario(self.diseno))

    def test_con_respuestas_de_ingreso_o_de_egreso_el_formulario_no_se_borra(self):
        guardar_respuestas_ingreso(
            self.estadia,
            self.diseno,
            foto_vigente(self.diseno),
            {self._item("Observaciones").clave: "Hola"},
            (),
            None,
        )
        guardar_respuestas_egreso(
            self.estadia,
            self.egreso,
            foto_vigente(self.egreso),
            {self._item("Observaciones", self.egreso).clave: "Chau"},
            (),
            None,
        )

        self.assertTrue(tiene_respuestas(self.diseno))
        self.assertTrue(tiene_respuestas(self.egreso))
        self.assertFalse(puede_eliminar_formulario(self.diseno))
        self.assertFalse(puede_eliminar_formulario(self.egreso))

    def test_la_unicidad_es_por_estadia_y_formulario(self):
        for _ in range(2):
            guardar_respuestas_ingreso(
                self.estadia,
                self.diseno,
                foto_vigente(self.diseno),
                {self._item("Observaciones").clave: "Otra vez"},
                (),
                None,
            )
        self.assertEqual(RespuestasIngresoEstadia.objects.count(), 1)


# ── P7 ───────────────────────────────────────────────────────────────────────


class DetalleDeEstadiaTests(_Base):
    def setUp(self):
        super().setUp()
        self.estadia = ingresar_persona(
            ciudadano=self.persona, dispositivo=self.cis, usuario=self.operador_cis, plaza=self.plaza
        )
        self.egreso = self._formulario(MomentoFormulario.EGRESO)
        self.url = reverse("dispositivos:estadia_detalle", args=[self.cis.pk, self.estadia.pk])

    def _responder(self):
        guardar_respuestas_ingreso(
            self.estadia,
            self.diseno,
            foto_vigente(self.diseno),
            {self._item("Observaciones").clave: "Llega con mochila"},
            [(self._item("Constancia").clave, _pdf())],
            self.operador_cis,
        )
        guardar_respuestas_egreso(
            self.estadia,
            self.egreso,
            foto_vigente(self.egreso),
            {self._item("Observaciones", self.egreso).clave: "Se va con familiares"},
            (),
            self.operador_cis,
        )

    def test_sin_respuestas_las_secciones_no_aparecen(self):
        pagina = self.client.get(self.url)
        self.assertEqual(pagina.status_code, 200)
        # La tarjeta del modal de egreso también se llama «Formulario de egreso»: se mira el id de la sección.
        self.assertNotContains(pagina, 'id="formulario-estadia-')

    def test_con_respuestas_muestra_las_dos_secciones_y_el_enlace_al_archivo(self):
        self._responder()

        pagina = self.client.get(self.url)

        self.assertContains(pagina, 'id="formulario-estadia-1"')
        self.assertContains(pagina, 'id="formulario-estadia-2"')
        self.assertContains(pagina, "Formulario de ingreso")
        self.assertContains(pagina, "Llega con mochila")
        self.assertContains(pagina, "Se va con familiares")
        self.assertContains(pagina, AdjuntoRespuestaIngreso.objects.get().archivo.url)
        self.assertEqual(self.client.get(AdjuntoRespuestaIngreso.objects.get().archivo.url).status_code, 200)

    def test_sin_ciudadano_ver_no_se_ve_y_sin_alcance_tampoco(self):
        self._responder()
        sin_ciudadano = self._operador("Solo dispositivo", self.cis, ("dispositivo.ver",))
        self.client.force_login(sin_ciudadano)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        ajeno = self._operador("Ajeno", self.parador, ("dispositivo.ver", "ciudadano.ver"))
        self.client.force_login(ajeno)
        self.assertEqual(self.client.get(self.url).status_code, 404)

    @tag("performance")
    def test_la_lectura_de_p7_tiene_presupuesto_fijo(self):
        self._responder()
        estadia = Estadia.objects.get(pk=self.estadia.pk)

        with CaptureQueriesContext(connection) as consultas:
            entradas = formularios_de_estadia(estadia)

        self.assertEqual([e["titulo"] for e in entradas], ["Formulario de ingreso", "Formulario de egreso"])
        self.assertEqual(len(consultas), _presupuesto("dispositivos_formularios_de_estadia"))


# ── PR 2: el formulario de egreso dentro del modal ───────────────────────────


class EgresoConFormularioTests(_Base):
    """`EstadiaEgresarView` con el formulario de «Egreso» del tipo (P4 y P7 mandan este mismo POST)."""

    def setUp(self):
        super().setUp()
        self.estadia = ingresar_persona(
            ciudadano=self.persona, dispositivo=self.cis, usuario=self.operador_cis, plaza=self.plaza
        )
        self.egreso = self._formulario(MomentoFormulario.EGRESO)
        self.motivo = MotivoEgreso.objects.create(codigo="alta-t", nombre="Alta de prueba", activo=True)
        self.url = reverse("dispositivos:egresar", args=[self.cis.pk, self.estadia.pk])
        self.url_p7 = reverse("dispositivos:estadia_detalle", args=[self.cis.pk, self.estadia.pk])
        self.url_p4 = f"{reverse('dispositivos:detalle', args=[self.cis.pk])}?tab=estadias&egreso={self.estadia.pk}"

    def _datos(self, **extra):
        datos = {
            "fecha_egreso": timezone.localtime().replace(second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M"),
            "motivo": self.motivo.pk,
            "destino": "Domicilio de familiar",
            "formulario_tipo_diseno": self.egreso.pk,
            "formulario_tipo_version": self.egreso.version,
            self._nombre("Cantidad de pertenencias", self.egreso): "2",
            self._nombre("Observaciones", self.egreso): "Se va con familiares",
            self._nombre("Constancia", self.egreso): _pdf(),
        }
        datos.update(extra)
        return datos

    def _post(self, datos):
        return self.client.post(self.url, datos, HTTP_X_REQUESTED_WITH="XMLHttpRequest")

    def _nada_escrito(self):
        self.estadia.refresh_from_db()
        self.assertEqual(self.estadia.estado, Estadia.Estado.ACTIVA)
        self.assertEqual(self.estadia.plaza_id, self.plaza.pk)
        self.assertFalse(RespuestasEgresoEstadia.objects.exists())
        self.assertFalse(AdjuntoRespuestaEgreso.objects.exists())
        self.assertEqual(self._carpeta_de_archivos(), [])

    def _con_ciudadano_ver(self):
        self.client.force_login(
            self._operador("Ve ciudadano", self.cis, ("dispositivo.ver", "dispositivo.egresar", "ciudadano.ver"))
        )

    def test_sin_formulario_vigente_el_egreso_es_el_de_siempre(self):
        self.egreso.dado_de_baja_en = timezone.now()
        self.egreso.save(update_fields=["dado_de_baja_en"])
        datos = {k: v for k, v in self._datos().items() if not k.startswith("formulario")}

        respuesta = self._post(datos)

        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        self.estadia.refresh_from_db()
        self.assertEqual(self.estadia.estado, Estadia.Estado.EGRESADA)
        self.assertFalse(RespuestasEgresoEstadia.objects.exists())

    def test_si_se_da_de_baja_con_el_modal_abierto_tambien_se_rechaza(self):
        datos = self._datos()
        self.egreso.dado_de_baja_en = timezone.now()
        self.egreso.save(update_fields=["dado_de_baja_en"])

        respuesta = self._post(datos)

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("__all__", respuesta.json()["errors"])
        self._nada_escrito()

    def test_con_formulario_se_guarda_con_la_foto_la_version_y_el_adjunto(self):
        respuesta = self._post(self._datos())

        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        self.estadia.refresh_from_db()
        self.assertEqual(self.estadia.estado, Estadia.Estado.EGRESADA)
        fila = RespuestasEgresoEstadia.objects.get()
        self.assertEqual(fila.estadia, self.estadia)
        self.assertEqual(fila.version, self.egreso.version)
        self.assertEqual(fila.definicion, foto_vigente(self.egreso))
        self.assertEqual(fila.respuestas[self._item("Cantidad de pertenencias", self.egreso).clave], 2)
        adjunto = AdjuntoRespuestaEgreso.objects.get()
        self.assertTrue(adjunto.archivo.name.startswith("dispositivos/estadias/formularios/"))
        self.assertFalse(RespuestasIngresoEstadia.objects.exists())

    def test_un_obligatorio_vacio_da_400_con_el_error_en_su_campo_y_no_se_escribe_nada(self):
        clave = self._item("Cantidad de pertenencias", self.egreso).clave

        respuesta = self._post(self._datos(**{self._nombre("Cantidad de pertenencias", self.egreso): ""}))

        self.assertEqual(respuesta.status_code, 400)
        errores = respuesta.json()["errors"]
        self.assertEqual(errores[clave], ["Este dato es obligatorio."])
        self.assertNotIn("__all__", errores)
        self._nada_escrito()

    def test_se_publica_el_formulario_con_el_modal_abierto_da_400_y_no_se_escribe_nada(self):
        datos = self._datos()  # lo que el modal dibujó: diseño y versión de antes
        self._mutar(
            self.egreso,
            lambda: constructor.crear_propio(
                self.egreso,
                self.egreso.items.get(tipo=ItemDiseno.Tipo.GRUPO),
                {
                    "propio": {
                        "texto": "Nuevo dato",
                        "tipo": "STRING",
                        "opciones": [],
                        "presentacion": "LISTA",
                        "obligatorio": False,
                    },
                    "canal": "ambos",
                },
            ),
        )

        respuesta = self._post(datos)

        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(
            respuesta.json()["errors"],
            {"__all__": ["El formulario de egreso cambió mientras estaba abierto: recargá la página y completalo."]},
        )
        self._nada_escrito()

    def test_los_errores_del_egreso_y_del_tipo_salen_juntos(self):
        clave = self._item("Cantidad de pertenencias", self.egreso).clave

        respuesta = self._post(self._datos(motivo="", **{self._nombre("Cantidad de pertenencias", self.egreso): ""}))

        self.assertEqual(respuesta.status_code, 400)
        errores = respuesta.json()["errors"]
        self.assertIn("motivo", errores)
        self.assertEqual(errores[clave], ["Este dato es obligatorio."])
        self._nada_escrito()

    def test_un_motivo_faltante_frena_aunque_el_formulario_este_completo(self):
        respuesta = self._post(self._datos(motivo=""))

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("motivo", respuesta.json()["errors"])
        self._nada_escrito()

    def test_si_guardar_las_respuestas_explota_la_estadia_sigue_activa(self):
        with patch("programas.views.dispositivos_legajo.guardar_respuestas_egreso", side_effect=RuntimeError("falla")):
            with self.assertRaises(RuntimeError):
                self._post(self._datos())

        self._nada_escrito()

    def test_si_falla_despues_de_escribir_el_archivo_se_borra(self):
        from programas.services import respuestas_dispositivo as servicio

        original = servicio.anotar_archivo_escrito

        def escribir_y_fallar(*args, **kwargs):
            original(*args, **kwargs)
            raise RuntimeError("falla")

        with patch.object(servicio, "anotar_archivo_escrito", side_effect=escribir_y_fallar):
            with self.assertRaises(RuntimeError):
                self._post(self._datos())

        self._nada_escrito()

    def test_un_formulario_dado_de_baja_no_se_pide_en_p7_ni_en_p4(self):
        self._con_ciudadano_ver()
        for url in (self.url_p7, self.url_p4):
            self.assertContains(self.client.get(url), "Formulario de egreso")
        self.egreso.dado_de_baja_en = timezone.now()
        self.egreso.save(update_fields=["dado_de_baja_en"])
        for url in (self.url_p7, self.url_p4):
            self.assertNotContains(self.client.get(url), "Formulario de egreso")

    def test_los_campos_llegan_dentro_del_modal_de_p4_y_de_p7_con_su_data_error(self):
        clave = self._item("Cantidad de pertenencias", self.egreso).clave
        self._con_ciudadano_ver()
        for url in (self.url_p7, self.url_p4):
            pagina = self.client.get(url)
            self.assertContains(pagina, f'data-error="{clave}"')
            self.assertContains(pagina, f'name="formulario-{clave}"')
            self.assertContains(pagina, "data-formulario-tipo-egreso")

    def test_p7_muestra_el_formulario_de_egreso_despues_de_egresar(self):
        self._con_ciudadano_ver()
        self.client.force_login(self.operador_cis)
        self.assertEqual(self._post(self._datos()).status_code, 200)

        pagina = self.client.get(self.url_p7)

        self.assertContains(pagina, "Formulario de egreso")
        self.assertContains(pagina, "Se va con familiares")
        self.assertContains(pagina, AdjuntoRespuestaEgreso.objects.get().archivo.url)

    @tag("performance")
    def test_el_formulario_suma_una_consulta_de_lectura_al_post_de_egreso(self):
        """Con formulario el POST lee el vigente del tipo (1) y guarda: fila bloqueada (1), alta (1), adjunto (1)."""
        with CaptureQueriesContext(connection) as con:
            self.assertEqual(self._post(self._datos()).status_code, 200)
        lecturas = [c["sql"] for c in con.captured_queries if "programas_disenoformulario" in c["sql"]]
        # El vigente (1) y la comprobación de baja que ya hacía el servicio de guardado no se suman: una sola.
        self.assertEqual(len(lecturas), 1, lecturas)
