"""Turnos y bitácora del dispositivo (MVP v2, etapa 3 · #695).

Lo que se verifica, en el orden de los criterios de aprobación:

1. **El turno vigente y la fecha operativa**, que va a consumir el censo (task 31):
   cambio de turno en el borde exacto, el nocturno que cruza la medianoche y pertenece
   al día en que empezó, la guardia de 24 h, el hueco entre turnos y la hora **local**
   (un momento en UTC del martes que en Resistencia todavía es lunes).
2. **Corregir no pisa.** La corrección es una fila nueva; la anterior conserva su texto y
   se sigue viendo. El manager no deja `update` ni `delete`, y `save()` sobre una fila
   guardada falla.
3. **Dos operadores no se pisan.** El que corrige una versión que otro ya corrigió recibe
   un error y no se pierde nada; y si alguien llegara sin pasar por el servicio, la base
   rechaza la segunda corrección de la misma versión.
4. **Autorización por capacidad y alcance**: `dispositivo.bitacora` para cargar,
   `dispositivo.editar` para configurar turnos, siempre con la asignación al dispositivo.
   Cada usuario de prueba tiene **todo menos** lo que el test prueba.

Ningún test depende del reloj: `timezone.now` se fija en cada caso.
"""

import shutil
import tempfile
from datetime import date, datetime, time, timedelta
from datetime import timezone as dt_timezone
from unittest import mock

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, models, transaction
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from core import rbac
from core.views.media import _autorizar
from legajos.models import Ciudadano
from programas.models import (
    AdjuntoBitacora,
    AsignacionDispositivo,
    Dispositivo,
    EntradaBitacora,
    Estadia,
    Programa,
    TipoDispositivo,
    Turno,
)
from programas.services.bitacora import (
    CORRECCION_CONCURRENTE,
    MAX_ADJUNTOS_POR_ENTRADA,
    PERSONAS_FUERA_DEL_TURNO,
    corregir_entrada,
    crear_turno,
    editar_turno,
    registrar_entrada,
    turno_vigente,
    turnos_del_dia,
)
from users.models import Capacidad, RolMeta

TODAS = ("dispositivo.ver", "dispositivo.admitir", "dispositivo.egresar", "dispositivo.editar", "dispositivo.bitacora")

#: El lunes 07/09/2026, en hora de Resistencia.
LUNES = date(2026, 9, 7)
MARTES = LUNES + timedelta(days=1)

PDF = b"%PDF-1.4\n%prueba\n"


def _local(dia, hora, minuto=0, segundo=0):
    return timezone.make_aware(datetime.combine(dia, time(hora, minuto, segundo)))


def _reloj(momento):
    """Fija `timezone.now()` en un momento: el servicio y los `auto_now` lo ven igual."""

    return mock.patch("django.utils.timezone.now", return_value=momento)


def _permiso(codigo):
    tipo = ContentType.objects.get_for_model(Capacidad)
    return Permission.objects.get(codename=rbac.codename_de(codigo), content_type=tipo)


def _turnos_cis():
    """Los tres del mockup P10, sin guardar: `turno_vigente` acepta la lista ya cargada."""

    return [
        Turno(nombre="Mañana", hora_desde=time(6), hora_hasta=time(14), orden=1),
        Turno(nombre="Tarde", hora_desde=time(14), hora_hasta=time(22), orden=2),
        Turno(nombre="Noche", hora_desde=time(22), hora_hasta=time(6), orden=3),
    ]


