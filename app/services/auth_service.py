from app.repositories.report_repository import ReportRepository
from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from app.repositories.user_repository import UserRepository


class AuthService:

    def __init__(self):
        self.user_repository = UserRepository()
        self.reports = ReportRepository()

    def register(
        self,
        full_name,
        email,
        phone,
        password
    ):
        full_name = full_name.strip()
        email = email.strip().lower()
        phone = phone.strip()

        if not full_name:
            raise ValueError(
                "El nombre es obligatorio."
            )

        if not email:
            raise ValueError(
                "El correo es obligatorio."
            )

        if len(password) < 6:
            raise ValueError(
                "La contraseña debe tener al menos 6 caracteres."
            )

        existing_user = (
            self.user_repository
            .find_by_email(email)
        )

        if existing_user:
            raise ValueError(
                "Ya existe una cuenta con este correo."
            )

        password_hash = generate_password_hash(
            password
        )

        user_data = {
            "full_name": full_name,
            "email": email,
            "phone": phone,
            "password_hash": password_hash,
            "role": "CLIENT"
        }

        user = self.user_repository.create(user_data)
        if user:
            self.reports.access(user, 'REGISTRO')
        return user

    def login(self, email, password):
        user = self.user_repository.find_by_email(email.strip().lower())
        if not user:
            # No almacenar correos ingresados para cuentas inexistentes.
            self.reports.access(None, 'FALLIDO')
            return {'status': 'invalid'}
        valid = check_password_hash(user['password_hash'], password)
        # PostgreSQL vuelve a comprobar bloqueo y estado activo bajo FOR UPDATE.
        result = self.reports.login_result(user['id'], valid)
        if result['status'] == 'success':
            result['user'] = user
        return result
