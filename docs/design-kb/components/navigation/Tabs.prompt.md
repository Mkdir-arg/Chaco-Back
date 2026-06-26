**Tabs** — horizontal tab bar with an underline indicator on the active item; controlled or uncontrolled.

```jsx
<Tabs defaultValue="datos" tabs={[
  { value: 'datos', label: 'Datos', icon: 'fas fa-user' },
  { value: 'familia', label: 'Grupo familiar', count: 4 },
  { value: 'archivos', label: 'Archivos' },
]} onChange={setTab} />
```

Props: `tabs` (string[] or {value,label,icon,count}[]), `value`/`defaultValue`, `onChange`.
