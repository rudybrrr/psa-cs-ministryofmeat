from enum import StrEnum


class IncidentState(StrEnum):
    INCIDENT_RECEIVED = "INCIDENT_RECEIVED"
    COLLECTING_STATE = "COLLECTING_STATE"
    CONSTRAINT_VALIDATION = "CONSTRAINT_VALIDATION"
    RECOVERY_ANALYSIS = "RECOVERY_ANALYSIS"
    RESOLVED = "RESOLVED"
    ESCALATED = "ESCALATED"


class DecisionAction(StrEnum):
    EXPEDITE = "EXPEDITE"
    REQUEST_RTA = "REQUEST_RTA"


class DecisionStatus(StrEnum):
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"


class AllocationStatus(StrEnum):
    PROPOSED = "PROPOSED"
    ALLOCATED = "ALLOCATED"
    REJECTED = "REJECTED"


class RTARequestStatus(StrEnum):
    PENDING = "PENDING"
    SENT = "SENT"
    CLOSED = "CLOSED"


class CarrierResponseType(StrEnum):
    ACCEPT = "ACCEPT"
    COUNTER = "COUNTER"


class ApprovalStatus(StrEnum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class AuditActor(StrEnum):
    AGENT = "AGENT"
    SOLVER = "SOLVER"
    POLICY = "POLICY"
    OPERATOR = "OPERATOR"
    CARRIER = "CARRIER"
    SYSTEM = "SYSTEM"
