from django.apps import apps
from django.db import models
from django.db.models import Count, Prefetch, Q


class OptimizedLegajoManager(models.Manager):
    """Manager optimizado para LegajoAtencion con queries preoptimizadas"""
    
    def with_full_relations(self):
        """Query completa con todas las relaciones optimizadas"""
        return self.select_related(
            'responsable'
        ).prefetch_related(
            'historial_contactos',
            'derivaciones__actividad_destino',
            'alertas'
        ).annotate(
            seguimientos_count=Count('historial_contactos'),
            eventos_count=Count('alertas'),
            derivaciones_count=Count('derivaciones')
        )
    
    def for_dashboard(self):
        """Query optimizada para dashboard"""
        return self.select_related(
            'responsable'
        ).annotate(
            seguimientos_count=Count('historial_contactos'),
            eventos_count=Count('alertas')
        )
    
    def for_list_view(self):
        """Query optimizada para vistas de lista"""
        return self.select_related(
            'responsable'
        ).annotate(
            seguimientos_count=Count('historial_contactos')
        )
    
    def activos(self):
        """Legajos activos con optimizaciones"""
        return self.for_list_view().filter(
            estado__in=['ABIERTO', 'EN_SEGUIMIENTO']
        )
    
    def con_riesgo_alto(self):
        """Legajos con riesgo alto optimizados"""
        return self.for_dashboard().filter(
            nivel_riesgo='ALTO'
        )


class OptimizedCiudadanoManager(models.Manager):
    """Manager optimizado para Ciudadano"""
    
    def with_legajos_info(self):
        """Ciudadanos con información de legajos optimizada"""
        return self.prefetch_related(
            Prefetch(
                'inscripciones_programas',
                queryset=apps.get_model('legajos', 'InscripcionPrograma').objects.select_related(
                    'programa', 'responsable'
                )
            )
        ).annotate(
            legajos_count=Count('inscripciones_programas'),
            legajos_activos_count=Count(
                'inscripciones_programas',
                filter=Q(inscripciones_programas__estado__in=['ACTIVO', 'EN_SEGUIMIENTO'])
            )
        )
    
    def activos(self):
        """Ciudadanos activos con optimizaciones básicas"""
        return self.filter(activo=True).annotate(
            legajos_count=Count('inscripciones_programas')
        )


class OptimizedInstitucionManager(models.Manager):
    """Manager optimizado para Institucion"""
    
    def with_full_info(self):
        """Instituciones con información completa optimizada"""
        return self.select_related(
            'provincia',
            'municipio', 
            'localidad'
        ).prefetch_related(
            'encargados',
            'documentos'
        ).annotate(
            legajos_count=Count('legajos'),
            encargados_count=Count('encargados')
        )
    
    def aprobadas(self):
        """Instituciones aprobadas con optimizaciones"""
        return self.with_full_info().filter(
            estado_registro='APROBADO'
        )
    
    def activas(self):
        """Instituciones activas con optimizaciones"""
        return self.with_full_info().filter(
            activo=True,
            estado_registro='APROBADO'
        )


class OptimizedAlertaManager(models.Manager):
    """Manager optimizado para AlertaCiudadano"""
    
    def activas_completas(self):
        """Alertas activas con relaciones completas"""
        return self.select_related(
            'ciudadano',
            'legajo',
            'cerrada_por'
        ).filter(activa=True)
    
    def por_prioridad(self, prioridad):
        """Alertas por prioridad optimizadas"""
        return self.activas_completas().filter(prioridad=prioridad)
    
    def criticas(self):
        """Alertas críticas optimizadas"""
        return self.por_prioridad('CRITICA')


class OptimizedDerivacionManager(models.Manager):
    """Manager optimizado para Derivacion"""
    
    def with_full_relations(self):
        """Derivaciones con relaciones completas"""
        return self.select_related(
            'legajo',
            'actividad_destino'
        )
    
    def pendientes(self):
        """Derivaciones pendientes optimizadas"""
        return self.with_full_relations().filter(estado='PENDIENTE')
    
    def por_urgencia(self, urgencia):
        """Derivaciones por urgencia optimizadas"""
        return self.with_full_relations().filter(urgencia=urgencia)