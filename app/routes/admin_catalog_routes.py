"""CRUD de catálogos administrativos: proveedores, inventario y servicios.

Las validaciones de negocio viven en Services y la persistencia en Repositories.
Este Blueprint es independiente del admin_bp existente, por lo que aplica su
propia protección de rol ADMIN y token CSRF.
"""
import hmac
import secrets

from flask import (
    Blueprint, abort, current_app, flash, redirect, render_template,
    request, session, url_for,
)

from app.repositories.user_repository import UserRepository
from app.services.inventory_service import InventoryService
from app.services.service_catalog_service import ServiceCatalogService
from app.services.supplier_service import SupplierService

admin_catalog_bp = Blueprint("admin_catalog", __name__, url_prefix="/admin/catalogos")
supplier_service = SupplierService()
inventory_service = InventoryService()
service_catalog_service = ServiceCatalogService()


@admin_catalog_bp.before_request
def only_admin():
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))

    user = UserRepository().find_by_id(session["user_id"])
    if not user or user.get("role") != "ADMIN":
        abort(403, description="Acceso exclusivo para administradores.")

    if not session.get("admin_csrf_token"):
        session["admin_csrf_token"] = secrets.token_urlsafe(32)

    if request.method == "POST":
        expected = session.get("admin_csrf_token") or ""
        provided = request.form.get("csrf_token") or ""
        if not hmac.compare_digest(expected, provided):
            abort(400, description="Token de seguridad inválido. Recargue la página.")


def _save(service, action, values, redirect_endpoint, success_msg, *, entity_id=None):
    """Ejecuta una operación de negocio y presenta errores sin detalles internos."""
    try:
        if action == "create":
            service.create(values)
        else:
            service.update(entity_id, values)
        flash(success_msg, "success")
        return redirect(url_for(redirect_endpoint))
    except ValueError as exc:
        flash(str(exc), "danger")
        return None
    except Exception:
        current_app.logger.exception("Error al guardar catálogo administrativo")
        flash("No se pudo guardar. Verifique los datos e inténtelo nuevamente.", "danger")
        return None


def _toggle(service, entity_id, is_active, endpoint, item_name):
    try:
        if is_active:
            service.deactivate(entity_id)
            flash(f"{item_name} desactivado correctamente.", "success")
        else:
            service.activate(entity_id)
            flash(f"{item_name} activado correctamente.", "success")
    except ValueError as exc:
        flash(str(exc), "warning")
    except Exception:
        current_app.logger.exception("Error al cambiar estado del catálogo")
        flash("No se pudo actualizar el estado del registro.", "danger")
    return redirect(url_for(endpoint))


# --------------------------- PROVEEDORES ---------------------------
@admin_catalog_bp.get("/proveedores")
def suppliers():
    return render_template("admin/suppliers.html",
                           suppliers=supplier_service.list_all(), section="suppliers")


@admin_catalog_bp.route("/proveedores/nuevo", methods=["GET", "POST"])
def supplier_new():
    values = {}
    if request.method == "POST":
        values = request.form.to_dict()
        result = _save(supplier_service, "create", values, "admin_catalog.suppliers",
                       "Proveedor registrado correctamente.")
        if result is not None:
            return result
    return render_template("admin/supplier_form.html", supplier=values,
                           editing=False, section="suppliers")


@admin_catalog_bp.route("/proveedores/<supplier_id>/editar", methods=["GET", "POST"])
def supplier_edit(supplier_id):
    supplier = supplier_service.get_by_id(supplier_id)
    if not supplier:
        abort(404)
    if request.method == "POST":
        values = request.form.to_dict()
        result = _save(supplier_service, "update", values, "admin_catalog.suppliers",
                       "Proveedor actualizado correctamente.", entity_id=supplier_id)
        if result is not None:
            return result
        supplier = {**supplier, **values}
    return render_template("admin/supplier_form.html", supplier=supplier,
                           editing=True, section="suppliers")


@admin_catalog_bp.post("/proveedores/<supplier_id>/estado")
def supplier_toggle(supplier_id):
    supplier = supplier_service.get_by_id(supplier_id)
    if not supplier:
        abort(404)
    return _toggle(supplier_service, supplier_id, supplier["active"],
                   "admin_catalog.suppliers", "Proveedor")


# ------------------------ PRODUCTOS / INSUMOS ------------------------
@admin_catalog_bp.get("/inventario")
def inventory():
    return render_template("admin/inventory.html",
                           items=inventory_service.list_all(), section="inventory")


def _supplier_options(current_id=None):
    # Permite mostrar el proveedor histórico inactivo si el producto lo tenía.
    return [s for s in supplier_service.list_all()
            if s.get("active") or str(s["id"]) == str(current_id)]


@admin_catalog_bp.route("/inventario/nuevo", methods=["GET", "POST"])
def inventory_new():
    values = {}
    if request.method == "POST":
        values = request.form.to_dict()
        result = _save(inventory_service, "create", values, "admin_catalog.inventory",
                       "Producto o insumo registrado correctamente.")
        if result is not None:
            return result
    return render_template("admin/inventory_form.html", item=values, editing=False,
                           suppliers=_supplier_options(values.get("supplier_id")),
                           section="inventory")


@admin_catalog_bp.route("/inventario/<item_id>/editar", methods=["GET", "POST"])
def inventory_edit(item_id):
    item = inventory_service.get_by_id(item_id)
    if not item:
        abort(404)
    if request.method == "POST":
        values = request.form.to_dict()
        result = _save(inventory_service, "update", values, "admin_catalog.inventory",
                       "Producto o insumo actualizado correctamente.", entity_id=item_id)
        if result is not None:
            return result
        item = {**item, **values}
    return render_template("admin/inventory_form.html", item=item, editing=True,
                           suppliers=_supplier_options(item.get("supplier_id")),
                           section="inventory")


@admin_catalog_bp.post("/inventario/<item_id>/estado")
def inventory_toggle(item_id):
    item = inventory_service.get_by_id(item_id)
    if not item:
        abort(404)
    return _toggle(inventory_service, item_id, item["active"],
                   "admin_catalog.inventory", "Producto o insumo")


# -------------------------- TIPOS DE SERVICIO -------------------------
@admin_catalog_bp.get("/servicios")
def services():
    return render_template("admin/services.html",
                           services=service_catalog_service.list_all(), section="services")


@admin_catalog_bp.route("/servicios/nuevo", methods=["GET", "POST"])
def service_new():
    values = {}
    if request.method == "POST":
        values = request.form.to_dict()
        result = _save(service_catalog_service, "create", values, "admin_catalog.services",
                       "Servicio técnico registrado correctamente.")
        if result is not None:
            return result
    return render_template("admin/service_form.html", service=values, editing=False,
                           section="services")


@admin_catalog_bp.route("/servicios/<service_id>/editar", methods=["GET", "POST"])
def service_edit(service_id):
    service = service_catalog_service.get_by_id(service_id)
    if not service:
        abort(404)
    if request.method == "POST":
        values = request.form.to_dict()
        result = _save(service_catalog_service, "update", values, "admin_catalog.services",
                       "Servicio técnico actualizado correctamente.", entity_id=service_id)
        if result is not None:
            return result
        service = {**service, **values}
    return render_template("admin/service_form.html", service=service, editing=True,
                           section="services")


@admin_catalog_bp.post("/servicios/<service_id>/estado")
def service_toggle(service_id):
    service = service_catalog_service.get_by_id(service_id)
    if not service:
        abort(404)
    return _toggle(service_catalog_service, service_id, service["active"],
                   "admin_catalog.services", "Servicio técnico")
