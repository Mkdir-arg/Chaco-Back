"""API de campo, ingresar a una persona en una cama (Cambio 614).

Es el asistente de ingreso de la web (``IngresoPersonaView`` + ``IngresoPlazaView`` + ``IngresoConfirmarView``)
en tres extremos, con las mismas reglas y el mismo servicio de escritura (``ingreso.confirmar_ingreso``):

* ``GET dispositivos/<d>/ingreso/persona/?dni=`` — paso 1: ¿la persona está en el padrón y ya está alojada?
* ``GET dispositivos/<d>/ingreso/formulario/`` — paso 2: el formulario de INGRESO vigente del tipo, o ``null``.
* ``POST dispositivos/<d>/ingresar/`` — paso 3: alta si hace falta, estadía y respuestas, en **una** transacción.

Quién puede: la capacidad de la web (``dispositivo.admitir`` con alcance sobre la institución y ``ciudadano.ver``)
y, para dar de alta a quien no está en el padrón, ``ciudadano.crear``. Una institución que el usuario no ve (o no
existe) es **404**; verla sin la capacidad, **403** ``SIN_PERMISO``; un dispositivo que no está ACTIVO, **400**.
**No se consulta el Registro de Personas**: la persona nueva es un alta manual (``estado_renaper`` vacío).

El formulario de ingreso viaja en el mismo formato que el de los relevamientos (``{definicion, version}``) y sus
respuestas se validan con el mismo motor que ellos (``validar_respuestas_con_avisos``, que arma los campos con
``forms_dinamicos._field_para_campo``, el de la web). **Archivos y firmas no se reciben**: la app no tiene dónde
mandarlos antes de que exista la estadía. Si el formulario tiene uno obligatorio visible, el ingreso se hace desde
el backoffice (409 ``INGRESO_CON_ARCHIVO``); los opcionales se omiten.
"""

from django.core.exceptions import ValidationError
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.response import Response

from core.dni import MENSAJE_DNI_INVALIDO, dni_valido, normalizar_dni
from core.rbac import puede
from legajos.models import Ciudadano
from programas.api.serializers_emergencia_ingreso import (
    FormularioDeIngresoRespuestaSerializer,
    IngresarEnvioSerializer,
    PersonaDelIngresoRespuestaSerializer,
)
from programas.api.throttles import ConsultaPersonasThrottle
from programas.api.views_emergencia import _SIN_TOKEN, _400, _respuesta_de_validacion, _VistaDeCampo
from programas.api.views_emergencia_estadias import _mapa_actualizado
from programas.models import Dispositivo, MomentoFormulario, Plaza
from programas.services.dispositivos import (
    CAP_VER,
    dispositivos_en_alcance,
    puede_en_programa_dispositivos,
    puede_operar_dispositivo,
)
from programas.services.estadias import CAP_ADMITIR, CAP_VER_CIUDADANO, verificar_alojamiento_en_red
from programas.services.ingreso import (
    buscar_ciudadano_por_dni,
    errores_del_alta_manual,
    ingresar_con_formulario,
    plaza_reservada_de,
    plazas_para_ingresar,
)
from programas.services.respuestas_dispositivo import formulario_vigente, foto_vigente
from programas.services.validacion_relevamiento import (
    FormularioCambio,
    IngresoConArchivo,
    RespuestasInvalidas,
    formulario_de_ingreso_de_la_app,
    requiere_archivo,
)

CAP_CREAR_CIUDADANO = "ciudadano.crear"

CODIGO_SIN_PERMISO = "SIN_PERMISO"
CODIGO_FORMULARIO_CAMBIO = "FORMULARIO_CAMBIO"
CODIGO_INGRESO_CON_ARCHIVO = "INGRESO_CON_ARCHIVO"
MENSAJE_SIN_INGRESAR = "No tenés permiso para ingresar personas en este dispositivo."
MENSAJE_SIN_ALTA = "No tenés permiso para dar de alta personas en el padrón."
MENSAJE_FORMULARIO_CAMBIO = "El formulario de ingreso cambió. Volvé a cargarlo."
MENSAJE_INGRESO_CON_ARCHIVO = "Este ingreso se hace desde el backoffice."
MENSAJE_NO_ACTIVO = "Solo se puede alojar en un dispositivo activo."
MENSAJE_PLAZA_NO_DISPONIBLE = "Esa cama ya no está disponible. Elegí otra."

