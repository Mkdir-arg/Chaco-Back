"""Estadía, clave de alojamiento y reserva de plaza (MVP v2, etapa 2 · #689).

Cuatro cosas se verifican acá, y cada una existe por un motivo distinto:

1. **La clave de alojamiento es una garantía del motor, no una consulta.** Hay un test
   que demuestra, con el generador de SQL de Django, que la forma «natural» de escribir
   esta regla —un `UniqueConstraint` con `condition=`— **no emite nada** en MySQL ni en
   MariaDB, y que la que está escrita sí. Sin ese test, el día que alguien «mejore» el
   modelo con un constraint condicional, la suite sigue verde y producción se queda sin
   la regla.
2. **Los bordes de fechas y de plaza ocupada**, que son los criterios de aprobación.
3. **La frontera de la verificación entre instituciones**: quien no tiene alcance sobre
   el dispositivo donde está la persona se entera de que la estadía existe y de nada más.
4. **`FUERA_SERVICIO` no se declara sobre una plaza tomada** (regla 1 de la etapa 2).
"""

from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, models, transaction
from django.db.backends.mysql.features import DatabaseFeatures as FeaturesMySQL
from django.test import TestCase
from django.utils import timezone

from core import rbac
from legajos.models import Ciudadano
from programas.models import (
    AsignacionDispositivo,
    Dispositivo,
    Estadia,
    MotivoEgreso,
    Plaza,
    Programa,
    ReservaPlaza,
    Sector,
    TipoDispositivo,
    TrazaDispositivo,
)
from programas.services.estadias import (
    AlojamientoEnLaRed,
    VerificacionAlojamiento,
    egresar_persona,
    ingresar_persona,
    liberar_reserva,
    reservar_plaza,
    sacar_plaza_de_servicio,
    verificar_alojamiento_en_red,
    volver_plaza_a_servicio,
)
from users.models import Capacidad, RolMeta

CAPACIDADES_OPERATIVAS = ("dispositivo.ver", "dispositivo.admitir", "dispositivo.egresar", "dispositivo.editar")


def _permiso(codigo):
    tipo = ContentType.objects.get_for_model(Capacidad)
    return Permission.objects.get(codename=rbac.codename_de(codigo), content_type=tipo)


class BaseEstadias(TestCase):
    """El terreno mínimo: un programa, dos instituciones y un operador por cada una."""

    def setUp(self):
        super().setUp()
        cache.clear()
        self.programa, _ = Programa.objects.get_or_create(
            codigo="DISPOSITIVOS",
            defaults={"nombre": "Dispositivos", "tipo": Programa.TipoPrograma.DISPOSITIVOS},
        )
        self.tipo = TipoDispositivo.objects.create(codigo="ALBERGUE", nombre="Albergue")
        self.cis = self._dispositivo("CIS-3", "Centro integrador")
        self.parador = self._dispositivo("PAR-1", "Parador")
        self.sector = Sector.objects.create(dispositivo=self.cis, nombre="Varones", capacidad=4)
        self.plaza = Plaza.objects.create(sector=self.sector, codigo="P1")
        self.otra_plaza = Plaza.objects.create(sector=self.sector, codigo="P2")
        self.sector_parador = Sector.objects.create(dispositivo=self.parador, nombre="General", capacidad=2)
        self.plaza_parador = Plaza.objects.create(sector=self.sector_parador, codigo="G1")
        # El egreso exige un motivo del catálogo, y lo exige el servicio: el terreno mínimo
        # trae uno para que no haya que crearlo en cada test que egresa a alguien.
        self.motivo_alta = MotivoEgreso.objects.create(codigo="alta", nombre="Alta", orden=1)
        self.persona = Ciudadano.objects.create(dni="30111222", nombre="Ana", apellido="Gómez")
        self.otra_persona = Ciudadano.objects.create(dni="30333444", nombre="Juan", apellido="Pérez")
        self.operador_cis = self._operador("Operador CIS", self.cis)
        self.operador_parador = self._operador("Operador Parador", self.parador)

    def _dispositivo(self, codigo, nombre):
        return Dispositivo.objects.create(
            tipo=self.tipo,
            codigo=codigo,
            nombre=nombre,
            estado=Dispositivo.Estado.ACTIVO,
            responsable_nombre=f"Responsable de {nombre}",
        )

    def _operador(self, nombre, dispositivo, capacidades=CAPACIDADES_OPERATIVAS):
        rol = Group.objects.create(name=nombre)
        RolMeta.objects.create(
            grupo=rol,
            categoria=rbac.CATEGORIA_PROGRAMA,
            programa=self.programa,
            activo=True,
        )
        rol.permissions.add(*[_permiso(codigo) for codigo in capacidades])
        AsignacionDispositivo.objects.create(dispositivo=dispositivo, rol=rol, activo=True)
        usuario = User.objects.create_user(username=nombre.replace(" ", "_").lower(), password="x")
        usuario.groups.add(rol)
        return User.objects.get(pk=usuario.pk)

    def _usuario(self, pk):
        """Recarga el usuario: `rbac` memoiza las capacidades en el objeto."""

        return User.objects.get(pk=pk)


