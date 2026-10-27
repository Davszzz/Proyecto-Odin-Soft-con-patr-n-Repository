"""Panel administrativo: vistas Flask protegidas, sin acceso directo a Supabase."""
import hmac
import secrets
from flask import (
    Blueprint, abort, flash, redirect, render_template,
    request, session, url_for
)
from app.repositories.user_repository import UserRepository
from app.services.admin_service import AdminService
from app.services.sales_request_service import SalesRequestService

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")
admin_service = AdminService()
sales_request_service = SalesRequestService()


@admin_bp.before_request
def check_admin_access():
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))

    # El rol se consulta en base de datos en CADA petición: no se confía
    # solamente en el valor guardado en la cookie de sesión.
    user = UserRepository().find_by_id(session["user_id"])
    if not user or user.get("role") != "ADMIN":
        abort(403, description="Acceso exclusivo para administradores.")

    if not session.get("admin_csrf_token"):
        session["admin_csrf_token"] = secrets.token_urlsafe(32)

    if request.method == "POST":
        expected = session.get("admin_csrf_token") or ""
        supplied = request.form.get("csrf_token") or ""
        if not hmac.compare_digest(expected, supplied):
            abort(400, description="Token de seguridad inválido. Recargue la página.")


@admin_bp.get("")
@admin_bp.get("/")
def dashboard():
    return render_template(
        "admin/dashboard.html", metrics=admin_service.dashboard(),
        section="dashboard"
    )


@admin_bp.get("/usuarios")
def users():
    return render_template(
        "admin/users.html", users=admin_service.users(), section="users"
    )


@admin_bp.route("/usuarios/nuevo", methods=["GET", "POST"])
def new_user():
    if request.method == "POST":
        try:
            admin_service.create_user(request.form)
            flash("Usuario creado correctamente.", "success")
            return redirect(url_for("admin.users"))
        except ValueError as error:
            flash(str(error), "danger")
        except Exception:
            flash("No se pudo crear el usuario. Revise los datos.", "danger")
    return render_template(
        "admin/user_form.html", user=None, section="users", editing=False
    )


@admin_bp.route("/usuarios/<user_id>/editar", methods=["GET", "POST"])
def edit_user(user_id):
    user = admin_service.get_user(user_id)
    if not user:
        abort(404)
    if request.method == "POST":
        try:
            admin_service.edit_user(user_id, session["user_id"], request.form)
            flash("Usuario actualizado correctamente.", "success")
            return redirect(url_for("admin.users"))
        except ValueError as error:
            flash(str(error), "danger")
        except Exception:
            flash("No se pudo actualizar el usuario.", "danger")
    return render_template(
        "admin/user_form.html", user=user, section="users", editing=True
    )


@admin_bp.post("/usuarios/<user_id>/eliminar")
def delete_user(user_id):
    try:
        admin_service.delete_user(user_id, session["user_id"])
        flash("Usuario eliminado correctamente.", "success")
    except ValueError as error:
        flash(str(error), "warning")
    except Exception:
        flash("No se pudo eliminar el usuario.", "danger")
    return redirect(url_for("admin.users"))


@admin_bp.get("/ordenes")
def orders():
    return render_template(
        "admin/orders.html", orders=admin_service.orders(), section="orders"
    )


@admin_bp.route("/ordenes/nueva", methods=["GET", "POST"])
def new_order():
    if request.method == "POST":
        try:
            order = admin_service.create_order(request.form)
            flash(f"Orden #{order['order_number']} creada correctamente.", "success")
            return redirect(url_for("admin.order_detail", order_id=order["id"]))
        except ValueError as error:
            flash(str(error), "danger")
        except Exception:
            flash("No se pudo crear la orden.", "danger")
    return render_template(
        "admin/order_form.html", order=None, editing=False,
        users=admin_service.users(), catalogs=admin_service.catalogs(),
        section="orders"
    )


@admin_bp.post("/ordenes/<order_id>/revisar")
def open_order_for_review(order_id):
    """El botón habitual 'Ver' registra el inicio de revisión sin pasos extra."""
    order = admin_service.get_order(order_id)
    if not order:
        abort(404)
    if (order.get("order_statuses") or {}).get("code") == "REGISTERED":
        try:
            admin_service.mark_order_under_review(order_id)
        except ValueError as exc:
            # Puede haber avanzado desde otra sesión; ver el estado actual.
            flash(str(exc), "warning")
        except Exception:
            from flask import current_app
            current_app.logger.exception("No se pudo registrar inicio de revisión")
            flash("No se pudo registrar el inicio de revisión.", "danger")
    return redirect(url_for("admin.order_detail", order_id=order_id))


@admin_bp.get("/ordenes/<order_id>")
def order_detail(order_id):
    order = admin_service.get_order(order_id)
    if not order:
        abort(404)
    linked_requests = sales_request_service.list_for_order(order_id)
    active_request = next(
        (item for item in linked_requests
         if item.get('status') in SalesRequestService.ACTIVE_LINK_STATUSES), None
    )
    return render_template(
        "admin/order_detail.html", order=order, section="orders",
        linked_requests=linked_requests, active_request=active_request,
        next_statuses=admin_service.available_status_transitions(order)
    )


@admin_bp.route("/ordenes/<order_id>/editar", methods=["GET", "POST"])
def edit_order(order_id):
    order = admin_service.get_order(order_id)
    if not order:
        abort(404)
    if request.method == "POST":
        try:
            admin_service.edit_order(order_id, request.form)
            flash("Orden actualizada correctamente.", "success")
            return redirect(url_for("admin.order_detail", order_id=order_id))
        except ValueError as error:
            flash(str(error), "danger")
        except Exception:
            flash("No se pudo actualizar la orden.", "danger")
    return render_template(
        "admin/order_form.html", order=order, editing=True,
        users=admin_service.users(), catalogs=admin_service.catalogs(),
        section="orders"
    )


@admin_bp.post("/ordenes/<order_id>/estado")
def advance_order_status(order_id):
    """Solo admite cancelación excepcional; el avance habitual es automático."""
    order = admin_service.get_order(order_id)
    if not order:
        abort(404)
    possible = admin_service.available_status_transitions(order)
    cancel = next((s for s in possible if s.get("code") == "CANCELLED"), None)
    if not cancel or str(request.form.get("next_status_id")) != str(cancel["id"]):
        abort(400, description="Solo se permite la cancelación manual.")
    try:
        admin_service.change_order_status(
            order_id, cancel["id"], request.form.get("status_note")
        )
        flash("Orden cancelada y movimiento registrado en el historial.", "success")
    except ValueError as error:
        flash(str(error), "warning")
    except Exception:
        from flask import current_app
        current_app.logger.exception("No se pudo cancelar la orden")
        flash("No se pudo cancelar la orden. Revisa las funciones SQL de Supabase.", "danger")
    return redirect(url_for("admin.order_detail", order_id=order_id))


@admin_bp.post("/ordenes/<order_id>/eliminar")
def delete_order(order_id):
    try:
        admin_service.delete_order(order_id)
        flash("Orden eliminada.", "success")
    except ValueError as error:
        flash(str(error), "warning")
    except Exception:
        flash("No se pudo eliminar la orden.", "danger")
    return redirect(url_for("admin.orders"))
