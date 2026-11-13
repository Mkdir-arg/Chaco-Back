"""Módulo Emergencia, PR 3: el backoffice de la mesa — bandeja (E2), ficha (E3) y «Nuevo caso».

Las reglas del caso ya están probadas contra el servicio en ``test_emergencia_casos``. Acá
se prueba **la puerta HTTP**: que cada vista exija lo que tiene que exigir, que traduzca lo
que contesta el servicio sin escribir nada por su cuenta, y que las dos pantallas cuesten
un número fijo de consultas.

* **Acceso** — sin login, al login; sin operar ni supervisar la mesa, 403; con cualquiera
  de las dos, adentro. El barrido de URLs ``emergencia:*`` de ``test_emergencia_base`` cubre
  las rutas nuevas sin que nadie las liste.
* **RU-12 / RU-13** — quien no tiene tomado el caso lo ve en solo lectura, y un POST directo
  a derivar, cerrar o contactar recibe 403 y no cambia nada. Quien supervisa actúa sin tomar.
  Visto en rojo contra la regla invertida: con ``_exigir_duenio_o_supervisor`` devolviendo
  ``False`` sin mirar, los cinco POST de ``test_un_post_directo_recibe_403_y_nada_cambia``
  contestan 302 y escriben, y ``SupervisorTests`` pierde la marca «por supervisor».
* **02 §9** — la «segunda pestaña» recibe el aviso de recargar, nunca un 500.
* **RU-19** — el semáforo siempre lleva texto.
* **Presupuestos** — E2 con 500 casos abiertos y E3 con 50 dispositivos (``--tag performance``).
"""

import re
import shutil
import tempfile
from datetime import timedelta
from pathlib import Path

from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.template.loader import get_template
from django.test import override_settings, tag
from django.urls import reverse

from core.models import Localidad
from legajos.models import Ciudadano
from programas.models import (
    AdjuntoCaso,
    CasoEmergencia,
    ContactoCaso,
    Derivacion,
    GrupoFamiliar,
    NumeradorEmergencia,
    TrazaCaso,
)
from programas.selectors import emergencia_mesa as mesa
from programas.services import emergencia as servicio
from programas.tests.test_emergencia_base import OPERAR, SUPERVISAR, urls_de_emergencia
from programas.tests.test_emergencia_casos import JPEG, T0, BaseCasos
from programas.views.emergencia import CASOS_POR_PAGINA

Estado = CasoEmergencia.Estado
Origen = CasoEmergencia.Origen
Prioridad = CasoEmergencia.Prioridad
Accion = TrazaCaso.Accion

URL_BANDEJA = "/emergencia/casos/"
URL_NUEVO = "/emergencia/casos/nuevo/"

#: Las acciones POST de un caso y un cuerpo que su formulario acepta.
ACCIONES = {
    "caso_tomar": {},
    "caso_soltar": {},
    "caso_reasignar": {"operador": "0"},
    "caso_prioridad": {"prioridad": "ALTA"},
    "caso_contacto": {"canal": "LLAMADA", "resultado": "ATENDIO", "observacion": ""},
    "caso_derivar": {"dispositivo": "0", "plazas": "2"},
    "caso_cancelar_derivacion": {"motivo": "Se equivocaron de familia"},
    "caso_cerrar": {"motivo": "NO_REQUIERE", "observacion": ""},
}

SEMAFORO = re.compile(r'<span class="badge badge-dot [^"]+" data-semaforo-sla="([A-Z_]*)"[^>]*>(.*?)</span>', re.S)


def _texto(html):
    return " ".join(re.sub(r"<[^>]+>", " ", html).split())


class BaseMesa(BaseCasos):
    """La mesa con una localidad, un dispositivo con lugar y los atajos de las pruebas HTTP."""

    def setUp(self):
        super().setUp()
        self.resistencia = Localidad.objects.create(nombre="Resistencia")
        self.club = self._dispositivo("Club Sarmiento", camas=10, localidad="Resistencia")

    def _url(self, nombre, caso):
        return reverse(f"emergencia:{nombre}", args=[caso.pk])

    def _ficha(self, caso, **parametros):
        return self.client.get(self._url("caso_detalle", caso), parametros)

    def _post(self, nombre, caso, datos=None):
        return self.client.post(self._url(nombre, caso), datos or {})

    def _avisos(self, respuesta):
        """Los avisos que dejó **este** pedido (no los que quedaron sin mostrar de los anteriores)."""
        dejados = [str(mensaje) for mensaje in get_messages(respuesta.wsgi_request)._queued_messages]
        # Se consumen, como hace la pantalla al dibujarlos: el próximo pedido arranca limpio.
        list(get_messages(respuesta.wsgi_request))
        return dejados

    def _formulario1(self, **cambios):
        datos = {
            "traslado": GrupoFamiliar.Traslado.BOMBEROS,
            "dni": str(next(self._dnis)),
            "nombre": "Rosa",
            "apellido": "Benítez",
            "telefono": "3624 555555",
            "adultos_f": "1",
            "adultos_m": "1",
            "menores_f": "0",
            "direccion": "Av. Sarmiento 1200",
            "localidad": str(self.resistencia.pk),
        }
        datos.update(cambios)
        return datos


# ---------------------------------------------------------------------------
# Acceso
# ---------------------------------------------------------------------------


class AccesoTests(BaseMesa):
    def setUp(self):
        super().setUp()
        self.caso = self._caso()
        self.gets = [URL_BANDEJA, URL_NUEVO, self._url("caso_detalle", self.caso)]
        self.posts = [self._url(nombre, self.caso) for nombre in ACCIONES]

    def test_las_urls_son_las_del_namespace_emergencia(self):
        self.assertEqual(reverse("emergencia:bandeja"), URL_BANDEJA)
        self.assertEqual(reverse("emergencia:caso_nuevo"), URL_NUEVO)

    def test_el_barrido_del_modulo_cubre_las_rutas_de_la_mesa(self):
        """El barrido de ``test_emergencia_base`` (rol de Becas, ciudadano) las prueba sin listarlas."""
        urls = urls_de_emergencia()
        self.assertIn(URL_BANDEJA, urls)
        self.assertIn(URL_NUEVO, urls)
        for nombre in (
            "tomar",
            "soltar",
            "reasignar",
            "prioridad",
            "contacto",
            "derivar",
            "cancelar-derivacion",
            "cerrar",
        ):
            with self.subTest(accion=nombre):
                self.assertTrue([url for url in urls if url.endswith(f"/{nombre}/")], nombre)
        self.assertGreaterEqual(len(urls), 12)

    def test_sin_login_todo_redirige_al_login(self):
        for url in self.gets + self.posts:
            with self.subTest(url=url):
                respuesta = self.client.get(url)
                self.assertEqual(respuesta.status_code, 302)
                self.assertEqual(respuesta.url, f"{reverse('users:login')}?next={url}")
                self.assertEqual(self.client.post(url, {}).status_code, 302)

    def test_sin_operar_ni_supervisar_todo_rechaza(self):
        colado = self._usuario("colado", [OPERAR, SUPERVISAR], programa=self.becas)
        for usuario in (self._usuario("sin_rol"), self.agente, colado):
            self.client.force_login(usuario)
            for url in self.gets + self.posts:
                with self.subTest(usuario=usuario.username, url=url):
                    self.assertEqual(self.client.get(url).status_code, 403)
                    self.assertEqual(self.client.post(url, {}).status_code, 403)
        self.assertEqual(self._fila(self.caso)["estado"], Estado.NUEVO)
        self.assertEqual(CasoEmergencia.objects.count(), 1)

    def test_quien_opera_y_quien_solo_supervisa_abren_las_tres_pantallas(self):
        for usuario in (self.operador, self.supervisor):
            self.client.force_login(usuario)
            for url in self.gets:
                with self.subTest(usuario=usuario.username, url=url):
                    self.assertEqual(self.client.get(url).status_code, 200)

    def test_las_acciones_no_se_abren_por_get(self):
        self.client.force_login(self.operador)
        for url in self.posts:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 405 if "reasignar" not in url else 403)

    def test_un_caso_que_no_existe_es_un_404(self):
        self.client.force_login(self.operador)
        self.assertEqual(self.client.get(reverse("emergencia:caso_detalle", args=[999_999])).status_code, 404)
        self.assertEqual(self.client.post(reverse("emergencia:caso_tomar", args=[999_999])).status_code, 404)

    def test_reasignar_es_solo_de_quien_supervisa(self):
        """RU §6 n.° 1, por HTTP: 403 y la fila no cambia."""
        self.client.force_login(self.operador)
        respuesta = self._post("caso_reasignar", self.caso, {"operador": self.otro_operador.pk})
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(self._fila(self.caso)["tomado_por_id"], None)
        self.assertEqual(len(self._trazas(self.caso)), 1)


