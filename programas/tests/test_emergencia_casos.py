"""Módulo Emergencia, PR 2: el modelo del caso y los servicios de la mesa.

Qué fija este archivo, regla por regla:

* **RN-1.2 a 1.5, 1.10 a 1.12** — ``crear_caso``: el total y la prioridad son del servidor,
  las validaciones del paso 3, el alta mínima del responsable, cómo nace el caso según el
  origen y la idempotencia por ``uuid_cliente`` (RU-16).
* **RN-2.1 a 2.6, 2.9, 2.11 a 2.15** — tomar, soltar, reasignar, priorizar, contactar,
  derivar, cancelar y cerrar, con dueño y supervisor (RU-12, RU-13) y una traza por
  transición (RU-15).
* **RN-2.10** — la tabla del semáforo del SLA, con **momentos fijos**.
* **RU §6 n.° 1 y n.° 4** — los dos tests de mutación de esta etapa. Se vieron en rojo
  contra la regla rota antes de quedar verdes; el detalle está en el docstring de cada uno.
* **Presupuestos** — ``conteo_por_solapa`` y ``dispositivos_para_derivar`` con 50
  dispositivos, por ``assertNumQueries``.

Las carreras de verdad (dos conexiones) están en ``test_emergencia_concurrencia``: en
SQLite ``select_for_update`` es un no-op. Acá se fija el **orden** de los candados por la
secuencia de llamadas (``OrdenDeLosCandadosEmergenciaTests``).
"""

import shutil
import tempfile
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, models, transaction
from django.test import SimpleTestCase, override_settings, tag
from django.utils import timezone

from core.models import Localidad
from core.tests.candados import orden_de_candados
from legajos.models import Ciudadano
from programas.models import (
    AdjuntoCaso,
    CasoEmergencia,
    ContactoCaso,
    Derivacion,
    Dispositivo,
    Estadia,
    GrupoFamiliar,
    IntegranteGrupo,
    NumeradorEmergencia,
    Plaza,
    ReservaPlaza,
    Sector,
    SLAEmergencia,
    TipoDispositivo,
    TrazaCaso,
)
from programas.selectors import emergencia as selectores
from programas.selectors.emergencia import (
    MARCA_ALCANZA,
    MARCA_FALTAN,
    MARCA_SIN_PLAZAS,
    SLA_EN_TERMINO,
    SLA_FUERA,
    SLA_POR_VENCER,
    EstadoSLA,
    estado_sla,
    texto_de_minutos,
)
from programas.services import emergencia as servicio
from programas.services import emergencia_alta
from programas.services.emergencia import (
    CasoTomadoPorOtro,
    EstadoCambio,
    FaltanPlazas,
)
from programas.tests.test_emergencia_base import OPERAR, RELEVAR, SUPERVISAR, BaseEmergencia

Estado = CasoEmergencia.Estado
Origen = CasoEmergencia.Origen
Prioridad = CasoEmergencia.Prioridad
Accion = TrazaCaso.Accion

#: Un jueves a las 10 de la mañana de Resistencia. Todo momento del archivo sale de acá.
T0 = timezone.make_aware(datetime(2026, 11, 12, 10, 0, 0))

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 64


class Reloj:
    """``timezone.now`` detenido, que avanza cuando el test lo dice."""

    def __init__(self, ahora):
        self.ahora = ahora

    def __call__(self):
        return self.ahora

    def avanzar(self, **lapso):
        self.ahora += timedelta(**lapso)
        return self.ahora


class BaseCasos(BaseEmergencia):
    """La mesa armada: operadores, supervisor, agente, y dispositivos con camas."""

    def setUp(self):
        super().setUp()
        self.reloj = Reloj(T0)
        parche = mock.patch("django.utils.timezone.now", self.reloj)
        parche.start()
        self.addCleanup(parche.stop)

        self.agente = self._usuario("agente", [RELEVAR])
        self.operador = self._persona_de_mesa("ana", [OPERAR], "Ana", "López")
        self.otro_operador = self._persona_de_mesa("juan", [OPERAR], "Juan", "Pérez")
        # Solo `supervisar`, sin `operar`: la regla no puede depender de que el rol traiga las dos.
        self.supervisor = self._persona_de_mesa("sup", [SUPERVISAR], "Sara", "Ruiz")
        self.tipo = TipoDispositivo.objects.create(
            codigo="EVACUADOS", nombre="Centro de evacuados", tipos_plaza_admitidos=["CAMA"]
        )
        self._dnis = iter(range(30_000_001, 30_009_999))

    def _persona_de_mesa(self, username, capacidades, nombre, apellido):
        usuario = self._usuario(username, capacidades)
        User.objects.filter(pk=usuario.pk).update(first_name=nombre, last_name=apellido)
        return User.objects.get(pk=usuario.pk)

    def _datos(self, **cambios):
        datos = {
            "traslado": GrupoFamiliar.Traslado.BOMBEROS,
            "dni": str(next(self._dnis)),
            "nombre": "Rosa",
            "apellido": "Benítez",
            "adultos_f": 1,
            "adultos_m": 1,
            "direccion": "Av. Sarmiento 1200",
        }
        datos.update(cambios)
        return datos

    def _caso(self, origen=Origen.TERRITORIO, usuario=None, uuid_cliente=None, relevado_en=None, **cambios):
        if usuario is None:
            usuario = self.agente if origen == Origen.TERRITORIO else self.operador
        return servicio.crear_caso(
            usuario=usuario,
            origen=origen,
            datos_formulario1=self._datos(**cambios),
            uuid_cliente=uuid_cliente,
            relevado_en=relevado_en,
        )

    def _caso_tomado(self, por=None, **cambios):
        return servicio.tomar_caso(self._caso(**cambios), por or self.operador)

    def _dispositivo(self, nombre, camas=0, *, latitud=None, longitud=None, tipo=None, estado=None, localidad=""):
        dispositivo = Dispositivo.objects.create(
            tipo=tipo or self.tipo,
            codigo=f"D-{Dispositivo.objects.count() + 1:03d}",
            nombre=nombre,
            estado=estado or Dispositivo.Estado.ACTIVO,
            latitud=latitud,
            longitud=longitud,
            localidad=localidad,
        )
        if camas:
            sector = Sector.objects.create(dispositivo=dispositivo, nombre="General", capacidad=camas)
            Plaza.objects.bulk_create([Plaza(sector=sector, codigo=f"C{n:03d}") for n in range(1, camas + 1)])
        return dispositivo

    def _ocupar(self, dispositivo, cuantas):
        """Ocupa ``cuantas`` camas con estadías activas de personas cualesquiera."""

        plazas = list(Plaza.objects.filter(sector__dispositivo=dispositivo).order_by("codigo")[:cuantas])
        for plaza in plazas:
            persona = Ciudadano.objects.create(dni=str(next(self._dnis)), nombre="Persona", apellido="Alojada")
            Estadia.objects.create(
                ciudadano=persona,
                dispositivo=dispositivo,
                plaza=plaza,
                fecha_ingreso=T0 - timedelta(days=1),
                clave_alojamiento=Estadia.clave_para(persona),
            )

    def _trazas(self, caso):
        return list(TrazaCaso.objects.filter(caso=caso).order_by("id"))

    def _fila(self, caso):
        """Lo que quedó en la base, sin nada de lo que tenga el objeto en memoria."""

        return CasoEmergencia.objects.filter(pk=caso.pk).values().get()


# ---------------------------------------------------------------------------
# Modelos
# ---------------------------------------------------------------------------


class ModelosTests(BaseCasos):
    def test_str_de_cada_modelo(self):
        caso = self._caso_tomado(dni="30111222", nombre="Rosa", apellido="Benítez", menores_f=1)
        dispositivo = self._dispositivo("Club Sarmiento", camas=5)
        derivacion = servicio.derivar_caso(caso, self.operador, dispositivo, 3)
        contacto = servicio.registrar_contacto(caso, self.operador, canal="LLAMADA", resultado="ATENDIO")
        integrante = IntegranteGrupo.objects.create(grupo=caso.grupo, orden=1)
        confirmado = IntegranteGrupo.objects.create(grupo=caso.grupo, orden=2, ciudadano=caso.grupo.responsable)
        adjunto = AdjuntoCaso(caso=caso, tipo=AdjuntoCaso.Tipo.VIVIENDA, cargado_por=self.agente)
        numerador = NumeradorEmergencia.objects.get(serie="C", anio=2026)

        self.assertEqual(str(caso.grupo), "Familia de Benítez, Rosa · 3 personas")
        self.assertEqual(str(caso), "Caso 2026-000001")
        self.assertEqual(str(derivacion), "Derivación del caso 2026-000001 a Club Sarmiento")
        self.assertEqual(str(contacto), "Llamada · Atendió · caso 2026-000001")
        self.assertEqual(str(integrante), "Integrante 1 · sin confirmar")
        self.assertEqual(str(confirmado), "Integrante 2 · Benítez, Rosa")
        self.assertEqual(str(adjunto), "Foto de la vivienda · caso 2026-000001")
        self.assertEqual(str(self._trazas(caso)[0]), "Caso 2026-000001 · Caso creado")
        self.assertEqual(str(numerador), "Serie C · 2026: 1")

    def test_el_grupo_de_una_persona_se_lee_en_singular(self):
        caso = self._caso(adultos_f=1, adultos_m=0, apellido="Sosa", nombre="Luz")
        self.assertEqual(str(caso.grupo), "Familia de Sosa, Luz · 1 persona")

    def test_la_traza_del_caso_es_inmutable(self):
        caso = self._caso()
        traza = self._trazas(caso)[0]
        traza.detalle = "otra cosa"

        with self.assertRaises(ValidationError):
            traza.save()
        with self.assertRaises(ValidationError):
            traza.delete()
        with self.assertRaises(ValidationError):
            TrazaCaso.objects.filter(pk=traza.pk).update(detalle="otra cosa")
        with self.assertRaises(ValidationError):
            TrazaCaso.objects.filter(pk=traza.pk).delete()
        with self.assertRaises(ValidationError):
            TrazaCaso.objects.bulk_update([traza], ["detalle"])
        self.assertEqual(TrazaCaso.objects.get(pk=traza.pk).detalle, "Relevado en territorio")

    def test_ningun_unique_del_modulo_es_condicional(self):
        """Un ``UniqueConstraint(condition=…)`` MySQL y MariaDB no lo crean: pasa acá y no existe en producción."""

        for modelo in (CasoEmergencia, Derivacion, IntegranteGrupo, AdjuntoCaso, NumeradorEmergencia, GrupoFamiliar):
            for restriccion in modelo._meta.constraints:
                if isinstance(restriccion, models.UniqueConstraint):
                    with self.subTest(restriccion=restriccion.name):
                        self.assertIsNone(restriccion.condition)

    def test_la_clave_vigente_sale_del_estado_aunque_se_guarde_solo_el_estado(self):
        caso = self._caso_tomado()
        derivacion = servicio.derivar_caso(caso, self.operador, self._dispositivo("Club", camas=5), 2)
        self.assertEqual(derivacion.clave_vigente, caso.pk)

        derivacion.estado = Derivacion.Estado.ACEPTADA
        derivacion.save(update_fields=["estado"])
        self.assertEqual(Derivacion.objects.get(pk=derivacion.pk).clave_vigente, caso.pk)

        derivacion.estado = Derivacion.Estado.RECHAZADA
        derivacion.save(update_fields=["estado"])
        self.assertIsNone(Derivacion.objects.get(pk=derivacion.pk).clave_vigente)

    def test_dos_derivaciones_vigentes_del_mismo_caso_chocan_en_la_base(self):
        caso = self._caso_tomado()
        dispositivo = self._dispositivo("Club", camas=5)
        servicio.derivar_caso(caso, self.operador, dispositivo, 2)

        with self.assertRaises(IntegrityError), transaction.atomic():
            Derivacion.objects.create(
                caso=caso,
                dispositivo=dispositivo,
                estado=Derivacion.Estado.ACEPTADA,
                plazas_pedidas=2,
                vence_en=T0,
                derivada_por=self.operador,
            )

    def test_las_derivaciones_resueltas_del_mismo_caso_conviven(self):
        caso = self._caso_tomado()
        dispositivo = self._dispositivo("Club", camas=5)
        for _ in range(3):
            derivacion = servicio.derivar_caso(caso, self.operador, dispositivo, 2)
            servicio.cancelar_derivacion(derivacion, self.operador, "Se equivocó de dispositivo")

        self.assertEqual(Derivacion.objects.filter(caso=caso, clave_vigente__isnull=True).count(), 3)

    def test_un_integrante_sin_confirmar_no_choca_con_otro_y_una_persona_no_entra_dos_veces(self):
        grupo = self._caso().grupo
        IntegranteGrupo.objects.create(grupo=grupo, orden=1)
        IntegranteGrupo.objects.create(grupo=grupo, orden=2)
        IntegranteGrupo.objects.create(grupo=grupo, orden=3, ciudadano=grupo.responsable)

        with self.assertRaises(IntegrityError), transaction.atomic():
            IntegranteGrupo.objects.create(grupo=grupo, orden=4, ciudadano=grupo.responsable)
        with self.assertRaises(IntegrityError), transaction.atomic():
            IntegranteGrupo.objects.create(grupo=grupo, orden=1)

    def test_una_marca_se_escribe_una_sola_vez(self):
        caso = CasoEmergencia()
        self.assertTrue(caso.marcar("tomado_en", T0))
        self.assertFalse(caso.marcar("tomado_en", T0 + timedelta(hours=1)))
        self.assertEqual(caso.tomado_en, T0)
        with self.assertRaises(ValueError):
            caso.marcar("relevado_en", T0)

    def test_un_caso_cerrado_sin_marca_no_entra_a_la_base(self):
        caso = self._caso()
        with self.assertRaises(IntegrityError), transaction.atomic():
            CasoEmergencia.objects.filter(pk=caso.pk).update(estado=Estado.CERRADO)

    def test_la_ubicacion_es_aproximada_desde_mas_de_cien_metros(self):
        caso = CasoEmergencia(latitud=Decimal("-27.45"), longitud=Decimal("-58.98"), precision_m=100)
        self.assertFalse(caso.ubicacion_aproximada)
        caso.precision_m = 101
        self.assertTrue(caso.ubicacion_aproximada)
        self.assertFalse(CasoEmergencia(precision_m=500).ubicacion_aproximada)

    def test_las_tablas_de_estados_visibles_cubren_todos_los_valores(self):
        self.assertEqual(set(servicio.ESTADOS_VISIBLES_CASO), set(Estado))
        self.assertEqual(set(servicio.PRIORIDADES_VISIBLES), set(Prioridad))
        self.assertEqual(
            servicio.estado_visible_de_caso(CasoEmergencia(estado=Estado.EN_GESTION)), ("En gestión", "warning")
        )
        self.assertEqual(servicio.prioridad_visible(CasoEmergencia(prioridad=Prioridad.ALTA)), ("Alta", "danger"))


