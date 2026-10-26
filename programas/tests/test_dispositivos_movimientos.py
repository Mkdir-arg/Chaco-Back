"""Movimientos de la estadía, cambio de plaza y permanencia (MVP v2, etapa 3 · #694).

Lo que se verifica, y por qué:

1. **Cada movimiento queda con autor y momento**, y el ingreso y el egreso también dejan
   el suyo: la línea de tiempo de P7 sale de un solo lugar.
2. **El cambio de plaza pasa por las mismas reglas que el ingreso**: la plaza de destino
   se bloquea y tiene que estar libre —ni ocupada, ni fuera de servicio, ni reservada,
   ni de otra institución—. Cada regla tiene su test, y cada test falla si se saca la
   guarda que prueba.
3. **La permanencia se calcula y coincide con los movimientos.**
4. **Los movimientos no se corrigen ni se borran.**
5. **La migración reconstruye la historia de las estadías anteriores** sin duplicarla.
"""

from datetime import datetime, timedelta
from importlib import import_module
from unittest import mock

from django.apps import apps
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models.query import QuerySet
from django.utils import timezone

from legajos.models import Ciudadano
from programas.models import (
    Estadia,
    MotivoEgreso,
    MovimientoEstadia,
    Plaza,
    ReservaPlaza,
    Sector,
    TrazaDispositivo,
)
from programas.services.estadias import (
    PLAZA_FUERA_DEL_DISPOSITIVO,
    PLAZA_OCUPADA_EN_EL_MEDIO,
    YA_TIENE_PLAZA,
    asignar_plaza,
    cambiar_plaza,
    egresar_persona,
    ingresar_persona,
    reservar_plaza,
    sacar_plaza_de_servicio,
)
from programas.services.movimientos import linea_de_tiempo, tramos_por_plaza
from programas.services.ocupacion import ocupacion_de_plazas
from programas.tests.test_dispositivos_estadias import BaseEstadias

Tipo = MovimientoEstadia.Tipo


class BaseMovimientos(BaseEstadias):
    """Una persona alojada hace tres días en la plaza P1 del CIS."""

    def setUp(self):
        super().setUp()
        self.ingreso = timezone.now() - timedelta(days=3)
        self.estadia = ingresar_persona(
            ciudadano=self.persona,
            dispositivo=self.cis,
            plaza=self.plaza,
            usuario=self.operador_cis,
            fecha_ingreso=self.ingreso,
        )
        self.otro_sector = Sector.objects.create(dispositivo=self.cis, nombre="Mujeres", capacidad=2)
        self.plaza_otro_sector = Plaza.objects.create(sector=self.otro_sector, codigo="M1")

    def _cambiar(self, plaza, **kwargs):
        kwargs.setdefault("usuario", self.operador_cis)
        kwargs.setdefault("motivo", "Convivencia")
        return cambiar_plaza(estadia=self.estadia, plaza=plaza, **kwargs)

    def _sin_cambios(self):
        """Lo que un cambio rechazado tiene que dejar igual: la plaza y la línea de tiempo."""

        self.estadia.refresh_from_db()
        self.assertEqual(self.estadia.plaza_id, self.plaza.pk)
        self.assertEqual(list(self.estadia.movimientos.values_list("tipo", flat=True)), [Tipo.INGRESO])


