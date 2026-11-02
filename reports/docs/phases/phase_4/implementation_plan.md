# Phase 4 — Tier 3 Multi-Agent Persona Layer · Implementation Plan & Decisions

*Status: **DRAFT — Batch 1 (D4-01, D4-04, D4-07), Batch 2 (D4-02, D4-03, D4-05), Batch 3 (D4-06, D4-08, D4-09) acknowledged (2026-11-02); Batch 3 items are record-only (one viable option each). Rejected alternatives and trade-off text preserved unedited for traceability. No implementation authorized by this document.*

*Baseline verified 2026-11-01: `233 passed, 5 skipped` (`uv run pytest -q`). Evidence base: `remediation_plan.md` §6/§9, `wave_a_return.md`, `evidence_bundle_v2_contract.md`, `tier3_contracts.md`, `tier3_persona_architecture.md`, `system_design.md` §6, `src/schemas/{evidence_bundle,persona_verdict}.py`, `src/gateway/*`, `tests/fixtures/sc_01..04`, `tests/unit/test_offline_harness.py`.*

---

## 1. Phase Context

| Item | Record |
| --- | --- |
| Objective | Build the three persona nodes, the deterministic divergence/escalation node, and bounded report assembly over the existing gateway. No Tier 1/Tier 2 behavior change. |
| Requirements | PRD FR6 (parallel personas, shared typed bundle), FR7 (convergence + quantitative divergence), FR8 (HITL on divergence / low Tier 1 confidence), FR9 (machine-readable trace). FR13 (Tier 3 promotion gate) is Phase 5. |
| Invariants | INV-1 (no LLM input to calculations), INV-2 (single versioned bundle), INV-4 (deterministic divergence over `recommendation`/`lean`/`confidence`), INV-5 (uniform low temperature), INV-6 (all calls via gateway breaker), INV-8 (CRO/Growth/Capital), INV-9 (HITL, never silent resolve), INV-10 (never auto-approve). |
| ADRs | ADR-002 (bundle), ADR-004 (deterministic divergence), ADR-005 (structural divergence), ADR-006/009/034 (gateway + fallback), ADR-033 (deterministic ratios), ADR-014/032 (schema versioning), ADR-016 (pending, §6 D4-01). |
| Constraints | 3–5-case smoke set (D-04); no statistical claim; divergence weights/threshold calibration deferred to Phase 5 (D-03); qualitative LLM-judge grounding deferred (D-06); no retrain, no feature-policy change, no promotion-gate change, no provider/model swap. |
| Entry conditions | Gate R-A 1–3 closed; v2 contract + SC fixtures + offline harness pass; gateway structured-output qualified (W-A4: 15/15 schema-valid per provider). Gate R-A 4 is this approval. |
| Exit criteria | (1) happy-path case yields a coherent end-to-end report; (2) engineered-divergence case yields genuinely different verdicts and routes to HITL; (3) incomplete/invalid persona yields no report, not a silent average; (4) invariant tests pass; (5) offline harness covers converge, diverge, incomplete. |
| Dependencies | Phase 1 (`pd`, `credit_rating`), Phase 2 (`pd_band`, `financial_ratios`), Phase 3 (`GatewayService`, events, breaker, cost/usage). |
| Downstream | Phase 5 consumes the divergence function + escalation outcomes for calibration/gates; Phase 6 owns durable trace persistence. |

---

## 2. Current State Audit

**Verified present**

- `EvidenceBundle` v2: `accounting_profile` (11 keys), `provenance`, `synthetic_assumptions`, computed `p90_pd`, v1/v2 validators, optional `persona_verdicts` (`src/schemas/evidence_bundle.py`).
- `PersonaVerdict`: `persona`, `recommendation` (`approve`/`conditional`/`reject`), `lean` ∈ [-1,1], `confidence` ∈ [0,1], `rationale` ≥10 chars (same file).
- Structured-output plumbing: `parse_persona_verdict` + `with_bounded_repair(max_repairs=1)`, tested (`tests/unit/test_persona_verdict.py`, 9 tests).
- Gateway: `GatewayService.complete(GatewayRequest) -> GatewayResult`; `json_mode`, `temperature=0.0` default, `usage`, `cost_usd`, `fallback_used`, typed `GatewayError`, `ProviderEvent`, per-provider breakers (`src/gateway/*`).
- Fixtures: SC-01..SC-04 v2 bundles with recorded verdicts; `test_offline_harness.py` 6 passing.
- 233 passed / 5 skipped baseline.

