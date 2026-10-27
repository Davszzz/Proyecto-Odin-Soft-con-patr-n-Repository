/* Filtros locales para tablas administrativas. No modifica datos. */
document.querySelectorAll('[data-ui-search]').forEach(input => {
  const table = document.getElementById(input.getAttribute('data-ui-search'));
  if (!table) return;
  input.addEventListener('input', () => {
    const value = input.value.trim().toLocaleLowerCase('es-PE');
    table.querySelectorAll('tbody tr').forEach(row => {
      if (!row.querySelector('td')) return;
      row.hidden = !row.textContent.toLocaleLowerCase('es-PE').includes(value);
    });
  });
});
