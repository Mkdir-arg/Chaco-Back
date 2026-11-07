# Componente · Sugerencias de personas (`nodo-sugerencias.js`, `.nodo-sugerencias`)

**Clasificación:** Canónico reutilizable. Pieza única.
**Evidencia:** `static/custom/js/nodo-sugerencias.js`, `static/custom/css/nodo-sugerencias.css`,
`core/forms_sugerencias.py`, `programas/selectors/personas_sugeridas.py`, `programas/views/dispositivos_legajo.py`
(`PersonasSugeridasView`), `programas/selectors/equipo_sugeridas.py` y `programas/views/dispositivos_equipo.py`
(`EquipoPersonasSugeridasView`).
**Consumidores de referencia:** el DNI de «Reservar» y «Prestar» en el modal de una plaza
(`programas/templates/programas/dispositivos/sectores/sectores.html`), el DNI del paso «Ingresar persona»
(`ingreso/paso_persona.html`, Cambio 416) y el campo de «Buscar agente» del modal de alta rápida de usuarios
(`users/templates/user/_alta_rapida_modal.html`, que se monta desde su propio JS al abrirse como agente; lo cargan
`legajo/detail.html` y `relevamientos/list.html`) y el buscador «Persona y rol» del modal «Sumar persona al Equipo»
(`legajo/detail.html`, Cambio 420: usa `data-sugerencias-destino`).

Mejora progresiva sobre un `<input>` de texto que ya existe: desde 3 caracteres muestra
la persona que coincide, o la lista, y al elegir una completa el campo con su DNI (o con `valor`, si la fila lo trae: el buscador de agentes deja
nombre y apellido). No
reemplaza al campo ni a la validación: el input es el que viaja en el POST y el servidor
(`clean_dni`, `buscar_ciudadano_por_dni`) decide igual que sin la pieza.

## Contrato

```html
<input class="nodo-field" data-sugerencias-url="/dispositivos/7/personas/buscar/"
       data-sugerencias-vacio="No encontramos a nadie: …"
       data-sugerencias-hay-mas="Hay más resultados: escribí más datos.">
```

- `data-sugerencias-url` se lee **en cada consulta**: una pantalla puede cambiarlo o quitarlo (sin URL no consulta).
  Un campo que la recibe después se monta con `window.NodoSugerencias.montar(contenedor)`.
- `data-sugerencias-destino="<id>"` apunta a un `<input type="hidden">`: al elegir, el destino recibe `valor` y el campo visible muestra `etiqueta` (la fila la trae); al volver a teclear, el destino se vacía. Es lo que viaja en el POST y el servidor lo valida (Cambio 420: el par `usuario:rol` del Equipo). Sin el atributo, y sin `etiqueta`, el comportamiento es el de siempre.
- `attrs_sugerencias(url, vacio=None)` acepta otro aviso de vacío (el paso «Ingresar persona» no manda a «Ingresar persona»).
- Se carga con `nodo-sugerencias.css` (`{% block page_css %}`) y `nodo-sugerencias.js`
  (`{% block customJS %}`) **solo en la pantalla que la usa**, no en `base.html`.
- El formulario Django pone los atributos con `attrs_sugerencias(url)` de `core/forms_sugerencias.py`
  (que también guarda los textos), en el `widget.attrs` (ver `url_sugerencias` en `ReservarPlazaForm`); sin la URL no se agrega nada y el campo queda como siempre.
- El JS envuelve el input en `.nodo-sugerencias` y agrega un panel con `ul[role=listbox]` y un
  aviso `role=status`. Sin dependencias: no usa Alpine.

## Comportamiento

- Mínimo 3 caracteres, espera de 250 ms, y cada consulta nueva cancela la anterior (`AbortController`).
- Combobox accesible: `role=combobox`, `aria-expanded`, `aria-controls`, `aria-activedescendant`;
  flechas recorren, Enter elige la marcada (sin marcada, envía el formulario), Escape cierra la lista
  sin llegar al modal.
- Todo texto del servidor entra con `textContent`, nunca con `innerHTML`.
- Si la consulta falla (403, red), se calla y el campo sigue siendo un input común.

## Contrato del endpoint

`GET ?q=` → `{"resultados": [{"apellido", "nombre", "dni"}], "hay_mas": bool}` (la fila puede sumar `valor` y `etiqueta`). Tope de 10, mínimo
de 3 caracteres; solo esas tres claves, nunca teléfono, correo ni domicilio. Búsqueda por prefijo
(`istartswith` → `LIKE 'x%'`, sin función sobre la columna; nunca `startswith`, que en MySQL/MariaDB es `LIKE BINARY` y recorre todo el índice). El endpoint de cada pantalla aplica la misma
capacidad y alcance que la acción que completa el campo.

## Selectores

- Los dos selectores comparten `normalizar_tecleado`, `palabras_del_tecleado` y `q_prefijo_por_palabras` de
  `users/services/busqueda.py` (100 caracteres, 5 palabras, `istartswith`), y los endpoints responden con `sin_cache`
  de `core/http_cache.py` (`Cache-Control: no-store`).
- Personas del Legajo: `programas/selectors/personas_sugeridas.py`. Con palabras, **una consulta por columna**
  (apellido y nombre) unidas en Python, ordenadas como la collation de la base (sin tildes ni mayúsculas): el `OR` entre columnas lo resuelve MySQL con `index_merge` y, con un prefijo
  común, ordena todo lo que coincide antes de cortar (200k filas: 51 ms contra 0,7 ms).
- Equipo (Cambio 420): `programas/selectors/equipo_sugeridas.py`, los pares «Persona — Rol» de `pares_persona_rol` filtrados por
  nombre o apellido (prefijo, una sola consulta sobre los enlaces usuario-rol); la fila trae `apellido`, `nombre`, `rol`, `valor` y
  `etiqueta`, nunca correo, teléfono ni DNI. Su endpoint pide `puede_gestionar_equipo`.
- Agentes (usuarios): `programas/selectors/agentes_sugeridos.py`, solo por nombre, con el DNI **enmascarado**; DNI y
  correo siguen siendo búsqueda exacta en el buscador completo. Su endpoint (`users:usuario_sugerir_agente`) tiene
  la misma guarda que ese buscador.