**Missing / incomplete**

| Gap | Evidence | Impact |
| --- | --- | --- |
| Four rubric fields are **tags only**, not typed bundle fields | `provenance` requires `covenant_flags`, `revenue_growth_rate`, `pipeline_value_estimate`, `concentration_flag`, but `EvidenceBundle` defines none; fixtures store values only as free-text in `synthetic_assumptions` | Personas cannot read their mandated evidence from the contract |
| `PersonaVerdict.limitations` absent | `tier3_persona_architecture.md` §5; `system_design.md` §7 "deferred to Phase 4" | Structured evidentiary gaps cannot be surfaced |
| No persona worker / prompt code | `src/agents/{orchestration,prompts,tools}` are docstring-only `__init__` files | FR6 unbuilt |
| No divergence, escalation, or convergence code | no `src/**` implementation | FR7/FR8 unbuilt |
| No report assembly or Tier 3 trace | none | FR9 unbuilt |
| No `tier3` configuration or dependency group | `params.yaml` has only `gateway`; `pyproject.toml` has no agent deps | No thresholds, call bounds, or orchestration runtime |
| Architecture data-flow still lists duplicate analyst nodes | `system_design.md` §3 table: "Data Scientist Agent" / "Financial/Domain Analyst Agent" = Planned | Conflicts with approved D-02; doc correction required at Phase 4 start |
| `system_design.md` Phase 4 row | "Not started" | Update at phase open/close per §8 protocol |

---

## 3. Phase Scope and Requirement Assessment

**In scope (bounded)**

- P4-01 evidence contract completion (typed rubric fields + `limitations`).
- P4-02 three persona workers (prompts, gateway calls, verdict validation, bounded repair).
- P4-03 deterministic divergence + escalation + HITL outcomes.
- P4-04 bounded orchestration/report assembly + in-memory trace.

**Out of scope**

- Tier 1 retrain / calibration change / freeze decision (Gate R-B, owner).
- Tier 2 engine or parameter behavior change (D-10, owner).
- Divergence weight/threshold **calibration** and statistical claims (Phase 5).
- Qualitative LLM-judge grounding (D-06 evidence-first).
- Durable trace storage / dashboard (Phase 6).
- Tier 3 promotion gate (FR13, Phase 5).

**Requirement tensions resolved or flagged**

| Tension | Resolution |
| --- | --- |
| FR9 "log a full trace" vs Roadmap Phase 6 "trace persistence" | Phase 4 returns a typed in-memory `Tier3Trace`; persistence deferred (D4-06). |
| FR8 "documented threshold" vs D-03 deferring calibration | Phase 4 ships explicit **provisional** constants marked `calibration: provisional-phase5`; no statistical claim (D4-02/D4-03). |
| FR6 labels "CFO / Capital Allocation Director" vs INV-8 | Canonical persona key stays `capital`; prose may say Capital. No schema change. |
| Architecture §5 `limitations` vs schema | Added under D4-01; ADR-016 records it. |
| D-02 duplicate analyst nodes vs data-flow text | Remove the two analyst rows in `system_design.md` §3 at Phase 4 open; only three persona LLM nodes. |

**Unstated assumption to reject:** that personas can already read their rubric fields. They cannot (§2 gap). P4-01 is a hard prerequisite for P4-02.

---

## 4. Candidate Feature Register

One integrated Phase 4 SDD spec is the recommended minimum (remediation plan §58); do not split per persona or per retry detail.

