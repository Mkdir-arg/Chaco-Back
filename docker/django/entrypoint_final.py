#!/usr/bin/env python
"""
Entrypoint final para el contenedor Django
Versión simplificada que ejecuta setup y servidor
"""

import os
import subprocess
import sys
import time


def wait_for_mysql():
    """Espera a que MySQL esté disponible"""
    print("🔄 Esperando MySQL...")

    for attempt in range(30):
        try:
            result = subprocess.run(
                ["mysql", "-h", "mysql", "-u", "root", "-p${DATABASE_PASSWORD:-chaco_pass}", "-e", "SELECT 1"],
                capture_output=True,
                timeout=5,
            )

            if result.returncode == 0:
                print("✅ MySQL disponible!")
                return True
        except:
            pass

        print(f"⏳ Intento {attempt + 1}/30...")
        time.sleep(2)

    return False


def main():
    print("🐳 SISOC - INICIANDO CONTENEDOR")

    # Cambiar al directorio correcto
    os.chdir("/sisoc")

    # Esperar MySQL
    if not wait_for_mysql():
        print("❌ MySQL no disponible")
        sys.exit(1)

    # Ejecutar setup
    print("🚀 Ejecutando configuración...")
    try:
        subprocess.run([sys.executable, "setup_sistema_completo.py"], check=True)
        print("✅ Configuración completada")
    except:
        print("⚠️ Error en configuración, continuando...")

    # Iniciar servidor
    print("🌐 Iniciando servidor...")
    subprocess.run([sys.executable, "manage.py", "runserver", "0.0.0.0:8000"])


if __name__ == "__main__":
    main()
