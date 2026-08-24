"""Tests del paso 2 y la ingesta del formulario público (#294/#295, análisis #289)."""

from datetime import date, timedelta
from uuid import uuid4

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from legajos.models import Ciudadano
from portal.forms.inscripcion import InscripcionPaso2Form
from portal.services.inscripcion import clave_sesion
from programas.models import (
    AdjuntoFormulario,
    Convocatoria,
    Formulario,
    PreguntaGlobal,
    Relevamiento,
    RequisitoNativo,
    Segmento,
)
from programas.services.becas import definicion_formulario
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


class _BasePaso2Test(TestCase):
    def setUp(self):
        cache.clear()
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

    def _data(self, **extra):
        data = {
            "celular": "3624123456",
            "email_contacto": "maria@correo.com",
            f"g_{self.pregunta.pk}": "Sí",
        }
        data.update(extra)
        return data

    def _files(self, **extra):
        files = {f"r_{self.requisito.pk}": SimpleUploadedFile("cert.png", b"\x89PNG fake", content_type="image/png")}
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
    def test_construye_los_campos_de_la_definicion(self):
        form = self._form()
        self.assertIn(f"g_{self.pregunta.pk}", form.fields)
        self.assertIn(f"r_{self.requisito.pk}", form.fields)
        self.assertNotIn("nombre", form.fields)  # identidad validada: no se pide

    def test_origen_manual_pide_identidad(self):
        form = self._form(
            identificacion=_identificacion(origen="manual"),
            data=self._data(nombre="Juan", apellido="Pérez", fecha_nacimiento="1990-01-01"),
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_obligatorios_dinamicos_se_exigen(self):
        data = self._data()
        data.pop(f"g_{self.pregunta.pk}")
        form = self._form(data=data, files={})
        self.assertFalse(form.is_valid())
        self.assertIn(f"g_{self.pregunta.pk}", form.errors)
        self.assertIn(f"r_{self.requisito.pk}", form.errors)

    def test_opcion_invalida_de_selector_se_rechaza(self):
        form = self._form(data=self._data(**{f"g_{self.pregunta.pk}": "Otra cosa"}))
        self.assertFalse(form.is_valid())
        self.assertIn(f"g_{self.pregunta.pk}", form.errors)

    def test_respuestas_ignoran_ids_ajenos_a_la_definicion(self):
        form = self._form(data=self._data(g_99999="hack", r_99999="hack"))
        self.assertTrue(form.is_valid(), form.errors)
        data = form.respuestas()
        self.assertNotIn("99999", data["globales"])
        self.assertNotIn("99999", data["requisitos"])
        self.assertEqual(data["globales"][str(self.pregunta.pk)], "Sí")
        self.assertEqual(data["requisitos"][str(self.requisito.pk)], "cert.png")

    def test_archivo_invalido_se_rechaza(self):
        exe = SimpleUploadedFile("virus.exe", b"MZ", content_type="application/octet-stream")
        form = self._form(files={f"r_{self.requisito.pk}": exe})
        self.assertFalse(form.is_valid())
        self.assertIn(f"r_{self.requisito.pk}", form.errors)
        gigante = SimpleUploadedFile("foto.png", b"0" * (5 * 1024 * 1024 + 1), content_type="image/png")
        form = self._form(files={f"r_{self.requisito.pk}": gigante})
        self.assertFalse(form.is_valid())

    def test_menor_exige_apoderado_y_mayor_no(self):
        hoy = timezone.localdate()
        menor = _identificacion()
        menor["datos"]["fecha_nacimiento"] = (hoy - timedelta(days=17 * 365)).isoformat()
        form = self._form(identificacion=menor)
        self.assertFalse(form.is_valid())
        self.assertIn("apoderado_dni", form.errors)
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
                apoderado_nombre="Ana",
                apoderado_apellido="Gómez",
                apoderado_dni="20.111.222",
                apoderado_genero="F",
                apoderado_fecha_nacimiento="1980-05-05",
            ),
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["apoderado_dni"], "20111222")


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
        self.assertEqual(formulario.data["globales"][str(self.pregunta.pk)], "Sí")
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
        form = self._form(
            identificacion=ident,
            data=self._data(nombre="Juan", apellido="Pérez", fecha_nacimiento="1990-01-01"),
        )
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

    def test_confirmacion_sin_envio_redirige_al_paso1(self):
        resp = self.client.get(reverse("portal:inscripcion_confirmacion", kwargs={"token": self.relevamiento.token_publico}))
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
