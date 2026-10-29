"""Respuestas por clave de ítem, foto de la definición y puente con el contrato
anterior (Cambio 58, Fase 4: tasks #345, #346 y #347, análisis #326)."""

from datetime import date, timedelta
from io import StringIO

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from legajos.models import Ciudadano
from programas.management.commands.seed_becas import ROL_ADMIN, ROL_TERRITORIAL
from programas.models import (
    Convocatoria,
    DisenoFormulario,
    Formulario,
    GrupoRequisito,
    OrigenRequisito,
    PreguntaGlobal,
    Relevamiento,
    RequisitoNativo,
    Segmento,
    TipoCampo,
)
from programas.services.becas import definicion_formulario
from programas.services.diseno import clave_pregunta, clave_requisito
from programas.services.respuestas import (
    campos_de,
    foto_definicion,
    identidad_desde_respuestas,
    legacy_desde_respuestas,
    legible,
    respuestas_desde_legacy,
    respuestas_legibles,
    sincronizar_desde_legacy,
)


class LegibleFechaTests(TestCase):
    """`legible` con un DATE: dd/mm/aaaa, y lo que no es una fecha válida queda tal cual
    (una fecha ISO imposible no puede levantar ValueError)."""

    def test_fecha_valida_imposible_y_otro_formato(self):
        item = {"tipo": "DATE"}
        self.assertEqual(legible(item, "2005-03-14"), "14/03/2005")
        self.assertEqual(legible(item, "2000-02-30"), "2000-02-30")
        self.assertEqual(legible(item, "1990-13-01"), "1990-13-01")
        self.assertEqual(legible(item, "15/03/2010"), "15/03/2010")


class _Base(TestCase):
    def setUp(self):
        call_command("seed_becas", stdout=StringIO())
        self.segmento = Segmento.objects.create(nombre="Educación", cupo_maximo=100)
        self.convocatoria = Convocatoria.objects.create(
            nombre="Becas 2026", segmento=self.segmento, fecha_inicio=date(2026, 1, 1), fecha_fin=date(2026, 12, 31)
        )
        self.nivel = RequisitoNativo.objects.create(
            texto="Nivel educativo",
            tipo=TipoCampo.SELECTOR,
            opciones=["Primario", "Secundario"],
            segmento=self.segmento,
            orden=1,
        )
        self.tenencia = PreguntaGlobal.objects.create(
            texto="Tenencia de la vivienda", tipo=TipoCampo.SELECTOR, opciones=["Propia", "Alquilada"], orden=600
        )
        self.territorial = User.objects.create_user("terri-resp", password="x")
        self.territorial.groups.add(Group.objects.get(name=ROL_TERRITORIAL))
        self.relevamiento = Relevamiento.objects.create(
            convocatoria=self.convocatoria,
            territorial=self.territorial,
            fecha_asignada=timezone.now(),
            zona="Zona",
        )
        self.definicion = definicion_formulario(self.relevamiento)
        self.foto = foto_definicion(self.relevamiento, self.definicion)
        self.k_tenencia = clave_pregunta(self.tenencia)
        self.k_nivel = clave_requisito(self.nivel)

    def _clave(self, origen, vinculo):
        return clave_pregunta(PreguntaGlobal.objects.get(origen=origen, vinculo=vinculo))


class FotoTests(_Base):
    def test_la_foto_lleva_version_canal_e_items(self):
        self.assertEqual(self.foto["version"], self.definicion["version"])
        self.assertEqual(self.foto["canal"], self.definicion["canal"])
        claves = [c["clave"] for c in campos_de(self.foto)]
        self.assertIn(self.k_tenencia, claves)
        self.assertIn(self.k_nivel, claves)
        self.assertIn(self._clave(OrigenRequisito.LEGAJO, "nombre"), claves)

    def test_los_campos_traen_lo_que_necesita_el_lector(self):
        campo = next(c for c in campos_de(self.foto) if c["clave"] == self.k_nivel)
        self.assertEqual(campo["texto"], "Nivel educativo")
        self.assertEqual(campo["tipo"], TipoCampo.SELECTOR)
        self.assertEqual(campo["opciones"], ["Primario", "Secundario"])


