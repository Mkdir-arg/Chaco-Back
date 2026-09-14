# Envío de beneficiarios a SIIS — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cada caso de Becas que queda APROBADO se da de alta como beneficiario en la tabla intermedia de SIIS (`POST /api/v1/auth/tab-intermedia`), con registro auditable por intento, corrección de datos y reintento desde la pantalla del caso.

**Architecture:** Se extiende el `SiisAPIClient` existente con el alta y los catálogos; un módulo puro nuevo `siis_envio.py` arma el payload desde el ciudadano, las respuestas del formulario marcadas con un "destino SIIS" y las correcciones del coordinador (`Formulario.datos_siis`); cada intento queda en `EnvioSIIS`. El disparo va en las vistas, después de que el servicio atómico de aprobación retornó, y nunca bloquea ni revierte la aprobación.

**Tech Stack:** Django 5.2, MySQL 8 (sin constraints condicionales), `requests`, runner de tests de Django (no pytest), Tailwind committeado, vanilla JS en los templates.

**Spec:** `docs/plans/2026-09-14-siis-envio-beneficiarios-design.md`

## Global Constraints

- Todo `python` por el venv: `$env:PY_VENV = "$PWD\.venv\Scripts\python.exe"`, `$env:DJANGO_SECRET_KEY="test-key"`, `$env:PYTEST_RUNNING="1"`, `$env:DJANGO_SYNCDB_PROJECT_APPS="True"`.
- Tests: `& $env:PY_VENV manage.py test <modulo>` (runner de Django). Bash: exportar `PYTHONIOENCODING=utf-8`.
- Autorización solo por capacidad (`puede`, `@requiere`), nunca por nombre de grupo. No se crean capacidades nuevas: reenvío y corrección usan `becas.revision.editar`; función del programa usa `becas.programa.administrar`.
- Modelos nuevos heredan de `core.models.TimeStamped` **salvo** los registros inmutables tipo `ValidacionSIS`, que usan `models.Model` + `creado` (se sigue ese hermano).
- Nombres de campo del payload **exactamente** los del manual v4.2; no se inventan campos.
- UI: extender lo existente en `formulario_detalle.html`; sin hex sueltos, sin `confirm()` nativo; `scripts/design_audit.py --changed` = 0 errores y `scripts/compile_templates.py` = 0.
- Tras cambiar modelos: migración inmediata; `makemigrations --check --dry-run` limpio.
- Rama de trabajo: `feature/siis-envio-beneficiarios` desde `origin/development`, en un worktree propio (hay sesiones concurrentes sobre el checkout principal).
- Cierre: entrada nueva en `docs/internal/requerimientos.md` + fila del índice + `scripts/requerimientos.py --check` OK.

---

## Mapa de archivos

| Archivo | Responsabilidad |
|---|---|
| `programas/models/__init__.py` | `PreguntaGlobal.destino_siis`, `ProgramaSiis.siis_funcion_id/_nombre`, `Formulario.datos_siis`, `EnvioSIIS` |
| `programas/migrations/0060_siis_envio_beneficiarios.py` | una sola migración |
| `programas/services/siis.py` | cliente HTTP: `cargar_beneficiario`, `catalogo`, `funciones_programa` |
| `programas/services/siis_envio.py` (nuevo) | puro: `calcular_cuil`, `parsear_direccion`, `Catalogos`, `armar_payload`, `enviar_beneficiario_a_siis`, `mensaje_envio` |
| `programas/forms.py` | `destino_siis` en `PreguntaGlobalForm`, `DatosSiisForm`, `ProgramaSiisFuncionForm` |
| `programas/views/revision.py` | disparo en aprobar, `formulario_enviar_siis`, `formulario_datos_siis`, `siis_localidades_json`, contexto |
| `programas/views/cupo.py` | disparo en promover |
| `programas/views/configuracion.py` | `programa_funcion_siis` |
| `programas/urls.py` | rutas nuevas |
| `programas/management/commands/reenviar_siis_pendientes.py` (nuevo) | reintento de errores técnicos |
| `programas/templates/programas/becas/revision/formulario_detalle.html` | sección "Envío a SIIS" + modal de datos |
| `programas/templates/programas/becas/config/programa_detail.html` | tarjeta "Alta de beneficiarios en SIIS" |
| `programas/tests/test_siis_envio.py` (nuevo) | unitarios del módulo puro y del servicio |
| `programas/tests/test_siis_service.py` | cliente |
| `programas/tests/test_becas_revision.py` | disparo, reenvío, corrección |
| `programas/tests/test_becas_config.py` | destino en pregunta, función en programa |
| `docs/internal/temas/siis-api.md`, `docs/internal/requerimientos.md` | registro |

---

### Task 1: Modelos y migración

**Files:**
- Modify: `programas/models/__init__.py` (`ProgramaSiis` ~L1207, `PreguntaGlobal` ~L1858, `Formulario` ~L2055, después de `ValidacionSIS` ~L2370)
- Create: `programas/migrations/0060_siis_envio_beneficiarios.py` (generada)
- Test: `programas/tests/test_siis_envio.py`

**Interfaces:**
- Produces: `PreguntaGlobal.DestinoSiis` (TextChoices), `PreguntaGlobal.destino_siis`, `ProgramaSiis.siis_funcion_id`, `ProgramaSiis.siis_funcion_nombre`, `Formulario.datos_siis`, `Formulario.envio_siis_vigente` (property), `EnvioSIIS` con `Estado` {ENVIADO, INCOMPLETO, RECHAZADO, ERROR}.

- [ ] **Step 1: Test de modelos**

```python
# programas/tests/test_siis_envio.py
from datetime import date
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from legajos.models import Ciudadano
from programas.models import (
    Convocatoria,
    EnvioSIIS,
    Formulario,
    PreguntaGlobal,
    ProgramaSiis,
    Relevamiento,
    Segmento,
    TipoCampo,
)


class _BaseEnvioTest(TestCase):
    def setUp(self):
        call_command("seed_becas", stdout=StringIO())
        self.programa = ProgramaSiis.objects.create(
            nombre="Ñachec",
            siis_programa_id=79,
            siis_programa_datos={"id": 79, "nombre": "Ñachec", "jurisdiccion_id": 28},
            siis_funcion_id=4,
            siis_funcion_nombre="Nivel Operativo",
        )
        self.segmento = Segmento.objects.create(nombre="Seg", cupo_maximo=10, programa=self.programa)
        self.convocatoria = Convocatoria.objects.create(
            nombre="Conv", segmento=self.segmento, fecha_inicio=date(2026, 1, 1), fecha_fin=date(2026, 12, 31)
        )
        self.user = User.objects.create_user("coord", password="x")
        self.relevamiento = Relevamiento.objects.create(
            convocatoria=self.convocatoria, territorial=self.user, fecha_asignada=date(2026, 6, 1), zona="A"
        )
        self.ciudadano = Ciudadano.objects.create(
            dni="20301234", nombre="Juan Carlos", apellido="Perez", fecha_nacimiento=date(1995, 6, 15), genero="M"
        )
        self.formulario = Formulario.objects.create(
            relevamiento=self.relevamiento,
            ciudadano=self.ciudadano,
            celular="3624123456",
            email_contacto="juan.perez@email.com",
            estado=Formulario.Estado.APROBADO,
            validado_renaper=True,
            data={"globales": {}, "requisitos": {}},
        )


class ModelosEnvioTests(_BaseEnvioTest):
    def test_envio_vigente_es_el_ultimo_enviado(self):
        EnvioSIIS.objects.create(
            formulario=self.formulario, estado=EnvioSIIS.Estado.ERROR, documento="20301234", codigo_error="ERROR_TECNICO"
        )
        ok = EnvioSIIS.objects.create(
            formulario=self.formulario, estado=EnvioSIIS.Estado.ENVIADO, documento="20301234", siis_id=26
        )
        self.assertEqual(self.formulario.envio_siis_vigente, ok)
        self.assertTrue(self.formulario.informado_a_siis)

    def test_pregunta_con_destino(self):
        p = PreguntaGlobal.objects.create(
            texto="Localidad", tipo=TipoCampo.STRING, destino_siis=PreguntaGlobal.DestinoSiis.LOCALIDAD_ACTUAL
        )
        self.assertEqual(p.destino_siis, "loc_actual")
        self.assertEqual(self.formulario.datos_siis, {})
```

- [ ] **Step 2: Correr y ver fallar**

Run: `& $env:PY_VENV manage.py test programas.tests.test_siis_envio.ModelosEnvioTests`
Expected: FAIL — `ImportError: cannot import name 'EnvioSIIS'`.

- [ ] **Step 3: Modelos**

En `ProgramaSiis`, después de `siis_verificado_en`:

```python
    # Alta de beneficiarios (tabla intermedia): función/nivel dentro del programa,
    # elegida del catálogo ``GET /api/v1/auth/catalogos/funciones?id_programa=``.
    siis_funcion_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="Función SIIS para el alta de beneficiarios"
    )
    siis_funcion_nombre = models.CharField(max_length=200, blank=True, default="", verbose_name="Nombre de la función SIIS")
```

En `PreguntaGlobal`, antes de `class Meta`:

```python
    class DestinoSiis(models.TextChoices):
        PROVINCIA_ACTUAL = "prov_actual", "Provincia del domicilio"
        LOCALIDAD_ACTUAL = "loc_actual", "Localidad del domicilio"
        BARRIO = "barrio_actual", "Barrio"
        CALLE_ALTURA = "calle_altura", "Calle y altura (piso, dpto)"
        ESTADO_CIVIL = "est_civil", "Estado civil"
        PROVINCIA_NACIMIENTO = "prov_nacim", "Provincia de nacimiento"
        LOCALIDAD_NACIMIENTO = "loc_nacim", "Localidad de nacimiento"

    destino_siis = models.CharField(
        max_length=20,
        choices=DestinoSiis.choices,
        blank=True,
        default="",
        db_index=True,
        verbose_name="Este dato alimenta a SIIS como",
        help_text="Con qué campo del alta de beneficiarios en SIIS se corresponde la respuesta. Una pregunta activa por destino.",
    )
```

En `Formulario`, después de `datos_identificacion`:

```python
    # Correcciones del coordinador para el alta en SIIS (claves = campos de la API).
    # Pisan lo derivado de las respuestas; nunca tocan ``data``.
    datos_siis = models.JSONField(default=dict, blank=True, verbose_name="Datos corregidos para SIIS")
```

y como métodos de `Formulario` (junto a otras properties):

```python
    @property
    def envio_siis_vigente(self):
        return self.envios_sis.order_by("-creado").first()

    @property
    def informado_a_siis(self):
        return self.envios_sis.filter(estado=EnvioSIIS.Estado.ENVIADO).exists()
```

Después de `ValidacionSIS`:

```python
class EnvioSIIS(models.Model):
    """Intento inmutable de alta de un beneficiario en la tabla intermedia de SIIS."""

    class Estado(models.TextChoices):
        ENVIADO = "ENVIADO", "Enviado"
        INCOMPLETO = "INCOMPLETO", "Datos incompletos"
        RECHAZADO = "RECHAZADO", "Rechazado por SIIS"
        ERROR = "ERROR", "Error técnico"

    formulario = models.ForeignKey(
        Formulario, on_delete=models.CASCADE, related_name="envios_sis", verbose_name="Formulario"
    )
    estado = models.CharField(max_length=15, choices=Estado.choices, db_index=True)
    siis_id = models.PositiveIntegerField(null=True, blank=True, verbose_name="ID asignado por SIIS")
    id_programa = models.PositiveIntegerField(null=True, blank=True)
    id_funcion = models.PositiveIntegerField(null=True, blank=True)
    documento = models.CharField(max_length=20)
    codigo_error = models.CharField(max_length=40, blank=True, default="")
    detalles = models.JSONField(default=dict, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    respuesta = models.JSONField(default=dict, blank=True)
    solicitado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="envios_sis_solicitados"
    )
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado"]
        verbose_name = "Envío a SIIS"
        verbose_name_plural = "Envíos a SIIS"

    def __str__(self):
        return f"Formulario #{self.formulario_id} · {self.estado}"

    @property
    def reintentable(self):
        return self.estado == self.Estado.ERROR
```

- [ ] **Step 4: Migración y tests**

Run: `& $env:PY_VENV manage.py makemigrations programas -n siis_envio_beneficiarios` → `0060_siis_envio_beneficiarios.py`.
Run: `& $env:PY_VENV manage.py test programas.tests.test_siis_envio.ModelosEnvioTests` → PASS.
Run: `& $env:PY_VENV manage.py makemigrations --check --dry-run` → "No changes detected".

- [ ] **Step 5: Commit**

```bash
git add programas/models/__init__.py programas/migrations/0060_siis_envio_beneficiarios.py programas/tests/test_siis_envio.py
git commit -m "feat(siis): modelos para el alta de beneficiarios (EnvioSIIS, destino de preguntas, funcion del programa)"
```

---

### Task 2: Cliente SIIS — alta y catálogos

**Files:**
- Modify: `programas/services/siis.py`
- Test: `programas/tests/test_siis_service.py`

**Interfaces:**
- Produces: `SiisAPIClient.cargar_beneficiario(payload) -> dict` con claves `success`, `siis_id`, `codigo`, `reintentable`, `detalles`, `error`, `data`; `SiisAPIClient.catalogo(nombre) -> list[dict]` (`nombre` ∈ `provincias|localidades|estados-civiles|tipos-documento|jurisdicciones`); `SiisAPIClient.funciones_programa(id_programa) -> list[dict]`; funciones módulo `cargar_beneficiario`, `catalogo`, `funciones_programa`; constantes `CATALOGO_CACHE_LARGO = 24*3600`, `CATALOGO_CACHE_KEY = "siis_api:catalogo:{}"`.

- [ ] **Step 1: Tests**

Agregar a `programas/tests/test_siis_service.py`, dentro de `SiisClientTests`:

