from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from ..models.nachec import HistorialEstadoCaso, TareaNachec


@login_required
def iniciar_prestacion(request, prestacion_id):
    """PROGRAMADA → EN_PROCESO"""
    from django.http import HttpResponseForbidden
    from ..models.nachec import PrestacionNachec

    prestacion = get_object_or_404(PrestacionNachec, id=prestacion_id)

    if request.user.id != prestacion.responsable_id:
        messages.error(request, 'Solo el responsable puede iniciar esta prestación')
        return HttpResponseForbidden('Acceso denegado')

    if prestacion.estado != 'PROGRAMADA':
        messages.error(request, 'La prestación no está en estado PROGRAMADA')
        return redirect('legajos:programa_detalle', pk=2)

    if request.method == 'POST':
        from django.db import transaction
        from django.utils import timezone

        with transaction.atomic():
            prestacion.estado = 'EN_PROCESO'
            prestacion.save()

            tarea = TareaNachec.objects.filter(
                prestacion=prestacion,
                tipo='ENTREGA',
                estado__in=['PENDIENTE', 'EN_PROCESO']
            ).first()

            if tarea and tarea.estado == 'PENDIENTE':
                tarea.estado = 'EN_PROCESO'
                tarea.save()

            HistorialEstadoCaso.objects.create(
                caso=prestacion.caso,
                estado_anterior=prestacion.caso.estado,
                estado_nuevo=prestacion.caso.estado,
                usuario=request.user,
                observacion=f"""Prestación iniciada: {prestacion.get_tipo_display()}
Responsable: {request.user.get_full_name()}
SLA: {prestacion.sla_hasta.strftime('%d/%m/%Y %H:%M') if prestacion.sla_hasta else 'No definido'}
Fecha programada: {prestacion.fecha_programada.strftime('%d/%m/%Y') if prestacion.fecha_programada else 'No definida'}"""
            )

        messages.success(request, f'Prestación {prestacion.get_tipo_display()} iniciada')
        return redirect('legajos:programa_detalle', pk=2)

    return redirect('legajos:programa_detalle', pk=2)


