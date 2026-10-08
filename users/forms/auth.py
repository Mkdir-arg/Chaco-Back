from django import forms
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError

from core import rbac
from core.services.throttle import (
    auth_ip_bloqueada,
    rate_limit_bloqueado,
    rate_limit_excedido,
    registrar_auth_fallida_por_ip,
)

#: SEC-26 · cubetas del login del backoffice.
#:
#: Son **dos** y se comportan distinto a propósito.
#:
#: La de **usuario** (acá) es la que ve la fuerza bruta distribuida: no mira la IP
#: (``incluir_ip=False``), así que rotar de proxy no devuelve la cuota. Pero por
#: eso mismo la llena **cualquiera**, con solo tipear el usuario de otro: por eso
#: se consulta recién **después** de autenticar y solo si la credencial estaba
#: mal. El dueño con su clave correcta entra siempre, esté la cubeta como esté.
#: Antes se preguntaba antes de autenticar, y diez POST bastaban para dejar diez
#: minutos afuera a cualquier persona del sistema.
#:
#: La de **IP** vive en ``core.services.throttle`` (``AUTH_FALLIDOS_MAX_POR_IP``,
#: compartida con la app de campo) y es la única que frena antes de verificar la
#: clave: la paga quien ataca, no la cuenta atacada.
#:
#: En las dos, solo cuentan los intentos **fallidos**: en una repartición el
#: backoffice sale por una IP única y decenas de personas entran a la misma hora;
#: cobrarle una ficha al que acierta la clave dejaría afuera a una oficina entera.
LOGIN_VENTANA_SEGUNDOS = 600
LOGIN_MAX_POR_USUARIO = 10


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
            # Lo único que se rechaza sin mirar la clave: el techo de la IP.
            if auth_ip_bloqueada(self.request):
                raise ValidationError(self.error_messages["demasiados_intentos"], code="demasiados_intentos")
            self.user_cache = authenticate(self.request, username=username, password=password)
            if self.user_cache is not None:
                self.confirm_login_allowed(self.user_cache)
                return self.cleaned_data
            # Recién acá se mira la cubeta del usuario: la credencial estaba mal.
            self._registrar_intento_fallido(username)
            if self._intentos_de_usuario_agotados(username):
                raise ValidationError(self.error_messages["demasiados_intentos"], code="demasiados_intentos")
            if self._credenciales_de_usuario_inactivo(username, password):
                raise ValidationError(self.error_messages["inactive"], code="inactive")
            raise self.get_invalid_login_error()

        return self.cleaned_data

    def _intentos_de_usuario_agotados(self, username):
        if self.request is None:  # formulario instanciado fuera de una vista
            return False
        return rate_limit_bloqueado(
            self.request, "login_usuario", LOGIN_MAX_POR_USUARIO, sufijo=username.lower(), incluir_ip=False
        )

    def _registrar_intento_fallido(self, username):
        if self.request is None:
            return
        registrar_auth_fallida_por_ip(self.request)
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
