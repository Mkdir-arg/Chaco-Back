from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.views import (
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views import View

from core.rbac import es_ciudadano_portal

from ..forms import (
    CiudadanoLoginForm,
    CiudadanoPasswordResetForm,
    RegistroStep1Form,
    RegistroStep2Form,
)
from ..services.ciudadano_auth import (
    RegistroCiudadanoCuentaExistenteError,
    RegistroCiudadanoIdentidadNoVerificadaError,
    RegistroCiudadanoLegajoYaVinculadoError,
    RegistroCiudadanoServicioNoDisponibleError,
    RegistroCiudadanoSesionInvalidaError,
    completar_registro_ciudadano,
    limpiar_login_fallido,
    login_bloqueado,
    preparar_registro_ciudadano,
    registrar_login_fallido,
)


def _get_client_ip(request):
    x_forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded:
        return x_forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


class CiudadanoLoginView(View):
    template_name = "portal/ciudadano/login.html"

    def get(self, request):
        if es_ciudadano_portal(request.user):
            return redirect("portal:ciudadano_mi_perfil")
        return render(request, self.template_name, {"form": CiudadanoLoginForm()})

    def post(self, request):
        ip = _get_client_ip(request)
        if login_bloqueado(ip):
            messages.error(request, "Demasiados intentos fallidos. Intentá de nuevo en 5 minutos.")
            return render(request, self.template_name, {"form": CiudadanoLoginForm(), "bloqueado": True})

        form = CiudadanoLoginForm(request, data=request.POST)
        if form.is_valid():
            limpiar_login_fallido(ip)
            login(request, form.get_user())
            return redirect("portal:ciudadano_mi_perfil")

        registrar_login_fallido(ip)
        return render(request, self.template_name, {"form": form})


class CiudadanoLogoutView(View):
    def post(self, request):
        logout(request)
        return redirect("portal:ciudadano_login")


class RegistroStep1View(View):
    template_name = "portal/ciudadano/registro_step1.html"

    def get(self, request):
        return render(request, self.template_name, {"form": RegistroStep1Form()})

    def post(self, request):
        form = RegistroStep1Form(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})

        try:
            request.session["registro_ciudadano"] = preparar_registro_ciudadano(
                dni=form.cleaned_data["dni"],
                genero=form.cleaned_data["genero"],
            )
        except RegistroCiudadanoCuentaExistenteError:
            messages.info(request, "Ya tenés una cuenta registrada. Iniciá sesión con tu DNI y contraseña.")
            return redirect("portal:ciudadano_login")
        except RegistroCiudadanoIdentidadNoVerificadaError:
            form.add_error("dni", "No pudimos verificar tu identidad. Verificá los datos ingresados.")
            return render(request, self.template_name, {"form": form})
        except RegistroCiudadanoServicioNoDisponibleError:
            form.add_error(None, "El servicio de verificación no está disponible. Intentá más tarde.")
            return render(request, self.template_name, {"form": form})

        return redirect("portal:ciudadano_registro_step2")


class RegistroStep2View(View):
    template_name = "portal/ciudadano/registro_step2.html"

    def get(self, request):
        datos = request.session.get("registro_ciudadano")
        if not datos:
            return redirect("portal:ciudadano_registro_step1")
        return render(request, self.template_name, {"form": RegistroStep2Form(), "datos": datos})

    def post(self, request):
        datos = request.session.get("registro_ciudadano")
        if not datos:
            return redirect("portal:ciudadano_registro_step1")

        form = RegistroStep2Form(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form, "datos": datos})

        try:
            user, ciudadano = completar_registro_ciudadano(
                datos_registro=datos,
                email=form.cleaned_data["email"],
                telefono=form.cleaned_data["telefono"],
                password=form.cleaned_data["password1"],
            )
        except RegistroCiudadanoSesionInvalidaError:
            return redirect("portal:ciudadano_registro_step1")
        except RegistroCiudadanoCuentaExistenteError:
            messages.error(request, "Ya existe una cuenta con ese DNI.")
            return redirect("portal:ciudadano_login")
        except RegistroCiudadanoLegajoYaVinculadoError:
            messages.error(request, "Este legajo ya tiene una cuenta asociada. Iniciá sesión.")
            request.session.pop("registro_ciudadano", None)
            return redirect("portal:ciudadano_login")

        request.session.pop("registro_ciudadano", None)
        login(request, user)
        messages.success(request, f"¡Bienvenido/a, {ciudadano.nombre}! Tu cuenta fue creada correctamente.")
        return redirect("portal:ciudadano_mi_perfil")


class CiudadanoPasswordResetView(PasswordResetView):
    form_class = CiudadanoPasswordResetForm
    template_name = "portal/ciudadano/password_reset.html"
    email_template_name = "portal/ciudadano/email/password_reset_body.html"
    subject_template_name = "portal/ciudadano/email/password_reset_subject.txt"
    success_url = reverse_lazy("portal:ciudadano_password_reset_done")


class CiudadanoPasswordResetDoneView(PasswordResetDoneView):
    template_name = "portal/ciudadano/password_reset_done.html"


class CiudadanoPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = "portal/ciudadano/password_reset_confirm.html"
    success_url = reverse_lazy("portal:ciudadano_password_reset_complete")


class CiudadanoPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = "portal/ciudadano/password_reset_complete.html"
