"""Paso 2 del link público: el formulario que diseñó la convocatoria, su
validación y la ingesta del caso (#294, #295; reescrito por el Cambio 58).

Desde el Cambio 58 cada campo se llama por su clave de ítem (``pg-<pk>``,
``rn-<pk>``, ``cp-…``) y la identidad, el contacto y el apoderado son requisitos
generales protegidos del catálogo, no columnas sueltas del formulario.
"""

from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

from django import forms
from django.contrib.staticfiles import finders
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.template.loader import get_template
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from legajos.models import Ciudadano
from portal.forms.inscripcion import InscripcionPaso2Form
from portal.services.inscripcion import clave_sesion
from programas.management.commands.seed_becas import asegurar_catalogo_protegido
from programas.models import (
    AdjuntoFormulario,
    Convocatoria,
    Formulario,
    OrigenRequisito,
    PreguntaGlobal,
    Relevamiento,
    RequisitoNativo,
    Segmento,
)
from programas.services.becas import definicion_formulario
from programas.services.diseno import clave_pregunta
from programas.services.inscripcion_publica import (
    InscripcionDuplicada,
    InscripcionNoDisponible,
    crear_formulario_publico,
)


def _identificacion(dni="30123456", origen="personas", **extra):
    base = {
        "dni": dni,
        "sexo": "F",
        "datos": {"nombre": "María Luján", "apellido": "Gómez", "fecha_nacimiento": "1991-03-14"}
        if origen == "personas"
        else None,
        "origen": origen,
        "client_uuid": str(uuid4()),
    }
    base.update(extra)
    return base


def _clave_vinculo(origen, vinculo):
    """La clave del ítem de un campo protegido del catálogo (Cambio 58)."""
    return clave_pregunta(PreguntaGlobal.objects.get(origen=origen, vinculo=vinculo))


