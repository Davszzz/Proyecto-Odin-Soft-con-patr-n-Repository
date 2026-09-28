from app.config import supabase


class OrderRepository:

    def create(self, order_data):
        response = (
            supabase
            .table("service_orders")
            .insert(order_data)
            .execute()
        )

        if not response.data:
            return None

        return response.data[0]

    def add_additional_services(
        self,
        order_id,
        additional_service_ids
    ):
        if not additional_service_ids:
            return []

        records = [
            {
                "order_id": order_id,
                "additional_service_id": service_id
            }
            for service_id in additional_service_ids
        ]

        response = (
            supabase
            .table("order_additional_services")
            .insert(records)
            .execute()
        )

        return response.data

    def add_status_history(
        self,
        order_id,
        status_id,
        notes=None
    ):
        response = (
            supabase
            .table("order_status_history")
            .insert({
                "order_id": order_id,
                "status_id": status_id,
                "notes": notes
            })
            .execute()
        )

        return response.data

    def get_by_user(self, user_id):
        response = (
            supabase
            .table("service_orders")
            .select(
                """
                *,
                equipment (
                    id,
                    brand,
                    model,
                    serial_number,
                    equipment_types (
                        id,
                        name
                    )
                ),
                service_types (
                    id,
                    name
                ),
                urgency_levels (
                    id,
                    name,
                    priority
                ),
                order_statuses (
                    id,
                    code,
                    name
                )
                """
            )
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )

        return response.data

    def get_by_id_and_user(
        self,
        order_id,
        user_id
    ):
        response = (
            supabase
            .table("service_orders")
            .select(
                """
                *,
                equipment (
                    id,
                    brand,
                    model,
                    serial_number,
                    notes,
                    equipment_types (
                        id,
                        name
                    )
                ),
                service_types (
                    id,
                    name
                ),
                urgency_levels (
                    id,
                    name,
                    priority
                ),
                order_statuses (
                    id,
                    code,
                    name
                ),
                order_additional_services (
                    additional_services (
                        id,
                        name,
                        description
                    )
                ),
                order_status_history (
                    id,
                    notes,
                    changed_at,
                    order_statuses (
                        id,
                        code,
                        name
                    )
                )
                """
            )
            .eq("id", order_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )

        if not response.data:
            return None

        return response.data[0]