# ---------------------------------------------------------------------------
# crear_caso
# ---------------------------------------------------------------------------


class CrearCasoTests(BaseCasos):
    def test_el_total_lo_calcula_el_servidor_y_no_el_que_manda_el_cliente(self):
        """RN-1.2."""
        caso = self._caso(
            menores_f=1, menores_m=2, adultos_f=1, adultos_m=1, mayores_f=1, mayores_m=1, total=99, total_declarado=99
        )
        self.assertEqual(caso.grupo.total_declarado, 7)
        self.assertEqual(GrupoFamiliar.objects.get(pk=caso.grupo_id).total_declarado, 7)

    def test_sin_personas_no_hay_caso(self):
        with self.assertRaises(ValidationError) as error:
            self._caso(adultos_f=0, adultos_m=0)
        self.assertEqual(error.exception.message_dict, {"total": ["Cargá al menos una persona."]})
        self.assertFalse(CasoEmergencia.objects.exists())

    def test_las_validaciones_del_paso_3(self):
        """RN-1.3: dependientes ≤ total, mayores dependientes ≤ mayores, lactantes ≤ menores."""
        base = {"menores_f": 1, "adultos_f": 1, "adultos_m": 0, "mayores_m": 1}  # total 3
        tabla = [
            ({"dependientes": 3}, None),
            ({"dependientes": 4}, "dependientes"),
            ({"mayores_dependientes": 1}, None),
            ({"mayores_dependientes": 2}, "mayores_dependientes"),
            ({"lactantes": 1}, None),
            ({"lactantes": 2}, "lactantes"),
            ({"lactantes": -1}, "lactantes"),
            ({"menores_f": "dos"}, "menores_f"),
        ]
        for cambios, campo_con_error in tabla:
            with self.subTest(cambios=cambios):
                if campo_con_error is None:
                    self._caso(**{**base, **cambios})
                    continue
                with self.assertRaises(ValidationError) as error:
                    self._caso(**{**base, **cambios})
                self.assertIn(campo_con_error, error.exception.message_dict)

    def test_la_prioridad_sugerida(self):
        """RN-1.4, la tabla entera. La calcula el servidor: lo que mande el cliente no cuenta."""
        solo_adultos = {"adultos_f": 1, "adultos_m": 1}
        tabla = [
            (solo_adultos, Prioridad.BAJA),
            ({**solo_adultos, "mascotas": True}, Prioridad.BAJA),
            ({**solo_adultos, "prioridad": "ALTA"}, Prioridad.BAJA),
            ({**solo_adultos, "menores_m": 1}, Prioridad.MEDIA),
            ({**solo_adultos, "mayores_f": 1}, Prioridad.MEDIA),
            ({**solo_adultos, "dependientes": 1}, Prioridad.MEDIA),
            ({**solo_adultos, "menores_f": 1, "lactantes": 1}, Prioridad.ALTA),
            ({**solo_adultos, "mayores_m": 1, "mayores_dependientes": 1}, Prioridad.ALTA),
            ({**solo_adultos, "embarazo": True}, Prioridad.ALTA),
            ({**solo_adultos, "electrodependiente": True}, Prioridad.ALTA),
            ({**solo_adultos, "medicacion_critica": True}, Prioridad.ALTA),
        ]
        for cambios, esperada in tabla:
            with self.subTest(cambios=cambios):
                self.assertEqual(self._caso(**cambios).prioridad, esperada)

    def test_sin_direccion_no_se_puede_enviar_aunque_haya_gps(self):
        """RN-1.12."""
        with self.assertRaises(ValidationError) as error:
            self._caso(direccion="  ", latitud=-27.45, longitud=-58.98)
        self.assertIn("direccion", error.exception.message_dict)

    def test_los_errores_llegan_todos_juntos_y_por_campo(self):
        with self.assertRaises(ValidationError) as error:
            self._caso(traslado="", dni="", direccion="", adultos_f=0, adultos_m=0)
        self.assertEqual(set(error.exception.message_dict), {"traslado", "dni", "direccion", "total"})

    def test_una_precision_del_gps_enorme_es_un_error_del_campo(self):
        """La columna es un entero de 32 bits: lo que no entra es un 400 del campo, no un 500."""
        for precision in (2_147_483_648, "1e30", float("inf")):
            with self.subTest(precision=precision):
                with self.assertRaises(ValidationError) as error:
                    self._caso(latitud=-27.45, longitud=-58.98, precision_m=precision)
                self.assertIn("precision_m", error.exception.message_dict)
        self.assertFalse(CasoEmergencia.objects.exists())
        caso = self._caso(latitud=-27.45, longitud=-58.98, precision_m=2_147_483_647)
        self.assertEqual(self._fila(caso)["precision_m"], 2_147_483_647)

    def test_otra_fuerza_pide_decir_cual(self):
        with self.assertRaises(ValidationError) as error:
            self._caso(traslado=GrupoFamiliar.Traslado.OTRA)
        self.assertIn("traslado_otro", error.exception.message_dict)
        caso = self._caso(traslado=GrupoFamiliar.Traslado.OTRA, traslado_otro="Gendarmería")
        self.assertEqual(caso.grupo.traslado_otro, "Gendarmería")

    def test_de_territorio_nace_nuevo_y_sin_tomar(self):
        """RN-1.10."""
        caso = self._caso(
            latitud=-27.451234,
            longitud=-58.986543,
            precision_m=35,
            telefono="3624 555555",
            observaciones="Agua al techo",
        )
        fila = self._fila(caso)

        self.assertEqual(fila["estado"], Estado.NUEVO)
        self.assertEqual(fila["origen"], Origen.TERRITORIO)
        self.assertIsNone(fila["tomado_por_id"])
        self.assertIsNone(fila["tomado_en"])
        self.assertEqual(fila["relevado_por_id"], self.agente.pk)
        self.assertEqual(fila["relevado_en"], T0)
        self.assertEqual(fila["latitud"], Decimal("-27.451234"))
        self.assertEqual(fila["precision_m"], 35)
        self.assertEqual(fila["situacion"], {"telefono": "3624 555555", "observaciones": "Agua al techo"})
        self.assertEqual(
            fila["necesidades"],
            {"embarazo": False, "electrodependiente": False, "medicacion_critica": False, "mascotas": False},
        )
        [traza] = self._trazas(caso)
        self.assertEqual((traza.accion, traza.estado_anterior, traza.estado_nuevo), (Accion.CREADO, "", Estado.NUEVO))
        self.assertEqual(traza.detalle, "Relevado en territorio")
        self.assertEqual(traza.usuario_id, self.agente.pk)

    def test_de_la_mesa_nace_tomado_por_quien_lo_carga(self):
        """HU-1.4."""
        caso = self._caso(origen=Origen.MESA)
        fila = self._fila(caso)

        self.assertEqual(fila["estado"], Estado.EN_GESTION)
        self.assertEqual(fila["tomado_por_id"], self.operador.pk)
        self.assertEqual(fila["tomado_en"], T0)
        self.assertEqual(fila["relevado_por_id"], self.operador.pk)
        self.assertEqual(self._trazas(caso)[0].detalle, "Cargado por la mesa")

    def test_quien_supervisa_tambien_carga_desde_la_mesa(self):
        caso = self._caso(origen=Origen.MESA, usuario=self.supervisor)
        self.assertEqual(caso.tomado_por_id, self.supervisor.pk)

    def test_el_ingreso_directo_queda_soportado_a_nivel_datos_y_sin_derivacion(self):
        guardia = self._usuario("guardia", ["dispositivo.admitir"], programa=self.dispositivos)
        caso = self._caso(origen=Origen.DISPOSITIVO, usuario=guardia)

        self.assertEqual(caso.origen, Origen.DISPOSITIVO)
        self.assertEqual(caso.estado, Estado.NUEVO)
        self.assertFalse(Derivacion.objects.exists())
        self.assertEqual(self._trazas(caso)[0].detalle, "Ingreso directo en el dispositivo")

    def test_cada_origen_pide_su_capacidad(self):
        """Tabla de RU §4: territorio el agente, mesa el operador, ingreso directo la guardia."""
        guardia = self._usuario("guardia", ["dispositivo.admitir"], programa=self.dispositivos)
        de_becas = self._usuario("de_becas", ["becas.campo"], programa=self.becas)
        prohibidos = [
            (Origen.TERRITORIO, self.operador),
            (Origen.TERRITORIO, self.supervisor),
            (Origen.TERRITORIO, guardia),
            (Origen.TERRITORIO, de_becas),
            (Origen.MESA, self.agente),
            (Origen.MESA, guardia),
            (Origen.MESA, de_becas),
            (Origen.DISPOSITIVO, self.agente),
            (Origen.DISPOSITIVO, self.operador),
            (Origen.DISPOSITIVO, de_becas),
        ]
        for origen, usuario in prohibidos:
            with self.subTest(origen=origen, usuario=usuario.username):
                with self.assertRaises(PermissionDenied):
                    self._caso(origen=origen, usuario=usuario)
        self.assertFalse(CasoEmergencia.objects.exists())

    def test_un_origen_que_no_existe_es_un_error_de_programacion(self):
        with self.assertRaises(ValueError):
            self._caso(origen="PORTAL")

    def test_el_responsable_que_ya_esta_en_el_legajo_se_reusa(self):
        """RN-1.5: por DNI, y sin tocarle nada."""
        persona = Ciudadano.objects.create(dni="28123456", nombre="Marta", apellido="Sosa")
        caso = self._caso(dni="28.123.456", nombre="Otro", apellido="Nombre", documento_extraviado=True)

        self.assertEqual(caso.grupo.responsable_id, persona.pk)
        persona.refresh_from_db()
        self.assertEqual((persona.nombre, persona.apellido, persona.dni_fisico), ("Marta", "Sosa", ""))
        self.assertEqual(Ciudadano.objects.filter(dni="28123456").count(), 1)
        self.assertTrue(caso.situacion["documento_extraviado"])

    def test_el_responsable_que_no_esta_se_da_de_alta_con_lo_minimo(self):
        caso = self._caso(dni="31222333", nombre="Rosa", apellido="Benítez")
        persona = caso.grupo.responsable

        self.assertEqual((persona.dni, persona.nombre, persona.apellido), ("31222333", "Rosa", "Benítez"))
        self.assertEqual(persona.genero, "")  # son dos: el sexo lo completa la ficha de la etapa 3
        self.assertEqual(persona.dni_fisico, "")

    def test_el_sexo_se_infiere_solo_si_la_familia_es_de_una_persona(self):
        sola = self._caso(adultos_f=0, adultos_m=0, mayores_f=1)
        solo = self._caso(adultos_f=0, adultos_m=1)
        self.assertEqual(sola.grupo.responsable.genero, Ciudadano.Genero.FEMENINO)
        self.assertEqual(solo.grupo.responsable.genero, Ciudadano.Genero.MASCULINO)

    def test_sin_nombre_no_se_da_de_alta_a_nadie(self):
        with self.assertRaises(ValidationError) as error:
            self._caso(dni="31222333", nombre="", apellido="")
        self.assertIn("nombre", error.exception.message_dict)
        self.assertFalse(Ciudadano.objects.filter(dni="31222333").exists())
        self.assertFalse(GrupoFamiliar.objects.exists())

    def test_un_dni_que_no_es_un_dni_no_da_de_alta_a_nadie(self):
        with self.assertRaises(ValidationError) as error:
            self._caso(dni="123")
        self.assertIn("dni", error.exception.message_dict)
        self.assertFalse(Ciudadano.objects.filter(dni="123").exists())

    def test_perdio_el_documento_pero_sabe_el_numero(self):
        """Hallazgo H5: es ``dni_fisico = NO_TIENE``, no un campo nuevo."""
        caso = self._caso(dni="31222333", documento_extraviado=True)
        self.assertEqual(caso.grupo.responsable.dni_fisico, Ciudadano.DniFisico.NO_TIENE)

    def test_el_numero_sale_del_numerador_del_anio(self):
        primero, segundo = self._caso(), self._caso()
        self.assertEqual((primero.numero, segundo.numero), ("2026-000001", "2026-000002"))

        self.reloj.ahora = timezone.make_aware(datetime(2027, 1, 1, 0, 30))
        self.assertEqual(self._caso().numero, "2027-000001")
        self.assertEqual(
            list(NumeradorEmergencia.objects.values_list("serie", "anio", "ultimo")), [("C", 2026, 2), ("C", 2027, 1)]
        )

    def test_la_serie_de_kits_tiene_su_propio_contador(self):
        self._caso()
        with transaction.atomic():
            numero = servicio.siguiente_numero(NumeradorEmergencia.Serie.KITS)
        self.assertEqual(numero, "2026-000001")
        self.assertEqual(NumeradorEmergencia.objects.get(serie="C").ultimo, 1)

    def test_un_caso_rechazado_no_gasta_numero(self):
        with self.assertRaises(ValidationError):
            self._caso(direccion="")
        self.assertEqual(self._caso().numero, "2026-000001")

    def test_la_hora_del_telefono_se_guarda_aparte_de_la_del_servidor(self):
        """RN-1.8 / RU-18: ``relevado_en`` es del cliente; ``creado`` es del servidor."""
        en_el_lugar = T0 - timedelta(hours=1, minutes=45)
        caso = self._caso(relevado_en=en_el_lugar)
        self.assertEqual(caso.relevado_en, en_el_lugar)
        self.assertEqual(caso.creado, T0)

    def test_la_localidad_es_una_fk_y_una_que_no_existe_se_rechaza(self):
        """RN-1.6."""
        localidad = Localidad.objects.create(nombre="Resistencia")
        self.assertEqual(self._caso(localidad=localidad.pk).localidad_id, localidad.pk)
        self.assertEqual(self._caso(localidad=localidad).localidad_id, localidad.pk)
        with self.assertRaises(ValidationError) as error:
            self._caso(localidad=999_999)
        self.assertIn("localidad", error.exception.message_dict)

    def test_sin_gps_los_tres_datos_quedan_nulos(self):
        """RN-1.7."""
        fila = self._fila(self._caso(precision_m=20))
        self.assertEqual((fila["latitud"], fila["longitud"], fila["precision_m"]), (None, None, None))

    def test_un_agente_puede_cargar_dos_veces_a_la_misma_familia(self):
        """RN-1.11: el servidor no lo bloquea; la mesa lo ve como posible duplicado."""
        primero = self._caso(dni="31222333")
        segundo = self._caso(dni="31222333")
        self.assertNotEqual(primero.pk, segundo.pk)
        self.assertEqual(primero.grupo.responsable_id, segundo.grupo.responsable_id)


