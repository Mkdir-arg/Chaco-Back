"""Ola 5 · PR 7 — FE-22, FE-16, V5A-NEW-04, G2-06 y V5A-NEW-07 (b).

Todas las fichas comparten el mismo síntoma: la pantalla **dice** algo que el
código no sostiene. Un KPI que quedó sin anotación y sale vacío (FE-16), un
botón que promete una función que no existe (FE-22), una bajada que nombra la
librería que se usó para maquetar (V5A-NEW-04), un rótulo que pide un correo
cuando el backend autentica por `username` (G2-06) y seis `<label>` que no
apuntan a ningún control (V5A-NEW-07 b).

Son assertions sobre el template porque el defecto está en el template: lo que
se verifica es que el texto o la estructura que mentía ya no esté, y que en su
lugar esté la pieza canónica. Lo de comportamiento (contadores del inicio) va
en `core.tests.test_inicio_contadores_ola5`.
"""

from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

REPO = Path(settings.BASE_DIR)


def _leer(ruta_relativa):
    return (REPO / ruta_relativa).read_text(encoding="utf-8")


LOGIN = "users/templates/user/login.html"
REPORTES = "legajos/templates/legajos/reportes.html"
ALERTAS_DASHBOARD = "templates/legajos/alertas_dashboard.html"
DASHBOARD_CONTACTOS = "legajos/templates/legajos/dashboard_contactos_simple.html"
PROGRAMAS_LEGAJOS = "legajos/templates/legajos/programas/programa_list.html"
CIUDADANO_EDIT = "legajos/templates/legajos/ciudadano_edit_form.html"
INICIO = "templates/inicio.html"
CONVOCATORIA_LIST = "programas/templates/programas/becas/relevamientos/convocatoria_list.html"
DASHBOARD_PANEL = "programas/templates/programas/becas/config/_dashboard_panel.html"


class LoginRotuladoPorUsuarioTests(SimpleTestCase):
    """G2-06 · el login autentica por `username` con el `ModelBackend` de Django.

    No hay `AUTHENTICATION_BACKENDS` propio y el ABM crea el usuario con un
    nombre libre, así que pedir «tu correo electrónico» manda a escribir algo
    que el backend no va a encontrar.
    """

    def test_el_campo_se_rotula_usuario(self):
        html = _leer(LOGIN)

        self.assertNotIn("Tu correo electrónico", html)
        self.assertIn(">Tu usuario *<", html)

    def test_el_placeholder_no_pide_un_correo(self):
        html = _leer(LOGIN)

        self.assertNotIn("Ingresá tu correo electrónico", html)
        self.assertIn('placeholder="Ingresá tu usuario"', html)

    def test_el_error_de_credenciales_no_habla_de_correo(self):
        from users.forms.auth import UsuariosAuthenticationForm

        mensaje = UsuariosAuthenticationForm.error_messages["invalid_login"]

        self.assertNotIn("correo", mensaje)
        self.assertIn("usuario", mensaje)


class ReportesDeLegajosTests(SimpleTestCase):
    """FE-22 · `/legajos/reportes/` es una pantalla viva (capacidad `reporte.ver`)."""

    def test_no_ofrece_botones_de_funciones_que_no_existen(self):
        html = _leer(REPORTES)

        self.assertNotIn("Próximamente", html)

    def test_las_metricas_usan_la_stat_card_canonica(self):
        html = _leer(REPORTES)

        self.assertEqual(html.count('{% include "components/_stat_card.html"'), 4)

    def test_el_encabezado_es_el_canonico(self):
        html = _leer(REPORTES)

        self.assertIn("{% page_header", html)
        self.assertNotIn("<h1", html)

    def test_no_quedan_metricas_de_calidad_en_cero_fijo(self):
        """Los cinco porcentajes salían del diccionario `metricas_calidad`, que la
        vista arma con ceros literales: la pantalla afirmaba «0 % de adherencia»."""
        html = _leer(REPORTES)

        self.assertNotIn("metricas_calidad", html)

    def test_la_vista_dejo_de_armar_el_diccionario_vacio(self):
        vista = _leer("legajos/views/dashboard_simple.py")

        self.assertNotIn("metricas_calidad", vista)

    def test_no_queda_paleta_cruda_de_tailwind(self):
        html = _leer(REPORTES)

        for clase in ("bg-blue-500", "bg-green-500", "bg-orange-500", "bg-purple-500", "text-gray-900"):
            self.assertNotIn(clase, html, f"{REPORTES} todavía usa {clase}")


