"""Emergencia, etapa 3, paso 2 (``services.emergencia_confirmacion``): confirmar, completar y agregar.

* **RN-3.5 a 3.7** — ``confirmar_integrante``: consume la reserva por la vía del PR 6, valida
  el mínimo y es atómica (si el ingreso falla no queda nada huérfano). En una cama libre
  devuelve la reserva sobrante y cierra las reservas comunes de la persona (D2 del Cambio
  409); una reserva común suya en la cama elegida se consume.
* **RN-3.8** — agregar una persona; completar la ficha después.
* **Bordes de 03 §10.**
"""

import uuid
from datetime import date, timedelta
from unittest import mock

from django.core.exceptions import PermissionDenied, ValidationError

from core.tests.candados import orden_de_candados
from legajos.models import Ciudadano
from legajos.models.contactos import TipoVinculo, VinculoFamiliar
from programas.models import (
    CasoEmergencia,
    EntradaBitacora,
    Estadia,
    IntegranteGrupo,
    Plaza,
    ReservaPlaza,
    TrazaCaso,
)
from programas.selectors import emergencia_alojar as selectores
from programas.services import emergencia_alojar as servicio
from programas.services import emergencia_confirmacion as servicio_confirmacion
from programas.services import ingreso as servicio_ingreso
from programas.services.emergencia import EstadoCambio
from programas.services.estadias import egresar_persona, liberar_reserva, reservar_plaza
from programas.services.ingreso import MOTIVO_RESERVA_CERRADA_POR_INGRESO, RESERVA_NUEVA_DURANTE_EL_INGRESO
from programas.tests.test_emergencia_alojar_base import BaseAlojar, ficha_minima
from programas.tests.test_emergencia_casos import T0

Estado = CasoEmergencia.Estado
Accion = TrazaCaso.Accion


# ---------------------------------------------------------------------------
# Confirmar a una persona (RN-3.5 a 3.7)
# ---------------------------------------------------------------------------