class TurnoVigenteTests(SimpleTestCase):
    """La función que el censo va a consumir. Sin base: los turnos van en memoria."""

    def setUp(self):
        self.turnos = _turnos_cis()

    def _vigente(self, momento, turnos=None):
        return turno_vigente(None, momento, turnos=self.turnos if turnos is None else turnos)

    def test_cambio_de_turno_en_el_borde_exacto(self):
        """`[inicio, fin)`: 13:59:59 es Mañana y 14:00 en punto ya es Tarde."""

        antes = self._vigente(_local(LUNES, 13, 59, 59))
        despues = self._vigente(_local(LUNES, 14))

        self.assertEqual(antes.turno.nombre, "Mañana")
        self.assertEqual(despues.turno.nombre, "Tarde")
        self.assertEqual(antes.fecha_operativa, LUNES)
        self.assertEqual(despues.fecha_operativa, LUNES)

    def test_el_nocturno_que_empieza_el_lunes_es_del_lunes_aunque_sea_martes(self):
        """El criterio de la task: martes 03:00 pertenece a la Noche del lunes."""

        for momento in (_local(LUNES, 22), _local(LUNES, 23, 59, 59), _local(MARTES, 0), _local(MARTES, 3)):
            with self.subTest(momento=momento):
                vigente = self._vigente(momento)
                self.assertEqual(vigente.turno.nombre, "Noche")
                self.assertEqual(vigente.fecha_operativa, LUNES)

    def test_a_las_seis_del_martes_empieza_el_dia_operativo_del_martes(self):
        ultima_de_la_noche = self._vigente(_local(MARTES, 5, 59, 59))
        primera_de_la_manana = self._vigente(_local(MARTES, 6))

        self.assertEqual((ultima_de_la_noche.turno.nombre, ultima_de_la_noche.fecha_operativa), ("Noche", LUNES))
        self.assertEqual((primera_de_la_manana.turno.nombre, primera_de_la_manana.fecha_operativa), ("Mañana", MARTES))

    def test_la_ventana_del_nocturno_termina_al_dia_siguiente(self):
        vigente = self._vigente(_local(MARTES, 3))

        self.assertEqual(vigente.inicio, _local(LUNES, 22))
        self.assertEqual(vigente.fin, _local(MARTES, 6))

    def test_se_calcula_en_hora_local_y_no_en_utc(self):
        """Resistencia está a UTC-3: la hora del reloj de la base no es la del turno.

        Martes 00:30 UTC es lunes 21:30 local: Tarde del lunes, no Noche. Y martes 08:00
        UTC son las 05:00 locales: todavía la Noche del lunes, no la Mañana del martes.
        """

        vigente = self._vigente(datetime(2026, 9, 8, 0, 30, tzinfo=dt_timezone.utc))
        self.assertEqual((vigente.turno.nombre, vigente.fecha_operativa), ("Tarde", LUNES))

        vigente = self._vigente(datetime(2026, 9, 8, 8, 0, tzinfo=dt_timezone.utc))
        self.assertEqual((vigente.turno.nombre, vigente.fecha_operativa), ("Noche", LUNES))

    def test_un_hueco_entre_turnos_no_tiene_turno_vigente(self):
        turnos = [Turno(nombre="Mañana", hora_desde=time(8), hora_hasta=time(12))]

        self.assertIsNone(self._vigente(_local(LUNES, 13), turnos=turnos))
        self.assertIsNone(self._vigente(_local(LUNES, 12), turnos=turnos), "el fin es abierto")
        self.assertIsNone(self._vigente(_local(LUNES, 13), turnos=[]))

    def test_la_guardia_de_24_horas_es_del_dia_en_que_empezo(self):
        turnos = [Turno(nombre="Guardia", hora_desde=time(8), hora_hasta=time(8))]

        antes = self._vigente(_local(MARTES, 7, 59), turnos=turnos)
        despues = self._vigente(_local(MARTES, 8), turnos=turnos)

        self.assertEqual(antes.fecha_operativa, LUNES)
        self.assertEqual(despues.fecha_operativa, MARTES)
        self.assertEqual((despues.inicio, despues.fin), (_local(MARTES, 8), _local(MARTES + timedelta(days=1), 8)))

    def test_los_turnos_del_dia_cubren_de_la_primera_hora_a_la_ultima(self):
        """El día operativo del lunes va del lunes 06:00 al martes 06:00, sin huecos."""

        situados = turnos_del_dia(None, LUNES, turnos=list(reversed(self.turnos)))

        self.assertEqual([s.turno.nombre for s in situados], ["Mañana", "Tarde", "Noche"])
        self.assertEqual(situados[0].inicio, _local(LUNES, 6))
        self.assertEqual(situados[-1].fin, _local(MARTES, 6))
        for anterior, siguiente in zip(situados, situados[1:], strict=False):
            self.assertEqual(anterior.fin, siguiente.inicio)


