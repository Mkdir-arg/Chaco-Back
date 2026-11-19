"""E8 · la pantalla «Situación» y la capacidad ``emergencia.ver_situacion`` (Cambio 509 · E-5 #1184).

* **Permisos** — con ``ver_situacion`` o ``supervisar`` 200; sin capacidad, con solo ``operar`` o con
  el rol desactivado, 403; sin sesión, al login; el ciudadano, al portal (TC-1184-01 a 03, TC-1182-*).
* **Enlaces a la mesa** solo con ``supervisar`` (TC-1184-04 a 06).
* **No nominal** (TC-1184-07): ni apellidos, ni DNI, ni direcciones, ni números de caso, ni
  coordenadas de familias en la respuesta.
* **Filtros** por GET (TC-1184-22 a 26, 37, 40) y **perfil** con salud solo provincial (TC-1184-28).
* **Sidebar** (TC-1182-02, 05 a 08) y la **migración** que se la da al Administrador (TC-1182-12, 13).
* **Presupuesto** de la vista (``--tag performance``, TC-1184-39): ≤ 21 como A y como S.

Todas las personas usan DNIs de prueba (90000001–90000099).
"""

import importlib
import json
import re
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.test import SimpleTestCase, TestCase, tag
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from core import rbac
from core.tests.historico import estado_historico
from programas.forms_emergencia_situacion import FiltrosSituacionForm
from programas.models import CasoEmergencia
from programas.services.emergencia_programa import CAP_VER_SITUACION, puede_ver_situacion
from programas.tests.test_emergencia_base import OPERAR, urls_de_emergencia
from programas.tests.test_emergencia_situacion import BancoSituacion, BaseSituacion, EscenarioSituacion
from users.models import Capacidad, RolMeta

VER_SITUACION = "emergencia.ver_situacion"
URL = "/emergencia/situacion/"
PRESUPUESTOS = Path(settings.BASE_DIR) / "scripts" / "perf_budgets.json"
CLAVE_PRESUPUESTO = "emergencia_situacion_vista"

#: Lo que no puede viajar a una pantalla de autoridades sin la capacidad de la mesa.
ENLACES_DE_LA_MESA = ("/emergencia/casos/", "/emergencia/tablero/", "/emergencia/entregas/", "Ir al tablero de la mesa")


class CatalogoVerSituacionTests(SimpleTestCase):
    def test_esta_en_el_modulo_emergencia_con_su_descripcion(self):
        modulo = next(m for m in rbac.CATALOGO if m["modulo"] == "emergencia")
        self.assertIn(
            (VER_SITUACION, "Ver la situación de la emergencia (tablero estratégico y mapa, sin datos personales)"),
            modulo["capacidades"],
        )
        self.assertEqual(CAP_VER_SITUACION, VER_SITUACION)

    def test_es_de_programa_y_se_tilda_solo_en_un_rol_de_emergencia(self):
        self.assertIn(VER_SITUACION, rbac.codigos_de_programa())
        self.assertIn(VER_SITUACION, rbac.capacidades_de_programa_asignables("EMERGENCIA"))
        self.assertNotIn(VER_SITUACION, rbac.capacidades_de_programa_asignables("BECAS"))

    def test_aparece_en_el_arbol_del_abm_de_roles(self):
        """TC-1182-01."""
        arbol = rbac.arbol_por_tabs(solo_programa=True, programa="EMERGENCIA")
        codigos = {
            capacidad["codigo"] if isinstance(capacidad, dict) else capacidad[0]
            for tab in arbol
            for modulo in tab["modulos"]
            for capacidad in modulo.get("capacidades", [])
        }
        self.assertIn(VER_SITUACION, codigos)

    def test_no_es_de_campo(self):
        self.assertNotIn(VER_SITUACION, rbac.CAPACIDADES_DE_CAMPO)


