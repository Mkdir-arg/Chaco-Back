from django.contrib import admin

from mapa.models import Punto


@admin.register(Punto)
class PuntoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "categoria", "latitud", "longitud", "cargado_por", "modificado")
    list_filter = ("categoria",)
    search_fields = ("nombre", "descripcion")
    raw_id_fields = ("cargado_por",)
    readonly_fields = ("creado", "modificado")
