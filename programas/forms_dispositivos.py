"""Formularios de la operación de Dispositivos (MVP v2).

Aparte de `programas/forms.py` a propósito: ese archivo es evidencia del campo canónico
(`INPUT_CLASS`), y un formulario nuevo que solo la consume no mueve esa pieza.
"""

from django import forms
from django.utils import timezone

from core.validators import ACCEPT_ADJUNTO
from core.widgets import ChipsSelectMultiple, SwitchInput
from programas.forms import INPUT_CLASS
from programas.models import EntradaBitacora, MotivoEgreso, Turno
from programas.services.bitacora_pantalla import TIPOS_MANUALES
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
# Acciones sobre una plaza del mapa (P5)
# --------------------------------------------------------------------------- #
#
# Las reglas de fondo —que la plaza no esté tomada, que la reserva siga abierta, el
# bloqueo de la fila— viven en `programas.services.estadias`. Acá solo viaja el motivo,
# que es lo único que el modal pide.


class SacarPlazaDeServicioForm(forms.Form):
    """Sacar una plaza de servicio: el motivo es obligatorio y queda en la plaza.

    Lo exige también `estadias.sacar_plaza_de_servicio` —la regla es del servicio, no del
    modal—: acá se repite para que el operador lo corrija sin un viaje al servidor.
    """

    motivo = forms.CharField(
        label="Motivo",
        max_length=200,
        widget=forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 3, "placeholder": "Colchón roto, reparación…"}),
        error_messages={"required": "Sacar una plaza de servicio exige un motivo."},
    )


class LiberarPlazaForm(forms.Form):
    """Liberar la reserva o el préstamo de una plaza. El motivo es opcional.

    Opcional y no obligatorio porque la reserva ya tiene el suyo —por qué se tomó— y esto
    solo lo reemplaza si se escribe algo: la mayoría de las veces se libera porque la
    persona no llegó, y obligar a tipearlo todos los días convierte el campo en ruido.
    """

    motivo = forms.CharField(
        label="Motivo",
        max_length=200,
        required=False,
        widget=forms.Textarea(
            attrs={"class": INPUT_CLASS, "rows": 3, "placeholder": "Opcional: reemplaza el motivo de la reserva"}
        ),
    )


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


# --------------------------------------------------------------------------- #
# Bitácora del turno (P10 · #697)
# --------------------------------------------------------------------------- #
#
# Los formularios solo traducen lo que llega del modal. Las reglas —turno en curso,
# personas alojadas en ese momento, tope de adjuntos, superposición de turnos— viven en
# `programas.services.bitacora`, y la vista muestra su error tal cual.

_FORMATOS_MOMENTO = ["%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"]


class AdjuntosInput(forms.FileInput):
    """Un `<input type="file" multiple>`."""

    allow_multiple_selected = True


class AdjuntosField(forms.FileField):
    """Varios archivos en un campo. Devuelve la lista tal cual llegó.

    Cada archivo y el tope por novedad los valida `bitacora._guardar_adjuntos` —con los
    heredados de la versión que se corrige—, antes de escribir el primero: acá no se
    repite la regla.
    """

    def clean(self, data, initial=None):
        if isinstance(data, (list, tuple)):
            return [archivo for archivo in data if archivo]
        return [data] if data else []


