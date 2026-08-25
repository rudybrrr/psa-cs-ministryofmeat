from backend.app.domain.canonical_replay import (
    CanonicalReplayActionType,
    CanonicalReplayStage,
    CanonicalReplayStageView,
    CanonicalReplayStatus,
)


def test_stage_vocabulary_matches_spec_exactly() -> None:
    assert [stage.value for stage in CanonicalReplayStage] == [
        "READY_TO_CREATE",
        "READY_FOR_PRE_DISCHARGE",
        "READY_TO_START_AGENT",
        "READY_TO_ADVANCE_TO_EVIDENCE_WAIT",
        "WAITING_FOR_ACTIVE_EVIDENCE",
        "READY_TO_RECONSIDER",
        "READY_TO_PREPARE_RTA",
        "REQUEST_APPROVAL_REQUIRED",
        "REQUEST_APPROVED_READY_TO_SEND",
        "WAITING_FOR_CARRIER",
        "CARRIER_COUNTER_RECEIVED",
        "COUNTER_APPROVAL_REQUIRED",
        "COUNTER_APPROVED_READY_TO_RESUME",
        "READY_FOR_SAFETY_EVIDENCE",
        "SAFETY_REVIEW_PENDING",
        "SAFETY_BLOCKED",
        "COMPLETE",
        "FAILED",
        "TRADEOFF_DECISION_REQUIRED",
        "OFF_CANONICAL_PATH",
    ]


def test_status_and_action_vocabularies_match_spec() -> None:
    assert [status.value for status in CanonicalReplayStatus] == [
        "PENDING_ACTION",
        "WAITING_HUMAN",
        "WAITING_EXTERNAL",
        "TERMINAL_SUCCESS",
        "TERMINAL_HALTED",
    ]
    assert [action.value for action in CanonicalReplayActionType] == [
        "CREATE_CANONICAL_INCIDENT",
        "BOOTSTRAP_PRE_DISCHARGE",
        "START_DEMO_AGENT_RUN",
        "ADVANCE_AGENT",
        "PUBLISH_DISCHARGE_ACTIVE",
        "SIMULATE_CARRIER_RESPONSE",
        "APPROVE_REQUEST",
        "APPROVE_COUNTER",
        "PERSIST_SAFETY_REVIEW",
        "SELECT_TRADEOFF_OPTION",
        "NONE",
    ]


def test_stage_view_is_frozen_with_bounded_ordinal() -> None:
    view = CanonicalReplayStageView(
        stage=CanonicalReplayStage.REQUEST_APPROVAL_REQUIRED,
        ordinal=8,
        progress_label="Stage 8 of 16",
        status=CanonicalReplayStatus.WAITING_HUMAN,
        explanation="Operator approval is required before the agent may send.",
        next_allowed_action=CanonicalReplayActionType.APPROVE_REQUEST,
        guided_can_execute=True,
        auto_replay_may_execute=True,
        requires_human_authority=True,
        deviation_reason=None,
    )
    try:
        view.status = CanonicalReplayStatus.PENDING_ACTION  # type: ignore[misc]
    except Exception:
        pass
    else:
        raise AssertionError("stage view must be frozen")
    assert view.ordinal == 8
    assert view.progress_label == "Stage 8 of 16"


def test_stage_view_ordinal_bounds() -> None:
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        CanonicalReplayStageView(
            stage=CanonicalReplayStage.SAFETY_BLOCKED,
            ordinal=0,
            progress_label="Stage 0 of 16",
            status=CanonicalReplayStatus.TERMINAL_SUCCESS,
            explanation="out of bounds",
            next_allowed_action=CanonicalReplayActionType.NONE,
            guided_can_execute=False,
            auto_replay_may_execute=False,
            requires_human_authority=False,
        )
    with pytest.raises(ValidationError):
        CanonicalReplayStageView(
            stage=CanonicalReplayStage.SAFETY_BLOCKED,
            ordinal=17,
            progress_label="Stage 17 of 16",
            status=CanonicalReplayStatus.TERMINAL_SUCCESS,
            explanation="out of bounds",
            next_allowed_action=CanonicalReplayActionType.NONE,
            guided_can_execute=False,
            auto_replay_may_execute=False,
            requires_human_authority=False,
        )
