"""Serializers de la API de campo del módulo Emergencia (etapa 1: Formulario 1).

Lo que lee y manda la app (`Chaco-mobile`). Agregar una clave es seguro; renombrarla o
sacarla es un release coordinado de la app: las claves de cada respuesta están fijadas en
`programas/tests/base_emergencia_api.py` y documentadas en
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
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from core.validators import ADJUNTO_MAX_BYTES, MENSAJE_ADJUNTO_TAMANIO, firma_coincide
from programas.models import AdjuntoCaso, CasoEmergencia, Derivacion, GrupoFamiliar
from programas.selectors.emergencia_mesa import nombre_de
from programas.services.avisos_emergencia import por_vencer
from programas.services.emergencia import NECESIDADES
from programas.services.emergencia_campo import acotar_relevado_en
from programas.services.emergencia_ingreso_comun import derivacion_vencida

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


def texto(**kwargs):
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
    traslado = texto(help_text=f"Obligatorio. Fuerza que traslada: {_TRASLADOS}.")
    traslado_otro = texto(help_text="Obligatorio si `traslado` es `OTRA`.")
    dni = texto(help_text="Obligatorio. DNI del responsable; se queda solo con los dígitos.")
    nombre = texto(
        help_text=(
            "Obligatorio si la persona no está en el legajo (alta mínima). Si está, se omite, coincide con el "
            "legajo o va con `identidad_en_conflicto`."
        )
    )
    apellido = texto(
        help_text=(
            "Obligatorio si la persona no está en el legajo (alta mínima). Si está, se omite, coincide con el "
            "legajo o va con `identidad_en_conflicto`."
        )
    )
    fecha_nacimiento = serializers.DateField(required=False, allow_null=True, default=None)
    telefono = texto()
    documento_extraviado = _aviso(help_text="Perdió el documento pero sabe el número.")
    identidad_en_conflicto = _aviso(
        help_text=(
            "El DNI ya está registrado como otra persona (400 con `persona_registrada`) y quien carga sostiene "
            "que el DNI es correcto: el caso se crea con la persona registrada, sin tocarla, y queda marcado "
            "«Identidad a revisar» con el `nombre` y `apellido` enviados. Sin conflicto se ignora."
        )
    )

    # Paso 2 · personas que ingresan juntas
    responsable_aparte = _aviso(
        help_text=(
            "`true`: las cantidades son los acompañantes y el total suma al responsable. Sin él (o "
            "`false`, lo que manda una app anterior), el responsable ya está contado en las cantidades."
        )
    )
    menores_f = _cantidad()
    menores_m = _cantidad()
    adultos_f = _cantidad()
    adultos_m = _cantidad()
    mayores_f = _cantidad()
    mayores_m = _cantidad()

    # Paso 3 · necesitan asistencia
    dependientes = _cantidad(help_text="No puede superar el total.")
    mayores_dependientes = _cantidad(help_text="No puede superar los mayores (más el responsable, si va aparte).")
    lactantes = _cantidad(help_text="No puede superar los menores.")
    embarazo = _aviso()
    electrodependiente = _aviso()
    medicacion_critica = _aviso()
    mascotas = _aviso()

    # Paso 4 · ubicación y fotos
    direccion = texto(help_text="Obligatoria: calle y número, o una referencia. Hasta 240 caracteres.")
    localidad = serializers.IntegerField(
        required=False, allow_null=True, default=None, help_text="`id` de `GET /api/emergencia/localidades/`."
    )
    latitud = serializers.FloatField(required=False, allow_null=True, default=None)
    longitud = serializers.FloatField(required=False, allow_null=True, default=None)
    precision_m = serializers.FloatField(
        required=False, allow_null=True, default=None, help_text="Precisión del GPS en metros."
    )
    observaciones = texto()
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
        # El de la puerta (`IngresoDirectoEnvioSerializer`) no tiene `relevado_en`.
        datos.pop("relevado_en", None)
        datos["fotos"] = {}
        for campo, tipo in FOTOS_DEL_CASO.items():
            archivo = datos.pop(campo, None)
            if archivo:
                datos["fotos"][tipo] = archivo
        return datos


class CasoEmergenciaCreadoSerializer(serializers.ModelSerializer):
    """Lo que la app necesita para mostrar «Enviado · 7 personas · Caso N.° 2026-C-000184»."""

    total_declarado = serializers.IntegerField(source="grupo.total_declarado", read_only=True)
    ya_tenia_caso = serializers.SerializerMethodField(
        help_text=(
            "Aditiva (Cambio 579). `true` si la familia ya tenía un caso abierto: no se creó otro, `numero` es el "
            "del caso que ya estaba y la respuesta es 200. La app puede ignorarla: tratarlo como un reenvío es correcto."
        )
    )

    def get_ya_tenia_caso(self, caso) -> bool:
        return caso.familia_ya_tenia_caso

    class Meta:
        model = CasoEmergencia
        fields = ["id", "numero", "prioridad", "total_declarado", "ya_tenia_caso"]
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
    llegadas = serializers.BooleanField(
        help_text="Admite familias (`dispositivo.admitir`) en algún dispositivo: «Llegada de familias» (M2)."
    )
    kits = serializers.BooleanField(
        help_text="Recibe kits (`emergencia.recibir_kit`) en algún dispositivo: «Recepción de kits» (M3)."
    )
    dispositivo = serializers.BooleanField(
        help_text="`llegadas` o `kits`: opera en algún dispositivo. Se mantiene por compatibilidad."
    )
    plazas = serializers.BooleanField(
        help_text="Ve al menos un edificio con `dispositivo.ver` en su alcance: «Plazas y estadías» (Cambio 596)."
    )
    stock = serializers.BooleanField(
        help_text="Ve el stock (`stock.ver`) de al menos un edificio de una institución que lleva stock: «Stock»."
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


class EdificioSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nombre = serializers.CharField()


class CasoAbiertoSerializer(serializers.Serializer):
    """El caso abierto de la familia: lo único que la guardia ve de él (Cambio 579). Sin ficha, contactos ni fotos."""

    id = serializers.IntegerField()
    numero = serializers.CharField()
    familia = serializers.CharField(help_text="El apellido del responsable.")
    personas = serializers.IntegerField(help_text="Personas declaradas del caso.")
    estado = serializers.CharField(help_text="Código del estado del caso (`NUEVO`, `EN_GESTION`, `DERIVADO`…).")
    estado_texto = serializers.CharField()
    derivada_a = serializers.CharField(
        allow_null=True,
        help_text="La institución a la que la mesa derivó la familia, solo si la derivación vigente es de este "
        "dispositivo o quien pregunta es la mesa; si no, `null` y `derivada_a_otra`.",
    )
    derivada_en = serializers.DateTimeField(allow_null=True, help_text="Cuándo se derivó.")
    derivada_a_otra = serializers.BooleanField(
        default=False,
        help_text="Aditiva (Cambio 579). `true` si la derivación vigente es de otra institución: `derivada_a` y "
        "`derivada_en` van en `null` y la pantalla dice «otra institución».",
    )
    en_este_dispositivo = serializers.BooleanField(help_text="`true` si el caso ya está derivado o ingresado acá.")


class PersonaDelIntegranteSerializer(serializers.Serializer):
    id = serializers.IntegerField(help_text="`id` del legajo.")
    nombre = serializers.CharField(help_text="«Apellido, Nombre».")
    dni = serializers.CharField()


class PlazaDelIntegranteSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    codigo = serializers.CharField()
    nombre = serializers.CharField(help_text="Código con el sector: «B-12 (Pabellón B)».")


class IdentidadDeclaradaSerializer(serializers.Serializer):
    nombre = serializers.CharField()
    apellido = serializers.CharField()


#: La marca «Identidad a revisar» para la guardia (Cambio 486): lo que declaró quien cargó, solo
#: mientras la mesa no la revisó; si no, ``null``.
_IDENTIDAD_A_REVISAR_HELP = (
    "`{nombre, apellido}` tal como los cargó quien relevó cuando el DNI ya era de otra persona registrada, "
    "mientras la mesa no lo revisó; si no, `null`. Es un aviso: no bloquea nada."
)


class IntegranteSerializer(serializers.Serializer):
    """Una fila de M2-3 («Persona 3 · sin confirmar» o «Pérez, Juan · cama B-12 · ficha incompleta»)."""

    id = serializers.IntegerField(
        help_text=(
            "Identifica la fila, no solo su número: el número se reusa si se quita una persona y se agrega otra. "
            "«Quitar» lo reenvía en el cuerpo para que un reenvío tardío no borre a otra persona."
        )
    )
    n = serializers.IntegerField(
        help_text="Número de la persona en la familia (puede haber huecos si se quitó una agregada). Va en la URL."
    )
    estado = serializers.CharField(help_text="`SIN_CONFIRMAR`, `CONFIRMADA` o `EGRESADA`.")
    ficha_completa = serializers.BooleanField(help_text="Secciones 4 a 8 con algún dato o «sin datos».")
    persona = PersonaDelIntegranteSerializer(allow_null=True, help_text="`null` hasta que se confirma.")
    responsable = PersonaDelIntegranteSerializer(
        allow_null=True,
        help_text=(
            "Solo en la persona 1: el responsable que cargó el caso (legajo, «Apellido, Nombre» y DNI), "
            "también **sin confirmar**, para rotularla. En las demás, `null`."
        ),
    )
    plaza = PlazaDelIntegranteSerializer(allow_null=True, help_text="La cama de **hoy**; `null` sin confirmar.")
    parentesco = serializers.CharField(help_text="Rótulo del parentesco; vacío sin confirmar.")
    confirmada_en = serializers.DateTimeField(allow_null=True)
    egresado_en = serializers.DateTimeField(allow_null=True)
    puede_quitarse = serializers.BooleanField(
        help_text=(
            "`true` si la persona se agregó en la puerta con «Agregar persona», sigue sin confirmar y el ingreso "
            "está en curso: se puede quitar con `…/integrantes/{n}/quitar/`. Nunca el responsable ni las personas "
            "del Formulario 1."
        )
    )
    es_adulto = serializers.BooleanField(
        help_text=(
            "`true` si la persona está `CONFIRMADA`, no egresó y tiene 18 años o más (por la fecha de su ficha o la "
            "del legajo): la misma regla con la que el servidor valida `adulto_responsable_orden`. Para armar el "
            "selector de adulto responsable, ofrecer las filas con `es_adulto` y sin la propia persona; el valor a "
            "enviar es el `n` de la fila elegida."
        )
    )


class IntegranteDetalleSerializer(IntegranteSerializer):
    """Una fila con su ficha guardada: lo que la app precarga para completar las secciones 4 a 8."""

    ficha = serializers.DictField(
        help_text=(
            "El Formulario 2 tal como se guardó (contrato, «La ficha»). La persona 1 sin confirmar y sin ficha "
            "llega precargada con el responsable: `parentesco` JEFE y `datos_personales` (DNI, nombre, apellido "
            "y lo que el legajo tenga)."
        )
    )
    secciones_incompletas = serializers.ListField(
        child=serializers.CharField(), help_text="Rótulos de las secciones 4 a 8 que faltan, en orden."
    )
    identidad_a_revisar = IdentidadDeclaradaSerializer(
        allow_null=True,
        help_text=f"Solo en la persona 1 (el responsable); en las demás, `null`. {_IDENTIDAD_A_REVISAR_HELP}",
    )


class DerivacionDelIngresoSerializer(serializers.Serializer):
    id = serializers.IntegerField(
        help_text=(
            "La derivación del ingreso que se está mirando. Va como `derivacion` en `…/alojar/`, "
            "`…/cerrar-diferencia/` y `…/cancelar-ingreso/`."
        )
    )


class IntegrantesDelCasoSerializer(serializers.Serializer):
    """M2-3: las N filas de la familia con el contador."""

    caso = CasoResumenSerializer()
    derivacion = DerivacionDelIngresoSerializer(help_text="La derivación aceptada de este ingreso (Cambio 477).")
    integrantes = IntegranteSerializer(many=True)
    confirmadas = serializers.IntegerField(help_text="El «3» de «3 de 7 confirmadas».")
    total_declarado = serializers.IntegerField(help_text="Filas de la familia: crece con «Agregar persona».")
    declaradas_al_relevar = serializers.IntegerField(help_text="Lo que dijo el Formulario 1 («llegaron 8 sobre 7»).")
    con_ficha_incompleta = serializers.IntegerField()


class ResponsableSerializer(serializers.Serializer):
    """El responsable de la familia, leído desde el caso (``source="caso"``)."""

    nombre = serializers.CharField(source="grupo.responsable.nombre")
    apellido = serializers.CharField(source="grupo.responsable.apellido")
    dni = serializers.CharField(source="grupo.responsable.dni")
    identidad_a_revisar = IdentidadDeclaradaSerializer(
        source="identidad_pendiente", allow_null=True, help_text=_IDENTIDAD_A_REVISAR_HELP
    )


class GrupoDeLaDerivacionSerializer(serializers.ModelSerializer):
    """La tabla del paso 2 del Formulario 1: personas por franja y asistencia.

    ``responsable_aparte``: si es ``true``, las franjas son los acompañantes y el responsable suma uno más.
    """

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
            "responsable_aparte",
        ]
        read_only_fields = fields


class ResponsableSinAvisoSerializer(ResponsableSerializer):
    """El responsable como lo muestra la tarjeta de la web: nombre, apellido y DNI. Sin la marca de identidad.

    ``identidad_a_revisar`` (Cambio 486) la muestra la web recién al abrir el ingreso, no en la tarjeta de la
    derivación pendiente: la clave viene siempre, pero en ``null``.
    """

    identidad_a_revisar = serializers.SerializerMethodField(help_text="Siempre `null` en `derivaciones/{id}/`.")

    @extend_schema_field(IdentidadDeclaradaSerializer(allow_null=True))
    def get_identidad_a_revisar(self, caso):
        return None


class DerivacionLlegadaSerializer(serializers.ModelSerializer):
    """La tarjeta de M2-2. Solo sale si la derivación es hacia el dispositivo de quien busca (RU-9)."""

    estado = serializers.CharField(read_only=True, help_text="`PENDIENTE` (por aceptar) o `ACEPTADA` (en curso).")
    vencida = serializers.SerializerMethodField(
        help_text="Pendiente con `vence_en` pasado: se puede aceptar igual mientras la mesa no la marque vencida."
    )
    derivada_en = serializers.DateTimeField(source="creado", read_only=True)
    derivada_por = serializers.SerializerMethodField(help_text="Nombre de quien derivó en la mesa.")
    caso = CasoResumenSerializer(read_only=True)
    responsable = ResponsableSerializer(source="caso", read_only=True)
    grupo = GrupoDeLaDerivacionSerializer(source="caso.grupo", read_only=True)
    necesidades = serializers.SerializerMethodField(
        help_text="Las que marcó el Formulario 1: `embarazo`, `electrodependiente`, `medicacion_critica`, `mascotas`."
    )
    telefono = serializers.SerializerMethodField()
    observaciones = serializers.SerializerMethodField()
    edificio = EdificioSerializer(
        read_only=True,
        allow_null=True,
        help_text=(
            "El edificio al que va la familia (`{id, nombre}`); `null` en las derivaciones anteriores al campo. "
            "«Aceptar» reserva solo camas de este edificio: contar las libres de ahí (`sector.edificio` del mapa)."
        ),
    )

    class Meta:
        model = Derivacion
        fields = [
            "id",
            "edificio",
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
        return derivacion_vencida(derivacion)

    def get_derivada_por(self, derivacion) -> str:
        return nombre_de(derivacion.derivada_por)

    def get_necesidades(self, derivacion) -> list[str]:
        return [clave for clave in NECESIDADES if derivacion.caso.necesidades.get(clave)]

    def get_telefono(self, derivacion) -> str:
        return derivacion.caso.situacion.get("telefono", "")

    def get_observaciones(self, derivacion) -> str:
        return derivacion.caso.situacion.get("observaciones", "")


class DerivacionPorRecibirSerializer(serializers.ModelSerializer):
    """Una fila de la lista de la sede (Cambio 576): lo justo para listar, sin datos personales de más.

    Es la fila de «Derivaciones por recibir» de la web. ``id`` es el de la derivación: el mismo que
    ``derivacion.id`` de ``buscar`` y el que llevan ``aceptar`` y ``rechazar``. Sin DNI, sin
    integrantes, sin domicilio ni teléfono. Espera ``caso__grupo__responsable`` y ``edificio``
    cargados y ``ahora`` en el contexto: sin consultas por fila.
    """

    apellido = serializers.CharField(source="caso.grupo.responsable.apellido", read_only=True)
    personas = serializers.IntegerField(source="caso.grupo.total_declarado", read_only=True)
    caso_numero = serializers.CharField(source="caso.numero", read_only=True)
    prioridad = serializers.CharField(source="caso.prioridad", read_only=True)
    por_vencer = serializers.SerializerMethodField(
        help_text="Faltan menos de 60 minutos para `vence_en`, o ya pasó (se acepta igual): destacarla."
    )
    edificio = EdificioSerializer(read_only=True, allow_null=True)

    class Meta:
        model = Derivacion
        fields = ["id", "apellido", "personas", "caso_numero", "prioridad", "vence_en", "por_vencer", "edificio"]
        read_only_fields = fields

    def get_por_vencer(self, derivacion) -> bool:
        return por_vencer(derivacion.vence_en, self.context["ahora"])


class DerivacionDetalleSerializer(DerivacionLlegadaSerializer):
    """``derivaciones/{id}/`` (Cambio 577): la misma tarjeta que ``derivacion`` de ``buscar``, sin el aviso de identidad."""

    responsable = ResponsableSinAvisoSerializer(source="caso", read_only=True)


class BusquedaPorDniSerializer(serializers.Serializer):
    """M2-1: lo que contesta ``…/buscar/?dni=`` (03 §7). Las claves vienen **siempre**; las que no aplican, ``null``."""

    resultado = serializers.CharField(help_text="`DERIVACION`, `SIN_DERIVACION` o `ALOJADA`.")
    dni = serializers.CharField(help_text="El DNI buscado, solo dígitos.")
    plazas_libres = serializers.IntegerField(
        help_text="Camas libres que este usuario puede usar ahora (con alcance Edificios, solo las de sus edificios): decide «Ingresar igual»."
    )
    mensaje = serializers.CharField(help_text="El texto para la pantalla. Nunca nombra un dispositivo ajeno.")
    derivacion = DerivacionLlegadaSerializer(allow_null=True, help_text="Solo con `DERIVACION`.")
    alojada_aca = serializers.BooleanField(allow_null=True, help_text="Solo con `ALOJADA`: ¿en este dispositivo?")
    alojada_en = serializers.CharField(
        help_text="Solo con `ALOJADA` y si quien busca lo puede ver: el nombre del dispositivo. Si no, vacío."
    )
    alojada_desde = serializers.DateTimeField(allow_null=True)
    puede_ingresar_igual = serializers.BooleanField(
        help_text=(
            "Solo con `SIN_DERIVACION` (si no, `false`): el usuario puede «Ingresar igual» acá: alcance sobre la "
            "institución o sobre edificios (con edificios, solo con las camas de los suyos; decisión del PM del "
            "24/11/2026). Ofrecer el botón solo si es `true` **y** `plazas_libres ≥ 1` (Cambio 532)."
        )
    )
    puede_avisar_a_la_mesa = serializers.BooleanField(
        help_text=(
            "Solo con `SIN_DERIVACION` (si no, `false`): el usuario puede «Avisar a la mesa» desde acá, también con "
            "alcance por edificios (Cambio 532). Es `false` si `derivada_a_otro_edificio` es `true`."
        )
    )
    derivada_a_otro_edificio = serializers.BooleanField(
        help_text=(
            "Aditiva. `true` cuando el `resultado` es `SIN_DERIVACION` pero la familia ya tiene una derivación "
            "vigente a **otro edificio de este mismo dispositivo**, fuera del alcance del usuario: avisar a la mesa "
            "duplicaría el caso. Mostrar `mensaje` y no ofrecer «Avisar a la mesa» (viene en `false`)."
        )
    )
    edificio_derivado = EdificioSerializer(
        allow_null=True,
        help_text="Aditiva. Solo con `derivada_a_otro_edificio`: el edificio destino (`{id, nombre}`); si no, `null`.",
    )
    caso_abierto = CasoAbiertoSerializer(
        allow_null=True,
        help_text=(
            "Aditiva (Cambio 579). Con `SIN_DERIVACION`, si la familia ya tiene un caso abierto: ofrecer "
            "«Ingresar con este caso» (si `puede_ingresar_con_caso`) o «Avisar a la mesa» en vez de cargar el "
            "Formulario 1. La app que no la lee sigue andando: «Ingresar igual» y «Avisar a la mesa» se suman al "
            "caso abierto en el servidor. Si no, `null`."
        ),
    )
    puede_ingresar_con_caso = serializers.BooleanField(
        help_text=(
            "Aditiva (Cambio 579). Con `caso_abierto`: el usuario puede ingresar a la familia sobre ese caso "
            "(alcance sobre toda la institución, camas libres y un estado que lo permite). Si no, `false`."
        )
    )


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
    motivo = texto(help_text="Obligatorio: `SIN_PLAZAS`, `NO_CUMPLE_PERFIL`, `NO_LLEGO` u `OTRO`.")
    observacion = texto(help_text="Obligatoria con `OTRO`.")


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


class QuitarIntegranteEnvioSerializer(serializers.Serializer):
    id = serializers.IntegerField(
        required=False,
        help_text=(
            "El `id` de la fila que la pantalla mostró. Opcional: sin él se actúa sobre el número de la URL. Con él, "
            "si esa fila ya no es la que tiene ese número, es un reenvío y no se toca nada (`ya_estaba_quitada`)."
        ),
    )


class IntegranteQuitadoSerializer(serializers.Serializer):
    n = serializers.IntegerField(help_text="El número de la persona quitada.")
    total_declarado = serializers.IntegerField(help_text="Las filas de la familia que quedan.")
    ya_estaba_quitada = serializers.BooleanField(
        help_text="`true` si era un reenvío: esa persona ya se había quitado y no se tocó nada."
    )


def _derivacion_vista():
    return serializers.IntegerField(
        source="derivacion_vista",
        required=False,
        allow_null=True,
        default=None,
        min_value=1,
        help_text=(
            "Opcional: `derivacion.id` de `…/integrantes/`. Si ya no es la derivación del caso (la mesa volvió a "
            "derivar y otra guardia aceptó), 409 sin tocar nada. Sin él, actúa sobre la última derivación."
        ),
    )


class AlojarFamiliaEnvioSerializer(serializers.Serializer):
    """La sección 4 del Formulario 1 (M2-5)."""

    derivacion = _derivacion_vista()
    sector = serializers.IntegerField(
        required=False, allow_null=True, default=None, help_text="`id` de un sector del dispositivo (`…/plazas/`)."
    )
    aula = texto(help_text="Aula o dormitorio. Hasta 80 caracteres.")
    tarjeta_entregada = _aviso()
    tarjeta_numero = texto(help_text="Obligatorio si `tarjeta_entregada`. Hasta 40 caracteres.")
    encargado = texto(
        help_text="Obsoleto: se ignora. Quien recibe es siempre el usuario autenticado (se guarda su id y su nombre)."
    )


class CerrarConDiferenciaEnvioSerializer(serializers.Serializer):
    derivacion = _derivacion_vista()
    motivo = texto(help_text="Obligatorio: `QUEDO_CON_FAMILIARES`, `NO_LLEGO`, `DERIVADO_A_SALUD` u `OTRO`.")
    observacion = texto(help_text="Obligatoria con `OTRO`.")


class CancelarIngresoEnvioSerializer(serializers.Serializer):
    derivacion = _derivacion_vista()
    motivo = texto(help_text="Obligatorio, hasta 200 caracteres.")


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
    edificio = EdificioSerializer(
        allow_null=True,
        help_text="Aditiva. El edificio del sector (`{id, nombre}`); `null` si el sector todavía no tiene edificio.",
    )


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
    direccion = texto(help_text="Opcional: sin ella va el domicilio del dispositivo. Hasta 240 caracteres.")


class IngresoDirectoSerializer(serializers.Serializer):
    caso = CasoResumenSerializer()
    reservadas = serializers.IntegerField()
    faltantes = serializers.IntegerField()
    integrantes = IntegranteSerializer(many=True)
    ya_tenia_caso = serializers.BooleanField(
        default=False,
        help_text=(
            "Aditiva (Cambio 579). `true` si la familia ya tenía un caso abierto y el ingreso se sumó a él en vez "
            "de abrir otro. La app que no la lee sigue andando."
        ),
    )


class AvisoALaMesaSerializer(serializers.Serializer):
    caso = CasoResumenSerializer()
    ya_tenia_caso = serializers.BooleanField(
        default=False,
        help_text=(
            "Aditiva (Cambio 579). `true` si la familia ya tenía un caso abierto y el aviso se sumó a él en vez de "
            "abrir otro (con una derivación pendiente a otra institución, se cancela)."
        ),
    )