class _BasePaso2Test(TestCase):
    def setUp(self):
        cache.clear()
        # Identidad, contacto y apoderado viven en el catálogo protegido.
        asegurar_catalogo_protegido()
        self.segmento = Segmento.objects.create(nombre="Seg", cupo_maximo=100)
        self.convocatoria = Convocatoria.objects.create(
            nombre="Becas 2026",
            segmento=self.segmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        self.pregunta = PreguntaGlobal.objects.create(
            texto="¿Asistís a una institución educativa?",
            tipo="SELECTOR",
            opciones=["Sí", "No"],
            obligatorio=True,
            orden=1,
        )
        self.requisito = RequisitoNativo.objects.create(
            texto="Certificado de alumno regular",
            tipo="ARCHIVO",
            segmento=self.segmento,
            obligatorio=True,
            orden=1,
        )
        self.relevamiento = Relevamiento.objects.create(
            convocatoria=self.convocatoria,
            tipo=Relevamiento.Tipo.PUBLICO,
            fecha_asignada=timezone.now() - timedelta(days=1),
            fecha_hasta=timezone.now() + timedelta(days=10),
        )
        self.definicion = definicion_formulario(self.relevamiento)
        self.k_pregunta = clave_pregunta(self.pregunta)
        self.k_requisito = f"rn-{self.requisito.pk}"
        self.k_telefono = _clave_vinculo(OrigenRequisito.LEGAJO, "telefono")
        self.k_email = _clave_vinculo(OrigenRequisito.LEGAJO, "email")
        self.k_nombre = _clave_vinculo(OrigenRequisito.LEGAJO, "nombre")
        self.k_apellido = _clave_vinculo(OrigenRequisito.LEGAJO, "apellido")
        self.k_nacimiento = _clave_vinculo(OrigenRequisito.LEGAJO, "fecha_nacimiento")
        self.k_apo_dni = _clave_vinculo(OrigenRequisito.PERSONA_VINCULADA, "dni")

    def _data(self, **extra):
        data = {
            self.k_telefono: "3624123456",
            self.k_email: "maria@correo.com",
            self.k_pregunta: "Sí",
        }
        data.update(extra)
        return data

    def _datos_manuales(self, **extra):
        """Lo que completa quien no pudo validar su identidad en el paso 1."""
        return self._data(
            **{
                self.k_nombre: "Juan",
                self.k_apellido: "Pérez",
                self.k_nacimiento: "1990-01-01",
                **extra,
            }
        )

    def _files(self, **extra):
        files = {self.k_requisito: SimpleUploadedFile("cert.png", b"\x89PNG fake", content_type="image/png")}
        files.update(extra)
        return files

    def _form(self, identificacion=None, data=None, files=None):
        return InscripcionPaso2Form(
            data if data is not None else self._data(),
            files if files is not None else self._files(),
            definicion=self.definicion,
            identificacion=identificacion or _identificacion(),
        )


class Paso2FormTests(_BasePaso2Test):
    def test_construye_los_campos_del_diseno_por_clave(self):
        form = self._form()
        self.assertIn(self.k_pregunta, form.fields)
        self.assertIn(self.k_requisito, form.fields)
        self.assertIn(self.k_telefono, form.fields)
        # Identidad validada en el paso 1: se muestra fija, no se pide.
        self.assertNotIn(self.k_nombre, form.fields)
        self.assertEqual(form.fijas[self.k_nombre], "María Luján")
        self.assertEqual(form.fijas[self.k_apellido], "Gómez")
        self.assertEqual(form.fijas[self.k_nacimiento], "1991-03-14")
        self.assertEqual(form.fijas[_clave_vinculo(OrigenRequisito.LEGAJO, "dni")], "30123456")

    def test_un_gps_malformado_no_bloquea_la_inscripcion(self):
        """El GPS viaja en campos ocultos y es best effort: si llega roto se
        descarta, porque la persona no puede ver ni corregir ese error."""
        form = self._form(data=self._data(gps_lat="-27,451", gps_lng="-58.98612345678"))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.cleaned_data["gps_lat"])
        self.assertIsNone(form.cleaned_data["gps_lng"])

    def test_los_grupos_llegan_en_el_orden_del_diseno(self):
        form = self._form()
        titulos = [g["titulo"] for g in form.grupos()]
        self.assertEqual(titulos[:3], ["Datos personales", "Contacto", "Apoderado"])
        self.assertIn("Cuestionario social", titulos)

    def test_origen_manual_pide_identidad(self):
        form = self._form(identificacion=_identificacion(origen="manual"), data=self._data())
        self.assertIn(self.k_nombre, form.fields)
        self.assertFalse(form.is_valid())
        self.assertIn(self.k_nombre, form.errors)
        form = self._form(identificacion=_identificacion(origen="manual"), data=self._datos_manuales())
        self.assertTrue(form.is_valid(), form.errors)

    def test_obligatorios_dinamicos_se_exigen(self):
        data = self._data()
        data.pop(self.k_pregunta)
        form = self._form(data=data, files={})
        self.assertFalse(form.is_valid())
        self.assertIn(self.k_pregunta, form.errors)
        self.assertIn(self.k_requisito, form.errors)

    def test_contacto_opcional_no_se_exige(self):
        """D9: el operador puede aflojar el contacto en el catálogo."""
        PreguntaGlobal.objects.filter(origen=OrigenRequisito.LEGAJO, vinculo="telefono").update(obligatorio=False)
        self.definicion = definicion_formulario(self.relevamiento)
        data = self._data()
        data.pop(self.k_telefono)
        form = self._form(data=data)
        self.assertTrue(form.is_valid(), form.errors)

    def test_opcion_invalida_de_selector_se_rechaza(self):
        form = self._form(data=self._data(**{self.k_pregunta: "Otra cosa"}))
        self.assertFalse(form.is_valid())
        self.assertIn(self.k_pregunta, form.errors)

    def test_respuestas_ignoran_claves_ajenas_al_diseno(self):
        form = self._form(data=self._data(**{"pg-99999": "hack", "rn-99999": "hack"}))
        self.assertTrue(form.is_valid(), form.errors)
        respuestas = form.respuestas()
        self.assertNotIn("pg-99999", respuestas)
        self.assertNotIn("rn-99999", respuestas)
        self.assertEqual(respuestas[self.k_pregunta], "Sí")
        self.assertEqual(respuestas[self.k_requisito], "cert.png")
        self.assertEqual(respuestas[self.k_telefono], "3624123456")

    def test_archivo_invalido_se_rechaza(self):
        exe = SimpleUploadedFile("virus.exe", b"MZ", content_type="application/octet-stream")
        form = self._form(files={self.k_requisito: exe})
        self.assertFalse(form.is_valid())
        self.assertIn(self.k_requisito, form.errors)
        gigante = SimpleUploadedFile("foto.png", b"0" * (5 * 1024 * 1024 + 1), content_type="image/png")
        form = self._form(files={self.k_requisito: gigante})
        self.assertFalse(form.is_valid())

    def test_menor_exige_apoderado_y_mayor_no(self):
        """La condición por defecto del grupo Apoderado (edad < 18) se evalúa en
        el servidor: para un menor el grupo se muestra y sus campos se exigen."""
        hoy = timezone.localdate()
        menor = _identificacion()
        menor["datos"]["fecha_nacimiento"] = (hoy - timedelta(days=17 * 365)).isoformat()
        form = self._form(identificacion=menor)
        self.assertFalse(form.is_valid())
        self.assertIn(self.k_apo_dni, form.errors)
        # Cumple 18 exactamente hoy: se trata como mayor (RN-22).
        cumple_hoy = _identificacion()
        cumple_hoy["datos"]["fecha_nacimiento"] = hoy.replace(year=hoy.year - 18).isoformat()
        form = self._form(identificacion=cumple_hoy)
        self.assertTrue(form.is_valid(), form.errors)

    def test_menor_con_apoderado_completo_pasa(self):
        hoy = timezone.localdate()
        menor = _identificacion()
        menor["datos"]["fecha_nacimiento"] = (hoy - timedelta(days=17 * 365)).isoformat()
        form = self._form(
            identificacion=menor,
            data=self._data(
                **{
                    _clave_vinculo(OrigenRequisito.PERSONA_VINCULADA, "nombre"): "Ana",
                    _clave_vinculo(OrigenRequisito.PERSONA_VINCULADA, "apellido"): "Gómez",
                    self.k_apo_dni: "20.111.222",
                    _clave_vinculo(OrigenRequisito.PERSONA_VINCULADA, "genero"): "F",
                    _clave_vinculo(OrigenRequisito.PERSONA_VINCULADA, "fecha_nacimiento"): "1980-05-05",
                }
            ),
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.respuestas()[self.k_apo_dni], "20111222")

    def test_lo_oculto_no_se_exige_ni_se_guarda(self):
        """D11: un campo cuya condición no se cumple no se pide y lo que llegue
        para él se descarta."""
        hoy = timezone.localdate()
        mayor = _identificacion()
        mayor["datos"]["fecha_nacimiento"] = (hoy - timedelta(days=30 * 365)).isoformat()
        form = self._form(identificacion=mayor, data=self._data(**{self.k_apo_dni: "20111222"}))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertNotIn(self.k_apo_dni, form.respuestas())


