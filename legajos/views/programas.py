"""
Vistas para Gestión Operativa de Programas
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, DetailView
from django.db.models import Q
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.utils import timezone

from core.rbac import CapacidadRequeridaMixin
from programas.models import Programa, InscripcionPrograma


class ProgramaListView(CapacidadRequeridaMixin, LoginRequiredMixin, ListView):
    capacidades_requeridas = "programa.ver"
    """
    Lista de programas que el usuario puede gestionar.
    - SuperAdmin: ve todos
    - Coordinador: ve solo sus programas asignados
    """
    model = Programa
    template_name = 'legajos/programas/programa_list.html'
    context_object_name = 'programas'
    
    def get_queryset(self):
        # DEPRECATED: filtros/annotates legacy removidos (dependían de models_institucional).
        return Programa.objects.filter(estado=Programa.Estado.ACTIVO).order_by(
            'orden', 'nombre'
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['es_superadmin'] = self.request.user.is_superuser
        return context


class ProgramaDetailView(CapacidadRequeridaMixin, LoginRequiredMixin, DetailView):
    capacidades_requeridas = "programa.ver"
    """
    Vista detallada de un programa con 5 solapas operativas:
    1. Dashboard Ejecutivo
    2. Bandeja de Derivaciones
    3. Ciudadanos en Atención
    4. Instituciones Participantes
    5. Indicadores
    """
    model = Programa
    template_name = 'legajos/programas/programa_detail.html'
    context_object_name = 'programa'
    
    def get_template_names(self):
        """Usar template específico para Ñachec"""
        programa = self.get_object()
        if programa.tipo in ['NACHEC', 'ÑACHEC']:
            return ['legajos/programas/programa_nachec_detail.html']
        return ['legajos/programas/programa_detail.html']
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        programa = self.get_object()
        
        # Si es Ñachec, cargar datos específicos
        if programa.tipo in ['NACHEC', 'ÑACHEC']:
            from ..models.nachec import CasoNachec
            from programas.models import DerivacionPrograma
            
            # Filtros
            estado_filtro = self.request.GET.get('estado')
            urgencia_filtro = self.request.GET.get('urgencia')
            busqueda = self.request.GET.get('q')
            
            # Derivaciones de ciudadanos (igual que programa 1)
            derivaciones_qs = DerivacionPrograma.objects.filter(
                programa_destino=programa
            ).select_related('ciudadano', 'programa_origen', 'derivado_por')
            
            # Aplicar filtros
            if estado_filtro:
                derivaciones_qs = derivaciones_qs.filter(estado=estado_filtro)
            if urgencia_filtro:
                derivaciones_qs = derivaciones_qs.filter(urgencia=urgencia_filtro)
            if busqueda:
                derivaciones_qs = derivaciones_qs.filter(
                    Q(ciudadano__nombre__icontains=busqueda) |
                    Q(ciudadano__apellido__icontains=busqueda) |
                    Q(ciudadano__numero_documento__icontains=busqueda)
                )
            
            context['derivaciones_ciudadanos'] = derivaciones_qs.order_by('-creado')[:50]
            
            # Stats de derivaciones ciudadanos (siempre globales)
            context['stats_ciudadanos'] = {
                'pendientes': DerivacionPrograma.objects.filter(programa_destino=programa, estado='PENDIENTE').count(),
                'aceptadas': DerivacionPrograma.objects.filter(programa_destino=programa, estado='ACEPTADA').count(),
                'rechazadas': DerivacionPrograma.objects.filter(programa_destino=programa, estado='RECHAZADA').count(),
            }
            
            # Filtros activos
            context['filtros_activos'] = {
                'estado': estado_filtro,
                'urgencia': urgencia_filtro,
                'busqueda': busqueda
            }
            
            # Casos Ñachec para otras pestañas
            from ..models.nachec import TareaNachec
            casos_nachec = CasoNachec.objects.select_related(
                'ciudadano_titular', 'operador_admision', 'territorial'
            ).order_by('-fecha_derivacion')
            
            # Agregar información de tarea de validación a cada caso
            for caso in casos_nachec:
                tarea = TareaNachec.objects.filter(caso=caso, tipo='VALIDACION', estado='COMPLETADA').first()
                caso.tarea_validacion_completada = bool(tarea)
            
            context['casos_nachec'] = casos_nachec
            
            # Métricas del dashboard analítico
            from django.db.models import Avg
            from ..models.nachec import PrestacionNachec, PlanIntervencionNachec, EvaluacionVulnerabilidad, RelevamientoNachec
            from datetime import timedelta
            
            hoy = timezone.now().date()
            
            # Fase 1: Captación
            derivaciones_totales = casos_nachec.count()
            derivaciones_aceptadas = casos_nachec.exclude(estado='RECHAZADO').count()
            tasa_aceptacion = round((derivaciones_aceptadas / derivaciones_totales * 100) if derivaciones_totales > 0 else 0, 1)
            
            # Fase 2: Asignación
            relevamientos_completados = RelevamientoNachec.objects.filter(caso__in=casos_nachec, completado=True).count()
            casos_sin_asignar = casos_nachec.filter(estado='A_ASIGNAR').count()
            
            # Fase 3: Evaluación
            evaluaciones = EvaluacionVulnerabilidad.objects.filter(caso__in=casos_nachec)
            scoring_alto = evaluaciones.filter(categoria_final='ALTO').count()
            scoring_medio = evaluaciones.filter(categoria_final='MEDIO').count()
            scoring_bajo = evaluaciones.filter(categoria_final='BAJO').count()
            planes_activos = PlanIntervencionNachec.objects.filter(caso__in=casos_nachec, vigente=True).count()
            
            # Fase 4: Ejecución
            prestaciones_qs = PrestacionNachec.objects.filter(caso__in=casos_nachec)
            prestaciones_entregadas = prestaciones_qs.filter(estado='ENTREGADA').count()
            prestaciones_programadas = prestaciones_qs.filter(estado='PROGRAMADA').count()
            
            # Cumplimiento SLA
            prestaciones_con_sla = prestaciones_qs.filter(estado='ENTREGADA', sla_hasta__isnull=False, fecha_entregada__isnull=False)
            cumplidas = sum(1 for p in prestaciones_con_sla if p.fecha_entregada and p.sla_hasta and 
                            timezone.make_aware(timezone.datetime.combine(p.fecha_entregada, timezone.datetime.min.time())) <= p.sla_hasta)
            cumplimiento_sla = round((cumplidas / prestaciones_con_sla.count() * 100) if prestaciones_con_sla.count() > 0 else 0, 1)
            
            # Fase 5: Seguimiento
            casos_cerrados = casos_nachec.filter(estado='CERRADO').count()
            
            # Impacto
            familias_asistidas = casos_nachec.filter(estado__in=['EN_EJECUCION', 'EN_SEGUIMIENTO', 'CERRADO']).count()
            score_promedio = round(evaluaciones.aggregate(Avg('score_total'))['score_total__avg'] or 0, 1)
            
            context['stats_nachec'] = {
                'derivados': CasoNachec.objects.filter(estado='DERIVADO').count(),
                'en_revision': CasoNachec.objects.filter(estado='EN_REVISION').count(),
                'asignados': CasoNachec.objects.filter(estado='ASIGNADO').count(),
                'en_relevamiento': CasoNachec.objects.filter(estado='EN_RELEVAMIENTO').count(),
                'evaluados': CasoNachec.objects.filter(estado='EVALUADO').count(),
                'en_seguimiento': CasoNachec.objects.filter(estado='EN_SEGUIMIENTO').count(),
            }
            
            # Dashboard analítico
            context['dashboard_metricas'] = {
                'derivaciones_totales': derivaciones_totales,
                'tasa_aceptacion': tasa_aceptacion,
                'relevamientos_completados': relevamientos_completados,
                'casos_sin_asignar': casos_sin_asignar,
                'scoring_alto': scoring_alto,
                'scoring_medio': scoring_medio,
                'scoring_bajo': scoring_bajo,
                'planes_activos': planes_activos,
                'prestaciones_entregadas': prestaciones_entregadas,
                'prestaciones_programadas': prestaciones_programadas,
                'cumplimiento_sla': cumplimiento_sla,
                'casos_cerrados': casos_cerrados,
                'familias_asistidas': familias_asistidas,
                'score_promedio': score_promedio
            }
            
            # PASO 8: Prestaciones activas
            from ..models.nachec import PrestacionNachec
            
            # Filtrar prestaciones donde el usuario es responsable o coordinador del caso
            prestaciones_qs = PrestacionNachec.objects.filter(
                Q(responsable=self.request.user) | Q(caso__coordinador=self.request.user)
            ).select_related(
                'caso__ciudadano_titular',
                'responsable',
                'plan'
            ).order_by('-fecha_programada')
            
            context['prestaciones_nachec'] = prestaciones_qs
            
            return context
        # DEPRECATED: operativa institucional legacy retirada con models_institucional.
        context.update(
            {
                'legacy_programa_operativa_deprecated': True,
                'total_instituciones': 0,
                'total_derivaciones_pendientes': 0,
                'total_casos_activos': 0,
                'total_casos_totales': 0,
                'derivaciones_ciudadanos': [],
                'derivaciones_institucionales': [],
                'instituciones': [],
                'casos_activos': [],
                'acompanamientos': [],
                'total_acompanamientos_activos': 0,
                'stats_ciudadanos': {
                    'pendientes': 0,
                    'aceptadas': 0,
                    'rechazadas': 0,
                },
                'stats_acompanamientos': {
                    'activos': 0,
                    'seguimiento': 0,
                    'cerrados': 0,
                    'bajas': 0,
                },
                'total_derivaciones': 0,
                'tasa_aceptacion': 0,
                'top_instituciones': [],
                'max_casos_institucion': 0,
                'ultimas_derivaciones': [],
                'promedio_casos_institucion': 0,
                'total_acompanamientos_totales': InscripcionPrograma.objects.filter(
                    programa=programa
                ).count(),
                'es_superadmin': self.request.user.is_superuser,
            }
        )
        return context


@login_required
@require_http_methods(["POST"])
def dar_de_baja_inscripcion(request, inscripcion_id):
    """
    Da de baja a un ciudadano de un programa persistente.
    Espera campo POST 'motivo' (obligatorio).
    """
    from ..services.programas import BajaProgramaService

    inscripcion = get_object_or_404(InscripcionPrograma, id=inscripcion_id)
    motivo = request.POST.get('motivo', '').strip()

    if not motivo:
        messages.error(request, "Debe ingresar un motivo para la baja.")
        return redirect('legajos:programa_detalle', pk=inscripcion.programa_id)

    try:
        BajaProgramaService.dar_de_baja(
            inscripcion_id=inscripcion_id,
            usuario=request.user,
            motivo=motivo,
        )
        messages.success(
            request,
            f"{inscripcion.ciudadano.nombre_completo} fue dado de baja del programa correctamente.",
        )
    except ValueError as exc:
        messages.error(request, str(exc))

    return redirect('legajos:programa_detalle', pk=inscripcion.programa_id)
