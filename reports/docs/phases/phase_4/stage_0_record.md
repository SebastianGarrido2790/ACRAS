# Phase 4 -- Stage 0 Record (Baseline Verification)

**Date:** 2026-11-03
**Stage:** 0 -- Pre-Implementation Verification & Dependency Check
**Status:** Gate 0 passed (Stage 0 authorization granted; Stages 1-6 require separate authorization).

- [x] Workspace operational: Python 3.12.10, `uv` 0.8.11; baseline green after the Stage 0 hygiene fix (see Stage 0 record).

If any precondition is unmet, execution does not begin.

---

## 3. Approved Feature Set & Stage Mapping

| Feature ID | Feature | Approved SDD location | Required by stage(s) | Dependencies | Status |
| --- | --- | --- | --- | --- | --- |
| `P4-01` | Tier 3 evidence contract completion (4 typed fields + `limitations`) | `phase_4/001_tier3_persona_layer/spec.md` §2.1, `plan.md` §2 | 1 | A-05 v2 lock; D4-01; Q-3 | Not started |
| `P4-02` | Persona workers (CRO / Growth / Capital) | same SDD §2.2, `plan.md` §4 | 3 | P4-01; Phase 3 gateway; D4-04/07/08 | Not started |
| `P4-03` | Deterministic divergence, Tier 1 confidence, escalation | same SDD §2.3, `plan.md` §3 | 2 | D4-02/03; Q-1 | Not started |
| `P4-04` | Orchestration, deterministic report, in-memory trace | same SDD §2.4, `plan.md` §5 | 4 | P4-02, P4-03; D4-04/05/06 | Not started |

All four are accepted into phase scope. No candidate is deferred or rejected. P4-03 executes before P4-02 because its inputs are the `PersonaVerdict` contract and recorded fixtures, not live workers — this is the order approved in implementation plan §7.

**Boundary inherited from the plan:** Tier 1 retrain, Tier 2 parameter behavior, divergence calibration, golden-set evaluation, qualitative grounding, durable trace storage, dashboards, and Tier 3 promotion are **not** executable work in this phase.

---

## 4. Stage Index

| Stage | Name | Gate (one line) | Falsification |
| --- | --- | --- | --- |
| 0 | Pre-Implementation Verification & Dependency Check | Baseline, approvals, dependency pin, concurrency mechanism, and Q-1 disposition are evidenced; no production code changed | Evidence reconciliation of three plan claims against the repository (no code fault) |
| 1 | Evidence Contract & Seed-Case Integrity | Four typed fields + `limitations` validate with `None` preserved; seed cases coherent; ADR-016 accepted; v1/Tier 1–2 unchanged | Force one new field to default `0.0`; the null-preservation test must fail |
| 2 | Deterministic Convergence Core | Divergence and both proxies pass property/edge tests; proxy selected per the approved criterion; truth table exhaustive; no auto-approve path | Flip the zero-weight fail-safe to `0.0`; property tests must fail |
| 3 | Persona Workers & Context Isolation | Three isolated calls validate; one repair max; isolation and uniform temperature proven; data-flow corrected | Inject another persona's rationale into one prompt; the isolation test must fail |
| 4 | Orchestration, Report & Trace | Graph runs fan-out → convergence → report; incomplete yields no report; every number traces to a typed field; trace complete | Remove one persona result from state; no report may be produced |
| 5 | Offline Acceptance & Exit-Criteria Verification | Full suite, Ruff, Pyright green; exit criteria 1–5 evidenced offline; independent mutation detected and reverted; `git status` clean | **One-time independent falsification pass** over the finished artifact |
| 6 | ADR Consolidation & Phase Sign-Off | PIR complete; ADRs and docs consolidated; exit criteria signed; Phase 5/6 entry conditions recorded; human sign-off | Documentation-to-reality audit of every closure claim |

