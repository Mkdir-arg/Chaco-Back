"""Listado y detalle de convocatorias con las piezas comunes de Becas (ola 3).

Cubre lo que se ve en la pantalla y que ningún otro test fija:

* CMP-4 — el estado de cada fila sale del mapa único
  (``programas/becas/_convocatoria_estado_badge.html``): «Cerrada» gris cuando está
  apagada, «Vencida» de atención y la pausa —propia o heredada— por encima de todo.
* El listado precarga ``segmento__programa`` y ``subsegmento__segmento__programa``:
  el badge mira ``pausa_efectiva``, que sin eso hace consultas por fila.
* POP-13 / POP-12 — «Desactivar» confirma en rojo con la consecuencia y «Sí,
  desactivar»; «Activar» confirma con el tono de marca y «Sí, activar».
* CMP-M3/M4 — tablas con ``.nodo-th``/``.nodo-td`` y acciones de fila
  ``.nodo-icon-btn`` con ``aria-label`` que nombra la convocatoria.
* POP-M1 — los modales de alta usan ``x-becas-modal`` y los parciales canónicos.
* TIT-16 — «Configurar formulario» es una acción del encabezado, no una solapa.
"""

from datetime import timedelta

from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from core.tests.js_harness import atributos_de
from programas.models import Convocatoria, ProgramaSiis, Segmento, Subsegmento
from programas.tests.base_becas import BecasPantallaTestCase


def _badges(html):
    """(clase, texto) de cada ``<span class="badge …">`` del fragmento."""
    salida = []
    resto = html
    while True:
        i = resto.find('<span class="badge')
        if i == -1:
            return salida
        fin_tag = resto.index(">", i)
        fin = resto.index("</span>", fin_tag)
        clases = resto[i + len('<span class="') : resto.index('"', i + len('<span class="'))]
        salida.append((clases, resto[fin_tag + 1 : fin].strip()))
        resto = resto[fin + 1 :]


class _BaseConvocatoriasDiseno(BecasPantallaTestCase):
    """Alias local de la base compartida.

    El contenido de este `setUp` nació acá (Cambio 130, PR R-11) y el PR R-20 lo
    movió a `programas.tests.base_becas` cuando apareció en otros cinco módulos
    (TST-02): el porqué de cada línea está en el docstring de ese archivo.
    """


class ConvocatoriaListadoEstadoTests(_BaseConvocatoriasDiseno):
    """CMP-4: el listado usa el mapa único de estados de la convocatoria."""

    def setUp(self):
        super().setUp()
        self.hoy = timezone.localdate()
        self.programa = ProgramaSiis.objects.create(nombre="Becas", siis_programa_id=4001)
        self.segmento = Segmento.objects.create(nombre="Seg Diseño", cupo_maximo=100, programa=self.programa)
        self.client.force_login(User.objects.create_superuser("admin-conv-diseno", password="x"))

    def _convocatoria(self, nombre, *, activo=True, vencida=False, **extra):
        return Convocatoria.objects.create(
            nombre=nombre,
            segmento=self.segmento,
            activo=activo,
            fecha_inicio=self.hoy - timedelta(days=60),
            fecha_fin=self.hoy - timedelta(days=1) if vencida else self.hoy + timedelta(days=30),
            **extra,
        )

    def _fila(self, convocatoria):
        html = self.client.get(reverse("becas:convocatorias")).content.decode()
        marca = html.index(f">{convocatoria.nombre}</a>")
        inicio = html.rindex("<tr ", 0, marca)
        return html[inicio : html.index("</tr>", marca)]

    def test_inactiva_es_cerrada_gris_y_nunca_roja(self):
        conv = self._convocatoria("Conv apagada", activo=False)

        fila = self._fila(conv)

        self.assertEqual(_badges(fila), [("badge badge-gray badge-dot", "Cerrada")])
        self.assertNotIn("badge-danger", fila)

    def test_vencida_sigue_siendo_atencion(self):
        conv = self._convocatoria("Conv vencida", vencida=True)

        self.assertEqual(_badges(self._fila(conv)), [("badge badge-warning badge-dot", "Vencida")])

    def test_activa_es_exito(self):
        conv = self._convocatoria("Conv viva")

        self.assertEqual(_badges(self._fila(conv)), [("badge badge-success badge-dot", "Activa")])

    def test_la_tabla_toma_en_cuenta_la_pausa_propia(self):
        conv = self._convocatoria("Conv pausada", pausado=True, pausa_motivo="Corte administrativo")

        fila = self._fila(conv)

        self.assertEqual(_badges(fila), [("badge badge-warning badge-dot", "Pausada")])
        self.assertIn('title="Corte administrativo"', fila)

    def test_la_tabla_toma_en_cuenta_la_pausa_heredada_del_programa(self):
        conv = self._convocatoria("Conv heredada")
        self.programa.pausado = True
        self.programa.pausa_motivo = "Programa en pausa"
        self.programa.save()

        fila = self._fila(conv)

        self.assertEqual(_badges(fila), [("badge badge-warning badge-dot", "Pausada")])
        self.assertIn('title="Programa en pausa"', fila)

    def _consultas_del_listado(self):
        """Consultas del listado con **todas** las cachés recién calentadas.

        Lo que se mide es si la pantalla consulta por fila, así que no puede
        depender de cuándo venció una clave de caché. Y dos de las consultas del
        request son exactamente eso: ``programas:becas`` (300 s) y
        ``sidebar:conversaciones_pendientes`` (**30 s**, `get_or_set` del badge del
        sidebar, que corre en todo el backoffice). Con el `cache.clear()` solo en
        `setUp`, la segunda medición del test podía caer del otro lado de esos 30 s y
        pagar un `COUNT` de más: es el `7 != 6` que puso roja la suite en el CI, sin
        que hubiera cambiado una línea de la pantalla. Limpiando acá, cada medición
        empieza igual: el GET de calentamiento repone las dos claves con TTL nuevo y
        el GET medido siempre las encuentra calientes.
        """
        url = reverse("becas:convocatorias")
        cache.clear()
        self.client.get(url)  # caches de sesión, permisos, Programa Becas y badge
        with CaptureQueriesContext(connection) as capturadas:
            respuesta = self.client.get(url)
        self.assertEqual(respuesta.status_code, 200)
        return len(capturadas), respuesta.content.decode()

    def test_el_listado_no_consulta_por_fila(self):
        """Sin ``select_related`` cada fila consultaría segmento, programa y subsegmento."""
        sub = Subsegmento.objects.create(segmento=self.segmento, nombre="Sub", cupo_maximo=10)
        self._convocatoria("Conv sola", subsegmento=sub)

        con_una, html = self._consultas_del_listado()
        self.assertEqual(html.count("badge-success badge-dot"), 1)

        for i in range(5):
            self._convocatoria(f"Conv extra {i}", subsegmento=sub)
        con_seis, html = self._consultas_del_listado()

        self.assertEqual(html.count("badge-success badge-dot"), 6)
        self.assertEqual(con_seis, con_una)

    def test_la_pausa_heredada_tampoco_consulta_por_fila(self):
        self.programa.pausado = True
        self.programa.save()
        self._convocatoria("Conv A")

        con_una, _ = self._consultas_del_listado()
        self._convocatoria("Conv B")
        con_dos, html = self._consultas_del_listado()

        self.assertEqual(html.count('badge-warning badge-dot"'), 2)
        self.assertEqual(con_dos, con_una)


