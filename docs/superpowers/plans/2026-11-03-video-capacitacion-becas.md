# Video de capacitación de Becas — plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Producir un MP4 único, regenerable por escena, que muestre el módulo Becas completo (5 roles, backoffice, link público, app de campo, errores) con narración en castellano rioplatense, y un chequeo automático que garantice que ninguna pantalla, campo, acción, mensaje ni estado quedó sin mostrar.

**Architecture:** Un comando Django (`seed_video_becas`) deja la base local en un estado conocido. `scripts/video_becas/inventario.py` extrae del código la lista de lo que hay que mostrar. Cada capítulo es un guion (`guion/NN.md`) y una escena Playwright (`escenas/NN.js`) hecha de pasos `{narracion, cubre, acciones}`; `lib/` aporta cursor visible, resaltado, tipeo humano, voz (edge-tts) y sincronía; `armar.ps1` orquesta seed → grabación → audio → `ffmpeg` → MP4 con capítulos y `.srt`.

**Tech Stack:** Django 5.2 (venv `.venv312`), Playwright para Node (propio de `scripts/video_becas/`), `edge-tts` (venv aparte), `ffmpeg`/`ffprobe`, PowerShell 5.1, Expo web (`Chaco-mobile`).

**Spec:** `docs/superpowers/specs/2026-11-03-video-capacitacion-becas-design.md`

## Global Constraints

- Grabación **solo en local** (`localhost:8000` del `docker compose` de dev; app con `npm run web`), nunca contra testing ni PRD.
- Datos: solo los que crea `seed_video_becas`. Ningún DNI, nombre ni correo real. DNIs del rango `90000001–90000099`.
- Voz: `es-AR-ElenaNeural` por defecto; `es-AR-TomasNeural` como alternativa por parámetro.
- Lienzo: 1920×1080. App de campo grabada a 390×844 y centrada sobre el lienzo.
- La barra de direcciones no aparece (Playwright graba el contenido de la página).
- `scripts/video_becas/` entra en `.gitattributes` como `export-ignore`; `scripts/video_becas/salida/` y `scripts/video_becas/.venv-voz/` y `scripts/video_becas/node_modules/` van al `.gitignore`.
- Nada de lo que se instala entra a `requirements.txt` ni al `package.json` de la raíz.
- `seed_video_becas` lleva `exigir_entorno_demo("seed_video_becas")` como primera línea de `handle` y se agrega a `SEEDS_DEMO` en `core/tests/test_comandos_peligrosos.py`.
- Condición de cierre: `inventario.py --faltantes` imprime `0 sin cubrir` para las categorías `url`, `campo`, `accion`, `msg` y `estado`.
- Python del repo siempre por `.venv312\Scripts\python.exe`; tests con el runner de Django (`manage.py test`), con `PYTEST_RUNNING=1` y `DJANGO_SYNCDB_PROJECT_APPS=True`.
- Al terminar: entrada en `docs/internal/requerimientos.md` y `scripts\requerimientos.py --check` en OK.
- Commits solo cuando el usuario lo pide; rama de trabajo `feature/video-capacitacion-becas` desde `origin/development`.

---

## Estructura de archivos

```
programas/management/commands/seed_video_becas.py     ← escenario de datos (Fase 1)
programas/tests/test_seed_video_becas.py              ← idempotencia y estados presentes
core/tests/test_comandos_peligrosos.py                ← +1 en SEEDS_DEMO
scripts/video_becas/
  README.md                       ← cómo regrabar (comandos, requisitos)
  package.json                    ← { "dependencies": { "playwright": "1.5x" } }
  inventario.py                   ← genera salida/inventario.json y --faltantes
  no-aplica.yml                   ← ítems que no se muestran, con motivo
  guion/00-introduccion.md … 10-errores.md
  escenas/00-introduccion.js … 10-errores.js
  escenas/index.js                ← lista ordenada de escenas; `node escenas --cobertura`
  lib/escena.js                   ← runner: pasos, timeline, recordVideo
  lib/cursor.js                   ← overlay de cursor + resaltado (addInitScript)
  lib/humano.js                   ← mover, clic, tipear a velocidad humana
  lib/voz.py                      ← edge-tts con caché por hash del texto
  lib/cartel.html                 ← cartel de capítulo
  lib/montar.ps1                  ← audio de la escena + mux + pad móvil
  armar.ps1                       ← orquestador
  salida/                         ← gitignored
```

---

## Fase 0 — Preparación del entorno

### Task 0.1: Rama, exclusiones y herramientas

**Files:**
- Modify: `.gitattributes` (bloque "Exclusiones del snapshot de release")
- Modify: `.gitignore`
- Create: `scripts/video_becas/README.md`
- Create: `scripts/video_becas/package.json`

- [ ] **Step 1: Rama de trabajo**

```powershell
git fetch origin
git switch -c feature/video-capacitacion-becas origin/development
```

- [ ] **Step 2: export-ignore e ignorados**

Agregar en `.gitattributes`, debajo de `/scripts/check_datos_personales.py export-ignore`:

```
# Video de capacitación de Becas: material interno, se regenera desde el repo.
/scripts/video_becas export-ignore
```

Agregar al final de `.gitignore`:

```
# Video de capacitación (scripts/video_becas): intermedios y entornos locales
scripts/video_becas/salida/
scripts/video_becas/.venv-voz/
scripts/video_becas/node_modules/
```

- [ ] **Step 3: package.json propio**

`scripts/video_becas/package.json`:

```json
{
  "name": "video-becas",
  "private": true,
  "type": "module",
  "scripts": {
    "cobertura": "node escenas/index.js --cobertura"
  },
  "dependencies": {
    "playwright": "^1.50.0"
  }
}
```

Luego, **avisando al usuario antes** (instala binarios de navegador):

```powershell
Set-Location scripts\video_becas; npm install; npx playwright install chromium; Set-Location ..\..
```

- [ ] **Step 4: ffmpeg y edge-tts (avisar antes de cada uno)**

```powershell
winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements
# abrir una shell nueva para que entre al PATH
ffmpeg -version | Select-Object -First 1
& .\.venv312\Scripts\python.exe -m venv scripts\video_becas\.venv-voz
& scripts\video_becas\.venv-voz\Scripts\python.exe -m pip install edge-tts
& scripts\video_becas\.venv-voz\Scripts\edge-tts.exe --list-voices | Select-String "es-AR"
```

Esperado: aparecen `es-AR-ElenaNeural` y `es-AR-TomasNeural`.

- [ ] **Step 5: README mínimo**

`scripts/video_becas/README.md` con: propósito, requisitos (ffmpeg, Node, `.venv-voz`), los tres comandos (`armar.ps1 -Seed`, `armar.ps1 -Capitulo 04`, `armar.ps1 -Todo`) y la condición de cierre (`inventario.py --faltantes` en 0). Se completa en la Task 3.3.

- [ ] **Step 6: Verificar que el release no lo arrastra**

```powershell
git check-attr export-ignore scripts/video_becas/README.md scripts/video_becas/lib/escena.js
git check-ignore -v scripts/video_becas/salida/x.mp4 scripts/video_becas/node_modules/x
```

Esperado: las dos rutas del primer comando responden `export-ignore: set`; las del segundo muestran la regla del `.gitignore` que las atrapa.

---

## Fase 1 — Escenario de datos

### Task 1.1: `seed_video_becas`, usuarios y programa

**Files:**
- Create: `programas/management/commands/seed_video_becas.py`
- Create: `programas/tests/test_seed_video_becas.py`
- Modify: `core/tests/test_comandos_peligrosos.py` (`SEEDS_DEMO`, L52-56)

**Interfaces:**
- Consumes: `exigir_entorno_demo(comando)` de `core/management/guardas.py`; `seed_becas` (crea programa BECAS y los 5 roles `Becas — Administrador|Coordinador|Coordinador Regional|Referente|Territorial`); modelos de `programas.models` (`ProgramaSiis`, `Segmento`, `Subsegmento`, `RequisitoNativo`, `PreguntaGlobal`, `Convocatoria`, `Relevamiento`, `Formulario`, `PadronHabilitado`, `AsignacionTerritorial`, `AsignacionCoordinador`, `AsignacionReferente`).
- Produces: constante `USUARIOS` (username → rol, clave `Video2026!`) y `DNI_BASE = 90000000`, que el guion y las escenas usan tal cual.

