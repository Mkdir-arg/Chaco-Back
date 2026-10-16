"""Hallazgos de QA del constructor y del catálogo de Becas (#338, #339 y #341).

- E2 (#338): las listas de requisitos muestran en qué canal se pide cada uno, sin
  abrir el modal, igual que el catálogo de preguntas (`_pregunta_row.html`).
- E3 (#339): borrar un requisito o una pregunta del catálogo que estaba en un diseño
  sube la versión en el acto, anula las condiciones que lo usaban como fuente (el
  constructor ya no queda trabado con 400) y el próximo que abre el constructor ve
  qué se borró y qué condiciones cayeron por eso.
- E4 (#339): el editor de condiciones solo ofrece como fuente un campo que se pide
  en todos los canales en que se pide el ítem (la regla de `fuentes_fuera_del_canal`).
"""

import json
from datetime import date
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from core.tests.js_harness import requiere_node
from programas.management.commands.seed_becas import ROL_ADMIN
from programas.models import (
    CanalFormulario,
    Convocatoria,
    DisenoFormulario,
    PreguntaGlobal,
    ProgramaSiis,
    RequisitoNativo,
    Segmento,
    Subsegmento,
    TipoCampo,
)
from programas.services import diseno as servicio_diseno
from programas.services.condiciones import validar_condicion
from programas.services.diseno import clave_pregunta, clave_requisito, obtener_o_crear_diseno, reconciliar
from programas.tests.test_constructor_confirmacion_y_autoguardado import _correr
from programas.views.diseno import _operadores

BADGE_APP = '<span class="badge badge-white">Solo app de campo</span>'
BADGE_LINK = '<span class="badge badge-white">Solo link público</span>'
BADGE_AMBOS = '<span class="badge badge-white">Ambos canales</span>'


