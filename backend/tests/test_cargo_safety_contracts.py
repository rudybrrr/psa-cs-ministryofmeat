from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from backend.app.domain.cargo_safety import (
    CargoNote,
    SemanticCheckFailureKind,
    SemanticCheckResult,
    SemanticSafetyAssessment,
)


def test_failed_assessment_requires_failure_kind_and_forbids_evidence_excerpt() -> None:
    values = dict(
        review_id=UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"),
        incident_id=UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
        container_id="SYN-CNT-010",
        cargo_note_id=UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc"),
        result=SemanticCheckResult.CHECK_FAILED,
        explanation="Checker configuration is unavailable.",
        structured_dangerous_goods=False,
        structured_un_number=None,
        structured_commodity="Synthetic dry cargo",
        checker_kind="openai",
        prompt_version="cargo-semantic-v1",
        created_at=datetime(2026, 8, 23, tzinfo=UTC),
    )
    with pytest.raises(ValidationError):
        SemanticSafetyAssessment(**values)
    with pytest.raises(ValidationError):
        SemanticSafetyAssessment(
            **values,
            failure_kind=SemanticCheckFailureKind.CONFIGURATION_ERROR,
            evidence_excerpt="invented",
        )


def test_cargo_note_rejects_empty_text_and_naive_time() -> None:
    with pytest.raises(ValidationError):
        CargoNote(
            incident_id=UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
            container_id="SYN-CNT-010", text=" ", source="demo",
            created_at=datetime(2026, 8, 23),
        )
