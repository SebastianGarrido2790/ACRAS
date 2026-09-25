# Product Requirements Document — ACRAS (Agentic Credit Risk & Analysis System)

**Author:** Sebastián Garrido Arévalo · **Date:** 2026-08-28 · **Version:** 2.0

---

## Document Overview

- **What it is:** The Product Requirements Document (PRD) specifying formal functional requirements (FR1–FR13), non-functional requirements, release gates, and governance policies for ACRAS.
- **Why it exists:** Serves as the authoritative functional specification and quality contract, enforcing critical validation rules (such as mandatory probability calibration gates and persona divergence gates) prior to promotion.
- **How to use it:** Consult this document to guide feature implementation, verify API and evidence-bundle contracts, check quantitative escalation thresholds, and validate acceptance criteria.

---

## Executive Summary

ACRAS turns SME (Small and Medium-sized Enterprise) credit underwriting from a 5–10 day manual process into a minutes-long, auditable one by combining a frozen, calibrated ML model with a parallel multi-agent interpretation layer. A vectorized Monte Carlo engine converts the model's point prediction into a full risk distribution; three specialist agents: a risk officer, a growth-oriented deal originator, and a capital-cost officer independently interpret that distribution and a shared evidence bundle, and a convergence node either synthesizes their agreement or routes genuine disagreement to a human. The system is only as valuable as two properties it must actively prove, not assume: that the underlying probabilities are calibrated (not just well-ranked), and that the three agents produce reasoning that actually diverges when the evidence warrants it. Both are treated here as release gates, not aspirations.

## Project Analogy

Imagine a bank's credit committee, with a risk officer, a growth-focused deal originator, and a finance officer worried about capital, sitting down to debate a loan file together. Normally that takes a week to convene and write up. ACRAS convenes AI stand-ins for those three roles instantly, has them read the exact same evidence, and reports back not just their conclusion but _where they disagreed and why_. The numbers behind the debate come from a calculator that never guesses; only the discussion happens in natural language.

## Problem Statement (Stakeholder Perspective)

Credit analysts, risk officers, and commercial teams share one structural complaint from different angles: the current process forces a choice between speed and defensibility. A fast answer (a raw model score) can't be defended to an auditor or a committee on its own; a defensible answer (a full manual write-up) takes too long to be commercially useful. No existing tool lets a lender get both at once, because doing so requires an architecture that keeps deterministic computation and interpretive judgment as two separate failure domains, most attempts either bolt an LLM directly onto the numbers (introducing hallucination risk into the calculation itself) or keep the model purely quantitative and uninterpretable.

## Goals & Non-Goals

**Goals:**

- Reduce turnaround for a standard SME file from 5–10 days to under 15 minutes.
- Replace a single PD point estimate with a full risk distribution (P10/P50/P90).
- Produce genuinely divergent, committee-style interpretation rather than one blended voice.
- Keep every quantitative claim traceable to a deterministic calculation.
- Escalate contested files to a human rather than auto-resolving them.

**Non-Goals:**

- No automatic loan approval — the system produces a recommendation, never a binding decision.
- No live core-banking integration, fraud detection, real-time transaction monitoring, portfolio-level stress testing, retail (non-SME) credit, or regulatory filing generation in this iteration.

## Personas (Summary)

Full detail lives in `user_story.md`. In brief:

- **Ana, SME Credit Analyst** — day-to-day operator; submits files, reviews reports, escalates when flagged.
- **Rodrigo, Head of Credit Risk** — oversight/approver; cares about audit trail, model calibration, and visibility into disagreement rather than silent averaging.
- **Marcela, Commercial/Growth Lead** — originates deals; cares about turnaround speed and getting a specific, actionable reason when a deal is declined or downgraded.

## Functional Requirements

