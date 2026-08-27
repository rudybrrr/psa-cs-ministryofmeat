# Task 7 report: deterministic runtime and resource measurement

## Scope

Added backend-only local runtime measurement in `backend/app/evaluation/evidence_runtime.py` and focused coverage in `backend/tests/test_evidence_runtime.py`. No provider, network, frontend, or workflow changes were made.

## Implementation

- `nearest_rank_percentile(values, percentile)` rejects percentiles outside `(0, 1]`, uses a conventional median for p50, and otherwise uses nearest rank. The approved examples are covered directly: p50 of `1..20` is `10.5`; p95 is `19.0`.
- `measure_local_runtime(run_once, repetitions)` rejects repetitions below one, measures every complete caller-isolated canonical run with `perf_counter_ns`, and verifies each result has exactly six agent steps and five successful tool calls. It emits `DeterministicRuntimeMetrics` with local duration samples, p50/p95, interpreter/platform metadata, `LOCAL_MACHINE_DEPENDENT`, and `production_sla_claimed=False`.
- `local_runtime_claim(metrics)` creates one `VERIFIED` runtime-evidence claim with `deterministic=False` and `included_in_fingerprint=False`. Its caveat explicitly says the value is local-machine dependent and not a production SLA. It deliberately does not create a second `deterministic_tool_call_count` claim, which is already owned by Task 5.

## Fingerprint behavior

The integration test constructs otherwise-identical report bodies whose duration samples, calculated percentiles, platform, and interpreter fields differ. Their serialized runtime payloads differ, while `normalized_evidence_payload` and `evidence_fingerprint` remain identical. Existing Task 1 normalization retains only the semantic runtime step/tool counts, so timing and machine metadata are excluded from deterministic reproducibility.

## TDD evidence

The new test module was created before the production module. The required focused pytest invocation initially failed at collection with `ModuleNotFoundError: backend.app.evaluation.evidence_runtime`, which was the expected RED state. After implementation, the same command passed.

## Verification

Executed exactly:

```powershell
uv run --python 3.12 --extra dev pytest backend/tests/test_evidence_runtime.py backend/tests/test_evidence_fingerprint.py -q
```

Result: `12 passed`. The suite reports one pre-existing FastAPI/Starlette `TestClient` deprecation warning from the installed `httpx` combination.

`git diff --check` was also run before commit.

## Caveat

The reported durations are intentionally environment-specific diagnostics, not production latency guarantees or SLA evidence. The caller supplies the isolated canonical run factory, keeping database/session setup outside this utility and preserving the existing canonical workflow boundary.
