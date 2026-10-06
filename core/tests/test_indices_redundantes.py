"""RED-83 · Ningún índice es prefijo de otro del mismo modelo.

Un índice cuyas columnas son el prefijo exacto de otro no aporta nada: el motor usa el
más largo para las dos consultas. Lo que sí hace es costar en cada `INSERT`, `UPDATE` y
`DELETE`, ocupar buffer pool y alargar el `ALTER` de una tabla grande
(`programas_formulario` ronda los 283 MB).

`information_schema.STATISTICS` en MariaDB 11.8 encontró cinco pares, los cinco
declarados a mano en los modelos (la auditoría los verificó contra la base real). La
migración que los saca es de la Ola 4; lo que este test aporta es el **ratchet**: la
lista de abajo fija lo que hay hoy y solo puede achicarse. Un par nuevo pone el test en
rojo en el PR que lo agrega, que es donde cuesta un minuto arreglarlo.

Qué se mira: lo que el modelo **declara**. `db_index=True`, `unique=True`,
`Meta.indexes`, `Meta.constraints` (los `UniqueConstraint` con `fields`) y
`Meta.unique_together`. Los índices que Django crea solo por ser una FK quedan afuera a
propósito: son parte de la foreign key, no una decisión de quien escribió el modelo.
"""

from django.apps import apps
from django.conf import settings
from django.db import models
from django.test import SimpleTestCase

# Las apps del proyecto (las de terceros no se tocan desde acá).
APPS_DEL_PROYECTO = (
    "conversaciones",
    "core",
    "dashboard",
    "legajos",
    "portal",
    "programas",
    "users",
)

# Ratchet (RED-83). Cada fila es «modelo: (índice chico) dentro de (índice largo)».
# **Esta lista solo baja.** La Ola 4 saca los cinco medidos con `AlterField` (sin
# `db_index`) + `RemoveIndex` por par; cada par que se vaya tiene que salir también de
# acá, y hay un test que lo exige para que la lista no se convierta en una mentira cómoda.
#
# Los cinco que la auditoría midió contra la base (marcados **RED-83**) son los de
# `programas_formulario` y `legajos_ciudadano`, las dos tablas que miró. Los otros 21
# salieron de recorrer los modelos de todas las apps del proyecto: son el mismo defecto
# en tablas chicas, deuda conocida y sin medir.
REDUNDANTES_CONOCIDOS = {
    "conversaciones.colaasignacion: (activo) dentro de (activo, conversaciones_actuales)",
    "conversaciones.conversacion: (dni_ciudadano) dentro de (dni_ciudadano)",
    "conversaciones.conversacion: (estado) dentro de (estado, prioridad)",
    "conversaciones.conversacion: (fecha_cierre) dentro de (fecha_cierre)",
    "conversaciones.conversacion: (fecha_inicio) dentro de (fecha_inicio)",
    "conversaciones.conversacion: (satisfaccion) dentro de (satisfaccion)",
    "conversaciones.conversacion: (tipo) dentro de (tipo, estado)",
    "conversaciones.mensaje: (remitente) dentro de (remitente, leido)",
    "legajos.alertaciudadano: (activa) dentro de (activa, prioridad, creado)",
    "legajos.alertaciudadano: (tipo) dentro de (tipo, prioridad)",
    "legajos.ciudadano: (activo) dentro de (activo, apellido, nombre, dni, creado)",  # RED-83
    "legajos.ciudadano: (apellido) dentro de (apellido, nombre)",  # RED-83
    "legajos.ciudadano: (dni) dentro de (dni)",  # RED-83
    "legajos.ciudadano: (email) dentro de (email)",  # RED-83
    "legajos.legajoatencion: (nivel_riesgo) dentro de (nivel_riesgo, fecha_admision)",
    "legajos.legajoatencion: (plan_vigente) dentro de (plan_vigente, estado)",
    "legajos.legajoatencion: (via_ingreso) dentro de (via_ingreso, fecha_admision)",
    "programas.admision: (cama) dentro de (cama, estado)",
    "programas.derivacionprograma: (estado) dentro de (estado, urgencia)",
    "programas.dispositivo: (nombre) dentro de (nombre, estado)",
    "programas.dispositivo: (nombre) dentro de (nombre, localidad)",
    "programas.formulario: (estado) dentro de (estado)",  # RED-83
    "programas.inscripcionprograma: (estado) dentro de (estado, fecha_inscripcion)",
    "programas.merendero: (nombre) dentro de (nombre, estado)",
    "programas.programa: (estado) dentro de (estado, orden)",
    "programas.relevamiento: (estado) dentro de (estado, fecha_asignada, fecha_hasta)",
}


