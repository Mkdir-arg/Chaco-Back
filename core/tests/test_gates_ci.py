"""Los gates del CI son obligatorios de verdad (RED-20, RED-63, RED-85, RED-24, RED-23, RED-22).

El 04/10/2026 `CLAUDE.md` §«Gates de CI» describía una política que no existía:
`gh api repos/Mkdir-arg/Chaco-Back/rulesets` devolvía `[]` y
`branches/development/protection` devolvía 404, así que un PR en rojo se mergeaba
con el botón normal y 23 commits de código entraron en 90 días sin pasar por
ningún workflow. Encima dos de los checks filtraban por `paths:` en el trigger:
un check que no corre nunca termina, y uno que no termina no puede ser
obligatorio.

Este módulo es el «test permanente» (RED-34) de las tres fichas del PR R-03:

- **RED-20** — los rulesets propuestos viven versionados en `docs/internal/rulesets/`
  (los aplica el dueño del repo), cada check que exigen existe como job y su
  workflow corre en **todos** los PRs a `development`.
- **RED-63** — `Ruff errores` (`--select F`) es bloqueante y las excepciones de
  `pip-audit` tienen vencimiento verificado.
- **RED-85** — las actions de los workflows con `contents: write` y `dorny/paths-filter`
  están pineadas por SHA.

El PR R-14 (Cambio 128) suma las tres fichas de los gates del release:

- **RED-24** — las condiciones de cierre de `CLAUDE.md` (`compile_templates`,
  `requerimientos --check`, `collectstatic`, `design_audit`) corrían solo en la máquina de
  quien desarrolla; ahora son el job obligatorio `Contratos del repo`.
- **RED-23** — `release-gate.yml` verifica el release **antes** del espejo, y el
  procedimiento del espejo está partido en TEST y PRD.
- **RED-22** — la etapa `verify` se le propone a ECOM por escrito, sin tocar el
  `.gitlab-ci.yml` que es de ellos.

El PR 5 de la Ola 7 (Cambio 199) suma las dos fichas de calidad del propio CI:

- **RED-86** — la suite corre en paralelo (`--parallel 4`), la cobertura se sigue midiendo
  con los procesos hijos (`concurrency = ["multiprocessing"]` + `coverage combine`) y la
  duración queda escrita en el resumen del job, con aviso sobre 12 min.
- **RED-76** — `mypy` existe, con un alcance acotado que crece un módulo por PR y arranca
  no bloqueante.

No toca la red: todo sale de los archivos del repo.
"""

import datetime
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import tomllib
import yaml
from django.conf import settings
from django.test import SimpleTestCase
from django.urls import resolve

RAIZ = Path(settings.BASE_DIR)
WORKFLOWS = RAIZ / ".github" / "workflows"
RULESETS = RAIZ / "docs" / "internal" / "rulesets"
EXCEPCIONES = RAIZ / "security" / "excepciones.toml"
VERIFICADOR = RAIZ / "scripts" / "check_excepciones_seguridad.py"
AUDITORIA = RAIZ / "scripts" / "design_audit.py"
RATCHET = RAIZ / ".design-audit-ratchet"

# `uses: owner/repo@referencia  # comentario`
USES = re.compile(r"^\s*-?\s*uses:\s*(?P<accion>[^@\s]+)@(?P<ref>\S+)\s*(?:#\s*(?P<comentario>.*))?$", re.MULTILINE)
SHA = re.compile(r"^[0-9a-f]{40}$")

# RED-85
REQUIREMENTS_CI = RAIZ / "requirements-ci.txt"
DEPENDABOT = RAIZ / ".github" / "dependabot.yml"
HERRAMIENTAS_DEL_CI = (
    "ruff",
    "coverage",
    "pip-audit",
    "bandit",
    "mkdocs-material",
    # RED-76. Los tres van juntos: `django-stubs[compatible-mypy]` es el que fija qué
    # mypy soporta y `djangorestframework-stubs` exige `django-stubs>=6`.
    "mypy",
    "django-stubs",
    "djangorestframework-stubs",
)
#: Cómo se invoca cada herramienta en un `run:` (`mkdocs-material` instala `mkdocs`).
INVOCACION = re.compile(r"(?m)^\s*(?:python -m\s+)?(ruff|coverage|pip-audit|bandit|mkdocs|mypy)\b")
#: Un `pip install` cualquiera. Lo único admitido es `-r <archivo>` o el `--upgrade pip`.
PIP_INSTALL = re.compile(r"(?m)^\s*(?:python -m\s+)?pip install\s+(?P<argumentos>.+)$")


def _cargar(nombre):
    return yaml.safe_load((WORKFLOWS / nombre).read_text(encoding="utf-8"))


def _pyproject():
    return tomllib.loads((RAIZ / "pyproject.toml").read_text(encoding="utf-8"))


def _disparador_pull_request(flujo):
    """`on` se parsea como `True` en YAML 1.1 (`on` es booleano): hay que buscar las dos."""
    disparadores = flujo.get("on", flujo.get(True, {})) or {}
    return disparadores.get("pull_request") or {}


def _nombres_de_jobs(flujo):
    return {datos.get("name", job): job for job, datos in (flujo.get("jobs") or {}).items()}


def _todos_los_workflows():
    return {ruta.name: _cargar(ruta.name) for ruta in sorted(WORKFLOWS.glob("*.yml"))}


def _lineas_de_requisitos(ruta):
    """Las líneas de un `requirements*.txt` que declaran un paquete (sin comentarios)."""
    return [
        linea.strip()
        for linea in ruta.read_text(encoding="utf-8").splitlines()
        if linea.strip() and not linea.lstrip().startswith(("#", "-r "))
    ]


def _distribucion(linea):
    """`bandit[toml]==1.9.4` → `bandit`."""
    return linea.split("==")[0].split("[")[0].strip().lower()


# La lista literal de lo que el ruleset tiene que exigir. Va escrita a mano y no derivada
# del JSON a propósito: los demás tests leen el JSON, así que sacarle un `context` los deja
# a todos en verde —el gate desaparece y nadie se entera—. Este es el que lo enfrenta.
# Agregar o quitar un check obligatorio implica tocar esta lista en el mismo PR.
CHECKS_OBLIGATORIOS = {
    "Django System Check",
    "Migration Check",
    "Tests & Coverage",
    "Query Budgets & Smoke Time",
    "Ephemeral MySQL Redis Contract",
    "Pip Audit",
    "Sin datos personales",
    "Ruff errores",
    "Validate inventory and authority",
    # RED-24, Cambio 128: la ficha de RED-20 ya lo anticipaba («los checks nuevos se
    # suman a la lista cuando existan»).
    "Contratos del repo",
    # RED-43, Cambio 160 (PR R-18): el gate de contrato de API. Entra obligatorio desde
    # el primer día porque es determinista, no toca la red ni el motor real y mide ~9 s
    # de tests; el filtro por rutas va adentro del job, así que reporta siempre.
    "Contratos de API",
}


