"""Emergencia, etapa 3, paso 1 (``services.emergencia_recepcion``): buscar, aceptar y rechazar.

* **RN-3.1 / 3.2** — ``buscar_por_dni``: los tres resultados y el alcance.
* **RN-3.3 / 3.4** — ``aceptar_derivacion``: vale vencida si el cron no pasó; reserva hasta lo
  pedido, parcial con aviso, 0 libres no acepta; elige las camas sola.
* **RN-3.13** — rechazo con motivo.
* **RU §6 n.° 2** y la mutación del PR («`admitir` en A no acepta una derivación de B»), vistas
  en rojo contra la regla rota; el detalle está en el docstring de cada una.
"""

from django.core.exceptions import PermissionDenied, ValidationError

from programas.models import (
    CasoEmergencia,
    Derivacion,
    EntradaBitacora,
    Estadia,
    IntegranteGrupo,
    Plaza,
    ReservaPlaza,
    Sector,
    TrazaCaso,
)
from programas.services import emergencia as mesa
from programas.services import emergencia_alojar as servicio
from programas.services.emergencia import EstadoCambio
from programas.tests.test_emergencia_alojar_base import BaseAlojar
from programas.tests.test_emergencia_casos import T0

Estado = CasoEmergencia.Estado
Accion = TrazaCaso.Accion


# ---------------------------------------------------------------------------
# Buscar (RN-3.1, RN-3.2)
# ---------------------------------------------------------------------------