class SidebarTests(BaseMesa):
    ENLACE_BANDEJA = 'href="/emergencia/casos/"'
    ENLACE_CONFIGURACION = 'href="/emergencia/config/"'

    def _inicio(self, usuario):
        self.client.force_login(usuario)
        respuesta = self.client.get(reverse("core:inicio"))
        self.assertEqual(respuesta.status_code, 200)
        return respuesta

    def test_quien_opera_ve_la_bandeja_y_no_la_configuracion(self):
        respuesta = self._inicio(self.operador)
        self.assertContains(respuesta, self.ENLACE_BANDEJA)
        self.assertNotContains(respuesta, self.ENLACE_CONFIGURACION)

    def test_quien_supervisa_ve_las_dos(self):
        respuesta = self._inicio(self.supervisor)
        self.assertContains(respuesta, self.ENLACE_BANDEJA)
        self.assertContains(respuesta, self.ENLACE_CONFIGURACION)

    def test_un_rol_de_becas_no_ve_ninguna(self):
        respuesta = self._inicio(self._usuario("becario", ["becas.segmento.ver"], programa=self.becas))
        self.assertNotContains(respuesta, self.ENLACE_BANDEJA)
        self.assertNotContains(respuesta, self.ENLACE_CONFIGURACION)

    def test_quien_solo_releva_tampoco(self):
        self.client.force_login(self.agente)
        respuesta = self.client.get(reverse("core:inicio"))
        self.assertNotContains(respuesta, self.ENLACE_BANDEJA, status_code=respuesta.status_code)

    def test_la_entrada_marca_la_pantalla_en_la_que_se_esta(self):
        self.client.force_login(self.supervisor)
        bandeja = self.client.get(URL_BANDEJA).content.decode()
        configuracion = self.client.get(reverse("emergencia:configuracion")).content.decode()
        # Las dos entradas del grupo desplegado (el ícono del menú colapsado es del módulo entero).
        marca = re.compile(r'href="(/emergencia/[a-z]+/)"\s+class="flex items-center gap-2[^>]*aria-current="page"')
        self.assertEqual(set(marca.findall(bandeja)), {"/emergencia/casos/"})
        self.assertEqual(set(marca.findall(configuracion)), {"/emergencia/config/"})


# ---------------------------------------------------------------------------
# «Nuevo caso»
# ---------------------------------------------------------------------------


class NuevoCasoTests(BaseMesa):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.operador)
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)
        ajuste = override_settings(MEDIA_ROOT=self.media)
        ajuste.enable()
        self.addCleanup(ajuste.disable)

    def test_el_formulario_tiene_los_cuatro_bloques_y_csrf(self):
        respuesta = self.client.get(URL_NUEVO)
        self.assertTemplateUsed(respuesta, "programas/emergencia/casos/form.html")
        for bloque in (
            "Traslado y responsable",
            "Personas que ingresan juntas",
            "Necesitan asistencia",
            "Ubicación y fotos",
        ):
            self.assertContains(respuesta, bloque)
        self.assertContains(respuesta, "csrfmiddlewaretoken")
        self.assertContains(respuesta, 'enctype="multipart/form-data"')
        # RN-1.1: el albergue no se elige al relevar.
        self.assertNotIn("dispositivo", respuesta.context["form"].fields)

    def test_crea_el_caso_con_origen_mesa_tomado_por_quien_lo_carga(self):
        """HU-1.4."""
        respuesta = self.client.post(URL_NUEVO, self._formulario1(lactantes="0", menores_f="1", embarazo="on"))

        caso = CasoEmergencia.objects.get()
        self.assertRedirects(respuesta, self._url("caso_detalle", caso))
        self.assertEqual(
            (caso.origen, caso.estado, caso.tomado_por_id, caso.relevado_por_id, caso.tomado_en),
            (Origen.MESA, Estado.EN_GESTION, self.operador.pk, self.operador.pk, T0),
        )
        self.assertEqual((caso.latitud, caso.longitud, caso.localidad_id), (None, None, self.resistencia.pk))
        # El total y la prioridad los calcula el servidor.
        self.assertEqual((caso.grupo.total_declarado, caso.prioridad), (3, Prioridad.ALTA))
        self.assertEqual(caso.situacion, {"telefono": "3624 555555"})
        self.assertEqual(caso.necesidades["embarazo"], True)
        self.assertEqual([t.accion for t in self._trazas(caso)], [Accion.CREADO])
        self.assertIn(f"Caso {caso.numero} cargado", self._avisos(respuesta)[0])

    def test_un_total_o_una_prioridad_que_mande_el_cliente_no_cuentan(self):
        self.client.post(URL_NUEVO, self._formulario1(total_declarado="40", prioridad="ALTA", estado="CERRADO"))
        caso = CasoEmergencia.objects.get()
        self.assertEqual(
            (caso.grupo.total_declarado, caso.prioridad, caso.estado), (2, Prioridad.BAJA, Estado.EN_GESTION)
        )

    def test_la_localidad_es_obligatoria_en_la_mesa(self):
        respuesta = self.client.post(URL_NUEVO, self._formulario1(localidad=""))
        self.assertEqual(respuesta.status_code, 400)
        self.assertTrue(respuesta.context["form"].errors["localidad"])
        self.assertFalse(CasoEmergencia.objects.exists())

    def test_la_entrada_invalida_vuelve_con_el_error_en_su_campo(self):
        invalidos = {
            "dni": "12",
            "direccion": "",
            "traslado": "",
            "adultos_f": "-1",
            "lactantes": "uno",
            "localidad": "999999",
        }
        for campo, valor in invalidos.items():
            with self.subTest(campo=campo):
                respuesta = self.client.post(URL_NUEVO, self._formulario1(**{campo: valor}))
                self.assertEqual(respuesta.status_code, 400)
                self.assertTrue(respuesta.context["form"].errors[campo])
        respuesta = self.client.post(URL_NUEVO, self._formulario1(traslado="OTRA"))
        self.assertTrue(respuesta.context["form"].errors["traslado_otro"])
        self.assertFalse(CasoEmergencia.objects.exists())
        self.assertFalse(NumeradorEmergencia.objects.filter(ultimo__gt=0).exists())

    def test_lo_que_rechaza_el_servicio_vuelve_al_campo_o_arriba(self):
        """Las reglas del caso no están en el formulario: las dice ``crear_caso`` y la pantalla las muestra."""
        sin_personas = self.client.post(URL_NUEVO, self._formulario1(adultos_f="0", adultos_m="0"))
        self.assertEqual(sin_personas.status_code, 400)
        self.assertContains(sin_personas, "Cargá al menos una persona.", status_code=400)
        self.assertEqual(sin_personas.context["form"].non_field_errors(), ["Cargá al menos una persona."])

        de_mas = self.client.post(URL_NUEVO, self._formulario1(lactantes="1"))
        self.assertEqual(de_mas.context["form"].errors["lactantes"], ["No puede haber más lactantes que menores."])

        sin_nombre = self.client.post(URL_NUEVO, self._formulario1(nombre="", apellido=""))
        self.assertIn("no está en el legajo", sin_nombre.context["form"].errors["nombre"][0])
        self.assertFalse(CasoEmergencia.objects.exists())

    def test_con_la_persona_en_el_legajo_no_hace_falta_el_nombre(self):
        persona = Ciudadano.objects.create(dni="30777001", nombre="Marta", apellido="Sosa")
        self.client.post(URL_NUEVO, self._formulario1(dni="30.777.001", nombre="", apellido=""))
        self.assertEqual(CasoEmergencia.objects.get().grupo.responsable_id, persona.pk)
        self.assertEqual(Ciudadano.objects.filter(dni="30777001").count(), 1)

    def test_las_fotos_se_guardan_y_la_ficha_las_muestra_por_media_protegida(self):
        datos = self._formulario1(
            foto_vivienda=SimpleUploadedFile("casa.jpg", JPEG, content_type="image/jpeg"),
            foto_acceso=SimpleUploadedFile("calle.jpg", JPEG, content_type="image/jpeg"),
        )
        self.client.post(URL_NUEVO, datos)

        caso = CasoEmergencia.objects.get()
        adjuntos = {adjunto.tipo: adjunto for adjunto in AdjuntoCaso.objects.filter(caso=caso)}
        self.assertEqual(set(adjuntos), {AdjuntoCaso.Tipo.VIVIENDA, AdjuntoCaso.Tipo.ACCESO})
        ficha = self._ficha(caso)
        for adjunto in adjuntos.values():
            self.assertTrue(adjunto.archivo.name.startswith(f"emergencia/casos/{caso.carpeta_media}/"))
            self.assertContains(ficha, f'src="{adjunto.archivo.url}"')
            # La sirve la vista autenticada, y a quien no trabaja en la mesa le dice que no.
            self.assertEqual(self.client.get(adjunto.archivo.url).status_code, 200)
        self.assertContains(ficha, "Foto de la vivienda del caso")
        self.client.force_login(self._usuario("becario", ["becas.segmento.ver"], programa=self.becas))
        self.assertEqual(self.client.get(adjuntos[AdjuntoCaso.Tipo.VIVIENDA].archivo.url).status_code, 403)

    def test_un_archivo_que_no_es_una_foto_se_rechaza_en_su_campo(self):
        datos = self._formulario1(
            foto_acceso=SimpleUploadedFile("nota.pdf", b"%PDF-1.4", content_type="application/pdf")
        )
        respuesta = self.client.post(URL_NUEVO, datos)
        self.assertEqual(respuesta.status_code, 400)
        self.assertTrue(respuesta.context["form"].errors["foto_acceso"])
        self.assertFalse(CasoEmergencia.objects.exists())


