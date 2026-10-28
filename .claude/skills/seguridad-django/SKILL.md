---
name: seguridad-django
description: Checklist de seguridad para código Django de Chaco — autorización por capacidades (core/rbac.py), separación backoffice/portal, inscripción pública por token, archivos del ciudadano, inyección SQL, XSS, CSRF, subidas, CSP y datos personales. Usala al escribir o revisar una vista, un endpoint de /api/, un formulario público, una subida de archivos, SQL crudo o cualquier cosa que muestre datos del padrón.
paths:
  - "core/rbac.py"
  - "**/views.py"
  - "**/views/*.py"
  - "**/api/*.py"
  - "**/middleware.py"
  - "config/middlewares/**"
  - "**/forms.py"
  - "**/forms/*.py"
---

# Seguridad en Django para Chaco

Adaptada de la skill `django-security` de [ECC](https://github.com/affaan-m/ECC)
(MIT, © 2026 Affaan Mustafa). Se quitó lo que contradice al repo (roles por campo en el
usuario, settings partidos por archivo, `django-csp`, JWT) y se dejó lo que vale, apuntado
a las piezas reales.

## 1. Autorización: por capacidad, del lado del servidor

- Se autoriza **solo por capacidad** (`modulo.accion`) con `core/rbac.py`:
  `@requiere("codigo")`, `puede(user, codigo, programa=None)`, `puede_alguna(...)`.
  Nunca por nombre de grupo, nunca `user.groups.filter(name=...)`, nunca `is_staff`.
- Capacidad nueva = entrada en el `CATALOGO` de `core/rbac.py`, no un `Permission` suelto.
- Módulos con `"alcance": "programa"`: pasar el `programa` en la verificación. Un rol de
  Becas no puede habilitar algo de Dispositivos.
- **La autorización no reemplaza al filtro del queryset.** Además de "puede ver casos",
  el queryset tiene que acotar *a cuáles* (programa, territorio, institución). Un `pk` en
  la URL que no se filtra por alcance es un IDOR.
- **Esconder el botón no es autorizar.** La vista que recibe el POST verifica de nuevo.
- En DRF, el default es `IsAuthenticated`: eso dice que hay sesión, no que tenga la
  capacidad. Un endpoint nuevo de `/api/` verifica `puede(...)` igual que una vista.
- Probar la guarda por **mutación**: romper la regla y ver el test en rojo. Un test de
  alcance que pasa con "cualquier rol habilita" no prueba nada.

## 2. Superficies separadas

- El ciudadano vive en `/portal/`; `PortalCiudadanoMiddleware` lo saca de cualquier otra
  ruta. Una ruta nueva para ciudadanos va bajo `/portal/` y no se exime del middleware.
- La **inscripción pública por token** es anónima: el token es la única llave. Nada de
  ids correlativos en esas URLs, validar el estado del relevamiento en el servidor, y no
  devolver datos de otra persona en errores ni en respuestas de validación.
- `media/` pasa siempre por `media_protegida` (sesión + pertenencia por archivo). Un
  archivo nuevo del ciudadano no se sirve por otra URL ni por `static/`.

## 3. Inyección SQL

```python
# Bien: el ORM o parámetros
Formulario.objects.filter(dni=dni)
cursor.execute("SELECT id FROM t WHERE dni = %s AND estado = %s", [dni, estado])

# Mal: interpolar la entrada
cursor.execute(f"SELECT id FROM t WHERE dni = {dni}")
Model.objects.raw("... WHERE x = '%s'" % valor)
Model.objects.extra(where=[f"x = {valor}"])
```

Los nombres de columna o de orden que vienen del request (`?orden=`) se validan contra una
lista cerrada antes de llegar al `order_by()`.

## 4. XSS

- Los templates escapan solos. `|safe`, `mark_safe()` y `{% autoescape off %}` solo con
  contenido propio, nunca con algo que cargó un usuario o vino de RENAPER/SIIS.
- Para armar HTML en Python: `format_html("<span>{}</span>", valor)`; no
  `mark_safe(f"...{valor}...")`.
- Datos hacia JavaScript: `{{ datos|json_script:"id-datos" }}` y leerlos con
  `JSON.parse(document.getElementById("id-datos").textContent)`. No interpolar variables
  dentro de un `<script>`.
- En Alpine, `x-text` y no `x-html` con datos de usuario.

## 5. CSRF

- Todo POST lleva `{% csrf_token %}`; los `fetch` mandan `X-CSRFToken`.
- `@csrf_exempt` solo para un webhook que se autentica de otra forma (firma, token), con
  el motivo en un comentario. Nunca para "que ande el formulario".
- Una acción que cambia datos no va por GET.

## 6. Subidas de archivos

- Validar tipo por contenido (bytes mágicos) y no solo por extensión, y que la extensión
  coincida con el contenido.
- Validar tamaño en el formulario. Los topes globales del request viven en
  `config/settings.py` (`DATA_UPLOAD_MAX_MEMORY_SIZE`, `DATA_UPLOAD_MAX_NUMBER_FILES`);
  `FILE_UPLOAD_MAX_MEMORY_SIZE` no es un tope, es el umbral para pasar a disco.
- Nombre del archivo generado por el sistema, nunca el que mandó el usuario tal cual.
- Se guarda bajo `media/` y se sirve solo por `media_protegida`.

## 7. Cabeceras y configuración

- CSP y `frame-ancestors` los pone `config.middlewares.security_headers.SecurityHeadersMiddleware`
  (escrito a mano, no `django-csp`; el ingress pisa `X-Frame-Options`). Un tercero nuevo
  —script, imagen, `connect-src`— se agrega ahí con su motivo, o en `CSP_EXTRA_SOURCES`.
- `manage.py check --deploy` es gate del CI: un warning nuevo se arregla, no se silencia.
- Secretos solo por variable de entorno. Nada de credenciales en el repo, en ejemplos ni
  en los tests.
- Los límites de intentos usan `core/services/throttle.py`; con más de un worker el
  contador necesita el caché compartido (Redis en `prd`).

## 8. Datos personales

- Los logs no llevan DNI, CUIL, nombre completo, correo, teléfono ni tokens. Loguear el
  `pk` y la acción.
- Ningún volcado de personas entra al repo (gate `Sin datos personales`): ni fixtures con
  datos reales ni CSV de ejemplo sacados de PRD.
- Las exportaciones (CSV/Excel) verifican capacidad y alcance igual que el listado del
  que salen.

## Checklist rápido

| Chequeo | Dónde |
|---|---|
| Capacidad verificada en el servidor, con programa si aplica | `@requiere` / `puede` |
| Queryset acotado al alcance del usuario | selector o servicio |
| Ruta de ciudadano bajo `/portal/` | `config/urls.py` |
| Sin `\|safe` / `mark_safe` sobre datos de usuario | templates y `format_html` |
| SQL crudo parametrizado; orden validado contra lista cerrada | `cursor.execute(sql, params)` |
| POST con CSRF; sin `@csrf_exempt` injustificado | vistas |
| Subidas validadas por contenido y tamaño; servidas por `media_protegida` | forms |
| Tercero nuevo declarado en el CSP | `security_headers.py` |
| Sin datos personales en logs ni en el repo | logging, fixtures |
| Test que se pone rojo si la guarda se rompe | tests |
