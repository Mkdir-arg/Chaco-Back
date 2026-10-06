"""Reintenta el alta en SIIS de los beneficiarios cuyo último envío fue un
error técnico **del que consta que el alta no salió** (fallo de conexión, 401,
503 del legacy). Los ``INCOMPLETO`` y ``RECHAZADO`` necesitan corrección humana y
no se tocan; los ``INCIERTO`` tampoco, porque el POST pudo haber llegado y el
alta no tiene baja: esos se liberan a mano con ``conciliar_envios_siis``.

Pensado para un cron o para correr a mano después de una caída del legacy de SIIS.

**Corre en seco por defecto**, como el resto de los comandos de SIIS: sin
``--aplicar`` lista lo que haría y no llama a nadie. ``--dry-run`` se mantiene
como alias del ensayo para los procedimientos que ya lo usaban.

**Freno de seguridad**, el mismo que las otras tres vías: corta tras
``--max-errores`` errores técnicos seguidos (10) o ``--max-inciertos`` envíos
seguidos sin saber si el alta llegó (3).

    python manage.py reenviar_siis_pendientes              # qué reintentaría
    python manage.py reenviar_siis_pendientes --aplicar
"""

from django.db.models import Exists, OuterRef, Subquery

from programas.management.commands._base_siis import ComandoSiisBase
from programas.models import EnvioSIIS, Formulario
from programas.services import proceso_masivo
from programas.services.siis_envio import Catalogos, enviar_beneficiario_a_siis


class Command(ComandoSiisBase):
    help = "Reintenta los envíos a SIIS que fallaron por error técnico."

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument("--limite", type=int, default=200, help="Máximo de casos por corrida. Por defecto 200.")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Alias histórico del ensayo. Hoy el ensayo ya es el default: sin --aplicar no se manda nada.",
        )

    def _casos(self, limite):
        # ``-id`` desempata dos intentos del mismo segundo (V2-NEW-04): sin él,
        # cuál es «el último» depende del orden físico de la tabla.
        ultimo = EnvioSIIS.objects.filter(formulario=OuterRef("pk")).order_by("-creado", "-id").values("estado")[:1]
        vigente = EnvioSIIS.objects.filter(formulario=OuterRef("pk"), vigente=True)
        casos = (
            Formulario.objects.filter(estado=Formulario.Estado.APROBADO)
            .annotate(ultimo_estado=Subquery(ultimo))
            .filter(ultimo_estado=EnvioSIIS.Estado.ERROR)
            # SIIS-01: nada con envío vigente vuelve a salir, por ninguna vía.
            .filter(~Exists(vigente))
            .select_related("ciudadano", "relevamiento__convocatoria__segmento__programa")
            .order_by("pk")
        )
        agotados = proceso_masivo.casos_con_errores_agotados()
        if agotados:
            casos = casos.exclude(pk__in=agotados)
        return list(casos[:limite]), agotados

    def handle(self, *args, **options):
        aplicar = options["aplicar"] and not options["dry_run"]
        self.exigir_sin_corrida_viva({**options, "aplicar": aplicar})
        casos, agotados = self._casos(options["limite"])
        if agotados:
            self._log(
                f"{len(agotados)} caso(s) con {proceso_masivo.MAX_REINTENTOS} o más errores técnicos quedan "
                "afuera: necesitan que alguien los mire. Ids: "
                + ", ".join(str(pk) for pk in agotados[:20])
                + ("…" if len(agotados) > 20 else ""),
                self.style.WARNING,
            )
        if not casos:
            self._log("Sin envíos pendientes de reintento.")
            return
        if not aplicar:
            for caso in casos:
                dni = caso.ciudadano.dni if caso.ciudadano_id else "-"
                self._log(f"[ensayo] caso #{caso.pk} · DNI {dni}")
            self._log(f"{len(casos)} caso(s) a reintentar. Agregá --aplicar para mandarlos.", self.style.WARNING)
            return
        catalogos = Catalogos()
        resumen = {}
        hechos = 0
        arranque = self._reloj()
        # El mismo freno que las otras tres vías. Sin él, este comando aceptaba
        # --max-errores y --max-inciertos y los ignoraba: con SIIS contestando
        # ambiguo se comía los 200 casos del --limite y dejaba 200 conciliaciones
        # a mano.
        freno = self._crear_freno(options)
        for caso in casos:
            try:
                envio = enviar_beneficiario_a_siis(caso, None, catalogos=catalogos)
            except ValueError:
                # SIIS-04: dejó de estar aprobado entre el listado y su turno.
                resumen["CAMBIO_DE_ESTADO"] = resumen.get("CAMBIO_DE_ESTADO", 0) + 1
                self._log(f"caso #{caso.pk}: cambió de estado, no se informa")
                continue
            resumen[envio.estado] = resumen.get(envio.estado, 0) + 1
            hechos += 1
            self._log(f"caso #{caso.pk}: {envio.get_estado_display()}")
            if freno.registrar(proceso_masivo.desenlace_de(envio)):
                detalle = ", ".join(f"{n} {estado.lower()}" for estado, n in sorted(resumen.items()))
                self._log(f"{hechos} reintentado(s) antes de cortar: {detalle}.")
                self._cortado_por_fallas(
                    freno,
                    self._reloj() - arranque,
                    "Los que quedaron en ERROR se retoman solos; los de resultado desconocido, no: "
                    "se concilian con `manage.py conciliar_envios_siis`.",
                )
        detalle = ", ".join(f"{n} {estado.lower()}" for estado, n in sorted(resumen.items()))
        self._log(self.style.SUCCESS(f"{len(casos)} reintentado(s): {detalle}."))