class BuscarPorDniTests(BaseAlojar):
    def test_el_dni_del_responsable_encuentra_la_derivacion_de_mi_dispositivo(self):
        caso, derivacion = self._derivado()

        resultado = servicio.buscar_por_dni(dispositivo=self.club, dni="30.111.222", usuario=self.guardia)

        self.assertEqual(resultado.resultado, servicio.BUSQUEDA_DERIVACION)
        self.assertEqual(resultado.derivacion, derivacion)
        self.assertEqual(resultado.caso, caso)
        self.assertEqual(resultado.plazas_libres, 9)
        self.assertEqual(resultado.dni, "30111222")

    def test_el_dni_de_un_integrante_ya_confirmado_tambien_la_encuentra(self):
        caso, derivacion = self._aceptado()
        self._confirmar(caso, 2, "45000111")

        resultado = servicio.buscar_por_dni(dispositivo=self.club, dni="45000111", usuario=self.guardia)

        self.assertEqual(resultado.resultado, servicio.BUSQUEDA_DERIVACION)
        self.assertEqual(resultado.derivacion, derivacion)

    def test_derivada_a_otro_dispositivo_es_sin_derivacion_y_no_lo_nombra(self):
        """**Mutación RU §6 n.° 2.** La guardia de A busca a una familia derivada a B.

        Visto en rojo sacando ``dispositivo=dispositivo`` del filtro de ``buscar_por_dni``:
        el resultado pasa a ``DERIVACION`` con la derivación de la Escuela adentro, y este
        test falla en la primera afirmación.
        """

        self._derivado(dispositivo=self.escuela)

        resultado = servicio.buscar_por_dni(dispositivo=self.club, dni="30111222", usuario=self.guardia)

        self.assertEqual(resultado.resultado, servicio.BUSQUEDA_SIN_DERIVACION)
        self.assertIsNone(resultado.derivacion)
        self.assertIsNone(resultado.caso)
        self.assertNotIn("Escuela", repr(resultado))
        self.assertEqual(resultado.mensaje, servicio.SIN_DERIVACION)

    def test_sin_alcance_sobre_el_dispositivo_no_se_busca(self):
        self._derivado()
        with self.assertRaises(PermissionDenied):
            servicio.buscar_por_dni(dispositivo=self.club, dni="30111222", usuario=self.guardia_escuela)
        with self.assertRaises(PermissionDenied):
            servicio.buscar_por_dni(dispositivo=self.club, dni="30111222", usuario=self.operador)

    def test_un_dni_que_nadie_conoce_es_sin_derivacion(self):
        resultado = servicio.buscar_por_dni(dispositivo=self.club, dni="39999999", usuario=self.guardia)
        self.assertEqual(resultado.resultado, servicio.BUSQUEDA_SIN_DERIVACION)
        self.assertEqual(resultado.plazas_libres, 9)

    def test_un_dni_que_no_es_un_dni_es_un_error(self):
        with self.assertRaises(ValidationError):
            servicio.buscar_por_dni(dispositivo=self.club, dni="abc", usuario=self.guardia)

    def test_una_persona_alojada_aca_se_informa_con_el_lugar(self):
        self._ocupar(self.club, 1)
        alojada = Estadia.objects.get().ciudadano

        resultado = servicio.buscar_por_dni(dispositivo=self.club, dni=alojada.dni, usuario=self.guardia)

        self.assertEqual(resultado.resultado, servicio.BUSQUEDA_ALOJADA)
        self.assertIs(resultado.alojada_aca, True)
        self.assertEqual(resultado.alojada_en, "Club Sarmiento")
        self.assertEqual(resultado.mensaje, "Alojada en Club Sarmiento desde el 11/11.")

    def test_una_persona_alojada_en_otro_dispositivo_no_dice_donde(self):
        """RN-3.2, RU-9: quien no opera la Escuela solo se entera de que está alojada."""

        self._ocupar(self.escuela, 1)
        alojada = Estadia.objects.get().ciudadano

        resultado = servicio.buscar_por_dni(dispositivo=self.club, dni=alojada.dni, usuario=self.guardia)

        self.assertEqual(resultado.resultado, servicio.BUSQUEDA_ALOJADA)
        self.assertIs(resultado.alojada_aca, False)
        self.assertEqual(resultado.alojada_en, "")
        self.assertIsNone(resultado.alojada_desde)
        self.assertNotIn("Escuela", repr(resultado))

    def test_quien_opera_los_dos_dispositivos_si_ve_donde_esta(self):
        de_los_dos = self._guardia("guardia_doble", self.club, self.escuela)
        self._ocupar(self.escuela, 1)
        alojada = Estadia.objects.get().ciudadano

        resultado = servicio.buscar_por_dni(dispositivo=self.club, dni=alojada.dni, usuario=de_los_dos)

        self.assertIs(resultado.alojada_aca, False)
        self.assertEqual(resultado.alojada_en, "Escuela 12")

    def test_el_responsable_alojado_con_un_ingreso_en_curso_lleva_a_seguir_con_su_familia(self):
        caso, derivacion = self._aceptado()
        self._confirmar(caso, 1, "30111222", parentesco={"parentesco": "JEFE"})

        resultado = servicio.buscar_por_dni(dispositivo=self.club, dni="30111222", usuario=self.guardia)

        self.assertEqual(resultado.resultado, servicio.BUSQUEDA_DERIVACION)

    def test_una_derivacion_vencida_no_se_ofrece_y_se_explica(self):
        """RN-3.3: una ``VENCIDA`` no se acepta; RU-20: se dice qué pasó y qué hacer."""

        _caso, derivacion = self._derivado()
        self.reloj.avanzar(hours=13)
        mesa.vencer_derivacion(derivacion)

        resultado = servicio.buscar_por_dni(dispositivo=self.club, dni="30111222", usuario=self.guardia)

        self.assertEqual(resultado.resultado, servicio.BUSQUEDA_SIN_DERIVACION)
        self.assertIn("La derivación venció a las 22:00", resultado.mensaje)
        self.assertIn("ingresala igual", resultado.mensaje)


# ---------------------------------------------------------------------------
# Aceptar (RN-3.3, RN-3.4) y rechazar (RN-3.13)
# ---------------------------------------------------------------------------


