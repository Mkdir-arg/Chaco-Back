(function () {
  const trashIcon = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0"/></svg>';

  function labelFor(control) {
    if (control.getAttribute('aria-label')) return control.getAttribute('aria-label');
    if (control.id) {
      const label = control.form.querySelector('label[for="' + CSS.escape(control.id) + '"]');
      if (label) return label.textContent.replace('*', '').trim();
    }
    if (control.placeholder) return control.placeholder;
    if (control.tagName === 'SELECT' && control.options.length) {
      return control.options[0].textContent.trim().replace(/^[-—]\s*/, '');
    }
    return control.name.replace(/_/g, ' ').replace(/^./, c => c.toUpperCase());
  }

  function isActive(control) {
    if (control.type === 'checkbox' || control.type === 'radio') return control.checked;
    return String(control.value || '').trim() !== '';
  }

  function init(form) {
    if (form.dataset.dynamicReady === 'true') return;
    form.dataset.dynamicReady = 'true';
    const originals = Array.from(form.querySelectorAll('input[name], select[name]'))
      .filter(el => !['hidden', 'submit', 'button'].includes(el.type));
    if (!originals.length) return;

    const definitions = originals.map(control => ({
      name: control.name,
      label: labelFor(control),
      template: control.cloneNode(true),
      active: isActive(control),
      value: control.value,
      checked: control.checked,
    }));
    const hidden = Array.from(form.querySelectorAll('input[type="hidden"]')).map(el => el.cloneNode(true));
    form.innerHTML = '';
    form.className = 'dynamic-list-filters';
    form.removeAttribute('style');
    hidden.forEach(el => form.appendChild(el));
    const componentTemplate = document.getElementById('nodo-list-filters-template');
    if (!componentTemplate) return;
    form.appendChild(componentTemplate.content.cloneNode(true));
    const add = form.querySelector('[data-list-filter-add]');
    const rows = form.querySelector('[data-list-filter-rows]');
    const footer = form.querySelector('[data-list-filter-footer]');
    const clear = form.querySelector('[data-list-filter-clear]');
    clear.href = window.location.pathname;

    function syncVisibility() {
      const hasRows = rows.children.length > 0;
      footer.hidden = !hasRows;
      rows.hidden = !hasRows;
      add.disabled = rows.children.length >= definitions.length;
    }

    function usedNames(exceptRow) {
      return new Set(Array.from(rows.children).filter(row => row !== exceptRow).map(row => row.dataset.field));
    }

    function addRow(definition) {
      const used = usedNames();
      const available = definitions.filter(def => !used.has(def.name));
      const initial = definition || available[0];
      if (!initial) return;
      const row = document.createElement('div');
      row.className = 'dynamic-list-filters__row';
      const field = document.createElement('select');
      field.className = 'nodo-field dynamic-list-filters__field';
      definitions.filter(def => def.name === initial.name || !used.has(def.name)).forEach(def => {
        field.add(new Option(def.label, def.name));
      });
      field.value = initial.name;
      const operator = document.createElement('select');
      operator.className = 'nodo-field dynamic-list-filters__operator';
      const remove = document.createElement('button');
      remove.type = 'button'; remove.className = 'dynamic-list-filters__remove'; remove.title = 'Quitar filtro';
      remove.setAttribute('aria-label', 'Quitar filtro'); remove.innerHTML = trashIcon;
      let valueControl;

      function renderValue(def, preserve) {
        if (valueControl) valueControl.remove();
        valueControl = def.template.cloneNode(true);
        valueControl.className = 'nodo-field dynamic-list-filters__value';
        valueControl.removeAttribute('style');
        valueControl.removeAttribute('onchange');
        valueControl.removeAttribute('oninput');
        valueControl.removeAttribute('onkeyup');
        valueControl.removeAttribute('@change');
        valueControl.removeAttribute('x-on:change');
        valueControl.name = def.name;
        if (!preserve || def.name !== initial.name) {
          if (valueControl.type === 'checkbox' || valueControl.type === 'radio') valueControl.checked = false;
          else valueControl.value = '';
        }
        operator.innerHTML = '<option>' + (valueControl.tagName === 'SELECT' || ['date', 'month', 'number'].includes(valueControl.type) ? 'Igual a' : 'Contiene') + '</option>';
        row.insertBefore(valueControl, remove);
        row.dataset.field = def.name;
      }
      field.addEventListener('change', () => renderValue(definitions.find(def => def.name === field.value), false));
      remove.addEventListener('click', () => {
        row.remove();
        syncVisibility();
      });
      row.append(field, operator, remove);
      rows.appendChild(row);
      renderValue(initial, Boolean(definition));
      syncVisibility();
    }

    definitions.filter(def => def.active).forEach(addRow);
    add.addEventListener('click', () => addRow());
    syncVisibility();
  }

  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('form[data-dynamic-list-filters]').forEach(init);
  });
})();
