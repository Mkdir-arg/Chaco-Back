"""Módulo Emergencia, PR 9: las entregas de kits en el backoffice — E4, E5 y la recepción en el dispositivo.

Las reglas de la entrega ya están probadas contra el servicio en ``test_emergencia_kits``.
Acá se prueba **la puerta HTTP**: que cada vista exija lo que tiene que exigir, que traduzca
lo que contesta el servicio sin escribir nada por su cuenta, y que el flujo ande de punta a
punta.

* **Acceso de la mesa** — sin login, al login; sin operar ni supervisar, 403. El barrido de
  URLs ``emergencia:*`` de ``test_emergencia_base`` cubre las rutas nuevas sin listarlas.
* **Acceso de la guardia** (RN-4.8, plan §2 C2) — sin ``recibir_kit`` en ningún dispositivo,
  403; con la capacidad en **otro** dispositivo, **404**, y nada cambia. Es la mutación de
  04 §11 por HTTP: con el recorte por alcance de ``RecepcionKitsMixin`` reemplazado por
  «tiene la capacidad en algún lado», ``test_la_guardia_de_otro_dispositivo_recibe_404``
  falla con «200 != 404» en las dos pantallas del Club (la guardia de la Escuela ve el
  formulario de una entrega ajena). El POST lo sigue frenando el servicio, que tiene su
  propia guarda y su propia mutación en ``test_emergencia_kits``.
* **Punta a punta** — crear en tres pasos → en camino → recibir con diferencia desde el
  dispositivo → E5 muestra la diferencia → reponer.
* **El asistente no usa la sesión** — lo que se crea es lo que mostró el paso 3.
* **Presupuesto** — E4 con 200 entregas (``--tag performance``).
"""

import re
import shutil
import tempfile
from datetime import timedelta

from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings, tag
from django.urls import reverse

from programas.models import EntradaBitacora, EntregaKit, LineaEntrega, MiembroEquipoDispositivo, TipoKit, TrazaEntrega
from programas.services import kits as servicio
from programas.tests.test_emergencia_base import OPERAR, SUPERVISAR, urls_de_emergencia
from programas.tests.test_emergencia_casos import JPEG, T0
from programas.tests.test_emergencia_kits import ADMITIR, PNG, RECIBIR_KIT, BaseKits
from programas.views.emergencia_kits import ENTREGAS_POR_PAGINA

Estado = EntregaKit.Estado

URL_ENTREGAS = "/emergencia/entregas/"
URL_NUEVA = "/emergencia/entregas/nueva/"

#: Las acciones POST de la mesa sobre una entrega y un cuerpo que su formulario acepta.
ACCIONES = {
    "entrega_en_camino": {"transporte": "", "hora": ""},
    "entrega_cancelar": {"motivo": "Se suspendió el envío"},
    "entrega_observar": {"texto": "Se reclamó al proveedor"},
}


def _texto(html):
    return " ".join(re.sub(r"<[^>]+>", " ", html).split())


class BaseVistasKits(BaseKits):
    def _url(self, nombre, *args):
        return reverse(f"emergencia:{nombre}", args=args)

    def _avisos(self, respuesta):
        """Los avisos que dejó **este** pedido."""
        dejados = [str(mensaje) for mensaje in get_messages(respuesta.wsgi_request)._queued_messages]
        list(get_messages(respuesta.wsgi_request))
        return dejados

    def _cantidades(self, **por_item):
        """El cuerpo del paso 2: ``cantidad_<id>`` de cada ítem del catálogo activo."""
        datos = {f"cantidad_{item.pk}": "" for item in TipoKit.objects.filter(activo=True)}
        datos.update({f"cantidad_{item.pk}": str(cantidad) for item, cantidad in por_item.values()})
        return datos

    def _foto(self, entrega):
        fila = EntregaKit.objects.filter(pk=entrega.pk).values().get()
        lineas = list(LineaEntrega.objects.filter(entrega=entrega).order_by("id").values())
        return fila, lineas, TrazaEntrega.objects.filter(entrega=entrega).count()

    def _remito_http(self, nombre="remito.jpg", contenido=JPEG, tipo="image/jpeg"):
        return SimpleUploadedFile(nombre, contenido, content_type=tipo)


# ---------------------------------------------------------------------------
# Acceso de la mesa
# ---------------------------------------------------------------------------


class AccesoDeLaMesaTests(BaseVistasKits):
    def setUp(self):
        super().setUp()
        self.entrega = self._entrega()
        self.gets = [
            URL_ENTREGAS,
            URL_NUEVA,
            self._url("entrega_nueva_items", self.club.pk),
            self._url("entrega_detalle", self.entrega.pk),
        ]
        self.posts = [self._url(nombre, self.entrega.pk) for nombre in ACCIONES] + [
            self._url("entrega_nueva_confirmar", self.club.pk)
        ]

    def test_las_urls_son_las_del_namespace_emergencia(self):
        self.assertEqual(reverse("emergencia:entregas"), URL_ENTREGAS)
        self.assertEqual(reverse("emergencia:entrega_nueva"), URL_NUEVA)

    def test_el_barrido_del_modulo_cubre_las_rutas_de_kits(self):
        """El barrido de ``test_emergencia_base`` (rol de Becas, ciudadano) las prueba sin listarlas."""
        urls = urls_de_emergencia()
        self.assertIn(URL_ENTREGAS, urls)
        self.assertIn(URL_NUEVA, urls)
        for fragmento in ("/en-camino/", "/cancelar/", "/observar/", "/confirmar/", "/kits/", "/recibir/"):
            with self.subTest(ruta=fragmento):
                self.assertTrue([url for url in urls if url.endswith(fragmento)], fragmento)

    def test_sin_login_todo_redirige_al_login(self):
        for url in self.gets + self.posts:
            with self.subTest(url=url):
                respuesta = self.client.get(url)
                self.assertEqual(respuesta.status_code, 302)
                self.assertEqual(respuesta.url, f"{reverse('users:login')}?next={url}")
                self.assertEqual(self.client.post(url, {}).status_code, 302)

    def test_sin_operar_ni_supervisar_todo_rechaza(self):
        colado = self._usuario("colado", [OPERAR, SUPERVISAR], programa=self.becas)
        antes = self._foto(self.entrega)
        for usuario in (self._usuario("sin_rol"), self.agente, self.guardia, colado):
            self.client.force_login(usuario)
            for url in self.gets + self.posts:
                with self.subTest(usuario=usuario.username, url=url):
                    self.assertEqual(self.client.get(url).status_code, 403)
                    self.assertEqual(self.client.post(url, ACCIONES["entrega_cancelar"]).status_code, 403)
        self.assertEqual(self._foto(self.entrega), antes)
        self.assertEqual(EntregaKit.objects.count(), 1)

    def test_quien_opera_y_quien_solo_supervisa_abren_las_pantallas(self):
        for usuario in (self.operador, self.supervisor):
            self.client.force_login(usuario)
            for url in self.gets:
                with self.subTest(usuario=usuario.username, url=url):
                    self.assertEqual(self.client.get(url).status_code, 200)

    def test_las_acciones_no_se_abren_por_get(self):
        self.client.force_login(self.operador)
        for nombre in ACCIONES:
            with self.subTest(accion=nombre):
                self.assertEqual(self.client.get(self._url(nombre, self.entrega.pk)).status_code, 405)

    def test_una_entrega_que_no_existe_es_un_404(self):
        self.client.force_login(self.operador)
        self.assertEqual(self.client.get(self._url("entrega_detalle", 999_999)).status_code, 404)
        self.assertEqual(
            self.client.post(self._url("entrega_cancelar", 999_999), ACCIONES["entrega_cancelar"]).status_code, 404
        )

    def test_un_destino_que_no_esta_activo_es_un_404_en_el_asistente(self):
        from programas.models import Dispositivo

        cerrado = self._dispositivo("Parroquia cerrada", estado=Dispositivo.Estado.CERRADO)
        self.client.force_login(self.operador)

        self.assertEqual(self.client.get(self._url("entrega_nueva_items", cerrado.pk)).status_code, 404)
        self.assertEqual(self.client.post(self._url("entrega_nueva_confirmar", cerrado.pk), {}).status_code, 404)


