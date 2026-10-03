r"""SEC-01: aplica en config/settings.py los defaults de DRF propuestos. Solo para probar en un
worktree descartable (el fix real se escribe a mano en el PR). Correr desde la raíz del repo:
  & C:\Users\mkdir\Proyectos\Chaco\.venv312\Scripts\python.exe <ruta>\patch_settings_sec01.py
"""

p = "config/settings.py"
s = open(p, encoding="utf-8").read()
old = '    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",\n'
new = old + (
    '    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],\n'
    '    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],\n'
)
assert old in s
open(p, "w", encoding="utf-8").write(s.replace(old, new, 1))
print("ok")