- [ ] **Step 1: Test de guarda y de idempotencia (rojo)**

`programas/tests/test_seed_video_becas.py`:

```python
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings

from programas.models import Convocatoria, Formulario, PadronHabilitado, Relevamiento

User = get_user_model()


@override_settings(DEBUG=True)
class SeedVideoBecasTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_video_becas", verbosity=0)

    def test_un_usuario_por_rol(self):
        esperados = {
            "admin.becas": "Becas — Administrador",
            "coordinador": "Becas — Coordinador",
            "coord.regional": "Becas — Coordinador Regional",
            "referente": "Becas — Referente",
            "territorial": "Becas — Territorial",
        }
        for username, rol in esperados.items():
            with self.subTest(username=username):
                user = User.objects.get(username=username)
                self.assertTrue(user.check_password("Video2026!"))
                self.assertTrue(user.groups.filter(name=rol).exists())

    def test_relevamientos_en_todos_los_estados(self):
        estados = set(Relevamiento.objects.values_list("estado", flat=True))
        self.assertTrue({"ASIGNADO", "EN_CURSO", "FINALIZADO", "EN_REVISION", "TERMINADO"} <= estados)
        self.assertTrue(Relevamiento.objects.filter(tipo=Relevamiento.Tipo.PUBLICO).exists())

    def test_casos_en_todos_los_estados(self):
        estados = set(Formulario.objects.values_list("estado", flat=True))
        self.assertTrue({"ENVIADO", "APROBADO", "RECHAZADO", "BAJA"} <= estados)

    def test_padron_ficticio(self):
        dnis = list(PadronHabilitado.objects.values_list("dni", flat=True))
        self.assertGreaterEqual(len(dnis), 30)
        self.assertTrue(all(90000000 < int(d) < 90000100 for d in dnis))

    def test_es_idempotente(self):
        antes = (User.objects.count(), Convocatoria.objects.count(), Relevamiento.objects.count(), Formulario.objects.count())
        call_command("seed_video_becas", verbosity=0)
        despues = (User.objects.count(), Convocatoria.objects.count(), Relevamiento.objects.count(), Formulario.objects.count())
        self.assertEqual(antes, despues)
```

Agregar `"seed_video_becas"` a `SEEDS_DEMO` en `core/tests/test_comandos_peligrosos.py` (L52-56), así el test existente exige la guarda.

- [ ] **Step 2: Correr y ver rojo**

```powershell
$env:PY_VENV=".\.venv312\Scripts\python.exe"; $env:DJANGO_SECRET_KEY="test-key"; $env:PYTEST_RUNNING="1"; $env:DJANGO_SYNCDB_PROJECT_APPS="True"
& $env:PY_VENV manage.py test programas.tests.test_seed_video_becas core.tests.test_comandos_peligrosos
```

Esperado: `CommandError: Unknown command: 'seed_video_becas'` (o equivalente).

- [ ] **Step 3: Esqueleto del comando con usuarios y programa**

`programas/management/commands/seed_video_becas.py` (leer primero `seed_becas_demo_mobile.py` L300-420 para copiar el estilo de `get_or_create` por nombre):

```python
"""Escenario de datos ficticios para grabar el video de capacitación de Becas.

Deja un usuario por rol, un programa con dos segmentos (uno con subsegmentos y
otro sin), convocatorias, relevamientos y casos en cada estado, y un padrón de
30 personas inexistentes. Idempotente: se puede correr antes de cada regrabación.
Solo corre en entorno demo (``exigir_entorno_demo``).
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import BaseCommand, call_command
from django.db import transaction
from django.utils import timezone

from core.management.guardas import exigir_entorno_demo
from programas.models import (
    AsignacionCoordinador,
    AsignacionReferente,
    AsignacionTerritorial,
    Convocatoria,
    Formulario,
    PadronHabilitado,
    PreguntaGlobal,
    ProgramaSiis,
    Relevamiento,
    RequisitoNativo,
    Segmento,
    Subsegmento,
)

User = get_user_model()

CLAVE = "Video2026!"
DNI_BASE = 90000000

USUARIOS = {
    "admin.becas": ("Becas — Administrador", "Ana", "Giménez"),
    "coordinador": ("Becas — Coordinador", "Carlos", "Pérez"),
    "coord.regional": ("Becas — Coordinador Regional", "Rocío", "Molina"),
    "referente": ("Becas — Referente", "Fabián", "Soto"),
    "territorial": ("Becas — Territorial", "Tamara", "Ledesma"),
}


class Command(BaseCommand):
    help = "Siembra el escenario del video de capacitación de Becas (solo entorno demo)."

    @transaction.atomic
    def handle(self, *args, **options):
        exigir_entorno_demo("seed_video_becas")
        call_command("seed_becas", verbosity=0)
        usuarios = self._usuarios()
        programa, seg_con, seg_sin, sub_a, sub_b = self._programa()
        self._alcances(usuarios, seg_con, seg_sin, sub_a)
        convocatorias = self._convocatorias(seg_con, seg_sin, sub_a, sub_b)
        self._padron(convocatorias["con_padron"])
        relevamientos = self._relevamientos(convocatorias, usuarios["territorial"])
        self._casos(relevamientos)
        self.stdout.write(self.style.SUCCESS("Escenario del video listo."))

    def _usuarios(self):
        usuarios = {}
        for username, (rol, nombre, apellido) in USUARIOS.items():
            user, _ = User.objects.update_or_create(
                username=username,
                defaults={"first_name": nombre, "last_name": apellido, "email": f"{username}@ejemplo.test", "is_active": True},
            )
            user.set_password(CLAVE)  # a propósito: es un escenario de grabación, siempre con la misma clave
            user.save(update_fields=["password"])
            user.groups.set([Group.objects.get(name=rol)])
            usuarios[username] = user
        return usuarios

    def _programa(self):
        programa = ProgramaSiis.objects.filter(segmentos__isnull=False).first() or ProgramaSiis.objects.first()
        seg_con, _ = Segmento.objects.update_or_create(
            nombre="Capacitación Laboral",
            defaults={"programa": programa, "cupo_maximo": 120, "activo": True, "descripcion": "Segmento con subsegmentos."},
        )
        seg_sin, _ = Segmento.objects.update_or_create(
            nombre="Terminalidad Educativa",
            defaults={"programa": programa, "cupo_maximo": 40, "activo": True, "descripcion": "Segmento sin subsegmentos."},
        )
        sub_a, _ = Subsegmento.objects.update_or_create(segmento=seg_con, nombre="Región Centro", defaults={"cupo_maximo": 70})
        sub_b, _ = Subsegmento.objects.update_or_create(segmento=seg_con, nombre="Región Norte", defaults={"cupo_maximo": 50})
        RequisitoNativo.objects.get_or_create(segmento=seg_con, subsegmento=None, texto="Tener entre 18 y 35 años")
        RequisitoNativo.objects.get_or_create(segmento=seg_sin, subsegmento=None, texto="No haber terminado el secundario")
        PreguntaGlobal.objects.get_or_create(
            texto="¿Tenés conexión a internet en tu casa?",
            defaults={"tipo": "boolean", "obligatorio": True, "activo": True, "orden": 1},
        )
        return programa, seg_con, seg_sin, sub_a, sub_b
```

Antes de escribir `_programa`, verificar en `programas/models/__init__.py` L2852-3060 los nombres exactos de los campos de `RequisitoNativo` y `PreguntaGlobal` (el agente de relevamiento vio `texto`, `tipo`, `opciones`, `obligatorio`, `orden`); ajustar si difieren. Los métodos `_alcances`, `_convocatorias`, `_padron`, `_relevamientos` y `_casos` se agregan en las tasks siguientes; mientras tanto, dejarlos como `return {}` / `pass` para que el módulo importe.

- [ ] **Step 4: Correr tests**

Esperado: `test_un_usuario_por_rol` y la guarda en verde; los demás rojos.

### Task 1.2: Alcances, convocatorias y padrón

**Files:**
- Modify: `programas/management/commands/seed_video_becas.py`

- [ ] **Step 1: `_alcances`**