@login_required
def confirmar_entrega_prestacion(request, prestacion_id):
    """EN_PROCESO → ENTREGADA con generación de próxima si frecuencia != UNICA"""
    from django.contrib.contenttypes.models import ContentType
    from django.http import HttpResponseForbidden, JsonResponse
    from legajos.models import Adjunto
    from ..models.nachec import PrestacionNachec

    prestacion = get_object_or_404(PrestacionNachec, id=prestacion_id)

    if request.user.id != prestacion.responsable_id:
        messages.error(request, 'Solo el responsable puede confirmar esta prestación')
        return HttpResponseForbidden('Acceso denegado')

    if prestacion.estado not in ['EN_PROCESO', 'EN_CURSO']:
        messages.error(request, 'La prestación no está en proceso')
        return redirect('legajos:programa_detalle', pk=2)

    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        archivo = request.FILES.get('evidencia')
        if archivo:
            content_type = ContentType.objects.get_for_model(PrestacionNachec)
            Adjunto.objects.create(
                content_type=content_type,
                object_id=prestacion.id,
                archivo=archivo,
                etiqueta=f"Evidencia - {archivo.name}"
            )
            return JsonResponse({'success': True})
        return JsonResponse({'success': False, 'error': 'No se recibió archivo'})

    if request.method == 'GET':
        content_type = ContentType.objects.get_for_model(PrestacionNachec)
        adjuntos = Adjunto.objects.filter(content_type=content_type, object_id=prestacion.id)
        evidencia_obligatoria = prestacion.tipo == 'ALIMENTARIA' and adjuntos.count() == 0
        return render(
            request,
            'legajos/nachec/modal_confirmar_entrega.html',
            {
                'prestacion': prestacion,
                'adjuntos': adjuntos,
                'evidencia_obligatoria': evidencia_obligatoria,
            },
        )

    if request.method == 'POST':
        from dateutil.relativedelta import relativedelta
        from django.contrib.contenttypes.models import ContentType
        from django.db import transaction
        from django.utils import timezone
        from legajos.models import Adjunto

        observaciones_entrega = request.POST.get('observaciones_entrega', '').strip()
        confirmacion = request.POST.get('confirmacion')

        if not confirmacion:
            messages.error(request, 'Debe confirmar la entrega')
            return redirect('legajos:nachec_confirmar_entrega', prestacion_id=prestacion.id)

        if len(observaciones_entrega) < 10:
            messages.error(request, 'Las observaciones deben tener al menos 10 caracteres')
            return redirect('legajos:nachec_confirmar_entrega', prestacion_id=prestacion.id)

        content_type = ContentType.objects.get_for_model(PrestacionNachec)
        adjuntos = Adjunto.objects.filter(content_type=content_type, object_id=prestacion.id)

        if prestacion.tipo == 'ALIMENTARIA' and adjuntos.count() == 0:
            messages.error(request, 'Debe adjuntar evidencia para prestaciones de tipo ALIMENTARIA')
            return redirect('legajos:nachec_confirmar_entrega', prestacion_id=prestacion.id)

        with transaction.atomic():
            prestacion.estado = 'ENTREGADA'
            prestacion.fecha_entregada = timezone.now().date()
            prestacion.observaciones = f"{prestacion.observaciones}\n\n[ENTREGA] {observaciones_entrega}"
            prestacion.save()

            tarea = TareaNachec.objects.filter(
                prestacion=prestacion,
                tipo='ENTREGA',
                estado__in=['PENDIENTE', 'EN_PROCESO']
            ).first()

            cumplio_sla = False
            if tarea:
                if prestacion.sla_hasta:
                    cumplio_sla = timezone.now() <= prestacion.sla_hasta

                tarea.estado = 'COMPLETADA'
                tarea.fecha_completada = timezone.now()
                tarea.resultado = f"""Entrega confirmada.
SLA cumplido: {'Sí' if cumplio_sla else 'No'}
Evidencias: {adjuntos.count()}
Observaciones: {observaciones_entrega}"""
                tarea.save()

            proxima_creada = False
            if prestacion.frecuencia != 'UNICA':
                if prestacion.frecuencia == 'SEMANAL':
                    fecha_proxima = prestacion.fecha_entregada + timedelta(days=7)
                elif prestacion.frecuencia == 'QUINCENAL':
                    fecha_proxima = prestacion.fecha_entregada + timedelta(days=14)
                elif prestacion.frecuencia == 'MENSUAL':
                    try:
                        fecha_proxima = prestacion.fecha_entregada + relativedelta(months=1)
                    except Exception:
                        fecha_proxima = prestacion.fecha_entregada + timedelta(days=30)
                else:
                    fecha_proxima = None

                if fecha_proxima:
                    sla_config = {
                        'ALIMENTARIA': {'URGENTE': 1, 'ALTA': 3, 'MEDIA': 7, 'BAJA': 7},
                        'VIVIENDA': {'URGENTE': 7, 'ALTA': 15, 'MEDIA': 30, 'BAJA': 30},
                        'SALUD': {'URGENTE': 3, 'ALTA': 7, 'MEDIA': 15, 'BAJA': 15},
                        'EDUCACION': {'URGENTE': 7, 'ALTA': 15, 'MEDIA': 30, 'BAJA': 30},
                        'EMPLEO': {'URGENTE': 7, 'ALTA': 15, 'MEDIA': 30, 'BAJA': 30},
                        'EMPRENDIMIENTO': {'URGENTE': 7, 'ALTA': 15, 'MEDIA': 30, 'BAJA': 30}
                    }

                    sla_dias = sla_config.get(prestacion.tipo, {}).get(prestacion.caso.prioridad or 'MEDIA', 15)
                    sla_hasta_proxima = timezone.make_aware(
                        timezone.datetime.combine(fecha_proxima, timezone.datetime.min.time())
                    ) + timedelta(days=sla_dias)

                    proxima_prestacion = PrestacionNachec.objects.create(
                        plan=prestacion.plan,
                        caso=prestacion.caso,
                        tipo=prestacion.tipo,
                        descripcion=prestacion.descripcion,
                        estado='PROGRAMADA',
                        frecuencia=prestacion.frecuencia,
                        fecha_programada=fecha_proxima,
                        sla_hasta=sla_hasta_proxima,
                        responsable=prestacion.responsable,
                        observaciones=f"Generada automáticamente por frecuencia {prestacion.frecuencia}"
                    )

                    TareaNachec.objects.create(
                        caso=prestacion.caso,
                        prestacion=proxima_prestacion,
                        tipo='ENTREGA',
                        titulo=f"Ejecutar prestación: {prestacion.tipo}",
                        descripcion=f"""Prestación programada para {prestacion.caso.ciudadano_titular.nombre_completo}

Tipo: {prestacion.tipo}
Frecuencia: {prestacion.frecuencia}
Fecha programada: {fecha_proxima.strftime('%d/%m/%Y')}

Generada automáticamente por frecuencia.""",
                        asignado_a=prestacion.responsable,
                        creado_por=request.user,
                        estado='PENDIENTE',
                        prioridad=prestacion.caso.prioridad or 'MEDIA',
                        fecha_vencimiento=sla_hasta_proxima.date()
                    )

                    proxima_creada = True

                    HistorialEstadoCaso.objects.create(
                        caso=prestacion.caso,
                        estado_anterior=prestacion.caso.estado,
                        estado_nuevo=prestacion.caso.estado,
                        usuario=request.user,
                        observacion=f"""Prestación regenerada: {prestacion.get_tipo_display()}
Frecuencia: {prestacion.frecuencia}
Próxima fecha: {fecha_proxima.strftime('%d/%m/%Y')}
SLA próxima: {sla_hasta_proxima.strftime('%d/%m/%Y')}"""
                    )

            HistorialEstadoCaso.objects.create(
                caso=prestacion.caso,
                estado_anterior=prestacion.caso.estado,
                estado_nuevo=prestacion.caso.estado,
                usuario=request.user,
                observacion=f"""Prestación entregada: {prestacion.get_tipo_display()}
SLA cumplido: {'Sí' if cumplio_sla else 'No'}
Fecha entrega: {prestacion.fecha_entregada.strftime('%d/%m/%Y')}
Evidencias: {adjuntos.count()}
Próxima generada: {'Sí' if proxima_creada else 'No'}
Observaciones: {observaciones_entrega[:100]}..."""
            )

            resultado = prestacion.caso.recalcular_estado_por_prestaciones()
            if resultado.get('cambio'):
                motivo = 'sin_prestaciones_activas' if resultado['estado_nuevo'] == 'EN_SEGUIMIENTO' else 'prestacion_activa_detectada'
                HistorialEstadoCaso.objects.create(
                    caso=prestacion.caso,
                    estado_anterior=resultado['estado_anterior'],
                    estado_nuevo=resultado['estado_nuevo'],
                    usuario=request.user,
                    observacion=f"""Transición automática por prestaciones
Motivo: {motivo}
Prestaciones activas: {resultado['prestaciones_activas']}"""
                )

                if resultado['estado_nuevo'] == 'EN_SEGUIMIENTO':
                    tarea_cierre_existente = TareaNachec.objects.filter(
                        caso=prestacion.caso,
                        tipo='OTRO',
                        titulo__icontains='Cerrar caso',
                        estado__in=['PENDIENTE', 'EN_PROCESO']
                    ).first()

                    if not tarea_cierre_existente:
                        sla_dias = {'URGENTE': 1, 'ALTA': 1, 'MEDIA': 2, 'BAJA': 3}.get(prestacion.caso.prioridad or 'MEDIA', 2)
                        TareaNachec.objects.create(
                            caso=prestacion.caso,
                            tipo='OTRO',
                            titulo='Cerrar caso - Sin prestaciones activas',
                            descripcion=f"""El caso pasó a EN_SEGUIMIENTO porque no quedan prestaciones activas.

Debe evaluar cierre del caso.

Plan vigente: {prestacion.plan.id}
Última prestación entregada: {prestacion.get_tipo_display()} - {prestacion.fecha_entregada.strftime('%d/%m/%Y')}""",
                            asignado_a=prestacion.caso.coordinador or request.user,
                            creado_por=request.user,
                            estado='PENDIENTE',
                            prioridad=prestacion.caso.prioridad or 'MEDIA',
                            fecha_vencimiento=(timezone.now() + timedelta(days=sla_dias)).date()
                        )

        msg = f'Prestación {prestacion.get_tipo_display()} confirmada como entregada'
        if proxima_creada:
            msg += f'. Próxima prestación programada para {fecha_proxima.strftime("%d/%m/%Y")}'
        messages.success(request, msg)
        return redirect('legajos:programa_detalle', pk=2)


