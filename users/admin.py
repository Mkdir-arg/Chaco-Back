from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group, User
from django.db import transaction

from core import rbac


class CandadoDeAdministracionMixin:
    """G1b-09 (ronda 3) · el `/admin/` toma el mismo candado que el ABM.

    Por acá se tildan las capacidades de un rol (`auth_group_permissions`), se borra un
    rol y se desactivan cuentas: lo mismo que `core.rbac.tomar_candado_de_administracion`
    serializa en el backoffice. El `/admin/` es la escotilla del superusuario y no corre
    `asegurar_admin_restante` —no se le pone un check al único camino que queda para
    arreglar un sistema sin administradores—, pero sí tiene que entrar en la misma fila:
    sin el candado cierra contra el resto el ciclo de locks de `CandadoSinDeadlockTests`
    (el `FOR UPDATE` sobre el ancla de un lado, el lock de FK sobre `auth_permission` que
    pide el m2m del otro) y el operador se come un `ERROR 1213` sin que nadie lo atrape.

    `save_model` corre **antes** de `save_related`, que es donde el `ModelAdmin` escribe
    los m2m, y las dos van dentro de la transacción que abre el changeform. La acción
    masiva del listado no abre ninguna, así que `delete_queryset` pone la suya: sin
    `atomic` el `select_for_update` sería un `TransactionManagementError` contra MySQL.
    """

    def save_model(self, request, obj, form, change):
        rbac.tomar_candado_de_administracion()
        super().save_model(request, obj, form, change)

    def delete_model(self, request, obj):
        rbac.tomar_candado_de_administracion()
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        with transaction.atomic():
            rbac.tomar_candado_de_administracion()
            super().delete_queryset(request, queryset)


# Unregister the default User admin
admin.site.unregister(User)


@admin.register(User)
class OptimizedUserAdmin(CandadoDeAdministracionMixin, BaseUserAdmin):
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
class OptimizedGroupAdmin(CandadoDeAdministracionMixin, admin.ModelAdmin):
    list_display = ["name"]
    search_fields = ["name"]
    filter_horizontal = ["permissions"]

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("permissions", "user_set")
