from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.shortcuts import redirect, render

from core.decorators import ciudadano_required

from ..forms import (
    CiudadanoCambioEmailForm,
    CiudadanoCambioPasswordForm,
    CiudadanoEditarDatosForm,
)
from ..selectors import (
    get_ciudadano_perfil_context,
    get_ciudadano_programa_derivaciones,
    get_ciudadano_programa_detalle_or_404,
    get_ciudadano_programas_context,
)
from ..services.ciudadano_perfil import (
    CambioEmailExpiradoError,
    CambioEmailInvalidoError,
    confirmar_cambio_email,
    crear_solicitud_cambio_email,
)


@ciudadano_required
def ciudadano_mi_perfil(request):
    ciudadano = request.user.ciudadano_perfil
    context = {"ciudadano": ciudadano}
    context.update(get_ciudadano_perfil_context(user=request.user, ciudadano=ciudadano))
    return render(request, "portal/ciudadano/mi_perfil.html", context)


@ciudadano_required
def ciudadano_mis_programas(request):
    ciudadano = request.user.ciudadano_perfil
    context = {"ciudadano": ciudadano}
    context.update(get_ciudadano_programas_context(ciudadano))
    return render(request, "portal/ciudadano/mis_programas.html", context)


@ciudadano_required
def ciudadano_programa_detalle(request, pk):
    ciudadano = request.user.ciudadano_perfil
    inscripcion = get_ciudadano_programa_detalle_or_404(ciudadano, pk)
    return render(
        request,
        "portal/ciudadano/programa_detalle.html",
        {
            "ciudadano": ciudadano,
            "inscripcion": inscripcion,
            "derivaciones": get_ciudadano_programa_derivaciones(ciudadano, inscripcion.programa),
        },
    )


@ciudadano_required
def ciudadano_mis_datos(request):
    ciudadano = request.user.ciudadano_perfil
    form = CiudadanoEditarDatosForm(request.POST or None, instance=ciudadano)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Tus datos fueron actualizados correctamente.")
        return redirect("portal:ciudadano_mis_datos")

    return render(
        request,
        "portal/ciudadano/mis_datos.html",
        {
            "ciudadano": ciudadano,
            "form": form,
        },
    )


@ciudadano_required
def ciudadano_cambio_email(request):
    ciudadano = request.user.ciudadano_perfil
    form = CiudadanoCambioEmailForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        crear_solicitud_cambio_email(
            request=request,
            user=request.user,
            nuevo_email=form.cleaned_data["nuevo_email"],
        )
        messages.success(
            request,
            f"Te enviamos un email a {form.cleaned_data['nuevo_email']} para confirmar el cambio.",
        )
        return redirect("portal:ciudadano_mis_datos")

    return render(
        request,
        "portal/ciudadano/cambio_email.html",
        {
            "ciudadano": ciudadano,
            "form": form,
        },
    )


def ciudadano_confirmar_email(request, token):
    try:
        confirmar_cambio_email(token=token)
    except CambioEmailInvalidoError:
        messages.error(request, "El enlace de confirmación no es válido.")
        return redirect("portal:ciudadano_login")
    except CambioEmailExpiradoError:
        messages.error(request, "Este enlace expiró. Solicitá un nuevo cambio de email.")
        return redirect("portal:ciudadano_login")

    messages.success(request, "Tu email fue actualizado correctamente.")
    return redirect("portal:ciudadano_mis_datos")


@ciudadano_required
def ciudadano_cambio_password(request):
    ciudadano = request.user.ciudadano_perfil
    form = CiudadanoCambioPasswordForm(request.user, request.POST or None)

    if request.method == "POST" and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        messages.success(request, "Tu contraseña fue cambiada correctamente.")
        return redirect("portal:ciudadano_mis_datos")

    return render(
        request,
        "portal/ciudadano/cambio_password.html",
        {
            "ciudadano": ciudadano,
            "form": form,
        },
    )