def _contextos_obligatorios():
    ruleset = json.loads((RULESETS / "ruleset-development.json").read_text(encoding="utf-8"))
    for regla in ruleset["rules"]:
        if regla["type"] == "required_status_checks":
            return [c["context"] for c in regla["parameters"]["required_status_checks"]]
    raise AssertionError("el ruleset de development no exige ningún status check")


_SPEC = importlib.util.spec_from_file_location("check_excepciones_seguridad", VERIFICADOR)
check_excepciones = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(check_excepciones)


class RulesetsPropuestosTests(SimpleTestCase):
    """Los rulesets son el único mecanismo que vuelve obligatorio cualquier gate nuevo."""

    def setUp(self):
        self.development = json.loads((RULESETS / "ruleset-development.json").read_text(encoding="utf-8"))
        self.main = json.loads((RULESETS / "ruleset-main.json").read_text(encoding="utf-8"))

    def _regla(self, ruleset, tipo):
        return next((r for r in ruleset["rules"] if r["type"] == tipo), None)

    def test_el_ruleset_de_development_apunta_a_development_y_esta_activo(self):
        self.assertEqual(self.development["target"], "branch")
        self.assertEqual(self.development["enforcement"], "active")
        self.assertEqual(self.development["conditions"]["ref_name"]["include"], ["refs/heads/development"])

    def test_el_ruleset_de_development_exige_pr_sin_aprobaciones(self):
        """Todo el equipo publica con la misma cuenta y GitHub no deja aprobar el propio PR.

        Exigir 1 aprobación bloquearía todos los merges (README §0.4). La revisión
        independiente sigue siendo el «Aprobado @ SHA» del proceso, no el botón.
        """
        pull_request = self._regla(self.development, "pull_request")

        self.assertIsNotNone(pull_request, "el ruleset tiene que exigir PR")
        self.assertEqual(pull_request["parameters"]["required_approving_review_count"], 0)

    def test_el_ruleset_de_development_exige_la_rama_al_dia(self):
        """Sin `strict`, un PR verde contra una base vieja mergea igual."""
        checks = self._regla(self.development, "required_status_checks")

        self.assertTrue(checks["parameters"]["strict_required_status_checks_policy"])

    def test_el_ruleset_de_development_protege_contra_borrado_y_reescritura(self):
        tipos = {regla["type"] for regla in self.development["rules"]}

        self.assertIn("deletion", tipos)
        self.assertIn("non_fast_forward", tipos)

    def test_el_ruleset_de_development_no_deja_pasar_a_nadie_por_arriba(self):
        self.assertEqual(self.development["bypass_actors"], [])

    def test_el_ruleset_de_main_bloquea_todo_salvo_github_actions(self):
        """`main` es una release generada: la escribe `publish-main.yml` y nadie más."""
        tipos = {regla["type"] for regla in self.main["rules"]}

        self.assertEqual(tipos, {"deletion", "non_fast_forward", "update"})
        self.assertEqual(
            self.main["bypass_actors"],
            [{"actor_id": 15368, "actor_type": "Integration", "bypass_mode": "always"}],
        )

    def test_el_ruleset_de_development_exige_exactamente_estos_diez_checks(self):
        """Sacar un `context` del JSON no puede pasar en silencio.

        Todos los demás tests leen la lista del propio archivo, así que borrar
        `{"context": "Ruff errores"}` los dejaba a los 27 en verde: el gate se apagaba sin
        que nada cayera. Este enfrenta el JSON contra la lista literal de arriba.
        """
        self.assertEqual(set(_contextos_obligatorios()), CHECKS_OBLIGATORIOS)

    def test_no_hay_checks_obligatorios_repetidos(self):
        contextos = _contextos_obligatorios()

        self.assertEqual(len(contextos), len(set(contextos)))

    def test_el_ruleset_de_main_no_exige_status_checks(self):
        """`main` no recibe PRs: la escribe `publish-main.yml`. Si alguna vez exigiera un
        check, el workflow que la publica quedaría esperándose a sí mismo.
        """
        tipos = {regla["type"] for regla in self.main["rules"]}

        self.assertNotIn("required_status_checks", tipos)
        self.assertNotIn("pull_request", tipos)

    def test_cada_check_obligatorio_existe_como_job_de_un_workflow(self):
        """Un `context` mal escrito deja el PR esperando para siempre un check que no llega."""
        publicados = set()
        for flujo in _todos_los_workflows().values():
            publicados.update(_nombres_de_jobs(flujo))

        faltantes = [c for c in _contextos_obligatorios() if c not in publicados]

        self.assertEqual(faltantes, [], f"checks obligatorios que ningún job publica: {faltantes}")

    def test_los_workflows_de_los_checks_obligatorios_corren_en_todo_pr_a_development(self):
        """Con `paths:` en el trigger el check no corre, queda «expected» y bloquea para siempre.

        Es lo que arregla el punto 3 de RED-20: el filtro va **adentro** del job.
        """
        obligatorios = set(_contextos_obligatorios())

        for nombre, flujo in _todos_los_workflows().items():
            jobs = set(_nombres_de_jobs(flujo))
            if not jobs & obligatorios:
                continue
            with self.subTest(workflow=nombre):
                pull_request = _disparador_pull_request(flujo)
                self.assertIn("development", pull_request.get("branches") or [])
                self.assertNotIn("paths", pull_request, "el filtro de rutas va adentro del job")
                self.assertNotIn("paths-ignore", pull_request)

    def test_ningun_job_obligatorio_puede_ponerse_en_verde_con_continue_on_error(self):
        obligatorios = set(_contextos_obligatorios())

        for nombre, flujo in _todos_los_workflows().items():
            for publicado, job in _nombres_de_jobs(flujo).items():
                if publicado not in obligatorios:
                    continue
                with self.subTest(workflow=nombre, job=publicado):
                    self.assertNotIn("continue-on-error", flujo["jobs"][job])

    def test_el_procedimiento_para_aplicar_los_rulesets_esta_escrito(self):
        """Los aplica el dueño del repo: si el comando no está escrito, no se aplican."""
        guia = (RAIZ / "docs" / "internal" / "rulesets.md").read_text(encoding="utf-8")

        self.assertIn("repos/Mkdir-arg/Chaco-Back/rulesets", guia)
        self.assertIn("docs/internal/rulesets/ruleset-development.json", guia)
        self.assertIn("docs/internal/rulesets/ruleset-main.json", guia)


class PushDirectoADevelopmentTests(SimpleTestCase):
    """Mientras no estén los rulesets, un push directo tiene que dejar un check rojo visible."""

    def test_backend_y_performance_tambien_corren_en_push_a_development(self):
        for nombre in ("pr-backend.yml", "pr-performance.yml"):
            with self.subTest(workflow=nombre):
                flujo = _cargar(nombre)
                disparadores = flujo.get("on", flujo.get(True, {}))

                self.assertIn("push", disparadores, "un push directo no dispararía nada")
                self.assertIn("development", disparadores["push"]["branches"])


