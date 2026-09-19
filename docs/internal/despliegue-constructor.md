# Despliegue de la versión con constructor de formularios

Manual operativo de la puesta en marcha del **Cambio 58 (constructor de formularios)** y
lo que viaja con él. Se escribió durante el despliegue a testing de ECOM del 18/09/2026 y
recoge los problemas reales que aparecieron, no una secuencia teórica.

**Para quién es:** quien opera el espejo al GitLab de ECOM y quien tiene acceso a la base y
a Argo CD. Cada paso dice quién lo puede hacer.

> **Estado al 18/09/2026.** Testing (`datanach.ecomdev.ar`) tiene la base migrada hasta la
> `0066` pero los pods todavía sirven la imagen anterior: falta un SYNC en Argo. Producción
> (`datanach.chaco.gob.ar`) sigue **sin** constructor.

---

## 1. Qué entra

| Cambio | Qué es | Migraciones |
|---|---|---|
| 58 | Constructor de formularios por convocatoria | 0060 a 0064 |
| 74 | Padrón con herencia convocatoria → relevamientos | 0065 |
| 73 | Alta de beneficiarios aprobados en SIIS | 0066 |
| 76 | Columna Sexo en el export de Ciudadanos | — |

Son 80 archivos y siete migraciones. Todas **aditivas**: ninguna borra datos. La `0065`
reemplaza una restricción de unicidad del padrón y la `0063` siembra el catálogo protegido.

### Efectos visibles para el ciudadano

El link público **no cambia de dirección**. El token vive en la base, se genera una sola vez
al crear el relevamiento y ninguna migración lo toca. Lo que cambia es el contenido del
formulario: aparece agrupado con títulos, y los bloques fijos de identidad, contacto y
apoderado pasan a ser ítems del diseño.

Dos diferencias de comportamiento a decidir **antes** de ir a producción:

- El **correo electrónico** queda opcional, porque así lo siembra la `0063`. Hoy en
  producción es obligatorio. Si se quiere mantener obligatorio, se cambia el flag en la
  siembra antes del release o se marca desde el catálogo en el backoffice.
- Quien esté a mitad del paso 2 en el momento del despliegue recibe el aviso de que el
  formulario cambió y lo vuelve a completar. No pierde el paso 1.

---

## 2. Antes de empezar

### 2.1 Dejar un resguardo

Antes de mover una rama de ECOM, etiquetar en GitHub el commit que está por quedar atrás:

```bash
git tag -a respaldo/ecom-<rama>-<motivo>-<fecha> <sha> -m "<qué contiene>"
git push origin refs/tags/<nombre-del-tag>
```

El tag **no** se sube a ECOM, para no disparar su CI. Ejemplo real:
`respaldo/ecom-test-constructor-2026-09-18`.

### 2.2 Verificar que no se pisa trabajo de ECOM

ECOM edita `.gitlab-ci.yml` en `test` y su automatización commitea ahí. `git fetch ecom test`
corta con HTTP 500, así que se usa un clon superficial:

```bash
git clone --depth=5 --branch test --quiet <url-ecom> <tmp>
git -C <tmp> log --format='%h %an | %s'
```

Si hay commits que no son nuestros, **parar**: hay que traerlos a `development` primero.
Comparar además el blob del CI en los dos lados; tienen que ser idénticos.

---

## 3. Espejar el código

Se usa `/pushGitLabecom`. Va primero a `test` y, recién después de verificar, a `main`.
**Pushear `main` es desplegar en producción**, sin aprobación intermedia.

Las ramas suelen estar divergidas porque producción recibe hotfixes fuera del release. En
ese caso **no se fuerza**: se crea un commit de merge cuyo árbol es idéntico al de nuestro
`main` y que lleva la punta de ellos como segundo padre.

```bash
git -C <tmp> fetch <ruta-del-repo> main
TREE=$(git -C <tmp> rev-parse FETCH_HEAD^{tree})
MERGE=$(git -C <tmp> commit-tree $TREE -p FETCH_HEAD -p HEAD -m "merge: alinear test con el release <sha>")
git -C <tmp> push origin ${MERGE}:refs/heads/test
```

Antes de pushear, confirmar que el árbol del commit nuevo es igual al del release. Después,
que `git ls-remote ecom` devuelve el commit esperado.

---

## 4. El despliegue y su trampa

