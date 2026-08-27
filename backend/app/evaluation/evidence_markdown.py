"""Pure Markdown projection of a validated Phase 8 evidence report."""

from __future__ import annotations

import json
from typing import Iterable

from backend.app.domain.evidence import EvidenceClaim, Phase8EvidenceReport


def _claims_with_prefix(
    report: Phase8EvidenceReport, prefixes: tuple[str, ...]
) -> tuple[EvidenceClaim, ...]:
    return tuple(
        sorted(
            (
                claim
                for claim in report.claims
                if claim.claim_id.startswith(prefixes)
            ),
            key=lambda claim: claim.claim_id,
        )
    )


def _claim_lines(claims: Iterable[EvidenceClaim]) -> list[str]:
    lines: list[str] = []
    for claim in sorted(claims, key=lambda item: item.claim_id):
        observed = json.dumps(
            claim.observed_value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        lines.append(
            f"- `{claim.claim_id}` — **{claim.status.value}** — {observed} — {claim.caveat}"
        )
    return lines


def _section(title: str, claims: Iterable[EvidenceClaim]) -> list[str]:
    return [f"## {title}", "", *_claim_lines(claims), ""]


def render_evidence_summary(report: Phase8EvidenceReport) -> str:
    """Render only values already present in the validated report."""

    if not isinstance(report, Phase8EvidenceReport):
        raise ValueError("render_evidence_summary requires Phase8EvidenceReport")
    report = Phase8EvidenceReport.model_validate(
        report.model_dump(mode="python", round_trip=True)
    )

    by_id = {claim.claim_id: claim for claim in report.claims}
    headline_ids = (
        "agent_terminal_state",
        "audit_material_action_coverage",
        "safety_terminal_escalation",
        "scarcity_expected_preserved_delta",
    )
    delta = by_id["scarcity_expected_preserved_delta"].observed_value
    if not isinstance(delta, dict):
        raise ValueError("scarcity delta observation is malformed")

    lines = [
        "# Phase 8 Deterministic Evidence Summary",
        "",
        "## Metadata and fingerprint",
        "",
        f"- Schema: `{report.schema_version}`",
        f"- Suite: `{report.suite_id}`",
        f"- Evaluation base: `{report.evaluation_base_sha}`",
        f"- Source revision: `{report.source_revision or 'unavailable'}`",
        f"- Generated at: `{report.generated_at.isoformat()}`",
        f"- Fixture IDs: `{', '.join(report.fixture_ids)}`",
        f"- Seed manifest: `{report.seed_manifest_id}`",
        f"- Canonical model: `{report.canonical_model_identity}`",
        f"- Canonical checker: `{report.canonical_checker_identity}`",
        f"- Fingerprint: `{report.deterministic_fingerprint}`",
        "",
        *_section("Verified headline", (by_id[item] for item in headline_ids)),
        *_section("Frozen scarcity", _claims_with_prefix(report, ("scarcity_",))),
        (
            "Frozen expected-preserved improvement: "
            f"`{float(delta['delta']):.4f}` (`+{float(delta['relative_improvement_percent']):.4f}%`)."
        ),
        "",
        *_section("Dynamic reconsideration", _claims_with_prefix(report, ("dynamic_",))),
        *_section(
            "Authority and tradeoff",
            _claims_with_prefix(report, ("authority_", "human_tradeoff_")),
        ),
        *_section(
            "Safety and agent",
            _claims_with_prefix(report, ("safety_", "agent_", "deterministic_tool_")),
        ),
        *_section("Audit and provenance", _claims_with_prefix(report, ("audit_",))),
        *(
            f"- `{row.claim_id}` → `{row.record_type}` / `{row.stable_key}` "
            f"({row.coverage_role.value}; `{row.source}`)"
            for row in report.provenance
            if row.claim_id.startswith("audit_")
        ),
        "",
        "## Runtime and resource label",
        "",
        f"- Label: `{report.runtime.label}`",
        f"- Production SLA claimed: `{str(report.runtime.production_sla_claimed).lower()}`",
        *_claim_lines((by_id["deterministic_local_runtime"],)),
        "",
        *_section(
            "NOT_ESTABLISHED",
            (claim for claim in report.claims if claim.status.value == "NOT_ESTABLISHED"),
        ),
        *_section(
            "DEFERRED",
            (claim for claim in report.claims if claim.status.value == "DEFERRED"),
        ),
        "## Regeneration command",
        "",
        "```text",
        report.command,
        "```",
        "",
    ]
    return "\n".join(lines)


__all__ = ["render_evidence_summary"]
