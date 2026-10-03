# 4.6 Usuarios, roles y dashboards (G1b, G2)

Fichas completas del dominio (pasada 3: G1b verificado por G2). Convenciones, `V-STD` y `V-UI`: README §0.
PoC: `poc/test_repro_usuarios.py`. Lo de la API REST de usuarios está en SEC-05/16/17; la toma de cuentas en SEC-03
(que absorbe G1b-01); clave provisoria del territorial y token de campo en SEC-26 (absorbe G1b-03 y G1b-04); el seed del
«Operador de backoffice» en OPS-06 (absorbe G2-02); `import_users_from_csv` en G2-05; el export del dashboard en G1b-11
(performance) y G2-01 (campos propios, dominio Becas).

| ID | Título | Sev. | Estado | Ola | Esf. | Avance 03-oct |
|---|---|---|---|---|---|---|
| G1b-02 | Capacidades «parciales» del programa se autootorgan las demás (contradice Cambio 20) | ALTA | CONF. test | 2 | M | ⬜ |
| G1b-05 | Operador no global deja cuentas activas sin rol, que entran al backoffice | MEDIA | CONF. test | 2 | S | ⬜ |
| G1b-06 | Admin de programa borra en silencio capacidades globales del rol al guardarlo | MEDIA | CONF. test | 2 | S | ⬜ |
| G2-03 | «Cambiar contraseña» abierto para cualquier sesión y sin pedir la clave actual | MEDIA | CONF. test | 2 | S | ⬜ |
| G1b-07 | Desactivar el último rol admin: 500 (programa) o sistema sin admin (global) | BAJA | CONF. test | 2 | S | ⬜ |
| G1b-08 | Claves tipeadas por un operador sin validadores ni cambio obligatorio | BAJA | CONF. lectura | 2 | S | ⬜ |
| G1b-09 | «Último administrador» salteable con dos operaciones simultáneas | BAJA | PLAUSIBLE | 7 | M | ⬜ |
| G1b-10 | Alta rápida: 500 ante colisión en carrera | BAJA | CONF. ajustado | 7 | S | ⬜ |
| G1b-12 | Dashboard de Becas: período sin tope y `?recalcular=1` sin freno | BAJA | CONF. ajustado | 4 | S | ⬜ |
| G2-04 | Inicio: los contadores no miden lo que dicen sus etiquetas | BAJA | CONF. lectura | 5 | S | ⬜ |
| G2-06 | El login pide «Tu correo electrónico» pero autentica por `username` | BAJA | CONF. lectura | 5 | S | ⬜ |
| R0b-01 | `user_form.html` no muestra el `help_text` de los campos que SEC-03 bloquea | BAJA (MINOR) | revisión Ola 0 (2ª tanda) | 2 (Usuarios) | S | ⬜ |
| R0b-02 | SEC-03: un rol desactivado no cuenta como fuera de alcance | BAJA (MINOR) | revisión Ola 0 (2ª tanda) | 2 (Usuarios) | S | ⬜ |
| R0b-03 | P-04 no cubre roles Backoffice/Sistema sin programa | BAJA (MINOR) | revisión Ola 0 (2ª tanda) | 2 (Usuarios; antes de R0b-12) | S | ⬜ |
| R0b-10 | Listado de usuarios: editar y activar/desactivar visibles para usuarios no gestionables | BAJA (MINOR) | revisión Ola 0 (2ª tanda) | 2 (Usuarios) | S | ⬜ |
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

## BAJA

### G1b-07 · Desactivar el último rol admin: 500 si es de programa; sistema sin admin si es global
**Severidad:** BAJA (mitigado: `seed_rbac` asigna «Administrador», protegido, a los superusuarios) · **Estado:** CONFIRMADO + AMPLIADO (`G1b07ToggleRolSinAdminTests`, 2 tests) · **Origen:** G1b-07 · **Ola:** 2 · **Esfuerzo:** S
- **Ubicación:** `users/services/roles.py:119-132` (solo `asegurar_admin_restante(programa=...)`); `users/views/roles.py:159-163` (solo captura `RolProtegidoError`).
- **Escenario (reproducido):** (1) desactivar el único rol admin de un programa sin superusuario activo → `SinAdministradorProgramaError` sin capturar → **500**; (2) desactivar un rol global no protegido con `usuario.administrar` deja `usuarios_que_administran()` vacío y responde 302.
- **Propuesta:** `toggle_activo` llama también `rbac.asegurar_admin_restante()` (global); la vista captura `SinAdministradorError`/`SinAdministradorProgramaError` y muestra el mensaje.
- **Tests:** los dos de la PoC invertidos.

