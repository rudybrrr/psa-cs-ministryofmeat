# Synthetic Fixtures

This directory is reserved for clearly synthetic, deterministic scenario data. It does not contain or represent a production PSA, carrier, manifest, schedule, or yard integration.

The first vertical slice uses only these fixed synthetic values:

- Terminal: `SYN-TUAS-TERMINAL`
- Delay event: `SYN-EVT-20260821-001`
- Inbound vessel call: `SYN-VC-SOUTHERN-STAR-01`
- Inbound vessel: `M/V Synthetic Southern Star`
- Scheduled arrival: `2026-08-21T05:00:00Z`
- Estimated arrival: `2026-08-21T06:30:00Z`
- Delay: 90 minutes
- Container: `PSAU1234567`, synthetic industrial machinery, 18,500 kg, non-DG, Rotterdam (`NLRTM`) to Jakarta (`IDJKT`)
- Connection: `SYN-CONN-STRAITS-01`
- Outbound vessel/voyage: `M/V Synthetic Straits Pioneer` / `SYN-SP-2108`
- Connection cutoff/departure: `2026-08-21T07:30:00Z` / `2026-08-21T09:00:00Z`
- Normal/expedited transfer: 120 / 45 minutes
- Yard forecast: `SYN-YARD-20260821-AM`, window `06:00Z`–`10:00Z`, four available expedite slots

The adapters expose read-only retrieval and feasibility behavior. They do not alter carrier schedules, DG rules, or yard capacity.
