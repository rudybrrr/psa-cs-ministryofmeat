# Workstreams

This file is maintained only by the lead/integration workflow. Individual agents edit only their assigned file under `docs/coordination/logs/`.

| Workstream | Owner log | Branch | Base | Status | Scope |
| --- | --- | --- | --- | --- | --- |
| Task 1: foundation and contracts | `win-codex.md` | `main` | unborn branch | Complete; pending contract approval | Result `0271bb7c24f2d97af7bdf86628c55df3a5a9f07c`; plan hygiene, coordination baseline, project metadata, frozen domain contracts, and contract tests |
| Task 2: state and persistence | `win-codex.md` | `main` | `0373384567b5ca32ea41ed007987bf0b75a9d2de` | Complete; pending Task 3 authorization | Result `2f868e8e48d7569ac0945bed8e25f13ea2944fef`; explicit state machine, SQLModel/SQLite repositories, and append-only audit service/tests only |

## Coordination rules

- The lead/integration workflow alone edits this file.
- Every agent edits only its own environment log.
- Every completed log entry records timestamp, task, branch, base SHA, resulting HEAD SHA, files changed, tests and results, interfaces/contracts changed, deliberate deferrals, blockers, and recommended next step.
- `DECISIONS.md` is append-only and only records changes to frozen interfaces, architecture, or scope.
- No agent may silently change a frozen domain contract. Stop and record or propose the change in `DECISIONS.md` before implementation.
