"""Catálogo de requisitos generales agrupado, con orígenes y canal (Cambio 58,
Fase 1: tasks #336 y #338, análisis #326)."""

from datetime import date, timedelta
from io import StringIO

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from programas.forms import PreguntaGlobalForm, RequisitoNativoForm
from programas.management.commands.seed_becas import ROL_ADMIN
from programas.models import (
    VINCULOS_LEGAJO,
    CanalFormulario,
    Convocatoria,
    GrupoRequisito,
    OrigenRequisito,
    PreguntaGlobal,
    Relevamiento,
    RequisitoNativo,
    Segmento,
    TipoCampo,
)
from programas.services.becas import definicion_formulario, get_campos_formulario


def _seed():
    call_command("seed_becas", stdout=StringIO())


class SeedCatalogoProtegidoTests(TestCase):
    def test_siembra_los_grupos_y_los_campos_vinculados(self):
        _seed()
        claves = list(GrupoRequisito.objects.order_by("orden").values_list("clave", flat=True))
        self.assertEqual(claves, ["datos_personales", "contacto", "apoderado", "cuestionario"])
        self.assertEqual(GrupoRequisito.objects.filter(protegido=True).count(), 3)
        apoderado = GrupoRequisito.objects.get(clave="apoderado")
        self.assertEqual(apoderado.condicion_defecto["reglas"][0]["op"], "edad_menor")
        self.assertEqual(apoderado.condicion_defecto["reglas"][0]["valor"], 18)

        legajo = PreguntaGlobal.objects.filter(origen=OrigenRequisito.LEGAJO)
        self.assertEqual(
            set(legajo.values_list("vinculo", flat=True)),
            {"nombre", "apellido", "dni", "fecha_nacimiento", "genero", "telefono", "email"},
        )
        self.assertEqual(PreguntaGlobal.objects.filter(origen=OrigenRequisito.PERSONA_VINCULADA).count(), 5)
        genero = PreguntaGlobal.objects.get(origen=OrigenRequisito.LEGAJO, vinculo="genero")
        # El tipo y las opciones los dicta el legajo, no el operador (RN-4).
        self.assertEqual(genero.tipo, TipoCampo.SELECTOR)
        self.assertEqual(genero.opciones, ["F", "M"])
        self.assertTrue(genero.protegido)
        self.assertTrue(genero.es_identidad)
        email = PreguntaGlobal.objects.get(origen=OrigenRequisito.LEGAJO, vinculo="email")
        self.assertFalse(email.obligatorio)  # D9: el contacto puede ser opcional
        self.assertFalse(email.es_identidad)

    def test_es_idempotente_y_respeta_lo_editado(self):
        _seed()
        antes = PreguntaGlobal.objects.count()
        celular = PreguntaGlobal.objects.get(origen=OrigenRequisito.LEGAJO, vinculo="telefono")
        celular.texto = "Tu celular"
        celular.save(update_fields=["texto"])
        _seed()
        self.assertEqual(PreguntaGlobal.objects.count(), antes)
        celular.refresh_from_db()
        self.assertEqual(celular.texto, "Tu celular")

    def test_las_preguntas_sin_grupo_caen_en_el_cuestionario(self):
        suelta = PreguntaGlobal.objects.create(texto="¿Trabajás?", tipo=TipoCampo.STRING)
        _seed()
        suelta.refresh_from_db()
        self.assertEqual(suelta.grupo.clave, "cuestionario")
        self.assertTrue(suelta.es_pregunta)
        self.assertFalse(suelta.protegido)

    def test_los_ordenes_de_los_protegidos_no_chocan_con_los_existentes(self):
        PreguntaGlobal.objects.create(texto="Ocupa el 1", tipo=TipoCampo.STRING, orden=1)
        _seed()
        ordenes = list(PreguntaGlobal.objects.values_list("orden", flat=True))
        self.assertEqual(len(ordenes), len(set(ordenes)))

    def test_el_registro_de_vinculos_cubre_lo_sembrado(self):
        for vinculo in ("nombre", "apellido", "dni", "fecha_nacimiento", "genero", "telefono", "email"):
            self.assertIn(vinculo, VINCULOS_LEGAJO)
        self.assertTrue(VINCULOS_LEGAJO["dni"]["solo_lectura"])


