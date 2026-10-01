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
mariadb -h <host> -u <usuario> -p --skip-ssl <base> < scripts/Aprobados.sql
mariadb -h <host> -u <usuario> -p --skip-ssl <base> < scripts/Localidades.sql
```

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

## 6 · Corregir los datos

```bash
python manage.py corregir_datos_siis \
    --fecha-nacimiento-renaper --heredar-nacimiento \
    --barrio-generico "Sin especificar" --fecha-apoderado 1990-01-01 \
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
| `Lost connection to server during query` | La base está saturada (restore en curso). Esperar y reintentar. |
| `DETENIDO tras 10 errores técnicos seguidos` | SIIS no responde. Esperar y volver a correr: lo hecho queda. |
| Ctrl+C a mitad | Seguro. Los comandos son reentrantes y no duplican. |
| Se corrió el paso 6 sin hacer el 3 | Los barrios reales quedaron pisados. Ver abajo. |

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

Después, rehacer los pasos 6, 7 y 8.

---

## Reglas que no se saltean

1. El paso 3 va **antes** del 6.
2. El paso 5 va **antes** del 6.
3. El paso 7 (un caso) va **antes** del 8, siempre.
4. Nada se reenvía sin que SIIS lo haya borrado primero.
