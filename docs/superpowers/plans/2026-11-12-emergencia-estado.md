# Módulo Emergencia — estado del desarrollo (bitácora viva)

**Última actualización:** 2026-11-12, backend completo (PRs 0 a 11) integrado y verificado; PR 12 (documentación) en curso.

Este archivo dice qué está hecho, dónde está, qué falta y cómo seguir desde un checkout local. Se
actualiza cada vez que un PR cambia de estado. El plan completo está en
[`2026-11-12-emergencia-plan.md`](2026-11-12-emergencia-plan.md) y el análisis funcional en
`docs/internal/emergencia/`. Los dos viven en la rama `docs/emergencia-analisis`, igual que este archivo.

---

## 1. Cómo seguir desde el local

```powershell
git fetch origin
git checkout docs/emergencia-analisis      # plan, análisis y este archivo
git checkout feat/emergencia-integracion-final  # todo el backend (PRs 0 a 11) junto y verificado
```

- **Nada está mergeado a `development` y no hay ningún PR abierto en GitHub.** Todo son ramas
  `feat/emergencia-*` pusheadas.
- Las ramas van **apiladas**: para abrir los PRs contra `development` hay que hacerlo en orden
  (§2), o mergear primero la base de cada una.
- Las ramas `feat/emergencia-*` salen de `development` @ `e968b179` y **no** traen los commits de
  documentación de `docs/emergencia-analisis`.
