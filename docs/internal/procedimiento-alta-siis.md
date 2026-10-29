# Alta masiva en SIIS — procedimiento

**Universo:** 7.506 casos · 7.496 candidatos (los que figuran en `aprobados_materias`)
**Duración total:** ~1 h 30 min

> **¿Hay que volver a hacerlo?** Empezá por la sección siguiente, «Camino probado en PRD»: es la
> corrida real del 28–29/10/2026, paso a paso, con los comandos que se pegaron en el pod y los números
> que dieron. Los pasos 1 a 8 de más abajo son el procedimiento original (01/10) y siguen valiendo como
> referencia de cada comando.

---

## Camino probado en PRD — Convocatoria 1 (28–29/10/2026)

Corrida real: primero **simulada en testing** (base = dump de PRD del 27/10, `--destino tabla`) y
después **hecha en PRD**: **1.786 altas** en SIIS de producción, `ENVIADO` con su `siis_id`.

### Cómo se trabajó (sin acceso directo a la base de PRD)

- La base de PRD (`mdbk8s.ecom.com.ar`) **no se alcanza por VPN**. Hubo dos vías:
  - **ECOM (Fabián Insaurralde)** corre los `.sql` de insumos en su consola SQL; pedirle `-t` y
    **sin** `--force`, para que frene en el primer error.
  - **Consola del pod `web` de PRD**: la imagen no trae cliente `mysql`, así que todo control va por
    `python manage.py shell <<'FIN' … FIN`.
- Los `.sql` con datos personales **no van al repo** (export-ignore + RED-01) ni a la imagen. Subirlos
  al repo para tenerlos en el pod obligaría además a un deploy completo de PRD. Se le pasan a ECOM.
- La conexión de la app tiene `read_timeout` de 10 s. Un control que recorre el JSON de todos los
  formularios (por ejemplo, las marcas `destinos_siis`) **se parte en tramos de 500 ids**
  (`for desde in range(0, max_id, 500): qs.filter(pk__gt=desde, pk__lte=desde + 500)…`), o muere con
  `OperationalError` *Lost connection to server during query*.
- **En ECOM no se filtra por fecha con `creado__date`**: se traduce a `CONVERT_TZ`, la base no tiene
  tablas de zona horaria y devuelve **vacío** (no error). Para lo reciente, ordenar por id o usar
  `creado >= CURDATE() - INTERVAL 1 DAY` en SQL crudo: trae desde ayer a las 00:00, un margen a
  propósito porque `creado` está en UTC y la corrida es en hora argentina.

### Decisiones del PM para esta corrida

| Tema | Decisión |
|---|---|
| Universo | Solo la **Convocatoria 1** (la beca). Quedan afuera los cursos (relevamientos 4 y 5) |
| Lista de exclusión (`siis_enviar`) | No se usó |
| Localidad declarada «San Fernando», «Resistencia San Fernando», «Argentina», «Chaco», «Chaco - Resistencia» | → **RESISTENCIA** (63 DNI agregados a `localidades_corregidas`) |
| `aprobados_materias` | Se **reemplaza** la vieja («0 materias») por la planilla del 27/10: 8.570 DNI |
| 3 apoderados con fecha imposible (casos 67, 1409, 6690: años 1090, 1665 y 3) | **No se corrigen.** SIIS los rechaza; se sacaron de la tabla intermedia |

### Orden real de ejecución

