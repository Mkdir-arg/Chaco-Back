"""Las exclusiones del MVP de Dispositivos, corridas de verdad con dos hilos (TST-01).

Las reglas de este módulo del dominio —una persona alojada en un solo lugar de la red,
una plaza con un solo ocupante, un relevamiento en curso por edificio, una corrección
por versión— no se pueden delegar a un `UniqueConstraint(condition=...)`:
MySQL y MariaDB lo ignoran en silencio (`ClaveDeAlojamientoTests` lo mide). Lo que las
sostiene es `select_for_update()` sobre la fila por la que se compite, más un UNIQUE común
sobre una columna anulable donde la fila no alcanza (`Estadia.clave_alojamiento`,
`FotoInspeccion.uuid_cliente`, `EntradaBitacora.version_anterior`).

Y eso, en SQLite —el motor de la suite rápida— **no se puede probar**: `select_for_update()`
es un no-op, así que los dos hilos entran juntos y la carrera que se quiere medir no existe.
Era el pendiente explícito del Cambio 262 («falta un test de concurrencia real»).

Acá se corre contra el motor de producción, con `@tag("mysql")`, que es lo que ejecuta el
job «Motor real» de `pr-performance.yml` contra `mariadb:10.11`, `mariadb:11` y `mysql:8.0`.
Sin motor real se saltea (`MotorRealMixin`).

Qué afirma cada caso, siempre lo mismo en tres partes:

1. **Exactamente uno gana** en las exclusiones. En los reenvíos idempotentes, los dos
   reciben el mismo registro y queda una sola escritura y una sola traza.
2. **El otro recibe el error de dominio**, un `ValidationError` o un
   `InspeccionEnConflicto`, nunca un `IntegrityError` crudo, un `OperationalError` de
   deadlock ni un 500. Quién de los dos gana **no** se afirma: depende del motor.
3. **El estado final es consistente**: una estadía, una reserva resuelta de una sola
   manera, un archivo en `media/`.

La capa de al lado —que el `select_for_update()` se pida, y desde dónde— es
`core.tests.candados.candados_tomados`, que corre en todos los PRs sobre SQLite. Las dos
hacen falta: esta no se ejecuta en cada PR, y aquella no puede decir que el candado sirva.
"""

import os
import tempfile
import threading
import uuid
from datetime import datetime, time, timedelta
from pathlib import Path
from unittest import mock

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connections
from django.test import TransactionTestCase, override_settings, tag
from django.utils import timezone

from core import rbac
from core.tests.test_motor_real import MotorRealMixin
from legajos.models import Ciudadano
from programas.models import (
    AsignacionDispositivo,
    Dispositivo,
    Edificio,
    EntradaBitacora,
    Estadia,
    FotoInspeccion,
    InspeccionEdificio,
    Plaza,
    Programa,
    ReservaPlaza,
    Sector,
    TipoDispositivo,
    TrazaInspeccion,
    Turno,
)
from programas.services.bitacora import (
    CORRECCION_CONCURRENTE,
    corregir_entrada,
    crear_turno,
    registrar_entrada,
)
from programas.services.estadias import (
    AlojamientoEnLaRed,
    cambiar_plaza,
    ingresar_persona,
    liberar_reserva,
    reservar_plaza,
)
from programas.services.inspecciones import (
    CONFLICTO_YA_REALIZADA,
    InspeccionEnConflicto,
    agregar_foto,
    crear_inspeccion,
    registrar_resultado,
)
from users.models import Capacidad, RolMeta

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 64

#: Todas las del Programa Dispositivos menos las de relevamiento edilicio, que van a los
#: usuarios que corresponde: cada usuario de prueba tiene todo menos lo que se prueba.
CAPACIDADES_OPERADOR = (
    "dispositivo.ver",
    "dispositivo.admitir",
    "dispositivo.egresar",
    "dispositivo.editar",
    "dispositivo.bitacora",
)

#: La guardia de 24 h del dispositivo de la bitácora: `hora_desde == hora_hasta` hace que
#: cualquier momento caiga en el turno en curso, así que el caso no depende de a qué hora
#: corra el CI. Lo que sí se fija es el reloj (ver `_RELOJ`).
GUARDIA_24H = (time(0), time(0))

