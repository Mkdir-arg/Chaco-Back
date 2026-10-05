"""Da de alta en SIIS, por lotes y de forma automática, los casos de Becas.

Hace exactamente lo mismo que el botón «Enviar a SIIS» de la revisión
(``enviar_beneficiario_a_siis``), caso por caso: arma el payload con los
identificadores configurados —corrección del caso, después el segmento, después
el programa (Cambio 82)— y **siempre** deja una fila auditable en ``EnvioSIIS``
con el resultado (``ENVIADO``, ``INCOMPLETO``, ``RECHAZADO`` o ``ERROR``).

**Qué casos toma.** Por defecto, los ``APROBADO`` que todavía no tienen un envío
``ENVIADO``: los que nunca se mandaron, los que quedaron ``INCOMPLETO`` (por si
se completaron los datos) y los que fallaron por ``ERROR`` técnico. Los que SIIS
ya rechazó se saltean salvo ``--reintentar-rechazados``, porque repetirlos sin
corregir nada solo genera el mismo rechazo.

**Estados de DATAÑACH.** ``--estados`` decide cuáles se informan; el default es
``APROBADO``. Los otros hay que nombrarlos:

* ``ENVIADO`` es un caso **que nadie revisó todavía**.
* ``RECHAZADO`` y ``BAJA`` son casos que la provincia resolvió que no.

Informar cualquiera de esos lo registra como beneficiario en SIIS. La API no
deduplica y desde acá no hay forma de dar de baja lo que se mandó: se arregla
del lado de SIIS, a mano. Por eso, además de nombrar el estado, hace falta
``--si-entiendo``.

**Cómo avanza.** En lotes (50 por defecto, ``--lote``) con una línea de log por
lote y una pausa opcional (``--pausa``). Cada envío queda confirmado al instante:
si se corta, lo hecho queda y volver a correrlo continúa por donde iba, porque
los ``ENVIADO`` no se vuelven a mandar.

**Freno de seguridad.** Se detiene tras ``--max-errores`` errores técnicos
**seguidos** (10 por defecto) o ``--max-inciertos`` resultados de resultado
desconocido seguidos (3 por defecto). El segundo tope es más bajo a propósito: un
error técnico deja el caso libre y se reintenta solo, mientras que un resultado
incierto lo deja **tomado** hasta que alguien le pregunte a ECOM si el alta
llegó. Las dos rachas se cuentan en paralelo: una falla de un tipo no borra la
del otro.

Corre en seco por defecto: sin ``--aplicar`` solo cuenta e informa.

    python manage.py enviar_casos_siis                          # cuántos hay
    python manage.py enviar_casos_siis --aplicar
    python manage.py enviar_casos_siis --aplicar --pausa 2 --convocatoria 12
    python manage.py enviar_casos_siis --estados APROBADO,ENVIADO --si-entiendo --aplicar

Necesita ``SIIS_API_URL``, ``SIIS_API_CLIENT_ID`` y ``SIIS_API_CLIENT_SECRET``
del ambiente contra el que se corre.
"""

import time

from django.core.management.base import CommandError
from django.db.models import Exists, OuterRef, Q, Subquery

from programas.management.commands._base_siis import ComandoSiisBase
from programas.models import EnvioSIIS, Formulario
from programas.services import proceso_masivo
from programas.services.siis_envio import Catalogos, enviar_beneficiario_a_siis

ESTADOS_ENVIO = (
    EnvioSIIS.Estado.ENVIADO,
    EnvioSIIS.Estado.INCOMPLETO,
    EnvioSIIS.Estado.RECHAZADO,
    EnvioSIIS.Estado.ERROR,
    # Los devuelve el servicio cuando el caso ya está tomado por otro camino:
    # son desenlaces posibles de cada llamada, aunque no se elijan nunca acá.
    EnvioSIIS.Estado.EN_PROCESO,
    EnvioSIIS.Estado.INCIERTO,
)
# Estados de DATAÑACH que no son una aprobación: informarlos a SIIS registra como
# beneficiario a alguien que nadie revisó, o que la provincia resolvió que no.
ESTADOS_SENSIBLES = (Formulario.Estado.ENVIADO, Formulario.Estado.RECHAZADO, Formulario.Estado.BAJA)


