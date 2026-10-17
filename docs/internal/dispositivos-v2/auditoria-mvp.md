# Auditoría final del MVP de Dispositivos v2

Documento interno · 17/10/2026 · consolidación del carril GK, Cambio 325.

## 1. Contexto y método

Seis revisores contrastaron `3bccfe6b075bbb015f5aff918fcb21154da8fd81` con el
[alcance público del MVP, §2 y §3](../../client/funcionalidades/mvp-dispositivos-v2.md),
el [mockup](../../client/mockups/dispositivos-v2.html), el
[mapeo](mapeo-mockup.md), las tasks y el código. L1 revisó relevamiento; L2 ingreso/egreso;
L3 operación diaria; D1 P2–P6; D2 P7–P21; P los procesos completos y los roles.
Esta matriz vuelve a contrastar las promesas con el código integrado de los Cambios
321 (G1), 322 (G3), 323 (G4), 324 (G2) y 325 (GK). No sustituye los issues ni certifica
una integración móvil que no se ejecutó.

Fuentes externas leídas, sintetizadas sin incorporar sus logs ni datos de acceso:

| Revisión | Fuente original |
|---|---|
| L1 | `scratchpad/lic/aud_l1.out` |
| L2 | `scratchpad/lic/aud_l2.out` |
| L3 | `scratchpad/lic/aud_l3.out` |
| D1 | `scratchpad/lic/aud_d1.out` |
| D2 | `scratchpad/lic/aud_d2_codex_final.md` y `%TEMP%/chaco-audit/d2/INFORME-D2.md` |
| P | `scratchpad/lic/aud_p_codex_final.md` y `%TEMP%/chaco-audit/p/informe-procesos.md` |

`scratchpad/lic` corresponde a la entrega de auditoría externa de la sesión
`a0abf18a-a875-4841-ae72-6b10153ff98b`; los archivos temporales no son dependencias
del producto. Las referencias duraderas son el código, sus tests y las entradas del
[registro](../requerimientos.md).

Los revisores de lógica rompieron guardas y comprobaron rojos, restaurando copias.
Una mutación que sobrevivió no se considera una regla desprotegida si otra defensa
del modelo o del motor la sigue rechazando: ocurrió con el UNIQUE de alojamiento y
con la plaza fuera de servicio. D2 usó contratos sobre DOM, sin mutar código.
P repitió en una copia limpia los recorridos afectados por mutaciones concurrentes
del worktree original; esos verdes compartidos no se presentan como evidencia aislada.

Hubo pruebas sobre SQLite, render Chromium a 1440/390 px y MariaDB 10.11 sin tablas
de zona horaria. P documentó 177 migraciones reales y bloques de API, censo y
concurrencia; G1 volvió a probar historia y concurrencia en MariaDB. GK ejecutó las
migraciones reales y los siete escenarios de `CarreraDeInspeccionTests` en un
MariaDB 10.11 efímero, puerto 3391; el cierre restaurado pasó 18 tests de concurrencia
y contrato del motor. La regresión GK cubrió 244 módulos de `programas core` por lotes:
5.038 ejecuciones, 64 omisiones, sin fallos pendientes después de actualizar y repetir
la expectativa nominal de bitácora automática. Performance: 35 tests aprobados;
nueve mutaciones detectadas, incluidas las de candado y orden de alcance en MariaDB.
Los comandos y resultados de los gates constan en el Cambio 325. Ver §7 para los límites.

Leyenda: **✅** comportamiento comprobado en el servidor actual; **🟦** apartamiento
aprobado, con su Cambio; **❌** función excluida del MVP, con referencia al §3 público.
Un ✅ no significa igualdad visual completa ni verificación de la app: la columna
Estado explicita el límite cuando corresponde. Las rutas abreviadas `services/`,
`selectors/`, `views/`, `api/` y `models/` son de `programas`; los tests sin prefijo
son módulos de `programas.tests`. Las pantallas se identifican por el mockup.

## 2. Matriz de promesas del §2

### Relevamiento en campo

