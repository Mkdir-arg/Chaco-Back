# Diseño técnico — Dashboard del Programa Becas

**Fecha:** 2026-09-05 · **Cadena:** Épica #69 · Análisis #366 (Definido) · Tasks #367–#375 · **Rama:** `feature/dashboard-becas`
**Estimación:** 70 h técnicas (86 h propuestas al Ministerio) · **Mock up:** https://claude.ai/code/artifact/672365a4-39ae-4ef9-895d-3664a99e77fb
**Registro:** Cambio 64 de `docs/internal/requerimientos.md` · frente 7 de la Versión 002

## Qué se construye

Una tercera solapa **«Dashboard»** en `/becas/config/programas/<pk>/`, a la derecha de «Requisitos del
programa». Una fila de filtros gobierna seis indicadores y ocho bloques (serie semanal, estados,
avance por convocatoria, relevamientos por estado, embudo, territoriales, respuestas de los
formularios, localidades). Todo se puede ver como tabla y bajar en CSV; hay planilla XLSX de una
hoja por bloque e impresión a PDF desde el navegador. Permisos `becas.reportes.ver` /
`becas.reportes.exportar`, alcance por rol igual que el resto de Becas.

**Principio rector:** el dashboard **no calcula nada nuevo sobre el dominio**. Lee lo que el módulo
de reportes ya calcula (`programas/services/reportes_becas.py`) y agrega tres cosas: la serie
temporal, la distribución de respuestas y el corte por localidad. Sin dependencias nuevas.

## Cómo debe quedar

### Capa de datos — `programas/services/dashboard_becas.py` (nuevo)

Un módulo puro, sin request ni template, que responde a una sola pregunta: «para este programa,
este usuario y estos filtros, ¿cuáles son los números?». Es la **única** fuente de la pantalla, del
endpoint JSON y de las exportaciones, así que los tres siempre coinciden.

```python
@dataclass(frozen=True)
class Filtros:
    desde: date | None; hasta: date | None          # ventana por Formulario.creado (RN-7)
    segmento_id: int | None; convocatoria_id: int | None
    relevamiento_id: int | None; canal: str | None  # Relevamiento.Tipo o None = ambos

datos = metricas(user, programa, filtros)          # -> Datos (dataclass), sin caché
datos = metricas_cacheadas(user, programa, filtros, recalcular=False)  # 5 min, RN-17/18
preguntas_graficables(user, programa)              # catálogo de opciones cerradas (RN-13)
distribucion_respuestas(user, programa, filtros, clave)  # -> Distribucion (RN-14/15)
hojas_exportacion(datos, distribuciones)           # -> [(nombre_hoja, Reporte), ...]
```

`Datos` lleva: `indicadores`, `serie_semanal`, `estados`, `canales`, `convocatorias`,
`relevamientos_por_estado`, `embudo`, `territoriales`, `localidades`, `alcance` (texto legible que
encabeza las exportaciones, RN-16) y `calculado_en`. Todo son tipos simples (int, str, date) para
que `dataclasses.asdict` alcance para el JSON y para la caché.

**Alcance.** Todo queryset nace de `convocatorias_visibles(user, programa)` filtrado por
`segmento__programa=programa`. Nunca `Formulario.objects.all()`. El recorte por rol se hereda de
`programas/services/autorizacion.py` sin redefinir nada (RN-3).

**Encadenado de filtros.** Convocatorias en alcance → (segmento, convocatoria) → relevamientos de
esas convocatorias → (relevamiento, canal) → formularios de esos relevamientos → (desde/hasta sobre
`creado`). Los relevamientos y convocatorias cuentan por estructura (no se recortan por fecha); los
formularios sí.

**Cálculos con una regla cada uno.**

| Bloque | Cómo | Regla |
|---|---|---|
| Formularios recibidos y variación | `count()` en la ventana; período anterior = misma longitud inmediatamente antes; `None` si no hay ventana | RN-8 |
| Serie semanal | `annotate(semana=TruncWeek("creado"))` + relleno de semanas vacías en Python | RN-7 |
| Estados | `values("estado").annotate(Count)`; cuatro estados que suman el total | RN-10 |
| Canales | igual, por `relevamiento__tipo` | RN-12 |
| Cupo ocupado | aprobados **históricos** (sin ventana) de los segmentos en alcance / `cupo_maximo`; regional → cupo distribuido en sus subsegmentos, como `reporte_cupos` | RN-9 |
| Lista de espera | `ListaEspera.filter(promovido=False)` sobre los formularios del alcance | RN-11 |
| Avance por convocatoria | una consulta con `annotate` por convocatoria (misma técnica que `reporte_avance`) + ocupación del segmento | RN-9 |
| Relevamientos por estado | `values("estado").annotate(Count)`; los seis estados siempre presentes, con 0 | — |
| Embudo | recibidos · identidad validada (`validado_renaper` o `identidad_forzada`) · aprobados · SIIS OK (última `ValidacionSIS`, subquery como en `reporte_embudo`) · lista de espera · rechazados | RN-10/11 |
| Territoriales | formularios por `relevamiento__territorial`, solo `tipo=TERRITORIAL`, top 8 | RN-12 |
| Localidades | `ciudadano__localidad__nombre`; sin ciudadano o sin localidad → «Sin localidad»; top 7 + «Otras», detalle completo aparte | — |

