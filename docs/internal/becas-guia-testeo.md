# Programa Becas — Guía de testeo

Guía para probar el Programa Becas de punta a punta (backoffice + API de campo).
Cubre las 6 tasks: #73, #79, #74, #76, #77, #82.

---

## 0. Preparación

```powershell
python manage.py migrate
python manage.py seed_rbac
python manage.py seed_becas
python manage.py createsuperuser   # si no tenés uno
python manage.py runserver
```

Crear 3 usuarios de prueba y asignarles los roles de Becas (desde el admin de
Django `/admin/auth/user/`, o por `shell`), agregándolos a los grupos:

- **Becas — Administrador** → usuario `admin_becas`
- **Becas — Coordinador** → usuario `coord_becas`
- **Becas — Territorial** → usuario `terri_becas` (ponerle contraseña conocida)

> Tip (shell): `u.groups.add(Group.objects.get(name="Becas — Coordinador"))`.

---

## 1. Roles y accesos (#79)

| # | Pasos | Resultado esperado |
|---|---|---|
| 1.1 | Login como `admin_becas` | El sidebar muestra **Becas** con Segmentos, Cuestionario social, Convocatorias, Relevamientos y Revisión |
| 1.2 | Login como `coord_becas` | El sidebar muestra **Becas** con Convocatorias, Relevamientos y Revisión (sin Segmentos/Cuestionario) |
| 1.3 | Login como `terri_becas` | **No** ve la sección Becas (solo usa la app de campo / API) |
| 1.4 | Como `coord_becas`, ir a `/becas/config/segmentos/` por URL directa | Redirige con "No tiene permisos" (no es admin del programa) |

---

## 2. Configuración del programa (#74) — como `admin_becas`

| # | Pasos | Resultado esperado |
|---|---|---|
| 2.1 | Becas → Segmentos → Nuevo segmento. Nombre "Producción Territorial", cupo 200, guardar | Aparece en la lista; tarjetas de stats actualizadas |
| 2.2 | Abrir el segmento → agregar subsegmento "Ladrillo" cupo 120 | Se agrega; barra de cupo distribuido 120/200 |
| 2.3 | Agregar subsegmento "Carbón" cupo **100** | **Error**: "supera el cupo del segmento… Máximo disponible: 80" (RN-40) |
| 2.4 | Agregar subsegmento "Carbón" cupo 80 | Se agrega; cupo distribuido 200/200, disponible 0 |
| 2.5 | En el segmento, asignar coordinador | El desplegable **solo** lista usuarios con rol Coordinador. Asignar `coord_becas` |
| 2.6 | Agregar requisito nativo del segmento (texto + tipo). Si tipo = Selector, cargar opciones (una por línea) | Se agrega; con Selector exige al menos una opción |
| 2.7 | Cuestionario social → Nueva pregunta tipo Selector con opciones | Se crea; se puede activar/desactivar y eliminar (confirmación SweetAlert2) |
| 2.8 | Desactivar una pregunta | Queda "Inactiva" (no se mostrará en el formulario de campo) |

---

## 3. Relevamientos (#76) — como `coord_becas`

> Requisito: tener una **Convocatoria** del segmento del coordinador.

| # | Pasos | Resultado esperado |
|---|---|---|
| 3.1 | Becas → Convocatorias → Nueva. Segmento = uno asignado al coordinador | El desplegable de segmentos solo muestra los suyos |
| 3.2 | Becas → Relevamientos → Nuevo. Elegir convocatoria, territorial (solo rol Territorial), fecha y zona | Se crea con nombre auto "Relevamiento NNN", estado **Asignado** |
| 3.3 | Abrir el relevamiento → Reasignar territorial | Cambia el territorial asignado |
| 3.4 | Reprogramar fecha | Cambia la fecha asignada |
| 3.5 | Crear un relevamiento de un segmento **no** asignado (manipular URL) | La convocatoria ajena no aparece / el alta falla |
| 3.6 | Filtrar la lista por estado | La tabla filtra correctamente; un relevamiento con fecha pasada y abierto muestra badge **Vencido** |

---

## 4. Revisión de formularios (#77) — como `coord_becas`