class NovedadForm(forms.Form):
    """Cargar una novedad del turno en curso (`bitacora.registrar_entrada`)."""

    tipo = forms.ChoiceField(
        label="Tipo",
        choices=(),
        widget=forms.Select(attrs={"class": INPUT_CLASS}),
        error_messages={"required": "Elegí el tipo de novedad."},
    )
    momento = forms.DateTimeField(
        label="Cuándo pasó",
        required=False,
        input_formats=_FORMATOS_MOMENTO,
        widget=forms.DateTimeInput(format="%Y-%m-%dT%H:%M", attrs={"class": INPUT_CLASS, "type": "datetime-local"}),
        help_text="Vacío = ahora. Puede ser más temprano, dentro del turno en curso.",
    )
    texto = forms.CharField(
        label="Qué pasó",
        widget=forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 4}),
        error_messages={"required": "Contá qué pasó."},
    )
    personas = forms.MultipleChoiceField(
        label="Personas involucradas",
        required=False,
        choices=(),
        widget=ChipsSelectMultiple,
    )
    adjuntos = AdjuntosField(
        label="Adjuntos",
        required=False,
        widget=AdjuntosInput(attrs={"class": INPUT_CLASS, "accept": ACCEPT_ADJUNTO}),
    )

    def __init__(self, *args, personas=(), max_adjuntos=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["tipo"].choices = [("", "Elegí el tipo"), *TIPOS_MANUALES]
        self.fields["personas"].choices = [(str(pk), etiqueta) for pk, etiqueta in personas]
        if max_adjuntos:
            self.fields["adjuntos"].help_text = f"Hasta {max_adjuntos} archivos: PDF, imágenes o documentos de 5 MB."


class CorreccionForm(forms.Form):
    """Corregir una novedad del turno en curso: agrega una versión (`bitacora.corregir_entrada`)."""

    # Un entero con un `<select>`: las opciones las arma la vista con las novedades del turno
    # en curso, sin una consulta (ni un `__str__` por fila) para dibujarlas; al recibir, solo
    # se exige que sea de este dispositivo. Que sea del turno en curso lo decide el servicio.
    entrada = forms.IntegerField(
        label="Novedad a corregir",
        widget=forms.Select(
            attrs={"class": INPUT_CLASS, "x-model": "correccion.entrada", "@change": "elegirCorreccion()"}
        ),
        error_messages={
            "required": "Elegí la novedad que querés corregir.",
            "invalid": "Elegí la novedad que querés corregir.",
        },
    )
    tipo = forms.ChoiceField(
        label="Tipo",
        choices=(),
        widget=forms.Select(attrs={"class": INPUT_CLASS, "x-model": "correccion.tipo"}),
        error_messages={"required": "Elegí el tipo de novedad."},
    )
    texto = forms.CharField(
        label="Texto corregido",
        widget=forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 4, "x-model": "correccion.texto"}),
        error_messages={"required": "La novedad necesita un texto."},
    )
    motivo = forms.CharField(
        label="Motivo de la corrección",
        required=False,
        max_length=255,
        widget=forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "Opcional"}),
    )

    def __init__(self, *args, dispositivo=None, corregibles=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.dispositivo = dispositivo
        self.fields["tipo"].choices = [("", "Elegí el tipo"), *TIPOS_MANUALES]
        self.fields["entrada"].widget.choices = [("", "Elegí la novedad"), *corregibles]

    def clean_entrada(self):
        entrada = EntradaBitacora.objects.filter(pk=self.cleaned_data["entrada"], dispositivo=self.dispositivo).first()
        if entrada is None:
            raise forms.ValidationError("Esa novedad no es de este dispositivo.")
        return entrada


class TurnoForm(forms.Form):
    """Alta o edición de un turno (`bitacora.crear_turno` / `editar_turno`).

    Sin `turno` es un alta; con `turno`, la edición de ese. Un turno no se borra: se da de
    baja con «Activo».
    """

    # Como `CorreccionForm.entrada`: las opciones salen de la vista y al recibir solo se
    # exige que el turno sea de este dispositivo.
    turno = forms.IntegerField(
        label="Turno",
        required=False,
        widget=forms.Select(attrs={"class": INPUT_CLASS, "x-model": "turnoForm.turno", "@change": "elegirTurno()"}),
        error_messages={"invalid": "Ese turno no es de este dispositivo."},
    )
    nombre = forms.CharField(
        label="Nombre",
        max_length=60,
        widget=forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "Mañana", "x-model": "turnoForm.nombre"}),
        error_messages={"required": "El turno necesita un nombre."},
    )
    hora_desde = forms.TimeField(
        label="Desde",
        widget=forms.TimeInput(
            format="%H:%M", attrs={"class": INPUT_CLASS, "type": "time", "x-model": "turnoForm.desde"}
        ),
        error_messages={"required": "Indicá a qué hora empieza."},
    )
    hora_hasta = forms.TimeField(
        label="Hasta",
        widget=forms.TimeInput(
            format="%H:%M", attrs={"class": INPUT_CLASS, "type": "time", "x-model": "turnoForm.hasta"}
        ),
        help_text="Si termina más temprano que su inicio, cruza la medianoche (22:00 a 06:00).",
        error_messages={"required": "Indicá a qué hora termina."},
    )
    orden = forms.IntegerField(
        label="Orden",
        min_value=0,
        max_value=32767,
        initial=0,
        required=False,
        widget=forms.NumberInput(attrs={"class": INPUT_CLASS, "x-model": "turnoForm.orden"}),
    )
    activo = forms.BooleanField(
        label="Activo",
        required=False,
        widget=SwitchInput(attrs={"x-model": "turnoForm.activo"}),
    )

    def __init__(self, *args, dispositivo=None, turnos=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.dispositivo = dispositivo
        self.fields["turno"].widget.choices = [("", "Nuevo turno"), *turnos]

    def clean_turno(self):
        pk = self.cleaned_data["turno"]
        if pk is None:
            return None
        turno = Turno.objects.filter(pk=pk, dispositivo=self.dispositivo).first()
        if turno is None:
            raise forms.ValidationError("Ese turno no es de este dispositivo.")
        return turno
