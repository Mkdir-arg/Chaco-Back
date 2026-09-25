"""Helpers de dominio del Programa Becas (épica #69 / análisis #70).

Funciones puras sobre los modelos de Becas. La autorización combinada con el
RBAC (admin vs coordinador con alcance) vive en ``programas.services.autorizacion``.
"""

from datetime import date

from django.db import models, transaction
from django.db.models import CharField, F, Q, Value
from django.db.models.lookups import Exact

from legajos.models import Ciudadano
from programas.models import (
    AsignacionCoordinador,
    CanalFormulario,
    OrigenRequisito,
    PreguntaGlobal,
    RequisitoNativo,
    Segmento,
)


def _filtro_canal(canal):
    """Un requisito se pide en su canal o en ambos (Cambio 58, D14)."""
    if not canal:
        return models.Q()
    return models.Q(canal=CanalFormulario.AMBOS) | models.Q(canal=canal)


def get_campos_formulario(convocatoria, canal=None):
    """Devuelve ``(globales, requisitos)`` para renderizar el formulario.

    - ``globales``: ``PreguntaGlobal`` activas, ordenadas (RN-31). Solo las de
      origen *pregunta*: los campos vinculados al legajo (Datos personales,
      Contacto, Apoderado; Cambio 58) siguen rindiéndose como bloques fijos
      hasta que el diseño por convocatoria los consuma.
    - ``requisitos``: ``RequisitoNativo`` del programa del segmento (los heredan
      todos sus segmentos), del segmento (subsegmento=None) y, si la convocatoria
      tiene subsegmento, también los del subsegmento (herencia; RN-32).
    - ``canal``: ``CanalFormulario.APP`` o ``LINK`` filtra lo que no se pide en
      ese canal; ``None`` devuelve todo.
    """
    globales = (
        PreguntaGlobal.objects.filter(activo=True, origen=OrigenRequisito.PREGUNTA)
        .filter(_filtro_canal(canal))
        .select_related("grupo")
        .order_by("orden", "id")
    )
    requisitos = (
        RequisitoNativo.objects.filter(filtro_requisitos_convocatoria(convocatoria))
        .filter(_filtro_canal(canal))
        .order_by("orden", "id")
    )
    return globales, requisitos


def filtro_requisitos_convocatoria(convocatoria):
    """La herencia de requisitos nativos de una convocatoria (RN-32), como
    ``Q``: los del programa del segmento, los del segmento (sin subsegmento) y,
    si la convocatoria tiene, los de su subsegmento."""
    filtros = models.Q(segmento_id=convocatoria.segmento_id, subsegmento__isnull=True)
    if convocatoria.subsegmento_id:
        filtros |= models.Q(subsegmento_id=convocatoria.subsegmento_id)
    programa_id = convocatoria.segmento.programa_id
    if programa_id:
        filtros |= models.Q(programa_id=programa_id)
    return filtros


def _se_pide_en(obj, canal):
    """``_filtro_canal`` en memoria: un requisito se pide en su canal o en ambos."""
    return not canal or obj.canal in (CanalFormulario.AMBOS, canal)


def _campo_dict(obj, alcance):
    grupo = getattr(obj, "grupo", None)
    return {
        "id": obj.pk,
        "texto": obj.texto,
        "tipo": obj.tipo,
        "opciones": obj.opciones or [],
        # Cómo mostrar las opciones (Cambio 56). Solo aplica a los tipos
        # selector; la app de campo decide su propio control con este dato.
        "presentacion": obj.presentacion,
        "obligatorio": obj.obligatorio,
        "orden": obj.orden,
        "alcance": alcance,
        "subsegmento_id": getattr(obj, "subsegmento_id", None),
        # Cambio 58: canal, origen y grupo del catálogo. La app vieja los ignora.
        "canal": obj.canal,
        "origen": getattr(obj, "origen", OrigenRequisito.PREGUNTA),
        "vinculo": getattr(obj, "vinculo", ""),
        "grupo": {"clave": grupo.clave, "nombre": grupo.nombre} if grupo is not None else None,
    }