_AJENA = OpenApiResponse(
    description="La institución no existe o está fuera del alcance del usuario (`dispositivo.ver`)."
)
_SIN_CAPACIDAD = OpenApiResponse(
    description="`code: SIN_PERMISO`: ve la institución pero le falta `dispositivo.admitir` o `ciudadano.ver` (o `ciudadano.crear` para dar de alta)."
)


def _sin_capacidad(mensaje=MENSAJE_SIN_INGRESAR):
    return Response({"detail": mensaje, "code": CODIGO_SIN_PERMISO}, status=status.HTTP_403_FORBIDDEN)


class _VistaDeIngreso(_VistaDeCampo):
    """Resuelve la institución por alcance y exige la capacidad del asistente de la web."""

    def _dispositivo(self, request, dispositivo_id):
        """``(dispositivo, None)`` si puede ingresar personas ahí; si no, ``(None, respuesta)``; ajeno: 404."""
        dispositivo = self._o_404(dispositivos_en_alcance(request.user, CAP_VER).select_related("tipo"), dispositivo_id)
        if (
            not puede_en_programa_dispositivos(request.user, CAP_ADMITIR)
            or not puede_operar_dispositivo(request.user, dispositivo, CAP_ADMITIR)
            or not puede(request.user, CAP_VER_CIUDADANO)
        ):
            return None, _sin_capacidad()
        if dispositivo.estado != Dispositivo.Estado.ACTIVO:
            return None, _respuesta_de_validacion({"dispositivo": [MENSAJE_NO_ACTIVO]})
        return dispositivo, None


class IngresoPersonaView(_VistaDeIngreso):
    """Consultar un DNI es una consulta de identidad: descuenta de la cubeta ``personas_campo`` (SEC-25), la misma
    de la consulta y de la sugerencia. Se descuenta **después** de las puertas de la vista (404/403/400 de la
    institución) y con un DNI bien formado, para que lo rechazado no gaste la cubeta del usuario."""

    throttle_classes = [ConsultaPersonasThrottle]
    _descuenta = False

    def get_throttles(self):
        return super().get_throttles() if self._descuenta else []

    @extend_schema(
        parameters=[OpenApiParameter("dni", str, required=True, description="DNI de la persona (7 u 8 dígitos).")],
        responses={
            200: PersonaDelIngresoRespuestaSerializer,
            400: _400("DNI inválido, o el dispositivo no está activo."),
            401: _SIN_TOKEN,
            403: _SIN_CAPACIDAD,
            404: _AJENA,
            429: OpenApiResponse(
                description="Se superó el tope de consultas de identidad del usuario (compartido con la consulta)."
            ),
        },
        description=(
            "Paso 1 del ingreso: busca a la persona por DNI **solo en el padrón** (no consulta el Registro de "
            "Personas). `encontrada: false` si no está (la app pide sus datos y la da de alta al confirmar). Si está, "
            "trae `alojada` (y `alojamiento` con dónde, según el alcance del usuario) y `plaza_reservada_id`, la "
            "cama que tiene reservada o prestada en este dispositivo, que el ingreso consume."
        ),
    )
    def get(self, request, dispositivo_id):
        dispositivo, rechazo = self._dispositivo(request, dispositivo_id)
        if rechazo is not None:
            return rechazo
        dni = normalizar_dni(request.query_params.get("dni", ""))
        if not dni_valido(dni):
            return _respuesta_de_validacion({"dni": [MENSAJE_DNI_INVALIDO]})
        self._descuenta = True
        self.check_throttles(request)
        ciudadano = buscar_ciudadano_por_dni(dni)
        if ciudadano is None:
            return Response({"encontrada": False})
        verificacion = verificar_alojamiento_en_red(ciudadano, request.user)
        alojamiento = None
        if verificacion.alojada:
            alojamiento = {
                "mensaje": verificacion.mensaje,
                "dentro_del_alcance": verificacion.dentro_del_alcance,
                "dispositivo": verificacion.dispositivo,
                "plaza": verificacion.plaza,
                "desde": verificacion.desde,
            }
        return Response(
            PersonaDelIngresoRespuestaSerializer(
                {
                    "encontrada": True,
                    "persona": {"id": ciudadano.pk, "dni": ciudadano.dni, "nombre_completo": ciudadano.nombre_completo},
                    "alojada": verificacion.alojada,
                    "alojamiento": alojamiento,
                    "plaza_reservada_id": plaza_reservada_de(ciudadano.pk, dispositivo),
                }
            ).data
        )


