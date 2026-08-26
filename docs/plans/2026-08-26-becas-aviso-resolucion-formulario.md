# Cambio 44 — Avisar por correo al ciudadano cuando se resuelve su formulario

🟢 **IMPLEMENTADO — 26/08/2026**

> Este documento fue el **spec de handoff** que se usó para construir el cambio. El registro
> definitivo es el **Cambio 44** de [`docs/internal/requerimientos.md`](../internal/requerimientos.md),
> que es la fuente de verdad; esto se conserva como antecedente del diseño previo a implementar.

| | |
|---|---|
| **Programa / módulo** | Becas · Portal |
| **Etiquetas** | `#correo` `#relevamientos` `#cupos` `#ui` `#infra` |
| **Solicitante** | PM — pedido directo en sesión de trabajo del 26/08/2026 |
| **Fecha del pedido** | 26/08/2026 |
| **Issue / épica** | sin issue |
| **Partes afectadas** | Backoffice · Servidor. **Mobile no se toca.** |
| **Migración** | Solo metadatos (`verbose_name` / `help_text` de `Relevamiento.confirmar_por_email`). Sin cambio de esquema. |

## Pedido original

> «En el programa Becas, cuando el ciudadano se inscribe le llega el comprobante de
> inscripción. Cuando el técnico valida el relevamiento en
> `/becas/revision/formulario/` lo puede aprobar o rechazar. Quiero que cuando pase
> eso se le envíe un mail avisando si fue aprobado o rechazado. Pero la aprobación o
> el rechazo no es la de SIIS, es la del caso en general.»

Definiciones agregadas en la misma sesión, al relevar el código:

> «Si queda en lista de espera se le notifica que entró pero está en lista de espera.»
> «Se le manda el motivo textual.» · «Ambas, sea por link o territorial.»
> «Lo respeta, y sumale eso al territorial también.» · «Sí, también cuando se pasa de
> lista a aprobado se avisa.»

## Alcance acordado

**Cuatro momentos de aviso**, no dos:

| Momento | Vista que lo dispara | Estado resultante |
|---|---|---|
| Aprobado con cupo | `formulario_aprobar` | `APROBADO` |
| Entró pero quedó en lista de espera | `formulario_aprobar` | sigue `ENVIADO` + entrada en `ListaEspera` |
| Rechazado | `formulario_rechazar` | `RECHAZADO` |
| Promovido de lista de espera a aprobado | `promover_lista_espera_view` | `APROBADO` |

- Aplica a **los dos tipos de relevamiento**: público por link y territorial de campo.
- **Respeta el toggle `confirmar_por_email`** del relevamiento, que pasa a estar
  disponible también en los territoriales (hoy solo se ofrece en los públicos).
- El **motivo del rechazo se manda textual**, tal como lo escribió el técnico.

**Queda explícitamente afuera:** la baja de un beneficiario ya aprobado
(`dar_de_baja`), los cambios de estado hechos desde el admin de Django, el reenvío
manual de un aviso, y cualquier aviso ligado a la validación SIIS.

## Decisiones tomadas

- **Cuatro correos y no dos, porque «Aprobar» tiene dos desenlaces.**
  `aprobar_o_poner_en_espera` devuelve `"aprobado"` o `"lista_espera"` según haya
  cupo, y `Formulario.Estado` no tiene un estado «en espera»: sin cupo el formulario
  **sigue en `ENVIADO`**. Mandar «fuiste aprobado» al apretar Aprobar le mentiría a
  quien cayó en lista de espera.

- **El motivo del rechazo va textual, por decisión del cliente.** Se deja asentado el
  riesgo asumido: `motivo_rechazo` es hoy una nota interna del técnico, sin revisión
  de estilo ni destinatario ciudadano. Si el programa quiere despersonalizarlo más
  adelante, el cambio es de plantilla y no de flujo.

- **El aviso no distingue origen del formulario.** `email_contacto` es obligatorio en
  el modelo (`Bloque C — Contacto`) y viaja también en el serializer de la API móvil,
  así que un formulario cargado por el territorial tiene correo igual que uno del link.

- **El toggle se extiende a territorial en lugar de crear un campo nuevo.** Es el
  mismo hecho para el ciudadano —«este relevamiento notifica por correo»— y duplicarlo
  daría dos interruptores que hay que mantener sincronizados. Como el campo tiene
  `default=False`, **ningún relevamiento existente empieza a mandar correos**: es
  opt-in y no hay envío retroactivo.

- **El correo se manda desde la vista, después de que el servicio devuelve, nunca
  dentro de la transacción.** `aprobar_o_poner_en_espera` y `promover_lista_espera`
  son `@transaction.atomic`: si se enviara adentro y la transacción hiciera rollback,
  el correo ya salió y no se puede retractar.

- **El aviso nunca rompe la acción del técnico**, mismo criterio que el comprobante
  (Cambio 41): si SMTP falla se loguea y la aprobación o el rechazo quedan firmes.
  El técnico no puede quedar bloqueado por un problema de correo.

- **No se toca `formulario_validar_sis`.** Es la prevalidación del Cambio 34 y no
  resuelve el caso; el pedido fue explícito en distinguirla.

## Implementación

### Servicio nuevo

`programas/services/avisos_resolucion.py`, modelado sobre
`enviar_confirmacion_inscripcion` de `inscripcion_publica.py`:

