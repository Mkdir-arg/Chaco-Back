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

**Freno de seguridad.** Se detiene tras ``--max-errores`` errores técnicos
**seguidos** (10 por defecto) o ``--max-inciertos`` resultados de resultado
desconocido seguidos (3 por defecto). El segundo tope es más bajo a propósito: un
error técnico deja el caso libre y se reintenta solo, mientras que un resultado
incierto lo deja **tomado** hasta que alguien le pregunte a ECOM si el alta
llegó. Las dos rachas se cuentan en paralelo: una falla de un tipo no borra la
del otro.

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

from django.core.management.base import CommandError

from programas.management.commands._base_siis import ComandoSiisBase
from programas.models import AltaIntermediaSIIS, Formulario
from programas.services import proceso_masivo
from programas.services.siis_envio import (
    DESTINO_SIIS,
    DESTINO_TABLA,
    DESTINOS,
    CatalogoNoDisponible,
    Catalogos,
    sincronizar_tabla_intermedia,
)

TOTAL_POR_DEFECTO = 1000
LOTE_POR_DEFECTO = proceso_masivo.LOTE


class Command(ComandoSiisBase):
    help = "Valida en SIIS, aprueba e informa el alta de los casos de Becas, en lotes."

    lote_por_defecto = LOTE_POR_DEFECTO

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--total", type=int, default=TOTAL_POR_DEFECTO, help=f"Casos a procesar. Por defecto {TOTAL_POR_DEFECTO}."
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
            "--sin-filtro-materias",
            action="store_true",
            help=(
                "Ignora la tabla aprobados_materias y considera a todos los casos. Por defecto a SIIS solo van "
                "los DNI que figuran en esa tabla, y si la tabla no existe el comando no corre."
            ),
        )
        parser.add_argument(
            "--solo-enviar",
            action="store_true",
            help="Salta validación y aprobación: solo informa el alta de los ya aprobados.",
        )
        parser.add_argument(
            "--destino",
            choices=list(DESTINOS),
            default=DESTINO_SIIS,
            help=(
                "A dónde va el alta. «siis» la manda a la API (por defecto). «tabla» la guarda en la "
                "tabla intermedia de este lado, sin llamar a SIIS, para revisarla o entregarla. "
                "Con «siis» se manda primero lo que haya quedado en esa tabla."
            ),
        )
        parser.add_argument("--convocatoria", type=int, default=None, help="Acota a una convocatoria por id.")
        parser.add_argument("--relevamiento", type=int, default=None, help="Acota a un relevamiento por id.")
        parser.add_argument("--segmento", type=int, default=None, help="Acota a un segmento por id.")

    # ── Orquestación ────────────────────────────────────────────────────────

    def _vaciar_tabla_intermedia(self, responsable, aplicar):
        """Manda a SIIS lo que haya quedado guardado de este lado.

        Va antes de elegir candidatos: así las que se sincronizan dejan su
        ``EnvioSIIS`` y no vuelven a entrar como casos nuevos en la misma
        corrida. Sin esto, un alta guardada con ``--destino tabla`` se quedaría
        ahí para siempre, que es justo lo que no puede pasar.
        """
        pendientes = AltaIntermediaSIIS.objects.filter(sincronizado=False).count()
        if not pendientes:
            return
        self._log(f"Tabla intermedia: {pendientes} alta(s) guardada(s) sin informar. Van primero.")
        if not aplicar:
            self._log("   (ensayo: no se manda ninguna)", self.style.WARNING)
            return
        cuenta = sincronizar_tabla_intermedia(responsable)
        self._log(
            f"   informadas {cuenta['altas']} · rechazadas {cuenta['rechazadas']} · errores {cuenta['errores']} · "
            f"cambiaron de estado {cuenta['no_aprobables']}"
        )
        if cuenta["no_aprobables"]:
            self._log(
                f"   {cuenta['no_aprobables']} alta(s) guardada(s) ya no corresponden a un caso aprobado: "
                "quedan en la tabla para que alguien decida si se regeneran o se descartan.",
                self.style.WARNING,
            )
        self._log("")

    def handle(self, *args, **options):
        aplicar = options["aplicar"]
        tamano = max(1, options["lote"])
        arranque = self._reloj()

        self._avisar_ensayo(aplicar, "no valida, no aprueba y no envía. Agregá --aplicar.")
        # --solo-completos lee los catálogos de SIIS aunque sea un ensayo.
        if aplicar or options["solo_completos"]:
            self._exigir_credenciales()

        responsable = self._responsable(options["usuario"])
        if aplicar and responsable is None and not options["solo_enviar"]:
            self._log(
                "   Sin --usuario, la traza de las aprobaciones queda sin responsable.",
                self.style.WARNING,
            )
        catalogos = Catalogos()
        cuenta = proceso_masivo.Cuenta()
        destino = options["destino"]
        if destino == DESTINO_TABLA:
            self._log(
                "Destino: la tabla intermedia de este lado. NO se llama a SIIS.\n"
                "   Para mandarlas de verdad, volvé a correr con --destino siis.",
                self.style.WARNING,
            )
        else:
            self._vaciar_tabla_intermedia(responsable, aplicar)
        filtros = {
            "convocatoria": options["convocatoria"],
            "relevamiento": options["relevamiento"],
            "segmento": options["segmento"],
            "solo_enviar": options["solo_enviar"],
            # Sin esto, con destino tabla cada vuelta vuelve a agarrar los mismos
            # candidatos --guardarlos no deja ``EnvioSIIS``-- y los pisa: la tabla
            # se queda clavada en el tamaño de la primera tanda.
            "destino": destino,
        }
        filtrar_materias = not options["sin_filtro_materias"]
        try:
            consulta = proceso_masivo.candidatos(filtrar_materias=filtrar_materias, **filtros)
            if filtrar_materias:
                # Solo se informa el tamaño de la tabla, que ya está en memoria por
                # el filtro. Antes se contaban los candidatos con y sin filtro para
                # decir cuántos quedaban afuera, pero cada ``count()`` sobre este
                # queryset --con ``distinct()`` y una subconsulta correlacionada--
                # Django lo envuelve en un SELECT COUNT(*) FROM (SELECT DISTINCT …),
                # y contra la base de ECOM eso no entra en su ``read_timeout`` de
                # 10 s: el comando moria antes de empezar. Cuántos quedan afuera se
                # deduce igual comparando con «Candidatos pendientes».
                habilitados = len(proceso_masivo.dnis_aprobados_materias())
                self._log(
                    f"Filtro por {proceso_masivo.TABLA_APROBADOS_MATERIAS}: "
                    f"solo entran los casos cuyo DNI figure ahí ({habilitados} DNI cargados)."
                )
            else:
                self._log("SIN filtro por aprobados_materias: se consideran todos los casos.", self.style.WARNING)
        except proceso_masivo.TablaAprobadosMateriasFaltante as exc:
            raise CommandError(str(exc)) from exc
        total = max(1, options["total"])
        if options["solo_completos"]:
            # Primero los ids; los casos se traen de a lotes mientras se eligen
            # (ver ``proceso_masivo.hidratar_por_lotes``): traerlos todos con su
            # JSON en una consulta no entra en el ``read_timeout`` de ECOM.
            ids = proceso_masivo.ids_de(consulta)
            self._log(f"Candidatos pendientes: {len(ids)}. Armando el payload de cada uno…")
            try:
                casos, descartados = proceso_masivo.elegir_completos(
                    proceso_masivo.hidratar_por_lotes(ids), catalogos, total, cuenta
                )
            except CatalogoNoDisponible as exc:
                raise CommandError(f"No se pudo leer un catálogo de SIIS: {exc}") from exc
        else:
            # Los ids primero y después los casos por pk: pedirle a MySQL los
            # primeros ``total`` candidatos completos lo hacía materializar los
            # 20.000 con su JSON antes de cortar (de 1,3 a 4,4 s en el banco
            # según la corrida; así, unos 0,4 s).
            casos, descartados = proceso_masivo.hidratar(proceso_masivo.ids_de(consulta, limite=total)), {}
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

        freno = self._crear_freno(options)
        detenido = False

        self._log("")
        for numero, lote in self._lotes(casos, tamano):
            antes = replace(cuenta)
            for caso in lote:
                resultado = proceso_masivo.procesar_caso(
                    caso,
                    responsable,
                    catalogos,
                    cuenta,
                    avisar=options["avisar"],
                    solo_enviar=options["solo_enviar"],
                    destino=destino,
                )
                if freno.registrar(resultado):
                    detenido = True
                    break
            self._log(
                f"   lote {numero:>3}/{total_lotes} · casos {lote[0].pk}-{lote[-1].pk} · "
                f"aprobados {cuenta.aprobados - antes.aprobados:>3} · "
                f"altas {cuenta.altas - antes.altas:>3} · "
                f"incompletos {cuenta.incompletos - antes.incompletos:>3} · "
                f"errores {cuenta.errores - antes.errores:>3} · "
                f"{self._reloj() - arranque:6.1f} s"
            )
            if detenido:
                break
            if options["pausa"] and numero < total_lotes:
                time.sleep(options["pausa"])

        filas = [
            ("aprobados", cuenta.aprobados),
            ("sin cupo → lista de espera", cuenta.lista_espera),
            ("no se pudieron aprobar", cuenta.no_aprobable),
            ("sin programa SIIS o sin DNI", cuenta.sin_datos),
            ("validación con error técnico", cuenta.error_validacion),
            ("altas hechas en SIIS", cuenta.altas),
            ("altas con datos incompletos", cuenta.incompletos),
            ("altas rechazadas por SIIS", cuenta.rechazados),
            ("altas con error técnico", cuenta.errores),
            ("altas de resultado desconocido", cuenta.inciertos),
            ("ya informados en otro caso (duplicado)", cuenta.duplicados),
            ("ya los tenía otro camino", cuenta.ocupados),
        ]
        if cuenta.guardadas:
            filas.append(("guardadas en la tabla intermedia", cuenta.guardadas))
        self._resumen(filas, ancho=38)
        segundos = self._reloj() - arranque
        if detenido:
            self._cortado_por_fallas(
                freno,
                segundos,
                "Volvé a correrlo cuando se recupere; lo hecho queda y los pendientes se retoman solos.",
            )
        if cuenta.incompletos:
            self._log(
                f"\n{cuenta.incompletos} altas quedaron INCOMPLETO: les falta un dato del "
                "payload y **no llegaron a SIIS**. El detalle por campo está en cada EnvioSIIS y en la pantalla "
                "del caso, en «Envío a SIIS». Esos casos ya quedaron aprobados.",
                self.style.WARNING,
            )
        self._log(f"\nListo en {segundos:.0f} s.", self.style.SUCCESS)