class BaseBitacora(TestCase):
    """Un programa, dos instituciones, los tres turnos del CIS y un operador por institución."""

    def setUp(self):
        super().setUp()
        cache.clear()
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)
        ajuste = override_settings(MEDIA_ROOT=self.media)
        ajuste.enable()
        self.addCleanup(ajuste.disable)

        self.programa, _ = Programa.objects.get_or_create(
            codigo="DISPOSITIVOS",
            defaults={"nombre": "Dispositivos", "tipo": Programa.TipoPrograma.DISPOSITIVOS},
        )
        self.tipo = TipoDispositivo.objects.create(codigo="ALBERGUE", nombre="Albergue")
        self.cis = self._dispositivo("CIS-3", "Centro integrador")
        self.parador = self._dispositivo("PAR-1", "Parador")
        for turno in _turnos_cis():
            turno.dispositivo = self.cis
            turno.save()
        self.manana, self.tarde, self.noche = Turno.objects.filter(dispositivo=self.cis).order_by("orden")
        self.persona = Ciudadano.objects.create(dni="30111222", nombre="Ana", apellido="Gómez")
        self.otra_persona = Ciudadano.objects.create(dni="30333444", nombre="Juan", apellido="Pérez")
        self.operador = self._operador("Operador CIS", self.cis)
        self.operador_parador = self._operador("Operador Parador", self.parador)

    def _dispositivo(self, codigo, nombre):
        return Dispositivo.objects.create(
            tipo=self.tipo, codigo=codigo, nombre=nombre, estado=Dispositivo.Estado.ACTIVO
        )

    def _operador(self, nombre, dispositivo, capacidades=TODAS):
        rol = Group.objects.create(name=nombre)
        RolMeta.objects.create(grupo=rol, categoria=rbac.CATEGORIA_PROGRAMA, programa=self.programa, activo=True)
        rol.permissions.add(*[_permiso(codigo) for codigo in capacidades])
        AsignacionDispositivo.objects.create(dispositivo=dispositivo, rol=rol, activo=True)
        usuario = User.objects.create_user(username=nombre.replace(" ", "_").lower(), password="x")
        usuario.groups.add(rol)
        return User.objects.get(pk=usuario.pk)

    def _estadia(self, persona, dispositivo, ingreso, egreso=None):
        return Estadia.objects.create(
            ciudadano=persona,
            dispositivo=dispositivo,
            fecha_ingreso=ingreso,
            fecha_egreso=egreso,
            estado=Estadia.Estado.EGRESADA if egreso else Estadia.Estado.ACTIVA,
            clave_alojamiento=None if egreso else Estadia.clave_para(persona),
        )

    def _cargar(self, ahora, **kwargs):
        datos = {
            "dispositivo": self.cis,
            "usuario": self.operador,
            "tipo": EntradaBitacora.Tipo.INCIDENTE,
            "texto": "Discusión en el comedor, sin lesiones.",
        }
        datos.update(kwargs)
        with _reloj(ahora):
            return registrar_entrada(**datos)

    def _corregir(self, ahora, entrada, **kwargs):
        datos = {"usuario": self.operador, "texto": "Discusión en el comedor entre dos residentes, sin lesiones."}
        datos.update(kwargs)
        with _reloj(ahora):
            return corregir_entrada(entrada=entrada, **datos)


class TurnoVigenteEnLaBaseTests(BaseBitacora):
    def test_sin_lista_lee_los_turnos_activos_del_dispositivo(self):
        vigente = turno_vigente(self.cis, _local(MARTES, 3))

        self.assertEqual(vigente.turno, self.noche)
        self.assertEqual(vigente.fecha_operativa, LUNES)

    def test_un_turno_dado_de_baja_no_rige(self):
        self.noche.activo = False
        self.noche.save()

        self.assertIsNone(turno_vigente(self.cis, _local(MARTES, 3)))

    def test_cada_dispositivo_tiene_sus_turnos(self):
        self.assertIsNone(turno_vigente(self.parador, _local(LUNES, 10)))


class ConfiguracionDeTurnosTests(BaseBitacora):
    def test_un_turno_superpuesto_no_entra(self):
        """El de 05 a 07 pisa el final de la Noche y el principio de la Mañana."""

        with self.assertRaises(ValidationError):
            crear_turno(
                dispositivo=self.cis,
                usuario=self.operador,
                nombre="Refuerzo",
                hora_desde=time(5),
                hora_hasta=time(7),
            )
        self.assertEqual(Turno.objects.filter(dispositivo=self.cis).count(), 3)

    def test_un_nocturno_superpuesto_con_otro_nocturno_no_entra(self):
        with self.assertRaises(ValidationError):
            crear_turno(
                dispositivo=self.cis,
                usuario=self.operador,
                nombre="Madrugada",
                hora_desde=time(23),
                hora_hasta=time(2),
            )

    def test_turnos_contiguos_conviven(self):
        turno = crear_turno(
            dispositivo=self.parador,
            usuario=self.operador_parador,
            nombre="Noche",
            hora_desde=time(20),
            hora_hasta=time(8),
        )
        crear_turno(
            dispositivo=self.parador,
            usuario=self.operador_parador,
            nombre="Día",
            hora_desde=time(8),
            hora_hasta=time(20),
        )

        self.assertTrue(turno.cruza_medianoche)
        self.assertEqual(turno_vigente(self.parador, _local(MARTES, 7, 59)).turno, turno)

    def test_cambiar_el_horario_vuelve_a_mirar_la_superposicion(self):
        with self.assertRaises(ValidationError):
            editar_turno(turno=self.tarde, usuario=self.operador, hora_hasta=time(23))

        self.tarde.refresh_from_db()
        self.assertEqual(self.tarde.hora_hasta, time(22))

    def test_dar_de_baja_un_turno_deja_lugar_para_otro(self):
        editar_turno(turno=self.noche, usuario=self.operador, activo=False)

        nuevo = crear_turno(
            dispositivo=self.cis, usuario=self.operador, nombre="Noche corta", hora_desde=time(22), hora_hasta=time(2)
        )

        self.assertEqual(turno_vigente(self.cis, _local(MARTES, 1)).turno, nuevo)

    def test_configurar_turnos_exige_editar(self):
        """Todo menos `dispositivo.editar`, con la asignación al dispositivo."""

        sin_editar = self._operador("Sin editar", self.cis, tuple(c for c in TODAS if c != "dispositivo.editar"))

        with self.assertRaises(PermissionDenied):
            crear_turno(
                dispositivo=self.cis, usuario=sin_editar, nombre="Extra", hora_desde=time(2), hora_hasta=time(3)
            )
        with self.assertRaises(PermissionDenied):
            editar_turno(turno=self.tarde, usuario=sin_editar, activo=False)

    def test_configurar_turnos_exige_alcance_sobre_el_dispositivo(self):
        """El operador del parador tiene `editar`, pero no está asignado al CIS."""

        with self.assertRaises(PermissionDenied):
            editar_turno(turno=self.tarde, usuario=self.operador_parador, activo=False)


