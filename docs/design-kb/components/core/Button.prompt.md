**Button** — the primary clickable control; `brand` variant carries the signature magenta→purple gradient and should appear once per view as the main CTA.

```jsx
<Button variant="brand" size="lg" icon="fas fa-plus">Nuevo legajo</Button>
<Button variant="secondary" icon="fas fa-filter">Filtrar</Button>
<Button variant="tertiary">Cancelar</Button>
<Button variant="danger" size="sm" icon="fas fa-trash">Eliminar</Button>
```

Variants: `brand` (gradient CTA), `primary` (solid jacaranda), `secondary` (neutral bordered), `tertiary` (white + brand outline), `ghost`, `danger`.
Sizes: `xs` `sm` `base` `lg` `xl`. Props: `icon` / `iconRight` (Font Awesome class), `block`, `disabled`.
