from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from programas.management.commands.seed_becas import ROL_COORDINADOR, ROL_TERRITORIAL
from programas.models import Segmento
from programas.services.autorizacion import es_admin_becas, puede_gestionar_segmento
from users.forms import UserCreationForm
from users.selectors.usuarios import alcance_roles_ids
from users.services.admin import UsuariosAdminService


@login_required
@require_POST
def usuario_alta_rapida(request):
    tipo = request.POST.get("tipo")
    if tipo not in ("coordinador", "territorial"):
        return JsonResponse({"ok": False, "message": "Tipo de usuario inválido."}, status=400)

    if tipo == "coordinador":
        if not es_admin_becas(request.user):
            return JsonResponse({"ok": False, "message": "No tiene permiso para crear coordinadores."}, status=403)
        rol = Group.objects.filter(name=ROL_COORDINADOR).first()
        segmento = None
    else:
        rol = Group.objects.filter(name=ROL_TERRITORIAL).first()
        segmento = Segmento.objects.filter(pk=request.POST.get("segmento_id"), activo=True).first()
        if not segmento or not puede_gestionar_segmento(request.user, segmento):
            return JsonResponse({"ok": False, "message": "Seleccioná un segmento permitido."}, status=403)

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
    return JsonResponse(
        {
            "ok": True,
            "user": {
                "id": usuario.pk,
                "label": usuario.get_full_name() or usuario.username,
                "segmento_id": segmento.pk if segmento else None,
            },
        }
    )