```python
    def _alcances(self, usuarios, seg_con, seg_sin, sub_a):
        for seg in (seg_con, seg_sin):
            AsignacionTerritorial.objects.get_or_create(segmento=seg, territorial=usuarios["territorial"])
            AsignacionCoordinador.objects.get_or_create(segmento=seg, coordinador=usuarios["coordinador"], defaults={"activo": True})
            AsignacionReferente.objects.get_or_create(segmento=seg, referente=usuarios["referente"])
        # El regional solo ve su subsegmento: ver cómo lo modela el código antes de
        # escribir esta línea (grep "coordinador_regional" en programas/services y users/).
```

Verificar en `programas/models/__init__.py` L3893-3960 los nombres de campo de `AsignacionReferente` y cómo se acota el Coordinador Regional a un subsegmento (`grep -n "coordinador_regional\|subsegmento" programas/services/alcance*.py users/`). Implementar el alcance del regional sobre `sub_a` con el modelo que aparezca.

- [ ] **Step 2: `_convocatorias`**

```python
    def _convocatorias(self, seg_con, seg_sin, sub_a, sub_b):
        hoy = timezone.localdate()
        def conv(nombre, segmento, subsegmento, desde, hasta, **extra):
            obj, _ = Convocatoria.objects.update_or_create(
                nombre=nombre,
                defaults={"segmento": segmento, "subsegmento": subsegmento, "fecha_inicio": desde, "fecha_fin": hasta,
                          "descripcion": extra.pop("descripcion", ""), "activo": extra.pop("activo", True), **extra},
            )
            return obj
        return {
            "con_padron": conv("Capacitación 2026 — Centro (con padrón)", seg_con, sub_a, hoy - timedelta(30), hoy + timedelta(60)),
            "sin_padron": conv("Terminalidad 2026 (link abierto)", seg_sin, None, hoy - timedelta(10), hoy + timedelta(45)),
            "cerrada": conv("Capacitación 2025 — Norte (cerrada)", seg_con, sub_b, hoy - timedelta(200), hoy - timedelta(20),
                            activo=False, cerrada_automaticamente=True, cerrada_el=timezone.now() - timedelta(19)),
            "pausada": conv("Capacitación 2026 — Norte (pausada)", seg_con, sub_b, hoy - timedelta(5), hoy + timedelta(90)),
        }
```

Verificar en L3080-3200 los nombres `cerrada_automaticamente`/`cerrada_el`. La pausa de `"pausada"` se hace sobre su **subsegmento** `sub_b` con el mismo servicio que usa la pantalla de pausas (`grep -n "def pausar" programas/services/*.py`), con usuario `admin.becas` y motivo "Revisión presupuestaria (ejemplo del video)".

- [ ] **Step 3: `_padron`**

```python
    def _padron(self, convocatoria):
        nombres = ["Lucía", "Mateo", "Valentina", "Santiago", "Martina", "Joaquín", "Camila", "Benjamín", "Sofía", "Thiago"]
        apellidos = ["Acosta", "Benítez", "Cáceres", "Duarte", "Escobar", "Ferreyra", "Gómez", "Ibarra", "López", "Núñez"]
        for i in range(1, 31):
            PadronHabilitado.objects.update_or_create(
                convocatoria=convocatoria, relevamiento=None, dni=str(DNI_BASE + i),
                defaults={"sexo": "F" if i % 2 else "M", "nombre": nombres[i % 10], "apellido": apellidos[(i * 3) % 10],
                          "fecha_nacimiento": timezone.localdate() - timedelta(days=365 * (18 + i % 15))},
            )
        # DNI 90000031 es la persona "fallecida" para el error del paso 1: ver qué
        # campo lo marca (grep -n "fallecid" programas/models/__init__.py) y setearlo.
```

- [ ] **Step 4: Correr tests** — `test_padron_ficticio` en verde.

### Task 1.3: Relevamientos y casos en cada estado

**Files:**
- Modify: `programas/management/commands/seed_video_becas.py`

- [ ] **Step 1: `_relevamientos`**

```python
    def _relevamientos(self, c, territorial):
        ahora = timezone.now()
        E = Relevamiento.Estado
        T = Relevamiento.Tipo
        def rel(conv, zona, estado, desde, hasta, tipo=T.TERRITORIAL, **extra):
            defaults = {"estado": estado, "fecha_asignada": desde, "fecha_hasta": hasta, "tipo": tipo,
                        "territorial": territorial if tipo == T.TERRITORIAL else None, **extra}
            obj, _ = Relevamiento.objects.update_or_create(convocatoria=conv, zona=zona, defaults=defaults)
            return obj
        d = timedelta
        return {
            "asignado":    rel(c["con_padron"], "Barrio San Martín", E.ASIGNADO, ahora + d(2), ahora + d(5)),
            "en_curso":    rel(c["con_padron"], "Barrio Belgrano", E.EN_CURSO, ahora - d(1), ahora + d(7)),
            "finalizado":  rel(c["con_padron"], "Villa Río Negro", E.FINALIZADO, ahora - d(10), ahora + d(3), fecha_finalizado=ahora - d(1)),
            "en_revision": rel(c["con_padron"], "Barrio Güiraldes", E.EN_REVISION, ahora - d(20), ahora - d(2)),
            "terminado":   rel(c["cerrada"], "Barrio Toba", E.TERMINADO, ahora - d(190), ahora - d(30)),
            "publico":     rel(c["sin_padron"], "", E.EN_CURSO, ahora - d(5), ahora + d(40), tipo=T.PUBLICO, cupo_maximo=50),
            "vencido":     rel(c["con_padron"], "", E.EN_CURSO, ahora - d(15), ahora - d(1), tipo=T.PUBLICO, cupo_maximo=30),
            "cupo_lleno":  rel(c["sin_padron"], "", E.EN_CURSO, ahora - d(3), ahora + d(10), tipo=T.PUBLICO, cupo_maximo=2),
            "pausado":     rel(c["pausada"], "", E.EN_CURSO, ahora - d(2), ahora + d(30), tipo=T.PUBLICO),
        }
```

`zona=""` para públicos: `clean()` exige zona solo en TERRITORIAL y `update_or_create` no llama a `clean()`; igual verificar que `save()` no la exija (L3414-3434). El relevamiento `vencido` queda `EN_CURSO` con `fecha_hasta` pasada: es exactamente el estado del incidente de hoy antes del cron.

- [ ] **Step 2: `_casos`**

Leer `Formulario` en L3989-4250 y el servicio de ingesta de la API (`programas/api/serializers.py`, `FormularioSerializer.create`) para ver cómo se arma un caso completo (`data`/`respuestas`, `ciudadano`, `client_uuid`). Crear con un helper `caso(relevamiento, dni, estado, **extra)` que use ese mismo camino (o `Formulario.objects.update_or_create(relevamiento=..., client_uuid=uuid5(NAMESPACE_DNS, f"video-{dni}"), defaults=...)` si el servicio exige request). Dejar:

| relevamiento | cantidad | estado |
|---|---|---|
| en_curso | 3 | ENVIADO (uno con identidad sin validar: origen "manual") |
| finalizado | 4 | ENVIADO |
| en_revision | 6 | 2 ENVIADO, 2 APROBADO, 1 RECHAZADO, 1 BAJA |
| terminado | 5 | 4 APROBADO, 1 RECHAZADO |
| publico | 2 | ENVIADO |
| cupo_lleno | 2 | ENVIADO (= `cupo_maximo`, así `cupo_completo` es True) |

Los DNIs de los casos salen del padrón (`DNI_BASE + i`); los de `publico`/`cupo_lleno` (sin padrón) usan `DNI_BASE + 40..45`. Para "lista de espera", usar el servicio de `programas/services/cupo.py` (`grep -n "def agregar_a_espera\|def promover" programas/services/cupo.py`) sobre el caso BAJA.

- [ ] **Step 3: Correr todos los tests del módulo + la guarda**

```powershell
& $env:PY_VENV manage.py test programas.tests.test_seed_video_becas core.tests.test_comandos_peligrosos
```

Esperado: todo verde.

- [ ] **Step 4: Probar contra la base real de dev**

```powershell
docker compose up -d
docker compose exec -T app python manage.py seed_video_becas
docker compose exec -T app python manage.py seed_video_becas   # segunda corrida: sin error, mismos conteos
```

