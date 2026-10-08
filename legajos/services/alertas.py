import logging
from collections import defaultdict
from datetime import timedelta

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.core.exceptions import ValidationError
from django.db.models import Count, Max, Q
from django.utils import timezone

from core.utils_fechas import fecha_local

from ..models import (
    AlertaCiudadano,
    Ciudadano,
    LegajoAtencion,
)
from ..models.contactos import HistorialContacto
from .linking import (
    get_legajo_ids_de_ciudadanos_activos,
    get_legajo_ids_for_ciudadano,
    get_programa_ids_for_legajo_ids,
    get_vinculos_de_legajos,
)

logger = logging.getLogger(__name__)

#: Legajos que se reconcilian por vuelta. El costo de la pasada queda acotado al
#: tamaño del lote: 4 consultas fijas, más las altas y un UPDATE de cierre.
LOTE_LEGAJOS = 500

#: Prioridades que la pasada periódica apaga cuando la alerta deja de aplicar. Las
#: ALTA y CRÍTICA las cierra una persona: apagarlas solas sería perder el registro de
#: un riesgo que nadie miró.
PRIORIDADES_RECONCILIADAS = ("MEDIA", "BAJA")

#: Alerta de conversaciones: la genera un mensaje del ciudadano, no el estado del
#: legajo, así que la pasada de legajos no la cierra (LEG-01). Cuelga de
#: ``legajo=None``, con lo que además nunca entra en el recorte por legajo; va
#: nombrada igual para que el día que alguien le ponga legajo la regla siga valiendo.
TIPO_DE_CONVERSACIONES = "MENSAJE_CIUDADANO"