class IdempotenciaTests(BaseCasos):
    """RU-16 / RN-1.8: el mismo ``uuid_cliente`` dos veces es un solo caso."""

    def test_el_mismo_envio_dos_veces_crea_un_caso(self):
        envio = uuid.uuid4()
        datos = self._datos()
        primero = servicio.crear_caso(
            usuario=self.agente, origen=Origen.TERRITORIO, datos_formulario1=datos, uuid_cliente=envio
        )
        self.reloj.avanzar(minutes=30)
        segundo = servicio.crear_caso(
            usuario=self.agente, origen=Origen.TERRITORIO, datos_formulario1=datos, uuid_cliente=str(envio)
        )

        self.assertFalse(primero.ya_existia)
        self.assertTrue(segundo.ya_existia)
        self.assertEqual(segundo.pk, primero.pk)
        self.assertEqual(segundo.numero, primero.numero)
        self.assertEqual(CasoEmergencia.objects.count(), 1)
        self.assertEqual(GrupoFamiliar.objects.count(), 1)
        self.assertEqual(TrazaCaso.objects.count(), 1)
        self.assertEqual(NumeradorEmergencia.objects.get(serie="C").ultimo, 1)

    def test_el_reenvio_devuelve_el_caso_aunque_ya_no_valide(self):
        """Lo que se devuelve es lo que quedó: un reenvío no se vuelve a juzgar."""
        envio = uuid.uuid4()
        primero = self._caso(uuid_cliente=envio)
        segundo = servicio.crear_caso(
            usuario=self.agente, origen=Origen.TERRITORIO, datos_formulario1={}, uuid_cliente=envio
        )
        self.assertEqual(segundo.pk, primero.pk)

    def test_se_encuentra_en_cualquiera_de_las_dos_formas_del_uuid(self):
        """MariaDB guarda el UUID con guiones y MySQL en hex: se busca por las dos."""
        envio = uuid.uuid4()
        primero = self._caso(uuid_cliente=envio)
        for forma in (envio.hex, str(envio), str(envio).upper()):
            with self.subTest(forma=forma):
                self.assertEqual(self._caso(uuid_cliente=forma).pk, primero.pk)

    def test_el_identificador_de_otro_usuario_no_devuelve_un_caso_ajeno(self):
        envio = uuid.uuid4()
        self._caso(uuid_cliente=envio)
        otro_agente = self._usuario("otro_agente", [RELEVAR])

        with self.assertRaises(ValidationError) as error:
            self._caso(usuario=otro_agente, uuid_cliente=envio)
        self.assertIn("uuid_cliente", error.exception.message_dict)
        self.assertEqual(CasoEmergencia.objects.count(), 1)

    def test_un_identificador_que_no_es_un_uuid_se_rechaza(self):
        with self.assertRaises(ValidationError) as error:
            self._caso(uuid_cliente="no-es-un-uuid")
        self.assertIn("uuid_cliente", error.exception.message_dict)

    def test_si_el_unique_salta_en_el_alta_se_devuelve_el_que_gano(self):
        """La carrera del mismo envío llegando dos veces a la vez, sin hilos.

        El segundo no vio al primero en la búsqueda inicial y choca recién en el ``INSERT``:
        tiene que devolver el caso que ganó, sin gastar número ni dejar un grupo huérfano.
        """
        envio = uuid.uuid4()
        ganador = self._caso(uuid_cliente=envio)
        busqueda = servicio._caso_de_ese_envio
        llamadas = []

        def no_lo_ve_la_primera_vez(uuid_cliente, usuario):
            llamadas.append(uuid_cliente)
            return None if len(llamadas) == 1 else busqueda(uuid_cliente, usuario)

        # Se parcha donde se usa: `crear_caso` vive en `emergencia_alta`.
        with mock.patch.object(emergencia_alta, "_caso_de_ese_envio", no_lo_ve_la_primera_vez):
            segundo = self._caso(uuid_cliente=envio)

        self.assertEqual(segundo.pk, ganador.pk)
        self.assertTrue(segundo.ya_existia)
        self.assertEqual(len(llamadas), 2)
        self.assertEqual(CasoEmergencia.objects.count(), 1)
        self.assertEqual(GrupoFamiliar.objects.count(), 1)
        self.assertEqual(NumeradorEmergencia.objects.get(serie="C").ultimo, 1)


class FotosDelCasoTests(BaseCasos):
    def setUp(self):
        super().setUp()
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)
        ajuste = override_settings(MEDIA_ROOT=self.media)
        ajuste.enable()
        self.addCleanup(ajuste.disable)

    def _foto(self, nombre="vivienda.jpg", contenido=JPEG):
        return SimpleUploadedFile(nombre, contenido, content_type="image/jpeg")

    def test_las_fotos_quedan_bajo_la_carpeta_opaca_del_caso(self):
        caso = self._caso(fotos={"VIVIENDA": self._foto(), "ACCESO": self._foto("acceso.jpg")})
        adjuntos = list(AdjuntoCaso.objects.filter(caso=caso).order_by("tipo"))

        self.assertEqual([adjunto.tipo for adjunto in adjuntos], ["ACCESO", "VIVIENDA"])
        for adjunto in adjuntos:
            self.assertTrue(adjunto.archivo.name.startswith(f"emergencia/casos/{caso.carpeta_media}/"))
            self.assertNotIn("vivienda", adjunto.archivo.name)
            self.assertNotIn("acceso", adjunto.archivo.name)
            self.assertEqual(adjunto.cargado_por_id, self.agente.pk)
        self.assertRegex(caso.carpeta_media, r"^[0-9a-f]{32}$")

    def test_un_archivo_que_no_es_una_foto_deshace_el_caso_entero(self):
        with self.assertRaises(ValidationError):
            self._caso(fotos={"VIVIENDA": self._foto(), "ACCESO": self._foto("acta.pdf", b"%PDF-1.4")})

        self.assertFalse(CasoEmergencia.objects.exists())
        self.assertFalse(AdjuntoCaso.objects.exists())

    def test_una_ruta_o_un_archivo_ya_guardado_no_es_una_foto(self):
        """Solo entra la subida: una ruta colgaría del caso un archivo que ya está en el disco."""
        guardado = self._foto()
        guardado._committed = True
        for foto in ("emergencia/casos/otro/vivienda.jpg", "/etc/passwd", guardado):
            with self.subTest(foto=foto):
                with self.assertRaises(ValidationError) as error:
                    self._caso(fotos={"VIVIENDA": foto})
                self.assertIn("fotos", error.exception.message_dict)

        self.assertFalse(CasoEmergencia.objects.exists())
        self.assertFalse(GrupoFamiliar.objects.exists())
        self.assertFalse(AdjuntoCaso.objects.exists())
        self.assertFalse(NumeradorEmergencia.objects.filter(ultimo__gt=0).exists())

    def test_una_foto_invalida_llega_junto_con_los_otros_errores(self):
        with self.assertRaises(ValidationError) as error:
            self._caso(direccion="", fotos={"ACCESO": self._foto("acta.pdf", b"%PDF-1.4")})

        self.assertEqual(set(error.exception.message_dict), {"direccion", "fotos"})
        self.assertFalse(NumeradorEmergencia.objects.filter(ultimo__gt=0).exists())

    def test_un_tipo_de_foto_que_no_existe_se_rechaza(self):
        with self.assertRaises(ValidationError) as error:
            self._caso(fotos={"REMITO": self._foto()})
        self.assertIn("fotos", error.exception.message_dict)

    def test_la_foto_la_baja_la_mesa_y_no_un_rol_de_otro_programa(self):
        """RU-17: detrás de login y con la capacidad de la mesa."""
        from core.views.media import _autorizar

        caso = self._caso(fotos={"VIVIENDA": self._foto()})
        ruta = AdjuntoCaso.objects.get(caso=caso).archivo.name
        de_becas = self._usuario("de_becas", ["becas.campo"], programa=self.becas)

        self.assertTrue(_autorizar(self.operador, ruta))
        self.assertTrue(_autorizar(self.supervisor, ruta))
        self.assertFalse(_autorizar(self.agente, ruta))
        self.assertFalse(_autorizar(de_becas, ruta))
        self.assertIsNone(_autorizar(self.operador, "emergencia/casos/no-existe/x.jpg"))


# ---------------------------------------------------------------------------
# Tomar, soltar, reasignar
# ---------------------------------------------------------------------------


class TomarCasoTests(BaseCasos):
    def test_tomar_un_caso_nuevo(self):
        """HU-2.1."""
        caso = self._caso()
        self.reloj.avanzar(minutes=4)
        tomado = servicio.tomar_caso(caso, self.operador)
        fila = self._fila(caso)

        self.assertEqual(tomado.estado, Estado.EN_GESTION)
        self.assertEqual(fila["estado"], Estado.EN_GESTION)
        self.assertEqual(fila["tomado_por_id"], self.operador.pk)
        self.assertEqual(fila["tomado_en"], T0 + timedelta(minutes=4))
        traza = self._trazas(caso)[-1]
        self.assertEqual(
            (traza.accion, traza.estado_anterior, traza.estado_nuevo), (Accion.TOMADO, Estado.NUEVO, Estado.EN_GESTION)
        )
        self.assertEqual(traza.detalle, "Tomado por Ana López")
        self.assertFalse(traza.por_supervisor)

    def test_dos_operadores_toman_el_mismo_caso_y_gana_uno(self):
        """**Mutación RU §6 n.° 4 / RN-2.1.**

        Los dos operadores tienen el caso en pantalla como ``NUEVO`` (dos objetos leídos
        antes de que nadie lo tome). El primero gana; el segundo recibe
        ``CasoTomadoPorOtro`` y la fila no cambia.

        Se vio en rojo rompiendo la guarda: con ``tomar_caso`` decidiendo sobre el objeto
        que le llega en vez de sobre la fila bloqueada (``caso = _bloquear_caso(caso)``
        comentado), el segundo operador también tomaba y este test fallaba con
        «CasoTomadoPorOtro not raised» y el caso a nombre de Juan. La carrera con dos
        conexiones es ``test_emergencia_concurrencia.CarreraDeTomarTests``.
        """
        caso = self._caso()
        en_la_pantalla_de_ana = CasoEmergencia.objects.get(pk=caso.pk)
        en_la_pantalla_de_juan = CasoEmergencia.objects.get(pk=caso.pk)

        servicio.tomar_caso(en_la_pantalla_de_ana, self.operador)
        self.reloj.avanzar(minutes=1)
        with self.assertRaises(CasoTomadoPorOtro) as error:
            servicio.tomar_caso(en_la_pantalla_de_juan, self.otro_operador)

        self.assertEqual(error.exception.tomado_por.pk, self.operador.pk)
        self.assertEqual(error.exception.tomado_en, T0)
        self.assertEqual(error.exception.estado_actual, Estado.EN_GESTION)
        self.assertIn("Ana López", error.exception.mensaje)
        fila = self._fila(caso)
        self.assertEqual((fila["tomado_por_id"], fila["tomado_en"]), (self.operador.pk, T0))
        self.assertEqual([traza.accion for traza in self._trazas(caso)], [Accion.CREADO, Accion.TOMADO])

    def test_el_perdedor_es_un_estado_cambio_para_quien_solo_atrapa_ese(self):
        caso = self._caso_tomado()
        with self.assertRaises(EstadoCambio):
            servicio.tomar_caso(caso, self.otro_operador)

    def test_volver_a_tomar_lo_que_ya_tengo_no_hace_nada(self):
        caso = self._caso_tomado()
        self.reloj.avanzar(minutes=10)
        otra_vez = servicio.tomar_caso(caso, self.operador)

        self.assertEqual(otra_vez.tomado_en, T0)
        self.assertEqual(len(self._trazas(caso)), 2)

    def test_quien_supervisa_tambien_puede_tomar(self):
        caso = servicio.tomar_caso(self._caso(), self.supervisor)
        self.assertEqual(caso.tomado_por_id, self.supervisor.pk)

    def test_sin_la_capacidad_de_la_mesa_no_se_toma(self):
        caso = self._caso()
        de_becas = self._usuario("de_becas", ["becas.campo"], programa=self.becas)
        for usuario in (self.agente, de_becas):
            with self.subTest(usuario=usuario.username):
                with self.assertRaises(PermissionDenied):
                    servicio.tomar_caso(caso, usuario)
        self.assertEqual(self._fila(caso)["estado"], Estado.NUEVO)


class SoltarCasoTests(BaseCasos):
    def test_el_duenio_suelta_y_la_marca_se_conserva(self):
        """RN-2.9: ``tomado_en`` no se borra."""
        caso = self._caso_tomado()
        self.reloj.avanzar(minutes=20)
        servicio.soltar_caso(caso, self.operador)
        fila = self._fila(caso)

        self.assertEqual(fila["estado"], Estado.NUEVO)
        self.assertIsNone(fila["tomado_por_id"])
        self.assertEqual(fila["tomado_en"], T0)
        traza = self._trazas(caso)[-1]
        self.assertEqual(
            (traza.accion, traza.estado_anterior, traza.estado_nuevo), (Accion.SOLTADO, Estado.EN_GESTION, Estado.NUEVO)
        )
        self.assertFalse(traza.por_supervisor)

    def test_retomar_no_pisa_la_primera_marca(self):
        """RN-2.9: el tramo corre desde la primera vez que alguien lo tomó."""
        caso = self._caso_tomado()
        self.reloj.avanzar(minutes=20)
        servicio.soltar_caso(caso, self.operador)
        self.reloj.avanzar(minutes=20)
        servicio.tomar_caso(caso, self.otro_operador)
        fila = self._fila(caso)

        self.assertEqual(fila["tomado_por_id"], self.otro_operador.pk)
        self.assertEqual(fila["tomado_en"], T0)

    def test_otro_operador_no_suelta_un_caso_ajeno(self):
        """RU-12."""
        caso = self._caso_tomado()
        with self.assertRaises(PermissionDenied):
            servicio.soltar_caso(caso, self.otro_operador)
        self.assertEqual(self._fila(caso)["tomado_por_id"], self.operador.pk)

    def test_quien_supervisa_suelta_cualquiera_y_la_traza_lo_dice(self):
        """RU-13."""
        caso = self._caso_tomado()
        servicio.soltar_caso(caso, self.supervisor)
        traza = self._trazas(caso)[-1]

        self.assertIsNone(self._fila(caso)["tomado_por_id"])
        self.assertTrue(traza.por_supervisor)
        self.assertEqual(traza.usuario_id, self.supervisor.pk)
        self.assertEqual(traza.detalle, "Devuelto a la bandeja (lo tenía Ana López) · por supervisor")

    def test_un_caso_que_no_esta_en_gestion_no_se_suelta(self):
        caso = self._caso()
        with self.assertRaises(EstadoCambio) as error:
            servicio.soltar_caso(caso, self.supervisor)
        self.assertEqual(error.exception.estado_actual, Estado.NUEVO)


