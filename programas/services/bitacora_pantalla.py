"""Datos de la pantalla «Bitácora del turno» (MVP v2, etapa 3 · #697 · P10).

La vista no cuenta ni decide estados: delega acá, y acá tampoco se decide ninguna regla de
la bitácora ni del censo.

* **El censo sale de** :mod:`programas.services.censo` **tal cual**: inicial, ingresos,
  egresos, final y si el tramo cuadra. Acá solo se le da formato. Si un tramo no cuadra se
  muestra con texto —cuánto dicen las estadías y cuánto los movimientos—, no solo con color.
* **Las cifras de plazas salen de** :func:`programas.services.ocupacion.ocupacion_de_plazas`,
  la misma fuente que el mapa y el detalle del dispositivo. Son la foto de **ahora**, así
  que se muestran solo en el día en curso: en un día anterior serían una mentira.
* **Qué turno está cerrado, abierto o sin abrir** lo dice el estado del tramo del censo
  (``cerrado``, ``en_curso``, ``por_venir``). No hay pase de guardia todavía: el turno
  «abre» porque su horario empezó, no porque alguien lo recibió.
* **Quién puede cargar o corregir** lo decide el servicio de la bitácora. Acá solo se
  dibujan los controles en el único lugar donde tienen sentido —el turno en curso del día
  en curso— y, si el servicio rechaza la carga, la vista muestra su error.
* **Un turno dado de baja no esconde su historia.** El censo usa los turnos activos, pero
  las novedades guardan su turno: si una fecha tiene novedades de un turno que después se
  dio de baja, ese turno aparece igual, como tarjeta de solo lectura y sin censo propio.

Privacidad
----------

Las personas involucradas en una novedad se **nombran** solo si quien mira tiene
``ciudadano.ver`` (la regla del Cambio 271: nombrar a una persona es abrir su legajo). Sin
esa capacidad se dice cuántas son, y el nombre ni siquiera llega al template.

Costo
-----

Constante en el volumen de la bitácora: los turnos, el censo (dos consultas con los turnos
ya leídos), las plazas (tres, solo hoy), el conteo de entradas por turno, la página de
entradas con sus personas y adjuntos (tres, más un ``COUNT`` solo si hay más que el tope),
las versiones anteriores, y —según lo que el usuario puede hacer— las novedades corregibles,
las personas alojadas y los turnos para configurar; y una más, solo si la fecha tiene
novedades de turnos dados de baja. **Ninguna consulta por entrada.**
Presupuesto ``dispositivos_bitacora_turno`` en ``scripts/perf_budgets.json``.
"""

from datetime import date, timedelta

from django.db.models import Count, Prefetch
from django.utils import timezone
from django.utils.formats import date_format

from programas.models import Dispositivo, EntradaBitacora, Estadia, Turno
from programas.services import censo as censo_servicio
from programas.services.bitacora import MAX_ADJUNTOS_POR_ENTRADA, turnos_activos
from programas.services.ocupacion import ocupacion_de_plazas

#: Cuántas entradas del turno se dibujan; el resto se avisa con el total. La pieza tiene su
#: propio tope de 100 como red: el recorte es este.
TOPE_ENTRADAS = 50
#: Cuántas novedades del turno en curso se ofrecen para corregir (las más recientes).
TOPE_CORREGIBLES = 50

#: El tono del badge de cada tipo. El template no sabe qué tipo es «grave». Vive en el
#: modelo, con el enum: la solapa Novedades del detalle de la estadía lo necesita igual y
#: lee las mismas entradas (`selectors.estadia_detalle`).
TONO_POR_TIPO = EntradaBitacora.TONO_POR_TIPO

#: Texto y tono del estado del turno, según el estado del tramo del censo.
ESTADO_TURNO = {
    censo_servicio.CERRADO: ("Cerrado", "success"),
    censo_servicio.EN_CURSO: ("Abierto", "info"),
    censo_servicio.POR_VENIR: ("Sin abrir", ""),
}

#: Los tipos que carga el operador, en el orden del modelo.
TIPOS_MANUALES = [
    (valor, texto) for valor, texto in EntradaBitacora.Tipo.choices if valor not in EntradaBitacora.TIPOS_AUTOMATICOS
]