class BaseVista(EscenarioSituacion):
    def setUp(self):
        super().setUp()
        self.autoridad = self._usuario("autoridad", [VER_SITUACION])

    def _get(self, usuario, url=URL):
        self.client.force_login(usuario)
        return self.client.get(url)

    def _html(self, usuario, url=URL):
        respuesta = self._get(usuario, url)
        self.assertEqual(respuesta.status_code, 200)
        return respuesta.content.decode()


class PermisosTests(BaseVista):
    def test_la_url_es_la_del_namespace_y_entra_al_barrido(self):
        self.assertEqual(reverse("emergencia:situacion"), URL)
        self.assertIn(URL, urls_de_emergencia())

    def test_sin_login_va_al_login(self):
        respuesta = self.client.get(URL)
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(f"?next={URL}", respuesta["Location"])

    def test_tc_1184_01_con_ver_situacion_200(self):
        html = self._html(self.autoridad)
        self.assertIn('<h1 class="nodo-hero__titulo">', html)
        self.assertEqual(html.count("nodo-stat-tablero "), 4)
        for solapa in ("tab-resumen", "tab-mapa", "tab-abastecimiento"):
            self.assertIn(f'id="{solapa}"', html)

    def test_tc_1184_02_sin_capacidad_y_con_solo_operar_403(self):
        self.assertEqual(self._get(self._usuario("nadie")).status_code, 403)
        self.assertEqual(self._get(self.operador).status_code, 403)

    def test_tc_1184_02_el_ciudadano_va_al_portal(self):
        ciudadano = self._usuario("ciudadano", [VER_SITUACION])
        ciudadano.groups.add(Group.objects.get_or_create(name=rbac.GRUPO_CIUDADANO_PORTAL)[0])
        respuesta = self._get(User.objects.get(pk=ciudadano.pk))
        self.assertRedirects(respuesta, reverse("portal:home"), fetch_redirect_response=False)

    def test_tc_1184_03_supervisar_y_superusuario_200(self):
        self.assertEqual(self._get(self.supervisor).status_code, 200)
        root = User.objects.create_superuser("root", "root@example.com", "x")
        self.assertEqual(self._get(root).status_code, 200)

    def test_tc_1184_03_con_el_rol_desactivado_403(self):
        RolMeta.objects.filter(grupo__in=self.autoridad.groups.all()).update(activo=False)
        self.assertEqual(self._get(User.objects.get(pk=self.autoridad.pk)).status_code, 403)

    def test_en_un_rol_de_otro_programa_no_alcanza(self):
        colado = self._usuario("colado", [VER_SITUACION], programa=self.becas)
        self.assertEqual(self._get(colado).status_code, 403)

    def test_supervisar_implica_ver_la_situacion_y_operar_no(self):
        self.assertTrue(puede_ver_situacion(self.autoridad))
        self.assertTrue(puede_ver_situacion(self.supervisor))
        self.assertFalse(puede_ver_situacion(self.operador))

    def test_tc_1182_03_la_autoridad_no_abre_la_mesa(self):
        self.client.force_login(self.autoridad)
        for url in ("/emergencia/casos/", "/emergencia/entregas/", "/emergencia/tablero/", "/emergencia/config/"):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)


class EnlacesTests(BaseVista):
    def test_tc_1184_04_la_autoridad_no_ve_enlaces_a_la_mesa(self):
        html = self._html(self.autoridad)
        for enlace in (*ENLACES_DE_LA_MESA, "Ver los avisos operativos"):
            with self.subTest(enlace=enlace):
                self.assertNotIn(enlace, html)

    def test_tc_1184_05_el_supervisor_ve_los_enlaces_sin_cifra(self):
        html = self._html(self.supervisor)
        self.assertIn("Ir al tablero de la mesa", html)
        self.assertIn("Ver los avisos operativos en el tablero de la mesa →</a>", html)
        self.assertIn(f'href="/emergencia/casos/?localidad={self.res.pk}"', html)

    def test_tc_1184_06_e1_enlaza_a_e8(self):
        self.assertIn(f'href="{URL}"', self._html(self.supervisor, "/emergencia/tablero/"))


