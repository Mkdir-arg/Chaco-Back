import logging
import re

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.db import IntegrityError
from django.http import JsonResponse, QueryDict
from django.views.decorators.http import require_GET, require_POST

from core import rbac
from core.http import error_json, ok_json
from core.services.throttle import rate_limit_excedido
from programas.management.commands.seed_becas import (
    ROL_COORDINADOR,
    ROL_COORDINADOR_REGIONAL,
    ROL_TERRITORIAL,
)
from programas.models import AsignacionTerritorial, Segmento
from programas.services.autorizacion import (
    es_admin_becas,
    puede_gestionar_segmento,
    segmentos_asignables_territorial,
)
from programas.services.dispositivos import puede_en_programa_dispositivos
from programas.services.inspecciones import (
    CAP_ASIGNAR,
    CAP_CREAR_AGENTE,
    CLAVE_ROL_AGENTE,
    buscar_agentes_de_relevamiento,
    edificios_en_alcance,
)
from users.forms import MENSAJE_DNI_DUPLICADO, UserCreationForm
from users.models import RolMeta
from users.selectors.usuarios import alcance_roles_ids
from users.services.admin import UsuariosAdminService
from users.services.correo import ENTREGA_LINK, entregar_credenciales_provisorias
from users.services.territoriales import (
    MIN_CARACTERES,
    TerritorialFueraDeAlcance,
    TerritorialInactivo,
    asignar_segmento,
    buscar_territoriales,
    nombre_para_mostrar,
)

# Atajos de alta de los modales de Becas: tipo del botón → (rol que otorga, plural
# para el mensaje de error). Son roles de backoffice y no llevan segmento: los da
# de alta el admin del programa. ``referente`` es el Coordinador Regional que queda
# a cargo de un subsegmento —así lo llama la UI de segmentos—, no el rol
# "Becas — Referente".
logger = logging.getLogger(__name__)

ROLES_BACKOFFICE = {
    "coordinador": (ROL_COORDINADOR, "coordinadores"),
    "referente": (ROL_COORDINADOR_REGIONAL, "referentes"),
}

#: Qué decirle al operador cuando la carrera la gana el otro (G1b-10). La clave es el
#: ``name`` del campo en el modal: el JS enfoca ``form.elements.namedItem(primerCampo)``.
MENSAJES_COLISION = {
    "username": "Ese nombre de usuario lo acaban de tomar. Probá con otro.",
    "dni": "Ese DNI ya está cargado en otro usuario. Revisalo.",
    "__all__": "No pudimos crear el usuario: alguno de los datos ya está en uso. Revisalos y probá de nuevo.",
}


#: Dónde nombra cada motor la clave que se rompió. MySQL 8 y MariaDB: ``for key
#: 'auth_user.username'`` / ``for key 'dni'``; SQLite: ``UNIQUE constraint failed:
#: users_profile.dni``.
_CLAVE_DEL_MOTOR = (
    re.compile(r"for key ['\"`]?([^'\"`\s]+)", re.IGNORECASE),
    re.compile(r"unique constraint failed:\s*([\w.,\s]+)", re.IGNORECASE),
)


def _clave_rota(error):
    """El nombre del índice que informa el motor (``auth_user.username``), o ``None``.

    Es el único pedazo del mensaje que no trae el valor que chocó, y lo que hace falta
    para entender una colisión que no se pudo atribuir a ``username`` ni a ``dni``: sin
    él, el log decía «campo __all__» y no quedaba forma de saber contra qué índice fue.
    """
    for patron in _CLAVE_DEL_MOTOR:
        encontrada = patron.search(str(error))
        if encontrada is not None:
            return encontrada.group(1).strip()
    return None


