"""Stock de insumos por institución y edificio (análisis 010, PR 1: esquema inerte).

Tres tablas. ``SaldoStock`` es la fila que se bloquea y que dice cuánto hay; ``OperacionStock`` y
``MovimientoStock`` son el libro **inmutable** (RN-010-05): una acción de una persona y los deltas firmados que
dejó. Para cada clave ``(dispositivo, edificio, item)``:

    SaldoStock.cantidad == Σ MovimientoStock.cantidad == saldo_posterior del último movimiento

Solo escribirá estas tablas ``programas.services.stock`` (PR 2a). Este PR no trae servicios ni pantallas: el
módulo queda apagado mientras ningún ``TipoDispositivo`` tenga ``maneja_stock``.

Va en un módulo aparte para no inflar ``models/__init__.py``; las FK a modelos de ese paquete son por nombre.
No hay ``UniqueConstraint`` condicional: MySQL y MariaDB lo descartan en silencio (RN-010-19).
"""

from django.contrib.auth.models import User
from django.db import models

from core.models import TimeStamped
from legajos.models import Ciudadano
from programas.models.inmutable import LibroInmutable


class SaldoStock(TimeStamped):
    """Cuánto hay de un insumo en un edificio, para una institución (RN-010-02). Es lo que se bloquea."""

    dispositivo = models.ForeignKey(
        "programas.Dispositivo", on_delete=models.PROTECT, related_name="saldos_stock", verbose_name="Institución"
    )
    edificio = models.ForeignKey(
        "programas.Edificio", on_delete=models.PROTECT, related_name="saldos_stock", verbose_name="Edificio"
    )
    item = models.ForeignKey(
        "programas.TipoKit", on_delete=models.PROTECT, related_name="saldos_stock", verbose_name="Insumo"
    )
    # `IntegerField` y no `PositiveIntegerField` a propósito: este último ya trae su propio CHECK sin nombre
    # (en SQLite) o `unsigned` (en MySQL), y «nunca negativo» dejaría de depender de la restricción de abajo,
    # que es la que se declara, se nombra y se prueba por mutación.
    cantidad = models.IntegerField(default=0, db_default=0, verbose_name="Cantidad")
    # Para la tabla de saldo sin leer el libro.
    ultimo_movimiento_en = models.DateTimeField(null=True, blank=True, verbose_name="Último movimiento")

    class Meta:
        verbose_name = "Saldo de stock"
        verbose_name_plural = "Saldos de stock"
        ordering = ["dispositivo_id", "edificio_id", "item_id"]
        constraints = [
            models.UniqueConstraint(fields=["dispositivo", "edificio", "item"], name="saldo_stock_clave_unica"),
            # MySQL >= 8.0.16 y MariaDB >= 10.2 la hacen cumplir: es el respaldo de «nunca negativo» (RN-010-03).
            models.CheckConstraint(condition=models.Q(cantidad__gte=0), name="saldo_stock_no_negativo"),
        ]

    def __str__(self):
        return f"{self.dispositivo_id}/{self.edificio_id}/{self.item_id}: {self.cantidad}"