class ConfirmarIntegranteTests(BaseAlojar):
    def test_confirmar_a_otra_persona_consume_la_reserva_del_responsable(self):
        """RN-3.5, por la vía del PR 6: la reserva nació a nombre del responsable."""

        self._turno(self.club)
        caso, derivacion = self._aceptado()
        reserva = self._reservas(derivacion)[0]

        integrante = self._confirmar(caso, 2, "45000111", plaza=reserva.plaza)

        juan = Ciudadano.objects.get(dni="45000111")
        estadia = Estadia.objects.get(ciudadano=juan)
        self.assertTrue(estadia.activa)
        self.assertEqual((estadia.dispositivo, estadia.plaza), (self.club, reserva.plaza))
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, ReservaPlaza.Estado.CONSUMIDA)
        self.assertEqual(reserva.ciudadano, juan)
        self.assertEqual(len(self._reservas(derivacion)), 6)
        integrante.refresh_from_db()
        self.assertEqual((integrante.ciudadano, integrante.estadia), (juan, estadia))
        self.assertEqual(integrante.confirmada_en, T0)
        self.assertEqual(integrante.parentesco, "HIJO")
        self.assertFalse(integrante.ficha_completa)
        self.assertEqual(integrante.ficha["version"], 1)
        self.assertEqual(integrante.ficha["datos_personales"]["dni"], "45000111")
        # El vínculo, visto desde el responsable.
        vinculo = VinculoFamiliar.objects.get()
        self.assertEqual(
            (vinculo.ciudadano_principal_id, vinculo.ciudadano_vinculado, vinculo.tipo_vinculo),
            (caso.grupo.responsable_id, juan, TipoVinculo.HIJO),
        )
        self.assertTrue(vinculo.convive)
        # HU-3.3: el INGRESO automático de la bitácora lo deja `ingresar_persona`.
        self.assertTrue(
            EntradaBitacora.objects.filter(
                dispositivo=self.club, tipo="INGRESO", origen=EntradaBitacora.Origen.AUTOMATICA
            ).exists()
        )
        traza = self._trazas(caso)[-1]
        self.assertEqual(traza.accion, Accion.INTEGRANTE_CONFIRMADO)
        self.assertIn("1 de 7", traza.detalle)
        self.assertNotIn("Pérez", traza.detalle, "la traza nombra a la familia")
        self.assertEqual((integrante.confirmadas, integrante.total_declarado), (1, 7))

    def test_confirmar_al_responsable_no_crea_vinculo_y_completa_su_legajo(self):
        """El responsable se dio de alta en la etapa 1 sin sexo: lo completa esta ficha."""

        caso, derivacion = self._aceptado()
        responsable = caso.grupo.responsable
        self.assertEqual(responsable.genero, "")

        # Sin nombre ni apellido en la ficha: con la persona en el legajo, el DNI alcanza.
        ficha = ficha_minima("30111222", parentesco={"parentesco": "JEFE"}, datos_personales={"sexo": "F"})
        del ficha["datos_personales"]["nombre"], ficha["datos_personales"]["apellido"]
        integrante = servicio.confirmar_integrante(
            caso=caso, orden=1, usuario=self.guardia, ficha=ficha, plaza=self._reservas(derivacion)[0].plaza
        )

        self.assertEqual(integrante.ciudadano, responsable)
        self.assertFalse(VinculoFamiliar.objects.exists())
        responsable.refresh_from_db()
        self.assertEqual(responsable.genero, "F")
        self.assertEqual(responsable.fecha_nacimiento, date(2006, 3, 10))
        self.assertEqual((responsable.nombre, responsable.apellido), ("Rosa", "Benítez"), "pisó el legajo")
        self.assertEqual(integrante.ficha["datos_personales"]["nombre"], "Rosa")
        self.assertEqual(Ciudadano.objects.filter(dni="30111222").count(), 1)

    def test_sin_el_minimo_no_se_crea_nada(self):
        """HU-3.3: «Falta: avisos de salud» y no queda ni la persona."""

        caso, derivacion = self._aceptado()
        ficha = ficha_minima("45000111")
        del ficha["avisos_salud"]
        personas = Ciudadano.objects.count()

        with self.assertRaises(ValidationError) as error:
            servicio.confirmar_integrante(
                caso=caso, orden=2, usuario=self.guardia, ficha=ficha, plaza=self._reservas(derivacion)[0].plaza
            )

        self.assertIn("Falta: avisos de salud", error.exception.message_dict["embarazo"][0])
        self.assertEqual(Ciudadano.objects.count(), personas)
        self.assertFalse(Estadia.objects.exists())
        self.assertEqual(len(self._reservas(derivacion)), 7)
        self.assertFalse(IntegranteGrupo.objects.filter(confirmada_en__isnull=False).exists())

    def test_un_menor_sin_adulto_responsable_no_se_confirma(self):
        caso, _derivacion = self._aceptado()
        with self.assertRaises(ValidationError) as error:
            self._confirmar(caso, 3, "55000111", datos_personales={"fecha_nacimiento": "2015-05-05"})
        self.assertEqual(set(error.exception.error_dict), {"adulto_responsable"})

        integrante = self._confirmar(
            caso,
            3,
            "55000111",
            datos_personales={"fecha_nacimiento": "2015-05-05"},
            observaciones={"adulto_responsable": "Rosa Benítez"},
        )
        self.assertTrue(integrante.confirmada)

    def test_quien_no_sabe_su_numero_de_dni_no_se_confirma_con_cama(self):
        caso, _derivacion = self._aceptado()
        with self.assertRaises(ValidationError) as error:
            self._confirmar(caso, 2, "")
        self.assertEqual(error.exception.message_dict["dni"], [servicio.SIN_NUMERO_DE_DOCUMENTO])
        self.assertFalse(Estadia.objects.exists())

    def test_perdio_el_documento_pero_sabe_el_numero_queda_marcado_solo_en_el_alta(self):
        """Hallazgo H5: ``dni_fisico = NO_TIENE`` en quien se da de alta acá; al legajo previo no se le toca."""

        caso, derivacion = self._aceptado()
        reservas = self._reservas(derivacion)
        self._confirmar(caso, 2, "45000111", plaza=reservas[0].plaza, datos_personales={"documento_extraviado": True})
        previa = Ciudadano.objects.create(dni="45000222", nombre="Lía", apellido="Sosa", dni_fisico="TIENE")
        self._confirmar(caso, 3, "45000222", plaza=reservas[1].plaza, datos_personales={"documento_extraviado": True})

        self.assertEqual(Ciudadano.objects.get(dni="45000111").dni_fisico, Ciudadano.DniFisico.NO_TIENE)
        previa.refresh_from_db()
        self.assertEqual(previa.dni_fisico, "TIENE")

    def test_si_el_ingreso_falla_no_queda_nada_huerfano(self):
        """**RN-3.7, atomicidad.** Ni legajo, ni vínculo, ni fila confirmada, y la reserva como estaba."""

        caso, derivacion = self._aceptado()
        reserva = self._reservas(derivacion)[0]
        personas, trazas = Ciudadano.objects.count(), len(self._trazas(caso))

        with mock.patch(
            "programas.services.reservas_derivacion.ingresar_persona",
            side_effect=ValidationError({"fecha_ingreso": "El ingreso no puede ser futuro."}),
        ):
            with self.assertRaises(ValidationError):
                self._confirmar(caso, 2, "45000111", plaza=reserva.plaza)

        self.assertEqual(Ciudadano.objects.count(), personas, "quedó un legajo huérfano")
        self.assertFalse(Ciudadano.objects.filter(dni="45000111").exists())
        self.assertFalse(VinculoFamiliar.objects.exists())
        self.assertFalse(Estadia.objects.exists())
        self.assertFalse(IntegranteGrupo.objects.filter(confirmada_en__isnull=False).exists())
        self.assertFalse(IntegranteGrupo.objects.filter(ciudadano__isnull=False).exists())
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, ReservaPlaza.Estado.VIGENTE)
        self.assertEqual(reserva.ciudadano_id, caso.grupo.responsable_id, "la reserva quedó a nombre de quien no entró")
        self.assertEqual(len(self._trazas(caso)), trazas)

    def test_si_falla_despues_del_ingreso_tampoco_queda_la_estadia(self):
        """El otro lado de la atomicidad: lo que se deshace incluye el ingreso ya hecho."""

        caso, derivacion = self._aceptado()
        with mock.patch.object(
            servicio_confirmacion, "_vincular_con_el_responsable", side_effect=RuntimeError("se cayó")
        ):
            with self.assertRaises(RuntimeError):
                self._confirmar(caso, 2, "45000111")

        self.assertFalse(Estadia.objects.exists())
        self.assertFalse(Ciudadano.objects.filter(dni="45000111").exists())
        self.assertEqual(len(self._reservas(derivacion)), 7)

    def test_una_persona_alojada_en_otro_dispositivo_no_se_confirma_y_no_se_dice_donde(self):
        """HU-3.3, RU-9: la guardia del Club no opera la Escuela."""

        caso, derivacion = self._aceptado()
        self._ocupar(self.escuela, 1)
        alojada = Estadia.objects.get().ciudadano

        with self.assertRaises(servicio.PersonaYaAlojada) as error:
            self._confirmar(caso, 2, alojada.dni)

        mensaje = error.exception.message_dict["dni"][0]
        self.assertIn("figura alojado en otro dispositivo de la red", mensaje)
        self.assertIn("cerrá el ingreso con diferencia", mensaje)
        self.assertNotIn("Escuela", mensaje)
        self.assertEqual(len(self._reservas(derivacion)), 7)
        self.assertFalse(IntegranteGrupo.objects.filter(confirmada_en__isnull=False).exists())

    def test_quien_opera_el_otro_dispositivo_si_lee_donde_esta(self):
        de_los_dos = self._guardia("guardia_doble", self.club, self.escuela)
        caso, _derivacion = self._aceptado()
        self._ocupar(self.escuela, 1)
        alojada = Estadia.objects.get().ciudadano

        with self.assertRaises(servicio.PersonaYaAlojada) as error:
            self._confirmar(caso, 2, alojada.dni, usuario=de_los_dos)

        self.assertIn("figura alojado en Escuela 12 desde el 11/11", error.exception.message_dict["dni"][0])

    def test_el_mismo_dni_dos_veces_en_la_familia_dice_donde_esta(self):
        """03 §10: «Ya confirmaste a Juan Pérez en la cama B-12»."""

        caso, derivacion = self._aceptado()
        reservas = self._reservas(derivacion)
        self._confirmar(caso, 2, "45000111", plaza=reservas[0].plaza)

        with self.assertRaises(ValidationError) as error:
            self._confirmar(caso, 3, "45.000.111", plaza=reservas[1].plaza)

        self.assertEqual(
            error.exception.message_dict["dni"],
            [f"Ya confirmaste a Juan Pérez en la cama {reservas[0].plaza.codigo} (General)."],
        )
        self.assertEqual(Estadia.objects.count(), 1)

    def test_una_cama_libre_sin_reserva_devuelve_una_de_las_guardadas(self):
        """La regla de la reserva sobrante: la derivación no retiene más camas que personas faltan.

        7 declaradas y 7 reservadas: quien entra en una cama libre devuelve **una** reserva
        —la de la plaza con id más alto—, y quedan 6 para las 6 personas que faltan.
        """

        caso, derivacion = self._aceptado()
        reservadas = [reserva.plaza_id for reserva in self._reservas(derivacion)]
        libre = self._cama_libre()
        self.assertNotIn(libre.pk, reservadas)

        integrante = self._confirmar(caso, 2, "45000111", plaza=libre)

        self.assertEqual(integrante.estadia.plaza, libre)
        self.assertTrue(integrante.reserva_liberada)
        vigentes = [reserva.plaza_id for reserva in self._reservas(derivacion)]
        self.assertEqual(vigentes, reservadas[:-1])
        liberada = ReservaPlaza.objects.get(derivacion=derivacion, estado=ReservaPlaza.Estado.LIBERADA)
        self.assertEqual(liberada.plaza_id, max(reservadas))
        self.assertEqual(liberada.motivo, servicio.MOTIVO_RESERVA_SOBRANTE)

    def test_si_todavia_hacen_falta_todas_las_reservas_no_se_libera_ninguna(self):
        """Reservó 5 de 7: una persona en una cama que se liberó después no devuelve nada."""

        caso, derivacion = self._derivado()
        self._ocupar(self.club, 4)
        servicio.aceptar_derivacion(derivacion=derivacion, usuario=self.guardia)
        ocupada = Estadia.objects.filter(dispositivo=self.club).first()
        egresar_persona(estadia=ocupada, usuario=self.guardia, motivo_egreso=self.motivo_alta, destino="Domicilio")

        integrante = self._confirmar(caso, 2, "45000111", plaza=ocupada.plaza)

        self.assertFalse(integrante.reserva_liberada)
        self.assertEqual(len(self._reservas(derivacion)), 5)

    def test_una_cama_reservada_para_otra_familia_no_se_puede_elegir(self):
        caso, _derivacion = self._aceptado(plazas=4)
        _otro, otra = self._derivado(dni="30222333", plazas=2)
        servicio.aceptar_derivacion(derivacion=otra, usuario=self.guardia)
        ajena = self._reservas(otra)[0].plaza

        with self.assertRaises(ValidationError) as error:
            self._confirmar(caso, 2, "45000111", plaza=ajena)

        self.assertIn("está reservada para otra persona · elegí otra", error.exception.message_dict["plaza"][0])
        self.assertFalse(Ciudadano.objects.filter(dni="45000111").exists())

    def _con_reserva_comun(self, dni, plaza, usuario):
        """Una persona con legajo y una reserva **común** (no de derivación) abierta en ``plaza``."""

        persona = Ciudadano.objects.create(dni=dni, nombre="Juan", apellido="Pérez")
        return persona, reservar_plaza(plaza=plaza, ciudadano=persona, usuario=usuario)

    def test_en_una_cama_libre_se_cierra_su_reserva_comun_de_otro_dispositivo(self):
        """D2 del Cambio 409: quien entra en una cama libre no sigue bloqueando la que tenía en otro lado.

        Visto en rojo: sin leer ``_reservas_abiertas_de`` en la rama de la cama libre, la
        persona quedaba alojada en el Club y su reserva de la Escuela seguía ``VIGENTE``.
        """

        caso, _derivacion = self._aceptado()
        escuela = Plaza.objects.filter(sector__dispositivo=self.escuela).order_by("pk").first()
        _persona, comun = self._con_reserva_comun("45000111", escuela, self.guardia_escuela)
        libre = self._cama_libre()

        integrante = self._confirmar(caso, 2, "45000111", plaza=libre)

        self.assertEqual(integrante.estadia.plaza, libre)
        comun.refresh_from_db()
        self.assertEqual(comun.estado, ReservaPlaza.Estado.LIBERADA, "la D2 del Cambio 409 no se aplicó")
        self.assertEqual(comun.motivo, MOTIVO_RESERVA_CERRADA_POR_INGRESO)

    def test_su_reserva_comun_en_la_cama_elegida_se_consume(self):
        """Una cama guardada para **la misma persona** no es «de otra persona»: el ingreso la consume.

        Visto en rojo: se rechazaba con «está reservada para otra persona».
        """

        caso, _derivacion = self._aceptado()
        libre = self._cama_libre()
        _persona, comun = self._con_reserva_comun("45000111", libre, self.guardia)

        integrante = self._confirmar(caso, 2, "45000111", plaza=libre)

        self.assertEqual(integrante.estadia.plaza, libre)
        comun.refresh_from_db()
        self.assertEqual(comun.estado, ReservaPlaza.Estado.CONSUMIDA)

    def test_una_reserva_comun_nueva_mientras_se_confirma_frena_el_ingreso(self):
        """Con la persona bloqueada se vuelve a mirar: una reserva que apareció en el medio frena."""

        caso, _derivacion = self._aceptado()
        Ciudadano.objects.create(dni="45000111", nombre="Juan", apellido="Pérez")
        escuela = Plaza.objects.filter(sector__dispositivo=self.escuela).order_by("pk").first()
        original = servicio_ingreso._bloquear_persona

        def bloquear_y_que_aparezca(ciudadano):
            original(ciudadano)
            reservar_plaza(plaza=escuela, ciudadano=ciudadano, usuario=self.guardia_escuela)

        with mock.patch.object(servicio_confirmacion, "_bloquear_persona", side_effect=bloquear_y_que_aparezca):
            with self.assertRaises(ValidationError) as error:
                self._confirmar(caso, 2, "45000111", plaza=self._cama_libre())

        self.assertEqual(error.exception.messages, [RESERVA_NUEVA_DURANTE_EL_INGRESO])
        self.assertFalse(Estadia.objects.exists())

    def test_una_cama_ocupada_se_rechaza_sin_pedir_su_candado(self):
        """Es lo que impide el ciclo con un egreso en curso (docstring del módulo)."""

        caso, _derivacion = self._aceptado(plazas=4)
        self._ocupar(self.club, 9)  # ocupa también las que no tienen reserva: `_ocupar` no mira
        ocupada = Estadia.objects.filter(dispositivo=self.club).order_by("-plaza_id").first().plaza

        with orden_de_candados(plaza=Plaza.objects, persona=Ciudadano.objects) as orden:
            with self.assertRaises(ValidationError) as error:
                self._confirmar(caso, 2, "45000111", plaza=ocupada)

        self.assertIn("ya está ocupada · elegí otra", error.exception.message_dict["plaza"][0])
        self.assertEqual(orden, [], "pidió un candado antes de rechazar la cama ocupada")

    def test_la_cama_reservada_que_quedo_fuera_de_servicio_se_rechaza_y_se_elige_otra(self):
        """03 §10: «La cama B-12 está fuera de servicio · elegí otra»."""

        caso, derivacion = self._aceptado()
        reservas = self._reservas(derivacion)
        rota = reservas[0].plaza
        # Para sacarla de servicio hay que soltarla primero (regla 1 de `estadias`): así llega a este estado.
        liberar_reserva(reserva=reservas[0], usuario=self.guardia, motivo="Se rompió el elástico")
        Plaza.objects.filter(pk=rota.pk).update(estado=Plaza.Estado.FUERA_SERVICIO, motivo_fuera_servicio="Rota")

        with self.assertRaises(ValidationError) as error:
            self._confirmar(caso, 2, "45000111", plaza=rota)
        self.assertEqual(
            error.exception.message_dict["plaza"],
            [f"La cama {rota.codigo} (General) está fuera de servicio · elegí otra."],
        )
        self.assertFalse(Ciudadano.objects.filter(dni="45000111").exists())

        integrante = self._confirmar(caso, 2, "45000111", plaza=reservas[1].plaza)
        self.assertTrue(integrante.confirmada)

    def test_una_cama_de_otro_dispositivo_o_inexistente_da_el_mismo_error(self):
        caso, _derivacion = self._aceptado()
        ajena = Plaza.objects.filter(sector__dispositivo=self.escuela).first()
        for plaza in (ajena, ajena.pk, 999_999, "abc"):
            with self.subTest(plaza=plaza), self.assertRaises(ValidationError) as error:
                self._confirmar(caso, 2, "45000111", plaza=plaza)
            self.assertEqual(error.exception.message_dict["plaza"], [servicio.ELEGI_UNA_CAMA])

    def test_una_fila_ya_confirmada_no_se_confirma_de_nuevo(self):
        """03 §10: dos guardias confirman a la misma persona; la segunda recarga (409)."""

        caso, derivacion = self._aceptado()
        reservas = self._reservas(derivacion)
        self._confirmar(caso, 2, "45000111", plaza=reservas[0].plaza)

        with self.assertRaises(EstadoCambio) as cambio:
            self._confirmar(caso, 2, "45000111", plaza=reservas[1].plaza)

        self.assertEqual(cambio.exception.estado_actual, Estado.INGRESO_EN_CURSO)
        self.assertEqual(Estadia.objects.count(), 1)
        self.assertEqual(len(self._reservas(derivacion)), 6)

    def test_reenviar_la_misma_confirmacion_devuelve_la_misma_fila(self):
        """RU-16: el mismo ``uuid_cliente`` no duplica ni falla."""

        caso, derivacion = self._aceptado()
        envio = uuid.uuid4()
        argumentos = {
            "caso": caso,
            "orden": 2,
            "usuario": self.guardia,
            "ficha": ficha_minima("45000111"),
            "plaza": self._reservas(derivacion)[0].plaza,
            "uuid_cliente": envio,
        }
        primera = servicio.confirmar_integrante(**argumentos)
        segunda = servicio.confirmar_integrante(**argumentos)

        self.assertFalse(primera.ya_estaba)
        self.assertTrue(segunda.ya_estaba)
        self.assertEqual(primera.pk, segunda.pk)
        self.assertEqual(Estadia.objects.count(), 1)

    def test_una_fila_que_no_es_de_la_familia_es_un_error(self):
        caso, _derivacion = self._aceptado()
        with self.assertRaises(ValidationError) as error:
            self._confirmar(caso, 99, "45000111")
        self.assertEqual(set(error.exception.error_dict), {"orden"})

    def test_sin_alcance_sobre_el_dispositivo_del_caso_no_se_confirma(self):
        caso, derivacion = self._aceptado()
        for usuario in (self.guardia_escuela, self.operador, self.supervisor):
            with self.subTest(usuario=usuario.username), self.assertRaises(PermissionDenied):
                self._confirmar(caso, 2, "45000111", usuario=usuario)
        self.assertFalse(Estadia.objects.exists())
        self.assertFalse(Ciudadano.objects.filter(dni="45000111").exists())

    def test_un_caso_que_todavia_no_se_acepto_no_admite_confirmaciones(self):
        caso, _derivacion = self._derivado()
        with self.assertRaises(EstadoCambio):
            servicio.confirmar_integrante(
                caso=caso, orden=1, usuario=self.guardia, ficha=ficha_minima("45000111"), plaza=self._cama_libre()
            )

    def test_un_caso_sin_ninguna_derivacion_no_dice_que_existe(self):
        caso = self._caso_tomado()
        with self.assertRaises(PermissionDenied):
            servicio.confirmar_integrante(
                caso=caso, orden=1, usuario=self.guardia, ficha=ficha_minima("45000111"), plaza=self._cama_libre()
            )


