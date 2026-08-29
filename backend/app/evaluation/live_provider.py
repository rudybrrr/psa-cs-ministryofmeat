from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
from collections.abc import Callable, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any, ContextManager
from uuid import UUID

from pydantic import ValidationError
from sqlmodel import Session

from backend.app.domain.agent_runtime import (
    AgentEscalationReason,
    AgentModelTurn,
    AgentRunState,
    AgentToolDefinition,
    AgentTurnContext,
    AgentWaitKind,
)
from backend.app.domain.cargo_safety import SemanticCheckResult, SemanticSafetyCheckInput
from backend.app.domain.live_evidence import (
    CostEstimate,
    CostStatus,
    LiveProviderReport,
    LiveProviderRunConfig,
    LiveStage,
    PricingSnapshot,
    ProviderCallObservation,
)

if TYPE_CHECKING:
    from backend.app.evaluation.live_openai_client import (
        InstrumentedOpenAIClient,
        ProviderCallBudget,
    )


EVALUATION_BASE_SHA = "2ff0e58d98e586f7904c726a4bb485a8419e2954"
FIXTURE_IDS = (
    "synthetic-canonical-scarcity-v1",
    "synthetic-canonical-dynamic-yard",
    "synthetic-canonical-cargo-note",
)


class _StageFailure(RuntimeError):
    def __init__(self, stage: LiveStage, *, call_cap: bool = False) -> None:
        self.stage = stage
        self.call_cap = call_cap
        super().__init__(stage.value)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _checkout_revision(repo_root: Path) -> str:
    completed = subprocess.run(
        ("git", "rev-parse", "HEAD"),
        cwd=repo_root,
        capture_output=True,
        check=False,
        text=True,
    )
    revision = completed.stdout.strip()
    if (
        completed.returncode != 0
        or len(revision) != 40
        or any(character not in "0123456789abcdef" for character in revision)
    ):
        raise ValueError("live evidence requires a resolvable checkout revision")
    return revision


def _validate_pricing_snapshot_provenance(
    path: Path, snapshot: PricingSnapshot, repo_root: Path
) -> None:
    relative = path.relative_to(repo_root).as_posix()
    tracked = subprocess.run(
        ("git", "ls-files", "--error-unmatch", "--", relative),
        cwd=repo_root,
        capture_output=True,
        check=False,
    )
    if tracked.returncode != 0:
        raise ValueError("pricing snapshot must be Git-tracked")
    committed = subprocess.run(
        ("git", "show", f"HEAD:{relative}"),
        cwd=repo_root,
        capture_output=True,
        check=False,
    )
    if committed.returncode != 0 or committed.stdout != path.read_bytes():
        raise ValueError("pricing snapshot content must be committed")
    snapshot_path = subprocess.run(
        ("git", "cat-file", "-e", f"{snapshot.snapshot_commit_sha}:{relative}"),
        cwd=repo_root,
        capture_output=True,
        check=False,
    )
    associated = subprocess.run(
        ("git", "merge-base", "--is-ancestor", snapshot.snapshot_commit_sha, "HEAD"),
        cwd=repo_root,
        capture_output=True,
        check=False,
    )
    if (
        snapshot_path.returncode != 0 or associated.returncode != 0
    ):
        raise ValueError(
            "pricing snapshot commit must contain the snapshot path in checkout history"
        )


def _report_metrics(
    observations: Sequence[ProviderCallObservation], complete_workflow_count: int
) -> dict[str, object]:
    successful = tuple(item for item in observations if item.success)
    latencies = sorted(
        item.latency_ms for item in successful if item.latency_ms is not None
    )
    return {
        "attempted_provider_call_count": len(observations),
        "successful_provider_call_count": len(successful),
        "failed_provider_call_count": len(observations) - len(successful),
        "complete_workflow_count": complete_workflow_count,
        "p50_successful_latency_ms": (
            float(latencies[math.ceil(0.50 * len(latencies)) - 1])
            if latencies
            else None
        ),
        "p95_successful_latency_ms": (
            float(latencies[math.ceil(0.95 * len(latencies)) - 1])
            if latencies
            else None
        ),
        "latency_provenance": "CLIENT_OBSERVED_REQUEST_LATENCY",
    }


