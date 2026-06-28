**Input** — labelled text field with optional leading icon, helper text and error state. Brand focus ring; rose on error.

```jsx
<Input label="DNI" placeholder="00.000.000" icon="fas fa-id-card" required />
<Input label="Email" type="email" error="Ingresá un correo válido" />
```

Props: `label`, `value`/`defaultValue`, `placeholder`, `type`, `icon` (FA class), `error`, `helper`, `required`, `disabled`, `onChange`.
