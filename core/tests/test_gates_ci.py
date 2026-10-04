"""Los gates del CI son obligatorios de verdad (RED-20, RED-63, RED-85).

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

No toca la red: todo sale de los archivos del repo.
"""

import datetime
import importlib.util
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml
from django.conf import settings
from django.test import SimpleTestCase

RAIZ = Path(settings.BASE_DIR)
WORKFLOWS = RAIZ / ".github" / "workflows"
RULESETS = RAIZ / "docs" / "internal" / "rulesets"
EXCEPCIONES = RAIZ / "security" / "excepciones.toml"
VERIFICADOR = RAIZ / "scripts" / "check_excepciones_seguridad.py"

# `uses: owner/repo@referencia  # comentario`
USES = re.compile(r"^\s*-?\s*uses:\s*(?P<accion>[^@\s]+)@(?P<ref>\S+)\s*(?:#\s*(?P<comentario>.*))?$", re.MULTILINE)
SHA = re.compile(r"^[0-9a-f]{40}$")


def _cargar(nombre):
    return yaml.safe_load((WORKFLOWS / nombre).read_text(encoding="utf-8"))


def _disparador_pull_request(flujo):
    """`on` se parsea como `True` en YAML 1.1 (`on` es booleano): hay que buscar las dos."""
    disparadores = flujo.get("on", flujo.get(True, {})) or {}
    return disparadores.get("pull_request") or {}


def _nombres_de_jobs(flujo):
    return {datos.get("name", job): job for job, datos in (flujo.get("jobs") or {}).items()}


def _todos_los_workflows():
    return {ruta.name: _cargar(ruta.name) for ruta in sorted(WORKFLOWS.glob("*.yml"))}


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

    def test_el_job_de_estilo_sigue_sin_bloquear_hasta_limpiar_la_deuda(self):
        job = self._job("Ruff estilo")

        self.assertTrue(job.get("continue-on-error"))
        comandos = " ".join(paso.get("run", "") for paso in job["steps"])
        self.assertIn("E,W,I", comandos)

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
