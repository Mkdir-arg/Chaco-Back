# Proceso masivo a SIIS — plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** una pantalla no listada del backoffice que dispara, para un programa, el circuito validar en SIIS → aprobar → informar el alta, con avance visible y freno.

**Architecture:** el bucle que hoy vive en el comando `procesar_casos_siis` se muda a `programas/services/proceso_masivo.py`; el comando y la vista nueva lo llaman igual. Una fila de `CorridaSiis` guarda el pedido, el avance y un latido. La vista lanza un hilo que ejecuta el servicio y va escribiendo en esa fila; la pantalla la lee cada cinco segundos.

**Tech Stack:** Django 5.2, Python 3.12, MySQL 8, Tailwind compilado, Alpine.js. Sin cola de tareas: el hilo es `threading.Thread(daemon=True)`.

**Spec:** [`docs/superpowers/specs/2026-09-22-proceso-masivo-siis-design.md`](../specs/2026-09-22-proceso-masivo-siis-design.md)

## Global Constraints

- Todo `python` va por el venv: `& $env:PY_VENV manage.py ...`. Tests con el runner de Django, **no pytest**:
  `$env:PYTEST_RUNNING="1"; $env:DJANGO_SYNCDB_PROJECT_APPS="True"; & $env:PY_VENV manage.py test programas`
- Modelos nuevos heredan de `core.models.TimeStamped`. Migración inmediata; el CI falla si falta.
- Templates del backoffice extienden `includes/base.html`. Inputs con la clase `nodo-field`. Botones `btn-nodo btn-brand` / `btn-tertiary` / `btn-danger`.
- Nada de `confirm()` nativo: confirmaciones con SweetAlert2.
- Al tocar UI: `scripts/design_audit.py --changed` en **0 errores** y `scripts/compile_templates.py` en 0. Comentarios de template multilínea van con `{% comment %}`, nunca `{# #}`.
- Autorización **solo por capacidad**, nunca por nombre de grupo. Agregar una capacidad implica tocar el `CATALOGO` de `core/rbac.py`, que es la fuente única.
- Al terminar todo: entrada nueva en `docs/internal/requerimientos.md` y `scripts/requerimientos.py --check` en OK.
- Ruff: `ruff check .` y `ruff format .`, line-length 120.

---

### Task 1: Modelo `CorridaSiis`

**Files:**
- Modify: `programas/models/__init__.py` (agregar al final, después de `EnvioSIIS`)
- Create: `programas/migrations/0071_corrida_siis.py` (generada, no escrita a mano)
- Test: `programas/tests/test_proceso_masivo.py`

**Interfaces:**
- Consumes: `ProgramaSiis` (ya existe), `core.models.TimeStamped`
- Produces:
  - `CorridaSiis.Estado` = `EN_CURSO` | `TERMINADA` | `CANCELADA` | `DETENIDA`
  - `CorridaSiis.interrumpida` → `bool` (propiedad)
  - `CorridaSiis.salteados` → `int` (propiedad)
  - `CorridaSiis.en_curso()` → `CorridaSiis | None` (classmethod)
  - Contadores enteros: `mirados`, `elegidos`, `aprobados`, `lista_espera`, `altas`, `incompletos`, `rechazados`, `errores`

- [ ] **Step 1: Escribir los tests que fallan**

Crear `programas/tests/test_proceso_masivo.py`:

```python
"""Proceso masivo a SIIS: registro de la corrida, servicio y pantalla."""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from programas.models import CorridaSiis, ProgramaSiis


class CorridaSiisTests(TestCase):
    def setUp(self):
        self.programa = ProgramaSiis.objects.create(nombre="Ñachec", siis_programa_id=79)

    def _corrida(self, **kwargs):
        return CorridaSiis.objects.create(programa=self.programa, total_pedido=1000, **kwargs)

    def test_una_corrida_recien_creada_no_esta_interrumpida(self):
        corrida = self._corrida(latido=timezone.now())
        self.assertFalse(corrida.interrumpida)

    def test_el_latido_viejo_la_marca_interrumpida(self):
        """Nadie escribe «me morí»: la interrupción se deduce del latido."""
        corrida = self._corrida(latido=timezone.now() - timedelta(minutes=5))
        self.assertTrue(corrida.interrumpida)

    def test_una_corrida_terminada_nunca_esta_interrumpida(self):
        corrida = self._corrida(
            estado=CorridaSiis.Estado.TERMINADA, latido=timezone.now() - timedelta(hours=3)
        )
        self.assertFalse(corrida.interrumpida)

    def test_sin_latido_se_mide_desde_que_se_creo(self):
        corrida = self._corrida()
        self.assertFalse(corrida.interrumpida)

    def test_en_curso_devuelve_la_corrida_viva(self):
        corrida = self._corrida(latido=timezone.now())
        self.assertEqual(CorridaSiis.en_curso(), corrida)

    def test_en_curso_ignora_una_interrumpida(self):
        """Un pod muerto hace diez minutos no puede dejar el sistema trabado."""
        self._corrida(latido=timezone.now() - timedelta(minutes=30))
        self.assertIsNone(CorridaSiis.en_curso())

    def test_salteados_es_la_diferencia_entre_mirados_y_elegidos(self):
        corrida = self._corrida(mirados=1600, elegidos=1000)
        self.assertEqual(corrida.salteados, 600)
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

```powershell
$env:PYTEST_RUNNING="1"; $env:DJANGO_SYNCDB_PROJECT_APPS="True"
& $env:PY_VENV manage.py test programas.tests.test_proceso_masivo
```

Esperado: `ImportError: cannot import name 'CorridaSiis' from 'programas.models'`

- [ ] **Step 3: Agregar el modelo**

En `programas/models/__init__.py`, después de la clase `EnvioSIIS`. Verificar que `timedelta` esté importado arriba (`from datetime import timedelta`); si no, agregarlo.

```python
class CorridaSiis(TimeStamped):
    """Una ejecución masiva del circuito validar → aprobar → informar el alta.

    Es lo que la pantalla lee para mostrar el avance, y lo que impide que se
    lancen dos a la vez. El proceso corre en un hilo del pod; por eso lo que
    importa acá es el **latido**: cuando el pod se recicla no queda nadie para
    escribir que murió, así que la interrupción se deduce de un latido viejo en
    vez de guardarse como estado. Un estado que depende de que lo escriba el
    proceso caído es un estado que nunca se ve.
    """

    class Estado(models.TextChoices):
        EN_CURSO = "EN_CURSO", "En curso"
        TERMINADA = "TERMINADA", "Terminada"
        CANCELADA = "CANCELADA", "Cancelada"
        DETENIDA = "DETENIDA", "Detenida"

    # Sin señal por más de esto, se da por interrumpida. Dos minutos es holgado:
    # un lote de 40 casos contra SIIS tarda bastante menos.
    LATIDO_VENCIDO = timedelta(minutes=2)

    programa = models.ForeignKey(ProgramaSiis, on_delete=models.CASCADE, related_name="corridas_siis")
    solicitada_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="corridas_siis_solicitadas"
    )
    total_pedido = models.PositiveIntegerField(verbose_name="Casos a procesar")
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.EN_CURSO, db_index=True)
    latido = models.DateTimeField(null=True, blank=True, verbose_name="Última señal de vida")
    cancelacion_pedida = models.BooleanField(default=False, verbose_name="Se pidió frenar")
    finalizada = models.DateTimeField(null=True, blank=True)
    mensaje = models.TextField(blank=True, default="", verbose_name="Por qué terminó")

    mirados = models.PositiveIntegerField(default=0)
    elegidos = models.PositiveIntegerField(default=0)
    aprobados = models.PositiveIntegerField(default=0)
    lista_espera = models.PositiveIntegerField(default=0)
    altas = models.PositiveIntegerField(default=0)
    incompletos = models.PositiveIntegerField(default=0)
    rechazados = models.PositiveIntegerField(default=0)
    errores = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Corrida masiva a SIIS"
        verbose_name_plural = "Corridas masivas a SIIS"
        ordering = ["-creado"]

    def __str__(self):
        return f"{self.programa.nombre} · {self.get_estado_display()} · {self.elegidos}/{self.total_pedido}"

    @property
    def interrumpida(self):
        """¿Dice que corre pero hace rato que no da señales?"""
        if self.estado != self.Estado.EN_CURSO:
            return False
        referencia = self.latido or self.creado
        return timezone.now() - referencia > self.LATIDO_VENCIDO

    @property
    def salteados(self):
        """Candidatos que se miraron y se descartaron por datos faltantes."""
        return max(self.mirados - self.elegidos, 0)

    @property
    def progreso(self):
        """Porcentaje 0-100 para la barra de avance."""
        if not self.total_pedido:
            return 0
        return min(int(self.elegidos * 100 / self.total_pedido), 100)

    @classmethod
    def en_curso(cls):
        """La corrida viva, o ``None``.

        Una interrumpida **no** cuenta: no hay nadie ejecutándola, así que no
        puede bloquear el lanzamiento de otra.
        """
        for corrida in cls.objects.filter(estado=cls.Estado.EN_CURSO).order_by("-creado"):
            if not corrida.interrumpida:
                return corrida
        return None