| Promesa | Task | Código actual | Test | Pantalla | Estado final |
|---|---|---|---|---|---|
| Aplicación conectada: autenticación, agenda e integración | 38 #703 | `api/views.py:ObtainCampoToken`, `api/views_inspecciones.py:InspeccionViewSet`, `api/serializers_inspecciones.py` | `test_api_campo_inspecciones` (autenticación, contrato, esquema y alcance); gate `contratos-api` | API de campo | ✅ servidor; app e integración entre repositorios no verificadas (§7) |
| Coordinador crea y asigna; agente recibe solo lo asignado | 35 #700, 36 #701, 38 #703 | `services/inspecciones.py:crear_inspeccion`, `inspecciones_asignadas`, `_exigir_asignado`; `views/dispositivos_relevamientos.py` | `test_dispositivos_inspecciones.AsignacionTests`, `SoloLoAsignadoTests`; `test_api_campo_inspecciones`; `test_dispositivos_concurrencia.CarreraDeInspeccionTests` | P21 → API | ✅; candado común con última desvinculación y alcance releído bajo lock (325) |
| Elegir edificio; predio compartido se releva una sola vez y lo ven sus instituciones | 20 #685, 35 #700, 37 #702 | `models/Edificio.dispositivos`; `services/inspecciones.py:inspecciones_de_dispositivo`; `services/edificios.py` | `test_dispositivos_inspecciones.PredioCompartidoTests`, `test_dispositivos_capacidad` | P19/P21 | ✅; edificio N:M, sectores de cada dispositivo |
| Cargar criticidad, observaciones y fotos | 35 #700, 38 #703 | `services/inspecciones.py:registrar_resultado`, `agregar_foto`; `core/validators.py`; `core/views/media.py` | `test_dispositivos_inspecciones.ResultadoYFotosTests`, `MediaDeFotosTests`; `test_api_campo_inspecciones` | API/informe/P19 | 🟦 Cambios 289/322: JPEG, PNG o WEBP; HEIC requiere conversión en app (no verificada); fotos nuevas rechazadas tras revisión, reenvíos previos idempotentes |
| Responsable y fecha automáticos | 35 #700 | `services/inspecciones.py:registrar_resultado` asigna usuario y `timezone.now()` | `test_dispositivos_inspecciones.ResultadoYFotosTests` | informe/P19 | ✅; fecha mostrada en hora local |
| Completar sin señal y sincronizar al reconectar | 39 #704 | `services/inspecciones.py:registrar_resultado`, `agregar_foto`; `core/db.py:q_uuid_en_texto`; migración `0093` | `test_api_campo_inspecciones.IdempotenciaTests`, `ConflictoTests`; `CarreraDeInspeccionTests` | API de campo | ✅ lado servidor: UUID, reintentos, fotos antes/después del resultado y 409; almacenamiento y cola móvil no verificados (§7) |
| Saber si está asignado, cargado o revisado | 35 #700, 36 #701 | `models/InspeccionEdificio`; `services/inspecciones.py:marcar_revisado`; `services/detalle_dispositivo.py:_evento_de_relevamiento` | `test_dispositivos_revision`; `test_dispositivos_auditoria_g3` | P21/informe/P19 | 🟦 Cambios 304/322: revisión con `revisado_en/por`, sin cuarto estado; marca visible también en P19 |
| Listado por dispositivo y detalle con observaciones/fotos | 36 #701, 37 #702 | `views/dispositivos_relevamientos.py`; `services/inspecciones.py:informe_de_relevamiento`; `services/detalle_dispositivo.py:infraestructura_del_dispositivo` | `test_dispositivos_relevamientos_listado`, `test_dispositivos_relevamiento_informe`, `test_dispositivos_infraestructura` | P19/P21/informe | 🟦 Cambios 279/289/322: cinco solapas; informe propio, incluido Cancelados; agente oculto a institución antes de realización |
| Semáforo de criticidad sobre el dispositivo | 40 #705 | `services/inspecciones.py:semaforo_de_inspeccion`, `semaforo_de_ultimas`, `semaforos_de_dispositivos`; `selectors/vencimiento_inspecciones.py` | `test_dispositivos_infraestructura`, `test_dispositivos_fidelidad_fi`, `test_dispositivos_auditoria_g3` | P2/P4/P19 | 🟦 Cambios 308/322: vencimiento de asignación, sin vigencia periódica; Crítico prevalece sobre Vencido |

### Ingreso y egreso de personas

| Promesa | Task | Código actual | Test | Pantalla | Estado final |
|---|---|---|---|---|---|
| Buscar por documento; identidad validada y alta en el mismo circuito | 25 #690 | `services/ingreso.py:buscar_ciudadano_por_dni`, `consultar_registro_de_personas`, `confirmar_ingreso`; `views/dispositivos_ingreso.py` | `test_dispositivos_ingreso`; `test_dispositivos_personas_red` | P6 paso 1 | ✅ servidor con integración externa simulada; alta al confirmar, con `ciudadano.crear`; RENAPER real no ensayado |
| Registrar ingreso con fecha y hora | 24 #689, 25 #690 | `services/estadias.py:ingresar_persona`; `models/Estadia` | `test_dispositivos_estadias.IngresoTests`, `test_dispositivos_ingreso` | P6 confirmación | ✅; no futuro, operación atómica |
| Asignar sector/plaza donde corresponde | 21 #686, 23 #688, 25 #690 | `services/ingreso.py:maneja_plazas`, `plazas_para_ingresar`; `services/estadias.py:_bloquear_plaza` | `test_dispositivos_ingreso`, `test_dispositivos_estadias` | P5/P6 | ✅; elegibilidad según tipo, sin paso ficticio para tipos sin plazas |
| Verificar toda la red; nadie alojado en dos lugares simultáneamente | 24 #689 | `services/estadias.py:verificar_alojamiento_en_red`, `_exigir_intervalo_sin_alojamiento`, `ingresar_persona`; `models/Estadia.clave_alojamiento` | `test_dispositivos_personas_red`, `test_dispositivos_estadias.ClaveDeAlojamientoTests`, `test_dispositivos_concurrencia.CarreraDePlazaTests` | P6 | ✅ Cambio 321: historia y presente, intervalos semiabiertos, candado por persona y UNIQUE común; mensaje ajeno opaco |
| Plaza libre y egreso nunca anterior al ingreso | 25 #690, 26 #691 | `services/estadias.py:_exigir_plaza_libre`, `_exigir_plaza_libre_desde`, `egresar_persona`; `models/Estadia.clean` | `test_dispositivos_estadias`, `test_dispositivos_movimientos`, `test_dispositivos_egreso`, concurrencia | P5/P6/P9 | ✅; también protege último movimiento y ocupación retroactiva de plaza |
| Egreso con fecha, motivo del catálogo y destino o derivación | 26 #691 | `services/estadias.py:egresar_persona`; `forms_dispositivos.py:EgresoForm` | `test_dispositivos_egreso`, `test_dispositivos_personas_red` | P9 desde P4/P7 | 🟦 Cambios 269/321: destino de texto obligatorio en servicio; derivación formal ❌ §3 «Mirada de red» |
| Liberar cupo y recalcular disponibilidad automáticamente | 22 #687, 26 #691, 27 #692 | `services/estadias.py:egresar_persona`; `services/ocupacion.py:ocupacion_de_plazas` | `test_dispositivos_ocupacion`, `test_dispositivos_egreso`, `test_dispositivos_censo` | P4/P5/P10 | ✅; libera clave en el mismo UPDATE, cifras derivadas |
| Legajo ciudadano muestra estadías, incluidas las cerradas | 28 #693 | `selectors/trayectoria.py:trayectoria_de`; `legajos/views/dispositivos.py`; `legajos/templates/legajos/solapas/dispositivos.html` | `test_solapa_dispositivos` | P16 | 🟦 Cambios 271/297: pantalla independiente; historia de red con `ciudadano.ver`, acción a P7 solo con alcance |
| Trazabilidad: qué pasó, quién y cuándo | 24 #689, 26 #691, 33 #698 | `services/movimientos.py:registrar_movimiento`; `models/MovimientoEstadia`; `selectors/auditoria_dispositivo.py` | `test_dispositivos_movimientos`, `test_dispositivos_auditoria`, `test_dispositivos_detalle.IdentidadDeEstadiasTests` | P4 Historial/P7/P10 | ✅; movimientos inmutables; identidad omitida sin capacidad y por defecto sin usuario (324/325) |

