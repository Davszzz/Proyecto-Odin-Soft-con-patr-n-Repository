from datetime import datetime, timezone

from app.repositories.catalog_repository import CatalogRepository
from app.repositories.equipment_repository import EquipmentRepository
from app.repositories.order_repository import OrderRepository


class OrderService:

    def __init__(self):
        self.catalog_repository = CatalogRepository()
        self.equipment_repository = EquipmentRepository()
        self.order_repository = OrderRepository()

    def get_order_form_data(self):
        return {
            "service_types":
                self.catalog_repository.get_service_types(),

            "equipment_types":
                self.catalog_repository.get_equipment_types(),

            "urgency_levels":
                self.catalog_repository.get_urgency_levels(),

            "additional_services":
                self.catalog_repository.get_additional_services()
        }

    def confirm_order(
        self,
        user_id,
        form_data
    ):
        # 1. Obtener estado inicial
        status = (
            self.catalog_repository
            .get_status_by_code("REGISTERED")
        )

        if not status:
            raise ValueError(
                "No se encontró el estado inicial de la orden."
            )

        # 2. Crear equipo
        equipment = (
            self.equipment_repository
            .create({
                "user_id": user_id,
                "equipment_type_id":
                    form_data["equipment_type_id"],

                "brand":
                    form_data.get("brand") or None,

                "model":
                    form_data.get("model") or None,

                "serial_number":
                    form_data.get("serial_number") or None
            })
        )

        if not equipment:
            raise ValueError(
                "No se pudo registrar el equipo."
            )

        # 3. Crear orden
        order = (
            self.order_repository
            .create({
                "user_id": user_id,

                "equipment_id":
                    equipment["id"],

                "service_type_id":
                    form_data["service_type_id"],

                "urgency_level_id":
                    form_data["urgency_level_id"],

                "status_id":
                    status["id"],

                "problem_description":
                    form_data["problem_description"],

                "confirmed_at":
                    datetime.now(
                        timezone.utc
                    ).isoformat()
            })
        )

        if not order:
            raise ValueError(
                "No se pudo registrar la orden."
            )

        # 4. Servicios adicionales
        additional_service_ids = (
            form_data.get(
                "additional_service_ids",
                []
            )
        )

        self.order_repository.add_additional_services(
            order["id"],
            additional_service_ids
        )

        # 5. Historial inicial
        self.order_repository.add_status_history(
            order["id"],
            status["id"],
            "Orden de servicio registrada."
        )

        return order
    
    def get_orders_by_user(self, user_id):
        return self.order_repository.get_by_user(
            user_id
        )

    def get_order_detail(
        self,
        order_id,
        user_id
    ):
        return (
            self.order_repository
            .get_by_id_and_user(
                order_id,
                user_id
            )
        )    