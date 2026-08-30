# NON-DETERMINISTIC LIVE PROVIDER EVIDENCE

Suite: `phase9-live-provider-evidence`
Generated: `2026-08-29T22:36:01.471284+00:00`
Source revision: `d52cc0493f1e4c9e6284ddf65e71c1367e0f7851`
Provider calls attempted: `2/10`
Provider calls successful: `2`
Provider calls failed: `0`
Complete workflows: `0/1`
Successful latency p50 ms: `2493.0`
Successful latency p95 ms: `5640.0`
Latency provenance: `CLIENT_OBSERVED_REQUEST_LATENCY`
Stopped stage: `SEMANTIC_SAFETY_SMOKE`
Cost: `NOT_ESTABLISHED`
Cost amount USD: `NOT_ESTABLISHED`
Cost reason: `NO_PRICING_SNAPSHOT`
Pricing snapshot commit: `NONE`

## Durable evidence IDs

Semantic smoke review: `NONE`
Semantic smoke assessment: `NONE`
Semantic smoke policy result: `NONE`
Agent run: `NONE`
Agent steps: `NONE`
Hero safety assessment: `NONE`
Final outcome: `NONE`

| Call | Stage | Method | Success | Model | Input tokens | Output tokens | Latency ms | Tool |
|---:|---|---|:---:|---|---:|---:|---:|---|
| 1 | CONNECTIVITY_SMOKE | responses.parse | yes | gpt-5.6-luna | 271 | 116 | 5640 | — |
| 2 | SEMANTIC_SAFETY_SMOKE | responses.parse | yes | gpt-5.6-luna | 283 | 139 | 2493 | — |