def definicion_formulario(relevamiento):
    """Definición del formulario para la app de campo (#82) y el link público.

    Devuelve preguntas globales y requisitos (con herencia de subsegmento) según
    la convocatoria del relevamiento, filtrados por el canal del relevamiento
    (Cambio 58), más el flag ``requiere_gps`` del segmento.
    """
    from programas.services.diseno import catalogo_convocatoria, items_vigentes, plan_por_defecto, serializar

    convocatoria = relevamiento.convocatoria
    canal = CanalFormulario.del_relevamiento(relevamiento)
    # El catálogo se lee una sola vez (dos consultas) y de ahí salen las listas
    # planas de siempre y la estructura anidada: antes ``get_campos_formulario``
    # y el plan por defecto o la reconciliación repetían las lecturas por nivel
    # —hasta ocho consultas por definición, servida en cada paso 2 del link y
    # en cada detalle y alta de la app (Cambio 91)—. Mismo resultado.
    catalogo = catalogo_convocatoria(convocatoria)
    preguntas, requisitos = catalogo
    globales = [p for p in preguntas if p.origen == OrigenRequisito.PREGUNTA and _se_pide_en(p, canal)]
    requisitos = [r for r in requisitos if _se_pide_en(r, canal)]
    # Cambio 58: la estructura anidada (grupos → campos y textos, con
    # condiciones) sale del diseño de la convocatoria, reconciliado en memoria
    # con el catálogo de hoy (RN-1: lo nuevo entra, lo desactivado sale, sin
    # escribir en un GET); si todavía no lo abrió nadie, del plan por defecto.
    # Las listas planas de siempre se conservan para la app vieja.
    diseno = getattr(convocatoria, "diseno", None)
    if diseno is not None:
        items = items_vigentes(diseno, catalogo)
    else:
        items = plan_por_defecto(convocatoria, catalogo=catalogo)
    return {
        "requiere_gps": convocatoria.segmento.requiere_gps,
        "canal": canal,
        "version": diseno.version if diseno is not None else 0,
        "items": serializar(items, canal),
        "globales": [_campo_dict(p, "global") for p in globales],
        "requisitos": [_campo_dict(r, _alcance_requisito(r)) for r in requisitos],
    }


def formulario_por_client_uuid(relevamiento, client_uuid):
    """Busca la clave idempotente sin depender del lookup UUID del motor.

    La columna es texto de 36 (admite el UUID con guiones que llega por API) y
    conviven filas con y sin guiones, así que se compara contra las dos formas
    como texto plano. Antes se normalizaba la columna con ``REPLACE(CAST(...))``:
    eso anulaba el índice único y cada envío recorría todos los formularios del
    relevamiento —con el lock del relevamiento tomado—; con miles de casos la
    cola de envíos pasaba el ``read_timeout`` de 10 s y el portal daba 500
    (24/09/2026, 165 errores en el paso 2 de la inscripción pública).
    """
    if not client_uuid:
        return None
    columna = F("client_uuid")
    return (
        relevamiento.formularios.filter(
            Q(Exact(columna, Value(client_uuid.hex, output_field=CharField())))
            | Q(Exact(columna, Value(str(client_uuid), output_field=CharField())))
        )
        .order_by("pk")
        .first()
    )


def _alcance_requisito(requisito):
    if requisito.subsegmento_id:
        return "subsegmento"
    return "segmento" if requisito.segmento_id else "programa"


def get_segmentos_coordinador(user):
    """Segmentos sobre los que ``user`` tiene una asignación de coordinador activa."""
    if user is None or not getattr(user, "is_authenticated", False):
        return Segmento.objects.none()
    return Segmento.objects.filter(
        asignaciones_coordinador__coordinador=user,
        asignaciones_coordinador__activo=True,
    ).distinct()


