from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from ..models.nachec import CasoNachec, HistorialEstadoCaso, TareaNachec


@login_required
def cerrar_caso_nachec(request, caso_id):
    """EN_SEGUIMIENTO → CERRADO con validaciones y cierre de plan"""
    from django.http import HttpResponseForbidden
    from ..models.nachec import PlanIntervencionNachec, PrestacionNachec

    caso = get_object_or_404(CasoNachec, id=caso_id)

    if caso.estado != 'EN_SEGUIMIENTO':
        messages.error(request, 'El caso no está en seguimiento')
        return redirect('legajos:programa_detalle', pk=2)

    es_coordinador = request.user.id == caso.coordinador_id
    tarea_cierre = TareaNachec.objects.filter(
        caso=caso,
        tipo='OTRO',
        titulo__icontains='Cerrar caso',
        asignado_a=request.user,
        estado__in=['PENDIENTE', 'EN_PROCESO']
    ).first()

    if not es_coordinador and not tarea_cierre:
        messages.error(request, 'No tienes permiso para cerrar este caso')
        return HttpResponseForbidden('Acceso denegado: solo coordinador')

    plan_vigente = PlanIntervencionNachec.objects.filter(caso=caso, vigente=True).first()

    if request.method == 'GET':
        prestaciones_activas = PrestacionNachec.objects.filter(
            plan=plan_vigente,
            estado__in=['PROGRAMADA', 'EN_PROCESO', 'EN_CURSO']
        ).count() if plan_vigente else 0

        ultima_prestacion = PrestacionNachec.objects.filter(
            caso=caso,
            estado='ENTREGADA'
        ).order_by('-fecha_entregada').first() if plan_vigente else None

        evaluacion = caso.evaluacion if hasattr(caso, 'evaluacion') else None
        prestaciones_entregadas = PrestacionNachec.objects.filter(
            caso=caso,
            estado='ENTREGADA'
        ).count()

        return render(
            request,
            'legajos/nachec/modal_cerrar_caso.html',
            {
                'caso': caso,
                'plan': plan_vigente,
                'evaluacion': evaluacion,
                'prestaciones_activas': prestaciones_activas,
                'ultima_prestacion': ultima_prestacion,
                'prestaciones_entregadas': prestaciones_entregadas,
                'puede_cerrar': prestaciones_activas == 0,
            },
        )

    if request.method == 'POST':
        from django.db import transaction
        from django.utils import timezone

        caso.refresh_from_db()
        if caso.estado != 'EN_SEGUIMIENTO':
            messages.error(request, 'El caso ya fue procesado por otro usuario')
            return redirect('legajos:programa_detalle', pk=2)

        prestaciones_activas = PrestacionNachec.objects.filter(
            plan=plan_vigente,
            estado__in=['PROGRAMADA', 'EN_PROCESO', 'EN_CURSO']
        ).count() if plan_vigente else 0

        if prestaciones_activas > 0:
            messages.error(request, f'No se puede cerrar: existen {prestaciones_activas} prestaciones activas')
            return redirect('legajos:nachec_cerrar_caso', caso_id=caso.id)

        motivo_cierre = request.POST.get('motivo_cierre')
        informe_cierre = request.POST.get('informe_cierre', '').strip()
        confirmacion = request.POST.get('confirmacion')

        if not motivo_cierre:
            messages.error(request, 'Debe seleccionar un motivo de cierre')
            return redirect('legajos:nachec_cerrar_caso', caso_id=caso.id)

        if len(informe_cierre) < 30:
            messages.error(request, 'El informe de cierre debe tener al menos 30 caracteres')
            return redirect('legajos:nachec_cerrar_caso', caso_id=caso.id)

        if not confirmacion:
            messages.error(request, 'Debe confirmar el cierre del caso')
            return redirect('legajos:nachec_cerrar_caso', caso_id=caso.id)

        with transaction.atomic():
            estado_anterior = caso.estado
            caso.estado = 'CERRADO'
            caso.fecha_cierre = timezone.now().date()
            caso.motivo_cierre = f"{motivo_cierre}: {informe_cierre}"
            caso.save()

            if plan_vigente:
                plan_vigente.vigente = False
                plan_vigente.save()

            tareas_abiertas = TareaNachec.objects.filter(
                caso=caso,
                estado__in=['PENDIENTE', 'EN_PROCESO']
            )
            tareas_canceladas = tareas_abiertas.count()
            tareas_abiertas.update(
                estado='CANCELADA',
                resultado=f"Cancelada por cierre de caso: {motivo_cierre}"
            )

            if tarea_cierre:
                tarea_cierre.estado = 'COMPLETADA'
                tarea_cierre.fecha_completada = timezone.now()
                tarea_cierre.resultado = f"Caso cerrado: {motivo_cierre}"
                tarea_cierre.save()

            prestaciones_entregadas = PrestacionNachec.objects.filter(
                caso=caso,
                estado='ENTREGADA'
            ).count()
            score_total = caso.evaluacion.score_total if hasattr(caso, 'evaluacion') else 0

            HistorialEstadoCaso.objects.create(
                caso=caso,
                estado_anterior=estado_anterior,
                estado_nuevo=caso.estado,
                usuario=request.user,
                observacion=f"""Caso cerrado por {request.user.get_full_name()}
Motivo: {motivo_cierre}
Plan ID: {plan_vigente.id if plan_vigente else 'N/A'}
Prestaciones entregadas: {prestaciones_entregadas}
Score total: {score_total}
Tareas canceladas: {tareas_canceladas}

Informe de cierre:
{informe_cierre}"""
            )

        messages.success(request, f'Caso cerrado correctamente. Fecha: {caso.fecha_cierre.strftime("%d/%m/%Y")}')
        return redirect('legajos:programa_detalle', pk=2)