class SidebarDeKitsTests(BaseVistasKits):
    ENLACE = 'href="/emergencia/entregas/"'

    def _inicio(self, usuario):
        self.client.force_login(usuario)
        return self.client.get(reverse("core:inicio"))

    def test_quien_opera_o_supervisa_ve_la_entrada(self):
        for usuario in (self.operador, self.supervisor):
            with self.subTest(usuario=usuario.username):
                self.assertContains(self._inicio(usuario), self.ENLACE)

    def test_la_guardia_y_un_rol_de_becas_no_la_ven(self):
        becario = self._usuario("becario", ["becas.segmento.ver"], programa=self.becas)
        for usuario in (self.guardia, becario):
            with self.subTest(usuario=usuario.username):
                respuesta = self._inicio(usuario)
                self.assertNotContains(respuesta, self.ENLACE, status_code=respuesta.status_code)

    def test_la_entrada_marca_la_pantalla_en_la_que_se_esta(self):
        self.client.force_login(self.supervisor)
        marca = re.compile(r'href="(/emergencia/[a-z]+/)"\s+class="flex items-center gap-2[^>]*aria-current="page"')

        entregas = self.client.get(URL_ENTREGAS).content.decode()
        bandeja = self.client.get(reverse("emergencia:bandeja")).content.decode()

        self.assertEqual(set(marca.findall(entregas)), {"/emergencia/entregas/"})
        self.assertEqual(set(marca.findall(bandeja)), {"/emergencia/casos/"})

    def test_la_entrada_no_suma_consultas_al_shell(self):
        """Misma condición que la bandeja: el inicio cuesta lo mismo con la entrada que sin ella."""
        self.client.force_login(self.operador)
        self.client.get(reverse("core:inicio"))
        with self.assertNumQueries(self._consultas_del_inicio()):
            self.client.get(reverse("core:inicio"))

    def _consultas_del_inicio(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as consultas:
            self.client.get(reverse("core:inicio"))
        # Ninguna consulta del shell toca las tablas de kits.
        self.assertEqual([c["sql"] for c in consultas if "entregakit" in c["sql"].lower()], [])
        return len(consultas)


# ---------------------------------------------------------------------------
# E4 · Listado
# ---------------------------------------------------------------------------


class ListadoDeEntregasTests(BaseVistasKits):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.operador)

    def test_el_listado_muestra_las_abiertas_con_su_resumen(self):
        preparada = self._entrega()
        self._recibir(self._en_camino(dispositivo=self.escuela), usuario=self.guardia_escuela)

        respuesta = self.client.get(URL_ENTREGAS)

        self.assertTemplateUsed(respuesta, "programas/emergencia/kits/list.html")
        self.assertEqual(respuesta.context["solapa"], "abiertas")
        self.assertEqual([fila["entrega"] for fila in respuesta.context["filas"]], [preparada])
        texto = _texto(respuesta.content.decode())
        self.assertIn(preparada.numero, texto)
        self.assertIn("10 Colchón, 3 Kit alimentario", texto)
        self.assertIn("Club Sarmiento", texto)
        self.assertIn("Preparada", texto)
        self.assertIn("Ana López · 12/11/2026 10:00", texto)

    def test_las_solapas_llevan_el_conteo_y_conservan_los_filtros(self):
        self._entrega()
        self._recibida_con_faltante()

        respuesta = self.client.get(URL_ENTREGAS, {"solapa": "con_diferencias", "dispositivo": self.club.pk})

        chips = {chip["texto"]: chip for chip in respuesta.context["solapas"]}
        self.assertEqual(
            {texto: chip["n"] for texto, chip in chips.items()},
            {"Abiertas": 1, "Con diferencias": 1, "Recibidas": 0, "Canceladas": 0},
        )
        self.assertTrue(chips["Con diferencias"]["activo"])
        self.assertEqual(chips["Abiertas"]["url"], f"{URL_ENTREGAS}?solapa=abiertas&dispositivo={self.club.pk}")
        self.assertContains(respuesta, "Recibida con diferencias")

    def test_los_filtros_recortan_el_listado(self):
        del_club = self._entrega(dispositivo=self.club)
        de_la_escuela = self._entrega(dispositivo=self.escuela)

        def filas(**filtros):
            return [fila["entrega"] for fila in self.client.get(URL_ENTREGAS, filtros).context["filas"]]

        self.assertEqual(filas(dispositivo=self.escuela.pk), [de_la_escuela])
        self.assertEqual(filas(localidad="Resistencia"), [del_club])
        self.assertEqual(filas(fecha="2026-11-12"), [de_la_escuela, del_club])
        self.assertEqual(filas(fecha="2026-11-13"), [])
        self.assertEqual(filas(estado="EN_CAMINO"), [])
        # Un valor que no es de la lista se ignora: el listado no rebota por una URL vieja.
        self.assertEqual(filas(estado="NO_EXISTE", dispositivo="x", fecha="ayer"), [de_la_escuela, del_club])

    def test_los_estados_vacios(self):
        respuesta = self.client.get(URL_ENTREGAS)
        self.assertContains(respuesta, "Todavía no hay entregas")

        self._recibir(self._en_camino())
        self.assertContains(self.client.get(URL_ENTREGAS), "No hay entregas en esta solapa")
        self.assertContains(
            self.client.get(URL_ENTREGAS, {"solapa": "recibidas", "localidad": "Otra"}),
            "Ninguna entrega coincide con los filtros",
        )

    def test_las_acciones_de_la_fila_dependen_del_estado(self):
        preparada, en_camino = self._entrega(), self._en_camino()
        recibida = self._recibir(self._en_camino())

        filas = {fila["entrega"].pk: fila for fila in self.client.get(URL_ENTREGAS).context["filas"]}
        recibidas = self.client.get(URL_ENTREGAS, {"solapa": "recibidas"}).context["filas"]

        self.assertEqual([a["texto"] for a in filas[preparada.pk]["acciones"]], ["Marcar en camino", "Cancelar"])
        self.assertEqual([a["texto"] for a in filas[en_camino.pk]["acciones"]], ["Cancelar"])
        self.assertEqual([fila["acciones"] for fila in recibidas if fila["entrega"].pk == recibida.pk], [[]])

    def test_el_modal_de_marcar_en_camino_lo_abre_la_url_solo_si_la_entrega_esta_preparada(self):
        preparada, en_camino = self._entrega(), self._en_camino()

        abierto = self.client.get(URL_ENTREGAS, {"en_camino": preparada.pk})
        cerrado = self.client.get(URL_ENTREGAS, {"en_camino": en_camino.pk})

        self.assertEqual(abierto.context["modal_en_camino"]["entrega"], preparada)
        self.assertContains(abierto, f'action="{self._url("entrega_en_camino", preparada.pk)}"')
        self.assertContains(abierto, "modalEnCamino: true")
        self.assertIsNone(cerrado.context["modal_en_camino"])
        self.assertContains(cerrado, "modalEnCamino: false")
        self.assertIsNone(self.client.get(URL_ENTREGAS, {"en_camino": "x"}).context["modal_en_camino"])

    def test_el_modal_de_cancelar_pide_el_motivo(self):
        entrega = self._en_camino()

        respuesta = self.client.get(URL_ENTREGAS, {"cancelar": entrega.pk})

        self.assertEqual(respuesta.context["modal_cancelar"]["entrega"], entrega)
        self.assertContains(respuesta, 'name="motivo"')
        self.assertContains(respuesta, "csrfmiddlewaretoken")
        # El parámetro que abre el modal no cuenta como filtro: el estado vacío no es el «con filtros».
        self.assertEqual(respuesta.context["filtro"], {})

    def test_desde_el_listado_la_accion_vuelve_al_listado(self):
        entrega = self._entrega()

        respuesta = self.client.post(
            self._url("entrega_en_camino", entrega.pk), {"transporte": "Camioneta", "hora": "", "volver": "listado"}
        )

        self.assertRedirects(respuesta, URL_ENTREGAS)
        self.assertEqual(EntregaKit.objects.get(pk=entrega.pk).estado, Estado.EN_CAMINO)
        # Un `volver` que no es el valor fijo no redirige a ningún otro lado.
        otra = self._entrega()
        respuesta = self.client.post(
            self._url("entrega_cancelar", otra.pk), {"motivo": "Error", "volver": "https://evil.example/"}
        )
        self.assertRedirects(respuesta, self._url("entrega_detalle", otra.pk))

    def test_pagina_de_a_cincuenta(self):
        for _ in range(ENTREGAS_POR_PAGINA + 1):
            self._entrega()

        primera = self.client.get(URL_ENTREGAS)
        segunda = self.client.get(URL_ENTREGAS, {"page": 2})

        self.assertEqual(len(primera.context["filas"]), ENTREGAS_POR_PAGINA)
        self.assertEqual(len(segunda.context["filas"]), 1)

    @tag("performance")
    def test_el_listado_con_200_entregas_cuesta_lo_mismo_que_con_5(self):
        """Presupuesto de E4: página, conteo de la paginación, solapas y opciones de los filtros."""
        for _ in range(5):
            self._entrega()
        self.client.get(URL_ENTREGAS)
        con_cinco = self._consultas(URL_ENTREGAS)

        for n in range(195):
            entrega = self._entrega(dispositivo=self.escuela if n % 2 else self.club)
            if n % 3 == 0:
                servicio.marcar_en_camino(entrega, self.operador)

        self.assertEqual(self._consultas(URL_ENTREGAS), con_cinco)
        # Las cinco del listado, sin contar sesión, usuario y permisos del shell.
        self.assertLessEqual(self._consultas(URL_ENTREGAS, solo_kits=True), 5)

    def _consultas(self, url, solo_kits=False):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as consultas:
            self.assertEqual(self.client.get(url).status_code, 200)
        if solo_kits:
            return len([c for c in consultas if "entregakit" in c["sql"].lower() or "lineaentrega" in c["sql"].lower()])
        return len(consultas)