class ClaveDeAlojamientoTests(BaseEstadias):
    def test_el_constraint_condicional_no_existe_en_mysql_ni_en_mariadb(self):
        """El motivo por el que la clave es una columna y no un `condition=`.

        Se compila el SQL de los dos constraints con el generador de Django, sin base:
        el condicional no emite **nada** en MySQL/MariaDB —`_create_unique_sql` devuelve
        `None` cuando `supports_partial_indexes` es `False`— y el de la clave emite su
        `UNIQUE`. En SQLite, el motor de esta misma suite, el condicional **sí** se crea:
        por eso un test que solo midiera el comportamiento pasaría en verde mientras la
        regla no existe en producción.
        """

        self.assertFalse(FeaturesMySQL.supports_partial_indexes, "MySQL y MariaDB no tienen índices parciales")

        unico = next(c for c in Estadia._meta.constraints if isinstance(c, models.UniqueConstraint))
        self.assertEqual(unico.fields, ("clave_alojamiento",))
        self.assertIsNone(unico.condition, "Un UNIQUE condicional sobre la estadía no existiría en producción")

    def test_dos_estadias_cerradas_de_la_misma_persona_conviven(self):
        """El UNIQUE es sobre una columna anulable: los `NULL` no chocan entre sí."""

        ahora = timezone.now()
        for dias in (10, 5):
            Estadia.objects.create(
                ciudadano=self.persona,
                dispositivo=self.cis,
                fecha_ingreso=ahora - timedelta(days=dias),
                fecha_egreso=ahora - timedelta(days=dias - 1),
                estado=Estadia.Estado.EGRESADA,
                clave_alojamiento=None,
            )

        self.assertEqual(Estadia.objects.filter(ciudadano=self.persona).count(), 2)

    def test_una_segunda_estadia_abierta_de_la_misma_persona_la_rechaza_la_base(self):
        Estadia.objects.create(
            ciudadano=self.persona,
            dispositivo=self.cis,
            fecha_ingreso=timezone.now(),
            clave_alojamiento=Estadia.clave_para(self.persona),
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            Estadia.objects.create(
                ciudadano=self.persona,
                dispositivo=self.parador,
                fecha_ingreso=timezone.now(),
                clave_alojamiento=Estadia.clave_para(self.persona),
            )

    def test_una_estadia_abierta_sin_clave_no_entra(self):
        """Sin esto, soltar la clave sin cerrar la estadía escondería a la persona."""

        with self.assertRaises(IntegrityError), transaction.atomic():
            Estadia.objects.create(
                ciudadano=self.persona,
                dispositivo=self.cis,
                fecha_ingreso=timezone.now(),
                clave_alojamiento=None,
            )

    def test_el_egreso_anterior_al_ingreso_lo_rechaza_la_base(self):
        ahora = timezone.now()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Estadia.objects.create(
                ciudadano=self.persona,
                dispositivo=self.cis,
                fecha_ingreso=ahora,
                fecha_egreso=ahora - timedelta(hours=1),
                estado=Estadia.Estado.EGRESADA,
                clave_alojamiento=None,
            )


class IngresoTests(BaseEstadias):
    def test_el_ingreso_abre_la_estadia_con_su_clave_y_deja_traza(self):
        estadia = ingresar_persona(
            ciudadano=self.persona,
            dispositivo=self.cis,
            plaza=self.plaza,
            usuario=self.operador_cis,
        )

        self.assertTrue(estadia.activa)
        self.assertEqual(estadia.clave_alojamiento, f"CIU-{self.persona.pk}")
        self.assertEqual(estadia.plaza_id, self.plaza.pk)
        self.assertEqual(estadia.ingresada_por_id, self.operador_cis.pk)
        traza = TrazaDispositivo.objects.filter(dispositivo=self.cis, accion="ESTADIA_INGRESO").get()
        self.assertIn(f"ciudadano {self.persona.pk}", traza.detalle)
        self.assertNotIn(self.persona.apellido, traza.detalle)

    def test_no_se_puede_alojar_a_alguien_que_ya_tiene_estadia_abierta_en_otro_dispositivo(self):
        ingresar_persona(
            ciudadano=self.persona,
            dispositivo=self.cis,
            plaza=self.plaza,
            usuario=self.operador_cis,
        )

        with self.assertRaises(AlojamientoEnLaRed) as capturado:
            ingresar_persona(
                ciudadano=self.persona,
                dispositivo=self.parador,
                plaza=self.plaza_parador,
                usuario=self.operador_parador,
            )

        self.assertTrue(capturado.exception.verificacion.alojada)
        self.assertEqual(Estadia.objects.activas().count(), 1)

    def test_una_plaza_ocupada_no_se_vuelve_a_dar(self):
        ingresar_persona(
            ciudadano=self.persona,
            dispositivo=self.cis,
            plaza=self.plaza,
            usuario=self.operador_cis,
        )

        with self.assertRaises(ValidationError) as capturado:
            ingresar_persona(
                ciudadano=self.otra_persona,
                dispositivo=self.cis,
                plaza=self.plaza,
                usuario=self.operador_cis,
            )

        self.assertIn("una estadía activa", str(capturado.exception))

    def test_una_plaza_fuera_de_servicio_no_recibe_a_nadie(self):
        Plaza.objects.filter(pk=self.plaza.pk).update(
            estado=Plaza.Estado.FUERA_SERVICIO, motivo_fuera_servicio="Refacción"
        )

        with self.assertRaises(ValidationError):
            ingresar_persona(
                ciudadano=self.persona,
                dispositivo=self.cis,
                plaza=Plaza.objects.get(pk=self.plaza.pk),
                usuario=self.operador_cis,
            )

    def test_la_plaza_tiene_que_ser_del_dispositivo(self):
        with self.assertRaises(ValidationError):
            ingresar_persona(
                ciudadano=self.persona,
                dispositivo=self.cis,
                plaza=self.plaza_parador,
                usuario=self.operador_cis,
            )

    def test_el_tipo_que_exige_plaza_no_deja_ingresar_sin_ella(self):
        TipoDispositivo.objects.filter(pk=self.tipo.pk).update(plaza_obligatoria_al_ingresar=True)

        with self.assertRaises(ValidationError):
            ingresar_persona(
                ciudadano=self.persona,
                dispositivo=Dispositivo.objects.get(pk=self.cis.pk),
                usuario=self.operador_cis,
            )

    def test_el_ingreso_no_puede_ser_futuro(self):
        with self.assertRaises(ValidationError):
            ingresar_persona(
                ciudadano=self.persona,
                dispositivo=self.cis,
                plaza=self.plaza,
                usuario=self.operador_cis,
                fecha_ingreso=timezone.now() + timedelta(hours=2),
            )

    def test_un_dispositivo_que_no_esta_activo_no_aloja(self):
        Dispositivo.objects.filter(pk=self.cis.pk).update(estado=Dispositivo.Estado.OBSERVADO)

        with self.assertRaises(ValidationError):
            ingresar_persona(
                ciudadano=self.persona,
                dispositivo=Dispositivo.objects.get(pk=self.cis.pk),
                plaza=self.plaza,
                usuario=self.operador_cis,
            )

    def test_sin_alcance_sobre_el_dispositivo_no_se_aloja(self):
        with self.assertRaises(PermissionDenied):
            ingresar_persona(
                ciudadano=self.persona,
                dispositivo=self.cis,
                plaza=self.plaza,
                usuario=self.operador_parador,
            )


class EgresoTests(BaseEstadias):
    def setUp(self):
        super().setUp()
        self.estadia = ingresar_persona(
            ciudadano=self.persona,
            dispositivo=self.cis,
            plaza=self.plaza,
            usuario=self.operador_cis,
            fecha_ingreso=timezone.now() - timedelta(days=2),
        )

    def test_el_egreso_suelta_la_clave_y_devuelve_a_la_persona_a_la_red(self):
        egresar_persona(estadia=self.estadia, usuario=self.operador_cis, motivo_egreso=self.motivo_alta)

        self.estadia.refresh_from_db()
        self.assertEqual(self.estadia.estado, Estadia.Estado.EGRESADA)
        self.assertIsNone(self.estadia.clave_alojamiento)
        self.assertEqual(self.estadia.egresada_por_id, self.operador_cis.pk)

        nueva = ingresar_persona(
            ciudadano=self.persona,
            dispositivo=self.parador,
            plaza=self.plaza_parador,
            usuario=self.operador_parador,
        )
        self.assertTrue(nueva.activa)

    def test_el_egreso_libera_la_plaza_para_otra_persona(self):
        egresar_persona(estadia=self.estadia, usuario=self.operador_cis, motivo_egreso=self.motivo_alta)

        otra = ingresar_persona(
            ciudadano=self.otra_persona,
            dispositivo=self.cis,
            plaza=self.plaza,
            usuario=self.operador_cis,
        )
        self.assertEqual(otra.plaza_id, self.plaza.pk)

    def test_el_egreso_no_puede_ser_anterior_al_ingreso(self):
        with self.assertRaises(ValidationError):
            egresar_persona(
                estadia=self.estadia,
                usuario=self.operador_cis,
                fecha_egreso=self.estadia.fecha_ingreso - timedelta(minutes=1),
                motivo_egreso=self.motivo_alta,
            )

    def test_el_egreso_no_puede_ser_futuro(self):
        with self.assertRaises(ValidationError):
            egresar_persona(
                estadia=self.estadia,
                usuario=self.operador_cis,
                fecha_egreso=timezone.now() + timedelta(days=1),
                motivo_egreso=self.motivo_alta,
            )

    def test_una_estadia_cerrada_no_se_egresa_dos_veces(self):
        egresar_persona(estadia=self.estadia, usuario=self.operador_cis, motivo_egreso=self.motivo_alta)

        with self.assertRaises(ValidationError):
            egresar_persona(estadia=self.estadia, usuario=self.operador_cis, motivo_egreso=self.motivo_alta)

    def test_el_egreso_deja_traza_con_el_motivo_del_catalogo_y_sin_las_observaciones(self):
        """La traza la lee todo el que opera el dispositivo: las observaciones son texto
        libre de la persona y no entran, igual que en el movimiento."""

        egresar_persona(
            estadia=self.estadia,
            usuario=self.operador_cis,
            motivo="Refiere violencia en el domicilio",
            motivo_egreso=self.motivo_alta,
        )

        traza = TrazaDispositivo.objects.filter(dispositivo=self.cis, accion="ESTADIA_EGRESO").get()
        self.assertEqual(traza.estado_nuevo, Estadia.Estado.EGRESADA)
        self.assertIn("motivo: Alta", traza.detalle)
        self.assertNotIn("violencia", traza.detalle)

    def test_sin_alcance_no_se_egresa(self):
        with self.assertRaises(PermissionDenied):
            egresar_persona(estadia=self.estadia, usuario=self.operador_parador, motivo_egreso=self.motivo_alta)


class VerificacionEnLaRedTests(BaseEstadias):
    """La frontera: qué se cuenta y qué no, según el alcance de quien pregunta."""

    def setUp(self):
        super().setUp()
        self.estadia = ingresar_persona(
            ciudadano=self.persona,
            dispositivo=self.cis,
            plaza=self.plaza,
            usuario=self.operador_cis,
        )

    def test_sin_estadia_abierta_la_verificacion_no_bloquea(self):
        verificacion = verificar_alojamiento_en_red(self.otra_persona, self._usuario(self.operador_cis.pk))

        self.assertFalse(verificacion.alojada)
        self.assertIn("no figura alojada", verificacion.mensaje)

    def test_dentro_del_alcance_se_ve_la_institucion_la_plaza_y_desde_cuando(self):
        verificacion = verificar_alojamiento_en_red(self.persona, self._usuario(self.operador_cis.pk))

        self.assertTrue(verificacion.alojada)
        self.assertTrue(verificacion.dentro_del_alcance)
        self.assertEqual(verificacion.dispositivo, self.cis.nombre)
        self.assertEqual(verificacion.plaza, self.plaza.codigo)
        self.assertEqual(verificacion.dispositivo_id, self.cis.pk)
        self.assertIsNotNone(verificacion.desde)
        self.assertIn(self.cis.nombre, verificacion.mensaje)
        self.assertIn(self.cis.responsable_nombre, verificacion.mensaje)

    def test_fuera_del_alcance_se_entera_de_que_existe_y_de_nada_mas(self):
        """El criterio de aprobación: avisa, exige resolverlo y no filtra la institución."""

        verificacion = verificar_alojamiento_en_red(self.persona, self._usuario(self.operador_parador.pk))

        self.assertTrue(verificacion.alojada)
        self.assertFalse(verificacion.dentro_del_alcance)
        self.assertEqual(verificacion.dispositivo, "")
        self.assertIsNone(verificacion.dispositivo_id)
        self.assertEqual(verificacion.plaza, "")
        self.assertIsNone(verificacion.desde)
        self.assertIsNone(verificacion.estadia_id)
        self.assertEqual(verificacion.responsable, "")

        mensaje = verificacion.mensaje
        for secreto in (self.cis.nombre, self.cis.codigo, self.cis.responsable_nombre, self.plaza.codigo):
            self.assertNotIn(secreto, mensaje)
        # Lo único que viaja es la clave, que se deriva de la persona que quien pregunta
        # ya tiene delante: no agrega un dato nuevo sobre la institución.
        self.assertIn(verificacion.clave, mensaje)
        self.assertIn("coordinación del Programa Dispositivos", mensaje)

    def test_el_mensaje_del_rechazo_fuera_de_alcance_tampoco_filtra(self):
        with self.assertRaises(AlojamientoEnLaRed) as capturado:
            ingresar_persona(
                ciudadano=self.persona,
                dispositivo=self.parador,
                plaza=self.plaza_parador,
                usuario=self._usuario(self.operador_parador.pk),
            )

        self.assertNotIn(self.cis.nombre, str(capturado.exception))

    def test_el_superusuario_ve_toda_la_red(self):
        jefe = User.objects.create_superuser(username="jefa", password="x", email="")

        verificacion = verificar_alojamiento_en_red(self.persona, jefe)

        self.assertTrue(verificacion.dentro_del_alcance)
        self.assertEqual(verificacion.dispositivo, self.cis.nombre)


class ReservaPlazaTests(BaseEstadias):
    def test_se_reserva_una_plaza_libre_y_queda_traza(self):
        reserva = reservar_plaza(
            plaza=self.plaza,
            ciudadano=self.persona,
            usuario=self.operador_cis,
            motivo="Espera #1",
        )

        self.assertTrue(reserva.vigente())
        self.assertTrue(TrazaDispositivo.objects.filter(dispositivo=self.cis, accion="PLAZA_RESERVADA").exists())

    def test_no_se_reserva_una_plaza_ocupada(self):
        ingresar_persona(
            ciudadano=self.persona,
            dispositivo=self.cis,
            plaza=self.plaza,
            usuario=self.operador_cis,
        )

        with self.assertRaises(ValidationError):
            reservar_plaza(plaza=self.plaza, ciudadano=self.otra_persona, usuario=self.operador_cis)

    def test_un_prestamo_necesita_su_vencimiento(self):
        with self.assertRaises(ValidationError):
            reservar_plaza(
                plaza=self.plaza,
                ciudadano=self.persona,
                usuario=self.operador_cis,
                tipo=ReservaPlaza.Tipo.PRESTAMO,
            )

    def test_una_plaza_reservada_no_recibe_a_otra_persona(self):
        reservar_plaza(plaza=self.plaza, ciudadano=self.persona, usuario=self.operador_cis)

        with self.assertRaises(ValidationError) as capturado:
            ingresar_persona(
                ciudadano=self.otra_persona,
                dispositivo=self.cis,
                plaza=self.plaza,
                usuario=self.operador_cis,
            )

        self.assertIn("una reserva vigente", str(capturado.exception))

    def test_el_ingreso_que_consume_su_propia_reserva_entra(self):
        reserva = reservar_plaza(plaza=self.plaza, ciudadano=self.persona, usuario=self.operador_cis)

        estadia = ingresar_persona(
            ciudadano=self.persona,
            dispositivo=self.cis,
            plaza=self.plaza,
            usuario=self.operador_cis,
            reserva=reserva,
        )

        reserva.refresh_from_db()
        self.assertEqual(estadia.plaza_id, self.plaza.pk)
        self.assertEqual(reserva.estado, ReservaPlaza.Estado.CONSUMIDA)

    def test_liberar_la_reserva_devuelve_la_plaza(self):
        reserva = reservar_plaza(plaza=self.plaza, ciudadano=self.persona, usuario=self.operador_cis)

        liberar_reserva(reserva=reserva, usuario=self.operador_cis, motivo="No se presentó")

        estadia = ingresar_persona(
            ciudadano=self.otra_persona,
            dispositivo=self.cis,
            plaza=self.plaza,
            usuario=self.operador_cis,
        )
        self.assertEqual(estadia.plaza_id, self.plaza.pk)

    def test_una_reserva_vencida_deja_de_tomar_la_plaza_sin_que_nadie_la_apague(self):
        ahora = timezone.now()
        ReservaPlaza.objects.create(
            plaza=self.plaza,
            ciudadano=self.persona,
            tipo=ReservaPlaza.Tipo.PRESTAMO,
            desde=ahora - timedelta(days=2),
            hasta=ahora - timedelta(days=1),
        )

        estadia = ingresar_persona(
            ciudadano=self.otra_persona,
            dispositivo=self.cis,
            plaza=self.plaza,
            usuario=self.operador_cis,
        )
        self.assertEqual(estadia.plaza_id, self.plaza.pk)

    def test_sin_alcance_no_se_reserva(self):
        with self.assertRaises(PermissionDenied):
            reservar_plaza(plaza=self.plaza, ciudadano=self.persona, usuario=self.operador_parador)


class FueraDeServicioTests(BaseEstadias):
    """Regla 1 de la etapa 2: el mapa nunca muestra ocupada y fuera de servicio a la vez."""

    def test_no_se_saca_de_servicio_una_plaza_con_estadia_activa(self):
        ingresar_persona(
            ciudadano=self.persona,
            dispositivo=self.cis,
            plaza=self.plaza,
            usuario=self.operador_cis,
        )

        with self.assertRaises(ValidationError) as capturado:
            sacar_plaza_de_servicio(plaza=self.plaza, usuario=self.operador_cis, motivo="Refacción")

        self.assertIn("reubicá", str(capturado.exception).lower())
        self.plaza.refresh_from_db()
        self.assertEqual(self.plaza.estado, Plaza.Estado.OPERATIVA)

    def test_no_se_saca_de_servicio_una_plaza_con_reserva_vigente(self):
        reservar_plaza(plaza=self.plaza, ciudadano=self.persona, usuario=self.operador_cis)

        with self.assertRaises(ValidationError):
            sacar_plaza_de_servicio(plaza=self.plaza, usuario=self.operador_cis, motivo="Refacción")

    def test_una_plaza_libre_sale_de_servicio_con_su_motivo_y_su_traza(self):
        plaza = sacar_plaza_de_servicio(plaza=self.plaza, usuario=self.operador_cis, motivo="Refacción")

        self.assertEqual(plaza.estado, Plaza.Estado.FUERA_SERVICIO)
        self.assertEqual(plaza.motivo_fuera_servicio, "Refacción")
        self.assertTrue(TrazaDispositivo.objects.filter(accion="PLAZA_FUERA_SERVICIO").exists())

    def test_sacar_de_servicio_sin_motivo_falla(self):
        with self.assertRaises(ValidationError):
            sacar_plaza_de_servicio(plaza=self.plaza, usuario=self.operador_cis, motivo="   ")

    def test_volver_a_servicio_borra_el_motivo_y_vuelve_a_recibir(self):
        sacar_plaza_de_servicio(plaza=self.plaza, usuario=self.operador_cis, motivo="Refacción")

        plaza = volver_plaza_a_servicio(plaza=self.plaza, usuario=self.operador_cis)

        self.assertEqual(plaza.estado, Plaza.Estado.OPERATIVA)
        self.assertEqual(plaza.motivo_fuera_servicio, "")
        estadia = ingresar_persona(
            ciudadano=self.persona,
            dispositivo=self.cis,
            plaza=plaza,
            usuario=self.operador_cis,
        )
        self.assertEqual(estadia.plaza_id, plaza.pk)


class CarreraEntreInstitucionesTests(BaseEstadias):
    """Lo que pasa cuando la verificacion no alcanza, que es el caso que importa."""

    def test_si_otro_gano_la_carrera_la_base_rechaza_igual_el_segundo_alojamiento(self):
        """Entre la verificacion y el alta puede entrar otra institucion.

        Se simula con la verificacion mintiendo —«no esta alojada»— mientras la estadia
        ya existe: es exactamente lo que ve el segundo operador cuando el primero
        confirma un milisegundo despues. El `UNIQUE` de `clave_alojamiento` lo frena, y
        el servicio lo traduce al mismo error que habria dado la verificacion. Sin esa
        columna —con el `UniqueConstraint` condicional que MySQL ignora— los dos
        alojamientos entrarian.
        """

        ingresar_persona(
            ciudadano=self.persona,
            dispositivo=self.cis,
            plaza=self.plaza,
            usuario=self.operador_cis,
        )
        libre = VerificacionAlojamiento(clave=Estadia.clave_para(self.persona))

        with mock.patch(
            "programas.services.estadias.verificar_alojamiento_en_red",
            side_effect=[libre, verificar_alojamiento_en_red(self.persona, self._usuario(self.operador_parador.pk))],
        ):
            with self.assertRaises(AlojamientoEnLaRed):
                ingresar_persona(
                    ciudadano=self.persona,
                    dispositivo=self.parador,
                    plaza=self.plaza_parador,
                    usuario=self.operador_parador,
                )

        self.assertEqual(Estadia.objects.activas().count(), 1)


class ContratoDeLaReservaTests(BaseEstadias):
    """MAJOR 1 de la revision de #802: el ingreso que consume una reserva la tiene que validar.

    Antes, `ingresar_persona(reserva=...)` usaba la reserva solo para excluirla del
    control de plaza tomada y para marcarla consumida: no miraba de quien era, ni de que
    plaza, ni si seguia vigente.
    """

    def test_no_se_aloja_a_otra_persona_con_la_reserva_ajena(self):
        reserva_de_ana = reservar_plaza(plaza=self.plaza, ciudadano=self.persona, usuario=self.operador_cis)

        with self.assertRaises(ValidationError):
            ingresar_persona(
                ciudadano=self.otra_persona,
                dispositivo=self.cis,
                plaza=self.plaza,
                usuario=self.operador_cis,
                reserva=reserva_de_ana,
            )

        reserva_de_ana.refresh_from_db()
        self.assertEqual(reserva_de_ana.estado, ReservaPlaza.Estado.VIGENTE)
        self.assertFalse(Estadia.objects.activas().exists())

    def test_una_reserva_liberada_no_se_consume(self):
        reserva = reservar_plaza(plaza=self.plaza, ciudadano=self.persona, usuario=self.operador_cis)
        liberar_reserva(reserva=reserva, usuario=self.operador_cis)

        with self.assertRaises(ValidationError):
            ingresar_persona(
                ciudadano=self.persona,
                dispositivo=self.cis,
                plaza=self.plaza,
                usuario=self.operador_cis,
                reserva=reserva,
            )

        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, ReservaPlaza.Estado.LIBERADA)

    def test_una_reserva_consumida_no_se_consume_dos_veces(self):
        reserva = reservar_plaza(plaza=self.plaza, ciudadano=self.persona, usuario=self.operador_cis)
        estadia = ingresar_persona(
            ciudadano=self.persona,
            dispositivo=self.cis,
            plaza=self.plaza,
            usuario=self.operador_cis,
            reserva=reserva,
        )
        egresar_persona(estadia=estadia, usuario=self.operador_cis, motivo_egreso=self.motivo_alta)

        with self.assertRaises(ValidationError):
            ingresar_persona(
                ciudadano=self.persona,
                dispositivo=self.cis,
                plaza=self.plaza,
                usuario=self.operador_cis,
                reserva=reserva,
            )

    def test_la_reserva_tiene_que_ser_de_la_plaza_del_ingreso(self):
        reserva = reservar_plaza(plaza=self.plaza, ciudadano=self.persona, usuario=self.operador_cis)

        with self.assertRaises(ValidationError):
            ingresar_persona(
                ciudadano=self.persona,
                dispositivo=self.cis,
                plaza=self.otra_plaza,
                usuario=self.operador_cis,
                reserva=reserva,
            )

        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, ReservaPlaza.Estado.VIGENTE)

    def test_un_ingreso_con_reserva_y_sin_plaza_no_entra(self):
        reserva = reservar_plaza(plaza=self.plaza, ciudadano=self.persona, usuario=self.operador_cis)

        with self.assertRaises(ValidationError):
            ingresar_persona(
                ciudadano=self.persona,
                dispositivo=self.cis,
                usuario=self.operador_cis,
                reserva=reserva,
            )


