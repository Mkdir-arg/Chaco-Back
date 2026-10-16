"""P21 · Relevamientos edilicios: listado y asignación del coordinador (MVP v2, etapa 4 · #701).

Lo que se fija acá, y por qué:

1. **El menú «Relevamientos» es del coordinador.** Aparece con ``inspeccion.asignar`` en el
   programa y no aparece para quien tiene todo lo demás de Dispositivos —incluido el admin—:
   el agente territorial recibe la tarea en la app y no entra a esta pantalla.
2. **El listado es exactamente `inspecciones_visibles`**, y las acciones de cada fila siguen
   el alcance del coordinador sobre **ese** edificio: lo que ve por otro camino lo ve sin
   poder tocarlo.
3. **Crear, reasignar y cancelar van por POST con CSRF y por el servicio.** Las guardas son
   la capacidad (la vista) y el alcance (el servicio); los errores vuelven al modal por campo.
4. **El selector de agentes no ofrece al personal del edificio** (`AGENTE_DEBE_SER_EXTERNO`).
5. **El costo de la página no crece con los relevamientos** (presupuesto en
   `scripts/perf_budgets.json`, sección `servicios`).
"""

import json
import re
from datetime import timedelta
from pathlib import Path

from django.db import connection
from django.test import Client, tag
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from programas.models import Edificio, InspeccionEdificio
from programas.services import inspecciones as servicio
from programas.services.inspecciones import Situacion, filtrar_por_situacion, resumen_listado, situacion_de
from programas.tests.test_dispositivos_inspecciones import TODAS_DE_DISPOSITIVOS, BaseInspecciones

URL_LISTA = reverse("dispositivos:relevamientos")
AJAX = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}
PRESUPUESTOS = Path(__file__).resolve().parents[2] / "scripts" / "perf_budgets.json"
CLAVE_PRESUPUESTO = "dispositivos_relevamientos_listado"
Estado = InspeccionEdificio.Estado


def _sin_token(contenido):
    """La página de error trae el token CSRF del shell (en el form y en el JS), distinto en cada respuesta."""

    return re.sub(rb"[A-Za-z0-9]{32,}", b"TOKEN", contenido)


class BaseListado(BaseInspecciones):
    def setUp(self):
        super().setUp()
        # Coordinador «puro»: solo `inspeccion.asignar`, asignado al parador. Sin un
        # `dispositivo.ver` que le abra el predio por otro camino.
        self.coord = self._usuario("coord", ("inspeccion.asignar",), [self.parador])

    def _cliente(self, usuario, csrf=False):
        cliente = Client(enforce_csrf_checks=csrf)
        cliente.force_login(usuario)
        return cliente

    def _url(self, nombre, *args):
        return reverse(f"dispositivos:{nombre}", args=args)

    def _edificio_del_parador(self, codigo):
        edificio = Edificio.objects.create(codigo=codigo, nombre=f"Edificio {codigo}")
        edificio.dispositivos.add(self.parador)
        return edificio


class PrivacidadAsignacionTests(BaseListado):
    def setUp(self):
        super().setUp()
        # Configurar da alcance global: acá la única condición ausente es coordinar B.
        capacidades = [c for c in TODAS_DE_DISPOSITIVOS if c != "programa.configurar"]
        self.lector = self._usuario("coord_a", capacidades, [self.parador])
        lector_b = self._usuario("lector_b", [c for c in capacidades if c != "inspeccion.asignar"], [self.cis])
        self.lector.groups.add(*lector_b.groups.all())
        self.agente.first_name = "Agente exclusivo B"
        self.agente.save(update_fields=["first_name"])
        self.otro_agente.first_name = "Agente visible A"
        self.otro_agente.save(update_fields=["first_name"])
        admin = self._usuario("admin_creador", TODAS_DE_DISPOSITIVOS)
        self.relevamiento_b = servicio.crear_inspeccion(
            admin, edificio=self.edificio_cis, asignado_a=self.agente, fecha_vencimiento=self.vence
        )
        self._crear(agente=self.otro_agente)

    def test_la_fila_oculta_el_nombre_sin_alcance_en_cada_estado(self):
        cliente = self._cliente(self.lector)
        for estado in Estado.values:
            with self.subTest(estado=estado):
                InspeccionEdificio.objects.filter(pk=self.relevamiento_b.pk).update(
                    estado=estado,
                    realizada_en=timezone.now() if estado == Estado.REALIZADA else None,
                    realizada_por=self.agente if estado == Estado.REALIZADA else None,
                    criticidad=InspeccionEdificio.Criticidad.BAJA if estado == Estado.REALIZADA else "",
                    motivo_cancelacion="Se reprograma" if estado == Estado.CANCELADA else "",
                )
                respuesta = cliente.get(URL_LISTA)
                self.assertEqual(respuesta.status_code, 200)
                fila = re.search(r"<tr[^>]*>\s*<td[^>]*>Edificio CIS.*?</tr>", respuesta.content.decode(), re.S)
                self.assertIsNotNone(fila)
                self.assertNotIn("Agente exclusivo B", fila.group())
                self.assertIn("Agente visible A", respuesta.content.decode())

    def test_la_pildora_solo_ofrece_agentes_con_asignacion_visible(self):
        respuesta = self._cliente(self.lector).get(URL_LISTA)
        self.assertEqual(respuesta.status_code, 200)
        for solapa in respuesta.context["solapas"]:
            opciones = next(p["opciones"] for p in solapa["pildoras"] if p["nombre"] == "asignado_a")
            self.assertEqual(opciones, [(str(self.otro_agente.pk), "Agente visible A")])


