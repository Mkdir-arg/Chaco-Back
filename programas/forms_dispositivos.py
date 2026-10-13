"""Formularios de la operación de Dispositivos (MVP v2).

Aparte de `programas/forms.py` a propósito: ese archivo es evidencia del campo canónico
(`INPUT_CLASS`), y un formulario nuevo que solo la consume no mueve esa pieza.
"""

from django import forms
from django.utils import timezone

from core.widgets import SwitchInput
from programas.forms import INPUT_CLASS
from programas.models import MotivoEgreso
from programas.services.movimientos import ultimo_momento


class EgresoForm(forms.Form):
    """Egreso de una persona del dispositivo (P9 del mockup · #691).

    La regla de fondo —fecha no futura ni anterior al ingreso, motivo vigente— la sostiene
    `programas.services.estadias.egresar_persona`, que relee la estadía con la fila
    bloqueada. Acá se repite lo que el operador puede corregir sin salir del modal.
    """

    fecha_egreso = forms.DateTimeField(
        label="Fecha y hora",
        input_formats=["%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"],
        widget=forms.DateTimeInput(format="%Y-%m-%dT%H:%M", attrs={"class": INPUT_CLASS, "type": "datetime-local"}),
        help_text="No puede ser anterior al ingreso.",
    )
    motivo = forms.ModelChoiceField(
        label="Motivo",
        queryset=MotivoEgreso.objects.none(),
        empty_label="Elegí un motivo",
        widget=forms.Select(attrs={"class": INPUT_CLASS}),
        error_messages={"required": "Elegí el motivo del egreso."},
    )
    destino = forms.CharField(
        label="Destino",
        max_length=200,
        widget=forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "Domicilio de familiar, otro dispositivo…"}),
        error_messages={"required": "Indicá a dónde va la persona."},
    )
    observaciones = forms.CharField(
        label="Observaciones",
        required=False,
        widget=forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 3, "placeholder": "Opcional"}),
    )
    pertenencias_devueltas = forms.BooleanField(
        label="Pertenencias devueltas y firmadas",
        required=False,
        widget=SwitchInput,
    )

    def __init__(self, *args, estadia=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.estadia = estadia
        self.fields["motivo"].queryset = MotivoEgreso.objects.filter(activo=True)
        if not self.is_bound:
            self.fields["fecha_egreso"].initial = timezone.localtime().replace(second=0, microsecond=0)

    def clean_fecha_egreso(self):
        fecha = self.cleaned_data["fecha_egreso"]
        if fecha > timezone.now():
            raise forms.ValidationError("El egreso no puede ser futuro.")
        if self.estadia is not None:
            ingreso = self.estadia.fecha_ingreso
            # El input `datetime-local` no trae segundos y el ingreso sí: egresar en el mismo
            # minuto del ingreso (un alta por error, corregida enseguida) quedaría «anterior».
            # Se compara al minuto y, dentro de ese minuto, se egresa en el instante del ingreso,
            # que es lo que el servicio y el constraint de la base aceptan.
            if fecha < ingreso.replace(second=0, microsecond=0):
                raise forms.ValidationError("El egreso no puede ser anterior al ingreso.")
            fecha = max(fecha, ingreso)
        return fecha


class CambioPlazaForm(forms.Form):
    """Cambio de plaza dentro del mismo dispositivo (P7 del mockup · #698).

    Ofrece solo las plazas **libres**, y libres según `programas.services.ocupacion`
    (las calcula la vista con `plazas_para_ingresar`, que pasa por `estado_de_plazas`): el
    formulario no decide qué es una plaza tomada. La regla de fondo —plaza del dispositivo,
    libre con su fila bloqueada, motivo, momento ni futuro ni anterior al último
    movimiento— la sostiene `programas.services.estadias.cambiar_plaza`.
    """

    plaza = forms.TypedChoiceField(
        label="Plaza de destino",
        coerce=int,
        widget=forms.Select(attrs={"class": INPUT_CLASS}),
        error_messages={
            "required": "Elegí la plaza a la que se mueve la persona.",
            "invalid_choice": "Esa plaza ya no está libre. Elegí otra.",
        },
    )
    momento = forms.DateTimeField(
        label="Fecha y hora",
        input_formats=["%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"],
        widget=forms.DateTimeInput(format="%Y-%m-%dT%H:%M", attrs={"class": INPUT_CLASS, "type": "datetime-local"}),
        help_text="No puede ser anterior al último movimiento de la estadía.",
    )
    motivo = forms.CharField(
        label="Motivo",
        widget=forms.Textarea(
            attrs={"class": INPUT_CLASS, "rows": 3, "placeholder": "Convivencia, pedido de la persona…"}
        ),
        error_messages={"required": "El cambio de plaza exige un motivo."},
    )

    def __init__(self, *args, estadia=None, sectores=(), **kwargs):
        """`sectores` es lo que devuelve `plazas_para_ingresar`: cada sector con sus plazas y su estado."""

        super().__init__(*args, **kwargs)
        self.estadia = estadia
        grupos = []
        for item in sectores:
            libres = [(plaza["pk"], plaza["codigo"]) for plaza in item["plazas"] if plaza["disponible"]]
            if libres:
                grupos.append((item["sector"].nombre, libres))
        self.hay_plazas_libres = bool(grupos)
        self.fields["plaza"].choices = [("", "Elegí una plaza libre"), *grupos]
        if not self.is_bound:
            self.fields["momento"].initial = timezone.localtime().replace(second=0, microsecond=0)

    def clean_motivo(self):
        motivo = self.cleaned_data["motivo"].strip()
        if not motivo:
            raise forms.ValidationError("El cambio de plaza exige un motivo.")
        return motivo

    def clean_momento(self):
        momento = self.cleaned_data["momento"]
        if momento > timezone.now():
            raise forms.ValidationError("El cambio no puede ser futuro.")
        if self.estadia is not None:
            ultimo = ultimo_momento(self.estadia)
            # Como en `EgresoForm` con el ingreso: el `datetime-local` no trae segundos y el
            # último movimiento sí. Un cambio cargado en el mismo minuto que el anterior
            # quedaría «anterior» por los segundos; se compara al minuto y, dentro de ese
            # minuto, el cambio va en el instante del último movimiento.
            if momento < ultimo.replace(second=0, microsecond=0):
                raise forms.ValidationError("El cambio no puede ser anterior al último movimiento de la estadía.")
            momento = max(momento, ultimo)
        return momento


# --------------------------------------------------------------------------- #
# Relevamientos edilicios (P21 · #701)
# --------------------------------------------------------------------------- #
# Las reglas de fondo —alcance del coordinador, un solo relevamiento en curso por
# edificio, agente activo, con la capacidad y externo al edificio— las sostiene
# `programas.services.inspecciones`. Los selectores ya llegan acotados por ese servicio.


class _AgenteChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, usuario):
        return usuario.get_full_name() or usuario.username


