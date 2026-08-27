"""End-to-end acceptance coverage for the Phase 8 evidence package."""

from __future__ import annotations

from collections import Counter
import os
from pathlib import Path
import subprocess
import sys

import pytest

from backend.app.domain.evidence import (
    ClaimStatus,
    EvidenceInvariantFailure,
    Phase8EvidenceReport,
    normalized_evidence_payload,
)
from backend.app.evaluation.evidence import Phase8EvidenceService, main


REPO_ROOT = Path(__file__).resolve().parents[2]
LIVE_CLAIM_IDS = {
    "live_model_token_usage",
    "live_model_cost",
    "live_model_latency",
}
EXPECTED_VERIFIED_CLAIM_IDS = {
    "agent_approval_identities",
    "agent_no_unavailable_tool_execution",
    "agent_step_count",
    "agent_successful_tool_order",
    "agent_terminal_state",
    "agent_wait_kinds",
    "agent_zero_model_credentials",
    "audit_material_action_coverage",
    "audit_provenance_map_complete",
    "authority_carrier_silence_is_absence",
    "authority_counter_approval_required",
    "authority_counter_fingerprint_bound",
    "authority_no_agent_approval",
    "authority_no_carrier_schedule_mutation",
    "authority_no_forbidden_tools",
    "authority_request_approval_required",
    "authority_request_fingerprint_bound",
    "authority_timeout_recomputes",
    "deterministic_local_runtime",
    "deterministic_tool_call_count",
    "dynamic_committed_allocations_immutable",
    "dynamic_evidence_precedes_carrier_mutation",
    "dynamic_expected_preserved_change",
    "dynamic_phase2_worlds_reconstructed",
    "dynamic_phase3_incompatible_plan_blocked",
    "dynamic_preserved_total_change",
    "dynamic_reconsideration_r0_r1",
    "human_tradeoff_agent_cannot_select",
    "human_tradeoff_auto_replay_halts",
    "human_tradeoff_boundary",
    "human_tradeoff_committed_slots_immutable",
    "human_tradeoff_fingerprint_bound",
    "safety_automation_blocked",
    "safety_canonical_contradiction",
    "safety_checker_failure_fails_closed",
    "safety_checker_scope_limited",
    "safety_pending_review_blocks_bypass",
    "safety_policy_owns_disposition",
    "safety_terminal_escalation",
    "scarcity_expected_preserved_delta",
    "scarcity_expedite_slot_cap",
    "scarcity_holdout_world_count",
    "scarcity_reproducibility_key",
    "scarcity_scenario_aware_beats_p50",
    "scarcity_zero_capacity_violations",
    "scarcity_zero_unsafe_allocations",
}


def _provenance_keys(report: Phase8EvidenceReport) -> Counter[tuple[object, ...]]:
    return Counter(
        (
            claim.claim_id,
            reference.record_type,
            reference.stable_key,
            reference.source,
            reference.record_id,
        )
        for claim in report.claims
        if claim.status is not ClaimStatus.DEFERRED
        for reference in claim.evidence_refs
    )


def _reported_provenance_keys(
    report: Phase8EvidenceReport,
) -> Counter[tuple[object, ...]]:
    return Counter(
        (
            entry.claim_id,
            entry.record_type,
            entry.stable_key,
            entry.source,
            entry.record_id,
        )
        for entry in report.provenance
    )


def test_two_unchanged_runs_have_equal_deterministic_evidence() -> None:
    first = Phase8EvidenceService(REPO_ROOT).run(runtime_repetitions=2)
    second = Phase8EvidenceService(REPO_ROOT).run(runtime_repetitions=2)

    assert first.deterministic_fingerprint == second.deterministic_fingerprint
    assert normalized_evidence_payload(first.body()) == normalized_evidence_payload(
        second.body()
    )
    assert first.runtime.run_durations_ms != ()
    assert second.runtime.run_durations_ms != ()