> Para tener datos: usar la **API** (sección 6) para crear formularios y
> finalizar el relevamiento, o cargarlos por el admin de Django.

| # | Pasos | Resultado esperado |
|---|---|---|
| 4.1 | Becas → Revisión | Lista de relevamientos **finalizados / en revisión** de sus segmentos |
| 4.2 | Abrir un relevamiento finalizado → "Iniciar revisión" | Estado pasa a **En revisión** |
| 4.3 | Abrir un formulario | Muestra identidad, RENAPER (pendiente), **Resultado SIS: pendiente**, respuestas del cuestionario y la traza |
| 4.4 | Editar el celular y guardar | Se guarda y aparece una entrada en la **Traza de cambios** (valor anterior → nuevo, usuario, fecha) |
| 4.5 | Aprobar (SweetAlert2) | Estado del formulario = **Aprobado** |
| 4.6 | Rechazar sin motivo | SweetAlert2 **no** deja continuar (motivo obligatorio) |
| 4.7 | Rechazar con motivo | Estado = **Rechazado**; se muestra el motivo |
| 4.8 | Con todos los formularios revisados → "Marcar terminado" | Estado del relevamiento = **Terminado** (si quedan ENVIADO, lo bloquea) |
| 4.9 | Como `coord_becas`, abrir por URL un formulario de **otro** segmento | **403** (fuera de alcance) |

---

## 5. Pruebas automatizadas

```powershell
$env:PY_VENV = "$PWD\.venv\Scripts\python.exe"
$env:DJANGO_SECRET_KEY = "test-key"
$env:PYTEST_RUNNING = "1"
$env:DJANGO_SYNCDB_PROJECT_APPS = "True"
& $env:PY_VENV manage.py test programas
```

Esperado: **OK** (84 tests). Por área:
`test_becas_models` (#73), `test_becas_rbac` (#79), `test_becas_config` (#74),
`test_becas_relevamientos` (#76), `test_becas_revision` (#77), `test_becas_api` (#82).

---

## 6. API de campo (#82) — smoke test

Reemplazar `TERRI_USER`/`TERRI_PASS` por el territorial creado, y `REL_ID` por un
relevamiento asignado a ese territorial.

```bash
# 6.1 Login → token (exige capacidad becas.campo)
curl -s -X POST http://localhost:8000/api/becas/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"terri_becas","password":"TERRI_PASS"}'
# → {"token":"<TOKEN>", ...}. Con un usuario sin becas.campo → 403.

# 6.2 Mis relevamientos
curl -s http://localhost:8000/api/becas/relevamientos/ -H "Authorization: Token <TOKEN>"

# 6.3 Detalle con definición de formulario (globales + requisitos + requiere_gps)
curl -s http://localhost:8000/api/becas/relevamientos/REL_ID/ -H "Authorization: Token <TOKEN>"

# 6.4 Iniciar
curl -s -X POST http://localhost:8000/api/becas/relevamientos/REL_ID/iniciar/ -H "Authorization: Token <TOKEN>"

# 6.5 Crear formulario con sync offline (resuelve/crea el Ciudadano por DNI)
curl -s -X POST http://localhost:8000/api/becas/relevamientos/REL_ID/formularios/ \
  -H "Authorization: Token <TOKEN>" -H "Content-Type: application/json" \
  -d '{"celular":"3624111222","email_contacto":"x@y.com",
       "datos_identificacion":{"dni":"40400400","nombre":"Juan","apellido":"Pérez"},
       "data":{"globales":{},"requisitos":{}}}'
# → 201; en la respuesta "ciudadano" queda seteado y "datos_identificacion" en null.

# 6.6 Finalizar (queda disponible para Revisión en el backoffice)
curl -s -X POST http://localhost:8000/api/becas/relevamientos/REL_ID/finalizar/ -H "Authorization: Token <TOKEN>"
```

Verificaciones clave:
- Sin token → 401/403.
- Un territorial **no** ve relevamientos de otro (404 al pedir uno ajeno).
- Crear formulario sin `dni` en `datos_identificacion` → 400.
- Si el DNI ya existe como Ciudadano, el formulario lo **linkea** sin pisar sus datos.
