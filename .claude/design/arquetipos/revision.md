# Arquetipo · Revisión (persona con ficha por secciones)

**Golden (la única que se clona):** `programas/templates/programas/dispositivos/estadia/revision_referencia.html`.
**Marcadores:** `scripts/design_audit.py --arquetipo revisión <archivo>`.
**Componentes:** page_header · alerta · tabs · ficha_timeline (sección de ficha y línea de tiempo) ·
estado_vacio · botones_badges.
**Molde visual:** el mockup P7 (mockup `dispositivos-v2.html`, pantalla P7).

La golden es una **referencia sin vista**: no tiene URL. Consume el contrato de contexto de abajo, y
el test `RevisionReferenciaTest` (`core/tests/test_nodo_ui_piezas.py`) la renderiza con los datos de
ejemplo del mockup. La pantalla real **clona** el archivo y le pone su vista; no lo edita.

## Cuándo

Una **persona** (o un caso) que se revisa y se opera en una sola pantalla: identidad arriba, una
ficha larga dividida en secciones con distinto avance y distinta sensibilidad, lo que fue pasando en
orden cronológico, y acciones que cambian su estado. Con una ficha corta y sin historia es Detalle.

## Estructura

1. `{% page_header %}`: nombre de la persona, bajada con ubicación y datos, estado y etiquetas
   (`badge`), acciones `btn-sm btn-fit` (son 4: van `btn-fit`). La acción destructiva va última,
   `btn-danger`, y lleva a su confirmación.
2. `_alerta` `warning` con el avance global de la ficha y «Completar ahora» (solo si falta).
3. Grilla `lg:grid-cols-3`: **izquierda** (2/3) una surface con solapas ARIA como el Detalle; la
   solapa Ficha apila `_ficha_seccion` en `space-y-3`. **Derecha** (1/3), surfaces apiladas:
   línea de tiempo (con la acción «Novedad»), contexto de la persona y adjuntos.

## Regla de la sección bloqueada

Una sección que el rol no puede leer **no se oculta**: se dibuja rayada, con su título, su badge de
sensibilidad, su avance y quién la completa. Nunca se muestran sus datos. La vista decide `bloqueada`
por capacidad; el template no evalúa permisos.

## Contrato de contexto (la vista lo prepara)

| Variable | Qué es |
|---|---|
| `persona` | `nombre_completo`, `dni`, `edad` |
| `ubicacion`, `estadia` | texto de ubicación; `estado`, `reingreso`, `ingreso`, `dias` |
| `ficha` | `pendiente` (bool), `titulo`, `texto`, `url_completar` |
| `secciones` | lista de dicts con las claves de `_ficha_seccion` (`codigo`, `titulo`, `avance`, `avance_tono`, `sensibilidad`, `sensibilidad_tono`, `bloqueada`, `motivo`, `completa`, `completar_url`, `campos`, `vacio_texto`) |
| `eventos` | lista de dicts de `_linea_tiempo`, ya ordenada |
| `puede_*`, `url_*` | acciones por capacidad: `cambiar_plaza`, `permiso_salida`, `trasladar`, `egresar`, `cargar_novedad` (la URL de esta última es `url_novedad`) |
| `otras_estadias`, `adjuntos` | listas; `n_movimientos`, `n_novedades`, `n_adjuntos` son contadores |
| `url_volver`, `url_legajo`, `migas` | navegación |

## Prohibido

- Lo del arquetipo Detalle (`<h1>`, `<style>`, «← Volver» de texto, solapas sin ARIA).
- Emoji como ícono (🔒, 📎): Font Awesome con `aria-hidden`.
- Ocultar una sección sensible en vez de bloquearla; mostrar sus datos a quien no tiene la capacidad.
- Calcular avance, tono del medidor o permisos en el template.

## Qué no cubre la golden

Los paneles de Movimientos, Novedades, Adjuntos e Historial traen solo el estado vacío: la pantalla
real los llena con la tabla del arquetipo Detalle. El `eyebrow` del mockup (línea sobre el título) no
existe en `{% page_header %}`: la ubicación va al principio de la bajada.

## Checklist (la usa el revisor)

- [ ] `--arquetipo revisión` OK y `--ratchet` con 0 nuevos.
- [ ] Molde declarado = golden; de la hermana solo salió dominio.
- [ ] Toda sección sensible sin permiso está bloqueada, con su avance y quién la completa.
- [ ] Ninguna regla (avance, tono, permiso) vive en el template.
- [ ] La acción destructiva va última, `btn-danger`, con confirmación.