Entrar a `http://localhost:8000` con `admin.becas` / `Video2026!` y recorrer Convocatorias y Relevamientos: tienen que verse los 9 relevamientos con sus estados.

- [ ] **Step 5: `ruff` y `check`**

```powershell
& $env:PY_VENV -m ruff check programas\management\commands\seed_video_becas.py programas\tests\test_seed_video_becas.py
& $env:PY_VENV manage.py check
```

---

## Fase 2 — Inventario de cobertura

### Task 2.1: `inventario.py` — generación

**Files:**
- Create: `scripts/video_becas/inventario.py`
- Create: `scripts/video_becas/no-aplica.yml`
- Test: `scripts/video_becas/test_inventario.py` (se corre con `python -m unittest`)

**Interfaces:**
- Produces: `salida/inventario.json` = lista de `{"id": str, "categoria": "url|campo|accion|msg|estado|app|req", "donde": "archivo:linea", "texto": str}`. Formato de `id`: `url:becas:<name>`, `url:portal:<name>`, `campo:<FormClass>.<field>`, `accion:<template relativo>#<n>`, `msg:<archivo>:<linea>`, `estado:<Modelo>.<VALOR>`, `app:<pantalla>`, `req:<numero>`.

- [ ] **Step 1: Test (rojo)**

```python
import json, subprocess, sys, unittest
from pathlib import Path

AQUI = Path(__file__).parent
RAIZ = AQUI.parent.parent
PY = RAIZ / ".venv312" / "Scripts" / "python.exe"


class InventarioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run([str(PY), str(AQUI / "inventario.py"), "--generar"], check=True, cwd=RAIZ)
        cls.items = json.loads((AQUI / "salida" / "inventario.json").read_text(encoding="utf-8"))
        cls.ids = {i["id"] for i in cls.items}

    def test_urls_de_becas(self):
        self.assertIn("url:becas:relevamiento_finalizar", self.ids)
        self.assertIn("url:portal:inscripcion_paso1", self.ids)

    def test_campos_de_forms(self):
        self.assertIn("campo:RelevamientoForm.zona", self.ids)
        self.assertIn("campo:InscripcionPaso1Form.dni", self.ids)

    def test_estados(self):
        self.assertIn("estado:Relevamiento.EN_REVISION", self.ids)
        self.assertIn("estado:Formulario.BAJA", self.ids)

    def test_mensajes_y_acciones(self):
        self.assertTrue(any(i.startswith("msg:portal/templates/portal/inscripcion/no_disponible.html") for i in self.ids))
        self.assertTrue(any(i.startswith("accion:programas/becas/relevamientos/relevamiento_detail.html") for i in self.ids))
```

- [ ] **Step 2: Implementación**

```python
"""Inventario de cobertura del video de Becas.

--generar   escribe salida/inventario.json desde el código
--faltantes compara con la cobertura declarada por las escenas y con no-aplica.yml
"""
import argparse, json, os, re, subprocess, sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent.parent
sys.path.insert(0, str(RAIZ))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ.setdefault("DJANGO_SECRET_KEY", "inventario")
os.environ.setdefault("PYTEST_RUNNING", "1")
import django  # noqa: E402

django.setup()

from django.urls import get_resolver  # noqa: E402

FORMS_BECAS = {
    "programas.forms": ["ProgramaSiisCreateForm", "ProgramaSiisIdentificadoresForm", "DatosSiisForm", "SegmentoForm",
                        "SegmentoCreateForm", "SubsegmentoForm", "GrupoRequisitoForm", "AsignacionCoordinadorForm",
                        "ConvocatoriaForm", "RelevamientoForm", "CupoRelevamientoForm", "ReasignarTerritorialForm",
                        "ReprogramarForm", "ForzarIdentidadForm", "VolverACampoForm", "FormularioRevisionForm",
                        "CiudadanoGeneroRevisionForm", "ItemGrupoForm", "ItemTextoForm", "ItemEtiquetaForm",
                        "ItemCampoPropioForm", "FormularioTipoNuevoForm", "RevisionPersonasFiltroForm"],
    "programas.forms_reportes": ["ReporteBecasFiltroForm", "DashboardBecasFiltroForm"],
    "portal.forms.inscripcion": ["InscripcionPaso1Form", "InscripcionPaso2Form"],
}
MODELOS_ESTADO = [("programas.models", "Relevamiento", "Estado"), ("programas.models", "Formulario", "Estado")]
TEMPLATES = [RAIZ / "programas/templates/programas/becas", RAIZ / "portal/templates/portal/inscripcion"]
CODIGO = [RAIZ / "programas/views", RAIZ / "programas/services", RAIZ / "programas/api", RAIZ / "portal/views", RAIZ / "portal/services"]
APP_SCREENS = RAIZ.parent / "Chaco-mobile" / "src" / "screens"

RE_MSG = re.compile(r'(messages\.(?:success|error|warning|info)|ValidationError|_error|CommandError)\(\s*[^"\']*?["\']([^"\']{8,})["\']')
RE_ACCION = re.compile(r'(<button[^>]*>|data-confirm-url=|<form[^>]*method="post")', re.I)
RE_TEXTO_ESTADO = re.compile(r'<(?:p|h2|h3)[^>]*>([^<]{15,})</', re.I)


def urls():
    for ns in ("becas", "portal"):
        res = get_resolver().namespace_dict[ns][1]
        for name in res.reverse_dict.keys():
            if isinstance(name, str):
                yield {"id": f"url:{ns}:{name}", "categoria": "url", "donde": f"{ns} urls", "texto": name}


def campos():
    import importlib
    for mod, clases in FORMS_BECAS.items():
        m = importlib.import_module(mod)
        for c in clases:
            form = getattr(m, c, None)
            if form is None:
                continue
            for nombre, f in form.base_fields.items():
                texto = f"{f.label or nombre} — {f.help_text}".strip(" —")
                yield {"id": f"campo:{c}.{nombre}", "categoria": "campo", "donde": mod, "texto": texto}


def estados():
    import importlib
    for mod, modelo, enum in MODELOS_ESTADO:
        E = getattr(getattr(importlib.import_module(mod), modelo), enum)
        for valor, etiqueta in E.choices:
            yield {"id": f"estado:{modelo}.{valor}", "categoria": "estado", "donde": f"{mod}.{modelo}", "texto": etiqueta}


def acciones_y_textos():
    for base in TEMPLATES:
        for t in base.rglob("*.html"):
            rel = t.relative_to(RAIZ).as_posix()
            src = t.read_text(encoding="utf-8")
            for n, m in enumerate(RE_ACCION.finditer(src), 1):
                yield {"id": f"accion:{rel.split('templates/')[1]}#{n}", "categoria": "accion", "donde": f"{rel}:{src[:m.start()].count(chr(10)) + 1}", "texto": m.group(0)[:80]}
            if "no_disponible" in rel or "demasiados" in rel or "ya_inscripto" in rel:
                for m in RE_TEXTO_ESTADO.finditer(src):
                    yield {"id": f"msg:{rel}:{src[:m.start()].count(chr(10)) + 1}", "categoria": "msg", "donde": rel, "texto": m.group(1).strip()}


def mensajes():
    for base in CODIGO:
        for p in base.rglob("*.py"):
            if "tests" in p.parts:
                continue
            rel = p.relative_to(RAIZ).as_posix()
            src = p.read_text(encoding="utf-8")
            for m in RE_MSG.finditer(src):
                linea = src[:m.start()].count("\n") + 1
                yield {"id": f"msg:{rel}:{linea}", "categoria": "msg", "donde": f"{rel}:{linea}", "texto": m.group(2)}


def app():
    if APP_SCREENS.exists():
        for p in sorted(APP_SCREENS.glob("*.js")) + sorted(APP_SCREENS.glob("*.jsx")) + sorted(APP_SCREENS.glob("*.tsx")):
            yield {"id": f"app:{p.stem}", "categoria": "app", "donde": p.name, "texto": p.stem}


def requerimientos():
    out = subprocess.run([sys.executable, str(RAIZ / "scripts/requerimientos.py"), "--programa", "becas"],
                         capture_output=True, text=True, cwd=RAIZ, env={**os.environ, "PYTHONIOENCODING": "utf-8"}).stdout
    for m in re.finditer(r"Cambio (\d+) — (.+?)\s+\[--ver", out):
        yield {"id": f"req:{m.group(1)}", "categoria": "req", "donde": "docs/internal/requerimientos.md", "texto": m.group(2)}


def generar():
    items = [*urls(), *campos(), *estados(), *acciones_y_textos(), *mensajes(), *app(), *requerimientos()]
    (AQUI / "salida").mkdir(exist_ok=True)
    (AQUI / "salida/inventario.json").write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    por_cat = {}
    for i in items:
        por_cat[i["categoria"]] = por_cat.get(i["categoria"], 0) + 1
    print("Inventario:", por_cat)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--generar", action="store_true")
    ap.add_argument("--faltantes", action="store_true")
    a = ap.parse_args()
    if a.generar or not a.faltantes:
        generar()
    if a.faltantes:
        from faltantes import faltantes  # Task 2.2
        sys.exit(faltantes())
```

