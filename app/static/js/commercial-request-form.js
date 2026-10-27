/* Odin Soft: líneas dinámicas para SOLPED, sin dependencias adicionales. */
(() => {
  'use strict';
  const form = document.getElementById('commercialRequestForm');
  if (!form) return;
  const wrapper = document.getElementById('commercialLines');
  const template = document.getElementById('commercialRowTemplate');
  const add = document.getElementById('addCommercialLine');
  const clientSelect = document.getElementById('client_id');
  const orderSelect = document.getElementById('service_order_id');
  const dataElement = document.getElementById('commercialCatalog');
  const catalog = dataElement ? JSON.parse(dataElement.textContent) : { services: [], products: [] };

  function updateConcept(row) {
    const kind = row.querySelector('[data-line-kind]').value;
    const select = row.querySelector('[data-line-reference]');
    const selected = select.value || select.dataset.currentRef || '';
    const entries = kind === 'PRODUCTO' ? catalog.products : catalog.services;
    select.replaceChildren();
    const placeholder = document.createElement('option');
    placeholder.value = '';
    placeholder.textContent = 'Selecciona un ' + (kind === 'PRODUCTO' ? 'producto o repuesto' : 'servicio');
    select.appendChild(placeholder);
    for (const entry of entries) {
      const option = document.createElement('option');
      option.value = String(entry.id);
      option.textContent = entry.name + (kind === 'PRODUCTO' ? ' · ' + (entry.item_type === 'INSUMO' ? 'Insumo' : entry.item_type === 'REPUESTO' ? 'Repuesto' : 'Producto') + ' · stock ' + entry.stock_quantity : '');
      option.selected = option.value === selected;
      select.appendChild(option);
    }
    select.dataset.currentRef = '';
  }

  function updateSuggestedPrice(row, overwrite = false) {
    const kind = row.querySelector('[data-line-kind]').value;
    const reference = row.querySelector('[data-line-reference]').value;
    const input = row.querySelector('[name="line_price[]"]');
    if (!input || (!overwrite && input.value !== '')) return;
    const options = kind === 'PRODUCTO' ? catalog.products : catalog.services;
    const item = options.find((entry) => String(entry.id) === reference);
    // Un catálogo sin precio sugerido debe dejar el campo vacío; nunca usar unit_cost.
    input.value = item && item.sale_price != null ? String(item.sale_price) : '';
  }

  function updateRowNumbers() {
    const rows = wrapper.querySelectorAll('[data-line-row]');
    rows.forEach((row, idx) => {
      row.querySelector('[data-line-number]').textContent = idx + 1;
      row.querySelector('[data-remove-line]').disabled = rows.length === 1;
    });
    add.disabled = rows.length >= 50;
  }

  function connectRow(row) {
    updateConcept(row);
    updateSuggestedPrice(row);
    row.querySelector('[data-line-kind]').addEventListener('change', () => {
      row.querySelector('[data-line-reference]').value = '';
      updateConcept(row);
      updateSuggestedPrice(row, true);
    });
    row.querySelector('[data-line-reference]').addEventListener('change', () => {
      updateSuggestedPrice(row, true);
    });
    row.querySelector('[data-remove-line]').addEventListener('click', () => {
      if (wrapper.querySelectorAll('[data-line-row]').length <= 1) return;
      row.remove();
      updateRowNumbers();
    });
  }

  function filterOrders() {
    const clientId = clientSelect.value;
    for (const option of orderSelect.querySelectorAll('option[data-client-id]')) {
      const visible = Boolean(clientId) && option.dataset.clientId === clientId;
      option.hidden = !visible;
      option.disabled = !visible;
      if (!visible && option.selected) orderSelect.value = '';
    }
  }

  wrapper.querySelectorAll('[data-line-row]').forEach(connectRow);
  updateRowNumbers();
  if (clientSelect && orderSelect) {
    clientSelect.addEventListener('change', filterOrders);
    filterOrders();
  }
  add.addEventListener('click', () => {
    if (wrapper.querySelectorAll('[data-line-row]').length >= 50) return;
    const row = template.content.firstElementChild.cloneNode(true);
    wrapper.appendChild(row);
    connectRow(row);
    updateRowNumbers();
  });
})();
