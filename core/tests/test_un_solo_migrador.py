"""RED-19 · Un solo migrador y la regla expand/contract.

Django no toma candado para `migrate` en MySQL/MariaDB. Con la forma que
`docker/k8s/README.md` recomendaba —«sin `command`/`args` en el pod: el entrypoint hace
todo»— y `replicas > 1`, cada pod corre `migrate` en cada arranque: medido contra MariaDB
11.8, dos `migrate` en paralelo terminan con uno muerto (1050 desde base vacía, 1060
desde base al día) y, si se cruzan dentro de una migración de varias operaciones, el
esquema queda a medias **sin** fila en `django_migrations`.

Lo que fija este módulo es la mitad que vive en el repo: que las plantillas y la guía de
Kubernetes digan quién migra y quién no, y que la regla expand/contract esté escrita
donde la lee quien escribe una migración (`CLAUDE.md`) y quien la revisa.

El candado `GET_LOCK('datanach_migrate', 900)` del comando `bootstrap_lock` es OPS-07
(Ola 3) y no entra acá: esto es la regla, aquello es la red debajo de la regla.
"""

from pathlib import Path

import yaml
from django.conf import settings
from django.test import SimpleTestCase

RAIZ = Path(settings.BASE_DIR)
K8S = RAIZ / "docker" / "k8s"
ENTRYPOINT = RAIZ / "docker-entrypoint.sh"


class UnSoloMigradorTests(SimpleTestCase):
    def setUp(self):
        self.readme = (K8S / "README.md").read_text(encoding="utf-8")

    def test_el_entrypoint_deja_apagar_el_migrate(self):
        """`RUN_MIGRATIONS=false` es la palanca: si desaparece, la regla no se puede aplicar."""
        self.assertIn('"${RUN_MIGRATIONS:-true}" = "true"', ENTRYPOINT.read_text(encoding="utf-8"))

    def test_el_deployment_web_nunca_migra(self):
        fragmento = yaml.safe_load((K8S / "bootstrap-initcontainer.yaml").read_text(encoding="utf-8"))
        web = next(c for c in fragmento["spec"]["template"]["spec"]["containers"] if c["name"] == "web")

        self.assertIn({"name": "RUN_MIGRATIONS", "value": "false"}, web.get("env") or [])

    def test_existe_la_plantilla_del_job_que_migra_una_sola_vez(self):
        """Un initContainer corre en **cada** pod: con `replicas > 1` sigue habiendo N."""
        job = yaml.safe_load((K8S / "bootstrap-job.yaml").read_text(encoding="utf-8"))

        self.assertEqual(job["kind"], "Job")
        contenedor = job["spec"]["template"]["spec"]["containers"][0]
        self.assertEqual(contenedor["args"], ["bootstrap"])
        self.assertEqual(job["spec"]["template"]["spec"]["restartPolicy"], "Never")

    def test_la_guia_ya_no_recomienda_que_migre_cada_pod(self):
        """Era `docker/k8s/README.md:37`: «sin `command`/`args` en el pod (recomendado)»."""
        self.assertNotIn("Sin `command`/`args` en el pod** (recomendado)", self.readme)
        self.assertIn("bootstrap-job.yaml", self.readme)
        self.assertIn("RUN_MIGRATIONS=false", self.readme)

    def test_la_guia_dice_que_el_job_va_antes_del_rollout(self):
        self.assertIn("kubectl wait", self.readme)


class ReglaExpandContractTests(SimpleTestCase):
    """Durante el rolling los pods viejos siguen atendiendo contra el esquema nuevo."""

    def test_claude_md_tiene_la_regla_y_sus_tres_clases(self):
        claude = (RAIZ / "CLAUDE.md").read_text(encoding="utf-8")

        self.assertIn("expand", claude.lower())
        self.assertIn("# CONTRACT:", claude)
        self.assertIn("# ROLLBACK-OK:", claude)

    def test_la_guia_de_kubernetes_explica_por_que_el_contract_espera(self):
        readme = (K8S / "README.md").read_text(encoding="utf-8")

        self.assertIn("Expand/contract", readme)
        self.assertIn("dos releases después", readme)
