from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from enum import StrEnum
from typing import Literal, Self

from pydantic import AwareDatetime, Field, JsonValue, model_validator

from backend.app.domain.models import FrozenContract


class ClaimStatus(StrEnum):
    VERIFIED = "VERIFIED"
    NOT_ESTABLISHED = "NOT_ESTABLISHED"
    DEFERRED = "DEFERRED"


class CoverageRole(StrEnum):
    PRIMARY_RECORD = "PRIMARY_RECORD"
    TYPED_HISTORY = "TYPED_HISTORY"
    AUDIT_EVENT = "AUDIT_EVENT"
    FROZEN_ARTIFACT = "FROZEN_ARTIFACT"


class EvidenceReference(FrozenContract):
    record_type: str = Field(min_length=1)
    stable_key: str = Field(min_length=1)
    source: str = Field(min_length=1)
    record_id: str | None = None


class ClaimReproducibility(FrozenContract):
    deterministic: bool
    included_in_fingerprint: bool
    fixture_ids: tuple[str, ...] = ()
    seed_manifest_id: str | None = None
    benchmark_reproducibility_key: str | None = None


class EvidenceClaim(FrozenContract):
    claim_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    statement: str = Field(min_length=1)
    status: ClaimStatus
    observed_value: JsonValue | None
    evidence_refs: tuple[EvidenceReference, ...] = ()
    caveat: str = Field(min_length=1)
    reproducibility: ClaimReproducibility | None = None

    @model_validator(mode="after")
    def valid_status_shape(self) -> Self:
        if self.status is ClaimStatus.VERIFIED:
            if self.observed_value is None or not self.evidence_refs:
                raise ValueError(
                    "VERIFIED claim requires an observation and evidence reference"
                )
        elif self.status is ClaimStatus.NOT_ESTABLISHED:
            if self.observed_value is None:
                raise ValueError(
                    "NOT_ESTABLISHED claim requires a partial-evidence observation"
                )
        else:
            later_phase = re.search(r"PHASE_([0-9]+)\b", self.caveat)
            if later_phase is None or int(later_phase.group(1)) <= 8:
                raise ValueError("DEFERRED claim caveat must name an owning later phase")
            if _contains_numeric_value(self.observed_value):
                raise ValueError("DEFERRED claim cannot contain observed numeric values")

        reference_keys = [
            (reference.record_type, reference.stable_key)
            for reference in self.evidence_refs
        ]
        if len(reference_keys) != len(set(reference_keys)):
            raise ValueError(
                "evidence references require unique record_type/stable_key pairs"
            )
        return self


class ProvenanceEntry(FrozenContract):
    claim_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    record_type: str = Field(min_length=1)
    stable_key: str = Field(min_length=1)
    source: str = Field(min_length=1)
    record_id: str | None = None
    coverage_role: CoverageRole


class DeterministicRuntimeMetrics(FrozenContract):
    repetitions: int = Field(ge=1)
    run_durations_ms: tuple[float, ...]
    canonical_run_wall_clock_ms: float = Field(ge=0)
    p50_local_runtime_ms: float = Field(ge=0)
    p95_local_runtime_ms: float = Field(ge=0)
    step_count: int = Field(ge=0)
    successful_tool_call_count: int = Field(ge=0)
    label: Literal["LOCAL_MACHINE_DEPENDENT"] = "LOCAL_MACHINE_DEPENDENT"
    production_sla_claimed: Literal[False] = False
    python_version: str = Field(min_length=1)
    platform: str = Field(min_length=1)

    @model_validator(mode="after")
    def duration_count_matches_repetitions(self) -> Self:
        if len(self.run_durations_ms) != self.repetitions:
            raise ValueError("run duration count must match repetitions")
        return self


