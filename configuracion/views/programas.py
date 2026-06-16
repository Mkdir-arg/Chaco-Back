"""
Wizard de configuración de programas sociales (US-005).
4 pasos con estado en sesión. Requiere grupo programaConfigurar.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from core.rbac import puede, requiere
from core.models import Subsecretaria
from legajos.models_programas import Programa

from ..forms.programas import (
    ProgramaPaso1Form,
    ProgramaPaso2Form,
    ProgramaPaso3Form,
    ProgramaPaso4Form,
)

_REDIRECT = 'configuracion:programas'

# ---------------------------------------------------------------------------
# Helpers de sesión
# ---------------------------------------------------------------------------

def _clave(pk=None):
    return f'wizard_programa_{pk}' if pk else 'wizard_programa_nuevo'


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
def programa_list(request):
    estado = request.GET.get('estado', '')
    subsecretaria_id = request.GET.get('subsecretaria', '')
    search = request.GET.get('q', '')

    qs = Programa.objects.select_related('subsecretaria__secretaria').order_by('orden', 'nombre')

    if estado:
        qs = qs.filter(estado=estado)
    if subsecretaria_id:
        qs = qs.filter(subsecretaria_id=subsecretaria_id)
    if search:
        qs = qs.filter(Q(nombre__icontains=search) | Q(codigo__icontains=search))

    puede_editar = puede(request.user, "programa.configurar")

    return render(request, 'configuracion/programa_list.html', {
        'programas': qs,
        'estados': Programa.Estado.choices,
        'subsecretarias': Subsecretaria.objects.filter(activo=True).order_by('nombre'),
        'estado_filtro': estado,
        'subsecretaria_filtro': subsecretaria_id,
        'search': search,
        'puede_editar': puede_editar,
    })


# ---------------------------------------------------------------------------
# Wizard — creación
# ---------------------------------------------------------------------------

@login_required
@requiere("programa.configurar", redirect_to=_REDIRECT)
def programa_wizard_paso1(request):
    data = _get_data(request)
    initial = {**data.get('paso1', {})}

    form = ProgramaPaso1Form(request.POST or None, initial=initial)

    if request.method == 'POST' and form.is_valid():
        data['paso1'] = {
            'nombre': form.cleaned_data['nombre'],
            'codigo': form.cleaned_data['codigo'],
            'descripcion': form.cleaned_data.get('descripcion', ''),
            'secretaria': form.cleaned_data['secretaria'].pk,
            'subsecretaria': form.cleaned_data['subsecretaria'].pk,
        }
        _set_data(request, data)
        return redirect('configuracion:programa_wizard_paso2')

    return render(request, 'configuracion/programa_wizard_paso1.html', {
        'form': form,
        'paso_actual': 1,
        'total_pasos': 4,
    })


@login_required
@requiere("programa.configurar", redirect_to=_REDIRECT)
def programa_wizard_paso2(request):
    data = _get_data(request)
    if not data.get('paso1'):
        return redirect('configuracion:programa_wizard_paso1')

    initial = data.get('paso2', {})
    form = ProgramaPaso2Form(request.POST or None, initial=initial)

    if request.method == 'POST' and form.is_valid():
        data['paso2'] = {'naturaleza': form.cleaned_data['naturaleza']}
        _set_data(request, data)
        return redirect('configuracion:programa_wizard_paso3')

    return render(request, 'configuracion/programa_wizard_paso2.html', {
        'form': form,
        'paso_actual': 2,
        'total_pasos': 4,
    })


@login_required
@requiere("programa.configurar", redirect_to=_REDIRECT)
def programa_wizard_paso3(request):
    data = _get_data(request)
    if not data.get('paso2'):
        return redirect('configuracion:programa_wizard_paso2')

    initial = data.get('paso3', {})
    form = ProgramaPaso3Form(request.POST or None, initial=initial)

    if request.method == 'POST' and form.is_valid():
        data['paso3'] = {
            'cupo_maximo': form.cleaned_data.get('cupo_maximo'),
            'tiene_lista_espera': form.cleaned_data.get('tiene_lista_espera', False),
        }
        _set_data(request, data)
        return redirect('configuracion:programa_wizard_paso4')

    return render(request, 'configuracion/programa_wizard_paso3.html', {
        'form': form,
        'paso_actual': 3,
        'total_pasos': 4,
    })


@login_required
@requiere("programa.configurar", redirect_to=_REDIRECT)
def programa_wizard_paso4(request):
    data = _get_data(request)
    if not data.get('paso3'):
        return redirect('configuracion:programa_wizard_paso3')

    initial = data.get('paso4', {'icono': 'folder', 'color': '#6366f1', 'orden': 0})
    form = ProgramaPaso4Form(request.POST or None, initial=initial)

    if request.method == 'POST' and form.is_valid():
        data['paso4'] = {
            'icono': form.cleaned_data['icono'],
            'color': form.cleaned_data['color'],
            'orden': form.cleaned_data['orden'],
        }
        _set_data(request, data)

        p1 = data['paso1']
        p2 = data['paso2']
        p3 = data['paso3']
        p4 = data['paso4']

        programa = Programa.objects.create(
            nombre=p1['nombre'],
            codigo=p1['codigo'],
            descripcion=p1.get('descripcion', ''),
            subsecretaria_id=p1['subsecretaria'],
            naturaleza=p2['naturaleza'],
            estado=Programa.Estado.BORRADOR,
            cupo_maximo=p3.get('cupo_maximo'),
            tiene_lista_espera=p3.get('tiene_lista_espera', False),
            icono=p4['icono'],
            color=p4['color'],
            orden=p4['orden'],
        )
        _clear_data(request)
        messages.success(request, f'Programa "{programa.nombre}" creado en estado Borrador.')
        return redirect('configuracion:programas')

    # Resumen para mostrar en el paso 4
    p1 = data.get('paso1', {})
    p2 = data.get('paso2', {})
    p3 = data.get('paso3', {})
    subsecretaria = Subsecretaria.objects.select_related('secretaria').filter(
        pk=p1.get('subsecretaria')
    ).first()

    return render(request, 'configuracion/programa_wizard_paso4.html', {
        'form': form,
        'paso_actual': 4,
        'total_pasos': 4,
        'resumen': {
            'nombre': p1.get('nombre'),
            'codigo': p1.get('codigo'),
            'descripcion': p1.get('descripcion'),
            'subsecretaria': subsecretaria,
            'naturaleza': dict(Programa.Naturaleza.choices).get(p2.get('naturaleza'), ''),
            'cupo_maximo': p3.get('cupo_maximo'),
            'tiene_lista_espera': p3.get('tiene_lista_espera', False),
        },
    })


# ---------------------------------------------------------------------------
# Wizard — edición
# ---------------------------------------------------------------------------

@login_required
@requiere("programa.configurar", redirect_to=_REDIRECT)
def programa_editar_paso1(request, pk):
    programa = get_object_or_404(Programa, pk=pk)
    if programa.estado == Programa.Estado.INACTIVO:
        messages.error(request, 'Los programas inactivos no pueden editarse.')
        return redirect('configuracion:programas')

    data = _get_data(request, pk)
    initial_default = {
        'nombre': programa.nombre,
        'codigo': programa.codigo,
        'descripcion': programa.descripcion,
        'secretaria': programa.subsecretaria.secretaria_id if programa.subsecretaria else None,
        'subsecretaria': programa.subsecretaria_id,
    }
    initial = {**initial_default, **data.get('paso1', {}), 'programa_id': pk}

    form = ProgramaPaso1Form(request.POST or None, initial=initial)

    if request.method == 'POST' and form.is_valid():
        data['paso1'] = {
            'nombre': form.cleaned_data['nombre'],
            'codigo': form.cleaned_data['codigo'],
            'descripcion': form.cleaned_data.get('descripcion', ''),
            'secretaria': form.cleaned_data['secretaria'].pk,
            'subsecretaria': form.cleaned_data['subsecretaria'].pk,
        }
        _set_data(request, data, pk)
        return redirect('configuracion:programa_editar_paso2', pk=pk)

    return render(request, 'configuracion/programa_wizard_paso1.html', {
        'form': form,
        'programa': programa,
        'paso_actual': 1,
        'total_pasos': 4,
        'es_edicion': True,
    })


@login_required
@requiere("programa.configurar", redirect_to=_REDIRECT)
def programa_editar_paso2(request, pk):
    programa = get_object_or_404(Programa, pk=pk)
    data = _get_data(request, pk)
    if not data.get('paso1'):
        return redirect('configuracion:programa_editar_paso1', pk=pk)

    initial = data.get('paso2', {'naturaleza': programa.naturaleza})
    form = ProgramaPaso2Form(request.POST or None, initial=initial)

    if request.method == 'POST' and form.is_valid():
        data['paso2'] = {'naturaleza': form.cleaned_data['naturaleza']}
        _set_data(request, data, pk)
        return redirect('configuracion:programa_editar_paso3', pk=pk)

    return render(request, 'configuracion/programa_wizard_paso2.html', {
        'form': form,
        'programa': programa,
        'paso_actual': 2,
        'total_pasos': 4,
        'es_edicion': True,
    })


@login_required
@requiere("programa.configurar", redirect_to=_REDIRECT)
def programa_editar_paso3(request, pk):
    programa = get_object_or_404(Programa, pk=pk)
    data = _get_data(request, pk)
    if not data.get('paso2'):
        return redirect('configuracion:programa_editar_paso2', pk=pk)

    initial = data.get('paso3', {
        'cupo_maximo': programa.cupo_maximo,
        'tiene_lista_espera': programa.tiene_lista_espera,
    })
    form = ProgramaPaso3Form(request.POST or None, initial=initial)

    if request.method == 'POST' and form.is_valid():
        data['paso3'] = {
            'cupo_maximo': form.cleaned_data.get('cupo_maximo'),
            'tiene_lista_espera': form.cleaned_data.get('tiene_lista_espera', False),
        }
        _set_data(request, data, pk)
        return redirect('configuracion:programa_editar_paso4', pk=pk)

    return render(request, 'configuracion/programa_wizard_paso3.html', {
        'form': form,
        'programa': programa,
        'paso_actual': 3,
        'total_pasos': 4,
        'es_edicion': True,
    })


@login_required
@requiere("programa.configurar", redirect_to=_REDIRECT)
def programa_editar_paso4(request, pk):
    programa = get_object_or_404(Programa, pk=pk)
    data = _get_data(request, pk)
    if not data.get('paso3'):
        return redirect('configuracion:programa_editar_paso3', pk=pk)

    initial = data.get('paso4', {
        'icono': programa.icono,
        'color': programa.color,
        'orden': programa.orden,
    })
    form = ProgramaPaso4Form(request.POST or None, initial=initial)

    if request.method == 'POST' and form.is_valid():
        p1 = data['paso1']
        p2 = data['paso2']
        p3 = data['paso3']
        p4 = form.cleaned_data

        programa.nombre = p1['nombre']
        programa.codigo = p1['codigo']
        programa.descripcion = p1.get('descripcion', '')
        programa.subsecretaria_id = p1['subsecretaria']
        programa.naturaleza = p2['naturaleza']
        programa.cupo_maximo = p3.get('cupo_maximo')
        programa.tiene_lista_espera = p3.get('tiene_lista_espera', False)
        programa.icono = p4['icono']
        programa.color = p4['color']
        programa.orden = p4['orden']
        programa.save()

        _clear_data(request, pk)
        messages.success(request, f'Programa "{programa.nombre}" actualizado.')
        return redirect('configuracion:programas')

    p1 = data.get('paso1', {})
    p2 = data.get('paso2', {})
    p3 = data.get('paso3', {})
    subsecretaria = Subsecretaria.objects.select_related('secretaria').filter(
        pk=p1.get('subsecretaria')
    ).first()

    return render(request, 'configuracion/programa_wizard_paso4.html', {
        'form': form,
        'programa': programa,
        'paso_actual': 4,
        'total_pasos': 4,
        'es_edicion': True,
        'resumen': {
            'nombre': p1.get('nombre'),
            'codigo': p1.get('codigo'),
            'descripcion': p1.get('descripcion'),
            'subsecretaria': subsecretaria,
            'naturaleza': dict(Programa.Naturaleza.choices).get(p2.get('naturaleza'), ''),
            'cupo_maximo': p3.get('cupo_maximo'),
            'tiene_lista_espera': p3.get('tiene_lista_espera', False),
        },
    })


# ---------------------------------------------------------------------------
# Cambiar estado del programa
# ---------------------------------------------------------------------------

@login_required
@requiere("programa.configurar", redirect_to=_REDIRECT)
def programa_cambiar_estado(request, pk):
    if request.method != 'POST':
        return redirect('configuracion:programas')

    programa = get_object_or_404(Programa, pk=pk)
    nuevo_estado = request.POST.get('estado')

    estados_validos = [e[0] for e in Programa.Estado.choices]
    if nuevo_estado not in estados_validos:
        messages.error(request, 'Estado no válido.')
        return redirect('configuracion:programas')

    if nuevo_estado == Programa.Estado.ACTIVO:
        if not programa.naturaleza:
            messages.error(
                request,
                'El programa no puede activarse sin tener la naturaleza configurada. '
                'Complete el wizard primero.'
            )
            return redirect('configuracion:programas')
    programa.estado = nuevo_estado
    programa.save(update_fields=['estado'])
    messages.success(request, f'Estado del programa actualizado a {programa.get_estado_display()}.')
    return redirect('configuracion:programas')
