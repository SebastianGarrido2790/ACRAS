# Tasks — 001 Tier 3 Persona Layer

**Status:** 🟡 **DRAFT — awaiting package approval.** No task is executable until the owner approves `spec.md`, `plan.md`, this task list, and `../execution_plan.md`, and explicitly authorizes implementation.

Execution order and per-stage hard gates are controlled by `../execution_plan.md`. A task may span a stage boundary only where the execution plan says so; no task starts before its stage's predecessor gate passes.

- [ ] **T3-T01 — Baseline and dependency verification.** Re-run the suite and static checks; record the starting commit; confirm the `tier3` group resolves and stays out of the serving image; verify LangGraph branch-concurrency semantics and the gateway's synchronous call path; confirm the Q-1 disposition. *Stage 0. Satisfies: precondition set (no FR).*
- [ ] **T3-T02 — Complete the evidence contract.** Add the four optional `EvidenceBundle` fields and `PersonaVerdict.limitations`; keep `v2`. *Stage 1. T3-FR-01/03/04.*
- [ ] **T3-T03 — Enforce provenance/derivation consistency.** Reject `derived` tags without a defined derivation; require `synthetic_assumptions` for synthetic values; add contract tests. *Stage 1. T3-FR-02.*
- [ ] **T3-T04 — Repair and populate seed cases.** Resolve SC-01 incoherence and SC-04 role labelling (per approved Q-1/Q-3); populate the four fields with evidenced or tagged-synthetic values; record the mapping table. *Stage 1. T3-FR-01/02.*
- [ ] **T3-T05 — File ADR-016.** Record the additive v2 change, the `limitations` field, the excluded loss fields, and the supersession of the `system_design.md` §7 version-bump expectation; submit for owner acceptance. *Stage 1. T3-FR-01/03/04.*
- [ ] **T3-T06 — Implement divergence.** Pure confidence-weighted pairwise distance with the zero-weight fail-safe; property tests for range, permutation, symmetry, monotonicity, and threshold boundary. *Stage 2. T3-FR-10/11.*
- [ ] **T3-T07 — Implement both Tier 1 confidence proxies.** Band dispersion and rating-boundary margin, pure and bounded; analytic edge tests including `p50 = 0` and out-of-range `pd`. *Stage 2. T3-FR-12.*
- [ ] **T3-T08 — Select the proxy by the approved check.** Run the bounded comparison on the seed cases, record actual values and the selection, and update `tier3.tier1_confidence_proxy`. *Stage 2. T3-FR-12 (blocked by Q-1 if unresolved).*
- [ ] **T3-T09 — Implement escalation.** Truth table returning `success`/`escalate`/`incomplete` with stable reason codes and fixed precedence; exhaustive row tests; assert no implicit approval. *Stage 2. T3-FR-13/14.*
- [ ] **T3-T10 — Build persona prompts and lean anchors.** One module per persona plus the shared deterministic digest; implement the approved lean anchor table; no cross-persona inputs. *Stage 3. T3-FR-05/09.*
- [ ] **T3-T11 — Implement the persona worker.** Gateway request (json mode, temperature 0.0, token bound), verdict validation, exactly one repair re-ask, typed result and attempt metadata. *Stage 3. T3-FR-06/07.*
- [ ] **T3-T12 — Prove isolation and rubric honesty.** Test that no persona request contains another persona's content; test missing-field `limitations`; correct the `system_design.md` §3 analyst rows to the three-persona boundary. *Stage 3. T3-FR-05/08.*
- [ ] **T3-T13 — Implement the graph.** Static LangGraph fan-out → join → convergence → report with a typed state and the verified concurrency mechanism. *Stage 4. T3-FR-05/10/13.*
- [ ] **T3-T14 — Implement the report template.** Deterministic Markdown + structured model; every number bound to a typed field; rationale verbatim and attributed; no LLM call. *Stage 4. T3-FR-15/16.*
- [ ] **T3-T15 — Implement the trace and bounds.** In-memory `Tier3Trace`; enforce call/token/time/cost bounds; incomplete outcomes carry reasons and no report. *Stage 4. T3-FR-17/18.*
- [ ] **T3-T16 — Extend the offline harness and prove exit criteria.** Drive the real convergence/report path from recorded fixtures; cover converge, diverge, and injected persona failure; run the full suite, Ruff, and Pyright; record evidence. *Stage 5. Exit criteria 1–7.*

## Evidence convention

Each task is closed only when its evidence is checked into the repository or recorded in the stage record: test names and results, the commands actually run, the commit or diff reference, and any deviation. A task is not "done" because the file exists.
