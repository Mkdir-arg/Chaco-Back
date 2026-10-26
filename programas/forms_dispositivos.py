"""Formularios de la operación de Dispositivos (MVP v2).

Aparte de `programas/forms.py` a propósito: ese archivo es evidencia del campo canónico
(`INPUT_CLASS`), y un formulario nuevo que solo la consume no mueve esa pieza.
"""

from django import forms
from django.utils import timezone

from core.validators import ACCEPT_ADJUNTO
from core.widgets import ChipsSelectMultiple, SwitchInput
from programas.forms import INPUT_CLASS
from programas.models import EntradaBitacora, MotivoEgreso, Plaza, Sector, Turno
from programas.services.bitacora_pantalla import TIPOS_MANUALES
from programas.services.edificios import CAMPOS as CAMPOS_EDIFICIO
from programas.services.movimientos import ultimo_momento
from programas.services.plazas import TOPE_POR_LOTE


class EgresoForm(forms.Form):
    """Egreso de una persona del dispositivo (P9 del mockup · #691).

    La regla de fondo —fecha no futura ni anterior al último movimiento, motivo vigente— la sostiene
    `programas.services.estadias.egresar_persona`, que relee la estadía con la fila
    bloqueada. Acá se repite lo que el operador puede corregir sin salir del modal.
    """

    fecha_egreso = forms.DateTimeField(
        label="Fecha y hora",
        input_formats=["%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"],
        widget=forms.DateTimeInput(format="%Y-%m-%dT%H:%M", attrs={"class": INPUT_CLASS, "type": "datetime-local"}),
        help_text="No puede ser anterior al último movimiento de la estadía.",
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
            ultimo = ultimo_momento(self.estadia)
            # El `datetime-local` no trae segundos y el último movimiento sí: se compara
            # al minuto y se conserva su instante si el egreso cae en ese mismo minuto.
            # El servicio vuelve a validar con la estadía bloqueada.
            if fecha < ultimo.replace(second=0, microsecond=0):
                raise forms.ValidationError("El egreso no puede ser anterior al último movimiento de la estadía.")
            fecha = max(fecha, ultimo)
        return fecha


class CambioPlazaForm(forms.Form):
    """Cambio de plaza dentro del mismo dispositivo (P7 del mockup · #698).

    Ofrece solo las plazas **libres**, y libres según `programas.services.ocupacion`
    (las calcula la vista con `plazas_para_ingresar`, que pasa por `estado_de_plazas`): el
    formulario no decide qué es una plaza tomada. La regla de fondo —plaza del dispositivo,
    libre con su fila bloqueada, motivo, momento ni futuro ni anterior al último
    movimiento— la sostiene `programas.services.estadias.cambiar_plaza`.

    Con una estadía **sin plaza** el mismo formulario es el de «Asignar plaza»
    (`asignar_plaza`): el motivo pasa a ser opcional y los textos dicen asignar.
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
        self.asigna = estadia is not None and estadia.plaza_id is None
        if self.asigna:
            self.fields["plaza"].label = "Plaza"
            self.fields["plaza"].error_messages["required"] = "Elegí la plaza que se le asigna a la persona."
            self.fields["momento"].help_text = "No puede ser anterior al último movimiento de la estadía."
            self.fields["motivo"].required = False
            self.fields["motivo"].widget.attrs["placeholder"] = "Opcional: se liberó una plaza, pedido de la persona…"
        self.fields["plaza"].choices = [("", "Elegí una plaza libre"), *grupos]
        if not self.is_bound:
            self.fields["momento"].initial = timezone.localtime().replace(second=0, microsecond=0)

    def clean_motivo(self):
        motivo = self.cleaned_data["motivo"].strip()
        if not motivo and not self.asigna:
            raise forms.ValidationError("El cambio de plaza exige un motivo.")
        return motivo

    def clean_momento(self):
        momento = self.cleaned_data["momento"]
        if momento > timezone.now():
            raise forms.ValidationError(
                "La asignación no puede ser futura." if self.asigna else "El cambio no puede ser futuro."
            )
        if self.estadia is not None:
            ultimo = ultimo_momento(self.estadia)
            # Como en `EgresoForm`: el `datetime-local` no trae segundos y el
            # último movimiento sí. Un cambio cargado en el mismo minuto que el anterior
            # quedaría «anterior» por los segundos; se compara al minuto y, dentro de ese
            # minuto, el cambio va en el instante del último movimiento.
            if momento < ultimo.replace(second=0, microsecond=0):
                raise forms.ValidationError(
                    "La asignación no puede ser anterior al último movimiento de la estadía."
                    if self.asigna
                    else "El cambio no puede ser anterior al último movimiento de la estadía."
                )
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
        # Tildado de fábrica: el alta de un turno es, por abrumadora mayoría, un turno que
        # empieza a regir. Lo pide el render sin JS —Alpine lo pisa al elegir un turno de la
        # lista—, y desde que `crear_turno` honra el interruptor un alta sin el campo crearía
        # un turno dado de baja sin que nadie lo haya pedido.
        initial=True,
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


# --------------------------------------------------------------------------- #
# Capacidad instalada: sectores, plazas y edificio (carril C5 · P5 y P19)
# --------------------------------------------------------------------------- #
# Las reglas de fondo —nombre único en el dispositivo, tipo de plaza que el tipo de
# institución admite, sector sin plazas tomadas para darlo de baja, código de edificio
# único— las sostienen `programas.services.plazas` y `programas.services.edificios`, que
# releen con la fila bloqueada. Acá va lo que el operador puede corregir sin salir del modal.


class SectorForm(forms.Form):
    """Alta y edición de un sector (P5: «Nuevo sector» y «Editar sector»).

    `capacidad` es la cifra **declarada**, la del legajo: la operativa sale de contar las
    plazas y la deriva el servicio de ocupación. Que no coincidan no es un error —P5 ya lo
    muestra como diferencia— y por eso el formulario no las confronta.
    """

    nombre = forms.CharField(
        label="Nombre",
        max_length=120,
        widget=forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "Pabellón A"}),
        error_messages={"required": "El sector necesita un nombre."},
    )
    tipo = forms.ChoiceField(
        label="Tipo de sector",
        choices=Sector.Tipo.choices,
        initial=Sector.Tipo.HABITACION,
        widget=forms.Select(attrs={"class": INPUT_CLASS}),
    )
    perfil = forms.CharField(
        label="Perfil de la población",
        max_length=120,
        required=False,
        widget=forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "varones, mujeres, tránsito…"}),
    )
    capacidad = forms.IntegerField(
        label="Capacidad declarada",
        min_value=0,
        initial=0,
        widget=forms.NumberInput(attrs={"class": INPUT_CLASS, "min": 0}),
        help_text="La del legajo. La operativa se cuenta desde las plazas cargadas.",
    )
    condiciones_uso = forms.CharField(
        label="Condiciones de uso",
        required=False,
        widget=forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 3, "placeholder": "Opcional"}),
    )
    activo = forms.BooleanField(
        label="Sector activo",
        required=False,
        initial=True,
        widget=SwitchInput,
        help_text="Un sector dado de baja deja de dibujarse en el mapa y de ofrecerse para ingresar.",
    )

    def __init__(self, *args, sector=None, **kwargs):
        """Con `sector`, es edición: el switch de baja existe solo ahí.

        En el alta el sector nace activo, y ofrecer «dar de baja» en el mismo formulario
        que lo crea sería una casilla que nadie toca.
        """

        super().__init__(*args, **kwargs)
        self.sector = sector
        if sector is None:
            del self.fields["activo"]
        elif not self.is_bound:
            for campo in ("nombre", "tipo", "perfil", "capacidad", "condiciones_uso", "activo"):
                self.initial.setdefault(campo, getattr(sector, campo))


class AgregarPlazasForm(forms.Form):
    """Lote de plazas de P5 («+ Agregar plazas»): a qué sector, cuántas y con qué código.

    Los tipos ofrecidos son los que el **tipo de institución** admite
    (`TipoDispositivo.tipos_plaza_admitidos`); con la lista vacía —«sin restricción
    declarada»— se ofrecen los tres. El servicio lo vuelve a exigir.
    """

    sector = forms.ModelChoiceField(
        label="Sector",
        queryset=None,
        empty_label="Elegí el sector",
        widget=forms.Select(attrs={"class": INPUT_CLASS}),
        error_messages={"required": "Elegí a qué sector agregar las plazas."},
    )
    cantidad = forms.IntegerField(
        label="Cantidad",
        min_value=1,
        max_value=TOPE_POR_LOTE,
        widget=forms.NumberInput(attrs={"class": INPUT_CLASS, "min": 1, "max": TOPE_POR_LOTE}),
        help_text=f"Hasta {TOPE_POR_LOTE} por vez.",
        error_messages={"required": "Indicá cuántas plazas agregar."},
    )
    tipo = forms.ChoiceField(
        label="Tipo de plaza",
        choices=Plaza.Tipo.choices,
        widget=forms.Select(attrs={"class": INPUT_CLASS}),
    )
    prefijo = forms.CharField(
        label="Prefijo del código",
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "A-"}),
        help_text="Opcional. El número va detrás, de a dos dígitos: con «A-», A-01, A-02…",
    )

    def __init__(self, *args, dispositivo, sectores, **kwargs):
        super().__init__(*args, **kwargs)
        self.dispositivo = dispositivo
        # El label de Sector usa el código del dispositivo; cargarlo una vez evita
        # una consulta por opción cuando hay varios pabellones en el modal.
        self.fields["sector"].queryset = sectores.select_related("dispositivo")
        admitidos = dispositivo.tipo.tipos_de_plaza
        if admitidos:
            self.fields["tipo"].choices = [
                (valor, etiqueta) for valor, etiqueta in Plaza.Tipo.choices if valor in admitidos
            ]
        self.fields["tipo"].initial = self.fields["tipo"].choices[0][0]


class PlazaForm(forms.Form):
    """Identidad de la plaza; el estado operativo se cambia desde su acción propia."""

    codigo = forms.CharField(label="Código", max_length=50, widget=forms.TextInput(attrs={"class": INPUT_CLASS}))
    tipo = forms.ChoiceField(
        label="Tipo de plaza", choices=Plaza.Tipo.choices, widget=forms.Select(attrs={"class": INPUT_CLASS})
    )

    def __init__(self, *args, dispositivo, plaza, **kwargs):
        super().__init__(*args, **kwargs)
        admitidos = dispositivo.tipo.tipos_de_plaza
        if admitidos:
            self.fields["tipo"].choices = [
                (valor, etiqueta) for valor, etiqueta in Plaza.Tipo.choices if valor in admitidos
            ]
        if not self.is_bound:
            self.initial.update(codigo=plaza.codigo, tipo=plaza.tipo)


class EdificioForm(forms.Form):
    """Alta y edición del inmueble (P19 · solapa Infraestructura).

    El domicilio va **normalizado**, cada parte en su campo: `Dispositivo.domicilio` es una
    línea libre que no se puede comparar entre las instituciones de un mismo predio, y el
    edificio es justo lo que las junta.
    """

    codigo = forms.CharField(
        label="Código del edificio",
        max_length=50,
        widget=forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "EDI-001"}),
        error_messages={"required": "El edificio necesita un código."},
    )
    nombre = forms.CharField(
        label="Nombre",
        max_length=200,
        widget=forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "Predio Av. Sarmiento"}),
        error_messages={"required": "El edificio necesita un nombre."},
    )
    calle = forms.CharField(
        label="Calle", max_length=160, required=False, widget=forms.TextInput(attrs={"class": INPUT_CLASS})
    )
    numero = forms.CharField(
        label="Número", max_length=20, required=False, widget=forms.TextInput(attrs={"class": INPUT_CLASS})
    )
    piso_departamento = forms.CharField(
        label="Piso/Departamento", max_length=40, required=False, widget=forms.TextInput(attrs={"class": INPUT_CLASS})
    )
    localidad = forms.CharField(
        label="Localidad", max_length=120, required=False, widget=forms.TextInput(attrs={"class": INPUT_CLASS})
    )
    provincia = forms.CharField(
        label="Provincia",
        max_length=120,
        required=False,
        initial="Chaco",
        widget=forms.TextInput(attrs={"class": INPUT_CLASS}),
    )
    codigo_postal = forms.CharField(
        label="Código postal", max_length=10, required=False, widget=forms.TextInput(attrs={"class": INPUT_CLASS})
    )

    def __init__(self, *args, edificio=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.edificio = edificio
        if edificio is not None and not self.is_bound:
            self.initial.setdefault("codigo", edificio.codigo)
            for campo in CAMPOS_EDIFICIO:
                self.initial.setdefault(campo, getattr(edificio, campo))


class VincularEdificioForm(forms.Form):
    """Predio compartido: sumar a esta institución un edificio que ya existe.

    El selector llega acotado por `edificios.edificios_vinculables`, que solo ofrece los
    del alcance del usuario: sin eso, el combo sería la lista de los inmuebles de todas
    las instituciones de la provincia.
    """

    edificio = forms.ModelChoiceField(
        label="Edificio",
        queryset=None,
        empty_label="Elegí un edificio",
        widget=forms.Select(attrs={"class": INPUT_CLASS}),
        error_messages={"required": "Elegí el edificio a vincular."},
        help_text="Solo los edificios de tu alcance que esta institución todavía no ocupa.",
    )

    def __init__(self, *args, edificios, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["edificio"].queryset = edificios
