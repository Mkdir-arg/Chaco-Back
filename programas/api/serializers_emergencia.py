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

import re
from pathlib import Path

from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import serializers
from rest_framework.fields import empty
from rest_framework.utils import html

from core.validators import ADJUNTO_MAX_BYTES, MENSAJE_ADJUNTO_TAMANIO, firma_coincide
from programas.models import AdjuntoCaso, CasoEmergencia, Derivacion, EntregaKit, GrupoFamiliar, LineaEntrega
from programas.services.emergencia import NECESIDADES
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


# ---------------------------------------------------------------------------
# M3 · Recepción de kits
# ---------------------------------------------------------------------------

#: Cómo viaja la cantidad de cada ítem en el multipart de la recepción: `cantidades[<id del ítem>]`.
CLAVE_DE_CANTIDAD = re.compile(r"^cantidades\[(\d+)\]$")
MENSAJE_SIN_CANTIDADES = "Indicá cuánto llegó de cada ítem: un campo `cantidades[<id del ítem>]` por línea."
MENSAJE_CANTIDADES_INVALIDAS = "La cantidad de cada ítem tiene que ser un número entero, cero o más."


class MiDispositivoEmergenciaSerializer(serializers.Serializer):
    """Un dispositivo donde el usuario es de la guardia de Emergencia (RU-5)."""

    id = serializers.IntegerField()
    nombre = serializers.CharField()
    entregas_pendientes = serializers.IntegerField(
        help_text="Entregas de kits que el usuario puede recibir ahí (en camino o preparadas). 0 si solo admite."
    )
    plazas_libres = serializers.IntegerField(
        help_text="Camas libres ahora (PR 8). 0 donde el usuario solo recibe kits y no admite familias."
    )
    derivaciones_pendientes = serializers.IntegerField(
        help_text="Derivaciones por aceptar o rechazar (PR 8). 0 donde el usuario solo recibe kits."
    )


class LineaEntregaKitSerializer(serializers.ModelSerializer):
    """Un ítem de la entrega: lo enviado y, cuando ya se recibió, lo recibido."""

    item = serializers.IntegerField(source="item_id", read_only=True, help_text="`id` del ítem del catálogo.")
    nombre = serializers.CharField(source="item.nombre", read_only=True)
    enviada = serializers.IntegerField(source="cantidad_enviada", read_only=True)
    recibida = serializers.IntegerField(
        source="cantidad_recibida", read_only=True, allow_null=True, help_text="`null` hasta que se recibe."
    )

    class Meta:
        model = LineaEntrega
        fields = ["item", "nombre", "unidad", "enviada", "recibida"]
        read_only_fields = fields


class EntregaKitSerializer(serializers.ModelSerializer):
    """Una entrega de kits como la ve la guardia: la misma forma en la lista y en el detalle."""

    lineas = LineaEntregaKitSerializer(many=True, read_only=True)

    class Meta:
        model = EntregaKit
        fields = [
            "id",
            "numero",
            "estado",
            "despachada_en",
            "recibida_en",
            "observacion_mesa",
            "observacion_dispositivo",
            "lineas",
        ]
        read_only_fields = fields


class _CantidadesField(serializers.DictField):
    """``{"<id del ítem>": cantidad}``. En multipart, un campo ``cantidades[<id>]`` por ítem."""

    def get_value(self, dictionary):
        if html.is_html_input(dictionary):
            cantidades = {}
            for clave in dictionary:
                coincide = CLAVE_DE_CANTIDAD.match(clave)
                if coincide:
                    cantidades[coincide.group(1)] = dictionary.get(clave)
            return cantidades or empty
        return super().get_value(dictionary)

    def run_child_validation(self, data):
        # Un solo mensaje para el campo, no un dict de errores por ítem: el 400 de la app es
        # una lista de mensajes por clave.
        try:
            return super().run_child_validation(data)
        except serializers.ValidationError:
            raise serializers.ValidationError(MENSAJE_CANTIDADES_INVALIDAS) from None