### Operación diaria del dispositivo

| Promesa | Task | Código actual | Test | Pantalla | Estado final |
|---|---|---|---|---|---|
| Movimientos entre sectores con registro | 29 #694 | `services/estadias.py:cambiar_plaza`; `services/movimientos.py`; `models/MovimientoEstadia` | `test_dispositivos_movimientos`, `test_dispositivos_fidelidad_fb`, concurrencia | P4/P7 | ✅; motivo, fecha, alcance y plaza libre bajo candado |
| Permanencia de cada persona | 29 #694, 33 #698 | `models/Estadia.dias_de_permanencia`; `selectors/estadia_detalle.py:detalle_de_estadia`; `templates/programas/dispositivos/legajo/detail.html` | `test_dispositivos_movimientos`, `test_dispositivos_egreso`, `test_dispositivos_detalle` | P4/P7/P9 | ✅ Cambio 324: calendario local, mismo método, sin atributo que lo sombree |
| Cambios de estado de estadía | 29 #694 | `models/Estadia.Estado`; `services/estadias.py:ingresar_persona`, `egresar_persona` | `test_dispositivos_estadias`, `test_dispositivos_movimientos` | P4/P7 | 🟦 Cambio 273 y decisión PM ratificada en 325: ACTIVA/EGRESADA; ingreso/egreso son las transiciones del MVP |
| Novedades y observaciones con turno y responsable | 30 #695, 32 #697 | `services/bitacora.py:registrar_entrada`, `anotar_en_bitacora`, `corregir_entrada`; `models/EntradaBitacora` | `test_dispositivos_bitacora`, `test_dispositivos_bitacora_automatica`, `test_dispositivos_bitacora_pantalla` | P10 | 🟦 Cambios 283/288/297: manuales y automáticas; corrección agrega versión por #695 aunque §3 excluía versionado; solo turno en curso, sin pase formal |
| Censo automático por turno; nadie tipea cifras | 31 #696 | `services/censo.py:censo_por_dia`, `fecha_operativa_de`; `services/ocupacion.py:alojada_en`; `services/bitacora_pantalla.py` | `test_dispositivos_censo`, `test_dispositivos_bitacora_pantalla.HuecoSinTurnoTests` | P10 | ✅; inicial + ingresos − egresos = final, noche/guardia y huecos; Cambio 323 dibuja hueco con movimientos o descuadre |
| Seguimiento interno durante la estadía | 33 #698 | `selectors/estadia_detalle.py:detalle_de_estadia`, `novedades_de_estadia` | `test_dispositivos_estadia_detalle` | P7 | 🟦 Cambios 277/283: ficha mínima, movimientos y novedades; no formularios configurables (§3 «Formularios») |
| Alertas por criticidad | 34 #699 | `services/alertas_dispositivos.py`; `core/services/vencimientos.py:AVISOS`; `selectors/vencimiento_inspecciones.py` | `test_dispositivos_alertas`, `test_dispositivos_auditoria_g3` | P4/P19 | ✅; cinco reglas al consultar, resolución en el origen, sin bloquear operaciones; cron proactivo fuera del MVP por decisión PM |
| Situación: personas, sector y plazas disponibles | 27 #692 | `services/detalle_dispositivo.py:estadias_del_dispositivo`, `indicadores_de_plazas`; `services/ocupacion.py`; `views/dispositivos_legajo.py` | `test_dispositivos_detalle`, `test_dispositivos_fidelidad_fb`, tests `performance` | P4/P5 | 🟦 Cambios 298/324/325: cuatro indicadores reales, identidad solo con `ciudadano.ver`; sin capacidad «Persona alojada», con menú distinguido por ubicación/ingreso |
| Auditoría básica de lo actuado | 34 #699 | `selectors/auditoria_dispositivo.py:FeedAuditoria`; `services/detalle_dispositivo.py:eventos_de_historial` | `test_dispositivos_auditoria`, `test_dispositivos_detalle.IdentidadDeEstadiasTests` | P4 Historial | ✅; cuatro fuentes paginadas sin duplicar ingreso; nombres de personas requieren opt-in/capacidad, defaults cerrados (325) |