class RegistrarEntradaTests(BaseBitacora):
    def test_la_novedad_queda_en_el_turno_y_la_fecha_operativa_del_momento(self):
        """Cargada el martes 03:00: Noche del lunes."""

        entrada = self._cargar(_local(MARTES, 3))

        self.assertEqual(entrada.turno, self.noche)
        self.assertEqual(entrada.fecha_operativa, LUNES)
        self.assertEqual(entrada.version, 1)
        self.assertEqual(entrada.responsable, self.operador)
        self.assertEqual(entrada.origen, EntradaBitacora.Origen.MANUAL)

    def test_se_puede_anotar_despues_algo_que_paso_antes_en_el_mismo_turno(self):
        entrada = self._cargar(_local(LUNES, 16, 52), momento=_local(LUNES, 16, 10))

        self.assertEqual(entrada.momento, _local(LUNES, 16, 10))
        self.assertEqual(entrada.turno, self.tarde)

    def test_una_novedad_de_un_turno_anterior_es_regularizar_y_no_entra(self):
        """A las 14:00 empezó la Tarde: lo de las 13:50 es de la Mañana, que ya cerró."""

        with self.assertRaises(ValidationError):
            self._cargar(_local(LUNES, 14, 5), momento=_local(LUNES, 13, 50))
        self.assertFalse(EntradaBitacora.objects.exists())

    def test_el_mismo_horario_de_otro_dia_tampoco_entra(self):
        with self.assertRaises(ValidationError):
            self._cargar(_local(MARTES, 16), momento=_local(LUNES, 16))

    def test_una_novedad_futura_no_entra(self):
        with self.assertRaises(ValidationError):
            self._cargar(_local(LUNES, 16), momento=_local(LUNES, 16, 30))

    def test_sin_turno_configurado_no_hay_bitacora(self):
        with self.assertRaises(ValidationError):
            self._cargar(_local(LUNES, 16), dispositivo=self.parador, usuario=self.operador_parador)

    def test_un_tipo_automatico_no_se_carga_a_mano(self):
        with self.assertRaises(ValidationError):
            self._cargar(_local(LUNES, 16), tipo=EntradaBitacora.Tipo.INGRESO)

    def test_sin_texto_no_entra(self):
        with self.assertRaises(ValidationError):
            self._cargar(_local(LUNES, 16), texto="   ")

    def test_cargar_exige_la_capacidad_de_bitacora(self):
        """Todo menos `dispositivo.bitacora`, asignado al CIS: ni `admitir` ni `editar` alcanzan."""

        sin_bitacora = self._operador("Sin bitacora", self.cis, tuple(c for c in TODAS if c != "dispositivo.bitacora"))

        with self.assertRaises(PermissionDenied):
            self._cargar(_local(LUNES, 16), usuario=sin_bitacora)

    def test_cargar_exige_alcance_sobre_el_dispositivo(self):
        """El operador del parador tiene la capacidad, pero no la asignación al CIS."""

        with self.assertRaises(PermissionDenied):
            self._cargar(_local(LUNES, 16), usuario=self.operador_parador)

    def test_las_personas_son_estadias_de_aca_abiertas_en_ese_momento(self):
        alojada = self._estadia(self.persona, self.cis, _local(LUNES, 9))

        entrada = self._cargar(_local(LUNES, 16), personas=[alojada])

        self.assertEqual(list(entrada.personas.all()), [alojada])
        self.assertEqual(entrada.personas.get().ciudadano, self.persona)

    def test_una_persona_de_otro_dispositivo_no_se_involucra(self):
        ajena = self._estadia(self.otra_persona, self.parador, _local(LUNES, 9))

        with self.assertRaisesMessage(ValidationError, PERSONAS_FUERA_DEL_TURNO):
            self._cargar(_local(LUNES, 16), personas=[ajena])
        self.assertFalse(EntradaBitacora.objects.exists())

    def test_una_persona_que_ya_habia_egresado_no_se_involucra(self):
        egresada = self._estadia(self.persona, self.cis, _local(LUNES, 8), egreso=_local(LUNES, 15))

        with self.assertRaisesMessage(ValidationError, PERSONAS_FUERA_DEL_TURNO):
            self._cargar(_local(LUNES, 16), personas=[egresada])

    def test_los_adjuntos_se_guardan_en_su_prefijo_y_cuelgan_de_la_entrada(self):
        acta = SimpleUploadedFile("acta.pdf", PDF, content_type="application/pdf")

        entrada = self._cargar(_local(LUNES, 16), adjuntos=[acta])

        adjunto = entrada.adjuntos.get()
        self.assertTrue(adjunto.archivo.name.startswith("dispositivos/bitacora/"))
        self.assertNotIn("acta", adjunto.archivo.name, "el nombre en disco es opaco")
        self.assertEqual(adjunto.nombre_original, "acta.pdf")
        self.assertEqual(adjunto.dispositivo, self.cis)

    def test_un_adjunto_no_permitido_no_deja_nada(self):
        script = SimpleUploadedFile("acta.html", b"<script></script>", content_type="text/html")

        with self.assertRaises(ValidationError):
            self._cargar(_local(LUNES, 16), adjuntos=[script])
        self.assertFalse(EntradaBitacora.objects.exists())
        self.assertFalse(AdjuntoBitacora.objects.exists())


