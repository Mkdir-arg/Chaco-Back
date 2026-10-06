"""Cierra a mano los envíos a SIIS de resultado desconocido (SIIS-02).

Cuando el POST del alta se corta a mitad —un ``ReadTimeout``, un 500, el pod
reiniciado entre el POST y el registro— **no se sabe** si SIIS registró al
beneficiario. Su API no deduplica ni permite dar de baja, así que reintentar a
ciegas es el peor desenlace posible: dos altas irreversibles de la misma persona.
Esos intentos quedan ``INCIERTO`` (o ``EN_PROCESO`` vencido) y **ningún camino
los reenvía**. Este comando es la única salida, y tiene tres pasos:

1. ``--listar`` arma el CSV que se le manda a ECOM: «¿estas personas están?».
   Trae una columna ``decision`` vacía y una ``motivo``.
2. ECOM devuelve el mismo archivo con ``decision`` en ``confirmar`` o ``liberar``
   (y ``siis_id`` cuando lo tenga), y ``--desde-csv`` lo aplica de una.
   Para pocos casos están ``--confirmar`` y ``--liberar``, que aceptan una lista
   de pk separada por comas.
3. Las decisiones quedan en la traza del caso, con el usuario que las tomó.

**Corre en seco por defecto**, como el resto de los comandos de SIIS: sin
``--aplicar`` dice qué haría y no toca nada.

    python manage.py conciliar_envios_siis --listar > inciertos.csv
    python manage.py conciliar_envios_siis --desde-csv inciertos.csv            # ensayo
    python manage.py conciliar_envios_siis --desde-csv inciertos.csv --aplicar --usuario coord
    python manage.py conciliar_envios_siis --confirmar 1234 --siis-id 55678 --aplicar --usuario coord
    python manage.py conciliar_envios_siis --liberar 1234,1235 --motivo "ECOM: no llegaron" --aplicar
"""

import csv

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from programas.models import EnvioSIIS
from programas.services.becas import registrar_traza

CAMPO_TRAZA = "envio_siis"
CONFIRMAR = "confirmar"
LIBERAR = "liberar"
# Las dos últimas las completa ECOM y las vuelve a leer ``--desde-csv``.
COLUMNAS = (
    "envio_id",
    "caso",
    "documento",
    "id_programa",
    "estado",
    "creado",
    "siis_id",
    "codigo_error",
    "decision",
    "motivo",
)


