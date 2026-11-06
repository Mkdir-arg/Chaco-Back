"""Da de alta de oficio, y APROBADAS, a personas que ya son beneficiarias.

Lee un CSV (``dni, sexo, apellido, nombres``) y, por cada persona, crea el caso
en el relevamiento público indicado, vincula o crea su legajo y lo deja
``APROBADO``. **No consulta SIIS, no da de alta en SIIS y no manda correos**: son
personas que ya figuran allá. Sí consulta Personas para acreditar la identidad;
quien no valida queda ``ENVIADO`` para que lo revise una persona.

Corre en seco por defecto: sin ``--aplicar`` no escribe nada. Es idempotente: una
corrida cortada se retoma sin duplicar (ver ``programas.services.alta_de_oficio``).

    python manage.py inscribir_de_oficio --token <uuid> --archivo padron.csv --usuario pm
    python manage.py inscribir_de_oficio --token <uuid> --archivo padron.csv --usuario pm --consultar-personas
    python manage.py inscribir_de_oficio --relevamiento 12 --archivo padron.csv --usuario pm \\
        --aplicar --informe informe.csv

La salida por pantalla son solo conteos y progreso: nunca nombres. El detalle por
fila (DNI, resultado, número de caso, id de legajo, origen) va al ``--informe``.
"""

import csv
import time
import uuid
from collections import Counter

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from programas.models import Relevamiento
from programas.services import alta_de_oficio as alta
from programas.services.becas import relevamiento_publico_por_token

PROGRESO_CADA = 100


