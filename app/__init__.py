import os
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from flask import (
    Flask,
    render_template,
    session,
    redirect,
    url_for
)

from app.routes.auth_routes import auth_bp
from app.routes.order_routes import orders_bp


load_dotenv()


LIMA_TZ = ZoneInfo("America/Lima")


def parse_supabase_datetime(value):
    if not value:
        return None

    if isinstance(value, datetime):
        dt = value
    else:
        value = str(value)

        # Supabase puede devolver fechas terminadas en Z
        value = value.replace("Z", "+00:00")

        try:
            dt = datetime.fromisoformat(value)
        except ValueError:
            return None

    # Si por alguna razón viniera sin zona horaria,
    # se considera UTC.
    if dt.tzinfo is None:
        dt = dt.replace(
            tzinfo=ZoneInfo("UTC")
        )

    return dt.astimezone(LIMA_TZ)


def format_date_pe(value):
    dt = parse_supabase_datetime(value)

    if not dt:
        return "-"

    return dt.strftime("%d/%m/%Y")


def format_datetime_pe(value):
    dt = parse_supabase_datetime(value)

    if not dt:
        return "-"

    return dt.strftime(
        "%d/%m/%Y - %H:%M"
    )

def create_app():

    app = Flask(__name__)
    
    app.jinja_env.filters[
        "date_pe"
    ] = format_date_pe

    app.jinja_env.filters[
        "datetime_pe"
    ] = format_datetime_pe

    app.secret_key = os.getenv(
        "SECRET_KEY"
    )

    if not app.secret_key:
        raise ValueError(
            "No se encontró SECRET_KEY."
        )

    app.register_blueprint(
        auth_bp
    )

    app.register_blueprint(
        orders_bp
    )

    @app.route("/")
    def index():

        if "user_id" not in session:
            return redirect(
                url_for("auth.login")
            )

        return render_template(
            "index.html"
        )

    return app