Stages are strictly sequential. No stage starts while its predecessor's gate is failed, partial, awaiting approval, or awaiting remediation.

---

## 5. Feature-Level SDD Integration

```text
reports/docs/phases/phase_4/
├── implementation_plan.md          # decisions (approved)
├── execution_plan.md               # this file: phase sequence + gates
├── README.md                       # phase index and status
└── 001_tier3_persona_layer/        # integrated SDD for P4-01…P4-04
    ├── spec.md                     # requirements + contracts + clarification gate
    ├── plan.md                      # design, module layout, test strategy
    └── tasks.md                     # T3-T01…T3-T16
```

The SDD follows `specification → human approval → plan → tasks → implementation → validation`. The four files are submitted for approval as **one package**; no task is executable before that approval. Feature-level task sequencing lives in `tasks.md`; the phase-level order and gates live here. A stage may cover tasks from more than one feature group only where the dependency order above makes it safe (none does in Phase 4).

---

## 6. Implementation Stages

### Stage 0 — Pre-Implementation Verification & Dependency Check

**Goal.** Establish the actual repository state, confirm every approval and open question, and prove the plan is executable before any production code changes.

**Actions**

1. Record branch, `HEAD`, working-tree status, and any local-only commits (the Batch 3 acknowledgment `1c5480e` was intentionally not pushed). No Git writes.
2. Re-run `uv run pytest -q`, `uv run ruff check .`, and `uv run pyright`; record exact counts, skips, duration, and exit codes rather than copying the 2026-11-01 baseline.
3. Immediately re-check `git status --porcelain`. Any tracked-file mutation caused by the suite (notably `gx/expectations/bankruptcy_data_suite.json`) fails the stage — that is an R-15 regression.
4. Verify the plan's state claims against the repository, not against the document: the four fields and `limitations` are absent; `params.yaml` has no `tier3` block; `src/agents/{prompts,orchestration}` are docstring-only; the offline harness has 6 passing tests; fixtures validate as v2. Any mismatch is a blocker to reconcile, never something to "fix" silently.
5. Verify ADR-016 is still reserved with no body, `system_design.md` §3 still lists the duplicate Data Scientist / Financial Analyst rows, and the Phase 4 status row reads "Not started". Record exact line references for the later corrections.
6. Verify approvals and the clarification gate: plan batches, SDD package, this execution plan, explicit implementation authorization, and the owner's **Q-1** choice (plus Q-2/Q-3/Q-4). An unresolved Q-1 blocks Stages 1–2.
7. Dependency check: resolve a candidate `langgraph` pin with a dry-run (no install, no lockfile write), confirm Python 3.12 compatibility, confirm it belongs in `[dependency-groups] tier3` **and** `[tool.uv] default-groups` (so CI installs it) while `uv sync --no-default-groups` in the Dockerfile keeps it out of serving. Confirm `pydantic-ai` stays absent.
8. Concurrency spike: with a throwaway, uncommitted script, measure whether the pinned LangGraph version executes the three fan-out branches concurrently or serially under sync `invoke`. Record measured wall time with sleep stubs. If serial, record that `ainvoke` + `asyncio.to_thread` is required; do not modify Phase 3 gateway code.
9. Verify provider and cost preconditions: both models remain pinned (no swap), `params.yaml` rates match the A-03 record, the live smoke test remains environment-gated, and no credentials exist in tracked files.
10. Verify Gate R-B status and record that the end-to-end raw-row demo, Tier 1 freeze/retrain decision, dataset-to-ratio mapping, Tier 2 semantics, and DVC remote provisioning are **not** Phase 4 exit criteria. They block the raw-row demo and Phase 5 promotion, not this build.
11. Pre-register the Q-1 arithmetic (`spec.md` §7 table) and the owner's chosen selection criterion as stage evidence, so Stage 2 cannot retro-fit a criterion to its result.
12. Produce the baseline record. No production functionality is implemented in this stage.

