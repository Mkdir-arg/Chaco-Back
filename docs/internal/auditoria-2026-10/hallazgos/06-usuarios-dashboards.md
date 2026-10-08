# 4.6 Usuarios, roles y dashboards (G1b, G2)

Fichas completas del dominio (pasada 3: G1b verificado por G2). Convenciones, `V-STD` y `V-UI`: README §0.
PoC: `poc/test_repro_usuarios.py`. Lo de la API REST de usuarios está en SEC-05/16/17; la toma de cuentas en SEC-03
(que absorbe G1b-01); clave provisoria del territorial y token de campo en SEC-26 (absorbe G1b-03 y G1b-04); el seed del
«Operador de backoffice» en OPS-06 (absorbe G2-02); `import_users_from_csv` en G2-05; el export del dashboard en G1b-11
(performance) y G2-01 (campos propios, dominio Becas).

| ID | Título | Sev. | Estado | Ola | Esf. | Avance 03-oct |
|---|---|---|---|---|---|---|
| G1b-02 | Capacidades «parciales» del programa se autootorgan las demás (contradice Cambio 20) | ALTA | CONF. test | 2 | M | ⬜ |
| G1b-05 | Operador no global deja cuentas activas sin rol, que entran al backoffice | MEDIA | CONF. test | 2 | S | ✅ |
| G1b-06 | Admin de programa borra en silencio capacidades globales del rol al guardarlo | MEDIA | CONF. test | 2 | S | ⬜ |
| G2-03 | «Cambiar contraseña» abierto para cualquier sesión y sin pedir la clave actual | MEDIA | CONF. test | 2 | S | ✅ |
| G1b-07 | Desactivar el último rol admin: 500 (programa) o sistema sin admin (global) | BAJA | CONF. test | 2 | S | ✅ |
| G1b-08 | Claves tipeadas por un operador sin validadores ni cambio obligatorio | BAJA | CONF. lectura | 2 | S | ✅ |
| G1b-09 | «Último administrador» salteable con dos operaciones simultáneas | BAJA | PLAUSIBLE | 7 | M | ⬜ |
| G1b-10 | Alta rápida: 500 ante colisión en carrera | BAJA | CONF. ajustado | 7 | S | ⬜ |
| G1b-12 | Dashboard de Becas: período sin tope y `?recalcular=1` sin freno | BAJA | CONF. ajustado | 4 | S | ✅ |
| G2-04 | Inicio: los contadores no miden lo que dicen sus etiquetas | BAJA | CONF. lectura | 5 | S | ✅ |
| G2-06 | El login pide «Tu correo electrónico» pero autentica por `username` | BAJA | CONF. lectura | 5 | S | ✅ |
| R0b-01 | `user_form.html` no muestra el `help_text` de los campos que SEC-03 bloquea | BAJA (MINOR) | revisión Ola 0 (2ª tanda) | 2 (Usuarios) | S | ✅ |
| R0b-02 | SEC-03: un rol desactivado no cuenta como fuera de alcance | BAJA (MINOR) | revisión Ola 0 (2ª tanda) | 2 (Usuarios) | S | ✅ |
| R0b-03 | P-04 no cubre roles Backoffice/Sistema sin programa | BAJA (MINOR) | revisión Ola 0 (2ª tanda) | 2 (Usuarios; antes de R0b-12) | S | ✅ |
| R0b-10 | Listado de usuarios: editar y activar/desactivar visibles para usuarios no gestionables | BAJA (MINOR) | revisión Ola 0 (2ª tanda) | 2 (Usuarios) | S | ✅ |
| R0b-12 | Correr P-04 (ampliado por R0b-03) en PRD | — (operativo, PM) | revisión Ola 0 (2ª tanda) | PM | — | ⬜ |

---

## ALTA

### G1b-02 · Separar «usuarios del programa» y «roles del programa» no impide escalar: cada capacidad permite darse la otra
**Severidad:** ALTA (sube desde MEDIA) · **Estado:** CONFIRMADO con test (`G1b02EscaladaDentroDelProgramaTests`, 2 tests) · **Origen:** G1b-02 · **Ola:** 2 (mismo PR que SEC-07) · **Esfuerzo:** M · **Decisión:** —
- **Ubicación:** `users/forms/roles.py:93-100`, `:138-147` (un operador no global puede tildar cualquier capacidad de módulo con alcance programa, incluidas `programa.usuario.administrar`, `programa.rol.administrar` y `programa.configurar`, `core/rbac.py:45-54`); `users/selectors/roles.py:85-96` (puede editar **su propio** rol); `users/forms/__init__.py:205-207` (el combo de roles ofrece todos los roles del programa sin mirar capacidades).
- **Escenario (reproducido):** (a) quien solo tiene `programa.rol.administrar` edita su propio rol, se tilda `programa.usuario.administrar` y `programa.configurar`, y pasa de 302 a **200** en `/usuarios/`; (b) quien solo tiene `programa.usuario.administrar` se asigna un rol de Becas que trae `programa.rol.administrar` y `becas.programa.administrar`. Contradice el Cambio 20 («se otorgan por separado»); se encadena con SEC-07 (`programa.configurar`) y con SEC-03 (toma de cuentas).
- **Propuesta:**
  1. `RolForm.clean` (no global): no permitir tildar capacidades que el operador no tiene **en ese programa**; `CAPS_ADMIN_PROGRAMA` y `programa.configurar` solo asignables por un operador global (salvo la excepción de DISPOSITIVOS de SEC-07).
  2. `users/selectors/roles.py`: prohibir que un operador no global edite los roles que él mismo tiene.
  3. `_roles_asignables_queryset(operador)`: excluir roles cuyas capacidades no sean subconjunto de las del operador en ese programa.
  4. Ojo con el alcance de admin de programa (`CAPS_ADMIN_PROGRAMA`, que se mueve en varios lugares a la vez: ver memoria del proyecto «Alcance de admin de programa (RBAC)»).
