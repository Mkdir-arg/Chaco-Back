"""Proceso masivo a SIIS: registro de la corrida, servicio y pantalla."""

import json
import re
import shutil
import subprocess
from datetime import date, timedelta
from io import StringIO
from pathlib import Path
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from core.rbac import CATALOGO
from legajos.models import Ciudadano
from programas.models import (
    Convocatoria,
    CorridaSiis,
    EnvioSIIS,
    Formulario,
    ProgramaSiis,
    Relevamiento,
    Segmento,
    ValidacionSIS,
)
from programas.services import proceso_masivo
from programas.services.siis_envio import CatalogoNoDisponible


class CorridaSiisTests(TestCase):
    def setUp(self):
        self.programa = ProgramaSiis.objects.create(nombre="Ñachec", siis_programa_id=79)

    def _corrida(self, **kwargs):
        kwargs.setdefault("total_pedido", 1000)
        return CorridaSiis.objects.create(programa=self.programa, **kwargs)

    def test_una_corrida_recien_creada_no_esta_interrumpida(self):
        corrida = self._corrida(latido=timezone.now())
        self.assertFalse(corrida.interrumpida)

    def test_el_latido_viejo_la_marca_interrumpida(self):
        """Nadie escribe «me morí»: la interrupción se deduce del latido."""
        corrida = self._corrida(latido=timezone.now() - timedelta(minutes=5))
        self.assertTrue(corrida.interrumpida)

    def test_una_corrida_terminada_nunca_esta_interrumpida(self):
        corrida = self._corrida(estado=CorridaSiis.Estado.TERMINADA, latido=timezone.now() - timedelta(hours=3))
        self.assertFalse(corrida.interrumpida)

    def test_sin_latido_se_mide_desde_que_se_creo(self):
        corrida = self._corrida()
        self.assertFalse(corrida.interrumpida)

    def test_en_curso_devuelve_la_corrida_viva(self):
        corrida = self._corrida(latido=timezone.now())
        self.assertEqual(CorridaSiis.en_curso(), corrida)

    def test_en_curso_ignora_una_interrumpida(self):
        """Un pod muerto hace diez minutos no puede dejar el sistema trabado."""
        self._corrida(latido=timezone.now() - timedelta(minutes=30))
        self.assertIsNone(CorridaSiis.en_curso())

    def test_salteados_es_la_diferencia_entre_mirados_y_elegidos(self):
        corrida = self._corrida(mirados=1600, elegidos=1000)
        self.assertEqual(corrida.salteados, 600)

    def test_el_progreso_no_se_pasa_de_cien(self):
        corrida = self._corrida(total_pedido=10, elegidos=12)
        self.assertEqual(corrida.progreso, 100)
        self.assertEqual(self._corrida(total_pedido=10, elegidos=3).progreso, 30)


def crear_tabla_aprobados_materias(*dnis):
    """Crea la tabla cruda del Cambio 90 con los DNI dados.

    Es una tabla sin modelo --la carga el organismo desde su planilla--, asi que
    los tests la crean a mano. Va en ``setUp`` y no en ``setUpTestData``: la
    transaccion de cada test la deshace al terminar.
    """
    tabla = proceso_masivo.TABLA_APROBADOS_MATERIAS
    with connection.cursor() as cur:
        cur.execute(f"CREATE TABLE {tabla} (dni VARCHAR(20))")
        for dni in dnis:
            cur.execute(f"INSERT INTO {tabla} (dni) VALUES (%s)", [dni])


def borrar_tabla_aprobados_materias():
    with connection.cursor() as cur:
        cur.execute(f"DROP TABLE {proceso_masivo.TABLA_APROBADOS_MATERIAS}")


