from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group, User

# Unregister the default User admin
admin.site.unregister(User)


@admin.register(User)
class OptimizedUserAdmin(BaseUserAdmin):
    """Optimized User admin with select_related and prefetch_related.

    G1c-10: el `/admin/` está montado en todos los entornos y este era un
    `UserAdmin` estándar, así que cualquier cuenta con `is_staff` y
    `auth.change_user` podía **tildarse `is_superuser`** o sumarse un rol desde
    acá, salteando entero el ABM de Usuarios —que sí evalúa alcance y
    autoprotección (SEC-03)—. Hoy no existe esa cuenta: ningún flujo del sistema
    pone `is_staff`, y por eso el hallazgo bajó a BAJA. Lo que cambia es que deje
    de depender de eso.
    """

    #: Lo que no se toca desde el `/admin/` si quien entra no es superusuario:
    #: el superusuario y los roles son escalada de privilegio, y `is_staff` es la
    #: llave de esta misma pantalla.
    CAMPOS_DE_PRIVILEGIO = ("is_superuser", "is_staff", "groups", "user_permissions")

    def get_readonly_fields(self, request, obj=None):
        solo_lectura = tuple(super().get_readonly_fields(request, obj))
        if request.user.is_superuser:
            return solo_lectura
        return tuple(dict.fromkeys(solo_lectura + self.CAMPOS_DE_PRIVILEGIO))

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("groups", "user_permissions")

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "groups":
            kwargs["queryset"] = Group.objects.all().prefetch_related("permissions")
        return super().formfield_for_manytomany(db_field, request, **kwargs)


# Optimize Group admin as well
admin.site.unregister(Group)


@admin.register(Group)
class OptimizedGroupAdmin(admin.ModelAdmin):
    list_display = ["name"]
    search_fields = ["name"]
    filter_horizontal = ["permissions"]

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("permissions", "user_set")
