from django import forms
from programas.models import Programa
from core.models import Secretaria, Subsecretaria


class ProgramaPaso1Form(forms.Form):
    """Paso 1 — Identidad y jerarquía organizacional."""
    _INPUT = 'block w-full rounded-md border border-gray-300 py-2 px-3 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500'
    _SELECT = 'block w-full rounded-md border border-gray-300 py-2 px-3 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500'

    nombre = forms.CharField(
        max_length=200,
        label='Nombre',
        widget=forms.TextInput(attrs={'placeholder': 'Nombre del programa', 'class': _INPUT}),
    )
    codigo = forms.CharField(
        max_length=50,
        label='Código',
        widget=forms.TextInput(attrs={'placeholder': 'Ej: PROG-001', 'class': _INPUT}),
    )
    descripcion = forms.CharField(
        required=False,
        label='Descripción',
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Descripción breve del programa...', 'class': _INPUT}),
    )
    secretaria = forms.ModelChoiceField(
        queryset=Secretaria.objects.filter(activo=True).order_by('nombre'),
        label='Secretaría',
        empty_label='Seleccionar secretaría...',
        widget=forms.Select(attrs={'class': _SELECT}),
    )
    subsecretaria = forms.ModelChoiceField(
        queryset=Subsecretaria.objects.none(),
        label='Subsecretaría',
        empty_label='Seleccionar subsecretaría...',
        widget=forms.Select(attrs={'class': _SELECT}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'secretaria' in self.data:
            try:
                secretaria_id = int(self.data.get('secretaria'))
                self.fields['subsecretaria'].queryset = Subsecretaria.objects.filter(
                    secretaria_id=secretaria_id, activo=True
                ).order_by('nombre')
            except (ValueError, TypeError):
                pass
        elif self.initial.get('secretaria'):
            self.fields['subsecretaria'].queryset = Subsecretaria.objects.filter(
                secretaria_id=self.initial['secretaria'], activo=True
            ).order_by('nombre')

    def clean_nombre(self):
        nombre = self.cleaned_data['nombre']
        programa_id = self.initial.get('programa_id')
        qs = Programa.objects.filter(nombre=nombre)
        if programa_id:
            qs = qs.exclude(pk=programa_id)
        if qs.exists():
            raise forms.ValidationError('Ya existe un programa con ese nombre.')
        return nombre

    def clean_codigo(self):
        codigo = self.cleaned_data['codigo'].upper()
        programa_id = self.initial.get('programa_id')
        qs = Programa.objects.filter(codigo=codigo)
        if programa_id:
            qs = qs.exclude(pk=programa_id)
        if qs.exists():
            raise forms.ValidationError('Ya existe un programa con ese código.')
        return codigo


class ProgramaPaso2Form(forms.Form):
    """Paso 2 — Naturaleza del programa."""
    naturaleza = forms.ChoiceField(
        choices=Programa.Naturaleza.choices,
        label='Naturaleza',
        widget=forms.RadioSelect(),
    )


class ProgramaPaso3Form(forms.Form):
    """Paso 3 — Capacidades activables: cupo y lista de espera."""
    cupo_maximo = forms.IntegerField(
        required=False,
        min_value=1,
        label='Cupo máximo',
        widget=forms.NumberInput(attrs={
            'placeholder': 'Sin límite si se deja vacío',
            'class': 'w-40 rounded-md border border-gray-300 py-2 px-3 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500',
        }),
    )
    tiene_lista_espera = forms.BooleanField(
        required=False,
        label='Habilitar lista de espera cuando se alcance el cupo',
    )

    def clean(self):
        cleaned = super().clean()
        cupo = cleaned.get('cupo_maximo')
        lista = cleaned.get('tiene_lista_espera')
        if lista and not cupo:
            raise forms.ValidationError(
                'La lista de espera requiere que se configure un cupo máximo.'
            )
        return cleaned


class ProgramaPaso4Form(forms.Form):
    """Paso 4 — Visual: ícono, color y orden de solapa."""
    _INPUT = 'block w-full rounded-md border border-gray-300 py-2 px-3 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500'

    icono = forms.CharField(
        max_length=50,
        label='Ícono',
        initial='folder',
        widget=forms.TextInput(attrs={'placeholder': 'Ej: people, school, assessment', 'class': _INPUT}),
    )
    color = forms.CharField(
        max_length=20,
        label='Color',
        initial='#6366f1',
        widget=forms.TextInput(attrs={'type': 'color', 'class': 'h-10 w-16 rounded border border-gray-300 cursor-pointer'}),
    )
    orden = forms.IntegerField(
        label='Orden de visualización',
        initial=0,
        min_value=0,
        widget=forms.NumberInput(attrs={'placeholder': '0', 'class': 'w-24 rounded-md border border-gray-300 py-2 px-3 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500'}),
    )
