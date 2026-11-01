# Gemini 2.5 Flash Lifecycle Verification (A-07 / W-A1)

*Status: bounded verification attempted; primary-source pricing page unreachable (transport error per W-A1 §6, `wave_a_return.md`). Live endpoint confirms model available. Near-term deprecation cannot be ruled out; no silent model swap permitted per ADR-034 / A-07 stop rule.*

## Verification performed (bounded, not open-ended)

- Provider endpoint: `gemini-2.5-flash` via `google/gemini-api` (primary).
- Live call: confirmed (W-A1 / W-A4); structured-output with `PersonaVerdict` validated (10–20 calls); reasoning tokens counted once (not double-counted); usage documented.
- Pricing verification: `params.yaml` corrected to Vertex AI rates (`$0.30` input / `$2.50` output, `2026-10-23`); source = Vertex AI Pricing (consistent with live call); Google AI Studio pricing page transport error recorded (W-A1 §6); no third-party tracker relied upon.
- Lifecycle/deprecation: primary-source page unreachable — no explicit retirement date confirmed; near-term retirement cannot be ruled out (`wave_a_return.md` §1, W-A1); **ADR-034 stop rule applies** — any near-term deprecation date triggers ADR-034 decision (no silent swap).

## Stop-rule / escalation

Per `remediation_plan.md` A-07 / W-A1 condition 4: near-term deprecation → return ADR-034 decision; never swap silently. No deprecation date confirmed at time of verification (`d8be010`); verification remains open until either (a) primary pricing/lifecycle page confirms stable lifecycle, or (b) deprecation notice appears — at which point ADR-034 activates.

## Impact on Phase 4

A-07 is non-blocking for decoupled Tier 3 build (`remediation_plan.md` §6, Gate R-A vs. R-B). Phase 4 planning (this document) does not require live provider calls — only the gateway qualification (W-A4, completed: structured-output validated) and the contract (v2, completed). A-07 verification must complete before any Phase 4 live call relies on `gemini-2.5-flash` as primary.