El push solo deja el código. El pipeline de ECOM construye la imagen, `argocd-image-updater`
commitea el digest y **ArgoCD** despliega. Tarda entre cinco y siete minutos.

Antes del Deployment corre el hook `web-bootstrap-migration`. **Si ese Job falla, Argo nunca
actualiza los pods** y la aplicación sigue sirviendo la imagen anterior. La app figura
*Healthy* porque lo viejo funciona, no porque el cambio esté arriba.

### 4.1 Tablas huérfanas tras restaurar un dump de producción

Este es el problema que apareció el 18/09 y va a repetirse cada vez que se restaure
producción sobre un ambiente que tuvo el constructor.

**Síntoma.** El Job falla en bucle:

```
Applying programas.0060_catalogo_grupos_origen_canal...
django.db.utils.OperationalError: (1050, "Table 'programas_gruporequisito' already exists")
```

**Causa.** Un dump de producción solo contiene las tablas que existen en producción. Al
restaurarlo, reemplaza `django_migrations` —que vuelve a la `0059`— pero **no borra** las
cuatro tablas que solo existen en la versión con constructor. Django cree que la `0060`
nunca se aplicó y choca con una tabla que ya está.

| Tabla huérfana | La crea |
|---|---|
| `programas_gruporequisito` | 0060 |
| `programas_disenoformulario` | 0061 |
| `programas_itemdiseno` | 0061 |
| `programas_enviosiis` | 0066 |

**Por qué `--fake` es la salida equivocada.** La `0060` hace nueve operaciones: primero crea
la tabla y después agrega seis columnas y modifica dos. Como falla en la primera, las otras
ocho no corren. Marcarla como aplicada deja la tabla de preguntas generales sin `grupo_id`,
`origen`, `vinculo`, `protegido` ni `canal`, y la aplicación falla en cada consulta al
catálogo. Además saltearía la siembra de la `0063`. La base queda en estado **mixto**: esas
cuatro tablas sobreviven, pero las columnas que las migraciones agregan a tablas que sí
están en el dump desaparecieron con el restore.

**Arreglo.** Borrar las cuatro huérfanas y dejar que las migraciones corran completas. Su
contenido es del ambiente anterior al restore, o sea datos ya descartados a propósito.

```sql
-- Diagnóstico: tienen que aparecer las 4
SELECT table_name, table_rows FROM information_schema.tables
WHERE table_schema = DATABASE()
  AND table_name IN ('programas_gruporequisito','programas_disenoformulario',
                     'programas_itemdiseno','programas_enviosiis');

-- Arreglo. Las claves foráneas se apagan porque estas tablas quedaron
-- apuntando a tablas que el restore recreó.
SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS `programas_itemdiseno`;
DROP TABLE IF EXISTS `programas_disenoformulario`;
DROP TABLE IF EXISTS `programas_gruporequisito`;
DROP TABLE IF EXISTS `programas_enviosiis`;
SET FOREIGN_KEY_CHECKS = 1;
```

No hace falta `kubectl` ni terminal en el contenedor: alcanza con un cliente SQL apuntando a
la base del ambiente.

### 4.2 Migraciones con nombre viejo (solo DEV)

El servidor de DEV (icore-srv) quedó desplegado desde la rama del constructor, cuando las
migraciones se llamaban `0057` a `0062`. Al pasar a `main` hay que **renombrar esas filas**
en `django_migrations` a `0060` a `0065`, o Django intenta aplicarlas de nuevo. No confundir
con el caso anterior: ahí las filas faltan, acá están con otro nombre.

---

## 5. Verificación

### 5.1 La base

```sql
SELECT 'ultima migracion' AS control,
       (SELECT name FROM django_migrations WHERE app='programas' ORDER BY id DESC LIMIT 1) AS valor,
       '0066_siis_envio_beneficiarios' AS esperado
UNION ALL SELECT 'grupos del catalogo',
       (SELECT COUNT(*) FROM programas_gruporequisito), '4'
UNION ALL SELECT 'campos vinculados',
       (SELECT COUNT(*) FROM programas_preguntaglobal WHERE origen <> 'pregunta'), '12'
UNION ALL SELECT 'columnas nuevas en preguntaglobal',
       (SELECT COUNT(*) FROM information_schema.columns
         WHERE table_schema=DATABASE() AND table_name='programas_preguntaglobal'
           AND column_name IN ('grupo_id','origen','vinculo','protegido','canal')), '5';
```