## 3. Pantallas P2–P21

«Igual» refiere a los elementos disponibles del MVP. Las referencias visuales son las
capturas de D1/D2 y de los carriles, no una nueva certificación pixel a pixel de GK.
Los estados móviles sin diseño específico se comparan contra el canon productivo.

| Pantalla | Superficie actual / evidencia | Igual o apartamiento final |
|---|---|---|
| P2 Instituciones | `legajo/list.html`; `test_dispositivos_listado` | 🟦 Cambio 286: filtros canónicos, columnas reales, CSV/Excel separados, acción de ícono; sin Importar. Eyebrow protegido por 323. Header que envuelve y contador de filtros se conservan por decisión PM. |
| P3 Alta | `legajo/form.html`; `test_dispositivos_fidelidad_fi`, `test_dispositivos_legajo` | 🟦 Cambios 308/323: dos columnas, panel de duplicados y validación; siete marcas para enviar, sin campos ni procedencia inexistentes; ModernModal. Alta solo admin del programa; borrador propio previo sigue editable. |
| P4 Detalle | `legajo/detail.html`; `test_dispositivos_detalle`, `test_dispositivos_egreso` | 🟦 Cambios 298/324/325: cinco solapas reales, indicadores grandes con tono, sin avatar, menú canónico, sin identidad sin capacidad; rótulo accesible con ubicación/ingreso. Sin ficha configurable, permiso ni traslado. |
| P5 Sectores/plazas | `legajo/sectores.html`; `test_dispositivos_sectores`, `test_dispositivos_fidelidad` | 🟦 Cambios 291/299: mapa canónico y leyenda con íconos, cinco estados; altas de reserva/préstamo ausentes. PM conserva Reservada/Prestada, indicador y Liberar. |
| P6 Ingreso | `ingreso/paso_*.html`; `test_dispositivos_ingreso` | 🟦 Cambios 272/299/323: tres pasos, mapa completo, aviso crítico sin bloquear, resumen sector · plaza; sin ficha mínima configurable ni Excepcional. Mensaje de red opaco fuera del alcance. |
| P7 Estadía | `estadia/detalle.html`; `test_dispositivos_estadia_detalle` | 🟦 Cambios 277/283/309: ficha mínima y tres solapas, timeline, otras estadías, cambio/egreso; sin permiso, traslado, formularios ni sensibilidad. Errores AJAX accesibles corregidos por 323. |
| P8 Traslado | Sin superficie MVP | ❌ §3 «Circuito de las personas»: se hace egreso e ingreso independientes, sin tránsito ni reserva enlazada. |
| P9 Egreso | Modales en `estadia/detalle.html` y `legajo/detail.html`; `test_dispositivos_egreso` | 🟦 Cambios 269/321/323/324: motivo y destino obligatorios, pertenencias y aviso; destino libre en vez de derivación formal; permanencia unificada y error asociado al control. Footer móvil canónico conservado. |
| P10 Bitácora | `bitacora/bitacora.html`; `test_dispositivos_bitacora_pantalla` | 🟦 Cambios 283/297/323: tarjetas, censo y entradas reales; switch Activo respetado, hueco visible sin acciones. Sin pase, exportación ni regularización; corrección versionada aprobada. |
| P11 Espera/derivaciones | Sin superficie MVP | ❌ §3 «Mirada de red»: sin cola priorizada ni aceptación/rechazo/vencimiento de derivaciones. |
| P12 Merendero | Fuera de esta auditoría | ❌ §3 «Lo demás»: programa Merenderos completo excluido. |
| P13 Prestación alimentaria | Fuera de esta auditoría | ❌ §3 «Lo demás»: no se rediseña la grilla de Merenderos. |
| P14 Configuración del tipo | Sin configuración avanzada de la maqueta | ❌ §3 «Formularios»/«Capacidad»: no se entrega el configurador completo. Modelo y defaults de tipos sí alimentan el circuito; no equivale a cumplir P14. |
| P15 Roles | ABM transversal existente; `core/rbac.py` | 🟦 Cambio 134 C-12: capacidades agregadas al catálogo, ABM sin rediseño. Alcance por subsecretaría y sensibilidad ❌ §3 «Permisos». El PM configura roles. |
| P16 Trayectoria | `legajos/solapas/dispositivos.html`; `test_solapa_dispositivos` | 🟦 Cambios 271/297: URL independiente, tabla de red e ícono condicionado por alcance; no reproduce las otras seis solapas del legajo. |
| P17 Formularios | Sin superficie MVP | ❌ §3 «Formularios»: sin constructor por tipo. |
| P18 Sensibilidad | Sin superficie MVP | ❌ §3 «Permisos»: sin niveles médico/psicosocial/judicial. |
| P19 Infraestructura | Solapa de `legajo/detail.html`; `test_dispositivos_infraestructura`, `test_dispositivos_auditoria_g3` | 🟦 Cambios 280/289/298/308/322/324/325: tres métricas grandes reales, edificios, domicilio, coordenadas si existen y enlace externo, predio compartido, timeline/fotos/informe; revisión y fecha en curso visibles. Sin tenencia, habitaciones, plano ni vigencia automática. Crítico prevalece. |
| P20 Consumos/contratos | Sin superficie MVP | ❌ §3 «Lo demás»: sin pagos, avisos ni escalamiento de consumos. |
| P21 Relevamientos | `relevamientos/list.html`, `informe.html`; `test_dispositivos_relevamientos_listado`, `test_dispositivos_revision` | 🟦 Cambios 279/289/304/322: cinco solapas, asignación en dos pasos Edificio → Agente → Vence → Indicaciones, informe también cancelado y revisión. Sin periodicidad, prioridad, exportar, chips no disponibles ni Relevar ya. Geometría móvil compartida conservada por PM. |

