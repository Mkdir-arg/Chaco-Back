"""Helpers de dominio del Programa Becas (épica #69 / análisis #70).

Funciones puras sobre los modelos de Becas. La autorización combinada con el
RBAC (admin vs coordinador con alcance) vive en ``programas.services.autorizacion``.
"""

from django.db import models, transaction

# RED-09 (segunda parte): el helper se mudó a ``core.db`` —lo necesitan también
# ``legajos`` y ``users``, que no pueden importar un servicio de ``programas``—.
# Se reexporta desde acá porque media docena de módulos ya lo importaban de este
# nombre; borrar el reexport es un cambio aparte, no el de la mudanza.
from core.db import q_uuid_en_texto
from legajos.models import Ciudadano
from programas.models import (
    AsignacionCoordinador,
    CanalFormulario,
    OrigenRequisito,
    PreguntaGlobal,
    Relevamiento,
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
    datos = {
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
    # G1-08: a qué campo del alta en SIIS alimenta este dato. Va **solo cuando
    # hay destino**: la foto del caso son ~27 KB y ``programas_formulario`` pesa
    # 283 MB en producción (Cambio 106), así que una clave vacía por campo se
    # paga por cada caso. Lo que marca que la foto es de las nuevas es la clave
    # ``destinos_siis`` del nivel de arriba, no esta.
    destino = getattr(obj, "destino_siis", "") or ""
    if destino:
        datos["destino_siis"] = destino
    return datos


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
    return relevamiento.formularios.filter(q_uuid_en_texto("client_uuid", client_uuid)).order_by("pk").first()


def relevamiento_publico_por_token(token, queryset=None):
    """Queryset de relevamientos públicos con ese ``token_publico`` (con o sin guiones).

    Una sola consulta por el índice único. ``token`` es un ``uuid.UUID`` (el
    conversor ``<uuid:token>`` de la URL ya lo entrega así).
    """
    if queryset is None:
        queryset = Relevamiento.objects.all()
    return queryset.filter(q_uuid_en_texto("token_publico", token), tipo=Relevamiento.Tipo.PUBLICO)


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


def trazas_de(formulario, usuario, cambios):
    """Las filas de ``TracaFormulario`` de una lista de cambios, **sin guardarlas**.

    ``cambios``: iterable de ``(campo, valor_anterior, valor_nuevo)``. Una fila por
    cambio (RN-14/29). Existe aparte de :func:`registrar_traza` porque los procesos
    por lotes —el cruce del padrón, PERF-04— acumulan las filas de miles de casos y
    las escriben con un solo ``bulk_create``: con un INSERT por caso, subir un padrón
    de una convocatoria grande son miles de sentencias dentro del request.
    """
    from programas.models import TracaFormulario

    return [
        TracaFormulario(
            formulario=formulario,
            editado_por=usuario,
            campo=campo,
            valor_anterior="" if va in (None, "") else str(va),
            valor_nuevo="" if vn in (None, "") else str(vn),
        )
        for (campo, va, vn) in cambios
    ]


def registrar_traza(formulario, usuario, cambios):
    """Registra en ``TracaFormulario`` una lista de cambios de campos (RN-14/29).

    ``cambios``: iterable de ``(campo, valor_anterior, valor_nuevo)``. Crea una
    fila inmutable por cambio. Devuelve la cantidad registrada.
    """
    from programas.models import TracaFormulario

    objs = trazas_de(formulario, usuario, cambios)
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


_ETIQUETA_IDENTIDAD = {"nombre": "nombre", "apellido": "apellido", "fecha_nacimiento": "fecha de nacimiento"}


def _anotar_identidad_acreditada(formulario, ciudadano, datos):
    """SIIS-08: deja constancia cuando el legajo que ya existía no coincide con
    la identidad que acreditó el padrón o Base de Personas.

    Un legajo creado antes con datos autodeclarados —o falsos, G1-01— recibe un
    caso validado y se queda como estaba: se completan ``genero`` y ``localidad``
    si faltaban, y nada más. El caso figura como validado, pero el alta en SIIS
    sale con el nombre del legajo, que es el que nadie verificó, y el alta en
    SIIS no tiene baja.

    **D-S08, opción mínima (default registrado):** no se corrige el legajo acá
    —quién manda sobre el legajo es una decisión del cliente— sino que se guarda
    la identidad acreditada y se frena el envío hasta que un coordinador resuelva
    cuál de las dos vale. Se guarda la identidad, no «hay conflicto»: así
    ``armar_payload`` vuelve a comparar contra el legajo de ese momento y el
    caso se destraba solo cuando alguien corrige el legajo, sin necesitar que
    nadie se acuerde de borrar una marca.

    Devuelve True si tocó ``formulario.datos_siis``.
    """
    from programas.services.identidad import (
        CLAVE_IDENTIDAD_ACREDITADA,
        ORIGENES_ACREDITADOS,
        diferencias_con_el_legajo,
    )

    origen = str(datos.get("origen") or "").strip().lower()
    if origen not in ORIGENES_ACREDITADOS:
        return False
    acreditada = {
        "nombre": datos.get("nombre") or "",
        "apellido": datos.get("apellido") or "",
        "fecha_nacimiento": str(datos.get("fecha_nacimiento") or ""),
        "origen": origen,
    }
    diferencias = diferencias_con_el_legajo(ciudadano, acreditada)
    if not diferencias:
        return False
    corrientes = formulario.datos_siis if isinstance(formulario.datos_siis, dict) else {}
    formulario.datos_siis = {**corrientes, CLAVE_IDENTIDAD_ACREDITADA: acreditada}
    registrar_traza(
        formulario,
        None,
        [
            (f"Identidad acreditada ({origen}) · {_ETIQUETA_IDENTIDAD[campo]}", del_legajo, acreditado)
            for campo, (del_legajo, acreditado) in diferencias.items()
        ],
    )
    return True


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
            # G1-06: la fecha puede venir en cualquier formato (o ser imposible)
            # y hasta acá llegaba cruda al ORM. El alta explota **después** del
            # commit del caso: 500, la app reintenta por ser 5xx y el caso queda
            # sin legajo. La API ya la normaliza al entrar; este es el cinturón
            # para los otros caminos y para los datos ya guardados.
            from programas.services.personas import fecha_iso

            fecha_nacimiento = fecha_iso(datos.get("fecha_nacimiento")) or None
            ciudadano, creado = Ciudadano.objects.get_or_create(
                dni=dni,
                defaults={
                    "nombre": datos.get("nombre", ""),
                    "apellido": datos.get("apellido", ""),
                    "fecha_nacimiento": fecha_nacimiento,
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
                if _anotar_identidad_acreditada(formulario, ciudadano, datos):
                    campos_actualizados.append("datos_siis")
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
