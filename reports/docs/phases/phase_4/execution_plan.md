# ACRAS Phase 4 — Staged Execution Plan

**Phase:** 4 — Tier 3 Multi-Agent Persona Layer
**Status:** ✅ **Stage 1 complete 2026-11-03** — Gate 0 passed; Gate 1 passed after ADR-016 acceptance. Stages 2–6 not started.
**Planning baseline:** Phase 3 closed 2026-10-19; pre-Phase-4 remediation Gate R-A items 1–4 closed; Phase 4 decisions D4-01…D4-09 approved/acknowledged 2026-11-02; baseline suite `233 passed, 5 skipped` (2026-11-01).
**Feature SDD:** `001_tier3_persona_layer/{spec,plan,tasks}.md` — one integrated SDD for P4-01…P4-04 (implementation plan §4).

---

## 1. Purpose and execution discipline

This plan translates the approved Phase 4 Implementation Plan and the integrated feature SDD into a sequential, evidence-gated execution sequence. It introduces no architectural decision. Decisions already approved are constraints to implement, not decisions to re-open.

Each stage has a hard gate. **No work in the next stage begins until the current stage's gate passes and its evidence is recorded.** A failed, partial, awaiting-approval, or undocumented stage stays open.

**Falsification policy.** Falsification is a deliberate attempt to prove that a control detects a meaningful failure. It is selective, and each stage that uses it uses a *different, targeted* fault aimed at that stage's governing assumption. Documentation and baseline stages use evidence reconciliation instead of artificial code faults. Stage 5 carries the **single independent falsification pass** over the finished artifact — one controlled mutation, introduced by a pass that did not write the code, to prove the acceptance suite is sensitive; it is reverted and never committed. Falsification is not repeated mechanically across stages.

**Authority split.** This plan controls phase-level sequence and gates. `001_tier3_persona_layer/` controls feature contracts, design, and tasks. Neither silently replaces the other.

---

## 2. Execution preconditions

All must hold before Stage 0 starts:

- [x] Phase 4 Implementation Plan approved: Batch 1 (D4-01/D4-04/D4-07) and Batch 2 (D4-02/D4-03/D4-05) approved; Batch 3 (D4-06/D4-08/D4-09) approved 2026-11-02.
- [x] Integrated SDD package (`spec.md`, `plan.md`, `tasks.md`) explicitly approved by the owner.
- [x] This execution plan explicitly approved.
- [x] **Clarification gate closed**: Q-1 resolved `b` (fixture repair + SC-05; `a` retained as fallback), Q-2/Q-3/Q-4 resolved — `001_tier3_persona_layer/spec.md` §7.
- [x] Implementation authorization granted for **Stage 0** and **Stage 1** (2026-11-03). Stages 2+ require separate authorization.
- [x] Gate R-A items 1–4 evidenced; Gate R-B items remain open and are recorded as **non-blocking** for the decoupled Tier 3 build.
- [x] Phase 3 closure evidence verified: gateway, breakers, events, and cost/usage semantics are in place; Phase 3 is not reopened.

---

## 3. Implementation Stages

### Stage 0 — Pre-Implementation Verification & Dependency Check ✅ **PASSED**

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