class RuffBloqueanteTests(SimpleTestCase):
    """RED-63: los errores reales de Ruff dejan de salir en amarillo."""

    def setUp(self):
        self.flujo = _cargar("pr-quality.yml")
        self.texto = (WORKFLOWS / "pr-quality.yml").read_text(encoding="utf-8")

    def _job(self, publicado):
        job = _nombres_de_jobs(self.flujo).get(publicado)
        self.assertIsNotNone(job, f"no existe el job «{publicado}»")
        return self.flujo["jobs"][job]

    def test_el_job_de_errores_bloquea_y_selecciona_la_familia_f(self):
        """`F` es «nombre indefinido, import roto, variable fantasma»: nunca es estilo."""
        job = self._job("Ruff errores")

        self.assertNotIn("continue-on-error", job)
        comandos = " ".join(paso.get("run", "") for paso in job["steps"])
        self.assertIn("--select F", comandos)

    def test_el_job_de_estilo_sigue_sin_bloquear(self):
        """Hoy da 0 y desde el Cambio 196 Ruff está pineado (`requirements-ci.txt`,
        RED-85), que era la condición técnica que faltaba. Encenderlo —sacarle el
        `continue-on-error` y sumarlo al ruleset— lo decide el PM, y mientras tanto este
        test fija el estado que hay.
        """
        job = self._job("Ruff estilo")

        self.assertTrue(job.get("continue-on-error"))
        comandos = " ".join(paso.get("run", "") for paso in job["steps"])
        self.assertIn("E,W,I", comandos)

    def test_el_job_de_estilo_no_reporta_las_lineas_largas_que_el_repo_ignora(self):
        """Un `--select` por línea de comandos pisa también el `ignore` de `pyproject.toml`.

        Sin el `--ignore E501` explícito, el job escupe las 43 líneas largas que el repo
        ignora a propósito y el único job de estilo queda en rojo permanente, o sea mudo.
        """
        comandos = " ".join(paso.get("run", "") for paso in self._job("Ruff estilo")["steps"])

        self.assertIn("--ignore E501", comandos)

    @unittest.skipUnless(shutil.which("ruff"), "hace falta ruff en el PATH")
    def test_ruff_select_f_no_tiene_hallazgos_hoy(self):
        """Antes de encender el gate hay que verificar que da 0 (lo pide la ficha)."""
        corrida = subprocess.run(
            ["ruff", "check", ".", "--select", "F", "--output-format", "concise"],
            cwd=RAIZ,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        self.assertEqual(corrida.returncode, 0, corrida.stdout)


class ExcepcionesDeSeguridadTests(SimpleTestCase):
    """RED-63: ninguna excepción de `pip-audit` es permanente de hecho."""

    def _escribir(self, contenido):
        carpeta = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, carpeta, True)
        archivo = carpeta / "excepciones.toml"
        archivo.write_text(contenido, encoding="utf-8")
        return archivo

    def test_cada_excepcion_declara_id_motivo_vencimiento_y_ticket(self):
        for entrada in check_excepciones.cargar(EXCEPCIONES):
            with self.subTest(id=entrada.get("id")):
                for clave in check_excepciones.CLAVES:
                    self.assertIn(clave, entrada)
                self.assertIsInstance(entrada["vence_el"], datetime.date)
                self.assertTrue(str(entrada["motivo"]).strip())
                self.assertTrue(str(entrada["ticket"]).strip())

    def test_ninguna_excepcion_del_repo_esta_vencida(self):
        """Este test es el que se pone rojo el día del vencimiento, en el PR y no en PRD."""
        errores = check_excepciones.revisar(check_excepciones.cargar(EXCEPCIONES), datetime.date.today())

        self.assertEqual(errores, [])

    def test_el_verificador_rechaza_una_excepcion_vencida(self):
        archivo = self._escribir(
            '[[pip_audit]]\nid = "PYSEC-0000-1"\nmotivo = "x"\nvence_el = 2026-01-01\nticket = "RED-63"\n'
        )

        errores = check_excepciones.revisar(check_excepciones.cargar(archivo), datetime.date(2026, 10, 4))

        self.assertEqual(len(errores), 1)
        self.assertIn("venció", errores[0])

    def test_el_verificador_rechaza_una_excepcion_sin_vencimiento(self):
        archivo = self._escribir('[[pip_audit]]\nid = "PYSEC-0000-1"\nmotivo = "x"\nticket = "RED-63"\n')

        errores = check_excepciones.revisar(check_excepciones.cargar(archivo), datetime.date(2026, 10, 4))

        self.assertEqual(len(errores), 1)
        self.assertIn("vence_el", errores[0])

    def test_el_verificador_rechaza_un_vencimiento_escrito_como_texto(self):
        """`vence_el = "2027-01-02"` parsea como string y nunca «vence»: es el agujero."""
        archivo = self._escribir(
            '[[pip_audit]]\nid = "PYSEC-0000-1"\nmotivo = "x"\nvence_el = "2026-01-01"\nticket = "RED-63"\n'
        )

        errores = check_excepciones.revisar(check_excepciones.cargar(archivo), datetime.date(2026, 10, 4))

        self.assertEqual(len(errores), 1)
        self.assertIn("fecha", errores[0])

    def test_los_ignores_de_pip_audit_salen_del_archivo_y_no_del_yaml(self):
        flujo = (WORKFLOWS / "pr-security.yml").read_text(encoding="utf-8")

        self.assertNotIn("--ignore-vuln PYSEC", flujo, "el ignore a mano vuelve a no tener vencimiento")
        self.assertIn("scripts/check_excepciones_seguridad.py", flujo)

    def test_pip_audit_sigue_bloqueando(self):
        flujo = _cargar("pr-security.yml")
        job = _nombres_de_jobs(flujo)["Pip Audit"]

        self.assertNotIn("continue-on-error", flujo["jobs"][job])

    def test_las_banderas_que_genera_el_verificador_son_las_del_archivo(self):
        ids = [e["id"] for e in check_excepciones.cargar(EXCEPCIONES)]

        banderas = check_excepciones.banderas(check_excepciones.cargar(EXCEPCIONES))

        self.assertEqual(banderas, [arg for i in ids for arg in ("--ignore-vuln", i)])


