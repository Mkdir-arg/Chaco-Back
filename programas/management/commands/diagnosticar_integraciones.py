"""Diagnóstico de las integraciones del entorno, con foco en el formulario público.

No escribe nada de negocio: recorre los mismos caminos que usa la aplicación e
informa dónde se corta. Nació de un caso real: en un entorno recién desplegado
el paso 1 del link público decía "No pudimos validar tus datos" y las tres
causas posibles —credenciales de Base de Personas sin cargar, servicio que
rechaza, o DNI que no está en la fuente— se ven **idénticas** desde la pantalla,
porque por diseño la inscripción sigue igual y queda como no validada.

    python manage.py diagnosticar_integraciones
    python manage.py diagnosticar_integraciones --dni 36210951 --sexo F
    python manage.py diagnosticar_integraciones --dni 36210951 --sexo F --relevamiento 12
    python manage.py diagnosticar_integraciones --token 3f6c1e4a-... --dni 36210951 --sexo F

Con ``--dni`` sale a la red contra Base de Personas (Gran Base) y dice si el
formulario público precargaría los datos. Con ``--relevamiento``/``--token``
audita además por qué un link acepta o no inscripciones.

Nunca imprime secretos: de cada credencial informa si está presente y su largo.
Devuelve código de salida distinto de 0 si algún paso falla, para usarlo como
chequeo de despliegue.
"""

from django.conf import settings
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone

CAP_PUBLICO = "becas.relevamiento.publico"
CACHE_PROBE_KEY = "diagnosticar_integraciones:probe"


