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

**Freno de seguridad.** Tras ``--max-errores`` errores técnicos **seguidos** (10
por defecto) se detiene: es señal de que SIIS está caído o las credenciales no
sirven, no de que los casos tengan un problema.

Corre en seco por defecto: sin ``--aplicar`` solo cuenta e informa.

    python manage.py enviar_casos_siis                          # cuántos hay
    python manage.py enviar_casos_siis --aplicar
    python manage.py enviar_casos_siis --aplicar --pausa 2 --convocatoria 12
    python manage.py enviar_casos_siis --estados APROBADO,ENVIADO --si-entiendo --aplicar

Necesita ``SIIS_API_URL``, ``SIIS_API_CLIENT_ID`` y ``SIIS_API_CLIENT_SECRET``
del ambiente contra el que se corre.
"""

import time

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db.models import OuterRef, Q, Subquery

from programas.models import EnvioSIIS, Formulario
from programas.services import proceso_masivo
from programas.services.siis_envio import Catalogos, enviar_beneficiario_a_siis

ESTADOS_ENVIO = (
    EnvioSIIS.Estado.ENVIADO,
    EnvioSIIS.Estado.INCOMPLETO,
    EnvioSIIS.Estado.RECHAZADO,
    EnvioSIIS.Estado.ERROR,
)
# Estados de DATAÑACH que no son una aprobación: informarlos a SIIS registra como
# beneficiario a alguien que nadie revisó, o que la provincia resolvió que no.
ESTADOS_SENSIBLES = (Formulario.Estado.ENVIADO, Formulario.Estado.RECHAZADO, Formulario.Estado.BAJA)


def _lotes(lista, tamano):
    for inicio in range(0, len(lista), tamano):
        yield inicio // tamano + 1, lista[inicio : inicio + tamano]


class Command(BaseCommand):
    help = "Da de alta en SIIS, por lotes, los casos de Becas que todavía no fueron informados."

    def add_arguments(self, parser):
        parser.add_argument("--aplicar", action="store_true", help="Llama a SIIS. Sin esto solo cuenta e informa.")
        parser.add_argument("--lote", type=int, default=50, help="Casos por lote. Por defecto 50.")
        parser.add_argument("--pausa", type=float, default=0.0, help="Segundos de espera entre lotes. Por defecto 0.")
        parser.add_argument(
            "--max-errores",
            type=int,
            default=10,
            help="Errores técnicos seguidos que detienen la corrida. Por defecto 10.",
        )
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
        parser.add_argument(
            "--usuario",
            default=None,
            help="Nombre de usuario que queda como solicitante. Por defecto ninguno (envío automático).",
        )

    def _log(self, texto="", estilo=None):
        self.stdout.write(estilo(texto) if estilo else texto)
        self.stdout.flush()

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
        casos = Formulario.objects.annotate(ultimo_envio=Subquery(ultimo)).filter(estado__in=estados).order_by("pk")
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

    def _solicitante(self, nombre):
        if not nombre:
            return None
        usuario = get_user_model().objects.filter(username=nombre).first()
        if usuario is None:
            raise CommandError(f"No existe el usuario «{nombre}».")
        return usuario

    # ── Orquestación ────────────────────────────────────────────────────────

    def handle(self, *args, **options):
        aplicar = options["aplicar"]
        tamano = max(1, options["lote"])
        max_errores = max(1, options["max_errores"])
        arranque = time.monotonic()

        estados, sensibles = self._estados_pedidos(options)

        if not aplicar:
            self._log("ENSAYO: no se llama a SIIS. Agregá --aplicar para enviar de verdad.\n", self.style.WARNING)
        self._log(f"SIIS: {settings.SIIS_API_URL}")
        if aplicar and not (settings.SIIS_API_CLIENT_ID and settings.SIIS_API_CLIENT_SECRET):
            raise CommandError("Faltan SIIS_API_CLIENT_ID / SIIS_API_CLIENT_SECRET en el entorno.")

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
        seguidos = 0
        detenido = False
        catalogos = Catalogos()

        self._log("")
        for numero, lote in _lotes(casos, tamano):
            parcial = {estado: 0 for estado in ESTADOS_ENVIO}
            # El lote se trae completo recién acá, con las relaciones que lee el
            # armado del payload; el resumen de arriba no las necesitaba.
            for caso in proceso_masivo.hidratar([pk for pk, _, _ in lote]):
                # La guarda del servicio se levanta solo si de verdad se pidieron
                # estados que no son aprobación: --si-entiendo solo no alcanza.
                envio = enviar_beneficiario_a_siis(
                    caso, solicitante, catalogos=catalogos, exigir_aprobado=not sensibles
                )
                cuenta[envio.estado] += 1
                parcial[envio.estado] += 1
                if envio.estado == EnvioSIIS.Estado.ERROR:
                    seguidos += 1
                    if seguidos >= max_errores:
                        detenido = True
                        break
                else:
                    seguidos = 0
            self._log(
                f"   lote {numero:>4}/{total_lotes} · casos {lote[0][0]}-{lote[-1][0]} · "
                f"enviados {parcial['ENVIADO']:>3} · incompletos {parcial['INCOMPLETO']:>3} · "
                f"rechazados {parcial['RECHAZADO']:>3} · errores {parcial['ERROR']:>3} · "
                f"acumulado {sum(cuenta.values()):>5} · {time.monotonic() - arranque:6.1f} s"
            )
            if detenido:
                break
            if options["pausa"] and numero < total_lotes:
                time.sleep(options["pausa"])

        self._log("")
        self._log("Resumen", self.style.MIGRATE_HEADING)
        self._log(f"   {'altas hechas (ENVIADO)':40} {cuenta['ENVIADO']:6}")
        self._log(f"   {'les falta un dato (INCOMPLETO)':40} {cuenta['INCOMPLETO']:6}")
        self._log(f"   {'rechazados por SIIS (RECHAZADO)':40} {cuenta['RECHAZADO']:6}")
        self._log(f"   {'errores técnicos (ERROR)':40} {cuenta['ERROR']:6}")
        segundos = time.monotonic() - arranque
        if detenido:
            self._log(
                f"\nDETENIDO tras {max_errores} errores técnicos seguidos en {segundos:.0f} s: "
                "SIIS no está respondiendo o las credenciales no sirven. Revisá el servicio y volvé a correr; "
                "los que quedaron en ERROR se retoman solos porque siguen contando como pendientes.",
                self.style.ERROR,
            )
            raise SystemExit(1)
        if cuenta[EnvioSIIS.Estado.INCOMPLETO]:
            self._log(
                "\nLos INCOMPLETO no llegaron a SIIS: les falta un dato del payload. El detalle por campo está "
                "en cada EnvioSIIS y en la pantalla del caso, en «Envío a SIIS».",
                self.style.WARNING,
            )
        self._log(f"\nListo en {segundos:.0f} s.", self.style.SUCCESS)
