import os

from dotenv import load_dotenv
from supabase import create_client
from supabase.client import ClientOptions
from flask import g, has_request_context, request, session
from werkzeug.local import LocalProxy
from uuid import UUID


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


_shared_client = create_client(SUPABASE_URL, SUPABASE_KEY)


def _request_client():
    """Headers privados para auditoría, sin mutar el cliente compartido."""
    if not has_request_context() or request.method != 'POST':
        return _shared_client
    if 'odin_db' not in g:
        headers = {'X-Odin-Endpoint': request.endpoint or ''}
        try:
            headers['X-Odin-Actor'] = str(UUID(str(session.get('user_id'))))
        except (ValueError, TypeError):
            pass
        g.odin_db = create_client(SUPABASE_URL, SUPABASE_KEY,
                                  options=ClientOptions(headers=headers))
    return g.odin_db


supabase = LocalProxy(_request_client)