Los templates de esta tabla son relativos a
`programas/templates/programas/dispositivos/`, excepto P16, relativo a
`legajos/templates/`. Los informes no tienen frame propio de mockup: siguen el
arquetipo Detalle. La excepción de dos franjas grandes en P4/P19 queda explícita
en `.claude/design/componentes/stat_card.md`; no habilita dos franjas en otras pantallas.

## 4. Los seis procesos de punta a punta

Los seis recorridos positivos de P se completaron sin superusuario, en su copia de
`3bccfe6b`, sobre SQLite y MariaDB. P-07 y P-08 fueron sondas adicionales de defectos;
no se confunden con los seis recorridos. La regresión actual se sostiene en los tests
versionados indicados, no en volver a ejecutar los scripts temporales de P.

| Proceso | Recorrido y salida final | Regresión actual / cierre |
|---|---|---|
| P-01 · ciclo institucional | Admin del programa crea borrador → envío → observación → corrección → reenvío → validación; inactiva/cierra según capacidad. | `test_dispositivos_legajo`, `test_dispositivos_listado.AccionDeAltaTests`, `test_dispositivos_auditoria`; 323 evita ofrecer alta delegada que termine en 403. Reactivación ❌ §3 «Legajo». |
| P-02 · capacidad física | Crear/vincular edificio compartido → sectores de cada institución → plazas → fuera de servicio con motivo → volver a servicio. Predio común, organización operativa separada. | `test_dispositivos_capacidad`, `test_dispositivos_sectores`, `test_dispositivos_plazas_acciones`; 322/325 protegen el último vínculo durante relevamiento, aun con concurrencia real. |
| P-03 · persona y día operativo | DNI/alta → ingreso → bloqueo de doble alojamiento → cambio → novedad/corrección → egreso → plaza libre → nuevo ingreso manual → trayectoria. Censo inicial 0 + 2 ingresos − 1 egreso = 1; cambiar plaza no altera existencia. | `test_dispositivos_ingreso`, `test_dispositivos_personas_red`, `test_dispositivos_movimientos`, `test_dispositivos_censo`, `test_dispositivos_bitacora`, `test_solapa_dispositivos`; 321/323/324. Reconocer reingreso automáticamente no es el acto manual de reingresar. |
| P-04 · campo | Coordinador asigna → agente autentica/descarga → fotos y resultado → reintentos → revisión → institución consulta resultado/semáforo compartido. | `test_api_campo_inspecciones`, `test_dispositivos_revision`, `test_dispositivos_infraestructura`, `CarreraDeInspeccionTests`; 322/325. Servidor verificado; recorrido con celular pendiente (§7). |
| P-05 · permisos y alcance | Admin, operador, coordinador, agente, lector y usuario sin rol recorren solo sus superficies. Asignación institucional y capacidad son condiciones independientes; P7 exige ciudadano antes de buscar. | `test_dispositivos_legajo.AlcanceDispositivosTests`, `test_dispositivos_detalle`, `test_api_campo_inspecciones`, `test_dispositivos_relevamiento_informe`; 324/325 eliminan identidad de P4 y sus defaults. Checklist en §6. |
| P-06 · tiempo, avisos e historial | Se cruza vencimiento → P4 calcula aviso → se resuelve en su origen → desaparece aviso; traza permanece. Revisar un resultado crítico no lo vuelve sano: hace falta un nuevo resultado. | `test_dispositivos_alertas`, `test_dispositivos_auditoria`, `test_dispositivos_auditoria_g3`; 322 conserva rojo ante vencimiento. Avisos al consultar; ejecución por cron proactivo fuera del MVP por PM. |

## 5. Hallazgos y cómo se cerraron

Los IDs se conservan por revisor; un mismo defecto hallado por varios aparece en
cada fila. No se arrastran los «difiere» originales como si el arreglo no existiera.

