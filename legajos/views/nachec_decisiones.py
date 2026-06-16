from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from ..models.nachec import CasoNachec, HistorialEstadoCaso, RelevamientoNachec, TareaNachec


@login_required
def evaluar_caso(request, caso_id):
    """EVALUADO → PLAN_DEFINIDO con evaluación profesional"""
    from django.http import HttpResponseForbidden

    caso = get_object_or_404(CasoNachec, id=caso_id)

    if caso.estado != 'EVALUADO':
        messages.error(request, 'El caso no está en estado EVALUADO')
        return redirect('legajos:programa_detalle', pk=2)

    tarea_evaluacion = TareaNachec.objects.filter(
        caso=caso,
        tipo='OTRO',
        titulo__icontains='Evaluar caso',
        asignado_a=request.user,
        estado__in=['PENDIENTE', 'EN_PROCESO']
    ).first()

    if not tarea_evaluacion:
        messages.error(request, 'No tienes tarea de evaluación asignada para este caso')
        return HttpResponseForbidden('Acceso denegado: sin tarea asignada')

    try:
        relevamiento = RelevamientoNachec.objects.filter(caso=caso, completado=True).latest('fecha_finalizacion')
    except RelevamientoNachec.DoesNotExist:
        messages.error(request, 'No existe relevamiento finalizado para este caso')
        return redirect('legajos:programa_detalle', pk=2)

    if request.method == 'GET':
        from django.contrib.contenttypes.models import ContentType
        from legajos.models import Adjunto

        content_type = ContentType.objects.get_for_model(RelevamientoNachec)
        adjuntos = Adjunto.objects.filter(content_type=content_type, object_id=relevamiento.id)

        return render(
            request,
            'legajos/nachec/modal_evaluar_caso.html',
            {
                'caso': caso,
                'relevamiento': relevamiento,
                'adjuntos': adjuntos,
                'tarea': tarea_evaluacion,
            },
        )

    if request.method == 'POST':
        accion = request.POST.get('accion')
        caso.refresh_from_db()
        if caso.estado != 'EVALUADO':
            messages.error(request, 'El caso ya fue procesado por otro usuario')
            return redirect('legajos:programa_detalle', pk=2)

        if accion == 'confirmar':
            return _confirmar_evaluacion(request, caso, relevamiento, tarea_evaluacion)
        if accion == 'ampliacion':
            return _solicitar_ampliacion(request, caso, tarea_evaluacion)
        if accion == 'rechazar':
            return _rechazar_caso(request, caso, tarea_evaluacion)
        messages.error(request, 'Acción inválida')
        return redirect('legajos:nachec_evaluar_caso', caso_id=caso.id)


