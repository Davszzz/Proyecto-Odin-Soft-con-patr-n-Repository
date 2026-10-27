"""Reglas de negocio de solicitudes (SOLPED): borrador -> pendiente -> aprobada."""
import re
from decimal import Decimal, InvalidOperation
from uuid import UUID

from app.repositories.sales_request_repository import SalesRequestRepository


def _uuid(value, label, optional=False):
    if optional and not value:
        return None
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        raise ValueError(f'{label}: identificador inválido.') from None


def _amount(value, label, *, allow_zero=False):
    try:
        n = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(f'{label}: debe ser numérico.') from None
    if not n.is_finite() or n < 0 or (not allow_zero and n == 0):
        raise ValueError(f'{label}: valor inválido.')
    if n > Decimal('9999999999.99') or n.as_tuple().exponent < -2:
        raise ValueError(f'{label}: máximo dos decimales y valor permitido.')
    return str(n)


class SalesRequestService:
    def __init__(self, repo=None):
        self.repo = repo if repo is not None else SalesRequestRepository()

    def list_all(self):
        return self.repo.list_all()

    def get(self, request_id):
        return self.repo.get(_uuid(request_id, 'Solicitud'))

    def catalogues(self):
        return {
            'clients': self.repo.list_clients(),
            'services': self.repo.list_services(),
            'products': self.repo.list_products(),
            'orders': self.repo.list_service_orders(),
        }

    ACTIVE_LINK_STATUSES = frozenset({'BORRADOR', 'PENDIENTE', 'APROBADA'})

    def list_for_order(self, order_id):
        return self.repo.list_for_order(_uuid(order_id, 'Orden técnica'))

    def prepare_from_order(self, order_id):
        """Prepara una SOLPED desde la orden con servicio y repuestos cobrables.

        Los costos del inventario no se convierten en precios comerciales.
        Tampoco hay movimientos de inventario en esta operación.
        """
        order_id = _uuid(order_id, 'Orden técnica')
        order = self.repo.get_service_order_context(order_id)
        if not order:
            raise ValueError('La orden técnica no existe.')
        client = self.repo.get_client(order['user_id'])
        if not client or client.get('role') != 'CLIENT':
            raise ValueError('La orden técnica no pertenece a una cuenta de cliente válida.')

        previous = self.repo.list_for_order(order_id)
        current = next((r for r in previous
                        if r.get('status') in self.ACTIVE_LINK_STATUSES), None)
        if current:
            return {'existing_request': current, 'order': order, 'client': client,
                    'lines': [], 'fields': {}, 'warnings': []}

        active_services = {str(x['id']): x for x in self.repo.list_services()}
        active_products = {str(x['id']): x for x in self.repo.list_products()}
        warnings = []
        lines = []
        service_id = str(order.get('service_type_id') or '')
        if service_id in active_services:
            service = active_services[service_id]
            lines.append({'item_kind': 'SERVICIO', 'reference': service_id,
                          'description': service['name'], 'quantity': '1',
                          'unit_price': (str(service['sale_price'])
                                         if service.get('sale_price') is not None else ''),
                          'catalog_price_configured': service.get('sale_price') is not None})
        else:
            warnings.append('El servicio original no está activo o no está asignado: selecciónalo manualmente.')

        for material in self.repo.list_order_materials(order_id):
            item_id = str(material.get('inventory_item_id') or '')
            if item_id not in active_products:
                warnings.append('Se omitió un material inactivo; revisa los conceptos de la orden.')
                continue
            if len(lines) >= 50:
                warnings.append('Hay más de 50 conceptos: revisa los materiales adicionales manualmente.')
                break
            item = active_products[item_id]
            # Un insumo interno es un consumo operativo, no un cobro automático.
            # Puede añadirse manualmente a la SOLPED si se factura aparte.
            if str(item.get('item_type') or 'PRODUCTO').upper() == 'INSUMO':
                continue
            lines.append({'item_kind': 'PRODUCTO', 'reference': item_id,
                          'description': item['name'],
                          'quantity': str(material['quantity']),
                          'unit_price': (str(item['sale_price'])
                                         if item.get('sale_price') is not None else ''),
                          'catalog_price_configured': item.get('sale_price') is not None})

        if not lines:
            lines = [{'item_kind': 'SERVICIO', 'reference': '',
                      'description': '', 'quantity': '1', 'unit_price': ''}]
        number = order.get('order_number') or order_id[:8]
        notes = f'SOLPED originada desde la orden técnica #{number}.'
        return {'existing_request': None, 'order': order, 'client': client,
                'lines': lines,
                'fields': {'user_id': str(order['user_id']),
                           'service_order_id': order_id, 'notes': notes},
                'warnings': warnings}

    def linked_order_context(self, request_record):
        """Datos del origen de una SOLPED existente para mostrar campos bloqueados."""
        order_id = request_record.get('service_order_id')
        if not order_id:
            return None
        order = self.repo.get_service_order_context(_uuid(order_id, 'Orden técnica'))
        if not order or str(order.get('user_id')) != str(request_record.get('user_id')):
            raise ValueError('No se pudo verificar el vínculo con la orden técnica.')
        client = self.repo.get_client(order['user_id'])
        if not client:
            raise ValueError('El cliente asociado ya no está disponible.')
        return {'order': order, 'client': client}

    @staticmethod
    def _assert_order_lines_match(lines, originals):
        """En SOLPED vinculada, solo cambian precios; orden determina conceptos/cantidades."""
        if len(lines) != len(originals):
            raise ValueError('Los conceptos deben coincidir con la orden técnica. Actualiza los materiales en la orden.')
        for line, source in zip(lines, originals):
            kind = str(line.get('item_kind') or '').upper()
            identifier = str(line.get('service_type_id') if kind == 'SERVICIO'
                             else line.get('inventory_item_id') or '')
            reference = str(source.get('reference') or source.get('service_type_id')
                            or source.get('inventory_item_id') or '')
            try:
                qty_equal = Decimal(str(line.get('quantity'))) == Decimal(str(source.get('quantity')))
            except (InvalidOperation, TypeError, ValueError):
                qty_equal = False
            if (kind != source.get('item_kind') or identifier != reference or not qty_equal
                    or str(line.get('description') or '') != str(source.get('description') or '')):
                raise ValueError('La SOLPED vinculada conserva los conceptos de la orden. Solo modifica sus precios.')

    def create_from_order(self, order_id, notes, lines):
        # Revalidamos el origen al guardar; no confiamos en IDs ocultos del HTML.
        context = self.prepare_from_order(order_id)
        if context['existing_request']:
            raise ValueError('Esta orden ya tiene una SOLPED activa. Accede a ella desde la orden.')
        self._assert_order_lines_match(lines, context['lines'])
        return self.save_draft(context['order']['user_id'], context['order']['id'],
                               notes, lines)

    def save_draft(self, user_id, service_order_id, notes, lines, *, request_id=None):
        client_id = _uuid(user_id, 'Cliente')
        client = self.repo.get_client(client_id)
        if not client or client.get('role') != 'CLIENT':
            raise ValueError('Seleccione un cliente existente.')
        order_id = _uuid(service_order_id, 'Orden técnica', optional=True)
        if order_id:
            order = self.repo.get_service_order(order_id)
            if not order or str(order.get('user_id')) != client_id:
                raise ValueError('La orden técnica debe pertenecer al cliente seleccionado.')
        if len((notes or '').strip()) > 3000:
            raise ValueError('Las observaciones no deben superar 3000 caracteres.')
        if not isinstance(lines, list) or not 1 <= len(lines) <= 50:
            raise ValueError('Ingrese entre 1 y 50 conceptos.')

        valid_services = {str(x['id']) for x in self.repo.list_services()}
        valid_products = {str(x['id']) for x in self.repo.list_products()}
        normalised = []
        for pos, line in enumerate(lines, 1):
            if not isinstance(line, dict):
                raise ValueError(f'Línea {pos}: formato inválido.')
            kind = str(line.get('item_kind') or '').strip().upper()
            if kind not in ('SERVICIO', 'PRODUCTO'):
                raise ValueError(f'Línea {pos}: tipo de concepto inválido.')
            ref_name = 'service_type_id' if kind == 'SERVICIO' else 'inventory_item_id'
            ref_id = _uuid(line.get(ref_name), f'Línea {pos}')
            available = valid_services if kind == 'SERVICIO' else valid_products
            if ref_id not in available:
                raise ValueError(f'Línea {pos}: servicio o producto no disponible.')
            description = str(line.get('description') or '').strip()
            if len(description) > 250:
                raise ValueError(f'Línea {pos}: descripción demasiado larga.')
            normalised.append({
                'item_kind': kind,
                'service_type_id': ref_id if kind == 'SERVICIO' else None,
                'inventory_item_id': ref_id if kind == 'PRODUCTO' else None,
                'description': description,
                'quantity': _amount(line.get('quantity'), f'Línea {pos} cantidad'),
                'unit_price': _amount(line.get('unit_price'), f'Línea {pos} precio', allow_zero=True),
            })
        existing_id = _uuid(request_id, 'Solicitud', optional=True)
        if existing_id:
            current = self.repo.get(existing_id)
            if not current or current['status'] != 'BORRADOR':
                raise ValueError('Solo pueden editarse las solicitudes en borrador.')
            # Una solicitud que nació de una orden no puede cambiar su orden o cliente.
            if current.get('service_order_id') and (
                str(current['service_order_id']) != str(order_id)
                or str(current['user_id']) != client_id
            ):
                raise ValueError('No puedes reasignar el cliente o la orden de una SOLPED vinculada.')
            if current.get('service_order_id'):
                sources = [
                    {'item_kind': entry['item_kind'],
                     'service_type_id': entry.get('service_type_id'),
                     'inventory_item_id': entry.get('inventory_item_id'),
                     'description': entry.get('description') or '',
                     'quantity': entry['quantity']}
                    for entry in current.get('details', [])
                ]
                self._assert_order_lines_match(normalised, sources)
        elif order_id:
            context = self.prepare_from_order(order_id)
            if context['existing_request']:
                raise ValueError('Esta orden ya tiene una SOLPED activa. Abre la solicitud existente.')
            self._assert_order_lines_match(normalised, context['lines'])
        return self.repo.save(existing_id, client_id, order_id, notes, normalised)

    def _status(self, request_id, previous, target):
        changed = self.repo.change_status(_uuid(request_id, 'Solicitud'), previous, target)
        if not changed:
            raise ValueError('No se pudo cambiar el estado de la solicitud. Verifique su estado actual.')
        return changed

    def submit(self, request_id):
        return self._status(request_id, ['BORRADOR'], 'PENDIENTE')

    def approve(self, request_id):
        return self._status(request_id, ['PENDIENTE'], 'APROBADA')

    def reject(self, request_id):
        return self._status(request_id, ['PENDIENTE'], 'RECHAZADA')

    def cancel(self, request_id):
        return self._status(request_id, ['BORRADOR', 'PENDIENTE'], 'CANCELADA')

    def delete_draft(self, request_id):
        if not self.repo.delete_draft(_uuid(request_id, 'Solicitud')):
            raise ValueError('Solo se pueden eliminar solicitudes en borrador.')
