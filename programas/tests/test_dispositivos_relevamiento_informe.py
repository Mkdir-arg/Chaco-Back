"""«Ver informe» de un relevamiento edilicio y quién ve de quién es (MVP v2, etapa 4).

Lo que se fija acá, y por qué:

1. **La pantalla tiene una sola regla de alcance**, `inspecciones_visibles`, y la entran
   tres personas distintas: el coordinador desde P21, el agente que lo cargó y quien opera
   una institución del edificio desde la solapa Infraestructura. Lo ajeno y lo inexistente
   dan el **mismo 404**, con el mismo cuerpo: no hay oráculo de existencia.
2. **La institución relevada no ve el nombre del agente asignado** ni las indicaciones que
   le dio la coordinación (decisión del juez). Un relevamiento en curso le dice «en curso»
   y nada más. Los ven el coordinador del edificio y el propio agente.
3. **El informe es de solo lectura**: no hay un POST, un form ni un `data-confirm-url`.
4. **Se llega desde las dos pantallas**: el menú de fila de P21 para lo completado y cada
   evento de la línea de tiempo de P4, y el botón «volver» devuelve a la de origen.

Cada usuario que se rechaza tiene **todo lo demás** salvo la condición que se prueba.
"""

import re
from datetime import timedelta

from django.test import Client
from django.urls import reverse

from programas.models import AsignacionDispositivo, Edificio, InspeccionEdificio, TrazaInspeccion
from programas.services.detalle_dispositivo import eventos_de_historial
from programas.services.inspecciones import (
    agregar_foto,
    cancelar_inspeccion,
    crear_inspeccion,
    informe_de_relevamiento,
    reasignar_inspeccion,
    registrar_resultado,
    ve_la_asignacion,
)
from programas.tests.test_dispositivos_inspecciones import TODAS_DE_DISPOSITIVOS, BaseInspecciones, _foto

Criticidad = InspeccionEdificio.Criticidad
URL_LISTA = reverse("dispositivos:relevamientos")


def _url(inspeccion, **params):
    url = reverse("dispositivos:relevamiento_informe", args=[inspeccion.pk])
    return f"{url}?{'&'.join(f'{k}={v}' for k, v in params.items())}" if params else url


class BaseInforme(BaseInspecciones):
    def setUp(self):
        super().setUp()
        self.admin = self._usuario("admin_programa", TODAS_DE_DISPOSITIVOS)
        # Un nombre propio y no el `username`: «agente» aparece suelto en el shell (el menú, los
        # textos de ayuda) y un `assertNotIn` sobre esa palabra no probaría nada.
        self.agente.first_name, self.agente.last_name = "Claudia", "Ríos"
        self.agente.save(update_fields=["first_name", "last_name"])
        self.nombre_agente = "Claudia Ríos"

    def _cliente(self, usuario):
        """Un cliente por usuario: la sesión única del backoffice cierra la segunda que se abre."""

        clientes = self.__dict__.setdefault("_clientes", {})
        if usuario.pk not in clientes:
            cliente = Client()
            cliente.force_login(self._fresco(usuario))
            clientes[usuario.pk] = cliente
        return clientes[usuario.pk]

    def _realizado(self, edificio=None, *, criticidad=Criticidad.MEDIA, observaciones="Filtración", fotos=("fachada",)):
        inspeccion = crear_inspeccion(
            self._fresco(self.admin),
            edificio=edificio or self.predio,
            asignado_a=self._fresco(self.agente),
            fecha_vencimiento=self.vence,
            indicaciones="Mirar los techos del pabellón C.",
        )
        registrar_resultado(
            self._fresco(self.agente),
            inspeccion,
            criticidad=criticidad,
            observaciones=observaciones,
            fotos=[(_foto(f"{rotulo}.jpg"), rotulo) for rotulo in fotos],
        )
        inspeccion.refresh_from_db()
        return inspeccion


