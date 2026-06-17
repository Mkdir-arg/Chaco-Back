from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from ..models.nachec import CasoNachec, HistorialEstadoCaso, RelevamientoNachec, TareaNachec
from ..services import ServicioOperacionNachec


def _get_municipios():
    """Obtener lista de municipios"""
    from core.models import Municipio
    return Municipio.objects.all().order_by('nombre')


@login_required
def completar_validacion(request, caso_id):
    """Completar validación creando tarea si no existe"""
    caso = get_object_or_404(CasoNachec, id=caso_id)

    if request.method == 'POST':
        ServicioOperacionNachec.completar_validacion(caso, request.user)
        messages.success(request, 'Validación completada. Ahora puede enviar el caso a asignación.')
        return redirect('legajos:programa_detalle', pk=2)

    return redirect('legajos:nachec_ver_tarea_validacion', caso_id=caso_id)


@login_required
def ver_tarea_validacion(request, caso_id):
    """Ver tarea de validación con checklist"""
    caso = get_object_or_404(CasoNachec, id=caso_id)
    tarea = TareaNachec.objects.filter(caso=caso, tipo='VALIDACION').first()
    return render(
        request,
        'legajos/nachec/ver_tarea_validacion.html',
        {
            'caso': caso,
            'tarea': tarea,
        },
    )


@login_required
def completar_tarea(request, tarea_id):
    """Completar una tarea"""
    tarea = get_object_or_404(TareaNachec, id=tarea_id)

    if request.method == 'POST':
        ServicioOperacionNachec.completar_tarea(tarea)
        messages.success(request, f'Tarea "{tarea.titulo}" completada')
        return redirect(request.META.get('HTTP_REFERER', 'legajos:programa_detalle'), pk=2)

    return redirect('legajos:programa_detalle', pk=2)


@login_required
def enviar_a_asignacion(request, caso_id):
    """EN_REVISION → A_ASIGNAR con validación completa"""
    caso = get_object_or_404(CasoNachec, id=caso_id)

    if caso.estado != 'EN_REVISION':
        messages.error(request, 'El caso no está en revisión')
        return redirect('legajos:programa_detalle', pk=2)

    if request.method == 'GET':
        context = ServicioOperacionNachec.build_envio_asignacion_context(caso)

        return render(
            request,
            'legajos/nachec/modal_enviar_asignacion.html',
            {
                'caso': caso,
                'validaciones': context['validaciones'],
                'puede_confirmar': context['puede_confirmar'],
                'tarea_validacion': context['tarea_validacion'],
                'municipios': _get_municipios(),
            },
        )

    if request.method == 'POST':
        try:
            result = ServicioOperacionNachec.enviar_a_asignacion(
                caso=caso,
                usuario=request.user,
                municipio=request.POST.get('municipio'),
                localidad=request.POST.get('localidad'),
                observaciones=request.POST.get('observaciones', ''),
            )
        except Exception as exc:
            messages.error(request, str(exc))
            return redirect('legajos:nachec_enviar_asignacion', caso_id=caso_id)

        messages.success(
            request,
            f"Caso enviado a asignación. Tarea creada para Coordinación (SLA: {result['sla_horas']}h)",
        )
        return redirect('legajos:programa_detalle', pk=2)


