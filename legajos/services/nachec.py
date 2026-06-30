from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from ..models.nachec import (
    CasoNachec,
    EstadoCaso,
    EstadoTarea,
    HistorialEstadoCaso,
    TareaNachec,
    TipoTarea,
)


class ServicioTransicionNachec:
    """Servicio para manejar transiciones de estado del caso."""

    TRANSICIONES_PERMITIDAS = {
        EstadoCaso.DERIVADO: [EstadoCaso.EN_REVISION, EstadoCaso.RECHAZADO],
        EstadoCaso.EN_REVISION: [EstadoCaso.A_ASIGNAR, EstadoCaso.RECHAZADO],
        EstadoCaso.A_ASIGNAR: [EstadoCaso.ASIGNADO],
        EstadoCaso.ASIGNADO: [EstadoCaso.EN_RELEVAMIENTO, EstadoCaso.SUSPENDIDO],
        EstadoCaso.EN_RELEVAMIENTO: [EstadoCaso.EVALUADO, EstadoCaso.SUSPENDIDO],
        EstadoCaso.EVALUADO: [
            EstadoCaso.PLAN_DEFINIDO,
            EstadoCaso.EN_RELEVAMIENTO,
            EstadoCaso.SUSPENDIDO,
        ],
        EstadoCaso.PLAN_DEFINIDO: [EstadoCaso.EN_EJECUCION, EstadoCaso.SUSPENDIDO],
        EstadoCaso.EN_EJECUCION: [EstadoCaso.EN_SEGUIMIENTO, EstadoCaso.SUSPENDIDO],
        EstadoCaso.EN_SEGUIMIENTO: [EstadoCaso.CERRADO, EstadoCaso.SUSPENDIDO],
        EstadoCaso.SUSPENDIDO: [
            EstadoCaso.ASIGNADO,
            EstadoCaso.EN_RELEVAMIENTO,
            EstadoCaso.EVALUADO,
            EstadoCaso.PLAN_DEFINIDO,
            EstadoCaso.EN_EJECUCION,
            EstadoCaso.EN_SEGUIMIENTO,
        ],
    }

    @classmethod
    def validar_transicion(cls, caso, nuevo_estado):
        estados_permitidos = cls.TRANSICIONES_PERMITIDAS.get(caso.estado, [])
        if nuevo_estado not in estados_permitidos:
            raise ValidationError(
                f"No se puede cambiar de {caso.get_estado_display()} a {EstadoCaso(nuevo_estado).label}"
            )

    @classmethod
    def registrar_historial(cls, caso, estado_anterior, estado_nuevo, usuario, observacion=""):
        HistorialEstadoCaso.objects.create(
            caso=caso,
            estado_anterior=estado_anterior,
            estado_nuevo=estado_nuevo,
            usuario=usuario,
            observacion=observacion,
        )

    @classmethod
    @transaction.atomic
    def tomar_caso(cls, caso, usuario):
        cls.validar_transicion(caso, EstadoCaso.EN_REVISION)
        estado_anterior = caso.estado
        caso.estado = EstadoCaso.EN_REVISION
        caso.operador_admision = usuario
        caso.save()
        cls.registrar_historial(caso, estado_anterior, caso.estado, usuario, "Caso tomado por operador")
        return caso

    @classmethod
    @transaction.atomic
    def rechazar_caso(cls, caso, usuario, motivo):
        if not motivo:
            raise ValidationError("El motivo de rechazo es obligatorio")

        cls.validar_transicion(caso, EstadoCaso.RECHAZADO)
        estado_anterior = caso.estado
        caso.estado = EstadoCaso.RECHAZADO
        caso.motivo_rechazo = motivo
        caso.fecha_cierre = timezone.now().date()
        caso.save()
        cls.registrar_historial(caso, estado_anterior, caso.estado, usuario, f"Rechazado: {motivo}")
        return caso

    @classmethod
    @transaction.atomic
    def enviar_a_asignacion(cls, caso, usuario):
        if not caso.ciudadano_titular:
            raise ValidationError("Debe existir un ciudadano titular vinculado")
        if not caso.municipio or not caso.localidad:
            raise ValidationError("Debe completar municipio y localidad")

        cls.validar_transicion(caso, EstadoCaso.A_ASIGNAR)
        estado_anterior = caso.estado
        caso.estado = EstadoCaso.A_ASIGNAR
        caso.save()
        cls.registrar_historial(caso, estado_anterior, caso.estado, usuario, "Enviado a asignación")
        return caso

    @classmethod
    @transaction.atomic
    def asignar_territorial(cls, caso, coordinador, territorial, fecha_limite_relevamiento=None):
        if not territorial:
            raise ValidationError("Debe seleccionar un territorial")

        cls.validar_transicion(caso, EstadoCaso.ASIGNADO)
        estado_anterior = caso.estado
        caso.estado = EstadoCaso.ASIGNADO
        caso.coordinador = coordinador
        caso.territorial = territorial
        caso.fecha_asignacion = timezone.now().date()

        if not fecha_limite_relevamiento:
            fecha_limite_relevamiento = timezone.now().date() + timedelta(days=7)
        caso.sla_relevamiento = fecha_limite_relevamiento
        caso.save()

        TareaNachec.objects.create(
            caso=caso,
            tipo=TipoTarea.RELEVAMIENTO,
            titulo="Relevamiento sociofamiliar inicial",
            descripcion="Realizar relevamiento completo de la situación sociofamiliar",
            asignado_a=territorial,
            creado_por=coordinador,
            estado=EstadoTarea.PENDIENTE,
            prioridad=caso.prioridad,
            fecha_vencimiento=fecha_limite_relevamiento,
        )

        cls.registrar_historial(
            caso,
            estado_anterior,
            caso.estado,
            coordinador,
            f"Asignado a {territorial.get_full_name()}",
        )
        return caso

    @classmethod
    @transaction.atomic
    def iniciar_relevamiento(cls, caso, territorial):
        if caso.territorial != territorial:
            raise ValidationError("Solo el territorial asignado puede iniciar el relevamiento")

        cls.validar_transicion(caso, EstadoCaso.EN_RELEVAMIENTO)
        estado_anterior = caso.estado
        caso.estado = EstadoCaso.EN_RELEVAMIENTO
        caso.fecha_relevamiento = timezone.now().date()
        caso.save()
        cls.registrar_historial(caso, estado_anterior, caso.estado, territorial, "Relevamiento iniciado")
        return caso

    @classmethod
    @transaction.atomic
    def finalizar_relevamiento(cls, caso, territorial):
        if not hasattr(caso, "relevamiento"):
            raise ValidationError("No existe relevamiento asociado")
        if not caso.relevamiento.completado:
            raise ValidationError("El relevamiento debe estar completado")

        cls.validar_transicion(caso, EstadoCaso.EVALUADO)
        estado_anterior = caso.estado
        caso.estado = EstadoCaso.EVALUADO
        caso.save()
        cls.registrar_historial(caso, estado_anterior, caso.estado, territorial, "Relevamiento finalizado")
        return caso

    @classmethod
    @transaction.atomic
    def confirmar_evaluacion(cls, caso, evaluador):
        if not hasattr(caso, "evaluacion"):
            raise ValidationError("No existe evaluación de vulnerabilidad")
        if not caso.evaluacion.categoria_final:
            raise ValidationError("Debe completar la categoría final de vulnerabilidad")

        cls.validar_transicion(caso, EstadoCaso.PLAN_DEFINIDO)
        estado_anterior = caso.estado
        caso.estado = EstadoCaso.PLAN_DEFINIDO
        caso.fecha_evaluacion = timezone.now().date()
        caso.save()
        cls.registrar_historial(caso, estado_anterior, caso.estado, evaluador, "Evaluación confirmada")
        return caso

    @classmethod
    @transaction.atomic
    def activar_plan(cls, caso, referente):
        plan_vigente = caso.planes.filter(vigente=True).first()
        if not plan_vigente:
            raise ValidationError("No existe plan de intervención vigente")

        cls.validar_transicion(caso, EstadoCaso.EN_EJECUCION)
        estado_anterior = caso.estado
        caso.estado = EstadoCaso.EN_EJECUCION
        caso.referente_programa = referente
        plan_vigente.fecha_activacion = timezone.now()
        plan_vigente.save()
        caso.save()
        cls.registrar_historial(caso, estado_anterior, caso.estado, referente, "Plan activado")
        return caso

    @classmethod
    @transaction.atomic
    def pasar_a_seguimiento(cls, caso, usuario):
        cls.validar_transicion(caso, EstadoCaso.EN_SEGUIMIENTO)
        estado_anterior = caso.estado
        caso.estado = EstadoCaso.EN_SEGUIMIENTO
        caso.save()
        cls.registrar_historial(caso, estado_anterior, caso.estado, usuario, "Pasado a seguimiento")
        return caso

    @classmethod
    @transaction.atomic
    def cerrar_caso(cls, caso, usuario, motivo_cierre):
        if not motivo_cierre:
            raise ValidationError("El motivo de cierre es obligatorio")

        cls.validar_transicion(caso, EstadoCaso.CERRADO)
        estado_anterior = caso.estado
        caso.estado = EstadoCaso.CERRADO
        caso.motivo_cierre = motivo_cierre
        caso.fecha_cierre = timezone.now().date()
        caso.save()
        cls.registrar_historial(caso, estado_anterior, caso.estado, usuario, f"Cerrado: {motivo_cierre}")
        return caso

    @classmethod
    @transaction.atomic
    def suspender_caso(cls, caso, usuario, motivo_suspension):
        if not motivo_suspension:
            raise ValidationError("El motivo de suspensión es obligatorio")

        cls.validar_transicion(caso, EstadoCaso.SUSPENDIDO)
        estado_anterior = caso.estado
        caso.estado = EstadoCaso.SUSPENDIDO
        caso.motivo_suspension = motivo_suspension
        caso.save()
        cls.registrar_historial(
            caso,
            estado_anterior,
            caso.estado,
            usuario,
            f"Suspendido: {motivo_suspension}",
        )
        return caso

    @classmethod
    @transaction.atomic
    def reactivar_caso(cls, caso, usuario, estado_destino, motivo_reactivacion):
        if caso.estado != EstadoCaso.SUSPENDIDO:
            raise ValidationError("Solo se pueden reactivar casos suspendidos")
        if not motivo_reactivacion:
            raise ValidationError("El motivo de reactivación es obligatorio")

        cls.validar_transicion(caso, estado_destino)
        estado_anterior = caso.estado
        caso.estado = estado_destino
        caso.motivo_suspension = ""
        caso.save()
        cls.registrar_historial(
            caso,
            estado_anterior,
            caso.estado,
            usuario,
            f"Reactivado: {motivo_reactivacion}",
        )
        return caso


