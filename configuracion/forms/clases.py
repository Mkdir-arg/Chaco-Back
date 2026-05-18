from django import forms


class ClaseActividadForm(forms.Form):
    """Formulario legacy de clases retiradas.

    Se mantiene para compatibilidad de imports mientras no exista el modulo de
    actividades institucionales.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["retirado"] = forms.CharField(
            required=False,
            disabled=True,
            initial="El modulo de clases fue retirado.",
        )