#: Un lunes a las 10 de la mañana de Resistencia. Se fija para todos los escenarios.
_RELOJ = timezone.make_aware(datetime(2026, 9, 7, 10, 0, 0))


def _permiso(codigo):
    tipo = ContentType.objects.get_for_model(Capacidad)
    return Permission.objects.get(codename=rbac.codename_de(codigo), content_type=tipo)


def _foto(nombre="fachada.jpg"):
    return SimpleUploadedFile(nombre, JPEG, content_type="image/jpeg")


def en_paralelo(*operaciones, timeout=60):
    """Corre cada operación en su hilo; todas arrancan juntas en una barrera.

    Devuelve ``(resultados, errores)`` —los dos en el orden en que terminaron, que es
    justamente lo que no se puede predecir—. Las excepciones van a `errores` y **no** a
    `resultados`: una excepción guardada entre los resultados dejaría el test en verde
    mientras el hilo se murió.

    Cada hilo cierra sus conexiones al terminar: en un `TransactionTestCase` las abre el
    hilo, no el test, y sin esto la base de test no se puede borrar al final.
    """

    barrera = threading.Barrier(len(operaciones), timeout=30)
    resultados, errores = [], []
    cerrojo = threading.Lock()

    def correr(operacion):
        try:
            barrera.wait()
            valor = operacion()
            with cerrojo:
                resultados.append(valor)
        except Exception as exc:
            with cerrojo:
                errores.append(exc)
        finally:
            connections.close_all()

    hilos = [threading.Thread(target=correr, args=(operacion,)) for operacion in operaciones]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join(timeout=timeout)

    vivos = [hilo for hilo in hilos if hilo.is_alive()]
    if vivos:
        raise AssertionError(f"{len(vivos)} de {len(hilos)} hilos siguen corriendo: candados cruzados o deadlock")
    return resultados, errores


class _BaseCarrera(MotorRealMixin, TransactionTestCase):
    """Una institución con dos plazas, otra enfrente, y un operador con alcance en las dos.

    `TransactionTestCase` y no `TestCase`: lo que se prueba son transacciones que
    commitean: con el `atomic` envolvente de `TestCase` los hilos no verían nada del otro.
    """

    def setUp(self):
        super().setUp()
        reloj = mock.patch("django.utils.timezone.now", return_value=_RELOJ)
        reloj.start()
        self.addCleanup(reloj.stop)
        cache.clear()
        self.programa, _ = Programa.objects.get_or_create(
            codigo="DISPOSITIVOS",
            defaults={"nombre": "Dispositivos", "tipo": Programa.TipoPrograma.DISPOSITIVOS},
        )
        self.tipo = TipoDispositivo.objects.create(codigo="ALBERGUE-C", nombre="Albergue")
        self.cis = self._dispositivo("CIS-C1", "CIS concurrencia")
        self.parador = self._dispositivo("PAR-C1", "Parador concurrencia")
        self.sector = Sector.objects.create(dispositivo=self.cis, nombre="Varones", capacidad=4)
        self.plaza = Plaza.objects.create(sector=self.sector, codigo="C-P1")
        self.otra_plaza = Plaza.objects.create(sector=self.sector, codigo="C-P2")
        self.tercera_plaza = Plaza.objects.create(sector=self.sector, codigo="C-P3")
        self.sector_parador = Sector.objects.create(dispositivo=self.parador, nombre="General", capacidad=2)
        self.plaza_parador = Plaza.objects.create(sector=self.sector_parador, codigo="C-G1")

        self.ana = Ciudadano.objects.create(dni="35100001", nombre="Ana", apellido="Giménez")
        self.beto = Ciudadano.objects.create(dni="35100002", nombre="Beto", apellido="Ruiz")

        self.operador = self._usuario("operador_conc", CAPACIDADES_OPERADOR, [self.cis, self.parador])

    def _dispositivo(self, codigo, nombre):
        return Dispositivo.objects.create(
            tipo=self.tipo,
            codigo=codigo,
            nombre=nombre,
            estado=Dispositivo.Estado.ACTIVO,
            responsable_nombre=f"Responsable de {nombre}",
        )

    def _usuario(self, nombre, capacidades, dispositivos=()):
        rol = Group.objects.create(name=f"Rol {nombre}")
        RolMeta.objects.create(grupo=rol, categoria=rbac.CATEGORIA_PROGRAMA, programa=self.programa, activo=True)
        rol.permissions.add(*[_permiso(codigo) for codigo in capacidades])
        for dispositivo in dispositivos:
            AsignacionDispositivo.objects.create(dispositivo=dispositivo, rol=rol, activo=True)
        # Se llaman servicios, sin login HTTP: no hace falta calcular un hash por fixture.
        usuario = User.objects.create_user(username=nombre)
        usuario.groups.add(rol)
        return User.objects.get(pk=usuario.pk)

    def _fresco(self, usuario):
        """`rbac` memoiza las capacidades en el objeto, y cada hilo necesita el suyo."""

        return User.objects.get(pk=usuario.pk)

    def _un_error(self, errores, tipo=ValidationError):
        """Exactamente un perdedor, y con el error de dominio: ni 500 ni deadlock."""

        self.assertEqual(
            len(errores),
            1,
            f"se esperaba un solo perdedor y hubo {len(errores)}: {[repr(e) for e in errores]}",
        )
        self.assertIsInstance(errores[0], tipo, f"el perdedor no recibió el error de dominio: {errores[0]!r}")
        return errores[0]