Ajustar `RE_ACCION`/`RE_MSG` mirando la salida real: el objetivo es que **cada botón y cada mensaje visible al usuario** aparezca una vez. Falsos positivos (botones de cerrar modal, `messages` de comandos internos) se descartan en `no-aplica.yml`, no afinando la regex hasta que oculte cosas reales.

- [ ] **Step 3: Correr el test y el comando**

```powershell
& .\.venv312\Scripts\python.exe -m unittest scripts\video_becas\test_inventario.py
& .\.venv312\Scripts\python.exe scripts\video_becas\inventario.py --generar
```

Esperado: test verde; la línea `Inventario: {...}` con conteos por categoría. Anotar los conteos en el README: fijan el tamaño del guion.

### Task 2.2: `--faltantes` y cobertura declarada por las escenas

**Files:**
- Create: `scripts/video_becas/faltantes.py`
- Create: `scripts/video_becas/escenas/index.js`
- Modify: `scripts/video_becas/test_inventario.py`

**Interfaces:**
- Consumes: `salida/inventario.json`; cada módulo `escenas/NN-*.js` exporta `export const escena = { id: "NN", titulo: "...", rol: "...", pasos: [{ narracion, cubre: [ids], acciones: async (ctx) => {} }] }`.
- Produces: `node escenas/index.js --cobertura` imprime JSON `{ "<escena id>": [ids...] }`; `faltantes()` devuelve 0 si no falta nada en `url|campo|accion|msg|estado`.

- [ ] **Step 1: Test (rojo)** — agregar a `test_inventario.py`:

```python
    def test_faltantes_reporta_lo_no_cubierto(self):
        r = subprocess.run([str(PY), str(AQUI / "inventario.py"), "--faltantes"], capture_output=True, text=True, cwd=RAIZ)
        self.assertIn("sin cubrir", r.stdout)
```

- [ ] **Step 2: `escenas/index.js`**

```js
import { readdirSync } from "node:fs";
import { pathToFileURL } from "node:url";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const aqui = dirname(fileURLToPath(import.meta.url));

export async function cargarEscenas() {
  const archivos = readdirSync(aqui).filter((f) => /^\d\d-.*\.js$/.test(f)).sort();
  const escenas = [];
  for (const f of archivos) {
    const mod = await import(pathToFileURL(join(aqui, f)).href);
    escenas.push(mod.escena);
  }
  return escenas;
}

if (process.argv.includes("--cobertura")) {
  const escenas = await cargarEscenas();
  const cobertura = {};
  for (const e of escenas) cobertura[e.id] = e.pasos.flatMap((p) => p.cubre ?? []);
  process.stdout.write(JSON.stringify(cobertura));
}
```

- [ ] **Step 3: `faltantes.py`**

```python
import json, subprocess, sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
GATE = {"url", "campo", "accion", "msg", "estado"}


def faltantes():
    items = json.loads((AQUI / "salida/inventario.json").read_text(encoding="utf-8"))
    cob = json.loads(subprocess.run(["node", "escenas/index.js", "--cobertura"], cwd=AQUI, capture_output=True, text=True, check=True).stdout or "{}")
    cubiertos = {i for ids in cob.values() for i in ids}
    no_aplica = {}
    for linea in (AQUI / "no-aplica.yml").read_text(encoding="utf-8").splitlines():
        if ":" in linea and not linea.startswith("#"):
            k, _, v = linea.partition(":")
            no_aplica[k.strip().strip('"')] = v.strip()
    desconocidos = cubiertos - {i["id"] for i in items}
    for d in sorted(desconocidos):
        print(f"ADVERTENCIA: la escena cubre un id que no está en el inventario: {d}")
    pendientes = [i for i in items if i["id"] not in cubiertos and i["id"] not in no_aplica]
    gate = [i for i in pendientes if i["categoria"] in GATE]
    for i in pendientes:
        print(f"{i['categoria']:7} {i['id']}  ← {i['donde']}  {i['texto'][:70]}")
    print(f"\n{len(gate)} sin cubrir (gate: {', '.join(sorted(GATE))}); {len(pendientes) - len(gate)} informativos (app/req) sin asignar")
    return 1 if gate else 0
```

`no-aplica.yml` arranca con un encabezado y el formato `"<id>": motivo`:

```yaml
# Ítems del inventario que no se muestran en el video, con el motivo. Uno por línea.
# "accion:programas/becas/...#3": botón "Cerrar" de un modal; no es una acción de negocio.
```

- [ ] **Step 4: Correr** — test verde; `--faltantes` lista todo (todavía no hay escenas) y termina en 1.

---

## Fase 3 — Infraestructura de grabación

### Task 3.1: `lib/` — cursor, acciones humanas, voz

**Files:**
- Create: `scripts/video_becas/lib/cursor.js`, `lib/humano.js`, `lib/voz.py`, `lib/cartel.html`

**Interfaces:**
- Produces: `instalarCursor(page)`; `resaltar(page, locator, ms=1200)`; `mover(page, locator)`, `clic(page, locator)`, `tipear(page, locator, texto)`; `voz.py --texto "..." --salida x.mp3 [--voz es-AR-ElenaNeural]` imprime la duración en segundos; `cartel.html?titulo=...&sub=...`.

- [ ] **Step 1: `lib/cursor.js`**

```js
export async function instalarCursor(page) {
  await page.addInitScript(() => {
    if (window.__cursorVideo) return;
    window.__cursorVideo = true;
    const css = document.createElement("style");
    css.textContent = `
      #cursor-video{position:fixed;z-index:2147483647;width:22px;height:22px;pointer-events:none;
        border-radius:50%;background:rgba(27,94,32,.35);border:2px solid #1b5e20;transform:translate(-50%,-50%);
        transition:transform .08s}
      #cursor-video.clic{transform:translate(-50%,-50%) scale(.6)}
      .resaltado-video{outline:3px solid #f9a825 !important;outline-offset:3px;border-radius:6px;transition:outline-color .3s}`;
    document.addEventListener("DOMContentLoaded", () => {
      document.head.appendChild(css);
      const c = document.createElement("div");
      c.id = "cursor-video";
      document.body.appendChild(c);
      document.addEventListener("mousemove", (e) => { c.style.left = e.clientX + "px"; c.style.top = e.clientY + "px"; });
      document.addEventListener("mousedown", () => c.classList.add("clic"));
      document.addEventListener("mouseup", () => c.classList.remove("clic"));
    });
  });
}

export async function resaltar(page, locator, ms = 1200) {
  const h = await locator.elementHandle();
  await h.evaluate((el) => el.classList.add("resaltado-video"));
  await page.waitForTimeout(ms);
  await h.evaluate((el) => el.classList.remove("resaltado-video"));
}
```

- [ ] **Step 2: `lib/humano.js`**

```js
export async function mover(page, locator) {
  await locator.scrollIntoViewIfNeeded();
  const b = await locator.boundingBox();
  if (!b) throw new Error("sin boundingBox: " + locator);
  await page.mouse.move(b.x + b.width / 2, b.y + b.height / 2, { steps: 28 });
  await page.waitForTimeout(250);
}

export async function clic(page, locator) {
  await mover(page, locator);
  await locator.click();
  await page.waitForTimeout(400);
}

export async function tipear(page, locator, texto) {
  await clic(page, locator);
  await locator.fill("");
  await locator.pressSequentially(texto, { delay: 55 });
  await page.waitForTimeout(300);
}

