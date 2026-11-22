"""Solapa Historial de la página del edificio (Cambio 571, PR 7 del lote «el edificio como unidad operativa»).

1. Contenido: lo que se deriva del edificio (estadías, plazas y sectores, kits, relevamientos, correcciones de la bitácora)
   y nada de otro edificio, de la otra institución del predio ni de lo que la traza no ata a un edificio.
2. Privacidad: sin ``ciudadano.ver`` no hay nombres de personas; sin ``emergencia.recibir_kit`` no hay entregas.
3. El contador de la solapa es el mismo número que el pie de la lista, con cualquier solapa abierta.
4. Paginación propia (``historial_page``) y el panel se arma solo con su solapa.
5. El costo no crece con los eventos (``dispositivos_edificio_operativo_historial``).
"""

import json
from unittest import mock

from django.db import connection
from django.test import tag
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from legajos.models import Ciudadano
from programas.models import (
    Dispositivo,
    EntregaKit,
    InspeccionEdificio,
    Plaza,
    Sector,
    TrazaDispositivo,
    TrazaEntrega,
    TrazaInspeccion,
)
from programas.services.bitacora import corregir_entrada, registrar_entrada
from programas.services.estadias import cambiar_plaza, reservar_plaza, sacar_plaza_de_servicio
from programas.services.plazas import agregar_plazas, crear_sector
from programas.tests.test_dispositivos_bitacora_pantalla import MARTES, MIERCOLES, TODO, _local, _reloj
from programas.tests.test_dispositivos_edificio_operativo import PRESUPUESTOS, BaseOperativo

CLAVE_PRESUPUESTO = "dispositivos_edificio_operativo_historial"
CON_KITS = (*TODO, "emergencia.recibir_kit")


class BaseHistorial(BaseOperativo):
    """El edificio A con sus dos ingresos (Ana y Juan), y alrededor todo lo que **no** le pertenece."""

    def setUp(self):
        super().setUp()
        # Otra institución en el mismo predio, con su sector y su traza.
        self.otra = Dispositivo.objects.create(
            tipo=self.tipo, codigo="GER-9", nombre="Geriátrico Reservado", estado=Dispositivo.Estado.ACTIVO
        )
        self.edif_a.dispositivos.add(self.otra)
        self.sector_otra = Sector.objects.create(
            dispositivo=self.otra, edificio=self.edif_a, nombre="Sector Secreto", capacidad=3
        )
        self.plaza_otra = Plaza.objects.create(sector=self.sector_otra, codigo="SEC-01")
        TrazaDispositivo.objects.create(
            dispositivo=self.otra,
            usuario=self.operador,
            accion="PLAZA_FUERA_SERVICIO",
            detalle="Plaza SEC-01 (Sector Secreto) · motivo: humedad",
        )
        TrazaDispositivo.objects.create(
            dispositivo=self.otra,
            usuario=self.operador,
            accion="SECTOR_CREADO",
            detalle="Sector Secreto · Otro · capacidad declarada 3 · edificio ED-A",
        )
        self.libre_a = Plaza.objects.create(sector=self.sector_a, codigo="A-LIBRE")
        self.libre_b = Plaza.objects.create(sector=self.sector_b, codigo="B-LIBRE")
        self.reservable_a = Plaza.objects.create(sector=self.sector_a, codigo="A-RESERVA")
        self.dora = Ciudadano.objects.create(dni="30999000", nombre="Dora", apellido="Vega")
        self.eva = Ciudadano.objects.create(dni="30999111", nombre="Eva", apellido="Paz")
        # Quien ve todo, kits incluidos: la capacidad de kits no está en el juego de las demás pantallas.
        self.ve_todo = self._con("Ve todo", *CON_KITS)

    def _historial(self, usuario=None, edificio=None, **params):
        respuesta = self._get(usuario or self.ve_todo, edificio or self.edif_a, tab="historial", **params)
        self.assertEqual(respuesta.status_code, 200)
        return respuesta

    def _titulos(self, respuesta):
        return [(e["titulo"], e["detalle"]) for e in respuesta.context["eventos_historial"]]

    def _textos(self, respuesta):
        return " | ".join(f"{titulo} {detalle}" for titulo, detalle in self._titulos(respuesta))

    def _traza(self, accion, detalle, dispositivo=None):
        return TrazaDispositivo.objects.create(
            dispositivo=dispositivo or self.cis, usuario=self.operador, accion=accion, detalle=detalle
        )

    def _kit(self, numero, edificio, accion=TrazaEntrega.Accion.RECIBIDA, dispositivo=None):
        entrega = EntregaKit.objects.create(
            numero=numero,
            dispositivo=dispositivo or self.cis,
            edificio=edificio,
            estado=EntregaKit.Estado.RECIBIDA,
            armada_por=self.operador,
        )
        TrazaEntrega.objects.create(entrega=entrega, usuario=self.operador, accion=accion, detalle="Recibida completa")
        return entrega

    def _relevamiento(self, edificio):
        inspeccion = InspeccionEdificio.objects.create(
            edificio=edificio,
            estado=InspeccionEdificio.Estado.REALIZADA,
            criticidad=InspeccionEdificio.Criticidad.BAJA,
            asignado_a=self.de_inst,
            creado_por=self.de_inst,
            fecha_vencimiento=timezone.now().date(),
            realizada_en=timezone.now(),
            realizada_por=self.de_inst,
        )
        TrazaInspeccion.objects.create(
            inspeccion=inspeccion,
            usuario=self.de_inst,
            accion=TrazaInspeccion.Accion.REALIZADA,
            detalle=f"Relevamiento de {edificio.codigo}",
        )
        return inspeccion

    def _correccion(self, edificio):
        with _reloj(_local(MIERCOLES, 15)):
            entrada = registrar_entrada(
                dispositivo=self.cis,
                usuario=self.operador,
                tipo="INCIDENTE",
                texto=f"Novedad en {edificio.codigo}",
                momento=_local(MIERCOLES, 15),
                edificio=edificio,
            )
            corregir_entrada(
                entrada=entrada,
                usuario=self.operador,
                texto="Texto corregido.",
                motivo=f"Error de tipeo en {edificio.codigo}",
            )