# --------------------------------------------------------------------------- #
# Estadías, plazas y reservas (Cambio 262)
# --------------------------------------------------------------------------- #


@tag("mysql")
class CarreraDePlazaTests(_BaseCarrera):
    """Lo que el `UniqueConstraint(condition=...)` borrado prometía y la fila del candado cumple."""

    def _ingresar(self, ciudadano_pk, plaza_pk, dispositivo_pk):
        def operacion():
            return ingresar_persona(
                ciudadano=Ciudadano.objects.get(pk=ciudadano_pk),
                dispositivo=Dispositivo.objects.get(pk=dispositivo_pk),
                usuario=self._fresco(self.operador),
                plaza=Plaza.objects.get(pk=plaza_pk),
            )

        return operacion

    def test_dos_ingresos_a_la_misma_plaza_dejan_una_sola_estadia(self):
        """Escenario 1: dos personas distintas, la misma plaza.

        Sin el `FOR UPDATE` de `_bloquear_plaza` los dos pasan `_exigir_plaza_libre` —cada
        uno lee la plaza libre antes de que el otro commitee— y la institución termina con
        dos personas en la misma cama, que es exactamente lo que el mapa no puede mostrar.
        """

        resultados, errores = en_paralelo(
            self._ingresar(self.ana.pk, self.plaza.pk, self.cis.pk),
            self._ingresar(self.beto.pk, self.plaza.pk, self.cis.pk),
        )

        self.assertEqual(len(resultados), 1, "las dos personas entraron a la misma plaza")
        error = self._un_error(errores)
        self.assertIn("La plaza ya tiene", str(error))
        self.assertEqual(Estadia.objects.activas().filter(plaza=self.plaza).count(), 1)
        self.assertEqual(Estadia.objects.count(), 1)

    def test_la_misma_persona_en_dos_dispositivos_deja_una_sola_estadia_abierta(self):
        """Escenario 2: la clave de alojamiento, que es lo único que cruza instituciones.

        Los dos hilos bloquean plazas **distintas**, de dispositivos distintos: no hay
        ninguna fila común donde formarse. Lo que los serializa es el UNIQUE de
        `clave_alojamiento`, y el servicio tiene que traducir ese `IntegrityError` a
        `AlojamientoEnLaRed` —el mensaje que explica por qué se rechaza el ingreso—, no
        dejarlo salir como 500.
        """

        resultados, errores = en_paralelo(
            self._ingresar(self.ana.pk, self.plaza.pk, self.cis.pk),
            self._ingresar(self.ana.pk, self.plaza_parador.pk, self.parador.pk),
        )

        self.assertEqual(len(resultados), 1, "la misma persona quedó alojada en dos dispositivos")
        self._un_error(errores, AlojamientoEnLaRed)
        self.assertEqual(Estadia.objects.activas().filter(ciudadano=self.ana).count(), 1)
        self.assertEqual(Estadia.objects.count(), 1)

    def test_dos_cambios_de_plaza_hacia_la_misma_plaza_libre_mueven_a_uno_solo(self):
        """Escenario 3: el cambio de plaza compite por lo mismo que el ingreso."""

        primera = ingresar_persona(
            ciudadano=self.ana,
            dispositivo=self.cis,
            usuario=self._fresco(self.operador),
            plaza=self.plaza,
        )
        segunda = ingresar_persona(
            ciudadano=self.beto,
            dispositivo=self.cis,
            usuario=self._fresco(self.operador),
            plaza=self.otra_plaza,
        )

        def mover(estadia_pk):
            def operacion():
                return cambiar_plaza(
                    estadia=Estadia.objects.get(pk=estadia_pk),
                    plaza=Plaza.objects.get(pk=self.tercera_plaza.pk),
                    usuario=self._fresco(self.operador),
                    motivo="Reubicación por obra",
                )

            return operacion

        resultados, errores = en_paralelo(mover(primera.pk), mover(segunda.pk))

        self.assertEqual(len(resultados), 1, "las dos personas se mudaron a la misma plaza")
        error = self._un_error(errores)
        self.assertIn("La plaza ya tiene", str(error))
        self.assertEqual(Estadia.objects.activas().filter(plaza=self.tercera_plaza).count(), 1)
        # Y el que perdió no se movió: sigue donde estaba.
        destinos = set(Estadia.objects.activas().values_list("plaza_id", flat=True))
        self.assertEqual(len(destinos), 2)
        self.assertIn(self.tercera_plaza.pk, destinos)
        ganador = resultados[0].estadia_id
        for estadia, origen in ((primera, self.plaza), (segunda, self.otra_plaza)):
            estadia.refresh_from_db()
            self.assertEqual(estadia.plaza_id, self.tercera_plaza.pk if estadia.pk == ganador else origen.pk)

    def test_un_ingreso_y_una_reserva_sobre_la_misma_plaza_no_conviven(self):
        """Escenario 4: ocupada **y** reservada a la vez es el mapa con disponibles negativos."""

        def reservar():
            return reservar_plaza(
                plaza=Plaza.objects.get(pk=self.plaza.pk),
                ciudadano=Ciudadano.objects.get(pk=self.beto.pk),
                usuario=self._fresco(self.operador),
            )

        resultados, errores = en_paralelo(self._ingresar(self.ana.pk, self.plaza.pk, self.cis.pk), reservar)

        self.assertEqual(len(resultados), 1, "la plaza quedó ocupada y reservada a la vez")
        self._un_error(errores)
        ocupada = Estadia.objects.activas().filter(plaza=self.plaza).exists()
        reservada = ReservaPlaza.objects.filter(plaza=self.plaza, estado=ReservaPlaza.Estado.VIGENTE).exists()
        self.assertNotEqual(ocupada, reservada, "la plaza quedó tomada dos veces (o ninguna)")

    def test_consumir_y_liberar_la_misma_reserva_a_la_vez_la_resuelve_una_sola_vez(self):
        """Escenario 5: la reserva se consume o se libera, nunca las dos cosas.

        Ambos servicios bloquean primero la plaza y después la reserva, sin JOIN que
        tome también el sector. El orden evita el deadlock de la actualización de la
        reserva, cuyo índice de FK también toma un candado sobre la plaza.
        """

        reserva = reservar_plaza(
            plaza=self.plaza,
            ciudadano=self.ana,
            usuario=self._fresco(self.operador),
        )

        def ingresar_con_la_reserva():
            return ingresar_persona(
                ciudadano=Ciudadano.objects.get(pk=self.ana.pk),
                dispositivo=Dispositivo.objects.get(pk=self.cis.pk),
                usuario=self._fresco(self.operador),
                plaza=Plaza.objects.get(pk=self.plaza.pk),
                reserva=ReservaPlaza.objects.get(pk=reserva.pk),
            )

        def liberar():
            return liberar_reserva(
                reserva=ReservaPlaza.objects.get(pk=reserva.pk),
                usuario=self._fresco(self.operador),
                motivo="La persona no se presentó",
            )

        resultados, errores = en_paralelo(ingresar_con_la_reserva, liberar)

        self.assertEqual(len(resultados), 1, "la reserva se consumió y se liberó")
        error = self._un_error(errores)
        self.assertIn("no está vigente", str(error))

        reserva.refresh_from_db()
        alojada = Estadia.objects.activas().filter(plaza=self.plaza).exists()
        if reserva.estado == ReservaPlaza.Estado.CONSUMIDA:
            self.assertTrue(alojada, "la reserva se consumió y nadie quedó alojado")
        else:
            self.assertEqual(reserva.estado, ReservaPlaza.Estado.LIBERADA)
            self.assertFalse(alojada, "la reserva se liberó y quedó alguien alojado igual")