export async function elegir(page, locator, valor) {
  await mover(page, locator);
  await locator.selectOption(valor);
  await page.waitForTimeout(500);
}
```

- [ ] **Step 3: `lib/voz.py`**

```python
"""Genera el audio de un texto con edge-tts y devuelve la duración en segundos.
Cachea por hash del texto+voz en salida/voz/<hash>.mp3."""
import argparse, hashlib, json, subprocess, sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent.parent
EDGE = AQUI / ".venv-voz" / "Scripts" / "edge-tts.exe"


def duracion(mp3):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(mp3)], capture_output=True, text=True, check=True).stdout
    return float(json.loads(out)["format"]["duration"])


def generar(texto, voz="es-AR-ElenaNeural", rate="-4%"):
    (AQUI / "salida/voz").mkdir(parents=True, exist_ok=True)
    h = hashlib.sha1(f"{voz}|{rate}|{texto}".encode()).hexdigest()[:16]
    mp3 = AQUI / "salida/voz" / f"{h}.mp3"
    if not mp3.exists():
        subprocess.run([str(EDGE), "--voice", voz, f"--rate={rate}", "--text", texto, "--write-media", str(mp3)], check=True)
    return mp3, duracion(mp3)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--texto", required=True)
    ap.add_argument("--voz", default="es-AR-ElenaNeural")
    a = ap.parse_args()
    mp3, d = generar(a.texto, a.voz)
    print(json.dumps({"mp3": str(mp3), "duracion": d}))
```

Probar: `& scripts\video_becas\.venv-voz\Scripts\python.exe scripts\video_becas\lib\voz.py --texto "Bienvenidos a la capacitación del módulo Becas."` → JSON con duración ~3 s; escuchar el mp3.

- [ ] **Step 4: `lib/cartel.html`**

Página estática 1920×1080, fondo oscuro, título grande y subtítulo, leídos de `location.search` (`titulo`, `sub`) con `decodeURIComponent`. Usa la tipografía y los colores del sistema de diseño (`.claude/agents/chaco-design-system.md`, tokens de color) para que el cartel se vea de la misma familia que la app; no es un template de Django, así que no pasa por `design_audit`.

### Task 3.2: `lib/escena.js` — runner con timeline y `lib/montar.ps1`

**Files:**
- Create: `scripts/video_becas/lib/escena.js`, `lib/montar.ps1`

**Interfaces:**
- Consumes: `escena` (Task 2.2), `instalarCursor`, `voz.py`.
- Produces: `salida/NN/video.webm`, `salida/NN/timeline.json` = `[{ "i", "narracion", "mp3", "inicio", "duracion" }]`; `montar.ps1 -Escena NN [-Movil]` → `salida/NN/escena.mp4` (video + audio, 1920×1080).

- [ ] **Step 1: `lib/escena.js`**

```js
import { chromium } from "playwright";
import { execFileSync } from "node:child_process";
import { mkdirSync, writeFileSync, renameSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { instalarCursor, resaltar } from "./cursor.js";
import * as humano from "./humano.js";

const RAIZ = join(dirname(fileURLToPath(import.meta.url)), "..");
const PY_VOZ = join(RAIZ, ".venv-voz", "Scripts", "python.exe");
const BASE = process.env.VIDEO_BASE_URL ?? "http://localhost:8000";
const BASE_APP = process.env.VIDEO_APP_URL ?? "http://localhost:8081";
const VOZ = process.env.VIDEO_VOZ ?? "es-AR-ElenaNeural";

function audio(texto) {
  const out = execFileSync(PY_VOZ, [join(RAIZ, "lib", "voz.py"), "--texto", texto, "--voz", VOZ], { encoding: "utf-8" });
  return JSON.parse(out);
}

export async function grabar(escena) {
  const dir = join(RAIZ, "salida", escena.id);
  mkdirSync(dir, { recursive: true });
  const movil = escena.movil === true;
  const viewport = movil ? { width: 390, height: 844 } : { width: 1920, height: 1080 };
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport, deviceScaleFactor: 1, recordVideo: { dir, size: viewport }, locale: "es-AR" });
  const page = await context.newPage();
  await instalarCursor(page);
  const ctx = { page, base: BASE, baseApp: BASE_APP, ...humano, resaltar: (loc, ms) => resaltar(page, loc, ms), cartel: (t, s) => page.goto(`file://${join(RAIZ, "lib", "cartel.html")}?titulo=${encodeURIComponent(t)}&sub=${encodeURIComponent(s ?? "")}`) };

  const t0 = Date.now();
  const timeline = [];
  for (const [i, paso] of escena.pasos.entries()) {
    const { mp3, duracion } = audio(paso.narracion);
    const inicio = (Date.now() - t0) / 1000;
    const tAccion = Date.now();
    await paso.acciones?.(ctx);
    const faltante = duracion * 1000 - (Date.now() - tAccion);
    if (faltante > 0) await page.waitForTimeout(faltante + 400);
    timeline.push({ i, narracion: paso.narracion, mp3, inicio, duracion, fin: (Date.now() - t0) / 1000 });
  }
  await page.waitForTimeout(800);
  const video = page.video();
  await context.close();
  renameSync(await video.path(), join(dir, "video.webm"));
  await browser.close();
  writeFileSync(join(dir, "timeline.json"), JSON.stringify(timeline, null, 1));
}
```

`ctx.login(usuario)` y `ctx.logout()` se agregan al mismo archivo: `login` va a `${base}/`, tipea usuario y `Video2026!` y espera `networkidle`; `logout` hace clic en el menú de usuario → «Cerrar sesión» (ver el selector real en `templates/includes/base.html`).

- [ ] **Step 2: `lib/montar.ps1`**

Construye el audio de la escena concatenando, por paso, el mp3 seguido de silencio hasta `fin` (según `timeline.json`), y lo muxea con `video.webm`. Para `-Movil`, escala el video a alto 1000 y lo centra con `pad=1920:1080` sobre un fondo `#0f172a`.

```powershell
param([Parameter(Mandatory)][string]$Escena, [switch]$Movil)
$dir = Join-Path $PSScriptRoot "..\salida\$Escena"
$tl = Get-Content (Join-Path $dir "timeline.json") -Raw -Encoding UTF8 | ConvertFrom-Json
$partes = @(); $i = 0
foreach ($p in $tl) {
  $pad = [math]::Max(0, $p.fin - $p.inicio - $p.duracion)
  $out = Join-Path $dir ("a{0:D3}.wav" -f $i)
  ffmpeg -y -loglevel error -i $p.mp3 -af "apad=pad_dur=$pad" -ar 48000 -ac 2 $out
  $partes += "file '$(($out -replace '\\','/'))'"; $i++
}
Set-Content (Join-Path $dir "audio.txt") $partes -Encoding ASCII
ffmpeg -y -loglevel error -f concat -safe 0 -i (Join-Path $dir "audio.txt") -c:a aac -b:a 160k (Join-Path $dir "audio.m4a")
$vf = if ($Movil) { "scale=-2:1000,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=#0f172a" } else { "scale=1920:1080" }
ffmpeg -y -loglevel error -i (Join-Path $dir "video.webm") -i (Join-Path $dir "audio.m4a") -vf $vf -r 30 -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p -c:a copy -shortest (Join-Path $dir "escena.mp4")
```

- [ ] **Step 3: Escena de prueba (descartable)**

`escenas/99-prueba.js` con dos pasos: cartel «Prueba» y login de `admin.becas` resaltando el menú «Programas». Correr:

```powershell
node -e "import('./scripts/video_becas/escenas/99-prueba.js').then(m=>import('./scripts/video_becas/lib/escena.js').then(l=>l.grabar(m.escena)))"
& scripts\video_becas\lib\montar.ps1 -Escena 99
```

Abrir `salida/99/escena.mp4`: se ve el cursor, el resaltado, y la voz coincide con lo que se muestra. Si la voz adelanta al video, subir el margen de `+400` ms en `escena.js`. Borrar `99-prueba.js` al terminar.

### Task 3.3: `armar.ps1` — orquestador y README

**Files:**
- Create: `scripts/video_becas/armar.ps1`
- Modify: `scripts/video_becas/README.md`

