from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.app.domain.evidence import (
    ClaimStatus,
    EvidenceInvariantFailure,
    Phase8EvidenceReport,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_CLAIM_IDS = {
    "scarcity_holdout_world_count",
    "scarcity_scenario_aware_beats_p50",
    "scarcity_expected_preserved_delta",
    "scarcity_expedite_slot_cap",
    "scarcity_zero_capacity_violations",
    "scarcity_zero_unsafe_allocations",
    "scarcity_reproducibility_key",
    "dynamic_reconsideration_r0_r1",
    "dynamic_preserved_total_change",
    "dynamic_expected_preserved_change",
    "dynamic_committed_allocations_immutable",
    "dynamic_phase2_worlds_reconstructed",
    "dynamic_phase3_incompatible_plan_blocked",
    "dynamic_evidence_precedes_carrier_mutation",
    "authority_request_approval_required",
    "authority_request_fingerprint_bound",
    "authority_counter_approval_required",
    "authority_counter_fingerprint_bound",
    "authority_carrier_silence_is_absence",
    "authority_timeout_recomputes",
    "authority_no_carrier_schedule_mutation",
    "authority_no_forbidden_tools",
    "authority_no_agent_approval",
    "human_tradeoff_boundary",
    "human_tradeoff_agent_cannot_select",
    "human_tradeoff_fingerprint_bound",
    "human_tradeoff_committed_slots_immutable",
    "human_tradeoff_auto_replay_halts",
    "safety_canonical_contradiction",
    "safety_automation_blocked",
    "safety_terminal_escalation",
    "safety_checker_scope_limited",
    "safety_policy_owns_disposition",
    "safety_checker_failure_fails_closed",
    "safety_pending_review_blocks_bypass",
    "agent_terminal_state",
    "agent_step_count",
    "agent_successful_tool_order",
    "agent_wait_kinds",
    "agent_approval_identities",
    "agent_no_unavailable_tool_execution",
    "agent_zero_model_credentials",
    "audit_material_action_coverage",
    "audit_provenance_map_complete",
    "deterministic_tool_call_count",
    "deterministic_local_runtime",
    "live_model_token_usage",
    "live_model_cost",
    "live_model_latency",
    "full_18_preserved_5_rolled_1_escalated",
}


@pytest.fixture(scope="module")
def report() -> Phase8EvidenceReport:
    from backend.app.evaluation.evidence import Phase8EvidenceService

    return Phase8EvidenceService(REPO_ROOT).run(runtime_repetitions=1)


def test_service_builds_complete_sorted_registry(report: Phase8EvidenceReport) -> None:
    claim_ids = [claim.claim_id for claim in report.claims]

    assert set(claim_ids) == EXPECTED_CLAIM_IDS
    assert claim_ids == sorted(EXPECTED_CLAIM_IDS)
    assert claim_ids.count("deterministic_tool_call_count") == 1

    claims = {claim.claim_id: claim for claim in report.claims}
    assert claims["safety_checker_scope_limited"].status is ClaimStatus.VERIFIED
    assert (
        claims["safety_checker_failure_fails_closed"].observed_value
        == {"assessment_result": "CHECK_FAILED", "automation_blocked": True}
    )
    assert claims["agent_zero_model_credentials"].observed_value == {
        "openai_api_key_present": False,
        "provider_client_construction_count": 0,
        "canonical_model_identity": "canonical-replay-agent-v1",
        "canonical_checker_identity": "canonical-replay-deterministic",
    }
    assert claims["agent_zero_model_credentials"].evidence_refs[0].source == (
        "backend.app.evaluation.evidence._provider_isolation_probe"
    )


def test_status_boundaries_are_honest_and_provenance_is_complete(
    report: Phase8EvidenceReport,
) -> None:
    claims = {claim.claim_id: claim for claim in report.claims}
    deferred = {
        "live_model_token_usage",
        "live_model_cost",
        "live_model_latency",
    }

    assert {
        claim_id
        for claim_id, claim in claims.items()
        if claim.status is ClaimStatus.DEFERRED
    } == deferred
    assert all(
        claims[claim_id].observed_value == "DEFERRED_TO_PHASE_9"
        and claims[claim_id].evidence_refs == ()
        for claim_id in deferred
    )
    assert {
        claim_id
        for claim_id, claim in claims.items()
        if claim.status is ClaimStatus.NOT_ESTABLISHED
    } == {"full_18_preserved_5_rolled_1_escalated"}
    assert {
        claim_id
        for claim_id, claim in claims.items()
        if claim.status is ClaimStatus.VERIFIED
    } == EXPECTED_CLAIM_IDS - deferred - {
        "full_18_preserved_5_rolled_1_escalated"
    }

    terminal = claims["full_18_preserved_5_rolled_1_escalated"]
    assert terminal.status is ClaimStatus.NOT_ESTABLISHED
    assert terminal.observed_value == {
        "r1_allocation_count": 8,
        "carrier_affected_container_ids": ["SYN-CNT-017"],
        "safety_escalation_container_id": "SYN-CNT-010",
        "complete_terminal_classification_count": 2,
        "required_container_count": 24,
    }
    assert len(report.provenance) == sum(
        len(claim.evidence_refs)
        for claim in report.claims
        if claim.status is not ClaimStatus.DEFERRED
    )
    assert all(claim.evidence_refs for claim in report.claims if claim.status is ClaimStatus.VERIFIED)


def test_markdown_is_an_ordered_projection_of_validated_report(
    report: Phase8EvidenceReport,
) -> None:
    from backend.app.evaluation.evidence_markdown import render_evidence_summary

    rendered = render_evidence_summary(report)
    headings = (
        "## Metadata and fingerprint",
        "## Verified headline",
        "## Frozen scarcity",
        "## Dynamic reconsideration",
        "## Authority and tradeoff",
        "## Safety and agent",
        "## Audit and provenance",
        "## Runtime and resource label",
        "## NOT_ESTABLISHED",
        "## DEFERRED",
        "## Regeneration command",
    )

    assert rendered.startswith("# Phase 8 Deterministic Evidence Summary\n")
    assert [rendered.index(heading) for heading in headings] == sorted(
        rendered.index(heading) for heading in headings
    )
    assert report.deterministic_fingerprint in rendered
    assert "0.4952" in rendered
    assert "+4.1220%" in rendered
    assert "DEFERRED_TO_PHASE_9" in rendered
    assert "NOT_ESTABLISHED" in rendered
    assert "LOCAL_MACHINE_DEPENDENT" in rendered
    assert "```mermaid" not in rendered
    assert "![" not in rendered


def test_markdown_revalidates_constructed_report_before_projection(
    report: Phase8EvidenceReport,
) -> None:
    from backend.app.evaluation.evidence_markdown import render_evidence_summary

    malformed = report.model_copy(
        update={"claims": (report.claims[0], report.claims[0])}
    )

    with pytest.raises(ValidationError, match="claim IDs must be unique"):
        render_evidence_summary(malformed)


def test_artifact_writer_serializes_schema_valid_json_and_markdown(
    report: Phase8EvidenceReport, tmp_path: Path
) -> None:
    from backend.app.evaluation.evidence import write_evidence_artifacts

    json_path = tmp_path / "evidence.json"
    markdown_path = tmp_path / "evidence.md"
    write_evidence_artifacts(report, json_path, markdown_path)

    reloaded = Phase8EvidenceReport.model_validate_json(
        json_path.read_text(encoding="utf-8")
    )
    assert reloaded == report
    assert markdown_path.read_text(encoding="utf-8").startswith(
        "# Phase 8 Deterministic Evidence Summary\n"
    )
    assert not json_path.with_name(json_path.name + ".tmp").exists()
    assert not markdown_path.with_name(markdown_path.name + ".tmp").exists()


@pytest.mark.parametrize(
    ("json_name", "markdown_name", "protected_name"),
    (
        ("evidence", "evidence.tmp", "evidence.tmp"),
        ("evidence.tmp", "evidence", "evidence.tmp"),
    ),
)
def test_cli_rejects_cross_colliding_destination_and_temp_paths_before_writing(
    report: Phase8EvidenceReport,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    json_name: str,
    markdown_name: str,
    protected_name: str,
) -> None:
    from backend.app.evaluation import evidence

    json_path = tmp_path / json_name
    markdown_path = tmp_path / markdown_name
    protected_path = tmp_path / protected_name
    untouched_path = (
        json_path if protected_path != json_path else markdown_path
    )
    protected_path.write_text("previous-artifact", encoding="utf-8")
    monkeypatch.setattr(
        evidence.Phase8EvidenceService,
        "run",
        lambda self, runtime_repetitions=20: report,
    )

    exit_code = evidence.main(
        [
            "--output-json",
            str(json_path),
            "--output-markdown",
            str(markdown_path),
            "--runtime-repetitions",
            "1",
        ]
    )

    assert exit_code == 2
    assert protected_path.read_text(encoding="utf-8") == "previous-artifact"
    assert not untouched_path.exists()


def test_artifact_writer_does_not_overwrite_pair_when_second_temp_write_fails(
    report: Phase8EvidenceReport,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.app.evaluation.evidence import write_evidence_artifacts

    json_path = tmp_path / "evidence.json"
    markdown_path = tmp_path / "evidence.md"
    json_path.write_text("previous-json", encoding="utf-8")
    markdown_path.write_text("previous-markdown", encoding="utf-8")
    markdown_tmp = markdown_path.with_name(markdown_path.name + ".tmp")
    original_write_text = Path.write_text

    def fail_markdown_tmp(path: Path, *args, **kwargs):
        if path == markdown_tmp:
            raise OSError("simulated markdown write failure")
        return original_write_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", fail_markdown_tmp)

    with pytest.raises(OSError, match="simulated markdown"):
        write_evidence_artifacts(report, json_path, markdown_path)

    assert json_path.read_text(encoding="utf-8") == "previous-json"
    assert markdown_path.read_text(encoding="utf-8") == "previous-markdown"
    assert not json_path.with_name(json_path.name + ".tmp").exists()
    assert not markdown_tmp.exists()


def test_artifact_writer_rolls_back_first_output_when_second_replace_fails(
    report: Phase8EvidenceReport,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.app.evaluation.evidence import write_evidence_artifacts

    json_path = tmp_path / "evidence.json"
    markdown_path = tmp_path / "evidence.md"
    json_path.write_text("previous-json", encoding="utf-8")
    markdown_path.write_text("previous-markdown", encoding="utf-8")
    markdown_tmp = markdown_path.with_name(markdown_path.name + ".tmp")
    original_replace = Path.replace

    def fail_markdown_replace(path: Path, target: Path):
        if path == markdown_tmp:
            raise OSError("simulated markdown replace failure")
        return original_replace(path, target)

    monkeypatch.setattr(Path, "replace", fail_markdown_replace)

    with pytest.raises(OSError, match="simulated markdown replace"):
        write_evidence_artifacts(report, json_path, markdown_path)

    assert json_path.read_text(encoding="utf-8") == "previous-json"
    assert markdown_path.read_text(encoding="utf-8") == "previous-markdown"
    assert not json_path.with_name(json_path.name + ".tmp").exists()
    assert not markdown_tmp.exists()


def test_main_maps_success_invariant_and_malformed_errors_without_overwrite(
    report: Phase8EvidenceReport,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.app.evaluation import evidence

    json_path = tmp_path / "cli.json"
    markdown_path = tmp_path / "cli.md"
    args = [
        "--output-json",
        str(json_path),
        "--output-markdown",
        str(markdown_path),
        "--runtime-repetitions",
        "1",
    ]
    monkeypatch.setattr(evidence.Phase8EvidenceService, "run", lambda self, runtime_repetitions=20: report)

    assert evidence.main(args) == 0
    assert Phase8EvidenceReport.model_validate_json(json_path.read_text(encoding="utf-8"))

    previous_json = json_path.read_text(encoding="utf-8")
    previous_markdown = markdown_path.read_text(encoding="utf-8")

    def invariant_failure(self, runtime_repetitions=20):
        raise EvidenceInvariantFailure("agent_step_count", "observed 7")

    monkeypatch.setattr(evidence.Phase8EvidenceService, "run", invariant_failure)
    assert evidence.main(args) == 1
    assert json_path.read_text(encoding="utf-8") == previous_json
    assert markdown_path.read_text(encoding="utf-8") == previous_markdown

    def malformed_failure(self, runtime_repetitions=20):
        raise json.JSONDecodeError("malformed", "{", 1)

    monkeypatch.setattr(evidence.Phase8EvidenceService, "run", malformed_failure)
    assert evidence.main(args) == 2
    assert json_path.read_text(encoding="utf-8") == previous_json
    assert markdown_path.read_text(encoding="utf-8") == previous_markdown


@pytest.mark.parametrize(
    "structural_error",
    (KeyError("missing aggregate field"), TypeError("wrong aggregate shape")),
)
def test_main_maps_structural_aggregate_errors_to_exit_2_without_overwrite(
    report: Phase8EvidenceReport,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    structural_error: Exception,
) -> None:
    from backend.app.evaluation import evidence

    json_path = tmp_path / "cli.json"
    markdown_path = tmp_path / "cli.md"
    json_path.write_text("previous-json", encoding="utf-8")
    markdown_path.write_text("previous-markdown", encoding="utf-8")

    def malformed_aggregate(self, runtime_repetitions=20):
        raise structural_error

    monkeypatch.setattr(
        evidence.Phase8EvidenceService,
        "run",
        malformed_aggregate,
    )

    exit_code = evidence.main(
        [
            "--output-json",
            str(json_path),
            "--output-markdown",
            str(markdown_path),
            "--runtime-repetitions",
            "1",
        ]
    )

    assert exit_code == 2
    assert json_path.read_text(encoding="utf-8") == "previous-json"
    assert markdown_path.read_text(encoding="utf-8") == "previous-markdown"


def test_cli_rejects_runtime_repetition_below_one(tmp_path: Path) -> None:
    from backend.app.evaluation.evidence import main

    with pytest.raises(SystemExit) as exc:
        main(
            [
                "--output-json",
                str(tmp_path / "evidence.json"),
                "--output-markdown",
                str(tmp_path / "evidence.md"),
                "--runtime-repetitions",
                "0",
            ]
        )

    assert exc.value.code == 2


def test_committed_artifacts_are_validated_and_consistent() -> None:
    from backend.app.evaluation.evidence_markdown import render_evidence_summary

    report = Phase8EvidenceReport.model_validate_json(
        (
            REPO_ROOT / "docs/evaluations/phase8-evidence-report.json"
        ).read_text(encoding="utf-8")
    )
    markdown = (
        REPO_ROOT / "docs/evaluations/phase8-evidence-summary.md"
    ).read_text(encoding="utf-8")

    assert markdown == render_evidence_summary(report)
    assert report.deterministic_fingerprint in markdown