- **Tests a agregar:** los dos de la PoC invertidos (`test_admin_roles_no_se_da_admin_usuarios_editando_su_rol`, `test_admin_usuarios_no_se_asigna_rol_con_mas_capacidades`); `test_admin_global_sigue_asignando_cualquier_rol`.
- **Verificación:** V-STD + `manage.py test users`. Pre-chequeo P-06 (README §3).
- **Dependencias:** SEC-07 y SEC-06 (mismo `RolForm.clean`); SEC-03.

## MEDIA

### G1b-05 · Un operador no global deja cuentas activas sin rol, que entran al backoffice y desaparecen de su listado
**Severidad:** MEDIA · **Estado:** CONFIRMADO con test (`G1b05CuentaFantasmaTests`) · **Origen:** G1b-05 · **Ola:** 2 · **Esfuerzo:** S
- **Ubicación:** `users/forms/__init__.py:326-337`, `:410-421` (`groups` con `required=False`); `users/services/admin.py:77-82`; `users/selectors/usuarios.py:55-65`; `users/forms/auth.py:48` (el bloqueo de login solo aplica si tiene `becas.campo`).
- **Escenario (reproducido):** el admin de Dispositivos le destilda el único rol a un operador: queda **activo y sin roles**, **desaparece** de la lista de ese admin (no puede reactivarlo ni desactivarlo), el login es válido y `/inicio/` responde 200. Es el camino natural de «sacar a alguien del programa». Agrava SEC-14 y SEC-11 (todo lo que solo exige `login_required`).
- **Propuesta:** en el `clean` de los dos forms, para operador no global, exigir al menos un rol en su alcance; alternativa: si `groups` queda vacío, `is_active=False` en el servicio con mensaje explícito. Contar las cuentas que ya están así con P-07.
- **Tests:** el de la PoC invertido (o: la cuenta queda inactiva y el admin sigue viéndola).

**Resolución:** ✅ Resuelto en #631 (Cambio 181, Ola 2 PR 2), 08-10-2026 — se aplicó la **primera**
opción: `_validar_al_menos_un_rol` en el `clean` de los dos forms del ABM. Un operador no global que
deja la selección vacía recibe un error de campo que además dice cuál es el camino correcto
(«desactivá el usuario»), y ese camino quedó cubierto con su propio test: desactivar conserva el rol,
así que la cuenta sigue apareciendo en el listado y se puede reactivar. En la **edición** la regla
mira los roles finales, no los tildados: si el usuario conserva roles fuera del alcance del operador
—que el guardado acotado no toca— la cuenta no queda huérfana y el guardado pasa. El admin global
queda afuera de la regla a propósito: a él la cuenta sin roles no se le esconde. **Test permanente:**
`users.tests.test_usuarios_ola2_pr2.G1b05CuentaSinRolTests.test_admin_programa_no_puede_dejar_la_cuenta_sin_roles`
(+ `test_el_camino_correcto_sigue_abierto_desactivar_la_cuenta`, `test_el_alta_de_un_admin_de_programa_exige_un_rol`,
`test_el_admin_global_sigue_pudiendo_dejarla_sin_roles` y la batería por rol: anónimo, sin rol, admin
de otro programa y superusuario). **P-07 sigue pendiente del PM:** este PR cierra la puerta, no limpia
las cuentas que ya quedaron así.

### G1b-06 · El admin de programa borra en silencio las capacidades globales del rol al guardarlo
**Severidad:** MEDIA · **Estado:** CONFIRMADO con test (`G1b06CapsGlobalesBorradasTests`) · **Origen:** G1b-06 · **Ola:** 2 · **Esfuerzo:** S
- **Ubicación:** `users/forms/roles.py:138-147` (filtra `cleaned["capacidades"]` a las de programa); `users/services/roles.py:16-20`, `:95` (`group.permissions.set(...)` reemplaza todo).
- **Escenario (reproducido):** el admin global agrega `ciudadano.ver` a un rol de Becas; el admin de roles de Becas lo guarda cambiando solo la descripción y `ciudadano.ver` desaparece.
- **Propuesta:** en `RolesAdminService.actualizar`, `finales = (actuales − permitidas_operador) ∪ seleccionadas`.
- **Tests:** el de la PoC invertido.

### G2-03 · «Cambiar contraseña obligatorio» está abierto para cualquier sesión y no pide la clave actual
**Severidad:** MEDIA · **Estado:** CONFIRMADO con test (`G2CambioClaveSinClaveActualTests`) · **Origen:** G2-03 · **Ola:** 2 (con SEC-26) · **Esfuerzo:** S
- **Ubicación:** `users/views/auth.py:41-62` (`LoginRequiredMixin` + `SetPasswordForm`, sin chequear `debe_cambiar_contrasena`); `users/urls.py` (`cambiar-contrasena/`).
- **Escenario (reproducido):** un usuario con `debe_cambiar_contrasena=False` hace POST a `/cambiar-contrasena/` con `new_password1/2` → 302 y la clave cambia sin conocer la actual. Con el XSS de SEC-08 (todas las páginas) o una sesión abierta en una PC compartida, un `fetch` silencioso toma la cuenta para siempre (no hace falta el email, como en SEC-03).
- **Propuesta:** en `dispatch`, si `not request.user.profile.debe_cambiar_contrasena`, redirigir al inicio (o usar `PasswordChangeForm`, que pide la clave actual). El cambio voluntario va por un flujo con clave actual: hoy existe en `django.contrib.auth.urls`, que SEC-26 propone quitar, así que hay que dar uno propio en el mismo PR. Ojo con la trampa del `Profile` cacheado (Cambio 37).
- **Tests:** el de la PoC invertido (302 al inicio y la clave intacta) y que con `debe_cambiar_contrasena=True` siga andando (`users/tests/test_credenciales.py`).
- **Dependencias:** SEC-08, SEC-26.