**Interfaces:**
- Produces: `armar.ps1 -Seed` (siembra por `docker compose exec`); `-Capitulo NN` (graba + monta una escena); `-Todo` (todas, luego une); `-Unir` (solo une lo ya montado) → `salida/video-becas.mp4` + `salida/video-becas.srt`.

- [ ] **Step 1: `armar.ps1`**

```powershell
param([switch]$Seed, [string]$Capitulo, [switch]$Todo, [switch]$Unir, [string]$Voz = "es-AR-ElenaNeural")
$ErrorActionPreference = "Stop"
$aqui = $PSScriptRoot; $raiz = Resolve-Path (Join-Path $aqui "..\..")
$env:VIDEO_VOZ = $Voz
if ($Seed) { docker compose -f (Join-Path $raiz "docker-compose.yml") exec -T app python manage.py seed_video_becas }

function Grabar($id) {
  $esc = Get-ChildItem (Join-Path $aqui "escenas") -Filter "$id-*.js" | Select-Object -First 1
  if (-not $esc) { throw "No hay escena $id" }
  $js = "import('./escenas/$($esc.Name)').then(m=>import('./lib/escena.js').then(l=>l.grabar(m.escena)))"
  Push-Location $aqui; node -e $js; Pop-Location
  $movil = (Get-Content $esc.FullName -Raw) -match "movil:\s*true"
  if ($movil) { & (Join-Path $aqui "lib\montar.ps1") -Escena $id -Movil } else { & (Join-Path $aqui "lib\montar.ps1") -Escena $id }
}

if ($Capitulo) { Grabar $Capitulo }
if ($Todo) { Get-ChildItem (Join-Path $aqui "escenas") -Filter "??-*.js" | ForEach-Object { Grabar $_.Name.Substring(0,2) } }
if ($Todo -or $Unir) {
  $escenas = Get-ChildItem (Join-Path $aqui "salida") -Directory | Where-Object { $_.Name -match '^\d\d$' } | Sort-Object Name
  $lista = $escenas | ForEach-Object { "file '" + (($_.FullName -replace '\\','/') + "/escena.mp4") + "'" }
  Set-Content (Join-Path $aqui "salida\concat.txt") $lista -Encoding ASCII
  # Capítulos (FFMETADATA) y subtítulos (.srt) a partir de los timeline.json
  $meta = @(";FFMETADATA1"); $srt = @(); $t = 0.0; $n = 1
  foreach ($e in $escenas) {
    $tl = Get-Content (Join-Path $e.FullName "timeline.json") -Raw -Encoding UTF8 | ConvertFrom-Json
    $dur = [double](ffprobe -v error -show_entries format=duration -of csv=p=0 (Join-Path $e.FullName "escena.mp4"))
    $titulo = (Get-Content (Get-ChildItem (Join-Path $aqui "escenas") -Filter "$($e.Name)-*.js").FullName -Raw) -replace '(?s).*titulo:\s*"([^"]+)".*','$1'
    $meta += "[CHAPTER]"; $meta += "TIMEBASE=1/1000"; $meta += "START=$([int]($t*1000))"; $meta += "END=$([int](($t+$dur)*1000))"; $meta += "title=$titulo"
    foreach ($p in $tl) {
      $a = [TimeSpan]::FromSeconds($t + $p.inicio); $b = [TimeSpan]::FromSeconds($t + $p.inicio + $p.duracion)
      $srt += "$n"; $srt += ("{0:hh\:mm\:ss\,fff} --> {1:hh\:mm\:ss\,fff}" -f $a, $b); $srt += $p.narracion; $srt += ""; $n++
    }
    $t += $dur
  }
  Set-Content (Join-Path $aqui "salida\capitulos.txt") $meta -Encoding UTF8
  Set-Content (Join-Path $aqui "salida\video-becas.srt") $srt -Encoding UTF8
  ffmpeg -y -loglevel error -f concat -safe 0 -i (Join-Path $aqui "salida\concat.txt") -i (Join-Path $aqui "salida\capitulos.txt") -map_metadata 1 -c copy (Join-Path $aqui "salida\video-becas.mp4")
  Write-Host "Listo: salida\video-becas.mp4 ($([math]::Round($t/60,1)) min) y video-becas.srt"
}
```

- [ ] **Step 2: Probar `-Unir` con la escena 99 montada** → `video-becas.mp4` abre, tiene un capítulo.

- [ ] **Step 3: README completo**: requisitos, cómo levantar backoffice (`docker compose up -d`) y app (`cd ..\Chaco-mobile; $env:EXPO_PUBLIC_DJANGO_API_URL="http://localhost:8000"; npm run web -- --clear`, puerto por defecto 8081: verificarlo en la consola de Expo y, si difiere, pasar `VIDEO_APP_URL`), los comandos de `armar.ps1`, cómo regrabar un solo capítulo, la condición de cierre y el formato de una escena.

---

## Fase 4 — Guion y escenas, capítulo por capítulo

Regla para todos los capítulos de esta fase:

1. Correr `inventario.py --faltantes` y tomar los ítems del capítulo (por patrón de id, indicados en cada task).
2. Escribir `guion/NN-nombre.md`: una sección `## Paso k` por paso, con **Narración** (texto que lee Elena, en «vos», frases cortas, sin siglas sin explicar) y **Pantalla** (qué se ve y qué se hace), y la lista `cubre:`. Es el documento que el PM revisa.
3. Escribir `escenas/NN-nombre.js` con los mismos pasos: `narracion` copiada del guion, `cubre` idéntico, `acciones` con `ctx.clic/tipear/elegir/resaltar/cartel/login/logout` y selectores por rol/texto (`page.getByRole("link", { name: "Convocatorias" })`, `getByLabel`), nunca por clase CSS.
4. `armar.ps1 -Seed` y `armar.ps1 -Capitulo NN`; mirar `salida/NN/escena.mp4` entero.
5. `inventario.py --faltantes`: los ids del capítulo ya no aparecen. Lo que de verdad no corresponde mostrar va a `no-aplica.yml` con motivo.
6. Cada paso que mencione un comportamiento no obvio cita la decisión (`cubre: ["req:NNN"]`) después de leerla con `scripts\requerimientos.py --ver NNN`.

Antes de empezar, con `admin.becas` abierto en el navegador, recorrer el menú «Programas» a mano para confirmar los textos reales de los links y botones que se van a nombrar en la narración.

### Task 4.0: Capítulo 00 — Introducción y glosario

Ítems: `estado:*` (presentados como mapa, se vuelven a cubrir en detalle después), `req:*` de glosario.
Pasos: cartel del video → cartel «Cómo está organizado Becas» con un diagrama estático (`lib/cartel.html` acepta también `?cuerpo=` con HTML simple) programa → segmento → subsegmento → convocatoria → relevamiento → caso → los 5 roles en una línea cada uno → «qué vamos a ver» (lista de capítulos). Sin login. Duración objetivo 3 min.

### Task 4.1: Capítulo 01 — Roles y usuarios

Ítems: `url:becas:inicio`, pantallas de usuarios y roles (`users`: alta de usuario, asignación de rol, ABM de roles — tomar sus urls de `users/urls.py` y agregarlas al inventario en `inventario.py` como `url:users:*` si no están), `req:*` sobre RBAC/correo compartido.
Pasos: login `admin.becas` → sidebar «Programas» → Usuarios: alta de `nuevo.coordinador` con rol Coordinador (mostrar la clave provisoria y el cambio obligatorio en el primer login) → ABM de Roles: abrir «Becas — Coordinador» y recorrer el árbol de capacidades explicando `ver/crear/editar` y el alcance por programa → logout → login con `coord.regional`: qué menús desaparecen → login `referente` → login `territorial`: pantalla de «no tenés acceso al backoffice» (o lo que muestre). Cubrir `estado` de usuario activo/inactivo.

### Task 4.2: Capítulo 02 — Configuración del programa