class IngresoYEgresoDejanMovimientoTests(BaseMovimientos):
    def test_el_ingreso_deja_su_movimiento_con_la_fecha_del_ingreso_y_no_la_de_la_carga(self):
        movimiento = self.estadia.movimientos.get()

        self.assertEqual(movimiento.tipo, Tipo.INGRESO)
        self.assertEqual(movimiento.momento, self.ingreso)
        self.assertEqual(movimiento.responsable, self.operador_cis)
        self.assertEqual(movimiento.dispositivo_id, self.cis.pk)
        self.assertEqual(movimiento.plaza_destino, self.plaza)
        self.assertIsNone(movimiento.plaza_origen)
        self.assertEqual((movimiento.estado_anterior, movimiento.estado_nuevo), ("", Estadia.Estado.ACTIVA))

    def test_el_egreso_deja_su_movimiento_con_la_fecha_del_egreso_y_el_motivo(self):
        motivo = MotivoEgreso.objects.create(codigo="alta-test", nombre="Alta de prueba")
        egreso = timezone.now() - timedelta(hours=1)
        egresar_persona(
            destino="Domicilio",
            estadia=self.estadia,
            usuario=self.operador_cis,
            fecha_egreso=egreso,
            motivo_egreso=motivo,
        )

        movimiento = self.estadia.movimientos.get(tipo=Tipo.EGRESO)
        self.assertEqual(movimiento.momento, egreso)
        self.assertEqual(movimiento.responsable, self.operador_cis)
        self.assertEqual(movimiento.motivo, "Alta de prueba")
        self.assertEqual(movimiento.plaza_origen, self.plaza)
        self.assertEqual(
            (movimiento.estado_anterior, movimiento.estado_nuevo), (Estadia.Estado.ACTIVA, Estadia.Estado.EGRESADA)
        )

    def test_el_egreso_no_puede_ser_anterior_al_ultimo_movimiento(self):
        cambio = timezone.now() - timedelta(days=1)
        self._cambiar(self.otra_plaza, momento=cambio)

        with self.assertRaises(ValidationError):
            egresar_persona(
                destino="Domicilio",
                estadia=self.estadia,
                usuario=self.operador_cis,
                fecha_egreso=cambio - timedelta(hours=1),
                motivo_egreso=self.motivo_alta,
            )

        self.estadia.refresh_from_db()
        self.assertTrue(self.estadia.activa)
        self.assertFalse(self.estadia.movimientos.filter(tipo=Tipo.EGRESO).exists())

    def test_un_ingreso_rechazado_no_deja_movimiento(self):
        with self.assertRaises(ValidationError):
            ingresar_persona(
                ciudadano=self.otra_persona, dispositivo=self.cis, plaza=self.plaza, usuario=self.operador_cis
            )

        self.assertEqual(MovimientoEstadia.objects.count(), 1)


