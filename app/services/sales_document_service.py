"""Comprobantes internos académicos: NO constituye emisión SUNAT."""
from decimal import Decimal, InvalidOperation
import re

from app.repositories.sales_document_repository import SalesDocumentRepository
from app.services.sales_request_service import _uuid


class SalesDocumentService:
    def __init__(self, repo=None):
        self.repo = repo if repo is not None else SalesDocumentRepository()

    def list_all(self):
        return self.repo.list_all()

    def get(self, document_id):
        return self.repo.get(_uuid(document_id, 'Comprobante'))

    @staticmethod
    def _fields(data):
        kind = str(data.get('document_type') or '').strip().upper()
        if kind not in ('FACTURA', 'BOLETA'):
            raise ValueError('Seleccione FACTURA o BOLETA.')
        series = str(data.get('series') or '').strip().upper()
        number = str(data.get('document_number') or '').strip()
        buyer = str(data.get('buyer_name') or '').strip()
        tax_id = str(data.get('buyer_tax_id') or '').strip() or None
        address = str(data.get('buyer_address') or '').strip() or None
        if not (1 <= len(series) <= 12 and 1 <= len(number) <= 20):
            raise ValueError('La serie y el número del comprobante son obligatorios.')
        if not (1 <= len(buyer) <= 180):
            raise ValueError('Ingrese el nombre o razón social del comprador.')
        if kind == 'FACTURA' and (not tax_id or not re.fullmatch(r'\d{11}', tax_id)):
            raise ValueError('La factura requiere un RUC de 11 dígitos.')
        try:
            rate = Decimal(str(data.get('tax_rate', '0.18')))
        except (InvalidOperation, ValueError, TypeError):
            raise ValueError('La tasa del impuesto es inválida.') from None
        if not rate.is_finite() or not 0 <= rate <= 1 or rate.as_tuple().exponent < -4:
            raise ValueError('La tasa debe estar entre 0 y 1 con máximo 4 decimales.')
        return {
            'document_type': kind,
            'series': series,
            'document_number': number,
            'buyer_name': buyer,
            'buyer_tax_id': tax_id,
            'buyer_address': address,
            'tax_rate': str(rate),
        }

    def create_draft(self, sale_id, fields):
        data = self._fields(fields)
        return self.repo.create(
            _uuid(sale_id, 'Venta'), data['document_type'], data['series'],
            data['document_number'], data['buyer_name'], data['buyer_tax_id'],
            data['buyer_address'], data['tax_rate'],
        )

    def update_draft(self, document_id, fields):
        result = self.repo.update_draft(_uuid(document_id, 'Comprobante'), self._fields(fields))
        if not result:
            raise ValueError('Solo pueden editarse comprobantes en borrador.')
        return result

    def emit(self, document_id):
        """Emisión SIMULADA, sin conexión a SUNAT."""
        result = self.repo.change_status(_uuid(document_id, 'Comprobante'), 'BORRADOR', 'EMITIDO')
        if not result:
            raise ValueError('Solo un comprobante en borrador puede marcarse como emitido.')
        return result

    def annul(self, document_id):
        result = self.repo.change_status(_uuid(document_id, 'Comprobante'), 'EMITIDO', 'ANULADO')
        if not result:
            raise ValueError('Solo un comprobante emitido puede anularse.')
        return result

    def delete_draft(self, document_id):
        if not self.repo.delete_draft(_uuid(document_id, 'Comprobante')):
            raise ValueError('Solo pueden eliminarse comprobantes en borrador.')
