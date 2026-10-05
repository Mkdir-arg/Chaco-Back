"""Cierra a mano los envíos a SIIS de resultado desconocido (SIIS-02).

Cuando el POST del alta se corta a mitad —un ``ReadTimeout``, un 500, el pod
reiniciado entre el POST y el registro— **no se sabe** si SIIS registró al
beneficiario. Su API no deduplica ni permite dar de baja, así que reintentar a
ciegas es el peor desenlace posible: dos altas irreversibles de la misma persona.
Esos intentos quedan ``INCIERTO`` (o ``EN_PROCESO`` vencido) y **ningún camino
los reenvía**. Este comando es la única salida, y tiene tres pasos:

1. ``--listar`` arma el CSV que se le manda a ECOM: «¿estas personas están?».
2. con la respuesta, ``--confirmar <pk>`` (está: queda ``ENVIADO``) o
   ``--liberar <pk> --motivo "..."`` (no está: vuelve a ser candidato).
3. las dos decisiones quedan en la traza del caso, con el usuario que las tomó.

    python manage.py conciliar_envios_siis --listar > inciertos.csv
    python manage.py conciliar_envios_siis --confirmar 1234 --siis-id 55678 --usuario coord
    python manage.py conciliar_envios_siis --liberar 1234 --motivo "ECOM confirmó que no llegó" --usuario coord
"""

import csv

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from programas.models import EnvioSIIS
from programas.services.becas import registrar_traza

CAMPO_TRAZA = "envio_siis"
COLUMNAS = ("envio_id", "caso", "documento", "id_programa", "estado", "creado", "siis_id", "codigo_error")


class Command(BaseCommand):
    help = "Lista, confirma o libera los envíos a SIIS cuyo resultado no se conoce."

    def add_arguments(self, parser):
        parser.add_argument("--listar", action="store_true", help="CSV de los envíos inciertos, para mandar a ECOM.")
        parser.add_argument(
            "--confirmar",
            type=int,
            default=None,
            metavar="PK",
            help="ECOM confirmó que el alta está: el envío queda ENVIADO y el caso informado.",
        )
        parser.add_argument(
            "--siis-id", type=int, default=None, help="ID que asignó SIIS, si ECOM lo informó. Solo con --confirmar."
        )
        parser.add_argument(
            "--liberar",
            type=int,
            default=None,
            metavar="PK",
            help="ECOM confirmó que el alta NO está: el envío queda ERROR y el caso vuelve a ser candidato.",
        )
        parser.add_argument("--motivo", default="", help="Por qué se libera. Obligatorio con --liberar.")
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

    def _usuario(self, nombre):
        if not nombre:
            return None
        from django.contrib.auth import get_user_model

        usuario = get_user_model().objects.filter(username=nombre).first()
        if usuario is None:
            raise CommandError(f"No existe el usuario «{nombre}».")
        return usuario

    # ── Acciones ────────────────────────────────────────────────────────────

    def _listar(self):
        inciertos = list(self._inciertos())
        # Va por ``self.stdout`` para que se pueda redirigir a un archivo y, de
        # paso, capturarse en los tests; el conteo va a stderr para no ensuciarlo.
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
                ]
            )
        self.stderr.write(f"{len(inciertos)} envío(s) de resultado desconocido.")

    def _confirmar(self, pk, siis_id, usuario):
        envio = self._envio(pk)
        with transaction.atomic():
            EnvioSIIS.objects.filter(pk=envio.pk).update(
                estado=EnvioSIIS.Estado.ENVIADO,
                # Sigue ocupando el caso: ahora porque el alta existe de verdad.
                vigente=True,
                siis_id=siis_id if siis_id is not None else envio.siis_id,
                codigo_error="INCIERTO_CONFIRMADO",
                resuelto_en=timezone.now(),
            )
            registrar_traza(
                envio.formulario,
                usuario,
                [(CAMPO_TRAZA, envio.estado, f"ENVIADO (conciliado con SIIS, id {siis_id or 's/d'})")],
            )
        self.stdout.write(
            self.style.SUCCESS(f"EnvioSIIS #{pk} confirmado: el caso #{envio.formulario_id} queda informado a SIIS.")
        )

    def _liberar(self, pk, motivo, usuario):
        if not motivo.strip():
            raise CommandError(
                "--liberar necesita --motivo: solo se libera con la confirmación de ECOM de que el alta no llegó, "
                "y eso tiene que quedar escrito en la traza del caso."
            )
        envio = self._envio(pk)
        with transaction.atomic():
            EnvioSIIS.objects.filter(pk=envio.pk).update(
                estado=EnvioSIIS.Estado.ERROR,
                # NULL libera el caso: vuelve a ser candidato en todas las vías.
                vigente=None,
                codigo_error="INCIERTO_LIBERADO",
                detalles={"_": [motivo.strip()]},
                resuelto_en=timezone.now(),
            )
            registrar_traza(
                envio.formulario, usuario, [(CAMPO_TRAZA, envio.estado, f"liberado para reenvío: {motivo.strip()}")]
            )
        self.stdout.write(
            self.style.SUCCESS(f"EnvioSIIS #{pk} liberado: el caso #{envio.formulario_id} vuelve a ser candidato.")
        )

    # ── Orquestación ────────────────────────────────────────────────────────

    def handle(self, *args, **options):
        pedidos = [bool(options["listar"]), options["confirmar"] is not None, options["liberar"] is not None]
        if sum(pedidos) != 1:
            raise CommandError("Elegí una sola acción: --listar, --confirmar <pk> o --liberar <pk>.")
        usuario = self._usuario(options["usuario"])
        if options["listar"]:
            return self._listar()
        if options["confirmar"] is not None:
            return self._confirmar(options["confirmar"], options["siis_id"], usuario)
        return self._liberar(options["liberar"], options["motivo"], usuario)
