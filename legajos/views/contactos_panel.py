from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from core.rbac import requiere
from ..selectors import get_legajo_contactos_context


@login_required
@requiere("ciudadano.ver")
def red_contactos_simple(request, legajo_id):
    """Vista simple para red de contactos"""
    return render(
        request,
        'legajos/red_contactos_simple.html',
        get_legajo_contactos_context(legajo_id),
    )


@login_required
@requiere("dashboard.ver")
def dashboard_contactos_simple(request):
    """Dashboard simple de contactos"""
    return render(
        request,
        'legajos/dashboard_contactos_simple.html',
        {'titulo': 'Dashboard de Contactos'},
    )


@login_required
def historial_contactos_simple(request, legajo_id):
    """Vista simple para historial de contactos"""
    return render(
        request,
        'legajos/historial_contactos_simple.html',
        get_legajo_contactos_context(legajo_id),
    )
