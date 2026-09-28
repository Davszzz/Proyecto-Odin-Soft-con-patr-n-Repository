import os

from dotenv import load_dotenv
from supabase import create_client, Client


load_dotenv()


SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")


if not SUPABASE_URL:
    raise ValueError(
        "No se encontró SUPABASE_URL en las variables de entorno."
    )

if not SUPABASE_KEY:
    raise ValueError(
        "No se encontró SUPABASE_KEY en las variables de entorno."
    )


supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)