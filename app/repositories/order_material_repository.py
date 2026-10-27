"""Operaciones de materiales por orden. La persistencia queda en Repository."""
from app.config import supabase


class OrderMaterialRepository:
    def add(self, order_id: str, item_id: str, quantity: int) -> None:
        # RPC invoca una transacción PostgreSQL atómica.
        supabase.rpc("add_order_material", {
            "p_order_id": order_id,
            "p_item_id": item_id,
            "p_quantity": quantity,
        }).execute()

    def remove(self, order_id: str, item_id: str) -> None:
        supabase.rpc("remove_order_material", {
            "p_order_id": order_id,
            "p_item_id": item_id,
        }).execute()

    def list_by_order(self, order_id: str) -> list:
        response = (
            supabase.table("order_inventory_items")
            .select("quantity,unit_cost,inventory_items(id,name,sku,item_type)")
            .eq("order_id", order_id)
            .execute()
        )
        return response.data or []
