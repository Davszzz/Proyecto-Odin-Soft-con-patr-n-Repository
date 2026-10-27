"""Validación y coordinación del catálogo de repuestos e insumos."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from app.repositories.inventory_repository import InventoryRepository
from app.repositories.supplier_repository import SupplierRepository


class InventoryService:
    ITEM_TYPES = {"REPUESTO", "INSUMO", "PRODUCTO"}

    def __init__(self, repository=None, supplier_repository=None):
        self.repository = repository if repository is not None else InventoryRepository()
        self.supplier_repository = (
            supplier_repository if supplier_repository is not None else SupplierRepository()
        )

    def list_all(self, active_only=False):
        return self.repository.list_all(active_only=active_only)

    def get_by_id(self, item_id):
        return self.repository.get_by_id(item_id)

    def list_used_by_order(self, order_id):
        return self.repository.list_used_by_order(order_id)

    @staticmethod
    def _parse_nonnegative_int(form, name):
        text = str(form.get(name, "0")).strip()
        if not text.isdecimal():
            raise ValueError(f"{name}: ingrese un número entero no negativo.")
        number = int(text)
        if number > 2_147_483_647:
            raise ValueError(f"{name}: valor demasiado alto.")
        return number

    @staticmethod
    def _parse_money(form, name):
        try:
            value = Decimal(str(form.get(name, "0")).strip())
        except InvalidOperation:
            raise ValueError(f"{name}: ingrese un costo válido.") from None
        if not value.is_finite() or value < 0 or value > Decimal("9999999999.99"):
            raise ValueError(f"{name}: costo fuera de rango.")
        return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

    def _validate(self, form):
        name = str(form.get("name") or "").strip()
        sku = str(form.get("sku") or "").strip() or None
        description = str(form.get("description") or "").strip() or None
        item_type = str(form.get("item_type") or "").strip().upper()
        supplier_id = str(form.get("supplier_id") or "").strip() or None

        if not name or len(name) > 150:
            raise ValueError("Ingrese un nombre de producto válido (máximo 150 caracteres).")
        if sku and len(sku) > 50:
            raise ValueError("El SKU no puede superar 50 caracteres.")
        if description and len(description) > 3000:
            raise ValueError("La descripción es demasiado larga.")
        if item_type not in self.ITEM_TYPES:
            raise ValueError("Seleccione REPUESTO, INSUMO o PRODUCTO.")
        if supplier_id:
            supplier = self.supplier_repository.get_by_id(supplier_id)
            if not supplier or not supplier.get("active"):
                raise ValueError("Seleccione un proveedor existente y activo.")
        sale_price_raw = str(form.get("sale_price") or "").strip()
        sale_price = (self._parse_money({"sale_price": sale_price_raw}, "sale_price")
                      if sale_price_raw else None)
        return {
            "sale_price": sale_price,
            "name": name,
            "sku": sku,
            "description": description,
            "item_type": item_type,
            "supplier_id": supplier_id,
            "stock_quantity": self._parse_nonnegative_int(form, "stock_quantity"),
            "min_stock": self._parse_nonnegative_int(form, "min_stock"),
            "unit_cost": self._parse_money(form, "unit_cost"),
        }

    def _check_sku(self, sku, item_id=None):
        if sku:
            existing = self.repository.get_by_sku(sku)
            if existing and str(existing["id"]) != str(item_id):
                raise ValueError("Ya existe un producto con ese SKU.")

    def create(self, form):
        values = self._validate(form)
        self._check_sku(values["sku"])
        return self.repository.create(values)

    def update(self, item_id, form):
        if not self.repository.get_by_id(item_id):
            raise ValueError("Producto o insumo no encontrado.")
        values = self._validate(form)
        self._check_sku(values["sku"], item_id)
        return self.repository.update(item_id, values)

    def deactivate(self, item_id):
        if not self.repository.get_by_id(item_id):
            raise ValueError("Producto o insumo no encontrado.")
        return self.repository.deactivate(item_id)

    def activate(self, item_id):
        if not self.repository.get_by_id(item_id):
            raise ValueError("Producto o insumo no encontrado.")
        return self.repository.activate(item_id)
