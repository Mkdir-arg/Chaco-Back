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
from users.selectors.roles import (
    programas_administrables,
    puede_gestionar_rol,
    roles_filtrados_para,
    roles_lista_para,
    roles_visibles_para,
)
from users.services.roles import RolesAdminService, RolProtegidoError


class _RolesPermMixin(CapacidadRequeridaMixin):
    # Entra el admin global (rol.administrar) y también el admin de programa
    # (programa.configurar en algún programa). El alcance fino lo aplica cada vista.
    capacidades_requeridas = ["rol.administrar", "programa.configurar"]


def _fuera_de_alcance(request):
    messages.error(request, "No tiene permisos para acceder a esta sección.")
    return redirect("users:roles")


class RolListView(_RolesPermMixin, TemplateView):
    template_name = "rol/rol_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        get = self.request.GET

        # El pipeline (JOINs + COUNT DISTINCT) se ejecuta UNA vez y las tres
        # formas (agrupados / filtrados / total) se derivan de ese resultado.
        roles = roles_visibles_para(user)
        lista = roles_lista_para(user, visibles=roles)
        context["roles"] = roles
        context["items"] = roles_filtrados_para(user, get, lista=lista)
        context["total_roles"] = len(lista)
        context["categorias_rol"] = list(rbac.CATEGORIAS_ROL) + [rbac.CATEGORIA_PROGRAMA]
        context["programas_admin"] = programas_administrables(user)

        context["filtro_q"] = get.get("q", "")
        context["filtro_categoria"] = get.get("categoria", "")
        context["filtro_programa"] = get.get("programa", "")
        context["filtro_estado"] = get.get("estado", "")
        context["hay_filtros_activos"] = bool(
            context["filtro_q"] or context["filtro_categoria"] or context["filtro_programa"] or context["filtro_estado"]
        )
        return context


class RolDetailView(_RolesPermMixin, View):
    def get(self, request, pk):
        group = get_object_or_404(Group.objects.select_related("meta", "meta__programa"), pk=pk)
        if not puede_gestionar_rol(request.user, group):
            return _fuera_de_alcance(request)
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
            request,
            "rol/rol_form.html",
            {"form": RolForm(operador=request.user), "es_edicion": False},
        )

    def post(self, request):
        form = RolForm(request.POST, operador=request.user)
        if form.is_valid():
            RolesAdminService.crear(form)
            messages.success(request, "Rol creado correctamente.")
            return redirect("users:roles")
        return render(request, "rol/rol_form.html", {"form": form, "es_edicion": False})


class RolUpdateView(_RolesPermMixin, View):
    def _get_group(self, pk):
        return get_object_or_404(Group.objects.select_related("meta", "meta__programa"), pk=pk)

    def get(self, request, pk):
        group = self._get_group(pk)
        if not puede_gestionar_rol(request.user, group):
            return _fuera_de_alcance(request)
        meta = getattr(group, "meta", None)
        if meta and meta.protegido:
            messages.error(request, "El rol está protegido y no puede editarse.")
            return redirect("users:roles")
        return render(
            request,
            "rol/rol_form.html",
            {
                "form": RolForm(instance=group, operador=request.user),
                "es_edicion": True,
                "group": group,
            },
        )

    def post(self, request, pk):
        group = self._get_group(pk)
        if not puede_gestionar_rol(request.user, group):
            return _fuera_de_alcance(request)
        form = RolForm(request.POST, instance=group, operador=request.user)
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
        group = get_object_or_404(Group.objects.select_related("meta", "meta__programa"), pk=pk)
        if not puede_gestionar_rol(request.user, group):
            return _fuera_de_alcance(request)
        try:
            RolesAdminService.eliminar(group)
        except (RolProtegidoError, rbac.SinAdministradorError) as exc:
            messages.error(request, str(exc))
            return redirect("users:roles")
        messages.success(request, "Rol eliminado.")
        return redirect("users:roles")


class RolToggleActivoView(_RolesPermMixin, View):
    def post(self, request, pk):
        group = get_object_or_404(Group.objects.select_related("meta", "meta__programa"), pk=pk)
        if not puede_gestionar_rol(request.user, group):
            return _fuera_de_alcance(request)
        try:
            activo = RolesAdminService.toggle_activo(group)
        except RolProtegidoError as exc:
            messages.error(request, str(exc))
            return redirect("users:roles")
        messages.success(request, "Rol activado." if activo else "Rol desactivado.")
        return redirect("users:roles")
