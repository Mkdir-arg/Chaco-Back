"""Novedades automáticas de la bitácora: ingreso, egreso y cambio de plaza (P10).

El modelo de la bitácora (Cambio 274) traía tipos reservados al sistema —INGRESO, EGRESO,
MOVIMIENTO— que **ningún servicio escribía**, y P10 los muestra en las entradas del turno
con la marca «automática». Acá entran, y lo que se verifica es:

1. **Cada movimiento de la estadía deja su novedad**, en la misma transacción: si el
   cambio se deshace, la novedad también.
2. **No se duplica.** La novedad cuelga del `MovimientoEstadia` con un uno a uno, y la
   base rechaza una segunda del mismo movimiento. No es cosmético: es lo que hace que un
   reintento no cuente dos veces lo mismo en la bitácora.
3. **El nombre de la persona no va en el texto.** Va en `personas`, que es lo que la
   pantalla nombra solo con `ciudadano.ver` (Cambio 271): si estuviera en el texto, la
   bitácora se lo contaría a cualquiera con `dispositivo.ver`, que es menos.
4. **No se inventa un turno.** Sin turno para ese momento —un hueco, o un dispositivo sin
   turnos configurados— no hay novedad, y el ingreso se registra igual.
5. **Ni el censo ni la auditoría se rompen**: el censo cuenta movimientos y estadías, no
   novedades, y la auditoría solo muestra correcciones (versión > 1), así que una entrada
   automática no aparece dos veces en el historial.
6. **No se corrigen desde la bitácora**: `corregir_entrada` las rechaza, y la pantalla no
   las ofrece.
"""

from datetime import time, timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from programas.models import EntradaBitacora, Estadia, MovimientoEstadia, Plaza
from programas.services.bitacora import anotar_en_bitacora, crear_turno
from programas.services.censo import censo_del_dia, fecha_operativa_de
from programas.services.estadias import cambiar_plaza, egresar_persona, ingresar_persona
from programas.tests.test_dispositivos_estadias import BaseEstadias

Tipo = EntradaBitacora.Tipo


class BaseAutomaticas(BaseEstadias):
    """El CIS con una guardia de 24 h: cualquier momento cae adentro de un turno."""

    def setUp(self):
        super().setUp()
        self.operador_cis = self._operador(
            "Operador automáticas", self.cis, ("dispositivo.ver", "dispositivo.admitir", "dispositivo.egresar")
        )
        self.turno = crear_turno(
            dispositivo=self.cis,
            usuario=self._operador("Config turnos", self.cis, ("dispositivo.editar",)),
            nombre="Guardia",
            hora_desde=time(8),
            hora_hasta=time(8),
        )

    def _alojar(self, **kwargs):
        kwargs.setdefault("ciudadano", self.persona)
        kwargs.setdefault("dispositivo", self.cis)
        kwargs.setdefault("plaza", self.plaza)
        kwargs.setdefault("usuario", self.operador_cis)
        return ingresar_persona(**kwargs)

    def _entradas(self):
        return list(EntradaBitacora.objects.filter(dispositivo=self.cis).order_by("momento", "id"))


