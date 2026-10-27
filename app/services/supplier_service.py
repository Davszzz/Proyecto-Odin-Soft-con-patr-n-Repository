"""Reglas de negocio para administrar proveedores."""
import re
from app.repositories.supplier_repository import SupplierRepository


class SupplierService:
    def __init__(self, repository=None):
        self.repository = repository if repository is not None else SupplierRepository()

    def list_all(self, active_only=False):
        return self.repository.list_all(active_only=active_only)

    def get_by_id(self, supplier_id):
        return self.repository.get_by_id(supplier_id)

    @staticmethod
    def _optional_text(form, field, max_length):
        value = str(form.get(field) or "").strip()
        if len(value) > max_length:
            raise ValueError(f"{field}: máximo {max_length} caracteres.")
        return value or None

    def _validate(self, form):
        name = (form.get("name") or "").strip()
        if not name or len(name) > 150:
            raise ValueError("El nombre del proveedor es obligatorio (máximo 150 caracteres).")
        tax_id = self._optional_text(form, "tax_id", 20)
        email = self._optional_text(form, "email", 150)
        if email and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            raise ValueError("Ingrese un correo electrónico válido.")
        return {
            "name": name,
            "tax_id": tax_id,
            "contact_name": self._optional_text(form, "contact_name", 150),
            "email": email.lower() if email else None,
            "phone": self._optional_text(form, "phone", 25),
            "address": self._optional_text(form, "address", 500),
        }

    def _check_tax_id(self, tax_id, supplier_id=None):
        if tax_id:
            existing = self.repository.get_by_tax_id(tax_id)
            if existing and str(existing["id"]) != str(supplier_id):
                raise ValueError("Ya existe un proveedor con ese documento/RUC.")

    def create(self, form):
        values = self._validate(form)
        self._check_tax_id(values["tax_id"])
        return self.repository.create(values)

    def update(self, supplier_id, form):
        if not self.repository.get_by_id(supplier_id):
            raise ValueError("Proveedor no encontrado.")
        values = self._validate(form)
        self._check_tax_id(values["tax_id"], supplier_id)
        return self.repository.update(supplier_id, values)

    def deactivate(self, supplier_id):
        if not self.repository.get_by_id(supplier_id):
            raise ValueError("Proveedor no encontrado.")
        return self.repository.deactivate(supplier_id)

    def activate(self, supplier_id):
        if not self.repository.get_by_id(supplier_id):
            raise ValueError("Proveedor no encontrado.")
        return self.repository.activate(supplier_id)
