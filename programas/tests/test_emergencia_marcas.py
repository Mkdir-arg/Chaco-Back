"""Módulo Emergencia, PR 11: los avisos de la mesa que dependen de las etapas 3 y 4.

Cada marca se prueba por la pantalla —en la fila de la bandeja (E2) y en la cabecera de la
ficha (E3)— con su texto exacto: aparece cuando corresponde y se va con la acción siguiente.

* **RN-3.13** — «Rechazado por X: motivo» hasta la próxima acción sobre el caso.
* **HU-2.5** — «Derivación vencida · volver a derivar» hasta la próxima acción.
* **02 §9** — «Dispositivo inactivo · volver a derivar» mientras la derivación pendiente
  apunte a un dispositivo que dejó de estar activo.
* **RN-3.8** — «Llegaron 2 sobre 1 declaradas».
* **RN-3.9 / HU-3.4** — «Ingreso parcial · 1 de 7» en la fila, con el motivo en la ficha.
* **M2-6** — «En la puerta de X» mientras la mesa no lo derivó; «Ingreso directo» sigue.
* **Presupuestos** — E2 con 500 casos y E3 cuestan lo mismo que sin marcas (17 y 18).

Mutación vista en rojo: con el «sin acción posterior» del rechazo roto (la condición sobre
``ultima_accion`` reemplazada por ``True``), ``test_el_rechazo_se_va_con_la_accion_siguiente``
y ``test_volver_a_derivar_saca_el_rechazo`` fallan con la marca todavía en la fila.
"""

from datetime import timedelta

from django.db import connection
from django.test import tag
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from programas.models import CasoEmergencia, Derivacion, Dispositivo, GrupoFamiliar, TrazaCaso
from programas.services import emergencia as mesa
from programas.services import emergencia_alojar as servicio
from programas.tests import test_emergencia_mesa as tests_mesa
from programas.tests.test_emergencia_alojar import BaseAlojar

Estado = CasoEmergencia.Estado
Origen = CasoEmergencia.Origen
Accion = TrazaCaso.Accion

URL_BANDEJA = "/emergencia/casos/"

RECHAZO = "Rechazado por Club Sarmiento: sin plazas"
VENCIDA = "Derivación vencida · volver a derivar"
INACTIVO = "Dispositivo inactivo · volver a derivar"


class BaseMarcas(BaseAlojar):
    def _fila(self, caso):
        """Los textos de las marcas de la fila del caso en la bandeja (solapa «Abiertos»)."""

        self.client.force_login(self.operador)
        respuesta = self.client.get(URL_BANDEJA, {"texto": caso.numero})
        self.assertEqual(respuesta.status_code, 200)
        filas = [fila for fila in respuesta.context["filas"] if fila["caso"].pk == caso.pk]
        self.assertEqual(len(filas), 1, "el caso no está en la bandeja")
        marcas = [marca["texto"] for marca in filas[0]["marcas"]]
        for texto in marcas:
            self.assertContains(respuesta, texto)
        return marcas

    def _ficha(self, caso):
        """Los títulos de los avisos de la ficha y la respuesta, para mirar el HTML."""

        self.client.force_login(self.operador)
        respuesta = self.client.get(reverse("emergencia:caso_detalle", args=[caso.pk]))
        self.assertEqual(respuesta.status_code, 200)
        return [aviso["texto"] for aviso in respuesta.context["avisos"]], respuesta

    def _rechazado(self, motivo="SIN_PLAZAS", observacion=""):
        caso, derivacion = self._derivado()
        servicio.rechazar_derivacion(
            derivacion=derivacion, usuario=self.guardia, motivo=motivo, observacion=observacion
        )
        return CasoEmergencia.objects.get(pk=caso.pk)

    def _vencido(self):
        caso, derivacion = self._derivado()
        self.reloj.ahora = derivacion.vence_en + timedelta(minutes=1)
        self.assertIsNotNone(mesa.vencer_derivacion(derivacion))
        return CasoEmergencia.objects.get(pk=caso.pk)


# ---------------------------------------------------------------------------
# RN-3.13 · Rechazado por X
# ---------------------------------------------------------------------------