class RecepcionKitEnvioSerializer(serializers.Serializer):
    """Cuerpo multipart de ``POST /api/emergencia/entregas/{id}/recibir/``.

    Acá solo se mira **la forma** (que el identificador sea un UUID, que las cantidades sean
    enteros). Las reglas —una cantidad por cada línea, el remito obligatorio en JPEG de hasta
    5 MB, el estado de la entrega, el alcance— son de ``recibir_entrega``, la misma función
    que usa la recepción web (RU-2): por eso el remito no es obligatorio en este nivel.
    """

    uuid_cliente = serializers.UUIDField(
        help_text="Identificador de la recepción, generado en el celular. Reenviarlo no la repite."
    )
    cantidades = _CantidadesField(
        child=serializers.IntegerField(min_value=0),
        error_messages={"required": MENSAJE_SIN_CANTIDADES},
        help_text=(
            "Cuánto llegó de **cada** ítem de la entrega, aunque sea 0. En multipart, un campo "
            "`cantidades[<id del ítem>]` por línea (p. ej. `cantidades[12]=8`)."
        ),
    )
    remito = serializers.FileField(
        required=False,
        allow_null=True,
        default=None,
        help_text="Obligatorio. Foto del remito en JPEG, hasta 5 MB. HEIC/HEIF se convierten en la app.",
    )
    observacion = _texto(help_text="Lo que la mesa tiene que saber de esta entrega. Opcional.")

    def cantidades_por_item(self):
        """``{item_id: cantidad}`` con las claves como enteros: lo que recibe ``recibir_entrega``."""
        return {int(item_id): cantidad for item_id, cantidad in self.validated_data["cantidades"].items()}


class DiferenciaDeRecepcionSerializer(serializers.Serializer):
    item = serializers.IntegerField(help_text="`id` del ítem del catálogo.")
    enviada = serializers.IntegerField()
    recibida = serializers.IntegerField()


class RecepcionKitRespuestaSerializer(serializers.Serializer):
    """«Recibida · 2 ítems con diferencia» (M3-2): el estado final y lo que difirió."""

    estado = serializers.ChoiceField(
        choices=EntregaKit.Estado.choices, help_text="`RECIBIDA` o `RECIBIDA_CON_DIFERENCIAS`."
    )
    diferencias = DiferenciaDeRecepcionSerializer(
        many=True, help_text="Las líneas con `recibida` distinta de `enviada`. Vacía si llegó completa."
    )


class EstadoCambioSerializer(serializers.Serializer):
    """El 409 de una pantalla que quedó vieja: qué pasó y en qué estado quedó el recurso."""

    detail = serializers.CharField()
    estado_actual = serializers.CharField()


# ---------------------------------------------------------------------------
# M2 · Llegada de familias (PR 8)
# ---------------------------------------------------------------------------
#
# Mismo criterio que el resto del archivo: acá solo se mira **la forma** del cuerpo (que el
# identificador sea un UUID, que la ficha sea un objeto). Las reglas —el mínimo de la ficha, la
# cama, los motivos, el estado del caso, el alcance— son de ``services.emergencia_alojar``, la
# misma capa que usa la pantalla E6 del backoffice (RU-2): por eso los motivos son texto libre
# para el serializer y un código inválido lo rechaza el servicio, con su mensaje.
#
# Los estados van como texto con sus valores en ``help_text`` y no como ``ChoiceField``: varios
# campos se llaman ``estado`` con conjuntos distintos, y Spectacular avisaría el choque de
# nombres de enum (``--fail-on-warn``).


class CasoResumenSerializer(serializers.ModelSerializer):
    """El caso en una línea: lo que la app necesita para el encabezado de M2-2 a M2-5."""

    total_declarado = serializers.IntegerField(source="grupo.total_declarado", read_only=True)

    class Meta:
        model = CasoEmergencia
        fields = ["id", "numero", "estado", "prioridad", "total_declarado"]
        read_only_fields = fields


class PersonaDelIntegranteSerializer(serializers.Serializer):
    id = serializers.IntegerField(help_text="`id` del legajo.")
    nombre = serializers.CharField(help_text="«Apellido, Nombre».")
    dni = serializers.CharField()


class PlazaDelIntegranteSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    codigo = serializers.CharField()
    nombre = serializers.CharField(help_text="Código con el sector: «B-12 (Pabellón B)».")


class IntegranteSerializer(serializers.Serializer):
    """Una fila de M2-3 («Persona 3 · sin confirmar» o «Pérez, Juan · cama B-12 · ficha incompleta»)."""

    n = serializers.IntegerField(help_text="Número de la persona en la familia (1 a `total_declarado`). Va en la URL.")
    estado = serializers.CharField(help_text="`SIN_CONFIRMAR`, `CONFIRMADA` o `EGRESADA`.")
    ficha_completa = serializers.BooleanField(help_text="Secciones 4 a 8 con algún dato o «sin datos».")
    persona = PersonaDelIntegranteSerializer(allow_null=True, help_text="`null` hasta que se confirma.")
    plaza = PlazaDelIntegranteSerializer(allow_null=True, help_text="La cama de **hoy**; `null` sin confirmar.")
    parentesco = serializers.CharField(help_text="Rótulo del parentesco; vacío sin confirmar.")
    confirmada_en = serializers.DateTimeField(allow_null=True)
    egresado_en = serializers.DateTimeField(allow_null=True)


