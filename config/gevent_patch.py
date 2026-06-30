# config/gevent_patch.py
"""
Parche para compatibilidad Django + gevent
Soluciona problemas de thread safety con conexiones de base de datos
"""

import os


def patch_django_for_gevent():
    """Aplica parches necesarios para que Django funcione con gevent"""

    # Solo aplicar en producción con gevent
    if os.environ.get("GUNICORN_WORKER_CLASS") == "gevent":
        # Parche 1: Deshabilitar thread checking en conexiones DB
        from django.db.backends.base.base import BaseDatabaseWrapper

        # Monkey patch para deshabilitar validación de threads
        original_validate = BaseDatabaseWrapper.validate_thread_sharing

        def patched_validate(self):
            # No hacer nada - permitir compartir conexiones entre greenlets
            pass

        BaseDatabaseWrapper.validate_thread_sharing = patched_validate

        # Parche 2: Forzar nuevas conexiones para cada greenlet
        from django.db import connections

        def close_old_connections():
            for conn in connections.all():
                conn.close_if_unusable_or_obsolete()

        # Aplicar al inicio de cada request
        from django.core.signals import request_started

        request_started.connect(lambda sender, **kwargs: close_old_connections())

        print("[GEVENT] Parches aplicados para compatibilidad Django + gevent")


def apply_gevent_patches():
    """Función principal para aplicar todos los parches"""
    try:
        patch_django_for_gevent()
    except Exception as e:
        print(f"[GEVENT] Error aplicando parches: {e}")
