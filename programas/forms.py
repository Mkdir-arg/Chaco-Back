"""Formularios del backoffice del Programa Becas (#74 / #76)."""

from django import forms
from django.contrib.auth.models import User
from django.db import models
from django.utils.dateparse import parse_date

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
from programas.services.becas import es_menor

# Clase reutilizable del design system para inputs/selects/textareas.
# Definida en static/custom/css/nodo-forms.css (alto 42px, foco de marca con ring).
INPUT_CLASS = "nodo-field"
CHECKBOX_CLASS = "h-4 w-4 rounded border-base text-fg-brand focus:ring-brand"


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
            "nombre": forms.TextInput(
                attrs={
                    "class": INPUT_CLASS,
                    "placeholder": "Ej: Producción Territorial / Fuego y Barro",
                }
            ),
            "descripcion": forms.Textarea(
                attrs={
                    "class": INPUT_CLASS,
                    "rows": 2,
                    "placeholder": "Población objetivo del segmento",
                }
            ),
            "cupo_maximo": forms.NumberInput(
                attrs={
                    "class": INPUT_CLASS,
                    "min": 0,
                    "placeholder": "Ej: 500",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["descripcion"].required = True
        from programas.services.autorizacion import usuarios_coordinadores_becas

        self.fields["coordinador"].queryset = usuarios_coordinadores_becas()
        self.fields["coordinador"].label_from_instance = lambda u: u.get_full_name() or u.username


class SubsegmentoForm(forms.ModelForm):
    """El segmento se fija desde la vista (no es un campo editable)."""

    class Meta:
        model = Subsegmento
        fields = ["nombre", "descripcion", "cupo_maximo"]
        widgets = {
            "nombre": forms.TextInput(
                attrs={
                    "class": INPUT_CLASS,
                    "placeholder": "Ej: Ladrillo",
                }
            ),
            "descripcion": forms.Textarea(
                attrs={
                    "class": INPUT_CLASS,
                    "rows": 2,
                    "placeholder": "Opcional",
                }
            ),
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
        from programas.services.autorizacion import usuarios_coordinadores_becas

        self.fields["coordinador"].queryset = usuarios_coordinadores_becas()
        self.fields["coordinador"].label_from_instance = lambda u: u.get_full_name() or u.username

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


class _SelectConSegmento(forms.Select):
    """Select cuyas opciones llevan ``data-segmento``.

    Lo usa el filtro dependiente convocatoria → territorial del alta de
    relevamiento (el JS del template oculta los territoriales que no
    pertenecen al segmento de la convocatoria elegida).
    """

    def __init__(self, *args, segmento_por_valor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.segmento_por_valor = segmento_por_valor or {}

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        segmento_id = self.segmento_por_valor.get(str(value))
        if segmento_id:
            option["attrs"]["data-segmento"] = segmento_id
        return option


class RelevamientoForm(forms.ModelForm):
    """ABM de relevamiento. El territorial se elige entre los usuarios con rol
    Territorial **del segmento de la convocatoria** (``AsignacionTerritorial``)."""

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
        from programas.services.autorizacion import usuarios_territoriales_becas

        terr_qs = usuarios_territoriales_becas().select_related("asignacion_territorial")
        conv_qs = Convocatoria.objects.select_related("segmento").filter(activo=True)
        if segmentos_permitidos is not None:
            conv_qs = conv_qs.filter(segmento__in=segmentos_permitidos)
        # data-segmento por opción para el filtro dependiente del template.
        # Los widgets se reemplazan ANTES de asignar los querysets: el setter de
        # queryset es el que propaga las choices al widget vigente.
        conv_map = {str(c.pk): str(c.segmento_id) for c in conv_qs}
        terr_map = {}
        for usuario in terr_qs:
            asignacion = getattr(usuario, "asignacion_territorial", None)
            if asignacion is not None:
                terr_map[str(usuario.pk)] = str(asignacion.segmento_id)
        self.fields["convocatoria"].widget = _SelectConSegmento(
            attrs={"class": INPUT_CLASS}, segmento_por_valor=conv_map
        )
        self.fields["territorial"].widget = _SelectConSegmento(
            attrs={"class": INPUT_CLASS}, segmento_por_valor=terr_map
        )
        self.fields["territorial"].queryset = terr_qs
        self.fields["territorial"].label_from_instance = lambda u: u.get_full_name() or u.username
        self.fields[
            "territorial"
        ].help_text = "Solo se listan los territoriales del segmento de la convocatoria elegida."
        self.fields["convocatoria"].queryset = conv_qs
        self.fields["observaciones"].required = False

    def clean(self):
        cleaned = super().clean()
        convocatoria = cleaned.get("convocatoria")
        territorial = cleaned.get("territorial")
        if convocatoria and territorial:
            asignacion = getattr(territorial, "asignacion_territorial", None)
            if asignacion is None or asignacion.segmento_id != convocatoria.segmento_id:
                self.add_error("territorial", "El territorial no pertenece al segmento de la convocatoria.")
        return cleaned


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

    def __init__(self, *args, segmento=None, **kwargs):
        super().__init__(*args, **kwargs)
        from programas.services.autorizacion import usuarios_territoriales_becas

        # Con segmento (el del relevamiento) solo ofrece territoriales asignados a él.
        self.fields["territorial"].queryset = usuarios_territoriales_becas(segmento=segmento)
        self.fields["territorial"].label_from_instance = lambda u: u.get_full_name() or u.username


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

    def clean(self):
        cleaned_data = super().clean()
        fecha_nacimiento = None
        if self.instance.ciudadano_id:
            fecha_nacimiento = self.instance.ciudadano.fecha_nacimiento
        elif isinstance(self.instance.datos_identificacion, dict):
            fecha_nacimiento = self.instance.datos_identificacion.get("fecha_nacimiento")
            if isinstance(fecha_nacimiento, str):
                try:
                    fecha_nacimiento = parse_date(fecha_nacimiento)
                except ValueError:
                    fecha_nacimiento = None

        if es_menor(fecha_nacimiento):
            for campo in ("apoderado_nombre", "apoderado_apellido", "apoderado_fecha_nacimiento"):
                if not cleaned_data.get(campo):
                    self.add_error(campo, "Este dato es obligatorio cuando la persona relevada es menor de edad.")
        return cleaned_data