def _columnas(index_or_fields):
    return tuple(campo.lstrip("-+") for campo in index_or_fields)


def _declaraciones(modelo):
    """Los índices que el modelo declara: ``(columnas, de dónde sale)``."""
    declarado = []

    for campo in modelo._meta.local_fields:
        if campo.primary_key or campo.is_relation:
            continue
        if campo.unique:
            declarado.append(((campo.name,), "unique=True"))
        elif campo.db_index:
            declarado.append(((campo.name,), "db_index=True"))

    for indice in modelo._meta.indexes:
        if indice.fields:  # los funcionales (`expressions`) no se comparan por columnas
            declarado.append((_columnas(indice.fields), f"Meta.indexes[{indice.name}]"))

    for restriccion in modelo._meta.constraints:
        if isinstance(restriccion, models.UniqueConstraint) and restriccion.fields:
            declarado.append((_columnas(restriccion.fields), f"Meta.constraints[{restriccion.name}]"))

    for juntos in modelo._meta.unique_together:
        declarado.append((_columnas(juntos), "Meta.unique_together"))

    return declarado


def _redundantes(modelo):
    etiqueta = modelo._meta.label_lower
    declarado = _declaraciones(modelo)
    hallazgos = set()

    for posicion, (columnas, _) in enumerate(declarado):
        for otra_posicion, (otras, _) in enumerate(declarado):
            if posicion == otra_posicion or len(columnas) > len(otras):
                continue
            # Dos declaraciones idénticas: gana la primera, para no contar el par dos veces.
            if columnas == otras and posicion > otra_posicion:
                continue
            if otras[: len(columnas)] == columnas:
                hallazgos.add(f"{etiqueta}: ({', '.join(columnas)}) dentro de ({', '.join(otras)})")

    return hallazgos


def _modelos_del_proyecto():
    for modelo in apps.get_models():
        if modelo._meta.app_label in APPS_DEL_PROYECTO and not modelo._meta.proxy:
            yield modelo


class IndicesRedundantesTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.medidos = set()
        for modelo in _modelos_del_proyecto():
            cls.medidos |= _redundantes(modelo)

    def test_no_hay_indices_prefijo_de_otro(self):
        nuevos = sorted(self.medidos - REDUNDANTES_CONOCIDOS)

        self.assertEqual(
            nuevos,
            [],
            "índices redundantes nuevos: el más corto no aporta nada y se paga en cada "
            "escritura.\n" + "\n".join(nuevos),
        )

    def test_la_lista_conocida_no_tiene_entradas_muertas(self):
        """Si un par se arregló, su fila sale de la lista en el mismo PR: el ratchet baja."""
        muertas = sorted(REDUNDANTES_CONOCIDOS - self.medidos)

        self.assertEqual(
            muertas,
            [],
            "estos pares ya no existen: sacalos de REDUNDANTES_CONOCIDOS.\n" + "\n".join(muertas),
        )

    def test_la_regla_detecta_un_prefijo_plantado(self):
        """Sin esto, un bug en el detector dejaría el ratchet en verde para siempre."""

        class ConIndiceRedundante(models.Model):
            estado = models.CharField(max_length=10, db_index=True)
            creado = models.DateTimeField()

            class Meta:
                app_label = "core"
                indexes = [models.Index(fields=["estado", "creado"], name="prueba_estado_creado_idx")]

        self.assertEqual(
            _redundantes(ConIndiceRedundante),
            {"core.conindiceredundante: (estado) dentro de (estado, creado)"},
        )

    def test_la_regla_no_marca_indices_que_no_se_solapan(self):
        class SinRedundancia(models.Model):
            estado = models.CharField(max_length=10, db_index=True)
            creado = models.DateTimeField()

            class Meta:
                app_label = "core"
                indexes = [models.Index(fields=["creado", "estado"], name="prueba_creado_estado_idx")]

        self.assertEqual(_redundantes(SinRedundancia), set())

    def test_las_apps_declaradas_existen(self):
        instaladas = {app.label for app in apps.get_app_configs()}

        for etiqueta in APPS_DEL_PROYECTO:
            with self.subTest(app=etiqueta):
                self.assertIn(etiqueta, instaladas)
                self.assertIn(etiqueta, settings.INSTALLED_APPS)
