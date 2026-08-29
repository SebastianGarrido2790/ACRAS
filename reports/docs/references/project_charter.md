# Project Charter — ACRAS (Agentic Credit Risk & Analysis System)

**Author:** Sebastián Garrido Arévalo · **Date:** 2026-08-28 · **Version:** 2.0 (three-tier redesign)

---

## Document Overview

- **What it is:** The foundational Project Charter defining project scope, target personas, business problem framing, realistic ROI appraisal, Definition of Done, and large-scale cost models for ACRAS.
- **Why it exists:** Establishes clear organizational boundaries, non-goals, and engineering criteria to guide decision-making and prevent scope creep.
- **How to use it:** Refer to this document to verify project scope, audit completion against the Definition of Done, review infrastructure and LLM cost estimates, and understand the organizational rationale behind architectural choices.

---

### 1. End State

A working, portfolio-grade multi-agent system that takes a single company's financial and credit profile as input and, within minutes, returns an auditable executive risk report combining a calibrated default-probability distribution with three independently-reasoned credit-committee perspectives, a risk officer, a growth-oriented deal originator, and a capital-cost officer, that explicitly surface disagreement rather than resolve to one blended voice. The system runs end-to-end on public data with a documented MLOps pipeline (data contracts, experiment tracking, evaluation gates), so that every claim in the report is either a deterministic calculation or an evaluated, versioned LLM output.

### 2. Audience

**Primary (in-system persona):** a Risk Manager or SME (Small and Medium-sized Enterprise) credit analyst at a digital lender or bank, who is the actual user the dashboard and report are designed for.

**Secondary (real-world audience for this build):** technical hiring managers. This is a portfolio artifact, not a paid engagement, and that honestly shapes some choices — e.g., a single-tenant demo dashboard instead of production auth/multi-tenancy — that a paying customer's deployment would need but that aren't the point of this demonstration.

### 3. Problem Framing

**Surface problem:** "SME credit risk assessment is slow and inconsistent."

**Real engineering problem:** how to compose a deterministic, auditable numerical model with non-deterministic LLM reasoning so the LLM adds interpretive judgment without being able to corrupt, invent, or silently substitute for the numbers underneath it — and how to get genuinely distinct reasoning out of three LLM calls that all see identical evidence, rather than three stylistic variations of the same answer.

### 4. The ROI Situation (brutally honest)

There is no captured ROI, this is a portfolio project, not a deployed system with a paying customer or real loss data. Honestly stated:

- As a demo, ACRAS proves an architectural pattern (frozen deterministic core + probabilistic interpretation layer). A real lender would still need to validate it against its own loss history before any turnaround-time or cost claim is credible.
- The realistic ROI case in an actual deployment is analyst-hours saved on the "clean" majority of files that don't need escalation, not full automation of the decision. The harder, disputed files still need a human, so the real savings ceiling is bounded by file mix, not by system capability.
- The three-persona debate pattern deliberately costs more in LLM spend and latency than a single summarization call would. That trade only pays for itself if genuine divergence is demonstrated (see the Canvas's decision-quality metric) — otherwise it's added cost with no added decision value, and the charter treats that as a real possibility, not a formality to wave through.

### 5. Definition of Done

Done means: all three tiers run end-to-end against the public dataset; the golden/adversarial evaluation set passes its defined thresholds, including the cross-persona divergence check; the Great Expectations data-contract gate is wired into the DVC pipeline; the circuit breaker and cross-provider fallback are demonstrated under a simulated provider outage; at least one full sample report has been manually reviewed for hallucination-free grounding; and the documentation set (canvas, charter, PRD, roadmap, ADR, runbook) is complete alongside the published code and demo.

Explicitly **not** required for "done": real customer integration, production auth/multi-tenancy, or live regulatory filing generation. These are named non-goals, not unfinished work.

### 6. Large-Scale Costs (real numbers, not marketing)

**At demo scale:** near-zero — free-tier LLM calls, a single small container instance, no vector database (qualitative inputs stay structured, not RAG-scale).

**At a hypothetical production scale** (~5,000 SME applications/month), rough back-of-envelope figures, not a costed vendor proposal:

- Three persona calls + one synthesis call per report at ~2–4k tokens each on a mid-tier model: roughly **$0.05–$0.20 per report** in model cost alone depending on provider/model choice → **~$250–$1,000/month** in LLM spend at that volume.
- Tier 1/Tier 2 compute (CPU-bound, sub-5ms) is negligible next to LLM cost.
- Hosting (small container service + a Postgres instance for audit logs): roughly **$100–$300/month**.
- Not included above, but real in production: ongoing engineering time for prompt-drift monitoring and eval-set maintenance — a recurring cost, not a one-time build cost.

### 7. Technology Stack

FastAPI (Tier 1 serving) · scikit-learn / XGBoost or LightGBM (PD model) · NumPy-vectorized Monte Carlo (Tier 2) · LangGraph + Pydantic AI (Tier 3 orchestration and typed evidence-bundle contracts) · Gemini API as primary LLM provider with a second provider as fallback behind a custom circuit breaker · MLflow + DVC + Great Expectations (tracking, data versioning, data-contract gating) · Docker · a lightweight dashboard (Streamlit or a small FastAPI+HTML front end) · GitHub Actions for CI.

### 8. Core Concepts

- **Deterministic core / probabilistic shell** — the ML model and Monte Carlo engine are frozen and versioned; only the interpretation layer around them is allowed to be non-deterministic.
- **Evidence bundle** — the single typed contract that is the only channel through which the three persona agents see the world, guaranteeing they're arguing about the same facts.
- **Fan-out / fan-in** — the three personas run in parallel against the same evidence bundle; a convergence node reconciles or escalates.
- **Disagreement as signal** — the system is designed to preserve and surface disagreement rather than average it away, because a report that always agrees with itself has no decision value to a credit committee.
- **Circuit breaker / provider fallback** — a runtime pattern, independent of business logic, protecting the system from a single LLM provider's outage or rate limit.
- **Data contract gate** — Great Expectations checks that must pass before DVC allows a new model version to train, keeping bad data out of Tier 1 at the source.

### 9. What Could Go Wrong

- **Persona non-divergence:** the three LLM agents converge to near-identical output regardless of prompting, making Tier 3 a cost center with no decision value. This is a genuine research risk, not just an implementation detail — mitigated by, but not eliminated by, the divergence-engineered golden set.
- **Calibration failure:** the PD model separates well (good AUC) but is poorly calibrated, silently making the Monte Carlo bands and every downstream rating numerically wrong even though the model "looks good" on ROC — mitigated by treating calibration metrics as a first-class evaluation gate, not an afterthought.
- **Scope creep** into production concerns (auth, multi-tenancy, real core-banking integration) that would blow the timeline without adding to what the architecture is meant to demonstrate.
- **LLM cost/rate-limit exposure** during repeated evaluation runs — mitigated by caching and by keeping the golden set intentionally small (~20–40 cases) rather than large.
- **Solo-builder bandwidth:** this runs in parallel with a 7-session, 4-lab certificate. The honest constraint is time, not technical feasibility — the phased roadmap exists to manage that risk, not to pad this document.
