"""El registro de modelos **tal como era** cuando corrió una migración (RED-17).

Los tests de migraciones del repo invocaban la función de la migración con
`django.apps.apps`, o sea con los modelos de **hoy**: un `RunPython` que usa un campo
agregado dos migraciones después pasa el test y revienta en el deploy, que es
exactamente lo que pasó con la `0052` y `padron_archivo` (`0a785d75`, 26/08).

`estado_historico(app, nombre)` devuelve el registro que Django le pasa a esa migración:
el estado del proyecto **antes** de ella (`al_final=False`, que es lo que recibe su
primer `RunPython`) o después (`al_final=True`).

El `override_settings(MIGRATION_MODULES={})` no es decorativo: la suite corre con
`DJANGO_SYNCDB_PROJECT_APPS=True`, que anula las migraciones de las ocho apps del
proyecto (`config/settings.py`). Sin limpiarlo, el loader no encuentra ninguna migración
en disco y el estado histórico sale vacío.
"""

from django.db.migrations.loader import MigrationLoader
from django.test import override_settings


def estado_historico(app, nombre, al_final=False):
    with override_settings(MIGRATION_MODULES={}):
        # `connection=None`: se arma el grafo desde los archivos, sin preguntarle a la
        # base qué está aplicado. El estado histórico es una propiedad del repo.
        loader = MigrationLoader(None, ignore_no_migrations=True)
        return loader.project_state((app, nombre), at_end=al_final).apps
