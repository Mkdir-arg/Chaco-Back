"""Serializers de la API de campo de Becas (#82)."""

import logging

from django.utils.dateparse import parse_date
from rest_framework import serializers
from rest_framework.settings import api_settings

from core.dni import MENSAJE_DNI_INVALIDO, dni_valido
from core.edad import es_menor
from legajos.models import Ciudadano
from programas.models import AdjuntoFormulario, Formulario, Relevamiento
from programas.services import campo as servicio_campo
from programas.services.becas import definicion_formulario
from programas.services.padron import normalizar_dni
from programas.services.personas import fecha_iso

logger = logging.getLogger(__name__)

MENSAJE_FECHA_INVALIDA = "La fecha de nacimiento no es una fecha válida."


def rechazo_legible(detalle, mensaje):
    """Un 400 que el territorial puede leer, sin sacarle el detalle por campo.

    La app (``becasApi.js``, ``buildResponseError``) arma el texto que ve la
    persona mirando ``detail`` y ``non_field_errors``; un diccionario anidado por
    campo —que es lo que devuelve un ``ValidationError`` con la forma de DRF— no
    cae en ninguna de las dos y el territorial, parado delante de la persona,
    lee «Error HTTP 400» y no sabe qué corregir.

    Se agrega ``non_field_errors`` **además** de lo que ya viajaba: quien lea el
    error por campo —el navegador del backoffice, un test— sigue encontrándolo
    donde estaba.
    """
    return serializers.ValidationError({**detalle, api_settings.NON_FIELD_ERRORS_KEY: [mensaje]})


class RelevamientoListSerializer(serializers.ModelSerializer):
    segmento = serializers.CharField(source="convocatoria.segmento.nombre", read_only=True)
    localidad = serializers.CharField(source="convocatoria.subsegmento.nombre", read_only=True, default="")
    convocatoria_nombre = serializers.CharField(source="convocatoria.nombre", read_only=True)
    # Anotado en el queryset del viewset (evita un COUNT por ítem).
    formularios_count = serializers.IntegerField(read_only=True)
    # Propiedades del modelo. Declaradas con su tipo porque `ModelSerializer` las
    # resolvía como `ReadOnlyField` y el esquema las publicaba como `string`
    # (RED-37): quien generara un cliente desde el esquema comparaba el cupo
    # contra un texto. El valor que viaja es el mismo.
    # RED-49: la property pasó a llamarse `cupos_libres_del_relevamiento` (había tres
    # cosas distintas llamadas `cupo_disponible`). El **campo de la API no cambia**: lo
    # lee la app de campo que ya está instalada, y el contrato lo congela
    # `programas/tests/test_becas_api_contrato.py`.
    cupo_disponible = serializers.IntegerField(source="cupos_libres_del_relevamiento", read_only=True)
    cupo_completo = serializers.BooleanField(read_only=True)
    pausado = serializers.SerializerMethodField()
    pausa_motivo = serializers.SerializerMethodField()

    class Meta:
        model = Relevamiento
        fields = [
            "id",
            "numero",
            "nombre",
            "zona",
            "fecha_asignada",
            "fecha_hasta",
            "estado",
            "segmento",
            "localidad",
            "convocatoria_nombre",
            "fecha_finalizado",
            "formularios_count",
            "cupo_maximo",
            "cupo_disponible",
            "cupo_completo",
            "pausado",
            "pausa_motivo",
        ]

    # El hint de retorno no es decorativo: drf-spectacular lo lee para tipar el
    # campo en el esquema (RED-37) y es el paso 3 de RED-76.
    def get_pausado(self, obj) -> bool:
        return obj.pausa_efectiva is not None

    def get_pausa_motivo(self, obj) -> str:
        pausa = obj.pausa_efectiva
        return pausa.pausa_motivo if pausa else ""


class RelevamientoDetailSerializer(RelevamientoListSerializer):
    definicion_formulario = serializers.SerializerMethodField()

    class Meta(RelevamientoListSerializer.Meta):
        fields = RelevamientoListSerializer.Meta.fields + ["definicion_formulario"]

    def get_definicion_formulario(self, obj) -> dict:
        return definicion_formulario(obj)


