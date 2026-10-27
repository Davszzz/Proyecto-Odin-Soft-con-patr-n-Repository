"""Acceso a la tabla public.suppliers (Supabase/PostgREST)."""
from datetime import datetime, timezone
from app.config import supabase


class SupplierRepository:
    TABLE = "suppliers"

    def list_all(self, active_only=False):
        query = supabase.table(self.TABLE).select("*")
        if active_only:
            query = query.eq("active", True)
        return query.order("name").execute().data or []

    def get_by_id(self, supplier_id):
        rows = (supabase.table(self.TABLE).select("*")
                .eq("id", supplier_id).limit(1).execute().data)
        return rows[0] if rows else None

    def get_by_tax_id(self, tax_id):
        rows = (supabase.table(self.TABLE).select("id")
                .eq("tax_id", tax_id).limit(1).execute().data)
        return rows[0] if rows else None

    def create(self, values):
        rows = supabase.table(self.TABLE).insert(values).execute().data
        return rows[0] if rows else None

    def update(self, supplier_id, values):
        changes = {**values, "updated_at": datetime.now(timezone.utc).isoformat()}
        rows = (supabase.table(self.TABLE).update(changes)
                .eq("id", supplier_id).execute().data)
        return rows[0] if rows else None

    def deactivate(self, supplier_id):
        """Eliminación lógica: conserva referencias de inventario e historial."""
        return self.update(supplier_id, {"active": False})

    def activate(self, supplier_id):
        return self.update(supplier_id, {"active": True})
