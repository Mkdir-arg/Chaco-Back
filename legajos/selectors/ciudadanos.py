from datetime import date

from django.db.models import Q

from programas.models import DerivacionPrograma, InscripcionPrograma, Programa

from ..models import AlertaCiudadano, Ciudadano, LegajoAtencion
from ..models.nachec import (
    CasoNachec,
    EvaluacionVulnerabilidad,
    HistorialEstadoCaso,
    PlanIntervencionNachec,
    PrestacionNachec,
    RelevamientoNachec,
)
from ..services import SolapasService


def buscar_ciudadanos_rapido(q):
    """
    Búsqueda rápida para el header del backoffice.
    - Input numérico: busca por DNI exacto.
    - Input texto (≥3 chars): busca por nombre o apellido (icontains).
    Retorna máximo 10 ciudadanos activos con datos para el dropdown.
    """
    q = q.strip()
    if not q:
        return []

    qs = Ciudadano.objects.filter(activo=True)

    if q.isdigit():
        qs = qs.filter(dni=q)
    elif len(q) >= 3:
        qs = qs.filter(Q(nombre__icontains=q) | Q(apellido__icontains=q))
    else:
        return []

    from datetime import date as _date

    hoy = _date.today()
    resultados = []
    for c in qs.order_by("apellido", "nombre")[:10]:
        edad = None
        if c.fecha_nacimiento:
            edad = (
                hoy.year
                - c.fecha_nacimiento.year
                - ((hoy.month, hoy.day) < (c.fecha_nacimiento.month, c.fecha_nacimiento.day))
            )
        resultados.append(
            {
                "id": c.pk,
                "nombre": c.nombre,
                "apellido": c.apellido,
                "dni": c.dni,
                "edad": edad,
                "foto_url": c.foto.url if c.foto else None,
            }
        )
    return resultados


def get_ciudadanos_queryset(search=""):
    queryset = Ciudadano.objects.filter(activo=True)
    if search:
        queryset = queryset.filter(
            Q(dni__icontains=search) | Q(nombre__icontains=search) | Q(apellido__icontains=search)
        )
    return queryset.order_by("apellido", "nombre")


def get_ciudadanos_dashboard_metrics():
    total_inscripciones_activas = InscripcionPrograma.objects.filter(
        estado__in=[InscripcionPrograma.Estado.ACTIVO, InscripcionPrograma.Estado.EN_SEGUIMIENTO]
    ).count()
    total_inscripciones = InscripcionPrograma.objects.count()
    tasa_adherencia = round((total_inscripciones_activas / total_inscripciones * 100) if total_inscripciones > 0 else 0)

    return {
        "total_ciudadanos": Ciudadano.objects.filter(activo=True).count(),
        "legajos_activos": total_inscripciones_activas,
        "alertas_criticas": AlertaCiudadano.objects.filter(activa=True).count(),
        "seguimientos_hoy": InscripcionPrograma.objects.filter(fecha_inscripcion=date.today()).count(),
        "tasa_adherencia": tasa_adherencia,
        "casos_alto_riesgo": DerivacionPrograma.objects.filter(
            estado=DerivacionPrograma.Estado.PENDIENTE,
            urgencia=DerivacionPrograma.Urgencia.ALTA,
        ).count(),
    }