class AceptarDerivacionTests(BaseAlojar):
    def test_aceptar_reserva_las_camas_y_abre_el_ingreso(self):
        """HU-3.2: 7 pedidas y 9 libres."""

        self._turno(self.club)
        caso, derivacion = self._derivado()

        resultado = servicio.aceptar_derivacion(derivacion=derivacion, usuario=self.guardia)

        fila = self._fila(caso)
        self.assertEqual(fila["estado"], Estado.INGRESO_EN_CURSO)
        self.assertEqual(fila["aceptado_en"], T0)
        derivacion.refresh_from_db()
        self.assertEqual(derivacion.estado, Derivacion.Estado.ACEPTADA)
        self.assertEqual(derivacion.respondida_por, self.guardia)
        reservas = self._reservas(derivacion)
        self.assertEqual(len(reservas), 7)
        self.assertEqual({reserva.ciudadano_id for reserva in reservas}, {caso.grupo.responsable_id})
        self.assertTrue(all(reserva.hasta is None for reserva in reservas))
        self.assertEqual((resultado.reservadas, resultado.faltantes), (7, 0))
        self.assertEqual(resultado.mensaje, "Reservé 7 de 7 camas")
        self.assertEqual([fila.orden for fila in resultado.integrantes], [1, 2, 3, 4, 5, 6, 7])
        self.assertEqual(IntegranteGrupo.objects.filter(grupo=caso.grupo, confirmada_en__isnull=True).count(), 7)
        traza = self._trazas(caso)[-1]
        self.assertEqual(traza.accion, Accion.DERIVACION_ACEPTADA)
        self.assertEqual((traza.estado_anterior, traza.estado_nuevo), (Estado.DERIVADO, Estado.INGRESO_EN_CURSO))
        self.assertEqual(traza.usuario, self.guardia)
        # RN-3.14: la novedad GENERAL automática, sin nombres de personas.
        entrada = EntradaBitacora.objects.get(dispositivo=self.club)
        self.assertEqual((entrada.tipo, entrada.origen), ("GENERAL", EntradaBitacora.Origen.AUTOMATICA))
        self.assertIn(f"caso N.° {caso.numero}", entrada.texto)
        self.assertNotIn("Benítez", entrada.texto)

    def test_con_menos_camas_que_las_pedidas_reserva_las_que_hay_y_avisa(self):
        """HU-3.2: 7 pedidas, 5 libres → «Reservé 5 de 7 · faltan 2 camas», y se puede seguir."""

        caso, derivacion = self._derivado()
        self._ocupar(self.club, 4)

        resultado = servicio.aceptar_derivacion(derivacion=derivacion, usuario=self.guardia)

        self.assertEqual((resultado.reservadas, resultado.faltantes), (5, 2))
        self.assertEqual(resultado.mensaje, "Reservé 5 de 7 · faltan 2 camas")
        self.assertEqual(len(self._reservas(derivacion)), 5)
        self.assertEqual(self._estado(caso), Estado.INGRESO_EN_CURSO)
        self.assertEqual(len(resultado.integrantes), 7, "las filas son las declaradas, no las camas")

    def test_sin_ninguna_cama_libre_no_se_acepta(self):
        caso, derivacion = self._derivado()
        self._ocupar(self.club, 9)

        with self.assertRaises(ValidationError) as error:
            servicio.aceptar_derivacion(derivacion=derivacion, usuario=self.guardia)

        self.assertEqual(error.exception.message_dict["plazas"], [servicio.SIN_PLAZAS_PARA_ACEPTAR])
        self.assertEqual(self._estado(caso), Estado.DERIVADO)
        derivacion.refresh_from_db()
        self.assertEqual(derivacion.estado, Derivacion.Estado.PENDIENTE)
        self.assertFalse(IntegranteGrupo.objects.exists())

    def test_reserva_hasta_las_plazas_pedidas_aunque_haya_mas_libres(self):
        _caso, derivacion = self._derivado(plazas=3)
        resultado = servicio.aceptar_derivacion(derivacion=derivacion, usuario=self.guardia)
        self.assertEqual((resultado.reservadas, resultado.faltantes), (3, 0))
        self.assertEqual(len(resultado.integrantes), 7)

    def test_una_pendiente_con_el_plazo_cumplido_se_acepta_si_el_cron_no_paso(self):
        """RN-3.3: la familia está en la puerta."""

        caso, derivacion = self._derivado()
        self.reloj.avanzar(hours=12, minutes=10)
        self.assertLess(derivacion.vence_en, self.reloj.ahora)

        servicio.aceptar_derivacion(derivacion=derivacion, usuario=self.guardia)

        self.assertEqual(self._estado(caso), Estado.INGRESO_EN_CURSO)

    def test_aceptar_y_vencer_se_excluyen(self):
        """Los dos bloquean caso → derivación y deciden con la fila bloqueada: gana el primero."""

        caso, derivacion = self._derivado()
        self.reloj.avanzar(hours=13)
        servicio.aceptar_derivacion(derivacion=derivacion, usuario=self.guardia)

        self.assertIsNone(mesa.vencer_derivacion(derivacion), "el cron venció una derivación aceptada")
        self.assertEqual(self._estado(caso), Estado.INGRESO_EN_CURSO)

        otro, otra = self._derivado(dni="30222333")
        self.reloj.avanzar(hours=13)
        self.assertIsNotNone(mesa.vencer_derivacion(otra))
        with self.assertRaises(EstadoCambio) as cambio:
            servicio.aceptar_derivacion(derivacion=otra, usuario=self.guardia)
        self.assertIn("La derivación venció", cambio.exception.mensaje)
        self.assertEqual(cambio.exception.estado_actual, Estado.EN_GESTION)
        self.assertFalse(ReservaPlaza.objects.filter(derivacion=otra).exists())

    def test_la_segunda_aceptacion_recibe_el_aviso_y_no_reserva_de_nuevo(self):
        caso, derivacion = self._derivado()
        servicio.aceptar_derivacion(derivacion=derivacion, usuario=self.guardia)

        with self.assertRaises(EstadoCambio) as cambio:
            servicio.aceptar_derivacion(derivacion=derivacion, usuario=self.guardia)

        self.assertIn("ya la aceptó", cambio.exception.mensaje)
        self.assertEqual(cambio.exception.estado_actual, Estado.INGRESO_EN_CURSO)
        self.assertEqual(len(self._reservas(derivacion)), 7)
        self.assertEqual(IntegranteGrupo.objects.filter(grupo=caso.grupo).count(), 7)

    def test_una_derivacion_cancelada_por_la_mesa_no_se_acepta(self):
        _caso, derivacion = self._derivado()
        mesa.cancelar_derivacion(derivacion, self.operador, "Error de carga")
        with self.assertRaises(EstadoCambio) as cambio:
            servicio.aceptar_derivacion(derivacion=derivacion, usuario=self.guardia)
        self.assertIn("canceló", cambio.exception.mensaje)

    def test_elige_el_sector_con_mas_camas_libres_y_por_codigo_natural(self):
        """RN-3.4: la familia queda junta; `B-9` va antes que `B-10`."""

        ala = Sector.objects.create(dispositivo=self.escuela, nombre="Ala B", capacidad=12)
        Plaza.objects.bulk_create([Plaza(sector=ala, codigo=f"B-{n}") for n in range(1, 13)])
        _caso, derivacion = self._derivado(dispositivo=self.escuela, plazas=7)

        servicio.aceptar_derivacion(derivacion=derivacion, usuario=self.guardia_escuela)

        codigos = [(r.plaza.sector.nombre, r.plaza.codigo) for r in self._reservas(derivacion)]
        self.assertEqual({sector for sector, _codigo in codigos}, {"Ala B"})
        self.assertEqual(sorted(codigo for _s, codigo in codigos), sorted(f"B-{n}" for n in range(1, 8)))

    def test_sin_turno_no_hay_novedad_de_bitacora_y_no_es_un_error(self):
        """Plan R8: es el comportamiento de Dispositivos. La traza del caso queda igual."""

        caso, derivacion = self._derivado()
        servicio.aceptar_derivacion(derivacion=derivacion, usuario=self.guardia)

        self.assertFalse(EntradaBitacora.objects.exists())
        self.assertEqual(self._trazas(caso)[-1].accion, Accion.DERIVACION_ACEPTADA)

    def test_quien_admite_en_otro_dispositivo_no_acepta_esta_derivacion(self):
        """**Mutación nueva del PR 7:** `admitir` en A no acepta una derivación de B aunque conozca el id.

        Visto en rojo sacando ``_exigir_alcance`` de ``_dispositivo_de``: ``rechazar_derivacion``
        —que no pasa por ``estadias``— deja que la guardia de la Escuela rechace la derivación
        del Club y este test falla en el segundo ``assertRaises`` («PermissionDenied not
        raised»). A ``aceptar_derivacion`` la sigue frenando, ya con los candados tomados, la
        guarda de ``reservar_plazas_de_derivacion`` (PR 6): son dos guardas y esta es la primera.
        """

        caso, derivacion = self._derivado()

        with self.assertRaises(PermissionDenied):
            servicio.aceptar_derivacion(derivacion=derivacion, usuario=self.guardia_escuela)
        with self.assertRaises(PermissionDenied):
            servicio.rechazar_derivacion(derivacion=derivacion, usuario=self.guardia_escuela, motivo="SIN_PLAZAS")

        derivacion.refresh_from_db()
        self.assertEqual(derivacion.estado, Derivacion.Estado.PENDIENTE)
        self.assertEqual(self._estado(caso), Estado.DERIVADO)
        self.assertFalse(ReservaPlaza.objects.exists())
        self.assertEqual(len(self._trazas(caso)), 3, "quedó una traza de algo que no pasó")

    def test_la_mesa_no_acepta_derivaciones(self):
        _caso, derivacion = self._derivado()
        with self.assertRaises(PermissionDenied):
            servicio.aceptar_derivacion(derivacion=derivacion, usuario=self.supervisor)


