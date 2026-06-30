from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group, User

# Unregister the default User admin
admin.site.unregister(User)


@admin.register(User)
class OptimizedUserAdmin(BaseUserAdmin):
    """Optimized User admin with select_related and prefetch_related"""

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
