from django import forms
from django.contrib.auth.models import Group

from core import rbac

_INPUT_CLASS = (
    "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none "
    "focus:ring-2 focus:ring-blue-500 focus:border-transparent"
)


class RolForm(forms.Form):
    """Alta/edición de un Rol = ``Group`` (nombre) + ``RolMeta`` + capacidades."""

    name = forms.CharField(
        max_length=150,
        label="Nombre del rol",
        widget=forms.TextInput(
            attrs={"class": _INPUT_CLASS, "placeholder": "Ej: Operador de legajos"}
        ),
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
    capacidades = forms.MultipleChoiceField(
        required=False,
        label="Capacidades",
        choices=[(c, c) for c in rbac.codigos_de_capacidad()],
        widget=forms.CheckboxSelectMultiple,
    )

    def __init__(self, *args, instance=None, **kwargs):
        self.instance = instance  # Group o None
        super().__init__(*args, **kwargs)
        if instance is not None and not self.is_bound:
            self.fields["name"].initial = instance.name
            meta = getattr(instance, "meta", None)
            if meta is not None:
                self.fields["descripcion"].initial = meta.descripcion
                self.fields["categoria"].initial = meta.categoria
            self.fields["capacidades"].initial = rbac.capacidades_de_grupo(instance)

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        qs = Group.objects.filter(name__iexact=name)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Ya existe un rol con ese nombre.")
        return name

    def arbol_capacidades(self):
        """Árbol por módulo con el estado tildado (para renderizar el formulario)."""
        if self.is_bound:
            activos = self.data.getlist("capacidades") if hasattr(self.data, "getlist") else self.data.get("capacidades", [])
        else:
            activos = self.fields["capacidades"].initial or []
        return rbac.arbol_capacidades(activos)