class ReservasAFuturoTests(BaseEstadias):
    """MAJOR 2 de la revision de #802: una reserva que todavia no empezo tambien toma la plaza.

    El control miraba un instante (`vigentes(momento)`) y no el intervalo: una reserva
    con `desde` futuro no se veia, y al llegar su `desde` la plaza quedaba ocupada **y**
    reservada, o reservada dos veces. Eso rompe `ocupadas + reservadas <= operativas` y
    da `disponibles` negativos en el mapa.
    """

    def _reserva_que_empieza_en(self, horas, *, plaza=None, ciudadano=None):
        """La que el servicio ya no deja crear, pero que puede existir por fuera de el."""

        ahora = timezone.now()
        return ReservaPlaza.objects.create(
            plaza=plaza or self.plaza,
            ciudadano=ciudadano or self.otra_persona,
            desde=ahora + timedelta(hours=horas),
            hasta=ahora + timedelta(hours=horas + 24),
        )

    def test_el_servicio_no_crea_reservas_que_empiezan_en_el_futuro(self):
        with self.assertRaises(ValidationError):
            reservar_plaza(
                plaza=self.plaza,
                ciudadano=self.persona,
                usuario=self.operador_cis,
                desde=timezone.now() + timedelta(hours=12),
            )

        self.assertFalse(ReservaPlaza.objects.exists())

    def test_no_se_reserva_encima_de_una_reserva_que_todavia_no_empezo(self):
        self._reserva_que_empieza_en(12)

        with self.assertRaises(ValidationError):
            reservar_plaza(
                plaza=self.plaza,
                ciudadano=self.persona,
                usuario=self.operador_cis,
                tipo=ReservaPlaza.Tipo.PRESTAMO,
                hasta=timezone.now() + timedelta(hours=24),
            )

    def test_no_se_aloja_en_una_plaza_con_una_reserva_que_empieza_en_una_hora(self):
        self._reserva_que_empieza_en(1)

        with self.assertRaises(ValidationError):
            ingresar_persona(
                ciudadano=self.persona,
                dispositivo=self.cis,
                plaza=self.plaza,
                usuario=self.operador_cis,
            )

    def test_tampoco_se_saca_de_servicio(self):
        self._reserva_que_empieza_en(1)

        with self.assertRaises(ValidationError):
            sacar_plaza_de_servicio(plaza=self.plaza, usuario=self.operador_cis, motivo="Refaccion")

    def test_una_reserva_vencida_sigue_sin_tomar_la_plaza(self):
        """La contracara: lo que ya termino no bloquea, aunque nadie la haya apagado."""

        ahora = timezone.now()
        ReservaPlaza.objects.create(
            plaza=self.plaza,
            ciudadano=self.otra_persona,
            desde=ahora - timedelta(days=2),
            hasta=ahora - timedelta(days=1),
        )

        estadia = ingresar_persona(
            ciudadano=self.persona,
            dispositivo=self.cis,
            plaza=self.plaza,
            usuario=self.operador_cis,
        )
        self.assertEqual(estadia.plaza_id, self.plaza.pk)


