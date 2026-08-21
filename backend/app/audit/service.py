from datetime import datetime
from uuid import UUID

from pydantic import JsonValue

from backend.app.domain.enums import AuditActor
from backend.app.domain.models import AuditEvent
from backend.app.storage.repositories import AuditRepository


class AuditService:
    def __init__(self, repository: AuditRepository) -> None:
        self._repository = repository

    def record(
        self,
        *,
        actor: AuditActor,
        incident_id: UUID,
        event_type: str,
        payload: dict[str, JsonValue],
        actor_id: str | None = None,
        timestamp: datetime | None = None,
    ) -> AuditEvent:
        values = {
            "actor": actor,
            "actor_id": actor_id,
            "incident_id": incident_id,
            "event_type": event_type,
            "payload": payload,
        }
        if timestamp is not None:
            values["timestamp"] = timestamp
        return self._repository.append(AuditEvent.model_validate(values))
