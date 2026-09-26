# Scoping Document — ACRAS (Agentic Credit Risk & Analysis System)

**Author:** Sebastián Garrido Arévalo · **Date:** 2026-09-25

**What this is:** A problem-framing document that sits upstream of the PRD — its job is to justify the shape of the system.

**Why it exists:** so problem framing, constraints, and success metrics live in one place instead of two overlapping ones, and so "does an LLM/agent even make sense here" is answered by evidence (§0 below and `capability_profile_gates.md`), not asserted.

**How to use it:** read this before the PRD; where this document and the PRD appear to disagree, the PRD is more detailed and wins on implementation specifics, but this document's problem framing and constraints are the source those specifics trace back to.

---

## 1. Project Summary

- **Problem (surface vs. real):** Surface — SME credit risk assessment takes 5–10 manual days. Real engineering problem — how to compose a deterministic, auditable numerical model with non-deterministic LLM reasoning so the LLM adds interpretive judgment without corrupting, inventing, or silently substituting for the numbers underneath it, and how to get three LLM calls reading identical evidence to produce genuinely different reasoning instead of three stylistic variations of one answer.
- **Why it matters / impact:** Collapses a throughput-bound, judgment-inconsistent manual process into a minutes-long, auditable one — without giving up the risk/growth/capital tension a real credit committee holds internally, which a single blended score or summary would erase.
- **Proposed approach:** A frozen, calibrated ML core (Tier 1) feeding a vectorized Monte Carlo risk distribution (Tier 2), interpreted by three parallel, rubric-differentiated LLM personas (Tier 3) that converge or explicitly diverge via a deterministic scoring function — never an LLM judging another LLM's prose.
- **Primary success metric:** % of divergence-engineered golden-set cases where the three personas register a materially different verdict — this is the one metric that validates the entire premise of building Tier 3 as multiple agents rather than one.
- **Key risks / unknowns:** persona non-divergence (Runbook §1), silent model miscalibration (Runbook §2), and the schedule risk already on record in the Technical Roadmap (Phase 4 is the largest, least de-risked phase).

## 2. Business / User Problem

Full detail in `user_story.md`. In brief: an SME credit analyst, a Head of Credit Risk, and a commercial/growth lead each experience the same underlying problem from a different angle — the current process forces a choice between a fast answer and a defensible one.

**Why an LLM/agentic approach, not traditional software, rules, or classical ML alone:** this is answered more rigorously by `capability_profile_gates.md` than restated here — in short, interpreting a risk distribution against three genuinely conflicting business mandates is high-variance judgment a rule table can't encode, but the arithmetic underneath that judgment must stay deterministic, which is exactly the split this architecture enforces (INV-1, INV-2).

## 3. Goal

Reduce SME file turnaround from 5–10 days to under 15 minutes; replace a single PD point estimate with a full risk distribution; produce genuinely divergent, auditable interpretation rather than one blended recommendation; keep every quantitative claim traceable to a deterministic calculation; route contested files to a human rather than auto-resolving them. Tied to the certificate's own timeline: full system through Phase 7 by late September 2026 (Technical Roadmap, with the schedule risk already documented there).

## 4. End State

A working, portfolio-grade multi-agent system that takes a single company's financial and credit profile and, within minutes, returns an auditable executive risk report combining a calibrated default-probability distribution with three independently-reasoned credit-committee perspectives, a risk officer, a growth-oriented deal originator, and a capital-cost officer that explicitly surface disagreement rather than resolve to one blended voice, with every number in the report traceable to a deterministic calculation or an evaluated, versioned LLM output.

**Definition of done:** all three tiers running end-to-end; golden/adversarial evaluation passing its thresholds including the divergence check; the GX data-contract gate wired and provably blocking bad data; the circuit breaker and fallback demonstrated under a simulated outage; documentation and code published.

## 5. Stakeholders

**In-system persona (primary):** SME Credit Analyst, Head of Credit Risk, Commercial/Growth Lead — full stories in `user_story.md`. **Real-world audience (secondary, stated plainly rather than dressed up as the primary audience):** technical hiring managers and the Professional Certificate's instructor evaluating engineering practice; this is a portfolio artifact, not a paid engagement, and that honestly shapes some choices (no production auth/multi-tenancy) that a paying customer's deployment would need. **Team:** solo build (Sebastián Garrido Arévalo) — no separate PM/Eng/Design/Legal roles exist to list.

## 6. The ROI Situation (Brutally Honest)

There is no captured ROI, this is a portfolio project, not a deployed system with a paying customer or real loss data. Honestly stated:

