# Proceso masivo a SIIS desde el backoffice

**Fecha:** 22/09/2026
**Estado:** diseño aprobado, sin implementar

## Problema

Informar a SIIS los 6.395 casos del relevamiento requiere, por cada uno, validar
la compatibilidad, aprobarlo e informar el alta. El comando
`procesar_casos_siis` ya hace ese circuito, pero solo se ejecuta entrando al pod
por línea de comandos, lo que depende de DevOps de ECOM cada vez.

Hace falta dispararlo desde el backoffice, acotado a un programa, sin que la
pantalla quede colgada los 8 a 25 minutos que tarda.

## Alcance

**Adentro:** una pantalla no listada que lanza el proceso para un programa, con
seguimiento del avance y posibilidad de frenarlo.

**Afuera:** cambiar el circuito en sí. Los tres pasos, sus guardas y sus reglas
ya están hechos y probados; esto es una forma nueva de dispararlos.

## Decisiones tomadas

### «Secreta» significa no listada, nunca sin permiso

La pantalla no aparece en ningún menú, link ni botón: se llega por la URL o no se
llega. Pero lo que la protege es una **capacidad RBAC**, no el hecho de estar
escondida. Esconder un botón que aprueba 1.000 casos y los registra en un sistema
provincial no es una medida de seguridad; es una medida de prolijidad.

Se descartó el gesto oculto —N clics en el título, combinación de teclas— porque
agrega JavaScript que hay que mantener y no protege nada: la URL directa sigue
existiendo.

### El total cuenta casos enviados, no casos mirados

Si se piden 1.000, el proceso recorre los pendientes salteando los que tienen
datos faltantes —sin tocarlos— hasta juntar 1.000 con el payload completo. Puede
haber mirado 1.600.

La pantalla distingue dos números que se confunden: **elegidos** (salieron con
todo lo necesario) y **altas** (SIIS las aceptó). La diferencia es lo que el
servicio rechazó por su cuenta. Prometer «1.000 altas» sería mentir: eso no
depende de nosotros.

### Ejecución en un hilo del pod, no en un CronJob

Se evaluaron tres caminos:

| | A favor | En contra |
|---|---|---|
| **Hilo en el pod** | No depende de nadie; arranca al instante | Si el pod se recicla, alguien tiene que retomar |
| **Registro + CronJob** | Sobrevive reinicios solo | ECOM tiene que agregar el CronJob; hasta 1 min de demora |
| **Los dos** | Lo mejor de ambos | También necesita el CronJob |

Se eligió el hilo por tres razones:

1. **ECOM es el cuello de botella.** Un diseño que no los necesita se puede usar
   ya.
2. **El proceso es retomable por construcción.** Un caso con alta `ENVIADO` no se
   vuelve a mandar, así que volver a lanzarlo no duplica nada. Esa propiedad es
   la que hace barata esta opción.
3. **El modo de falla queda visible.** El latido convierte «se colgó y nadie
   sabe» en «interrumpida, ¿continuás?».

Si más adelante ECOM agrega el CronJob, se pasa al esquema mixto sin tocar nada:
el cron llamaría al mismo servicio.

### «Interrumpida» se deduce, no se guarda

Si el estado dice `EN_CURSO` pero el latido tiene más de dos minutos, la corrida
está interrumpida.

Tiene que ser así: cuando el pod muere no queda nadie para escribir «me morí». Un
estado que depende de que el proceso caído lo registre es un estado que nunca se
ve.

La regla de «una corrida por vez» sale de lo mismo: bloquea una corrida
`EN_CURSO` **con latido fresco**. Un pod muerto hace diez minutos no deja el
sistema trabado.

### Una corrida por vez en todo el sistema

Dos corridas simultáneas golpean el mismo SIIS y comparten el freno por errores
seguidos: si el servicio se pone lento, ninguna de las dos frena a tiempo.
Además, dos procesos podrían tomar el mismo caso.

Se descartó «una por programa» por ser complejidad para un escenario que todavía
no existe: hoy hay un solo programa con casos.

### Continuar no reanuda: lanza una corrida nueva

No se guarda por dónde iba. «Continuar» arranca otra corrida por lo que falta, y
los ya enviados se saltean solos. Guardar la posición sería estado que puede
quedar desincronizado, para resolver algo que la idempotencia ya resuelve.

### El correo al ciudadano no se ofrece

Aprobar manda un aviso de resolución (Cambio 44). Mil correos irretractables no
van detrás de un botón oculto. No es una opción de la pantalla; si algún día hace
falta, se decide aparte.

