from django.db import migrations

# Mismo valor que `Plaza.Tipo.CAMA`: se escribe a mano para que la migración no dependa del
# código de hoy (los modelos históricos no traen las TextChoices).
CAMA = "CAMA"


def convertir_tipos_v1(TipoDispositivo):
    """Deja cada tipo de la v1 sin configurar como si alguien abriera el modal y guardara.

    Un tipo de la v1 es `maneja_camas=True` con `tipos_plaza_admitidos` vacío (`[]` o nulo).
    `TipoDispositivoForm` lo abre con «Cama» y «Exige asignar una plaza» tildados y, al
    guardar, escribe `tipos_plaza_admitidos=["CAMA"]`, `plaza_obligatoria_al_ingresar=True`
    y deja `maneja_camas=True`. Es exactamente lo que hace esta función (Cambio 372).

    Idempotente: filtra por el estado de origen, así que un reintento no toca lo convertido.
    La lista vacía se mira en Python (pocas filas): el lookup JSON difiere entre MySQL y MariaDB.
    """

    convertidos = 0
    for tipo in TipoDispositivo.objects.filter(maneja_camas=True).only("id", "tipos_plaza_admitidos"):
        if tipo.tipos_plaza_admitidos:
            continue
        TipoDispositivo.objects.filter(pk=tipo.pk).update(
            tipos_plaza_admitidos=[CAMA],
            plaza_obligatoria_al_ingresar=True,
            maneja_camas=True,
        )
        convertidos += 1
    return convertidos


def convertir(apps, schema_editor):
    convertir_tipos_v1(apps.get_model("programas", "TipoDispositivo"))


class Migration(migrations.Migration):
    dependencies = [
        ("programas", "0105_dispositivo_encuadre"),
    ]

    operations = [
        # REVERSA-NOOP: no se distingue un tipo convertido de uno que alguien guardó a mano, y lo
        # convertido (lista ["CAMA"] + plaza obligatoria + maneja_camas=True) es lo que la
        # release anterior ya sabe leer (Cambio 372, Reversión): no queda nada inconsistente.
        migrations.RunPython(convertir, migrations.RunPython.noop),
    ]