def _confirmar_evaluacion(request, caso, relevamiento, tarea_evaluacion):
    """Confirmar evaluación y crear plan"""
    from django.db import transaction
    from django.utils import timezone

    from ..models.nachec import EvaluacionVulnerabilidad, PlanIntervencionNachec

    dictamen = request.POST.get('dictamen', '').strip()
    categoria_final = request.POST.get('categoria_final')
    componentes = request.POST.getlist('componentes')

    if len(dictamen) < 20:
        messages.error(request, 'El dictamen debe tener al menos 20 caracteres')
        return redirect('legajos:nachec_evaluar_caso', caso_id=caso.id)
    if not categoria_final:
        messages.error(request, 'Debe seleccionar una categoría final')
        return redirect('legajos:nachec_evaluar_caso', caso_id=caso.id)
    if not componentes:
        messages.error(request, 'Debe seleccionar al menos un componente del plan')
        return redirect('legajos:nachec_evaluar_caso', caso_id=caso.id)

    override = categoria_final != relevamiento.score_categoria
    justificacion_override = request.POST.get('justificacion_override', '').strip()
    if override and len(justificacion_override) < 20:
        messages.error(request, 'Debe justificar el cambio de categoría (min 20 caracteres)')
        return redirect('legajos:nachec_evaluar_caso', caso_id=caso.id)

    with transaction.atomic():
        evaluacion_existente = EvaluacionVulnerabilidad.objects.filter(caso=caso).first()
        if evaluacion_existente:
            messages.warning(request, 'Este caso ya fue evaluado')
            return redirect('legajos:programa_detalle', pk=2)

        EvaluacionVulnerabilidad.objects.create(
            caso=caso,
            relevamiento=relevamiento,
            evaluador=request.user,
            score_total=relevamiento.score_total,
            score_version=relevamiento.score_version,
            categoria_sugerida=relevamiento.score_categoria,
            dictamen=dictamen,
            categoria_final=categoria_final,
            override_categoria=override,
            justificacion_override=justificacion_override if override else '',
        )

        PlanIntervencionNachec.objects.filter(caso=caso, vigente=True).update(vigente=False)
        PlanIntervencionNachec.objects.create(
            caso=caso,
            referente=request.user,
            objetivo_general=f"Plan de intervención para caso con vulnerabilidad {categoria_final}",
            fecha_inicio=timezone.now().date(),
            horizonte_dias=90,
            incluye_alimentacion='ALIMENTARIA' in componentes,
            incluye_vivienda='VIVIENDA' in componentes,
            incluye_empleo='EMPLEO' in componentes,
            incluye_salud='SALUD' in componentes,
            incluye_educacion='EDUCACION' in componentes,
            incluye_emprendimiento='EMPRENDIMIENTO' in componentes,
            vigente=False,
            observaciones=f"Componentes: {', '.join(componentes)}",
        )

        estado_anterior = caso.estado
        caso.estado = 'PLAN_DEFINIDO'
        caso.fecha_evaluacion = timezone.now().date()
        if not caso.coordinador:
            caso.coordinador = request.user
        caso.save()

        tarea_evaluacion.estado = 'COMPLETADA'
        tarea_evaluacion.fecha_completada = timezone.now()
        tarea_evaluacion.resultado = f"Evaluado. Categoría: {categoria_final}. Plan definido con {len(componentes)} componentes."
        tarea_evaluacion.save()

        tarea_activacion_existente = TareaNachec.objects.filter(
            caso=caso,
            tipo='OTRO',
            titulo__icontains='Activar plan',
            estado__in=['PENDIENTE', 'EN_PROCESO']
        ).first()

        if not tarea_activacion_existente:
            sla_dias = {'URGENTE': 1, 'ALTA': 1, 'MEDIA': 2, 'BAJA': 3}.get(caso.prioridad or 'MEDIA', 2)
            TareaNachec.objects.create(
                caso=caso,
                tipo='OTRO',
                titulo='Activar plan de intervención',
                descripcion=f"""Plan definido. Debe activar y programar prestaciones.

Categoría final: {categoria_final}
Componentes: {', '.join(componentes)}

Dictamen:
{dictamen}

Score: {relevamiento.score_total} ({relevamiento.score_categoria} → {categoria_final})
Override: {'Sí - ' + justificacion_override if override else 'No'}""",
                asignado_a=caso.coordinador or request.user,
                creado_por=request.user,
                estado='PENDIENTE',
                prioridad=caso.prioridad or 'MEDIA',
                fecha_vencimiento=(timezone.now() + timedelta(days=sla_dias)).date(),
            )

        HistorialEstadoCaso.objects.create(
            caso=caso,
            estado_anterior=estado_anterior,
            estado_nuevo=caso.estado,
            usuario=request.user,
            observacion=f"""Evaluación completada por {request.user.get_full_name()}
Categoría: {relevamiento.score_categoria} → {categoria_final}
Override: {'Sí' if override else 'No'}
{'Justificación: ' + justificacion_override if override else ''}
Componentes: {', '.join(componentes)}
Score: {relevamiento.score_total} [v{relevamiento.score_version}]
Dictamen: {dictamen[:100]}..."""
        )

    messages.success(request, f'Evaluación completada. Plan definido con categoría {categoria_final}.')
    return redirect('legajos:programa_detalle', pk=2)


