from django.contrib.auth.views import LoginView

from users.forms.auth import UsuariosAuthenticationForm


class UsuariosLoginView(LoginView):
    template_name = "user/login.html"
    authentication_form = UsuariosAuthenticationForm

    def get_success_url(self):
        return super().get_success_url()