# ---------------------------------------------------------------------------
# E2 · Bandeja
# ---------------------------------------------------------------------------


class BandejaTests(BaseMesa):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.operador)

    def _numeros(self, respuesta):
        return [fila["caso"].numero for fila in respuesta.context["filas"]]

    def _chips(self, respuesta):
        chips = respuesta.context["solapas_por_estado"] + respuesta.context["solapas_de_atencion"]
        return {chip["texto"]: chip for chip in chips}

    def test_sin_casos_ofrece_cargar_el_primero(self):
        respuesta = self.client.get(URL_BANDEJA)
        self.assertTemplateUsed(respuesta, "programas/emergencia/casos/list.html")
        self.assertContains(respuesta, "Todavía no hay casos")
        self.assertContains(respuesta, f'href="{URL_NUEVO}"')

    def test_las_ocho_solapas_llevan_su_conteo(self):
        nuevo = self._caso(apellido="Acosta")
        mio = self._caso_tomado(apellido="Benítez")
        derivado = self._caso_tomado(apellido="Cáceres")
        servicio.derivar_caso(derivado, self.operador, self.club, 2)
        cerrado = self._caso_tomado(apellido="Díaz")
        servicio.cerrar_sin_alojamiento(cerrado, self.operador, CasoEmergencia.MotivoCierre.NO_REQUIERE)
        self.reloj.avanzar(minutes=16)  # el nuevo, sin tomar, ya pasó sus 15 minutos

        respuesta = self.client.get(URL_BANDEJA)

        chips = self._chips(respuesta)
        self.assertEqual(
            {texto: chip["n"] for texto, chip in chips.items()},
            {
                "Abiertos": 3,
                "Nuevos": 1,
                "En gestión": 1,
                "Derivados": 1,
                "Ingreso en curso": 0,
                "Cerrados": 1,
                "Fuera de SLA": 1,
                "Ingreso directo": 0,
            },
        )
        self.assertEqual([texto for texto, chip in chips.items() if chip["activo"]], ["Abiertos"])
        # Por defecto, los abiertos: fuera de SLA primero, y el cerrado no está.
        self.assertEqual(self._numeros(respuesta), [nuevo.numero, mio.numero, derivado.numero])
        self.assertEqual(self._numeros(self.client.get(URL_BANDEJA, {"solapa": "cerrados"})), [cerrado.numero])
        self.assertEqual(self._numeros(self.client.get(URL_BANDEJA, {"solapa": "fuera_sla"})), [nuevo.numero])
        self.assertContains(respuesta, 'aria-current="true"')

    def test_la_fila_muestra_familia_estado_prioridad_y_quien_lo_tiene(self):
        caso = self._caso_tomado(apellido="Benítez", embarazo=True, localidad=self.resistencia.pk)
        respuesta = self.client.get(URL_BANDEJA)
        fila = respuesta.context["filas"][0]
        self.assertEqual(
            (fila["familia"], fila["detalle"], fila["localidad"], fila["tomado_por"]),
            ("Familia Benítez", f"2 personas · Caso {caso.numero}", "Resistencia", "Ana López"),
        )
        self.assertEqual((fila["estado_texto"], fila["prioridad_texto"]), ("En gestión", "Alta"))
        self.assertContains(respuesta, '<span class="badge badge-dot badge-warning">En gestión</span>', html=True)
        self.assertContains(respuesta, '<span class="badge badge-danger">Alta</span>', html=True)
        self.assertContains(respuesta, f'aria-label="Abrir el caso {caso.numero} de la Familia Benítez"')

    def test_tomar_se_ofrece_solo_en_los_nuevos(self):
        nuevo = self._caso()
        tomado = self._caso_tomado()
        respuesta = self.client.get(URL_BANDEJA)
        self.assertContains(respuesta, f'action="{self._url("caso_tomar", nuevo)}"')
        self.assertNotContains(respuesta, f'action="{self._url("caso_tomar", tomado)}"')

    def test_las_marcas_de_la_fila_van_en_texto(self):
        aproximado = self._caso(latitud="-27.451", longitud="-58.986", precision_m=250)
        self._caso(dni=aproximado.grupo.responsable.dni)  # la misma persona, otra vez
        self.reloj.avanzar(minutes=1)
        demorado = self._caso(relevado_en=T0 - timedelta(minutes=105))
        alojado = self._caso()
        self._ocupar(self.club, 1)
        estadia = self.club.estadias.get()
        estadia.ciudadano = alojado.grupo.responsable
        estadia.clave_alojamiento = estadia.clave_para(alojado.grupo.responsable)
        estadia.save()

        html = self.client.get(URL_BANDEJA).content.decode()

        self.assertIn("Ubicación aproximada", html)
        self.assertEqual(html.count("Posible duplicado: caso "), 2)
        self.assertIn("Relevado 08:15 · enviado 10:01", html)
        self.assertIn("Responsable alojado en Club Sarmiento", html)
        self.assertNotIn("Ingreso parcial", html)
        self.assertEqual(demorado.estado, Estado.NUEVO)

    def test_un_caso_relevado_y_enviado_en_el_momento_no_lleva_la_marca(self):
        self._caso()
        self.assertNotContains(self.client.get(URL_BANDEJA), "enviado")

    def test_los_filtros(self):
        mio = self._caso_tomado(apellido="Benítez", localidad=self.resistencia.pk, embarazo=True)
        ajeno = self._caso_tomado(por=self.otro_operador, apellido="Cáceres")
        nuevo = self._caso(apellido="Acosta")

        def numeros(**filtros):
            return set(self._numeros(self.client.get(URL_BANDEJA, filtros)))

        self.assertEqual(numeros(operador="mios"), {mio.numero})
        self.assertEqual(numeros(operador=str(self.otro_operador.pk)), {ajeno.numero})
        self.assertEqual(numeros(estado="NUEVO"), {nuevo.numero})
        self.assertEqual(numeros(prioridad="ALTA"), {mio.numero})
        self.assertEqual(numeros(localidad=str(self.resistencia.pk)), {mio.numero})
        self.assertEqual(numeros(texto="cáceres"), {ajeno.numero})
        self.assertEqual(numeros(texto=nuevo.numero), {nuevo.numero})
        self.assertEqual(numeros(texto=mio.grupo.responsable.dni), {mio.numero})
        self.assertEqual(numeros(sla="EN_TERMINO"), {mio.numero, ajeno.numero, nuevo.numero})
        self.assertEqual(numeros(sla="FUERA"), set())
        # «Míos» de otra persona son otros.
        self.client.force_login(self.otro_operador)
        self.assertEqual(numeros(operador="mios"), {ajeno.numero})

    def test_un_filtro_que_no_es_de_la_lista_se_ignora_y_no_rompe(self):
        caso = self._caso()
        for filtros in (
            {"estado": "INVENTADO"},
            {"solapa": "x"},
            {"sla": "ROJO"},
            {"localidad": "abc"},
            {"operador": "'; --"},
        ):
            with self.subTest(filtros=filtros):
                respuesta = self.client.get(URL_BANDEJA, filtros)
                self.assertEqual(respuesta.status_code, 200)
                self.assertEqual(self._numeros(respuesta), [caso.numero])

    def test_las_solapas_conservan_los_filtros_y_los_filtros_la_solapa(self):
        self._caso()
        respuesta = self.client.get(URL_BANDEJA, {"solapa": "nuevos", "prioridad": "BAJA", "page": "1"})
        chips = self._chips(respuesta)
        self.assertEqual(chips["Cerrados"]["url"], f"{URL_BANDEJA}?solapa=cerrados&prioridad=BAJA")
        self.assertContains(respuesta, '<input type="hidden" name="solapa" value="nuevos">', html=True)
        self.assertContains(respuesta, '<option value="BAJA" selected>Baja</option>', html=True)

    def test_sin_resultados_distingue_los_filtros_de_la_solapa_vacia(self):
        self._caso()
        con_filtro = self.client.get(URL_BANDEJA, {"texto": "zzz"})
        self.assertContains(con_filtro, "Ningún caso coincide con los filtros")
        self.assertContains(con_filtro, f'href="{URL_BANDEJA}?solapa=abiertos"')
        solapa_vacia = self.client.get(URL_BANDEJA, {"solapa": "cerrados"})
        self.assertContains(solapa_vacia, "No hay casos en esta solapa")
        self.assertNotContains(solapa_vacia, "Ningún caso coincide")

    def test_los_operadores_del_filtro_son_los_de_la_mesa(self):
        self._caso()
        inactivo = self._persona_de_mesa("ida", [OPERAR], "Ida", "Baja")
        User.objects.filter(pk=inactivo.pk).update(is_active=False)
        self._usuario("colado", [OPERAR], programa=self.becas)
        User.objects.create_superuser("root", "root@example.com", "x")
        self.assertEqual({usuario.username for usuario in mesa.operadores_de_la_mesa()}, {"ana", "juan", "sup"})
        nombres = [nombre for _pk, nombre in self.client.get(URL_BANDEJA).context["operadores"]]
        self.assertEqual(nombres, ["Ana López", "Juan Pérez", "Sara Ruiz"])