class MenuTests(BaseListado):
    def test_quien_tiene_todo_menos_asignar_no_ve_el_menu_ni_entra(self):
        todo_menos = [c for c in TODAS_DE_DISPOSITIVOS if c != "inspeccion.asignar"]
        usuario = self._usuario("todo_menos_asignar", todo_menos, [self.parador])
        cliente = self._cliente(usuario)

        respuesta = cliente.get(reverse("dispositivos:lista"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, reverse("dispositivos:lista"))  # el grupo Dispositivos sí está
        self.assertNotContains(respuesta, f'href="{URL_LISTA}"')
        self.assertEqual(cliente.get(URL_LISTA).status_code, 403)

    def test_el_agente_territorial_no_ve_el_menu(self):
        respuesta = self._cliente(self.agente).get(reverse("core:inicio"))
        self.assertNotContains(respuesta, f'href="{URL_LISTA}"')

    def test_el_coordinador_ve_el_menu_y_queda_marcado(self):
        respuesta = self._cliente(self.coord).get(URL_LISTA)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, f'href="{URL_LISTA}"')
        self.assertContains(respuesta, "Relevamientos")


def _filas(respuesta, clave="en_curso"):
    return next(s for s in respuesta.context["solapas"] if s["clave"] == clave)["filas"]


def _solapa(respuesta, clave):
    return next(s for s in respuesta.context["solapas"] if s["clave"] == clave)