class ReasignarCasoTests(BaseCasos):
    def test_operar_sin_supervisar_no_reasigna(self):
        """**Mutación RU §6 n.° 1.**

        Un operador —el dueño del caso, que es el que más motivo tendría— intenta pasárselo
        a otro. ``PermissionDenied`` y la fila no cambia.

        Se vio en rojo contra la regla invertida: con la guarda de ``reasignar_caso``
        cambiada a ``puede_operar_la_mesa`` (la que usan todas las demás acciones), el
        operador reasignaba y este test fallaba con «PermissionDenied not raised».
        """
        caso = self._caso_tomado()
        antes = self._fila(caso)

        for usuario in (self.operador, self.otro_operador, self.agente):
            with self.subTest(usuario=usuario.username):
                with self.assertRaises(PermissionDenied):
                    servicio.reasignar_caso(caso, usuario, self.otro_operador)

        self.assertEqual(self._fila(caso), antes)
        self.assertEqual(len(self._trazas(caso)), 2)

    def test_quien_supervisa_reasigna_y_el_reloj_no_se_reinicia(self):
        """HU-2.6 / RN-2.9."""
        caso = self._caso_tomado()
        self.reloj.avanzar(minutes=25)
        servicio.reasignar_caso(caso, self.supervisor, self.otro_operador)
        fila = self._fila(caso)
        traza = self._trazas(caso)[-1]

        self.assertEqual(fila["tomado_por_id"], self.otro_operador.pk)
        self.assertEqual(fila["estado"], Estado.EN_GESTION)
        self.assertEqual(fila["tomado_en"], T0)
        self.assertEqual(traza.accion, Accion.REASIGNADO)
        self.assertEqual(traza.detalle, "Reasignado de Ana López a Juan Pérez · por supervisor")
        self.assertTrue(traza.por_supervisor)

    def test_reasignar_un_caso_nuevo_lo_deja_en_gestion(self):
        caso = self._caso()
        self.reloj.avanzar(minutes=3)
        servicio.reasignar_caso(caso, self.supervisor, self.operador)
        fila = self._fila(caso)

        self.assertEqual((fila["estado"], fila["tomado_por_id"]), (Estado.EN_GESTION, self.operador.pk))
        self.assertEqual(fila["tomado_en"], T0 + timedelta(minutes=3))
        self.assertEqual(self._trazas(caso)[-1].detalle, "Reasignado de nadie a Ana López · por supervisor")

    def test_reasignar_un_caso_derivado_solo_cambia_quien_lo_tiene(self):
        caso = self._caso_tomado()
        servicio.derivar_caso(caso, self.operador, self._dispositivo("Club", camas=5), 2)
        self.reloj.avanzar(minutes=30)
        servicio.reasignar_caso(caso, self.supervisor, self.otro_operador)
        fila = self._fila(caso)

        self.assertEqual((fila["estado"], fila["tomado_por_id"]), (Estado.DERIVADO, self.otro_operador.pk))
        self.assertEqual((fila["tomado_en"], fila["derivado_en"]), (T0, T0))

    def test_solo_se_reasigna_a_alguien_de_la_mesa(self):
        caso = self._caso_tomado()
        inactivo = self._usuario("inactivo", [OPERAR])
        User.objects.filter(pk=inactivo.pk).update(is_active=False)
        for destino in (self.agente, inactivo, 999_999):
            with self.subTest(destino=destino):
                with self.assertRaises(ValidationError) as error:
                    servicio.reasignar_caso(caso, self.supervisor, destino)
                self.assertIn("operador", error.exception.message_dict)
        self.assertEqual(self._fila(caso)["tomado_por_id"], self.operador.pk)

    def test_reasignar_a_quien_ya_lo_tiene_no_deja_traza(self):
        caso = self._caso_tomado()
        with self.assertRaises(ValidationError):
            servicio.reasignar_caso(caso, self.supervisor, self.operador)
        self.assertEqual(len(self._trazas(caso)), 2)


# ---------------------------------------------------------------------------
# Prioridad y contactos
# ---------------------------------------------------------------------------


class PrioridadTests(BaseCasos):
    def test_cambiar_la_prioridad_deja_el_valor_anterior_y_el_nuevo(self):
        """RN-2.11."""
        caso = self._caso_tomado()
        servicio.cambiar_prioridad(caso, self.operador, Prioridad.ALTA)
        traza = self._trazas(caso)[-1]

        self.assertEqual(self._fila(caso)["prioridad"], Prioridad.ALTA)
        self.assertEqual(traza.accion, Accion.PRIORIDAD)
        self.assertEqual(traza.detalle, "Prioridad: Baja → Alta")
        self.assertEqual((traza.estado_anterior, traza.estado_nuevo), (Estado.EN_GESTION, Estado.EN_GESTION))

    def test_la_misma_prioridad_no_deja_traza(self):
        caso = self._caso_tomado()
        servicio.cambiar_prioridad(caso, self.operador, Prioridad.BAJA)
        self.assertEqual(len(self._trazas(caso)), 2)

    def test_la_prioridad_no_cambia_nada_mas(self):
        caso = self._caso_tomado()
        antes = self._fila(caso)
        servicio.cambiar_prioridad(caso, self.operador, Prioridad.ALTA)
        despues = self._fila(caso)
        distintos = {campo for campo in antes if antes[campo] != despues[campo]}
        self.assertEqual(distintos, {"prioridad"})

    def test_el_que_no_lo_tiene_tomado_no_la_cambia_y_quien_supervisa_si(self):
        """RU-12 y RU-13, también sobre un caso que nadie tomó."""
        for caso in (self._caso_tomado(), self._caso()):
            with self.subTest(estado=caso.estado):
                with self.assertRaises(PermissionDenied):
                    servicio.cambiar_prioridad(caso, self.otro_operador, Prioridad.ALTA)
                self.assertEqual(self._fila(caso)["prioridad"], Prioridad.BAJA)

                servicio.cambiar_prioridad(caso, self.supervisor, Prioridad.ALTA)
                self.assertEqual(self._fila(caso)["prioridad"], Prioridad.ALTA)
                self.assertTrue(self._trazas(caso)[-1].por_supervisor)

    def test_una_prioridad_que_no_existe_se_rechaza(self):
        with self.assertRaises(ValidationError):
            servicio.cambiar_prioridad(self._caso_tomado(), self.operador, "URGENTE")


class ContactoTests(BaseCasos):
    def test_registrar_un_contacto(self):
        """HU-2.4 / RN-2.12."""
        caso = self._caso_tomado()
        self.reloj.avanzar(minutes=7)
        contacto = servicio.registrar_contacto(
            caso, self.operador, canal="WHATSAPP", resultado="NO_ATENDIO", observacion="  Dejé mensaje  "
        )
        traza = self._trazas(caso)[-1]

        self.assertEqual(ContactoCaso.objects.filter(caso=caso).count(), 1)
        self.assertEqual((contacto.canal, contacto.resultado), ("WHATSAPP", "NO_ATENDIO"))
        self.assertEqual(contacto.observacion, "Dejé mensaje")
        self.assertEqual(contacto.por_id, self.operador.pk)
        self.assertEqual(contacto.momento, T0 + timedelta(minutes=7))
        self.assertEqual((traza.accion, traza.detalle), (Accion.CONTACTO, "WhatsApp · No atendió"))

    def test_los_cuatro_canales_y_los_cuatro_resultados(self):
        self.assertEqual(set(ContactoCaso.Canal.values), {"LLAMADA", "WHATSAPP", "SMS", "PRESENCIAL"})
        self.assertEqual(set(ContactoCaso.Resultado.values), {"ATENDIO", "NO_ATENDIO", "NUMERO_ERRONEO", "OTRO"})

    def test_un_canal_que_no_existe_no_deja_ni_contacto_ni_traza(self):
        caso = self._caso_tomado()
        with self.assertRaises(ValidationError):
            servicio.registrar_contacto(caso, self.operador, canal="PALOMA", resultado="ATENDIO")
        self.assertFalse(ContactoCaso.objects.exists())
        self.assertEqual(len(self._trazas(caso)), 2)

    def test_el_que_no_lo_tiene_tomado_no_registra_y_quien_supervisa_si(self):
        caso = self._caso_tomado()
        with self.assertRaises(PermissionDenied):
            servicio.registrar_contacto(caso, self.otro_operador, canal="LLAMADA", resultado="ATENDIO")
        contacto = servicio.registrar_contacto(caso, self.supervisor, canal="LLAMADA", resultado="ATENDIO")

        self.assertEqual(contacto.por_id, self.supervisor.pk)
        self.assertTrue(self._trazas(caso)[-1].por_supervisor)


# ---------------------------------------------------------------------------
# Derivar y cancelar
# ---------------------------------------------------------------------------


class DerivarCasoTests(BaseCasos):
    def test_derivar_deja_el_caso_derivado_con_una_derivacion_pendiente(self):
        """HU-2.3."""
        caso = self._caso_tomado(menores_f=1)
        dispositivo = self._dispositivo("Club Sarmiento", camas=10)
        self.reloj.avanzar(minutes=18)
        derivacion = servicio.derivar_caso(caso, self.operador, dispositivo, 3)
        fila = self._fila(caso)
        traza = self._trazas(caso)[-1]

        self.assertEqual(fila["estado"], Estado.DERIVADO)
        self.assertEqual(fila["derivado_en"], T0 + timedelta(minutes=18))
        self.assertEqual(fila["tomado_por_id"], self.operador.pk)
        self.assertEqual(derivacion.estado, Derivacion.Estado.PENDIENTE)
        self.assertEqual((derivacion.dispositivo_id, derivacion.plazas_pedidas), (dispositivo.pk, 3))
        self.assertEqual(derivacion.derivada_por_id, self.operador.pk)
        self.assertEqual(derivacion.clave_vigente, caso.pk)
        self.assertEqual(
            (traza.accion, traza.estado_anterior, traza.estado_nuevo),
            (Accion.DERIVADO, Estado.EN_GESTION, Estado.DERIVADO),
        )
        self.assertEqual(traza.detalle, "Derivado a Club Sarmiento · 3 plazas pedidas")

    def test_vence_cuando_dice_la_configuracion_vigente(self):
        """RN-2.7: ahora más ``vigencia_derivacion_min`` de E7."""
        SLAEmergencia.objects.filter(programa=self.programa).update(vigencia_derivacion_min=90)
        caso = self._caso_tomado()
        derivacion = servicio.derivar_caso(caso, self.operador, self._dispositivo("Club", camas=5), 2)
        self.assertEqual(derivacion.vence_en, T0 + timedelta(minutes=90))

    def test_derivar_no_reserva_plazas(self):
        """02 §7: la reserva la hace el dispositivo al aceptar."""
        caso = self._caso_tomado()
        dispositivo = self._dispositivo("Club", camas=5)
        servicio.derivar_caso(caso, self.operador, dispositivo, 2)

        self.assertFalse(ReservaPlaza.objects.exists())
        self.assertEqual(selectores.ocupacion_de_plazas(dispositivo).de(dispositivo).conteo.disponibles, 5)

    def test_sin_plazas_libres_no_se_deriva(self):
        """RN-2.5."""
        caso = self._caso_tomado()
        lleno = self._dispositivo("Lleno", camas=2)
        self._ocupar(lleno, 2)

        for confirmar in (False, True):
            with self.subTest(confirmar=confirmar):
                with self.assertRaises(ValidationError) as error:
                    servicio.derivar_caso(caso, self.operador, lleno, 2, confirmar_faltantes=confirmar)
                self.assertNotIsInstance(error.exception, FaltanPlazas)
        self.assertEqual(self._fila(caso)["estado"], Estado.EN_GESTION)
        self.assertFalse(Derivacion.objects.exists())

    def test_con_menos_plazas_que_las_pedidas_hay_que_confirmar(self):
        """RN-2.5: 5 libres para 7 pide confirmación, y ``plazas_pedidas`` guarda lo pedido."""
        caso = self._caso_tomado()
        dispositivo = self._dispositivo("Club", camas=8)
        self._ocupar(dispositivo, 3)

        with self.assertRaises(FaltanPlazas) as error:
            servicio.derivar_caso(caso, self.operador, dispositivo, 7)
        self.assertEqual((error.exception.libres, error.exception.pedidas, error.exception.faltan), (5, 7, 2))
        self.assertEqual(self._fila(caso)["estado"], Estado.EN_GESTION)
        self.assertFalse(Derivacion.objects.exists())

        derivacion = servicio.derivar_caso(caso, self.operador, dispositivo, 7, confirmar_faltantes=True)
        self.assertEqual(derivacion.plazas_pedidas, 7)
        self.assertEqual(self._trazas(caso)[-1].detalle, "Derivado a Club · 7 plazas pedidas · faltan 2")

    def test_pedir_menos_de_una_plaza_se_rechaza(self):
        caso = self._caso_tomado()
        dispositivo = self._dispositivo("Club", camas=5)
        for pedidas in (0, -1, "", None, "muchas"):
            with self.subTest(pedidas=pedidas):
                with self.assertRaises(ValidationError) as error:
                    servicio.derivar_caso(caso, self.operador, dispositivo, pedidas)
                self.assertIn("plazas_pedidas", error.exception.message_dict)

    def test_solo_se_deriva_a_un_dispositivo_elegible(self):
        """RN-2.2 / hallazgo H6: activo, de un tipo activo que maneja plazas y admite camas."""
        caso = self._caso_tomado()
        solo_cupos = TipoDispositivo.objects.create(codigo="COMEDOR", nombre="Comedor", tipos_plaza_admitidos=["CUPO"])
        sin_plazas = TipoDispositivo.objects.create(codigo="OFICINA", nombre="Oficina")
        dado_de_baja = TipoDispositivo.objects.create(
            codigo="VIEJO", nombre="Tipo viejo", tipos_plaza_admitidos=["CAMA"], activo=False
        )
        no_elegibles = [
            self._dispositivo("Inactivo", camas=5, estado=Dispositivo.Estado.INACTIVO),
            self._dispositivo("Borrador", camas=5, estado=Dispositivo.Estado.BORRADOR),
            self._dispositivo("Comedor", tipo=solo_cupos),
            self._dispositivo("Oficina", tipo=sin_plazas),
            self._dispositivo("De un tipo dado de baja", camas=5, tipo=dado_de_baja),
        ]
        for dispositivo in no_elegibles:
            with self.subTest(dispositivo=dispositivo.nombre):
                self.assertFalse(selectores.dispositivo_elegible(dispositivo))
                with self.assertRaises(ValidationError) as error:
                    servicio.derivar_caso(caso, self.operador, dispositivo, 1)
                self.assertIn("dispositivo", error.exception.message_dict)
        self.assertFalse(Derivacion.objects.exists())

    def test_un_tipo_que_admite_camas_y_cupos_es_elegible(self):
        mixto = TipoDispositivo.objects.create(codigo="MIXTO", nombre="Mixto", tipos_plaza_admitidos=["CUPO", "CAMA"])
        obliga = TipoDispositivo.objects.create(codigo="PARADOR", nombre="Parador", plaza_obligatoria_al_ingresar=True)
        self.assertTrue(selectores.dispositivo_elegible(self._dispositivo("Mixto", tipo=mixto)))
        self.assertTrue(selectores.dispositivo_elegible(self._dispositivo("Parador", tipo=obliga)))

    def test_la_segunda_pestana_recibe_a_donde_y_a_que_hora_se_derivo(self):
        """02 §9: 409 «El caso ya fue derivado a X a las 14:22. Recargá la ficha»."""
        caso = self._caso_tomado()
        club = self._dispositivo("Club Sarmiento", camas=5)
        escuela = self._dispositivo("Escuela 12", camas=5)
        en_la_otra_pestana = CasoEmergencia.objects.get(pk=caso.pk)
        self.reloj.ahora = timezone.make_aware(datetime(2026, 11, 12, 14, 22))
        servicio.derivar_caso(caso, self.operador, club, 2)

        with self.assertRaises(EstadoCambio) as error:
            servicio.derivar_caso(en_la_otra_pestana, self.operador, escuela, 2)

        self.assertEqual(error.exception.estado_actual, Estado.DERIVADO)
        self.assertEqual(
            error.exception.mensaje, "El caso ya fue derivado a Club Sarmiento a las 14:22. Recargá la ficha."
        )
        self.assertEqual(Derivacion.objects.filter(caso=caso).count(), 1)

    def test_la_segunda_derivacion_vigente_choca_con_el_unique_y_es_un_estado_cambio(self):
        """RN-2.6: el ``IntegrityError`` de ``clave_vigente`` nunca llega crudo.

        El caso dice «en gestión» pero la base ya tiene una derivación vigente (lo que deja
        una carrera que el candado no cubrió): la rechaza el UNIQUE y el servicio lo
        traduce. La transacción sigue sana: el caso no cambió y se puede seguir leyendo.
        """
        caso = self._caso_tomado()
        club = self._dispositivo("Club", camas=5)
        Derivacion.objects.create(
            caso=caso, dispositivo=club, plazas_pedidas=2, vence_en=T0 + timedelta(hours=12), derivada_por=self.operador
        )

        with self.assertRaises(EstadoCambio) as error:
            servicio.derivar_caso(caso, self.operador, self._dispositivo("Escuela", camas=5), 2)

        self.assertIn("derivación vigente", error.exception.mensaje)
        self.assertEqual(self._fila(caso)["estado"], Estado.EN_GESTION)
        self.assertEqual(Derivacion.objects.filter(caso=caso).count(), 1)
        self.assertEqual([traza.accion for traza in self._trazas(caso)], [Accion.CREADO, Accion.TOMADO])

    def test_el_que_no_lo_tiene_tomado_no_deriva_y_quien_supervisa_si(self):
        """RU-12 y RU-13."""
        caso = self._caso_tomado()
        dispositivo = self._dispositivo("Club", camas=5)
        with self.assertRaises(PermissionDenied):
            servicio.derivar_caso(caso, self.otro_operador, dispositivo, 2)
        self.assertFalse(Derivacion.objects.exists())

        derivacion = servicio.derivar_caso(caso, self.supervisor, dispositivo, 2)
        traza = self._trazas(caso)[-1]
        self.assertEqual(derivacion.derivada_por_id, self.supervisor.pk)
        self.assertEqual(self._fila(caso)["tomado_por_id"], self.operador.pk)  # actúa sin tomarlo
        self.assertTrue(traza.por_supervisor)
        self.assertEqual(traza.detalle, "Derivado a Club · 2 plazas pedidas · por supervisor")

    def test_un_caso_nuevo_no_se_deriva(self):
        caso = self._caso()
        with self.assertRaises(EstadoCambio) as error:
            servicio.derivar_caso(caso, self.supervisor, self._dispositivo("Club", camas=5), 2)
        self.assertEqual(error.exception.estado_actual, Estado.NUEVO)

    def test_que_el_responsable_ya_este_alojado_no_bloquea_derivar(self):
        """RN-2.15: es una marca, no una regla."""
        caso = self._caso_tomado()
        donde_esta = self._dispositivo("Parador", camas=2)
        Estadia.objects.create(
            ciudadano=caso.grupo.responsable,
            dispositivo=donde_esta,
            fecha_ingreso=T0 - timedelta(days=2),
            clave_alojamiento=Estadia.clave_para(caso.grupo.responsable),
        )

        derivacion = servicio.derivar_caso(caso, self.operador, self._dispositivo("Club", camas=5), 2)
        self.assertEqual(derivacion.estado, Derivacion.Estado.PENDIENTE)


