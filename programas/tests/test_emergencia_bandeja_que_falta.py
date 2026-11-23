"""Cambio 580: la columna «Qué falta» de la bandeja de casos.

Cada combinación de estado del caso (y de su derivación) tiene un texto, y se prueba por la pantalla: la fila de la
bandeja trae ``que_falta`` y el HTML lo dibuja. La columna no cambia estados: solo dice qué sigue.

Mutación vista en rojo: con la rama de «rechazada» de ``que_falta`` apagada, ``test_en_gestion_tras_un_rechazo``
falla con «Derivarlo a una institución» en lugar de «a otra institución»; con el filtro de «Sin tomar» sin el
``tomado_por__isnull``, ``test_sin_tomar_no_trae_lo_que_ya_tiene_dueno`` falla.
"""

from datetime import timedelta

from django.db import connection
from django.test import tag
from django.test.utils import CaptureQueriesContext

from programas.models import CasoEmergencia, Dispositivo
from programas.services import emergencia as mesa
from programas.tests.test_emergencia_marcas import URL_BANDEJA, BaseMarcas

Estado = CasoEmergencia.Estado


class QueFaltaTests(BaseMarcas):
    def _que_falta(self, caso, solapa="abiertos"):
        self.client.force_login(self.operador)
        respuesta = self.client.get(URL_BANDEJA, {"texto": caso.numero, "solapa": solapa})
        self.assertEqual(respuesta.status_code, 200)
        filas = [fila for fila in respuesta.context["filas"] if fila["caso"].pk == caso.pk]
        self.assertEqual(len(filas), 1, "el caso no está en la bandeja")
        que_falta = filas[0]["que_falta"]
        self.assertContains(respuesta, que_falta["texto"])
        if que_falta["nota"]:
            self.assertContains(respuesta, que_falta["nota"])
        return que_falta

    def test_nuevo_hay_que_tomarlo(self):
        caso = self._caso()
        self.assertEqual(self._que_falta(caso), {"texto": "Tomarlo", "nota": "", "urgente": False})

    def test_nuevo_con_la_familia_en_la_puerta(self):
        caso = self._caso()
        CasoEmergencia.objects.filter(pk=caso.pk).update(
            situacion={
                CasoEmergencia.SITUACION_EN_LA_PUERTA: {"dispositivo_id": self.club.pk, "dispositivo": "Club Sarmiento"}
            }
        )
        self.assertEqual(
            self._que_falta(caso),
            {"texto": "Tomarlo", "nota": "La familia espera en la puerta de Club Sarmiento", "urgente": True},
        )

    def test_en_gestion_hay_que_derivarlo(self):
        caso = self._caso_tomado()
        self.assertEqual(self._que_falta(caso), {"texto": "Derivarlo a una institución", "nota": "", "urgente": False})

    def test_en_gestion_tras_un_rechazo(self):
        caso = self._rechazado()
        self.assertEqual(
            self._que_falta(caso),
            {
                "texto": "Derivarlo a otra institución",
                "nota": "Club Sarmiento no lo aceptó: sin plazas",
                "urgente": True,
            },
        )

    def test_el_rechazo_se_apaga_con_la_accion_siguiente(self):
        caso = self._rechazado()
        mesa.registrar_contacto(caso, self.operador, canal="LLAMADA", resultado="ATENDIO")
        self.assertEqual(self._que_falta(caso)["texto"], "Derivarlo a una institución")

    def test_en_gestion_tras_una_derivacion_vencida(self):
        caso = self._vencido()
        self.assertEqual(
            self._que_falta(caso),
            {"texto": "Derivarlo de nuevo", "nota": "La institución no respondió a tiempo", "urgente": True},
        )

    def test_derivado_espera_que_la_institucion_acepte(self):
        caso, _derivacion = self._derivado()
        self.assertEqual(
            self._que_falta(caso),
            {"texto": "Esperar que Club Sarmiento lo acepte", "nota": "", "urgente": False},
        )

    def test_derivado_con_el_plazo_cumplido_sin_marcar(self):
        caso, derivacion = self._derivado()
        self.reloj.ahora = derivacion.vence_en + timedelta(minutes=1)
        self.assertEqual(
            self._que_falta(caso),
            {
                "texto": "Confirmar con Club Sarmiento si lo acepta",
                "nota": "Pasó el plazo para responder",
                "urgente": True,
            },
        )

    def test_derivado_a_una_institucion_que_dejo_de_estar_activa(self):
        caso, _derivacion = self._derivado()
        Dispositivo.objects.filter(pk=self.club.pk).update(estado=Dispositivo.Estado.INACTIVO)
        self.assertEqual(
            self._que_falta(caso),
            {
                "texto": "Cancelar la derivación y derivarlo a otra institución",
                "nota": "Club Sarmiento dejó de estar activa",
                "urgente": True,
            },
        )

    def test_ingreso_en_curso_espera_que_confirmen_a_las_personas(self):
        caso, _derivacion = self._aceptado()
        self.assertEqual(caso.estado, Estado.INGRESO_EN_CURSO)
        self.assertEqual(
            self._que_falta(caso),
            {"texto": "Esperar que Club Sarmiento confirme a las personas", "nota": "", "urgente": False},
        )

    def test_ingreso_en_curso_sin_movimiento(self):
        caso, _derivacion = self._aceptado()
        self.reloj.avanzar(hours=30)
        que_falta = self._que_falta(caso)
        self.assertEqual(que_falta["texto"], "Contactar a Club Sarmiento")
        self.assertTrue(que_falta["urgente"])
        self.assertIn("sin movimiento hace", que_falta["nota"])

    def test_alojado_completo_no_falta_nada(self):
        caso = self._alojado_con(total_alojado=2)
        self.assertEqual(
            self._que_falta(caso, "alojados"),
            {"texto": "Nada: se cierra cuando egrese la familia", "nota": "", "urgente": False},
        )

    def test_alojado_con_ingreso_parcial(self):
        caso = self._alojado_con(total_alojado=1)
        self.assertEqual(
            self._que_falta(caso, "alojados"),
            {
                "texto": "Contactar a la familia",
                "nota": "Falta 1 persona de las 2 declaradas",
                "urgente": True,
            },
        )

    def test_cerrado_dice_el_motivo(self):
        caso = self._caso_tomado()
        mesa.cerrar_sin_alojamiento(caso, self.operador, CasoEmergencia.MotivoCierre.NO_REQUIERE)
        que_falta = self._que_falta(caso, "cerrados")
        self.assertEqual(que_falta["texto"], "Nada: el caso está cerrado")
        self.assertTrue(que_falta["nota"])
        self.assertFalse(que_falta["urgente"])

    def _alojado_con(self, *, total_alojado):
        caso = self._caso()
        CasoEmergencia.objects.filter(pk=caso.pk).update(
            estado=Estado.ALOJADO,
            total_alojado=total_alojado,
            tomado_en=caso.creado,
            derivado_en=caso.creado,
            aceptado_en=caso.creado,
            alojado_en=caso.creado,
        )
        caso.refresh_from_db()
        return caso