class CorreccionTests(BaseBitacora):
    def test_corregir_agrega_una_version_y_la_anterior_sigue_visible(self):
        original = self._cargar(_local(LUNES, 16, 10))
        texto_original = original.texto

        corregida = self._corregir(_local(LUNES, 16, 30), original, motivo="Faltaba quiénes")

        original.refresh_from_db()
        self.assertEqual(original.texto, texto_original, "la versión anterior no se toca")
        self.assertEqual(corregida.version, 2)
        self.assertEqual(corregida.entrada_original, original)
        self.assertEqual(corregida.version_anterior, original)
        self.assertEqual(list(original.versiones()), [original, corregida])
        self.assertEqual(list(corregida.versiones()), [original, corregida])
        self.assertEqual(list(EntradaBitacora.objects.vigentes()), [corregida])
        self.assertEqual(EntradaBitacora.objects.count(), 2)

    def test_la_correccion_conserva_cuando_paso_y_hereda_personas_y_adjuntos(self):
        alojada = self._estadia(self.persona, self.cis, _local(LUNES, 9))
        acta = SimpleUploadedFile("acta.pdf", PDF, content_type="application/pdf")
        original = self._cargar(_local(LUNES, 16, 10), personas=[alojada], adjuntos=[acta])

        corregida = self._corregir(_local(LUNES, 17), original)

        self.assertEqual(
            (corregida.momento, corregida.turno, corregida.fecha_operativa),
            (original.momento, original.turno, original.fecha_operativa),
        )
        self.assertEqual(list(corregida.personas.all()), [alojada])
        self.assertEqual(list(corregida.adjuntos.all()), list(original.adjuntos.all()))

    def test_quitar_un_adjunto_lo_saca_de_la_version_nueva_y_no_de_la_anterior(self):
        acta = SimpleUploadedFile("acta.pdf", PDF, content_type="application/pdf")
        original = self._cargar(_local(LUNES, 16, 10), adjuntos=[acta])
        adjunto = original.adjuntos.get()

        corregida = self._corregir(_local(LUNES, 17), original, quitar_adjuntos=[adjunto])

        self.assertFalse(corregida.adjuntos.exists())
        self.assertEqual(list(original.adjuntos.all()), [adjunto])

    def test_la_correccion_de_la_correccion_sigue_la_cadena(self):
        v1 = self._cargar(_local(LUNES, 16, 10))
        v2 = self._corregir(_local(LUNES, 16, 20), v1)
        v3 = self._corregir(_local(LUNES, 16, 30), v2, texto="Tercera redacción.")

        self.assertEqual((v3.version, v3.entrada_original, v3.version_anterior), (3, v1, v2))
        self.assertEqual(list(v1.versiones()), [v1, v2, v3])
        self.assertEqual(list(EntradaBitacora.objects.vigentes()), [v3])

    def test_dos_operadores_que_corrigen_la_misma_version_no_se_pisan(self):
        """Los dos tenían delante la versión 1. El primero gana; el segundo se entera."""

        companera = self._operador("Companera CIS", self.cis)
        original = self._cargar(_local(LUNES, 16, 10))
        vista_por_los_dos = EntradaBitacora.objects.get(pk=original.pk)

        primera = self._corregir(_local(LUNES, 16, 20), vista_por_los_dos, texto="La versión del primero.")
        with self.assertRaisesMessage(ValidationError, CORRECCION_CONCURRENTE):
            self._corregir(_local(LUNES, 16, 21), vista_por_los_dos, usuario=companera, texto="La del segundo.")

        self.assertEqual(EntradaBitacora.objects.count(), 2)
        primera.refresh_from_db()
        self.assertEqual(primera.texto, "La versión del primero.")
        self.assertEqual(list(EntradaBitacora.objects.vigentes()), [primera])

    def test_corregir_fuera_del_turno_en_curso_es_regularizar_y_no_entra(self):
        original = self._cargar(_local(LUNES, 13))

        with self.assertRaises(ValidationError):
            self._corregir(_local(LUNES, 14, 30), original)
        self.assertEqual(EntradaBitacora.objects.count(), 1)

    def test_corregir_exige_la_capacidad_de_bitacora(self):
        sin_bitacora = self._operador("Sin bitacora", self.cis, tuple(c for c in TODAS if c != "dispositivo.bitacora"))
        original = self._cargar(_local(LUNES, 16, 10))

        with self.assertRaises(PermissionDenied):
            self._corregir(_local(LUNES, 16, 30), original, usuario=sin_bitacora)

    def test_corregir_exige_alcance_sobre_el_dispositivo(self):
        original = self._cargar(_local(LUNES, 16, 10))

        with self.assertRaises(PermissionDenied):
            self._corregir(_local(LUNES, 16, 30), original, usuario=self.operador_parador)

    def test_una_novedad_automatica_no_se_corrige_desde_la_bitacora(self):
        automatica = EntradaBitacora.objects.create(
            dispositivo=self.cis,
            turno=self.tarde,
            fecha_operativa=LUNES,
            momento=_local(LUNES, 16, 48),
            responsable=self.operador,
            tipo=EntradaBitacora.Tipo.INGRESO,
            origen=EntradaBitacora.Origen.AUTOMATICA,
            texto="Ingreso · plaza B-03",
        )

        with self.assertRaises(ValidationError):
            self._corregir(_local(LUNES, 17), automatica)