class CambioDePlazaTests(BaseMovimientos):
    def test_el_cambio_mueve_a_la_persona_y_deja_su_movimiento_con_autor_y_momento(self):
        momento = timezone.now() - timedelta(hours=5)
        movimiento = self._cambiar(self.otra_plaza, momento=momento)

        self.estadia.refresh_from_db()
        self.assertEqual(self.estadia.plaza, self.otra_plaza)
        self.assertEqual(movimiento.tipo, Tipo.CAMBIO_PLAZA)
        self.assertEqual(movimiento.momento, momento)
        self.assertEqual(movimiento.responsable, self.operador_cis)
        self.assertEqual(movimiento.motivo, "Convivencia")
        self.assertEqual((movimiento.plaza_origen, movimiento.plaza_destino), (self.plaza, self.otra_plaza))
        self.assertEqual(movimiento.dispositivo_id, self.cis.pk)
        self.assertTrue(TrazaDispositivo.objects.filter(dispositivo=self.cis, accion="ESTADIA_CAMBIO_PLAZA").exists())

    def test_sin_momento_el_cambio_es_ahora(self):
        antes = timezone.now()
        movimiento = self._cambiar(self.otra_plaza)

        self.assertGreaterEqual(movimiento.momento, antes)
        self.assertLessEqual(movimiento.momento, timezone.now())

    def test_a_una_plaza_de_otro_sector_es_un_cambio_de_sector(self):
        movimiento = self._cambiar(self.plaza_otro_sector)

        self.assertEqual(movimiento.tipo, Tipo.CAMBIO_SECTOR)

    def test_la_plaza_de_origen_queda_libre_para_otra_persona(self):
        self._cambiar(self.otra_plaza)

        conteo = ocupacion_de_plazas(self.cis).de(self.cis).conteo
        self.assertEqual(conteo.ocupadas, 1)
        otra = ingresar_persona(
            ciudadano=self.otra_persona, dispositivo=self.cis, plaza=self.plaza, usuario=self.operador_cis
        )
        self.assertEqual(otra.plaza, self.plaza)

    def test_no_se_mueve_a_una_plaza_ocupada(self):
        ingresar_persona(
            ciudadano=self.otra_persona, dispositivo=self.cis, plaza=self.otra_plaza, usuario=self.operador_cis
        )

        with self.assertRaisesMessage(ValidationError, "estadía activa"):
            self._cambiar(self.otra_plaza)
        self._sin_cambios()

    def test_no_se_mueve_a_una_plaza_fuera_de_servicio(self):
        sacar_plaza_de_servicio(plaza=self.otra_plaza, usuario=self.operador_cis, motivo="Colchón roto")

        with self.assertRaisesMessage(ValidationError, "fuera de servicio"):
            self._cambiar(self.otra_plaza)
        self._sin_cambios()

    def test_no_se_mueve_a_una_plaza_reservada_para_otra_persona(self):
        reservar_plaza(plaza=self.otra_plaza, ciudadano=self.otra_persona, usuario=self.operador_cis)

        with self.assertRaisesMessage(ValidationError, "reserva vigente"):
            self._cambiar(self.otra_plaza)
        self._sin_cambios()

    def test_no_se_mueve_a_una_plaza_prestada(self):
        reservar_plaza(
            plaza=self.otra_plaza,
            ciudadano=self.otra_persona,
            usuario=self.operador_cis,
            tipo=ReservaPlaza.Tipo.PRESTAMO,
            hasta=timezone.now() + timedelta(hours=12),
        )

        with self.assertRaisesMessage(ValidationError, "préstamo vigente"):
            self._cambiar(self.otra_plaza)
        self._sin_cambios()

    def test_no_se_mueve_a_una_plaza_de_un_sector_dado_de_baja(self):
        baja = Sector.objects.create(dispositivo=self.cis, nombre="Cerrado", activo=False)
        plaza = Plaza.objects.create(sector=baja, codigo="X1")

        with self.assertRaisesMessage(ValidationError, "dado de baja"):
            self._cambiar(plaza)
        self._sin_cambios()

    def test_no_se_mueve_a_una_plaza_de_otro_dispositivo(self):
        with self.assertRaisesMessage(ValidationError, PLAZA_FUERA_DEL_DISPOSITIVO):
            self._cambiar(self.plaza_parador)
        self._sin_cambios()

    def test_no_se_mueve_a_la_plaza_en_la_que_ya_esta(self):
        with self.assertRaisesMessage(ValidationError, "ya está en esa plaza"):
            self._cambiar(self.plaza)
        self._sin_cambios()

    def test_una_estadia_cerrada_no_se_mueve(self):
        egresar_persona(
            destino="Domicilio", estadia=self.estadia, usuario=self.operador_cis, motivo_egreso=self.motivo_alta
        )

        with self.assertRaisesMessage(ValidationError, "ya está cerrada"):
            self._cambiar(self.otra_plaza)
        self.estadia.refresh_from_db()
        self.assertEqual(self.estadia.plaza_id, self.plaza.pk)
        self.assertFalse(self.estadia.movimientos.filter(tipo__in=MovimientoEstadia.TIPOS_DE_CAMBIO_DE_PLAZA))

    def test_el_cambio_exige_motivo(self):
        with self.assertRaisesMessage(ValidationError, "exige un motivo"):
            self._cambiar(self.otra_plaza, motivo="   ")
        self._sin_cambios()

    def test_el_cambio_no_puede_ser_futuro(self):
        with self.assertRaisesMessage(ValidationError, "futuro"):
            self._cambiar(self.otra_plaza, momento=timezone.now() + timedelta(minutes=5))
        self._sin_cambios()

    def test_el_cambio_no_puede_ser_anterior_al_ultimo_movimiento(self):
        with self.assertRaisesMessage(ValidationError, "último movimiento"):
            self._cambiar(self.otra_plaza, momento=self.ingreso - timedelta(minutes=1))
        self._sin_cambios()

    def test_el_cambio_no_puede_ser_anterior_al_cambio_previo_aunque_sea_posterior_al_ingreso(self):
        """El de arriba pasa aunque la guarda compare contra el ingreso: este no.

        El segundo cambio se fecha **entre el ingreso y el primer cambio**. Contra el ingreso
        pasaría, y dejaría a la persona saliendo de P2 antes de haber llegado; contra
        `ultimo_momento` —el del primer cambio— se rechaza.
        """

        primero = self.ingreso + timedelta(days=2)
        self._cambiar(self.otra_plaza, momento=primero)

        with self.assertRaisesMessage(ValidationError, "último movimiento"):
            self._cambiar(self.plaza_otro_sector, momento=self.ingreso + timedelta(days=1))

        self.estadia.refresh_from_db()
        self.assertEqual(self.estadia.plaza_id, self.otra_plaza.pk)
        self.assertEqual(
            list(self.estadia.movimientos.values_list("tipo", flat=True)), [Tipo.INGRESO, Tipo.CAMBIO_PLAZA]
        )

    def test_bloquea_la_plaza_de_destino_y_la_estadia(self):
        """La exclusión es `select_for_update`, no un constraint: si el bloqueo se va, esto se pone rojo.

        SQLite no emite el `FOR UPDATE`, así que se mira qué modelos se piden bloqueados.
        """

        original = QuerySet.select_for_update
        bloqueados = []

        def registrar(queryset, *args, **kwargs):
            bloqueados.append(queryset.model)
            return original(queryset, *args, **kwargs)

        with mock.patch.object(QuerySet, "select_for_update", autospec=True, side_effect=registrar):
            self._cambiar(self.otra_plaza)

        self.assertEqual(bloqueados, [Plaza, Estadia], "primero la plaza, después la estadía")


