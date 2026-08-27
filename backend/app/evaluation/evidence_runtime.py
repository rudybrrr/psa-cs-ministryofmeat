"""Local, non-SLA runtime measurement for the canonical evidence run."""

from __future__ import annotations

import math
import platform
import statistics
import sys
from collections.abc import Callable, Sequence
from time import perf_counter_ns

from backend.app.domain.agent_runtime import AgentToolInvocationStatus
from backend.app.domain.evidence import (
    ClaimReproducibility,
    ClaimStatus,
    DeterministicRuntimeMetrics,
    EvidenceClaim,
    EvidenceReference,
    assert_verified,
)
from backend.app.evaluation.evidence_safety_agent import CanonicalEvidenceRun


def nearest_rank_percentile(values: Sequence[float], percentile: float) -> float:
    """Return the conventional median at p50 and nearest-rank otherwise."""

    if not 0 < percentile <= 1:
        raise ValueError("percentile must be in (0, 1]")
    if not values:
        raise ValueError("values must not be empty")

    ordered = sorted(values)
    if percentile == 0.5:
        return float(statistics.median(ordered))
    return float(ordered[math.ceil(percentile * len(ordered)) - 1])


def measure_local_runtime(
    run_once: Callable[[], CanonicalEvidenceRun], repetitions: int
) -> DeterministicRuntimeMetrics:
    """Time complete, caller-isolated canonical runs on this local machine."""

    if repetitions < 1:
        raise ValueError("repetitions must be at least one")

    durations_ms: list[float] = []
    for _ in range(repetitions):
        started_ns = perf_counter_ns()
        result = run_once()
        duration_ms = (perf_counter_ns() - started_ns) / 1_000_000
        _assert_canonical_run_shape(result)
        durations_ms.append(duration_ms)

    durations = tuple(durations_ms)
    return DeterministicRuntimeMetrics(
        repetitions=repetitions,
        run_durations_ms=durations,
        canonical_run_wall_clock_ms=durations[0],
        p50_local_runtime_ms=nearest_rank_percentile(durations, 0.5),
        p95_local_runtime_ms=nearest_rank_percentile(durations, 0.95),
        step_count=6,
        successful_tool_call_count=5,
        python_version=sys.version,
        platform=platform.platform(),
    )


def local_runtime_claim(metrics: DeterministicRuntimeMetrics) -> EvidenceClaim:
    """Describe local timing evidence without creating a second tool-count claim."""

    reference = EvidenceReference(
        record_type="LocalRuntimeMeasurement",
        stable_key="canonical-run:local-runtime",
        source="evidence_runtime.measure_local_runtime",
    )
    return EvidenceClaim(
        claim_id="local_runtime_measurement",
        statement="Canonical evidence runtime was measured on the local machine.",
        status=ClaimStatus.VERIFIED,
        observed_value={
            "repetitions": metrics.repetitions,
            "run_durations_ms": list(metrics.run_durations_ms),
            "canonical_run_wall_clock_ms": metrics.canonical_run_wall_clock_ms,
            "p50_local_runtime_ms": metrics.p50_local_runtime_ms,
            "p95_local_runtime_ms": metrics.p95_local_runtime_ms,
            "python_version": metrics.python_version,
            "platform": metrics.platform,
        },
        evidence_refs=(reference,),
        caveat=(
            "LOCAL_MACHINE_DEPENDENT measurement only; it is not a production SLA "
            "or a deterministic timing claim."
        ),
        reproducibility=ClaimReproducibility(
            deterministic=False,
            included_in_fingerprint=False,
        ),
    )


def _assert_canonical_run_shape(result: CanonicalEvidenceRun) -> None:
    assert_verified(
        result.agent_run.step_count == 6,
        "agent_step_count",
        f"observed {result.agent_run.step_count}",
    )
    invocations = result.agent_history.tool_invocations
    assert_verified(
        len(invocations) == 5
        and all(
            invocation.status is AgentToolInvocationStatus.SUCCEEDED
            for invocation in invocations
        ),
        "deterministic_tool_call_count",
        f"observed {len(invocations)} successful tool calls",
    )