```python
    @patch("programas.services.siis.requests.post")
    def test_cargar_beneficiario_201_devuelve_el_id(self, post):
        cache.set(TOKEN_CACHE_KEY, "abc", 60)
        respuesta = Mock(status_code=201)
        respuesta.json.return_value = {"status": "OK", "total_insertados": 1, "ids_generados": [26], "registros": [{"id": 26}]}
        post.return_value = respuesta

        r = SiisAPIClient().cargar_beneficiario({"dni": 1, "tdoc": 1})

        self.assertTrue(r["success"])
        self.assertEqual(r["siis_id"], 26)
        self.assertTrue(post.call_args.args[0].endswith("/api/v1/auth/tab-intermedia"))
        self.assertEqual(post.call_args.kwargs["json"], {"dni": 1, "tdoc": 1})

    @patch("programas.services.siis.requests.post")
    def test_cargar_beneficiario_201_sin_ids_generados_lee_registros(self, post):
        cache.set(TOKEN_CACHE_KEY, "abc", 60)
        respuesta = Mock(status_code=201)
        respuesta.json.return_value = {"registros": [{"id": 31, "dni": 1}]}
        post.return_value = respuesta
        self.assertEqual(SiisAPIClient().cargar_beneficiario({})["siis_id"], 31)

    @patch("programas.services.siis.requests.post")
    def test_cargar_beneficiario_400_trae_detalles_por_campo(self, post):
        cache.set(TOKEN_CACHE_KEY, "abc", 60)
        respuesta = Mock(status_code=400)
        respuesta.json.return_value = {
            "error": "DATOS_INVALIDOS",
            "mensaje": "Uno o más campos no superaron las validaciones.",
            "detalles": {"barrio_actual": ["mínimo 4 caracteres"]},
        }
        post.return_value = respuesta

        r = SiisAPIClient().cargar_beneficiario({})

        self.assertFalse(r["success"])
        self.assertEqual(r["codigo"], "DATOS_INVALIDOS")
        self.assertFalse(r["reintentable"])
        self.assertEqual(r["detalles"], {"barrio_actual": ["mínimo 4 caracteres"]})

    @patch("programas.services.siis.requests.post")
    def test_cargar_beneficiario_401_invalida_el_token(self, post):
        cache.set(TOKEN_CACHE_KEY, "abc", 60)
        respuesta = Mock(status_code=401)
        respuesta.json.return_value = {"error": "UNAUTHORIZED"}
        post.return_value = respuesta
        r = SiisAPIClient().cargar_beneficiario({})
        self.assertEqual(r["codigo"], "UNAUTHORIZED")
        self.assertTrue(r["reintentable"])
        self.assertIsNone(cache.get(TOKEN_CACHE_KEY))

    @patch("programas.services.siis.requests.post")
    def test_cargar_beneficiario_503_es_reintentable(self, post):
        cache.set(TOKEN_CACHE_KEY, "abc", 60)
        respuesta = Mock(status_code=503)
        respuesta.json.return_value = {"error": "ERROR_BD_LEGACY"}
        post.return_value = respuesta
        r = SiisAPIClient().cargar_beneficiario({})
        self.assertEqual(r["codigo"], "ERROR_BD_LEGACY")
        self.assertTrue(r["reintentable"])

    @patch("programas.services.siis.requests.post", side_effect=requests.Timeout())
    def test_cargar_beneficiario_timeout_es_error_tecnico(self, post):
        cache.set(TOKEN_CACHE_KEY, "abc", 60)
        r = SiisAPIClient().cargar_beneficiario({})
        self.assertFalse(r["success"])
        self.assertEqual(r["codigo"], "ERROR_TECNICO")
        self.assertTrue(r["reintentable"])

    @patch("programas.services.siis.requests.get")
    def test_catalogo_normaliza_y_cachea(self, get):
        cache.set(TOKEN_CACHE_KEY, "abc", 60)
        respuesta = Mock(status_code=200)
        respuesta.json.return_value = {"data": [{"id": 22, "nombre": "Chaco"}, {"id": "x", "nombre": "Mal"}, {"id": 2}]}
        respuesta.raise_for_status.return_value = None
        get.return_value = respuesta

        items = SiisAPIClient().catalogo("provincias")
        SiisAPIClient().catalogo("provincias")

        self.assertEqual(items, [{"id": 22, "nombre": "Chaco"}])
        self.assertEqual(get.call_count, 1)
        self.assertTrue(get.call_args.args[0].endswith("/api/v1/auth/catalogos/provincias"))

    @patch("programas.services.siis.requests.get")
    def test_funciones_programa_pide_por_id_programa(self, get):
        cache.set(TOKEN_CACHE_KEY, "abc", 60)
        respuesta = Mock(status_code=200)
        respuesta.json.return_value = [{"id": 4, "nombre": "Nivel Operativo", "id_programa": 79}]
        respuesta.raise_for_status.return_value = None
        get.return_value = respuesta

        items = SiisAPIClient().funciones_programa(79)

        self.assertEqual(items[0]["id"], 4)
        self.assertIn("id_programa=79", get.call_args.args[0])

    def test_catalogo_nombre_desconocido(self):
        with self.assertRaises(ValueError):
            SiisAPIClient().catalogo("otra-cosa")
```

- [ ] **Step 2: Correr y ver fallar**

Run: `& $env:PY_VENV manage.py test programas.tests.test_siis_service` → FAIL con `AttributeError: 'SiisAPIClient' object has no attribute 'cargar_beneficiario'`.

- [ ] **Step 3: Implementación**

En `programas/services/siis.py`, constantes junto a las otras:

```python
CATALOGO_CACHE_KEY = "siis_api:catalogo:{}"
CATALOGO_CACHE_LARGO = 24 * 60 * 60
CATALOGOS_MAESTROS = ("provincias", "localidades", "estados-civiles", "tipos-documento", "jurisdicciones")
TAB_INTERMEDIA_PATH = "/api/v1/auth/tab-intermedia"
# Códigos de la matriz de respuestas del manual v4.2 (sección 6).
CODIGOS_REINTENTABLES = {"UNAUTHORIZED", "ERROR_BD_LEGACY", "ERROR_INTERNO", "ERROR_TECNICO"}
```

Métodos en `SiisAPIClient`, después de `validar_compatibilidad`:

```python
    @staticmethod
    def _normalizar_items(items):
        """Ítems con ``id`` entero y ``nombre``; conserva el resto de las claves
        (las localidades pueden traer su provincia, las funciones su programa)."""
        resultado = []
        for item in items:
            if not isinstance(item, dict):
                continue
            nombre = item.get("nombre") or item.get("descripcion") or item.get("denominacion")
            try:
                item_id = int(item.get("id"))
            except (TypeError, ValueError):
                continue
            if not nombre:
                continue
            normalizado = dict(item)
            normalizado["id"] = item_id
            normalizado["nombre"] = str(nombre).strip()
            resultado.append(normalizado)
        return resultado

    def catalogo(self, nombre):
        """Catálogo maestro (sección 2 del manual), cacheado 24 h: cambian casi nunca."""
        if nombre not in CATALOGOS_MAESTROS:
            raise ValueError(f"Catálogo SIIS desconocido: {nombre}")
        clave = CATALOGO_CACHE_KEY.format(nombre)
        cached = cache.get(clave)
        if cached is not None:
            return cached
        body = self._cargar_catalogo(
            f"/api/v1/auth/catalogos/{nombre}",
            f"SIIS no encontró el catálogo de {nombre.replace('-', ' ')}.",
        )
        items = self._normalizar_items(self._items(body, nombre, "items", "results"))
        cache.set(clave, items, CATALOGO_CACHE_LARGO)
        return items

    def funciones_programa(self, id_programa):
        clave = CATALOGO_CACHE_KEY.format(f"funciones:{int(id_programa)}")
        cached = cache.get(clave)
        if cached is not None:
            return cached
        body = self._cargar_catalogo(
            f"/api/v1/auth/catalogos/funciones?id_programa={int(id_programa)}",
            "SIIS no encontró las funciones del programa.",
        )
        items = self._normalizar_items(self._items(body, "funciones", "items", "results"))
        cache.set(clave, items, CATALOGO_CACHE_LARGO)
        return items

    @staticmethod
    def _siis_id_de(body):
        if not isinstance(body, dict):
            return None
        ids = body.get("ids_generados")
        if isinstance(ids, list) and ids:
            try:
                return int(ids[0])
            except (TypeError, ValueError):
                pass
        registros = body.get("registros")
        if isinstance(registros, list) and registros and isinstance(registros[0], dict):
            try:
                return int(registros[0].get("id"))
            except (TypeError, ValueError):
                pass
        return None

    def cargar_beneficiario(self, payload):
        """Alta individual en la tabla intermedia (Modalidad A). Nunca lanza: el
        resultado dice si hay que corregir datos (400) o reintentar (401/5xx/red)."""
        try:
            response = instrument_external_call(
                "siis",
                requests.post,
                f"{self.base_url}{TAB_INTERMEDIA_PATH}",
                json=payload,
                headers={"Authorization": f"Bearer {self._token()}"},
                timeout=self.timeout,
            )
        except (requests.RequestException, TypeError, ValueError, _SiisConfigurationError) as exc:
            logger.error("Error técnico al cargar un beneficiario en SIIS (%s)", type(exc).__name__)
            return {
                "success": False,
                "codigo": "ERROR_TECNICO",
                "reintentable": True,
                "error": "No se pudo conectar con SIIS.",
                "detalles": {},
                "data": {},
            }
        try:
            body = response.json()
        except ValueError:
            body = {}
        if not isinstance(body, dict):
            body = {"respuesta": body}
        if response.status_code == 401:
            cache.delete(TOKEN_CACHE_KEY)
        if response.status_code in (200, 201):
            return {"success": True, "siis_id": self._siis_id_de(body), "codigo": "", "reintentable": False, "detalles": {}, "data": body}
        codigo = str(body.get("error") or "").strip().upper()
        if not codigo:
            codigo = {400: "DATOS_INVALIDOS", 401: "UNAUTHORIZED", 503: "ERROR_BD_LEGACY"}.get(response.status_code, "ERROR_INTERNO")
        detalles = body.get("detalles") if isinstance(body.get("detalles"), dict) else {}
        return {
            "success": False,
            "codigo": codigo,
            "reintentable": codigo in CODIGOS_REINTENTABLES or response.status_code >= 500,
            "error": body.get("mensaje") or body.get("detail") or f"SIIS respondió HTTP {response.status_code}.",
            "detalles": detalles,
            "data": body,
        }
```

Funciones de módulo al final del archivo:

```python
def cargar_beneficiario(payload):
    return SiisAPIClient().cargar_beneficiario(payload)


def catalogo(nombre):
    return SiisAPIClient().catalogo(nombre)


def funciones_programa(id_programa):
    return SiisAPIClient().funciones_programa(id_programa)
```

- [ ] **Step 4: Correr**

Run: `& $env:PY_VENV manage.py test programas.tests.test_siis_service` → PASS (los 19 previos + 9 nuevos).

- [ ] **Step 5: Commit**

```bash
git add programas/services/siis.py programas/tests/test_siis_service.py
git commit -m "feat(siis): alta de beneficiarios (tab-intermedia) y catalogos maestros en el cliente"
```

---

### Task 3: Módulo puro — CUIL, dirección y armado del payload

**Files:**
- Create: `programas/services/siis_envio.py`
- Test: `programas/tests/test_siis_envio.py`

**Interfaces:**
- Consumes: `catalogo(nombre)` de Task 2; `respuesta_de(data, clave)` de `programas/services/dashboard_becas.py`; `PreguntaGlobal.DestinoSiis`.
- Produces: `calcular_cuil(dni, sexo) -> (prefijo:int, digito:int)`; `parsear_direccion(texto) -> dict(calle, nro, piso, dpto)`; `clave_nombre(texto) -> str`; `class Catalogos` con `provincia_id(nombre)`, `localidad_id(nombre, provincia_id=None)`, `estado_civil_id(nombre)`; `class CatalogoNoDisponible(Exception)`; `armar_payload(formulario, catalogos=None, hoy=None) -> (payload: dict, faltantes: dict[str, str])`.

- [ ] **Step 1: Tests**

Agregar a `programas/tests/test_siis_envio.py`:

