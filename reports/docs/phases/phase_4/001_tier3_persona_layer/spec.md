# Feature Specification — 001 Tier 3 Persona Layer

**Status:** ✅ **APPROVED — 2026-11-02**; clarification gate closed 2026-11-03 (Q-1 `b`, Q-2/Q-3/Q-4 resolved, §7); Stage 0 complete; Stage 1 complete 2026-11-03 (**Gate 1 passed**, ADR-016 accepted). Implementation authorization separate.

**Authority:** `../implementation_plan.md` (D4-01…D4-09 approved/acknowledged 2026-11-02), PRD FR6–FR9, `invariants.md` (INV-1/2/4/5/6/8/9/10), ADR-002/004/005/006/009/014/033/034, `../../pre-phase_4_remediation/tier3_contracts.md`, `../../pre-phase_4_remediation/evidence_bundle_v2_contract.md`, `../../architecture/tier3_persona_architecture.md`.

**Execution:** `../execution_plan.md` (phase-level sequence and gates). This spec controls feature-level contracts, design, and tasks. Neither replaces the other.

---

## 1. Purpose and boundaries

Deliver the Tier 3 interpretation layer over the Phase 3 gateway: complete the evidence contract personas read from, run three isolated persona workers, compute divergence and escalation deterministically, and assemble one bounded, auditable report plus an in-memory trace.

**In scope:** the four capability groups P4-01…P4-04 in the implementation plan §4.

**Out of scope (hard):**

- Tier 1 retrain, recalibration, feature-policy change, or promotion-gate change (Gate R-B, owner).
- Tier 2 engine or parameter behavior change.
- Divergence threshold **calibration**, statistical accuracy claims, or golden-set evaluation (Phase 5).
- Qualitative LLM-judge grounding, LLM narrative synthesis, or any additional LLM call beyond the three personas (+ bounded repairs).
- Durable trace storage, dashboards, or Tier 3 serving promotion (FR13, Phase 5/6).
- Provider or model changes; gateway behavior changes (Phase 3 is closed).

## 2. Functional requirements

### 2.1 Evidence contract (FR6, INV-1/2, D4-01)

- **T3-FR-01** — `EvidenceBundle` v2 gains four optional typed fields: `covenant_flags: list[str] | None`, `revenue_growth_rate: float | None`, `pipeline_value_estimate: float | None`, `concentration_flag: bool | None`. An absent source yields `None`; it is never `0.0`, `[]`, or `False`.
- **T3-FR-02** — Each field's value is consistent with its `provenance` tag: `synthetic` requires a matching `synthetic_assumptions` entry; `derived` requires a derivation defined in the v2 contract. No fixture or caller may tag a field `derived` without one.
- **T3-FR-03** — `PersonaVerdict` gains `limitations: list[str]` (default empty) so a persona can surface missing or unverifiable evidence.
- **T3-FR-04** — `schema_version` stays `v2`; `p90_pd` remains computed by reference to `pd_band.p90`; v1 validation and Tier 1/Tier 2 behavior are unchanged.

### 2.2 Persona workers (FR6, INV-5/6/8, D4-04/07/08)

- **T3-FR-05** — Exactly three persona roles: `cro`, `growth`, `capital`. Each is built only from the shared `EvidenceBundle` plus its own rubric — never another persona's prompt, output, verdict, or the raw gathering trace.
- **T3-FR-06** — Every model call goes through `GatewayService.complete` with `json_mode=True`, `temperature=0.0`, and the configured per-persona token bound. No provider SDK is imported in `src/agents/`.
- **T3-FR-07** — Each persona output must validate as `PersonaVerdict`. A schema-invalid output triggers at most **one** bounded repair re-ask through the gateway; a second failure marks that persona failed (incomplete), never coerced, defaulted, or dropped.
- **T3-FR-08** — Rubric fields: CRO reads `p90_pd` + `covenant_flags`; Growth reads `revenue_growth_rate` + `pipeline_value_estimate`; Capital reads `concentration_flag` + `p90_pd`/`credit_rating`. A persona whose required field is `None` must record a `limitations` entry and may lower `confidence`; it must not invent a value.
- **T3-FR-09** — Prompts ship an explicit `lean` anchor rubric (the approved anchor table in `plan.md` §3.5) so `lean` is anchored, not free-floating. `recommendation` uses the canonical `approve` / `conditional` / `reject` literals only.

### 2.3 Convergence and escalation (FR7/FR8, INV-4/9/10, D4-02/03)

