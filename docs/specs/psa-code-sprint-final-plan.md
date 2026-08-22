# PSA Code Sprint 2.0: Final Plan

**Team decision, 21 August 2026. Submission 30 August. Nine days.**

This is decided, not proposed. Reading it should take five minutes.

> **What it does:** when a late vessel breaks transhipment connections, it triages every affected container: allocates scarce yard capacity under forecast uncertainty, negotiates a later berth time with the onward carrier, rolls what cannot be saved, and escalates unsafe calls to a human, leaving a full audit trace.
>
> **Why it wins:** the agent has no tool for authority PSA does not hold, so it cannot hallucinate actions a terminal cannot take, and it allocates a genuinely scarce resource under uncertainty rather than comparing each container to a threshold.

---

## The idea in one paragraph

A mainline vessel arrives late at Tuas. Containers booked onto three onward services can no longer make their connections. Our system manages the recovery exception container by container: deterministic systems establish what is feasible, a dominance policy may select a clearly dominant recovery, and a human operator decides when the feasible alternatives contain a genuine business trade-off. The agent gathers the changing evidence, handles authorised tools and counterparties, and explains the options. It does not predict the delay, replace the TOS, or optimise the berth plan. Those systems exist. It handles what happens to the box after the plan has already broken.

## The pitch line

> 24 transhipment containers are at risk. Thirteen could benefit from expedited handling. The terminal has capacity for eight. The onward carrier has not agreed to adjust its timing.

Never open with "a vessel has been delayed by three hours." Everyone will have that.

---

## What makes this hard (and why it is not a rules engine)

Four things, and all four must be built. If any is dropped, this becomes an if-statement with a language model attached and it loses.

**Scarce capacity, allocated under uncertainty.** Thirteen containers could benefit from expedited yard handling. Equipment supports eight during the critical overlap. The allocation does not run on median ready times: it maximises the *expected* number of preserved connections given each container's forecast distribution, subject to equipment, block, reefer and DG constraints. A box whose median makes the boundary but whose p90 does not is worth less than a box with a tighter band, and the solver reflects that. The solver produces feasible, Pareto-efficient alternatives. An established deterministic dominance policy may select only when one alternative clearly dominates; if the alternatives retain a genuine cargo-priority or downstream-consequence trade-off, a human operator decides. The agent gathers and explains the evidence but does not convert those business trade-offs into arbitrary prose judgment.

**Uncertainty.** Ready times are forecasts, not facts. Before discharge starts the yard returns a band (p10 12:58 / p50 13:08 / p90 13:23), not a number. Once discharge begins the bands tighten and the agent must revisit earlier recommendations, because containers that were marginal under a wide band may no longer be.

**External authority.** PSA cannot order another company's feeder to wait. It can issue a request under DCSA's Estimated / Requested / Planned / Actual pattern and the carrier decides. The carrier may accept, counter, or say nothing at all.

**Safety that cannot be argued with.** A dangerous goods container passes structured validation, but the free-text commodity description contradicts the declaration. The agent flags the contradiction, refuses to resolve it, and escalates. It never infers a UN number or classifies the cargo itself.

---

## The one architectural decision to lead with

The agent's tool list encodes organisational authority. Actions PSA cannot take do not exist as tools.

**Available:** `request_expedite_feasibility()`, `prepare_rta_request()`, `send_authorised_rta_request()`, `roll_container()`, `escalate_case()`

**Does not exist:** `hold_feeder()`, `change_carrier_schedule()`, `override_dg_rule()`, `set_yard_capacity()`

A model cannot hallucinate an authority it has no tool for. Most teams will build an omnipotent agent. This is our clearest originality claim and it goes on the architecture slide.

---

## What the agent does vs deterministic systems and the human operator

| The agent handles | Deterministic systems decide | The human operator decides |
|---|---|---|
| Which information to gather next and why it matters | Whether a move is physically feasible | Which Pareto-efficient alternative to take when a genuine business trade-off remains |
| The evolving exception as forecasts, tool results and counterparty responses change | Earliest safe ready time and connection feasibility arithmetic | How cargo priority and downstream consequence resolve that trade-off |
| Authorised tool calls and communication with external counterparties | DG segregation, reefer continuity and other hard safety constraints | Whether to approve externally directed actions that require operator authority |
| Detecting missing evidence, failures and silence, then recomputing or escalating | Expedite capacity limits and feasible allocations | Unsafe or exceptional calls escalated beyond deterministic authority |
| Explaining evidence, alternatives and consequences | Whether one alternative clearly dominates under established deterministic policy | Any choice for which no alternative clearly dominates |

The solver returns feasible, Pareto-efficient *sets* under a stochastic objective, not a business-preference ranking. A deterministic dominance policy may select only when one alternative clearly dominates under established policy. If the frontier contains a genuine trade-off, the human operator chooses; the agent gathers information, manages the evolving exception, handles tools and counterparties, and explains the alternatives. We deliberately avoid a hand-weighted scoring formula over priority and cargo type because that hides policy inside arbitrary numbers, and the LLM must not replace those arbitrary numerical weights with equally arbitrary prose judgment. The optimization objective is expected preserved connections; the remaining dimensions are hard constraints, established deterministic policy, or explicit human judgment.

---

## The canonical incident

One scenario. It is the acceptance test, the synthetic data target, the demo script and the deck spine.

Inbound service ASX-17 slips 3h15m. 24 containers at risk across three onward services (SF1 feeder, JV2, EC3). Ready boundary is PTA + 35 minutes for all three services.

| Outcome | Containers |
|---|---|
| Connection preserved | 18 |
| Rolled deliberately | 5 |
| Escalated (DG, cannot be decided safely) | 1 |