```python
from unittest.mock import patch

from django.test import SimpleTestCase

from programas.services import siis_envio
from programas.services.siis import SiisCatalogError
from programas.services.siis_envio import Catalogos, armar_payload, calcular_cuil, parsear_direccion


class CuilTests(SimpleTestCase):
    def test_masculino(self):
        # 20-20301234-? → verificador conocido
        self.assertEqual(calcular_cuil("20301234", "M")[0], 20)

    def test_femenino(self):
        self.assertEqual(calcular_cuil("20301234", "F")[0], 27)

    def test_digito_verificador_modulo_11(self):
        # Caso público: CUIL 20-12345678-6
        self.assertEqual(calcular_cuil("12345678", "M"), (20, 6))

    def test_resto_diez_cambia_a_23(self):
        # Se busca un DNI cuyo cálculo con prefijo 20 dé 10: se verifica la regla, no el número.
        with patch.object(siis_envio, "_verificador", return_value=10):
            self.assertEqual(calcular_cuil("1", "M"), (23, 9))
            self.assertEqual(calcular_cuil("1", "F"), (23, 4))

    def test_resto_once_es_cero(self):
        with patch.object(siis_envio, "_verificador", return_value=11):
            self.assertEqual(calcular_cuil("1", "M"), (20, 0))


class DireccionTests(SimpleTestCase):
    def test_calle_numero_piso_dpto(self):
        self.assertEqual(
            parsear_direccion("AV. 9 DE JULIO 450 (2, B)"),
            {"calle": "AV. 9 DE JULIO", "nro": 450, "piso": 2, "dpto": "B"},
        )

    def test_calle_y_numero(self):
        self.assertEqual(parsear_direccion("Sarmiento 100"), {"calle": "Sarmiento", "nro": 100, "piso": None, "dpto": None})

    def test_sin_numero(self):
        self.assertEqual(parsear_direccion("Los Alamos S/N"), {"calle": "Los Alamos", "nro": None, "piso": None, "dpto": None})
        self.assertEqual(parsear_direccion("S/N"), {"calle": "", "nro": None, "piso": None, "dpto": None})

    def test_solo_calle(self):
        self.assertEqual(parsear_direccion("Belgrano"), {"calle": "Belgrano", "nro": None, "piso": None, "dpto": None})

    def test_piso_y_dpto_sueltos(self):
        self.assertEqual(
            parsear_direccion("Mitre 1200 piso 3 dpto A"),
            {"calle": "Mitre", "nro": 1200, "piso": 3, "dpto": "A"},
        )

    def test_vacio(self):
        self.assertEqual(parsear_direccion(""), {"calle": "", "nro": None, "piso": None, "dpto": None})


PROVINCIAS = [{"id": 22, "nombre": "Chaco"}, {"id": 2, "nombre": "Buenos Aires"}]
LOCALIDADES = [
    {"id": 1, "nombre": "Resistencia", "id_provincia": 22},
    {"id": 37, "nombre": "Juan José Castelli", "id_provincia": 22},
    {"id": 900, "nombre": "Resistencia", "id_provincia": 2},
]
ESTADOS_CIVILES = [{"id": 1, "nombre": "Soltero/a"}, {"id": 2, "nombre": "Casado/a"}, {"id": 5, "nombre": "Conviviente"}]


def _catalogo_falso(nombre):
    return {"provincias": PROVINCIAS, "localidades": LOCALIDADES, "estados-civiles": ESTADOS_CIVILES}[nombre]


class CatalogosTests(SimpleTestCase):
    def setUp(self):
        self.cat = Catalogos(cargar=_catalogo_falso)

    def test_provincia_por_nombre_normalizado(self):
        self.assertEqual(self.cat.provincia_id("chaco"), 22)
        self.assertEqual(self.cat.provincia_id("BUENOS AIRES"), 2)
        self.assertIsNone(self.cat.provincia_id("Formosa"))

    def test_localidad_acotada_a_la_provincia(self):
        self.assertEqual(self.cat.localidad_id("Resistencia", 22), 1)
        self.assertEqual(self.cat.localidad_id("Resistencia", 2), 900)
        self.assertEqual(self.cat.localidad_id("juan jose castelli", 22), 37)
        self.assertIsNone(self.cat.localidad_id("J.j castelli", 22))

    def test_localidad_sin_provincia_devuelve_solo_si_es_unica(self):
        self.assertIsNone(self.cat.localidad_id("Resistencia"))
        self.assertEqual(self.cat.localidad_id("Juan José Castelli"), 37)

    def test_estado_civil_tolera_barra_a(self):
        self.assertEqual(self.cat.estado_civil_id("Soltero/a"), 1)
        self.assertEqual(self.cat.estado_civil_id("Casada"), 2)
        self.assertEqual(self.cat.estado_civil_id("conviviente"), 5)
        self.assertIsNone(self.cat.estado_civil_id("Viudo"))

    def test_error_del_catalogo_se_propaga_como_no_disponible(self):
        def falla(nombre):
            raise SiisCatalogError("caído")

        with self.assertRaises(siis_envio.CatalogoNoDisponible):
            Catalogos(cargar=falla).provincia_id("Chaco")


class ArmarPayloadTests(_BaseEnvioTest):
    def setUp(self):
        super().setUp()
        self.cat = Catalogos(cargar=_catalogo_falso)
        D = PreguntaGlobal.DestinoSiis
        self.p_prov = PreguntaGlobal.objects.create(texto="Provincia", tipo=TipoCampo.STRING, destino_siis=D.PROVINCIA_ACTUAL, orden=101)
        self.p_loc = PreguntaGlobal.objects.create(texto="Localidad", tipo=TipoCampo.STRING, destino_siis=D.LOCALIDAD_ACTUAL, orden=102)
        self.p_barrio = PreguntaGlobal.objects.create(texto="Barrio", tipo=TipoCampo.STRING, destino_siis=D.BARRIO, orden=103)
        self.p_calle = PreguntaGlobal.objects.create(texto="Calle y altura", tipo=TipoCampo.STRING, destino_siis=D.CALLE_ALTURA, orden=104)
        self.p_civil = PreguntaGlobal.objects.create(
            texto="Estado Civil", tipo=TipoCampo.SELECTOR, opciones=["Soltero/a", "Casado/a"], destino_siis=D.ESTADO_CIVIL, orden=105
        )
        self.p_prov_nac = PreguntaGlobal.objects.create(texto="Prov nac", tipo=TipoCampo.STRING, destino_siis=D.PROVINCIA_NACIMIENTO, orden=106)
        self.p_loc_nac = PreguntaGlobal.objects.create(texto="Loc nac", tipo=TipoCampo.STRING, destino_siis=D.LOCALIDAD_NACIMIENTO, orden=107)
        self.formulario.data = {
            "globales": {
                str(self.p_prov.pk): "Chaco",
                str(self.p_loc.pk): "Resistencia",
                str(self.p_barrio.pk): "BARRIO CENTRO",
                str(self.p_calle.pk): "AV. 9 DE JULIO 450 (2, B)",
                str(self.p_civil.pk): "Soltero/a",
                str(self.p_prov_nac.pk): "Chaco",
                str(self.p_loc_nac.pk): "Resistencia",
            },
            "requisitos": {},
        }
        self.formulario.save(update_fields=["data"])

    def test_adulto_completo_calza_con_la_modalidad_a_del_manual(self):
        payload, faltantes = armar_payload(self.formulario, catalogos=self.cat, hoy=date(2026, 9, 14))
        self.assertEqual(faltantes, {})
        self.assertEqual(
            payload,
            {
                "dni": 20301234,
                "tdoc": 1,
                "cuil_pref": calcular_cuil("20301234", "M")[0],
                "cuil_dig": calcular_cuil("20301234", "M")[1],
                "apellido": "PEREZ",
                "nombre": "JUAN CARLOS",
                "sexo": "M",
                "est_civil": 1,
                "prov_nacim": 22,
                "fecha_nacim": "1995-06-15",
                "loc_nacim": 1,
                "celular": 3624123456,
                "prov_actual": 22,
                "loc_actual": 1,
                "barrio_actual": "BARRIO CENTRO",
                "calle_actual": "AV. 9 DE JULIO",
                "nro_actual": 450,
                "piso_actual": 2,
                "dpto_actual": "B",
                "correo_electron": "juan.perez@email.com",
                "jurid": 28,
                "id_plan_soc": 79,
                "id_fun_x_plan": 4,
            },
        )

    def test_localidad_sin_match_y_altura_sin_numero_quedan_como_faltantes(self):
        self.formulario.data["globales"][str(self.p_loc.pk)] = "J.j castelli"
        self.formulario.data["globales"][str(self.p_calle.pk)] = "Los Alamos S/N"
        self.formulario.save(update_fields=["data"])
        payload, faltantes = armar_payload(self.formulario, catalogos=self.cat)
        self.assertIn("loc_actual", faltantes)
        self.assertIn("nro_actual", faltantes)
        self.assertNotIn("loc_actual", payload)
        self.assertEqual(payload["calle_actual"], "Los Alamos")

    def test_barrio_numerico_se_prefija_y_barrio_corto_falta(self):
        self.formulario.data["globales"][str(self.p_barrio.pk)] = "108"
        self.formulario.save(update_fields=["data"])
        payload, faltantes = armar_payload(self.formulario, catalogos=self.cat)
        self.assertEqual(payload["barrio_actual"], "Barrio 108")
        self.formulario.data["globales"][str(self.p_barrio.pk)] = "Sur"
        self.formulario.save(update_fields=["data"])
        _, faltantes = armar_payload(self.formulario, catalogos=self.cat)
        self.assertIn("barrio_actual", faltantes)

    def test_datos_siis_pisan_las_respuestas(self):
        self.formulario.data["globales"][str(self.p_loc.pk)] = "J.j castelli"
        self.formulario.datos_siis = {"loc_actual": 37, "nro_actual": 15, "barrio_actual": "Barrio Norte"}
        self.formulario.save(update_fields=["data", "datos_siis"])
        payload, faltantes = armar_payload(self.formulario, catalogos=self.cat)
        self.assertEqual(faltantes, {})
        self.assertEqual(payload["loc_actual"], 37)
        self.assertEqual(payload["nro_actual"], 15)
        self.assertEqual(payload["barrio_actual"], "Barrio Norte")

    def test_sin_preguntas_marcadas_faltan_los_campos_del_domicilio(self):
        PreguntaGlobal.objects.filter(destino_siis__gt="").update(destino_siis="")
        payload, faltantes = armar_payload(self.formulario, catalogos=self.cat)
        for campo in ("prov_actual", "loc_actual", "barrio_actual", "calle_actual", "nro_actual", "est_civil", "prov_nacim", "loc_nacim"):
            self.assertIn(campo, faltantes, campo)

    def test_menor_sin_apoderado_falta_y_con_apoderado_manda_los_siete_campos(self):
        self.ciudadano.fecha_nacimiento = date(2015, 3, 10)
        self.ciudadano.save(update_fields=["fecha_nacimiento"])
        _, faltantes = armar_payload(self.formulario, catalogos=self.cat, hoy=date(2026, 9, 14))
        self.assertIn("dni_apoderado", faltantes)

        self.formulario.apoderado_dni = "25999888"
        self.formulario.apoderado_nombre = "Mario"
        self.formulario.apoderado_apellido = "Tutor"
        self.formulario.apoderado_genero = "M"
        self.formulario.apoderado_fecha_nacimiento = date(1978, 10, 20)
        self.formulario.save()
        payload, faltantes = armar_payload(self.formulario, catalogos=self.cat, hoy=date(2026, 9, 14))
        self.assertEqual(faltantes, {})
        self.assertEqual(payload["dni_apoderado"], 25999888)
        self.assertEqual(payload["apellido_apoderado"], "TUTOR")
        self.assertEqual(payload["nombre_apoderado"], "MARIO")
        self.assertEqual(payload["sexo_apoderado"], "M")
        self.assertEqual(payload["fecha_nacim_apoderado"], "1978-10-20")
        self.assertEqual((payload["cuil_pref_apoderado"], payload["cuil_dig_apoderado"]), calcular_cuil("25999888", "M"))

    def test_mayor_no_manda_apoderado_aunque_lo_tenga(self):
        self.formulario.apoderado_dni = "25999888"
        self.formulario.save(update_fields=["apoderado_dni"])
        payload, _ = armar_payload(self.formulario, catalogos=self.cat, hoy=date(2026, 9, 14))
        self.assertNotIn("dni_apoderado", payload)

    def test_programa_sin_funcion_ni_jurisdiccion_falta(self):
        self.programa.siis_funcion_id = None
        self.programa.siis_programa_datos = {"id": 79}
        self.programa.save()
        _, faltantes = armar_payload(self.formulario, catalogos=self.cat)
        self.assertIn("id_fun_x_plan", faltantes)
        self.assertIn("jurid", faltantes)

    def test_sexo_no_binario_y_sin_celular(self):
        self.ciudadano.genero = "X"
        self.ciudadano.save(update_fields=["genero"])
        self.formulario.celular = ""
        self.formulario.save(update_fields=["celular"])
        payload, faltantes = armar_payload(self.formulario, catalogos=self.cat)
        self.assertIn("sexo", faltantes)
        self.assertNotIn("celular", payload)
```

- [ ] **Step 2: Correr y ver fallar**

Run: `& $env:PY_VENV manage.py test programas.tests.test_siis_envio` → FAIL con `ModuleNotFoundError: programas.services.siis_envio`.

- [ ] **Step 3: Implementación**