class FormularioSerializer(serializers.ModelSerializer):
    ciudadano_dni = serializers.CharField(source="ciudadano.dni", read_only=True)
    ciudadano_nombre = serializers.CharField(source="ciudadano.nombre", read_only=True)
    ciudadano_apellido = serializers.CharField(source="ciudadano.apellido", read_only=True)
    client_uuid = serializers.UUIDField(required=False, allow_null=True)
    capturado_en = serializers.DateTimeField(required=False, allow_null=True)
    # G1-16: con qué versión del diseño capturó el teléfono. **Opcional**: la app
    # instalada (`Chaco-mobile@a66c2d3`) no la manda y el alta funciona igual.
    # Si viene, se guarda y se compara contra la versión de la foto que el caso
    # terminó guardando (`services.campo`). El tope es el del `INT` con signo de
    # la columna: sin él, un `2**40` pasa el serializer y MariaDB en modo estricto
    # lo contesta con un `DataError`, o sea un 500 para la app.
    version_capturada = serializers.IntegerField(required=False, allow_null=True, min_value=0, max_value=2_147_483_647)

    class Meta:
        model = Formulario
        fields = [
            "id",
            "numero",
            "client_uuid",
            "capturado_en",
            "relevamiento",
            "estado",
            "motivo_rechazo",
            "validado_renaper",
            "ciudadano",
            "ciudadano_dni",
            "ciudadano_nombre",
            "ciudadano_apellido",
            "datos_identificacion",
            "celular",
            "email_contacto",
            "apoderado_nombre",
            "apoderado_apellido",
            "apoderado_dni",
            "apoderado_genero",
            "apoderado_fecha_nacimiento",
            "apoderado_ciudadano",
            "gps_lat",
            "gps_lng",
            # G1-04: la captura entró después de que el relevamiento cerró,
            # dentro de la gracia. Clave **nueva**: la app vieja la ignora.
            "sincronizado_tarde",
            # G1-16: la versión del diseño con la que se capturó. Clave **nueva**
            # y opcional en los dos sentidos: la app vieja ni la manda ni la lee.
            "version_capturada",
            "data",
            "creado",
            "modificado",
        ]
        read_only_fields = [
            "id",
            "numero",
            "relevamiento",
            "estado",
            "motivo_rechazo",
            # SEC-23 · lo escribe **solo** el servidor
            # (`_actualizar_validacion_identidad`). Entraba por el cuerpo del
            # request y lo pisaba `_completar_alta` un instante después, así que
            # no servía para nada y sí daba un camino para marcar validada una
            # identidad que nadie acreditó. La app en producción
            # (`Chaco-mobile@a66c2d3`) lo manda en el alta: un campo de solo
            # lectura **se ignora**, no da 400, así que el teléfono instalado no
            # cambia de comportamiento. La clave sigue viajando en la respuesta.
            "validado_renaper",
            "ciudadano",
            "ciudadano_dni",
            "ciudadano_nombre",
            "ciudadano_apellido",
            "apoderado_ciudadano",
            "sincronizado_tarde",
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
        # G1-05: el DNI del titular es lo único que se rechaza, porque un caso
        # con un DNI imposible no se puede arreglar después —no se lo puede
        # cruzar con el padrón, ni consultar en SIIS, ni unir a un legajo—.
        # El resto de lo que venga mal se acepta y se observa (`services.campo`).
        if isinstance(datos, dict) and datos.get("dni") is not None:
            dni = normalizar_dni(datos.get("dni"))
            if not dni_valido(dni):
                raise rechazo_legible({"datos_identificacion": {"dni": MENSAJE_DNI_INVALIDO}}, MENSAJE_DNI_INVALIDO)
            datos["dni"] = dni
        # G1-06: la fecha llega como la tipeó el territorial. `parse_date`
        # devuelve None para `15/03/2010` y traga el ValueError de `2000-02-30`,
        # así que el texto crudo seguía viaje hasta el ORM y el alta del legajo
        # explotaba **después** del commit del caso: 500, la app reintenta ocho
        # veces por ser 5xx, y el caso queda sin legajo y sin RN-22 evaluada.
        if isinstance(datos, dict) and datos.get("fecha_nacimiento"):
            normalizada = fecha_iso(datos["fecha_nacimiento"])
            if not normalizada:
                raise rechazo_legible(
                    {"datos_identificacion": {"fecha_nacimiento": MENSAJE_FECHA_INVALIDA}},
                    MENSAJE_FECHA_INVALIDA,
                )
            datos["fecha_nacimiento"] = normalizada
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
                "apoderado_dni",
                "apoderado_genero",
                "apoderado_fecha_nacimiento",
            )
            faltantes = [
                campo
                for campo in campos_apoderado
                if not (attrs.get(campo) if campo in attrs else getattr(self.instance, campo, None))
            ]
            if faltantes:
                raise serializers.ValidationError(
                    {
                        campo: "Este dato es obligatorio cuando la persona relevada es menor de edad."
                        for campo in faltantes
                    }
                )
            valor_dni = attrs.get("apoderado_dni") if "apoderado_dni" in attrs else self.instance.apoderado_dni
            # RED-48: misma normalización y misma regla de largo que el resto de las
            # puertas (acá estaban las dos escritas a mano).
            dni_apoderado = normalizar_dni(valor_dni)
            if not dni_valido(dni_apoderado):
                raise serializers.ValidationError({"apoderado_dni": MENSAJE_DNI_INVALIDO})
            attrs["apoderado_dni"] = dni_apoderado
            valor_genero = (
                attrs.get("apoderado_genero") if "apoderado_genero" in attrs else self.instance.apoderado_genero
            )
            if valor_genero not in (Ciudadano.Genero.MASCULINO, Ciudadano.Genero.FEMENINO):
                raise serializers.ValidationError({"apoderado_genero": "Seleccioná sexo F o M."})
        return attrs


