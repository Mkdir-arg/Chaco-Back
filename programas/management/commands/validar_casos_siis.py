"""Valida contra SIIS, de forma automática y por lotes, los casos de Becas que
todavía no tienen una validación de compatibilidad.

Hace exactamente lo mismo que el botón «Validar con SIIS» de la revisión
(``validar_formulario_en_siis``), caso por caso: una consulta sincrónica al
servicio y **siempre** una fila auditable en ``ValidacionSIS`` con el veredicto
(``OK``, ``RECHAZADO`` o ``ERROR`` técnico). La pantalla de revisión toma como
vigente la última validación del caso, así que lo que este comando registra es
lo que el revisor ve al abrirlo. Aprobar un caso exige una validación previa
(Cambio 34), por eso conviene tenerlas hechas de antemano.

**Qué casos toma.** Por defecto, los que no tienen ninguna validación. Con
``--reintentar-errores`` suma los que quedaron en ``ERROR`` técnico en su último
intento. Con ``--todos`` revalida absolutamente todos, aunque ya tengan veredicto.
Los casos rechazados por el revisor se saltean salvo ``--incluir-rechazados``.

**Cómo avanza.** En lotes (50 por defecto, ``--lote``) con una línea de log por
lote y una pausa opcional entre lotes (``--pausa``) para no saturar a SIIS.
Cada consulta queda confirmada al instante: si se corta, lo hecho queda y volver
a correrlo continúa por donde iba, porque los ya validados no se vuelven a tocar.

**Freno de seguridad.** Si SIIS no responde, cada consulta deja una fila
``ERROR`` inútil. Tras ``--max-errores`` errores técnicos **seguidos** (10 por
defecto) el comando se detiene y lo dice: es señal de que el servicio está caído
o las credenciales no sirven, no de que los casos tengan un problema. (Acá
``--max-inciertos`` no se usa: una consulta de compatibilidad no deja nada del
otro lado, así que no hay resultado ambiguo que conciliar.)

Corre en seco por defecto: sin ``--aplicar`` solo cuenta e informa, no llama a SIIS.

    python manage.py validar_casos_siis                     # cuántos faltan
    python manage.py validar_casos_siis --aplicar
    python manage.py validar_casos_siis --aplicar --pausa 2 --reintentar-errores

Necesita ``SIIS_API_URL``, ``SIIS_API_CLIENT_ID`` y ``SIIS_API_CLIENT_SECRET`` del
ambiente contra el que se corre.
"""

import time

from django.db.models import OuterRef, Q, Subquery, Value
from django.db.models.functions import Coalesce

from programas.management.commands._base_siis import ComandoSiisBase
from programas.models import Formulario, ValidacionSIS
from programas.services import proceso_masivo
from programas.services.validacion_siis import validar_formulario_en_siis

ESTADOS = (ValidacionSIS.Estado.OK, ValidacionSIS.Estado.RECHAZADO, ValidacionSIS.Estado.ERROR)
#: El estado que toma un caso **sin** ninguna validación. ``ValidacionSIS.estado`` no
#: admite la cadena vacía (son tres choices), así que no se pisa con ningún veredicto
#: real: es solo la forma de que «no tiene» sea un valor y entre en el mismo ``IN``.
SIN_VALIDACION = ""