```python
# programas/services/siis_envio.py
"""Alta de beneficiarios aprobados en la tabla intermedia de SIIS.

Módulo puro: arma el payload de los 30 campos del manual v4.2 a partir del
ciudadano, las respuestas del formulario marcadas con un ``destino_siis`` y las
correcciones del coordinador (``Formulario.datos_siis``). Lo que no se puede
resolver queda en ``faltantes`` y el envío no se hace.
"""

import re
import unicodedata
from datetime import date

from programas.models import EnvioSIIS, Formulario, PreguntaGlobal
from programas.services.dashboard_becas import respuesta_de
from programas.services.siis import SiisCatalogError, cargar_beneficiario, catalogo

TDOC_DNI = 1
BARRIO_MINIMO = 4
LARGO_TEXTO = 50
MAYORIA_DE_EDAD = 18
_PESOS_CUIL = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)
_PALABRAS_DIRECCION = {"piso", "dpto", "depto", "dto", "departamento", "de", "y", "casa", "mz", "mza", "manzana"}


class CatalogoNoDisponible(Exception):
    """SIIS no devolvió un catálogo: el envío se reintenta, no se corrige."""


# ---------------------------------------------------------------------------
# CUIL
# ---------------------------------------------------------------------------
def _verificador(prefijo, dni):
    base = f"{prefijo:02d}{dni}"
    suma = sum(int(c) * p for c, p in zip(base, _PESOS_CUIL))
    return 11 - (suma % 11)


def calcular_cuil(dni, sexo):
    """``(prefijo, dígito)`` con el algoritmo estándar de módulo 11.

    Prefijo 20 (M) / 27 (F). Si el verificador da 10, el prefijo pasa a 23 y el
    dígito es 9 (M) o 4 (F); si da 11, el dígito es 0.
    """
    dni = re.sub(r"\D", "", str(dni or "")).zfill(8)[-8:]
    prefijo = 27 if str(sexo).upper() == "F" else 20
    digito = _verificador(prefijo, dni)
    if digito == 11:
        digito = 0
    elif digito == 10:
        prefijo = 23
        digito = 4 if str(sexo).upper() == "F" else 9
    return prefijo, digito


# ---------------------------------------------------------------------------
# Dirección
# ---------------------------------------------------------------------------
def parsear_direccion(texto):
    """Separa «Calle y altura (piso, dpto)» en ``calle``, ``nro``, ``piso`` y ``dpto``.

    El número es el último grupo de dígitos fuera de paréntesis; lo que hay
    entre paréntesis o después del número se interpreta como piso (dígitos) y
    departamento (una o dos letras). ``S/N`` deja ``nro`` en ``None``.
    """
    texto = " ".join(str(texto or "").split())
    extra = " ".join(re.findall(r"\(([^)]*)\)", texto))
    base = re.sub(r"\([^)]*\)", " ", texto)
    sin_numero = re.search(r"\bS\s*/\s*N\b", base, re.IGNORECASE)
    if sin_numero:
        base = base[: sin_numero.start()]
    base = " ".join(base.split()).strip(" ,-")
    calle, nro = base, None
    if not sin_numero:
        m = re.match(r"^(?P<calle>.*?)(?:^|[\s,]+)(?P<nro>\d{1,6})(?P<cola>\D*)$", base)
        if m and m.group("calle").strip(" ,-"):
            calle = m.group("calle").strip(" ,-")
            nro = int(m.group("nro"))
            extra = f"{extra} {m.group('cola')}".strip()
    piso = dpto = None
    if extra:
        m_piso = re.search(r"\d{1,3}", extra)
        piso = int(m_piso.group()) if m_piso else None
        for token in re.split(r"[\s,;/.-]+", extra):
            if re.fullmatch(r"[A-Za-z]{1,2}", token) and token.lower() not in _PALABRAS_DIRECCION:
                dpto = token.upper()
                break
    return {"calle": calle[:LARGO_TEXTO], "nro": nro, "piso": piso, "dpto": dpto}


# ---------------------------------------------------------------------------
# Catálogos
# ---------------------------------------------------------------------------
def clave_nombre(texto):
    """Clave de comparación: sin acentos, sin «/a», minúsculas, un espacio."""
    t = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode().casefold()
    t = re.sub(r"/[ao]s?\b", "", t)
    t = re.sub(r"[^a-z0-9]+", " ", t).strip()
    return t


class Catalogos:
    """Resuelve nombres a ids de los catálogos maestros. ``cargar`` se inyecta en tests."""

    def __init__(self, cargar=catalogo):
        self._cargar = cargar
        self._cache = {}

    def _items(self, nombre):
        if nombre not in self._cache:
            try:
                self._cache[nombre] = list(self._cargar(nombre))
            except SiisCatalogError as exc:
                raise CatalogoNoDisponible(str(exc)) from exc
        return self._cache[nombre]

    @staticmethod
    def _provincia_de(item):
        for clave in ("id_provincia", "provincia_id", "provincia", "prov_id"):
            valor = item.get(clave)
            if isinstance(valor, dict):
                valor = valor.get("id")
            try:
                return int(valor)
            except (TypeError, ValueError):
                continue
        return None

    def _buscar(self, nombre_catalogo, texto, filtro=None):
        clave = clave_nombre(texto)
        if not clave:
            return None
        candidatos = [i for i in self._items(nombre_catalogo) if clave_nombre(i["nombre"]) == clave]
        if filtro is not None:
            candidatos = [i for i in candidatos if filtro(i)]
        return candidatos[0]["id"] if len(candidatos) == 1 else None

    def provincia_id(self, nombre):
        return self._buscar("provincias", nombre)

    def localidad_id(self, nombre, provincia_id=None):
        if provincia_id is None:
            return self._buscar("localidades", nombre)
        return self._buscar("localidades", nombre, lambda i: self._provincia_de(i) in (None, int(provincia_id)))

    def estado_civil_id(self, nombre):
        return self._buscar("estados-civiles", nombre)

    def nombre_de(self, nombre_catalogo, item_id):
        for item in self._items(nombre_catalogo):
            if item["id"] == item_id:
                return item["nombre"]
        return ""


# ---------------------------------------------------------------------------
# Payload
# ---------------------------------------------------------------------------
def _texto_mayus(valor):
    return " ".join(str(valor or "").split()).upper()[:LARGO_TEXTO]


def _digitos(valor):
    return re.sub(r"\D", "", str(valor or ""))


def _edad(fecha_nacimiento, hoy):
    return hoy.year - fecha_nacimiento.year - ((hoy.month, hoy.day) < (fecha_nacimiento.month, fecha_nacimiento.day))


def respuestas_por_destino(formulario):
    """``{destino: texto}`` con la primera respuesta no vacía de cada pregunta marcada."""
    preguntas = PreguntaGlobal.objects.filter(activo=True).exclude(destino_siis="").values_list("pk", "destino_siis")
    resultado = {}
    for pk, destino in preguntas:
        valores = [str(v).strip() for v in respuesta_de(formulario.data, f"global:{pk}") if str(v or "").strip()]
        if valores:
            resultado[destino] = valores[0]
    return resultado


def _apoderado(formulario, faltantes):
    """Los 7 campos condicionales del manual (sección 4)."""
    if formulario.apoderado_ciudadano_id:
        a = formulario.apoderado_ciudadano
        dni, nombre, apellido, sexo, nacimiento = a.dni, a.nombre, a.apellido, a.genero, a.fecha_nacimiento
    else:
        dni, nombre, apellido = formulario.apoderado_dni, formulario.apoderado_nombre, formulario.apoderado_apellido
        sexo, nacimiento = formulario.apoderado_genero, formulario.apoderado_fecha_nacimiento
    datos = {}
    dni = _digitos(dni)
    if not dni:
        faltantes["dni_apoderado"] = "La persona es menor de 18 años y el caso no tiene apoderado con DNI."
        return datos
    datos["dni_apoderado"] = int(dni)
    if apellido:
        datos["apellido_apoderado"] = _texto_mayus(apellido)
    else:
        faltantes["apellido_apoderado"] = "Falta el apellido del apoderado."
    if nombre:
        datos["nombre_apoderado"] = _texto_mayus(nombre)
    else:
        faltantes["nombre_apoderado"] = "Falta el nombre del apoderado."
    sexo = str(sexo or "").upper()
    if sexo in ("F", "M"):
        datos["sexo_apoderado"] = sexo
        datos["cuil_pref_apoderado"], datos["cuil_dig_apoderado"] = calcular_cuil(dni, sexo)
    else:
        faltantes["sexo_apoderado"] = "El sexo del apoderado debe ser F o M."
    if nacimiento:
        datos["fecha_nacim_apoderado"] = nacimiento.isoformat()
    else:
        faltantes["fecha_nacim_apoderado"] = "Falta la fecha de nacimiento del apoderado."
    return datos


def armar_payload(formulario, catalogos=None, hoy=None):
    """``(payload, faltantes)``: el payload solo se manda si ``faltantes`` está vacío.

    Lanza :class:`CatalogoNoDisponible` si SIIS no devuelve un catálogo (error
    técnico, reintentable), a diferencia de un dato que no matchea (faltante).
    """
    catalogos = catalogos or Catalogos()
    hoy = hoy or date.today()
    faltantes = {}
    payload = {"tdoc": TDOC_DNI}
    ciudadano = formulario.ciudadano
    programa = formulario.relevamiento.convocatoria.segmento.programa
    respuestas = respuestas_por_destino(formulario)
    correcciones = formulario.datos_siis if isinstance(formulario.datos_siis, dict) else {}

    # --- Persona ---
    dni = _digitos(ciudadano.dni if ciudadano else "")
    if dni and len(dni) <= 10:
        payload["dni"] = int(dni)
    else:
        faltantes["dni"] = "El caso no tiene un ciudadano con DNI válido."
    if ciudadano and ciudadano.apellido:
        payload["apellido"] = _texto_mayus(ciudadano.apellido)
    else:
        faltantes["apellido"] = "Falta el apellido."
    if ciudadano and ciudadano.nombre:
        payload["nombre"] = _texto_mayus(ciudadano.nombre)
    else:
        faltantes["nombre"] = "Falta el nombre."
    sexo = str(ciudadano.genero if ciudadano else "").upper()
    if sexo in ("F", "M"):
        payload["sexo"] = sexo
        if dni:
            payload["cuil_pref"], payload["cuil_dig"] = calcular_cuil(dni, sexo)
    else:
        faltantes["sexo"] = "SIIS solo admite sexo F o M; corregilo en la sección de género del caso."
    nacimiento = ciudadano.fecha_nacimiento if ciudadano else None
    if nacimiento and nacimiento <= hoy:
        payload["fecha_nacim"] = nacimiento.isoformat()
    else:
        faltantes["fecha_nacim"] = "Falta la fecha de nacimiento o es futura."

    # --- Estado civil ---
    est_civil = correcciones.get("est_civil")
    if est_civil is None and respuestas.get("est_civil"):
        est_civil = catalogos.estado_civil_id(respuestas["est_civil"])
    if est_civil is not None:
        payload["est_civil"] = int(est_civil)
    else:
        faltantes["est_civil"] = "No se pudo determinar el estado civil (sin pregunta marcada o sin coincidencia en el catálogo)."

    # --- Domicilio actual ---
    prov_actual = correcciones.get("prov_actual")
    if prov_actual is None and respuestas.get("prov_actual"):
        prov_actual = catalogos.provincia_id(respuestas["prov_actual"])
    if prov_actual is not None:
        payload["prov_actual"] = int(prov_actual)
    else:
        faltantes["prov_actual"] = "No se pudo determinar la provincia del domicilio."
    loc_actual = correcciones.get("loc_actual")
    if loc_actual is None and respuestas.get("loc_actual"):
        loc_actual = catalogos.localidad_id(respuestas["loc_actual"], prov_actual)
    if loc_actual is not None:
        payload["loc_actual"] = int(loc_actual)
    else:
        faltantes["loc_actual"] = "La localidad no coincide con el catálogo de SIIS: elegila de la lista."

    barrio = correcciones.get("barrio_actual") or respuestas.get("barrio_actual") or ""
    barrio = " ".join(str(barrio).split())
    if barrio.isdigit():
        barrio = f"Barrio {barrio}"
    if len(barrio) >= BARRIO_MINIMO:
        payload["barrio_actual"] = barrio[:LARGO_TEXTO]
    else:
        faltantes["barrio_actual"] = "El barrio debe tener al menos 4 caracteres."

    direccion = parsear_direccion(respuestas.get("calle_altura", ""))
    calle = correcciones.get("calle_actual") or direccion["calle"]
    if calle:
        payload["calle_actual"] = str(calle)[:LARGO_TEXTO]
    else:
        faltantes["calle_actual"] = "Falta la calle del domicilio."
    nro = correcciones.get("nro_actual", direccion["nro"])
    if nro is not None and str(nro).strip() != "":
        payload["nro_actual"] = int(nro)
    else:
        faltantes["nro_actual"] = "Falta la altura del domicilio (SIIS exige un número)."
    piso = correcciones.get("piso_actual", direccion["piso"])
    if piso is not None and str(piso).strip() != "":
        payload["piso_actual"] = int(piso)
    dpto = correcciones.get("dpto_actual", direccion["dpto"])
    if dpto:
        payload["dpto_actual"] = str(dpto).strip().upper()[:2]

    # --- Nacimiento ---
    prov_nacim = correcciones.get("prov_nacim")
    if prov_nacim is None and respuestas.get("prov_nacim"):
        prov_nacim = catalogos.provincia_id(respuestas["prov_nacim"])
    if prov_nacim is not None:
        payload["prov_nacim"] = int(prov_nacim)
    else:
        faltantes["prov_nacim"] = "Falta la provincia de nacimiento."
    loc_nacim = correcciones.get("loc_nacim")
    if loc_nacim is None and respuestas.get("loc_nacim"):
        loc_nacim = catalogos.localidad_id(respuestas["loc_nacim"], prov_nacim)
    if loc_nacim is not None:
        payload["loc_nacim"] = int(loc_nacim)
    else:
        faltantes["loc_nacim"] = "Falta la localidad de nacimiento."

    # --- Contacto (opcionales) ---
    celular = _digitos(formulario.celular)
    if celular:
        payload["celular"] = int(celular)
    if formulario.email_contacto:
        payload["correo_electron"] = str(formulario.email_contacto).strip()[:LARGO_TEXTO]

    # --- Programa ---
    if programa is None:
        faltantes["id_plan_soc"] = "El segmento no tiene un programa SIIS configurado."
    else:
        payload["id_plan_soc"] = programa.siis_programa_id
        jurid = (programa.siis_programa_datos or {}).get("jurisdiccion_id")
        try:
            payload["jurid"] = int(jurid)
        except (TypeError, ValueError):
            faltantes["jurid"] = "El programa vinculado no informa jurisdicción; verificá el vínculo con SIIS."
        if programa.siis_funcion_id:
            payload["id_fun_x_plan"] = programa.siis_funcion_id
        else:
            faltantes["id_fun_x_plan"] = "El programa no tiene configurada la función SIIS para el alta de beneficiarios."

    # --- Apoderado (condicional) ---
    if nacimiento and _edad(nacimiento, hoy) < MAYORIA_DE_EDAD:
        payload.update(_apoderado(formulario, faltantes))

    return payload, faltantes
```

- [ ] **Step 4: Correr**

Run: `& $env:PY_VENV manage.py test programas.tests.test_siis_envio` → PASS. Si `test_digito_verificador_modulo_11` falla por el número elegido, verificar a mano: 2,0,1,2,3,4,5,6,7,8 × 5,4,3,2,7,6,5,4,3,2 = 10+0+3+4+21+24+25+24+21+16 = 148; 148 % 11 = 5; 11-5 = **6**. OK.

- [ ] **Step 5: Commit**

```bash
git add programas/services/siis_envio.py programas/tests/test_siis_envio.py
git commit -m "feat(siis): armado del payload de alta de beneficiarios (CUIL, direccion, catalogos, apoderado)"
```

---

### Task 4: Servicio de envío con registro auditable

**Files:**
- Modify: `programas/services/siis_envio.py`
- Test: `programas/tests/test_siis_envio.py`

**Interfaces:**
- Consumes: `armar_payload`, `cargar_beneficiario` (Task 2), `EnvioSIIS`.
- Produces: `enviar_beneficiario_a_siis(formulario, solicitado_por, catalogos=None) -> EnvioSIIS`; `mensaje_envio(envio) -> (nivel: str, texto: str)` con nivel ∈ `success|warning|error`.

- [ ] **Step 1: Tests**

