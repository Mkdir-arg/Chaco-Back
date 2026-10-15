"""Diagnóstico del envío de correo, para verificar un entorno recién configurado.

Recorre el mismo camino que usa la aplicación y va informando dónde se corta.
Sirve para separar las causas que desde el backoffice se ven todas iguales —el
aviso "no se pudo enviar el correo"—: variables sin cargar, DNS, egress cerrado
al 587, credenciales rechazadas, o remitente distinto del que autentica.

    python manage.py diagnosticar_correo
    python manage.py diagnosticar_correo otra.casilla@dominio
    python manage.py diagnosticar_correo --solo-config
    python manage.py diagnosticar_correo --sin-enviar
    python manage.py diagnosticar_correo --canal masivo
    python manage.py diagnosticar_correo --canal masivo --destino otra.casilla@dominio

Con ``--canal masivo`` recorre los mismos pasos contra el SMTP propio de las campañas de
Notificaciones (``NOTIF_EMAIL_*``, Amazon SES; Cambio 311): configuración, DNS, conexión con
login y, solo si se pasa un destino, un correo de prueba por ese canal. Sirve para verificar
desde el pod que hay salida al 587 de SES. La contraseña nunca se imprime: solo su largo.

El correo de prueba usa la plantilla real del alta de usuario, así que además de
la entrega valida el armado del mensaje y que el logo se sirva desde el static
público. Los datos que viajan adentro son de prueba y no habilitan ningún acceso.

Devuelve código de salida distinto de 0 si algún paso falla, para poder usarlo
como chequeo de despliegue.
"""

import re
import smtplib
import socket

from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import EmailMessage, EmailMultiAlternatives, get_connection
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.urls import reverse

from notificaciones.services import canal as canal_campanas
from users.services.correo import contexto_pie

DESTINATARIO_POR_DEFECTO = "farinamatias00@gmail.com"
COMUN = "comun"
MASIVO = "masivo"

_DIRECCION_ENTRE_ANGULOS = re.compile(r"<([^>]+)>")


def direccion_de(remitente):
    """Dirección sola a partir de un remitente con formato ``Nombre <dir@dominio>``."""
    encontrada = _DIRECCION_ENTRE_ANGULOS.search(remitente or "")
    return (encontrada.group(1) if encontrada else (remitente or "")).strip()