class CadaMovimientoDejaSuNovedadTests(BaseAutomaticas):
    def test_el_ingreso_deja_su_novedad_con_el_turno_la_hora_y_la_persona(self):
        ingreso = timezone.now() - timedelta(hours=2)

        estadia = self._alojar(fecha_ingreso=ingreso)

        entrada = EntradaBitacora.objects.get(dispositivo=self.cis)
        self.assertEqual(entrada.tipo, Tipo.INGRESO)
        self.assertEqual(entrada.origen, EntradaBitacora.Origen.AUTOMATICA)
        self.assertEqual(entrada.turno, self.turno)
        self.assertEqual(entrada.momento, ingreso, "la novedad es de cuándo pasó, no de cuándo se cargó")
        self.assertEqual(entrada.responsable, self.operador_cis)
        self.assertEqual(entrada.texto, "Ingreso · plaza P1")
        self.assertEqual(list(entrada.personas.all()), [estadia])
        self.assertEqual(entrada.movimiento, estadia.movimientos.get(tipo=MovimientoEstadia.Tipo.INGRESO))

    def test_el_egreso_deja_su_novedad_con_el_motivo_del_catalogo(self):
        estadia = self._alojar(fecha_ingreso=timezone.now() - timedelta(days=1))

        egresar_persona(estadia=estadia, usuario=self.operador_cis, motivo_egreso=self.motivo_alta)

        entrada = EntradaBitacora.objects.get(dispositivo=self.cis, tipo=Tipo.EGRESO)
        self.assertEqual(entrada.texto, "Egreso · motivo: Alta")
        self.assertEqual(list(entrada.personas.all()), [estadia])

    def test_el_cambio_de_plaza_deja_una_novedad_de_tipo_movimiento(self):
        estadia = self._alojar(fecha_ingreso=timezone.now() - timedelta(days=1))

        cambiar_plaza(estadia=estadia, plaza=self.otra_plaza, usuario=self.operador_cis, motivo="Convivencia")

        entrada = EntradaBitacora.objects.get(dispositivo=self.cis, tipo=Tipo.MOVIMIENTO)
        self.assertEqual(entrada.texto, "Cambio de plaza · P1 → P2 · motivo: Convivencia")

    def test_el_nombre_de_la_persona_no_va_en_el_texto(self):
        """Va en `personas`, que la pantalla nombra solo con `ciudadano.ver` (Cambio 271)."""

        estadia = self._alojar()
        egresar_persona(estadia=estadia, usuario=self.operador_cis, motivo_egreso=self.motivo_alta)

        for entrada in self._entradas():
            self.assertNotIn(self.persona.apellido, entrada.texto, entrada.texto)
            self.assertNotIn(self.persona.dni, entrada.texto, entrada.texto)

    def test_las_observaciones_libres_del_egreso_no_entran_en_la_novedad(self):
        estadia = self._alojar()

        egresar_persona(
            estadia=estadia,
            usuario=self.operador_cis,
            motivo="Refiere violencia en el domicilio",
            motivo_egreso=self.motivo_alta,
        )

        entrada = EntradaBitacora.objects.get(dispositivo=self.cis, tipo=Tipo.EGRESO)
        self.assertNotIn("violencia", entrada.texto)


class NoSeDuplicanTests(BaseAutomaticas):
    def test_la_base_rechaza_una_segunda_novedad_del_mismo_movimiento(self):
        """La guarda contra el reintento: el uno a uno no depende de que nadie llame dos veces."""

        estadia = self._alojar()
        movimiento = estadia.movimientos.get(tipo=MovimientoEstadia.Tipo.INGRESO)

        with self.assertRaises(IntegrityError), transaction.atomic():
            anotar_en_bitacora(movimiento)

        self.assertEqual(EntradaBitacora.objects.filter(movimiento=movimiento).count(), 1)

    def test_un_ingreso_rechazado_no_deja_novedad(self):
        """Misma transacción: si el alta se deshace, la bitácora no se queda con el rastro."""

        self._alojar()
        antes = EntradaBitacora.objects.count()

        with self.assertRaises(ValidationError):
            ingresar_persona(
                ciudadano=self.otra_persona,
                dispositivo=self.cis,
                plaza=self.plaza,
                usuario=self.operador_cis,
            )

        self.assertEqual(EntradaBitacora.objects.count(), antes)


class SinTurnoNoSeInventaTests(BaseAutomaticas):
    def test_sin_turnos_configurados_el_ingreso_se_registra_igual_y_sin_novedad(self):
        self.turno.activo = False
        self.turno.save(update_fields=["activo", "modificado"])

        estadia = self._alojar()

        self.assertTrue(estadia.activa)
        self.assertEqual(EntradaBitacora.objects.count(), 0)

    def test_un_momento_en_un_hueco_entre_turnos_no_deja_novedad(self):
        """Mañana 06-14 y Tarde 14-22: entre las 22 y las 06 no hay turno."""

        self.turno.hora_desde, self.turno.hora_hasta = time(6), time(22)
        self.turno.save(update_fields=["hora_desde", "hora_hasta", "modificado"])
        madrugada = timezone.localtime(timezone.now() - timedelta(days=1)).replace(
            hour=3, minute=0, second=0, microsecond=0
        )

        estadia = self._alojar(fecha_ingreso=madrugada)

        self.assertTrue(estadia.activa)
        self.assertEqual(EntradaBitacora.objects.count(), 0)


