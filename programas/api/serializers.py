"""Serializers de la API de campo de Becas (#82)."""

from rest_framework import serializers

from programas.models import AdjuntoFormulario, Formulario, Relevamiento
from programas.services.becas import definicion_formulario


class RelevamientoListSerializer(serializers.ModelSerializer):
    segmento = serializers.CharField(source="convocatoria.segmento.nombre", read_only=True)
    convocatoria_nombre = serializers.CharField(source="convocatoria.nombre", read_only=True)
    formularios_count = serializers.SerializerMethodField()

    class Meta:
        model = Relevamiento
        fields = [
            "id",
            "nombre",
            "zona",
            "fecha_asignada",
            "estado",
            "segmento",
            "convocatoria_nombre",
            "fecha_finalizado",
            "formularios_count",
        ]

    def get_formularios_count(self, obj):
        return obj.formularios.count()


class RelevamientoDetailSerializer(RelevamientoListSerializer):
    definicion_formulario = serializers.SerializerMethodField()

    class Meta(RelevamientoListSerializer.Meta):
        fields = RelevamientoListSerializer.Meta.fields + ["definicion_formulario"]

    def get_definicion_formulario(self, obj):
        return definicion_formulario(obj)


class FormularioSerializer(serializers.ModelSerializer):
    ciudadano_dni = serializers.CharField(source="ciudadano.dni", read_only=True)

    class Meta:
        model = Formulario
        fields = [
            "id",
            "relevamiento",
            "estado",
            "motivo_rechazo",
            "validado_renaper",
            "ciudadano",
            "ciudadano_dni",
            "datos_identificacion",
            "celular",
            "email_contacto",
            "apoderado_nombre",
            "apoderado_apellido",
            "apoderado_fecha_nacimiento",
            "gps_lat",
            "gps_lng",
            "data",
            "creado",
            "modificado",
        ]
        read_only_fields = [
            "id",
            "relevamiento",
            "estado",
            "motivo_rechazo",
            "ciudadano",
            "ciudadano_dni",
            "creado",
            "modificado",
        ]

    def validate(self, attrs):
        # Debe poder identificarse: ciudadano (en update) o datos_identificacion.
        if not self.instance:
            datos = attrs.get("datos_identificacion")
            if not datos or not datos.get("dni"):
                raise serializers.ValidationError(
                    {"datos_identificacion": "Se requiere al menos el DNI en datos_identificacion."}
                )
        return attrs


class AdjuntoFormularioSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdjuntoFormulario
        fields = ["id", "formulario", "pregunta_global", "requisito_nativo", "archivo", "creado"]
        read_only_fields = ["id", "formulario", "creado"]

    def validate(self, attrs):
        pregunta = attrs.get("pregunta_global")
        requisito = attrs.get("requisito_nativo")
        if bool(pregunta) == bool(requisito):
            raise serializers.ValidationError(
                "Se requiere exactamente uno: pregunta_global o requisito_nativo."
            )
        return attrs