class ListadoTests(BaseListado):
    def _ajeno(self):
        admin = self._usuario("admin", TODAS_DE_DISPOSITIVOS)
        return servicio.crear_inspeccion(
            self._fresco(admin),
            edificio=self.edificio_cis,
            asignado_a=self._fresco(self.agente),
            fecha_vencimiento=self.vence,
        )

    def test_lista_exactamente_lo_visible(self):
        del_predio = self._crear()
        ajeno = self._ajeno()

        respuesta = self._cliente(self.coord).get(URL_LISTA)

        ids = [r.pk for r in _filas(respuesta)]
        self.assertEqual(ids, [del_predio.pk])
        self.assertNotIn(ajeno.pk, ids)
        self.assertContains(respuesta, "Predio Resistencia")
        self.assertNotContains(respuesta, "Edificio CIS")

    def test_la_solapa_en_curso_no_muestra_completados_ni_cancelados(self):
        completado = self._crear()
        servicio.registrar_resultado(
            self._fresco(self.agente), completado, criticidad=InspeccionEdificio.Criticidad.BAJA
        )
        cancelado = self._crear()
        servicio.cancelar_inspeccion(self._fresco(self.coord), cancelado, "Duplicado")
        en_curso = self._crear()

        respuesta = self._cliente(self.coord).get(URL_LISTA)

        self.assertEqual([r.pk for r in _filas(respuesta)], [en_curso.pk])
        self.assertEqual([r.pk for r in _filas(respuesta, "completados")], [completado.pk])
        self.assertEqual([r.pk for r in _filas(respuesta, "cancelados")], [cancelado.pk])
        # Los contadores salen del aggregate y tienen que coincidir con lo que cada solapa lista.
        self.assertEqual([s["total"] for s in respuesta.context["solapas"]], [1, 1, 0, 1])
        self.assertContains(respuesta, 'role="tab" id="tab-en_curso" aria-controls="panel-en_curso"')

    def test_la_solapa_activa_viene_de_la_url_y_una_invalida_cae_en_en_curso(self):
        cliente = self._cliente(self.coord)
        self.assertEqual(cliente.get(URL_LISTA, {"tab": "cancelados"}).context["solapa_actual"], "cancelados")
        self.assertEqual(cliente.get(URL_LISTA, {"tab": "inventada"}).context["solapa_actual"], "en_curso")

    def test_lo_visible_sin_alcance_se_ve_con_las_acciones_bloqueadas(self):
        # Coordina el parador y además opera el CIS: ve el relevamiento del CIS por
        # `dispositivo.ver`, pero no puede asignar ahí.
        mixto = self._usuario("mixto", ("inspeccion.asignar",), [self.parador])
        rol_ver = self._usuario("mixto_ver", ("dispositivo.ver",), [self.cis]).groups.first()
        mixto.groups.add(rol_ver)
        del_cis = self._ajeno()
        del_predio = self._crear()

        respuesta = self._cliente(self._fresco(mixto)).get(URL_LISTA)

        filas = {r.pk: r for r in _filas(respuesta)}
        self.assertEqual(set(filas), {del_cis.pk, del_predio.pk})
        self.assertFalse(filas[del_cis.pk].gestionable)
        self.assertIn("Fuera de tu alcance", filas[del_cis.pk].motivo_reasignar)
        self.assertIn("Fuera de tu alcance", filas[del_cis.pk].motivo_cancelar)
        self.assertTrue(filas[del_predio.pk].gestionable)
        self.assertEqual(filas[del_predio.pk].motivo_cancelar, "")
        # La acción principal se ve solo donde se puede usar; donde no, queda en el menú con su motivo.
        self.assertContains(respuesta, 'aria-label="Reasignar el relevamiento de Predio Resistencia"')
        self.assertNotContains(respuesta, 'aria-label="Reasignar el relevamiento de Edificio CIS"')

    def test_lo_cancelado_solo_ofrece_ver_informe(self):
        inspeccion = self._crear()
        servicio.cancelar_inspeccion(self._fresco(self.coord), inspeccion, "Duplicado")

        respuesta = self._cliente(self.coord).get(URL_LISTA, {"tab": "cancelados"})

        self.assertTrue(_filas(respuesta, "cancelados")[0].con_acciones)
        self.assertContains(respuesta, f"menu-fila-relevamiento-{inspeccion.pk}")
        self.assertContains(respuesta, reverse("dispositivos:relevamiento_informe", args=[inspeccion.pk]))
        self.assertContains(respuesta, "Ver informe")
        self.assertNotContains(respuesta, f"cancelar={inspeccion.pk}")
        self.assertNotContains(respuesta, "Marcar como revisado")
        self.assertNotContains(respuesta, "Reasignar el relevamiento de")

    def test_lo_completado_solo_ofrece_ver_el_informe(self):
        """Terminal, pero no sin acciones: queda leerlo. Ni reasignar ni cancelar."""

        inspeccion = self._crear()
        servicio.registrar_resultado(
            self._fresco(self.agente), inspeccion, criticidad=InspeccionEdificio.Criticidad.BAJA
        )

        respuesta = self._cliente(self.coord).get(URL_LISTA, {"tab": "completados"})
        html = respuesta.content.decode()

        self.assertTrue(_filas(respuesta, "completados")[0].con_acciones)
        self.assertIn(f"menu-fila-relevamiento-{inspeccion.pk}", html)
        self.assertIn(reverse("dispositivos:relevamiento_informe", args=[inspeccion.pk]), html)
        self.assertNotIn("Reasignar el relevamiento de", html)
        self.assertNotIn(f"cancelar={inspeccion.pk}", html)

    def test_pildoras_filtran_por_situacion_y_agente(self):
        hoy = timezone.localdate()
        vencido = self._crear()
        InspeccionEdificio.objects.filter(pk=vencido.pk).update(fecha_vencimiento=hoy - timedelta(days=1))
        al_dia = self._crear(edificio=self._edificio_del_parador("ED-2"), agente=self.otro_agente)
        InspeccionEdificio.objects.filter(pk=al_dia.pk).update(fecha_vencimiento=hoy + timedelta(days=60))
        cliente = self._cliente(self.coord)

        self.assertEqual([r.pk for r in _filas(cliente.get(URL_LISTA, {"estado": "VENCIDA"}))], [vencido.pk])
        self.assertEqual([r.pk for r in _filas(cliente.get(URL_LISTA, {"estado": "AL_DIA"}))], [al_dia.pk])
        por_agente = cliente.get(URL_LISTA, {"asignado_a": self.otro_agente.pk})
        self.assertEqual([r.pk for r in _filas(por_agente)], [al_dia.pk])
        self.assertEqual(_solapa(por_agente, "en_curso")["total"], 1)

        respuesta = cliente.get(URL_LISTA, {"estado": "POR_VENCER"})
        self.assertEqual(_filas(respuesta), [])
        self.assertContains(respuesta, "Ningún relevamiento coincide con los filtros")

    def test_el_agente_filtra_las_tres_solapas_y_sus_contadores(self):
        for edificio, agente in ((self.predio, self.agente), (self._edificio_del_parador("ED-2"), self.otro_agente)):
            inspeccion = self._crear(edificio=edificio, agente=agente)
            servicio.registrar_resultado(
                self._fresco(agente), inspeccion, criticidad=InspeccionEdificio.Criticidad.MEDIA
            )

        respuesta = self._cliente(self.coord).get(URL_LISTA, {"asignado_a": self.otro_agente.pk})

        completados = _solapa(respuesta, "completados")
        self.assertEqual([r.asignado_a_id for r in completados["filas"]], [self.otro_agente.pk])
        self.assertEqual(completados["total"], 1)
        self.assertEqual(respuesta.context["resumen"]["solapa_completados"], 1)

    def test_la_paginacion_no_arrastra_el_modal(self):
        primera = None
        for n in range(26):
            inspeccion = self._crear(edificio=self._edificio_del_parador(f"ED-P{n}"))
            primera = primera or inspeccion

        respuesta = self._cliente(self.coord).get(
            URL_LISTA, {"tab": "en_curso", "reasignar": primera.pk, "asignado_a": self.agente.pk}
        )

        self.assertIn("form_reasignar", respuesta.context)
        siguiente = re.search(r'href="(\?en_curso_page=2[^"]*)"', respuesta.content.decode())
        self.assertIsNotNone(siguiente, "falta el enlace a la página 2 de En curso")
        enlace = siguiente.group(1)
        self.assertNotIn("reasignar", enlace)
        self.assertIn("tab=en_curso", enlace)
        self.assertIn(f"asignado_a={self.agente.pk}", enlace)

    def test_al_dia_se_lee_igual_en_la_tarjeta_el_badge_y_la_pildora(self):
        al_dia = self._crear()
        InspeccionEdificio.objects.filter(pk=al_dia.pk).update(
            fecha_vencimiento=timezone.localdate() + timedelta(days=60)
        )
        respuesta = self._cliente(self.coord).get(URL_LISTA)

        fila = _filas(respuesta)[0]
        self.assertEqual((fila.situacion, fila.situacion_texto), (Situacion.AL_DIA, "Al día"))
        self.assertIn((Situacion.AL_DIA, "Al día"), _solapa(respuesta, "en_curso")["pildoras"][0]["opciones"])
        self.assertContains(respuesta, "Al día", count=3)  # tarjeta, opción de la píldora y badge

    def test_parametros_con_digitos_no_ascii_no_rompen(self):
        cliente = self._cliente(self.coord)
        for clave in ("asignar", "reasignar", "cancelar", "asignado_a", "en_curso_page"):
            for valor in ("²", "١"):
                respuesta = cliente.get(URL_LISTA, {clave: valor})
                self.assertEqual(respuesta.status_code, 200, (clave, valor))

    def test_abrir_un_modal_no_cuenta_como_filtro(self):
        respuesta = self._cliente(self.coord).get(URL_LISTA, {"asignar": self.predio.pk})
        self.assertContains(respuesta, "No hay relevamientos en curso")
        self.assertNotContains(respuesta, "Ningún relevamiento coincide con los filtros")
        self.assertContains(respuesta, "Asignar relevamiento · Predio Resistencia")

    def test_el_paso_uno_conserva_la_solapa_y_los_filtros(self):
        respuesta = self._cliente(self.coord).get(
            URL_LISTA, {"tab": "completados", "asignado_a": self.agente.pk, "nuevo": "1", "q": "x"}
        )
        self.assertEqual(
            respuesta.context["ocultos_nuevo"], [("tab", "completados"), ("asignado_a", str(self.agente.pk))]
        )
        self.assertContains(respuesta, '<input type="hidden" name="tab" value="completados">', count=2)

    def test_situacion_derivada_y_resumen(self):
        hoy = timezone.localdate()
        inspeccion = self._crear()
        for dias, esperado in (
            (-1, Situacion.VENCIDA),
            (0, Situacion.POR_VENCER),
            (30, Situacion.POR_VENCER),
            (31, Situacion.AL_DIA),
        ):
            inspeccion.fecha_vencimiento = hoy + timedelta(days=dias)
            self.assertEqual(situacion_de(inspeccion, hoy), esperado, dias)
        InspeccionEdificio.objects.filter(pk=inspeccion.pk).update(fecha_vencimiento=hoy - timedelta(days=2))
        qs = InspeccionEdificio.objects.all()
        self.assertEqual(
            resumen_listado(qs, hoy=hoy),
            {
                "asignados": 1,
                "vencidos": 1,
                "por_vencer": 0,
                "al_dia": 0,
                "solapa_en_curso": 1,
                "solapa_completados": 0,
                "solapa_revisados": 0,
                "solapa_cancelados": 0,
            },
        )
        self.assertEqual(resumen_listado(qs, situacion=Situacion.AL_DIA, hoy=hoy)["solapa_en_curso"], 0)
        self.assertEqual(filtrar_por_situacion(qs, Situacion.VENCIDA, hoy).count(), 1)
        self.assertEqual(filtrar_por_situacion(qs, Situacion.POR_VENCER, hoy).count(), 0)