- As a demo, ACRAS proves an architectural pattern (frozen deterministic core + probabilistic interpretation layer). A real lender would still need to validate it against its own loss history before any turnaround-time or cost claim is credible.
- The realistic ROI case in an actual deployment is analyst-hours saved on the "clean" majority of files that don't need escalation, not full automation of the decision. The harder, disputed files still need a human, so the real savings ceiling is bounded by file mix, not by system capability.
- The three-persona debate pattern deliberately costs more in LLM spend and latency than a single summarization call; that trade only pays for itself if genuine divergence is demonstrated (§1's primary success metric), otherwise it's added cost with no added decision value, and this document treats that as a real possibility being tested, not a formality being waved through.

## 7. Prior Work

An earlier, single-tier version of ACRAS (a direct PD-model-plus-FastAPI proof of concept, predating this three-tier redesign) already validated the core tool-calling and MLOps pattern — DVC/MLflow-tracked training, a model wrapped as an agent-callable tool — and is the baseline this redesign supersedes, not a from-scratch start. The incumbent industry approach this project stands in contrast to is traditional rule-based credit scorecards (fast, auditable, but rigid and unable to surface interpretive disagreement) and, at the other extreme, an unconstrained "LLM writes the credit memo" approach (flexible but untrustworthy for the numbers themselves) — the rejection of that second approach is documented in detail as the Merging Test in `tier3_persona_architecture.md` §1.

## 8. Input and Output

**Input:** a structured company profile — financial statement fields, requested loan amount/term, structured qualitative fields (sector, covenant history). No free-text or scraped input in current scope. **Output:** an executive risk report (PD, risk distribution, credit rating, three persona verdicts, convergence outcome) plus a full machine-readable trace (tool calls, fallback events, divergence score) persisted for audit. **What's stored:** the evidence bundle and trace log per report (Roadmap Phase 6); no cross-request persistent memory (Tier 3 is single-shot per report, per `capability_profile_gates.md` Part 1, Gate 5).

## 9. Constraints

| Constraint                | Target                                                                            | Notes                                                                                                                                       |
| ------------------------- | --------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| Latency (p50 / p99)       | p50 < 2 min · p99 < 15 min                                                        | Dominated by LLM round-trips, not the ML/Monte Carlo layers (sub-5ms).                                                                      |
| Cost per request          | < $0.15                                                                           | Three persona calls + one deterministic convergence pass — no self-consistency multiplier.                                                  |
| Quality bar — calibration | Brier score within documented bounds, in addition to AUC/KS                       | Exact numeric bound is **not yet fixed** — pending a real baseline from Phase 1; stated here as provisional, not invented to fill the cell. |
| Quality bar — divergence  | Provisional target: ≥ 90% of engineered-divergence golden cases correctly flagged | **Proposed, needs your sign-off** — no real usage data exists yet to justify a precise number; flagged rather than asserted as final.       |
| Privacy / compliance      | No real PII; synthetic/public data only in current (demo) scope                   | A real deployment would need financial-data handling compliance not yet in scope — stated honestly rather than glossed over.                |
| Availability / uptime     | Not applicable at demo scale                                                      | Single-instance, no SLA; stating a fabricated "99.5%" for a portfolio demo would be dishonest, not rigorous.                                |

## 10. Success Metrics

- **User-facing:** turnaround time per file; whether an analyst can point to a specific, reproducible computation behind the report rather than a black-box score.
- **Technical:** % of divergence-engineered golden-set cases correctly flagged as divergent (the metric that validates Tier 3's existence); LLM-as-judge grounding pass rate (no invented figures); Tier 1 calibration metric within documented bounds at every promotion.
- **System:** latency (p50/p99); cost per report; circuit-breaker trip rate (a reliability signal, not just a failure count); uptime (N/A at demo scale, per §9).

## 11. Checklist

- [x] Evidence the problem is worth solving — the 5–10 day manual turnaround and its throughput/consistency cost (§1, §2).
- [x] Evidence an LLM/agentic approach is the right tool — `capability_profile_gates.md`, completed independently of this document.
- [x] Goals and metrics aligned with stakeholder priorities — Ana/Rodrigo/Marcela's stories in `user_story.md` map directly onto §3's goals.
- [ ] Scope shared with relevant stakeholders — honestly: N/A in the conventional sense. This is a solo portfolio build; the "stakeholder review" that exists is this document's own approval cycle, not a team sign-off. Marked unchecked rather than checked dishonestly.
- [x] Decisions and trade-offs recorded in a decision log — `system_design.md`'s ADR ledger, ADR-001 through ADR-016 (pending).

## 12. What Could Go Wrong

- **Headline risks:** persona non-divergence, silent calibration failure, and — per `capability_profile_gates.md` Gate 4's finding above — building Tier 3 with no data-driven divergence check until Phase 5, which is why this document proposes pulling a small seed golden-set forward into Phase 4 itself.
- **Persona non-divergence:** the three LLM agents converge to near-identical output regardless of prompting, making Tier 3 a cost center with no decision value. This is a genuine research risk, not just an implementation detail — mitigated by, but not eliminated by, the divergence-engineered golden set.
- **Calibration failure:** the PD model separates well (good AUC) but is poorly calibrated, silently making the Monte Carlo bands and every downstream rating numerically wrong even though the model "looks good" on ROC — mitigated by treating calibration metrics as a first-class evaluation gate, not an afterthought.
- **Scope creep** into production concerns (auth, multi-tenancy, real core-banking integration) that would blow the timeline without adding to what the architecture is meant to demonstrate.
- **LLM cost/rate-limit exposure** during repeated evaluation runs — mitigated by caching and by keeping the golden set intentionally small (~20–40 cases) rather than large.
- **Solo-builder bandwidth:** The honest constraint is time, not technical feasibility — the phased roadmap exists to manage that risk, not to pad this document.
