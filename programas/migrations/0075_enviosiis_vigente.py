# Cambio 127 (auditoría oct-2026, SIIS-01/02/05): un solo envío vigente por caso.
#
# El alta en SIIS es irreversible (su API no tiene baja) y hasta acá se decidía
# con un check-then-act sin lock ni constraint: dos clics, el masivo y un comando
# a mano podían dar de alta dos veces al mismo beneficiario. ``vigente`` dentro de
# un índice único es la unicidad condicional que MariaDB no da con
# ``UniqueConstraint(condition=…)`` (``supports_partial_indexes = False``).
#
# EXPAND/CONTRACT: esta migración solo agrega. La columna nace NULL, así que el
# código viejo —que no la conoce— sigue insertando filas con ``vigente = NULL`` y
# nunca choca con el índice único. Se puede desplegar la migración antes que el
# código. Lo que NO se puede es correrla con una corrida masiva en curso: ver el
# «Riesgo de deploy» del PR.
#
# Tiempo esperado en ``programas_enviosiis`` (decenas de miles de filas): los dos
# ADD COLUMN son instantáneos en MariaDB 10.3+/MySQL 8 (columna nullable al final
# de la tabla, ALGORITHM=INSTANT); la migración de datos recorre la tabla por
# rangos de pk de a 2.000 y escribe de a 1.000; los dos índices son online DDL
# (INPLACE, concurrent DML permitido). Medido contra el banco MySQL 8 del repo:
# segundos, no minutos.

from django.db import migrations, models

PAGINA = 2000
LOTE = 1000

ENVIADO = "ENVIADO"
EN_PROCESO = "EN_PROCESO"
INCIERTO = "INCIERTO"


def _por_paginas(modelo, campos, filtro=None):
    """Recorre la tabla por rangos de pk: ninguna consulta se acerca al
    ``read_timeout`` de 10 s de la base de ECOM (patrón de la 0072)."""
    ultimo = 0
    while True:
        consulta = modelo.objects.filter(pk__gt=ultimo)
        if filtro is not None:
            consulta = consulta.filter(**filtro)
        filas = list(consulta.order_by("pk").values_list("pk", *campos)[:PAGINA])
        if not filas:
            return
        yield filas
        ultimo = filas[-1][0]


def poblar_vigente(apps, schema_editor):
    """Marca ``vigente`` en el ``ENVIADO`` más viejo de cada caso.

    El más viejo y no el último: si un caso ya tiene dos altas en SIIS (el bug
    que esta migración cierra; V2-NEW-03 lo mide en PRD antes del deploy), la
    primera es la que de verdad ocupó el lugar. Los duplicados **no hacen fallar
    la migración**: se listan por pantalla para que vayan a ECOM y se depuren del
    lado de SIIS, que es el único lado donde se pueden borrar.
    """
    EnvioSIIS = apps.get_model("programas", "EnvioSIIS")
    primero_por_caso = {}
    duplicados = {}
    for filas in _por_paginas(EnvioSIIS, ("formulario_id", "creado"), filtro={"estado": ENVIADO}):
        for pk, formulario_id, creado in filas:
            anterior = primero_por_caso.get(formulario_id)
            if anterior is None:
                primero_por_caso[formulario_id] = (creado, pk)
                continue
            duplicados.setdefault(formulario_id, [anterior[1]]).append(pk)
            if (creado, pk) < anterior:
                primero_por_caso[formulario_id] = (creado, pk)

    pks = sorted(pk for _, pk in primero_por_caso.values())
    for inicio in range(0, len(pks), LOTE):
        EnvioSIIS.objects.filter(pk__in=pks[inicio : inicio + LOTE]).update(vigente=True)

    if duplicados:
        print(
            f"\n  ATENCIÓN: {len(duplicados)} caso(s) ya tienen más de un alta ENVIADO en SIIS. "
            "Queda vigente la más vieja; el resto hay que depurarlo del lado de SIIS (V2-NEW-03)."
        )
        for formulario_id, envios in sorted(duplicados.items()):
            print(f"    caso #{formulario_id}: EnvioSIIS {', '.join(str(pk) for pk in sorted(envios))}")


def revertir_vigente(apps, schema_editor):
    """Deja la tabla legible para el código viejo, sin reenviar nada.

    El código anterior a esta migración no conoce ``EN_PROCESO`` ni ``INCIERTO``:
    los tomaría como «último envío distinto de ENVIADO», o sea **candidatos a
    reenviar**, que es justo lo que no puede pasar con un alta que pudo haber
    llegado. Se los marca ``ENVIADO`` —el único estado que ningún camino
    reenvía— con el código de error que dice qué eran, y se listan sus pk: son
    los que hay que conciliar con ECOM antes de volver a tocarlos.
    """
    EnvioSIIS = apps.get_model("programas", "EnvioSIIS")
    ambiguos = list(
        EnvioSIIS.objects.filter(estado__in=(EN_PROCESO, INCIERTO)).order_by("pk").values_list("pk", "formulario_id")
    )
    if not ambiguos:
        return
    for inicio in range(0, len(ambiguos), LOTE):
        pks = [pk for pk, _ in ambiguos[inicio : inicio + LOTE]]
        EnvioSIIS.objects.filter(pk__in=pks).update(estado=ENVIADO, codigo_error="INCIERTO_AL_REVERTIR")
    print(
        f"\n  ATENCIÓN: {len(ambiguos)} envío(s) de resultado desconocido quedaron como ENVIADO para que "
        "ningún camino los reenvíe. Hay que preguntarle a ECOM si llegaron:"
    )
    for pk, formulario_id in ambiguos:
        print(f"    EnvioSIIS {pk} (caso #{formulario_id})")


class Migration(migrations.Migration):
    dependencies = [("programas", "0074_altaintermediasiis")]

    operations = [
        migrations.AlterField(
            model_name="enviosiis",
            name="estado",
            field=models.CharField(
                choices=[
                    ("EN_PROCESO", "En proceso"),
                    ("ENVIADO", "Enviado"),
                    ("INCOMPLETO", "Datos incompletos"),
                    ("RECHAZADO", "Rechazado por SIIS"),
                    ("ERROR", "Error técnico"),
                    ("INCIERTO", "Resultado incierto"),
                ],
                db_index=True,
                max_length=15,
            ),
        ),
        migrations.AddField(
            model_name="enviosiis",
            name="vigente",
            field=models.BooleanField(default=None, editable=False, null=True),
        ),
        migrations.AddField(
            model_name="enviosiis",
            name="resuelto_en",
            field=models.DateTimeField(blank=True, null=True),
        ),
        # Va antes del índice único: si quedaran dos ``vigente=True`` del mismo
        # caso, el ALTER TABLE fallaría y dejaría el esquema a medias.
        migrations.RunPython(poblar_vigente, revertir_vigente),
        migrations.AddConstraint(
            model_name="enviosiis",
            constraint=models.UniqueConstraint(fields=("formulario", "vigente"), name="uniq_enviosiis_vigente_caso"),
        ),
        migrations.AddIndex(
            model_name="enviosiis",
            index=models.Index(fields=["documento", "id_programa"], name="idx_enviosiis_doc_plan"),
        ),
    ]