class SelectorDeAgentesTests(BaseListado):
    def _opciones(self, respuesta, form):
        return {u.pk for u in respuesta.context[form].fields["asignado_a"].queryset}

    def test_el_personal_del_edificio_no_aparece_al_asignar(self):
        respuesta = self._cliente(self.coord).get(URL_LISTA, {"asignar": self.predio.pk})

        opciones = self._opciones(respuesta, "form_asignar")
        self.assertIn(self.agente.pk, opciones)
        self.assertNotIn(self.personal_parador.pk, opciones)
        self.assertNotContains(respuesta, f'value="{self.personal_parador.pk}"')

    def test_el_personal_del_edificio_no_aparece_al_reasignar(self):
        inspeccion = self._crear()
        respuesta = self._cliente(self.coord).get(URL_LISTA, {"reasignar": inspeccion.pk})

        opciones = self._opciones(respuesta, "form_reasignar")
        self.assertIn(self.otro_agente.pk, opciones)
        self.assertNotIn(self.personal_parador.pk, opciones)

    def test_el_modal_de_un_edificio_fuera_de_alcance_no_se_abre(self):
        respuesta = self._cliente(self.coord).get(URL_LISTA, {"asignar": self.edificio_cis.pk})
        self.assertNotIn("form_asignar", respuesta.context)

    def test_reasignar_y_cancelar_de_otro_alcance_no_abren_el_modal(self):
        admin = self._usuario("admin", TODAS_DE_DISPOSITIVOS)
        ajeno = servicio.crear_inspeccion(
            self._fresco(admin),
            edificio=self.edificio_cis,
            asignado_a=self._fresco(self.agente),
            fecha_vencimiento=self.vence,
        )
        cliente = self._cliente(self.coord)
        for clave, form in (("reasignar", "form_reasignar"), ("cancelar", "form_cancelar")):
            respuesta = cliente.get(URL_LISTA, {clave: ajeno.pk})
            self.assertNotIn(form, respuesta.context)
            self.assertNotContains(respuesta, "Edificio CIS")


