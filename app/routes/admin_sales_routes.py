"""Proceso comercial administrativo: SOLPED -> venta -> comprobante académico.
Rutas de presentación, sin consultas directas a Supabase. Todas protegidas con rol y CSRF.
"""
import hmac
import secrets
from decimal import Decimal, InvalidOperation

from flask import (
    Blueprint, abort, current_app, flash, redirect,
    render_template, request, session, url_for,
)

from app.repositories.user_repository import UserRepository
from app.services.sales_request_service import SalesRequestService
from app.services.sale_service import SaleService
from app.services.sales_document_service import SalesDocumentService

admin_sales_bp = Blueprint('admin_sales', __name__, url_prefix='/admin/comercial')
request_service = SalesRequestService()
sale_service = SaleService()
document_service = SalesDocumentService()


@admin_sales_bp.before_request
def check_admin():
    if not session.get('user_id'):
        return redirect(url_for('auth.login'))
    user = UserRepository().find_by_id(session['user_id'])
    if not user or user.get('role') != 'ADMIN':
        abort(403, description='Acceso exclusivo para administradores.')
    if not session.get('admin_csrf_token'):
        session['admin_csrf_token'] = secrets.token_urlsafe(32)
    if request.method == 'POST':
        expected = session.get('admin_csrf_token', '')
        provided = request.form.get('csrf_token', '')
        if not hmac.compare_digest(expected, provided):
            abort(400, description='Token de seguridad inválido. Recargue la página.')


def _subtotal(rows):
    total = Decimal('0')
    for line in rows or []:
        try:
            total += Decimal(str(line.get('line_total') or '0'))
        except (ValueError, TypeError, InvalidOperation):
            continue
    return total


def _money(n):
    try:
        return f"{Decimal(str(n or 0)):,.2f}"
    except (ValueError, TypeError, InvalidOperation):
        return '0.00'


@admin_sales_bp.app_template_filter('commercial_money')
def money_filter(n):
    return _money(n)


def _action(callable_action, success, fallback_endpoint, **url_args):
    try:
        result = callable_action()
        flash(success, 'success')
    except ValueError as exc:
        flash(str(exc), 'warning')
        result = None
    except Exception:
        current_app.logger.exception('Error en operación comercial')
        flash('No se pudo completar la operación. Compruebe los datos o su estado.', 'danger')
        result = None
    return result, redirect(url_for(fallback_endpoint, **url_args))


def _submitted_lines(form):
    """Lee filas repetidas del formulario sin mezclar columnas de filas distintas."""
    kinds = form.getlist('line_kind[]')
    references = form.getlist('line_reference[]')
    descriptions = form.getlist('line_description[]')
    quantities = form.getlist('line_quantity[]')
    prices = form.getlist('line_price[]')
    count = len(kinds)
    if not 1 <= count <= 50 or any(len(v) != count for v in
                                      (references, descriptions, quantities, prices)):
        raise ValueError('El detalle debe contener entre 1 y 50 conceptos completos.')
    output = []
    for kind, ref, description, qty, price in zip(
        kinds, references, descriptions, quantities, prices
    ):
        kind = (kind or '').strip().upper()
        output.append({
            'item_kind': kind,
            'service_type_id': ref if kind == 'SERVICIO' else None,
            'inventory_item_id': ref if kind == 'PRODUCTO' else None,
            'description': (description or '').strip(),
            'quantity': qty,
            'unit_price': price,
        })
    return output


def _form_lines_from_saved(detail):
    return [{
        'item_kind': x.get('item_kind', 'SERVICIO'),
        'reference': x.get('service_type_id') if x.get('item_kind') == 'SERVICIO'
                     else x.get('inventory_item_id'),
        'description': x.get('description', ''),
        'quantity': x.get('quantity', 1),
        'unit_price': x.get('unit_price', '0.00'),
    } for x in detail]


