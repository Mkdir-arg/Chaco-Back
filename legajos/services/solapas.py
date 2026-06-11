"""
Servicio para gestionar solapas dinámicas de programas
"""
import re
import unicodedata

from django.db.models import Q
from ..models_programas import DerivacionPrograma, InscripcionPrograma, Programa


class SolapasService:
    """Servicio para obtener las solapas dinámicas de un ciudadano"""
    
    # Solapas estáticas (siempre visibles)
    SOLAPAS_ESTATICAS = [
        {'id': 'resumen',          'nombre': 'Resumen',           'icono': 'gauge-high',         'orden': 0,   'estatica': True},
        {'id': 'conversaciones',   'nombre': 'Conversaciones',     'icono': 'comments',           'orden': 860, 'estatica': True},
        {'id': 'derivaciones',     'nombre': 'Derivaciones',       'icono': 'share-nodes',        'orden': 870, 'estatica': True},
        {'id': 'alertas',          'nombre': 'Alertas',            'icono': 'bell',               'orden': 880, 'estatica': True},
        {'id': 'linea_tiempo',     'nombre': 'Línea de tiempo',    'icono': 'clock-rotate-left',  'orden': 950, 'estatica': True},
        {'id': 'red_familiar',     'nombre': 'Red Familiar',       'icono': 'users',              'orden': 998, 'estatica': True},
        {'id': 'archivos',         'nombre': 'Archivos',           'icono': 'folder-open',        'orden': 999, 'estatica': True},
    ]
    
    @classmethod
    def obtener_solapas_ciudadano(cls, ciudadano):
        """
        Obtiene todas las solapas (estáticas + dinámicas) para un ciudadano
        
        Args:
            ciudadano: Instancia de Ciudadano
            
        Returns:
            Lista de diccionarios con información de cada solapa
        """
        solapas = []

        # 1. Agregar todas las solapas estáticas (copias para no mutar la lista de clase)
        for s in cls.SOLAPAS_ESTATICAS:
            solapas.append(dict(s))

        # 2. Obtener programas activos del ciudadano
        inscripciones_activas = InscripcionPrograma.objects.filter(
            ciudadano=ciudadano,
            estado__in=['ACTIVO', 'EN_SEGUIMIENTO']
        ).select_related('programa').order_by('programa__orden')

        # 3. Agregar solapas dinámicas de programas (orden 100-799)
        for inscripcion in inscripciones_activas:
            programa = inscripcion.programa
            tipo_normalizado = cls._normalizar_tipo_programa(programa.tipo)
            solapas.append({
                'id': f'programa_{tipo_normalizado}',
                'nombre': programa.nombre,
                'icono': programa.icono or 'star',
                'color': programa.color,
                'url_name': cls._obtener_url_programa(tipo_normalizado),
                'url_params': {'ciudadano_id': ciudadano.id, 'inscripcion_id': inscripcion.id},
                'orden': 100 + programa.orden,
                'estatica': False,
                'programa': programa,
                'inscripcion': inscripcion,
                'badge': cls._obtener_badge_programa(inscripcion),
            })

        # 4. Inyectar badges en solapas estáticas
        badges = cls.obtener_badges_ciudadano(ciudadano)
        solapas_final = []
        for s in solapas:
            if s['id'] in badges and 'badge' not in s:
                s = {**s, 'badge': badges[s['id']]}
            solapas_final.append(s)

        # 5. Ordenar por campo 'orden'
        solapas_final.sort(key=lambda x: x['orden'])
        return solapas_final
    
    @classmethod
    def obtener_programas_activos(cls, ciudadano):
        """
        Obtiene solo los programas activos del ciudadano
        
        Args:
            ciudadano: Instancia de Ciudadano
            
        Returns:
            QuerySet de InscripcionPrograma
        """
        return InscripcionPrograma.objects.filter(
            ciudadano=ciudadano,
            estado__in=['ACTIVO', 'EN_SEGUIMIENTO']
        ).select_related('programa').order_by('programa__orden')
    
    @classmethod
    def obtener_programas_disponibles_derivacion(cls, ciudadano, programa_origen=None):
        """
        Obtiene programas disponibles para derivación (que el ciudadano NO tiene activos)
        
        Args:
            ciudadano: Instancia de Ciudadano
            programa_origen: Programa desde el cual se deriva (opcional)
            
        Returns:
            QuerySet de Programa
        """
        # Obtener IDs de programas donde ya está inscrito
        programas_inscritos = InscripcionPrograma.objects.filter(
            ciudadano=ciudadano,
            estado__in=['ACTIVO', 'EN_SEGUIMIENTO']
        ).values_list('programa_id', flat=True)
        
        # Obtener programas activos que NO tiene
        programas_disponibles = Programa.objects.filter(
            estado='ACTIVO'
        ).exclude(
            id__in=programas_inscritos
        )
        
        # Si hay programa origen, excluirlo también
        if programa_origen:
            programas_disponibles = programas_disponibles.exclude(id=programa_origen.id)
        
        return programas_disponibles.order_by('orden', 'nombre')
    
    @classmethod
    def tiene_derivaciones_pendientes(cls, ciudadano, programa=None):
        """
        Verifica si el ciudadano tiene derivaciones pendientes
        
        Args:
            ciudadano: Instancia de Ciudadano
            programa: Programa específico (opcional)
            
        Returns:
            bool
        """
        query = Q(ciudadano=ciudadano, estado='PENDIENTE')
        
        if programa:
            query &= Q(programa_destino=programa)
        
        return DerivacionPrograma.objects.filter(query).exists()
    
    @classmethod
    def obtener_derivaciones_pendientes(cls, ciudadano):
        """
        Obtiene todas las derivaciones pendientes del ciudadano
        
        Args:
            ciudadano: Instancia de Ciudadano
            
        Returns:
            QuerySet de DerivacionPrograma
        """
        return DerivacionPrograma.objects.filter(
            ciudadano=ciudadano,
            estado='PENDIENTE'
        ).select_related(
            'programa_origen',
            'programa_destino',
            'derivado_por'
        ).order_by('-creado')
    
    @classmethod
    def obtener_badges_ciudadano(cls, ciudadano):
        """
        Calcula los badges para las solapas estáticas del hub.
        Retorna dict {tab_id: {'tipo': 'numero'|'punto', 'valor': N, 'color_hex': '#...'}}
        """
        import datetime
        from django.utils import timezone

        badges = {}

        # Alertas activas → número rojo
        alertas_count = ciudadano.alertas.filter(activa=True).count()
        if alertas_count:
            badges['alertas'] = {'tipo': 'numero', 'valor': alertas_count, 'color_hex': '#EF4444'}

        # Derivaciones pendientes → número naranja
        derivaciones_count = ciudadano.derivaciones_programas.filter(estado='PENDIENTE').count()
        if derivaciones_count:
            badges['derivaciones'] = {'tipo': 'numero', 'valor': derivaciones_count, 'color_hex': '#F97316'}

        # Mensajes no leídos del ciudadano → número violeta
        try:
            from conversaciones.models import Mensaje
            mensajes_count = Mensaje.objects.filter(
                conversacion__dni_ciudadano=ciudadano.dni,
                conversacion__estado__in=['pendiente', 'activa'],
                remitente='ciudadano',
                leido=False,
            ).count()
            if mensajes_count:
                badges['conversaciones'] = {'tipo': 'numero', 'valor': mensajes_count, 'color_hex': '#8B5CF6'}
        except Exception:
            pass

        return badges

    @classmethod
    def _obtener_url_programa(cls, tipo_programa):
        """
        Mapea el tipo de programa a su URL name
        
        Args:
            tipo_programa: Tipo del programa
            
        Returns:
            str: URL name
        """
        url_map = {
            'ACOMPANAMIENTO_SOCIAL': 'legajos:programa_detalle',
            'NACHEC': 'nachec:detalle_caso_ciudadano',
            'ECONOMICO': 'programas:economico_detalle',
            'FAMILIAR': 'programas:familiar_detalle',
        }
        return url_map.get(tipo_programa, 'legajos:programa_detalle')

    @classmethod
    def _normalizar_tipo_programa(cls, tipo_programa):
        """
        Normaliza tipos de programa para usarlos como IDs estables en tabs.
        Ej: 'ÑACHEC' o variantes con codificación rota -> 'NACHEC'
        """
        valor = (tipo_programa or "").upper().strip()

        # Compatibilidad con variantes históricas de NACHEC.
        if "NACHEC" in valor or "ÑACHEC" in valor or "ACHEC" in valor:
            return "NACHEC"

        ascii_valor = unicodedata.normalize("NFKD", valor).encode("ascii", "ignore").decode("ascii")
        ascii_valor = re.sub(r"[^A-Z0-9]+", "_", ascii_valor).strip("_")
        return ascii_valor or "PROGRAMA"
    
    @classmethod
    def _obtener_badge_programa(cls, inscripcion):
        """
        Badge de la solapa de un programa. Usa la misma forma que los badges
        de solapas estáticas: {'tipo': 'numero'|'punto', 'valor': N,
        'color_hex': '#...', 'title': '...'} o None.
        """
        from django.utils import timezone

        if inscripcion.estado == 'PENDIENTE':
            return {
                'tipo': 'punto',
                'color_hex': '#F59E0B',
                'title': 'Inscripción pendiente',
            }

        # Inscripción en seguimiento sin actividad hace más de 30 días
        modificado = getattr(inscripcion, 'modificado', None)
        if inscripcion.estado == 'EN_SEGUIMIENTO' and modificado:
            dias = (timezone.now() - modificado).days
            if dias > 30:
                return {
                    'tipo': 'punto',
                    'color_hex': '#F97316',
                    'title': f'Sin actividad hace {dias} días',
                }

        return None
    
    @classmethod
    def crear_inscripcion_directa(cls, ciudadano, programa, responsable, notas=''):
        """
        Crea una inscripción directa a un programa (sin derivación)
        
        Args:
            ciudadano: Instancia de Ciudadano
            programa: Instancia de Programa
            responsable: Usuario responsable
            notas: Notas adicionales
            
        Returns:
            InscripcionPrograma
        """
        # Verificar que no exista inscripción activa
        existe = InscripcionPrograma.objects.filter(
            ciudadano=ciudadano,
            programa=programa,
            estado__in=['ACTIVO', 'EN_SEGUIMIENTO']
        ).exists()
        
        if existe:
            raise ValueError(f"El ciudadano ya tiene una inscripción activa en {programa.nombre}")
        
        inscripcion = InscripcionPrograma.objects.create(
            ciudadano=ciudadano,
            programa=programa,
            via_ingreso='DIRECTO',
            estado='ACTIVO',
            responsable=responsable,
            notas=notas
        )
        
        return inscripcion
    
    @classmethod
    def obtener_historial_programas(cls, ciudadano):
        """
        Obtiene el historial completo de programas del ciudadano (activos + cerrados)
        
        Args:
            ciudadano: Instancia de Ciudadano
            
        Returns:
            QuerySet de InscripcionPrograma
        """
        return InscripcionPrograma.objects.filter(
            ciudadano=ciudadano
        ).select_related('programa', 'responsable').order_by('-fecha_inscripcion')
    
    @classmethod
    def cerrar_inscripcion(cls, inscripcion, motivo_cierre, usuario):
        """
        Cierra una inscripción a un programa
        
        Args:
            inscripcion: InscripcionPrograma
            motivo_cierre: Motivo del cierre
            usuario: Usuario que cierra
        """
        from django.utils import timezone
        
        if inscripcion.estado == 'CERRADO':
            raise ValueError("La inscripción ya está cerrada")
        
        inscripcion.estado = 'CERRADO'
        inscripcion.fecha_cierre = timezone.now().date()
        inscripcion.motivo_cierre = motivo_cierre
        
        # Agregar nota de cierre
        nota_cierre = f"\n\n[{timezone.now().strftime('%d/%m/%Y %H:%M')}] Cerrado por {usuario.get_full_name() or usuario.username}\nMotivo: {motivo_cierre}"
        inscripcion.notas += nota_cierre
        
        inscripcion.save()