def test_claim_statuses_values_tool_order_and_provenance_are_exact() -> None:
    report = Phase8EvidenceService(REPO_ROOT).run(runtime_repetitions=1)
    claims = {claim.claim_id: claim for claim in report.claims}
    terminal = claims["full_18_preserved_5_rolled_1_escalated"]
    terminal_value = terminal.observed_value

    assert set(claims) == (
        EXPECTED_VERIFIED_CLAIM_IDS
        | LIVE_CLAIM_IDS
        | {"full_18_preserved_5_rolled_1_escalated"}
    )
    assert {claims[claim_id].status for claim_id in EXPECTED_VERIFIED_CLAIM_IDS} == {
        ClaimStatus.VERIFIED
    }
    assert {claims[claim_id].status for claim_id in LIVE_CLAIM_IDS} == {
        ClaimStatus.DEFERRED
    }
    assert {claims[claim_id].observed_value for claim_id in LIVE_CLAIM_IDS} == {
        "DEFERRED_TO_PHASE_9"
    }
    assert isinstance(terminal_value, dict)
    complete_terminal_classification = (
        terminal_value["complete_terminal_classification_count"]
        == terminal_value["required_container_count"]
        == 24
    )
    assert terminal.status is (
        ClaimStatus.VERIFIED
        if complete_terminal_classification
        else ClaimStatus.NOT_ESTABLISHED
    )
    assert claims["scarcity_reproducibility_key"].observed_value == (
        "d0dc76fb9239f4f77320f4b0a0fd5572d0b9a86a80da0448892d5336f205fe21"
    )
    assert claims["agent_step_count"].observed_value == 6
    assert claims["deterministic_tool_call_count"].observed_value == 5
    assert claims["agent_successful_tool_order"].observed_value == [
        "pause_agent_run",
        "request_expedite_feasibility",
        "prepare_rta_request",
        "send_authorised_rta_request",
        "request_cargo_safety_review",
    ]
    assert _reported_provenance_keys(report) == _provenance_keys(report)


def test_invariant_failure_returns_one_without_overwrite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    json_path = tmp_path / "report.json"
    markdown_path = tmp_path / "summary.md"
    json_path.write_text("sentinel-json", encoding="utf-8")
    markdown_path.write_text("sentinel-markdown", encoding="utf-8")
    monkeypatch.setattr(
        Phase8EvidenceService,
        "run",
        lambda self, runtime_repetitions: (_ for _ in ()).throw(
            EvidenceInvariantFailure("agent_step_count", "observed 7")
        ),
    )

    code = main(
        [
            "--output-json",
            str(json_path),
            "--output-markdown",
            str(markdown_path),
            "--runtime-repetitions",
            "1",
        ]
    )

    assert code == 1
    assert json_path.read_text(encoding="utf-8") == "sentinel-json"
    assert markdown_path.read_text(encoding="utf-8") == "sentinel-markdown"


def test_invalid_runtime_repetitions_return_two(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as error:
        main(
            [
                "--output-json",
                str(tmp_path / "report.json"),
                "--output-markdown",
                str(tmp_path / "summary.md"),
                "--runtime-repetitions",
                "0",
            ]
        )

    assert error.value.code == 2


def test_normal_cli_run_returns_zero(tmp_path: Path) -> None:
    json_path = tmp_path / "report.json"
    markdown_path = tmp_path / "summary.md"

    assert main(
        [
            "--output-json",
            str(json_path),
            "--output-markdown",
            str(markdown_path),
            "--runtime-repetitions",
            "1",
        ]
    ) == 0
    assert Phase8EvidenceReport.model_validate_json(
        json_path.read_text(encoding="utf-8")
    )
    assert markdown_path.exists()


def test_evidence_module_smoke_runs_without_credentials(tmp_path: Path) -> None:
    json_path = tmp_path / "report.json"
    markdown_path = tmp_path / "summary.md"
    environment = {
        key: value for key, value in os.environ.items() if key != "OPENAI_API_KEY"
    }

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "backend.app.evaluation.evidence",
            "--output-json",
            str(json_path),
            "--output-markdown",
            str(markdown_path),
            "--runtime-repetitions",
            "1",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
        env=environment,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert Phase8EvidenceReport.model_validate_json(
        json_path.read_text(encoding="utf-8")
    )
    assert markdown_path.exists()


def test_committed_artifact_matches_a_fresh_semantic_regeneration() -> None:
    generated = Phase8EvidenceService(REPO_ROOT).run(runtime_repetitions=1)
    committed = Phase8EvidenceReport.model_validate_json(
        (REPO_ROOT / "docs/evaluations/phase8-evidence-report.json").read_text(
            encoding="utf-8"
        )
    )

    assert generated.deterministic_fingerprint == committed.deterministic_fingerprint
    assert normalized_evidence_payload(generated.body()) == normalized_evidence_payload(
        committed.body()
    )