class NoNominalTests(BaseVista):
    def test_tc_1184_07_ni_apellidos_ni_dni_ni_direcciones_ni_numeros_de_caso_ni_coordenadas(self):
        html = self._html(self.supervisor)
        prohibidos = ["Benítez", "Av. Sarmiento 1200", "-27.4111", "-27,4111", "-58.9222"]
        prohibidos += list(CasoEmergencia.objects.values_list("numero", flat=True))
        prohibidos += [str(dni) for dni in range(90_000_001, 90_000_031)]
        for dato in prohibidos:
            with self.subTest(dato=dato):
                self.assertNotIn(dato, html)

    def test_el_dispositivo_reservado_no_se_nombra(self):
        self.assertNotIn("Refugio", self._html(self.supervisor))


class FiltrosTests(BaseVista):
    def test_tc_1184_40_sin_ventana_es_72_h(self):
        html = self._html(self.autoridad)
        self.assertIn('<option value="">72 h</option>', html)
        self.assertIn("Evolución por bloques de 6 h", html)

    def test_7_dias_por_dia_operativo(self):
        html = self._html(self.autoridad, f"{URL}?ventana=7d")
        self.assertIn('<option value="7d" selected>7 días</option>', html)
        self.assertIn("Evolución por día operativo", html)

    def test_tc_1184_26_parametros_invalidos_no_rompen(self):
        respuesta = self._get(self.autoridad, f"{URL}?ventana=abc&departamento=zzz&localidad=999999&tab=xx")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context["solapa"], "resumen")
        self.assertIn("Toda la provincia · últimas 72 h", respuesta.content.decode())

    def test_tc_1184_37_deep_link_a_una_solapa(self):
        html = self._html(self.autoridad, f"{URL}?tab=mapa")
        self.assertIn('x-show="tab===\'mapa\'" role="tabpanel"', html)
        self.assertIn("x-show=\"tab==='resumen'\" x-cloak", html)

    def test_tc_1184_35_el_resumen_se_dibuja_sin_x_cloak(self):
        self.assertIn('x-show="tab===\'resumen\'" role="tabpanel"', self._html(self.autoridad))

    def test_tc_1184_22_el_departamento_acota_la_demanda_y_no_la_capacidad(self):
        html = self._html(self.autoridad, f"{URL}?departamento=San+Fernando")
        self.assertIn("Departamento San Fernando · últimas 72 h", html)
        self.assertIn("Red provincial · ", html)
        self.assertNotIn(">Las Breñas<", html)

    def test_tc_1184_24_localidad_de_otro_departamento_se_ignora_y_avisa(self):
        html = self._html(self.autoridad, f"{URL}?departamento=San+Fernando&localidad={self.bre.pk}")
        self.assertIn("La localidad elegida no es de ese departamento", html)

    def test_tc_1184_24_la_lista_de_localidades_sigue_al_departamento(self):
        html = self._html(self.autoridad, f"{URL}?departamento=San+Fernando")
        self.assertIn(f'<option value="{self.res.pk}">Resistencia</option>', html)
        self.assertNotIn(f'<option value="{self.bre.pk}">', html)

    def test_tc_1184_28_perfil_con_filtro_sin_salud(self):
        html = self._html(self.supervisor, f"{URL}?localidad={self.res.pk}")
        self.assertIn("Los datos de salud se muestran solo para toda la provincia.", html)
        self.assertNotIn('<dt class="text-body">Medicación crítica sin dosis</dt>', html)
        self.assertIn("menos de 5", html)
        sin_filtro = self._html(self.supervisor)
        self.assertIn('<dt class="text-body">Medicación crítica sin dosis</dt>', sin_filtro)

    def test_tc_1184_25_filtro_que_vacia_la_demanda(self):
        vacia = self._loc("Puerto Vacío", -27.2, -59.1, "San Fernando")
        html = self._html(self.autoridad, f"{URL}?localidad={vacia.pk}")
        self.assertIn("Sin demanda con estos filtros", html)
        self.assertIn(f'href="{URL}" class="btn-nodo btn-tertiary btn-base mt-2">Limpiar filtros', html)

    def test_el_form_ignora_cada_campo_invalido_por_separado(self):
        form = FiltrosSituacionForm({"ventana": "7d", "tab": "nada", "localidad": "x"})
        self.assertEqual((form.ventana_elegida, form.solapa), ("7d", "resumen"))