#: Los tipos del filtro: todos menos el pase de guardia, que en esta etapa no existe (ni se
#: dibuja ni se ofrece, tampoco como opción de un filtro).
TIPOS_DEL_FILTRO = [
    (valor, texto) for valor, texto in EntradaBitacora.Tipo.choices if valor != EntradaBitacora.Tipo.PASE
]

#: Antes de esto no hubo bitácora: una fecha más vieja es un error de tipeo, y sin piso
#: restar un día a ``date.min`` desborda.
PISO_FECHA = date(2020, 1, 1)


def fecha_pedida(valor, hoy: date) -> date:
    """La fecha operativa de la querystring, o hoy. Futura o mal escrita es hoy; muy vieja, el piso."""

    try:
        fecha = date.fromisoformat((valor or "").strip())
    except ValueError:
        return hoy
    return max(min(fecha, hoy), PISO_FECHA)


def _hora(momento) -> str:
    return timezone.localtime(momento).strftime("%H:%M")


def _dia(fecha: date) -> str:
    return date_format(fecha, "l d/m/Y")


def _plural(cantidad, singular, plural):
    return f"{cantidad} {singular if cantidad == 1 else plural}"


def _autor(usuario) -> str:
    if usuario is None:
        return ""
    return usuario.get_full_name() or usuario.get_username()


def _persona(estadia) -> str:
    ciudadano = estadia.ciudadano
    return f"{ciudadano.apellido}, {ciudadano.nombre}"


def _texto_de(entrada, *, nombrar_personas: bool) -> str:
    """El texto de la entrada más las líneas de personas, adjuntos y motivo de corrección.

    La pieza escapa y respeta los saltos de línea: los datos se agregan como líneas nuevas.
    """

    lineas = [entrada.texto]
    personas = list(entrada.personas.all())
    if personas:
        if nombrar_personas:
            lineas.append("Personas: " + " · ".join(_persona(estadia) for estadia in personas))
        else:
            lineas.append("Personas involucradas: " + str(len(personas)))
    adjuntos = list(entrada.adjuntos.all())
    if adjuntos:
        lineas.append("Adjuntos: " + ", ".join(str(adjunto) for adjunto in adjuntos))
    if entrada.motivo_correccion:
        lineas.append("Motivo de la corrección: " + entrada.motivo_correccion)
    return "\n".join(lineas)


def _entrada(entrada, *, nombrar_personas: bool, reemplazada: bool = False) -> dict:
    """El dict que pide `components/_entradas_bitacora.html`."""

    datos = {
        "hora": _hora(entrada.momento),
        "categoria": entrada.get_tipo_display(),
        "tono": TONO_POR_TIPO.get(entrada.tipo, ""),
        "texto": _texto_de(entrada, nombrar_personas=nombrar_personas),
        "autor": _autor(entrada.responsable),
        "automatica": entrada.origen == EntradaBitacora.Origen.AUTOMATICA,
        "version": entrada.version,
    }
    if reemplazada:
        # La pieza escribe «Versión N» solo desde la 2; la reemplazada lo dice en el título
        # para que la versión 1 también se lea como versión.
        datos["titulo"] = f"Versión {entrada.version}, reemplazada."
        datos["version"] = None
    return datos


def _personas_prefetch(nombrar_personas: bool):
    estadias = Estadia.objects.only("id", "ciudadano_id")
    if nombrar_personas:
        estadias = Estadia.objects.select_related("ciudadano").only(
            "id", "ciudadano", "ciudadano__nombre", "ciudadano__apellido"
        )
    return Prefetch("personas", queryset=estadias)


def _del_turno(dispositivo, fecha, turno, tipo):
    entradas = EntradaBitacora.objects.filter(dispositivo=dispositivo, fecha_operativa=fecha, turno=turno)
    if tipo:
        entradas = entradas.filter(tipo=tipo)
    return entradas