- **T3-FR-10** — Divergence is a pure deterministic function of the three verdicts' `recommendation`, `lean`, and `confidence`, using the approved confidence-weighted mean of pairwise distances. It is bounded `[0,1]`, permutation-invariant, and returns `1.0` when total pair weight is zero (fail-safe, not agreement).
- **T3-FR-11** — No LLM judge participates in divergence, escalation, or report assembly.
- **T3-FR-12** — Both Tier 1 confidence proxies are implemented as pure functions of Tier 1/Tier 2 outputs only: (A) band dispersion, (B) rating-boundary margin. Phase 4 selects one by the approved bounded check; the other remains implemented and documented.
- **T3-FR-13** — Escalation returns exactly one of `success`, `escalate`, `incomplete` with machine-readable reason codes, per the table in §4.
- **T3-FR-14** — No path implies approval. `escalate` and `incomplete` always carry a human-review flag; the system remains decision-support only.

### 2.4 Report and trace (FR9, D4-05/06/07)

- **T3-FR-15** — The report is assembled by a deterministic template over typed bundle fields, verdicts, and the convergence result. Every number originates from a typed field; persona rationale is quoted verbatim and attributed. No extra LLM call.
- **T3-FR-16** — `incomplete` produces **no report**, only an outcome carrying the failure reasons. There is no partial or averaged report.
- **T3-FR-17** — `Tier3Trace` is returned in memory with: correlation id, per-persona attempt records (provider, latency, usage, cost, repair used), gateway provider events, divergence inputs/output, confidence proxy used + value, escalation outcome + reasons.
- **T3-FR-18** — One report is bounded to ≤6 gateway calls (3 personas + ≤1 repair each), `max_tokens_per_persona: 1024`, `report_timeout_s: 60`, `cost_cap_usd_per_report: 0.05`. Breaching a bound yields `incomplete`; it never yields a partial report.

## 3. Contracts

```text
EvidenceBundle (v2, additive — no version bump)
  covenant_flags: list[str] | None = None
  revenue_growth_rate: float | None = None
  pipeline_value_estimate: float | None = None
  concentration_flag: bool | None = None

PersonaVerdict
  limitations: list[str] = Field(default_factory=list)
```

```text
params.yaml  tier3:                       # provisional; Phase 5 calibrates
  divergence_threshold: 0.50
  tier1_confidence_threshold: 0.30
  tier1_confidence_proxy: <selected at Stage 2>
  band_dispersion_ref: 2.0                # normalizer for proxy A (see Q-1)
  max_tokens_per_persona: 1024
  max_gateway_calls_per_report: 6
  report_timeout_s: 60.0
  cost_cap_usd_per_report: 0.05
  calibration: provisional-phase5
```

Outcome contract (shape, not field-by-field): `Tier3Outcome(status, reasons, report, trace)`; `report is None` whenever `status == "incomplete"`.

## 4. Failure and escalation table

| Condition | Outcome | Report | HITL |
| --- | --- | --- | --- |
| 3 valid verdicts, divergence < threshold, Tier 1 confidence ≥ threshold | `success` | yes | no |
| divergence ≥ threshold | `escalate` | yes, flagged | yes |
| Tier 1 confidence < threshold | `escalate` | yes, flagged | yes |
| any persona served by the fallback provider | `escalate` (provisional, fail-safe) | yes, flagged | yes |
| persona invalid after one repair | `incomplete` | **no** | yes |
| gateway failure / timeout for any persona | `incomplete` | **no** | yes |
| call, token, time, or cost bound exceeded | `incomplete` | **no** | yes |
| cost reported as unknown by the gateway | `escalate` + `cost_unknown` trace flag (Q-2) | yes, flagged | yes |

## 5. Non-functional requirements

Deterministic and reproducible under fixed settings; fully offline-verifiable in CI (no network, no credentials); one new dependency group (`tier3`) excluded from the serving image; no new telemetry platform; no secrets in source, fixtures, prompts, or logs; auditability of every control path via the trace.

## 6. Acceptance criteria

1. Contract fields validate, `None` is preserved, `limitations` round-trips, v1 and Tier 1/Tier 2 behavior unchanged.
2. Three isolated parallel persona invocations share the bundle and never each other's context; temperature uniform; one repair maximum.
3. Divergence is deterministic, permutation-invariant, bounded, and monotone in lean spread; zero-weight fail-safe is `1.0`.
4. Every escalation-table row is covered by a test; no row yields an implicit approval.
5. Happy path produces a coherent report; engineered divergence escalates; a failed persona produces no report.
6. Every report number traces to a typed field; trace contains provider, usage, cost, divergence, and outcome evidence.
7. Full `pytest`, `ruff`, and `pyright` pass; the offline harness covers converge, diverge, and incomplete.