class EstadoWebsocketTests(SimpleTestCase):
    """FE-22 · el semáforo de WebSocket miente cuando los WebSockets están apagados.

    Con `APP_RUNTIME=runserver` las rutas `ws/` responden 426 y el punto queda
    gris para siempre: un indicador permanentemente apagado se lee como «el
    sistema está caído».
    """

    def test_el_semaforo_vive_detras_de_websockets_enabled(self):
        html = _leer(ALERTAS_DASHBOARD)

        indice = html.index("Estado WebSocket")
        antes = html[:indice]

        self.assertIn("{% if websockets_enabled %}", antes)
        self.assertIn("{% endif %}", html[indice:])


class EmojisComoIconosTests(SimpleTestCase):
    """FE-22 · los emojis del dashboard de contactos los lee el lector de pantalla.

    `📊` se anuncia «gráfico de barras» en medio de un estado vacío que ya dice
    «No hay datos para mostrar».
    """

    EMOJIS = ("📊", "📈", "📋", "👥")

    def test_el_dashboard_de_contactos_no_usa_emojis(self):
        html = _leer(DASHBOARD_CONTACTOS)

        for emoji in self.EMOJIS:
            self.assertNotIn(emoji, html, f"{DASHBOARD_CONTACTOS} todavía usa el emoji {emoji}")

    def test_los_iconos_que_los_reemplazan_estan_ocultos_a_la_accesibilidad(self):
        html = _leer(DASHBOARD_CONTACTOS)

        for fragmento in html.split('<i class="fas ')[1:]:
            self.assertIn('aria-hidden="true"', fragmento.split(">")[0] + ">")


class InicioSinHeroTests(SimpleTestCase):
    """FE-22 / D-F22 · el canon dice «no se arman heros para backoffice operativo».

    Default del README §2: aplicar el canon salvo que el PM registre la excepción.
    """

    def test_el_inicio_no_arma_un_hero(self):
        html = _leer(INICIO)

        self.assertNotIn("ini-hero", html)

    def test_el_titulo_sale_del_encabezado_canonico(self):
        html = _leer(INICIO)

        self.assertIn("{% page_header", html)

    def test_el_saludo_dejo_de_calcularse_en_el_cliente(self):
        """El eyebrow «Buenos días» era la única razón de `saludo` en el Alpine."""
        html = _leer(INICIO)

        self.assertNotIn("saludo", html)


class ProgramasDeLegajosSinKpisVaciosTests(SimpleTestCase):
    """FE-16 · las tres métricas por tarjeta leen anotaciones que ya no existen.

    `get_queryset` las quitó al retirar `models_institucional` y quedó
    documentado con un «DEPRECATED»: el template las sigue imprimiendo, así que
    cada tarjeta muestra tres números en blanco bajo sus rótulos.
    """

    ANOTACIONES_MUERTAS = (
        "programa.total_instituciones",
        "programa.total_derivaciones_pendientes",
        "programa.total_casos_activos",
    )

    def test_las_tres_anotaciones_muertas_no_estan(self):
        html = _leer(PROGRAMAS_LEGAJOS)

        for anotacion in self.ANOTACIONES_MUERTAS:
            self.assertNotIn(anotacion, html, f"{PROGRAMAS_LEGAJOS} todavía imprime {anotacion}")

    def test_el_queryset_ya_no_se_declara_deprecado_con_anotaciones(self):
        vista = _leer("legajos/views/programas.py")

        self.assertNotIn("filtros/annotates legacy removidos", vista)


