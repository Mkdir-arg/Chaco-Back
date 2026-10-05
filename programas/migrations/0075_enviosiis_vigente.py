# Cambio 127 (auditoría oct-2026, SIIS-01/02/05): un solo envío vigente por caso.
#
# El alta en SIIS es irreversible (su API no tiene baja) y hasta acá se decidía
# con un check-then-act sin lock ni constraint: dos clics, el masivo y un comando
# a mano podían dar de alta dos veces al mismo beneficiario. ``vigente`` dentro de
# un índice único es la unicidad condicional que MariaDB no da con
# ``UniqueConstraint(condition=…)`` (``supports_partial_indexes = False``), y
# ``clave_persona_plan`` hace lo mismo una fila más arriba: una sola alta vigente
# por persona y plan, aunque venga de otro formulario (SIIS-05).
#
# EXPAND/CONTRACT: esta migración solo agrega. Las columnas nacen NULL, así que el
# código viejo —que no las conoce— sigue insertando filas con ``vigente = NULL`` y
# nunca choca con los índices únicos. Se puede desplegar la migración antes que el
# código. Lo que NO se puede es correrla con una corrida masiva en curso: ver el
# «Riesgo de deploy» del PR.
#
# Tiempo esperado en ``programas_enviosiis`` (decenas de miles de filas): los tres
# ADD COLUMN son instantáneos en MariaDB 10.3+/MySQL 8 (columnas nullable al final
# de la tabla, ALGORITHM=INSTANT); la migración de datos recorre la tabla por
# rangos de pk de a 2.000 y escribe de a 1.000; los índices son online DDL
# (INPLACE, concurrent DML permitido).

from django.db import migrations, models
from django.db.models import Count, Value
from django.db.models.functions import Cast, Concat

PAGINA = 2000
LOTE = 1000
# Cuántos duplicados se listan por pantalla. El resto queda igual en la traza de
# su caso, que es lo consultable; el log del deploy no es un informe.
TOPE_LISTADO = 100

ENVIADO = "ENVIADO"
EN_PROCESO = "EN_PROCESO"
INCIERTO = "INCIERTO"
CAMPO_TRAZA = "envio_siis"


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


def _trazar(apps, filas):
    """Deja una fila de ``TracaFormulario`` por duplicado, para que quede consultable.

    La salida por pantalla de una migración se pierde con el log del deploy. La
    traza del caso, en cambio, la ve el coordinador en la pantalla del caso y se
    consulta después con SQL (``WHERE campo = 'envio_siis'``).
    """
    Traca = apps.get_model("programas", "TracaFormulario")
    Traca.objects.bulk_create(
        [
            Traca(
                formulario_id=formulario_id,
                editado_por=None,
                campo=CAMPO_TRAZA,
                valor_anterior="",
                valor_nuevo=texto,
            )
            for formulario_id, texto in filas
        ],
        batch_size=LOTE,
    )


