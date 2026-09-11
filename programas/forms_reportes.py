"""Filtros validados para los reportes transversales de Becas y el dashboard del programa."""

from datetime import timedelta

from django import forms
from django.contrib.auth.models import User
from django.utils import timezone

from programas.models import Convocatoria, Relevamiento, Segmento
from programas.services.autorizacion import (
    convocatorias_visibles,
    segmentos_visibles,
    usuarios_territoriales_becas,
)
from programas.services.dashboard_becas import Filtros, preguntas_graficables


class ReporteBecasFiltroForm(forms.Form):
    segmento = forms.ModelChoiceField(queryset=Segmento.objects.none(), required=False)
    convocatoria = forms.ModelChoiceField(queryset=Convocatoria.objects.none(), required=False)
    territorial = forms.ModelChoiceField(queryset=User.objects.none(), required=False)
    desde = forms.DateField(required=False, input_formats=["%Y-%m-%d"])
    hasta = forms.DateField(required=False, input_formats=["%Y-%m-%d"])
    estado = forms.ChoiceField(
        required=False, choices=(("", "Todas"), ("activas", "Activas"), ("cerradas", "Cerradas"))
    )
    solo_activos = forms.BooleanField(required=False)

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        convocatorias = convocatorias_visibles(user)
        self.fields["segmento"].queryset = segmentos_visibles(user)
        self.fields["convocatoria"].queryset = convocatorias
        self.fields["territorial"].queryset = (
            usuarios_territoriales_becas().filter(relevamientos_asignados__convocatoria__in=convocatorias).distinct()
        )

    def clean(self):
        datos = super().clean()
        desde, hasta = datos.get("desde"), datos.get("hasta")
        if desde and hasta and desde > hasta:
            raise forms.ValidationError("La fecha desde no puede ser posterior a la fecha hasta.")
        return datos

    def parametros(self, codigo):
        datos = self.cleaned_data
        comunes = {"desde": datos.get("desde"), "hasta": datos.get("hasta")}
        if codigo == "cupos":
            return {
                "segmento_id": getattr(datos.get("segmento"), "pk", None),
                "solo_activos": datos.get("solo_activos", False),
            }
        if codigo == "avance":
            return {
                **comunes,
                "segmento_id": getattr(datos.get("segmento"), "pk", None),
                "estado": datos.get("estado") or None,
            }
        if codigo == "produccion":
            return {
                **comunes,
                "segmento_id": getattr(datos.get("segmento"), "pk", None),
                "territorial_id": getattr(datos.get("territorial"), "pk", None),
            }
        if codigo == "embudo":
            return {**comunes, "convocatoria_id": getattr(datos.get("convocatoria"), "pk", None)}
        return {
            **comunes,
            "segmento_id": getattr(datos.get("segmento"), "pk", None),
            "convocatoria_id": getattr(datos.get("convocatoria"), "pk", None),
        }


