"""Lista (y con ``--aplicar`` cierra) las filas de lista de espera que cuelgan de
casos ya resueltos.

Hasta que la regla quedó en el servicio, rechazar, dar de baja o aprobar con
cupo libre a un caso en espera dejaba su fila de ``ListaEspera`` activa: seguía
ocupando un lugar, contaba en «en lista de espera» y se podía «promover» a
APROBADO. Desde ese cambio ningún camino las deja colgando; este comando limpia
las que ya estaban.

Paso manual post-deploy, no una migración: toca datos reales y es una decisión
del cliente correrlo. Por defecto **solo lista**. Es idempotente: una vez
cerradas, las filas dejan de estar activas y la segunda corrida no encuentra
nada.

El cierre es el mismo que usan el rechazo y la baja
(``cerrar_espera_activa``): ``promovido=True`` más una traza en el caso con el
motivo, para que se distinga de una promoción de verdad.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from programas.models import Formulario, ListaEspera
from programas.services.cupo import cerrar_espera_activa


def filas_colgadas():
    """Filas activas de la lista de espera cuyo caso ya no está pendiente."""
    return (
        ListaEspera.objects.filter(promovido=False)
        .exclude(formulario__estado=Formulario.Estado.ENVIADO)
        .select_related("formulario", "segmento")
        .order_by("segmento_id", "posicion", "pk")
    )


class Command(BaseCommand):
    help = (
        "Lista las filas de lista de espera activas de casos ya rechazados, aprobados o dados de baja. "
        "Con --aplicar las cierra (idempotente)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--aplicar", action="store_true", help="Cierra las filas. Sin esto solo las lista.")
        parser.add_argument(
            "--usuario",
            default=None,
            help="Usuario que queda como responsable en la traza del cierre. Recomendado con --aplicar.",
        )

    def handle(self, *args, **options):
        responsable = None
        if options["usuario"]:
            responsable = get_user_model().objects.filter(username=options["usuario"]).first()
            if responsable is None:
                raise CommandError(f"No existe el usuario «{options['usuario']}».")

        filas = list(filas_colgadas())
        if not filas:
            self.stdout.write(self.style.SUCCESS("No hay filas de lista de espera colgando de casos resueltos."))
            return

        self.stdout.write(f"Filas de lista de espera activas de casos ya resueltos: {len(filas)}")
        por_estado = {}
        for fila in filas:
            estado = fila.formulario.get_estado_display()
            por_estado[estado] = por_estado.get(estado, 0) + 1
            self.stdout.write(
                f"   fila {fila.pk:>6} · {fila.segmento.nombre} · posición {fila.posicion:>4} · "
                f"caso {fila.formulario_id} · {estado} · ingresó {fila.fecha_ingreso:%d/%m/%Y}"
            )
        self.stdout.write("   " + " · ".join(f"{n} {estado}" for estado, n in sorted(por_estado.items())))

        if not options["aplicar"]:
            self.stdout.write(self.style.WARNING("\nEnsayo: no se cerró nada. Agregá --aplicar para cerrarlas."))
            return

        cerradas = 0
        # Un caso con filas en más de un segmento se cierra una sola vez: el
        # servicio cierra todas las filas activas del caso.
        casos = {fila.formulario_id: fila.formulario for fila in filas}
        for formulario in casos.values():
            with transaction.atomic():
                # Releído con lock: si entre el listado y el cierre el caso volvió
                # a estar pendiente, su fila ya no cuelga y no se toca.
                estado = Formulario.objects.select_for_update().filter(pk=formulario.pk).values_list("estado")
                if estado.get()[0] == Formulario.Estado.ENVIADO:
                    continue
                motivo = f"limpieza de datos, el caso ya estaba {formulario.get_estado_display().lower()}"
                cerradas += cerrar_espera_activa(formulario, responsable, motivo)
        self.stdout.write(self.style.SUCCESS(f"\nCerradas: {cerradas} filas de {len(casos)} casos."))
