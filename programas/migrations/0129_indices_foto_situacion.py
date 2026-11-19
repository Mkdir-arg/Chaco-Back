"""Índices de la foto de situación de E8 (Cambio 509; pendiente 1 del Cambio 508, RNF-009-10).

El ``EXPLAIN`` de E-4 (MariaDB 10.11) mostró cuatro lecturas de la foto que recorrían la tabla entera,
incluida la historia de eventos anteriores. Cada índice de acá sirve a una:

* ``IntegranteGrupo.egresado_en``: personas alojadas (``egresado_en IS NULL OR >= x``; también A4).
* ``Derivacion(estado, creado)``: pendientes de toda la red y rechazadas o vencidas de la cohorte
  (el selector filtra además ``creado >= x``, implicado por el del caso).
* ``EntregaKit.despachada_en`` y ``EntregaKit.estado``: ``despachada_en >= x OR estado = EN_CAMINO``
  con *index merge*.
* ``Estadia.fecha_ingreso`` y ``Estadia.fecha_egreso``: el ritmo de las últimas 6 h con *index merge*.

Solo índices, sin columnas ni datos: la release anterior no los ve y la reversa es borrarlos. Como
en ``0128``, el DDL no es transaccional: si se corta a mitad, el reintento falla con «Duplicate key
name»; se borra a mano el índice que quedó y se reintenta (tablas de miles de filas, segundos).
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("programas", "0128_indices_ventana_casos_emergencia"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="derivacion",
            index=models.Index(fields=["estado", "creado"], name="derivacion_estado_creado_idx"),
        ),
        migrations.AddIndex(
            model_name="entregakit",
            index=models.Index(fields=["despachada_en"], name="entrega_kit_despachada_en_idx"),
        ),
        migrations.AddIndex(
            model_name="entregakit",
            index=models.Index(fields=["estado"], name="entrega_kit_estado_idx"),
        ),
        migrations.AddIndex(
            model_name="estadia",
            index=models.Index(fields=["fecha_ingreso"], name="estadia_fecha_ingreso_idx"),
        ),
        migrations.AddIndex(
            model_name="estadia",
            index=models.Index(fields=["fecha_egreso"], name="estadia_fecha_egreso_idx"),
        ),
        migrations.AddIndex(
            model_name="integrantegrupo",
            index=models.Index(fields=["egresado_en"], name="integrante_egresado_en_idx"),
        ),
    ]
