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

Es decir: el que se va no lo elegía ninguna consulta caliente, ni sola ni compartida.

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
        ("programas", "0083_sec09_upload_to_uuid"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="formulario",
            name="programas_f_estado_e0feb6_idx",
        ),
    ]