| Revisor / severidad / hallazgo | Cierre final y evidencia |
|---|---|
| L1 MINOR 1 · API fuera del gate de contratos | **322 G3** agrega módulo a `pr-backend.yml`; **325 GK** ubica su test en `ContratosDeApiTests`. |
| L1 MINOR 2 · foto nueva después de revisión | **Decisión PM + 322 G3:** rechazar nueva foto con 409 `ESTADO_NO_ADMITE`; reenvío idéntico conserva idempotencia. `test_api_campo_inspecciones`, `test_dispositivos_auditoria_g3`. |
| L1 MINOR 3 · fotos de cancelado inaccesibles desde listado | **322 G3:** Cancelados ofrece Ver informe; no habilita mutaciones. `test_dispositivos_relevamientos_listado`. |
| L1 MINOR 4 · revisión invisible en P19 | **322 G3:** badge Revisado, revisor/fecha, criticidad en texto y tono. `test_dispositivos_auditoria_g3`. |
| L1 MINOR 5 · última desvinculación deja tarea huérfana | **322 G3:** rechaza última desvinculación con ASIGNADA. **325 GK:** candado común con asignación, alcance después de esperar y rechazo de edificio ya sin vínculos; tests de ambos órdenes en MariaDB. |
| L1 MINOR 6 · Vencido desplaza Crítico | **Decisión PM + 322 G3:** Alta prevalece en edificio y dispositivo; `test_dispositivos_auditoria_g3`, fidelidad FI. Sustituye precedencia anterior de 308. |
| L1 MINOR 7 · foto en curso sin fecha en P19 | **322 G3:** fecha realizada o fecha de foto si aún no hay resultado; tests G3/FB. |
| L2 MAJOR 1 · superposición histórica en red | **321 G1:** exclusión de intervalos al ingresar bajo candado de persona; `test_dispositivos_personas_red` y concurrencia histórica. El egreso solo acorta intervalo; no impide cerrar datos históricos inconsistentes. |
| L2 MAJOR 2 · nombre/DNI de P4 sin capacidad | **Decisión PM + 324 G2:** ocultar identidad conservando fila y operación; tests de celda, menú, modales e Historial. **325 GK:** defaults cerrados y rótulos distinguibles. |
| L2 MAJOR 3 · permanencia P4/P7 distinta | **324 G2:** mismo método de calendario local; `test_dispositivos_egreso`. |
| L2 MINOR 1 · destino opcional en servicio | **Decisión PM + 321 G1:** destino obligatorio, normalizado, sin cambiar estado si falta; `test_dispositivos_personas_red`. |
| L2 MINOR 2 · atributo muerto sombrea método | **324 G2:** eliminado y test que exige método invocable. |
| L2 MINOR 3 · Reservada/Prestada sin alta desde UI | **Decisión PM, ratificada en 325:** conservar leyenda, estados, indicador y Liberar; altas de reservas/préstamos siguen fuera. No se agrega flujo ficticio. |
| L2 MINOR 4 · sondeo autoriza admitir pero recorta con ver | **321 G1:** alcance con `dispositivo.admitir`; test con admitir y sin ver. |
| L2 MINOR 5 · P7/P16 nombran institución ajena | **Decisión PM de alcance ya aprobada, Cambios 271/277:** trayectoria de red deliberada con `ciudadano.ver`; enlaces solo en alcance. Se conserva el sondeo opaco de ingreso. |
| L2 MINOR 6 · escaneo DNI hidrata todos los legajos | **321 G1:** `values_list(id, dni)` e hidratación del ganador; test de materialización y presupuestos nuevos. |
| L3 MAJOR 1 · dos cálculos de permanencia | **324 G2**, mismo cierre que L2 MAJOR 3. |
| L3 MINOR 2 · atributo muerto | **324 G2**, mismo cierre que L2 MINOR 2. |
| L3 MINOR 3 · test tautológico de indicadores | **324 G2:** valores/tonos literales y umbrales 50/90; mutación detectada. |
| L3 MINOR 4 · hueco sin tarjeta P10 | **Decisión PM + 323 G4:** tarjeta de solo lectura con movimientos o descuadre, no seleccionable; `HuecoSinTurnoTests`. |
| L3 MINOR 5 · switch Activo ignorado al crear turno | **323 G4:** formulario/vista/servicio transmiten activo; test con switch encendido y apagado. |
| D1 MAJOR H-1 · indicadores chicos P4/P19 | **Decisión PM + 324 G2:** variante tablero con tono explícito y sin alterar gradiente por defecto; **325 GK** aclara excepción de ambas franjas. Tests de componente, detalle e infraestructura. |
| D1 MINOR H-2 · header envuelto alineado a izquierda | **Decisión PM:** conservar pieza compartida, no modificar todo el sistema por este MVP. Apartamiento visual aceptado, sin corrección lateral. |
| D1 MINOR H-3 · resumen plaza/sector invertido | **323 G4:** sector · plaza; `test_dispositivos_ingreso.ResumenDelPasoFinalTests`. |
| D1 MINOR H-4 · Swal propio en P3 | **323 G4:** ModernModal y toast canónicos; render y fixtures JS. |
| D1 MINOR H-5 · eyebrow sin test | **323 G4:** aserción literal y mutación roja; `test_dispositivos_listado.EncabezadoTests`. |
| D1 MINOR H-6 · falta aviso crítico en ingreso | **323 G4:** alerta informativa con umbral del tipo y sin bloquear; `AvisoDeOcupacionCriticaTests`. |
| D1 MINOR H-7 · asteriscos de borrador frente a validación | **Decisión PM + 323 G4:** siete campos de validación con marca; los ausentes del modelo no se inventan. `test_dispositivos_fidelidad_fi`. |
| D1 MINOR H-8 · avatar adicional | **Decisión PM + 324 G2:** sin avatar, nombre/DNI autorizados; test de HTML. |
| D1 MINOR H-9 · filtros sin contador de activos | **Decisión PM:** no modificar la pieza compartida de filtros. Apartamiento visual aceptado. |
| D2 MAJOR D2-01 · error AJAX sin ARIA/foco | **323 G4:** marcar inválido, asociar error sin perder ayuda, enfocar primer control y limpiar al corregir; `test_becas_feedback_js.AjaxJsAccesibilidadDeErroresTests`. |
| D2 MINOR D2-02 · Vence antes que Agente | **322 G3:** orden Edificio → Agente → Vence → Indicaciones; test de posición en template y render a ambos anchos. |
| D2 MINOR D2-C1 · texto en dos líneas en footer móvil | **Decisión PM:** conservar footer canónico compartido, sin parche de Dispositivos; apartamiento visual aceptado. |
| D2 MINOR D2-C2 · confirmación ocupa altura móvil completa | **Decisión PM:** prevalece runtime compartido; no modificar shell/CSS global en este MVP. No se declara igualdad con hoja inferior. |
| P MAJOR P-M1 / P-01 · identidad de P4 | **324 G2 + 325 GK**, mismo cierre que L2 MAJOR 2. |
| P MAJOR P-M2 / P-02 · creador delegado termina en 403 | **Decisión PM + 323 G4:** alta y buscador de duplicados solo admin del programa; botón y servidor con mismo mixin; pruebas sin `programa.configurar`. |
| P diferencia · no hay reactivación | **Decisión PM:** fuera del MVP, §3 «Legajo de la institución»; no es defecto pendiente de implementación de este carril. |
| P diferencia · cron no ejecuta AVISOS | **Decisión PM:** avisos al consultar; proactividad por cron fuera del MVP. Ver §7 sobre instalación ECOM. |
| Revisión G2 MINOR · menús genéricos repetidos | **325 GK:** rótulo con sector/plaza o ingreso; test sin capacidad, cuatro filas y cuatro etiquetas sin nombres/DNI. |
| Revisión G2 MINOR · defaults exponen personas | **325 GK:** `evento_de_movimiento`, `FeedAuditoria`, `auditoria_del_dispositivo` optan por False; servicio sin usuario oculta identidad. Test de las cuatro entradas y cuatro mutaciones independientes. |
| Revisión G2 MINOR · doble fuente del nombre en celda | **325 GK:** `persona_visible` también en celda; condición solo alrededor de DNI. Test del nombre preparado por la vista y mutación. |
| Revisión G2 MINOR · ficha de stat card contradictoria | **325 GK:** excepción acotada P4/P19; sin cambio de CSS, clases o componente compartido. |
| Revisión G3 MINOR · test de gate en clase ajena | **325 GK:** clase independiente `ContratosDeApiTests(SimpleTestCase)` para `pr-backend.yml`. |
| Revisión G3 MINOR · carrera asignación/desvinculación | **325 GK:** ambas toman Edificio sin JOIN dentro del FOR UPDATE; alcance después del lock y guarda sin vínculos. Tests reales en ambos órdenes y mutaciones de candado/orden/guarda. |