def _desenlace(envio):
    """Lo que el envío le dice al freno sobre el estado de SIIS.

    Un ``INCIERTO`` que acaba de intentarse es una falla —y de las caras—; uno
    que ya estaba, no: ahí no se llamó a SIIS.
    """
    if envio.estado == EnvioSIIS.Estado.ERROR:
        return proceso_masivo.FALLA_TECNICA
    if envio.estado == EnvioSIIS.Estado.INCIERTO and envio.recien_intentado:
        return proceso_masivo.FALLA_INCIERTA
    return None


class Command(ComandoSiisBase):
    help = "Da de alta en SIIS, por lotes, los casos de Becas que todavía no fueron informados."

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--estados",
            default=str(Formulario.Estado.APROBADO),
            help=(
                "Estados de DATAÑACH a informar, separados por coma. Por defecto APROBADO. "
                "Nombrar ENVIADO, RECHAZADO o BAJA exige además --si-entiendo."
            ),
        )
        parser.add_argument(
            "--si-entiendo",
            action="store_true",
            help="Confirma que se informan casos sin aprobar. SIIS no deduplica ni permite dar de baja desde acá.",
        )
        parser.add_argument(
            "--sin-filtro-materias",
            action="store_true",
            help=(
                "Ignora la tabla aprobados_materias y considera a todos los casos. Por defecto a SIIS solo van "
                "los DNI que figuran en esa tabla, y si la tabla no existe el comando no corre."
            ),
        )
        parser.add_argument(
            "--reintentar-rechazados",
            action="store_true",
            help="Incluye los casos que SIIS ya rechazó (por defecto se saltean).",
        )
        parser.add_argument("--limite", type=int, default=0, help="Procesa como mucho N casos. 0 = todos.")
        parser.add_argument("--convocatoria", type=int, default=None, help="Acota a una convocatoria por id.")
        parser.add_argument("--relevamiento", type=int, default=None, help="Acota a un relevamiento por id.")
        parser.add_argument("--segmento", type=int, default=None, help="Acota a un segmento por id.")
        parser.add_argument("--programa", type=int, default=None, help="Acota a un programa SIIS por id interno.")

    # ── Selección ───────────────────────────────────────────────────────────

    def _estados_pedidos(self, options):
        crudos = [e.strip().upper() for e in str(options["estados"]).split(",") if e.strip()]
        validos = {e.value for e in Formulario.Estado}
        desconocidos = [e for e in crudos if e not in validos]
        if desconocidos:
            raise CommandError(
                f"Estado(s) inexistente(s): {', '.join(desconocidos)}. Los válidos son {', '.join(sorted(validos))}."
            )
        if not crudos:
            raise CommandError("--estados no puede quedar vacío.")
        sensibles = [e for e in crudos if e in ESTADOS_SENSIBLES]
        if sensibles and not options["si_entiendo"]:
            raise CommandError(
                f"Pediste informar casos en {', '.join(sensibles)}. "
                "ENVIADO es un caso que nadie revisó; RECHAZADO y BAJA los resolvió la provincia que no. "
                "Informarlos los registra como beneficiarios en SIIS: la API no deduplica y desde acá no se "
                "puede dar de baja lo mandado. Si es lo que querés, agregá --si-entiendo."
            )
        return crudos, sensibles

    def _casos(self, options, estados):
        """``[(pk, estado, programa_id), ...]`` de los casos a informar, en orden de pk.

        Solo lo que el resumen necesita: los casos completos se traen de a lotes
        recién al procesarlos (``proceso_masivo.hidratar``). Traerlos todos acá
        --8.900 aprobados con ``data``, ``respuestas`` y ``definicion``-- eran
        5 s en el banco y contra la base de ECOM no entra en su ``read_timeout``
        de 10 s; los ids con estado y programa vuelven en 30 ms.
        """
        ultimo = EnvioSIIS.objects.filter(formulario=OuterRef("pk")).order_by("-creado", "-id").values("estado")[:1]
        vigente = EnvioSIIS.objects.filter(formulario=OuterRef("pk"), vigente=True)
        casos = (
            Formulario.objects.annotate(ultimo_envio=Subquery(ultimo))
            .filter(estado__in=estados)
            # SIIS-01: un caso con envío vigente (informado, en vuelo o incierto)
            # no vuelve a salir por ninguna vía.
            .filter(~Exists(vigente))
            .order_by("pk")
        )
        if options["convocatoria"]:
            casos = casos.filter(relevamiento__convocatoria_id=options["convocatoria"])
        if options["relevamiento"]:
            casos = casos.filter(relevamiento_id=options["relevamiento"])
        if options["segmento"]:
            casos = casos.filter(relevamiento__convocatoria__segmento_id=options["segmento"])
        if options["programa"]:
            casos = casos.filter(relevamiento__convocatoria__segmento__programa_id=options["programa"])
        # Pendiente es: sin envío (NULL, que no entra en un IN) o con un último
        # intento que todavía se puede repetir.
        repetibles = [EnvioSIIS.Estado.INCOMPLETO, EnvioSIIS.Estado.ERROR]
        if options["reintentar_rechazados"]:
            repetibles.append(EnvioSIIS.Estado.RECHAZADO)
        casos = casos.filter(Q(ultimo_envio__isnull=True) | Q(ultimo_envio__in=repetibles))
        # Cambio 90: a SIIS solo van los DNI de aprobados_materias. Cualquier
        # camino que llegue a SIIS respeta la misma regla; este es uno de ellos.
        if not options["sin_filtro_materias"]:
            casos = casos.filter(ciudadano__dni__in=proceso_masivo.dnis_aprobados_materias())
        casos = casos.values_list("pk", "estado", "relevamiento__convocatoria__segmento__programa_id")
        if options["limite"]:
            casos = casos[: options["limite"]]
        return list(casos)

    # ── Orquestación ────────────────────────────────────────────────────────

    def handle(self, *args, **options):
        aplicar = options["aplicar"]
        tamano = max(1, options["lote"])
        arranque = self._reloj()

        estados, sensibles = self._estados_pedidos(options)

        self._avisar_ensayo(aplicar, "no se llama a SIIS. Agregá --aplicar para enviar de verdad.")
        if aplicar:
            self._exigir_credenciales()

        solicitante = self._solicitante(options["usuario"])
        try:
            casos = self._casos(options, estados)
        except proceso_masivo.TablaAprobadosMateriasFaltante as exc:
            raise CommandError(str(exc)) from exc
        if options["sin_filtro_materias"]:
            self._log("SIN filtro por aprobados_materias: se consideran todos los casos.", self.style.WARNING)

        ya_enviados = (
            EnvioSIIS.objects.filter(estado=EnvioSIIS.Estado.ENVIADO).values("formulario_id").distinct().count()
        )
        self._log(f"Estados a informar: {', '.join(estados)}")
        self._log(f"Casos en total: {Formulario.objects.count()} · ya informados a SIIS: {ya_enviados}")
        if sensibles:
            self._log(
                f"   ATENCIÓN: {', '.join(sensibles)} no son aprobaciones. Lo que se mande queda "
                "registrado como beneficiario en SIIS y no se puede dar de baja desde acá.",
                self.style.WARNING,
            )
        if not casos:
            self._log("No hay casos que informar con los criterios pedidos.", self.style.SUCCESS)
            return

        total_lotes = (len(casos) + tamano - 1) // tamano
        self._log(f"A informar: {len(casos)} casos en {total_lotes} lotes de {tamano}")
        por_estado = {}
        for _, estado, _ in casos:
            por_estado[estado] = por_estado.get(estado, 0) + 1
        self._log("   " + " · ".join(f"{n} {estado}" for estado, n in sorted(por_estado.items())))
        sin_programa = sum(1 for _, _, programa_id in casos if programa_id is None)
        if sin_programa:
            self._log(
                f"   {sin_programa} sin programa SIIS en el segmento: van a quedar INCOMPLETO.", self.style.WARNING
            )
        if not aplicar:
            self._log("\nEnsayo terminado, no se llamó a SIIS.", self.style.WARNING)
            return

        cuenta = {estado: 0 for estado in ESTADOS_ENVIO}
        # Casos que cambiaron de estado entre el listado y su lote (SIIS-04).
        cambiados = 0
        freno = self._crear_freno(options)
        detenido = False
        catalogos = Catalogos()

        self._log("")
        for numero, lote in self._lotes(casos, tamano):
            parcial = {estado: 0 for estado in ESTADOS_ENVIO}
            # El lote se trae completo recién acá, con las relaciones que lee el
            # armado del payload; el resumen de arriba no las necesitaba.
            for caso in proceso_masivo.hidratar([pk for pk, _, _ in lote]):
                # La guarda del servicio se levanta solo si de verdad se pidieron
                # estados que no son aprobación: --si-entiendo solo no alcanza.
                # Con la guarda levantada igual se exige, bajo el lock, que el
                # estado releído siga entre los pedidos (SIIS-04, V2-NEW-06).
                try:
                    envio = enviar_beneficiario_a_siis(
                        caso,
                        solicitante,
                        catalogos=catalogos,
                        exigir_aprobado=not sensibles,
                        estados_permitidos=estados if sensibles else None,
                    )
                except ValueError:
                    cambiados += 1
                    continue
                cuenta[envio.estado] += 1
                parcial[envio.estado] += 1
                if freno.registrar(_desenlace(envio)):
                    detenido = True
                    break
            self._log(
                f"   lote {numero:>4}/{total_lotes} · casos {lote[0][0]}-{lote[-1][0]} · "
                f"enviados {parcial['ENVIADO']:>3} · incompletos {parcial['INCOMPLETO']:>3} · "
                f"rechazados {parcial['RECHAZADO']:>3} · errores {parcial['ERROR']:>3} · "
                f"acumulado {sum(cuenta.values()):>5} · {self._reloj() - arranque:6.1f} s"
            )
            if detenido:
                break
            if options["pausa"] and numero < total_lotes:
                time.sleep(options["pausa"])

        self._resumen(
            (
                ("altas hechas (ENVIADO)", cuenta[EnvioSIIS.Estado.ENVIADO]),
                ("les falta un dato (INCOMPLETO)", cuenta[EnvioSIIS.Estado.INCOMPLETO]),
                ("rechazados por SIIS (RECHAZADO)", cuenta[EnvioSIIS.Estado.RECHAZADO]),
                ("errores técnicos (ERROR)", cuenta[EnvioSIIS.Estado.ERROR]),
                ("de resultado desconocido (INCIERTO)", cuenta[EnvioSIIS.Estado.INCIERTO]),
                ("ya los tenía otro camino", cuenta[EnvioSIIS.Estado.EN_PROCESO]),
                ("cambiaron de estado y no se informaron", cambiados),
            )
        )
        segundos = self._reloj() - arranque
        if detenido:
            self._cortado_por_fallas(
                freno,
                segundos,
                "Revisá el servicio y volvé a correr; los que quedaron en ERROR se retoman solos porque "
                "siguen contando como pendientes.",
            )
        if cuenta[EnvioSIIS.Estado.INCOMPLETO]:
            self._log(
                "\nLos INCOMPLETO no llegaron a SIIS: les falta un dato del payload. El detalle por campo está "
                "en cada EnvioSIIS y en la pantalla del caso, en «Envío a SIIS».",
                self.style.WARNING,
            )
        self._log(f"\nListo en {segundos:.0f} s.", self.style.SUCCESS)
