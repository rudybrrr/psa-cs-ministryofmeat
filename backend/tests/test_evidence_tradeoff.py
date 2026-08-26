from backend.app.domain.evidence import ClaimStatus


def test_tradeoff_collector_proves_backend_human_authority_boundary(session) -> None:
    from backend.app.evaluation.evidence_authority import collect_tradeoff_claims

    claims = {claim.claim_id: claim for claim in collect_tradeoff_claims(session)}

    assert set(claims) == {"human_tradeoff_backend_authority_boundary"}
    claim = claims["human_tradeoff_backend_authority_boundary"]
    assert claim.status is ClaimStatus.VERIFIED
    assert claim.observed_value == {
        "review_state_before_selection": "OPEN",
        "model_calls_before_selection": 0,
        "selection_tool_in_runtime_registry": False,
        "stale_selection_exception": "DynamicYardConflict",
        "stale_selection_mutated": False,
        "committed_slots_retained": ["SYN-CNT-002", "SYN-CNT-004"],
        "projector_stage": "TRADEOFF_DECISION_REQUIRED",
        "projector_action": "SELECT_TRADEOFF_OPTION",
        "auto_replay_may_execute": False,
        "requires_human_authority": True,
    }
    assert "frontend" not in claim.statement.lower()
    assert "AutoReplayController" not in claim.caveat
