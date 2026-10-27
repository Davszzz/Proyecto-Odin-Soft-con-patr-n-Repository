"""Persistencia de repuestos, productos e insumos."""
from datetime import datetime, timezone
from app.config import supabase


class InventoryRepository:
    TABLE = "inventory_items"
    LIST_FIELDS = "*,suppliers(id,name)"

    def list_all(self, active_only=False):
        query = supabase.table(self.TABLE).select(self.LIST_FIELDS)
        if active_only:
            query = query.eq("active", True)
        return query.order("name").execute().data or []

    def get_by_id(self, item_id):
        rows = (supabase.table(self.TABLE).select(self.LIST_FIELDS)
                .eq("id", item_id).limit(1).execute().data)
        return rows[0] if rows else None

    def get_by_sku(self, sku):
        rows = (supabase.table(self.TABLE).select("id")
                .eq("sku", sku).limit(1).execute().data)
        return rows[0] if rows else None

    def create(self, values):
        rows = supabase.table(self.TABLE).insert(values).execute().data
        return rows[0] if rows else None

    def update(self, item_id, values):
        changes = {**values, "updated_at": datetime.now(timezone.utc).isoformat()}
        rows = (supabase.table(self.TABLE).update(changes)
                .eq("id", item_id).execute().data)
        return rows[0] if rows else None

    def deactivate(self, item_id):
        """Eliminación lógica para conservar consumos históricos."""
        return self.update(item_id, {"active": False})

    def activate(self, item_id):
        return self.update(item_id, {"active": True})

    def list_used_by_order(self, order_id):
        return (supabase.table("order_inventory_items")
                .select("quantity,unit_cost,inventory_items(id,name,sku,item_type)")
                .eq("order_id", order_id).execute().data or [])
