"""Formularios por tipo de dispositivo (P17): uno por momento, editados con el
constructor de Becas.

Cubre el dueño nuevo del motor (`DisenoFormulario.tipo_dispositivo` + `momento`),
la tabla y el modal del detalle del tipo, el editor y sus mutaciones, la baja, el
aislamiento con Becas y los presupuestos de consultas.
"""

import json
from datetime import date
from pathlib import Path

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.test import TestCase, tag
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from programas.models import (
    CanalFormulario,
    Convocatoria,
    DisenoFormulario,
    ItemDiseno,
    MomentoFormulario,
    PreguntaGlobal,
    Programa,
    Segmento,
    TipoCampo,
    TipoDispositivo,
)
from programas.selectors.formularios_tipo import formularios_del_tipo
from programas.services.diseno import items_ordenados, items_vigentes, obtener_o_crear_diseno, plan_por_defecto
from programas.services.formularios_tipo import (
    crear_formulario,
    eliminar_formulario,
    momentos_libres,
    puede_eliminar_formulario,
)
from programas.tests.test_dispositivos_config import rol_configuracion

AJAX = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}


def _presupuesto(nombre):
    presupuestos = json.loads(
        (Path(__file__).resolve().parents[2] / "scripts/perf_budgets.json").read_text(encoding="utf-8")
    )
    return presupuestos["servicios"][nombre]["consultas_fijas"]


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.programa, _ = Programa.objects.get_or_create(
            codigo="DISPOSITIVOS",
            defaults={"nombre": "Dispositivos", "tipo": Programa.TipoPrograma.DISPOSITIVOS},
        )
        cls.otro_programa = Programa.objects.create(codigo="BECAS-FT", nombre="Becas test")
        cls.admin = User.objects.create_user("admin-formularios", password="x")
        cls.admin.groups.add(rol_configuracion("Admin formularios test", cls.programa))
        cls.ajeno = User.objects.create_user("admin-becas-ft", password="x")
        cls.ajeno.groups.add(rol_configuracion("Admin Becas ft", cls.otro_programa))
        cls.sin_permiso = User.objects.create_user("operador-ft", password="x")
        cls.tipo = TipoDispositivo.objects.create(codigo="CIS", nombre="Centro de integración")
        cls.otro_tipo = TipoDispositivo.objects.create(codigo="HOGAR", nombre="Hogar")

    def setUp(self):
        self.client.force_login(self.admin)

    # ── helpers ──
    def _url(self, nombre, momento="ingreso", *args, tipo=None):
        return reverse(f"dispositivos:{nombre}", args=[(tipo or self.tipo).pk, momento, *args])

    def _form(self, nombre, data, *args, momento="ingreso"):
        return self.client.post(self._url(nombre, momento, *args), data, **AJAX)

    def _json(self, nombre, payload, *args, momento="ingreso"):
        return self.client.post(
            self._url(nombre, momento, *args), data=json.dumps(payload), content_type="application/json", **AJAX
        )

    def _formulario(self, momento="ingreso"):
        return DisenoFormulario.objects.get(tipo_dispositivo=self.tipo, momento=momento)

    def _grupo(self, etiqueta="Datos del ingreso", momento="ingreso"):
        resp = self._form("formulario_grupo_crear", {"etiqueta": etiqueta, "canal": "ambos"}, momento=momento)
        self.assertEqual(resp.status_code, 200, resp.content)
        return self._formulario(momento).items.get(tipo=ItemDiseno.Tipo.GRUPO, etiqueta=etiqueta)

    def _propio(self, grupo, texto, **extra):
        datos = {"padre": grupo.clave, "texto": texto, "tipo": "STRING", "canal": "ambos", **extra}
        resp = self._form("formulario_propio_crear", datos)
        self.assertEqual(resp.status_code, 200, resp.content)
        return self._formulario().items.get(tipo=ItemDiseno.Tipo.CAMPO, propio__texto=texto)


# ── Modelo y servicio ────────────────────────────────────────────────────────