class IngresoFormularioView(_VistaDeIngreso):
    @extend_schema(
        responses={
            200: FormularioDeIngresoRespuestaSerializer,
            400: _400("El dispositivo no está activo."),
            401: _SIN_TOKEN,
            403: _SIN_CAPACIDAD,
            404: _AJENA,
        },
        description=(
            "Paso 2 del ingreso: el formulario de **Ingreso** vigente del tipo del dispositivo, en el formato de "
            "los relevamientos (`{definicion, version}`), o `formulario: null` si el tipo no pide ninguno. "
            "`requiere_archivo` avisa que tiene un campo de archivo o firma obligatorio: ese ingreso se hace desde "
            "el backoffice (409 `INGRESO_CON_ARCHIVO` al confirmar)."
        ),
    )
    def get(self, request, dispositivo_id):
        dispositivo, rechazo = self._dispositivo(request, dispositivo_id)
        if rechazo is not None:
            return rechazo
        diseno = formulario_vigente(dispositivo.tipo_id, MomentoFormulario.INGRESO)
        if diseno is None:
            return Response({"formulario": None})
        foto = foto_vigente(diseno)
        return Response(
            {
                "formulario": {
                    "definicion": foto,
                    "version": diseno.version,
                    "requiere_archivo": requiere_archivo(foto),
                }
            }
        )