def _campo_en_colision(error):
    """Qué índice único rompió, leído del **nombre de la clave** que informa el motor.

    Buscar el nombre del campo en el mensaje entero no sirve: ahí también viaja el valor
    que chocó, y el alta del usuario ``dnievas`` —``Duplicate entry 'dnievas' for key
    'auth_user.username'``— le marcaba el DNI, que estaba bien. Se recorta primero la
    clave (``auth_user.username``, ``dni``, ``users_profile_dni_…_uniq``) y recién ahí se
    la parte en palabras: así ``dnievas`` no es ninguna de ellas.

    Cuando no se puede decidir se devuelve el error de formulario general, en vez de
    culpar al campo equivocado.
    """
    for patron in _CLAVE_DEL_MOTOR:
        encontrada = patron.search(str(error))
        if encontrada is None:
            continue
        palabras = set(re.split(r"\W|_", encontrada.group(1).lower()))
        for campo in ("username", "dni"):
            if campo in palabras:
                return campo
    return "__all__"


CAP_TERRITORIAL = "becas.usuario.territorial"

#: Cubetas por operador (sin IP: detrás del NAT de una repartición comparten dirección).
CUBETA_BUSCAR_TERRITORIAL = "usuario_buscar_territorial"
CUBETA_ASIGNAR_TERRITORIAL = "usuario_asignar_territorial"
BUSQUEDAS_POR_MINUTO = 30
ASIGNACIONES_POR_MINUTO = 20

MENSAJE_DNI_TERRITORIAL = (
    "Ese DNI ya es de un usuario del sistema: buscalo en el paso anterior, "
    "o pedile al administrador del programa que le sume el rol Territorial."
)

#: Alta de agentes de relevamiento edilicio (Dispositivos). Cubeta por operador, como las del territorial.
CUBETA_ALTA_AGENTE = "usuario_alta_agente"
CUBETA_BUSCAR_AGENTE = "usuario_buscar_agente"
ALTAS_AGENTE_POR_MINUTO = 20
#: Lo único que el operador de Dispositivos puede mandar en el alta: nada de roles, jerarquía ni segmentos.
CAMPOS_ALTA_AGENTE = ("username", "email", "first_name", "last_name", "dni", "telefono")

MENSAJE_DNI_AGENTE = (
    "Ese DNI ya es de un usuario del sistema: pedile al administrador del programa que le sume el rol de agente."
)

#: Qué se le dice a quien repite un DNI, por tipo de alta (la persona ya existe: hay que sumarle el rol, no duplicarla).
#: Los tipos de backoffice no están: ven el texto genérico del ABM.
MENSAJES_DNI_DUPLICADO = {"territorial": MENSAJE_DNI_TERRITORIAL, "agente": MENSAJE_DNI_AGENTE}

#: En Dispositivos `programa.configurar` es delegable a propósito (da alcance total de configurador:
#: `puede_configurar_dispositivos`, `dispositivos_en_alcance`), así que `puede_asignar_capacidades` no la frena.
#: Un rol de agente que la tenga convertiría el alta en una vía para fabricar configuradores.
CAPS_PROHIBIDAS_EN_ROL_DE_AGENTE = frozenset({"programa.configurar"})


def _rol_de_agente():
    """El grupo sembrado de agente (por clave) o ``None`` si no se lo puede dar de forma segura.

    Se descarta si está inactivo, si dejó de ser de Dispositivos o si alguien le tildó una capacidad
    que un operador de programa no puede repartir: el endpoint solo está pensado para dar el rol de
    agente, no para fabricar administradores.
    """
    meta = RolMeta.objects.filter(clave=CLAVE_ROL_AGENTE, activo=True).select_related("grupo", "programa").first()
    if meta is None or meta.categoria != rbac.CATEGORIA_PROGRAMA or meta.programa is None:
        return None
    if meta.programa.codigo != rbac.CODIGO_PROGRAMA_DISPOSITIVOS:
        return None
    capacidades = set(rbac.capacidades_de_grupo(meta.grupo))
    if capacidades & CAPS_PROHIBIDAS_EN_ROL_DE_AGENTE:
        return None
    if not rbac.puede_asignar_capacidades(meta.programa, capacidades):
        return None
    return meta.grupo


