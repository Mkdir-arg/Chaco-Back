"""Cambio 422: ver todos los dispositivos no abre el relevamiento de una institución ajena.

Caso QA 7. Un coordinador con «Ver dispositivos» amplio y «Crear, asignar, reasignar y
cancelar relevamientos edilicios» acotado a algunas instituciones abría el informe, las
fotos y los adjuntos de un edificio fuera de su alcance de inspección: el camino de
`dispositivo.ver` de `inspecciones_visibles` usaba el alcance de **lectura**
(`dispositivos_en_alcance`), que con `dispositivo.ver_todos` o el admin del programa es todo.

Decisión del PM (07/11/2026): el relevamiento lo ve quien lo coordina, el agente asignado y
quien opera una institución del edificio (su Equipo). Fuera de eso, 404, aunque vea todos los
dispositivos. El superusuario y el admin del programa con `inspeccion.asignar` siguen viendo todo.
"""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.urls import reverse

from programas.models import AdjuntoRespuestaRelevamiento, Edificio
from programas.services.inspecciones import crear_inspeccion, inspecciones_visibles
from programas.tests.test_dispositivos_relevamiento_informe import URL_LISTA, BaseInforme, _url

User = get_user_model()


class AlcanceDeLecturaNoAbreRelevamientosTests(BaseInforme):
    def setUp(self):
        super().setUp()
        # El usuario de QA: coordina el parador y lee todos los dispositivos.
        self.coord_ver_todos = self._usuario(
            "coord_ver_todos", ("dispositivo.ver", "dispositivo.ver_todos", "inspeccion.asignar"), [self.parador]
        )
        # Lee todo por ser admin del programa, pero no coordina relevamientos.
        self.admin_sin_asignar = self._usuario("admin_sin_asignar", ("dispositivo.ver", "programa.configurar"))
        self.ajeno = self._realizado(self.edificio_cis)
        self.ajeno_en_curso = self._crear_en_curso()
        self.propio = self._realizado()
        self.adjunto = AdjuntoRespuestaRelevamiento.objects.create(
            inspeccion=self.ajeno, clave="plano", archivo=ContentFile(b"%PDF-1.4 plano", name="plano.pdf")
        )

    def _crear_en_curso(self):
        otro = self._dispositivo("CIS-4", "CIS anexo")
        edificio = Edificio.objects.create(codigo="ED-CIS-4", nombre="Edificio CIS anexo")
        edificio.dispositivos.add(otro)
        return crear_inspeccion(
            self._fresco(self.admin),
            edificio=edificio,
            asignado_a=self._fresco(self.agente),
            fecha_vencimiento=self.vence,
        )

    def _estado_media(self, usuario, url):
        respuesta = self._cliente(usuario).get(url)
        if respuesta.streaming:
            b"".join(respuesta.streaming_content)
        return respuesta.status_code

    def _lectores_amplios(self):
        return (self.coord_ver_todos, self.admin_sin_asignar)

    def test_el_informe_ajeno_da_404(self):
        for usuario in self._lectores_amplios():
            with self.subTest(usuario=usuario.username):
                self.assertEqual(self._cliente(usuario).get(_url(self.ajeno)).status_code, 404)

    def test_las_fotos_y_los_adjuntos_ajenos_no_se_sirven(self):
        urls = [foto.archivo.url for foto in self.ajeno.fotos.all()] + [self.adjunto.archivo.url]
        self.assertEqual(len(urls), 2)
        for usuario in self._lectores_amplios():
            for url in urls:
                with self.subTest(usuario=usuario.username, url=url):
                    self.assertTrue(url.startswith(settings.MEDIA_URL))
                    self.assertIn(self._estado_media(usuario, url), (403, 404))

    def test_reasignar_y_cancelar_lo_ajeno_dan_404(self):
        cliente = self._cliente(self.coord_ver_todos)
        reasignar = reverse("dispositivos:relevamiento_reasignar", args=[self.ajeno_en_curso.pk])
        cancelar = reverse("dispositivos:relevamiento_cancelar", args=[self.ajeno_en_curso.pk])

        self.assertEqual(cliente.post(reasignar, {"asignado_a": self.otro_agente.pk}).status_code, 404)
        self.assertEqual(cliente.post(cancelar, {"motivo": "Duplicado"}).status_code, 404)
        self.ajeno_en_curso.refresh_from_db()
        self.assertEqual(self.ajeno_en_curso.asignado_a_id, self.agente.pk)
        self.assertEqual(self.ajeno_en_curso.estado, self.ajeno_en_curso.Estado.ASIGNADA)

    def test_lo_ajeno_no_aparece_en_el_listado_ni_en_sus_solapas(self):
        respuesta = self._cliente(self.coord_ver_todos).get(URL_LISTA)

        self.assertEqual(respuesta.status_code, 200)
        filas = {fila.pk for solapa in respuesta.context["solapas"] for fila in solapa["filas"]}
        self.assertIn(self.propio.pk, filas)
        self.assertNotIn(self.ajeno.pk, filas)
        self.assertNotIn(self.ajeno_en_curso.pk, filas)
        visibles = set(inspecciones_visibles(self._fresco(self.coord_ver_todos)).values_list("pk", flat=True))
        self.assertEqual(visibles, {self.propio.pk})

    def test_lo_de_su_alcance_lo_sigue_viendo(self):
        self.assertEqual(self._cliente(self.coord_ver_todos).get(_url(self.propio)).status_code, 200)

    def test_la_solapa_infraestructura_ajena_no_lista_sus_relevamientos(self):
        """Ve el detalle del CIS por `ver_todos`, pero el registro no enlaza informes que darían 404."""

        respuesta = self._cliente(self.coord_ver_todos).get(reverse("dispositivos:detalle", args=[self.cis.pk]))

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context["infraestructura"]["eventos"], [])
        self.assertNotContains(respuesta, _url(self.ajeno))

    def test_el_admin_del_programa_con_asignar_y_el_superusuario_ven_todo(self):
        superusuario = User.objects.create_superuser(username="super", password="x")
        for usuario in (self.admin, superusuario):
            for inspeccion in (self.ajeno, self.propio):
                with self.subTest(usuario=usuario.username, inspeccion=inspeccion.pk):
                    self.assertEqual(self._cliente(usuario).get(_url(inspeccion)).status_code, 200)
            for url in [foto.archivo.url for foto in self.ajeno.fotos.all()] + [self.adjunto.archivo.url]:
                with self.subTest(usuario=usuario.username, url=url):
                    self.assertEqual(self._estado_media(usuario, url), 200)

    def test_el_agente_asignado_sigue_viendo_lo_suyo(self):
        """El agente no tiene alcance sobre el CIS: lo ve por ser quien lo relevó."""

        self.assertEqual(self._cliente(self.agente).get(_url(self.ajeno)).status_code, 200)

    def test_quien_opera_la_institucion_sigue_viendo_su_edificio(self):
        """El Equipo de la institución sí abre: es el relevamiento de su propio edificio."""

        operador_cis = self._usuario("operador_cis", ("dispositivo.ver",), [self.cis])

        self.assertEqual(self._cliente(operador_cis).get(_url(self.ajeno)).status_code, 200)
        self.assertEqual(self._cliente(operador_cis).get(_url(self.propio)).status_code, 404)
