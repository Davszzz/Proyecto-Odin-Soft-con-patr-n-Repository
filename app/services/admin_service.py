"""Casos de uso de administración: usuarios y órdenes."""
import re
from werkzeug.security import generate_password_hash
from app.repositories.admin_repository import AdminRepository
from app.services.order_service import OrderService


class AdminService:
    ROLES = {"CLIENT", "ADMIN"}

    # Flujo operativo: solo avances, sin saltos ni retrocesos.
    STATUS_TRANSITIONS = {
        "REGISTERED": ("REVIEW", "CANCELLED"),
        "REVIEW": ("IN_PROGRESS", "CANCELLED"),
        "IN_PROGRESS": ("COMPLETED", "CANCELLED"),
        "COMPLETED": (),
        "CANCELLED": (),
    }

    def __init__(self, repository=None, order_service=None):
        self.repo = repository or AdminRepository()
        self.order_service = order_service or OrderService()

    def dashboard(self):
        users = self.repo.list_users()
        orders = self.repo.list_orders()
        return {
            "users_total": len(users),
            "orders_total": len(orders),
            "orders_active": sum(
                (o.get("order_statuses") or {}).get("code")
                not in ("COMPLETED", "CANCELLED") for o in orders
            ),
            "orders_completed": sum(
                (o.get("order_statuses") or {}).get("code") == "COMPLETED"
                for o in orders
            ),
            "recent_orders": orders[:6]
        }

    def users(self):
        return self.repo.list_users()

    def orders(self):
        return self.repo.list_orders()

    def get_user(self, user_id):
        return self.repo.get_user(user_id)

    def get_order(self, order_id):
        return self.repo.get_order(order_id)

    def catalogs(self):
        return {
            "service_types": self.repo.active_catalog("service_types"),
            "equipment_types": self.repo.active_catalog("equipment_types"),
            "urgency_levels": self.repo.active_catalog("urgency_levels", "priority"),
            "additional_services": self.repo.active_catalog("additional_services"),
            "order_statuses": self.repo.active_catalog("order_statuses")
        }

    def _validate_user(self, form, editing=False):
        name = (form.get("full_name") or "").strip()
        email = (form.get("email") or "").strip().lower()
        phone = (form.get("phone") or "").strip()
        role = (form.get("role") or "CLIENT").strip().upper()
        password = form.get("password") or ""
        if not name or len(name) > 150:
            raise ValueError("Ingrese un nombre válido (máximo 150 caracteres).")
        if len(email) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            raise ValueError("Ingrese un correo electrónico válido.")
        if len(phone) > 30:
            raise ValueError("El teléfono no debe superar 30 caracteres.")
        if role not in self.ROLES:
            raise ValueError("Rol no permitido.")
        if (not editing or password) and len(password) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres.")
        return {"full_name": name, "email": email, "phone": phone, "role": role}, password

    def create_user(self, form):
        values, password = self._validate_user(form)
        if self.repo.find_email(values["email"]):
            raise ValueError("Ya existe un usuario con ese correo.")
        values["password_hash"] = generate_password_hash(password)
        return self.repo.create_user(values)

    def edit_user(self, user_id, current_user_id, form):
        existing = self.repo.get_user(user_id)
        if not existing:
            raise ValueError("Usuario no encontrado.")
        values, password = self._validate_user(form, editing=True)
        if user_id == current_user_id and values["role"] != "ADMIN":
            raise ValueError("No puede retirarse a sí mismo el rol ADMIN.")
        same_email = self.repo.find_email(values["email"])
        if same_email and same_email["id"] != user_id:
            raise ValueError("El correo ya pertenece a otra cuenta.")
        if password:
            values["password_hash"] = generate_password_hash(password)
        return self.repo.update_user(user_id, values)

    def delete_user(self, user_id, current_user_id):
        if user_id == current_user_id:
            raise ValueError("No puede eliminar su propia cuenta administrativa.")
        if not self.repo.get_user(user_id):
            raise ValueError("Usuario no encontrado.")
        if self.repo.user_has_related_records(user_id):
            raise ValueError(
                "No se puede eliminar: el usuario tiene equipos u órdenes relacionados. "
                "Conserve la cuenta para preservar el historial."
            )
        return self.repo.delete_user(user_id)

    def _catalog_id(self, options, candidate, label):
        if not candidate or candidate not in {str(c["id"]) for c in options}:
            raise ValueError(f"Seleccione un {label} válido.")
        return candidate

    def create_order(self, form):
        catalogs = self.catalogs()
        user_id = (form.get("user_id") or "").strip()
        if not self.repo.get_user(user_id):
            raise ValueError("Seleccione un usuario existente.")
        data = {
            "service_type_id": self._catalog_id(
                catalogs["service_types"], form.get("service_type_id"), "tipo de servicio"),
            "equipment_type_id": self._catalog_id(
                catalogs["equipment_types"], form.get("equipment_type_id"), "tipo de equipo"),
            "urgency_level_id": self._catalog_id(
                catalogs["urgency_levels"], form.get("urgency_level_id"), "nivel de urgencia"),
            "brand": (form.get("brand") or "").strip()[:150],
            "model": (form.get("model") or "").strip()[:150],
            "serial_number": (form.get("serial_number") or "").strip()[:150],
            "problem_description": (form.get("problem_description") or "").strip(),
            "additional_service_ids": form.getlist("additional_services")
        }
        if not data["problem_description"]:
            raise ValueError("La descripción del problema es obligatoria.")
        valid_additions = {str(c["id"]) for c in catalogs["additional_services"]}
        if not set(data["additional_service_ids"]).issubset(valid_additions):
            raise ValueError("Hay servicios adicionales no permitidos.")
        # Reutiliza el caso de uso existente: no duplicamos persistencia.
        return self.order_service.confirm_order(user_id, data)

    def available_status_transitions(self, order):
        """Estados seleccionables según el estado actual de la orden."""
        current_code = (order.get("order_statuses") or {}).get("code")
        codes = self.STATUS_TRANSITIONS.get(current_code, ())
        active_by_code = {s.get("code"): s for s in self.repo.active_catalog("order_statuses")}
        return [active_by_code[code] for code in codes if code in active_by_code]

    def mark_order_under_review(self, order_id):
        """Se dispara al abrir una orden desde el listado; no hay selector de estado."""
        current = self.repo.get_order(order_id)
        if not current:
            raise ValueError("Orden no encontrada.")
        if (current.get("order_statuses") or {}).get("code") != "REGISTERED":
            return None
        return self.repo.advance_order_status(
            order_id, "REGISTERED", "REVIEW",
            "La orden fue abierta para su revisión técnica."
        )

    def change_order_status(self, order_id, next_status_id, notes):
        """Solo la acción de seguimiento cambia un estado técnico."""
        current = self.repo.get_order(order_id)
        if not current:
            raise ValueError("Orden no encontrada.")
        previous_code = (current.get("order_statuses") or {}).get("code")
        allowed = self.available_status_transitions(current)
        target = next((s for s in allowed if str(s["id"]) == str(next_status_id)), None)
        if not target:
            raise ValueError("Transición no permitida: avanza la orden al siguiente estado.")
        message = (notes or "").strip()
        if len(message) < 5 or len(message) > 500:
            raise ValueError("Escribe una observación de 5 a 500 caracteres para el historial.")
        # El RPC bloquea la fila, vuelve a validar el estado y registra el
        # evento junto a la actualización. Así no quedan historiales incompletos.
        return self.repo.advance_order_status(order_id, previous_code, target["code"], message)

    def edit_order(self, order_id, form):
        """Edita datos técnicos, sin permitir saltos de estado."""
        current = self.repo.get_order(order_id)
        if not current:
            raise ValueError("Orden no encontrada.")
        catalogs = self.catalogs()
        changes = {
            "service_type_id": self._catalog_id(
                catalogs["service_types"], form.get("service_type_id"), "tipo de servicio"),
            "urgency_level_id": self._catalog_id(
                catalogs["urgency_levels"], form.get("urgency_level_id"), "nivel de urgencia"),
            "problem_description": (form.get("problem_description") or "").strip()
        }
        if not changes["problem_description"]:
            raise ValueError("La descripción del problema es obligatoria.")
        self.repo.update_order(order_id, changes)
        equipment = current.get("equipment") or {}
        if equipment.get("id"):
            self.repo.update_equipment(equipment["id"], {
                "brand": (form.get("brand") or "").strip() or None,
                "model": (form.get("model") or "").strip() or None,
                "serial_number": (form.get("serial_number") or "").strip() or None
            })

    def delete_order(self, order_id):
        if not self.repo.delete_order(order_id):
            raise ValueError("La orden no existe o no pudo eliminarse.")
