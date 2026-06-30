from django import forms
from django.contrib.auth.models import Group

from core import rbac
from programas.models import Programa

_INPUT_CLASS = (
    "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none "
    "focus:ring-2 focus:ring-blue-500 focus:border-transparent"
)


class RolForm(forms.Form):
    """Alta/edición de un Rol = ``Group`` (nombre) + ``RolMeta`` + capacidades."""

    name = forms.CharField(
        max_length=150,
        label="Nombre del rol",
        widget=forms.TextInput(attrs={"class": _INPUT_CLASS, "placeholder": "Ej: Operador de legajos"}),
    )
    descripcion = forms.CharField(
        required=False,
        label="Descripción",
        widget=forms.Textarea(
            attrs={
                "class": _INPUT_CLASS,
                "rows": 3,
                "placeholder": "Qué puede hacer este rol y para quién es.",
            }
        ),
    )
    categoria = forms.ChoiceField(
        choices=rbac.CATEGORIAS_ROL_CHOICES,
        label="Categoría",
        widget=forms.Select(attrs={"class": _INPUT_CLASS}),
    )
    programa = forms.ModelChoiceField(
        queryset=Programa.objects.all(),
        required=False,
        label="Programa",
        empty_label="— Seleccioná un programa —",
        widget=forms.Select(attrs={"class": _INPUT_CLASS}),
    )
    capacidades = forms.MultipleChoiceField(
        required=False,
        label="Capacidades",
        choices=[(c, c) for c in rbac.codigos_de_capacidad()],
        widget=forms.CheckboxSelectMultiple,
    )

    def __init__(self, *args, instance=None, operador=None, **kwargs):
        self.instance = instance  # Group o None
        self.operador = operador
        super().__init__(*args, **kwargs)

        # Modo del formulario según el operador (admin global vs admin de programa).
        from users.selectors.roles import es_admin_global, programas_administrables

        self.es_admin_global = operador is None or es_admin_global(operador)
        self.programa_fijo = None
        if not self.es_admin_global:
            progs = programas_administrables(operador)
            self.fields["programa"].queryset = progs
            self.fields["programa"].empty_label = None
            self.fields["categoria"].choices = [
                (rbac.CATEGORIA_NACHEC, rbac.CATEGORIA_NACHEC),
                (rbac.CATEGORIA_BECAS, rbac.CATEGORIA_BECAS),
            ]
            self.fields["categoria"].required = True
            self.fields["categoria"].initial = rbac.CATEGORIA_BECAS
            self.fields["capacidades"].choices = [(c, c) for c in sorted(rbac.codigos_de_programa())]
            self.fields["programa"].required = False
            if progs.count() == 1:
                self.programa_fijo = progs.first()
                self.fields["programa"].initial = self.programa_fijo.pk

        if instance is not None and not self.is_bound:
            self.fields["name"].initial = instance.name
            meta = getattr(instance, "meta", None)
            if meta is not None:
                self.fields["descripcion"].initial = meta.descripcion
                self.fields["categoria"].initial = meta.categoria
                self.fields["programa"].initial = meta.programa_id
            self.fields["capacidades"].initial = rbac.capacidades_de_grupo(instance)

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        qs = Group.objects.filter(name__iexact=name)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Ya existe un rol con ese nombre.")
        return name

    def clean(self):
        """Forzado de alcance para admins de programa (server-side, sin confiar en el POST)."""
        cleaned = super().clean()
        if not self.es_admin_global:
            if self.programa_fijo is not None:
                cleaned["programa"] = self.programa_fijo
            caps = cleaned.get("capacidades") or []
            cleaned["capacidades"] = [c for c in caps if rbac.es_codigo_de_programa(c)]
        return cleaned

    def _activos(self):
        if self.is_bound:
            return (
                self.data.getlist("capacidades") if hasattr(self.data, "getlist") else self.data.get("capacidades", [])
            )
        return self.fields["capacidades"].initial or []

    def arbol_capacidades(self):
        """Árbol plano por módulo (retrocompatibilidad)."""
        return rbac.arbol_capacidades(self._activos(), solo_programa=not self.es_admin_global)

    def arbol_por_tabs(self):
        """Árbol agrupado por tab para el panel de capacidades."""
        return rbac.arbol_por_tabs(self._activos(), solo_programa=not self.es_admin_global)