class ModeloTests(_Base):
    def test_un_tipo_no_puede_tener_dos_formularios_del_mismo_momento(self):
        """La restricción de la base, sin pasar por el servicio (mutación: sin
        `uniq_diseno_tipo_momento` la segunda alta entra)."""
        DisenoFormulario.objects.create(tipo_dispositivo=self.tipo, momento=MomentoFormulario.INGRESO)
        with self.assertRaises(IntegrityError), transaction.atomic():
            DisenoFormulario.objects.create(tipo_dispositivo=self.tipo, momento=MomentoFormulario.INGRESO)
        # Otro tipo sí puede tener el mismo momento.
        DisenoFormulario.objects.create(tipo_dispositivo=self.otro_tipo, momento=MomentoFormulario.INGRESO)

    def test_el_diseno_tiene_exactamente_un_dueno_y_momento_solo_con_el_tipo(self):
        segmento = Segmento.objects.create(nombre="Educación", cupo_maximo=10)
        convocatoria = Convocatoria.objects.create(
            nombre="Becas", segmento=segmento, fecha_inicio=date(2026, 1, 1), fecha_fin=date(2026, 12, 31)
        )
        invalidos = {
            "sin dueño": {},
            "dos dueños": {"convocatoria": convocatoria, "tipo_dispositivo": self.tipo, "momento": "ingreso"},
            "tipo sin momento": {"tipo_dispositivo": self.tipo},
            "convocatoria con momento": {"convocatoria": convocatoria, "momento": "ingreso"},
        }
        for caso, campos in invalidos.items():
            with self.subTest(caso=caso), self.assertRaises(IntegrityError), transaction.atomic():
                DisenoFormulario.objects.create(**campos)
        DisenoFormulario.objects.create(convocatoria=convocatoria)
        DisenoFormulario.objects.create(tipo_dispositivo=self.tipo, momento="egreso")


class ServicioTests(_Base):
    def test_crea_el_formulario_vacio_en_version_1_para_cada_momento(self):
        PreguntaGlobal.objects.create(texto="Tenencia", tipo=TipoCampo.SELECTOR, opciones=["A", "B"], orden=1)
        for momento in MomentoFormulario.values:
            with self.subTest(momento=momento):
                formulario = crear_formulario(self.tipo, momento, self.admin)
                self.assertEqual(formulario.version, 1)
                self.assertIsNone(formulario.convocatoria_id)
                # No hereda el catálogo de Becas: nace vacío.
                self.assertFalse(formulario.items.exists())
        self.assertEqual(momentos_libres(self.tipo.formularios.values_list("momento", flat=True)), [])

    def test_momento_repetido_o_invalido_es_error_de_validacion(self):
        crear_formulario(self.tipo, "ingreso")
        with self.assertRaises(ValidationError) as repetido:
            crear_formulario(self.tipo, "ingreso")
        self.assertEqual(repetido.exception.code, "momento_ocupado")
        self.assertIn("Ingreso de persona", repetido.exception.messages[0])
        with self.assertRaises(ValidationError) as invalido:
            crear_formulario(self.tipo, "inventado")
        self.assertEqual(invalido.exception.code, "momento_invalido")
        self.assertEqual(self.tipo.formularios.count(), 1)

    def test_momentos_libres_respeta_el_orden_y_saca_los_ocupados(self):
        libres = momentos_libres(["ingreso", "propio"])
        self.assertEqual(
            [valor for valor, _ in libres],
            ["crear_dispositivo", "asignacion_plaza", "novedades_turno", "egreso", "traslado"],
        )
        self.assertEqual(libres[0][1], "Crear dispositivo")

    def test_eliminar_borra_los_items_y_libera_el_momento(self):
        formulario = crear_formulario(self.tipo, "egreso")
        ItemDiseno.objects.create(diseno=formulario, tipo=ItemDiseno.Tipo.GRUPO, clave="g-1", etiqueta="Cierre")
        self.assertTrue(puede_eliminar_formulario(formulario))
        eliminar_formulario(formulario)
        self.assertFalse(ItemDiseno.objects.filter(clave="g-1").exists())
        self.assertIn("egreso", dict(momentos_libres(self.tipo.formularios.values_list("momento", flat=True))))
        crear_formulario(self.tipo, "egreso")

    def test_los_formularios_del_tipo_vienen_en_orden_con_sus_conteos(self):
        egreso = crear_formulario(self.tipo, "egreso")
        crear_formulario(self.tipo, "crear_dispositivo")
        crear_formulario(self.otro_tipo, "ingreso")
        grupo = ItemDiseno.objects.create(diseno=egreso, tipo=ItemDiseno.Tipo.GRUPO, clave="g-1", etiqueta="Cierre")
        for n in range(2):
            ItemDiseno.objects.create(
                diseno=egreso,
                tipo=ItemDiseno.Tipo.CAMPO,
                clave=f"p-{n}",
                padre=grupo,
                orden=n,
                propio={"texto": f"Campo {n}", "tipo": "STRING"},
            )
        filas = formularios_del_tipo(self.tipo)
        self.assertEqual([f.momento for f in filas], ["crear_dispositivo", "egreso"])
        self.assertEqual((filas[1].n_secciones, filas[1].n_campos), (1, 2))
        self.assertEqual(filas[1].se_completa_en, "Egresar")
        self.assertEqual(filas[0].se_completa_en, "Alta de la institución")