### G1b-08 · Claves tipeadas por un operador sin validadores ni cambio obligatorio
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Origen:** G1b-08 · **Ola:** 2 (con SEC-26) · **Esfuerzo:** S
- **Ubicación:** `users/forms/__init__.py:313-325`, `:400-408` (`CharField` sin `validate_password`); `users/services/admin.py:65-67` (`set_password` sin marcar `debe_cambiar_contrasena`).
- **Propuesta:** `clean_password` con `validate_password`; al fijar la clave de **otro** usuario, `debe_cambiar_contrasena=True` (cuidado con el `Profile` cacheado, Cambio 37).

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

### G2-04 · Inicio: los contadores no miden lo que dicen sus etiquetas
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Origen:** G2-04 · **Ola:** 5 · **Esfuerzo:** S · **Decisión:** D-G204
- **Ubicación:** `core/views/public.py:66-84`; `templates/inicio.html:470-476`, `:504-505`, `:521-522`; `dashboard/utils.py:40-83`; `dashboard/api_views/__init__.py:203`, `:221`.
- **Evidencia:** «Total ciudadanos ↑N nuevos este mes» = `InscripcionPrograma` del mes, no ciudadanos nuevos; «Seguimientos hoy: X · X actividades hoy» es el mismo número dos veces (inscripciones con `fecha_inscripcion = hoy`); «usuarios activos hoy» = `last_login` de las últimas 24 h, incluye ciudadanos del portal; `tendencias_datos` arma `range(dias)` desde `hoy - dias`: el gráfico **nunca incluye hoy**; nada mira Becas (`Formulario`), donde está casi toda la operación.
- **Propuesta:** corregir etiquetas («inscripciones este mes», sacar la línea duplicada, «ingresaron en las últimas 24 h»), filtrar `last_login` a usuarios de backoffice, `range(dias + 1)` (o `fecha_inicio = hoy - (dias - 1)`); D-G204: ¿el inicio muestra indicadores de Becas? El «hoy» UTC es BEC-18.
- **Tests:** contexto de `inicio_view` con 1 ciudadano nuevo y 2 inscripciones del mes muestra las dos cifras por separado; `tendencias_datos` con `labels[-1]` = hoy. V-UI.

### G2-06 · El login pide «Tu correo electrónico» pero autentica por `username`
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Origen:** G2-06 · **Ola:** 5 · **Esfuerzo:** S
- **Ubicación:** `users/templates/user/login.html:146`, `:155`; `users/forms/auth.py:23`; sin `AUTHENTICATION_BACKENDS` propio (ModelBackend por username); el ABM (`user_form.html:156`) y el alta rápida (`_alta_rapida_modal.html:27`) piden «Nombre de usuario» libre; el correo de credenciales informa «Usuario: {{ username }}».
- **Propuesta:** rotular «Usuario» (lo más chico; default). Alternativa: backend que acepte email **solo si es único**, lo que exige validar unicidad del email en `users/forms/__init__.py` (hoy no). V-UI.

## Seguimientos de la revisión de la Ola 0, segunda tanda (agregados el 03-oct-2026)

Observaciones MINOR del revisor de #539 (SEC-03, Cambio 110) y un seguimiento operativo. Las líneas son de
`origin/development @ 719dc0a`. Van juntas en el PR 2 de la Ola 2 (*Usuarios*).