- Tests en local (PowerShell, receta de `CLAUDE.md`):

  ```powershell
  $env:PY_VENV = "$PWD\.venv\Scripts\python.exe"; $env:DJANGO_SECRET_KEY = "test-key"
  $env:PYTEST_RUNNING = "1"; $env:DJANGO_SYNCDB_PROJECT_APPS = "True"
  & $env:PY_VENV manage.py test programas.tests.test_emergencia_base programas.tests.test_emergencia_casos `
      programas.tests.test_emergencia_mesa programas.tests.test_emergencia_vencimientos `
      programas.tests.test_emergencia_api_contrato programas.tests.test_dispositivos_reservas_derivacion `
      core.tests.test_nodo_ui_emergencia
  ```

---

## 2. Estado de cada PR

| PR | Qué es | Estado | Rama | Commit | Sale de |
|---|---|---|---|---|---|
| 0 | Piezas de UI del lote | ✅ Verificado y pusheado | `feat/emergencia-pr0-piezas` | `c8932a9d` | `development` |
| 1 | Programa, RBAC y configuración (E7) | ✅ Verificado y pusheado | `feat/emergencia-pr1-base` | `8e14fe50` | `development` |
| 2 | Modelo del caso y servicios de la mesa | ✅ Verificado y pusheado | `feat/emergencia-pr2-casos` | `ffd070b9` | PR 1 |
| 3 | Mesa: bandeja E2, ficha E3, «Nuevo caso» | ✅ Verificado y pusheado | `feat/emergencia-pr3-mesa` | `deae7666` | PR 2 + merge de PR 0 |
| 4 | Vencimientos de la mesa | ✅ Verificado y pusheado | `feat/emergencia-pr4-vencimientos` | `1dc4bd61` | PR 2 |
| 5 | API base, login y M1 (backend) | ✅ Verificado y pusheado | `feat/emergencia-pr5-api` | `92141d18` | PR 2 |
| 6 | Dispositivos: reservas de derivación, bitácora automática, señal de egreso | ✅ Verificado y pusheado | `feat/emergencia-pr6-reservas` | `a5b9e38e` | PR 2 |
| — | Integración de los PRs 0 a 6 | ✅ Suite completa corrida | `feat/emergencia-integracion-ola3` | `1afe2718` | PR 3 + merges de 6, 4 y 5 |
| 7 | Alojar: servicios de la etapa 3 y backoffice E6 | ✅ Verificado y pusheado | `feat/emergencia-pr7-alojar` | `c9ada33d` | integración ola 3 |
| 9 + 9-API | Kits: modelo, servicios, E4, E5, recepción web y API M3 | ✅ Verificado y pusheado | `feat/emergencia-pr9-kits` | `cb738b66` | integración ola 3 |
| — | Integración de los PRs 0 a 9 | ✅ Suite completa corrida (8.870 tests) | `feat/emergencia-integracion-ola4` | `630f5c5f` | PR 7 + merge de PR 9 |
| 8 | API M2 (llegada de familias) | ✅ Verificado y pusheado | `feat/emergencia-pr8-api-m2` | `cca63bf7` | integración ola 4 |
| 10 | Tablero E1 y avisos | ✅ Verificado y pusheado | `feat/emergencia-pr10-tablero` | `959aebe3` | integración ola 4 |
| 11 | Marcas de la bandeja y la ficha (etapas 3 y 4) | ✅ Verificado y pusheado | `feat/emergencia-pr11-marcas` | `839b368c` | integración ola 4 |
| — | **Integración final del backend (PRs 0 a 11)** | ✅ Suite completa: 8.986 tests | `feat/emergencia-integracion-final` | `4503041c` | PR 8 + merges de 10 y 11 |
| 12 | Documentación del módulo y entradas de `requerimientos.md` | 🔄 En desarrollo | `feat/emergencia-pr12-docs` | — | integración final |
| 13 | QA (casos por task, plan de pruebas) | ⏳ Pendiente | — | — | todos |
| 5-P | PWA: módulo Emergencia y M1 | ⛔ Bloqueado (§6) | — | — | PR 5 |
| 8-P | PWA: M2 | ⛔ Bloqueado (§6) | — | — | PR 8 |
| 9-P | PWA: M3 | ⛔ Bloqueado (§6) | — | — | PR 9-API |

«Verificado» quiere decir que, después de recibir el trabajo del subagente, se volvieron a correr sobre
el commit `manage.py check`, `makemigrations --check`, `check_migraciones.py`, los tests del módulo, ruff
y, en los PRs con UI, las auditorías de diseño.

### Orden sugerido para abrir los PRs contra `development`

1. PR 0 y PR 1 (independientes entre sí).
2. PR 2 (sobre PR 1).
3. PR 3 (necesita 0 y 2), PR 4, PR 5 y PR 6 (cada uno sobre PR 2).
4. PR 7 y PR 9 (sobre todo lo anterior).
5. PR 8, PR 10, PR 11.
6. PR 12 (documentación y `requerimientos.md`).

Antes de abrir el PR 3 conviene hacer squash de su commit «wip» (`2587db2a`) con `deae7666`; lo mismo
con el WIP del PR 4 (`a8f5590d`) y el del PR 7 (`c9ada33d`).

---

## 3. Qué trae cada PR terminado

### PR 0 — Piezas de UI
- Cuatro piezas nuevas en `templates/components/`: `_semaforo_sla.html` (badge y variante `reloj`),
  `_tarjeta_dispositivo_derivar.html`, `_contador_avance.html`, `_celda_diferencia.html`.
- Ficha de cada una en `.claude/design/componentes/` y fila en el inventario de
  `.claude/agents/chaco-design-system.md`.
- Filtro nuevo `menos` en `core/templatetags/nodo_ui.py`.
- Tests: `core/tests/test_nodo_ui_emergencia.py`.
- No cambió ninguna pieza ni pantalla existente.

### PR 1 — Programa, RBAC y configuración
- `core/rbac.py`: módulo `emergencia` (`emergencia.relevar`, `operar`, `supervisar`, acotado al programa
  EMERGENCIA), `emergencia.recibir_kit` en un módulo acotado a DISPOSITIVOS, y `emergencia.relevar` en
  `CAPACIDADES_DE_CAMPO`.
- Modelos `SLAEmergencia`, `TipoKit`, `TrazaConfiguracion`.
- Migraciones: `programas.0116_emergencia_base`, `programas.0117_programa_emergencia`,
  `users.0047_capacidades_emergencia` (le da `operar`, `supervisar` y `recibir_kit` al rol Administrador).
- Servicios: `programas/services/emergencia_programa.py`, `configuracion_emergencia.py`. Comando
  `seed_emergencia`.
- Pantalla E7 en `/emergencia/config/` y entrada en el sidebar.
- Tests: `programas/tests/test_emergencia_base.py`.

### PR 2 — Modelo del caso y servicios de la mesa
- Modelos: `GrupoFamiliar`, `IntegranteGrupo`, `CasoEmergencia`, `Derivacion` (con `clave_vigente` y
  unique simple), `ContactoCaso`, `AdjuntoCaso`, `TrazaCaso`, `NumeradorEmergencia`.
- Migración `programas.0118_emergencia_casos` (solo tablas nuevas; `uuid_cliente` en `char(36)`).
- `programas/services/emergencia.py`: `crear_caso`, `tomar_caso`, `soltar_caso`, `reasignar_caso`,
  `cambiar_prioridad`, `registrar_contacto`, `derivar_caso`, `cancelar_derivacion`,
  `cerrar_sin_alojamiento`, `siguiente_numero`. Excepciones `EstadoCambio`, `CasoTomadoPorOtro`,
  `FaltanPlazas`.
- `programas/selectors/emergencia.py`: `estado_sla`, `bandeja`, `conteo_por_solapa`,
  `dispositivos_para_derivar`, `posibles_duplicados`, `responsable_alojado`.
- Regla de acceso a las fotos del caso en `core/rutas_media.py` y `core/views/media.py`.
- Tests: `test_emergencia_casos.py` y `test_emergencia_concurrencia.py` (carreras, solo con motor real).

### PR 3 — Mesa
- `programas/views/emergencia.py`: bandeja, ficha, «Nuevo caso» y ocho acciones POST.
- `programas/selectors/emergencia_mesa.py`, formularios en `programas/forms_emergencia.py`, rutas en
  `programas/emergencia_urls.py`.
- Templates `programas/templates/programas/emergencia/casos/` (`list.html`, `detail.html`, `form.html`).
- Sidebar: «Emergencia» (operar o supervisar) y «Configuración de Emergencia» (supervisar).
- `_semaforo_sla.html` suma el parámetro opcional `texto_tiempo`.
- Tests: `test_emergencia_mesa.py`. Presupuestos: E2 en 17 consultas con 500 casos, E3 en 18.

### PR 4 — Vencimientos
- `programas/services/vencimientos_emergencia.py`: reglas `emergencia.derivacion` y
  `emergencia.caso_sin_avance`.
- En `emergencia.py`: `vencer_derivacion`, `devolver_a_bandeja_por_inactividad`, `limite_de_inactividad`.
- `core/services/vencimientos.py` y el comando `procesar_vencimientos`: flag opcional
  `ReglaVencimiento.transaccion_unica` (default `True`; las reglas de Becas no cambian).
- Tests: `test_emergencia_vencimientos.py`.

### PR 5 — API base
- Login (`ObtainCampoToken`): `modulos` puede traer `"emergencia"`; las claves del cuerpo no cambian.
- Namespace `/api/emergencia/`: raíz, `perfil/`, `personas/consultar/`, `localidades/`, `casos/` (POST
  idempotente por `uuid_cliente`), `casos/mios/`.
- `modulo_habilitado(user)` y `roles_en_app(user)` en `emergencia_programa.py`.
- Contrato para la app: `docs/internal/contrato-app-emergencia.md`.
- Tests: `test_emergencia_api_contrato.py`.

### PR 6 — Dispositivos
- `ReservaPlaza.derivacion` (FK anulable). Migración `programas.0119_reserva_plaza_derivacion`.
- `programas/services/estadias.py`: `reservar_plazas_de_derivacion`, `consumir_reserva_de_derivacion`,
  `liberar_reservas_de_derivacion`. `reserva_propia_vigente` y `ingreso._reservas_abiertas_de` excluyen
  las reservas de derivación.
- `programas/services/bitacora.py`: `anotar_novedad_automatica`.
- `programas/senales.py`: señal `estadia_egresada`, enviada dentro de `egresar_persona`.
- `ocupacion.EstadoPlaza.derivacion_id` (aditivo).
- Tests: `test_dispositivos_reservas_derivacion.py` y `test_emergencia_reservas_concurrencia.py`. No se
  editó ningún test existente de Dispositivos.

### PR 7 — Alojar (etapa 3)
- `programas/services/emergencia_alojar.py`: `buscar_por_dni`, `aceptar_derivacion`, `rechazar_derivacion`,
  `confirmar_integrante`, `completar_ficha`, `agregar_integrante`, `alojar_familia`,
  `cerrar_con_diferencia`, `cancelar_ingreso`, `ingreso_directo`, `avisar_a_la_mesa`, y el receptor
  `al_egresar_estadia` (cierra el caso cuando egresa el último integrante).
- Selectores de alojar y de llegadas del dispositivo.
- Backoffice E6 «Llegadas» bajo el dispositivo: llegadas, alojar, integrantes, ficha, cama (mapa de plazas
  en modo emergencia, sin tocar la pieza), Formulario 1 del ingreso directo. Templates en
  `programas/templates/programas/emergencia/dispositivo/`.
- E3 de la mesa muestra los integrantes. La guardia del dispositivo ve las fotos del caso.
- Sin migraciones.
- Tests: `test_emergencia_alojar.py` (113), `test_emergencia_alojar_vistas.py` (57),
  `test_emergencia_alojar_concurrencia.py` (7, solo con motor real).
- Cambió una aserción de `test_dispositivos_reservas_derivacion.py` (PR 6): afirmaba que la señal de
  egreso no tenía receptores, y el PR 7 es el que agrega el suyo.

### PR 8 — API M2 (llegada de familias)
- 12 rutas nuevas en `/api/emergencia/`: buscar por DNI, aceptar/rechazar derivación, integrantes (listar,
  agregar, detalle, confirmar, completar ficha), plazas del dispositivo para el caso, alojar, cerrar con
  diferencia, cancelar ingreso, ingreso directo y avisar a la mesa. `mis-dispositivos` suma
  `plazas_libres` y `derivaciones_pendientes`.
- Misma capa de servicios que la web (RU-2); sin alcance → 404; estado cambiado → 409 con `estado_actual`.
- Contrato completo en `docs/internal/contrato-app-emergencia.md` §13 (incluye el esquema de la ficha).
- `perfil.dispositivo` ahora es `false` para el admin de Dispositivos que no puede operar; se cambió
  una aserción existente de los tests del PR 5 por eso.
- Aceptar, rechazar, alojar y los cierres no son idempotentes por `uuid_cliente` (no hay dónde guardarlo
  sin migración): un reintento da 409 y la app recarga.
- Tests: `test_emergencia_api_m2.py` (51).

### PR 10 — Tablero E1 y avisos
- `programas/selectors/emergencia_tablero.py`, `programas/services/avisos_emergencia.py` (7 reglas de
  aviso), vista y template `emergencia/tablero.html`, entrada «Tablero de Emergencia» en el sidebar
  (solo supervisar).
- Arquetipo Detalle con hero de programa y stat cards; sin gráficos; sin la solapa «Mapa de la emergencia».
- Selectores y avisos en 10 consultas; vista completa en 16. Sin `CONVERT_TZ`.
- Cambió `scripts/design_audit.py`: el tablero entra en `HERO_PANTALLAS` y la variante «detalle +
  apilado» acepta el hero en lugar del `page_header`.
- «Ingreso parcial sin revisar» se da por revisado con un contacto posterior al alojamiento (no hay
  campo de observación de la mesa en el caso).
- Tests: `test_emergencia_tablero.py` (45).

### PR 11 — Marcas de la bandeja y la ficha
- Marcas nuevas: «Rechazado por X: motivo», «Derivación vencida · volver a derivar», «Dispositivo
  inactivo · volver a derivar», «Llegaron N sobre M declaradas», «En la puerta de X». Se van con la
  siguiente acción sobre el caso.
- Presupuestos de E2 (17) y E3 (18) sin cambios.
- Tests: `test_emergencia_marcas.py` (19).

### PR 9 y 9-API — Kits
- Modelos `EntregaKit`, `LineaEntrega`, `TrazaEntrega`. Migración `programas.0120_emergencia_kits`.
- `programas/services/kits.py`: `crear_entrega`, `marcar_en_camino`, `cancelar_entrega`,
  `recibir_entrega` (idempotente por `uuid_cliente`), `observar_recepcion`. Selectores en
  `programas/selectors/kits.py`.
- Backoffice: E4 (listado + nueva entrega), E5 (detalle con enviado / recibido / diferencia, reponer) y
  recepción dentro del dispositivo. Templates en `programas/templates/programas/emergencia/kits/`.
- API M3 en `/api/emergencia/`: `mis-dispositivos/`, entregas pendientes del dispositivo, detalle y
  `recibir/`. Contrato actualizado en `docs/internal/contrato-app-emergencia.md`.
- Tests: `test_emergencia_kits.py` (102), `test_emergencia_kits_vistas.py` (63).

---

## 4. Decisiones del PM ya tomadas

| Tema | Decisión |
|---|---|
| Ramas | Una rama por PR, sin abrir PRs hasta que se pida. |
| Formulario 2 (ficha individual) | Fijo, con versión dentro del JSON. |
| Tocar Dispositivos para las reservas de familia (PR 6) | Autorizado, como en el plan. |
| Persona que no sabe su número de DNI | No se le asigna cama; el ingreso se cierra con diferencia. |

El resto de las decisiones abiertas del README §10 sigue con los supuestos del plan (§7 del plan).

---

## 5. Desvíos respecto del plan y cosas a revisar

- **PR 6, sin índice `(derivacion, estado)`.** El plan lo pedía. No se creó porque en InnoDB haría que
  liberar una cama desde el mapa pueda chocar (deadlock) con cancelar o vencer la derivación. Queda el
  índice implícito de la FK. No se midió contra un motor real.
- **PR 4, cambio en `core/`.** El flag `transaccion_unica` no estaba en el plan. Sin él, el vencimiento
  retiene el candado de cada caso hasta terminar toda la regla.
- **PR 4, una aserción de Becas editada.** `test_las_reglas_estan_registradas_al_arrancar` ahora espera
  también las dos reglas de Emergencia.
- **PR 5, un test de inspecciones partido en dos.** La guardia con `dispositivo.admitir` ahora saca
  token (entra por Emergencia); el relevamiento edilicio sigue cerrado para ella.
- **PR 3, «Nuevo caso» en una página** con cuatro bloques, no asistente de cuatro pasos (el asistente
  guarda estado en la sesión, compartida entre pestañas).
- **PR 3, solapas de la bandeja** con chips de enlace en dos filas (son ocho).
- **PR 1, catálogo de kits en E7** como bloques de campos, no tabla editable (sería pieza nueva).
- **PR 1 y 3, snapshots de Becas regenerados** (`programas/tests/snapshots/formulario_detalle/`): el
  diff reportado son líneas en blanco por el sidebar. Conviene mirarlo en el review.
- **Plazas libres al derivar.** El número cuenta todas las plazas del dispositivo, no solo las camas.
  Falta decidir si se corrige (toca `ocupacion.py`).
- **RN-5.5 contra RN-2.8.** «Minutos sin avance» se lee al correr la regla, no queda congelado por caso.
- **Semáforo consultado dos veces** en la bandeja (una consulta de más, evitable tocando el selector).
- **Sidebar sin alcance de programa**: un rol de otro programa con la capacidad tildada vería el link y
  recibiría 403 al entrar.
- **Sin revisión visual en navegador** de ninguna pantalla nueva (E1 a E7, «Nuevo caso», kits).
- **«Plazas libres» cuenta todas las plazas, no solo camas**, en el panel Derivar y en el tablero.
- **Validación antes que alcance** en `cerrar_con_diferencia` y `rechazar_derivacion`: con un id ajeno y
  un motivo inválido dan 400 en vez de 404. No filtra datos; se puede reordenar en un PR chico.
- **PR 7 y PR 9 sin reporte final del subagente.** Los dos se cortaron por límite de uso justo al
  terminar; el código está commiteado y pasa todas las verificaciones, pero las decisiones que tomaron
  no quedaron escritas. Revisarlas en el diff antes de abrir los PRs.

---

## 6. Pendientes y bloqueos

### Bloqueado: PWA (`Chaco-mobile`)
- Falta permiso de escritura sobre el repo en la sesión de desarrollo.
- Falta confirmar la rama base: los módulos de Dispositivos de la app están en `test`, no en `main`.
- Para el PR 5-P: la consulta de personas pide `sexo` además del DNI, y responde con el formato de Becas
  (`{success, origen, data, datos_api}`), no con el de 01 §8.

### Pendiente de CI (no se puede correr sin MySQL/MariaDB)
- Carreras con dos conexiones (`@tag("mysql")`) de los PRs 2, 4, 6, 7, 8 y 9.
- Job «Migrate ida y vuelta» y `check_sqlmigrate` para las migraciones `0116` a `0120` y `users.0047`.

### Condiciones de cierre que todavía no se cumplieron
- **Entradas en `docs/internal/requerimientos.md`** (etiqueta nueva `#emergencia`): ningún PR la escribió
  todavía. Van en el PR 12, o una por PR al abrirlos.