class IngresarView(_VistaDeIngreso):
    @extend_schema(
        request=IngresarEnvioSerializer,
        responses={
            201: OpenApiResponse(
                description="`{ok: true, estadia_id, mapa}`: el mapa del edificio de la cama, ya actualizado."
            ),
            400: _400(
                "Persona o cama inválidas, persona ya alojada, cama tomada, campos del alta o respuestas del formulario "
                "(`claves: {clave: texto}`)."
            ),
            401: _SIN_TOKEN,
            403: _SIN_CAPACIDAD,
            404: _AJENA,
            409: OpenApiResponse(
                description=(
                    "`code: FORMULARIO_CAMBIO` (la versión del formulario ya no es la vigente: recargarlo) o "
                    "`code: INGRESO_CON_ARCHIVO` (pide un archivo o firma obligatorios: se hace en el backoffice)."
                )
            ),
        },
        description=(
            "Paso 3: ingresa a la persona en la cama. Sin legajo, da de alta a `persona_nueva` (alta manual); todo "
            "—alta, estadía y respuestas del formulario— en una transacción: si algo falla no queda nada."
        ),
    )
    def post(self, request, dispositivo_id):
        dispositivo, rechazo = self._dispositivo(request, dispositivo_id)
        if rechazo is not None:
            return rechazo
        entrada = IngresarEnvioSerializer(data=request.data)
        if not entrada.is_valid():
            return _respuesta_de_validacion(self._aplanar(entrada.errors))
        datos = entrada.validated_data

        persona, rechazo = self._persona(request, datos)
        if rechazo is not None:
            return rechazo
        plaza, rechazo = self._plaza(request, dispositivo, datos["plaza_id"], persona)
        if rechazo is not None:
            return rechazo
        formulario, rechazo = self._formulario(dispositivo, datos["formulario"])
        if rechazo is not None:
            return rechazo

        estadia, respuesta = self._ejecutar(
            lambda: self._ingresar(request, dispositivo, datos, persona, plaza, formulario),
            sin_permiso=_sin_capacidad(),
        )
        if respuesta is not None:
            return self._traducir(respuesta)
        mapa = _mapa_actualizado(request, dispositivo, plaza.sector.edificio_id if plaza is not None else None)
        return Response({"ok": True, "estadia_id": estadia.pk, "mapa": mapa}, status=status.HTTP_201_CREATED)

    # --- Pasos --------------------------------------------------------------------------------

    def _persona(self, request, datos):
        """``({"ciudadano": Ciudadano} | {"manual": dict}, None)`` o ``(None, respuesta)``.

        Un ``persona_nueva`` cuyo DNI ya está en el padrón usa ese legajo: no se duplica ni se pisa.
        """
        if datos["ciudadano_id"] is not None:
            ciudadano = Ciudadano.objects.filter(pk=datos["ciudadano_id"]).first()
            if ciudadano is None:
                return None, _respuesta_de_validacion({"ciudadano_id": ["No encontramos a esa persona en el padrón."]})
            return {"ciudadano": ciudadano}, None
        nueva = datos["persona_nueva"]
        existente = buscar_ciudadano_por_dni(nueva["dni"])
        if existente is not None:
            return {"ciudadano": existente}, None
        if not puede(request.user, CAP_CREAR_CIUDADANO):
            return None, _sin_capacidad(MENSAJE_SIN_ALTA)
        manual = {
            "dni": nueva["dni"],
            "nombre": nueva["nombre"].strip(),
            "apellido": nueva["apellido"].strip(),
            "fecha_nacimiento": nueva["fecha_nacimiento"].isoformat() if nueva["fecha_nacimiento"] else None,
            "genero": nueva["sexo"],
        }
        errores = errores_del_alta_manual(manual)
        if errores:
            return None, _respuesta_de_validacion(
                {("sexo" if campo == "genero" else campo): m for campo, m in errores.items()}
            )
        return {"manual": manual}, None

    def _plaza(self, request, dispositivo, plaza_id, persona):
        """``(Plaza | None, None)`` o ``(None, 400)``: la cama tiene que ser elegible **para esta persona**.

        Elegible es lo que el asistente de la web ofrece: disponible (o la que la persona tiene guardada) y en un
        edificio donde el usuario puede admitir. Sin cama solo si el tipo no maneja plazas ni la exige.
        """
        if plaza_id is None:
            return None, None
        ciudadano = persona.get("ciudadano")
        _, elegibles = plazas_para_ingresar(
            dispositivo,
            puede_ver_personas=True,
            plaza_propia_id=plaza_reservada_de(ciudadano.pk, dispositivo) if ciudadano else None,
            usuario=request.user,
        )
        if plaza_id not in elegibles:
            return None, _respuesta_de_validacion({"plaza_id": [MENSAJE_PLAZA_NO_DISPONIBLE]})
        plaza = Plaza.objects.select_related("sector__edificio").filter(pk=plaza_id, sector__dispositivo=dispositivo)
        return plaza.first(), None

    def _formulario(self, dispositivo, envio):
        """``((diseno, foto, respuestas, ()) | None, None)`` o ``(None, respuesta)``. Valida antes de escribir."""
        try:
            validado = formulario_de_ingreso_de_la_app(dispositivo.tipo_id, envio)
        except FormularioCambio:
            return None, Response(
                {"detail": MENSAJE_FORMULARIO_CAMBIO, "code": CODIGO_FORMULARIO_CAMBIO},
                status=status.HTTP_409_CONFLICT,
            )
        except IngresoConArchivo:
            return None, Response(
                {"detail": MENSAJE_INGRESO_CON_ARCHIVO, "code": CODIGO_INGRESO_CON_ARCHIVO},
                status=status.HTTP_409_CONFLICT,
            )
        except RespuestasInvalidas as error:
            respuesta = _respuesta_de_validacion({"respuestas": list(error.por_clave.values())})
            respuesta.data["claves"] = error.por_clave
            return None, respuesta
        if validado is None:
            return None, None
        diseno, foto, respuestas = validado
        return (diseno, foto, respuestas, ()), None

    def _ingresar(self, request, dispositivo, datos, persona, plaza, formulario):
        """La estadía y sus respuestas en una transacción (el servicio de siempre revalida y toma la cama)."""
        ciudadano = persona.get("ciudadano")
        try:
            return ingresar_con_formulario(
                dispositivo=dispositivo,
                usuario=request.user,
                ciudadano_id=ciudadano.pk if ciudadano else None,
                datos_renaper=None,
                datos_manual=persona.get("manual"),
                plaza_id=plaza.pk if plaza is not None else None,
                formulario=formulario,
            )
        except Ciudadano.DoesNotExist:
            raise ValidationError({"ciudadano_id": "No encontramos a esa persona en el padrón."}) from None
        except Plaza.DoesNotExist:
            raise ValidationError({"plaza_id": MENSAJE_PLAZA_NO_DISPONIBLE}) from None

    @staticmethod
    def _aplanar(errores):
        """Los errores del alta (``persona_nueva.<campo>``) suben al nivel del cuerpo: la app los pinta por campo."""
        planos = {}
        for campo, mensajes in errores.items():
            if campo in ("persona_nueva", "formulario") and isinstance(mensajes, dict):
                for subcampo, submensajes in mensajes.items():
                    planos[subcampo] = submensajes
            else:
                planos[campo] = mensajes
        return planos

    @staticmethod
    def _traducir(respuesta):
        """Los errores del servicio hablan de ``plaza``/``reserva``: la app los lee en ``plaza_id``."""
        for campo in ("plaza", "reserva"):
            if campo in respuesta.data:
                respuesta.data.setdefault("plaza_id", []).extend(respuesta.data.pop(campo))
        return respuesta
