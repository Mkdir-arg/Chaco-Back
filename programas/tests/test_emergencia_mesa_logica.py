"""Cambio 533: la lógica de la bandeja, la ficha y el alta de la mesa de Emergencia.

Cada clase cubre un hallazgo del relevamiento de lógica del 22/11: la pantalla vieja de la ficha (6), los
modales que se cerraban con el error (19), la localidad del alta (8), el buscador de la bandeja (17), la
búsqueda de «Derivar» con acentos (21), la solapa «Alojados» (20) y la derivación vencida sin marcar (5).
"""

from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError

from core.models import Localidad
from legajos.models import Ciudadano
from programas.forms_emergencia import NuevoCasoMesaForm
from programas.models import CasoEmergencia, Derivacion, IntegranteGrupo
from programas.selectors import emergencia as selectores
from programas.selectors import emergencia_mesa as mesa
from programas.selectors.emergencia import ResponsableAlojado
from programas.services import emergencia as servicio
from programas.services import vencimientos_emergencia
from programas.services.configuracion_emergencia import sla_vigente
from programas.services.emergencia import CasoDeOtroOperador
from programas.tests.test_emergencia_casos import T0, localidad_operativa
from programas.tests.test_emergencia_mesa import URL_BANDEJA, BaseMesa

Estado = CasoEmergencia.Estado


# ---------------------------------------------------------------------------
# Hallazgo 6 · acción sobre una pantalla vieja
# ---------------------------------------------------------------------------


class PantallaViejaTests(BaseMesa):
    def setUp(self):
        super().setUp()
        self.caso = self._caso_tomado(por=self.operador)

    def test_el_servicio_distingue_el_caso_de_otro_del_que_nadie_tomo(self):
        with self.assertRaises(CasoDeOtroOperador) as error:
            servicio.cambiar_prioridad(self.caso, self.otro_operador, "ALTA")
        self.assertIsInstance(error.exception, PermissionDenied)  # la API lo sigue contestando como antes
        self.assertEqual(error.exception.caso.pk, self.caso.pk)
        self.assertIn("lo tiene tomado Ana López", str(error.exception))

    def test_sin_dueno_sigue_siendo_un_permission_denied_comun(self):
        nuevo = self._caso()
        with self.assertRaises(PermissionDenied) as error:
            servicio.cambiar_prioridad(nuevo, self.otro_operador, "ALTA")
        self.assertNotIsInstance(error.exception, CasoDeOtroOperador)

    def test_el_json_de_ubicar_el_domicilio_avisa_en_vez_de_dar_403(self):
        self.client.force_login(self.otro_operador)
        respuesta = self.client.post(
            self._url("caso_ubicar_domicilio", self.caso), {"latitud": "-27.46", "longitud": "-58.98"}
        )
        self.assertEqual(respuesta.status_code, 409)
        cuerpo = respuesta.json()
        self.assertFalse(cuerpo["guardado"])
        self.assertIn("lo tiene tomado Ana López", cuerpo["error"])

    def test_el_estado_que_cambio_vuelve_a_la_ficha_con_el_mensaje(self):
        self.client.force_login(self.operador)
        servicio.cerrar_sin_alojamiento(self.caso, self.operador, CasoEmergencia.MotivoCierre.NO_REQUIERE)
        respuesta = self._post("caso_prioridad", self.caso, {"prioridad": "ALTA"})
        self.assertRedirects(respuesta, self._url("caso_detalle", self.caso), fetch_redirect_response=False)
        self.assertEqual(
            self._avisos(respuesta), ["El caso está cerrado y no se reabre. Si hace falta, cargá uno nuevo."]
        )


# ---------------------------------------------------------------------------
# Hallazgo 19 · los modales reabren con lo enviado
# ---------------------------------------------------------------------------


