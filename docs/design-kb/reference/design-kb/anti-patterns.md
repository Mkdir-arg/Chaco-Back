# Anti-Patterns
**NODO Design System — What NOT to do**

---

## A. Color & Token Violations

### AP-C01: Hardcoded hex values in components
```css
/* ❌ WRONG */
.card { background: #f9fafb; border: 1px solid #e5e7eb; }
.button-primary { background: #5059bc; }

/* ✅ CORRECT */
.card { background: var(--bg-secondary-soft); border: var(--border-width) solid var(--border-base); }
.button-primary { background: var(--bg-brand); }
```

### AP-C02: Using opacity as disabled state substitute
```css
/* ❌ WRONG */
button:disabled { opacity: 0.5; }

/* ✅ CORRECT */
button:disabled { background: var(--bg-disabled); color: var(--text-fg-disabled); border-color: var(--border-base); }
```

### AP-C03: Using text-heading or text-body on colored backgrounds
```css
/* ❌ WRONG — text-heading on bg-brand surface */
<div class="bg-brand text-heading">Brand button label</div>

/* ✅ CORRECT */
<div class="bg-brand text-white">Brand button label</div>
/* Or use text-fg-brand-strong inside brand-colored alerts/badges */
```

### AP-C04: Creating ad-hoc colors outside the system
```css
/* ❌ WRONG */
.custom-badge { background: #ff6600; color: white; }

/* ✅ CORRECT — use warning tokens */
<span class="badge-warning">Status</span>
```

### AP-C05: Using color as the only state communicator
```html
<!-- ❌ WRONG — only red text, no icon or label change -->
<p style="color: red">Email incorrecto</p>

<!-- ✅ CORRECT — color + icon + specific message -->
<p class="text-fg-danger text-xs flex items-center gap-1">
  <ExclamationCircleIcon class="w-4 h-4" /> El email no es válido
</p>
```

---

## B. Typography Violations

### AP-T01: Using Gellat outside access screens
```html
<!-- ❌ WRONG — Gellat in a dashboard card heading -->
<h2 class="font-brand text-xl">Ciudadanos en Tratamiento</h2>

<!-- ✅ CORRECT — Inter for all internal UI -->
<h2 class="font-sans font-semibold text-xl text-heading">Ciudadanos en Tratamiento</h2>
```

### AP-T02: Arbitrary font sizes outside the scale
```css
/* ❌ WRONG */
.heading { font-size: 22px; }

/* ✅ CORRECT — use scale (text-xl = 20px, text-2xl = 24px) */
.heading { font-size: var(--font-size-2xl); }
```

### AP-T03: font-normal on button labels
```html
<!-- ❌ WRONG -->
<button class="btn-brand font-normal">Guardar</button>

<!-- ✅ CORRECT -->
<button class="btn-brand font-medium">Guardar</button>
```

### AP-T04: Placeholder used as field label
```html
<!-- ❌ WRONG -->
<input type="text" placeholder="Email" />

<!-- ✅ CORRECT -->
<label>Email institucional</label>
<input type="text" placeholder="usuario@chaco.gov.ar" />
```

---

## C. Layout Violations

### AP-L01: Split-screen layout on internal screens
```html
<!-- ❌ WRONG — split screen for a list view -->
<div class="flex">
  <div class="w-60%">Illustration</div>
  <div class="w-40%">Citizen table</div>
</div>

<!-- ✅ CORRECT — only for authentication -->
<!-- Split screen is ONLY for login and password recovery -->
```

### AP-L02: Full-width form within content area
```html
<!-- ❌ WRONG -->
<form class="w-full">...</form>

<!-- ✅ CORRECT -->
<form class="max-w-[700px] mx-auto">...</form>
```