class BadgeDeCanalTests(TestCase):
    """E2: el canal se ve en la celda Tipo; «ambos» no lleva badge."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_becas", stdout=StringIO())
        cls.admin = User.objects.create_user("admin_canal", password="x")
        cls.admin.groups.add(Group.objects.get(name=ROL_ADMIN))
        cls.programa = ProgramaSiis.objects.create(siis_programa_id=77, nombre="Becas canal")
        cls.segmento = Segmento.objects.create(nombre="Seg canal", cupo_maximo=10, programa=cls.programa)
        cls.subsegmento = Subsegmento.objects.create(segmento=cls.segmento, nombre="Sub canal", cupo_maximo=5)

        def requisito(texto, canal, **ancla):
            return RequisitoNativo.objects.create(texto=texto, tipo=TipoCampo.STRING, canal=canal, **ancla)

        requisito("Prog solo app", CanalFormulario.APP, programa=cls.programa)
        requisito("Prog ambos", CanalFormulario.AMBOS, programa=cls.programa)
        requisito("Seg solo link", CanalFormulario.LINK, segmento=cls.segmento)
        requisito("Seg ambos", CanalFormulario.AMBOS, segmento=cls.segmento)
        requisito("Sub solo app", CanalFormulario.APP, segmento=cls.segmento, subsegmento=cls.subsegmento)
        requisito("Sub ambos", CanalFormulario.AMBOS, segmento=cls.segmento, subsegmento=cls.subsegmento)

    def setUp(self):
        self.client.force_login(self.admin)

    def _html(self, nombre, *args):
        resp = self.client.get(reverse(f"becas:{nombre}", args=args))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertNotIn(BADGE_AMBOS, html)
        return html

    def test_panel_del_programa(self):
        html = self._html("programa_detalle", self.programa.pk)
        self.assertEqual(html.count(BADGE_APP), 1)
        self.assertNotIn(BADGE_LINK, html)

    def test_panel_del_segmento_y_heredados_del_programa(self):
        html = self._html("segmento_detalle", self.segmento.pk)
        self.assertEqual(html.count(BADGE_LINK), 1)  # el propio del segmento
        self.assertEqual(html.count(BADGE_APP), 1)  # el heredado del programa (solo lectura)

    def test_panel_del_subsegmento_y_heredados(self):
        html = self._html("subsegmento_detalle", self.subsegmento.pk)
        # Propio del subsegmento + heredado del programa; el del segmento es «link».
        self.assertEqual(html.count(BADGE_APP), 2)
        self.assertEqual(html.count(BADGE_LINK), 1)

    def test_pagina_de_requisitos(self):
        html = self._html("requisitos_segmento")
        self.assertIn(BADGE_LINK, html)
        self.assertIn(BADGE_APP, html)


class _BaseBajas(TestCase):
    """Una convocatoria con su diseño ya abierto una vez (versión 1).

    El certificado (segmento, orden 2) puede depender del nivel (segmento, orden 1);
    el barrio es el único requisito del subsegmento, así que su grupo automático se
    queda vacío si se lo borra.
    """

    def setUp(self):
        call_command("seed_becas", stdout=StringIO())
        self.admin = User.objects.create_user("admin_bajas", password="x")
        self.admin.groups.add(Group.objects.get(name=ROL_ADMIN))
        self.segmento = Segmento.objects.create(nombre="Educación", cupo_maximo=100)
        self.subsegmento = Subsegmento.objects.create(segmento=self.segmento, nombre="Resistencia", cupo_maximo=40)
        self.convocatoria = Convocatoria.objects.create(
            nombre="Becas 2026",
            segmento=self.segmento,
            subsegmento=self.subsegmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        self.nivel = RequisitoNativo.objects.create(
            texto="Nivel educativo",
            tipo=TipoCampo.SELECTOR,
            opciones=["Primario", "Secundario"],
            segmento=self.segmento,
            orden=1,
        )
        self.certificado = RequisitoNativo.objects.create(
            texto="Certificado de alumno regular", tipo=TipoCampo.ARCHIVO, segmento=self.segmento, orden=2
        )
        self.barrio = RequisitoNativo.objects.create(
            texto="Barrio", tipo=TipoCampo.STRING, segmento=self.segmento, subsegmento=self.subsegmento, orden=1
        )
        self.tenencia = PreguntaGlobal.objects.create(
            texto="Tenencia de la vivienda", tipo=TipoCampo.SELECTOR, opciones=["Propia", "Alquilada"], orden=600
        )
        self.diseno, _ = obtener_o_crear_diseno(self.convocatoria)
        self.assertEqual(self.diseno.version, 1)

    def _condicionar(self, clave_destino, fuente, valor):
        item = self.diseno.items.get(clave=clave_destino)
        item.condicion = {"modo": "todas", "reglas": [{"fuente": fuente, "op": "es", "valor": valor}]}
        item.save(update_fields=["condicion"])
        return item

    def _version(self):
        return DisenoFormulario.objects.get(pk=self.diseno.pk).version


class BorrarDelCatalogoTests(_BaseBajas):
    def test_sin_dependientes_sube_la_version_y_el_aviso_lo_nombra(self):
        self.certificado.delete()
        self.assertEqual(self._version(), 2)  # en el acto, no al abrir el constructor

        avisos = reconciliar(self.diseno)

        self.assertIn("Certificado de alumno regular", avisos["quitados"])
        self.assertEqual(avisos["fuentes_quitadas"], ["Certificado de alumno regular"])
        self.assertEqual(avisos["condiciones_quitadas"], [])
        self.assertEqual(self._version(), 2)  # ya subió con el borrado

    def test_con_dependientes_anula_la_condicion_en_el_acto_y_avisa_quien_la_perdio(self):
        cert = self._condicionar(clave_requisito(self.certificado), clave_requisito(self.nivel), "Secundario")

        self.nivel.delete()

        cert.refresh_from_db()
        self.assertIsNone(cert.condicion)
        self.assertEqual(self._version(), 2)
        avisos = reconciliar(self.diseno)
        self.assertEqual(avisos["fuentes_quitadas"], ["Nivel educativo → Certificado de alumno regular"])
        self.assertIn("Nivel educativo", avisos["quitados"])

    def test_una_pregunta_general_tambien(self):
        cert = self._condicionar(clave_requisito(self.certificado), clave_pregunta(self.tenencia), "Propia")

        self.tenencia.delete()

        cert.refresh_from_db()
        self.assertIsNone(cert.condicion)
        avisos = reconciliar(self.diseno)
        self.assertEqual(avisos["fuentes_quitadas"], ["Tenencia de la vivienda → Certificado de alumno regular"])

    def test_reconciliar_dos_veces_no_vuelve_a_avisar_ni_a_subir_la_version(self):
        """TC-339-07."""
        self.certificado.delete()
        reconciliar(self.diseno)

        avisos = reconciliar(self.diseno)

        self.assertEqual(avisos["quitados"], [])
        self.assertEqual(avisos["fuentes_quitadas"], [])
        self.assertEqual(self._version(), 2)
        self.assertIsNone(DisenoFormulario.objects.get(pk=self.diseno.pk).bajas_pendientes)

    def test_el_grupo_automatico_que_queda_vacio_se_borra_al_reconciliar(self):
        """RN-3: el barrio era el único campo del grupo del subsegmento."""
        self.barrio.delete()
        self.assertTrue(self.diseno.items.filter(clave="g-subsegmento").exists())

        reconciliar(self.diseno)

        self.assertFalse(self.diseno.items.filter(clave="g-subsegmento").exists())
        self.assertEqual(self._version(), 2)

    def test_borrado_masivo_tiene_el_mismo_efecto(self):
        cert = self._condicionar(clave_requisito(self.certificado), clave_requisito(self.nivel), "Secundario")

        RequisitoNativo.objects.filter(pk=self.nivel.pk).delete()

        cert.refresh_from_db()
        self.assertIsNone(cert.condicion)
        avisos = reconciliar(self.diseno)
        self.assertEqual(avisos["fuentes_quitadas"], ["Nivel educativo → Certificado de alumno regular"])

    def test_borrar_todo_el_catalogo_no_rompe(self):
        PreguntaGlobal.objects.all().delete()
        RequisitoNativo.objects.all().delete()
        avisos = reconciliar(self.diseno)
        self.assertIn("Tenencia de la vivienda", avisos["quitados"])
        self.assertFalse(self.diseno.items.filter(pregunta__isnull=False).exists())

    def test_los_disenos_se_bloquean_en_orden_de_id(self):
        """Dos borrados concurrentes que tocan los mismos diseños toman los candados
        en el mismo orden (por id del diseño): si no, InnoDB puede abortar uno por
        deadlock y responder 500. `ItemDiseno` se ordena por `orden` por defecto, así
        que acá el ítem del primer diseño va último a propósito."""
        otra = Convocatoria.objects.create(
            nombre="Becas 2026 bis",
            segmento=self.segmento,
            subsegmento=self.subsegmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        segundo, _ = obtener_o_crear_diseno(otra)
        self.assertLess(self.diseno.pk, segundo.pk)
        clave = clave_requisito(self.nivel)
        self.diseno.items.filter(clave=clave).update(orden=99)
        segundo.items.filter(clave=clave).update(orden=0)

        with patch.object(servicio_diseno, "bloquear", wraps=servicio_diseno.bloquear) as espia:
            self.nivel.delete()

        self.assertEqual([c.args[0].pk for c in espia.call_args_list], [self.diseno.pk, segundo.pk])

    def test_borrado_desde_el_admin(self):
        cert = self._condicionar(clave_requisito(self.certificado), clave_requisito(self.nivel), "Secundario")
        root = User.objects.create_superuser("root_bajas", "root@bajas.test", "x")
        self.client.force_login(root)

        resp = self.client.post(
            reverse("admin:programas_requisitonativo_delete", args=[self.nivel.pk]), {"post": "yes"}
        )

        self.assertEqual(resp.status_code, 302)
        self.assertFalse(RequisitoNativo.objects.filter(pk=self.nivel.pk).exists())
        cert.refresh_from_db()
        self.assertIsNone(cert.condicion)
        self.assertEqual(self._version(), 2)


class ConstructorTrasElBorradoTests(_BaseBajas):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)

    def test_una_mutacion_despues_del_borrado_no_da_400(self):
        """Antes la condición quedaba apuntando a una fuente inexistente y toda
        mutación moría en `validar_coherencia` hasta reabrir el constructor."""
        self._condicionar(clave_requisito(self.certificado), clave_requisito(self.nivel), "Secundario")
        self.nivel.delete()

        resp = self.client.post(
            reverse("becas:formulario_mover", args=[self.convocatoria.pk]),
            data=json.dumps({"clave": clave_requisito(self.certificado), "padre": "g-cuestionario", "posicion": 0}),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(resp.status_code, 200, resp.content)

    def test_la_pantalla_muestra_el_aviso_de_lo_borrado(self):
        self._condicionar(clave_requisito(self.certificado), clave_requisito(self.nivel), "Secundario")
        self.nivel.delete()

        resp = self.client.get(reverse("becas:convocatoria_formulario", args=[self.convocatoria.pk]))

        self.assertIn("Nivel educativo → Certificado de alumno regular", resp.content.decode())


# Un diseño con fuentes en los tres canales, y destinos al final. `S(x)` = canales
# donde se sirve x, con la cascada del padre (`items_planos`):
#   f-app {app} · f-link {link} · f-ambos {app, link} · f-hijo {app} (grupo solo app)
#   d-ambos {app, link} · d-app {app} · d-guardada {app, link} · d-imposible {} (app en grupo link)
_ITEMS_CANAL = [
    {"clave": "g-a", "tipo": "grupo", "canal": "ambos", "padre": None, "titulo": "A"},
    {"clave": "f-app", "tipo": "campo", "canal": "app", "padre": "g-a", "titulo": "F app"},
    {"clave": "f-link", "tipo": "campo", "canal": "link", "padre": "g-a", "titulo": "F link"},
    {"clave": "f-ambos", "tipo": "campo", "canal": "ambos", "padre": "g-a", "titulo": "F ambos"},
    {"clave": "g-app", "tipo": "grupo", "canal": "app", "padre": None, "titulo": "Solo app"},
    {"clave": "f-hijo", "tipo": "campo", "canal": "ambos", "padre": "g-app", "titulo": "F hijo"},
    {"clave": "g-z", "tipo": "grupo", "canal": "ambos", "padre": None, "titulo": "Z"},
    {"clave": "d-ambos", "tipo": "campo", "canal": "ambos", "padre": "g-z", "titulo": "D ambos"},
    {"clave": "d-app", "tipo": "campo", "canal": "app", "padre": "g-z", "titulo": "D app"},
    {
        "clave": "d-guardada",
        "tipo": "campo",
        "canal": "ambos",
        "padre": "g-z",
        "titulo": "D guardada",
        "condicion": {"modo": "todas", "reglas": [{"fuente": "f-link", "op": "vacio", "valor": None}]},
    },
    {"clave": "g-link", "tipo": "grupo", "canal": "link", "padre": None, "titulo": "Solo link"},
    {"clave": "d-imposible", "tipo": "campo", "canal": "app", "padre": "g-link", "titulo": "D imposible"},
]


@requiere_node
class FuentesPorCanalTests(SimpleTestCase):
    """E4: `fuentesPara` del constructor con la regla exacta del servidor (BEC-04):
    la fuente f se ofrece para el ítem i si S(i) ⊆ S(f); con S(i) vacío, todas."""

    def _fuentes(self, clave):
        log = _correr(
            "window.NodoConstructor.datos().items = " + json.dumps(_ITEMS_CANAL) + ";\n"
            "var __p = window.constructorPagina(1);\n"
            "__p.abrir({modal: 'condicion', clave: " + json.dumps(clave) + "});\n"
            "__log.fuentes = __p.cond.fuentes.map(function (f) { return [f.clave, f.titulo]; });"
        )
        return [tuple(f) for f in log["fuentes"]]

    def test_un_item_de_ambos_canales_solo_ofrece_fuentes_de_ambos(self):
        self.assertEqual(self._fuentes("d-ambos"), [("f-ambos", "F ambos")])

    def test_un_item_solo_app_ofrece_lo_que_se_pide_en_la_app(self):
        claves = [c for c, _ in self._fuentes("d-app")]
        self.assertEqual(claves, ["f-app", "f-ambos", "f-hijo", "d-ambos"])

    def test_la_fuente_ya_guardada_fuera_de_canal_se_muestra_marcada(self):
        self.assertEqual(
            self._fuentes("d-guardada"),
            [("f-link", "F link (no se pide en este canal)"), ("f-ambos", "F ambos"), ("d-ambos", "D ambos")],
        )

    def test_operadores_de_fecha_vacio_solo_si_la_regla_guardada_lo_usa(self):
        """E5: el editor no ofrece «está vacío/completo» para una fecha, salvo que
        la regla ya guardada lo use (si no, el `<select>` la perdería)."""
        operadores = json.dumps(_operadores())
        log = _correr(
            "var __ge = document.getElementById;\n"
            "document.getElementById = function (id) {\n"
            "  if (id === 'constructor-operadores') { return {textContent: " + json.dumps(operadores) + "}; }\n"
            "  return __ge(id);\n"
            "};\n"
            "window.NodoConstructor.datos().items = [\n"
            "  {clave: 'g', tipo: 'grupo', canal: 'ambos', padre: null},\n"
            "  {clave: 'nac', tipo: 'campo', canal: 'ambos', padre: 'g', tipo_campo: 'DATE'},\n"
            "  {clave: 'x', tipo: 'campo', canal: 'ambos', padre: 'g'}\n"
            "];\n"
            "var __p = window.constructorPagina(1);\n"
            "__p.abrir({modal: 'condicion', clave: 'x'});\n"
            "__log.nuevo = __p.operadoresDe('nac', '');\n"
            "__log.guardado = __p.operadoresDe('nac', 'vacio');\n"
            "__log.ajeno = __p.operadoresDe('nac', 'es');"
        )
        self.assertNotIn("vacio", log["nuevo"])
        self.assertNotIn("completo", log["nuevo"])
        self.assertIn("edad_menor", log["nuevo"])
        self.assertIn("vacio", log["guardado"])
        self.assertNotIn("completo", log["guardado"])
        self.assertNotIn("es", log["ajeno"])  # un operador que el servidor no acepta no se cuela

    def test_un_item_que_no_se_sirve_en_ningun_canal_ofrece_todo(self):
        claves = [c for c, _ in self._fuentes("d-imposible")]
        self.assertEqual(claves, ["f-app", "f-link", "f-ambos", "f-hijo", "d-ambos", "d-app", "d-guardada"])


class OperadoresDeFechaTests(SimpleTestCase):
    """E5 (#339, #341): para una fecha el editor ofrece edad y antes/después; el
    servidor sigue **aceptando** «vacío/completo» para no congelar los diseños que
    ya los tienen (`validar_coherencia` rechazaría cualquier mutación)."""

    def test_el_editor_no_ofrece_vacio_ni_completo_para_fechas(self):
        ofrecidos = _operadores()["por_tipo"][TipoCampo.DATE]
        self.assertNotIn("vacio", ofrecidos)
        self.assertNotIn("completo", ofrecidos)
        self.assertIn("edad_menor", ofrecidos)
        self.assertIn("anterior", ofrecidos)

    def test_los_demas_tipos_siguen_ofreciendolos(self):
        self.assertIn("vacio", _operadores()["por_tipo"][TipoCampo.STRING])
        self.assertIn("completo", _operadores()["por_tipo"][TipoCampo.INT])

    def test_el_servidor_sigue_aceptando_vacio_sobre_una_fecha(self):
        self.assertIn("vacio", _operadores()["aceptados"][TipoCampo.DATE])
        condicion = {"modo": "todas", "reglas": [{"fuente": "nac", "op": "vacio", "valor": None}]}
        anteriores = {"nac": {"tipo": "campo", "tipo_campo": TipoCampo.DATE}}
        self.assertEqual(validar_condicion(condicion, {"clave": "x"}, anteriores), [])
