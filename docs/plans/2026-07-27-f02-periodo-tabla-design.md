# F-02: período mensual y tabla operativa

## Objetivo

Hacer más clara y cómoda la carga mensual F-02 sin alterar su contrato de datos,
permisos ni validaciones.

## Diseño aprobado

- Reemplazar los campos numéricos separados por un selector mensual nativo con
  etiqueta visible. La vista sigue recibiendo `anio` y `mes` para conservar URLs,
  enlaces y reglas existentes.
- Presentar la grilla dentro de un panel de alto fijo adaptable: encabezado fijo,
  scroll vertical interno y scroll horizontal solo cuando la pantalla lo requiera.
- Mantener el guardado visible en un pie fijo del panel.
- Uniformar anchos, alineación y espaciado de raciones, total y observaciones,
  preservando etiquetas accesibles y el cálculo de total derivado.

## Fuera de alcance

- No cambian modelos, rutas, permisos, raciones, cálculo de totales ni el formato
  de persistencia de la prestación.
- No se agrega una dependencia de calendario ni se reemplazan los controles nativos
  del navegador.

## Validación

- Compilación de templates y auditoría de diseño sin errores.
- Prueba de vista para mantener la URL anual/mensual y el total derivado.
- Verificación local con el entorno sintético `MER-ACEPT-181` en julio de 2026.