# --------------------------------------------------------------------------- #
# Relevamiento edilicio (Cambio 276 y task 39)
# --------------------------------------------------------------------------- #


@tag("mysql")
class CarreraDeInspeccionTests(_BaseCarrera):
    """Un relevamiento en curso por edificio, y los reenvíos de la app sin conexión."""

    def setUp(self):
        super().setUp()
        media = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(media.cleanup)
        self.media = Path(media.name)
        contexto = override_settings(MEDIA_ROOT=media.name)
        contexto.enable()
        self.addCleanup(contexto.disable)

        self.edificio = Edificio.objects.create(codigo="ED-CONC", nombre="Edificio concurrencia")
        self.edificio.dispositivos.add(self.cis)
        self.coordinador = self._usuario("coord_conc", ("inspeccion.asignar", "dispositivo.ver"), [self.cis])
        # Externo a las instituciones del edificio: es el default de `AGENTE_DEBE_SER_EXTERNO`.
        self.agente = self._usuario("agente_conc", ("inspeccion.relevar",))
        self.otro_agente = self._usuario("otro_agente_conc", ("inspeccion.relevar",))
        self.vence = timezone.localdate() + timedelta(days=30)

    def _crear(self, agente=None):
        return crear_inspeccion(
            self._fresco(self.coordinador),
            edificio=Edificio.objects.get(pk=self.edificio.pk),
            asignado_a=self._fresco(agente or self.agente),
            fecha_vencimiento=self.vence,
        )

    def _archivos_en_media(self):
        return [Path(raiz) / nombre for raiz, _, nombres in os.walk(self.media) for nombre in nombres]

    def test_dos_asignaciones_del_mismo_edificio_dejan_un_relevamiento_en_curso(self):
        """Escenario 6: dos coordinadores asignan el mismo predio en el mismo minuto.

        La regla es «un edificio, un relevamiento en curso», y no la puede escribir el
        esquema: sería un `UniqueConstraint` con `condition=estado=ASIGNADA`, que en
        producción no existe. La sostiene el `FOR UPDATE` sobre la fila del edificio.
        """

        resultados, errores = en_paralelo(
            lambda: self._crear(self.agente),
            lambda: self._crear(self.otro_agente),
        )

        self.assertEqual(len(resultados), 1, "el edificio quedó con dos relevamientos en curso")
        error = self._un_error(errores)
        self.assertIn("ya tiene un relevamiento en curso", str(error))
        self.assertEqual(
            InspeccionEdificio.objects.filter(
                edificio=self.edificio, estado=InspeccionEdificio.Estado.ASIGNADA
            ).count(),
            1,
        )

    def test_el_mismo_envio_de_resultado_dos_veces_es_idempotente(self):
        """Escenario 8a: la app reintenta el mismo `uuid_resultado` y los dos responden OK.

        Es el caso real del reenvío: la app manda, se corta la conexión antes de leer la
        respuesta y vuelve a mandar. Los dos tienen que ver el relevamiento como quedó —sin
        un segundo resultado y sin un 409 que mande a refrescar por nada—.
        """

        inspeccion = self._crear()
        mismo = uuid.uuid4()

        def enviar():
            return registrar_resultado(
                self._fresco(self.agente),
                InspeccionEdificio.objects.get(pk=inspeccion.pk),
                criticidad=InspeccionEdificio.Criticidad.MEDIA,
                observaciones="Humedad en el techo",
                uuid_resultado=mismo,
            )

        resultados, errores = en_paralelo(enviar, enviar)

        self.assertEqual([repr(error) for error in errores], [], "un reenvío idéntico no puede dar conflicto")
        self.assertEqual(len(resultados), 2)
        self.assertEqual({resultado.pk for resultado in resultados}, {inspeccion.pk})
        inspeccion.refresh_from_db()
        self.assertEqual(inspeccion.estado, InspeccionEdificio.Estado.REALIZADA)
        self.assertEqual(inspeccion.uuid_resultado, mismo)
        self.assertEqual(inspeccion.criticidad, InspeccionEdificio.Criticidad.MEDIA)
        self.assertEqual(
            InspeccionEdificio.objects.filter(estado=InspeccionEdificio.Estado.REALIZADA).count(),
            1,
        )
        # La auditoría es lo único que distingue «se cerró una vez» de «se cerró dos veces
        # con el mismo resultado»: sin el candado los dos hilos escriben el mismo estado y
        # la fila final es idéntica, pero quedan dos líneas de que se relevó.
        self.assertEqual(
            TrazaInspeccion.objects.filter(inspeccion=inspeccion, accion=TrazaInspeccion.Accion.REALIZADA).count(),
            1,
            "el reenvío dejó una segunda línea de auditoría: el resultado se escribió dos veces",
        )

    def test_dos_resultados_distintos_a_la_vez_dejan_uno_y_el_otro_es_conflicto(self):
        """Escenario 8b: dos envíos **distintos** sobre el mismo relevamiento."""

        inspeccion = self._crear()

        def enviar(criticidad):
            def operacion():
                return registrar_resultado(
                    self._fresco(self.agente),
                    InspeccionEdificio.objects.get(pk=inspeccion.pk),
                    criticidad=criticidad,
                    uuid_resultado=uuid.uuid4(),
                )

            return operacion

        resultados, errores = en_paralelo(
            enviar(InspeccionEdificio.Criticidad.ALTA),
            enviar(InspeccionEdificio.Criticidad.BAJA),
        )

        self.assertEqual(len(resultados), 1, "el relevamiento se cerró dos veces")
        error = self._un_error(errores, InspeccionEnConflicto)
        self.assertEqual(error.codigo, CONFLICTO_YA_REALIZADA)
        inspeccion.refresh_from_db()
        self.assertEqual(inspeccion.estado, InspeccionEdificio.Estado.REALIZADA)
        # El que ganó es el que quedó: la criticidad y el uuid son del mismo envío.
        self.assertEqual(inspeccion.criticidad, resultados[0].criticidad)
        self.assertEqual(inspeccion.uuid_resultado, resultados[0].uuid_resultado)
        self.assertEqual(
            TrazaInspeccion.objects.filter(inspeccion=inspeccion, accion=TrazaInspeccion.Accion.REALIZADA).count(),
            1,
        )

    def test_la_misma_foto_mandada_dos_veces_no_deja_un_archivo_huerfano(self):
        """Escenario 9: idempotencia de `agregar_foto`, con el storage incluido.

        La base vuelve atrás con la transacción; el disco no. El reenvío tiene que devolver
        la fila que ya está **antes** de escribir nada, y lo que escribió el que perdiera
        una carrera lo borra `core.archivos`. Si quedara un archivo suelto nadie se
        enteraría: no hay fila que lo apunte.
        """

        inspeccion = self._crear()
        mismo = uuid.uuid4()

        def enviar():
            return agregar_foto(
                self._fresco(self.agente),
                InspeccionEdificio.objects.get(pk=inspeccion.pk),
                _foto(),
                descripcion="Fachada",
                uuid_cliente=mismo,
            )

        resultados, errores = en_paralelo(enviar, enviar)

        self.assertEqual([repr(error) for error in errores], [], "un reenvío idéntico no puede dar conflicto")
        self.assertEqual(len(resultados), 2)
        self.assertEqual(FotoInspeccion.objects.filter(inspeccion=inspeccion).count(), 1)
        self.assertEqual({foto.pk for foto in resultados}, {FotoInspeccion.objects.get().pk})
        # Uno de los dos la encontró ya cargada: es lo que la app lee para no reintentar.
        self.assertEqual(sorted(getattr(foto, "ya_existia", None) is True for foto in resultados), [False, True])
        self.assertEqual(
            self._archivos_en_media(),
            [Path(FotoInspeccion.objects.get().archivo.path)],
            "quedó un archivo en media/ que ninguna fila apunta",
        )
        self.assertEqual(
            TrazaInspeccion.objects.filter(inspeccion=inspeccion, accion=TrazaInspeccion.Accion.FOTO).count(),
            1,
        )


