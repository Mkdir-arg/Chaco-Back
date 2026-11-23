"""Módulo Emergencia, PR 9: las entregas de kits en el backoffice — E4 y E5, la mesa.

La recepción en el dispositivo (la guardia) vive en ``test_emergencia_kits_guardia_vistas``, que usa la base
``BaseVistasKits`` de este módulo.

Las reglas de la entrega ya están probadas contra el servicio en ``test_emergencia_kits``.
Acá se prueba **la puerta HTTP**: que cada vista exija lo que tiene que exigir, que traduzca
lo que contesta el servicio sin escribir nada por su cuenta, y que el flujo ande de punta a
punta.

* **Acceso de la mesa** — sin login, al login; sin operar ni supervisar, 403. El barrido de
  URLs ``emergencia:*`` de ``test_emergencia_base`` cubre las rutas nuevas sin listarlas.
* **Acceso de la guardia** (RN-4.8, plan §2 C2) — en ``test_emergencia_kits_guardia_vistas``: sin
  ``recibir_kit`` en ningún dispositivo, 403; con la capacidad en **otro** dispositivo, **404**,
  y nada cambia. Es la mutación de 04 §11 por HTTP: con el recorte por alcance de
  ``RecepcionKitsMixin`` reemplazado por «tiene la capacidad en algún lado»,
  ``test_la_guardia_de_otro_dispositivo_recibe_404`` falla con «200 != 404». El POST lo sigue
  frenando el servicio, que tiene su propia guarda y su propia mutación en ``test_emergencia_kits``.
* **Punta a punta** — crear en una pantalla → en camino → recibir con diferencia → E5 muestra la
  diferencia → reponer (una sola vez) o aceptar con motivo.
* **La pantalla de nueva entrega no usa la sesión** — se crea lo que trajo el envío.
* **Presupuesto** — E4 con 200 entregas (``--tag performance``).
"""

import re
import shutil
import tempfile
from datetime import timedelta
from unittest import mock

from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings, tag
from django.urls import reverse

from programas.models import EntregaKit, LineaEntrega, TipoKit, TrazaEntrega
from programas.services import kits as servicio
from programas.tests.test_emergencia_base import OPERAR, SUPERVISAR, urls_de_emergencia
from programas.tests.test_emergencia_casos import JPEG, T0
from programas.tests.test_emergencia_kits import ADMITIR, RECIBIR_KIT, BaseKits
from programas.views.emergencia_kits import ENTREGAS_POR_PAGINA

Estado = EntregaKit.Estado

URL_ENTREGAS = "/emergencia/entregas/"
URL_NUEVA = "/emergencia/entregas/nueva/"