class _BaseProcesoTest(TestCase):
    def setUp(self):
        call_command("seed_becas", stdout=StringIO())
        # Cambio 90: sin esta tabla, candidatos() se niega a devolver nada.
        crear_tabla_aprobados_materias("20301234")
        self.programa = ProgramaSiis.objects.create(nombre="Ñachec", siis_programa_id=79, siis_funcion_id=4)
        self.segmento = Segmento.objects.create(nombre="Seg", cupo_maximo=100, programa=self.programa)
        self.convocatoria = Convocatoria.objects.create(
            nombre="Conv",
            segmento=self.segmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        self.user = User.objects.create_user("coord_masivo", password="x")
        self.relevamiento = Relevamiento.objects.create(
            convocatoria=self.convocatoria,
            territorial=self.user,
            fecha_asignada=date(2026, 6, 1),
            zona="A",
        )
        self.ciudadano = Ciudadano.objects.create(
            dni="20301234", nombre="Juan", apellido="Perez", fecha_nacimiento=date(1995, 6, 15), genero="M"
        )

    def _caso(self, estado=Formulario.Estado.ENVIADO, validado_renaper=True):
        """Un caso que el masivo puede tomar.

        Nace con la identidad validada porque es lo que hace falta para
        aprobarlo: desde BEC-21 un ENVIADO sin validar ya no es candidato, así que
        un caso sin eso no probaría el circuito sino la exclusión.
        """
        return Formulario.objects.create(
            relevamiento=self.relevamiento,
            ciudadano=self.ciudadano,
            estado=estado,
            validado_renaper=validado_renaper,
        )


class CandidatosTests(_BaseProcesoTest):
    def test_toma_los_enviados_y_los_aprobados(self):
        enviado = self._caso()
        aprobado = self._caso(Formulario.Estado.APROBADO)
        self._caso(Formulario.Estado.RECHAZADO)
        encontrados = set(proceso_masivo.candidatos(programa=self.programa).values_list("pk", flat=True))
        self.assertEqual(encontrados, {enviado.pk, aprobado.pk})

    def test_saltea_el_que_ya_tiene_alta(self):
        caso = self._caso(Formulario.Estado.APROBADO)
        EnvioSIIS.objects.create(formulario=caso, estado=EnvioSIIS.Estado.ENVIADO, documento="1")
        self.assertFalse(proceso_masivo.candidatos(programa=self.programa).exists())

    def test_incluye_al_que_nunca_se_mando(self):
        """Sin envio el ultimo estado es NULL, y un exclude lo descartaria."""
        caso = self._caso(Formulario.Estado.APROBADO)
        self.assertIn(caso.pk, proceso_masivo.candidatos(programa=self.programa).values_list("pk", flat=True))

    def test_saltea_el_duplicado_sin_resolver(self):
        caso = self._caso()
        caso.conflicto_duplicado = True
        caso.conflicto_resuelto = False
        caso.save(update_fields=["conflicto_duplicado", "conflicto_resuelto"])
        self.assertFalse(proceso_masivo.candidatos(programa=self.programa).exists())

    def test_no_usa_distinct_y_cada_caso_sale_una_sola_vez(self):
        """Nada multiplica filas (el conflicto de carga se excluye por subconsulta),
        y el DISTINCT hacía que MySQL materializara todos los candidatos con su
        JSON antes de ordenar y cortar."""
        caso = self._caso()
        for _ in range(2):
            Formulario.objects.create(
                relevamiento=self.relevamiento,
                ciudadano=self.ciudadano,
                duplicado_de=caso,
                conflicto_duplicado=True,
                conflicto_resuelto=True,
            )
        consulta = proceso_masivo.candidatos(programa=self.programa)
        self.assertNotIn("DISTINCT", str(consulta.query))
        pks = list(consulta.values_list("pk", flat=True))
        self.assertEqual(len(pks), len(set(pks)))
        self.assertIn(caso.pk, pks)

    def test_excluye_enviados_sin_identidad_validada(self):
        """BEC-21: aprobar exige identidad validada, así que consultarlos es tirar llamadas.

        Un ENVIADO sin validar no se puede aprobar (``motivo_bloqueo_aprobacion``),
        pero igual se le consultaba la compatibilidad a SIIS —hasta 40 s— para
        después contarlo como «no se pudo aprobar».
        """
        sin_validar = self._caso()
        Formulario.objects.filter(pk=sin_validar.pk).update(validado_renaper=False)
        validado = self._caso()

        pks = list(proceso_masivo.candidatos(programa=self.programa).values_list("pk", flat=True))

        self.assertEqual(pks, [validado.pk])

    def test_un_aprobado_sin_validar_sigue_siendo_candidato(self):
        """Ya está aprobado: lo que falta es informarlo, y eso no vuelve a mirar la identidad."""
        aprobado = self._caso(Formulario.Estado.APROBADO)
        Formulario.objects.filter(pk=aprobado.pk).update(validado_renaper=False)

        pks = list(proceso_masivo.candidatos(programa=self.programa).values_list("pk", flat=True))

        self.assertEqual(pks, [aprobado.pk])

    def test_excluye_al_enviado_sin_ciudadano_con_dni(self):
        caso = self._caso()
        Formulario.objects.filter(pk=caso.pk).update(ciudadano=None)

        pks = list(proceso_masivo.candidatos(programa=self.programa, filtrar_materias=False).values_list("pk"))

        self.assertEqual(pks, [])

    def test_no_toma_casos_de_una_pausa_vigente(self):
        """BEC-21: pausar frena la carga en campo; aprobar en lote la ignoraba."""
        caso = self._caso()
        niveles = (
            (self.relevamiento, "relevamiento"),
            (self.convocatoria, "convocatoria"),
            (self.segmento, "segmento"),
            (self.programa, "programa"),
        )
        for objeto, nombre in niveles:
            with self.subTest(nivel=nombre):
                type(objeto).objects.filter(pk=objeto.pk).update(pausado=True)
                pks = list(proceso_masivo.candidatos(programa=self.programa).values_list("pk", flat=True))
                self.assertEqual(pks, [], f"una pausa en {nombre} no frenó el masivo")
                type(objeto).objects.filter(pk=objeto.pk).update(pausado=False)
        self.assertEqual(
            list(proceso_masivo.candidatos(programa=self.programa).values_list("pk", flat=True)), [caso.pk]
        )

    def test_hidratar_por_lotes_recorre_todos_en_orden_de_pk(self):
        casos = [self._caso() for _ in range(5)]
        consulta = proceso_masivo.candidatos(programa=self.programa)
        ids = proceso_masivo.ids_de(consulta)
        self.assertEqual(ids, sorted(c.pk for c in casos))
        self.assertEqual(proceso_masivo.ids_de(consulta, limite=2), ids[:2])
        with self.assertNumQueries(3):  # cinco ids de a dos: tres lotes, una consulta cada uno
            hidratados = list(proceso_masivo.hidratar_por_lotes(ids, tamano=2))
        self.assertEqual([c.pk for c in hidratados], ids)
        # Las relaciones que lee el circuito vienen cargadas: armar el payload no vuelve a la base.
        with self.assertNumQueries(0):
            for hidratado in hidratados:
                self.assertIsNotNone(hidratado.ciudadano)
                self.assertEqual(hidratado.relevamiento.convocatoria.segmento.programa, self.programa)


class IdsPorRangoTests(_BaseProcesoTest):
    """``ids_de`` pide los ids por rangos de pk, no todos de una.

    La tabla de casos pesa 283 MB en producción —27 KB de foto por caso— y en
    InnoDB el índice primario es la tabla: traer todos los ids de una la recorre
    entera y muere por el ``read_timeout`` de 10 s de ECOM. El síntoma engañaba,
    porque entraba o no según la I/O del servidor: el mismo comando andaba tras
    unos minutos de pausa y fallaba lanzado enseguida después de otro.
    """

    def test_devuelve_todos_los_ids_en_orden(self):
        casos = [self._caso() for _ in range(5)]

        ids = proceso_masivo.ids_de(proceso_masivo.candidatos(), pagina=2)

        self.assertEqual(ids, sorted(c.pk for c in casos))

    def test_pagina_de_a_poco_en_vez_de_una_consulta_grande(self):
        for _ in range(5):
            self._caso()

        candidatos = proceso_masivo.candidatos()  # fuera: lee aprobados_materias
        with CaptureQueriesContext(connection) as consultas:
            proceso_masivo.ids_de(candidatos, pagina=2)

        paginas = [c["sql"] for c in consultas if "LIMIT 2" in c["sql"]]
        # 5 casos de a 2: tres páginas con datos y una vacía que corta el bucle.
        self.assertEqual(len(paginas), 4, paginas)
        # Y cada una arranca donde terminó la anterior.
        self.assertTrue(all('"id" >' in sql for sql in paginas), paginas)

    def test_respeta_el_limite_sin_pedir_de_mas(self):
        for _ in range(6):
            self._caso()

        ids = proceso_masivo.ids_de(proceso_masivo.candidatos(), limite=3, pagina=2)

        self.assertEqual(len(ids), 3)

    def test_sin_candidatos_no_entra_en_un_bucle_infinito(self):
        self.assertEqual(proceso_masivo.ids_de(proceso_masivo.candidatos(), pagina=2), [])


class ElegirCompletosTests(_BaseProcesoTest):
    def test_junta_el_total_salteando_los_incompletos(self):
        """El total cuenta casos que se mandan, no casos que se miran."""
        casos = [self._caso() for _ in range(3)]
        cuenta = proceso_masivo.Cuenta()
        with patch("programas.services.proceso_masivo.armar_payload") as armar:
            armar.side_effect = [({}, {"nro_actual": "falta"}), ({}, {}), ({}, {})]
            elegidos, descartados = proceso_masivo.elegir_completos(casos, None, 2, cuenta)
        self.assertEqual([c.pk for c in elegidos], [casos[1].pk, casos[2].pk])
        self.assertEqual(descartados, {"nro_actual": 1})
        self.assertEqual(cuenta.mirados, 3)
        self.assertEqual(cuenta.elegidos, 2)

    def test_si_no_alcanzan_devuelve_los_que_hay(self):
        casos = [self._caso()]
        cuenta = proceso_masivo.Cuenta()
        with patch("programas.services.proceso_masivo.armar_payload") as armar:
            armar.return_value = ({}, {})
            elegidos, _ = proceso_masivo.elegir_completos(casos, None, 50, cuenta)
        self.assertEqual(len(elegidos), 1)


class _BaseCorrerTest(_BaseProcesoTest):
    """Mocks del circuito completo: lo que se prueba acá es el bucle, no los pasos."""

    def setUp(self):
        super().setUp()
        self.parches = {
            nombre: patch(f"programas.services.proceso_masivo.{nombre}").start()
            for nombre in (
                "armar_payload",
                "validar_formulario_en_siis",
                "aprobar_o_poner_en_espera",
                "enviar_beneficiario_a_siis",
                "enviar_aviso_resolucion",
            )
        }
        self.addCleanup(patch.stopall)
        self.parches["armar_payload"].return_value = ({}, {})
        self.parches["validar_formulario_en_siis"].side_effect = lambda f, u: ValidacionSIS.objects.create(
            formulario=f, estado=ValidacionSIS.Estado.OK, documento="1", id_programa=79
        )
        self.parches["aprobar_o_poner_en_espera"].side_effect = lambda f, u: "aprobado"
        self.parches["enviar_beneficiario_a_siis"].side_effect = lambda f, u, **kw: EnvioSIIS.objects.create(
            formulario=f, estado=EnvioSIIS.Estado.ENVIADO, documento="1", siis_id=1
        )

    def _corrida(self, total=10):
        return CorridaSiis.objects.create(programa=self.programa, total_pedido=total)


class CorrerTests(_BaseCorrerTest):
    def test_termina_y_cuenta_las_altas(self):
        for _ in range(3):
            self._caso()
        corrida = proceso_masivo.correr(self._corrida(), lote=2)
        self.assertEqual(corrida.estado, CorridaSiis.Estado.TERMINADA)
        self.assertEqual(corrida.altas, 3)
        self.assertEqual(corrida.aprobados, 3)
        self.assertIsNotNone(corrida.finalizada)

    def test_escribe_el_latido_en_cada_lote(self):
        for _ in range(3):
            self._caso()
        corrida = proceso_masivo.correr(self._corrida(), lote=2)
        self.assertIsNotNone(corrida.latido)
        self.assertFalse(corrida.interrumpida)

    def test_frenar_corta_en_el_caso_y_no_al_cerrar_el_lote(self):
        """SIIS-03: esperar al lote eran hasta 40 llamadas de más después del freno.

        Con un caso tardando hasta 40 s, cerrar el lote de 40 son 26 minutos entre
        que alguien aprieta Frenar y que el proceso deje de mandar altas a SIIS,
        que no tienen baja.
        """
        for _ in range(4):
            self._caso()
        corrida = self._corrida()

        def marcar(f, u, **kw):
            # Alguien aprieta Frenar mientras corre el primer caso.
            CorridaSiis.objects.filter(pk=corrida.pk).update(cancelacion_pedida=True)
            return EnvioSIIS.objects.create(formulario=f, estado=EnvioSIIS.Estado.ENVIADO, documento="1")

        self.parches["enviar_beneficiario_a_siis"].side_effect = marcar
        resultado = proceso_masivo.correr(corrida, lote=40)
        self.assertEqual(resultado.estado, CorridaSiis.Estado.CANCELADA)
        self.assertEqual(resultado.altas, 1)
        self.assertEqual(EnvioSIIS.objects.count(), 1)

    def test_se_detiene_tras_errores_tecnicos_seguidos(self):
        for _ in range(4):
            self._caso()
        self.parches["enviar_beneficiario_a_siis"].side_effect = lambda f, u, **kw: EnvioSIIS.objects.create(
            formulario=f, estado=EnvioSIIS.Estado.ERROR, documento="1", codigo_error="ERROR_TECNICO"
        )
        corrida = proceso_masivo.correr(self._corrida(), lote=10, max_errores=2)
        self.assertEqual(corrida.estado, CorridaSiis.Estado.DETENIDA)
        self.assertIn("SIIS", corrida.mensaje)

    def test_el_catalogo_caido_la_detiene_con_el_motivo(self):
        self._caso()
        self.parches["armar_payload"].side_effect = CatalogoNoDisponible("el servicio no responde")
        corrida = proceso_masivo.correr(self._corrida())
        self.assertEqual(corrida.estado, CorridaSiis.Estado.DETENIDA)
        self.assertIn("no responde", corrida.mensaje)

    def test_una_excepcion_no_prevista_queda_escrita(self):
        """Corre en un hilo: si escapara, nadie la veria."""
        self._caso()
        self.parches["validar_formulario_en_siis"].side_effect = RuntimeError("algo raro")
        corrida = proceso_masivo.correr(self._corrida())
        self.assertEqual(corrida.estado, CorridaSiis.Estado.DETENIDA)
        self.assertIn("algo raro", corrida.mensaje)

    def test_sin_candidatos_termina_igual(self):
        corrida = proceso_masivo.correr(self._corrida())
        self.assertEqual(corrida.estado, CorridaSiis.Estado.TERMINADA)
        self.assertEqual(corrida.altas, 0)

    def test_no_manda_correos_al_ciudadano(self):
        """Mil correos irretractables no van detras de un boton oculto."""
        self._caso()
        proceso_masivo.correr(self._corrida())
        self.parches["enviar_aviso_resolucion"].assert_not_called()


class LatidoTests(_BaseCorrerTest):
    """SIIS-03: la corrida da señales de vida mientras trabaja, no cada 40 casos.

    El latido es lo único que distingue «sigue trabajando» de «el pod se murió»:
    ``CorridaSiis.en_curso()`` y la pantalla se deciden con él. Mientras no se
    escribía —toda la selección y cada lote de 40 casos— una corrida viva se veía
    interrumpida, y entonces ``crear_corrida`` dejaba lanzar otra **con el hilo
    viejo todavía mandando altas a SIIS**.
    """

    def test_hay_latido_antes_de_empezar_a_elegir(self):
        """El de la PoC invertido: la selección entera corría sin un solo latido.

        Con 7.496 candidatos, armar el payload de cada uno para ver si sale
        completo tarda entre 40 y 65 s y se acerca a los 2 minutos del latido
        vencido viejo: la corrida se daba por muerta antes de mandar nada.
        """
        corrida = self._corrida()
        visto = {}

        def elegir(casos, catalogos, total, cuenta, **kw):
            visto["latido"] = CorridaSiis.objects.get(pk=corrida.pk).latido
            return [], {}

        with patch("programas.services.proceso_masivo.elegir_completos", side_effect=elegir):
            proceso_masivo.correr(corrida)

        self.assertIsNotNone(visto["latido"], "la selección empieza sin que la corrida haya dado señales")

    def test_la_seleccion_late_cada_cien_candidatos_mirados(self):
        casos = [self._caso() for _ in range(3)] * 84  # 252 miradas, sin tocar la base de más
        self.parches["armar_payload"].return_value = ({}, {"loc_actual": "falta"})
        latidos = []

        elegidos, _ = proceso_masivo.elegir_completos(
            casos, None, 10, proceso_masivo.Cuenta(), al_mirar=lambda: latidos.append(1)
        )

        self.assertEqual(elegidos, [])
        self.assertEqual(len(latidos), 252 // proceso_masivo.LATIDO_CADA_MIRADOS)

    def test_una_corrida_lenta_nunca_se_ve_interrumpida(self):
        """Veinte casos a 10 s cada uno: con el latido por lote se veía muerta.

        El reloj avanza dentro del envío, que es donde se van los segundos de
        verdad (token, validación y alta, hasta 40 s cada llamada).
        """
        for _ in range(20):
            self._caso()
        corrida = self._corrida(total=20)
        reloj = {"ahora": timezone.now()}
        interrumpida_en_el_caso = []

        def enviar(formulario, usuario, **kw):
            reloj["ahora"] += timedelta(seconds=10)
            interrumpida_en_el_caso.append(CorridaSiis.objects.get(pk=corrida.pk).interrumpida)
            return EnvioSIIS.objects.create(formulario=formulario, estado=EnvioSIIS.Estado.ENVIADO, documento="1")

        self.parches["enviar_beneficiario_a_siis"].side_effect = enviar
        with patch("django.utils.timezone.now", side_effect=lambda: reloj["ahora"]):
            proceso_masivo.correr(corrida, lote=40)

        self.assertEqual(len(interrumpida_en_el_caso), 20)
        self.assertNotIn(True, interrumpida_en_el_caso, "una corrida que está trabajando apareció como muerta")

    def test_el_latido_vencido_cubre_tres_llamadas_a_siis_con_margen(self):
        """Dos minutos no alcanzaban: un caso son hasta tres llamadas de 40 s.

        El umbral tiene que estar **por encima** del peor caso de un solo caso, o
        un caso lento alcanza para que la corrida se declare muerta a sí misma.
        """
        from django.conf import settings

        techo = (settings.SIIS_API_CONNECT_TIMEOUT + settings.SIIS_API_TIMEOUT) * 3
        self.assertGreater(CorridaSiis.LATIDO_VENCIDO.total_seconds(), techo)


class CorridaReemplazadaTests(_BaseCorrerTest):
    """SIIS-03: dos corridas EN_CURSO a la vez, y el hilo viejo mandando altas."""

    def test_crear_corrida_retira_la_que_quedo_sin_senal(self):
        """El de la PoC invertido: antes quedaban dos EN_CURSO conviviendo."""
        vieja = self._corrida(total=5)
        CorridaSiis.objects.filter(pk=vieja.pk).update(
            creado=timezone.now() - CorridaSiis.LATIDO_VENCIDO * 2,
            latido=timezone.now() - CorridaSiis.LATIDO_VENCIDO * 2,
        )

        nueva = proceso_masivo.crear_corrida(programa=self.programa, solicitada_por=self.user, total_pedido=5)

        self.assertIsNotNone(nueva)
        self.assertEqual(CorridaSiis.objects.filter(estado=CorridaSiis.Estado.EN_CURSO).count(), 1)
        vieja.refresh_from_db()
        self.assertEqual(vieja.estado, CorridaSiis.Estado.DETENIDA)
        self.assertIsNotNone(vieja.finalizada)
        self.assertIn("sin señal", vieja.mensaje)
        self.assertIn(f"#{nueva.pk}", vieja.mensaje)

    def test_el_hilo_reemplazado_se_retira_sin_pisar_el_estado(self):
        """Si el pod viejo seguía vivo, al menos no vuelve a escribir la corrida."""
        for _ in range(4):
            self._caso()
        corrida = self._corrida()

        def reemplazar(formulario, usuario, **kw):
            CorridaSiis.objects.filter(pk=corrida.pk).update(
                estado=CorridaSiis.Estado.DETENIDA, mensaje="Interrumpida: reemplazada por la corrida #99"
            )
            return EnvioSIIS.objects.create(formulario=formulario, estado=EnvioSIIS.Estado.ENVIADO, documento="1")

        self.parches["enviar_beneficiario_a_siis"].side_effect = reemplazar
        proceso_masivo.correr(corrida, lote=40)

        corrida.refresh_from_db()
        self.assertEqual(corrida.estado, CorridaSiis.Estado.DETENIDA)
        self.assertEqual(corrida.mensaje, "Interrumpida: reemplazada por la corrida #99")
        # Se retiró en el primer caso: no siguió mandando altas a SIIS.
        self.assertEqual(EnvioSIIS.objects.count(), 1)


class IncompatiblesTests(_BaseCorrerTest):
    """BEC-11 (D-B11): en la corrida no hay revisor que decida sobre un rechazo.

    El Cambio 81 sacó el bloqueo porque «la aprobación es una decisión técnica del
    revisor»; en el proceso masivo esa persona no existe, así que un incompatible
    quedaría aprobado e informado a SIIS sin que nadie lo haya mirado.
    """

    def _rechazado_por_siis(self):
        self.parches["validar_formulario_en_siis"].side_effect = lambda f, u: ValidacionSIS.objects.create(
            formulario=f,
            estado=ValidacionSIS.Estado.RECHAZADO,
            documento="1",
            id_programa=79,
            motivo="Ya percibe otro beneficio",
        )

    def test_un_rechazado_por_siis_no_se_aprueba_en_lote(self):
        caso = self._caso()
        self._rechazado_por_siis()
        cuenta = proceso_masivo.Cuenta()

        desenlace = proceso_masivo.procesar_caso(caso, self.user, None, cuenta)

        self.assertIsNone(desenlace, "un incompatible no es una falla de SIIS: no cuenta para el freno")
        self.assertEqual(cuenta.incompatibles, 1)
        self.parches["aprobar_o_poner_en_espera"].assert_not_called()
        self.parches["enviar_beneficiario_a_siis"].assert_not_called()
        caso.refresh_from_db()
        self.assertEqual(caso.estado, Formulario.Estado.ENVIADO)

    def test_la_corrida_los_cuenta_y_sigue_con_los_demas(self):
        self._caso()
        self._rechazado_por_siis()

        corrida = proceso_masivo.correr(self._corrida())

        self.assertEqual(corrida.estado, CorridaSiis.Estado.TERMINADA)
        self.assertEqual(corrida.incompatibles, 1)
        self.assertEqual(corrida.altas, 0)

    def test_un_error_tecnico_de_la_validacion_sigue_siendo_otra_cosa(self):
        """Incompatible es un veredicto; un error técnico no dice nada de la persona."""
        caso = self._caso()
        self.parches["validar_formulario_en_siis"].side_effect = lambda f, u: ValidacionSIS.objects.create(
            formulario=f, estado=ValidacionSIS.Estado.ERROR, documento="1", id_programa=79
        )
        cuenta = proceso_masivo.Cuenta()

        desenlace = proceso_masivo.procesar_caso(caso, self.user, None, cuenta)

        self.assertEqual(desenlace, proceso_masivo.FALLA_TECNICA)
        self.assertEqual(cuenta.incompatibles, 0)
        self.assertEqual(cuenta.error_validacion, 1)


class LanzarTests(_BaseProcesoTest):
    def test_el_ejecutor_se_inyecta(self):
        """En los tests corre sincronico; sin eso serian una carrera."""
        corrida = CorridaSiis.objects.create(programa=self.programa, total_pedido=1)
        llamadas = []
        proceso_masivo.lanzar(corrida, ejecutor=llamadas.append)
        self.assertEqual(len(llamadas), 1)


class PantallaProcesoMasivoTests(_BaseProcesoTest):
    CAP = "becas.programa.proceso_masivo"

    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_superuser("admin_masivo", password="x")
        self.client.force_login(self.admin)

    def _url(self, nombre="proceso_masivo"):
        return reverse(f"becas:{nombre}", args=[self.programa.pk])

    def test_la_capacidad_esta_en_el_catalogo(self):
        codigos = [c for modulo in CATALOGO for c, _ in modulo["capacidades"]]
        self.assertIn(self.CAP, codigos)

    def test_la_pantalla_abre_y_muestra_los_pendientes(self):
        self._caso()
        resp = self.client.get(self._url())
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Proceso masivo")
        self.assertEqual(resp.context["pendientes"], 1)

    def test_sin_la_capacidad_no_entra(self):
        """Un usuario sin la capacidad no llega, aunque sepa la URL."""
        otro = User.objects.create_user("sin_capacidad", password="x")
        self.client.force_login(otro)
        resp = self.client.get(self._url())
        self.assertIn(resp.status_code, (302, 403))

    def test_no_se_enlaza_desde_ninguna_otra_pantalla(self):
        """«Secreta» es no listada: ninguna plantilla ajena apunta acá."""
        raiz = Path(__file__).resolve().parents[1] / "templates"
        propia = "proceso_masivo.html"
        con_referencia = sorted(
            ruta.name for ruta in raiz.rglob("*.html") if "proceso_masivo" in ruta.read_text(encoding="utf-8")
        )
        self.assertEqual(con_referencia, [propia])

    def test_lanzar_crea_la_corrida_y_no_espera(self):
        self._caso()
        with patch("programas.views.proceso_masivo.servicio.lanzar") as lanzar:
            resp = self.client.post(self._url("proceso_masivo_lanzar"), {"total_pedido": "25"})
        self.assertEqual(resp.status_code, 302)
        corrida = CorridaSiis.objects.get()
        self.assertEqual(corrida.total_pedido, 25)
        self.assertEqual(corrida.solicitada_por, self.admin)
        lanzar.assert_called_once()

    def test_no_deja_lanzar_dos_a_la_vez(self):
        CorridaSiis.objects.create(programa=self.programa, total_pedido=10, latido=timezone.now())
        with patch("programas.views.proceso_masivo.servicio.lanzar") as lanzar:
            self.client.post(self._url("proceso_masivo_lanzar"), {"total_pedido": "10"})
        self.assertEqual(CorridaSiis.objects.count(), 1)
        lanzar.assert_not_called()

    def test_una_interrumpida_no_bloquea(self):
        CorridaSiis.objects.create(
            programa=self.programa, total_pedido=10, latido=timezone.now() - timedelta(minutes=30)
        )
        with patch("programas.views.proceso_masivo.servicio.lanzar"):
            self.client.post(self._url("proceso_masivo_lanzar"), {"total_pedido": "10"})
        self.assertEqual(CorridaSiis.objects.count(), 2)

    def test_un_total_invalido_no_crea_nada(self):
        with patch("programas.views.proceso_masivo.servicio.lanzar"):
            self.client.post(self._url("proceso_masivo_lanzar"), {"total_pedido": "0"})
            self.client.post(self._url("proceso_masivo_lanzar"), {"total_pedido": "99999"})
            self.client.post(self._url("proceso_masivo_lanzar"), {"total_pedido": "abc"})
        self.assertFalse(CorridaSiis.objects.exists())

    def test_frenar_marca_la_corrida(self):
        corrida = CorridaSiis.objects.create(programa=self.programa, total_pedido=10, latido=timezone.now())
        resp = self.client.post(self._url("proceso_masivo_frenar"))
        self.assertEqual(resp.status_code, 302)
        corrida.refresh_from_db()
        self.assertTrue(corrida.cancelacion_pedida)
        # El estado lo cambia el proceso al cerrar el lote, no este request.
        self.assertEqual(corrida.estado, CorridaSiis.Estado.EN_CURSO)

    def test_frenar_sin_corrida_no_rompe(self):
        resp = self.client.post(self._url("proceso_masivo_frenar"))
        self.assertEqual(resp.status_code, 302)

    def test_frenar_alcanza_a_una_corrida_sin_latido(self):
        """V2-NEW-01: la que parece interrumpida es justo la que hay que poder frenar.

        «Sin señal» no es «muerta»: una corrida lenta —o un pod que tarda en
        escribir— se veía interrumpida, y entonces el botón Frenar decía «no hay
        ninguna corrida en curso» mientras el hilo seguía mandando altas a SIIS.
        """
        corrida = CorridaSiis.objects.create(
            programa=self.programa, total_pedido=10, latido=timezone.now() - timedelta(hours=1)
        )

        self.client.post(self._url("proceso_masivo_frenar"))

        corrida.refresh_from_db()
        self.assertTrue(corrida.cancelacion_pedida)

    def test_frenar_solo_afecta_a_la_corrida_de_este_programa(self):
        """A5-33: el botón está en la pantalla de un programa y frenaba la de cualquiera."""
        otro = ProgramaSiis.objects.create(nombre="Otro programa", siis_programa_id=80)
        ajena = CorridaSiis.objects.create(programa=otro, total_pedido=10, latido=timezone.now())

        resp = self.client.post(self._url("proceso_masivo_frenar"))

        ajena.refresh_from_db()
        self.assertFalse(ajena.cancelacion_pedida, "se frenó la corrida de otro programa")
        self.assertEqual(resp.status_code, 302)


class ConfirmacionProcesoMasivoTests(_BaseProcesoTest):
    """POP-6: lanzar y frenar piden confirmación antes de mandar el POST.

    Lanzar aprueba y da de alta en SIIS hasta miles de casos con un clic; frenar
    corta una corrida que no se retoma sola. Los dos pasan por un ModernModal rojo.
    """

    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_superuser("admin_confirma", password="x")
        self.client.force_login(self.admin)
        self.url = reverse("becas:proceso_masivo", args=[self.programa.pk])

    def test_el_form_de_lanzar_pide_confirmacion_con_los_pendientes(self):
        self._caso()
        html = self.client.get(self.url).content.decode()
        self.assertIn("data-confirmar-masivo data-pendientes", html)
        self.assertIn('data-pendientes="1"', html)
        self.assertIn("ModernModal.show", html)
        self.assertIn("danger: true", html)
        self.assertIn("Sí, procesar hasta", html)

    def test_los_pendientes_viajan_sin_separador_de_miles(self):
        """El JS hace la cuenta con el número crudo; el formato va en el modal."""
        with patch("programas.views.proceso_masivo.servicio.candidatos") as candidatos:
            candidatos.return_value.count.return_value = 3482
            html = self.client.get(self.url).content.decode()
        self.assertIn('data-pendientes="3482"', html)

    def test_frenar_pide_confirmacion(self):
        CorridaSiis.objects.create(
            programa=self.programa, solicitada_por=self.admin, total_pedido=10, latido=timezone.now()
        )
        html = self.client.get(self.url).content.decode()
        self.assertIn("data-confirmar-frenar", html)
        self.assertIn("¿Frenar la corrida?", html)
        self.assertIn("Sí, frenar", html)
        self.assertNotIn("data-confirmar-masivo data-pendientes", html)

    def test_la_relectura_automatica_no_pisa_el_modal_abierto(self):
        """Con la corrida en curso la pantalla se relee cada 5 s: si el modal de
        frenar está abierto, la relectura espera en vez de cerrarlo."""
        CorridaSiis.objects.create(
            programa=self.programa, solicitada_por=self.admin, total_pedido=10, latido=timezone.now()
        )
        html = self.client.get(self.url).content.decode()
        self.assertIn("modal-overlay", html)
        self.assertIn("function releer()", html)

    def test_sin_pendientes_no_ofrece_lanzar(self):
        html = self.client.get(self.url).content.decode()
        self.assertNotIn("data-confirmar-masivo data-pendientes", html)
        self.assertIn("No quedan casos pendientes de informar", html)

    def test_interrumpida_sin_pendientes_no_ofrece_continuar(self):
        """Una interrumpida sin nada pendiente no invita a «Continuar» algo que no lanzaría nada."""
        CorridaSiis.objects.create(
            programa=self.programa,
            solicitada_por=self.admin,
            total_pedido=10,
            latido=timezone.now() - timedelta(minutes=30),
        )
        html = self.client.get(self.url).content.decode()
        self.assertIn("la corrida no necesita continuarse", " ".join(html.split()))
        self.assertNotIn("Continuar lanza una corrida nueva", html)
        self.assertNotIn("data-confirmar-masivo data-pendientes", html)

    def test_interrumpida_con_pendientes_ofrece_continuar(self):
        self._caso()
        CorridaSiis.objects.create(
            programa=self.programa,
            solicitada_por=self.admin,
            total_pedido=10,
            latido=timezone.now() - timedelta(minutes=30),
        )
        html = self.client.get(self.url).content.decode()
        self.assertIn("Continuar lanza una corrida nueva", html)
        self.assertIn("data-confirmar-masivo data-pendientes", html)


# DOM mínimo para correr el script de la pantalla en node, sin dependencias. Los
# relojes son falsos: el test decide cuándo pasa el tiempo. El stub de ModernModal
# imita lo que importa del real (base.html): abre el overlay y enfoca «Sí, …» a los 10 ms.
_ARNES_JS = r"""
const fs = require('fs');
const entrada = JSON.parse(fs.readFileSync(0, 'utf8'));
let ahora = 1000;
Date.now = () => ahora;
let timers = [];
global.setTimeout = (fn, ms) => { timers.push({ fn, en: ahora + (ms || 0) }); };
function avanzar(ms) {
  const hasta = ahora + ms;
  while (true) {
    timers.sort((a, b) => a.en - b.en);
    if (!timers.length || timers[0].en > hasta) break;
    const t = timers.shift();
    ahora = t.en;
    t.fn();
  }
  ahora = hasta;
}
let overlayOculto = true;
let foco = null;
const oyentes = {};
const boton = { disabled: false };
const form = {
  dataset: {},
  elements: { total_pedido: { value: entrada.pedido } },
  envios: 0,
  submit() { this.envios++; },
  querySelector() { return boton; },
  addEventListener(tipo, fn) { oyentes[tipo] = fn; },
};
if (entrada.pendientes !== undefined) form.dataset.pendientes = entrada.pendientes;
const selector = entrada.escenario === 'frenar' ? 'form[data-confirmar-frenar]' : 'form[data-confirmar-masivo]';
global.window = global;
let relecturas = 0;
global.location = { reload() { relecturas++; } };
global.document = {
  querySelector: (sel) => (sel === selector ? form : null),
  getElementById: (id) => {
    if (id === 'modal-overlay') return { classList: { contains: (c) => c === 'hidden' && overlayOculto } };
    if (id === 'modal-cancel') return { focus() { foco = 'cancelar'; } };
    return null;
  },
};
const mostrados = [];
global.ModernModal = {
  show(op) { mostrados.push(op); overlayOculto = false; setTimeout(() => { foco = 'confirmar'; }, 10); },
};
eval(entrada.script);
const evento = { preventDefault() {} };
const r = {};
oyentes.submit(evento);
r.modales = mostrados.length;
r.titulo = mostrados[0] && mostrados[0].title;
r.mensaje = mostrados[0] && mostrados[0].message;
r.boton = mostrados[0] && mostrados[0].confirmText;
r.danger = mostrados[0] && mostrados[0].danger;
avanzar(60);
r.foco = foco;
oyentes.submit(evento);  // un Enter de más sobre el input con el modal abierto
r.modales_tras_otro_submit = mostrados.length;
mostrados[0].onConfirm();  // segundo Enter a los 60 ms del primero: no confirma
r.envios_rapido = form.envios;
avanzar(500);
mostrados[0].onConfirm();
mostrados[0].onConfirm();  // doble clic durante el cierre de ModernModal
r.envios = form.envios;
r.boton_deshabilitado = boton.disabled;
overlayOculto = true;
oyentes.submit(evento);
r.modales_final = mostrados.length;
avanzar(6000);
r.relecturas = relecturas;
process.stdout.write(JSON.stringify(r));
"""


@skipUnless(shutil.which("node"), "node no está instalado")
class ConfirmacionProcesoMasivoJsTests(_BaseProcesoTest):
    """Comportamiento del script (POP-6, ronda 2): un solo envío aunque haya doble
    clic o doble Enter, y el foco arranca en Cancelar."""

    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_superuser("admin_js", password="x")
        self.client.force_login(self.admin)
        self.url = reverse("becas:proceso_masivo", args=[self.programa.pk])

    def _script(self):
        html = self.client.get(self.url).content.decode()
        scripts = re.findall(r"<script>(.*?)</script>", html, flags=re.S)
        propios = [s for s in scripts if "confirmarYEnviar" in s]
        self.assertEqual(len(propios), 1)
        return propios[0]

    def _correr(self, escenario, **datos):
        entrada = json.dumps({"script": self._script(), "escenario": escenario, **datos})
        salida = subprocess.run(
            [shutil.which("node"), "-e", _ARNES_JS],
            input=entrada,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
        )
        self.assertEqual(salida.returncode, 0, salida.stderr)
        return json.loads(salida.stdout)

    def test_lanzar_envia_una_sola_vez_y_enfoca_cancelar(self):
        self._caso()
        r = self._correr("lanzar", pendientes="1200", pedido="1000")
        self.assertEqual(r["modales"], 1)
        self.assertTrue(r["danger"])
        self.assertEqual(r["titulo"], "¿Procesar hasta 1.000 casos?")
        self.assertEqual(r["boton"], "Sí, procesar hasta 1.000")
        self.assertIn("Los casos incompletos se saltean y siguen pendientes.", r["mensaje"])
        self.assertIn("Quedan al menos 200 pendientes", r["mensaje"])
        self.assertEqual(r["foco"], "cancelar")
        self.assertEqual(r["modales_tras_otro_submit"], 1)
        self.assertEqual(r["envios_rapido"], 0)
        self.assertEqual(r["envios"], 1)
        self.assertTrue(r["boton_deshabilitado"])
        self.assertEqual(r["modales_final"], 1)

    def test_lanzar_sin_resto_omite_la_ultima_frase(self):
        self._caso()
        r = self._correr("lanzar", pendientes="1", pedido="1000")
        self.assertEqual(r["titulo"], "¿Procesar hasta 1 caso?")
        self.assertNotIn("Queda", r["mensaje"])

    def test_frenar_envia_una_sola_vez_y_no_relee_despues(self):
        CorridaSiis.objects.create(
            programa=self.programa, solicitada_por=self.admin, total_pedido=10, latido=timezone.now()
        )
        r = self._correr("frenar")
        self.assertEqual(r["titulo"], "¿Frenar la corrida?")
        self.assertEqual(r["boton"], "Sí, frenar")
        self.assertEqual(r["foco"], "cancelar")
        self.assertEqual(r["envios_rapido"], 0)
        self.assertEqual(r["envios"], 1)
        self.assertTrue(r["boton_deshabilitado"])
        # La relectura espera con el modal abierto y no pisa el envío ya hecho.
        self.assertEqual(r["relecturas"], 0)


class FiltroAprobadosMateriasTests(_BaseProcesoTest):
    """Cambio 90: a SIIS solo van los DNI de ``aprobados_materias``."""

    def _otro_ciudadano(self, dni):
        return Ciudadano.objects.create(
            dni=dni, nombre="Otra", apellido="Persona", fecha_nacimiento=date(1990, 1, 1), genero="F"
        )

    def _caso_de(self, ciudadano):
        return Formulario.objects.create(
            relevamiento=self.relevamiento,
            ciudadano=ciudadano,
            estado=Formulario.Estado.ENVIADO,
            validado_renaper=True,
        )

    def test_deja_afuera_al_dni_que_no_esta_en_la_tabla(self):
        adentro = self._caso()
        afuera = self._caso_de(self._otro_ciudadano("99887766"))
        pks = set(proceso_masivo.candidatos(programa=self.programa).values_list("pk", flat=True))
        self.assertIn(adentro.pk, pks)
        self.assertNotIn(afuera.pk, pks)

    def test_sin_filtro_entran_todos(self):
        self._caso()
        self._caso_de(self._otro_ciudadano("99887766"))
        self.assertEqual(proceso_masivo.candidatos(programa=self.programa, filtrar_materias=False).count(), 2)

    def test_cruza_aunque_la_planilla_venga_sin_ceros_o_con_puntos(self):
        """Excel se come los ceros a la izquierda; la base puede tenerlos."""
        borrar_tabla_aprobados_materias()
        crear_tabla_aprobados_materias("7.654.321")
        caso = self._caso_de(self._otro_ciudadano("07654321"))
        self.assertIn(caso.pk, proceso_masivo.candidatos(programa=self.programa).values_list("pk", flat=True))

    def test_sin_la_tabla_falla_cerrado(self):
        """La tabla decide quien NO va. Si falta, mandar a todos seria el error que evita."""
        borrar_tabla_aprobados_materias()
        self._caso()
        with self.assertRaises(proceso_masivo.TablaAprobadosMateriasFaltante):
            list(proceso_masivo.candidatos(programa=self.programa))

    def test_sin_la_tabla_la_corrida_queda_detenida_con_el_motivo(self):
        borrar_tabla_aprobados_materias()
        corrida = CorridaSiis.objects.create(programa=self.programa, total_pedido=5)
        with patch("programas.services.proceso_masivo.Catalogos"):
            corrida = proceso_masivo.correr(corrida)
        self.assertEqual(corrida.estado, CorridaSiis.Estado.DETENIDA)
        self.assertIn("aprobados_materias", corrida.mensaje)


class PantallaSinTablaMateriasTests(_BaseProcesoTest):
    def setUp(self):
        super().setUp()
        borrar_tabla_aprobados_materias()
        self.admin = User.objects.create_superuser("admin_sin_tabla", password="x")
        self.client.force_login(self.admin)

    def test_la_pantalla_avisa_y_no_ofrece_lanzar(self):
        resp = self.client.get(reverse("becas:proceso_masivo", args=[self.programa.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Falta la tabla que decide qui\u00e9n va a SIIS")
        self.assertNotContains(resp, 'name="total_pedido"')

    def test_lanzar_no_crea_la_corrida(self):
        with patch("programas.views.proceso_masivo.servicio.lanzar") as lanzar:
            self.client.post(reverse("becas:proceso_masivo_lanzar", args=[self.programa.pk]), {"total_pedido": "5"})
        self.assertFalse(CorridaSiis.objects.exists())
        lanzar.assert_not_called()