class AlcanceTests(BaseInforme):
    def test_el_coordinador_del_edificio_ve_el_informe_completo(self):
        inspeccion = self._realizado()

        respuesta = self._cliente(self.coordinador).get(_url(inspeccion))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Informe del relevamiento")
        self.assertContains(respuesta, "Predio Resistencia")
        self.assertContains(respuesta, "Filtración")
        self.assertContains(respuesta, "fachada")

    def test_quien_opera_otra_institucion_del_predio_tambien_entra(self):
        """El relevamiento es del edificio: lo leen todas las instituciones que lo ocupan."""

        inspeccion = self._realizado()

        respuesta = self._cliente(self.operador_geriatrico).get(_url(inspeccion))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Filtración")

    def test_lo_ajeno_y_lo_inexistente_dan_el_mismo_404(self):
        """Sin oráculo: el de otro edificio contesta igual que un id que no existe."""

        ajeno = self._realizado(self.edificio_cis)
        inexistente = ajeno.pk + 10_000

        cliente = self._cliente(self.coordinador)
        ajena = cliente.get(_url(ajeno))
        vacia = cliente.get(reverse("dispositivos:relevamiento_informe", args=[inexistente]))

        self.assertEqual((ajena.status_code, vacia.status_code), (404, 404))

    def test_quien_no_tiene_ninguna_capacidad_de_dispositivos_tambien_recibe_404(self):
        """No hay una segunda regla de alcance en la vista: `inspecciones_visibles` le da vacío."""

        inspeccion = self._realizado()
        ajeno = self._usuario("sin_dispositivos", ())

        self.assertEqual(self._cliente(ajeno).get(_url(inspeccion)).status_code, 404)

    def test_el_agente_asignado_lo_ve_aunque_el_edificio_no_sea_de_su_alcance(self):
        inspeccion = self._realizado()

        self.assertEqual(self._cliente(self.agente).get(_url(inspeccion)).status_code, 200)

    def test_otro_agente_del_programa_no_lo_ve(self):
        inspeccion = self._realizado()

        self.assertEqual(self._cliente(self.otro_agente).get(_url(inspeccion)).status_code, 404)

    def test_es_de_solo_lectura(self):
        inspeccion = self._realizado()

        html = self._cliente(self.coordinador).get(_url(inspeccion)).content.decode()

        self.assertNotIn("<form", html.split('id="resultado-titulo"')[1])
        self.assertNotIn("data-confirm-url", html)


