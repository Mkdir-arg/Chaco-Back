"""RED-83 · Se va el índice duplicado de `programas_formulario.estado`.

`Formulario.estado` declaraba `db_index=True` **y** `Meta.indexes = [Index(["estado"])]`:
dos árboles idénticos sobre la columna que más se reescribe (cada alta, cada paso de la
revisión) de la tabla más grande del sistema. En el banco MariaDB 10.11 de
`scripts/perf_mysql` la tabla pesa **362 MB** con 20.000 casos.

`EXPLAIN` antes y después, en el mismo banco:

* bandeja por estado ordenada por `creado` → `prog_formulario_creado_idx` en los dos
  casos (ninguno de los dos índices de `estado` entraba en juego);
* conteo por estado → `programas_formulario_estado_2cbb26f8`, el que crea `db_index=True`
  y el que se conserva, antes y después, con el mismo `key_len` y el mismo plan
  (`Using where; Using index`);
* `relevamiento_id + estado` → `programas_f_relevam_4c6a6a_idx`, intacto.

Es decir: en las tres consultas medidas acá el plan no cambia. **El que se va sí
aparecía en una medición previa**: PERF-13 (Cambio 180, `docs/internal/requerimientos.md`)
registró `key=programas_f_estado_e0feb6_idx` para la bandeja `estado=BAJA` página 10
(400 de 40.000 casos, 2,4-4,9 ms), que es el caso **barato** de esa pantalla. No hay
consecuencia: el índice que sobrevive es idéntico —un árbol sobre `(estado)`— y el
optimizador elige uno u otro indistintamente, así que el plan y el costo son los mismos.
Lo que cambia es el **nombre** que imprime `EXPLAIN`: quien reproduzca PERF-13 después de
esta migración va a ver `key=programas_formulario_estado_2cbb26f8` y no el `key=` que
quedó escrito en aquella tabla.

**Online.** `DROP INDEX` de un secundario en InnoDB es in-place: no reconstruye la tabla
ni bloquea DML. Medido en el banco sobre los 362 MB: **29 ms**, contra el `read_timeout`
de 10 s de ECOM. No lleva marca de `# CONTRACT:` porque no la pide el contrato ni el
caso: durante el rolling la release vieja no nombra índices —los elige el optimizador—,
así que no hay código viejo que esto pueda romper.

**Reversa probada:** `RemoveIndex` vuelve a crear el índice y se corrió ida → vuelta →
ida contra el banco, con datos, las tres en verde.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("programas", "0084_solicitud_merendero_creado_por"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="formulario",
            name="programas_f_estado_e0feb6_idx",
        ),
    ]