| # | Dónde | Qué | Resultado en PRD |
|---|---|---|---|
| 1 | ECOM (consola SQL) | `Aprobados.sql` (DROP + CREATE), `Localidades.sql`, `DatosPersonas.sql` si falta `ciudadanos_renaper` | ver huellas abajo |
| 2 | ECOM (consola SQL) | Preparación: los 7 destinos SIIS de los requisitos (13, 14, 15, 16, 17, 25, 28), `JSON_REMOVE` de las marcas `destinos_siis = []`, 63 DNI → Resistencia | 7 destinos · 5.261 marcas → 0 · 63 DNI |
| 3 | Pantalla | Programa vinculado a SIIS: programa **90**, plan 90, jurid 28, función 4 «Ñachec colaboradores nivel 4» | — |
| 4 | Pod | `sincronizar_programas_siis` y `correr_alta_siis --solo-precondiciones --sin-insumos` | OK |
| 5 | Pod | **`seed_catalogo_siis`** (en PRD el padrón estaba vacío: 0/0/0) | 30 provincias · 275 localidades · 28 + 1 alias |
| 6 | Pod | `corregir_datos_siis` (ensayo y después `--aplicar`) | 1.339 casos escritos · 25 legajos |
| 7 | Pod | `procesar_casos_siis --destino tabla` en tandas | 1.789 en `siis_tabla_intermedia` |
| 8 | Pod (`manage.py shell`) o ECOM | Control de la tabla intermedia | ver abajo |
| 9 | Pod | Envío a SIIS **de a lotes** con script (no con el comando) | 1.786 `ENVIADO` |

**Huellas de los insumos** (confirman que se cargó el archivo correcto sin mirar datos):

```sql
SELECT COUNT(*), SUM(CRC32(dni)) FROM aprobados_materias;              -- 8570, 17996118160594
SELECT COUNT(*), SUM(CRC32(dni)) FROM localidades_corregidas;          -- 4777, 9880505386725 (con los 63)
SELECT COUNT(*), SUM(CRC32(dni_consultado)) FROM ciudadanos_renaper;   -- 10321, 21930136131971
```

**Paso 6 — corrección de datos:**

```bash
python manage.py corregir_datos_siis --convocatoria 1 --fecha-nacimiento-renaper --heredar-nacimiento \
  --fecha-apoderado 1990-01-01 --barrio-generico "Sin especificar" \
  --estado-civil-sin-equivalente "Soltero/a" --usuario <usuario>         # ensayo; después + --aplicar
```

Escribe **solo** `formulario.datos_siis` (y la fecha de nacimiento de 25 legajos). No llama a SIIS ni
toca la tabla intermedia. Dio idéntico en testing y en PRD: 274 localidades desde la planilla, 147 que
no cruzan, 129 barrios genéricos, 442 apoderados con el DNI del propio alumno.

**Paso 7 — a la tabla intermedia, en tandas de 200 con pausa.** SIIS corta por exceso de pedidos
alrededor de 300 por minuto; en la validación eso queda como `ERROR` reintentable.

```bash
for i in $(seq 1 40); do
  python manage.py procesar_casos_siis --destino tabla --convocatoria 1 --solo-completos --total 200 --lote 40 --si --aplicar --usuario <usuario> 2>&1 | grep -v connectionpool > /tmp/tanda.log
  echo "== tanda $i =="; grep -E "aprobados  |incompatibles|error técnico  |tabla intermedia|DETENIDO|No hay casos" /tmp/tanda.log
  grep -q "No hay casos" /tmp/tanda.log && break
  sleep 90
done
```

Si la consola se corta, se vuelve a pegar: sigue desde donde quedó, y los incompatibles no se
reconsultan. Resultado en PRD (34 tandas, ~75 min), contado en `programas_validacionsis`:

| Validación | Casos | Qué es |
|---|---|---|
| OK → tabla intermedia | **1.789** | |
| `duplicidad_becas` | **4.672** | Ya tenían la beca en SIIS de producción: la primera vuelta se cargó por otra vía |
| `edad_minima` | 52 | Rechazo legítimo |
| `empleo_publico` | 3 | Rechazo legítimo |
| `ERROR` por exceso de pedidos | 47 | Se reintentaron solos |

**Paso 8 — control de la tabla intermedia:**

Las consultas miran **solo lo pendiente** (`sincronizado = 0`): las filas de corridas anteriores no se
borran al sincronizar. En el pod no hay cliente `mysql`, así que se corren dentro de
`manage.py shell` con `from django.db import connection; c = connection.cursor(); c.execute("…");
print(c.fetchall())`, o las corre ECOM en su consola.