```python
from programas.services.siis_envio import enviar_beneficiario_a_siis, mensaje_envio


class EnviarBeneficiarioTests(ArmarPayloadTests):
    """Hereda el formulario completo de ArmarPayloadTests."""

    def setUp(self):
        super().setUp()
        self.cargar = patch("programas.services.siis_envio.cargar_beneficiario").start()
        self.addCleanup(patch.stopall)
        self.cargar.return_value = {"success": True, "siis_id": 26, "codigo": "", "reintentable": False, "detalles": {}, "data": {"ids_generados": [26]}}

    def test_envio_exitoso_registra_enviado(self):
        envio = enviar_beneficiario_a_siis(self.formulario, self.user, catalogos=self.cat)
        self.assertEqual(envio.estado, EnvioSIIS.Estado.ENVIADO)
        self.assertEqual(envio.siis_id, 26)
        self.assertEqual(envio.id_programa, 79)
        self.assertEqual(envio.id_funcion, 4)
        self.assertEqual(envio.documento, "20301234")
        self.assertEqual(envio.payload["dni"], 20301234)
        self.assertEqual(envio.solicitado_por, self.user)
        self.assertEqual(mensaje_envio(envio), ("success", "Informado a SIIS (ID 26)."))

    def test_no_reenvia_si_ya_esta_enviado(self):
        enviar_beneficiario_a_siis(self.formulario, self.user, catalogos=self.cat)
        otro = enviar_beneficiario_a_siis(self.formulario, self.user, catalogos=self.cat)
        self.assertEqual(self.cargar.call_count, 1)
        self.assertEqual(self.formulario.envios_sis.count(), 1)
        self.assertEqual(otro.estado, EnvioSIIS.Estado.ENVIADO)

    def test_faltantes_registran_incompleto_sin_llamar(self):
        self.formulario.data["globales"][str(self.p_loc.pk)] = "J.j castelli"
        self.formulario.save(update_fields=["data"])
        envio = enviar_beneficiario_a_siis(self.formulario, self.user, catalogos=self.cat)
        self.assertEqual(envio.estado, EnvioSIIS.Estado.INCOMPLETO)
        self.assertIn("loc_actual", envio.detalles)
        self.cargar.assert_not_called()
        self.assertEqual(mensaje_envio(envio)[0], "warning")

    def test_400_registra_rechazado_con_detalles(self):
        self.cargar.return_value = {
            "success": False, "codigo": "DATOS_INVALIDOS", "reintentable": False,
            "error": "Uno o más campos…", "detalles": {"barrio_actual": ["mínimo 4"]}, "data": {"error": "DATOS_INVALIDOS"},
        }
        envio = enviar_beneficiario_a_siis(self.formulario, self.user, catalogos=self.cat)
        self.assertEqual(envio.estado, EnvioSIIS.Estado.RECHAZADO)
        self.assertEqual(envio.codigo_error, "DATOS_INVALIDOS")
        self.assertEqual(envio.detalles, {"barrio_actual": ["mínimo 4"]})
        self.assertFalse(envio.reintentable)

    def test_503_registra_error_reintentable(self):
        self.cargar.return_value = {"success": False, "codigo": "ERROR_BD_LEGACY", "reintentable": True, "error": "x", "detalles": {}, "data": {}}
        envio = enviar_beneficiario_a_siis(self.formulario, self.user, catalogos=self.cat)
        self.assertEqual(envio.estado, EnvioSIIS.Estado.ERROR)
        self.assertTrue(envio.reintentable)
        self.assertEqual(mensaje_envio(envio)[0], "error")

    def test_catalogo_caido_es_error_tecnico(self):
        def falla(nombre):
            raise SiisCatalogError("SIIS no está disponible temporalmente.")

        envio = enviar_beneficiario_a_siis(self.formulario, self.user, catalogos=Catalogos(cargar=falla))
        self.assertEqual(envio.estado, EnvioSIIS.Estado.ERROR)
        self.assertEqual(envio.codigo_error, "ERROR_TECNICO")
        self.assertIn("catalogo", envio.detalles)
        self.cargar.assert_not_called()

    def test_solo_casos_aprobados(self):
        self.formulario.estado = Formulario.Estado.ENVIADO
        self.formulario.save(update_fields=["estado"])
        with self.assertRaises(ValueError):
            enviar_beneficiario_a_siis(self.formulario, self.user, catalogos=self.cat)
```

- [ ] **Step 2: Correr y ver fallar** → `ImportError: enviar_beneficiario_a_siis`.

- [ ] **Step 3: Implementación** (al final de `siis_envio.py`)

```python
# ---------------------------------------------------------------------------
# Servicio
# ---------------------------------------------------------------------------
def enviar_beneficiario_a_siis(formulario, solicitado_por, catalogos=None):
    """Da de alta al beneficiario en SIIS y **siempre** deja un ``EnvioSIIS``.

    Idempotente: un caso ya ``ENVIADO`` no se vuelve a mandar (la API no
    deduplica). Nunca lanza por fallas de red ni de SIIS.
    """
    if formulario.estado != Formulario.Estado.APROBADO:
        raise ValueError("Solo se informan a SIIS los casos aprobados.")
    vigente = formulario.envios_sis.filter(estado=EnvioSIIS.Estado.ENVIADO).order_by("-creado").first()
    if vigente:
        return vigente

    programa = formulario.relevamiento.convocatoria.segmento.programa
    base = {
        "formulario": formulario,
        "id_programa": programa.siis_programa_id if programa else None,
        "id_funcion": programa.siis_funcion_id if programa else None,
        "documento": str(formulario.ciudadano.dni if formulario.ciudadano_id else "")[:20],
        "solicitado_por": solicitado_por,
    }
    try:
        payload, faltantes = armar_payload(formulario, catalogos=catalogos)
    except CatalogoNoDisponible as exc:
        return EnvioSIIS.objects.create(
            estado=EnvioSIIS.Estado.ERROR, codigo_error="ERROR_TECNICO", detalles={"catalogo": [str(exc)]}, **base
        )
    if faltantes:
        return EnvioSIIS.objects.create(
            estado=EnvioSIIS.Estado.INCOMPLETO, codigo_error="DATOS_INCOMPLETOS", detalles=faltantes, payload=payload, **base
        )

    resultado = cargar_beneficiario(payload)
    if resultado.get("success"):
        return EnvioSIIS.objects.create(
            estado=EnvioSIIS.Estado.ENVIADO, siis_id=resultado.get("siis_id"), payload=payload, respuesta=resultado.get("data") or {}, **base
        )
    estado = EnvioSIIS.Estado.ERROR if resultado.get("reintentable") else EnvioSIIS.Estado.RECHAZADO
    detalles = resultado.get("detalles") or {}
    if not detalles and resultado.get("error"):
        detalles = {"_": [str(resultado["error"])]}
    return EnvioSIIS.objects.create(
        estado=estado, codigo_error=str(resultado.get("codigo") or "")[:40], detalles=detalles, payload=payload,
        respuesta=resultado.get("data") or {}, **base,
    )


def mensaje_envio(envio):
    """``(nivel, texto)`` para el toast de la vista."""
    if envio.estado == EnvioSIIS.Estado.ENVIADO:
        sufijo = f" (ID {envio.siis_id})" if envio.siis_id else ""
        return "success", f"Informado a SIIS{sufijo}."
    if envio.estado == EnvioSIIS.Estado.INCOMPLETO:
        return "warning", f"El envío a SIIS quedó pendiente: faltan {len(envio.detalles)} dato(s). Completalos desde el caso."
    if envio.estado == EnvioSIIS.Estado.RECHAZADO:
        return "warning", "SIIS rechazó el alta del beneficiario: revisá los datos señalados y reenviá."
    return "error", "SIIS no respondió correctamente; el envío quedó registrado para reintentar."
```

- [ ] **Step 4: Correr** → PASS.

- [ ] **Step 5: Commit**

```bash
git add programas/services/siis_envio.py programas/tests/test_siis_envio.py
git commit -m "feat(siis): servicio de envio de beneficiarios con registro auditable e idempotencia"
```

---

### Task 5: Disparo al aprobar y al promover

**Files:**
- Modify: `programas/views/revision.py` (`formulario_aprobar` ~L565), `programas/views/cupo.py` (`promover_lista_espera_view` ~L150)
- Test: `programas/tests/test_becas_revision.py`

**Interfaces:**
- Consumes: `enviar_beneficiario_a_siis`, `mensaje_envio`.

- [ ] **Step 1: Tests** (nueva clase al final de `test_becas_revision.py`)

```python
class EnvioSiisAlAprobarTests(_BaseAprobacionTest):
    def setUp(self):
        super().setUp()
        self.programa.siis_programa_datos = {"id": 41, "jurisdiccion_id": 28}
        self.programa.siis_funcion_id = 4
        self.programa.save()
        self.enviar = patch("programas.views.revision.enviar_beneficiario_a_siis").start()
        self.enviar_cupo = patch("programas.views.cupo.enviar_beneficiario_a_siis").start()
        self.addCleanup(patch.stopall)
        for mock in (self.enviar, self.enviar_cupo):
            mock.return_value = EnvioSIIS(
                formulario=self.form_a, estado=EnvioSIIS.Estado.INCOMPLETO, detalles={"loc_actual": "x"}
            )

    def test_aprobar_con_cupo_dispara_el_envio(self):
        self.client.post(reverse("becas:formulario_aprobar", args=[self.form_a.pk]))
        self.enviar.assert_called_once()
        self.assertEqual(self.enviar.call_args.args[0].pk, self.form_a.pk)

    def test_aprobar_a_lista_de_espera_no_dispara(self):
        self.seg_a.cupo_maximo = 0
        self.seg_a.save(update_fields=["cupo_maximo"])
        self.client.post(reverse("becas:formulario_aprobar", args=[self.form_a.pk]))
        self.form_a.refresh_from_db()
        self.assertEqual(self.form_a.estado, Formulario.Estado.ENVIADO)
        self.enviar.assert_not_called()

    def test_promover_dispara_el_envio(self):
        self.seg_a.cupo_maximo = 0
        self.seg_a.save(update_fields=["cupo_maximo"])
        self.client.post(reverse("becas:formulario_aprobar", args=[self.form_a.pk]))
        lista = ListaEspera.objects.get(formulario=self.form_a)
        self.seg_a.cupo_maximo = 10
        self.seg_a.save(update_fields=["cupo_maximo"])
        self.client.force_login(self.admin)
        self.client.post(reverse("becas:lista_espera_promover", args=[lista.pk]))
        self.form_a.refresh_from_db()
        self.assertEqual(self.form_a.estado, Formulario.Estado.APROBADO)
        self.enviar_cupo.assert_called_once()

    def test_una_falla_del_envio_no_revierte_la_aprobacion(self):
        self.enviar.side_effect = RuntimeError("boom")
        self.client.post(reverse("becas:formulario_aprobar", args=[self.form_a.pk]))
        self.form_a.refresh_from_db()
        self.assertEqual(self.form_a.estado, Formulario.Estado.APROBADO)
```

Agregar `EnvioSIIS`, `ListaEspera` a los imports de `programas.models` en el test si faltan.

- [ ] **Step 2: Correr y ver fallar** → `AttributeError: module 'programas.views.revision' has no attribute 'enviar_beneficiario_a_siis'`.

- [ ] **Step 3: Implementación**

`programas/views/revision.py` — import:

```python
from programas.services.siis_envio import enviar_beneficiario_a_siis, mensaje_envio
```

y en `formulario_aprobar`, dentro del `else:` después de armar el mensaje de aprobado / lista de espera y **antes** de `enviar_aviso_resolucion`:

```python
            if resultado == "aprobado":
                _informar_a_siis(request, formulario)
```

Helper a nivel de módulo (cerca de `_tiene_conflicto_duplicado_pendiente`):

```python
def _informar_a_siis(request, formulario):
    """Alta del beneficiario en SIIS tras la aprobación. Va afuera de la
    transacción del servicio y nunca deshace la aprobación: un fallo acá se
    registra (o se loguea) y el coordinador reintenta desde el caso."""
    try:
        envio = enviar_beneficiario_a_siis(formulario, request.user)
    except Exception:  # noqa: BLE001 — la aprobación ya está confirmada
        logger.exception("Fallo inesperado al informar el beneficiario %s a SIIS", formulario.pk)
        messages.error(request, "No se pudo informar el beneficiario a SIIS; reintentá desde el caso.")
        return None
    nivel, texto = mensaje_envio(envio)
    getattr(messages, nivel)(request, texto)
    return envio
```

Asegurar `import logging` y `logger = logging.getLogger(__name__)` al tope si no existen.

`programas/views/cupo.py` — import igual, y en `promover_lista_espera_view`, en el `else:` antes de `enviar_aviso_resolucion`:

```python
            _informar_a_siis(request, lista.formulario)
```

con el mismo helper `_informar_a_siis` copiado en `cupo.py` (dos vistas, dos módulos; el helper es de 10 líneas y evita un import cruzado entre vistas).

- [ ] **Step 4: Correr**

Run: `& $env:PY_VENV manage.py test programas.tests.test_becas_revision` → PASS (toda la suite existente sigue en verde: los tests viejos de aprobar no tienen preguntas marcadas y el envío real quedaría INCOMPLETO sin llamar a la red, pero `armar_payload` sí consulta el catálogo de estados civiles… **no**: solo consulta si hay respuesta; sin respuesta no toca la red). Verificar que ningún test viejo hace una llamada HTTP real: correr con `SIIS_API_URL` apuntando a `https://siis.example` ya está en el override de los tests de cliente; en los de revisión, `Catalogos` no se invoca sin respuestas.

- [ ] **Step 5: Commit**

```bash
git add programas/views/revision.py programas/views/cupo.py programas/tests/test_becas_revision.py
git commit -m "feat(siis): informar el beneficiario a SIIS al aprobar con cupo y al promover de la lista de espera"
```

---

### Task 6: Reenvío manual y corrección de datos (vistas, form, urls)

**Files:**
- Modify: `programas/forms.py`, `programas/views/revision.py`, `programas/urls.py`
- Test: `programas/tests/test_becas_revision.py`

**Interfaces:**
- Produces: `DatosSiisForm(data, catalogos=None)` con campos `prov_actual, loc_actual, barrio_actual, calle_actual, nro_actual, piso_actual, dpto_actual, est_civil, prov_nacim, loc_nacim` (todos opcionales) y método `como_datos_siis() -> dict`; vistas `formulario_enviar_siis`, `formulario_datos_siis`, `siis_localidades_json`; rutas `becas:formulario_enviar_siis`, `becas:formulario_datos_siis`, `becas:siis_localidades`.

