"""Caso de uso: consumo de materiales y control de stock por orden."""
from decimal import Decimal
from uuid import UUID
from app.repositories.order_material_repository import OrderMaterialRepository
from app.repositories.inventory_repository import InventoryRepository
from app.services.admin_service import AdminService


class OrderMaterialService:
    def __init__(self, repository=None, inventory_repository=None, admin_service=None):
        self.repository = repository if repository is not None else OrderMaterialRepository()
        self.inventory_repository = (
            inventory_repository if inventory_repository is not None else InventoryRepository()
        )
        self.admin_service = admin_service if admin_service is not None else AdminService()

    @staticmethod
    def _uuid(value, description):
        try:
            return str(UUID(str(value)))
        except (ValueError, TypeError, AttributeError):
            raise ValueError(f"{description} inválido.") from None

    def _order(self, order_id):
        order_id = self._uuid(order_id, "Identificador de orden")
        order = self.admin_service.get_order(order_id)
        if not order:
            raise ValueError("La orden no existe.")
        return order

    @staticmethod
    def _modifiable(order):
        code = (order.get("order_statuses") or {}).get("code")
        if code in {"COMPLETED", "CANCELLED"}:
            raise ValueError("No puede cambiar materiales de una orden finalizada o cancelada.")

    def get_page_data(self, order_id):
        order = self._order(order_id)
        rows = self.repository.list_by_order(order["id"])
        subtotal = sum((
            Decimal(str(row["unit_cost"])) * int(row["quantity"])
            for row in rows
        ), Decimal("0.00"))
        return {
            "order": order,
            "materials": rows,
            "items": self.inventory_repository.list_all(active_only=True),
            "total_cost": f"{subtotal:.2f}",
            "can_modify": (order.get("order_statuses") or {}).get("code")
                          not in {"COMPLETED", "CANCELLED"},
        }

    def add(self, order_id, item_id, quantity):
        order = self._order(order_id)
        self._modifiable(order)
        item_id = self._uuid(item_id, "Producto")
        raw_quantity = str(quantity).strip()
        if not raw_quantity.isdecimal():
            raise ValueError("Ingrese una cantidad entera positiva.")
        qty = int(raw_quantity)
        if qty < 1 or qty > 10000:
            raise ValueError("La cantidad debe estar entre 1 y 10000.")
        # Se revisa antes para dar feedback; la RPC verifica de nuevo bajo bloqueo.
        item = self.inventory_repository.get_by_id(item_id)
        if not item or not item.get("active"):
            raise ValueError("Seleccione un producto activo y existente.")
        self.repository.add(order["id"], item_id, qty)

    def remove(self, order_id, item_id):
        order = self._order(order_id)
        self._modifiable(order)
        item_id = self._uuid(item_id, "Producto")
        self.repository.remove(order["id"], item_id)