class CancelarDerivacionTests(BaseCasos):
    def setUp(self):
        super().setUp()
        self.caso = self._caso_tomado()
        self.club = self._dispositivo("Club Sarmiento", camas=5)
        self.derivacion = servicio.derivar_caso(self.caso, self.operador, self.club, 2)

    def test_cancelar_devuelve_el_caso_a_gestion_con_el_mismo_duenio(self):
        """HU-2.3."""
        self.reloj.avanzar(minutes=40)
        cancelada = servicio.cancelar_derivacion(self.derivacion, self.operador, "  La familia se fue con parientes ")
        fila = self._fila(self.caso)
        traza = self._trazas(self.caso)[-1]

        self.assertEqual(cancelada.estado, Derivacion.Estado.CANCELADA)
        self.assertIsNone(cancelada.clave_vigente)
        self.assertEqual(cancelada.motivo, "La familia se fue con parientes")
        self.assertEqual((cancelada.respondida_por_id, cancelada.respondida_en), (self.operador.pk, self.reloj.ahora))
        self.assertEqual((fila["estado"], fila["tomado_por_id"]), (Estado.EN_GESTION, self.operador.pk))
        self.assertEqual(
            (traza.accion, traza.estado_anterior, traza.estado_nuevo),
            (Accion.DERIVACION_CANCELADA, Estado.DERIVADO, Estado.EN_GESTION),
        )
        self.assertEqual(traza.detalle, "Derivación a Club Sarmiento cancelada: La familia se fue con parientes")

    def test_volver_de_una_cancelada_y_derivar_de_nuevo_no_pisa_la_marca(self):
        """RN-2.9: ``derivado_en`` es el de la primera derivación."""
        self.reloj.avanzar(minutes=40)
        servicio.cancelar_derivacion(self.derivacion, self.operador, "Error de carga")
        self.assertEqual(self._fila(self.caso)["derivado_en"], T0)

        self.reloj.avanzar(minutes=10)
        nueva = servicio.derivar_caso(self.caso, self.operador, self._dispositivo("Escuela", camas=5), 2)
        fila = self._fila(self.caso)

        self.assertEqual(fila["estado"], Estado.DERIVADO)
        self.assertEqual(fila["derivado_en"], T0)
        self.assertEqual(nueva.vence_en, T0 + timedelta(minutes=50 + 720))
        self.assertEqual(Derivacion.objects.filter(caso=self.caso).count(), 2)

    def test_cancelar_pide_motivo(self):
        for motivo in ("", "   ", None):
            with self.subTest(motivo=motivo):
                with self.assertRaises(ValidationError) as error:
                    servicio.cancelar_derivacion(self.derivacion, self.operador, motivo)
                self.assertIn("motivo", error.exception.message_dict)
        self.assertEqual(self._fila(self.caso)["estado"], Estado.DERIVADO)

    def test_una_derivacion_que_ya_no_esta_pendiente_no_se_cancela(self):
        """El dispositivo la aceptó mientras la mesa miraba la ficha vieja."""
        Derivacion.objects.filter(pk=self.derivacion.pk).update(estado=Derivacion.Estado.ACEPTADA)
        CasoEmergencia.objects.filter(pk=self.caso.pk).update(estado=Estado.INGRESO_EN_CURSO)

        with self.assertRaises(EstadoCambio) as error:
            servicio.cancelar_derivacion(self.derivacion, self.operador, "Ya no hace falta")

        self.assertEqual(error.exception.estado_actual, Estado.INGRESO_EN_CURSO)
        self.assertEqual(Derivacion.objects.get(pk=self.derivacion.pk).estado, Derivacion.Estado.ACEPTADA)

    def test_cancelar_dos_veces_es_un_estado_cambio(self):
        servicio.cancelar_derivacion(self.derivacion, self.operador, "Error de carga")
        with self.assertRaises(EstadoCambio):
            servicio.cancelar_derivacion(self.derivacion, self.operador, "Error de carga")
        self.assertEqual(TrazaCaso.objects.filter(caso=self.caso, accion=Accion.DERIVACION_CANCELADA).count(), 1)

    def test_el_que_no_lo_tiene_tomado_no_cancela_y_quien_supervisa_si(self):
        with self.assertRaises(PermissionDenied):
            servicio.cancelar_derivacion(self.derivacion, self.otro_operador, "Porque sí")
        self.assertEqual(Derivacion.objects.get(pk=self.derivacion.pk).estado, Derivacion.Estado.PENDIENTE)

        servicio.cancelar_derivacion(self.derivacion, self.supervisor, "Dispositivo inundado")
        self.assertTrue(self._trazas(self.caso)[-1].por_supervisor)
        self.assertEqual(self._fila(self.caso)["tomado_por_id"], self.operador.pk)


# ---------------------------------------------------------------------------
# Cerrar
# ---------------------------------------------------------------------------


class CerrarSinAlojamientoTests(BaseCasos):
    def test_cerrar_un_caso_en_gestion(self):
        """HU-2.7 / RN-2.13."""
        caso = self._caso_tomado()
        self.reloj.avanzar(minutes=50)
        servicio.cerrar_sin_alojamiento(caso, self.operador, "ASISTIDO_DOMICILIO", "  Se le llevó agua ")
        fila = self._fila(caso)
        traza = self._trazas(caso)[-1]

        self.assertEqual(fila["estado"], Estado.CERRADO)
        self.assertEqual(fila["cerrado_en"], T0 + timedelta(minutes=50))
        self.assertEqual(
            (fila["motivo_cierre"], fila["observacion_cierre"]), ("ASISTIDO_DOMICILIO", "Se le llevó agua")
        )
        self.assertEqual(
            (traza.accion, traza.estado_anterior, traza.estado_nuevo),
            (Accion.CERRADO, Estado.EN_GESTION, Estado.CERRADO),
        )
        self.assertEqual(traza.detalle, "Cerrado sin alojamiento: Asistido en domicilio")

    def test_el_motivo_sale_del_select_y_otro_pide_contar_que_paso(self):
        caso = self._caso_tomado()
        for motivo, observacion, campo in (
            ("", "", "motivo"),
            ("PORQUE_SI", "", "motivo"),
            ("TODOS_EGRESADOS", "", "motivo"),  # lo pone el sistema en la etapa 3, no una persona
            ("OTRO", "  ", "observacion"),
        ):
            with self.subTest(motivo=motivo):
                with self.assertRaises(ValidationError) as error:
                    servicio.cerrar_sin_alojamiento(caso, self.operador, motivo, observacion)
                self.assertIn(campo, error.exception.message_dict)
        self.assertEqual(self._fila(caso)["estado"], Estado.EN_GESTION)

        servicio.cerrar_sin_alojamiento(caso, self.operador, "OTRO", "Duplicado de N.° 2026-000007")
        self.assertEqual(self._fila(caso)["observacion_cierre"], "Duplicado de N.° 2026-000007")

    def test_un_caso_derivado_no_se_cierra_sin_cancelar_antes(self):
        """RN-2.6."""
        caso = self._caso_tomado()
        derivacion = servicio.derivar_caso(caso, self.operador, self._dispositivo("Club", camas=5), 2)

        with self.assertRaises(EstadoCambio) as error:
            servicio.cerrar_sin_alojamiento(caso, self.operador, "NO_REQUIERE")
        self.assertEqual(error.exception.estado_actual, Estado.DERIVADO)
        self.assertIn("cancelá la derivación", error.exception.mensaje)
        self.assertEqual(self._fila(caso)["estado"], Estado.DERIVADO)

        servicio.cancelar_derivacion(derivacion, self.operador, "No hace falta")
        servicio.cerrar_sin_alojamiento(caso, self.operador, "NO_REQUIERE")
        self.assertEqual(self._fila(caso)["estado"], Estado.CERRADO)

    def test_el_que_no_lo_tiene_tomado_no_cierra_y_quien_supervisa_si(self):
        caso = self._caso_tomado()
        with self.assertRaises(PermissionDenied):
            servicio.cerrar_sin_alojamiento(caso, self.otro_operador, "NO_REQUIERE")
        self.assertEqual(self._fila(caso)["estado"], Estado.EN_GESTION)

        servicio.cerrar_sin_alojamiento(caso, self.supervisor, "SIN_CONTACTO")
        self.assertTrue(self._trazas(caso)[-1].por_supervisor)

    def test_cerrado_es_terminal(self):
        """RN-2.13: ninguna acción reabre ni toca un caso cerrado."""
        caso = self._caso_tomado()
        dispositivo = self._dispositivo("Club", camas=5)
        derivacion = servicio.derivar_caso(caso, self.operador, dispositivo, 2)
        servicio.cancelar_derivacion(derivacion, self.operador, "No hace falta")
        servicio.cerrar_sin_alojamiento(caso, self.operador, "NO_REQUIERE")
        antes = self._fila(caso)
        trazas = len(self._trazas(caso))
        self.reloj.avanzar(hours=3)

        acciones = {
            "tomar": lambda quien: servicio.tomar_caso(caso, quien),
            "soltar": lambda quien: servicio.soltar_caso(caso, quien),
            "reasignar": lambda quien: servicio.reasignar_caso(caso, self.supervisor, self.otro_operador),
            "prioridad": lambda quien: servicio.cambiar_prioridad(caso, quien, Prioridad.ALTA),
            "contacto": lambda quien: servicio.registrar_contacto(caso, quien, canal="LLAMADA", resultado="ATENDIO"),
            "derivar": lambda quien: servicio.derivar_caso(caso, quien, dispositivo, 2),
            "cancelar": lambda quien: servicio.cancelar_derivacion(derivacion, quien, "Otra vez"),
            "cerrar": lambda quien: servicio.cerrar_sin_alojamiento(caso, quien, "SIN_CONTACTO"),
        }
        for nombre, accion in acciones.items():
            for quien in (self.operador, self.otro_operador, self.supervisor):
                with self.subTest(accion=nombre, quien=quien.username):
                    with self.assertRaises(EstadoCambio) as error:
                        accion(quien)
                    self.assertEqual(error.exception.estado_actual, Estado.CERRADO)

        self.assertEqual(self._fila(caso), antes)
        self.assertEqual(len(self._trazas(caso)), trazas)
        self.assertFalse(ContactoCaso.objects.exists())
        self.assertEqual(Derivacion.objects.filter(caso=caso).count(), 1)


