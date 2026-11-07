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
from programas.tests.test_dispositivos_relevamiento_informe import URL_LISTA, BaseInforme, Criticidad, _url

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


class EdificioCompartidoTests(BaseInforme):
    """Cambio 428, decisión 1: el relevamiento es del edificio, y un edificio puede ser de varios dispositivos.

    Quien tiene alcance de inspección sobre ALGUNO de los dispositivos vinculados lo ve (listado,
    informe, fotos); fuera de eso, 404 aunque lea todos los dispositivos.
    """

    def setUp(self):
        super().setUp()
        # Un edificio de dos dispositivos que no comparten nada más: el parador y el CIS.
        self.compartido = Edificio.objects.create(codigo="ED-COMP", nombre="Predio parador y CIS")
        self.compartido.dispositivos.add(self.parador, self.cis)
        self.inspeccion = self._realizado(self.compartido)
        self.operador_cis = self._usuario("operador_cis", ("dispositivo.ver",), [self.cis])
        self.operador_parador = self._usuario("operador_parador", ("dispositivo.ver",), [self.parador])
        self.operador_ajeno = self._usuario("operador_ajeno", ("dispositivo.ver",), [self.sin_edificio])
        self.lector_amplio = self._usuario("lector_amplio", ("dispositivo.ver", "dispositivo.ver_todos"))

    def test_cada_dispositivo_vinculado_alcanza_para_ver_el_informe_y_las_fotos(self):
        urls = [foto.archivo.url for foto in self.inspeccion.fotos.all()]
        self.assertEqual(len(urls), 1)
        for usuario in (self.operador_cis, self.operador_parador, self.coordinador):
            with self.subTest(usuario=usuario.username):
                self.assertEqual(self._cliente(usuario).get(_url(self.inspeccion)).status_code, 200)
                self.assertEqual(self._cliente(usuario).get(urls[0]).status_code, 200)

    def _ids_visibles(self, usuario):
        return set(inspecciones_visibles(self._fresco(usuario)).values_list("pk", flat=True))

    def test_el_listado_lo_incluye_para_quien_opera_alguno_de_los_vinculados(self):
        for usuario in (self.operador_cis, self.operador_parador, self.coordinador):
            with self.subTest(usuario=usuario.username):
                self.assertIn(self.inspeccion.pk, self._ids_visibles(usuario))
        filas = {
            fila.pk
            for solapa in self._cliente(self.coordinador).get(URL_LISTA).context["solapas"]
            for fila in solapa["filas"]
        }
        self.assertIn(self.inspeccion.pk, filas)

    def test_quien_no_opera_ninguno_de_los_vinculados_recibe_404(self):
        url_foto = self.inspeccion.fotos.first().archivo.url
        for usuario in (self.operador_ajeno, self.lector_amplio):
            with self.subTest(usuario=usuario.username):
                self.assertEqual(self._cliente(usuario).get(_url(self.inspeccion)).status_code, 404)
                self.assertIn(self._cliente(usuario).get(url_foto).status_code, (403, 404))
                self.assertNotIn(self.inspeccion.pk, self._ids_visibles(usuario))


class FranjaInfraestructuraSinAlcanceTests(BaseInforme):
    """Cambio 428, decisión 2: sin alcance de inspección, el detalle del dispositivo da solo el semáforo."""

    def setUp(self):
        super().setUp()
        self.inspeccion = self._realizado(
            self.predio, criticidad=Criticidad.ALTA, observaciones="Humedad estructural en el techo"
        )
        self.lector_amplio = self._usuario("lector_amplio", ("dispositivo.ver", "dispositivo.ver_todos"))
        self.operador = self._usuario("operador_par", ("dispositivo.ver",), [self.parador])

    def _detalle(self, usuario):
        return self._cliente(usuario).get(reverse("dispositivos:detalle", args=[self.parador.pk]))

    @staticmethod
    def _panel(respuesta):
        """El HTML de la solapa Infraestructura: el historial es otra solapa con su propia regla."""

        return respuesta.content.decode().split('id="panel-infraestructura"')[1].split('role="tabpanel"')[0]

    def test_sin_alcance_ve_el_semaforo_y_la_fecha_pero_no_observaciones_ni_relevador(self):
        respuesta = self._detalle(self.lector_amplio)

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context["infraestructura"]["semaforo"].texto, "Crítico")
        panel = self._panel(respuesta)
        self.assertIn("Crítico", panel)
        self.assertIn(self.inspeccion.realizada_en.strftime("%d/%m/%Y"), panel)
        self.assertNotIn("Humedad estructural", panel)
        self.assertNotIn(self.nombre_agente, panel)
        self.assertFalse(respuesta.context["infraestructura"]["edificios"][0]["ve_detalle"])

    def test_con_alcance_y_el_superusuario_lo_ven_todo(self):
        superusuario = User.objects.create_superuser(username="super2", password="x")
        for usuario in (self.operador, self.admin, superusuario):
            with self.subTest(usuario=usuario.username):
                panel = self._panel(self._detalle(usuario))
                self.assertIn("Humedad estructural", panel)
                self.assertIn(self.nombre_agente, panel)