# ---------------------------------------------------------------------------
# E4 · «Nueva entrega»
# ---------------------------------------------------------------------------


class NuevaEntregaTests(BaseVistasKits):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.operador)
        self.url_items = self._url("entrega_nueva_items", self.club.pk)
        self.url_confirmar = self._url("entrega_nueva_confirmar", self.club.pk)

    def test_paso_1_lista_los_dispositivos_activos_con_su_resumen(self):
        from programas.models import Dispositivo

        self._dispositivo("Parroquia cerrada", estado=Dispositivo.Estado.CERRADO)
        self._ocupar(self.club, 3)
        self._recibida_con_faltante()

        respuesta = self.client.get(URL_NUEVA)

        self.assertTemplateUsed(respuesta, "programas/emergencia/kits/nueva_destino.html")
        destinos = {destino["nombre"]: destino for destino in respuesta.context["destinos"]}
        self.assertEqual(set(destinos), {"Club Sarmiento", "Escuela 12"})
        self.assertEqual((destinos["Club Sarmiento"]["alojadas"], destinos["Club Sarmiento"]["plazas"]), (3, "3 de 4"))
        self.assertTrue(destinos["Club Sarmiento"]["ultima_entrega"]["con_diferencias"])
        self.assertIsNone(destinos["Escuela 12"]["ultima_entrega"])
        self.assertContains(respuesta, f'href="{self.url_items}"')
        self.assertContains(respuesta, "Paso 1 de 3")
        self.assertContains(respuesta, "Con diferencias")

    def test_paso_1_busca_por_nombre_o_localidad(self):
        por_nombre = self.client.get(URL_NUEVA, {"q": "sarmi"}).context["destinos"]
        por_localidad = self.client.get(URL_NUEVA, {"q": "barranq"}).context["destinos"]
        sin_nada = self.client.get(URL_NUEVA, {"q": "zzz"})

        self.assertEqual([d["nombre"] for d in por_nombre], ["Club Sarmiento"])
        self.assertEqual([d["nombre"] for d in por_localidad], ["Escuela 12"])
        self.assertContains(sin_nada, "Ningún dispositivo coincide con la búsqueda")

    def test_paso_2_ofrece_el_catalogo_activo(self):
        TipoKit.objects.filter(pk=self.agua.pk).update(activo=False)

        respuesta = self.client.get(self.url_items)

        self.assertTemplateUsed(respuesta, "programas/emergencia/kits/nueva_items.html")
        self.assertEqual(
            [campo.label for campo in respuesta.context["form"].campos_de_cantidad()], ["Colchón", "Kit alimentario"]
        )
        self.assertContains(respuesta, "En unidad.")
        self.assertContains(respuesta, f'action="{self.url_confirmar}"')
        self.assertContains(respuesta, "Paso 2 de 3")

    def test_paso_2_sin_catalogo_lo_dice_y_no_ofrece_el_formulario(self):
        TipoKit.objects.update(activo=False)

        respuesta = self.client.get(self.url_items)

        self.assertContains(respuesta, "El catálogo de kits no tiene ítems activos")
        self.assertNotContains(respuesta, "Continuar")
        self.assertNotContains(respuesta, 'name="repone_a"')
        self.assertNotContains(respuesta, reverse("emergencia:configuracion") + '"')

    def test_hu_4_1_una_cantidad_en_cero_no_avanza(self):
        datos = self._cantidades(a=(self.colchon, 0), b=(self.alimentos, 3))

        respuesta = self.client.post(self.url_confirmar, datos)

        self.assertEqual(respuesta.status_code, 400)
        self.assertTemplateUsed(respuesta, "programas/emergencia/kits/nueva_items.html")
        self.assertContains(respuesta, "Sacá el ítem o poné una cantidad", status_code=400)
        self.assertFalse(EntregaKit.objects.exists())

    def test_hu_4_1_sin_ninguna_cantidad_no_avanza(self):
        respuesta = self.client.post(self.url_confirmar, self._cantidades())

        self.assertEqual(respuesta.status_code, 400)
        self.assertContains(respuesta, "La entrega necesita al menos un ítem con cantidad.", status_code=400)

    def test_paso_3_muestra_el_resumen_y_todavia_no_escribe(self):
        datos = self._cantidades(a=(self.colchon, 10), b=(self.alimentos, 3))

        respuesta = self.client.post(self.url_confirmar, datos)

        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "programas/emergencia/kits/nueva_confirmar.html")
        self.assertEqual(
            respuesta.context["lineas"],
            [
                {"item": "Colchón", "cantidad": 10, "unidad": "unidad"},
                {"item": "Kit alimentario", "cantidad": 3, "unidad": "kit"},
            ],
        )
        self.assertContains(respuesta, f'name="cantidad_{self.colchon.pk}" value="10"')
        self.assertContains(respuesta, 'name="confirmar"')
        self.assertContains(respuesta, "Paso 3 de 3")
        self.assertFalse(EntregaKit.objects.exists())

    def test_hu_4_1_confirmar_crea_la_entrega_preparada(self):
        datos = self._cantidades(a=(self.colchon, 10), b=(self.alimentos, 3))
        datos.update(confirmar="1", observacion="Entregar a la directora.")

        respuesta = self.client.post(self.url_confirmar, datos)

        entrega = EntregaKit.objects.get()
        self.assertRedirects(respuesta, self._url("entrega_detalle", entrega.pk))
        self.assertEqual(
            (entrega.estado, entrega.dispositivo, entrega.armada_por), (Estado.PREPARADA, self.club, self.operador)
        )
        self.assertEqual(entrega.observacion_mesa, "Entregar a la directora.")
        self.assertEqual(
            list(entrega.lineas.order_by("id").values_list("item__nombre", "cantidad_enviada")),
            [("Colchón", 10), ("Kit alimentario", 3)],
        )
        self.assertIn(f"Entrega {entrega.numero} armada para Club Sarmiento", self._avisos(respuesta)[0])
        self.assertIn(entrega, [fila["entrega"] for fila in self.client.get(URL_ENTREGAS).context["filas"]])

    def test_el_asistente_no_guarda_nada_en_la_sesion(self):
        """Dos pestañas, dos destinos: cada «Crear entrega» escribe lo que mostró su pantalla."""
        claves_antes = set(self.client.session.keys())
        para_el_club = self._cantidades(a=(self.colchon, 10))
        para_la_escuela = self._cantidades(a=(self.agua, 6))
        # Las dos pestañas llegan al paso 3 antes de que ninguna confirme.
        self.client.post(self.url_confirmar, para_el_club)
        self.client.post(self._url("entrega_nueva_confirmar", self.escuela.pk), para_la_escuela)
        self.assertEqual(set(self.client.session.keys()), claves_antes)

        self.client.post(self.url_confirmar, {**para_el_club, "confirmar": "1"})
        self.client.post(self._url("entrega_nueva_confirmar", self.escuela.pk), {**para_la_escuela, "confirmar": "1"})

        club = EntregaKit.objects.get(dispositivo=self.club)
        escuela = EntregaKit.objects.get(dispositivo=self.escuela)
        self.assertEqual(list(club.lineas.values_list("item__nombre", "cantidad_enviada")), [("Colchón", 10)])
        self.assertEqual(list(escuela.lineas.values_list("item__nombre", "cantidad_enviada")), [("Agua 6 l", 6)])

    def test_un_item_que_se_desactivo_entre_el_paso_2_y_el_3_no_se_descarta_en_silencio(self):
        datos = self._cantidades(a=(self.colchon, 10), b=(self.agua, 6))
        datos["confirmar"] = "1"
        TipoKit.objects.filter(pk=self.agua.pk).update(activo=False)

        respuesta = self.client.post(self.url_confirmar, datos)

        self.assertEqual(respuesta.status_code, 400)
        self.assertContains(respuesta, "ya no está en el catálogo activo", status_code=400)
        self.assertFalse(EntregaKit.objects.exists())

    def test_anterior_vuelve_al_paso_2_con_las_cantidades(self):
        datos = self._cantidades(a=(self.colchon, 10), b=(self.alimentos, 3))

        respuesta = self.client.post(self.url_items, datos)

        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "programas/emergencia/kits/nueva_items.html")
        self.assertContains(respuesta, f'name="cantidad_{self.colchon.pk}" value="10"')
        self.assertFalse(respuesta.context["form"].is_bound)
        self.assertFalse(EntregaKit.objects.exists())

    def test_el_paso_3_no_se_abre_por_get(self):
        self.assertRedirects(self.client.get(self.url_confirmar), self.url_items)


