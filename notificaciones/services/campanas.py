"""Alta, edición, borrado y duplicado de campañas (RF-007-03 a RF-007-06, RF-007-13, RF-007-19).

La validación de los archivos vive en el form (``CampanaForm``), que ya llama a
:func:`notificaciones.services.lectura_excel.parsear_destinatarios` y a
:func:`notificaciones.services.html.procesar`. Acá se escribe: la campaña, un
``Destinatario`` por correo válido y un ``Descartado`` por fila que no se envía, todo en
una transacción.

Los archivos: el storage no tiene transacción, así que la escritura va decorada con
``core.archivos.archivos_atomicos`` (si la base vuelve atrás, el archivo recién escrito
se borra) y el archivo **reemplazado** se borra recién con ``on_commit`` (si se borrara
antes y la base volviera atrás, la fila quedaría nombrando un archivo que ya no está).
"""

from __future__ import annotations

import logging
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction

from core.archivos import anotar_archivo_escrito, archivos_atomicos
from notificaciones.models import Campana, Descartado, Destinatario
from notificaciones.services import html as servicio_html
from notificaciones.services.lectura_excel import parsear_destinatarios

logger = logging.getLogger(__name__)

LOTE_BULK = 1000
PREFIJO_COPIA = "Copia de "


class TransicionInvalida(Exception):
    """La acción no corresponde al estado actual de la campaña (RN-007-01, RN-007-10)."""


def _nombre_original(archivo):
    return Path(getattr(archivo, "name", "") or "").name[:255]


def _borrar_tras_commit(storage, nombre):
    """Borra un archivo reemplazado o huérfano recién cuando la base confirmó."""
    if not nombre:
        return

    def borrar():
        try:
            storage.delete(nombre)
        except Exception:  # best effort: un storage caído no puede tapar la operación
            logger.exception("No se pudo borrar el archivo %s de una campaña", nombre)

    transaction.on_commit(borrar)


def _guardar_lista(campana, lectura):
    """Reemplaza destinatarios y descartados por lo que dejó la lectura del Excel."""
    campana.destinatarios.all().delete()
    campana.descartados.all().delete()
    Destinatario.objects.bulk_create(
        [Destinatario(campana=campana, email=email, fila_excel=fila) for fila, email in lectura.validos],
        batch_size=LOTE_BULK,
    )
    Descartado.objects.bulk_create(
        [
            Descartado(campana=campana, fila_excel=fila, valor=valor, motivo=motivo)
            for fila, valor, motivo in lectura.descartados
        ],
        batch_size=LOTE_BULK,
    )
    campana.leidas = lectura.leidas
    campana.total = len(lectura.validos)
    campana.invalidos = lectura.invalidos
    campana.duplicados = lectura.duplicados
    campana.enviados = 0
    campana.fallidos = 0


def _aplicar_html(campana, datos_html):
    for campo, valor in datos_html.items():
        setattr(campana, campo, valor)


def _asignar_archivo(campana, campo, archivo):
    """Pone el archivo en el campo; el nombre opaco lo arma ``upload_to``."""
    setattr(campana, campo, archivo)


def _anotar_escritos(campana, asignados):
    for campo, asignado in asignados.items():
        anotar_archivo_escrito(getattr(campana, campo), asignado=asignado)


@archivos_atomicos
@transaction.atomic
def crear_campana(*, nombre, asunto, archivo_excel, archivo_html, lectura, datos_html, usuario):
    """Crea la campaña en «A enviar» con su lista ya leída y su HTML ya saneado."""
    campana = Campana(
        nombre=nombre,
        asunto=asunto,
        nombre_excel=_nombre_original(archivo_excel),
        nombre_html=_nombre_original(archivo_html),
        creada_por=usuario,
        estado=Campana.Estado.A_ENVIAR,
    )
    _asignar_archivo(campana, "archivo_excel", archivo_excel)
    _asignar_archivo(campana, "archivo_html", archivo_html)
    _aplicar_html(campana, datos_html)
    campana.save()
    _anotar_escritos(campana, {"archivo_excel": archivo_excel, "archivo_html": archivo_html})
    _guardar_lista(campana, lectura)
    campana.save(update_fields=["leidas", "total", "invalidos", "duplicados", "enviados", "fallidos", "modificado"])
    return campana