class RechazarDerivacionTests(BaseAlojar):
    def test_rechazar_devuelve_el_caso_a_quien_lo_tenia(self):
        caso, derivacion = self._derivado()

        rechazada = servicio.rechazar_derivacion(derivacion=derivacion, usuario=self.guardia, motivo="SIN_PLAZAS")

        fila = self._fila(caso)
        self.assertEqual(fila["estado"], Estado.EN_GESTION)
        self.assertEqual(fila["tomado_por_id"], self.operador.pk)
        self.assertEqual(rechazada.estado, Derivacion.Estado.RECHAZADA)
        self.assertEqual(rechazada.motivo, "Sin plazas")
        self.assertIsNone(rechazada.clave_vigente)
        traza = self._trazas(caso)[-1]
        self.assertEqual(traza.accion, Accion.DERIVACION_RECHAZADA)
        self.assertEqual(traza.detalle, "Rechazado por Club Sarmiento: sin plazas")
        # El caso se puede volver a derivar.
        mesa.derivar_caso(CasoEmergencia.objects.get(pk=caso.pk), self.operador, self.escuela, 5, True)

    def test_el_motivo_es_del_catalogo_y_otro_pide_observacion(self):
        _caso, derivacion = self._derivado()
        for motivo, observacion, campo in (
            ("", "", "motivo"),
            ("PORQUE_SI", "", "motivo"),
            ("OTRO", " ", "observacion"),
        ):
            with self.subTest(motivo=motivo), self.assertRaises(ValidationError) as error:
                servicio.rechazar_derivacion(
                    derivacion=derivacion, usuario=self.guardia, motivo=motivo, observacion=observacion
                )
            self.assertEqual(set(error.exception.error_dict), {campo})

        rechazada = servicio.rechazar_derivacion(
            derivacion=derivacion, usuario=self.guardia, motivo="OTRO", observacion="El edificio está sin luz"
        )
        self.assertEqual(rechazada.observacion, "El edificio está sin luz")

    def test_una_derivacion_ya_aceptada_no_se_rechaza(self):
        _caso, derivacion = self._aceptado()
        with self.assertRaises(EstadoCambio):
            servicio.rechazar_derivacion(derivacion=derivacion, usuario=self.guardia, motivo="NO_LLEGO")
        self.assertEqual(len(self._reservas(derivacion)), 7)
