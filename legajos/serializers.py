from rest_framework import serializers
from django.contrib.auth.models import User
from .models import (
    Ciudadano,
    Derivacion,
    AlertaCiudadano,
)


class CiudadanoSerializer(serializers.ModelSerializer):
    """Serializer para el modelo Ciudadano"""
    legajos_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Ciudadano
        fields = [
            'id', 'dni', 'nombre', 'apellido', 'fecha_nacimiento',
            'genero', 'telefono', 'email', 'domicilio', 'activo',
            'legajos_count', 'creado', 'modificado'
        ]
        read_only_fields = ['id', 'creado', 'modificado']
    
    def get_legajos_count(self, obj):
        return getattr(obj, 'legajos_count', obj.inscripciones_programas.count())


class UserSerializer(serializers.ModelSerializer):
    """Serializer básico para User"""
    
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email']


class DerivacionSerializer(serializers.ModelSerializer):
    """Serializer para Derivacion"""
    actividad_destino_nombre = serializers.CharField(source='actividad_destino.nombre', read_only=True)
    
    class Meta:
        model = Derivacion
        fields = [
            'id', 'legajo', 'actividad_destino', 'actividad_destino_nombre', 'motivo', 'urgencia',
            'estado', 'respuesta', 'fecha_aceptacion', 'creado', 'modificado'
        ]
        read_only_fields = ['id', 'creado', 'modificado']


class AlertaCiudadanoSerializer(serializers.ModelSerializer):
    """Serializer para AlertaCiudadano"""
    ciudadano_nombre = serializers.CharField(source='ciudadano.nombre_completo', read_only=True)
    legajo_codigo = serializers.CharField(source='legajo.codigo', read_only=True)
    dispositivo_nombre = serializers.SerializerMethodField()
    cerrada_por_nombre = serializers.CharField(source='cerrada_por.get_full_name', read_only=True)

    def get_dispositivo_nombre(self, obj):
        if not obj.legajo or not obj.legajo.dispositivo:
            return None
        return obj.legajo.dispositivo.nombre
    
    class Meta:
        model = AlertaCiudadano
        fields = [
            'id', 'ciudadano', 'ciudadano_nombre', 'legajo', 'legajo_codigo',
            'dispositivo_nombre', 'tipo', 'prioridad', 'mensaje', 'activa', 
            'fecha_cierre', 'cerrada_por', 'cerrada_por_nombre', 'creado', 'modificado'
        ]
        read_only_fields = ['id', 'creado', 'modificado']


# Importar serializers de contactos
from .serializers_contactos import *