# ---------------------------------------------------------------------------
# E5 · Detalle y acciones de la mesa
# ---------------------------------------------------------------------------


class DetalleDeEntregaTests(BaseVistasKits):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.operador)

    def _detalle(self, entrega):
        return self.client.get(self._url("entrega_detalle", entrega.pk))

    def test_una_preparada_ofrece_marcar_en_camino_y_cancelar(self):
        respuesta = self._detalle(self._entrega(observacion="Entregar a la directora."))

        self.assertTemplateUsed(respuesta, "programas/emergencia/kits/detail.html")
        self.assertTrue(respuesta.context["puede_marcar_en_camino"])
        self.assertTrue(respuesta.context["puede_cancelar"])
        self.assertEqual(respuesta.context["url_reponer"], "")
        self.assertNotIn("form_observar", respuesta.context)
        texto = _texto(respuesta.content.decode())
        self.assertIn("Entregar a la directora.", texto)
        self.assertIn("Todavía no hay remito", texto)
        self.assertIn("Entrega armada", texto)

    def test_hu_4_4_con_diferencias_muestra_enviado_recibido_diferencia_observacion_y_remito(self):
        entrega = self._en_camino()
        recibida = self._recibir(
            entrega, {self.colchon.pk: 8, self.alimentos.pk: 4}, observacion="Faltaron dos colchones."
        )

        respuesta = self._detalle(recibida)

        self.assertEqual(respuesta.context["estado_texto"], "Recibida con diferencias")
        html = respuesta.content.decode()
        texto = _texto(html)
        self.assertIn("−2 · faltan", texto)
        self.assertIn("+1 · de más", texto)
        self.assertIn("Faltaron dos colchones.", texto)
        self.assertIn("Gabi Guardia_Club", texto)
        self.assertIn(f'href="/media/{recibida.remito.name}"', html)
        self.assertEqual(respuesta.context["remito"][0]["alt"], f"Remito de la entrega {recibida.numero}")
        self.assertIn(f"{self._url('entrega_nueva_items', self.club.pk)}?repone={recibida.pk}", html)
        self.assertFalse(respuesta.context["puede_cancelar"])
        self.assertIn("form_observar", respuesta.context)

    def test_una_recibida_completa_no_ofrece_reponer(self):
        respuesta = self._detalle(self._recibir(self._en_camino()))

        self.assertEqual(respuesta.context["url_reponer"], "")
        self.assertIn("sin diferencia", _texto(respuesta.content.decode()))

    def test_solo_de_mas_no_ofrece_reponer(self):
        """Reponer precarga lo que faltó: si solo llegó de más, no hay nada que reponer."""
        recibida = self._recibir(self._en_camino(), {self.colchon.pk: 10, self.alimentos.pk: 5})

        self.assertEqual(self._detalle(recibida).context["url_reponer"], "")

    def test_marcar_en_camino_desde_el_detalle(self):
        entrega = self._entrega()

        respuesta = self.client.post(
            self._url("entrega_en_camino", entrega.pk), {"transporte": "Camioneta AB123CD", "hora": "2026-11-12T09:30"}
        )

        self.assertRedirects(respuesta, self._url("entrega_detalle", entrega.pk))
        actual = EntregaKit.objects.get(pk=entrega.pk)
        self.assertEqual((actual.estado, actual.transporte), (Estado.EN_CAMINO, "Camioneta AB123CD"))
        self.assertEqual(actual.despachada_en, T0 - timedelta(minutes=30))
        self.assertEqual(self._avisos(respuesta), [f"La entrega {entrega.numero} está en camino."])

    def test_una_hora_de_salida_futura_o_ilegible_no_la_marca(self):
        entrega = self._entrega()

        for hora, aviso in (("2026-11-12T10:30", "no puede ser posterior"), ("mañana", "Indicá la fecha y la hora")):
            with self.subTest(hora=hora):
                respuesta = self.client.post(self._url("entrega_en_camino", entrega.pk), {"hora": hora})
                self.assertIn(aviso, self._avisos(respuesta)[0])
        self.assertEqual(EntregaKit.objects.get(pk=entrega.pk).estado, Estado.PREPARADA)

    def test_cancelar_pide_el_motivo(self):
        entrega = self._en_camino()

        sin_motivo = self.client.post(self._url("entrega_cancelar", entrega.pk), {"motivo": "  "})
        self.assertEqual(self._avisos(sin_motivo), ["Indicá por qué se cancela la entrega."])
        self.assertEqual(EntregaKit.objects.get(pk=entrega.pk).estado, Estado.EN_CAMINO)

        con_motivo = self.client.post(self._url("entrega_cancelar", entrega.pk), {"motivo": "El camión volvió"})
        self.assertEqual(self._avisos(con_motivo), [f"Entrega {entrega.numero} cancelada."])
        self.assertEqual(EntregaKit.objects.get(pk=entrega.pk).estado, Estado.CANCELADA)
        self.assertIn("El camión volvió", _texto(self._detalle(entrega).content.decode()))

    def test_la_segunda_pestana_recibe_el_aviso_y_no_un_500(self):
        """La guardia la recibió mientras la mesa tenía el modal de cancelar abierto."""
        entrega = self._en_camino()
        self._recibir(entrega)

        respuesta = self.client.post(self._url("entrega_cancelar", entrega.pk), {"motivo": "Ya no hace falta"})

        self.assertRedirects(respuesta, self._url("entrega_detalle", entrega.pk))
        self.assertIn("ya la recibió Gabi Guardia_Club", self._avisos(respuesta)[0])
        self.assertEqual(EntregaKit.objects.get(pk=entrega.pk).estado, Estado.RECIBIDA)

    def test_rn_4_5_la_mesa_observa_y_las_cantidades_no_cambian(self):
        recibida = self._recibida_con_faltante()
        lineas = list(LineaEntrega.objects.filter(entrega=recibida).order_by("id").values())

        respuesta = self.client.post(self._url("entrega_observar", recibida.pk), {"texto": "Se reclamó."})

        self.assertRedirects(respuesta, self._url("entrega_detalle", recibida.pk))
        self.assertEqual(EntregaKit.objects.get(pk=recibida.pk).observacion_mesa, "Se reclamó.")
        self.assertEqual(list(LineaEntrega.objects.filter(entrega=recibida).order_by("id").values()), lineas)
        self.assertIn("Observación de la mesa", _texto(self._detalle(recibida).content.decode()))

    def test_observar_una_entrega_abierta_avisa_y_no_escribe(self):
        entrega = self._en_camino()

        respuesta = self.client.post(self._url("entrega_observar", entrega.pk), {"texto": "Nota"})

        self.assertIn("todavía no fue recibida", self._avisos(respuesta)[0])
        self.assertEqual(EntregaKit.objects.get(pk=entrega.pk).observacion_mesa, "")

    def test_no_hay_ninguna_url_que_edite_la_recepcion(self):
        """RN-4.5: las únicas acciones de la mesa sobre una entrega son estas tres."""
        acciones = {url.rstrip("/").rsplit("/", 1)[-1] for url in urls_de_emergencia() if "/entregas/1/" in url}
        self.assertEqual(acciones, {"1", "en-camino", "cancelar", "observar"})