class DashboardBecasFiltroForm(forms.Form):
    """Filtros de la solapa Dashboard del programa (análisis #366, RN-4 a RN-7).

    Recorta los querysets por alcance del usuario **y** por programa; traduce el
    período a fechas; el relevamiento solo vale dentro de la convocatoria elegida
    (RN-5) y la convocatoria dentro del segmento elegido (RN-6).
    """

    PERIODO_30, PERIODO_90, PERIODO_ANIO, PERIODO_TODO, PERIODO_CUSTOM = "30", "90", "anio", "todo", "custom"
    PERIODOS = (
        (PERIODO_30, "Últimos 30 días"),
        (PERIODO_90, "Últimos 90 días"),
        (PERIODO_ANIO, "Este año"),
        (PERIODO_TODO, "Todo el período"),
        (PERIODO_CUSTOM, "Personalizado"),
    )

    periodo = forms.ChoiceField(required=False, choices=PERIODOS, initial=PERIODO_90)
    desde = forms.DateField(required=False, input_formats=["%Y-%m-%d"])
    hasta = forms.DateField(required=False, input_formats=["%Y-%m-%d"])
    segmento = forms.ModelChoiceField(queryset=Segmento.objects.none(), required=False)
    convocatoria = forms.ModelChoiceField(queryset=Convocatoria.objects.none(), required=False)
    relevamiento = forms.ModelChoiceField(queryset=Relevamiento.objects.none(), required=False)
    canal = forms.ChoiceField(required=False, choices=(("", "Ambos"),) + tuple(Relevamiento.Tipo.choices))
    # CharField y no ChoiceField: una clave vieja (pregunta borrada) no invalida todo
    # el tablero; ``clave_pregunta`` cae a la primera del catálogo.
    pregunta = forms.CharField(required=False, max_length=40)

    def __init__(self, *args, user, programa, **kwargs):
        super().__init__(*args, **kwargs)
        self.user, self.programa = user, programa
        # ``programa`` es el ProgramaSiis de la pantalla; el alcance por rol lo resuelve
        # autorizacion con su propio Programa del RBAC (ver docstring del servicio).
        self.fields["segmento"].queryset = segmentos_visibles(user).filter(programa=programa).order_by("nombre")
        convocatorias = convocatorias_visibles(user).filter(segmento__programa=programa)
        self.fields["convocatoria"].queryset = convocatorias.select_related("segmento").order_by(
            "-fecha_inicio", "nombre"
        )
        self.fields["relevamiento"].queryset = Relevamiento.objects.filter(convocatoria__in=convocatorias).order_by(
            "numero"
        )
        self.preguntas = preguntas_graficables(user, programa)

    def clean(self):
        datos = super().clean()
        periodo = datos.get("periodo") or self.PERIODO_90
        hoy = timezone.localdate()
        if periodo == self.PERIODO_CUSTOM:
            desde, hasta = datos.get("desde"), datos.get("hasta")
            if not desde or not hasta:
                raise forms.ValidationError("Indicá desde y hasta para el período personalizado.")
            if desde > hasta:
                raise forms.ValidationError("La fecha desde no puede ser posterior a la fecha hasta.")
        elif periodo == self.PERIODO_TODO:
            desde, hasta = None, None
        elif periodo == self.PERIODO_ANIO:
            desde, hasta = hoy.replace(month=1, day=1), hoy
        else:
            dias = 30 if periodo == self.PERIODO_30 else 90
            desde, hasta = hoy - timedelta(days=dias - 1), hoy
        datos["periodo"], datos["desde"], datos["hasta"] = periodo, desde, hasta

        convocatoria, segmento, relevamiento = (
            datos.get("convocatoria"),
            datos.get("segmento"),
            datos.get("relevamiento"),
        )
        # RN-6: una convocatoria de otro segmento se limpia, no se rechaza.
        if convocatoria and segmento and convocatoria.segmento_id != segmento.pk:
            datos["convocatoria"] = convocatoria = None
        # RN-5: el relevamiento solo vale dentro de la convocatoria elegida.
        if relevamiento and (not convocatoria or relevamiento.convocatoria_id != convocatoria.pk):
            datos["relevamiento"] = None
        return datos

    def filtros(self):
        datos = self.cleaned_data
        return Filtros(
            desde=datos.get("desde"),
            hasta=datos.get("hasta"),
            segmento_id=getattr(datos.get("segmento"), "pk", None),
            convocatoria_id=getattr(datos.get("convocatoria"), "pk", None),
            relevamiento_id=getattr(datos.get("relevamiento"), "pk", None),
            canal=datos.get("canal") or None,
        )

    def clave_pregunta(self):
        """La pregunta elegida si sigue en el catálogo; si no, la primera; si no hay, None."""
        clave = self.cleaned_data.get("pregunta")
        if clave and any(p.clave == clave for p in self.preguntas):
            return clave
        return self.preguntas[0].clave if self.preguntas else None

    def relevamientos_de(self, convocatoria):
        """Opciones del selector de relevamiento para la convocatoria elegida (RN-5)."""
        if convocatoria is None:
            return []
        qs = self.fields["relevamiento"].queryset.filter(convocatoria=convocatoria).select_related("territorial")
        return [
            {
                "id": rel.pk,
                "nombre": rel.nombre,
                "tipo": rel.get_tipo_display(),
                "territorial": (rel.territorial.get_full_name().strip() or rel.territorial.username)
                if rel.territorial_id
                else "",
                "estado": rel.get_estado_display(),
            }
            for rel in qs
        ]
