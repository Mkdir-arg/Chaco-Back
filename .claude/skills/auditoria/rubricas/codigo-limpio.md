# Rúbrica: código limpio y estructura

Adaptada de la skill `thermo-nuclear-code-quality-review` del plugin Thermos
([cursor/plugins](https://github.com/cursor/plugins), commit `8b3326d`, MIT, © Cursor). Se conservó
el núcleo —ambición por simplificar sin cambiar comportamiento, la regla de las 1000 líneas, cero
condiciones especiales sueltas— y se calibró para Chaco: qué bloquea en un PR, las capas del repo
y sus helpers canónicos.

## Calibración para Chaco (leer primero)

**Modo `pr` — bloquea solo lo que el PR empeora.** En modo `completa`, la misma situación sobre
el código existente:

| Situación | Modo `pr` | Modo `completa` |
|---|---|---|
| Un archivo pasa de menos de 1000 líneas a más de 1000 sin una razón estructural fuerte | `[MAJOR]` | MEDIA |
| Un archivo que ya pasaba las 1000 líneas crece de forma notable | `[MINOR]`; `[MAJOR]` si lo que suma es lógica que debería vivir en otro módulo | MEDIA |
| Condiciones especiales (`if` de un caso puntual) en un flujo ajeno o compartido | `[MAJOR]` | MEDIA |
| Un helper que ya existe en su forma canónica (tabla de abajo), escrito de nuevo | `[MAJOR]` | MEDIA |
| Lógica de negocio en la capa equivocada (en una vista, un template o un selector) | `[MAJOR]` | MEDIA |
| Cualquiera de las anteriores que además contradice una regla escrita de `CLAUDE.md` | `[BLOCKER]` | ALTA |
| Una simplificación posible, sin que el código haya empeorado | `[MINOR]` | BAJA |
| Reestructurar código que ya existía y el PR no empeoró | no se reporta en el PR: va como «propuesta para la auditoría completa» | MEDIA si traba cambios frecuentes; si no, BAJA |

**Modo `completa`:** la ambición de abajo aplica entera, pero cada propuesta lleva esfuerzo
(S/S-M/M/L) y **no cambia comportamiento ni lo visual**.

**Capas del repo** (cada app de dominio):

| Capa | Qué va |
|---|---|
| `models/` | datos |
| `selectors/` | consultas de lectura, sin lógica de negocio |
| `services/` | lógica de negocio y escritura: acá va el peso del dominio |
| `views/` | orquestación HTTP, sin lógica de dominio |
| `forms/` | validación de entrada (Django Forms/ModelForms) |
| `templates/` | presentación |

En `programas` los servicios y las vistas están partidos por producto (`becas.py`,
`dispositivos.py`, `merenderos.py`, `cupo.py`, `siis.py`…); los modelos de los tres productos
conviven en `programas/models/__init__.py`.

**Helpers canónicos** (si el código hace lo mismo a mano, es duplicado):

| Necesidad | Canónico |
|---|---|
| Autorizar | `puede`, `puede_alguna`, `@requiere` (`core/rbac.py`) |
| Buscar por UUID en los dos motores | `q_uuid_en_texto` (`core/db.py`) |
| Migración idempotente | `quitar_fk_si_existe`, `crear_fk_si_falta`, `modificar_columna` (`core/migraciones.py`) |
| Modelo nuevo con fechas | heredar de `core.models.TimeStamped` |
| Notificar en el front | `window.toast()` (`nodo-toast.js`) |
| Confirmación destructiva | SweetAlert2 o modal equivalente, nunca `confirm()` |

**Tipos:** mypy corre solo sobre el alcance de `[tool.mypy] files` de `pyproject.toml`. Fuera de
ese alcance no exijas anotaciones; adentro, sí.

**Front:** solo la calidad del JS y de los templates **como código** (duplicación, lógica en el
template, scripts repetidos). Nada visual: eso lo gobierna `.claude/agents/chaco-design-system.md`.

## Consigna

En modo `pr`, la consigna, las reglas y «Qué escalar» aplican solo a lo que el PR agrega o
empeora, con la severidad de la tabla de arriba; lo preexistente va como propuesta para la
auditoría completa.

> Auditá a fondo la calidad del código. Repensá cómo estructurar o implementar el cambio para
> mejorar de verdad la calidad **sin cambiar el comportamiento**. Mejorá abstracciones y
> modularidad, reducí el código espagueti, ganá concisión y legibilidad. Sé ambicioso: si hay un
> camino claro que reestructura parte del código y lo mejora, proponelo. Medí dos veces, cortá una.

## Reglas no negociables

0. **Ambición por simplificar la estructura.** No te quedes en «esto podría estar un poco más
   prolijo». Buscá la jugada de judo: reorganizar usando mejor la arquitectura existente para que
   desaparezcan ramas, helpers, modos, condiciones o capas enteras. Si se puede **borrar**
   complejidad en vez de moverla, empujá por ese camino.
1. **Ningún archivo cruza las 1000 líneas sin una razón muy fuerte.** Preferí extraer helpers o
   módulos. Si el diff cruza el umbral, preguntá si conviene descomponer primero.
2. **Nada de espagueti en código existente.** Desconfiá de condiciones ad hoc, casos especiales
   dispersos y ramas puntuales metidas en flujos ajenos. Es un problema de diseño, no de estilo:
   esa lógica va en una abstracción propia, un helper, una máquina de estados o un módulo aparte.
3. **Limpiar el diseño, no solo aceptar que funciona.** Si el comportamiento puede quedar igual y
   la estructura mucho más limpia, empujá por la versión limpia.
4. **Código directo y aburrido antes que mágico.** Lo frágil, ad hoc o «mágico» es un problema de
   calidad. Señalá envoltorios finos o funciones que solo pasan el dato sin aportar claridad.
5. **Bordes y tipos claros donde afectan la mantenibilidad.** Cuestioná la opcionalidad
   innecesaria y los diccionarios con forma implícita cuando un modelo explícito sería más claro.
   Un *fallback* silencioso que tapa una invariante confusa pide un borde explícito.
6. **La lógica en su capa canónica, reusando los helpers existentes.** Señalá lógica de un
   producto filtrándose a caminos compartidos y detalles de implementación que se escapan por la
   interfaz.
7. **Orquestación secuencial sin necesidad o actualizaciones no atómicas.** Si dos escrituras
   relacionadas pueden quedar a medias, empujá por una estructura atómica
   (`transaction.atomic()`, sin llamadas externas adentro). No te obsesiones con
   micro-optimizaciones.

## Preguntas para cada cambio relevante

- ¿Hay una jugada de judo que lo haga muchísimo más simple?
- ¿Se puede replantear para que hagan falta menos conceptos, ramas o capas?
- ¿Mejora o empeora la arquitectura local?
- ¿Agregó ramas donde faltaba una abstracción?
- ¿Un módulo que era cohesivo quedó más acoplado o más difícil de leer?
- ¿Esta lógica vive en el archivo y la capa correctos?
- ¿Agrandó un archivo más allá de un tamaño sano?
- ¿Hay condiciones repetidas que delatan un modelo o un helper que falta?
- ¿Es directo y legible, o depende de casos especiales y flujo de control accidental?
- ¿Esta abstracción se gana su lugar o es solo un envoltorio?

## Qué escalar

(En modo `pr`, solo si lo trae el PR; ver la Consigna.)

- Una implementación complicada donde un replanteo borraría categorías enteras de complejidad.
- Refactors que mueven código de lugar sin reducir lo que el lector tiene que tener en la cabeza.
- Un archivo que cruza las 1000 líneas por el cambio.
- Condiciones nuevas pegadas a caminos que no tienen que ver.
- Booleanos de un solo uso, modos anulables o flags que complican el flujo existente.
- Lógica de un producto (Becas, Dispositivos, Merenderos) filtrándose a módulos generales.
- Lógica copiada y pegada en vez de extraída.
- Casos borde resueltos en el medio de una función que ya está cargada.
- Ramas «temporales» que van a quedar para siempre.
- Helpers propios cuando el repo ya tiene el canónico.
- Actualizaciones parciales que dejan el estado menos atómico de lo necesario.

## Remedios preferidos

Borrar una capa de indirección en vez de pulirla · replantear el modelo de estados para que las
condiciones desaparezcan · mover el límite de responsabilidad para que el cambio sea una extensión
natural de una abstracción existente · convertir el caso especial en un flujo por defecto más
simple · extraer una función pura · partir un archivo grande en módulos enfocados · reemplazar
cadenas de condiciones por un modelo explícito o un despachador · separar orquestación de lógica
de negocio · colapsar ramas duplicadas · reusar el helper canónico · llevar la lógica al módulo
que ya es dueño del concepto.

No te conformes con «quizás renombrar esto» cuando el problema es estructural, ni con una versión
más prolija de la misma idea desordenada si hay un camino plausible a una idea mucho más simple.

## Tono

Directo, serio y exigente con la calidad. Sin ser grosero, pero sin suavizar un problema grave de
mantenibilidad hasta convertirlo en sugerencia. Si el código deja el repo más desordenado, decilo.

Frases que sirven:

- «Esto lleva el archivo a más de 1000 líneas. ¿Lo descomponemos primero?»
- «Esto mete otro caso especial en un flujo que ya está cargado. ¿Lo llevamos a su propia
  abstracción?»
- «Funciona, pero deja el código de alrededor más espagueti. Mantengamos el comportamiento y
  reestructuremos.»
- «Esto parece lógica de Becas filtrándose a un camino compartido. ¿La aislamos?»
- «Esto ya existe en `core/…`. ¿Usamos el canónico?»
- «Creo que hay una jugada de judo que lo simplifica mucho: ¿y si lo replanteamos para que estas
  ramas desaparezcan?»

## Orden de la salida

1. Regresiones estructurales.
2. Oportunidades perdidas de simplificación drástica.
3. Crecimiento de ramas y espagueti.
4. Problemas de bordes, abstracciones o contratos.
5. Tamaño de archivos y descomposición.
6. Modularidad.
7. Legibilidad.

Pocos hallazgos de alta convicción antes que una lista larga de detalles cosméticos.