@login_required
def reabrir_caso_nachec(request, caso_id):
    """CERRADO → EN_SEGUIMIENTO/EVALUADO/PLAN_DEFINIDO según tipo de reapertura"""
    from django.http import HttpResponseForbidden
    from ..models.nachec import PlanIntervencionNachec, PrestacionNachec

    caso = get_object_or_404(CasoNachec, id=caso_id)

    if caso.estado != 'CERRADO':
        messages.error(request, 'El caso no está cerrado')
        return redirect('legajos:programa_detalle', pk=2)

    es_coordinador = request.user.id == caso.coordinador_id
    es_superadmin = request.user.is_superuser

    if not es_coordinador and not es_superadmin:
        messages.error(request, 'No tienes permiso para reabrir este caso')
        return HttpResponseForbidden('Acceso denegado: solo coordinador o superadmin')

    if request.method == 'GET':
        planes_historicos = PlanIntervencionNachec.objects.filter(caso=caso).order_by('-creado')
        plan_mas_reciente = planes_historicos.first()
        prestaciones_activas = PrestacionNachec.objects.filter(
            caso=caso,
            estado__in=['PROGRAMADA', 'EN_PROCESO', 'EN_CURSO']
        ).count()
        evaluacion = caso.evaluacion if hasattr(caso, 'evaluacion') else None

        return render(
            request,
            'legajos/nachec/modal_reabrir_caso.html',
            {
                'caso': caso,
                'plan_mas_reciente': plan_mas_reciente,
                'tiene_plan': planes_historicos.exists(),
                'prestaciones_activas': prestaciones_activas,
                'evaluacion': evaluacion,
            },
        )

    if request.method == 'POST':
        from django.db import transaction
        from django.utils import timezone

        caso.refresh_from_db()
        if caso.estado != 'CERRADO':
            messages.error(request, 'El caso ya fue procesado por otro usuario')
            return redirect('legajos:programa_detalle', pk=2)

        tipo_reapertura = request.POST.get('tipo_reapertura')
        motivo_reapertura = request.POST.get('motivo_reapertura')
        detalle_reapertura = request.POST.get('detalle_reapertura', '').strip()

        if not tipo_reapertura:
            messages.error(request, 'Debe seleccionar tipo de reapertura')
            return redirect('legajos:nachec_reabrir_caso', caso_id=caso.id)

        if not motivo_reapertura:
            messages.error(request, 'Debe seleccionar motivo de reapertura')
            return redirect('legajos:nachec_reabrir_caso', caso_id=caso.id)

        if len(detalle_reapertura) < 30:
            messages.error(request, 'El detalle debe tener al menos 30 caracteres')
            return redirect('legajos:nachec_reabrir_caso', caso_id=caso.id)

        with transaction.atomic():
            estado_anterior = caso.estado
            tareas_creadas = []
            plan_reactivado = None

            if tipo_reapertura == 'ADMINISTRATIVA':
                caso.estado = 'EN_SEGUIMIENTO'
                caso.fecha_cierre = None
                caso.save()

                tarea = TareaNachec.objects.create(
                    caso=caso,
                    tipo='OTRO',
                    titulo='Revisión por reapertura administrativa',
                    descripcion=f"""Caso reabierto administrativamente.

Motivo: {motivo_reapertura}
Detalle: {detalle_reapertura}

Debe revisar documentación y validar información.""",
                    asignado_a=caso.coordinador or request.user,
                    creado_por=request.user,
                    estado='PENDIENTE',
                    prioridad=caso.prioridad or 'MEDIA',
                    fecha_vencimiento=(timezone.now() + timedelta(days=2)).date()
                )
                tareas_creadas.append(tarea.id)

            elif tipo_reapertura == 'OPERATIVA':
                accion_operativa = request.POST.get('accion_operativa')

                if accion_operativa == 'REACTIVAR_PLAN':
                    plan_mas_reciente = PlanIntervencionNachec.objects.filter(caso=caso).order_by('-creado').first()

                    if not plan_mas_reciente:
                        messages.error(request, 'No existe plan para reactivar. Use "Forzar reevaluación".')
                        return redirect('legajos:nachec_reabrir_caso', caso_id=caso.id)

                    PlanIntervencionNachec.objects.filter(caso=caso, vigente=True).update(vigente=False)
                    plan_mas_reciente.vigente = True
                    plan_mas_reciente.save()
                    plan_reactivado = plan_mas_reciente.id

                    caso.estado = 'PLAN_DEFINIDO'
                    caso.fecha_cierre = None
                    caso.save()

                    sla_dias = {'URGENTE': 1, 'ALTA': 1, 'MEDIA': 2, 'BAJA': 3}.get(caso.prioridad or 'MEDIA', 2)
                    tarea = TareaNachec.objects.create(
                        caso=caso,
                        tipo='OTRO',
                        titulo='Activar plan reactivado',
                        descripcion=f"""Caso reabierto operativamente con plan reactivado.

Motivo: {motivo_reapertura}
Detalle: {detalle_reapertura}

Plan ID: {plan_mas_reciente.id}

Debe activar el plan y programar prestaciones.""",
                        asignado_a=caso.coordinador or request.user,
                        creado_por=request.user,
                        estado='PENDIENTE',
                        prioridad=caso.prioridad or 'MEDIA',
                        fecha_vencimiento=(timezone.now() + timedelta(days=sla_dias)).date()
                    )
                    tareas_creadas.append(tarea.id)

                elif accion_operativa == 'FORZAR_REEVALUACION':
                    PlanIntervencionNachec.objects.filter(caso=caso, vigente=True).update(vigente=False)

                    caso.estado = 'EVALUADO'
                    caso.fecha_cierre = None
                    caso.save()

                    sla_dias = {'URGENTE': 1, 'ALTA': 1, 'MEDIA': 2, 'BAJA': 3}.get(caso.prioridad or 'MEDIA', 2)
                    tarea = TareaNachec.objects.create(
                        caso=caso,
                        tipo='OTRO',
                        titulo='Reevaluar caso reabierto',
                        descripcion=f"""Caso reabierto operativamente para reevaluación.

Motivo: {motivo_reapertura}
Detalle: {detalle_reapertura}

Debe evaluar nuevamente el caso y definir plan de intervención.""",
                        asignado_a=caso.coordinador or request.user,
                        creado_por=request.user,
                        estado='PENDIENTE',
                        prioridad=caso.prioridad or 'MEDIA',
                        fecha_vencimiento=(timezone.now() + timedelta(days=sla_dias)).date()
                    )
                    tareas_creadas.append(tarea.id)

                else:
                    messages.error(request, 'Debe seleccionar acción operativa')
                    return redirect('legajos:nachec_reabrir_caso', caso_id=caso.id)

            else:
                messages.error(request, 'Tipo de reapertura inválido')
                return redirect('legajos:nachec_reabrir_caso', caso_id=caso.id)

            HistorialEstadoCaso.objects.create(
                caso=caso,
                estado_anterior=estado_anterior,
                estado_nuevo=caso.estado,
                usuario=request.user,
                observacion=f"""Caso reabierto por {request.user.get_full_name()}
Tipo: {tipo_reapertura}
Motivo: {motivo_reapertura}
Plan reactivado: {plan_reactivado or 'N/A'}
Tareas creadas: {len(tareas_creadas)}

Detalle:
{detalle_reapertura}"""
            )

        messages.success(request, f'Caso reabierto exitosamente. Estado: {caso.get_estado_display()}')
        return redirect('legajos:programa_detalle', pk=2)