class ServicioDeteccionDuplicados:
    """Servicio para detectar casos duplicados."""

    @classmethod
    def detectar_duplicados(cls, ciudadano):
        casos_activos = CasoNachec.objects.filter(ciudadano_titular=ciudadano).exclude(
            estado__in=[EstadoCaso.CERRADO, EstadoCaso.RECHAZADO]
        )
        return casos_activos.exists(), casos_activos

    @classmethod
    def marcar_duplicado(cls, caso):
        caso.tiene_duplicado = True
        caso.save()


class ServicioSLA:
    """Servicio para calcular y validar SLAs."""

    @classmethod
    def calcular_sla_revision(cls, fecha_derivacion, dias_habiles=2):
        fecha = fecha_derivacion
        dias_agregados = 0

        while dias_agregados < dias_habiles:
            fecha += timedelta(days=1)
            if fecha.weekday() < 5:
                dias_agregados += 1

        return fecha

    @classmethod
    def calcular_sla_relevamiento(cls, fecha_asignacion, dias_habiles=7):
        return cls.calcular_sla_revision(fecha_asignacion, dias_habiles)

    @classmethod
    def esta_vencido(cls, fecha_sla):
        if not fecha_sla:
            return False
        return timezone.now().date() > fecha_sla


class ServicioOperacionNachec:
    """Orquesta tareas y transiciones operativas alrededor del caso."""

    ESTADOS_CASOS_ACTIVOS = [
        EstadoCaso.ASIGNADO,
        EstadoCaso.EN_RELEVAMIENTO,
        EstadoCaso.EN_EJECUCION,
        EstadoCaso.EN_SEGUIMIENTO,
    ]

    @staticmethod
    @transaction.atomic
    def completar_validacion(caso, usuario):
        tarea, created = TareaNachec.objects.get_or_create(
            caso=caso,
            tipo=TipoTarea.VALIDACION,
            defaults={
                "titulo": "Revisión inicial - Validación de datos",
                "descripcion": "Checklist de revisión inicial completado",
                "asignado_a": usuario,
                "creado_por": usuario,
                "estado": EstadoTarea.COMPLETADA,
                "prioridad": caso.prioridad or "MEDIA",
                "fecha_vencimiento": timezone.now().date() + timedelta(days=2),
            },
        )

        if not created and tarea.estado != EstadoTarea.COMPLETADA:
            tarea.estado = EstadoTarea.COMPLETADA
            tarea.save(update_fields=["estado", "modificado"])

        return tarea

    @staticmethod
    @transaction.atomic
    def completar_tarea(tarea):
        if tarea.estado != EstadoTarea.COMPLETADA:
            tarea.estado = EstadoTarea.COMPLETADA
            tarea.save(update_fields=["estado", "modificado"])
        return tarea

    @staticmethod
    def build_envio_asignacion_context(caso):
        tarea_validacion = TareaNachec.objects.filter(caso=caso, tipo=TipoTarea.VALIDACION).first()
        validaciones = {
            "tarea_completada": bool(tarea_validacion and tarea_validacion.estado == EstadoTarea.COMPLETADA),
            "tiene_dni": bool(caso.ciudadano_titular and caso.ciudadano_titular.dni),
            "tiene_prioridad": bool(caso.prioridad),
            "tiene_municipio": bool(caso.ciudadano_titular and caso.ciudadano_titular.municipio),
            "tiene_localidad": bool(caso.localidad and caso.localidad != "Sin especificar"),
        }
        puede_confirmar = all(
            [
                validaciones["tarea_completada"],
                validaciones["tiene_dni"],
                validaciones["tiene_prioridad"],
                validaciones["tiene_municipio"],
            ]
        )
        return {
            "validaciones": validaciones,
            "puede_confirmar": puede_confirmar,
            "tarea_validacion": tarea_validacion,
        }

    @staticmethod
    def _get_tarea_asignacion_pendiente(caso):
        return TareaNachec.objects.filter(
            caso=caso,
            tipo=TipoTarea.OTRO,
            titulo__icontains="Asignar territorial",
            estado__in=[EstadoTarea.PENDIENTE, EstadoTarea.EN_PROCESO],
        ).first()

    @classmethod
    @transaction.atomic
    def enviar_a_asignacion(cls, caso, usuario, municipio=None, localidad=None, observaciones=""):
        caso.refresh_from_db()
        if caso.estado != EstadoCaso.EN_REVISION:
            raise ValidationError("El caso ya fue procesado por otro usuario")

        tarea_validacion = TareaNachec.objects.filter(
            caso=caso,
            tipo=TipoTarea.VALIDACION,
            estado=EstadoTarea.COMPLETADA,
        ).first()
        if not tarea_validacion:
            raise ValidationError("No se puede enviar: la tarea de validación no está completada")
        if not caso.ciudadano_titular.dni:
            raise ValidationError("No se puede enviar: falta DNI del titular")
        if not caso.ciudadano_titular.municipio:
            raise ValidationError(
                "No se puede enviar: debe especificar municipio del ciudadano para asignación territorial"
            )

        if municipio:
            caso.municipio = municipio
        if localidad:
            caso.localidad = localidad

        estado_anterior = caso.estado
        caso.estado = EstadoCaso.A_ASIGNAR
        caso.fecha_envio_asignacion = timezone.now()
        sla_horas = {"URGENTE": 12, "ALTA": 12, "MEDIA": 24, "BAJA": 48}.get(caso.prioridad, 24)
        caso.sla_asignacion_hasta = timezone.now() + timedelta(hours=sla_horas)
        caso.save()

        tarea = cls._get_tarea_asignacion_pendiente(caso)
        descripcion = f"""Caso enviado a asignación territorial.

Municipio: {caso.municipio}
Localidad: {caso.localidad}
Prioridad: {caso.get_prioridad_display()}

Observaciones del operador:
{observaciones}

Debe asignar un territorial de la zona para iniciar relevamiento."""
        if tarea:
            tarea.descripcion = descripcion
            tarea.prioridad = caso.prioridad
            tarea.fecha_vencimiento = (timezone.now() + timedelta(hours=sla_horas)).date()
            tarea.save()
        else:
            tarea = TareaNachec.objects.create(
                caso=caso,
                tipo=TipoTarea.OTRO,
                titulo="Asignar territorial al caso",
                descripcion=descripcion,
                asignado_a=usuario,
                creado_por=usuario,
                estado=EstadoTarea.PENDIENTE,
                prioridad=caso.prioridad,
                fecha_vencimiento=(timezone.now() + timedelta(hours=sla_horas)).date(),
            )

        HistorialEstadoCaso.objects.create(
            caso=caso,
            estado_anterior=estado_anterior,
            estado_nuevo=caso.estado,
            usuario=usuario,
            observacion=f"""Caso enviado a asignación territorial.
SLA: {sla_horas}h
Municipio: {caso.municipio}
Localidad: {caso.localidad}
Observaciones: {observaciones}""",
        )

        return {"caso": caso, "tarea": tarea, "sla_horas": sla_horas}

    @classmethod
    @transaction.atomic
    def asignar_territorial(cls, caso, coordinador, territorial, fecha_limite_obj, instrucciones):
        if caso.estado != EstadoCaso.A_ASIGNAR:
            raise ValidationError("El caso ya fue asignado por otro usuario. Actualice la pantalla.")
        if not territorial:
            raise ValidationError("Debe seleccionar un territorial válido")
        if len((instrucciones or "").strip()) < 10:
            raise ValidationError("Las instrucciones deben tener al menos 10 caracteres")
        if fecha_limite_obj < timezone.now().date():
            raise ValidationError("La fecha límite no puede ser anterior a hoy")

        estado_anterior = caso.estado
        caso.estado = EstadoCaso.ASIGNADO
        caso.territorial = territorial
        caso.coordinador = coordinador
        caso.fecha_asignacion = timezone.now().date()
        caso.sla_relevamiento = fecha_limite_obj
        caso.instrucciones_asignacion = instrucciones
        caso.save()

        tarea_asignacion = cls._get_tarea_asignacion_pendiente(caso)
        if tarea_asignacion:
            tarea_asignacion.estado = EstadoTarea.COMPLETADA
            tarea_asignacion.fecha_completada = timezone.now()
            tarea_asignacion.resultado = (
                f"Asignado a {territorial.get_full_name()}. SLA relevamiento: {fecha_limite_obj.strftime('%d/%m/%Y')}"
            )
            tarea_asignacion.save()

        descripcion_relevamiento = f"""Realizar relevamiento sociofamiliar del caso.

Instrucciones del coordinador:
{instrucciones}

Datos del caso:
- Ciudadano: {caso.ciudadano_titular.nombre_completo}
- DNI: {caso.ciudadano_titular.dni}
- Municipio: {caso.municipio}
- Localidad: {caso.localidad}
- Dirección: {caso.direccion}
- Prioridad: {caso.get_prioridad_display()}

Fecha límite: {fecha_limite_obj.strftime("%d/%m/%Y")}"""

        tarea_relevamiento = TareaNachec.objects.filter(
            caso=caso,
            tipo=TipoTarea.RELEVAMIENTO,
            estado__in=[EstadoTarea.PENDIENTE, EstadoTarea.EN_PROCESO],
        ).first()
        if tarea_relevamiento:
            tarea_relevamiento.asignado_a = territorial
            tarea_relevamiento.fecha_vencimiento = fecha_limite_obj
            tarea_relevamiento.descripcion = descripcion_relevamiento
            tarea_relevamiento.save()
        else:
            tarea_relevamiento = TareaNachec.objects.create(
                caso=caso,
                tipo=TipoTarea.RELEVAMIENTO,
                titulo="Relevamiento inicial del caso",
                descripcion=descripcion_relevamiento,
                asignado_a=territorial,
                creado_por=coordinador,
                estado=EstadoTarea.PENDIENTE,
                prioridad=caso.prioridad,
                fecha_vencimiento=fecha_limite_obj,
            )

        sla_cumplido = timezone.now().date() <= (caso.sla_revision or timezone.now().date())
        HistorialEstadoCaso.objects.create(
            caso=caso,
            estado_anterior=estado_anterior,
            estado_nuevo=caso.estado,
            usuario=coordinador,
            observacion=f"""Territorial asignado: {territorial.get_full_name()}
SLA relevamiento: {fecha_limite_obj.strftime("%d/%m/%Y")}
SLA asignación cumplido: {"Sí" if sla_cumplido else "No"}
Instrucciones: {instrucciones[:100]}...""",
        )

        return {
            "caso": caso,
            "tarea_relevamiento": tarea_relevamiento,
            "sla_cumplido": sla_cumplido,
        }

    @classmethod
    def get_territoriales_con_carga(cls):
        from django.contrib.auth import get_user_model

        user_model = get_user_model()
        return (
            user_model.objects.filter(is_active=True)
            .annotate(
                casos_activos=Count(
                    "casos_nachec_territorial",
                    filter=Q(casos_nachec_territorial__estado__in=cls.ESTADOS_CASOS_ACTIVOS),
                )
            )
            .order_by("first_name", "last_name", "username")
        )

    @classmethod
    def build_reasignacion_context(cls, caso):
        return {
            "territoriales": cls.get_territoriales_con_carga(),
            "territorial_actual": caso.territorial,
        }

    @classmethod
    @transaction.atomic
    def reasignar_territorial(cls, caso, usuario, territorial, motivo):
        motivo_limpio = (motivo or "").strip()
        if not territorial:
            raise ValidationError("Debe seleccionar un territorial")
        if len(motivo_limpio) < 10:
            raise ValidationError("El motivo debe tener al menos 10 caracteres")

        territorial_anterior = caso.territorial
        caso.territorial = territorial
        caso.save(update_fields=["territorial", "modificado"])

        TareaNachec.objects.filter(
            caso=caso,
            asignado_a=territorial_anterior,
            estado__in=[EstadoTarea.PENDIENTE, EstadoTarea.EN_PROCESO],
        ).update(asignado_a=territorial)

        HistorialEstadoCaso.objects.create(
            caso=caso,
            estado_anterior=caso.estado,
            estado_nuevo=caso.estado,
            usuario=usuario,
            observacion=(
                "Reasignación por superadmin\n"
                f"De: {territorial_anterior.get_full_name() if territorial_anterior else 'Sin asignar'}\n"
                f"A: {territorial.get_full_name()}\n"
                f"Motivo: {motivo_limpio}"
            ),
        )
        return caso

    @classmethod
    def build_inicio_relevamiento_context(cls, caso):
        if caso.sla_relevamiento:
            dias_restantes = (caso.sla_relevamiento - timezone.now().date()).days
            if dias_restantes < 0:
                return {"sla_texto": f"Vencido hace {abs(dias_restantes)} días", "sla_vencido": True}
            if dias_restantes == 0:
                return {"sla_texto": "Vence hoy", "sla_vencido": False}
            return {"sla_texto": f"Vence en {dias_restantes} días", "sla_vencido": False}
        return {"sla_texto": "No definido", "sla_vencido": False}

    @classmethod
    @transaction.atomic
    def iniciar_relevamiento(cls, caso, territorial):
        if caso.estado != EstadoCaso.ASIGNADO:
            raise ValidationError("El caso no está en estado ASIGNADO")
        if caso.territorial_id != territorial.id:
            raise ValidationError("Solo el territorial asignado puede iniciar el relevamiento")

        tarea_relevamiento = TareaNachec.objects.filter(
            caso=caso,
            tipo=TipoTarea.RELEVAMIENTO,
            estado__in=[EstadoTarea.PENDIENTE, EstadoTarea.EN_PROCESO],
        ).first()
        if not tarea_relevamiento:
            raise ValidationError("No existe tarea de relevamiento para este caso. Contactar coordinación.")

        sla_vencido = bool(caso.sla_relevamiento and timezone.now().date() > caso.sla_relevamiento)
        estado_anterior = caso.estado
        caso.estado = EstadoCaso.EN_RELEVAMIENTO
        caso.fecha_inicio_relevamiento = timezone.now()
        caso.save(update_fields=["estado", "fecha_inicio_relevamiento", "modificado"])

        if tarea_relevamiento.estado == EstadoTarea.PENDIENTE:
            tarea_relevamiento.estado = EstadoTarea.EN_PROCESO
            tarea_relevamiento.save(update_fields=["estado", "modificado"])

        HistorialEstadoCaso.objects.create(
            caso=caso,
            estado_anterior=estado_anterior,
            estado_nuevo=caso.estado,
            usuario=territorial,
            observacion=(
                f"Relevamiento iniciado por {territorial.get_full_name()}\n"
                f"SLA relevamiento: {caso.sla_relevamiento.strftime('%d/%m/%Y') if caso.sla_relevamiento else 'No definido'}\n"
                f"Inicio fuera de SLA: {'Sí' if sla_vencido else 'No'}\n"
                f"Tarea ID: {tarea_relevamiento.id}\n"
                f"Prioridad: {caso.get_prioridad_display()}\n"
                f"Municipio: {caso.municipio}"
            ),
        )
        return {"caso": caso, "tarea": tarea_relevamiento, "sla_vencido": sla_vencido}