class CrearTests(BaseListado):
    def _datos(self, **extra):
        datos = {"asignado_a": self.agente.pk, "fecha_vencimiento": self.vence.isoformat(), "indicaciones": "Techos"}
        datos.update(extra)
        return datos

    def test_crea_y_vuelve_al_listado_con_los_filtros(self):
        url = self._url("relevamiento_asignar", self.predio.pk)
        respuesta = self._cliente(self.coord).post(url, self._datos(volver="estado=ASIGNADA&asignar=9"), **AJAX)

        self.assertEqual(respuesta.status_code, 200)
        cuerpo = respuesta.json()
        self.assertTrue(cuerpo["ok"])
        self.assertEqual(cuerpo["redirect"], f"{URL_LISTA}?estado=ASIGNADA")
        inspeccion = InspeccionEdificio.objects.get()
        self.assertEqual((inspeccion.edificio, inspeccion.asignado_a_id), (self.predio, self.agente.pk))
        self.assertEqual(inspeccion.creado_por_id, self.coord.pk)

    def test_sin_csrf_no_crea(self):
        url = self._url("relevamiento_asignar", self.predio.pk)
        respuesta = self._cliente(self.coord, csrf=True).post(url, self._datos(), **AJAX)
        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(InspeccionEdificio.objects.exists())

    def test_sin_la_capacidad_no_crea(self):
        todo_menos = [c for c in TODAS_DE_DISPOSITIVOS if c != "inspeccion.asignar"]
        usuario = self._usuario("todo_menos_asignar", todo_menos, [self.parador])
        url = self._url("relevamiento_asignar", self.predio.pk)
        respuesta = self._cliente(usuario).post(url, self._datos(), **AJAX)
        self.assertEqual(respuesta.status_code, 403)
        # Lo frena la capacidad, en la vista, antes de llegar al alcance del servicio.
        self.assertEqual(respuesta.json()["message"], "No tenés permiso para realizar esta acción.")
        self.assertFalse(InspeccionEdificio.objects.exists())

    def test_fuera_de_alcance_responde_igual_que_un_edificio_inexistente(self):
        # Si respondiera 400 o 403 según el agente, se podría saber qué edificios existen y
        # quién es personal de instituciones ajenas.
        cliente = self._cliente(self.coord)
        for agente in (self.agente, self.personal_parador):
            ajeno = cliente.post(
                self._url("relevamiento_asignar", self.edificio_cis.pk), self._datos(asignado_a=agente.pk), **AJAX
            )
            inexistente = cliente.post(
                self._url("relevamiento_asignar", 999999), self._datos(asignado_a=agente.pk), **AJAX
            )
            self.assertEqual(ajeno.status_code, 404)
            self.assertEqual(
                (ajeno.status_code, _sin_token(ajeno.content)),
                (inexistente.status_code, _sin_token(inexistente.content)),
            )
        self.assertFalse(InspeccionEdificio.objects.exists())

    def test_el_personal_del_edificio_vuelve_como_error_del_campo(self):
        url = self._url("relevamiento_asignar", self.predio.pk)
        respuesta = self._cliente(self.coord).post(url, self._datos(asignado_a=self.personal_parador.pk), **AJAX)
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("asignado_a", respuesta.json()["errors"])
        self.assertFalse(InspeccionEdificio.objects.exists())

    def test_las_reglas_del_servicio_vuelven_por_campo(self):
        url = self._url("relevamiento_asignar", self.predio.pk)
        cliente = self._cliente(self.coord)
        ayer = (timezone.localdate() - timedelta(days=1)).isoformat()

        errores = cliente.post(url, self._datos(fecha_vencimiento=ayer), **AJAX).json()["errors"]
        self.assertEqual(list(errores), ["fecha_vencimiento"])

        self._crear()
        errores = cliente.post(url, self._datos(), **AJAX).json()["errors"]
        self.assertEqual(list(errores), ["edificio"])
        self.assertEqual(InspeccionEdificio.objects.count(), 1)

    def test_campos_obligatorios(self):
        url = self._url("relevamiento_asignar", self.predio.pk)
        errores = self._cliente(self.coord).post(url, {}, **AJAX).json()["errors"]
        self.assertEqual(set(errores), {"asignado_a", "fecha_vencimiento"})


