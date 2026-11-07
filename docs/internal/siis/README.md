# Propuesta de equivalencias de localidades de Chaco (core → SIIS)

**Interno, no se publica** (`docs/internal`, no `docs/client`): es material de trabajo para que el organismo decida.

El selector de Localidad guarda nombres del catálogo core (778 en Chaco). El padrón de SIIS tiene 165. Las que no
cruzan por `clave_nombre` terminan en «La localidad no coincide con el catálogo de SIIS». El archivo
`propuesta-alias-localidades-chaco.csv` propone, para cada una, a qué localidad de SIIS equivale. **Es una propuesta:
el código no decide equivalencias** (ver `AliasLocalidadSiis`).

## Qué trae el CSV

Una fila por localidad core de Chaco: `localidad_core, municipio_core, estado, localidad_siis_propuesta, siis_id, motivo`.

| estado | significa | qué hace el organismo |
|---|---|---|
| `CRUZA` | ya cruza con SIIS (por nombre o por una equivalencia cargada) | nada |
| `PROPUESTA` | no cruza, hay un único candidato en SIIS; el `motivo` dice por qué | aprobar, corregir el `siis_id` o rechazar |
| `SIN_CANDIDATO` | no hay candidato, hay varios, ya se revisó sin destino, o el mismo nombre daría propuestas distintas según el municipio | decidir a mano |

Conteo de esta corrida (06/11/2026, fixture `core/fixtures/localidad_municipio_provincia.json` + padrón de
`programas/data/`): **131 CRUZA, 522 PROPUESTA, 125 SIN_CANDIDATO** (778 en total).

**Ojo con las `PROPUESTA` por municipio** (las 522 salieron por esa vía). Dice «el municipio de esta localidad es la
localidad X de SIIS»: un paraje o un lote de ese municipio no es necesariamente la localidad X. Es la vía más débil
y hay que mirarla fila por fila. Las que dicen «lote», «colonia» o «paraje» son las más dudosas.

## Cómo se genera de nuevo

```powershell
$env:PY_VENV = "$PWD\.venv\Scripts\python.exe"
& $env:PY_VENV manage.py proponer_alias_siis --salida docs/internal/siis/propuesta-alias-localidades-chaco.csv
```

Solo lee: no escribe en la base. Sin `--salida` el CSV va a stdout y el resumen a stderr. Necesita la base con el
catálogo core (fixture) y el catálogo de SIIS (`seed_catalogo_siis`) cargados.

## Cómo se revisa

1. Abrir el CSV (UTF-8; en Excel, «Datos → Desde texto» eligiendo UTF-8).
2. Filtrar `estado = PROPUESTA`. En cada fila: **aprobar** (dejarla), **corregir** (cambiar `siis_id` por el correcto) o
   **rechazar** (vaciar `siis_id`).
3. Filtrar `estado = SIN_CANDIDATO` y decidir las que el organismo quiera resolver (por ejemplo, una cabecera para un
   paraje). Las que quedan sin decisión siguen sin cruzar y se corrigen caso por caso.

## Cómo se pasan las filas aprobadas (después de la aprobación, en otro PR)

Se agregan a `programas/data/siis_alias_localidades.csv`, que tiene las columnas
`provincia_siis_id,texto,localidad_siis_id,nota`:

- `provincia_siis_id`: `1` (Chaco).
- `texto`: `localidad_core`.
- `localidad_siis_id`: el `siis_id` aprobado (vacío = «se revisó y no hay equivalencia»).
- `nota`: algo corto, p. ej. «aprobada por el organismo el dd/mm/aaaa».

Después correr `python manage.py seed_catalogo_siis` (idempotente).

**Límite del mecanismo:** el alias se busca por **nombre**, no por municipio. Si dos localidades core se llaman igual
en municipios distintos (hay muchos «Lote 1»), una sola fila las traduce a las dos al mismo destino. Por eso esas
quedan como `SIN_CANDIDATO`: una fila por nombre no puede decir dos cosas.

## Provincia: «Tierra del Fuego, Antártida e Islas del Atlántico Sur»

Core la llama así y SIIS «TIERRA DEL FUEGO», así que `ProvinciaSiis.clave` no coincide y esa provincia no cruza.
No hay hoy un mecanismo de alias de provincia (`AliasLocalidadSiis` es solo de localidades; `Catalogos.provincia_id`
compara `clave_nombre` contra `ProvinciaSiis.clave`). Está fuera del alcance de este PR (solo Chaco). Opciones:
**DECISIÓN CLIENTE / del juez:** (a) una tabla/CSV de alias de provincias, simétrico al de localidades; (b) guardar en
`ProvinciaSiis` una clave alternativa; (c) tratarlo como caso único en `provincia_id`. Recomendación: (a), porque
sigue el patrón ya conocido por el organismo.