- [ ] **Step 1: Tests**

```python
class ReenvioYDatosSiisTests(_BaseAprobacionTest):
    def setUp(self):
        super().setUp()
        self.form_a.estado = Formulario.Estado.APROBADO
        self.form_a.save(update_fields=["estado"])
        self.enviar = patch("programas.views.revision.enviar_beneficiario_a_siis").start()
        self.catalogo = patch("programas.forms.catalogo").start()
        self.addCleanup(patch.stopall)
        self.enviar.return_value = EnvioSIIS(formulario=self.form_a, estado=EnvioSIIS.Estado.ENVIADO, siis_id=26)
        self.catalogo.side_effect = lambda nombre: {
            "provincias": [{"id": 22, "nombre": "Chaco"}],
            "localidades": [{"id": 37, "nombre": "Juan José Castelli", "id_provincia": 22}],
            "estados-civiles": [{"id": 1, "nombre": "Soltero/a"}],
        }[nombre]

    def test_reenviar_requiere_post_y_capacidad(self):
        self.assertEqual(self.client.get(reverse("becas:formulario_enviar_siis", args=[self.form_a.pk])).status_code, 405)
        self.client.force_login(self.territorial)
        resp = self.client.post(reverse("becas:formulario_enviar_siis", args=[self.form_a.pk]))
        self.assertEqual(resp.status_code, 403)
        self.enviar.assert_not_called()

    def test_reenviar_llama_al_servicio(self):
        resp = self.client.post(reverse("becas:formulario_enviar_siis", args=[self.form_a.pk]))
        self.assertRedirects(resp, reverse("becas:formulario_detalle", args=[self.form_a.pk]), fetch_redirect_response=False)
        self.enviar.assert_called_once()

    def test_reenviar_no_aplica_a_casos_no_aprobados(self):
        self.form_a.estado = Formulario.Estado.ENVIADO
        self.form_a.save(update_fields=["estado"])
        self.client.post(reverse("becas:formulario_enviar_siis", args=[self.form_a.pk]))
        self.enviar.assert_not_called()

    def test_guardar_datos_siis_con_traza_y_sin_enviar(self):
        resp = self.client.post(
            reverse("becas:formulario_datos_siis", args=[self.form_a.pk]),
            {"prov_actual": "22", "loc_actual": "37", "barrio_actual": "Barrio 108", "calle_actual": "Los Alamos", "nro_actual": "15"},
        )
        self.assertEqual(resp.status_code, 302)
        self.form_a.refresh_from_db()
        self.assertEqual(self.form_a.datos_siis["loc_actual"], 37)
        self.assertEqual(self.form_a.datos_siis["nro_actual"], 15)
        self.assertNotIn("piso_actual", self.form_a.datos_siis)
        self.assertTrue(self.form_a.trazas.filter(campo__startswith="Datos SIIS").exists())
        self.enviar.assert_not_called()

    def test_datos_siis_valida_barrio_corto_y_localidad_fuera_del_catalogo(self):
        form = DatosSiisForm({"barrio_actual": "Sur", "loc_actual": "999", "prov_actual": "22"})
        self.assertFalse(form.is_valid())
        self.assertIn("barrio_actual", form.errors)
        self.assertIn("loc_actual", form.errors)

    def test_localidades_json_filtra_por_provincia(self):
        resp = self.client.get(reverse("becas:siis_localidades") + "?provincia=22")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"localidades": [{"id": 37, "nombre": "Juan José Castelli"}]})
```

Importar `DatosSiisForm` desde `programas.forms` en el test.

- [ ] **Step 2: Correr y ver fallar** → `ImportError: DatosSiisForm`.

- [ ] **Step 3: Implementación**

`programas/forms.py` — import `from programas.services.siis import SiisCatalogError, catalogo, listar_programas` (extender la línea existente) y al final:

```python
class DatosSiisForm(forms.Form):
    """Correcciones del coordinador para el alta en SIIS. Todos los campos son
    opcionales: solo lo completado pisa lo que salió del relevamiento."""

    prov_actual = forms.ChoiceField(label="Provincia del domicilio", required=False, widget=forms.Select(attrs={"class": INPUT_CLASS}))
    loc_actual = forms.IntegerField(label="Localidad del domicilio", required=False, widget=forms.Select(attrs={"class": INPUT_CLASS}))
    barrio_actual = forms.CharField(label="Barrio", required=False, max_length=50, widget=forms.TextInput(attrs={"class": INPUT_CLASS}))
    calle_actual = forms.CharField(label="Calle", required=False, max_length=50, widget=forms.TextInput(attrs={"class": INPUT_CLASS}))
    nro_actual = forms.IntegerField(label="Altura / número", required=False, min_value=0, widget=forms.NumberInput(attrs={"class": INPUT_CLASS, "min": 0}))
    piso_actual = forms.IntegerField(label="Piso", required=False, min_value=0, widget=forms.NumberInput(attrs={"class": INPUT_CLASS, "min": 0}))
    dpto_actual = forms.CharField(label="Departamento", required=False, max_length=2, widget=forms.TextInput(attrs={"class": INPUT_CLASS, "maxlength": 2}))
    est_civil = forms.ChoiceField(label="Estado civil", required=False, widget=forms.Select(attrs={"class": INPUT_CLASS}))
    prov_nacim = forms.ChoiceField(label="Provincia de nacimiento", required=False, widget=forms.Select(attrs={"class": INPUT_CLASS}))
    loc_nacim = forms.IntegerField(label="Localidad de nacimiento", required=False, widget=forms.Select(attrs={"class": INPUT_CLASS}))

    CAMPOS = ("prov_actual", "loc_actual", "barrio_actual", "calle_actual", "nro_actual", "piso_actual", "dpto_actual", "est_civil", "prov_nacim", "loc_nacim")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        provincias, self.error_catalogo = _cargar_catalogo(lambda: catalogo("provincias"))
        estados, error_estados = _cargar_catalogo(lambda: catalogo("estados-civiles"))
        self.error_catalogo = self.error_catalogo or error_estados
        opciones_prov = _catalogo_choices(provincias, "Sin cambios")
        self.fields["prov_actual"].choices = opciones_prov
        self.fields["prov_nacim"].choices = opciones_prov
        self.fields["est_civil"].choices = _catalogo_choices(estados, "Sin cambios")

    def _validar_localidad(self, campo, campo_provincia):
        loc = self.cleaned_data.get(campo)
        if loc is None:
            return
        prov = self.cleaned_data.get(campo_provincia)
        localidades, error = _cargar_catalogo(lambda: catalogo("localidades"))
        if error:
            self.add_error(campo, error)
            return
        item = next((i for i in localidades if i["id"] == loc), None)
        if item is None:
            self.add_error(campo, "La localidad no está en el catálogo de SIIS.")
            return
        prov_item = item.get("id_provincia") or item.get("provincia_id")
        if prov and prov_item is not None and str(prov_item) != str(prov):
            self.add_error(campo, "La localidad no pertenece a la provincia elegida.")

    def clean_barrio_actual(self):
        barrio = " ".join((self.cleaned_data.get("barrio_actual") or "").split())
        if barrio and len(barrio) < 4:
            raise forms.ValidationError("El barrio debe tener al menos 4 caracteres.")
        return barrio

    def clean_dpto_actual(self):
        return (self.cleaned_data.get("dpto_actual") or "").strip().upper()

    def clean(self):
        cleaned = super().clean()
        self._validar_localidad("loc_actual", "prov_actual")
        self._validar_localidad("loc_nacim", "prov_nacim")
        return cleaned

    def como_datos_siis(self):
        """Solo lo completado, con los tipos que espera la API (enteros para ids y números)."""
        datos = {}
        for campo in self.CAMPOS:
            valor = self.cleaned_data.get(campo)
            if valor in (None, ""):
                continue
            datos[campo] = int(valor) if campo not in ("barrio_actual", "calle_actual", "dpto_actual") else valor
        return datos
```

`programas/views/revision.py`:

```python
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from programas.forms import DatosSiisForm  # sumar al import existente
from programas.services.siis import SiisCatalogError, catalogo


@login_required
@requiere(CAP_REVISION_EDITAR)
@require_POST
def formulario_enviar_siis(request, pk):
    formulario = get_object_or_404(Formulario.objects.select_related("relevamiento__convocatoria__segmento__programa", "ciudadano"), pk=pk)
    _assert_scope_formulario(request, formulario)
    if formulario.estado != Formulario.Estado.APROBADO:
        messages.error(request, "Solo se informan a SIIS los casos aprobados.")
    else:
        _informar_a_siis(request, formulario)
    return redirect("becas:formulario_detalle", pk=formulario.pk)


@login_required
@requiere(CAP_REVISION_EDITAR)
@require_POST
def formulario_datos_siis(request, pk):
    formulario = get_object_or_404(Formulario, pk=pk)
    _assert_scope_formulario(request, formulario)
    form = DatosSiisForm(request.POST)
    if not form.is_valid():
        for campo, errores in form.errors.items():
            etiqueta = form.fields[campo].label if campo in form.fields else "Datos SIIS"
            messages.error(request, f"{etiqueta}: {' '.join(errores)}")
        return redirect("becas:formulario_detalle", pk=formulario.pk)
    anteriores = formulario.datos_siis if isinstance(formulario.datos_siis, dict) else {}
    nuevos = form.como_datos_siis()
    cambios = [
        (f"Datos SIIS · {form.fields[campo].label}", str(anteriores.get(campo, "")), str(valor))
        for campo, valor in nuevos.items()
        if anteriores.get(campo) != valor
    ]
    with transaction.atomic():
        formulario.datos_siis = {**anteriores, **nuevos}
        formulario.save(update_fields=["datos_siis", "modificado"])
        registrar_traza(formulario, request.user, cambios)
    messages.success(request, "Datos para SIIS guardados. Reenviá el caso para informarlo." if cambios else "No hubo cambios para guardar.")
    return redirect("becas:formulario_detalle", pk=formulario.pk)


@login_required
@requiere(CAP_REVISION_EDITAR)
@require_GET
def siis_localidades_json(request):
    """Localidades del catálogo de SIIS para el select dependiente de provincia."""
    try:
        provincia = int(request.GET.get("provincia") or 0)
    except ValueError:
        provincia = 0
    try:
        items = catalogo("localidades")
    except SiisCatalogError as exc:
        return JsonResponse({"localidades": [], "error": str(exc)}, status=503)
    if provincia:
        items = [i for i in items if str(i.get("id_provincia") or i.get("provincia_id") or provincia) == str(provincia)]
    return JsonResponse({"localidades": [{"id": i["id"], "nombre": i["nombre"]} for i in sorted(items, key=lambda i: i["nombre"])]})
```

(`transaction` ya se importa en `revision.py`; verificar y sumar `from django.db import transaction` si no.)

`programas/urls.py`, después de `validar-padron`:

```python
    path("revision/formulario/<int:pk>/enviar-siis/", rev.formulario_enviar_siis, name="formulario_enviar_siis"),
    path("revision/formulario/<int:pk>/datos-siis/", rev.formulario_datos_siis, name="formulario_datos_siis"),
    path("revision/siis/localidades/", rev.siis_localidades_json, name="siis_localidades"),
```

- [ ] **Step 4: Correr** → PASS.

- [ ] **Step 5: Commit**

```bash
git add programas/forms.py programas/views/revision.py programas/urls.py programas/tests/test_becas_revision.py
git commit -m "feat(siis): reenvio manual y correccion de datos para el alta del beneficiario"
```

---

### Task 7: Destino SIIS en el ABM de preguntas globales

**Files:**
- Modify: `programas/forms.py` (`PreguntaGlobalForm` ~L829), `programas/templates/programas/becas/config/pregunta_form.html`, `programas/templates/programas/becas/config/pregunta_list.html`
- Test: `programas/tests/test_becas_config.py`

- [ ] **Step 1: Tests**

```python
class DestinoSiisPreguntaTests(TestCase):
    def setUp(self):
        call_command("seed_becas", stdout=StringIO())
        self.admin = User.objects.create_user("admin_cfg", password="x")
        self.admin.groups.add(Group.objects.get(name=ROL_ADMIN))
        self.client.force_login(self.admin)

    def _post(self, texto, destino, activo="on"):
        return self.client.post(
            reverse("becas:pregunta_crear"),
            {"texto": texto, "tipo": TipoCampo.STRING, "orden": "", "obligatorio": "on", "activo": activo, "destino_siis": destino},
        )

    def test_crea_pregunta_con_destino(self):
        self._post("Localidad", "loc_actual")
        self.assertEqual(PreguntaGlobal.objects.get(texto="Localidad").destino_siis, "loc_actual")

    def test_rechaza_dos_activas_con_el_mismo_destino(self):
        self._post("Localidad", "loc_actual")
        form = PreguntaGlobalForm(
            {"texto": "Otra", "tipo": TipoCampo.STRING, "orden": "", "obligatorio": "on", "activo": "on", "destino_siis": "loc_actual"}
        )
        self.assertFalse(form.is_valid())
        self.assertIn("destino_siis", form.errors)

    def test_permite_repetir_destino_si_la_otra_esta_inactiva(self):
        self._post("Vieja", "loc_actual", activo="")
        resp = self._post("Nueva", "loc_actual")
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(PreguntaGlobal.objects.filter(destino_siis="loc_actual").count(), 2)
```

- [ ] **Step 2: Correr y ver fallar** → la primera pasa a medias (el campo se ignora), la segunda falla porque el form es válido.

- [ ] **Step 3: Implementación**

`PreguntaGlobalForm`:

```python
    class Meta:
        model = PreguntaGlobal
        fields = ["texto", "tipo", "presentacion", "obligatorio", "orden", "activo", "destino_siis"]
        widgets = {
            ...existentes...,
            "destino_siis": forms.Select(attrs={"class": INPUT_CLASS}),
        }

    def clean_destino_siis(self):
        destino = self.cleaned_data.get("destino_siis") or ""
        if destino and self.cleaned_data.get("activo", True):
            otras = PreguntaGlobal.objects.filter(activo=True, destino_siis=destino)
            if self.instance.pk:
                otras = otras.exclude(pk=self.instance.pk)
            if otras.exists():
                raise forms.ValidationError(
                    f"Ya hay una pregunta activa que alimenta «{PreguntaGlobal.DestinoSiis(destino).label}»: «{otras.first().texto}»."
                )
        return destino
```

