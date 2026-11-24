"""Proyecciones explícitas y paginadas para reportes; no se exportan secretos."""
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

LIMA = ZoneInfo('America/Lima')

# Orden estable, campos permitidos y fecha del hecho (si corresponde).
SOURCES = {
    'users': ('id,full_name,email,role,active,department,location,segment,created_at', 'id', 'created_at'),
    'suppliers': ('id,name,tax_id,active,category,location,created_at', 'id', 'created_at'),
    'inventory_items': ('id,name,sku,item_type,supplier_id,stock_quantity,min_stock,unit_cost,sale_price,active,created_at', 'id', 'created_at'),
    'service_types': ('id,name,active,sale_price,estimated_unit_cost', 'id', None),
    'sales_requests': ('id,user_id,service_order_id', 'id', None),
    'sales_request_details': ('id,item_kind,inventory_item_id,service_type_id', 'id', None),
    'sales': ('id,sale_number,request_id,status,seller_id,seller_name,payment_tracking,created_at', 'id', 'created_at'),
    'sale_details': ('id,sale_id,source_request_detail_id,description,quantity,unit_price,line_total,report_unit_cost,report_cost_basis', 'id', None),
    'sale_documents': ('id,sale_id,status,document_type,issued_at', 'id', None),
    'access_events': ('id,user_id,user_name,outcome,created_at', 'id', 'created_at'),
    'audit_events': ('id,actor_id,actor_name,entity,entity_id,action,changed_fields,created_at', 'id', 'created_at'),
    'inventory_movements': ('id,item_id,item_name,quantity_delta,stock_after,reason,created_at', 'id', 'created_at'),
    'supplier_purchases': ('id,supplier_id,item_id,quantity,unit_cost,ordered_on,expected_on,received_at,created_at', 'id', 'ordered_on'),
    'supplier_purchase_payments': ('id,purchase_id,amount,created_at', 'id', 'created_at'),
    'supplier_evaluations': ('id,supplier_id,score,notes,created_at', 'id', 'created_at'),
    'sale_payments': ('id,sale_id,amount,method,created_at', 'id', 'created_at'),
    'report_tracking': ('id,started_at', 'id', None),
}

class ReportRepository:
    PAGE = 500
    LIMIT = 50000

    def __init__(self, client=None):
        self._client = client

    @property
    def db(self):
        if self._client is not None:
            return self._client
        from app.config import supabase
        return supabase

    def rows(self, table, start=None, end=None):
        fields, key, date_field = SOURCES[table]
        result = []
        cursor = None
        while True:
            q = self.db.table(table).select(fields).order(key).limit(self.PAGE)
            if cursor is not None:
                q = q.gt(key, cursor)
            if date_field:
                def bound(d):
                    return d.isoformat() if date_field == 'ordered_on' else datetime.combine(d, time.min, LIMA).isoformat()
                if start:
                    q = q.gte(date_field, bound(start))
                if end:
                    q = q.lt(date_field, bound(end + timedelta(days=1)))
            page = q.execute().data or []
            if not page:
                return result
            result.extend(page)
            if len(result) > self.LIMIT:
                raise ValueError('El reporte supera 50 000 registros de origen. Reduce el período o solicita una consulta agregada.')
            if len(page) < self.PAGE:
                return result
            cursor = page[-1][key]

    def access(self, user, outcome):
        self.db.table('access_events').insert({'user_id': (user or {}).get('id'), 'user_name': (user or {}).get('full_name'), 'outcome': outcome}).execute()

    def login_result(self, user_id, password_valid):
        result = self.db.rpc('odin_login_result', {'p_id':user_id, 'p_valid':password_valid}).execute().data
        if not isinstance(result, dict) or result.get('status') not in ('success','invalid','temporarily_locked'):
            raise RuntimeError('Respuesta de autenticación no válida.')
        return result

    def operation(self, name, params):
        if name not in {'odin_purchase_create','odin_purchase_receive','odin_purchase_pay','odin_sale_pay'}:
            raise ValueError('Operación no permitida.')
        return self.db.rpc(name, params).execute().data

    def evaluation(self, values):
        return self.db.table('supplier_evaluations').insert(values).execute().data