class RechazoTests(BaseMarcas):
    def test_el_rechazo_marca_la_fila_y_la_ficha(self):
        caso = self._rechazado()

        self.assertIn(RECHAZO, self._fila(caso))
        avisos, ficha = self._ficha(caso)
        self.assertEqual(avisos, [RECHAZO])
        self.assertContains(ficha, "El caso volvió a gestión: derivalo a otro dispositivo o cerralo.")

    def test_con_motivo_otro_la_ficha_muestra_lo_que_contó_el_dispositivo(self):
        caso = self._rechazado(motivo="OTRO", observacion="Se inundó el salón")

        self.assertIn("Rechazado por Club Sarmiento: otro", self._fila(caso))
        _avisos, ficha = self._ficha(caso)
        self.assertContains(ficha, "Se inundó el salón")

    def test_el_rechazo_se_va_con_la_accion_siguiente(self):
        caso = self._rechazado()
        mesa.registrar_contacto(caso, self.operador, canal="LLAMADA", resultado="ATENDIO")

        self.assertNotIn(RECHAZO, self._fila(caso))
        avisos, ficha = self._ficha(caso)
        self.assertEqual(avisos, [])
        # La traza sigue diciendo «Rechazado por …»: lo que se va es el aviso de la cabecera.
        self.assertNotContains(ficha, "El caso volvió a gestión: derivalo a otro dispositivo o cerralo.")

    def test_volver_a_derivar_saca_el_rechazo(self):
        caso = self._rechazado()
        mesa.derivar_caso(caso, self.operador, self.escuela, 5, True)

        self.assertNotIn(RECHAZO, self._fila(caso))

    def test_un_segundo_rechazo_nombra_al_ultimo_dispositivo(self):
        caso = self._rechazado()
        derivacion = mesa.derivar_caso(caso, self.operador, self.escuela, 5, True)
        servicio.rechazar_derivacion(derivacion=derivacion, usuario=self.guardia_escuela, motivo="NO_CUMPLE_PERFIL")

        marcas = self._fila(caso)
        self.assertIn("Rechazado por Escuela 12: no cumple perfil", marcas)
        self.assertNotIn(RECHAZO, marcas)


# ---------------------------------------------------------------------------
# HU-2.5 · Derivación vencida
# ---------------------------------------------------------------------------


class VencidaTests(BaseMarcas):
    def test_la_vencida_marca_la_fila_y_la_ficha(self):
        caso = self._vencido()

        self.assertIn(VENCIDA, self._fila(caso))
        avisos, ficha = self._ficha(caso)
        self.assertEqual(avisos, [VENCIDA])
        self.assertContains(ficha, "El dispositivo no respondió a tiempo y el caso volvió a gestión.")

    def test_la_vencida_esta_en_fuera_de_sla(self):
        caso = self._vencido()
        self.client.force_login(self.operador)
        respuesta = self.client.get(URL_BANDEJA, {"solapa": "fuera_sla"})
        self.assertIn(caso.pk, [fila["caso"].pk for fila in respuesta.context["filas"]])
        self.assertContains(respuesta, VENCIDA)

    def test_la_vencida_se_va_con_la_accion_siguiente(self):
        caso = self._vencido()
        mesa.cambiar_prioridad(caso, self.operador, CasoEmergencia.Prioridad.BAJA)

        self.assertNotIn(VENCIDA, self._fila(caso))
        self.assertEqual(self._ficha(caso)[0], [])


# ---------------------------------------------------------------------------
# 02 §9 · Dispositivo inactivo
# ---------------------------------------------------------------------------


class DispositivoInactivoTests(BaseMarcas):
    def _apagar(self, dispositivo):
        Dispositivo.objects.filter(pk=dispositivo.pk).update(estado=Dispositivo.Estado.INACTIVO)

    def test_la_derivacion_pendiente_a_un_inactivo_marca_la_fila_y_la_ficha(self):
        caso, _derivacion = self._derivado()
        self.assertNotIn(INACTIVO, self._fila(caso))

        self._apagar(self.club)

        self.assertIn(INACTIVO, self._fila(caso))
        avisos, ficha = self._ficha(caso)
        self.assertEqual(avisos, [INACTIVO])
        self.assertContains(ficha, "Cancelá la derivación y derivalo a otro.")

    def test_cancelar_la_derivacion_saca_la_marca(self):
        caso, derivacion = self._derivado()
        self._apagar(self.club)
        mesa.cancelar_derivacion(derivacion, self.operador, "El club cerró")

        self.assertNotIn(INACTIVO, self._fila(caso))

    def test_si_el_dispositivo_vuelve_a_estar_activo_la_marca_se_va(self):
        caso, _derivacion = self._derivado()
        self._apagar(self.club)
        Dispositivo.objects.filter(pk=self.club.pk).update(estado=Dispositivo.Estado.ACTIVO)

        self.assertNotIn(INACTIVO, self._fila(caso))

    def test_con_la_derivacion_aceptada_no_se_marca(self):
        caso, _derivacion = self._aceptado()
        self._apagar(self.club)

        self.assertNotIn(INACTIVO, self._fila(caso))


# ---------------------------------------------------------------------------
# RN-3.8 y RN-3.9 · Llegaron más, llegaron menos
# ---------------------------------------------------------------------------


