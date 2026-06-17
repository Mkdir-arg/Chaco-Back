from django import forms
from django.contrib.auth.models import Group

from core import rbac
from programas.models import Programa

_INPUT_CLASS = (
    "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none "
    "focus:ring-2 focus:ring-blue-500 focus:border-transparent"
)


class RolForm(forms.Form):
    """Alta/ediciÃ³n de un Rol = ``Group`` (nombre) + ``RolMeta`` + capacidades."""

    name = forms.CharField(
        max_length=150,
        label="Nombre del rol",
        widget=forms.TextInput(
            attrs={"class": _INPUT_CLASS, "placeholder": "Ej: Operador de legajos"}
        ),
    )
    descripcion = forms.CharField(
        required=False,
        label="DescripciÃ³n",
        widget=forms.Textarea(
            attrs={
                "class": _INPUT_CLASS,
                "rows": 3,
                "placeholder": "QuÃ© puede hacer este rol y para quiÃ©n es.",
            }
        ),
    )
    categoria = forms.ChoiceField(
        choices=rbac.CATEGORIAS_ROL_CHOICES,
        label="CategorÃ­a",
        widget=forms.Select(attrs={"class": _INPUT_CLASS}),
    )
    programa = forms.ModelChoiceField(
        queryset=Programa.objects.all(),
        required=False,
        label="Programa",
        empty_label="â€” SeleccionÃ¡ un programa â€”",
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

        # Modo del formulario segÃºn el operador (admin global vs admin de programa).
        from users.selectors.roles import es_admin_global, programas_administrables

        self.es_admin_global = operador is None or es_admin_global(operador)
        self.programa_fijo = None
        if not self.es_admin_global:
            progs = programas_administrables(operador)
            self.fields["programa"].queryset = progs
            self.fields["programa"].empty_label = None
            # El alcance fija la categorÃ­a en 'Programa' y acota el Ã¡rbol/capacidades.
            # categorÃ­a y (si hay uno solo) programa se fuerzan en clean(), por eso
            # no son required a nivel de campo: el servidor no confÃ­a en el POST.
            self.fields["categoria"].choices = [
                (rbac.CATEGORIA_PROGRAMA, rbac.CATEGORIA_PROGRAMA)
            ]
            self.fields["categoria"].required = False
            self.fields["categoria"].initial = rbac.CATEGORIA_PROGRAMA
            self.fields["capacidades"].choices = [
                (c, c) for c in sorted(rbac.codigos_de_programa())
            ]
            if progs.count() == 1:
                self.programa_fijo = progs.first()
                self.fields["programa"].initial = self.programa_fijo.pk
                self.fields["programa"].required = False
            else:
                self.fields["programa"].required = True

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
        """RN-1 + forzado de alcance para admins de programa.

        Un admin de programa no decide la categorÃ­a ni puede salirse de su
        programa ni tildar capacidades globales: se fuerza en servidor sin
        confiar en el POST.
        """
        cleaned = super().clean()
        if not self.es_admin_global:
            cleaned["categoria"] = rbac.CATEGORIA_PROGRAMA
            if self.programa_fijo is not None:
                cleaned["programa"] = self.programa_fijo
            caps = cleaned.get("capacidades") or []
            cleaned["capacidades"] = [c for c in caps if rbac.es_codigo_de_programa(c)]

        categoria = cleaned.get("categoria")
        programa = cleaned.get("programa")
        if categoria == rbac.CATEGORIA_PROGRAMA and programa is None:
            self.add_error("programa", "Un rol de categorÃ­a 'Programa' requiere seleccionar un Programa.")
        if categoria != rbac.CATEGORIA_PROGRAMA and programa is not None:
            self.add_error("programa", "Solo los roles de categorÃ­a 'Programa' pueden tener un Programa asociado.")
        return cleaned

    def _categoria_actual(self):
        if self.is_bound:
            return self.data.get("categoria")
        return self.fields["categoria"].initial

    def arbol_capacidades(self):
        """Ãrbol por mÃ³dulo con el estado tildado (para renderizar el formulario).

        Se limita a mÃ³dulos "de programa" cuando el rol es de categorÃ­a
        'Programa' o el operador es admin de programa.
        """
        if self.is_bound:
            activos = self.data.getlist("capacidades") if hasattr(self.data, "getlist") else self.data.get("capacidades", [])
        else:
            activos = self.fields["capacidades"].initial or []
        solo_programa = (not self.es_admin_global) or (
            self._categoria_actual() == rbac.CATEGORIA_PROGRAMA
        )
        return rbac.arbol_capacidades(activos, solo_programa=solo_programa)