Ítems: `url:becas:programa_*`, `segmento_*`, `subsegmento_*`, `requisito_*`, `pregunta_*`, `coordinador_*`, `gestionar_pausa`, `proceso_masivo*`; `campo:ProgramaSiis*`, `SegmentoForm`, `SegmentoCreateForm`, `SubsegmentoForm`, `GrupoRequisitoForm`, `AsignacionCoordinadorForm`; `msg:` de `views/configuracion.py` y `services/` de segmentos/cupo (RN-40: la suma de subsegmentos no supera el segmento — provocarlo).
Pasos (rol `admin.becas`): detalle del programa → identificadores SIIS → segmento nuevo «Oficios» campo por campo (cada opción explicada) → subsegmentos con cupo, forzar el error de RN-40 → requisitos y preguntas globales (cada tipo de pregunta) → coordinadores (alta, baja, `activo`) → pausar el segmento «Oficios» con motivo, ver el cartel de pausa heredada en una convocatoria, reanudar → proceso masivo a SIIS (en modo de prueba) → dashboard del programa.

### Task 4.3: Capítulo 03 — Convocatorias y constructor de formularios

Ítems: `url:becas:convocatoria_*`, `formulario_*` (constructor, `views/diseno.py`); `campo:ConvocatoriaForm`, `Item*Form`, `FormularioTipoNuevoForm`; `msg:` de `views/diseno.py`, `services/convocatorias*`; `estado` de convocatoria (activa / cerrada automáticamente / reactivada).
Pasos (`coordinador`): listado y filtros → alta de convocatoria (segmento con y sin subsegmento, fechas, descripción, `activo`) → constructor: grupo, texto, etiqueta, campo propio de cada tipo, orden, vista previa → padrón: subir CSV (archivo ficticio generado en el seed o en `salida/`), ver cruce → convocatoria «cerrada» del seed: qué la cerró (cron), reactivar → exportar beneficiarios CSV.

### Task 4.4: Capítulo 04 — Relevamientos

Ítems: `url:becas:relevamiento_*`; `campo:RelevamientoForm`, `CupoRelevamientoForm`, `ReasignarTerritorialForm`, `ReprogramarForm`, `VolverACampoForm`; `accion:` de `relevamiento_detail.html` y `relevamiento_form*`; `estado:Relevamiento.*`; `msg:` de `views/relevamientos.py`, `services/relevamientos*`, `vencimientos.py`.
Pasos (`coordinador`): listado → alta territorial (zona, fechas, cupo, territorial, solapamiento informativo) → alta público: link, copiar, QR si existe → detalle del «en_curso» → finalizar (confirmación) → volver a campo con fecha nueva (el caso de hoy; `req` del cierre por vencimiento) → reprogramar → reasignar → cupo del relevamiento → correr `procesar_vencimientos` a mano (`docker compose exec`) y mostrar cómo el «vencido» pasó a En revisión; narrar que en producción corre solo a las 03:10.

### Task 4.5: Capítulo 05 — Inscripción pública por link

Ítems: `url:portal:inscripcion_*`; `campo:InscripcionPaso1Form`, `InscripcionPaso2Form`; `msg:` de `portal/views/inscripcion.py`, `portal/services/inscripcion.py`, templates `no_disponible`, `ya_inscripto`, `demasiados_intentos`.
Pasos (sin login, contexto nuevo del navegador): abrir link del «publico» → paso 1 con DNI `90000041` → captcha → paso 2 campo por campo, adjuntos, apoderado para menor (segundo intento con una fecha de nacimiento de menor) → comprobante → repetir con el mismo DNI: «ya inscripto» → link «con_padron» con DNI fuera del padrón → link «vencido»: «ya no admite inscripciones» → link «asignado» (todavía no abrió) → link «cupo_lleno» → link «pausado».

### Task 4.6: Capítulo 06 — App de campo (móvil)

Ítems: `app:*`; `msg:` de `programas/api/views.py` (`_error(...)`: fuera de período, no en curso, pausado, DNI ya relevado…).
Escena con `movil: true`, `ctx.baseApp`. Pasos (`territorial`): login → lista de relevamientos asignados (el «asignado» y el «en_curso») → iniciar el «asignado» (fuera de período: error; luego el que sí está en fecha) → cargar persona: DNI del padrón, datos que vuelven de identidad en modo de prueba, formulario dinámico, fotos (subir un archivo de `lib/`), GPS (narrar) → DNI ya relevado → modo sin conexión: cortar la red con `context.setOffline(true)`, cargar una persona, reconectar y ver la cola subir → finalizar → intentar cargar en uno pausado.

### Task 4.7: Capítulo 07 — Revisión de casos

Ítems: `url:becas:revision_*`; `campo:FormularioRevisionForm`, `ForzarIdentidadForm`, `CiudadanoGeneroRevisionForm`, `RevisionPersonasFiltroForm`; `accion:` de los templates de revisión; `estado:Formulario.*`; `msg:` de `views/revision.py`, `services/revision.py`, `validacion_siis.py`, `siis.py`.
Pasos (`coordinador`): bandeja y filtros → detalle de un caso ENVIADO: datos, respuestas, adjuntos, identidad validada vs. manual → revalidar identidad (RENAPER en modo de prueba), forzar identidad, validar contra padrón, corregir género → aprobar → rechazar con motivo → reenviar aviso → enviar a SIIS → terminar la revisión del relevamiento (y por qué no vuelve a campo después) → entrar como `coord.regional`: solo ver.

### Task 4.8: Capítulo 08 — Cupo, lista de espera y beneficiarios

Ítems: `url:becas:cupo_*`, `beneficiario_*`, `espera_*`; `msg:` de `services/cupo.py`.
Pasos (`coordinador`): cupo del segmento (las tres acepciones: cupo del segmento, sin distribuir, libres — `req` RED-49) → dar de baja un aprobado con motivo → lista de espera → promover → la solapa Becas del legajo del ciudadano.

### Task 4.9: Capítulo 09 — Reportes, dashboard y roles de consulta

Ítems: `url:becas:reporte*`, `programa_dashboard_*`; `campo:ReporteBecasFiltroForm`, `DashboardBecasFiltroForm`.
Pasos: `coordinador`: reportes con cada filtro, exportar → dashboard → `referente`: qué ve y qué no → `coord.regional`: el dashboard acotado a su subsegmento.

### Task 4.10: Capítulo 10 — Errores frecuentes y soluciones

Ítems: todo `msg:` que haya quedado sin cubrir + los de la lista del spec. Cada error es un paso con tres frases: qué se ve, por qué pasa, qué hacer. Se reutilizan las pantallas ya grabadas pero provocando el error en vivo. Incluir: el mensaje de sesión cerrada en otra computadora (abrir un segundo contexto con el mismo usuario), cambio de contraseña obligatorio, menú que no aparece por falta de capacidad (crear un rol sin `relevamiento.ver` y entrar con él).

---

## Fase 5 — Cierre

### Task 5.1: Cobertura en 0 y revisión del video completo

- [ ] `& .\.venv312\Scripts\python.exe scripts\video_becas\inventario.py --faltantes` → `0 sin cubrir`. Cada línea de `no-aplica.yml` tiene motivo.
- [ ] `armar.ps1 -Seed; armar.ps1 -Todo` desde cero (base re-sembrada) → `salida/video-becas.mp4`.
- [ ] Ver el video entero con el guion al lado. Anotar en `guion/REVISION.md` cada desvío (voz que adelanta, texto cortado, pantalla distinta a la narrada) y corregir la escena. Regrabar solo esas.
- [ ] Entregar al PM `video-becas.mp4` + `.srt` (fuera del repo: carpeta compartida que el PM indique).

### Task 5.2: Registro y verificación de gates

- [ ] Entrada en `docs/internal/requerimientos.md` (plantilla del archivo): qué se construyó, decisiones (local con datos ficticios, voz Elena, inventario como condición de cierre), cómo regrabar, pendientes (tipo: regrabar al cambiar una pantalla). Fila en el índice.
- [ ] `& $env:PY_VENV scripts\requerimientos.py --check` → OK.
- [ ] `& $env:PY_VENV manage.py check`; `& $env:PY_VENV manage.py makemigrations --check --dry-run` (sin migraciones: el seed no toca modelos); `ruff check .` sobre lo tocado; suite `programas.tests.test_seed_video_becas` y `core.tests.test_comandos_peligrosos` en verde.
- [ ] `scripts\check_docs_client.py` no aplica (nada en `docs/client/`). `design_audit.py --ratchet` no aplica (sin templates nuevos).
- [ ] PR contra `development` cuando el usuario lo pida, con el video **no** adjunto al repo.