def poblar_vigente(apps, schema_editor):
    """Marca ``vigente`` y ``clave_persona_plan`` en los envíos que ocupan un lugar.

    Dos pasadas, porque son dos reglas distintas:

    1. **Un vigente por caso.** Queda el ``ENVIADO`` **más viejo** de cada
       formulario: si un caso ya tiene dos altas en SIIS (el bug que esta
       migración cierra), la primera es la que de verdad ocupó el lugar.
    2. **Un vigente por persona y plan** (SIIS-05), que puede cruzar formularios:
       dos casos distintos del mismo DNI en el mismo plan pueden tener los dos un
       alta real en SIIS. El desempate es el mismo —el más viejo— pero el perdedor
       **conserva** ``vigente=True`` y solo se queda sin clave.

    Eso último es deliberado y es lo contrario de lo intuitivo: sacarle
    ``vigente`` al perdedor lo devolvería a la lista de candidatos y la próxima
    corrida mandaría una **tercera** alta de la misma persona. El alta no tiene
    baja, así que lo único seguro es que los dos casos sigan tomados.

    **Nunca falla y nunca borra.** Cada duplicado se imprime y deja una traza en
    su caso, que es lo que después se le manda a ECOM para depurarlo del lado de
    SIIS, el único lado donde se pueden sacar.
    """
    EnvioSIIS = apps.get_model("programas", "EnvioSIIS")
    primero_por_caso = {}
    duplicados_por_caso = {}
    for filas in _por_paginas(EnvioSIIS, ("formulario_id", "creado"), filtro={"estado": ENVIADO}):
        for pk, formulario_id, creado in filas:
            anterior = primero_por_caso.get(formulario_id)
            if anterior is None:
                primero_por_caso[formulario_id] = (creado, pk)
                continue
            duplicados_por_caso.setdefault(formulario_id, [anterior[1]]).append(pk)
            if (creado, pk) < anterior:
                primero_por_caso[formulario_id] = (creado, pk)

    pks = sorted(pk for _, pk in primero_por_caso.values())
    for inicio in range(0, len(pks), LOTE):
        EnvioSIIS.objects.filter(pk__in=pks[inicio : inicio + LOTE]).update(vigente=True)

    if duplicados_por_caso:
        print(
            f"\n  ATENCION: {len(duplicados_por_caso)} caso(s) ya tienen mas de un alta ENVIADO en SIIS. "
            "Queda vigente la mas vieja; el resto hay que depurarlo del lado de SIIS (V2-NEW-03)."
        )
        trazas = []
        for numero, (formulario_id, envios) in enumerate(sorted(duplicados_por_caso.items())):
            lista = ", ".join(str(pk) for pk in sorted(envios))
            if numero < TOPE_LISTADO:
                print(f"    caso #{formulario_id}: EnvioSIIS {lista}")
            trazas.append((formulario_id, f"alta duplicada en el mismo caso al migrar: EnvioSIIS {lista}"))
        if len(duplicados_por_caso) > TOPE_LISTADO:
            print(f"    ... y {len(duplicados_por_caso) - TOPE_LISTADO} mas (todos quedan en la traza de su caso)")
        _trazar(apps, trazas)

    _poblar_clave_persona_plan(apps)