# ---------------------------------------------------------------------------
# La recepción en el dispositivo
# ---------------------------------------------------------------------------


class RecepcionEnElDispositivoTests(BaseVistasKits):
    def setUp(self):
        super().setUp()
        self.entrega = self._en_camino(dispositivo=self.club, observacion="Entregar a la directora.")
        self.url_kits = self._url("dispositivo_kits", self.club.pk)
        self.url_recibir = self._url("dispositivo_kit_recibir", self.club.pk, self.entrega.pk)

    def _cuerpo(self, colchones=10, kits=3, remito="jpeg", **extra):
        cuerpo = {f"cantidad_{self.colchon.pk}": colchones, f"cantidad_{self.alimentos.pk}": kits, **extra}
        if remito == "jpeg":
            cuerpo["remito"] = self._remito_http()
        elif remito is not None:
            cuerpo["remito"] = remito
        return cuerpo

    def test_sin_login_redirige_al_login(self):
        for url in (self.url_kits, self.url_recibir):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).url, f"{reverse('users:login')}?next={url}")
                self.assertEqual(self.client.post(url, {}).status_code, 302)

    def test_sin_la_capacidad_en_ningun_dispositivo_es_un_403(self):
        """Lo mismo que la API contesta con ``SIN_MODULO``: no abre esta parte del módulo."""
        sin_equipo = self._guardia("sin_equipo", [RECIBIR_KIT])
        admisor = self._guardia("admisor", [ADMITIR, "dispositivo.ver"], [self.club])
        de_becas = self._usuario("de_becas", ["becas.campo"], programa=self.becas)
        antes = self._foto(self.entrega)

        for usuario in (sin_equipo, admisor, de_becas, self.operador, self.supervisor, self.agente):
            self.client.force_login(usuario)
            for url in (self.url_kits, self.url_recibir):
                with self.subTest(usuario=usuario.username, url=url):
                    self.assertEqual(self.client.get(url).status_code, 403)
                    self.assertEqual(self.client.post(url, self._cuerpo()).status_code, 403)
        self.assertEqual(self._foto(self.entrega), antes)

    def test_la_guardia_de_otro_dispositivo_recibe_404(self):
        """**Mutación de RN-4.8 por HTTP.** ``recibir_kit`` en la Escuela no abre nada del Club.

        Visto en rojo: con ``RecepcionKitsMixin`` aceptando a quien tiene la capacidad en
        **algún** dispositivo (sin filtrar por el de la URL), los dos GET del Club contestan
        200 («200 != 404») y la guardia de la Escuela ve la entrega ajena. El 404 es el de un
        id inexistente: el cuerpo no nombra al Club.
        """
        self.client.force_login(self.guardia_escuela)
        antes = self._foto(self.entrega)
        # La entrega del Club pedida por el Club, y pedida por su propio dispositivo.
        por_la_escuela = self._url("dispositivo_kit_recibir", self.escuela.pk, self.entrega.pk)

        for url in (self.url_kits, self.url_recibir, por_la_escuela):
            with self.subTest(url=url):
                respuesta = self.client.get(url)
                self.assertEqual(respuesta.status_code, 404)
                self.assertNotIn("Club Sarmiento", respuesta.content.decode())
                self.assertEqual(self.client.post(url, self._cuerpo()).status_code, 404)

        self.assertEqual(self._foto(self.entrega), antes)
        self.assertFalse(EntregaKit.objects.get(pk=self.entrega.pk).remito)
        self.assertFalse(EntradaBitacora.objects.exists())
        # …y un dispositivo que no existe contesta lo mismo.
        self.assertEqual(self.client.get(self._url("dispositivo_kits", 999_999)).status_code, 404)

    def test_la_guardia_ve_las_pendientes_de_su_dispositivo(self):
        preparada = self._entrega(dispositivo=self.club)
        self._en_camino(dispositivo=self.escuela)
        self.client.force_login(self.guardia)

        respuesta = self.client.get(self.url_kits)

        self.assertTemplateUsed(respuesta, "programas/emergencia/kits/pendientes.html")
        self.assertEqual([fila["entrega"] for fila in respuesta.context["filas"]], [self.entrega, preparada])
        self.assertContains(respuesta, f'href="{self.url_recibir}"')
        self.assertContains(respuesta, "Sin marca de salida")
        self.assertEqual(respuesta.context["url_dispositivo"], "")

    def test_el_enlace_al_dispositivo_solo_si_lo_puede_ver(self):
        con_ver = self._guardia("guardia_con_ver", [RECIBIR_KIT, "dispositivo.ver"], [self.club])
        self.client.force_login(con_ver)

        self.assertEqual(
            self.client.get(self.url_kits).context["url_dispositivo"],
            reverse("dispositivos:detalle", args=[self.club.pk]),
        )

    def test_el_formulario_llega_precargado_con_lo_enviado(self):
        self.client.force_login(self.guardia)

        respuesta = self.client.get(self.url_recibir)

        self.assertTemplateUsed(respuesta, "programas/emergencia/kits/recibir.html")
        self.assertContains(respuesta, f'name="cantidad_{self.colchon.pk}" value="10"')
        self.assertContains(respuesta, f'name="cantidad_{self.alimentos.pk}" value="3"')
        self.assertContains(respuesta, 'enctype="multipart/form-data"')
        self.assertContains(respuesta, "Entregar a la directora.")
        self.assertContains(respuesta, "Se enviaron 10 · en unidad.")

    def test_hu_4_3_confirmar_sin_tocar_nada_la_deja_recibida(self):
        self.client.force_login(self.guardia)

        respuesta = self.client.post(self.url_recibir, self._cuerpo(observacion="Todo en orden."))

        self.assertRedirects(respuesta, self.url_kits)
        recibida = EntregaKit.objects.get(pk=self.entrega.pk)
        self.assertEqual((recibida.estado, recibida.recibida_por), (Estado.RECIBIDA, self.guardia))
        self.assertEqual(recibida.observacion_dispositivo, "Todo en orden.")
        self.assertTrue(recibida.remito.name.startswith(f"emergencia/entregas/{recibida.carpeta_media}/"))
        self.assertEqual(self._avisos(respuesta), [f"Entrega {recibida.numero}: recibida completa."])
        self.assertEqual(self.client.get(self.url_kits).context["filas"], [])

    def test_hu_4_3_cambiar_una_cantidad_la_deja_con_diferencias(self):
        self.client.force_login(self.guardia)

        respuesta = self.client.post(self.url_recibir, self._cuerpo(colchones=8))

        recibida = EntregaKit.objects.get(pk=self.entrega.pk)
        self.assertEqual(recibida.estado, Estado.RECIBIDA_CON_DIFERENCIAS)
        self.assertEqual(recibida.lineas.get(item=self.colchon).diferencia, -2)
        self.assertEqual(self._avisos(respuesta), [f"Entrega {recibida.numero}: recibida · 1 ítem con diferencia."])

    def test_hu_4_3_sin_la_foto_dice_que_falta_el_remito(self):
        self.client.force_login(self.guardia)

        respuesta = self.client.post(self.url_recibir, self._cuerpo(remito=None))

        self.assertEqual(respuesta.status_code, 400)
        self.assertContains(respuesta, "Falta la foto del remito.", status_code=400)
        self.assertEqual(EntregaKit.objects.get(pk=self.entrega.pk).estado, Estado.EN_CAMINO)

    def test_un_remito_que_no_es_jpeg_vuelve_a_su_campo(self):
        self.client.force_login(self.guardia)
        png = self._remito_http("remito.png", PNG, "image/png")

        respuesta = self.client.post(self.url_recibir, self._cuerpo(colchones=7, remito=png))

        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(respuesta.context["form"].errors["remito"], ["La foto del remito tiene que llegar en JPEG."])
        # Lo que ya había cargado no se pierde.
        self.assertContains(respuesta, f'name="cantidad_{self.colchon.pk}" value="7"', status_code=400)
        self.assertEqual(EntregaKit.objects.get(pk=self.entrega.pk).estado, Estado.EN_CAMINO)

    def test_una_cantidad_vacia_o_negativa_no_se_acepta(self):
        self.client.force_login(self.guardia)

        for cantidad, aviso in (("", "Indicá cuánto llegó, aunque sea cero."), ("-1", "cero o más")):
            with self.subTest(cantidad=cantidad):
                respuesta = self.client.post(self.url_recibir, self._cuerpo(colchones=cantidad))
                self.assertContains(respuesta, aviso, status_code=400)
        self.assertEqual(EntregaKit.objects.get(pk=self.entrega.pk).estado, Estado.EN_CAMINO)

    def test_si_la_mesa_la_cancelo_mientras_cargaba_avisa_y_vuelve_a_las_pendientes(self):
        self.client.force_login(self.guardia)
        self.reloj.avanzar(hours=5, minutes=2)
        servicio.cancelar_entrega(self.entrega, self.operador, "El camión volvió")

        respuesta = self.client.post(self.url_recibir, self._cuerpo())

        self.assertRedirects(respuesta, self.url_kits)
        self.assertEqual(
            self._avisos(respuesta),
            [f"Entrega {self.entrega.numero} cancelada por la mesa a las 15:02. Ya no se puede recibir."],
        )
        self.assertFalse(EntregaKit.objects.get(pk=self.entrega.pk).remito)

    def test_abrir_una_ya_recibida_avisa_y_vuelve_a_las_pendientes(self):
        self._recibir(self.entrega)
        self.client.force_login(self.guardia)

        respuesta = self.client.get(self.url_recibir)

        self.assertRedirects(respuesta, self.url_kits)
        self.assertIn("ya la recibió", self._avisos(respuesta)[0])

    def test_una_fila_del_equipo_dada_de_baja_ya_no_entra(self):
        MiembroEquipoDispositivo.objects.filter(usuario=self.guardia).update(activo=False)
        self.client.force_login(self.guardia)

        self.assertEqual(self.client.get(self.url_kits).status_code, 403)


