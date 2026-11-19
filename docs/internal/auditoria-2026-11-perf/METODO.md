# Auditoría de performance y optimización 2026-11 — método de la serie

Tres capítulos con el mismo método: **Becas → Emergencia → Dispositivos**. Cada capítulo entrega
`docs/internal/auditoria-2026-11-perf/<modulo>.md` y sus issues en Backlog (Iteration 7). La base
es `/auditoria completa` (`.claude/skills/auditoria/modo-completa.md`): worktree del SHA, ficha
(`plantillas/ficha.md`), segunda pasada que reproduce lo grave y cruce con `auditoria-2026-10` §8.
Nada se implementa sin aprobación del PM.

## 1. Revisores por tajada

Cada tajada pasa por tres revisores en paralelo, con el mismo alcance (lista de archivos):

| Revisor | Agente | Mira | Prefijos |
|---|---|---|---|
| Thermos · corrección | `thermo-nuclear-review-subagent` | bugs, rupturas, seguridad, RBAC (`core/rbac.py`) | `ERR`, `SEG` |
| Thermos · calidad | `thermo-nuclear-code-quality-review-subagent` | estructura, capas, regla de 1.000 líneas, duplicación, JS y lógica en templates | `LIM`, `FE` |
| Chaco · performance | `chaco-auditor`, eje PERF | `rubricas/rendimiento.md` + skill `mysql-mariadb`; N+1, consultas que crecen, índices, exports, `read_timeout` 10 s | `PERF`, `DAT` |

Thermos está pensado para un diff: el prompt le dice que el alcance es la lista de archivos
completa, no cambios. Los IDs llevan la letra del módulo: `B-PERF-01`, `E-LIM-03`, `D-ERR-02`.

## 2. Alcance

Dentro: Python, templates, JS y API de cada módulo. `programas/models/__init__.py` se lee como
contexto (índices y relaciones), no se audita entero.

Fuera de las tajadas (no corren en caminos calientes): comandos de semilla (`seed_*`) y de
diagnóstico de un solo uso (`diagnosticar_*`, `medir_*`, `verificar_json_guardado`,
`proponer_alias_siis`, `corregir_datos_siis`). Los crons y comandos que corren en producción sí
entran.

Lo compartido se audita una sola vez, en el capítulo del módulo que más lo usa.

### Capítulo 1 · Becas (6 tajadas, 18 revisores)