| ID | Candidate | Requirement / need | Current state | Decisions | Dependencies | Acceptance evidence | SDD depth |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `P4-01` | Tier 3 evidence contract completion | FR6, INV-2, ADR-016 | Four fields tag-only; `limitations` absent | D4-01 | A-05 v2 lock | Schema tests: typed fields validate; `None` preserved (no zero/False default); `limitations` round-trips | Integrated spec §contract (no separate feature spec) |
| `P4-02` | Persona workers (CRO/Growth/Capital) | FR6, INV-5/6/8 | Prompts/orchestration empty | D4-04, D4-07, D4-08 | P4-01, gateway | 3 isolated parallel calls; each validates `PersonaVerdict`; one repair max; temperature uniform 0.0; no cross-persona context | Integrated spec + tasks group |
| `P4-03` | Deterministic divergence, escalation, HITL | FR7/8, INV-4/9/10 | None | D4-02, D4-03 | P4-02 | Property tests: permutation invariance, bounded [0,1], monotone in lean spread; every truth-table row tested; no auto-approve | Integrated spec + tasks group |
| `P4-04` | Orchestration, report assembly, trace | FR9, INV-2/6/10, D-06 | None | D4-04, D4-05, D4-06 | P4-02/03 | Report numbers trace to bundle fields; incomplete → no report; trace includes provider events, usage/cost, divergence, decision | Integrated spec + tasks group |

**Dispositions:** all four **Accepted (pending this approval)**. No feature is deferred or rejected. Candidate boundaries are cohesive; no separate feature for prompts, retries, or logging.

---

## 5. Decision Log Summary

| ID | Title | Scope / impact | Approval required | Status | Remarks |
| --- | --- | --- | --- | --- | --- |
| D4-01 | Tier 3 evidence fields + `PersonaVerdict.limitations` | Canonical bundle/verdict contract; ADR-016 | **Yes** | ✅ **Approved** | Batch 1, per owner request 2026-11-02. Rejected alternatives preserved. |
| D4-02 | Divergence function structure + provisional constants | FR7, INV-4; Phase 5 calibrates numbers | **Yes** | ✅ **Approved** | Batch 2, per owner request 2026-11-02. Rejected alternatives preserved. |
| D4-03 | Tier 1 confidence proxy + escalation truth table | FR8, INV-9 | **Yes** (proxy decided by bounded test) | ✅ **Approved** | Batch 2, per owner request 2026-11-02. Rejected alternatives preserved. |
| D4-04 | Orchestration framework and dependency surface | D-05 instantiation; `pyproject.toml` | **Yes** | ✅ **Approved** | Batch 1, per owner request 2026-11-02. Rejected alternatives preserved. |
| D4-05 | Report assembly: deterministic template vs LLM narrative | FR9, D-06 | **Yes** | ✅ **Approved** | Batch 2, per owner request 2026-11-02. Rejected alternatives preserved. |
| D4-06 | Trace artifact scope in Phase 4 | FR9 vs Phase 6 boundary | No — one viable option | ✅ **Acknowledged (Batch 3)** | Record-only; one viable option exists. |
| D4-07 | Per-report call/token/time/cost bounds | INV-6, bounded execution | **Yes** (cost ceiling) | ✅ **Approved** | Batch 1, per owner request 2026-11-02. Rejected alternatives preserved. |
| D4-08 | Prompt packaging + context isolation | INV-5/8, architecture §7 | No — one viable option | ✅ **Acknowledged (Batch 3)** | Record-only; one viable option exists. |
| D4-09 | Offline verification strategy | D-04, D-06 | No — one viable option | ✅ **Acknowledged (Batch 3)** | Record-only; one viable option exists. |

**Acknowledged batches:** Batch 1 (D4-01, D4-04, D4-07) ✅ approved; Batch 2 (D4-02, D4-03, D4-05) ✅ approved; Batch 3 (D4-06, D4-08, D4-09) ✅ acknowledged.

---

## 6. Decisions

### D4-01 — Complete the Tier 3 evidence contract ✅ **APPROVED (Batch 1, 2026-11-02)**

**Question.** How do personas receive the four rubric fields the locked v2 contract already names, and where does `limitations` live?

