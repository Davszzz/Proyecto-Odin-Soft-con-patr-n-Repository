"""Lectura de metadatos de auditoría, sin exponer credenciales."""
from uuid import UUID


class AuditRepository:
    TABLES = frozenset({
        'users', 'service_orders', 'inventory_items', 'suppliers', 'service_types',
        'sales_requests', 'sales', 'sale_documents', 'supplier_purchases',
    })
    FIELDS = ('id,created_at,created_at_known,created_by,created_by_source,'
              'updated_at,updated_at_known,updated_by,updated_by_source')

    def __init__(self, client=None):
        self._client = client

    @property
    def db(self):
        if self._client is not None:
            return self._client
        from app.config import supabase
        return supabase

    @staticmethod
    def ids(values):
        return sorted({str(UUID(str(value))) for value in values if value})

    def records(self, table, ids):
        if table not in self.TABLES:
            raise ValueError('Tabla de auditoría no permitida.')
        keys = self.ids(ids)
        rows = []
        for start in range(0, len(keys), 100):
            rows.extend(self.db.table(table).select(self.FIELDS)
                        .in_('id', keys[start:start+100]).execute().data or [])
        return rows

    def actor_names(self, ids):
        keys = self.ids(ids)
        names = {}
        for start in range(0, len(keys), 100):
            rows = (self.db.table('users').select('id,full_name')
                    .in_('id', keys[start:start+100]).execute().data or [])
            names.update({str(row['id']): row.get('full_name') for row in rows})
        return names
