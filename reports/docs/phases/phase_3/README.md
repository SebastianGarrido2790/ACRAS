# ACRAS Phase 3 — LLM Gateway & Provider Resilience

**Status:** ✅ **Closed 2026-10-19** — implementation validated through execution stages 0–8; Stage 9 closure audit, PIR, and exit-criteria evidence recorded in `implementation_plan.md` §8, §9 and §11. Human Phase 3 sign-off granted 2026-10-19.

Contents:
- `implementation_plan.md` — approved decisions (D3-01…D3-06), Post-Implementation Review, phase-closure checklist, and the Stage 9 exit-criteria audit.
- `execution_plan.md` — staged execution plan (stages 0–9) with per-stage hard gates and recorded evidence.
- `001_llm_gateway/` — `spec.md`, `plan.md`, `tasks.md` (provider-neutral contracts, adapters, configuration, events).
- `002_provider_resilience/` — `spec.md`, `plan.md`, `tasks.md` (bounded routing, failure eligibility, per-provider circuit breakers).

Implementation:
- `src/gateway/` — contracts, configuration, provider adapters, resilience policy, events, orchestration.
- `tests/unit/test_gateway_*.py`, `tests/unit/test_*_adapter.py`, `tests/unit/test_provider_resilience.py`, `tests/integration/test_gateway_resilience.py`.

Scope boundary: Phase 3 delivers gateway infrastructure only. Tier 3 personas, EvidenceBundle v2, deterministic divergence scoring, and evaluation gates remain Phase 4/5 work. Deterministic Tier 1–2 behavior and EvidenceBundle v1 are unchanged.

No credentials are stored in this repository. The live-provider smoke test is opt-in (`ACRAS_LIVE_GATEWAY_SMOKE=1`) and is not part of routine CI.