**Resolución:** ✅ Resuelto en #631 (Cambio 181, Ola 2 PR 2), 08-10-2026 — `dispatch` de
`CambioContrasenaObligatorioView` sale por redirect si el Profile no tiene `debe_cambiar_contrasena`.
El `fetch` silencioso ya no cambia nada: el 302 sobre un POST se convierte en GET, así que no hay
reenvío de la clave nueva. **Desvío de la ficha:** el redirect no va al inicio sino a la pantalla de
cambio **voluntario**, que este mismo PR crea (`users:cambiar_contrasena`,
`user/cambiar_contrasena.html`, `PasswordChangeForm`): quien entró a propósito a cambiar su clave
llega adonde quería, y quien no, igual no cambió nada. Esa pantalla es la que SEC-26 debía, porque el
mismo PR saca `django.contrib.auth.urls` de la raíz y con él el `/password_change/` que contestaba
sin plantilla; es también la única entrada nueva del shell (menú del avatar). El `Profile` lo lee de
la caché que dejó `BackofficeSingleSessionMiddleware`, así que el gate no agrega consultas (Cambio 37
y RED-52). **Test permanente:**
`users.tests.test_credenciales_ola2_pr2.G2CambioClaveSinClaveActualTests.test_una_sesion_sin_clave_provisoria_no_cambia_la_clave_sin_la_actual`
(+ `test_con_la_clave_provisoria_la_pantalla_sigue_andando`, `test_el_cambio_voluntario_exige_la_clave_actual`,
`test_el_cambio_voluntario_con_la_clave_actual_funciona_y_no_pierde_la_sesion`, y la batería por rol:
anónimo, sin rol y superusuario).

## BAJA

### G1b-07 · Desactivar el último rol admin: 500 si es de programa; sistema sin admin si es global
**Severidad:** BAJA (mitigado: `seed_rbac` asigna «Administrador», protegido, a los superusuarios) · **Estado:** CONFIRMADO + AMPLIADO (`G1b07ToggleRolSinAdminTests`, 2 tests) · **Origen:** G1b-07 · **Ola:** 2 · **Esfuerzo:** S
- **Ubicación:** `users/services/roles.py:119-132` (solo `asegurar_admin_restante(programa=...)`); `users/views/roles.py:159-163` (solo captura `RolProtegidoError`).
- **Escenario (reproducido):** (1) desactivar el único rol admin de un programa sin superusuario activo → `SinAdministradorProgramaError` sin capturar → **500**; (2) desactivar un rol global no protegido con `usuario.administrar` deja `usuarios_que_administran()` vacío y responde 302.
- **Propuesta:** `toggle_activo` llama también `rbac.asegurar_admin_restante()` (global); la vista captura `SinAdministradorError`/`SinAdministradorProgramaError` y muestra el mensaje.
- **Tests:** los dos de la PoC invertidos.

**Resolución:** ✅ Resuelto en #631 (Cambio 181, Ola 2 PR 2), 08-10-2026 — las dos mitades.
`RolToggleActivoView` captura `rbac.SinAdministradorError`, que es la base de
`SinAdministradorProgramaError`, así que el 500 pasa a ser el mismo aviso que ya daban editar y
borrar; y `toggle_activo` corre también el check **global**. **Desvío de la ficha:** el check global
no corre en toda desactivación sino solo cuando el rol otorga alguna capacidad de
`CAPS_ADMINISTRACION` (`_administra_el_sistema`, la contracara de `_programa_que_administra`).
Desactivar un rol operativo no puede dejar al sistema sin admins, y correrlo igual tenía un efecto
perverso medible: en una base que ya está sin administradores —un seed a medias, un restore— pasaba a
no poder desactivarse **ningún** rol, con un mensaje que no explica nada. **Test permanente:**
`users.tests.test_usuarios_ola2_pr2.G1b07ToggleRolSinAdminTests.test_desactivar_el_unico_rol_admin_de_un_programa_avisa_y_no_rompe`
(+ `test_desactivar_el_unico_rol_admin_global_no_deja_el_sistema_sin_nadie`,
`test_con_otro_admin_global_la_desactivacion_sigue_andando`,
`test_un_rol_operativo_se_desactiva_sin_consultar_administradores`, `test_sin_capacidad_y_anonimo_no_togglean`).

### G1b-08 · Claves tipeadas por un operador sin validadores ni cambio obligatorio
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Origen:** G1b-08 · **Ola:** 2 (con SEC-26) · **Esfuerzo:** S
- **Ubicación:** `users/forms/__init__.py:313-325`, `:400-408` (`CharField` sin `validate_password`); `users/services/admin.py:65-67` (`set_password` sin marcar `debe_cambiar_contrasena`).
- **Propuesta:** `clean_password` con `validate_password`; al fijar la clave de **otro** usuario, `debe_cambiar_contrasena=True` (cuidado con el `Profile` cacheado, Cambio 37).

