"""Formularios del backoffice de Programas."""

from calendar import monthrange
from collections import OrderedDict

from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date

from core.models import Localidad, Municipio
from core.selectors.geografia import localidades_operativas, municipios_operativos
from programas.models import (
    AsignacionCoordinador,
    Cama,
    CampoTipoDispositivo,
    Convocatoria,
    Dispositivo,
    EntregaMercaderia,
    Formulario,
    PreguntaGlobal,
    PrestacionDiaria,
    RegistroDiario,
    Relevamiento,
    RequisitoNativo,
    Segmento,
    SolicitudMerendero,
    Subsegmento,
    TipoCampo,
    TipoDispositivo,
)
from programas.services.becas import es_menor
from programas.services.dispositivos import normalizar_codigo_institucional
from programas.services.siis import SiisCatalogError, listar_programas

# Clase reutilizable del design system para inputs/selects/textareas.
# Definida en static/custom/css/nodo-forms.css (alto 42px, foco de marca con ring).
INPUT_CLASS = "nodo-field"
CHECKBOX_CLASS = "h-4 w-4 rounded border-base text-fg-brand focus:ring-brand"


def _catalogo_choices(items, empty_label):
    return [("", empty_label)] + [(str(item["id"]), item["nombre"]) for item in items]


def _cargar_catalogo(loader):
    try:
        return loader(), ""
    except SiisCatalogError as exc:
        return [], str(exc)
    except Exception:
        return [], "No se pudo cargar el catálogo de SIIS. Verificá la conexión e intentá nuevamente."


def _congelar_programa_siis(instance, programa):
    """Guarda en el segmento la foto del programa al momento de vincularlo.

    Es la referencia contra la que después se compara el estado que informa
    SIIS, y lo que muestra el detalle informativo del segmento.
    """
    ahora = timezone.now()
    instance.siis_programa_datos = programa
    instance.siis_programa_estado = programa.get("estado") or Segmento.EstadoSiis.ACTIVO
    instance.siis_vinculado_en = ahora
    instance.siis_verificado_en = ahora


def _text_widget(rows=3):
    return forms.Textarea(attrs={"class": INPUT_CLASS, "rows": rows})


class SegmentoForm(forms.ModelForm):
    siis_programa_id = forms.ChoiceField(
        label="Programa SIIS", choices=(), widget=forms.Select(attrs={"class": INPUT_CLASS})
    )

    class Meta:
        model = Segmento
        fields = [
            "nombre",
            "descripcion",
            "cupo_maximo",
            "requiere_gps",
            "siis_programa_id",
            "activo",
        ]
        widgets = {
            "nombre": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "descripcion": _text_widget(),
            "cupo_maximo": forms.NumberInput(attrs={"class": INPUT_CLASS, "min": 0}),
            "requiere_gps": forms.CheckboxInput(attrs={"class": CHECKBOX_CLASS}),
            "activo": forms.CheckboxInput(attrs={"class": CHECKBOX_CLASS}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        programas, error = _cargar_catalogo(listar_programas)
        self._programas_siis = {programa["id"]: programa for programa in programas}
        self._siis_programa_id_previo = self.instance.siis_programa_id if self.instance.pk else None
        self.fields["siis_programa_id"].choices = _catalogo_choices(programas, "Seleccioná un programa…")
        actual = self.instance.siis_programa_id if self.instance.pk else None
        if actual and str(actual) not in {value for value, _ in self.fields["siis_programa_id"].choices}:
            # El programa vinculado ya no está en el catálogo activo: se conserva
            # como opción para no perder el vínculo al guardar otro campo.
            etiqueta = self.instance.siis_programa_nombre or f"Programa SIIS #{actual}"
            self.fields["siis_programa_id"].choices += [(str(actual), f"{etiqueta} — inactivo en SIIS")]
        if error:
            self.fields["siis_programa_id"].help_text = error

    def clean_siis_programa_id(self):
        programa_id = int(self.cleaned_data["siis_programa_id"])
        duplicado = Segmento.objects.filter(siis_programa_id=programa_id)
        if self.instance.pk:
            duplicado = duplicado.exclude(pk=self.instance.pk)
        if duplicado.exists():
            raise forms.ValidationError("Ese programa SIIS ya está asociado a otro segmento.")
        return programa_id

    def save(self, commit=True):
        instance = super().save(commit=False)
        programa = self._programas_siis.get(instance.siis_programa_id)
        if programa and instance.siis_programa_id != self._siis_programa_id_previo:
            _congelar_programa_siis(instance, programa)
        if commit:
            instance.save()
        return instance


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
    siis_programa_id = forms.ChoiceField(
        label="Programa SIIS", choices=(), widget=forms.Select(attrs={"class": INPUT_CLASS})
    )

    class Meta:
        model = Segmento
        fields = ["siis_programa_id", "nombre", "descripcion", "cupo_maximo"]
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
        self.fields["nombre"].required = False
        self.fields["descripcion"].required = True
        programas, error = _cargar_catalogo(listar_programas)
        self._programas_siis = {programa["id"]: programa for programa in programas}
        self.fields["siis_programa_id"].choices = _catalogo_choices(programas, "Seleccioná un programa…")
        if error:
            self.fields["siis_programa_id"].help_text = error
        from programas.services.autorizacion import usuarios_coordinadores_becas

        self.fields["coordinador"].queryset = usuarios_coordinadores_becas()
        self.fields["coordinador"].label_from_instance = lambda u: u.get_full_name() or u.username

    def clean_siis_programa_id(self):
        programa_id = int(self.cleaned_data["siis_programa_id"])
        if Segmento.objects.filter(siis_programa_id=programa_id).exists():
            raise forms.ValidationError("Ese programa SIIS ya está asociado a otro segmento.")
        return programa_id

    def clean(self):
        cleaned = super().clean()
        programa_id = cleaned.get("siis_programa_id")
        if programa_id:
            nombre = dict(self.fields["siis_programa_id"].choices).get(str(programa_id))
            if nombre:
                cleaned["nombre"] = nombre
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        programa = self._programas_siis.get(instance.siis_programa_id)
        if programa:
            _congelar_programa_siis(instance, programa)
        if commit:
            instance.save()
        return instance


class SubsegmentoForm(forms.ModelForm):
    """El segmento se fija desde la vista (no es un campo editable)."""

    class Meta:
        model = Subsegmento
        fields = ["nombre", "descripcion", "cupo_maximo", "referente"]
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
            "referente": forms.Select(attrs={"class": INPUT_CLASS}),
        }

    def __init__(self, *args, segmento=None, **kwargs):
        super().__init__(*args, **kwargs)
        # El subsegmento es local: su nombre lo escribe el operador. Antes se
        # copiaba del catálogo de segmentos de SIIS, que ECOM dejó de exponer.
        self.fields["descripcion"].required = False
        if segmento is not None:
            self.instance.segmento = segmento
        # Un solo referente por subsegmento: elegir otro reemplaza al anterior.
        from programas.services.autorizacion import usuarios_coordinadores_regionales_becas

        self.fields["referente"].required = False
        self.fields["referente"].empty_label = "Sin referente asignado"
        self.fields["referente"].queryset = usuarios_coordinadores_regionales_becas()
        self.fields["referente"].label_from_instance = lambda u: u.get_full_name() or u.username

    def clean_nombre(self):
        nombre = (self.cleaned_data.get("nombre") or "").strip()
        duplicado = Subsegmento.objects.filter(segmento_id=self.instance.segmento_id, nombre__iexact=nombre)
        if self.instance.pk:
            duplicado = duplicado.exclude(pk=self.instance.pk)
        if duplicado.exists():
            raise forms.ValidationError("Ya existe un subsegmento con ese nombre en este segmento.")
        return nombre


class _OpcionesMixin(forms.ModelForm):
    """Maneja ``opciones`` (JSON) vía un textarea (una opción por línea), válido
    solo para los tipos SELECTOR / SELECTOR_MULTIPLE."""

    opciones_texto = forms.CharField(
        required=False,
        label="Opciones (una por línea)",
        help_text="Solo para Selector / Selector múltiple.",
        widget=forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 4}),
    )
    tipo_field_name = "tipo"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.opciones:
            self.fields["opciones_texto"].initial = "\n".join(self.instance.opciones)

    def clean(self):
        cleaned = super().clean()
        tipo = cleaned.get(self.tipo_field_name)
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