class AutorizacionDelCambioTests(BaseMovimientos):
    def test_sin_admitir_no_se_cambia_de_plaza_aunque_tenga_todo_lo_demas(self):
        sin_admitir = self._operador(
            "Sin admitir", self.cis, capacidades=("dispositivo.ver", "dispositivo.egresar", "dispositivo.editar")
        )

        with self.assertRaises(PermissionDenied):
            self._cambiar(self.otra_plaza, usuario=sin_admitir)
        self._sin_cambios()

    def test_con_admitir_en_otra_institucion_no_se_cambia_de_plaza(self):
        with self.assertRaises(PermissionDenied):
            self._cambiar(self.otra_plaza, usuario=self.operador_parador)
        self._sin_cambios()


class AsignarPlazaTests(BaseEstadias):
    """«Asignar plaza» a quien ingresó sin plaza: mismas reglas de plaza que el cambio, motivo opcional."""

    def setUp(self):
        super().setUp()
        self.ingreso = timezone.now() - timedelta(days=2)
        # El tipo de la base no maneja plazas ni la exige: el ingreso «Sin plaza» es válido.
        self.estadia = ingresar_persona(
            ciudadano=self.persona, dispositivo=self.cis, usuario=self.operador_cis, fecha_ingreso=self.ingreso
        )
        self.assertIsNone(self.estadia.plaza_id)
        self.tipo.plaza_obligatoria_al_ingresar = True
        self.tipo.save()

    def _asignar(self, plaza, **kwargs):
        kwargs.setdefault("usuario", self.operador_cis)
        return asignar_plaza(estadia=self.estadia, plaza=plaza, **kwargs)

    def _sin_cambios(self):
        self.estadia.refresh_from_db()
        self.assertIsNone(self.estadia.plaza_id)
        self.assertEqual(list(self.estadia.movimientos.values_list("tipo", flat=True)), [Tipo.INGRESO])

    def test_asigna_la_plaza_y_deja_movimiento_traza_y_motivo_opcional(self):
        momento = timezone.now() - timedelta(hours=3)
        movimiento = self._asignar(self.plaza, momento=momento)

        self.estadia.refresh_from_db()
        self.assertEqual(self.estadia.plaza, self.plaza)
        self.assertEqual(movimiento.tipo, Tipo.CAMBIO_PLAZA)
        self.assertIsNone(movimiento.plaza_origen)
        self.assertEqual(movimiento.plaza_destino, self.plaza)
        self.assertEqual(movimiento.momento, momento)
        self.assertEqual(movimiento.responsable, self.operador_cis)
        self.assertEqual(movimiento.motivo, "")
        self.assertTrue(
            TrazaDispositivo.objects.filter(dispositivo=self.cis, accion="ESTADIA_ASIGNACION_PLAZA").exists()
        )

    def test_la_novedad_automatica_dice_que_se_asigno_la_plaza(self):
        from programas.services.bitacora import _texto_automatico

        movimiento = self._asignar(self.plaza)

        self.assertEqual(_texto_automatico(movimiento), f"Se asignó la plaza {self.plaza.codigo}")

    def test_la_persona_cuenta_en_la_plaza_desde_el_momento_asignado(self):
        momento = timezone.now() - timedelta(hours=5)
        self._asignar(self.plaza, momento=momento)

        tramos = tramos_por_plaza(self.estadia)
        self.assertEqual([(t.plaza_id, t.desde) for t in tramos], [(None, self.ingreso), (self.plaza.pk, momento)])
        self.assertEqual(ocupacion_de_plazas(self.cis).de(self.cis).conteo.ocupadas, 1)

    def test_con_motivo_queda_en_el_movimiento(self):
        movimiento = self._asignar(self.plaza, motivo="  Se liberó una plaza  ")

        self.assertEqual(movimiento.motivo, "Se liberó una plaza")

    def test_una_estadia_con_plaza_se_cambia_no_se_asigna(self):
        self._asignar(self.plaza)

        with self.assertRaises(ValidationError) as error:
            self._asignar(self.otra_plaza)

        self.assertEqual(error.exception.message_dict["plaza"], [YA_TIENE_PLAZA])
        self.estadia.refresh_from_db()
        self.assertEqual(self.estadia.plaza, self.plaza)

    def test_una_plaza_ocupada_no_se_asigna(self):
        ingresar_persona(ciudadano=self.otra_persona, dispositivo=self.cis, plaza=self.plaza, usuario=self.operador_cis)

        with self.assertRaises(ValidationError):
            self._asignar(self.plaza)
        self._sin_cambios()

    def test_una_plaza_de_otro_dispositivo_no_se_asigna(self):
        with self.assertRaises(ValidationError) as error:
            self._asignar(self.plaza_parador)

        self.assertEqual(error.exception.message_dict["plaza"], [PLAZA_FUERA_DEL_DISPOSITIVO])
        self._sin_cambios()

    def test_el_momento_no_puede_ser_futuro_ni_anterior_al_ingreso(self):
        for momento in (timezone.now() + timedelta(hours=1), self.ingreso - timedelta(hours=1)):
            with self.subTest(momento=momento), self.assertRaises(ValidationError) as error:
                self._asignar(self.plaza, momento=momento)
            self.assertIn("momento", error.exception.message_dict)
        self._sin_cambios()

    def test_la_plaza_tiene_que_haber_estado_libre_desde_el_momento(self):
        ocupante = ingresar_persona(
            ciudadano=self.otra_persona,
            dispositivo=self.cis,
            plaza=self.plaza,
            usuario=self.operador_cis,
            fecha_ingreso=self.ingreso,
        )
        cambiar_plaza(
            estadia=ocupante,
            plaza=self.otra_plaza,
            usuario=self.operador_cis,
            motivo="x",
            momento=timezone.now() - timedelta(hours=1),
        )

        with self.assertRaises(ValidationError) as error:
            self._asignar(self.plaza, momento=timezone.now() - timedelta(hours=5))

        self.assertEqual(error.exception.message_dict["momento"], [PLAZA_OCUPADA_EN_EL_MEDIO])
        self._sin_cambios()

    def test_un_tipo_que_no_maneja_plazas_no_asigna(self):
        self.tipo.plaza_obligatoria_al_ingresar = False
        self.tipo.save()
        self.estadia.dispositivo.tipo.refresh_from_db()

        with self.assertRaises(ValidationError):
            self._asignar(self.plaza)
        self._sin_cambios()

    def test_una_estadia_cerrada_no_se_asigna(self):
        egresar_persona(
            destino="Domicilio", estadia=self.estadia, usuario=self.operador_cis, motivo_egreso=self.motivo_alta
        )

        with self.assertRaises(ValidationError):
            self._asignar(self.plaza)

    def test_sin_admitir_o_en_otra_institucion_es_permission_denied(self):
        sin_admitir = self._operador("Sin admitir", self.cis, capacidades=("dispositivo.ver", "dispositivo.egresar"))

        for usuario in (sin_admitir, self.operador_parador):
            with self.subTest(usuario=usuario.username), self.assertRaises(PermissionDenied):
                self._asignar(self.plaza, usuario=usuario)
        self._sin_cambios()

    def test_bloquea_primero_la_plaza_y_despues_la_estadia(self):
        bloqueados = []
        original = QuerySet.select_for_update

        def registrar(queryset, *args, **kwargs):
            bloqueados.append(queryset.model)
            return original(queryset, *args, **kwargs)

        with mock.patch.object(QuerySet, "select_for_update", autospec=True, side_effect=registrar):
            self._asignar(self.plaza)

        self.assertEqual(bloqueados, [Plaza, Estadia])


