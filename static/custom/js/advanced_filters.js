(function () {
    const form = document.getElementById('filters-form');
    if (!form) {
        return;
    }

    const configId = form.dataset.configId;
    if (!configId) {
        console.warn('AdvancedFilters: falta data-config-id en el formulario.');
        return;
    }

    const configScript = document.getElementById(configId);
    if (!configScript) {
        console.warn('AdvancedFilters: no se encontró el script con la configuración.');
        return;
    }

    let config;
    try {
        config = JSON.parse(configScript.textContent);
    } catch (error) {
        console.error('AdvancedFilters: configuración inválida.', error);
        return;
    }

    const rowsContainer = document.getElementById('filters-rows');
    const addBtn = document.getElementById('add-filter');
    const logicSelect = document.getElementById('filters-logic');
    const hiddenInput = document.getElementById('filters-input');
    const footer = document.getElementById('filters-footer');

    if (!rowsContainer || !addBtn || !logicSelect || !hiddenInput || !footer) {
        console.warn('AdvancedFilters: faltan elementos requeridos en el DOM.');
        return;
    }

    function syncVisibility() {
        const hasRows = rowsContainer.children.length > 0;
        rowsContainer.hidden = !hasRows;
        footer.hidden = !hasRows;
    }

    const operatorLabels = Object.assign(
        {
            contains: 'Contiene',
            ncontains: 'No contiene',
            eq: 'Igual a',
            ne: 'Distinto de',
            gt: 'Mayor a',
            lt: 'Menor a',
            empty: 'Vacío',
        },
        config.operatorLabels || {}
    );

    const defaultOpByType = Object.assign(
        {
            text: 'contains',
            number: 'eq',
            boolean: 'eq',
            choice: 'eq',
        },
        config.defaultOperators || {}
    );

    const booleanOptions = config.booleanOptions || [
        { value: 'true', label: 'Sí' },
        { value: 'false', label: 'No' },
    ];

    const emptyModeOptions = [
        { value: 'both', label: 'Nulos o vacíos' },
        { value: 'null', label: 'Solo nulos' },
        { value: 'blank', label: 'Solo vacíos' },
    ];

    const fields = Array.isArray(config.fields) ? config.fields : [];
    if (!fields.length) {
        console.warn('AdvancedFilters: no hay campos configurados.');
        return;
    }

    const operatorsByType = Object.assign(
        {
            text: ['contains', 'ncontains', 'eq', 'ne', 'empty'],
            number: ['eq', 'ne', 'gt', 'lt', 'empty'],
            boolean: ['eq', 'ne'],
            choice: ['eq', 'ne'],
        },
        config.operators || {}
    );

    const fieldsByName = fields.reduce((acc, field) => {
        if (field && field.name) {
            acc[field.name] = field;
        }
        return acc;
    }, {});

    const fieldOptions = fields
        .filter(field => field && field.name && field.label)
        .map(field => ({ value: field.name, label: field.label }));

    if (!fieldOptions.length) {
        console.warn('AdvancedFilters: no hay campos válidos para mostrar.');
        return;
    }

    function createSelect(className, options) {
        const select = document.createElement('select');
        select.className = className;
        if (Array.isArray(options)) {
            populateOptions(select, options);
        }
        return select;
    }

    function createOption(value, label) {
        const option = document.createElement('option');
        option.value = value;
        option.textContent = label;
        return option;
    }

    function populateOptions(select, options) {
        select.innerHTML = '';
        options.forEach(opt => {
            select.appendChild(createOption(opt.value, opt.label));
        });
    }

    function getFieldDefinition(name) {
        return fieldsByName[name];
    }

    function getOperatorsFor(fieldType) {
        const ops = operatorsByType[fieldType];
        if (!Array.isArray(ops) || !ops.length) {
            return operatorsByType.text;
        }
        return ops;
    }

    function getOperatorOptions(fieldType) {
        return getOperatorsFor(fieldType).map(op => ({
            value: op,
            label: operatorLabels[op] || op,
        }));
    }

    function getChoiceOptions(fieldDef) {
        if (fieldDef.type === 'boolean') {
            return booleanOptions;
        }
        return Array.isArray(fieldDef.choices) ? fieldDef.choices : [];
    }

    function applyInputAttributes(input, fieldDef) {
        input.removeAttribute('step');
        input.removeAttribute('min');
        input.removeAttribute('max');
        input.removeAttribute('pattern');

        if (fieldDef.type === 'number') {
            input.type = 'number';
            const attrs = fieldDef.input || {};
            input.step = attrs.step || '1';
            if (attrs.min !== undefined) {
                input.min = attrs.min;
            }
            if (attrs.max !== undefined) {
                input.max = attrs.max;
            }
        } else {
            input.type = 'text';
        }
    }

    function disableBlankOption(emptyModeSel, disabled) {
        Array.from(emptyModeSel.options).forEach(opt => {
            if (opt.value === 'blank') {
                opt.disabled = disabled;
            }
        });
        if (disabled && emptyModeSel.value === 'blank') {
            emptyModeSel.value = 'both';
        }
    }

    function addRow(prefill) {
        const row = document.createElement('div');
        row.className = 'dynamic-list-filters__row';

        const fieldSel = createSelect('nodo-field', fieldOptions);
        fieldSel.classList.add('dynamic-list-filters__field');
        const opSel = createSelect('nodo-field');
        opSel.classList.add('dynamic-list-filters__operator');
        const valueInput = document.createElement('input');
        valueInput.type = 'text';
        valueInput.className = 'nodo-field dynamic-list-filters__value';
        valueInput.placeholder = 'Valor';

        const selectValue = createSelect('nodo-field');
        selectValue.classList.add('dynamic-list-filters__value');
        selectValue.style.display = 'none';

        const emptyModeSel = createSelect('nodo-field', emptyModeOptions);
        emptyModeSel.classList.add('dynamic-list-filters__value');
        emptyModeSel.style.display = 'none';

        const removeBtn = document.createElement('button');
        removeBtn.type = 'button';
        removeBtn.className = 'dynamic-list-filters__remove';
        removeBtn.setAttribute('aria-label', 'Quitar filtro');
        removeBtn.title = 'Quitar filtro';
        removeBtn.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0"/></svg>';

        const refs = {
            fieldSel,
            opSel,
            valueInput,
            selectValue,
            emptyModeSel,
        };

        function currentFieldDef() {
            return getFieldDefinition(fieldSel.value) || fields[0];
        }

        function refreshOperators(preserveCurrent) {
            const fieldDef = currentFieldDef();
            const options = getOperatorOptions(fieldDef.type);
            const previous = preserveCurrent ? opSel.value : null;
            populateOptions(opSel, options);

            const defaultOp = defaultOpByType[fieldDef.type] || options[0]?.value;
            opSel.value = options.some(opt => opt.value === previous)
                ? previous
                : defaultOp;
        }

        function refreshSelectOptions(fieldDef, prefillValue) {
            const options = getChoiceOptions(fieldDef);
            if (!options.length) {
                selectValue.innerHTML = '';
                return;
            }

            populateOptions(selectValue, options);
            if (prefillValue !== undefined) {
                selectValue.value = prefillValue;
                if (selectValue.value !== prefillValue) {
                    // si el valor no existe, agregarlo temporalmente
                    selectValue.appendChild(createOption(prefillValue, prefillValue));
                    selectValue.value = prefillValue;
                }
            }
        }

        function adjustVisibility(prefillValue) {
            const fieldDef = currentFieldDef();
            const operator = opSel.value;
            const type = fieldDef.type;

            if (operator === 'empty') {
                valueInput.style.display = 'none';
                selectValue.style.display = 'none';
                emptyModeSel.style.display = 'inline-block';
                disableBlankOption(emptyModeSel, type === 'number' || type === 'boolean');
                return;
            }

            emptyModeSel.style.display = 'none';

            if (type === 'choice' || type === 'boolean') {
                refreshSelectOptions(fieldDef, prefillValue);
                selectValue.style.display = 'inline-block';
                valueInput.style.display = 'none';
                return;
            }

            selectValue.style.display = 'none';
            valueInput.style.display = 'inline-block';
            applyInputAttributes(valueInput, fieldDef);

            if (prefillValue !== undefined) {
                valueInput.value = prefillValue;
            }
        }

        fieldSel.addEventListener('change', () => {
            const fieldDef = currentFieldDef();
            refreshOperators(false);
            adjustVisibility();
            if (fieldDef.type !== 'choice' && fieldDef.type !== 'boolean') {
                valueInput.value = '';
            } else {
                selectValue.value = getChoiceOptions(fieldDef)[0]?.value || '';
            }
        });

        opSel.addEventListener('change', () => adjustVisibility());
        removeBtn.addEventListener('click', () => {
            row.remove();
            syncVisibility();
        });

        row.appendChild(fieldSel);
        row.appendChild(opSel);
        row.appendChild(valueInput);
        row.appendChild(selectValue);
        row.appendChild(emptyModeSel);
        row.appendChild(removeBtn);
        rowsContainer.appendChild(row);

        // Prefill / defaults
        if (prefill) {
            if (prefill.field && fieldsByName[prefill.field]) {
                fieldSel.value = prefill.field;
            }
            refreshOperators(true);
            if (prefill.op) {
                opSel.value = prefill.op;
            }
            adjustVisibility(prefill.op === 'empty' ? undefined : prefill.value);

            if (opSel.value === 'empty' && prefill.empty_mode) {
                emptyModeSel.value = prefill.empty_mode;
            } else if (prefill.value !== undefined) {
                const fieldDef = currentFieldDef();
                if (fieldDef.type === 'choice' || fieldDef.type === 'boolean') {
                    refreshSelectOptions(fieldDef, prefill.value);
                } else {
                    valueInput.value = String(prefill.value);
                }
            }
        } else {
            fieldSel.value = fieldOptions[0].value;
            refreshOperators(false);
            adjustVisibility();
        }

        row._advancedFilterRefs = refs;
        syncVisibility();
    }

    addBtn.addEventListener('click', () => addRow());

    form.addEventListener('submit', () => {
        const items = [];
        const rows = rowsContainer.children;

        for (let i = 0; i < rows.length; i += 1) {
            const refs = rows[i]._advancedFilterRefs;
            if (!refs) {
                continue;
            }

            const field = refs.fieldSel.value;
            const op = refs.opSel.value;
            const fieldDef = getFieldDefinition(field);
            if (!fieldDef || !field || !op) {
                continue;
            }

            if (op === 'empty') {
                items.push({ field, op, empty_mode: refs.emptyModeSel.value || 'both' });
                continue;
            }

            if (fieldDef.type === 'choice' || fieldDef.type === 'boolean') {
                const selected = refs.selectValue.value;
                if (selected !== '') {
                    items.push({ field, op, value: selected });
                }
                continue;
            }

            const rawValue = refs.valueInput.value.trim();
            if (rawValue !== '') {
                items.push({ field, op, value: rawValue });
            }
        }

        const logic = logicSelect.value || 'AND';
        hiddenInput.value = items.length ? JSON.stringify({ logic, items }) : '';
    });

    function loadFromQuerystring() {
        try {
            const params = new URLSearchParams(window.location.search);
            const raw = params.get('filters');
            if (!raw) {
                return false;
            }
            const parsed = JSON.parse(raw);
            if (!parsed || !Array.isArray(parsed.items) || !parsed.items.length) {
                return false;
            }

            logicSelect.value = parsed.logic === 'OR' ? 'OR' : 'AND';
            parsed.items.forEach(item => addRow(item));
            return true;
        } catch (error) {
            console.warn('AdvancedFilters: no se pudo reconstruir filtros desde la URL.', error);
            return false;
        }
    }

    loadFromQuerystring();
    syncVisibility();
})();