def _form_lines_from_post(form):
    count = max(len(form.getlist('line_kind[]')), 1)
    rows = []
    for i in range(min(count, 50)):
        def field(name, default=''):
            vals = form.getlist(name)
            return vals[i] if i < len(vals) else default
        rows.append({
            'item_kind': field('line_kind[]', 'SERVICIO'),
            'reference': field('line_reference[]'),
            'description': field('line_description[]'),
            'quantity': field('line_quantity[]', '1'),
            'unit_price': field('line_price[]', '0.00'),
        })
    return rows


# -------- SOLPED CABECERA + DETALLE --------
@admin_sales_bp.get('/solicitudes')
def sales_requests():
    return render_template('admin/sales_requests.html',
                           records=request_service.list_all(), section='sales_requests')


def _render_request_form(record=None, *, editing=False, fields=None, lines=None,
                         origin_order=None, origin_client=None, origin_warnings=None):
    if editing and record and record.get('service_order_id') and not origin_order:
        link = request_service.linked_order_context(record)
        origin_order, origin_client = link['order'], link['client']
    choices = request_service.catalogues()
    return render_template('admin/sales_request_form.html',
                           record=record or {}, fields=fields or {},
                           lines=lines or [{'item_kind': 'SERVICIO', 'reference': '',
                                             'description': '', 'quantity': '1',
                                             'unit_price': '0.00'}],
                           editing=editing, choices=choices, section='sales_requests',
                           origin_order=origin_order, origin_client=origin_client,
                           origin_warnings=origin_warnings or [])


@admin_sales_bp.route('/solicitudes/desde-orden/<order_id>', methods=['GET', 'POST'])
def request_from_order(order_id):
    """Un clic desde la orden: precarga datos operativos para SOLPED."""
    try:
        context = request_service.prepare_from_order(order_id)
    except ValueError as exc:
        flash(str(exc), 'warning')
        return redirect(url_for('admin.orders'))

    if context['existing_request']:
        flash('Esta orden ya tiene una SOLPED activa. Puedes continuar con ella.', 'info')
        return redirect(url_for('admin_sales.request_detail',
                                request_id=context['existing_request']['id']))

    if request.method == 'POST':
        try:
            key = request_service.create_from_order(
                order_id, request.form.get('notes', ''), _submitted_lines(request.form)
            )
            flash('SOLPED creada desde la orden técnica, sin duplicar los datos.', 'success')
            return redirect(url_for('admin_sales.request_detail', request_id=key))
        except ValueError as exc:
            flash(str(exc), 'danger')
        except Exception:
            current_app.logger.exception('No se pudo crear SOLPED desde orden')
            flash('No se pudo guardar la SOLPED. Verifica sus conceptos y duplicados.', 'danger')
        return _render_request_form(
            fields={**context['fields'], 'notes': request.form.get('notes', '')},
            lines=_form_lines_from_post(request.form),
            origin_order=context['order'], origin_client=context['client'],
            origin_warnings=context['warnings'],
        )

    return _render_request_form(
        fields=context['fields'], lines=context['lines'],
        origin_order=context['order'], origin_client=context['client'],
        origin_warnings=context['warnings'],
    )


@admin_sales_bp.route('/solicitudes/nueva', methods=['GET', 'POST'])
def request_new():
    """El flujo principal siempre inicia en una orden técnica."""
    if request.method == 'POST':
        abort(400, description='Crea la SOLPED desde el detalle de una orden de servicio.')
    flash('Abre una orden y utiliza «Generar SOLPED» para evitar duplicar datos.', 'info')
    return redirect(url_for('admin.orders'))


