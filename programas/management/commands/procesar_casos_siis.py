"""Corre el circuito completo de un caso de Becas: validar en SIIS, aprobar e
informar el alta. Caso por caso, en lotes, igual que lo haría el revisor.

Es la versión automática de los dos botones de la pantalla de revisión:

1. **Validar con SIIS** — ``validar_formulario_en_siis``. Deja siempre una fila
   auditable en ``ValidacionSIS``. Desde el Cambio 81 el veredicto no frena la
   aprobación, pero haberla hecho sigue siendo obligatorio.
2. **Aprobar** — ``aprobar_o_poner_en_espera``. Solo toma casos ``ENVIADO``. Si
   el segmento no tiene cupo, el caso cae en **lista de espera** y ahí termina:
   no se informa a SIIS.
3. **Enviar a SIIS** — ``enviar_beneficiario_a_siis``, con los identificadores
   configurados (Cambio 82). Deja una fila en ``EnvioSIIS``.

Un caso que falla en un paso no avanza al siguiente y no interrumpe al resto.

**El correo al ciudadano va apagado.** La pantalla avisa la resolución por mail
(Cambio 44); acá no, porque una corrida de mil casos son mil correos y no hay
forma de retractarlos. ``--avisar`` lo prende a propósito.

**Qué casos toma.** Los ``ENVIADO`` (pendientes de resolución) y los ya
``APROBADO`` que todavía no tienen un alta ``ENVIADO`` en SIIS, para que una
corrida cortada se retome sola. Se saltean los que tienen un conflicto de carga
duplicada sin resolver: eso lo decide una persona.

**``--solo-completos``.** Arma el payload de cada candidato y se queda solo con
los que hoy saldrían **sin faltantes**. Es la diferencia entre «los primeros
1000 pendientes» y «los primeros 1000 que SIIS va a aceptar»: un caso incompleto
no llega a SIIS, pero igual queda aprobado y con una fila de error para revisar a
mano. El descarte no toca el caso y el ensayo informa por qué campo se cayó cada
uno.

**Freno de seguridad.** Tras ``--max-errores``  errores técnicos **seguidos** (10
por defecto) se detiene: es señal de que SIIS está caído, no de que los casos
tengan un problema.

Corre en seco por defecto: sin ``--aplicar`` no valida, no aprueba y no envía.

    python manage.py procesar_casos_siis                        # qué haría
    python manage.py procesar_casos_siis --aplicar
    python manage.py procesar_casos_siis --aplicar --pausa 2 --convocatoria 12
    python manage.py procesar_casos_siis --solo-completos --total 1000 --lote 40

Necesita ``SIIS_API_URL``, ``SIIS_API_CLIENT_ID`` y ``SIIS_API_CLIENT_SECRET``
del ambiente contra el que se corre.
"""

import time
from dataclasses import replace

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from programas.models import Formulario
from programas.services import proceso_masivo
from programas.services.siis_envio import CatalogoNoDisponible, Catalogos

TOTAL_POR_DEFECTO = 1000
LOTE_POR_DEFECTO = proceso_masivo.LOTE


def _lotes(lista, tamano):
    for inicio in range(0, len(lista), tamano):
        yield inicio // tamano + 1, lista[inicio : inicio + tamano]


