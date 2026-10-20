"""Formulario «Crear dispositivo» del tipo en el alta y la edición de la institución (P17, carril 2).

Cubre la sección de P3 (endpoint y sin JS), las condiciones evaluadas en el servidor, el
tipo de valor contra la obligatoriedad (solo al enviar a validación), la foto y la versión
guardadas, la edición después de cambiar el diseño, el cambio de tipo, los archivos y su
regla de `/media/`, la lectura en P4, la baja del formulario con respuestas y los dos
MINOR del Cambio 343 (franjas). Los presupuestos van con `@tag("performance")`.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path
from unittest import skipUnless
from unittest.mock import patch

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import tag
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from programas.forms import FranjaHorariaFormSet, formulario_tipo_para
from programas.models import (
    AdjuntoRespuestaAlta,
    DisenoFormulario,
    Dispositivo,
    ItemDiseno,
    MomentoFormulario,
    RespuestasAltaDispositivo,
    TipoDispositivo,
)
from programas.services import constructor
from programas.services.formularios_tipo import crear_formulario, puede_eliminar_formulario
from programas.services.respuestas_dispositivo import formularios_respondidos
from programas.tests.test_dispositivos_fidelidad_fd import AHORA
from programas.tests.test_dispositivos_horarios_localidad import LUNES, _post_franjas, catalogo_chaco
from programas.tests.test_dispositivos_inspecciones import TODAS_DE_DISPOSITIVOS, BaseInspecciones

PDF = b"%PDF-1.4\n%prueba\n"


def _presupuesto(nombre):
    presupuestos = json.loads(
        (Path(__file__).resolve().parents[2] / "scripts/perf_budgets.json").read_text(encoding="utf-8")
    )
    return presupuestos["servicios"][nombre]["consultas_fijas"]


def _pdf(nombre="habilitacion.pdf"):
    return SimpleUploadedFile(nombre, PDF, content_type="application/pdf")


class _Base(BaseInspecciones):
    """Un tipo con su formulario «Crear dispositivo»: camas (número, obligatorio), cocina
    (Sí/No, obligatorio), la habilitación de la cocina (archivo, obligatorio, solo si
    hay cocina), un texto y observaciones (opcional)."""

    def setUp(self):
        reloj = patch("django.utils.timezone.now", return_value=AHORA)
        reloj.start()
        self.addCleanup(reloj.stop)
        super().setUp()
        catalogo_chaco()
        self.admin = self._usuario("admin_formulario_alta", TODAS_DE_DISPOSITIVOS)
        self.client.force_login(self.admin)
        self.crear = reverse("dispositivos:crear")
        self.seccion = reverse("dispositivos:formulario_tipo_seccion")

        self.diseno = crear_formulario(self.tipo, MomentoFormulario.CREAR_DISPOSITIVO, self.admin)
        self.grupo = self._grupo(self.diseno, "Datos del edificio")
        self.camas = self._campo(self.diseno, self.grupo, "Cantidad de camas", "INT", obligatorio=True)
        self.cocina = self._campo(
            self.diseno, self.grupo, "¿Tiene cocina?", "SELECTOR", obligatorio=True, opciones=["Sí", "No"]
        )
        self.habilitacion = self._campo(
            self.diseno, self.grupo, "Habilitación de la cocina", "ARCHIVO", obligatorio=True
        )
        self._mutar(
            self.diseno,
            lambda: constructor.poner_condicion(
                self.habilitacion,
                {"modo": "todas", "reglas": [{"fuente": self.cocina.clave, "op": "es", "valor": "Sí"}]},
            ),
        )
        self._mutar(
            self.diseno,
            lambda: constructor.crear_texto(
                self.diseno, self.grupo, {"texto": "Los datos los verifica el área técnica.", "canal": "ambos"}
            ),
        )
        self.observaciones = self._campo(self.diseno, self.grupo, "Observaciones", "STRING")

    # ── helpers ──
    def _mutar(self, diseno, operacion):
        constructor.mutar(diseno, self.admin, operacion)
        diseno.refresh_from_db()

    def _grupo(self, diseno, titulo):
        self._mutar(
            diseno, lambda: constructor.crear_grupo(diseno, {"etiqueta": titulo, "subtitulo": "", "canal": "ambos"})
        )
        return diseno.items.get(tipo=ItemDiseno.Tipo.GRUPO, etiqueta=titulo)

    def _campo(self, diseno, grupo, texto, tipo="STRING", *, obligatorio=False, opciones=()):
        propio = {
            "texto": texto,
            "tipo": tipo,
            "opciones": list(opciones),
            "presentacion": "LISTA",
            "obligatorio": obligatorio,
        }
        self._mutar(diseno, lambda: constructor.crear_propio(diseno, grupo, {"propio": propio, "canal": "ambos"}))
        return diseno.items.get(tipo=ItemDiseno.Tipo.CAMPO, propio__texto=texto)

    def _nombre(self, item):
        return f"formulario-{item.clave}"

    def _datos(self, codigo="FA-1", *, tipo=None, diseno=None, respuestas=None, enviar=False):
        datos = {
            "tipo": (tipo or self.tipo).pk,
            "codigo": codigo,
            "nombre": f"Institución {codigo}",
            "localidad": "Resistencia",
            "domicilio": "Calle 123",
            "responsable_nombre": "Responsable",
            "contacto_telefono": "123456",
        }
        if diseno is not False:
            datos["formulario_tipo_diseno"] = (diseno or self.diseno).pk
        for item, valor in (respuestas or {}).items():
            datos[self._nombre(item)] = valor
        if enviar:
            datos["accion"] = "enviar_validacion"
        return datos

    def _alta(self, codigo="FA-1", **kwargs):
        return self.client.post(self.crear, self._datos(codigo, **kwargs))

    def _completo(self):
        """Lo obligatorio respondido, con cocina y su habilitación."""
        return {self.camas: "12", self.cocina: "Sí", self.habilitacion: _pdf(), self.observaciones: "Nada"}

    def _fila(self, dispositivo, diseno=None):
        return RespuestasAltaDispositivo.objects.get(dispositivo=dispositivo, diseno=diseno or self.diseno)


# ── La sección de P3 ─────────────────────────────────────────────────────────


class SeccionTests(_Base):
    def test_el_alta_dibuja_las_preguntas_del_tipo_en_su_propia_tarjeta_despues_de_dias_y_horarios(self):
        html = self.client.get(self.crear, {"tipo": self.tipo.pk}).content.decode()
        # Sin tipo elegido en el GET no hay sección: la trae el JS al elegirlo.
        self.assertNotIn("formulario_tipo_diseno", html)

        respuesta = self.client.post(self.crear, self._datos(diseno=False))
        html = respuesta.content.decode()
        self.assertIn(f'name="formulario_tipo_diseno" value="{self.diseno.pk}"', html)
        # Tarjeta propia: Días y horarios cierra la de datos y el formulario del tipo va después.
        self.assertLess(html.index("Responsable y contacto"), html.index("Días y horarios"))
        self.assertLess(html.index("Días y horarios"), html.index("Formulario de ingreso"))
        self.assertLess(html.index("Formulario de ingreso"), html.index("Datos del edificio"))
        self.assertIn(f"Lo pide el tipo «{self.tipo.nombre}»", html)
        for item in (self.camas, self.cocina, self.habilitacion, self.observaciones):
            self.assertIn(f'name="{self._nombre(item)}"', html)
        self.assertIn("Los datos los verifica el área técnica.", html)
        self.assertIn('enctype="multipart/form-data"', html)
        self.assertIn('id="formulario-tipo-items"', html)

    def test_sin_formulario_del_tipo_no_sale_la_tarjeta(self):
        sin_formulario = TipoDispositivo.objects.create(codigo="HOGAR", nombre="Hogar")
        html = self.client.get(self.crear, {"tipo": sin_formulario.pk}).content.decode()
        self.assertNotIn("Formulario de ingreso", html)
        self.assertIn("Días y horarios", html)
        self.assertEqual(self.client.get(self.seccion, {"tipo": sin_formulario.pk}).content.strip(), b"")
        self.assertContains(self.client.get(self.seccion, {"tipo": self.tipo.pk}), "Formulario de ingreso")

    def test_sin_js_guardar_con_el_tipo_recien_elegido_vuelve_con_la_seccion_y_no_guarda(self):
        respuesta = self._alta(diseno=False)

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "El tipo elegido tiene preguntas propias")
        self.assertContains(respuesta, f'name="{self._nombre(self.camas)}"')
        self.assertFalse(Dispositivo.objects.filter(codigo="FA-1").exists())

    def test_el_endpoint_cambia_la_seccion_segun_el_tipo(self):
        sin_formulario = TipoDispositivo.objects.create(codigo="HOGAR", nombre="Hogar")
        inactivo = TipoDispositivo.objects.create(codigo="INAC", nombre="Inactivo", activo=False)
        crear_formulario(inactivo, MomentoFormulario.CREAR_DISPOSITIVO)

        con = self.client.get(self.seccion, {"tipo": self.tipo.pk})
        self.assertEqual(con.status_code, 200)
        self.assertContains(con, "Cantidad de camas")
        self.assertContains(con, f'name="formulario_tipo_diseno" value="{self.diseno.pk}"')
        # Tipo sin formulario, inactivo, inexistente o mal escrito: la misma sección vacía.
        for tipo in (sin_formulario.pk, inactivo.pk, 999999, "abc", "²", ""):
            with self.subTest(tipo=tipo):
                respuesta = self.client.get(self.seccion, {"tipo": tipo})
                self.assertEqual(respuesta.status_code, 200)
                self.assertEqual(respuesta.content.decode().strip(), "")

    def test_el_endpoint_del_alta_pide_el_alta_completa(self):
        """Todas las capacidades salvo el alcance de admin del programa: 403, como el alta
        (mutación: sin el chequeo de alcance en la vista, 200)."""
        sin_admin = tuple(c for c in TODAS_DE_DISPOSITIVOS if c != "programa.configurar")
        usuario = self._usuario("sin_admin_fa", sin_admin, [self.cis])
        self.client.force_login(usuario)

        self.assertEqual(self.client.get(self.seccion, {"tipo": self.tipo.pk}).status_code, 403)

    def test_el_endpoint_de_la_edicion_pide_editar_esa_institucion_y_lo_ajeno_es_404(self):
        """Con editar sobre el CIS (y todo lo demás menos el alcance de admin): el CIS
        precarga; el parador, uno inexistente o uno mal escrito dan 404 (mutación:
        resolviendo el dispositivo sin `dispositivos_en_alcance`, el parador da 200)."""
        sin_admin = tuple(c for c in TODAS_DE_DISPOSITIVOS if c != "programa.configurar")
        usuario = self._usuario("editor_cis_fa", sin_admin, [self.cis])
        RespuestasAltaDispositivo.objects.create(
            dispositivo=self.cis, diseno=self.diseno, definicion={}, respuestas={self.camas.clave: 7}
        )
        self.client.force_login(usuario)

        propio = self.client.get(self.seccion, {"tipo": self.tipo.pk, "dispositivo": self.cis.pk})
        self.assertEqual(propio.status_code, 200)
        self.assertContains(propio, 'value="7"')
        for pedido in (self.parador.pk, 999999, "abc", "١"):
            with self.subTest(dispositivo=pedido):
                respuesta = self.client.get(self.seccion, {"tipo": self.tipo.pk, "dispositivo": pedido})
                self.assertEqual(respuesta.status_code, 404)

    def test_formulario_dado_de_baja_no_se_pide(self):
        DisenoFormulario.objects.filter(pk=self.diseno.pk).update(dado_de_baja_en=AHORA)

        self.assertIsNone(formulario_tipo_para(self.tipo.pk))
        self.assertEqual(self.client.get(self.seccion, {"tipo": self.tipo.pk}).content.decode().strip(), "")
        # Sin formulario vigente, el alta se guarda sin la marca.
        self.assertEqual(self._alta(diseno=False).status_code, 302)


# ── Guardado, condiciones y obligatoriedad ───────────────────────────────────


class GuardadoTests(_Base):
    def test_el_alta_guarda_la_foto_la_version_y_las_respuestas_tipadas(self):
        respuesta = self._alta(respuestas=self._completo())

        self.assertEqual(respuesta.status_code, 302)
        dispositivo = Dispositivo.objects.get(codigo="FA-1")
        fila = self._fila(dispositivo)
        self.assertEqual(fila.version, self.diseno.version)
        self.assertEqual(fila.definicion["version"], self.diseno.version)
        claves_foto = {item["clave"] for grupo in fila.definicion["items"] for item in grupo["items"]}
        self.assertIn(self.camas.clave, claves_foto)
        self.assertEqual(fila.respuestas[self.camas.clave], 12)
        self.assertEqual(fila.respuestas[self.cocina.clave], "Sí")
        self.assertEqual(fila.respuestas[self.habilitacion.clave], "habilitacion.pdf")
        self.assertEqual(fila.actualizado_por, self.admin)

    def test_un_valor_de_tipo_invalido_se_rechaza_tambien_en_el_borrador(self):
        respuesta = self._alta(respuestas={self.camas: "doce"})

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Introduzca un número entero")
        self.assertFalse(Dispositivo.objects.filter(codigo="FA-1").exists())
        self.assertFalse(RespuestasAltaDispositivo.objects.exists())

    def test_el_borrador_guarda_sin_los_obligatorios(self):
        """Mutación: con `required` en los obligatorios (sin la línea que lo apaga), el
        borrador incompleto vuelve con error."""
        respuesta = self._alta(respuestas={self.observaciones: "Solo esto"})

        self.assertEqual(respuesta.status_code, 302)
        fila = self._fila(Dispositivo.objects.get(codigo="FA-1"))
        self.assertEqual(fila.respuestas, {self.observaciones.clave: "Solo esto"})

    def test_enviar_a_validacion_exige_los_obligatorios_visibles(self):
        """Mutación: sin `exige_formulario` en `enviar_a_validacion`, se envía igual."""
        respuesta = self._alta(respuestas={self.cocina: "Sí"}, enviar=True)

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Completá las preguntas obligatorias del formulario del tipo")
        self.assertContains(respuesta, "Cantidad de camas, Habilitación de la cocina")
        self.assertContains(respuesta, "Este dato es obligatorio.")
        self.assertFalse(Dispositivo.objects.filter(codigo="FA-1").exists())

        self.assertEqual(self._alta(respuestas=self._completo(), enviar=True).status_code, 302)
        self.assertEqual(Dispositivo.objects.get(codigo="FA-1").estado, Dispositivo.Estado.PENDIENTE_VALIDACION)

    def test_un_obligatorio_oculto_no_se_exige_ni_se_guarda_aunque_llegue_en_el_post(self):
        """Sin cocina, la habilitación queda oculta: un POST armado que la manda igual no
        la guarda ni escribe el archivo, y enviar a validación no la pide."""
        respuesta = self._alta(
            respuestas={self.camas: "4", self.cocina: "No", self.habilitacion: _pdf("colado.pdf")}, enviar=True
        )

        self.assertEqual(respuesta.status_code, 302)
        dispositivo = Dispositivo.objects.get(codigo="FA-1")
        self.assertEqual(dispositivo.estado, Dispositivo.Estado.PENDIENTE_VALIDACION)
        fila = self._fila(dispositivo)
        self.assertNotIn(self.habilitacion.clave, fila.respuestas)
        self.assertFalse(AdjuntoRespuestaAlta.objects.exists())

    def test_un_valor_invalido_en_un_campo_oculto_no_frena_el_guardado(self):
        hornallas = self._campo(self.diseno, self.grupo, "Cantidad de hornallas", "INT")
        self._mutar(
            self.diseno,
            lambda: constructor.poner_condicion(
                hornallas, {"modo": "todas", "reglas": [{"fuente": self.cocina.clave, "op": "es", "valor": "Sí"}]}
            ),
        )
        respuesta = self._alta(respuestas={self.cocina: "No", hornallas: "cuatro"})

        self.assertEqual(respuesta.status_code, 302)
        self.assertNotIn(hornallas.clave, self._fila(Dispositivo.objects.get(codigo="FA-1")).respuestas)

    def test_sin_nada_respondido_no_se_crea_la_fila(self):
        self.assertEqual(self._alta().status_code, 302)
        self.assertFalse(RespuestasAltaDispositivo.objects.exists())
        self.assertTrue(puede_eliminar_formulario(self.diseno))


# ── Edición ──────────────────────────────────────────────────────────────────


class EdicionTests(_Base):
    def setUp(self):
        super().setUp()
        self._alta(respuestas={self.camas: "5", self.cocina: "No", self.observaciones: "Hola"})
        self.dispositivo = Dispositivo.objects.get(codigo="FA-1")
        self.editar = reverse("dispositivos:editar", args=[self.dispositivo.pk])

    def _post_edicion(self, **kwargs):
        datos = self._datos(**kwargs)
        datos["codigo"] = self.dispositivo.codigo
        datos["nombre"] = self.dispositivo.nombre
        return self.client.post(self.editar, datos)

    def test_la_edicion_precarga_por_clave_y_conserva_lo_que_el_diseno_quito(self):
        """Mutación: sin las claves conservadas en `guardar_respuestas_alta`, la respuesta
        a «Observaciones» se pierde al guardar."""
        version_respondida = self._fila(self.dispositivo).version
        self._mutar(self.diseno, self.observaciones.delete)
        personal = self._campo(self.diseno, self.grupo, "Personal a cargo", "INT")

        html = self.client.get(self.editar).content.decode()
        self.assertRegex(html, rf'name="{self._nombre(self.camas)}" value="5"')
        self.assertIn(f'name="{self._nombre(personal)}"', html)
        self.assertNotIn("Observaciones", html)

        respuesta = self._post_edicion(respuestas={self.camas: "6", self.cocina: "No", personal: "3"})
        self.assertEqual(respuesta.status_code, 302)
        fila = self._fila(self.dispositivo)
        self.assertEqual(fila.version, self.diseno.version)
        self.assertGreater(fila.version, version_respondida)
        self.assertEqual(fila.respuestas[self.camas.clave], 6)
        self.assertEqual(fila.respuestas[personal.clave], 3)
        self.assertEqual(fila.respuestas[self.observaciones.clave], "Hola")
        self.assertEqual(fila.anteriores[self.observaciones.clave]["campo"]["texto"], "Observaciones")
        self.assertEqual(fila.anteriores[self.observaciones.clave]["version"], version_respondida)
        claves_foto = {item["clave"] for grupo in fila.definicion["items"] for item in grupo["items"]}
        self.assertNotIn(self.observaciones.clave, claves_foto)

    def test_cambiar_de_tipo_conserva_las_respuestas_del_anterior(self):
        hogar = TipoDispositivo.objects.create(codigo="HOGAR", nombre="Hogar")
        diseno_hogar = crear_formulario(hogar, MomentoFormulario.CREAR_DISPOSITIVO, self.admin)
        talleres = self._campo(diseno_hogar, self._grupo(diseno_hogar, "Talleres"), "Talleres por semana", "INT")
        antes = self._fila(self.dispositivo).respuestas

        respuesta = self._post_edicion(tipo=hogar, diseno=diseno_hogar, respuestas={talleres: "2"})

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(self._fila(self.dispositivo).respuestas, antes)
        self.assertEqual(self._fila(self.dispositivo, diseno_hogar).respuestas, {talleres.clave: 2})
        detalle = self.client.get(reverse("dispositivos:detalle", args=[self.dispositivo.pk]))
        self.assertContains(detalle, "Talleres por semana")
        self.assertContains(detalle, "Tipo anterior: Albergue")

    def test_guardar_sin_cambios_no_reescribe_la_fila(self):
        fila = self._fila(self.dispositivo)
        self._post_edicion(respuestas={self.camas: "5", self.cocina: "No", self.observaciones: "Hola"})
        self.assertEqual(self._fila(self.dispositivo).modificado, fila.modificado)


# ── Archivos y /media/ ───────────────────────────────────────────────────────


class ArchivoTests(_Base):
    def test_el_archivo_se_sube_en_el_mismo_post_y_se_valida(self):
        malo = SimpleUploadedFile("habilitacion.exe", b"MZ", content_type="application/octet-stream")
        rechazo = self._alta(respuestas={self.cocina: "Sí", self.habilitacion: malo})
        self.assertEqual(rechazo.status_code, 200)
        self.assertContains(rechazo, "Solo se aceptan archivos JPG, PNG o PDF.")

        disfrazado = SimpleUploadedFile("habilitacion.pdf", b"<html></html>", content_type="application/pdf")
        self.assertEqual(self._alta(respuestas={self.cocina: "Sí", self.habilitacion: disfrazado}).status_code, 200)
        self.assertFalse(AdjuntoRespuestaAlta.objects.exists())

        self.assertEqual(self._alta(respuestas=self._completo()).status_code, 302)
        adjunto = AdjuntoRespuestaAlta.objects.get()
        self.assertEqual(adjunto.clave, self.habilitacion.clave)
        self.assertTrue(adjunto.archivo.name.startswith("dispositivos/formularios/"))
        self.assertNotIn("habilitacion", adjunto.archivo.name)

    def test_si_el_guardado_falla_el_archivo_escrito_se_borra(self):
        with patch("programas.views.dispositivos_legajo.registrar_alta_dispositivo", side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                self._alta(respuestas=self._completo())
        self.assertFalse(AdjuntoRespuestaAlta.objects.exists())
        carpeta = Path(settings.MEDIA_ROOT) / "dispositivos" / "formularios"
        self.assertEqual([p for p in carpeta.rglob("*") if p.is_file()], [])

    def test_media_lo_baja_quien_ve_ese_dispositivo_y_lo_ajeno_es_404(self):
        """Mutación: sin el alcance en `_archivo_de_formulario_dispositivo` (solo la
        capacidad), el operador del geriátrico lo baja."""
        self._alta(respuestas=self._completo())
        dispositivo = Dispositivo.objects.get(codigo="FA-1")
        url = AdjuntoRespuestaAlta.objects.get().archivo.url

        self.assertEqual(self.client.get(url).status_code, 200)
        propio = self._usuario("operador_fa", ("dispositivo.ver",), [dispositivo])
        self.client.force_login(propio)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.force_login(self.operador_geriatrico)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.get(url.replace(".pdf", "x.pdf")).status_code, 404)


# ── P4 ───────────────────────────────────────────────────────────────────────


class DetalleTests(_Base):
    def test_la_solapa_datos_muestra_lo_respondido_por_seccion_y_solo_lo_visible(self):
        self._alta(respuestas={self.camas: "9", self.cocina: "No", self.observaciones: "Con patio"})
        dispositivo = Dispositivo.objects.get(codigo="FA-1")

        respuesta = self.client.get(reverse("dispositivos:detalle", args=[dispositivo.pk]))

        self.assertContains(respuesta, "Crear dispositivo")
        self.assertContains(respuesta, f"Versión {self.diseno.version}")
        self.assertContains(respuesta, "Datos del edificio")
        self.assertContains(respuesta, "Cantidad de camas")
        self.assertContains(respuesta, "Con patio")
        # Oculta por su condición (sin cocina): no se muestra ni como vacía.
        self.assertNotContains(respuesta, "Habilitación de la cocina")

    def test_el_archivo_se_enlaza_desde_p4(self):
        self._alta(respuestas=self._completo())
        dispositivo = Dispositivo.objects.get(codigo="FA-1")
        adjunto = AdjuntoRespuestaAlta.objects.get()

        respuesta = self.client.get(reverse("dispositivos:detalle", args=[dispositivo.pk]))
        self.assertContains(respuesta, f'href="{adjunto.archivo.url}"')

    def test_sin_respuestas_no_hay_seccion(self):
        respuesta = self.client.get(reverse("dispositivos:detalle", args=[self.cis.pk]))
        self.assertNotContains(respuesta, "formulario-respondido-1")


# ── Eliminar con respuestas = baja ───────────────────────────────────────────


class BajaTests(_Base):
    def _eliminar(self, diseno):
        url = reverse("dispositivos:formulario_eliminar", args=[diseno.tipo_dispositivo_id, diseno.momento])
        return self.client.post(url)

    def test_con_respuestas_eliminar_da_de_baja_y_se_reactiva(self):
        """Mutación: `puede_eliminar_formulario` sin mirar las respuestas da True."""
        self._alta(respuestas={self.camas: "3"})
        dispositivo = Dispositivo.objects.get(codigo="FA-1")
        self.assertFalse(puede_eliminar_formulario(self.diseno))
        tabla = self.client.get(reverse("dispositivos:tipo_detalle", args=[self.tipo.pk]))
        self.assertContains(tabla, "ya tiene respuestas: no se borra, se da de baja")

        self.assertEqual(self._eliminar(self.diseno).status_code, 302)
        self.diseno.refresh_from_db()
        self.assertIsNotNone(self.diseno.dado_de_baja_en)
        self.assertTrue(self.diseno.items.exists())

        tabla = self.client.get(reverse("dispositivos:tipo_detalle", args=[self.tipo.pk]))
        self.assertContains(tabla, "De baja")
        reactivar = reverse("dispositivos:formulario_reactivar", args=[self.tipo.pk, self.diseno.momento])
        self.assertContains(tabla, reactivar)
        # Deja de pedirse en P3 y se sigue leyendo en P4.
        self.assertEqual(self.client.get(self.seccion, {"tipo": self.tipo.pk}).content.decode().strip(), "")
        self.assertContains(
            self.client.get(reverse("dispositivos:detalle", args=[dispositivo.pk])), "Cantidad de camas"
        )

        version = self.diseno.version
        self.assertEqual(self.client.post(reactivar).status_code, 302)
        self.diseno.refresh_from_db()
        self.assertIsNone(self.diseno.dado_de_baja_en)
        self.assertEqual(self.diseno.version, version)
        self.assertContains(self.client.get(self.seccion, {"tipo": self.tipo.pk}), "Cantidad de camas")

    def test_sin_respuestas_eliminar_borra_como_antes(self):
        tabla = self.client.get(reverse("dispositivos:tipo_detalle", args=[self.tipo.pk]))
        self.assertContains(tabla, "Nadie lo respondió todavía")

        self._eliminar(self.diseno)
        self.assertFalse(DisenoFormulario.objects.filter(pk=self.diseno.pk).exists())

    def test_reactivar_pide_configurar(self):
        self.client.force_login(self.operador_geriatrico)
        url = reverse("dispositivos:formulario_reactivar", args=[self.tipo.pk, self.diseno.momento])
        self.assertEqual(self.client.post(url).status_code, 403)


# ── MINOR del Cambio 343 (franjas) ───────────────────────────────────────────


class FranjasMinorTests(_Base):
    def test_la_superposicion_se_informa_aunque_otra_fila_tenga_error(self):
        """Mutación: con el `if any(self.errors): return` de antes, la superposición no se informa."""
        datos = _post_franjas((LUNES, "08:00", ""), (LUNES, "09:00", "12:00"), (LUNES, "11:00", "14:00"))
        formset = FranjaHorariaFormSet(datos, prefix="franjas")

        self.assertFalse(formset.is_valid())
        self.assertIn("Indicá hasta qué hora.", formset.forms[0].errors["hora_hasta"])
        self.assertIn("Se superpone con la franja del lunes de 09:00 a 12:00.", formset.forms[2].errors["hora_desde"])

    @skipUnless(shutil.which("node"), "Requiere Node para ejecutar el JS renderizado")
    def test_una_franja_que_vuelve_marcada_para_quitar_se_oculta_y_no_cuenta(self):
        """Mutación: sin ocultar la fila marcada en `prepararQuitar`, sigue visible y la
        franja nueva del mismo horario se rechaza por superposición."""
        html = self.client.get(self.crear).content.decode()
        script = next(s for s in re.findall(r"<script>(.*?)</script>", html, re.S) if "prepararQuitar" in s)
        resultado = subprocess.run(
            [shutil.which("node"), str(settings.BASE_DIR / "programas/tests/js/franjas_quitar_fa.cjs")],
            input=json.dumps(script),
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=15,
        )
        self.assertEqual(resultado.returncode, 0, resultado.stderr)


# ── Presupuestos ─────────────────────────────────────────────────────────────


@tag("performance")
class PresupuestoTests(_Base):
    def _sumar_campos(self, cantidad):
        for n in range(cantidad):
            self._campo(self.diseno, self.grupo, f"Extra {n}", "STRING")

    def test_la_seccion_de_p3_cuesta_lo_mismo_con_pocos_o_muchos_campos(self):
        """En el alta no hay respuestas que precargar: una consulta menos que en la edición."""
        techo = _presupuesto("dispositivos_formulario_tipo_p3")
        medidas = {"alta": [], "edicion": []}
        for extra in (0, 8):
            self._sumar_campos(extra)
            for modo, dispositivo in (("alta", None), ("edicion", self.cis)):
                with CaptureQueriesContext(connection) as consultas:
                    formulario_tipo_para(self.tipo.pk, dispositivo)
                medidas[modo].append(len(consultas))
        self.assertEqual(medidas["edicion"], [techo, techo])
        self.assertEqual(medidas["alta"], [techo - 1, techo - 1])

    def test_p4_lee_lo_respondido_sin_n_mas_uno(self):
        techo = _presupuesto("dispositivos_formularios_respondidos")
        medidas = []
        for codigo, extra in (("FA-P1", 0), ("FA-P2", 8)):
            self._sumar_campos(extra)
            self._alta(codigo, respuestas=self._completo())
            dispositivo = Dispositivo.objects.get(codigo=codigo)
            with CaptureQueriesContext(connection) as consultas:
                formularios_respondidos(dispositivo)
            medidas.append(len(consultas))
        self.assertEqual(medidas, [techo, techo])

    def test_las_pantallas_no_crecen_con_los_campos(self):
        self._alta("FA-P3", respuestas=self._completo())
        dispositivo = Dispositivo.objects.get(codigo="FA-P3")
        urls = (
            reverse("dispositivos:editar", args=[dispositivo.pk]),
            reverse("dispositivos:detalle", args=[dispositivo.pk]),
        )
        antes = {}
        for url in urls:
            self.client.get(url)
            with CaptureQueriesContext(connection) as consultas:
                self.client.get(url)
            antes[url] = len(consultas)
        self._sumar_campos(8)
        for url in urls:
            with self.subTest(url=url), CaptureQueriesContext(connection) as consultas:
                self.client.get(url)
            self.assertEqual(len(consultas), antes[url], url)
