from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, PasswordResetForm
from django.contrib.auth.models import User

from core.rbac import es_ciudadano_portal
from legajos.models import Ciudadano


class CiudadanoLoginForm(AuthenticationForm):
    username = forms.CharField(
        label="DNI",
        widget=forms.TextInput(attrs={"placeholder": "Ingresá tu DNI", "autofocus": True}),
    )
    password = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(attrs={"placeholder": "Ingresá tu contraseña"}),
    )

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not es_ciudadano_portal(user):
            raise forms.ValidationError(
                "Este acceso es exclusivo para ciudadanos.",
                code="no_ciudadano",
            )


class RegistroStep1Form(forms.Form):
    dni = forms.CharField(
        label="DNI",
        max_length=10,
        widget=forms.TextInput(attrs={"placeholder": "Sin puntos ni guiones"}),
    )
    genero = forms.ChoiceField(
        label="Género",
        choices=[("M", "Masculino"), ("F", "Femenino"), ("X", "No binario / Otro")],
    )

    def clean_dni(self):
        dni = self.cleaned_data["dni"].strip().replace(".", "").replace("-", "")
        if not dni.isdigit():
            raise forms.ValidationError("El DNI debe contener solo números.")
        if len(dni) < 6 or len(dni) > 9:
            raise forms.ValidationError("El DNI ingresado no es válido.")
        return dni


class RegistroStep2Form(forms.Form):
    """Paso 2: completar datos y elegir contraseña."""

    email = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={"placeholder": "tu@email.com"}),
    )
    telefono = forms.CharField(
        label="Teléfono",
        required=False,
        max_length=20,
        widget=forms.TextInput(attrs={"placeholder": "Opcional"}),
    )
    password1 = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(attrs={"placeholder": "Mínimo 8 caracteres"}),
    )
    password2 = forms.CharField(
        label="Confirmar contraseña",
        widget=forms.PasswordInput(attrs={"placeholder": "Repetí tu contraseña"}),
    )

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Este email ya está registrado.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get("password1")
        p2 = cleaned_data.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Las contraseñas no coinciden.")
        if p1 and len(p1) < 8:
            self.add_error("password1", "La contraseña debe tener al menos 8 caracteres.")
        return cleaned_data


class CiudadanoEditarDatosForm(forms.ModelForm):
    telefono = forms.CharField(
        label="Teléfono",
        required=False,
        max_length=40,
        widget=forms.TextInput(attrs={"placeholder": "Ej: 2664-123456"}),
    )
    domicilio = forms.CharField(
        label="Domicilio",
        required=False,
        max_length=240,
        widget=forms.TextInput(attrs={"placeholder": "Calle, número, barrio"}),
    )

    class Meta:
        model = Ciudadano
        fields = ["telefono", "domicilio"]


class CiudadanoCambioEmailForm(forms.Form):
    nuevo_email = forms.EmailField(
        label="Nuevo email",
        widget=forms.EmailInput(attrs={"placeholder": "tu@nuevo-email.com"}),
    )

    def clean_nuevo_email(self):
        email = self.cleaned_data["nuevo_email"]
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Este email ya está en uso.")
        return email


class CiudadanoCambioPasswordForm(PasswordChangeForm):
    old_password = forms.CharField(
        label="Contraseña actual",
        widget=forms.PasswordInput(attrs={"placeholder": "Tu contraseña actual", "autofocus": True}),
    )
    new_password1 = forms.CharField(
        label="Nueva contraseña",
        widget=forms.PasswordInput(attrs={"placeholder": "Mínimo 8 caracteres"}),
    )
    new_password2 = forms.CharField(
        label="Confirmar nueva contraseña",
        widget=forms.PasswordInput(attrs={"placeholder": "Repetí la nueva contraseña"}),
    )


class CiudadanoPasswordResetForm(PasswordResetForm):
    """Solo resetea contraseñas de usuarios del grupo Ciudadanos."""

    def get_users(self, email):
        active_users = User.objects.filter(email__iexact=email, is_active=True)
        return (u for u in active_users if es_ciudadano_portal(u))


class CiudadanoNuevaConsultaForm(forms.Form):
    motivo = forms.CharField(
        label="Motivo de la consulta",
        min_length=10,
        max_length=2000,
        widget=forms.Textarea(attrs={"rows": 5}),
    )

    def clean_motivo(self):
        return self.cleaned_data["motivo"].strip()


class CiudadanoEnviarMensajeForm(forms.Form):
    texto = forms.CharField(
        label="Mensaje",
        max_length=2000,
        widget=forms.Textarea(attrs={"rows": 2}),
    )

    def clean_texto(self):
        return self.cleaned_data["texto"].strip()