class IngestaPublicaTests(_BasePaso2Test):
    def _form_valido(self, identificacion=None):
        form = self._form(identificacion=identificacion)
        assert form.is_valid(), form.errors
        return form

    def test_envio_crea_formulario_y_legajo_validado(self):
        ident = _identificacion()
        formulario, creado = crear_formulario_publico(
            self.relevamiento, identificacion=ident, form=self._form_valido(ident), client_uuid=ident["client_uuid"]
        )
        self.assertTrue(creado)
        self.assertEqual(formulario.estado, Formulario.Estado.ENVIADO)
        self.assertEqual(formulario.numero, 1)
        self.assertTrue(formulario.validado_renaper)
        self.assertIsNone(formulario.created_by)
        ciudadano = Ciudadano.objects.get(dni="30123456")
        self.assertEqual(ciudadano.nombre, "María Luján")
        self.assertEqual(formulario.ciudadano, ciudadano)
        # Respuestas por clave + foto de la definición (D3).
        self.assertEqual(formulario.respuestas[self.k_pregunta], "Sí")
        self.assertEqual(formulario.definicion["version"], self.definicion["version"])
        self.assertTrue(formulario.definicion["items"])
        # Puente con el contrato anterior: data por pk y columnas fijas.
        self.assertEqual(formulario.data["globales"][str(self.pregunta.pk)], "Sí")
        self.assertEqual(formulario.celular, "3624123456")
        self.assertEqual(formulario.email_contacto, "maria@correo.com")
        adjunto = AdjuntoFormulario.objects.get(formulario=formulario)
        self.assertEqual(adjunto.requisito_nativo_id, self.requisito.pk)

    def test_dni_existente_se_linkea_sin_duplicar(self):
        existente = Ciudadano.objects.create(dni="30123456", nombre="María", apellido="Gómez")
        ident = _identificacion()
        formulario, _ = crear_formulario_publico(
            self.relevamiento, identificacion=ident, form=self._form_valido(ident), client_uuid=ident["client_uuid"]
        )
        self.assertEqual(formulario.ciudadano, existente)
        self.assertEqual(Ciudadano.objects.filter(dni="30123456").count(), 1)

    def test_origen_manual_queda_no_validado(self):
        ident = _identificacion(origen="manual")
        form = self._form(identificacion=ident, data=self._datos_manuales())
        self.assertTrue(form.is_valid(), form.errors)
        formulario, _ = crear_formulario_publico(
            self.relevamiento, identificacion=ident, form=form, client_uuid=ident["client_uuid"]
        )
        self.assertFalse(formulario.validado_renaper)
        self.assertEqual(formulario.ciudadano.nombre, "Juan")

    def test_doble_submit_es_idempotente(self):
        ident = _identificacion()
        primero, creado1 = crear_formulario_publico(
            self.relevamiento, identificacion=ident, form=self._form_valido(ident), client_uuid=ident["client_uuid"]
        )
        segundo, creado2 = crear_formulario_publico(
            self.relevamiento, identificacion=ident, form=self._form_valido(ident), client_uuid=ident["client_uuid"]
        )
        self.assertTrue(creado1)
        self.assertFalse(creado2)
        self.assertEqual(primero.pk, segundo.pk)
        self.assertEqual(self.relevamiento.formularios.count(), 1)

    def test_cupo_lleno_no_crea(self):
        self.relevamiento.cupo_maximo = 1
        self.relevamiento.save(update_fields=["cupo_maximo"])
        Formulario.objects.create(
            relevamiento=self.relevamiento, celular="1", email_contacto="a@a.com", datos_identificacion={"dni": "1"}
        )
        ident = _identificacion(dni="28111222")
        with self.assertRaises(InscripcionNoDisponible):
            crear_formulario_publico(
                self.relevamiento, identificacion=ident, form=self._form_valido(ident), client_uuid=ident["client_uuid"]
            )
        self.assertEqual(self.relevamiento.formularios.count(), 1)

    def test_duplicado_colado_entre_pasos_se_rechaza(self):
        Formulario.objects.create(
            relevamiento=self.relevamiento,
            celular="1",
            email_contacto="a@a.com",
            datos_identificacion={"dni": "30123456"},
        )
        ident = _identificacion()
        with self.assertRaises(InscripcionDuplicada):
            crear_formulario_publico(
                self.relevamiento, identificacion=ident, form=self._form_valido(ident), client_uuid=ident["client_uuid"]
            )

    def test_vencido_al_enviar_no_crea(self):
        self.relevamiento.fecha_hasta = timezone.now() - timedelta(hours=1)
        self.relevamiento.save(update_fields=["fecha_hasta"])
        ident = _identificacion()
        with self.assertRaises(InscripcionNoDisponible):
            crear_formulario_publico(
                self.relevamiento, identificacion=ident, form=self._form_valido(ident), client_uuid=ident["client_uuid"]
            )


