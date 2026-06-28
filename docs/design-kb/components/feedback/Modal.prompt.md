**Modal** — centered dialog over a dimmed, blurred backdrop; tinted header icon, body and action footer.

```jsx
<Modal title="Confirmar baja" tone="danger" onClose={close}
  footer={<>
    <Button variant="secondary" onClick={close}>Cancelar</Button>
    <Button variant="danger">Dar de baja</Button>
  </>}>
  ¿Querés dar de baja este legajo? Esta acción no se puede deshacer.
</Modal>
```

Props: `open`, `title`, `tone` (info/success/warning/danger/brand), `icon`, `footer`, `onClose`, `width`.