### Las catorce decisiones del PM

Estas decisiones vienen cerradas en el encargo; no son preguntas para una nueva aprobación.

| N.º | Decisión | Aplicación |
|---|---|---|
| 1 | Identidad oculta en P4 sin `ciudadano.ver`; fila permanece | 324/325 |
| 2 | Alta de institución solo por admin del programa | 323 |
| 3 | Franja grande conservando tonos | 324; contrato de dos franjas P4/P19 aclarado en 325 |
| 4 | Destino obligatorio también en servicio | 321 |
| 5 | Rechazar foto nueva tras revisión; conservar reenvío idempotente | 322 |
| 6 | Crítico prevalece sobre Vencido | 322 |
| 7 | Dibujar hueco de P10 de solo lectura | 323 |
| 8 | Asteriscos según validación del mockup, sobre campos reales | 323 |
| 9 | Sin avatar de persona en P4 | 324 |
| 10 | Reservada/Prestada y Liberar se quedan, sin alta nueva | 325; recorte de 291 conservado |
| 11 | Cambios de estado del MVP = ingreso/egreso | 325; regla de 273 conservada |
| 12 | Reactivación fuera del MVP | 325; §3 «Legajo» |
| 13 | Avisos por cron fuera del MVP; se calculan al consultar | 325; no se agregan REGLAS ni correo |
| 14 | No rediseñar piezas compartidas de todo el sistema | Header, filtros, footer y geometría móvil conservados; no impide el arreglo explícitamente encargado de errores AJAX (323) ni la ampliación autorizada de stat card (324) |

## 6. Checklist de capacidades por rol para el PM

