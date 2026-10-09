"""`docs/client/` no publica nada que no deba, y el gate que lo dice no es decorativo (RED-64).

`docs/client/` se construye con MkDocs y se publica en un sitio **público** en cada push
a `development` que toque esa carpeta. La mitad humana de la ficha —*required reviewers*
sobre el `environment` del job— la configura el dueño del repo; la mecánica es
`scripts/check_docs_client.py`, y vive acá además del workflow para que el hallazgo
aparezca en el PR y no recién cuando el dato ya está en internet.

El caso que motivó esto no es hipotético: al 09-oct-2026
`docs/client/funcionalidades/programa-becas.md` publicaba una respuesta de RENAPER con el
apellido, el nombre, el DNI, el CUIL, la fecha de nacimiento y el domicilio de una persona
real, pegada «para mostrar al equipo Ministerio». El mismo PR que trae este test la
despublica.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import tempfile
import textwrap
from pathlib import Path

import yaml
from django.conf import settings
from django.test import SimpleTestCase

RAIZ = Path(settings.BASE_DIR)
GATE = RAIZ / "scripts" / "check_docs_client.py"
WORKFLOW = RAIZ / ".github" / "workflows" / "docs-auto-deploy.yml"


def _cargar_gate():
    """El script es stdlib + PyYAML y no importa Django: se carga por ruta."""
    especificacion = importlib.util.spec_from_file_location("check_docs_client", GATE)
    modulo = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(modulo)
    return modulo


def _flujo():
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _pasos():
    return _flujo()["jobs"]["deploy"]["steps"]


class DocsClientPublicablesTests(SimpleTestCase):
    """La medición sobre el repo de verdad. Este es el que tiene que quedarse en 0."""

    def test_docs_client_no_publica_nada_que_no_deba(self):
        hallazgos = _cargar_gate().revisar(RAIZ)
        self.assertEqual(
            hallazgos,
            [],
            "docs/client/ tiene algo que no puede salir publicado:\n"
            + "\n".join(f"  {h['archivo']}:{h['linea']} [{h['regla']}] {h['mensaje']}" for h in hallazgos),
        )

    def test_la_respuesta_de_renaper_de_ejemplo_no_trae_una_persona(self):
        """El hallazgo concreto que cerró la ficha, fijado por su contenido."""
        texto = (RAIZ / "docs" / "client" / "funcionalidades" / "programa-becas.md").read_text(encoding="utf-8")
        self.assertNotIn("40732138", texto)
        self.assertNotIn("20407321384", texto)
        self.assertIn('"cuil": "<cuil>"', texto)


class DeteccionDelGateTests(SimpleTestCase):
    """Que el gate encuentre algo, sobre un árbol sintético. Sin esto queda verde por ciego."""

    def setUp(self):
        self.gate = _cargar_gate()

    def _arbol(self, paginas: dict[str, str], nav: list | None = None, not_in_nav: str = "") -> Path:
        raiz = Path(self.enterContext(tempfile.TemporaryDirectory()))
        carpeta = raiz / "docs" / "client"
        for nombre, contenido in paginas.items():
            destino = carpeta / nombre
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text(textwrap.dedent(contenido), encoding="utf-8")
        config = {"docs_dir": "docs/client", "nav": nav if nav is not None else [{"Inicio": "index.md"}]}
        if not_in_nav:
            config["not_in_nav"] = not_in_nav
        (raiz / "mkdocs.yml").write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")
        return raiz

    def _reglas(self, raiz: Path) -> list[str]:
        return [h["regla"] for h in self.gate.revisar(raiz)]

    def test_un_dni_junto_a_la_palabra_que_lo_nombra_frena_la_publicacion(self):
        raiz = self._arbol({"index.md": "El ciudadano con DNI 40732138 pidió la beca.\n"})
        self.assertEqual(self._reglas(raiz), ["persona"])

    def test_un_dni_con_puntos_tambien(self):
        raiz = self._arbol({"index.md": "Documento 40.732.138.\n"})
        self.assertEqual(self._reglas(raiz), ["persona"])

    def test_un_cuil_no_necesita_ninguna_palabra_cerca(self):
        raiz = self._arbol({"index.md": '    "identificador": "20407321384",\n'})
        self.assertEqual(self._reglas(raiz), ["persona"])

    def test_un_numero_de_siete_digitos_sin_contexto_no_es_un_documento(self):
        raiz = self._arbol({"index.md": "El presupuesto del programa es de 1234567 pesos.\n"})
        self.assertEqual(self._reglas(raiz), [])

    def test_un_secreto_con_valor_de_verdad_frena_la_publicacion(self):
        raiz = self._arbol({"index.md": "SIIS_API_CLIENT_SECRET=aH7x29ZqLmTp4Rb\n"})
        self.assertEqual(self._reglas(raiz), ["secreto"])

    def test_la_plantilla_del_env_que_el_repo_publica_no_es_un_secreto(self):
        """Las doce líneas que el `\\S` de la ficha marcaba y son exactamente lo que hay que escribir."""
        raiz = self._arbol(
            {
                "index.md": textwrap.dedent(
                    """\
                    DATABASE_PASSWORD=…
                    MYSQL_ROOT_PASSWORD=<password-root-db>
                    SIIS_API_CLIENT_SECRET=<lo-provee-ECOM>
                    EMAIL_HOST_PASSWORD=<password>
                    -e DJANGO_SUPERUSER_PASSWORD=<contraseña> \\
                    - Validadores de contraseña: `MinimumLengthValidator(min_length=8)`
                    - **Recuperación de contraseña:** flujo autogestionado.
                    """
                )
            }
        )
        self.assertEqual(self._reglas(raiz), [])

    def test_un_md_que_no_esta_en_el_nav_frena_la_publicacion(self):
        raiz = self._arbol({"index.md": "Hola.\n", "suelto.md": "Algo que nadie linkeó.\n"})
        self.assertEqual(self._reglas(raiz), ["nav"])

    def test_declararlo_en_not_in_nav_lo_habilita(self):
        raiz = self._arbol(
            {"index.md": "Hola.\n", "plantillas/acta.md": "Plantilla.\n"},
            not_in_nav="/plantillas/\n",
        )
        self.assertEqual(self._reglas(raiz), [])

    def test_el_gate_sale_con_codigo_uno_cuando_encuentra_algo(self):
        raiz = self._arbol({"index.md": "DNI 40732138\n"})
        limpia = self._arbol({"index.md": "Sin datos de nadie.\n"})
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self.gate.main(["--raiz", str(raiz)]), 1)
            self.assertEqual(self.gate.main(["--raiz", str(limpia)]), 0)

    def test_el_gate_no_imprime_el_valor_que_encontro(self):
        """El log de Actions de un repo público también es público."""
        raiz = self._arbol({"index.md": "DNI 40732138\n"})
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida):
            self.gate.main(["--raiz", str(raiz)])
        self.assertNotIn("40732138", salida.getvalue())


class WorkflowDePublicacionTests(SimpleTestCase):
    """El gate y la aprobación están donde tienen que estar, en el único camino a internet."""

    def test_el_gate_corre_antes_de_construir_y_de_publicar(self):
        nombres = [paso.get("name", "") for paso in _pasos()]
        comandos = [paso.get("run", "") for paso in _pasos()]
        indice_gate = next(i for i, run in enumerate(comandos) if "check_docs_client.py" in run)
        indice_build = next(i for i, run in enumerate(comandos) if "mkdocs build" in run)
        indice_deploy = next(i for i, run in enumerate(comandos) if "gh-deploy" in run)
        self.assertLess(indice_gate, indice_build, f"el gate va antes de construir; pasos: {nombres}")
        self.assertLess(indice_gate, indice_deploy)

    def test_el_job_de_publicacion_pasa_por_un_environment(self):
        """Es el colgador de los *required reviewers*: sin `environment` no hay dónde pedirlos."""
        entorno = _flujo()["jobs"]["deploy"].get("environment")
        self.assertIsNotNone(entorno, "el job que publica tiene que declarar un environment (RED-64)")
        nombre = entorno["name"] if isinstance(entorno, dict) else entorno
        self.assertTrue(nombre)

    def test_el_environment_no_es_github_pages(self):
        """`github-pages` existe y solo admite la rama `gh-pages`: apuntarlo ahí rompe la publicación."""
        entorno = _flujo()["jobs"]["deploy"]["environment"]
        nombre = entorno["name"] if isinstance(entorno, dict) else entorno
        self.assertNotEqual(nombre, "github-pages")

    def test_el_gate_se_dispara_cuando_cambia_el_propio_gate(self):
        disparadores = _flujo().get("on", _flujo().get(True))
        rutas = disparadores["push"]["paths"]
        self.assertIn("scripts/check_docs_client.py", rutas)
        self.assertIn("docs/client/**", rutas)
        self.assertIn("mkdocs.yml", rutas)

    def test_el_gate_no_sigue_de_largo_si_falla(self):
        paso = next(p for p in _pasos() if "check_docs_client.py" in p.get("run", ""))
        self.assertNotEqual(paso.get("continue-on-error"), True)
        self.assertNotEqual(_flujo()["jobs"]["deploy"].get("continue-on-error"), True)