class ContenidoTests(BaseHistorial):
    def test_trae_las_estadias_de_este_edificio_con_el_turno(self):
        respuesta = self._historial()

        textos = self._textos(respuesta)
        self.assertIn("Ingreso de Gómez, Ana", textos)
        self.assertIn("Ingreso de Pérez, Juan", textos)
        # Juan ingresó un miércoles a las 15: el turno Tarde, entre la fecha y quien lo hizo.
        cuando = [e["cuando"] for e in respuesta.context["eventos_historial"] if "Juan" in e["titulo"]]
        self.assertTrue(cuando[0].split(" · ")[1] == "Turno tarde", cuando)
        self.assertTrue(cuando[0].endswith("Lucía Méndez"), cuando)

    def test_cambio_de_plaza_y_reserva_del_edificio(self):
        with _reloj():
            cambiar_plaza(estadia=self.estadia_ana, plaza=self.libre_a, usuario=self.operador, motivo="Humedad")
            reservar_plaza(plaza=self.libre_b, ciudadano=self.dora, usuario=self.operador)
            reservar_plaza(plaza=self.reservable_a, ciudadano=self.eva, usuario=self.operador)

        textos = self._textos(self._historial())

        self.assertIn("Cambio de plaza de Gómez, Ana", textos)
        self.assertIn("De plaza A-01 (Varones) a plaza A-LIBRE (Varones)", textos)
        self.assertIn("Plaza A-RESERVA (Varones)", textos)
        # La reserva de una plaza del otro edificio es del otro edificio.
        self.assertNotIn("B-LIBRE", textos)

    def test_plazas_y_sectores_del_edificio(self):
        with _reloj():
            sacar_plaza_de_servicio(plaza=self.libre_a, usuario=self.operador, motivo="Colchón roto")
            crear_sector(
                dispositivo=self.cis,
                usuario=self.operador,
                nombre="Pabellón Nuevo",
                tipo="PABELLON",
                edificio=self.edif_a,
            )
            agregar_plazas(sector=self.sector_a, usuario=self.operador, cantidad=2)

        textos = self._textos(self._historial())

        self.assertIn("Plaza fuera de servicio Plaza A-LIBRE (Varones) · motivo: Colchón roto", textos)
        self.assertIn("Alta de un sector Sector Pabellón Nuevo", textos)
        self.assertIn("Alta de plazas Sector Varones", textos)

    def test_un_sector_que_se_muda_de_edificio_aparece_en_los_dos(self):
        self._traza("SECTOR_EDITADO", "Sector Varones · Otro · capacidad declarada 4 · edificio ED-B (antes: ED-A)")

        self.assertIn("Cambio en un sector", self._textos(self._historial()))
        self.assertIn("Cambio en un sector", self._textos(self._historial(edificio=self.edif_b)))

    def test_entregas_de_kits_del_edificio(self):
        self._kit("2026-K-000701", self.edif_a)

        textos = self._textos(self._historial())

        self.assertIn("Entrega de kits recibida Entrega 2026-K-000701 · Recibida completa", textos)

    def test_relevamientos_y_correcciones_de_bitacora_del_edificio(self):
        self._relevamiento(self.edif_a)
        self._correccion(self.edif_a)

        textos = self._textos(self._historial())

        self.assertIn("Resultado del relevamiento edilicio Relevamiento de ED-A", textos)
        self.assertIn("Corrección de una novedad de la bitácora", textos)
        self.assertIn("Motivo: Error de tipeo en ED-A", textos)

    def test_el_relevamiento_no_lleva_turno(self):
        self._relevamiento(self.edif_a)

        evento = next(e for e in self._historial().context["eventos_historial"] if "relevamiento" in e["titulo"])

        self.assertNotIn("Turno", evento["cuando"])