class ReasignarYCancelarTests(BaseListado):
    def setUp(self):
        super().setUp()
        self.inspeccion = self._crear()

    def test_reasigna(self):
        url = self._url("relevamiento_reasignar", self.inspeccion.pk)
        respuesta = self._cliente(self.coord).post(url, {"asignado_a": self.otro_agente.pk}, **AJAX)
        self.assertTrue(respuesta.json()["ok"])
        self.inspeccion.refresh_from_db()
        self.assertEqual(self.inspeccion.asignado_a_id, self.otro_agente.pk)

    def test_reasignar_al_mismo_agente_es_error_del_campo(self):
        url = self._url("relevamiento_reasignar", self.inspeccion.pk)
        respuesta = self._cliente(self.coord).post(url, {"asignado_a": self.agente.pk}, **AJAX)
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("asignado_a", respuesta.json()["errors"])

    def test_reasignar_sin_csrf_o_sin_capacidad_no_cambia_nada(self):
        url = self._url("relevamiento_reasignar", self.inspeccion.pk)
        self.assertEqual(
            self._cliente(self.coord, csrf=True).post(url, {"asignado_a": self.otro_agente.pk}).status_code, 403
        )
        operador = self._fresco(self.operador_geriatrico)  # ve el relevamiento, no puede asignar
        self.assertEqual(self._cliente(operador).post(url, {"asignado_a": self.otro_agente.pk}).status_code, 403)
        self.inspeccion.refresh_from_db()
        self.assertEqual(self.inspeccion.asignado_a_id, self.agente.pk)

    def test_reasignar_lo_que_no_ve_es_404(self):
        otro = self._usuario("coord_cis", ("inspeccion.asignar",), [self.cis])
        url = self._url("relevamiento_reasignar", self.inspeccion.pk)
        respuesta = self._cliente(otro).post(url, {"asignado_a": self.otro_agente.pk}, **AJAX)
        self.assertEqual(respuesta.status_code, 404)

    def test_visible_sin_alcance_es_403_del_servicio(self):
        mixto = self._usuario("mixto", ("inspeccion.asignar",), [self.cis])
        mixto.groups.add(self._usuario("mixto_ver", ("dispositivo.ver",), [self.geriatrico]).groups.first())
        url = self._url("relevamiento_cancelar", self.inspeccion.pk)
        respuesta = self._cliente(self._fresco(mixto)).post(url, {"motivo": "Duplicado"}, **AJAX)
        self.assertEqual(respuesta.status_code, 403)
        self.inspeccion.refresh_from_db()
        self.assertEqual(self.inspeccion.estado, Estado.ASIGNADA)

    def test_cancelar_exige_motivo_y_vuelve_por_campo(self):
        url = self._url("relevamiento_cancelar", self.inspeccion.pk)
        respuesta = self._cliente(self.coord).post(url, {"motivo": "   "}, **AJAX)
        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(list(respuesta.json()["errors"]), ["motivo"])

    def test_cancela_y_no_se_cancela_dos_veces(self):
        url = self._url("relevamiento_cancelar", self.inspeccion.pk)
        cliente = self._cliente(self.coord)
        self.assertTrue(cliente.post(url, {"motivo": "Se mudó la institución"}, **AJAX).json()["ok"])
        self.inspeccion.refresh_from_db()
        self.assertEqual(
            (self.inspeccion.estado, self.inspeccion.motivo_cancelacion), (Estado.CANCELADA, "Se mudó la institución")
        )

        respuesta = cliente.post(url, {"motivo": "Otra vez"}, **AJAX)
        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(list(respuesta.json()["errors"]), ["__all__"])

    def test_sin_ajax_redirige_con_aviso(self):
        url = self._url("relevamiento_cancelar", self.inspeccion.pk)
        respuesta = self._cliente(self.coord).post(url, {"motivo": "Duplicado", "volver": "page=2"})
        self.assertRedirects(respuesta, f"{URL_LISTA}?page=2", fetch_redirect_response=False)