Los cuatro grupos son Datos personales, Contacto, Apoderado y Cuestionario social. Los doce
campos vinculados son siete al legajo de la persona y cinco del apoderado.

### 5.2 Qué imagen está corriendo, sin entrar a Argo

Django nombra los estáticos con el hash de su contenido, así que el HTML de una página
pública dice qué versión sirve. Es la verificación más confiable desde afuera: probar rutas
del backoffice no sirve, porque el ambiente responde 404 a cualquier URL sin sesión.

```bash
curl -s https://<ambiente>/portal/ | grep -o 'tailwind\.[a-f0-9]*\.css'
```

Para calcular el hash esperado de cada versión:

```bash
git show <sha-de-la-version>:static/custom/css/tailwind.css | md5sum | cut -c1-12
```

Valores de esta puesta en marcha:

| Versión | tailwind.css | nodo-forms.css |
|---|---|---|
| Producción (sin constructor) | `d27ef8238eb9` | `1e38cb7dc49f` |
| Release con constructor | `6cfbddc3fe70` | `4dd32ad76c85` |

Conviene incluir en la comparación algún archivo que **no** haya cambiado entre las dos
versiones: si ese coincide, confirma que el método mide bien.

### 5.3 Funcional

Entrar a una convocatoria en el backoffice: tiene que aparecer la solapa **Formulario** con
el constructor. Abrir el link público de un relevamiento: el formulario se ve agrupado, sin
campos duplicados.

---

## 6. Permisos de Argo CD

El SYNC lo dispara ArgoCD. A la fecha, el usuario `matiasfarina` **no** tiene el permiso
`applications, sync` sobre `default/datanach`: el botón devuelve *permission denied*. Además
la terminal de los pods está deshabilitada, solo hay SUMMARY, EVENTS y LOGS.

Consecuencia operativa: si el sync queda fallado, hace falta alguien de ECOM con ese
permiso. Argo agota cinco reintentos y limpia el Job solo, así que después no queda nada que
borrar, pero tampoco vuelve a intentar por su cuenta.

La alternativa sin depender de ellos es forzar una revisión nueva: un commit trivial a
`ecom/test` genera una imagen nueva, el image-updater la commitea y el auto-sync se dispara.
Cuesta un build y entre cinco y siete minutos más.

---

## 7. Volver atrás

**El código es fácil.** Se espeja de nuevo el árbol de la versión anterior, con commit de
alineación. El tag de respaldo del paso 2.1 sirve para eso.

**La base no vuelve sola, y esto es lo importante.** Las migraciones no se revierten al
revertir el código, y la `0063` siembra doce preguntas generales con `activo = True`. El
código sin constructor toma **todas** las preguntas generales activas sin filtrar por
`origen`, así que esas doce aparecen **duplicadas** sobre los bloques fijos en el link
público y en la app de campo.

O sea que la combinación *código viejo + base nueva* deja el formulario roto. Para volver de
verdad hay que desactivar esas doce filas o restaurar la base.

```sql
-- Comprobar el estado antes de revertir el código
SELECT COUNT(*) FROM programas_preguntaglobal
 WHERE origen <> 'pregunta' AND activo = 1;   -- 12 ⇒ el código viejo las va a mostrar
```

---

## 8. Carga de la tabla de RENAPER

Independiente del despliegue: la consulta a RENAPER de un lote de DNI se guarda en una tabla
propia, `ciudadanos_renaper`, que no la crea ninguna migración.

**Origen.** `ciudadanos_renaper.csv`, 10.321 filas, UTF-8 con fin de línea CRLF. De esas,
10.220 trajeron datos y 101 no: 94 sin coincidencia, 5 personas fallecidas y 2 con el sexo
de origen ilegible.

**Por qué falla el asistente gráfico.** Dos motivos, y aparecen en ese orden:

1. La columna `_ok` trae el texto `True` / `False`, que es como Python escribe un booleano.
   El importador deduce que es numérica y falla con
   `Can't parse numeric value [True] ... For input string: "True"`.
2. Las celdas vacías de un CSV son cadena vacía, no nulo, y revientan contra las columnas
   numéricas y de fecha. Afecta a `fecha_nacimiento` (101), `sexo` (101), `codigo_postal`
   (275), `altura` (6192) y `_http_status` (2).

**Cómo se carga.** Hay dos archivos generados, equivalentes:

- `ciudadanos_renaper.sql` — `CREATE TABLE` más 21 sentencias `INSERT` de 500 filas, con
  `True` convertido a 1, `False` a 0 y cada vacío a `NULL`. No depende de permisos
  especiales. Es la vía recomendada.
- `ciudadanos_renaper_load.sql` — el mismo `CREATE TABLE` más un `LOAD DATA LOCAL INFILE`
  que lee el CSV original y convierte al vuelo. Sirve para repetir la carga con lotes
  nuevos; necesita `local_infile` habilitado en cliente y servidor.

```bash
mariadb -h<host> -u<usuario> -p <base> < ciudadanos_renaper.sql
```

**Se ejecuta como script, no como consulta.** El archivo tiene 24 sentencias y MariaDB
acepta una por vez; mandarlo entero como una sola consulta da
`You have an error in your SQL syntax ... near 'SET @@session.sql_mode'`. En DBeaver es
`Alt+X`, no `Ctrl+Enter`. Con 2,8 MB conviene la línea de comandos.

**Decisiones de la tabla.** `dni_consultado` es la clave primaria: es único en las 10.321
filas. `dni` y `dni_consultado` quedan como `VARCHAR(20)`, igual que la columna DNI de
Ciudadanos, para que un `JOIN` use el índice en vez de forzar una conversión. Hay 101 filas
donde el DNI que devolvió RENAPER difiere del consultado, por eso están separados. Se tipan
solo los campos inequívocos: `fecha_nacimiento` como `DATE`, `_ok` como booleano, `sexo` y
`_http_status` como enteros. El resto queda como texto para no perder ceros a la izquierda,
que aparecen en `piso_vivienda` y `departamento_vivienda`.

**Control.**

```sql
SELECT COUNT(*) AS filas, SUM(`_ok`) AS con_datos, SUM(`_ok` = 0) AS sin_datos
FROM `ciudadanos_renaper`;
-- esperado: 10321 | 10220 | 101
```

---

## 9. Checklist

- [ ] Tag de resguardo creado y subido a GitHub
- [ ] Clon superficial revisado: sin commits de ECOM, `.gitlab-ci.yml` idéntico
- [ ] Decidido si el correo va obligatorio u opcional
- [ ] Espejo a `test` con commit de alineación, árbol verificado
- [ ] Job de migraciones en verde, sin tablas huérfanas
- [ ] Los cuatro controles de la base dan lo esperado
- [ ] El hash del estático confirma que los pods tomaron la imagen nueva
- [ ] Solapa Formulario visible y link público sin campos duplicados
- [ ] Tabla `ciudadanos_renaper` cargada con 10.321 filas
- [ ] Recién entonces, evaluar el espejo a `main` (producción)


---

## 10. Después del despliegue: completar los casos y validarlos

Con el constructor arriba, los casos anteriores siguen sin foto y sin los campos nuevos. Dos comandos lo
resuelven (Cambio 79). Los dos corren en seco por defecto.

```bash
mariadb -h<host> -u<usuario> -p <base> < scripts/DatosPersonas.sql     # la tabla de RENAPER
python manage.py completar_casos_renaper                              # ensayo: leer los números
python manage.py completar_casos_renaper --aplicar --pisar-existentes # lotes de 50, ~5 min contra ECOM
python manage.py validar_casos_siis                                   # cuántos casos faltan validar
python manage.py validar_casos_siis --aplicar --pausa 1               # dentro del pod: ahí están las credenciales
```

- Antes del cruce, revisar que el selector **Provincia Nacimiento** tenga las 24 jurisdicciones.
- Antes de aprobar casos, marcar en «Requisitos por segmento» qué requisito alimenta cada destino de SIIS
  (Provincia, Localidad, Barrio, Calle y altura, Estado Civil, Provincia Nacimiento, Localidad de nacimiento).
  Sin eso el alta sale incompleta y el coordinador lo carga a mano por caso (Cambio 80).
- Ambos son reanudables e idempotentes: una segunda corrida no vuelve a escribir lo ya hecho.
- `validar_casos_siis` se frena solo tras 10 errores técnicos seguidos; eso es SIIS caído o credenciales
  inválidas. Los `ERROR` se retoman con `--reintentar-errores`.
- Control: `SELECT SUM(definicion IS NOT NULL) FROM programas_formulario;` tiene que dar el total de casos.