**Respuestas (RN-13 a RN-15).** El catálogo une `PreguntaGlobal` activas y `RequisitoNativo` del
programa, de sus segmentos y subsegmentos en alcance, solo tipos `SELECTOR` y `SELECTOR_MULTIPLE`
(el sistema no tiene tipo sí/no propio: un sí/no es un selector de dos opciones). Clave estable
`global:<pk>` / `requisito:<pk>`. **Una sola función lee la respuesta**:

```python
def respuesta_de(formulario, clave) -> list[str]:
    """Hoy: Formulario.data[{"globales"|"requisitos"}][str(pk)]. Con el Cambio 58: respuestas."""
```

Se cuenta en Python sobre `values_list("data")` del recorte —el JSON no tiene esquema y MySQL y
SQLite deberían coincidir— y es el único punto que toca `data`. La base son los formularios que
**tienen** la pregunta respondida; en múltiple cada opción marcada suma una vez y `multiple=True`
avisa a la pantalla.

**Caché (RN-17/18).** Clave `becas:dashboard:<programa>:<sha1(filtros + huella_alcance)>` donde la
huella es la lista ordenada de ids de segmentos visibles (y de subsegmentos a cargo para el
regional). Dos usuarios con distinto alcance nunca comparten entrada. `recalcular=True` borra y
recomputa. `calculado_en` viaja dentro del valor cacheado y la pantalla lo muestra.

### Filtros — `DashboardBecasFiltroForm` en `programas/forms_reportes.py`

Mismo patrón que `ReporteBecasFiltroForm`: recibe `user` y `programa`, recorta los querysets de
segmento / convocatoria / relevamiento por alcance y programa, valida `desde <= hasta` y traduce
`periodo` (`30` · `90` · `anio` · `todo` · `custom`) a fechas. Método `filtros()` → `Filtros`.
Campo `pregunta` con las claves del catálogo. Campo `canal` con `Relevamiento.Tipo`.

### Vistas y rutas — `programas/views/dashboard_becas.py` (nuevo)

| Ruta (`becas:`) | Vista | Permiso | Devuelve |
|---|---|---|---|
| `config/programas/<pk>/dashboard/datos/` | `programa_dashboard_datos` | `becas.reportes.ver` + programa visible | JSON: `datos`, `respuestas` (de la pregunta elegida), `opciones.relevamientos` (de la convocatoria elegida), `errores` del form |
| `config/programas/<pk>/dashboard/export/<formato>/` | `programa_dashboard_exportar` | `becas.reportes.exportar` + programa visible | `xlsx` → libro de varias hojas · `csv?bloque=<nombre>` → un bloque |

Ambas reusan `_programas_qs` para el «programa visible» y responden **403** sin capacidad (CA-1,
CA-6). `ProgramaSiisDetailView` solo agrega al contexto `puede_dashboard`, `puede_exportar_dashboard`
y el form de filtros con sus opciones; **los números no se calculan al cargar la página**: los pide
el JS al abrir la solapa (RNF-1).

### Exportación — `programas/services/exportacion_reportes.py`

Se agrega `respuesta_libro(hojas, nombre, alcance)` junto a `respuesta_reporte`, con el mismo
`celda_segura` y `Workbook(write_only=True)`. Primera fila de cada hoja: el alcance aplicado
(RN-16). `respuesta_reporte` no cambia: sigue sirviendo a los cinco reportes.

### Interfaz — `_dashboard_panel.html` + `static/custom/js/becas-dashboard.js`

Piezas canónicas del inventario (`.claude/agents/chaco-design-system.md`), sin CSS nuevo:

- **Tabs backoffice:** tercera pestaña en `programa_detail.html`, `x-show="tab==='dash'"`, con
  `?tab=dash` para deep link (patrón de `convocatoria_detail.html`). El botón dispara
  `$dispatch('becas-dashboard-abrir')`; el JS carga recién ahí.
- **Stat cards / métricas:** el patrón Tailwind de `convocatoria_detail.html` (`bg-white rounded-xl
  p-4 border border-base shadow-sm`, label `text-xs text-body-subtle font-medium`, valor `text-2xl
  font-bold text-heading`, icono en caja `w-8 h-8 rounded-lg`). **No** se mueve el CSS `.stat-card`
  de `inicio.html`: ese es local de esa plantilla y el inventario ya tiene la pieza canónica.
- **Filtros:** `nodo-field`, labels `text-sm font-medium text-heading`; una fila, arriba de todo.
- **Tabla densa** para «Avance por convocatoria» y para toda vista de tabla; **badges** para
  estados; **estado vacío** canónico por bloque; **botones** `btn-nodo` (exportar = `btn-brand`,
  auxiliares = `btn-tertiary`).