class FormularioListSerializer(FormularioSerializer):
    """El caso en el **listado** de un relevamiento (G1-03).

    Es ``FormularioSerializer`` sin ``data``: el JSON de respuestas del contrato
    anterior pesa ~7 KB por caso y de esta lista la app solo lee el nombre, el
    DNI, el estado y el ``client_uuid`` (para no duplicar lo que ya subió). Con
    el listado sin paginar —el otro medio arreglo de G1-03— traerlo por fila es
    justo lo que no se puede hacer: 40 casos × 7 KB en una sola respuesta, con
    el ``read_timeout`` de 10 s de por medio.

    El resto de las claves se conserva **tal cual**: la app en producción lee
    ``datos_identificacion`` cuando el caso todavía no tiene legajo, que es el
    caso normal de una carga offline recién sincronizada.
    """

    class Meta(FormularioSerializer.Meta):
        fields = [clave for clave in FormularioSerializer.Meta.fields if clave != "data"]


class ConsultaPersonaSerializer(serializers.Serializer):
    """Cuerpo de ``POST /api/becas/personas/consultar/`` (y su alias RENAPER).

    La vista validaba a mano y el esquema publicaba el POST sin ``requestBody``:
    un cliente generado desde la documentación mandaba el cuerpo vacío (RED-37).

    Las normalizaciones son las mismas que hacía la vista —DNI a dígitos, sexo
    sin espacios y en mayúscula— para que no cambie qué entradas acepta la app
    en producción.
    """

    SEXOS = (("F", "Femenino"), ("M", "Masculino"))

    dni = serializers.CharField(help_text="DNI; se queda solo con los dígitos.")
    sexo = serializers.ChoiceField(choices=SEXOS)
    relevamiento = serializers.IntegerField(
        required=False,
        help_text="Relevamiento contra cuyo padrón identificar. Si no viene, se usan todos los vigentes.",
    )

    def to_internal_value(self, data):
        crudo = data.dict() if hasattr(data, "dict") else dict(data)
        crudo["dni"] = normalizar_dni(crudo.get("dni"))
        crudo["sexo"] = str(crudo.get("sexo") or "").strip().upper()
        # La app vieja no manda el relevamiento, y manda `""` o `null` cuando
        # todavía no eligió uno: eso siempre significó "todos los vigentes".
        if not crudo.get("relevamiento"):
            crudo.pop("relevamiento", None)
        return super().to_internal_value(crudo)


