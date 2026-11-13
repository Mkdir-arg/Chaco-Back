"""Serializers de la API de campo del módulo Emergencia (etapa 1: Formulario 1).

Lo que lee y manda la app (`Chaco-mobile`). Agregar una clave es seguro; renombrarla o
sacarla es un release coordinado de la app: las claves de cada respuesta están fijadas en
`programas/tests/test_emergencia_api_contrato.py` y documentadas en
`docs/internal/contrato-app-emergencia.md`.

**Qué valida este archivo y qué no.** Las reglas del Formulario 1 —total, RN-1.3, dirección
obligatoria, DNI, localidad— son de `programas.services.emergencia.crear_caso`, que es la
misma función que usa la mesa (RU-2). Acá solo se **traduce el multipart**: un `"false"` de
formulario a booleano, un `"3"` a entero, una fecha ISO a `datetime`. Por eso casi todo es
opcional para el serializer, y no hay topes ni mínimos: lo que falta, lo negativo o lo largo
lo dice el servicio (o el ``full_clean`` del modelo), con el mismo mensaje que en el
backoffice y junto con los demás errores. Las dos reglas propias del canal sí están acá: las fotos de la app son
**JPEG** (RN-1.9; el modelo admite además PNG y WEBP, que es lo que sube la mesa) y la hora
del teléfono no puede ser del futuro (`emergencia_campo.acotar_relevado_en`).
"""

from pathlib import Path

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from core.validators import ADJUNTO_MAX_BYTES, MENSAJE_ADJUNTO_TAMANIO, firma_coincide
from programas.models import AdjuntoCaso, CasoEmergencia, GrupoFamiliar
from programas.services.emergencia_campo import acotar_relevado_en

FOTO_EXTENSIONES_APP = (".jpg", ".jpeg")
MENSAJE_FOTO_JPEG = "La foto tiene que llegar en JPEG. La app convierte y comprime antes de enviar."

#: Campo del multipart → tipo de `AdjuntoCaso`. A lo sumo una foto de cada una.
FOTOS_DEL_CASO = {
    "foto_vivienda": AdjuntoCaso.Tipo.VIVIENDA,
    "foto_acceso": AdjuntoCaso.Tipo.ACCESO,
}

_TRASLADOS = ", ".join(f"`{codigo}`" for codigo in GrupoFamiliar.Traslado.values)


def validar_foto_de_la_app(archivo):
    """JPEG de verdad y hasta 5 MB (RN-1.9). Más angosto que `core.validators.validar_foto`.

    El modelo vuelve a validar el archivo con `validar_foto` al guardarlo: esto no lo
    reemplaza, lo recorta al único formato que produce la app.
    """
    extension = Path((getattr(archivo, "name", "") or "").lower()).suffix
    if extension not in FOTO_EXTENSIONES_APP or not firma_coincide(archivo, extension):
        raise serializers.ValidationError(MENSAJE_FOTO_JPEG)
    if (getattr(archivo, "size", 0) or 0) > ADJUNTO_MAX_BYTES:
        raise serializers.ValidationError(MENSAJE_ADJUNTO_TAMANIO)
    return archivo


def _texto(**kwargs):
    return serializers.CharField(required=False, allow_blank=True, default="", **kwargs)


def _cantidad(**kwargs):
    return serializers.IntegerField(required=False, default=0, **kwargs)


def _aviso(**kwargs):
    return serializers.BooleanField(required=False, default=False, **kwargs)


