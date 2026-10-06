# Alta masiva en SIIS — procedimiento

**Universo:** 7.506 casos · 7.496 candidatos (los que figuran en `aprobados_materias`)
**Duración total:** ~1 h 30 min

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
