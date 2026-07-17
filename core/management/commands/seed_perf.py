"""Datos sintéticos, deterministas e idempotentes para auditorías de performance."""

import os
import sys
from datetime import UTC, date, datetime, timedelta

from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone

from conversaciones.models import ColaAsignacion, Conversacion, Mensaje
from core import rbac
from core.models import Localidad, Municipio, Provincia
from legajos.models import AlertaCiudadano, Ciudadano, HistorialContacto, LegajoAtencion, VinculoFamiliar
from programas.management.commands.seed_becas import ROL_ADMIN, ROL_COORDINADOR, ROL_TERRITORIAL
from programas.models import (
    AsignacionCoordinador,
    AsignacionTerritorial,
    Convocatoria,
    CupoSegmento,
    DerivacionPrograma,
    Formulario,
    InscripcionPrograma,
    Programa,
    Relevamiento,
    RequisitoNativo,
    Segmento,
    Subsegmento,
    TipoCampo,
)

PERF_PREFIX = "PERF"
PERF_ADMIN_USERNAME = "perf_admin"
PERF_CITIZEN_USERNAME = "perf_ciudadano"
PERF_FIRST_DNI = "80000000"


def _ensure_user(username, *, first_name, last_name, is_staff=False, is_superuser=False):
    user, created = User.objects.get_or_create(username=username)
    user.first_name = first_name
    user.last_name = last_name
    user.email = f"{username}@perf.invalid"
    user.is_active = True
    user.is_staff = is_staff
    user.is_superuser = is_superuser
    user.last_login = timezone.now()
    if created:
        user.set_unusable_password()
    user.save()
    return user


def _set_groups(user, *group_names):
    groups = Group.objects.filter(name__in=group_names)
    found = set(groups.values_list("name", flat=True))
    missing = set(group_names) - found
    if missing:
        raise CommandError(f"Faltan roles requeridos por seed_perf: {', '.join(sorted(missing))}")
    user.groups.set(groups)


