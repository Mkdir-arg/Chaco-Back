# Componente · Sugerencias de personas (`nodo-sugerencias.js`, `.nodo-sugerencias`)

**Clasificación:** Canónico reutilizable. Pieza única.
**Evidencia:** `static/custom/js/nodo-sugerencias.js`, `static/custom/css/nodo-sugerencias.css`,
`programas/selectors/personas_sugeridas.py`, `programas/views/dispositivos_legajo.py`
(`PersonasSugeridasView`).
**Consumidores de referencia:** el DNI de «Reservar» y «Prestar» en el modal de una plaza
(`programas/templates/programas/dispositivos/sectores/sectores.html`).

Mejora progresiva sobre un `<input>` de texto que ya existe: desde 3 caracteres muestra
la persona que coincide, o la lista, y al elegir una completa el campo con su DNI. No
reemplaza al campo ni a la validación: el input es el que viaja en el POST y el servidor
(`clean_dni`, `buscar_ciudadano_por_dni`) decide igual que sin la pieza.

## Contrato

```html
<input class="nodo-field" data-sugerencias-url="/dispositivos/7/personas/buscar/"
       data-sugerencias-vacio="No encontramos a nadie: …"
       data-sugerencias-hay-mas="Hay más resultados: escribí más datos.">
```

- Se carga con `nodo-sugerencias.css` (`{% block page_css %}`) y `nodo-sugerencias.js`
  (`{% block customJS %}`) **solo en la pantalla que la usa**, no en `base.html`.
- El formulario Django pone los atributos con `widget.attrs` (ver `url_sugerencias` en
  `ReservarPlazaForm`); sin la URL no se agrega nada y el campo queda como siempre.
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

`GET ?q=` → `{"resultados": [{"apellido", "nombre", "dni"}], "hay_mas": bool}`. Tope de 10, mínimo
de 3 caracteres; solo esas tres claves, nunca teléfono, correo ni domicilio. Búsqueda por prefijo
(`LIKE 'x%'`, sin función sobre la columna). El endpoint de cada pantalla aplica la misma
capacidad y alcance que la acción que completa el campo.