class Paso2VistaTests(_BasePaso2Test):
    def _sembrar_sesion(self, ident):
        session = self.client.session
        session[clave_sesion(self.relevamiento)] = ident
        session.save()

    def _url(self):
        return reverse("portal:inscripcion_paso2", kwargs={"token": self.relevamiento.token_publico})

    def test_post_valido_crea_y_redirige_a_confirmacion(self):
        ident = _identificacion()
        self._sembrar_sesion(ident)
        resp = self.client.post(self._url(), {**self._data(), **{k: v for k, v in self._files().items()}})
        self.assertRedirects(
            resp,
            reverse("portal:inscripcion_confirmacion", kwargs={"token": self.relevamiento.token_publico}),
            fetch_redirect_response=False,
        )
        self.assertEqual(self.relevamiento.formularios.count(), 1)
        # La identificación se limpia y el comprobante queda para la pantalla.
        self.assertNotIn(clave_sesion(self.relevamiento), self.client.session)
        self.assertEqual(self.client.session[f"inscripcion_ok_{self.relevamiento.pk}"]["numero"], 1)

    def test_get_renderiza_el_formulario_por_grupos(self):
        """La pantalla arma los grupos del diseño y publica los ítems con sus
        condiciones para el motor del navegador."""
        self._sembrar_sesion(_identificacion())
        resp = self.client.get(self._url())
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn('id="formulario-items"', html)
        self.assertIn(f'data-item="{self.k_pregunta}"', html)
        self.assertIn(f'data-item="{self.k_telefono}"', html)
        self.assertIn("Datos personales", html)
        self.assertIn("Apoderado", html)
        # La identidad validada se muestra, no se pide.
        self.assertIn("María Luján", html)
        self.assertNotIn(f'name="{self.k_nombre}"', html)
        # Los ítems planos llevan la condición del grupo Apoderado.
        planos = resp.context["planos"]
        apoderado = next(p for p in planos if p["clave"] == "g-apoderado")
        self.assertEqual(apoderado["condicion"]["reglas"][0]["op"], "edad_menor")

    def test_confirmacion_sin_envio_redirige_al_paso1(self):
        resp = self.client.get(
            reverse("portal:inscripcion_confirmacion", kwargs={"token": self.relevamiento.token_publico})
        )
        self.assertEqual(resp.status_code, 302)

    def test_reenvio_tras_confirmar_no_duplica(self):
        ident = _identificacion()
        self._sembrar_sesion(ident)
        datos_post = {**self._data(), **self._files()}
        self.client.post(self._url(), datos_post)
        # Segundo POST: la sesión ya no tiene identificación → vuelve al paso 1.
        resp = self.client.post(self._url(), datos_post)
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse("portal:inscripcion_paso1", kwargs={"token": self.relevamiento.token_publico}), resp.url)
        self.assertEqual(self.relevamiento.formularios.count(), 1)