class ContenidoTests(BaseVista):
    def test_bloques_del_resumen(self):
        html = self._html(self.supervisor)
        for titulo in (
            "Necesita atención",
            "Presión por localidad",
            "Evolución",
            "Capacidad de la red",
            "Embudo del circuito",
            "Perfil de las personas",
            "Logística de kits",
            "Cómo se calcula",
            "Documento de trabajo · datos agregados, sin datos personales",
        ):
            with self.subTest(titulo=titulo):
                self.assertIn(titulo, html)
        self.assertIn("Red provincial: camas de los dispositivos elegibles", html)

    def test_tc_1184_36_mapa_vacio_y_abastecimiento_a_pedido(self):
        html = self._html(self.autoridad)
        self.assertIn("El mapa todavía no está disponible", html)
        self.assertIn("El abastecimiento se calcula cuando lo pedís", html)
        self.assertNotIn("leaflet", html.lower())


class SinCasosTests(BaseSituacion):
    def test_tc_1184_31_programa_vacio(self):
        self.client.force_login(self._usuario("autoridad", [VER_SITUACION]))
        respuesta = self.client.get(URL)
        self.assertEqual(respuesta.status_code, 200)
        html = respuesta.content.decode()
        self.assertIn("Todavía no hay casos", html)
        self.assertIn("—", html)


class SidebarTests(BaseVista):
    def test_tc_1182_02_la_autoridad_ve_solo_situacion(self):
        html = self._html(self.autoridad)
        self.assertIn(f'href="{URL}"', html)
        self.assertNotIn('href="/emergencia/casos/"', html)
        self.assertNotIn('href="/emergencia/config/"', html)

    def test_tc_1184_38_situacion_es_la_pagina_actual(self):
        html = self._html(self.supervisor)
        self.assertIn(f'href="{URL}"\n                           class="flex items-center gap-2', html)
        situacion = html.split(f'href="{URL}"', 1)[1].split("</a>", 1)[0]
        self.assertIn('aria-current="page"', situacion)
        tablero = html.split('href="/emergencia/tablero/"', 1)[1].split("</a>", 1)[0]
        self.assertNotIn('aria-current="page"', tablero)

    def test_tc_1182_07_operar_solo_no_ve_situacion(self):
        html = self._html(self.operador, "/emergencia/casos/")
        self.assertNotIn(f'href="{URL}"', html)

    def test_tc_1182_08_las_capacidades_se_unen(self):
        mixto = self._usuario("mixto", [VER_SITUACION, OPERAR])
        html = self._html(mixto)
        self.assertIn('href="/emergencia/casos/"', html)
        self.assertIn('href="/emergencia/entregas/"', html)
        self.assertNotIn('href="/emergencia/config/"', html)