class Command(BaseCommand):
    help = "Lista, confirma o libera los envíos a SIIS cuyo resultado no se conoce."

    def add_arguments(self, parser):
        parser.add_argument("--listar", action="store_true", help="CSV de los envíos inciertos, para mandar a ECOM.")
        parser.add_argument(
            "--confirmar",
            default=None,
            metavar="PKS",
            help="ECOM confirmó que el alta está: quedan ENVIADO. Un pk o varios separados por comas.",
        )
        parser.add_argument(
            "--liberar",
            default=None,
            metavar="PKS",
            help="ECOM confirmó que el alta NO está: quedan ERROR y los casos vuelven a ser candidatos.",
        )
        parser.add_argument(
            "--desde-csv",
            default=None,
            metavar="RUTA",
            help="Aplica el CSV que devolvió ECOM: una fila por envío, con la columna «decision».",
        )
        parser.add_argument(
            "--siis-id", type=int, default=None, help="ID que asignó SIIS. Solo con --confirmar de un solo pk."
        )
        parser.add_argument("--motivo", default="", help="Por qué se libera. Obligatorio con --liberar.")
        parser.add_argument("--aplicar", action="store_true", help="Escribe. Sin esto solo dice qué haría.")
        parser.add_argument("--usuario", default=None, help="Quien tomó la decisión. Queda en la traza del caso.")

    # ── Selección ───────────────────────────────────────────────────────────

    def _inciertos(self):
        """Los ``INCIERTO`` y los ``EN_PROCESO`` que ya no pueden estar en vuelo."""
        corte = timezone.now() - EnvioSIIS.EN_PROCESO_VENCE
        return (
            EnvioSIIS.objects.filter(vigente=True)
            .exclude(estado=EnvioSIIS.Estado.ENVIADO)
            .exclude(estado=EnvioSIIS.Estado.EN_PROCESO, creado__gt=corte)
            .select_related("formulario")
            .order_by("pk")
        )

    def _envio(self, pk):
        envio = EnvioSIIS.objects.select_related("formulario").filter(pk=pk).first()
        if envio is None:
            raise CommandError(f"No existe el EnvioSIIS #{pk}.")
        if not envio.incierto:
            raise CommandError(
                f"El EnvioSIIS #{pk} está en {envio.estado} y no es un resultado incierto: no hay nada que conciliar."
            )
        return envio

    @staticmethod
    def _pks(crudo):
        pks = []
        for parte in str(crudo).replace(";", ",").split(","):
            parte = parte.strip()
            if not parte:
                continue
            if not parte.isdigit():
                raise CommandError(f"«{parte}» no es un número de EnvioSIIS.")
            pks.append(int(parte))
        if not pks:
            raise CommandError("No pasaste ningún pk.")
        return pks

    def _usuario(self, nombre):
        if not nombre:
            return None
        usuario = get_user_model().objects.filter(username=nombre).first()
        if usuario is None:
            raise CommandError(f"No existe el usuario «{nombre}».")
        return usuario

    # ── Acciones ────────────────────────────────────────────────────────────

    def _listar(self):
        inciertos = list(self._inciertos())
        salida = csv.writer(self.stdout, lineterminator="\n")
        salida.writerow(COLUMNAS)
        for envio in inciertos:
            salida.writerow(
                [
                    envio.pk,
                    envio.formulario_id,
                    envio.documento,
                    envio.id_programa or "",
                    envio.estado,
                    timezone.localtime(envio.creado).isoformat(timespec="seconds") if envio.creado else "",
                    envio.siis_id or "",
                    envio.codigo_error,
                    "",
                    "",
                ]
            )
        # Por stderr para que el CSV se pueda redirigir limpio a un archivo.
        self.stderr.write(f"{len(inciertos)} envío(s) de resultado desconocido.")

    def _confirmar(self, envio, siis_id, usuario):
        with transaction.atomic():
            EnvioSIIS.objects.filter(pk=envio.pk).update(
                estado=EnvioSIIS.Estado.ENVIADO,
                # Sigue ocupando el caso —y el lugar de la persona en el plan—:
                # ahora porque el alta existe de verdad.
                vigente=True,
                clave_persona_plan=envio.clave_persona_plan,
                siis_id=siis_id if siis_id is not None else envio.siis_id,
                codigo_error="INCIERTO_CONFIRMADO",
                resuelto_en=timezone.now(),
            )
            registrar_traza(
                envio.formulario,
                usuario,
                [(CAMPO_TRAZA, envio.estado, f"ENVIADO (conciliado con SIIS, id {siis_id or 's/d'})")],
            )
        return f"#{envio.pk}: confirmado, el caso #{envio.formulario_id} queda informado a SIIS."

    def _liberar(self, envio, motivo, usuario):
        with transaction.atomic():
            EnvioSIIS.objects.filter(pk=envio.pk).update(
                estado=EnvioSIIS.Estado.ERROR,
                # NULL libera el caso y el lugar de la persona en el plan: vuelve
                # a ser candidato en todas las vías.
                vigente=None,
                clave_persona_plan=None,
                codigo_error=EnvioSIIS.LIBERADO,
                detalles={"_": [motivo]},
                resuelto_en=timezone.now(),
            )
            registrar_traza(
                envio.formulario, usuario, [(CAMPO_TRAZA, envio.estado, f"liberado para reenvío: {motivo}")]
            )
        return f"#{envio.pk}: liberado, el caso #{envio.formulario_id} vuelve a ser candidato."

    # ── Lotes ───────────────────────────────────────────────────────────────

    def _filas_del_csv(self, ruta):
        """``[(pk, decision, motivo, siis_id)]`` leídas del archivo que devolvió ECOM."""
        try:
            with open(ruta, newline="", encoding="utf-8-sig") as archivo:
                filas = list(csv.DictReader(archivo))
        except OSError as exc:
            raise CommandError(f"No se pudo leer {ruta}: {exc}") from exc
        if not filas:
            raise CommandError(f"{ruta} no tiene filas.")
        if "envio_id" not in filas[0] or "decision" not in filas[0]:
            raise CommandError("El CSV tiene que tener las columnas «envio_id» y «decision» (las trae --listar).")
        pedidos = []
        for numero, fila in enumerate(filas, start=2):
            decision = (fila.get("decision") or "").strip().lower()
            if not decision:
                continue  # ECOM todavía no la contestó: no se toca.
            if decision not in (CONFIRMAR, LIBERAR):
                raise CommandError(f"Fila {numero}: «decision» es «{decision}»; tiene que ser confirmar o liberar.")
            crudo = (fila.get("envio_id") or "").strip()
            if not crudo.isdigit():
                raise CommandError(f"Fila {numero}: «envio_id» es «{crudo}», que no es un número.")
            siis_id = (fila.get("siis_id") or "").strip()
            pedidos.append(
                (int(crudo), decision, (fila.get("motivo") or "").strip(), int(siis_id) if siis_id else None)
            )
        if not pedidos:
            raise CommandError("Ninguna fila del CSV tiene «decision» completa: no hay nada que aplicar.")
        return pedidos

    def _aplicar(self, pedidos, usuario, aplicar):
        """Aplica ``[(pk, decision, motivo, siis_id)]``, o dice qué haría."""
        for pk, decision, motivo, _ in pedidos:
            if decision == LIBERAR and not motivo:
                raise CommandError(
                    f"#{pk}: liberar necesita un motivo. Solo se libera con la confirmación de ECOM de que el "
                    "alta no llegó, y eso tiene que quedar escrito en la traza del caso."
                )
        # Se validan **todos** antes de escribir ninguno: un pk equivocado en la
        # fila 40 no puede dejar 39 conciliados y el resto sin hacer.
        envios = {pk: self._envio(pk) for pk, _, _, _ in pedidos}
        if not aplicar:
            for pk, decision, motivo, siis_id in pedidos:
                extra = f" (siis_id {siis_id})" if siis_id else ""
                extra += f" · motivo: {motivo}" if motivo else ""
                self._log(f"[ensayo] #{pk} caso #{envios[pk].formulario_id} → {decision}{extra}")
            self._log(f"{len(pedidos)} envío(s) a conciliar. Agregá --aplicar para escribirlos.", self.style.WARNING)
            return
        hechos = {CONFIRMAR: 0, LIBERAR: 0}
        for pk, decision, motivo, siis_id in pedidos:
            envio = envios[pk]
            if decision == CONFIRMAR:
                self._log(self._confirmar(envio, siis_id, usuario))
            else:
                self._log(self._liberar(envio, motivo, usuario))
            hechos[decision] += 1
        self._log(self.style.SUCCESS(f"Listo: {hechos[CONFIRMAR]} confirmado(s) y {hechos[LIBERAR]} liberado(s)."))

    def _log(self, texto, estilo=None):
        self.stdout.write(estilo(texto) if estilo else texto)

    # ── Orquestación ────────────────────────────────────────────────────────

    def handle(self, *args, **options):
        acciones = [bool(options["listar"]), options["confirmar"], options["liberar"], options["desde_csv"]]
        if sum(1 for accion in acciones if accion) != 1:
            raise CommandError("Elegí una sola acción: --listar, --confirmar, --liberar o --desde-csv.")
        if options["listar"]:
            return self._listar()

        usuario = self._usuario(options["usuario"])
        motivo = options["motivo"].strip()
        if options["desde_csv"]:
            pedidos = self._filas_del_csv(options["desde_csv"])
        elif options["confirmar"]:
            pks = self._pks(options["confirmar"])
            if options["siis_id"] is not None and len(pks) > 1:
                raise CommandError("--siis-id es de un solo envío: para varios, usá el CSV con su columna siis_id.")
            pedidos = [(pk, CONFIRMAR, "", options["siis_id"]) for pk in pks]
        else:
            pedidos = [(pk, LIBERAR, motivo, None) for pk in self._pks(options["liberar"])]
        return self._aplicar(pedidos, usuario, options["aplicar"])