class ModalesConErrorTests(BaseMesa):
    def setUp(self):
        super().setUp()
        self.caso = self._caso_tomado(por=self.operador)
        self.client.force_login(self.operador)

    def test_cerrar_con_otro_sin_observacion_reabre_el_modal_con_lo_escrito_y_el_error(self):
        respuesta = self._post("caso_cerrar", self.caso, {"motivo": "OTRO", "observacion": ""})
        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(respuesta.context["modal_abierto"], "cerrar")
        self.assertContains(respuesta, "modalCerrar: true", status_code=400)
        self.assertContains(respuesta, "Con el motivo «Otro», contá qué pasó.", status_code=400)
        form = respuesta.context["form_cierre"]
        self.assertTrue(form.is_bound)
        self.assertEqual(form["motivo"].value(), "OTRO")
        self.assertEqual(self._fila(self.caso)["estado"], Estado.EN_GESTION)

    def test_solo_se_abre_el_modal_de_la_accion_que_fallo(self):
        respuesta = self._post("caso_prioridad", self.caso, {"prioridad": "URGENTE"})
        self.assertContains(respuesta, "modalPrioridad: true", status_code=400)
        for otro in ("modalCerrar", "modalCancelar", "modalReasignar"):
            self.assertContains(respuesta, f"{otro}: false", status_code=400)

    def test_una_ficha_comun_arranca_con_todos_los_modales_cerrados(self):
        respuesta = self._ficha(self.caso)
        for modal in ("modalCerrar", "modalCancelar", "modalPrioridad", "modalReasignar"):
            self.assertContains(respuesta, f"{modal}: false")

    def test_el_contacto_conserva_lo_escrito_cuando_falta_un_dato(self):
        respuesta = self._post("caso_contacto", self.caso, {"canal": "", "observacion": "Esperan en la esquina"})
        self.assertEqual(respuesta.status_code, 400)
        self.assertContains(respuesta, "Esperan en la esquina", status_code=400)
        self.assertTrue(respuesta.context["form_contacto"].errors)


# ---------------------------------------------------------------------------
# Hallazgo 8 · la localidad del alta
# ---------------------------------------------------------------------------


class LocalidadDelAltaTests(BaseMesa):
    def setUp(self):
        super().setUp()
        self.ajena = localidad_operativa("Goya", provincia="Corrientes")
        self.sin_municipio = Localidad.objects.create(nombre="Suelta")

    def test_el_formulario_ofrece_solo_las_de_la_provincia_con_su_municipio(self):
        campo = NuevoCasoMesaForm().fields["localidad"]
        self.assertEqual(campo.label, "Localidad (Municipio)")
        opciones = {pk: etiqueta for pk, etiqueta in campo.choices if pk}
        self.assertEqual(opciones[self.resistencia.pk], "Resistencia (Resistencia)")
        self.assertNotIn(self.ajena.pk, opciones)
        self.assertNotIn(self.sin_municipio.pk, opciones)

    def test_el_formulario_rechaza_una_localidad_de_otra_provincia(self):
        form = NuevoCasoMesaForm(data=self._formulario1(localidad=str(self.ajena.pk)))
        self.assertFalse(form.is_valid())
        self.assertIn("localidad", form.errors)

    def test_el_servicio_tambien_la_rechaza(self):
        for pk in (self.ajena.pk, self.sin_municipio.pk):
            with self.subTest(pk=pk), self.assertRaises(ValidationError) as error:
                self._caso(localidad=pk)
            self.assertIn("localidad", error.exception.message_dict)
        self.assertEqual(self._caso(localidad=self.resistencia.pk).localidad_id, self.resistencia.pk)

    def test_una_localidad_ya_resuelta_por_el_servidor_no_se_vuelve_a_acotar(self):
        """El ingreso directo toma la del dispositivo por nombre: ese camino no pasa por el selector."""
        self.assertEqual(self._caso(localidad=self.ajena).localidad_id, self.ajena.pk)


# ---------------------------------------------------------------------------
# Hallazgo 17 · el buscador de la bandeja
# ---------------------------------------------------------------------------