@login_required
def asignar_territorial(request, caso_id):
    """A_ASIGNAR → ASIGNADO con modal mejorado"""
    from django.contrib.auth.models import User
    from django.db import transaction
    from django.utils import timezone

    caso = get_object_or_404(CasoNachec, id=caso_id)

    if request.method == 'POST':
        caso.refresh_from_db()
        if caso.estado != 'A_ASIGNAR':
            messages.error(request, 'El caso ya fue asignado por otro usuario. Actualice la pantalla.')
            return redirect('legajos:programa_detalle', pk=2)

        territorial_id = request.POST.get('territorial_id')
        fecha_limite = request.POST.get('fecha_limite_relevamiento')
        instrucciones = request.POST.get('instrucciones', '').strip()

        if not territorial_id:
            messages.error(request, 'Debe seleccionar un territorial válido')
            return redirect('legajos:nachec_asignar_territorial', caso_id=caso.id)
        if not fecha_limite:
            messages.error(request, 'Debe especificar fecha límite de relevamiento')
            return redirect('legajos:nachec_asignar_territorial', caso_id=caso.id)

        try:
            territorial = User.objects.get(id=territorial_id, is_active=True)
        except User.DoesNotExist:
            messages.error(request, 'El territorial seleccionado no es válido')
            return redirect('legajos:nachec_asignar_territorial', caso_id=caso.id)

        from datetime import datetime
        try:
            fecha_limite_obj = datetime.strptime(fecha_limite, '%Y-%m-%d').date()
        except ValueError:
            messages.error(request, 'Formato de fecha inválido')
            return redirect('legajos:nachec_asignar_territorial', caso_id=caso.id)

        try:
            ServicioOperacionNachec.asignar_territorial(
                caso=caso,
                coordinador=request.user,
                territorial=territorial,
                fecha_limite_obj=fecha_limite_obj,
                instrucciones=instrucciones,
            )
        except Exception as exc:
            messages.error(request, str(exc))
            return redirect('legajos:nachec_asignar_territorial', caso_id=caso.id)

        messages.success(request, f'Territorial asignado exitosamente. Tarea de relevamiento creada con vencimiento {fecha_limite_obj.strftime("%d/%m/%Y")}.')
        return redirect('legajos:programa_detalle', pk=2)

    if caso.sla_revision:
        dias_restantes = (caso.sla_revision - timezone.now().date()).days
        if dias_restantes < 0:
            sla_texto = f"Vencido hace {abs(dias_restantes)} días"
        elif dias_restantes == 0:
            sla_texto = "Vence hoy"
        else:
            sla_texto = f"Vence en {dias_restantes} días"
    else:
        sla_texto = "No definido"

    if caso.prioridad == 'URGENTE' or caso.prioridad == 'ALTA':
        dias_sla = 1
    elif caso.prioridad == 'MEDIA':
        dias_sla = 2
    else:
        dias_sla = 3

    fecha_limite_default = (timezone.now() + timedelta(days=dias_sla)).date()

    territoriales = User.objects.filter(is_active=True).order_by('first_name', 'last_name')
    for territorial in territoriales:
        territorial.casos_activos = CasoNachec.objects.filter(
            territorial=territorial,
            estado__in=['ASIGNADO', 'EN_RELEVAMIENTO', 'EN_EJECUCION', 'EN_SEGUIMIENTO'],
        ).count()

    territoriales_sugeridos = sorted(territoriales, key=lambda item: item.casos_activos)[:3]

    return render(
        request,
        'legajos/nachec/asignar_territorial.html',
        {
            'caso': caso,
            'territoriales': territoriales,
            'territoriales_sugeridos': territoriales_sugeridos,
            'sla_asignacion_texto': sla_texto,
            'fecha_limite_default': fecha_limite_default.strftime('%Y-%m-%d'),
            'fecha_minima': timezone.now().date().strftime('%Y-%m-%d'),
        },
    )