class NadaSePisaTests(BaseBitacora):
    """El texto nunca se actualiza: ni por la fila, ni por el manager, ni en masa."""

    def setUp(self):
        super().setUp()
        self.entrada = self._cargar(_local(LUNES, 16, 10))

    def test_guardar_una_entrada_ya_guardada_falla(self):
        self.entrada.texto = "Otra cosa."

        with self.assertRaises(ValidationError):
            self.entrada.save()
        self.assertEqual(
            EntradaBitacora.objects.get(pk=self.entrada.pk).texto, "Discusión en el comedor, sin lesiones."
        )

    def test_el_manager_no_actualiza_ni_borra(self):
        with self.assertRaises(ValidationError):
            EntradaBitacora.objects.filter(pk=self.entrada.pk).update(texto="Otra cosa.")
        with self.assertRaises(ValidationError):
            EntradaBitacora.objects.filter(pk=self.entrada.pk).delete()
        with self.assertRaises(ValidationError):
            EntradaBitacora.objects.bulk_update([self.entrada], ["texto"])
        with self.assertRaises(ValidationError):
            self.entrada.delete()
        self.assertTrue(EntradaBitacora.objects.filter(pk=self.entrada.pk).exists())


class GarantiasDeLaBaseTests(BaseBitacora):
    """La red de abajo: lo que rechaza el motor aunque alguien no pase por el servicio."""

    def _version(self, anterior, numero, **kwargs):
        datos = {
            "dispositivo": self.cis,
            "turno": self.tarde,
            "fecha_operativa": LUNES,
            "momento": anterior.momento,
            "responsable": self.operador,
            "tipo": anterior.tipo,
            "texto": f"Versión {numero}",
            "version": numero,
            "entrada_original": anterior.entrada_original or anterior,
            "version_anterior": anterior,
        }
        datos.update(kwargs)
        return EntradaBitacora.objects.create(**datos)

    def test_una_version_no_se_corrige_dos_veces(self):
        """El UNIQUE de `version_anterior`, con el número de versión distinto para que no lo tape el otro."""

        original = self._cargar(_local(LUNES, 16, 10))
        self._version(original, 2)

        with self.assertRaises(IntegrityError), transaction.atomic():
            self._version(original, 3)

    def test_el_numero_de_version_no_se_repite_en_la_cadena(self):
        original = self._cargar(_local(LUNES, 16, 10))
        v2 = self._version(original, 2)
        v3 = self._version(v2, 3)

        with self.assertRaises(IntegrityError), transaction.atomic():
            self._version(v3, 2)

    def test_una_correccion_sin_su_cadena_no_entra(self):
        original = self._cargar(_local(LUNES, 16, 10))

        with self.assertRaises(IntegrityError), transaction.atomic():
            self._version(original, 2, entrada_original=None)

    def test_ningun_unique_de_la_bitacora_es_condicional(self):
        """Un `condition=` acá pasaría en SQLite y no existiría en MySQL ni en MariaDB."""

        for modelo in (Turno, EntradaBitacora):
            for constraint in modelo._meta.constraints:
                if isinstance(constraint, models.UniqueConstraint):
                    with self.subTest(constraint=constraint.name):
                        self.assertIsNone(constraint.condition)
        self.assertTrue(EntradaBitacora._meta.get_field("version_anterior").unique)


