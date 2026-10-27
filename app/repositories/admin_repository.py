"""Consultas e inserciones exclusivas del panel administrativo.

La capa Repository encapsula aquí el acceso a Supabase.
"""
from app.config import supabase


class AdminRepository:
    USER_FIELDS = "id,full_name,email,phone,role,created_at"
    ORDER_LIST_FIELDS = """
        id,order_number,user_id,equipment_id,service_type_id,
        urgency_level_id,status_id,problem_description,created_at,
        users(id,full_name,email),
        equipment(id,brand,model,serial_number,equipment_types(name)),
        service_types(name),urgency_levels(name),order_statuses(code,name)
    """
    ORDER_DETAIL_FIELDS = """
        *,
        users(id,full_name,email),
        equipment(id,brand,model,serial_number,equipment_types(id,name)),
        service_types(id,name),urgency_levels(id,name),order_statuses(id,code,name),
        order_additional_services(additional_services(id,name)),
        order_status_history(id,notes,changed_at,order_statuses(name,code))
    """

    def list_users(self):
        result = (supabase.table("users").select(self.USER_FIELDS)
                  .order("created_at", desc=True).execute())
        return result.data or []

    def get_user(self, user_id):
        result = (supabase.table("users").select(self.USER_FIELDS)
                  .eq("id", user_id).limit(1).execute())
        return result.data[0] if result.data else None

    def find_email(self, email):
        result = (supabase.table("users").select("id")
                  .eq("email", email).limit(1).execute())
        return result.data[0] if result.data else None

    def create_user(self, values):
        result = supabase.table("users").insert(values).execute()
        return result.data[0] if result.data else None

    def update_user(self, user_id, values):
        result = (supabase.table("users").update(values).eq("id", user_id)
                  .execute())
        return result.data[0] if result.data else None

    def user_has_related_records(self, user_id):
        for table_name in ("service_orders", "equipment"):
            result = (supabase.table(table_name).select("id")
                      .eq("user_id", user_id).limit(1).execute())
            if result.data:
                return True
        return False

    def delete_user(self, user_id):
        return (supabase.table("users").delete().eq("id", user_id)
                .execute()).data

    def list_orders(self):
        result = (supabase.table("service_orders")
                  .select(self.ORDER_LIST_FIELDS)
                  .order("created_at", desc=True).execute())
        return result.data or []

    def get_order(self, order_id):
        result = (supabase.table("service_orders")
                  .select(self.ORDER_DETAIL_FIELDS)
                  .eq("id", order_id).limit(1).execute())
        return result.data[0] if result.data else None

    def update_order(self, order_id, values):
        result = (supabase.table("service_orders").update(values)
                  .eq("id", order_id).execute())
        return result.data[0] if result.data else None

    def advance_order_status(self, order_id, expected_code, next_code, notes):
        """Actualización + historial dentro de una única transacción PostgreSQL."""
        result = supabase.rpc("advance_service_order_status", {
            "p_order_id": order_id,
            "p_expected_status_code": expected_code,
            "p_next_status_code": next_code,
            "p_notes": notes,
        }).execute()
        return result.data

    def update_equipment(self, equipment_id, values):
        result = (supabase.table("equipment").update(values)
                  .eq("id", equipment_id).execute())
        return result.data[0] if result.data else None

    def insert_status_history(self, order_id, status_id, notes):
        result = supabase.table("order_status_history").insert({
            "order_id": order_id,
            "status_id": status_id,
            "notes": notes
        }).execute()
        return result.data

    def delete_order(self, order_id):
        """Eliminar dependencias antes de la orden; no existe transacción global."""
        original = self.get_order(order_id)
        if not original:
            return False
        for table in ("order_additional_services", "order_status_history"):
            supabase.table(table).delete().eq("order_id", order_id).execute()
        result = (supabase.table("service_orders").delete().eq("id", order_id)
                  .execute())
        # El equipo se conserva: puede pertenecer a otras órdenes.
        return bool(result.data)

    def active_catalog(self, table, order_field="name"):
        allowed = {
            "service_types", "equipment_types", "urgency_levels",
            "additional_services", "order_statuses"
        }
        if table not in allowed:
            raise ValueError("Catálogo no permitido")
        result = (supabase.table(table).select("*")
                  .eq("active", True).order(order_field).execute())
        return result.data or []