# --------------------------------------------------------------------------- #
# Turnos y bitácora (Cambio 272)
# --------------------------------------------------------------------------- #


@tag("mysql")
class CarreraDeBitacoraTests(_BaseCarrera):
    """La corrección que no pisa y el turno vigente que sigue siendo uno.

    El reloj va fijo (`_RELOJ`): lo que se mide es la carrera entre los dos hilos, no a qué
    hora corrió el CI. Con la guardia de 24 h cualquier momento cae en el turno en curso,
    así que el caso tampoco depende de que el reloj fijo coincida con un turno.
    """

    def test_dos_turnos_superpuestos_dados_de_alta_a_la_vez_dejan_uno_solo(self):
        """Escenario 10: si los dos entran, «el turno vigente» deja de ser uno.

        Los nombres son distintos a propósito: el `UniqueConstraint(dispositivo, nombre)`
        no puede ser lo que sostenga la regla. Lo único que la sostiene es el `FOR UPDATE`
        sobre la fila del dispositivo, porque la superposición de intervalos circulares no
        la expresa ningún constraint.
        """

        def crear(nombre, desde, hasta):
            def operacion():
                return crear_turno(
                    dispositivo=Dispositivo.objects.get(pk=self.cis.pk),
                    usuario=self._fresco(self.operador),
                    nombre=nombre,
                    hora_desde=desde,
                    hora_hasta=hasta,
                )

            return operacion

        resultados, errores = en_paralelo(
            crear("Mañana", time(6), time(14)),
            crear("Mañana larga", time(12), time(20)),
        )

        self.assertEqual(len(resultados), 1, "los dos turnos superpuestos entraron")
        error = self._un_error(errores)
        self.assertIn("se superpone con el turno", str(error))
        self.assertEqual(Turno.objects.filter(dispositivo=self.cis, activo=True).count(), 1)

    def test_dos_correcciones_de_la_misma_entrada_dejan_una_sola_version_nueva(self):
        """Escenario 7: dos operadores corrigen la misma versión.

        La cadena de versiones es la auditoría de la bitácora: dos correcciones de la misma
        versión serían dos ramas, y la pantalla tendría que elegir cuál mostrar. La fila
        común donde se forman es la **raíz** de la cadena; el UNIQUE de `version_anterior`
        es la red de abajo, para quien llegue sin pasar por el servicio.
        """

        Turno.objects.create(
            dispositivo=self.cis,
            nombre="Guardia",
            hora_desde=GUARDIA_24H[0],
            hora_hasta=GUARDIA_24H[1],
        )
        entrada = registrar_entrada(
            dispositivo=self.cis,
            usuario=self._fresco(self.operador),
            tipo=EntradaBitacora.Tipo.GENERAL,
            texto="Se recibió una donación de frazadas.",
        )

        def corregir(texto):
            def operacion():
                return corregir_entrada(
                    entrada=EntradaBitacora.objects.get(pk=entrada.pk),
                    usuario=self._fresco(self.operador),
                    texto=texto,
                    motivo="Error de tipeo",
                )

            return operacion

        resultados, errores = en_paralelo(
            corregir("Se recibieron doce frazadas."),
            corregir("Se recibieron veinte frazadas."),
        )

        self.assertEqual(len(resultados), 1, "la entrada se corrigió dos veces: la cadena se bifurcó")
        error = self._un_error(errores)
        self.assertIn(CORRECCION_CONCURRENTE, str(error))
        self.assertEqual(EntradaBitacora.objects.filter(version_anterior=entrada).count(), 1)
        versiones = list(entrada.versiones())
        self.assertEqual([version.version for version in versiones], [1, 2])
        # La versión 1 conserva su texto: corregir agrega, no pisa.
        self.assertEqual(versiones[0].texto, "Se recibió una donación de frazadas.")
        self.assertEqual(versiones[1].texto, resultados[0].texto)