def _tarjeta(turno, tramo, *, elegido, cantidad, url_ver, acciones_en_curso) -> dict:
    """El dict de `components/_turno_tarjeta.html`. Sin ``tramo``, el turno está dado de baja."""

    acciones = []
    if tramo is None:
        estado, tono = "Dado de baja", ""
        detalle = f"{_plural(cantidad, 'entrada', 'entradas')} · turno dado de baja, sin censo propio"
    else:
        estado, tono = ESTADO_TURNO[tramo.estado]
        if tramo.estado == censo_servicio.POR_VENIR:
            detalle = f"Empieza a las {_hora(tramo.inicio)}."
        elif tramo.estado == censo_servicio.EN_CURSO:
            detalle = (
                f"{_plural(cantidad, 'entrada', 'entradas')} · {_plural(tramo.final, 'alojada', 'alojadas')} ahora"
            )
        else:
            detalle = (
                f"{_plural(cantidad, 'entrada', 'entradas')} · {tramo.inicial} al inicio · {tramo.final} al cierre"
            )
        if not tramo.cuadra:
            detalle += " · el censo no cuadra"
        if tramo.en_curso:
            acciones.extend(acciones_en_curso)
    if not elegido and (tramo is None or tramo.estado != censo_servicio.POR_VENIR):
        acciones.append({"texto": "Ver", "variante": "tertiary", "url": url_ver})
    return {
        "nombre": turno.nombre,
        "horario": f"{turno.hora_desde:%H:%M}–{turno.hora_hasta:%H:%M}",
        "estado": estado,
        "tono": tono,
        "detalle": detalle,
        "activo": bool(tramo and tramo.en_curso),
        "sin_abrir": bool(tramo and tramo.estado == censo_servicio.POR_VENIR),
        "acciones": acciones,
    }


def _filas_del_censo(tramo, censo_dia, conteo):
    """Las filas del recuadro «Censo del turno», en el orden del mockup y con las cifras de los
    servicios y nada más. Solo «Disponibles» va destacado."""

    filas = []
    if conteo is not None:
        filas.append({"etiqueta": "Plazas totales / operativas", "valor": f"{conteo.totales} / {conteo.operativas}"})
    final = None
    if tramo is not None and tramo.estado != censo_servicio.POR_VENIR:
        if tramo.cuadra:
            final = str(tramo.final)
        else:
            # Manda la existencia de las estadías, pero se dicen las dos.
            final = f"{tramo.alojadas_al_fin} según estadías · {tramo.final} según movimientos"
        filas += [
            {"etiqueta": f"Al inicio del turno · {_hora(tramo.inicio)}", "valor": tramo.inicial},
            {"etiqueta": "Ingresos del turno", "valor": tramo.ingresos},
            {"etiqueta": "Egresos del turno", "valor": tramo.egresos},
        ]
    filas += [
        {"etiqueta": "Ingresos del día", "valor": censo_dia.ingresos},
        {"etiqueta": "Egresos del día", "valor": censo_dia.egresos},
    ]
    if final is not None:
        filas.append(
            {
                "etiqueta": "Alojadas ahora" if tramo.en_curso else f"Al cierre del turno · {_hora(tramo.fin)}",
                "valor": final,
            }
        )
    if conteo is not None:
        filas += [
            {"etiqueta": "Reservadas o prestadas", "valor": conteo.reservadas},
            {"etiqueta": "Disponibles", "valor": conteo.disponibles, "destacado": True},
        ]
    return filas


def _descuadres(censo_dia) -> str:
    """El texto de la alerta: qué tramos del día no cuadran y por cuánto."""

    partes = []
    for tramo in censo_dia.tramos:
        if tramo.cuadra:
            continue
        nombre = tramo.nombre
        if tramo.turno is None:
            nombre = f"{tramo.nombre} ({_hora(tramo.inicio)}–{_hora(tramo.fin)})"
        diferencia = abs(tramo.diferencia)
        sentido = "más" if tramo.diferencia > 0 else "menos"
        partes.append(
            f"{nombre}: las estadías registran {_plural(diferencia, 'persona', 'personas')} {sentido} "
            "que los ingresos y egresos"
        )
    if not partes:
        return ""
    return (
        "; ".join(partes) + ". Se muestra la existencia de las estadías, que es la del mapa de plazas; "
        "revisá los movimientos de ese tramo."
    )