class EntradaEnElDetalleDelDispositivoTests(BaseVistasKits):
    """«Emergencia · Kits» en el menú del detalle del dispositivo (P4)."""

    def _detalle(self, usuario, dispositivo):
        self.client.force_login(usuario)
        return self.client.get(reverse("dispositivos:detalle", args=[dispositivo.pk]))

    def test_la_ve_quien_recibe_kits_en_ese_dispositivo(self):
        con_ver = self._guardia("guardia_con_ver", [RECIBIR_KIT, "dispositivo.ver"], [self.club])

        respuesta = self._detalle(con_ver, self.club)

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context["url_kits_emergencia"], self._url("dispositivo_kits", self.club.pk))
        self.assertContains(respuesta, "Emergencia · Kits")
        self.assertContains(respuesta, f'href="{self._url("dispositivo_kits", self.club.pk)}"')

    def test_no_la_ve_quien_ve_el_dispositivo_sin_recibir_kits(self):
        solo_ver = self._guardia("solo_ver", ["dispositivo.ver", ADMITIR], [self.club])

        respuesta = self._detalle(solo_ver, self.club)

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context["url_kits_emergencia"], "")
        self.assertNotContains(respuesta, "Emergencia · Kits")

    def test_recibir_kits_en_otro_dispositivo_no_la_muestra_en_este(self):
        mixto = self._guardia("mixto", [RECIBIR_KIT, "dispositivo.ver"], [self.escuela])
        self._sumar_rol(mixto, ["dispositivo.ver"], self.dispositivos, [self.club])

        respuesta = self._detalle(mixto, self.club)

        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, "Emergencia · Kits")