def estimate_cost(
    snapshot: PricingSnapshot | None,
    observations: Sequence[ProviderCallObservation],
) -> CostEstimate:
    if snapshot is None:
        return CostEstimate(
            status=CostStatus.NOT_ESTABLISHED,
            reason="NO_PRICING_SNAPSHOT",
        )
    if snapshot.provider != "openai":
        return CostEstimate(
            status=CostStatus.NOT_ESTABLISHED,
            reason="INVALID_PRICING_SNAPSHOT",
        )
    if not observations or any(
        observation.configured_model != snapshot.model
        or observation.returned_model not in {None, snapshot.model}
        for observation in observations
    ):
        return CostEstimate(
            status=CostStatus.NOT_ESTABLISHED,
            reason="MODEL_MISMATCH",
        )
    if any(
        observation.input_tokens is None or observation.output_tokens is None
        for observation in observations
    ):
        return CostEstimate(
            status=CostStatus.NOT_ESTABLISHED,
            reason="INCOMPLETE_TOKEN_USAGE",
        )
    amount = sum(
        (
            Decimal(observation.input_tokens) * snapshot.input_price_per_unit
            + Decimal(observation.output_tokens) * snapshot.output_price_per_unit
            for observation in observations
        ),
        Decimal(0),
    )
    return CostEstimate(
        status=CostStatus.ESTIMATED_USD,
        amount_usd=amount,
        pricing_snapshot_commit_sha=snapshot.snapshot_commit_sha,
    )


