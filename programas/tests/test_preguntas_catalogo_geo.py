"""Cambio 418: Provincia y Localidad del domicilio como preguntas de Requisitos
generales, con las opciones en el catálogo geográfico de ``core``."""

import json
from uuid import uuid4

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from core.models import Localidad, Municipio, Provincia
from programas.forms import PreguntaGlobalForm
from programas.models import Formulario, PreguntaGlobal, Relevamiento, RequisitoNativo, TipoCampo
from programas.services.becas import definicion_formulario
from programas.services.dashboard_becas import _armar_distribucion, _opciones_texto
from programas.services.respuestas import foto_definicion, huella_definicion
from programas.tests.test_app_de_campo import _CampoBase

Fuente = PreguntaGlobal.FuenteOpciones


def sembrar_catalogo():
    chaco = Provincia.objects.create(nombre="Chaco")
    corrientes = Provincia.objects.create(nombre="Corrientes")
    m_chaco = Municipio.objects.create(nombre="San Fernando", provincia=chaco)
    m_chaco2 = Municipio.objects.create(nombre="Barranqueras", provincia=chaco)
    m_corr = Municipio.objects.create(nombre="Capital", provincia=corrientes)
    # «San Antonio» se repite entre municipios de la misma provincia: sale una vez.
    Localidad.objects.create(nombre="Resistencia", municipio=m_chaco)
    Localidad.objects.create(nombre="San Antonio", municipio=m_chaco)
    Localidad.objects.create(nombre="San Antonio", municipio=m_chaco2)
    Localidad.objects.create(nombre="Barranqueras", municipio=m_chaco2)
    Localidad.objects.create(nombre="Corrientes", municipio=m_corr)
    return chaco, corrientes


def crear_par(**extra):
    provincia = PreguntaGlobal.objects.create(
        texto="Provincia del domicilio", tipo="SELECTOR", fuente_opciones=Fuente.PROVINCIA, orden=50, **extra
    )
    localidad = PreguntaGlobal.objects.create(
        texto="Localidad del domicilio",
        tipo="SELECTOR",
        fuente_opciones=Fuente.LOCALIDAD,
        depende_de=provincia,
        orden=51,
        **extra,
    )
    return provincia, localidad


def datos_form(**extra):
    datos = {"texto": "Pregunta", "tipo": "STRING", "presentacion": "LISTA", "canal": "ambos", "obligatorio": "on"}
    datos.update(extra)
    return datos