#: Las acciones POST de la mesa sobre una entrega y un cuerpo que su formulario acepta.
ACCIONES = {
    "entrega_en_camino": {"transporte": "", "hora": ""},
    "entrega_cancelar": {"motivo": "Se suspendió el envío"},
    "entrega_observar": {"texto": "Se reclamó al proveedor"},
    "entrega_aceptar_diferencia": {"motivo": "Lo cubre otro envío"},
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
            self._url("entrega_detalle", self.entrega.pk),
        ]
        self.posts = [self._url(nombre, self.entrega.pk) for nombre in ACCIONES] + [URL_NUEVA]

    def test_las_urls_son_las_del_namespace_emergencia(self):
        self.assertEqual(reverse("emergencia:entregas"), URL_ENTREGAS)
        self.assertEqual(reverse("emergencia:entrega_nueva"), URL_NUEVA)

    def test_el_barrido_del_modulo_cubre_las_rutas_de_kits(self):
        """El barrido de ``test_emergencia_base`` (rol de Becas, ciudadano) las prueba sin listarlas."""
        urls = urls_de_emergencia()
        self.assertIn(URL_ENTREGAS, urls)
        self.assertIn(URL_NUEVA, urls)
        for fragmento in ("/en-camino/", "/cancelar/", "/observar/", "/aceptar-diferencia/", "/kits/", "/recibir/"):
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
            {
                "Abiertas": 1,
                "Demoradas (más de 48 h)": 0,
                "Con diferencia sin cerrar": 1,
                "Recibidas": 0,
                "Canceladas": 0,
            },
        )
        self.assertTrue(chips["Con diferencia sin cerrar"]["activo"])
        self.assertEqual(chips["Abiertas"]["url"], f"{URL_ENTREGAS}?solapa=abiertas&dispositivo={self.club.pk}")
        self.assertContains(respuesta, "Recibida con diferencias")

    def test_una_demorada_lleva_su_chip_y_el_listado_avisa_con_un_enlace_a_la_solapa(self):
        """Mutación: ``es_demorada`` siempre falso deja en rojo el chip; sin ``_alerta_de_demoradas``, el aviso."""
        vieja, reciente = self._en_camino(), self._en_camino()
        EntregaKit.objects.filter(pk=vieja.pk).update(
            despachada_en=T0 - timedelta(hours=EntregaKit.HORAS_PARA_DEMORADA + 12)
        )
        rotulo = f"Demorada (más de {EntregaKit.HORAS_PARA_DEMORADA} h)"

        respuesta = self.client.get(URL_ENTREGAS)

        self.assertContains(respuesta, f'<span class="badge badge-warning">{rotulo}</span>', count=1)
        self.assertEqual(
            {fila["entrega"].pk: fila["demorada"] for fila in respuesta.context["filas"]},
            {vieja.pk: True, reciente.pk: False},
        )
        alerta = respuesta.context["alerta_demoradas"]
        self.assertEqual(
            alerta["titulo"],
            f"1 entrega lleva más de {EntregaKit.HORAS_PARA_DEMORADA} horas en camino sin recibirse",
        )
        self.assertEqual(alerta["url"], f"{URL_ENTREGAS}?solapa=demoradas")
        self.assertContains(respuesta, alerta["titulo"])
        # En la propia solapa de las demoradas el aviso sobra.
        self.assertIsNone(self.client.get(URL_ENTREGAS, {"solapa": "demoradas"}).context["alerta_demoradas"])

    def test_sin_demoradas_no_hay_aviso_ni_chip(self):
        self._en_camino()

        respuesta = self.client.get(URL_ENTREGAS)

        self.assertIsNone(respuesta.context["alerta_demoradas"])
        self.assertNotContains(respuesta, "Demorada (más de")

    def test_una_diferencia_sin_cerrar_lleva_su_chip_y_lo_pierde_al_cerrarse(self):
        original = self._recibida_con_faltante()

        abierta = self.client.get(URL_ENTREGAS, {"solapa": "con_diferencias"})
        self.assertContains(abierta, '<span class="badge badge-warning">Diferencia sin cerrar</span>', count=1)
        self.assertEqual(
            [accion["texto"] for accion in abierta.context["filas"][0]["acciones"]], ["Cerrar la diferencia"]
        )

        servicio.aceptar_diferencia(original, self.operador, "Lo cubre otro envío")
        cerrada = self.client.get(URL_ENTREGAS, {"solapa": "recibidas"})
        self.assertEqual([fila["entrega"] for fila in cerrada.context["filas"]], [original])
        self.assertNotContains(cerrada, "Diferencia sin cerrar</span>")

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
    """La pantalla única (Cambio 586): destino, «Le falta (estimado)», cantidades, salida y nota."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.operador)
        self.url_club = f"{URL_NUEVA}?dispositivo={self.club.pk}"

    def _crear(self, destino=None, salida="despues", **cantidades):
        datos = {
            "dispositivo": (destino or self.club).pk,
            "salida": salida,
            "observacion": "",
            **self._cantidades(**cantidades),
        }
        return self.client.post(URL_NUEVA, datos)

    def test_sin_destino_solo_pide_elegirlo(self):
        respuesta = self.client.get(URL_NUEVA)

        self.assertTemplateUsed(respuesta, "programas/emergencia/kits/nueva.html")
        self.assertIsNone(respuesta.context["destino"])
        self.assertContains(respuesta, "Elegir el destino")
        self.assertNotContains(respuesta, "Crear y enviar")

    def test_con_destino_muestra_la_columna_le_falta_y_el_formulario(self):
        TipoKit.objects.filter(pk=self.agua.pk).update(activo=False)

        respuesta = self.client.get(self.url_club)

        self.assertEqual(respuesta.context["destino"]["nombre"], "Club Sarmiento")
        self.assertEqual([fila["item"].nombre for fila in respuesta.context["filas"]], ["Colchón", "Kit alimentario"])
        texto = _texto(respuesta.content.decode())
        self.assertIn("Le falta (estimado)", texto)
        self.assertIn("Crear y enviar", texto)
        self.assertIn("Sale ahora: queda en camino", texto)
        self.assertIn("Todavía no sale: queda preparada", texto)
        self.assertContains(respuesta, 'name="salida"')

    def test_un_destino_que_no_esta_activo_muestra_el_error_del_campo_y_el_post_es_404(self):
        from programas.models import Dispositivo

        cerrado = self._dispositivo("Parroquia cerrada", estado=Dispositivo.Estado.CERRADO)

        respuesta = self.client.get(f"{URL_NUEVA}?dispositivo={cerrado.pk}")

        self.assertIsNone(respuesta.context["destino"])
        self.assertNotContains(respuesta, "Crear y enviar")
        self.assertEqual(self._crear(destino=cerrado, a=(self.colchon, 1)).status_code, 404)
        self.assertFalse(EntregaKit.objects.exists())

    def test_sin_catalogo_lo_dice_y_no_ofrece_el_formulario(self):
        TipoKit.objects.update(activo=False)

        respuesta = self.client.get(self.url_club)

        self.assertContains(respuesta, "El catálogo de kits no tiene ítems activos")
        self.assertNotContains(respuesta, "Crear y enviar")

    def test_una_cantidad_en_cero_no_crea(self):
        respuesta = self._crear(a=(self.colchon, 0), b=(self.alimentos, 3))

        self.assertEqual(respuesta.status_code, 400)
        self.assertTemplateUsed(respuesta, "programas/emergencia/kits/nueva.html")
        self.assertContains(respuesta, "Sacá el ítem o poné una cantidad", status_code=400)
        self.assertFalse(EntregaKit.objects.exists())

    def test_sin_ninguna_cantidad_no_crea(self):
        respuesta = self._crear()

        self.assertEqual(respuesta.status_code, 400)
        self.assertContains(respuesta, "La entrega necesita al menos un ítem con cantidad.", status_code=400)
        self.assertFalse(EntregaKit.objects.exists())

    def _edificios_del_club(self, cuantos):
        from programas.models import Edificio

        edificios = [Edificio.objects.create(codigo=f"EK-{n}", nombre=f"Edificio {n}") for n in range(cuantos)]
        for edificio in edificios:
            edificio.dispositivos.add(self.club)
        return edificios

    def test_con_varios_edificios_pide_elegir_y_la_entrega_sale_con_ese(self):
        _a, b = self._edificios_del_club(2)
        self.assertContains(self.client.get(self.url_club), 'name="edificio"')

        sin_elegir = self._crear(a=(self.colchon, 2))
        self.assertEqual(sin_elegir.status_code, 400)
        self.assertContains(sin_elegir, "Elegí el edificio al que va la entrega.", status_code=400)
        self.assertFalse(EntregaKit.objects.exists())

        self.client.post(
            URL_NUEVA,
            {
                "dispositivo": self.club.pk,
                "salida": "despues",
                "edificio": b.pk,
                **self._cantidades(a=(self.colchon, 2)),
            },
        )
        self.assertEqual(EntregaKit.objects.get().edificio_id, b.pk)

    def test_con_un_solo_edificio_no_se_pregunta_y_queda_fijo(self):
        (unico,) = self._edificios_del_club(1)
        self.assertNotContains(self.client.get(self.url_club), 'name="edificio"')

        self._crear(a=(self.colchon, 2))

        self.assertEqual(EntregaKit.objects.get().edificio_id, unico.pk)

    def test_todavia_no_sale_la_deja_preparada(self):
        datos = {
            "dispositivo": self.club.pk,
            "salida": "despues",
            "observacion": "Entregar a la directora.",
            **self._cantidades(a=(self.colchon, 10), b=(self.alimentos, 3)),
        }

        respuesta = self.client.post(URL_NUEVA, datos)

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
        self.assertEqual(
            list(TrazaEntrega.objects.filter(entrega=entrega).values_list("accion", flat=True)), ["CREADA"]
        )

    def test_sale_ahora_la_crea_y_la_marca_en_camino(self):
        respuesta = self._crear(salida="ahora", a=(self.colchon, 10))

        entrega = EntregaKit.objects.get()
        self.assertRedirects(respuesta, self._url("entrega_detalle", entrega.pk))
        self.assertEqual(entrega.estado, Estado.EN_CAMINO)
        self.assertEqual(entrega.despachada_en, T0)
        self.assertIn(f"Entrega {entrega.numero} enviada a Club Sarmiento. Está en camino.", self._avisos(respuesta)[0])
        self.assertEqual(
            list(TrazaEntrega.objects.filter(entrega=entrega).order_by("id").values_list("accion", flat=True)),
            ["CREADA", "EN_CAMINO"],
        )

    def test_si_no_se_puede_marcar_en_camino_no_queda_ninguna_entrega(self):
        """Crear y enviar es una sola transacción: si el segundo paso falla, el primero se deshace."""
        from django.core.exceptions import ValidationError

        with mock.patch("programas.services.kits.marcar_en_camino", side_effect=ValidationError("No se pudo.")):
            respuesta = self._crear(salida="ahora", a=(self.colchon, 10))

        self.assertEqual(respuesta.status_code, 400)
        self.assertContains(respuesta, "No se pudo.", status_code=400)
        self.assertFalse(EntregaKit.objects.exists())
        self.assertFalse(TrazaEntrega.objects.exists())

    def test_no_guarda_nada_en_la_sesion(self):
        """Dos pestañas, dos destinos: cada «Crear y enviar» escribe lo que trajo su formulario."""
        claves_antes = set(self.client.session.keys())
        self.client.get(self.url_club)
        self.client.get(f"{URL_NUEVA}?dispositivo={self.escuela.pk}")
        self.assertEqual(set(self.client.session.keys()), claves_antes)

        self._crear(a=(self.colchon, 10))
        self._crear(destino=self.escuela, a=(self.agua, 6))

        club = EntregaKit.objects.get(dispositivo=self.club)
        escuela = EntregaKit.objects.get(dispositivo=self.escuela)
        self.assertEqual(list(club.lineas.values_list("item__nombre", "cantidad_enviada")), [("Colchón", 10)])
        self.assertEqual(list(escuela.lineas.values_list("item__nombre", "cantidad_enviada")), [("Agua 6 l", 6)])

    def test_un_item_que_se_desactivo_mientras_se_armaba_no_se_descarta_en_silencio(self):
        datos = {
            "dispositivo": self.club.pk,
            "salida": "despues",
            **self._cantidades(a=(self.colchon, 10), b=(self.agua, 6)),
        }
        TipoKit.objects.filter(pk=self.agua.pk).update(activo=False)

        respuesta = self.client.post(URL_NUEVA, datos)

        self.assertEqual(respuesta.status_code, 400)
        self.assertContains(respuesta, "ya no está en el catálogo activo", status_code=400)
        self.assertFalse(EntregaKit.objects.exists())

    def test_cargar_lo_estimado_precarga_lo_que_le_falta(self):
        """La cuenta del faltante se prueba en ``test_emergencia_abastecimiento``; acá, que la pantalla la cargue."""
        from types import SimpleNamespace

        from programas.views.emergencia_kits import NuevaEntregaView

        estimado = {
            self.colchon.pk: SimpleNamespace(faltan=5, demoradas=0),
            self.alimentos.pk: SimpleNamespace(faltan=0, demoradas=2),
        }
        with mock.patch.object(NuevaEntregaView, "_estimado", return_value=(estimado, "")):
            sin_cargar = self.client.get(self.url_club)
            cargado = self.client.get(f"{self.url_club}&estimado=1")

        self.assertContains(sin_cargar, "Cargar lo estimado")
        self.assertNotContains(sin_cargar, f'name="cantidad_{self.colchon.pk}" value=')
        self.assertContains(cargado, f'name="cantidad_{self.colchon.pk}" value="5"')
        self.assertNotContains(cargado, f'name="cantidad_{self.alimentos.pk}" value=')
        self.assertContains(cargado, "2 demorados (más de 48 h)")

    def test_en_una_reposicion_no_se_ofrece_cargar_lo_estimado(self):
        """Con ``repone`` las cantidades arrancan con lo que faltó: el botón no haría nada. Mutación: quitar el
        ``original is None`` de ``hay_estimado`` en la vista deja en rojo este test."""
        from types import SimpleNamespace

        from programas.views.emergencia_kits import NuevaEntregaView

        recibida = self._recibir(self._en_camino(), {self.colchon.pk: 8, self.alimentos.pk: 3})
        estimado = {self.colchon.pk: SimpleNamespace(faltan=5, demoradas=0)}
        with mock.patch.object(NuevaEntregaView, "_estimado", return_value=(estimado, "")):
            repuesta = self.client.get(f"{self.url_club}&repone={recibida.pk}")
            comun = self.client.get(self.url_club)

        self.assertNotContains(repuesta, "Cargar lo estimado")
        self.assertContains(comun, "Cargar lo estimado")

    def test_reenviar_una_reposicion_ya_hecha_a_un_destino_con_dos_edificios_devuelve_la_del_primer_envio(self):
        """El segundo POST del mismo armado ya no encuentra la diferencia abierta: los edificios se deciden con la entrega
        que nombra ``repone_a`` y no vuelve un «Elegí el edificio». Mutación: usar solo la diferencia abierta en el POST
        deja este test en rojo (400)."""
        import uuid

        from programas.models import Edificio

        edificios = [Edificio.objects.create(codigo=f"RE-{n}", nombre=f"Edificio {n}") for n in (1, 2)]
        for edificio in edificios:
            edificio.dispositivos.add(self.club)
        original = self._recibir(self._en_camino(edificio=edificios[0]), {self.colchon.pk: 8, self.alimentos.pk: 3})
        cuerpo = {
            "dispositivo": self.club.pk,
            "repone_a": original.pk,
            "uuid_cliente": str(uuid.uuid4()),
            "salida": "despues",
            "observacion": "",
            **self._cantidades(colchon=(self.colchon, 2)),
        }

        primero = self.client.post(URL_NUEVA, cuerpo)
        segundo = self.client.post(URL_NUEVA, cuerpo)

        self.assertEqual((primero.status_code, segundo.status_code), (302, 302))
        self.assertEqual(primero.url, segundo.url)
        self.assertEqual(EntregaKit.objects.filter(repone_a=original).count(), 1)

    def test_reponer_arranca_con_lo_que_falto(self):
        recibida = self._recibir(self._en_camino(), {self.colchon.pk: 8, self.alimentos.pk: 4})

        respuesta = self.client.get(f"{self.url_club}&repone={recibida.pk}")

        self.assertContains(respuesta, f"Repone a la entrega {recibida.numero}")
        self.assertContains(respuesta, f'name="cantidad_{self.colchon.pk}" value="2"')
        self.assertContains(respuesta, f'name="repone_a" value="{recibida.pk}"')
        self.assertEqual(respuesta.context["sin_item_activo_texto"], "")

    def test_reponer_avisa_de_los_items_inactivos_con_faltante(self):
        recibida = self._recibir(self._en_camino(), {self.colchon.pk: 8, self.alimentos.pk: 5})
        TipoKit.objects.filter(pk=self.colchon.pk).update(activo=False)

        respuesta = self.client.get(f"{self.url_club}&repone={recibida.pk}")

        self.assertEqual(respuesta.context["sin_item_activo_texto"], "Colchón (2)")
        self.assertContains(respuesta, "Hay ítems que no se pueden reponer")

    def test_la_url_del_paso_2_viejo_redirige_a_la_pantalla_unica(self):
        respuesta = self.client.get(f"{self._url('entrega_nueva_items', self.club.pk)}?repone=7")

        self.assertRedirects(
            respuesta, f"{URL_NUEVA}?dispositivo={self.club.pk}&repone=7", fetch_redirect_response=False
        )
        self.assertFalse(EntregaKit.objects.exists())


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
        self.assertNotIn("cerrar_diferencia", respuesta.context)
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
        self.assertEqual(
            respuesta.context["cerrar_diferencia"]["url_reponer"],
            f"{URL_NUEVA}?dispositivo={self.club.pk}&repone={recibida.pk}",
        )
        self.assertIn("Qué hacer ahora: cerrar la diferencia", texto)
        self.assertIn("Reponer lo que faltó", texto)
        self.assertIn("Aceptar la diferencia", texto)
        self.assertIn("Sin cerrar", texto)
        self.assertFalse(respuesta.context["puede_cancelar"])
        self.assertIn("form_observar", respuesta.context)

    def test_una_recibida_completa_no_ofrece_cerrar_nada(self):
        respuesta = self._detalle(self._recibir(self._en_camino()))

        self.assertNotIn("cerrar_diferencia", respuesta.context)
        self.assertIn("sin diferencia", _texto(respuesta.content.decode()))

    def test_solo_de_mas_no_ofrece_reponer_pero_si_aceptar(self):
        """Reponer precarga lo que faltó: si solo llegó de más, no hay nada que reponer."""
        recibida = self._recibir(self._en_camino(), {self.colchon.pk: 10, self.alimentos.pk: 5})

        respuesta = self._detalle(recibida)

        self.assertEqual(respuesta.context["cerrar_diferencia"]["url_reponer"], "")
        self.assertIn("form_aceptar", respuesta.context)

    def test_aceptar_la_diferencia_pide_el_motivo_y_la_cierra(self):
        recibida = self._recibida_con_faltante()
        url = self._url("entrega_aceptar_diferencia", recibida.pk)

        sin_motivo = self.client.post(url, {"motivo": "  "})
        self.assertRedirects(sin_motivo, self._url("entrega_detalle", recibida.pk))
        self.assertIsNone(EntregaKit.objects.get(pk=recibida.pk).cierre_diferencia)

        con_motivo = self.client.post(url, {"motivo": "Lo cubre otro envío"})
        self.assertIn("aceptada", self._avisos(con_motivo)[0])
        cerrada = EntregaKit.objects.get(pk=recibida.pk)
        self.assertEqual(
            (cerrada.cierre_diferencia, cerrada.cierre_diferencia_motivo, cerrada.cierre_diferencia_por),
            (EntregaKit.CierreDiferencia.ACEPTADA, "Lo cubre otro envío", self.operador),
        )
        respuesta = self._detalle(recibida)
        self.assertNotIn("cerrar_diferencia", respuesta.context)
        self.assertIn("Aceptada: Lo cubre otro envío", _texto(respuesta.content.decode()))
        # Ya cerrada, la pantalla de «Nueva entrega» no ofrece reponerla.
        reponer = self.client.get(f"{URL_NUEVA}?dispositivo={self.club.pk}&repone={recibida.pk}")
        self.assertIsNone(reponer.context["repone_a"])

    def test_marcar_en_camino_desde_el_detalle(self):
        self.reloj.ahora = T0 - timedelta(hours=2)
        entrega = self._entrega()
        self.reloj.ahora = T0

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
        self.assertEqual(acciones, {"1", "en-camino", "cancelar", "observar", "aceptar-diferencia"})


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

        # 1. La mesa arma la entrega en una sola pantalla y queda preparada.
        cliente = mesa
        self.assertContains(cliente.get(f"{URL_NUEVA}?dispositivo={self.club.pk}"), "Le falta (estimado)")
        cantidades = self._cantidades(a=(self.colchon, 10), b=(self.alimentos, 3))
        cliente.post(
            URL_NUEVA,
            {
                **cantidades,
                "dispositivo": self.club.pk,
                "salida": "despues",
                "observacion": "Para la guardia de la tarde.",
            },
        )
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
        self.assertContains(con_diferencias, "Con diferencia sin cerrar")
        self.assertEqual([fila["entrega"] for fila in con_diferencias.context["filas"]], [recibida])
        detalle = cliente.get(self._url("entrega_detalle", recibida.pk))
        texto = _texto(detalle.content.decode())
        self.assertIn("−2 · faltan", texto)
        self.assertIn("Faltaron dos colchones.", texto)
        self.assertEqual(cliente.get(f"/media/{recibida.remito.name}").status_code, 200)

        # 5. Reponer: el paso 2 arranca con lo que faltó y la entrega nueva guarda a quién repone.
        pantalla = cliente.get(detalle.context["cerrar_diferencia"]["url_reponer"])
        self.assertContains(pantalla, f'name="cantidad_{self.colchon.pk}" value="2"')
        self.assertNotContains(pantalla, f'name="cantidad_{self.alimentos.pk}" value=')
        self.assertContains(pantalla, f'name="repone_a" value="{recibida.pk}"')
        self.assertContains(pantalla, f"Repone a la entrega {recibida.numero}")
        reposicion_datos = {
            **self._cantidades(a=(self.colchon, 2)),
            "repone_a": str(recibida.pk),
            "dispositivo": self.club.pk,
            "salida": "ahora",
        }
        cliente.post(URL_NUEVA, reposicion_datos)

        reposicion = EntregaKit.objects.exclude(pk=recibida.pk).get()
        self.assertEqual((reposicion.repone_a, reposicion.estado), (recibida, Estado.EN_CAMINO))
        # Repuesta una sola vez: la original quedó cerrada y ya no ofrece reponer.
        self.assertEqual(EntregaKit.objects.get(pk=recibida.pk).cierre_diferencia, EntregaKit.CierreDiferencia.REPUESTA)
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
            ["CREADA", "EN_CAMINO", "RECIBIDA", "DIFERENCIA_REPUESTA"],
        )