def _solicitar_ampliacion(request, caso, tarea_evaluacion):
    """Solicitar ampliación de relevamiento"""
    from django.db import transaction
    from django.utils import timezone

    motivo = request.POST.get('motivo_ampliacion')
    detalle = request.POST.get('detalle_ampliacion', '').strip()
    plazo_horas = int(request.POST.get('plazo_ampliacion', 48))

    if len(detalle) < 20:
        messages.error(request, 'El detalle de ampliación debe tener al menos 20 caracteres')
        return redirect('legajos:nachec_evaluar_caso', caso_id=caso.id)

    with transaction.atomic():
        estado_anterior = caso.estado
        caso.estado = 'EN_RELEVAMIENTO'
        caso.save()

        fecha_limite = timezone.now() + timedelta(hours=plazo_horas)
        TareaNachec.objects.create(
            caso=caso,
            tipo='AMPLIACION',
            titulo='Ampliación de relevamiento solicitada',
            descripcion=f"""Ampliación solicitada por evaluador.

Motivo: {motivo}
Detalle: {detalle}
Plazo: {plazo_horas}h

Debe completar información faltante y volver a finalizar relevamiento.""",
            asignado_a=caso.territorial,
            creado_por=request.user,
            estado='PENDIENTE',
            prioridad=caso.prioridad,
            fecha_vencimiento=fecha_limite.date(),
        )

        tarea_evaluacion.estado = 'EN_PROCESO'
        tarea_evaluacion.resultado = f"Ampliación solicitada: {motivo}"
        tarea_evaluacion.save()

        HistorialEstadoCaso.objects.create(
            caso=caso,
            estado_anterior=estado_anterior,
            estado_nuevo=caso.estado,
            usuario=request.user,
            observacion=f"""Ampliación solicitada por {request.user.get_full_name()}
Motivo: {motivo}
Plazo: {plazo_horas}h
Detalle: {detalle}"""
        )

    messages.warning(request, f'Ampliación solicitada. Caso vuelve a EN_RELEVAMIENTO con plazo de {plazo_horas}h.')
    return redirect('legajos:programa_detalle', pk=2)


def _rechazar_caso(request, caso, tarea_evaluacion):
    """Rechazar caso"""
    from django.db import transaction
    from django.utils import timezone

    motivo = request.POST.get('motivo_rechazo')
    observaciones = request.POST.get('observaciones_rechazo', '').strip()

    if len(observaciones) < 20:
        messages.error(request, 'Las observaciones de rechazo deben tener al menos 20 caracteres')
        return redirect('legajos:nachec_evaluar_caso', caso_id=caso.id)

    with transaction.atomic():
        estado_anterior = caso.estado
        caso.estado = 'RECHAZADO'
        caso.motivo_rechazo = f"{motivo}: {observaciones}"
        caso.fecha_cierre = timezone.now().date()
        caso.save()

        tarea_evaluacion.estado = 'COMPLETADA'
        tarea_evaluacion.fecha_completada = timezone.now()
        tarea_evaluacion.resultado = f"Caso rechazado: {motivo}"
        tarea_evaluacion.save()

        TareaNachec.objects.filter(
            caso=caso,
            estado__in=['PENDIENTE', 'EN_PROCESO']
        ).exclude(id=tarea_evaluacion.id).update(
            estado='CANCELADA',
            resultado=f"Cancelada por rechazo del caso: {motivo}"
        )

        HistorialEstadoCaso.objects.create(
            caso=caso,
            estado_anterior=estado_anterior,
            estado_nuevo=caso.estado,
            usuario=request.user,
            observacion=f"""Caso rechazado por {request.user.get_full_name()}
Motivo: {motivo}
Observaciones: {observaciones}"""
        )

    messages.info(request, f'Caso rechazado: {motivo}')
    return redirect('legajos:programa_detalle', pk=2)