class LlegaronTests(BaseMarcas):
    def test_agregar_una_persona_marca_llegaron_mas_que_las_declaradas(self):
        caso, _derivacion = self._aceptado(menores_f=0, menores_m=0, adultos_m=0)
        self.assertNotIn("Llegaron 2 sobre 1 declaradas", self._fila(caso))

        servicio.agregar_integrante(caso=caso, usuario=self.guardia)

        self.assertIn("Llegaron 2 sobre 1 declaradas", self._fila(caso))
        avisos, _ficha = self._ficha(caso)
        self.assertEqual(avisos, ["Llegaron 2 sobre 1 declaradas"])

    def test_el_ingreso_parcial_va_en_la_fila_y_el_motivo_en_la_ficha(self):
        caso, _derivacion = self._aceptado()
        self._confirmar(caso, 2, "45000111")
        self.assertNotIn("Ingreso parcial · 1 de 7", self._fila(caso))

        servicio.cerrar_con_diferencia(
            caso=caso, usuario=self.guardia, motivo="NO_LLEGO", observacion="Quedaron en lo de la abuela"
        )

        self.assertIn("Ingreso parcial · 1 de 7", self._fila(caso))
        _avisos, ficha = self._ficha(caso)
        self.assertContains(ficha, "Ingreso parcial · 1 de 7 personas alojadas · No llegó al centro")
        self.assertContains(ficha, "Quedaron en lo de la abuela")


# ---------------------------------------------------------------------------
# M2-6 · En la puerta de X, e ingreso directo
# ---------------------------------------------------------------------------


class EnLaPuertaTests(BaseMarcas):
    def _en_la_puerta(self):
        return servicio.avisar_a_la_mesa(
            dispositivo=self.club, usuario=self.guardia, datos_formulario1=self._datos(dni="33444555")
        )

    def test_el_aviso_marca_la_fila_y_la_ficha_hasta_que_la_mesa_lo_deriva(self):
        caso = self._en_la_puerta()
        marcas = self._fila(caso)
        self.assertIn("En la puerta de Club Sarmiento", marcas)
        self.assertNotIn("Ingreso directo", marcas)
        _avisos, ficha = self._ficha(caso)
        self.assertEqual(ficha.context["alojamiento"]["en_la_puerta"], "Club Sarmiento")
        self.assertContains(ficha, "La guardia de ese dispositivo avisó")

        # Tomarlo no lo saca: la familia sigue esperando.
        caso = mesa.tomar_caso(caso, self.operador)
        self.assertIn("En la puerta de Club Sarmiento", self._fila(caso))

        mesa.derivar_caso(caso, self.operador, self.club, caso.grupo.total_declarado, True)

        marcas = self._fila(caso)
        self.assertNotIn("En la puerta de Club Sarmiento", marcas)
        self.assertNotIn("Ingreso directo", marcas)
        _avisos, ficha = self._ficha(caso)
        # La traza conserva el aviso del dispositivo; la cabecera ya no lo muestra.
        self.assertEqual(ficha.context["alojamiento"]["en_la_puerta"], "")
        self.assertNotContains(ficha, "La guardia de ese dispositivo avisó")

    def test_el_ingreso_directo_sigue_marcado(self):
        caso = servicio.ingreso_directo(
            dispositivo=self.club, usuario=self.guardia, datos_formulario1=self._datos(dni="33444666")
        )
        self.assertIn("Ingreso directo", self._fila(caso))
        _avisos, ficha = self._ficha(caso)
        self.assertContains(ficha, "sin pasar por la mesa")


# ---------------------------------------------------------------------------
# Presupuestos
# ---------------------------------------------------------------------------