class PuenteLegacyTests(_Base):
    def test_del_contrato_anterior_a_claves(self):
        respuestas = respuestas_desde_legacy(
            {"globales": {str(self.tenencia.pk): "Propia"}, "requisitos": {str(self.nivel.pk): "Secundario"}},
            {"celular": "3624123456", "email_contacto": "a@a.com", "apoderado_dni": "20111222"},
            {"dni": "30123456", "nombre": "María", "apellido": "Gómez", "sexo": "F", "fecha_nacimiento": "1991-03-14"},
            self.foto,
        )
        self.assertEqual(respuestas[self.k_tenencia], "Propia")
        self.assertEqual(respuestas[self.k_nivel], "Secundario")
        self.assertEqual(respuestas[self._clave(OrigenRequisito.LEGAJO, "telefono")], "3624123456")
        self.assertEqual(respuestas[self._clave(OrigenRequisito.LEGAJO, "email")], "a@a.com")
        self.assertEqual(respuestas[self._clave(OrigenRequisito.PERSONA_VINCULADA, "dni")], "20111222")
        self.assertEqual(respuestas[self._clave(OrigenRequisito.LEGAJO, "nombre")], "María")
        self.assertEqual(respuestas[self._clave(OrigenRequisito.LEGAJO, "genero")], "F")

    def test_ids_ajenos_a_la_foto_se_ignoran(self):
        respuestas = respuestas_desde_legacy(
            {"globales": {"99999": "hack"}, "requisitos": {"99999": "hack"}}, {}, {}, self.foto
        )
        self.assertEqual(respuestas, {})

    def test_de_claves_al_contrato_anterior(self):
        respuestas = {
            self.k_tenencia: "Propia",
            self.k_nivel: "Secundario",
            self._clave(OrigenRequisito.LEGAJO, "telefono"): "3624123456",
            self._clave(OrigenRequisito.PERSONA_VINCULADA, "nombre"): "Ana",
            "cp-abc123": "un campo propio",
        }
        data, fijos = legacy_desde_respuestas(respuestas, self.foto)
        self.assertEqual(data["globales"][str(self.tenencia.pk)], "Propia")
        self.assertEqual(data["requisitos"][str(self.nivel.pk)], "Secundario")
        self.assertEqual(fijos["celular"], "3624123456")
        self.assertEqual(fijos["apoderado_nombre"], "Ana")
        # Un campo propio no tiene lugar en el contrato anterior: no se pierde,
        # vive en ``respuestas``, pero no viaja en ``data``.
        self.assertNotIn("cp-abc123", str(data))

    def test_identidad_desde_respuestas(self):
        respuestas = {
            self._clave(OrigenRequisito.LEGAJO, "nombre"): "Juan",
            self._clave(OrigenRequisito.LEGAJO, "apellido"): "Pérez",
            self._clave(OrigenRequisito.LEGAJO, "fecha_nacimiento"): "1990-01-01",
        }
        identidad = identidad_desde_respuestas(respuestas, self.foto)
        self.assertEqual(identidad["nombre"], "Juan")
        self.assertEqual(identidad["apellido"], "Pérez")
        self.assertEqual(identidad["fecha_nacimiento"], "1990-01-01")