**Context.** `evidence_bundle_v2_contract.md` §3 specifies `covenant_flags` (`list[str]|None`), `revenue_growth_rate` (`float|None`), `pipeline_value_estimate` (`float|None`), `concentration_flag` (`bool|None`). `EvidenceBundle` implements none; only `provenance` tags exist. Fixtures encode the values as prose. `PersonaVerdict.limitations` is specified in the architecture and deferred to Phase 4.

**Governing.** INV-2 (single schema, no ad hoc context), D-01 (no silent zero/default), A-05 v2 lock, ADR-014 (versioning), ADR-016 note (`system_design.md` §7).

**Options.**
- **A.** Add the four optional typed fields to `EvidenceBundle` v2 and add `limitations: list[str] = []` to `PersonaVerdict`; file ADR-016. No version bump: additions are optional and backward compatible (`extra="forbid"` unaffected; existing fixtures validate with `None`).
- **B.** Bump to `v3` for the additions.
- **C.** Pass the values as prompt-only context or a separate `Tier3Context` model.

**Trade-offs.** A matches the already-locked contract, keeps one schema, and adds no migration. B adds version churn with no semantic change (no existing field changes meaning). C violates INV-2/ADR-002 and reintroduces ad hoc context.

**Recommendation.** **A.** Implementation must preserve `None` (never default to `0.0`/`False`), keep `p90_pd` computed, and validate `limitations` as strings.

**Approval.** Owner: yes (canonical contract change). **Status.** ✅ **Approved 2026-11-02** (Batch 1).

**Consequences.** ADR-016 filed at approval; `system_design.md` §7 deferred-field note closed; P4-02 may consume `bundle.<field>` directly. Any future field addition still follows ADR-014.

---

### D4-02 — Divergence function structure ✅ **APPROVED (Batch 2, 2026-11-02)**

**Question.** Which deterministic function over `recommendation`, `lean`, and `confidence` computes divergence, given INV-4 and deferred calibration?

**Context.** INV-4 fixes the fields and forbids an LLM judge; ADR-004 fixes the mechanism, not the formula or number. No implementation exists. The fixtures give recorded verdicts for converge, diverge, and incomplete cases.

**Governing.** INV-4, ADR-004, D-03 (formula direction approved; weights/threshold evidence-gated), D-04 (no statistical claim).

**Options.**
- **A.** Weighted blend with persona-specific weights.
- **B.** Confidence-weighted mean of pairwise distances: `rec_distance` ∈ {0, 0.5, 1} (equal / one conditional / approve-vs-reject), `lean_distance = |lean_i − lean_j| / 2`, `pair_distance = 0.5·rec + 0.5·lean`, `pair_weight = (confidence_i + confidence_j)/2`, `divergence = Σ(w·d)/Σw`, and `divergence = 1.0` if `Σw = 0` (fail-safe: zero persona confidence is unknown, not agreement). Range [0,1]; permutation invariant; monotone in lean spread.
- **C.** Unresolved: compare A/B on SC-01..04 before selecting.

**Trade-offs.** A introduces unjustified persona weights and breaks permutation symmetry. B uses all three required fields, is closed-form, testable, and has no arbitrary per-persona authority. C adds a decision cycle for a formula whose shape is not empirically contested; the contested part is the threshold, not the distance.

**Recommendation.** **B**, with `divergence_threshold: 0.50` as an explicit **provisional** constant in `params.yaml` marked `calibration: provisional-phase5`. Phase 5 owns calibration; no accuracy claim in Phase 4.

**Approval.** Owner: yes (formula + provisional constant). **Status.** ✅ **Approved (Batch 2, 2026-11-02)**.

**Consequences.** Pure function, no I/O, unit/property tests (permutation invariance, bounds, monotonicity, zero-weight fail-safe = 1.0). Threshold changes are a Phase 5 calibration act, not a code refactor.

---

### D4-03 — Tier 1 confidence proxy and escalation truth table ✅ **APPROVED (Batch 2, 2026-11-02)**