class TrazaDeCadaTransicionTests(BaseCasos):
    """RU-15: cada cosa que le pasa al caso deja una fila, y solo una."""

    def test_el_recorrido_entero_de_la_mesa(self):
        caso = self._caso()
        dispositivo = self._dispositivo("Club", camas=5)
        servicio.tomar_caso(caso, self.operador)
        servicio.cambiar_prioridad(caso, self.operador, Prioridad.MEDIA)
        servicio.registrar_contacto(caso, self.operador, canal="LLAMADA", resultado="ATENDIO")
        servicio.soltar_caso(caso, self.operador)
        servicio.reasignar_caso(caso, self.supervisor, self.otro_operador)
        derivacion = servicio.derivar_caso(caso, self.otro_operador, dispositivo, 2)
        servicio.cancelar_derivacion(derivacion, self.otro_operador, "Cambio de planes")
        servicio.cerrar_sin_alojamiento(caso, self.otro_operador, "POR_SU_CUENTA")

        recorrido = [(t.accion, t.estado_anterior, t.estado_nuevo, t.usuario_id) for t in self._trazas(caso)]
        self.assertEqual(
            recorrido,
            [
                (Accion.CREADO, "", Estado.NUEVO, self.agente.pk),
                (Accion.TOMADO, Estado.NUEVO, Estado.EN_GESTION, self.operador.pk),
                (Accion.PRIORIDAD, Estado.EN_GESTION, Estado.EN_GESTION, self.operador.pk),
                (Accion.CONTACTO, Estado.EN_GESTION, Estado.EN_GESTION, self.operador.pk),
                (Accion.SOLTADO, Estado.EN_GESTION, Estado.NUEVO, self.operador.pk),
                (Accion.REASIGNADO, Estado.NUEVO, Estado.EN_GESTION, self.supervisor.pk),
                (Accion.DERIVADO, Estado.EN_GESTION, Estado.DERIVADO, self.otro_operador.pk),
                (Accion.DERIVACION_CANCELADA, Estado.DERIVADO, Estado.EN_GESTION, self.otro_operador.pk),
                (Accion.CERRADO, Estado.EN_GESTION, Estado.CERRADO, self.otro_operador.pk),
            ],
        )
        self.assertEqual([t.por_supervisor for t in self._trazas(caso)].count(True), 1)

    def test_las_marcas_del_recorrido_no_se_pisan(self):
        """RN-2.9 de punta a punta: soltar, retomar, reasignar y volver de una cancelada."""
        caso = self._caso()
        dispositivo = self._dispositivo("Club", camas=5)
        self.reloj.avanzar(minutes=5)
        servicio.tomar_caso(caso, self.operador)
        tomado = self.reloj.ahora
        self.reloj.avanzar(minutes=5)
        servicio.soltar_caso(caso, self.operador)
        self.reloj.avanzar(minutes=5)
        servicio.tomar_caso(caso, self.otro_operador)
        self.reloj.avanzar(minutes=5)
        servicio.reasignar_caso(caso, self.supervisor, self.operador)
        self.reloj.avanzar(minutes=5)
        derivacion = servicio.derivar_caso(caso, self.operador, dispositivo, 2)
        derivado = self.reloj.ahora
        self.reloj.avanzar(minutes=5)
        servicio.cancelar_derivacion(derivacion, self.operador, "Error")
        self.reloj.avanzar(minutes=5)
        servicio.derivar_caso(caso, self.operador, dispositivo, 2)
        fila = self._fila(caso)

        self.assertEqual((fila["tomado_en"], fila["derivado_en"]), (tomado, derivado))
        self.assertEqual((fila["aceptado_en"], fila["alojado_en"], fila["cerrado_en"]), (None, None, None))


# ---------------------------------------------------------------------------
# Lo que la ficha ofrece contra lo que el servicio deja hacer
# ---------------------------------------------------------------------------


class _Deshacer(Exception):
    """Deshace una acción que pasó: cada celda de la tabla parte del mismo caso."""


class AccionesPosiblesTests(BaseCasos):
    """``acciones_posibles`` ofrece exactamente lo que los servicios dejan hacer (RU-12, RU-13).

    Una tabla: cada estado del caso × quien mira (el dueño, quien supervisa, otro operador) ×
    cada acción de la ficha. Lo ofrecido no puede terminar en ``PermissionDenied`` ni en
    ``EstadoCambio``; lo no ofrecido, sí. Cada llamada corre en un savepoint que se deshace.

    La única celda que no ofrece y tampoco falla es la que el servicio define así a propósito:
    el dueño que vuelve a tomar lo que ya tiene (doble clic, segunda pestaña) no cambia nada.
    """

    ACCIONES = (
        "puede_tomar",
        "puede_soltar",
        "puede_derivar",
        "puede_cerrar",
        "puede_cancelar_derivacion",
        "puede_reasignar",
    )

    def setUp(self):
        super().setUp()
        self.club = self._dispositivo("Club Sarmiento", camas=10)
        self.destino = self._persona_de_mesa("lucia", [OPERAR], "Lucía", "Gómez")
        derivaciones = {}
        casos = {Estado.NUEVO: self._caso(), Estado.EN_GESTION: self._caso_tomado()}
        casos[Estado.DERIVADO] = self._caso_tomado()
        derivaciones[Estado.DERIVADO] = servicio.derivar_caso(casos[Estado.DERIVADO], self.operador, self.club, 2)
        for estado in (Estado.INGRESO_EN_CURSO, Estado.ALOJADO):
            caso = self._caso_tomado()
            derivacion = servicio.derivar_caso(caso, self.operador, self.club, 2)
            derivacion.estado = Derivacion.Estado.ACEPTADA
            derivacion.save()
            marcas = {"aceptado_en": T0, "alojado_en": T0 if estado == Estado.ALOJADO else None}
            CasoEmergencia.objects.filter(pk=caso.pk).update(estado=estado, **marcas)
            casos[estado], derivaciones[estado] = caso, derivacion
        casos[Estado.CERRADO] = servicio.cerrar_sin_alojamiento(
            self._caso_tomado(), self.operador, CasoEmergencia.MotivoCierre.NO_REQUIERE
        )
        self.casos = {estado: CasoEmergencia.objects.get(pk=caso.pk) for estado, caso in casos.items()}
        self.derivaciones = {estado: Derivacion.objects.get(pk=d.pk) for estado, d in derivaciones.items()}
        self.roles = {"dueño": self.operador, "supervisor": self.supervisor, "otro operador": self.otro_operador}

    def _ejecutar(self, accion, caso, derivacion, usuario):
        llamadas = {
            "puede_tomar": lambda: servicio.tomar_caso(caso, usuario),
            "puede_soltar": lambda: servicio.soltar_caso(caso, usuario),
            "puede_derivar": lambda: servicio.derivar_caso(caso, usuario, self.club, 1),
            "puede_cerrar": lambda: servicio.cerrar_sin_alojamiento(
                caso, usuario, CasoEmergencia.MotivoCierre.NO_REQUIERE
            ),
            "puede_cancelar_derivacion": lambda: servicio.cancelar_derivacion(derivacion, usuario, "Prueba"),
            "puede_reasignar": lambda: servicio.reasignar_caso(caso, usuario, self.destino),
        }
        try:
            with transaction.atomic():
                llamadas[accion]()
                raise _Deshacer
        except _Deshacer:
            return None
        except (PermissionDenied, EstadoCambio) as error:
            return error

    def test_lo_ofrecido_pasa_y_lo_no_ofrecido_se_rechaza(self):
        for estado, caso in self.casos.items():
            derivacion = self.derivaciones.get(estado)
            pendiente = derivacion is not None and derivacion.estado == Derivacion.Estado.PENDIENTE
            for rol, usuario in self.roles.items():
                acciones = servicio.acciones_posibles(
                    caso,
                    usuario,
                    es_supervisor=servicio.puede_supervisar_la_mesa(usuario),
                    derivacion_pendiente=pendiente,
                )
                if acciones["solo_lectura"]:
                    with self.subTest(estado=estado, rol=rol, clave="solo_lectura"):
                        self.assertFalse(any(acciones[accion] for accion in self.ACCIONES))
                for accion in self.ACCIONES:
                    with self.subTest(estado=estado, rol=rol, accion=accion):
                        if derivacion is None and accion == "puede_cancelar_derivacion":
                            # Sin derivación no hay nada que cancelar, ni botón que ofrecerlo.
                            self.assertFalse(acciones[accion])
                            continue
                        error = self._ejecutar(accion, caso, derivacion, usuario)
                        if acciones[accion]:
                            self.assertIsNone(error, f"Se ofrece y el servicio contesta: {error!r}")
                        elif (accion, estado, rol) == ("puede_tomar", Estado.EN_GESTION, "dueño"):
                            self.assertIsNone(error)
                            self.assertEqual(self._fila(caso)["tomado_por_id"], usuario.pk)
                        else:
                            self.assertIsNotNone(error, "No se ofrece, pero el servicio la deja hacer.")

    def test_la_tabla_de_la_ficha(self):
        """Lo que se ve, celda por celda: quién tiene qué en cada estado."""

        esperado = {
            # estado: {rol: acciones ofrecidas}
            Estado.NUEVO: {
                r: {"puede_tomar"} | ({"puede_reasignar"} if r == "supervisor" else set()) for r in self.roles
            },
            Estado.EN_GESTION: {
                "dueño": {"puede_soltar", "puede_derivar", "puede_cerrar"},
                "supervisor": {"puede_soltar", "puede_derivar", "puede_cerrar", "puede_reasignar"},
                "otro operador": set(),
            },
            Estado.DERIVADO: {
                "dueño": {"puede_cancelar_derivacion"},
                "supervisor": {"puede_cancelar_derivacion", "puede_reasignar"},
                "otro operador": set(),
            },
            Estado.INGRESO_EN_CURSO: {"dueño": set(), "supervisor": {"puede_reasignar"}, "otro operador": set()},
            Estado.ALOJADO: {"dueño": set(), "supervisor": {"puede_reasignar"}, "otro operador": set()},
            Estado.CERRADO: {r: set() for r in self.roles},
        }
        solo_lectura = {
            (Estado.EN_GESTION, "otro operador"),
            (Estado.DERIVADO, "otro operador"),
            (Estado.INGRESO_EN_CURSO, "otro operador"),
            (Estado.ALOJADO, "otro operador"),
        }
        for estado, caso in self.casos.items():
            derivacion = self.derivaciones.get(estado)
            for rol, usuario in self.roles.items():
                with self.subTest(estado=estado, rol=rol):
                    acciones = servicio.acciones_posibles(
                        caso,
                        usuario,
                        es_supervisor=rol == "supervisor",
                        derivacion_pendiente=bool(derivacion and derivacion.estado == Derivacion.Estado.PENDIENTE),
                    )
                    self.assertEqual({a for a in self.ACCIONES if acciones[a]}, esperado[estado][rol])
                    self.assertEqual(acciones["solo_lectura"], (estado, rol) in solo_lectura)
                    self.assertEqual(acciones["es_duenio"], rol == "dueño" and estado != Estado.NUEVO)

    def test_no_consulta_la_base(self):
        caso = self.casos[Estado.EN_GESTION]
        with self.assertNumQueries(0):
            servicio.acciones_posibles(caso, self.operador, es_supervisor=False, derivacion_pendiente=False)


# ---------------------------------------------------------------------------
# El orden de los candados
# ---------------------------------------------------------------------------


class OrdenDeLosCandadosEmergenciaTests(BaseCasos):
    """Todo camino bloquea **primero el caso** y después la derivación; ninguno llega a las plazas.

    Es el orden global del plan (§8, R1): caso → derivación → plazas → reservas → persona.
    Acá se prueba por la secuencia de llamadas y no por su efecto: en SQLite
    ``select_for_update()`` es un no-op y no hay deadlock que reproducir. La carrera de
    verdad es ``programas.tests.test_emergencia_concurrencia``, con ``@tag("mysql")``.
    """

    def _orden(self):
        return orden_de_candados(
            caso=CasoEmergencia.objects,
            derivacion=Derivacion.objects,
            plaza=Plaza.objects,
            reserva=ReservaPlaza.objects,
            persona=Ciudadano.objects,
            numerador=NumeradorEmergencia.objects,
        )

    def test_cada_accion_sobre_el_caso_bloquea_el_caso_y_nada_mas(self):
        dispositivo = self._dispositivo("Club", camas=5)
        acciones = {
            "tomar": lambda caso: servicio.tomar_caso(caso, self.operador),
            "prioridad": lambda caso: servicio.cambiar_prioridad(caso, self.supervisor, Prioridad.ALTA),
            "contacto": lambda caso: servicio.registrar_contacto(
                caso, self.supervisor, canal="LLAMADA", resultado="ATENDIO"
            ),
            "reasignar": lambda caso: servicio.reasignar_caso(caso, self.supervisor, self.otro_operador),
            "soltar": lambda caso: servicio.soltar_caso(servicio.tomar_caso(caso, self.operador), self.operador),
            "derivar": lambda caso: servicio.derivar_caso(
                servicio.tomar_caso(caso, self.operador), self.operador, dispositivo, 1
            ),
            "cerrar": lambda caso: servicio.cerrar_sin_alojamiento(
                servicio.tomar_caso(caso, self.operador), self.operador, "NO_REQUIERE"
            ),
        }
        for nombre, accion in acciones.items():
            with self.subTest(accion=nombre):
                caso = self._caso()
                with self._orden() as orden:
                    accion(caso)
                self.assertEqual(set(orden), {"caso"})

    def test_cancelar_una_derivacion_toma_primero_el_caso(self):
        caso = self._caso_tomado()
        derivacion = servicio.derivar_caso(caso, self.operador, self._dispositivo("Club", camas=5), 2)

        with self._orden() as orden:
            servicio.cancelar_derivacion(derivacion, self.operador, "Error de carga")

        self.assertEqual(orden, ["caso", "derivacion"])

    def test_crear_un_caso_solo_bloquea_el_numerador(self):
        with self._orden() as orden:
            self._caso()
        self.assertEqual(orden, ["numerador"])


# ---------------------------------------------------------------------------
# Semáforo del SLA (RN-2.10)
# ---------------------------------------------------------------------------


def _sla(**cambios):
    """Los objetivos de fábrica: 15 / 30 / 120 / 60, por vencer al 80 %."""
    return SLAEmergencia(**cambios)


def _caso_en(estado, *, creado=T0, tomado=None, derivado=None, aceptado=None, alojado=None):
    """Un caso sin guardar con sus marcas: el semáforo no necesita la base."""
    caso = CasoEmergencia(
        estado=estado, tomado_en=tomado, derivado_en=derivado, aceptado_en=aceptado, alojado_en=alojado
    )
    caso.creado = creado
    return caso


def _min(minutos, segundos=0):
    return timedelta(minutes=minutos, seconds=segundos)


