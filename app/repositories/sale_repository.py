"""Persistencia de ventas y sus líneas (conversión a través de función SQL)."""


def _db():
    from app.config import supabase
    return supabase


class SaleRepository:
    def list_all(self):
        response = (_db().table('sales').select('*,sales_requests(request_number,user_id)')
                    .order('created_at', desc=True).execute())
        return response.data or []

    def get(self, sale_id):
        response = (_db().table('sales').select('*,sales_requests(request_number,user_id)')
                    .eq('id', sale_id).limit(1).execute())
        if not response.data:
            return None
        sale = response.data[0]
        response = (_db().table('sale_details').select('*')
                    .eq('sale_id', sale_id).order('line_number').execute())
        sale['details'] = response.data or []
        return sale

    def create_from_request(self, request_id, notes):
        response = _db().rpc('create_sale_from_request', {
            'p_request_id': request_id, 'p_notes': notes,
        }).execute()
        return response.data

    def find_by_request(self, request_id):
        result = (_db().table('sales').select('id,sale_number,status')
                  .eq('request_id', request_id).limit(1).execute())
        return result.data[0] if result.data else None

    def create_from_request_simple(self, request_id, notes):
        """Aprueba SOLPED y registra venta confirmada de forma atómica."""
        response = _db().rpc('create_sale_from_request_simple', {
            'p_request_id': request_id, 'p_notes': notes,
        }).execute()
        return response.data

    def change_status(self, sale_id, old_states, new_status):
        response = (_db().table('sales').update({'status': new_status})
                    .eq('id', sale_id).in_('status', old_states).execute())
        return response.data[0] if response.data else None

    def update_notes(self, sale_id, notes):
        response = (_db().table('sales').update({'notes': notes})
                    .eq('id', sale_id).eq('status', 'REGISTRADA').execute())
        return response.data[0] if response.data else None

    def has_document(self, sale_id):
        response = (_db().table('sale_documents').select('id')
                    .eq('sale_id', sale_id).limit(1).execute())
        return bool(response.data)

    def delete_registered(self, sale_id):
        """Solo se puede borrar una venta todavía no confirmada."""
        response = (_db().table('sales').delete()
                    .eq('id', sale_id).eq('status', 'REGISTRADA').execute())
        return bool(response.data)
