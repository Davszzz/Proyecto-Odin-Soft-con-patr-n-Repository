"""Persistencia SOLPED. No contiene validaciones ni decisiones de negocio."""


def _db():
    from app.config import supabase
    return supabase


class SalesRequestRepository:
    def list_all(self):
        response = (_db().table('sales_requests')
                    .select('*,users(id,full_name,email),service_orders(id,order_number)')
                    .order('created_at', desc=True).execute())
        return response.data or []

    def get(self, request_id):
        response = (_db().table('sales_requests')
                    .select('*,users(id,full_name,email),service_orders(id,order_number)')
                    .eq('id', request_id).limit(1).execute())
        if not response.data:
            return None
        record = response.data[0]
        details = (_db().table('sales_request_details').select('*')
                   .eq('request_id', request_id).order('line_number').execute())
        record['details'] = details.data or []
        return record

    def save(self, request_id, user_id, service_order_id, notes, lines):
        response = _db().rpc('save_sales_request', {
            'p_request_id': request_id,
            'p_user_id': user_id,
            'p_service_order_id': service_order_id,
            'p_notes': notes,
            'p_lines': lines,
        }).execute()
        return response.data

    def change_status(self, request_id, previous_states, new_status):
        result = (_db().table('sales_requests')
                  .update({'status': new_status})
                  .eq('id', request_id)
                  .in_('status', previous_states).execute())
        return result.data[0] if result.data else None

    def delete_draft(self, request_id):
        result = (_db().table('sales_requests').delete()
                  .eq('id', request_id).eq('status', 'BORRADOR').execute())
        return bool(result.data)

    def list_clients(self):
        response = (_db().table('users').select('id,full_name,email')
                    .eq('role', 'CLIENT').order('full_name').execute())
        return response.data or []

    def get_client(self, user_id):
        response = (_db().table('users').select('id,role,full_name,email')
                    .eq('id', user_id).limit(1).execute())
        return response.data[0] if response.data else None

    def get_service_order(self, order_id):
        response = (_db().table('service_orders').select('id,user_id,order_number')
                    .eq('id', order_id).limit(1).execute())
        return response.data[0] if response.data else None

    def list_services(self):
        response = (_db().table('service_types').select('id,name,sale_price')
                    .eq('active', True).order('name').execute())
        return response.data or []

    def list_products(self):
        response = (_db().table('inventory_items').select('id,name,item_type,stock_quantity,sale_price')
                    .eq('active', True).order('name').execute())
        return response.data or []

    def list_for_order(self, order_id):
        """Historial de SOLPED relacionadas con una orden técnica."""
        response = (_db().table('sales_requests')
                    .select('id,request_number,status,created_at')
                    .eq('service_order_id', order_id)
                    .order('created_at', desc=True).execute())
        return response.data or []

    def get_service_order_context(self, order_id):
        """Datos de la orden para prefijar una SOLPED, sin duplicar registros."""
        response = (_db().table('service_orders')
                    .select('id,user_id,order_number,service_type_id,problem_description,'
                            'service_types(id,name),equipment(brand,model)')
                    .eq('id', order_id).limit(1).execute())
        return response.data[0] if response.data else None

    def list_order_materials(self, order_id):
        """Materiales ya consumidos: se copian como conceptos, NO se descuenta stock."""
        response = (_db().table('order_inventory_items')
                    .select('inventory_item_id,quantity,inventory_items(id,name,active,item_type,sale_price)')
                    .eq('order_id', order_id).execute())
        return response.data or []

    def list_service_orders(self):
        response = (_db().table('service_orders')
                    .select('id,user_id,order_number')
                    .order('created_at', desc=True).limit(500).execute())
        return response.data or []
