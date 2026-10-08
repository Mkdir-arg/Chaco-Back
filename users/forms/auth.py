from django import forms
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError

from core import rbac
from core.services.throttle import rate_limit_bloqueado, rate_limit_excedido

#: SEC-26 · cubetas del login del backoffice.
#:
#: Son **dos**, y la que importa es la de usuario: una fuerza bruta distribuida
#: cambia de IP en cada intento, así que una cubeta por IP sola no la ve. La de
#: usuario no mira la IP (``incluir_ip=False``), de modo que rotar de proxy no
#: devuelve la cuota.
#:
#: Solo cuentan los intentos **fallidos**: en una repartición el backoffice sale
#: por una IP única y decenas de personas entran a la misma hora; cobrarle una
#: ficha al que acierta la clave dejaría afuera a una oficina entera. Por eso la
#: cubeta por IP es más holgada que la de usuario, que es la que frena el ataque
#: dirigido a una cuenta.
LOGIN_VENTANA_SEGUNDOS = 600
LOGIN_MAX_POR_USUARIO = 10
LOGIN_MAX_POR_IP = 30


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
        "invalid_login": "Credenciales inválidas. Verificá tu usuario y contraseña.",
        "inactive": "Tu usuario está inactivo. Contactá a un administrador para que lo reactive.",
        "territorial_mobile_only": "Usuario no válido para ingresar al sistema.",
        "demasiados_intentos": ("Demasiados intentos fallidos. Esperá unos minutos antes de volver a probar."),
    }

    remember = forms.BooleanField(required=False, label="Recordarme")

    def clean(self):
        username = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")

        if username is not None and password:
            if self._intentos_agotados(username):
                raise ValidationError(self.error_messages["demasiados_intentos"], code="demasiados_intentos")
            self.user_cache = authenticate(self.request, username=username, password=password)
            if self.user_cache is None:
                self._registrar_intento_fallido(username)
                if self._credenciales_de_usuario_inactivo(username, password):
                    raise ValidationError(self.error_messages["inactive"], code="inactive")
                raise self.get_invalid_login_error()
            else:
                self.confirm_login_allowed(self.user_cache)

        return self.cleaned_data

    def _intentos_agotados(self, username):
        if self.request is None:  # formulario instanciado fuera de una vista
            return False
        return rate_limit_bloqueado(self.request, "login_ip", LOGIN_MAX_POR_IP) or rate_limit_bloqueado(
            self.request, "login_usuario", LOGIN_MAX_POR_USUARIO, sufijo=username.lower(), incluir_ip=False
        )

    def _registrar_intento_fallido(self, username):
        if self.request is None:
            return
        rate_limit_excedido(self.request, "login_ip", LOGIN_MAX_POR_IP, LOGIN_VENTANA_SEGUNDOS)
        rate_limit_excedido(
            self.request,
            "login_usuario",
            LOGIN_MAX_POR_USUARIO,
            LOGIN_VENTANA_SEGUNDOS,
            sufijo=username.lower(),
            incluir_ip=False,
        )

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if rbac.es_solo_campo(user):
            raise ValidationError(
                self.error_messages["territorial_mobile_only"],
                code="territorial_mobile_only",
            )

    @staticmethod
    def _credenciales_de_usuario_inactivo(username, password):
        """¿La cuenta existe, está inactiva y la contraseña es correcta?"""
        UserModel = get_user_model()
        try:
            user = UserModel._default_manager.get_by_natural_key(username)
        except UserModel.DoesNotExist:
            return False
        return not user.is_active and user.check_password(password)
