"""
Sistema de predicción de riesgo basado en análisis de patrones
"""
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Count, Avg


class RiskPredictor:
    """Predictor de riesgo para ciudadanos"""
    
    @staticmethod
    def calcular_riesgo_abandono(ciudadano):
        """
        Calcula probabilidad de abandono del tratamiento (0-100)
        """
        from .linking import get_active_legajo_for_ciudadano
        from .models_contactos import HistorialContacto
        
        score = 0
        factores = []
        
        # Obtener legajo activo
        legajo = get_active_legajo_for_ciudadano(ciudadano)
        
        if not legajo:
            return {'score': 0, 'nivel': 'BAJO', 'factores': ['Sin legajo activo']}
        
        ahora = timezone.now()
        hace_30_dias = ahora - timedelta(days=30)
        hace_15_dias = ahora - timedelta(days=15)
        hace_7_dias = ahora - timedelta(days=7)
        
        # Factor 1: Tiempo sin contacto (peso: 35%)
        ultimo_seguimiento = HistorialContacto.objects.filter(
            legajo=legajo
        ).order_by('-fecha_contacto').first()
        
        if ultimo_seguimiento:
            dias_sin_contacto = (ahora - ultimo_seguimiento.fecha_contacto).days
            if dias_sin_contacto > 30:
                score += 35
                factores.append(f'Sin contacto hace {dias_sin_contacto} días')
            elif dias_sin_contacto > 15:
                score += 20
                factores.append(f'Contacto irregular ({dias_sin_contacto} días)')
            elif dias_sin_contacto > 7:
                score += 10
                factores.append('Contacto espaciado')
        else:
            score += 35
            factores.append('Sin seguimientos registrados')
        
        # Factor 2: Calidad de contacto (peso: 25%)
        seguimientos_recientes = HistorialContacto.objects.filter(
            legajo=legajo,
            fecha_contacto__gte=hace_30_dias,
        )
        
        if seguimientos_recientes.exists():
            contactos_fallidos = seguimientos_recientes.filter(
                estado__in=['NO_CONTESTA', 'CANCELADO', 'REPROGRAMADO']
            ).count()
            total = seguimientos_recientes.count()

            tasa_problemas = contactos_fallidos / total
            if tasa_problemas > 0.6:
                score += 25
                factores.append('Alta tasa de contactos fallidos')
            elif tasa_problemas > 0.3:
                score += 15
                factores.append('Contactabilidad irregular')
        
        # Factor 3: Derivaciones recientes (peso: 20%)
        derivaciones_recientes = legajo.derivaciones.filter(
            creado__gte=hace_30_dias
        ).count()

        if derivaciones_recientes >= 2:
            score += 20
            factores.append(f'{derivaciones_recientes} derivaciones recientes')
        elif derivaciones_recientes == 1:
            score += 10
            factores.append('Derivación reciente')
        
        # Factor 4: Falta de plan vigente (peso: 10%)
        if not legajo.plan_vigente:
            score += 10
            factores.append('Sin plan de intervención vigente')
        
        # Factor 5: Nivel de riesgo del legajo (peso: 10%)
        if legajo.nivel_riesgo == 'ALTO':
            score += 10
            factores.append('Nivel de riesgo alto')
        elif legajo.nivel_riesgo == 'MEDIO':
            score += 5
        
        # Determinar nivel
        if score >= 70:
            nivel = 'CRITICO'
        elif score >= 50:
            nivel = 'ALTO'
        elif score >= 30:
            nivel = 'MEDIO'
        else:
            nivel = 'BAJO'
        
        return {
            'score': min(score, 100),
            'nivel': nivel,
            'factores': factores
        }
    
    @staticmethod
    def calcular_riesgo_evento_critico(ciudadano):
        """
        Calcula probabilidad de evento crítico en próximos 30 días (0-100)
        """
        from .linking import get_active_legajo_for_ciudadano
        from .models_contactos import HistorialContacto
        
        score = 0
        factores = []
        
        legajo = get_active_legajo_for_ciudadano(ciudadano)
        
        if not legajo:
            return {'score': 0, 'nivel': 'BAJO', 'factores': ['Sin legajo activo']}
        
        ahora = timezone.now()
        hace_90_dias = ahora - timedelta(days=90)
        hace_30_dias = ahora - timedelta(days=30)
        
        # Factor 1: Historial de derivaciones (peso: 40%)
        derivaciones_historicas = legajo.derivaciones.filter(
            creado__gte=hace_90_dias
        ).count()

        if derivaciones_historicas >= 3:
            score += 40
            factores.append(f'{derivaciones_historicas} derivaciones en últimos 90 días')
        elif derivaciones_historicas >= 2:
            score += 30
            factores.append('Múltiples derivaciones recientes')
        elif derivaciones_historicas == 1:
            score += 15
            factores.append('Derivación reciente')
        
        # Factor 2: Evaluación de riesgo (peso: 30%)
        try:
            evaluacion = legajo.evaluacion
            if evaluacion.riesgo_suicida:
                score += 30
                factores.append('⚠️ Riesgo suicida identificado')
            if evaluacion.violencia:
                score += 20
                factores.append('⚠️ Situación de violencia')
        except:
            pass
        
        # Factor 3: Nivel de riesgo del legajo (peso: 20%)
        if legajo.nivel_riesgo == 'ALTO':
            score += 20
            factores.append('Clasificación de riesgo alto')
        elif legajo.nivel_riesgo == 'MEDIO':
            score += 10
        
        # Factor 4: Falta de seguimiento (peso: 10%)
        seguimientos_recientes = HistorialContacto.objects.filter(
            legajo=legajo,
            fecha_contacto__gte=hace_30_dias
        ).count()
        
        if seguimientos_recientes == 0:
            score += 10
            factores.append('Sin seguimiento en 30 días')
        
        # Determinar nivel
        if score >= 70:
            nivel = 'CRITICO'
        elif score >= 50:
            nivel = 'ALTO'
        elif score >= 30:
            nivel = 'MEDIO'
        else:
            nivel = 'BAJO'
        
        return {
            'score': min(score, 100),
            'nivel': nivel,
            'factores': factores
        }
    
    @staticmethod
    def generar_recomendaciones(ciudadano):
        """
        Genera recomendaciones automáticas basadas en el análisis
        """
        from .linking import get_active_legajo_for_ciudadano
        from .models_contactos import HistorialContacto
        
        recomendaciones = []
        
        legajo = get_active_legajo_for_ciudadano(ciudadano)
        
        if not legajo:
            return ['Considerar apertura de nuevo legajo si requiere atención']
        
        ahora = timezone.now()
        hace_15_dias = ahora - timedelta(days=15)
        hace_30_dias = ahora - timedelta(days=30)
        
        # Recomendación 1: Contacto
        ultimo_seguimiento = HistorialContacto.objects.filter(
            legajo=legajo
        ).order_by('-fecha_contacto').first()
        
        if ultimo_seguimiento:
            dias_sin_contacto = (ahora - ultimo_seguimiento.fecha_contacto).days
            if dias_sin_contacto > 15:
                recomendaciones.append({
                    'prioridad': 'ALTA',
                    'icono': '📞',
                    'texto': f'Contactar urgente - {dias_sin_contacto} días sin seguimiento'
                })
            elif dias_sin_contacto > 7:
                recomendaciones.append({
                    'prioridad': 'MEDIA',
                    'icono': '📅',
                    'texto': 'Programar seguimiento próximamente'
                })
        else:
            recomendaciones.append({
                'prioridad': 'ALTA',
                'icono': '🚨',
                'texto': 'Realizar primer seguimiento'
            })
        
        # Recomendación 2: Plan de intervención
        if not legajo.plan_vigente:
            recomendaciones.append({
                'prioridad': 'ALTA',
                'icono': '📋',
                'texto': 'Crear plan de intervención'
            })
        
        # Recomendación 3: Evaluación
        try:
            evaluacion = legajo.evaluacion
            if evaluacion.riesgo_suicida or evaluacion.violencia:
                recomendaciones.append({
                    'prioridad': 'CRITICA',
                    'icono': '⚠️',
                    'texto': 'Monitoreo intensivo requerido - Riesgos identificados'
                })
        except:
            recomendaciones.append({
                'prioridad': 'MEDIA',
                'icono': '🩺',
                'texto': 'Completar evaluación inicial'
            })
        
        # Recomendación 4: Red de apoyo
        from .models_contactos import VinculoFamiliar
        vinculos = VinculoFamiliar.objects.filter(ciudadano_principal=ciudadano).count()
        
        if vinculos == 0:
            recomendaciones.append({
                'prioridad': 'MEDIA',
                'icono': '👥',
                'texto': 'Identificar y registrar red de apoyo familiar'
            })
        
        # Recomendación 5: Derivaciones pendientes
        from .models import Derivacion
        derivaciones_pendientes = Derivacion.objects.filter(
            legajo=legajo,
            estado='PENDIENTE'
        ).count()
        
        if derivaciones_pendientes > 0:
            recomendaciones.append({
                'prioridad': 'MEDIA',
                'icono': '🔄',
                'texto': f'Seguir {derivaciones_pendientes} derivación(es) pendiente(s)'
            })
        
        return recomendaciones[:5]  # Máximo 5 recomendaciones
    
    @staticmethod
    def obtener_prediccion_completa(ciudadano):
        """
        Obtiene predicción completa con todos los indicadores
        """
        riesgo_abandono = RiskPredictor.calcular_riesgo_abandono(ciudadano)
        riesgo_evento = RiskPredictor.calcular_riesgo_evento_critico(ciudadano)
        recomendaciones = RiskPredictor.generar_recomendaciones(ciudadano)
        
        return {
            'abandono': riesgo_abandono,
            'evento_critico': riesgo_evento,
            'recomendaciones': recomendaciones,
            'timestamp': timezone.now().isoformat()
        }
