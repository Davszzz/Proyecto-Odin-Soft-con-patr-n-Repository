"""Reglas de negocio del catálogo principal de servicios técnicos."""
from decimal import Decimal, InvalidOperation
from app.repositories.service_catalog_repository import ServiceCatalogRepository


class ServiceCatalogService:
    def __init__(self, repository=None):
        self.repository = repository if repository is not None else ServiceCatalogRepository()

    def list_all(self, active_only=False):
        return self.repository.list_all(active_only=active_only)

    def get_by_id(self, service_id):
        return self.repository.get_by_id(service_id)

    @staticmethod
    def _validate(form):
        name = str(form.get("name") or "").strip()
        description = str(form.get("description") or "").strip() or None
        if not name or len(name) > 150:
            raise ValueError("El nombre del servicio es obligatorio (máximo 150 caracteres).")
        if description and len(description) > 3000:
            raise ValueError("La descripción del servicio es demasiado larga.")
        sale_price_text = str(form.get("sale_price") or "").strip()
        sale_price = None
        if sale_price_text:
            try:
                value = Decimal(sale_price_text)
            except InvalidOperation:
                raise ValueError("Ingrese un precio de venta válido.") from None
            if (not value.is_finite() or value < 0 or
                    value > Decimal("9999999999.99") or value.as_tuple().exponent < -2):
                raise ValueError("El precio de venta debe ser positivo o cero y tener máximo dos decimales.")
            sale_price = str(value.quantize(Decimal("0.01")))
        return {"name": name, "description": description, "sale_price": sale_price}

    def create(self, form):
        return self.repository.create(self._validate(form))

    def update(self, service_id, form):
        if not self.repository.get_by_id(service_id):
            raise ValueError("Servicio no encontrado.")
        return self.repository.update(service_id, self._validate(form))

    def deactivate(self, service_id):
        if not self.repository.get_by_id(service_id):
            raise ValueError("Servicio no encontrado.")
        return self.repository.deactivate(service_id)

    def activate(self, service_id):
        if not self.repository.get_by_id(service_id):
            raise ValueError("Servicio no encontrado.")
        return self.repository.activate(service_id)