Nota: `activo` se limpia antes que `destino_siis` porque está antes en `fields`; si no, mover la validación a `clean()`.

`pregunta_form.html` no cambia (renderiza `{% for field in form %}`), pero agregar en el `_field.html`-loop nada. En `pregunta_list.html`, en la fila de cada pregunta, agregar un badge si tiene destino:

```django
{% if p.destino_siis %}<span class="badge badge-info ml-2" title="Alimenta el alta en SIIS">SIIS: {{ p.get_destino_siis_display }}</span>{% endif %}
```

(ubicar junto al texto de la pregunta; revisar la variable del loop en ese template.)

- [ ] **Step 4: Correr** → `manage.py test programas.tests.test_becas_config` PASS. `scripts/design_audit.py --changed` 0 errores.

- [ ] **Step 5: Commit**

```bash
git add programas/forms.py programas/templates/programas/becas/config/pregunta_list.html programas/tests/test_becas_config.py
git commit -m "feat(siis): las preguntas globales declaran que campo del alta en SIIS alimentan"
```

---

### Task 8: Función SIIS del programa

**Files:**
- Modify: `programas/forms.py`, `programas/views/configuracion.py`, `programas/urls.py`, `programas/templates/programas/becas/config/programa_detail.html`
- Test: `programas/tests/test_becas_config.py`

**Interfaces:**
- Produces: `ProgramaSiisFuncionForm(data, programa=...)`; vista `programa_funcion_siis` (POST) en `becas:programa_funcion_siis`.

- [ ] **Step 1: Tests**

```python
class FuncionSiisProgramaTests(TestCase):
    def setUp(self):
        call_command("seed_becas", stdout=StringIO())
        self.admin = User.objects.create_user("admin_cfg2", password="x")
        self.admin.groups.add(Group.objects.get(name=ROL_ADMIN))
        self.client.force_login(self.admin)
        self.programa = ProgramaSiis.objects.create(nombre="Ñachec", siis_programa_id=79)
        self.funciones = patch("programas.forms.funciones_programa").start()
        self.addCleanup(patch.stopall)
        self.funciones.return_value = [{"id": 4, "nombre": "Nivel Operativo", "id_programa": 79}]

    def test_guarda_la_funcion_elegida(self):
        resp = self.client.post(reverse("becas:programa_funcion_siis", args=[self.programa.pk]), {"siis_funcion_id": "4"})
        self.assertEqual(resp.status_code, 302)
        self.programa.refresh_from_db()
        self.assertEqual(self.programa.siis_funcion_id, 4)
        self.assertEqual(self.programa.siis_funcion_nombre, "Nivel Operativo")
        self.funciones.assert_called_with(79)

    def test_rechaza_una_funcion_fuera_del_catalogo(self):
        self.client.post(reverse("becas:programa_funcion_siis", args=[self.programa.pk]), {"siis_funcion_id": "99"})
        self.programa.refresh_from_db()
        self.assertIsNone(self.programa.siis_funcion_id)

    def test_requiere_administrar_programa(self):
        coord = User.objects.create_user("coord_cfg", password="x")
        coord.groups.add(Group.objects.get(name=ROL_COORDINADOR))
        self.client.force_login(coord)
        resp = self.client.post(reverse("becas:programa_funcion_siis", args=[self.programa.pk]), {"siis_funcion_id": "4"})
        self.assertEqual(resp.status_code, 403)
```

- [ ] **Step 2: Correr y ver fallar** → `NoReverseMatch: programa_funcion_siis`.

- [ ] **Step 3: Implementación**

`programas/forms.py` (import `funciones_programa` desde `programas.services.siis`):

```python
class ProgramaSiisFuncionForm(forms.ModelForm):
    """Función/nivel del programa que viaja en ``id_fun_x_plan`` al dar de alta
    beneficiarios. Se elige del catálogo de SIIS; no se tipea."""

    siis_funcion_id = forms.ChoiceField(label="Función SIIS", choices=(), widget=forms.Select(attrs={"class": INPUT_CLASS}))

    class Meta:
        model = ProgramaSiis
        fields = ["siis_funcion_id"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        funciones, error = _cargar_catalogo(lambda: funciones_programa(self.instance.siis_programa_id))
        self._funciones = {f["id"]: f for f in funciones}
        self.fields["siis_funcion_id"].choices = _catalogo_choices(funciones, "Seleccioná una función…")
        if error:
            self.fields["siis_funcion_id"].help_text = error

    def clean_siis_funcion_id(self):
        funcion_id = int(self.cleaned_data["siis_funcion_id"])
        if funcion_id not in self._funciones:
            raise forms.ValidationError("Esa función no está en el catálogo de SIIS para este programa.")
        return funcion_id

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.siis_funcion_nombre = self._funciones[instance.siis_funcion_id]["nombre"]
        if commit:
            instance.save(update_fields=["siis_funcion_id", "siis_funcion_nombre", "modificado"])
        return instance
```

`programas/views/configuracion.py`:

```python
CAP_PROGRAMA_ADMINISTRAR = "becas.programa.administrar"


@login_required
@requiere(CAP_PROGRAMA_ADMINISTRAR)
@require_POST
def programa_funcion_siis(request, pk):
    programa = get_object_or_404(ProgramaSiis, pk=pk)
    if not _programas_qs(request.user).filter(pk=programa.pk).exists():
        raise PermissionDenied("No tiene acceso a este programa.")
    form = ProgramaSiisFuncionForm(request.POST, instance=programa)
    if form.is_valid():
        form.save()
        messages.success(request, f"Función SIIS guardada: {programa.siis_funcion_nombre}.")
    else:
        messages.error(request, " ".join(" ".join(e) for e in form.errors.values()))
    return redirect("becas:programa_detalle", pk=programa.pk)
```

(sumar los imports que falten: `login_required`, `requiere` de `core.rbac`, `require_POST`, `ProgramaSiisFuncionForm`.) En `ProgramaSiisDetailView.get_context_data`:

```python
        ctx["puede_administrar_programa"] = puede(self.request.user, CAP_PROGRAMA_ADMINISTRAR)
        if ctx["puede_administrar_programa"]:
            ctx["form_funcion_siis"] = ProgramaSiisFuncionForm(instance=programa)
```

`programas/urls.py`:

```python
    path("config/programas/<int:pk>/funcion-siis/", cfg.programa_funcion_siis, name="programa_funcion_siis"),
```

`programa_detail.html`, después del bloque `{% if programa.siis_bloqueado %}…{% endif %}`:

```django
  {# Alta de beneficiarios en SIIS: función del programa (id_fun_x_plan) #}
  <section class="bg-white rounded-xl border border-base shadow-sm p-5">
    <div class="flex items-start justify-between gap-4 flex-wrap">
      <div>
        <h2 class="text-heading font-bold" style="font-size:16px;">Alta de beneficiarios en SIIS</h2>
        <p class="text-sm text-body-subtle mt-1">
          Los casos aprobados se informan a SIIS con la función
          {% if programa.siis_funcion_id %}<strong class="text-heading">{{ programa.siis_funcion_nombre }} (#{{ programa.siis_funcion_id }})</strong>{% else %}<span class="badge badge-warning">sin configurar</span>{% endif %}.
        </p>
      </div>
      {% if puede_administrar_programa %}
      <form method="post" action="{% url 'becas:programa_funcion_siis' programa.pk %}" class="flex items-end gap-2 flex-wrap">
        {% csrf_token %}
        <div>
          <label for="{{ form_funcion_siis.siis_funcion_id.id_for_label }}" class="block text-sm font-medium text-heading mb-1">Función SIIS</label>
          {{ form_funcion_siis.siis_funcion_id }}
          {% if form_funcion_siis.siis_funcion_id.help_text %}<p class="mt-1 text-xs text-fg-danger">{{ form_funcion_siis.siis_funcion_id.help_text }}</p>{% endif %}
        </div>
        <button type="submit" class="btn-nodo btn-brand btn-base">Guardar</button>
      </form>
      {% endif %}
    </div>
  </section>
```

- [ ] **Step 4: Correr** → tests PASS; `design_audit.py --changed` 0; `compile_templates.py` 0.

- [ ] **Step 5: Commit**

```bash
git add programas/forms.py programas/views/configuracion.py programas/urls.py programas/templates/programas/becas/config/programa_detail.html programas/tests/test_becas_config.py
git commit -m "feat(siis): funcion del programa para el alta de beneficiarios, elegida del catalogo"
```

---

### Task 9: UI del caso — sección "Envío a SIIS" y modal de datos

**Files:**
- Modify: `programas/views/revision.py` (`formulario_detalle` contexto), `programas/templates/programas/becas/revision/formulario_detalle.html`
- Test: `programas/tests/test_becas_revision.py`

- [ ] **Step 1: Tests**

```python
class UiEnvioSiisTests(_BaseAprobacionTest):
    def setUp(self):
        super().setUp()
        patch("programas.forms.catalogo", side_effect=lambda n: []).start()
        self.addCleanup(patch.stopall)

    def test_seccion_no_aparece_en_casos_no_aprobados(self):
        resp = self.client.get(reverse("becas:formulario_detalle", args=[self.form_a.pk]))
        self.assertNotContains(resp, "Envío a SIIS")

    def test_seccion_muestra_estado_detalles_y_acciones(self):
        self.form_a.estado = Formulario.Estado.APROBADO
        self.form_a.save(update_fields=["estado"])
        EnvioSIIS.objects.create(
            formulario=self.form_a, estado=EnvioSIIS.Estado.INCOMPLETO, documento="1",
            detalles={"loc_actual": "La localidad no coincide con el catálogo de SIIS: elegila de la lista."},
        )
        resp = self.client.get(reverse("becas:formulario_detalle", args=[self.form_a.pk]))
        self.assertContains(resp, "Envío a SIIS")
        self.assertContains(resp, "Datos incompletos")
        self.assertContains(resp, "elegila de la lista")
        self.assertContains(resp, reverse("becas:formulario_enviar_siis", args=[self.form_a.pk]))
        self.assertContains(resp, reverse("becas:formulario_datos_siis", args=[self.form_a.pk]))

    def test_enviado_oculta_las_acciones(self):
        self.form_a.estado = Formulario.Estado.APROBADO
        self.form_a.save(update_fields=["estado"])
        EnvioSIIS.objects.create(formulario=self.form_a, estado=EnvioSIIS.Estado.ENVIADO, documento="1", siis_id=26)
        resp = self.client.get(reverse("becas:formulario_detalle", args=[self.form_a.pk]))
        self.assertContains(resp, "ID SIIS")
        self.assertNotContains(resp, reverse("becas:formulario_enviar_siis", args=[self.form_a.pk]))
```

- [ ] **Step 2: Correr y ver fallar.**

- [ ] **Step 3: Implementación**

Contexto en `formulario_detalle` (antes del `render`):

```python
    envios_sis = []
    envio_siis = None
    datos_siis_form = None
    if formulario.estado == Formulario.Estado.APROBADO:
        envios_sis = list(formulario.envios_sis.select_related("solicitado_por"))
        envio_siis = envios_sis[0] if envios_sis else None
        if puede(request.user, CAP_REVISION_EDITAR) and not (envio_siis and envio_siis.estado == EnvioSIIS.Estado.ENVIADO):
            datos_siis_form = DatosSiisForm(initial=formulario.datos_siis or {})
```

y en el dict: `"envio_siis": envio_siis, "historial_envios_sis": envios_sis, "datos_siis_form": datos_siis_form, "puede_enviar_siis": puede(request.user, CAP_REVISION_EDITAR)`. Importar `EnvioSIIS`.

Template, después de la sección `{# 6. Resultado SIIS #}` (cerrar su `</section>` y agregar):

