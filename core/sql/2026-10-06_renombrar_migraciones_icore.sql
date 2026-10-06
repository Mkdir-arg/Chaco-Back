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

-- Verificar que hayan sido seis y recién entonces confirmar.
SELECT app, name, applied FROM django_migrations
 WHERE app='programas' AND name BETWEEN '0057' AND '0066' ORDER BY name;

COMMIT;

-- DESPUÉS. `python manage.py verificar_esquema_migraciones` tiene que terminar en
-- «Esquema coherente» y `showmigrations programas` mostrar 0060-0065 con [X] y las tres
-- de índices (0057-0059) con [ ]: esas sí se aplican en el deploy, y son ALTER de índice
-- sobre `programas_formulario`.
