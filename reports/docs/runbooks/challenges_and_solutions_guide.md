# Challenges & Solutions Guide — ACRAS (Agentic Credit Risk & Analysis System)

**Author:** Sebastián Garrido Arévalo · **Date:** 2026-08-28 · **Status:** Pre-implementation — seeded with anticipated entries only

---

## Document Overview

- **What it is:** An engineering runbook and challenge catalog documenting anticipated failure modes, observed edge cases, root causes, governing architectural authorities (ADRs/PRD), and verified resolutions for ACRAS.
- **Why it exists:** Provides pre-authorized solutions for critical technical failure modes (e.g., persona non-divergence, calibration drift, provider outages, ungrounded hallucinated figures), preventing ad-hoc or unprincipled fixes during development and operation.
- **How to use it:**
  - **Structure:** Each entry records a **Challenge Domain**, **Problem/Symptom**, **Root Cause**, **Solution**, and **Governing Authority** (the planning artifact that established the decision).
  - **Lifecycle & Updates:** Initial entries carry **Status: Anticipated**. When an issue is encountered during implementation, append a new entry with **Status: Encountered & Resolved** detailing observed reality versus anticipation. Anticipated entries are preserved as evidence of proactive design.

---

## 1. Persona Non-Divergence

**Status:** Anticipated
**Challenge Domain:** Multi-agent design / LLM behavior
**Problem/Symptom:** The CRO, Growth, and Capital persona nodes produce near-identical recommendations even on divergence-engineered golden-set cases — Tier 3 becomes three stylistic restatements of one answer.
**Root Cause:** Insufficiently distinct rubrics or derived-field emphasis per persona, or an LLM's default tendency toward consensus-shaped output regardless of role framing.
**Solution:** Rubric-conditioned prompts and role-specific derived fields per persona (not temperature); validated by the divergence-check gate before any Tier 3 promotion — a configuration that fails this check does not ship, regardless of how well it performs elsewhere.
**Governing Authority:** ADR-004, ADR-005; PRD FR13.

## 2. Silent Calibration Failure

**Status:** Anticipated
**Challenge Domain:** ML modeling
**Problem/Symptom:** The Tier 1 model shows strong AUC/KS separation but its predicted probabilities don't match observed default frequencies — every downstream Monte Carlo band and rating is numerically wrong despite the model "looking good."
**Root Cause:** Gradient-boosted models are commonly tuned for discrimination, not calibration, by default; without an explicit calibration step, good ranking and good probability estimates are two different properties that get conflated.
**Solution:** Brier score / reliability curve computed as a mandatory promotion gate, separate from and in addition to AUC/KS; post-hoc calibration (Platt scaling or isotonic regression) applied if the raw model output fails the gate, before the model is frozen for serving.
**Governing Authority:** ADR-003; PRD FR12.

## 3. Data Contract Drift

**Status:** Anticipated
**Challenge Domain:** Data engineering / MLOps
**Problem/Symptom:** A new training data pull silently differs from the original contract — schema change, unexpected nulls, out-of-range values — and a model trains on it anyway.
**Root Cause:** Source dataset updates without a corresponding contract review.
**Solution:** Great Expectations validates the data contract in front of the DVC pipeline; a failed expectation halts training before a bad model can be produced.
**Governing Authority:** ADR-007.

## 4. LLM Provider Outage or Rate-Limiting

**Status:** Anticipated
**Challenge Domain:** Reliability / infrastructure
**Problem/Symptom:** Tier 3 calls fail, hang, or degrade in latency due to the primary LLM provider being down or rate-limited.
**Root Cause:** Single-provider dependency with no automatic fallback.
**Solution:** LLM gateway with a circuit breaker (defined timeout / consecutive-error thresholds) and automatic failover to a secondary provider.
**Governing Authority:** ADR-006.

## 5. Non-Reproducible Escalation on Re-Run

