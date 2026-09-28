from flask import (
    Blueprint,
    render_template,
    request,
    session,
    redirect,
    url_for,
    flash,
    abort
)

from app.services.order_service import OrderService
from app.utils.decorators import login_required


orders_bp = Blueprint(
    "orders",
    __name__
)

order_service = OrderService()


@orders_bp.route("/ordenes")
@login_required
def list_orders():

    orders = (
        order_service
        .get_orders_by_user(
            session["user_id"]
        )
    )

    return render_template(
        "ordenes.html",
        orders=orders
    )


@orders_bp.route(
    "/nueva-orden",
    methods=["GET", "POST"]
)
@login_required
def new_order():

    data = order_service.get_order_form_data()

    if request.method == "POST":

        service_type_id = request.form.get(
            "service_type_id"
        )

        equipment_type_id = request.form.get(
            "equipment_type_id"
        )

        urgency_level_id = request.form.get(
            "urgency_level_id"
        )

        additional_service_ids = request.form.getlist(
            "additional_services"
        )

        # Buscar nombres para mostrarlos en el resumen

        service_type = next(
            (
                item
                for item in data["service_types"]
                if item["id"] == service_type_id
            ),
            None
        )

        equipment_type = next(
            (
                item
                for item in data["equipment_types"]
                if item["id"] == equipment_type_id
            ),
            None
        )

        urgency_level = next(
            (
                item
                for item in data["urgency_levels"]
                if item["id"] == urgency_level_id
            ),
            None
        )

        selected_additional_services = [
            item
            for item in data["additional_services"]
            if item["id"] in additional_service_ids
        ]

        order_data = {
            "service_type_id":
                service_type_id,

            "equipment_type_id":
                equipment_type_id,

            "urgency_level_id":
                urgency_level_id,

            "additional_service_ids":
                additional_service_ids,

            "brand":
                request.form.get(
                    "brand",
                    ""
                ),

            "model":
                request.form.get(
                    "model",
                    ""
                ),

            "serial_number":
                request.form.get(
                    "serial_number",
                    ""
                ),

            "problem_description":
                request.form.get(
                    "problem_description",
                    ""
                )
        }

        return render_template(
            "resumen.html",

            order=order_data,

            service_type=service_type,
            equipment_type=equipment_type,
            urgency_level=urgency_level,

            additional_services=
                selected_additional_services
        )

    return render_template(
        "nueva_orden.html",

        service_types=
            data["service_types"],

        equipment_types=
            data["equipment_types"],

        urgency_levels=
            data["urgency_levels"],

        additional_services=
            data["additional_services"]
    )

@orders_bp.route(
    "/confirmar-orden",
    methods=["POST"]
)
@login_required
def confirm_order():

    try:

        form_data = {
            "service_type_id":
                request.form.get(
                    "service_type_id"
                ),

            "equipment_type_id":
                request.form.get(
                    "equipment_type_id"
                ),

            "urgency_level_id":
                request.form.get(
                    "urgency_level_id"
                ),

            "brand":
                request.form.get(
                    "brand",
                    ""
                ),

            "model":
                request.form.get(
                    "model",
                    ""
                ),

            "serial_number":
                request.form.get(
                    "serial_number",
                    ""
                ),

            "problem_description":
                request.form.get(
                    "problem_description",
                    ""
                ),

            "additional_service_ids":
                request.form.getlist(
                    "additional_services"
                )
        }

        order = order_service.confirm_order(
            session["user_id"],
            form_data
        )

        flash(
            f"Orden #{order['order_number']} registrada correctamente.",
            "success"
        )

        return redirect(
            url_for(
                "orders.list_orders"
            )
        )

    except Exception as error:

        print(
            "ERROR AL CONFIRMAR ORDEN:",
            error
        )

        flash(
            "No se pudo registrar la orden.",
            "danger"
        )

        return redirect(
            url_for(
                "orders.new_order"
            )
        )

@orders_bp.route(
    "/orden/<order_id>"
)
@login_required
def order_detail(order_id):

    order = (
        order_service
        .get_order_detail(
            order_id,
            session["user_id"]
        )
    )

    if not order:
        abort(404)

    return render_template(
        "detalle_orden.html",
        order=order
    )