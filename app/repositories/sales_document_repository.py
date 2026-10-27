"""Persistencia de boletas/facturas académicas; sin integración con SUNAT."""
from datetime import datetime, timezone


def _db():
    from app.config import supabase
    return supabase


class SalesDocumentRepository:
    def list_all(self):
        response = (_db().table('sale_documents').select('*')
                    .order('created_at', desc=True).execute())
        return response.data or []

    def get(self, document_id):
        response = (_db().table('sale_documents').select('*')
                    .eq('id', document_id).limit(1).execute())
        if not response.data:
            return None
        document = response.data[0]
        response = (_db().table('sale_document_details').select('*')
                    .eq('document_id', document_id).order('line_number').execute())
        document['details'] = response.data or []
        return document

    def create(self, sale_id, doc_type, series, number, buyer_name,
               buyer_tax_id, buyer_address, tax_rate):
        response = _db().rpc('create_sale_document', {
            'p_sale_id': sale_id,
            'p_document_type': doc_type,
            'p_series': series,
            'p_document_number': number,
            'p_buyer_name': buyer_name,
            'p_buyer_tax_id': buyer_tax_id,
            'p_buyer_address': buyer_address,
            'p_tax_rate': str(tax_rate),
        }).execute()
        return response.data

    def update_draft(self, document_id, values):
        response = (_db().table('sale_documents').update(values)
                    .eq('id', document_id).eq('status', 'BORRADOR').execute())
        return response.data[0] if response.data else None

    def change_status(self, document_id, previous_state, new_status):
        changes = {'status': new_status}
        if new_status == 'EMITIDO':
            changes['issued_at'] = datetime.now(timezone.utc).isoformat()
        response = (_db().table('sale_documents').update(changes)
                    .eq('id', document_id).eq('status', previous_state).execute())
        return response.data[0] if response.data else None

    def delete_draft(self, document_id):
        """Descarta un comprobante no emitido y sus líneas por FK CASCADE."""
        response = (_db().table('sale_documents').delete()
                    .eq('id', document_id).eq('status', 'BORRADOR').execute())
        return bool(response.data)