class AgenteOcultoTests(BaseInforme):
    """Decisión del juez: la institución relevada no sabe quién va a ir a relevarla."""

    def _en_curso(self, edificio=None):
        return crear_inspeccion(
            self._fresco(self.admin),
            edificio=edificio or self.predio,
            asignado_a=self._fresco(self.agente),
            fecha_vencimiento=self.vence,
            indicaciones="Mirar los techos del pabellón C.",
        )

    def test_la_institucion_no_ve_el_agente_ni_las_indicaciones_en_el_informe(self):
        inspeccion = self._en_curso()

        respuesta = self._cliente(self.operador_geriatrico).get(_url(inspeccion))
        html = respuesta.content.decode()

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context["agente"], "")
        self.assertEqual(respuesta.context["indicaciones"], "")
        self.assertNotIn(self.nombre_agente, html)
        self.assertNotIn("Agente asignado", html)
        self.assertNotIn("pabellón C", html)

    def test_el_coordinador_del_edificio_si_los_ve(self):
        inspeccion = self._en_curso()

        respuesta = self._cliente(self.coordinador).get(_url(inspeccion))

        self.assertEqual(respuesta.context["agente"], self.nombre_agente)
        self.assertContains(respuesta, "Agente asignado")
        self.assertContains(respuesta, "pabellón C")

    def test_el_coordinador_de_otro_edificio_no_los_ve(self):
        """La capacidad sola no alcanza: la regla es el alcance sobre **ese** edificio."""

        inspeccion = self._en_curso()
        otro = self._usuario("coord_cis", ("inspeccion.asignar", "dispositivo.ver"), [self.cis])
        self.edificio_cis.dispositivos.add(self.geriatrico)  # para que lo pueda ver por `dispositivo.ver`

        self.assertFalse(ve_la_asignacion(self._fresco(otro), inspeccion))

    def test_el_propio_agente_se_ve_a_si_mismo(self):
        inspeccion = self._en_curso()

        self.assertTrue(ve_la_asignacion(self._fresco(self.agente), inspeccion))
        self.assertFalse(ve_la_asignacion(self._fresco(self.otro_agente), inspeccion))

    def test_en_la_solapa_infraestructura_el_evento_dice_en_curso_y_nada_mas(self):
        self._en_curso()

        respuesta = self._cliente(self.operador_geriatrico).get(
            reverse("dispositivos:detalle", args=[self.geriatrico.pk])
        )
        evento = respuesta.context["infraestructura"]["eventos"][0]

        self.assertEqual(evento["cuando"], "en curso")
        # La pantalla entera, no solo el panel: la solapa Historial lee la misma asignación
        # desde `TrazaInspeccion`, cuyo detalle se escribió con el nombre adentro.
        self.assertNotIn(self.nombre_agente, respuesta.content.decode())

    def test_el_historial_tampoco_nombra_al_agente_mientras_esta_en_curso(self):
        """La traza de la asignación guarda el nombre en el texto: se rearma sin él."""

        self._en_curso()

        respuesta = self._cliente(self.operador_geriatrico).get(
            reverse("dispositivos:detalle", args=[self.geriatrico.pk])
        )
        asignada = [e for e in respuesta.context["eventos"] if "asign" in e["titulo"].lower()]

        self.assertEqual(len(asignada), 1)
        self.assertNotIn(self.nombre_agente, asignada[0]["detalle"])
        self.assertNotIn(self.nombre_agente, asignada[0]["cuando"])
        self.assertIn("Equipo territorial", asignada[0]["cuando"])
        self.assertIn("Predio Resistencia", asignada[0]["detalle"])

    def test_una_vez_realizado_el_historial_si_lo_nombra(self):
        """El resultado es auditable: lo que se oculta es quién iba a ir, no quién fue."""

        self._realizado()

        respuesta = self._cliente(self.operador_geriatrico).get(
            reverse("dispositivos:detalle", args=[self.geriatrico.pk])
        )
        asignada = [e for e in respuesta.context["eventos"] if "asign" in e["titulo"].lower()]

        self.assertIn(self.nombre_agente, asignada[0]["detalle"])

    def test_el_coordinador_si_ve_el_agente_en_la_solapa(self):
        self._en_curso()

        respuesta = self._cliente(self.coordinador).get(reverse("dispositivos:detalle", args=[self.parador.pk]))
        evento = respuesta.context["infraestructura"]["eventos"][0]

        self.assertIn(f"asignado a {self.nombre_agente}", evento["cuando"])

    def test_lo_realizado_si_dice_quien_relevo(self):
        """Lo que se oculta es la asignación, no el resultado: el informe es auditable."""

        inspeccion = self._realizado()

        respuesta = self._cliente(self.operador_geriatrico).get(_url(inspeccion))

        self.assertEqual(respuesta.context["relevo"], self.nombre_agente)
        self.assertContains(respuesta, self.nombre_agente)