class ConvocatoriaListadoAccionesTests(_BaseConvocatoriasDiseno):
    """POP-13 / POP-12 y las acciones de fila del listado."""

    def setUp(self):
        super().setUp()
        self.hoy = timezone.localdate()
        self.segmento = Segmento.objects.create(nombre="Seg Acciones", cupo_maximo=100)
        self.client.force_login(User.objects.create_superuser("admin-conv-acciones", password="x"))

    def _convocatoria(self, nombre, *, activo=True, vencida=False):
        return Convocatoria.objects.create(
            nombre=nombre,
            segmento=self.segmento,
            activo=activo,
            fecha_inicio=self.hoy - timedelta(days=60),
            fecha_fin=self.hoy - timedelta(days=1) if vencida else self.hoy + timedelta(days=30),
        )

    def _atributos(self):
        html = self.client.get(reverse("becas:convocatorias")).content.decode()
        return [attrs for _, attrs in atributos_de(html)]

    def test_desactivar_confirma_en_rojo_con_la_consecuencia(self):
        conv = self._convocatoria("Conv activa")

        (boton,) = [
            a for a in self._atributos() if a.get("data-confirm-url", "").endswith(f"/convocatorias/{conv.pk}/toggle/")
        ]

        self.assertEqual(boton["data-confirm-danger"], "true")
        self.assertEqual(boton["data-confirm-icon"], "danger")
        self.assertEqual(boton["data-confirm-ok"], "Sí, desactivar")
        self.assertEqual(boton["data-confirm-title"], "¿Desactivar la convocatoria?")
        self.assertIn("deja de aceptar relevamientos nuevos", boton["data-confirm-text"])
        self.assertIn("nodo-icon-btn--danger", boton["class"].split())
        self.assertEqual(boton["aria-label"], "Desactivar convocatoria Conv activa")

    def test_activar_confirma_con_el_tono_de_marca(self):
        conv = self._convocatoria("Conv apagada", activo=False)

        (boton,) = [
            a for a in self._atributos() if a.get("data-confirm-url", "").endswith(f"/convocatorias/{conv.pk}/toggle/")
        ]

        self.assertEqual(boton["data-confirm-danger"], "false")
        self.assertEqual(boton["data-confirm-ok"], "Sí, activar")
        self.assertEqual(boton["data-confirm-title"], "¿Activar la convocatoria?")
        self.assertNotIn("nodo-icon-btn--danger", boton["class"].split())
        self.assertEqual(boton["aria-label"], "Activar convocatoria Conv apagada")

    def test_una_vencida_ofrece_reactivar_y_no_el_toggle(self):
        conv = self._convocatoria("Conv vencida", activo=False, vencida=True)
        atributos = self._atributos()

        self.assertEqual([a for a in atributos if "data-confirm-url" in a], [])
        (boton,) = [a for a in atributos if "data-reactivar-url" in a]
        self.assertEqual(boton["data-nombre"], conv.nombre)
        self.assertIn("nodo-icon-btn", boton["class"].split())

    def test_la_tabla_usa_las_clases_de_tabla_y_el_ojo_con_aria_label(self):
        conv = self._convocatoria("Conv mirada")
        html = self.client.get(reverse("becas:convocatorias")).content.decode()

        self.assertIn('<th class="nodo-th">Nombre</th>', html)
        self.assertIn('<td class="nodo-td text-body">', html)
        detalle = reverse("becas:convocatoria_detalle", args=[conv.pk])
        (ver,) = [
            a for _, a in atributos_de(html) if a.get("href") == detalle and "nodo-icon-btn" in a.get("class", "")
        ]
        self.assertEqual(ver["aria-label"], f"Ver convocatoria {conv.nombre}")

    def test_el_modal_de_alta_es_el_canonico(self):
        html = self.client.get(reverse("becas:convocatorias")).content.decode()

        (overlay,) = [a for _, a in atributos_de(html) if a.get("x-becas-modal") == "modalCrear"]
        self.assertIn("x-cloak", overlay)
        (dialogo,) = [a for _, a in atributos_de(html) if a.get("aria-labelledby") == "modal-convocatoria-crear-titulo"]
        self.assertEqual(dialogo["role"], "dialog")
        self.assertEqual(dialogo["aria-modal"], "true")
        self.assertIn('id="modal-convocatoria-crear-titulo"', html)
        self.assertIn("custom/js/becas-modal.js", html)
        self.assertIn("Crear convocatoria", html)