class EdicionDelCiudadanoTests(SimpleTestCase):
    """V5A-NEW-04 · hero fuera de canon y texto técnico visible al usuario."""

    def test_la_bajada_no_nombra_la_libreria_de_maquetado(self):
        html = _leer(CIUDADANO_EDIT)

        self.assertNotIn("Flowbite", html)

    def test_el_encabezado_es_el_canonico(self):
        html = _leer(CIUDADANO_EDIT)

        self.assertIn("{% page_header", html)
        self.assertNotIn("<h1", html)

    def test_no_queda_el_hero_con_gradiente(self):
        html = _leer(CIUDADANO_EDIT)

        self.assertNotIn("bg-gradient-to-r", html)
        self.assertNotIn("bg-gradient-to-br", html)

    def test_el_estado_sale_del_dato_y_no_de_un_literal(self):
        """«Activo» estaba escrito en el template: un ciudadano dado de baja
        también se veía activo. `Ciudadano.activo` existe desde siempre."""
        html = _leer(CIUDADANO_EDIT)

        self.assertIn("object.activo", html)


class ConvocatoriaListLabelsTests(SimpleTestCase):
    """V5A-NEW-07 (b) · los 6 `<label>` del modal «Nueva convocatoria» sin `for`.

    WCAG 1.3.1: el lector de pantalla no asocia el rótulo con el control y el
    clic sobre el texto no enfoca el campo.
    """

    CAMPOS = ("nombre", "segmento", "subsegmento", "fecha_inicio", "fecha_fin", "descripcion")

    def test_cada_label_apunta_a_su_control(self):
        html = _leer(CONVOCATORIA_LIST)

        for campo in self.CAMPOS:
            esperado = 'for="{{ form_convocatoria.%s.id_for_label }}"' % campo
            self.assertIn(esperado, html, f"falta {esperado}")

    def test_no_quedan_labels_sueltos(self):
        html = _leer(CONVOCATORIA_LIST)

        self.assertNotIn('<label class="block text-sm font-medium text-heading mb-1">', html)

    def test_el_modal_no_arrastra_estilo_local(self):
        """La ficha del arquetipo Modal descartó esta pantalla como golden por el
        `[x-cloak]` propio —`override.css` ya lo declara global— y el backdrop
        con `style=`, que tiene clase compilada (`bg-black/50 backdrop-blur-sm`)."""
        html = _leer(CONVOCATORIA_LIST)

        self.assertNotIn("<style>", html)
        self.assertNotIn("backdrop-filter", html)
        self.assertIn("bg-black/50 backdrop-blur-sm", html)


class DashboardPanelDeBecasTests(SimpleTestCase):
    """V5A-NEW-07 (b) · deuda puntual de la solapa «Dashboard» del programa.

    El dashboard **no** es molde (el arquetipo está pendiente en el agente), así
    que solo se corrige lo que la ficha nombra.
    """

    def test_los_titulos_de_bloque_no_fijan_el_tamano_en_linea(self):
        html = _leer(DASHBOARD_PANEL)

        self.assertNotIn('style="font-size:16px"', html)
        self.assertEqual(html.count('class="text-heading font-bold text-base"'), 3)

    def test_el_modal_de_respuestas_usa_la_pieza_del_arquetipo(self):
        html = _leer(DASHBOARD_PANEL)

        self.assertIn('x-becas-modal="modalRespuestas"', html)

    def test_el_modal_de_respuestas_usa_el_header_y_el_pie_canonicos(self):
        html = _leer(DASHBOARD_PANEL)

        self.assertIn('{% include "programas/becas/_modal_header.html"', html)
        self.assertIn('{% include "programas/becas/_modal_footer.html"', html)

    def test_el_modal_no_dibuja_su_propia_x_con_svg(self):
        """El header canónico trae la X en Font Awesome; el SVG pegado a mano
        compite con `[R:ICONARIA]` (Heroicons queda solo en el shell)."""
        html = _leer(DASHBOARD_PANEL)

        self.assertNotIn("M6 18L18 6M6 6l12 12", html)
