from django.contrib import admin

from core.models import (
    Localidad,
    Provincia,
    Municipio,
    Sexo,
    Mes,
    Dia,
)

admin.site.register(Provincia)
admin.site.register(Municipio)
admin.site.register(Sexo)
admin.site.register(Mes)
admin.site.register(Dia)


@admin.register(Localidad)
class LocalidadAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('municipio__provincia')
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "municipio":
            provincia_id = request.GET.get("provincia")
            if provincia_id:
                kwargs["queryset"] = Municipio.objects.filter(provincia_id=provincia_id).select_related('provincia')
            else:
                kwargs["queryset"] = Municipio.objects.select_related('provincia')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
