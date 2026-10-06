-- Renumeración de las migraciones del constructor en icore-srv (OPS-01, Cambio 153).
--
-- QUÉ PASÓ. icore-srv quedó desplegado desde `feature/constructor-formularios` (a9fc4ee),
-- donde las seis migraciones del constructor se llamaban 0057 a 0062. Al mergearse a
-- `development` se renumeraron a 0060-0065, porque entre medio habían entrado tres
-- migraciones de índices (0057-0059). Para Django son migraciones **distintas**: las de
-- `development` figuran como no aplicadas, así que el próximo deploy las va a correr y
-- va a morir con «1050 Table already exists» dejando el esquema a medias (en MySQL y
-- MariaDB el DDL no es transaccional).
--
-- `manage.py verificar_esquema_migraciones` detecta exactamente esto y aborta el
-- arranque antes del `migrate`. Este script es la reparación.
--
-- Vive en `core/sql/` y no en `scripts/`, que está ignorado entero por RED-01 (los
-- volcados del organismo): acá no hay un solo dato personal, son seis UPDATE de
-- metadata, y desde `core/sql/` viaja en el release, que es donde icore lo necesita.
--
-- CUÁNDO CORRERLO. Una sola vez, en icore-srv, **antes** del próximo deploy que traiga
-- `development`/`main`. No corre solo: lo ejecuta una persona. Nunca en ECOM (testing ni
-- producción), que nunca tuvo esa rama. Consultar antes con P-13.
--
-- ANTES. Dump completo (paso D.0 del runbook, docs/internal/processes.md) y la foto:
--
--   SELECT id, app, name, applied FROM django_migrations
--    WHERE app='programas' AND name BETWEEN '0057' AND '0066' ORDER BY id;
--
-- Las seis filas tienen que ser exactamente las de abajo, con `applied` de septiembre de
-- 2026. Si aparece alguna de las tres de índices (0057_formulario_indice_relevamiento_
-- creado, 0058_formulario_indices_bandejas, 0059_formulario_renaper_idx_con_relevamiento),
-- la base ya está renumerada: no hay nada que hacer.
--
-- NO es un sustituto de `--fake`, que está prohibido: acá no se marca nada como aplicado,
-- se corrige el nombre con el que se registró lo que SÍ se aplicó.
--
-- CÓMO SE CORRE. **Pegado en una sesión interactiva**, no con `mariadb < archivo`:
--
--   docker compose -f docker-compose.prod.yml exec mysql \
--     sh -c 'mariadb -uroot -p"$MYSQL_ROOT_PASSWORD" "$DATABASE_NAME"'
--
-- Se pegan las seis UPDATE, se mira el SELECT de verificación del final y **recién
-- entonces se escribe `COMMIT;` a mano**. Por eso el archivo **no trae `COMMIT`**: con
-- `mariadb < archivo` el cliente ejecuta todo de corrido, así que un COMMIT escrito acá
-- confirmaría aunque el SELECT mostrara otra cosa —el «verificar y recién entonces
-- confirmar» sería mentira—. Sin COMMIT, redirigir el archivo no aplica nada: la
-- transacción se deshace al cerrar la conexión. Es el comportamiento buscado.

START TRANSACTION;

UPDATE django_migrations SET name='0060_catalogo_grupos_origen_canal'
 WHERE app='programas' AND name='0057_catalogo_grupos_origen_canal';

UPDATE django_migrations SET name='0061_diseno_formulario'
 WHERE app='programas' AND name='0058_diseno_formulario';

UPDATE django_migrations SET name='0062_formulario_respuestas_definicion'
 WHERE app='programas' AND name='0059_formulario_respuestas_definicion';

UPDATE django_migrations SET name='0063_sembrar_catalogo_protegido'
 WHERE app='programas' AND name='0060_sembrar_catalogo_protegido';

UPDATE django_migrations SET name='0064_orden_validacion_sis'
 WHERE app='programas' AND name='0061_orden_validacion_sis';

UPDATE django_migrations SET name='0065_padron_relevamiento_herencia'
 WHERE app='programas' AND name='0062_padron_relevamiento_herencia';

-- Verificación antes de confirmar. Tienen que aparecer EXACTAMENTE estas seis:
--   0060_catalogo_grupos_origen_canal        0063_sembrar_catalogo_protegido
--   0061_diseno_formulario                   0064_orden_validacion_sis
--   0062_formulario_respuestas_definicion    0065_padron_relevamiento_herencia
-- y `renombradas` tiene que decir 6.
SELECT COUNT(*) AS renombradas FROM django_migrations
 WHERE app='programas' AND name IN (
   '0060_catalogo_grupos_origen_canal', '0061_diseno_formulario',
   '0062_formulario_respuestas_definicion', '0063_sembrar_catalogo_protegido',
   '0064_orden_validacion_sis', '0065_padron_relevamiento_herencia');

SELECT app, name, applied FROM django_migrations
 WHERE app='programas' AND name BETWEEN '0057' AND '0066' ORDER BY name;

-- Si el resultado es el esperado, escribir a mano:
--
--   COMMIT;
--
-- Si no lo es:
--
--   ROLLBACK;

-- DESPUÉS. `python manage.py verificar_esquema_migraciones` tiene que terminar en
-- «Esquema coherente» y `showmigrations programas` mostrar 0060-0065 con [X] y las tres
-- de índices (0057-0059) con [ ]: esas sí se aplican en el deploy, y son ALTER de índice
-- sobre `programas_formulario`.
