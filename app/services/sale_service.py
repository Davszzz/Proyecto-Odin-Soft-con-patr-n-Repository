"""Reglas comerciales: conversión a venta, confirmación y cancelación."""
from app.repositories.sale_repository import SaleRepository
from app.services.sales_request_service import _uuid


class SaleService:
    def __init__(self, repo=None):
        self.repo = repo if repo is not None else SaleRepository()

    def list_all(self):
        return self.repo.list_all()

    def get(self, sale_id):
        return self.repo.get(_uuid(sale_id, 'Venta'))

    def convert(self, request_id, notes=''):
        """La función SQL verifica aprobación y copia íntegro el detalle."""
        if len((notes or '').strip()) > 3000:
            raise ValueError('Las observaciones son demasiado largas.')
        return self.repo.create_from_request(_uuid(request_id, 'Solicitud'), notes)

    def find_by_request(self, request_id):
        return self.repo.find_by_request(_uuid(request_id, 'Solicitud'))

    def convert_simple(self, request_id, notes=''):
        """Flujo principal: SOLPED revisada -> venta confirmada en un clic."""
        if len((notes or '').strip()) > 3000:
            raise ValueError('Las observaciones son demasiado largas.')
        return self.repo.create_from_request_simple(_uuid(request_id, 'Solicitud'), notes)

    def confirm(self, sale_id):
        changed = self.repo.change_status(_uuid(sale_id, 'Venta'), ['REGISTRADA'], 'CONFIRMADA')
        if not changed:
            raise ValueError('Solo una venta registrada puede confirmarse.')
        return changed

    def update_notes(self, sale_id, notes):
        if len((notes or '').strip()) > 3000:
            raise ValueError('Las observaciones son demasiado largas.')
        changed = self.repo.update_notes(_uuid(sale_id, 'Venta'), notes)
        if not changed:
            raise ValueError('Solo se pueden editar ventas registradas.')
        return changed

    def cancel(self, sale_id):
        key = _uuid(sale_id, 'Venta')
        if self.repo.has_document(key):
            raise ValueError('No se puede cancelar una venta con comprobante. Conserve el historial.')
        changed = self.repo.change_status(key, ['REGISTRADA', 'CONFIRMADA'], 'CANCELADA')
        if not changed:
            raise ValueError('Esta venta no puede cancelarse.')
        return changed

    def delete_registered(self, sale_id):
        key = _uuid(sale_id, 'Venta')
        if self.repo.has_document(key):
            raise ValueError('No se puede eliminar una venta vinculada a un comprobante.')
        if not self.repo.delete_registered(key):
            raise ValueError('Solo se pueden eliminar ventas registradas sin comprobante.')