@tag("performance")
class PresupuestoConMarcasTests(tests_mesa.BaseMesa):
    """Con todas las marcas en la página, E2 y E3 cuestan lo mismo que sin ellas."""

    CONSULTAS_E2 = tests_mesa.PresupuestoDeConsultasTests.CONSULTAS_E2
    CONSULTAS_E3 = tests_mesa.PresupuestoDeConsultasTests.CONSULTAS_E3
    _casos_en_lote = tests_mesa.PresupuestoDeConsultasTests._casos_en_lote

    MARCAS = (
        "Rechazado por Club Sarmiento: sin plazas",
        VENCIDA,
        INACTIVO,
        "Llegaron 3 sobre 2 declaradas",
        "Ingreso parcial · 1 de 2",
        "En la puerta de Club Sarmiento",
        "Ingreso directo",
    )

    def _con_todas_las_marcas(self, casos):
        """Reparte las siete marcas entre los casos, escribiendo las filas a mano: acá se mide leer."""

        apagado = self._dispositivo("Escuela cerrada", camas=2, estado=Dispositivo.Estado.INACTIVO)
        derivaciones, trazas, grupos = [], [], []
        vence = self.reloj.ahora + timedelta(hours=12)
        for n, caso in enumerate(casos):
            marca = n % 7
            if marca == 0:
                caso.estado = Estado.EN_GESTION
                derivaciones.append(
                    Derivacion(
                        caso=caso,
                        dispositivo=self.club,
                        estado=Derivacion.Estado.RECHAZADA,
                        plazas_pedidas=2,
                        vence_en=vence,
                        derivada_por=self.operador,
                        motivo="Sin plazas",
                        respondida_en=self.reloj.ahora,
                    )
                )
                trazas.append(TrazaCaso(caso=caso, accion=Accion.DERIVACION_RECHAZADA))
            elif marca == 1:
                caso.estado = Estado.EN_GESTION
                trazas.append(TrazaCaso(caso=caso, accion=Accion.DERIVACION_VENCIDA))
            elif marca == 2:
                caso.estado = Estado.DERIVADO
                derivaciones.append(
                    Derivacion(
                        caso=caso, dispositivo=apagado, plazas_pedidas=2, vence_en=vence, derivada_por=self.operador
                    )
                )
            elif marca == 3:
                caso.grupo.total_declarado = 3
                grupos.append(caso.grupo)
            elif marca == 4:
                caso.estado = Estado.ALOJADO
                caso.total_alojado = 1
            elif marca == 5:
                caso.origen = Origen.DISPOSITIVO
                caso.estado = Estado.NUEVO
                caso.tomado_por = None
                caso.derivado_en = None
                caso.situacion = {"en_la_puerta_de": {"dispositivo_id": self.club.pk, "dispositivo": "Club Sarmiento"}}
            else:
                caso.origen = Origen.DISPOSITIVO
        CasoEmergencia.objects.bulk_update(
            casos, ["estado", "total_alojado", "origen", "tomado_por", "derivado_en", "situacion"]
        )
        GrupoFamiliar.objects.bulk_update(grupos, ["total_declarado"])
        for derivacion in derivaciones:
            derivacion.save()
        TrazaCaso.objects.bulk_create(trazas)

    def test_e2_con_500_casos_y_todas_las_marcas(self):
        self._con_todas_las_marcas(self._casos_en_lote(500))
        self.client.force_login(self.operador)
        self.client.get(URL_BANDEJA)

        with self.assertNumQueries(self.CONSULTAS_E2):
            respuesta = self.client.get(URL_BANDEJA)

        self.assertEqual(respuesta.context["page_obj"].paginator.count, 500)
        en_la_pagina = {marca["texto"] for fila in respuesta.context["filas"] for marca in fila["marcas"]}
        for marca in self.MARCAS:
            self.assertIn(marca, en_la_pagina)
            self.assertContains(respuesta, marca)

    def test_e3_con_las_marcas_cuesta_lo_mismo(self):
        caso = self._caso_tomado()
        Derivacion.objects.create(
            caso=caso,
            dispositivo=self.club,
            estado=Derivacion.Estado.RECHAZADA,
            plazas_pedidas=2,
            vence_en=self.reloj.ahora,
            derivada_por=self.operador,
            motivo="Sin plazas",
            respondida_en=self.reloj.ahora,
        )
        TrazaCaso.objects.create(caso=caso, accion=Accion.DERIVACION_RECHAZADA)
        GrupoFamiliar.objects.filter(pk=caso.grupo_id).update(total_declarado=3)
        self.client.force_login(self.operador)
        self._ficha(caso)

        with self.assertNumQueries(self.CONSULTAS_E3):
            respuesta = self._ficha(caso)

        self.assertEqual(
            [aviso["texto"] for aviso in respuesta.context["avisos"]],
            ["Rechazado por Club Sarmiento: sin plazas", "Llegaron 3 sobre 2 declaradas"],
        )

    def test_e3_derivado_a_un_inactivo_cuesta_lo_mismo_que_a_un_activo(self):
        caso = self._caso_tomado()
        mesa.derivar_caso(caso, self.operador, self.club, 2)
        self.client.force_login(self.operador)
        self._ficha(caso)
        with CaptureQueriesContext(connection) as activo:
            self.assertEqual(self._ficha(caso).context["avisos"], [])

        Dispositivo.objects.filter(pk=self.club.pk).update(estado=Dispositivo.Estado.INACTIVO)
        with self.assertNumQueries(len(activo)):
            respuesta = self._ficha(caso)
        self.assertEqual([aviso["texto"] for aviso in respuesta.context["avisos"]], [INACTIVO])
