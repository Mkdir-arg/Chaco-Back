**StatCard** — dashboard KPI tile: tinted icon square, large value, label and an optional trend indicator.

```jsx
<StatCard label="Legajos activos" value="1.284" icon="fas fa-folder-open"
          tone="brand" change="8%" changeDir="up" footnote="vs. mes anterior" />
```

Props: `label`, `value`, `icon` (FA class), `tone` (brand/success/warning/danger/olive/neutral), `change`, `changeDir` (up/down/flat), `footnote`.
