"""Alta masiva de usuarios desde un CSV, con los grupos de un usuario de referencia (G2-05).

Qué hacía mal y por qué importa: `--reference-user-id` traía **el id 368 escrito
en el código**, que en otra base es cualquiera —o nadie—; a todo usuario del CSV
le hacía `groups.set(...)`, así que una fila con el nombre de alguien que ya
trabaja le reemplazaba los roles, el email y **la contraseña** sin preguntar, sin
ensayo, sin `validate_password`, sin `transaction.atomic` y sin marcar la clave
como provisoria. Una fila rota a mitad del archivo dejaba la mitad aplicada.

El contrato nuevo es el del resto de los comandos que escriben
(`ComandoSiisBase`): **en seco por defecto**, escritura con `--aplicar`, y lo
destructivo —pisar una cuenta que ya existe— detrás de `--actualizar --motivo`,
que deja rastro en el log. La planificación y la validación de claves corren
igual en el ensayo: el objetivo es que lo que falle, falle **antes** de escribir.

La salida nombra usuarios y nada más: ni la contraseña del CSV ni el correo de
nadie van a quedar en el log de una terminal compartida.
"""

import csv
import logging
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core import rbac
from users.models import Profile

logger = logging.getLogger(__name__)

COLUMNAS_REQUERIDAS = {"Usuario", "Email", "Nombre completo", "Apellido", "Contraseña"}
#: Estaba entre las obligatorias y **no la leía nadie**: los grupos salen del
#: usuario de referencia. Exigir una columna que se ignora hace creer que asigna
#: el rol; se acepta si viene, con aviso, y ya no se pide.
COLUMNA_IGNORADA = "Rol"

AYUDA_REFERENCIA = (
    "ID del usuario cuyos grupos se replican. Obligatorio y sin default: el 368 que traía escrito "
    "es otra persona en cada base."
)
AYUDA_APLICAR = "Escribe de verdad. Sin esto solo informa qué haría."
AYUDA_ACTUALIZAR = (
    "Toca también a los usuarios que ya existen: les reemplaza grupos, email, nombre y contraseña. Exige --motivo."
)
AYUDA_MOTIVO = "Por qué se pisan cuentas existentes. Obligatorio con --actualizar; queda en el log."

FALTA_MOTIVO = (
    "--actualizar necesita --motivo: le reemplaza los grupos y la contraseña a gente que ya está "
    "trabajando, así que tiene que quedar escrito quién lo hizo y por qué."
)
YA_EXISTE = "«{usuario}» ya existe: no se toca. Con --actualizar --motivo «...» se le replican los grupos."