class PermanenciaTests(BaseMovimientos):
    def test_la_permanencia_de_una_estadia_cerrada_coincide_con_sus_movimientos(self):
        self._cambiar(self.otra_plaza, momento=timezone.now() - timedelta(days=2))
        self._cambiar(self.plaza_otro_sector, momento=timezone.now() - timedelta(days=1))
        egresar_persona(
            destino="Domicilio", estadia=self.estadia, usuario=self.operador_cis, motivo_egreso=self.motivo_alta
        )
        self.estadia.refresh_from_db()

        movimientos = list(linea_de_tiempo(self.estadia))
        self.assertEqual(
            [m.tipo for m in movimientos], [Tipo.INGRESO, Tipo.CAMBIO_PLAZA, Tipo.CAMBIO_SECTOR, Tipo.EGRESO]
        )
        self.assertEqual(self.estadia.permanencia(), movimientos[-1].momento - movimientos[0].momento)

        tramos = tramos_por_plaza(self.estadia)
        self.assertEqual([t.plaza_id for t in tramos], [self.plaza.pk, self.otra_plaza.pk, self.plaza_otro_sector.pk])
        self.assertEqual(sum((t.duracion for t in tramos), timedelta()), self.estadia.permanencia())

    def test_la_permanencia_de_una_estadia_abierta_corre_hasta_ahora(self):
        self._cambiar(self.otra_plaza, momento=timezone.now() - timedelta(days=1))
        corte = timezone.now()

        self.assertEqual(self.estadia.permanencia(corte), corte - self.ingreso)
        tramos = tramos_por_plaza(self.estadia, momento=corte)
        self.assertEqual(tramos[-1].hasta, corte)
        self.assertEqual(sum((t.duracion for t in tramos), timedelta()), self.estadia.permanencia(corte))

    def test_los_dias_de_permanencia_son_de_calendario_en_la_hora_local(self):
        """El ejemplo del mockup: ingreso el 03/09 a las 19:40, hoy 08/09 a las 16:48 → 5 días."""

        ingreso = timezone.make_aware(datetime(2026, 9, 3, 19, 40))
        estadia = Estadia(fecha_ingreso=ingreso)

        self.assertEqual(estadia.dias_de_permanencia(timezone.make_aware(datetime(2026, 9, 8, 16, 48))), 5)
        # Pasada la medianoche local ya es otro día, aunque no hayan pasado 24 horas.
        self.assertEqual(estadia.dias_de_permanencia(timezone.make_aware(datetime(2026, 9, 4, 0, 5))), 1)