def coordinador_gestiona_segmento(user, segmento):
    """¿``user`` tiene asignación de coordinador activa sobre ``segmento``?

    Chequeo puro sobre ``AsignacionCoordinador`` (sin considerar el rol Admin).
    La verificación completa de acceso está en
    :func:`programas.services.autorizacion.puede_gestionar_segmento`.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    return AsignacionCoordinador.objects.filter(coordinador=user, segmento=segmento, activo=True).exists()


def es_menor(fecha_nacimiento, referencia=None):
    """True si ``fecha_nacimiento`` corresponde a un menor de 18 años (RN-22).

    Devuelve None si no hay fecha (no se puede determinar).
    """
    if not fecha_nacimiento:
        return None
    hoy = referencia or date.today()
    edad = hoy.year - fecha_nacimiento.year - ((hoy.month, hoy.day) < (fecha_nacimiento.month, fecha_nacimiento.day))
    return edad < 18


def registrar_traza(formulario, usuario, cambios):
    """Registra en ``TracaFormulario`` una lista de cambios de campos (RN-14/29).

    ``cambios``: iterable de ``(campo, valor_anterior, valor_nuevo)``. Crea una
    fila inmutable por cambio. Devuelve la cantidad registrada.
    """
    from programas.models import TracaFormulario

    objs = [
        TracaFormulario(
            formulario=formulario,
            editado_por=usuario,
            campo=campo,
            valor_anterior="" if va in (None, "") else str(va),
            valor_nuevo="" if vn in (None, "") else str(vn),
        )
        for (campo, va, vn) in cambios
    ]
    if objs:
        TracaFormulario.objects.bulk_create(objs)
    return len(objs)


def _completar_contacto(ciudadano, formulario):
    """RN-10, volcado al legajo: el celular y el correo que la persona respondió
    en el formulario completan el legajo **solo si estaba vacío**; nunca pisan
    un dato ya cargado por otro programa."""
    completar = []
    if formulario.celular and not ciudadano.telefono:
        ciudadano.telefono = formulario.celular
        completar.append("telefono")
    if formulario.email_contacto and not ciudadano.email:
        ciudadano.email = formulario.email_contacto
        completar.append("email")
    if completar:
        ciudadano.save(update_fields=[*completar, "modificado"])
    return completar


@transaction.atomic
def resolver_ciudadano_offline(formulario):
    """Resuelve el ciudadano de un formulario que llegó por sync offline.

    Si ``ciudadano`` es None y hay ``datos_identificacion``, hace
    ``get_or_create`` por DNI (linkea si existe, crea con datos mínimos si no) y
    limpia ``datos_identificacion``. Idempotente: si ya hay ciudadano, no hace nada.
    """
    campos_actualizados = []
    if not formulario.ciudadano_id and formulario.datos_identificacion:
        datos = formulario.datos_identificacion
        dni = datos.get("dni")
        if dni:
            genero = str(datos.get("sexo") or datos.get("genero") or "").strip().upper()
            if genero not in Ciudadano.Genero.values:
                genero = ""
            # La localidad viene del padrón (Cambio 57) y solo completa el legajo:
            # nunca pisa una ya cargada.
            localidad_id = datos.get("localidad_id") or None
            ciudadano, creado = Ciudadano.objects.get_or_create(
                dni=dni,
                defaults={
                    "nombre": datos.get("nombre", ""),
                    "apellido": datos.get("apellido", ""),
                    "fecha_nacimiento": datos.get("fecha_nacimiento") or None,
                    "genero": genero,
                    "localidad_id": localidad_id,
                },
            )
            if not creado:
                completar = []
                if not ciudadano.genero and genero:
                    ciudadano.genero = genero
                    completar.append("genero")
                if not ciudadano.localidad_id and localidad_id:
                    ciudadano.localidad_id = localidad_id
                    completar.append("localidad")
                if completar:
                    ciudadano.save(update_fields=[*completar, "modificado"])
            _completar_contacto(ciudadano, formulario)
            formulario.ciudadano = ciudadano
            formulario.datos_identificacion = None
            campos_actualizados.extend(["ciudadano", "datos_identificacion"])

    if formulario.ciudadano_id and not campos_actualizados:
        # Ya tenía legajo (p. ej. edición de contacto en revisión): igual completa.
        _completar_contacto(formulario.ciudadano, formulario)

    apoderado_desactualizado = bool(
        formulario.apoderado_ciudadano_id and formulario.apoderado_ciudadano.dni != formulario.apoderado_dni
    )
    if formulario.apoderado_dni and (not formulario.apoderado_ciudadano_id or apoderado_desactualizado):
        apoderado, creado = Ciudadano.objects.get_or_create(
            dni=formulario.apoderado_dni,
            defaults={
                "nombre": formulario.apoderado_nombre,
                "apellido": formulario.apoderado_apellido,
                "fecha_nacimiento": formulario.apoderado_fecha_nacimiento,
                "genero": formulario.apoderado_genero,
            },
        )
        if not creado:
            completar = {}
            for campo_formulario, campo_ciudadano in (
                ("apoderado_nombre", "nombre"),
                ("apoderado_apellido", "apellido"),
                ("apoderado_fecha_nacimiento", "fecha_nacimiento"),
                ("apoderado_genero", "genero"),
            ):
                valor = getattr(formulario, campo_formulario)
                if valor and not getattr(apoderado, campo_ciudadano):
                    completar[campo_ciudadano] = valor
            if completar:
                for campo, valor in completar.items():
                    setattr(apoderado, campo, valor)
                apoderado.save(update_fields=[*completar.keys(), "modificado"])
        formulario.apoderado_ciudadano = apoderado
        campos_actualizados.append("apoderado_ciudadano")

    if campos_actualizados:
        formulario.save(update_fields=[*campos_actualizados, "modificado"])
    return formulario.ciudadano
