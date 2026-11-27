"""Presentación de la auditoría R8, sin inventar responsables históricos."""
import logging
from app.repositories.audit_repository import AuditRepository

logger = logging.getLogger(__name__)


class AuditService:
    def __init__(self, repository=None):
        self.repository = repository if repository is not None else AuditRepository()

    @staticmethod
    def _actor(row, prefix, names, lookup_failed):
        source = row.get(prefix + '_by_source')
        actor_id = row.get(prefix + '_by')
        if source == 'SYSTEM':
            return 'Sistema'
        if source != 'USER' or not actor_id:
            return 'No registrado'
        if lookup_failed:
            return 'Nombre no disponible'
        return names.get(str(actor_id)) or 'Usuario no disponible'

    @staticmethod
    def _date(row, prefix):
        # Una fecha técnica de migración no debe mostrarse como fecha histórica.
        return row.get(prefix + '_at') if row.get(prefix + '_at_known') is True else None

    def for_records(self, table, ids):
        keys = [str(key) for key in ids if key]
        if not keys:
            return {}
        try:
            rows = self.repository.records(table, keys)
        except Exception as exc:
            # La vista principal sigue funcionando incluso si falta la migración R8.
            logger.warning('Lectura de auditoría no disponible (%s, %s)', table, type(exc).__name__)
            return {key: {'available': False} for key in keys}
        actors = {row[prefix + '_by'] for row in rows for prefix in ('created', 'updated')
                  if row.get(prefix + '_by_source') == 'USER' and row.get(prefix + '_by')}
        lookup_failed = False
        try:
            names = self.repository.actor_names(actors) if actors else {}
        except Exception as exc:
            logger.warning('Consulta de autores no disponible (%s)', type(exc).__name__)
            names, lookup_failed = {}, True
        result = {key: {'available': False} for key in keys}
        for row in rows:
            result[str(row['id'])] = {
                'available': True,
                'created_at': self._date(row, 'created'),
                'updated_at': self._date(row, 'updated'),
                'created_by': self._actor(row, 'created', names, lookup_failed),
                'updated_by': self._actor(row, 'updated', names, lookup_failed),
            }
        return result

    def for_record(self, table, record_id):
        return self.for_records(table, [record_id]).get(str(record_id), {'available': False})
