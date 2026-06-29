"""Formularios del backoffice del Programa Becas (#74 / #76)."""
from django import forms
from django.contrib.auth.models import User
from django.db import models

from programas.models import (
    AsignacionCoordinador,
    Convocatoria,
    Formulario,
    PreguntaGlobal,
    Relevamiento,
    RequisitoNativo,
    Segmento,
    Subsegmento,
    TipoCampo,
)

# Clase reutilizable del design system para inputs/selects/textareas.
# Definida en static/custom/css/nodo-forms.css (alto 42px, foco de marca con ring).
INPUT_CLASS = "nodo-field"
CHECKBOX_CLASS = "h-4 w-4 rounded border-base text-fg-brand focus:ring-brand"

ROL_COORDINADOR = "Becas — Coordinador"
ROL_TERRITORIAL = "Becas — Territorial"


def _text_widget(rows=3):
    return forms.Textarea(attrs={"class": INPUT_CLASS, "rows": rows})


class SegmentoForm(forms.ModelForm):
    class Meta:
        model = Segmento
        fields = ["nombre", "descripcion", "cupo_maximo", "requiere_gps", "activo"]
        widgets = {
            "nombre": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "descripcion": _text_widget(),
            "cupo_maximo": forms.NumberInput(attrs={"class": INPUT_CLASS, "min": 0}),
            "requiere_gps": forms.CheckboxInput(attrs={"class": CHECKBOX_CLASS}),
            "activo": forms.CheckboxInput(attrs={"class": CHECKBOX_CLASS}),
        }