class IntegranteDetalleSerializer(IntegranteSerializer):
    """Una fila con su ficha guardada: lo que la app precarga para completar las secciones 4 a 8."""

    ficha = serializers.DictField(help_text="El Formulario 2 tal como se guardó (contrato, «La ficha»).")
    secciones_incompletas = serializers.ListField(
        child=serializers.CharField(), help_text="Rótulos de las secciones 4 a 8 que faltan, en orden."
    )


class IntegrantesDelCasoSerializer(serializers.Serializer):
    """M2-3: las N filas de la familia con el contador."""

    caso = CasoResumenSerializer()
    integrantes = IntegranteSerializer(many=True)
    confirmadas = serializers.IntegerField(help_text="El «3» de «3 de 7 confirmadas».")
    total_declarado = serializers.IntegerField(help_text="Filas de la familia: crece con «Agregar persona».")
    declaradas_al_relevar = serializers.IntegerField(help_text="Lo que dijo el Formulario 1 («llegaron 8 sobre 7»).")
    con_ficha_incompleta = serializers.IntegerField()


class ResponsableSerializer(serializers.Serializer):
    nombre = serializers.CharField()
    apellido = serializers.CharField()
    dni = serializers.CharField()


class GrupoDeLaDerivacionSerializer(serializers.ModelSerializer):
    """La tabla del paso 2 del Formulario 1: personas por franja y asistencia."""

    class Meta:
        model = GrupoFamiliar
        fields = [
            "menores_f",
            "menores_m",
            "adultos_f",
            "adultos_m",
            "mayores_f",
            "mayores_m",
            "dependientes",
            "mayores_dependientes",
            "lactantes",
        ]
        read_only_fields = fields


class DerivacionLlegadaSerializer(serializers.ModelSerializer):
    """La tarjeta de M2-2. Solo sale si la derivación es hacia el dispositivo de quien busca (RU-9)."""

    estado = serializers.CharField(read_only=True, help_text="`PENDIENTE` (por aceptar) o `ACEPTADA` (en curso).")
    vencida = serializers.SerializerMethodField(
        help_text="Pendiente con `vence_en` pasado: se puede aceptar igual mientras la mesa no la marque vencida."
    )
    derivada_en = serializers.DateTimeField(source="creado", read_only=True)
    derivada_por = serializers.SerializerMethodField(help_text="Nombre de quien derivó en la mesa.")
    caso = CasoResumenSerializer(read_only=True)
    responsable = ResponsableSerializer(source="caso.grupo.responsable", read_only=True)
    grupo = GrupoDeLaDerivacionSerializer(source="caso.grupo", read_only=True)
    necesidades = serializers.SerializerMethodField(
        help_text="Las que marcó el Formulario 1: `embarazo`, `electrodependiente`, `medicacion_critica`, `mascotas`."
    )
    telefono = serializers.SerializerMethodField()
    observaciones = serializers.SerializerMethodField()

    class Meta:
        model = Derivacion
        fields = [
            "id",
            "estado",
            "plazas_pedidas",
            "vence_en",
            "vencida",
            "derivada_en",
            "derivada_por",
            "caso",
            "responsable",
            "grupo",
            "necesidades",
            "telefono",
            "observaciones",
        ]
        read_only_fields = fields

    def get_vencida(self, derivacion) -> bool:
        return derivacion.estado == Derivacion.Estado.PENDIENTE and derivacion.vence_en < timezone.now()

    def get_derivada_por(self, derivacion) -> str:
        usuario = derivacion.derivada_por
        if usuario is None:
            return ""
        return usuario.get_full_name().strip() or usuario.get_username()

    def get_necesidades(self, derivacion) -> list[str]:
        return [clave for clave in NECESIDADES if derivacion.caso.necesidades.get(clave)]

    def get_telefono(self, derivacion) -> str:
        return derivacion.caso.situacion.get("telefono", "")

    def get_observaciones(self, derivacion) -> str:
        return derivacion.caso.situacion.get("observaciones", "")