def _poblar_clave_persona_plan(apps):
    """Segunda pasada: la clave ``documento:id_programa`` de cada vigente.

    La clave se calcula **en el motor** (``CONCAT``): es una función de dos
    columnas que ya están en la fila. Traer 40.000 filas a Python para
    escribirlas una por una son 90 s contra MariaDB, y 20 s con ``bulk_update``
    y sus CASE WHEN de a mil; así son menos de 3.

    Primero se averigua **quiénes repiten** y esos quedan afuera del UPDATE
    masivo: así no se escribe nunca un estado intermedio con claves repetidas.
    Importa porque la migración tiene que poder volver a correrse sobre un
    esquema que ya tenga el índice único (un intento anterior cortado a mitad,
    el runner de los tests, que arma el esquema desde los modelos).
    """
    EnvioSIIS = apps.get_model("programas", "EnvioSIIS")
    clave = Concat("documento", Value(":"), Cast("id_programa", models.CharField()))
    completos = EnvioSIIS.objects.filter(vigente=True).exclude(documento="").exclude(id_programa__isnull=True)

    # Una consulta agrupada encuentra a los que comparten persona y plan. Son
    # poquísimos —son altas dobles reales de PRD— y el resto del trabajo se hace
    # sobre un puñado de filas.
    repetidos = [
        (fila["documento"], fila["id_programa"])
        for fila in completos.values("documento", "id_programa").annotate(cuantas=Count("id")).filter(cuantas__gt=1)
    ]
    cruzados = {}
    for inicio in range(0, len(repetidos), LOTE):
        condicion = models.Q()
        for documento, id_programa in repetidos[inicio : inicio + LOTE]:
            condicion |= models.Q(documento=documento, id_programa=id_programa)
        for pk, formulario_id, documento, id_programa, creado in completos.filter(condicion).values_list(
            "pk", "formulario_id", "documento", "id_programa", "creado"
        ):
            cruzados.setdefault(f"{documento}:{id_programa}", []).append((creado, pk, formulario_id))

    # El UPDATE masivo va por rangos de pk —una consulta acotada por vez, como
    # el resto de la migración— y saltea los repetidos.
    repetidas_pks = {pk for envios in cruzados.values() for _, pk, _ in envios}
    ultimo = 0
    while True:
        tramo = list(completos.filter(pk__gt=ultimo).order_by("pk").values_list("pk", flat=True)[:PAGINA])
        if not tramo:
            break
        limpios = [pk for pk in tramo if pk not in repetidas_pks]
        if limpios:
            EnvioSIIS.objects.filter(pk__in=limpios).update(clave_persona_plan=clave)
        ultimo = tramo[-1]

    if not cruzados:
        return
    # De cada grupo se queda con la clave el más viejo; los demás la pierden pero
    # **siguen vigentes**: liberarlos los devolvería a la lista de candidatos y
    # la próxima corrida mandaría una tercera alta de la misma persona.
    for envios in cruzados.values():
        envios.sort()
        EnvioSIIS.objects.filter(pk=envios[0][1]).update(clave_persona_plan=clave)

    print(
        f"\n  ATENCION: {len(cruzados)} persona(s) ya figuran con mas de un alta vigente en el mismo plan, "
        "desde casos distintos. Los casos quedan TODOS tomados a proposito (liberar uno mandaria una tercera "
        "alta); el duplicado hay que depurarlo del lado de SIIS. Queda tambien en la traza de cada caso."
    )
    trazas = []
    for numero, (clave, envios) in enumerate(sorted(cruzados.items())):
        documento, _, plan = clave.partition(":")
        lista = ", ".join(f"EnvioSIIS {pk} (caso #{caso})" for _, pk, caso in sorted(envios))
        if numero < TOPE_LISTADO:
            print(f"    DNI {documento} - plan {plan}: {lista}")
        for _, _, caso in envios:
            trazas.append((caso, f"alta duplicada entre casos al migrar (DNI {documento}, plan {plan}): {lista}"))
    if len(cruzados) > TOPE_LISTADO:
        print(f"    ... y {len(cruzados) - TOPE_LISTADO} mas (todos quedan en la traza de sus casos)")
    _trazar(apps, trazas)


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
        f"\n  ATENCION: {len(ambiguos)} envio(s) de resultado desconocido quedaron como ENVIADO para que "
        "ningun camino los reenvie. Hay que preguntarle a ECOM si llegaron:"
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
            name="clave_persona_plan",
            field=models.CharField(blank=True, editable=False, max_length=40, null=True),
        ),
        migrations.AddField(
            model_name="enviosiis",
            name="resuelto_en",
            field=models.DateTimeField(blank=True, null=True),
        ),
        # Va antes de los índices únicos: si quedaran dos ``vigente=True`` del
        # mismo caso —o dos claves iguales—, el ALTER TABLE fallaría y dejaría el
        # esquema a medias (el DDL de MySQL no es transaccional).
        migrations.RunPython(poblar_vigente, revertir_vigente),
        migrations.AddConstraint(
            model_name="enviosiis",
            constraint=models.UniqueConstraint(fields=("formulario", "vigente"), name="uniq_enviosiis_vigente_caso"),
        ),
        migrations.AddConstraint(
            model_name="enviosiis",
            constraint=models.UniqueConstraint(fields=("clave_persona_plan",), name="uniq_enviosiis_persona_plan"),
        ),
        migrations.AddIndex(
            model_name="enviosiis",
            index=models.Index(fields=["documento", "id_programa"], name="idx_enviosiis_doc_plan"),
        ),
    ]