class CompletarFichaTests(BaseAlojar):
    def test_completar_las_secciones_que_faltan_deja_la_ficha_completa(self):
        caso, _derivacion = self._aceptado()
        self._confirmar(caso, 2, "45000111")

        parcial = servicio.completar_ficha(
            caso=caso, orden=2, usuario=self.guardia, ficha={"educacion": {"nivel_educativo": "SECUNDARIO"}}
        )
        self.assertFalse(parcial.ficha_completa)

        completa = servicio.completar_ficha(
            caso=caso,
            orden=2,
            usuario=self.guardia,
            ficha={
                "vacunacion": {"esquema_al_dia": True},
                "salud": {"sin_datos": True},
                "trabajo": {"ocupacion": "Estudiante"},
                "observaciones": {"mascotas": False},
                # La identidad no se cambia después de confirmar: esto se ignora.
                "datos_personales": {"dni": "11111111", "nombre": "Otro"},
            },
        )

        completa.refresh_from_db()
        self.assertTrue(completa.ficha_completa)
        self.assertEqual(completa.ficha["educacion"], {"nivel_educativo": "SECUNDARIO"})
        self.assertEqual(completa.ficha["datos_personales"]["dni"], "45000111")
        self.assertEqual(self._trazas(caso)[-1].accion, Accion.FICHA_ACTUALIZADA)

    def test_tambien_con_la_familia_ya_alojada(self):
        caso, _derivacion = self._aceptado(menores_f=0, menores_m=0, adultos_m=0)
        self._confirmar(caso, 1, "30111222", parentesco={"parentesco": "JEFE"})
        servicio.alojar_familia(caso=caso, usuario=self.guardia)

        integrante = servicio.completar_ficha(
            caso=caso, orden=1, usuario=self.guardia, ficha={"trabajo": {"sin_datos": True}}
        )
        self.assertEqual(integrante.ficha["trabajo"], {"sin_datos": True})

    def test_una_persona_sin_confirmar_no_tiene_ficha_que_completar(self):
        caso, _derivacion = self._aceptado()
        with self.assertRaises(ValidationError):
            servicio.completar_ficha(caso=caso, orden=2, usuario=self.guardia, ficha={"trabajo": {"sin_datos": True}})

    def test_a_un_menor_no_se_le_puede_borrar_el_adulto_responsable(self):
        caso, _derivacion = self._aceptado()
        self._confirmar(
            caso,
            3,
            "55000111",
            datos_personales={"fecha_nacimiento": "2015-05-05"},
            observaciones={"adulto_responsable": "Rosa Benítez"},
        )
        with self.assertRaises(ValidationError) as error:
            servicio.completar_ficha(
                caso=caso, orden=3, usuario=self.guardia, ficha={"observaciones": {"mascotas": True}}
            )
        self.assertEqual(set(error.exception.error_dict), {"adulto_responsable"})

    def test_sin_alcance_no_se_completa(self):
        caso, _derivacion = self._aceptado()
        self._confirmar(caso, 2, "45000111")
        with self.assertRaises(PermissionDenied):
            servicio.completar_ficha(
                caso=caso, orden=2, usuario=self.guardia_escuela, ficha={"trabajo": {"sin_datos": True}}
            )


