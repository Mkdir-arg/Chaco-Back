"""Datos que las fichas PERF-13 y PERF-15 necesitan en el banco y que `escalar_bench`
no crea: un estado raro en la bandeja y un padrón grande en la convocatoria.

- **PERF-13** quiere la bandeja filtrada por un estado que casi no existe. `escalar_bench`
  reparte APROBADO/RECHAZADO/ENVIADO y deja `BAJA` en cero, que es justo el filtro de la
  ficha. Se marcan 400 de los 20.000 (2 %): raro, pero con página 10.
- **PERF-15** quiere el padrón del tamaño que la ficha pone como umbral (> 50k). Se cargan
  50.000 filas de nivel convocatoria, la mitad con identidad (RN-2), que es lo que cuenta
  el `aggregate` del detalle.

**Este script BORRA.** Es el primero de la carpeta que lo hace: vacía el padrón de la
convocatoria del último relevamiento público (`PadronHabilitado.objects.filter(
convocatoria=conv).delete()`) antes de recargarlo, y le pone `BAJA` a 400 casos que hoy
están `ENVIADO`. Por eso exige la base descartable del banco (`chaco_perf_ci`,
preguntada al servidor) y no solo «no es SQLite», que es lo único que mira
`_bootstrap.cargar_django()`: con `DATABASE_*` apuntando a cualquier MySQL/MariaDB con
datos —un restore de PRD en el laptop, por ejemplo— esto se llevaba puesto un padrón sin
avisar.

Uso: python scripts/perf_mysql/escenarios_borde.py [--bajas 400] [--padron 50000]
"""

import argparse

from _bootstrap import cargar_django, exigir_base_descartable  # noqa: E402

cargar_django()
exigir_base_descartable()

from programas.models import Formulario, PadronHabilitado, Relevamiento  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bajas", type=int, default=400)
    parser.add_argument("--padron", type=int, default=50000)
    args = parser.parse_args()

    rel = Relevamiento.objects.filter(tipo=Relevamiento.Tipo.PUBLICO).order_by("-pk").first()
    conv = rel.convocatoria

    pks = list(
        Formulario.objects.filter(relevamiento=rel, estado=Formulario.Estado.ENVIADO)
        .order_by("pk")
        .values_list("pk", flat=True)[: args.bajas]
    )
    Formulario.objects.filter(pk__in=pks).update(estado=Formulario.Estado.BAJA)
    print(f"BAJA: {Formulario.objects.filter(estado=Formulario.Estado.BAJA).count()} de {Formulario.objects.count()}")

    PadronHabilitado.objects.filter(convocatoria=conv).delete()
    filas = []
    for i in range(args.padron):
        con_identidad = i % 2 == 0
        filas.append(
            PadronHabilitado(
                convocatoria=conv,
                relevamiento=None,
                dni=f"{40000000 + i}",
                sexo="F" if i % 2 else "M",
                nombre="Nombre" if con_identidad else "",
                apellido=f"Apellido{i}" if con_identidad else "",
            )
        )
        if len(filas) >= 2000:
            PadronHabilitado.objects.bulk_create(filas, batch_size=2000)
            filas = []
    if filas:
        PadronHabilitado.objects.bulk_create(filas, batch_size=2000)
    print(f"padrón convocatoria {conv.pk}: {PadronHabilitado.objects.filter(convocatoria=conv).count()} filas")


if __name__ == "__main__":
    main()