class CasoEmergenciaEnvioSerializer(serializers.Serializer):
    """Cuerpo multipart de ``POST /api/emergencia/casos/``: el Formulario 1 completo.

    Cualquier otra clave se ignora, incluidos un ``total`` o una ``prioridad`` que mande la
    app: los dos los calcula el servidor (RN-1.2, RN-1.4).
    """

    uuid_cliente = serializers.UUIDField(
        help_text="Identificador del envío, generado en el celular. Reenviarlo no crea otro caso."
    )
    relevado_en = serializers.DateTimeField(
        required=False,
        allow_null=True,
        default=None,
        help_text=(
            "Hora del teléfono al tocar «Enviar» (ISO 8601 con zona). Es la única hora del cliente que se "
            "guarda. Sin ella vale la del servidor; adelantada más de un día, 400."
        ),
    )

    # Paso 1 · traslado y responsable
    traslado = _texto(help_text=f"Obligatorio. Fuerza que traslada: {_TRASLADOS}.")
    traslado_otro = _texto(help_text="Obligatorio si `traslado` es `OTRA`.")
    dni = _texto(help_text="Obligatorio. DNI del responsable; se queda solo con los dígitos.")
    nombre = _texto(help_text="Obligatorio si la persona no está en el legajo (alta mínima).")
    apellido = _texto(help_text="Obligatorio si la persona no está en el legajo (alta mínima).")
    fecha_nacimiento = serializers.DateField(required=False, allow_null=True, default=None)
    telefono = _texto()
    documento_extraviado = _aviso(help_text="Perdió el documento pero sabe el número.")

    # Paso 2 · personas que ingresan juntas (el responsable está incluido)
    menores_f = _cantidad()
    menores_m = _cantidad()
    adultos_f = _cantidad()
    adultos_m = _cantidad()
    mayores_f = _cantidad()
    mayores_m = _cantidad()

    # Paso 3 · necesitan asistencia
    dependientes = _cantidad(help_text="No puede superar el total.")
    mayores_dependientes = _cantidad(help_text="No puede superar los mayores.")
    lactantes = _cantidad(help_text="No puede superar los menores.")
    embarazo = _aviso()
    electrodependiente = _aviso()
    medicacion_critica = _aviso()
    mascotas = _aviso()

    # Paso 4 · ubicación y fotos
    direccion = _texto(help_text="Obligatoria: calle y número, o una referencia. Hasta 240 caracteres.")
    localidad = serializers.IntegerField(
        required=False, allow_null=True, default=None, help_text="`id` de `GET /api/emergencia/localidades/`."
    )
    latitud = serializers.FloatField(required=False, allow_null=True, default=None)
    longitud = serializers.FloatField(required=False, allow_null=True, default=None)
    precision_m = serializers.FloatField(
        required=False, allow_null=True, default=None, help_text="Precisión del GPS en metros."
    )
    observaciones = _texto()
    foto_vivienda = serializers.FileField(
        required=False,
        allow_null=True,
        default=None,
        validators=[validar_foto_de_la_app],
        help_text="JPEG, hasta 5 MB. HEIC/HEIF se convierten en la app.",
    )
    foto_acceso = serializers.FileField(
        required=False,
        allow_null=True,
        default=None,
        validators=[validar_foto_de_la_app],
        help_text="JPEG, hasta 5 MB. HEIC/HEIF se convierten en la app.",
    )

    def validate_relevado_en(self, valor):
        try:
            return acotar_relevado_en(valor)
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.message_dict["relevado_en"]) from None

    def datos_formulario1(self):
        """Lo validado, con la forma que espera ``crear_caso`` (``fotos`` por tipo)."""
        datos = dict(self.validated_data)
        datos.pop("uuid_cliente")
        datos.pop("relevado_en")
        datos["fotos"] = {}
        for campo, tipo in FOTOS_DEL_CASO.items():
            archivo = datos.pop(campo, None)
            if archivo:
                datos["fotos"][tipo] = archivo
        return datos


class CasoEmergenciaCreadoSerializer(serializers.ModelSerializer):
    """Lo que la app necesita para mostrar «Enviado · 7 personas · Caso N.° 2026-000184»."""

    total_declarado = serializers.IntegerField(source="grupo.total_declarado", read_only=True)

    class Meta:
        model = CasoEmergencia
        fields = ["id", "numero", "prioridad", "total_declarado"]
        read_only_fields = fields


class MiCasoEmergenciaSerializer(serializers.ModelSerializer):
    """Una fila de «Mis envíos»: cómo sigue el caso que mandó el agente."""

    total_declarado = serializers.IntegerField(source="grupo.total_declarado", read_only=True)
    creado_en = serializers.DateTimeField(source="creado", read_only=True, help_text="Cuándo lo recibió el servidor.")

    class Meta:
        model = CasoEmergencia
        fields = ["numero", "estado", "total_declarado", "creado_en"]
        read_only_fields = fields


class LocalidadEmergenciaSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nombre = serializers.CharField()


class PerfilEmergenciaSerializer(serializers.Serializer):
    """Qué accesos muestra la pantalla inicial del módulo (RU-5)."""

    relevar = serializers.BooleanField(help_text="Agente territorial: «Ingreso de familias» (M1).")
    dispositivo = serializers.BooleanField(
        help_text="Guardia de un dispositivo: «Llegada de familias» (M2) y «Recepción de kits» (M3)."
    )