@archivos_atomicos
@transaction.atomic
def editar_campana(campana, *, nombre, asunto, archivo_excel=None, archivo_html=None, lectura=None, datos_html=None):
    """Cambia nombre y asunto y, si vinieron, reemplaza el Excel (recalcula la lista) o el HTML.

    Solo en «A enviar»: se relee la fila con candado para que un «Enviar» que llegó en el
    medio no deje una campaña enviándose con la lista cambiada abajo.
    """
    actual = Campana.objects.select_for_update().get(pk=campana.pk)
    if not actual.editable:
        raise TransicionInvalida("Solo se puede editar una campaña que está «A enviar».")
    actual.nombre = nombre
    actual.asunto = asunto
    asignados = {}
    if archivo_excel is not None:
        _borrar_tras_commit(actual.archivo_excel.storage, actual.archivo_excel.name)
        _asignar_archivo(actual, "archivo_excel", archivo_excel)
        actual.nombre_excel = _nombre_original(archivo_excel)
        asignados["archivo_excel"] = archivo_excel
    if archivo_html is not None:
        _borrar_tras_commit(actual.archivo_html.storage, actual.archivo_html.name)
        _asignar_archivo(actual, "archivo_html", archivo_html)
        actual.nombre_html = _nombre_original(archivo_html)
        _aplicar_html(actual, datos_html)
        asignados["archivo_html"] = archivo_html
    actual.save()
    _anotar_escritos(actual, asignados)
    if archivo_excel is not None:
        _guardar_lista(actual, lectura)
        actual.save(update_fields=["leidas", "total", "invalidos", "duplicados", "enviados", "fallidos", "modificado"])
    return actual


@transaction.atomic
def eliminar_campana(campana):
    """Borra la campaña, sus destinatarios y sus archivos. Solo en «A enviar»."""
    actual = Campana.objects.select_for_update().get(pk=campana.pk)
    if not actual.editable:
        raise TransicionInvalida("Una campaña enviada o enviándose no se puede eliminar.")
    for campo in ("archivo_excel", "archivo_html"):
        archivo = getattr(actual, campo)
        _borrar_tras_commit(archivo.storage, archivo.name)
    actual.delete()


def _copia_de(campo):
    """Los bytes de un archivo guardado, como archivo nuevo con su nombre original."""
    try:
        campo.open("rb")
        try:
            contenido = campo.read()
        finally:
            campo.close()
    except (FileNotFoundError, OSError) as exc:
        raise ValidationError("No se encontró el archivo original de la campaña: no se puede duplicar.") from exc
    return contenido


def duplicar_campana(campana, *, usuario):
    """Copia en «A enviar» con «Copia de <nombre>», el mismo asunto, HTML y lista (RF-007-19).

    Se copian los **dos archivos** y se vuelve a leer el Excel y a sanear el HTML, igual
    que en el alta: una copia de una campaña vieja no hereda una lista calculada con
    reglas que pudieron cambiar. La original no se toca.
    """
    excel = ContentFile(_copia_de(campana.archivo_excel), name=campana.nombre_excel or "destinatarios.xlsx")
    html = ContentFile(_copia_de(campana.archivo_html), name=campana.nombre_html or "correo.html")
    lectura = parsear_destinatarios(excel)
    datos_html = servicio_html.procesar(html)
    nombre = f"{PREFIJO_COPIA}{campana.nombre}"[: Campana._meta.get_field("nombre").max_length]
    return crear_campana(
        nombre=nombre,
        asunto=campana.asunto,
        archivo_excel=excel,
        archivo_html=html,
        lectura=lectura,
        datos_html=datos_html,
        usuario=usuario,
    )
