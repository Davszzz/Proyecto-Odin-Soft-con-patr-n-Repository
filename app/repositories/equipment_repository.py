from app.config import supabase


class EquipmentRepository:

    def create(self, equipment_data):
        response = (
            supabase
            .table("equipment")
            .insert(equipment_data)
            .execute()
        )

        if not response.data:
            return None

        return response.data[0]

    