class MediaDeLaBitacoraTests(BaseBitacora):
    """El acta la baja quien ve **ese** dispositivo; el de otra institución, no."""

    def setUp(self):
        super().setUp()
        acta = SimpleUploadedFile("acta.pdf", PDF, content_type="application/pdf")
        self.ruta = self._cargar(_local(LUNES, 16), adjuntos=[acta]).adjuntos.get().archivo.name

    def test_quien_opera_el_dispositivo_baja_el_acta(self):
        self.assertIs(_autorizar(self.operador, self.ruta), True)

    def test_el_operador_de_otra_institucion_no(self):
        self.assertIs(_autorizar(self.operador_parador, self.ruta), False)

    def test_sin_ver_no_la_baja_aunque_cargue_la_bitacora(self):
        sin_ver = self._operador("Sin ver", self.cis, tuple(c for c in TODAS if c != "dispositivo.ver"))

        self.assertIs(_autorizar(sin_ver, self.ruta), False)

    def test_un_archivo_sin_fila_no_tiene_duenio(self):
        self.assertIsNone(_autorizar(self.operador, "dispositivos/bitacora/2026/09/inexistente.pdf"))


def _pdf(nombre="acta.pdf"):
    return SimpleUploadedFile(nombre, PDF, content_type="application/pdf")


class RelacionesInmutablesTests(BaseBitacora):
    """Revisión de #827: una versión guardada tampoco cambia sus personas ni sus adjuntos."""

    def setUp(self):
        super().setUp()
        self.alojada = self._estadia(self.persona, self.cis, _local(LUNES, 9))
        self.otra = self._estadia(self.otra_persona, self.cis, _local(LUNES, 10))
        self.entrada = self._cargar(_local(LUNES, 16, 10), personas=[self.alojada], adjuntos=[_pdf()])

    def test_las_personas_de_una_version_guardada_no_cambian(self):
        for cambio in (
            lambda: self.entrada.personas.add(self.otra),
            lambda: self.entrada.personas.remove(self.alojada),
            lambda: self.entrada.personas.clear(),
            lambda: self.entrada.personas.set([self.otra]),
            lambda: self.otra.entradas_bitacora.add(self.entrada),
        ):
            with self.subTest(cambio=cambio), self.assertRaises(ValidationError), transaction.atomic():
                cambio()
        self.assertEqual(list(EntradaBitacora.objects.get(pk=self.entrada.pk).personas.all()), [self.alojada])

    def test_los_adjuntos_de_una_version_guardada_no_cambian(self):
        adjunto = self.entrada.adjuntos.get()
        otro = AdjuntoBitacora.objects.create(dispositivo=self.cis, archivo=_pdf("otra.pdf"))

        for cambio in (
            lambda: self.entrada.adjuntos.add(otro),
            lambda: self.entrada.adjuntos.remove(adjunto),
            lambda: self.entrada.adjuntos.clear(),
            lambda: adjunto.entradas.clear(),
        ):
            with self.subTest(cambio=cambio), self.assertRaises(ValidationError), transaction.atomic():
                cambio()
        self.assertEqual(list(self.entrada.adjuntos.all()), [adjunto])

    def test_el_servicio_si_las_escribe_al_crear_la_version(self):
        corregida = self._corregir(_local(LUNES, 16, 30), self.entrada, personas=[self.alojada, self.otra])

        self.assertEqual(set(corregida.personas.all()), {self.alojada, self.otra})
        self.assertEqual(corregida.adjuntos.count(), 1)
        self.assertFalse(corregida._relaciones_abiertas, "la marca no queda puesta después de crear")


