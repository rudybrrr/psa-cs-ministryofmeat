"""Deterministic canonical replay demo model and semantic checker (Phase 7).

Both classes are credential-free and make zero network calls. The demo model
implements the existing AgentModel protocol and selects only currently exposed
tools; the semantic checker implements the existing SemanticSafetyChecker
protocol and produces semantic evidence only — the frozen Phase 4 policy
remains the sole owner of PASS_THROUGH versus ESCALATE.
"""

from __future__ import annotations

import re
from typing import Sequence

from backend.app.domain.agent_runtime import (
    AgentModelTurn,
    AgentToolCall,
    AgentToolDefinition,
    AgentTurnContext,
    InvalidAgentModelTurn,
)
from backend.app.domain.cargo_safety import (
    SemanticCheckResult,
    SemanticSafetyCheckInput,
    SemanticSafetyCheckOutput,
)


CANONICAL_REPLAY_MODEL_NAME = "canonical-replay-agent-v1"
SYNTHETIC_DEMO_OPERATOR_ID = "synthetic-demo-operator"
GUIDED_OPERATOR_ID = "operator-console"
CANONICAL_JV2_CONNECTION_ID = "SYN-CONN-JV2"
CANONICAL_SAFETY_CONTAINER_ID = "SYN-CNT-010"
CANONICAL_SAFETY_NOTE_TEXT = (
    "Manifest declares general cargo; free-text handling note identifies "
    "corrosive material and requires safety review."
)
CANONICAL_SAFETY_NOTE_SOURCE = "synthetic-canonical-cargo-note"
CANONICAL_COUNTER_EFFECTIVE_AT = "2026-08-23T05:00:00Z"


_HAZARD_TOKEN_PATTERN = re.compile(
    r"\b(?:"
    r"un\s\d{4}"
    r"|dangerous\s+goods"
    r"|dg"
    r"|hazardous"
    r"|corrosive"
    r"|flammable"
    r"|explosive"
    r"|radioactive"
    r"|toxic"
    r"|lithium-ion\s+batteries"
    r")\b",
    re.IGNORECASE,
)

_SEQUENCE_VIOLATION = "CANONICAL_SEQUENCE_VIOLATION"


class CanonicalReplayAgentModel:
    model_name = CANONICAL_REPLAY_MODEL_NAME

    def decide(self, context: AgentTurnContext, available_tools: Sequence[AgentToolDefinition]) -> AgentModelTurn | InvalidAgentModelTurn:
        tools = {tool.name: tool for tool in available_tools}
        summary = context.summary
        forecast_stages = list((summary.get("dynamic_yard") or {}).get("forecast_stages") or [])

        if "request_expedite_feasibility" in tools:
            return self._turn("request_expedite_feasibility", {})

        if context.step_count == 0:
            if forecast_stages == ["PRE_DISCHARGE"] and "pause_agent_run" in tools:
                return self._turn("pause_agent_run", {})
            return InvalidAgentModelTurn(
                error_kind=_SEQUENCE_VIOLATION,
                detail="Canonical replay must pause on its first turn after PRE_DISCHARGE bootstrap evidence exists.",
            )

        if "prepare_rta_request" in tools:
            if not forecast_stages:
                return InvalidAgentModelTurn(
                    error_kind=_SEQUENCE_VIOLATION,
                    detail="Canonical replay requires bootstrapped dynamic-yard evidence before preparing an RTA request.",
                )
            options = list(
                ((tools["prepare_rta_request"].parameters.get("properties") or {}).get("connection_id") or {}).get("enum")
                or []
            )
            if len(options) != 1:
                return InvalidAgentModelTurn(
                    error_kind="CANONICAL_AMBIGUOUS_CONNECTION",
                    detail=f"Expected exactly one compatible connection option, found {len(options)}.",
                )
            return self._turn("prepare_rta_request", {"connection_id": options[0]})

        if "send_authorised_rta_request" in tools:
            candidates = [
                case["id"]
                for case in (summary.get("carrier_cases") or [])
                if case.get("state") == "AWAITING_REQUEST_APPROVAL" and case.get("id") is not None
            ]
            if len(candidates) != 1:
                return InvalidAgentModelTurn(
                    error_kind="CANONICAL_AMBIGUOUS_CASE",
                    detail=f"Expected exactly one carrier case awaiting request approval, found {len(candidates)}.",
                )
            return self._turn("send_authorised_rta_request", {"case_id": candidates[0]})

        if "request_cargo_safety_review" in tools:
            pending = list(summary.get("cargo_safety_pending_reviews") or [])
            containers = sorted({str(item.get("container_id")) for item in pending if item.get("container_id") is not None})
            if len(pending) != 1 or containers != [CANONICAL_SAFETY_CONTAINER_ID]:
                return InvalidAgentModelTurn(
                    error_kind="CANONICAL_AMBIGUOUS_CONTAINER",
                    detail="Canonical replay evaluates exactly the single persisted SYN-CNT-010 safety review.",
                )
            return self._turn("request_cargo_safety_review", {"container_id": CANONICAL_SAFETY_CONTAINER_ID})

        if "escalate_agent_run" in tools:
            return self._turn("escalate_agent_run", {})
        return InvalidAgentModelTurn(
            error_kind="CANONICAL_NO_LEGAL_ACTION",
            detail="No canonical legal action is currently exposed; refusing to invent authority.",
        )

    @staticmethod
    def _turn(name: str, arguments: dict) -> AgentModelTurn:
        return AgentModelTurn(tool_call=AgentToolCall(name=name, arguments=arguments), action_summary=f"Canonical replay selects {name}.")


class CanonicalReplaySemanticChecker:
    checker_kind = "canonical-replay-deterministic"
    model_name = None

    def check(self, evidence: SemanticSafetyCheckInput) -> SemanticSafetyCheckOutput:
        match = _HAZARD_TOKEN_PATTERN.search(evidence.note_text) if not evidence.structured_dangerous_goods else None
        if match is None:
            return SemanticSafetyCheckOutput(
                result=SemanticCheckResult.NO_CONTRADICTION_FOUND,
                explanation=(
                    f"No untrusted-note conflict with the trusted structured declaration of "
                    f"{evidence.structured_commodity}; this is evidence only, not a safety determination."
                ),
                evidence_excerpt=None,
            )
        return SemanticSafetyCheckOutput(
            result=SemanticCheckResult.CONTRADICTION_FOUND,
            explanation=(
                f'Untrusted cargo note conflicts with the trusted structured declaration of '
                f'"{evidence.structured_commodity}" (declared free of dangerous goods); '
                "deterministic semantic inconsistency detected for policy review."
            ),
            evidence_excerpt=evidence.note_text[match.start(): match.end()],
        )