class Paso2PresentacionSelectorTests(_BasePaso2Test):
    """Cambio 56: el mismo campo se rinde como lista o como buscador con
    píldoras según lo configurado, sin tocar qué valores son válidos."""

    def _definicion_con(self, tipo, presentacion, opciones=None):
        campo = {
            "id": self.pregunta.pk,
            "clave": self.k_pregunta,
            "tipo_item": "campo",
            "texto": "Nivel educativo",
            "tipo": tipo,
            "opciones": opciones or ["Primario", "Secundario", "Terciario"],
            "presentacion": presentacion,
            "obligatorio": True,
            "orden": 1,
            "alcance": "global",
            "subsegmento_id": None,
            "origen": "pregunta",
            "vinculo": "",
            "condicion": None,
        }
        if presentacion is None:
            del campo["presentacion"]
        return {
            "requiere_gps": False,
            "version": 1,
            "canal": "link",
            "items": [
                {
                    "tipo": "grupo",
                    "clave": "g-x",
                    "titulo": "Grupo",
                    "subtitulo": "",
                    "condicion": None,
                    "items": [campo],
                }
            ],
            "globales": [],
            "requisitos": [],
        }

    def _widget(self, definicion):
        form = InscripcionPaso2Form(definicion=definicion, identificacion=_identificacion())
        return form.fields[self.k_pregunta].widget

    def test_selector_con_buscador_usa_select_con_el_engache(self):
        widget = self._widget(self._definicion_con("SELECTOR", "BUSCADOR"))
        self.assertIsInstance(widget, forms.Select)
        self.assertEqual(widget.attrs.get("data-buscador"), "1")
        self.assertIn("data-buscador-placeholder", widget.attrs)

    def test_selector_multiple_con_buscador_deja_de_ser_checkboxes(self):
        widget = self._widget(self._definicion_con("SELECTOR_MULTIPLE", "BUSCADOR"))
        self.assertIsInstance(widget, forms.SelectMultiple)
        self.assertNotIsInstance(widget, forms.CheckboxSelectMultiple)
        self.assertEqual(widget.attrs.get("data-buscador"), "1")

    def test_lista_mantiene_lo_de_siempre(self):
        simple = self._widget(self._definicion_con("SELECTOR", "LISTA"))
        multiple = self._widget(self._definicion_con("SELECTOR_MULTIPLE", "LISTA"))
        self.assertIsInstance(simple, forms.Select)
        self.assertNotIn("data-buscador", simple.attrs)
        self.assertIsInstance(multiple, forms.CheckboxSelectMultiple)

    def test_campo_sin_presentacion_se_lee_como_lista(self):
        """Una definición vieja —o un cliente que no manda la clave— no explota."""
        widget = self._widget(self._definicion_con("SELECTOR", None))
        self.assertNotIn("data-buscador", widget.attrs)

    def test_el_buscador_no_cambia_que_valores_son_validos(self):
        definicion = self._definicion_con("SELECTOR", "BUSCADOR")
        valido = InscripcionPaso2Form(
            {self.k_pregunta: "Secundario"}, definicion=definicion, identificacion=_identificacion()
        )
        self.assertTrue(valido.is_valid(), valido.errors)

        invalido = InscripcionPaso2Form(
            {self.k_pregunta: "Universitario"}, definicion=definicion, identificacion=_identificacion()
        )
        self.assertFalse(invalido.is_valid())
        self.assertIn(self.k_pregunta, invalido.errors)