**Question.** What deterministic Tier 1 confidence measure feeds FR8/INV-9, and how does escalation combine it with divergence?

**Context.** FR8/INV-9 require a documented threshold; D-03 leaves the proxy evidence-first. `pd_band` and `pd` are available. No proxy exists.

**Governing.** FR8, INV-9, INV-10, D-03, `tier3_contracts.md` §2.

**Options.**
- **A.** Band dispersion: `confidence = 1 − min(1, ((p90 − p10)/p50) / ref)` (high dispersion → low confidence).
- **B.** Rating margin: normalized distance from `pd` to the nearest `rating_thresholds` boundary (near a boundary → low confidence).
- **C.** Unresolved: implement both pure functions, run a bounded check on SC-01..04, select the proxy that separates SC-04 without flagging SC-01; record result; owner confirms.

**Trade-offs.** A measures scenario dispersion, not decision stability. B measures how close the rating is to flipping — closer to "confidence in the Tier 1 output". Both are cheap. A single fixture set cannot prove either; the check only falsifies a proxy that fails to separate, it does not validate population behavior.

**Recommendation.** **C** (bounded, consistent with D-03 "evidence first"). Ship both functions; default to the proxy the check selects; keep the other as a documented alternative. Provisional `tier1_confidence_threshold: 0.30`.

**Escalation outcomes (fixed direction, `tier3_contracts.md` §2):**
- `incomplete` — any persona missing/invalid after one repair → no report, HITL. Never average two personas.
- `escalate` — divergence ≥ threshold **or** Tier 1 confidence < threshold; a fallback-served verdict is tagged with its provider and **provisionally escalated** (fail-safe default; D-06 leaves the exact fallback policy to evidence). Report carries the HITL flag.
- `success` — all three valid, divergence below threshold, confidence above threshold.

**Approval.** Owner: yes (proxy selection after test; thresholds provisional). **Status.** ✅ **Approved (Batch 2, 2026-11-02)**.

**Consequences.** Truth table is exhaustively tested; `escalate` never means auto-approve; `incomplete` never produces a report.

---

### D4-04 — Orchestration framework and dependency surface

**Question.** Implement the fixed 3-way fan-out + deterministic convergence with LangGraph (approved D-05 default) or plain `asyncio`?

**Context.** D-05 approved "gateway-direct LangGraph calls with Pydantic validation" after gateway qualification; W-A4 confirmed 15/15 schema-valid per provider. `src/agents/orchestration/__init__.py` names LangGraph. `pyproject.toml` has no agent dependency group; ADR-010/022 keep serving deps lean.

**Governing.** D-05, INV-6, ADR-010/022, AGENTS.md minimal-complexity rule.

**Options.**
- **A.** LangGraph, pinned in a new `tier3` dependency group (excluded from the serving image).
- **B.** Stdlib `asyncio.gather` fan-out + a plain convergence function; no new dependency; requires explicitly superseding D-05.

**Trade-offs.** A honors the approved decision and gives declarative node/edge wiring and state inspection; cost is one new dependency + transitive surface. B is smaller for a fixed 3-node fan-out and removes a dependency risk, but deviates from the approved D-05 baseline and its recorded rationale. The graph is static, so neither option changes runtime behavior.

**Recommendation.** **A** — implement the minimal graph (fan-out → join → divergence → report); do not add Pydantic AI. If dependency cost is unacceptable, B is viable only with an explicit D-05 supersession.

**Approval.** Owner: yes (new dependency). **Status.** ✅ **Approved** (Batch 1, 2026-11-02).

**Consequences.** `pyproject.toml` gains `tier3`; serving image unchanged; graph nodes are thin wrappers over `GatewayService.complete`.

**Consequences.** `pyproject.toml` gains `tier3`; serving image unchanged; graph nodes are thin wrappers over `GatewayService.complete`.

---

### D4-05 — Report assembly: deterministic template vs LLM narrative ✅ **APPROVED (Batch 2, 2026-11-02)**

**Question.** How is the executive report assembled while satisfying D-06 numeric grounding?

