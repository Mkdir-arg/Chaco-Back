from django.conf import settings
from django.contrib import messages
from django.contrib.auth.forms import PasswordChangeForm, SetPasswordForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import (
    LoginView,
    PasswordChangeView,
    PasswordResetConfirmView,
    PasswordResetView,
)
from django.db import transaction
from django.shortcuts import redirect
from django.urls import reverse_lazy

from core.services.throttle import rate_limit_excedido
from users.forms.auth import UsuariosAuthenticationForm
from users.models import Profile

#: SEC-26 · cubetas del recupero de contraseña. Igual que en el login, la cubeta
#: que frena el ataque dirigido es la del correo tipeado (sin IP); la de IP evita
#: que una sola máquina use el formulario como cañón de correo.
RECUPERO_VENTANA_SEGUNDOS = 3600
RECUPERO_MAX_POR_CORREO = 5
RECUPERO_MAX_POR_IP = 20


class UsuariosLoginView(LoginView):
    template_name = "user/login.html"
    authentication_form = UsuariosAuthenticationForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        response = super().form_valid(form)

        # La sesión web que acaba de autenticarse reemplaza a cualquier sesión
        # anterior. El bloqueo hace determinista el resultado ante dos ingresos
        # casi simultáneos del mismo usuario: el FOR UPDATE va en la misma lectura
        # del get_or_create (si el perfil no existe, se crea dentro de esta
        # transacción), sin releer la fila recién obtenida.
        with transaction.atomic():
            profile, _ = Profile.objects.select_for_update().get_or_create(user=form.get_user())
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

    **G2-03:** por eso mismo la pantalla solo existe mientras la clave provisoria
    esté sin cambiar. Sin el gate, cualquier sesión abierta —un `fetch` desde el
    XSS de SEC-08, una PC compartida— cambiaba la clave *sin conocer la actual* y
    se quedaba con la cuenta para siempre. El cambio voluntario va por
    :class:`CambioContrasenaVoluntarioView`, que sí pide la clave actual.
    """

    template_name = "user/cambiar_contrasena_obligatorio.html"
    form_class = SetPasswordForm
    success_url = reverse_lazy("core:inicio")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            # El Profile lo dejó en la caché `BackofficeSingleSessionMiddleware`:
            # leerlo acá no agrega consultas (RED-52).
            perfil = getattr(request.user, "profile", None)
            if perfil is None or not perfil.debe_cambiar_contrasena:
                return redirect("users:cambiar_contrasena")
        return super().dispatch(request, *args, **kwargs)

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


class CambioContrasenaVoluntarioView(LoginRequiredMixin, PasswordChangeView):
    """Cambio de clave a pedido del propio usuario: **exige la clave actual**.

    Reemplaza a ``/password_change/`` de ``django.contrib.auth.urls``, que SEC-26
    sacó de la raíz del URLconf. Aquel flujo no tenía plantilla propia ni link en
    ninguna pantalla, pero contestaba igual: un POST válido cambiaba la clave y
    redirigía sin renderizar nada.
    """

    template_name = "user/cambiar_contrasena.html"
    form_class = PasswordChangeForm
    success_url = reverse_lazy("core:inicio")

    def form_valid(self, form):
        # Misma razón que en la pantalla obligatoria: `update_session_auth_hash`
        # rota la sesión y el Profile tiene que acompañarla.
        response = super().form_valid(form)
        Profile.objects.filter(user=self.request.user).update(
            backoffice_session_key=self.request.session.session_key,
        )
        messages.success(self.request, "Tu contraseña fue actualizada.")
        return response


class RecuperarContrasenaView(PasswordResetView):
    """«Olvidé mi contraseña» del backoffice, con límite de intentos (SEC-26).

    Cuando la cubeta se agota **no se manda el correo y la respuesta es la misma**
    de siempre: la pantalla de confirmación no revela si la dirección existe, y
    tampoco tiene que revelar si alguien la está usando de cañón de correo.
    """

    def form_valid(self, form):
        correo = (form.cleaned_data.get("email") or "").strip().lower()
        excedido = rate_limit_excedido(
            self.request, "recupero_ip", RECUPERO_MAX_POR_IP, RECUPERO_VENTANA_SEGUNDOS
        ) or rate_limit_excedido(
            self.request,
            "recupero_correo",
            RECUPERO_MAX_POR_CORREO,
            RECUPERO_VENTANA_SEGUNDOS,
            sufijo=correo,
            incluir_ip=False,
        )
        if excedido:
            return super(PasswordResetView, self).form_valid(form)
        return super().form_valid(form)


class EstablecerContrasenaView(PasswordResetConfirmView):
    """Alta de clave por link de un solo uso; también **libera la clave provisoria**.

    Es el otro extremo de D-26: al territorial de la app no se le manda una clave
    provisoria en texto plano (nunca va a pisar la pantalla del backoffice que lo
    obligaría a cambiarla), se le manda este link. Sin limpiar el flag acá, la
    cuenta quedaba marcada «debe cambiar la contraseña» para siempre.
    """

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.user is not None:
            Profile.objects.filter(user=self.user).update(debe_cambiar_contrasena=False)
        return response