```python
def enviar_aviso_resolucion(formulario, resultado, *, motivo="", protocol="https", domain=""):
    """resultado ∈ {"aprobado", "lista_espera", "rechazado", "promovido"}."""
```

- Corta temprano si `not relevamiento.confirmar_por_email or not formulario.email_contacto`.
- `EmailMultiAlternatives` con las dos versiones (`.txt` + `.html`) y `contexto_pie()`
  de `users/services/correo.py`.
- `try/except` alrededor de `send`, `logger.exception`, devuelve `False`.

### Plantillas

`programas/templates/programas/becas/email/resolucion_body.txt` y `.html`, un par
único con bloques condicionales por `resultado`. Reusan `user/email/_encabezado.html`
y `_pie.html` para no abrir una tercera variante de marca.

Asuntos: `Tu inscripción fue aprobada`, `Tu inscripción quedó en lista de espera`,
`Novedades sobre tu inscripción` (rechazo) y `Tu inscripción fue aprobada` (promoción),
todos con `— {{ convocatoria }}`.

### Puntos de llamada

| Archivo | Dónde | Argumentos |
|---|---|---|
| `programas/views/revision.py` | `formulario_aprobar`, en el `else` tras `aprobar_o_poner_en_espera` | `resultado` tal cual lo devolvió el servicio |
| `programas/views/revision.py` | `formulario_rechazar`, después de `registrar_traza` | `"rechazado"`, `motivo=motivo` |
| `programas/views/cupo.py` | `promover_lista_espera_view`, tras `promover_lista_espera` | `"promovido"` |

### Toggle en territoriales

- `programas/forms.py`: hoy `__init__` hace `self.fields.pop("confirmar_por_email")`
  cuando `not puede_publico`. El campo deja de removerse; siguen removiéndose `tipo` y
  `padron`.
- Templates: el toggle está dentro del `fieldset` que se muestra solo para el tipo
  público en `convocatoria_detail.html:353`, `relevamiento_list.html:244` y
  `relevamiento_form.html:45`. Hay que **sacarlo del fieldset** y dejarlo visible para
  ambos tipos.
- Textos: la etiqueta «Enviar confirmación por correo al inscribirse» y el `help_text`
  «Al inscribirse por el link, la persona recibe un correo con su comprobante» quedan
  desactualizados; ahora cubren también los avisos de resolución y el canal territorial.
- `relevamiento_detail.html:58` muestra el estado del toggle: revisar la redacción.

## Archivos

`programas/services/avisos_resolucion.py` (nuevo) · `programas/templates/programas/becas/email/resolucion_body.{txt,html}` (nuevos) · `programas/views/revision.py` · `programas/views/cupo.py` · `programas/forms.py` · `programas/models/__init__.py` (textos del campo) · `programas/migrations/00NN_*` (metadatos) · `programas/templates/programas/becas/relevamientos/{convocatoria_detail,relevamiento_list,relevamiento_form,relevamiento_detail}.html` · tests: `programas/tests/test_avisos_resolucion.py` (nuevo), `programas/tests/test_becas_revision.py`

## Base de datos

Sin cambio de esquema. `Relevamiento.confirmar_por_email` ya existe desde
`programas.0049` con `default=False`. La migración nueva solo registra el cambio de
`verbose_name` / `help_text`, necesaria para que `makemigrations --check` quede limpio.

## Validación

- Un test por desenlace: aprobado, lista de espera, rechazado, promovido.
- Toggle apagado → no se manda nada, en relevamiento público **y** en territorial.
- Territorial con toggle encendido → manda (es la regresión que habilita este cambio).
- SMTP caído → la aprobación y el rechazo quedan firmes igual, y la vista no rompe.
- `formulario_validar_sis` **no** manda correo.
- Rechazo → el motivo textual aparece en el cuerpo.
- Suites `programas` y `portal` sin regresiones nuevas (contra el baseline conocido de
  errores de entorno por Python 3.14 renderizando plantillas).
- `manage.py check` · `makemigrations --check` · `design_audit.py --changed` en 0
  errores · `compile_templates.py` en 0.

## Puesta en marcha en el servidor

- Deploy estándar con migración (solo metadatos, riesgo nulo).
- **Depende del SMTP real**, que es el Cambio 37 / 13 y sigue pendiente de ECOM:
  `EMAIL_BACKEND` cae a consola mientras `EMAIL_HOST` esté vacío. Hasta entonces el
  código funciona y los tests pasan, pero no se entrega nada.
- Tras el deploy **nada cambia solo**: el toggle viene en `False` en todos los
  relevamientos existentes. Para empezar a notificar hay que activarlo relevamiento
  por relevamiento.

## Pendientes / a definir

- La **baja de un beneficiario aprobado** (`dar_de_baja`) no avisa. Quedó fuera de
  alcance; es el mismo hecho para el ciudadano y conviene definirlo.
- **Textos definitivos de los cuatro correos**: los aprueba el programa de Becas.
- Si el motivo del rechazo textual resulta inadecuado en producción, la salida es
  cambiar la plantilla.

## Reversión

Revertir el PR y retroceder la migración de metadatos. No se pierden datos: no hay
columnas nuevas ni registros propios. Los relevamientos territoriales que hayan
quedado con el toggle en `True` conservan el valor; deja de tener efecto.