# ── Detalle del tipo: tabla y modal ──────────────────────────────────────────


class DetalleTipoTests(_Base):
    def test_sin_formularios_invita_a_crear_y_ofrece_todos_los_momentos(self):
        resp = self.client.get(reverse("dispositivos:tipo_detalle", args=[self.tipo.pk]))
        self.assertContains(resp, "Este tipo todavía no tiene formularios")
        self.assertContains(resp, "Nuevo formulario")
        self.assertNotContains(resp, "no tiene formulario propio")
        opciones = [valor for valor, _ in resp.context["form_nuevo_formulario"].fields["momento"].choices]
        self.assertEqual(opciones, MomentoFormulario.values)

    def test_la_tabla_lista_los_formularios_y_el_modal_solo_los_momentos_libres(self):
        crear_formulario(self.tipo, "ingreso")
        crear_formulario(self.tipo, "propio")
        resp = self.client.get(reverse("dispositivos:tipo_detalle", args=[self.tipo.pk]))
        html = resp.content.decode()
        self.assertIn("Ingreso de persona", html)
        self.assertIn("Sin asignar", html)
        self.assertIn(self._url("formulario_editor"), html)
        self.assertIn(self._url("formulario_eliminar"), html)
        self.assertIn("2 formularios", html)
        opciones = [valor for valor, _ in resp.context["form_nuevo_formulario"].fields["momento"].choices]
        self.assertNotIn("ingreso", opciones)
        self.assertNotIn("propio", opciones)
        self.assertEqual(len(opciones), 5)

    def test_con_todos_los_momentos_ocupados_no_se_ofrece_nuevo_formulario(self):
        for momento in MomentoFormulario.values:
            crear_formulario(self.tipo, momento)
        resp = self.client.get(reverse("dispositivos:tipo_detalle", args=[self.tipo.pk]))
        self.assertIsNone(resp.context["form_nuevo_formulario"])
        self.assertNotContains(resp, "Nuevo formulario")
        self.assertNotContains(resp, reverse("dispositivos:formulario_crear", args=[self.tipo.pk]))

    def test_el_parcial_ajax_del_detalle_tambien_trae_los_formularios(self):
        crear_formulario(self.tipo, "traslado")
        resp = self.client.post(
            reverse("dispositivos:tipo_editar", args=[self.tipo.pk]),
            {"codigo": "CIS", "nombre": "Centro editado", "descripcion": "", "activo": "on"},
            **AJAX,
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertIn("Trasladar", resp.json()["html"])


class CrearYEliminarVistaTests(_Base):
    def test_crear_redirige_al_editor_y_repetir_no_duplica(self):
        url = reverse("dispositivos:formulario_crear", args=[self.tipo.pk])
        resp = self.client.post(url, {"momento": "novedades_turno"})
        self.assertRedirects(resp, self._url("formulario_editor", "novedades_turno"))
        self.assertEqual(self._formulario("novedades_turno").version, 1)

        resp = self.client.post(url, {"momento": "novedades_turno"})
        self.assertRedirects(resp, reverse("dispositivos:tipo_detalle", args=[self.tipo.pk]))
        self.assertEqual(self.tipo.formularios.count(), 1)

        resp = self.client.post(url, {"momento": "inventado"})
        self.assertRedirects(resp, reverse("dispositivos:tipo_detalle", args=[self.tipo.pk]))
        self.assertEqual(self.tipo.formularios.count(), 1)

    def test_eliminar_desde_la_vista_libera_el_momento(self):
        crear_formulario(self.tipo, "ingreso")
        resp = self.client.post(self._url("formulario_eliminar"))
        self.assertRedirects(resp, reverse("dispositivos:tipo_detalle", args=[self.tipo.pk]))
        self.assertFalse(self.tipo.formularios.exists())
        resp = self.client.get(reverse("dispositivos:tipo_detalle", args=[self.tipo.pk]))
        self.assertIn("ingreso", [v for v, _ in resp.context["form_nuevo_formulario"].fields["momento"].choices])

    def test_eliminar_no_acepta_get(self):
        crear_formulario(self.tipo, "ingreso")
        self.assertEqual(self.client.get(self._url("formulario_eliminar")).status_code, 405)
        self.assertTrue(self.tipo.formularios.exists())


# ── Editor ───────────────────────────────────────────────────────────────────


class EditorTests(_Base):
    def setUp(self):
        super().setUp()
        crear_formulario(self.tipo, "ingreso")

    def test_la_pantalla_es_el_constructor_sin_canal_ni_restablecer(self):
        resp = self.client.get(self._url("formulario_editor"))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn('id="constructor-items"', html)
        self.assertIn('id="constructor-preview"', html)
        self.assertIn("Ingreso de persona", html)
        self.assertIn("se completa en: Ingreso", html)
        self.assertIn("Este formulario todavía no tiene preguntas", html)
        self.assertIn(self._url("formulario_propio_crear"), html)
        self.assertNotIn("Se pide en", html)
        self.assertNotIn("App de campo", html)
        self.assertNotIn('data-accion="restablecer"', html)
        self.assertNotIn("data-url-restablecer", html)

    def test_grupo_campo_propio_condicion_mover_y_eliminar_suben_la_version(self):
        formulario = self._formulario()
        version = formulario.version

        grupo = self._grupo()
        self.assertEqual(self._formulario().version, version + 1)

        texto_resp = self._form(
            "formulario_texto_crear", {"padre": grupo.clave, "texto": "Leé antes", "canal": "ambos"}
        )
        self.assertEqual(texto_resp.status_code, 200, texto_resp.content)

        sexo = self._propio(grupo, "¿Tiene documento?", tipo="SELECTOR", opciones_texto="Sí\nNo", presentacion="LISTA")
        numero = self._propio(grupo, "Número de documento")
        self.assertTrue(sexo.es_propio)
        self.assertEqual(sexo.propio["opciones"], ["Sí", "No"])

        condicion = {"modo": "todas", "reglas": [{"fuente": sexo.clave, "op": "es", "valor": "Sí"}]}
        resp = self._json("formulario_condicion", {"condicion": condicion}, numero.clave)
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(ItemDiseno.objects.get(pk=numero.pk).condicion, condicion)

        otro = self._grupo("Salud")
        resp = self._json("formulario_mover", {"clave": numero.clave, "padre": otro.clave, "posicion": 0})
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(ItemDiseno.objects.get(pk=numero.pk).padre_id, otro.pk)

        antes = self._formulario().version
        resp = self._form("formulario_item_eliminar", {}, numero.clave)
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertFalse(ItemDiseno.objects.filter(pk=numero.pk).exists())
        self.assertEqual(self._formulario().version, antes + 1)
        self.assertEqual(resp.json()["datos"]["version"], antes + 1)
        # Ocho guardados: dos grupos, un texto, dos campos, la condición, el movimiento y la baja.
        self.assertEqual(self._formulario().version, version + 8)

    def test_editar_un_item_lo_guarda_y_sube_la_version(self):
        grupo = self._grupo()
        version = self._formulario().version
        resp = self._form("formulario_item_editar", {"etiqueta": "Ingreso", "canal": "ambos"}, grupo.clave)
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(ItemDiseno.objects.get(pk=grupo.pk).etiqueta, "Ingreso")
        self.assertEqual(self._formulario().version, version + 1)

    def test_todo_se_pide_en_ambos_canales_aunque_el_post_diga_otro(self):
        """Mutación: con `_en_ambos` devolviendo el canal del POST, el grupo queda en «link»."""
        grupo = self._form("formulario_grupo_crear", {"etiqueta": "Solo link", "canal": "link"})
        self.assertEqual(grupo.status_code, 200, grupo.content)
        grupo = self._formulario().items.get(etiqueta="Solo link")
        self.assertEqual(grupo.canal, CanalFormulario.AMBOS)
        propio = self._propio(grupo, "Observaciones", canal="app")
        self.assertEqual(propio.canal, CanalFormulario.AMBOS)
        self._form("formulario_item_editar", {"etiqueta": "Solo link", "canal": "app"}, grupo.clave)
        self.assertEqual(ItemDiseno.objects.get(pk=grupo.pk).canal, CanalFormulario.AMBOS)

    def test_condicion_sobre_un_campo_posterior_se_rechaza_sin_subir_la_version(self):
        grupo = self._grupo()
        primero = self._propio(grupo, "Primero")
        segundo = self._propio(grupo, "Segundo", tipo="SELECTOR", opciones_texto="A\nB", presentacion="LISTA")
        version = self._formulario().version
        condicion = {"modo": "todas", "reglas": [{"fuente": segundo.clave, "op": "es", "valor": "A"}]}
        resp = self._json("formulario_condicion", {"condicion": condicion}, primero.clave)
        self.assertEqual(resp.status_code, 400)
        self.assertIsNone(ItemDiseno.objects.get(pk=primero.pk).condicion)
        self.assertEqual(self._formulario().version, version)

    def test_un_item_de_otro_formulario_es_404(self):
        crear_formulario(self.tipo, "egreso")
        grupo = self._grupo("Del egreso", momento="egreso")
        resp = self._form("formulario_item_editar", {"etiqueta": "X", "canal": "ambos"}, grupo.clave)
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(ItemDiseno.objects.get(pk=grupo.pk).etiqueta, "Del egreso")


# ── Acceso ───────────────────────────────────────────────────────────────────


class AccesoTests(_Base):
    def setUp(self):
        super().setUp()
        self.formulario = crear_formulario(self.tipo, "ingreso")
        self.grupo = ItemDiseno.objects.create(
            diseno=self.formulario, tipo=ItemDiseno.Tipo.GRUPO, clave="g-1", etiqueta="Datos"
        )

    def _rutas(self, tipo=None, momento="ingreso"):
        tipo = tipo or self.tipo
        en = lambda nombre, *args: reverse(f"dispositivos:{nombre}", args=[tipo.pk, momento, *args])  # noqa: E731
        return [
            ("get", en("formulario_editor")),
            ("post", en("formulario_eliminar")),
            ("post", en("formulario_mover")),
            ("post", en("formulario_grupo_crear")),
            ("post", en("formulario_texto_crear")),
            ("post", en("formulario_propio_crear")),
            ("post", en("formulario_item_editar", "g-1")),
            ("post", en("formulario_condicion", "g-1")),
            ("post", en("formulario_item_eliminar", "g-1")),
        ]

    def test_sin_permiso_ni_alcance_de_dispositivos_es_403_y_no_cambia_nada(self):
        """Mutación: sin `ConfigurarDispositivosMixin` en `_MutacionView` el operador muta."""
        rutas = [*self._rutas(), ("post", reverse("dispositivos:formulario_crear", args=[self.tipo.pk]))]
        for usuario in (self.sin_permiso, self.ajeno):
            self.client.force_login(usuario)
            for verbo, ruta in rutas:
                with self.subTest(usuario=usuario.username, ruta=ruta):
                    datos = {"etiqueta": "Hackeado", "canal": "ambos", "momento": "egreso"}
                    self.assertEqual(getattr(self.client, verbo)(ruta, datos).status_code, 403)
                    resp = getattr(self.client, verbo)(ruta, datos, **AJAX)
                    self.assertEqual(resp.status_code, 403)
                    self.assertFalse(resp.json()["ok"])
        self.assertEqual(self.tipo.formularios.count(), 1)
        self.assertEqual(self.formulario.items.count(), 1)
        self.assertEqual(DisenoFormulario.objects.get(pk=self.formulario.pk).version, 1)

    def test_anonimo_no_entra(self):
        self.client.logout()
        resp = self.client.get(self._url("formulario_editor"))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(self.client.post(self._url("formulario_grupo_crear"), {}, **AJAX).status_code, 401)

    def test_tipo_inexistente_momento_invalido_y_momento_sin_formulario_son_404(self):
        """Mutación: si `_formulario` no filtra por tipo, el «ingreso» de un tipo se
        abre y se muta desde la URL de otro."""
        inexistente = TipoDispositivo(pk=999999)
        casos = {
            "tipo inexistente": self._rutas(tipo=inexistente),
            "momento inválido": self._rutas(momento="inventado"),
            "momento de otro tipo": self._rutas(tipo=self.otro_tipo),
        }
        for caso, rutas in casos.items():
            for verbo, ruta in rutas:
                with self.subTest(caso=caso, ruta=ruta):
                    resp = getattr(self.client, verbo)(ruta, {"etiqueta": "X", "canal": "ambos"}, **AJAX)
                    self.assertEqual(resp.status_code, 404)
        resp = self.client.post(reverse("dispositivos:formulario_crear", args=[999999]), {"momento": "ingreso"})
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(self.formulario.items.count(), 1)
        self.assertTrue(DisenoFormulario.objects.filter(pk=self.formulario.pk).exists())


# ── Aislamiento con Becas ────────────────────────────────────────────────────


class AislamientoBecasTests(_Base):
    def test_un_formulario_de_tipo_no_aparece_en_ninguna_lectura_de_becas(self):
        formulario = crear_formulario(self.tipo, "ingreso")
        grupo = ItemDiseno.objects.create(diseno=formulario, tipo=ItemDiseno.Tipo.GRUPO, clave="g-dis", etiqueta="Disp")
        segmento = Segmento.objects.create(nombre="Educación", cupo_maximo=10)
        convocatoria = Convocatoria.objects.create(
            nombre="Becas", segmento=segmento, fecha_inicio=date(2026, 1, 1), fecha_fin=date(2026, 12, 31)
        )
        diseno_becas, _ = obtener_o_crear_diseno(convocatoria)
        self.assertNotEqual(diseno_becas.pk, formulario.pk)
        self.assertNotIn(grupo.pk, [i.pk for i in items_ordenados(diseno_becas)])
        self.assertFalse(DisenoFormulario.objects.filter(convocatoria__isnull=False, tipo_dispositivo=self.tipo))
        self.assertEqual(list(DisenoFormulario.objects.filter(convocatoria=convocatoria)), [diseno_becas])
        # Y al revés: la convocatoria no es un formulario del tipo.
        self.assertEqual([f.pk for f in formularios_del_tipo(self.tipo)], [formulario.pk])

    def test_el_catalogo_de_becas_no_entra_al_formulario_de_un_tipo(self):
        """Fuente de catálogo por dueño. Mutación: sin la guarda de
        `_catalogo_esperado`, `items_vigentes` le agrega las preguntas globales
        activas al formulario del tipo."""
        PreguntaGlobal.objects.create(texto="Tenencia", tipo=TipoCampo.SELECTOR, opciones=["A", "B"], orden=1)
        formulario = crear_formulario(self.tipo, "ingreso")
        grupo = ItemDiseno.objects.create(diseno=formulario, tipo=ItemDiseno.Tipo.GRUPO, clave="g-1", etiqueta="Datos")
        self.assertEqual([i.pk for i in items_vigentes(formulario)], [grupo.pk])
        self.assertEqual(plan_por_defecto(None), [])


# ── Presupuestos ─────────────────────────────────────────────────────────────


@tag("performance")
class PresupuestoTests(_Base):
    def _poblar(self, formularios):
        for momento in MomentoFormulario.values[:formularios]:
            formulario = crear_formulario(self.tipo, momento)
            for g in range(3):
                grupo = ItemDiseno.objects.create(
                    diseno=formulario, tipo=ItemDiseno.Tipo.GRUPO, clave=f"g-{momento}-{g}", etiqueta=f"G{g}", orden=g
                )
                ItemDiseno.objects.bulk_create(
                    ItemDiseno(
                        diseno=formulario,
                        tipo=ItemDiseno.Tipo.CAMPO,
                        clave=f"p-{momento}-{g}-{n}",
                        padre=grupo,
                        orden=n,
                        propio={"texto": f"Campo {n}", "tipo": "STRING"},
                    )
                    for n in range(6)
                )

    def test_la_tabla_del_tipo_cuesta_lo_mismo_con_uno_o_siete_formularios(self):
        techo = _presupuesto("dispositivos_formularios_del_tipo")
        for cantidad in (1, 7):
            DisenoFormulario.objects.filter(tipo_dispositivo=self.tipo).delete()
            self._poblar(cantidad)
            with CaptureQueriesContext(connection) as consultas:
                filas = formularios_del_tipo(self.tipo)
            self.assertEqual(len(filas), cantidad)
            self.assertLessEqual(len(consultas), techo, [c["sql"] for c in consultas])

    def test_el_editor_no_consulta_por_item(self):
        techo = _presupuesto("dispositivos_formulario_editor")
        medidas = []
        for campos in (1, 6):
            DisenoFormulario.objects.filter(tipo_dispositivo=self.tipo).delete()
            self._poblar(1)
            ItemDiseno.objects.filter(diseno__tipo_dispositivo=self.tipo, orden__gte=campos).delete()
            url = self._url("formulario_editor", MomentoFormulario.values[0])
            self.client.get(url)  # calienta sesión y caché de permisos
            with CaptureQueriesContext(connection) as consultas:
                self.assertEqual(self.client.get(url).status_code, 200)
            medidas.append(len(consultas))
            self.assertLessEqual(len(consultas), techo, [c["sql"] for c in consultas])
        self.assertEqual(medidas[0], medidas[1])