class ActionsPineadasTests(SimpleTestCase):
    """RED-85: un tag es mutable; en un workflow con `contents: write` es el artefacto de PRD."""

    CON_ESCRITURA = ("publish-main.yml", "docs-auto-deploy.yml")

    def _usos(self, nombre):
        return list(USES.finditer((WORKFLOWS / nombre).read_text(encoding="utf-8")))

    def test_los_workflows_con_contents_write_siguen_siendo_los_dos_conocidos(self):
        """Si aparece un tercero, este test avisa antes de que nadie lo pinee."""
        con_escritura = [
            ruta.name
            for ruta in sorted(WORKFLOWS.glob("*.yml"))
            if (_cargar(ruta.name).get("permissions") or {}).get("contents") == "write"
        ]

        self.assertEqual(con_escritura, sorted(self.CON_ESCRITURA))

    def test_las_actions_de_esos_workflows_estan_pineadas_por_sha(self):
        for nombre in self.CON_ESCRITURA:
            for uso in self._usos(nombre):
                with self.subTest(workflow=nombre, accion=uso.group("accion")):
                    self.assertRegex(uso.group("ref"), SHA, "pineala por SHA de commit, no por tag")

    def test_cada_pin_lleva_su_version_en_un_comentario(self):
        """Sin el tag al lado, el SHA es ilegible y nadie lo actualiza nunca."""
        for nombre in self.CON_ESCRITURA:
            for uso in self._usos(nombre):
                with self.subTest(workflow=nombre, accion=uso.group("accion")):
                    self.assertRegex((uso.group("comentario") or ""), r"^v\d")

    def test_paths_filter_esta_pineada_por_sha_en_todos_los_workflows(self):
        """Es la action que RED-20 mete adentro de los jobs obligatorios: la entrada más golosa."""
        usos = [
            uso
            for ruta in sorted(WORKFLOWS.glob("*.yml"))
            for uso in self._usos(ruta.name)
            if uso.group("accion") == "dorny/paths-filter"
        ]

        self.assertTrue(usos, "RED-20 mueve los filtros `paths` adentro del job con dorny/paths-filter")
        for uso in usos:
            self.assertRegex(uso.group("ref"), SHA)


class HerramientasDelCiPineadasTests(SimpleTestCase):
    """RED-85 (Ola 7): ninguna herramienta del CI se instala «la última que haya».

    Los workflows hacían `pip install ruff`, `pip install coverage`,
    `pip install pip-audit` y `pip install mkdocs-material`. Un release de cualquiera
    vuelve rojo un PR que no cambió una línea, y el autor no tiene cómo saber que el rojo
    no es suyo. `Pip Audit` es el peor caso: es obligatorio desde el Cambio 121 y su base
    de advisories cambia sola, así que un release suyo frena **todos** los merges
    abiertos a la vez.
    """

    def _runs(self, nombre):
        flujo = _cargar(nombre)
        for job in (flujo.get("jobs") or {}).values():
            yield job, "\n".join(paso.get("run", "") for paso in (job.get("steps") or []))

    def test_ningun_workflow_instala_una_herramienta_sin_version(self):
        sueltos = []
        for ruta in sorted(WORKFLOWS.glob("*.yml")):
            for _job, comandos in self._runs(ruta.name):
                for coincidencia in PIP_INSTALL.finditer(comandos):
                    argumentos = coincidencia.group("argumentos").strip()
                    if argumentos.startswith("-r ") or argumentos == "--upgrade pip":
                        continue
                    sueltos.append(f"{ruta.name}: pip install {argumentos}")

        self.assertEqual(
            sueltos,
            [],
            "la versión tiene que salir de un archivo de requirements, no del índice de PyPI: " + str(sueltos),
        )

    def test_requirements_ci_pinea_todas_sus_lineas(self):
        """Un `>=` o un nombre pelado acá es exactamente el problema que la ficha cierra."""
        for linea in _lineas_de_requisitos(REQUIREMENTS_CI):
            with self.subTest(linea=linea):
                self.assertIn("==", linea)

    def test_estan_las_herramientas_que_el_ci_usa(self):
        distribuciones = {_distribucion(linea) for linea in _lineas_de_requisitos(REQUIREMENTS_CI)}

        self.assertEqual(distribuciones, set(HERRAMIENTAS_DEL_CI))

    def test_el_job_que_usa_una_herramienta_instala_el_archivo(self):
        """Pinear en un archivo que ningún job instala no sirve de nada."""
        for ruta in sorted(WORKFLOWS.glob("*.yml")):
            for nombre_job, comandos in self._runs(ruta.name):
                if not INVOCACION.search(comandos):
                    continue
                with self.subTest(workflow=ruta.name, job=nombre_job.get("name", "?")):
                    self.assertIn("pip install -r requirements-ci.txt", comandos)

    def test_requirements_ci_no_trae_nada_de_la_aplicacion(self):
        """La separación es el punto de la ficha: lo que importa el producto va en
        `requirements.txt` y lo instala la imagen; esto no viaja a ningún ambiente."""
        de_la_imagen = {_distribucion(linea) for linea in _lineas_de_requisitos(RAIZ / "requirements.txt")}
        del_ci = {_distribucion(linea) for linea in _lineas_de_requisitos(REQUIREMENTS_CI)}

        self.assertEqual(de_la_imagen & del_ci, set())
        self.assertNotIn("-r requirements.txt", REQUIREMENTS_CI.read_text(encoding="utf-8"))


class DependabotTests(SimpleTestCase):
    """RED-85, la otra mitad: con todo pineado, lo que envejece es el pin.

    Sin dependabot, «fijar la versión» es cambiar un riesgo por otro: la advisory nueva
    deja de frenar un PR ajeno y pasa a no aparecer nunca.
    """

    ECOSISTEMAS = {"pip", "github-actions", "npm"}

    def setUp(self):
        self.configuracion = yaml.safe_load(DEPENDABOT.read_text(encoding="utf-8"))

    def test_cubre_los_tres_ecosistemas_del_repo(self):
        """`pip` (los tres requirements), las actions de los workflows y el `tailwindcss`
        de `package.json`, cuyo CSS compilado está commiteado."""
        declarados = {bloque["package-ecosystem"] for bloque in self.configuracion["updates"]}

        self.assertEqual(declarados, self.ECOSISTEMAS)

    def test_todos_apuntan_a_development(self):
        """`main` es una release generada por `publish-main.yml` y no se toca a mano
        (`docs/internal/branching.md`): un PR de dependabot contra `main` no tendría
        dónde mergear."""
        for bloque in self.configuracion["updates"]:
            with self.subTest(ecosistema=bloque["package-ecosystem"]):
                self.assertEqual(bloque.get("target-branch"), "development")

    def test_todos_corren_semanalmente(self):
        for bloque in self.configuracion["updates"]:
            with self.subTest(ecosistema=bloque["package-ecosystem"]):
                self.assertEqual((bloque.get("schedule") or {}).get("interval"), "weekly")

    def test_pip_mira_la_raiz_que_es_donde_viven_los_tres_archivos(self):
        """`requirements.txt`, `requirements-dev.txt` y `requirements-ci.txt` están en la
        raíz: con `directory: "/"` dependabot los toma a los tres."""
        bloque = next(b for b in self.configuracion["updates"] if b["package-ecosystem"] == "pip")

        self.assertEqual(bloque["directory"], "/")
        for archivo in ("requirements.txt", "requirements-dev.txt", "requirements-ci.txt"):
            with self.subTest(archivo=archivo):
                self.assertTrue((RAIZ / archivo).exists())