def pantalla_bitacora(
    dispositivo,
    *,
    fecha=None,
    turno_id=None,
    tipo="",
    ahora=None,
    puede_cargar=False,
    puede_configurar=False,
    nombrar_personas=False,
    url_base="",
):
    """Todo lo que dibuja P10 para un día operativo del dispositivo.

    ``fecha`` es la fecha operativa pedida, como ``date`` o como el texto ISO de la
    querystring (por omisión, la de ahora; nunca futura ni anterior a ``PISO_FECHA``).
    ``turno_id`` elige el turno cuyas entradas se listan (por omisión, el en curso; en un
    día anterior, el primero). ``tipo`` filtra las entradas. Los ``puede_*`` y
    ``nombrar_personas`` los resuelve la vista con ``puede_operar_dispositivo`` y
    ``rbac.puede``: acá solo deciden qué se arma.
    """

    ahora = ahora or timezone.now()
    turnos = turnos_activos(dispositivo)
    hoy = censo_servicio.fecha_operativa_de(dispositivo, ahora, turnos=turnos)
    if isinstance(fecha, str):
        fecha = fecha_pedida(fecha, hoy)
    else:
        fecha = max(min(fecha or hoy, hoy), PISO_FECHA)
    es_hoy = fecha == hoy
    tipos_validos = dict(TIPOS_DEL_FILTRO)
    tipo = tipo if tipo in tipos_validos else ""
    activo = dispositivo.estado == Dispositivo.Estado.ACTIVO

    censo_dia = censo_servicio.censo_del_dia(dispositivo, fecha, turnos=turnos, ahora=ahora)
    tramos_de_turno = list(censo_dia.turnos)

    # El turno en curso lo decide el censo, comparando con `ahora`: en un día anterior todos
    # sus tramos están cerrados, así que no hay ninguno. Es la ÚNICA compuerta de la pantalla
    # para ofrecer cargar o corregir; la regla de fondo (solo el turno en curso) la sostiene
    # `programas.services.bitacora`, que rechaza igual cualquier otra carga.
    en_curso = next((t for t in tramos_de_turno if t.en_curso), None)
    puede_cargar = bool(puede_cargar and activo and en_curso is not None)

    cantidades = dict(
        EntradaBitacora.objects.vigentes()
        .filter(dispositivo=dispositivo, fecha_operativa=fecha)
        .values_list("turno_id")
        .annotate(cuantas=Count("id"))
        .order_by()
    )

    # Los turnos de la fecha: los activos, con su tramo del censo, y los dados de baja que
    # tienen novedades ese día, sin censo. La consulta de estos últimos solo se hace si los hay.
    opciones = [(t.turno, t) for t in tramos_de_turno]
    activos = {t.turno.pk for t in tramos_de_turno}
    dados_de_baja = [pk for pk in cantidades if pk not in activos]
    if dados_de_baja:
        opciones += [
            (turno, None)
            for turno in Turno.objects.filter(pk__in=dados_de_baja, dispositivo=dispositivo).order_by(
                "orden", "hora_desde", "id"
            )
        ]

    # En el orden del día: un turno dado de baja va donde caía su horario, no al final.
    opciones.sort(key=lambda opcion: opcion[0].ventana(fecha)[0])

    # El turno elegido: el de la querystring si es uno de la fecha. Si no, el en curso; hoy
    # en un hueco entre turnos, el último que empezó; en un día anterior, el primero.
    por_pk = {opcion[0].pk: opcion for opcion in opciones}
    elegido = None
    try:
        elegido = por_pk.get(int(turno_id)) if turno_id not in (None, "") else None
    except (TypeError, ValueError):
        elegido = None
    if elegido is None and opciones:
        empezados = [t for t in tramos_de_turno if t.estado != censo_servicio.POR_VENIR]
        if en_curso is not None:
            elegido = (en_curso.turno, en_curso)
        elif es_hoy and empezados:
            elegido = (empezados[-1].turno, empezados[-1])
        else:
            elegido = opciones[0]
    turno, tramo = elegido if elegido else (None, None)

    # Las plazas son la foto de ahora: solo tienen sentido en el día en curso.
    conteo = ocupacion_de_plazas(dispositivo, ahora).de(dispositivo).conteo if es_hoy else None

    entradas, total, versiones, adjuntos = [], 0, [], []
    if turno is not None:
        vigentes = list(
            _del_turno(dispositivo, fecha, turno, tipo)
            .vigentes()
            .select_related("responsable")
            .prefetch_related(_personas_prefetch(nombrar_personas), "adjuntos")
            .order_by("-momento", "-id")[: TOPE_ENTRADAS + 1]
        )
        total = len(vigentes)
        if total > TOPE_ENTRADAS:
            total = _del_turno(dispositivo, fecha, turno, tipo).vigentes().count()
            vigentes = vigentes[:TOPE_ENTRADAS]
        entradas = [_entrada(entrada, nombrar_personas=nombrar_personas) for entrada in vigentes]
        for entrada in vigentes:
            for adjunto in entrada.adjuntos.all():
                adjuntos.append(
                    {
                        "nombre": str(adjunto),
                        "url": adjunto.archivo.url,
                        "hora": _hora(entrada.momento),
                        "categoria": entrada.get_tipo_display(),
                    }
                )
        reemplazadas = (
            _del_turno(dispositivo, fecha, turno, tipo)
            .filter(correccion__isnull=False)
            .select_related("responsable")
            .prefetch_related(_personas_prefetch(nombrar_personas), "adjuntos")
            .order_by("-momento", "-version", "-id")[:TOPE_ENTRADAS]
        )
        versiones = [_entrada(entrada, nombrar_personas=nombrar_personas, reemplazada=True) for entrada in reemplazadas]

    corregibles = []
    if puede_cargar:
        corregibles = [
            {
                "pk": entrada.pk,
                "etiqueta": f"{_hora(entrada.momento)} · {entrada.get_tipo_display()} · {entrada.texto[:60]}",
                "tipo": entrada.tipo,
                "texto": entrada.texto,
            }
            for entrada in EntradaBitacora.objects.vigentes()
            .filter(
                dispositivo=dispositivo,
                fecha_operativa=fecha,
                turno=en_curso.turno,
                origen=EntradaBitacora.Origen.MANUAL,
            )
            .only("id", "momento", "tipo", "texto")
            .order_by("-momento", "-id")[:TOPE_CORREGIBLES]
        ]

    personas = []
    if puede_cargar and nombrar_personas:
        personas = [
            (estadia.pk, _persona(estadia) + (f" · {estadia.plaza.codigo}" if estadia.plaza_id else ""))
            for estadia in Estadia.objects.activas()
            .filter(dispositivo=dispositivo)
            .select_related("ciudadano", "plaza")
            .only("id", "plaza", "plaza__codigo", "ciudadano", "ciudadano__nombre", "ciudadano__apellido")
            .order_by("ciudadano__apellido", "ciudadano__nombre", "id")
        ]

    turnos_config = []
    if puede_configurar:
        turnos_config = [
            {
                "pk": t.pk,
                "etiqueta": str(t) if t.activo else f"{t} (dado de baja)",
                "nombre": t.nombre,
                "desde": f"{t.hora_desde:%H:%M}",
                "hasta": f"{t.hora_hasta:%H:%M}",
                "orden": t.orden,
                "activo": t.activo,
            }
            for t in Turno.objects.filter(dispositivo=dispositivo).order_by("orden", "hora_desde", "id")
        ]

    def url_de(fecha_url, turno_url=None, extra=""):
        partes = [f"fecha={fecha_url.isoformat()}"]
        if turno_url is not None:
            partes.append(f"turno={turno_url.pk}")
        if extra:
            partes.append(extra)
        return f"{url_base}?{'&'.join(partes)}"

    # Las acciones de la tarjeta llevan a esta misma pantalla con el modal pedido por GET
    # (`?novedad=1`, `?corregir=`): la vista lo abre al dibujarla. Ningún enlace muta nada.
    #
    # El turno de la URL es el EN CURSO, no el que se está mirando: la tarjeta con acciones es
    # siempre la del turno en curso (`_tarjeta` las cuelga solo de ese tramo) y `corregibles`
    # sale de `en_curso.turno`. Si se llegó con «Ver» a otro turno, llevar el de la vista
    # abriría el modal sobre un turno al que no se puede cargar, con una lista de correcciones
    # que no son suyas. `puede_cargar` ya exige `en_curso is not None`.
    acciones_en_curso = []
    if puede_cargar:
        acciones_en_curso.append(
            {"texto": "+ Novedad", "variante": "brand", "url": url_de(fecha, en_curso.turno, "novedad=1")}
        )
        if corregibles:
            acciones_en_curso.append(
                {"texto": "Corregir", "variante": "secondary", "url": url_de(fecha, en_curso.turno, "corregir=")}
            )
    tarjetas = [
        _tarjeta(
            opcion_turno,
            opcion_tramo,
            elegido=turno is not None and opcion_turno.pk == turno.pk,
            cantidad=cantidades.get(opcion_turno.pk, 0),
            url_ver=url_de(fecha, opcion_turno),
            acciones_en_curso=acciones_en_curso,
        )
        for opcion_turno, opcion_tramo in opciones
    ]

    anterior = fecha - timedelta(days=1) if fecha > PISO_FECHA else None
    siguiente = fecha + timedelta(days=1) if fecha < hoy else None
    ocultos = [("fecha", fecha.isoformat())]
    if turno is not None:
        ocultos.append(("turno", str(turno.pk)))

    # Por omisión se mira el turno en curso: si lo que se lista es otro, se llegó con «Ver» y
    # el título lo dice, para que nadie lea las entradas de la mañana como las de ahora.
    titulo_entradas = "Entradas"
    if turno is not None:
        titulo_entradas = f"Turno {turno.nombre} · entradas"
        if en_curso is not None and turno.pk != en_curso.turno.pk:
            titulo_entradas += f" · no es el turno en curso (ahora, {en_curso.turno.nombre})"

    if tramo is None and turno is not None:
        censo_nota = f"El turno {turno.nombre} se dio de baja: no tiene censo propio. Abajo, el del día."
    elif tramo is not None and tramo.estado == censo_servicio.POR_VENIR:
        censo_nota = f"El turno {turno.nombre} todavía no empezó."
    else:
        censo_nota = ""

    return {
        "hoy": hoy,
        "fecha": fecha,
        "fecha_texto": _dia(fecha),
        "es_hoy": es_hoy,
        "dia_anterior": {"url": url_de(anterior), "texto": _dia(anterior)} if anterior else None,
        "dia_siguiente": {"url": url_de(siguiente), "texto": _dia(siguiente)} if siguiente else None,
        "url_hoy": url_base if not es_hoy else "",
        "sin_turnos": not turnos,
        "tarjetas": tarjetas,
        "turno": turno,
        "tramo": tramo,
        "titulo_entradas": titulo_entradas,
        "censo": censo_dia,
        "censo_filas": _filas_del_censo(tramo, censo_dia, conteo),
        "censo_descuadre": _descuadres(censo_dia),
        "censo_nota": censo_nota,
        "entradas": entradas,
        "entradas_total": total,
        "versiones": versiones,
        "adjuntos": adjuntos,
        "puede_cargar": puede_cargar,
        "turno_en_curso": en_curso.turno if en_curso else None,
        "corregibles": corregibles,
        "personas": personas,
        "turnos_config": turnos_config,
        "pildoras": [
            {
                "nombre": "tipo",
                "etiqueta": "Tipo",
                "opciones": TIPOS_DEL_FILTRO,
                "valor": tipo,
                "todos": "Todas",
            }
        ],
        "ocultos": ocultos,
        "tipo": tipo,
        "url_sin_tipo": url_de(fecha, turno),
        # Abrir el modal de turnos sin perder dónde se estaba: vuelve a ESTA fecha y a ESTE
        # turno. Armado acá, con `url_de`, y no en la vista: la vista no conoce la fecha
        # resuelta (`?fecha=` puede venir vacía o inválida) ni el turno elegido por omisión.
        "url_abrir_turnos": url_de(fecha, turno, "turnos=1"),
        "censo_titulo": "Censo del turno" if tramo is not None else "Censo del día",
        "subtitulo_en_curso": (
            f"Turno {en_curso.turno.nombre} · {en_curso.turno.hora_desde:%H:%M}–{en_curso.turno.hora_hasta:%H:%M}"
            if en_curso
            else ""
        ),
        "dispositivo_activo": activo,
        "max_adjuntos": MAX_ADJUNTOS_POR_ENTRADA,
    }