@login_required
def reasignar_territorial(request, caso_id):
    """Reasignar territorial (solo superadmin)"""
    from django.contrib.auth.models import User

    if not request.user.is_superuser:
        messages.error(request, 'Solo superadmin puede reasignar casos')
        return HttpResponseForbidden('Acceso denegado')

    caso = get_object_or_404(CasoNachec, id=caso_id)

    if request.method == 'POST':
        territorial_id = request.POST.get('territorial_id')
        motivo = request.POST.get('motivo', '').strip()

        if not territorial_id:
            messages.error(request, 'Debe seleccionar un territorial')
            return redirect('legajos:nachec_reasignar_territorial', caso_id=caso.id)
        if len(motivo) < 10:
            messages.error(request, 'El motivo debe tener al menos 10 caracteres')
            return redirect('legajos:nachec_reasignar_territorial', caso_id=caso.id)

        try:
            territorial = User.objects.get(id=territorial_id, is_active=True)
        except User.DoesNotExist:
            messages.error(request, 'Territorial no válido')
            return redirect('legajos:nachec_reasignar_territorial', caso_id=caso.id)

        try:
            ServicioOperacionNachec.reasignar_territorial(
                caso=caso,
                usuario=request.user,
                territorial=territorial,
                motivo=motivo,
            )
        except ValidationError as exc:
            messages.error(request, str(exc.message))
            return redirect('legajos:nachec_reasignar_territorial', caso_id=caso.id)

        messages.success(request, f'Caso reasignado a {territorial.get_full_name()}')
        return redirect('legajos:programa_detalle', pk=2)

    context = ServicioOperacionNachec.build_reasignacion_context(caso)

    return render(
        request,
        'legajos/nachec/reasignar_territorial.html',
        {
            'caso': caso,
            'territoriales': context['territoriales'],
            'territorial_actual': context['territorial_actual'],
        },
    )


@login_required
def iniciar_relevamiento(request, caso_id):
    """ASIGNADO → EN_RELEVAMIENTO con control de acceso y validaciones"""
    caso = get_object_or_404(CasoNachec, id=caso_id)

    if request.method == 'POST':
        caso.refresh_from_db()
        if caso.estado != 'ASIGNADO':
            messages.error(request, 'El caso no está en estado ASIGNADO')
            return redirect('legajos:programa_detalle', pk=2)
        if request.user.id != caso.territorial_id:
            messages.error(request, 'No estás asignado como territorial a este caso')
            return HttpResponseForbidden('Acceso denegado: no eres el territorial asignado')

        try:
            result = ServicioOperacionNachec.iniciar_relevamiento(caso=caso, territorial=request.user)
        except ValidationError as exc:
            messages.error(request, str(exc.message))
            return redirect('legajos:programa_detalle', pk=2)

        if result['sla_vencido']:
            messages.warning(request, 'Relevamiento iniciado. ADVERTENCIA: SLA vencido - el inicio se registró fuera de término.')
        else:
            messages.success(request, 'Relevamiento iniciado exitosamente. Tarea en proceso.')
        return redirect('legajos:nachec_formulario_relevamiento', caso_id=caso.id)

    if request.user.id != caso.territorial_id:
        messages.error(request, 'Solo el territorial asignado puede iniciar el relevamiento')
        return HttpResponseForbidden('Acceso denegado')
    if caso.estado != 'ASIGNADO':
        messages.error(request, 'El caso no está en estado ASIGNADO')
        return redirect('legajos:programa_detalle', pk=2)

    context = ServicioOperacionNachec.build_inicio_relevamiento_context(caso)

    return render(
        request,
        'legajos/nachec/iniciar_relevamiento.html',
        {
            'caso': caso,
            'sla_texto': context['sla_texto'],
            'sla_vencido': context['sla_vencido'],
        },
    )