**Inputs / dependencies.** Approved package; Phase 1–3 evidence; fixtures and harness; `params.yaml`; `pyproject.toml`; Dockerfile; CI workflow.

**ADR Implements.** None new. This stage verifies applicability of already accepted decisions.

**Falsification.** No artificial fault. Reconcile three concrete claims (fields absent; harness 6 pass; no `tier3` config) against the repository and prove or disprove each. A claim that cannot be reproduced fails the gate.

**Stage 0 record — 2026-11-03 (Gate 0 passed).**

| Item | Evidence |
| --- | --- |
| Starting commit | `a8cbe6c` on `main`; `origin/main` identical; clean tree; no local-only commits |
| Suite (pre-fix) | `uv run pytest -q`: 233 passed, 5 skipped, 71 warnings, 125.21 s, exit 0; post-run `git status --porcelain` clean (no R-15 mutation) |
| Static (pre-fix) | `uv run ruff check .`: 14 errors, exit 1; `uv run pyright`: 2 errors, exit 1 — pre-existing since `c1e9c6a` / `d8be010`, not caused by Phase 4 docs |
| Hygiene fix | Owner-approved, behavior-neutral: import order, unused import/vars, 8×`E501` wraps, 3×`W293`, 2 Optional guards. Files: `src/schemas/evidence_bundle.py`, `tests/unit/test_evidence_bundle_v2.py`, `tests/unit/test_offline_harness.py`, `tests/unit/test_tier2_sensitivity.py`; diff `+30/−15` (commit pending authorization) |
| Suite (post-fix) | 233 passed, 5 skipped, 90.97 s, exit 0 |
| Static (post-fix) | ruff: 0; pyright: 0 errors, 0 warnings |
| Claim 1 (fields absent) | TRUE — the four names exist only as provenance tag keys (`src/schemas/evidence_bundle.py:210-217`, `:225`); no typed fields, no `limitations` |
| Claim 2 (harness 6 tests) | TRUE — `pytest --collect-only` returns exactly 6 |
| Claim 3 (no `tier3` config) | TRUE — no `tier3:` in `params.yaml`; `langgraph` and `pydantic-ai` not installed |
| Docs state | ADR-016 reserved with no body (`system_design.md:171`, `:254`); duplicate `Data Scientist Agent` / `Financial/Domain Analyst Agent` rows at `:100-101`; Phase 4 row `:31` reads "Not started" |
| Approvals | D4-01…D4-09 approved; SDD and execution plan approved; Q-1(`b`), Q-2, Q-3, Q-4 resolved (`spec.md` §7); implementation authorization: Stage 0 only (2026-11-03) |
| Gates | R-A closed; R-B open (R-15 GX mutation, DVC remote provisioning) — non-blocking for the decoupled Tier 3 build |
| Providers | `gemini-2.5-flash` / `openai/gpt-oss-20b` pinned; cost rates present (A-03, rate dates 2026-10-23 / 2026-10-12); live smoke opt-in (`tests/integration/test_gateway_resilience.py:799`); no credential patterns in tracked files |
| Dependency | `langgraph==1.2.19` resolves on Python 3.12.10 (dry-run; no lockfile write). It pulls `langgraph-sdk` and `langsmith` (network-capable, inert unless configured; excluded from serving by `uv sync --no-default-groups`). `pydantic-ai` absent |
| Concurrency | 3 sibling nodes × 0.4 s in a throwaway venv outside the repo: sync `invoke` 0.407 s, async `ainvoke` 0.404 s → concurrent. `ainvoke` + `asyncio.to_thread` **not required**; gateway unchanged |
| Q-1 pre-registration | Arithmetic table and owner-selected criterion frozen from `spec.md` §7; Stage 2 may not retro-fit a criterion |

**Baseline defect note.** Static checks were red at the starting commit (Wave B/C hygiene debt). The fix is recorded as a Stage 0 item; no behavior, schema, or dependency changed.

