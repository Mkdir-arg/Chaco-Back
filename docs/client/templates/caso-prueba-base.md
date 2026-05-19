# :material-test-tube: Caso de Prueba Base

!!! abstract "Plantilla"
    Caso maestro reutilizable. Define **qué se valida** y **cómo**; cada ejecución concreta se documenta como una **instancia de prueba** (`EX-…`) que referencia a este caso base (`CB-…`).

---

## :material-information-outline: Metadatos

| Campo | Valor |
|---|---|
| :material-folder-outline: **Proyecto** | Chaco — Digitalización de procesos provinciales |
| :material-tag-outline: **Código del caso** | `CB-LOGIN` / `CB-REGISTRO` / `CB-DERIVACION` |
| :material-bookmark-outline: **Caso base** | *Nombre del caso, por ejemplo: Login* |
| :material-package-variant: **Módulo** | `legajos` / `conversaciones` / `portal` / ... |
| :material-source-commit: **Versión inicial** | `YYYY-MM-DD` o commit |
| :material-account-outline: **Responsable** | *Nombre del analista o tester* |

---

## :material-bullseye-arrow: Objetivo

!!! quote ""
    *Qué valida este caso base y qué comportamiento debe mantenerse estable en el tiempo.*

---

## :material-format-letter-case: Convención de nombres

=== ":material-bookmark: Casos base"

    Prefijo **`CB-`** seguido de un nombre corto en mayúsculas, sin espacios ni acentos.

    | Ejemplo | Descripción |
    |---|---|
    | `CB-LOGIN` | Acceso de usuario al sistema |
    | `CB-REGISTRO` | Registro de un ciudadano |
    | `CB-DERIVACION` | Derivación a un programa |

=== ":material-clipboard-play-outline: Instancias de prueba"

    Prefijo **`EX-`** seguido del caso base y la fecha de ejecución.

    | Ejemplo | Descripción |
    |---|---|
    | `EX-LOGIN-2026-05-15` | Ejecución del CB-LOGIN el 15/05/2026 |
    | `EX-REGISTRO-2026-05-22` | Ejecución del CB-REGISTRO el 22/05/2026 |

---

## :material-checkbox-multiple-marked-outline: Precondiciones

- [ ] *Usuario existente / permisos / datos previos*
- [ ] *Entorno disponible*
- [ ] *Integraciones o servicios requeridos*

---

## :material-database-arrow-down-outline: Datos de entrada

| Dato | Valor esperado |
|---|---|
| *Campo* | *Valor* |
| *Campo* | *Valor* |

---

## :material-format-list-numbered: Pasos del caso base

1. *Paso 1*
2. *Paso 2*
3. *Paso 3*
4. *Agregar los necesarios*

---

## :material-check-circle-outline: Resultado esperado

!!! success ""
    *Qué debe ocurrir al completar el flujo correctamente.*

---

## :material-check-decagram-outline: Criterios de aceptación asociados

- [ ] *Criterio 1*
- [ ] *Criterio 2*
- [ ] *Criterio 3*

---

## :material-history: Historial de ejecuciones

| Fecha | Entorno | Versión / Commit | Resultado | Instancia |
|---|---|---|:-:|---|
| `YYYY-MM-DD` | local / staging / prod | *hash* | OK / Fallo / Pendiente | *link o referencia* |

---

## :material-note-text-outline: Notas

!!! note ""
    *Observaciones generales del caso base, supuestos o dependencias.*