@login_required
def finalizar_relevamiento(request, caso_id):
    """EN_RELEVAMIENTO → EVALUADO con validaciones y scoring"""
    from django.contrib.contenttypes.models import ContentType
    from django.db import transaction
    from django.http import HttpResponseForbidden
    from django.utils import timezone

    from legajos.models import Adjunto

    caso = get_object_or_404(CasoNachec, id=caso_id)

    if caso.estado != 'EN_RELEVAMIENTO':
        messages.error(request, 'El caso no está en relevamiento')
        return redirect('legajos:programa_detalle', pk=2)
    if request.user.id != caso.territorial_id:
        messages.error(request, 'Solo el territorial asignado puede finalizar el relevamiento')
        return HttpResponseForbidden('Acceso denegado')

    try:
        relevamiento = RelevamientoNachec.objects.filter(caso=caso, completado=False).latest('creado')
    except RelevamientoNachec.DoesNotExist:
        messages.error(request, 'No existe relevamiento sin completar para este caso. Debe completar el formulario de relevamiento primero.')
        return redirect('legajos:nachec_formulario_relevamiento', caso_id=caso.id)

    if request.method == 'GET':
        validaciones = {}
        validaciones['relevamiento_completo'] = relevamiento.is_completo()
        validaciones['faltantes'] = relevamiento.faltantes_por_seccion()

        content_type = ContentType.objects.get_for_model(RelevamientoNachec)
        adjuntos = Adjunto.objects.filter(content_type=content_type, object_id=relevamiento.id)
        validaciones['cantidad_evidencias'] = adjuntos.count()

        riesgo_critico = (
            relevamiento.urgencia_alimentaria
            or relevamiento.hay_violencia
            or relevamiento.tipo_vivienda in ['PRECARIA', 'CALLE']
        )
        validaciones['riesgo_critico'] = riesgo_critico
        validaciones['evidencia_obligatoria'] = riesgo_critico and adjuntos.count() == 0

        score_total, score_categoria, score_detalle = relevamiento.calcular_scoring()

        sla_vencido = False
        if caso.sla_relevamiento:
            dias_restantes = (caso.sla_relevamiento - timezone.now().date()).days
            if dias_restantes < 0:
                sla_texto = f"Vencido hace {abs(dias_restantes)} días"
                sla_vencido = True
            elif dias_restantes == 0:
                sla_texto = "Vence hoy"
            else:
                sla_texto = f"Vence en {dias_restantes} días"
        else:
            sla_texto = "No definido"

        puede_finalizar = validaciones['relevamiento_completo'] and not validaciones['evidencia_obligatoria']

        return render(
            request,
            'legajos/nachec/modal_finalizar_relevamiento.html',
            {
                'caso': caso,
                'relevamiento': relevamiento,
                'validaciones': validaciones,
                'adjuntos': adjuntos,
                'score_total': score_total,
                'score_categoria': score_categoria,
                'score_detalle': score_detalle,
                'sla_texto': sla_texto,
                'sla_vencido': sla_vencido,
                'puede_finalizar': puede_finalizar,
            },
        )

    if request.method == 'POST':
        caso.refresh_from_db()
        relevamiento.refresh_from_db()

        if caso.estado != 'EN_RELEVAMIENTO':
            messages.error(request, 'El caso ya fue procesado por otro usuario')
            return redirect('legajos:programa_detalle', pk=2)
        if relevamiento.completado:
            messages.warning(request, 'Este relevamiento ya fue finalizado')
            return redirect('legajos:programa_detalle', pk=2)
        if not relevamiento.is_completo():
            faltantes = relevamiento.faltantes_por_seccion()
            msg_faltantes = []
            for seccion, campos in faltantes.items():
                if campos:
                    msg_faltantes.append(f"{seccion.title()}: {', '.join(campos)}")
            messages.error(request, f'No se puede finalizar. Faltan campos: {" | ".join(msg_faltantes)}')
            return redirect('legajos:nachec_finalizar_relevamiento', caso_id=caso.id)

        content_type = ContentType.objects.get_for_model(RelevamientoNachec)
        adjuntos = Adjunto.objects.filter(content_type=content_type, object_id=relevamiento.id)
        riesgo_critico = (
            relevamiento.urgencia_alimentaria
            or relevamiento.hay_violencia
            or relevamiento.tipo_vivienda in ['PRECARIA', 'CALLE']
        )

        if riesgo_critico and adjuntos.count() == 0:
            messages.error(request, 'No se puede finalizar: debe adjuntar evidencia por situación de riesgo crítico (urgencia alimentaria, violencia o vivienda precaria/calle)')
            return redirect('legajos:nachec_finalizar_relevamiento', caso_id=caso.id)

        observaciones_cierre = request.POST.get('observaciones_cierre', '').strip()
        if len(observaciones_cierre) < 10:
            messages.error(request, 'Las observaciones de cierre deben tener al menos 10 caracteres')
            return redirect('legajos:nachec_finalizar_relevamiento', caso_id=caso.id)

        with transaction.atomic():
            score_total, score_categoria, score_detalle = relevamiento.calcular_scoring()
            relevamiento.score_total = score_total
            relevamiento.score_categoria = score_categoria
            relevamiento.score_detalle = score_detalle
            relevamiento.score_version = 'v1'
            relevamiento.completado = True
            relevamiento.fecha_finalizacion = timezone.now()
            relevamiento.observaciones_cierre = observaciones_cierre
            relevamiento.save()

            estado_anterior = caso.estado
            caso.estado = 'EVALUADO'
            caso.fecha_relevamiento = timezone.now().date()
            caso.save()

            tarea_relevamiento = TareaNachec.objects.filter(
                caso=caso,
                tipo='RELEVAMIENTO',
                asignado_a=caso.territorial,
                estado__in=['PENDIENTE', 'EN_PROCESO'],
            ).first()

            if tarea_relevamiento:
                tarea_relevamiento.estado = 'COMPLETADA'
                tarea_relevamiento.fecha_completada = timezone.now()
                tarea_relevamiento.resultado = f"Relevamiento finalizado. Score: {score_total} ({score_categoria}). Versión: v1"
                tarea_relevamiento.save()

            tarea_evaluacion_existente = TareaNachec.objects.filter(
                caso=caso,
                tipo='OTRO',
                titulo__icontains='Evaluar caso',
                estado__in=['PENDIENTE', 'EN_PROCESO'],
            ).first()

            sla_dias = {'URGENTE': 1, 'ALTA': 1, 'MEDIA': 2, 'BAJA': 3}.get(caso.prioridad, 2)
            sla_evaluacion = timezone.now() + timedelta(days=sla_dias)

            if not tarea_evaluacion_existente:
                TareaNachec.objects.create(
                    caso=caso,
                    tipo='OTRO',
                    titulo='Evaluar caso y definir plan de intervención',
                    descripcion=f"""Relevamiento finalizado. Debe evaluar el caso y definir plan de intervención.

Scoring de vulnerabilidad (v1):
- Total: {score_total}/100
- Categoría: {score_categoria}
- Familia: {score_detalle.get('familia', 0)}/15
- Ingresos: {score_detalle.get('ingresos', 0)}/25
- Vivienda: {score_detalle.get('vivienda', 0)}/20
- Salud: {score_detalle.get('salud', 0)}/25
- Riesgos: {score_detalle.get('riesgos', 0)}/15

Observaciones del territorial:
{observaciones_cierre}

Evidencias adjuntas: {adjuntos.count()}
Riesgo crítico: {'Sí' if riesgo_critico else 'No'}""",
                    asignado_a=caso.coordinador or request.user,
                    creado_por=request.user,
                    estado='PENDIENTE',
                    prioridad=caso.prioridad,
                    fecha_vencimiento=sla_evaluacion.date(),
                )

            sla_cumplido = caso.sla_relevamiento and timezone.now().date() <= caso.sla_relevamiento
            HistorialEstadoCaso.objects.create(
                caso=caso,
                estado_anterior=estado_anterior,
                estado_nuevo=caso.estado,
                usuario=request.user,
                observacion=f"""Relevamiento finalizado por {request.user.get_full_name()}
Score: {score_total}/100 ({score_categoria}) [v1]
Evidencias: {adjuntos.count()}
Riesgo crítico: {'Sí' if riesgo_critico else 'No'}
SLA cumplido: {'Sí' if sla_cumplido else 'No'}
Observaciones: {observaciones_cierre[:100]}...""",
            )

        messages.success(request, f'Relevamiento finalizado. Caso pasó a EVALUADO. Score: {score_total} ({score_categoria})')
        return redirect('legajos:programa_detalle', pk=2)