class Command(ComandoSiisBase):
    help = "Valida contra SIIS, por lotes, los casos de Becas que aún no tienen validación de compatibilidad."

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--reintentar-errores",
            action="store_true",
            help="Incluye los casos cuya última validación fue un ERROR técnico.",
        )
        parser.add_argument("--todos", action="store_true", help="Revalida todos los casos, tengan o no veredicto.")
        parser.add_argument(
            "--incluir-rechazados",
            action="store_true",
            help="Incluye los casos que el revisor ya rechazó (por defecto se saltean).",
        )
        parser.add_argument("--limite", type=int, default=0, help="Procesa como mucho N casos. 0 = todos.")
        parser.add_argument("--convocatoria", type=int, default=None, help="Acota a una convocatoria por id.")

    # ── Selección ───────────────────────────────────────────────────────────

    def _casos(self, options):
        """El queryset de los casos a validar, **sin** traerlos a memoria.

        PERF-06: devolvía ``list(casos)`` sin ``defer``, o sea todos los casos con sus
        cuatro JSON (unos 7 KB por caso) en una sola consulta. Con 20.000 casos eso no
        entra en el ``read_timeout`` de 10 s de ECOM. Quien llama se queda con los ids y
        los hidrata de a lotes.
        """
        # PERF-19: el ``Coalesce`` deja el filtro en **una** referencia a la subconsulta
        # correlacionada. Antes, «sin validación» era ``Q(isnull=True)`` y con
        # ``--reintentar-errores`` se le sumaba un segundo ``Q`` sobre la misma
        # anotación: Django escribía la subconsulta dos veces en el WHERE y MariaDB la
        # resolvía dos veces por fila. Con el NULL ya convertido a ``""``, el estado
        # «sin validación» es un valor más y entra en el mismo ``IN``.
        ultima = ValidacionSIS.objects.filter(formulario=OuterRef("pk")).order_by("-creado", "-id").values("estado")[:1]
        casos = (
            Formulario.objects.select_related("ciudadano", "relevamiento__convocatoria__segmento__programa")
            .annotate(ultima_validacion=Coalesce(Subquery(ultima), Value(SIN_VALIDACION)))
            .order_by("pk")
        )
        if options["convocatoria"]:
            casos = casos.filter(relevamiento__convocatoria_id=options["convocatoria"])
        if not options["incluir_rechazados"]:
            casos = casos.exclude(estado=Formulario.Estado.RECHAZADO)
        if not options["todos"]:
            pendientes = [SIN_VALIDACION]
            if options["reintentar_errores"]:
                pendientes.append(ValidacionSIS.Estado.ERROR)
            casos = casos.filter(ultima_validacion__in=pendientes)
        return casos

    # ── Orquestación ────────────────────────────────────────────────────────

    def handle(self, *args, **options):
        aplicar = options["aplicar"]
        tamano = max(1, options["lote"])
        arranque = self._reloj()

        # Valida contra SIIS caso por caso, igual que el masivo y con el mismo
        # freno: en paralelo se consultan los mismos casos dos veces (SIIS-03).
        self.exigir_sin_corrida_viva(options)
        self._avisar_ensayo(aplicar, "no se llama a SIIS. Agregá --aplicar para validar de verdad.")
        if aplicar:
            self._exigir_credenciales()

        solicitante = self._solicitante(options["usuario"])
        consulta = self._casos(options)
        # PERF-06: primero los ids —por rangos de pk, como el masivo— y después los
        # casos de a lotes. ``list(consulta)`` traía los 20.000 con sus cuatro JSON en
        # una sola consulta de decenas de MB.
        ids = proceso_masivo.ids_de(consulta, limite=options["limite"] or None)

        total_casos = Formulario.objects.count()
        con_validacion = ValidacionSIS.objects.values("formulario_id").distinct().count()
        self._log(f"Casos en total: {total_casos} · con alguna validación: {con_validacion}")
        if not ids:
            self._log("No hay casos que validar con los criterios pedidos.", self.style.SUCCESS)
            return
        total_lotes = (len(ids) + tamano - 1) // tamano
        criterio = (
            "todos"
            if options["todos"]
            else "sin validación" + (" o con ERROR técnico" if options["reintentar_errores"] else "")
        )
        self._log(f"A validar ({criterio}): {len(ids)} casos en {total_lotes} lotes de {tamano}")
        # Los dos salteos se cuentan en la base, no recorriendo los casos en memoria.
        # ``ids`` son los primeros ``--limite`` en orden de pk, así que acotar por el
        # último pk reproduce **exactamente** ese conjunto sin un ``IN`` de miles.
        acotada = consulta.filter(pk__lte=ids[-1]) if options["limite"] else consulta
        sin_programa = acotada.filter(relevamiento__convocatoria__segmento__programa__isnull=True).count()
        sin_dni = acotada.filter(Q(ciudadano__isnull=True) | Q(ciudadano__dni="")).count()
        if sin_programa or sin_dni:
            self._log(
                f"   se van a saltear: {sin_programa} sin programa SIIS en el segmento, {sin_dni} sin DNI",
                self.style.WARNING,
            )
        if not aplicar:
            self._log("\nEnsayo terminado, no se consultó a SIIS.", self.style.WARNING)
            return

        cuenta = {estado: 0 for estado in ESTADOS}
        cuenta.update(salteados=0)
        # Una consulta de compatibilidad no deja nada del otro lado: acá la
        # única racha posible es la de errores técnicos.
        freno = self._crear_freno(options)
        detenido = False

        self._log("")
        for numero, lote_ids in self._lotes(ids, tamano):
            # Sin los cuatro JSON del caso: la consulta de compatibilidad solo manda
            # DNI, programa y fecha de nacimiento (``validar_formulario_en_siis``).
            lote = proceso_masivo.hidratar(lote_ids, diferir=proceso_masivo.JSON_DEL_CASO)
            parcial = {estado: 0 for estado in ESTADOS}
            for caso in lote:
                try:
                    validacion = validar_formulario_en_siis(caso, solicitante)
                except ValueError:
                    # Sin programa SIIS o sin DNI: no hay consulta posible.
                    cuenta["salteados"] += 1
                    continue
                cuenta[validacion.estado] += 1
                parcial[validacion.estado] += 1
                falla = proceso_masivo.FALLA_TECNICA if validacion.estado == ValidacionSIS.Estado.ERROR else None
                if freno.registrar(falla):
                    detenido = True
                    break
            self._log(
                f"   lote {numero:>4}/{total_lotes} · casos {lote_ids[0]}-{lote_ids[-1]} · "
                f"OK {parcial['OK']:>3} · rechazados {parcial['RECHAZADO']:>3} · errores {parcial['ERROR']:>3} · "
                f"acumulado {sum(cuenta[e] for e in ESTADOS):>5} · {self._reloj() - arranque:6.1f} s"
            )
            if detenido:
                break
            if options["pausa"] and numero < total_lotes:
                time.sleep(options["pausa"])

        self._resumen(
            (
                ("compatibles (OK)", cuenta["OK"]),
                ("incompatibles (RECHAZADO)", cuenta["RECHAZADO"]),
                ("errores técnicos (ERROR)", cuenta["ERROR"]),
                ("salteados sin programa o sin DNI", cuenta["salteados"]),
            )
        )
        segundos = self._reloj() - arranque
        if detenido:
            self._cortado_por_fallas(
                freno,
                segundos,
                "Revisá el servicio y volvé a correr; los casos que quedaron en ERROR se retoman "
                "con --reintentar-errores.",
            )
        self._log(f"\nListo en {segundos:.0f} s.", self.style.SUCCESS)