**Resolución:** ✅ Resuelto en #631 (Cambio 181, Ola 2 PR 2), 08-10-2026 — `_validar_clave_tipeada`
corre `validate_password` en el `clean` de los dos forms del ABM (vacío sigue significando «no
cambiar», así que no valida nada de más), y `_marcar_cambio_obligatorio` pone
`debe_cambiar_contrasena=True` cuando la clave la tipeó **otro**. Se escribe sobre el Profile
cacheado y se sincroniza `fields_cache`, que es lo que la segunda parte de RED-52 —en este mismo
PR— deja de arreglar por accidente. **Dos detalles code-first que la ficha no tenía:** (a) si el
operador se cambia la clave a sí mismo desde el ABM no se marca nada, porque ya la conoce; (b) el
campo `password` del form de **edición** existe pero `user_form.html` no lo renderiza (solo lo
muestra en el alta), así que por pantalla esa clave hoy se tipea únicamente al dar de alta sin
correo —el validador igual hace falta, porque el campo sigue aceptando el POST—.

**Corregido en la ronda 2: el usuario de campo.** La marca `debe_cambiar_contrasena` la cobra el
backoffice, y a quien solo tiene `becas.campo` el backoffice no le pide nada —el login web lo rechaza
y `/api/becas/auth/token/` no mira el flag—, así que sobre él quedaba puesta y no la hacía cumplir
nadie: la clave que tipeaba el operador le quedaba vigente para siempre. Es el mismo agujero que D-26
(b) cerró para el alta **con** correo mandando un link de reseteo, y que por la puerta de al lado
—alta **sin** correo— seguía abierto. Se cierra por donde corresponde, que es el alta y no la marca:
`_validar_correo_de_entrega` le **exige correo a un usuario de campo** (`rbac.roles_solo_campo`, la
misma pregunta que `es_solo_campo` pero sobre los roles tildados, porque en el alta el usuario todavía
no existe), ya que el link es la única vía por la que le puede llegar una clave que el operador no
conozca. Para el resto nada cambia: sin correo la clave la sigue tipeando el operador y vale un solo
ingreso. La marca se escribe igual sobre el usuario de campo, por si mañana suma un rol de backoffice.

**Cerrado en la ronda 3: la edición era el camino de atrás.** Con el alta tapada quedaba una ruta de
dos pasos hacia el mismo estado: se daba de alta un usuario **mixto** sin correo —legítimo, porque
tiene otra capacidad y el backoffice sí le va a pedir cambiar la clave al entrar— y después se lo
editaba destildándole el rol que no era de campo. La cuenta terminaba solo-campo, sin correo y con la
clave que tipeó el operador, vigente para siempre. `_validar_correo_de_entrega_al_editar` rechaza esa
edición con el mismo mensaje del alta, y mira la **transición**, no el estado final: los territoriales
sin correo que ya existen se tienen que poder seguir editando (cambiarle el nombre a uno de ellos
sigue andando), porque si no quedaban congelados hasta que alguien les cargara un correo. Los roles
con los que la cuenta queda se calculan como los calcula el guardado —un admin de programa conserva
los roles fuera de su alcance—, y la regla de la clave del alta no se aplica acá: en la edición el
campo vacío significa «no la cambies». En el **alta rápida** de Becas el modal pasa a marcar el correo
como obligatorio cuando el tipo es `territorial`, y la ayuda de la clave dice lo que de verdad pasa:
al territorial le llega un enlace para fijarla él.

**Test permanente:**
`users.tests.test_usuarios_ola2_pr2.G1b08ClaveTipeadaTests.test_fijarle_la_clave_a_otro_obliga_a_cambiarla`
(+ `test_el_alta_rechaza_una_clave_que_no_pasa_los_validadores`,
`test_la_edicion_rechaza_una_clave_que_no_pasa_los_validadores`,
`test_cambiarse_la_propia_clave_desde_el_abm_no_obliga_a_nada`, `test_una_edicion_sin_clave_no_toca_el_flag`;
`users.tests.test_credenciales_ola2_pr2.AltaDeUsuarioDeCampoTests` ×5, encabezada por
`test_el_alta_de_un_usuario_de_campo_sin_correo_se_rechaza`;
`users.tests.test_credenciales_ola2_pr2.EdicionHaciaUsuarioDeCampoTests` ×4, encabezada por
`test_sacarle_el_rol_de_backoffice_a_un_mixto_sin_correo_se_rechaza` y con
`test_un_territorial_sin_correo_que_ya_existia_se_sigue_pudiendo_editar` como contracara).

### G1b-09 · «Último administrador» salteable con dos operaciones simultáneas
**Severidad:** BAJA · **Estado:** PLAUSIBLE (sin repro de concurrencia) · **Origen:** G1b-09 · **Ola:** 7 · **Esfuerzo:** M
- **Ubicación:** `core/rbac.py:745-770` (`exists()` sin bloqueo); `users/views/admin.py:157-165`; `users/services/admin.py:203-205`.
- **Propuesta:** `SELECT … FOR UPDATE` sobre las `RolMeta` admin dentro de la transacción del toggle, o `GET_LOCK('datanach_ultimo_admin', 5)`.

