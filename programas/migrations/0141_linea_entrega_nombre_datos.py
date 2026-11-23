from django.db import migrations
from django.db.models import OuterRef, Subquery


def rellenar_nombre(apps, schema_editor):
    """Copia el nombre del ítem a las líneas que no lo tienen. Idempotente: solo toca las ``NULL``.

    Una sola sentencia ``UPDATE`` con subconsulta (sin recorrer fila por fila): la tabla crece con
    cada entrega y el ``read_timeout`` de ECOM es de 10 s. Si se corta y se reintenta, retoma
    donde quedó porque filtra por el estado de origen.
    """
    LineaEntrega = apps.get_model("programas", "LineaEntrega")
    TipoKit = apps.get_model("programas", "TipoKit")
    nombre_del_item = TipoKit.objects.filter(pk=OuterRef("item_id")).values("nombre")[:1]
    LineaEntrega.objects.filter(nombre__isnull=True).update(nombre=Subquery(nombre_del_item))


class Migration(migrations.Migration):
    dependencies = [
        ("programas", "0140_linea_entrega_nombre"),
    ]

    operations = [
        # REVERSA-NOOP: la columna ``nombre`` sigue existiendo al revertir solo este paso y quedan los
        # nombres copiados; no es inconsistencia (el código lee ``nombre or item.nombre``). Al revertir
        # 0140 la columna se borra con ellos, y el nombre sigue en el ítem.
        migrations.RunPython(rellenar_nombre, migrations.RunPython.noop),
    ]