**Status:** Anticipated
**Challenge Domain:** Multi-agent reliability / auditability
**Problem/Symptom:** Re-running the identical case through Tier 3 produces a different recommendation or a different HITL escalation outcome with no change in input.
**Root Cause:** Sampling randomness (high or inconsistent temperature) driving output variance instead of structured, reasoned differences.
**Solution:** Uniform low temperature (~0–0.2) across all three personas; a fixed-settings regression test asserts the same case run twice returns the same recommendation category — any drift fails the test rather than being explained away after the fact.
**Governing Authority:** ADR-005; Technical Roadmap Phase 5.

## 6. Ungrounded Figures in Persona Rationale

**Status:** Anticipated
**Challenge Domain:** Agent output quality / trust
**Problem/Symptom:** A persona's narrative rationale cites a number — a ratio, a percentage, a dollar figure — that doesn't actually appear anywhere in the evidence bundle.
**Root Cause:** Narrative generation isn't strictly constrained to cite only fields present in the structured evidence bundle.
**Solution:** LLM-as-judge grounding check against the golden set as a release gate; prompts explicitly restrict cited figures to evidence-bundle fields, and evaluation checks for violations rather than assuming prompting alone is sufficient.
**Governing Authority:** PRD FR13 / auditability NFR; Technical Roadmap Phase 5.

## 7. Golden Dataset Blind Spots

**Status:** Anticipated
**Challenge Domain:** Evaluation methodology
**Problem/Symptom:** The golden set passes cleanly, but real report generation still surfaces an issue no test case covers.
**Root Cause:** A hand-authored set of ~20–40 cases has inherently limited coverage, and the underlying public dataset may not contain enough genuinely marginal or ambiguous real-world cases to sample from.
**Solution:** Deliberately engineer synthetic edge cases targeting each known failure mode (calibration edge, divergence edge, missing/incomplete data) rather than relying only on sampled cases; treat golden-set expansion as ongoing, triggered every time a new failure mode is discovered — not a one-time deliverable that's considered finished after Phase 5.
**Governing Authority:** PRD Open Questions; Canvas §6/§8.

## 8. Phase 4 Schedule Slip

**Status:** Anticipated
**Challenge Domain:** Project management
**Problem/Symptom:** Phase 4 (Tier 3 multi-agent core) exceeds its 7–10 day estimate, threatening the Session 7 (2026-09-29) target.
**Root Cause:** Phase 4 is both the largest and least de-risked phase in the roadmap, and it runs in parallel with certificate coursework hours rather than in dedicated full-time blocks.
**Solution:** A de-scope lever was pre-agreed rather than decided under deadline pressure: degrade Phase 6's dashboard to a CLI or notebook-driven interface, which preserves every PRD requirement, acceptance scenario, and governance gate untouched.
**Governing Authority:** Technical Roadmap, Schedule Risk section.

## 9. Evidence-Bundle Schema Drift

**Status:** Anticipated
**Challenge Domain:** Software architecture / contract management
**Problem/Symptom:** A tier or agent starts silently depending on a field the shared evidence-bundle schema doesn't guarantee, or two components disagree on a field's meaning.
**Root Cause:** Incremental schema evolution (v0 → v1 → v2) without versioning discipline, or an ad hoc field added mid-implementation to solve an immediate problem.
**Solution:** The evidence bundle is versioned once per roadmap phase in Pydantic, with changes made only at declared phase boundaries and recorded as new ADR entries — never patched silently mid-phase.
**Governing Authority:** ADR-002; System Design §5 (Data Flow).

## 10. Per-Report Cost Overrun

**Status:** Anticipated
**Challenge Domain:** Cost / token economics
**Problem/Symptom:** Actual per-report LLM cost exceeds the $0.15 target.
**Root Cause:** Unbounded rationale length in persona output, or a circuit breaker retrying the primary provider too aggressively during a degradation event instead of failing fast to the fallback.
**Solution:** Token/cost logging at the gateway layer with a hard per-report budget check; a length cap on the rationale field in the output schema; the circuit breaker is tuned to fail fast rather than retry excessively.
**Governing Authority:** PRD cost NFR; ADR-006.