class OraculoDePlazasTests(BaseEstadias):
    """MINOR de la revision de #802: una plaza que no existe y una ajena dan el mismo error.

    Antes la ajena daba `ValidationError` y la inexistente `DoesNotExist` (un 500): un
    oraculo para enumerar ids de plazas de otras instituciones. Y la ajena se bloqueaba
    con `FOR UPDATE` antes de mirar de quien era.
    """

    def _error_al_ingresar_en(self, plaza):
        with self.assertRaises(ValidationError) as capturado:
            ingresar_persona(
                ciudadano=self.persona,
                dispositivo=self.cis,
                plaza=plaza,
                usuario=self.operador_cis,
            )
        return capturado.exception.message_dict

    def test_inexistente_y_ajena_dan_el_mismo_error(self):
        inexistente = Plaza.objects.order_by("-pk").first().pk + 1000

        self.assertEqual(self._error_al_ingresar_en(inexistente), self._error_al_ingresar_en(self.plaza_parador))

    def test_al_reservar_inexistente_y_ajena_dan_el_mismo_error(self):
        """Al reservar, el dispositivo sale de la plaza: «ajena» es «sin alcance»."""

        inexistente = Plaza.objects.order_by("-pk").first().pk + 1000
        errores = []
        for plaza in (inexistente, self.plaza_parador):
            with self.assertRaises(PermissionDenied) as capturado:
                reservar_plaza(plaza=plaza, ciudadano=self.persona, usuario=self.operador_cis)
            errores.append(str(capturado.exception))

        self.assertEqual(errores[0], errores[1])
        self.assertFalse(ReservaPlaza.objects.exists())