### G1b-10 · Alta rápida: 500 ante colisión en carrera
**Severidad:** BAJA · **Estado:** CONFIRMADO-AJUSTADO (el `ModelForm` ya valida `username` único y el `clean` el DNI: el 500 solo sale en una carrera sobre `auth_user.username` o `users_profile.dni`) · **Origen:** G1b-10 (el texto crudo de la excepción está en SEC-36) · **Ola:** 7 · **Esfuerzo:** S
- **Ubicación:** `users/views/quick_create.py:64`.
- **Propuesta:** capturar `IntegrityError` → error de campo (o JSON 409).

### G1b-12 · Dashboard de Becas: período custom sin tope y `?recalcular=1` saltea la caché
**Severidad:** BAJA · **Estado:** CONFIRMADO + AJUSTADO · **Origen:** G1b-12 · **Ola:** 4 · **Esfuerzo:** S
- **Ubicación:** `programas/forms_reportes.py:121-126` (sin techo); `programas/services/dashboard_becas.py:281` (`_serie_semanal`), `:303-312`, `:326` (`_variacion`); `programas/views/dashboard_becas.py:83`.
- **Escenario:** `desde=2000-01-01&hasta=3999-12-31` arma ~104k semanas y las cachea; si la ventana es más larga que la distancia de `desde` al año 1, `_variacion` tira `OverflowError`, que la vista devuelve como 500 con mensaje.
- **Propuesta:** `hasta <= hoy` y rango máximo de 5 años en el form; ignorar `recalcular` si la entrada de caché tiene menos de N segundos.

**Resolución:** ✅ Resuelto en #NNN (Cambio 189, Ola 4 PR 5), 08-oct-2026 — la propuesta tal cual. El período
personalizado rechaza `hasta` posterior a hoy y una ventana mayor a `MAX_ANIOS_PERIODO = 5` años (`_hace_anios` tolera
el 29 de febrero), así que la variación contra el período anterior no puede irse antes del año 1 y el `OverflowError`
deja de existir por construcción: `desde=2000-01-01&hasta=3999-12-31` devolvía **500** y ahora devuelve 400 con el
error del filtro. `?recalcular=1` se atiende como mucho **uno cada 30 s por recorte** (`recalculo_permitido`, un
`cache.add` atómico en Redis y en LocMem); el resto se sirve de la caché, que por RN-17 nunca tiene más de 5 minutos.
Si la caché no responde se recalcula, que es lo que pasaba antes. **DECISIÓN CLIENTE: 30 s** —la ficha no fija N; es un
décimo del TTL del tablero—.
**Test permanente:** `programas.tests.test_dashboard_exports.PeriodoYRecalculoTests`
(`test_el_periodo_personalizado_no_puede_terminar_despues_de_hoy`,
`test_el_periodo_personalizado_tiene_techo_de_cinco_anios`, `test_una_ventana_imposible_da_400_y_no_un_500`,
`test_recalcular_se_atiende_una_vez_por_ventana`, `test_vencido_el_freno_recalcular_vuelve_a_valer` y
`test_el_freno_no_mezcla_dos_recortes`).


### G2-04 · Inicio: los contadores no miden lo que dicen sus etiquetas
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Origen:** G2-04 · **Ola:** 5 · **Esfuerzo:** S · **Decisión:** D-G204
- **Ubicación:** `core/views/public.py:66-84`; `templates/inicio.html:470-476`, `:504-505`, `:521-522`; `dashboard/utils.py:40-83`; `dashboard/api_views/__init__.py:203`, `:221`.
- **Evidencia:** «Total ciudadanos ↑N nuevos este mes» = `InscripcionPrograma` del mes, no ciudadanos nuevos; «Seguimientos hoy: X · X actividades hoy» es el mismo número dos veces (inscripciones con `fecha_inscripcion = hoy`); «usuarios activos hoy» = `last_login` de las últimas 24 h, incluye ciudadanos del portal; `tendencias_datos` arma `range(dias)` desde `hoy - dias`: el gráfico **nunca incluye hoy**; nada mira Becas (`Formulario`), donde está casi toda la operación.
- **Propuesta:** corregir etiquetas («inscripciones este mes», sacar la línea duplicada, «ingresaron en las últimas 24 h»), filtrar `last_login` a usuarios de backoffice, `range(dias + 1)` (o `fecha_inicio = hoy - (dias - 1)`); D-G204: ¿el inicio muestra indicadores de Becas? El «hoy» UTC es BEC-18.
- **Tests:** contexto de `inicio_view` con 1 ciudadano nuevo y 2 inscripciones del mes muestra las dos cifras por separado; `tendencias_datos` con `labels[-1]` = hoy. V-UI.

