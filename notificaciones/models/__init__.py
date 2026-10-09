"""Modelos de las campañas de correo (análisis 007).

Una **campaña** es un asunto, un cuerpo HTML ya saneado y una lista de destinatarios
leída de un Excel. Se arma en «A enviar» y, cuando alguien con ``notificacion.enviar``
la dispara, un hilo del pod manda un correo individual a cada destinatario en lotes.

El envío sigue el patrón de ``programas.CorridaSiis``: lo que importa es el **latido**.
Cuando el pod se recicla no queda nadie para escribir que el envío murió, así que la
interrupción se deduce de un latido viejo en vez de guardarse como estado.
"""

from datetime import timedelta

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from core.models import TimeStamped
from core.rutas_media import ruta_notificacion_excel, ruta_notificacion_html

#: Tope de destinatarios válidos por campaña (RN-007-05, decidido por el PM).
TOPE_DESTINATARIOS = 5000


class Campana(TimeStamped):
    """Una campaña de correo masivo."""

    class Estado(models.TextChoices):
        A_ENVIAR = "A_ENVIAR", "A enviar"
        ENVIANDO = "ENVIANDO", "Enviando"
        ENVIADA = "ENVIADA", "Enviada"
        ENVIADA_CON_ERRORES = "ENVIADA_CON_ERRORES", "Enviada con errores"
        CANCELADA = "CANCELADA", "Cancelada"

    #: Sin señal por más de esto, el envío se da por interrumpido. Un correo con el
    #: SMTP lento tarda como mucho ``EMAIL_TIMEOUT`` (5 s) y el latido se escribe por
    #: correo; la pausa entre lotes es de segundos. Cinco minutos es el mismo umbral
    #: que ``CorridaSiis``: un envío vivo no se declara muerto a sí mismo.
    LATIDO_VENCIDO = timedelta(minutes=5)

    nombre = models.CharField(max_length=120, verbose_name="Nombre")
    asunto = models.CharField(max_length=150, verbose_name="Asunto")

    archivo_excel = models.FileField(
        upload_to=ruta_notificacion_excel, max_length=255, verbose_name="Lista de destinatarios (Excel)"
    )
    nombre_excel = models.CharField(max_length=255, blank=True, default="", verbose_name="Nombre original del Excel")
    archivo_html = models.FileField(
        upload_to=ruta_notificacion_html, max_length=255, verbose_name="Cuerpo del correo (HTML)"
    )
    nombre_html = models.CharField(max_length=255, blank=True, default="", verbose_name="Nombre original del HTML")
    # Lo que se envía y lo que muestra la vista previa: el HTML ya saneado, nunca el
    # original. El texto plano es la alternativa del mismo correo (RN-007-13).
    html_sanitizado = models.TextField(blank=True, default="")
    texto_plano = models.TextField(blank=True, default="")
    # Avisos de la previsualización, calculados al subir el HTML.
    elementos_quitados = models.PositiveIntegerField(default=0, verbose_name="Elementos inseguros quitados")
    imagenes_no_visibles = models.PositiveIntegerField(default=0, verbose_name="Imágenes con ruta relativa o cid:")

    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.A_ENVIAR, db_index=True)
    creada_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="campanas_creadas"
    )
    enviada_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="campanas_enviadas"
    )
    enviada_en = models.DateTimeField(null=True, blank=True, verbose_name="Envío iniciado")
    finalizada_en = models.DateTimeField(null=True, blank=True, verbose_name="Envío terminado")
    latido = models.DateTimeField(null=True, blank=True, verbose_name="Última señal de vida")
    cancelacion_pedida = models.BooleanField(default=False, verbose_name="Se pidió detener")
    # Token de la corrida a cargo del envío (uuid4 en hex). «Enviar» y «Reanudar» ponen uno
    # nuevo; el hilo lo compara antes de cada correo y se retira si cambió. Es lo que impide
    # que un hilo que se creyó muerto —latido vencido con el hilo vivo— siga mandando a la par
    # del que lo reemplazó. CharField y no UUIDField: sin el gotcha de char(32) en MariaDB.
    corrida = models.CharField(max_length=32, null=True, blank=True, verbose_name="Corrida a cargo")
    mensaje = models.TextField(blank=True, default="", verbose_name="Último aviso del envío")

    # Resultado de la lectura del Excel.
    leidas = models.PositiveIntegerField(default=0, verbose_name="Filas leídas")
    total = models.PositiveIntegerField(default=0, verbose_name="Destinatarios")
    invalidos = models.PositiveIntegerField(default=0, verbose_name="Inválidos descartados")
    duplicados = models.PositiveIntegerField(default=0, verbose_name="Duplicados descartados")
    # Avance del envío. Los escribe el hilo al cerrar cada lote; el detalle los cuenta
    # en vivo desde los destinatarios.
    enviados = models.PositiveIntegerField(default=0)
    fallidos = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Campaña de correo"
        verbose_name_plural = "Campañas de correo"
        ordering = ["-creado"]

    def __str__(self):
        return f"{self.nombre} · {self.get_estado_display()}"

    @property
    def interrumpida(self):
        """¿Dice que se está enviando pero hace rato que no da señales?"""
        if self.estado != self.Estado.ENVIANDO:
            return False
        referencia = self.latido or self.enviada_en or self.modificado
        return timezone.now() - referencia > self.LATIDO_VENCIDO

    @property
    def descartados_total(self):
        return self.invalidos + self.duplicados

    @property
    def editable(self):
        """RN-007-10: solo «A enviar» se edita, se elimina, se prueba y se envía."""
        return self.estado == self.Estado.A_ENVIAR

    @property
    def terminada(self):
        return self.estado in (self.Estado.ENVIADA, self.Estado.ENVIADA_CON_ERRORES, self.Estado.CANCELADA)