**Context.** D-06 requires deterministic validation of report numbers against the bundle; qualitative LLM-judge grounding is deferred. Persona `rationale` is free text.

**Governing.** FR9, D-06, INV-10, `tier3_contracts.md` §3.

**Options.**
- **A.** Deterministic template over bundle fields + verdicts + divergence: fixed sections, numbers injected from typed fields, persona rationale quoted verbatim, no extra LLM call.
- **B.** LLM narrative synthesis, then a numeric grounding validator.

**Trade-offs.** A makes every number traceable by construction, adds no cost/latency/trust surface, and keeps the report auditable. B reads more naturally but adds a call, a failure mode, and a grounding check that must be built and falsified; D-06 does not require it.

**Recommendation.** **A.** Numeric grounding is structural, not a post-hoc check. Persona prose stays attributed and unedited.

**Approval.** Owner: yes (report artifact). **Status.** ✅ **Approved (Batch 2, 2026-11-02)**.

**Consequences.** No LLM call in report assembly; template changes are presentation-only; B remains a Phase 5+ option if executive prose is required.

---

### D4-06 — Trace artifact scope in Phase 4 ✅ **ACKNOWLEDGED (Batch 3, 2026-11-02)**

**Question.** FR9 requires a full machine-readable trace; the Roadmap assigns persistence to Phase 6. What does Phase 4 produce?

**Context.** Gateway already emits versioned `ProviderEvent`s with usage/cost and redaction.

**Governing.** FR9, Roadmap Phase 4/6 boundary, ADR-034.

**Options.** **A.** Typed in-memory `Tier3Trace` returned with the report (correlation id, provider events, per-persona attempts/usage/cost, divergence inputs/output, escalation outcome). **B.** Durable storage now.

**Recommendation.** **A** — one viable option under the roadmap boundary. Persistence schema is Phase 6.

**Approval.** No approval required — only one viable option exists under the applicable constraints. **Status.** ✅ **Acknowledged (Batch 3, 2026-11-02)**.

**Consequences.** Phase 6 consumes `Tier3Trace` without re-running the pipeline; no storage dependency added.

---

### D4-07 — Per-report call, token, time, and cost bounds ✅ **APPROVED (Batch 1, 2026-11-02)**

**Question.** What bounds enforce INV-6 and bounded execution for one Tier 3 report?

**Context.** Gateway enforces exactly one primary + one fallback attempt per call and zero same-provider retries. Repairs are additional gateway calls. No Tier 3 budget exists.

**Governing.** INV-6, AGENTS.md bounded-execution rule, `tier3_contracts.md` §4, A-03 rates.

**Options.** **A.** Provisional `params.yaml tier3` caps: 3 persona calls + ≤1 repair each (≤6 gateway calls/report); `max_tokens_per_persona: 1024`; `report_timeout_s: 60`; `cost_cap_usd_per_report: 0.05`. **B.** No Tier 3 caps, rely on gateway only — non-viable (unbounded report cost/time).

**Recommendation.** **A**, marked provisional; Phase 5 tunes. Exceeding a cap yields `incomplete`/stop, never a partial silent report.

**Approval.** Owner: yes (cost ceiling). **Status.** ✅ **Approved** (Batch 1, 2026-11-02).

**Consequences.** Worst case ≈12 provider attempts/report (6 calls × 2 legs) but repair-triggered attempts are expected to be rare and are logged as a signal.

---

### D4-08 — Prompt packaging and context isolation ✅ **ACKNOWLEDGED (Batch 3, 2026-11-02)**

**Question.** Where do persona prompts live, and how is "the three personas never see each other" enforced?

**Context.** `tier3_persona_architecture.md` §7 requires isolated context; INV-5 fixes uniform temperature; INV-8 fixes role names.

**Governing.** INV-5, INV-8, architecture §7, ADR-005.

**Options.** **A.** One versioned module per persona under `src/agents/prompts/`, each assembled only from the bundle + its rubric; isolation asserted by a graph/contract test. **B.** One shared prompt parameterized by role.