class SegmentoCreateForm(forms.ModelForm):
    """Alta de segmento — modal "Nuevo segmento" del kit.

    Suma ``coordinador`` (se persiste como ``AsignacionCoordinador`` en la vista)
    y deja fuera GPS/activo. ``descripcion`` es obligatoria como en el kit.
    """

    coordinador = forms.ModelChoiceField(
        queryset=User.objects.none(),
        label="Coordinador asignado",
        empty_label="Seleccioná…",
        widget=forms.Select(attrs={"class": INPUT_CLASS}),
    )

    class Meta:
        model = Segmento
        fields = ["nombre", "descripcion", "cupo_maximo"]
        widgets = {
            "nombre": forms.TextInput(attrs={
                "class": INPUT_CLASS,
                "placeholder": "Ej: Producción Territorial / Fuego y Barro",
            }),
            "descripcion": forms.Textarea(attrs={
                "class": INPUT_CLASS, "rows": 2,
                "placeholder": "Población objetivo del segmento",
            }),
            "cupo_maximo": forms.NumberInput(attrs={
                "class": INPUT_CLASS, "min": 0, "placeholder": "Ej: 500",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["descripcion"].required = True
        self.fields["coordinador"].queryset = User.objects.filter(
            groups__name=ROL_COORDINADOR, is_active=True
        ).distinct().order_by("username")


class SubsegmentoForm(forms.ModelForm):
    """El segmento se fija desde la vista (no es un campo editable)."""

    class Meta:
        model = Subsegmento
        fields = ["nombre", "descripcion", "cupo_maximo"]
        widgets = {
            "nombre": forms.TextInput(attrs={
                "class": INPUT_CLASS,
                "placeholder": "Ej: Ladrillo",
            }),
            "descripcion": forms.Textarea(attrs={
                "class": INPUT_CLASS,
                "rows": 2,
                "placeholder": "Opcional",
            }),
            "cupo_maximo": forms.NumberInput(attrs={"class": INPUT_CLASS, "min": 0}),
        }

    def __init__(self, *args, segmento=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["descripcion"].required = False
        if segmento is not None:
            self.instance.segmento = segmento


class _OpcionesMixin(forms.ModelForm):
    """Maneja ``opciones`` (JSON) vía un textarea (una opción por línea), válido
    solo para los tipos SELECTOR / SELECTOR_MULTIPLE."""

    opciones_texto = forms.CharField(
        required=False,
        label="Opciones (una por línea)",
        help_text="Solo para Selector / Selector múltiple.",
        widget=forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 4}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.opciones:
            self.fields["opciones_texto"].initial = "\n".join(self.instance.opciones)

    def clean(self):
        cleaned = super().clean()
        tipo = cleaned.get("tipo")
        texto = (cleaned.get("opciones_texto") or "").strip()
        if tipo in (TipoCampo.SELECTOR, TipoCampo.SELECTOR_MULTIPLE):
            opciones = [linea.strip() for linea in texto.splitlines() if linea.strip()]
            if not opciones:
                self.add_error("opciones_texto", "Indicá al menos una opción para este tipo de campo.")
            cleaned["_opciones"] = opciones
        else:
            cleaned["_opciones"] = None
        return cleaned

    def save(self, commit=True):
        self.instance.opciones = self.cleaned_data.get("_opciones")
        return super().save(commit=commit)


class PreguntaGlobalForm(_OpcionesMixin):
    class Meta:
        model = PreguntaGlobal
        fields = ["texto", "tipo", "obligatorio", "orden", "activo"]
        widgets = {
            "texto": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "tipo": forms.Select(attrs={"class": INPUT_CLASS}),
            "obligatorio": forms.CheckboxInput(attrs={"class": CHECKBOX_CLASS}),
            "orden": forms.NumberInput(attrs={"class": INPUT_CLASS, "min": 0}),
            "activo": forms.CheckboxInput(attrs={"class": CHECKBOX_CLASS}),
        }


class RequisitoNativoForm(_OpcionesMixin):
    """El segmento (y subsegmento opcional) se fijan desde la vista."""

    obligatorio = forms.TypedChoiceField(
        label="Obligatorio",
        choices=[(True, "Obligatorio"), (False, "Opcional")],
        coerce=lambda x: x in (True, "True", "1", 1),
        widget=forms.Select(attrs={"class": INPUT_CLASS}),
        initial=True,
    )

    class Meta:
        model = RequisitoNativo
        fields = ["texto", "tipo", "obligatorio", "orden"]
        widgets = {
            "texto": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "tipo": forms.Select(attrs={"class": INPUT_CLASS}),
            "orden": forms.NumberInput(attrs={"class": INPUT_CLASS, "min": 0}),
        }

    def __init__(self, *args, segmento=None, subsegmento=None, **kwargs):
        super().__init__(*args, **kwargs)
        if segmento is not None:
            self.instance.segmento = segmento
        # subsegmento puede ser None (requisito del segmento) o una instancia.
        self.instance.subsegmento = subsegmento
        # ``orden`` es opcional: si no se indica, se autocalcula como el siguiente
        # disponible (así el form inline que no lo renderiza sigue funcionando).
        self.fields["orden"].required = False

    def clean_orden(self):
        orden = self.cleaned_data.get("orden")
        if orden not in (None, ""):
            return orden
        hermanos = RequisitoNativo.objects.filter(
            segmento=self.instance.segmento, subsegmento=self.instance.subsegmento
        )
        ultimo = hermanos.aggregate(m=models.Max("orden"))["m"]
        return (ultimo or 0) + 1


class AsignacionCoordinadorForm(forms.ModelForm):
    """Asigna un coordinador (usuario con rol Coordinador) a un segmento."""

    class Meta:
        model = AsignacionCoordinador
        fields = ["coordinador"]
        widgets = {"coordinador": forms.Select(attrs={"class": INPUT_CLASS})}

    def __init__(self, *args, segmento=None, **kwargs):
        super().__init__(*args, **kwargs)
        if segmento is not None:
            self.instance.segmento = segmento
        # Solo usuarios con el rol Coordinador de Becas (#74).
        self.fields["coordinador"].queryset = User.objects.filter(
            groups__name=ROL_COORDINADOR, is_active=True
        ).distinct().order_by("username")

    def clean(self):
        cleaned = super().clean()
        coord = cleaned.get("coordinador")
        seg = self.instance.segmento
        if coord and seg:
            existe = AsignacionCoordinador.objects.filter(segmento=seg, coordinador=coord)
            if self.instance.pk:
                existe = existe.exclude(pk=self.instance.pk)
            if existe.exists():
                self.add_error("coordinador", "Ese coordinador ya está asignado a este segmento.")
        return cleaned


class ConvocatoriaForm(forms.ModelForm):
    """Convocatoria: segmento requerido + subsegmento opcional del segmento (RN-30)."""

    class Meta:
        model = Convocatoria
        fields = ["nombre", "segmento", "subsegmento", "fecha_inicio", "fecha_fin", "descripcion", "activo"]
        widgets = {
            "nombre": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "segmento": forms.Select(attrs={"class": INPUT_CLASS}),
            "subsegmento": forms.Select(attrs={"class": INPUT_CLASS}),
            "fecha_inicio": forms.DateInput(attrs={"class": INPUT_CLASS, "type": "date"}),
            "fecha_fin": forms.DateInput(attrs={"class": INPUT_CLASS, "type": "date"}),
            "descripcion": _text_widget(),
            "activo": forms.CheckboxInput(attrs={"class": CHECKBOX_CLASS}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["subsegmento"].required = False
        self.fields["subsegmento"].queryset = Subsegmento.objects.select_related("segmento")


class RelevamientoForm(forms.ModelForm):
    """ABM de relevamiento. El territorial se elige entre usuarios con rol Territorial."""

    class Meta:
        model = Relevamiento
        fields = ["convocatoria", "territorial", "fecha_asignada", "zona", "observaciones"]
        widgets = {
            "convocatoria": forms.Select(attrs={"class": INPUT_CLASS}),
            "territorial": forms.Select(attrs={"class": INPUT_CLASS}),
            "fecha_asignada": forms.DateInput(attrs={"class": INPUT_CLASS, "type": "date"}),
            "zona": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "observaciones": forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 3}),
        }

    def __init__(self, *args, segmentos_permitidos=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["territorial"].queryset = User.objects.filter(
            groups__name=ROL_TERRITORIAL, is_active=True
        ).distinct().order_by("username")
        conv_qs = Convocatoria.objects.select_related("segmento").filter(activo=True)
        if segmentos_permitidos is not None:
            conv_qs = conv_qs.filter(segmento__in=segmentos_permitidos)
        self.fields["convocatoria"].queryset = conv_qs
        self.fields["observaciones"].required = False


class ReasignarTerritorialForm(forms.Form):
    territorial = forms.ModelChoiceField(
        queryset=User.objects.none(),
        widget=forms.Select(attrs={"class": INPUT_CLASS}),
        label="Nuevo territorial",
    )
    motivo = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 2}),
        label="Motivo",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["territorial"].queryset = User.objects.filter(
            groups__name=ROL_TERRITORIAL, is_active=True
        ).distinct().order_by("username")


class ReprogramarForm(forms.Form):
    fecha_asignada = forms.DateField(
        widget=forms.DateInput(attrs={"class": INPUT_CLASS, "type": "date"}),
        label="Nueva fecha asignada",
    )


class FormularioRevisionForm(forms.ModelForm):
    """Edición en revisión de los campos de contacto/apoderado del formulario.

    Cada cambio queda registrado en ``TracaFormulario`` (lo hace la vista, no el
    form). Las respuestas dinámicas y la identidad RENAPER no se editan acá.
    """

    # Etiquetas legibles de los campos auditables (para la traza).
    LABELS = {
        "celular": "Celular",
        "email_contacto": "Correo electrónico",
        "apoderado_nombre": "Apoderado · nombre",
        "apoderado_apellido": "Apoderado · apellido",
        "apoderado_fecha_nacimiento": "Apoderado · fecha de nacimiento",
    }

    class Meta:
        model = Formulario
        fields = [
            "celular",
            "email_contacto",
            "apoderado_nombre",
            "apoderado_apellido",
            "apoderado_fecha_nacimiento",
        ]
        widgets = {
            "celular": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "email_contacto": forms.EmailInput(attrs={"class": INPUT_CLASS}),
            "apoderado_nombre": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "apoderado_apellido": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "apoderado_fecha_nacimiento": forms.DateInput(attrs={"class": INPUT_CLASS, "type": "date"}),
        }