class Paso2AssetsBuscadorTests(_BasePaso2Test):
    """El control necesita su CSS y su JS en la pantalla; sin ellos el campo
    sigue funcionando como desplegable nativo, pero no habría buscador.

    Se lee el template en vez de pedir la página: el render del test client se
    cae en el entorno local (Python 3.14 + Django 4.2) por un bug ajeno a esto.
    """

    def _template(self, nombre):
        return Path(get_template(nombre).origin.name).read_text(encoding="utf-8")

    def test_el_paso_2_carga_el_buscador_y_el_motor_de_condiciones(self):
        html = self._template("portal/inscripcion/paso2.html")
        self.assertIn("custom/css/nodo-buscador.css", html)
        self.assertIn("custom/js/nodo-buscador.js", html)
        self.assertIn("custom/js/nodo-condiciones.js", html)
        self.assertIn("custom/js/nodo-formulario.js", html)

    def test_el_shell_deja_el_hueco_para_el_css(self):
        html = self._template("portal/inscripcion/base_inscripcion.html")
        self.assertIn("{% block extra_css %}", html)

    def test_los_assets_existen_en_el_repo(self):
        rutas = (
            "custom/css/nodo-buscador.css",
            "custom/js/nodo-buscador.js",
            "custom/js/nodo-condiciones.js",
            "custom/js/nodo-formulario.js",
        )
        for ruta in rutas:
            with self.subTest(ruta=ruta):
                self.assertIsNotNone(finders.find(ruta), f"falta {ruta}")

    def test_el_select_configurado_se_renderiza_con_el_enganche(self):
        PreguntaGlobal.objects.filter(pk=self.pregunta.pk).update(presentacion="BUSCADOR")
        form = InscripcionPaso2Form(
            definicion=definicion_formulario(self.relevamiento),
            identificacion=_identificacion(),
        )
        html = str(form[self.k_pregunta])
        self.assertIn('data-buscador="1"', html)
        self.assertIn("<select", html)


class IngestaConOrigenPadronTests(_BasePaso2Test):
    """Cambio 57: una identificación por padrón crea el caso validado, con su
    origen, y completa la localidad del legajo."""

    def test_origen_padron_valida_y_carga_la_localidad(self):
        from core.models import Localidad, Municipio, Provincia

        provincia = Provincia.objects.create(nombre="Chaco")
        municipio = Municipio.objects.create(nombre="San Fernando", provincia=provincia)
        resistencia = Localidad.objects.create(nombre="Resistencia", municipio=municipio)
        ident = _identificacion(
            origen="padron",
            datos={
                "nombre": "María Luján",
                "apellido": "Gómez",
                "fecha_nacimiento": "1991-03-14",
                "localidad_id": resistencia.pk,
            },
        )
        form = self._form(identificacion=ident)
        self.assertTrue(form.is_valid(), form.errors)
        formulario, creado = crear_formulario_publico(
            self.relevamiento, identificacion=ident, form=form, client_uuid=str(uuid4())
        )
        self.assertTrue(creado)
        self.assertTrue(formulario.validado_renaper)
        self.assertEqual(formulario.origen_validacion, Formulario.OrigenValidacion.PADRON)
        self.assertEqual(formulario.ciudadano.nombre, "María Luján")
        self.assertEqual(formulario.ciudadano.localidad, resistencia)

    def test_origen_manual_sigue_sin_validar(self):
        ident = _identificacion(origen="manual")
        form = self._form(identificacion=ident, data=self._datos_manuales())
        self.assertTrue(form.is_valid(), form.errors)
        formulario, _ = crear_formulario_publico(
            self.relevamiento, identificacion=ident, form=form, client_uuid=str(uuid4())
        )
        self.assertFalse(formulario.validado_renaper)
        self.assertEqual(formulario.origen_validacion, "")