class _OrdenUnicoMixin:
    """``orden`` opcional y sin repetidos dentro de su alcance.

    Si el operador no lo escribe, se autonumera como el último + 1; si lo
    escribe, no puede chocar con el de otro registro del mismo alcance (dos
    requisitos no pueden compartir la misma posición en el formulario).
    Las subclases definen el alcance en ``hermanos_orden()``.
    """

    # Texto del error de choque; las subclases lo ajustan al alcance real.
    mensaje_orden_duplicado = "Ya hay otro registro con el orden {orden}. Elegí un número libre."

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        campo = self.fields["orden"]
        campo.required = False
        campo.help_text = "Si lo dejás vacío se numera automáticamente."
        campo.widget.attrs.setdefault("placeholder", "Automático")

    def hermanos_orden(self):
        """Queryset de los registros que comparten la numeración."""
        raise NotImplementedError

    def clean_orden(self):
        orden = self.cleaned_data.get("orden")
        hermanos = self.hermanos_orden()
        if self.instance.pk:
            hermanos = hermanos.exclude(pk=self.instance.pk)
        if orden in (None, ""):
            ultimo = hermanos.aggregate(m=models.Max("orden"))["m"]
            return (ultimo or 0) + 1
        if hermanos.filter(orden=orden).exists():
            raise forms.ValidationError(self.mensaje_orden_duplicado.format(orden=orden))
        return orden