class MovimientosInmutablesTests(BaseMovimientos):
    def test_un_movimiento_no_se_corrige(self):
        movimiento = self.estadia.movimientos.get()
        movimiento.motivo = "otra cosa"

        with self.assertRaises(ValidationError):
            movimiento.save()
        with self.assertRaises(ValidationError):
            MovimientoEstadia.objects.filter(pk=movimiento.pk).update(motivo="otra cosa")

    def test_un_movimiento_no_se_borra(self):
        movimiento = self.estadia.movimientos.get()

        with self.assertRaises(ValidationError):
            movimiento.delete()
        with self.assertRaises(ValidationError):
            MovimientoEstadia.objects.filter(pk=movimiento.pk).delete()
        self.assertTrue(MovimientoEstadia.objects.filter(pk=movimiento.pk).exists())

    def test_la_base_rechaza_un_cambio_de_plaza_a_la_misma_plaza_o_a_ninguna(self):
        for origen, destino in ((self.plaza, self.plaza), (self.plaza, None)):
            with self.subTest(destino=destino), self.assertRaises(IntegrityError), transaction.atomic():
                MovimientoEstadia.objects.create(
                    estadia=self.estadia,
                    dispositivo=self.cis,
                    tipo=Tipo.CAMBIO_PLAZA,
                    momento=timezone.now(),
                    plaza_origen=origen,
                    plaza_destino=destino,
                )