The canonical full-demo target uses disjoint outcome buckets: 5 containers are preserved without intervention, 8 are preserved through scarce yard expedition, and 5 are intended to be preserved through the later carrier/RTA recovery phase, for a total target of 18 preserved; 5 are rolled and 1 is escalated. Phase 2 proves only the scarce-capacity portion: 13 containers could benefit from expedition, but only 8 expedite slots exist. The later RTA phase must empirically establish its intended five recoveries. If later implementation evidence differs, report the observed outcome rather than hard-coding the 18/5/1 target.

**Two demo peaks.** The scarce-capacity allocation is the intellectual peak. The DG semantic catch is the emotional peak. Build the video around both.

**All data is synthetic.** Vessel names, container numbers, yard positions and timings are invented to resemble realistic terminal operations. Say so on screen. The integration boundary is modelled on public DCSA OVS and Port Call 2.0 standards.

---

## Build plan

**Stack:** Python + FastAPI backend, React frontend (operations console, no chat UI), SQLite, OR-Tools CP-SAT for capacity feasibility. Plain Python state machine unless someone already knows LangGraph well; do not learn a framework this week.

**Four simulators:** schedule (OVS-shaped), manifest and cargo, yard (returns forecast bands and capacity), carrier (supports ACCEPT / COUNTER / SILENT).

**Ownership**

| Who | Owns | Branch |
|---|---|---|
| Rudy | Architecture, schemas, state machine, agent and tool contracts, yard model, OR-Tools, merges | `feat/core-orchestrator` |
| Teammate 1 | Operations console against a frozen API contract, static JSON first | `feat/ops-dashboard` |
| Teammate 2 | Schedule, manifest and carrier simulators, event generation, scenario reset | `feat/operational-simulator` |
| Teammate 3 | Eval harness, token and latency instrumentation, evidence capture, then deck and video | `feat/evals-demo` |

**Order of work.** Thinnest possible spine first: one container from delay event to decision, printed output, no UI. Then scarcity. Then carrier silence. Then uncertainty bands and the stochastic objective. Then the DG semantic catch. Then the baseline comparison. Polish is what gets cut, never the four hard things above.

**Dates.** 22 Aug: ugly end-to-end run. 23 Aug: differentiators in, deck started in parallel. 24 Aug: security, guardrails, audit, eval suite, baseline comparison. 25 Aug: feature freeze. 26 to 28 Aug: video and deck. 29 Aug: final package plus backup recording. 30 Aug: submit early.

---

## Measurement (this is a scored criterion almost nobody will build)

**The headline number.** Run our stochastic allocator against a naive median-threshold allocator across 50 seeded scenarios and report the delta in preserved connections. Past Code Sprint winners have all carried one defensible quantified claim; this is ours, and unlike a business-impact figure it is reproducible and honestly ours to make.

Alongside correctness evals, report mean tokens per incident, cost per container decision, and p95 latency. The brief explicitly names runtime and resource efficiency including token usage. We already have a `tool_calls` table; instrumenting it is an afternoon.

Correctness evals must assert: DG constraint never bypassed, no carrier schedule ever modified locally, never more than 8 expedite jobs allocated, no RTA sent without operator approval, timeout triggers recomputation, low-confidence boxes reconsidered, every action produces an audit event.

---

## Honest weaknesses (know these before a judge finds them)

**The berth-time lever is an inference.** Real terminals may negotiate the cargo cut-off rather than the carrier's berth arrival, and DCSA's Port Call standard explicitly puts cargo operations out of scope. We use the berth request because it is the only publicly standardised terminal-to-carrier timing mechanism. If asked: the lever may differ, nothing about the agent's role changes.

**The problem size is not publicly measured.** Nobody publishes how often transhipment connections fail or what it costs. Do not invent a number. Say the frequency is not public and explain that this is true of terminal-internal data generally.

**Transhipment is a crowded theme.** Roughly 90% of Singapore's throughput is transhipment, so many teams will land nearby. Our scope (container-level decisions after the connection is already broken) is much narrower than the likely field. This is managed by framing, which is why the pitch line above matters.

**The field is large and the judges are engineers.** The 2024 winner beat 91 other teams. Recent winners carried real algorithmic content and a quantified result: custom allocation heuristics with Bayesian optimisation in 2025, a DQN plus 3D A* router in 2024. Both of those years were scoped to a horizontal-transport theme, so the AGV pattern reflects the brief, not PSA's preference; 2026 is open-ended. But the appetite for genuine technical substance is the reason the stochastic objective and the baseline comparison are non-negotiable rather than nice-to-have.

---

## Rejected, and why

| Idea | Why not |
|---|---|
| Equipment breakdown / crane reallocation | PSA's strongest existing capability, plus an A*STAR fleet management partnership. Whole pitch spent explaining why we are not competing with our judges. |
| DG screening as a standalone project | Absorbed into this plan instead. As a standalone it leans toward classification rather than orchestration and would need the full evidence-chase loop rebuilt. |
| Cross-network disruption recovery | Undemoable in nine days, nine invented data sources, and PSA BDP has a funded A*STAR programme on exactly this. |
| Contractor safety exceptions | Strongest public evidence of a PSA gap, but visually flat and half the pitch defends an LLM near safety-critical work. Backup only. |
| Berth, yard, truck, ETA, digital twin, visibility | PSA already has OptEVoyage, ABT, OptETruck, iWX, Smart Navigator, Risk Monitor and Tuas digital twin work. |

---

## Not up for further discussion

The idea, the scope, and the four hard things. Every remaining decision is an implementation decision. The next artifact this team produces is a repository, not a document.