class SemaforoEnPantallaTests(BaseMesa):
    """RU-19: el semáforo siempre es texto + color, en la fila y en el reloj de la ficha."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.operador)

    def test_cada_fila_lleva_un_semaforo_con_texto(self):
        self._caso(apellido="Acosta")
        self.reloj.avanzar(minutes=4)
        self._caso(apellido="Benítez")
        self.reloj.avanzar(minutes=12)
        self._caso(apellido="Cáceres")
        # A los 17 minutos: el primero pasó sus 15, el segundo lleva 13 (más del 80 %) y el tercero, 1.
        self.reloj.avanzar(minutes=1)
        cerrado = self._caso_tomado(apellido="Díaz")
        servicio.cerrar_sin_alojamiento(cerrado, self.operador, CasoEmergencia.MotivoCierre.NO_REQUIERE)

        abiertos = SEMAFORO.findall(self.client.get(URL_BANDEJA).content.decode())
        cerrados = SEMAFORO.findall(self.client.get(URL_BANDEJA, {"solapa": "cerrados"}).content.decode())

        self.assertEqual(
            [(estado, _texto(cuerpo)) for estado, cuerpo in abiertos],
            [
                ("FUERA", "Fuera de SLA · 2 min"),
                ("POR_VENCER", "Por vencer · 2 min"),
                ("EN_TERMINO", "En término · 14 min"),
            ],
        )
        # Un caso cerrado no tiene tramo corriendo, y también lo dice con palabras.
        self.assertEqual([(estado, _texto(cuerpo)) for estado, cuerpo in cerrados], [("", "Sin SLA")])
        for _estado, cuerpo in abiertos + cerrados:
            self.assertIn('aria-hidden="true"', cuerpo)
            self.assertTrue(_texto(cuerpo))

    def test_un_lapso_largo_se_lee_en_horas(self):
        self._caso()
        self.reloj.avanzar(hours=3)
        semaforos = SEMAFORO.findall(self.client.get(URL_BANDEJA).content.decode())
        self.assertEqual([_texto(cuerpo) for _estado, cuerpo in semaforos], ["Fuera de SLA · 2 h"])

    def test_la_ficha_lleva_un_solo_reloj_con_el_tramo(self):
        caso = self._caso_tomado()
        self.reloj.avanzar(minutes=22)
        html = self._ficha(caso).content.decode()
        relojes = [cuerpo for _estado, cuerpo in SEMAFORO.findall(html)]
        self.assertEqual([_texto(cuerpo) for cuerpo in relojes], ["Derivar vence en 8 min"])
        self.assertEqual(html.count('role="status"'), 1)

    def test_la_ficha_de_un_caso_cerrado_no_lleva_reloj(self):
        caso = self._caso_tomado()
        servicio.cerrar_sin_alojamiento(caso, self.operador, CasoEmergencia.MotivoCierre.NO_REQUIERE)
        self.assertEqual(SEMAFORO.findall(self._ficha(caso).content.decode()), [])


# ---------------------------------------------------------------------------
# E3 · Ficha
# ---------------------------------------------------------------------------


class FichaTests(BaseMesa):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.operador)

    def test_muestra_lo_relevado_las_personas_y_la_traza(self):
        caso = self._caso_tomado(
            apellido="Benítez",
            nombre="Rosa",
            telefono="3624 555555",
            menores_f=2,
            lactantes=1,
            dependientes=1,
            mascotas=True,
            observaciones="Casa con agua hasta la ventana",
            localidad=self.resistencia.pk,
            latitud="-27.451",
            longitud="-58.986",
            precision_m=12,
        )
        respuesta = self._ficha(caso)

        self.assertTemplateUsed(respuesta, "programas/emergencia/casos/detail.html")
        self.assertEqual(respuesta.context["titulo"], f"Caso {caso.numero} · Familia Benítez")
        datos = {dato["etiqueta"]: dato["valor"] for dato in respuesta.context["datos"]}
        self.assertEqual(datos["Responsable"], "Benítez, Rosa")
        self.assertEqual(datos["Teléfono de contacto"], "3624 555555")
        self.assertEqual(datos["Fuerza que traslada"], "Bomberos")
        self.assertEqual(datos["Localidad"], "Resistencia")
        self.assertEqual(datos["Relevado por"], "agente")
        personas = respuesta.context["personas"]
        self.assertEqual((personas["total"], personas["total_femenino"], personas["total_masculino"]), (4, 3, 1))
        self.assertEqual(personas["necesidades"], ["Mascotas"])
        self.assertContains(respuesta, "Casa con agua hasta la ventana")
        self.assertContains(respuesta, "Ver en el mapa")
        self.assertContains(respuesta, "Se completa cuando el dispositivo confirma las fichas")
        self.assertEqual([evento["titulo"] for evento in respuesta.context["eventos"]], ["Tomado", "Caso creado"])
        self.assertContains(respuesta, "Lo tenés tomado vos.")

    def test_el_duenio_ve_el_panel_de_derivar_con_los_dispositivos(self):
        caso = self._caso_tomado(menores_f=3)  # 5 personas
        chico = self._dispositivo("Parroquia", camas=3)
        lleno = self._dispositivo("Escuela 12", camas=2)
        self._ocupar(lleno, 2)
        Dispositivo = type(self.club)
        self._dispositivo("Inactivo", camas=9, estado=Dispositivo.Estado.INACTIVO)

        respuesta = self._ficha(caso)

        panel = respuesta.context["panel"]
        self.assertEqual(panel["plazas"], 5)
        tarjetas = {tarjeta["nombre"]: tarjeta for tarjeta in panel["dispositivos"]}
        self.assertEqual(list(tarjetas), ["Club Sarmiento", "Parroquia", "Escuela 12"])
        self.assertEqual(
            tarjetas["Club Sarmiento"]["accion_url"],
            f"{self._url('caso_detalle', caso)}?plazas=5&derivar={self.club.pk}",
        )
        self.assertEqual((tarjetas["Parroquia"]["marca"], tarjetas["Parroquia"]["faltan"]), ("FALTAN", 2))
        self.assertIn(f"derivar={chico.pk}", tarjetas["Parroquia"]["accion_url"])
        # RN-2.5: sin plazas no se deriva, y se dice por qué.
        self.assertEqual(tarjetas["Escuela 12"]["accion_motivo"], "Sin plazas disponibles")
        self.assertNotIn("accion_url", tarjetas["Escuela 12"])
        self.assertContains(respuesta, "Faltan 2 plazas")
        self.assertContains(respuesta, "Sin plazas disponibles")
        self.assertContains(respuesta, "Derivar a Club Sarmiento")
        self.assertNotContains(respuesta, "Inactivo")
        # RU-14: nada de la operación interna del dispositivo.
        self.assertEqual(
            set(tarjetas["Parroquia"]) - {"pk", "accion_texto", "accion_url"},
            {"id", "nombre", "localidad", "libres", "reservadas", "distancia_km", "marca", "faltan"},
        )

    def test_el_panel_recalcula_con_las_plazas_y_filtra_por_nombre_y_localidad(self):
        caso = self._caso_tomado()
        self._dispositivo("Parroquia", camas=3, localidad="Fontana")

        con_mas = self._ficha(caso, plazas="6")
        self.assertEqual(con_mas.context["panel"]["plazas"], 6)
        marcas = {tarjeta["nombre"]: tarjeta["marca"] for tarjeta in con_mas.context["panel"]["dispositivos"]}
        self.assertEqual(marcas, {"Club Sarmiento": "ALCANZA", "Parroquia": "FALTAN"})
        self.assertContains(con_mas, 'name="plazas" value="6"')

        por_nombre = self._ficha(caso, q="parro")
        self.assertEqual([t["nombre"] for t in por_nombre.context["panel"]["dispositivos"]], ["Parroquia"])
        por_localidad = self._ficha(caso, localidad_dispositivo="Resistencia")
        self.assertEqual([t["nombre"] for t in por_localidad.context["panel"]["dispositivos"]], ["Club Sarmiento"])
        self.assertEqual(por_localidad.context["panel"]["localidades"], ["Fontana", "Resistencia"])
        sin_nada = self._ficha(caso, q="zzz")
        self.assertContains(sin_nada, "Ningún dispositivo para derivar")
        # Un valor inválido no rompe: vuelve al total del grupo.
        self.assertEqual(self._ficha(caso, plazas="0").context["panel"]["plazas"], 2)

    def test_el_panel_tiene_tope_y_avisa_cuantos_quedan_afuera(self):
        caso = self._caso_tomado()
        for numero in range(mesa.TOPE_DISPOSITIVOS + 4):
            self._dispositivo(f"Centro {numero:02d}", camas=2)
        respuesta = self._ficha(caso)
        panel = respuesta.context["panel"]
        self.assertEqual((panel["mostrados"], panel["total"]), (mesa.TOPE_DISPOSITIVOS, mesa.TOPE_DISPOSITIVOS + 5))
        self.assertContains(
            respuesta, f"Mostrando {mesa.TOPE_DISPOSITIVOS} de {mesa.TOPE_DISPOSITIVOS + 5} dispositivos"
        )

    def test_elegir_un_dispositivo_abre_la_confirmacion_con_post_y_csrf(self):
        caso = self._caso_tomado()
        respuesta = self._ficha(caso, derivar=self.club.pk)
        confirmacion = respuesta.context["confirmar_derivar"]
        self.assertEqual(
            (confirmacion["titulo"], confirmacion["faltan"], confirmacion["accion"]),
            ("Derivar a Club Sarmiento", False, "Sí, derivar"),
        )
        self.assertContains(respuesta, f'<form method="post" action="{self._url("caso_derivar", caso)}"')
        self.assertContains(respuesta, f'name="dispositivo" value="{self.club.pk}"')
        self.assertContains(respuesta, "modalDerivar: true")
        self.assertNotContains(respuesta, "¿Seguís?")
        # Abrir la confirmación no deriva nada.
        self.assertEqual(self._fila(caso)["estado"], Estado.EN_GESTION)
        self.assertFalse(Derivacion.objects.exists())

    def test_con_menos_plazas_que_las_pedidas_la_confirmacion_pregunta(self):
        """RN-2.5: «Vas a reservar 5 de 7 plazas. ¿Seguís?»."""
        caso = self._caso_tomado(menores_f=5)  # 7 personas
        parroquia = self._dispositivo("Parroquia", camas=5)
        respuesta = self._ficha(caso, derivar=parroquia.pk)
        confirmacion = respuesta.context["confirmar_derivar"]
        self.assertEqual((confirmacion["faltan"], confirmacion["accion"]), (True, "Sí, derivar igual"))
        self.assertContains(respuesta, "Vas a reservar 5 de 7 plazas. ¿Seguís?")
        self.assertContains(respuesta, 'name="confirmar_faltantes" value="True"')

    def test_un_dispositivo_sin_plazas_o_que_no_es_elegible_no_abre_la_confirmacion(self):
        caso = self._caso_tomado()
        lleno = self._dispositivo("Escuela 12", camas=1)
        self._ocupar(lleno, 1)
        for pedido in (lleno.pk, 999_999, "abc"):
            with self.subTest(derivar=pedido):
                respuesta = self._ficha(caso, derivar=pedido)
                self.assertIsNone(respuesta.context["confirmar_derivar"])
                self.assertContains(respuesta, "modalDerivar: false")

    def test_un_caso_derivado_muestra_la_derivacion_y_como_cancelarla(self):
        caso = self._caso_tomado()
        servicio.derivar_caso(caso, self.operador, self.club, 2)
        respuesta = self._ficha(caso)
        derivacion = respuesta.context["derivacion"]
        self.assertEqual(
            (derivacion["dispositivo"], derivacion["plazas"], derivacion["derivada_por"], derivacion["estado"]),
            ("Club Sarmiento", "2 plazas", "Ana López", "Esperando aceptación"),
        )
        self.assertEqual(derivacion["vence"], "12/11/2026 22:00")  # 12 h de vigencia
        self.assertNotIn("panel", respuesta.context)
        self.assertContains(respuesta, "Cancelar derivación")
        self.assertContains(respuesta, f'action="{self._url("caso_cancelar_derivacion", caso)}"')
        # RN-2.6: derivado no se cierra ni se suelta sin cancelar antes.
        self.assertNotContains(respuesta, "Cerrar sin alojamiento")
        self.assertNotContains(respuesta, "¿Soltar el caso?")

    def test_las_acciones_que_muta_el_estado_piden_motivo_o_confirmacion_y_nunca_confirm_nativo(self):
        """RU-22 con C4: arquetipo Modal para el motivo y ModernModal para el sí/no."""
        caso = self._caso_tomado()
        html = self._ficha(caso).content.decode()
        self.assertIn(f'data-confirm-url="{self._url("caso_soltar", caso)}"', html)
        self.assertIn('x-becas-modal="modalCerrar"', html)
        self.assertIn('<select name="motivo" class="nodo-field" required', html)
        # El shell trae lo suyo; lo que no puede traer ninguna de las dos cosas es la pantalla.
        fuente = Path(get_template("programas/emergencia/casos/detail.html").origin.name).read_text(encoding="utf-8")
        self.assertNotIn("confirm(", fuente)
        self.assertNotIn("Swal.fire", fuente)
        self.assertEqual(html.count('role="dialog"'), html.count('aria-modal="true"'))
        for etiqueta in (
            "No requiere alojamiento",
            "Sin contacto con la familia",
            "Asistido en domicilio",
            "Se alojó por su cuenta",
            "Otro",
        ):
            self.assertIn(f">{etiqueta}</option>", html)
        self.assertNotIn("Todos egresados", html)

    def test_las_marcas_del_caso_van_como_avisos(self):
        caso = self._caso_tomado()
        otro = self._caso(dni=caso.grupo.responsable.dni)
        self._ocupar(self.club, 1)
        estadia = self.club.estadias.get()
        estadia.ciudadano = caso.grupo.responsable
        estadia.clave_alojamiento = estadia.clave_para(caso.grupo.responsable)
        estadia.save()

        respuesta = self._ficha(caso)

        self.assertContains(respuesta, "Posible duplicado")
        self.assertContains(respuesta, f"Abrir el caso {otro.numero}")
        self.assertContains(respuesta, f'href="{self._url("caso_detalle", otro)}"')
        self.assertContains(respuesta, "Responsable alojado en Club Sarmiento")

    def test_un_caso_cerrado_dice_el_motivo_y_no_ofrece_nada(self):
        caso = self._caso_tomado()
        servicio.cerrar_sin_alojamiento(
            caso, self.operador, CasoEmergencia.MotivoCierre.OTRO, "Se fue a lo de la hermana"
        )
        respuesta = self._ficha(caso)
        self.assertContains(respuesta, "Caso cerrado: Otro")
        self.assertContains(respuesta, "Se fue a lo de la hermana")
        self.assertNotIn("panel", respuesta.context)
        for clave in (
            "puede_actuar",
            "puede_derivar",
            "puede_cerrar",
            "puede_soltar",
            "puede_tomar",
            "puede_reasignar",
        ):
            self.assertFalse(respuesta.context[clave], clave)
        self.assertNotContains(respuesta, "Registrar un contacto")
        self.assertNotContains(respuesta, "Más acciones")


# ---------------------------------------------------------------------------
# RU-12 y RU-13: dueño, no dueño y supervisor
# ---------------------------------------------------------------------------


class QuienNoLoTieneTomadoTests(BaseMesa):
    def setUp(self):
        super().setUp()
        self.reloj.avanzar(minutes=0)
        self.caso = self._caso_tomado(por=self.operador)
        self.reloj.avanzar(minutes=12)
        self.client.force_login(self.otro_operador)

    def test_lo_ve_en_solo_lectura_con_quien_lo_tiene_y_desde_cuando(self):
        respuesta = self._ficha(self.caso)
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.context["solo_lectura"])
        self.assertContains(respuesta, "Tomado por Ana López hace 12 min.")
        self.assertNotIn("panel", respuesta.context)
        for form in ("form_contacto", "form_cierre", "form_prioridad", "form_reasignar", "form_cancelar"):
            self.assertNotIn(form, respuesta.context)
        html = respuesta.content.decode()
        for accion in ("caso_contacto", "caso_derivar", "caso_cerrar", "caso_soltar", "caso_prioridad", "caso_tomar"):
            self.assertNotIn(self._url(accion, self.caso), html, accion)
        self.assertNotIn("Más acciones", html)
        self.assertNotIn("Derivar a Club Sarmiento", html)

    def test_un_post_directo_recibe_403_y_nada_cambia(self):
        antes = self._fila(self.caso)
        cuerpos = {
            **ACCIONES,
            "caso_derivar": {"dispositivo": self.club.pk, "plazas": "2"},
        }
        for accion in ("caso_derivar", "caso_cerrar", "caso_contacto", "caso_prioridad", "caso_soltar"):
            with self.subTest(accion=accion):
                self.assertEqual(self._post(accion, self.caso, cuerpos[accion]).status_code, 403)
        servicio.derivar_caso(self.caso, self.operador, self.club, 2)
        self.assertEqual(
            self._post("caso_cancelar_derivacion", self.caso, cuerpos["caso_cancelar_derivacion"]).status_code, 403
        )

        self.assertEqual(Derivacion.objects.get().estado, Derivacion.Estado.PENDIENTE)
        self.assertFalse(ContactoCaso.objects.exists())
        despues = self._fila(self.caso)
        self.assertEqual(despues["estado"], Estado.DERIVADO)
        for campo in ("prioridad", "tomado_por_id", "cerrado_en", "motivo_cierre"):
            self.assertEqual(despues[campo], antes[campo], campo)
        self.assertEqual([t.accion for t in self._trazas(self.caso)], [Accion.CREADO, Accion.TOMADO, Accion.DERIVADO])

    def test_tomar_un_caso_que_tomo_otro_avisa_quien_lo_tiene(self):
        """HU-2.1: «Tomado por Ana López» y nada cambia."""
        respuesta = self._post("caso_tomar", self.caso)
        self.assertRedirects(respuesta, self._url("caso_detalle", self.caso), fetch_redirect_response=False)
        self.assertEqual(
            self._avisos(respuesta), [f"El caso {self.caso.numero} ya lo tomó Ana López. Recargá la bandeja."]
        )
        self.assertEqual(self._fila(self.caso)["tomado_por_id"], self.operador.pk)

    def test_un_caso_nuevo_ofrece_tomar_y_nada_mas(self):
        nuevo = self._caso()
        respuesta = self._ficha(nuevo)
        self.assertTrue(respuesta.context["puede_tomar"])
        self.assertFalse(respuesta.context["solo_lectura"])
        self.assertContains(respuesta, f'action="{self._url("caso_tomar", nuevo)}"')
        self.assertContains(respuesta, "Nadie tomó este caso todavía")
        self.assertNotIn("panel", respuesta.context)
        self.assertNotContains(respuesta, "Registrar un contacto")

    def test_tomar_lo_deja_a_su_nombre_y_abre_la_ficha(self):
        nuevo = self._caso()
        respuesta = self._post("caso_tomar", nuevo)
        self.assertRedirects(respuesta, self._url("caso_detalle", nuevo), fetch_redirect_response=False)
        fila = self._fila(nuevo)
        self.assertEqual((fila["estado"], fila["tomado_por_id"]), (Estado.EN_GESTION, self.otro_operador.pk))
        self.assertIn("panel", self._ficha(nuevo).context)


class SupervisorTests(BaseMesa):
    """RU-13: actúa sobre cualquier caso sin tomarlo, y la traza lo dice."""

    def setUp(self):
        super().setUp()
        self.caso = self._caso_tomado(por=self.operador)
        self.client.force_login(self.supervisor)

    def test_ve_el_panel_y_las_acciones_de_un_caso_ajeno(self):
        respuesta = self._ficha(self.caso)
        self.assertFalse(respuesta.context["solo_lectura"])
        self.assertIn("panel", respuesta.context)
        for form in ("form_contacto", "form_cierre", "form_prioridad", "form_reasignar"):
            self.assertIn(form, respuesta.context)
        self.assertContains(respuesta, "Tomado por Ana López")
        self.assertContains(respuesta, "Reasignar")

    def test_actua_sin_tomarlo_y_queda_por_supervisor(self):
        self._post(
            "caso_contacto",
            self.caso,
            {"canal": "WHATSAPP", "resultado": "NO_ATENDIO", "observacion": "Sin tilde azul"},
        )
        self._post("caso_prioridad", self.caso, {"prioridad": "ALTA"})
        self._post("caso_derivar", self.caso, {"dispositivo": self.club.pk, "plazas": "2"})

        fila = self._fila(self.caso)
        self.assertEqual(
            (fila["estado"], fila["prioridad"], fila["tomado_por_id"]), (Estado.DERIVADO, "ALTA", self.operador.pk)
        )
        del_supervisor = [t for t in self._trazas(self.caso) if t.usuario_id == self.supervisor.pk]
        self.assertEqual([t.accion for t in del_supervisor], [Accion.CONTACTO, Accion.PRIORIDAD, Accion.DERIVADO])
        self.assertTrue(all(t.por_supervisor for t in del_supervisor))
        self.assertContains(self._ficha(self.caso), "Por supervisor")

    def test_reasigna_y_el_reloj_no_se_reinicia(self):
        """HU-2.6 y RN-2.9."""
        tomado_en = self._fila(self.caso)["tomado_en"]
        self.reloj.avanzar(minutes=20)
        respuesta = self._post("caso_reasignar", self.caso, {"operador": self.otro_operador.pk})
        self.assertRedirects(respuesta, self._url("caso_detalle", self.caso), fetch_redirect_response=False)
        self.assertEqual(self._avisos(respuesta), [f"El caso {self.caso.numero} pasó a Juan Pérez."])
        fila = self._fila(self.caso)
        self.assertEqual((fila["tomado_por_id"], fila["tomado_en"]), (self.otro_operador.pk, tomado_en))
        self.assertEqual(self._trazas(self.caso)[-1].detalle, "Reasignado de Ana López a Juan Pérez · por supervisor")

    def test_reasignar_a_quien_no_es_de_la_mesa_no_cambia_nada(self):
        for operador in (self.agente.pk, 999_999, ""):
            with self.subTest(operador=operador):
                respuesta = self._post("caso_reasignar", self.caso, {"operador": operador})
                self.assertRedirects(respuesta, self._url("caso_detalle", self.caso), fetch_redirect_response=False)
                self.assertTrue(self._avisos(respuesta))
        self.assertEqual(self._fila(self.caso)["tomado_por_id"], self.operador.pk)

    def test_la_lista_para_reasignar_son_los_de_la_mesa(self):
        opciones = self._ficha(self.caso).context["form_reasignar"].fields["operador"].queryset
        self.assertEqual({usuario.username for usuario in opciones}, {"ana", "juan", "sup"})

    def test_suelta_un_caso_ajeno_y_vuelve_a_la_bandeja(self):
        respuesta = self._post("caso_soltar", self.caso)
        self.assertRedirects(respuesta, URL_BANDEJA, fetch_redirect_response=False)
        fila = self._fila(self.caso)
        self.assertEqual((fila["estado"], fila["tomado_por_id"]), (Estado.NUEVO, None))


# ---------------------------------------------------------------------------
# De punta a punta, y la segunda pestaña
# ---------------------------------------------------------------------------


class FlujoDePuntaAPuntaTests(BaseMesa):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.operador)

    def _cargar(self, **cambios):
        self.client.post(URL_NUEVO, self._formulario1(**cambios))
        return CasoEmergencia.objects.latest("id")

    def test_nuevo_caso_contacto_derivar_cancelar_y_cerrar(self):
        caso = self._cargar(apellido="Benítez")

        # Aparece en la bandeja, en gestión y a nombre de quien lo cargó.
        bandeja = self.client.get(URL_BANDEJA, {"operador": "mios"})
        fila = bandeja.context["filas"][0]
        self.assertEqual(
            (fila["caso"].pk, fila["estado_texto"], fila["tomado_por"]), (caso.pk, "En gestión", "Ana López")
        )

        # Contacto.
        respuesta = self._post(
            "caso_contacto", caso, {"canal": "LLAMADA", "resultado": "ATENDIO", "observacion": "Esperan en la esquina"}
        )
        self.assertRedirects(respuesta, self._url("caso_detalle", caso), fetch_redirect_response=False)
        self.assertEqual(self._avisos(respuesta), ["Contacto registrado."])
        ficha = self._ficha(caso)
        self.assertEqual([c["titulo"] for c in ficha.context["contactos"]], ["Llamada · Atendió"])
        self.assertContains(ficha, "Esperan en la esquina")

        # Derivar: alcanza, no hay nada que confirmar.
        self.reloj.avanzar(minutes=5)
        respuesta = self._post(
            "caso_derivar", caso, {"dispositivo": self.club.pk, "plazas": "2", "confirmar_faltantes": "False"}
        )
        self.assertRedirects(respuesta, self._url("caso_detalle", caso), fetch_redirect_response=False)
        self.assertIn("derivado a Club Sarmiento", self._avisos(respuesta)[0])
        derivacion = Derivacion.objects.get()
        self.assertEqual(
            (derivacion.estado, derivacion.plazas_pedidas, derivacion.dispositivo_id, derivacion.derivada_por_id),
            (Derivacion.Estado.PENDIENTE, 2, self.club.pk, self.operador.pk),
        )
        self.assertEqual(self._fila(caso)["estado"], Estado.DERIVADO)
        self.assertEqual(self.client.get(URL_BANDEJA, {"solapa": "derivados"}).context["filas"][0]["caso"].pk, caso.pk)

        # Cancelar: sin motivo no; con motivo, vuelve a gestión con el mismo dueño (HU-2.3).
        respuesta = self._post("caso_cancelar_derivacion", caso, {"motivo": " "})
        self.assertEqual(self._avisos(respuesta), ["Indicá por qué se cancela la derivación."])
        self.assertEqual(Derivacion.objects.get().estado, Derivacion.Estado.PENDIENTE)
        respuesta = self._post("caso_cancelar_derivacion", caso, {"motivo": "La familia se fue a otro lado"})
        self.assertIn("cancelada", self._avisos(respuesta)[0])
        derivacion.refresh_from_db()
        self.assertEqual(
            (derivacion.estado, derivacion.motivo), (Derivacion.Estado.CANCELADA, "La familia se fue a otro lado")
        )
        fila = self._fila(caso)
        self.assertEqual((fila["estado"], fila["tomado_por_id"]), (Estado.EN_GESTION, self.operador.pk))

        # Cerrar: el motivo es del select y obligatorio (RN-2.13).
        rechazos = (
            ({"motivo": ""}, "Elegí el motivo del cierre."),
            ({"motivo": "TODOS_EGRESADOS"}, "Elegí el motivo del cierre."),
            ({"motivo": "OTRO", "observacion": ""}, "Con el motivo «Otro», contá qué pasó."),
        )
        for cuerpo, aviso in rechazos:
            respuesta = self._post("caso_cerrar", caso, cuerpo)
            self.assertEqual(self._avisos(respuesta), [aviso])
            self.assertEqual(self._fila(caso)["estado"], Estado.EN_GESTION, cuerpo)
        respuesta = self._post("caso_cerrar", caso, {"motivo": "POR_SU_CUENTA", "observacion": ""})
        self.assertEqual(self._avisos(respuesta), [f"Caso {caso.numero} cerrado sin alojamiento."])
        fila = self._fila(caso)
        self.assertEqual((fila["estado"], fila["motivo_cierre"]), (Estado.CERRADO, "POR_SU_CUENTA"))
        self.assertIsNotNone(fila["cerrado_en"])

        self.assertEqual(
            [t.accion for t in self._trazas(caso)],
            [Accion.CREADO, Accion.CONTACTO, Accion.DERIVADO, Accion.DERIVACION_CANCELADA, Accion.CERRADO],
        )
        self.assertEqual(self.client.get(URL_BANDEJA).context["filas"], [])
        self.assertEqual(self.client.get(URL_BANDEJA, {"solapa": "cerrados"}).context["filas"][0]["caso"].pk, caso.pk)

    def test_derivar_con_faltantes_pide_confirmar_y_recien_ahi_deriva(self):
        """RN-2.5 por HTTP: sin el «sí», vuelve a la confirmación con la pregunta."""
        caso = self._cargar(menores_f="5")  # 7 personas
        parroquia = self._dispositivo("Parroquia", camas=5)

        sin_confirmar = self._post("caso_derivar", caso, {"dispositivo": parroquia.pk, "plazas": "7"})

        self.assertRedirects(
            sin_confirmar,
            f"{self._url('caso_detalle', caso)}?plazas=7&derivar={parroquia.pk}",
            fetch_redirect_response=False,
        )
        self.assertIn("5 de las 7 plazas", self._avisos(sin_confirmar)[0])
        self.assertFalse(Derivacion.objects.exists())
        self.assertContains(self.client.get(sin_confirmar.url), "Vas a reservar 5 de 7 plazas. ¿Seguís?")

        confirmado = self._post(
            "caso_derivar", caso, {"dispositivo": parroquia.pk, "plazas": "7", "confirmar_faltantes": "True"}
        )

        self.assertRedirects(confirmado, self._url("caso_detalle", caso), fetch_redirect_response=False)
        self.assertEqual(Derivacion.objects.get().plazas_pedidas, 7)
        self.assertIn("faltan 2", self._trazas(caso)[-1].detalle)

    def test_derivar_a_un_dispositivo_sin_plazas_o_con_datos_invalidos_no_deriva(self):
        caso = self._cargar()
        lleno = self._dispositivo("Escuela 12", camas=1)
        self._ocupar(lleno, 1)
        cuerpos = (
            {"dispositivo": lleno.pk, "plazas": "2", "confirmar_faltantes": "True"},
            {"dispositivo": self.club.pk, "plazas": "0"},
            {"dispositivo": self.club.pk, "plazas": ""},
            {"dispositivo": "999999", "plazas": "2"},
            {"plazas": "2"},
        )
        for cuerpo in cuerpos:
            with self.subTest(cuerpo=cuerpo):
                respuesta = self._post("caso_derivar", caso, cuerpo)
                self.assertRedirects(respuesta, self._url("caso_detalle", caso), fetch_redirect_response=False)
                aviso = self._avisos(respuesta)
                self.assertEqual(len(aviso), 1)
                # RU-20: dice qué pasó y qué hacer, no «Este campo es requerido».
                self.assertRegex(aviso[0], r"Elegí otro|Pedí al menos una plaza|Recargá la ficha")
        self.assertFalse(Derivacion.objects.exists())
        self.assertEqual(self._fila(caso)["estado"], Estado.EN_GESTION)

    def test_soltar_lo_devuelve_a_la_bandeja_como_nuevo(self):
        caso = self._cargar()
        respuesta = self._post("caso_soltar", caso)
        self.assertRedirects(respuesta, URL_BANDEJA, fetch_redirect_response=False)
        fila = self._fila(caso)
        self.assertEqual((fila["estado"], fila["tomado_por_id"]), (Estado.NUEVO, None))
        self.assertIsNotNone(fila["tomado_en"])  # RN-2.9

    def test_cambiar_la_prioridad_deja_el_valor_anterior_y_el_nuevo(self):
        caso = self._cargar()
        respuesta = self._post("caso_prioridad", caso, {"prioridad": "ALTA"})
        self.assertEqual(self._avisos(respuesta), [f"Prioridad del caso {caso.numero}: alta."])
        self.assertEqual(self._trazas(caso)[-1].detalle, "Prioridad: Baja → Alta")
        self.assertTrue(self._avisos(self._post("caso_prioridad", caso, {"prioridad": "URGENTE"})))
        self.assertEqual(self._fila(caso)["prioridad"], "ALTA")


class SegundaPestaniaTests(BaseMesa):
    """02 §9: la pantalla quedó vieja. El servicio lo dice, la vista lo muestra y nunca es un 500."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.operador)
        self.caso = self._caso_tomado()
        self.parroquia = self._dispositivo("Parroquia", camas=5)

    def test_derivar_un_caso_ya_derivado_avisa_adonde_y_pide_recargar(self):
        cuerpo = {"dispositivo": self.club.pk, "plazas": "2"}
        self.assertEqual(self._post("caso_derivar", self.caso, cuerpo).status_code, 302)
        self.reloj.avanzar(minutes=3)

        segunda = self._post("caso_derivar", self.caso, {"dispositivo": self.parroquia.pk, "plazas": "2"})

        self.assertRedirects(segunda, self._url("caso_detalle", self.caso), fetch_redirect_response=False)
        self.assertEqual(
            self._avisos(segunda), ["El caso ya fue derivado a Club Sarmiento a las 10:00. Recargá la ficha."]
        )
        self.assertEqual(Derivacion.objects.count(), 1)
        self.assertEqual(Derivacion.objects.get().dispositivo_id, self.club.pk)
        # Y la ficha a la que vuelve es la de ahora.
        self.assertEqual(self.client.get(segunda.url).context["derivacion"]["dispositivo"], "Club Sarmiento")

    def test_cada_accion_sobre_una_pantalla_vieja_avisa_y_no_escribe(self):
        servicio.cerrar_sin_alojamiento(self.caso, self.operador, CasoEmergencia.MotivoCierre.NO_REQUIERE)
        trazas = len(self._trazas(self.caso))
        cuerpos = {**ACCIONES, "caso_derivar": {"dispositivo": self.club.pk, "plazas": "2"}}
        for accion in (
            "caso_tomar",
            "caso_soltar",
            "caso_prioridad",
            "caso_contacto",
            "caso_derivar",
            "caso_cancelar_derivacion",
            "caso_cerrar",
        ):
            with self.subTest(accion=accion):
                respuesta = self._post(accion, self.caso, cuerpos[accion])
                self.assertRedirects(respuesta, self._url("caso_detalle", self.caso), fetch_redirect_response=False)
                aviso = self._avisos(respuesta)
                self.assertEqual(len(aviso), 1)
                self.assertRegex(aviso[0], r"cerrado|Recargá")
        self.assertEqual(len(self._trazas(self.caso)), trazas)
        self.assertFalse(Derivacion.objects.exists())
        self.assertFalse(ContactoCaso.objects.exists())

    def test_cancelar_una_derivacion_que_ya_no_esta_pendiente_pide_recargar(self):
        servicio.derivar_caso(self.caso, self.operador, self.club, 2)
        derivacion = Derivacion.objects.get()
        servicio.cancelar_derivacion(derivacion, self.operador, "Primera pestaña")

        respuesta = self._post("caso_cancelar_derivacion", self.caso, {"motivo": "Segunda pestaña"})

        self.assertEqual(
            self._avisos(respuesta),
            [f"El caso {self.caso.numero} ya no tiene una derivación pendiente. Recargá la ficha."],
        )
        derivacion.refresh_from_db()
        self.assertEqual(derivacion.motivo, "Primera pestaña")

    def test_el_aviso_llega_a_la_pantalla_como_mensaje_del_shell(self):
        servicio.derivar_caso(self.caso, self.operador, self.club, 2)
        respuesta = self.client.post(
            self._url("caso_derivar", self.caso), {"dispositivo": self.parroquia.pk, "plazas": "2"}, follow=True
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'class="dj-message"')
        self.assertContains(respuesta, "Recargá la ficha.")


