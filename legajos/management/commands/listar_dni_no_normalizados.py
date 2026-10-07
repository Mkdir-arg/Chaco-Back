"""G1c-08 / P-17 · Qué DNI están fuera de la regla única, en Legajos y en Usuarios.

Desde este cambio ninguna puerta deja entrar un `12.345.678` ni un documento de 6 o 9
dígitos, pero las fichas que ya están cargadas así siguen ahí. Son dos problemas
distintos y el comando cuenta los dos por separado:

* **Con separadores** (`12.345.678`): cada una puede tener una **gemela** normalizada —
  la misma persona partida en dos legajos, que Becas (que normaliza) nunca encuentra—.
* **Con un largo fuera de la regla** (`core.dni.LARGOS_DNI_VALIDOS`): son las que este
  PR frena. Un caso de Becas cuyo ciudadano tenga uno de estos DNI deja de informarse a
  SIIS y queda con «El caso no tiene un ciudadano con DNI válido». Es el número que hay
  que mirar **antes del deploy**.

Mira las **dos** tablas que guardan un DNI: `legajos_ciudadano` —la persona atendida— y
`users_profile` —el usuario de backoffice, la novena puerta de RED-48—. Son dos
poblaciones distintas y el impacto también: un ciudadano fuera de la regla frena el alta
a SIIS de su caso; un usuario fuera de la regla no puede corregir su propio DNI sin que
lo haga quien administra. Por eso el resumen las cuenta por separado.

El comando es de **solo lectura a propósito**: unir dos legajos es mover adjuntos,
alertas, historial, inscripciones y casos de Becas, y cuál de los dos sobrevive no lo
puede decidir un script. Lo que hace es dejar la lista para que la revise el área, que
es lo que pide P-17 del plan de la auditoría.

La salida de pantalla **enmascara el documento** —alcanza para reconocer la ficha y el
id para abrirla—; el CSV lo trae entero, porque es el insumo con el que se cruzan las
fichas, y se maneja como cualquier otro export con datos personales.

    manage.py listar_dni_no_normalizados            # tabla legible, documento enmascarado
    manage.py listar_dni_no_normalizados --csv      # para pegar en una planilla
"""

import csv

from django.core.management.base import BaseCommand

from core.dni import LARGOS_DNI_VALIDOS, dni_valido, normalizar_dni
from legajos.models import Ciudadano
from users.models import Profile

COLUMNAS = ("origen", "id", "dni_guardado", "dni_normalizado", "apellido", "nombre", "colisiona_con", "motivo")

MOTIVO_SEPARADORES = "separadores"
MOTIVO_LARGO = "largo"

ORIGEN_CIUDADANO = "ciudadano"
ORIGEN_USUARIO = "usuario"


def enmascarar(dni):
    """`12.345.678` → `12******78`: se reconoce la ficha sin imprimir el documento.

    Se conserva el largo del valor guardado —y por eso los asteriscos tapan también los
    separadores—: lo que hace falta para reconocerla es el principio, el final y cuánto
    mide; el documento entero está en el CSV.
    """
    texto = str(dni or "")
    if len(texto) <= 4:
        return "*" * len(texto)
    return f"{texto[:2]}{'*' * (len(texto) - 4)}{texto[-2:]}"


def motivos(guardado):
    """Por qué esta ficha está fuera de la regla: puede ser por los dos."""
    limpio = normalizar_dni(guardado)
    encontrados = []
    if limpio != str(guardado or ""):
        encontrados.append(MOTIVO_SEPARADORES)
    if not dni_valido(limpio):
        encontrados.append(MOTIVO_LARGO)
    return encontrados


def _candidatos(queryset, campos):
    """Las filas con un DNI fuera de la regla, decidido por `motivos()` en Python.

    **Sin expresión regular, a propósito.** El descarte barato por largo
    (`Length("dni")`) deja afuera lo obvio, pero no alcanza: `1.234.56` mide 8 y está
    mal igual. Lo que falta —«tiene algo que no es un dígito»— no se puede preguntar en
    el ORM sin un `dni__regex`, y un regex con el largo interpolado esquivaría el
    ratchet de RED-48 (`core/tests/test_regla_dni.py`), que es justo la guardia que
    impide que vuelva a haber dos reglas de DNI. Así que la decisión es una sola,
    `core.dni`, aplicada fila por fila.

    El costo es un recorrido completo de la tabla. Es aceptable: el comando es manual,
    de solo lectura, y se corre una vez antes del deploy —no está en ninguna pantalla—.
    """
    for fila in queryset.order_by("dni").values(*campos).iterator():
        if motivos(fila["dni"]):
            yield fila


