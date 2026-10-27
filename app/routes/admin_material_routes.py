"""Pantalla de materiales de órdenes: exclusiva de ADMIN y protegida con CSRF."""
import hmac
import secrets
from flask import (
    Blueprint, abort, current_app, flash, redirect, render_template,
    request, session, url_for,
)
from app.repositories.user_repository import UserRepository
from app.services.order_material_service import OrderMaterialService

admin_material_bp = Blueprint("admin_material", __name__, url_prefix="/admin/materiales")
material_service = OrderMaterialService()


@admin_material_bp.before_request
def only_admin():
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))
    user = UserRepository().find_by_id(session["user_id"])
    if not user or user.get("role") != "ADMIN":
        abort(403, description="Acceso exclusivo para administradores.")
    if not session.get("admin_csrf_token"):
        session["admin_csrf_token"] = secrets.token_urlsafe(32)
    if request.method == "POST":
        if not hmac.compare_digest(
            session.get("admin_csrf_token") or "",
            request.form.get("csrf_token") or "",
        ):
            abort(400, description="Token CSRF inválido.")


@admin_material_bp.get("/orden/<order_id>")
def order_materials(order_id):
    try:
        data = material_service.get_page_data(order_id)
    except ValueError:
        abort(404)
    return render_template("admin/order_materials.html", **data, section="orders")


@admin_material_bp.post("/orden/<order_id>/agregar")
def add_material(order_id):
    try:
        material_service.add(
            order_id,
            request.form.get("item_id"),
            request.form.get("quantity"),
        )
        flash("Material agregado y stock descontado correctamente.", "success")
    except ValueError as exc:
        flash(str(exc), "warning")
    except Exception:
        current_app.logger.exception("No se pudo asignar material")
        flash("No se pudo registrar el material. Compruebe el stock disponible.", "danger")
    return redirect(url_for("admin_material.order_materials", order_id=order_id))


@admin_material_bp.post("/orden/<order_id>/quitar/<item_id>")
def remove_material(order_id, item_id):
    try:
        material_service.remove(order_id, item_id)
        flash("Asignación retirada y stock restituido.", "success")
    except ValueError as exc:
        flash(str(exc), "warning")
    except Exception:
        current_app.logger.exception("No se pudo quitar material")
        flash("No se pudo retirar el material.", "danger")
    return redirect(url_for("admin_material.order_materials", order_id=order_id))