def _segmento_destino(request, valor):
    """El segmento activo que el operador puede ofrecer y gestionar, o ``None``.

    Es el mismo criterio que el selector del ABM y el escritor
    (`segmentos_asignables_territorial`), más ``puede_gestionar_segmento``.
    """
    try:
        pk = int(valor)
    except (TypeError, ValueError):
        return None
    segmento = Segmento.objects.filter(pk=pk, activo=True).first()
    if (
        segmento is None
        or not segmentos_asignables_territorial(request.user).filter(pk=segmento.pk).exists()
        or not puede_gestionar_segmento(request.user, segmento)
    ):
        return None
    return segmento


@login_required
@require_GET
def usuario_buscar_territorial(request):
    """Busca territoriales que ya tienen cuenta, para sumarles el segmento destino."""
    if not rbac.puede(request.user, CAP_TERRITORIAL):
        return error_json("No tiene permiso para buscar territoriales.", status=403)
    segmento = _segmento_destino(request, request.GET.get("segmento_id"))
    if segmento is None:
        return error_json("Seleccioná un segmento permitido.", status=403)
    if rate_limit_excedido(
        request,
        CUBETA_BUSCAR_TERRITORIAL,
        BUSQUEDAS_POR_MINUTO,
        sufijo=str(request.user.pk),
        incluir_ip=False,
    ):
        return error_json("Hiciste muchas búsquedas seguidas. Esperá un minuto y probá de nuevo.", status=429)
    texto = (request.GET.get("q") or "").strip()
    if len(texto) < MIN_CARACTERES:
        return error_json(f"Escribí al menos {MIN_CARACTERES} caracteres.", status=400)
    resultados, hay_mas = buscar_territoriales(request.user, texto, segmento)
    return ok_json(resultados=resultados, hay_mas=hay_mas)


@login_required
@require_GET
def usuario_buscar_agente(request):
    """Busca agentes de relevamiento que ya tienen cuenta (Cambio 397), para elegirlos en el modal de asignar.

    Mismo gate que el botón «Crear agente» (``inspeccion.agente.crear`` acotada a Dispositivos). Solo devuelve
    a quien tiene el rol sembrado de agente y marca si es asignable al edificio; **no da rol ni permiso**.
    """
    if not puede_en_programa_dispositivos(request.user, CAP_CREAR_AGENTE):
        return error_json("No tiene permiso para buscar agentes.", status=403)
    try:
        edificio_id = int(request.GET.get("edificio_id") or "")
    except ValueError:
        return error_json("Elegí primero el edificio.", status=400)
    edificio = edificios_en_alcance(request.user, CAP_ASIGNAR).filter(pk=edificio_id).first()
    if edificio is None:
        return error_json("No tenés alcance sobre ese edificio.", status=403)
    if rate_limit_excedido(
        request,
        CUBETA_BUSCAR_AGENTE,
        BUSQUEDAS_POR_MINUTO,
        sufijo=str(request.user.pk),
        incluir_ip=False,
    ):
        return error_json("Hiciste muchas búsquedas seguidas. Esperá un minuto y probá de nuevo.", status=429)
    texto = (request.GET.get("q") or "").strip()
    if len(texto) < MIN_CARACTERES:
        return error_json(f"Escribí al menos {MIN_CARACTERES} caracteres.", status=400)
    resultados, hay_mas = buscar_agentes_de_relevamiento(edificio, texto)
    return ok_json(resultados=resultados, hay_mas=hay_mas)


@login_required
@require_POST
def usuario_asignar_territorial(request):
    """Suma el segmento destino a un territorial que ya existe."""
    if not rbac.puede(request.user, CAP_TERRITORIAL):
        return error_json("No tiene permiso para asignar territoriales.", status=403)
    segmento = _segmento_destino(request, request.POST.get("segmento_id"))
    if segmento is None:
        return error_json("Seleccioná un segmento permitido.", status=403)
    if rate_limit_excedido(
        request,
        CUBETA_ASIGNAR_TERRITORIAL,
        ASIGNACIONES_POR_MINUTO,
        sufijo=str(request.user.pk),
        incluir_ip=False,
    ):
        return error_json("Hiciste muchas asignaciones seguidas. Esperá un minuto y probá de nuevo.", status=429)
    try:
        usuario, segmentos = asignar_segmento(request.user, request.POST.get("user_id"), segmento)
    except TerritorialFueraDeAlcance:
        return error_json("No podés asignar a este usuario.", status=403)
    except TerritorialInactivo:
        return error_json("Está inactivo: lo reactiva el administrador del programa.", status=409)
    return ok_json(
        message="Se asignó el territorial al segmento.",
        user={
            "id": usuario.pk,
            "label": nombre_para_mostrar(usuario),
            "segmento_id": segmento.pk,
            "segmentos": segmentos,
        },
    )


