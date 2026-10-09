"""`docs/client/` no publica nada que no deba, y el gate que lo dice no es decorativo (RED-64).

`docs/client/` se construye con MkDocs y se publica en un sitio **público** en cada push
a `development` que toque esa carpeta. La mitad humana de la ficha —*required reviewers*
sobre el `environment` del job— la configura el dueño del repo; la mecánica es
`scripts/check_docs_client.py`, y vive acá además del workflow para que el hallazgo
aparezca en el PR y no recién cuando el dato ya está en internet.

El caso que motivó esto no es hipotético, y tampoco se cerró de una: al 09-oct-2026 el
repo publicaba una **misma** respuesta de RENAPER de una persona real —apellido, nombre,
documento, CUIL, fecha de nacimiento, domicilio e identificadores internos— en dos
lugares. La primera pasada tocó solo `docs/client/funcionalidades/programa-becas.md`, y
ahí dejó la fecha de nacimiento y los datos del ejemplar del DNI; el registro **entero**
seguía en `docs/internal/analisis/003-programa-becas-relevamiento-propuesta.md`, que no
publica MkDocs pero se lee igual porque el repositorio es público. La segunda pasada
reemplaza los dos por valores inventados, barre `docs/` entero y le agrega al gate las
reglas que no tenía: fecha de nacimiento rodeada de identidad, domicilio con calle y
número, y todas las extensiones que MkDocs copia al sitio, no solo `.md`.

Los valores de los casos rojos de acá son inventados. No se usa el dato real ni para
afirmar que ya no está: eso lo dice el gate sobre el árbol, en
`DocsClientPublicablesTests`.
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
WORKFLOW_PR = RAIZ / ".github" / "workflows" / "pr-datos.yml"

#: Inventados, y elegidos para que **no** caigan en los marcadores que el gate perdona.
DOCUMENTO_INVENTADO = "98765432"
CUIL_INVENTADO = "27987654321"
NACIMIENTO_INVENTADO = "1983-07-14"


def _cargar_gate():
    """El script es stdlib + PyYAML y no importa Django: se carga por ruta."""
    especificacion = importlib.util.spec_from_file_location("check_docs_client", GATE)
    modulo = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(modulo)
    return modulo


def _flujo(ruta: Path = WORKFLOW):
    return yaml.safe_load(ruta.read_text(encoding="utf-8"))


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

    def test_la_respuesta_de_renaper_de_ejemplo_es_la_estructura_y_no_una_persona(self):
        """Los dos lugares donde estaba el mismo registro, fijados por lo que tienen que decir.

        Se afirma el contenido **inventado**, no la ausencia del real: escribir el valor
        que se despublicó dentro de un test es volver a publicarlo.
        """
        for relativa in (
            Path("docs/client/funcionalidades/programa-becas.md"),
            Path("docs/internal/analisis/003-programa-becas-relevamiento-propuesta.md"),
        ):
            with self.subTest(archivo=relativa.as_posix()):
                texto = (RAIZ / relativa).read_text(encoding="utf-8")
                self.assertIn('"fechaNacimiento": "2000-01-01"', texto)
                self.assertIn('"calle": "CALLE FALSA"', texto)
                self.assertIn('"numero": "123"', texto)
                self.assertIn("valores ficticios", texto, "el bloque tiene que decir que no es de nadie")
                self.assertEqual(_cargar_gate()._revisar_contenido(relativa.as_posix(), texto), [])


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

    # --- 1 · persona identificable -------------------------------------------------

    def test_un_dni_junto_a_la_palabra_que_lo_nombra_frena_la_publicacion(self):
        raiz = self._arbol({"index.md": f"El ciudadano con DNI {DOCUMENTO_INVENTADO} pidió la beca.\n"})
        self.assertEqual(self._reglas(raiz), ["persona"])

    def test_un_dni_con_puntos_tambien(self):
        raiz = self._arbol({"index.md": "Documento 98.765.432.\n"})
        self.assertEqual(self._reglas(raiz), ["persona"])

    def test_la_clave_numero_documento_no_se_escapa_por_el_borde_de_palabra(self):
        """`\\bdocumento\\b` no veía `numeroDocumento`, que es la clave de media API."""
        raiz = self._arbol({"index.md": f'    "numeroDocumento": "{DOCUMENTO_INVENTADO}",\n'})
        self.assertEqual(self._reglas(raiz), ["persona"])

    def test_un_cuil_no_necesita_ninguna_palabra_cerca(self):
        raiz = self._arbol({"index.md": f'    "identificador": "{CUIL_INVENTADO}",\n'})
        self.assertEqual(self._reglas(raiz), ["persona"])

    def test_un_numero_de_siete_digitos_sin_contexto_no_es_un_documento(self):
        raiz = self._arbol({"index.md": "El presupuesto del programa es de 1234567 pesos.\n"})
        self.assertEqual(self._reglas(raiz), [])

    def test_un_tamano_en_bytes_al_lado_de_la_palabra_dni_no_es_una_persona(self):
        """El propio informe de la auditoría se marcaba solo: «(2.874.634 bytes; … DNI, CUIL…)»."""
        raiz = self._arbol({"index.md": "`scripts/Volcado.sql` (2.874.634 bytes; columnas DNI, CUIL, apellido).\n"})
        self.assertEqual(self._reglas(raiz), [])

    def test_un_documento_dentro_de_un_uuid_no_es_una_persona(self):
        raiz = self._arbol({"index.md": "El documento `2895d5ce-f8cd-4ee0-a606-90719590f027` ya existía.\n"})
        self.assertEqual(self._reglas(raiz), [])

    def test_un_documento_de_relleno_no_frena_nada(self):
        """Es lo que deja al gate en 0 sin una lista de archivos perdonados."""
        raiz = self._arbol({"index.md": "DNI 12345678, DNI 00000000, documento 12.345.670.\n"})
        self.assertEqual(self._reglas(raiz), [])

    def test_un_cuil_de_relleno_tampoco(self):
        raiz = self._arbol({"index.md": '    "cuil": "20123456789",\n'})
        self.assertEqual(self._reglas(raiz), [])

    # --- 2 · fecha de nacimiento ---------------------------------------------------

    def test_una_fecha_de_nacimiento_entre_campos_de_identidad_frena_la_publicacion(self):
        raiz = self._arbol(
            {
                "index.md": f"""\
                ```json
                {{
                  "apellido": "PEREZ",
                  "fechaNacimiento": "{NACIMIENTO_INVENTADO}",
                  "calle": "ALGUNA"
                }}
                ```
                """
            }
        )
        self.assertEqual(self._reglas(raiz), ["persona"])

    def test_una_fecha_de_nacimiento_sin_identidad_alrededor_no_alcanza(self):
        raiz = self._arbol({"index.md": f'    "fechaNacimiento": "{NACIMIENTO_INVENTADO}",\n'})
        self.assertEqual(self._reglas(raiz), [])

    def test_la_prosa_que_habla_de_fechas_de_nacimiento_no_es_un_hallazgo(self):
        """Un gate que marca el párrafo que *describe* el bug se apaga el primer día."""
        raiz = self._arbol(
            {"index.md": "Una fecha de nacimiento ilegible (`15/03/2010`) seguía viaje al DNI del padrón.\n"}
        )
        self.assertEqual(self._reglas(raiz), [])

    def test_la_fecha_de_relleno_no_es_la_de_nadie(self):
        raiz = self._arbol({"index.md": '    "apellido": "PEREZ",\n    "fechaNacimiento": "2000-01-01",\n'})
        self.assertEqual(self._reglas(raiz), [])

    # --- 3 · domicilio -------------------------------------------------------------

    def test_una_calle_con_altura_frena_la_publicacion(self):
        raiz = self._arbol({"index.md": "Domicilio declarado: Calle Segunda 4321, Resistencia.\n"})
        self.assertEqual(self._reglas(raiz), ["persona"])

    def test_la_calle_y_la_altura_en_claves_separadas_tambien(self):
        """Es la forma en que lo devuelven RENAPER y Personas: dos claves, dos líneas."""
        raiz = self._arbol({"index.md": '    "calle": "SEGUNDA",\n    "piso": "3",\n    "numero": "4321",\n'})
        self.assertEqual(self._reglas(raiz), ["persona"])

    def test_calle_falsa_es_un_marcador_y_no_un_domicilio(self):
        raiz = self._arbol({"index.md": '    "calle": "CALLE FALSA",\n    "numero": "123",\n'})
        self.assertEqual(self._reglas(raiz), [])

    def test_una_ruta_con_un_numero_no_es_una_calle(self):
        """En este repo «ruta» es una URL: «ninguna ruta da 500» no es un domicilio."""
        raiz = self._arbol({"index.md": "Sin test de humo: nada afirma «ninguna ruta da 500».\n"})
        self.assertEqual(self._reglas(raiz), [])

    # --- 4 · secretos --------------------------------------------------------------

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

    def test_una_secretaria_del_organigrama_no_es_un_secreto(self):
        raiz = self._arbol({"index.md": "El único test que toca `configuracion/views/secretaria.py:108,218`.\n"})
        self.assertEqual(self._reglas(raiz), [])

    def test_un_archivo_de_tokens_no_es_un_secreto(self):
        raiz = self._arbol({"index.md": "`--brand:#5059bc` → `--color-brand-700` (`chaco-tokens.css:19`).\n"})
        self.assertEqual(self._reglas(raiz), [])

    def test_una_referencia_de_codigo_no_es_un_secreto(self):
        raiz = self._arbol({"index.md": '"    var token = json.data && json.data.token;",\n'})
        self.assertEqual(self._reglas(raiz), [])

    def test_la_clave_de_prueba_del_ci_no_es_un_secreto(self):
        raiz = self._arbol({"index.md": 'env: { DJANGO_SECRET_KEY: test-key, PYTEST_RUNNING: "1" }\n'})
        self.assertEqual(self._reglas(raiz), [])

    # --- 5 · nav y extensiones -----------------------------------------------------

    def test_un_md_que_no_esta_en_el_nav_frena_la_publicacion(self):
        raiz = self._arbol({"index.md": "Hola.\n", "suelto.md": "Algo que nadie linkeó.\n"})
        self.assertEqual(self._reglas(raiz), ["nav"])

    def test_declararlo_en_not_in_nav_lo_habilita(self):
        raiz = self._arbol(
            {"index.md": "Hola.\n", "plantillas/acta.md": "Plantilla.\n"},
            not_in_nav="/plantillas/\n",
        )
        self.assertEqual(self._reglas(raiz), [])

    def test_un_html_del_sitio_tambien_se_revisa(self):
        """MkDocs copia **todo** `docs_dir`: un mockup `.html` se publica igual que una página."""
        raiz = self._arbol({"index.md": "Hola.\n", "mockups/m.html": f"<span>DNI {DOCUMENTO_INVENTADO}</span>\n"})
        self.assertEqual(self._reglas(raiz), ["persona"])

    def test_al_html_no_se_le_pide_que_este_en_el_nav(self):
        """El nav de MkDocs solo lista `.md`: no hay dónde declarar un asset."""
        raiz = self._arbol({"index.md": "Hola.\n", "mockups/m.html": "<span>Sin datos de nadie.</span>\n"})
        self.assertEqual(self._reglas(raiz), [])

    def test_un_json_publicado_tambien_se_revisa(self):
        raiz = self._arbol({"index.md": "Hola.\n", "datos.json": f'{{"cuil": "{CUIL_INVENTADO}"}}\n'})
        self.assertEqual(self._reglas(raiz), ["persona"])

    # --- salida --------------------------------------------------------------------

    def test_el_gate_sale_con_codigo_uno_cuando_encuentra_algo(self):
        raiz = self._arbol({"index.md": f"DNI {DOCUMENTO_INVENTADO}\n"})
        limpia = self._arbol({"index.md": "Sin datos de nadie.\n"})
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self.gate.main(["--raiz", str(raiz)]), 1)
            self.assertEqual(self.gate.main(["--raiz", str(limpia)]), 0)

    def test_el_gate_no_imprime_el_valor_que_encontro(self):
        """El log de Actions de un repo público también es público."""
        raiz = self._arbol({"index.md": f"DNI {DOCUMENTO_INVENTADO}\n"})
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida):
            self.gate.main(["--raiz", str(raiz)])
        self.assertNotIn(DOCUMENTO_INVENTADO, salida.getvalue())


class AlcanceAmpliadoTests(SimpleTestCase):
    """`--todo-docs`: el repositorio es público, no solo el sitio que construye MkDocs."""

    def setUp(self):
        self.gate = _cargar_gate()

    def _arbol(self, archivos: dict[str, str]) -> Path:
        raiz = Path(self.enterContext(tempfile.TemporaryDirectory()))
        for nombre, contenido in archivos.items():
            destino = raiz / nombre
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text(textwrap.dedent(contenido), encoding="utf-8")
        (raiz / "mkdocs.yml").write_text(
            yaml.safe_dump({"docs_dir": "docs/client", "nav": [{"Inicio": "index.md"}]}),
            encoding="utf-8",
        )
        return raiz

    def test_lo_que_no_publica_mkdocs_igual_se_lee_en_github(self):
        raiz = self._arbol(
            {
                "docs/client/index.md": "Sin datos de nadie.\n",
                "docs/internal/notas.md": f'    "cuil": "{CUIL_INVENTADO}",\n',
            }
        )
        self.assertEqual(self.gate.revisar(raiz), [])
        self.assertEqual([h["archivo"] for h in self.gate.revisar_todo(raiz)], ["docs/internal/notas.md"])

    def test_los_md_de_la_raiz_entran_en_el_barrido(self):
        raiz = self._arbol({"docs/client/index.md": "Hola.\n", "AGENTS.md": f"DNI {DOCUMENTO_INVENTADO}\n"})
        self.assertEqual([h["archivo"] for h in self.gate.revisar_todo(raiz)], ["AGENTS.md"])

    def test_el_barrido_amplio_no_aplica_la_regla_del_nav(self):
        """Fuera del sitio no hay menú: pedir que un `.md` esté en el nav no significa nada."""
        raiz = self._arbol({"docs/client/index.md": "Hola.\n", "docs/internal/suelto.md": "Nada.\n"})
        self.assertEqual(self.gate.revisar_todo(raiz), [])

    def test_el_modo_todo_docs_se_puede_invocar_desde_la_linea_de_comandos(self):
        raiz = self._arbol({"docs/client/index.md": "Hola.\n", "docs/internal/x.md": f"DNI {DOCUMENTO_INVENTADO}\n"})
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida):
            self.assertEqual(self.gate.main(["--raiz", str(raiz), "--todo-docs"]), 1)
        self.assertIn("docs/internal/x.md", salida.getvalue())
        self.assertNotIn(DOCUMENTO_INVENTADO, salida.getvalue())


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


class BarridoDeTodoDocsEnElPrTests(SimpleTestCase):
    """El barrido amplio corre en el PR, y corre informando, no bloqueando."""

    def _paso(self):
        pasos = _flujo(WORKFLOW_PR)["jobs"]["sin-datos-personales"]["steps"]
        return next(p for p in pasos if "--todo-docs" in p.get("run", ""))

    def test_el_barrido_amplio_corre_en_el_job_de_datos(self):
        self.assertIn("check_docs_client.py", self._paso()["run"])

    def test_el_barrido_amplio_no_bloquea(self):
        """37 hallazgos sobre el repo saneado, los 37 deliberados: bloquear sería nacer en rojo."""
        self.assertIs(self._paso().get("continue-on-error"), True)

    def test_el_job_que_lo_hospeda_sigue_siendo_bloqueante(self):
        self.assertNotIn("continue-on-error", _flujo(WORKFLOW_PR)["jobs"]["sin-datos-personales"])
