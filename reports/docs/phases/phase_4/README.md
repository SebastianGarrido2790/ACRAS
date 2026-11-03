# ACRAS Phase 4 — Tier 3 Multi-Agent Persona Layer

**Status:** ✅ **APPROVED — 2026-11-02**; Stage 0 complete 2026-11-03 (baseline verified green, dependency pin and concurrency mechanism recorded). Stages 1–6 not authorized.

Contents:

- `implementation_plan.md` — approved decisions D4-01…D4-09 (Batch 1 + Batch 2 approved, Batch 3 acknowledged 2026-11-02), current-state audit, candidate register, Post-Implementation Review scaffold.
- `execution_plan.md` — staged execution (Stages 0–6) with one-line gates, tailored falsification, global controls, acceptance checklist, and stage record.
- `001_tier3_persona_layer/` — integrated feature SDD for P4-01…P4-04:
  - `spec.md` — requirements T3-FR-01…18, contracts, failure/escalation table, clarification gate (Q-1 blocking).
  - `plan.md` — module layout, divergence/proxy design, persona and graph design, test strategy, traceability.
  - `tasks.md` — T3-T01…T3-T16 mapped to stages and requirements.

Scope boundary: Phase 4 delivers the Tier 3 persona interpretation layer only — evidence-contract completion, three isolated persona workers, deterministic divergence/escalation, and one bounded report plus in-memory trace. Tier 1 retraining, Tier 2 behavior, threshold calibration and the golden set (Phase 5), durable trace storage and dashboards (Phase 6), and Tier 3 promotion remain out of scope.

Known blockers before implementation: the clarification gate in `001_tier3_persona_layer/spec.md` §7, including Q-1 (the approved Tier 1-confidence selection check cannot pass on the current seed set) and Q-3 (seed-case integrity edits). Gate R-B items remain open but are non-blocking for this decoupled Tier 3 build.

No credentials are stored in this repository; the live-provider smoke test is opt-in and never part of CI.