@admin_sales_bp.route('/solicitudes/<request_id>/editar', methods=['GET', 'POST'])
def request_edit(request_id):
    record = request_service.get(request_id)
    if not record:
        abort(404)
    if record['status'] != 'BORRADOR':
        flash('Solo puedes editar solicitudes en borrador.', 'warning')
        return redirect(url_for('admin_sales.request_detail', request_id=request_id))
    if request.method == 'POST':
        try:
            lines = _submitted_lines(request.form)
            request_service.save_draft(
                record['user_id'] if record.get('service_order_id') else request.form.get('user_id'),
                record['service_order_id'] if record.get('service_order_id') else request.form.get('service_order_id'),
                request.form.get('notes', ''), lines, request_id=request_id
            )
            flash('Borrador actualizado.', 'success')
            return redirect(url_for('admin_sales.request_detail', request_id=request_id))
        except ValueError as exc:
            flash(str(exc), 'danger')
        except Exception:
            current_app.logger.exception('No se pudo editar SOLPED')
            flash('No se pudo guardar la solicitud.', 'danger')
        return _render_request_form(record, editing=True,
                                    fields=request.form.to_dict(),
                                    lines=_form_lines_from_post(request.form))
    return _render_request_form(record, editing=True, fields=record,
                                lines=_form_lines_from_saved(record['details']))


@admin_sales_bp.get('/solicitudes/<request_id>')
def request_detail(request_id):
    record = request_service.get(request_id)
    if not record:
        abort(404)
    return render_template('admin/sales_request_detail.html', record=record,
                           linked_sale=sale_service.find_by_request(request_id),
                           subtotal=_subtotal(record['details']), section='sales_requests')


@admin_sales_bp.post('/solicitudes/<request_id>/<action>')
def request_action(request_id, action):
    operations = {
        'enviar': (request_service.submit, 'Solicitud enviada a revisión.'),
        'aprobar': (request_service.approve, 'Solicitud aprobada.'),
        'rechazar': (request_service.reject, 'Solicitud rechazada.'),
        'cancelar': (request_service.cancel, 'Solicitud cancelada.'),
        'eliminar': (request_service.delete_draft, 'Borrador eliminado.'),
    }
    if action not in operations:
        abort(404)
    func, label = operations[action]
    _, result = _action(lambda: func(request_id), label,
                        'admin_sales.sales_requests' if action == 'eliminar'
                        else 'admin_sales.request_detail',
                        **({} if action == 'eliminar' else {'request_id': request_id}))
    return result


# -------- VENTA CABECERA + DETALLE --------
@admin_sales_bp.get('/ventas')
def sales():
    return render_template('admin/sales.html', records=sale_service.list_all(),
                           section='sales')


@admin_sales_bp.post('/solicitudes/<request_id>/convertir')
def sale_convert(request_id):
    try:
        key = sale_service.convert_simple(request_id, request.form.get('notes', ''))
        flash('Venta confirmada desde la SOLPED. Ya puedes preparar el comprobante.', 'success')
        return redirect(url_for('admin_sales.sale_detail', sale_id=key))
    except ValueError as exc:
        flash(str(exc), 'warning')
    except Exception:
        current_app.logger.exception('No se pudo convertir la solicitud a venta')
        flash('No se pudo convertir la solicitud a venta.', 'danger')
    return redirect(url_for('admin_sales.request_detail', request_id=request_id))


@admin_sales_bp.get('/ventas/<sale_id>')
def sale_detail(sale_id):
    sale = sale_service.get(sale_id)
    if not sale:
        abort(404)
    document = next((d for d in document_service.list_all()
                     if str(d['sale_id']) == str(sale_id)), None)
    return render_template('admin/sale_detail.html', sale=sale, document=document,
                           subtotal=_subtotal(sale['details']), section='sales')


@admin_sales_bp.post('/ventas/<sale_id>/notas')
def sale_notes(sale_id):
    _, result = _action(lambda: sale_service.update_notes(
        sale_id, request.form.get('notes', '')),
        'Observaciones actualizadas.', 'admin_sales.sale_detail', sale_id=sale_id)
    return result


