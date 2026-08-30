# NON-DETERMINISTIC LIVE PROVIDER EVIDENCE

Suite: `phase9-live-provider-evidence`
Generated: `2026-08-29T22:46:18.771754+00:00`
Source revision: `ce95c2fc2db1fad47874959a051dd4639f144f08`
Provider calls attempted: `5/10`
Provider calls successful: `5`
Provider calls failed: `0`
Complete workflows: `0/1`
Successful latency p50 ms: `2337.0`
Successful latency p95 ms: `3166.0`
Latency provenance: `CLIENT_OBSERVED_REQUEST_LATENCY`
Stopped stage: `COMPLETE_WORKFLOW`
Cost: `NOT_ESTABLISHED`
Cost amount USD: `NOT_ESTABLISHED`
Cost reason: `NO_PRICING_SNAPSHOT`
Pricing snapshot commit: `NONE`

## Durable evidence IDs

Semantic smoke review: `ade5620e-0d36-419a-95b4-543bf166f550`
Semantic smoke assessment: `edafe6da-7b21-427a-831d-b63a8fd9c6c6`
Semantic smoke policy result: `2d5461ea-1bdd-4fb8-a128-b7d41dd48c2e`
Agent run: `NONE`
Agent steps: `NONE`
Hero safety assessment: `NONE`
Final outcome: `NONE`

| Call | Stage | Method | Success | Model | Input tokens | Output tokens | Latency ms | Tool |
|---:|---|---|:---:|---|---:|---:|---:|---|
| 1 | CONNECTIVITY_SMOKE | responses.parse | yes | gpt-5.6-luna | 306 | 103 | 3166 | — |
| 2 | SEMANTIC_SAFETY_SMOKE | responses.parse | yes | gpt-5.6-luna | 318 | 127 | 2337 | — |
| 3 | TOOL_SELECTION_SMOKE | responses.create | yes | gpt-5.6-terra | 173 | 37 | 1745 | pause_agent_run |
| 4 | COMPLETE_WORKFLOW | responses.create | yes | gpt-5.6-terra | 789 | 98 | 2144 | — |
| 5 | COMPLETE_WORKFLOW | responses.create | yes | gpt-5.6-terra | 789 | 96 | 3089 | — |
