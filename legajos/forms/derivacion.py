from django import forms
from django.db import transaction

from programas.models import DerivacionPrograma, InscripcionPrograma, Programa


class DerivarProgramaForm(forms.Form):
    """Formulario para derivar o inscribir ciudadanos a programas activos."""

    institucion_programa = forms.ModelChoiceField(
        queryset=Programa.objects.none(),
        label='Programa destino',
        empty_label='Seleccionar programa...',
    )
    tipo_inicio = forms.ChoiceField(
        choices=(
            ('derivacion', 'Derivación (requiere aceptación)'),
            ('inscripcion_directa', 'Inscripción directa'),
        ),
        required=False,
        initial='derivacion',
    )
    programa_origen = forms.ModelChoiceField(
        queryset=Programa.objects.none(),
        required=False,
        empty_label='Derivación espontánea',
    )
    motivo = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 4}),
        min_length=6,
        max_length=2000,
    )
    urgencia = forms.ChoiceField(
        choices=DerivacionPrograma.Urgencia.choices,
        initial=DerivacionPrograma.Urgencia.MEDIA,
    )
    observaciones = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 3}),
    )

    def __init__(self, *args, **kwargs):
        self.ciudadano = kwargs.pop('ciudadano')
        self.allow_inscripcion_directa = kwargs.pop('allow_inscripcion_directa', False)
        super().__init__(*args, **kwargs)

        self.fields['institucion_programa'].queryset = Programa.objects.filter(
            estado=Programa.Estado.ACTIVO
        ).order_by('nombre')
        self.fields['programa_origen'].queryset = Programa.objects.filter(
            inscripciones__ciudadano=self.ciudadano,
            inscripciones__estado__in=['ACTIVO', 'EN_SEGUIMIENTO'],
        ).distinct().order_by('nombre')

        if not self.allow_inscripcion_directa:
            self.fields['tipo_inicio'].widget = forms.HiddenInput()
            self.fields['tipo_inicio'].initial = 'derivacion'

        shared_class = 'w-full rounded-lg border border-gray-300 px-3 py-2 focus:border-blue-500 focus:outline-none'
        self.fields['institucion_programa'].widget.attrs.update({'class': shared_class})
        self.fields['tipo_inicio'].widget.attrs.update({'class': shared_class})
        self.fields['programa_origen'].widget.attrs.update({'class': shared_class})
        self.fields['motivo'].widget.attrs.update({'class': shared_class})
        self.fields['urgencia'].widget.attrs.update({'class': shared_class})
        self.fields['observaciones'].widget.attrs.update({'class': shared_class})

    def clean(self):
        cleaned_data = super().clean()
        programa_destino = cleaned_data.get('institucion_programa')
        programa_origen = cleaned_data.get('programa_origen')
        tipo_inicio = cleaned_data.get('tipo_inicio') or 'derivacion'

        if not self.allow_inscripcion_directa:
            tipo_inicio = 'derivacion'
            cleaned_data['tipo_inicio'] = 'derivacion'

        if programa_destino and programa_origen and programa_destino.id == programa_origen.id:
            self.add_error('institucion_programa', 'El programa destino debe ser distinto del origen.')

        if programa_destino and tipo_inicio == 'derivacion':
            existe_pendiente = DerivacionPrograma.objects.filter(
                ciudadano=self.ciudadano,
                programa_destino=programa_destino,
                estado=DerivacionPrograma.Estado.PENDIENTE,
            ).exists()
            if existe_pendiente:
                self.add_error('institucion_programa', 'Ya existe una derivación pendiente hacia este programa.')

        if programa_destino and tipo_inicio == 'inscripcion_directa':
            existe_inscripcion = InscripcionPrograma.objects.filter(
                ciudadano=self.ciudadano,
                programa=programa_destino,
                estado__in=['PENDIENTE', 'ACTIVO', 'EN_SEGUIMIENTO'],
            ).exists()
            if existe_inscripcion:
                self.add_error('institucion_programa', 'El ciudadano ya tiene una inscripción activa o pendiente en este programa.')

        return cleaned_data

    @transaction.atomic
    def save(self, usuario):
        programa_destino = self.cleaned_data['institucion_programa']
        programa_origen = self.cleaned_data.get('programa_origen')
        motivo = self.cleaned_data['motivo'].strip()
        observaciones = (self.cleaned_data.get('observaciones') or '').strip()
        urgencia = self.cleaned_data['urgencia']
        tipo_inicio = self.cleaned_data.get('tipo_inicio', 'derivacion')

        motivo_completo = motivo
        if observaciones:
            motivo_completo = f"{motivo}\n\nObservaciones:\n{observaciones}"

        if tipo_inicio == 'inscripcion_directa':
            inscripcion = InscripcionPrograma.objects.create(
                ciudadano=self.ciudadano,
                programa=programa_destino,
                estado=InscripcionPrograma.Estado.ACTIVO,
                via_ingreso=InscripcionPrograma.ViaIngreso.DIRECTO,
                responsable=usuario,
                notas=motivo_completo,
            )
            return {'tipo': 'inscripcion', 'objeto': inscripcion}

        inscripcion_origen = None
        if programa_origen:
            inscripcion_origen = InscripcionPrograma.objects.filter(
                ciudadano=self.ciudadano,
                programa=programa_origen,
                estado__in=['ACTIVO', 'EN_SEGUIMIENTO'],
            ).first()

        derivacion = DerivacionPrograma.objects.create(
            ciudadano=self.ciudadano,
            programa_origen=programa_origen,
            inscripcion_origen=inscripcion_origen,
            programa_destino=programa_destino,
            motivo=motivo_completo,
            urgencia=urgencia,
            derivado_por=usuario,
        )
        return {'tipo': 'derivacion', 'objeto': derivacion}
