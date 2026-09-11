---
description: "Reconstruir el consumo de horas de un período desde la evidencia y cargarlo en el financiero"
argument-hint: "[período: «esta semana», «del 31/08 al 05/09», «ayer»…]"
---

# Carga de horas por reconstrucción

Actuá como el **PM Assistant de Chaco**. El método de cuantificación —unidad de
registro, techo por día, equivalente convencional, reunión diaria, reparto por
rol, frontera de mes— está en `PM.md` (raíz, fuente de verdad): **leé la sección
"5.b Carga de horas por reconstrucción" completa y seguila al pie de la letra**.
Este comando agrega la receta operativa: cómo levantar la evidencia, dónde
escribir, cómo verificar y cómo publicar.

Período pedido: `$ARGUMENTS`

## 0. Antes de empezar

- **No asumas la fecha.** Corré `date "+%A %d/%m/%Y %H:%M"`: la sesión puede
  venir de días anteriores y el checkout es compartido con otras sesiones.
- Si el período viene vacío, asumí **la semana en curso (lunes a hoy)** y decilo
  en la primera línea de la respuesta.
- **Distinguí el pedido:** «mostrame / analizá / cuántas horas» ⇒ solo mostrás y
  esperás confirmación. «cargá / actualizá / registrá» ⇒ escribís y publicás.
  Ante la duda, mostrá primero: el PM revisa y ajusta los renglones casi siempre.

## 1. Qué hay cargado ya

```bash
# Últimos días registrados y formato de las secciones
grep -n "^### .*Consumo del\|^### .*Consumo de .* por programa" docs/client/financiero/detalle-tareas.md | tail -8
# Filas ya cargadas de un día (para no duplicar)
grep -c "^| 31/08" docs/client/financiero/detalle-tareas.md
```

Anotá qué días del período ya tienen filas y con cuántas horas: esas se
**completan**, no se reemplazan.

## 2. Levantá la evidencia

```bash
# Commits del período, TODAS las ramas, sin bots, ordenados por fecha
git log --all --since="AAAA-MM-DD 00:00" --no-merges --perl-regexp \
  --author='^(?!github-actions)' --format='%h|%ad|%s' \
  --date=format:'%d/%m %H:%M' | sort -t'|' -k2 | uniq -f1

# Volumen de cada commit (archivos y líneas): tamaño real del entregable
git show --stat --format='' <hash> | tail -1

# Historia efectiva de la rama, con fecha de autor y de commit
git log HEAD -20 --format='%h|%ad|%cd|%s' --date=format:'%d/%m %H:%M'

# Releases automáticos y qué release tiene producción del organismo
git log origin/main --since="AAAA-MM-DD" --format='%ad %s' --date=format:'%d/%m %H:%M'
git ls-remote ecom main test

# Cambios definidos e implementados en el período (lo que no deja rastro en el diff)
grep -n "^# Cambio \|^🟢 \*\*HECHO\|^🟡" docs/internal/requerimientos.md | tail -30

# Análisis y QA no dejan commits: los issues sí
gh issue list --repo Mkdir-arg/Chaco-Back --search "created:>=AAAA-MM-DD" --limit 50
```

Fuentes que **no** están en el repo y hay que preguntar: apertura y soporte de
convocatorias, reuniones con el organismo, pruebas manuales, trabajo del equipo
móvil y cualquier día sin commits.

## 3. Cuantificá

Aplicá las reglas de `PM.md` §5.b. Orden de trabajo que funciona:

1. Agrupá la evidencia **por día** y por **frente** (portal público, constructor,
   Dispositivos, rendimiento, gestión…).
2. Asigná cada frente a la persona por rol (tabla de §5.b) y poné las horas del
   entregable, no del commit.
3. Sumá la **reunión diaria** (1 h por integrante) y el **informe** del PM (0,5 h)
   en cada día hábil.
4. Completá la jornada del PM hasta 9 h con coordinación, tablero y revisión.
5. Chequeá el techo de cada persona en cada día y rebalanceá si se pasa.
6. Calculá el `Equiv.` solo en las filas con código (≈ 2 × horas); el resto, `—`.

