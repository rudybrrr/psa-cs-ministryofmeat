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

## Canonical 24-container scarcity fixture

`canonical-24-container.json` is the clearly synthetic, deterministic Phase 2 source fixture. It is validated directly as `CanonicalIncidentFixture` by a read-only local-file adapter; it is not a PSA, carrier, manifest, schedule, or yard integration.

- Fixture: `SYN-CANONICAL-24-V1`
- Terminal: `SYN-TUAS-TERMINAL`
- Inbound service: `ASX-17`
- Inbound vessel call: `SYN-ASX17-TUAS-001`
- Inbound vessel: `M/V Synthetic Meridian`
- Scheduled/estimated arrival: `2026-08-22T01:00:00Z` / `2026-08-22T04:15:00Z`, a synthetic 195-minute delay
- Onward services: SF1 (9 containers), JV2 (8), and EC3 (7)
- Cargo: 14 dry, 6 reefer, and 4 structurally represented DG containers
- Ready boundaries: PTA + 35 minutes for every onward service
- Expedite saving: 30 minutes
- Critical overlap: SF1/JV2, with eight total expedite slots
- Handling-group limits: `SYN-A-EQ1=4`, `SYN-B-EQ2=3`, `SYN-C-EQ3=3`
- Hard safety limits: at most three reefers and one structurally cleared DG allocation

The fixture deliberately stores no beneficiary or outcome label. P50 classification is derived from ready time, the service boundary, the 30-minute expedite saving, reefer continuity, and structural DG clearance. Those values derive 13 expedite candidates (7 SF1 and 6 JV2), while capacity permits at most eight allocations; five containers need no expedition and six cannot be preserved by expedition alone.

DG information in this Phase 2 fixture is structural synthetic data only. It does not perform semantic mismatch analysis, infer a UN number, negotiate with a carrier, or invoke an LLM. The later RTA phase remains separate, and this fixture does not hard-code a full-demo 18/5/1 result.

## Synthetic carrier-demo suite

`canonical-carrier-response-plan.json` is a versioned, deterministic Phase 3
carrier-demo suite (`SYN-CANONICAL-CARRIER-DEMO-V1`). It contains three named,
independent runs, each against a separate canonical Phase 2 incident instance:

- `ACCEPT-RUN`: `SYN-CONN-JV2` → `ACCEPT`
- `COUNTER-RUN`: `SYN-CONN-JV2` → `COUNTER`
- `SILENT-RUN`: `SYN-CONN-EC3` → `SILENT`

The repeated JV2 connection is valid: carrier-recovery case uniqueness is
`(incident_id, connection_id)`, not connection ID globally. SF1 is deliberately
absent because frozen Phase 2 evidence provides no preparable zero-world SF1
carrier-recovery candidate. This suite is a synthetic demo-fixture correction;
it does not alter the Phase 2 canonical fixture, benchmark, selected allocation,
or preparation eligibility.

`SILENT` means no `CarrierResponse` is persisted. It becomes evidence only when
an explicit timeout is recorded by `SYSTEM`. The plan is synthetic and intended
only for deterministic demonstrations and tests; it does not claim hard-coded
recovery counts.

## Phase 5A runtime configuration

`canonical-agent-runtime-config.json` contains trusted synthetic backend inputs
for the narrow Phase 5A carrier facade: canonical RTA prepare timestamps and
injectable clock values before and at a response deadline. The LLM never reads
or supplies these values. It receives only a connection or case identity; the
backend constructs the existing Phase 3 command and remains responsible for
validating it. The synthetic harness may select the clock value, but the agent
cannot advance or fabricate time.

The RTA interaction is representative of DCSA Estimated / Requested / Planned /
Actual timing interactions. PSA does not claim to use this exact interaction
today. Any deployment adapter must map the same authority boundary to PSA's real
operational interfaces and authority model; this fixture never authorizes a local
carrier schedule mutation.

## Frozen scarcity evaluation seeds

`scarcity-evaluation-seeds.json` declares 50 synthetic holdout seeds for the
canonical fixture. They are deterministic SHA-256-derived experimental inputs,
not PSA data or calibrated operating distributions. Development uses separate
debug seeds; the frozen holdout seeds must not be used to tune fixture values,
scenario distributions, allocator behavior, Pareto filtering, or dominance
policy. A correctness defect after evaluation requires a newly versioned
manifest and an explicit coordination decision.