class CorreccionRevisionTests(BaseBitacora):
    """Revisión de #827: dispositivo activo, turno guardado, ids de personas y tope de adjuntos."""

    def test_no_se_corrige_en_un_dispositivo_que_ya_no_esta_activo(self):
        original = self._cargar(_local(LUNES, 16, 10))
        Dispositivo.objects.filter(pk=self.cis.pk).update(estado=Dispositivo.Estado.INACTIVO)

        with self.assertRaises(ValidationError):
            self._corregir(_local(LUNES, 16, 30), original)
        self.assertEqual(EntradaBitacora.objects.count(), 1)

    def test_si_cambian_los_turnos_no_se_corrige_lo_de_un_turno_que_ya_termino(self):
        """La Tarde se parte en dos a las 16:00. Lo de las 16:10 quedó guardado en la Tarde,
        que terminó: recalcular desde el momento lo ubicaría en el Vespertino en curso."""

        original = self._cargar(_local(LUNES, 16, 10))
        editar_turno(turno=self.tarde, usuario=self.operador, hora_hasta=time(16))
        crear_turno(
            dispositivo=self.cis, usuario=self.operador, nombre="Vespertino", hora_desde=time(16), hora_hasta=time(22)
        )

        with self.assertRaises(ValidationError):
            self._corregir(_local(LUNES, 16, 30), original)
        self.assertEqual(EntradaBitacora.objects.count(), 1)

    def test_si_cambia_el_horario_del_turno_en_curso_lo_suyo_se_sigue_corrigiendo(self):
        """La Tarde pasa a empezar 16:20. Lo de las 16:10 sigue guardado en la Tarde de hoy."""

        original = self._cargar(_local(LUNES, 16, 10))
        editar_turno(turno=self.tarde, usuario=self.operador, hora_desde=time(16, 20))

        corregida = self._corregir(_local(LUNES, 16, 30), original)

        self.assertEqual((corregida.turno, corregida.fecha_operativa), (self.tarde, LUNES))

    def test_el_mismo_turno_de_otro_dia_no_corrige(self):
        """Revisión de #827: Tarde del lunes 16:10, corregida el martes 16:30 —también Tarde—.

        Es la condición `fecha_operativa` del turno en curso: el turno coincide, el día no.
        """

        original = self._cargar(_local(LUNES, 16, 10))

        with self.assertRaises(ValidationError):
            self._corregir(_local(MARTES, 16, 30), original)
        self.assertEqual(EntradaBitacora.objects.count(), 1)

    def test_la_noche_de_otro_dia_tampoco_corrige(self):
        """Noche del lunes 23:00 corregida el martes 23:00: Noche las dos, de fechas operativas distintas."""

        original = self._cargar(_local(LUNES, 23))

        with self.assertRaises(ValidationError):
            self._corregir(_local(MARTES, 23), original)
        self.assertEqual(EntradaBitacora.objects.count(), 1)

    def test_los_ids_de_personas_como_texto_son_la_misma_estadia(self):
        alojada = self._estadia(self.persona, self.cis, _local(LUNES, 9))

        entrada = self._cargar(_local(LUNES, 16), personas=[str(alojada.pk), alojada.pk, f" {alojada.pk} "])

        self.assertEqual(list(entrada.personas.all()), [alojada])

    def test_un_id_de_persona_que_no_es_numero_es_un_error_de_validacion(self):
        for invalido in ("abc", None, "1.5"):
            with self.subTest(invalido=invalido), self.assertRaisesMessage(ValidationError, PERSONAS_FUERA_DEL_TURNO):
                self._cargar(_local(LUNES, 16), personas=[invalido])
        self.assertFalse(EntradaBitacora.objects.exists())

    def test_una_novedad_no_lleva_mas_del_tope_de_adjuntos(self):
        archivos = [_pdf(f"acta{numero}.pdf") for numero in range(MAX_ADJUNTOS_POR_ENTRADA + 1)]

        with self.assertRaises(ValidationError):
            self._cargar(_local(LUNES, 16), adjuntos=archivos)
        self.assertFalse(AdjuntoBitacora.objects.exists())

    def test_la_correccion_suma_los_heredados_al_tope(self):
        original = self._cargar(
            _local(LUNES, 16), adjuntos=[_pdf(f"acta{n}.pdf") for n in range(MAX_ADJUNTOS_POR_ENTRADA)]
        )

        with self.assertRaises(ValidationError):
            self._corregir(_local(LUNES, 16, 30), original, adjuntos_nuevos=[_pdf("una.pdf")])
        corregida = self._corregir(
            _local(LUNES, 16, 31),
            original,
            adjuntos_nuevos=[_pdf("una.pdf")],
            quitar_adjuntos=[original.adjuntos.first()],
        )
        self.assertEqual(corregida.adjuntos.count(), MAX_ADJUNTOS_POR_ENTRADA)
