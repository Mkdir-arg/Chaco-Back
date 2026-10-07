# Fixtures de contrato de los servicios externos (RED-41)

Respuestas **sintéticas** de RENAPER, Base de Personas («Gran Base») y SIIS, una
por servicio y rama, escritas a mano con la estructura documentada y valores
inventados.

- **No son fixtures de Django.** No se cargan con `loaddata`: son el cuerpo JSON
  tal cual lo devuelve el proveedor, y los consume
  `programas/tests/test_contratos_externos.py` para hacerle pasar al parser real
  una respuesta con la forma real (domicilio anidado incluido), en vez del
  diccionario de tres claves que inventaba cada test.
- **No hay datos de personas.** DNI `11111111`/`22222222`, nombres «Sintetica
  Prueba». **Decisión D-RED-04 (default aplicado): sintético**, porque icore
  tiene datos reales y corre con `ENVIRONMENT=prd`. Grabar una respuesta real
  —aun anonimizada— necesita aprobación explícita del PM, `RENAPER_TEST_MODE=1`
  contra el DNI de prueba y revisión antes de versionar.
- **Se comparten.** Un solo archivo por rama para todos los tests: hasta la
  auditoría los dos únicos lugares con una respuesta realista **discrepaban** en
  el formato de la misma clave (`fechaNacimiento` como `08/05/1992` en uno y
  `1990-01-02` en el otro), así que los tests se contradecían entre sí.

| Archivo | Qué congela |
|---|---|
| `renaper_ok.json` | alta exitosa, con el `data` completo del proveedor |
| `renaper_fallecido.json` | `mensaf: "FALLECIDO"`, la rama que corta el alta |
| `personas_ok.json` | respuesta con `data` y **domicilio anidado** (SIIS-10) |
| `personas_no_encontrada.json` | `codigo: 12`, el «no encontrado» del proveedor |
| `siis_alta_ok.json` | 201 de la tabla intermedia, con `ids_generados` |
| `siis_rechazado.json` | 400 con `error`, `mensaje` y `detalles` por campo |

El día que ECOM entregue el contrato definitivo (task #243) estos archivos son
lo que hay que corregir: `test_toda_clave_leida_existe_en_el_fixture` se pone
rojo si el parser empieza a leer una clave que el fixture no tiene.