class BuscadorDeLaBandejaTests(BaseMesa):
    def setUp(self):
        super().setUp()
        self.caso = self._caso(dni="30111222", nombre="Rosa", apellido="Benítez")
        self.otro = self._caso(dni="30333444", nombre="Marta", apellido="Acosta")
        for orden, (dni, nombre, apellido) in enumerate(
            (("40555666", "Lucía", "Gómez"), ("40555777", "Lucas", "Gómez")), start=1
        ):
            persona = Ciudadano.objects.create(dni=dni, nombre=nombre, apellido=apellido)
            IntegranteGrupo.objects.create(grupo=self.caso.grupo, orden=orden, ciudadano=persona)
        self.client.force_login(self.operador)

    def _numeros(self, texto):
        respuesta = self.client.get(URL_BANDEJA, {"texto": texto, "solapa": "abiertos"})
        return [fila["caso"].numero for fila in respuesta.context["filas"]]

    def test_encuentra_por_dni_de_un_integrante(self):
        self.assertEqual(self._numeros("40555666"), [self.caso.numero])
        self.assertEqual(self._numeros("40.555.777"), [self.caso.numero])

    def test_encuentra_por_nombre_o_apellido_de_un_integrante_sin_repetir_el_caso(self):
        self.assertEqual(self._numeros("Gómez"), [self.caso.numero])  # dos integrantes coinciden: una sola fila

    def test_encuentra_por_nombre_del_responsable(self):
        self.assertEqual(self._numeros("Marta"), [self.otro.numero])

    def test_parte_el_texto_en_palabras_y_todas_tienen_que_aparecer(self):
        self.assertEqual(self._numeros("Rosa Benítez"), [self.caso.numero])
        self.assertEqual(self._numeros("Benítez Rosa"), [self.caso.numero])
        self.assertEqual(self._numeros("Rosa Acosta"), [])
        self.assertEqual(self._numeros("Rosa Lucía"), [self.caso.numero])  # responsable + integrante

    def test_sin_texto_trae_todos_y_no_suma_consultas_por_palabra(self):
        self.assertEqual(len(self._numeros("")), 2)
        con_una = self._contar(lambda: self._numeros("Rosa"))
        con_cuatro = self._contar(lambda: self._numeros("Rosa Benítez Lucía Gómez"))
        self.assertEqual(con_una, con_cuatro)

    def _contar(self, accion):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as consultas:
            accion()
        return len(consultas)


# ---------------------------------------------------------------------------
# Hallazgo 21 · «Derivar» sin acentos
# ---------------------------------------------------------------------------


class BusquedaDeDerivarTests(BaseMesa):
    def setUp(self):
        super().setUp()
        self.caso = self._caso_tomado(por=self.operador)
        self.escuela = self._dispositivo("Escuela Pérez", camas=5, localidad="Resistencia")

    def _visibles(self, texto):
        """Las instituciones dentro de las tarjetas que el panel deja ver con ese texto."""
        panel = mesa.panel_de_derivar(self.caso, self.operador, texto=texto)
        return {institucion["nombre"] for tarjeta in panel["edificios"] for institucion in tarjeta["instituciones"]}

    def test_sin_texto_se_ven_las_dos(self):
        self.assertEqual(self._visibles(""), {"Club Sarmiento", "Escuela Pérez"})

    def test_la_busqueda_no_distingue_acentos_ni_mayusculas(self):
        for texto in ("perez", "PÉREZ", "Pérez", "  escuela   perez "):
            with self.subTest(texto=texto):
                self.assertEqual(self._visibles(texto), {"Escuela Pérez"})

    def test_un_texto_que_no_coincide_no_trae_nada(self):
        self.assertEqual(self._visibles("zzz"), set())


# ---------------------------------------------------------------------------
# Hallazgo 20 · solapa «Alojados»
# ---------------------------------------------------------------------------