class Command(BaseCommand):
    help = "Da de alta de oficio (APROBADO, sin SIIS ni correos) a beneficiarias vigentes desde un CSV."

    def add_arguments(self, parser):
        parser.add_argument("--token", help="Token (uuid) del link público del relevamiento.")
        parser.add_argument("--relevamiento", type=int, help="Id del relevamiento público.")
        parser.add_argument("--archivo", required=True, help="CSV con encabezados dni, sexo, apellido, nombres.")
        parser.add_argument("--usuario", required=True, help="Username que queda en created_by y en la traza.")
        parser.add_argument("--aplicar", action="store_true", help="Escribe. Sin esto no se escribe nada.")
        parser.add_argument(
            "--consultar-personas",
            action="store_true",
            help="En seco, también consulta Personas para informar cuántas validarían.",
        )
        parser.add_argument("--pausa", type=float, default=0.2, help="Segundos entre consultas a Personas.")
        parser.add_argument(
            "--max-errores",
            type=int,
            default=10,
            help="Errores técnicos seguidos de Personas antes de frenar.",
        )
        parser.add_argument("--informe", help="Ruta del CSV de informe (obligatorio con --aplicar).")

    def handle(self, *args, **opciones):
        aplicar = opciones["aplicar"]
        if aplicar and not opciones["informe"]:
            raise CommandError("--informe es obligatorio con --aplicar.")
        relevamiento = self._relevamiento(opciones["token"], opciones["relevamiento"])
        usuario = self._usuario(opciones["usuario"])
        try:
            filas = alta.preparar_filas(alta.leer_filas(opciones["archivo"]))
        except alta.ArchivoInvalido as error:
            raise CommandError(str(error)) from error

        servicio = alta.AltaDeOficio(relevamiento, usuario)
        validas = [f for f in filas if f["previo"] is None]
        self.stdout.write(
            f"Relevamiento {relevamiento.pk} ({relevamiento.convocatoria.nombre}): "
            f"{len(filas)} filas, {len(validas)} para procesar."
        )
        problema = servicio.verificar_cupo(filas)
        if problema:
            raise CommandError(f"El cupo no alcanza: {problema}. No se procesó nada.")

        if aplicar:
            resultados = self._aplicar(servicio, filas, opciones)
        else:
            resultados = self._en_seco(servicio, filas, opciones)
        if aplicar:
            self._escribir_informe(opciones["informe"], resultados)
        self._resumen(resultados, aplicar)

    # -- entradas ------------------------------------------------------------
    def _relevamiento(self, token, pk):
        if bool(token) == bool(pk):
            raise CommandError("Indicá --token o --relevamiento (uno solo).")
        if token:
            try:
                token = uuid.UUID(token)
            except ValueError as error:
                raise CommandError("--token no es un uuid válido.") from error
            relevamiento = relevamiento_publico_por_token(token).select_related("convocatoria__segmento").first()
        else:
            relevamiento = (
                Relevamiento.objects.filter(pk=pk, tipo=Relevamiento.Tipo.PUBLICO)
                .select_related("convocatoria__segmento")
                .first()
            )
        if relevamiento is None:
            raise CommandError("No existe un relevamiento público con ese token o id.")
        if not relevamiento.token_publico:
            raise CommandError("El relevamiento no tiene token público.")
        return relevamiento

    @staticmethod
    def _usuario(username):
        try:
            return get_user_model().objects.get(username=username)
        except get_user_model().DoesNotExist as error:
            raise CommandError(f"No existe el usuario '{username}'.") from error

    # -- corridas ------------------------------------------------------------
    def _en_seco(self, servicio, filas, opciones):
        """No escribe: valida archivo, duplicados y cupo; con ``--consultar-personas``
        suma cuántas validarían."""
        resultados = []
        validarian = no_validarian = 0
        consultas_seguidas = 0
        for numero, fila in enumerate(filas, start=1):
            if fila["previo"] is not None:
                resultados.append(fila["previo"])
            elif opciones["consultar_personas"]:
                resultado, validaria = servicio.consultar(fila)
                if resultado is not None:
                    resultados.append(resultado)
                    consultas_seguidas = consultas_seguidas + 1 if resultado.error_tecnico else 0
                    if consultas_seguidas >= opciones["max_errores"]:
                        self._frenar(opciones["max_errores"])
                        break
                else:
                    consultas_seguidas = 0
                    validarian += bool(validaria)
                    no_validarian += not validaria
                    resultados.append(alta.ResultadoFila(fila["dni"], "pendiente"))
                if opciones["pausa"]:
                    time.sleep(opciones["pausa"])
            else:
                previo, _existente = servicio.estado_previo(fila["dni"])
                resultados.append(previo or alta.ResultadoFila(fila["dni"], "pendiente"))
            if numero % PROGRESO_CADA == 0:
                self.stdout.write(f"  {numero}/{len(filas)} filas revisadas")
        if opciones["consultar_personas"]:
            self.stdout.write(f"Validarían en Personas: {validarian}. No validarían: {no_validarian}.")
        return resultados

    def _aplicar(self, servicio, filas, opciones):
        resultados = []
        seguidos = 0
        for numero, fila in enumerate(filas, start=1):
            resultado = fila["previo"] or servicio.procesar(fila)
            resultados.append(resultado)
            seguidos = seguidos + 1 if resultado.error_tecnico else 0
            if numero % PROGRESO_CADA == 0:
                self.stdout.write(f"  {numero}/{len(filas)} filas procesadas")
            if seguidos >= opciones["max_errores"]:
                self._frenar(opciones["max_errores"])
                break
            if resultado.consulto_personas and opciones["pausa"]:
                time.sleep(opciones["pausa"])
        return resultados

    def _frenar(self, max_errores):
        self.stderr.write(
            self.style.ERROR(
                f"Frenado: {max_errores} errores técnicos seguidos de Personas. "
                "Lo ya procesado quedó; volvé a correr el comando para retomar."
            )
        )

    # -- salida ----------------------------------------------------------------
    @staticmethod
    def _escribir_informe(ruta, resultados):
        with open(ruta, "w", newline="", encoding="utf-8-sig") as archivo:
            escritor = csv.writer(archivo)
            escritor.writerow(["dni", "resultado", "numero_formulario", "ciudadano_id", "origen", "detalle"])
            for r in resultados:
                escritor.writerow([r.dni, r.resultado, r.numero, r.ciudadano_id, r.origen, r.detalle])

    def _resumen(self, resultados, aplicar):
        conteo = Counter(r.resultado for r in resultados)
        self.stdout.write("Resumen" + ("" if aplicar else " (EN SECO: no se escribió nada)") + ":")
        for clave in (*alta.RESULTADOS, "pendiente"):
            if conteo.get(clave):
                self.stdout.write(f"  {clave}: {conteo[clave]}")
        if not aplicar:
            self.stdout.write("Para escribir, sumá --aplicar (y --informe <ruta.csv>).")
