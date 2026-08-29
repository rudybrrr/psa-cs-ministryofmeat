# NON-DETERMINISTIC LIVE PROVIDER EVIDENCE

Suite: `phase9-live-provider-evidence`
Generated: `2026-08-29T23:23:09.458345+00:00`
Source revision: `3ac64d1c5c65a7c91bd0779cca9f2251a1336c3d`
Provider calls attempted: `10/10`
Provider calls successful: `10`
Provider calls failed: `0`
Complete workflows: `1/1`
Successful latency p50 ms: `1728.0`
Successful latency p95 ms: `2378.0`
Latency provenance: `CLIENT_OBSERVED_REQUEST_LATENCY`
Stopped stage: `NONE`
Cost: `NOT_ESTABLISHED`
Cost amount USD: `NOT_ESTABLISHED`
Cost reason: `NO_PRICING_SNAPSHOT`
Pricing snapshot commit: `NONE`

## Durable evidence IDs

Semantic smoke review: `c029e573-c8b2-4e39-a59a-c9bbf20ebd18`
Semantic smoke assessment: `62fe7bb6-b90e-4cc0-9c58-589965b7d7c7`
Semantic smoke policy result: `a2fa9f47-aa1b-4f7d-aa0b-0e4397a43710`
Agent run: `1b06ca1f-8c7f-4f7a-b6f5-61b89d37d065`
Agent steps: `bce0a4d3-db5e-4356-9708-ab76cea89c54, 3deac403-dafc-4820-9d31-3d3da86dd941, ff6f8fc7-b1ba-4165-b133-e2266b251425, c7980d5c-ee55-4b2b-b42d-d9e05f732eec, 8c3697e2-e16a-4c66-ae74-34201b779fa7, afb03288-3bee-4ffd-badd-1b755ac416f6`
Hero safety assessment: `96131c9d-e4d9-43e3-8fa8-00388715efc4`
Final outcome: `fa1d146f-e288-4868-8301-eff4629deef2`

| Call | Stage | Method | Success | Model | Input tokens | Output tokens | Latency ms | Tool |
|---:|---|---|:---:|---|---:|---:|---:|---|
| 1 | CONNECTIVITY_SMOKE | responses.parse | yes | gpt-5.6-luna | 306 | 129 | 2378 | — |
| 2 | SEMANTIC_SAFETY_SMOKE | responses.parse | yes | gpt-5.6-luna | 318 | 105 | 1728 | — |
| 3 | TOOL_SELECTION_SMOKE | responses.create | yes | gpt-5.6-terra | 419 | 26 | 1085 | pause_agent_run |
| 4 | COMPLETE_WORKFLOW | responses.create | yes | gpt-5.6-terra | 1117 | 28 | 1754 | pause_agent_run |
| 5 | COMPLETE_WORKFLOW | responses.create | yes | gpt-5.6-terra | 1023 | 76 | 1813 | request_expedite_feasibility |
| 6 | COMPLETE_WORKFLOW | responses.create | yes | gpt-5.6-terra | 1034 | 49 | 1849 | prepare_rta_request |
| 7 | COMPLETE_WORKFLOW | responses.create | yes | gpt-5.6-terra | 1164 | 59 | 1711 | send_authorised_rta_request |
| 8 | COMPLETE_WORKFLOW | responses.create | yes | gpt-5.6-terra | 1244 | 43 | 1340 | request_cargo_safety_review |
| 9 | COMPLETE_WORKFLOW | responses.parse | yes | gpt-5.6-luna | 318 | 120 | 2070 | — |
| 10 | OPTIONAL_SAMPLE | responses.create | yes | gpt-5.6-terra | 419 | 25 | 1134 | pause_agent_run |