class Destinatario(TimeStamped):
    """Un correo válido de la lista, con su resultado de envío."""

    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        # Reclamado por una corrida, que lo está mandando ahora. Un destinatario solo se
        # manda si se lo pudo pasar de PENDIENTE a EN_CURSO con un UPDATE condicional.
        EN_CURSO = "EN_CURSO", "Enviándose"
        ENVIADO = "ENVIADO", "Enviado"
        FALLIDO = "FALLIDO", "Fallido"

    campana = models.ForeignKey(Campana, on_delete=models.CASCADE, related_name="destinatarios")
    email = models.CharField(max_length=254)
    fila_excel = models.PositiveIntegerField(verbose_name="Fila del Excel")
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.PENDIENTE)
    enviado_en = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Destinatario"
        verbose_name_plural = "Destinatarios"
        ordering = ["fila_excel", "pk"]
        constraints = [
            # RN-007-04: un correo cuenta una sola vez por campaña (se guarda en minúsculas).
            models.UniqueConstraint(fields=["campana", "email"], name="notif_destinatario_unico"),
        ]
        indexes = [
            # El hilo pide los pendientes de a lotes y el detalle cuenta por estado.
            models.Index(fields=["campana", "estado"], name="notif_dest_campana_estado"),
            # «Correos enviados en el mes» del listado: rango sobre la fecha de envío.
            models.Index(fields=["estado", "enviado_en"], name="notif_dest_estado_enviado"),
        ]

    def __str__(self):
        return self.email


class Descartado(TimeStamped):
    """Una fila del Excel que no se va a enviar, con el motivo."""

    class Motivo(models.TextChoices):
        INVALIDO = "INVALIDO", "Formato inválido"
        DUPLICADO = "DUPLICADO", "Duplicado"
        VACIO = "VACIO", "Vacío"

    campana = models.ForeignKey(Campana, on_delete=models.CASCADE, related_name="descartados")
    fila_excel = models.PositiveIntegerField(verbose_name="Fila del Excel")
    valor = models.CharField(max_length=255, blank=True, default="", verbose_name="Valor leído")
    motivo = models.CharField(max_length=10, choices=Motivo.choices)

    class Meta:
        verbose_name = "Fila descartada"
        verbose_name_plural = "Filas descartadas"
        ordering = ["fila_excel", "pk"]

    def __str__(self):
        return f"Fila {self.fila_excel}: {self.get_motivo_display()}"


class PruebaEnviada(TimeStamped):
    """Registro de cada «Enviar prueba» (RF-007-18): quién, a qué correo, cuándo y cómo salió.

    Una prueba no cambia el estado de la campaña ni cuenta como envío.
    """

    campana = models.ForeignKey(Campana, on_delete=models.CASCADE, related_name="pruebas")
    enviada_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="pruebas_de_campana"
    )
    email = models.CharField(max_length=254)
    ok = models.BooleanField(default=False)
    error = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Prueba de campaña"
        verbose_name_plural = "Pruebas de campaña"
        ordering = ["-creado"]

    def __str__(self):
        return f"{self.email} · {'ok' if self.ok else 'falló'}"
