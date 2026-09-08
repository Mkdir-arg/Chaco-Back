# Formulario público de Becas — Fase 6: correcciones de la segunda revisión

**Para quien ejecuta (Codex u otro agente):** este documento es autosuficiente. Cada punto trae
*dónde está el error, por qué es un error y exactamente qué hacer*. No hace falta releer las
fases anteriores; sí hay que leer `CLAUDE.md` y `AGENTS.md` (convenciones del repo) antes de tocar código.

| | |
|---|---|
| **Rama base** | `feature/relevamiento-publico-fase-5-correcciones` (PR #305). Crear `feature/relevamiento-publico-fase-6-correcciones` desde ahí y abrir el PR **contra la rama de Fase 5**. |
| **Cadena** | Épica #69 · Análisis #289 · registro `docs/internal/requerimientos.md` **Cambio 40** |
| **Origen** | Segunda revisión de código del diff `development…fase-5` (24/08/2026): 10 hallazgos, 4 de seguridad/producción |
| **Estimación** | ~4 h |
| **Entorno** | Siempre el venv del repo: `$env:PY_VENV = "$PWD\.venv\Scripts\python.exe"; $env:DJANGO_SECRET_KEY = "test-key"`. Python 3.14 local rompe el render de templates bajo el test client (`AttributeError: 'super' object has no attribute 'dicts'`): **ese error es de entorno y ya está en `development`**; cualquier otro error es real. |

## Reglas de trabajo para esta fase

1. **Un commit por hallazgo** (título `fix(becas): …` o `fix(portal): …`), en el orden de abajo.
2. **Cada hallazgo lleva su test** en `portal/tests/test_correcciones_review_2.py` (crear) o en el módulo de tests existente que corresponda. Los tests tienen que **fallar antes del fix y pasar después**; si un test necesita renderizar bajo el test client, usar el helper `_tolerar_render_local` de `portal/tests/test_inscripcion.py` (solo tolera el bug conocido `dicts`, re-lanza el resto).
3. **Reutilizar lo que existe** — es el motivo de varios de estos bugs. Los helpers a reutilizar están nombrados en cada punto.
4. **No mover issues del Project ni tocar `main`** (solo el PM mueve tareas).
5. **Gates de cierre** (todos deben quedar en cero/OK): `manage.py check` · `makemigrations --check --dry-run` (esta fase **no** migra) · `scripts\design_audit.py --changed` 0 errores · `scripts\compile_templates.py` 0 errores · `scripts\requerimientos.py --check` OK · suites `portal.tests` y `programas.tests.test_relevamiento_publico test_padron test_becas_api test_becas_vencimientos test_becas_revision` sin fallos nuevos (los errores `dicts` preexistentes son 6 en `test_relevamiento_publico` y 14 en `test_becas_revision`, más 11 en `portal.tests` de módulos ajenos; verificarlo contra `development` si hay dudas).
6. **Al terminar**, agregar al **Historial del Cambio 40** en `docs/internal/requerimientos.md` una entrada fechada «Fase 6 — segunda revisión» que liste los 10 arreglos en una línea cada uno (mismo estilo que la entrada de la Fase 5 que ya está ahí) y actualizar la línea de PRs en `docs/plans/2026-08-22-formulario-publico-becas-plan.md` (sección *Estado*) sumando el PR nuevo.

---

## Críticos

### C1 · El rate limit del paso 1 se saltea con el header `X-Forwarded-For`

- **Archivos:** `portal/services/inscripcion.py` (`_ip_de`, `intentos_excedidos`, `registrar_intento`, líneas ~45-70) · `core/services/throttle.py` (`_ip_cliente`).
- **Error:** la IP se toma del **primer** valor de `X-Forwarded-For`. nginx (`nginx.conf:46`) usa `$proxy_add_x_forwarded_for`, que **agrega** al final lo que ya traía el cliente; el primer valor lo controla el atacante. Rotando el header, cada request cae en un bucket nuevo y el paso 1 queda como oráculo ilimitado de Gran Base/RENAPER y de «quién está inscripto». Además `portal/services/inscripcion.py` **reimplementa** `core/services/throttle.py`, que tiene el mismo defecto.
- **Solución:**
  1. En `core/services/throttle.py`, cambiar `_ip_cliente` para preferir `HTTP_X_REAL_IP` (nginx lo fija con `$remote_addr`, `nginx.conf:45`), luego el **último** valor de `X-Forwarded-For`, luego `REMOTE_ADDR`. Esto arregla también a los otros consumidores del throttle.
  2. En `portal/services/inscripcion.py`, **borrar** `_ip_de`, `intentos_excedidos` y `registrar_intento`, y exponer una sola función `paso1_excedido(request)` que delegue en `rate_limit_excedido(request, "inscripcion_paso1", MAX_INTENTOS_IP, VENTANA_SEGUNDOS)`. Conservar las constantes `MAX_INTENTOS_IP` / `VENTANA_SEGUNDOS` (con sus `getattr(settings, …)`).
  3. En `portal/views/inscripcion.py` (`inscripcion_paso1`), reemplazar el par «`intentos_excedidos` al inicio + `registrar_intento` en cada rama» por **una** llamada a `paso1_excedido(request)` al comienzo del POST: `rate_limit_excedido` cuenta y decide en el mismo paso. Si excede → `form.is_valid(); form.add_error(None, MENSAJE_DEMASIADOS_INTENTOS)` sin consultar nada más (mantener ese comportamiento).
  4. Ajustar `portal/tests/test_inscripcion.py`: el test del rate limit hoy parchea `portal.views.inscripcion.intentos_excedidos`; pasar a parchear `portal.views.inscripcion.paso1_excedido`. El test unitario de ventana (`RateLimitTests`) pasa a usar `rate_limit_excedido` directamente.
- **Test nuevo:** con `RequestFactory`, dos requests con `HTTP_X_FORWARDED_FOR` distintos pero el mismo `HTTP_X_REAL_IP` comparten el contador; y un request con `X-Real-IP` ignora un `X-Forwarded-For` falso.

### C2 · El captcha se resuelve una vez y se reutiliza infinitamente

- **Archivo:** `portal/views/inscripcion.py`, `inscripcion_paso1`, rama de éxito (~línea 107-115: se guarda la sesión y se hace `redirect` al paso 2).
- **Error:** la respuesta del captcha queda en `request.session[SESSION_KEY_CAPTCHA]` después del POST exitoso; solo se regenera en el camino que vuelve a renderizar. Un bot resuelve `a+b` una vez y loopea POSTs con distintos DNIs: `captcha_valido` sigue dando `True` y cada request consulta Gran Base.
- **Solución:** en `portal/services/inscripcion.py` agregar `consumir_captcha(request)` que haga `request.session.pop(SESSION_KEY_CAPTCHA, None)` y `pop(SESSION_KEY_CAPTCHA_PREGUNTA, None)`. Llamarla en la vista **inmediatamente después** de que `captcha_valido(...)` devuelva `True` (antes de seguir con padrón/duplicado/consulta), de modo que **cualquier** POST con captcha correcto lo consuma, avance o no. El render posterior ya llama a `nuevo_captcha(request)` en POST, así que el formulario que vuelve con error trae desafío nuevo.
- **Test nuevo:** POST exitoso (con `consultar_persona` mockeado) → segundo POST con la misma respuesta de captcha y otro DNI **no** avanza (no redirect, `consultar_persona` llamado una sola vez).

### C3 · La idempotencia por `client_uuid` no funciona en el MySQL de producción

- **Archivo:** `programas/services/inscripcion_publica.py`, `crear_formulario_publico` (~línea 75: `rel.formularios.filter(client_uuid=client_uuid).first()`).
- **Error:** el lookup nativo de `UUIDField` falla o no matchea en el esquema productivo, que guarda los UUID **como texto sin guiones**. El equipo ya lo sufrió en la sincronización móvil y lo resolvió con `_formulario_por_client_uuid` en `programas/api/views.py:57` (anota `Replace(Cast("client_uuid", CharField()), "-", "")` y compara con `client_uuid.hex`). Al no reusarlo, en producción el doble submit del paso 2 crea dos formularios o da 500, aunque en SQLite (tests) funcione.
- **Solución:**
  1. Mover `_formulario_por_client_uuid` a `programas/services/becas.py` como `formulario_por_client_uuid(relevamiento, client_uuid)` (misma implementación). En `programas/api/views.py` dejar `_formulario_por_client_uuid = formulario_por_client_uuid` (import) para no tocar sus llamadas ni sus tests.
  2. En `crear_formulario_publico`, convertir el `client_uuid` de sesión (es `str`) con `uuid.UUID(client_uuid)` y usar `formulario_por_client_uuid(rel, ...)`. Si el string no es un UUID válido (`ValueError`), tratarlo como ausente (no idempotencia) — no puede romper el envío.
- **Test nuevo:** el test existente `test_doble_submit_es_idempotente` (`portal/tests/test_inscripcion_envio.py`) debe seguir pasando; agregar uno que llame al servicio con `client_uuid` como **string con guiones** y verifique que el segundo envío devuelve `creado=False`. (La diferencia real solo se ve en MySQL; el objetivo del test es asegurar que se usa el helper tolerante y la conversión a `uuid.UUID`.)

### C4 · `formulario_revalidar_renaper` no pasa por el scope ni por el gate RN-P13

- **Archivo:** `programas/views/revision.py:563-566`.
- **Error:** es la única vista mutante de formularios que no llama a `_assert_scope_formulario(request, formulario)`. Un usuario con `becas.programa.administrar` pero sin `becas.relevamiento.publico` (o fuera del segmento) puede POSTear `/becas/formularios/<pk>/revalidar-renaper/` sobre un formulario del link y pisar nombre/apellido/género/fecha del ciudadano, aunque el detalle le dé 403.
- **Solución:** agregar `_assert_scope_formulario(request, formulario)` inmediatamente después del `get_object_or_404` (antes del chequeo de método), igual que hacen `formulario_detalle` y las demás vistas del módulo.
- **Test nuevo:** con `RequestFactory` + `patch` de `puede` en `programas.views.revision` devolviendo `False` para `CAP_RELEVAMIENTO_PUBLICO`, la vista sobre un formulario de relevamiento público lanza `PermissionDenied` (o responde 403 vía client).

---

## Altos

### A5 · RN-22 se saltea si la fecha de Gran Base no se pudo normalizar

- **Archivo:** `portal/forms/inscripcion.py`, `InscripcionPaso2Form.__init__` (~línea 158-160) y `fecha_nacimiento_efectiva` (~línea 176-184).
- **Error:** con `origen == "personas"` se **borran** los campos `nombre/apellido/fecha_nacimiento`. Si `fecha_iso()` devolvió `""` (formato desconocido del proveedor), `fecha_nacimiento_efectiva()` es `None`, `es_menor(None)` es `None` y `clean()` nunca exige apoderado: un menor se inscribe sin apoderado, con `datos_identificacion.fecha_nacimiento=""` y `validado_renaper=True`, y no tiene dónde cargar la fecha.
- **Solución:** en `__init__`, cuando `origen == "personas"` borrar solo `nombre` y `apellido`; **conservar `fecha_nacimiento` únicamente si la fecha validada está vacía** (`not fecha_iso(datos.get("fecha_nacimiento"))`), como campo obligatorio; si la fecha validada existe, borrarlo como hoy. En `fecha_nacimiento_efectiva`, si no es manual y el campo `fecha_nacimiento` está presente en `self.fields`, devolver `cleaned_data.get("fecha_nacimiento")`. En `programas/services/inscripcion_publica.py`, al armar `datos_identificacion` para `es_validado`, usar la fecha del form si la del proveedor vino vacía. La identidad sigue contando como validada (nombre y apellido vienen del proveedor). Actualizar el template `paso2.html`: el bloque «Tus datos» hoy solo se muestra con `form.es_manual`; mostrar también el campo `fecha_nacimiento` cuando exista en el form (`{% if "fecha_nacimiento" in form.fields %}`) con el texto «No pudimos obtener tu fecha de nacimiento: completala».
- **Test nuevo:** identificación `personas` con `datos.fecha_nacimiento = "texto raro"` → el form **exige** `fecha_nacimiento`; completándola con una fecha de menor, exige apoderado.

### A6 · El DNI del apoderado solo se valida cuando la persona es menor

- **Archivo:** `portal/forms/inscripcion.py`, `clean()` (~línea 190-205).
- **Error:** el bloque de apoderado se renderiza siempre (`paso2.html`), pero la normalización/validación de `apoderado_dni` vive dentro del `if es_menor(...)`. Un adulto que escribe `30.123.456` o `abc` hace que `resolver_ciudadano_offline` cree un `Ciudadano` con ese DNI malformado (`programas/services/becas.py:165`).
- **Solución:** sacar la normalización fuera de la rama de menor: si `cleaned.get("apoderado_dni")` viene cargado, siempre reducirlo a dígitos, exigir 7-8 dígitos (`add_error` si no) y guardar el valor normalizado. Dentro de la rama de menor solo queda la obligatoriedad de los cinco campos. Mismo criterio para `apoderado_genero` si viene cargado (ya es `ChoiceField`, no hace falta más).
- **Test nuevo:** adulto con `apoderado_dni="30.123.456"` → `cleaned_data["apoderado_dni"] == "30123456"`; adulto con `apoderado_dni="abc"` → error en el campo.

### A7 · Si falla la carga del padrón, el link queda abierto (fail-open)

- **Archivos:** `programas/forms.py`, `RelevamientoForm.save()` (~línea 1250) · `programas/views/relevamientos.py`, `RelevamientoCreateView.form_valid` (~línea 553).
- **Error:** `super().save()` commitea el relevamiento (token, EN_CURSO) y **después** `cargar_padron` corre en su propia transacción. Si falla (`bulk_create`, storage del archivo), el request da 500 pero el público queda vivo con cero filas de padrón, y `esta_habilitado` interpreta «sin padrón = abierto». No hay `ATOMIC_REQUESTS`.
- **Solución:** envolver el cuerpo de `RelevamientoForm.save()` en `with transaction.atomic():` (alta + `cargar_padron` en la misma transacción; `cargar_padron` ya es `@transaction.atomic`, anida bien). Alternativa equivalente: decorar `form_valid` con `transaction.atomic`. Elegir el form: así también protege el alta de página completa.
- **Test nuevo:** con `patch("programas.services.padron.PadronHabilitado.objects.bulk_create", side_effect=RuntimeError)`, `form.save()` lanza y **no existe** ningún `Relevamiento` nuevo.

### A8 · Dos listados de revisión muestran formularios públicos a quien no tiene la capacidad

- **Archivo:** `programas/views/revision.py`, `RevisionPersonasListView` y `RenaperPendientesListView` (`get_queryset`, ~líneas 130-180).
- **Error:** el gate RN-P13 se aplica en los detalles (`_assert_scope_formulario`) pero no en estos dos listados: un coordinador sin `becas.relevamiento.publico` ve filas de inscriptos por link (territorial vacío), cuenta `pendientes_renaper` con ellos, y cada «Abrir» da 403. En `relevamientos.py` el invariante ya existe: `_sin_publicos_si_no_puede(qs, user)`.
- **Solución:** en ambos `get_queryset` (y en el `base` de `get_context_data` de pendientes RENAPER, y en el contador `pendientes_renaper` del contexto si lo hay), excluir `relevamiento__tipo=Relevamiento.Tipo.PUBLICO` cuando `not puede(self.request.user, CAP_RELEVAMIENTO_PUBLICO)`. Crear un helper local `_sin_formularios_publicos_si_no_puede(qs, user)` en `revision.py` (espejo del de relevamientos, filtrando por `relevamiento__tipo`). Mientras se está ahí: en `renaper_pendientes.html:37`, mostrar «Formulario público» cuando `formulario.relevamiento.territorial` es nulo (hoy queda vacío).
- **Test nuevo:** con la capacidad parcheada en `False`, `RevisionPersonasListView().get_queryset()` no incluye el formulario del público; con `True`, sí.

### A9 · Beneficiarios y su export incluyen formularios públicos que el usuario no puede abrir

- **Archivo:** `programas/views/relevamientos.py`, `ConvocatoriaDetailView.get_context_data` (~línea 177: `beneficiarios`, `n_beneficiarios`, `n_aprobados`) y `convocatoria_export_beneficiarios`.
- **Error:** los relevamientos se filtran con `_sin_publicos_si_no_puede`, pero los formularios de la solapa Beneficiarios y su CSV se calculan sobre **todos** los `Formulario` de la convocatoria. El usuario sin capacidad ve `n_relevamientos=1` y 50 beneficiarios, cada uno con link a un detalle que da 403; `convocatoria_export_relevamientos` sí filtra, así que los dos exports se contradicen.
- **Solución:** aplicar a esos querysets de `Formulario` la misma exclusión (`exclude(relevamiento__tipo=PUBLICO)` cuando no `_puede_publico(user)`). Crear `_sin_formularios_publicos_si_no_puede(qs, user)` en `relevamientos.py` y usarlo en el contexto y en el export.
- **Test nuevo:** convocatoria con un territorial (1 formulario aprobado) y un público (1 aprobado); usuario sin capacidad → `n_beneficiarios == 1` y el CSV tiene una sola fila de datos; con capacidad → 2.

---

## Medio

### M10 · Un relevamiento convertido a público desde el admin queda ASIGNADO para siempre

- **Archivos:** `programas/models/__init__.py`, `Relevamiento.save()` (~línea 1681-1686) · `programas/admin.py`, `RelevamientoAdmin`.
- **Error:** la Fase 5 hizo que el token se genere en cualquier `save()` (para que la conversión por admin tenga link), pero la promoción `ASIGNADO → EN_CURSO` sigue gateada en `_state.adding`. Convertido por admin, el link existe y siempre responde «no disponible» porque `relevamiento_disponible()` exige EN_CURSO y los únicos caminos a ese estado necesitan territorial.
- **Solución (la más simple y sana):** en `RelevamientoAdmin` hacer `tipo` **read-only en edición** (`get_readonly_fields`: agregar `"tipo"` cuando `obj is not None`). El tipo se define al crear y no se cambia (RN-P1 del análisis #289). Con eso, la generación de token en `save()` puede volver a ser solo en el alta, o quedarse como está (inofensiva). Registrar en el Historial del Cambio 40 que la conversión de tipo por admin quedó bloqueada.
- **Test nuevo:** `RelevamientoAdmin(Relevamiento, site).get_readonly_fields(request, obj=rel)` contiene `"tipo"` y no lo contiene con `obj=None`.

---

## Menores (hacer si sobra tiempo, en el mismo PR)

- `renaper_pendientes.html:37`: celda de territorial vacía para públicos → «Formulario público» (cubierto en A8).
- `portal/views/inscripcion.py`: en el camino de doble submit concurrente (`creado=False`) el comprobante guarda `correo_enviado=False`; es cosmético.
- `programas/views/relevamientos.py`, `relevamiento_reemplazar_padron`: parsea `request.FILES["padron"]` a mano. Convención de `CLAUDE.md` («usar Django Forms para el backoffice»): crear un `PadronReemplazoForm(forms.Form)` con el mismo `FileField` y `clean_padron` que `RelevamientoForm` (extraer la validación a una función compartida en `programas/forms.py`) y usarlo en la vista.

---

## Checklist de entrega

- [ ] 10 commits (C1…M10) con su test cada uno, en verde.
- [ ] Gates del punto 5 de *Reglas de trabajo* en cero/OK.
- [ ] Historial del Cambio 40 y *Estado* del plan actualizados.
- [ ] PR contra `feature/relevamiento-publico-fase-5-correcciones` con título
      `Formulario público de Becas — Fase 6: correcciones de la segunda revisión`, cuerpo con la
      tabla error → fix por hallazgo y la nota de que los errores `dicts` son de entorno (Python 3.14),
      verificados contra `development`.
- [ ] Reportar al PM: la pila queda #301 → #302 → #303 → #304 → #305 → #306 (o el número que salga).