Derivado del informe de procesos, contrastado con `core/rbac.py`,
`programas/mixins_dispositivos.py` y los servicios. Configuración manual del PM:
este carril **no modifica roles ni seeds**. Rol activo de programa DISPOSITIVOS;
`AsignacionDispositivo` concede alcance al rol. Una capacidad no concede por sí sola
una asignación, y `programa.configurar` amplía alcance sin otorgar otras capacidades.

| Rol | Capacidades a revisar/tildar | Alcance y condiciones |
|---|---|---|
| Admin del programa | ☐ `programa.configurar` ☐ `dispositivo.ver` ☐ `dispositivo.crear` ☐ `dispositivo.editar` ☐ `dispositivo.validar` ☐ `dispositivo.admitir` ☐ `dispositivo.egresar` ☐ `dispositivo.bitacora` ☐ `inspeccion.asignar` ☐ `ciudadano.ver` ☐ `ciudadano.crear` | Total en Dispositivos. Alta requiere además capacidad crear; no hace falta superusuario. |
| Operador institucional | ☐ `dispositivo.ver` ☐ `dispositivo.admitir` ☐ `dispositivo.egresar` ☐ `dispositivo.bitacora` ☐ `ciudadano.ver` ☐ `ciudadano.crear` | Asignación a su institución. ☐ `dispositivo.editar` solo si mantiene estructura o turnos. No necesita crear instituciones ni configurar programa. |
| Validador separado | ☐ `dispositivo.ver` ☐ `dispositivo.validar` | Asignación a instituciones que valida; configurar programa solo para alcance total. Editar si también corrige/envía. Separación obligatoria de funciones ❌ §3 «Permisos». |
| Coordinador | ☐ `inspeccion.asignar` ☐ `dispositivo.ver` | Instituciones cuyos edificios coordina. Asignar, reasignar, cancelar y revisar usan la misma capacidad. Sin ciudadano.ver ve la fila sin identidad en P4. |
| Agente de campo | ☐ `inspeccion.relevar` | Usuario activo con correo; asignación individual, externo al personal del edificio (289). No necesita becas.campo ni operación institucional. |
| Lector | ☐ `dispositivo.ver` ☐ `ciudadano.ver` si consulta personas/P7/P16 | Asignación institucional; sin escritura. P4 oculta nombres/DNI sin ciudadano.ver; P7/P16 exigen la capacidad. |
| Sin rol de Dispositivos | ☐ Comprobar ausencia de capacidades de Dispositivos/inspecciones | Las rutas de backoffice deben rechazar el acceso. No se usan nombres de grupos para autorizar. |

No se necesitan `programa.usuario.administrar` ni `programa.rol.administrar` para
estos recorridos. Los turnos se configuran por institución con `dispositivo.editar`.
El catálogo de motivos conserva su mantenimiento en Django Admin; P14 completa no entra.

| Aviso | Dónde aparece | Cómo se resuelve |
|---|---|---|
| Último resultado Alta | P4, rojo P2/P19 | Nuevo resultado no crítico; revisar no lo apaga. |
| Asignación pendiente vencida | P4/P19/P21 | Completar o cancelar; fecha anterior a hoy local, no el mismo día. |
| Institución activa sin turnos | P4 | Configurar al menos un turno activo. |
| Plaza fuera de servicio | P4/P5 | Volver a servicio desde su acción. |
| Reserva/préstamo vencido | P4 → P5 | Liberar; disponibilidad ya se recalcula por fecha. |

## 7. Lo que no se verificó y límites de entrega

- **App móvil y pruebas de integración reales entre repositorios:** siguen sin
  verificación de la APK, almacenamiento local, modo avión, conversión HEIC y cola
  de sincronización. Son promesas de §2, **no funciones excluidas por §3**. Los ✅ de
  campo certifican únicamente el contrato y comportamiento servidor. El PM/QA debe
  cerrar el bloque móvil antes de afirmar entrega completa de esa promesa.
- **Cronjobs instalados en ECOM:** se revisaron manifiestos/comandos, no instalación,
  ejecución efectiva ni correo. Los comandos existentes de Becas/Legajos no procesan
  AVISOS de Dispositivos. Por decisión PM, este MVP calcula avisos al consultar;
  no se promete un automatismo proactivo agregado en este carril.
- **MySQL 8 para toda la suite:** no ejecutado. MariaDB 10.11 focal y SQLite no equivalen
  a toda la matriz MariaDB 11/MySQL 8, ni a toda la suite sobre MariaDB.
- **Servicios externos reales y entorno productivo:** sin RENAPER con personas reales,
  sin comprobar límite multipart del ingress ECOM. No hay datos personales en esta matriz.
- **Revisión visual:** D1/D2 y los carriles entregaron capturas Chromium; GK modifica
  textos accesibles y la fuente del nombre, sin rehacer esas capturas. No se certifican
  Safari/Firefox, lectores de pantalla físicos, teclado virtual ni dark mode.
- Las pruebas temporales de los revisores y sus capturas viven fuera del repo; se
  conservan aquí sus conclusiones y límites. Los tests versionados y las validaciones
  de cierre de GK constan en el **Cambio 325** del registro. No se presenta un porcentaje
  global de «100 %»: apartamientos aprobados, recortes y verificación externa son distintos.

`mkdocs.yml` publica solo `docs/client/` (`docs_dir`). Las otras páginas internas de
Dispositivos tampoco están en ese nav: esta matriz permanece interna y no se agrega al sitio.
