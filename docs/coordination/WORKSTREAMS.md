# Workstreams

This file is maintained only by the lead/integration workflow. Individual agents edit only their assigned file under `docs/coordination/logs/`.

| Workstream | Owner log | Branch | Base | Status | Scope |
| --- | --- | --- | --- | --- | --- |
| Task 1: foundation and contracts | `win-codex.md` | `main` | unborn branch | Complete; pending contract approval | Result `0271bb7c24f2d97af7bdf86628c55df3a5a9f07c`; plan hygiene, coordination baseline, project metadata, frozen domain contracts, and contract tests |
| Task 2: state and persistence | Unassigned | — | — | Blocked pending approval | Do not begin until Task 1 contracts are approved |

## Coordination rules

- The lead/integration workflow alone edits this file.
- Every agent edits only its own environment log.
- Every completed log entry records timestamp, task, branch, base SHA, resulting HEAD SHA, files changed, tests and results, interfaces/contracts changed, deliberate deferrals, blockers, and recommended next step.
- `DECISIONS.md` is append-only and only records changes to frozen interfaces, architecture, or scope.
- No agent may silently change a frozen domain contract. Stop and record or propose the change in `DECISIONS.md` before implementation.