## 4. Mostrá los renglones antes de escribir

Una tabla por día con `Persona | Tarea | Horas`, y al pie de cada día el cierre:

| | Fariña | Pablo | Juani | Abate | Día |
|---|---:|---:|---:|---:|---:|
| Día | … | … | … | … | … |
| **Acumulado** | … | … | … | … | … |

El PM pide habitualmente el **acumulado por persona por día**: incluilo siempre.
Cerrá con el total por persona, el total del período, el reparto por programa y
el impacto en el presupuesto del mes. Marcá explícitamente los supuestos que
necesitan confirmación (días sin evidencia, fines de semana, reparto por persona).

## 5. Escribí el registro

En `docs/client/financiero/`, todo en **lenguaje cliente** (nada de rutas,
ramas, PRs ni jerga: «el link público», «el constructor de formularios»):

1. **`detalle-tareas.md`** — sección del período:
   `### :material-package-variant-closed: Consumo del X al Y de <mes> — por entregable`
   con una nota `!!! note` que explique el período, la tabla
   `Período | Persona | Programa | Entregable | Qué incluye | Horas | Equiv.` y su
   fila `**Total X al Y/MM**`. Si el día ya tenía filas, agregalas al bloque que
   corresponde y **recalculá el total de ese bloque**.
2. **`### Consumo de <mes> por programa`** del mes tocado (Becas / Dispositivos /
   Transversal + total). Si el mes está cerrado con traslado, actualizá el
   esfuerzo real y el excedente trasladado, **sin tocar la imputación**.
3. **`mes-AAAA-MM.md`** — tarjetas (presupuesto, consumido, saldo), consumo por
   programa, consumo por persona y la lista «Qué se está trabajando en el mes».
4. **`financiero/index.md`** — tarjeta del mes en curso y, si aplica, la del mes
   cerrado.
5. **`docs/client/index.md`** — bloque «Estado financiero» y «Última
   actualización».
6. **Contador total** al pie de `detalle-tareas.md`: minutos, equivalente en
   horas y desglose por mes.
7. Si el período movió el avance de una funcionalidad, actualizá también la
   página de la versión activa (`docs/client/versiones/version-00N.md`):
   ejecutado, restante y sección de avance.

## 6. Verificá (obligatorio, antes del commit)

```bash
# Las filas de cada día tienen que dar el total declarado
.venv/Scripts/python.exe -c "
import io,re
d=io.open(r'docs/client/financiero/detalle-tareas.md',encoding='utf-8').read().split(chr(10))
def suma(pref):
    t=0.0
    for l in d:
        if l.startswith('| '+pref):
            c=[x.strip() for x in l.split('|')]
            m=re.match(r'^([0-9]+(?:[.,][0-9]+)?) h\$', c[-3]) if len(c)>4 else None
            if m: t+=float(m.group(1).replace(',','.'))
    return t
for p in ['01/09','02/09','03/09','04/09','05/09']: print(p, suma(p))
"
```

La columna de horas es la **antepenúltima** celda de la tabla por entregable
(`c[-3]`). Además: los totales por programa y por persona tienen que cerrar
contra las filas, el contador acumulado contra la suma de los meses, y

```powershell
& .venv\Scripts\mkdocs.exe build --strict     # el sitio tiene que compilar
```

## 7. Publicá

Commit a `development` (el sitio se publica solo con **Docs Auto Deploy**). El
checkout es compartido con otras sesiones: **verificá la rama en el mismo comando
que el commit** y, si estás en otra, usá un worktree desde `origin/development`.

```bash
git add docs/client && [ "$(git branch --show-current)" = "development" ] \
  && git commit -q -F <mensaje> && git push -q origin development
gh run list --branch development --limit 2      # Docs Auto Deploy en verde
```

Cerrá la respuesta con lo cargado, los totales nuevos, el impacto en el
presupuesto del mes y **qué quedó pendiente de confirmación**.
