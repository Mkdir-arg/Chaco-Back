# Módulo Emergencia — estado del desarrollo (bitácora viva)

**Última actualización:** 2026-11-13 22:40. **11 de 13 PRs mergeados a `development`** (PR 0 a PR 10, más el PR 9 antes que el PR 8). #1136 (PR 11) está aprobado y espera el CI. Falta #1137 (PR 12, documentación).

Este archivo dice qué está hecho, dónde está, qué falta y cómo seguir desde un checkout local. Se
actualiza cada vez que un PR cambia de estado. El plan completo está en
[`2026-11-12-emergencia-plan.md`](2026-11-12-emergencia-plan.md) y el análisis funcional en
`docs/internal/emergencia/`. Los dos viven en la rama `docs/emergencia-analisis`, igual que este archivo.

---

## 0. PRs abiertos (lo vigente)

El desarrollo se rebasó sobre `development` @ `6770545b` en una **cadena lineal de ramas `-v2`**. Las
migraciones del módulo quedaron renumeradas a `programas.0117`–`0121` (`users.0047` no cambió) y los
Cambios de `requerimientos.md` a **462–474**. Las ramas sin `-v2` y las `integracion-*` quedan solo como
referencia histórica.

Se mergean **en este orden**. Cada PR apunta a la rama del anterior; al mergear uno, el siguiente pasa a
apuntar a `development` y recién ahí le corre el CI.