```django
  {% if formulario.estado == 'APROBADO' %}
  {# 7. Envío a SIIS (alta del beneficiario en la tabla intermedia) #}
  <section class="bg-white rounded-xl border border-base shadow-sm overflow-hidden" aria-labelledby="titulo-envio-siis">
    <div class="px-5 py-4 border-b border-light flex items-center gap-2">
      <i class="fas fa-paper-plane text-fg-brand" aria-hidden="true"></i>
      <h2 id="titulo-envio-siis" class="text-heading font-bold" style="font-size:16px;">Envío a SIIS</h2>
    </div>
    <div class="p-6">
      {% if envio_siis %}
      <div class="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <p class="text-xs uppercase tracking-wide font-semibold text-body-subtle mb-2">Último intento</p>
          {% if envio_siis.estado == 'ENVIADO' %}<span class="badge badge-success badge-dot">Enviado</span>
          {% elif envio_siis.estado == 'INCOMPLETO' %}<span class="badge badge-warning badge-dot">Datos incompletos</span>
          {% elif envio_siis.estado == 'RECHAZADO' %}<span class="badge badge-danger badge-dot">Rechazado por SIIS</span>
          {% else %}<span class="badge badge-warning badge-dot">Error técnico</span>{% endif %}
        </div>
        <p class="text-xs text-body-subtle">{{ envio_siis.creado|date:"d/m/Y H:i" }} · {{ envio_siis.solicitado_por.username|default:"sistema" }}</p>
      </div>
      {% if envio_siis.siis_id %}
      <dl class="mt-4"><dt class="text-xs uppercase tracking-wide font-semibold text-body-subtle">ID SIIS</dt><dd class="text-heading text-sm font-medium">#{{ envio_siis.siis_id }}</dd></dl>
      {% endif %}
      {% if envio_siis.detalles %}
      <div class="mt-4 rounded-lg bg-warning-soft border border-warning-subtle p-4 text-sm" role="status">
        <p class="font-semibold text-heading mb-2">{% if envio_siis.estado == 'RECHAZADO' %}SIIS señaló:{% else %}Falta resolver:{% endif %}</p>
        <ul class="space-y-1">
          {% for campo, mensajes in envio_siis.detalles.items %}
          <li><span class="font-mono text-xs text-body-subtle">{{ campo }}</span> — {% if mensajes|length and mensajes.0 %}{{ mensajes|join:" " }}{% else %}{{ mensajes }}{% endif %}</li>
          {% endfor %}
        </ul>
      </div>
      {% endif %}
      {% else %}
      <p class="text-sm text-body-subtle">El beneficiario todavía no fue informado a SIIS.</p>
      {% endif %}

      {% if puede_enviar_siis and envio_siis.estado != 'ENVIADO' %}
      <div class="mt-5 flex items-center gap-3 flex-wrap">
        {% if datos_siis_form %}
        <button type="button" id="btn-datos-siis" class="btn-nodo btn-secondary btn-base"><i class="fas fa-pen" aria-hidden="true"></i> Completar datos para SIIS</button>
        {% endif %}
        <form method="post" action="{% url 'becas:formulario_enviar_siis' formulario.pk %}">
          {% csrf_token %}
          <button type="submit" class="btn-nodo btn-brand btn-base">{% if envio_siis %}Reenviar a SIIS{% else %}Informar a SIIS{% endif %}</button>
        </form>
        {% if historial_envios_sis|length > 1 %}
        <button type="button" id="btn-historial-envios-siis" class="btn-nodo btn-tertiary btn-base ml-auto" aria-expanded="false" aria-controls="historial-envios-siis">
          <i class="fas fa-history" aria-hidden="true"></i> Historial de envíos ({{ historial_envios_sis|length }})
        </button>
        {% endif %}
      </div>
      {% endif %}

      {% if historial_envios_sis|length > 1 %}
      <div id="historial-envios-siis" class="hidden mt-5 border-t border-light pt-5" aria-label="Historial de envíos a SIIS">
        <div class="space-y-3">
          {% for item in historial_envios_sis %}
          <article class="rounded-lg border border-light bg-secondary p-4">
            <div class="flex items-start justify-between gap-3 flex-wrap">
              <span class="text-sm text-heading font-medium">{{ item.get_estado_display }}{% if item.codigo_error %} · {{ item.codigo_error }}{% endif %}{% if item.siis_id %} · ID {{ item.siis_id }}{% endif %}</span>
              <time class="text-xs text-body-subtle">{{ item.creado|date:"d/m/Y H:i" }}</time>
            </div>
          </article>
          {% endfor %}
        </div>
      </div>
      {% endif %}
    </div>
  </section>
  {% endif %}
```

Modal (junto a los otros modales, mismo markup que el de "forzar"; el `<form>` apunta a `becas:formulario_datos_siis` y renderiza `datos_siis_form` con `{% include "programas/becas/_field.html" %}` en dos columnas; ids `modal-datos-siis-overlay`, `modal-datos-siis-close`, `modal-datos-siis-cancelar`, `form-datos-siis`). Al abrirlo, el JS carga localidades:

```javascript
  // Modal "Completar datos para SIIS" — selects de localidad dependientes de la provincia.
  const datosSiisOverlay = document.getElementById('modal-datos-siis-overlay');
  if (datosSiisOverlay) {
    const urlLocalidades = "{% url 'becas:siis_localidades' %}";
    function cargarLocalidades(selProv, selLoc, actual) {
      selLoc.innerHTML = '<option value="">Sin cambios</option>';
      if (!selProv.value) return;
      fetch(urlLocalidades + '?provincia=' + encodeURIComponent(selProv.value), {credentials: 'same-origin'})
        .then(r => r.json())
        .then(data => {
          (data.localidades || []).forEach(l => {
            const o = document.createElement('option');
            o.value = l.id; o.textContent = l.nombre;
            if (String(l.id) === String(actual || '')) o.selected = true;
            selLoc.appendChild(o);
          });
          if (data.error) window.toast(data.error, 'error');
        })
        .catch(() => window.toast('No se pudieron cargar las localidades de SIIS.', 'error'));
    }
    [['id_prov_actual', 'id_loc_actual', '{{ formulario.datos_siis.loc_actual|default:"" }}'],
     ['id_prov_nacim', 'id_loc_nacim', '{{ formulario.datos_siis.loc_nacim|default:"" }}']].forEach(([p, l, actual]) => {
      const selProv = document.getElementById(p), selLoc = document.getElementById(l);
      if (!selProv || !selLoc) return;
      selProv.addEventListener('change', () => cargarLocalidades(selProv, selLoc, ''));
      cargarLocalidades(selProv, selLoc, actual);
    });
    function cerrar() { datosSiisOverlay.classList.add('hidden'); datosSiisOverlay.style.display = 'none'; }
    document.getElementById('btn-datos-siis').addEventListener('click', () => { datosSiisOverlay.classList.remove('hidden'); datosSiisOverlay.style.display = 'flex'; });
    document.getElementById('modal-datos-siis-cancelar').addEventListener('click', cerrar);
    document.getElementById('modal-datos-siis-close').addEventListener('click', cerrar);
    datosSiisOverlay.addEventListener('click', e => { if (e.target === datosSiisOverlay) cerrar(); });
    document.addEventListener('keydown', e => { if (e.key === 'Escape' && !datosSiisOverlay.classList.contains('hidden')) cerrar(); });
  }
  const btnHistEnv = document.getElementById('btn-historial-envios-siis');
  const histEnv = document.getElementById('historial-envios-siis');
  if (btnHistEnv && histEnv) {
    btnHistEnv.addEventListener('click', () => {
      const abierto = btnHistEnv.getAttribute('aria-expanded') === 'true';
      btnHistEnv.setAttribute('aria-expanded', String(!abierto));
      histEnv.classList.toggle('hidden', abierto);
    });
  }
```

Los selects de localidad (`loc_actual`, `loc_nacim`) son `IntegerField` con widget `Select`: el form acepta el valor entero que llega del `<option>`.

- [ ] **Step 4: Auditorías y tests**

Run: `& $env:PY_VENV manage.py test programas.tests.test_becas_revision` → PASS.
Run: `& $env:PY_VENV scripts\design_audit.py --changed` → 0 errores. `& $env:PY_VENV scripts\compile_templates.py` → 0. `& $env:PY_VENV scripts\check_design_agent.py --changed` → OK.
Si se usan clases Tailwind nuevas que no estén en el CSS committeado: `npm run build:tailwind` y commitear la salida.

- [ ] **Step 5: Commit**

```bash
git add programas/views/revision.py programas/templates/programas/becas/revision/formulario_detalle.html programas/tests/test_becas_revision.py
git commit -m "feat(siis): seccion Envio a SIIS en el caso, con detalle por campo, correccion y reenvio"
```

---

### Task 10: Comando de reintento

**Files:**
- Create: `programas/management/commands/reenviar_siis_pendientes.py`
- Test: `programas/tests/test_siis_envio.py`

- [ ] **Step 1: Tests**

```python
from django.core.management import call_command


class ComandoReenvioTests(_BaseEnvioTest):
    def setUp(self):
        super().setUp()
        self.enviar = patch("programas.management.commands.reenviar_siis_pendientes.enviar_beneficiario_a_siis").start()
        self.addCleanup(patch.stopall)
        self.enviar.side_effect = lambda f, u, **kw: EnvioSIIS(formulario=f, estado=EnvioSIIS.Estado.ENVIADO, siis_id=1)

    def test_reintenta_solo_errores_tecnicos(self):
        EnvioSIIS.objects.create(formulario=self.formulario, estado=EnvioSIIS.Estado.ERROR, documento="1", codigo_error="ERROR_BD_LEGACY")
        otro = Formulario.objects.create(relevamiento=self.relevamiento, ciudadano=self.ciudadano, celular="1", email_contacto="a@b.c", estado=Formulario.Estado.APROBADO)
        EnvioSIIS.objects.create(formulario=otro, estado=EnvioSIIS.Estado.INCOMPLETO, documento="1")
        salida = StringIO()
        call_command("reenviar_siis_pendientes", stdout=salida)
        self.assertEqual(self.enviar.call_count, 1)
        self.assertEqual(self.enviar.call_args.args[0].pk, self.formulario.pk)
        self.assertIn("1 reintentado", salida.getvalue())

    def test_dry_run_no_envia(self):
        EnvioSIIS.objects.create(formulario=self.formulario, estado=EnvioSIIS.Estado.ERROR, documento="1")
        call_command("reenviar_siis_pendientes", "--dry-run", stdout=StringIO())
        self.enviar.assert_not_called()

    def test_sin_envios_no_hace_nada(self):
        call_command("reenviar_siis_pendientes", stdout=StringIO())
        self.enviar.assert_not_called()
```

- [ ] **Step 2: Correr y ver fallar** → `CommandError: Unknown command`.

- [ ] **Step 3: Implementación**

```python
"""Reintenta el alta en SIIS de los beneficiarios cuyo último envío fue un
error técnico (401/5xx/red/catálogo caído). Los ``INCOMPLETO`` y ``RECHAZADO``
necesitan corrección humana y no se tocan. Pensado para un cron o para correr
a mano después de una caída del legacy de SIIS."""

from django.core.management.base import BaseCommand
from django.db.models import OuterRef, Subquery

from programas.models import EnvioSIIS, Formulario
from programas.services.siis_envio import Catalogos, enviar_beneficiario_a_siis


class Command(BaseCommand):
    help = "Reintenta los envíos a SIIS que fallaron por error técnico."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Lista sin enviar.")
        parser.add_argument("--limite", type=int, default=200, help="Máximo de casos por corrida.")

    def handle(self, *args, **options):
        ultimo = EnvioSIIS.objects.filter(formulario=OuterRef("pk")).order_by("-creado").values("estado")[:1]
        casos = (
            Formulario.objects.filter(estado=Formulario.Estado.APROBADO)
            .annotate(ultimo_estado=Subquery(ultimo))
            .filter(ultimo_estado=EnvioSIIS.Estado.ERROR)
            .select_related("ciudadano", "relevamiento__convocatoria__segmento__programa", "apoderado_ciudadano")
            .order_by("pk")[: options["limite"]]
        )
        casos = list(casos)
        if not casos:
            self.stdout.write("Sin envíos pendientes de reintento.")
            return
        if options["dry_run"]:
            for f in casos:
                self.stdout.write(f"[dry-run] caso #{f.pk} · DNI {f.ciudadano.dni if f.ciudadano_id else '-'}")
            self.stdout.write(f"{len(casos)} caso(s) a reintentar.")
            return
        catalogos = Catalogos()
        resumen = {}
        for f in casos:
            envio = enviar_beneficiario_a_siis(f, None, catalogos=catalogos)
            resumen[envio.estado] = resumen.get(envio.estado, 0) + 1
            self.stdout.write(f"caso #{f.pk}: {envio.get_estado_display()}")
        detalle = ", ".join(f"{n} {estado.lower()}" for estado, n in sorted(resumen.items()))
        self.stdout.write(self.style.SUCCESS(f"{len(casos)} reintentado(s): {detalle}."))
```

- [ ] **Step 4: Correr** → PASS.

- [ ] **Step 5: Commit**

```bash
git add programas/management/commands/reenviar_siis_pendientes.py programas/tests/test_siis_envio.py
git commit -m "feat(siis): comando reenviar_siis_pendientes para los errores tecnicos"
```

---

### Task 11: Documentación, registro y cierre

**Files:**
- Modify: `docs/internal/temas/siis-api.md`, `docs/internal/requerimientos.md`

- [ ] **Step 1: `siis-api.md`** — agregar a la tabla de endpoints:

```
| 5 | `POST /api/v1/auth/tab-intermedia` — objeto o arreglo de 30 campos | Alta de beneficiarios en la tabla intermedia (manual v4.2, sep-2026). 201 con `ids_generados`; 400 `DATOS_INVALIDOS` con `detalles` por campo; 503 `ERROR_BD_LEGACY` reintentable |
| 6 | `GET /api/v1/auth/catalogos/{provincias|localidades|estados-civiles|tipos-documento|jurisdicciones}` y `.../funciones?id_programa=` | Catálogos maestros para los ids del alta |
```

y una sección "Alta de beneficiarios" con: qué dispara el envío, `EnvioSIIS`, `destino_siis`, `datos_siis`, el comando, y los límites externos (sin baja/modificación, `S/N`, `jurisdiccion_id`).

- [ ] **Step 2: `requerimientos.md`** — entrada nueva con la plantilla del archivo (Programa/módulo Becas · revisión e integraciones; etiquetas `#siis #relevamientos #datos #ui`; Pedido; Alcance; Decisiones tomadas: las 6 del PM + la cuestión abierta del lugar de nacimiento; Implementación; Archivos; Base de datos `0060`; Validación; Puesta en marcha: deploy + `migrate` + configurar función del programa + marcar destinos en las preguntas; Pendientes: `S/N`, baja/modificación, cron del comando, reenvío retroactivo). Fila en el índice. Actualizar el Cambio 50 con historial fechado: el pendiente 1 pasa a hecho.

- [ ] **Step 3: Verificación completa**

```powershell
& $env:PY_VENV manage.py check
& $env:PY_VENV manage.py makemigrations --check --dry-run
& $env:PY_VENV manage.py test programas.tests.test_siis_envio programas.tests.test_siis_service programas.tests.test_becas_revision programas.tests.test_becas_config programas.tests.test_becas_rbac
& $env:PY_VENV -m ruff check .
& $env:PY_VENV -m ruff format --check .
& $env:PY_VENV scripts\design_audit.py --changed
& $env:PY_VENV scripts\compile_templates.py
& $env:PY_VENV scripts\check_design_agent.py --changed
& $env:PY_VENV scripts\requerimientos.py --check
```

- [ ] **Step 4: Commit y PR**

```bash
git add docs/internal/temas/siis-api.md docs/internal/requerimientos.md docs/plans/2026-09-14-siis-envio-beneficiarios-design.md docs/plans/2026-09-14-siis-envio-beneficiarios-plan.md
git commit -m "docs(siis): registro del alta de beneficiarios (Cambio nuevo) y contrato v4.2"
git push -u origin feature/siis-envio-beneficiarios
gh pr create --repo Mkdir-arg/Chaco-Back --base development --title "feat(siis): alta de beneficiarios aprobados en la tabla intermedia" --body "..."
```