# ---------------------------------------------------------------------------
# Agregar (RN-3.8)
# ---------------------------------------------------------------------------


class AgregarIntegranteTests(BaseAlojar):
    def test_agregar_suma_una_fila_y_la_cama_sale_de_las_libres(self):
        """HU-3.5: 7 declaradas → 8; la persona nueva no tiene reserva."""

        caso, derivacion = self._aceptado()

        nuevo = servicio.agregar_integrante(caso=caso, usuario=self.guardia)

        self.assertEqual((nuevo.orden, nuevo.total_declarado), (8, 8))
        caso.grupo.refresh_from_db()
        self.assertEqual(caso.grupo.total_declarado, 8)
        self.assertEqual(caso.grupo.suma_de_cantidades(), 7, "lo declarado al relevar no se toca")
        self.assertEqual(len(self._reservas(derivacion)), 7)
        self.assertEqual(self._trazas(caso)[-1].detalle, "Agregada persona por el dispositivo · 8 sobre 7 declaradas")
        # Las 8 personas entran: 7 por su reserva y la octava por una cama libre, sin devolver ninguna.
        reservas = self._reservas(derivacion)
        for orden, reserva in enumerate(reservas, start=1):
            self._confirmar(caso, orden, str(45_000_100 + orden), plaza=reserva.plaza)
        octava = self._confirmar(caso, 8, "45000999", plaza=self._cama_libre())
        self.assertFalse(octava.reserva_liberada)
        self.assertEqual((octava.confirmadas, octava.total_declarado), (8, 8))

    def test_sin_cama_libre_la_fila_existe_pero_confirmar_avisa(self):
        """HU-3.5: «Sin cama libre · liberá una o cerrá con diferencia»."""

        caso, derivacion = self._aceptado()
        for orden, reserva in enumerate(self._reservas(derivacion), start=1):
            self._confirmar(caso, orden, str(45_000_100 + orden), plaza=reserva.plaza)
        self._ocupar_libres(self.club)
        servicio.agregar_integrante(caso=caso, usuario=self.guardia)

        with self.assertRaises(ValidationError) as error:
            servicio.confirmar_integrante(
                caso=caso, orden=8, usuario=self.guardia, ficha=ficha_minima("45000999"), plaza=None
            )

        self.assertEqual(error.exception.message_dict["plaza"], [servicio.SIN_CAMA_LIBRE])

    def _ocupar_libres(self, dispositivo):
        for plaza in selectores.camas_libres(dispositivo):
            persona = Ciudadano.objects.create(dni=str(next(self._dnis)), nombre="Persona", apellido="Alojada")
            Estadia.objects.create(
                ciudadano=persona,
                dispositivo=dispositivo,
                plaza=plaza,
                fecha_ingreso=T0 - timedelta(days=1),
                clave_alojamiento=Estadia.clave_para(persona),
            )

    def test_reenviar_el_mismo_alta_no_suma_dos_personas(self):
        caso, _derivacion = self._aceptado()
        envio = uuid.uuid4()

        primera = servicio.agregar_integrante(caso=caso, usuario=self.guardia, uuid_cliente=envio)
        self._confirmar(caso, 8, "45000999", plaza=self._cama_libre())
        segunda = servicio.agregar_integrante(caso=caso, usuario=self.guardia, uuid_cliente=envio)

        self.assertEqual(primera.pk, segunda.pk)
        self.assertTrue(segunda.ya_estaba)
        self.assertEqual(IntegranteGrupo.objects.filter(grupo=caso.grupo).count(), 8)

    def test_solo_con_el_ingreso_en_curso_y_con_alcance(self):
        caso, _derivacion = self._derivado()
        with self.assertRaises(EstadoCambio):
            servicio.agregar_integrante(caso=caso, usuario=self.guardia)
        with self.assertRaises(PermissionDenied):
            servicio.agregar_integrante(caso=caso, usuario=self.guardia_escuela)
