"""Composite Phase 8 deterministic evidence service and command-line entrypoint."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import TypeVar
from unittest.mock import patch

from pydantic import ValidationError
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

from backend.app.domain.cargo_safety import (
    SemanticCheckFailureKind,
    SemanticCheckResult,
    SemanticSafetyCheckInput,
)
from backend.app.domain.evidence import (
    ClaimReproducibility,
    ClaimStatus,
    EvidenceClaim,
    EvidenceInvariantFailure,
    EvidenceReference,
    EvidenceReportBody,
    Phase8EvidenceReport,
    assert_verified,
    evidence_fingerprint,
    normalized_evidence_payload,
)
from backend.app.evaluation.evidence_audit import (
    build_provenance_map,
    collect_audit_claims,
)
from backend.app.evaluation.evidence_authority import (
    collect_authority_claims,
    collect_tradeoff_claims,
)
from backend.app.evaluation.evidence_dynamic_yard import (
    DynamicYardEvidenceResult,
    collect_dynamic_yard_claims,
)
from backend.app.evaluation.evidence_runtime import (
    local_runtime_claim,
    measure_local_runtime,
)
from backend.app.evaluation.evidence_safety_agent import (
    CanonicalEvidenceRun,
    claims_from_canonical_run,
    run_canonical_evidence_scenario,
)
from backend.app.evaluation.evidence_scarcity import collect_scarcity_claims
from backend.app.orchestration.cargo_safety import CargoSafetyWorkflow
from backend.app.orchestration.scarce_capacity import build_scarce_capacity_workflow
from backend.app.services.canonical_replay import (
    CANONICAL_REPLAY_MODEL_NAME,
    CANONICAL_SAFETY_CONTAINER_ID,
    CANONICAL_SAFETY_NOTE_TEXT,
    CanonicalReplaySemanticChecker,
)
from backend.app.services.semantic_safety import FakeSemanticSafetyChecker


REPO_ROOT = Path(__file__).resolve().parents[3]
EVALUATION_BASE_SHA = "71716a0eee8413358dfc1e125a942945fc4be18c"
FIXTURE_ID = "SYN-CANONICAL-24-V1"
SEED_MANIFEST_ID = "SYN-CANONICAL-24-HOLDOUT-V1"
CHECKER_IDENTITY = "canonical-replay-deterministic"
CLI_VERSION = "phase8-evidence-v1"
REGENERATION_COMMAND = (
    "uv run --python 3.12 --extra dev python -m "
    "backend.app.evaluation.evidence "
    "--output-json docs/evaluations/phase8-evidence-report.json "
    "--output-markdown docs/evaluations/phase8-evidence-summary.md "
    "--runtime-repetitions 20"
)

_T = TypeVar("_T")


@contextmanager
def _isolated_session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            yield session
    finally:
        engine.dispose()


def _in_isolated_session(collector: Callable[[Session], _T]) -> _T:
    with _isolated_session() as session:
        return collector(session)


@contextmanager
def _provider_isolation_probe() -> Iterator[dict[str, object]]:
    """Remove credentials and fail before any provider client can be constructed."""

    previous = os.environ.pop("OPENAI_API_KEY", None)
    observation: dict[str, object] = {
        "openai_api_key_present": False,
        "provider_client_construction_count": 0,
        "canonical_model_identity": CANONICAL_REPLAY_MODEL_NAME,
        "canonical_checker_identity": CHECKER_IDENTITY,
    }

    def blocked_provider(*args, **kwargs):
        del args, kwargs
        observation["provider_client_construction_count"] = int(
            observation["provider_client_construction_count"]
        ) + 1
        raise EvidenceInvariantFailure(
            "agent_zero_model_credentials",
            "a provider client construction path was invoked",
        )

    try:
        with (
            patch("backend.app.services.agent_model.OpenAI", blocked_provider),
            patch("backend.app.services.semantic_safety.OpenAI", blocked_provider),
        ):
            yield observation
    finally:
        if previous is not None:
            os.environ["OPENAI_API_KEY"] = previous


def _copy_claim(
    source: EvidenceClaim,
    *,
    claim_id: str,
    statement: str,
    observed_value: object,
) -> EvidenceClaim:
    return EvidenceClaim(
        claim_id=claim_id,
        statement=statement,
        status=source.status,
        observed_value=observed_value,
        evidence_refs=source.evidence_refs,
        caveat=source.caveat,
        reproducibility=source.reproducibility,
    )


def _expanded_authority_claims(claims: tuple[EvidenceClaim, ...]) -> tuple[EvidenceClaim, ...]:
    source = {claim.claim_id: claim for claim in claims}
    request = source["carrier_request_authority_boundary"]
    counter = source["carrier_counter_authority_boundary"]
    silence = source["carrier_silence_timeout_and_runtime_scope"]
    request_value = request.observed_value
    counter_value = counter.observed_value
    silence_value = silence.observed_value
    if not all(isinstance(value, dict) for value in (request_value, counter_value, silence_value)):
        raise EvidenceInvariantFailure(
            "authority_request_approval_required",
            "authority probe returned a malformed observation",
        )

    return (
        _copy_claim(
            request,
            claim_id="authority_request_approval_required",
            statement="Carrier dispatch requires an approved request binding.",
            observed_value={
                "unapproved_send_exception": request_value["unapproved_send_exception"],
                "history_unchanged": request_value["unapproved_send_history_unchanged"],
            },
        ),
        _copy_claim(
            request,
            claim_id="authority_request_fingerprint_bound",
            statement="Carrier request approval is bound to the exact persisted fingerprint.",
            observed_value={
                "wrong_fingerprint_exception": request_value[
                    "wrong_request_fingerprint_exception"
                ],
                "persisted_approval_count": request_value[
                    "approval_count_after_wrong_fingerprint"
                ],
            },
        ),
        _copy_claim(
            counter,
            claim_id="authority_counter_approval_required",
            statement="Counter timing cannot take effect before operator approval.",
            observed_value={
                "carrier_response_count": counter_value["counter_response_count"],
                "effective_timing_count_before_approval": counter_value[
                    "effective_timing_count_before_approval"
                ],
            },
        ),
        _copy_claim(
            counter,
            claim_id="authority_counter_fingerprint_bound",
            statement="Counter approval is bound to the exact persisted fingerprint.",
            observed_value={
                "wrong_fingerprint_exception": counter_value[
                    "wrong_counter_fingerprint_exception"
                ],
                "effective_timing_count": counter_value[
                    "effective_timing_count_after_wrong_fingerprint"
                ],
            },
        ),
        _copy_claim(
            silence,
            claim_id="authority_carrier_silence_is_absence",
            statement="The deterministic silent carrier plan persists no response.",
            observed_value={
                "carrier_response_count": silence_value[
                    "silent_carrier_response_count"
                ]
            },
        ),
        _copy_claim(
            silence,
            claim_id="authority_timeout_recomputes",
            statement="A due silent-carrier timeout reaches a terminal recovery state.",
            observed_value={
                "terminal_state": silence_value["timeout_terminal_state"]
            },
        ),
        _copy_claim(
            silence,
            claim_id="authority_no_carrier_schedule_mutation",
            statement="Carrier recovery leaves the canonical connection fixture unchanged.",
            observed_value={
                "fixture_connection_unchanged": silence_value[
                    "fixture_connection_unchanged"
                ]
            },
        ),
        _copy_claim(
            silence,
            claim_id="authority_no_forbidden_tools",
            statement="The runtime registry exposes no forbidden operational authority tools.",
            observed_value={
                "forbidden_runtime_tools": silence_value["forbidden_runtime_tools"]
            },
        ),
        _copy_claim(
            silence,
            claim_id="authority_no_agent_approval",
            statement="The runtime registry exposes no agent approval-authority tools.",
            observed_value={
                "agent_approval_authority_tools": silence_value[
                    "agent_approval_authority_tools"
                ]
            },
        ),
    )


def _expanded_tradeoff_claims(claims: tuple[EvidenceClaim, ...]) -> tuple[EvidenceClaim, ...]:
    if len(claims) != 1 or not isinstance(claims[0].observed_value, dict):
        raise EvidenceInvariantFailure(
            "human_tradeoff_boundary", "tradeoff probe returned a malformed observation"
        )
    source = claims[0]
    value = source.observed_value
    return (
        _copy_claim(
            source,
            claim_id="human_tradeoff_boundary",
            statement="An open human tradeoff blocks agent continuation until selection.",
            observed_value={
                "review_state": value["review_state_before_selection"],
                "model_calls_to_wait": value["model_calls_to_reach_human_wait"],
                "model_calls_while_waiting": value[
                    "model_calls_while_waiting_before_selection"
                ],
                "requires_human_authority": value["requires_human_authority"],
            },
        ),
        _copy_claim(
            source,
            claim_id="human_tradeoff_agent_cannot_select",
            statement="The agent registry exposes no tradeoff-selection or approval authority.",
            observed_value={
                "selection_tool_exposed": value[
                    "selection_tool_in_runtime_registry"
                ],
                "agent_approval_authority_tools": value[
                    "agent_approval_authority_tools"
                ],
            },
        ),
        _copy_claim(
            source,
            claim_id="human_tradeoff_fingerprint_bound",
            statement="A stale tradeoff fingerprint is rejected without durable mutation.",
            observed_value={
                "exception": value["stale_selection_exception"],
                "persisted_state_unchanged": value[
                    "stale_selection_persisted_state_unchanged"
                ],
            },
        ),
        _copy_claim(
            source,
            claim_id="human_tradeoff_committed_slots_immutable",
            statement="Exact human selection retains the committed allocation slots.",
            observed_value={
                "committed_slots": value["committed_slots_retained"]
            },
        ),
        _copy_claim(
            source,
            claim_id="human_tradeoff_auto_replay_halts",
            statement="The backend projector halts Auto Replay at the human boundary.",
            observed_value={
                "stage": value["projector_stage"],
                "next_action": value["projector_action"],
                "auto_replay_may_execute": value["auto_replay_may_execute"],
                "requires_human_authority": value["requires_human_authority"],
            },
        ),
    )


def _checker_scope_claim() -> EvidenceClaim:
    output = CanonicalReplaySemanticChecker().check(
        SemanticSafetyCheckInput(
            structured_dangerous_goods=False,
            structured_un_number=None,
            structured_commodity="General cargo",
            note_text=CANONICAL_SAFETY_NOTE_TEXT,
        )
    )
    output_fields = list(output.model_dump(mode="json"))
    assert_verified(
        output_fields == ["result", "explanation", "evidence_excerpt"]
        and not hasattr(output, "disposition")
        and not hasattr(output, "dangerous_goods")
        and not hasattr(output, "un_number"),
        "safety_checker_scope_limited",
        "canonical checker output exceeded the semantic-evidence contract",
    )
    return EvidenceClaim(
        claim_id="safety_checker_scope_limited",
        statement="The canonical checker emits semantic evidence, not safety disposition or DG classification.",
        status=ClaimStatus.VERIFIED,
        observed_value={
            "output_fields": output_fields,
            "disposition_field_present": False,
            "dangerous_goods_field_present": False,
            "un_number_field_present": False,
        },
        evidence_refs=(
            EvidenceReference(
                record_type="DeterministicSafetyProbe",
                stable_key="phase8-probe:safety-checker-scope",
                source="CanonicalReplaySemanticChecker.check",
            ),
        ),
        caveat="Deterministic canonical checker output contract only.",
        reproducibility=ClaimReproducibility(
            deterministic=True,
            included_in_fingerprint=True,
            fixture_ids=(FIXTURE_ID,),
        ),
    )


def _checker_failure_claim() -> EvidenceClaim:
    with _isolated_session() as session:
        phase2 = build_scarce_capacity_workflow(session).run()
        checker = FakeSemanticSafetyChecker(
            result=SemanticCheckResult.NO_CONTRADICTION_FOUND,
            failure_kind=SemanticCheckFailureKind.PROVIDER_ERROR,
        )
        workflow = CargoSafetyWorkflow.for_session(session, checker=checker)
        review = workflow.create_review(
            phase2.incident.id,
            CANONICAL_SAFETY_CONTAINER_ID,
            "Cargo note could not be checked.",
            "phase8-failure-probe",
        )
        workflow.evaluate(review.id)
        history = workflow.history(review.id)
        assessment = history.assessment
        policy = history.policy_result
        assert_verified(
            assessment is not None
            and assessment.result is SemanticCheckResult.CHECK_FAILED
            and policy is not None
            and policy.automation_blocked is True,
            "safety_checker_failure_fails_closed",
            "checker failure did not persist CHECK_FAILED with automation blocked",
        )
        reference = EvidenceReference(
            record_type="CargoSafetyHistory",
            stable_key="phase8-probe:safety-checker-failure",
            source="CargoSafetyRepository.history",
            record_id=str(review.id),
        )

    return EvidenceClaim(
        claim_id="safety_checker_failure_fails_closed",
        statement="A deterministic checker failure persists CHECK_FAILED and blocks automation.",
        status=ClaimStatus.VERIFIED,
        observed_value={
            "assessment_result": SemanticCheckResult.CHECK_FAILED.value,
            "automation_blocked": True,
        },
        evidence_refs=(reference,),
        caveat="Isolated deterministic failure probe; no provider client or network call.",
        reproducibility=ClaimReproducibility(
            deterministic=True,
            included_in_fingerprint=True,
            fixture_ids=(FIXTURE_ID,),
        ),
    )


def _credential_isolation_claim(observation: dict[str, object]) -> EvidenceClaim:
    assert_verified(
        observation["openai_api_key_present"] is False
        and observation["provider_client_construction_count"] == 0,
        "agent_zero_model_credentials",
        "canonical evaluation was not isolated from provider credentials/clients",
    )
    return EvidenceClaim(
        claim_id="agent_zero_model_credentials",
        statement="The canonical evaluation runs with no model credential or provider client construction.",
        status=ClaimStatus.VERIFIED,
        observed_value=observation,
        evidence_refs=(
            EvidenceReference(
                record_type="ProviderIsolationProbe",
                stable_key="phase8-probe:provider-isolation",
                source="Phase8EvidenceService._provider_isolation_probe",
            ),
        ),
        caveat="Credential-free deterministic canonical replay only; live use is deferred.",
        reproducibility=ClaimReproducibility(
            deterministic=True,
            included_in_fingerprint=True,
            fixture_ids=(FIXTURE_ID,),
        ),
    )


def _not_established_terminal_claim(
    dynamic: DynamicYardEvidenceResult,
    canonical: CanonicalEvidenceRun,
) -> EvidenceClaim:
    r1 = dynamic.history.revisions[-1]
    affected = sorted(canonical.carrier_history.case.affected_container_ids)
    safety_container = canonical.safety_history.review.container_id
    classified = sorted(set(affected) | {safety_container})
    assert_verified(
        len(r1.allocated_container_ids) == 8
        and affected == ["SYN-CNT-017"]
        and safety_container == "SYN-CNT-010"
        and len(classified) < 24,
        "full_18_preserved_5_rolled_1_escalated",
        "partial terminal-classification evidence drifted",
    )
    return EvidenceClaim(
        claim_id="full_18_preserved_5_rolled_1_escalated",
        statement="All 24 containers are classified into 18 preserved, 5 rolled, and 1 escalated.",
        status=ClaimStatus.NOT_ESTABLISHED,
        observed_value={
            "r1_allocation_count": len(r1.allocated_container_ids),
            "carrier_affected_container_ids": affected,
            "safety_escalation_container_id": safety_container,
            "complete_terminal_classification_count": len(classified),
            "required_container_count": 24,
        },
        evidence_refs=(
            EvidenceReference(
                record_type="AllocationTradeoffHistory",
                stable_key=f"dynamic-yard:{FIXTURE_ID}",
                source="DynamicYardRepository.history",
                record_id=str(dynamic.incident_id),
            ),
            EvidenceReference(
                record_type="CarrierRecoveryHistory",
                stable_key="canonical-run:carrier-history",
                source="CarrierRecoveryRepository.history",
                record_id=str(canonical.carrier_history.case.id),
            ),
            EvidenceReference(
                record_type="CargoSafetyHistory",
                stable_key="canonical-run:safety-history",
                source="CargoSafetyRepository.history",
                record_id=str(canonical.safety_history.review.id),
            ),
        ),
        caveat=(
            "NOT_ESTABLISHED: no complete disjoint durable terminal ledger classifies "
            "all 24 containers."
        ),
        reproducibility=ClaimReproducibility(
            deterministic=True,
            included_in_fingerprint=True,
            fixture_ids=(FIXTURE_ID,),
        ),
    )


def _deferred_claim(claim_id: str, statement: str) -> EvidenceClaim:
    return EvidenceClaim(
        claim_id=claim_id,
        statement=statement,
        status=ClaimStatus.DEFERRED,
        observed_value="DEFERRED_TO_PHASE_9",
        evidence_refs=(),
        caveat="DEFERRED_TO_PHASE_9",
        reproducibility=ClaimReproducibility(
            deterministic=True,
            included_in_fingerprint=True,
        ),
    )


LIVE_DEFERRED_CLAIMS = (
    _deferred_claim("live_model_token_usage", "Live model token usage is measured."),
    _deferred_claim("live_model_cost", "Live model API cost is measured."),
    _deferred_claim("live_model_latency", "Live model latency is measured."),
)


def _runtime_claim(metrics) -> EvidenceClaim:
    source = local_runtime_claim(metrics)
    return _copy_claim(
        source,
        claim_id="deterministic_local_runtime",
        statement="Canonical deterministic runs were measured on the local machine.",
        observed_value=source.observed_value,
    )


def _provenance_completeness_claim(claims: Sequence[EvidenceClaim]) -> EvidenceClaim:
    claim_ids = [claim.claim_id for claim in claims]
    assert_verified(
        len(claim_ids) == len(set(claim_ids)),
        "audit_provenance_map_complete",
        "claim registry contains duplicate IDs before provenance construction",
    )
    reference_count = sum(
        len(claim.evidence_refs)
        for claim in claims
        if claim.status is not ClaimStatus.DEFERRED
    ) + 1
    return EvidenceClaim(
        claim_id="audit_provenance_map_complete",
        statement="Every non-deferred evidence reference has exactly one provenance row.",
        status=ClaimStatus.VERIFIED,
        observed_value={
            "claim_count": len(claims) + 1,
            "reference_count": reference_count,
            "provenance_row_count": reference_count,
        },
        evidence_refs=(
            EvidenceReference(
                record_type="EvidenceRegistryProbe",
                stable_key="phase8-report:provenance-completeness",
                source="build_provenance_map and EvidenceReportBody validation",
            ),
        ),
        caveat="Validated composite Phase 8 report registry only.",
        reproducibility=ClaimReproducibility(
            deterministic=True,
            included_in_fingerprint=True,
            fixture_ids=(FIXTURE_ID,),
        ),
    )


class Phase8EvidenceService:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = Path(repo_root).resolve()

    def run(self, runtime_repetitions: int = 20) -> Phase8EvidenceReport:
        if runtime_repetitions < 1:
            raise ValueError("runtime repetitions must be at least one")

        with _provider_isolation_probe() as provider_observation:
            scarcity_claims = collect_scarcity_claims(self.repo_root)
            dynamic = _in_isolated_session(collect_dynamic_yard_claims)
            authority_claims = _expanded_authority_claims(
                _in_isolated_session(collect_authority_claims)
            )
            tradeoff_claims = _expanded_tradeoff_claims(
                _in_isolated_session(collect_tradeoff_claims)
            )
            canonical = _in_isolated_session(run_canonical_evidence_scenario)
            canonical_claims = claims_from_canonical_run(canonical)
            audit_claims = collect_audit_claims(canonical)
            runtime = measure_local_runtime(
                lambda: _in_isolated_session(run_canonical_evidence_scenario),
                runtime_repetitions,
            )
            explicit_probe_claims = (
                _checker_scope_claim(),
                _checker_failure_claim(),
                _credential_isolation_claim(provider_observation),
            )

        claims: list[EvidenceClaim] = [
            *scarcity_claims,
            *dynamic.claims,
            *authority_claims,
            *tradeoff_claims,
            *canonical_claims,
            *audit_claims,
            *explicit_probe_claims,
            _runtime_claim(runtime),
            _not_established_terminal_claim(dynamic, canonical),
            *LIVE_DEFERRED_CLAIMS,
        ]
        claims.append(_provenance_completeness_claim(claims))
        sorted_claims = tuple(sorted(claims, key=lambda claim: claim.claim_id))
        provenance = build_provenance_map(sorted_claims)
        body = EvidenceReportBody(
            evaluation_base_sha=EVALUATION_BASE_SHA,
            source_revision=_source_revision(self.repo_root),
            generated_at=datetime.now(UTC),
            command=REGENERATION_COMMAND,
            cli_version=CLI_VERSION,
            fixture_ids=(FIXTURE_ID,),
            seed_manifest_id=SEED_MANIFEST_ID,
            canonical_model_identity=CANONICAL_REPLAY_MODEL_NAME,
            canonical_checker_identity=CHECKER_IDENTITY,
            claims=sorted_claims,
            provenance=provenance,
            runtime=runtime,
        )
        fingerprint = evidence_fingerprint(body)
        return Phase8EvidenceReport.model_validate(
            {
                **body.model_dump(mode="python"),
                "deterministic_fingerprint": fingerprint,
            }
        )


def _source_revision(repo_root: Path) -> str | None:
    try:
        completed = subprocess.run(
            ("git", "rev-parse", "HEAD"),
            cwd=repo_root,
            capture_output=True,
            check=False,
            text=True,
        )
    except OSError:
        return None
    revision = completed.stdout.strip()
    if completed.returncode == 0 and len(revision) == 40:
        return revision
    return None


def write_evidence_artifacts(
    report: Phase8EvidenceReport,
    json_path: Path,
    markdown_path: Path,
) -> None:
    from backend.app.evaluation.evidence_markdown import render_evidence_summary

    validated = Phase8EvidenceReport.model_validate(report.model_dump(mode="python"))
    json_text = validated.model_dump_json(indent=2) + "\n"
    markdown_text = render_evidence_summary(validated)
    json_path = Path(json_path)
    markdown_path = Path(markdown_path)
    if json_path == markdown_path:
        raise ValueError("JSON and Markdown output paths must be different")
    json_tmp = json_path.with_name(json_path.name + ".tmp")
    markdown_tmp = markdown_path.with_name(markdown_path.name + ".tmp")
    if json_tmp == markdown_tmp:
        raise ValueError("JSON and Markdown temporary paths must be different")

    json_previous = json_path.read_bytes() if json_path.exists() else None
    json_replaced = False
    try:
        json_tmp.write_text(json_text, encoding="utf-8")
        markdown_tmp.write_text(markdown_text, encoding="utf-8")
        json_tmp.replace(json_path)
        json_replaced = True
        markdown_tmp.replace(markdown_path)
    except Exception:
        if json_replaced:
            if json_previous is None:
                json_path.unlink(missing_ok=True)
            else:
                json_tmp.write_bytes(json_previous)
                json_tmp.replace(json_path)
        raise
    finally:
        json_tmp.unlink(missing_ok=True)
        markdown_tmp.unlink(missing_ok=True)


def _positive_integer(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate deterministic Phase 8 evidence.")
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-markdown", type=Path, required=True)
    parser.add_argument(
        "--runtime-repetitions",
        type=_positive_integer,
        default=20,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = Phase8EvidenceService(REPO_ROOT).run(
            runtime_repetitions=args.runtime_repetitions
        )
        write_evidence_artifacts(report, args.output_json, args.output_markdown)
    except EvidenceInvariantFailure as error:
        print(f"VERIFIED invariant failed: {error}", file=sys.stderr)
        return 1
    except (ValidationError, ValueError, OSError, json.JSONDecodeError) as error:
        print(f"Phase 8 evidence error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "Phase8EvidenceService",
    "evidence_fingerprint",
    "main",
    "normalized_evidence_payload",
    "write_evidence_artifacts",
]
