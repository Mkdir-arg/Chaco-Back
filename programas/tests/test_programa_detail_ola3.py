"""Detalle de programa (Becas): usa las piezas comunes (encabezado, modales, estados)."""

import re
from io import StringIO

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from programas.models import ProgramaSiis, RequisitoNativo, Segmento


class ProgramaDetalleOla3Tests(TestCase):
    def setUp(self):
        cache.clear()
        call_command("seed_becas", stdout=StringIO())
        self.programa = ProgramaSiis.objects.create(nombre="Producción", siis_programa_id=38)
        self.client.force_login(User.objects.create_superuser("super_prog_det", password="x"))

    def _html(self):
        response = self.client.get(reverse("becas:programa_detalle", args=[self.programa.pk]))
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def test_tres_modales_son_dialogos_con_titulo_existente(self):
        html = self._html()
        ids = re.findall(r'role="dialog" aria-modal="true"\s+aria-labelledby="([^"]+)"', html)
        for esperado in ("modal-seg-titulo", "modal-req-titulo", "modal-req-edit-titulo"):
            self.assertIn(esperado, ids)
            self.assertIn(f'id="{esperado}"', html)
        self.assertIn("custom/js/becas-modal.js", html)

    def test_modal_de_requisito_conserva_todos_los_campos(self):
        html = self._html()
        for name in (
            "texto",
            "tipo",
            "obligatorio",
            "orden",
            "opciones_texto",
            "presentacion",
            "canal",
            "destino_siis",
        ):
            self.assertIn(f'name="{name}"', html)

    def test_pausado_es_warning_y_reanudar_lleva_play(self):
        ProgramaSiis.objects.filter(pk=self.programa.pk).update(pausado=True, pausa_motivo="Prueba")
        html = self._html()
        self.assertIn('badge-warning badge-dot" title="Prueba">Pausado</span>', html)
        self.assertNotIn('badge-danger badge-dot">Pausado', html)
        self.assertRegex(html, r'btn-brand btn-sm[^>]*>\s*<i class="fas fa-play"')
        self.assertIn("Reanudar programa", html)

    def test_pausar_sigue_danger_con_pause(self):
        html = self._html()
        self.assertRegex(html, r'btn-danger btn-sm[^>]*>\s*<i class="fas fa-pause"')
        self.assertIn("Pausar programa", html)

    def test_acciones_de_fila_nombran_el_requisito(self):
        RequisitoNativo.objects.create(programa=self.programa, texto="DNI del titular", tipo="TEXTO", orden=1)
        html = self._html()
        self.assertIn('aria-label="Editar requisito DNI del titular"', html)
        self.assertIn('aria-label="Eliminar requisito DNI del titular"', html)
        self.assertIn('data-confirm-danger="true"', html)
        self.assertIn('data-confirm-ok="Sí, eliminar"', html)

    def test_tabs_alternan_peso_y_contador(self):
        html = self._html()
        self.assertIn(
            "border-brand font-bold' : 'text-body-subtle border-transparent hover:text-body font-medium'", html
        )
        self.assertIn("bg-brand-soft text-fg-brand", html)

    def test_nuevo_requisito_tiene_destino_siis(self):
        html = self._html()
        inicio = html.index('id="form-req-crear"')
        fin = html.index("</form>", inicio)
        bloque_crear = html[inicio:fin]
        self.assertIn('name="destino_siis"', bloque_crear)
        self.assertIn("No alimenta a SIIS", bloque_crear)

    def test_tabla_segmentos_usa_piezas_comunes_nodo(self):
        Segmento.objects.create(programa=self.programa, nombre="Segmento A", cupo_maximo=10)
        html = self._html()
        self.assertIn("nodo-thead-row", html)
        self.assertIn('class="nodo-th', html)
        self.assertIn('class="nodo-td', html)
        self.assertNotIn("hover:bg-tertiary", html)
        self.assertNotIn("font-size:11px", html)
        self.assertNotIn("font-size:13.5px", html)

    def test_panel_requisitos_programa_usa_piezas_comunes_nodo(self):
        RequisitoNativo.objects.create(programa=self.programa, texto="DNI del titular", tipo="TEXTO", orden=1)
        html = self._html()
        inicio = html.index('id="reqs-programa-panel"')
        bloque_panel = html[inicio : inicio + 3000]
        self.assertIn("nodo-thead-row", bloque_panel)
        self.assertIn('class="nodo-th', bloque_panel)
        self.assertIn('class="nodo-td', bloque_panel)

    def test_modal_siis_es_becas_modal(self):
        html = self._html()
        self.assertIn('x-becas-modal="modalInfo"', html)
        self.assertIn('id="modal-info-titulo"', html)

    def test_alta_rapida_de_coordinador_se_apila_sobre_nuevo_segmento(self):
        # RONDA 2, hallazgo MAJOR #1: con "Nuevo segmento" abierto, "Crear coordinador"
        # tiene que quedar arriba en la pila de becas-modal.js (Tab atrapado y Escape
        # solo para el anidado). El PR #485 le dio a este modal role=dialog +
        # becasModal.bind (ver users/tests/test_alta_rapida_modal.py); acá solo se fija
        # el contrato desde el lado de programa_detail.html: el botón que lo abre y el
        # propio include quedan servidos en la misma página, después de becas-modal.js.
        html = self._html()
        self.assertIn('data-quick-user="coordinador"', html)
        self.assertIn('data-user-select="#id_coordinador"', html)
        self.assertIn('id="quick-user-modal"', html)
        self.assertIn('role="dialog" aria-modal="true" aria-labelledby="quick-user-titulo"', html)
        self.assertIn("becasModal.bind", html)
        pos_becas_modal_js = html.index("custom/js/becas-modal.js")
        pos_quick_user = html.index('id="quick-user-modal"')
        self.assertLess(
            pos_quick_user,
            pos_becas_modal_js,
            "el include del alta rapida va antes del bloque customJS, pero su propio "
            "script se autoinyecta becas-modal.js si hace falta (ver _alta_rapida_modal.html)",
        )