class Command(BaseCommand):
    help = "Verifica el envío de correo paso a paso: configuración, conexión, plantillas y entrega real."

    def add_arguments(self, parser):
        parser.add_argument(
            "destinatario",
            nargs="?",
            default=None,
            help=(
                f"Casilla que recibe la prueba. Por defecto {DESTINATARIO_POR_DEFECTO} en el canal común; "
                "en el masivo, sin destino no se manda nada."
            ),
        )
        parser.add_argument(
            "--destino",
            help="Lo mismo que el destinatario posicional, con nombre. Si vienen los dos, manda este.",
        )
        parser.add_argument(
            "--canal",
            choices=(COMUN, MASIVO),
            default=COMUN,
            help=(
                "comun (por defecto): el SMTP del sistema, EMAIL_*. "
                "masivo: el SMTP propio de las campañas de Notificaciones, NOTIF_EMAIL_* (Amazon SES)."
            ),
        )
        parser.add_argument(
            "--solo-config",
            action="store_true",
            help="Solo revisa las variables de entorno. No sale a la red.",
        )
        parser.add_argument(
            "--sin-enviar",
            action="store_true",
            help="Revisa configuración, conexión y plantillas, pero no manda el correo.",
        )
        parser.add_argument(
            "--dominio",
            help=(
                "Dominio para los enlaces del correo. Por defecto el de la variable DOMINIO, "
                "que es la que usa el resto del sistema."
            ),
        )

    def handle(self, *args, **options):
        self._fallas = []
        dominio = options["dominio"] or settings.DOMINIO
        self._p = self._perfil(options["canal"])
        destino = options["destino"] or options["destinatario"]
        if self._p["canal"] == MASIVO:
            self._titulo("Canal masivo de las campañas de Notificaciones (NOTIF_EMAIL_*)")
        elif not destino:
            destino = DESTINATARIO_POR_DEFECTO

        self._paso_configuracion()
        if options["solo_config"]:
            self._cerrar()
            return
        if self._fallas:
            # Sin variables no tiene sentido intentar la conexión: el error sería
            # otro y taparía el verdadero.
            self._cerrar()
            return

        if not self._paso_conexion():
            self._cerrar()
            return

        if self._p["canal"] == MASIVO:
            # Las plantillas de usuario no viajan por este canal: el paso 3 es el envío.
            if destino and not options["sin_enviar"]:
                self._paso_envio_masivo(destino)
            elif not options["sin_enviar"]:
                self._titulo("3. Envío de prueba")
                self.stdout.write("       Sin --destino no se manda nada: en el canal masivo el envío es opcional.")
            self._cerrar()
            return

        if not self._paso_plantillas(dominio):
            self._cerrar()
            return

        if not options["sin_enviar"]:
            self._paso_envio(destino, dominio)

        self._cerrar()

    @staticmethod
    def _perfil(canal):
        """Los datos del canal a revisar, con el prefijo de sus variables para los mensajes."""
        if canal == MASIVO:
            return {
                "canal": MASIVO,
                "prefijo": "NOTIF_EMAIL_",
                "host": settings.NOTIF_EMAIL_HOST,
                "puerto": settings.NOTIF_EMAIL_PORT,
                "usuario": settings.NOTIF_EMAIL_HOST_USER,
                "clave": settings.NOTIF_EMAIL_HOST_PASSWORD,
                "tls": settings.NOTIF_EMAIL_USE_TLS,
                "ssl": False,
                "timeout": settings.NOTIF_EMAIL_TIMEOUT,
                "backend": canal_campanas.backend_masivo(),
                "conexion": canal_campanas.conexion_masiva,
            }
        return {
            "canal": COMUN,
            "prefijo": "EMAIL_",
            "host": settings.EMAIL_HOST,
            "puerto": settings.EMAIL_PORT,
            "usuario": settings.EMAIL_HOST_USER,
            "clave": settings.EMAIL_HOST_PASSWORD,
            "tls": settings.EMAIL_USE_TLS,
            "ssl": getattr(settings, "EMAIL_USE_SSL", False),
            "timeout": settings.EMAIL_TIMEOUT,
            "backend": settings.EMAIL_BACKEND,
            "conexion": get_connection,
        }

    # -- Pasos ----------------------------------------------------------------

    def _paso_configuracion(self):
        self._titulo("1. Configuración del entorno")
        p = self._p
        v = p["prefijo"]

        backend = p["backend"].rsplit(".", 2)[-2]
        if not p["host"]:
            if p["canal"] == MASIVO:
                self._error(
                    "NOTIF_EMAIL_HOST vacía: el canal masivo no está configurado y las campañas salen por el "
                    "correo del sistema (EMAIL_*). Para usar el servicio masivo, cargá las NOTIF_EMAIL_*."
                )
            else:
                self._error(
                    "EMAIL_HOST vacía: el backend es el de consola, los correos se escriben en el log "
                    "y no salen del servidor. Es el modo de desarrollo."
                )
            return
        self._ok(f"{v}HOST: {p['host']} (backend {backend})")

        try:
            ip = socket.gethostbyname(p["host"])
            self._ok(f"DNS: {p['host']} resuelve a {ip}")
        except socket.gaierror as exc:
            self._error(f"DNS: {p['host']} no resuelve ({exc}). Revisá el nombre del servidor.")

        self._ok(f"{v}PORT: {p['puerto']}")

        if not p["usuario"]:
            self._error(f"{v}HOST_USER vacía: sin usuario no hay autenticación y el servidor rechaza el envío.")
        else:
            self._ok(f"{v}HOST_USER: {p['usuario']}")

        if not p["clave"]:
            self._error(f"{v}HOST_PASSWORD vacía.")
        else:
            self._ok(f"{v}HOST_PASSWORD: presente ({len(p['clave'])} caracteres)")

        if p["tls"] and p["ssl"]:
            self._error("EMAIL_USE_TLS y EMAIL_USE_SSL prendidas a la vez: Django rechaza esa combinación.")
        elif p["tls"]:
            self._ok(f"{v}USE_TLS: True (STARTTLS, lo que corresponde al 587)")
        elif p["ssl"]:
            self._aviso("EMAIL_USE_SSL: True. Es el modo del 465; en el 587 va EMAIL_USE_TLS.")
        else:
            self._aviso("Sin TLS ni SSL: la contraseña viajaría en claro. Casi ningún servidor lo acepta.")

        self._ok(f"{v}TIMEOUT: {p['timeout']}s")

        if p["canal"] == MASIVO:
            self._configuracion_masiva()
            return

        remitente = direccion_de(settings.DEFAULT_FROM_EMAIL)
        self._ok(f"DEFAULT_FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}")
        if settings.EMAIL_HOST_USER and remitente.lower() != settings.EMAIL_HOST_USER.lower():
            self._error(
                f"El remitente visible ({remitente}) no es la casilla que autentica "
                f"({settings.EMAIL_HOST_USER}). Sin permiso de relay, el servidor rechaza un From "
                "distinto del autenticado: las dos variables tienen que llevar la misma dirección. "
                "Si difieren solo en el dominio, ahí está el error."
            )

        if settings.ENVIRONMENT == "prd":
            self._ok("ENVIRONMENT=prd: los asuntos van sin prefijo.")
        else:
            self._ok(
                f"ENVIRONMENT={settings.ENVIRONMENT}: los asuntos van prefijados con "
                f'"{settings.EMAIL_ASUNTO_PREFIJO.strip()}" para no confundirse con los reales.'
            )

        pie = []
        pie.append(f"soporte: {settings.EMAIL_SOPORTE or 'sin definir, la línea no se imprime'}")
        pie.append(f"dirección: {settings.EMAIL_PIE_DIRECCION or 'sin definir, no se imprime'}")
        self.stdout.write(f"       pie de los correos — {'; '.join(pie)}")
        self.stdout.write(f"       enlace de recupero válido por {settings.PASSWORD_RESET_TIMEOUT // 3600} h")

    def _configuracion_masiva(self):
        """Lo propio del canal masivo: remitente verificado en SES y ritmo contra su cuota."""
        if settings.NOTIF_DEFAULT_FROM_EMAIL:
            self._ok(f"NOTIF_DEFAULT_FROM_EMAIL: {settings.NOTIF_DEFAULT_FROM_EMAIL}")
        else:
            self._aviso(
                f"NOTIF_DEFAULT_FROM_EMAIL vacía: las campañas salen con DEFAULT_FROM_EMAIL "
                f"({settings.DEFAULT_FROM_EMAIL})."
            )
        self.stdout.write(
            f"       Con Amazon SES el remitente ({direccion_de(canal_campanas.remitente_masivo())}) tiene que ser "
            "una identidad verificada —la dirección o su dominio— en la región del host; si no, SES rechaza "
            "el mensaje. En sandbox, además, solo entrega a direcciones verificadas."
        )
        lote, pausa = settings.NOTIF_LOTE, settings.NOTIF_PAUSA_SEG
        if pausa:
            self._ok(
                f"Ritmo: NOTIF_LOTE={lote} cada NOTIF_PAUSA_SEG={pausa:g}s, a lo sumo ~{lote / pausa:.1f} correos/s. "
                "Tiene que quedar por debajo de la cuota de envíos por segundo de la cuenta SES."
            )
        else:
            self._aviso(
                "NOTIF_PAUSA_SEG=0: sin pausa entre lotes el ritmo lo pone el servidor y puede pasar la cuota "
                "de envíos por segundo de la cuenta SES."
            )
        prefijo = settings.EMAIL_ASUNTO_PREFIJO.strip() or "sin prefijo"
        self._ok(f'ENVIRONMENT={settings.ENVIRONMENT}: prefijo de asunto "{prefijo}".')

    def _paso_conexion(self):
        """Abre la conexión real sin mandar nada: separa red, TLS y credenciales."""
        p = self._p
        self._titulo(f"2. Conexión y autenticación ({p['host']}:{p['puerto']})")
        conexion = p["conexion"]()
        try:
            conexion.open()
        except smtplib.SMTPAuthenticationError as exc:
            self._error(
                f"El servidor rechazó las credenciales: {exc.smtp_code} {self._texto(exc.smtp_error)}. "
                "Revisá usuario y contraseña; llega hasta acá, así que la red y el TLS están bien."
            )
            return False
        except smtplib.SMTPNotSupportedError as exc:
            self._error(f"El servidor no ofrece lo que se le pide ({exc}). Revisá TLS y el puerto.")
            return False
        except (socket.timeout, TimeoutError):
            self._error(
                f"Timeout a los {p['timeout']}s. El puerto {p['puerto']} no responde: "
                "lo más común es que la salida esté filtrada. Hay que habilitar el egress."
            )
            return False
        except ConnectionRefusedError:
            self._error(f"Conexión rechazada en el puerto {p['puerto']}: nada escuchando o firewall.")
            return False
        except socket.gaierror as exc:
            self._error(f"No se pudo resolver {p['host']} ({exc}).")
            return False
        except Exception as exc:  # noqa: BLE001 — el diagnóstico informa cualquier falla, no la propaga
            self._error(f"No se pudo abrir la conexión: {type(exc).__name__}: {exc}")
            return False

        self._ok("Conexión abierta y autenticada.")
        smtp = getattr(conexion, "connection", None)
        features = getattr(smtp, "esmtp_features", None) or {}
        if "auth" in features:
            self._ok(f"Mecanismos de autenticación ofrecidos: {features['auth'].strip()}")
        conexion.close()
        return True

    def _paso_plantillas(self, dominio):
        """Renderiza los dos correos del sistema sin enviarlos."""
        self._titulo("3. Armado de los correos")
        protocolo = "http" if dominio.startswith("localhost") or dominio.startswith("127.") else "https"
        contexto = {
            "user": self._usuario_de_prueba(),
            "password_provisoria": "PRUEBA-NO-VALIDA",  # nosec B105 - texto ficticio para renderizar una plantilla
            "rol": "Rol de prueba",
            "protocol": protocolo,
            "domain": dominio,
            "enlace_login": f"{protocolo}://{dominio}{reverse('users:login')}",
            # De muestra: el enlace del correo de recupero se arma con un token real
            # recién cuando alguien lo pide desde la pantalla de ingreso.
            "uid": "MQ",
            "token": "prueba-000000",  # nosec B105 - token ficticio, no se usa para autenticación
            **contexto_pie(),
        }

        for nombre, plantillas in (
            ("alta de usuario", ("credenciales_usuario.html", "credenciales_usuario.txt")),
            ("recupero de contraseña", ("recupero_contrasena.html", "recupero_contrasena.txt")),
        ):
            for plantilla in plantillas:
                try:
                    render_to_string(f"user/email/{plantilla}", contexto)
                except Exception as exc:  # noqa: BLE001
                    self._error(f"{nombre}: no se pudo armar {plantilla} — {type(exc).__name__}: {exc}")
                    return False
            self._ok(f"{nombre}: se arma bien (HTML y texto).")

        self._ok(f"Los enlaces y el logo apuntan a {protocolo}://{dominio}")
        if dominio.startswith("localhost") or dominio.startswith("127."):
            self._aviso(
                "DOMINIO es local: los enlaces y el logo del correo no van a funcionar fuera de esta máquina. "
                "En test y producción tiene que ser el dominio público."
            )
        return True

    def _paso_envio(self, destinatario, dominio):
        self._titulo(f"4. Envío real a {destinatario}")
        protocolo = "http" if dominio.startswith("localhost") or dominio.startswith("127.") else "https"
        contexto = {
            "user": self._usuario_de_prueba(),
            "password_provisoria": "PRUEBA-NO-VALIDA",  # nosec B105 - texto ficticio para renderizar una plantilla
            "rol": "Rol de prueba",
            "protocol": protocolo,
            "domain": dominio,
            "enlace_login": f"{protocolo}://{dominio}{reverse('users:login')}",
            **contexto_pie(),
        }
        asunto = f"{settings.EMAIL_ASUNTO_PREFIJO}[PRUEBA] Tu usuario de DATAÑACH fue creado"
        cuerpo = render_to_string("user/email/credenciales_usuario.txt", contexto)
        html = render_to_string("user/email/credenciales_usuario.html", contexto)

        mensaje = EmailMultiAlternatives(asunto, cuerpo, settings.DEFAULT_FROM_EMAIL, [destinatario])
        mensaje.attach_alternative(html, "text/html")
        try:
            enviados = mensaje.send(fail_silently=False)
        except Exception as exc:  # noqa: BLE001
            self._error(f"El servidor aceptó la conexión pero rechazó el mensaje: {type(exc).__name__}: {exc}")
            return

        if not enviados:
            self._error("El backend informó 0 mensajes enviados.")
            return

        self._ok(f'Mensaje entregado al servidor. Asunto: "{asunto}"')
        self.stdout.write(
            "       Revisá la casilla, y también correo no deseado: un dominio que recién empieza "
            "a enviar suele caer ahí las primeras veces."
        )
        self.stdout.write("       El usuario y la clave del mensaje son de prueba y no habilitan ningún acceso.")

    def _paso_envio_masivo(self, destinatario):
        """Un correo de texto por el canal de las campañas, con su remitente."""
        self._titulo(f"3. Envío real a {destinatario} por el canal masivo")
        asunto = f"{settings.EMAIL_ASUNTO_PREFIJO}[PRUEBA] Diagnóstico del correo masivo de DATAÑACH"
        cuerpo = (
            "Este correo lo mandó el diagnóstico del canal masivo de DATAÑACH (las campañas de "
            "Notificaciones). Si llegó, el servidor tiene salida al servicio de correo masivo.\n"
        )
        mensaje = EmailMessage(
            asunto,
            cuerpo,
            canal_campanas.remitente_masivo(),
            [destinatario],
            connection=canal_campanas.conexion_masiva(),
        )
        try:
            enviados = mensaje.send(fail_silently=False)
        except Exception as exc:  # noqa: BLE001
            self._error(f"El servidor aceptó la conexión pero rechazó el mensaje: {type(exc).__name__}: {exc}")
            self.stdout.write(
                "       Con SES, lo habitual es un remitente sin verificar o, en sandbox, un destino sin verificar."
            )
            return
        if not enviados:
            self._error("El backend informó 0 mensajes enviados.")
            return
        self._ok(f'Mensaje entregado al servicio masivo. Asunto: "{asunto}"')
        self.stdout.write("       Revisá la casilla, y también correo no deseado.")

    # -- Auxiliares -----------------------------------------------------------

    @staticmethod
    def _usuario_de_prueba():
        """Usuario sin guardar: el diagnóstico no escribe en la base."""
        return User(username="usuario.de.prueba", first_name="Prueba", email="prueba@example.com")

    @staticmethod
    def _texto(valor):
        return valor.decode("utf-8", "replace") if isinstance(valor, bytes) else valor

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
                self.style.ERROR(f"Diagnóstico con {len(self._fallas)} falla(s). El envío de correo no está operativo.")
            )
            # Código de salida != 0 para poder usarlo como gate de despliegue.
            raise SystemExit(1)
        self.stdout.write(self.style.SUCCESS("Diagnóstico sin fallas: el envío de correo está operativo."))