# ---------------------------------------------------------------------------
# Presupuestos de consultas
# ---------------------------------------------------------------------------


@tag("performance")
class PresupuestoDeConsultasTests(BaseMesa):
    """Las dos pantallas cuestan lo mismo con 5 filas que con 500: sin N+1.

    Los números son los medidos. Si suben, hay una consulta nueva por página (o por fila):
    antes de mover el techo, mirar cuál es.
    """

    #: E2: la sesión, el usuario, sus roles, su perfil y sus capacidades (5, las del shell), el
    #: SLA (1), el semáforo de los abiertos una sola vez —lo comparten el orden de la bandeja y
    #: el conteo de «Fuera de SLA»— (1), el conteo y la página del paginador (2), el agregado
    #: de solapas (1), los duplicados (3), los responsables alojados (1) y los operadores y las
    #: localidades del filtro (2).
    CONSULTAS_E2 = 16
    #: E3: las cinco del shell, el caso (1), el SLA (1), los duplicados (3), fotos, contactos y
    #: traza (3), el responsable alojado (1) y el panel de derivar (4).
    CONSULTAS_E3 = 18

    def _casos_en_lote(self, cuantos):
        """``cuantos`` casos abiertos sin pasar por el servicio: acá se mide leer, no crear."""

        personas = Ciudadano.objects.bulk_create(
            [Ciudadano(dni=str(41_000_000 + n), nombre="Persona", apellido=f"Apellido{n:03d}") for n in range(cuantos)]
        )
        grupos = GrupoFamiliar.objects.bulk_create(
            [
                GrupoFamiliar(
                    responsable=persona, traslado=GrupoFamiliar.Traslado.BOMBEROS, adultos_f=2, total_declarado=2
                )
                for persona in personas
            ]
        )
        estados = (Estado.NUEVO, Estado.EN_GESTION, Estado.DERIVADO)
        casos = []
        for n, grupo in enumerate(grupos):
            estado = estados[n % 3]
            tomado = estado != Estado.NUEVO
            casos.append(
                CasoEmergencia(
                    numero=CasoEmergencia.formatear_numero(2026, 900_000 + n),
                    grupo=grupo,
                    origen=Origen.TERRITORIO,
                    estado=estado,
                    prioridad=(Prioridad.ALTA, Prioridad.MEDIA, Prioridad.BAJA)[n % 3],
                    localidad=self.resistencia,
                    direccion=f"Calle {n}",
                    relevado_por=self.agente,
                    relevado_en=T0 - timedelta(minutes=n),
                    tomado_por=self.operador if tomado else None,
                    tomado_en=T0 if tomado else None,
                    derivado_en=T0 if estado == Estado.DERIVADO else None,
                )
            )
        return CasoEmergencia.objects.bulk_create(casos)

    def test_e2_con_500_casos_abiertos(self):
        self._casos_en_lote(500)
        self.reloj.avanzar(minutes=40)  # una parte queda fuera de SLA: el orden usa la lista de ids
        self.client.force_login(self.operador)
        self.client.get(URL_BANDEJA)  # calienta lo que es del proceso (content types, programa)

        with self.assertNumQueries(self.CONSULTAS_E2):
            respuesta = self.client.get(URL_BANDEJA)

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(respuesta.context["filas"]), CASOS_POR_PAGINA)
        self.assertEqual(respuesta.context["page_obj"].paginator.count, 500)
        self.assertEqual(respuesta.context["page_obj"].paginator.num_pages, 10)
        with self.assertNumQueries(self.CONSULTAS_E2):
            ultima = self.client.get(URL_BANDEJA, {"page": "10", "solapa": "fuera_sla"})
        self.assertEqual(ultima.status_code, 200)

    def test_e2_cuesta_lo_mismo_con_pocos_casos(self):
        self._casos_en_lote(6)
        self.client.force_login(self.operador)
        self.client.get(URL_BANDEJA)
        with self.assertNumQueries(self.CONSULTAS_E2):
            self.assertEqual(len(self.client.get(URL_BANDEJA).context["filas"]), 6)

    def test_e3_con_50_dispositivos(self):
        for numero in range(50):
            dispositivo = self._dispositivo(f"Centro {numero:02d}", camas=4, latitud="-27.45", longitud="-58.98")
            if numero % 2:
                self._ocupar(dispositivo, 2)
        caso = self._caso_tomado(latitud="-27.451", longitud="-58.986", precision_m=10)
        servicio.registrar_contacto(caso, self.operador, canal="LLAMADA", resultado="ATENDIO")
        self.client.force_login(self.operador)
        self._ficha(caso)

        with self.assertNumQueries(self.CONSULTAS_E3):
            respuesta = self._ficha(caso)

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context["panel"]["total"], 51)
        self.assertEqual(len(respuesta.context["panel"]["dispositivos"]), mesa.TOPE_DISPOSITIVOS)
        # Con la confirmación abierta cuesta lo mismo: sale de lo que el panel ya leyó.
        with self.assertNumQueries(self.CONSULTAS_E3):
            self.assertIsNotNone(self._ficha(caso, derivar=self.club.pk).context["confirmar_derivar"])

    def test_e3_cuesta_lo_mismo_con_un_dispositivo(self):
        caso = self._caso_tomado()
        self.client.force_login(self.operador)
        self._ficha(caso)
        with self.assertNumQueries(self.CONSULTAS_E3):
            self._ficha(caso)
