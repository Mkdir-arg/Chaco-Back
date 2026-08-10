from django.conf import settings
from django.contrib.auth.views import LoginView
from django.db import transaction

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
