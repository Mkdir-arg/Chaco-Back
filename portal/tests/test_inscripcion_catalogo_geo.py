"""Cambio 418 en el link público: Provincia y Localidad del catálogo en el paso 2."""

from django.core.cache import cache
from django.urls import reverse

from portal.forms.inscripcion import InscripcionPaso2Form
from portal.services.inscripcion import clave_sesion
from portal.tests.test_inscripcion_envio import _BasePaso2Test, _identificacion
from programas.models import CanalFormulario, PreguntaGlobal
from programas.services.becas import definicion_formulario
from programas.services.diseno import clave_pregunta
from programas.tests.test_preguntas_catalogo_geo import crear_par, sembrar_catalogo


class _BaseGeoTest(_BasePaso2Test):
    def setUp(self):
        super().setUp()
        cache.clear()
        sembrar_catalogo()
        self.provincia, self.localidad = crear_par(obligatorio=True)
        self.definicion = definicion_formulario(self.relevamiento)
        self.k_prov, self.k_loc = clave_pregunta(self.provincia), clave_pregunta(self.localidad)

    def _form_geo(self, provincia, localidad):
        return self._form(data=self._data(**{self.k_prov: provincia, self.k_loc: localidad}))


class Paso2FormCatalogoTests(_BaseGeoTest):
    def test_las_opciones_de_provincia_salen_del_catalogo_no_de_la_foto(self):
        form = self._form()
        self.assertEqual([valor for valor, _ in form.fields[self.k_prov].choices], ["", "Chaco", "Corrientes"])

    def test_acepta_la_localidad_de_la_provincia_elegida(self):
        form = self._form_geo("Chaco", "Resistencia")
        self.assertTrue(form.is_valid(), form.errors)
        respuestas = form.respuestas()
        self.assertEqual(respuestas[self.k_prov], "Chaco")
        self.assertEqual(respuestas[self.k_loc], "Resistencia")

    def test_rechaza_una_localidad_de_otra_provincia(self):
        form = self._form_geo("Chaco", "Corrientes")
        self.assertFalse(form.is_valid())
        self.assertIn(self.k_loc, form.errors)
        self.assertIn("no pertenece a la provincia", form.errors[self.k_loc][0])

    def test_rechaza_una_localidad_que_no_existe(self):
        form = self._form_geo("Chaco", "Atlantis")
        self.assertFalse(form.is_valid())
        self.assertIn(self.k_loc, form.errors)

    def test_rechaza_una_provincia_que_no_existe(self):
        form = self._form_geo("Narnia", "Resistencia")
        self.assertFalse(form.is_valid())
        self.assertIn(self.k_prov, form.errors)

    def test_sin_la_provincia_en_el_canal_no_se_valida_la_pertenencia(self):
        """La Provincia solo se pide en la app: en el link no hay contra qué cruzar."""
        PreguntaGlobal.objects.filter(pk=self.provincia.pk).update(canal=CanalFormulario.APP)
        definicion = definicion_formulario(self.relevamiento)
        form = InscripcionPaso2Form(
            self._data(**{self.k_loc: "Corrientes"}),
            self._files(),
            definicion=definicion,
            identificacion=_identificacion(),
        )
        self.assertNotIn(self.k_prov, form.fields)
        self.assertTrue(form.is_valid(), form.errors)

    def test_con_la_provincia_oculta_por_condicion_no_se_valida_la_pertenencia(self):
        from programas.models import ItemDiseno
        from programas.services.diseno import obtener_o_crear_diseno

        diseno, _ = obtener_o_crear_diseno(self.convocatoria)
        # La condición depende de una respuesta que no se da: el ítem queda oculto.
        ItemDiseno.objects.filter(diseno=diseno, clave=self.k_prov).update(
            condicion={"modo": "todas", "reglas": [{"fuente": self.k_pregunta, "op": "igual", "valor": "Nunca"}]}
        )
        definicion = definicion_formulario(self.relevamiento)
        form = InscripcionPaso2Form(
            self._data(**{self.k_prov: "Chaco", self.k_loc: "Corrientes", self.k_pregunta: "Sí"}),
            self._files(),
            definicion=definicion,
            identificacion=_identificacion(),
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertNotIn(self.k_prov, form.respuestas())


class Paso2VistaCatalogoTests(_BaseGeoTest):
    def _url(self):
        return reverse("portal:inscripcion_paso2", kwargs={"token": self.relevamiento.token_publico})

    def _sembrar_sesion(self):
        session = self.client.session
        session[clave_sesion(self.relevamiento)] = _identificacion()
        session.save()

    def test_el_get_embebe_el_catalogo_y_el_script_de_la_cascada(self):
        self._sembrar_sesion()
        html = self.client.get(self._url()).content.decode()
        self.assertIn('id="catalogos-geo"', html)
        self.assertIn("nodo-cascada-geo.js", html)
        self.assertIn(f'data-geo-provincia="{self.k_prov}"', html)
        self.assertIn('data-geo="provincia"', html)
        # Las localidades NO se renderizan como <option>: las llena el navegador.
        self.assertNotIn(">Resistencia</option>", html)

    def test_sin_preguntas_de_catalogo_la_pagina_no_cambia(self):
        PreguntaGlobal.objects.filter(pk__in=[self.provincia.pk, self.localidad.pk]).update(activo=False)
        self._sembrar_sesion()
        html = self.client.get(self._url()).content.decode()
        self.assertNotIn("catalogos-geo", html)
        self.assertNotIn("nodo-cascada-geo.js", html)

    def test_el_post_con_par_incoherente_vuelve_con_el_error_y_la_localidad_elegida(self):
        self._sembrar_sesion()
        datos = {**self._data(**{self.k_prov: "Chaco", self.k_loc: "Corrientes"}), **self._files()}
        resp = self.client.post(self._url(), datos)
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn("no pertenece a la provincia elegida", html)
        self.assertIn('data-geo-valor="Corrientes"', html)
        self.assertEqual(self.relevamiento.formularios.count(), 0)

    def test_el_post_con_par_correcto_crea_el_caso(self):
        """También cubre R4: el POST no queda como «el formulario cambió» por el catálogo."""
        self._sembrar_sesion()
        self.client.get(self._url())
        datos = {**self._data(**{self.k_prov: "Chaco", self.k_loc: "Resistencia"}), **self._files()}
        resp = self.client.post(self._url(), datos)
        self.assertEqual(resp.status_code, 302)
        caso = self.relevamiento.formularios.get()
        self.assertEqual(caso.respuestas[self.k_loc], "Resistencia")
        self.assertNotIn("catalogos", caso.definicion)