```

- [ ] **Step 4: Generar la migración**

```powershell
& $env:PY_VENV manage.py makemigrations programas --name corrida_siis
```

Esperado: `programas/migrations/0071_corrida_siis.py` con `Create model CorridaSiis`.

- [ ] **Step 5: Correr los tests y verificar que pasan**

```powershell
& $env:PY_VENV manage.py test programas.tests.test_proceso_masivo
```

Esperado: 7 tests OK.

- [ ] **Step 6: Verificar que no falta ninguna migración**

```powershell
& $env:PY_VENV manage.py makemigrations --check --dry-run
```

Esperado: `No changes detected`

- [ ] **Step 7: Commit**

```bash
git add programas/models/__init__.py programas/migrations/0071_corrida_siis.py programas/tests/test_proceso_masivo.py
git commit -m "feat(becas): registro de la corrida masiva a SIIS

La interrupcion se deduce de un latido viejo y no se guarda como estado: cuando
el pod se recicla no queda nadie para escribir que murio. Por lo mismo, una
corrida interrumpida no bloquea el lanzamiento de otra."
```

---

### Task 2: Servicio `proceso_masivo` (extracción del comando)

**Files:**
- Create: `programas/services/proceso_masivo.py`
- Modify: `programas/management/commands/procesar_casos_siis.py` (borrar `_casos`, `_elegir`, `_procesar`; llamar al servicio)
- Test: `programas/tests/test_proceso_masivo.py` (agregar clase)

**Interfaces:**
- Consumes: `armar_payload`, `Catalogos`, `CatalogoNoDisponible`, `enviar_beneficiario_a_siis` (de `programas.services.siis_envio`); `validar_formulario_en_siis`; `aprobar_o_poner_en_espera`; `enviar_aviso_resolucion`
- Produces:
  - `LOTE = 40`, `MAX_ERRORES = 10`
  - `class Cuenta` — dataclass con los enteros `mirados`, `elegidos`, `aprobados`, `lista_espera`, `no_aprobable`, `sin_datos`, `error_validacion`, `altas`, `incompletos`, `rechazados`, `errores`
  - `candidatos(*, programa=None, convocatoria=None, relevamiento=None, segmento=None, solo_enviar=False) -> QuerySet[Formulario]`
  - `elegir_completos(casos, catalogos, total, cuenta) -> tuple[list[Formulario], dict[str, int]]`
  - `procesar_caso(caso, responsable, catalogos, cuenta, *, avisar=False, solo_enviar=False) -> str | None` (devuelve `"tecnico"` o `None`)

- [ ] **Step 1: Escribir los tests que fallan**

Agregar al final de `programas/tests/test_proceso_masivo.py`:

```python
from datetime import date
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command

from legajos.models import Ciudadano
from programas.models import Convocatoria, EnvioSIIS, Formulario, Relevamiento, Segmento
from programas.services import proceso_masivo