**Resolución:** ✅ Resuelto en el PR #609 (Cambio 161), 07-10-2026 — los cuatro defectos, los cuatro de rótulo o
de ventana. (1) «↑N nuevos este mes» pasa a «inscripciones este mes», que es lo que `registros_mes` cuenta.
(2) `actividad_hoy` **se borra** del contexto y del template: era `seguimientos_hoy` con otro nombre, y el pie de
esa tarjeta ahora explica el número de arriba («inscripciones con fecha de hoy») en vez de repetirlo. (3)
`usuarios_activos` pasa a `ingresos_24h`, **excluye a los ciudadanos del portal** (`groups__name` ≠ `Ciudadanos`,
el marcador de identidad de `core.rbac.es_ciudadano_portal`) y el rótulo dice «N ingresos al backoffice en las
últimas 24 h»: `last_login` es el último ingreso, no actividad sostenida. La clave de caché pasa a
`home:ingresos_backoffice_24h` para que las entradas con la semántica vieja no sobrevivan al deploy —de paso
deja de pisarse con la que escribe la vista muerta `DashboardView`—. (4) `tendencias_datos` arranca la serie en
`hoy - (dias - 1)`: el último punto es hoy y el selector sigue dando la cantidad de barras que promete.
**Ronda 2 — la cuarta tarjeta tampoco medía lo que decía.** «Legajos activos · de N legajos en total» salía de
`dashboard.utils.contar_legajos()`, que agrega **`InscripcionPrograma`**, no `LegajoAtencion`. Con 4 legajos de
atención (3 activos) y 5 inscripciones en PENDIENTE, el inicio decía «0 · de 5» y `/legajos/reportes/` decía
«4 · 3» en la misma sesión: dos pantallas contradiciéndose, y ninguna rota —medían cosas distintas bajo el
mismo rótulo—. Manda el rótulo: la tarjeta pasa a `LegajoAtencion` con la **misma** definición de «activo» que
usa reportes (*todo lo que no esté `CERRADO`*, así que ABIERTO, EN_SEGUIMIENTO y DERIVADO cuentan), y esa
definición deja de estar escrita dos veces: vive en `legajos/selectors/legajos.py`
(`legajos_abiertos`, `resumen_legajos_atencion`) y la consumen las dos pantallas.
`contar_legajos()` **no se tocó** —la usa `dashboard.views.home.DashboardView` (vista tapada, RED-78) y RED-51
tiene dos tests escritos sobre que `stats_legajos` agrega inscripciones—: el contador nuevo es
`contar_legajos_atencion()`, con su clave `stats_legajos_atencion`, que el receiver de
`legajos/signals/core.py` ya invalida en cada alta o baja de legajo. Mismo presupuesto de consultas: el
`aggregate` resuelve total y activos en una, igual que el anterior.
**Efecto visible:** hoy en PRD no hay legajos de atención cargados, así que la tarjeta va a mostrar **0**. Es el
número correcto; el que se veía antes era el de otra cosa.
**D-G204 aplicado:** se corrigen las etiquetas; que el inicio muestre indicadores de Becas sigue siendo un
requerimiento aparte.
**Evidencia nueva para BEC-18, encontrada por el CI:** el primer test de la serie afirmaba «una inscripción de
hoy entra en el último bucket» y **pasaba en Windows y fallaba en el CI**. La causa no es G2-04:
`InscripcionPrograma.fecha_inscripcion` es `DateField(auto_now_add=True)` y el `pre_save` de Django **descarta
el valor que se le pase** para escribir `datetime.date.today()`, la fecha naíf del proceso; en Linux
`Settings.__init__` hace `os.environ["TZ"] = TIME_ZONE; time.tzset()` (`django/conf/__init__.py:195-205`), así
que esa fecha es la de **Argentina**, mientras que la ventana de la serie se arma con `timezone.now().date()`,
que es la de **UTC**. Entre las 21 y las 24 de Argentina las dos difieren en un día, y una inscripción recién
creada cae un bucket antes del que el gráfico rotula como hoy. En Windows `time.tzset` no existe, Django saltea
el bloque y el desfase no se ve: por eso la suite local daba verde. Es exactamente **BEC-18** («el hoy UTC», Ola 3).
**Resuelto para este uso en la ronda 2:** la ventana la arma `timezone.localdate()`, que es lo que propone la
ficha BEC-18, así que los dos relojes coinciden y el `update()` del test se fue. Entre las 21 y las 24 de
Argentina el último bucket rotulaba «mañana» y salía siempre en cero. El resto de los «hoy» UTC del sistema
siguen abiertos en BEC-18. **Test permanente:**
`core.tests.test_inicio_contadores_ola5.ContextoDelInicioTests.test_el_contexto_no_repite_el_mismo_numero_en_dos_claves`
(+ `test_los_ingresos_no_cuentan_a_los_ciudadanos_del_portal`, `test_los_ingresos_viejos_quedan_fuera_de_la_ventana`,
`EtiquetasDelInicioTests` ×3, `TendenciasIncluyenHoyTests` ×5 —incluido
`test_la_ventana_usa_la_fecha_local_y_no_la_utc`, con el reloj congelado a las 23:30 ART— y, por la cuarta
tarjeta, `core.tests.test_inicio_legajos_ola5_pr7` ×8 (`ReproDelRevisorTests`,
`UnaSolaDefinicionDeActivoTests`, `ContadorDeInscripcionesIntactoTests`); incluido
`test_antes_el_ultimo_dia_quedaba_fuera_de_la_ventana`, que fija el borde opuesto: el primer bucket es
`hoy - (dias - 1)`, así que la serie no se corrió un día para atrás al arreglarla).

### G2-06 · El login pide «Tu correo electrónico» pero autentica por `username`
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Origen:** G2-06 · **Ola:** 5 · **Esfuerzo:** S
- **Ubicación:** `users/templates/user/login.html:146`, `:155`; `users/forms/auth.py:23`; sin `AUTHENTICATION_BACKENDS` propio (ModelBackend por username); el ABM (`user_form.html:156`) y el alta rápida (`_alta_rapida_modal.html:27`) piden «Nombre de usuario» libre; el correo de credenciales informa «Usuario: {{ username }}».
- **Propuesta:** rotular «Usuario» (lo más chico; default). Alternativa: backend que acepte email **solo si es único**, lo que exige validar unicidad del email en `users/forms/__init__.py` (hoy no). V-UI.