class TipoDispositivoForm(forms.ModelForm):
    class Meta:
        model = TipoDispositivo
        fields = [
            "codigo",
            "nombre",
            "descripcion",
            "maneja_camas",
            "umbral_ocupacion_amarillo",
            "umbral_ocupacion_rojo",
            "activo",
        ]
        widgets = {
            "codigo": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "nombre": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "descripcion": _text_widget(rows=3),
            "maneja_camas": forms.CheckboxInput(attrs={"class": CHECKBOX_CLASS}),
            "umbral_ocupacion_amarillo": forms.NumberInput(attrs={"class": INPUT_CLASS, "min": 0, "max": 100}),
            "umbral_ocupacion_rojo": forms.NumberInput(attrs={"class": INPUT_CLASS, "min": 0, "max": 100}),
            "activo": forms.CheckboxInput(attrs={"class": CHECKBOX_CLASS}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for nombre, default in (
            ("umbral_ocupacion_amarillo", 50),
            ("umbral_ocupacion_rojo", 80),
        ):
            self.fields[nombre].required = False
            self.fields[nombre].initial = getattr(self.instance, nombre, default) or default

    def clean(self):
        cleaned = super().clean()
        amarillo = cleaned.get("umbral_ocupacion_amarillo")
        rojo = cleaned.get("umbral_ocupacion_rojo")
        cleaned["umbral_ocupacion_amarillo"] = (
            amarillo if amarillo is not None else getattr(self.instance, "umbral_ocupacion_amarillo", 50) or 50
        )
        cleaned["umbral_ocupacion_rojo"] = (
            rojo if rojo is not None else getattr(self.instance, "umbral_ocupacion_rojo", 80) or 80
        )
        if cleaned["umbral_ocupacion_amarillo"] >= cleaned["umbral_ocupacion_rojo"]:
            self.add_error("umbral_ocupacion_rojo", "El umbral rojo debe ser mayor que el amarillo.")
        return cleaned


class DispositivoForm(forms.ModelForm):
    """Alta y edición del legajo institucional de un dispositivo."""

    class Meta:
        model = Dispositivo
        fields = [
            "tipo",
            "codigo",
            "nombre",
            "localidad",
            "domicilio",
            "latitud",
            "longitud",
            "responsable_nombre",
            "responsable_documento",
            "contacto_telefono",
            "contacto_email",
            "horarios",
        ]
        widgets = {
            "tipo": forms.Select(attrs={"class": INPUT_CLASS}),
            "codigo": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "nombre": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "localidad": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "domicilio": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "latitud": forms.NumberInput(attrs={"class": INPUT_CLASS, "step": "0.000001"}),
            "longitud": forms.NumberInput(attrs={"class": INPUT_CLASS, "step": "0.000001"}),
            "responsable_nombre": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "responsable_documento": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "contacto_telefono": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "contacto_email": forms.EmailInput(attrs={"class": INPUT_CLASS}),
            "horarios": _text_widget(rows=3),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tipos = TipoDispositivo.objects.all()
        if self.instance.pk and self.instance.tipo_id:
            tipos = tipos.filter(Q(activo=True) | Q(pk=self.instance.tipo_id))
        else:
            tipos = tipos.filter(activo=True)
        self.fields["tipo"].queryset = tipos.order_by("nombre")

    def clean_codigo(self):
        codigo = normalizar_codigo_institucional(self.cleaned_data["codigo"])
        duplicado = Dispositivo.objects.filter(codigo__iexact=codigo)
        if self.instance.pk:
            duplicado = duplicado.exclude(pk=self.instance.pk)
        if duplicado.exists():
            raise forms.ValidationError("Ya existe un dispositivo con este código institucional.")
        return codigo


class CantidadCamasForm(forms.Form):
    cantidad = forms.IntegerField(
        min_value=1,
        label="Cantidad de camas a agregar",
        widget=forms.NumberInput(attrs={"class": INPUT_CLASS, "min": 1}),
    )


class CamaForm(forms.ModelForm):
    class Meta:
        model = Cama
        fields = ["codigo", "estado"]
        widgets = {
            "codigo": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "estado": forms.Select(attrs={"class": INPUT_CLASS}),
        }

    def clean_codigo(self):
        return normalizar_codigo_institucional(self.cleaned_data["codigo"])


class CampoTipoDispositivoForm(_OpcionesMixin):
    tipo_field_name = "tipo_campo"

    class Meta:
        model = CampoTipoDispositivo
        fields = ["seccion", "nombre", "tipo_campo", "obligatorio", "rol_calculo", "orden"]
        widgets = {
            "seccion": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "nombre": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "tipo_campo": forms.Select(attrs={"class": INPUT_CLASS}),
            "obligatorio": forms.CheckboxInput(attrs={"class": CHECKBOX_CLASS}),
            "rol_calculo": forms.Select(attrs={"class": INPUT_CLASS}),
            "orden": forms.NumberInput(attrs={"class": INPUT_CLASS, "min": 0}),
        }

    def __init__(self, *args, tipo_dispositivo=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["rol_calculo"].required = False
        if tipo_dispositivo is not None:
            self.instance.tipo_dispositivo = tipo_dispositivo

    def clean_rol_calculo(self):
        return self.cleaned_data.get("rol_calculo") or CampoTipoDispositivo.RolCalculo.NINGUNO


class BusquedaCiudadanoDNIForm(forms.Form):
    dni = forms.CharField(
        label="DNI",
        max_length=20,
        widget=forms.TextInput(attrs={"class": INPUT_CLASS, "inputmode": "numeric", "autocomplete": "off"}),
    )
    sexo = forms.ChoiceField(
        label="Sexo registral (solo para consultar RENAPER si no existe el legajo)",
        choices=[("", "No consultar RENAPER"), ("M", "Masculino"), ("F", "Femenino")],
        required=False,
        widget=forms.Select(attrs={"class": INPUT_CLASS}),
    )

    def clean_dni(self):
        dni = "".join(filter(str.isdigit, self.cleaned_data["dni"]))
        if not 7 <= len(dni) <= 8:
            raise forms.ValidationError("El DNI debe tener entre 7 y 8 dígitos.")
        return dni


class CiudadanoAdmisionForm(forms.Form):
    """Alta mínima solo para un DNI que aún no existe en Legajos."""

    dni = forms.CharField(widget=forms.HiddenInput())
    nombre = forms.CharField(label="Nombre", max_length=120, widget=forms.TextInput(attrs={"class": INPUT_CLASS}))
    apellido = forms.CharField(label="Apellido", max_length=120, widget=forms.TextInput(attrs={"class": INPUT_CLASS}))
    fecha_nacimiento = forms.DateField(
        label="Fecha de nacimiento",
        required=False,
        widget=forms.DateInput(attrs={"class": INPUT_CLASS, "type": "date"}),
    )
    genero = forms.ChoiceField(
        label="Género",
        choices=[("", "Sin informar"), ("M", "Masculino"), ("F", "Femenino"), ("X", "No binario")],
        required=False,
        widget=forms.Select(attrs={"class": INPUT_CLASS}),
    )
    domicilio = forms.CharField(
        label="Domicilio", max_length=240, required=False, widget=forms.TextInput(attrs={"class": INPUT_CLASS})
    )

    def clean_dni(self):
        return "".join(filter(str.isdigit, self.cleaned_data["dni"]))


class F00DinamicoForm(forms.Form):
    """Renderiza y valida la configuración vigente del tipo de dispositivo."""

    @staticmethod
    def es_egreso(campo):
        return campo.rol_calculo == CampoTipoDispositivo.RolCalculo.EGRESO

    @staticmethod
    def es_ingreso(campo):
        return campo.rol_calculo == CampoTipoDispositivo.RolCalculo.INGRESO

    def __init__(self, *args, tipo_dispositivo, ciudadano=None, respuestas=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.campos_configurados = list(tipo_dispositivo.campos_configurados.all().order_by("orden", "id"))
        respuestas = respuestas or {}
        agrupados = OrderedDict()
        for campo in self.campos_configurados:
            nombre = self.nombre_campo(campo)
            inicial = respuestas.get(str(campo.pk))
            if inicial is None and ciudadano is not None and "obra social" in campo.nombre.casefold():
                inicial = ciudadano.obra_social
            opciones = [(opcion, opcion) for opcion in (campo.opciones or [])]
            kwargs_campo = {"label": campo.nombre, "required": campo.obligatorio, "initial": inicial}
            if campo.tipo_campo == TipoCampo.INT:
                field = forms.IntegerField(
                    widget=forms.NumberInput(attrs={"class": INPUT_CLASS, "step": 1}), **kwargs_campo
                )
            elif campo.tipo_campo == TipoCampo.SELECTOR:
                field = forms.ChoiceField(
                    choices=[("", "Seleccioná…"), *opciones],
                    widget=forms.Select(attrs={"class": INPUT_CLASS}),
                    **kwargs_campo,
                )
            elif campo.tipo_campo == TipoCampo.SELECTOR_MULTIPLE:
                field = forms.MultipleChoiceField(
                    choices=opciones,
                    widget=forms.CheckboxSelectMultiple(attrs={"class": CHECKBOX_CLASS}),
                    **kwargs_campo,
                )
            elif campo.tipo_campo == TipoCampo.DATE:
                field = forms.DateField(
                    widget=forms.DateInput(attrs={"class": INPUT_CLASS, "type": "date"}), **kwargs_campo
                )
            elif campo.tipo_campo == TipoCampo.ARCHIVO:
                field = forms.FileField(widget=forms.ClearableFileInput(attrs={"class": INPUT_CLASS}), **kwargs_campo)
            else:
                field = forms.CharField(widget=forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 2}), **kwargs_campo)
            field.widget.attrs["data-f00-campo"] = str(campo.pk)
            if campo.tipo_campo == TipoCampo.INT:
                if self.es_egreso(campo):
                    field.widget.attrs["data-f00-egreso"] = "true"
                elif self.es_ingreso(campo):
                    field.widget.attrs["data-f00-ingreso"] = "true"
            self.fields[nombre] = field
            agrupados.setdefault(campo.seccion, []).append({"campo": campo, "bound": self[nombre]})
        self.secciones = [{"nombre": nombre, "campos": campos} for nombre, campos in agrupados.items()]

    @staticmethod
    def nombre_campo(campo):
        return f"f00_{campo.pk}"

    def respuestas_y_archivos(self):
        respuestas, archivos = {}, {}
        for campo in self.campos_configurados:
            valor = self.cleaned_data.get(self.nombre_campo(campo))
            if campo.tipo_campo == TipoCampo.ARCHIVO:
                if valor:
                    archivos[campo] = valor
                continue
            if hasattr(valor, "isoformat"):
                valor = valor.isoformat()
            respuestas[str(campo.pk)] = valor
        egresos = sum(
            self.cleaned_data.get(self.nombre_campo(campo)) or 0
            for campo in self.campos_configurados
            if campo.tipo_campo == TipoCampo.INT and self.es_egreso(campo)
        )
        ingresos = sum(
            self.cleaned_data.get(self.nombre_campo(campo)) or 0
            for campo in self.campos_configurados
            if campo.tipo_campo == TipoCampo.INT and self.es_ingreso(campo)
        )
        if any(campo.rol_calculo != CampoTipoDispositivo.RolCalculo.NINGUNO for campo in self.campos_configurados):
            respuestas["_totales"] = {"egresos": egresos, "ingresos": ingresos, "saldo_estimado": ingresos - egresos}
        return respuestas, archivos


class EgresoAdmisionForm(forms.Form):
    fecha_egreso = forms.DateTimeField(
        label="Fecha y hora de egreso",
        widget=forms.DateTimeInput(attrs={"class": INPUT_CLASS, "type": "datetime-local"}),
    )
    motivo = forms.CharField(label="Motivo", widget=_text_widget(), required=True)
    destino = forms.CharField(
        label="Destino", max_length=240, widget=forms.TextInput(attrs={"class": INPUT_CLASS}), required=True
    )


class TrasladoAdmisionForm(forms.Form):
    destino = forms.ModelChoiceField(
        queryset=Dispositivo.objects.none(),
        label="Dispositivo de destino",
        widget=forms.Select(attrs={"class": INPUT_CLASS}),
    )
    cama = forms.ModelChoiceField(
        queryset=Cama.objects.none(),
        label="Cama de destino",
        required=False,
        widget=forms.Select(attrs={"class": INPUT_CLASS}),
    )

    def __init__(self, *args, dispositivos=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["destino"].queryset = (dispositivos or Dispositivo.objects.none()).filter(
            estado=Dispositivo.Estado.ACTIVO
        )
        self.fields["cama"].queryset = Cama.objects.filter(estado=Cama.Estado.DISPONIBLE).select_related("dispositivo")

    def clean(self):
        cleaned = super().clean()
        destino, cama = cleaned.get("destino"), cleaned.get("cama")
        if cama and destino and cama.dispositivo_id != destino.pk:
            self.add_error("cama", "La cama debe pertenecer al dispositivo de destino.")
        return cleaned


class PromoverEsperaForm(forms.Form):
    cama = forms.ModelChoiceField(
        queryset=Cama.objects.none(), label="Cama disponible", widget=forms.Select(attrs={"class": INPUT_CLASS})
    )

    def __init__(self, *args, dispositivo, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cama"].queryset = Cama.objects.filter(dispositivo=dispositivo, estado=Cama.Estado.DISPONIBLE)


class RegistroDiarioForm(forms.ModelForm):
    OBSERVACIONES_POR_CONCEPTO = (
        ("camas_totales", "Camas totales"),
        ("ingresos", "Ingresos"),
        ("egresos", "Egresos"),
        ("ocupacion_nocturna", "Ocupación nocturna"),
        ("camas_disponibles", "Camas disponibles"),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        observaciones = self.instance.observaciones if self.instance.pk else {}
        for clave, etiqueta in self.OBSERVACIONES_POR_CONCEPTO:
            self.fields[f"observacion_{clave}"] = forms.CharField(
                label=f"Observación · {etiqueta}",
                required=False,
                initial=observaciones.get(clave, ""),
                widget=_text_widget(rows=2),
            )

    def observaciones_por_concepto(self):
        return {
            clave: self.cleaned_data[f"observacion_{clave}"].strip()
            for clave, _ in self.OBSERVACIONES_POR_CONCEPTO
            if self.cleaned_data[f"observacion_{clave}"].strip()
        }

    class Meta:
        model = RegistroDiario
        fields = ["turno", "observaciones_generales"]
        widgets = {
            "turno": forms.Select(attrs={"class": INPUT_CLASS}),
            "observaciones_generales": _text_widget(),
        }


class SolicitudMerenderoForm(forms.ModelForm):
    class Meta:
        model = SolicitudMerendero
        fields = [
            "codigo",
            "nombre",
            "domicilio",
            "zona",
            "barrio",
            "dias_horarios",
            "responsable_nombre",
            "responsable_documento",
            "responsable_email",
            "telefono",
            "documentacion",
        ]
        widgets = {
            "codigo": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "nombre": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "domicilio": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "zona": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "barrio": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "dias_horarios": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "responsable_nombre": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "responsable_documento": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "responsable_email": forms.EmailInput(attrs={"class": INPUT_CLASS}),
            "telefono": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "documentacion": forms.ClearableFileInput(attrs={"class": INPUT_CLASS}),
        }

    def clean_codigo(self):
        return normalizar_codigo_institucional(self.cleaned_data["codigo"])

    def __init__(self, *args, validar_completitud=True, **kwargs):
        super().__init__(*args, **kwargs)
        if not validar_completitud:
            for campo in self.fields.values():
                campo.required = False
            return
        for campo in SolicitudMerendero.CAMPOS_INSTITUCIONALES_REQUERIDOS:
            self.fields[campo].required = True


class EntregaMercaderiaForm(forms.ModelForm):
    class Meta:
        model = EntregaMercaderia
        fields = ["fecha", "cantidad_kits", "servicio", "responsable_receptor", "observaciones"]
        widgets = {
            "fecha": forms.DateInput(attrs={"class": INPUT_CLASS, "type": "date"}),
            "cantidad_kits": forms.NumberInput(attrs={"class": INPUT_CLASS, "min": 1}),
            "servicio": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "responsable_receptor": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "observaciones": _text_widget(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["servicio"].required = True


class PrestacionMensualForm(forms.Form):
    """Valida la grilla dinámica de raciones de la planilla F-02."""

    anio = forms.IntegerField(min_value=2000, max_value=2100)
    mes = forms.IntegerField(min_value=1, max_value=12)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dias = self._dias_del_periodo()
        for dia in self.dias:
            for servicio, _etiqueta in PrestacionDiaria.Servicio.choices:
                self.fields[self._nombre_racion(dia, servicio)] = forms.IntegerField(min_value=0, required=False)
            self.fields[self._nombre_observacion(dia)] = forms.CharField(required=False)

    def _dias_del_periodo(self):
        try:
            anio = int(self.data.get("anio"))
            mes = int(self.data.get("mes"))
            if not 2000 <= anio <= 2100 or not 1 <= mes <= 12:
                return ()
            return range(1, monthrange(anio, mes)[1] + 1)
        except (TypeError, ValueError):
            return ()

    @staticmethod
    def _nombre_racion(dia, servicio):
        return f"raciones-{dia}-{servicio}"

    @staticmethod
    def _nombre_observacion(dia):
        return f"observacion-{dia}"

    def clean(self):
        cleaned_data = super().clean()
        if not self.dias or self.errors:
            return cleaned_data

        raciones, observaciones = {}, {}
        for dia in self.dias:
            raciones[dia] = {}
            for servicio, _etiqueta in PrestacionDiaria.Servicio.choices:
                nombre_racion = self._nombre_racion(dia, servicio)
                if nombre_racion not in self.data:
                    self.add_error(nombre_racion, "La grilla de prestación debe enviarse completa.")
                raciones[dia][servicio] = cleaned_data.get(nombre_racion) or 0
            observaciones[dia] = cleaned_data[self._nombre_observacion(dia)]
        if self.errors:
            return cleaned_data
        cleaned_data["raciones"] = raciones
        cleaned_data["observaciones"] = observaciones
        return cleaned_data


class PreguntaGlobalForm(_OrdenUnicoMixin, _OpcionesMixin):
    """Requisitos generales: el orden es único entre todas las preguntas."""

    mensaje_orden_duplicado = "Ya hay otra pregunta con el orden {orden}. Elegí un número libre."

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

    def hermanos_orden(self):
        return PreguntaGlobal.objects.all()


class RequisitoNativoForm(_OrdenUnicoMixin, _OpcionesMixin):
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
        # El orden es único dentro del subsegmento, o del segmento cuando el
        # requisito es propio del segmento (subsegmento nulo).
        self.mensaje_orden_duplicado = (
            "Ya hay otro requisito con el orden {orden} en este "
            f"{'subsegmento' if subsegmento is not None else 'segmento'}. Elegí un número libre."
        )

    def hermanos_orden(self):
        # Por ``_id`` para no explotar cuando el form se instancia sin segmento
        # (la vista de listado lo usa solo para renderizar el modal).
        return RequisitoNativo.objects.filter(
            segmento_id=self.instance.segmento_id, subsegmento_id=self.instance.subsegmento_id
        )


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

        coordinadores = usuarios_coordinadores_becas()
        # En el selector solo se ofrecen coordinadores todavía disponibles para
        # este segmento. En un POST conservamos el queryset completo para que
        # ``clean()`` pueda informar explícitamente una asignación duplicada en
        # lugar de devolver el error genérico de "opción no válida".
        if segmento is not None and not self.is_bound:
            coordinadores = coordinadores.exclude(
                pk__in=AsignacionCoordinador.objects.filter(
                    segmento=segmento,
                ).values("coordinador_id"),
            )
        self.fields["coordinador"].queryset = coordinadores
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
            "fecha_inicio": forms.DateInput(
                format="%Y-%m-%d",
                attrs={"class": INPUT_CLASS, "type": "date"},
            ),
            "fecha_fin": forms.DateInput(
                format="%Y-%m-%d",
                attrs={"class": INPUT_CLASS, "type": "date"},
            ),
            "descripcion": _text_widget(),
            "activo": forms.CheckboxInput(attrs={"class": CHECKBOX_CLASS}),
        }

    def __init__(self, *args, subsegmentos_permitidos=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["subsegmento"].required = False
        segmento_id = self.data.get("segmento") if self.is_bound else self.instance.segmento_id
        try:
            segmento_id = int(segmento_id) if segmento_id else None
        except (TypeError, ValueError):
            segmento_id = None
        subsegmentos = (
            Subsegmento.objects.select_related("segmento").filter(segmento_id=segmento_id)
            if segmento_id
            else Subsegmento.objects.none()
        )
        if subsegmentos_permitidos is not None:
            subsegmentos = subsegmentos.filter(pk__in=subsegmentos_permitidos)
        self.fields["subsegmento"].queryset = subsegmentos
        if self.instance.pk:
            for field_name in ("fecha_inicio", "fecha_fin"):
                self.fields[field_name].required = False
                self.fields[field_name].help_text = "Dejalo sin cambios para mantener la fecha actual."

    def clean(self):
        """ "Fecha manda": no se puede dejar activa una convocatoria con la fecha
        de fin ya vencida. Para reactivar una vencida hay que extender la fecha."""
        cleaned = super().clean()
        if self.instance.pk:
            for field_name in ("fecha_inicio", "fecha_fin"):
                if not cleaned.get(field_name):
                    cleaned[field_name] = getattr(self.instance, field_name)
        activo = cleaned.get("activo")
        fecha_fin = cleaned.get("fecha_fin")
        if activo and fecha_fin and fecha_fin < timezone.localdate():
            self.add_error(
                "fecha_fin",
                "Para activar la convocatoria, extendé la fecha de fin a hoy o una posterior.",
            )
        return cleaned

    def save(self, commit=True):
        # Si queda activa, limpiamos la marca de cierre automático (una
        # reactivación deja de ser un "cierre por vencimiento").
        convocatoria = super().save(commit=False)
        if convocatoria.activo:
            convocatoria.cerrada_automaticamente = False
            convocatoria.cerrada_el = None
        if commit:
            convocatoria.save()
        return convocatoria


class _SelectConSegmento(forms.Select):
    """Select cuyas opciones llevan ``data-segmento``.

    Lo usa el filtro dependiente convocatoria → territorial del alta de
    relevamiento (el JS del template oculta los territoriales que no
    pertenecen al segmento de la convocatoria elegida).
    """

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        instance = getattr(value, "instance", None)
        segmento_id = getattr(instance, "segmento_id", None)
        if segmento_id is None:
            asignacion = getattr(instance, "asignacion_territorial", None)
            segmento_id = getattr(asignacion, "segmento_id", None)
        if segmento_id:
            option["attrs"]["data-segmento"] = segmento_id
        fecha_inicio = getattr(instance, "fecha_inicio", None)
        fecha_fin = getattr(instance, "fecha_fin", None)
        if fecha_inicio and fecha_fin:
            option["attrs"]["data-fecha-inicio"] = fecha_inicio.isoformat()
            option["attrs"]["data-fecha-fin"] = fecha_fin.isoformat()
        return option


class RelevamientoForm(forms.ModelForm):
    """ABM de relevamiento. El territorial se elige entre los usuarios con rol
    Territorial **del segmento de la convocatoria** (``AsignacionTerritorial``).

    La zona dejó de escribirse a mano: se elige del catálogo de localidades
    (`/configuracion/localidades/`) con dos selectores encadenados, Municipio y
    Localidad, ambos acotados a la provincia que opera el sistema. ``zona`` sigue
    siendo texto en el modelo —no hubo migración— y guarda el nombre de la
    localidad elegida; el municipio solo filtra y no se persiste.
    """

    municipio = forms.ModelChoiceField(
        queryset=Municipio.objects.none(),
        label="Municipio",
        empty_label="Elegí un municipio",
        widget=forms.Select(attrs={"class": INPUT_CLASS, "data-municipio": "1"}),
        help_text="Filtra las localidades disponibles.",
    )
    # Pisa el CharField del modelo: el operador elige una Localidad y
    # ``clean_zona`` la reduce al texto que se guarda.
    zona = forms.ModelChoiceField(
        queryset=Localidad.objects.none(),
        label="Localidad",
        empty_label="Elegí primero el municipio",
        widget=forms.Select(attrs={"class": INPUT_CLASS, "data-localidad": "1"}),
    )

    field_order = [
        "convocatoria",
        "territorial",
        "municipio",
        "zona",
        "fecha_asignada",
        "fecha_hasta",
        "cupo_maximo",
        "observaciones",
    ]

    class Meta:
        model = Relevamiento
        fields = [
            "convocatoria",
            "territorial",
            "fecha_asignada",
            "fecha_hasta",
            "zona",
            "cupo_maximo",
            "observaciones",
        ]
        widgets = {
            "convocatoria": forms.Select(attrs={"class": INPUT_CLASS}),
            "territorial": forms.Select(attrs={"class": INPUT_CLASS}),
            "fecha_asignada": forms.DateInput(attrs={"class": INPUT_CLASS, "type": "date"}),
            "fecha_hasta": forms.DateInput(attrs={"class": INPUT_CLASS, "type": "date"}),
            "cupo_maximo": forms.NumberInput(attrs={"class": INPUT_CLASS, "min": 1}),
            "observaciones": forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 3}),
        }

    def __init__(
        self,
        *args,
        segmentos_permitidos=None,
        convocatorias_permitidas=None,
        territoriales_permitidos=None,
        operador=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.operador = operador
        from programas.services.autorizacion import usuarios_territoriales_becas

        terr_qs = usuarios_territoriales_becas().select_related("asignacion_territorial")
        conv_qs = (
            Convocatoria.objects.select_related("segmento", "subsegmento")
            .filter(
                activo=True,
                pausado=False,
                segmento__pausado=False,
            )
            # El bloqueo por SIIS es una property del segmento; acá se filtra por
            # la columna porque esto es un queryset.
            .exclude(segmento__siis_programa_estado__in=Segmento.ESTADOS_SIIS_BLOQUEANTES)
            .filter(models.Q(subsegmento__isnull=True) | models.Q(subsegmento__pausado=False))
        )
        if segmentos_permitidos is not None:
            conv_qs = conv_qs.filter(segmento__in=segmentos_permitidos)
        if convocatorias_permitidas is not None:
            conv_qs = conv_qs.filter(pk__in=convocatorias_permitidas)
        if territoriales_permitidos is not None:
            terr_qs = terr_qs.filter(pk__in=territoriales_permitidos)

        # ModelChoiceIteratorValue expone la instancia de cada opción; así el
        # widget agrega data-segmento sin evaluar ambos querysets por duplicado.
        self.fields["convocatoria"].widget = _SelectConSegmento(attrs={"class": INPUT_CLASS})
        self.fields["territorial"].widget = _SelectConSegmento(attrs={"class": INPUT_CLASS})
        self.fields["territorial"].queryset = terr_qs
        self.fields["territorial"].label_from_instance = lambda u: u.get_full_name() or u.username
        self.fields[
            "territorial"
        ].help_text = "Solo se listan los territoriales del segmento de la convocatoria elegida."
        self.fields["convocatoria"].queryset = conv_qs
        self.fields["observaciones"].required = False
        # Compatibilidad con clientes/formularios anteriores: un relevamiento
        # de un solo día usa fecha_desde como fecha_hasta y el cupo conserva
        # el valor vigente (o el default del modelo en un alta).
        self.fields["fecha_hasta"].required = False
        self.fields["cupo_maximo"].required = False
        self._preparar_localidad()

    def _preparar_localidad(self):
        """Deja listos los dos selectores de la zona.

        El de Localidad se llena por AJAX al elegir el municipio, así que se
        renderiza vacío: mandar las localidades de toda la provincia en cada carga
        de la pantalla es peso muerto, y son cientos. La validación **no** usa esas
        opciones sino el queryset completo, de modo que un POST armado a mano
        tampoco puede meter una localidad de otra provincia.

        Cuando el form vuelve con errores hay que repoblar las opciones del
        municipio elegido, o el operador pierde lo que había seleccionado.
        """
        self.fields["municipio"].queryset = municipios_operativos()
        self.fields["zona"].queryset = localidades_operativas()

        municipio_id = self.data.get(self.add_prefix("municipio")) if self.is_bound else None
        opciones = []
        if municipio_id:
            opciones = [
                (loc.pk, loc.nombre) for loc in self.fields["zona"].queryset.filter(municipio_id=municipio_id)
            ]
        vacia = "Elegí una localidad" if opciones else "Elegí primero el municipio"
        self.fields["zona"].widget.choices = [("", vacia), *opciones]

    def clean_zona(self):
        """Del catálogo al texto: se guarda el nombre de la localidad.

        El cruce contra el municipio se hace acá porque ``field_order`` lo limpia
        antes; después de esto la instancia de Localidad se pierde.
        """
        localidad = self.cleaned_data.get("zona")
        if localidad is None:
            return ""
        municipio = self.cleaned_data.get("municipio")
        if municipio is not None and localidad.municipio_id != municipio.pk:
            raise forms.ValidationError("Esa localidad no pertenece al municipio elegido.")
        return localidad.nombre

    def clean(self):
        cleaned = super().clean()
        convocatoria = cleaned.get("convocatoria")
        territorial = cleaned.get("territorial")
        if convocatoria and territorial:
            try:
                asignacion = territorial.asignacion_territorial
            except ObjectDoesNotExist:
                asignacion = None
            if asignacion is None or asignacion.segmento_id != convocatoria.segmento_id:
                self.add_error("territorial", "El territorial no pertenece al segmento de la convocatoria.")
        fecha_desde = cleaned.get("fecha_asignada")
        fecha_hasta = cleaned.get("fecha_hasta") or fecha_desde
        if fecha_hasta:
            cleaned["fecha_hasta"] = fecha_hasta
        if not cleaned.get("cupo_maximo"):
            cleaned["cupo_maximo"] = self.instance.cupo_maximo or Relevamiento._meta.get_field("cupo_maximo").default
        if fecha_desde and fecha_hasta and fecha_hasta < fecha_desde:
            self.add_error("fecha_hasta", "La fecha hasta no puede ser anterior a la fecha desde.")
        return cleaned


class CupoRelevamientoForm(forms.ModelForm):
    class Meta:
        model = Relevamiento
        fields = ["cupo_maximo"]
        widgets = {"cupo_maximo": forms.NumberInput(attrs={"class": INPUT_CLASS, "min": 1})}

    def clean_cupo_maximo(self):
        cupo = self.cleaned_data["cupo_maximo"]
        utilizados = self.instance.formularios.count()
        if cupo < utilizados:
            raise forms.ValidationError(f"No puede reducirse por debajo de las {utilizados} personas ya relevadas.")
        return cupo


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
        label="Nueva fecha desde",
    )
    fecha_hasta = forms.DateField(
        widget=forms.DateInput(attrs={"class": INPUT_CLASS, "type": "date"}),
        label="Nueva fecha hasta",
    )

    def __init__(self, *args, convocatoria=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["fecha_hasta"].required = False
        self.convocatoria = convocatoria
        if convocatoria is not None:
            for campo in ("fecha_asignada", "fecha_hasta"):
                self.fields[campo].widget.attrs.update(
                    min=convocatoria.fecha_inicio.isoformat(),
                    max=convocatoria.fecha_fin.isoformat(),
                )

    def clean(self):
        cleaned = super().clean()
        fecha_desde = cleaned.get("fecha_asignada")
        fecha_hasta = cleaned.get("fecha_hasta") or fecha_desde
        if fecha_hasta:
            cleaned["fecha_hasta"] = fecha_hasta
        if fecha_desde and fecha_hasta and fecha_hasta < fecha_desde:
            self.add_error("fecha_hasta", "La fecha hasta no puede ser anterior a la fecha desde.")
        if (
            self.convocatoria
            and fecha_desde
            and not self.convocatoria.fecha_inicio <= fecha_desde <= self.convocatoria.fecha_fin
        ):
            inicio = self.convocatoria.fecha_inicio.strftime("%d/%m/%Y")
            fin = self.convocatoria.fecha_fin.strftime("%d/%m/%Y")
            self.add_error(
                "fecha_asignada",
                f"La fecha desde debe estar comprendida dentro del período de la convocatoria ({inicio} - {fin}).",
            )
        if (
            self.convocatoria
            and fecha_hasta
            and not self.convocatoria.fecha_inicio <= fecha_hasta <= self.convocatoria.fecha_fin
        ):
            inicio = self.convocatoria.fecha_inicio.strftime("%d/%m/%Y")
            fin = self.convocatoria.fecha_fin.strftime("%d/%m/%Y")
            self.add_error(
                "fecha_hasta",
                f"La fecha hasta debe estar comprendida dentro del período de la convocatoria ({inicio} - {fin}).",
            )
        return cleaned


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
        "apoderado_dni": "Apoderado · DNI",
        "apoderado_genero": "Apoderado · sexo",
        "apoderado_fecha_nacimiento": "Apoderado · fecha de nacimiento",
    }

    class Meta:
        model = Formulario
        fields = [
            "celular",
            "email_contacto",
            "apoderado_nombre",
            "apoderado_apellido",
            "apoderado_dni",
            "apoderado_genero",
            "apoderado_fecha_nacimiento",
        ]
        widgets = {
            "celular": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "email_contacto": forms.EmailInput(attrs={"class": INPUT_CLASS}),
            "apoderado_nombre": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "apoderado_apellido": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "apoderado_dni": forms.TextInput(attrs={"class": INPUT_CLASS, "inputmode": "numeric"}),
            "apoderado_genero": forms.Select(attrs={"class": INPUT_CLASS}),
            "apoderado_fecha_nacimiento": forms.DateInput(
                format="%Y-%m-%d",
                attrs={"class": INPUT_CLASS, "type": "date"},
            ),
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
            for campo in (
                "apoderado_nombre",
                "apoderado_apellido",
                "apoderado_dni",
                "apoderado_genero",
                "apoderado_fecha_nacimiento",
            ):
                if not cleaned_data.get(campo):
                    self.add_error(campo, "Este dato es obligatorio cuando la persona relevada es menor de edad.")
        return cleaned_data


class CiudadanoGeneroRevisionForm(forms.Form):
    """Carga el sexo registral requerido para consultar RENAPER."""

    genero = forms.ChoiceField(
        label="Sexo",
        choices=[("", "Seleccionar..."), ("M", "M"), ("F", "F"), ("X", "X")],
        widget=forms.RadioSelect(),
    )
