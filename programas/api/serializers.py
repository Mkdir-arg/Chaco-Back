"""Serializers de la API de campo de Becas (#82)."""

import logging

from django.utils.dateparse import parse_date
from rest_framework import serializers

from legajos.models import Ciudadano
from programas.models import AdjuntoFormulario, Formulario, Relevamiento
from programas.services.becas import definicion_formulario, es_menor

logger = logging.getLogger(__name__)


class RelevamientoListSerializer(serializers.ModelSerializer):
    segmento = serializers.CharField(source="convocatoria.segmento.nombre", read_only=True)
    convocatoria_nombre = serializers.CharField(source="convocatoria.nombre", read_only=True)
    # Anotado en el queryset del viewset (evita un COUNT por ítem).
    formularios_count = serializers.IntegerField(read_only=True)

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

        datos = attrs.get("datos_identificacion")
        if datos is None and self.instance:
            datos = self.instance.datos_identificacion
        fecha_nacimiento = datos.get("fecha_nacimiento") if isinstance(datos, dict) else None
        if isinstance(fecha_nacimiento, str):
            try:
                fecha_nacimiento = parse_date(fecha_nacimiento)
            except ValueError:
                fecha_nacimiento = None
        if fecha_nacimiento is None and isinstance(datos, dict) and datos.get("dni"):
            fecha_nacimiento = (
                Ciudadano.objects.filter(dni=datos["dni"]).values_list("fecha_nacimiento", flat=True).first()
            )
        if fecha_nacimiento is None and self.instance and self.instance.ciudadano_id:
            fecha_nacimiento = self.instance.ciudadano.fecha_nacimiento

        if fecha_nacimiento is None:
            logger.warning(
                "RN-22 no pudo evaluarse: formulario sin fecha de nacimiento (dni=%s)",
                datos.get("dni") if isinstance(datos, dict) else None,
            )

        if es_menor(fecha_nacimiento):
            campos_apoderado = (
                "apoderado_nombre",
                "apoderado_apellido",
                "apoderado_fecha_nacimiento",
            )
            faltantes = [
                campo
                for campo in campos_apoderado
                if not (attrs.get(campo) if campo in attrs else getattr(self.instance, campo, None))
            ]
            if faltantes:
                raise serializers.ValidationError(
                    {campo: "Este dato es obligatorio cuando la persona relevada es menor de edad." for campo in faltantes}
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
            raise serializers.ValidationError("Se requiere exactamente uno: pregunta_global o requisito_nativo.")
        return attrs