class Command(BaseCommand):
    help = "Verifica las variables de todas las integraciones y prueba Base de Personas (formulario público)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dni",
            help="DNI con el que probar Base de Personas de verdad (sale a la red). Sin esto solo se audita la config.",
        )
        parser.add_argument(
            "--sexo",
            default="M",
            help="Sexo del --dni: F o M (acepta Femenino/Masculino). Default: M.",
        )
        parser.add_argument(
            "--relevamiento",
            type=int,
            help="pk de un relevamiento público: audita si su link acepta inscripciones y por qué.",
        )
        parser.add_argument(
            "--token",
            help="token_publico de un relevamiento (alternativa a --relevamiento; es lo que va en la URL del link).",
        )

    def handle(self, *args, **options):
        self._fallas = []
        self._avisos = 0

        self._titulo(f"Entorno: {getattr(settings, 'ENVIRONMENT', '(sin ENVIRONMENT)')} · zona {settings.TIME_ZONE}")
        self._ok(f"ahora = {timezone.localtime().strftime('%d/%m/%Y %H:%M')} (hora del servidor)")

        self._base_de_datos()
        self._cache()
        resultado_personas = self._base_de_personas(options["dni"], options["sexo"])
        self._renaper()
        self._siis()
        self._correo()
        self._formulario_publico(options, resultado_personas)

        self._cerrar()

    # ── Infraestructura ────────────────────────────────────────────────────────

    def _base_de_datos(self):
        self._titulo("Base de datos")
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            self._ok(f"{connection.vendor}: responde")
        except Exception as exc:
            self._error(f"no responde: {type(exc).__name__} {exc}")

    def _cache(self):
        self._titulo("Caché / Redis")
        backend = settings.CACHES["default"]["BACKEND"]
        self.stdout.write(f"       backend: {backend}")
        if "locmem" in backend.lower():
            self._aviso("caché en memoria del proceso: el token de las APIs no se comparte entre workers")
        try:
            cache.set(CACHE_PROBE_KEY, "ok", 30)
            leido = cache.get(CACHE_PROBE_KEY)
            cache.delete(CACHE_PROBE_KEY)
            if leido == "ok":
                self._ok("escritura y lectura OK")
            else:
                self._error(f"escribió pero leyó {leido!r}")
        except Exception as exc:
            # Un Redis caído acá es grave: el cliente de Personas cachea el token
            # y la excepción de conexión NO está atrapada en `consultar()`.
            self._error(f"no responde: {type(exc).__name__} {exc}")

    # ── Integraciones ──────────────────────────────────────────────────────────

    def _base_de_personas(self, dni, sexo):
        """Gran Base: la que usa el paso 1 del formulario público y la app de campo."""
        self._titulo("Base de Personas / Gran Base  [la usa el formulario público]")
        from programas.services.identidad import gran_base_activa
        from programas.services.personas import PersonasAPIClient, consultar_persona

        self._var("PERSONAS_API_ACTIVA", "True" if gran_base_activa() else "False")
        if not gran_base_activa():
            # Cambio 57: apagada a propósito mientras el servicio no responde.
            # No es una falla: la identidad sale del padrón de la convocatoria.
            self._ok(
                "desactivada por configuración: no se consulta en el link, en la app ni en «Revalidar». "
                "La identidad se resuelve con el padrón de la convocatoria (nombre y apellido en el Excel)."
            )
            self._aviso("cuando el servicio vuelva, poné PERSONAS_API_ACTIVA=True: manda sobre el padrón si difieren")
            return None

        cliente = PersonasAPIClient()
        self._var("PERSONAS_API_URL", cliente.base_url)
        self._secreto("PERSONAS_API_CLIENT_ID", cliente.client_id)
        self._secreto("PERSONAS_API_CLIENT_SECRET", cliente.client_secret)
        self._var("PERSONAS_API_ENTIDAD_UUID", cliente.entidad_uuid)
        self._var("PERSONAS_API_FUENTE_ID", cliente.fuente_id)
        self.stdout.write(f"       timeouts: {cliente.timeout[0]}s conectar, {cliente.timeout[1]}s leer")

        if not cliente._configurada():
            self._error(
                "configuración incompleta: el formulario público NUNCA va a precargar datos y no deja rastro "
                "en el log (la consulta corta antes de salir a la red). Faltan credenciales en el entorno."
            )
            return None
        self._ok("configuración completa")

        try:
            token = cliente._token()
            self._ok(f"token obtenido ({len(token)} caracteres)")
        except Exception as exc:
            self._error(f"no se pudo obtener el token: {type(exc).__name__} {str(exc)[:200]}")
            return None

        if not dni:
            self._aviso("sin --dni no se probó una consulta real (la config está bien, pero no se ejercitó)")
            return None

        sexo_norm = self._normalizar_sexo(sexo)
        if not sexo_norm:
            self._error(f"--sexo {sexo!r} no es válido: usá F o M")
            return None

        resultado = consultar_persona(dni, sexo_norm)
        if resultado.get("success"):
            datos = resultado.get("data") or {}
            nombre, apellido = datos.get("nombre", ""), datos.get("apellido", "")
            self._ok(f"consulta {dni}/{sexo_norm}: {apellido}, {nombre}")
            self.stdout.write(f"       fecha de nacimiento: {datos.get('fecha_nacimiento') or '(no vino)'}")
            if nombre and apellido:
                self._ok("el formulario público precargaría estos datos (origen=personas, identidad validada)")
            else:
                # Sin nombre o apellido el paso 1 lo toma como no validado.
                self._aviso("respondió pero sin nombre/apellido: el formulario quedaría como NO validado")
            if not datos.get("fecha_nacimiento"):
                self._aviso("sin fecha de nacimiento el paso 2 la pide a mano (RN-22 necesita la edad)")
            if resultado.get("fallecido"):
                self._aviso("la persona figura como fallecida: el paso 1 rechaza la inscripción")
            return resultado

        if resultado.get("not_found"):
            self._aviso(
                f"consulta {dni}/{sexo_norm}: la API respondió OK pero el DNI no está en la fuente "
                f"{cliente.fuente_id}. La integración funciona; ese documento se cargaría a mano."
            )
            return resultado

        self._error(f"consulta {dni}/{sexo_norm} falló: {resultado.get('error')}")
        return resultado

    def _renaper(self):
        """Otra integración: la usa el backoffice (legajos), no el formulario público."""
        self._titulo("RENAPER  [backoffice/legajos, no el formulario público]")
        if getattr(settings, "RENAPER_TEST_MODE", False):
            self._aviso("RENAPER_TEST_MODE=True: devuelve datos de prueba, no consulta el servicio real")
            return
        self._var("RENAPER_API_URL", settings.RENAPER_API_URL)
        self._var("RENAPER_LOGIN_URL", settings.RENAPER_LOGIN_URL)
        self._var("RENAPER_CONSULTA_URL", settings.RENAPER_CONSULTA_URL)
        self._secreto("RENAPER_API_USERNAME", settings.RENAPER_API_USERNAME)
        self._secreto("RENAPER_API_PASSWORD", settings.RENAPER_API_PASSWORD)
        self._secreto("RENAPER_API_KEY", settings.RENAPER_API_KEY)
        modo = getattr(settings, "RENAPER_AUTH_MODE", "auto")
        tiene_credenciales = bool(settings.RENAPER_API_USERNAME and settings.RENAPER_API_PASSWORD)
        if not settings.RENAPER_API_URL and not settings.RENAPER_CONSULTA_URL:
            self._error("sin URL de consulta y sin TEST_MODE: el backoffice no puede validar identidad")
        elif modo in ("credentials", "auto") and not tiene_credenciales and not settings.RENAPER_API_KEY:
            self._error(f"sin credenciales ni API key (RENAPER_AUTH_MODE={modo})")
        else:
            self._ok(f"configuración presente (modo {modo})")

    def _siis(self):
        self._titulo("SIIS  [catálogo de programas]")
        self._var("SIIS_API_URL", settings.SIIS_API_URL)
        self._secreto("SIIS_API_CLIENT_ID", settings.SIIS_API_CLIENT_ID)
        self._secreto("SIIS_API_CLIENT_SECRET", settings.SIIS_API_CLIENT_SECRET)
        if not all((settings.SIIS_API_URL, settings.SIIS_API_CLIENT_ID, settings.SIIS_API_CLIENT_SECRET)):
            self._error("configuración incompleta: el select de Programa SIIS va a quedar vacío")
        else:
            self._ok("configuración completa — la prueba en vivo es `manage.py diagnosticar_siis`")

    def _correo(self):
        self._titulo("Correo / SMTP  [confirmación de la inscripción pública y credenciales]")
        backend = settings.EMAIL_BACKEND
        self.stdout.write(f"       backend: {backend}")
        if "console" in backend or "locmem" in backend or "dummy" in backend:
            self._aviso(f"backend de desarrollo ({backend}): los correos no salen del servidor")
            return
        self._var("EMAIL_HOST", settings.EMAIL_HOST)
        self._var("EMAIL_PORT", settings.EMAIL_PORT)
        self._var("DEFAULT_FROM_EMAIL", settings.DEFAULT_FROM_EMAIL)
        self._secreto("EMAIL_HOST_PASSWORD", settings.EMAIL_HOST_PASSWORD)
        if not settings.EMAIL_HOST:
            self._error("sin EMAIL_HOST: la confirmación de inscripción no se va a enviar")
        else:
            self._ok("configuración presente — la prueba en vivo es `manage.py diagnosticar_correo`")

    # ── Formulario público ─────────────────────────────────────────────────────

    def _formulario_publico(self, options, resultado_personas):
        """Lo que hace falta del lado de la app para que el link funcione.

        Todo lo de acá toca la base: si el entorno todavía no migró, se informa y
        se sigue, porque el valor del comando está en el resto del diagnóstico.
        """
        try:
            self._formulario_publico_inner(options, resultado_personas)
        except Exception as exc:
            self._error(f"no se pudo auditar el formulario público: {type(exc).__name__} {exc}")

    def _formulario_publico_inner(self, options, resultado_personas):
        from core import rbac
        from programas.models import Relevamiento

        self._titulo("Formulario público: capacidad y roles")
        if CAP_PUBLICO not in rbac.codigos_de_capacidad():
            self._error(f"{CAP_PUBLICO} no está en el catálogo de capacidades")
            return
        codename = rbac.codename_de(CAP_PUBLICO)
        roles = list(
            Group.objects.filter(permissions__codename=codename)
            .values_list("name", flat=True)
            .distinct()
            .order_by("name")
        )
        if roles:
            self._ok(f"{CAP_PUBLICO} la tienen: {', '.join(roles)}")
        else:
            self._aviso(
                f"ningún rol tiene {CAP_PUBLICO}: la superficie del backoffice está oculta para todos "
                "(salvo superusuarios). Encender = tildarla en la pantalla de Roles."
            )

        publicos = Relevamiento.objects.filter(tipo=Relevamiento.Tipo.PUBLICO)
        self.stdout.write(f"       relevamientos públicos en la base: {publicos.count()}")

        rel = self._buscar_relevamiento(options, publicos)
        if rel is not None:
            self._auditar_link(rel, options, resultado_personas)

    def _buscar_relevamiento(self, options, publicos):
        from programas.models import Relevamiento

        if options["relevamiento"]:
            rel = Relevamiento.objects.filter(pk=options["relevamiento"]).select_related("convocatoria").first()
            if rel is None:
                self._error(f"no existe el relevamiento #{options['relevamiento']}")
            elif not rel.es_publico:
                self._error(f"el relevamiento #{rel.pk} no es de formulario público (tipo={rel.tipo})")
                rel = None
            return rel
        if options["token"]:
            rel = publicos.filter(token_publico=options["token"]).select_related("convocatoria").first()
            if rel is None:
                self._error(f"ningún relevamiento público tiene el token {options['token']}")
            return rel
        return None

    def _auditar_link(self, rel, options, resultado_personas):
        from portal.services.inscripcion import dni_ya_inscripto, relevamiento_disponible
        from programas.models import Relevamiento
        from programas.services.padron import esta_habilitado

        ahora = timezone.localtime()
        self._titulo(f"Link del relevamiento #{rel.pk} — {rel.nombre}")
        self.stdout.write(f"       convocatoria : {rel.convocatoria}")
        self.stdout.write(f"       URL          : {rel.url_publica}")
        self.stdout.write(
            f"       ventana      : {timezone.localtime(rel.fecha_asignada).strftime('%d/%m/%Y %H:%M')}"
            f" → {timezone.localtime(rel.fecha_hasta).strftime('%d/%m/%Y %H:%M')}"
        )
        self.stdout.write(f"       estado       : {rel.get_estado_display()}")
        self.stdout.write(f"       cupo         : {rel.cupo_utilizado} / {rel.cupo_maximo}")
        # El padrón es de la convocatoria (Cambio 57).
        padron_qs = rel.convocatoria.padron.all()
        padron = padron_qs.count()
        con_identidad = padron_qs.exclude(nombre="").exclude(apellido="").count()
        self.stdout.write(
            f"       padrón       : {f'{padron} habilitados, {con_identidad} con identidad' if padron else 'sin padrón (link abierto)'}"
        )
        self.stdout.write(f"       correo       : {'sí' if rel.confirmar_por_email else 'no'}")

        # Los cuatro motivos que muestran la MISMA pantalla "no disponible".
        if rel.estado != Relevamiento.Estado.EN_CURSO:
            self._error(f"estado {rel.get_estado_display()}: el link solo acepta envíos En curso (reabrilo)")
        if rel.fecha_asignada > ahora:
            self._error(f"todavía no empezó: arranca {timezone.localtime(rel.fecha_asignada).strftime('%d/%m %H:%M')}")
        if rel.fecha_hasta < ahora:
            self._error(f"vencido: terminó {timezone.localtime(rel.fecha_hasta).strftime('%d/%m %H:%M')}")
        pausa = rel.pausa_efectiva
        if pausa is not None:
            self._error(
                f"pausado o bloqueado ({type(pausa).__name__}): {getattr(pausa, 'pausa_motivo', '') or 'sin motivo'}"
            )
        if rel.cupo_completo:
            self._error(f"cupo completo: {rel.cupo_utilizado}/{rel.cupo_maximo}")

        if relevamiento_disponible(rel):
            self._ok("el link ACEPTA inscripciones")
        else:
            self._error("el link muestra «Formulario no disponible» (ver los motivos de arriba)")

        if rel.confirmar_por_email and "console" in settings.EMAIL_BACKEND:
            self._aviso("tiene confirmación por correo pero el backend es de consola: el correo no sale")

        dni = options["dni"]
        if not dni:
            return
        sexo_norm = self._normalizar_sexo(options["sexo"])
        if padron and not esta_habilitado(rel, dni, sexo_norm):
            self._error(f"el DNI {dni} NO está en el padrón (con ese sexo): el paso 1 lo rechaza")
        elif padron:
            from programas.services.padron import fila_padron

            fila = fila_padron(rel, dni, sexo_norm)
            if fila is not None and fila.tiene_identidad:
                self._ok(
                    f"el DNI {dni} está en el padrón con identidad: el paso 2 precarga {fila.apellido}, {fila.nombre}"
                )
            else:
                self._aviso(f"el DNI {dni} está en el padrón pero sin nombre y apellido: no valida por padrón")
        if dni_ya_inscripto(rel.convocatoria, dni):
            self._aviso(f"el DNI {dni} ya tiene un formulario en esta convocatoria: el paso 1 corta por duplicado")
        if resultado_personas is not None and not resultado_personas.get("success"):
            self._aviso("con este DNI el paso 2 iba a pedir los datos a mano (ver Base de Personas más arriba)")

    # ── Salida ─────────────────────────────────────────────────────────────────

    @staticmethod
    def _normalizar_sexo(valor):
        from programas.services.padron import normalizar_sexo

        return normalizar_sexo(valor)

    def _var(self, nombre, valor):
        if valor in ("", None):
            self.stdout.write(f"       {nombre:28}: (vacío)")
        else:
            self.stdout.write(f"       {nombre:28}: {valor}")

    def _secreto(self, nombre, valor):
        """Nunca imprime el valor: solo si está y cuánto mide."""
        if not valor:
            self.stdout.write(f"       {nombre:28}: (vacío)")
        else:
            self.stdout.write(f"       {nombre:28}: presente ({len(str(valor))} caracteres)")

    def _titulo(self, texto):
        self.stdout.write(f"\n{texto}")

    def _ok(self, texto):
        self.stdout.write(self.style.SUCCESS(f"  OK    {texto}"))

    def _aviso(self, texto):
        self._avisos += 1
        self.stdout.write(self.style.WARNING(f"  AVISO {texto}"))

    def _error(self, texto):
        self._fallas.append(texto)
        self.stdout.write(self.style.ERROR(f"  FALLA {texto}"))

    def _cerrar(self):
        self.stdout.write("")
        if self._fallas:
            self.stdout.write(
                self.style.ERROR(f"Diagnóstico con {len(self._fallas)} falla(s) y {self._avisos} aviso(s):")
            )
            for falla in self._fallas:
                self.stdout.write(self.style.ERROR(f"  - {falla}"))
            raise SystemExit(1)
        self.stdout.write(self.style.SUCCESS(f"Diagnóstico sin fallas ({self._avisos} aviso(s))."))