```sql
SELECT COUNT(*), COUNT(DISTINCT dni) FROM siis_tabla_intermedia WHERE sincronizado = 0;       -- iguales
SELECT id_plan_soc, jurid, id_fun_x_plan, COUNT(*) FROM siis_tabla_intermedia
 WHERE sincronizado = 0 GROUP BY 1,2,3;                                                      -- un solo grupo
SELECT SUM(loc_actual IS NULL), SUM(fecha_nacim IS NULL) FROM siis_tabla_intermedia
 WHERE sincronizado = 0;                                                                     -- 0, 0
SELECT COUNT(*) FROM siis_tabla_intermedia
 WHERE sincronizado = 0 AND fecha_nacim > CURDATE() - INTERVAL 18 YEAR AND dni_apoderado IS NULL; -- 0
SELECT formulario_id, fecha_nacim_apoderado FROM siis_tabla_intermedia
 WHERE sincronizado = 0 AND fecha_nacim_apoderado < '1753-01-01';                            -- sacarlas
```

La última consulta encuentra las fechas que **el SQL Server de SIIS no acepta** (anteriores a 1753):
SIIS contesta `503 ERROR_BD_LEGACY` «conversion of a varchar data type to a datetime». Ese error se
reintenta, así que la fila vuelve a salir en cada lote y frena el envío: hay que **sacarla de la tabla**
antes de mandar (`AltaIntermediaSIIS.objects.filter(formulario_id__in=[…], sincronizado=False).delete()`).
El caso no cambia; si después le corrigen la fecha, se regenera con `--destino tabla`.

**Paso 9 — envío real a SIIS, de a lotes.** **No usar `procesar_casos_siis --destino siis` para vaciar
una tabla intermedia grande**: drena **todas** las filas pendientes de una sola vez, sin `--total`, sin
pausa y sin freno. En el **alta**, el corte por exceso de pedidos (HTTP 429) **no es reintentable**: el
envío queda `INCIERTO` y hay que conciliarlo con ECOM. Se usa la misma función del comando, con límite:

```bash
python manage.py shell <<'FIN'
import time
from django.contrib.auth import get_user_model
from django.db.models import Count
from core.checks import escritura_siis_bloqueada
from programas.models import AltaIntermediaSIIS, EnvioSIIS
from programas.services.siis_envio import sincronizar_tabla_intermedia

LOTE, PAUSA, MAX_LOTES = 1, 0, 1        # PRUEBA de 1 caso. Masivo: 40, 60, 50

assert not escritura_siis_bloqueada(), "Este ambiente NO puede escribir en SIIS: frenado"
yo = get_user_model().objects.get(username="<usuario>")
for i in range(1, MAX_LOTES + 1):
    pend = AltaIntermediaSIIS.objects.filter(sincronizado=False).count()
    if not pend:
        print("No quedan pendientes."); break
    t = time.time()
    c = sincronizar_tabla_intermedia(yo, limite=LOTE)
    print(f"lote {i:>2} · pendientes antes {pend:>5} · {c} · {time.time()-t:.0f} s", flush=True)
    if c["errores"] or c["rechazadas"] or c["no_aprobables"] or c["excluidas"]:
        print("FRENO: hubo errores/rechazos."); break
    if i < MAX_LOTES:
        time.sleep(PAUSA)
print("pendientes:", AltaIntermediaSIIS.objects.filter(sincronizado=False).count())
print("envíos por estado:", list(EnvioSIIS.objects.values_list("estado").annotate(n=Count("id")).order_by("estado")))
FIN
```

1. Primero **1 caso**, y verificarlo:
   `AltaIntermediaSIIS.objects.filter(sincronizado=True).order_by("-sincronizado_en").first().envio`
   tiene que estar `ENVIADO` con `siis_id`.
2. Después el masivo con `40, 60, 50`. Un lote de 100 tardó 20 s, que es el ritmo en el que SIIS
   empieza a cortar; con 40 por minuto queda muy lejos. Tarda unos 45 minutos.
3. Si frena, mirar el error antes de seguir:
   `EnvioSIIS.objects.filter(estado__in=["ERROR", "INCIERTO", "EN_PROCESO"])` → `codigo_error`,
   `detalles`, `respuesta`. **No alcanza con `ERROR`:** un 429 o un 408 deja el envío `INCIERTO`.
