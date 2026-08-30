"""Constructor del formulario de la convocatoria (Cambio 58, Fase 3: tasks
#342, #343 y #344, análisis #326): pantalla, drag & drop, ítems y condiciones."""

import json
from datetime import date
from io import StringIO

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from programas.management.commands.seed_becas import ROL_ADMIN, ROL_COORDINADOR
from programas.models import (
    Convocatoria,
    DisenoFormulario,
    ItemDiseno,
    PreguntaGlobal,
    RequisitoNativo,
    Segmento,
    TipoCampo,
)
from programas.services.diseno import clave_pregunta, clave_requisito, items_ordenados, obtener_o_crear_diseno


class _Base(TestCase):
    def setUp(self):
        call_command("seed_becas", stdout=StringIO())
        self.admin = User.objects.create_user("admin-cons", password="x")
        self.admin.groups.add(Group.objects.get(name=ROL_ADMIN))
        self.client.force_login(self.admin)
        self.segmento = Segmento.objects.create(nombre="Educación", cupo_maximo=100)
        self.convocatoria = Convocatoria.objects.create(
            nombre="Becas 2026", segmento=self.segmento, fecha_inicio=date(2026, 1, 1), fecha_fin=date(2026, 12, 31)
        )
        self.nivel = RequisitoNativo.objects.create(
            texto="Nivel educativo",
            tipo=TipoCampo.SELECTOR,
            opciones=["Primario", "Secundario"],
            segmento=self.segmento,
            orden=1,
        )
        self.certificado = RequisitoNativo.objects.create(
            texto="Certificado", tipo=TipoCampo.ARCHIVO, segmento=self.segmento, orden=2
        )
        self.tenencia = PreguntaGlobal.objects.create(
            texto="Tenencia de la vivienda", tipo=TipoCampo.SELECTOR, opciones=["Propia", "Alquilada"], orden=600
        )
        self.pk = self.convocatoria.pk

    # ── helpers ──
    def _url(self, nombre, *args):
        return reverse(f"becas:{nombre}", args=[self.pk, *args])

    def _json(self, nombre, payload, *args):
        return self.client.post(
            self._url(nombre, *args),
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

    def _form(self, nombre, data, *args):
        return self.client.post(self._url(nombre, *args), data, HTTP_X_REQUESTED_WITH="XMLHttpRequest")

    def _diseno(self):
        diseno, _ = obtener_o_crear_diseno(self.convocatoria)
        return diseno

    def _claves(self):
        return [i.clave for i in items_ordenados(self._diseno())]

    def _item(self, clave):
        return self._diseno().items.get(clave=clave)


class PantallaTests(_Base):
    def test_abre_y_persiste_el_diseno_por_defecto(self):
        self.assertFalse(DisenoFormulario.objects.filter(convocatoria=self.convocatoria).exists())
        resp = self.client.get(self._url("convocatoria_formulario"))
        self.assertEqual(resp.status_code, 200)
        diseno = DisenoFormulario.objects.get(convocatoria=self.convocatoria)
        self.assertEqual(diseno.version, 1)
        html = resp.content.decode()
        self.assertIn('id="constructor-items"', html)
        self.assertIn('id="constructor-preview"', html)
        self.assertIn('id="constructor-datos"', html)
        self.assertIn("Datos personales", html)
        self.assertIn("Nivel educativo", html)
        self.assertIn("Tenencia de la vivienda", html)
        # Los datos para la vista previa traen los ítems en orden con su tipo de campo.
        datos = resp.context["datos"]
        claves = [i["clave"] for i in datos["items"]]
        self.assertIn(clave_requisito(self.nivel), claves)
        nivel = next(i for i in datos["items"] if i["clave"] == clave_requisito(self.nivel))
        self.assertEqual(nivel["tipo_campo"], "SELECTOR")
        self.assertEqual(nivel["alcance"], "segmento")
        self.assertFalse(nivel["eliminable"])

    def test_el_detalle_enlaza_al_constructor_solo_a_quien_puede(self):
        resp = self.client.get(reverse("becas:convocatoria_detalle", args=[self.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context["puede_formulario"])
        self.assertIn(self._url("convocatoria_formulario"), resp.content.decode())

        coordinador = User.objects.create_user("coord-cons", password="x")
        coordinador.groups.add(Group.objects.get(name=ROL_COORDINADOR))
        self.client.force_login(coordinador)
        # Sin asignación sobre el segmento, no gestiona la convocatoria: ni la ve.
        resp = self.client.get(self._url("convocatoria_formulario"))
        self.assertIn(resp.status_code, (302, 403, 404))

    def test_anonimo_redirige_al_login(self):
        self.client.logout()
        resp = self.client.get(self._url("convocatoria_formulario"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("next=", resp.url)


class MoverTests(_Base):
    def test_mueve_un_campo_a_otro_grupo_y_sube_la_version(self):
        diseno = self._diseno()
        version = diseno.version
        resp = self._json(
            "formulario_mover", {"clave": clave_requisito(self.nivel), "padre": "g-cuestionario", "posicion": 0}
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["target"], "#constructor-items")
        self.assertIn("Nivel educativo", data["html"])
        item = self._item(clave_requisito(self.nivel))
        self.assertEqual(item.padre.clave, "g-cuestionario")
        self.assertEqual(item.orden, 0)
        hermanos = list(item.padre.hijos.order_by("orden", "id"))
        self.assertEqual([h.orden for h in hermanos], list(range(len(hermanos))))  # compactos
        self.assertEqual(hermanos[0], item)
        self.assertGreater(self._item(clave_pregunta(self.tenencia)).orden, 0)
        diseno.refresh_from_db()
        self.assertEqual(diseno.version, version + 1)
        self.assertEqual(diseno.actualizado_por, self.admin)

    def test_reordena_grupos_en_la_raiz(self):
        self._diseno()
        resp = self._json("formulario_mover", {"clave": "g-segmento", "padre": None, "posicion": 0})
        self.assertEqual(resp.status_code, 200, resp.content)
        grupos = [i.clave for i in items_ordenados(self._diseno()) if i.es_grupo]
        self.assertEqual(grupos[0], "g-segmento")

    def test_un_grupo_no_entra_en_otro_grupo(self):
        self._diseno()
        resp = self._json("formulario_mover", {"clave": "g-segmento", "padre": "g-cuestionario", "posicion": 0})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("grupo", resp.json()["message"].lower())

    def test_un_campo_no_queda_suelto(self):
        self._diseno()
        resp = self._json("formulario_mover", {"clave": clave_requisito(self.nivel), "padre": None, "posicion": 0})
        self.assertEqual(resp.status_code, 400)

    def test_rechaza_el_movimiento_que_deja_la_fuente_despues(self):
        """RN-6: el Apoderado depende de la fecha de nacimiento (Datos
        personales). Mover Datos personales al final rompe la condición → 400
        y no cambia nada."""
        diseno = self._diseno()
        version = diseno.version
        orden_antes = self._claves()
        resp = self._json("formulario_mover", {"clave": "g-datos_personales", "padre": None, "posicion": 10})
        self.assertEqual(resp.status_code, 400, resp.content)
        data = resp.json()
        self.assertFalse(data["ok"])
        self.assertIn("g-apoderado", data["errores"])
        self.assertEqual(self._claves(), orden_antes)  # rollback completo
        diseno.refresh_from_db()
        self.assertEqual(diseno.version, version)

    def test_payload_invalido(self):
        self._diseno()
        resp = self.client.post(self._url("formulario_mover"), data="x", content_type="application/json")
        self.assertEqual(resp.status_code, 400)
        resp = self._json("formulario_mover", {"clave": "no-existe", "padre": None, "posicion": 0})
        self.assertEqual(resp.status_code, 404)


class ItemsTests(_Base):
    def test_crear_grupo_texto_y_campo_propio(self):
        resp = self._form(
            "formulario_grupo_crear", {"etiqueta": "Situación laboral", "subtitulo": "Del titular", "canal": "ambos"}
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        grupo = self._diseno().items.get(etiqueta="Situación laboral")
        self.assertTrue(grupo.es_grupo)
        self.assertTrue(grupo.clave.startswith("g-"))
        # Al final de la raíz.
        self.assertEqual([i.clave for i in items_ordenados(self._diseno()) if i.es_grupo][-1], grupo.clave)

        resp = self._form(
            "formulario_texto_crear",
            {"padre": grupo.clave, "texto": "Contanos tu trabajo. Más info en https://chaco.gob.ar", "canal": "link"},
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        texto = grupo.hijos.get(tipo=ItemDiseno.Tipo.TEXTO)
        self.assertEqual(texto.canal, "link")
        self.assertTrue(texto.clave.startswith("t-"))

        resp = self._form(
            "formulario_propio_crear",
            {
                "padre": grupo.clave,
                "texto": "¿Trabajás?",
                "tipo": "SELECTOR",
                "opciones_texto": "Sí\nNo",
                "presentacion": "LISTA",
                "obligatorio": "on",
                "canal": "ambos",
            },
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        propio = grupo.hijos.get(tipo=ItemDiseno.Tipo.CAMPO)
        self.assertTrue(propio.es_propio)
        self.assertEqual(propio.propio["opciones"], ["Sí", "No"])
        self.assertTrue(propio.propio["obligatorio"])
        self.assertEqual(propio.orden, 1)  # después del texto
        datos = resp.json()["datos"]
        dato = next(i for i in datos["items"] if i["clave"] == propio.clave)
        self.assertTrue(dato["propio"])
        self.assertTrue(dato["eliminable"])
        self.assertEqual(dato["tipo_campo"], "SELECTOR")

    def test_texto_y_propio_necesitan_grupo_y_el_propio_selector_necesita_opciones(self):
        self._diseno()
        resp = self._form("formulario_texto_crear", {"texto": "Hola", "canal": "ambos"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("__all__", resp.json()["errors"])
        resp = self._form(
            "formulario_propio_crear",
            {
                "padre": "g-cuestionario",
                "texto": "¿Trabajás?",
                "tipo": "SELECTOR",
                "opciones_texto": "",
                "canal": "ambos",
            },
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("opciones_texto", resp.json()["errors"])

    def test_editar_grupo_etiqueta_de_catalogo_y_propio(self):
        self._diseno()
        # Grupo del catálogo: se renombra en el diseño sin tocar el catálogo.
        resp = self._form(
            "formulario_item_editar",
            {"etiqueta": "Tus datos", "subtitulo": "Como figuran en el DNI", "canal": "ambos"},
            "g-datos_personales",
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        grupo = self._item("g-datos_personales")
        self.assertEqual(grupo.etiqueta, "Tus datos")
        self.assertEqual(grupo.titulo, "Tus datos")
        self.assertEqual(grupo.grupo_catalogo.nombre, "Datos personales")
        # Campo del catálogo: solo la etiqueta; el resto lo dicta el catálogo.
        resp = self._form(
            "formulario_item_editar", {"etiqueta": "¿Qué nivel cursás?", "tipo": "INT"}, clave_requisito(self.nivel)
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        nivel = self._item(clave_requisito(self.nivel))
        self.assertEqual(nivel.titulo, "¿Qué nivel cursás?")
        self.nivel.refresh_from_db()
        self.assertEqual(self.nivel.tipo, TipoCampo.SELECTOR)
        self.assertEqual(self.nivel.texto, "Nivel educativo")
        # Vaciar la etiqueta vuelve al texto del catálogo.
        self._form("formulario_item_editar", {"etiqueta": ""}, clave_requisito(self.nivel))
        self.assertEqual(self._item(clave_requisito(self.nivel)).titulo, "Nivel educativo")

    def test_eliminar_solo_textos_propios_y_grupos_vacios(self):
        self._diseno()
        # Requisito del catálogo: no.
        resp = self._json("formulario_item_eliminar", {}, clave_requisito(self.nivel))
        self.assertEqual(resp.status_code, 400)
        self.assertTrue(self._diseno().items.filter(clave=clave_requisito(self.nivel)).exists())
        # Grupo con hijos: no.
        resp = self._json("formulario_item_eliminar", {}, "g-segmento")
        self.assertEqual(resp.status_code, 400)
        # Grupo vacío: sí.
        self._form("formulario_grupo_crear", {"etiqueta": "Vacío", "canal": "ambos"})
        vacio = self._diseno().items.get(etiqueta="Vacío")
        resp = self._json("formulario_item_eliminar", {}, vacio.clave)
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertFalse(self._diseno().items.filter(pk=vacio.pk).exists())
        # Texto: sí.
        self._form("formulario_texto_crear", {"padre": "g-cuestionario", "texto": "Aviso", "canal": "ambos"})
        texto = self._diseno().items.get(tipo=ItemDiseno.Tipo.TEXTO)
        resp = self._json("formulario_item_eliminar", {}, texto.clave)
        self.assertEqual(resp.status_code, 200)

    def test_restablecer_vuelve_al_plan_por_defecto(self):
        self._diseno()
        self._form("formulario_grupo_crear", {"etiqueta": "Extra", "canal": "ambos"})
        self._form(
            "formulario_item_editar", {"etiqueta": "Tus datos", "subtitulo": "", "canal": "ambos"}, "g-datos_personales"
        )
        resp = self._json("formulario_restablecer", {})
        self.assertEqual(resp.status_code, 200, resp.content)
        diseno = self._diseno()
        self.assertFalse(diseno.items.filter(etiqueta="Extra").exists())
        self.assertEqual(diseno.items.get(clave="g-datos_personales").etiqueta, "")
        self.assertGreaterEqual(diseno.version, 3)


class CondicionTests(_Base):
    def test_guarda_una_condicion_valida_sobre_un_campo_anterior(self):
        self._diseno()
        # El certificado (segmento, orden 2) depende del nivel (segmento, orden 1).
        condicion = {
            "modo": "todas",
            "reglas": [{"fuente": clave_requisito(self.nivel), "op": "es", "valor": "Secundario"}],
        }
        resp = self._json("formulario_condicion", {"condicion": condicion}, clave_requisito(self.certificado))
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(self._item(clave_requisito(self.certificado)).condicion, condicion)
        self.assertIn("Condicional", resp.json()["html"])

    def test_rechaza_fuente_posterior_operador_ajeno_y_sin_valor(self):
        self._diseno()
        posterior = {
            "modo": "todas",
            "reglas": [{"fuente": clave_requisito(self.certificado), "op": "adjuntado", "valor": None}],
        }
        resp = self._json("formulario_condicion", {"condicion": posterior}, clave_requisito(self.nivel))
        self.assertEqual(resp.status_code, 400)
        self.assertIsNone(self._item(clave_requisito(self.nivel)).condicion)

        ajeno = {"modo": "todas", "reglas": [{"fuente": clave_requisito(self.nivel), "op": "edad_menor", "valor": 18}]}
        resp = self._json("formulario_condicion", {"condicion": ajeno}, clave_requisito(self.certificado))
        self.assertEqual(resp.status_code, 400)
        self.assertIn("no aplica", resp.json()["message"])

        sin_valor = {"modo": "todas", "reglas": [{"fuente": clave_requisito(self.nivel), "op": "es", "valor": ""}]}
        resp = self._json("formulario_condicion", {"condicion": sin_valor}, clave_requisito(self.certificado))
        self.assertEqual(resp.status_code, 400)

    def test_quitar_la_condicion(self):
        self._diseno()
        apoderado = self._item("g-apoderado")
        self.assertIsNotNone(apoderado.condicion)  # nace con edad < 18 desde el catálogo
        resp = self._json("formulario_condicion", {"condicion": None}, "g-apoderado")
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertIsNone(self._item("g-apoderado").condicion)
        self.assertIn("se muestra siempre", resp.json()["message"])

    def test_sin_reglas_equivale_a_sin_condicion(self):
        self._diseno()
        resp = self._json("formulario_condicion", {"condicion": {"modo": "alguna", "reglas": []}}, "g-apoderado")
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(self._item("g-apoderado").condicion)


class PermisosTests(_Base):
    def test_las_mutaciones_exigen_post_y_permiso(self):
        self._diseno()
        self.assertEqual(self.client.get(self._url("formulario_mover")).status_code, 405)
        self.assertEqual(self.client.get(self._url("formulario_restablecer")).status_code, 405)
        self.client.logout()
        resp = self._json("formulario_mover", {"clave": "g-segmento", "padre": None, "posicion": 0})
        self.assertIn(resp.status_code, (302, 403))
        territorial = User.objects.create_user("terri-cons", password="x")
        self.client.force_login(territorial)
        resp = self._json("formulario_mover", {"clave": "g-segmento", "padre": None, "posicion": 0})
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()["ok"], False)