class OperacionStock(LibroInmutable):
    """Una acción de una persona sobre el stock (RN-010-05). No hereda ``TimeStamped``: no se modifica."""

    class Tipo(models.TextChoices):
        INGRESO_KIT = "INGRESO_KIT", "Recepción de kit"
        INGRESO_MANUAL = "INGRESO_MANUAL", "Ingreso manual"
        ENTREGA_PERSONA = "ENTREGA_PERSONA", "Entrega a una persona"
        TRASPASO = "TRASPASO", "Traspaso"
        AJUSTE = "AJUSTE", "Ajuste por conteo"

    class Origen(models.TextChoices):
        """Catálogo cerrado del ingreso manual (RN-010-08, decisión 4)."""

        DONACION = "DONACION", "Donación"
        MUNICIPIO = "MUNICIPIO", "Municipio"
        COMPRA = "COMPRA", "Compra"
        OTRO_PROGRAMA = "OTRO_PROGRAMA", "Otro programa"
        OTRO = "OTRO", "Otro"

    class MotivoAjuste(models.TextChoices):
        """Catálogo cerrado del ajuste por conteo (RN-010-12, decisión 4)."""

        INVENTARIO_INICIAL = "INVENTARIO_INICIAL", "Inventario inicial"
        CONTEO_PERIODICO = "CONTEO_PERIODICO", "Conteo periódico"
        ROTURA_VENCIMIENTO = "ROTURA_VENCIMIENTO", "Rotura o vencimiento"
        PERDIDA_ROBO = "PERDIDA_ROBO", "Pérdida o robo"
        CORRECCION_CARGA = "CORRECCION_CARGA", "Corrección de carga"
        OTRO = "OTRO", "Otro"

    tipo = models.CharField(max_length=20, choices=Tipo.choices, verbose_name="Tipo")
    # Donde ocurre; en un traspaso, el origen.
    dispositivo = models.ForeignKey(
        "programas.Dispositivo", on_delete=models.PROTECT, related_name="operaciones_stock", verbose_name="Institución"
    )
    edificio = models.ForeignKey(
        "programas.Edificio", on_delete=models.PROTECT, related_name="operaciones_stock", verbose_name="Edificio"
    )
    # Solo traspaso.
    destino_dispositivo = models.ForeignKey(
        "programas.Dispositivo",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="operaciones_stock_destino",
        verbose_name="Institución de destino",
    )
    destino_edificio = models.ForeignKey(
        "programas.Edificio",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="operaciones_stock_destino",
        verbose_name="Edificio de destino",
    )
    # Quien la hizo (en INGRESO_KIT, quien recibió).
    usuario = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="operaciones_stock", verbose_name="Responsable"
    )
    # Sin fecha retroactiva (criterio b): el momento es el de la carga.
    creado_en = models.DateTimeField(auto_now_add=True, verbose_name="Momento")
    # Solo entrega a persona.
    ciudadano = models.ForeignKey(
        Ciudadano,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="operaciones_stock",
        verbose_name="Persona",
    )
    # Solo INGRESO_KIT. UNIQUE sobre columna anulable: MySQL y MariaDB admiten varios NULL, y corta una doble
    # suma de la misma entrega (RN-010-06).
    entrega_kit = models.OneToOneField(
        "programas.EntregaKit",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="operacion_stock",
        verbose_name="Entrega de kit",
    )
    # Solo ingreso manual.
    # `default` y `db_default` de a par: sin `default`, MySQL 8 (sin RETURNING) deja un `DatabaseDefault` en memoria.
    origen = models.CharField(
        max_length=20, choices=Origen.choices, blank=True, default="", db_default="", verbose_name="Origen"
    )
    origen_detalle = models.CharField(
        max_length=120, blank=True, default="", db_default="", verbose_name="Detalle del origen"
    )
    # Número o referencia de texto, sin foto (decisión 3).
    comprobante = models.CharField(max_length=60, blank=True, default="", db_default="", verbose_name="Comprobante")
    # Solo ajuste.
    motivo = models.CharField(
        max_length=20,
        choices=MotivoAjuste.choices,
        blank=True,
        default="",
        db_default="",
        verbose_name="Motivo del ajuste",
    )
    # Detalle del ajuste u observación de la entrega.
    observacion = models.CharField(max_length=200, blank=True, default="", db_default="", verbose_name="Observación")
    # Idempotencia (RN-010-18). Único sobre columna anulable y `char(36)` en MySQL/MariaDB (programas.0145);
    # se busca con `core.db.q_uuid_en_texto`.
    uuid_cliente = models.UUIDField(null=True, blank=True, unique=True, editable=False, verbose_name="Identificador")

    class Meta(LibroInmutable.Meta):
        verbose_name = "Operación de stock"
        verbose_name_plural = "Operaciones de stock"
        ordering = ["creado_en", "id"]
        indexes = [
            # El historial del edificio.
            models.Index(fields=["dispositivo", "edificio", "creado_en"], name="opstock_edificio_idx"),
            # El historial de la persona.
            models.Index(fields=["ciudadano", "creado_en"], name="opstock_persona_idx"),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} · {self.dispositivo_id}/{self.edificio_id}"


class MovimientoStock(LibroInmutable):
    """El delta firmado que una operación dejó en un saldo, con el saldo que quedó (RN-010-05)."""

    class Tipo(models.TextChoices):
        INGRESO_KIT = "INGRESO_KIT", "Recepción de kit"
        INGRESO_MANUAL = "INGRESO_MANUAL", "Ingreso manual"
        ENTREGA_PERSONA = "ENTREGA_PERSONA", "Entrega a una persona"
        # El sentido del traspaso vive acá.
        TRASPASO_SALIDA = "TRASPASO_SALIDA", "Traspaso (salida)"
        TRASPASO_ENTRADA = "TRASPASO_ENTRADA", "Traspaso (entrada)"
        AJUSTE = "AJUSTE", "Ajuste por conteo"

    operacion = models.ForeignKey(
        OperacionStock, on_delete=models.PROTECT, related_name="movimientos", verbose_name="Operación"
    )
    tipo = models.CharField(max_length=20, choices=Tipo.choices, verbose_name="Tipo")
    # La clave del saldo que movió.
    dispositivo = models.ForeignKey(
        "programas.Dispositivo", on_delete=models.PROTECT, related_name="movimientos_stock", verbose_name="Institución"
    )
    edificio = models.ForeignKey(
        "programas.Edificio", on_delete=models.PROTECT, related_name="movimientos_stock", verbose_name="Edificio"
    )
    item = models.ForeignKey(
        "programas.TipoKit", on_delete=models.PROTECT, related_name="movimientos_stock", verbose_name="Insumo"
    )
    # Delta firmado; nunca cero.
    cantidad = models.IntegerField(verbose_name="Cantidad")
    # El saldo después de este movimiento: el historial se lee sin recalcular.
    saldo_posterior = models.PositiveIntegerField(verbose_name="Saldo posterior")
    creado_en = models.DateTimeField(auto_now_add=True, verbose_name="Momento")

    class Meta(LibroInmutable.Meta):
        verbose_name = "Movimiento de stock"
        verbose_name_plural = "Movimientos de stock"
        ordering = ["creado_en", "id"]
        constraints = [
            models.CheckConstraint(condition=~models.Q(cantidad=0), name="movimiento_stock_no_cero"),
        ]
        indexes = [
            models.Index(fields=["dispositivo", "edificio", "item", "creado_en"], name="movstock_clave_idx"),
            # Últimos movimientos del edificio y filtro por fechas sin insumo.
            models.Index(fields=["dispositivo", "edificio", "creado_en"], name="movstock_edificio_idx"),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} {self.cantidad:+d} · {self.dispositivo_id}/{self.edificio_id}/{self.item_id}"