4. **Antes de volver a pegar el script** (porque frenó o porque se cortó la consola), revisar si quedó
   algún `INCIERTO` o algún `EN_PROCESO` de más de 5 minutos. Si hay, **no se vuelve a pegar** hasta
   conciliarlo con `conciliar_envios_siis --listar` → ECOM → `--confirmar`/`--liberar --aplicar`.
   Motivo: el script marca `sincronizado` **sin contarla ni frenar** a toda fila cuyo caso ya tenga un
   envío vigente (`siis_envio.py`, rama `envios_sis.filter(vigente=True)`), y `INCIERTO` y `EN_PROCESO`
   cuentan como vigentes. Si se vuelve a pegar antes, el alta dudosa desaparece de la vista e imprime
   «pendientes: 0». Una vez conciliado, lo `ENVIADO` no se repite y una fila liberada vuelve a salir en
   el próximo lote.

Resultado final en PRD: **`ENVIADO` 1.786** · `ERROR` 1 (caso 67, la fecha imposible, antes de sacarla
de la tabla) · `INCOMPLETO` 2 (envíos viejos del 13 y el 15/10).

### Qué quedó abierto después de esta corrida

| Tema | Estado |
|---|---|
| 4.672 `duplicidad_becas` | Confirmar con SIIS que están en el programa 90, y decidir qué estado muestran en DATAÑACH (hoy: incompatibles, no aprobados) |
| 3 apoderados con fecha imposible | Si se corrigen, regenerar con `--destino tabla` y mandar |
| 147 localidades que no cruzan | Sumarlas a la planilla o agregar equivalencias en el padrón |
| 52 por `edad_minima`, 3 por `empleo_publico` | Rechazos legítimos de SIIS: no se hace nada |

---

## 1 · Preparar el ambiente

- [ ] Vaciar `EMAIL_HOST` en el configmap. Reiniciar pods.
- [ ] Verificar que el comando existe: `python manage.py corregir_datos_siis --help`

⏱ 5 min

---

## 2 · Cargar las tablas de insumo

Contra la base, **no desde el pod** (la imagen no trae cliente):

```bash
mariadb -h <host> -u <usuario> -p --skip-ssl <base> < $DATOS_SIIS_DIR/Aprobados.sql
mariadb -h <host> -u <usuario> -p --skip-ssl <base> < $DATOS_SIIS_DIR/Localidades.sql
```

> Los `.sql` **no están en el repositorio ni en la imagen**: tienen datos personales
> reales (Cambio 116, RED-01). Viven en el directorio que apunta `DATOS_SIIS_DIR`
> —por defecto `/datos-siis`—, montado como volumen de solo lectura. Si no está
> montado, `correr_alta_siis` corta antes de tocar nada y nombra la variable. De
> dónde sale cada archivo: [`scripts/README-datos-siis.md`](../../scripts/README-datos-siis.md).

| Tabla | Filas esperadas |
|---|---|
| `aprobados_materias` | 15.531 |
| `localidades_corregidas` | 4.714 |
| `ciudadanos_renaper` | 10.321 (ya viene en la base) |

⏱ 2 min

---

## 3 · Configurar en la pantalla

**3a.** Catálogo de requisitos → "Este dato alimenta a SIIS como":

| id | Pregunta | Destino |
|---|---|---|
| 13 | Provincia | `prov_actual` |
| 14 | Localidad | `loc_actual` |
| 15 | Barrio | `barrio_actual` |
| 16 | Calle y altura | `calle_altura` |
| 17 | Estado Civil | `est_civil` |
| 25 | Provincia Nacimiento | `prov_nacim` |
| 28 | Localidad de nacimiento | `loc_nacim` |

**3b.** Detalle del programa → «Alta de beneficiarios en SIIS» → `id_plan_soc`, `jurid`, `id_fun_x_plan`

> Sin esto no sale ningún alta. Y si se corre el paso 5 sin esto, el sistema no ve
> las respuestas del formulario y pisa los barrios reales con el genérico.

