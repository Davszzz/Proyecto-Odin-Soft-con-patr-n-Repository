/* Odin Soft | Búsqueda reutilizable de tablas ya renderizadas.
 * data-ui-search: id de tabla; data-search-columns: índices (base 0) de búsqueda/sugerencias;
 * data-search-filters: JSON objeto {etiqueta: índice de columna o clave data-search-* de fila}.
 * No envía consultas, no cambia datos, no depende de plugins externos.
 */
(() => {
  'use strict';
  const clean = value => String(value ?? '').replace(/\s+/g, ' ').trim();
  const normalize = value => clean(value).normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('es-PE');
  const matches = (value, query) => normalize(query).split(/\s+/).every(word => normalize(value).includes(word));
  const unique = values => [...new Map(values.filter(Boolean).map(v => [normalize(v), v])).values()]
    .sort((a, b) => a.localeCompare(b, 'es', {numeric: true, sensitivity: 'base'}));
  const el = (tag, cls, text) => {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  };

  function enhance(input) {
    const id = input.dataset.uiSearch;
    const table = document.getElementById(id);
    const label = input.closest('label');
    if (!table || !label || !table.tBodies.length || input.dataset.searchReady) return;
    input.dataset.searchReady = '1';
    const body = table.tBodies[0];
    const columnCount = table.tHead?.rows[0]?.cells.length || 1;
    // Las filas vacías del servidor tienen colspan. No deben convertirse en registros.
    const rows = Array.from(body.rows).filter(row => row.cells.length === columnCount && !row.cells[0].hasAttribute('colspan'));
    const columns = (input.dataset.searchColumns || '0').split(',').map(Number).filter(n => Number.isInteger(n) && n >= 0 && n < columnCount);
    let filterSpec = {};
    try { filterSpec = JSON.parse(input.dataset.searchFilters || '{}'); } catch (_) { /* búsqueda aún disponible */ }
    const cellText = (row, index) => {
      const cell = row.cells[index];
      if (!cell) return '';
      // Para clientes con avatar, sugerir nombre y correo sin incluir la inicial decorativa.
      const title = cell.querySelector('.ui-title-cell');
      const subline = cell.querySelector('.ui-subline');
      if (title && subline) return clean(`${title.textContent} ${subline.textContent}`);
      return clean(cell.innerText || cell.textContent);
    };
    const filterValue = (row, key) => typeof key === 'number' ? cellText(row, key) : clean(row.getAttribute(`data-search-${key}`));
    const headers = Array.from(table.tHead.rows[0].cells);
    const collator = new Intl.Collator('es-PE', {numeric: true, sensitivity: 'base'});
    const sortable = headers.map((th, index) => ({th, index, type: th.dataset.sortType || 'text'}))
      .filter(({type}) => type !== 'none');
    const defaultColumn = Number(table.dataset.sortColumn || 0);
    const defaultSort = {index: sortable.some(c => c.index === defaultColumn) ? defaultColumn : sortable[0]?.index,
      direction: table.dataset.sortDirection === 'desc' ? -1 : 1};
    let sort = {...defaultSort};
    let page = 1;
    let pageSize = 10;
    const sortValue = (row, index, type) => {
      const cell = row.cells[index];
      const value = clean(cell.dataset.sortValue ?? cellText(row, index));
      if (!value || ['—', '-', 'Sin definir', 'None', 'null'].includes(value)) return null;
      if (type === 'number') { const n = Number(value); return Number.isFinite(n) ? n : null; }
      if (type === 'date') { const n = Date.parse(value); return Number.isFinite(n) ? n : null; }
      return value;
    };
    const records = rows.map((row, originalIndex) => {
      // Conservar búsqueda libre sobre columnas visibles, excepto acciones.
      const text = headers.map((th, index) => th.dataset.sortType === 'none' ? '' : cellText(row, index)).join(' ');
      const suggestions = columns.flatMap(index => {
        const cell = row.cells[index];
        const title = cell?.querySelector('.ui-title-cell, strong');
        const subline = cell?.querySelector('.ui-subline');
        return title && subline ? [clean(title.textContent), clean(subline.textContent)] : [cellText(row, index)];
      }).filter(v => v && v !== '—' && v !== '-' && v !== 'Sin SKU');
      return {row, text, suggestions, originalIndex, sortValues: headers.map((th, i) => sortValue(row, i, th.dataset.sortType || "text"))};
    });

    const panel = el('div', 'odin-search-panel');
    label.parentNode.insertBefore(panel, label);
    const controls = el('div', 'odin-search-controls');
    panel.append(controls);
    const field = el('div', 'odin-search-field');
    controls.append(field);
    field.append(label);
    const list = el('div', 'odin-search-suggestions');
    list.id = `${id}-suggestions`;
    list.setAttribute('role', 'listbox');
    list.setAttribute('aria-label', 'Sugerencias de búsqueda');
    list.hidden = true;
    field.append(list);
    input.setAttribute('role', 'combobox');
    input.setAttribute('aria-autocomplete', 'list');
    input.setAttribute('aria-controls', list.id);
    input.setAttribute('aria-expanded', 'false');
    input.setAttribute('autocomplete', 'off');
    const filters = Object.entries(filterSpec).map(([name, key]) => {
      const wrapper = el('label', 'odin-search-filter');
      wrapper.append(el('span', 'visually-hidden', name));
      const select = el('select', 'form-select form-select-sm');
      select.setAttribute('aria-label', name);
      const all = el('option', '', `${name}: todos`);
      all.value = '';
      select.append(all);
      unique(rows.map(row => filterValue(row, key))).forEach(value => {
        const option = el('option', '', value);
        option.value = normalize(value);
        select.append(option);
      });
      wrapper.append(select);
      controls.append(wrapper);
      return {select, key};
    });
    const clear = el('button', 'btn btn-outline-secondary btn-sm odin-search-clear', 'Restablecer vista');
    clear.type = 'button';
    controls.append(clear);
    const count = el('div', 'odin-search-count');
    count.setAttribute('role', 'status');
    count.setAttribute('aria-live', 'polite');
    panel.append(count);
    const empty = el('tr');
    const emptyCell = el('td', 'text-center text-muted py-4', 'No se encontraron coincidencias.');
    emptyCell.colSpan = columnCount;
    empty.append(emptyCell);
    empty.hidden = true;
    if (rows.length) body.append(empty);
    const wrapper = table.closest('.table-responsive');
    if (wrapper) {
      wrapper.classList.add('odin-table-scroll');
      wrapper.tabIndex = 0;
      wrapper.setAttribute('role', 'region');
      wrapper.setAttribute('aria-label', 'Tabla de registros');
    }
    table.classList.add('odin-managed-table');
    const footer = el('div', 'odin-table-footer');
    const sizeLabel = el('label', 'odin-table-size', 'Registros por página');
    const sizeSelect = el('select', 'form-select form-select-sm');
    [10, 25, 50, 100].forEach(n => {
      const option = el('option', '', String(n)); option.value = String(n); sizeSelect.append(option);
    });
    sizeLabel.append(sizeSelect); footer.append(sizeLabel);
    const nav = el('div', 'odin-table-nav');
    const prev = el('button', 'btn btn-outline-secondary btn-sm', 'Anterior'); prev.type = 'button';
    const next = el('button', 'btn btn-outline-secondary btn-sm', 'Siguiente'); next.type = 'button';
    const pageText = el('span', 'odin-table-page'); pageText.setAttribute('aria-live', 'polite');
    nav.append(prev, pageText, next); footer.append(nav);
    (wrapper || table).after(footer);
    const sortButtons = sortable.map(({th, index}) => {
      const name = clean(th.textContent);
      const button = el('button', 'odin-sort-button', name); button.type = 'button';
      const arrow = el('span', 'odin-sort-arrow'); arrow.setAttribute('aria-hidden', 'true');
      button.append(arrow); th.replaceChildren(button); th.scope = 'col';
      button.addEventListener('click', () => {
        sort = {index, direction: sort.index === index ? -sort.direction : 1}; page = 1; refresh(false);
      });
      return {th, index, button, arrow, name};
    });
    function updateHeaders() {
      sortButtons.forEach(({th, index, button, arrow, name}) => {
        const selected = index === sort.index;
        if (selected) th.setAttribute('aria-sort', sort.direction === 1 ? 'ascending' : 'descending');
        else th.removeAttribute('aria-sort');
        arrow.textContent = selected ? (sort.direction === 1 ? '↑' : '↓') : '↕';
        button.setAttribute('aria-label', `${name}: ordenar ${selected && sort.direction === 1 ? 'descendente' : 'ascendente'}`);
      });
    }
    let active = -1;
    let options = [];
    const close = () => {
      list.hidden = true;
      input.setAttribute('aria-expanded', 'false');
      input.removeAttribute('aria-activedescendant');
      active = -1;
    };
    const allowed = record => filters.every(({select, key}) => !select.value || normalize(filterValue(record.row, key)) === select.value);
    const selectSuggestion = value => {
      input.value = value;
      page = 1; refresh(false);
      input.focus();
      close();
    };
    function refresh(openSuggestions) {
      const query = input.value;
      const eligible = records.filter(allowed);
      const shown = eligible.filter(r => matches(r.text, query));
      if (sort.index !== undefined) shown.sort((a, b) => {
        const x = a.sortValues[sort.index], y = b.sortValues[sort.index];
        if (x === null || y === null) return x === y ? a.originalIndex - b.originalIndex : x === null ? 1 : -1;
        const cmp = typeof x === 'number' && typeof y === 'number' ? x - y : collator.compare(String(x), String(y));
        return cmp * sort.direction || a.originalIndex - b.originalIndex;
      });
      const pages = Math.max(1, Math.ceil(shown.length / pageSize));
      page = Math.min(page, pages);
      const offset = (page - 1) * pageSize;
      const visible = new Set(shown.slice(offset, offset + pageSize));
      records.forEach(record => { record.row.hidden = !visible.has(record); });
      // Mover nodos existentes: conservar formularios, valores, enlaces y eventos.
      const fragment = document.createDocumentFragment();
      shown.forEach(record => fragment.append(record.row));
      const matched = new Set(shown);
      records.filter(record => !matched.has(record)).forEach(record => fragment.append(record.row));
      if (rows.length) { fragment.append(empty); empty.hidden = shown.length !== 0; }
      body.append(fragment);
      count.textContent = `${shown.length} de ${records.length} registros · Mostrando ${shown.length ? offset + 1 : 0}–${Math.min(offset + pageSize, shown.length)}`;
      pageText.textContent = `Página ${page} de ${pages}`;
      prev.disabled = page <= 1; next.disabled = page >= pages;
      clear.disabled = !query && !filters.some(f => f.select.value) && sort.index === defaultSort.index && sort.direction === defaultSort.direction && pageSize === 10 && page === 1;
      updateHeaders();
      close();
      list.replaceChildren();
      options = [];
      if (!openSuggestions || !normalize(query)) return;
      // Coincidencias parciales también dentro de un nombre. Máximo 6 opciones.
      const candidates = unique(eligible.flatMap(r => r.suggestions).filter(v => matches(v, query)))
        .sort((a, b) => Number(normalize(b).startsWith(normalize(query))) - Number(normalize(a).startsWith(normalize(query)))).slice(0, 6);
      if (!candidates.length) return;
      candidates.forEach((value, index) => {
        const option = el('div', 'odin-search-option', value);
        option.id = `${list.id}-${index}`;
        option.setAttribute('role', 'option');
        option.setAttribute('aria-selected', 'false');
        option.addEventListener('pointerdown', event => event.preventDefault());
        option.addEventListener('click', () => selectSuggestion(value));
        list.append(option);
        options.push({option, value});
      });
      list.hidden = false;
      input.setAttribute('aria-expanded', 'true');
    }
    input.addEventListener('input', () => { page = 1; refresh(true); });
    input.addEventListener('focus', () => refresh(true));
    input.addEventListener('blur', close);
    input.addEventListener('keydown', event => {
      if (event.key === 'Escape') { close(); return; }
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        if (list.hidden) refresh(true);
        if (!options.length || list.hidden) return;
        event.preventDefault();
        active = active < 0 ? (event.key === 'ArrowDown' ? 0 : options.length - 1)
          : (active + (event.key === 'ArrowDown' ? 1 : -1) + options.length) % options.length;
        options.forEach(({option}, index) => option.setAttribute('aria-selected', String(index === active)));
        input.setAttribute('aria-activedescendant', options[active].option.id);
      } else if (event.key === 'Enter' && !list.hidden && active >= 0) {
        event.preventDefault();
        selectSuggestion(options[active].value);
      }
    });
    filters.forEach(({select}) => select.addEventListener('change', () => { page = 1; refresh(false); }));
    sizeSelect.addEventListener('change', () => { pageSize = Number(sizeSelect.value); page = 1; refresh(false); if (wrapper) wrapper.scrollTop = 0; });
    prev.addEventListener('click', () => { page--; refresh(false); if (wrapper) wrapper.scrollTop = 0; });
    next.addEventListener('click', () => { page++; refresh(false); if (wrapper) wrapper.scrollTop = 0; });
    clear.addEventListener('click', () => {
      input.value = '';
      filters.forEach(({select}) => { select.value = ''; });
      sort = {...defaultSort}; pageSize = 10; sizeSelect.value = '10'; page = 1;
      refresh(false); if (wrapper) wrapper.scrollTop = 0;
      input.focus();
    });
    refresh(false);
  }
  document.querySelectorAll('[data-ui-search]').forEach(enhance);
})();