- **Gráficos:** Chart.js 4.4.6 vendorizado, carga diferida como `inicio.html`. Un color por serie
  de magnitud (barras horizontales, `barThickness` 18, `borderRadius` 4 solo en el extremo); estados
  con colores semánticos; sin doble eje; leyenda y etiqueta siempre. **Los colores se leen de los
  tokens en runtime** (`getComputedStyle(...).getPropertyValue('--color-brand-500')`): el JS no
  tiene hex.
- **Vista de tabla por bloque:** el JS arma la tabla desde los mismos datos (`textContent`, nunca
  `innerHTML` con datos).
- **Impresión:** `@media print` oculta filtros, botones y solapas.

### Tests — `programas/tests/test_dashboard_becas.py`

Fixtures en el estilo de `test_reportes_becas.py` (`seed_becas` + roles reales). Cubren conteos a
mano, coherencia entre bloques (CA-3), alcance por rol con el caso de fuga (CA-4), permisos 403
(CA-1, CA-6), RN-9 (cupo insensible al período), RN-8 (variación `None`), respuestas simple/múltiple,
casos límite, exportaciones y presupuesto de consultas con `CaptureQueriesContext`.

## Fases de desarrollo

Cada fase cierra con `manage.py check`, sus tests en verde y un commit propio en la rama. Las de
UI agregan `design_audit.py --changed`, `compile_templates.py` y `check_design_agent.py --changed`
en 0.

| Fase | Task | Entregable demostrable | Horas |
|---|---|---|---|
| **1. Servicio de métricas** | #367 | `metricas()` devuelve todos los bloques coherentes; tests de conteo y alcance | 10 |
| **2. Respuestas** | #368 | `preguntas_graficables()` y `distribucion_respuestas()` con lectura única; tests simple/múltiple | 10 |
| **3. Solapa, filtros y permisos** | #369 | La pestaña aparece solo con capacidad; el endpoint JSON responde con filtros y 403 | 5 |
| **4. Interfaz** | #370 | La solapa muestra indicadores y gráficos reales, vista de tabla, estados vacíos; auditoría en 0 | 14 |
| **5. Exportación** | #371 | XLSX de varias hojas, CSV por bloque, impresión | 6 |
| **6. Caché y presupuesto** | #372 | Caché 5 min con huella de alcance; `assertNumQueries` fijado | 4 |
| **7. Pruebas automatizadas** | #373 | Suite completa en verde (se escribe junto a cada fase; acá se cierra la cobertura) | 8 |
| **8. QA funcional** | #374 | Casos por criterio, ejecución por rol, contraste con el hub de reportes | 10 |
| **9. Release** | #375 | PR a `development`, CI verde, espejo a ECOM, Cambio 64 en «Hecho» | 3 |

Orden real de trabajo: 1 → 2 → 3 → 4 → 5, con la caché (6) dentro del servicio desde la Fase 1 y
los tests (7) escritos fase a fase. QA (8) y release (9) las gobierna el PM.

## Decisiones cerradas en el diseño

- **Sí/no = selector de dos opciones.** El sistema no tiene `TipoCampo` booleano; el análisis lo
  nombra «sí/no» porque así lo ve el usuario. El catálogo filtra por `TipoCampo.selectores()`.
- **Los relevamientos no se recortan por fecha.** Un relevamiento asignado sin formularios cuenta
  en «Relevamientos por estado» aunque el período sea de 30 días; lo que la ventana recorta son
  los formularios. Es lo que hace que «15 en total» no baile al mover el período.
- **Cupo del segmento, no de la convocatoria.** `Convocatoria` no tiene cupo; la tabla de avance
  muestra la ocupación del segmento al que pertenece, con el mismo criterio de `reporte_cupos`.
- **Serie con `TruncWeek`.** Portable entre MySQL y SQLite (tests). Las semanas sin formularios se
  rellenan en Python para que el gráfico no salte fechas.
- **Conteo de respuestas en Python.** `data` es JSON sin esquema; una `JSON_TABLE` de MySQL no
  corre en los tests y ataría el bloque al motor. El recorte ya viene acotado por filtros, y la
  caché de 5 minutos absorbe el costo.
- **Sin CSS nuevo.** Todo sale de tokens y utilidades ya compiladas; si una clase Tailwind falta en
  el build, se corre `npm run build:tailwind` (regla TWBUILD).

## Gates de cierre (por fase y al final)

```powershell
$env:PY_VENV = "$PWD\.venv\Scripts\python.exe"; $env:DJANGO_SECRET_KEY = "test-key"
& $env:PY_VENV manage.py check
$env:PYTEST_RUNNING = "1"; & $env:PY_VENV manage.py test programas.tests.test_dashboard_becas -v 2
& $env:PY_VENV scripts\design_audit.py --changed      # 0 errores
& $env:PY_VENV scripts\compile_templates.py            # 0
& $env:PY_VENV scripts\check_design_agent.py --changed
& $env:PY_VENV scripts\requerimientos.py --check       # al cerrar: Cambio 64 -> Hecho
```
