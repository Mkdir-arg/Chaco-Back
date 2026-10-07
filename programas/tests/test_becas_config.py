"""Tests del backoffice de Configuración de Becas (#74)."""

from datetime import date
from io import StringIO
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db.models import Max
from django.test import TestCase
from django.urls import reverse

from programas.forms import (
    AsignacionCoordinadorForm,
    PreguntaGlobalForm,
    RequisitoNativoForm,
    SubsegmentoForm,
)
from programas.management.commands.seed_becas import ROL_ADMIN, ROL_COORDINADOR
from programas.models import (
    AdjuntoFormulario,
    AsignacionCoordinador,
    Convocatoria,
    DisenoFormulario,
    Formulario,
    ItemDiseno,
    PreguntaGlobal,
    ProgramaSiis,
    Relevamiento,
    RequisitoNativo,
    Segmento,
    Subsegmento,
    TipoCampo,
)


class _BaseConfigTest(TestCase):
    def setUp(self):
        call_command("seed_becas", stdout=StringIO())
        self.admin = User.objects.create_user("admin_becas", password="x")
        self.admin.groups.add(Group.objects.get(name=ROL_ADMIN))
        self.coord = User.objects.create_user("coord_becas", password="x")
        self.coord.groups.add(Group.objects.get(name=ROL_COORDINADOR))