class AlcanceDeLosDatosTests(BaseHistorial):
    def setUp(self):
        super().setUp()
        # Todo lo que sigue es de otro edificio, de la otra institución o no tiene edificio.
        with _reloj():
            sacar_plaza_de_servicio(plaza=self.libre_b, usuario=self.operador, motivo="Goteras")
            agregar_plazas(sector=self.sector_b, usuario=self.operador, cantidad=1)
            crear_sector(
                dispositivo=self.cis, usuario=self.operador, nombre="Anexo B", tipo="OTRO", edificio=self.edif_b
            )
        self._ingreso_b = self._ingresar_en_b()
        self._kit("2026-K-000801", self.edif_b)
        self._kit("2026-K-000802", None)
        self._kit("2026-K-000803", self.edif_a, dispositivo=self.otra)
        self._relevamiento(self.edif_b)
        self._correccion(self.edif_b)
        self._traza("EDITADO", '{"nombre": {"anterior": "CIS", "nuevo": "CIS 3"}}')
        self._traza("TURNO_CREADO", "Turno Madrugada")
        self.beto_nombre = "Ríos, Beto"

    def _ingresar_en_b(self):
        beto = Ciudadano.objects.create(dni="30555666", nombre="Beto", apellido="Ríos")
        return self._ingresar(beto, self.plaza_b, _local(MARTES, 12))

    def test_el_edificio_a_no_trae_nada_de_otro_edificio_ni_de_la_otra_institucion_ni_de_lo_que_no_tiene_edificio(self):
        textos = self._textos(self._historial())

        for ajeno in (
            "B-LIBRE",
            "Mujeres",
            "B-01",
            "Ríos",
            "ED-B",
            "000801",
            "000802",
            "000803",
            "Sector Secreto",
            "SEC-01",
            "Secreto",
            "Reservado",
            "Goteras",
            "Anexo B",
            "CIS 3",
            "Madrugada",
        ):
            with self.subTest(ajeno=ajeno):
                self.assertNotIn(ajeno, textos)
        self.assertNotContains(self._historial(), "Sector Secreto")

    def test_un_sector_de_la_otra_institucion_con_el_mismo_nombre_no_atrae_las_trazas_de_plaza_de_esta(self):
        # «Mujeres» es de la institución en el edificio B; la otra institución tiene uno igual en el edificio A.
        Sector.objects.create(dispositivo=self.otra, edificio=self.edif_a, nombre="Mujeres", capacidad=1)

        textos = self._textos(self._historial())

        self.assertNotIn("B-LIBRE", textos)
        self.assertNotIn("Goteras", textos)

    def test_el_edificio_b_trae_lo_suyo(self):
        textos = self._textos(self._historial(edificio=self.edif_b))

        for propio in ("B-LIBRE", "Ríos, Beto", "000801", "ED-B", "Anexo B", "Error de tipeo en ED-B"):
            with self.subTest(propio=propio):
                self.assertIn(propio, textos)
        for ajeno in ("A-LIBRE", "Gómez", "Pérez", "000802", "000803", "Error de tipeo en ED-A"):
            with self.subTest(ajeno=ajeno):
                self.assertNotIn(ajeno, textos)

    def test_quien_opera_solo_este_edificio_ve_este_y_el_otro_da_404(self):
        self.assertEqual(self._historial(usuario=self.de_a).status_code, 200)
        self.assertEqual(self._get(self.de_a, self.edif_b, tab="historial").status_code, 404)

    def test_el_contador_y_el_pie_dan_lo_mismo_que_la_lista_en_los_dos_edificios(self):
        for edificio in (self.edif_a, self.edif_b):
            with self.subTest(edificio=edificio.codigo):
                en_la_solapa = self._historial(edificio=edificio).context["contadores"]["historial"]
                con_otra = self._get(self.ve_todo, edificio, tab="estadias").context["contadores"]["historial"]

                self.assertEqual(en_la_solapa, con_otra)
                self.assertGreater(en_la_solapa, 0)