class SemaforoDelSlaTests(SimpleTestCase):
    """La tabla de estados del semáforo, con momentos fijos. ``estado_sla`` no llama a ``now()``."""

    def _afirmar(self, caso, ahora, esperado, sla=None):
        semaforo = estado_sla(caso, sla or _sla(), ahora)
        self.assertEqual((semaforo.estado, semaforo.minutos, semaforo.tramo), esperado)
        return semaforo

    def test_tramo_tomar(self):
        """Objetivo 15 min; por vencer desde el minuto 12 (80 %)."""
        nuevo = _caso_en(Estado.NUEVO)
        tabla = [
            (_min(0), (SLA_EN_TERMINO, 15, "tomar")),
            (_min(5), (SLA_EN_TERMINO, 10, "tomar")),
            (_min(11, 59), (SLA_EN_TERMINO, 4, "tomar")),
            (_min(12), (SLA_POR_VENCER, 3, "tomar")),
            (_min(14, 30), (SLA_POR_VENCER, 1, "tomar")),
            (_min(15), (SLA_POR_VENCER, 0, "tomar")),
            (_min(15, 1), (SLA_FUERA, 0, "tomar")),
            (_min(16), (SLA_FUERA, 1, "tomar")),
            (_min(57), (SLA_FUERA, 42, "tomar")),
        ]
        for lapso, esperado in tabla:
            with self.subTest(lapso=lapso):
                self._afirmar(nuevo, T0 + lapso, esperado)

    def test_tramo_derivar(self):
        """Objetivo 30 min desde que se tomó; por vencer desde el minuto 24."""
        tomado = T0 + _min(10)
        en_gestion = _caso_en(Estado.EN_GESTION, tomado=tomado)
        tabla = [
            (_min(22), (SLA_EN_TERMINO, 8, "derivar")),
            (_min(24), (SLA_POR_VENCER, 6, "derivar")),
            (_min(30), (SLA_POR_VENCER, 0, "derivar")),
            (_min(72), (SLA_FUERA, 42, "derivar")),
        ]
        for lapso, esperado in tabla:
            with self.subTest(lapso=lapso):
                self._afirmar(en_gestion, tomado + lapso, esperado)

    def test_tramo_aceptar(self):
        """Objetivo 120 min desde que se derivó; por vencer desde el minuto 96."""
        derivado = T0 + _min(40)
        caso = _caso_en(Estado.DERIVADO, tomado=T0 + _min(10), derivado=derivado)
        tabla = [
            (_min(95), (SLA_EN_TERMINO, 25, "aceptar")),
            (_min(96), (SLA_POR_VENCER, 24, "aceptar")),
            (_min(120), (SLA_POR_VENCER, 0, "aceptar")),
            (_min(121), (SLA_FUERA, 1, "aceptar")),
        ]
        for lapso, esperado in tabla:
            with self.subTest(lapso=lapso):
                self._afirmar(caso, derivado + lapso, esperado)

    def test_tramo_alojar(self):
        """Objetivo 60 min desde que el dispositivo aceptó; por vencer desde el minuto 48."""
        aceptado = T0 + _min(100)
        caso = _caso_en(Estado.INGRESO_EN_CURSO, tomado=T0 + _min(10), derivado=T0 + _min(40), aceptado=aceptado)
        tabla = [
            (_min(47), (SLA_EN_TERMINO, 13, "alojar")),
            (_min(48), (SLA_POR_VENCER, 12, "alojar")),
            (_min(61), (SLA_FUERA, 1, "alojar")),
        ]
        for lapso, esperado in tabla:
            with self.subTest(lapso=lapso):
                self._afirmar(caso, aceptado + lapso, esperado)

    def test_alojado_y_cerrado_no_tienen_sla(self):
        marcas = {"tomado": T0, "derivado": T0, "aceptado": T0}
        self.assertIsNone(estado_sla(_caso_en(Estado.ALOJADO, alojado=T0, **marcas), _sla(), T0 + _min(500)))
        self.assertIsNone(estado_sla(_caso_en(Estado.CERRADO), _sla(), T0 + _min(500)))
        self.assertIsNone(estado_sla(_caso_en(Estado.CERRADO, tomado=T0), _sla(), T0 + _min(500)))

    def test_un_caso_soltado_sigue_en_el_tramo_derivar_desde_la_primera_toma(self):
        """RN-2.9: soltar no reinicia nada. El SLA mide a la familia, no al operador."""
        tomado = T0 + _min(10)
        soltado = _caso_en(Estado.NUEVO, tomado=tomado)
        self._afirmar(soltado, tomado + _min(35), (SLA_FUERA, 5, "derivar"))

    def test_un_caso_que_volvio_de_una_derivacion_sigue_en_el_tramo_aceptar(self):
        """RN-2.9 / HU-2.5: vencida o cancelada, corre desde la primera derivación."""
        derivado = T0 + _min(40)
        de_vuelta = _caso_en(Estado.EN_GESTION, tomado=T0 + _min(10), derivado=derivado)
        self._afirmar(de_vuelta, derivado + _min(12 * 60), (SLA_FUERA, 600, "aceptar"))

    def test_el_umbral_y_los_objetivos_son_los_de_la_configuracion(self):
        """02 §9: cambiar E7 mueve el semáforo de los casos abiertos; no se congela por caso."""
        nuevo = _caso_en(Estado.NUEVO)
        self._afirmar(nuevo, T0 + _min(8), (SLA_EN_TERMINO, 7, "tomar"))
        self._afirmar(nuevo, T0 + _min(8), (SLA_POR_VENCER, 7, "tomar"), sla=_sla(umbral_por_vencer_pct=50))
        self._afirmar(nuevo, T0 + _min(8), (SLA_FUERA, 3, "tomar"), sla=_sla(objetivo_tomar_min=5))
        self._afirmar(nuevo, T0 + _min(8), (SLA_EN_TERMINO, 52, "tomar"), sla=_sla(objetivo_tomar_min=60))

    def test_la_hora_del_telefono_no_entra_en_el_calculo(self):
        """RU-18: el tramo «tomar» corre desde ``creado``, no desde ``relevado_en``."""
        caso = _caso_en(Estado.NUEVO)
        caso.relevado_en = T0 - timedelta(hours=3)
        self._afirmar(caso, T0 + _min(5), (SLA_EN_TERMINO, 10, "tomar"))

    def test_se_desarma_como_la_terna_y_trae_el_resto(self):
        semaforo = estado_sla(_caso_en(Estado.NUEVO), _sla(), T0 + _min(57))
        estado, minutos, tramo = semaforo

        self.assertIsInstance(semaforo, EstadoSLA)
        self.assertEqual((estado, minutos, tramo), (SLA_FUERA, 42, "tomar"))
        self.assertEqual((semaforo.objetivo_min, semaforo.transcurridos_min), (15, 57))
        self.assertTrue(semaforo.fuera)
        self.assertEqual(semaforo.texto_tiempo, "42 min")

    def test_los_minutos_grandes_se_leen_en_horas_y_en_dias(self):
        tabla = [(0, "0 min"), (42, "42 min"), (99, "99 min"), (100, "1 h"), (48 * 60, "48 h"), (71 * 60 + 59, "71 h")]
        tabla += [(72 * 60, "3 d"), (10 * 24 * 60 + 5, "10 d")]
        for minutos, texto in tabla:
            with self.subTest(minutos=minutos):
                self.assertEqual(texto_de_minutos(minutos), texto)

        derivado = T0
        colgado = _caso_en(Estado.DERIVADO, tomado=T0, derivado=derivado)
        semaforo = estado_sla(colgado, _sla(), derivado + timedelta(hours=50))
        self.assertEqual((semaforo.estado, semaforo.minutos, semaforo.texto_tiempo), (SLA_FUERA, 48 * 60, "48 h"))

    def test_un_reloj_atrasado_no_da_minutos_negativos(self):
        self._afirmar(_caso_en(Estado.NUEVO), T0 - _min(3), (SLA_EN_TERMINO, 15, "tomar"))


# ---------------------------------------------------------------------------
# Bandeja
# ---------------------------------------------------------------------------


class BandejaTests(BaseCasos):
    def setUp(self):
        super().setUp()
        self.sla = SLAEmergencia.objects.get(programa=self.programa)
        self.resistencia = Localidad.objects.create(nombre="Resistencia")
        self.club = self._dispositivo("Club", camas=20)
        # Un caso por situación, creados con cinco minutos de diferencia.
        self.viejo = self._caso(dni="30500001", apellido="Acosta", localidad=self.resistencia.pk)
        self.reloj.avanzar(minutes=5)
        self.alta = self._caso(dni="30500002", apellido="Benítez", embarazo=True)
        self.reloj.avanzar(minutes=5)
        self.en_gestion = self._caso_tomado(dni="30500003", apellido="Cáceres")
        self.reloj.avanzar(minutes=5)
        self.derivado = self._caso_tomado(por=self.otro_operador, dni="30500004", apellido="Díaz")
        servicio.derivar_caso(self.derivado, self.otro_operador, self.club, 2)
        self.cerrado = self._caso_tomado(dni="30500005", apellido="Escobar")
        servicio.cerrar_sin_alojamiento(self.cerrado, self.operador, "NO_REQUIERE")
        self.ahora = self.reloj.avanzar(minutes=5)  # T0 + 20

    def _numeros(self, filtros=None, **kwargs):
        return [caso.numero for caso in selectores.bandeja(filtros, **kwargs)]

    def test_el_conteo_de_solapas_es_una_sola_consulta(self):
        with self.assertNumQueries(1):
            conteo = selectores.conteo_por_solapa()

        self.assertEqual(
            conteo,
            {
                "total": 5,
                "abiertos": 4,
                "nuevos": 2,
                "en_gestion": 1,
                "derivados": 1,
                "ingreso_en_curso": 0,
                "alojados": 0,
                "ingreso_directo": 0,
                "cerrados": 1,
            },
        )
        self.assertEqual(set(conteo) - {"total", "alojados"}, set(selectores.SOLAPAS) - {"fuera_sla"})

    def test_cada_solapa_trae_lo_suyo(self):
        esperado = {
            "abiertos": {self.viejo, self.alta, self.en_gestion, self.derivado},
            "nuevos": {self.viejo, self.alta},
            "en_gestion": {self.en_gestion},
            "derivados": {self.derivado},
            "ingreso_en_curso": set(),
            "ingreso_directo": set(),
            "cerrados": {self.cerrado},
        }
        for solapa, casos in esperado.items():
            with self.subTest(solapa=solapa):
                self.assertEqual(set(self._numeros({"solapa": solapa})), {caso.numero for caso in casos})

    def test_fuera_de_sla_se_calcula_sobre_los_abiertos(self):
        """A T0+20: los dos nuevos pasaron sus 15 min (el segundo, justo: 15 no es «fuera»)."""
        with self.assertNumQueries(1):
            fuera = selectores.ids_fuera_de_sla(self.sla, self.ahora)
        self.assertEqual(fuera, [self.viejo.pk])

        self.assertEqual(self._numeros({"solapa": "fuera_sla"}, sla=self.sla, ahora=self.ahora), [self.viejo.numero])
        en_una_hora = self.ahora + timedelta(hours=1)
        self.assertEqual(
            set(self._numeros({"solapa": "fuera_sla"}, sla=self.sla, ahora=en_una_hora)),
            {self.viejo.numero, self.alta.numero, self.en_gestion.numero},
        )

    def test_el_filtro_por_semaforo(self):
        self.assertEqual(self._numeros({"sla": "FUERA"}, sla=self.sla, ahora=self.ahora), [self.viejo.numero])
        self.assertEqual(self._numeros({"sla": "POR_VENCER"}, sla=self.sla, ahora=self.ahora), [self.alta.numero])
        self.assertEqual(
            set(self._numeros({"sla": "EN_TERMINO"}, sla=self.sla, ahora=self.ahora)),
            {self.en_gestion.numero, self.derivado.numero},
        )

    def test_cuando_nadie_esta_fuera_de_sla_la_bandeja_se_arma_igual(self):
        """Con la lista de «fuera» vacía, ni el orden ni la solapa se rompen."""
        al_crear_el_ultimo = T0 + timedelta(minutes=15)
        self.assertEqual(selectores.ids_fuera_de_sla(self.sla, T0 + timedelta(minutes=10)), [])
        self.assertEqual(self._numeros({"solapa": "fuera_sla"}, sla=self.sla, ahora=al_crear_el_ultimo), [])
        self.assertEqual(
            self._numeros({"solapa": "abiertos"}, sla=self.sla, ahora=al_crear_el_ultimo),
            [self.alta.numero, self.viejo.numero, self.en_gestion.numero, self.derivado.numero],
        )

    def test_sin_reloj_no_se_puede_filtrar_por_sla(self):
        for filtros in ({"solapa": "fuera_sla"}, {"sla": "FUERA"}):
            with self.subTest(filtros=filtros):
                with self.assertRaises(ValueError):
                    selectores.bandeja(filtros)
        with self.assertRaises(ValueError):
            selectores.bandeja({"solapa": "todas"})
        with self.assertRaises(ValueError):
            selectores.bandeja({"sla": "ROJO"}, sla=self.sla, ahora=self.ahora)
        with self.assertRaises(ValueError):
            selectores.bandeja({"barrio": "Sur"})

    def test_el_orden_es_fuera_de_sla_despues_prioridad_despues_el_mas_viejo(self):
        """02 §3."""
        abiertos = {"solapa": "abiertos"}
        # Sin reloj: prioridad (la ALTA primero) y después antigüedad.
        self.assertEqual(
            self._numeros(abiertos),
            [self.alta.numero, self.viejo.numero, self.en_gestion.numero, self.derivado.numero],
        )
        # Con reloj: el que está fuera de SLA pasa adelante aunque sea de prioridad baja.
        self.assertEqual(
            self._numeros(abiertos, sla=self.sla, ahora=self.ahora),
            [self.viejo.numero, self.alta.numero, self.en_gestion.numero, self.derivado.numero],
        )

    def test_los_filtros(self):
        self.assertEqual(self._numeros({"estado": Estado.DERIVADO}), [self.derivado.numero])
        self.assertEqual(self._numeros({"prioridad": Prioridad.ALTA}), [self.alta.numero])
        self.assertEqual(self._numeros({"localidad": self.resistencia.pk}), [self.viejo.numero])
        self.assertEqual(self._numeros({"tomado_por": self.otro_operador.pk}), [self.derivado.numero])
        self.assertEqual(
            self._numeros({"tomado_por": self.operador.pk, "solapa": "abiertos"}), [self.en_gestion.numero]
        )
        self.assertEqual(self._numeros({"origen": Origen.MESA}), [])
        self.assertEqual(self._numeros({"estado": "", "prioridad": None, "texto": "  "}).__len__(), 5)

    def test_el_texto_busca_por_numero_dni_y_apellido(self):
        self.assertEqual(self._numeros({"texto": self.derivado.numero}), [self.derivado.numero])
        self.assertEqual(self._numeros({"texto": "000003"}), [self.en_gestion.numero])
        self.assertEqual(self._numeros({"texto": "30.500.002"}), [self.alta.numero])
        self.assertEqual(self._numeros({"texto": "cáceres"}), [self.en_gestion.numero])
        self.assertEqual(self._numeros({"texto": "no hay nadie"}), [])

    @tag("performance")
    def test_la_pagina_de_la_bandeja_no_tiene_n_mas_uno(self):
        """Una consulta para armar el orden y una para la página, con todo lo de la fila."""
        with self.assertNumQueries(2):
            casos = list(selectores.bandeja({"solapa": "abiertos"}, sla=self.sla, ahora=self.ahora)[:50])
            for caso in casos:
                _ = (
                    caso.grupo.total_declarado,
                    caso.grupo.responsable.apellido,
                    caso.localidad.nombre if caso.localidad_id else "",
                    caso.tomado_por.username if caso.tomado_por_id else "",
                    estado_sla(caso, self.sla, self.ahora),
                )
        self.assertEqual(len(casos), 4)

    def test_el_ingreso_directo_tiene_su_solapa(self):
        guardia = self._usuario("guardia", ["dispositivo.admitir"], programa=self.dispositivos)
        directo = self._caso(origen=Origen.DISPOSITIVO, usuario=guardia)

        self.assertEqual(self._numeros({"solapa": "ingreso_directo"}), [directo.numero])
        self.assertEqual(selectores.conteo_por_solapa()["ingreso_directo"], 1)