class ReconstruccionDeLaMigracionTests(BaseEstadias):
    migracion = "programas.migrations.0089_movimiento_estadia"

    def test_reconstruye_ingreso_y_egreso_de_las_estadias_anteriores_sin_duplicar(self):
        ingreso = timezone.now() - timedelta(days=10)
        egreso = timezone.now() - timedelta(days=4)
        motivo = MotivoEgreso.objects.create(codigo="traslado-test", nombre="Traslado de prueba")
        cerrada = Estadia.objects.create(
            ciudadano=self.persona,
            dispositivo=self.cis,
            plaza=self.plaza,
            fecha_ingreso=ingreso,
            fecha_egreso=egreso,
            estado=Estadia.Estado.EGRESADA,
            motivo=motivo,
            ingresada_por=self.operador_cis,
        )
        abierta = Estadia.objects.create(
            ciudadano=self.otra_persona,
            dispositivo=self.cis,
            plaza=self.otra_plaza,
            fecha_ingreso=ingreso,
            clave_alojamiento=Estadia.clave_para(self.otra_persona),
        )

        reconstruir = import_module(self.migracion).reconstruir_movimientos
        reconstruir(apps, schema_editor=None)
        reconstruir(apps, schema_editor=None)

        self.assertEqual(
            [(m.tipo, m.momento, m.responsable_id, m.motivo) for m in linea_de_tiempo(cerrada)],
            [(Tipo.INGRESO, ingreso, self.operador_cis.pk, ""), (Tipo.EGRESO, egreso, None, "Traslado de prueba")],
        )
        self.assertEqual([m.tipo for m in linea_de_tiempo(abierta)], [Tipo.INGRESO])
        self.assertEqual(sum((t.duracion for t in tramos_por_plaza(cerrada)), timedelta()), cerrada.permanencia())