# ---------------------------------------------------------------------------
# Punta a punta
# ---------------------------------------------------------------------------


class PuntaAPuntaTests(BaseVistasKits):
    def setUp(self):
        super().setUp()
        self.media_http = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media_http, ignore_errors=True)
        ajuste = override_settings(MEDIA_ROOT=self.media_http)
        ajuste.enable()
        self.addCleanup(ajuste.disable)

    def test_crear_marcar_recibir_con_diferencia_ver_y_reponer(self):
        # Un cliente por persona: el backoffice admite una sola sesión por usuario, y volver a
        # entrar con el mismo cliente reemplazaría la anterior.
        mesa, guardia = Client(), Client()
        mesa.force_login(self.operador)
        guardia.force_login(self.guardia)

        # 1. La mesa arma la entrega en tres pasos.
        cliente = mesa
        self.assertContains(cliente.get(URL_NUEVA), self._url("entrega_nueva_items", self.club.pk))
        cantidades = self._cantidades(a=(self.colchon, 10), b=(self.alimentos, 3))
        url_confirmar = self._url("entrega_nueva_confirmar", self.club.pk)
        self.assertEqual(cliente.post(url_confirmar, cantidades).status_code, 200)
        cliente.post(url_confirmar, {**cantidades, "confirmar": "1", "observacion": "Para la guardia de la tarde."})
        entrega = EntregaKit.objects.get()
        self.assertEqual(entrega.estado, Estado.PREPARADA)

        # 2. La marca en camino desde el listado.
        cliente.post(self._url("entrega_en_camino", entrega.pk), {"transporte": "Camioneta", "volver": "listado"})
        self.assertEqual(EntregaKit.objects.get(pk=entrega.pk).estado, Estado.EN_CAMINO)

        # 3. La guardia del dispositivo la recibe con dos colchones menos.
        self.reloj.avanzar(hours=2)
        cliente = guardia
        url_kits = self._url("dispositivo_kits", self.club.pk)
        url_recibir = self._url("dispositivo_kit_recibir", self.club.pk, entrega.pk)
        self.assertContains(cliente.get(url_kits), url_recibir)
        self.assertContains(cliente.get(url_recibir), "Para la guardia de la tarde.")
        respuesta = cliente.post(
            url_recibir,
            {
                f"cantidad_{self.colchon.pk}": "8",
                f"cantidad_{self.alimentos.pk}": "3",
                "remito": self._remito_http(),
                "observacion": "Faltaron dos colchones.",
            },
        )
        self.assertRedirects(respuesta, url_kits)
        recibida = EntregaKit.objects.get(pk=entrega.pk)
        self.assertEqual(recibida.estado, Estado.RECIBIDA_CON_DIFERENCIAS)
        # La guardia baja el remito que subió; la mesa también.
        self.assertEqual(cliente.get(f"/media/{recibida.remito.name}").status_code, 200)

        # 4. La mesa la ve en «Con diferencias» y E5 muestra la diferencia.
        cliente = mesa
        con_diferencias = cliente.get(URL_ENTREGAS, {"solapa": "con_diferencias"})
        self.assertEqual([fila["entrega"] for fila in con_diferencias.context["filas"]], [recibida])
        detalle = cliente.get(self._url("entrega_detalle", recibida.pk))
        texto = _texto(detalle.content.decode())
        self.assertIn("−2 · faltan", texto)
        self.assertIn("Faltaron dos colchones.", texto)
        self.assertEqual(cliente.get(f"/media/{recibida.remito.name}").status_code, 200)

        # 5. Reponer: el paso 2 arranca con lo que faltó y la entrega nueva guarda a quién repone.
        paso_2 = cliente.get(detalle.context["url_reponer"])
        self.assertContains(paso_2, f'name="cantidad_{self.colchon.pk}" value="2"')
        self.assertNotContains(paso_2, f'name="cantidad_{self.alimentos.pk}" value=')
        self.assertContains(paso_2, f'name="repone_a" value="{recibida.pk}"')
        self.assertContains(paso_2, f"Repone a la entrega {recibida.numero}")
        reposicion_datos = {**self._cantidades(a=(self.colchon, 2)), "repone_a": str(recibida.pk)}
        paso_3 = cliente.post(url_confirmar, reposicion_datos)
        self.assertContains(paso_3, f"la entrega {recibida.numero}")
        cliente.post(url_confirmar, {**reposicion_datos, "confirmar": "1"})

        reposicion = EntregaKit.objects.exclude(pk=recibida.pk).get()
        self.assertEqual(reposicion.repone_a, recibida)
        self.assertEqual(list(reposicion.lineas.values_list("item__nombre", "cantidad_enviada")), [("Colchón", 2)])
        # E5 lo muestra en los dos sentidos.
        self.assertContains(
            cliente.get(self._url("entrega_detalle", reposicion.pk)), f"Repone a la entrega {recibida.numero}"
        )
        original = cliente.get(self._url("entrega_detalle", recibida.pk))
        self.assertEqual([r["numero"] for r in original.context["reposiciones"]], [reposicion.numero])
        self.assertContains(original, self._url("entrega_detalle", reposicion.pk))
        # La traza cuenta toda la historia.
        self.assertEqual(
            list(TrazaEntrega.objects.filter(entrega=recibida).order_by("id").values_list("accion", flat=True)),
            ["CREADA", "EN_CAMINO", "RECIBIDA"],
        )