class NoRompeElCensoNiLaAuditoriaTests(BaseAutomaticas):
    def test_el_censo_sigue_contando_movimientos_y_no_novedades(self):
        # Ambos movimientos pertenecen al mismo día operativo, a cualquier hora del runner.
        ingreso = timezone.localtime(timezone.now() - timedelta(days=1)).replace(
            hour=10, minute=0, second=0, microsecond=0
        )
        egreso = ingreso.replace(hour=12)
        estadia = self._alojar(fecha_ingreso=ingreso)
        egresar_persona(
            estadia=estadia,
            usuario=self.operador_cis,
            fecha_egreso=egreso,
            motivo_egreso=self.motivo_alta,
        )

        censo = censo_del_dia(self.cis, fecha_operativa_de(self.cis, ingreso))

        self.assertEqual((censo.ingresos, censo.egresos), (1, 1))
        self.assertTrue(all(tramo.cuadra for tramo in censo.tramos), "una novedad no mueve el censo")

    def test_la_auditoria_no_cuenta_la_novedad_automatica_como_un_evento_mas(self):
        """El historial ya tiene el movimiento: la novedad sería la misma línea dos veces."""

        from programas.selectors.auditoria_dispositivo import auditoria_del_dispositivo

        estadia = self._alojar()
        feed = auditoria_del_dispositivo(self.cis)
        titulos = [evento["titulo"] for evento in feed[0 : feed.count()]]

        self.assertEqual(titulos.count(f"Ingreso de {self.persona.apellido}, {self.persona.nombre}"), 1)
        self.assertEqual(EntradaBitacora.objects.filter(personas=estadia).count(), 1)


class NoSeCorrigenDesdeLaBitacoraTests(BaseAutomaticas):
    def test_corregir_una_novedad_automatica_se_rechaza(self):
        from programas.services.bitacora import corregir_entrada

        self._alojar()
        entrada = EntradaBitacora.objects.get(dispositivo=self.cis)
        corrector = self._operador("Bitacorista", self.cis, ("dispositivo.ver", "dispositivo.bitacora"))

        with self.assertRaises(ValidationError):
            corregir_entrada(entrada=entrada, usuario=corrector, texto="Otra cosa")

        self.assertEqual(EntradaBitacora.objects.count(), 1)


class LaEstadiaLasMuestraTests(BaseAutomaticas):
    def test_la_solapa_novedades_de_la_estadia_las_lista(self):
        """La novedad queda colgando de la estadía: es la persona involucrada."""

        from programas.selectors.estadia_detalle import novedades_de_estadia

        estadia = self._alojar(fecha_ingreso=timezone.now() - timedelta(days=1))
        cambiar_plaza(estadia=estadia, plaza=self.otra_plaza, usuario=self.operador_cis, motivo="Convivencia")

        filas = list(novedades_de_estadia(estadia))

        self.assertEqual([fila["categoria"] for fila in filas], ["Movimiento", "Ingreso"])
        self.assertEqual(filas[0]["texto"], "Cambio de plaza · P1 → P2 · motivo: Convivencia")


class SinPlazaTests(BaseAutomaticas):
    def test_un_ingreso_sin_plaza_lo_dice(self):
        self.tipo.plaza_obligatoria_al_ingresar = False
        self.tipo.tipos_plaza_admitidos = ""
        self.tipo.save()
        Plaza.objects.filter(sector__dispositivo=self.cis).delete()

        self._alojar(plaza=None)

        entrada = EntradaBitacora.objects.get(dispositivo=self.cis)
        self.assertEqual(entrada.texto, "Ingreso · sin plaza asignada")
        self.assertEqual(Estadia.objects.get(ciudadano=self.persona).plaza_id, None)