class BusquedaPorDniSerializer(serializers.Serializer):
    """M2-1: lo que contesta ``…/buscar/?dni=`` (03 §7). Las claves vienen **siempre**; las que no aplican, ``null``."""

    resultado = serializers.CharField(help_text="`DERIVACION`, `SIN_DERIVACION` o `ALOJADA`.")
    dni = serializers.CharField(help_text="El DNI buscado, solo dígitos.")
    plazas_libres = serializers.IntegerField(help_text="Camas libres del dispositivo ahora: decide «Ingresar igual».")
    mensaje = serializers.CharField(help_text="El texto para la pantalla. Nunca nombra un dispositivo ajeno.")
    derivacion = DerivacionLlegadaSerializer(allow_null=True, help_text="Solo con `DERIVACION`.")
    alojada_aca = serializers.BooleanField(allow_null=True, help_text="Solo con `ALOJADA`: ¿en este dispositivo?")
    alojada_en = serializers.CharField(
        help_text="Solo con `ALOJADA` y si quien busca lo puede ver: el nombre del dispositivo. Si no, vacío."
    )
    alojada_desde = serializers.DateTimeField(allow_null=True)


class AceptarDerivacionEnvioSerializer(serializers.Serializer):
    uuid_cliente = serializers.UUIDField(
        required=False,
        allow_null=True,
        default=None,
        help_text=(
            "Identificador del toque, generado en el celular. Se acepta y no se guarda: aceptar no es idempotente; "
            "un reintento contesta 409 con `estado_actual: INGRESO_EN_CURSO` y la app sigue a los integrantes."
        ),
    )


class AceptacionSerializer(serializers.Serializer):
    caso = CasoResumenSerializer()
    reservadas = serializers.IntegerField(help_text="Camas reservadas para la familia.")
    faltantes = serializers.IntegerField(help_text="Las que faltaron para llegar a las pedidas. 0 si alcanzó.")
    mensaje = serializers.CharField(help_text="«Reservé 5 de 7 · faltan 2 camas».")
    integrantes = IntegranteSerializer(many=True)


class RechazarDerivacionEnvioSerializer(serializers.Serializer):
    motivo = _texto(help_text="Obligatorio: `SIN_PLAZAS`, `NO_CUMPLE_PERFIL`, `NO_LLEGO` u `OTRO`.")
    observacion = _texto(help_text="Obligatoria con `OTRO`.")


class RechazoSerializer(serializers.Serializer):
    caso_estado = serializers.CharField(help_text="`EN_GESTION`: el caso volvió a la mesa.")


class ConfirmarIntegranteEnvioSerializer(serializers.Serializer):
    uuid_cliente = serializers.UUIDField(
        help_text="Identificador de la confirmación, generado en el celular. Reenviarlo devuelve la misma fila."
    )
    ficha = serializers.DictField(
        required=False, default=dict, help_text="El Formulario 2: el mínimo (secciones 1 a 3) y, si se quiere, 4 a 8."
    )
    plaza_id = serializers.IntegerField(
        required=False, allow_null=True, default=None, help_text="`id` de una cama elegible de `…/plazas/?caso=`."
    )


class ConfirmacionSerializer(serializers.Serializer):
    integrante = IntegranteSerializer()
    confirmadas = serializers.IntegerField()
    total_declarado = serializers.IntegerField()
    reserva_liberada = serializers.BooleanField(
        help_text="La persona entró en una cama libre y se devolvió una reserva de la familia que ya sobraba."
    )


class CompletarFichaEnvioSerializer(serializers.Serializer):
    ficha = serializers.DictField(
        help_text=(
            "Las secciones 4 a 8 que se cargan (`educacion`, `vacunacion`, `salud`, `trabajo`, `observaciones`). "
            "Cada una que viene reemplaza a la guardada; las del mínimo no se cambian."
        )
    )


class FichaCompletadaSerializer(serializers.Serializer):
    ficha_completa = serializers.BooleanField()
    secciones_incompletas = serializers.ListField(child=serializers.CharField())


class AgregarIntegranteEnvioSerializer(serializers.Serializer):
    uuid_cliente = serializers.UUIDField(
        help_text="Identificador del alta, generado en el celular. Reenviarlo devuelve la misma fila, sin sumar otra."
    )


class IntegranteAgregadoSerializer(serializers.Serializer):
    integrante = IntegranteSerializer()
    total_declarado = serializers.IntegerField()


