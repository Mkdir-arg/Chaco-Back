"""ABM de Roles del backoffice (Group + RolMeta + capacidades).

Acceso restringido a la capacidad ``rol.administrar``. Reemplaza a ``GroupListView``.
"""
from django.contrib import messages
from django.contrib.auth.models import Group
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import TemplateView

from core import rbac
from core.rbac import CapacidadRequeridaMixin
from users.forms.roles import RolForm
from users.selectors.roles import roles_por_categoria
from users.services.roles import RolesAdminService, RolProtegidoError


class _RolesPermMixin(CapacidadRequeridaMixin):
    capacidades_requeridas = "rol.administrar"


class RolListView(_RolesPermMixin, TemplateView):
    template_name = "rol/rol_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["roles_por_categoria"] = roles_por_categoria()
        return context


class RolDetailView(_RolesPermMixin, View):
    def get(self, request, pk):
        group = get_object_or_404(Group.objects.select_related("meta"), pk=pk)
        return render(
            request,
            "rol/rol_detail.html",
            {
                "group": group,
                "meta": getattr(group, "meta", None),
                "arbol": rbac.arbol_capacidades(rbac.capacidades_de_grupo(group)),
                "num_usuarios": group.user_set.count(),
            },
        )


class RolCreateView(_RolesPermMixin, View):
    def get(self, request):
        return render(
            request, "rol/rol_form.html", {"form": RolForm(), "es_edicion": False}
        )

    def post(self, request):
        form = RolForm(request.POST)
        if form.is_valid():
            RolesAdminService.crear(form)
            messages.success(request, "Rol creado correctamente.")
            return redirect("users:roles")
        return render(
            request, "rol/rol_form.html", {"form": form, "es_edicion": False}
        )


class RolUpdateView(_RolesPermMixin, View):
    def _get_group(self, pk):
        return get_object_or_404(Group.objects.select_related("meta"), pk=pk)

    def get(self, request, pk):
        group = self._get_group(pk)
        meta = getattr(group, "meta", None)
        if meta and meta.protegido:
            messages.error(request, "El rol está protegido y no puede editarse.")
            return redirect("users:roles")
        return render(
            request,
            "rol/rol_form.html",
            {"form": RolForm(instance=group), "es_edicion": True, "group": group},
        )

    def post(self, request, pk):
        group = self._get_group(pk)
        form = RolForm(request.POST, instance=group)
        if form.is_valid():
            try:
                RolesAdminService.actualizar(form, group)
            except (RolProtegidoError, rbac.SinAdministradorError) as exc:
                messages.error(request, str(exc))
                return redirect("users:roles")
            messages.success(request, "Rol actualizado correctamente.")
            return redirect("users:roles")
        return render(
            request,
            "rol/rol_form.html",
            {"form": form, "es_edicion": True, "group": group},
        )


class RolDeleteView(_RolesPermMixin, View):
    def post(self, request, pk):
        group = get_object_or_404(Group, pk=pk)
        try:
            RolesAdminService.eliminar(group)
        except (RolProtegidoError, rbac.SinAdministradorError) as exc:
            messages.error(request, str(exc))
            return redirect("users:roles")
        messages.success(request, "Rol eliminado.")
        return redirect("users:roles")


class RolToggleActivoView(_RolesPermMixin, View):
    def post(self, request, pk):
        group = get_object_or_404(Group, pk=pk)
        try:
            activo = RolesAdminService.toggle_activo(group)
        except RolProtegidoError as exc:
            messages.error(request, str(exc))
            return redirect("users:roles")
        messages.success(request, "Rol activado." if activo else "Rol desactivado.")
        return redirect("users:roles")