def build_ciudadano_detail_context(ciudadano, user=None):

    from core.rbac import puede

    puede_ver_sensible = puede(user, "ciudadano.sensible")

    # Generar alertas on-the-fly antes de consultar (best-effort)
    try:
        from ..services.alertas import AlertasService

        AlertasService.generar_alertas_ciudadano(ciudadano.pk)
    except Exception:
        pass

    acompanamientos = (
        InscripcionPrograma.objects.filter(
            ciudadano=ciudadano,
            programa__tipo__in=[
                Programa.TipoPrograma.ACOMPANAMIENTO_SOCIAL,
            ],
            estado__in=[InscripcionPrograma.Estado.ACTIVO, InscripcionPrograma.Estado.EN_SEGUIMIENTO],
        )
        .select_related("programa", "responsable")
        .order_by("-fecha_inscripcion")
    )

    context = {
        "puede_ver_sensible": puede_ver_sensible,
        "legajos": LegajoAtencion.objects.none(),
        "acompanamientos": acompanamientos,
        "acompanamientos_activos_count": acompanamientos.count(),
        "solapas": [
            solapa
            for solapa in SolapasService.obtener_solapas_ciudadano(ciudadano)
            if solapa["id"] != "legajos" and "ACOMPANAMIENTO" not in solapa["id"]
        ],
        "programas_activos": SolapasService.obtener_programas_activos(ciudadano),
    }
    context["solapas_programas"] = [s for s in context["solapas"] if not s["estatica"]]

    # --- Becas (issue #80): tab embebida, contenido con prefijo para evitar colisiones ---
    if any(solapa["id"] == "becas" for solapa in context["solapas_programas"]):
        resumen_becas = SolapasService.obtener_resumen_becas_ciudadano(ciudadano)
        context["becas_formularios"] = resumen_becas["formularios"]
        context["becas_estado_texto"] = resumen_becas["estado_texto"]
        context["becas_estado_color"] = resumen_becas["estado_color"]
        context["becas_segmento_nombre"] = resumen_becas["segmento_nombre"]
        context["becas_fecha_envio"] = resumen_becas["fecha_envio"]
        context["becas_Formulario"] = resumen_becas["Formulario"]

    # Historial de programas: inscripciones que ya no están vigentes
    context["historial_programas"] = SolapasService.obtener_historial_programas(ciudadano).filter(
        estado__in=[
            InscripcionPrograma.Estado.CERRADO,
            InscripcionPrograma.Estado.SUSPENDIDO,
            InscripcionPrograma.Estado.DADO_DE_BAJA,
        ]
    )

    # --- Instituciones vinculadas (vía legajos) ---
    context["instituciones_ciudadano"] = []

    # --- Conversaciones ---
    try:
        from conversaciones.models import Conversacion

        context["conversaciones_ciudadano"] = Conversacion.objects.filter(dni_ciudadano=ciudadano.dni).order_by(
            "-fecha_inicio"
        )[:20]
    except Exception:
        context["conversaciones_ciudadano"] = []

    # --- Derivaciones ---
    context["derivaciones_ciudadano"] = ciudadano.derivaciones_programas.select_related(
        "programa_origen", "programa_destino", "derivado_por"
    ).order_by("-creado")[:20]

    # --- Alertas ---
    context["alertas_ciudadano"] = ciudadano.alertas.filter(activa=True).order_by("prioridad", "-creado")

    # --- Línea de tiempo ---
    linea = []

    for ins in (
        InscripcionPrograma.objects.filter(ciudadano=ciudadano)
        .select_related("programa")
        .order_by("-fecha_inscripcion")[:20]
    ):
        linea.append(
            {
                "fecha": ins.fecha_inscripcion,
                "icono": "user-plus",
                "color_hex": ins.programa.color or "#3B82F6",
                "titulo": f"Inscripción a {ins.programa.nombre}",
                "descripcion": ins.get_estado_display(),
            }
        )

    for deriv in ciudadano.derivaciones_programas.select_related("programa_destino").order_by("-creado")[:10]:
        linea.append(
            {
                "fecha": deriv.creado.date() if hasattr(deriv.creado, "date") else deriv.creado,
                "icono": "share-nodes",
                "color_hex": "#F97316",
                "titulo": f"Derivación a {deriv.programa_destino.nombre}",
                "descripcion": deriv.get_estado_display(),
            }
        )

    linea.sort(key=lambda x: x["fecha"], reverse=True)
    context["linea_tiempo"] = linea[:50]

    caso_nachec = (
        CasoNachec.objects.filter(ciudadano_titular=ciudadano)
        .exclude(estado__in=["CERRADO", "RECHAZADO", "SUSPENDIDO"])
        .select_related("territorial", "coordinador", "operador_admision")
        .order_by("-creado")
        .first()
    )
    if not caso_nachec:
        return context

    context["caso_nachec"] = caso_nachec
    context["relevamiento"] = RelevamientoNachec.objects.filter(caso=caso_nachec).order_by("-creado").first()
    context["evaluacion"] = EvaluacionVulnerabilidad.objects.filter(caso=caso_nachec).first()
    context["plan_vigente"] = PlanIntervencionNachec.objects.filter(
        caso=caso_nachec,
        vigente=True,
    ).first()
    context["prestaciones"] = (
        PrestacionNachec.objects.filter(caso=caso_nachec).select_related("responsable").order_by("-creado")[:10]
    )
    context["historial_estados"] = (
        HistorialEstadoCaso.objects.filter(caso=caso_nachec).select_related("usuario").order_by("-timestamp")[:10]
    )
    return context