class SinRelevarTests(BaseListado):
    """La cuarta solapa no lista relevamientos: lista EDIFICIOS que nunca se relevaron.

    Lo que falta no tiene fila en `InspeccionEdificio`, así que no puede salir de las otras
    tres. «Relevado» es lo mismo que mide el semáforo: una realizada, no una asignada.
    """

    def _sin_relevar(self, respuesta):
        return respuesta.context["sin_relevar"]

    def test_lista_los_edificios_del_alcance_que_nunca_se_relevaron(self):
        otro = self._edificio_del_parador("ED-2")

        respuesta = self._cliente(self.coord).get(URL_LISTA, {"tab": "sin_relevar"})
        solapa = self._sin_relevar(respuesta)

        self.assertEqual({e.pk for e in solapa["filas"]}, {self.predio.pk, otro.pk})
        self.assertEqual(solapa["total"], 2)
        self.assertContains(respuesta, "Sin relevar nunca")

    def test_el_edificio_relevado_sale_de_la_solapa(self):
        inspeccion = self._crear()
        self._edificio_del_parador("ED-2")

        servicio.registrar_resultado(
            self._fresco(self.agente), inspeccion, criticidad=InspeccionEdificio.Criticidad.BAJA
        )
        solapa = self._sin_relevar(self._cliente(self.coord).get(URL_LISTA, {"tab": "sin_relevar"}))

        self.assertEqual([e.codigo for e in solapa["filas"]], ["ED-2"])

    def test_un_cancelado_no_cuenta_como_relevado(self):
        """No dejó resultado: el edificio sigue sin relevar y hay que volver a asignarlo."""

        inspeccion = self._crear()
        servicio.cancelar_inspeccion(self._fresco(self.coord), inspeccion, "Duplicado")

        solapa = self._sin_relevar(self._cliente(self.coord).get(URL_LISTA, {"tab": "sin_relevar"}))

        self.assertEqual([e.pk for e in solapa["filas"]], [self.predio.pk])
        self.assertTrue(solapa["filas"][0].url_asignar)

    def test_un_edificio_de_otro_alcance_no_aparece(self):
        respuesta = self._cliente(self.coord).get(URL_LISTA, {"tab": "sin_relevar"})

        self.assertNotIn(self.edificio_cis.pk, [e.pk for e in self._sin_relevar(respuesta)["filas"]])
        self.assertNotContains(respuesta, "Edificio CIS")

    def test_un_edificio_inactivo_no_aparece(self):
        """No se puede relevar (`crear_inspeccion` lo rechaza): ofrecer «Asignar» sería mentir."""

        inactivo = self._edificio_del_parador("ED-OFF")
        Edificio.objects.filter(pk=inactivo.pk).update(activo=False)

        solapa = self._sin_relevar(self._cliente(self.coord).get(URL_LISTA, {"tab": "sin_relevar"}))

        self.assertEqual([e.pk for e in solapa["filas"]], [self.predio.pk])

    def test_el_que_ya_tiene_uno_en_curso_aparece_sin_el_boton_asignar(self):
        self._crear()
        libre = self._edificio_del_parador("ED-2")

        respuesta = self._cliente(self.coord).get(URL_LISTA, {"tab": "sin_relevar"})
        por_pk = {e.pk: e for e in self._sin_relevar(respuesta)["filas"]}

        self.assertEqual(por_pk[self.predio.pk].url_asignar, "")
        self.assertEqual(por_pk[self.predio.pk].asignado_a, self.agente.username)
        self.assertTrue(por_pk[libre.pk].url_asignar)
        self.assertContains(respuesta, "ya tiene uno en curso")
        self.assertContains(respuesta, "Sin asignar")

    def test_asignar_abre_el_modal_que_ya_existe(self):
        libre = self._edificio_del_parador("ED-2")

        respuesta = self._cliente(self.coord).get(URL_LISTA, {"tab": "sin_relevar", "asignar": libre.pk})

        self.assertIn("form_asignar", respuesta.context)
        self.assertEqual(respuesta.context["edificio_asignar"], libre)

    def test_pagina_con_su_propio_parametro_sin_mover_las_otras_solapas(self):
        for n in range(26):
            self._edificio_del_parador(f"ED-P{n}")

        respuesta = self._cliente(self.coord).get(URL_LISTA, {"tab": "sin_relevar", "sin_relevar_page": 2})
        solapa = self._sin_relevar(respuesta)

        self.assertEqual(solapa["total"], 27)
        self.assertEqual(len(solapa["filas"]), 2)
        self.assertIn("tab=sin_relevar", solapa["filtros_qs"])