def _aplicar_datos_relevamiento(relevamiento, post):
    """Aplica los datos del POST a la instancia de relevamiento (sin guardar)."""
    relevamiento.cantidad_convivientes = int(post.get('cantidad_convivientes', 0) or 0)
    relevamiento.hay_embarazo = post.get('hay_embarazo') == 'on'
    relevamiento.hay_discapacidad = post.get('hay_discapacidad') == 'on'
    relevamiento.detalle_discapacidad = post.get('detalle_discapacidad', '')
    relevamiento.ingreso_mensual_rango = post.get('ingreso_mensual_rango')
    relevamiento.fuente_ingreso = post.get('fuente_ingreso')
    relevamiento.situacion_laboral = post.get('situacion_laboral')
    relevamiento.tipo_vivienda = post.get('tipo_vivienda')
    relevamiento.material_predominante = post.get('material_predominante')
    relevamiento.tiene_agua = post.get('tiene_agua') == 'on'
    relevamiento.tiene_luz = post.get('tiene_luz') == 'on'
    relevamiento.tiene_gas = post.get('tiene_gas') == 'on'
    relevamiento.tiene_cloaca = post.get('tiene_cloaca') == 'on'
    relevamiento.cobertura_salud = post.get('cobertura_salud')
    relevamiento.menores_escolarizados = post.get('menores_escolarizados') == 'on'
    relevamiento.acceso_alimentos = post.get('acceso_alimentos')
    relevamiento.frecuencia_comidas = int(post.get('frecuencia_comidas', 0) or 0)
    relevamiento.hay_violencia = post.get('hay_violencia') == 'on'
    relevamiento.urgencia_alimentaria = post.get('urgencia_alimentaria') == 'on'
    relevamiento.observaciones = post.get('observaciones', '')