@login_required
def reprogramar_prestacion(request, prestacion_id):
    """Reprogramar fecha y recalcular SLA"""
    from django.http import HttpResponseForbidden
    from ..models.nachec import PrestacionNachec

    prestacion = get_object_or_404(PrestacionNachec, id=prestacion_id)

    if request.user.id != prestacion.responsable_id:
        messages.error(request, 'Solo el responsable puede reprogramar esta prestación')
        return HttpResponseForbidden('Acceso denegado')

    if prestacion.estado not in ['PROGRAMADA', 'EN_PROCESO', 'EN_CURSO']:
        messages.error(request, 'La prestación no puede ser reprogramada en su estado actual')
        return redirect('legajos:programa_detalle', pk=2)

    if request.method == 'GET':
        from django.utils import timezone
        return render(
            request,
            'legajos/nachec/modal_reprogramar_prestacion.html',
            {
                'prestacion': prestacion,
                'fecha_minima': timezone.now().date().strftime('%Y-%m-%d'),
            },
        )

    if request.method == 'POST':
        from datetime import datetime
        from django.db import transaction
        from django.utils import timezone

        nueva_fecha = request.POST.get('nueva_fecha')
        motivo = request.POST.get('motivo')
        detalle = request.POST.get('detalle', '').strip()

        if not nueva_fecha:
            messages.error(request, 'Debe especificar nueva fecha')
            return redirect('legajos:nachec_reprogramar_prestacion', prestacion_id=prestacion.id)

        if len(detalle) < 10:
            messages.error(request, 'El detalle debe tener al menos 10 caracteres')
            return redirect('legajos:nachec_reprogramar_prestacion', prestacion_id=prestacion.id)

        try:
            fecha_obj = datetime.strptime(nueva_fecha, '%Y-%m-%d').date()
            if fecha_obj < timezone.now().date():
                messages.error(request, 'La fecha no puede ser anterior a hoy')
                return redirect('legajos:nachec_reprogramar_prestacion', prestacion_id=prestacion.id)
        except ValueError:
            messages.error(request, 'Formato de fecha inválido')
            return redirect('legajos:nachec_reprogramar_prestacion', prestacion_id=prestacion.id)

        with transaction.atomic():
            fecha_anterior = prestacion.fecha_programada
            prestacion.fecha_programada = fecha_obj

            sla_config = {
                'ALIMENTARIA': {'URGENTE': 1, 'ALTA': 3, 'MEDIA': 7, 'BAJA': 7},
                'VIVIENDA': {'URGENTE': 7, 'ALTA': 15, 'MEDIA': 30, 'BAJA': 30},
                'SALUD': {'URGENTE': 3, 'ALTA': 7, 'MEDIA': 15, 'BAJA': 15},
                'EDUCACION': {'URGENTE': 7, 'ALTA': 15, 'MEDIA': 30, 'BAJA': 30},
                'EMPLEO': {'URGENTE': 7, 'ALTA': 15, 'MEDIA': 30, 'BAJA': 30},
                'EMPRENDIMIENTO': {'URGENTE': 7, 'ALTA': 15, 'MEDIA': 30, 'BAJA': 30}
            }

            sla_dias = sla_config.get(prestacion.tipo, {}).get(prestacion.caso.prioridad or 'MEDIA', 15)
            prestacion.sla_hasta = timezone.make_aware(
                timezone.datetime.combine(fecha_obj, timezone.datetime.min.time())
            ) + timedelta(days=sla_dias)

            prestacion.observaciones = f"{prestacion.observaciones}\n\n[REPROGRAMACIÓN] {motivo}: {detalle}"
            prestacion.save()

            tarea = TareaNachec.objects.filter(
                prestacion=prestacion,
                tipo='ENTREGA',
                estado__in=['PENDIENTE', 'EN_PROCESO']
            ).first()

            if tarea:
                tarea.fecha_vencimiento = prestacion.sla_hasta.date()
                tarea.save()

            HistorialEstadoCaso.objects.create(
                caso=prestacion.caso,
                estado_anterior=prestacion.caso.estado,
                estado_nuevo=prestacion.caso.estado,
                usuario=request.user,
                observacion=f"""Prestación reprogramada: {prestacion.get_tipo_display()}
Fecha anterior: {fecha_anterior.strftime('%d/%m/%Y') if fecha_anterior else 'No definida'}
Nueva fecha: {fecha_obj.strftime('%d/%m/%Y')}
Nuevo SLA: {prestacion.sla_hasta.strftime('%d/%m/%Y %H:%M')}
Motivo: {motivo}
Detalle: {detalle}"""
            )

        messages.success(request, f'Prestación reprogramada para {fecha_obj.strftime("%d/%m/%Y")}')
        return redirect('legajos:programa_detalle', pk=2)