class ConvocatoriaDetalleDisenoTests(_BaseConvocatoriasDiseno):
    """TIT-15 / TIT-16 y las piezas comunes del detalle."""

    def setUp(self):
        super().setUp()
        self.hoy = timezone.localdate()
        segmento = Segmento.objects.create(nombre="Seg Detalle", cupo_maximo=100)
        self.convocatoria = Convocatoria.objects.create(
            nombre="Conv Detalle",
            segmento=segmento,
            fecha_inicio=self.hoy - timedelta(days=10),
            fecha_fin=self.hoy + timedelta(days=30),
        )
        self.client.force_login(User.objects.create_superuser("admin-conv-detalle", password="x"))

    def _html(self):
        respuesta = self.client.get(reverse("becas:convocatoria_detalle", args=[self.convocatoria.pk]))
        self.assertEqual(respuesta.status_code, 200)
        return respuesta.content.decode()

    def test_configurar_formulario_es_una_accion_del_encabezado_y_no_una_solapa(self):
        html = self._html()
        destino = reverse("becas:convocatoria_formulario", args=[self.convocatoria.pk])

        (enlace,) = [a for _, a in atributos_de(html) if a.get("href") == destino]

        clases = enlace["class"].split()
        self.assertIn("btn-nodo", clases)
        self.assertIn("btn-secondary", clases)
        self.assertIn("btn-sm", clases)
        # La barra de solapas queda solo con solapas: nada de `ml-auto` colgado.
        barra = html[html.index("border-b border-base flex gap-1 px-2 flex-wrap") :]
        self.assertNotIn(destino, barra[: barra.index("</div>")])
        # El encabezado ya lo dibujó antes de la barra.
        self.assertLess(html.index(destino), html.index("border-b border-base flex gap-1 px-2 flex-wrap"))

    def test_los_contadores_de_las_solapas_usan_variantes_de_badge(self):
        html = self._html()

        self.assertIn("tab==='rel' ? 'badge-info' : 'badge-gray'", html)
        self.assertIn("tab==='ben' ? 'badge-info' : 'badge-gray'", html)
        self.assertNotIn("bg-brand-soft text-fg-brand'", html)

    def test_cerrada_en_el_encabezado_y_en_la_ficha(self):
        self.convocatoria.activo = False
        self.convocatoria.save()

        html = self._html()

        self.assertEqual(html.count('badge badge-gray badge-dot">Cerrada</span>'), 2)
        self.assertNotIn(">Inactiva</span>", html)

    def test_el_modal_de_relevamiento_es_el_canonico(self):
        html = self._html()

        (overlay,) = [a for _, a in atributos_de(html) if a.get("x-becas-modal") == "modalRel"]
        self.assertIn("x-cloak", overlay)
        (dialogo,) = [a for _, a in atributos_de(html) if a.get("aria-labelledby") == "modal-relevamiento-crear-titulo"]
        self.assertEqual(dialogo["aria-modal"], "true")
        self.assertIn("custom/js/becas-modal.js", html)

    def test_las_alertas_de_la_pagina_usan_la_receta_unica(self):
        html = self._html()

        for bloque in ("bg-danger-soft", "bg-warning-soft"):
            for nodo in [a for _, a in atributos_de(html) if bloque in a.get("class", "")]:
                if "badge" in nodo.get("class", ""):
                    continue
                clases = nodo["class"].split()
                self.assertIn("p-4", clases, nodo)
                self.assertEqual(nodo.get("role"), "alert", nodo)