class QueFaltaSinConsultasPorFilaTests(BaseMarcas):
    @tag("performance")
    def test_la_columna_cuesta_lo_mismo_con_pocos_casos_que_con_muchos(self):
        self.client.force_login(self.operador)

        def consultas():
            self.client.get(URL_BANDEJA, {"solapa": "abiertos"})  # calienta el proceso
            with CaptureQueriesContext(connection) as capturadas:
                self.client.get(URL_BANDEJA, {"solapa": "abiertos"})
            return len(capturadas)

        self._derivado()
        con_uno = consultas()
        for _ in range(4):
            self._derivado()
        self._caso_tomado()
        self._rechazado()
        self.assertEqual(consultas(), con_uno)


class EnlacesQueEntranALaBandejaTests(BaseMarcas):
    """Los enlaces que arma el código y no traen solapa no pueden caer en «Sin tomar» (Cambio 580)."""

    def _numeros(self, url):
        self.client.force_login(self.operador)
        respuesta = self.client.get(url)
        self.assertEqual(respuesta.status_code, 200)
        return {fila["caso"].numero for fila in respuesta.context["filas"]}

    def test_el_aviso_de_ingresos_parciales_lleva_a_los_alojados(self):
        from programas.services import avisos_emergencia
        from programas.services.configuracion_emergencia import sla_vigente

        casos = []
        for n in range(avisos_emergencia.TOPE_POR_REGLA + 1):
            caso = self._caso(dni=str(30700000 + n), apellido=f"Parcial{n}")
            CasoEmergencia.objects.filter(pk=caso.pk).update(
                estado=Estado.ALOJADO,
                total_alojado=1,
                tomado_en=caso.creado,
                derivado_en=caso.creado,
                aceptado_en=caso.creado,
                alojado_en=caso.creado,
            )
            casos.append(caso)
        avisos = avisos_emergencia.ingresos_parciales_sin_revisar(
            sla_vigente(), self.reloj.ahora + timedelta(hours=1), self.operador
        )
        resumen = avisos[-1]
        self.assertTrue(resumen.enlace.endswith("?solapa=alojados"), resumen.enlace)
        self.assertIn(casos[-1].numero, self._numeros(resumen.enlace))


class FiltrarSinSolapaEnLaUrlTests(BaseMarcas):
    """Con la solapa implícita, buscar o filtrar por quién lo tiene mira todos los abiertos (Cambio 580)."""

    def setUp(self):
        super().setUp()
        self.ajeno = self._caso_tomado(por=self.otro_operador, apellido="Ajena")
        self.client.force_login(self.operador)

    def _numeros(self, filtros):
        respuesta = self.client.get(URL_BANDEJA, filtros)
        self.assertEqual(respuesta.status_code, 200)
        return [fila["caso"].numero for fila in respuesta.context["filas"]], respuesta

    def test_filtrar_por_el_operador_que_lo_tiene(self):
        numeros, _ = self._numeros({"operador": str(self.otro_operador.pk)})
        self.assertEqual(numeros, [self.ajeno.numero])

    def test_buscar_por_dni_y_por_numero_de_un_caso_con_dueno(self):
        for texto in (self.ajeno.grupo.responsable.dni, self.ajeno.numero):
            with self.subTest(texto=texto):
                self.assertEqual(self._numeros({"texto": texto})[0], [self.ajeno.numero])

    def test_la_solapa_implicita_no_se_vuelve_explicita_al_filtrar(self):
        _, respuesta = self._numeros({"texto": self.ajeno.numero})
        self.assertNotContains(respuesta, 'name="solapa"')
        self.assertEqual(respuesta.context["solapa_explicita"], "")

    def test_una_solapa_explicita_se_respeta_y_su_hidden_se_conserva(self):
        numeros, respuesta = self._numeros({"solapa": "sin_tomar", "texto": self.ajeno.numero})
        self.assertEqual(numeros, [])
        self.assertContains(respuesta, '<input type="hidden" name="solapa" value="sin_tomar">', html=True)

    def test_sin_filtros_sigue_abriendo_sin_tomar(self):
        self._caso(dni="30800001", apellido="Libre")
        numeros, _ = self._numeros({})
        self.assertNotIn(self.ajeno.numero, numeros)
        self.assertEqual(len(numeros), 1)