class Command(BaseCommand):
    help = "Lista los DNI de ciudadanos y usuarios que están fuera de la regla única, y sus duplicados."

    def add_arguments(self, parser):
        parser.add_argument("--csv", action="store_true", help="Salida en CSV, con el documento completo.")

    def handle(self, *args, **opciones):
        filas = [*self._ciudadanos(), *self._usuarios()]
        if not filas:
            self.stdout.write(self.style.SUCCESS("Ningún DNI fuera de la regla única."))
            return

        self._marcar_colisiones(filas)

        if opciones["csv"]:
            escritor = csv.DictWriter(self.stdout, fieldnames=COLUMNAS, lineterminator="\n")
            escritor.writeheader()
            escritor.writerows(filas)
            return

        for fila in filas:
            marca = f" -> colisiona con {fila['origen']} {fila['colisiona_con']}" if fila["colisiona_con"] else ""
            self.stdout.write(
                f"{fila['origen']}\t{fila['id']}\t{enmascarar(fila['dni_guardado'])}\t[{fila['motivo']}]\t"
                f"{fila['apellido']}, {fila['nombre']}{marca}"
            )
        self.stdout.write("")
        self._resumen(filas)

    # -- Las dos poblaciones ------------------------------------------------

    def _ciudadanos(self):
        campos = ("id", "dni", "apellido", "nombre")
        return [
            self._fila(ORIGEN_CIUDADANO, fila["id"], fila["dni"], fila["apellido"], fila["nombre"])
            for fila in _candidatos(Ciudadano.objects.all(), campos)
        ]

    def _usuarios(self):
        campos = ("id", "dni", "user__last_name", "user__first_name", "user__username")
        filas = []
        for fila in _candidatos(Profile.objects.exclude(dni=None), campos):
            apellido = fila["user__last_name"] or fila["user__username"]
            filas.append(self._fila(ORIGEN_USUARIO, fila["id"], fila["dni"], apellido, fila["user__first_name"] or ""))
        return filas

    @staticmethod
    def _fila(origen, identificador, guardado, apellido, nombre):
        return {
            "origen": origen,
            "id": identificador,
            "dni_guardado": guardado,
            "dni_normalizado": normalizar_dni(guardado),
            "apellido": apellido,
            "nombre": nombre,
            "colisiona_con": "",
            "motivo": "+".join(motivos(guardado)),
        }

    @staticmethod
    def _marcar_colisiones(filas):
        """La gemela normalizada, buscada en la **misma** tabla que la fila."""
        por_origen = {
            ORIGEN_CIUDADANO: Ciudadano.objects,
            ORIGEN_USUARIO: Profile.objects,
        }
        for origen, manager in por_origen.items():
            normalizados = {f["dni_normalizado"] for f in filas if f["origen"] == origen} - {""}
            if not normalizados:
                continue
            gemelos = dict(manager.filter(dni__in=normalizados).values_list("dni", "id"))
            for fila in filas:
                if fila["origen"] != origen:
                    continue
                gemelo = gemelos.get(fila["dni_normalizado"])
                if gemelo and gemelo != fila["id"]:
                    fila["colisiona_con"] = gemelo

    def _resumen(self, filas):
        for origen, etiqueta in ((ORIGEN_CIUDADANO, "ciudadano(s)"), (ORIGEN_USUARIO, "usuario(s) de backoffice")):
            del_origen = [fila for fila in filas if fila["origen"] == origen]
            if not del_origen:
                continue
            con_separadores = sum(1 for fila in del_origen if MOTIVO_SEPARADORES in fila["motivo"])
            con_largo = sum(1 for fila in del_origen if MOTIVO_LARGO in fila["motivo"])
            colisiones = sum(1 for fila in del_origen if fila["colisiona_con"])
            self.stdout.write(
                self.style.WARNING(
                    f"{len(del_origen)} {etiqueta} fuera de la regla única: {con_separadores} con separadores "
                    f"({colisiones} con una ficha normalizada ya existente) y "
                    f"{con_largo} con un largo fuera de {LARGOS_DNI_VALIDOS}."
                )
            )
        self.stdout.write(
            self.style.WARNING(
                "Los que tienen un largo fuera de la regla son los que dejan de informarse a SIIS (ciudadanos) "
                "y los que no pueden corregir su propio DNI (usuarios). "
                "La unificación es manual (P-17): este comando no toca nada."
            )
        )
