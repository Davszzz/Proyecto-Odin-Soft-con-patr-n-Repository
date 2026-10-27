"""CRUD administrativo de tipos de servicio; no altera CatalogRepository actual."""
from app.config import supabase


class ServiceCatalogRepository:
    TABLE = "service_types"

    def list_all(self, active_only=False):
        query = supabase.table(self.TABLE).select("*")
        if active_only:
            query = query.eq("active", True)
        return query.order("name").execute().data or []

    def get_by_id(self, service_id):
        rows = (supabase.table(self.TABLE).select("*")
                .eq("id", service_id).limit(1).execute().data)
        return rows[0] if rows else None

    def create(self, values):
        rows = supabase.table(self.TABLE).insert(values).execute().data
        return rows[0] if rows else None

    def update(self, service_id, values):
        rows = (supabase.table(self.TABLE).update(values)
                .eq("id", service_id).execute().data)
        return rows[0] if rows else None

    def deactivate(self, service_id):
        """Evita borrar servicios relacionados a órdenes existentes."""
        return self.update(service_id, {"active": False})

    def activate(self, service_id):
        return self.update(service_id, {"active": True})