**Stage 0 evidence** -> [stage evidence](stages_evidence.md#stage-0--pre-implementation-verification--dependency-check) (2026-11-03 evidence preserved; no production behavior changed).

**Gate 0 — Baseline accepted.** Starting commit, exact test/static-check results, and a clean post-suite status are recorded; approvals and the Q-1 disposition are recorded; the dependency pin and branch-concurrency mechanism are documented; no production behavior has changed.

---

### Stage 1 — Evidence Contract & Seed-Case Integrity (P4-01) ✅ **PASSED**

**Goal.** Make the evidence the personas are required to read actually present, typed, and internally consistent, without changing the schema version or any Tier 1/Tier 2 behavior.

**Actions**

1. Add `covenant_flags`, `revenue_growth_rate`, `pipeline_value_estimate`, `concentration_flag` as optional fields on `EvidenceBundle`, and `limitations` on `PersonaVerdict` (`default_factory=list`). Keep `extra="forbid", frozen=True`, keep `schema_version` at `v2`, keep `p90_pd` computed.
2. Add the narrow provenance rules from `plan.md` §2: `synthetic` requires a tagged assumption; `derived` is limited to defined derivations (`financial_ratios`, `p90_pd`).
3. Contract tests: valid parse; `None` preserved and provably distinct from `0.0`/`False`/`[]`; `limitations` round-trip; unknown fields still rejected; v1 contract and `p90_pd` equality unchanged.
4. Apply the approved Q-1/Q-3 seed-case decisions: repair SC-01's rating/PD/band incoherence and SC-04's role label, or add SC-05, exactly as approved. Populate the four fields from evidenced values or explicit tagged-synthetic values. Record the field-by-field mapping table. Do **not** rewrite verdicts or financial ratios.
5. Add a fixture-integrity test: `credit_rating` equals the deterministic mapping of `pd`; every `derived` tag has a defined derivation; every `synthetic` tag has an assumption entry.
6. Write ADR-016 into `system_design.md` §6 (additive v2 change, `limitations`, excluded loss fields, supersession of the §7 version-bump note) and submit it for owner acceptance.
7. Record the P4-01 Post-Implementation Review row with actual evidence.

**Inputs / dependencies.** Stage 0 gate; approved Q-1/Q-3; `evidence_bundle_v2_contract.md`; fixtures.

**ADR Implements.** **ADR-016** (new, accepted at this stage).

**Falsification.** Temporarily set a new field's default to `0.0` (the exact failure D-01 forbids) and confirm the null-preservation test fails; restore and re-run green.

**Stage 1 evidence** → [stage evidence](stages_evidence.md#stage-1--evidence-contract--seed-case-integrity-p4-01) (contract, mapping table, repairs, falsification, verification). 

**Gate 1 — Contract complete and seed cases coherent.** All contract tests pass; `None` is preserved; seed cases validate and are internally consistent; ADR-016 is accepted; v1 and Tier 1/Tier 2 behavior are unchanged.

---

### Stage 2 — Deterministic Convergence Core (P4-03)

**Goal.** Establish divergence, Tier 1 confidence, and escalation as pure, exhaustively tested functions before any live persona call exists.

**Actions**

1. Add `Tier3Config` to `src/config/loader.py` and the `tier3:` block to `params.yaml` (`spec.md` §3), with explicit bounds and `calibration: provisional-phase5`.
2. Implement `divergence.py` per `plan.md` §3.1, including the zero-total-weight fail-safe and `>=` threshold semantics.
3. Implement `tier1_confidence.py` with both proxies, the completed normalizers from `plan.md` §3.2, and their edge cases (`p50 <= 0`, out-of-range `pd`, boundary, bucket center).
4. Run the bounded proxy comparison on the seed cases; record the actual values in a table; apply the owner-approved selection criterion; update `tier3.tier1_confidence_proxy`. If the criterion cannot be satisfied, **stop and return to D4-03** — do not adjust fixtures or thresholds to manufacture a pass.
5. Implement `escalation.py`: fixed precedence (`incomplete` > `escalate` > `success`), stable reason codes, fallback-provenance escalation, and no implicit approval.
6. Tests: property tests (range, permutation invariance, symmetry, monotonicity in lean spread, zero-weight fail-safe), the exhaustive recommendation-distance table, threshold boundary, every escalation row, and an import-boundary test asserting the module has no gateway, network, or LLM dependency.

**Inputs / dependencies.** Stage 1 gate; approved Q-1 criterion; recorded fixtures.

**ADR Implements.** None new. Implements ADR-004's mechanism under D4-02/D4-03.

**Falsification.** Flip the zero-weight fail-safe to `0.0` and invert one `lean` sign in the formula; confirm the property tests fail; restore and re-run green.

**Gate 2 — Convergence is deterministic and provable.** Divergence and both proxies pass property and edge tests; the selected proxy and its evidence are recorded under the approved criterion; every escalation row is covered; no path implies approval; the pure modules have no I/O dependency.

---

### Stage 3 — Persona Workers & Context Isolation (P4-02)

**Goal.** Make three genuinely independent persona calls over the shared bundle and prove isolation as a structural fact.

**Actions**

1. Implement `prompts/digest.py`: a deterministic, persona-neutral rendering of typed bundle fields, with missing values rendered as an explicit "not available" marker.
2. Implement one prompt module per persona (`cro.py`, `growth.py`, `capital.py`) with its rubric fields, role framing, and the approved lean anchor table. No module accepts another persona's output.
3. Implement `persona_worker.py`: `GatewayRequest` with `json_mode=True`, `temperature=0.0`, configured token bound; `GatewayService.complete`; `with_bounded_repair(..., max_repairs=1)`; typed result with failure reason and attempt metadata; one-line schema mismatch note on re-ask without echoing invalid output.
4. Tests with a fake gateway only: request shape, success, one-repair recovery, double failure → incomplete, missing-field `limitations`, uniform temperature, and no direct provider SDK import under `src/agents/`.
5. Isolation test: inspect each outbound request and fail if any other persona key, verdict, or rationale appears. Also assert the digest is identical across personas apart from the rubric section.
6. Correct `system_design.md` §3: remove the duplicate Data Scientist / Financial Analyst rows; only the three persona LLM nodes remain. Record the diff.
7. Record the P4-02 Post-Implementation Review row.

**Inputs / dependencies.** Stage 1 gate; Stage 2 gate (for the verdict contract); Phase 3 `GatewayService`; approved lean anchors (Q-4).

**ADR Implements.** None new. Implements INV-5/INV-8 and D4-08.

**Falsification.** Inject another persona's rationale into one persona's prompt payload and confirm the isolation test fails; remove the injection. Separately, return invalid JSON twice and confirm the worker reports failure rather than coercing a verdict.

**Gate 3 — Personas are isolated and bounded.** Three validated isolated calls are demonstrated; one repair maximum is proven; temperature is uniform; no cross-persona content appears in any request; the architecture data flow matches the implemented boundary.

---

### Stage 4 — Orchestration, Report & Trace (P4-04)

**Goal.** Join the approved pieces into one bounded execution that produces either an auditable report with a complete trace, or an explicit incomplete outcome.

**Actions**

1. Implement the typed graph state and `graph.py`: static fan-out → join → convergence → report, using the concurrency mechanism verified at Stage 0.
2. Implement `trace.py`: correlation id, per-persona attempts (provider, latency, usage, cost, repair used), gateway provider events, divergence inputs/output, proxy used and value, outcome and reason codes.
3. Implement `report.py`: deterministic Markdown + structured model; every number bound to a typed field; rationale verbatim and attributed; `limitations` listed; no LLM call.
4. Enforce the bounds: ≤6 gateway calls, per-persona token ceiling, 60 s wall clock, $0.05 cost cap; unknown cost per the approved Q-2 resolution. A breach stops the run and returns `incomplete`.
5. Tests with a fake gateway: converge → `success` + report; diverge → `escalate` + flagged report; missing/failed persona → `incomplete` + `report is None`; numeric traceability; trace completeness; exactly three LLM nodes; no peer context in the graph state.
6. Record the P4-04 Post-Implementation Review row.

**Inputs / dependencies.** Stages 2 and 3 gates.

**ADR Implements.** None new. Implements D4-04/D4-05/D4-06.

**Falsification.** Remove one persona result from the graph state and confirm the run returns `incomplete` with no report; assert no two-persona averaged report exists.

**Gate 4 — Orchestration is bounded and auditable.** All three outcomes are demonstrated end-to-end offline; every report number traces to a typed field; the trace is complete for each outcome; bounds stop rather than truncate; no incomplete path yields a report.

---

### Stage 5 — Offline Acceptance & Exit-Criteria Verification

**Goal.** Turn the phase's exit criteria and invariants into permanent, deterministic evidence, and independently test whether the suite can detect a broken control.

**Actions**

1. Extend `tests/unit/test_offline_harness.py` to drive the real divergence, escalation, and report functions from the recorded fixtures; cover converge, diverge, and an injected persona failure (the incomplete path is proven by an injected failure, not by SC-04's label).
2. Assert exit criteria explicitly: (1) happy-path report is coherent; (2) engineered divergence yields genuinely different verdicts and routes to HITL; (3) incomplete yields no report and no silent average; (4) invariant tests pass; (5) the offline harness covers all three outcomes.
3. Run the full suite, Ruff, and Pyright; record exact counts, skips, duration, and exit codes; re-check `git status --porcelain` for suite-induced mutations.
4. Verify the invariant boundaries: no persona output reaches a Tier 1/Tier 2 calculation (INV-1); one versioned bundle (INV-2); uniform temperature (INV-5); all calls through `GatewayService` (INV-6); no auto-approve and no partial report (INV-9/INV-10).
5. Inspect the dependency diff: only the approved `tier3` group; no `pydantic-ai`; serving dependency set unchanged. If a Docker daemon is available, verify the serving image build; otherwise record the skip and the reason.
6. Scan source, tests, fixtures, and logs for credentials, prompts, and borrower-sensitive data.
7. **One-time independent falsification pass.** In a scratch copy of the finished artifact, introduce exactly one controlled mutation (disable the incomplete guard, or set `divergence_threshold` to `1.1`). Confirm at least one acceptance test fails, with the expected reason. Record the mutation and the failure output, restore the original, and re-run green. Never commit the mutation.
8. Optional live smoke (`ACRAS_LIVE_GATEWAY_SMOKE=1`): run only if authorized and credential-safe; record date, provider, and outcome; it is never a gate.

**Inputs / dependencies.** Stages 1–4 gates; recorded fixtures; optional credentials for the smoke only.

**ADR Implements.** None new. This is the conformance stage.

**Falsification.** The one-time independent mutation pass described in action 7 — applied once, by this stage, and reverted.

**Gate 5 — Exit criteria evidenced.** Full suite, Ruff, and Pyright pass; all five exit criteria have evidence; the independent mutation was detected and reverted; the tree is clean; no live call is required for CI.

---

### Stage 6 — ADR Consolidation & Phase Sign-Off

**Goal.** Close the loop between decided, built, verified, and recorded before Phase 5 planning begins.

**Actions**

1. Confirm ADR-016 is present, accurate, and consistent with the implemented contract; verify the `system_design.md` §7 reserved-field note is closed and §3 lists only the three persona LLM nodes.
2. Reconcile the implementation diff against the approved plan, the SDD requirements, the invariants, and every stage gate. Any deviation without an approved change record blocks closure.
3. Complete every Post-Implementation Review row in the Phase 4 Implementation Plan with actual results, deviations, and references. No `Pending` row survives without a formally approved exception.
4. Record the empirical evidence: seed-case outcomes, divergence and confidence values, escalation decisions, run counts, and the recorded limitation that the seed set cannot establish calibration or population performance.
5. Resolve or formally accept remaining findings with an owner. Material unresolved requirements block sign-off; they cannot be relabelled non-blocking.
6. Verify all exit criteria and the recorded decisions' non-goals (no calibration claim, no durable storage, no promotion gate).
7. Confirm next-phase entry conditions: Phase 5 receives the divergence function, provisional thresholds, escalation outcomes, and the seed set; Phase 6 receives the `Tier3Trace` shape.
8. Update project architecture and status records: Phase 4 row, roadmap status, and any cross-reference made stale by the change.
9. Obtain explicit human Phase 4 sign-off.

**Inputs / dependencies.** All stage gates; PIR rows; ADR-016; stage evidence records.

**ADR Implements.** None new. Consolidates existing accepted ADRs only.

**Falsification.** Documentation-to-reality audit: trace every closure claim to a test result, diff, configuration, or recorded stage evidence. An unsupported claim fails the gate.

**Gate 6 — Phase 4 closed; Phase 5 may enter its own planning.** Every stage passed; ADRs consolidated; PIR complete; exit criteria evidenced; residual risks owned; next-phase entry conditions recorded; human sign-off granted. Phase 5 work is not authorized by this closure alone.

---

## 7. Global Execution Controls & Change Handling

1. **Sequential rule.** No later stage starts while an earlier gate is failed, partial, awaiting approval, or awaiting remediation.
2. **80% rule.** If the implementer is not at least 80% confident in a mathematical formulation, library behavior, threshold semantics, or pipeline configuration, stop and ask. Do not guess. Stage 0's concurrency spike and Stage 2's proxy arithmetic exist because of this rule.
3. **Stop-the-line.** On any unexpected failure, regression, or schema mismatch, stop, preserve evidence, diagnose the root cause, fix, verify, and only then resume. Never push past a broken test, and never weaken a test to obtain green.
4. **Change protocol.** If implementation reveals a decision that differs from the approved plan: halt the stage; record original decision, new evidence, proposed change, downstream impact, recommendation; update `implementation_plan.md`; obtain operator approval; update the SDD; resume only after the decision is locked. This applies to Q-1's resolution, the LangGraph concurrency mechanism, and any threshold or fixture change.
5. **Task-batch control.** Work only from approved `tasks.md` items. Stop after each task or approved batch, present the diff and evidence, and obtain the required approval before continuing.
6. **Secret hygiene.** No credentials in source, `params.yaml`, fixtures, prompts, logs, chat, or generated artifacts. Live runs use out-of-band environment variables.
7. **Live-provider boundary.** Routine CI makes no provider call. The live smoke is opt-in, credential-safe, and never a gate.
8. **Scope walls.** Do not change Tier 1/Tier 2 behavior, `EvidenceBundle` v1, gateway behavior, provider/model pins, promotion gates, or add calibration claims. Do not add a dependency beyond the approved `tier3` group.
9. **Cost and time bounds.** The D4-07 caps are enforced, not advisory. Exceeding a bound yields `incomplete`.

---

## 8. Acceptance Evidence Checklist

- [ ] Contract: four typed fields + `limitations` validate; `None` preserved and distinct from zero/false/empty; v1 and `p90_pd` unchanged.
- [ ] Seed cases: internally consistent (`credit_rating` matches `pd`; provenance matches value; synthetic values tagged); mapping table recorded.
- [ ] ADR-016: accepted, accurate, consolidated; §7 note closed; §3 data flow corrected.
- [ ] Divergence: deterministic, bounded, permutation-invariant, monotone in lean spread, zero-weight fail-safe `1.0`.
- [ ] Tier 1 confidence: both proxies implemented; selection recorded under the owner-approved criterion; thresholds marked provisional.
- [ ] Escalation: every table row tested; fixed precedence; no implicit approval; incomplete never produces a report.
- [ ] Personas: three isolated invocations; uniform temperature; one repair maximum; no cross-persona context; rubric fields read from the bundle.
- [ ] Report: deterministic template; every number traced to a typed field; rationale verbatim and attributed; no LLM call.
- [ ] Trace: provider events, per-persona attempts, usage/cost (or explicit unknown), divergence, proxy, and outcome recorded in memory.
- [ ] Bounds: call/token/time/cost caps enforced; breach yields `incomplete`.
- [ ] Offline harness: converge, diverge, and incomplete covered without network access.
- [ ] Quality: full `pytest`, Ruff, and Pyright green; skips explained; `git status` clean after the run.
- [ ] Dependencies: only the approved `tier3` group; serving image dependency set unchanged; `pydantic-ai` absent.
- [ ] Independent falsification: one mutation detected, recorded, reverted, and green re-verified.
- [ ] PIR: all Phase 4 rows complete; residual risks owned; exit criteria signed.

---

## 9. Summary Table & Stage Record

| Stage | Name | Primary deliverable | ADRs | Gate | Status |
| --- | --- | --- | --- | --- | --- |
| 0 | Pre-Implementation Verification & Dependency Check | Baseline, dependency pin, concurrency mechanism, Q-1 disposition | None new | Baseline accepted | ✅ Passed 2026-11-03 |
| 1 | Evidence Contract & Seed-Case Integrity | Typed fields + `limitations`, coherent seed cases | **ADR-016** | Contract complete | ✅ Passed 2026-11-03 |
| 2 | Deterministic Convergence Core | Divergence, both proxies, escalation | None new | Convergence provable | ⬜ Not started |
| 3 | Persona Workers & Context Isolation | Three isolated workers + prompts | None new | Isolation proven | ⬜ Not started |
| 4 | Orchestration, Report & Trace | Graph, report template, in-memory trace | None new | Orchestration auditable | ⬜ Not started |
| 5 | Offline Acceptance & Exit-Criteria Verification | Exit-criteria evidence + independent falsification | None new | Exit criteria evidenced | ⬜ Not started |
| 6 | ADR Consolidation & Phase Sign-Off | PIR, consolidation, sign-off | None new | Phase closed | ⬜ Not started |

| Artifact / control | Status |
| --- | --- |
| Phase 4 Implementation Plan | ✅ All decisions approved (Batch 1/2/3), 2026-11-02 |
| Integrated SDD (`001_tier3_persona_layer`) | ✅ Approved 2026-11-02 |
| This Execution Plan | ✅ Approved 2026-11-02 |
| Clarification gate (Q-1) | ✅ Closed 2026-11-03 — Q-1(`b`), Q-2, Q-3, Q-4 resolved |
| Implementation authorization | 🟡 Stage 0 and Stage 1 granted 2026-11-03; Stages 2–6 not granted |
| Stages 0–6 | 🟡 Stages 0–1 passed; 2–6 not started |

**Next gate.** Stage 2 requires explicit implementation authorization. Stage 2 selection is bound to the frozen Q-1 criterion in `spec.md` §7.

**Approval status.** Package approved 2026-11-02; clarification gate closed 2026-11-03; Stages 0 and 1 authorized and implemented. Approval of this plan does not authorize Stage 2 or later; each stage's work requires explicit, operation-scoped authorization, and Git writes remain separately authorized.