# ---------------------------------------------------------------------------
# Panel «Derivar»
# ---------------------------------------------------------------------------

#: Plaza 25 de Mayo de Resistencia y tres puntos cada vez más lejos.
PLAZA = (Decimal("-27.451100"), Decimal("-58.986500"))
A_2_KM = (Decimal("-27.469100"), Decimal("-58.986500"))
A_10_KM = (Decimal("-27.541000"), Decimal("-58.986500"))
A_30_KM = (Decimal("-27.720900"), Decimal("-58.986500"))


class DispositivosParaDerivarTests(BaseCasos):
    def _con_gps(self, **cambios):
        return self._caso_tomado(latitud=PLAZA[0], longitud=PLAZA[1], precision_m=10, **cambios)

    def _nombres(self, filas):
        return [fila["nombre"] for fila in filas]

    def test_lo_que_devuelve_de_cada_dispositivo_y_nada_mas(self):
        """RU-14: nombre, localidad, plazas, distancia. Nada de la operación interna."""
        caso = self._con_gps()
        club = self._dispositivo("Club", camas=6, latitud=A_2_KM[0], longitud=A_2_KM[1], localidad="Resistencia")
        self._ocupar(club, 1)
        persona = Ciudadano.objects.create(dni="30999001", nombre="Con", apellido="Reserva")
        ReservaPlaza.objects.create(
            plaza=Plaza.objects.filter(sector__dispositivo=club).order_by("-codigo").first(),
            ciudadano=persona,
            desde=T0 - timedelta(hours=1),
            creada_por=self.operador,
        )

        [fila] = selectores.dispositivos_para_derivar(caso, self.operador)

        self.assertEqual(
            set(fila), {"id", "nombre", "localidad", "libres", "reservadas", "distancia_km", "marca", "faltan"}
        )
        self.assertEqual((fila["id"], fila["nombre"], fila["localidad"]), (club.pk, "Club", "Resistencia"))
        self.assertEqual((fila["libres"], fila["reservadas"]), (4, 1))
        self.assertAlmostEqual(fila["distancia_km"], 2.0, delta=0.05)
        self.assertEqual((fila["marca"], fila["faltan"]), (MARCA_ALCANZA, 0))

    def test_alcanza_faltan_y_sin_plazas(self):
        """HU-2.2: contra el total declarado, o contra las plazas que se quieran pedir."""
        caso = self._con_gps(menores_f=2, menores_m=3)  # 7 personas
        justo = self._dispositivo("Justo", camas=7)
        corto = self._dispositivo("Corto", camas=5)
        lleno = self._dispositivo("Lleno", camas=3)
        self._ocupar(lleno, 3)

        filas = {fila["id"]: fila for fila in selectores.dispositivos_para_derivar(caso, self.operador)}
        self.assertEqual((filas[justo.pk]["marca"], filas[justo.pk]["faltan"]), (MARCA_ALCANZA, 0))
        self.assertEqual((filas[corto.pk]["marca"], filas[corto.pk]["faltan"]), (MARCA_FALTAN, 2))
        self.assertEqual((filas[lleno.pk]["marca"], filas[lleno.pk]["faltan"]), (MARCA_SIN_PLAZAS, 7))

        con_cinco = {fila["id"]: fila for fila in selectores.dispositivos_para_derivar(caso, self.operador, plazas=5)}
        self.assertEqual(con_cinco[corto.pk]["marca"], MARCA_ALCANZA)

    def test_solo_aparecen_los_elegibles(self):
        """RN-2.2 / H6, la misma definición que usa ``derivar_caso``."""
        caso = self._con_gps()
        solo_cupos = TipoDispositivo.objects.create(codigo="COMEDOR", nombre="Comedor", tipos_plaza_admitidos=["CUPO"])
        de_baja = TipoDispositivo.objects.create(
            codigo="VIEJO", nombre="Viejo", tipos_plaza_admitidos=["CAMA"], activo=False
        )
        self._dispositivo("Elegible", camas=5)
        self._dispositivo("Inactivo", camas=5, estado=Dispositivo.Estado.INACTIVO)
        self._dispositivo("Comedor", tipo=solo_cupos)
        self._dispositivo("Oficina", tipo=TipoDispositivo.objects.create(codigo="OFI", nombre="Oficina"))
        self._dispositivo("De tipo dado de baja", camas=5, tipo=de_baja)

        self.assertEqual(self._nombres(selectores.dispositivos_para_derivar(caso, self.operador)), ["Elegible"])

    def test_el_orden_es_alcanza_despues_distancia_y_la_desconocida_al_final(self):
        """02 §3 y RN-2.4."""
        caso = self._con_gps()  # 2 personas
        self._dispositivo("Lejos y alcanza", camas=5, latitud=A_30_KM[0], longitud=A_30_KM[1])
        self._dispositivo("Cerca y alcanza", camas=5, latitud=A_2_KM[0], longitud=A_2_KM[1])
        self._dispositivo("Sin coordenadas y alcanza", camas=5)
        self._dispositivo("Cerca y faltan", camas=1, latitud=A_2_KM[0], longitud=A_2_KM[1])
        self._dispositivo("Medio y faltan", camas=1, latitud=A_10_KM[0], longitud=A_10_KM[1])
        lleno = self._dispositivo("Al lado y sin plazas", camas=1, latitud=PLAZA[0], longitud=PLAZA[1])
        self._ocupar(lleno, 1)

        filas = selectores.dispositivos_para_derivar(caso, self.operador)

        self.assertEqual(
            self._nombres(filas),
            [
                "Cerca y alcanza",
                "Lejos y alcanza",
                "Sin coordenadas y alcanza",
                "Cerca y faltan",
                "Medio y faltan",
                "Al lado y sin plazas",
            ],
        )
        self.assertIsNone(filas[2]["distancia_km"])
        self.assertAlmostEqual(filas[1]["distancia_km"], 30.0, delta=0.1)
        self.assertEqual(filas[5]["distancia_km"], 0.0)

    def test_un_caso_sin_gps_no_tiene_distancia_y_se_ordena_solo_por_plazas(self):
        """Hallazgo H4: no hay centroide de localidad. La distancia es desconocida."""
        localidad = Localidad.objects.create(nombre="Resistencia")
        caso = self._caso_tomado(localidad=localidad.pk)  # sin GPS, 2 personas
        self._dispositivo("Zeta alcanza", camas=5, latitud=A_2_KM[0], longitud=A_2_KM[1])
        self._dispositivo("Alfa alcanza", camas=5, latitud=A_30_KM[0], longitud=A_30_KM[1])
        self._dispositivo("Beta faltan", camas=1, latitud=PLAZA[0], longitud=PLAZA[1])

        filas = selectores.dispositivos_para_derivar(caso, self.operador)

        self.assertEqual([fila["distancia_km"] for fila in filas], [None, None, None])
        self.assertEqual(self._nombres(filas), ["Alfa alcanza", "Zeta alcanza", "Beta faltan"])

    def test_lo_autoriza_operar_en_emergencia_y_no_ver_dispositivos(self):
        """RU-14: la mesa lo ve sin ninguna capacidad de Dispositivos; un rol de Dispositivos, no."""
        caso = self._con_gps()
        self._dispositivo("Club", camas=5)
        ve_dispositivos = self._usuario(
            "ve_dispositivos", ["dispositivo.ver", "dispositivo.ver_todos"], programa=self.dispositivos
        )

        self.assertEqual(len(selectores.dispositivos_para_derivar(caso, self.operador)), 1)
        self.assertEqual(len(selectores.dispositivos_para_derivar(caso, self.supervisor)), 1)
        for usuario in (ve_dispositivos, self.agente):
            with self.subTest(usuario=usuario.username):
                with self.assertRaises(PermissionDenied):
                    selectores.dispositivos_para_derivar(caso, usuario)

    @tag("performance")
    def test_con_cincuenta_dispositivos_son_cuatro_consultas(self):
        """Sin N+1: los elegibles con su tipo y las tres de ``ocupacion_de_plazas`` en lote."""
        caso = self._con_gps()
        for n in range(50):
            dispositivo = self._dispositivo(
                f"Centro {n:02d}", camas=4, latitud=PLAZA[0] - Decimal(n) / 1000, longitud=PLAZA[1]
            )
            if n % 3 == 0:
                self._ocupar(dispositivo, 2)
        caso = CasoEmergencia.objects.select_related("grupo").get(pk=caso.pk)
        operador = User.objects.get(pk=self.operador.pk)
        selectores.dispositivos_para_derivar(caso, operador)  # resuelve y memoiza las capacidades

        with self.assertNumQueries(4):
            filas = selectores.dispositivos_para_derivar(caso, operador)

        self.assertEqual(len(filas), 50)
        self.assertEqual(filas[0]["nombre"], "Centro 00")  # a todos les alcanza: gana el más cercano

    def test_la_distancia_es_haversine(self):
        self.assertAlmostEqual(selectores.distancia_km(*PLAZA, *A_10_KM), 10.0, delta=0.05)
        # Resistencia – Sáenz Peña, unos 150 km en línea recta.
        self.assertAlmostEqual(selectores.distancia_km(-27.4511, -58.9865, -26.7852, -60.4388), 161.5, delta=2)
        self.assertEqual(selectores.distancia_km(*PLAZA, *PLAZA), 0.0)
        self.assertIsNone(selectores.distancia_km(None, None, *PLAZA))
        self.assertIsNone(selectores.distancia_km(*PLAZA, None, PLAZA[1]))


# ---------------------------------------------------------------------------
# Marcas: posible duplicado y responsable alojado
# ---------------------------------------------------------------------------


class MarcasDelCasoTests(BaseCasos):
    def test_posible_duplicado_por_el_mismo_responsable(self):
        """RN-2.14 / RN-1.11."""
        primero = self._caso(dni="31222333")
        segundo = self._caso(dni="31222333")
        otro = self._caso(dni="31999888")

        self.assertEqual(selectores.posibles_duplicados(primero), [(segundo.pk, segundo.numero)])
        self.assertEqual(selectores.posibles_duplicados(segundo), [(primero.pk, primero.numero)])
        self.assertEqual(selectores.posibles_duplicados(otro), [])

    def test_posible_duplicado_por_un_integrante(self):
        """RN-2.14: el responsable de un caso figura como integrante confirmado de otro."""
        de_ana = self._caso(dni="31222333")
        de_juan = self._caso(dni="31444555")
        IntegranteGrupo.objects.create(
            grupo=de_juan.grupo, orden=2, ciudadano=de_ana.grupo.responsable, confirmada_en=T0
        )

        self.assertEqual(selectores.posibles_duplicados(de_ana), [(de_juan.pk, de_juan.numero)])
        self.assertEqual(selectores.posibles_duplicados(de_juan), [(de_ana.pk, de_ana.numero)])

    def test_un_caso_cerrado_no_cuenta_como_duplicado(self):
        cerrado = self._caso_tomado(dni="31222333")
        servicio.cerrar_sin_alojamiento(cerrado, self.operador, "NO_REQUIERE")
        abierto = self._caso(dni="31222333")

        self.assertEqual(selectores.posibles_duplicados(abierto), [])

    @tag("performance")
    def test_los_duplicados_de_una_pagina_son_tres_consultas(self):
        casos = [self._caso(dni="31222333") for _ in range(3)] + [self._caso() for _ in range(10)]
        casos = list(CasoEmergencia.objects.select_related("grupo").filter(pk__in=[caso.pk for caso in casos]))

        with self.assertNumQueries(3):
            duplicados = selectores.posibles_duplicados_de(casos)

        self.assertEqual(len(duplicados), 3)
        self.assertTrue(all(len(otros) == 2 for otros in duplicados.values()))

    def test_responsable_alojado_dice_donde(self):
        """RN-2.15: la mesa ve en qué dispositivo; el recorte de alcance es de Dispositivos."""
        caso = self._caso(dni="31222333")
        sin_estadia = self._caso(dni="31999888")
        parador = self._dispositivo("Parador Norte", camas=2)
        estadia = Estadia.objects.create(
            ciudadano=caso.grupo.responsable,
            dispositivo=parador,
            fecha_ingreso=T0 - timedelta(days=2),
            clave_alojamiento=Estadia.clave_para(caso.grupo.responsable),
        )

        alojado = selectores.responsable_alojado(caso, self.operador)

        self.assertEqual((alojado.estadia_id, alojado.dispositivo_id), (estadia.pk, parador.pk))
        self.assertEqual((alojado.dispositivo, alojado.desde), ("Parador Norte", T0 - timedelta(days=2)))
        self.assertIsNone(selectores.responsable_alojado(sin_estadia, self.operador))

    def test_una_estadia_egresada_no_marca_al_responsable(self):
        caso = self._caso(dni="31222333")
        Estadia.objects.create(
            ciudadano=caso.grupo.responsable,
            dispositivo=self._dispositivo("Parador", camas=2),
            fecha_ingreso=T0 - timedelta(days=5),
            fecha_egreso=T0 - timedelta(days=1),
            estado=Estadia.Estado.EGRESADA,
        )
        self.assertIsNone(selectores.responsable_alojado(caso, self.operador))

    def test_responsable_alojado_es_una_consulta_por_pagina_y_pide_la_mesa(self):
        casos = [self._caso() for _ in range(5)]
        casos = list(CasoEmergencia.objects.select_related("grupo").filter(pk__in=[caso.pk for caso in casos]))
        operador = User.objects.get(pk=self.operador.pk)
        selectores.responsables_alojados(casos, operador)

        with self.assertNumQueries(1):
            self.assertEqual(selectores.responsables_alojados(casos, operador), {})
        with self.assertRaises(PermissionDenied):
            selectores.responsables_alojados(casos, self.agente)