⏱ 10 min

---

## 4 · Catálogo geográfico — EL PASO QUE MÁS CARO SALE SALTEAR

```bash
python manage.py seed_catalogo_siis
```

Esperado: **30 provincias · 275 localidades · 32 equivalencias**

Verificar que diga esos tres números antes de seguir:

```sql
SELECT (SELECT COUNT(*) FROM programas_provinciasiis) AS prov,
       (SELECT COUNT(*) FROM programas_localidadsiis) AS loc,
       (SELECT COUNT(*) FROM programas_aliaslocalidadsiis) AS alias;
```

> **Un restore deja este catálogo vacío** (producción lo tiene así). Y sin él, el
> sistema cae a la API de SIIS, que **devuelve posiciones de una lista, no ids**:
> el 01/10/2026 eso mandó 4.139 altas con la localidad equivocada —un chico de
> Machagai quedó registrado en Colonia Popular, uno de Sáenz Peña en Fontana—.
> Resistencia y Barranqueras coincidieron de casualidad, por estar primeras en
> las dos listas.

⏱ 10 seg

---

## 5 · Completar desde RENAPER

```bash
python manage.py completar_casos_renaper --aplicar --lote 50
```

Si la base viene de un restore reciente, puede dar `Lost connection`: esperar a que
el restore termine del todo y reintentar.

⏱ 5 min

---

## 5b · (Opcional) Dejarlo en la tabla intermedia primero

Si se quiere revisar la corrida entera antes de que SIIS vea nada:

```bash
python manage.py correr_alta_siis --destino tabla --aplicar --usuario <user>
```

No llama a SIIS. Deja las altas en `siis_tabla_intermedia`, con los campos como columnas, para revisarlas por
SQL o entregárselas al organismo. No hay caso de prueba ni freno: no hay nada que verificar del otro lado.

Revisión típica antes de mandar:

```sql
SELECT prov_actual, loc_actual, COUNT(*) FROM siis_tabla_intermedia GROUP BY 1, 2 ORDER BY 3 DESC;
SELECT COUNT(*) FROM siis_tabla_intermedia WHERE fecha_nacim_apoderado < '1753-01-01';
SELECT COUNT(*) FROM siis_tabla_intermedia WHERE nro_actual >= 10000;
```

Cuando esté revisado, la corrida normal con `--destino siis` **vacía esa tabla primero** y después sigue con
los casos nuevos. Nada se queda ahí.

---

## 6 · Corregir los datos

```bash
python manage.py corregir_datos_siis \
    --fecha-nacimiento-renaper --heredar-nacimiento \
    --barrio-generico "Sin especificar" --fecha-apoderado 1990-01-01 \
    --estado-civil-sin-equivalente "Soltero/a" \
    --aplicar --limite 999999
```

Esperado, aproximado:

| Corrección | Casos |
|---|---|
| Localidad del domicilio | ~280 |
| Localidad de nacimiento | ~200 |
| Barrio | ~186 |
| Fecha del apoderado | ~520 |
| Fecha de nacimiento del titular (legajo) | 31 |
| Estado civil que SIIS no tiene («Separado/a») | 11 |

Mirar dos líneas del resumen: **"la planilla tampoco cruza"** y **"su DNI no está en la
planilla"**. Son la lista de trabajo para la próxima vuelta.

⏱ 15 min

---

## 7 · UN caso, y parar — NO ES UN TRÁMITE

```bash
python manage.py procesar_casos_siis --solo-completos --total 1 --lote 40 --aplicar --usuario <usuario>
```

**Frenar acá.** Pedirle a alguien que abra ese caso en SIIS y verifique con qué
**localidad** quedó registrado.

Elegir un caso del interior (Machagai, Quitilipi, Sáenz Peña), **no de Resistencia**:
una localidad mal mapeada puede coincidir igual si está primera en las dos listas.

Y controlar el id contra el catálogo antes de mirar en SIIS:

```sql
SELECT JSON_VALUE(e.payload, '$.loc_actual') AS id_enviado,
       (SELECT nombre FROM programas_localidadsiis
        WHERE siis_id = JSON_VALUE(e.payload, '$.loc_actual')) AS deberia_ser
FROM programas_enviosiis e WHERE e.estado = 'ENVIADO' ORDER BY e.id DESC LIMIT 1;
```

> El 01/10/2026 se salteó esta verificación y 4.139 personas quedaron con el
> domicilio equivocado. SIIS las aceptó sin un solo error.

⏱ 1 min + verificación humana

---

## 8 · La corrida completa

```bash
python manage.py procesar_casos_siis --solo-completos --total 999999 --lote 40 --pausa 2 --aplicar --usuario <usuario>
```

Esperado: **~7.350 altas** de 7.496 candidatos.

Volver a correrlo al terminar. Si dice `No hay casos que procesar`, no quedó ninguno.

El resumen cuenta aparte los **incompatibles según SIIS**: casos que SIIS contestó
que no corresponden al programa. En lote no se aprueban —en la pantalla eso lo
decide el revisor, y acá no hay revisor— y quedan como estaban, para que alguien
los mire desde la revisión. No son un error ni se pierden.

Una vez que SIIS los declaró incompatibles **salen de la lista de candidatos**:
si siguieran, cada corrida los volvería a consultar y se gastaría en ellos. La
pantalla del proceso masivo los cuenta aparte («Incompatibles según SIIS») para
que no desaparezcan. Vuelven solos si alguien los revalida y SIIS cambia de
opinión, o si cambia el DNI o el plan del caso: ahí el veredicto viejo ya no
corresponde.

⏱ 65 min

---

## Qué queda afuera

| Motivo | Casos | Se puede? |
|---|---|---|
| Localidad que no cruza y no está en la planilla | ~137 | Sumándolos a la planilla |
| Fecha de nacimiento imposible, sin fila en RENAPER | 6 | Consultando RENAPER en vivo |
| Caso sin ningún dato cargado | 1 | No |
| «Localidad» que es un departamento, provincia o país | ~20 | Decisión del organismo |

---

## Si algo sale mal

| Situación | Qué hacer |
|---|---|
| `Hay una corrida masiva en curso (#N, …)` | Alguien lanzó el proceso desde la pantalla. Los dos caminos toman los mismos casos y cada uno lleva su propio freno, así que el comando no arranca. Esperar a que termine o frenarla desde la pantalla. Si de verdad no hay alternativa: `--ignorar-corrida --motivo "…"`, que exige el motivo y lo deja escrito en el log y en la corrida que pisa. **La guarda es de una sola dirección**: frena a un comando que arranca con la pantalla corriendo, pero no al revés —si el comando ya está corriendo, alguien puede lanzar la corrida desde la pantalla—. Lo irreversible sigue cubierto igual (un caso no se puede informar dos veces, SIIS-01); lo que se cruza son las cuentas y los frenos. |
| `Lost connection to server during query` | La base está saturada (restore en curso). Esperar y reintentar. |
| `DETENIDO tras 10 errores técnicos seguidos` | SIIS no responde. Esperar y volver a correr: lo hecho queda. |
| Ctrl+C a mitad | No duplica. El caso que estaba en vuelo queda `EN_PROCESO` y, pasados 5 minutos, se ve como **incierto**: no se sabe si SIIS lo registró. Volver a lanzar el comando retoma el resto y **no lo toca**; ese se resuelve con `conciliar_envios_siis` (abajo). |
| Un caso quedó `INCIERTO` | No se reenvía por ninguna vía. Se concilia con ECOM: ver «Envíos de resultado desconocido». |
| Se corrió el paso 6 sin hacer el 3 | Los barrios reales quedaron pisados. Ver abajo. |

### Envíos de resultado desconocido (`INCIERTO`)

Un `ReadTimeout`, un 500 o un pod reiniciado entre el POST y el registro dejan el
intento sin saber si SIIS registró al beneficiario. La API no deduplica ni permite
dar de baja, así que **reintentar a ciegas es el peor desenlace posible**: esos
casos quedan tomados y ningún camino los vuelve a mandar. La salida es preguntarle
a ECOM:

