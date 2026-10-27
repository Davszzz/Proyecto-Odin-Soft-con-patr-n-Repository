from app.config import supabase
from datetime import datetime, timezone, timedelta

class UserRepository:

    def find_by_email(self, email):
        response = (
            supabase
            .table("users")
            .select("*")
            .eq("email", email)
            .limit(1)
            .execute()
        )

        if not response.data:
            return None

        return response.data[0]

    def find_by_id(self, user_id):
        response = (
            supabase
            .table("users")
            .select("*")
            .eq("id", user_id)
            .limit(1)
            .execute()
        )

        if not response.data:
            return None

        return response.data[0]

    def create(self, user_data):
        response = (
            supabase
            .table("users")
            .insert(user_data)
            .execute()
        )

        if not response.data:
            return None

        return response.data[0]

    def register_failed_attempt(
        self,
        user_id,
        lock_seconds=30
    ):
        user = self.find_by_id(user_id)

        if not user:
            return {
                "locked": False,
                "remaining_seconds": 0
            }

        attempts = user.get(
            "failed_login_attempts",
            0
        ) + 1

        changes = {
            "failed_login_attempts": attempts
        }

        if attempts >= 3:
            lock_until = (
                datetime.now(timezone.utc)
                + timedelta(seconds=lock_seconds)
            ).isoformat()

            changes["lock_until"] = lock_until
            changes["failed_login_attempts"] = 0

        response = (
            supabase
            .table("users")
            .update(changes)
            .eq("id", user_id)
            .execute()
        )

        if attempts >= 3:
            return {
                "locked": True,
                "remaining_seconds": lock_seconds
            }

        return {
            "locked": False,
            "remaining_seconds": 0
        }

    def reset_failed_attempts(self, user_id):
        (
            supabase
            .table("users")
            .update({
                "failed_login_attempts": 0,
                "lock_until": None
            })
            .eq("id", user_id)
            .execute()
        )