class ConsultaPersonaRespuestaSerializer(serializers.Serializer):
    """La respuesta 200 de la consulta de identidad (Cambio 57)."""

    success = serializers.BooleanField()
    origen = serializers.CharField(help_text="`padron`, `personas` o `manual`.")
    data = serializers.DictField()
    datos_api = serializers.DictField()


# Adjuntos de la app de campo. El portal publico tiene su propia lista, mas
# corta (`portal/forms/inscripcion.py`): alla el upload es anonimo y ahi el
# criterio es el mas duro posible. Aca sube un territorial autenticado desde un
# telefono, asi que se suman los formatos que producen las camaras -- rechazar
# una captura legitima le rompe el trabajo de campo.
#
# Lo que importa que quede AFUERA es el contenido ejecutable o interpretable
# (.html, .svg, .js): `/media/` lo sirve nginx directo, sin pasar por Django, asi
# que un archivo asi se ejecutaria en el origen del sitio.
ADJUNTO_EXTENSIONES = (".jpg", ".jpeg", ".png", ".pdf", ".heic", ".heif", ".webp")
ADJUNTO_MAX_BYTES = 5 * 1024 * 1024


MENSAJE_ADJUNTO_FORMATO = "Solo se aceptan archivos JPG, PNG, WEBP, HEIC o PDF."
MENSAJE_ADJUNTO_TAMANIO = "El archivo no puede superar los 5 MB."


class AdjuntoFormularioSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdjuntoFormulario
        fields = ["id", "formulario", "pregunta_global", "requisito_nativo", "archivo", "creado"]
        read_only_fields = ["id", "formulario", "creado"]

    def validate(self, attrs):
        """Tipo y tamaño del archivo, y a qué campo del formulario pertenece.

        Las dos reglas del archivo estaban en un ``validate_archivo``, que
        devuelve el error **solo** bajo la clave ``archivo``: la app lo arma
        mirando ``detail``/``non_field_errors``, así que el territorial veía
        «Error HTTP 400» en vez de «el archivo no puede superar los 5 MB» —el
        único mensaje que le dice qué hacer—. Se conserva la clave ``archivo``
        (quien lea por campo la sigue encontrando) y se suma la legible.
        """
        archivo = attrs.get("archivo")
        nombre = (getattr(archivo, "name", "") or "").lower()
        if not nombre.endswith(ADJUNTO_EXTENSIONES):
            raise rechazo_legible({"archivo": [MENSAJE_ADJUNTO_FORMATO]}, MENSAJE_ADJUNTO_FORMATO)
        if archivo.size > ADJUNTO_MAX_BYTES:
            raise rechazo_legible({"archivo": [MENSAJE_ADJUNTO_TAMANIO]}, MENSAJE_ADJUNTO_TAMANIO)

        pregunta = attrs.get("pregunta_global")
        requisito = attrs.get("requisito_nativo")
        if bool(pregunta) == bool(requisito):
            raise serializers.ValidationError("Se requiere exactamente uno: pregunta_global o requisito_nativo.")
        # G1-07: se rechaza **solo** la referencia que nunca pudo ser de esta
        # convocatoria (otro segmento, o un campo que no pide ningún archivo). La
        # que quedó vieja entre la captura y la sincronización entra y se observa
        # (`servicio_campo.guardar_adjunto`): un 400 corta la cola de subidas de
        # la app y se lleva puestos los documentos que venían después. El
        # ``formulario`` lo pone la vista en el contexto, que es la única que sabe
        # de qué caso se trata (el campo es de solo lectura justamente para que el
        # cliente no lo elija).
        formulario = self.context.get("formulario")
        if formulario is not None and (
            servicio_campo.pertenencia_del_adjunto(formulario, pregunta_global=pregunta, requisito_nativo=requisito)
            == servicio_campo.ADJUNTO_AJENO
        ):
            raise serializers.ValidationError(servicio_campo.MENSAJE_ADJUNTO_AJENO)
        return attrs