class EvidenceReportBody(FrozenContract):
    schema_version: Literal["phase8-evidence-v1"] = "phase8-evidence-v1"
    suite_id: Literal["phase8-deterministic-evidence"] = (
        "phase8-deterministic-evidence"
    )
    evaluation_base_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_revision: str | None = Field(default=None, pattern=r"^[0-9a-f]{40}$")
    generated_at: AwareDatetime
    command: str = Field(min_length=1)
    cli_version: str = Field(min_length=1)
    fixture_ids: tuple[str, ...]
    seed_manifest_id: str
    canonical_model_identity: str
    canonical_checker_identity: str
    claims: tuple[EvidenceClaim, ...]
    provenance: tuple[ProvenanceEntry, ...]
    runtime: DeterministicRuntimeMetrics

    @model_validator(mode="after")
    def unique_claims_with_consistent_provenance(self) -> Self:
        claim_ids = [claim.claim_id for claim in self.claims]
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("report claim IDs must be unique")

        expected = Counter(
            (
                claim.claim_id,
                reference.record_type,
                reference.stable_key,
                reference.source,
                reference.record_id,
            )
            for claim in self.claims
            if claim.status is not ClaimStatus.DEFERRED
            for reference in claim.evidence_refs
        )
        actual = Counter(
            (
                entry.claim_id,
                entry.record_type,
                entry.stable_key,
                entry.source,
                entry.record_id,
            )
            for entry in self.provenance
        )
        if actual != expected:
            raise ValueError(
                "provenance must exactly match every non-deferred claim reference"
            )
        return self


class Phase8EvidenceReport(EvidenceReportBody):
    deterministic_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")

    def body(self) -> EvidenceReportBody:
        return EvidenceReportBody.model_validate(
            self.model_dump(exclude={"deterministic_fingerprint"})
        )


class EvidenceInvariantFailure(RuntimeError):
    def __init__(self, claim_id: str, detail: str) -> None:
        super().__init__(f"{claim_id}: {detail}")
        self.claim_id = claim_id


def assert_verified(condition: bool, claim_id: str, detail: str) -> None:
    if not condition:
        raise EvidenceInvariantFailure(claim_id, detail)


def normalized_evidence_payload(body: EvidenceReportBody) -> dict[str, object]:
    claims: list[dict[str, object]] = []
    for claim in sorted(body.claims, key=lambda item: item.claim_id):
        references = [
            {
                "record_type": reference.record_type,
                "stable_key": reference.stable_key,
                "source": reference.source,
            }
            for reference in sorted(
                claim.evidence_refs,
                key=lambda item: (item.record_type, item.stable_key, item.source),
            )
        ]
        reproducibility = (
            None
            if claim.reproducibility is None
            else claim.reproducibility.model_dump(mode="json")
        )
        normalized_claim: dict[str, object] = {
            "claim_id": claim.claim_id,
            "statement": claim.statement,
            "status": claim.status.value,
            "evidence_refs": references,
            "caveat": claim.caveat,
            "reproducibility": reproducibility,
        }
        if (
            claim.reproducibility is None
            or claim.reproducibility.included_in_fingerprint
        ):
            normalized_claim["observed_value"] = claim.observed_value
        claims.append(normalized_claim)

    return {
        "schema_version": body.schema_version,
        "suite_id": body.suite_id,
        "evaluation_base_sha": body.evaluation_base_sha,
        "fixture_ids": body.fixture_ids,
        "seed_manifest_id": body.seed_manifest_id,
        "canonical_model_identity": body.canonical_model_identity,
        "canonical_checker_identity": body.canonical_checker_identity,
        "claims": claims,
        "runtime": {
            "step_count": body.runtime.step_count,
            "successful_tool_call_count": body.runtime.successful_tool_call_count,
        },
    }


def evidence_fingerprint(body: EvidenceReportBody) -> str:
    payload = normalized_evidence_payload(body)
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _contains_numeric_value(value: JsonValue | None) -> bool:
    if isinstance(value, bool) or value is None:
        return False
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, list):
        return any(_contains_numeric_value(item) for item in value)
    if isinstance(value, dict):
        return any(_contains_numeric_value(item) for item in value.values())
    return False