@login_required
def activar_plan(request, caso_id):
    """PLAN_DEFINIDO → EN_EJECUCION con programación de prestaciones"""
    from django.contrib.auth.models import User
    from django.http import HttpResponseForbidden
    from django.db import transaction
    from django.utils import timezone

    from ..models.nachec import PlanIntervencionNachec, PrestacionNachec

    caso = get_object_or_404(CasoNachec, id=caso_id)

    if caso.estado != 'PLAN_DEFINIDO':
        messages.error(request, 'El caso no tiene plan definido')
        return redirect('legajos:programa_detalle', pk=2)

    tarea_activacion = TareaNachec.objects.filter(
        caso=caso,
        tipo='OTRO',
        titulo__icontains='Activar plan',
        asignado_a=request.user,
        estado__in=['PENDIENTE', 'EN_PROCESO']
    ).first()

    if not tarea_activacion:
        messages.error(request, 'No tienes tarea de activación asignada para este caso')
        return HttpResponseForbidden('Acceso denegado: sin tarea asignada')

    plan = PlanIntervencionNachec.objects.filter(caso=caso).order_by('-creado').first()
    if not plan:
        messages.error(request, 'No existe plan para este caso')
        return redirect('legajos:programa_detalle', pk=2)

    if plan.vigente or plan.fecha_activacion:
        messages.warning(request, 'El plan ya fue activado')
        return redirect('legajos:programa_detalle', pk=2)

    if request.method == 'GET':
        evaluacion = caso.evaluacion if hasattr(caso, 'evaluacion') else None
        componentes = []
        if plan.incluye_alimentacion:
            componentes.append({'codigo': 'ALIMENTARIA', 'nombre': 'Alimentación', 'icono': 'utensils', 'color': 'orange'})
        if plan.incluye_vivienda:
            componentes.append({'codigo': 'VIVIENDA', 'nombre': 'Vivienda', 'icono': 'home', 'color': 'blue'})
        if plan.incluye_salud:
            componentes.append({'codigo': 'SALUD', 'nombre': 'Salud', 'icono': 'heartbeat', 'color': 'red'})
        if plan.incluye_educacion:
            componentes.append({'codigo': 'EDUCACION', 'nombre': 'Educación', 'icono': 'graduation-cap', 'color': 'purple'})
        if plan.incluye_empleo:
            componentes.append({'codigo': 'EMPLEO', 'nombre': 'Empleo/Capacitación', 'icono': 'briefcase', 'color': 'green'})
        if plan.incluye_emprendimiento:
            componentes.append({'codigo': 'EMPRENDIMIENTO', 'nombre': 'Emprendimiento', 'icono': 'lightbulb', 'color': 'yellow'})

        usuarios = User.objects.filter(is_active=True).order_by('first_name', 'last_name')
        return render(
            request,
            'legajos/nachec/modal_activar_plan.html',
            {
                'caso': caso,
                'plan': plan,
                'evaluacion': evaluacion,
                'componentes': componentes,
                'usuarios': usuarios,
                'tarea': tarea_activacion,
            },
        )

    if request.method == 'POST':
        caso.refresh_from_db()
        plan.refresh_from_db()

        if caso.estado != 'PLAN_DEFINIDO':
            messages.error(request, 'El caso ya fue procesado por otro usuario')
            return redirect('legajos:programa_detalle', pk=2)
        if plan.vigente or plan.fecha_activacion:
            messages.warning(request, 'El plan ya fue activado')
            return redirect('legajos:programa_detalle', pk=2)

        confirmacion = request.POST.get('confirmacion')
        if not confirmacion:
            messages.error(request, 'Debe confirmar la activación del plan')
            return redirect('legajos:nachec_activar_plan', caso_id=caso.id)

        componentes_data = []
        componentes_activos = []
        if plan.incluye_alimentacion:
            componentes_activos.append('ALIMENTARIA')
        if plan.incluye_vivienda:
            componentes_activos.append('VIVIENDA')
        if plan.incluye_salud:
            componentes_activos.append('SALUD')
        if plan.incluye_educacion:
            componentes_activos.append('EDUCACION')
        if plan.incluye_empleo:
            componentes_activos.append('EMPLEO')
        if plan.incluye_emprendimiento:
            componentes_activos.append('EMPRENDIMIENTO')

        for comp in componentes_activos:
            responsable_id = request.POST.get(f'responsable_{comp}')
            fecha_inicio = request.POST.get(f'fecha_inicio_{comp}')
            frecuencia = request.POST.get(f'frecuencia_{comp}', 'UNICA')
            observaciones = request.POST.get(f'observaciones_{comp}', '')

            if not responsable_id:
                messages.error(request, f'Debe asignar responsable para {comp}')
                return redirect('legajos:nachec_activar_plan', caso_id=caso.id)
            if not fecha_inicio:
                messages.error(request, f'Debe especificar fecha de inicio para {comp}')
                return redirect('legajos:nachec_activar_plan', caso_id=caso.id)

            from datetime import datetime
            try:
                fecha_obj = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
                if fecha_obj < timezone.now().date():
                    messages.error(request, f'La fecha de inicio para {comp} no puede ser anterior a hoy')
                    return redirect('legajos:nachec_activar_plan', caso_id=caso.id)
            except ValueError:
                messages.error(request, f'Formato de fecha inválido para {comp}')
                return redirect('legajos:nachec_activar_plan', caso_id=caso.id)

            try:
                responsable = User.objects.get(id=responsable_id, is_active=True)
            except User.DoesNotExist:
                messages.error(request, f'Responsable inválido para {comp}')
                return redirect('legajos:nachec_activar_plan', caso_id=caso.id)

            componentes_data.append(
                {
                    'tipo': comp,
                    'responsable': responsable,
                    'fecha_inicio': fecha_obj,
                    'frecuencia': frecuencia,
                    'observaciones': observaciones,
                }
            )

        with transaction.atomic():
            PlanIntervencionNachec.objects.filter(caso=caso, vigente=True).exclude(id=plan.id).update(vigente=False)
            plan.vigente = True
            plan.fecha_activacion = timezone.now()
            plan.save()

            prestaciones_creadas = 0
            tareas_creadas = 0
            sla_config = {
                'ALIMENTARIA': {'URGENTE': 1, 'ALTA': 3, 'MEDIA': 7, 'BAJA': 7},
                'VIVIENDA': {'URGENTE': 7, 'ALTA': 15, 'MEDIA': 30, 'BAJA': 30},
                'SALUD': {'URGENTE': 3, 'ALTA': 7, 'MEDIA': 15, 'BAJA': 15},
                'EDUCACION': {'URGENTE': 7, 'ALTA': 15, 'MEDIA': 30, 'BAJA': 30},
                'EMPLEO': {'URGENTE': 7, 'ALTA': 15, 'MEDIA': 30, 'BAJA': 30},
                'EMPRENDIMIENTO': {'URGENTE': 7, 'ALTA': 15, 'MEDIA': 30, 'BAJA': 30},
            }

            for comp_data in componentes_data:
                sla_dias = sla_config.get(comp_data['tipo'], {}).get(caso.prioridad or 'MEDIA', 15)
                sla_hasta = timezone.now() + timedelta(days=sla_dias)

                prestacion_existente = PrestacionNachec.objects.filter(
                    plan=plan,
                    caso=caso,
                    tipo=comp_data['tipo'],
                    estado__in=['CREADA', 'PROGRAMADA', 'EN_PROCESO', 'EN_CURSO']
                ).first()

                if prestacion_existente:
                    prestacion_existente.responsable = comp_data['responsable']
                    prestacion_existente.fecha_programada = comp_data['fecha_inicio']
                    prestacion_existente.frecuencia = comp_data['frecuencia']
                    prestacion_existente.sla_hasta = sla_hasta
                    prestacion_existente.observaciones = comp_data['observaciones']
                    prestacion_existente.save()
                    prestacion = prestacion_existente
                else:
                    prestacion = PrestacionNachec.objects.create(
                        plan=plan,
                        caso=caso,
                        tipo=comp_data['tipo'],
                        descripcion=f"Prestación de {comp_data['tipo'].lower()} - {caso.ciudadano_titular.nombre_completo}",
                        estado='PROGRAMADA',
                        frecuencia=comp_data['frecuencia'],
                        fecha_programada=comp_data['fecha_inicio'],
                        sla_hasta=sla_hasta,
                        responsable=comp_data['responsable'],
                        observaciones=comp_data['observaciones'],
                    )
                    prestaciones_creadas += 1

                tarea_existente = TareaNachec.objects.filter(
                    caso=caso,
                    prestacion=prestacion,
                    tipo='ENTREGA',
                    estado__in=['PENDIENTE', 'EN_PROCESO']
                ).first()

                if not tarea_existente:
                    TareaNachec.objects.create(
                        caso=caso,
                        prestacion=prestacion,
                        tipo='ENTREGA',
                        titulo=f"Ejecutar prestación: {comp_data['tipo']}",
                        descripcion=f"""Prestación programada para {caso.ciudadano_titular.nombre_completo}

Tipo: {comp_data['tipo']}
Frecuencia: {comp_data['frecuencia']}
Fecha programada: {comp_data['fecha_inicio'].strftime('%d/%m/%Y')}

Observaciones:
{comp_data['observaciones']}""",
                        asignado_a=comp_data['responsable'],
                        creado_por=request.user,
                        estado='PENDIENTE',
                        prioridad=caso.prioridad or 'MEDIA',
                        fecha_vencimiento=sla_hasta.date(),
                    )
                    tareas_creadas += 1

            if prestaciones_creadas > 0 or PrestacionNachec.objects.filter(plan=plan).exists():
                estado_anterior = caso.estado
                caso.estado = 'EN_EJECUCION'
                caso.save()
            else:
                messages.error(request, 'No se pudieron crear prestaciones. Plan no activado.')
                return redirect('legajos:nachec_activar_plan', caso_id=caso.id)

            tarea_activacion.estado = 'COMPLETADA'
            tarea_activacion.fecha_completada = timezone.now()
            tarea_activacion.resultado = f"Plan activado. {prestaciones_creadas} prestaciones creadas, {tareas_creadas} tareas generadas."
            tarea_activacion.save()

            componentes_str = ', '.join([c['tipo'] for c in componentes_data])
            responsables_str = ', '.join([f"{c['tipo']}: {c['responsable'].get_full_name()}" for c in componentes_data])
            HistorialEstadoCaso.objects.create(
                caso=caso,
                estado_anterior=estado_anterior,
                estado_nuevo=caso.estado,
                usuario=request.user,
                observacion=f"""Plan activado por {request.user.get_full_name()}
Componentes: {componentes_str}
Responsables: {responsables_str}
Prestaciones: {prestaciones_creadas} creadas
Tareas: {tareas_creadas} generadas"""
            )

        messages.success(request, f'Plan activado exitosamente. Se crearon {prestaciones_creadas} prestaciones y {tareas_creadas} tareas de ejecución.')
        return redirect('legajos:programa_detalle', pk=2)