**Resolución:** ✅ Resuelto en el PR #609 (Cambio 161), 07-10-2026 — **default aplicado**: el label pasa a «Tu
usuario *», el placeholder a «Ingresá tu usuario» y el `invalid_login` de `UsuariosAuthenticationForm` a
«Credenciales inválidas. Verificá tu usuario y contraseña». No se tocó el backend: sigue el `ModelBackend` por
`username`, que es lo que el ABM y el alta rápida dan de alta. **Test permanente:**
`core.tests.test_front_ola5_pr7.LoginRotuladoPorUsuarioTests.test_el_campo_se_rotula_usuario`
(+ `test_el_placeholder_no_pide_un_correo`, `test_el_error_de_credenciales_no_habla_de_correo`).

## Seguimientos de la revisión de la Ola 0, segunda tanda (agregados el 03-oct-2026)

Observaciones MINOR del revisor de #539 (SEC-03, Cambio 110) y un seguimiento operativo. Las líneas son de
`origin/development @ 719dc0a`. Van juntas en el PR 2 de la Ola 2 (*Usuarios*).

### R0b-01 · `user_form.html` no muestra el `help_text` de los campos que SEC-03 bloquea
**Severidad:** BAJA (MINOR del revisor de #539) · **Estado:** CONFIRMADO (lectura) · **Origen:** revisión de la Ola 0, 2ª tanda · **Ola:** 2 (PR 2, Usuarios) · **Esfuerzo:** S
- **Ubicación:** `users/forms/__init__.py:476-486` (deshabilita `username`, `email` y `password` y les pone el aviso en `help_text`); `users/templates/user/user_form.html:156-164` y `:205-207` renderizan label, campo y errores, nunca `help_text`.
- **Escenario:** el admin de programa ve los campos grises sin saber por qué; el aviso nunca llega a la pantalla.
- **Propuesta:** renderizar `{{ form.<campo>.help_text }}` debajo de cada campo (con el estilo de ayuda del sistema de diseño), o un aviso único arriba del bloque cuando `not form.credenciales_editables`. V-UI.
- **Test:** GET de la edición de un usuario multiprograma por un admin de programa contiene el texto del aviso.

**Resolución:** ✅ Resuelto en #631 (Cambio 181, Ola 2 PR 2), 08-10-2026 — `user_form.html` renderiza
el `help_text` de `username`, `email` y `password` con la pieza de ayuda del sistema (`mt-1 text-xs
text-body-subtle`, la misma de `components/_field.html`), condicionada a que el campo tenga ayuda:
en el alta no aparece nada y en la edición bloqueada aparece el aviso de SEC-03 debajo de cada campo
gris. Se eligió el `help_text` por campo y no un aviso único arriba del bloque porque es el texto que
el form **ya** escribe y así no quedan dos lugares diciendo lo mismo. **Test permanente:**
`users.tests.test_usuarios_ola2_pr2.R0b01AvisoDeCredencialesTests.test_el_formulario_muestra_por_que_el_usuario_y_el_correo_estan_grises`
(+ `test_con_todos_los_roles_en_alcance_no_hay_aviso`).

### R0b-02 · SEC-03: un rol desactivado no cuenta como fuera de alcance
**Severidad:** BAJA (MINOR del revisor de #539) · **Estado:** CONFIRMADO (lectura) · **Origen:** revisión de la Ola 0, 2ª tanda · **Ola:** 2 (PR 2, Usuarios) · **Esfuerzo:** S
- **Ubicación:** `users/selectors/usuarios.py:145-147` (`puede_gestionar_credenciales` hace `.exclude(meta__activo=False)`: un rol inactivo de otro programa no frena).
- **Escenario:** el admin de Becas cambia clave y correo de un usuario que tiene, además, un rol **desactivado** de admin de Dispositivos; si después alguien reactiva ese rol, el usuario recupera el acceso a Dispositivos con credenciales que puso el admin de Becas (el mismo vector de G1b-01, diferido).
- **Propuesta:** contar los roles inactivos como fuera de alcance (sacar el `exclude`), o fijar la decisión contraria en `requerimientos.md` con este escenario.
- **Test:** usuario con rol de Becas + rol inactivo de otro programa → el admin de Becas no edita credenciales.

**Resolución:** ✅ Resuelto en #631 (Cambio 181, Ola 2 PR 2), 08-10-2026 — `puede_gestionar_credenciales`
pasa a comparar contra un alcance propio, `alcance_roles_ids_credenciales`, que son los roles de los
programas que el operador administra **sin filtrar por `activo`**. **Desvío de la ficha:** la
propuesta literal era «sacar el `exclude`», y eso hacía además que un rol desactivado **del propio
programa** sacara de alcance: un admin de Becas no podía tocar las credenciales de su propio usuario
porque alguien le había desactivado un rol de Becas. El criterio que queda separa las dos preguntas
—qué puede **asignar** (solo roles activos, `alcance_roles_ids`, sin cambios) y qué roles **no lo
exceden** (los de sus programas, activos o no)—, que es lo que el escenario de la ficha describe.
**Test permanente:**
`users.tests.test_usuarios_ola2_pr2.R0b02RolDesactivadoFueraDeAlcanceTests.test_un_rol_inactivo_de_otro_programa_frena_las_credenciales`
(+ `test_un_rol_inactivo_del_propio_programa_no_frena_nada`, `test_el_admin_global_no_tiene_restriccion`).

### R0b-03 · P-04 no cubre roles Backoffice/Sistema sin programa
**Severidad:** BAJA (MINOR del revisor de #539) · **Estado:** CONFIRMADO (lectura) · **Origen:** revisión de la Ola 0, 2ª tanda · **Ola:** 2 (PR 2, Usuarios; conviene hacerlo antes de R0b-12) · **Esfuerzo:** S
- **Ubicación:** README §3, P-04: la primera consulta hace `JOIN programas_programa` (descarta los roles sin programa) y la segunda `JOIN users_rolmeta` (descarta los grupos sin `RolMeta`, que `puede_gestionar_credenciales` cuenta como fuera de alcance).
- **Propuesta:** `LEFT JOIN` a `programas_programa` y a `users_rolmeta` y listar, por usuario activo con algún rol de programa, cuántos roles de categoría Backoffice/Sistema (programa nulo) y cuántos grupos sin `RolMeta` tiene: son las cuentas cuyas credenciales el admin de programa dejó de poder tocar con SEC-03.

**Resolución:** ✅ Resuelto en #631 (Cambio 181, Ola 2 PR 2), 08-10-2026 — P-04 reescrita en el
README §3 con los dos `LEFT JOIN` y columnas nuevas `roles_sin_programa` y `roles_sin_meta`. Se le
sumó `roles_desactivados`, que la ficha no pedía pero que R0b-02 vuelve relevante en el mismo
release: desde este PR un rol desactivado de otro programa también saca de alcance, así que esas
cuentas entran en la misma lista que el PM tiene que revisar. Es SQL de solo lectura: lo corre el PM
(R0b-12), no este PR. **Test permanente:**
`core/tests/test_contrato_auditoria.py::PrechequeoP04Tests.test_las_dos_consultas_llegan_a_rolmeta_y_a_programa_con_left_join`
(+ `test_la_segunda_consulta_lista_las_cuentas_que_quedaban_invisibles`): la ficha no deja código, así
que el candado es sobre el README, que es su única superficie.

### R0b-10 · Listado de usuarios: editar y activar/desactivar visibles para usuarios no gestionables
**Severidad:** BAJA (MINOR del revisor de #539) · **Estado:** CONFIRMADO (lectura) · **Origen:** revisión de la Ola 0, 2ª tanda · **Ola:** 2 (PR 2, Usuarios) · **Esfuerzo:** S
- **Ubicación:** `users/templates/user/user_list.html:71` (link a `usuario_editar`) y `:97` (form de `usuario_toggle`): solo se esconden para el propio usuario.
- **Escenario:** el admin de programa ve los botones sobre un superusuario o un multiprograma; al usarlos recibe redirect con aviso (el servidor ya rechaza).
- **Propuesta:** anotar por fila `gestionable` y `credenciales_editables` en la vista del listado (en lote, sin N+1) y esconder o deshabilitar los botones. V-UI.
- **Test:** el listado de un admin de programa no tiene la URL de edición ni de toggle de un superusuario.

**Resolución:** ✅ Resuelto en #631 (Cambio 181, Ola 2 PR 2), 08-10-2026 —
`anotar_acciones_del_listado(operador, usuarios)` marca `gestionable` y `credenciales_editables` en
cada fila de la página y `user_list.html` esconde el lápiz y el interruptor según esas dos marcas
(con «Fuera de tu alcance» cuando no hay ninguna acción posible). La anotación es **en lote**: los
roles salen del `prefetch_related("groups")` que el listado ya hace y las capacidades de cada rol se
resuelven con cuatro consultas acotadas a los roles que aparecen en la página, nunca una por fila.
Cubre las tres ramas de alcance —admin global, admin de programa y gestor territorial de Becas—, que
es donde estaba el riesgo de que la pantalla y el servidor dijeran cosas distintas. El servidor sigue
siendo la autoridad: `puede_gestionar_usuario` y `puede_gestionar_credenciales` no se tocaron.
**Ajuste de la ronda 2:** la leyenda «Fuera de tu alcance» faltaba en una de las dos ramas. Con
`gestionable=True` y `credenciales_editables=False` —el multiprograma: editar sí, activar no— la celda
quedaba con el lápiz y **nada más**, y la ausencia del interruptor no se explicaba sola. Ahora también
ahí va la leyenda. Se sumó una consulta a la anotación (`tiene_token_app`), para «Cerrar sesión de la
app» de SEC-26: el techo del test pasa de 15 a 16.
**Test permanente:**
`users.tests.test_usuarios_ola2_pr2.R0b10BotonesDelListadoTests.test_el_listado_no_ofrece_editar_ni_togglear_a_un_superusuario`
(+ `test_el_listado_no_ofrece_togglear_a_un_multiprograma` —editar sí, togglear no, que es
exactamente la asimetría de SEC-03—, `test_sobre_un_usuario_propio_siguen_estando_los_dos_botones`,
`test_el_admin_global_sigue_viendo_todos_los_botones` y
`test_la_anotacion_no_consulta_una_vez_por_fila`, con el techo de consultas sobre 12 filas).

### R0b-12 · Correr P-04 en PRD (operativo, PM)
**Severidad:** — (operativo, sin código) · **Origen:** #539 (Cambio 110) · **Ola:** PM · **Esfuerzo:** —
- **Qué:** correr P-04 (README §3), ampliado por R0b-03, en PRD de ECOM, antes o junto con el release que lleve SEC-03, para saber qué cuentas dejan de ser editables por un admin de programa (superusuarios con rol de programa, multiprograma, roles Backoffice/Sistema) y avisarle a sus admins que esas altas pasan por un admin global.