- **`/auditoria pr <N>`** de cada PR antes de mergear.
- Casos de QA por task.

### Fallos conocidos del entorno de desarrollo en la nube
La suite completa da 30 fallos que **también da `development` sin cambios** en ese contenedor:
`core.tests.test_sql_motor_real` (12, falta `mysqlclient`), tres `…no_se_traduce_a_like_binary_en_mysql`
(ídem) y `core.tests.test_settings_entorno_y_timeouts` (15, causa sin investigar). En un entorno con
MySQL deberían pasar; verificarlo en CI.

---

## 7. Qué sigue

1. Terminar el PR 12 (documentación y entradas de `requerimientos.md`).
2. Revisar el diff de PR 7 y PR 9 (sus subagentes no dejaron reporte de decisiones).
3. Abrir los PRs contra `development` en el orden de §2 y pasarlos por `/auditoria pr <N>`.
4. Que el CI corra las carreras con motor real y la migración ida y vuelta.
5. PWA, cuando se destrabe §6.
3. PR 10 (tablero y avisos) cuando estén 7 y 9.
4. PR 12 (documentación y entradas de requerimientos).
5. PWA, cuando se destrabe §6.

---

## 8. Historial

| Fecha | Qué pasó |
|---|---|
| 2026-11-12 | Plan escrito y pusheado (`bb4a64b3`). |
| 2026-11-12 | Ola 1: PR 0 y PR 1. |
| 2026-11-12 | Ola 2: PR 2. |
| 2026-11-12 | Ola 3: PR 3, 4, 5 y 6. Integración de 0 a 6 con la suite completa. |
| 2026-11-12 | Ola 5 (Opus): PR 8, PR 10 y PR 11. Integración final del backend con 8.986 tests. PR 12 lanzado. |
| 2026-11-12 | Ola 4: PR 7 y PR 9. Los subagentes se cortaron por límite de uso (Fable y después Opus); el orquestador verificó y pusheó lo commiteado. Integración de 0 a 9 con la suite completa. |