class PildorasPorPanelTests(BaseListado):
    """MINOR del Cambio 279: filtrar desde otra solapa tiene que quedarse en esa solapa.

    La solapa la cambia Alpine en el navegador y el formulario de filtros lo arma el
    servidor, así que el oculto `tab` es el de **cada panel**, no el que resolvió el
    servidor (patrón de P4).
    """

    def _ocultos(self, html, clave):
        """Los ocultos `tab` del panel: de su `id` al del panel siguiente, sin los modales."""

        cuerpo = html.split("x-becas-modal")[0]
        panel = cuerpo.split(f'id="panel-{clave}"')[1]
        siguiente = panel.find('id="panel-')
        return re.findall(
            r'<input type="hidden" name="tab" value="([^"]+)">', panel[:siguiente] if siguiente != -1 else panel
        )

    def test_cada_panel_manda_su_propia_solapa(self):
        self._crear()

        html = self._cliente(self.coord).get(URL_LISTA).content.decode()

        for clave in ("en_curso", "completados", "cancelados"):
            self.assertEqual(self._ocultos(html, clave), [clave], clave)

    def test_el_oculto_no_sigue_a_la_solapa_que_pidio_la_url(self):
        """Antes el oculto era `solapa_actual`: desde Completados, filtrar volvía a En curso."""

        html = self._cliente(self.coord).get(URL_LISTA, {"tab": "completados"}).content.decode()

        self.assertEqual(self._ocultos(html, "en_curso"), ["en_curso"])
        self.assertEqual(self._ocultos(html, "completados"), ["completados"])

    def test_la_pildora_estado_solo_se_ofrece_donde_filtra(self):
        """«Vencido / por vencer / al día» se derivan de lo que está en curso: en las otras no."""

        respuesta = self._cliente(self.coord).get(URL_LISTA)

        nombres = {s["clave"]: [p["nombre"] for p in s["pildoras"]] for s in respuesta.context["solapas"]}
        self.assertEqual(nombres["en_curso"], ["estado", "asignado_a"])
        self.assertEqual(nombres["completados"], ["asignado_a"])
        self.assertEqual(nombres["cancelados"], ["asignado_a"])

    def test_la_cuarta_solapa_no_ofrece_pildoras(self):
        """Filtran relevamientos y ahí hay edificios: una píldora que no hace nada confunde."""

        html = self._cliente(self.coord).get(URL_LISTA).content.decode()

        self.assertEqual(self._ocultos(html, "sin_relevar"), [])


@tag("performance")
class ListadoPresupuestoTests(BaseListado):
    """La página no puede hacer una consulta por fila: edificio, agente, alcance y situación van en lote."""

    def _presupuesto(self):
        return json.loads(PRESUPUESTOS.read_text(encoding="utf-8"))["servicios"][CLAVE_PRESUPUESTO]

    def _medir(self, cliente):
        with CaptureQueriesContext(connection) as medida:
            respuesta = cliente.get(URL_LISTA)
        self.assertEqual(respuesta.status_code, 200)
        return len(medida), len(_filas(respuesta))

    def _sembrar(self, desde, hasta):
        for n in range(desde, hasta):
            edificio = self._edificio_del_parador(f"ED-{n}")
            servicio.crear_inspeccion(
                self._fresco(self.coord),
                edificio=edificio,
                asignado_a=self._fresco(self.agente),
                fecha_vencimiento=self.vence,
            )

    def test_el_listado_cuesta_lo_mismo_con_dos_que_con_veinte(self):
        techo = self._presupuesto()["consultas_fijas"]
        cliente = self._cliente(self.coord)
        cliente.get(URL_LISTA)  # calienta la sesión y el cache del programa
        # Las tres solapas con filas: una página vacía no consulta, así que se mide el peor caso.
        completado = self._crear()
        servicio.registrar_resultado(
            self._fresco(self.agente), completado, criticidad=InspeccionEdificio.Criticidad.ALTA
        )
        servicio.cancelar_inspeccion(self._fresco(self.coord), self._crear(), "Duplicado")

        self._sembrar(0, 2)
        pocas, filas_pocas = self._medir(cliente)
        self._sembrar(2, 20)
        muchas, filas_muchas = self._medir(cliente)

        self.assertEqual((filas_pocas, filas_muchas), (2, 20))
        self.assertEqual(pocas, muchas, "El listado hace consultas por fila.")
        self.assertLessEqual(
            muchas,
            techo,
            f"{muchas} consultas; el presupuesto de «{CLAVE_PRESUPUESTO}» en scripts/perf_budgets.json es "
            f"{techo}. Subirlo exige justificarlo en el mismo PR.",
        )