class PrivacidadHistorialTests(BaseInforme):
    def _lector(self, nombre):
        return self._usuario(
            nombre, [c for c in TODAS_DE_DISPOSITIVOS if c not in ("inspeccion.asignar", "programa.configurar")]
        )

    def _dar_lectura(self, usuario):
        AsignacionDispositivo.objects.create(dispositivo=self.parador, rol=usuario.groups.get(), activo=True)

    def _asignar(self, agente):
        return crear_inspeccion(
            self._fresco(self.admin), edificio=self.predio, asignado_a=agente, fecha_vencimiento=self.vence
        )

    def test_cancelar_no_revela_la_asignacion_ni_la_reasignacion(self):
        lector = self._lector("lector_cancelado")
        self._dar_lectura(lector)
        inspeccion = self._asignar(self.otro_agente)
        reasignar_inspeccion(self._fresco(self.admin), inspeccion, self._fresco(self.agente))
        cancelar_inspeccion(self._fresco(self.admin), inspeccion, "Se reprograma")
        respuesta = self._cliente(lector).get(reverse("dispositivos:detalle", args=[self.parador.pk]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(respuesta.context["eventos"]), 3)
        for evento in respuesta.context["eventos"]:
            self.assertIn("Equipo territorial", evento["cuando"])
            self.assertNotIn(self.nombre_agente, evento["detalle"])
        self.assertNotContains(respuesta, self.nombre_agente)

    def test_cada_tipo_de_traza_oculta_nombres_si_no_se_realizo(self):
        lector = self._lector("lector_trazas")
        self._dar_lectura(lector)
        inspeccion = self._asignar(self.agente)
        # Incluso una traza histórica inconsistente de resultado/foto debe pasar la guarda.
        for accion in TrazaInspeccion.Accion.values:
            TrazaInspeccion.objects.create(
                inspeccion=inspeccion, accion=accion, usuario=self.agente, detalle=f"Asignada a {self.nombre_agente}"
            )
        for estado in (InspeccionEdificio.Estado.ASIGNADA, InspeccionEdificio.Estado.CANCELADA):
            InspeccionEdificio.objects.filter(pk=inspeccion.pk).update(
                estado=estado,
                motivo_cancelacion="Se reprograma" if estado == InspeccionEdificio.Estado.CANCELADA else "",
            )
            _, eventos = eventos_de_historial(self.parador, usuario=self._fresco(lector))
            self.assertEqual(len(eventos), len(TrazaInspeccion.Accion.values) + 1)
            for evento in eventos:
                with self.subTest(estado=estado, accion=evento["titulo"]):
                    self.assertNotIn(self.nombre_agente, evento["detalle"])
                    self.assertNotIn(self.nombre_agente, evento["cuando"])

    def test_el_propio_agente_ve_su_asignacion_pero_no_la_de_otro(self):
        agente = self._lector("agente_con_lectura")
        inspeccion = self._asignar(agente)
        # Primero se asigna como agente externo; después obtiene lectura del legajo.
        self._dar_lectura(agente)
        respuesta = self._cliente(agente).get(reverse("dispositivos:detalle", args=[self.parador.pk]))
        self.assertEqual(respuesta.status_code, 200)
        evento = respuesta.context["eventos"][0]
        self.assertIn(agente.username, evento["detalle"])
        self.assertNotIn("Equipo territorial", evento["cuando"])
        reasignar_inspeccion(self._fresco(self.admin), inspeccion, self._fresco(self.agente))
        _, eventos = eventos_de_historial(self.parador, usuario=self._fresco(agente))
        for evento in eventos:
            self.assertNotIn(self.nombre_agente, evento["detalle"])
            self.assertIn("Equipo territorial", evento["cuando"])


class EnlacesTests(BaseInforme):
    def test_p21_ofrece_ver_informe_solo_en_lo_completado(self):
        realizado = self._realizado()
        otro = Edificio.objects.create(codigo="ED-2", nombre="Anexo")
        otro.dispositivos.add(self.parador)
        en_curso = crear_inspeccion(
            self._fresco(self.coordinador),
            edificio=otro,
            asignado_a=self._fresco(self.agente),
            fecha_vencimiento=self.vence,
        )

        html = self._cliente(self.coordinador).get(URL_LISTA).content.decode()

        self.assertIn("Ver informe", html)
        self.assertIn(reverse("dispositivos:relevamiento_informe", args=[realizado.pk]), html)
        self.assertNotIn(reverse("dispositivos:relevamiento_informe", args=[en_curso.pk]), html)

    def test_la_linea_de_tiempo_de_p4_enlaza_cada_relevamiento(self):
        inspeccion = self._realizado()

        respuesta = self._cliente(self.operador_geriatrico).get(
            reverse("dispositivos:detalle", args=[self.geriatrico.pk])
        )
        esperado = (
            reverse("dispositivos:relevamiento_informe", args=[inspeccion.pk]) + f"?dispositivo={self.geriatrico.pk}"
        )

        self.assertEqual(respuesta.context["infraestructura"]["eventos"][0]["enlace"], esperado)
        self.assertContains(respuesta, esperado)

    def test_volver_devuelve_al_detalle_cuando_se_entro_desde_ahi(self):
        inspeccion = self._realizado()

        respuesta = self._cliente(self.operador_geriatrico).get(_url(inspeccion, dispositivo=self.geriatrico.pk))

        self.assertEqual(
            respuesta.context["volver_url"],
            reverse("dispositivos:detalle", args=[self.geriatrico.pk]) + "?tab=infraestructura",
        )
        self.assertEqual(respuesta.context["volver_label"], "Geriátrico")

    def test_un_dispositivo_ajeno_en_la_url_no_arma_el_volver(self):
        """El `?dispositivo=` se valida con el alcance del usuario, no se copia."""

        inspeccion = self._realizado()

        respuesta = self._cliente(self.operador_geriatrico).get(_url(inspeccion, dispositivo=self.cis.pk))

        self.assertEqual(respuesta.context["volver_url"], reverse("dispositivos:lista"))

    def test_el_coordinador_vuelve_al_listado_con_sus_filtros(self):
        inspeccion = self._realizado()
        url = reverse("dispositivos:relevamiento_informe", args=[inspeccion.pk])

        respuesta = self._cliente(self.coordinador).get(url, {"volver": "tab=completados&asignar=99"})

        # El querystring se rearma: los parámetros de modal no vuelven a abrir nada.
        self.assertEqual(respuesta.context["volver_url"], f"{URL_LISTA}?tab=completados")

    def test_un_id_que_no_es_decimal_ascii_no_rompe_el_volver(self):
        inspeccion = self._realizado()

        respuesta = self._cliente(self.operador_geriatrico).get(_url(inspeccion, dispositivo="²"))

        self.assertEqual(respuesta.status_code, 200)


class ContenidoTests(BaseInforme):
    def test_la_galeria_trae_las_fotos_del_relevamiento_y_su_total(self):
        inspeccion = self._realizado(fotos=("fachada", "cocina"))
        agregar_foto(self._fresco(self.agente), inspeccion, _foto("tarde.jpg"), "patio")

        informe = informe_de_relevamiento(self._fresco(self.coordinador), inspeccion)

        self.assertEqual([foto["rotulo"] for foto in informe["fotos"]], ["fachada", "cocina", "patio"])
        self.assertEqual(informe["total_fotos"], 3)
        self.assertTrue(all(foto["url"] for foto in informe["fotos"]))

    def test_un_relevamiento_cancelado_muestra_su_motivo_y_no_una_criticidad(self):
        inspeccion = crear_inspeccion(
            self._fresco(self.admin),
            edificio=self.predio,
            asignado_a=self._fresco(self.agente),
            fecha_vencimiento=self.vence,
        )
        InspeccionEdificio.objects.filter(pk=inspeccion.pk).update(
            estado=InspeccionEdificio.Estado.CANCELADA, motivo_cancelacion="El edificio se desocupó"
        )
        inspeccion.refresh_from_db()

        respuesta = self._cliente(self.coordinador).get(_url(inspeccion))

        self.assertContains(respuesta, "El edificio se desocupó")
        self.assertContains(respuesta, "todavía sin resultado")

    def test_las_tres_cifras_del_encabezado_salen_del_servicio(self):
        inspeccion = self._realizado(criticidad=Criticidad.ALTA, fotos=("fachada", "techo"))

        informe = informe_de_relevamiento(self._fresco(self.coordinador), inspeccion)
        etiquetas = [indicador["etiqueta"] for indicador in informe["indicadores"]]

        self.assertEqual(etiquetas, ["Estado edilicio", "Relevado el", "Fotos"])
        self.assertEqual(informe["indicadores"][0]["valor"], "Crítico")
        self.assertEqual(informe["indicadores"][0]["tono"], "danger")
        self.assertEqual(informe["indicadores"][2]["valor"], 2)

    def test_en_curso_el_encabezado_habla_del_vencimiento(self):
        inspeccion = crear_inspeccion(
            self._fresco(self.admin),
            edificio=self.predio,
            asignado_a=self._fresco(self.agente),
            fecha_vencimiento=self.vence,
        )
        # El vencimiento se corre después: `crear_inspeccion` no acepta uno pasado.
        InspeccionEdificio.objects.filter(pk=inspeccion.pk).update(fecha_vencimiento=self.vence - timedelta(days=60))
        inspeccion.refresh_from_db()

        informe = informe_de_relevamiento(self._fresco(self.coordinador), inspeccion)

        self.assertEqual(informe["indicadores"][1]["etiqueta"], "Vence el")
        self.assertEqual(informe["situacion_texto"], "Vencido")
        self.assertIsNone(informe["semaforo"])

    def test_el_titulo_de_la_pagina_nombra_el_edificio(self):
        edificio = Edificio.objects.create(codigo="ED-X", nombre="Edificio X")
        edificio.dispositivos.add(self.parador)
        inspeccion = self._realizado(edificio)

        html = self._cliente(self.coordinador).get(_url(inspeccion)).content.decode()

        self.assertRegex(html, re.compile(r"<title>.*Edificio X.*</title>", re.S))
