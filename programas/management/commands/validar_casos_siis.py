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

from django.db.models import OuterRef, Q, Subquery

from programas.management.commands._base_siis import ComandoSiisBase
from programas.models import Formulario, ValidacionSIS
from programas.services import proceso_masivo
from programas.services.validacion_siis import validar_formulario_en_siis

ESTADOS = (ValidacionSIS.Estado.OK, ValidacionSIS.Estado.RECHAZADO, ValidacionSIS.Estado.ERROR)


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
        ultima = ValidacionSIS.objects.filter(formulario=OuterRef("pk")).order_by("-creado", "-id").values("estado")[:1]
        casos = (
            Formulario.objects.select_related("ciudadano", "relevamiento__convocatoria__segmento__programa")
            .annotate(ultima_validacion=Subquery(ultima))
            .order_by("pk")
        )
        if options["convocatoria"]:
            casos = casos.filter(relevamiento__convocatoria_id=options["convocatoria"])
        if not options["incluir_rechazados"]:
            casos = casos.exclude(estado=Formulario.Estado.RECHAZADO)
        if not options["todos"]:
            # «Sin validación» es NULL en la subconsulta, y NULL no entra en un IN.
            pendientes = Q(ultima_validacion__isnull=True)
            if options["reintentar_errores"]:
                pendientes |= Q(ultima_validacion=ValidacionSIS.Estado.ERROR)
            casos = casos.filter(pendientes)
        if options["limite"]:
            casos = casos[: options["limite"]]
        return list(casos)

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
        casos = self._casos(options)

        total_casos = Formulario.objects.count()
        con_validacion = ValidacionSIS.objects.values("formulario_id").distinct().count()
        self._log(f"Casos en total: {total_casos} · con alguna validación: {con_validacion}")
        if not casos:
            self._log("No hay casos que validar con los criterios pedidos.", self.style.SUCCESS)
            return
        total_lotes = (len(casos) + tamano - 1) // tamano
        criterio = (
            "todos"
            if options["todos"]
            else "sin validación" + (" o con ERROR técnico" if options["reintentar_errores"] else "")
        )
        self._log(f"A validar ({criterio}): {len(casos)} casos en {total_lotes} lotes de {tamano}")
        sin_programa = sum(1 for c in casos if c.relevamiento.convocatoria.segmento.programa_id is None)
        sin_dni = sum(1 for c in casos if c.ciudadano is None or not c.ciudadano.dni)
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
        for numero, lote in self._lotes(casos, tamano):
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
                f"   lote {numero:>4}/{total_lotes} · casos {lote[0].pk}-{lote[-1].pk} · "
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