### Siempre solo los casos completos

Mandar uno incompleto no lo informa a SIIS, pero igual lo deja **aprobado** y con
una fila de error para revisar a mano. No hay razón para ofrecer lo contrario, así
que no es una opción.

## Diseño

### Modelo

`CorridaSiis`, una fila por corrida:

| Campo | Para qué |
|---|---|
| `programa` | a qué programa se acotó |
| `solicitada_por`, `iniciada`, `finalizada` | quién y cuándo |
| `total_pedido` | el número que se tipeó |
| `estado` | `EN_CURSO` · `TERMINADA` · `CANCELADA` · `DETENIDA` |
| `latido` | se reescribe al cerrar cada lote |
| `cancelacion_pedida` | lo marca el botón Frenar |
| `mensaje` | por qué terminó, cuando no fue por llegar al total |
| contadores | mirados, elegidos, aprobados, lista de espera, altas, incompletos, rechazados, errores |

«Salteados» no se guarda: es `mirados - elegidos`. «Incompletos» debería quedar
siempre en cero, porque solo se eligen casos con el payload completo; si alguna
vez sube, es la señal de que algo cambió entre la selección y el envío.

Propiedad derivada `interrumpida`: `estado == EN_CURSO` y latido de más de dos
minutos.

### Servicio

El bucle sale del comando y pasa a `programas/services/proceso_masivo.py`. El
comando `procesar_casos_siis` y la vista llaman al mismo servicio: no hay dos
implementaciones que se desincronicen.

El ejecutor se inyecta. En producción lanza un hilo; en los tests corre
sincrónico. Sin eso las pruebas serían una carrera.

El hilo tiene dos obligaciones, las dos aprendidas rompiéndolas antes:

- **Cerrar su conexión a la base al terminar.** Django abre una por hilo.
- **Nada de una transacción que envuelva toda la corrida.** Es lo que dejó a
  `completar_casos_renaper` una hora sin confirmar contra ECOM. Cada caso se
  confirma solo, y por eso se puede cortar y retomar.

### Pantalla

`/becas/config/programas/<id>/proceso-masivo/`, detrás de
`becas.programa.proceso_masivo`.

**Sin corrida:** aviso de que el alta no se deshace, cuántos casos hay
pendientes, campo de cantidad con 1.000 por defecto, botón Procesar, y el
resultado de la última corrida.

**Corriendo:** barra de avance, contadores separados, quién la lanzó y hace
cuánto, botón Frenar. Se refresca sola cada cinco segundos.

**Interrumpida:** el aviso, hasta dónde llegó y el botón Continuar.

El lote es de 40 casos y no se configura desde la pantalla: es el tamaño con el
que ya corre el comando y no hay razón para que el operador lo elija.

Frenar marca la corrida; el proceso corta **al terminar el lote en curso**, no a
mitad de un caso. Por eso puede tardar hasta 40 casos en parar.

### Permiso

Capacidad `becas.programa.proceso_masivo`, agregada al `CATALOGO` de
`core/rbac.py` con alcance de programa. No se asigna a ningún rol en el seed: se
tilda a mano en el ABM de Roles.

## Cómo termina una corrida

| Desenlace | Estado |
|---|---|
| Llegó al total pedido | `TERMINADA` |
| Se apretó Frenar | `CANCELADA` |
| 10 errores técnicos seguidos | `DETENIDA` — SIIS no responde |
| El catálogo de SIIS se cayó | `DETENIDA` con el motivo |
| Excepción no prevista | `DETENIDA`, con el error escrito en la corrida |

## Pruebas

- Una segunda corrida se bloquea mientras hay una con latido fresco.
- Una corrida con latido viejo **no** bloquea.
- Frenar corta al cerrar el lote, no antes.
- El freno por errores técnicos seguidos dispara y deja el motivo.
- Los casos salteados por datos faltantes no se modifican.
- El total cuenta enviados, no mirados: con 1 pedido y el primer candidato
  incompleto, procesa el segundo.
- Sin la capacidad, la URL responde 403.

## Riesgo abierto, previo a usar esto

No está confirmado si SIIS interpreta `loc_actual` como el id numerado por
provincia —lo que dice el catálogo del organismo y lo que implementó el Cambio
86— o como un id global. Si fuera global, las altas entrarían con el domicilio
equivocado **sin dar error**.

La primera corrida tiene que ser de **un caso**, verificando en SIIS con qué
domicilio quedó registrado. El campo de cantidad existe, entre otras cosas, para
poder hacer eso.
