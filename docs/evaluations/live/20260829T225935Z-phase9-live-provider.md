# NON-DETERMINISTIC LIVE PROVIDER EVIDENCE

Suite: `phase9-live-provider-evidence`
Generated: `2026-08-29T22:59:45.353370+00:00`
Source revision: `807583bb058803dc6b115f160868547bbc083fdd`
Provider calls attempted: `4/10`
Provider calls successful: `4`
Provider calls failed: `0`
Complete workflows: `0/1`
Successful latency p50 ms: `2367.0`
Successful latency p95 ms: `2964.0`
Latency provenance: `CLIENT_OBSERVED_REQUEST_LATENCY`
Stopped stage: `COMPLETE_WORKFLOW`
Cost: `NOT_ESTABLISHED`
Cost amount USD: `NOT_ESTABLISHED`
Cost reason: `NO_PRICING_SNAPSHOT`
Pricing snapshot commit: `NONE`

## Durable evidence IDs

Semantic smoke review: `0ec881a1-72cc-4fa2-91d5-f086435bc178`
Semantic smoke assessment: `e44c7a46-256e-4ab2-9171-bfdd6fc37eb1`
Semantic smoke policy result: `1139864e-4ce3-491e-ab1f-4fb5bb73c785`
Agent run: `NONE`
Agent steps: `NONE`
Hero safety assessment: `NONE`
Final outcome: `NONE`

| Call | Stage | Method | Success | Model | Input tokens | Output tokens | Latency ms | Tool |
|---:|---|---|:---:|---|---:|---:|---:|---|
| 1 | CONNECTIVITY_SMOKE | responses.parse | yes | gpt-5.6-luna | 306 | 120 | 2964 | — |
| 2 | SEMANTIC_SAFETY_SMOKE | responses.parse | yes | gpt-5.6-luna | 318 | 145 | 2693 | — |
| 3 | TOOL_SELECTION_SMOKE | responses.create | yes | gpt-5.6-terra | 261 | 26 | 1335 | pause_agent_run |
| 4 | COMPLETE_WORKFLOW | responses.create | yes | gpt-5.6-terra | 879 | 33 | 2367 | get_incident_context |