class VerificacionExigeCapacidadTests(BaseEstadias):
    """MINOR de la revision de #802: la verificacion de red exige capacidad por si misma.

    Si no, cualquier vista futura que la llame sin gate le dice a cualquier usuario
    autenticado si una persona esta alojada en algun lugar de la red.
    """

    def setUp(self):
        super().setUp()
        ingresar_persona(
            ciudadano=self.persona,
            dispositivo=self.cis,
            plaza=self.plaza,
            usuario=self.operador_cis,
        )

    def test_sin_usuario_no_se_pregunta(self):
        with self.assertRaises(PermissionDenied):
            verificar_alojamiento_en_red(self.persona, None)

    def test_un_usuario_autenticado_sin_capacidad_no_se_entera(self):
        cualquiera = User.objects.create_user(username="cualquiera", password="x")

        with self.assertRaises(PermissionDenied):
            verificar_alojamiento_en_red(self.persona, cualquiera)

    def test_quien_solo_ve_no_puede_preguntar_por_la_red(self):
        mirador = self._operador("Solo mirar", self.parador, capacidades=("dispositivo.ver",))

        with self.assertRaises(PermissionDenied):
            verificar_alojamiento_en_red(self.persona, mirador)

    def test_quien_admite_en_otra_institucion_si_pregunta_y_ve_solo_que_existe(self):
        verificacion = verificar_alojamiento_en_red(self.persona, self._usuario(self.operador_parador.pk))

        self.assertTrue(verificacion.alojada)
        self.assertFalse(verificacion.dentro_del_alcance)
