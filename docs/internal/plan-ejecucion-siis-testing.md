# Plan de ejecución — alta masiva en SIIS (ambiente de testing)

**Ambiente:** `datanach-test` · https://datanach.ecomdev.ar
**Fecha:** 22/09/2026

Todos los comandos se corren **dentro del pod de `web`**:

```bash
kubectl -n datanach-test exec -it deploy/web -c <contenedor-app> -- bash
```

Los comandos que escriben piden `--aplicar`. **Sin ese flag no tocan nada**: cuentan,
informan y salen. Correr primero en seco siempre.

---

## Requisitos previos

Dos cosas del ambiente, ninguna de la aplicación.

### R1 · Apagar el correo saliente

En el configmap de `datanach-test`, **vaciar `EMAIL_HOST`**.

Django decide el backend por la presencia de esa variable: vacía, los correos se
imprimen por consola y no salen. Sin esto, cualquier prueba en testing le manda
mail a ciudadanos reales, porque la base es copia de producción.

Requiere reiniciar los pods. No requiere cambios de código.

### R2 · Destrabar el deploy

El Job `web-bootstrap-migration` quedó colgado. El entrypoint arranca con un
`wait_for_database` que reintenta cada 2 s **sin límite**, así que si el pod no
llega a MySQL se queda ahí sin fallar nunca.

```bash
# Primero guardar el log: se pierde al borrar el pod
kubectl -n datanach-test logs job/web-bootstrap-migration --tail=50 > /tmp/bootstrap.log
kubectl -n datanach-test delete job web-bootstrap-migration
```

Argo tiene auto-sync y lo recrea solo.

Aprovechar y limpiar cuatro CronJobs colgados desde hace horas:

```bash
kubectl -n datanach-test delete job datanach-generar-alertas-29833740
kubectl -n datanach-test delete job datanach-limpiar-alertas-conversaciones-29834310
kubectl -n datanach-test delete job datanach-procesar-vencimientos-29834290
kubectl -n datanach-test delete job datanach-sincronizar-programas-siis-29834340
```

---

## Fase 0 · Cargar el padrón de RENAPER

**Solo si la tabla no existe todavía.** Se corre contra MySQL, no desde el pod: la
imagen no trae cliente de base.

```bash
mariadb -h <host> -u <usuario> -p <base> < scripts/DatosPersonas.sql
```

**Esperado:** 10.321 filas en la tabla de personas.

```sql
SELECT COUNT(*) FROM DatosPersonas;
-- 10321
```

---

## Fase 1 · Verificar el catálogo geográfico

Se carga **solo** en el arranque del contenedor. Este paso solo confirma que pasó.

```bash
python manage.py seed_catalogo_siis
```

**Esperado:**

```
Provincias: 0 nuevas, 30 ya estaban
Localidades: 0 nuevas, 275 ya estaban
Equivalencias: 0 nuevas, 16 ya estaban (5 sin destino a propósito)
```

Si dice **30 nuevas / 275 nuevas**, es que el bootstrap no lo había corrido. No
es un problema: acaba de cargarlo. Es idempotente.

> **Si falla** con «Falta el archivo de datos»: los CSV no llegaron a la imagen.
> Avisar y frenar acá.

---

## Fase 2 · Completar los casos desde RENAPER

Le da a cada caso su copia del formulario y completa CUIT, CUIL, provincia y
localidad de nacimiento cruzando por DNI.

**Primero en seco:**

```bash
python manage.py completar_casos_renaper
```

**Después de verdad:**

```bash
python manage.py completar_casos_renaper --aplicar --lote 50
```

**Esperado** (medido el 21/09 sobre este mismo ambiente):

| | |
|---|---|
| Casos con foto del formulario | 6.395 |
| CUIT completado | ~6.270 |
| CUIL completado | ~5.098 |
| Provincia de nacimiento | ~6.382 |
| Localidad de nacimiento | ~6.382 |

Avanza en lotes de 50 con una línea de log por lote. **Se puede cortar con Ctrl+C
sin riesgo**: lo hecho queda confirmado y volver a correrlo continúa donde iba.

Si ya se corrió antes, va a informar números bajos o cero. Es correcto: solo llena
lo que está vacío.

---

## Fase 3 · Ver cuánto cruza la geografía

No modifica nada. Dice qué localidades no se pueden traducir al catálogo de SIIS.

```bash
python manage.py seed_catalogo_siis --revisar
```

**Esperado, aproximado:**

```
DOMICILIO — 6395 casos
   cruza                        5653   88.4%
   cruza por equivalencia        331    5.2%
   no cruza                      339    5.3%

NACIMIENTO — 6395 casos
   cruza                        6052   94.6%
   cruza por equivalencia        219    3.4%
   no cruza                      111    1.7%
```

Lo importante: **«cruza» + «cruza por equivalencia» arriba del 93 %**.

Si «no cruza» es mucho más alto, avisar: probablemente el catálogo no se cargó.

---

## Fase 3b · Cargar la tabla de aprobados (Cambio 90)

**Obligatoria antes de la Fase 5.** A SIIS solo van los DNI que figuren en
`aprobados_materias`. Si la tabla no existe, `procesar_casos_siis` y la pantalla
del proceso masivo **se niegan a correr**, a propósito.

La carga el organismo desde su planilla. Se corre contra MySQL, no desde el pod:

```bash
mariadb -h <host> -u <usuario> -p <base> < scripts/aprobados_materias_plantilla.sql
```

El archivo trae el `CREATE TABLE` y un `INSERT` de ejemplo: hay que reemplazar los
DNI de ejemplo por los reales, uno por fila. Con puntos o sin puntos, con o sin
ceros a la izquierda, da lo mismo: el sistema normaliza antes de cruzar.

**Esperado:** la última línea del script devuelve la cantidad de DNI cargados.

```sql
SELECT COUNT(*) AS dni_habilitados FROM aprobados_materias;
```

> **Si el ensayo de la Fase 5 dice** «No existe la tabla `aprobados_materias`»,
> es esto. Cargarla y volver a correr.

Cuando corra la Fase 5, el ensayo informa cuántos pendientes quedan afuera por no
figurar en la tabla, separado de los incompletos:

```
Filtro por aprobados_materias: 4213 de 6681 pendientes quedan afuera por no figurar en la tabla.
```

---

## Fase 4 · Configurar los identificadores del programa

**Esto lo hace el equipo de DATAÑACH desde la pantalla, no DevOps.** Se documenta
acá porque el resto no funciona sin este paso.

Detalle del programa → tarjeta «Alta de beneficiarios en SIIS». Tres números que
viajan en cada alta: `id_plan_soc`, `jurid`, `id_fun_x_plan`.

---

## Fase 5 · La primera corrida: UN caso

> **Este paso no se saltea.**
>
> Todavía no está confirmado si SIIS interpreta el id de localidad como numerado
> **por provincia** o como un id **global**. Si fuera global, las altas entran con
> el domicilio equivocado y **SIIS las acepta igual, sin dar error**. No hay forma
> de darse cuenta salvo mirando.

```bash
python manage.py procesar_casos_siis --solo-completos --total 1 --lote 40 --aplicar --usuario <usuario>
```

**Esperado:**

```
Candidatos pendientes: NNNN. Armando el payload de cada uno…
A procesar: 1 casos en 1 lotes de 40

   lote   1/1 · casos XXXX-XXXX · aprobados 1 · altas 1 · incompletos 0 · errores 0

Resumen
   aprobados                                   1
   altas hechas en SIIS                        1
```

**Después de esto, PARAR.** Alguien de DATAÑACH tiene que entrar a SIIS y verificar
con qué **domicilio** quedó registrada esa persona.

- Localidad correcta → seguir a la Fase 6.
- Localidad equivocada → **frenar todo** y avisar. Hay que corregir el catálogo.

---

## Fase 6 · La corrida grande

Solo con la Fase 5 verificada.

```bash
python manage.py procesar_casos_siis --solo-completos --total 1000 --lote 40 --pausa 2 --aplicar --usuario <usuario>
```

Por cada caso: lo valida contra SIIS, lo aprueba y lo informa. Lotes de 40 con 2
segundos entre lotes.

**El total cuenta casos que se mandan, no casos que se miran.** Si pide 1000,
recorre los pendientes salteando —sin tocarlos— a los que les falta un dato, hasta
juntar 1000 con el payload completo. Puede haber mirado 1600.

**Esperado:**

```
Resumen
   aprobados                                 ~1000
   sin cupo → lista de espera                    N
   altas hechas en SIIS                       ~990
   altas rechazadas por SIIS                     N
   altas con error técnico                       0
```

### Qué significa cada final

| Final | Qué pasó | Qué hacer |
|---|---|---|
| `Listo en N s` | Terminó | Nada |
| `DETENIDO tras 10 errores técnicos seguidos` | SIIS no responde | Esperar y volver a correr. Lo hecho quedó |
| Ctrl+C | Cortado a mano | Volver a correr: sigue donde iba |

**Se puede cortar en cualquier momento.** Un caso ya informado no se vuelve a
mandar, así que reejecutar nunca duplica.

---

## Alternativa: la pantalla

Las fases 5 y 6 también se pueden hacer desde el navegador, sin entrar al pod:

```
/becas/config/programas/<id>/proceso-masivo/
```

No figura en ningún menú. Requiere la capacidad `becas.programa.proceso_masivo`,
que hay que tildar a mano en el ABM de Roles. Tiene campo de cantidad, barra de
avance y botón para frenar.

---

## Resumen de comandos

```bash
# 1. Verificar catálogo
python manage.py seed_catalogo_siis

# 2. Completar desde RENAPER (seco, después real)
python manage.py completar_casos_renaper
python manage.py completar_casos_renaper --aplicar --lote 50

# 3. Ver cuánto cruza
python manage.py seed_catalogo_siis --revisar

# 3b. Cargar aprobados_materias (contra MySQL, no desde el pod) - ver Fase 3b

# 4. UN caso, y verificar en SIIS antes de seguir
python manage.py procesar_casos_siis --solo-completos --total 1 --lote 40 --aplicar --usuario <usuario>

# 5. El resto
python manage.py procesar_casos_siis --solo-completos --total 1000 --lote 40 --pausa 2 --aplicar --usuario <usuario>
```

## Contacto ante dudas

Cualquier salida que no coincida con lo esperado, **frenar y consultar** antes de
seguir. Ninguna de las fases 1 a 3 es destructiva; las fases 5 y 6 registran
personas en SIIS y eso **no se puede deshacer desde DATAÑACH**.