class Command(BaseCommand):
    help = "Siembra datos sintéticos namespaced PERF para scripts/CI de performance. Nunca usa datos productivos."

    def add_arguments(self, parser):
        parser.add_argument("--scale", type=int, default=200, help="Cantidad de entidades principales (default: 200).")

    def handle(self, *args, **options):
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        scale = options["scale"]
        if scale < 1:
            raise CommandError("--scale debe ser mayor que cero")
        if (
            os.environ.get("PYTEST_RUNNING") != "1"
            or connection.vendor != "sqlite"
            or connection.settings_dict.get("NAME") not in (":memory:", "file:memorydb_default?mode=memory&cache=shared")
        ):
            raise CommandError("seed_perf solo puede ejecutarse con PYTEST_RUNNING=1 y SQLite in-memory")

        if "auth_user" not in connection.introspection.table_names():
            call_command("migrate", interactive=False, run_syncdb=True, verbosity=0)

        with transaction.atomic():
            self._seed(scale)

    def _seed(self, scale):

        call_command("seed_datos_base", verbosity=0)

        admin = _ensure_user(
            PERF_ADMIN_USERNAME,
            first_name="Administrador",
            last_name="Performance",
            is_staff=True,
            is_superuser=False,
        )
        citizen_user = _ensure_user(
            PERF_CITIZEN_USERNAME,
            first_name="Ciudadano",
            last_name="Performance",
        )
        coordinator = _ensure_user(
            "perf_coordinador",
            first_name="Coordinador",
            last_name="Performance",
            is_staff=True,
        )
        operators = [
            _ensure_user(
                f"perf_operador_{index:02d}",
                first_name=f"Operador {index:02d}",
                last_name="Performance",
                is_staff=True,
            )
            for index in range(1, 5)
        ]

        _set_groups(admin, rbac.ROL_ADMINISTRADOR, ROL_ADMIN)
        _set_groups(citizen_user, rbac.GRUPO_CIUDADANO_PORTAL)
        _set_groups(coordinator, ROL_COORDINADOR)
        for operator in operators:
            _set_groups(operator, "Administrador")
            ColaAsignacion.objects.update_or_create(
                operador=operator,
                defaults={"activo": True, "max_conversaciones": 1000, "conversaciones_actuales": 0},
            )

        provincia = Provincia.objects.filter(nombre__icontains="chaco").first() or Provincia.objects.first()
        if provincia is None:
            provincia = Provincia.objects.create(nombre="Chaco PERF")
        municipio = Municipio.objects.filter(provincia=provincia).first()
        if municipio is None:
            municipio = Municipio.objects.create(nombre="Municipio PERF", provincia=provincia)
        localidad = Localidad.objects.filter(municipio=municipio).first()
        if localidad is None:
            localidad = Localidad.objects.create(nombre="Localidad PERF", municipio=municipio)

        becas = Programa.objects.get(codigo="BECAS")
        apoyo, _ = Programa.objects.update_or_create(
            codigo="PERF-APOYO",
            defaults={
                "nombre": "Programa Apoyo PERF",
                "tipo": Programa.TipoPrograma.ACOMPANAMIENTO_SOCIAL,
                "descripcion": "Programa sintético para mediciones de performance.",
                "naturaleza": Programa.Naturaleza.PERSISTENTE,
                "estado": Programa.Estado.ACTIVO,
                "orden": 900,
            },
        )

        segment_count = max(10, scale // 10)
        segmentos = []
        convocatorias = []
        territoriales = []
        for index in range(segment_count):
            segmento, _ = Segmento.objects.update_or_create(
                nombre=f"PERF Segmento {index:03d}",
                defaults={
                    "descripcion": "Segmento sintético para auditoría de performance.",
                    "cupo_maximo": max(scale, 200),
                    "requiere_gps": index % 2 == 0,
                    "activo": True,
                },
            )
            subsegmento, _ = Subsegmento.objects.update_or_create(
                segmento=segmento,
                nombre=f"PERF Subsegmento {index:03d}",
                defaults={"descripcion": "Subsegmento sintético.", "cupo_maximo": max(scale // 2, 100)},
            )
            CupoSegmento.objects.update_or_create(segmento=segmento, defaults={"cupo_ocupado": 0})
            RequisitoNativo.objects.update_or_create(
                segmento=segmento,
                subsegmento=None,
                texto=f"PERF requisito {index:03d}",
                defaults={"tipo": TipoCampo.STRING, "orden": 900 + index, "obligatorio": True},
            )
            territorial = _ensure_user(
                f"perf_territorial_{index:03d}",
                first_name=f"Territorial {index:03d}",
                last_name="Performance",
            )
            _set_groups(territorial, ROL_TERRITORIAL)
            AsignacionCoordinador.objects.update_or_create(
                segmento=segmento,
                coordinador=coordinator,
                defaults={"activo": True},
            )
            AsignacionTerritorial.objects.update_or_create(
                territorial=territorial,
                defaults={"segmento": segmento},
            )
            convocatoria, _ = Convocatoria.objects.update_or_create(
                nombre=f"PERF Convocatoria {index:03d}",
                segmento=segmento,
                defaults={
                    "subsegmento": subsegmento,
                    "fecha_inicio": date(2025, 1, 1),
                    "fecha_fin": date(2030, 12, 31),
                    "descripcion": "Convocatoria sintética para auditoría de performance.",
                    "activo": True,
                },
            )
            segmentos.append(segmento)
            convocatorias.append(convocatoria)
            territoriales.append(territorial)

        relevamientos = []
        for index in range(scale):
            bucket = 0 if index < min(50, scale) else index % segment_count
            relevamiento, _ = Relevamiento.objects.update_or_create(
                nombre=f"PERF Relevamiento {index:04d}",
                defaults={
                    "convocatoria": convocatorias[bucket],
                    "territorial": territoriales[bucket],
                    "fecha_asignada": date(2025, 2, 1) + timedelta(days=index % 28),
                    "zona": f"Zona PERF {bucket:03d}",
                    "observaciones": "Relevamiento sintético para auditoría de performance.",
                    "estado": Relevamiento.Estado.EN_REVISION,
                },
            )
            relevamientos.append(relevamiento)

        ciudadanos = []
        fixed_start = datetime(2025, 1, 1, 12, 0, tzinfo=UTC)
        for index in range(scale):
            dni = str(80000000 + index)
            ciudadano, _ = Ciudadano.objects.update_or_create(
                dni=dni,
                defaults={
                    "nombre": f"Nombre PERF {index:04d}",
                    "apellido": f"Apellido PERF {index:04d}",
                    "fecha_nacimiento": date(1980 + index % 30, index % 12 + 1, index % 27 + 1),
                    "genero": Ciudadano.Genero.MASCULINO if index % 2 == 0 else Ciudadano.Genero.FEMENINO,
                    "telefono": f"3704{index:06d}",
                    "email": f"ciudadano{index:04d}@perf.invalid",
                    "domicilio": f"Calle PERF {index}",
                    "provincia": provincia,
                    "municipio": municipio,
                    "localidad": localidad,
                    "activo": True,
                    "usuario": citizen_user if index == 0 else None,
                    "tipo_vivienda": Ciudadano.TipoVivienda.PROPIA,
                    "tenencia_vivienda": Ciudadano.TenenciaVivienda.TITULAR,
                    "condiciones_vivienda": "Condiciones sintéticas " + ("x" * 256),
                    "situacion_laboral": Ciudadano.SituacionLaboral.EMPLEADO_FORMAL,
                    "ingreso_estimado": Ciudadano.IngresoEstimado.ENTRE_1_2_CBT,
                    "nivel_educativo": Ciudadano.NivelEducativo.SECUNDARIO_COMPLETO,
                    "cobertura_medica": "Cobertura PERF",
                    "medicacion_habitual": "Sin medicación habitual",
                    "dni_fisico": Ciudadano.DniFisico.TIENE,
                    "estado_renaper": Ciudadano.EstadoRenaper.REGISTRADO,
                    "estado_migratorio": Ciudadano.EstadoMigratorio.NACIONAL,
                    "observaciones": "Observación sintética " + ("y" * 512),
                },
            )
            legajo, _ = LegajoAtencion.objects.update_or_create(
                codigo=f"PERF-LEG-{index:05d}",
                defaults={
                    "responsable": operators[index % len(operators)],
                    "estado": LegajoAtencion.Estado.EN_SEGUIMIENTO,
                    "via_ingreso": LegajoAtencion.ViaIngreso.ESPONTANEA,
                    "plan_vigente": index % 2 == 0,
                    "nivel_riesgo": "ALTO" if index % 20 == 0 else "BAJO",
                    "notas": "Notas sintéticas " + ("z" * 512),
                },
            )
            inscripcion, _ = InscripcionPrograma.objects.update_or_create(
                ciudadano=ciudadano,
                programa=becas,
                defaults={
                    "estado": InscripcionPrograma.Estado.ACTIVO,
                    "via_ingreso": InscripcionPrograma.ViaIngreso.DIRECTO,
                    "responsable": operators[index % len(operators)],
                    "legajo_id": legajo.pk,
                    "notas": "Inscripción sintética PERF.",
                },
            )
            InscripcionPrograma.objects.update_or_create(
                ciudadano=ciudadano,
                programa=apoyo,
                defaults={
                    "estado": InscripcionPrograma.Estado.EN_SEGUIMIENTO,
                    "via_ingreso": InscripcionPrograma.ViaIngreso.DERIVACION_INTERNA,
                    "responsable": operators[index % len(operators)],
                    "notas": "Segunda inscripción sintética PERF.",
                },
            )
            DerivacionPrograma.objects.update_or_create(
                ciudadano=ciudadano,
                programa_destino=apoyo,
                defaults={
                    "programa_origen": becas,
                    "inscripcion_origen": inscripcion,
                    "motivo": f"PERF derivación {index:04d}",
                    "urgencia": DerivacionPrograma.Urgencia.MEDIA,
                    "estado": DerivacionPrograma.Estado.PENDIENTE,
                    "derivado_por": admin,
                },
            )
            HistorialContacto.objects.update_or_create(
                legajo=legajo,
                motivo=f"PERF contacto {index:04d}",
                defaults={
                    "tipo_contacto": "LLAMADA",
                    "fecha_contacto": fixed_start + timedelta(minutes=index),
                    "duracion_minutos": 15,
                    "profesional": operators[index % len(operators)],
                    "estado": "EXITOSO",
                    "resumen": "Resumen sintético para auditoría de performance.",
                    "acuerdos": "Acuerdo sintético.",
                    "proximos_pasos": "Seguimiento sintético.",
                    "seguimiento_requerido": index % 3 == 0,
                },
            )
            AlertaCiudadano.objects.update_or_create(
                ciudadano=ciudadano,
                tipo=AlertaCiudadano.TipoAlerta.SIN_PLAN,
                mensaje=f"PERF alerta {index:04d}",
                defaults={
                    "legajo": legajo,
                    "prioridad": AlertaCiudadano.Prioridad.ALTA if index % 20 == 0 else AlertaCiudadano.Prioridad.MEDIA,
                    "activa": True,
                },
            )
            form_relevamiento = relevamientos[0] if index < min(50, scale) else relevamientos[index]
            Formulario.objects.update_or_create(
                relevamiento=form_relevamiento,
                ciudadano=ciudadano,
                defaults={
                    "estado": Formulario.Estado.ENVIADO,
                    "validado_renaper": index % 2 == 0,
                    "celular": f"3704{index:06d}",
                    "email_contacto": f"formulario{index:04d}@perf.invalid",
                    "data": {"origen": PERF_PREFIX, "indice": index, "texto": "d" * 512},
                    "created_by": territoriales[index % segment_count],
                },
            )
            ciudadanos.append(ciudadano)

        if len(ciudadanos) > 1:
            for index, ciudadano in enumerate(ciudadanos):
                VinculoFamiliar.objects.update_or_create(
                    ciudadano_principal=ciudadano,
                    ciudadano_vinculado=ciudadanos[(index + 1) % len(ciudadanos)],
                    tipo_vinculo="REFERENTE",
                    defaults={"activo": True, "es_contacto_emergencia": index % 4 == 0},
                )

        conversation_times = [fixed_start + timedelta(days=1, minutes=index) for index in range(scale)]
        existing = {
            conversation.fecha_inicio: conversation
            for conversation in Conversacion.objects.filter(
                ciudadano_usuario=citizen_user,
                fecha_inicio__in=conversation_times,
            )
        }
        missing = []
        for index, started_at in enumerate(conversation_times):
            if started_at in existing:
                continue
            missing.append(
                Conversacion(
                    tipo="personal",
                    estado=("pendiente", "activa", "cerrada")[index % 3],
                    prioridad=("normal", "alta", "urgente")[index % 3],
                    dni_ciudadano=PERF_FIRST_DNI,
                    fecha_inicio=started_at,
                    operador_asignado=None if index % 3 == 0 else operators[index % len(operators)],
                    ciudadano_usuario=citizen_user,
                )
            )
        Conversacion.objects.bulk_create(missing)
        conversations = list(
            Conversacion.objects.filter(ciudadano_usuario=citizen_user, fecha_inicio__in=conversation_times).order_by(
                "fecha_inicio"
            )
        )
        for index, conversation in enumerate(conversations):
            conversation.tipo = "personal"
            conversation.estado = ("pendiente", "activa", "cerrada")[index % 3]
            conversation.prioridad = ("normal", "alta", "urgente")[index % 3]
            conversation.dni_ciudadano = PERF_FIRST_DNI
            conversation.operador_asignado = None if index % 3 == 0 else operators[index % len(operators)]
            conversation.ciudadano_usuario = citizen_user
        Conversacion.objects.bulk_update(
            conversations,
            ["tipo", "estado", "prioridad", "dni_ciudadano", "operador_asignado", "ciudadano_usuario"],
        )

        expected_messages = []
        for index, conversation in enumerate(conversations):
            message_count = 50 if index == 0 else 4
            for message_index in range(message_count):
                expected_messages.append(
                    Mensaje(
                        conversacion=conversation,
                        remitente="ciudadano" if message_index % 2 == 0 else "operador",
                        contenido=f"PERF-MSG-{index:04d}-{message_index:02d} " + ("m" * 128),
                        fecha_envio=conversation.fecha_inicio + timedelta(seconds=message_index),
                        leido=message_index % 3 == 0,
                    )
                )
        existing_contents = set(
            Mensaje.objects.filter(contenido__startswith="PERF-MSG-").values_list("contenido", flat=True)
        )
        Mensaje.objects.bulk_create(
            [message for message in expected_messages if message.contenido not in existing_contents]
        )
        expected_by_content = {message.contenido: message for message in expected_messages}
        stored_messages = list(Mensaje.objects.filter(contenido__in=expected_by_content))
        for message in stored_messages:
            expected = expected_by_content[message.contenido]
            message.conversacion = expected.conversacion
            message.remitente = expected.remitente
            message.fecha_envio = expected.fecha_envio
            message.leido = expected.leido
        Mensaje.objects.bulk_update(stored_messages, ["conversacion", "remitente", "fecha_envio", "leido"])

        cache.clear()
        self.stdout.write(
            self.style.SUCCESS(
                "seed_perf completo: "
                f"{scale} ciudadanos/legajos/conversaciones/formularios, "
                f"{len(relevamientos)} relevamientos y {segment_count} segmentos. "
                "Trámites: no aplicable (módulo actual sin modelos/rutas)."
            )
        )