## 7. Clarification gate (resolve before implementation authorization)

**Q-1 — BLOCKING: the approved Tier 1-confidence qualification check cannot pass on the current seed set.**

Arithmetic over the recorded fixtures (`params.yaml` rating thresholds; proxy A normalized with `ref = 2.0`; proxy B = bucket-relative distance to the nearest rating boundary):

| Case | pd | p10/p50/p90 | Proxy A | Proxy B | Plan role |
| --- | --- | --- | --- | --- | --- |
| SC-01 | 0.015 | 0.010/0.015/0.025 | 0.500 | **0.000** (pd on the 0.015 boundary) | converge / happy path |
| SC-02 | 0.045 | 0.030/0.045/0.080 | 0.444 | 0.286 | diverge |
| SC-03 | 0.025 | 0.015/0.025/0.045 | 0.400 | 0.571 | diverge |
| SC-04 | 0.065 | 0.045/0.065/0.100 | 0.577 | 0.300 | incomplete (persona-level) |

- Proxy A cannot separate SC-04 from SC-01 for **any** `ref`: SC-04's relative band width (0.846) is smaller than SC-01's (1.000), so A always scores SC-04 ≥ SC-01.
- Proxy B flags SC-01 (margin exactly 0) and also flags SC-02, so no `success` case remains.
- SC-04's designed role is a **persona-level** incomplete case, not a low-Tier-1-confidence case; using it as the low-confidence reference conflates two different failures.
- Separately, SC-01 is internally incoherent: `pd = 0.015` maps to `BBB` under `rating_thresholds`, but the fixture asserts `credit_rating = "AAA"`.

**Recommended resolution (b):** repair the seed set within the approved 3–5 case budget — make SC-01 a coherent high-confidence case (consistent `credit_rating`/`pd`/band), and add **SC-05** as the genuine low-Tier-1-confidence case (near-boundary `pd`, wide band). Run the approved check against SC-05 instead of SC-04. This preserves the evidence-based selection and fixes the incoherence, at the cost of two fixture edits the owner must approve.

**Fallback (a):** no fixture edits; select proxy B on construct validity (it measures decision stability, which is what FR8 means by Tier 1 confidence), verify both directions on constructed test inputs rather than fixtures, and record that the seed set cannot evidence Tier 1 separation.

**Selected (recommended b):** fixture repair + SC-05, proxy B selected, thresholds provisional. **Rejected option preserved (a):** construct-validity selection, no fixture edits, seed inconclusive — available if owner declines edits. **Owner confirmation required before Stage 2 starts; authorization separate.**

**Q-1 — RESOLVED (recommended b; a retained as fallback).** Repair seed set within 3–5 budget: SC-01 coherent (rating/PD/band consistent), SC-04 label corrected, add SC-05 as genuine low-confidence case near boundary; select proxy against SC-05 (proxy B construct-valid; proxy A structurally inverted for any `ref`). Rejected option (a) preserved: construct-validity selection with constructed inputs, no fixture edits, seed set inconclusive.

**Q-2 — RESOLVED (recommended fail-safe).** `cost_unknown` in trace → escalate to HITL; never $0. Keeps D4-07 cap meaningful. Rejected option preserved: assume unknown = $0.

**Q-3 — RESOLVED (recommended).** Populate fields from evidence/synthetic with `synthetic_assumptions`; fix `derived` tags (`revenue_growth_rate`, `concentration_flag`) to defined derivations; no verdict/ratio rewrite; SC-05 added if Q-1(b). Fallback preserved: partial population, document gaps.

**Q-4 — APPROVED (recommended).** Lean anchor table (`±1.0/±0.5/0.0`) approved from `plan.md` §3.5; part of prompt semantics. Alternative (no anchor, free-floating `lean`) rejected.

**Record-only (no owner input needed):** `incomplete` → `report=None` (INV-9); ADR-016 (v2 additive, supersedes `system_design.md` §7 version-bump note).

## 8. Definition of done

Every functional requirement above is implemented and evidenced by a passing test at the stage named in `../execution_plan.md`; the clarification gate is closed; the full suite, Ruff, and Pyright pass; the Post-Implementation Review rows for P4-01…P4-04 are completed with actual results; ADR-016 is accepted and consolidated.
