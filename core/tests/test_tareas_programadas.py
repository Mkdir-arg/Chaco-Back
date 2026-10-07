"""G3-04 y G3-05 · Las cuatro tareas programadas, en los dos ambientes.

Los mismos cuatro comandos corren en Kubernetes (CronJob) y en icore-srv (cron del host).
En los dos lados el modo de falla es el mismo y es silencioso: **una corrida que se
cuelga**. En k8s, con `concurrencyPolicy: Forbid` y sin `activeDeadlineSeconds`, el Job
colgado bloquea todas las corridas siguientes y nadie se entera; en icore no había ni
candado ni límite de tiempo, así que dos `generar_alertas` podían solaparse y un
`docker exec` colgado quedaba corriendo para siempre.

Lo que se fija acá:

* **G3-04** — cada CronJob declara su zona horaria (el manifiesto decía desde siempre que
  los horarios «replican el cron de la VM en hora argentina», y sin `timeZone` corrían en
  UTC), su `startingDeadlineSeconds`, su `activeDeadlineSeconds`, `backoffLimit: 1` —sin
  él, un `sincronizar_programas_siis` que falla porque SIIS está caído se reintenta seis
  veces contra SIIS— y el historial acotado.
* **G3-05** — los cuatro snippets de icore están versionados (faltaban dos, y los otros
  dos los nombraban como «ya existentes»), y todos pasan por el envoltorio con `flock`,
  `timeout` y fecha en el log.

El manifiesto real de ECOM no está en el repo (H-05): esto es la plantilla de referencia.
"""

from pathlib import Path

import yaml
from django.conf import settings
from django.test import SimpleTestCase

RAIZ = Path(settings.BASE_DIR)
CRONJOBS = RAIZ / "docker" / "k8s" / "cronjobs.yaml"
CRON = RAIZ / "docker" / "cron"

ZONA = "America/Argentina/Buenos_Aires"

#: comando → (nombre del CronJob, segundos de `activeDeadlineSeconds`)
TAREAS = {
    "generar_alertas": ("datanach-generar-alertas", 1800),
    "procesar_vencimientos": ("datanach-procesar-vencimientos", 900),
    "limpiar_alertas_conversaciones": ("datanach-limpiar-alertas-conversaciones", 900),
    "sincronizar_programas_siis": ("datanach-sincronizar-programas-siis", 1800),
}


def _cronjobs():
    documentos = [doc for doc in yaml.safe_load_all(CRONJOBS.read_text(encoding="utf-8")) if doc]
    return {doc["metadata"]["name"]: doc for doc in documentos}


class CronJobsDeKubernetesTests(SimpleTestCase):
    """G3-04."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cronjobs = _cronjobs()

    def test_estan_los_cuatro(self):
        self.assertEqual(set(self.cronjobs), {nombre for nombre, _ in TAREAS.values()})

    def test_cada_uno_declara_su_zona_horaria(self):
        """Sin `timeZone` el `schedule` corre en UTC y el archivo dice lo contrario."""
        for comando, (nombre, _) in TAREAS.items():
            with self.subTest(comando=comando):
                self.assertEqual(self.cronjobs[nombre]["spec"].get("timeZone"), ZONA)

    def test_cada_uno_tiene_limite_de_tiempo_y_de_reintentos(self):
        for comando, (nombre, deadline) in TAREAS.items():
            with self.subTest(comando=comando):
                spec = self.cronjobs[nombre]["spec"]
                self.assertEqual(spec["jobTemplate"]["spec"].get("activeDeadlineSeconds"), deadline)
                self.assertEqual(spec["jobTemplate"]["spec"].get("backoffLimit"), 1)

    def test_cada_uno_acota_el_arranque_tardio_y_el_historial(self):
        for comando, (nombre, _) in TAREAS.items():
            with self.subTest(comando=comando):
                spec = self.cronjobs[nombre]["spec"]
                self.assertEqual(spec.get("startingDeadlineSeconds"), 600)
                self.assertEqual(spec.get("successfulJobsHistoryLimit"), 3)
                self.assertEqual(spec.get("failedJobsHistoryLimit"), 5)

    def test_sigue_el_forbid_que_evita_dos_corridas_a_la_vez(self):
        for comando, (nombre, _) in TAREAS.items():
            with self.subTest(comando=comando):
                self.assertEqual(self.cronjobs[nombre]["spec"].get("concurrencyPolicy"), "Forbid")

    def test_los_horarios_son_los_mismos_que_en_icore(self):
        """Con `timeZone` puesto, los dos ambientes corren a la misma hora local."""
        esperados = {
            "datanach-generar-alertas": "0 * * * *",
            "datanach-procesar-vencimientos": "10 3 * * *",
            "datanach-limpiar-alertas-conversaciones": "30 3 * * *",
            "datanach-sincronizar-programas-siis": "0 4 * * *",
        }
        for nombre, schedule in esperados.items():
            with self.subTest(nombre=nombre):
                self.assertEqual(self.cronjobs[nombre]["spec"]["schedule"], schedule)


class CronDeIcoreTests(SimpleTestCase):
    """G3-05."""

    def test_los_cuatro_snippets_estan_versionados(self):
        """Faltaban `generar_alertas` y `limpiar_alertas_conversaciones`: los otros dos
        los nombraban como «los crons ya existentes», que no estaban en ninguna parte."""
        for comando in TAREAS:
            with self.subTest(comando=comando):
                self.assertTrue((CRON / f"{comando}.cron").is_file(), f"falta docker/cron/{comando}.cron")

    def test_existe_el_envoltorio_con_candado_y_limite(self):
        envoltorio = (CRON / "chaco-cron.sh").read_text(encoding="utf-8")

        self.assertIn("flock", envoltorio)
        self.assertIn("timeout", envoltorio)
        self.assertIn("date", envoltorio)

    def test_cada_linea_de_cron_pasa_por_el_envoltorio(self):
        for comando in TAREAS:
            with self.subTest(comando=comando):
                lineas = [
                    linea
                    for linea in (CRON / f"{comando}.cron").read_text(encoding="utf-8").splitlines()
                    if linea.strip() and not linea.lstrip().startswith("#")
                ]
                self.assertEqual(len(lineas), 1, "un snippet, una línea de crontab")
                self.assertIn("chaco-cron.sh", lineas[0])
                self.assertIn(comando, lineas[0])

    def test_hay_rotacion_del_log(self):
        """`~/cron-chaco.log` crecía sin límite: es el único registro de las corridas."""
        self.assertTrue((CRON / "logrotate-cron-chaco.conf").is_file())