@admin_sales_bp.post('/ventas/<sale_id>/<action>')
def sale_action(sale_id, action):
    allowed = {'confirmar': (sale_service.confirm, 'Venta confirmada.'),
               'cancelar': (sale_service.cancel, 'Venta cancelada.'),
               'eliminar': (sale_service.delete_registered, 'Venta no confirmada eliminada.')}
    if action not in allowed:
        abort(404)
    func, message = allowed[action]
    if action == 'eliminar':
        _, result = _action(lambda: func(sale_id), message, 'admin_sales.sales')
    else:
        _, result = _action(lambda: func(sale_id), message, 'admin_sales.sale_detail',
                            sale_id=sale_id)
    return result


# -------- FACTURA / BOLETA (ACADÉMICAS) --------
@admin_sales_bp.get('/comprobantes')
def documents():
    return render_template('admin/sale_documents.html',
                           records=document_service.list_all(), section='documents')


def _render_document_form(sale, *, record=None, fields=None, editing=False):
    return render_template('admin/sale_document_form.html', sale=sale,
                           record=record or {}, fields=fields or {},
                           editing=editing, section='documents')


@admin_sales_bp.route('/ventas/<sale_id>/comprobante/nuevo', methods=['GET', 'POST'])
def document_new(sale_id):
    sale = sale_service.get(sale_id)
    if not sale:
        abort(404)
    if sale['status'] != 'CONFIRMADA':
        flash('Primero confirma la venta.', 'warning')
        return redirect(url_for('admin_sales.sale_detail', sale_id=sale_id))
    if request.method == 'POST':
        try:
            key = document_service.create_draft(sale_id, request.form.to_dict())
            flash('Comprobante académico creado como borrador.', 'success')
            return redirect(url_for('admin_sales.document_detail', document_id=key))
        except ValueError as exc:
            flash(str(exc), 'danger')
        except Exception:
            current_app.logger.exception('No se pudo crear comprobante')
            flash('No se pudo generar el comprobante. Revisa los datos y la numeración.', 'danger')
    return _render_document_form(sale, fields=request.form.to_dict())


@admin_sales_bp.route('/comprobantes/<document_id>/editar', methods=['GET', 'POST'])
def document_edit(document_id):
    doc = document_service.get(document_id)
    if not doc:
        abort(404)
    if doc['status'] != 'BORRADOR':
        flash('Solo se editan comprobantes en borrador.', 'warning')
        return redirect(url_for('admin_sales.document_detail', document_id=document_id))
    sale = sale_service.get(doc['sale_id'])
    if not sale:
        abort(404)
    if request.method == 'POST':
        try:
            document_service.update_draft(document_id, request.form.to_dict())
            flash('Comprobante actualizado.', 'success')
            return redirect(url_for('admin_sales.document_detail', document_id=document_id))
        except ValueError as exc:
            flash(str(exc), 'danger')
        except Exception:
            current_app.logger.exception('No se pudo editar comprobante')
            flash('No se pudo guardar el comprobante.', 'danger')
        return _render_document_form(sale, record=doc, fields=request.form.to_dict(), editing=True)
    return _render_document_form(sale, record=doc, fields=doc, editing=True)


@admin_sales_bp.get('/comprobantes/<document_id>')
def document_detail(document_id):
    doc = document_service.get(document_id)
    if not doc:
        abort(404)
    return render_template('admin/sale_document_detail.html', doc=doc,
                           subtotal=_subtotal(doc['details']), section='documents')


@admin_sales_bp.post('/comprobantes/<document_id>/<action>')
def document_action(document_id, action):
    allowed = {'emitir': (document_service.emit, 'Comprobante marcado como emitido (simulación).'),
               'anular': (document_service.annul, 'Comprobante anulado (simulación).'),
               'eliminar': (document_service.delete_draft, 'Borrador de comprobante eliminado.')}
    if action not in allowed:
        abort(404)
    func, message = allowed[action]
    if action == 'eliminar':
        _, result = _action(lambda: func(document_id), message, 'admin_sales.documents')
    else:
        _, result = _action(lambda: func(document_id), message,
                            'admin_sales.document_detail', document_id=document_id)
    return result