class AlertasService:
    """Servicio para generar y gestionar alertas automáticas."""

    @staticmethod
    def reconciliar_alertas():
        """Pasada periódica de alertas: una vuelta por **legajo**, no por ciudadano.

        Las dos mitades de la Ola 4 PR 4 viven acá:

        * **PERF-20.** El comando recorría ``Ciudadano.objects.filter(activo=True)`` y
          pagaba tres consultas por cada uno —el ``SELECT`` del ciudadano, el ``UPDATE``
          en bloque de sus alertas y el ``SELECT`` de sus legajos, casi siempre con un
          ``IN`` vacío—. Medido con 20.200 activos de los que 200 tienen legajo: **61.821
          sentencias por corrida**, cada hora. Acá el universo sale de las inscripciones
          que **sí** tienen legajo, así que el costo deja de depender de los 20.000
          ciudadanos que no tienen nada que alertar.
        * **LEG-01.** Ya no se apaga en bloque para volver a crear: se compara el set
          vigente ``(legajo, tipo)`` contra el activo, se crea solo lo que falta y se
          cierra —con ``fecha_cierre``, que el ``update`` masivo no escribía— lo que dejó
          de aplicar. Una segunda pasada seguida no escribe una sola fila ni vuelve a
          notificar por WebSocket.

        Devuelve ``{"legajos", "vigentes", "creadas", "cerradas"}``.
        """
        legajo_ids = list(get_legajo_ids_de_ciudadanos_activos())
        resumen = {"legajos": len(legajo_ids), "vigentes": 0, "creadas": 0, "cerradas": 0}
        for desde in range(0, len(legajo_ids), LOTE_LEGAJOS):
            lote = legajo_ids[desde : desde + LOTE_LEGAJOS]
            try:
                parcial = AlertasService._reconciliar_lote(lote)
            except Exception as exc:
                # Un lote que falla no se lleva puesta la pasada entera, igual que antes
                # un ciudadano que fallaba no frenaba a los demás.
                logger.exception("Error reconciliando alertas de un lote de legajos: %s", exc)
                continue
            for clave, valor in parcial.items():
                resumen[clave] += valor
        return resumen

    @staticmethod
    def generar_alertas_ciudadano(ciudadano_id):
        """Reconcilia las alertas de los legajos de un ciudadano.

        Mismo contrato que :meth:`reconciliar_alertas` acotado a una persona: crea lo
        que falta, cierra lo que dejó de aplicar y no vuelve a notificar lo que ya
        estaba.
        """
        try:
            legajo_ids = list(get_legajo_ids_for_ciudadano(ciudadano_id).distinct())
            return AlertasService._reconciliar_lote(legajo_ids)
        except Exception as exc:
            logger.exception("Error generando alertas: %s", exc)
            return {"vigentes": 0, "creadas": 0, "cerradas": 0}

    @staticmethod
    def _reconciliar_lote(legajo_ids):
        """Reconcilia un lote de legajos con un número **fijo** de consultas.

        Cuatro lecturas (inscripciones del lote, legajos con sus dos agregados,
        alertas activas y —solo si hay algo que crear— los ciudadanos), más un
        ``INSERT`` por alta y un único ``UPDATE`` de cierre.
        """
        vacio = {"vigentes": 0, "creadas": 0, "cerradas": 0}
        if not legajo_ids:
            return vacio

        ciudadano_por_legajo = {}
        programas_por_legajo = defaultdict(set)
        for legajo_id, ciudadano_id, programa_id in get_vinculos_de_legajos(legajo_ids):
            # Orden ascendente: el último que se escribe es la inscripción más reciente,
            # que es el ciudadano que resuelve `LegajoAtencion.ciudadano`.
            ciudadano_por_legajo[legajo_id] = ciudadano_id
            if programa_id is not None:
                programas_por_legajo[legajo_id].add(programa_id)

        vigentes = {}
        for legajo in AlertasService._legajos_con_sus_insumos(legajo_ids):
            if ciudadano_por_legajo.get(legajo.pk) is None:
                continue
            for tipo, prioridad, mensaje in AlertasService._reglas_vigentes(
                legajo,
                ultimo_contacto=legajo.ultimo_contacto,
                contactos_fallidos=legajo.contactos_fallidos,
            ):
                vigentes[(legajo.pk, tipo)] = (legajo, prioridad, mensaje)

        activas = list(
            AlertaCiudadano.objects.filter(activa=True, legajo_id__in=legajo_ids).values_list(
                "id", "legajo_id", "tipo", "prioridad"
            )
        )
        existentes = {(legajo_id, tipo) for _, legajo_id, tipo, _ in activas}

        creadas = AlertasService._crear_las_que_faltan(
            [(clave, datos) for clave, datos in vigentes.items() if clave not in existentes],
            ciudadano_por_legajo,
            programas_por_legajo,
        )
        cerradas = AlertasService._cerrar_las_que_ya_no_aplican(activas, vigentes)
        return {"vigentes": len(vigentes), "creadas": creadas, "cerradas": cerradas}

    @staticmethod
    def _legajos_con_sus_insumos(legajo_ids):
        """Los legajos del lote con lo que las reglas necesitan, en **una** consulta.

        Los dos insumos que antes costaban dos consultas por legajo —el último contacto
        y los fallidos del último mes— vienen anotados sobre el mismo ``JOIN``. El
        ``fecha_contacto__gte`` compara la columna contra un parámetro: no hay ninguna
        función sobre la columna, que es lo que MariaDB no puede resolver por índice.
        """
        hace_30 = timezone.now() - timedelta(days=30)
        return LegajoAtencion.objects.filter(pk__in=legajo_ids).annotate(
            ultimo_contacto=Max("historial_contactos__fecha_contacto"),
            contactos_fallidos=Count(
                "historial_contactos",
                filter=Q(
                    historial_contactos__estado="NO_CONTESTA",
                    historial_contactos__fecha_contacto__gte=hace_30,
                ),
            ),
        )

    @staticmethod
    def _crear_las_que_faltan(a_crear, ciudadano_por_legajo, programas_por_legajo):
        """Da de alta las alertas vigentes que todavía no existen y las notifica.

        Las altas van de a una y no con ``bulk_create``: en MySQL 8 —icore— el
        ``bulk_create`` no devuelve el ``pk``, y el aviso por WebSocket lo necesita
        (el dashboard dibuja ``data-alerta-id`` y el cierre se entrega por ese id).
        En régimen son cero: la reconciliación solo crea lo que cambió.
        """
        if not a_crear:
            return 0
        ciudadanos = Ciudadano.objects.in_bulk({ciudadano_por_legajo[legajo_id] for (legajo_id, _), _ in a_crear})
        creadas = 0
        for (legajo_id, tipo), (legajo, prioridad, mensaje) in a_crear:
            ciudadano = ciudadanos.get(ciudadano_por_legajo[legajo_id])
            if ciudadano is None:
                continue
            alerta = AlertaCiudadano.objects.create(
                ciudadano=ciudadano,
                legajo=legajo,
                tipo=tipo,
                prioridad=prioridad,
                mensaje=mensaje,
            )
            # El ruteo ya está resuelto para todo el lote: pasarlo evita la consulta por
            # alerta que `_ruteo_de` haría (Cambio 179 lo dejó fuera del payload a
            # propósito, así que acá solo se lo precalcula).
            AlertasService._enviar_notificacion_alerta(
                alerta,
                ruteo={
                    "responsable_id": legajo.responsable_id,
                    "programa_ids": sorted(programas_por_legajo.get(legajo_id, ())),
                },
            )
            creadas += 1
        return creadas

    @staticmethod
    def _cerrar_las_que_ya_no_aplican(activas, vigentes):
        """Cierra las MEDIA/BAJA del lote cuyo ``(legajo, tipo)`` dejó de estar vigente.

        Con ``fecha_cierre`` y ``cerrada_por=None``: el ``update(activa=False)`` masivo
        de antes dejaba la fila apagada sin decir cuándo ni por qué, y como volvía a
        crearse en la misma pasada el resultado era una fila nueva por hora y un aviso
        por WebSocket por hora (LEG-01).

        Lo que **no** toca: las alertas sin legajo —las de conversaciones, incluida
        ``MENSAJE_CIUDADANO``— y las ALTA/CRÍTICA, que las cierra una persona.
        """
        a_cerrar = [
            alerta_id
            for alerta_id, legajo_id, tipo, prioridad in activas
            if prioridad in PRIORIDADES_RECONCILIADAS
            and tipo != TIPO_DE_CONVERSACIONES
            and (legajo_id, tipo) not in vigentes
        ]
        if not a_cerrar:
            return 0
        ahora = timezone.now()
        return AlertaCiudadano.objects.filter(id__in=a_cerrar).update(
            activa=False,
            fecha_cierre=ahora,
            cerrada_por=None,
            modificado=ahora,
        )

    @staticmethod
    def generar_alertas_legajo(legajo):
        """Regenera solo las alertas del legajo dado (para la señal post_save)."""
        try:
            return AlertasService._generar_alertas_legajo(legajo)
        except Exception as exc:
            logger.exception("Error generando alertas del legajo: %s", exc)
            return []

    @staticmethod
    def _generar_alertas_legajo(legajo):
        """Genera las alertas vigentes de un legajo (camino de la señal ``post_save``).

        Lee sus dos insumos de a uno porque viene con un solo legajo en la mano; la
        pasada periódica los trae anotados por lote. Las **reglas** son las mismas
        (:meth:`_reglas_vigentes`): escritas dos veces se desincronizaban al primer
        umbral que cambiara.
        """
        ciudadano = legajo.ciudadano
        if not ciudadano:
            return []

        ultimo = HistorialContacto.objects.filter(legajo=legajo).order_by("-fecha_contacto").first()
        contactos_fallidos = HistorialContacto.objects.filter(
            legajo=legajo,
            estado="NO_CONTESTA",
            fecha_contacto__gte=timezone.now() - timedelta(days=30),
        ).count()

        return [
            AlertasService._crear_alerta(ciudadano, legajo, tipo, prioridad, mensaje)
            for tipo, prioridad, mensaje in AlertasService._reglas_vigentes(
                legajo,
                ultimo_contacto=ultimo.fecha_contacto if ultimo else None,
                contactos_fallidos=contactos_fallidos,
            )
        ]

    @staticmethod
    def _reglas_vigentes(legajo, *, ultimo_contacto, contactos_fallidos):
        """``[(tipo, prioridad, mensaje)]`` de las alertas que le corresponden al legajo.

        **No toca la base**: recibe los dos insumos que dependen del historial de
        contactos (``ultimo_contacto`` es un ``datetime`` o ``None``). Es la única
        definición de los umbrales, compartida por la señal y por la pasada periódica.
        """
        reglas = []

        if legajo.nivel_riesgo == "ALTO":
            reglas.append(("RIESGO_ALTO", "ALTA", "Legajo con nivel de riesgo alto"))

        evaluacion = getattr(legajo, "evaluacion", None)
        if not evaluacion:
            dias_sin_eval = (timezone.localdate() - legajo.fecha_apertura).days
            if dias_sin_eval > 15:
                reglas.append(("SIN_EVALUACION", "MEDIA", f"Sin evaluación inicial hace {dias_sin_eval} días"))

        if legajo.estado in ["ABIERTO", "EN_SEGUIMIENTO"] and not legajo.plan_vigente:
            reglas.append(("SIN_PLAN", "MEDIA", "Legajo activo sin plan de intervención"))

        if ultimo_contacto:
            dias_sin_contacto = (timezone.localdate() - fecha_local(ultimo_contacto)).days
            if dias_sin_contacto > 30:
                reglas.append(("SIN_CONTACTO", "ALTA", f"Sin contacto hace {dias_sin_contacto} días"))

        if contactos_fallidos >= 3:
            reglas.append(("CONTACTOS_FALLIDOS", "MEDIA", f"{contactos_fallidos} contactos fallidos en el último mes"))

        return reglas

    @staticmethod
    def _crear_alerta(ciudadano, legajo, tipo, prioridad, mensaje):
        """Crea una alerta si no existe una similar activa."""
        alerta_existente = AlertaCiudadano.objects.filter(
            ciudadano=ciudadano,
            legajo=legajo,
            tipo=tipo,
            activa=True,
        ).first()

        if not alerta_existente:
            alerta = AlertaCiudadano.objects.create(
                ciudadano=ciudadano,
                legajo=legajo,
                tipo=tipo,
                prioridad=prioridad,
                mensaje=mensaje,
            )
            AlertasService._enviar_notificacion_alerta(alerta)
            return alerta

        return alerta_existente

    @staticmethod
    def _ruteo_de(legajo_id, responsable_id):
        """Datos **de servidor** para que el consumer decida el alcance sin consultar.

        El grupo `alertas_sistema` es uno solo y el filtro por alcance va en la
        entrega. Resolverlo ahí costaba cinco consultas por alerta **y por
        socket** —tres ``IN`` anidados sobre las 40k inscripciones—, y la pasada
        horaria de ``generar_alertas`` redifunde todo de una: con el
        ``read_timeout`` de 10 s de ECOM eso es una cola. Acá se resuelve **una
        vez por alerta**, del lado del emisor, y el consumer compara contra el
        alcance que tiene cacheado (`AlertasConsumer`).

        Viaja en el evento aparte de ``alerta``: nunca se le manda al cliente.
        """
        if legajo_id is None:
            return {"responsable_id": None, "programa_ids": []}
        return {
            "responsable_id": responsable_id,
            "programa_ids": sorted(set(get_programa_ids_for_legajo_ids([legajo_id]))),
        }

    @staticmethod
    def _enviar_notificacion_alerta(alerta, ruteo=None):
        """Envía notificación WebSocket para nueva alerta.

        ``ruteo`` se pasa ya resuelto cuando quien llama lo calculó para todo un lote
        (la pasada periódica): así el alcance se resuelve una vez por lote en vez de
        una vez por alerta. Sin él se resuelve acá, como siempre.
        """
        try:
            channel_layer = get_channel_layer()

            alerta_data = {
                "id": alerta.id,
                "ciudadano": alerta.ciudadano.nombre_completo,
                "ciudadano_id": alerta.ciudadano.id,
                "tipo": alerta.tipo,
                "prioridad": alerta.prioridad,
                "mensaje": alerta.mensaje,
                "fecha": alerta.creado.strftime("%d/%m/%Y %H:%M"),
                # `LegajoAtencion.id` es un UUID y el consumer serializa el
                # evento con `json.dumps`: sin `str()` reventaba con
                # «Object of type UUID is not JSON serializable» —y reventaba
                # justo en las alertas que **sí** cuelgan de un legajo, que son
                # las únicas que caen dentro del alcance de alguien (G1c-04)—.
                # El error moría en el log del consumer, así que la difusión
                # parecía andar.
                "legajo_id": str(alerta.legajo.id) if alerta.legajo else None,
            }

            # **Un** `group_send` por alerta, también para las CRÍTICAS. G1c-17
            # había arreglado la rama crítica —mandaba al grupo `alertas_criticas`
            # con el tipo `nueva_alerta_critica`, que no existen en ningún
            # consumer, y por eso el modal nunca se disparaba— pero la dejó como un
            # **segundo** mensaje sobre el mismo grupo: la crítica llegaba dos
            # veces, el cliente mostraba toast *y* modal, el sonido sonaba dos
            # veces y el contador se refrescaba dos veces. La prioridad ya viaja en
            # el payload: la forma del aviso la decide el cliente.
            async_to_sync(channel_layer.group_send)(
                "alertas_sistema",
                {
                    "type": "nueva_alerta",
                    "alerta": alerta_data,
                    "ruteo": ruteo
                    if ruteo is not None
                    else AlertasService._ruteo_de(alerta.legajo_id, getattr(alerta.legajo, "responsable_id", None)),
                },
            )
        except Exception as exc:
            logger.exception("Error enviando notificación WebSocket: %s", exc)

    @staticmethod
    def _enviar_cierre_alerta(alerta):
        """Avisa por WS que una alerta se cerró, para sacarla del dashboard abierto.

        El handler `alerta_cerrada` del consumer existía desde el principio **sin
        un solo productor**, así que nunca podía llegar: la tarjeta de la alerta
        que otro acababa de cerrar se quedaba en pantalla hasta recargar. Y
        resolver su alcance con ``obtener_alertas_usuario`` —que filtra
        ``activa=True``— era imposible por construcción, porque para cuando se
        emite el cierre la alerta ya está en ``activa=False``. El ruteo del
        emisor no mira ``activa``, así que el cierre se entrega al mismo conjunto
        de sockets que recibió el alta.
        """
        try:
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                "alertas_sistema",
                {
                    "type": "alerta_cerrada",
                    "alerta_id": alerta.id,
                    "ruteo": AlertasService._ruteo_de(alerta.legajo_id, getattr(alerta.legajo, "responsable_id", None)),
                },
            )
        except Exception as exc:
            logger.exception("Error enviando el cierre de alerta por WebSocket: %s", exc)

    @staticmethod
    def obtener_alertas_ciudadano(ciudadano_id):
        """Obtiene alertas activas de un ciudadano."""
        return (
            AlertaCiudadano.objects.filter(
                ciudadano_id=ciudadano_id,
                activa=True,
            )
            .select_related("legajo")
            .order_by("-prioridad", "-creado")
        )

    @staticmethod
    def cerrar_alerta(alerta_id, usuario=None):
        """Cierra una alerta **del alcance del usuario**.

        Antes resolvía ``AlertaCiudadano.objects.get(id=alerta_id)`` sobre toda
        la tabla: con `n = 1..N` cualquier cuenta de backoffice silenciaba las
        alertas de todo el sistema (SEC-18, auditoría oct-2026). Ahora la busca
        dentro de ``FiltrosUsuarioService.obtener_alertas_usuario``, el mismo
        alcance con el que el usuario las ve; fuera de ahí devuelve ``False``.

        Un ``alerta_id`` que no es un entero (el `pk` crudo de una ruta de DRF)
        levantaba ``ValueError`` y la vista contestaba **500**: acá también es
        ``False``.
        """
        from .filtros_usuario import FiltrosUsuarioService

        if usuario is None:
            return False
        try:
            # `select_related("legajo")`: el aviso de cierre por WS necesita el
            # `responsable_id` del legajo y así no cuesta una consulta extra.
            alerta = FiltrosUsuarioService.obtener_alertas_usuario(usuario).select_related("legajo").get(id=alerta_id)
        except (AlertaCiudadano.DoesNotExist, ValueError, TypeError, ValidationError):
            return False

        alerta.activa = False
        alerta.fecha_cierre = timezone.now()
        alerta.cerrada_por = usuario
        alerta.save()
        AlertasService._enviar_cierre_alerta(alerta)
        return True

    @staticmethod
    def generar_alerta_mensaje_ciudadano(conversacion):
        """Genera alerta cuando un ciudadano envía un mensaje."""
        if not conversacion or not hasattr(conversacion, "ciudadano"):
            return None

        return AlertasService._crear_alerta(
            conversacion.ciudadano,
            None,
            "MENSAJE_CIUDADANO",
            "MEDIA",
            "Nuevo mensaje del ciudadano en conversación",
        )

    @staticmethod
    def generar_alerta_seguimiento_vencido(seguimiento):
        """Genera alerta por seguimiento vencido."""
        if not seguimiento or not seguimiento.legajo:
            return None

        ciudadano = seguimiento.legajo.ciudadano
        if not ciudadano:
            return None

        return AlertasService._crear_alerta(
            ciudadano,
            seguimiento.legajo,
            "SEGUIMIENTO_VENCIDO",
            "ALTA",
            "Seguimiento con fecha vencida",
        )

    @staticmethod
    def generar_alerta_evento_critico(legajo, tipo_evento, descripcion):
        """Genera alerta por evento crítico."""
        if not legajo:
            return None

        ciudadano = legajo.ciudadano
        if not ciudadano:
            return None

        return AlertasService._crear_alerta(
            ciudadano,
            legajo,
            tipo_evento,
            "CRITICA",
            descripcion,
        )