| ID   | Requirement                                                                                                                                                                                                  |
| ---- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| FR1  | Accept a structured company profile as input via API and dashboard.                                                                                                                                          |
| FR2  | Compute a PD via the frozen Tier 1 model, served through FastAPI.                                                                                                                                            |
| FR3  | Run a vectorized Monte Carlo simulation (N ≥ 10,000) producing P10/P50/P90 default/loss bands from the Tier 1 output.                                                                                        |
| FR4  | Convert PD into a credit rating category (e.g., AAA–CCC) via a versioned, documented mapping.                                                                                                                |
| FR5  | Compute financial ratios (EBITDA, margins, leverage) from structured input via the Financial/Domain Analyst Agent.                                                                                           |
| FR6  | Run three persona agent nodes (CRO (Chief Risk Officer), Portfolio Growth Director, CFO (Chief Finance Officer)/Capital Allocation Director) in parallel against one shared, typed evidence-bundle contract. |
| FR7  | Run a convergence node that reconciles persona outputs **and computes a quantitative divergence score** between them.                                                                                        |
| FR8  | Escalate to human-in-the-loop review whenever the divergence score exceeds a documented threshold, or Tier 1 confidence falls below a documented threshold.                                                  |
| FR9  | Log a full machine-readable trace per report: tool calls, fallback events, PD/Monte Carlo bands, per-persona verdicts, divergence score.                                                                     |
| FR10 | Fall back to a secondary LLM provider via a circuit breaker if the primary provider fails or times out.                                                                                                      |
| FR11 | Block model training when Great Expectations data-contract checks fail.                                                                                                                                      |
| FR12 | Block model **promotion to serving** unless the candidate passes both a calibration check and a discrimination check — good AUC alone is insufficient.                                                       |
| FR13 | Block Tier 3 **promotion to serving** unless it passes a divergence-check gate against engineered golden-set cases — grounding/fluency checks alone are insufficient.                                        |

FR12 and FR13 exist specifically to prevent the two failure modes flagged during design review: a well-ranked but miscalibrated model silently corrupting every downstream tier, and three agents that read as thoughtful but never actually disagree.

## Non-Functional Requirements

- **Latency:** full report under ~15 minutes wall-clock; target under 2 minutes for a typical case (dominated by LLM round-trips, not the ML/Monte Carlo layers).
- **Cost:** per-report LLM cost under a defined ceiling (target < $0.15).
- **Reliability:** system completes without unhandled failure under a simulated primary-provider outage.
- **Auditability:** every report traceable end-to-end without re-running the pipeline.
- **Model quality bar:** calibration (e.g., Brier score / reliability curve) within documented bounds, in addition to discrimination metrics, before serving.
- **Decision-quality bar:** measurable, quantified disagreement on divergence-engineered golden cases before serving.
- **Reproducibility:** Tiers 1–2 are deterministic and version-pinned (same input + same model version → identical output); Tier 3 is non-deterministic but fully versioned and logged.

## System Architecture

