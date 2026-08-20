"""Diagnóstico del envío de correo, para verificar un entorno recién configurado.

Recorre el mismo camino que usa la aplicación y va informando dónde se corta.
Sirve para separar las causas que desde el backoffice se ven todas iguales —el
aviso "no se pudo enviar el correo"—: variables sin cargar, DNS, egress cerrado
al 587, credenciales rechazadas, o remitente distinto del que autentica.

    python manage.py diagnosticar_correo
    python manage.py diagnosticar_correo otra.casilla@dominio
    python manage.py diagnosticar_correo --solo-config
    python manage.py diagnosticar_correo --sin-enviar

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
from django.core.mail import EmailMultiAlternatives, get_connection
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.urls import reverse

from users.services.correo import contexto_pie

DESTINATARIO_POR_DEFECTO = "farinamatias00@gmail.com"

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
            default=DESTINATARIO_POR_DEFECTO,
            help=f"Casilla que recibe la prueba. Por defecto {DESTINATARIO_POR_DEFECTO}.",
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

        if not self._paso_plantillas(dominio):
            self._cerrar()
            return

        if not options["sin_enviar"]:
            self._paso_envio(options["destinatario"], dominio)

        self._cerrar()

    # -- Pasos ----------------------------------------------------------------

    def _paso_configuracion(self):
        self._titulo("1. Configuración del entorno")

        backend = settings.EMAIL_BACKEND.rsplit(".", 2)[-2]
        if not settings.EMAIL_HOST:
            self._error(
                "EMAIL_HOST vacía: el backend es el de consola, los correos se escriben en el log "
                "y no salen del servidor. Es el modo de desarrollo."
            )
            return
        self._ok(f"EMAIL_HOST: {settings.EMAIL_HOST} (backend {backend})")

        try:
            ip = socket.gethostbyname(settings.EMAIL_HOST)
            self._ok(f"DNS: {settings.EMAIL_HOST} resuelve a {ip}")
        except socket.gaierror as exc:
            self._error(f"DNS: {settings.EMAIL_HOST} no resuelve ({exc}). Revisá el nombre del servidor.")

        self._ok(f"EMAIL_PORT: {settings.EMAIL_PORT}")

        if not settings.EMAIL_HOST_USER:
            self._error("EMAIL_HOST_USER vacía: sin usuario no hay autenticación y el servidor rechaza el envío.")
        else:
            self._ok(f"EMAIL_HOST_USER: {settings.EMAIL_HOST_USER}")

        if not settings.EMAIL_HOST_PASSWORD:
            self._error("EMAIL_HOST_PASSWORD vacía.")
        else:
            self._ok(f"EMAIL_HOST_PASSWORD: presente ({len(settings.EMAIL_HOST_PASSWORD)} caracteres)")

        usa_ssl = getattr(settings, "EMAIL_USE_SSL", False)
        if settings.EMAIL_USE_TLS and usa_ssl:
            self._error("EMAIL_USE_TLS y EMAIL_USE_SSL prendidas a la vez: Django rechaza esa combinación.")
        elif settings.EMAIL_USE_TLS:
            self._ok("EMAIL_USE_TLS: True (STARTTLS, lo que corresponde al 587)")
        elif usa_ssl:
            self._aviso("EMAIL_USE_SSL: True. Es el modo del 465; en el 587 va EMAIL_USE_TLS.")
        else:
            self._aviso("Sin TLS ni SSL: la contraseña viajaría en claro. Casi ningún servidor lo acepta.")

        self._ok(f"EMAIL_TIMEOUT: {settings.EMAIL_TIMEOUT}s")

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

    def _paso_conexion(self):
        """Abre la conexión real sin mandar nada: separa red, TLS y credenciales."""
        self._titulo(f"2. Conexión y autenticación ({settings.EMAIL_HOST}:{settings.EMAIL_PORT})")
        conexion = get_connection()
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
                f"Timeout a los {settings.EMAIL_TIMEOUT}s. El puerto {settings.EMAIL_PORT} no responde: "
                "lo más común es que la salida esté filtrada. Hay que habilitar el egress."
            )
            return False
        except ConnectionRefusedError:
            self._error(f"Conexión rechazada en el puerto {settings.EMAIL_PORT}: nada escuchando o firewall.")
            return False
        except socket.gaierror as exc:
            self._error(f"No se pudo resolver {settings.EMAIL_HOST} ({exc}).")
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