class SolapaAlojadosTests(BaseMesa):
    def setUp(self):
        super().setUp()
        self.abierto = self._caso_tomado(por=self.operador, apellido="Abierto")
        self.completo = self._alojado(apellido="Completo", alojados=2)
        self.parcial = self._alojado(apellido="Parcial", alojados=1)
        self.client.force_login(self.operador)

    def _alojado(self, *, apellido, alojados):
        caso = self._caso(apellido=apellido)
        CasoEmergencia.objects.filter(pk=caso.pk).update(
            estado=Estado.ALOJADO,
            total_alojado=alojados,
            tomado_en=T0,
            derivado_en=T0,
            aceptado_en=T0,
            alojado_en=T0,
        )
        return caso

    def _numeros(self, solapa):
        respuesta = self.client.get(URL_BANDEJA, {"solapa": solapa})
        return {fila["caso"].numero for fila in respuesta.context["filas"]}

    def test_los_alojados_tienen_su_solapa(self):
        self.assertEqual(self._numeros("alojados"), {self.completo.numero, self.parcial.numero})

    def test_abiertos_coincide_con_caso_abierto_tambien_para_un_alojado_completo(self):
        """Un alojado sigue abierto hasta que egresa la familia: la solapa no lo esconde (Cambio 580)."""
        self.assertTrue(self.completo.abierto)
        self.assertEqual(self._numeros("abiertos"), {self.abierto.numero, self.completo.numero, self.parcial.numero})

    def test_el_chip_cuenta_y_el_conteo_cierra(self):
        respuesta = self.client.get(URL_BANDEJA)
        chips = {c["texto"]: c["n"] for c in respuesta.context["solapas"]}
        self.assertEqual(chips["Alojados"], 2)
        conteo = mesa.conteos_de_solapas(None, None, semaforos={})
        self.assertEqual((conteo["alojados"], conteo["abiertos"]), (2, 3))

    def test_un_caso_alojado_no_lleva_la_marca_de_responsable_alojado(self):
        alojado = ResponsableAlojado(1, self.club.pk, "Club Sarmiento", T0)
        caso = selectores.bandeja({"solapa": "alojados"}).get(pk=self.completo.pk)
        textos = [m["texto"] for m in mesa._marcas_de_fila(caso, None, alojado, sla_vigente(), T0)]
        self.assertNotIn("Responsable alojado en Club Sarmiento", textos)
        antes = selectores.bandeja({"solapa": "abiertos"}).get(pk=self.abierto.pk)
        textos = [m["texto"] for m in mesa._marcas_de_fila(antes, None, alojado, sla_vigente(), T0)]
        self.assertIn("Responsable alojado en Club Sarmiento", textos)


# ---------------------------------------------------------------------------
# Hallazgo 5 · derivación vencida que el cron todavía no marcó
# ---------------------------------------------------------------------------


class DerivacionVencidaSinMarcarTests(BaseMesa):
    def setUp(self):
        super().setUp()
        self.caso = self._caso_tomado(por=self.operador)
        self.derivacion = servicio.derivar_caso(self.caso, self.operador, self.club, 2)
        self.client.force_login(self.operador)

    def _marcas(self):
        fila = self.client.get(URL_BANDEJA, {"solapa": "abiertos"}).context["filas"][0]
        return [m["texto"] for m in fila["marcas"]]

    def test_dentro_del_plazo_no_se_ve_vencida(self):
        self.assertNotIn("Derivación vencida sin marcar", self._marcas())
        ficha = self._ficha(self.caso)
        self.assertFalse(ficha.context["derivacion"]["vencida"])
        self.assertContains(ficha, "Vence")
        self.assertNotContains(ficha, "Venció")

    def test_pasado_el_plazo_la_bandeja_y_la_ficha_muestran_el_estado_real(self):
        self.reloj.ahora = self.derivacion.vence_en + timedelta(minutes=1)
        self.assertIn("Derivación vencida sin marcar", self._marcas())
        ficha = self._ficha(self.caso)
        self.assertTrue(ficha.context["derivacion"]["vencida"])
        self.assertContains(ficha, "Venció")
        self.assertContains(ficha, "todavía la puede aceptar")
        # La regla vigente (RN-3.3) no cambia: sigue pendiente hasta que el proceso la marque.
        self.derivacion.refresh_from_db()
        self.assertEqual(self.derivacion.estado, Derivacion.Estado.PENDIENTE)
        self.assertEqual(self._fila(self.caso)["estado"], Estado.DERIVADO)

    def test_cuando_el_proceso_la_marca_el_aviso_pasa_a_ser_el_de_siempre(self):
        self.reloj.ahora = self.derivacion.vence_en + timedelta(minutes=1)
        vencimientos_emergencia.vencer_derivaciones(vencimientos_emergencia.derivaciones_vencidas())
        marcas = self._marcas()
        self.assertNotIn("Derivación vencida sin marcar", marcas)
        self.assertIn("Derivación vencida · volver a derivar", marcas)
