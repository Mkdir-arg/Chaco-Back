-- Tabla `aprobados_materias` (Cambio 90): los DNI que SI van a SIIS.
--
-- A SIIS solo se informan los casos cuyo DNI figure aca. Si la tabla no existe,
-- el proceso masivo se niega a correr: la tabla decide quien NO va, y sin ella
-- mandar a todos seria justo el error que evita.
--
-- Como cargarla desde la planilla:
--   1. Exportar la columna de DNI a texto, un DNI por linea.
--   2. Reemplazar los DNI de ejemplo de abajo por los reales, uno por fila del INSERT.
--   3. Correr este archivo contra la base:
--        mariadb -h <host> -u <usuario> -p <base> < scripts/aprobados_materias_plantilla.sql
--
-- Formato del DNI: da lo mismo con puntos, sin puntos, con o sin ceros a la
-- izquierda. El sistema normaliza los dos lados antes de cruzar.
--
-- Para volver a cargarla entera, este archivo la borra y la crea de nuevo.

SET NAMES utf8mb4;

DROP TABLE IF EXISTS `aprobados_materias`;
CREATE TABLE `aprobados_materias` (
  `dni` VARCHAR(20) NOT NULL,
  PRIMARY KEY (`dni`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Un DNI por fila. Los de abajo son de EJEMPLO: reemplazarlos.
INSERT INTO `aprobados_materias` (`dni`) VALUES
('20301234'),
('7654321'),
('33444555');

-- Verificacion: cuantos DNI quedaron cargados.
SELECT COUNT(*) AS dni_habilitados FROM `aprobados_materias`;
