"""Circuito masivo de Becas: validar en SIIS, aprobar e informar el alta.

Es el mismo camino que los botones de la pantalla de revisión, caso por caso.
Vive acá —y no dentro del comando— porque lo usan dos disparadores: el comando
``procesar_casos_siis`` y la pantalla del proceso masivo. Una segunda
implementación se habría desincronizado con la primera regla que cambiara.
"""

import threading
from dataclasses import dataclass, field

from django.core.exceptions import ValidationError
from django.db import connection
from django.db.models import OuterRef, Q, Subquery
from django.utils import timezone

from programas.models import CorridaSiis, EnvioSIIS, Formulario, ValidacionSIS
from programas.services.avisos_resolucion import enviar_aviso_resolucion
from programas.services.cupo import aprobar_o_poner_en_espera
from programas.services.siis_envio import (
    CatalogoNoDisponible,
    Catalogos,
    armar_payload,
    enviar_beneficiario_a_siis,
)
from programas.services.validacion_siis import validar_formulario_en_siis

LOTE = 40
MAX_ERRORES = 10

# Contadores que viajan de ``Cuenta`` a ``CorridaSiis`` con el mismo nombre.
CONTADORES = ("mirados", "elegidos", "aprobados", "lista_espera", "altas", "incompletos", "rechazados", "errores")


@dataclass
class Cuenta:
    """Los desenlaces de una corrida. Se acumulan y se vuelcan a ``CorridaSiis``."""

    mirados: int = 0
    elegidos: int = 0
    aprobados: int = 0
    lista_espera: int = 0
    no_aprobable: int = 0
    sin_datos: int = 0
    error_validacion: int = 0
    altas: int = 0
    incompletos: int = 0
    rechazados: int = 0
    errores: int = 0
    descartados: dict = field(default_factory=dict)


def candidatos(*, programa=None, convocatoria=None, relevamiento=None, segmento=None, solo_enviar=False):
    """Casos que todavía no se informaron a SIIS.

    Los ``ENVIADO`` (pendientes de resolución) y los ya ``APROBADO`` sin alta,
    para que una corrida cortada se retome sola. Se saltean los que tienen un
    conflicto de carga duplicada sin resolver: eso lo decide una persona, igual
    que en la pantalla de revisión.
    """
    ultimo = EnvioSIIS.objects.filter(formulario=OuterRef("pk")).order_by("-creado", "-id").values("estado")[:1]
    casos = (
        Formulario.objects.select_related(
            "ciudadano", "relevamiento__convocatoria__segmento__programa", "apoderado_ciudadano"
        )
        .annotate(ultimo_envio=Subquery(ultimo))
        # «Todavía no informado» incluye a los que no tienen ningún envío, y eso
        # es NULL: un ``exclude`` los descartaría a todos, porque
        # ``NOT (NULL = 'ENVIADO')`` no es verdadero.
        .filter(Q(ultimo_envio__isnull=True) | ~Q(ultimo_envio=EnvioSIIS.Estado.ENVIADO))
        .order_by("pk")
    )
    estados = [Formulario.Estado.APROBADO]
    if not solo_enviar:
        estados.append(Formulario.Estado.ENVIADO)
    casos = casos.filter(estado__in=estados)
    if programa is not None:
        casos = casos.filter(relevamiento__convocatoria__segmento__programa=programa)
    if convocatoria is not None:
        casos = casos.filter(relevamiento__convocatoria_id=convocatoria)
    if relevamiento is not None:
        casos = casos.filter(relevamiento_id=relevamiento)
    if segmento is not None:
        casos = casos.filter(relevamiento__convocatoria__segmento_id=segmento)
    casos = casos.exclude(Q(conflicto_duplicado=True) & Q(conflicto_resuelto=False)).exclude(
        cargas_en_conflicto__conflicto_resuelto=False
    )
    return casos.distinct()


def elegir_completos(casos, catalogos, total, cuenta):
    """``(elegidos, descartados_por_campo)``: los que hoy saldrían sin faltantes.

    El total cuenta casos que se **mandan**, no casos que se miran: se recorre
    hasta juntarlos, salteando sin tocar a los que les falta un dato. Mandar uno
    incompleto no lo informa a SIIS pero igual lo deja aprobado y con una fila de
    error para revisar a mano.
    """
    elegidos, descartados = [], {}
    for caso in casos:
        if len(elegidos) >= total:
            break
        cuenta.mirados += 1
        _, faltantes = armar_payload(caso, catalogos=catalogos)
        if faltantes:
            for campo in faltantes:
                descartados[campo] = descartados.get(campo, 0) + 1
            continue
        elegidos.append(caso)
        cuenta.elegidos += 1
    cuenta.descartados = descartados
    return elegidos, descartados


