from backend.app.domain.evidence import ClaimStatus


def test_authority_collector_proves_exact_carrier_boundaries_and_runtime_scope(session) -> None:
    from backend.app.evaluation.evidence_authority import collect_authority_claims

    claims = {claim.claim_id: claim for claim in collect_authority_claims(session)}

    assert set(claims) == {
        "carrier_request_authority_boundary",
        "carrier_counter_authority_boundary",
        "carrier_silence_timeout_and_runtime_scope",
    }
    assert {claim.status for claim in claims.values()} == {ClaimStatus.VERIFIED}
    assert claims["carrier_request_authority_boundary"].observed_value == {
        "unapproved_send_exception": "CarrierRecoveryConflict",
        "unapproved_send_history_unchanged": True,
        "wrong_request_fingerprint_exception": "CarrierRecoveryConflict",
        "approval_count_after_wrong_fingerprint": 0,
    }
    assert claims["carrier_counter_authority_boundary"].observed_value == {
        "counter_response_count": 1,
        "effective_timing_count_before_approval": 0,
        "wrong_counter_fingerprint_exception": "CarrierRecoveryConflict",
        "effective_timing_count_after_wrong_fingerprint": 0,
    }
    silence = claims["carrier_silence_timeout_and_runtime_scope"].observed_value
    assert set(silence) == {
        "silent_carrier_response_count",
        "timeout_terminal_state",
        "fixture_connection_unchanged",
        "forbidden_runtime_tools",
    }
    assert silence["silent_carrier_response_count"] == 0
    assert silence["fixture_connection_unchanged"] is True
    assert silence["forbidden_runtime_tools"] == []
    assert silence["timeout_terminal_state"] in {"COMPLETED", "ESCALATED"}