class AbmPreguntaCatalogoTests(TestCase):
    def setUp(self):
        from django.core.management import call_command

        call_command("seed_becas", stdout=__import__("io").StringIO())
        sembrar_catalogo()

    def test_con_fuente_no_se_piden_opciones_y_el_tipo_es_selector(self):
        form = PreguntaGlobalForm(datos_form(tipo="STRING", fuente_opciones=Fuente.PROVINCIA))
        self.assertTrue(form.is_valid(), form.errors)
        pregunta = form.save()
        self.assertEqual(pregunta.tipo, TipoCampo.SELECTOR)
        self.assertIsNone(pregunta.opciones)
        self.assertEqual(pregunta.presentacion, "LISTA")

    def test_con_fuente_no_se_guardan_opciones_aunque_lleguen(self):
        form = PreguntaGlobalForm(
            datos_form(tipo="SELECTOR", fuente_opciones=Fuente.PROVINCIA, opciones_texto="Uno\nDos")
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.save().opciones)

    def test_sin_fuente_un_selector_sigue_exigiendo_opciones(self):
        form = PreguntaGlobalForm(datos_form(tipo="SELECTOR"))
        self.assertFalse(form.is_valid())
        self.assertIn("opciones_texto", form.errors)

    def test_localidad_sin_depende_de_es_invalida(self):
        form = PreguntaGlobalForm(datos_form(fuente_opciones=Fuente.LOCALIDAD))
        self.assertFalse(form.is_valid())
        self.assertIn("depende_de", form.errors)

    def test_localidad_depende_de_una_pregunta_de_provincia(self):
        otra = PreguntaGlobal.objects.create(texto="Otra", tipo="SELECTOR", opciones=["a"], orden=60)
        form = PreguntaGlobalForm(datos_form(fuente_opciones=Fuente.LOCALIDAD, depende_de=otra.pk))
        self.assertFalse(form.is_valid())
        self.assertIn("depende_de", form.errors)

    def test_localidad_con_su_provincia_es_valida(self):
        provincia, _ = crear_par()
        form = PreguntaGlobalForm(datos_form(fuente_opciones=Fuente.LOCALIDAD, depende_de=provincia.pk))
        self.assertTrue(form.is_valid(), form.errors)

    def test_el_form_no_desactiva_una_provincia_con_localidad_activa(self):
        provincia, _ = crear_par()
        form = PreguntaGlobalForm(
            datos_form(texto=provincia.texto, tipo="SELECTOR", fuente_opciones=Fuente.PROVINCIA),
            instance=provincia,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("activo", form.errors)
        activa = datos_form(texto=provincia.texto, tipo="SELECTOR", fuente_opciones=Fuente.PROVINCIA, activo="on")
        self.assertTrue(PreguntaGlobalForm(activa, instance=provincia).is_valid())

    def test_el_form_no_activa_una_localidad_con_su_provincia_inactiva(self):
        provincia, localidad = crear_par()
        PreguntaGlobal.objects.filter(pk=provincia.pk).update(activo=False)
        datos = datos_form(
            texto=localidad.texto,
            tipo="SELECTOR",
            fuente_opciones=Fuente.LOCALIDAD,
            depende_de=provincia.pk,
            activo="on",
        )
        form = PreguntaGlobalForm(datos, instance=localidad)
        self.assertFalse(form.is_valid())
        self.assertIn("activo", form.errors)

    def test_provincia_no_lleva_depende_de(self):
        provincia, _ = crear_par()
        form = PreguntaGlobalForm(datos_form(fuente_opciones=Fuente.PROVINCIA, depende_de=provincia.pk))
        self.assertFalse(form.is_valid())
        self.assertIn("depende_de", form.errors)

    def test_una_provincia_con_localidades_no_deja_de_serlo(self):
        provincia, _ = crear_par()
        form = PreguntaGlobalForm(
            datos_form(tipo="SELECTOR", opciones_texto="a", fuente_opciones=""), instance=provincia
        )
        self.assertFalse(form.is_valid())
        self.assertIn("fuente_opciones", form.errors)

    def test_aviso_si_un_requisito_nativo_ya_alimenta_el_mismo_destino(self):
        RequisitoNativo.objects.create(
            texto="Provincia", tipo="STRING", destino_siis="prov_actual", programa=None, segmento=None
        )
        form = PreguntaGlobalForm(datos_form(fuente_opciones=Fuente.PROVINCIA, destino_siis="prov_actual"))
        self.assertFalse(form.is_valid())
        self.assertIn("destino_siis", form.errors)
        self.assertIn("prioridad", form.errors["destino_siis"][0])

    def test_sin_requisito_nativo_el_destino_se_acepta(self):
        form = PreguntaGlobalForm(datos_form(fuente_opciones=Fuente.PROVINCIA, destino_siis="prov_actual"))
        self.assertTrue(form.is_valid(), form.errors)

    def test_el_destino_de_otro_dominio_no_choca_con_el_requisito(self):
        RequisitoNativo.objects.create(texto="Barrio", tipo="STRING", destino_siis="barrio_actual")
        form = PreguntaGlobalForm(datos_form(fuente_opciones=Fuente.PROVINCIA, destino_siis="prov_actual"))
        self.assertTrue(form.is_valid(), form.errors)


class EliminarYActivarTests(TestCase):
    def setUp(self):
        from django.core.management import call_command

        call_command("seed_becas", stdout=__import__("io").StringIO())
        self.admin = User.objects.create_superuser("admin-geo", "a@a.com", "x")
        self.client.force_login(self.admin)
        self.provincia, self.localidad = crear_par()

    def _mensajes(self, resp):
        return [str(m) for m in resp.wsgi_request._messages]

    def test_eliminar_la_provincia_con_localidad_dependiente_tiene_mensaje_propio(self):
        resp = self.client.post(reverse("becas:pregunta_eliminar", args=[self.provincia.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(PreguntaGlobal.objects.filter(pk=self.provincia.pk).exists())
        texto = " ".join(self._mensajes(resp))
        self.assertIn("(Localidad) depende de ésta", texto)
        self.assertNotIn("subieron este documento", texto)

    def test_eliminar_la_localidad_y_despues_la_provincia(self):
        self.client.post(reverse("becas:pregunta_eliminar", args=[self.localidad.pk]))
        self.client.post(reverse("becas:pregunta_eliminar", args=[self.provincia.pk]))
        self.assertFalse(PreguntaGlobal.objects.filter(pk__in=[self.provincia.pk, self.localidad.pk]).exists())

    def test_set_null_no_levanta_protected_error_al_borrar_por_el_orm(self):
        """Con ``SET_NULL`` el borrado directo no se frena: la guarda es de la vista."""
        self.provincia.delete()
        self.localidad.refresh_from_db()
        self.assertIsNone(self.localidad.depende_de_id)

    def test_no_se_desactiva_la_provincia_con_localidad_activa(self):
        self.client.post(reverse("becas:pregunta_toggle", args=[self.provincia.pk]))
        self.provincia.refresh_from_db()
        self.assertTrue(self.provincia.activo)

    def test_no_se_activa_la_localidad_con_su_provincia_inactiva(self):
        PreguntaGlobal.objects.filter(pk__in=[self.provincia.pk, self.localidad.pk]).update(activo=False)
        self.client.post(reverse("becas:pregunta_toggle", args=[self.localidad.pk]))
        self.localidad.refresh_from_db()
        self.assertFalse(self.localidad.activo)


class DefinicionConCatalogoTests(_CampoBase):
    def setUp(self):
        super().setUp()
        cache.clear()
        sembrar_catalogo()

    def test_sin_preguntas_de_catalogo_la_definicion_no_cambia(self):
        definicion = definicion_formulario(self.rel)
        self.assertNotIn("catalogos", definicion)
        for campo in definicion["globales"]:
            self.assertNotIn("fuente_opciones", campo)
            self.assertNotIn("depende_de", campo)

    def test_inactivas_no_activan_el_catalogo(self):
        crear_par(activo=False)
        self.assertNotIn("catalogos", definicion_formulario(self.rel))

    def test_una_localidad_cuya_provincia_no_se_sirve_en_el_canal_sale_como_texto(self):
        provincia, localidad = crear_par()
        PreguntaGlobal.objects.filter(pk=provincia.pk).update(canal="link")  # el relevamiento de la prueba es de la app
        definicion = definicion_formulario(self.rel)
        campos = [c for g in definicion["items"] for c in g["items"] if c.get("tipo_item") == "campo"]
        loc = next(c for c in campos if c["clave"] == f"pg-{localidad.pk}")
        self.assertEqual(loc["tipo"], TipoCampo.STRING)
        self.assertNotIn("fuente_opciones", loc)
        self.assertNotIn("depende_de", loc)
        glob = next(c for c in definicion["globales"] if c["id"] == localidad.pk)
        self.assertEqual(glob["tipo"], TipoCampo.STRING)
        self.assertNotIn("catalogos", definicion)

    def test_el_campo_expone_fuente_y_dependencia_y_el_catalogo_va_arriba(self):
        provincia, localidad = crear_par()
        definicion = definicion_formulario(self.rel)
        por_clave = {c["clave"]: c for g in definicion["items"] for c in g["items"] if c.get("tipo_item") == "campo"}
        self.assertEqual(por_clave[f"pg-{provincia.pk}"]["fuente_opciones"], "provincia")
        self.assertNotIn("depende_de", por_clave[f"pg-{provincia.pk}"])
        self.assertEqual(por_clave[f"pg-{localidad.pk}"]["fuente_opciones"], "localidad")
        self.assertEqual(por_clave[f"pg-{localidad.pk}"]["depende_de"], f"pg-{provincia.pk}")
        self.assertEqual(por_clave[f"pg-{localidad.pk}"]["opciones"], [])
        self.assertEqual(
            definicion["catalogos"],
            {
                "provincias": ["Chaco", "Corrientes"],
                "localidades": {
                    "Chaco": ["Barranqueras", "Resistencia", "San Antonio"],
                    "Corrientes": ["Corrientes"],
                },
            },
        )

    def test_el_catalogo_se_lee_una_vez_por_definicion_y_se_cachea(self):
        crear_par()
        definicion_formulario(self.rel)
        with self.assertNumQueries(0 + self._consultas_sin_catalogo()):
            definicion_formulario(self.rel)

    def _consultas_sin_catalogo(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as capturadas:
            definicion_formulario(self.rel, con_catalogos=False)
        return len(capturadas)

    def test_la_foto_y_la_huella_no_llevan_catalogos(self):
        crear_par()
        definicion = definicion_formulario(self.rel)
        self.assertIn("catalogos", definicion)
        foto = foto_definicion(self.rel, definicion)
        self.assertNotIn("catalogos", foto)
        self.assertNotIn("catalogos", json.dumps(foto))
        self.assertNotIn("catalogos", foto_definicion(self.rel))

    def test_la_huella_es_la_misma_en_el_get_y_en_el_post(self):
        """R4: la huella del paso 2 se calcula dos veces (al mostrar y al enviar); con
        el catálogo cambiando de orden entre una y otra no puede variar."""
        crear_par()
        antes = huella_definicion(foto_definicion(self.rel, definicion_formulario(self.rel)))
        cache.clear()
        Localidad.objects.create(nombre="Fontana", municipio=Municipio.objects.get(nombre="San Fernando"))
        despues = huella_definicion(foto_definicion(self.rel, definicion_formulario(self.rel)))
        self.assertEqual(antes, despues)
        self.assertEqual(antes, huella_definicion(foto_definicion(self.rel)))


class ApiCapacidadCatalogosTests(_CampoBase):
    def setUp(self):
        super().setUp()
        cache.clear()
        sembrar_catalogo()
        self.provincia, self.localidad = crear_par()
        self.url_detalle = reverse("becas_api:relevamiento-detail", args=[self.rel.pk])

    def _campos(self, definicion):
        return {c["clave"]: c for g in definicion["items"] for c in g["items"] if c.get("tipo_item") == "campo"}

    def test_sin_capacidad_el_campo_es_texto_y_no_hay_catalogos(self):
        definicion = self.client.get(self.url_detalle).json()["definicion_formulario"]
        self.assertNotIn("catalogos", definicion)
        campos = self._campos(definicion)
        for pregunta in (self.provincia, self.localidad):
            campo = campos[f"pg-{pregunta.pk}"]
            self.assertEqual(campo["tipo"], "STRING")
            self.assertNotIn("fuente_opciones", campo)
            self.assertNotIn("depende_de", campo)
        for campo in definicion["globales"]:
            self.assertNotIn("fuente_opciones", campo)
        tipos_globales = {c["id"]: c["tipo"] for c in definicion["globales"]}
        self.assertEqual(tipos_globales[self.provincia.pk], "STRING")

    def test_con_capacidad_es_selector_y_trae_catalogos(self):
        resp = self.client.get(self.url_detalle, HTTP_X_CAPACIDADES="catalogos")
        definicion = resp.json()["definicion_formulario"]
        self.assertIn("catalogos", definicion)
        campos = self._campos(definicion)
        self.assertEqual(campos[f"pg-{self.provincia.pk}"]["tipo"], "SELECTOR")
        self.assertEqual(campos[f"pg-{self.localidad.pk}"]["depende_de"], f"pg-{self.provincia.pk}")

    def test_las_claves_de_la_definicion_son_las_del_contrato_mas_catalogos(self):
        from programas.tests.test_becas_api_contrato import CLAVES_DEFINICION, CLAVES_DEFINICION_OPCIONALES

        sin = self.client.get(self.url_detalle).json()["definicion_formulario"]
        con = self.client.get(self.url_detalle, HTTP_X_CAPACIDADES="catalogos").json()["definicion_formulario"]
        self.assertEqual(sorted(sin), sorted(CLAVES_DEFINICION))
        self.assertEqual(sorted(con), sorted([*CLAVES_DEFINICION, *CLAVES_DEFINICION_OPCIONALES]))

    def test_la_capacidad_tambien_se_declara_por_query(self):
        resp = self.client.get(self.url_detalle, {"capacidades": "otra, Catalogos"})
        self.assertIn("catalogos", resp.json()["definicion_formulario"])

    def test_otra_capacidad_no_habilita_los_catalogos(self):
        resp = self.client.get(self.url_detalle, HTTP_X_CAPACIDADES="otra")
        self.assertNotIn("catalogos", resp.json()["definicion_formulario"])


class AltaApiConParDeCatalogoTests(_CampoBase):
    def setUp(self):
        super().setUp()
        cache.clear()
        sembrar_catalogo()
        self.rel.estado = Relevamiento.Estado.EN_CURSO
        self.rel.save(update_fields=["estado", "modificado"])
        self.provincia, self.localidad = crear_par(obligatorio=False)
        self.k_provincia, self.k_localidad = f"pg-{self.provincia.pk}", f"pg-{self.localidad.pk}"

    def _alta(self, provincia, localidad):
        from programas.services.respuestas import foto_definicion, respuestas_desde_legacy

        payload = self._payload(client_uuid=str(uuid4()))
        respuestas = respuestas_desde_legacy(
            payload["data"], payload, payload["datos_identificacion"], foto_definicion(self.rel)
        )
        respuestas[self.k_provincia] = provincia
        respuestas[self.k_localidad] = localidad
        payload["respuestas"] = respuestas
        return self.client.post(self.url, payload, format="json")

    def test_par_coherente_se_guarda_sin_observacion(self):
        resp = self._alta("Chaco", "Resistencia")
        self.assertEqual(resp.status_code, 201, resp.data)
        caso = Formulario.objects.get(pk=resp.data["id"])
        self.assertEqual(caso.respuestas[self.k_localidad], "Resistencia")
        self.assertIn(caso.observaciones_carga, (None, ""))

    def test_par_incoherente_se_guarda_y_deja_una_observacion(self):
        resp = self._alta("Chaco", "Corrientes")
        self.assertEqual(resp.status_code, 201, resp.data)
        caso = Formulario.objects.get(pk=resp.data["id"])
        self.assertEqual(caso.respuestas[self.k_provincia], "Chaco")
        self.assertEqual(caso.respuestas[self.k_localidad], "Corrientes")
        self.assertIn("localidad que no es de la provincia", caso.observaciones_carga)

    def test_la_foto_persistida_no_lleva_catalogos(self):
        resp = self._alta("Chaco", "Resistencia")
        caso = Formulario.objects.get(pk=resp.data["id"])
        self.assertNotIn("catalogos", caso.definicion)
        self.assertNotIn("catalogos", json.dumps(caso.definicion))
        self.assertIn(self.k_localidad, json.dumps(caso.definicion))


class DashboardConCatalogoTests(TestCase):
    def test_sin_opciones_fijas_solo_se_muestra_lo_observado(self):
        provincia = PreguntaGlobal.objects.create(
            texto="Provincia", tipo="SELECTOR", fuente_opciones=Fuente.PROVINCIA, orden=70
        )
        self.assertEqual(_opciones_texto(provincia.opciones), [])

        class _P:
            clave, texto, tipo, origen, multiple = "global:1", "Provincia", "Selector", "Pregunta general", False
            opciones = []

        distribucion = _armar_distribucion(_P, {"Chaco": 3, "Corrientes": 1}, 4)
        self.assertEqual([o["opcion"] for o in distribucion.opciones], ["Chaco", "Corrientes"])
        self.assertEqual(len(distribucion.opciones), 2)


class ModalesDelListadoConCatalogoTests(TestCase):
    """Cambio 445: el PM crea y edita desde los modales del listado, no desde la página completa."""

    AJAX = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}

    def setUp(self):
        from django.core.management import call_command

        call_command("seed_becas", stdout=__import__("io").StringIO())
        self.admin = User.objects.create_superuser("admin-modal-geo", "a@a.com", "x")
        self.client.force_login(self.admin)

    def _listado(self):
        resp = self.client.get(reverse("becas:preguntas"))
        self.assertEqual(resp.status_code, 200)
        return resp

    def test_los_dos_modales_traen_la_fuente_y_la_dependencia_con_las_choices_del_servidor(self):
        provincia, _ = crear_par()
        html = self._listado().content.decode()
        # Un par de selectores por modal (alta y edición).
        self.assertEqual(html.count('name="fuente_opciones"'), 2)
        self.assertEqual(html.count('name="depende_de"'), 2)
        for valor, etiqueta in [("", "Opciones cargadas a mano")] + list(Fuente.choices):
            self.assertEqual(html.count(f'<option value="{valor}">{etiqueta}</option>'), 2)
        # Solo las preguntas de Provincia son candidatas a «Depende de».
        self.assertEqual(html.count(f'<option value="{provincia.pk}">{provincia.texto}</option>'), 2)

    def test_depende_de_no_ofrece_preguntas_que_no_son_de_provincia(self):
        _, localidad = crear_par()
        html = self._listado().content.decode()
        self.assertNotIn(f'<option value="{localidad.pk}">{localidad.texto}</option>', html)

    def test_la_fila_precarga_la_fuente_y_la_dependencia_en_el_modal_de_edicion(self):
        provincia, localidad = crear_par()
        html = self._listado().content.decode()
        self.assertIn(f"'{Fuente.LOCALIDAD}',\n          '{provincia.pk}'", html.replace("\r\n", "\n"))
        self.assertIn(f"'{Fuente.PROVINCIA}',\n          ''", html.replace("\r\n", "\n"))
        self.assertIn(reverse("becas:pregunta_editar", args=[localidad.pk]), html)

    def test_alta_con_fuente_provincia_crea_la_pregunta_inactiva_y_con_fuente(self):
        resp = self.client.post(
            reverse("becas:pregunta_crear"),
            datos_form(texto="Provincia", fuente_opciones=Fuente.PROVINCIA, activo="on"),
            **self.AJAX,
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        pregunta = PreguntaGlobal.objects.get(texto="Provincia")
        self.assertEqual(pregunta.fuente_opciones, Fuente.PROVINCIA)
        self.assertEqual(pregunta.tipo, TipoCampo.SELECTOR)
        self.assertFalse(pregunta.activo)

    def test_alta_de_localidad_con_su_provincia_nace_inactiva(self):
        provincia = PreguntaGlobal.objects.create(
            texto="Provincia", tipo="SELECTOR", fuente_opciones=Fuente.PROVINCIA, orden=70
        )
        resp = self.client.post(
            reverse("becas:pregunta_crear"),
            datos_form(texto="Localidad", fuente_opciones=Fuente.LOCALIDAD, depende_de=provincia.pk, activo="on"),
            **self.AJAX,
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        localidad = PreguntaGlobal.objects.get(texto="Localidad")
        self.assertEqual(localidad.depende_de_id, provincia.pk)
        self.assertFalse(localidad.activo)

    def test_alta_comun_sigue_naciendo_activa(self):
        resp = self.client.post(reverse("becas:pregunta_crear"), datos_form(texto="Común", activo="on"), **self.AJAX)
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(PreguntaGlobal.objects.get(texto="Común").activo)

    def test_los_errores_del_servidor_llegan_al_modal_por_campo(self):
        resp = self.client.post(
            reverse("becas:pregunta_crear"),
            datos_form(texto="Localidad", fuente_opciones=Fuente.LOCALIDAD),
            **self.AJAX,
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("depende_de", resp.json()["errors"])
        # Y el modal tiene dónde mostrarlo: un <p data-error> por campo, en alta y en edición.
        html = self._listado().content.decode()
        self.assertEqual(html.count('data-error="depende_de"'), 2)
        self.assertEqual(html.count('data-error="fuente_opciones"'), 2)