class ElegirEdificioForm(forms.Form):
    """Primer paso de «Nuevo relevamiento»: elegir el edificio (GET).

    El agente depende del edificio —con el agente externo, el personal de sus
    instituciones no se ofrece—, así que el modal de asignación se arma ya con uno elegido.
    """

    asignar = forms.ModelChoiceField(
        label="Edificio",
        queryset=None,
        empty_label="Elegí un edificio",
        widget=forms.Select(attrs={"class": INPUT_CLASS}),
        help_text="Solo los edificios de tu alcance que no tienen un relevamiento en curso.",
    )

    def __init__(self, *args, edificios, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["asignar"].queryset = edificios


class AsignarRelevamientoForm(forms.Form):
    edificio = forms.CharField(
        label="Edificio", required=False, disabled=True, widget=forms.TextInput(attrs={"class": INPUT_CLASS})
    )
    asignado_a = _AgenteChoiceField(
        label="Agente territorial",
        queryset=None,
        empty_label="Elegí un agente",
        widget=forms.Select(attrs={"class": INPUT_CLASS}),
        error_messages={
            "required": "Elegí el agente que va a relevar.",
            "invalid_choice": "Ese agente no se puede asignar a este edificio.",
        },
    )
    fecha_vencimiento = forms.DateField(
        label="Vence",
        input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"class": INPUT_CLASS, "type": "date"}),
        error_messages={"required": "Indicá hasta cuándo hay tiempo de relevar."},
    )
    indicaciones = forms.CharField(
        label="Indicaciones para el territorial",
        required=False,
        widget=forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 3, "placeholder": "Opcional"}),
    )

    def __init__(self, *args, edificio, agentes, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["edificio"].initial = f"{edificio.nombre} · {edificio.codigo}"
        self.fields["asignado_a"].queryset = agentes


class ReasignarRelevamientoForm(forms.Form):
    asignado_a = _AgenteChoiceField(
        label="Nuevo agente territorial",
        queryset=None,
        empty_label="Elegí un agente",
        widget=forms.Select(attrs={"class": INPUT_CLASS}),
        error_messages={
            "required": "Elegí el agente que va a relevar.",
            "invalid_choice": "Ese agente no se puede asignar a este edificio.",
        },
    )

    def __init__(self, *args, agentes, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["asignado_a"].queryset = agentes


class CancelarRelevamientoForm(forms.Form):
    motivo = forms.CharField(
        label="Motivo",
        max_length=200,
        widget=forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 3}),
        error_messages={"required": "Cancelar un relevamiento exige un motivo."},
    )
