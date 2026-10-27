from datetime import datetime, timezone
from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from app.repositories.user_repository import UserRepository


class AuthService:

    def __init__(self):
        self.user_repository = UserRepository()

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

        return self.user_repository.create(
            user_data
        )

    def login(self, email, password):

        email = email.strip().lower()

        user = self.user_repository.find_by_email(
            email
        )

        if not user:
            return {
                "status": "invalid"
            }

        lock_until = user.get("lock_until")

        if lock_until:
            lock_until_dt = datetime.fromisoformat(
                lock_until.replace("Z", "+00:00")
            )

            now = datetime.now(timezone.utc)

            if lock_until_dt > now:
                remaining_seconds = int(
                    (lock_until_dt - now).total_seconds()
                )

                return {
                    "status": "temporarily_locked",
                    "remaining_seconds": remaining_seconds
                }

        valid_password = check_password_hash(
            user["password_hash"],
            password
        )

        if not valid_password:
            result = self.user_repository.register_failed_attempt(
                user["id"],
                lock_seconds=30
            )

            if result["locked"]:
                return {
                    "status": "temporarily_locked",
                    "remaining_seconds": result["remaining_seconds"]
                }

            return {
                "status": "invalid"
            }

        self.user_repository.reset_failed_attempts(
            user["id"]
        )

        return {
            "status": "success",
            "user": user
        }