class AlojarFamiliaEnvioSerializer(serializers.Serializer):
    """La sección 4 del Formulario 1 (M2-5)."""

    sector = serializers.IntegerField(
        required=False, allow_null=True, default=None, help_text="`id` de un sector del dispositivo (`…/plazas/`)."
    )
    aula = _texto(help_text="Aula o dormitorio. Hasta 80 caracteres.")
    tarjeta_entregada = _aviso()
    tarjeta_numero = _texto(help_text="Obligatorio si `tarjeta_entregada`. Hasta 40 caracteres.")
    encargado = _texto(help_text="Quién recibe. Vacío: el usuario.")


class CerrarConDiferenciaEnvioSerializer(serializers.Serializer):
    motivo = _texto(help_text="Obligatorio: `QUEDO_CON_FAMILIARES`, `NO_LLEGO`, `DERIVADO_A_SALUD` u `OTRO`.")
    observacion = _texto(help_text="Obligatoria con `OTRO`.")


class CancelarIngresoEnvioSerializer(serializers.Serializer):
    motivo = _texto(help_text="Obligatorio, hasta 200 caracteres.")


class CierreDeIngresoSerializer(serializers.Serializer):
    """Cómo quedó el caso después de alojar, cerrar con diferencia o cancelar el ingreso."""

    estado = serializers.CharField(
        help_text="`ALOJADO` (alojar, diferencia), `CERRADO` si ya no quedaba nadie, `EN_GESTION` o `NUEVO` (cancelar)."
    )
    total_alojado = serializers.IntegerField(allow_null=True)
    liberadas = serializers.IntegerField(help_text="Reservas de la familia que quedaron libres.")


class SectorDelMapaSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nombre = serializers.CharField()
    perfil = serializers.CharField()


class PlazaDelMapaSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    codigo = serializers.CharField()
    nombre = serializers.CharField()
    estado = serializers.CharField(
        help_text=(
            "`LIBRE`, `RESERVADA_FAMILIA` (guardada para esta familia), `OCUPADA`, `FUERA_SERVICIO` o `RESERVADA` "
            "(para otra persona o familia)."
        )
    )
    elegible = serializers.BooleanField(help_text="`LIBRE` o `RESERVADA_FAMILIA`: lo único que hay que mirar.")
    texto = serializers.CharField(help_text="Texto del estado (la app lo puede ignorar).")
    tono = serializers.CharField(help_text="Tono del backoffice (la app lo puede ignorar).")
    detalle = serializers.CharField(help_text="Motivo de la fuera de servicio u ocupante (con `ciudadano.ver`).")


class SectorConPlazasSerializer(serializers.Serializer):
    sector = SectorDelMapaSerializer()
    plazas = PlazaDelMapaSerializer(many=True, help_text="A lo sumo 200 por sector, por código.")
    total = serializers.IntegerField()
    libres = serializers.IntegerField()
    reservadas_familia = serializers.IntegerField()


class MapaDePlazasSerializer(serializers.Serializer):
    caso = serializers.IntegerField(allow_null=True, help_text="El `?caso=` pedido, o `null`.")
    sectores = SectorConPlazasSerializer(many=True)


class IngresoDirectoEnvioSerializer(CasoEmergenciaEnvioSerializer):
    """Cuerpo multipart de ``…/ingreso-directo/`` y ``…/avisar-mesa/``: el Formulario 1 en la puerta.

    El de M1 sin ``relevado_en`` (la familia está en la puerta: vale la hora del servidor). La
    dirección y la localidad son opcionales: sin ellas van las del dispositivo (RN-3.10).
    """

    relevado_en = None
    direccion = _texto(help_text="Opcional: sin ella va el domicilio del dispositivo. Hasta 240 caracteres.")

    def datos_formulario1(self):
        datos = dict(self.validated_data)
        datos.pop("uuid_cliente")
        datos["fotos"] = {}
        for campo, tipo in FOTOS_DEL_CASO.items():
            archivo = datos.pop(campo, None)
            if archivo:
                datos["fotos"][tipo] = archivo
        return datos


class IngresoDirectoSerializer(serializers.Serializer):
    caso = CasoResumenSerializer()
    reservadas = serializers.IntegerField()
    faltantes = serializers.IntegerField()
    integrantes = IntegranteSerializer(many=True)


class AvisoALaMesaSerializer(serializers.Serializer):
    caso = CasoResumenSerializer()