| Orden | PR | Qué | Rama | Cambio |
|---|---|---|---|---|
| 1 | [#1125](https://github.com/Mkdir-arg/Chaco-Back/pull/1125) | PR 0 · piezas de UI | `feat/emergencia-pr0-piezas-v2` | 462 |
| 2 | [#1126](https://github.com/Mkdir-arg/Chaco-Back/pull/1126) | PR 1 · programa, RBAC, E7 | `feat/emergencia-pr1-base-v2` | 463 |
| 3 | [#1127](https://github.com/Mkdir-arg/Chaco-Back/pull/1127) | PR 2 · caso y servicios de la mesa | `feat/emergencia-pr2-casos-v2` | 464 |
| 4 | [#1128](https://github.com/Mkdir-arg/Chaco-Back/pull/1128) | PR 3 · mesa E2/E3 | `feat/emergencia-pr3-mesa-v2` | 465 |
| 5 | [#1129](https://github.com/Mkdir-arg/Chaco-Back/pull/1129) | PR 4 · vencimientos | `feat/emergencia-pr4-vencimientos-v2` | 466 |
| 6 | [#1130](https://github.com/Mkdir-arg/Chaco-Back/pull/1130) | PR 5 · API base y login | `feat/emergencia-pr5-api-v2` | 467 |
| 7 | [#1131](https://github.com/Mkdir-arg/Chaco-Back/pull/1131) | PR 6 · reservas en Dispositivos (modo juez) | `feat/emergencia-pr6-reservas-v2` | 468 |
| 8 | [#1132](https://github.com/Mkdir-arg/Chaco-Back/pull/1132) | PR 7 · alojar y E6 | `feat/emergencia-pr7-alojar-v2` | 469 |
| 9 | [#1133](https://github.com/Mkdir-arg/Chaco-Back/pull/1133) | PR 9 · kits y API M3 | `feat/emergencia-pr9-kits-v2` | 471 |
| 10 | [#1134](https://github.com/Mkdir-arg/Chaco-Back/pull/1134) | PR 8 · API M2 | `feat/emergencia-pr8-api-m2-v2` | 470 |
| 11 | [#1135](https://github.com/Mkdir-arg/Chaco-Back/pull/1135) | PR 10 · tablero y avisos | `feat/emergencia-pr10-tablero-v2` | 472 |
| 12 | [#1136](https://github.com/Mkdir-arg/Chaco-Back/pull/1136) | PR 11 · marcas | `feat/emergencia-pr11-marcas-v2` | 473 |
| 13 | [#1137](https://github.com/Mkdir-arg/Chaco-Back/pull/1137) | PR 12 · manual y Cambios | `feat/emergencia-pr12-docs-v2` | 474 |
| — | [#1138](https://github.com/Mkdir-arg/Chaco-Back/pull/1138) | **Borrador, NO MERGEAR**: todo junto contra `development`, solo para que el CI corra ya | `feat/emergencia-pr12-docs-v2` | — |

### Avance del merge (se actualiza con cada PR)

| PR | Estado | Merge en `development` | Notas de auditoría |
|---|---|---|---|
| #1125 PR 0 | Mergeado | `a03504da` | |
| #1126 PR 1 | Mergeado | `b75aca8c` | |
| #1127 PR 2 | Mergeado | `5bc7e8a4` | |
| #1128 PR 3 | Mergeado | `d0197bca` | |
| #1129 PR 4 | Mergeado | `86d5c6af` | |
| #1130 PR 5 | Mergeado | `870998e1` | 2 rondas. Se sacaron del serializer reglas que no tiene el servicio (`max_length=60`, `min_value=0`) y el 409 pasó a reconocerse por tipo (`UuidEnUso`, también en kits del PR 9). |
| #1131 PR 6 | Mergeado | `413eb813` | 2 rondas. Las reservas de derivación pasaron a `services/reservas_derivacion.py` (`estadias.py` 1316 → 1033 líneas). D2 del Cambio 409 en `consumir_reserva_de_derivacion`. Ficha `turno_bitacora.md` actualizada (la exige `check_design_agent`). |
| #1132 PR 7 | Mergeado | `916aa160` | Pasó por dos rondas y una tercera revisión acotada. `emergencia_alojar.py` (1893 líneas) quedó partido en 6 módulos más una fachada. D2 del Cambio 409 en la cama libre. `acciones_del_ingreso` es la regla única. La cama se bloquea siempre antes que la persona. Ficha `turno_bitacora.md`. |
| #1133 PR 9 | Mergeado | `70b5965e` | Una ronda. Kits y API M3. Migración `0121`. |
| #1134 PR 8 | Mergeado | `cf544a33` | Dos rondas. `views_emergencia.py` (1128 líneas) se partió en base, kits, llegadas y sin_derivacion. `ingreso_sin_candado` es la guarda única: GET y POST dan el mismo 409. La búsqueda por DNI tiene un tope `emergencia_buscar` de 300/h. |
| #1135 PR 10 | Mergeado | `8400f935` | Una ronda. Tablero E1 y avisos. Se aceptan 16 consultas en la vista y 12 en el dominio. Se actualizó la ficha `shells.md` y el sidebar quedó con una sola entrada activa en la recepción de kits. |
| #1136 PR 11 | Aprobado (ronda 2), espera el CI | | «En la puerta» quedó con una sola regla, «caso abierto y nunca derivado», en E1, E2 y E3. «Rechazo sin nueva acción» y la última traza tienen una sola fuente. |
| #1137 PR 12 | Pendiente | | Manual y Cambios 462 a 474. |

**MINOR registrados para PRs siguientes:**
- **PR 5:** el largo de `traslado_otro` no sale en el primer 400; `test_emergencia_api_contrato.py` tiene 1084 líneas; `_respuesta_400` privado; tercera definición de `CAP_ADMITIR`; doble `EXISTS` en `perfil/`; `validar_foto_de_la_app` duplica a `validar_adjunto`.
- **PR 9:**
  - El remito queda huérfano si el UNIQUE corta la recepción.
  - El contrato §12 dice «no importa el segundo cuerpo».
  - Hay helpers copiados (`_url`, `_errores_de`, `nombre_de`, `fecha_hora`).
  - La regla de acciones por estado de la entrega está repetida.
  - Un selector autoriza por su cuenta.
  - Los modelos traen la sexta copia de la traza inmutable.
  - Los tests de kits pasan las 1000 líneas.
  - Los modales están duplicados.
- **PR 8:** `opera_en_algun_dispositivo` repite `recibe_kits` en línea; habría que mover `recibe_kits` a `emergencia_programa`.
- **PR 10:**
  - Las localidades homónimas se agrupan por nombre.
  - «Todavía no hay casos» no aparece cuando hay red.
  - Falta la solapa «Mapa de la emergencia», que va deshabilitada.
  - `entregas_en_camino` carga todo.
  - Hay dos definiciones de ingreso directo.
  - Están copiados los elegibles, las plazas libres y `TONOS`/`ICONOS`.
  - La ventana RN-5.1 no tiene índice `(estado, cerrado_en)`.
  - Queda un comentario muerto en `test_nodo_ui_piezas`.
- **PR 11:**
  - Falta un test `@tag("mysql")` para `__has_key`.
  - `familias_en_la_puerta` debería acotarse con `pk__in`.
  - Los avisos de E3 tienen que llevar `role="status"`.
- **PR 7:** `acciones_del_ingreso` recibe el `total` calculado de dos formas (conviene calcularlo adentro). Quedan los alias `SITUACION_*` y el envoltorio `es_ingreso_directo` sin uso en producción. Hay un ciclo improbable con un egreso simultáneo, documentado en la fachada.
- **PR 6:** el protocolo de candados de D2 está copiado de `confirmar_ingreso` (convendría extraer `_bloquear_plazas` y `_cerrar_reservas_comunes`); tres mensajes literales copiados de `estadias.py`.

Para cada PR: CI en verde → `/auditoria pr <N>` → merge (el hook `guardia_merge` exige el «Aprobado @
SHA»). Al mergear, si el siguiente no se retargetea solo a `development`, cambiarle la base a mano.
Verificación local de la punta (`pr12-v2`): 9.051 tests, solo los 30 fallos conocidos del entorno.

Para seguir desde el local: `git fetch origin && git checkout feat/emergencia-pr12-docs-v2`.

---

## 1. Cómo seguir desde el local

```powershell
git fetch origin
git checkout docs/emergencia-analisis      # plan, análisis y este archivo
git checkout feat/emergencia-integracion-final  # todo el backend (PRs 0 a 11) junto y verificado
```

- **PR 0 a PR 10 ya están en `development`** (ver §0). Quedan abiertos el PR 11 (aprobado) y el PR 12.
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
| 12 | Manual del módulo y Cambios 457 a 469 en `requerimientos.md` | ✅ Verificado y pusheado | `feat/emergencia-pr12-docs` | `e96d1c4b` | integración final |
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

### ✅ Hecho: rebase sobre `development` (ver §0)
- `development` avanzó (hoy en `a1563b68`) y ya tiene `programas.0116_respuestas_ingreso_egreso_estadia`.
  Choca con `programas.0116_emergencia_base`. Al rebasar hay que **renumerar las migraciones del módulo
  (0116 a 0120)** y sus dependencias, y actualizar los números citados en los Cambios 457 a 469 y en el
  manual.
- Los Cambios 457 a 469 se numeraron después del 456 de `development`; al rebasar puede haber un conflicto
  chico al final del índice de `requerimientos.md`.

### Antes de operar una emergencia real
- **Frecuencia del cron de vencimientos.** `procesar_vencimientos` corre una vez por día (03:10) y al
  arrancar el contenedor. Con eso una derivación vencida puede quedar pendiente casi un día y la regla de
  «minutos sin avance» no sirve. Hay que programar una corrida cada ~5 min con
  `--solo emergencia.derivacion` y `--solo emergencia.caso_sin_avance`, en icore y en ECOM.

### Condiciones de cierre que todavía no se cumplieron
- Entradas en `docs/internal/requerimientos.md`: **hechas** en el PR 12 (Cambios 457 a 469, etiqueta
  `#emergencia`; `requerimientos.py --check` da OK). El estado de cada entrada se pasa a «Hecho» al
  mergear.
- **`/auditoria pr <N>`** de cada PR antes de mergear.
- Casos de QA por task.

### Fallos conocidos del entorno de desarrollo en la nube
La suite completa da 30 fallos que **también da `development` sin cambios** en ese contenedor:
`core.tests.test_sql_motor_real` (12, falta `mysqlclient`), tres `…no_se_traduce_a_like_binary_en_mysql`
(ídem) y `core.tests.test_settings_entorno_y_timeouts` (15, causa sin investigar). En un entorno con
MySQL deberían pasar; verificarlo en CI.

---

## 7. Qué sigue

1. Rebasar las ramas sobre `development` y renumerar las migraciones (ver §6).
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
| 2026-11-13 | Rebase sobre `development` en ramas `-v2` (migraciones 0117–0121, Cambios 462–474). Abiertos #1125 a #1137 (apilados) y #1138 (borrador para CI). |
| 2026-11-12 | PR 12: manual (`docs/internal/emergencia-manual.md`) y Cambios 457 a 469. Detectado el choque de la migración 0116 con `development`. |
| 2026-11-12 | Ola 5 (Opus): PR 8, PR 10 y PR 11. Integración final del backend con 8.986 tests. |
| 2026-11-12 | Ola 4: PR 7 y PR 9. Los subagentes se cortaron por límite de uso (Fable y después Opus); el orquestador verificó y pusheó lo commiteado. Integración de 0 a 9 con la suite completa. |