Frozen Tier 1 (FastAPI-served PD model) → Tier 2 (vectorized Monte Carlo, consumes Tier 1's output distribution, no retraining dependency) → Tier 3 (LangGraph fan-out to CRO / Growth / Capital persona nodes reading one Pydantic evidence bundle, fan-in to a convergence node) → Orchestrator (aggregates into the executive report) → Dashboard (Risk Manager–facing input/output). An LLM gateway with a circuit breaker sits in front of all LLM calls; a Great Expectations gate sits in front of the DVC training pipeline. Full component detail lives in `canvas.md` (Solution) and will be finalized as the actual-state record in `system_design.md`.

## Data Sources

Training: a public structured credit-risk dataset (financial ratios + default/no-default label), schema-validated before DVC tracks a version. Production/demo input: synthetic, structured company profiles entered via the dashboard, no free-text scraping, to avoid a training/production mismatch. Evaluation: a hand-authored golden set (~20–40 cases) purpose-built to exercise calibration edge cases and engineered divergence scenarios, since there is no live production traffic to sample from.

## Primary Scenario (Acceptance Criteria)

**Scenario 1 — happy path:**
_Given_ a company profile with strong financials and a modest requested loan amount, _when_ submitted to ACRAS, _then_ the system returns a report within 2 minutes containing a PD, P10/P50/P90 bands, a credit rating, and three persona verdicts with a divergence score below the escalation threshold — auto-finalized without human review.

**Scenario 2 — engineered divergence (the gate that matters most):**
_Given_ a company profile engineered with a marginal PD, strong revenue growth, and a thin capital buffer, _when_ submitted to ACRAS, _then_ the CRO persona flags elevated risk, the Growth persona recommends approval citing growth potential, the Capital persona flags capital strain, the divergence score exceeds the escalation threshold, and the file routes to human-in-the-loop review instead of auto-resolving.

**Scenario 3 — calibration gate:**
_Given_ a candidate Tier 1 model retrained on updated data, _when_ evaluated against the golden dataset before promotion, _then_ it is promoted only if its calibration metric is within documented bounds in addition to its discrimination metric — a model with strong AUC but poor calibration is blocked from deployment.

## Success Metrics & KPIs

Turnaround time per file (target < 15 min); cost per report (target < $0.15); % of divergence-engineered golden-set cases correctly flagged as divergent; LLM-as-judge grounding pass rate (no invented figures); Tier 1 calibration metric within documented bounds at every promotion.

## Out of Scope (Future Iterations)

Fraud detection, real-time transaction monitoring, portfolio-level stress testing, retail (non-SME) credit, regulatory adverse-action filing generation, live core-banking integration, production multi-tenant auth.

## Dependencies & Constraints

Public dataset availability and quality; LLM provider API access/quotas for both primary and fallback providers; DVC/MLflow/Great Expectations tooling; solo-builder mindset.

## Resolved Decisions

**Divergence measurement (resolved).** Divergence is computed deterministically, not by an LLM judge scoring semantic similarity between narratives — a probabilistic measurement on top of a probabilistic output would violate the deterministic-core/probabilistic-shell principle this system is built on. Each persona emits a small Pydantic-validated structured verdict alongside its narrative rationale:

```python
class PersonaVerdict(BaseModel):
    recommendation: Literal["approve", "conditional", "decline"]
    lean: float = Field(ge=-1.0, le=1.0)   # risk-appetite position
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str                          # narrative, for the human report only
```

The divergence score is a plain, unit-testable function over three of these objects: categorical mismatch across `recommendation` combined with variance of `lean`. The escalation **threshold is provisional**, calibrated against the golden set by picking the operating point that separates author-labeled "should converge" cases from "should diverge" cases — analogous to choosing an operating point on an ROC curve. It is documented here as a starting point pending real usage data, not a final, principled constant.

**Temperature (resolved).** Temperature is **not** the divergence mechanism. All three personas run at the same low, uniform temperature (≈0–0.2) for reproducibility and auditability — temperature-driven divergence would mean the same file could flip between auto-approve and HITL escalation on a re-run with no underlying cause, which is a defect in the tier meant to be most trustworthy, not a feature. Genuine divergence is instead engineered structurally: (1) a distinct, explicit evaluation rubric per persona (CRO weighted toward P90 tail loss and covenant history; Growth weighted toward revenue trajectory and pipeline value; Capital weighted toward capital consumption and concentration), and (2) role-specific derived fields foregrounded from the identical shared evidence bundle — same facts, different lens per mandate. A regression test re-runs the same case through the same persona twice at fixed settings and asserts the recommendation category doesn't move; if it does, temperature is doing more work than intended.

**Explicitly deferred (not MVP scope):** loan-size-scaled divergence thresholds and self-consistency majority voting across repeated persona calls. Real refinements, but out of scope against solo-builder bandwidth, which is already the top-flagged project risk.

## Open Questions / Risks (Revisit After Implementation)

- Does the chosen public dataset contain enough genuinely marginal/ambiguous cases to build a realistic divergence golden set, or will cases need to be hand-crafted synthetically?
- Once real output data exists, does the ROC-style provisional threshold hold up, or does it need re-calibration against actual usage patterns?
- Should disagreement patterns be logged and mined over time to detect a given persona's "voice" drifting (e.g., the CRO persona growing systematically more conservative across model/prompt updates)?
