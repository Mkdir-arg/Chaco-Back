"""RED-83 · Se van los cuatro índices de `legajos_ciudadano` que son prefijo de otro.

Un índice cuyas columnas son el prefijo exacto de otro no aporta nada: el motor usa el
largo para las dos consultas. Lo que sí hace es costar en cada `INSERT`, `UPDATE` y
`DELETE`, ocupar buffer pool y alargar todo `ALTER` de la tabla.

Medido contra el banco MariaDB 10.11 de `scripts/perf_mysql` (21.522 ciudadanos, 18 MB),
con `EXPLAIN` antes y después de cada baja:

* `legajos_ciudadano_activo_027759ca (activo)` ⊂ `legajos_ciu_listado_idx (activo,
  apellido, nombre, dni, creado)` — el listado ya elegía el largo: mismo plan.
* `legajos_ciudadano_apellido_ffe80589 (apellido)` ⊂ `legajos_ciu_apellid_2efcc7_idx
  (apellido, nombre)` — es el **único** que el optimizador llegaba a elegir (la búsqueda
  por apellido). Después del `DROP` la misma consulta usa el compuesto con el mismo
  `type=range`, el mismo `key_len=482` y las mismas filas estimadas: el prefijo izquierdo
  del compuesto sirve exactamente el mismo rango.
* `legajos_ciu_dni_4e1a21_idx (dni)` ≡ el índice UNIQUE `dni` — duplicado exacto; el
  lookup por documento seguía siendo `const` por el UNIQUE, que es el que se conserva.
* `legajos_ciu_email_e7552c_idx (email)` ≡ `legajos_ciudadano_email_36679ad5 (email)`,
  el que crea `db_index=True` — duplicado exacto, y el que el motor ya elegía.

**Por qué va online y por qué no lleva marca de CONTRACT.** `DROP INDEX` de un índice
secundario en InnoDB es una operación in-place: no reconstruye la tabla y no bloquea DML.
Medido en el banco: 31 + 31 + 27 + 32 ms, cuatro bajas sobre esta tabla, muy por debajo
del `read_timeout` de 10 s de ECOM. Y no es un *contract* en el sentido de
`scripts/check_migraciones.py`: la release vieja que sigue atendiendo durante el rolling
no nombra ningún índice —los nombra el optimizador, no el ORM—, así que no hay código que
se rompa por esto. Lo que se borra es una decisión de esquema, no un dato ni una columna.

**Reversa probada, no declarada de palabra.** `RemoveIndex` y `AlterField` revierten solos
(vuelven a crear los cuatro índices) y se corrió el ciclo entero contra el banco:
ida → vuelta → ida, las tres en verde, ~3,3 s cada una contando el arranque de Django.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("legajos", "0010_sec09_upload_to_uuid"),
    ]

    operations = [
        # Duplicado exacto del índice UNIQUE que ya crea `dni = CharField(unique=True)`.
        migrations.RemoveIndex(
            model_name="ciudadano",
            name="legajos_ciu_dni_4e1a21_idx",
        ),
        # Duplicado exacto del que crea `email = EmailField(db_index=True)`.
        migrations.RemoveIndex(
            model_name="ciudadano",
            name="legajos_ciu_email_e7552c_idx",
        ),
        # Los dos `AlterField` son solo la baja del índice de una columna: el tipo no
        # cambia, así que MySQL/MariaDB no emiten `MODIFY` y el SQL de ida es un
        # `DROP INDEX` pelado (verificado con `sqlmigrate`). El nombre del índice no se
        # escribe a mano —lo generó el schema editor con un hash— sino que lo resuelve
        # Django por introspección, que es lo que vuelve el paso portable entre motores.
        migrations.AlterField(
            model_name="ciudadano",
            name="activo",
            field=models.BooleanField(default=True),
        ),
        migrations.AlterField(
            model_name="ciudadano",
            name="apellido",
            field=models.CharField(max_length=120),
        ),
    ]