### R0b-01 · `user_form.html` no muestra el `help_text` de los campos que SEC-03 bloquea
**Severidad:** BAJA (MINOR del revisor de #539) · **Estado:** CONFIRMADO (lectura) · **Origen:** revisión de la Ola 0, 2ª tanda · **Ola:** 2 (PR 2, Usuarios) · **Esfuerzo:** S
- **Ubicación:** `users/forms/__init__.py:476-486` (deshabilita `username`, `email` y `password` y les pone el aviso en `help_text`); `users/templates/user/user_form.html:156-164` y `:205-207` renderizan label, campo y errores, nunca `help_text`.
- **Escenario:** el admin de programa ve los campos grises sin saber por qué; el aviso nunca llega a la pantalla.
- **Propuesta:** renderizar `{{ form.<campo>.help_text }}` debajo de cada campo (con el estilo de ayuda del sistema de diseño), o un aviso único arriba del bloque cuando `not form.credenciales_editables`. V-UI.
- **Test:** GET de la edición de un usuario multiprograma por un admin de programa contiene el texto del aviso.

### R0b-02 · SEC-03: un rol desactivado no cuenta como fuera de alcance
**Severidad:** BAJA (MINOR del revisor de #539) · **Estado:** CONFIRMADO (lectura) · **Origen:** revisión de la Ola 0, 2ª tanda · **Ola:** 2 (PR 2, Usuarios) · **Esfuerzo:** S
- **Ubicación:** `users/selectors/usuarios.py:145-147` (`puede_gestionar_credenciales` hace `.exclude(meta__activo=False)`: un rol inactivo de otro programa no frena).
- **Escenario:** el admin de Becas cambia clave y correo de un usuario que tiene, además, un rol **desactivado** de admin de Dispositivos; si después alguien reactiva ese rol, el usuario recupera el acceso a Dispositivos con credenciales que puso el admin de Becas (el mismo vector de G1b-01, diferido).
- **Propuesta:** contar los roles inactivos como fuera de alcance (sacar el `exclude`), o fijar la decisión contraria en `requerimientos.md` con este escenario.
- **Test:** usuario con rol de Becas + rol inactivo de otro programa → el admin de Becas no edita credenciales.

### R0b-03 · P-04 no cubre roles Backoffice/Sistema sin programa
**Severidad:** BAJA (MINOR del revisor de #539) · **Estado:** CONFIRMADO (lectura) · **Origen:** revisión de la Ola 0, 2ª tanda · **Ola:** 2 (PR 2, Usuarios; conviene hacerlo antes de R0b-12) · **Esfuerzo:** S
- **Ubicación:** README §3, P-04: la primera consulta hace `JOIN programas_programa` (descarta los roles sin programa) y la segunda `JOIN users_rolmeta` (descarta los grupos sin `RolMeta`, que `puede_gestionar_credenciales` cuenta como fuera de alcance).
- **Propuesta:** `LEFT JOIN` a `programas_programa` y a `users_rolmeta` y listar, por usuario activo con algún rol de programa, cuántos roles de categoría Backoffice/Sistema (programa nulo) y cuántos grupos sin `RolMeta` tiene: son las cuentas cuyas credenciales el admin de programa dejó de poder tocar con SEC-03.

### R0b-10 · Listado de usuarios: editar y activar/desactivar visibles para usuarios no gestionables
**Severidad:** BAJA (MINOR del revisor de #539) · **Estado:** CONFIRMADO (lectura) · **Origen:** revisión de la Ola 0, 2ª tanda · **Ola:** 2 (PR 2, Usuarios) · **Esfuerzo:** S
- **Ubicación:** `users/templates/user/user_list.html:71` (link a `usuario_editar`) y `:97` (form de `usuario_toggle`): solo se esconden para el propio usuario.
- **Escenario:** el admin de programa ve los botones sobre un superusuario o un multiprograma; al usarlos recibe redirect con aviso (el servidor ya rechaza).
- **Propuesta:** anotar por fila `gestionable` y `credenciales_editables` en la vista del listado (en lote, sin N+1) y esconder o deshabilitar los botones. V-UI.
- **Test:** el listado de un admin de programa no tiene la URL de edición ni de toggle de un superusuario.

### R0b-12 · Correr P-04 en PRD (operativo, PM)
**Severidad:** — (operativo, sin código) · **Origen:** #539 (Cambio 110) · **Ola:** PM · **Esfuerzo:** —
- **Qué:** correr P-04 (README §3), ampliado por R0b-03, en PRD de ECOM, antes o junto con el release que lleve SEC-03, para saber qué cuentas dejan de ser editables por un admin de programa (superusuarios con rol de programa, multiprograma, roles Backoffice/Sistema) y avisarle a sus admins que esas altas pasan por un admin global.
