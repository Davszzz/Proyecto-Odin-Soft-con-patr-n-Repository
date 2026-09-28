from app.config import supabase


class CatalogRepository:

    def get_service_types(self):
        response = (
            supabase
            .table("service_types")
            .select("*")
            .eq("active", True)
            .order("name")
            .execute()
        )

        return response.data

    def get_equipment_types(self):
        response = (
            supabase
            .table("equipment_types")
            .select("*")
            .eq("active", True)
            .order("name")
            .execute()
        )

        return response.data

    def get_urgency_levels(self):
        response = (
            supabase
            .table("urgency_levels")
            .select("*")
            .eq("active", True)
            .order("priority")
            .execute()
        )

        return response.data

    def get_additional_services(self):
        response = (
            supabase
            .table("additional_services")
            .select("*")
            .eq("active", True)
            .order("name")
            .execute()
        )

        return response.data

    def get_status_by_code(self, code):
     response = (
         supabase
         .table("order_statuses")
         .select("*")
         .eq("code", code)
         .limit(1)
         .execute()
     )

     if not response.data:
         return None

     return response.data[0]
    