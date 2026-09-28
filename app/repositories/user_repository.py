from app.config import supabase


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