def procesar_caso(caso, responsable, catalogos, cuenta, *, avisar=False, solo_enviar=False):
    """Valida, aprueba e informa un caso. Devuelve ``"tecnico"`` si falló SIIS.

    Un caso que falla en un paso no avanza al siguiente y no interrumpe al resto.
    """
    if not solo_enviar:
        try:
            validacion = validar_formulario_en_siis(caso, responsable)
        except ValueError:
            # Sin programa SIIS o sin DNI: no hay consulta posible.
            cuenta.sin_datos += 1
            return None
        if validacion.estado == ValidacionSIS.Estado.ERROR:
            cuenta.error_validacion += 1
            return "tecnico"

        if caso.estado == Formulario.Estado.ENVIADO:
            try:
                resultado = aprobar_o_poner_en_espera(caso, responsable)
            except ValidationError:
                # Falta algo que la aprobación exige (identidad, validación que
                # no corresponde al programa actual…).
                cuenta.no_aprobable += 1
                return None
            if resultado == "lista_espera":
                # Sin cupo no hay beneficiario que informar.
                cuenta.lista_espera += 1
                if avisar:
                    enviar_aviso_resolucion(caso, resultado)
                return None
            cuenta.aprobados += 1
            if avisar:
                enviar_aviso_resolucion(caso, resultado)

    envio = enviar_beneficiario_a_siis(caso, responsable, catalogos=catalogos)
    if envio.estado == EnvioSIIS.Estado.ENVIADO:
        cuenta.altas += 1
    elif envio.estado == EnvioSIIS.Estado.INCOMPLETO:
        cuenta.incompletos += 1
    elif envio.estado == EnvioSIIS.Estado.RECHAZADO:
        cuenta.rechazados += 1
    else:
        cuenta.errores += 1
        return "tecnico"
    return None


# ---------------------------------------------------------------------------
# Corrida
# ---------------------------------------------------------------------------
def _lotes(lista, tamano):
    for inicio in range(0, len(lista), tamano):
        yield lista[inicio : inicio + tamano]


def _guardar(corrida, cuenta, **extra):
    """Vuelca los contadores y el latido. Cada lote deja su rastro en la base.

    Escribe **solo** los campos que toca. Un ``save()`` completo pisaría
    ``cancelacion_pedida`` con el valor que este proceso tiene en memoria, y
    quien apretó Frenar lo escribió desde otro request: el freno se perdería en
    el siguiente latido.
    """
    for campo in CONTADORES:
        setattr(corrida, campo, getattr(cuenta, campo))
    corrida.latido = timezone.now()
    for campo, valor in extra.items():
        setattr(corrida, campo, valor)
    corrida.save(update_fields=[*CONTADORES, "latido", *extra.keys(), "modificado"])


def correr(corrida, *, responsable=None, catalogos=None, lote=LOTE, max_errores=MAX_ERRORES):
    """Ejecuta la corrida y va escribiendo su avance. **Nunca lanza.**

    Todo desenlace —incluida una excepción que no previmos— queda escrito en la
    corrida. Corre en un hilo: si dejara escapar una excepción, nadie la vería y
    la pantalla quedaría con una corrida «en curso» para siempre.

    No hay una transacción que envuelva todo a propósito. Cada caso se confirma
    solo; eso es lo que permite cortar y retomar, y lo que evita el cuelgue de
    una transacción larga contra una base remota.
    """
    catalogos = catalogos or Catalogos()
    cuenta = Cuenta()
    responsable = responsable or corrida.solicitada_por
    try:
        pendientes = list(candidatos(programa=corrida.programa))
        casos, _ = elegir_completos(pendientes, catalogos, corrida.total_pedido, cuenta)
        _guardar(corrida, cuenta)

        seguidos = 0
        for grupo in _lotes(casos, max(1, lote)):
            for caso in grupo:
                if procesar_caso(caso, responsable, catalogos, cuenta) == "tecnico":
                    seguidos += 1
                else:
                    seguidos = 0
            _guardar(corrida, cuenta)
            if seguidos >= max_errores:
                _guardar(
                    corrida,
                    cuenta,
                    estado=CorridaSiis.Estado.DETENIDA,
                    finalizada=timezone.now(),
                    mensaje=(
                        f"Se detuvo tras {max_errores} errores técnicos seguidos: SIIS no está respondiendo "
                        "o las credenciales no sirven. Lo hecho quedó; volvé a lanzarla cuando se recupere."
                    ),
                )
                return corrida
            # El freno se relee de la base: lo marca otro request.
            corrida.refresh_from_db(fields=["cancelacion_pedida"])
            if corrida.cancelacion_pedida:
                _guardar(
                    corrida,
                    cuenta,
                    estado=CorridaSiis.Estado.CANCELADA,
                    finalizada=timezone.now(),
                    mensaje="La frenaron desde la pantalla. Lo procesado quedó firme.",
                )
                return corrida

        _guardar(corrida, cuenta, estado=CorridaSiis.Estado.TERMINADA, finalizada=timezone.now())
        return corrida
    except CatalogoNoDisponible as exc:
        _guardar(
            corrida,
            cuenta,
            estado=CorridaSiis.Estado.DETENIDA,
            finalizada=timezone.now(),
            mensaje=f"No se pudo leer un catálogo de SIIS: {exc}",
        )
        return corrida
    except Exception as exc:  # noqa: BLE001 - la corrida es el único lugar donde se puede informar
        _guardar(
            corrida,
            cuenta,
            estado=CorridaSiis.Estado.DETENIDA,
            finalizada=timezone.now(),
            mensaje=f"Error no previsto: {exc}",
        )
        return corrida


def _en_un_hilo(funcion):
    threading.Thread(target=funcion, daemon=True).start()


def lanzar(corrida, *, responsable=None, ejecutor=None):
    """Arranca la corrida sin hacer esperar al request.

    ``ejecutor`` se inyecta para poder correr sincrónico en los tests: con el
    hilo de verdad, las pruebas serían una carrera.
    """

    def trabajo():
        try:
            correr(corrida, responsable=responsable)
        finally:
            # Django abre una conexión por hilo; sin esto queda colgada.
            connection.close()

    (ejecutor or _en_un_hilo)(trabajo)