```bash
# 1. El listado que se le manda a ECOM: «¿estas personas están en SIIS?»
#    El CSV trae dos columnas vacías, `decision` y `motivo`, para que las complete.
python manage.py conciliar_envios_siis --listar > inciertos.csv

# 2. Vuelve el archivo con `decision` en «confirmar» o «liberar». Primero el ensayo:
python manage.py conciliar_envios_siis --desde-csv inciertos.csv
python manage.py conciliar_envios_siis --desde-csv inciertos.csv --aplicar --usuario coord

# Para pocos casos, sin pasar por el archivo (también en seco por defecto):
python manage.py conciliar_envios_siis --confirmar 1234 --siis-id 55678 --aplicar --usuario coord
python manage.py conciliar_envios_siis --liberar 1234,1235 --motivo "ECOM: no llegaron" --aplicar
```

Las decisiones quedan en la traza del caso, con quién las tomó. **Nunca se libera
sin la confirmación de ECOM**: liberar un alta que sí llegó es duplicarla. Si un
pk del lote está mal, no se escribe ninguno: se valida todo antes de empezar.

### Cuando la corrida se detiene sola

`DETENIDO tras N resultados de resultado desconocido seguidos` no es lo mismo que
`DETENIDO tras N errores técnicos seguidos`. El segundo es SIIS caído y los casos
quedaron libres: se vuelve a correr y listo. El primero es SIIS contestando mal, y
cada uno de esos N casos quedó **tomado**: hay que conciliarlos antes de seguir, o
la próxima corrida los saltea y el número crece. Los topes son `--max-errores`
(10) y `--max-inciertos` (3), y son distintos a propósito: un error no cuesta
nada y un incierto cuesta una conciliación.

### Deshacer un envío (solo si SIIS ya lo borró de su lado)

```sql
-- 1. Sacar el barrio generico escrito a ciegas
UPDATE programas_formulario
SET datos_siis = JSON_REMOVE(datos_siis, '$.barrio_actual')
WHERE JSON_VALUE(datos_siis, '$.barrio_actual') = 'Sin especificar';

-- 2. Liberar los casos para reenviarlos
DELETE FROM programas_enviosiis WHERE estado = 'ENVIADO';
```

> **Solo después de que ECOM borre esos registros de la tabla intermedia de SIIS.**
> La API no deduplica y desde acá no se da de baja: sin ese paso previo, se duplican.

> **Y nunca borrar un `EnvioSIIS` suelto sin mirar antes su `clave_persona_plan`.**
> Desde el Cambio 127 esa columna es la que impide que la misma persona tenga dos
> altas vigentes en el mismo plan, aunque vengan de casos distintos. Si hay un
> grupo cruzado —dos casos del mismo DNI y plan, los dos tomados— **la clave la
> tiene uno solo**, y borrar justo a ese libera la clave: el otro caso sigue
> tomado, pero el DNI queda libre y la próxima corrida puede mandar **un alta
> más** de alguien que ya está en SIIS dos veces. Antes de borrar uno suelto:
>
> ```sql
> -- ¿Qué clave tiene el que voy a borrar, y hay otros vigentes de la misma persona y plan?
> SELECT id, formulario_id, estado, vigente, clave_persona_plan
> FROM programas_enviosiis
> WHERE vigente = 1
>   AND (documento, id_programa) = (SELECT documento, id_programa FROM programas_enviosiis WHERE id = <pk>);
> ```
>
> Si vuelve **más de una fila**, es un grupo cruzado: se borran **todas** o
> ninguna, y solo después de que ECOM las haya sacado de SIIS. La lista de los
> grupos que había al migrar está en la traza de cada caso:
> `SELECT formulario_id, valor_nuevo FROM programas_tracaformulario WHERE campo = 'envio_siis';`

Después, rehacer los pasos 6, 7 y 8.

---

## Reglas que no se saltean

1. El paso 3 va **antes** del 6.
2. El paso 5 va **antes** del 6.
3. El paso 7 (un caso) va **antes** del 8, siempre.
4. Nada se reenvía sin que SIIS lo haya borrado primero.