class _BaseProcesoTest(TestCase):
    def setUp(self):
        call_command("seed_becas", stdout=StringIO())
        self.programa = ProgramaSiis.objects.create(
            nombre="Ñachec", siis_programa_id=79, siis_funcion_id=4
        )
        self.segmento = Segmento.objects.create(nombre="Seg", cupo_maximo=100, programa=self.programa)
        self.convocatoria = Convocatoria.objects.create(
            nombre="Conv",
            segmento=self.segmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        self.user = User.objects.create_user("coord_masivo", password="x")
        self.relevamiento = Relevamiento.objects.create(
            convocatoria=self.convocatoria,
            territorial=self.user,
            fecha_asignada=date(2026, 6, 1),
            zona="A",
        )
        self.ciudadano = Ciudadano.objects.create(
            dni="20301234", nombre="Juan", apellido="Perez", fecha_nacimiento=date(1995, 6, 15), genero="M"
        )

    def _caso(self, estado=Formulario.Estado.ENVIADO):
        return Formulario.objects.create(
            relevamiento=self.relevamiento, ciudadano=self.ciudadano, estado=estado
        )


class CandidatosTests(_BaseProcesoTest):
    def test_toma_los_enviados_y_los_aprobados(self):
        enviado = self._caso()
        aprobado = self._caso(Formulario.Estado.APROBADO)
        self._caso(Formulario.Estado.RECHAZADO)
        encontrados = set(proceso_masivo.candidatos(programa=self.programa).values_list("pk", flat=True))
        self.assertEqual(encontrados, {enviado.pk, aprobado.pk})

    def test_saltea_el_que_ya_tiene_alta(self):
        caso = self._caso(Formulario.Estado.APROBADO)
        EnvioSIIS.objects.create(formulario=caso, estado=EnvioSIIS.Estado.ENVIADO, documento="1")
        self.assertFalse(proceso_masivo.candidatos(programa=self.programa).exists())

    def test_incluye_al_que_nunca_se_mando(self):
        """Sin envio el ultimo estado es NULL, y un exclude lo descartaria."""
        caso = self._caso(Formulario.Estado.APROBADO)
        self.assertIn(caso.pk, proceso_masivo.candidatos(programa=self.programa).values_list("pk", flat=True))

    def test_saltea_el_duplicado_sin_resolver(self):
        caso = self._caso()
        caso.conflicto_duplicado = True
        caso.conflicto_resuelto = False
        caso.save(update_fields=["conflicto_duplicado", "conflicto_resuelto"])
        self.assertFalse(proceso_masivo.candidatos(programa=self.programa).exists())


class ElegirCompletosTests(_BaseProcesoTest):
    def test_junta_el_total_salteando_los_incompletos(self):
        """El total cuenta casos que se mandan, no casos que se miran."""
        casos = [self._caso() for _ in range(3)]
        cuenta = proceso_masivo.Cuenta()
        with patch("programas.services.proceso_masivo.armar_payload") as armar:
            armar.side_effect = [({}, {"nro_actual": "falta"}), ({}, {}), ({}, {})]
            elegidos, descartados = proceso_masivo.elegir_completos(casos, None, 2, cuenta)
        self.assertEqual([c.pk for c in elegidos], [casos[1].pk, casos[2].pk])
        self.assertEqual(descartados, {"nro_actual": 1})
        self.assertEqual(cuenta.mirados, 3)
        self.assertEqual(cuenta.elegidos, 2)

    def test_si_no_alcanzan_devuelve_los_que_hay(self):
        casos = [self._caso()]
        cuenta = proceso_masivo.Cuenta()
        with patch("programas.services.proceso_masivo.armar_payload") as armar:
            armar.return_value = ({}, {})
            elegidos, _ = proceso_masivo.elegir_completos(casos, None, 50, cuenta)
        self.assertEqual(len(elegidos), 1)
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

```powershell
& $env:PY_VENV manage.py test programas.tests.test_proceso_masivo.CandidatosTests
```

Esperado: `ModuleNotFoundError: No module named 'programas.services.proceso_masivo'`

- [ ] **Step 3: Escribir el servicio**

Crear `programas/services/proceso_masivo.py`:

```python
"""Circuito masivo de Becas: validar en SIIS, aprobar e informar el alta.

Es el mismo camino que los botones de la pantalla de revisión, caso por caso.
Vive acá —y no dentro del comando— porque lo usan dos disparadores: el comando
``procesar_casos_siis`` y la pantalla del proceso masivo. Una segunda
implementación se habría desincronizado con la primera regla que cambiara.
"""

from dataclasses import dataclass, field

from django.core.exceptions import ValidationError
from django.db.models import OuterRef, Q, Subquery

from programas.models import EnvioSIIS, Formulario, ValidacionSIS
from programas.services.avisos_resolucion import enviar_aviso_resolucion
from programas.services.cupo import aprobar_o_poner_en_espera
from programas.services.siis_envio import (
    CatalogoNoDisponible,
    armar_payload,
    enviar_beneficiario_a_siis,
)
from programas.services.validacion_siis import validar_formulario_en_siis

LOTE = 40
MAX_ERRORES = 10


@dataclass
class Cuenta:
    """Los desenlaces de una corrida. Se acumulan y se vuelcan a ``CorridaSiis``."""

    mirados: int = 0
    elegidos: int = 0
    aprobados: int = 0
    lista_espera: int = 0
    no_aprobable: int = 0
    sin_datos: int = 0
    error_validacion: int = 0
    altas: int = 0
    incompletos: int = 0
    rechazados: int = 0
    errores: int = 0
    descartados: dict = field(default_factory=dict)


def candidatos(*, programa=None, convocatoria=None, relevamiento=None, segmento=None, solo_enviar=False):
    """Casos que todavía no se informaron a SIIS.

    Los ``ENVIADO`` (pendientes de resolución) y los ya ``APROBADO`` sin alta,
    para que una corrida cortada se retome sola. Se saltean los que tienen un
    conflicto de carga duplicada sin resolver: eso lo decide una persona, igual
    que en la pantalla de revisión.
    """
    ultimo = EnvioSIIS.objects.filter(formulario=OuterRef("pk")).order_by("-creado", "-id").values("estado")[:1]
    casos = (
        Formulario.objects.select_related(
            "ciudadano", "relevamiento__convocatoria__segmento__programa", "apoderado_ciudadano"
        )
        .annotate(ultimo_envio=Subquery(ultimo))
        # «Todavía no informado» incluye a los que no tienen ningún envío, y eso
        # es NULL: un ``exclude`` los descartaría a todos, porque
        # ``NOT (NULL = 'ENVIADO')`` no es verdadero.
        .filter(Q(ultimo_envio__isnull=True) | ~Q(ultimo_envio=EnvioSIIS.Estado.ENVIADO))
        .order_by("pk")
    )
    estados = [Formulario.Estado.APROBADO]
    if not solo_enviar:
        estados.append(Formulario.Estado.ENVIADO)
    casos = casos.filter(estado__in=estados)
    if programa is not None:
        casos = casos.filter(relevamiento__convocatoria__segmento__programa=programa)
    if convocatoria is not None:
        casos = casos.filter(relevamiento__convocatoria_id=convocatoria)
    if relevamiento is not None:
        casos = casos.filter(relevamiento_id=relevamiento)
    if segmento is not None:
        casos = casos.filter(relevamiento__convocatoria__segmento_id=segmento)
    casos = casos.exclude(Q(conflicto_duplicado=True) & Q(conflicto_resuelto=False)).exclude(
        cargas_en_conflicto__conflicto_resuelto=False
    )
    return casos.distinct()


def elegir_completos(casos, catalogos, total, cuenta):
    """``(elegidos, descartados_por_campo)``: los que hoy saldrían sin faltantes.

    El total cuenta casos que se **mandan**, no casos que se miran: se recorre
    hasta juntarlos, salteando sin tocar a los que les falta un dato. Mandar uno
    incompleto no lo informa a SIIS pero igual lo deja aprobado y con una fila de
    error para revisar a mano.
    """
    elegidos, descartados = [], {}
    for caso in casos:
        if len(elegidos) >= total:
            break
        cuenta.mirados += 1
        _, faltantes = armar_payload(caso, catalogos=catalogos)
        if faltantes:
            for campo in faltantes:
                descartados[campo] = descartados.get(campo, 0) + 1
            continue
        elegidos.append(caso)
        cuenta.elegidos += 1
    cuenta.descartados = descartados
    return elegidos, descartados


def procesar_caso(caso, responsable, catalogos, cuenta, *, avisar=False, solo_enviar=False):
    """Valida, aprueba e informa un caso. Devuelve ``"tecnico"`` si falló SIIS.

    Un caso que falla en un paso no avanza al siguiente y no interrumpe al resto.
    """
    if not solo_enviar:
        try:
            validacion = validar_formulario_en_siis(caso, responsable)
        except ValueError:
            # Sin programa SIIS o sin DNI: no hay consulta posible.
            cuenta.sin_datos += 1
            return None
        if validacion.estado == ValidacionSIS.Estado.ERROR:
            cuenta.error_validacion += 1
            return "tecnico"

        if caso.estado == Formulario.Estado.ENVIADO:
            try:
                resultado = aprobar_o_poner_en_espera(caso, responsable)
            except ValidationError:
                # Falta algo que la aprobación exige (identidad, validación que
                # no corresponde al programa actual…).
                cuenta.no_aprobable += 1
                return None
            if resultado == "lista_espera":
                # Sin cupo no hay beneficiario que informar.
                cuenta.lista_espera += 1
                if avisar:
                    enviar_aviso_resolucion(caso, resultado)
                return None
            cuenta.aprobados += 1
            if avisar:
                enviar_aviso_resolucion(caso, resultado)

    envio = enviar_beneficiario_a_siis(caso, responsable, catalogos=catalogos)
    if envio.estado == EnvioSIIS.Estado.ENVIADO:
        cuenta.altas += 1
    elif envio.estado == EnvioSIIS.Estado.INCOMPLETO:
        cuenta.incompletos += 1
    elif envio.estado == EnvioSIIS.Estado.RECHAZADO:
        cuenta.rechazados += 1
    else:
        cuenta.errores += 1
        return "tecnico"
    return None
```

- [ ] **Step 4: Correr los tests y verificar que pasan**

```powershell
& $env:PY_VENV manage.py test programas.tests.test_proceso_masivo
```

Esperado: 13 tests OK.

- [ ] **Step 5: Refactorizar el comando para que use el servicio**

En `programas/management/commands/procesar_casos_siis.py`:

1. Reemplazar el bloque de imports de servicios por:

```python
from programas.models import EnvioSIIS, Formulario
from programas.services import proceso_masivo
from programas.services.siis_envio import CatalogoNoDisponible, Catalogos
```

2. Borrar los métodos `_casos`, `_elegir` y `_procesar` de la clase `Command`.

3. Reemplazar `TOTAL_POR_DEFECTO = 1000` / `LOTE_POR_DEFECTO = 40` por:

```python
TOTAL_POR_DEFECTO = 1000
LOTE_POR_DEFECTO = proceso_masivo.LOTE
```

4. En `handle`, reemplazar la obtención de casos por:

```python
        catalogos = Catalogos()
        consulta = proceso_masivo.candidatos(
            convocatoria=options["convocatoria"],
            relevamiento=options["relevamiento"],
            segmento=options["segmento"],
            solo_enviar=options["solo_enviar"],
        )
        cuenta = proceso_masivo.Cuenta()
        if options["solo_completos"]:
            candidatos_lista = list(consulta)
            self._log(f"Candidatos pendientes: {len(candidatos_lista)}. Armando el payload de cada uno…")
            try:
                casos, descartados = proceso_masivo.elegir_completos(
                    candidatos_lista, catalogos, max(1, options["total"]), cuenta
                )
            except CatalogoNoDisponible as exc:
                raise CommandError(f"No se pudo leer un catálogo de SIIS: {exc}") from exc
        else:
            casos, descartados = list(consulta[: max(1, options["total"])]), {}
```

5. En el bucle de lotes, reemplazar la llamada a `self._procesar(...)` por:

```python
                if (
                    proceso_masivo.procesar_caso(
                        caso,
                        responsable,
                        catalogos,
                        cuenta,
                        avisar=options["avisar"],
                        solo_enviar=options["solo_enviar"],
                    )
                    == "tecnico"
                ):
```

6. Reemplazar los usos de `cuenta[...]` por atributos: `cuenta.altas`, `cuenta.incompletos`, `cuenta.rechazados`, `cuenta.errores`, `cuenta.aprobados`, `cuenta.lista_espera`, `cuenta.no_aprobable`, `cuenta.sin_datos`, `cuenta.error_validacion`. El diccionario `antes = dict(cuenta)` pasa a `antes = replace(cuenta)` — importar `from dataclasses import replace`.

- [ ] **Step 6: Correr la suite del comando y verificar que sigue verde**

```powershell
& $env:PY_VENV manage.py test programas.tests.test_siis_envio programas.tests.test_proceso_masivo
```

Esperado: todos OK. Los tests de `ComandoCircuitoCompletoTests` parchean `programas.management.commands.procesar_casos_siis.*`; los que ahora viven en el servicio hay que reapuntarlos a `programas.services.proceso_masivo.*`. Ajustar esos `patch(...)` y volver a correr.

- [ ] **Step 7: Lint y commit**

```powershell
& $env:PY_VENV -m ruff check .
& $env:PY_VENV -m ruff format .
```

```bash
git add programas/services/proceso_masivo.py programas/management/commands/procesar_casos_siis.py programas/tests/
git commit -m "refactor(becas): el circuito masivo a SIIS pasa a un servicio

Lo van a llamar dos disparadores: el comando y la pantalla del proceso masivo.
Dos implementaciones se habrian desincronizado con la primera regla que cambiara."
```

---

### Task 3: El servicio escribe la corrida (latido, contadores, freno)

**Files:**
- Modify: `programas/services/proceso_masivo.py`
- Test: `programas/tests/test_proceso_masivo.py`

**Interfaces:**
- Consumes: `CorridaSiis` (Task 1), `Cuenta`, `candidatos`, `elegir_completos`, `procesar_caso` (Task 2)
- Produces:
  - `correr(corrida, *, responsable=None, catalogos=None, lote=LOTE, max_errores=MAX_ERRORES) -> CorridaSiis` — sincrónico; nunca lanza
  - `lanzar(corrida, *, responsable=None, ejecutor=None) -> None` — `ejecutor` recibe un callable; el default lanza un hilo

- [ ] **Step 1: Escribir los tests que fallan**

Agregar a `programas/tests/test_proceso_masivo.py`:

```python
class CorrerTests(_BaseProcesoTest):
    def setUp(self):
        super().setUp()
        self.parches = {
            nombre: patch(f"programas.services.proceso_masivo.{nombre}").start()
            for nombre in ("armar_payload", "validar_formulario_en_siis", "aprobar_o_poner_en_espera",
                           "enviar_beneficiario_a_siis", "enviar_aviso_resolucion")
        }
        self.addCleanup(patch.stopall)
        self.parches["armar_payload"].return_value = ({}, {})
        self.parches["validar_formulario_en_siis"].side_effect = lambda f, u: ValidacionSIS.objects.create(
            formulario=f, estado=ValidacionSIS.Estado.OK, documento="1", id_programa=79
        )
        self.parches["aprobar_o_poner_en_espera"].side_effect = lambda f, u: "aprobado"
        self.parches["enviar_beneficiario_a_siis"].side_effect = lambda f, u, **kw: EnvioSIIS.objects.create(
            formulario=f, estado=EnvioSIIS.Estado.ENVIADO, documento="1", siis_id=1
        )

    def _corrida(self, total=10):
        return CorridaSiis.objects.create(programa=self.programa, total_pedido=total)

    def test_termina_y_cuenta_las_altas(self):
        for _ in range(3):
            self._caso()
        corrida = proceso_masivo.correr(self._corrida(), lote=2)
        self.assertEqual(corrida.estado, CorridaSiis.Estado.TERMINADA)
        self.assertEqual(corrida.altas, 3)
        self.assertEqual(corrida.aprobados, 3)
        self.assertIsNotNone(corrida.finalizada)

    def test_escribe_el_latido_en_cada_lote(self):
        for _ in range(3):
            self._caso()
        corrida = proceso_masivo.correr(self._corrida(), lote=2)
        self.assertIsNotNone(corrida.latido)

    def test_frenar_corta_al_cerrar_el_lote(self):
        for _ in range(4):
            self._caso()
        corrida = self._corrida()
        # Alguien aprieta Frenar mientras corre el primer lote.
        def marcar(f, u, **kw):
            CorridaSiis.objects.filter(pk=corrida.pk).update(cancelacion_pedida=True)
            return EnvioSIIS.objects.create(formulario=f, estado=EnvioSIIS.Estado.ENVIADO, documento="1")

        self.parches["enviar_beneficiario_a_siis"].side_effect = marcar
        resultado = proceso_masivo.correr(corrida, lote=2)
        self.assertEqual(resultado.estado, CorridaSiis.Estado.CANCELADA)
        # Corto al cerrar el lote, no a mitad: procesó los 2 del primer lote.
        self.assertEqual(resultado.altas, 2)

    def test_se_detiene_tras_errores_tecnicos_seguidos(self):
        for _ in range(4):
            self._caso()
        self.parches["enviar_beneficiario_a_siis"].side_effect = lambda f, u, **kw: EnvioSIIS.objects.create(
            formulario=f, estado=EnvioSIIS.Estado.ERROR, documento="1", codigo_error="ERROR_TECNICO"
        )
        corrida = proceso_masivo.correr(self._corrida(), lote=10, max_errores=2)
        self.assertEqual(corrida.estado, CorridaSiis.Estado.DETENIDA)
        self.assertIn("SIIS", corrida.mensaje)

    def test_el_catalogo_caido_la_detiene_con_el_motivo(self):
        self._caso()
        self.parches["armar_payload"].side_effect = CatalogoNoDisponible("el servicio no responde")
        corrida = proceso_masivo.correr(self._corrida())
        self.assertEqual(corrida.estado, CorridaSiis.Estado.DETENIDA)
        self.assertIn("no responde", corrida.mensaje)

    def test_una_excepcion_no_prevista_queda_escrita(self):
        self._caso()
        self.parches["validar_formulario_en_siis"].side_effect = RuntimeError("algo raro")
        corrida = proceso_masivo.correr(self._corrida())
        self.assertEqual(corrida.estado, CorridaSiis.Estado.DETENIDA)
        self.assertIn("algo raro", corrida.mensaje)

    def test_sin_candidatos_termina_igual(self):
        corrida = proceso_masivo.correr(self._corrida())
        self.assertEqual(corrida.estado, CorridaSiis.Estado.TERMINADA)
        self.assertEqual(corrida.altas, 0)


class LanzarTests(_BaseProcesoTest):
    def test_el_ejecutor_se_inyecta(self):
        """En los tests corre sincrónico; sin eso serían una carrera."""
        corrida = CorridaSiis.objects.create(programa=self.programa, total_pedido=1)
        llamadas = []
        proceso_masivo.lanzar(corrida, ejecutor=lambda fn: llamadas.append(fn))
        self.assertEqual(len(llamadas), 1)
```

Agregar al import de modelos del archivo de tests: `CorridaSiis`, `ValidacionSIS`. Y `from programas.services.siis_envio import CatalogoNoDisponible`.

- [ ] **Step 2: Correr los tests y verificar que fallan**

```powershell
& $env:PY_VENV manage.py test programas.tests.test_proceso_masivo.CorrerTests
```

Esperado: `AttributeError: module 'programas.services.proceso_masivo' has no attribute 'correr'`

- [ ] **Step 3: Implementar `correr` y `lanzar`**

Agregar al final de `programas/services/proceso_masivo.py`. Sumar arriba los imports: `import threading`, `from django.db import connection`, `from django.utils import timezone`, `from programas.models import CorridaSiis`, `from programas.services.siis_envio import Catalogos`.

```python
def _lotes(lista, tamano):
    for inicio in range(0, len(lista), tamano):
        yield lista[inicio : inicio + tamano]


def _guardar(corrida, cuenta, **extra):
    """Vuelca los contadores y el latido. Cada lote deja su rastro en la base."""
    for campo in ("mirados", "elegidos", "aprobados", "lista_espera", "altas", "incompletos", "rechazados", "errores"):
        setattr(corrida, campo, getattr(cuenta, campo))
    corrida.latido = timezone.now()
    for campo, valor in extra.items():
        setattr(corrida, campo, valor)
    corrida.save()


def correr(corrida, *, responsable=None, catalogos=None, lote=LOTE, max_errores=MAX_ERRORES):
    """Ejecuta la corrida y va escribiendo su avance. **Nunca lanza.**

    Todo desenlace —incluida una excepción que no previmos— queda escrito en la
    corrida. Corre en un hilo: si dejara escapar una excepción, nadie la vería y
    la pantalla quedaría con una corrida «en curso» para siempre.

    No hay una transacción que envuelva todo a propósito. Cada caso se confirma
    solo; eso es lo que permite cortar y retomar, y lo que evita el cuelgue de
    una transacción larga contra una base remota.
    """
    catalogos = catalogos or Catalogos()
    cuenta = Cuenta()
    responsable = responsable or corrida.solicitada_por
    try:
        candidatos_lista = list(candidatos(programa=corrida.programa))
        casos, _ = elegir_completos(candidatos_lista, catalogos, corrida.total_pedido, cuenta)
        _guardar(corrida, cuenta)

        seguidos = 0
        for grupo in _lotes(casos, max(1, lote)):
            for caso in grupo:
                if procesar_caso(caso, responsable, catalogos, cuenta) == "tecnico":
                    seguidos += 1
                else:
                    seguidos = 0
            _guardar(corrida, cuenta)
            if seguidos >= max_errores:
                _guardar(
                    corrida,
                    cuenta,
                    estado=CorridaSiis.Estado.DETENIDA,
                    finalizada=timezone.now(),
                    mensaje=(
                        f"Se detuvo tras {max_errores} errores técnicos seguidos: SIIS no está respondiendo "
                        "o las credenciales no sirven. Lo hecho quedó; volvé a lanzarla cuando se recupere."
                    ),
                )
                return corrida
            # El freno se relee de la base: lo marca otro request.
            corrida.refresh_from_db(fields=["cancelacion_pedida"])
            if corrida.cancelacion_pedida:
                _guardar(
                    corrida,
                    cuenta,
                    estado=CorridaSiis.Estado.CANCELADA,
                    finalizada=timezone.now(),
                    mensaje="La frenaron desde la pantalla. Lo procesado quedó firme.",
                )
                return corrida

        _guardar(corrida, cuenta, estado=CorridaSiis.Estado.TERMINADA, finalizada=timezone.now())
        return corrida
    except CatalogoNoDisponible as exc:
        _guardar(
            corrida,
            cuenta,
            estado=CorridaSiis.Estado.DETENIDA,
            finalizada=timezone.now(),
            mensaje=f"No se pudo leer un catálogo de SIIS: {exc}",
        )
        return corrida
    except Exception as exc:  # noqa: BLE001 - la corrida es el único lugar donde se puede informar
        _guardar(
            corrida,
            cuenta,
            estado=CorridaSiis.Estado.DETENIDA,
            finalizada=timezone.now(),
            mensaje=f"Error no previsto: {exc}",
        )
        return corrida


def _en_un_hilo(funcion):
    threading.Thread(target=funcion, daemon=True).start()


def lanzar(corrida, *, responsable=None, ejecutor=None):
    """Arranca la corrida sin hacer esperar al request.

    ``ejecutor`` se inyecta para poder correr sincrónico en los tests: con el
    hilo de verdad, las pruebas serían una carrera.
    """
    def trabajo():
        try:
            correr(corrida, responsable=responsable)
        finally:
            # Django abre una conexión por hilo; sin esto queda colgada.
            connection.close()

    (ejecutor or _en_un_hilo)(trabajo)
```

- [ ] **Step 4: Correr los tests y verificar que pasan**

```powershell
& $env:PY_VENV manage.py test programas.tests.test_proceso_masivo
```

Esperado: 21 tests OK.

- [ ] **Step 5: Commit**

```bash
git add programas/services/proceso_masivo.py programas/tests/test_proceso_masivo.py
git commit -m "feat(becas): la corrida masiva escribe su avance, su latido y su freno

correr() nunca lanza: corre en un hilo, y una excepcion que escape dejaria la
corrida «en curso» para siempre sin que nadie sepa por que. El freno se relee de
la base porque lo marca otro request, y corta al cerrar el lote."
```

---

### Task 4: Pantalla no listada, capacidad y lanzamiento

**Files:**
- Modify: `core/rbac.py` (agregar la capacidad al `CATALOGO`)
- Create: `programas/views/proceso_masivo.py`
- Modify: `programas/urls.py` (dos rutas nuevas)
- Create: `programas/templates/programas/becas/config/proceso_masivo.html`
- Test: `programas/tests/test_proceso_masivo.py`

**Interfaces:**
- Consumes: `CorridaSiis` (Task 1), `proceso_masivo.candidatos` y `proceso_masivo.lanzar` (Tasks 2 y 3)
- Produces:
  - Capacidad `becas.programa.proceso_masivo`
  - URL `becas:proceso_masivo` → `/becas/config/programas/<int:pk>/proceso-masivo/`
  - URL `becas:proceso_masivo_lanzar` → `.../proceso-masivo/lanzar/`

- [ ] **Step 1: Escribir los tests que fallan**

Agregar a `programas/tests/test_proceso_masivo.py`:

```python
from django.urls import reverse

from core.rbac import CATALOGO


class PantallaProcesoMasivoTests(_BaseProcesoTest):
    CAP = "becas.programa.proceso_masivo"

    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_superuser("admin_masivo", password="x")
        self.client.force_login(self.admin)

    def _url(self, nombre="proceso_masivo"):
        return reverse(f"becas:{nombre}", args=[self.programa.pk])

    def test_la_capacidad_esta_en_el_catalogo(self):
        codigos = [c for modulo in CATALOGO for c, _ in modulo["capacidades"]]
        self.assertIn(self.CAP, codigos)

    def test_la_pantalla_abre_y_muestra_los_pendientes(self):
        self._caso()
        resp = self.client.get(self._url())
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Proceso masivo")

    def test_sin_la_capacidad_no_entra(self):
        """Un usuario sin la capacidad no llega, aunque sepa la URL."""
        otro = User.objects.create_user("sin_capacidad", password="x")
        self.client.force_login(otro)
        resp = self.client.get(self._url())
        self.assertIn(resp.status_code, (302, 403))

    def test_lanzar_crea_la_corrida_y_no_espera(self):
        self._caso()
        with patch("programas.views.proceso_masivo.servicio.lanzar") as lanzar:
            resp = self.client.post(self._url("proceso_masivo_lanzar"), {"total_pedido": "25"})
        self.assertEqual(resp.status_code, 302)
        corrida = CorridaSiis.objects.get()
        self.assertEqual(corrida.total_pedido, 25)
        self.assertEqual(corrida.solicitada_por, self.admin)
        lanzar.assert_called_once()

    def test_no_deja_lanzar_dos_a_la_vez(self):
        CorridaSiis.objects.create(programa=self.programa, total_pedido=10, latido=timezone.now())
        with patch("programas.views.proceso_masivo.servicio.lanzar") as lanzar:
            self.client.post(self._url("proceso_masivo_lanzar"), {"total_pedido": "10"})
        self.assertEqual(CorridaSiis.objects.count(), 1)
        lanzar.assert_not_called()

    def test_una_interrumpida_no_bloquea(self):
        CorridaSiis.objects.create(
            programa=self.programa, total_pedido=10, latido=timezone.now() - timedelta(minutes=30)
        )
        with patch("programas.views.proceso_masivo.servicio.lanzar"):
            self.client.post(self._url("proceso_masivo_lanzar"), {"total_pedido": "10"})
        self.assertEqual(CorridaSiis.objects.count(), 2)

    def test_un_total_invalido_no_crea_nada(self):
        with patch("programas.views.proceso_masivo.servicio.lanzar"):
            self.client.post(self._url("proceso_masivo_lanzar"), {"total_pedido": "0"})
        self.assertFalse(CorridaSiis.objects.exists())
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

```powershell
& $env:PY_VENV manage.py test programas.tests.test_proceso_masivo.PantallaProcesoMasivoTests
```

Esperado: `AssertionError` en la capacidad y `NoReverseMatch` en las URLs.

- [ ] **Step 3: Agregar la capacidad**

En `core/rbac.py`, dentro del módulo `becas_admin`, agregar a su lista `capacidades` una cuarta entrada, después de `becas.coordinador_regional`:

```python
            (
                "becas.programa.proceso_masivo",
                "Ejecutar el proceso masivo a SIIS (aprueba e informa altas en lote)",
            ),
```

No se asigna a ningún rol en el seed: se tilda a mano en el ABM de Roles.

- [ ] **Step 4: Escribir la vista**

Crear `programas/views/proceso_masivo.py`:

```python
"""Proceso masivo a SIIS: pantalla no listada para lanzar el circuito en lote.

No figura en ningún menú ni link, pero lo que la protege es la capacidad
``becas.programa.proceso_masivo``, no el hecho de estar escondida: esconder un
botón que aprueba mil casos y los registra en un sistema provincial es prolijidad,
no seguridad.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.views.generic.detail import DetailView

from core.rbac import CapacidadRequeridaMixin, requiere
from programas.models import CorridaSiis, ProgramaSiis
# Alias: este módulo ya se llama proceso_masivo; sin él, dentro del archivo
# `proceso_masivo` sería ambiguo para quien lo lea.
from programas.services import proceso_masivo as servicio

CAP_PROCESO_MASIVO = "becas.programa.proceso_masivo"
TOTAL_MAXIMO = 5000


class ProcesoMasivoView(CapacidadRequeridaMixin, LoginRequiredMixin, DetailView):
    model = ProgramaSiis
    capacidades_requeridas = CAP_PROCESO_MASIVO
    template_name = "programas/becas/config/proceso_masivo.html"
    context_object_name = "programa"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["corrida"] = CorridaSiis.objects.filter(programa=self.object).order_by("-creado").first()
        ctx["en_curso"] = CorridaSiis.en_curso()
        ctx["pendientes"] = servicio.candidatos(programa=self.object).count()
        ctx["total_maximo"] = TOTAL_MAXIMO
        return ctx


@login_required
@requiere(CAP_PROCESO_MASIVO)
@require_POST
def proceso_masivo_lanzar(request, pk):
    """Crea la corrida y devuelve enseguida: el trabajo sigue en un hilo."""
    programa = get_object_or_404(ProgramaSiis, pk=pk)
    destino = redirect("becas:proceso_masivo", pk=programa.pk)

    if CorridaSiis.en_curso() is not None:
        messages.error(request, "Ya hay una corrida en curso. Esperá a que termine o frenala.")
        return destino

    try:
        total = int(request.POST.get("total_pedido") or 0)
    except ValueError:
        total = 0
    if not 1 <= total <= TOTAL_MAXIMO:
        messages.error(request, f"La cantidad tiene que estar entre 1 y {TOTAL_MAXIMO}.")
        return destino

    corrida = CorridaSiis.objects.create(
        programa=programa, solicitada_por=request.user, total_pedido=total
    )
    servicio.lanzar(corrida, responsable=request.user)
    messages.success(request, f"Corrida lanzada por {total} casos.")
    return destino
```

- [ ] **Step 5: Agregar las URLs**

En `programas/urls.py`, después de la ruta `programa_identificadores_siis`:

```python
    path(
        "config/programas/<int:pk>/proceso-masivo/",
        masivo.ProcesoMasivoView.as_view(),
        name="proceso_masivo",
    ),
    path(
        "config/programas/<int:pk>/proceso-masivo/lanzar/",
        masivo.proceso_masivo_lanzar,
        name="proceso_masivo_lanzar",
    ),
```

Y en los imports del archivo, junto a los otros módulos de vistas:

```python
from programas.views import proceso_masivo as masivo
```

- [ ] **Step 6: Escribir la plantilla**

Crear `programas/templates/programas/becas/config/proceso_masivo.html`:

```html
{% extends "includes/base.html" %}
{% load rbac %}
{% block title %}Becas · Proceso masivo{% endblock %}

{% block main-content %}
<div class="mb-8 max-w-3xl">

  <div class="flex items-start gap-3 mb-6">
    <a href="{% url 'becas:programa_detalle' programa.pk %}"
       class="btn-tertiary btn-back-circle" aria-label="Volver al programa">
      <i class="fas fa-arrow-left" aria-hidden="true"></i>
    </a>
    <div class="min-w-0">
      <h1 class="font-extrabold text-heading" style="font-size:28px; letter-spacing:-0.5px">Proceso masivo</h1>
      <p class="text-sm text-body-subtle mt-1.5">{{ programa.nombre }}</p>
    </div>
  </div>

  <div class="rounded-lg bg-warning-soft border border-warning-subtle p-4 text-sm mb-6" role="alert">
    <strong class="text-heading">Esto aprueba casos y los da de alta en SIIS</strong>
    <p class="text-body mt-1">
      El alta no se puede deshacer desde acá. Cada caso se valida con SIIS, se aprueba y se informa.
    </p>
  </div>

  {% if en_curso %}
  <div class="bg-white rounded-xl border border-base shadow-sm p-5">
    <div class="flex items-center justify-between gap-4 flex-wrap mb-4">
      <p class="text-sm text-body-subtle">
        <span class="badge badge-success badge-dot">En curso</span>
        lanzada por {{ en_curso.solicitada_por.get_full_name|default:en_curso.solicitada_por.username }}
        · {{ en_curso.creado|timesince }} atrás
      </p>
      {% comment %}El botón Frenar llega en la Task 5, junto con su vista y su URL:
      una plantilla que apunte a una ruta inexistente no renderiza.{% endcomment %}
    </div>

    <div class="w-full rounded-full h-3 mb-2" style="background: var(--bg-secondary)">
      <div class="h-3 rounded-full" style="width: {{ en_curso.progreso }}%; background: var(--color-brand-500)"></div>
    </div>
    <p class="text-sm text-body mb-4">{{ en_curso.elegidos }} de {{ en_curso.total_pedido }}</p>

    <dl class="grid grid-cols-2 sm:grid-cols-3 gap-3 text-sm">
      <div><dt class="text-body-subtle">Altas en SIIS</dt><dd class="text-heading font-bold">{{ en_curso.altas }}</dd></div>
      <div><dt class="text-body-subtle">Aprobados</dt><dd class="text-heading font-bold">{{ en_curso.aprobados }}</dd></div>
      <div><dt class="text-body-subtle">Sin cupo → espera</dt><dd class="text-heading font-bold">{{ en_curso.lista_espera }}</dd></div>
      <div><dt class="text-body-subtle">Rechazados por SIIS</dt><dd class="text-heading font-bold">{{ en_curso.rechazados }}</dd></div>
      <div><dt class="text-body-subtle">Errores técnicos</dt><dd class="text-heading font-bold">{{ en_curso.errores }}</dd></div>
      <div><dt class="text-body-subtle">Salteados sin datos</dt><dd class="text-heading font-bold">{{ en_curso.salteados }}</dd></div>
    </dl>
  </div>

  {% elif corrida and corrida.interrumpida %}
  <div class="rounded-lg bg-warning-soft border border-warning-subtle p-4 text-sm mb-6" role="alert">
    <strong class="text-heading">Interrumpida</strong>
    <p class="text-body mt-1">
      Sin señal desde hace {{ corrida.latido|timesince }}. Llegó a {{ corrida.elegidos }} de {{ corrida.total_pedido }}.
      Continuar lanza una corrida nueva por lo que falta; los ya informados se saltean solos.
    </p>
  </div>
  {% endif %}

  {% if not en_curso %}
  <div class="bg-white rounded-xl border border-base shadow-sm p-5 mt-6">
    <dl class="grid grid-cols-2 gap-3 text-sm mb-5">
      <div><dt class="text-body-subtle">Pendientes de informar</dt><dd class="text-heading font-bold text-2xl">{{ pendientes }}</dd></div>
    </dl>
    <form method="post" action="{% url 'becas:proceso_masivo_lanzar' programa.pk %}" class="flex items-end gap-3 flex-wrap">
      {% csrf_token %}
      <div>
        <label for="total_pedido" class="block text-[13px] font-semibold text-heading mb-1.5">Cantidad a procesar</label>
        <input type="number" name="total_pedido" id="total_pedido" value="1000"
               min="1" max="{{ total_maximo }}" required class="nodo-field" style="max-width:160px">
      </div>
      <button type="submit" class="btn-nodo btn-brand btn-base">
        {% if corrida and corrida.interrumpida %}Continuar{% else %}Procesar{% endif %}
      </button>
    </form>
    <p class="text-xs text-body-subtle mt-3">
      El total cuenta casos que se mandan. Los que tienen datos faltantes se saltean sin tocarlos,
      así que puede mirar más de los que pedís.
    </p>
  </div>
  {% endif %}

  {% if corrida and not en_curso %}
  <div class="bg-white rounded-xl border border-base shadow-sm p-5 mt-6">
    <p class="text-[13px] font-semibold text-heading mb-2">Última corrida</p>
    <p class="text-sm text-body-subtle">
      {{ corrida.creado|date:"d/m/Y H:i" }} ·
      {{ corrida.solicitada_por.get_full_name|default:corrida.solicitada_por.username }} ·
      {{ corrida.get_estado_display }}
    </p>
    <p class="text-sm text-body mt-1">
      {{ corrida.total_pedido }} pedidos → {{ corrida.altas }} altas ·
      {{ corrida.rechazados }} rechazados por SIIS · {{ corrida.salteados }} salteados
    </p>
    {% if corrida.mensaje %}<p class="text-sm text-fg-danger mt-1">{{ corrida.mensaje }}</p>{% endif %}
  </div>
  {% endif %}

</div>
{% endblock %}

{% block customJS %}
{% if en_curso %}
<script>
  // La corrida avanza en un hilo del pod: la pantalla la relee cada 5 s.
  setTimeout(function () { window.location.reload(); }, 5000);
</script>
{% endif %}
{% endblock %}
```

- [ ] **Step 7: Correr los tests**

```powershell
& $env:PY_VENV manage.py test programas.tests.test_proceso_masivo
```

Esperado: todos los de `PantallaProcesoMasivoTests` OK.

- [ ] **Step 8: Auditorías de UI**

```powershell
& $env:PY_VENV scripts\compile_templates.py
& $env:PY_VENV scripts\design_audit.py --changed
```

Esperado: `ERRORES: 0` y `design_audit` sin errores nuevos. El único preexistente admitido es `focus:ring-brand` en `segmento_list.html`.

- [ ] **Step 9: Commit**

```bash
git add core/rbac.py programas/views/proceso_masivo.py programas/urls.py programas/templates/programas/becas/config/proceso_masivo.html programas/models/__init__.py programas/tests/test_proceso_masivo.py
git commit -m "feat(becas): pantalla no listada para lanzar el proceso masivo a SIIS

No figura en ningun menu, pero lo que la protege es la capacidad
becas.programa.proceso_masivo: esconder un boton que aprueba mil casos es
prolijidad, no seguridad. No se asigna a ningun rol en el seed."
```

---

### Task 5: Frenar

**Files:**
- Modify: `programas/views/proceso_masivo.py`
- Modify: `programas/urls.py`
- Test: `programas/tests/test_proceso_masivo.py`

**Interfaces:**
- Consumes: `CorridaSiis.en_curso()` (Task 1), la vista de la Task 4
- Produces: URL `becas:proceso_masivo_frenar` → `.../proceso-masivo/frenar/`

- [ ] **Step 1: Escribir los tests que fallan**

Agregar a `PantallaProcesoMasivoTests`:

```python
    def test_frenar_marca_la_corrida(self):
        corrida = CorridaSiis.objects.create(
            programa=self.programa, total_pedido=10, latido=timezone.now()
        )
        resp = self.client.post(self._url("proceso_masivo_frenar"))
        self.assertEqual(resp.status_code, 302)
        corrida.refresh_from_db()
        self.assertTrue(corrida.cancelacion_pedida)
        # El estado lo cambia el proceso al cerrar el lote, no este request.
        self.assertEqual(corrida.estado, CorridaSiis.Estado.EN_CURSO)

    def test_frenar_sin_corrida_no_rompe(self):
        resp = self.client.post(self._url("proceso_masivo_frenar"))
        self.assertEqual(resp.status_code, 302)
```

- [ ] **Step 2: Correr y verificar que fallan**

```powershell
& $env:PY_VENV manage.py test programas.tests.test_proceso_masivo.PantallaProcesoMasivoTests
```

Esperado: `NoReverseMatch: Reverse for 'proceso_masivo_frenar' not found`

- [ ] **Step 3: Agregar la vista**

Al final de `programas/views/proceso_masivo.py`:

```python
@login_required
@requiere(CAP_PROCESO_MASIVO)
@require_POST
def proceso_masivo_frenar(request, pk):
    """Pide el freno. **No** cambia el estado: eso lo hace el proceso.

    El estado final lo escribe quien está corriendo, al cerrar el lote en curso.
    Si lo marcara este request, la pantalla diría «cancelada» mientras el hilo
    sigue procesando los casos que le quedan del lote.
    """
    programa = get_object_or_404(ProgramaSiis, pk=pk)
    corrida = CorridaSiis.en_curso()
    if corrida is None:
        messages.info(request, "No hay ninguna corrida en curso.")
    else:
        CorridaSiis.objects.filter(pk=corrida.pk).update(cancelacion_pedida=True)
        messages.success(
            request,
            "Se pidió frenar. El proceso corta al terminar el lote en curso: puede tardar hasta 40 casos.",
        )
    return redirect("becas:proceso_masivo", pk=programa.pk)
```

- [ ] **Step 4: Agregar la URL**

En `programas/urls.py`, después de `proceso_masivo_lanzar`:

```python
    path(
        "config/programas/<int:pk>/proceso-masivo/frenar/",
        masivo.proceso_masivo_frenar,
        name="proceso_masivo_frenar",
    ),
```

- [ ] **Step 5: Poner el botón Frenar en la plantilla**

En `proceso_masivo.html`, reemplazar el bloque `{% comment %}…{% endcomment %}` que dejó la Task 4 por:

```html
      <form method="post" action="{% url 'becas:proceso_masivo_frenar' programa.pk %}">
        {% csrf_token %}
        <button type="submit" class="btn-nodo btn-danger btn-sm">Frenar</button>
      </form>
```

- [ ] **Step 6: Correr toda la suite**

```powershell
& $env:PY_VENV manage.py test programas
```

Esperado: todos OK.

- [ ] **Step 7: Auditorías, lint y gates**

```powershell
& $env:PY_VENV scripts\compile_templates.py
& $env:PY_VENV scripts\design_audit.py --changed
& $env:PY_VENV -m ruff check .
& $env:PY_VENV -m ruff format .
& $env:PY_VENV manage.py check
& $env:PY_VENV manage.py makemigrations --check --dry-run
```

- [ ] **Step 8: Registrar el requerimiento**

Agregar la entrada al final de `docs/internal/requerimientos.md` y su fila en el índice, con el número que siga al último usado —verificarlo primero, porque hay otra sesión trabajando sobre el mismo checkout—. La entrada tiene que dejar escrito:

- que «secreta» es *no listada*, y que lo que protege es la capacidad;
- que el total cuenta casos enviados y no mirados;
- por qué la interrupción se deduce del latido en vez de guardarse;
- por qué se eligió el hilo sobre el CronJob, y que pasar al esquema mixto después no requiere tocar nada;
- que el correo al ciudadano no se ofrece;
- el riesgo abierto del `loc_actual` por provincia contra global, y que la primera corrida tiene que ser de 1 caso.

```powershell
& $env:PY_VENV scripts\requerimientos.py --check
```

Esperado: `OK`.

- [ ] **Step 9: Commit**

```bash
git add programas/views/proceso_masivo.py programas/urls.py programas/tests/test_proceso_masivo.py programas/templates/ docs/internal/requerimientos.md
git commit -m "feat(becas): frenar la corrida masiva desde la pantalla

El request solo marca el pedido; el estado final lo escribe el proceso al cerrar
el lote. Marcarlo aca diria «cancelada» mientras el hilo sigue procesando."
```

---

## Verificación final

Antes de dar por terminado:

1. `manage.py test programas` en verde contra el venv de Python 3.12 (el venv 3.14 tiene el baseline conocido de `'super' object has no attribute 'dicts'`).
2. `design_audit.py --changed` sin errores nuevos.
3. `compile_templates.py` en 0.
4. `requerimientos.py --check` en OK.
5. La pantalla abre en `/becas/config/programas/<id>/proceso-masivo/` y **no** aparece ningún link hacia ella: `grep -rn "proceso_masivo" programas/templates/` solo puede devolver la propia plantilla.

## Riesgo que hay que respetar al usar esto

Sigue sin confirmarse si SIIS interpreta `loc_actual` como el id numerado por provincia —lo que implementó el Cambio 86— o como un id global. Si fuera global, las altas entran con el domicilio equivocado **sin dar error**.

La primera corrida real tiene que ser de **1 caso**, verificando en SIIS con qué domicilio quedó registrado.
