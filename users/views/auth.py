from django.conf import settings
from django.contrib import messages
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, PasswordChangeView
from django.db import transaction
from django.urls import reverse_lazy

from users.forms.auth import UsuariosAuthenticationForm
from users.models import Profile


class UsuariosLoginView(LoginView):
    template_name = "user/login.html"
    authentication_form = UsuariosAuthenticationForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        response = super().form_valid(form)

        # La sesión web que acaba de autenticarse reemplaza a cualquier sesión
        # anterior. El bloqueo hace determinista el resultado ante dos ingresos
        # casi simultáneos del mismo usuario.
        with transaction.atomic():
            profile, _ = Profile.objects.get_or_create(user=form.get_user())
            profile = Profile.objects.select_for_update().get(pk=profile.pk)
            profile.backoffice_session_key = self.request.session.session_key
            profile.save(update_fields=["backoffice_session_key"])

        if form.cleaned_data["remember"]:
            self.request.session.set_expiry(settings.SESSION_COOKIE_AGE)
        else:
            self.request.session.set_expiry(0)
        return response

    def get_success_url(self):
        return super().get_success_url()


class CambioContrasenaObligatorioView(LoginRequiredMixin, PasswordChangeView):
    """Primer ingreso con clave provisoria: no se opera hasta cambiarla (RN-C2).

    Usa ``SetPasswordForm`` y no ``PasswordChangeForm``: el usuario acaba de
    autenticarse con la clave provisoria, pedírsela de nuevo no agrega seguridad.
    """

    template_name = "user/cambiar_contrasena_obligatorio.html"
    form_class = SetPasswordForm
    success_url = reverse_lazy("core:inicio")

    def form_valid(self, form):
        # super() rota la sesión (update_session_auth_hash). Si no reflejamos la
        # clave nueva en el Profile, BackofficeSingleSessionMiddleware lee la
        # sesión como "reemplazada" y expulsa al usuario recién validado.
        response = super().form_valid(form)
        Profile.objects.filter(user=self.request.user).update(
            debe_cambiar_contrasena=False,
            backoffice_session_key=self.request.session.session_key,
        )
        messages.success(self.request, "Tu contraseña fue actualizada.")
        return response