@login_required
def pasar_a_seguimiento(request, caso_id):
    """EN_EJECUCION → EN_SEGUIMIENTO"""
    caso = get_object_or_404(CasoNachec, id=caso_id)
    if caso.estado != 'EN_EJECUCION':
        messages.error(request, 'El caso no está en ejecución')
        return redirect('legajos:programa_detalle', pk=2)

    estado_anterior = caso.estado
    caso.estado = 'EN_SEGUIMIENTO'
    caso.save()
    HistorialEstadoCaso.objects.create(
        caso=caso,
        estado_anterior=estado_anterior,
        estado_nuevo=caso.estado,
        usuario=request.user,
    )
    messages.success(request, 'Caso en seguimiento')
    return redirect('legajos:programa_detalle', pk=2)


@login_required
def cerrar_caso(request, caso_id):
    """EN_SEGUIMIENTO → CERRADO"""
    caso = get_object_or_404(CasoNachec, id=caso_id)
    if caso.estado != 'EN_SEGUIMIENTO':
        messages.error(request, 'El caso no está en seguimiento')
        return redirect('legajos:programa_detalle', pk=2)

    estado_anterior = caso.estado
    caso.estado = 'CERRADO'
    caso.save()
    HistorialEstadoCaso.objects.create(
        caso=caso,
        estado_anterior=estado_anterior,
        estado_nuevo=caso.estado,
        usuario=request.user,
    )
    messages.success(request, 'Caso cerrado')
    return redirect('legajos:programa_detalle', pk=2)