@login_required
def cancelar_prestacion(request, prestacion_id):
    """Cancelar prestación y tarea asociada"""
    from django.http import HttpResponseForbidden
    from ..models.nachec import PrestacionNachec

    prestacion = get_object_or_404(PrestacionNachec, id=prestacion_id)

    if request.user.id != prestacion.responsable_id:
        messages.error(request, 'Solo el responsable puede cancelar esta prestación')
        return HttpResponseForbidden('Acceso denegado')

    if prestacion.estado in ['ENTREGADA', 'COMPLETADA']:
        messages.error(request, 'No se puede cancelar una prestación ya entregada')
        return redirect('legajos:programa_detalle', pk=2)

    if request.method == 'GET':
        return render(
            request,
            'legajos/nachec/modal_cancelar_prestacion.html',
            {'prestacion': prestacion},
        )

    if request.method == 'POST':
        from django.db import transaction
        from django.utils import timezone

        motivo = request.POST.get('motivo')
        detalle = request.POST.get('detalle', '').strip()

        if len(detalle) < 10:
            messages.error(request, 'El detalle debe tener al menos 10 caracteres')
            return redirect('legajos:nachec_cancelar_prestacion', prestacion_id=prestacion.id)

        with transaction.atomic():
            prestacion.estado = 'CANCELADA'
            prestacion.observaciones = f"{prestacion.observaciones}\n\n[CANCELACIÓN] {motivo}: {detalle}"
            prestacion.save()

            tarea = TareaNachec.objects.filter(
                prestacion=prestacion,
                tipo='ENTREGA',
                estado__in=['PENDIENTE', 'EN_PROCESO']
            ).first()

            if tarea:
                tarea.estado = 'CANCELADA'
                tarea.resultado = f"Cancelada: {motivo} - {detalle}"
                tarea.save()

            HistorialEstadoCaso.objects.create(
                caso=prestacion.caso,
                estado_anterior=prestacion.caso.estado,
                estado_nuevo=prestacion.caso.estado,
                usuario=request.user,
                observacion=f"""Prestación cancelada: {prestacion.get_tipo_display()}
Motivo: {motivo}
Detalle: {detalle}"""
            )

            resultado = prestacion.caso.recalcular_estado_por_prestaciones()
            if resultado.get('cambio'):
                motivo_cambio = 'sin_prestaciones_activas' if resultado['estado_nuevo'] == 'EN_SEGUIMIENTO' else 'prestacion_activa_detectada'
                HistorialEstadoCaso.objects.create(
                    caso=prestacion.caso,
                    estado_anterior=resultado['estado_anterior'],
                    estado_nuevo=resultado['estado_nuevo'],
                    usuario=request.user,
                    observacion=f"""Transición automática por prestaciones
Motivo: {motivo_cambio}
Prestaciones activas: {resultado['prestaciones_activas']}"""
                )

                if resultado['estado_nuevo'] == 'EN_SEGUIMIENTO':
                    tarea_cierre_existente = TareaNachec.objects.filter(
                        caso=prestacion.caso,
                        tipo='OTRO',
                        titulo__icontains='Cerrar caso',
                        estado__in=['PENDIENTE', 'EN_PROCESO']
                    ).first()

                    if not tarea_cierre_existente:
                        sla_dias = {'URGENTE': 1, 'ALTA': 1, 'MEDIA': 2, 'BAJA': 3}.get(prestacion.caso.prioridad or 'MEDIA', 2)
                        TareaNachec.objects.create(
                            caso=prestacion.caso,
                            tipo='OTRO',
                            titulo='Cerrar caso - Sin prestaciones activas',
                            descripcion=f"""El caso pasó a EN_SEGUIMIENTO porque no quedan prestaciones activas.

Debe evaluar cierre del caso.

Plan vigente: {prestacion.plan.id}
Última acción: Cancelación de prestación {prestacion.get_tipo_display()}""",
                            asignado_a=prestacion.caso.coordinador or request.user,
                            creado_por=request.user,
                            estado='PENDIENTE',
                            prioridad=prestacion.caso.prioridad or 'MEDIA',
                            fecha_vencimiento=(timezone.now() + timedelta(days=sla_dias)).date()
                        )

        messages.info(request, f'Prestación {prestacion.get_tipo_display()} cancelada')
        return redirect('legajos:programa_detalle', pk=2)
