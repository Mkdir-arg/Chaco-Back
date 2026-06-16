from rest_framework import serializers
from django.contrib.auth.models import User
from .models.contactos import (
    HistorialContacto,
    VinculoFamiliar,
)
from .models import Ciudadano, LegajoAtencion


class CiudadanoBasicoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ciudadano
        fields = ['id', 'dni', 'nombre', 'apellido', 'telefono']


class HistorialContactoSerializer(serializers.ModelSerializer):
    profesional_nombre = serializers.CharField(source='profesional.get_full_name', read_only=True)
    ciudadano_nombre = serializers.SerializerMethodField()
    duracion_formateada = serializers.CharField(read_only=True)

    def get_ciudadano_nombre(self, obj):
        ciudadano = getattr(obj.legajo, 'ciudadano', None)
        return str(ciudadano) if ciudadano else ''
    
    class Meta:
        model = HistorialContacto
        fields = '__all__'
        read_only_fields = ('creado', 'modificado')
    
    def validate_fecha_contacto(self, value):
        from datetime import datetime
        if value > datetime.now():
            raise serializers.ValidationError("La fecha de contacto no puede ser futura")
        return value


class VinculoFamiliarSerializer(serializers.ModelSerializer):
    ciudadano_principal_nombre = serializers.CharField(source='ciudadano_principal.__str__', read_only=True)
    ciudadano_vinculado_nombre = serializers.CharField(source='ciudadano_vinculado.__str__', read_only=True)
    ciudadano_vinculado_detail = CiudadanoBasicoSerializer(source='ciudadano_vinculado', read_only=True)
    tipo_vinculo_display = serializers.CharField(source='get_tipo_vinculo_display', read_only=True)
    
    class Meta:
        model = VinculoFamiliar
        fields = '__all__'
        read_only_fields = ('creado', 'modificado')
    
    def validate(self, data):
        if data['ciudadano_principal'] == data['ciudadano_vinculado']:
            raise serializers.ValidationError("Un ciudadano no puede vincularse consigo mismo")
        return data


# Serializers para listados y búsquedas
class HistorialContactoListSerializer(serializers.ModelSerializer):
    profesional_nombre = serializers.CharField(source='profesional.get_full_name', read_only=True)
    tipo_contacto_display = serializers.CharField(source='get_tipo_contacto_display', read_only=True)
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    
    class Meta:
        model = HistorialContacto
        fields = [
            'id', 'fecha_contacto', 'tipo_contacto', 'tipo_contacto_display',
            'estado', 'estado_display', 'motivo', 'profesional_nombre',
            'duracion_minutos', 'seguimiento_requerido'
        ]


class UserBasicoSerializer(serializers.ModelSerializer):
    nombre_completo = serializers.CharField(source='get_full_name', read_only=True)
    
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'nombre_completo']