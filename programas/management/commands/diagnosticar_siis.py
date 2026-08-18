"""Diagnóstico de la integración con SIIS, para verificar un entorno recién configurado.

No escribe nada: recorre el mismo camino que usa la aplicación (el cliente de
``programas.services.siis``) y va informando dónde se corta. Sirve para separar
las tres causas que se ven iguales desde el backoffice —el select de "Programa
SIIS" vacío—: falta de configuración, rechazo del servicio, o un catálogo que
llega pero que el normalizador descarta por un cambio de contrato de ECOM.

    python manage.py diagnosticar_siis
    python manage.py diagnosticar_siis --usar-cache
    python manage.py diagnosticar_siis --dni 20123456 --programa 34

Devuelve código de salida distinto de 0 si algún paso falla, para poder usarlo
como chequeo de despliegue.
"""

from django.conf import settings
from django.core.cache import cache
from django.core.management.base import BaseCommand

from programas.services.siis import (
    ESTADO_ACTIVO,
    PROGRAMAS_CACHE_KEY,
    PROGRAMAS_TODOS_CACHE_KEY,
    TOKEN_CACHE_KEY,
    SiisAPIClient,
    SiisCatalogError,
    motivos_de_rechazo,
)


class Command(BaseCommand):
    help = "Verifica la integración con SIIS paso a paso: configuración, token, catálogo y parseo."

    def add_arguments(self, parser):
        parser.add_argument(
            "--usar-cache",
            action="store_true",
            help=(
                "No invalida el token ni el catálogo cacheados. Por defecto se descartan "
                "para que la prueba salga a la red."
            ),
        )
        parser.add_argument("--dni", help="DNI para probar además la prevalidación de compatibilidad.")
        parser.add_argument(
            "--programa",
            type=int,
            help="id del programa SIIS contra el que validar el --dni. Si se omite, se toma el primero del catálogo.",
        )

    def handle(self, *args, **options):
        self._fallas = []
        cliente = SiisAPIClient()

        if not options["usar_cache"]:
            cache.delete_many([TOKEN_CACHE_KEY, PROGRAMAS_CACHE_KEY, PROGRAMAS_TODOS_CACHE_KEY])
            self.stdout.write("Cachés de token y catálogo descartadas: la prueba sale a la red.")

        if not self._paso_configuracion(cliente):
            self._cerrar()
            return

        if not self._paso_token(cliente):
            self._cerrar()
            return

        programas = self._paso_catalogo(cliente)
        if options["dni"]:
            self._paso_compatibilidad(cliente, options["dni"], options["programa"], programas)

        self._cerrar()

    # -- Pasos ----------------------------------------------------------------

    def _paso_configuracion(self, cliente):
        self._titulo("1. Configuración del entorno")
        faltantes = []
        for nombre, valor, secreto in (
            ("SIIS_API_URL", cliente.base_url, False),
            ("SIIS_API_CLIENT_ID", cliente.client_id, False),
            ("SIIS_API_CLIENT_SECRET", cliente.client_secret, True),
        ):
            if not valor:
                faltantes.append(nombre)
                self._error(f"{nombre}: vacía")
            elif secreto:
                self._ok(f"{nombre}: presente ({len(valor)} caracteres)")
            else:
                self._ok(f"{nombre}: {valor}")

        connect, leer = cliente.timeout
        self.stdout.write(f"       timeouts: {connect}s para conectar, {leer}s para leer")

        if faltantes:
            self._error(
                f"Sin {', '.join(faltantes)} el cliente corta antes de salir a la red y el select "
                "de Programa SIIS queda vacío. Los valores los emite ECOM."
            )
            return False

        # El default apunta al entorno de test de ECOM: si un entorno productivo
        # quedó con ese valor, el catálogo trae datos desactualizados sin fallar.
        if "ecomdev.ar" in cliente.base_url and settings.ENVIRONMENT == "prd":
            self._aviso(
                f"ENVIRONMENT=prd pero SIIS_API_URL apunta a {cliente.base_url}, "
                "que es el entorno de test de ECOM."
            )
        return True

    def _paso_token(self, cliente):
        self._titulo("2. Autenticación (POST /api/v1/auth/token)")
        try:
            token = cliente._token()
        except Exception as exc:  # noqa: BLE001 — el diagnóstico informa cualquier falla, no la propaga
            self._error(f"No se pudo obtener el token: {type(exc).__name__}: {exc}")
            respuesta = getattr(exc, "response", None)
            if respuesta is not None:
                self._error(f"SIIS respondió HTTP {respuesta.status_code}: {respuesta.text[:300]}")
            return False
        self._ok(f"Token obtenido ({len(token)} caracteres).")
        return True

    def _paso_catalogo(self, cliente):
        """Compara el catálogo crudo con el normalizado para aislar cambios de contrato."""
        self._titulo("3. Catálogo de programas (GET /api/v1/programas)")
        activos = []
        for estado in (ESTADO_ACTIVO, "TODOS"):
            try:
                cuerpo = cliente._cargar_catalogo(
                    f"/api/v1/programas?estado={estado}", "Catálogo no encontrado."
                )
            except SiisCatalogError as exc:
                self._error(f"estado={estado}: {exc}")
                continue

            crudos = cliente._items(cuerpo, "programas", "results")
            normalizados = cliente._normalizar_catalogo(crudos, ("id", "id_programa"))
            if estado == ESTADO_ACTIVO:
                activos = [p for p in normalizados if p["estado"] == ESTADO_ACTIVO]
                usables = activos
            else:
                usables = normalizados

            self.stdout.write(f"\n  estado={estado}")
            self.stdout.write(f"       items en la respuesta   : {len(crudos)}")
            self.stdout.write(f"       interpretados por la app: {len(normalizados)}")
            if estado == ESTADO_ACTIVO:
                self.stdout.write(f"       que llegan al select    : {len(usables)}")

            if not crudos:
                self._aviso(
                    f"SIIS respondió sin programas para estado={estado}. No es un error de integración: "
                    "el catálogo del entorno está vacío o no publica programas para este cliente."
                )
            elif not normalizados:
                # Único caso que es culpa nuestra: los datos llegaron y el
                # normalizador los tiró. Se muestran las claves recibidas para
                # poder comparar contra las que el cliente espera.
                claves = sorted(crudos[0].keys()) if isinstance(crudos[0], dict) else type(crudos[0]).__name__
                self._error(
                    "SIIS devolvió programas pero ninguno sobrevive al parseo. Es un cambio de contrato: "
                    "el normalizador espera 'id'/'id_programa' y 'nombre'/'descripcion'/'denominacion'."
                )
                self.stdout.write(f"       claves del primer item: {claves}")
            elif not usables:
                # Se interpretaron bien pero ninguno está vigente. No es falla:
                # el select vacío es correcto y el motivo es la vigencia.
                self._aviso(
                    "Los programas se interpretaron bien pero ninguno está ACTIVO, así que el select "
                    "queda vacío igual. El motivo es la vigencia en SIIS, no la integración."
                )
                for programa in normalizados[:10]:
                    self.stdout.write(f"         #{programa['id']} {programa['nombre']} [{programa['estado']}]")
            else:
                self._ok(f"{len(usables)} programa(s) usable(s).")
                for programa in usables[:10]:
                    self.stdout.write(f"         #{programa['id']} {programa['nombre']} [{programa['estado']}]")
                if len(usables) > 10:
                    self.stdout.write(f"         y {len(usables) - 10} más")
        return activos

    def _paso_compatibilidad(self, cliente, dni, id_programa, programas):
        self._titulo("4. Prevalidación de compatibilidad (POST /api/v1/validaciones/compatibilidad)")
        if id_programa is None:
            if not programas:
                self._aviso("No hay programa contra el que validar: pasá --programa <id>.")
                return
            id_programa = programas[0]["id"]
            self.stdout.write(f"       sin --programa: se usa #{id_programa} del catálogo")

        resultado = cliente.validar_compatibilidad(dni, id_programa)
        if not resultado["success"]:
            self._error(f"La consulta falló: {resultado['error']}")
            return

        datos = resultado["data"]
        veredicto = "APTO" if resultado["compatible"] else "NO APTO"
        self._ok(f"SIIS respondió: resultado={datos.get('resultado')}, apto={datos.get('apto')} -> {veredicto}")
        for bandera, texto in motivos_de_rechazo(datos.get("validaciones")):
            self.stdout.write(f"         {bandera}: {texto}")

    # -- Salida ---------------------------------------------------------------

    def _titulo(self, texto):
        self.stdout.write(f"\n{texto}")

    def _ok(self, texto):
        self.stdout.write(self.style.SUCCESS(f"  OK    {texto}"))

    def _aviso(self, texto):
        self.stdout.write(self.style.WARNING(f"  AVISO {texto}"))

    def _error(self, texto):
        self._fallas.append(texto)
        self.stdout.write(self.style.ERROR(f"  FALLA {texto}"))

    def _cerrar(self):
        self.stdout.write("")
        if self._fallas:
            self.stdout.write(
                self.style.ERROR(
                    f"Diagnóstico con {len(self._fallas)} falla(s). La integración no está operativa."
                )
            )
            # Código de salida != 0 para poder usarlo como gate de despliegue.
            raise SystemExit(1)
        self.stdout.write(self.style.SUCCESS("Diagnóstico sin fallas: la integración con SIIS responde."))