class Command(BaseCommand):
    help = "Crea usuarios a partir de un CSV y replica los grupos del usuario de referencia."

    def add_arguments(self, parser):
        parser.add_argument("csv_path", type=str, help="Ruta al archivo CSV con las columnas requeridas.")
        parser.add_argument("--reference-user-id", type=int, required=True, help=AYUDA_REFERENCIA)
        parser.add_argument("--aplicar", action="store_true", help=AYUDA_APLICAR)
        parser.add_argument("--actualizar", action="store_true", help=AYUDA_ACTUALIZAR)
        parser.add_argument("--motivo", default="", help=AYUDA_MOTIVO)

    def handle(self, *args, **options):
        aplicar = options["aplicar"]
        actualizar = options["actualizar"]
        motivo = (options.get("motivo") or "").strip()

        if actualizar and not motivo:
            raise CommandError(FALTA_MOTIVO)

        csv_path = Path(options["csv_path"])
        if not csv_path.exists():
            raise CommandError(f"El archivo '{csv_path}' no existe.")

        user_model = get_user_model()
        try:
            referencia = user_model.objects.get(pk=options["reference_user_id"])
        except user_model.DoesNotExist as exc:
            raise CommandError(
                f"No se encontró el usuario de referencia con id={options['reference_user_id']}."
            ) from exc

        grupos_referencia = list(referencia.groups.all())
        self.stdout.write(f"Grupos a replicar (de «{referencia.username}»): {len(grupos_referencia)}")

        if not aplicar:
            self.stdout.write(self.style.WARNING("ENSAYO: no se escribe nada. Agregá --aplicar para hacerlo."))
        if actualizar:
            self.stdout.write(self.style.WARNING(f"--actualizar: se pisan las cuentas existentes. Motivo: {motivo}"))
            logger.warning(
                "import_users_from_csv --actualizar sobre %s (referencia: %s, motivo: %s)",
                csv_path.name,
                referencia.username,
                motivo,
            )

        plan, omitidos = self._planificar(csv_path, user_model, actualizar)

        if aplicar:
            self._aplicar(plan, grupos_referencia)

        creados = sum(1 for p in plan if p["crear"])
        self.stdout.write(
            self.style.SUCCESS(
                f"{'Proceso finalizado' if aplicar else 'Ensayo finalizado'}. "
                f"Usuarios {'creados' if aplicar else 'a crear'}: {creados}, "
                f"{'actualizados' if aplicar else 'a actualizar'}: {len(plan) - creados}, "
                f"omitidos: {len(omitidos)}."
            )
        )

    # ── Planificación (corre igual en el ensayo) ────────────────────────────

    def _planificar(self, csv_path, user_model, actualizar):
        """`([{usuario, crear, datos, clave}], [omitidos])`, o corta sin escribir nada."""
        plan, omitidos, errores = [], [], []

        with csv_path.open(newline="", encoding="utf-8-sig") as csv_file:
            reader = csv.DictReader(csv_file)
            headers = set(reader.fieldnames or [])
            faltantes = COLUMNAS_REQUERIDAS - headers
            if faltantes:
                raise CommandError(f"El CSV no contiene las columnas requeridas: {', '.join(sorted(faltantes))}")
            if COLUMNA_IGNORADA in headers:
                self.stdout.write(
                    self.style.WARNING(
                        f"La columna «{COLUMNA_IGNORADA}» se ignora: los grupos salen de --reference-user-id."
                    )
                )

            for numero, row in enumerate(reader, start=2):
                username = (row.get("Usuario") or "").strip()
                if not username:
                    self.stdout.write(self.style.WARNING(f"Fila {numero} sin 'Usuario': se omite."))
                    continue

                existente = user_model.objects.filter(username=username).first()
                if existente is not None and not actualizar:
                    self.stdout.write(self.style.WARNING(YA_EXISTE.format(usuario=username)))
                    omitidos.append(username)
                    continue

                datos = {
                    "email": (row.get("Email") or "").strip(),
                    "first_name": (row.get("Nombre completo") or "").strip(),
                    "last_name": (row.get("Apellido") or "").strip(),
                }
                clave = (row.get("Contraseña") or "").strip()
                if existente is None and not clave:
                    errores.append(f"Fila {numero} («{username}»): falta la contraseña.")
                    continue
                if clave:
                    molde = existente or user_model(username=username, **datos)
                    try:
                        validate_password(clave, molde)
                    except ValidationError as exc:
                        errores.append(f"Fila {numero} («{username}»): {' '.join(exc.messages)}")
                        continue

                plan.append({"username": username, "crear": existente is None, "datos": datos, "clave": clave})

        if errores:
            raise CommandError("El CSV tiene filas que no se pueden aplicar:\n  - " + "\n  - ".join(errores))
        return plan, omitidos

    # ── Escritura ───────────────────────────────────────────────────────────

    def _aplicar(self, plan, grupos_referencia):
        user_model = get_user_model()
        hubo_pisados = False
        programas_previos = set()

        with transaction.atomic():
            # G1b-09: el candado va antes de leer y de escribir. El lote puede pisarle
            # los roles al último administrador mientras alguien lo desactiva desde el ABM.
            rbac.tomar_candado_de_administracion()
            for item in plan:
                usuario, creado = user_model.objects.get_or_create(username=item["username"], defaults=item["datos"])
                if not creado:
                    hubo_pisados = True
                    # Qué programas administraba ANTES de que `groups.set` le reemplace
                    # los roles: el check global no alcanza, porque el sistema puede
                    # quedarse con admins y un programa concreto sin ninguno (RN-8).
                    # Es lo mismo que mira el ABM (`UsuariosAdminService`).
                    programas_previos |= rbac.programas_que_administra(usuario)
                    for campo, valor in item["datos"].items():
                        if valor:
                            setattr(usuario, campo, valor)
                if item["clave"]:
                    usuario.set_password(item["clave"])
                usuario.save()
                usuario.groups.set(grupos_referencia)
                if item["clave"]:
                    # La clave viajó en texto plano en el CSV: es provisoria y el
                    # middleware no deja operar hasta que la persona la cambie.
                    perfil, _ = Profile.objects.get_or_create(user=usuario)
                    perfil.debe_cambiar_contrasena = True
                    perfil.save(update_fields=["debe_cambiar_contrasena"])
                self.stdout.write(self.style.SUCCESS(f"«{item['username']}» {'creado' if creado else 'actualizado'}."))

            if hubo_pisados:
                # `groups.set` puede haberle quitado el rol al único que administra:
                # el sistema entero primero y después cada programa que alguno de los
                # pisados administraba. Dentro del `atomic`, así la excepción revierte
                # el lote completo en vez de dejar media planilla aplicada.
                try:
                    rbac.asegurar_admin_restante()
                    for programa in self._programas(programas_previos):
                        rbac.asegurar_admin_restante(programa=programa)
                except rbac.SinAdministradorError as exc:
                    raise CommandError(str(exc)) from exc

    @staticmethod
    def _programas(ids):
        """Los programas como objetos y no como ids: el mensaje de error lo lee una
        persona en una terminal y «el programa «3»» no le dice nada."""
        if not ids:
            return []
        from programas.models import Programa

        return list(Programa.objects.filter(pk__in=sorted(ids)).order_by("pk"))