class MigracionVerSituacionTests(TestCase):
    """``users.0051``: declara la capacidad y se la da solo al Administrador (TC-1182-12, 13)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.migracion = importlib.import_module("users.migrations.0051_capacidad_ver_situacion")
        cls.apps_de_entonces = estado_historico("users", "0051_capacidad_ver_situacion", al_final=True)

    def _administrador(self):
        grupo = Group.objects.create(name=rbac.ROL_ADMINISTRADOR)
        RolMeta.objects.create(
            grupo=grupo,
            categoria=rbac.CATEGORIA_BACKOFFICE,
            protegido=True,
            activo=True,
            clave=self.migracion.CLAVE_ADMINISTRADOR,
        )
        tipo = ContentType.objects.get_for_model(Capacidad)
        grupo.permissions.add(*Permission.objects.filter(content_type=tipo, codename="dispositivo_ver"))
        return grupo

    def _codenames(self, grupo):
        return set(grupo.permissions.values_list("codename", flat=True))

    def test_el_codename_y_la_etiqueta_son_los_del_catalogo(self):
        catalogo = dict(rbac.todas_las_capacidades())
        for codename, nombre in self.migracion.CAPACIDADES:
            self.assertEqual(catalogo.get(codename), nombre)
        self.assertEqual({c for c, _ in self.migracion.CAPACIDADES}, {rbac.codename_de(VER_SITUACION)})

    def test_el_administrador_la_recibe_y_ningun_otro_rol(self):
        admin = self._administrador()
        otro = Group.objects.create(name="Supervisor de la mesa")
        self.migracion.sembrar(self.apps_de_entonces, None)
        self.migracion.sembrar(self.apps_de_entonces, None)
        self.assertEqual(self._codenames(admin), {"dispositivo_ver", "emergencia_ver_situacion"})
        self.assertEqual(self._codenames(otro), set())

    def test_la_reversa_se_la_saca_y_conserva_lo_demas(self):
        admin = self._administrador()
        self.migracion.sembrar(self.apps_de_entonces, None)
        self.migracion.quitar(self.apps_de_entonces, None)
        self.assertEqual(self._codenames(admin), {"dispositivo_ver"})

    def test_sin_administrador_no_hace_nada(self):
        self.migracion.sembrar(self.apps_de_entonces, None)
        self.migracion.quitar(self.apps_de_entonces, None)
        self.assertFalse(Group.objects.filter(name=rbac.ROL_ADMINISTRADOR).exists())


@tag("performance")
class PresupuestoVistaTests(BancoSituacion):
    """TC-1184-39: la vista entera con 5.000 casos, 3.000 alojados, 50 dispositivos y 500 entregas."""

    def _techo(self):
        return json.loads(PRESUPUESTOS.read_text(encoding="utf-8"))["servicios"][CLAVE_PRESUPUESTO]["consultas_fijas"]

    def _medir(self, usuario, url=URL):
        self.client.force_login(usuario)
        self.client.get(url)  # calienta la caché de proceso del programa
        with CaptureQueriesContext(connection) as capturadas:
            respuesta = self.client.get(url)
        self.assertEqual(respuesta.status_code, 200)
        return capturadas

    def test_como_autoridad_y_como_supervisor(self):
        techo = self._techo()
        self.assertLessEqual(techo, 21)
        autoridad = self._usuario("autoridad", [VER_SITUACION])
        # El superusuario abre todos los dispositivos y paga la consulta de «Ver dispositivo», pero no lee sus
        # capacidades (bypass): también 18.
        root = User.objects.create_superuser("root", "root@example.com", "x")
        for usuario, url in (
            (autoridad, URL),
            (root, URL),
            (self.supervisor, URL),
            (self.supervisor, f"{URL}?departamento=San+Fernando&ventana=7d&tab=mapa"),
        ):
            with self.subTest(usuario=usuario.username, url=url):
                capturadas = self._medir(usuario, url)
                self.assertLessEqual(len(capturadas), techo, [q["sql"][:140] for q in capturadas.captured_queries])


class PaginacionYImpresionTests(BaseVista):
    """TC-1184-17 y la parte estructural de TC-1184-33/34 (la vista previa real queda manual)."""

    def _paginando(self):
        """De a una fila desde la primera: así dos localidades ya son dos páginas."""
        return mock.patch.multiple("programas.views.emergencia_situacion", PAGINAR_DESDE=1, FILAS_POR_PAGINA=1)

    def _paginada(self, url):
        with self._paginando():
            return self._html(self.autoridad, url)

    @staticmethod
    def _tabla_de_pantalla(html):
        return html.split('<div class="overflow-x-auto nodo-no-imprimir">', 1)[1].split("</table>", 1)[0]

    def test_tc_1184_17_pagina_y_conserva_los_filtros_y_la_solapa(self):
        with self._paginando():
            html = self._html(self.autoridad, f"{URL}?departamento=San+Fernando")
            pagina_2 = self._get(self.autoridad, f"{URL}?departamento=San+Fernando&localidades_page=2")
        self.assertIn("localidades_page=2", html)
        enlace = re.search(r'href="([^"]*localidades_page=2[^"]*)"', html).group(1)
        self.assertIn("departamento=San+Fernando", enlace)
        self.assertIn("tab=resumen", enlace)
        self.assertEqual(pagina_2.status_code, 200)
        filas = pagina_2.context["presion"]["filas"]
        primera, segunda = filas[0]["localidad"], filas[1]["localidad"]
        pantalla = self._tabla_de_pantalla(pagina_2.content.decode())
        self.assertIn(segunda, pantalla)
        self.assertNotIn(primera, pantalla)

    def test_paginada_en_el_papel_va_la_tabla_entera_con_encabezado_y_total(self):
        html = self._paginada(URL)
        self.assertIn('<div class="overflow-x-auto nodo-no-imprimir">', html)
        papel = html.split('<div class="nodo-solo-impresion">', 1)[1].split("</table>", 1)[0]
        self.assertIn('scope="col">Localidad</th>', papel)
        self.assertIn(">Total</td>", papel)
        for localidad in ("Resistencia", "Barranqueras", "Las Breñas"):
            with self.subTest(localidad=localidad):
                self.assertIn(localidad, papel)

    def test_sin_paginar_la_tabla_de_pantalla_se_imprime(self):
        html = self._html(self.autoridad)
        self.assertNotIn("overflow-x-auto nodo-no-imprimir", html)
        self.assertNotIn('<div class="nodo-solo-impresion">', html)
        self.assertNotIn("localidades_page=", html)

    def test_que_sale_en_el_papel_y_que_no(self):
        html = self._html(self.autoridad, f"{URL}?tab=abastecimiento")
        self.assertIn("custom/css/nodo-impresion.css", html)
        self.assertRegex(html, r'id="panel-resumen" aria-labelledby="tab-resumen" class="nodo-impresion-panel')
        self.assertIn('id="panel-mapa" aria-labelledby="tab-mapa" class="nodo-no-imprimir"', html)
        self.assertIn('id="panel-abastecimiento" aria-labelledby="tab-abastecimiento" class="nodo-no-imprimir', html)
        self.assertIn('<div class="nodo-no-imprimir space-y-2">', html)
        self.assertIn('<div class="nodo-no-imprimir bg-white rounded-xl', html)
        self.assertIn('<details class="nodo-impresion-desplegar', html)
        self.assertIn('<p class="nodo-solo-impresion text-sm font-semibold text-heading">Toda la provincia', html)
        self.assertIn('<p class="nodo-solo-impresion text-xs text-body-subtle">Documento de trabajo', html)
        # «Actualizar» toma la solapa visible al hacer clic, como «Limpiar».
        self.assertIn("u.searchParams.set('tab', tab)", html)


def _emergencia_colapsado(html):
    """El link del grupo Emergencia con el sidebar colapsado (se arma en el servidor, dentro del template)."""

    fin = html.index('title="Emergencia"')
    inicio = html.rindex('<template x-if="sidebarCollapsed">', 0, fin)
    return re.search(r'href="([^"]+)"', html[inicio:fin]).group(1)


class SidebarColapsadoTests(BaseVista):
    def test_tc_1182_05_con_solo_ver_situacion_lleva_a_la_situacion(self):
        self.assertEqual(_emergencia_colapsado(self._html(self.autoridad)), URL)

    def test_quien_opera_va_a_la_bandeja(self):
        self.assertEqual(_emergencia_colapsado(self._html(self.supervisor)), "/emergencia/casos/")
        self.assertEqual(_emergencia_colapsado(self._html(self.operador, "/emergencia/casos/")), "/emergencia/casos/")