### AP-L03: Primary CTA left-aligned
```html
<!-- ❌ WRONG -->
<div class="flex">
  <button class="btn-brand">⊕ Nuevo legajo</button>
</div>

<!-- ✅ CORRECT -->
<div class="flex justify-between items-center">
  <h1>Ciudadanos</h1>
  <button class="btn-brand">⊕ Nuevo legajo</button>
</div>
```

---

## D. Component Violations

### AP-CO01: Two Brand buttons in the same section
```html
<!-- ❌ WRONG -->
<div>
  <button class="btn-brand">Guardar borrador</button>
  <button class="btn-brand">Publicar</button>
</div>

<!-- ✅ CORRECT — one Brand, one Tertiary or Secondary -->
<div>
  <button class="btn-tertiary">Guardar borrador</button>
  <button class="btn-brand">Publicar →</button>
</div>
```

### AP-CO02: Destructive action without SweetAlert2 confirmation
```javascript
// ❌ WRONG
deleteButton.onclick = () => fetch('/api/citizen/delete/123');

// ❌ ALSO WRONG
deleteButton.onclick = () => { if(confirm('Are you sure?')) fetch(...) };

// ✅ CORRECT
deleteButton.onclick = () => {
  Swal.fire({
    title: '¿Estás seguro?',
    text: 'Esta acción no se puede deshacer.',
    showCancelButton: true,
    confirmButtonText: 'Eliminar',
  }).then(result => {
    if (result.isConfirmed) fetch('/api/citizen/delete/123');
  });
};
```

### AP-CO03: Table without empty state
```html
<!-- ❌ WRONG — blank table body -->
<tbody></tbody>

<!-- ✅ CORRECT -->
<tbody>
  {% if not citizens %}
  <tr><td colspan="8">
    <div class="empty-state">
      <UserGroupIcon class="w-12 h-12 text-body-subtle" />
      <p class="text-heading font-semibold">No hay ciudadanos registrados</p>
    </div>
  </td></tr>
  {% endif %}
</tbody>
```

### AP-CO04: Removing focus rings for "aesthetic" reasons
```css
/* ❌ WRONG — accessibility violation */
* { outline: none; }
button:focus { outline: none; }

/* ✅ CORRECT — always keep visible focus */
button:focus { outline: 2px solid var(--border-brand); }
```

### AP-CO05: Arbitrary z-index values
```css
/* ❌ WRONG */
.my-modal { z-index: 9999; }
.my-dropdown { z-index: 500; }

/* ✅ CORRECT — use the defined z-index scale */
/* base=0, dropdown=10, modal=100, toast=200 */
.my-modal { z-index: 100; }
.my-dropdown { z-index: 10; }
```

---

## E. Icon Violations

### AP-I01: Mixing icon libraries in the same component
```html
<!-- ❌ WRONG — Heroicons + Font Awesome mixed -->
<div>
  <UserIcon /> <!-- Heroicons -->
  <i class="fa-solid fa-trash"></i> <!-- Font Awesome -->
</div>

<!-- ✅ CORRECT — Heroicons only in new templates -->
<div>
  <UserIcon />
  <TrashIcon />
</div>
```

### AP-I02: Hardcoded color on icon
```html
<!-- ❌ WRONG -->
<BellIcon style="color: #5059bc" />

<!-- ✅ CORRECT -->
<BellIcon class="text-fg-brand" />
```

---

## F. Error Handling Violations

### AP-E01: Exposing technical details to users
```python
# ❌ WRONG — Django view returning exception detail
return JsonResponse({'error': str(e)}, status=500)

# ✅ CORRECT
return JsonResponse({'error': 'Error al procesar la solicitud. Intenta nuevamente.'}, status=500)
```

### AP-E02: Auto-dismissing error toasts
```javascript
// ❌ WRONG — error silently disappears
toastr.error('Error al guardar.', '', { timeOut: 3000 });

// ✅ CORRECT — errors persist until dismissed
toastr.error('Error al guardar.', '', { timeOut: 0, closeButton: true });
```