**Recommendation.** **A** — one viable option; B allows cross-persona context bleed and weakens INV-5/ADR-005.

**Approval.** No approval required — only one viable option exists under the applicable constraints. **Status.** ✅ **Acknowledged (Batch 3, 2026-11-02)**.

**Consequences.** Prompts are versioned and testable; no persona sees another's prompt, output, or raw trace; all calls use `temperature=0.0`.

---

### D4-09 — Offline verification strategy ✅ **ACKNOWLEDGED (Batch 3, 2026-11-02)**

**Question.** How is divergence/convergence verified without live provider calls on every run?

**Context.** D-04 approved a 3–5-case smoke set; `test_offline_harness.py` already replays recorded verdicts; W-A4 qualified live structured output.

**Governing.** D-04, D-06, ADR-005 fixed-settings regression.

**Options.** **A.** Extend the offline harness to drive the real divergence/escalation/report functions with recorded verdicts; keep a separate opt-in live smoke. **B.** Live-only verification.

**Recommendation.** **A** — one viable option under D-04; B makes CI cost/nondeterminism unacceptable.

**Approval.** No approval required — only one viable option exists under the applicable constraints. **Status.** ✅ **Acknowledged (Batch 3, 2026-11-02)**.

**Consequences.** CI is deterministic; live smoke is opt-in and never a gate.

---

## 7. What Happens After Approval

1. **Record approvals** in §6 (`Approved <date>`) and file **ADR-016** (D4-01) if it passes the ADR threshold.
2. **Doc correction (D-02):** remove the duplicate Data Scientist / Financial Analyst rows from `system_design.md` §3; update the Phase 4 status row.
3. **Config:** add `params.yaml` `tier3:` block (D4-02/D4-03/D4-07) marked provisional; add the `tier3` dependency group (D4-04).
4. **SDD:** open one integrated `spec.md` → `plan.md` → `tasks.md` under `reports/docs/phases/phase_4/`; tasks grouped P4-01..P4-04.
5. **Implement in order:** P4-01 → P4-03 pure functions (offline) → P4-02 workers → P4-04 orchestration/report → harness extension.
6. **Validate:** full suite + invariant tests + offline harness; record results. No retrain, no gate change, no provider swap.
7. **Any material deviation** returns through change-management (`.agents/workflows/change-management.md`).

*Approval of a decision is not implementation approval for unrelated work.*

---

## 8. Post-Implementation Review & Remediation

Filled after implementation; the plan stays open until reviewed against approved decisions.

| Item | Expectation | Actual | Finding | Severity | Remediation | Status |
| --- | --- | --- | --- | --- | --- | --- |
| P4-01 contract | Four typed fields + `limitations`; `None` preserved | — | — | — | — | Pending |
| P4-02 personas | 3 isolated parallel calls; uniform temp; one repair max | — | — | — | — | Pending |
| P4-03 divergence | Deterministic, permutation-invariant, bounded; truth table covered | — | — | — | — | Pending |
| P4-04 report/trace | Numbers trace to bundle; incomplete → no report; trace complete | — | — | — | — | Pending |
| Exit criteria | Happy path + engineered divergence + incomplete + invariants | — | — | — | — | Pending |
| Docs | ADR-016 filed; D-02 data-flow corrected; status updated | — | — | — | — | Pending |

**PIR gates:** every material finding resolved, accepted, or escalated; exit criteria independently verified; no auto-approval path (INV-10); no LLM input to Tier 1/2 (INV-1).

---

## 9. Approval Request

**Batch 1 (unblock):** D4-01 (contract), D4-04 (LangGraph + dependency), D4-07 (bounds).
**Batch 2 (semantics):** D4-02 (divergence formula + provisional constant), D4-03 (confidence proxy via bounded test + thresholds), D4-05 (deterministic report).
**Batch 3 (acknowledge):** D4-06, D4-08, D4-09 (no-approval-required records).

*Not authorized by this document: any code implementation, dependency installation, threshold adoption as final, data/training change, provider/model swap, promotion-gate change, or durable trace storage.*