def _crear_y_responder(request, *, tipo, rol, data, alcance, segmento=None, roles_acotados=None):
    """Cola común del alta rápida: valida con `UserCreationForm`, crea, entrega la clave y responde el JSON.

    Es la misma para todos los tipos; lo que cambia —permiso, rol, datos aceptados y alcance de roles—
    lo resuelve cada llamador (`usuario_alta_rapida` para Becas, `_alta_agente` para Dispositivos).
    """
    data.setlist("groups", [str(rol.pk)])
    if segmento:
        data.setlist("segmentos_territoriales", [str(segmento.pk)])
    form = UserCreationForm(data=data, operador=request.user, roles_acotados=roles_acotados)
    if not form.is_valid():
        errores = {campo: [str(error) for error in lista] for campo, lista in form.errors.items()}
        mensaje_dni = MENSAJES_DNI_DUPLICADO.get(tipo)
        if mensaje_dni and MENSAJE_DNI_DUPLICADO in errores.get("dni", []):
            # La persona ya existe: hay que sumarle el rol, no duplicarla. El texto del ABM no cambia.
            errores["dni"] = [mensaje_dni if e == MENSAJE_DNI_DUPLICADO else e for e in errores["dni"]]
            return JsonResponse({"ok": False, "message": mensaje_dni, "errors": errores}, status=400)
        return JsonResponse({"ok": False, "errors": errores}, status=400)

    try:
        usuario = UsuariosAdminService.create_user_from_form(form, alcance_group_ids=alcance)
    except IntegrityError as exc:
        # G1b-10: el `ModelForm` ya valida que el usuario y el DNI no estén tomados,
        # así que acá solo llega la **carrera**: dos altas simultáneas con el mismo
        # valor pasan las dos validaciones y la segunda choca contra el índice único.
        # Sin esto el modal recibía el HTML de un 500 y mostraba «respuesta inesperada
        # del servidor»; ahora dice qué dato repetir y deja el foco en ese campo.
        # El mensaje del motor trae el **valor** que chocó (`Duplicate entry '30111222'
        # for key 'users_profile.dni'`): loguearlo entero deja el DNI de una persona en
        # el log de la aplicación, que no es un lugar con control de acceso. Alcanza con
        # el campo para entender qué pasó.
        campo = _campo_en_colision(exc)
        if campo == "__all__":
            # Ronda 3: acá el campo no se pudo atribuir, así que «campo __all__» no dice
            # nada. El nombre de la clave sí —es contra qué índice chocó— y tampoco lleva
            # el valor, que es lo que no puede quedar en el log.
            logger.warning(
                "Alta rápida: colisión de unicidad que no se pudo atribuir a un campo (clave %s)",
                _clave_rota(exc) or "sin nombre en el mensaje del motor",
            )
        else:
            logger.warning("Alta rápida: colisión de unicidad al crear el usuario (campo %s)", campo)
        return JsonResponse(
            {"ok": False, "message": MENSAJES_COLISION[campo], "errors": {campo: [MENSAJES_COLISION[campo]]}},
            status=409,
        )

    # Mismo criterio que el ABM de usuarios: con correo, la clave la genera el
    # sistema y viaja en el mensaje (RN-C1); sin correo, queda la que tipeó el
    # operador y se la entrega por otra vía.
    aviso = ""
    if usuario.email:
        try:
            modalidad = entregar_credenciales_provisorias(usuario, request, rol=rol.name)
            aviso = (
                "Se envió el correo con el enlace para definir la contraseña."
                if modalidad == ENTREGA_LINK
                else "Se envió el correo con la clave provisoria."
            )
        except Exception:
            logger.exception("El usuario fue creado, pero no se pudo enviar la clave provisoria")
            aviso = 'No se pudo enviar el correo: el usuario puede entrar con "Olvidé mi contraseña".'
    else:
        aviso = "Sin correo: entregale la contraseña provisoria por otra vía."

    segmentos = []
    if segmento:
        segmentos = list(
            AsignacionTerritorial.objects.filter(territorial=usuario)
            .order_by("pk")
            .values_list("segmento_id", flat=True)
        )
    return JsonResponse(
        {
            "ok": True,
            "message": aviso,
            "user": {
                "id": usuario.pk,
                "label": usuario.get_full_name() or usuario.username,
                "segmento_id": segmento.pk if segmento else None,
                "segmentos": segmentos,
            },
        }
    )