class FormProtegidoTests(TestCase):
    def setUp(self):
        _seed()
        self.dni = PreguntaGlobal.objects.get(origen=OrigenRequisito.LEGAJO, vinculo="dni")
        self.email = PreguntaGlobal.objects.get(origen=OrigenRequisito.LEGAJO, vinculo="email")
        self.contacto = GrupoRequisito.objects.get(clave="contacto")

    def _data(self, pregunta, **extra):
        data = {
            "texto": pregunta.texto,
            "tipo": pregunta.tipo,
            "presentacion": pregunta.presentacion,
            "grupo": pregunta.grupo_id,
            "canal": pregunta.canal,
            "orden": pregunta.orden,
            "obligatorio": "on" if pregunta.obligatorio else "",
            "activo": "on" if pregunta.activo else "",
        }
        data.update(extra)
        return data

    def test_un_protegido_no_cambia_de_tipo_ni_de_opciones_por_post(self):
        form = PreguntaGlobalForm(
            self._data(self.dni, tipo=TipoCampo.SELECTOR, opciones_texto="A\nB", texto="Documento"),
            instance=self.dni,
        )
        self.assertTrue(form.is_valid(), form.errors)
        guardado = form.save()
        self.assertEqual(guardado.tipo, TipoCampo.STRING)
        self.assertIsNone(guardado.opciones)
        self.assertEqual(guardado.texto, "Documento")  # la etiqueta sí se edita
        self.assertTrue(form.fields["tipo"].disabled)

    def test_la_identidad_no_se_hace_opcional_ni_se_desactiva(self):
        form = PreguntaGlobalForm(self._data(self.dni, obligatorio="", activo=""), instance=self.dni)
        self.assertTrue(form.is_valid(), form.errors)
        guardado = form.save()
        self.assertTrue(guardado.obligatorio)
        self.assertTrue(guardado.activo)

    def test_el_contacto_si_puede_ser_opcional_y_cambiar_de_grupo(self):
        datos = GrupoRequisito.objects.get(clave="datos_personales")
        form = PreguntaGlobalForm(
            self._data(self.email, obligatorio="", grupo=datos.pk, canal="link"), instance=self.email
        )
        self.assertTrue(form.is_valid(), form.errors)
        guardado = form.save()
        self.assertFalse(guardado.obligatorio)
        self.assertEqual(guardado.grupo, datos)
        self.assertEqual(guardado.canal, CanalFormulario.LINK)

    def test_una_pregunta_nueva_sin_grupo_va_al_cuestionario(self):
        form = PreguntaGlobalForm(
            {
                "texto": "¿Tenés obra social?",
                "tipo": TipoCampo.STRING,
                "canal": "ambos",
                "obligatorio": "on",
                "activo": "on",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().grupo.clave, "cuestionario")

    def test_el_requisito_nativo_declara_canal(self):
        seg = Segmento.objects.create(nombre="Seg", cupo_maximo=10)
        form = RequisitoNativoForm(
            {"texto": "Foto del DNI físico", "tipo": TipoCampo.ARCHIVO, "canal": "app", "obligatorio": "True"},
            segmento=seg,
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save(commit=False).canal, CanalFormulario.APP)


class VistasProtegidasTests(TestCase):
    def setUp(self):
        _seed()
        self.admin = User.objects.create_user("admin_cat", password="x")
        self.admin.groups.add(Group.objects.get(name=ROL_ADMIN))
        self.client.force_login(self.admin)
        self.dni = PreguntaGlobal.objects.get(origen=OrigenRequisito.LEGAJO, vinculo="dni")
        self.email = PreguntaGlobal.objects.get(origen=OrigenRequisito.LEGAJO, vinculo="email")

    def test_no_se_elimina_un_protegido(self):
        self.client.post(reverse("becas:pregunta_eliminar", args=[self.dni.pk]))
        self.assertTrue(PreguntaGlobal.objects.filter(pk=self.dni.pk).exists())

    def test_no_se_desactiva_la_identidad(self):
        self.client.post(reverse("becas:pregunta_toggle", args=[self.dni.pk]))
        self.dni.refresh_from_db()
        self.assertTrue(self.dni.activo)

    def test_el_contacto_si_se_desactiva(self):
        self.client.post(reverse("becas:pregunta_toggle", args=[self.email.pk]))
        self.email.refresh_from_db()
        self.assertFalse(self.email.activo)

    def test_una_pregunta_comun_se_elimina(self):
        comun = PreguntaGlobal.objects.create(texto="X", tipo=TipoCampo.STRING)
        self.client.post(reverse("becas:pregunta_eliminar", args=[comun.pk]))
        self.assertFalse(PreguntaGlobal.objects.filter(pk=comun.pk).exists())


class DefinicionPorCanalTests(TestCase):
    """La definición filtra por el canal del relevamiento y, hasta que el
    diseño por convocatoria los consuma, deja afuera los campos vinculados
    (siguen siendo bloques fijos en el link y en la app)."""

    def setUp(self):
        _seed()
        self.segmento = Segmento.objects.create(nombre="Seg", cupo_maximo=100)
        self.convocatoria = Convocatoria.objects.create(
            nombre="Conv", segmento=self.segmento, fecha_inicio=date(2026, 1, 1), fecha_fin=date(2026, 12, 31)
        )
        self.territorial = User.objects.create_user("terri_canal")
        self.rel_app = Relevamiento.objects.create(
            convocatoria=self.convocatoria,
            territorial=self.territorial,
            fecha_asignada=timezone.now(),
            zona="Zona",
        )
        self.rel_link = Relevamiento.objects.create(
            convocatoria=self.convocatoria,
            tipo=Relevamiento.Tipo.PUBLICO,
            fecha_asignada=timezone.now() - timedelta(days=1),
            fecha_hasta=timezone.now() + timedelta(days=10),
        )
        PreguntaGlobal.objects.create(texto="Solo app", tipo=TipoCampo.ARCHIVO, canal="app", orden=501)
        PreguntaGlobal.objects.create(texto="Solo link", tipo=TipoCampo.STRING, canal="link", orden=502)
        PreguntaGlobal.objects.create(texto="Ambos", tipo=TipoCampo.STRING, canal="ambos", orden=503)
        RequisitoNativo.objects.create(
            texto="Req app", tipo=TipoCampo.STRING, segmento=self.segmento, canal="app", orden=1
        )
        RequisitoNativo.objects.create(
            texto="Req ambos", tipo=TipoCampo.STRING, segmento=self.segmento, canal="ambos", orden=2
        )

    def _textos(self, definicion, clave):
        return [c["texto"] for c in definicion[clave]]

    def test_la_app_recibe_lo_de_app_y_lo_de_ambos(self):
        definicion = definicion_formulario(self.rel_app)
        self.assertEqual(definicion["canal"], "app")
        globales = self._textos(definicion, "globales")
        self.assertIn("Solo app", globales)
        self.assertIn("Ambos", globales)
        self.assertNotIn("Solo link", globales)
        self.assertEqual(self._textos(definicion, "requisitos"), ["Req app", "Req ambos"])

    def test_el_link_recibe_lo_de_link_y_lo_de_ambos(self):
        definicion = definicion_formulario(self.rel_link)
        self.assertEqual(definicion["canal"], "link")
        globales = self._textos(definicion, "globales")
        self.assertIn("Solo link", globales)
        self.assertNotIn("Solo app", globales)
        self.assertEqual(self._textos(definicion, "requisitos"), ["Req ambos"])

    def test_los_campos_vinculados_no_entran_como_preguntas(self):
        """Hasta el diseño por convocatoria, nombre/apellido/etc. siguen siendo
        bloques fijos: si entraran acá se pedirían dos veces."""
        definicion = definicion_formulario(self.rel_link)
        for campo in definicion["globales"]:
            self.assertEqual(campo["origen"], "pregunta")
        self.assertNotIn("DNI", self._textos(definicion, "globales"))

    def test_cada_campo_lleva_canal_origen_y_grupo(self):
        campo = next(c for c in definicion_formulario(self.rel_app)["globales"] if c["texto"] == "Ambos")
        self.assertEqual(campo["canal"], "ambos")
        self.assertEqual(campo["origen"], "pregunta")
        self.assertEqual(campo["grupo"]["clave"], "cuestionario")

    def test_sin_canal_devuelve_todo(self):
        globales, requisitos = get_campos_formulario(self.convocatoria)
        self.assertEqual({p.canal for p in globales} >= {"app", "link", "ambos"}, True)
        self.assertEqual(requisitos.count(), 2)
