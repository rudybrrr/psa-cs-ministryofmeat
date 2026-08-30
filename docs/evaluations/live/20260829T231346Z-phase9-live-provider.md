# NON-DETERMINISTIC LIVE PROVIDER EVIDENCE

Suite: `phase9-live-provider-evidence`
Generated: `2026-08-29T23:13:59.161298+00:00`
Source revision: `ac69e039fec5761824fdb6130ab128f616974e6b`
Provider calls attempted: `7/10`
Provider calls successful: `7`
Provider calls failed: `0`
Complete workflows: `0/1`
Successful latency p50 ms: `1441.0`
Successful latency p95 ms: `2343.0`
Latency provenance: `CLIENT_OBSERVED_REQUEST_LATENCY`
Stopped stage: `COMPLETE_WORKFLOW`
Cost: `NOT_ESTABLISHED`
Cost amount USD: `NOT_ESTABLISHED`
Cost reason: `NO_PRICING_SNAPSHOT`
Pricing snapshot commit: `NONE`

## Durable evidence IDs

Semantic smoke review: `6cb9623d-9ac3-46db-9991-d875ff82508b`
Semantic smoke assessment: `271061ac-1391-4b84-9456-11b5a0328704`
Semantic smoke policy result: `914fe948-d953-4a43-8d45-5ae4b705f404`
Agent run: `NONE`
Agent steps: `NONE`
Hero safety assessment: `NONE`
Final outcome: `NONE`

| Call | Stage | Method | Success | Model | Input tokens | Output tokens | Latency ms | Tool |
|---:|---|---|:---:|---|---:|---:|---:|---|
| 1 | CONNECTIVITY_SMOKE | responses.parse | yes | gpt-5.6-luna | 306 | 102 | 2343 | — |
| 2 | SEMANTIC_SAFETY_SMOKE | responses.parse | yes | gpt-5.6-luna | 318 | 117 | 2022 | — |
| 3 | TOOL_SELECTION_SMOKE | responses.create | yes | gpt-5.6-terra | 419 | 26 | 1174 | pause_agent_run |
| 4 | COMPLETE_WORKFLOW | responses.create | yes | gpt-5.6-terra | 1101 | 25 | 1441 | pause_agent_run |
| 5 | COMPLETE_WORKFLOW | responses.create | yes | gpt-5.6-terra | 1007 | 70 | 1675 | request_expedite_feasibility |
| 6 | COMPLETE_WORKFLOW | responses.create | yes | gpt-5.6-terra | 1028 | 54 | 1136 | prepare_rta_request |
| 7 | COMPLETE_WORKFLOW | responses.create | yes | gpt-5.6-terra | 1172 | 63 | 1386 | send_authorised_rta_request |