class LiveProviderEvaluator:
    def __init__(
        self,
        config: LiveProviderRunConfig,
        client_factory: Callable[[ProviderCallBudget], InstrumentedOpenAIClient],
        session_factory: Callable[[], ContextManager[Session]],
    ) -> None:
        self._config = config
        self._client_factory = client_factory
        self._session_factory = session_factory
        self._stages: dict[int, LiveStage] = {}
        self._selected_tools: dict[int, str] = {}
        self._budget: Any | None = None

    def run(self) -> LiveProviderReport:
        source_revision = _checkout_revision(_repo_root())
        snapshot = self._load_snapshot()
        from backend.app.evaluation.live_openai_client import (
            LiveProviderCallCapExceeded,
            ProviderCallBudget,
        )

        class EvaluatorProviderCallBudget(ProviderCallBudget):
            def __init__(self, max_calls: int) -> None:
                super().__init__(max_calls)
                self.cap_rejections = 0

            def admit(self, method: Any) -> int:
                try:
                    return super().admit(method)
                except LiveProviderCallCapExceeded:
                    self.cap_rejections += 1
                    raise

        budget = EvaluatorProviderCallBudget(self._config.max_calls)
        self._budget = budget
        client = self._client_factory(budget)
        stopped_stage: LiveStage | None = None
        durable: dict[str, Any] = {}
        complete_workflow_count = 0
        try:
            checker, model = self._adapters(client)
            self._invoke(
                client,
                LiveStage.CONNECTIVITY_SMOKE,
                lambda: (
                    checker.check(
                        SemanticSafetyCheckInput(
                            structured_dangerous_goods=False,
                            structured_un_number=None,
                            structured_commodity="general cargo",
                            note_text="No contradictory cargo declaration is present.",
                        )
                    ),
                    None,
                ),
            )
            self._register_storage_models()
            with self._session_factory() as session:
                durable.update(self._persisted_semantic_smoke(client, checker, session))
                self._single_tool_smoke(client, model, LiveStage.TOOL_SELECTION_SMOKE)
                durable.update(self._complete_workflow(client, session))
                complete_workflow_count = 1
            observations = self._observations(client)
            if (
                len(observations) == 9
                and all(item.success for item in observations)
                and len(observations) < self._config.max_calls
            ):
                self._single_tool_smoke(client, model, LiveStage.OPTIONAL_SAMPLE)
            elif len(observations) >= self._config.max_calls:
                stopped_stage = LiveStage.STOPPED_AT_CALL_CAP
        except _StageFailure as failure:
            stopped_stage = (
                LiveStage.STOPPED_AT_CALL_CAP if failure.call_cap else failure.stage
            )
        except Exception:
            stopped_stage = LiveStage.COMPLETE_WORKFLOW
        observations = self._observations(client)
        return LiveProviderReport(
            label="NON-DETERMINISTIC LIVE PROVIDER EVIDENCE",
            schema_version="phase9-live-evidence-v1",
            suite_id="phase9-live-provider-evidence",
            generated_at=datetime.now(UTC),
            source_revision=source_revision,
            evaluation_base_sha=EVALUATION_BASE_SHA,
            environment=(
                "deployed"
                if os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("VERCEL_ENV")
                else "local"
            ),
            config=self._config,
            fixture_ids=FIXTURE_IDS,
            observations=observations,
            **_report_metrics(observations, complete_workflow_count),
            stopped_stage=stopped_stage,
            cost=estimate_cost(snapshot, observations),
            **durable,
        )

    @staticmethod
    def _adapters(client: InstrumentedOpenAIClient) -> tuple[Any, Any]:
        from backend.app.services.agent_model import OpenAIAgentModel
        from backend.app.services.semantic_safety import OpenAISemanticSafetyChecker

        # The non-secret sentinel only satisfies the adapters' configuration guard;
        # the injected client owns all provider I/O.
        return (
            OpenAISemanticSafetyChecker(api_key="injected-client", client=client),
            OpenAIAgentModel(api_key="injected-client", client=client),
        )

    @staticmethod
    def _register_storage_models() -> None:
        # Session factories may create tables on entry, so all table models must
        # be registered before entering the injected context manager.
        from backend.app.storage import (  # noqa: F401
            agent_runtime,
            cargo_safety,
            carrier_recovery,
            dynamic_yard,
            repositories,
        )

    def _load_snapshot(self) -> PricingSnapshot | None:
        path = self._config.pricing_snapshot_path
        if path is None:
            return None
        repo_root = _repo_root()
        resolved = (path if path.is_absolute() else repo_root / path).resolve()
        if resolved == repo_root or repo_root not in resolved.parents:
            raise ValueError("pricing snapshot must be repository-contained")
        try:
            snapshot = PricingSnapshot.model_validate_json(
                resolved.read_text(encoding="utf-8")
            )
        except (OSError, ValidationError, ValueError) as error:
            raise ValueError("invalid PHASE9_LIVE_PRICING_SNAPSHOT") from error
        if snapshot.provider != "openai":
            raise ValueError("pricing snapshot provider must be openai")
        _validate_pricing_snapshot_provenance(resolved, snapshot, repo_root)
        return snapshot

    def _invoke(
        self,
        client: InstrumentedOpenAIClient,
        stage: LiveStage,
        operation: Callable[[], tuple[Any, str | None]],
    ) -> Any:
        before = len(client.observations)
        rejected_before = getattr(self._budget, "cap_rejections", 0)
        try:
            result, selected_tool = operation()
        except Exception as error:
            self._tag_new_observations(client, before, stage, None)
            raise _StageFailure(
                stage,
                call_cap=(
                    getattr(self._budget, "cap_rejections", 0) > rejected_before
                    or (
                        len(client.observations) == before
                        and before >= self._config.max_calls
                    )
                ),
            ) from error
        self._tag_new_observations(client, before, stage, selected_tool)
        if getattr(self._budget, "cap_rejections", 0) > rejected_before:
            raise _StageFailure(stage, call_cap=True)
        new = tuple(client.observations[before:])
        if not new and len(client.observations) >= self._config.max_calls:
            raise _StageFailure(stage, call_cap=True)
        if not new or any(not item.success for item in new):
            raise _StageFailure(stage)
        return result

    def _tag_new_observations(
        self,
        client: InstrumentedOpenAIClient,
        before: int,
        stage: LiveStage,
        selected_tool: str | None,
    ) -> None:
        successful_creates = [
            item
            for item in client.observations[before:]
            if item.success and item.method == "responses.create"
        ]
        for observation in client.observations[before:]:
            self._stages[observation.call_number] = stage
        if selected_tool is not None and successful_creates:
            self._selected_tools[successful_creates[-1].call_number] = selected_tool

    def _observations(
        self, client: InstrumentedOpenAIClient
    ) -> tuple[ProviderCallObservation, ...]:
        return tuple(
            observation.model_copy(
                update={
                    "stage": self._stages.get(observation.call_number, observation.stage),
                    "selected_tool": self._selected_tools.get(observation.call_number),
                }
            )
            for observation in client.observations
        )

    def _single_tool_smoke(
        self, client: InstrumentedOpenAIClient, model: Any, stage: LiveStage
    ) -> None:
        tool = AgentToolDefinition(
            name="pause_agent_run",
            description="Pause at a durable wait boundary.",
            parameters={
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        )

        def select() -> tuple[AgentModelTurn, str]:
            turn = model.decide(
                AgentTurnContext(
                    run_id=UUID(int=1),
                    incident_id=UUID(int=2),
                    step_count=0,
                    remaining_steps=1,
                    summary={"available_tools": [tool.name]},
                ),
                (tool,),
            )
            if not isinstance(turn, AgentModelTurn) or turn.tool_call is None:
                raise AssertionError("single-tool smoke returned no valid action")
            if turn.tool_call.name != tool.name or turn.tool_call.arguments:
                raise AssertionError("single-tool smoke selected an unexpected action")
            return turn, turn.tool_call.name

        self._invoke(client, stage, select)

    def _persisted_semantic_smoke(
        self, client: Any, checker: Any, session: Session
    ) -> dict[str, str]:
        from backend.app.domain.cargo_safety import CargoSafetyReviewState
        from backend.app.orchestration.cargo_safety import CargoSafetyWorkflow
        from backend.app.orchestration.scarce_capacity import (
            build_scarce_capacity_workflow,
        )
        from backend.app.services.canonical_replay import (
            CANONICAL_SAFETY_CONTAINER_ID,
            CANONICAL_SAFETY_NOTE_SOURCE,
            CANONICAL_SAFETY_NOTE_TEXT,
        )

        incident = build_scarce_capacity_workflow(session).run().incident
        workflow = CargoSafetyWorkflow.for_session(session, checker=checker)
        review = workflow.create_review(
            incident.id,
            CANONICAL_SAFETY_CONTAINER_ID,
            CANONICAL_SAFETY_NOTE_TEXT,
            CANONICAL_SAFETY_NOTE_SOURCE,
        )

        def evaluate() -> tuple[Any, None]:
            outcome = workflow.evaluate(review.id)
            if (
                outcome.review.state is not CargoSafetyReviewState.COMPLETED
                or outcome.assessment.result
                is not SemanticCheckResult.CONTRADICTION_FOUND
                or not outcome.policy_result.automation_blocked
            ):
                raise AssertionError("canonical semantic smoke did not fail closed")
            return outcome, None

        outcome = self._invoke(client, LiveStage.SEMANTIC_SAFETY_SMOKE, evaluate)
        return {
            "semantic_smoke_review_id": str(outcome.review.id),
            "semantic_smoke_assessment_id": str(outcome.assessment.id),
            "semantic_smoke_policy_result_id": str(outcome.policy_result.id),
        }

    def _complete_workflow(
        self, client: InstrumentedOpenAIClient, session: Session
    ) -> dict[str, Any]:
        from backend.app.domain.carrier_recovery import (
            AuthorizationSubjectKind,
            CounterApprovalCommand,
            RequestApprovalCommand,
            SimulateCarrierResponseCommand,
        )
        from backend.app.domain.enums import ApprovalStatus
        from backend.app.orchestration.agent_runtime import (
            AgentRuntimeCoordinator,
            CanonicalAgentRuntimeConfiguration,
        )
        from backend.app.orchestration.cargo_safety import CargoSafetyWorkflow
        from backend.app.orchestration.carrier_recovery import (
            build_carrier_recovery_workflow,
        )
        from backend.app.orchestration.dynamic_yard import DynamicYardWorkflow
        from backend.app.orchestration.scarce_capacity import (
            build_scarce_capacity_workflow,
        )
        from backend.app.services.agent_model import OpenAIAgentModel
        from backend.app.services.canonical_replay import (
            CANONICAL_COUNTER_EFFECTIVE_AT,
            CANONICAL_SAFETY_CONTAINER_ID,
            CANONICAL_SAFETY_NOTE_SOURCE,
            CANONICAL_SAFETY_NOTE_TEXT,
            GUIDED_OPERATOR_ID,
        )
        from backend.app.services.dynamic_yard import CanonicalDynamicYardHarness
        from backend.app.services.semantic_safety import OpenAISemanticSafetyChecker
        from backend.app.storage.agent_runtime import AgentRuntimeConflict
        from backend.app.storage.agent_runtime import AgentRuntimeRepository

        phase2 = build_scarce_capacity_workflow(session).run()
        incident_id = phase2.incident.id
        yard = DynamicYardWorkflow.for_session(session)
        harness = CanonicalDynamicYardHarness()
        yard.initialize(incident_id, harness.bootstrap_snapshot(incident_id))
        configuration = CanonicalAgentRuntimeConfiguration.load()
        runtime = AgentRuntimeCoordinator(
            session=session,
            model=OpenAIAgentModel(api_key="injected-client", client=client),
            clock=configuration.clock("before_deadline"),
            configuration=configuration,
            cargo_safety_checker=OpenAISemanticSafetyChecker(
                api_key="injected-client", client=client
            ),
        )
        run = runtime.create_run(incident_id)
        runs = AgentRuntimeRepository(session)

        paused = self._runtime_advance(client, runtime, runs, run.id)
        if paused.wait_kind is not AgentWaitKind.NEW_OPERATIONAL_EVIDENCE:
            raise _StageFailure(LiveStage.COMPLETE_WORKFLOW)
        yard.ingest(harness.discharge_active_snapshot(incident_id))
        reconsidered = self._runtime_advance(client, runtime, runs, run.id)
        if reconsidered.state is not AgentRunState.RUNNING:
            raise _StageFailure(LiveStage.COMPLETE_WORKFLOW)
        yard_history = yard.history(incident_id)
        revisions = yard_history.revisions
        assessment = yard_history.assessments[-1]
        if (
            len(revisions) != 2
            or revisions[1].parent_revision_id != revisions[0].id
            or (
                assessment.preserved_connection_total_before,
                assessment.preserved_connection_total_after,
                assessment.expected_preserved_connections_before,
                assessment.expected_preserved_connections_after,
            )
            != (601, 602, 12.02, 12.04)
        ):
            raise _StageFailure(LiveStage.COMPLETE_WORKFLOW)

        prepared = self._runtime_advance(client, runtime, runs, run.id)
        if (
            prepared.wait_kind is not AgentWaitKind.REQUEST_APPROVAL
            or prepared.wait_subject_id is None
        ):
            raise _StageFailure(LiveStage.COMPLETE_WORKFLOW)
        case_id = UUID(prepared.wait_subject_id)
        carrier = build_carrier_recovery_workflow(session)
        request_binding = next(
            item
            for item in carrier.history(case_id).bindings
            if item.subject_kind is AuthorizationSubjectKind.OUTBOUND_REQUEST
        )
        carrier.record_request_approval(
            RequestApprovalCommand(
                case_id=case_id,
                proposal_decision_id=request_binding.proposal_decision_id,
                request_id=request_binding.subject_id,
                expected_payload_fingerprint=request_binding.payload_fingerprint,
                operator_id=GUIDED_OPERATOR_ID,
                status=ApprovalStatus.APPROVED,
            )
        )
        sent = self._runtime_advance(client, runtime, runs, run.id)
        if sent.wait_kind is not AgentWaitKind.CARRIER_RESPONSE_OR_TIMEOUT:
            raise _StageFailure(LiveStage.COMPLETE_WORKFLOW)
        carrier.simulate_response(
            SimulateCarrierResponseCommand(
                case_id=case_id, effective_at=CANONICAL_COUNTER_EFFECTIVE_AT
            )
        )
        try:
            runtime.advance(run.id)
        except AgentRuntimeConflict:
            pass
        else:
            raise _StageFailure(LiveStage.COMPLETE_WORKFLOW)
        if runtime.get_run(run.id).wait_kind is not AgentWaitKind.COUNTER_APPROVAL:
            raise _StageFailure(LiveStage.COMPLETE_WORKFLOW)
        counter_binding = next(
            item
            for item in carrier.history(case_id).bindings
            if item.subject_kind is AuthorizationSubjectKind.COUNTER_PROPOSAL
        )
        carrier.record_counter_approval(
            CounterApprovalCommand(
                case_id=case_id,
                proposal_decision_id=counter_binding.proposal_decision_id,
                carrier_response_id=counter_binding.subject_id,
                expected_payload_fingerprint=counter_binding.payload_fingerprint,
                operator_id=GUIDED_OPERATOR_ID,
                status=ApprovalStatus.APPROVED,
            )
        )
        safety = CargoSafetyWorkflow.for_session(
            session,
            checker=OpenAISemanticSafetyChecker(
                api_key="injected-client", client=client
            ),
        )
        review = safety.create_review(
            incident_id,
            CANONICAL_SAFETY_CONTAINER_ID,
            CANONICAL_SAFETY_NOTE_TEXT,
            CANONICAL_SAFETY_NOTE_SOURCE,
        )
        terminal = self._runtime_advance(client, runtime, runs, run.id)
        history = safety.history(review.id)
        if (
            terminal.state is not AgentRunState.ESCALATED
            or terminal.escalation_reason
            is not AgentEscalationReason.SAFETY_REVIEW_REQUIRED
            or terminal.step_count != 6
            or history.policy_result is None
            or not history.policy_result.automation_blocked
            or history.assessment is None
        ):
            raise _StageFailure(LiveStage.COMPLETE_WORKFLOW)
        agent_history = runs.history(run.id)
        return {
            "agent_run_id": str(run.id),
            "agent_step_ids": tuple(str(step.id) for step in agent_history.steps),
            "safety_assessment_id": str(history.assessment.id),
            "final_outcome_id": str(history.policy_result.id),
        }

    def _runtime_advance(
        self, client: Any, runtime: Any, runs: Any, run_id: UUID
    ) -> Any:
        before_steps = runs.history(run_id).tool_invocations

        def advance() -> tuple[Any, str | None]:
            result = runtime.advance(run_id)
            after_steps = runs.history(run_id).tool_invocations
            created = after_steps[len(before_steps) :]
            selected = created[-1].tool_name if created else None
            return result, selected

        return self._invoke(client, LiveStage.COMPLETE_WORKFLOW, advance)


def render_live_evidence(report: LiveProviderReport) -> str:
    lines = [
        "# NON-DETERMINISTIC LIVE PROVIDER EVIDENCE",
        "",
        f"Suite: `{report.suite_id}`",
        f"Generated: `{report.generated_at.isoformat()}`",
        f"Source revision: `{report.source_revision}`",
        f"Provider calls attempted: `{report.attempted_provider_call_count}/{report.config.max_calls}`",
        f"Provider calls successful: `{report.successful_provider_call_count}`",
        f"Provider calls failed: `{report.failed_provider_call_count}`",
        f"Complete workflows: `{report.complete_workflow_count}/{report.config.max_workflows}`",
        f"Successful latency p50 ms: `{report.p50_successful_latency_ms}`",
        f"Successful latency p95 ms: `{report.p95_successful_latency_ms}`",
        f"Latency provenance: `{report.latency_provenance}`",
        f"Stopped stage: `{report.stopped_stage.value if report.stopped_stage else 'NONE'}`",
        f"Cost: `{report.cost.status.value}`",
        f"Cost amount USD: `{report.cost.amount_usd if report.cost.amount_usd is not None else 'NOT_ESTABLISHED'}`",
        f"Cost reason: `{report.cost.reason or 'NONE'}`",
        f"Pricing snapshot commit: `{report.cost.pricing_snapshot_commit_sha or 'NONE'}`",
        "",
        "## Durable evidence IDs",
        "",
        f"Semantic smoke review: `{report.semantic_smoke_review_id or 'NONE'}`",
        f"Semantic smoke assessment: `{report.semantic_smoke_assessment_id or 'NONE'}`",
        f"Semantic smoke policy result: `{report.semantic_smoke_policy_result_id or 'NONE'}`",
        f"Agent run: `{report.agent_run_id or 'NONE'}`",
        f"Agent steps: `{', '.join(report.agent_step_ids) if report.agent_step_ids else 'NONE'}`",
        f"Hero safety assessment: `{report.safety_assessment_id or 'NONE'}`",
        f"Final outcome: `{report.final_outcome_id or 'NONE'}`",
        "",
        "| Call | Stage | Method | Success | Model | Input tokens | Output tokens | Latency ms | Tool |",
        "|---:|---|---|:---:|---|---:|---:|---:|---|",
    ]
    lines.extend(
        "| {call} | {stage} | {method} | {success} | {model} | {input_tokens} | {output_tokens} | {latency} | {tool} |".format(
            call=item.call_number,
            stage=item.stage.value,
            method=item.method,
            success="yes" if item.success else "no",
            model=item.returned_model or item.configured_model,
            input_tokens=item.input_tokens if item.input_tokens is not None else "—",
            output_tokens=item.output_tokens if item.output_tokens is not None else "—",
            latency=item.latency_ms if item.latency_ms is not None else "—",
            tool=item.selected_tool or "—",
        )
        for item in report.observations
    )
    return "\n".join(lines) + "\n"


def write_artifacts(
    report: LiveProviderReport, output_json: Path, output_markdown: Path
) -> None:
    json_path, markdown_path = _live_output_paths(output_json, output_markdown)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(render_live_evidence(report), encoding="utf-8")


def _live_output_path(path: Path) -> Path:
    root = Path(__file__).resolve().parents[3]
    live_root = (root / "docs" / "evaluations" / "live").resolve()
    resolved = (path if path.is_absolute() else root / path).resolve()
    if resolved == live_root or live_root not in resolved.parents:
        raise ValueError("live-provider artifacts must be under docs/evaluations/live/")
    return resolved


def _live_output_paths(output_json: Path, output_markdown: Path) -> tuple[Path, Path]:
    json_path = _live_output_path(output_json)
    markdown_path = _live_output_path(output_markdown)
    if json_path == markdown_path:
        raise ValueError("JSON and Markdown artifact paths must be distinct")
    return json_path, markdown_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate bounded live-provider evidence.")
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-markdown", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = LiveProviderRunConfig.from_environ(os.environ)
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("live tests require OPENAI_API_KEY")
    _live_output_paths(args.output_json, args.output_markdown)

    def client_factory(budget: Any) -> Any:
        # Import and SDK construction stay behind environment, path, and pricing
        # validation; LiveProviderEvaluator.run() invokes this only afterward.
        from backend.app.evaluation.live_openai_client import InstrumentedOpenAIClient

        return InstrumentedOpenAIClient.from_api_key(api_key, budget)

    @contextmanager
    def session_scope() -> Any:
        from backend.app.storage.database import create_db_and_tables, engine

        create_db_and_tables(engine)
        with Session(engine) as session:
            yield session

    evaluator = LiveProviderEvaluator(
        config,
        client_factory,
        session_scope,
    )
    report = evaluator.run()
    write_artifacts(report, args.output_json, args.output_markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