class PrivacidadTests(BaseHistorial):
    def setUp(self):
        super().setUp()
        self._kit("2026-K-000901", self.edif_a)
        self.sin_ciudadano = self._con("Sin ciudadano", "dispositivo.ver", "emergencia.recibir_kit")
        self.sin_kits = self._con("Sin kits", "dispositivo.ver", "ciudadano.ver")

    def test_sin_ciudadano_ver_no_hay_nombres_de_personas(self):
        respuesta = self._historial(usuario=self.sin_ciudadano)

        textos = self._textos(respuesta)
        self.assertIn("Ingreso de Persona alojada", textos)
        for nombre in ("Gómez", "Pérez", "Ana", "Juan"):
            with self.subTest(nombre=nombre):
                self.assertNotIn(nombre, textos)
                self.assertNotContains(respuesta, f"{nombre},")

    def test_con_ciudadano_ver_se_nombra_a_la_persona(self):
        self.assertIn("Gómez, Ana", self._textos(self._historial(usuario=self.sin_kits)))

    def test_sin_recibir_kit_no_hay_entregas_ni_se_cuentan(self):
        respuesta = self._historial(usuario=self.sin_kits)
        # El contador de otra solapa respeta la misma capacidad (una sola sesión por usuario: sin otro login en el medio).
        otra = self._get(self.sin_kits, self.edif_a, tab="estadias").context["contadores"]["historial"]
        con_kits = self._historial(usuario=self.sin_ciudadano)

        self.assertNotIn("000901", self._textos(respuesta))
        self.assertIn("000901", self._textos(con_kits))
        self.assertEqual(con_kits.context["contadores"]["historial"], respuesta.context["contadores"]["historial"] + 1)
        self.assertEqual(otra, respuesta.context["contadores"]["historial"])

    def test_un_relevamiento_sin_realizar_no_nombra_al_agente_a_quien_no_lo_ve(self):
        inspeccion = InspeccionEdificio.objects.create(
            edificio=self.edif_a,
            estado=InspeccionEdificio.Estado.ASIGNADA,
            asignado_a=self.de_inst,
            creado_por=self.de_inst,
            fecha_vencimiento=timezone.now().date(),
        )
        TrazaInspeccion.objects.create(
            inspeccion=inspeccion,
            usuario=self.de_inst,
            accion=TrazaInspeccion.Accion.ASIGNADA,
            detalle="Asignado a Lucía Méndez",
        )

        respuesta = self._historial(usuario=self.sin_ciudadano)

        self.assertNotContains(respuesta, "Asignado a Lucía Méndez")
        self.assertIn("Equipo territorial", respuesta.content.decode())


