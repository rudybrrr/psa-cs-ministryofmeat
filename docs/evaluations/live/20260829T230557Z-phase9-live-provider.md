# NON-DETERMINISTIC LIVE PROVIDER EVIDENCE

Suite: `phase9-live-provider-evidence`
Generated: `2026-08-29T23:06:11.449539+00:00`
Source revision: `3cdb71c9820d4e1c8e3997cab8bbdf80808ddab0`
Provider calls attempted: `7/10`
Provider calls successful: `7`
Provider calls failed: `0`
Complete workflows: `0/1`
Successful latency p50 ms: `1798.0`
Successful latency p95 ms: `2697.0`
Latency provenance: `CLIENT_OBSERVED_REQUEST_LATENCY`
Stopped stage: `COMPLETE_WORKFLOW`
Cost: `NOT_ESTABLISHED`
Cost amount USD: `NOT_ESTABLISHED`
Cost reason: `NO_PRICING_SNAPSHOT`
Pricing snapshot commit: `NONE`

## Durable evidence IDs

Semantic smoke review: `6b5bfad7-48a2-44db-b82b-da5e0eff04ee`
Semantic smoke assessment: `546b8d94-ec14-48a2-9b14-442af9028a97`
Semantic smoke policy result: `87a034ba-51c4-4f2a-b99b-210ee8e81bfd`
Agent run: `NONE`
Agent steps: `NONE`
Hero safety assessment: `NONE`
Final outcome: `NONE`

| Call | Stage | Method | Success | Model | Input tokens | Output tokens | Latency ms | Tool |
|---:|---|---|:---:|---|---:|---:|---:|---|
| 1 | CONNECTIVITY_SMOKE | responses.parse | yes | gpt-5.6-luna | 306 | 124 | 2697 | — |
| 2 | SEMANTIC_SAFETY_SMOKE | responses.parse | yes | gpt-5.6-luna | 318 | 135 | 2144 | — |
| 3 | TOOL_SELECTION_SMOKE | responses.create | yes | gpt-5.6-terra | 419 | 26 | 1168 | pause_agent_run |
| 4 | COMPLETE_WORKFLOW | responses.create | yes | gpt-5.6-terra | 1122 | 15 | 1798 | pause_agent_run |
| 5 | COMPLETE_WORKFLOW | responses.create | yes | gpt-5.6-terra | 1172 | 70 | 2191 | request_expedite_feasibility |
| 6 | COMPLETE_WORKFLOW | responses.create | yes | gpt-5.6-terra | 1193 | 27 | 1317 | prepare_rta_request |
| 7 | COMPLETE_WORKFLOW | responses.create | yes | gpt-5.6-terra | 1371 | 74 | 1745 | get_carrier_recovery_history |