class Command(BaseCommand):
    help = "Valida en SIIS, aprueba e informa el alta de los casos de Becas, en lotes."

    def add_arguments(self, parser):
        parser.add_argument("--aplicar", action="store_true", help="Ejecuta. Sin esto solo cuenta e informa.")
        parser.add_argument(
            "--total", type=int, default=TOTAL_POR_DEFECTO, help=f"Casos a procesar. Por defecto {TOTAL_POR_DEFECTO}."
        )
        parser.add_argument(
            "--lote", type=int, default=LOTE_POR_DEFECTO, help=f"Casos por lote. Por defecto {LOTE_POR_DEFECTO}."
        )
        parser.add_argument("--pausa", type=float, default=0.0, help="Segundos de espera entre lotes. Por defecto 0.")
        parser.add_argument(
            "--max-errores",
            type=int,
            default=10,
            help="Errores técnicos seguidos que detienen la corrida. Por defecto 10.",
        )
        parser.add_argument(
            "--avisar",
            action="store_true",
            help="Manda el correo de resolución al ciudadano. Apagado por defecto: son mil correos irretractables.",
        )
        parser.add_argument(
            "--solo-completos",
            action="store_true",
            help="Solo procesa los casos cuyo payload hoy sale sin faltantes. Descarta el resto sin tocarlos.",
        )
        parser.add_argument(
            "--solo-enviar",
            action="store_true",
            help="Salta validación y aprobación: solo informa el alta de los ya aprobados.",
        )
        parser.add_argument("--convocatoria", type=int, default=None, help="Acota a una convocatoria por id.")
        parser.add_argument("--relevamiento", type=int, default=None, help="Acota a un relevamiento por id.")
        parser.add_argument("--segmento", type=int, default=None, help="Acota a un segmento por id.")
        parser.add_argument(
            "--usuario",
            default=None,
            help="Usuario que queda como responsable en la traza y en los registros. Recomendado.",
        )

    def _log(self, texto="", estilo=None):
        self.stdout.write(estilo(texto) if estilo else texto)
        self.stdout.flush()

    # ── Selección ───────────────────────────────────────────────────────────

    def _responsable(self, nombre):
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

        if not aplicar:
            self._log("ENSAYO: no valida, no aprueba y no envía. Agregá --aplicar.\n", self.style.WARNING)
        self._log(f"SIIS: {settings.SIIS_API_URL}")
        # --solo-completos lee los catálogos de SIIS aunque sea un ensayo.
        if (aplicar or options["solo_completos"]) and not (
            settings.SIIS_API_CLIENT_ID and settings.SIIS_API_CLIENT_SECRET
        ):
            raise CommandError("Faltan SIIS_API_CLIENT_ID / SIIS_API_CLIENT_SECRET en el entorno.")

        responsable = self._responsable(options["usuario"])
        if aplicar and responsable is None and not options["solo_enviar"]:
            self._log(
                "   Sin --usuario, la traza de las aprobaciones queda sin responsable.",
                self.style.WARNING,
            )
        catalogos = Catalogos()
        cuenta = proceso_masivo.Cuenta()
        consulta = proceso_masivo.candidatos(
            convocatoria=options["convocatoria"],
            relevamiento=options["relevamiento"],
            segmento=options["segmento"],
            solo_enviar=options["solo_enviar"],
        )
        total = max(1, options["total"])
        if options["solo_completos"]:
            pendientes = list(consulta)
            self._log(f"Candidatos pendientes: {len(pendientes)}. Armando el payload de cada uno…")
            try:
                casos, descartados = proceso_masivo.elegir_completos(pendientes, catalogos, total, cuenta)
            except CatalogoNoDisponible as exc:
                raise CommandError(f"No se pudo leer un catálogo de SIIS: {exc}") from exc
        else:
            casos, descartados = list(consulta[:total]), {}
        if descartados:
            total_descartados = sum(descartados.values())
            self._log(f"Descartados por datos incompletos: {total_descartados} (no se tocan)")
            for campo, n in sorted(descartados.items(), key=lambda kv: -kv[1])[:5]:
                self._log(f"   {campo:20} {n:6}")
        if not casos:
            self._log("No hay casos que procesar con los criterios pedidos.", self.style.SUCCESS)
            return

        total_lotes = (len(casos) + tamano - 1) // tamano
        pasos = "enviar" if options["solo_enviar"] else "validar → aprobar → enviar"
        self._log(f"Pasos: {pasos}")
        self._log(f"A procesar: {len(casos)} casos en {total_lotes} lotes de {tamano}")
        por_estado = {}
        for caso in casos:
            por_estado[caso.estado] = por_estado.get(caso.estado, 0) + 1
        self._log("   " + " · ".join(f"{n} {estado}" for estado, n in sorted(por_estado.items())))
        if options["avisar"]:
            self._log(
                f"   --avisar está prendido: se mandan hasta {por_estado.get(Formulario.Estado.ENVIADO, 0)} "
                "correos a ciudadanos y no se pueden retractar.",
                self.style.WARNING,
            )
        if not aplicar:
            self._log("\nEnsayo terminado, no se tocó nada.", self.style.WARNING)
            return

        seguidos = 0
        detenido = False

        self._log("")
        for numero, lote in _lotes(casos, tamano):
            antes = replace(cuenta)
            for caso in lote:
                resultado = proceso_masivo.procesar_caso(
                    caso,
                    responsable,
                    catalogos,
                    cuenta,
                    avisar=options["avisar"],
                    solo_enviar=options["solo_enviar"],
                )
                if resultado == "tecnico":
                    seguidos += 1
                    if seguidos >= max_errores:
                        detenido = True
                        break
                else:
                    seguidos = 0
            self._log(
                f"   lote {numero:>3}/{total_lotes} · casos {lote[0].pk}-{lote[-1].pk} · "
                f"aprobados {cuenta.aprobados - antes.aprobados:>3} · "
                f"altas {cuenta.altas - antes.altas:>3} · "
                f"incompletos {cuenta.incompletos - antes.incompletos:>3} · "
                f"errores {cuenta.errores - antes.errores:>3} · "
                f"{time.monotonic() - arranque:6.1f} s"
            )
            if detenido:
                break
            if options["pausa"] and numero < total_lotes:
                time.sleep(options["pausa"])

        self._log("")
        self._log("Resumen", self.style.MIGRATE_HEADING)
        self._log(f"   {'aprobados':38} {cuenta.aprobados:6}")
        self._log(f"   {'sin cupo → lista de espera':38} {cuenta.lista_espera:6}")
        self._log(f"   {'no se pudieron aprobar':38} {cuenta.no_aprobable:6}")
        self._log(f"   {'sin programa SIIS o sin DNI':38} {cuenta.sin_datos:6}")
        self._log(f"   {'validación con error técnico':38} {cuenta.error_validacion:6}")
        self._log(f"   {'altas hechas en SIIS':38} {cuenta.altas:6}")
        self._log(f"   {'altas con datos incompletos':38} {cuenta.incompletos:6}")
        self._log(f"   {'altas rechazadas por SIIS':38} {cuenta.rechazados:6}")
        self._log(f"   {'altas con error técnico':38} {cuenta.errores:6}")
        segundos = time.monotonic() - arranque
        if detenido:
            self._log(
                f"\nDETENIDO tras {max_errores} errores técnicos seguidos en {segundos:.0f} s: "
                "SIIS no está respondiendo o las credenciales no sirven. Volvé a correrlo cuando se recupere; "
                "lo hecho queda y los pendientes se retoman solos.",
                self.style.ERROR,
            )
            raise SystemExit(1)
        if cuenta.incompletos:
            self._log(
                f"\n{cuenta.incompletos} altas quedaron INCOMPLETO: les falta un dato del "
                "payload y **no llegaron a SIIS**. El detalle por campo está en cada EnvioSIIS y en la pantalla "
                "del caso, en «Envío a SIIS». Esos casos ya quedaron aprobados.",
                self.style.WARNING,
            )
        self._log(f"\nListo en {segundos:.0f} s.", self.style.SUCCESS)