def _alta_agente(request):
    """Alta de un agente de relevamiento edilicio (Dispositivos, ``inspeccion.agente.crear``).

    Solo da el rol sembrado de agente: permiso acotado a Dispositivos, límite por operador, rol por clave,
    lista blanca de campos y un formulario que no acepta ningún otro rol.
    """
    if not puede_en_programa_dispositivos(request.user, CAP_CREAR_AGENTE):
        return JsonResponse({"ok": False, "message": "No tiene permiso para crear agentes."}, status=403)
    if rate_limit_excedido(
        request,
        CUBETA_ALTA_AGENTE,
        ALTAS_AGENTE_POR_MINUTO,
        sufijo=str(request.user.pk),
        incluir_ip=False,
    ):
        return JsonResponse(
            {"ok": False, "message": "Hiciste muchas altas seguidas. Esperá un minuto y probá de nuevo."},
            status=429,
        )
    rol = _rol_de_agente()
    if rol is None:
        return JsonResponse({"ok": False, "message": "El rol requerido no está configurado."}, status=409)
    # Lista blanca: solo los datos de la persona. Roles, contraseña, jerarquía y segmentos del POST se descartan.
    data = QueryDict(mutable=True)
    for campo in CAMPOS_ALTA_AGENTE:
        data[campo] = request.POST.get(campo, "").strip()
    if not data["email"]:
        # Decisión del 14-oct: el agente lleva correo obligatorio; el enlace de la clave viaja por ahí.
        mensaje = "El correo es obligatorio: la clave se le entrega por correo."
        return JsonResponse({"ok": False, "message": mensaje, "errors": {"email": [mensaje]}}, status=400)
    return _crear_y_responder(
        request,
        tipo="agente",
        rol=rol,
        data=data,
        alcance={rol.pk},
        roles_acotados=Group.objects.filter(pk=rol.pk),
    )


@login_required
@require_POST
def usuario_alta_rapida(request):
    tipo = request.POST.get("tipo")
    if tipo == "agente":
        return _alta_agente(request)
    if tipo not in ROLES_BACKOFFICE and tipo != "territorial":
        return JsonResponse({"ok": False, "message": "Tipo de usuario inválido."}, status=400)

    if tipo == "territorial":
        if not rbac.puede(request.user, CAP_TERRITORIAL):
            return JsonResponse({"ok": False, "message": "No tiene permiso para crear territoriales."}, status=403)
        rol = Group.objects.filter(name=ROL_TERRITORIAL).first()
        segmento = _segmento_destino(request, request.POST.get("segmento_id"))
        if segmento is None:
            return JsonResponse({"ok": False, "message": "Seleccioná un segmento permitido."}, status=403)
    else:
        nombre_rol, plural = ROLES_BACKOFFICE[tipo]
        if not es_admin_becas(request.user):
            return JsonResponse({"ok": False, "message": f"No tiene permiso para crear {plural}."}, status=403)
        rol = Group.objects.filter(name=nombre_rol).first()
        segmento = None

    if not rol:
        return JsonResponse({"ok": False, "message": "El rol requerido no está configurado."}, status=409)

    return _crear_y_responder(
        request,
        tipo=tipo,
        rol=rol,
        data=request.POST.copy(),
        alcance=alcance_roles_ids(request.user),
        segmento=segmento,
    )
