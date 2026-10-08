"""ABM de Roles del backoffice (Group + RolMeta + capacidades).

Acceso restringido a la capacidad ``rol.administrar``. Reemplaza a ``GroupListView``.
"""

from django.contrib import messages
from django.contrib.auth.models import Group
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import TemplateView

from core import rbac
from core.rbac import CapacidadRequeridaMixin
from users.forms.roles import RolForm
from users.selectors.roles import (
    programas_administrables_roles,
    puede_editar_rol,
    puede_gestionar_rol,
    roles_filtrados_para,
    roles_lista_para,
    roles_visibles_para,
)
from users.services.roles import RolesAdminService, RolProtegidoError


class _RolesPermMixin(CapacidadRequeridaMixin):
    # Entra el admin global (rol.administrar) y también quien administra los roles
    # de algún programa (programa.rol.administrar). El alcance lo aplica cada vista.
    capacidades_requeridas = list(rbac.CAPS_ENTRADA_ABM_ROLES)


def _fuera_de_alcance(request):
    messages.error(request, "No tiene permisos para acceder a esta sección.")
    return redirect("users:roles")


class RolListView(_RolesPermMixin, TemplateView):
    template_name = "rol/rol_list.html"
    # El listado paginaba «1 de 1» con los dos botones deshabilitados y la tabla
    # entera debajo: un pie que afirmaba algo falso (FE-17). Pagina de verdad.
    por_pagina = 25

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        get = self.request.GET

        # El pipeline (JOINs + COUNT DISTINCT) se ejecuta UNA vez: la lista plana y la
        # filtrada se derivan de ese resultado.
        lista = roles_lista_para(user, visibles=roles_visibles_para(user))
        filtrados = roles_filtrados_para(user, get, lista=lista)
        paginator = Paginator(filtrados, self.por_pagina)
        page_obj = paginator.get_page(get.get("page"))
        context["items"] = page_obj.object_list
        context["page_obj"] = page_obj
        context["paginator"] = paginator
        context["is_paginated"] = page_obj.has_other_pages()
        context["categorias_rol"] = list(rbac.CATEGORIAS_ROL) + [rbac.CATEGORIA_PROGRAMA]
        context["programas_admin"] = programas_administrables_roles(user)

        # La pantalla decide «los filtros no traen nada» con `request.GET|hay_filtros`
        # (el filtro canónico de `nodo_ui`), así que no se pasa un `hay_filtros_activos`
        # propio; `roles` (el agrupado) y `total_roles` tampoco tienen consumidor.
        context["filtro_q"] = get.get("q", "")
        context["filtro_categoria"] = get.get("categoria", "")
        context["filtro_programa"] = get.get("programa", "")
        context["filtro_estado"] = get.get("estado", "")
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
        if not puede_editar_rol(request.user, group):
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
        if not puede_editar_rol(request.user, group):
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
        if not puede_editar_rol(request.user, group):
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
        if not puede_editar_rol(request.user, group):
            return _fuera_de_alcance(request)
        try:
            activo = RolesAdminService.toggle_activo(group)
        # `SinAdministradorProgramaError` hereda de `SinAdministradorError`: las dos
        # entran acá. Sin este `except` la excepción subía como 500 (G1b-07).
        except (RolProtegidoError, rbac.SinAdministradorError) as exc:
            messages.error(request, str(exc))
            return redirect("users:roles")
        messages.success(request, "Rol activado." if activo else "Rol desactivado.")
        return redirect("users:roles")