class PanelTests(BaseHistorial):
    def test_con_otra_solapa_no_se_arma_y_el_boton_navega(self):
        respuesta = self._get(self.ve_todo, self.edif_a, tab="equipo")

        self.assertFalse(respuesta.context["historial_cargado"])
        self.assertNotIn("historial", respuesta.context)
        self.assertContains(respuesta, 'id="tab-historial" aria-controls="panel-historial" data-solapa-navega')
        self.assertEqual(respuesta.context["url_solapa_historial"], f"{self._url(self.edif_a)}?tab=historial")
        self.assertNotContains(respuesta, "Ingreso de")

    def test_con_su_solapa_abierta_va_armado_y_el_boton_no_navega(self):
        respuesta = self._historial()

        self.assertTrue(respuesta.context["historial_cargado"])
        self.assertContains(respuesta, "Ingreso de Gómez, Ana")
        self.assertNotContains(respuesta, 'id="tab-historial" aria-controls="panel-historial" data-solapa-navega')

    def test_sin_eventos_dibuja_el_estado_vacio(self):
        vacio = self._historial(edificio=self.edif_b)

        # B tiene un sector con una plaza pero ninguna estadía: sin movimientos ni trazas.
        self.assertEqual(vacio.context["contadores"]["historial"], 0)
        self.assertContains(vacio, "Todavía no hay movimientos en este edificio")

    def test_pagina_de_a_20_con_su_parametro_y_conserva_la_solapa(self):
        for numero in range(25):
            self._traza("PLAZA_EN_SERVICIO", f"Plaza A-LIBRE (Varones) · vuelta {numero}")

        primera = self._historial()
        segunda = self._historial(historial_page=2)

        self.assertEqual(len(primera.context["eventos_historial"]), 20)
        self.assertEqual(primera.context["contadores"]["historial"], primera.context["historial"].paginator.count)
        self.assertEqual(segunda.context["historial"].number, 2)
        self.assertEqual(len(segunda.context["eventos_historial"]), segunda.context["historial"].paginator.count - 20)
        self.assertContains(primera, "historial_page=2")
        self.assertContains(primera, "tab=historial")

    def test_una_pagina_que_no_existe_cae_en_la_ultima(self):
        respuesta = self._historial(historial_page=999)

        self.assertEqual(respuesta.status_code, 200)

    def test_los_eventos_van_del_mas_nuevo_al_mas_viejo(self):
        self._traza("PLAZA_EN_SERVICIO", "Plaza A-LIBRE (Varones)")

        fechas = [e["cuando"] for e in self._historial().context["eventos_historial"]]

        self.assertEqual(self._titulos(self._historial())[0][0], "Plaza de nuevo en servicio")
        self.assertEqual(len(fechas), self._historial().context["historial"].paginator.count)


@tag("performance")
class PresupuestoDelHistorialTests(BaseHistorial):
    def _medir(self, **params):
        self.client.force_login(self.ve_todo)
        url = self._url(self.edif_a)
        self.client.get(url, params)
        with CaptureQueriesContext(connection) as consultas:
            respuesta = self.client.get(url, params)
        self.assertEqual(respuesta.status_code, 200)
        return len(consultas)

    def _crecer(self):
        self._kit("2026-K-001001", self.edif_a)
        self._relevamiento(self.edif_a)
        self._correccion(self.edif_a)
        for numero in range(30):
            self._traza("PLAZA_FUERA_SERVICIO", f"Plaza A-LIBRE (Varones) · motivo: {numero}")
            self._traza("SECTOR_EDITADO", f"Sector Varones · Otro · capacidad declarada 4 · edificio ED-A · {numero}")
        for numero in range(5):
            sector = Sector.objects.create(dispositivo=self.cis, edificio=self.edif_a, nombre=f"S{numero}", capacidad=2)
            Plaza.objects.create(sector=sector, codigo=f"X-{numero}")

    def test_la_solapa_cuesta_lo_mismo_con_pocos_que_con_muchos_eventos(self):
        antes = self._medir(tab="historial")
        self._crecer()
        despues = self._medir(tab="historial")

        self.assertEqual(antes, despues)
        techo = json.loads(PRESUPUESTOS.read_text(encoding="utf-8"))["servicios"][CLAVE_PRESUPUESTO]
        self.assertLessEqual(despues, techo["consultas_fijas"])

    def test_la_segunda_pagina_cuesta_lo_mismo_que_la_primera(self):
        self._crecer()

        self.assertEqual(self._medir(tab="historial"), self._medir(tab="historial", historial_page=2))

    def test_el_contador_de_las_otras_solapas_es_una_consulta_y_no_crece(self):
        antes = self._medir(tab="estadias")
        self._crecer()
        despues = self._medir(tab="estadias")

        self.assertEqual(antes, despues)

    def test_el_contador_cuesta_una_consulta_en_cualquier_solapa(self):
        con = self._medir(tab="estadias")
        with mock.patch("programas.services.edificio_operativo.contar_eventos_del_edificio", return_value=0):
            sin = self._medir(tab="estadias")

        self.assertEqual(con - sin, 1)
