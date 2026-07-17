from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError


class UsuariosAuthenticationForm(AuthenticationForm):
    """Form de login que distingue el usuario inactivo del error de credenciales.

    El ``ModelBackend`` por defecto rechaza a los usuarios inactivos dentro de
    ``authenticate`` (devuelve ``None``), de modo que nunca se llega a
    ``confirm_login_allowed`` y todo cae en el mensaje genérico de credenciales.

    Acá, cuando las credenciales son correctas pero la cuenta está inactiva,
    emitimos un mensaje específico. El estado inactivo solo se revela si la
    contraseña es válida, para no habilitar enumeración de usuarios.
    """

    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": "Credenciales inválidas. Verificá tu correo y contraseña.",
        "inactive": "Tu usuario está inactivo. Contactá a un administrador para que lo reactive.",
    }

    def clean(self):
        username = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")

        if username is not None and password:
            self.user_cache = authenticate(self.request, username=username, password=password)
            if self.user_cache is None:
                if self._credenciales_de_usuario_inactivo(username, password):
                    raise ValidationError(self.error_messages["inactive"], code="inactive")
                raise self.get_invalid_login_error()
            else:
                self.confirm_login_allowed(self.user_cache)

        return self.cleaned_data

    @staticmethod
    def _credenciales_de_usuario_inactivo(username, password):
        """¿La cuenta existe, está inactiva y la contraseña es correcta?"""
        UserModel = get_user_model()
        try:
            user = UserModel._default_manager.get_by_natural_key(username)
        except UserModel.DoesNotExist:
            return False
        return not user.is_active and user.check_password(password)