class SincronizarTests(_Base):
    def _caso(self, **extra):
        datos = {
            "relevamiento": self.relevamiento,
            "celular": "3624123456",
            "email_contacto": "a@a.com",
            "data": {"globales": {str(self.tenencia.pk): "Propia"}, "requisitos": {}},
            "datos_identificacion": {"dni": "30123456", "nombre": "María", "apellido": "Gómez", "sexo": "F"},
        }
        datos.update(extra)
        return Formulario.objects.create(**datos)

    def test_un_caso_del_contrato_anterior_gana_respuestas_y_foto(self):
        formulario = self._caso()
        self.assertEqual(formulario.respuestas, {})
        sincronizar_desde_legacy(formulario, self.relevamiento)
        formulario.refresh_from_db()
        self.assertEqual(formulario.definicion["version"], self.definicion["version"])
        self.assertEqual(formulario.respuestas[self.k_tenencia], "Propia")
        self.assertEqual(formulario.respuestas[self._clave(OrigenRequisito.LEGAJO, "telefono")], "3624123456")
        self.assertEqual(formulario.respuestas[self._clave(OrigenRequisito.LEGAJO, "nombre")], "María")

    def test_no_pisa_la_foto_ni_los_campos_propios(self):
        formulario = self._caso()
        sincronizar_desde_legacy(formulario, self.relevamiento)
        formulario.respuestas["cp-propio"] = "algo que solo vive en el diseño"
        formulario.save(update_fields=["respuestas"])
        version_original = formulario.definicion["version"]
        # Cambia el catálogo: la foto del caso no se mueve (D3).
        PreguntaGlobal.objects.create(texto="Nueva", tipo=TipoCampo.STRING, orden=700)
        formulario.celular = "3629999999"
        formulario.save(update_fields=["celular"])
        sincronizar_desde_legacy(formulario)
        formulario.refresh_from_db()
        self.assertEqual(formulario.definicion["version"], version_original)
        self.assertEqual(formulario.respuestas["cp-propio"], "algo que solo vive en el diseño")
        self.assertEqual(formulario.respuestas[self._clave(OrigenRequisito.LEGAJO, "telefono")], "3629999999")

    def test_la_api_de_la_app_sincroniza_al_crear(self):
        self.client.force_login(self.territorial)
        url = reverse("becas_api:relevamiento-formularios", args=[self.relevamiento.pk])
        self.relevamiento.estado = Relevamiento.Estado.EN_CURSO
        self.relevamiento.save(update_fields=["estado"])
        resp = self.client.post(
            url,
            {
                "datos_identificacion": {"dni": "28111222", "nombre": "Ana", "apellido": "Ruiz", "sexo": "F"},
                "celular": "3624000111",
                "email_contacto": "ana@correo.com",
                "data": {"globales": {str(self.tenencia.pk): "Alquilada"}, "requisitos": {}},
            },
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        formulario = Formulario.objects.get(pk=resp.json()["id"])
        self.assertTrue(formulario.definicion)
        self.assertEqual(formulario.respuestas[self.k_tenencia], "Alquilada")
        self.assertEqual(formulario.respuestas[self._clave(OrigenRequisito.LEGAJO, "telefono")], "3624000111")


class LecturaRevisionTests(_Base):
    def _caso_con_foto(self):
        formulario = Formulario.objects.create(
            relevamiento=self.relevamiento,
            celular="3624123456",
            email_contacto="a@a.com",
            datos_identificacion={"dni": "30123456", "nombre": "María", "apellido": "Gómez", "sexo": "F"},
        )
        sincronizar_desde_legacy(formulario, self.relevamiento)
        formulario.refresh_from_db()
        return formulario

    def test_los_bloques_siguen_el_orden_de_la_foto(self):
        formulario = self._caso_con_foto()
        bloques = respuestas_legibles(formulario)
        titulos = [b["grupo"]["titulo"] for b in bloques]
        self.assertEqual(titulos[:3], ["Datos personales", "Contacto", "Apoderado"])
        contacto = next(b for b in bloques if b["grupo"]["titulo"] == "Contacto")
        telefono = next(i for i in contacto["items"] if i["clave"] == self._clave(OrigenRequisito.LEGAJO, "telefono"))
        self.assertEqual(telefono["valor"], "3624123456")

    def test_lo_que_no_se_pidio_se_marca_oculto(self):
        """El grupo Apoderado depende de la edad: para una persona mayor queda
        oculto y la revisión lo muestra como «no se pidió», no como vacío."""
        GrupoRequisito.objects.filter(clave="apoderado").update(
            condicion_defecto={
                "modo": "todas",
                "reglas": [{"fuente": "legajo:fecha_nacimiento", "op": "edad_menor", "valor": 18}],
            }
        )
        formulario = self._caso_con_foto()
        clave_nacimiento = self._clave(OrigenRequisito.LEGAJO, "fecha_nacimiento")
        formulario.respuestas[clave_nacimiento] = (timezone.localdate() - timedelta(days=30 * 365)).isoformat()
        formulario.save(update_fields=["respuestas"])
        bloques = respuestas_legibles(formulario)
        apoderado = next(b for b in bloques if b["grupo"]["titulo"] == "Apoderado")
        self.assertTrue(apoderado["oculto"])
        # Menor: el grupo se pidió.
        formulario.respuestas[clave_nacimiento] = (timezone.localdate() - timedelta(days=10 * 365)).isoformat()
        formulario.save(update_fields=["respuestas"])
        apoderado = next(b for b in respuestas_legibles(formulario) if b["grupo"]["titulo"] == "Apoderado")
        self.assertFalse(apoderado["oculto"])

    def test_leer_la_foto_no_crece_con_la_cantidad_de_campos(self):
        """Guarda de performance del camino nuevo: la lectura resuelve todo con
        una sola consulta (los adjuntos), sin una por campo."""
        formulario = self._caso_con_foto()
        with self.assertNumQueries(1):
            bloques = respuestas_legibles(formulario)
            self.assertTrue(bloques)
        # Con más campos en la foto, sigue siendo una.
        for indice in range(10):
            PreguntaGlobal.objects.create(texto=f"Extra {indice}", tipo=TipoCampo.STRING, orden=700 + indice)
        formulario.definicion = None
        formulario.save(update_fields=["definicion"])
        sincronizar_desde_legacy(formulario, self.relevamiento)
        formulario.refresh_from_db()
        with self.assertNumQueries(1):
            respuestas_legibles(formulario)

    def test_un_caso_sin_foto_devuelve_none(self):
        formulario = Formulario.objects.create(relevamiento=self.relevamiento, datos_identificacion={"dni": "30123456"})
        self.assertIsNone(respuestas_legibles(formulario))

    def test_el_detalle_de_revision_usa_la_foto(self):
        formulario = self._caso_con_foto()
        formulario.ciudadano = Ciudadano.objects.create(dni="30123456", nombre="María", apellido="Gómez")
        formulario.save(update_fields=["ciudadano"])
        admin = User.objects.create_user("admin-resp", password="x")
        admin.groups.add(Group.objects.get(name=ROL_ADMIN))
        self.client.force_login(admin)
        resp = self.client.get(reverse("becas:formulario_detalle", args=[formulario.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertIsNotNone(resp.context["bloques"])
        html = resp.content.decode()
        # Las preguntas van en «Respuestas», en el orden de la foto; identidad,
        # contacto y apoderado no se repiten ahí porque tienen su sección arriba.
        titulos = [b["grupo"]["titulo"] for b in resp.context["bloques"]]
        self.assertIn("Cuestionario social", titulos)
        self.assertNotIn("Datos personales", titulos)
        self.assertNotIn("Contacto", titulos)
        self.assertIn("Tenencia de la vivienda", html)
        self.assertIn("3624123456", html)  # el contacto sigue en su form

    def test_editar_el_contacto_actualiza_las_respuestas(self):
        formulario = self._caso_con_foto()
        formulario.ciudadano = Ciudadano.objects.create(dni="30123456", nombre="María", apellido="Gómez")
        formulario.save(update_fields=["ciudadano"])
        admin = User.objects.create_user("admin-edit", password="x")
        admin.groups.add(Group.objects.get(name=ROL_ADMIN))
        self.client.force_login(admin)
        resp = self.client.post(
            reverse("becas:formulario_detalle", args=[formulario.pk]),
            {"celular": "3629999999", "email_contacto": "nuevo@correo.com"},
        )
        self.assertEqual(resp.status_code, 302)
        formulario.refresh_from_db()
        self.assertEqual(formulario.respuestas[self._clave(OrigenRequisito.LEGAJO, "telefono")], "3629999999")
        self.assertEqual(formulario.respuestas[self._clave(OrigenRequisito.LEGAJO, "email")], "nuevo@correo.com")


class VolcadoAlLegajoTests(_Base):
    def test_el_contacto_completa_el_legajo_sin_pisar(self):
        from programas.services.becas import resolver_ciudadano_offline

        nuevo = Formulario.objects.create(
            relevamiento=self.relevamiento,
            celular="3624000111",
            email_contacto="nuevo@correo.com",
            datos_identificacion={"dni": "28111222", "nombre": "Ana", "apellido": "Ruiz", "sexo": "F"},
        )
        resolver_ciudadano_offline(nuevo)
        nuevo.refresh_from_db()
        self.assertEqual(nuevo.ciudadano.telefono, "3624000111")
        self.assertEqual(nuevo.ciudadano.email, "nuevo@correo.com")

        existente = Ciudadano.objects.create(dni="30123456", nombre="María", apellido="Gómez", telefono="3620000000")
        otro = Formulario.objects.create(
            relevamiento=self.relevamiento,
            celular="3629999999",
            email_contacto="maria@correo.com",
            datos_identificacion={"dni": "30123456", "nombre": "María", "apellido": "Gómez", "sexo": "F"},
        )
        resolver_ciudadano_offline(otro)
        existente.refresh_from_db()
        self.assertEqual(existente.telefono, "3620000000")  # no se pisa
        self.assertEqual(existente.email, "maria@correo.com")  # se completa


class _BaseDetalle(_Base):
    """Casos con foto abiertos (y guardados) desde el detalle de revisión."""

    def setUp(self):
        super().setUp()
        # Superusuario: el caso del link público exige además la capacidad de
        # relevamientos públicos (RN-P13), que no es lo que se prueba acá.
        self.admin = User.objects.create_superuser("admin-detalle", password="x")
        self.client.force_login(self.admin)

    def _url(self, formulario):
        return reverse("becas:formulario_detalle", args=[formulario.pk])

    def _detalle(self, formulario):
        return self.client.get(self._url(formulario))

    def _relevamiento_publico(self):
        return Relevamiento.objects.create(
            convocatoria=self.convocatoria, tipo=Relevamiento.Tipo.PUBLICO, fecha_asignada=timezone.now()
        )

    def _caso_adulto(self, relevamiento=None):
        """Un adulto con su legajo. Sin ``relevamiento``, el de la app de campo:
        su foto oculta el grupo Apoderado a los mayores (``edad_menor 18``)."""
        relevamiento = relevamiento or self.relevamiento
        formulario = Formulario.objects.create(
            relevamiento=relevamiento,
            celular="3624123456",
            email_contacto="maria@correo.com",
            datos_identificacion={"dni": "30123456", "nombre": "María", "apellido": "Gómez", "sexo": "F"},
        )
        sincronizar_desde_legacy(formulario, relevamiento)
        formulario.ciudadano = Ciudadano.objects.get_or_create(
            dni="30123456", defaults={"nombre": "María", "apellido": "Gómez", "fecha_nacimiento": date(1990, 1, 1)}
        )[0]
        formulario.save(update_fields=["ciudadano"])
        formulario.respuestas[self._clave(OrigenRequisito.LEGAJO, "fecha_nacimiento")] = "1990-01-01"
        formulario.save(update_fields=["respuestas"])
        return formulario

    def _post_contacto(self, formulario, **extra):
        datos = {"celular": formulario.celular, "email_contacto": formulario.email_contacto}
        datos.update(extra)
        return self.client.post(self._url(formulario), datos)


class ApoderadoSegunLaFotoTests(_BaseDetalle):
    """#347 (E6): la sección editable del apoderado sigue a la foto del caso.

    La app de campo oculta el grupo Apoderado a los adultos y
    ``campo.aplicar_revision`` borra lo que hubiera llegado; si la revisión lo
    ofrecía igual, el revisor lo volvía a cargar y se creaba el legajo de un
    apoderado que el formulario nunca pidió. El Cambio 67 (se pide a todos) vale
    para el link, cuyo grupo no tiene condición: con foto manda la foto."""

    def test_con_foto_de_la_app_y_un_adulto_no_se_ofrece_el_apoderado(self):
        resp = self._detalle(self._caso_adulto())
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.context["mostrar_apoderado"])
        self.assertNotIn("apoderado_dni", resp.context["form"].fields)
        self.assertNotContains(resp, 'name="apoderado_dni"')
        self.assertContains(resp, "No se pidió")

    def test_por_el_link_sin_condicion_el_apoderado_se_muestra(self):
        """Cambio 67: por el link el grupo no tiene condición y se pide a todos."""
        resp = self._detalle(self._caso_adulto(self._relevamiento_publico()))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context["mostrar_apoderado"])
        self.assertContains(resp, 'name="apoderado_dni"')

    def test_sin_foto_el_apoderado_se_muestra(self):
        """Caso anterior al Cambio 58: no hay condición que leer (Cambio 67)."""
        formulario = Formulario.objects.create(relevamiento=self.relevamiento, celular="3624123456")
        resp = self._detalle(formulario)
        self.assertTrue(resp.context["mostrar_apoderado"])
        self.assertContains(resp, 'name="apoderado_dni"')

    def test_el_post_no_carga_un_apoderado_que_no_se_pidio(self):
        formulario = self._caso_adulto()
        resp = self._post_contacto(
            formulario,
            celular="3629999999",
            apoderado_nombre="Ana",
            apoderado_apellido="Pérez",
            apoderado_dni="27111444",
            apoderado_genero="F",
            apoderado_fecha_nacimiento="1980-05-05",
        )
        self.assertEqual(resp.status_code, 302)
        formulario.refresh_from_db()
        self.assertEqual(formulario.celular, "3629999999")
        self.assertEqual(formulario.apoderado_dni, "")
        self.assertIsNone(formulario.apoderado_ciudadano_id)
        self.assertFalse(Ciudadano.objects.filter(dni="27111444").exists())

    def test_los_datos_ya_cargados_se_muestran_y_no_se_borran(self):
        """Un caso con apoderado cargado y el grupo oculto (p. ej. cargado antes
        de la regla): se muestra para no esconder un dato del caso, y guardar el
        contacto no lo vacía."""
        formulario = self._caso_adulto()
        Formulario.objects.filter(pk=formulario.pk).update(
            apoderado_nombre="Ana", apoderado_apellido="Pérez", apoderado_dni="27111444"
        )
        formulario.refresh_from_db()
        resp = self._detalle(formulario)
        self.assertTrue(resp.context["mostrar_apoderado"])
        self.assertContains(resp, 'value="27111444"')
        self._post_contacto(
            formulario,
            celular="3629999999",
            apoderado_nombre="Ana",
            apoderado_apellido="Pérez",
            apoderado_dni="27111444",
        )
        formulario.refresh_from_db()
        self.assertEqual(formulario.celular, "3629999999")
        self.assertEqual(formulario.apoderado_dni, "27111444")
        self.assertEqual(formulario.apoderado_nombre, "Ana")


class VersionDelFormularioTests(_BaseDetalle):
    """#347 (E7): el aviso de que el formulario cambió sale solo si cambió."""

    def _caso_version(self, version_foto, version_vigente):
        DisenoFormulario.objects.create(convocatoria=self.convocatoria, version=version_vigente)
        formulario = self._caso_adulto()
        formulario.definicion = {**formulario.definicion, "version": version_foto}
        formulario.save(update_fields=["definicion"])
        return formulario

    def test_foto_vieja_avisa_la_version_vigente(self):
        resp = self._detalle(self._caso_version(5, 7))
        self.assertEqual(resp.context["version_vigente"], 7)
        self.assertContains(resp, "Formulario v5")
        self.assertContains(resp, "vigente: v7")

    def test_foto_de_la_version_vigente_no_avisa(self):
        resp = self._detalle(self._caso_version(7, 7))
        self.assertContains(resp, "Formulario v7")
        self.assertNotContains(resp, "vigente: v")

    def test_sin_diseno_no_avisa(self):
        formulario = self._caso_adulto()
        formulario.definicion = {**formulario.definicion, "version": 3}
        formulario.save(update_fields=["definicion"])
        resp = self._detalle(formulario)
        self.assertEqual(resp.context["version_vigente"], 0)
        self.assertNotContains(resp, "vigente: v")


class GuardarSinCambiosTests(_BaseDetalle):
    """#347 (E8): «Guardar» sin cambios no reescribe el caso, pero sigue
    reparando un alta que quedó a medias."""

    def test_sin_cambios_no_toca_el_caso(self):
        formulario = self._caso_adulto(self._relevamiento_publico())
        antes = Formulario.objects.get(pk=formulario.pk).modificado
        resp = self._post_contacto(
            formulario,
            apoderado_nombre="",
            apoderado_apellido="",
            apoderado_dni="",
            apoderado_genero="",
            apoderado_fecha_nacimiento="",
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Formulario.objects.get(pk=formulario.pk).modificado, antes)

    def test_sin_cambios_repara_el_alta_incompleta(self):
        formulario = self._caso_adulto(self._relevamiento_publico())
        Formulario.objects.filter(pk=formulario.pk).update(ciudadano=None)
        formulario.refresh_from_db()
        self._post_contacto(formulario)
        formulario.refresh_from_db()
        self.assertIsNotNone(formulario.ciudadano_id)
        self.assertEqual(formulario.ciudadano.dni, "30123456")

    def test_sin_cambios_completa_la_foto_de_un_caso_anterior(self):
        formulario = Formulario.objects.create(
            relevamiento=self.relevamiento, celular="3624123456", email_contacto="a@b.com"
        )
        self._post_contacto(formulario)
        formulario.refresh_from_db()
        self.assertTrue(formulario.definicion)

    def test_sin_cambios_vincula_al_apoderado_pendiente(self):
        formulario = self._caso_adulto(self._relevamiento_publico())
        Formulario.objects.filter(pk=formulario.pk).update(
            apoderado_nombre="Ana", apoderado_apellido="Pérez", apoderado_dni="27111444"
        )
        formulario.refresh_from_db()
        self._post_contacto(formulario, apoderado_nombre="Ana", apoderado_apellido="Pérez", apoderado_dni="27111444")
        formulario.refresh_from_db()
        self.assertEqual(formulario.apoderado_ciudadano.dni, "27111444")


class PlaceholderArchivoTests(_Base):
    def test_el_pendiente_upload_de_la_app_no_rompe_ni_se_muestra(self):
        certificado = RequisitoNativo.objects.create(
            texto="Certificado", tipo=TipoCampo.ARCHIVO, segmento=self.segmento, orden=2
        )
        foto = foto_definicion(self.relevamiento)
        data = {"globales": {}, "requisitos": {str(certificado.pk): {"pendiente_upload": True}}}
        respuestas = respuestas_desde_legacy(data, {}, {}, foto)
        clave = clave_requisito(certificado)
        self.assertEqual(respuestas[clave], {"pendiente_upload": True})
        vuelta, _ = legacy_desde_respuestas(respuestas, foto)
        self.assertEqual(vuelta["requisitos"][str(certificado.pk)], {"pendiente_upload": True})
        formulario = Formulario.objects.create(
            relevamiento=self.relevamiento,
            respuestas=respuestas,
            definicion=foto,
            datos_identificacion={"dni": "1"},
        )
        fila = next(i for b in respuestas_legibles(formulario) for i in b["items"] if i.get("clave") == clave)
        self.assertTrue(fila["es_archivo"])
        self.assertEqual(fila["valor"], "")