class AccesoConfigTests(_BaseConfigTest):
    def test_admin_accede(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse("becas:segmentos"))
        self.assertEqual(resp.status_code, 200)

    def test_coordinador_ve_lista_pero_no_puede_crear(self):
        # El Coordinador tiene becas.segmento.ver (solo lectura): accede a la
        # lista, pero sin becas.segmento.crear no puede dar de alta.
        self.client.force_login(self.coord)
        resp = self.client.get(reverse("becas:segmentos"))
        self.assertEqual(resp.status_code, 200)
        resp = self.client.post(
            reverse("becas:segmento_crear"),
            {"nombre": "Nuevo", "descripcion": "", "cupo_maximo": 10, "coordinador": self.coord.pk},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Segmento.objects.filter(nombre="Nuevo").exists())

    def test_coordinador_sin_asignacion_no_ve_segmentos_de_otros(self):
        # segmentos_visibles() acota la lista a los segmentos asignados: sin
        # ninguna asignación, la lista queda vacía aunque pueda verla.
        Segmento.objects.create(nombre="S1", cupo_maximo=100)
        self.client.force_login(self.coord)
        resp = self.client.get(reverse("becas:segmentos"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(list(resp.context["segmentos"]), [])

    def test_coordinador_asignado_ve_solo_su_segmento(self):
        seg_propio = Segmento.objects.create(nombre="Propio", cupo_maximo=100)
        seg_ajeno = Segmento.objects.create(nombre="Ajeno", cupo_maximo=100)
        AsignacionCoordinador.objects.create(segmento=seg_propio, coordinador=self.coord)
        self.client.force_login(self.coord)

        resp = self.client.get(reverse("becas:segmentos"))
        self.assertEqual(list(resp.context["segmentos"]), [seg_propio])

        resp = self.client.get(reverse("becas:segmento_detalle", args=[seg_propio.pk]))
        self.assertEqual(resp.status_code, 200)
        resp = self.client.get(reverse("becas:segmento_detalle", args=[seg_ajeno.pk]))
        self.assertEqual(resp.status_code, 403)

    def test_anonimo_redirige_login(self):
        resp = self.client.get(reverse("becas:segmentos"))
        self.assertEqual(resp.status_code, 302)

    def test_sin_permiso_via_ajax_devuelve_403_json(self):
        # Los modales postean por fetch: sin capacidad, la respuesta debe ser
        # JSON 403 con el motivo real (no el redirect que el toast muestra como
        # "Ocurrió un error").
        seg = Segmento.objects.create(nombre="S-ajax", cupo_maximo=100)
        AsignacionCoordinador.objects.create(segmento=seg, coordinador=self.coord)
        self.client.force_login(self.coord)
        resp = self.client.post(
            reverse("becas:subsegmento_crear", args=[seg.pk]),
            {"nombre": "Sub", "cupo_maximo": 10},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(resp.status_code, 403)
        data = resp.json()
        self.assertFalse(data["ok"])
        self.assertIn("permisos", data["message"])

    def test_sin_permiso_sin_ajax_sigue_redirigiendo(self):
        seg = Segmento.objects.create(nombre="S-redir", cupo_maximo=100)
        AsignacionCoordinador.objects.create(segmento=seg, coordinador=self.coord)
        self.client.force_login(self.coord)
        resp = self.client.post(
            reverse("becas:subsegmento_crear", args=[seg.pk]),
            {"nombre": "Sub", "cupo_maximo": 10},
        )
        self.assertEqual(resp.status_code, 302)  # comportamiento histórico con mensaje


class ProgramaSiisConfigTests(_BaseConfigTest):
    """CRUD del nivel Programa (SIIS): la cabeza de Programa → Segmento → Subsegmento."""

    def setUp(self):
        super().setUp()
        self.programas_siis = patch(
            "programas.forms.listar_programas", return_value=[{"id": 38, "nombre": "Producción", "estado": "ACTIVO"}]
        )
        self.programas_siis.start()
        self.addCleanup(self.programas_siis.stop)
        self.client.force_login(self.admin)

    def test_listado_accesible(self):
        resp = self.client.get(reverse("becas:programas"))
        self.assertEqual(resp.status_code, 200)

    def test_crear_programa_desde_el_catalogo(self):
        resp = self.client.post(reverse("becas:programa_crear"), {"siis_programa_id": 38})
        self.assertEqual(resp.status_code, 302)
        programa = ProgramaSiis.objects.get(siis_programa_id=38)
        # El nombre se toma tal cual del catálogo.
        self.assertEqual(programa.nombre, "Producción")

    def test_modal_nuevo_programa_ordena_catalogo_alfabeticamente(self):
        self.programas_siis.stop()
        self.addCleanup(self.programas_siis.start)
        with patch(
            "programas.forms.listar_programas",
            return_value=[
                {"id": 3, "nombre": "Zoonosis", "estado": "ACTIVO"},
                {"id": 1, "nombre": "Ángeles", "estado": "ACTIVO"},
                {"id": 2, "nombre": "becas", "estado": "ACTIVO"},
            ],
        ):
            resp = self.client.get(reverse("becas:programas"))

        choices = list(resp.context["form_programa"].fields["siis_programa_id"].choices)
        self.assertEqual([label for _, label in choices[1:]], ["Ángeles", "becas", "Zoonosis"])

    def test_detalle_del_programa(self):
        programa = ProgramaSiis.objects.create(nombre="Producción", siis_programa_id=38)
        Segmento.objects.create(programa=programa, nombre="Seg A", cupo_maximo=10)
        resp = self.client.get(reverse("becas:programa_detalle", args=[programa.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual([s.nombre for s in resp.context["segmentos"]], ["Seg A"])

    def test_crear_requisito_de_programa(self):
        programa = ProgramaSiis.objects.create(nombre="Producción", siis_programa_id=38)
        resp = self.client.post(
            reverse("becas:requisito_programa_crear", args=[programa.pk]),
            {"texto": "Constancia", "tipo": TipoCampo.STRING, "orden": 1, "obligatorio": "True"},
        )
        self.assertEqual(resp.status_code, 302)
        req = RequisitoNativo.objects.get(texto="Constancia")
        self.assertEqual(req.programa, programa)
        self.assertIsNone(req.segmento)


class SegmentoCrudTests(_BaseConfigTest):
    def setUp(self):
        super().setUp()
        self.programa = ProgramaSiis.objects.create(nombre="Producción", siis_programa_id=38)
        self.client.force_login(self.admin)

    def test_crear_segmento(self):
        resp = self.client.post(
            reverse("becas:segmento_crear"),
            {
                "programa": self.programa.pk,
                "nombre": "Producción Territorial",
                "descripcion": "Población objetivo del segmento productivo",
                "cupo_maximo": 200,
                "coordinador": self.coord.pk,
            },
        )
        self.assertEqual(resp.status_code, 302)
        seg = Segmento.objects.get(nombre="Producción Territorial")
        self.assertEqual(seg.cupo_maximo, 200)
        self.assertEqual(seg.programa, self.programa)

    def test_crear_segmento_sin_programa_falla(self):
        resp = self.client.post(
            reverse("becas:segmento_crear"),
            {
                "nombre": "Suelto",
                "descripcion": "Sin programa",
                "cupo_maximo": 200,
                "coordinador": self.coord.pk,
            },
        )
        self.assertEqual(resp.status_code, 200)  # re-render con error
        self.assertFalse(Segmento.objects.filter(nombre="Suelto").exists())

    def test_editar_segmento(self):
        seg = Segmento.objects.create(programa=self.programa, nombre="S1", cupo_maximo=100)
        resp = self.client.post(
            reverse("becas:segmento_editar", args=[seg.pk]),
            {"nombre": "S1 editado", "descripcion": "", "cupo_maximo": 150, "activo": "on"},
        )
        self.assertEqual(resp.status_code, 302)
        seg.refresh_from_db()
        self.assertEqual(seg.nombre, "S1 editado")
        self.assertEqual(seg.cupo_maximo, 150)

    def test_toggle_segmento(self):
        seg = Segmento.objects.create(nombre="S1", cupo_maximo=100, activo=True)
        self.client.post(reverse("becas:segmento_toggle", args=[seg.pk]))
        seg.refresh_from_db()
        self.assertFalse(seg.activo)


class SubsegmentoCupoTests(_BaseConfigTest):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)
        self.seg = Segmento.objects.create(nombre="S", cupo_maximo=200)

    def test_crear_subsegmento_ok(self):
        """El nombre lo escribe el operador: el subsegmento no consulta a SIIS."""
        resp = self.client.post(
            reverse("becas:subsegmento_crear", args=[self.seg.pk]),
            {"nombre": "Ladrillo", "cupo_maximo": 120},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Subsegmento.objects.filter(segmento=self.seg, nombre="Ladrillo").exists())

    def test_no_permite_dos_subsegmentos_con_el_mismo_nombre(self):
        """Se valida sobre el form (no vía HTTP) para no depender del render."""
        Subsegmento.objects.create(segmento=self.seg, nombre="Ladrillo", cupo_maximo=50)

        form = SubsegmentoForm({"nombre": "ladrillo", "cupo_maximo": 50}, segmento=self.seg)

        self.assertFalse(form.is_valid())
        self.assertIn("nombre", form.errors)

    def test_subsegmento_excede_cupo_rn40(self):
        Subsegmento.objects.create(segmento=self.seg, nombre="Ladrillo", cupo_maximo=120)
        resp = self.client.post(
            reverse("becas:subsegmento_crear", args=[self.seg.pk]),
            {"nombre": "Carbón", "cupo_maximo": 100},  # 120 + 100 > 200
        )
        self.assertEqual(resp.status_code, 200)  # re-render con error
        self.assertFalse(Subsegmento.objects.filter(nombre="Carbón").exists())
        self.assertContains(resp, "supera el cupo del segmento")


class SubsegmentoDetailRenderTests(_BaseConfigTest):
    """TIT-5/DE-7: encabezado sin card, migas, estado y modales accesibles."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)
        self.programa = ProgramaSiis.objects.create(nombre="Prog", siis_programa_id=1)
        self.seg = Segmento.objects.create(programa=self.programa, nombre="Estudiantes terciarios", cupo_maximo=200)
        self.sub = Subsegmento.objects.create(
            segmento=self.seg, nombre="Resistencia Norte", descripcion="Zona metropolitana", cupo_maximo=120
        )

    def test_encabezado_sin_card_con_migas_y_bajada(self):
        resp = self.client.get(reverse("becas:subsegmento_detalle", args=[self.sub.pk]))
        self.assertEqual(resp.status_code, 200)
        contenido = resp.content.decode()
        self.assertContains(
            resp, '<h1 class="text-3xl font-extrabold text-heading tracking-tight">Resistencia Norte</h1>'
        )
        self.assertContains(resp, 'aria-label="Migas"')
        self.assertContains(resp, "Segmento padre:")
        self.assertContains(resp, reverse("becas:segmento_detalle", args=[self.seg.pk]))
        self.assertContains(resp, "Cupo máximo:")
        self.assertContains(resp, "120")
        self.assertContains(resp, "Zona metropolitana")
        self.assertNotIn('class="bg-white rounded-xl border border-base shadow-sm p-5"', contenido)

    def test_estado_activo_usa_pausable_estado_badge(self):
        resp = self.client.get(reverse("becas:subsegmento_detalle", args=[self.sub.pk]))
        self.assertContains(resp, 'badge badge-success badge-dot">Activo')

    def test_estado_pausado(self):
        self.sub.pausado = True
        self.sub.pausa_motivo = "Cupo agotado"
        self.sub.save(update_fields=["pausado", "pausa_motivo"])
        resp = self.client.get(reverse("becas:subsegmento_detalle", args=[self.sub.pk]))
        self.assertContains(resp, 'badge badge-warning badge-dot" title="Cupo agotado">Pausado')

    def test_modales_son_x_becas_modal_con_dialog_accesible(self):
        resp = self.client.get(reverse("becas:subsegmento_detalle", args=[self.sub.pk]))
        contenido = resp.content.decode()
        self.assertIn('x-becas-modal="modalReqNuevo"', contenido)
        self.assertIn('x-becas-modal="modalReqEdit"', contenido)
        self.assertIn('x-becas-modal="modalSubEdit"', contenido)
        self.assertIn('aria-labelledby="modal-reqnuevo-titulo"', contenido)
        self.assertIn('aria-labelledby="modal-reqedit-titulo"', contenido)
        self.assertIn('aria-labelledby="modal-subedit-titulo"', contenido)

    def test_acciones_de_fila_con_aria_label_que_nombra_el_requisito(self):
        RequisitoNativo.objects.create(
            segmento=self.seg,
            subsegmento=self.sub,
            texto="Certificado de alumno regular",
            tipo=TipoCampo.STRING,
            orden=1,
        )
        resp = self.client.get(reverse("becas:subsegmento_detalle", args=[self.sub.pk]))
        self.assertContains(resp, 'aria-label="Editar requisito: Certificado de alumno regular"')
        self.assertContains(resp, 'aria-label="Eliminar requisito: Certificado de alumno regular"')
        self.assertContains(resp, 'data-confirm-danger="true"')
        self.assertContains(resp, 'data-confirm-ok="Sí, eliminar"')
        self.assertContains(resp, 'class="nodo-icon-btn nodo-icon-btn--danger"')

    def test_tipo_badge_usa_badge_white(self):
        RequisitoNativo.objects.create(
            segmento=self.seg, subsegmento=self.sub, texto="DNI", tipo=TipoCampo.STRING, orden=1
        )
        resp = self.client.get(reverse("becas:subsegmento_detalle", args=[self.sub.pk]))
        self.assertContains(resp, 'class="badge badge-white"')


class SubsegmentoFormRenderTests(_BaseConfigTest):
    """TIT-10/11: formulario de respaldo con page_header y Cancelar al origen."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)
        self.seg = Segmento.objects.create(nombre="S", cupo_maximo=200)
        self.sub = Subsegmento.objects.create(segmento=self.seg, nombre="Sub", cupo_maximo=50)

    def test_crear_cancelar_va_al_segmento(self):
        resp = self.client.get(reverse("becas:subsegmento_crear", args=[self.seg.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Nuevo subsegmento")
        url_origen = reverse("becas:segmento_detalle", args=[self.seg.pk])
        self.assertContains(resp, f'href="{url_origen}" class="btn-nodo btn-secondary btn-base">Cancelar')

    def test_editar_cancelar_va_al_subsegmento(self):
        resp = self.client.get(reverse("becas:subsegmento_editar", args=[self.sub.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Editar subsegmento")
        url_origen = reverse("becas:subsegmento_detalle", args=[self.sub.pk])
        self.assertContains(resp, f'href="{url_origen}" class="btn-nodo btn-secondary btn-base">Cancelar')


class CoordinadorTests(_BaseConfigTest):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)
        self.seg = Segmento.objects.create(nombre="S", cupo_maximo=100)

    def test_asignar_coordinador(self):
        resp = self.client.post(
            reverse("becas:coordinador_asignar", args=[self.seg.pk]),
            {"coordinador": self.coord.pk},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(AsignacionCoordinador.objects.filter(segmento=self.seg, coordinador=self.coord).exists())

    def test_selector_excluye_coordinadores_ya_asignados(self):
        disponible = User.objects.create_user("coord_disponible", password="x")
        disponible.groups.add(Group.objects.get(name=ROL_COORDINADOR))
        AsignacionCoordinador.objects.create(segmento=self.seg, coordinador=self.coord)

        form = AsignacionCoordinadorForm(segmento=self.seg)
        opciones = form.fields["coordinador"].queryset

        self.assertNotIn(self.coord, opciones)
        self.assertIn(disponible, opciones)

        form_duplicado = AsignacionCoordinadorForm(
            {"coordinador": self.coord.pk},
            segmento=self.seg,
        )

        self.assertFalse(form_duplicado.is_valid())
        self.assertIn(
            "Ese coordinador ya está asignado a este segmento.",
            form_duplicado.errors["coordinador"],
        )
        self.assertEqual(
            AsignacionCoordinador.objects.filter(segmento=self.seg, coordinador=self.coord).count(),
            1,
        )

    def test_no_asignar_usuario_sin_rol_coordinador(self):
        otro = User.objects.create_user("otro", password="x")  # sin rol coordinador
        self.client.post(
            reverse("becas:coordinador_asignar", args=[self.seg.pk]),
            {"coordinador": otro.pk},
        )
        # El form rechaza el usuario (queryset acotado a rol coordinador)
        self.assertFalse(AsignacionCoordinador.objects.filter(coordinador=otro).exists())

    def test_desasignar_coordinador(self):
        asig = AsignacionCoordinador.objects.create(segmento=self.seg, coordinador=self.coord)
        self.client.post(reverse("becas:coordinador_desasignar", args=[asig.pk]))
        self.assertFalse(AsignacionCoordinador.objects.filter(pk=asig.pk).exists())


class RequisitoTests(_BaseConfigTest):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)
        self.seg = Segmento.objects.create(nombre="S", cupo_maximo=100)
        self.sub = Subsegmento.objects.create(segmento=self.seg, nombre="Sub", cupo_maximo=40)

    def test_crear_requisito_segmento(self):
        resp = self.client.post(
            reverse("becas:requisito_crear", args=[self.seg.pk]),
            {"texto": "Actividad", "tipo": TipoCampo.STRING, "orden": 1, "obligatorio": "True"},
        )
        self.assertEqual(resp.status_code, 302)
        req = RequisitoNativo.objects.get(texto="Actividad")
        self.assertEqual(req.segmento, self.seg)
        self.assertIsNone(req.subsegmento)

    def test_crear_requisito_subsegmento(self):
        resp = self.client.post(
            reverse("becas:requisito_crear", args=[self.seg.pk]) + f"?subsegmento={self.sub.pk}",
            {
                "texto": "Tipo horno",
                "tipo": TipoCampo.STRING,
                "orden": 1,
                "obligatorio": "True",
                "subsegmento": self.sub.pk,
            },
        )
        self.assertEqual(resp.status_code, 302)
        req = RequisitoNativo.objects.get(texto="Tipo horno")
        self.assertEqual(req.subsegmento, self.sub)

    def test_crear_requisito_selector_parsea_opciones(self):
        resp = self.client.post(
            reverse("becas:requisito_crear", args=[self.seg.pk]),
            {
                "texto": "Material",
                "tipo": TipoCampo.SELECTOR,
                "orden": 1,
                "obligatorio": "True",
                "opciones_texto": "Ladrillo\nCarbón\nOtro",
            },
        )
        self.assertEqual(resp.status_code, 302)
        req = RequisitoNativo.objects.get(texto="Material")
        self.assertEqual(req.opciones, ["Ladrillo", "Carbón", "Otro"])


class PreguntaGlobalTests(_BaseConfigTest):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)

    def test_crear_pregunta_selector(self):
        resp = self.client.post(
            reverse("becas:pregunta_crear"),
            {
                "texto": "Tenencia de la vivienda",
                "tipo": TipoCampo.SELECTOR,
                "orden": 1,
                "obligatorio": "on",
                "activo": "on",
                "opciones_texto": "Propia\nAlquilada\nPrestada",
            },
        )
        self.assertEqual(resp.status_code, 302)
        p = PreguntaGlobal.objects.get(texto="Tenencia de la vivienda")
        self.assertEqual(p.opciones, ["Propia", "Alquilada", "Prestada"])

    def test_toggle_pregunta(self):
        p = PreguntaGlobal.objects.create(texto="X", tipo=TipoCampo.STRING, activo=True)
        self.client.post(reverse("becas:pregunta_toggle", args=[p.pk]))
        p.refresh_from_db()
        self.assertFalse(p.activo)

    def test_eliminar_pregunta(self):
        p = PreguntaGlobal.objects.create(texto="X", tipo=TipoCampo.STRING)
        self.client.post(reverse("becas:pregunta_eliminar", args=[p.pk]))
        self.assertFalse(PreguntaGlobal.objects.filter(pk=p.pk).exists())

    def test_filtra_preguntas_con_componente_dinamico(self):
        esperada = PreguntaGlobal.objects.create(
            texto="Fecha de inscripción", tipo=TipoCampo.DATE, obligatorio=True, activo=True
        )
        PreguntaGlobal.objects.create(texto="Observaciones", tipo=TipoCampo.STRING, obligatorio=False, activo=True)
        # El catálogo protegido (Cambio 58) trae «Fecha de nacimiento», también DATE y
        # obligatoria: el texto acota a la creada acá.
        respuesta = self.client.get(
            reverse("becas:preguntas"),
            {"q": "Fecha de inscripción", "tipo": TipoCampo.DATE, "obligatorio": "1", "activo": "1"},
        )
        self.assertEqual(list(respuesta.context["preguntas"]), [esperada])
        self.assertContains(respuesta, "data-dynamic-list-filters")
        self.assertTrue(respuesta.context["hay_filtros_activos"])


class OrdenRequisitosTests(_BaseConfigTest):
    """El orden se puede escribir o dejar vacío (autonumera), pero no se repite
    entre requisitos del mismo alcance."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)
        self.seg = Segmento.objects.create(nombre="S", cupo_maximo=100)
        self.sub = Subsegmento.objects.create(segmento=self.seg, nombre="Sub", cupo_maximo=40)

    def _crear_requisito(self, texto, orden="", subsegmento=None):
        url = reverse("becas:requisito_crear", args=[self.seg.pk])
        datos = {"texto": texto, "tipo": TipoCampo.STRING, "obligatorio": "True", "orden": orden}
        if subsegmento is not None:
            url += f"?subsegmento={subsegmento.pk}"
            datos["subsegmento"] = subsegmento.pk
        return self.client.post(url, datos)

    def test_autonumera_correlativo_cuando_el_orden_viene_vacio(self):
        self._crear_requisito("Primero")
        self._crear_requisito("Segundo")
        self.assertEqual(RequisitoNativo.objects.get(texto="Primero").orden, 1)
        self.assertEqual(RequisitoNativo.objects.get(texto="Segundo").orden, 2)

    def test_autonumera_despues_del_orden_mas_alto_cargado_a_mano(self):
        self._crear_requisito("Manual", orden=7)
        self._crear_requisito("Automatico")
        self.assertEqual(RequisitoNativo.objects.get(texto="Automatico").orden, 8)

    def test_rechaza_dos_requisitos_con_el_mismo_orden_en_el_segmento(self):
        self._crear_requisito("Primero", orden=3)
        form = RequisitoNativoForm(
            {"texto": "Repetido", "tipo": TipoCampo.STRING, "obligatorio": "True", "orden": 3},
            segmento=self.seg,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("orden 3", form.errors["orden"][0])
        self.assertIn("segmento", form.errors["orden"][0])

    def test_rechaza_dos_requisitos_con_el_mismo_orden_en_el_subsegmento(self):
        self._crear_requisito("Propio", orden=2, subsegmento=self.sub)
        form = RequisitoNativoForm(
            {"texto": "Repetido", "tipo": TipoCampo.STRING, "obligatorio": "True", "orden": 2},
            segmento=self.seg,
            subsegmento=self.sub,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("subsegmento", form.errors["orden"][0])

    def test_el_orden_del_subsegmento_es_independiente_del_segmento(self):
        # Cada alcance numera por su cuenta: el requisito propio del
        # subsegmento puede repetir el orden de uno heredado del segmento.
        self._crear_requisito("Del segmento", orden=1)
        self._crear_requisito("Del subsegmento", orden=1, subsegmento=self.sub)
        propio = RequisitoNativo.objects.get(texto="Del subsegmento")
        self.assertEqual(propio.orden, 1)
        self.assertEqual(propio.subsegmento, self.sub)

    def test_autonumera_el_subsegmento_desde_su_propia_numeracion(self):
        self._crear_requisito("Del segmento", orden=9)
        self._crear_requisito("Del subsegmento", subsegmento=self.sub)
        self.assertEqual(RequisitoNativo.objects.get(texto="Del subsegmento").orden, 1)

    def test_editar_sin_tocar_el_orden_no_choca_consigo_mismo(self):
        self._crear_requisito("Original", orden=4)
        req = RequisitoNativo.objects.get(texto="Original")
        resp = self.client.post(
            reverse("becas:requisito_editar", args=[req.pk]),
            {"texto": "Renombrado", "tipo": TipoCampo.STRING, "obligatorio": "True", "orden": 4},
        )
        self.assertEqual(resp.status_code, 302)
        req.refresh_from_db()
        self.assertEqual((req.texto, req.orden), ("Renombrado", 4))

    def test_editar_hacia_un_orden_ocupado_se_rechaza(self):
        self._crear_requisito("Primero", orden=1)
        self._crear_requisito("Segundo", orden=2)
        segundo = RequisitoNativo.objects.get(texto="Segundo")
        form = RequisitoNativoForm(
            {"texto": "Segundo", "tipo": TipoCampo.STRING, "obligatorio": "True", "orden": 1},
            instance=segundo,
            segmento=self.seg,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("orden 1", form.errors["orden"][0])


class OrdenPreguntasGlobalesTests(_BaseConfigTest):
    """Mismo contrato de orden para los requisitos generales."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)

    def _crear_pregunta(self, texto, orden=""):
        return self.client.post(
            reverse("becas:pregunta_crear"),
            {"texto": texto, "tipo": TipoCampo.STRING, "orden": orden, "obligatorio": "on", "activo": "on"},
        )

    def test_autonumera_cuando_el_orden_viene_vacio(self):
        tope = PreguntaGlobal.objects.aggregate(m=Max("orden"))["m"]
        self._crear_pregunta("Nueva")
        self.assertEqual(PreguntaGlobal.objects.get(texto="Nueva").orden, tope + 1)

    def test_rechaza_dos_preguntas_con_el_mismo_orden(self):
        self._crear_pregunta("Primera", orden=3)
        form = PreguntaGlobalForm(
            {"texto": "Repetida", "tipo": TipoCampo.STRING, "orden": 3, "obligatorio": "on", "activo": "on"}
        )
        self.assertFalse(form.is_valid())
        self.assertIn("orden 3", form.errors["orden"][0])

    def test_editar_sin_tocar_el_orden_no_choca_consigo_mismo(self):
        self._crear_pregunta("Original", orden=3)
        pregunta = PreguntaGlobal.objects.get(texto="Original")
        resp = self.client.post(
            reverse("becas:pregunta_editar", args=[pregunta.pk]),
            {"texto": "Renombrada", "tipo": TipoCampo.STRING, "orden": 3, "obligatorio": "on", "activo": "on"},
        )
        self.assertEqual(resp.status_code, 302)
        pregunta.refresh_from_db()
        self.assertEqual((pregunta.texto, pregunta.orden), ("Renombrada", 3))


class DestinoSiisPreguntaTests(TestCase):
    """Las preguntas globales declaran qué campo del alta en SIIS alimentan."""

    def setUp(self):
        call_command("seed_becas", stdout=StringIO())
        self.admin = User.objects.create_user("admin_cfg_siis", password="x")
        self.admin.groups.add(Group.objects.get(name=ROL_ADMIN))
        self.client.force_login(self.admin)

    def _post(self, texto, destino, activo="on"):
        datos = {"texto": texto, "tipo": TipoCampo.STRING, "orden": "", "obligatorio": "on", "destino_siis": destino}
        if activo:
            datos["activo"] = activo
        return self.client.post(reverse("becas:pregunta_crear"), datos)

    def test_crea_pregunta_con_destino(self):
        self._post("Localidad", "loc_actual")
        self.assertEqual(PreguntaGlobal.objects.get(texto="Localidad").destino_siis, "loc_actual")

    def test_rechaza_dos_activas_con_el_mismo_destino(self):
        self._post("Localidad", "loc_actual")
        form = PreguntaGlobalForm(
            {
                "texto": "Otra",
                "tipo": TipoCampo.STRING,
                "orden": "",
                "obligatorio": "on",
                "activo": "on",
                "destino_siis": "loc_actual",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("destino_siis", form.errors)
        self.assertIn("Localidad", form.errors["destino_siis"][0])

    def test_permite_repetir_destino_si_la_otra_esta_inactiva(self):
        self._post("Vieja", "loc_actual", activo="")
        resp = self._post("Nueva", "loc_actual")
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(PreguntaGlobal.objects.filter(destino_siis="loc_actual").count(), 2)

    def test_la_lista_muestra_el_destino(self):
        self._post("Localidad", "loc_actual")
        resp = self.client.get(reverse("becas:preguntas"))
        self.assertContains(resp, "SIIS: Localidad del domicilio")


class DestinoSiisRequisitoTests(_BaseConfigTest):
    """Cambio 80: los requisitos del segmento también pueden alimentar a SIIS."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)
        self.seg = Segmento.objects.create(nombre="Futuro", cupo_maximo=100)
        self.otro = Segmento.objects.create(nombre="Otro", cupo_maximo=100)

    def _post(self, segmento, texto, destino, **extra):
        datos = {"texto": texto, "tipo": TipoCampo.STRING, "orden": "", "obligatorio": "True", "destino_siis": destino}
        datos.update(extra)
        return self.client.post(reverse("becas:requisito_crear", args=[segmento.pk]), datos)

    def test_crea_requisito_con_destino(self):
        resp = self._post(self.seg, "Localidad", "loc_actual")
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(RequisitoNativo.objects.get(texto="Localidad").destino_siis, "loc_actual")

    def test_rechaza_dos_requisitos_con_el_mismo_destino_en_el_mismo_segmento(self):
        self._post(self.seg, "Localidad", "loc_actual")
        form = RequisitoNativoForm(
            {
                "texto": "Otra",
                "tipo": TipoCampo.STRING,
                "orden": "",
                "obligatorio": "True",
                "destino_siis": "loc_actual",
            },
            segmento=self.seg,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("destino_siis", form.errors)
        self.assertIn("Localidad", form.errors["destino_siis"][0])

    def test_dos_segmentos_pueden_repetir_el_destino(self):
        self._post(self.seg, "Localidad", "loc_actual")
        resp = self._post(self.otro, "Localidad", "loc_actual")
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(RequisitoNativo.objects.filter(destino_siis="loc_actual").count(), 2)

    def test_editar_sin_tocar_el_destino_lo_conserva(self):
        self._post(self.seg, "Localidad", "loc_actual")
        req = RequisitoNativo.objects.get(texto="Localidad")
        resp = self.client.post(
            reverse("becas:requisito_editar", args=[req.pk]),
            {
                "texto": "Localidad actual",
                "tipo": TipoCampo.STRING,
                "orden": req.orden,
                "obligatorio": "True",
                "destino_siis": "loc_actual",
            },
        )
        self.assertEqual(resp.status_code, 302)
        req.refresh_from_db()
        self.assertEqual((req.texto, req.destino_siis), ("Localidad actual", "loc_actual"))

    def test_la_lista_muestra_el_destino(self):
        self._post(self.seg, "Localidad", "loc_actual")
        resp = self.client.get(reverse("becas:requisitos_segmento") + f"?segmento={self.seg.pk}")
        self.assertContains(resp, "SIIS: Localidad del domicilio")


class RequisitosSegmentoModalesRenderTests(_BaseConfigTest):
    """Los 2 modales de requisitos_segmento.html con x-becas-modal y sin SVG."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)
        self.seg = Segmento.objects.create(nombre="Futuro", cupo_maximo=100)

    def test_modales_x_becas_modal_dialog_y_sin_svg(self):
        resp = self.client.get(reverse("becas:requisitos_segmento"))
        self.assertEqual(resp.status_code, 200)
        contenido = resp.content.decode()
        self.assertIn('x-becas-modal="modalCrear"', contenido)
        self.assertIn('x-becas-modal="modalEdit"', contenido)
        self.assertIn('role="dialog"', contenido)
        self.assertIn('aria-labelledby="modal-reqseg-crear-titulo"', contenido)
        self.assertIn('aria-labelledby="modal-reqseg-editar-titulo"', contenido)
        self.assertIn('<i class="fas fa-clipboard-list" aria-hidden="true"></i>', contenido)
        self.assertIn('<i class="fas fa-edit" aria-hidden="true"></i>', contenido)

    def test_fila_con_requisito_usa_nodo_icon_btn_y_aria_label(self):
        RequisitoNativo.objects.create(segmento=self.seg, texto="Localidad", tipo=TipoCampo.STRING, orden=1)
        resp = self.client.get(reverse("becas:requisitos_segmento") + f"?segmento={self.seg.pk}")
        self.assertContains(resp, 'aria-label="Editar requisito: Localidad"')
        self.assertContains(resp, 'aria-label="Eliminar requisito: Localidad"')
        self.assertContains(resp, 'data-confirm-danger="true"')
        self.assertContains(resp, 'class="nodo-icon-btn nodo-icon-btn--danger"')
        self.assertContains(resp, 'class="badge badge-white"')


class IdentificadoresSiisProgramaTests(TestCase):
    """Cambio 82: los tres ids del alta se escriben a mano y el plan avisa si
    difiere del que trajo la API."""

    URL = "becas:programa_identificadores_siis"

    def setUp(self):
        call_command("seed_becas", stdout=StringIO())
        self.admin = User.objects.create_user("admin_cfg_funcion", password="x")
        self.admin.groups.add(Group.objects.get(name=ROL_ADMIN))
        self.client.force_login(self.admin)
        self.programa = ProgramaSiis.objects.create(
            nombre="Ñachec",
            siis_programa_id=79,
            siis_programa_datos={"id": 79, "nombre": "Ñachec", "jurisdiccion_id": 28},
        )
        self.funciones = patch("programas.forms.funciones_programa").start()
        self.addCleanup(patch.stopall)
        self.funciones.return_value = [{"id": 4, "nombre": "Nivel Operativo", "id_programa": 79}]

    def _post(self, **datos):
        return self.client.post(reverse(self.URL, args=[self.programa.pk]), datos)

    def test_guarda_la_funcion_escrita_a_mano(self):
        resp = self._post(siis_funcion_id="4")
        self.assertEqual(resp.status_code, 302)
        self.programa.refresh_from_db()
        self.assertEqual(self.programa.siis_funcion_id, 4)
        self.assertEqual(self.programa.siis_funcion_nombre, "Nivel Operativo")

    def test_acepta_una_funcion_que_el_catalogo_no_tiene_y_no_le_pone_nombre(self):
        """El catálogo viene vacío cuando SIIS no reconoce el programa: si el
        select fuera la única vía, la convocatoria se quedaría sin salida."""
        self._post(siis_funcion_id="99")
        self.programa.refresh_from_db()
        self.assertEqual(self.programa.siis_funcion_id, 99)
        self.assertEqual(self.programa.siis_funcion_nombre, "")

    def test_el_plan_igual_al_de_la_api_no_queda_como_pisado(self):
        self._post(siis_id_plan_soc="79")
        self.programa.refresh_from_db()
        self.assertIsNone(self.programa.siis_id_plan_soc)
        self.assertFalse(self.programa.siis_id_plan_soc_pisado)
        self.assertEqual(self.programa.siis_id_plan_soc_efectivo, 79)

    def test_el_plan_distinto_se_guarda_sin_tocar_el_id_del_catalogo(self):
        self._post(siis_id_plan_soc="90")
        self.programa.refresh_from_db()
        self.assertEqual(self.programa.siis_id_plan_soc, 90)
        self.assertEqual(self.programa.siis_id_plan_soc_efectivo, 90)
        self.assertTrue(self.programa.siis_id_plan_soc_pisado)
        # ``siis_programa_id`` es la clave con la que se sincroniza el estado
        # contra el catálogo: pisarlo dejaría el programa en DESCONOCIDO.
        self.assertEqual(self.programa.siis_programa_id, 79)

    def test_el_detalle_avisa_cuando_el_plan_difiere(self):
        self._post(siis_id_plan_soc="90")
        resp = self.client.get(reverse("becas:programa_detalle", args=[self.programa.pk]))
        self.assertContains(resp, "Identificadores distintos de los que trajo SIIS")

    def test_la_jurisdiccion_igual_a_la_de_la_api_no_queda_como_pisada(self):
        self._post(siis_jurid="28")
        self.programa.refresh_from_db()
        self.assertIsNone(self.programa.siis_jurid)
        self.assertEqual(self.programa.siis_jurid_efectivo, 28)
        self.assertFalse(self.programa.siis_jurid_pisado)

    def test_la_jurisdiccion_distinta_queda_marcada(self):
        self._post(siis_jurid="31")
        self.programa.refresh_from_db()
        self.assertEqual(self.programa.siis_jurid_efectivo, 31)
        self.assertTrue(self.programa.siis_jurid_pisado)

    def test_requiere_administrar_programa(self):
        coord = User.objects.create_user("coord_cfg_funcion", password="x")
        coord.groups.add(Group.objects.get(name=ROL_COORDINADOR))
        self.client.force_login(coord)
        resp = self._post(siis_funcion_id="4")
        self.assertEqual(resp.status_code, 302)
        self.programa.refresh_from_db()
        self.assertIsNone(self.programa.siis_funcion_id)

    def test_el_detalle_muestra_los_identificadores_y_el_form(self):
        self.programa.siis_funcion_id = 4
        self.programa.siis_funcion_nombre = "Nivel Operativo"
        self.programa.save()
        resp = self.client.get(reverse("becas:programa_detalle", args=[self.programa.pk]))
        self.assertContains(resp, "Alta de beneficiarios en SIIS")
        self.assertContains(resp, "Nivel Operativo")
        self.assertContains(resp, reverse(self.URL, args=[self.programa.pk]))


class EliminarRequisitoYSubsegmentoTests(_BaseConfigTest):
    """RED-31: las dos vistas de borrado de Configuración, hasta acá sin ejecutar.

    `requisito_eliminar` y `subsegmento_eliminar` tenían el cuerpo entero sin
    ejecutar en la suite (coverage). Son las dos caras del mismo problema:
    `subsegmento_eliminar` atrapa `ProtectedError` y avisa, y `requisito_eliminar`
    borra en cascada —y se lleva puestos los `AdjuntoFormulario` de casos ya
    cargados, que es el bug de **DAT-01**—.

    Desde **DAT-01** (Cambio 168) las dos se comportan igual: `AdjuntoFormulario`
    pasó a PROTECT y `requisito_eliminar` convierte el `ProtectedError` en un aviso
    con el número de casos afectados. `test_requisito_con_adjunto_en_un_caso` es el
    test de RED-31 **invertido**: caracterizaba el daño —la fila del adjunto
    desaparecía— y ahora exige que el documento del ciudadano sobreviva.
    """

    def setUp(self):
        super().setUp()
        self.segmento = Segmento.objects.create(nombre="Seg borrados", cupo_maximo=100)
        self.client.force_login(self.admin)

    def _subsegmento(self, nombre="Sub"):
        return Subsegmento.objects.create(segmento=self.segmento, nombre=nombre, cupo_maximo=10)

    def _requisito(self, **extra):
        datos = {"texto": "Constancia", "tipo": TipoCampo.ARCHIVO, "segmento": self.segmento}
        datos.update(extra)
        return RequisitoNativo.objects.create(**datos)

    def _convocatoria(self, nombre, **extra):
        return Convocatoria.objects.create(
            nombre=nombre,
            segmento=self.segmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
            **extra,
        )

    # -- Subsegmento ---------------------------------------------------------

    def test_subsegmento_en_uso_por_una_convocatoria_no_se_borra_y_avisa(self):
        """`Convocatoria.subsegmento` es PROTECT: la vista tiene que convertir
        el `ProtectedError` en un aviso, no en un 500."""
        sub = self._subsegmento()
        self._convocatoria("Conv con sub", subsegmento=sub)

        resp = self.client.post(reverse("becas:subsegmento_eliminar", args=[sub.pk]), follow=True)

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(Subsegmento.objects.filter(pk=sub.pk).exists())
        self.assertIn(
            "No se puede eliminar el subsegmento porque está utilizado por una convocatoria.",
            [str(m) for m in resp.context["messages"]],
        )

    def test_subsegmento_libre_se_borra_y_redirige_al_segmento(self):
        sub = self._subsegmento()

        resp = self.client.post(reverse("becas:subsegmento_eliminar", args=[sub.pk]))

        self.assertRedirects(
            resp,
            reverse("becas:segmento_detalle", args=[self.segmento.pk]),
            fetch_redirect_response=False,
        )
        self.assertFalse(Subsegmento.objects.filter(pk=sub.pk).exists())

    # -- Requisito -----------------------------------------------------------

    def test_requisito_sin_adjuntos_se_borra_con_su_item_de_diseno(self):
        """Cambio 58: el ítem del diseño que referencia al requisito se va con
        él (el catálogo es dueño del campo). Lo que DAT-01 no puede hacer es
        «arreglar» la cascada dejando el ítem huérfano."""
        requisito = self._requisito()
        diseno = DisenoFormulario.objects.create(convocatoria=self._convocatoria("Conv diseno"))
        item = ItemDiseno.objects.create(
            diseno=diseno,
            tipo=ItemDiseno.Tipo.CAMPO,
            clave=f"rn-{requisito.pk}",
            requisito=requisito,
        )

        resp = self.client.post(reverse("becas:requisito_eliminar", args=[requisito.pk]))

        self.assertRedirects(
            resp,
            reverse("becas:segmento_detalle", args=[self.segmento.pk]),
            fetch_redirect_response=False,
        )
        self.assertFalse(RequisitoNativo.objects.filter(pk=requisito.pk).exists())
        self.assertFalse(ItemDiseno.objects.filter(pk=item.pk).exists())

    def _caso_con_adjunto(self, nombre_conv, **campo):
        """Un caso cargado con un documento subido para `pregunta_global=` o
        `requisito_nativo=`, que es lo que DAT-01 protege."""
        relevamiento = Relevamiento.objects.create(
            convocatoria=self._convocatoria(nombre_conv),
            territorial=self.admin,
            fecha_asignada=date(2026, 6, 1),
            zona="A",
        )
        formulario = Formulario.objects.create(relevamiento=relevamiento, celular="3624000000")
        adjunto = AdjuntoFormulario.objects.create(
            formulario=formulario,
            archivo=SimpleUploadedFile("constancia.pdf", b"%PDF-1.4", content_type="application/pdf"),
            **campo,
        )
        self.addCleanup(adjunto.archivo.storage.delete, adjunto.archivo.name)
        return formulario, adjunto

    def test_requisito_con_adjunto_en_un_caso(self):
        """**DAT-01: el documento del ciudadano sobrevive al borrado del catálogo.**

        Es el test de RED-31 invertido. Hasta el Cambio 168
        `AdjuntoFormulario.requisito_nativo` era CASCADE: borrar el requisito
        borraba la fila del adjunto de todos los casos ya cargados y dejaba el
        archivo huérfano en `media/`. El revisor abría el caso y la foto no estaba,
        sin error ni log —el bloque de revisión arma la vista desde la foto de la
        definición, así que lo mostraba como *faltante*, no como borrado—.
        """
        requisito = self._requisito()
        formulario, adjunto = self._caso_con_adjunto("Conv con caso", requisito_nativo=requisito)
        nombre, storage = adjunto.archivo.name, adjunto.archivo.storage

        resp = self.client.post(reverse("becas:requisito_eliminar", args=[requisito.pk]), follow=True)

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(RequisitoNativo.objects.filter(pk=requisito.pk).exists())
        self.assertTrue(AdjuntoFormulario.objects.filter(pk=adjunto.pk).exists())
        self.assertTrue(storage.exists(nombre))
        self.assertTrue(Formulario.objects.filter(pk=formulario.pk).exists())
        self.assertIn(
            "No se puede eliminar: 1 caso(s) ya subieron este documento.",
            [str(m) for m in resp.context["messages"]][0],
        )

    def test_el_aviso_cuenta_casos_y_no_archivos(self):
        """Dos documentos del mismo caso son **un** caso para quien configura."""
        requisito = self._requisito()
        formulario, _ = self._caso_con_adjunto("Conv dos adjuntos", requisito_nativo=requisito)
        extra = AdjuntoFormulario.objects.create(
            formulario=formulario,
            requisito_nativo=requisito,
            archivo=SimpleUploadedFile("otra.pdf", b"%PDF-1.4", content_type="application/pdf"),
        )
        self.addCleanup(extra.archivo.storage.delete, extra.archivo.name)

        resp = self.client.post(reverse("becas:requisito_eliminar", args=[requisito.pk]), follow=True)

        self.assertIn("1 caso(s)", [str(m) for m in resp.context["messages"]][0])

    def test_pregunta_con_adjunto_en_un_caso_no_se_borra_y_avisa(self):
        """La otra mitad de DAT-01: el mismo CASCADE colgaba de `PreguntaGlobal`.

        Acá sí hay salida y el mensaje la nombra: la pregunta se **desactiva** y
        deja de pedirse sin borrar el documento de nadie.
        """
        pregunta = PreguntaGlobal.objects.create(
            texto="Foto del certificado",
            tipo=TipoCampo.ARCHIVO,
            orden=900,
        )
        _, adjunto = self._caso_con_adjunto("Conv pregunta", pregunta_global=pregunta)

        resp = self.client.post(reverse("becas:pregunta_eliminar", args=[pregunta.pk]), follow=True)

        self.assertTrue(PreguntaGlobal.objects.filter(pk=pregunta.pk).exists())
        self.assertTrue(AdjuntoFormulario.objects.filter(pk=adjunto.pk).exists())
        self.assertIn(
            "No se puede eliminar: 1 caso(s) ya subieron este documento. Desactivala en lugar de borrarla.",
            [str(m) for m in resp.context["messages"]],
        )

    def test_pregunta_sin_adjuntos_se_borra_con_su_item_de_diseno(self):
        """Lo que DAT-01 **no** puede romper: sin adjuntos el catálogo sigue mandando
        y el ítem del diseño se va con la pregunta (Cambio 58)."""
        pregunta = PreguntaGlobal.objects.create(texto="Dato suelto", tipo=TipoCampo.STRING, orden=901)
        diseno = DisenoFormulario.objects.create(convocatoria=self._convocatoria("Conv pregunta libre"))
        item = ItemDiseno.objects.create(
            diseno=diseno,
            tipo=ItemDiseno.Tipo.CAMPO,
            clave=f"pg-{pregunta.pk}",
            pregunta=pregunta,
        )

        self.client.post(reverse("becas:pregunta_eliminar", args=[pregunta.pk]))

        self.assertFalse(PreguntaGlobal.objects.filter(pk=pregunta.pk).exists())
        self.assertFalse(ItemDiseno.objects.filter(pk=item.pk).exists())

    def test_el_admin_tampoco_borra_un_requisito_con_adjuntos(self):
        """DAT-01: la guarda es del modelo, así que `/admin/` también la tiene.

        El `/admin/` arma la cascada antes de borrar: con PROTECT los adjuntos
        aparecen como objetos protegidos, la confirmación no ofrece el botón y el
        POST no borra nada. Antes, la misma pantalla listaba los adjuntos entre lo
        que se iba a borrar y el POST se los llevaba.
        """
        requisito = self._requisito()
        _, adjunto = self._caso_con_adjunto("Conv admin", requisito_nativo=requisito)
        root = User.objects.create_superuser("root_dat01", "root@dat01.test", "x")
        self.client.force_login(root)
        url = reverse("admin:programas_requisitonativo_delete", args=[requisito.pk])

        resp = self.client.post(url, {"post": "yes"})

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context["protected"])
        self.assertTrue(RequisitoNativo.objects.filter(pk=requisito.pk).exists())
        self.assertTrue(AdjuntoFormulario.objects.filter(pk=adjunto.pk).exists())

    def test_el_subsegmento_frenado_por_un_adjunto_lo_dice_por_su_nombre(self):
        """El mensaje sigue a la causa real, no al único caso que había antes.

        `RequisitoNativo.subsegmento` es CASCADE, así que borrar el subsegmento
        intenta borrar sus requisitos y choca con el PROTECT de DAT-01. Decirle
        «está utilizado por una convocatoria» a eso manda a buscar donde no está.
        """
        sub = self._subsegmento("Sub con documentos")
        requisito = self._requisito(segmento=None, subsegmento=sub)
        self._caso_con_adjunto("Conv sub adjunto", requisito_nativo=requisito)

        resp = self.client.post(reverse("becas:subsegmento_eliminar", args=[sub.pk]), follow=True)

        self.assertTrue(Subsegmento.objects.filter(pk=sub.pk).exists())
        self.assertIn(
            "No se puede eliminar el subsegmento: alguno de sus requisitos ya tiene documentos subidos en 1 caso(s).",
            [str(m) for m in resp.context["messages"]],
        )

    # -- Método y capacidad --------------------------------------------------

    def test_las_dos_vistas_exigen_post_y_capacidad(self):
        """GET no borra nunca; anónimo va al login; sin la capacidad tampoco borra.

        Los objetos se crean una sola vez a propósito: si alguno de los tres
        caminos borrara, los siguientes `subTest` se quedarían sin objeto y el
        fallo se vería igual.
        """
        sin_rol = User.objects.create_user("sin_rol_borrados", password="x")
        for nombre, objeto in (
            ("becas:subsegmento_eliminar", self._subsegmento()),
            ("becas:requisito_eliminar", self._requisito()),
        ):
            url = reverse(nombre, args=[objeto.pk])
            modelo = type(objeto)

            with self.subTest(vista=nombre, caso="GET no borra"):
                self.client.force_login(self.admin)
                resp = self.client.get(url)
                self.assertEqual(resp.status_code, 302)
                self.assertTrue(modelo.objects.filter(pk=objeto.pk).exists())

            with self.subTest(vista=nombre, caso="anonimo va al login"):
                self.client.logout()
                resp = self.client.post(url)
                self.assertEqual(resp.status_code, 302)
                # El login del backoffice vive en la raíz, no en `/login/`.
                self.assertEqual(resp["Location"], f"{reverse(settings.LOGIN_URL)}?next={url}")
                self.assertTrue(modelo.objects.filter(pk=objeto.pk).exists())

            with self.subTest(vista=nombre, caso="sin la capacidad no borra"):
                self.client.force_login(sin_rol)
                resp = self.client.post(url)
                self.assertIn(resp.status_code, (302, 403))
                self.assertTrue(modelo.objects.filter(pk=objeto.pk).exists())