@login_required
def formulario_relevamiento(request, caso_id):
    """Formulario de relevamiento sociofamiliar"""
    from django.contrib.contenttypes.models import ContentType

    from legajos.models import Adjunto

    caso = get_object_or_404(CasoNachec, id=caso_id)

    if request.method == 'POST':
        relevamiento, _ = RelevamientoNachec.objects.get_or_create(
            caso=caso,
            defaults={
                'territorial': request.user,
                'cantidad_convivientes': int(request.POST.get('cantidad_convivientes', 0) or 0),
                'frecuencia_comidas': int(request.POST.get('frecuencia_comidas', 0) or 0),
            },
        )

        _aplicar_datos_relevamiento(relevamiento, request.POST)
        relevamiento.save()

        content_type = ContentType.objects.get_for_model(RelevamientoNachec)
        evidencias_subidas = 0
        for key in request.FILES:
            if key.startswith('evidencia_'):
                archivo = request.FILES[key]
                Adjunto.objects.create(
                    content_type=content_type,
                    object_id=relevamiento.id,
                    archivo=archivo,
                    etiqueta=f"Evidencia {key.split('_')[1]}",
                )
                evidencias_subidas += 1

        if evidencias_subidas > 0:
            messages.success(request, f'Relevamiento guardado con {evidencias_subidas} evidencia(s).')
        else:
            messages.success(request, 'Relevamiento guardado exitosamente.')
        return redirect('legajos:programa_detalle', pk=2)

    relevamiento = RelevamientoNachec.objects.filter(caso=caso).order_by('-creado').first()
    if not relevamiento:
        relevamiento = RelevamientoNachec.objects.create(
            caso=caso,
            territorial=request.user,
            cantidad_convivientes=0,
            frecuencia_comidas=0,
        )

    score_total, score_categoria, score_desglose = relevamiento.calcular_scoring()

    return render(
        request,
        'legajos/nachec/formulario_relevamiento.html',
        {
            'caso': caso,
            'relevamiento': relevamiento,
            'score_total': score_total,
            'score_categoria': score_categoria,
            'score_desglose': score_desglose,
        },
    )


