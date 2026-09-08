import logging

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from programas.management.commands.seed_becas import (
    ROL_COORDINADOR,
    ROL_COORDINADOR_REGIONAL,
    ROL_TERRITORIAL,
)
from programas.models import Segmento
from programas.services.autorizacion import es_admin_becas, puede_gestionar_segmento
from users.forms import UserCreationForm
from users.selectors.usuarios import alcance_roles_ids
from users.services.admin import UsuariosAdminService
from users.services.correo import entregar_credenciales_provisorias

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


@login_required
@require_POST
def usuario_alta_rapida(request):
    tipo = request.POST.get("tipo")
    if tipo not in ROLES_BACKOFFICE and tipo != "territorial":
        return JsonResponse({"ok": False, "message": "Tipo de usuario inválido."}, status=400)

    if tipo == "territorial":
        rol = Group.objects.filter(name=ROL_TERRITORIAL).first()
        segmento = Segmento.objects.filter(pk=request.POST.get("segmento_id"), activo=True).first()
        if not segmento or not puede_gestionar_segmento(request.user, segmento):
            return JsonResponse({"ok": False, "message": "Seleccioná un segmento permitido."}, status=403)
    else:
        nombre_rol, plural = ROLES_BACKOFFICE[tipo]
        if not es_admin_becas(request.user):
            return JsonResponse({"ok": False, "message": f"No tiene permiso para crear {plural}."}, status=403)
        rol = Group.objects.filter(name=nombre_rol).first()
        segmento = None

    if not rol:
        return JsonResponse({"ok": False, "message": "El rol requerido no está configurado."}, status=409)

    data = request.POST.copy()
    data.setlist("groups", [str(rol.pk)])
    if segmento:
        data["segmento_territorial"] = str(segmento.pk)
    form = UserCreationForm(data=data, operador=request.user)
    if not form.is_valid():
        errores = {campo: [str(error) for error in lista] for campo, lista in form.errors.items()}
        return JsonResponse({"ok": False, "errors": errores}, status=400)

    usuario = UsuariosAdminService.create_user_from_form(form, alcance_group_ids=alcance_roles_ids(request.user))

    # Mismo criterio que el ABM de usuarios: con correo, la clave la genera el
    # sistema y viaja en el mensaje (RN-C1); sin correo, queda la que tipeó el
    # operador y se la entrega por otra vía.
    aviso = ""
    if usuario.email:
        try:
            entregar_credenciales_provisorias(usuario, request, rol=rol.name)
            aviso = "Se envió el correo con la clave provisoria."
        except Exception:
            logger.exception("El usuario fue creado, pero no se pudo enviar la clave provisoria")
            aviso = 'No se pudo enviar el correo: el usuario puede entrar con "Olvidé mi contraseña".'
    else:
        aviso = "Sin correo: entregale la contraseña provisoria por otra vía."

    return JsonResponse(
        {
            "ok": True,
            "message": aviso,
            "user": {
                "id": usuario.pk,
                "label": usuario.get_full_name() or usuario.username,
                "segmento_id": segmento.pk if segmento else None,
            },
        }
    )
