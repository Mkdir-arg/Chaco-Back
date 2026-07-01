import re
import unicodedata

from django.db.models import Q

from ..models import DerivacionPrograma, InscripcionPrograma, Programa


class SolapasService:
    """Solapas dinámicas del legajo ciudadano basadas en inscripciones a programas."""

    SOLAPAS_ESTATICAS = [
        {"id": "resumen", "nombre": "Resumen", "icono": "gauge-high", "orden": 0, "estatica": True},
        {"id": "conversaciones", "nombre": "Conversaciones", "icono": "comments", "orden": 860, "estatica": True},
        {"id": "derivaciones", "nombre": "Derivaciones", "icono": "share-nodes", "orden": 870, "estatica": True},
        {"id": "alertas", "nombre": "Alertas", "icono": "bell", "orden": 880, "estatica": True},
        {
            "id": "linea_tiempo",
            "nombre": "Línea de tiempo",
            "icono": "clock-rotate-left",
            "orden": 950,
            "estatica": True,
        },
        {"id": "red_familiar", "nombre": "Red Familiar", "icono": "users", "orden": 998, "estatica": True},
        {"id": "archivos", "nombre": "Archivos", "icono": "folder-open", "orden": 999, "estatica": True},
    ]

    @classmethod
    def obtener_solapas_ciudadano(cls, ciudadano):
        solapas = [dict(s) for s in cls.SOLAPAS_ESTATICAS]

        inscripciones_activas = (
            InscripcionPrograma.objects.filter(
                ciudadano=ciudadano,
                estado__in=["ACTIVO", "EN_SEGUIMIENTO"],
            )
            .select_related("programa")
            .order_by("programa__orden")
        )

        for inscripcion in inscripciones_activas:
            programa = inscripcion.programa
            tipo_normalizado = cls._normalizar_tipo_programa(programa.tipo)
            solapas.append(
                {
                    "id": f"programa_{tipo_normalizado}",
                    "nombre": programa.nombre,
                    "icono": programa.icono or "star",
                    "color": programa.color,
                    "url_name": cls._obtener_url_programa(tipo_normalizado),
                    "url_params": {"ciudadano_id": ciudadano.id, "inscripcion_id": inscripcion.id},
                    "orden": 100 + programa.orden,
                    "estatica": False,
                    "programa": programa,
                    "inscripcion": inscripcion,
                    "badge": cls._obtener_badge_programa(inscripcion),
                }
            )

        badges = cls.obtener_badges_ciudadano(ciudadano)
        solapas_final = []
        for s in solapas:
            if s["id"] in badges and "badge" not in s:
                s = {**s, "badge": badges[s["id"]]}
            solapas_final.append(s)

        solapa_becas = cls._obtener_solapa_becas(ciudadano)
        if solapa_becas:
            solapas_final.append(solapa_becas)

        solapas_final.sort(key=lambda x: x["orden"])
        return solapas_final

    @classmethod
    def obtener_programas_activos(cls, ciudadano):
        return (
            InscripcionPrograma.objects.filter(
                ciudadano=ciudadano,
                estado__in=["ACTIVO", "EN_SEGUIMIENTO"],
            )
            .select_related("programa")
            .order_by("programa__orden")
        )

    @classmethod
    def obtener_programas_disponibles_derivacion(cls, ciudadano, programa_origen=None):
        programas_inscritos = InscripcionPrograma.objects.filter(
            ciudadano=ciudadano,
            estado__in=["ACTIVO", "EN_SEGUIMIENTO"],
        ).values_list("programa_id", flat=True)

        qs = Programa.objects.filter(estado="ACTIVO").exclude(id__in=programas_inscritos)
        if programa_origen:
            qs = qs.exclude(id=programa_origen.id)
        return qs.order_by("orden", "nombre")

    @classmethod
    def tiene_derivaciones_pendientes(cls, ciudadano, programa=None):
        query = Q(ciudadano=ciudadano, estado="PENDIENTE")
        if programa:
            query &= Q(programa_destino=programa)
        return DerivacionPrograma.objects.filter(query).exists()

    @classmethod
    def obtener_derivaciones_pendientes(cls, ciudadano):
        return (
            DerivacionPrograma.objects.filter(ciudadano=ciudadano, estado="PENDIENTE")
            .select_related("programa_origen", "programa_destino", "derivado_por")
            .order_by("-creado")
        )

    @classmethod
    def obtener_badges_ciudadano(cls, ciudadano):
        badges = {}

        alertas_count = ciudadano.alertas.filter(activa=True).count()
        if alertas_count:
            badges["alertas"] = {"tipo": "numero", "valor": alertas_count, "color_hex": "#EF4444"}

        derivaciones_count = ciudadano.derivaciones_programas.filter(estado="PENDIENTE").count()
        if derivaciones_count:
            badges["derivaciones"] = {"tipo": "numero", "valor": derivaciones_count, "color_hex": "#F97316"}

        try:
            from conversaciones.models import Mensaje

            mensajes_count = Mensaje.objects.filter(
                conversacion__dni_ciudadano=ciudadano.dni,
                conversacion__estado__in=["pendiente", "activa"],
                remitente="ciudadano",
                leido=False,
            ).count()
            if mensajes_count:
                badges["conversaciones"] = {"tipo": "numero", "valor": mensajes_count, "color_hex": "#8B5CF6"}
        except Exception:
            pass

        return badges

    @classmethod
    def crear_inscripcion_directa(cls, ciudadano, programa, responsable, notas=""):
        existe = InscripcionPrograma.objects.filter(
            ciudadano=ciudadano,
            programa=programa,
            estado__in=["ACTIVO", "EN_SEGUIMIENTO"],
        ).exists()
        if existe:
            raise ValueError(f"El ciudadano ya tiene una inscripción activa en {programa.nombre}")
        return InscripcionPrograma.objects.create(
            ciudadano=ciudadano,
            programa=programa,
            via_ingreso="DIRECTO",
            estado="ACTIVO",
            responsable=responsable,
            notas=notas,
        )

    @classmethod
    def obtener_historial_programas(cls, ciudadano):
        return (
            InscripcionPrograma.objects.filter(ciudadano=ciudadano)
            .select_related("programa", "responsable")
            .order_by("-fecha_inscripcion")
        )

    @classmethod
    def cerrar_inscripcion(cls, inscripcion, motivo_cierre, usuario):
        from django.utils import timezone

        if inscripcion.estado == "CERRADO":
            raise ValueError("La inscripción ya está cerrada")
        inscripcion.estado = "CERRADO"
        inscripcion.fecha_cierre = timezone.now().date()
        inscripcion.motivo_cierre = motivo_cierre
        nota_cierre = (
            f"\n\n[{timezone.now().strftime('%d/%m/%Y %H:%M')}] "
            f"Cerrado por {usuario.get_full_name() or usuario.username}\n"
            f"Motivo: {motivo_cierre}"
        )
        inscripcion.notas += nota_cierre
        inscripcion.save()

    @classmethod
    def _obtener_url_programa(cls, tipo_programa):
        url_map = {
            "ACOMPANAMIENTO_SOCIAL": "legajos:programa_detalle",
            "NACHEC": "nachec:detalle_caso_ciudadano",
            "ECONOMICO": "programas:economico_detalle",
            "FAMILIAR": "programas:familiar_detalle",
        }
        return url_map.get(tipo_programa, "legajos:programa_detalle")

    @classmethod
    def _normalizar_tipo_programa(cls, tipo_programa):
        valor = (tipo_programa or "").upper().strip()
        if "NACHEC" in valor or "ÑACHEC" in valor or "ACHEC" in valor:
            return "NACHEC"
        ascii_valor = unicodedata.normalize("NFKD", valor).encode("ascii", "ignore").decode("ascii")
        ascii_valor = re.sub(r"[^A-Z0-9]+", "_", ascii_valor).strip("_")
        return ascii_valor or "PROGRAMA"

    @classmethod
    def _obtener_solapa_becas(cls, ciudadano):
        """Genera la solapa dinámica 'Becas' si el ciudadano tiene formularios (issue #80).

        Sin 'url': se renderiza embebida en el legajo (tab-becas), igual que Resumen
        o Conversaciones, en vez de redirigir a la página standalone.
        """
        from programas.models import Formulario, ListaEspera
        from programas.services.cupo import estado_relevante_becas

        formularios_qs = Formulario.objects.filter(ciudadano=ciudadano)
        estados = set(formularios_qs.values_list("estado", flat=True))
        if not estados:
            return None

        en_espera = ListaEspera.objects.filter(
            formulario__ciudadano=ciudadano, promovido=False
        ).exists()

        texto, color = estado_relevante_becas(estados, en_espera)
        color_hex = {
            "success": "var(--text-fg-success)",
            "warning": "var(--text-fg-warning)",
            "danger": "var(--text-fg-danger)",
            "gray": "var(--text-body-subtle)",
        }[color]
        badge = {"tipo": "punto", "color_hex": color_hex, "title": texto}

        return {
            "id": "becas",
            "nombre": "Becas",
            "icono": "graduation-cap",
            "orden": 200,
            "estatica": False,
            "badge": badge,
        }

    @classmethod
    def obtener_resumen_becas_ciudadano(cls, ciudadano):
        """Datos del resumen de Becas de un ciudadano (issue #80).

        Reusado por la vista standalone (programas.views.solapas_becas) y por la tab
        embebida "Becas" del legajo (legajos.selectors.ciudadanos.build_ciudadano_detail_context).
        """
        from programas.models import Formulario
        from programas.services.cupo import estado_relevante_becas

        formularios = list(
            Formulario.objects.filter(ciudadano=ciudadano)
            .select_related(
                "relevamiento__convocatoria__segmento",
                "relevamiento__convocatoria__subsegmento",
            )
            .prefetch_related("lista_espera")
            .order_by("-creado")
        )

        # Anotar cada formulario con en_espera_activa usando el prefetch (sin queries extra)
        for f in formularios:
            f.en_espera_activa = any(not le.promovido for le in f.lista_espera.all())

        if formularios:
            estados = {f.estado for f in formularios}
            en_espera = any(f.en_espera_activa for f in formularios)
            estado_texto, estado_color = estado_relevante_becas(estados, en_espera)
        else:
            estado_texto, estado_color = "—", "gray"

        # Stat cards basadas en formulario más reciente
        formulario_reciente = formularios[0] if formularios else None
        segmento_nombre = (
            formulario_reciente.relevamiento.convocatoria.segmento.nombre
            if formulario_reciente
            else "—"
        )
        fecha_envio = formulario_reciente.creado if formulario_reciente else None

        return {
            "formularios": formularios,
            "estado_texto": estado_texto,
            "estado_color": estado_color,
            "segmento_nombre": segmento_nombre,
            "fecha_envio": fecha_envio,
            "Formulario": Formulario,  # para acceder a Estado choices en template
        }

    @classmethod
    def _obtener_badge_programa(cls, inscripcion):
        from django.utils import timezone

        if inscripcion.estado == "PENDIENTE":
            return {"tipo": "punto", "color_hex": "#F59E0B", "title": "Inscripción pendiente"}

        modificado = getattr(inscripcion, "modificado", None)
        if inscripcion.estado == "EN_SEGUIMIENTO" and modificado:
            dias = (timezone.now() - modificado).days
            if dias > 30:
                return {
                    "tipo": "punto",
                    "color_hex": "#F97316",
                    "title": f"Sin actividad hace {dias} días",
                }
        return None
