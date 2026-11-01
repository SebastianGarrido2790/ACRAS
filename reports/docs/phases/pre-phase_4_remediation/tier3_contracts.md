# Tier 3 Contracts — Design Record (Wave B / Gate R-A item 2 pending)

*Status: design only; no code. Phase 4 planning approval required before implement.*

Governed by: D-03 / INV-4 / approved D-01–D-11 (2026-10-20).
Evidence: `tier3_persona_architecture.md` §3–§5; `remediation_plan.md` §3 (R-03); `wave_a_return.md` §6 (D-03 direction approved; confidence/threshold evidence-gated).

## 1. Divergence (INV-4 — deterministic, no LLM judge)

Formula: deterministic over `PersonaVerdict` structured fields (`recommendation`, `lean`, `confidence`). Divergence score is not finalized; weights/threshold remain evidence-gated per D-03 and Phase 5 calibration (ADR-004 fixes mechanism, not the number). No LLM judge used — consistent with INV-4.

## 2. Escalation / human-in-the-loop

Truth table (approved direction, thresholds deferred):
- Divergence above threshold → HITL.
- Low Tier 1 confidence (proxy to be defined) → HITL.
- Any persona failure / schema-invalid output / incomplete after bounded repair → HITL (never silent average).
- Fallback-served verdict near threshold → HITL policy to be confirmed with evidence.

## 3. Grounding

Deterministic numeric validation of report numbers against `EvidenceBundle` fields (INV-2 contract). Qualitative LLM-judge grounding deferred (D-06 evidence-first); not required for Phase 4 build.

## 4. Failure / repair contract
- Persona failure: no report; surface incomplete (INV-9 / INV-10).
- Schema-invalid: at most one bounded repair via gateway; then fail loudly.
- Repair budget counted against call budget (INV-6 / gateway circuit breaker).

## 5. D-02 — analyst-node removal (architecture consistency)

Data-flow / architecture docs currently describe redundant "Data Scientist Agent" (rating/ratio) steps that duplicate Tier 1 / Tier 2 outputs. Per D-02 (approved 2026-10-20):
- Remove duplicate analyst steps from `tier3_persona_architecture.md` / `system_design.md` data-flow.
- Only three persona nodes (`cro`, `growth`, `capital`) make LLM calls.
- All calculations (`ratios`, `p90_pd` reference) pass through deterministic Tier 1/2 outputs — never LLM.

## Deferrals (explicit, not omissions)

- Divergence weights / escalation threshold — deferred to Phase 5 calibration (D-03).
- Tier 1 confidence proxy — deferred until evidence defines (distance to rating threshold / relative P90 width).
- Qualitative grounding mechanism — deferred to D-06 evidence-first; deterministic numeric grounding implemented.
