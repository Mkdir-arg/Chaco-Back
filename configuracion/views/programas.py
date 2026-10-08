"""
Wizard de configuración de programas sociales (US-005).
4 pasos con estado en sesión. Requiere la capacidad ``programa.configurar``.

**SEC-07 / D-07.** ``programa.configurar`` es de un módulo "de programa", así que vive
en roles acotados a un programa, pero las nueve vistas la pedían con ``@requiere``, que
evalúa **sin alcance**: el admin de roles de Becas se la tildaba en un rol de Becas y
editaba el wizard de Dispositivos. Desde este cambio:

* **crear** un programa (los cuatro pasos del alta, que todavía no tienen ``pk`` contra
  el cual evaluar nada) pide la capacidad en un rol **sin programa**
  (``requiere_sin_programa``);
* **editar** un programa concreto —y cambiarle el estado— la pide **sobre ese
  programa**, o en un rol global;
* el **listado** sigue abierto a ``CAPS_ENTRADA_PROGRAMAS`` (SEC-36) y decide fila por
  fila qué acciones dibuja.

Lo que **no** se hace es mover ``programa.configurar`` a un módulo global: con alcance
DISPOSITIVOS la evalúa ``programas.services.dispositivos.puede_configurar_dispositivos``,
y globalizarla rompería ese alcance.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from core import rbac
from core.models import Subsecretaria
from core.rbac import requiere, requiere_sin_programa
from programas.models import Programa
from programas.services.programa_cache import invalidar_programa

from ..forms.programas import (
    ProgramaPaso1Form,
    ProgramaPaso2Form,
    ProgramaPaso3Form,
    ProgramaPaso4Form,
)

_REDIRECT = "configuracion:programas"
#: Mismo tamaño que las otras listas de Configuración (FE-04/FE-17).
POR_PAGINA = 20
CAP_CONFIGURAR = "programa.configurar"


def puede_crear_programas(user):
    """¿Puede dar de alta un programa? (D-07: solo roles **sin** programa).

    El alta no tiene alcance posible —el programa todavía no existe—, así que la
    capacidad tiene que venir de un rol global. Es también lo que decide si el
    listado ofrece el botón «Nuevo programa».
    """
    return rbac.puede_sin_programa(user, CAP_CONFIGURAR)


def puede_configurar_programa(user, programa):
    """¿Puede editar **este** programa? (D-07: el suyo, o cualquiera si es global)."""
    return puede_crear_programas(user) or rbac.puede(user, CAP_CONFIGURAR, programa=programa)


# ---------------------------------------------------------------------------
# Helpers de sesión
# ---------------------------------------------------------------------------


def _clave(pk=None):
    return f"wizard_programa_{pk}" if pk else "wizard_programa_nuevo"


def _get_data(request, pk=None):
    return request.session.get(_clave(pk), {})


def _set_data(request, data, pk=None):
    request.session[_clave(pk)] = data
    request.session.modified = True


def _clear_data(request, pk=None):
    request.session.pop(_clave(pk), None)
    request.session.modified = True


# ---------------------------------------------------------------------------
# Listado de programas
# ---------------------------------------------------------------------------


@login_required
@requiere(*rbac.CAPS_ENTRADA_PROGRAMAS, redirect_to="core:inicio")
def programa_list(request):
    estado = request.GET.get("estado", "")
    subsecretaria_id = request.GET.get("subsecretaria", "")
    search = request.GET.get("q", "")

    qs = Programa.objects.select_related("subsecretaria__secretaria").order_by("orden", "nombre")

    if estado:
        qs = qs.filter(estado=estado)
    if subsecretaria_id:
        qs = qs.filter(subsecretaria_id=subsecretaria_id)
    if search:
        qs = qs.filter(Q(nombre__icontains=search) | Q(codigo__icontains=search))

    # FE-17: la pantalla ya incluía el pie de paginación (Cambio 166) pero la vista
    # devolvía la lista entera, así que el pie no se dibujaba nunca.
    pagina = Paginator(qs, POR_PAGINA).get_page(request.GET.get("page"))

    # SEC-07: el lápiz se dibuja por fila. Un admin de Dispositivos ve el catálogo
    # entero (SEC-36) pero solo puede editar el suyo, y el botón tiene que decir lo
    # mismo que contesta la vista de edición.
    puede_crear = puede_crear_programas(request.user)
    programas = list(pagina.object_list)
    for programa in programas:
        programa.puede_editar = puede_crear or rbac.puede(request.user, CAP_CONFIGURAR, programa=programa)

    return render(
        request,
        "configuracion/programa_list.html",
        {
            "programas": programas,
            "page_obj": pagina,
            "paginator": pagina.paginator,
            "is_paginated": pagina.has_other_pages(),
            "estados": Programa.Estado.choices,
            "subsecretarias": Subsecretaria.objects.filter(activo=True).order_by("nombre"),
            "estado_filtro": estado,
            "subsecretaria_filtro": subsecretaria_id,
            "search": search,
            "puede_crear": puede_crear,
            "puede_editar_alguno": any(p.puede_editar for p in programas),
        },
    )


# ---------------------------------------------------------------------------
# Wizard — creación
# ---------------------------------------------------------------------------


@login_required
@requiere_sin_programa(CAP_CONFIGURAR, redirect_to=_REDIRECT)
def programa_wizard_paso1(request):
    data = _get_data(request)
    initial = {**data.get("paso1", {})}

    form = ProgramaPaso1Form(request.POST or None, initial=initial)

    if request.method == "POST" and form.is_valid():
        data["paso1"] = {
            "nombre": form.cleaned_data["nombre"],
            "codigo": form.cleaned_data["codigo"],
            "descripcion": form.cleaned_data.get("descripcion", ""),
            "secretaria": form.cleaned_data["secretaria"].pk,
            "subsecretaria": form.cleaned_data["subsecretaria"].pk,
        }
        _set_data(request, data)
        return redirect("configuracion:programa_wizard_paso2")

    return render(
        request,
        "configuracion/programa_wizard_paso1.html",
        {
            "form": form,
            "paso_actual": 1,
            "total_pasos": 4,
        },
    )


@login_required
@requiere_sin_programa(CAP_CONFIGURAR, redirect_to=_REDIRECT)
def programa_wizard_paso2(request):
    data = _get_data(request)
    if not data.get("paso1"):
        return redirect("configuracion:programa_wizard_paso1")

    initial = data.get("paso2", {})
    form = ProgramaPaso2Form(request.POST or None, initial=initial)

    if request.method == "POST" and form.is_valid():
        data["paso2"] = {"naturaleza": form.cleaned_data["naturaleza"]}
        _set_data(request, data)
        return redirect("configuracion:programa_wizard_paso3")

    return render(
        request,
        "configuracion/programa_wizard_paso2.html",
        {
            "form": form,
            "paso_actual": 2,
            "total_pasos": 4,
        },
    )


@login_required
@requiere_sin_programa(CAP_CONFIGURAR, redirect_to=_REDIRECT)
def programa_wizard_paso3(request):
    data = _get_data(request)
    if not data.get("paso2"):
        return redirect("configuracion:programa_wizard_paso2")

    initial = data.get("paso3", {})
    form = ProgramaPaso3Form(request.POST or None, initial=initial)

    if request.method == "POST" and form.is_valid():
        data["paso3"] = {
            "cupo_maximo": form.cleaned_data.get("cupo_maximo"),
            "tiene_lista_espera": form.cleaned_data.get("tiene_lista_espera", False),
        }
        _set_data(request, data)
        return redirect("configuracion:programa_wizard_paso4")

    return render(
        request,
        "configuracion/programa_wizard_paso3.html",
        {
            "form": form,
            "paso_actual": 3,
            "total_pasos": 4,
        },
    )


@login_required
@requiere_sin_programa(CAP_CONFIGURAR, redirect_to=_REDIRECT)
def programa_wizard_paso4(request):
    data = _get_data(request)
    if not data.get("paso3"):
        return redirect("configuracion:programa_wizard_paso3")

    initial = data.get("paso4", {"icono": "folder", "color": "#6366f1", "orden": 0})
    form = ProgramaPaso4Form(request.POST or None, initial=initial)

    if request.method == "POST" and form.is_valid():
        data["paso4"] = {
            "icono": form.cleaned_data["icono"],
            "color": form.cleaned_data["color"],
            "orden": form.cleaned_data["orden"],
        }
        _set_data(request, data)

        p1 = data["paso1"]
        p2 = data["paso2"]
        p3 = data["paso3"]
        p4 = data["paso4"]

        programa = Programa.objects.create(
            nombre=p1["nombre"],
            codigo=p1["codigo"],
            descripcion=p1.get("descripcion", ""),
            subsecretaria_id=p1["subsecretaria"],
            naturaleza=p2["naturaleza"],
            estado=Programa.Estado.BORRADOR,
            cupo_maximo=p3.get("cupo_maximo"),
            tiene_lista_espera=p3.get("tiene_lista_espera", False),
            icono=p4["icono"],
            color=p4["color"],
            orden=p4["orden"],
        )
        _clear_data(request)
        messages.success(request, f'Programa "{programa.nombre}" creado en estado Borrador.')
        return redirect("configuracion:programas")

    # Resumen para mostrar en el paso 4
    p1 = data.get("paso1", {})
    p2 = data.get("paso2", {})
    p3 = data.get("paso3", {})
    subsecretaria = Subsecretaria.objects.select_related("secretaria").filter(pk=p1.get("subsecretaria")).first()

    return render(
        request,
        "configuracion/programa_wizard_paso4.html",
        {
            "form": form,
            "paso_actual": 4,
            "total_pasos": 4,
            "resumen": {
                "nombre": p1.get("nombre"),
                "codigo": p1.get("codigo"),
                "descripcion": p1.get("descripcion"),
                "subsecretaria": subsecretaria,
                "naturaleza": dict(Programa.Naturaleza.choices).get(p2.get("naturaleza"), ""),
                "cupo_maximo": p3.get("cupo_maximo"),
                "tiene_lista_espera": p3.get("tiene_lista_espera", False),
            },
        },
    )


# ---------------------------------------------------------------------------
# Wizard — edición
# ---------------------------------------------------------------------------


@login_required
def programa_editar_paso1(request, pk):
    programa = get_object_or_404(Programa, pk=pk)
    # SEC-07 / D-07: con el programa resuelto, la capacidad se evalúa **sobre él**.
    if not puede_configurar_programa(request.user, programa):
        return rbac.respuesta_sin_permiso(request, _REDIRECT)
    if programa.estado == Programa.Estado.INACTIVO:
        messages.error(request, "Los programas inactivos no pueden editarse.")
        return redirect("configuracion:programas")

    data = _get_data(request, pk)
    initial_default = {
        "nombre": programa.nombre,
        "codigo": programa.codigo,
        "descripcion": programa.descripcion,
        "secretaria": programa.subsecretaria.secretaria_id if programa.subsecretaria else None,
        "subsecretaria": programa.subsecretaria_id,
    }
    initial = {**initial_default, **data.get("paso1", {}), "programa_id": pk}

    form = ProgramaPaso1Form(request.POST or None, initial=initial)

    if request.method == "POST" and form.is_valid():
        data["paso1"] = {
            "nombre": form.cleaned_data["nombre"],
            "codigo": form.cleaned_data["codigo"],
            "descripcion": form.cleaned_data.get("descripcion", ""),
            "secretaria": form.cleaned_data["secretaria"].pk,
            "subsecretaria": form.cleaned_data["subsecretaria"].pk,
        }
        _set_data(request, data, pk)
        return redirect("configuracion:programa_editar_paso2", pk=pk)

    return render(
        request,
        "configuracion/programa_wizard_paso1.html",
        {
            "form": form,
            "programa": programa,
            "paso_actual": 1,
            "total_pasos": 4,
            "es_edicion": True,
        },
    )


@login_required
def programa_editar_paso2(request, pk):
    programa = get_object_or_404(Programa, pk=pk)
    # SEC-07 / D-07: con el programa resuelto, la capacidad se evalúa **sobre él**.
    if not puede_configurar_programa(request.user, programa):
        return rbac.respuesta_sin_permiso(request, _REDIRECT)
    data = _get_data(request, pk)
    if not data.get("paso1"):
        return redirect("configuracion:programa_editar_paso1", pk=pk)

    initial = data.get("paso2", {"naturaleza": programa.naturaleza})
    form = ProgramaPaso2Form(request.POST or None, initial=initial)

    if request.method == "POST" and form.is_valid():
        data["paso2"] = {"naturaleza": form.cleaned_data["naturaleza"]}
        _set_data(request, data, pk)
        return redirect("configuracion:programa_editar_paso3", pk=pk)

    return render(
        request,
        "configuracion/programa_wizard_paso2.html",
        {
            "form": form,
            "programa": programa,
            "paso_actual": 2,
            "total_pasos": 4,
            "es_edicion": True,
        },
    )


@login_required
def programa_editar_paso3(request, pk):
    programa = get_object_or_404(Programa, pk=pk)
    # SEC-07 / D-07: con el programa resuelto, la capacidad se evalúa **sobre él**.
    if not puede_configurar_programa(request.user, programa):
        return rbac.respuesta_sin_permiso(request, _REDIRECT)
    data = _get_data(request, pk)
    if not data.get("paso2"):
        return redirect("configuracion:programa_editar_paso2", pk=pk)

    initial = data.get(
        "paso3",
        {
            "cupo_maximo": programa.cupo_maximo,
            "tiene_lista_espera": programa.tiene_lista_espera,
        },
    )
    form = ProgramaPaso3Form(request.POST or None, initial=initial)

    if request.method == "POST" and form.is_valid():
        data["paso3"] = {
            "cupo_maximo": form.cleaned_data.get("cupo_maximo"),
            "tiene_lista_espera": form.cleaned_data.get("tiene_lista_espera", False),
        }
        _set_data(request, data, pk)
        return redirect("configuracion:programa_editar_paso4", pk=pk)

    return render(
        request,
        "configuracion/programa_wizard_paso3.html",
        {
            "form": form,
            "programa": programa,
            "paso_actual": 3,
            "total_pasos": 4,
            "es_edicion": True,
        },
    )


@login_required
def programa_editar_paso4(request, pk):
    programa = get_object_or_404(Programa, pk=pk)
    # SEC-07 / D-07: con el programa resuelto, la capacidad se evalúa **sobre él**.
    if not puede_configurar_programa(request.user, programa):
        return rbac.respuesta_sin_permiso(request, _REDIRECT)
    data = _get_data(request, pk)
    if not data.get("paso3"):
        return redirect("configuracion:programa_editar_paso3", pk=pk)

    initial = data.get(
        "paso4",
        {
            "icono": programa.icono,
            "color": programa.color,
            "orden": programa.orden,
        },
    )
    form = ProgramaPaso4Form(request.POST or None, initial=initial)

    if request.method == "POST" and form.is_valid():
        p1 = data["paso1"]
        p2 = data["paso2"]
        p3 = data["paso3"]
        p4 = form.cleaned_data

        # RED-80: el alcance del RBAC resuelve el ``Programa`` desde una clave cacheada
        # 300 s, y el paso 1 deja **cambiar el código**. Sin invalidar las dos —la vieja
        # y la nueva—, durante cinco minutos los pods evalúan contra la fila anterior:
        # en Dispositivos eso es «nadie entra», y en Becas un 403 (RED-56). Es la única
        # pantalla que escribe un ``Programa``, así que es la que tiene que borrarlas.
        codigo_anterior = programa.codigo

        programa.nombre = p1["nombre"]
        programa.codigo = p1["codigo"]
        programa.descripcion = p1.get("descripcion", "")
        programa.subsecretaria_id = p1["subsecretaria"]
        programa.naturaleza = p2["naturaleza"]
        programa.cupo_maximo = p3.get("cupo_maximo")
        programa.tiene_lista_espera = p3.get("tiene_lista_espera", False)
        programa.icono = p4["icono"]
        programa.color = p4["color"]
        programa.orden = p4["orden"]
        programa.save()
        invalidar_programa(codigo_anterior)
        if programa.codigo != codigo_anterior:
            invalidar_programa(programa.codigo)

        _clear_data(request, pk)
        messages.success(request, f'Programa "{programa.nombre}" actualizado.')
        return redirect("configuracion:programas")

    p1 = data.get("paso1", {})
    p2 = data.get("paso2", {})
    p3 = data.get("paso3", {})
    subsecretaria = Subsecretaria.objects.select_related("secretaria").filter(pk=p1.get("subsecretaria")).first()

    return render(
        request,
        "configuracion/programa_wizard_paso4.html",
        {
            "form": form,
            "programa": programa,
            "paso_actual": 4,
            "total_pasos": 4,
            "es_edicion": True,
            "resumen": {
                "nombre": p1.get("nombre"),
                "codigo": p1.get("codigo"),
                "descripcion": p1.get("descripcion"),
                "subsecretaria": subsecretaria,
                "naturaleza": dict(Programa.Naturaleza.choices).get(p2.get("naturaleza"), ""),
                "cupo_maximo": p3.get("cupo_maximo"),
                "tiene_lista_espera": p3.get("tiene_lista_espera", False),
            },
        },
    )


# ---------------------------------------------------------------------------
# Cambiar estado del programa
# ---------------------------------------------------------------------------


@login_required
def programa_cambiar_estado(request, pk):
    if request.method != "POST":
        return redirect("configuracion:programas")

    programa = get_object_or_404(Programa, pk=pk)
    # SEC-07 / D-07: con el programa resuelto, la capacidad se evalúa **sobre él**.
    if not puede_configurar_programa(request.user, programa):
        return rbac.respuesta_sin_permiso(request, _REDIRECT)
    nuevo_estado = request.POST.get("estado")

    estados_validos = [e[0] for e in Programa.Estado.choices]
    if nuevo_estado not in estados_validos:
        messages.error(request, "Estado no válido.")
        return redirect("configuracion:programas")

    if nuevo_estado == Programa.Estado.ACTIVO:
        if not programa.naturaleza:
            messages.error(
                request,
                "El programa no puede activarse sin tener la naturaleza configurada. Complete el wizard primero.",
            )
            return redirect("configuracion:programas")
    programa.estado = nuevo_estado
    programa.save(update_fields=["estado"])
    # RED-80: la entrada cacheada guarda el ``Programa`` entero, estado incluido.
    invalidar_programa(programa.codigo)
    messages.success(request, f"Estado del programa actualizado a {programa.get_estado_display()}.")
    return redirect("configuracion:programas")