| Tajada | Archivos |
|---|---|
| B1 Revisión y relevamientos | views/revision.py, views/relevamientos.py, selectors/revision.py, selectors/convocatorias.py, services/solapas.py, services/listados.py, templates becas/revision/**, becas/relevamientos/** |
| B2 Dashboard y reportes | services/dashboard_becas.py, views/dashboard_becas.py, services/reportes_becas.py, views/reportes_becas.py, forms_reportes.py, services/exportacion_reportes.py, services/reportes.py, views/inicio_becas.py, views/solapas_becas.py, static/custom/js/becas-dashboard.js, templates becas/reportes/** |
| B3 SIIS | services/siis.py, siis_envio.py, siis_sync.py, validacion_siis.py; commands procesar_casos_siis, enviar_casos_siis, correr_alta_siis, conciliar_envios_siis, reenviar_siis_pendientes, sincronizar_programas_siis, validar_casos_siis, _base_siis, _insumos_siis, _localidades_csv_siis |
| B4 Proceso masivo, cupo y padrón | services/proceso_masivo.py, views/proceso_masivo.py, services/cupo.py, views/cupo.py, services/padron.py, services/personas.py, services/alta_de_oficio.py, services/marca_de_oficio.py, services/vencimientos.py, services/avisos_resolucion.py; commands inscribir_de_oficio, completar_casos_renaper, cerrar_espera_colgada; templates becas/cupo/**, becas/email/** |
| B5 Configuración y constructor | views/configuracion.py, views/diseno.py, services/diseno.py, services/constructor.py, services/condiciones.py, forms_dinamicos.py, forms.py (parte Becas), views/pausas.py, services/pausas.py, views/eliminacion.py, services/eliminacion.py; templates becas/config/**, becas/formulario/**; JS nodo-constructor, nodo-condiciones, becas-modal, nodo-formulario |
| B6 App de campo y link público | api/views.py, api/serializers.py, api/throttles.py, services/campo.py, services/identidad.py, services/respuestas.py, services/becas.py, services/inscripcion_publica.py, services/inscripciones.py, services/autorizacion.py, services/catalogo_geografico.py, portal/{forms,services,views}/inscripcion.py, templatetags/becas_extras.py; JS nodo-firma, nodo-cascada-geo |

### Capítulo 2 · Emergencia (4 tajadas, 12 revisores)

| Tajada | Archivos |
|---|---|
| E1 Mesa y casos | selectors/emergencia.py, emergencia_mesa.py, services/emergencia.py, emergencia_ficha.py, emergencia_comun.py, emergencia_alta.py, views/emergencia.py, forms_emergencia.py, templates emergencia/*.html, emergencia/casos/** |
| E2 Alojar, recepción y cierre | selectors/emergencia_alojar.py, services/emergencia_alojar.py, emergencia_recepcion.py, emergencia_confirmacion.py, emergencia_cierre.py, emergencia_ingreso_comun.py, emergencia_sin_derivacion.py, services/reservas_derivacion.py, services/emergencia_programa.py |
| E3 Tablero, avisos, kits y dispositivo | selectors/emergencia_tablero.py, views/emergencia_tablero.py, services/avisos_emergencia.py, vencimientos_emergencia.py, configuracion_emergencia.py, views/emergencia_config.py, selectors/kits.py, services/kits.py, views/emergencia_kits.py, forms_emergencia_kits.py, views/emergencia_dispositivo.py, forms_emergencia_dispositivo.py, templates emergencia/kits/**, emergencia/dispositivo/** |
| E4 API de campo | api/serializers_emergencia.py, views_emergencia.py, views_emergencia_kits.py, views_emergencia_llegadas.py, views_emergencia_sin_derivacion.py, selectors/emergencia_llegadas.py, emergencia_campo.py, services/emergencia_campo.py, urls de emergencia, mixins_emergencia.py |

### Capítulo 3 · Dispositivos (4 tajadas, 12 revisores)

| Tajada | Archivos |
|---|---|
| D1 Legajo y detalle | views/dispositivos_legajo.py, services/detalle_dispositivo.py, selectors/auditoria_dispositivo.py, services/dispositivos.py, mixins_dispositivos.py, templates dispositivos/legajo/** |
| D2 Estadías, ingreso y ocupación | services/estadias.py, ingreso.py, ocupacion.py, movimientos.py, censo.py, plazas.py, sectores_plazas.py, nombre_plaza.py, selectors/estadia_detalle.py, trayectoria.py, capacidad_dispositivo.py, views/dispositivos_ingreso.py, dispositivos_capacidad.py, forms_ingreso.py, templates dispositivos/estadia/**, ingreso/**, sectores/** |
| D3 Bitácora, equipo y formularios | services/bitacora.py, bitacora_pantalla.py, bitacora_detalle.py, views/dispositivos_bitacora.py, forms_bitacora.py, services/equipo_dispositivo.py, horarios_dispositivo.py, agentes, buscador_agentes, sumar_agente, selectors de sugeridos, views/dispositivos_equipo.py, services/formularios_tipo.py, respuestas_dispositivo.py, views/dispositivos_formularios.py, dispositivos_config.py, forms_dispositivos.py, alertas_dispositivos.py, templates bitacora/**, config/**, JS nodo-formulario-tipo |
| D4 Edificios e inspecciones | services/inspecciones.py, edificios.py, validacion_relevamiento.py, selectors/edificios.py, inspecciones.py, vencimiento_inspecciones.py, views/dispositivos_edificios.py, dispositivos_relevamientos.py, api/views_inspecciones.py, serializers_inspecciones.py, views/reportes.py, templates edificios/**, relevamientos/** |

## 3. Pasos de cada capítulo

1. **Worktree** del SHA de `origin/development` (local, fuera del repo).
2. **Línea de base:** archivos > 1.000 líneas del alcance, `perf_audit.py`, y banco
   (`bench_mysql.py`) con las rutas del módulo.
3. **Pasada 1:** los 3 revisores de cada tajada, de a dos tajadas por vez (6 agentes en paralelo).
4. **Unificar:** deduplicar entre revisores (un hallazgo que dos revisores encuentran sube de
   peso), cruzar con `auditoria-2026-10` (README §8 descartados; si sigue abierto, se cita su ID).
5. **Pasada 2 · verificar:**
   - CRÍTICA/ALTA de corrección: PoC que afirma el defecto (como `modo-completa.md` §4).
   - Todo PERF ALTA o mayor: medición en el banco, MariaDB 10.11 con 10 s de `read_timeout`:
     ms en frío/caliente, consultas, `EXPLAIN ANALYZE`. Sin número, baja a INFO.
6. **Informe** `<modulo>.md`: resumen, índice, plan por olas (S=2, S-M=4, M=8, L=20 h), reglas
   para no repetirlo, descartados, línea de base.
7. **Issues:** uno por ola (no por ficha), en Backlog, Iteration 7, con las fichas y los casos de
   QA. Re-setear Status=Backlog al final y verificar.
8. **PR de documentación** con la entrada de `requerimientos.md`, que pasa por `/auditoria pr`.

## 4. Banco

- Becas: receta de `scripts/perf_mysql/README.md` tal cual (20.000 casos).
- Emergencia y Dispositivos: el banco no los siembra ni mide sus rutas. Antes del capítulo 2 va un
  PR (`perf/banco-emergencia-dispositivos`) con `scripts/perf_mysql/escenarios_emergencia.py` y `escenarios_dispositivos.py` (volumen de
  producción, a confirmar) y sus rutas en `bench_mysql.py`. **No** se toca `seed_perf`: lo usa el
  CI de performance.

## 5. Modelos

| Trabajo | Modelo |
|---|---|
| Revisores (pasada 1) | los de cada agente; `chaco-auditor` con `opus` |
| PoC y mediciones (pasada 2) | `sonnet` |
| Unificar, cruzar, informe | el juez |
| Sembrado del banco (PR) | `sonnet` |