@login_required
def autosave_relevamiento(request, caso_id):
    """Autoguardado parcial del relevamiento — devuelve scoring en vivo."""
    from django.http import JsonResponse
    from django.utils import timezone

    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Metodo no permitido'}, status=405)

    caso = get_object_or_404(CasoNachec, id=caso_id)

    relevamiento, _ = RelevamientoNachec.objects.get_or_create(
        caso=caso,
        defaults={
            'territorial': request.user,
            'cantidad_convivientes': 0,
            'frecuencia_comidas': 0,
        },
    )

    _aplicar_datos_relevamiento(relevamiento, request.POST)
    relevamiento.save()

    score_total, score_categoria, score_desglose = relevamiento.calcular_scoring()

    return JsonResponse({
        'success': True,
        'score_total': score_total,
        'score_categoria': score_categoria,
        'score_desglose': score_desglose,
        'saved_at': timezone.now().strftime('%H:%M:%S'),
    })


@login_required
def adjuntar_evidencias(request, caso_id):
    """Pantalla para adjuntar evidencias al relevamiento"""
    from django.contrib.contenttypes.models import ContentType
    from django.http import HttpResponseForbidden

    from legajos.models import Adjunto

    caso = get_object_or_404(CasoNachec, id=caso_id)

    if request.user.id != caso.territorial_id:
        messages.error(request, 'Solo el territorial asignado puede adjuntar evidencias')
        return HttpResponseForbidden('Acceso denegado')

    relevamiento = RelevamientoNachec.objects.filter(caso=caso).order_by('-creado').first()
    if not relevamiento:
        messages.error(request, 'No existe relevamiento para este caso')
        return redirect('legajos:programa_detalle', pk=2)

    if request.method == 'POST':
        accion = request.POST.get('accion')

        if accion == 'subir':
            archivo = request.FILES.get('archivo')
            etiqueta = request.POST.get('etiqueta', '').strip()

            if not archivo:
                messages.error(request, 'Debe seleccionar un archivo')
                return redirect('legajos:nachec_adjuntar_evidencias', caso_id=caso.id)
            if len(etiqueta) < 3:
                messages.error(request, 'La etiqueta debe tener al menos 3 caracteres')
                return redirect('legajos:nachec_adjuntar_evidencias', caso_id=caso.id)

            content_type = ContentType.objects.get_for_model(RelevamientoNachec)
            Adjunto.objects.create(
                content_type=content_type,
                object_id=relevamiento.id,
                archivo=archivo,
                etiqueta=etiqueta,
                subido_por=request.user,
            )

            messages.success(request, f'Evidencia "{etiqueta}" adjuntada correctamente')
            return redirect('legajos:nachec_adjuntar_evidencias', caso_id=caso.id)

        if accion == 'continuar':
            messages.info(request, 'Puede finalizar el relevamiento cuando esté listo')
            return redirect('legajos:programa_detalle', pk=2)

    content_type = ContentType.objects.get_for_model(RelevamientoNachec)
    adjuntos = Adjunto.objects.filter(content_type=content_type, object_id=relevamiento.id)
    riesgo_critico = (
        relevamiento.urgencia_alimentaria
        or relevamiento.hay_violencia
        or relevamiento.tipo_vivienda in ['PRECARIA', 'CALLE']
    )

    return render(
        request,
        'legajos/nachec/adjuntar_evidencias.html',
        {
            'caso': caso,
            'relevamiento': relevamiento,
            'adjuntos': adjuntos,
            'riesgo_critico': riesgo_critico,
            'puede_continuar': not riesgo_critico or adjuntos.count() > 0,
        },
    )
