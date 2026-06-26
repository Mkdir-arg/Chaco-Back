**Card** — the base white surface (12px radius, hairline border, soft shadow). Wraps content, with optional header/footer slots and a top accent stripe.

```jsx
<Card title="Datos del legajo" subtitle="Actualizado hoy" headerRight={<Badge variant="success" dot>Activo</Badge>}>
  …contenido…
</Card>

<Card hover accent="var(--bg-brand)">…</Card>
```

Props: `title`, `subtitle`, `headerRight`, `footer`, `padding`, `hover`, `accent`.
