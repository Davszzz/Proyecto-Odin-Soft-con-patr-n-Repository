"""Orden y paginación de compras sobre el conjunto completo, antes de consultar auditoría."""
import unicodedata

COLUMNS = {'supplier': 'Proveedor / artículo', 'ordered_on': 'Pedido / entrega',
           'quantity': 'Unidades', 'total': 'Importe', 'balance': 'Saldo', 'received_at': 'Recepción'}
PAGE_SIZES = (10, 25, 50, 100)


def text_key(value):
    text = str(value or '').casefold().replace('ñ', 'n\uffff')
    return ''.join(c for c in unicodedata.normalize('NFD', text) if not unicodedata.combining(c))


def purchase_table(records, column='ordered_on', direction='desc', page=1, size=10):
    if column not in COLUMNS or direction not in ('asc', 'desc'):
        column, direction = 'ordered_on', 'desc'
    if size not in PAGE_SIZES:
        size = 10
    present, missing = [], []
    for row in records:
        (missing if row.get(column) is None or row.get(column) == '' else present).append(row)
    def key(row):
        if column == 'supplier':
            return text_key(row[column]), text_key(row.get('item'))
        return row[column]
    # Orden estable, conservando el orden previo para valores iguales.
    ordered = sorted(present, key=key, reverse=direction == 'desc') + missing
    total = len(ordered)
    pages = max(1, (total + size - 1) // size)
    page = min(max(1, page), pages)
    offset = (page - 1) * size
    return dict(purchases=ordered[offset:offset+size], sort_column=column, sort_direction=direction,
                page=page, pages=pages, size=size, total_rows=total,
                first_row=offset+1 if total else 0, last_row=min(offset+size,total), page_sizes=PAGE_SIZES)