class PlazaOcupadaEnElMedioTests(BaseEstadias):
    """Revisión de #826, MINOR 3: una carga retroactiva mira la plaza **desde** su fecha, no solo ahora.

    Juan ocupó P2 del lunes 10:00 al martes 10:00; hoy, miércoles al mediodía, P2 está
    libre. Mover a Ana —o ingresar a alguien— a P2 con fecha del lunes a la noche pasaba
    el control de «plaza libre ahora» y dejaba dos personas en P2 durante doce horas,
    que es lo que después leen la línea de tiempo y el censo. Reloj fijo.
    """

    LUNES = timezone.make_aware(datetime(2026, 9, 7, 10))
    AHORA = LUNES + timedelta(days=2, hours=2)

    def setUp(self):
        super().setUp()
        with self._reloj():
            self.ana = ingresar_persona(
                ciudadano=self.persona,
                dispositivo=self.cis,
                plaza=self.plaza,
                usuario=self.operador_cis,
                fecha_ingreso=self.LUNES - timedelta(days=1),
            )
            juan = ingresar_persona(
                ciudadano=self.otra_persona,
                dispositivo=self.cis,
                plaza=self.otra_plaza,
                usuario=self.operador_cis,
                fecha_ingreso=self.LUNES,
            )
            self.salida_de_juan = self.LUNES + timedelta(days=1)
            egresar_persona(
                destino="Domicilio",
                estadia=juan,
                usuario=self.operador_cis,
                fecha_egreso=self.salida_de_juan,
                motivo_egreso=self.motivo_alta,
            )

    def _reloj(self):
        return mock.patch("django.utils.timezone.now", return_value=self.AHORA)

    def _cambiar(self, momento):
        with self._reloj():
            return cambiar_plaza(
                estadia=self.ana,
                plaza=self.otra_plaza,
                usuario=self.operador_cis,
                motivo="Convivencia",
                momento=momento,
            )

    def _ingresar_tercera(self, fecha):
        tercera = Ciudadano.objects.create(dni="30555666", nombre="Rosa", apellido="Benítez")
        with self._reloj():
            return ingresar_persona(
                ciudadano=tercera,
                dispositivo=self.cis,
                plaza=self.otra_plaza,
                usuario=self.operador_cis,
                fecha_ingreso=fecha,
            )

    def test_un_cambio_retroactivo_a_una_plaza_que_otro_ocupo_en_el_medio_no_entra(self):
        with self.assertRaisesMessage(ValidationError, PLAZA_OCUPADA_EN_EL_MEDIO):
            self._cambiar(self.LUNES + timedelta(hours=12))

        self.ana.refresh_from_db()
        self.assertEqual(self.ana.plaza, self.plaza)
        self.assertEqual(list(self.ana.movimientos.values_list("tipo", flat=True)), [Tipo.INGRESO])

    def test_tambien_si_el_otro_entro_despues_de_la_fecha_del_cambio(self):
        with self.assertRaisesMessage(ValidationError, PLAZA_OCUPADA_EN_EL_MEDIO):
            self._cambiar(self.LUNES - timedelta(hours=2))

    def test_el_cambio_fechado_despues_de_que_el_otro_salio_si_entra(self):
        movimiento = self._cambiar(self.salida_de_juan + timedelta(hours=1))

        self.assertEqual(movimiento.plaza_destino, self.otra_plaza)

    def test_el_cambio_fechado_justo_cuando_el_otro_salio_entra(self):
        """`[desde, hasta)`: Juan ya no estaba en el instante en que salió."""

        movimiento = self._cambiar(self.salida_de_juan)

        self.assertEqual(movimiento.momento, self.salida_de_juan)

    def test_un_ingreso_retroactivo_a_una_plaza_que_otro_ocupo_en_el_medio_no_entra(self):
        with self.assertRaisesMessage(ValidationError, PLAZA_OCUPADA_EN_EL_MEDIO):
            self._ingresar_tercera(self.LUNES + timedelta(hours=12))

        self.assertFalse(Estadia.objects.filter(ciudadano__dni="30555666").exists())

    def test_el_ingreso_retroactivo_despues_de_que_el_otro_salio_si_entra(self):
        estadia = self._ingresar_tercera(self.salida_de_juan + timedelta(minutes=1))

        self.assertEqual(estadia.plaza, self.otra_plaza)