class ContratosDelRepoTests(SimpleTestCase):
    """RED-24: las condiciones de cierre de `CLAUDE.md` dejan de correr solo en una máquina.

    `compile_templates`, `requerimientos.py --check` y `design_audit` vivían en el hook de
    Claude Code y en la cabeza de quien desarrolla: un cambio hecho desde un IDE o desde la
    web de GitHub no pasaba por ninguno. `collectstatic` no corría nunca en el CI, y es el
    que produce el 500 más caro del sistema («Missing staticfiles manifest entry»).
    """

    JOB = "Contratos del repo"

    def setUp(self):
        self.flujo = _cargar("pr-quality.yml")
        clave = _nombres_de_jobs(self.flujo).get(self.JOB)
        self.assertIsNotNone(clave, f"no existe el job «{self.JOB}»")
        self.job = self.flujo["jobs"][clave]
        self.comandos = "\n".join(paso.get("run", "") for paso in self.job["steps"])

    def test_el_job_bloquea(self):
        self.assertNotIn("continue-on-error", self.job)

    def test_corre_las_cuatro_condiciones_de_cierre(self):
        for comando in (
            "scripts/compile_templates.py --bloques",
            "scripts/requerimientos.py --check",
            "manage.py collectstatic",
            "scripts/design_audit.py",
        ):
            with self.subTest(comando=comando):
                self.assertIn(comando, self.comandos)

    def test_el_collectstatic_usa_el_almacenamiento_con_manifest(self):
        """Con `ENVIRONMENT` en dev el storage no genera manifest y el paso no prueba nada.

        El 500 de producción sale justo de ahí: `{% static 'custom/js/nuevo.js' %}` sin el
        archivo commiteado pasa `check`, `compile_templates` y la suite entera, y revienta
        en el primer render de PRD.
        """
        paso = next(p for p in self.job["steps"] if "collectstatic" in p.get("run", ""))

        self.assertEqual(paso["env"]["ENVIRONMENT"], "prd")
        self.assertEqual(paso["env"]["DJANGO_DEBUG"], "False")
        self.assertIn("staticfiles.json", paso["run"], "hay que fallar si no quedó el manifest")

    def test_el_ratchet_de_design_audit_no_aborta_el_paso_antes_de_comparar(self):
        """`design_audit.py` sale con 1 cuando hay errores y Actions corre con `-e`.

        Sin el `|| true` el paso muere antes de leer el número y el ratchet nunca compara:
        el gate quedaría rojo siempre, o sea mudo.
        """
        paso = next(p for p in self.job["steps"] if "design_audit.py" in p.get("run", ""))

        self.assertIn("|| true", paso["run"])

    def test_el_ratchet_tiene_techo_versionado(self):
        self.assertTrue(RATCHET.exists(), "falta .design-audit-ratchet")
        self.assertRegex(RATCHET.read_text(encoding="utf-8").strip(), r"^\d+$")

    def test_el_job_compara_contra_el_archivo_de_ratchet(self):
        self.assertIn(".design-audit-ratchet", self.comandos)

    @unittest.skipUnless(AUDITORIA.exists(), "hace falta scripts/design_audit.py")
    def test_la_medicion_de_hoy_no_supera_el_techo(self):
        """El mismo número que mide el CI, medido acá: el ratchet solo puede bajar.

        Corre el script entero (menos de un segundo) y lee la línea de resumen, que es el
        contrato entre el script y el job. Si la Ola 6 cambia ese formato, lo que se pone
        rojo es este test y no el gate del release.
        """
        corrida = subprocess.run(
            [sys.executable, str(AUDITORIA)],
            cwd=RAIZ,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        medidos = re.search(r"design_audit: (\d+) error", corrida.stdout)

        self.assertIsNotNone(medidos, f"la línea de resumen cambió de formato: {corrida.stdout[-300:]}")
        self.assertLessEqual(
            int(medidos.group(1)),
            int(RATCHET.read_text(encoding="utf-8").strip()),
            "subieron los errores del sistema de diseño: arreglalos o justificá el techo nuevo",
        )


class ContratoDeMigracionesTests(SimpleTestCase):
    """RED-14/RED-19/RED-57: el contrato de migraciones corre en el CI y es obligatorio.

    No se agregó un check nuevo a propósito: el paso vive adentro de `Migration Check`,
    que ya está en `CHECKS_OBLIGATORIOS`. Un `context` nuevo hay que sumarlo a mano al
    ruleset del repo —que todavía no está aplicado (RED-20, pendiente del dueño)—, así
    que hasta entonces un job nuevo sería un check que nadie exige. El paso es
    determinista y tarda menos de un segundo: no hay motivo para separarlo.
    """

    JOB = "Migration Check"

    def setUp(self):
        self.flujo = _cargar("pr-backend.yml")
        clave = _nombres_de_jobs(self.flujo).get(self.JOB)
        self.assertIsNotNone(clave, f"no existe el job «{self.JOB}»")
        self.job = self.flujo["jobs"][clave]

    def test_el_job_corre_el_contrato_de_migraciones(self):
        comandos = "\n".join(paso.get("run", "") for paso in self.job["steps"])

        self.assertIn("scripts/check_migraciones.py", comandos)

    def test_el_paso_va_en_un_job_que_el_ruleset_exige(self):
        self.assertIn(self.JOB, CHECKS_OBLIGATORIOS)

    def test_el_checkout_trae_el_historial_entero(self):
        """Sin `fetch-depth: 0` no hay base contra la cual comparar y el gate no ve nada."""
        checkout = next(paso for paso in self.job["steps"] if str(paso.get("uses", "")).startswith("actions/checkout"))

        self.assertEqual((checkout.get("with") or {}).get("fetch-depth"), 0)

    def test_el_gate_compara_contra_la_base_del_pr(self):
        paso = next(p for p in self.job["steps"] if "check_migraciones.py" in p.get("run", ""))

        self.assertIn("pull_request.base.sha", (paso.get("env") or {}).get("BASE", ""))
        self.assertIn("--base", paso["run"])

    def test_el_script_existe_y_es_ejecutable_sin_django(self):
        """Es un gate de CI: si importara Django, se caería con cualquier settings raro."""
        script = (RAIZ / "scripts" / "check_migraciones.py").read_text(encoding="utf-8")

        self.assertNotIn("import django", script)
        self.assertNotIn("manage.py", script)


class CoberturaTests(SimpleTestCase):
    """TST-03: el gate de cobertura existe, mide ramas y tiene los umbrales medidos.

    El gate son **tres números y una lista**, y viven en archivos distintos
    (`pyproject.toml` y `pr-backend.yml`). Sin este test, bajarlos es gratis: volver
    `fail_under` a 48, apagar `branch`, o borrar el paso del piso por módulo deja la
    suite entera en verde y nadie se entera hasta que alguien mire el diff. Que es
    exactamente el agujero que TST-03 venía a cerrar —el `fail_under = 48` estaba 33
    puntos por debajo de lo real y por eso no podía fallar nunca—.

    Mismo molde que `ContratoDeMigracionesTests`: el paso vive adentro de
    `Tests & Coverage`, que ya está en `CHECKS_OBLIGATORIOS`, así que no hace falta
    sumar un `context` nuevo al ruleset —que todavía no está aplicado—.

    Lo medido el 07-10-2026 con la suite completa, Python 3.12 + Django 5.2.17: 81 %
    con ramas sobre 23.315 sentencias y 6.192 ramas; los nueve módulos críticos, 94 %.
    Los umbrales quedan dos y cuatro puntos abajo. Son **ratchets**: cuando la
    medición suba, suben con ella y este test se actualiza en el mismo diff.
    """

    JOB = "Tests & Coverage"
    PASO = "Coverage por módulo crítico"

    #: Los nueve flujos por donde pasan el alta en SIIS, el cupo, el padrón y el link
    #: público. Escritos a mano, no derivados del workflow: si alguien saca uno del
    #: `--include`, la lista tiene que cambiar acá y eso se ve en el diff.
    MODULOS_CRITICOS = (
        "programas/services/siis_envio.py",
        "programas/services/proceso_masivo.py",
        "programas/services/cupo.py",
        "programas/services/inscripcion_publica.py",
        "programas/services/padron.py",
        "programas/services/respuestas.py",
        "programas/api/views.py",
        "portal/views/inscripcion.py",
        "core/rbac.py",
    )
    PISO_POR_MODULO = 90
    FAIL_UNDER = 79

    def setUp(self):
        self.flujo = _cargar("pr-backend.yml")
        clave = _nombres_de_jobs(self.flujo).get(self.JOB)
        self.assertIsNotNone(clave, f"no existe el job «{self.JOB}»")
        self.job = self.flujo["jobs"][clave]
        self.pyproject = (RAIZ / "pyproject.toml").read_text(encoding="utf-8")

    def _paso_del_piso(self):
        pasos = [p for p in self.job["steps"] if p.get("name") == self.PASO]
        self.assertEqual(
            len(pasos),
            1,
            f"el paso «{self.PASO}» tiene que existir una sola vez en «{self.JOB}»: es el "
            "único gate que mira módulo por módulo, y el número global promedia 23.315 "
            "sentencias, así que una caída fuerte en un módulo caliente se diluye y no lo mueve",
        )
        return pasos[0]

    def test_el_job_mide_cobertura(self):
        comandos = "\n".join(paso.get("run", "") for paso in self.job["steps"])

        self.assertIn("coverage run", comandos)
        self.assertIn("coverage report", comandos)

    def test_el_paso_va_en_un_job_que_el_ruleset_exige(self):
        self.assertIn(self.JOB, CHECKS_OBLIGATORIOS)

    def test_existe_el_paso_del_piso_por_modulo_critico(self):
        self.assertIn("coverage report", self._paso_del_piso()["run"])

    def test_el_piso_por_modulo_sigue_en_noventa(self):
        self.assertIn(f"--fail-under={self.PISO_POR_MODULO}", self._paso_del_piso()["run"])

    def test_el_paso_nombra_exactamente_los_nueve_modulos_criticos(self):
        run = self._paso_del_piso()["run"]
        incluidos = run.split("--include=", 1)[1].split()[0].strip()

        self.assertEqual(sorted(incluidos.split(",")), sorted(self.MODULOS_CRITICOS))

    def test_los_nueve_modulos_criticos_existen(self):
        """Un módulo renombrado desaparece del `--include` **en silencio**: `coverage`
        no se queja de una ruta que no existe, simplemente mide menos. Con ocho de los
        nueve el TOTAL sigue por encima de 90 y el gate queda verde midiendo de menos.
        """
        faltantes = [ruta for ruta in self.MODULOS_CRITICOS if not (RAIZ / ruta).is_file()]

        self.assertEqual(
            faltantes,
            [],
            "estos módulos del `--include` ya no existen: el gate los mide como 0 líneas y "
            f"baja de hecho el alcance sin ponerse rojo. Actualizá el paso y esta lista: {faltantes}",
        )

    def test_el_coverage_mide_ramas(self):
        """Sin `branch`, un `if` cuyo cuerpo se ejecuta siempre por la misma rama cuenta
        como 100 % cubierto."""
        self.assertIn("branch = true", self.pyproject)

    def test_el_fail_under_global_sigue_en_el_techo_medido(self):
        self.assertIn(f"fail_under = {self.FAIL_UNDER}", self.pyproject)

    def test_el_omit_deja_afuera_lo_que_no_es_producto(self):
        """El 48 % se medía sobre **todo** el repo, herramientas incluidas."""
        for ruta in ("core/performance/*", "scripts/*", "awslabs-mcp/*", "docker/*"):
            with self.subTest(ruta=ruta):
                self.assertIn(f'"{ruta}"', self.pyproject)


class SuiteEnParaleloTests(SimpleTestCase):
    """RED-86: la suite corre en paralelo, se sigue midiendo, y el tiempo queda escrito.

    El job tenía `timeout-minutes: 15` sobre una corrida en serie. Los
    `TransactionTestCase` de la Ola 1 la empujan hacia el techo, y **un timeout se ve
    como «failure» genérico**: la reacción es «re-run» y el número crece sin que nadie
    lo vea. Subir el techo solo corre el problema de lugar; lo que lo cierra es medir.

    Las dos mitades que este test sostiene son las que se caen sin ruido:

    * sacar `--parallel` deja la suite el triple de lenta y nada se pone rojo;
    * sacar `concurrency`/`parallel` de `[tool.coverage.run]`, o el `coverage combine`,
      deja a coverage midiendo **solo el proceso padre** —que no corre ningún test— y el
      `fail_under` se desploma sin que haya cambiado una línea de código.
    """

    JOB = "Tests & Coverage"
    TIMEOUT_MINUTOS = 25
    #: El aviso de la ficha: 12 minutos, en segundos.
    AVISO_SEGUNDOS = 720

    def setUp(self):
        self.flujo = _cargar("pr-backend.yml")
        clave = _nombres_de_jobs(self.flujo).get(self.JOB)
        self.assertIsNotNone(clave, f"no existe el job «{self.JOB}»")
        self.job = self.flujo["jobs"][clave]
        self.comandos = "\n".join(paso.get("run", "") for paso in self.job["steps"])
        self.pyproject = (RAIZ / "pyproject.toml").read_text(encoding="utf-8")

    def test_la_suite_corre_en_paralelo(self):
        self.assertRegex(self.comandos, r"manage\.py test .*--parallel \d+")

    def test_el_techo_del_job_subio_a_veinticinco(self):
        self.assertEqual(self.job.get("timeout-minutes"), self.TIMEOUT_MINUTOS)

    def test_coverage_sigue_midiendo_los_procesos_hijos(self):
        """Sin esto el número cae por el paralelismo, no por el código."""
        self.assertIn('concurrency = ["multiprocessing"]', self.pyproject)
        self.assertIn("parallel = true", self.pyproject)

    def test_la_configuracion_de_coverage_esta_en_el_archivo_y_no_en_el_comando(self):
        """Los subprocesos no ven los flags del `coverage run` del padre: solo el archivo."""
        self.assertNotIn("--concurrency", self.comandos)

    def test_el_job_combina_antes_de_reportar(self):
        orden = [paso.get("run", "") for paso in self.job["steps"]]
        combine = next(i for i, run in enumerate(orden) if "coverage combine" in run)
        reporte = next(i for i, run in enumerate(orden) if "coverage report" in run)

        self.assertLess(combine, reporte, "`coverage report` sin `combine` no encuentra datos")

    def test_el_job_escribe_la_duracion_y_avisa_sobre_doce_minutos(self):
        paso = next(p for p in self.job["steps"] if "GITHUB_STEP_SUMMARY" in p.get("run", ""))

        self.assertEqual(str(paso["env"]["AVISO_SEGUNDOS"]), str(self.AVISO_SEGUNDOS))
        self.assertIn("::warning::", paso["run"])

    def test_la_duracion_se_mide_aunque_la_suite_falle(self):
        """El caso que importa es justo el timeout, donde no hay resultado pero sí número."""
        paso = next(p for p in self.job["steps"] if "GITHUB_STEP_SUMMARY" in p.get("run", ""))

        self.assertIn("always()", str(paso.get("if", "")))

    def test_el_job_sigue_bloqueando(self):
        self.assertIn(self.JOB, CHECKS_OBLIGATORIOS)
        self.assertNotEqual(self.job.get("continue-on-error"), True)
        for paso in self.job["steps"]:
            if "manage.py test" in paso.get("run", ""):
                self.assertNotEqual(paso.get("continue-on-error"), True)


class TipadoGradualTests(SimpleTestCase):
    """RED-76: mypy existe, tiene un alcance acotado y ese alcance está en verde.

    2,7 % de retornos anotados sobre 2.195 funciones (`programas`: 5 de 1.117). Un
    checker sobre todo el árbol daría miles de hallazgos y nadie lo miraría, así que lo
    que se adopta es el **alcance**: `files` de `[tool.mypy]`. Lo que este test impide es
    que el alcance crezca a un directorio entero (con lo que el job pasaría a ser ruido) o
    que alguien lo haga pasar con `# type: ignore` sueltos, que es la otra forma de dejar
    el gate en verde sin arreglar nada.
    """

    JOB = "Tipos (mypy)"

    def setUp(self):
        self.flujo = _cargar("pr-quality.yml")
        clave = _nombres_de_jobs(self.flujo).get(self.JOB)
        self.assertIsNotNone(clave, f"no existe el job «{self.JOB}»")
        self.job = self.flujo["jobs"][clave]
        self.configuracion = _pyproject()

    def _alcance(self):
        return self.configuracion["tool"]["mypy"]["files"]

    def test_el_alcance_esta_declarado_y_son_archivos_que_existen(self):
        alcance = self._alcance()

        self.assertTrue(alcance, "sin `files`, mypy mira todo el árbol y el job es ruido")
        for ruta in alcance:
            with self.subTest(ruta=ruta):
                self.assertTrue(ruta.endswith(".py"), "el alcance se amplía un módulo por vez, no por directorio")
                self.assertTrue((RAIZ / ruta).is_file(), f"{ruta} no existe: mypy no avisa, simplemente mide menos")

    def test_lo_estricto_cubre_exactamente_el_alcance(self):
        """Un módulo en `files` sin su `override` entra sin que se le exija anotar nada."""
        estrictos = set()
        for override in self.configuracion["tool"]["mypy"].get("overrides", []):
            if override.get("disallow_untyped_defs"):
                estrictos |= set(override["module"])

        self.assertEqual(estrictos, {ruta[: -len(".py")].replace("/", ".") for ruta in self._alcance()})

    def test_el_plugin_de_django_sabe_de_donde_salen_los_settings(self):
        self.assertIn("mypy_django_plugin.main", self.configuracion["tool"]["mypy"]["plugins"])
        self.assertEqual(self.configuracion["tool"]["django-stubs"]["django_settings_module"], "config.settings")

    def test_un_type_ignore_sin_codigo_no_compila(self):
        self.assertIn("ignore-without-code", self.configuracion["tool"]["mypy"]["enable_error_code"])

    def test_el_alcance_no_tiene_type_ignore(self):
        """Hacerlo pasar a fuerza de `# type: ignore` deja el gate verde sin arreglar nada."""
        con_ignore = [ruta for ruta in self._alcance() if "type: ignore" in (RAIZ / ruta).read_text(encoding="utf-8")]

        self.assertEqual(con_ignore, [], f"el alcance de mypy se silencia en: {con_ignore}")

    def test_el_job_arranca_sin_bloquear(self):
        """Como pide la ficha, hasta que estén los cinco módulos. El `continue-on-error`
        va en el paso: a nivel job, GitHub reporta *success* y la evidencia queda
        enterrada en el log."""
        self.assertNotIn(self.JOB, CHECKS_OBLIGATORIOS)
        self.assertNotEqual(self.job.get("continue-on-error"), True)
        paso = next(p for p in self.job["steps"] if "mypy" in p.get("run", ""))
        self.assertTrue(paso.get("continue-on-error"))

    def test_el_job_instala_la_aplicacion_porque_el_plugin_importa_los_settings(self):
        comandos = "\n".join(paso.get("run", "") for paso in self.job["steps"])

        self.assertIn("pip install -r requirements.txt", comandos)
        self.assertIn("pip install -r requirements-ci.txt", comandos)


class ReleaseGateTests(SimpleTestCase):
    """RED-23: alguien verifica el release antes de que exista el espejo.

    El build de ECOM tarda 5-7 minutos y `main` despliega **producción automáticamente**:
    cuando `/pushGitLabecom` llegaba al paso de `main`, testing ni había terminado de
    construir. «`test` primero, se verifica ahí, recién después `main`» era prosa que el
    procedimiento no implementaba.
    """

    def setUp(self):
        self.flujo = _cargar("release-gate.yml")
        self.texto = (WORKFLOWS / "release-gate.yml").read_text(encoding="utf-8")

    def test_se_dispara_a_mano_con_el_sha_del_release(self):
        disparadores = self.flujo.get("on", self.flujo.get(True, {}))

        self.assertIn("workflow_dispatch", disparadores)
        self.assertIn("sha", disparadores["workflow_dispatch"]["inputs"])
        self.assertTrue(disparadores["workflow_dispatch"]["inputs"]["sha"]["required"])

    def test_la_corrida_lleva_el_sha_en_el_titulo(self):
        """`gh run list` no muestra los `inputs`: sin esto, dos corridas son indistinguibles.

        Y de eso depende el paso a producción, que exige el gate verde **de ese SHA**.
        """
        self.assertIn("sha", self.flujo.get("run-name", ""))

    def test_el_gate_del_release_tambien_exige_los_contextos_obligatorios(self):
        """Mismo agujero que en `publish-main`: cero check-runs no puede ser verde."""
        self.assertIn("ruleset-development.json", self.texto)
        self.assertIn("no tiene ni un check-run", self.texto)

    def test_el_ruleset_sale_del_head_del_pr_y_no_del_commit_de_release(self):
        """Mismo contrato de transición que `publish-main`, y por el mismo motivo.

        Acá hay además un segundo motivo: el árbol donde el job está parado es el de
        `main`, donde `docs/` ni siquiera está (`export-ignore`). Antes se leía del commit
        de `development` que originó el release, que es **el merge**: su árbol ya tiene el
        ruleset nuevo, así que el PR que lo originó quedaba exigido con checks que no
        existían cuando corrió.
        """
        self.assertIn('git show "$head:docs/internal/rulesets/ruleset-development.json"', self.texto)
        self.assertNotIn('git show "$ORIGEN:docs', self.texto)

    def test_la_lista_vacia_de_obligatorios_tambien_frena_el_release_gate(self):
        self.assertRegex(self.texto, r'if \[ ! -s "\$RUNNER_TEMP/obligatorios\.txt" \]')
        self.assertIn("no declara ningún check obligatorio", self.texto)

    def test_no_corre_en_pull_request(self):
        """Un check que corre en PRs y filtra por rutas queda «expected» para siempre.

        Este no entra en la lista de obligatorios de RED-20 justamente porque es a pedido:
        verifica un commit de `main`, que no recibe PRs.
        """
        disparadores = self.flujo.get("on", self.flujo.get(True, {}))

        self.assertNotIn("pull_request", disparadores)
        for nombre in _nombres_de_jobs(self.flujo):
            with self.subTest(job=nombre):
                self.assertNotIn(nombre, CHECKS_OBLIGATORIOS)

    def test_verifica_el_ci_del_pr_de_origen_y_no_el_commit_de_release(self):
        """El commit de `main` lo escribe el bot: no tiene checks ni PR.

        Hay que derivarlo del mensaje `release: … (development@<sha>)`, buscar el PR de ese
        commit de `development` y mirar los checks de **su head** (mismo ajuste que RED-21).
        """
        self.assertIn("development@", self.texto)
        self.assertIn("/pulls", self.texto)
        self.assertRegex(self.texto, r"commits/\$head/check-runs")

    def test_corre_la_suite_completa(self):
        self.assertIn("manage.py test", self.texto)

    def test_prueba_las_migraciones_contra_el_motor_de_produccion(self):
        """PRD y testing de ECOM son MariaDB, no MySQL (README §0, Cambio 99)."""
        servicios = [
            servicio.get("image", "")
            for job in self.flujo["jobs"].values()
            for servicio in (job.get("services") or {}).values()
        ]

        self.assertTrue([i for i in servicios if i.startswith("mariadb:")], f"servicios: {servicios}")
        for comando in ("migrate --noinput", "migrate --check", "makemigrations --check --dry-run"):
            with self.subTest(comando=comando):
                self.assertIn(comando, self.texto)

    def test_construye_la_imagen_y_exige_el_manifest_de_estaticos(self):
        self.assertIn("docker build", self.texto)
        self.assertIn("staticfiles.json", self.texto)

    def test_el_smoke_pega_a_rutas_que_existen_de_verdad(self):
        """Un smoke contra una URL inventada da 404 y el gate lo leería como «no es 500».

        La ficha nombraba `/accounts/login/`, que en este proyecto no existe: el login vive
        en la raíz (`users:login`) y hay un alias en `/login/`. Se verifica contra el
        URLconf real, no contra la ficha.
        """
        rutas = [
            paso["env"]["SMOKE_RUTAS"]
            for job in self.flujo["jobs"].values()
            for paso in job["steps"]
            if "SMOKE_RUTAS" in (paso.get("env") or {})
        ]

        self.assertTrue(rutas, "el workflow tiene que declarar SMOKE_RUTAS")
        for ruta in " ".join(rutas).split():
            with self.subTest(ruta=ruta):
                self.assertIsNotNone(resolve(ruta), f"{ruta} no existe en el URLconf")


class EspejoEnDosPasosTests(SimpleTestCase):
    """RED-23 (3): el espejo a ECOM deja de ser una sola corrida con una sola confirmación."""

    def setUp(self):
        self.guia = (RAIZ / "docs" / "internal" / "espejo-ecom.md").read_text(encoding="utf-8")

    def test_el_procedimiento_esta_partido_en_test_y_prd(self):
        self.assertIn("/pushGitLabecomTEST", self.guia)
        self.assertIn("/pushGitLabecomPRD", self.guia)

    def test_el_paso_a_produccion_exige_lo_verificado_en_testing(self):
        for exigencia in ("release-gate", "^{tree}", "ls-remote ecom test"):
            with self.subTest(exigencia=exigencia):
                self.assertIn(exigencia, self.guia)

    def test_el_paso_a_produccion_pide_una_segunda_confirmacion_escrita(self):
        self.assertIn("PRODUCCION", self.guia)

    def test_la_guia_recuerda_que_main_despliega_produccion_sin_aprobacion(self):
        self.assertIn("producción", self.guia.lower())
        self.assertIn("ArgoCD", self.guia)


class PropuestaAEcomTests(SimpleTestCase):
    """RED-22: el pipeline de ECOM es de ellos; lo nuestro es la propuesta escrita."""

    def setUp(self):
        self.propuesta = (RAIZ / "docs" / "internal" / "propuesta-ecom-verify.md").read_text(encoding="utf-8")

    def test_la_propuesta_trae_la_etapa_verify_completa(self):
        for pieza in ("verify", "check --deploy", "makemigrations --check --dry-run", "manage.py test"):
            with self.subTest(pieza=pieza):
                self.assertIn(pieza, self.propuesta)

    def test_la_propuesta_incluye_el_tag_inmutable(self):
        """Sin tag por commit no hay artefacto al que volver: ECOM publica solo `:latest` (RED-16)."""
        self.assertIn("CI_COMMIT_SHORT_SHA", self.propuesta)

    def test_nuestra_copia_del_pipeline_sigue_intacta(self):
        """`.gitlab-ci.yml` viaja en el release y tiene que quedar byte a byte igual al suyo.

        Si lo editamos de nuestro lado, el próximo espejo les revierte el archivo: por eso
        la etapa `verify` vive en un documento de propuesta y no en el YAML.
        """
        pipeline = (RAIZ / ".gitlab-ci.yml").read_text(encoding="utf-8")

        self.assertNotIn("verify", pipeline)
        self.assertIn("stages:", pipeline)
